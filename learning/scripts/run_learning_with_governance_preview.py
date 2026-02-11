# learning/scripts/run_learning_with_governance_preview.py

from learning.session._governance_flow import run_governance_chain
from learning.schemas.learning_proposal import LearningProposal
from learning.schemas.learning_delta import LearningDelta


class DummySurface:
    coherence = 0.0
    entropy = 0.0
    momentum = 0.0
    escalation = 0.0


def build_demo_proposal(delta_count: int):
    deltas = [
        LearningDelta(target=f"demo_{i}", value=1.0)
        for i in range(delta_count)
    ]
    return LearningProposal(
        proposal_id="demo",
        deltas=deltas,
        bounded=True,
        replay_consistent=True,
    )


if __name__ == "__main__":
    proposals = [build_demo_proposal(delta_count=3)]
    surface = DummySurface()

    try:
        record = run_governance_chain(proposals, surface)

        print("=== GOVERNANCE PREVIEW ===")
        print(f"Fragility Index: {record.fragility_index}")
        print(f"Allowed Adjustment: {record.envelope.allowed_adjustment}")
        print(f"Applied Adjustment: {record.application.applied_adjustment}")
        print("Decision: APPROVED")

    except AssertionError:
        print("Decision: REJECTED")