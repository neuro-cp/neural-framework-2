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

    IMPORTANT:
    - This module must NOT import BrainRuntime (avoids circular import).
    - This module must NOT run demo code at import time.

    DESIGN INTENT:
    - Baseline activity is tonic and persistent (does NOT decay to zero)
    - External input is phasic
    - Noise is additive and bounded
    """

    # --------------------------------------------------
    # Identity / metadata
    # --------------------------------------------------

    assembly_id: str = ""
    size: int = 100
    sign: float = 1.0  # +1 excitatory, -1 inhibitory (affects output polarity)

    # --------------------------------------------------
    # State variables
    # --------------------------------------------------

    activity: float = 0.0
    firing_rate: float = 0.0
    input: float = 0.0

    # --------------------------------------------------
    # Dynamics
    # --------------------------------------------------

    baseline: float = 0.0        # tonic drive (persistent)
    tau: float = 0.05            # seconds; membrane / population time constant
    threshold: float = 0.5       # firing threshold
    gain: float = 1.0            # slope above threshold
    max_rate: float = 2.0        # firing rate clamp

    # --------------------------------------------------
    # Noise
    # --------------------------------------------------

    noise_amplitude: float = 0.0
    noise_distribution: str = "gaussian"  # gaussian | uniform

    # --------------------------------------------------
    # Stability clamps
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
        """
        Build a PopulationModel from merged dynamics params.
        """

        assembly_id = str(params.get("assembly_id") or default_assembly_id)

        size = _i(
            params.get("size", params.get("n", params.get("neurons", 100))),
            100,
        )

        sign = _f(params.get("sign", 1.0), 1.0)

        baseline = _f(
            params.get("baseline", params.get("base", 0.0)),
            0.0,
        )

        tau = _f(params.get("tau", 0.05), 0.05)
        threshold = _f(params.get("threshold", 0.5), 0.5)
        gain = _f(params.get("gain", 1.0), 1.0)

        max_rate = _f(
            params.get("max_rate", params.get("max_firing_rate", 2.0)),
            2.0,
        )

        noise_amplitude = _f(
            params.get("noise_amplitude", params.get("noise", 0.0)),
            0.0,
        )

        noise_distribution = str(
            params.get("noise_distribution", "gaussian")
        ).lower()

        clamp_min = _f(params.get("clamp_min", 0.0), 0.0)
        clamp_max = _f(params.get("clamp_max", 1.0), 1.0)

        # Initial conditions
        init_activity = _f(
            params.get("activity", baseline),
            baseline,
        )

        init_firing = _f(
            params.get("firing_rate", 0.0),
            0.0,
        )

        return cls(
            assembly_id=assembly_id,
            size=size,
            sign=sign,
            activity=init_activity,
            firing_rate=init_firing,
            input=0.0,
            baseline=baseline,
            tau=tau,
            threshold=threshold,
            gain=gain,
            max_rate=max_rate,
            noise_amplitude=noise_amplitude,
            noise_distribution=noise_distribution,
            clamp_min=clamp_min,
            clamp_max=clamp_max,
        )

    # --------------------------------------------------
    # Output
    # --------------------------------------------------

    def output(self) -> float:
        """
        Signed output used for region-to-region propagation.
        """
        return self.sign * self.firing_rate

    # --------------------------------------------------
    # Noise
    # --------------------------------------------------

    def _sample_noise(self) -> float:
        amp = self.noise_amplitude
        if amp <= 0.0:
            return 0.0

        if self.noise_distribution == "uniform":
            return random.uniform(-amp, amp)

        # Default: gaussian
        return random.gauss(0.0, amp)

    # --------------------------------------------------
    # Step
    # --------------------------------------------------

    def step(self, dt: float) -> None:
        """
        Advance one timestep.

        MODEL:
        - Baseline is tonic (persistent)
        - Input is phasic (cleared each step)
        - Activity relaxes toward baseline + input
        """

        # Total drive
        drive = self.baseline + self.input + self._sample_noise()

        # Leaky integration toward drive
        # dA/dt = (drive - A) / tau
        if self.tau <= 0.0:
            self.activity = drive
        else:
            self.activity += (dt / self.tau) * (drive - self.activity)

        # Clamp activity for numerical stability
        if self.activity < self.clamp_min:
            self.activity = self.clamp_min
        elif self.activity > self.clamp_max:
            self.activity = self.clamp_max

        # Thresholded firing
        above = self.activity - self.threshold
        if above > 0.0:
            fr = self.gain * above
        else:
            fr = 0.0

        # Clamp firing rate
        if fr < 0.0:
            fr = 0.0
        elif fr > self.max_rate:
            fr = self.max_rate

        self.firing_rate = fr

        # Consume input (phasic)
        self.input = 0.0
