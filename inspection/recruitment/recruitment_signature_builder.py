from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from inspection.recruitment.recruitment_stats_from_dump import (
    load_dump,
    total_mass,
    fraction_active,
    top_k_assemblies,
    tier_counts,
    overlap_fraction,
)


# ------------------------------------------------------------
# Data object (episodic artifact)
# ------------------------------------------------------------

@dataclass(frozen=True)
class RecruitmentSignature:
    # Episodic identity
    episode_id: int
    region: str

    episode_start_step: int
    episode_end_step: int

    salience_summary: Dict[str, float]
    urgency_summary: Dict[str, float]
    value_summary: Dict[str, float]
    decision_summary: Dict | None

    # Recruitment comparison
    baseline_step: int
    poke_step: int

    baseline_mass: float
    poke_mass: float
    delta_mass: float

    baseline_fraction_active: float
    poke_fraction_active: float
    delta_fraction_active: float

    baseline_tiers: Dict[str, int]
    poke_tiers: Dict[str, int]

    top_k_overlap: float

    # Structural interpretation
    recruitment_level: str
    identity_stability: str


# ------------------------------------------------------------
# Builder
# ------------------------------------------------------------

class RecruitmentSignatureBuilder:
    def __init__(self, top_k: int = 10):
        self._top_k = top_k

    def build(
        self,
        *,
        episode_id: int,
        region: str,
        baseline_dump: Path,
        post_dump: Path,
        episode_bounds: Dict[str, int],
        salience_summary: Dict[str, float],
        urgency_summary: Dict[str, float],
        value_summary: Dict[str, float],
        decision_summary: Dict | None,
    ) -> RecruitmentSignature:

        base = load_dump(baseline_dump)
        poke = load_dump(post_dump)

        base_asm = base["assemblies"]
        poke_asm = poke["assemblies"]

        base_mass = total_mass(base_asm)
        poke_mass = total_mass(poke_asm)

        base_frac = fraction_active(base_asm)
        poke_frac = fraction_active(poke_asm)

        base_top = top_k_assemblies(base_asm, self._top_k)
        poke_top = top_k_assemblies(poke_asm, self._top_k)

        overlap = overlap_fraction(base_top, poke_top)

        # --------------------------------------------------
        # Structural recruitment interpretation
        # --------------------------------------------------

        if poke_frac >= 0.95 and base_frac < 0.95:
            recruitment_level = "full"
        elif poke_frac > base_frac and poke_frac >= 0.3:
            recruitment_level = "partial"
        elif poke_frac < base_frac:
            recruitment_level = "suppression"
        else:
            recruitment_level = "none"

        # --------------------------------------------------
        # Identity stability interpretation
        # --------------------------------------------------

        if overlap >= 0.8:
            identity_stability = "stable"
        elif overlap >= 0.3:
            identity_stability = "shifted"
        else:
            identity_stability = "reorganized"

        return RecruitmentSignature(
            episode_id=episode_id,
            region=region,

            episode_start_step=episode_bounds["start_step"],
            episode_end_step=episode_bounds["end_step"],

            salience_summary=salience_summary,
            urgency_summary=urgency_summary,
            value_summary=value_summary,
            decision_summary=decision_summary,

            baseline_step=base["step"],
            poke_step=poke["step"],

            baseline_mass=base_mass,
            poke_mass=poke_mass,
            delta_mass=poke_mass - base_mass,

            baseline_fraction_active=base_frac,
            poke_fraction_active=poke_frac,
            delta_fraction_active=poke_frac - base_frac,

            baseline_tiers=tier_counts(base_asm),
            poke_tiers=tier_counts(poke_asm),

            top_k_overlap=overlap,

            recruitment_level=recruitment_level,
            identity_stability=identity_stability,
        )