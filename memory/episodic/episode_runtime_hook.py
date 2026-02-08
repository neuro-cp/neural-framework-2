from __future__ import annotations

from typing import Optional

from memory.episodic.episode_boundary_policy import EpisodeBoundaryPolicy
from memory.episodic.episode_tracker import EpisodeTracker


class EpisodeRuntimeHook:
    """
    Runtime-facing episodic hook (read-only bridge).

    Responsibilities:
    - Observe runtime snapshots
    - Evaluate episodic boundary policy
    - Delegate lifecycle actions to EpisodeTracker

    Non-responsibilities:
    - No authority
    - No resets
    - No learning
    - No runtime mutation
    """

    def __init__(
        self,
        *,
        tracker: EpisodeTracker,
        boundary_policy: Optional[EpisodeBoundaryPolicy] = None,
    ) -> None:
        self.tracker = tracker
        self.boundary_policy = boundary_policy or EpisodeBoundaryPolicy()

    def step(
        self,
        *,
        step: int,
        decision_event: bool,
        working_state_active: Optional[bool] = None,
        context_shift: bool = False,
        time: Optional[float] = None,  # reserved for Phase 6+
    ) -> None:
        """
        Called once per runtime step.

        Observes runtime state and delegates episodic
        lifecycle transitions when boundary conditions
        are declared by policy.
        """

        # --------------------------------------------------
        # Ensure an episode exists
        # --------------------------------------------------
        if not self.tracker.has_active_episode():
            self.tracker.start_episode(
                step=step,
                reason="initial",
            )
            return

        # --------------------------------------------------
        # Boundary evaluation (pure observation)
        # --------------------------------------------------
        should_close = self.boundary_policy.should_close_episode(
            episode_start_step=self.tracker.active_start_step,
            current_step=step,
            decision_event=decision_event,
            working_state_active=working_state_active,
        )

        if should_close:
            self.tracker.close_episode(
                step=step,
                reason="boundary",
            )

        # --------------------------------------------------
        # Open next episode if one just closed
        # --------------------------------------------------
        if not self.tracker.has_active_episode():
            self.tracker.start_episode(
                step=step,
                reason="boundary",
            )
