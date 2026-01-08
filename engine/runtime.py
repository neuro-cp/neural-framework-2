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
    Stable mass-based runtime with semantic gating.

    CHECKPOINT 5 (ENFORCED):
    - Subpopulations instantiated as real assemblies
    - TRN / GPi-style inhibition enforced at propagation
    - Relay nuclei gated before downstream projection
    - No learning, no oscillations, no instability

    CHECKPOINT 6 (FOUNDATION ONLY):
    - Explicit brain_state tracking (INERT)
    """

    # --------------------------------------------------
    # Init
    # --------------------------------------------------

    def __init__(self, brain: Dict[str, Any], dt: float = 0.01):
        self.brain = brain
        self.dt = float(dt)
        self.time = 0.0

        # -------------------------------
        # Brain state (INERT)
        # -------------------------------
        self.brain_state: str = "awake"

        gd = brain.get("global_dynamics") or brain.get("dynamics") or {}

        self.global_pop_dyn = gd.get("population_defaults", {}) if isinstance(gd, dict) else {}
        self.global_prop = gd.get("propagation", {}) if isinstance(gd, dict) else {}

        # -------------------------------
        # Global activity regulation
        # -------------------------------
        self.target_global_activity = _as_float(gd.get("target_global_activity", 1.0), 1.0)
        self.activity_gain = 1.0
        self.activity_gain_tau = _as_float(gd.get("activity_gain_tau", 1.0), 1.0)
        self.min_activity_gain = _as_float(gd.get("min_activity_gain", 0.1), 0.1)
        self.max_activity_gain = _as_float(gd.get("max_activity_gain", 2.0), 2.0)

        # -------------------------------
        # Runtime config
        # -------------------------------
        runtime_cfg = brain.get("runtime", {}) or {}

        self.neurons_per_assembly = _as_int(runtime_cfg.get("neurons_per_assembly", 500), 500)
        self.assembly_downscale_factor = max(
            _as_float(runtime_cfg.get("assembly_downscale_factor", 1.0), 1.0),
            1.0,
        )
        self.max_assemblies_per_population = _as_int(
            runtime_cfg.get("max_assemblies_per_population", 0),
            0,
        )

        # -------------------------------
        # State containers
        # -------------------------------
        self.region_states: Dict[str, Dict[str, Any]] = {}
        self._all_pops: List[PopulationModel] = []

        self._stim_queue: List[Tuple[str, Optional[str], Optional[int], float]] = []
        self._region_key_by_label: Dict[str, str] = {}

        self._build(brain)

    # ------------------------------------------------------------
    # Brain state API (SAFE / INERT)
    # ------------------------------------------------------------

    def set_state(self, name: str) -> None:
        """Set global brain state (no dynamics attached yet)."""
        name = _norm(name)
        if name and name != self.brain_state:
            self.brain_state = name

    def get_state(self) -> str:
        return self.brain_state

    # ------------------------------------------------------------
    # Region resolution
    # ------------------------------------------------------------

    def _build_region_id_map(self, regions: Dict[str, Any]) -> None:
        self._region_key_by_label.clear()
        for rk, rdef in regions.items():
            self._region_key_by_label[_norm(rk)] = rk
            if isinstance(rdef, dict):
                rid = rdef.get("region_id")
                if rid:
                    self._region_key_by_label[_norm(rid)] = rk

    def _resolve_region_key(self, label: str) -> Optional[str]:
        return self._region_key_by_label.get(_norm(label)) if label else None

    # ------------------------------------------------------------
    # Build
    # ------------------------------------------------------------

    def _apply_downscale(self, n: int) -> int:
        if n <= 0:
            return 0
        n2 = int(round(n * self.assembly_downscale_factor))
        n2 = max(1, n2)
        if self.max_assemblies_per_population:
            n2 = min(n2, self.max_assemblies_per_population)
        return n2

    def _build(self, brain: Dict[str, Any]) -> None:
        regions = brain.get("regions", {}) or {}
        self._build_region_id_map(regions)

        for region_key, region_def in regions.items():
            state = {"def": region_def, "populations": {}}
            self.region_states[region_key] = state

            region_dyn = region_def.get("dynamics", {}) if isinstance(region_def, dict) else {}
            pops = region_def.get("populations", {}) if isinstance(region_def, dict) else {}
            is_relay_region = bool(region_def.get("is_relay"))

            for pop_id, pop_blob in pops.items():
                if not isinstance(pop_blob, dict) or "count" not in pop_blob:
                    continue

                count = _as_int(pop_blob.get("count"), 0)
                base = _deep_merge(self.global_pop_dyn, region_dyn)
                base = _deep_merge(base, pop_blob.get("dynamics", {}))

                total_assemblies = self._apply_downscale(
                    int(round(count / self.neurons_per_assembly))
                )

                built: List[PopulationModel] = []
                subpops = pop_blob.get("subpopulations")

                # ----------------------------
                # Subpopulation expansion
                # ----------------------------
                if isinstance(subpops, dict):
                    for sub_name, spec in subpops.items():
                        frac = _as_float(spec.get("fraction", 0.0), 0.0)
                        n = max(1, int(round(total_assemblies * frac)))

                        for i in range(n):
                            merged = dict(base)
                            merged.setdefault("size", self.neurons_per_assembly)
                            merged.update(pop_blob)
                            merged.update(spec)

                            aid = f"{region_key}:{pop_id}:{sub_name}:{i}"
                            pop = PopulationModel.from_params(
                                merged,
                                default_assembly_id=aid,
                                global_defaults=self.global_pop_dyn,
                            )

                            pop.subpopulation = sub_name
                            pop.semantic_role = spec.get("role")

                            if is_relay_region:
                                pop.is_relay = True

                            if pop_blob.get("neuron_type") == "inhibitory":
                                pop.receives_inhibition_from = set()

                            built.append(pop)
                            self._all_pops.append(pop)

                    state["populations"][pop_id] = built
                    continue

                # ----------------------------
                # Homogeneous population
                # ----------------------------
                for idx in range(total_assemblies):
                    merged = dict(base)
                    merged.setdefault("size", self.neurons_per_assembly)

                    aid = f"{region_key}:{pop_id}:{idx}"
                    pop = PopulationModel.from_params(
                        {**merged, **pop_blob},
                        default_assembly_id=aid,
                        global_defaults=self.global_pop_dyn,
                    )

                    if is_relay_region:
                        pop.is_relay = True

                    built.append(pop)
                    self._all_pops.append(pop)

                state["populations"][pop_id] = built

    # ------------------------------------------------------------
    # Activity helpers
    # ------------------------------------------------------------

    def _total_activity(self) -> float:
        return sum(abs(p.output()) for p in self._all_pops)

    def _update_activity_gain(self) -> None:
        error = self.target_global_activity - self._total_activity()
        self.activity_gain += (self.dt / self.activity_gain_tau) * error
        self.activity_gain = max(
            self.min_activity_gain,
            min(self.activity_gain, self.max_activity_gain),
        )

    # ------------------------------------------------------------
    # Stimulus
    # ------------------------------------------------------------

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
        for region_key, pop_id, idx, mag in self._stim_queue:
            pops = self.region_states.get(region_key, {}).get("populations", {})
            targets = pops.values() if pop_id is None else [pops.get(pop_id, [])]
            for plist in targets:
                for p in plist if idx is None else plist[idx : idx + 1]:
                    p.input += mag
        self._stim_queue.clear()

    # ------------------------------------------------------------
    # Propagation with relay gating
    # ------------------------------------------------------------

    def _reset_inputs(self) -> None:
        for p in self._all_pops:
            p.input = 0.0

    def _region_mass(self, region_key: str) -> float:
        return sum(
            p.output()
            for plist in self.region_states[region_key]["populations"].values()
            for p in plist
        )

    def _propagate_activity(self) -> None:
        regions = self.brain.get("regions", {}) or {}
        g = _as_float(self.global_prop.get("global_strength", 1.0), 1.0) * self.activity_gain

        region_mass = {rk: self._region_mass(rk) for rk in self.region_states}

        for src_key, src_def in regions.items():
            outputs = src_def.get("outputs") if isinstance(src_def, dict) else None
            if not outputs:
                continue

            src_signal = region_mass.get(src_key, 0.0)
            if src_signal == 0.0:
                continue

            for edge in outputs:
                tgt_key = self._resolve_region_key(edge.get("target_region"))
                if not tgt_key:
                    continue

                strength = _as_float(edge.get("strength", 0.0), 0.0)
                delta = strength * src_signal * g

                for plist in self.region_states[tgt_key]["populations"].values():
                    for p in plist:
                        if getattr(p, "is_relay", False):
                            if p.activity <= p.threshold:
                                continue

                        if hasattr(p, "receives_inhibition_from"):
                            if src_key in p.receives_inhibition_from:
                                p.input -= abs(delta)
                                continue

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

        self._update_activity_gain()
        self.time += self.dt
