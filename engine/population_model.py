from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, Optional


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def _f(x: Any, default: float) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _i(x: Any, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return int(default)


# ------------------------------------------------------------
# Population Model (GROUND-TRUTH, SELF-SUSTAINING)
# ------------------------------------------------------------

@dataclass
class PopulationModel:
    """
    Assembly-level dynamics unit.

    CORE INVARIANTS:
    - Activity is signed and membrane-like
    - Inhibition acts during integration
    - Firing rate is rectified and bounded
    - Populations have intrinsic tonic state
    - No oscillators, no learning, no hidden state
    """

    # -------------------------
    # Identity
    # -------------------------

    assembly_id: str = ""
    size: int = 100
    sign: float = 1.0  # +1 excitatory, -1 inhibitory

    # -------------------------
    # State
    # -------------------------

    activity: float = 0.0
    firing_rate: float = 0.0

    # Transient inputs (cleared each step)
    input: float = 0.0
    lateral_inhibition: float = 0.0

    # -------------------------
    # Intrinsic tonic state (NEW)
    # -------------------------

    tonic: float = 0.0                 # persistent current
    tonic_target: float = 0.0          # preferred resting level
    tonic_gain: float = 0.05           # VERY slow adaptation

    # -------------------------
    # Core dynamics
    # -------------------------

    baseline: float = 0.0
    tau: float = 10.0
    threshold: float = 0.0
    gain: float = 1.0
    max_rate: float = 10.0

    inhibition_gain: float = 0.0
    homeostatic_gain: float = 0.0
    normalization: float = 0.0

    # -------------------------
    # Noise
    # -------------------------

    noise_amplitude: float = 0.0
    noise_distribution: str = "gaussian"

    # -------------------------
    # Safety
    # -------------------------

    clamp_min: float = -1.0
    clamp_max: float = 1.0

    # -------------------------
    # Semantic modifiers
    # -------------------------

    semantic_role: Optional[str] = None
    semantic_gain: float = 1.0
    semantic_tau_bias: float = 1.0
    semantic_inhibition_bias: float = 1.0

    # ------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------

    @classmethod
    def from_params(
        cls,
        params: Dict[str, Any],
        *,
        default_assembly_id: str,
        global_defaults: Optional[Dict[str, Any]] = None,
    ) -> "PopulationModel":

        g = global_defaults or {}

        def pick(key: str, default: Any):
            return params.get(key, g.get(key, default))

        baseline = _f(
            pick("baseline", pick("baseline_firing_rate_hz", 0.0)),
            0.0,
        )

        # --- NEW: tonic target defaults ---
        tonic_target = _f(
            pick("tonic_target", baseline),
            baseline,
        )

        model = cls(
            assembly_id=str(pick("assembly_id", default_assembly_id)),
            size=_i(pick("size", pick("neurons", 100)), 100),
            sign=_f(pick("sign", 1.0), 1.0),

            baseline=baseline,
            tau=_f(pick("tau", 10.0), 10.0),
            threshold=_f(pick("threshold", 0.0), 0.0),
            gain=_f(pick("gain", 1.0), 1.0),
            max_rate=_f(pick("max_rate", 10.0), 10.0),

            inhibition_gain=_f(pick("inhibition_gain", 0.0), 0.0),
            homeostatic_gain=_f(pick("homeostatic_gain", 0.0), 0.0),
            normalization=_f(pick("normalization", 0.0), 0.0),

            noise_amplitude=_f(pick("noise_amplitude", 0.0), 0.0),
            noise_distribution=str(pick("noise_distribution", "gaussian")).lower(),

            clamp_min=_f(pick("clamp_min", -1.0), -1.0),
            clamp_max=_f(pick("clamp_max", 1.0), 1.0),

            activity=_f(params.get("activity", baseline), baseline),

            tonic_target=tonic_target,
            tonic=tonic_target,
            tonic_gain=_f(pick("tonic_gain", 0.02), 0.02),
        )

        # Semantic modifiers (unchanged)
        model.semantic_role = params.get("role")

        model.semantic_gain = max(
            0.1,
            1.0
            + _f(params.get("gain_modulation", 0.0), 0.0)
            + _f(params.get("novelty_bias", 0.0), 0.0),
        )

        model.semantic_tau_bias = max(
            0.1,
            1.0
            - _f(params.get("recurrent_bias", 0.0), 0.0)
            + _f(params.get("fatigue_sensitivity", 0.0), 0.0),
        )

        model.semantic_inhibition_bias = max(
            0.1,
            1.0 + _f(params.get("inhibitory_bias", 0.0), 0.0),
        )

        return model

    # ------------------------------------------------------------
    # Output
    # ------------------------------------------------------------

    def output(self) -> float:
        return self.firing_rate

    # ------------------------------------------------------------
    # Noise
    # ------------------------------------------------------------

    def _sample_noise(self) -> float:
        if self.noise_amplitude <= 0.0:
            return 0.0
        if self.noise_distribution == "uniform":
            return random.uniform(-self.noise_amplitude, self.noise_amplitude)
        return random.gauss(0.0, self.noise_amplitude)

    # ------------------------------------------------------------
    # Step
    # ------------------------------------------------------------

    def step(self, dt: float) -> None:
        """
        Advance one timestep.

        Key property:
        - Tonic state adapts slowly
        - Activity does NOT collapse to zero
        """

        # --- Slow tonic adaptation (NEW) ---
        self.tonic += self.tonic_gain * (self.tonic_target - self.activity)

        tau = self.tau * self.semantic_tau_bias
        gain = self.gain * self.semantic_gain
        inhibition_gain = self.inhibition_gain * self.semantic_inhibition_bias

        homeo = self.homeostatic_gain * (self.baseline - self.activity)
        self_inhib = inhibition_gain * self.activity

        net_drive = self.sign * (self.input - self.lateral_inhibition)

        drive = (
            self.baseline
            + self.tonic
            + net_drive
            + homeo
            - self_inhib
            + self._sample_noise()
        )

        if tau > 0.0:
            self.activity += (dt / tau) * (drive - self.activity)
        else:
            self.activity = drive

        self.activity = max(self.clamp_min, min(self.activity, self.clamp_max))

        above = self.activity - self.threshold
        if above > 0.0:
            fr = gain * above
            if self.normalization > 0.0:
                fr /= (1.0 + self.normalization * abs(self.activity))
        else:
            fr = 0.0

        self.firing_rate = max(0.0, min(fr, self.max_rate))

        self.input = 0.0
        self.lateral_inhibition = 0.0
