from __future__ import annotations

from typing import Iterable, List, Tuple

from learning.schemas.learning_proposal import LearningProposal
from learning.schemas.learning_session_report import LearningSessionReport
from learning.session.proposal_generators.frequency_proposal_generator import (
    FrequencyProposalGenerator,
)
from learning.session.proposal_generators.episode_span_proposal_generator import (
    EpisodeSpanProposalGenerator,
)
from learning.audit.learning_audit import LearningAudit, LearningAuditResult


class LearningSession:
    """
    Offline learning session.

    CONTRACT:
    - Pure function of replay artifacts
    - No mutation
    - No persistence
    - Deterministic
    - Ordered execution: generators → audit → report
    """

    def __init__(self, *, replay_id: str) -> None:
        self._replay_id = replay_id

        # Generators are stateless and ordered
        self._freq_gen = FrequencyProposalGenerator()
        self._span_gen = EpisodeSpanProposalGenerator()

        # Audit is mandatory and always runs after generation
        self._audit = LearningAudit()

    def run(self, *, inputs: Iterable[object]) -> List[LearningProposal]:
        proposals: List[LearningProposal] = []

        semantic_ids: List[str] = [
            obj for obj in inputs if isinstance(obj, str)
        ]

        semantic_episode_pairs: List[Tuple[str, int]] = [
            obj for obj in inputs
            if isinstance(obj, tuple) and len(obj) == 2
        ]

        # 1. Proposal generation (ordered)
        proposals.extend(
            self._freq_gen.generate(
                replay_id=self._replay_id,
                semantic_ids=semantic_ids,
            )
        )
        proposals.extend(
            self._span_gen.generate(
                replay_id=self._replay_id,
                semantic_episode_pairs=semantic_episode_pairs,
            )
        )

        # 2. Mandatory audit (hard gate)
        audit_result: LearningAuditResult = self._audit.audit(
            proposals=proposals
        )

        # 3. Session report (descriptive only)
        _ = LearningSessionReport(
            replay_id=self._replay_id,
            proposal_ids=[p.proposal_id for p in proposals],
            proposal_count=len(proposals),
            rejected_count=0,
            audit_passed=audit_result.passed,
            audit_notes=audit_result.notes,
        )

        return proposals
