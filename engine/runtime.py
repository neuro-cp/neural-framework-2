# engine/runtime.py
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

    CORE INVARIANTS:
    - Physiology integrates first
    - Competition redistributes activity only
    - Persistence is EPHEMERAL (no parameter mutation)
    - Context is gain-only (no direct activity injection)
    - No hidden learning paths
    """

    # --------------------------------------------------------
    # Initialization
    # --------------------------------------------------------

    def __init__(self, brain: Dict[str, Any], dt: float = 0.01):
        self.brain = brain
        self.dt = float(dt)

        self.time = 0.0
        self.step_count = 0

        # -----------------------------
        # Global defaults
        # -----------------------------
        gd = brain.get("global_dynamics", {}) or {}
        self.global_pop_dyn = gd.get("population_defaults", {})

        # -----------------------------
        # Assembly authority
        # -----------------------------
        self.assembly_control = self._load_assembly_control()
        self._debug_assembly_authority()

        # -----------------------------
        # Competition kernel (NO persistence inside kernel)
        # -----------------------------
        self.enable_competition = True
        self.competition_kernel = CompetitionKernel(
            inhibition_strength=0.35,
            persistence_gain=0.0,
            dominance_tau=0.25,
        )

        # -----------------------------
        # Basal ganglia persistence (external, ephemeral)
        # -----------------------------
        self.enable_persistence = True
        self.bg_persistence = BasalGangliaPersistence(
            decay_tau=30.0,
            bias_gain=0.15,
        )

        # -----------------------------
        # Runtime context (ephemeral cognitive bias)
        # -----------------------------
        self.enable_context = True
        self.context = RuntimeContext(decay_tau=5.0)

        # PFC → context hook
        self.enable_pfc_context = True
        self.pfc_context = PFCContextHook(
            activity_threshold=0.15,
            injection_gain=0.05,
        )

        # -----------------------------
        # GPi disinhibition
        # -----------------------------
        self.enable_gpi_disinhibition = True
        self.gpi_gain = 0.6
        self.gpi_floor = 0.25

        # -----------------------------
        # Runtime state
        # -----------------------------
        self.region_states: Dict[str, Dict[str, Any]] = {}
        self._all_pops: List[PopulationModel] = []
        self._stim_queue: List[Tuple[str, Optional[str], Optional[int], float]] = []
        self._region_key_by_label: Dict[str, str] = {}

        # Build network
        self._build(brain)

        print("[DEBUG] Runtime initialized")
        print(f"[DEBUG] Regions built: {len(self.region_states)}")
        print(f"[DEBUG] Assemblies built: {len(self._all_pops)}")

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

    def _debug_assembly_authority(self) -> None:
        print("[DEBUG] Assembly authority:")
        for r, n in sorted(self.assembly_control.items()):
            print(f"  {r}: {n}")

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
    # Build Populations
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
    # Step
    # ============================================================

    def step(self) -> None:
        self.step_count += 1

        # --------------------------------------------------
        # Phase 1: input reset + stimulus injection
        # --------------------------------------------------
        for p in self._all_pops:
            p.input = 0.0

        for region_key, pop_id, idx, mag in self._stim_queue:
            pops = self.region_states.get(region_key, {}).get("populations", {})
            targets = pops.values() if pop_id is None else [pops.get(pop_id, [])]
            for plist in targets:
                for p in plist if idx is None else plist[idx:idx + 1]:
                    p.input += mag

        self._stim_queue.clear()

        # --------------------------------------------------
        # Phase 2: physiology
        # --------------------------------------------------
        for pop in self._all_pops:
            pop.step(self.dt)

        # --------------------------------------------------
        # Phase 3: PFC → context extraction
        # --------------------------------------------------
        if self.enable_context and self.enable_pfc_context:
            self._step_context_hooks()

        # --------------------------------------------------
        # Phase 4: striatal competition + persistence
        # --------------------------------------------------
        if self.enable_competition:
            self._step_striatum()

        # --------------------------------------------------
        # Phase 5: context decay
        # --------------------------------------------------
        if self.enable_context:
            self.context.step(self.dt)

        # --------------------------------------------------
        # Phase 6: GPi disinhibition
        # --------------------------------------------------
        relief = self._compute_gpi_relief()

        # --------------------------------------------------
        # Phase 7: corticothalamic drive
        # --------------------------------------------------
        self._drive_thalamus(relief)

        self.time += self.dt

    # ============================================================
    # Subsystems
    # ============================================================

    def _step_context_hooks(self) -> None:
        pfc = self.region_states.get("pfc")
        if not pfc:
            return

        assemblies = [
            p for plist in pfc["populations"].values() for p in plist
        ]
        if not assemblies:
            return

        self.pfc_context.apply(
            pfc_assemblies=assemblies,
            context=self.context,
        )

    def _step_striatum(self) -> None:
        striatum = self.region_states.get("striatum")
        if not striatum:
            return

        assemblies = [
            p for plist in striatum["populations"].values() for p in plist
        ]
        if not assemblies:
            return

        external_gain: Dict[str, float] = {}

        for p in assemblies:
            gain = 1.0
            if self.enable_persistence:
                gain += self.bg_persistence.get_bias(p.assembly_id)
            if self.enable_context:
                gain *= self.context.get_gain(p.assembly_id)

            external_gain[p.assembly_id] = gain

        self.competition_kernel.apply(
            assemblies,
            self.dt,
            external_gain=external_gain,
        )

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

        activity = sum(
            p.output()
            for plist in gpi["populations"].values()
            for p in plist
        )

        return max(self.gpi_floor, 1.0 - self.gpi_gain * activity)

    def _drive_thalamus(self, relief: float) -> None:
        cortex = self.region_states.get("association_cortex")
        if not cortex:
            return

        src = [p for plist in cortex["populations"].values() for p in plist]
        if not src:
            return

        mean = sum(p.output() for p in src) / len(src)
        drive = sum((p.output() - mean) for p in src) / len(src)

        for relay in ("lgn", "md", "pulvinar", "vpl", "vpm"):
            th = self.region_states.get(relay)
            if not th:
                continue

            for plist in th["populations"].values():
                for p in plist:
                    p.input += drive * 0.02 * relief
