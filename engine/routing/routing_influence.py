# engine/routing/routing_influence.py
from __future__ import annotations
from typing import Optional


class RoutingInfluence:
    """
    Read-only routing influence.
    Converts hypothesis assignments into upstream gain bias.
    """

    def __init__(self, default_gain: float = 1.0):
        self.default_gain = float(default_gain)

    def gain_for(
        self,
        assembly_id: str,
        hypothesis_id: Optional[str],
        target_channel: Optional[str],
    ) -> float:
        """
        Return a multiplicative gain applied to outgoing drive.

        MUST be:
        - deterministic
        - bounded
        - reversible
        """

        # No hypothesis → no influence
        if hypothesis_id is None or target_channel is None:
            return self.default_gain

        # Lawful, minimal asymmetry
        # Hypotheses bias their matching channels only
        if hypothesis_id == target_channel:
            return self.default_gain * 1.10

        # Mild suppression of non-matching channel
        return self.default_gain * 0.90
