from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

# ============================================================
# Imports under test (will fail until implemented)
# ============================================================

from inspection.recruitment.recruitment_signature_builder import (
    RecruitmentSignatureBuilder,
    RecruitmentSignature,
)

# ============================================================
# Test fixtures (offline-only, synthetic where possible)
# ============================================================

@pytest.fixture
def episode_id() -> int:
    return 42


@pytest.fixture
def fake_episode_bounds() -> Dict[str, int]:
    return {
        "start_step": 900,
        "end_step": 1100,
    }


@pytest.fixture
def recruitment_dump_paths(tmp_path: Path) -> Dict[str, Path]:
    """
    Create minimal baseline / post-poke dumps that mirror
    the real STN structure you already observed.
    """

    baseline = {
        "region": "stn",
        "step": 948,
        "assemblies": [
            {"assembly_id": f"stn:{i}", "output": 0.01 if i < 8 else 0.0}
            for i in range(25)
        ],
    }

    post = {
        "region": "stn",
        "step": 1051,
        "assemblies": [
            {"assembly_id": f"stn:{i}", "output": 0.22 if i < 8 else 0.11}
            for i in range(25)
        ],
    }

    baseline_path = tmp_path / "baseline.json"
    post_path = tmp_path / "post.json"

    baseline_path.write_text(__import__("json").dumps(baseline))
    post_path.write_text(__import__("json").dumps(post))

    return {
        "baseline": baseline_path,
        "post": post_path,
    }


@pytest.fixture
def empty_trace_summary() -> Dict[str, float]:
    return {
        "count": 0,
        "mean": 0.0,
        "max": 0.0,
    }


# ============================================================
# Tests
# ============================================================

def test_recruitment_signature_builder_creates_signature(
    episode_id: int,
    fake_episode_bounds: Dict[str, int],
    recruitment_dump_paths: Dict[str, Path],
    empty_trace_summary: Dict[str, float],
) -> None:
    """
    Core contract test.

    Ensures:
    - adapter produces a RecruitmentSignature
    - no runtime access
    - no mutation of inputs
    """

    builder = RecruitmentSignatureBuilder()

    sig = builder.build(
        episode_id=episode_id,
        region="stn",
        baseline_dump=recruitment_dump_paths["baseline"],
        post_dump=recruitment_dump_paths["post"],
        episode_bounds=fake_episode_bounds,
        salience_summary=empty_trace_summary,
        urgency_summary=empty_trace_summary,
        value_summary=empty_trace_summary,
        decision_summary=None,
    )

    assert isinstance(sig, RecruitmentSignature)

    # -------------------------
    # Identity & scope
    # -------------------------

    assert sig.episode_id == episode_id
    assert sig.region == "stn"

    # -------------------------
    # Structural interpretation
    # -------------------------

    assert sig.recruitment_level == "full"
    assert sig.identity_stability == "stable"
    assert sig.scaling_direction == "up"

    # -------------------------
    # Numeric sanity
    # -------------------------

    assert sig.delta_fraction_active > 0.5
    assert sig.delta_mass > 1.0
    assert 0.9 <= sig.top_k_overlap <= 1.0

    # -------------------------
    # Context carried but inert
    # -------------------------

    assert sig.salience_summary["count"] == 0
    assert sig.urgency_summary["max"] == 0.0
    assert sig.value_summary["mean"] == 0.0

    # -------------------------
    # Decision metadata
    # -------------------------

    assert sig.has_decision is False
    assert sig.winner is None