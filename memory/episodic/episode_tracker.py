from __future__ import annotations

from typing import Optional, List, Dict

from memory.episodic.episode_structure import Episode
from memory.episodic.episode_trace import EpisodeTrace


class EpisodeTracker:
    """
    Passive episodic boundary tracker.

    Responsibilities:
    - Create episodes
    - Annotate decisions
    - Close episodes
    - Maintain episode history
    - Emit trace records

    Non-responsibilities:
    - No control
    - No gating
    - No learning
    - No reset authority
    """

    def __init__(self, trace: EpisodeTrace) -> None:
        self._trace = trace
        self._episodes: List[Episode] = []
        self._active: Optional[Episode] = None
        self._next_id: int = 0

    # --------------------------------------------------
    # Episode lifecycle
    # --------------------------------------------------

    def start_episode(
        self,
        *,
        step: int,
        tags: Optional[Dict] = None,
        reason: str = "explicit_start",
    ) -> Episode:
        """
        Start a new episode.

        Closes any currently active episode first.
        """
        if self._active is not None:
            self.close_episode(step=step, reason="implicit_close")

        ep = Episode(
            episode_id=self._next_id,
            start_step=step,
            start_time=0.0,  # Placeholder; time wiring is Phase 6+
            tags=tags or {},
        )

        self._trace.record_start(
            episode_id=ep.episode_id,
            step=step,
            reason=reason,
        )

        self._next_id += 1
        self._episodes.append(ep)
        self._active = ep
        return ep

    def mark_decision(
        self,
        *,
        step: int,
        winner: str,
    ) -> None:
        """
        Annotate the active episode with a decision.
        """
        if self._active is None:
            # Decision without an episode → create implicit episode
            self.start_episode(
                step=step,
                reason="implicit_decision_episode",
            )

        self._active.mark_decision(
            step=step,
            time=0.0,  # Placeholder
            winner=winner,
        )

    def close_episode(
        self,
        *,
        step: int,
        reason: str = "explicit_close",
    ) -> None:
        """
        Close the currently active episode.
        """
        if self._active is None:
            return

        ep = self._active
        ep.close(step=step, time=0.0)

        self._trace.record_close(
            episode_id=ep.episode_id,
            step=step,
            start_step=ep.start_step,
            reason=reason,
        )

        self._active = None

    # --------------------------------------------------
    # Introspection
    # --------------------------------------------------

    def active_episode(self) -> Optional[Episode]:
        return self._active

    def active_start_step(self) -> Optional[int]:
        return self._active.start_step if self._active else None

    def all_episodes(self) -> List[Episode]:
        return list(self._episodes)

    def last_episode(self) -> Optional[Episode]:
        return self._episodes[-1] if self._episodes else None

    def episode_count(self) -> int:
        return len(self._episodes)

    # --------------------------------------------------
    # Diagnostics / safety
    # --------------------------------------------------

    def sanity_check(self) -> None:
        """
        Internal consistency checks (debug only).
        """
        for ep in self._episodes:
            if ep.closed:
                assert ep.end_step is not None

            if ep.has_decision():
                assert ep.decision_step is not None
                assert ep.decision_winner is not None
