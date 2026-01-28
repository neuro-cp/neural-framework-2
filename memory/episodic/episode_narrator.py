from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Iterable

from memory.episodic.episode_replay import EpisodeReplay
from memory.episodic.episode_structure import Episode
from memory.episodic.episode_trace import EpisodeTraceRecord


# ============================================================
# Narrative event (purely descriptive)
# ============================================================

@dataclass(frozen=True)
class NarrativeEvent:
    """
    Human-readable description of a single episodic event.

    This object is:
    - read-only
    - offline
    - descriptive only
    - non-semantic
    """

    episode_id: int
    step: int
    kind: str           # "start", "decision", "close", "info"
    message: str
    payload: Dict[str, Any]


# ============================================================
# Episode narrator
# ============================================================

class EpisodeNarrator:
    """
    Offline episodic narrator.

    Responsibilities:
    - Consume EpisodeReplay + EpisodeTrace
    - Produce a temporal narrative of what occurred
    - Describe dynamics WITHOUT interpretation or intent

    Non-responsibilities:
    - No learning
    - No inference
    - No runtime access
    - No semantic abstraction
    """

    def narrate(
        self,
        replay: EpisodeReplay,
    ) -> List[NarrativeEvent]:
        """
        Produce a narrative for all closed episodes in the replay.
        """
        narrative: List[NarrativeEvent] = []

        for episode, records in replay.replay():
            narrative.extend(self._narrate_episode(episode, records))

        return narrative

    # --------------------------------------------------
    # Episode-level narration
    # --------------------------------------------------

    def _narrate_episode(
        self,
        episode: Episode,
        records: Iterable[EpisodeTraceRecord],
    ) -> List[NarrativeEvent]:
        events: List[NarrativeEvent] = []

        # --------------------------------------------------
        # Episode header
        # --------------------------------------------------
        events.append(
            NarrativeEvent(
                episode_id=episode.episode_id,
                step=episode.start_step,
                kind="start",
                message=(
                    f"Episode {episode.episode_id} started at step {episode.start_step}."
                ),
                payload={
                    "start_step": episode.start_step,
                    "tags": dict(episode.tags),
                },
            )
        )

        # --------------------------------------------------
        # Trace-driven narration
        # --------------------------------------------------
        for r in records:
            if r.event == "decision":
                events.append(
                    NarrativeEvent(
                        episode_id=episode.episode_id,
                        step=r.step,
                        kind="decision",
                        message=self._format_decision(r),
                        payload=dict(r.payload),
                    )
                )

            elif r.event == "close":
                events.append(
                    NarrativeEvent(
                        episode_id=episode.episode_id,
                        step=r.step,
                        kind="close",
                        message=self._format_close(episode, r),
                        payload=dict(r.payload),
                    )
                )

        # --------------------------------------------------
        # Post-episode summary
        # --------------------------------------------------
        events.append(
            NarrativeEvent(
                episode_id=episode.episode_id,
                step=episode.end_step or episode.start_step,
                kind="info",
                message=self._format_summary(episode),
                payload={
                    "decision_count": episode.decision_count,
                    "duration_steps": episode.duration_steps,
                    "winner": episode.winner,
                    "confidence": episode.confidence,
                },
            )
        )

        return events

    # --------------------------------------------------
    # Formatting helpers (descriptive only)
    # --------------------------------------------------

    def _format_decision(self, record: EpisodeTraceRecord) -> str:
        winner = record.payload.get("winner")
        confidence = record.payload.get("confidence")

        if winner is None:
            return f"Decision event at step {record.step} (no winner recorded)."

        if confidence is not None:
            return (
                f"Decision at step {record.step}: "
                f"winner={winner}, confidence={confidence:.3f}."
            )

        return f"Decision at step {record.step}: winner={winner}."

    def _format_close(self, episode: Episode, record: EpisodeTraceRecord) -> str:
        reason = record.payload.get("reason", "unspecified")
        return (
            f"Episode {episode.episode_id} closed at step {record.step} "
            f"(reason={reason})."
        )

    def _format_summary(self, episode: Episode) -> str:
        if episode.decision_count == 0:
            return (
                f"Episode {episode.episode_id} ended without a decision "
                f"after {episode.duration_steps} steps."
            )

        return (
            f"Episode {episode.episode_id} ended with "
            f"{episode.decision_count} decision(s); "
            f"winner={episode.winner}, confidence={episode.confidence}."
        )
