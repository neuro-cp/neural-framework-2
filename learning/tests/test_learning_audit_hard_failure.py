import pytest

from learning.session.learning_session import LearningSession


def test_learning_audit_hard_failure_raises():
    session = LearningSession(replay_id="replay_fail")

    inputs = [
        "sem:alpha",
        "sem:alpha",
    ]

    with pytest.raises(AssertionError):
        session.run(inputs=inputs)
