from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from learning.schemas.learning_proposal import LearningProposal


@dataclass(frozen=True)
class LearningAuditResult:
    """
    Immutable result of a learning audit.

    CONTRACT:
    - Descriptive only
    - No authority
    - Safe to discard and recompute
    """

    passed: bool
    finding_count: int
    notes: Optional[str] = None


class LearningAudit:
    """
    Verifies learning safety properties.

    HARD RULE:
    - Raises on failure
    - Returns a result object on success
    """

    def audit(
        self,
        *,
        proposals: List[LearningProposal],
    ) -> LearningAuditResult:
        for p in proposals:
            assert p.bounded, "Unbounded learning proposal"
            assert p.replay_consistent, "Replay inconsistency detected"

        return LearningAuditResult(
            passed=True,
            finding_count=0,
            notes=None,
        )
