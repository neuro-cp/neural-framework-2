from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engine.population_model import PopulationModel
from engine.competition import CompetitionKernel
from engine.runtime_context import RuntimeContext
from engine.context_hooks import PFCContextHook
from persistence.persistence_core import BasalGangliaPersistence


# ============================================================
# Utilities
# ============================================================

def _norm(x: Any) -> str:
    return str(x or "").strip().lower()


def _as_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return int(default)


# ============================================================
# BrainRuntime
# ============================================================

class BrainRuntime:
    """
    Ground-truth dynamical runtime.

    EXECUTION ORDER (AUTHORITATIVE):
      1. Reset inputs + apply stimuli
      2. Physiology update
      3. PFC → RuntimeContext injection
      4. Striatum competition + BG persistence
      5. Context decay
      6. GPi disinhibition
      7. Connectivity propagation + Thalamic gating

    ADDITION (READ-ONLY):
      - Explicit decision latch (Checkpoint 16)
    """

    # --------------------------------------------------
    # Decision latch defaults (tuned for observability,
    # NOT for control) .15, .75, 8 steps is baseline
    # --------------------------------------------------
    DECISION_DOMINANCE_THRESHOLD = 0.04
    DECISION_RELIEF_THRESHOLD = 0.47
    DECISION_SUSTAIN_STEPS = 5

    def __init__(self, brain: Dict[str, Any], dt: float = 0.01):
        self.brain = brain
        self.dt = float(dt)
        self.time = 0.0
        self.step_count = 0

        # --------------------------------------------------
        # Global defaults
        # --------------------------------------------------
        gd = brain.get("global_dynamics", {}) or {}
        self.global_pop_dyn = gd.get("population_defaults", {})

        # --------------------------------------------------
        # Assembly authority
        # --------------------------------------------------
        self.assembly_control = self._load_assembly_control()

        # --------------------------------------------------
        # Competition kernel
        # --------------------------------------------------
        self.enable_competition = True
        self.competition_kernel = CompetitionKernel(
            inhibition_strength=0.55,
            persistence_gain=0.15,
            dominance_tau=0.75,
        )

        # --------------------------------------------------
        # Basal ganglia persistence
        # --------------------------------------------------
        self.enable_persistence = True
        self.bg_persistence = BasalGangliaPersistence(
            decay_tau=30.0,
            bias_gain=0.15,
        )

        # --------------------------------------------------
        # Runtime context
        # --------------------------------------------------
        self.enable_context = True
        self.context = RuntimeContext(decay_tau=5.0)

        self.enable_pfc_context = True
        self.pfc_context = PFCContextHook(
            activity_threshold=0.02,
            injection_gain=0.05,
            target_domain="global",
        )

        # --------------------------------------------------
        # GPi disinhibition / gating
        # --------------------------------------------------
        self.enable_gpi_disinhibition = True
        self.gpi_gain = 0.6
        self.gpi_floor = 0.25
        self._last_gate_strength: float = 1.0

        # --------------------------------------------------
        # Runtime state
        # --------------------------------------------------
        self.region_states: Dict[str, Dict[str, Any]] = {}
        self._all_pops: List[PopulationModel] = []
        self._stim_queue: List[Tuple[str, Optional[str], Optional[int], float]] = []
        self._region_key_by_label: Dict[str, str] = {}

        # --------------------------------------------------
        # Decision latch (read-only)
        # --------------------------------------------------
        self._decision_fired: bool = False
        self._decision_counter: int = 0
        self._decision_state: Optional[Dict[str, Any]] = None

        # --------------------------------------------------
        # Part B: allow sustain-step override via brain dict
        # (default remains DECISION_SUSTAIN_STEPS)
        # --------------------------------------------------
        self._decision_sustain_required: int = int(self.DECISION_SUSTAIN_STEPS)
        try:
            latch_cfg = brain.get("decision_latch", {}) or {}
            if "sustain_steps" in latch_cfg:
                self._decision_sustain_required = max(1, int(latch_cfg["sustain_steps"]))
        except Exception:
            self._decision_sustain_required = int(self.DECISION_SUSTAIN_STEPS)

        self._build(brain)

    # ============================================================
    # Assembly Control
    # ============================================================

    def _load_assembly_control(self) -> Dict[str, int]:
        path = Path(__file__).parent.parent / "config" / "assembly_control.json"
        if not path.exists():
            return {}

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        out: Dict[str, int] = {}
        for region, spec in raw.items():
            try:
                n = int(spec["assemblies"] if isinstance(spec, dict) else spec)
                out[region.lower()] = max(1, n)
            except Exception:
                pass
        return out

    # ============================================================
    # Region Resolution
    # ============================================================

    def _build_region_id_map(self, regions: Dict[str, Any]) -> None:
        self._region_key_by_label.clear()
        for key, rdef in regions.items():
            self._region_key_by_label[_norm(key)] = key
            if isinstance(rdef, dict) and rdef.get("region_id"):
                self._region_key_by_label[_norm(rdef["region_id"])] = key

    def _resolve_region_key(self, label: str) -> Optional[str]:
        return self._region_key_by_label.get(_norm(label))

    # ============================================================
    # Build Network
    # ============================================================

    def _build(self, brain: Dict[str, Any]) -> None:
        regions = brain.get("regions", {}) or {}
        self._build_region_id_map(regions)

        for region_key, region_def in regions.items():
            self.region_states[region_key] = {
                "def": region_def,
                "populations": {},
            }

            n_assemblies = self.assembly_control.get(region_key.lower())
            if n_assemblies is None:
                continue

            for pop_id, pop_blob in region_def.get("populations", {}).items():
                count = _as_int(pop_blob.get("count"), 0)
                if count <= 0:
                    continue

                size = max(1, count // n_assemblies)
                plist: List[PopulationModel] = []

                for i in range(n_assemblies):
                    params = dict(self.global_pop_dyn)
                    params.update(pop_blob)
                    params["size"] = size

                    pop = PopulationModel.from_params(
                        params,
                        default_assembly_id=f"{region_key}:{pop_id}:{i}",
                        global_defaults=self.global_pop_dyn,
                    )
                    plist.append(pop)
                    self._all_pops.append(pop)

                self.region_states[region_key]["populations"][pop_id] = plist

    # ============================================================
    # External Input API
    # ============================================================

    def inject_stimulus(
        self,
        region_id: str,
        population_id: Optional[str] = None,
        assembly_index: Optional[int] = None,
        magnitude: float = 1.0,
    ) -> None:
        rk = self._resolve_region_key(region_id) or region_id
        self._stim_queue.append((rk, population_id, assembly_index, magnitude))

    # ============================================================
    # STEP
    # ============================================================

    def step(self) -> None:
        self.step_count += 1

        # 1. Reset + stimuli
        for p in self._all_pops:
            p.input = 0.0

        for region_key, pop_id, idx, mag in self._stim_queue:
            pops = self.region_states.get(region_key, {}).get("populations", {})
            targets = pops.values() if pop_id is None else [pops.get(pop_id, [])]
            for plist in targets:
                for p in plist if idx is None else plist[idx:idx + 1]:
                    p.input += mag
        self._stim_queue.clear()

        # 2. Physiology
        for p in self._all_pops:
            p.step(self.dt)

        # 3. PFC → Context
        if self.enable_context and self.enable_pfc_context:
            self._apply_pfc_context()

        # 4. Striatum competition + persistence
        if self.enable_competition:
            self._step_striatum()

        # 5. Context decay
        if self.enable_context:
            self.context.step(self.dt)

        # 6. GPi disinhibition
        relief = self._compute_gpi_relief()
        self._last_gate_strength = relief

        # --- Decision latch evaluation (READ-ONLY) ---
        self._evaluate_decision_latch(relief)

        # 7. Connectivity + Thalamic gating
        self._propagate_connectivity(relief)

        self.time += self.dt

    # ============================================================
    # Subsystems
    # ============================================================

    def _apply_pfc_context(self) -> None:
        pfc = self.region_states.get("pfc")
        if not pfc:
            return
        assemblies = [p for plist in pfc["populations"].values() for p in plist]
        if assemblies:
            self.pfc_context.apply(assemblies, self.context)

    def _step_striatum(self) -> None:
        striatum = self.region_states.get("striatum")
        if not striatum:
            return

        assemblies = [
            p
            for plist in striatum["populations"].values()
            for p in plist
            if getattr(p, "subpopulation", None) is not None
        ]
        if not assemblies:
            return

        external_gain = {}
        external_bias = {}

        if self.enable_context:
            for p in assemblies:
                external_gain[p.assembly_id] = self.context.get_gain(p.assembly_id)
                ch = getattr(p, "subpopulation", None) or "default"
                b = self.context.get_bias(p.assembly_id)
                if b is not None:
                    external_bias.setdefault(ch, []).append(float(b))

            for ch, vals in list(external_bias.items()):
                external_bias[ch] = sum(vals) / len(vals) if vals else 0.0

        self.competition_kernel.apply(
            assemblies,
            self.dt,
            external_gain=external_gain or None,
            external_bias=external_bias or None,
        )

        self._last_striatum_snapshot = {
            "winner": self.competition_kernel.last_winner_channel,
            "dominance": dict(self.competition_kernel.last_dominance_map),
            "instant": dict(self.competition_kernel.last_instantaneous_map),
            "time": self.time,
        }

        if self.enable_persistence:
            max_out = max(p.output() for p in assemblies)
            for p in assemblies:
                if p.output() >= max_out * 0.95:
                    self.bg_persistence.reinforce(p.assembly_id, amount=0.02)
            self.bg_persistence.step(self.dt)

    def _compute_gpi_relief(self) -> float:
        if not self.enable_gpi_disinhibition:
            return 1.0

        gpi = self.region_states.get("gpi")
        if not gpi:
            return 1.0

        outs = [float(p.output()) for plist in gpi["populations"].values() for p in plist]
        if not outs:
            return 1.0

        gpi_mean = sum(outs) / len(outs)
        relief = 1.0 - self.gpi_gain * gpi_mean
        return max(self.gpi_floor, min(1.0, relief))

    # ============================================================
    # Decision Latch (Read-Only)
    # ============================================================

    def _evaluate_decision_latch(self, relief: float) -> None:
        if self._decision_fired:
            return

        snap = getattr(self, "_last_striatum_snapshot", None)
        if not snap:
            self._decision_counter = 0
            return

        dom = snap.get("dominance", {})
        if len(dom) < 2:
            self._decision_counter = 0
            return

        vals = sorted(dom.values(), reverse=True)
        delta = vals[0] - vals[1]

        if (
            delta >= self.DECISION_DOMINANCE_THRESHOLD
            and relief >= self.DECISION_RELIEF_THRESHOLD
        ):
            self._decision_counter += 1
        else:
            self._decision_counter = 0

        # Part B: sustain requirement is now runtime-configurable
        if self._decision_counter >= self._decision_sustain_required:
            self._decision_fired = True
            self._decision_state = {
                "time": self.time,
                "step": self.step_count,
                "winner": snap.get("winner"),
                "delta_dominance": delta,
                "relief": relief,
            }

    # ============================================================
    # Connectivity + Thalamic Gating
    # ============================================================

    def _propagate_connectivity(self, relief: float) -> None:
        for src_key, state in self.region_states.items():
            outputs = state.get("def", {}).get("outputs", [])
            if not outputs:
                continue

            src_pops = [p for plist in state["populations"].values() for p in plist]
            if not src_pops:
                continue

            src_drive = sum(p.output() for p in src_pops) / len(src_pops)

            for out in outputs:
                tgt_key = self._resolve_region_key(out.get("target") or out.get("region") or "")
                if not tgt_key or tgt_key not in self.region_states:
                    continue

                strength = float(out.get("strength", 1.0))

                if src_key.lower() == "gpi" and tgt_key.lower() == "md":
                    self._apply_input_to_region(tgt_key, src_drive * strength * relief)
                else:
                    self._apply_input_to_region(tgt_key, src_drive * strength)

        self._drive_thalamus(relief)

    def _apply_input_to_region(self, region_key: str, amount: float) -> None:
        region = self.region_states.get(region_key)
        if not region:
            return
        for plist in region["populations"].values():
            for p in plist:
                p.input += amount

    def _drive_thalamus(self, relief: float) -> None:
        cortex = self.region_states.get("association_cortex")
        if not cortex:
            return

        src = [p for plist in cortex["populations"].values() for p in plist]
        if not src:
            return

        mean = sum(p.output() for p in src) / len(src)
        drive = sum(abs(p.output() - mean) for p in src) / len(src)

        for relay in ("lgn", "md", "pulvinar", "vpl", "vpm"):
            th = self.region_states.get(relay)
            if not th:
                continue
            for plist in th["populations"].values():
                for p in plist:
                    p.input += drive * 0.02 * relief

    # ============================================================
    # Diagnostics / External API
    # ============================================================

    def snapshot_gate_state(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "relief": self._last_gate_strength,
            "winner": getattr(self, "_last_striatum_snapshot", {}).get("winner"),
            "decision": self._decision_state,
        }

    def get_decision_state(self) -> Optional[Dict[str, Any]]:
        return self._decision_state
