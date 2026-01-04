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


def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _as_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return int(default)


class BrainRuntime:
    """
    Runtime engine:
    - Builds PopulationModel assemblies from the compiled brain dict
    - Supports one-step queueable external stimuli (poke)
    - Propagates population-to-population (preferred), with region-level fallback
    - Steps all assemblies forward each dt
    """

    def __init__(self, brain: Dict[str, Any], dt: float = 0.01):
        self.brain = brain
        self.dt = float(dt)
        self.time = 0.0

        gd: Dict[str, Any] = brain.get("global_dynamics") or brain.get("dynamics") or {}

        self.global_pop_dyn: Dict[str, Any] = (
            gd.get("population_defaults", {}) if isinstance(gd, dict) else {}
        )
        if not self.global_pop_dyn and isinstance(gd, dict):
            self.global_pop_dyn = dict(gd)

        self.global_noise: Dict[str, Any] = (
            gd.get("background_noise", {}) or {} if isinstance(gd, dict) else {}
        )
        self.global_prop: Dict[str, Any] = (
            gd.get("propagation", {}) or {} if isinstance(gd, dict) else {}
        )

        self.baseline_activity_scale: float = (
            _as_float(gd.get("baseline_activity_scale", 0.0), 0.0) if isinstance(gd, dict) else 0.0
        )

        runtime_cfg = brain.get("runtime", {}) or {}

        self.neurons_per_assembly: int = _as_int(
            runtime_cfg.get("neurons_per_assembly") or gd.get("neurons_per_assembly") or 500,
            500,
        )

        self.assembly_downscale_factor: float = _as_float(
            runtime_cfg.get("assembly_downscale_factor")
            or runtime_cfg.get("downscale_factor")
            or 1.0,
            1.0,
        )
        if self.assembly_downscale_factor <= 0.0:
            self.assembly_downscale_factor = 1.0

        self.max_assemblies_per_population: int = _as_int(
            runtime_cfg.get("max_assemblies_per_population")
            or runtime_cfg.get("max_assemblies_per_pop")
            or 0,
            0,
        )

        self.region_states: Dict[str, Dict[str, Any]] = {}
        self._all_pops: List[PopulationModel] = []

        self._stim_queue: List[Tuple[str, Optional[str], Optional[int], float]] = []

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

        if "noise_amplitude" not in merged:
            merged["noise_amplitude"] = _as_float(
                self.global_noise.get("amplitude", 0.0) if isinstance(self.global_noise, dict) else 0.0,
                0.0,
            )

        if "noise_distribution" not in merged:
            merged["noise_distribution"] = str(
                self.global_noise.get("distribution", "gaussian")
                if isinstance(self.global_noise, dict)
                else "gaussian"
            ).lower()

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

        if pop_blob.get("sign") is not None:
            pop_dyn["sign"] = pop_blob["sign"]
        else:
            nt = _norm(pop_blob.get("neuron_type"))
            if nt == "inhibitory":
                pop_dyn["sign"] = -1.0
            elif nt == "excitatory":
                pop_dyn["sign"] = 1.0

        if pop_blob.get("baseline") is not None:
            pop_dyn["baseline"] = pop_blob["baseline"]
        else:
            fr_hz = pop_blob.get("baseline_firing_rate_hz")
            if fr_hz is not None:
                thr = _as_float(base_dyn.get("threshold", 0.5), 0.5)
                gain = _as_float(base_dyn.get("gain", 1.0), 1.0) or 1.0
                fr = _as_float(fr_hz, 0.0)
                pop_dyn["baseline"] = thr + (fr / gain)

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
            "activity_ceiling",
        ):
            if pop_blob.get(k) is not None:
                pop_dyn[k] = pop_blob[k]

        return pop_dyn

    def _apply_downscale_and_cap(self, n: int) -> int:
        n2 = int(max(0, round(n * self.assembly_downscale_factor)))
        if n2 < 1 and n > 0:
            n2 = 1
        if self.max_assemblies_per_population and n2 > self.max_assemblies_per_population:
            n2 = self.max_assemblies_per_population
        return n2

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self, brain: Dict[str, Any]) -> None:
        regions = brain.get("regions", {}) or {}
        self._build_region_id_map(regions)

        for region_key, region_def in regions.items():
            region_state = {"def": region_def, "populations": {}}
            self.region_states[region_key] = region_state

            region_dyn: Dict[str, Any] = {}
            if isinstance(region_def, dict):
                region_dyn = region_def.get("dynamics", {}) or {}

            populations = {}
            if isinstance(region_def, dict):
                populations = region_def.get("populations", {}) or {}

            for pop_id, pop_blob in populations.items():
                built: List[PopulationModel] = []

                # Explicit assembly list
                if isinstance(pop_blob, list):
                    base = self._merged_base_dyn(region_dyn=region_dyn, pop_dyn={})
                    for idx, adef in enumerate(pop_blob):
                        adef = adef or {}
                        assembly_dyn = adef.get("dynamics", {}) if isinstance(adef, dict) else {}
                        merged = _deep_merge(base, assembly_dyn)

                        default_aid = f"{region_key}:{pop_id}:{idx}"
                        if isinstance(adef, dict):
                            if adef.get("assembly_id"):
                                merged["assembly_id"] = adef["assembly_id"]
                            if adef.get("size") is not None:
                                merged["size"] = adef["size"]
                            if adef.get("sign") is not None:
                                merged["sign"] = adef["sign"]

                        pop = PopulationModel.from_params(merged, default_assembly_id=default_aid)
                        built.append(pop)
                        self._all_pops.append(pop)

                    region_state["populations"][pop_id] = built
                    continue

                # Dict schema
                if isinstance(pop_blob, dict):
                    pop_dyn = pop_blob.get("dynamics", {}) or {}
                    assembly_defs = pop_blob.get("assemblies", []) or pop_blob.get("assembly_defs", []) or []

                    if assembly_defs:
                        base = self._merged_base_dyn(region_dyn=region_dyn, pop_dyn=pop_dyn)
                        for idx, adef in enumerate(assembly_defs):
                            adef = adef or {}
                            assembly_dyn = adef.get("dynamics", {}) if isinstance(adef, dict) else {}
                            merged = _deep_merge(base, assembly_dyn)

                            default_aid = f"{region_key}:{pop_id}:{idx}"
                            if isinstance(adef, dict):
                                if adef.get("assembly_id"):
                                    merged["assembly_id"] = adef["assembly_id"]
                                if adef.get("size") is not None:
                                    merged["size"] = adef["size"]
                                if adef.get("sign") is not None:
                                    merged["sign"] = adef["sign"]

                            pop = PopulationModel.from_params(merged, default_assembly_id=default_aid)
                            built.append(pop)
                            self._all_pops.append(pop)

                        region_state["populations"][pop_id] = built
                        continue

                    # TEMPLATE schema
                    if "count" in pop_blob:
                        count = _as_int(pop_blob.get("count") or 0, 0)

                        base = self._merged_base_dyn(region_dyn=region_dyn, pop_dyn={})
                        pop_dyn2 = self._template_pop_dyn(pop_blob, base_dyn=base)
                        base2 = self._merged_base_dyn(region_dyn=region_dyn, pop_dyn=pop_dyn2)

                        n_assemblies = 0
                        if count > 0 and self.neurons_per_assembly > 0:
                            n_assemblies = max(1, int(round(count / float(self.neurons_per_assembly))))
                            n_assemblies = self._apply_downscale_and_cap(n_assemblies)

                        for idx in range(n_assemblies):
                            merged = dict(base2)
                            merged.setdefault("size", self.neurons_per_assembly)
                            default_aid = f"{region_key}:{pop_id}:{idx}"
                            pop = PopulationModel.from_params(merged, default_assembly_id=default_aid)
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
        self._stim_queue.append((rid, population_id, assembly_index, float(magnitude)))

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
    # Propagation (population-aware)
    # ------------------------------------------------------------------

    def _reset_inputs(self) -> None:
        for pop in self._all_pops:
            pop.input = 0.0

    def _region_population_mean_output(self, region_key: str) -> Dict[str, float]:
        """
        Returns mean signed firing output per population_id.
        """
        out: Dict[str, float] = {}
        pops_by_pop = self.region_states[region_key]["populations"]
        for pop_id, plist in pops_by_pop.items():
            if not plist:
                continue
            total = 0.0
            for p in plist:
                total += p.output()
            out[pop_id] = total / float(len(plist))
        return out

    def _region_mean_output_excitatory_only(self, region_key: str) -> float:
        """
        Fallback region output: mean output across assemblies with sign > 0.
        This prevents inhibitory populations from collapsing the entire region signal.
        """
        total = 0.0
        n = 0
        for plist in self.region_states[region_key]["populations"].values():
            for pop in plist:
                if pop.sign > 0:
                    total += pop.output()
                    n += 1
        return (total / n) if n else 0.0

    def _global_strength(self) -> float:
        return _as_float(self.global_prop.get("global_strength", 1.0), 1.0) if isinstance(self.global_prop, dict) else 1.0

    def _propagate_activity(self) -> None:
        regions = self.brain.get("regions", {}) or {}
        g = self._global_strength()

        # Precompute source signals per region and population
        src_pop_signal: Dict[str, Dict[str, float]] = {}
        src_region_fallback: Dict[str, float] = {}

        for rk in self.region_states.keys():
            src_pop_signal[rk] = self._region_population_mean_output(rk)
            src_region_fallback[rk] = self._region_mean_output_excitatory_only(rk)

        for src_key, src_def in regions.items():
            if src_key not in self.region_states:
                continue
            if not isinstance(src_def, dict):
                continue

            outputs = src_def.get("outputs")
            if not outputs:
                continue

            # If the region defines inputs/outputs as list edges, we support both:
            # - population-specific edges (source_population / target_population)
            # - region-level edges (no populations specified)
            #
            # If outputs is a dict, we preserve legacy behavior but use excitatory-only fallback.

            # -------------------------
            # Dict outputs (legacy)
            # -------------------------
            if isinstance(outputs, dict):
                src_signal = src_region_fallback.get(src_key, 0.0)
                if src_signal == 0.0:
                    continue

                for tgt_label, w in outputs.items():
                    tgt_key = self._resolve_region_key(tgt_label) or (tgt_label if tgt_label in self.region_states else None)
                    if not tgt_key:
                        continue

                    pops_by_pop = self.region_states[tgt_key]["populations"]

                    if isinstance(w, (int, float)):
                        delta = float(w) * src_signal * g
                        for plist in pops_by_pop.values():
                            for pop in plist:
                                pop.input += delta
                    elif isinstance(w, dict):
                        for tgt_pop, pw in w.items():
                            if tgt_pop not in pops_by_pop:
                                continue
                            if not isinstance(pw, (int, float)):
                                continue
                            delta = float(pw) * src_signal * g
                            for pop in pops_by_pop[tgt_pop]:
                                pop.input += delta
                continue

            # -------------------------
            # List outputs (preferred)
            # -------------------------
            if isinstance(outputs, list):
                for edge in outputs:
                    if not isinstance(edge, dict):
                        continue

                    tgt_label = edge.get("target_region") or edge.get("target") or edge.get("to")
                    tgt_key = self._resolve_region_key(tgt_label) or (tgt_label if tgt_label in self.region_states else None)
                    if not tgt_key:
                        continue

                    strength = edge.get("strength", edge.get("weight"))
                    if not isinstance(strength, (int, float)):
                        continue

                    tgt_pop = edge.get("target_population") or edge.get("population") or edge.get("to_population")
                    src_pop = edge.get("source_population") or edge.get("from_population") or edge.get("population_from")

                    # Choose the source signal:
                    if src_pop:
                        src_signal = src_pop_signal.get(src_key, {}).get(str(src_pop), 0.0)
                    else:
                        src_signal = src_region_fallback.get(src_key, 0.0)

                    if src_signal == 0.0:
                        continue

                    delta = float(strength) * src_signal * g
                    pops_by_pop = self.region_states[tgt_key]["populations"]

                    if tgt_pop and tgt_pop in pops_by_pop:
                        for pop in pops_by_pop[tgt_pop]:
                            pop.input += delta
                    else:
                        for plist in pops_by_pop.values():
                            for pop in plist:
                                pop.input += delta

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def step(self) -> None:
        self._reset_inputs()
        self._apply_stimuli()
        self._propagate_activity()

        for pop in self._all_pops:
            pop.step(self.dt)

        self.time += self.dt
