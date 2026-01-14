# persistence/persistence_core.py
from __future__ import annotations

from typing import Dict

from persistence.traces import ExponentialTrace


class BasalGangliaPersistence:
    """
    Persistence of recent striatal dominance.

    PURPOSE:
    - Maintain a short-lived eligibility-like trace of "recent winners"
    - Provide a small, bounded bias signal for future competition
    - NO learning, NO plasticity, NO parameter writes

    NOTES:
    - This is intentionally weak. It's a stabilizer / inertia term, not memory.
    - Cleanup is performed automatically when traces decay to ~0.
    """

    def __init__(
        self,
        decay_tau: float = 30.0,
        bias_gain: float = 0.15,
        epsilon: float = 1e-9,
    ):
        self.traces: Dict[str, ExponentialTrace] = {}
        self.decay_tau = float(decay_tau)
        self.bias_gain = float(bias_gain)
        self.epsilon = float(epsilon)

    # ------------------------------------------------------------
    # Trace management
    # ------------------------------------------------------------

    def ensure_trace(self, assembly_id: str) -> None:
        aid = str(assembly_id)
        if aid not in self.traces:
            self.traces[aid] = ExponentialTrace(decay_tau=self.decay_tau)

    # ------------------------------------------------------------
    # Dynamics
    # ------------------------------------------------------------

    def step(self, dt: float) -> None:
        if not self.traces:
            return

        dead = []
        for aid, trace in self.traces.items():
            trace.step(dt)
            if abs(getattr(trace, "value", 0.0)) < self.epsilon:
                dead.append(aid)

        for aid in dead:
            del self.traces[aid]

    # ------------------------------------------------------------
    # Reinforcement
    # ------------------------------------------------------------

    def reinforce(self, assembly_id: str, amount: float) -> None:
        """
        Additively reinforce a trace.
        """
        if amount == 0.0:
            return
        self.ensure_trace(assembly_id)
        self.traces[str(assembly_id)].reinforce(float(amount))

    # ------------------------------------------------------------
    # Readout
    # ------------------------------------------------------------

    def get_bias(self, assembly_id: str) -> float:
        """
        Returns a small positive bias factor (additive), scaled by bias_gain.
        """
        trace = self.traces.get(str(assembly_id))
        if not trace:
            return 0.0
        return float(getattr(trace, "value", 0.0)) * self.bias_gain

    def dump(self) -> Dict[str, float]:
        """
        Read-only snapshot of trace values for debugging.
        """
        return {aid: float(getattr(t, "value", 0.0)) for aid, t in self.traces.items()}

    def clear(self) -> None:
        self.traces.clear()
