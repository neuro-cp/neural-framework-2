from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from engine.population_model import PopulationModel


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a or {})
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _norm(x: Any) -> str:
    return str(x or "").strip().lower()


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


# ------------------------------------------------------------
# BrainRuntime
# ------------------------------------------------------------

class BrainRuntime:
    """
    Stable mass-based runtime.

    Guarantees:
    - Assemblies persist at tonic baseline
    - Region outputs propagate even at low firing
    - Supports dict and list output schemas
    """

    def __init__(self, brain: Dict[str, Any], dt: float = 0.01):
        self.brain = brain
        self.dt = float(dt)
        self.time = 0.0

        gd = brain.get("global_dynamics") or brain.get("dynamics") or {}

        self.global_pop_dyn = gd.get("population_defaults", {}) if isinstance(gd, dict) else {}
        self.global_noise = gd.get("background_noise", {}) if isinstance(gd, dict) else {}
        self.global_prop = gd.get("propagation", {}) if isinstance(gd, dict) else {}

        self.baseline_activity_scale = _as_float(
            gd.get("baseline_activity_scale", 0.0), 0.0
        )

        runtime_cfg = brain.get("runtime", {}) or {}

        self.neurons_per_assembly = _as_int(
            runtime_cfg.get("neurons_per_assembly", 500), 500
        )

        self.assembly_downscale_factor = _as_float(
            runtime_cfg.get("assembly_downscale_factor", 1.0), 1.0
        )
        if self.assembly_downscale_factor <= 0:
            self.assembly_downscale_factor = 1.0

        self.max_assemblies_per_population = _as_int(
            runtime_cfg.get("max_assemblies_per_population", 0), 0
        )

        self.region_states: Dict[str, Dict[str, Any]] = {}
        self._all_pops: List[PopulationModel] = []

        self._stim_queue: List[Tuple[str, Optional[str], Optional[int], float]] = []
        self._region_key_by_label: Dict[str, str] = {}

        self._build(brain)

    # ------------------------------------------------------------
    # Region resolution
    # ------------------------------------------------------------

    def _build_region_id_map(self, regions: Dict[str, Any]) -> None:
        self._region_key_by_label.clear()
        for rk, rdef in regions.items():
            self._region_key_by_label[_norm(rk)] = rk
            if isinstance(rdef, dict):
                for k in ("region_id", "name"):
                    if rdef.get(k):
                        self._region_key_by_label[_norm(rdef[k])] = rk

    def _resolve_region_key(self, label: str) -> Optional[str]:
        return self._region_key_by_label.get(_norm(label)) if label else None

    # ------------------------------------------------------------
    # Build
    # ------------------------------------------------------------

    def _apply_downscale(self, n: int) -> int:
        n2 = int(round(n * self.assembly_downscale_factor)) if n > 0 else 0
        if n2 < 1 and n > 0:
            n2 = 1
        if self.max_assemblies_per_population:
            n2 = min(n2, self.max_assemblies_per_population)
        return n2

    def _build(self, brain: Dict[str, Any]) -> None:
        regions = brain.get("regions", {}) or {}
        self._build_region_id_map(regions)

        for region_key, region_def in regions.items():
            region_state = {"def": region_def, "populations": {}}
            self.region_states[region_key] = region_state

            region_dyn = region_def.get("dynamics", {}) if isinstance(region_def, dict) else {}
            pops = region_def.get("populations", {}) if isinstance(region_def, dict) else {}

            for pop_id, pop_blob in pops.items():
                built: List[PopulationModel] = []

                if isinstance(pop_blob, dict) and "count" in pop_blob:
                    count = _as_int(pop_blob.get("count"), 0)
                    base = _deep_merge(self.global_pop_dyn, region_dyn)
                    base = _deep_merge(base, pop_blob.get("dynamics", {}))

                    n_assemblies = self._apply_downscale(
                        int(round(count / self.neurons_per_assembly))
                    )

                    for idx in range(n_assemblies):
                        merged = dict(base)
                        merged.setdefault("size", self.neurons_per_assembly)

                        if self.baseline_activity_scale:
                            merged["baseline"] = merged.get("baseline", 0.0) + self.baseline_activity_scale

                        aid = f"{region_key}:{pop_id}:{idx}"
                        pop = PopulationModel.from_params(merged, default_assembly_id=aid)
                        built.append(pop)
                        self._all_pops.append(pop)

                region_state["populations"][pop_id] = built

    # ------------------------------------------------------------
    # Stimulus
    # ------------------------------------------------------------

    def inject_stimulus(self, region_id, population_id=None, assembly_index=None, magnitude=1.0):
        rid = self._resolve_region_key(region_id) or region_id
        self._stim_queue.append((rid, population_id, assembly_index, float(magnitude)))

    def _apply_stimuli(self) -> None:
        for region_key, pop_id, idx, mag in self._stim_queue:
            pops = self.region_states.get(region_key, {}).get("populations", {})
            targets = pops.values() if pop_id is None else [pops.get(pop_id, [])]
            for plist in targets:
                for p in plist if idx is None else plist[idx:idx + 1]:
                    p.input += mag
        self._stim_queue.clear()

    # ------------------------------------------------------------
    # Propagation (MASS-BASED, SAFE)
    # ------------------------------------------------------------

    def _reset_inputs(self) -> None:
        for p in self._all_pops:
            p.input = 0.0

    def _region_excitatory_mass(self, region_key: str) -> float:
        total = 0.0
        for plist in self.region_states[region_key]["populations"].values():
            for p in plist:
                if p.sign > 0:
                    total += p.output()
        return total

    def _global_strength(self) -> float:
        return _as_float(self.global_prop.get("global_strength", 1.0), 1.0)

    def _propagate_activity(self) -> None:
        regions = self.brain.get("regions", {}) or {}
        g = self._global_strength()

        region_mass = {
            rk: self._region_excitatory_mass(rk)
            for rk in self.region_states
        }

        for src_key, src_def in regions.items():
            if not isinstance(src_def, dict):
                continue

            outputs = src_def.get("outputs")
            if not outputs:
                continue

            src_signal = region_mass.get(src_key, 0.0)
            if src_signal == 0.0:
                continue

            # ------------------------------
            # Dict outputs
            # ------------------------------
            if isinstance(outputs, dict):
                for tgt_label, w in outputs.items():
                    tgt_key = self._resolve_region_key(tgt_label)
                    if not tgt_key:
                        continue

                    delta = float(w) * src_signal * g
                    for plist in self.region_states[tgt_key]["populations"].values():
                        for p in plist:
                            p.input += delta

            # ------------------------------
            # List outputs
            # ------------------------------
            elif isinstance(outputs, list):
                for edge in outputs:
                    if not isinstance(edge, dict):
                        continue

                    tgt_label = edge.get("target_region") or edge.get("to")
                    tgt_key = self._resolve_region_key(tgt_label)
                    if not tgt_key:
                        continue

                    strength = edge.get("strength", edge.get("weight"))
                    if not isinstance(strength, (int, float)):
                        continue

                    delta = float(strength) * src_signal * g
                    pops = self.region_states[tgt_key]["populations"]

                    tgt_pop = edge.get("target_population")
                    if tgt_pop and tgt_pop in pops:
                        for p in pops[tgt_pop]:
                            p.input += delta
                    else:
                        for plist in pops.values():
                            for p in plist:
                                p.input += delta

    # ------------------------------------------------------------
    # Step
    # ------------------------------------------------------------

    def step(self) -> None:
        self._reset_inputs()
        self._apply_stimuli()
        self._propagate_activity()

        for pop in self._all_pops:
            pop.step(self.dt)

        self.time += self.dt
