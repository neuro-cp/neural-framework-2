from __future__ import annotations

from typing import Iterator, Callable, Optional, Dict, Any, List

from memory.episodic.episode_structure import Episode
from memory.episodic.episode_trace import EpisodeTrace


class EpisodeReplay:
    """
    Read-only episodic replay utility.

    Consumes:
    - a snapshot list of Episodes (structure)
    - an EpisodeTrace (events)

    NO authority, NO mutation, NO runtime coupling.
    """

    def __init__(
        self,
        *,
        episodes: List[Episode],
        trace: EpisodeTrace,
    ) -> None:
        # Snapshot to prevent external mutation
        self._episodes = list(episodes)
        self._trace = trace

    # --------------------------------------------------
    # Core accessors
    # --------------------------------------------------

    def episodes(self) -> List[Episode]:
        return list(self._episodes)

    def closed_episodes(self) -> List[Episode]:
        return [ep for ep in self._episodes if ep.closed]

    def active_episode(self) -> Optional[Episode]:
        for ep in reversed(self._episodes):
            if not ep.closed:
                return ep
        return None

    # --------------------------------------------------
    # Iterators
    # --------------------------------------------------

    def iter_episodes(self) -> Iterator[Episode]:
        yield from self._episodes

    def iter_closed(self) -> Iterator[Episode]:
        for ep in self._episodes:
            if ep.closed:
                yield ep

    # --------------------------------------------------
    # Decision-focused views
    # --------------------------------------------------

    def episodes_with_decisions(self) -> List[Episode]:
        return [ep for ep in self._episodes if ep.has_decision()]

    def iter_decision_events(self) -> Iterator[Dict[str, Any]]:
        for ep in self._episodes:
            for d in ep.decisions:
                yield {
                    "episode_id": ep.episode_id,
                    "episode_start_step": ep.start_step,
                    "episode_start_time": ep.start_time,
                    **d,
                }

    # --------------------------------------------------
    # Trace alignment helpers
    # --------------------------------------------------

    def trace_for_episode(self, episode_id: int):
        return [r for r in self._trace.records() if r.episode_id == episode_id]

    def replay(self):
        for ep in self.closed_episodes():
            yield ep, self.trace_for_episode(ep.episode_id)

    # --------------------------------------------------
    # Summaries
    # --------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        closed = [ep for ep in self._episodes if ep.closed]

        return {
            "total_episodes": len(self._episodes),
            "closed_episodes": len(closed),
            "episodes_with_decisions": sum(1 for ep in self._episodes if ep.has_decision()),
            "total_decisions": sum(len(ep.decisions) for ep in self._episodes),
            "mean_duration_steps": self._mean(
                [ep.duration_steps for ep in closed if ep.duration_steps is not None]
            ),
            "mean_duration_time": self._mean(
                [ep.duration_time for ep in closed if ep.duration_time is not None]
            ),
        }

    def project(
        self,
        fn: Callable[[Episode], Any],
        *,
        closed_only: bool = True,
    ) -> List[Any]:
        eps = self.closed_episodes() if closed_only else self.episodes()
        return [fn(ep) for ep in eps]

    @staticmethod
    def _mean(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return sum(values) / len(values)
