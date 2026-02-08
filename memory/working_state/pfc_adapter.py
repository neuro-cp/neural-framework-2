from __future__ import annotations

from typing import Any, Dict, Optional

from memory.working_state.working_state import WorkingState
from memory.working_state.working_policy import WorkingPolicy
from memory.working_state.working_hook import WorkingRuntimeHook


class PFCAdapter:
    """
    Adapter / facade for PFC-like Working State.

    PURPOSE:
    - Integrate post-decision working state into the runtime
    - Bridge decision latch → working memory dynamics
    - Expose advisory stabilization signals

    DESIGN GUARANTEES:
    - Read-only with respect to decision arbitration
    - No learning
    - No authority over BG
    - Safe to disable at runtime
    """

    def __init__(
        self,
        *,
        enable: bool = True,
        state: Optional[WorkingState] = None,
        policy: Optional[WorkingPolicy] = None,
    ):
        self.enable = bool(enable)

        self._hook = WorkingRuntimeHook(
            state=state or WorkingState(),
            policy=policy or WorkingPolicy(),
        )

    # --------------------------------------------------
    # Runtime-facing API
    # --------------------------------------------------

    def ingest_decision(self, decision_state: Optional[Dict[str, Any]]) -> None:
        """
        Ingest decision latch output.

        This should be called AFTER the decision latch evaluates,
        and BEFORE dynamics step.
        """
        if not self.enable or decision_state is None:
            return

        self._hook.ingest(decision_state=decision_state)

    def step(self, dt: float) -> None:
        """
        Advance working-state dynamics.
        """
        if not self.enable:
            return

        self._hook.step(dt)

        # --------------------------------------------------
        # Ephemeral external gain modulation (e.g. VTA value)
        # --------------------------------------------------
        if hasattr(self, "_external_gain_fn"):
            try:
                base = self._hook.strength()
                mod = float(self._external_gain_fn(base))
                self._hook.state._strength = max(0.0, mod)
            finally:
                del self._external_gain_fn

    # --------------------------------------------------
    # External modulation hooks (ephemeral)
    # --------------------------------------------------

    def apply_external_gain(self, fn) -> None:
        """
        Apply a temporary external modifier to working-state strength.

        - fn: Callable[[float], float]
        - Applied after internal dynamics
        - Cleared automatically after one step
        """
        if not self.enable:
            return

        self._external_gain_fn = fn

    # --------------------------------------------------
    # Advisory outputs (read-only)
    # --------------------------------------------------

    def is_engaged(self) -> bool:
        return self._hook.is_engaged() if self.enable else False

    def active_channel(self) -> Optional[str]:
        return self._hook.active_channel() if self.enable else None

    def strength(self) -> float:
        return self._hook.strength() if self.enable else 0.0

    def suppressive_bias(self) -> Dict[str, float]:
        """
        Advisory suppressive bias hint.

        Intended for:
        - BG competition dampening
        - attention narrowing
        - post-decision stabilization

        NOT applied automatically.
        """
        return self._hook.suppressive_bias() if self.enable else {}

    # --------------------------------------------------
    # Diagnostics
    # --------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        if not self.enable:
            return {
                "enabled": False,
                "engaged": False,
            }

        snap = self._hook.snapshot()
        snap["enabled"] = True
        return snap

    def reset(self) -> None:
        """
        Hard reset. For testing only.
        """
        self._hook.reset()
