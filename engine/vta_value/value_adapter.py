from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValueAdapter:
    """
    Adapter that applies tonic VTA value to downstream systems.

    Allowed injection targets ONLY:
      - DecisionBias (bias scaling)
      - PFC persistence gain

    Explicitly forbidden:
      - GPi / gate relief
      - Latch thresholds
      - Sustain counters
      - Salience
      - Context memory
      - Urgency / affect
    """

    # -------------------------
    # Injection gains
    # -------------------------

    decision_bias_gain: float = 0.5
    pfc_persistence_gain: float = 0.3

    enabled: bool = True

    # ============================================================
    # Injection API
    # ============================================================

    def apply_to_decision_bias(
        self,
        *,
        value: float,
        bias_map: dict[str, float],
    ) -> dict[str, float]:
        """
        Apply value as a soft bias scaling to DecisionBias.

        This does NOT select a winner.
        It only tilts existing biases symmetrically.
        """
        if not self.enabled:
            return bias_map

        if not bias_map:
            return bias_map

        scale = 1.0 + (value * self.decision_bias_gain)

        # Apply uniformly to preserve relative structure
        return {
            k: v * scale
            for k, v in bias_map.items()
        }

    def apply_to_pfc_persistence(
        self,
        *,
        value: float,
        base_gain: float,
    ) -> float:
        """
        Apply value as a persistence-supporting gain to PFC.

        This does NOT create working state.
        It only supports persistence AFTER commitment.
        """
        if not self.enabled:
            return base_gain

        return base_gain * (1.0 + value * self.pfc_persistence_gain)

    # ============================================================
    # Lifecycle
    # ============================================================

    def reset(self) -> None:
        """No internal state to reset (included for symmetry)."""
        return
