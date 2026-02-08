from __future__ import annotations

from typing import Dict, Optional


class DecisionBias:
    """
    Ephemeral downstream bias applied *after* a decision is committed.

    PURPOSE:
    - Bias future signal routing in favor of a committed decision
    - Introduce short-term inertia without learning
    - Decay cleanly back to neutrality

    HARD CONSTRAINTS:
    - Read-only with respect to competition and salience
    - No learning
    - No history beyond current bias values
    - Deterministic decay
    """

    def __init__(
        self,
        *,
        decay_tau: float = 4.0,
        max_bias: float = 0.30,
        suppress_gain: float = 0.15,
    ):
        """
        Parameters:
        - decay_tau: seconds for bias to decay toward zero
        - max_bias: absolute cap on bias magnitude
        - suppress_gain: how strongly non-winning channels are suppressed
        """
        self.decay_tau = float(decay_tau)
        self.max_bias = float(max_bias)
        self.suppress_gain = float(suppress_gain)

        # channel_id -> bias value (positive = facilitation, negative = suppression)
        self._bias: Dict[str, float] = {}

        # For observability
        self.last_winner: Optional[str] = None
        self.last_applied_step: Optional[int] = None
       
        # Ephemeral external bias modifiers (cleared every step)
        self._external_modifiers = []


    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def apply_decision(
        self,
        *,
        winner: str,
        channels: Optional[list[str]] = None,
        strength: float = 1.0,
        step: Optional[int] = None,
    ) -> None:
        """
        Apply a decision bias.

        Parameters:
        - winner: winning channel identifier
        - channels: all known competing channels (optional)
        - strength: scalar in [0, 1] controlling bias magnitude
        - step: runtime step (for diagnostics only)
        """

        strength = max(0.0, min(1.0, float(strength)))

        # Facilitate the winner
        win_bias = min(self.max_bias, self.max_bias * strength)
        self._bias[winner] = win_bias

        # Suppress competitors if provided
        if channels:
            for ch in channels:
                if ch == winner:
                    continue
                self._bias[ch] = max(
                    -self.max_bias,
                    -self.suppress_gain * win_bias,
                )

        self.last_winner = winner
        self.last_applied_step = step

    def get(self, channel_id: str) -> float:
        """
        Return current bias for a channel.
        """
        return float(self._bias.get(channel_id, 0.0))

    # ------------------------------------------------------------
    # External modulation hooks (ephemeral)
    # ------------------------------------------------------------

    def apply_external(self, fn) -> None:
        """
        Apply a temporary external modifier to the bias map.

        - fn: Callable[[Dict[str, float]], Dict[str, float]]
        - Applied after decay
        - Cleared automatically after one step
        - No learning, no persistence
        """
        self._external_modifiers.append(fn)

    # ------------------------------------------------------------
    # Decay
    # ------------------------------------------------------------

    def step(self, dt: float) -> None:
        """
        Apply continuous exponential decay toward zero,
        then apply any ephemeral external modifiers.
        """
        if self.decay_tau <= 0:
            self._bias.clear()
        else:
            decay = float(dt) / self.decay_tau
            for ch in list(self._bias.keys()):
                v = self._bias[ch] * (1.0 - decay)
                if abs(v) <= 1e-6:
                    del self._bias[ch]
                else:
                    self._bias[ch] = v

        # --------------------------------------------------
        # Apply ephemeral external modifiers (e.g. VTA value)
        # --------------------------------------------------
        if self._external_modifiers:
            bias = dict(self._bias)  # work on a copy

            for fn in self._external_modifiers:
                bias = fn(bias)

            # Enforce hard bounds and cleanup
            for ch, v in list(bias.items()):
                if abs(v) > self.max_bias:
                    bias[ch] = max(-self.max_bias, min(self.max_bias, v))
                if abs(bias[ch]) <= 1e-6:
                    del bias[ch]

            self._bias = bias
            self._external_modifiers.clear()



    # ------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------

    def dump(self) -> Dict[str, float]:
        """
        Snapshot of all current bias values.
        """
        return dict(self._bias)
