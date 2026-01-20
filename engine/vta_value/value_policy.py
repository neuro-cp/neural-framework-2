from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValuePolicy:
    """
    Policy governing updates to the tonic VTA value signal.

    This policy enforces:
    - Slow, bounded updates only
    - No phasic jumps
    - No reward prediction error
    - No learning or accumulation
    - No urgency or latch coupling
    """

    # -------------------------
    # Update constraints
    # -------------------------

    max_step_change: float = 0.1     # absolute cap per update
    min_interval: float = 0.1        # seconds between updates

    # -------------------------
    # Safety flags
    # -------------------------

    enabled: bool = True

    # -------------------------
    # Internal bookkeeping
    # -------------------------

    _last_update_time: Optional[float] = None

    # ============================================================
    # Policy API
    # ============================================================

    def allow_update(self, t: float) -> bool:
        """
        Check whether an update is allowed at time t.
        """
        if not self.enabled:
            return False

        if self._last_update_time is None:
            return True

        return (t - self._last_update_time) >= self.min_interval

    def apply(
        self,
        current_value: float,
        proposed_value: float,
        t: float,
    ) -> float:
        """
        Apply policy constraints to a proposed value update.

        Returns the value that is allowed to be set.
        """
        if not self.allow_update(t):
            return current_value

        # Limit magnitude of change (no phasic jumps)
        delta = proposed_value - current_value
        if delta > self.max_step_change:
            delta = self.max_step_change
        elif delta < -self.max_step_change:
            delta = -self.max_step_change

        new_value = current_value + delta

        # Record update time
        self._last_update_time = t

        return new_value

    def reset(self) -> None:
        """Reset policy state (used on runtime reset)."""
        self._last_update_time = None
