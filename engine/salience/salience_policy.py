from __future__ import annotations


class SaliencePolicy:
    """
    Salience update policy.

    PURPOSE:
    - Gate which salience updates are allowed
    - Enforce bounded, biologically plausible influence
    - Prevent salience from becoming a covert decision system

    DESIGN PRINCIPLES:
    - Stateless
    - Deterministic
    - Conservative by default
    """

    # ------------------------------------------------------------
    # Hard limits (global safety rails)
    # ------------------------------------------------------------

    MAX_DELTA = 0.05          # single injection cap
    MAX_ABS_SALIENCE = 1.0   # should match SalienceField.max_salience
    EPSILON = 1e-6

    # ------------------------------------------------------------
    # Allow rules
    # ------------------------------------------------------------

    @classmethod
    def allow_update(cls, channel_id: str, delta: float) -> bool:
        """
        Decide whether a salience update is allowed.

        Rejects:
        - Near-zero noise
        - Excessively large impulses
        """
        if abs(delta) < cls.EPSILON:
            return False

        if abs(delta) > cls.MAX_DELTA:
            return False

        if not channel_id:
            return False

        return True

    # ------------------------------------------------------------
    # Clamping
    # ------------------------------------------------------------

    @classmethod
    def clamp(cls, value: float) -> float:
        """
        Clamp salience to safe bounds.
        """
        if value > cls.MAX_ABS_SALIENCE:
            return cls.MAX_ABS_SALIENCE
        if value < -cls.MAX_ABS_SALIENCE:
            return -cls.MAX_ABS_SALIENCE
        return value
