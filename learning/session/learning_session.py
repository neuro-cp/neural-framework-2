from __future__ import annotations

from typing import Iterable, List, Tuple, Optional, Dict, Any

from learning.schemas.learning_proposal import LearningProposal
from learning.schemas.learning_session_report import LearningSessionReport
from learning.session.proposal_generators.frequency_proposal_generator import (
    FrequencyProposalGenerator,
)
from learning.session.proposal_generators.episode_span_proposal_generator import (
    EpisodeSpanProposalGenerator,
)
from learning.session.proposal_generators.structural_pattern_proposal_generator import (
    StructuralPatternProposalGenerator,
)
from learning.audit.learning_audit import LearningAudit
from learning.audit.learning_audit_report import LearningAuditReport


class LearningSession:
    """
    Offline learning session.

    CONTRACT:
    - Pure function of replay artifacts
    - No mutation
    - No persistence
    - Deterministic
    - Ordered execution: generators → audit → report
    - Hard failure on structural violations
    """

    def __init__(self, *, replay_id: str) -> None:
        self._replay_id = replay_id

        self._freq_gen = FrequencyProposalGenerator()
        self._span_gen = EpisodeSpanProposalGenerator()
        self._struct_gen = StructuralPatternProposalGenerator()

        self._audit = LearningAudit()

    def run(self, *, inputs: Iterable[object]) -> List[LearningProposal]:
        proposals: List[LearningProposal] = []

        # --- Input separation (pure extraction) ---

        semantic_ids: List[str] = [
            obj for obj in inputs if isinstance(obj, str)
        ]

        duplicate_semantics_detected = (
            len(semantic_ids) != len(set(semantic_ids))
        )

        semantic_episode_pairs: List[Tuple[str, int]] = [
            obj for obj in inputs
            if isinstance(obj, tuple) and len(obj) == 2
        ]

        pattern_counts: Optional[Dict[str, Any]] = None
        for obj in inputs:
            if isinstance(obj, dict):
                pattern_counts = obj

        # --- 1. Ordered proposal generation ---

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

        if pattern_counts is not None:
            proposals.extend(
                self._struct_gen.generate(
                    replay_id=self._replay_id,
                    pattern_counts=pattern_counts,
                )
            )

        # --- 2. Mandatory structural audit (hard gate) ---

        audit_result: LearningAuditReport = self._audit.audit(
            proposals=proposals
        )

        # Audit now raises internally on failure,
        # so no need to re-raise here.

        # --- 3. Descriptive session report (inspection only) ---

        _ = LearningSessionReport(
            replay_id=self._replay_id,
            proposal_ids=[p.proposal_id for p in proposals],
            proposal_count=len(proposals),
            rejected_count=0,
            audit_passed=audit_result.passed,
            audit_notes=audit_result.notes,
        )

        return proposals