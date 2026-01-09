# engine/runtime.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engine.population_model import PopulationModel
from engine.competition import CompetitionKernel


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
# BrainRuntime — Ground-Truth Dynamics Core
# ============================================================

class BrainRuntime:
    """
    Ground-truth dynamical runtime.

    HARD INVARIANTS:
    - Physiology integrates first
    - Competition redistributes activity only
    - Routing is zero-mean and normalized
    - BG disinhibition scales routing gain only
    - No tonic excitation of inhibitory gates
    """

    def __init__(self, brain: Dict[str, Any], dt: float = 0.01):
        self.brain = brain
        self.dt = float(dt)
        self.time = 0.0
        self.step_count = 0

        gd = brain.get("global_dynamics", {}) or {}
        self.global_pop_dyn = gd.get("population_defaults", {})
        self.routing_resolver = brain.get("routing_resolver")

        # -----------------------------
        # Assembly authority
        # -----------------------------
        self.assembly_control = self._load_assembly_control()

        print("[DEBUG] Assembly authority:")
        for r, n in sorted(self.assembly_control.items()):
            print(f"  {r}: {n}")

        # -----------------------------
        # Competition
        # -----------------------------
        self.enable_competition = True
        self.competition_regions = {"striatum"}
        self.competition_kernel = CompetitionKernel(
            inhibition_strength=0.35,
            persistence_gain=0.4,
            dominance_tau=0.25,
        )

        # -----------------------------
        # BG disinhibition (GAIN ONLY)
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

        self._build(brain)

        print("[DEBUG] Runtime initialized")
        print(f"[DEBUG] Regions built: {len(self.region_states)}")
        print(f"[DEBUG] Assemblies built: {len(self._all_pops)}")

    # ============================================================
    # Assembly control
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
    # Region resolution
    # ============================================================

    def _build_region_id_map(self, regions: Dict[str, Any]) -> None:
        self._region_key_by_label.clear()
        for rk, rdef in regions.items():
            self._region_key_by_label[_norm(rk)] = rk
            if isinstance(rdef, dict) and rdef.get("region_id"):
                self._region_key_by_label[_norm(rdef["region_id"])] = rk

    def _resolve_region_key(self, label: str) -> Optional[str]:
        return self._region_key_by_label.get(_norm(label))

    # ============================================================
    # Build populations
    # ============================================================

    def _build(self, brain: Dict[str, Any]) -> None:
        regions = brain.get("regions", {}) or {}
        self._build_region_id_map(regions)

        for region_key, region_def in regions.items():
            state = {"def": region_def, "populations": {}}
            self.region_states[region_key] = state

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

                state["populations"][pop_id] = plist

    # ============================================================
    # Stimulus handling
    # ============================================================

    def _reset_inputs(self) -> None:
        for p in self._all_pops:
            p.input = 0.0

    def inject_stimulus(
        self,
        region_id: str,
        population_id: Optional[str] = None,
        assembly_index: Optional[int] = None,
        magnitude: float = 1.0,
    ) -> None:
        rid = self._resolve_region_key(region_id) or region_id
        self._stim_queue.append((rid, population_id, assembly_index, magnitude))

    def _apply_stimuli(self) -> None:
        for region_key, pop_id, idx, mag in self._stim_queue:
            pops = self.region_states.get(region_key, {}).get("populations", {})
            targets = pops.values() if pop_id is None else [pops.get(pop_id, [])]
            for plist in targets:
                for p in plist if idx is None else plist[idx:idx + 1]:
                    p.input += mag
        self._stim_queue.clear()

    # ============================================================
    # Step
    # ============================================================

    def step(self) -> None:
        self.step_count += 1

        # Phase 1: inputs
        self._reset_inputs()
        self._apply_stimuli()

        # Phase 2: physiology
        for pop in self._all_pops:
            pop.step(self.dt)

        # Phase 3: striatal competition
        if self.enable_competition:
            striatum = self.region_states.get("striatum")
            if striatum:
                assemblies = [
                    p
                    for plist in striatum["populations"].values()
                    for p in plist
                ]
                if assemblies:
                    self.competition_kernel.apply(assemblies, self.dt)

        # Phase 4: BG disinhibition (routing gain only)
        relief = 1.0
        if self.enable_gpi_disinhibition:
            gpi = self.region_states.get("gpi")
            if gpi:
                gpi_activity = sum(
                    p.output()
                    for plist in gpi["populations"].values()
                    for p in plist
                )
                relief = max(self.gpi_floor, 1.0 - self.gpi_gain * gpi_activity)

        # Phase 5: cortex → thalamus (ZERO-MEAN)
        cortex = self.region_states.get("association_cortex")
        if cortex:
            src = [
                p
                for plist in cortex["populations"].values()
                for p in plist
            ]
            if src:
                mean = sum(p.output() for p in src) / len(src)
                variance = [(p.output() - mean) for p in src]
                drive = sum(variance) / max(len(variance), 1)

                for relay in ("lgn", "md", "pulvinar", "vpl", "vpm"):
                    th = self.region_states.get(relay)
                    if not th:
                        continue
                    for plist in th["populations"].values():
                        for p in plist:
                            p.input += drive * 0.02 * relief

        self.time += self.dt
