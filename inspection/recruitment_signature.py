from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional


@dataclass(frozen=True)
class RecruitmentSignature:
    """
    Immutable, inspection-only snapshot describing how a population or region
    expressed activity during a window of time.

    This object encodes *structure*, not meaning.

    It is lawful to:
    - compare signatures
    - aggregate signatures
    - correlate signatures with semantic activation or outcomes

    It is NOT lawful to:
    - drive runtime behavior
    - activate or suppress assemblies
    - encode rules or actions
    """

    # --------------------------------------------------
    # Identity / scope
    # --------------------------------------------------

    region: str
    population: Optional[str]

    # --------------------------------------------------
    # Structural expression
    # --------------------------------------------------

    assembly_count: int

    active_fraction: float
    """
    Fraction of assemblies meaningfully active during the window.
    Range: [0.0, 1.0]
    """

    total_mass: float
    """
    Sum of activity mass across assemblies.
    Used to distinguish rescaling vs recruitment.
    """

    # --------------------------------------------------
    # Distribution shape
    # --------------------------------------------------

    top_k_indices: FrozenSet[int]
    """
    Indices of the most active assemblies (orderless).
    Used for stability / reshuffle analysis.
    """

    # --------------------------------------------------
    # Temporal context
    # --------------------------------------------------

    start_step: int
    end_step: int

    # --------------------------------------------------
    # Optional provenance (inspection only)
    # --------------------------------------------------

    source: str
    """
    Freeform descriptor such as:
    - 'baseline'
    - 'poke:STN:150'
    - 'replay:wake'
    """

    def duration(self) -> int:
        return self.end_step - self.start_step