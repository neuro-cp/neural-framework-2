from __future__ import annotations

from engine.salience.salience_field import SalienceField
from engine.salience.salience_policy import SaliencePolicy


def test_basic_injection_and_decay() -> None:
    """
    Salience should:
    - Accept valid updates
    - Accumulate modestly
    - Decay over time
    """

    field = SalienceField(decay_tau=2.0)

    # Initial state
    assert field.get("D1") == 0.0

    # Valid injection
    assert SaliencePolicy.allow_update("D1", 0.02)
    field.inject("D1", 0.02)

    v1 = field.get("D1")
    assert 0.019 <= v1 <= 0.021

    # Step forward → decay
    field.step(dt=1.0)
    v2 = field.get("D1")

    assert v2 < v1
    assert v2 > 0.0


def test_reject_oversized_impulse() -> None:
    """
    Oversized salience impulses must be rejected.
    """

    field = SalienceField()

    allowed = SaliencePolicy.allow_update("D1", 0.5)
    assert allowed is False

    # Even if someone tries anyway, clamp must hold
    field.inject("D1", 0.5)
    v = field.get("D1")

    assert abs(v) <= SaliencePolicy.MAX_ABS_SALIENCE


def test_reject_noise() -> None:
    """
    Near-zero noise should be ignored.
    """

    field = SalienceField()

    allowed = SaliencePolicy.allow_update("D1", 1e-9)
    assert allowed is False

    field.inject("D1", 1e-9)
    assert field.get("D1") == 0.0


def test_multiple_channels_independent() -> None:
    """
    Salience channels must not leak into each other.
    """

    field = SalienceField()

    field.inject("D1", 0.02)
    field.inject("D2", -0.01)

    assert field.get("D1") > 0.0
    assert field.get("D2") < 0.0
    assert abs(field.get("D1") - field.get("D2")) > 0.01


def test_clear() -> None:
    """
    Clear should wipe all salience clean.
    """

    field = SalienceField()
    field.inject("D1", 0.03)
    field.inject("D2", -0.02)

    field.clear()

    assert field.get("D1") == 0.0
    assert field.get("D2") == 0.0
