# persistence/traces.py
from __future__ import annotations

class ExponentialTrace:
    """
    Slow, bounded persistence trace.
    Accumulates from activity, decays over time.
    """

    def __init__(
        self,
        decay_tau: float = 30.0,   # seconds
        max_value: float = 1.0,
    ):
        self.value = 0.0
        self.decay_tau = decay_tau
        self.max_value = max_value

    def step(self, dt: float) -> None:
        # exponential decay
        self.value *= (1.0 - dt / self.decay_tau)
        if self.value < 0.0:
            self.value = 0.0

    def reinforce(self, amount: float) -> None:
        self.value += amount
        if self.value > self.max_value:
            self.value = self.max_value
