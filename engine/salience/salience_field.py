# engine/salience/salience_field.py
from __future__ import annotations

from typing import Dict


class SalienceField:
    """
    Ephemeral salience signal field.

    PURPOSE:
    - Represents short-lived attentional / novelty / urgency signals
    - Decays continuously
    - Biases downstream gain or routing (later)

    DESIGN CONSTRAINTS:
    - No learning
    - No persistence
    - No cognition
    """

    def __init__(
        self,
        *,
        decay_tau: float = 3.0,
        max_value: float = 1.0,
    ):
        self.decay_tau = float(decay_tau)
        self.max_value = float(max_value)

        # assembly_id -> salience value
        self._values: Dict[str, float] = {}

    # --------------------------------------------------
    # API
    # --------------------------------------------------

    def inject(self, assembly_id: str, amount: float) -> None:
        v = self._values.get(assembly_id, 0.0)
        self._values[assembly_id] = min(self.max_value, v + float(amount))

    def get(self, assembly_id: str) -> float:
        return float(self._values.get(assembly_id, 0.0))

    def step(self, dt: float) -> None:
        if self.decay_tau <= 0:
            self._values.clear()
            return

        decay = float(dt) / self.decay_tau
        for k in list(self._values.keys()):
            v = self._values[k] * (1.0 - decay)
            if v <= 1e-6:
                del self._values[k]
            else:
                self._values[k] = v

    def dump(self) -> Dict[str, float]:
        return dict(self._values)
