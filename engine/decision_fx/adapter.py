from __future__ import annotations

from typing import Any, Dict, Optional

from engine.decision_fx.decision_policy import DecisionPolicy
from engine.decision_fx.decision_router import DecisionRouter
from engine.decision_fx.decision_effects import DecisionEffects
from engine.decision_fx.runtime_hook import DecisionRuntimeHook
from engine.decision_fx.decision_trace import DecisionTrace


class DecisionFXAdapter:
    """
    Facade / adapter for the Decision FX subsystem.

    PURPOSE:
    - Provide a single runtime-facing entry point
    - Encapsulate policy, routing, effects, and tracing
    - Guarantee read-only, advisory behavior

    HARD GUARANTEES:
    - No learning
    - No stateful dynamics
    - No authority over decisions
    - Safe to disable at runtime
    """

    def __init__(self, enable_trace: bool = True):
        self.policy = DecisionPolicy()
        self.router = DecisionRouter()
        self.effects = DecisionEffects()
        self.hook = DecisionRuntimeHook()

        self.enable_trace = bool(enable_trace)
        self._trace: Optional[DecisionTrace] = DecisionTrace() if self.enable_trace else None

    # --------------------------------------------------
    # Runtime-facing API (SINGLE CALL)
    # --------------------------------------------------

    def apply(
        self,
        *,
        decision_state: Dict[str, Any],
        dominance: Dict[str, float],
    ) -> None:
        """
        Consume a committed decision and compute advisory effects.

        This method is PURE with respect to runtime dynamics.
        """

        policy = self.policy.compute(
            decision_state=decision_state,
            dominance=dominance,
        )

        routed = self.router.route(policy)

        # Ensure required keys exist for DecisionEffects.apply(**bundle)
        routed.setdefault("region_gain", {})
        routed.setdefault("suppress_channels", {})
        routed.setdefault("lock_action", False)

        effects = self.effects.apply(**routed)

        self.hook.ingest(effects)

        if self._trace is not None:
            self._trace.record(
                step=int(decision_state.get("step", -1)),
                time=float(decision_state.get("time", 0.0)),
                winner=decision_state.get("winner"),
                dominance=dict(dominance or {}),
                delta=float(decision_state.get("delta_dominance", 0.0)),
                relief=float(decision_state.get("relief", 0.0)),
                bias=policy.get("bias_snapshot"),
                effects=effects,
                runtime_hook=self.hook.snapshot(),
            )

    # --------------------------------------------------
    # Read-only exposure
    # --------------------------------------------------

    def get_thalamic_gain_modifier(self) -> float:
        # Runtime expects a numeric modifier, not a bound method.
        return float(self.hook.thalamic_gain())

    # Optional compatibility alias
    def get_thalamic_gain(self) -> float:
        return float(self.hook.thalamic_gain())

    def dump(self) -> Dict[str, Any]:
        return self.hook.snapshot()
