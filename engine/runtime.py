# engine/runtime.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from engine.population_model import PopulationModel


def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Merge dict b into dict a recursively (returns new dict)."""
    out = dict(a or {})
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


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

        # Global dynamics (prefer modern schema)
        gd: Dict[str, Any] = (
            brain.get("global_dynamics")
            or brain.get("dynamics")
            or {}
        )

        # Population defaults live under "population_defaults"
        self.global_pop_dyn: Dict[str, Any] = (
            gd.get("population_defaults", {}) if isinstance(gd, dict) else {}
        )
        if not self.global_pop_dyn and isinstance(gd, dict):
            # Back-compat: treat root dict as population defaults
            self.global_pop_dyn = dict(gd)

        self.global_noise: Dict[str, Any] = (
            gd.get("background_noise", {}) or {}
            if isinstance(gd, dict)
            else {}
        )
        self.global_prop: Dict[str, Any] = (
            gd.get("propagation", {}) or {}
            if isinstance(gd, dict)
            else {}
        )

        # Optional helper scalar (legacy)
        self.baseline_activity_scale: float = (
            float(gd.get("baseline_activity_scale", 0.0) or 0.0)
            if isinstance(gd, dict)
            else 0.0
        )

        # Default neurons-per-assembly (historical behavior)
        runtime_cfg = brain.get("runtime", {}) or {}
        self.neurons_per_assembly: int = int(
            runtime_cfg.get("neurons_per_assembly")
            or gd.get("neurons_per_assembly")
            or 500
        )

        # region_states[region_key] = {
        #   "def": region_def,
        #   "populations": {pop_id: [PopulationModel, ...]}
        # }
        self.region_states: Dict[str, Dict[str, Any]] = {}

        # Flat list of all assemblies
        self._all_pops: List[PopulationModel] = []

        # Stimulus queue
        self._stim_queue: List[
            Tuple[str, Optional[str], Optional[int], float]
        ] = []

        # Region label resolution
        self._region_key_by_label: Dict[str, str] = {}

        self._build(brain)

    # ------------------------------------------------------------------
    # Region ID resolution
    # ------------------------------------------------------------------

    def _build_region_id_map(self, regions: Dict[str, Any]) -> None:
        self._region_key_by_label.clear()
        for region_key, region_def in (regions or {}).items():
            self._region_key_by_label[_norm(region_key)] = region_key

            if isinstance(region_def, dict):
                rid = region_def.get("region_id")
                name = region_def.get("name")
                if rid:
                    self._region_key_by_label[_norm(rid)] = region_key
                if name:
                    self._region_key_by_label[_norm(name)] = region_key

    def _resolve_region_key(self, label: str) -> Optional[str]:
        if not label:
            return None
        return self._region_key_by_label.get(_norm(label))

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------

    def _merged_base_dyn(
        self,
        *,
        region_dyn: Dict[str, Any],
        pop_dyn: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = _deep_merge(self.global_pop_dyn, region_dyn or {})
        merged = _deep_merge(merged, pop_dyn or {})

        # Global noise defaults
        if "noise_amplitude" not in merged:
            merged["noise_amplitude"] = float(
                self.global_noise.get("amplitude", 0.0)
                if isinstance(self.global_noise, dict)
                else 0.0
            )

        if "noise_distribution" not in merged:
            merged["noise_distribution"] = str(
                self.global_noise.get("distribution", "gaussian")
                if isinstance(self.global_noise, dict)
                else "gaussian"
            )

        # Activity floor / ceiling mapping
        if "clamp_min" not in merged and "activity_floor" in merged:
            merged["clamp_min"] = merged.get("activity_floor")

        if "clamp_max" not in merged and "activity_ceiling" in merged:
            merged["clamp_max"] = merged.get("activity_ceiling")

        return merged

    def _template_pop_dyn(
        self,
        pop_blob: Dict[str, Any],
        *,
        base_dyn: Dict[str, Any],
    ) -> Dict[str, Any]:
        pop_dyn: Dict[str, Any] = {}

        # Sign
        if pop_blob.get("sign") is not None:
            pop_dyn["sign"] = pop_blob["sign"]
        else:
            nt = _norm(pop_blob.get("neuron_type"))
            if nt == "inhibitory":
                pop_dyn["sign"] = -1.0
            elif nt == "excitatory":
                pop_dyn["sign"] = 1.0

        # Baseline from firing-rate hint
        if pop_blob.get("baseline") is not None:
            pop_dyn["baseline"] = pop_blob["baseline"]
        else:
            fr_hz = pop_blob.get("baseline_firing_rate_hz")
            if fr_hz is not None:
                thr = float(base_dyn.get("threshold", 0.5))
                gain = float(base_dyn.get("gain", 1.0)) or 1.0
                try:
                    fr = float(fr_hz)
                except Exception:
                    fr = 0.0
                pop_dyn["baseline"] = thr + (fr / gain)

        # Direct overrides
        for k in (
            "tau",
            "threshold",
            "gain",
            "max_rate",
            "noise_amplitude",
            "noise_distribution",
            "clamp_min",
            "clamp_max",
            "activity_floor",
            "tonic_drive",
        ):
            if pop_blob.get(k) is not None:
                pop_dyn[k] = pop_blob[k]

        return pop_dyn

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self, brain: Dict[str, Any]) -> None:
        regions = brain.get("regions", {}) or {}
        self._build_region_id_map(regions)

        for region_key, region_def in regions.items():
            region_state = {"def": region_def, "populations": {}}
            self.region_states[region_key] = region_state

            region_dyn = {}
            if isinstance(region_def, dict):
                region_dyn = region_def.get("dynamics", {}) or {}

            populations = {}
            if isinstance(region_def, dict):
                populations = region_def.get("populations", {}) or {}

            for pop_id, pop_blob in populations.items():
                built: List[PopulationModel] = []

                # -----------------------------
                # Explicit assembly list
                # -----------------------------
                if isinstance(pop_blob, list):
                    base = self._merged_base_dyn(
                        region_dyn=region_dyn,
                        pop_dyn={},
                    )

                    for idx, adef in enumerate(pop_blob):
                        adef = adef or {}
                        assembly_dyn = (
                            adef.get("dynamics", {})
                            if isinstance(adef, dict)
                            else {}
                        )
                        merged = _deep_merge(base, assembly_dyn)

                        default_aid = f"{region_key}:{pop_id}:{idx}"

                        if isinstance(adef, dict):
                            if adef.get("assembly_id"):
                                merged["assembly_id"] = adef["assembly_id"]
                            if adef.get("size") is not None:
                                merged["size"] = adef["size"]
                            if adef.get("sign") is not None:
                                merged["sign"] = adef["sign"]

                        pop = PopulationModel.from_params(
                            merged,
                            default_assembly_id=default_aid,
                        )
                        built.append(pop)
                        self._all_pops.append(pop)

                    region_state["populations"][pop_id] = built
                    continue

                # -----------------------------
                # Dict schema
                # -----------------------------
                if isinstance(pop_blob, dict):
                    pop_dyn = pop_blob.get("dynamics", {}) or {}
                    assembly_defs = (
                        pop_blob.get("assemblies", [])
                        or pop_blob.get("assembly_defs", [])
                        or []
                    )

                    # Explicit assemblies
                    if assembly_defs:
                        base = self._merged_base_dyn(
                            region_dyn=region_dyn,
                            pop_dyn=pop_dyn,
                        )

                        for idx, adef in enumerate(assembly_defs):
                            adef = adef or {}
                            assembly_dyn = (
                                adef.get("dynamics", {})
                                if isinstance(adef, dict)
                                else {}
                            )
                            merged = _deep_merge(base, assembly_dyn)

                            default_aid = f"{region_key}:{pop_id}:{idx}"

                            if isinstance(adef, dict):
                                if adef.get("assembly_id"):
                                    merged["assembly_id"] = adef["assembly_id"]
                                if adef.get("size") is not None:
                                    merged["size"] = adef["size"]
                                if adef.get("sign") is not None:
                                    merged["sign"] = adef["sign"]

                            pop = PopulationModel.from_params(
                                merged,
                                default_assembly_id=default_aid,
                            )
                            built.append(pop)
                            self._all_pops.append(pop)

                        region_state["populations"][pop_id] = built
                        continue

                    # TEMPLATE schema
                    if "count" in pop_blob:
                        try:
                            count = int(pop_blob.get("count") or 0)
                        except Exception:
                            count = 0

                        base = self._merged_base_dyn(
                            region_dyn=region_dyn,
                            pop_dyn={},
                        )
                        pop_dyn2 = self._template_pop_dyn(
                            pop_blob,
                            base_dyn=base,
                        )
                        base2 = self._merged_base_dyn(
                            region_dyn=region_dyn,
                            pop_dyn=pop_dyn2,
                        )

                        if count > 0 and self.neurons_per_assembly > 0:
                            n_assemblies = max(
                                1,
                                int(round(count / float(self.neurons_per_assembly))),
                            )
                        else:
                            n_assemblies = 0

                        for idx in range(n_assemblies):
                            merged = dict(base2)
                            merged.setdefault("size", self.neurons_per_assembly)

                            default_aid = f"{region_key}:{pop_id}:{idx}"
                            pop = PopulationModel.from_params(
                                merged,
                                default_assembly_id=default_aid,
                            )
                            built.append(pop)
                            self._all_pops.append(pop)

                        region_state["populations"][pop_id] = built
                        continue

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
        rid = self._resolve_region_key(region_id) or region_id
        self._stim_queue.append(
            (rid, population_id, assembly_index, float(magnitude))
        )

    def _apply_stimuli(self) -> None:
        if not self._stim_queue:
            return

        for region_key, population_id, assembly_index, mag in self._stim_queue:
            if region_key not in self.region_states:
                continue

            pops_by_pop = self.region_states[region_key]["populations"]

            if population_id is None:
                for plist in pops_by_pop.values():
                    if assembly_index is None:
                        for pop in plist:
                            pop.input += mag
                    elif 0 <= assembly_index < len(plist):
                        plist[assembly_index].input += mag
                continue

            if population_id not in pops_by_pop:
                continue

            plist = pops_by_pop[population_id]
            if assembly_index is None:
                for pop in plist:
                    pop.input += mag
            elif 0 <= assembly_index < len(plist):
                plist[assembly_index].input += mag

        self._stim_queue.clear()

    # ------------------------------------------------------------------
    # Step / propagation
    # ------------------------------------------------------------------

    def _reset_inputs(self) -> None:
        for pop in self._all_pops:
            pop.input = 0.0

    def _region_mean_output(self, region_key: str) -> float:
        total = 0.0
        n = 0
        for plist in self.region_states[region_key]["populations"].values():
            for pop in plist:
                total += pop.output()
                n += 1
        return (total / n) if n else 0.0

    def _propagate_activity(self) -> None:
        regions = self.brain.get("regions", {}) or {}
        global_strength = (
            float(self.global_prop.get("global_strength", 1.0))
            if isinstance(self.global_prop, dict)
            else 1.0
        )

        mean_out = {
            rk: self._region_mean_output(rk)
            for rk in self.region_states.keys()
        }

        for src_key, src_def in regions.items():
            if src_key not in mean_out:
                continue

            src_signal = mean_out[src_key]
            if src_signal == 0.0:
                continue

            outputs = src_def.get("outputs") if isinstance(src_def, dict) else None
            if not outputs:
                continue

            # Dict outputs
            if isinstance(outputs, dict):
                for tgt_label, w in outputs.items():
                    tgt_key = (
                        self._resolve_region_key(tgt_label)
                        or (tgt_label if tgt_label in self.region_states else None)
                    )
                    if not tgt_key:
                        continue

                    pops_by_pop = self.region_states[tgt_key]["populations"]

                    if isinstance(w, (int, float)):
                        delta = float(w) * src_signal * global_strength
                        for plist in pops_by_pop.values():
                            for pop in plist:
                                pop.input += delta
                    elif isinstance(w, dict):
                        for tgt_pop, pw in w.items():
                            if tgt_pop not in pops_by_pop:
                                continue
                            if not isinstance(pw, (int, float)):
                                continue
                            delta = float(pw) * src_signal * global_strength
                            for pop in pops_by_pop[tgt_pop]:
                                pop.input += delta
                continue

            # List outputs
            if isinstance(outputs, list):
                for edge in outputs:
                    if not isinstance(edge, dict):
                        continue

                    tgt_label = (
                        edge.get("target_region")
                        or edge.get("target")
                        or edge.get("to")
                    )
                    tgt_key = (
                        self._resolve_region_key(tgt_label)
                        or (tgt_label if tgt_label in self.region_states else None)
                    )
                    if not tgt_key:
                        continue

                    strength = edge.get("strength", edge.get("weight"))
                    if not isinstance(strength, (int, float)):
                        continue

                    delta = float(strength) * src_signal * global_strength
                    tgt_pop = (
                        edge.get("target_population")
                        or edge.get("population")
                        or edge.get("to_population")
                    )

                    pops_by_pop = self.region_states[tgt_key]["populations"]

                    if tgt_pop and tgt_pop in pops_by_pop:
                        for pop in pops_by_pop[tgt_pop]:
                            pop.input += delta
                    else:
                        for plist in pops_by_pop.values():
                            for pop in plist:
                                pop.input += delta

    def step(self) -> None:
        self._reset_inputs()
        self._apply_stimuli()
        self._propagate_activity()

        for pop in self._all_pops:
            pop.step(self.dt)

        self.time += self.dt
