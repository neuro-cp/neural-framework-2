from learning.session.learning_session import LearningSession


def test_learning_session_idempotent():
    session = LearningSession(replay_id="r1")

    a = session.run(inputs=[])
    b = session.run(inputs=[])

    assert a == b
