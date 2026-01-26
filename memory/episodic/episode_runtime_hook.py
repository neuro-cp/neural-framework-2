from __future__ import annotations

from typing import Optional

from memory.episodic.episode_policy import (
    EpisodePolicy,
    EpisodeBoundarySignal,
)
from memory.episodic.episode_tracker import EpisodeTracker


class EpisodeRuntimeHook:
    """
    Runtime-facing episodic hook.

    Responsibilities:
    - Observe runtime state (read-only)
    - Query EpisodePolicy
    - Forward boundary signals to EpisodeTracker

    Non-responsibilities:
    - No resets
    - No memory deletion
    - No decision authority
    - No latch interaction
    """

    def __init__(
        self,
        *,
        policy: EpisodePolicy,
        tracker: EpisodeTracker,
    ) -> None:
        self.policy = policy
        self.tracker = tracker

    # --------------------------------------------------
    # Runtime observation hook
    # --------------------------------------------------
    def step(
        self,
        *,
        step: int,
        decision_made: bool,
        working_state_active: bool,
        context_shift: bool = False,
    ) -> Optional[EpisodeBoundarySignal]:
        """
        Called once per runtime step.

        Returns the boundary signal for observability/testing,
        but does NOT act on it directly.
        """

        signal = self.policy.evaluate(
            step=step,
            active_episode_start_step=self.tracker.active_start_step,
            decision_made=decision_made,
            working_state_active=working_state_active,
            context_shift=context_shift,
        )

        if signal is None:
            return None

        # --------------------------------------------------
        # Forward advisory signals to tracker
        # --------------------------------------------------
        if signal.close_active:
            self.tracker.close_episode(
                step=step,
                reason=signal.reason,
            )

        if signal.start_new:
            self.tracker.start_episode(
                step=step,
                reason=signal.reason,
            )

        return signal
