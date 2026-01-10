# engine/runtime_context.py
from __future__ import annotations

from typing import Dict


class RuntimeContext:
    """
    Ephemeral runtime context buffer.

    PURPOSE:
    - Provide short-lived, decay-only bias signals
    - Act as a stable expansion point for PFC-like context
    - Never mutate physiology or parameters

    DESIGN GUARANTEES:
    - No learning
    - No plasticity
    - No cross-assembly side effects
    - Fully optional (neutral when unused)
    """

    def __init__(self, decay_tau: float = 5.0):
        self.decay_tau = float(decay_tau)

        # Scalar context values keyed by assembly_id
        self._context: Dict[str, float] = {}

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def get_gain(self, assembly_id: str) -> float:
        """
        Return multiplicative gain contribution for an assembly.
        Neutral = 1.0
        """
        return 1.0 + self._context.get(assembly_id, 0.0)

    def inject(self, assembly_id: str, amount: float) -> None:
        """
        Add transient context bias to an assembly.
        """
        self._context[assembly_id] = self._context.get(assembly_id, 0.0) + amount

    def step(self, dt: float) -> None:
        """
        Exponential decay of all context traces.
        """
        if not self._context:
            return

        decay = dt / max(self.decay_tau, 1e-6)
        to_delete = []

        for k, v in self._context.items():
            nv = v * (1.0 - decay)
            if abs(nv) < 1e-6:
                to_delete.append(k)
            else:
                self._context[k] = nv

        for k in to_delete:
            del self._context[k]

    def clear(self) -> None:
        self._context.clear()
