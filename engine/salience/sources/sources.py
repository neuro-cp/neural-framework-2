# engine/salience/sources/sources.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol, Iterable


# ============================================================
# Salience Update
# ============================================================

@dataclass(frozen=True)
class SalienceUpdate:
    """
    Proposed salience change emitted by a source.

    NOTE:
    - This is a proposal, not an action.
    - SaliencePolicy decides whether it is allowed.
    """

    channel_id: str
    delta: float
    source: str


# ============================================================
# Salience Source Interface
# ============================================================

class SalienceSource(Protocol):
    """
    Abstract salience source.

    A source:
    - Observes system state (passed in explicitly)
    - Emits zero or more SalienceUpdate proposals
    - Has no side effects
    - Has no memory unless explicitly designed to

    Sources DO NOT:
    - Apply salience directly
    - Know about decision latch
    - Know about dopamine
    """

    name: str

    def compute(self, observation: Dict[str, float]) -> Iterable[SalienceUpdate]:
        """
        Compute salience updates from an observation snapshot.

        observation:
            A flat, read-only dict of signals relevant to this source.
            (e.g., dominance delta, novelty score, prediction error)

        Returns:
            Iterable of SalienceUpdate proposals (possibly empty)
        """
        ...


# ============================================================
# Utilities
# ============================================================

def single_update(
    channel_id: str,
    delta: float,
    source: str,
) -> Iterable[SalienceUpdate]:
    """
    Convenience helper for simple sources that emit one update.
    """
    return (SalienceUpdate(channel_id, delta, source),)
