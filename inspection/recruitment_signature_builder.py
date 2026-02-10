from __future__ import annotations

from typing import Iterable, Sequence

from inspection.recruitment.recruitment_signature import RecruitmentSignature


class RecruitmentSignatureBuilder:
    """
    Builder for RecruitmentSignature objects.

    This class performs *measurement*, not interpretation.

    It consumes already-available numeric data (e.g. per-assembly activity)
    and emits a frozen structural snapshot suitable for inspection,
    replay analysis, or learning evidence.

    No mutation.
    No caching.
    No policy.
    """

    @staticmethod
    def from_activity(
        *,
        region: str,
        population: str | None,
        assembly_activity: Sequence[float],
        start_step: int,
        end_step: int,
        top_k: int,
        source: str,
        activity_threshold: float,
    ) -> RecruitmentSignature:
        """
        Build a RecruitmentSignature from per-assembly activity values.

        Parameters
        ----------
        assembly_activity:
            Sequence of activity values, one per assembly.

        top_k:
            Number of top assemblies to track for stability / reshuffle analysis.

        activity_threshold:
            Minimum activity required to count an assembly as 'active'.
        """

        if not assembly_activity:
            raise ValueError("assembly_activity must not be empty")

        assembly_count = len(assembly_activity)

        active_indices = [
            i for i, v in enumerate(assembly_activity) if v >= activity_threshold
        ]

        active_fraction = len(active_indices) / assembly_count

        total_mass = float(sum(assembly_activity))

        # Identify top-K assemblies by activity (orderless)
        ranked = sorted(
            range(assembly_count),
            key=lambda i: assembly_activity[i],
            reverse=True,
        )

        top_k_indices = frozenset(ranked[:top_k])

        return RecruitmentSignature(
            region=region,
            population=population,
            assembly_count=assembly_count,
            active_fraction=active_fraction,
            total_mass=total_mass,
            top_k_indices=top_k_indices,
            start_step=start_step,
            end_step=end_step,
            source=source,
        )