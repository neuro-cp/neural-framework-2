# engine/routing/routing_influence.py
from __future__ import annotations
from typing import Optional


class RoutingInfluence:
    """
    Read-only routing influence.
    Converts hypothesis assignments and salience into upstream gain bias.

    Guarantees:
    - deterministic
    - bounded
    - reversible
    - no decision authority
    """

    def __init__(
        self,
        *,
        default_gain: float = 1.0,
        salience_field=None,
        max_salience_gain: float = 0.15,
    ):
        self.default_gain = float(default_gain)
        self.salience_field = salience_field
        self.max_salience_gain = float(max_salience_gain)

    def gain_for(
        self,
        assembly_id: str,
        hypothesis_id: Optional[str],
        target_channel: Optional[str],
    ) -> float:
        """
        Return a multiplicative gain applied to outgoing drive.

        Order of influence:
        1) hypothesis-channel alignment (identity)
        2) salience modulation (magnitude, gated upstream)
        """

        gain = self.default_gain

        # ----------------------------------
        # Hypothesis alignment (existing)
        # ----------------------------------
        if hypothesis_id is not None and target_channel is not None:
            if hypothesis_id == target_channel:
                gain *= 1.10
            else:
                gain *= 0.90

        # ----------------------------------
        # Salience modulation (new, lawful)
        # ----------------------------------
        if self.salience_field is not None:
            s = float(self.salience_field.get(assembly_id))
            if s > 0.0:
                # bounded, linear lift
                gain *= (1.0 + min(s, 1.0) * self.max_salience_gain)

        return gain
