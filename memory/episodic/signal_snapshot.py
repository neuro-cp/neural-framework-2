from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SignalSnapshot:
    """
    Offline snapshot of modulatory signals at a single timestep.

    This object is:
    - read-only
    - descriptive only
    - detached from runtime
    - safe for narration and inspection

    It does NOT:
    - infer intent
    - trigger behavior
    - mutate state
    - encode semantics
    """

    step: int

    # --------------------------------------------------
    # Modulatory signals (optional, sparse by design)
    # --------------------------------------------------
    salience: Optional[float] = None
    value: Optional[float] = None
    urgency: Optional[float] = None

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def is_nonbaseline(self) -> bool:
        """
        Return True if any signal is present and non-zero.
        """
        return any(
            v not in (None, 0.0)
            for v in (self.salience, self.value, self.urgency)
        )

    def as_dict(self) -> dict[str, float]:
        """
        Return a compact dict of present signals.
        """
        out: dict[str, float] = {}

        if self.salience is not None:
            out["salience"] = self.salience
        if self.value is not None:
            out["value"] = self.value
        if self.urgency is not None:
            out["urgency"] = self.urgency

        return out
