# engine/runtime.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from engine.population_model import PopulationModel


def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge dict b into dict a recursively (returns new dict).
    """
    out = dict(a or {})
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class BrainRuntime:
    """
    Runtime engine:
    - Builds PopulationModel assemblies from the compiled brain dict
    - Supports one-step queueable external stimuli (poke)
    - Propagates region-to-region using mean signed firing output
    - Steps all assemblies forward each dt
    """

    def __init__(self, brain: Dict[str, Any], dt: float = 0.01):
        self.brain = brain
        self.dt = float(dt)
        self.time = 0.0

        # Optional global dynamics
        self.global_dyn: Dict[str, Any] = (
            brain.get("global_dynamics")
            or brain.get("dynamics")
            or {}
        )

        # region_states[region_id] = {"def": region_def, "populations": {pop_id: [PopulationModel,...]}}
        self.region_states: Dict[str, Dict[str, Any]] = {}

        # Fast list of all assemblies for stepping/resetting
        self._all_pops: List[PopulationModel] = []

        # Queue stimuli so resets don't wipe them
        # Each item: (region_id, population_id, assembly_index, magnitude)
        self._stim_queue: List[Tuple[str, Optional[str], Optional[int], float]] = []

        self._build(brain)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self, brain: Dict[str, Any]) -> None:
        regions = brain.get("regions", {}) or {}

        for region_id, region_def in regions.items():
            region_state = {"def": region_def, "populations": {}}
            self.region_states[region_id] = region_state

            region_dyn = region_def.get("dynamics", {}) or {}

            populations = region_def.get("populations", {}) or {}
            # populations could be:
            # - {pop_id: [assembly_def, ...]}
            # - {pop_id: {"dynamics": {...}, "assemblies": [ ... ]}}
            for pop_id, pop_blob in populations.items():
                pop_dyn: Dict[str, Any] = {}
                assembly_defs: List[Dict[str, Any]] = []

                if isinstance(pop_blob, dict):
                    pop_dyn = pop_blob.get("dynamics", {}) or {}
                    assembly_defs = pop_blob.get("assemblies", []) or []
                    # if dict but user stored list under other key
                    if not assembly_defs and "assembly_defs" in pop_blob:
                        assembly_defs = pop_blob.get("assembly_defs") or []
                elif isinstance(pop_blob, list):
                    assembly_defs = pop_blob
                else:
                    # Unknown schema: skip
                    assembly_defs = []

                built: List[PopulationModel] = []
                for idx, adef in enumerate(assembly_defs):
                    adef = adef or {}
                    assembly_dyn = adef.get("dynamics", {}) if isinstance(adef, dict) else {}

                    merged = _deep_merge(self.global_dyn, region_dyn)
                    merged = _deep_merge(merged, pop_dyn)
                    merged = _deep_merge(merged, assembly_dyn)

                    default_aid = f"{region_id}:{pop_id}:{idx}"
                    # Allow assembly_id at top-level of adef
                    if isinstance(adef, dict) and adef.get("assembly_id"):
                        merged["assembly_id"] = adef["assembly_id"]
                    if isinstance(adef, dict) and adef.get("size") is not None:
                        merged["size"] = adef["size"]
                    if isinstance(adef, dict) and adef.get("sign") is not None:
                        merged["sign"] = adef["sign"]

                    pop = PopulationModel.from_params(merged, default_assembly_id=default_aid)

                    built.append(pop)
                    self._all_pops.append(pop)

                region_state["populations"][pop_id] = built

    # ------------------------------------------------------------------
    # External Stimulus
    # ------------------------------------------------------------------

    def inject_stimulus(
        self,
        region_id: str,
        population_id: Optional[str] = None,
        assembly_index: Optional[int] = None,
        magnitude: float = 1.0,
    ) -> None:
        """
        Queue a stimulus to be applied on the NEXT step after inputs are reset.
        This prevents 'poke' from getting wiped by input resets.
        """
        self._stim_queue.append((region_id, population_id, assembly_index, float(magnitude)))

    def _apply_stimuli(self) -> None:
        if not self._stim_queue:
            return

        for region_id, population_id, assembly_index, mag in self._stim_queue:
            if region_id not in self.region_states:
                continue

            region = self.region_states[region_id]
            pops_by_pop = region["populations"]

            if population_id is None:
                # All populations in region
                for plist in pops_by_pop.values():
                    if assembly_index is None:
                        for pop in plist:
                            pop.input += mag
                    else:
                        if 0 <= assembly_index < len(plist):
                            plist[assembly_index].input += mag
                continue

            # Specific population in region
            if population_id not in pops_by_pop:
                continue

            plist = pops_by_pop[population_id]
            if assembly_index is None:
                for pop in plist:
                    pop.input += mag
            else:
                if 0 <= assembly_index < len(plist):
                    plist[assembly_index].input += mag

        self._stim_queue.clear()

    # ------------------------------------------------------------------
    # Step / propagation
    # ------------------------------------------------------------------

    def _reset_inputs(self) -> None:
        # PopulationModel consumes input inside pop.step(), but we reset anyway for safety
        for pop in self._all_pops:
            pop.input = 0.0

    def _region_mean_output(self, region_id: str) -> float:
        region = self.region_states[region_id]
        total = 0.0
        n = 0

        for plist in region["populations"].values():
            for pop in plist:
                total += pop.output()
                n += 1

        return (total / n) if n else 0.0

    def _propagate_activity(self) -> None:
        """
        Region-to-region propagation using MEAN signed firing output.
        Supports two output formats:
          outputs = {target_region: weight}
          outputs = {target_region: {target_population_id: weight, ...}}
        """
        regions = self.brain.get("regions", {}) or {}

        # Precompute mean outputs from current state (previous step's firing)
        mean_out: Dict[str, float] = {}
        for rid in self.region_states.keys():
            mean_out[rid] = self._region_mean_output(rid)

        for src_id, src_def in regions.items():
            if src_id not in mean_out:
                continue

            src_signal = mean_out[src_id]
            outputs = src_def.get("outputs", {}) or {}

            if not outputs or src_signal == 0.0:
                continue

            # outputs can be dict; anything else: ignore
            if not isinstance(outputs, dict):
                continue

            for tgt_id, w in outputs.items():
                if tgt_id not in self.region_states:
                    continue

                tgt_region = self.region_states[tgt_id]
                pops_by_pop = tgt_region["populations"]

                # Case A: numeric weight
                if isinstance(w, (int, float)):
                    delta = float(w) * src_signal
                    for plist in pops_by_pop.values():
                        for pop in plist:
                            pop.input += delta
                    continue

                # Case B: per-population weights
                if isinstance(w, dict):
                    for tgt_pop_id, pw in w.items():
                        if tgt_pop_id not in pops_by_pop:
                            continue
                        if not isinstance(pw, (int, float)):
                            continue
                        delta = float(pw) * src_signal
                        for pop in pops_by_pop[tgt_pop_id]:
                            pop.input += delta

    def step(self) -> None:
        """
        Advance simulation by one timestep.
        Order:
          1) reset inputs
          2) apply queued stimuli (poke)
          3) propagate region->region based on current firing rates
          4) step all assemblies (consumes input)
          5) advance time
        """
        self._reset_inputs()
        self._apply_stimuli()
        self._propagate_activity()

        for pop in self._all_pops:
            pop.step(self.dt)

        self.time += self.dt
