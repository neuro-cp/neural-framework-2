from __future__ import annotations

from typing import Tuple


class LearningEvaluationPolicy:
    """
    Policy defining whether learning is allowed.

    CONTRACT:
    - Pure logic
    - Deterministic
    - No mutation
    """

    MIN_TOTAL_DIFFS: int = 1

    @classmethod
    def evaluate(
        cls,
        *,
        total_diffs: int,
    ) -> Tuple[bool, Tuple[str, ...]]:
        reasons = []

        if total_diffs < cls.MIN_TOTAL_DIFFS:
            reasons.append("insufficient_evidence")

        allowed = not reasons
        return allowed, tuple(reasons)
