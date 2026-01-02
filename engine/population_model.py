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
    """

    # Identity / metadata
    assembly_id: str = ""
    size: int = 100
    sign: float = 1.0  # +1 excitatory-ish, -1 inhibitory-ish (affects output)

    # State
    activity: float = 0.0
    firing_rate: float = 0.0
    input: float = 0.0

    # Dynamics
    baseline: float = 0.0
    tau: float = 0.05           # seconds; leaky integration time constant
    threshold: float = 0.5      # activity threshold for firing
    gain: float = 1.0           # firing gain above threshold
    max_rate: float = 2.0       # clamp

    # Noise
    noise_amplitude: float = 0.0
    noise_distribution: str = "gaussian"  # gaussian | uniform

    # Optional clamps (keeps your "activity ~0.6" style stable)
    clamp_min: float = 0.0
    clamp_max: float = 1.0

    @classmethod
    def from_params(cls, params: Dict[str, Any], *, default_assembly_id: str) -> "PopulationModel":
        """
        Build a PopulationModel from merged dynamics params.
        """
        assembly_id = str(params.get("assembly_id") or default_assembly_id)

        size = _i(
            params.get("size", params.get("n", params.get("neurons", 100))),
            100
        )

        sign = _f(params.get("sign", 1.0), 1.0)

        baseline = _f(params.get("baseline", params.get("base", 0.0)), 0.0)
        tau = _f(params.get("tau", 0.05), 0.05)
        threshold = _f(params.get("threshold", 0.5), 0.5)
        gain = _f(params.get("gain", 1.0), 1.0)
        max_rate = _f(params.get("max_rate", params.get("max_firing_rate", 2.0)), 2.0)

        noise_amplitude = _f(params.get("noise_amplitude", params.get("noise", 0.0)), 0.0)
        noise_distribution = str(params.get("noise_distribution", "gaussian")).lower()

        clamp_min = _f(params.get("clamp_min", 0.0), 0.0)
        clamp_max = _f(params.get("clamp_max", 1.0), 1.0)

        # Initialize activity near baseline unless provided
        init_activity = _f(params.get("activity", baseline), baseline)
        init_firing = _f(params.get("firing_rate", 0.0), 0.0)

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

    def output(self) -> float:
        """
        Signed output used for region-to-region propagation.
        """
        return self.sign * self.firing_rate

    def _sample_noise(self) -> float:
        amp = self.noise_amplitude
        if amp <= 0.0:
            return 0.0
        if self.noise_distribution == "uniform":
            return random.uniform(-amp, amp)
        # default gaussian
        return random.gauss(0.0, amp)

    def step(self, dt: float) -> None:
        """
        Advance one timestep.
        - Uses leaky integration on activity
        - Converts activity -> firing_rate via threshold+gain
        - Clears input after applying it
        """
        drive = self.baseline + self.input + self._sample_noise()

        # Leaky integrator: dA/dt = (drive - A) / tau
        if self.tau <= 0:
            self.activity = drive
        else:
            self.activity += (dt / self.tau) * (drive - self.activity)

        # Clamp activity for stability
        if self.activity < self.clamp_min:
            self.activity = self.clamp_min
        elif self.activity > self.clamp_max:
            self.activity = self.clamp_max

        # Thresholded firing
        above = self.activity - self.threshold
        fr = self.gain * above if above > 0.0 else 0.0

        # Clamp firing
        if fr < 0.0:
            fr = 0.0
        if fr > self.max_rate:
            fr = self.max_rate

        self.firing_rate = fr

        # Consume input
        self.input = 0.0
