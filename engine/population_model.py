# engine/population_model.py
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict


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


@dataclass
class PopulationModel:
    """
    A single 'assembly' (subpopulation) dynamics model.

    DESIGN GOALS:
    - Tonic baseline (never decays to zero)
    - Phasic external input
    - Activity-dependent inhibition (stability)
    - Soft normalization (prevents lockstep saturation)
    """

    # --------------------------------------------------
    # Identity
    # --------------------------------------------------

    assembly_id: str = ""
    size: int = 100
    sign: float = 1.0  # +1 excitatory, -1 inhibitory

    # --------------------------------------------------
    # State
    # --------------------------------------------------

    activity: float = 0.0
    firing_rate: float = 0.0
    input: float = 0.0

    # --------------------------------------------------
    # Core dynamics
    # --------------------------------------------------

    baseline: float = 0.0
    tau: float = 0.05
    threshold: float = 0.5
    gain: float = 1.0
    max_rate: float = 2.0

    # NEW: intrinsic stabilization
    inhibition_gain: float = 0.0     # subtracts activity from drive
    normalization: float = 0.0        # divisive soft cap

    # --------------------------------------------------
    # Noise
    # --------------------------------------------------

    noise_amplitude: float = 0.0
    noise_distribution: str = "gaussian"

    # --------------------------------------------------
    # Safety clamps
    # --------------------------------------------------

    clamp_min: float = 0.0
    clamp_max: float = 1.0

    # --------------------------------------------------
    # Construction
    # --------------------------------------------------

    @classmethod
    def from_params(
        cls,
        params: Dict[str, Any],
        *,
        default_assembly_id: str,
    ) -> "PopulationModel":

        assembly_id = str(params.get("assembly_id") or default_assembly_id)

        size = _i(params.get("size", params.get("neurons", 100)), 100)
        sign = _f(params.get("sign", 1.0), 1.0)

        baseline = _f(params.get("baseline", 0.0), 0.0)
        tau = _f(params.get("tau", 0.05), 0.05)
        threshold = _f(params.get("threshold", 0.5), 0.5)
        gain = _f(params.get("gain", 1.0), 1.0)
        max_rate = _f(params.get("max_rate", 2.0), 2.0)

        inhibition_gain = _f(params.get("inhibition_gain", 0.0), 0.0)
        normalization = _f(params.get("normalization", 0.0), 0.0)

        noise_amplitude = _f(params.get("noise_amplitude", 0.0), 0.0)
        noise_distribution = str(params.get("noise_distribution", "gaussian")).lower()

        clamp_min = _f(params.get("clamp_min", 0.0), 0.0)
        clamp_max = _f(params.get("clamp_max", 1.0), 1.0)

        init_activity = _f(params.get("activity", baseline), baseline)

        return cls(
            assembly_id=assembly_id,
            size=size,
            sign=sign,
            activity=init_activity,
            firing_rate=0.0,
            input=0.0,
            baseline=baseline,
            tau=tau,
            threshold=threshold,
            gain=gain,
            max_rate=max_rate,
            inhibition_gain=inhibition_gain,
            normalization=normalization,
            noise_amplitude=noise_amplitude,
            noise_distribution=noise_distribution,
            clamp_min=clamp_min,
            clamp_max=clamp_max,
        )

    # --------------------------------------------------
    # Output
    # --------------------------------------------------

    def output(self) -> float:
        return self.sign * self.firing_rate

    # --------------------------------------------------
    # Noise
    # --------------------------------------------------

    def _sample_noise(self) -> float:
        if self.noise_amplitude <= 0.0:
            return 0.0
        if self.noise_distribution == "uniform":
            return random.uniform(-self.noise_amplitude, self.noise_amplitude)
        return random.gauss(0.0, self.noise_amplitude)

    # --------------------------------------------------
    # Step
    # --------------------------------------------------

    def step(self, dt: float) -> None:
        """
        Advance one timestep with intrinsic stabilization.
        """

        # Activity-dependent inhibition
        inhibition = self.inhibition_gain * self.activity

        # Total drive
        drive = (
            self.baseline
            + self.input
            - inhibition
            + self._sample_noise()
        )

        # Leaky integration
        if self.tau > 0.0:
            self.activity += (dt / self.tau) * (drive - self.activity)
        else:
            self.activity = drive

        # Clamp activity
        self.activity = max(self.clamp_min, min(self.activity, self.clamp_max))

        # Threshold + soft normalization
        above = self.activity - self.threshold
        if above > 0.0:
            fr = self.gain * above
            if self.normalization > 0.0:
                fr /= (1.0 + self.normalization * self.activity)
        else:
            fr = 0.0

        self.firing_rate = max(0.0, min(fr, self.max_rate))

        # Consume phasic input
        self.input = 0.0
