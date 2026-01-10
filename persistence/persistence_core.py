# persistence/persistence_core.py
from __future__ import annotations
from typing import Dict

from persistence.traces import ExponentialTrace


class BasalGangliaPersistence:
    """
    Persistence of recent striatal dominance.
    Biases future competition slightly.
    """

    def __init__(
        self,
        decay_tau: float = 30.0,
        bias_gain: float = 0.15,
    ):
        self.traces: Dict[str, ExponentialTrace] = {}
        self.decay_tau = decay_tau
        self.bias_gain = bias_gain

    def ensure_trace(self, assembly_id: str) -> None:
        if assembly_id not in self.traces:
            self.traces[assembly_id] = ExponentialTrace(
                decay_tau=self.decay_tau
            )

    def step(self, dt: float) -> None:
        for trace in self.traces.values():
            trace.step(dt)

    def reinforce(self, assembly_id: str, amount: float) -> None:
        self.ensure_trace(assembly_id)
        self.traces[assembly_id].reinforce(amount)

    def get_bias(self, assembly_id: str) -> float:
        """
        Returns a small positive bias factor.
        """
        trace = self.traces.get(assembly_id)
        if not trace:
            return 0.0
        return trace.value * self.bias_gain
