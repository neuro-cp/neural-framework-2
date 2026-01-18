# engine/salience/sources/surprise_source.py
from __future__ import annotations

from typing import Dict

from engine.salience.sources.salience_source import BaseSalienceSource


class SurpriseSource(BaseSalienceSource):
    """
    Surprise-based salience source.

    PURPOSE:
    - Detect unexpected changes in activity
    - Highlight novelty / prediction error
    - Bias attention without steering decisions

    BIOLOGICAL ANALOG:
    - Cortical prediction error
    - Mismatch / novelty detection (pre-dopaminergic)

    DESIGN:
    - Stateless
    - Symmetric (no valence)
    - Conservative magnitude
    """

    name = "surprise"

    # Surprise should be weaker than competition
    max_delta = 0.02

    # Minimum deviation required to count as surprise
    EPSILON = 1e-3

    def _compute_delta(
        self, observation: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Compute salience deltas based on unexpected deviation.

        Expected observation format:
            {
                channel_id: deviation_from_expected (signed or abs)
            }

        Interpretation:
        - Large magnitude deviation → surprise
        - Sign is ignored (surprise is unsigned)
        """

        deltas: Dict[str, float] = {}

        for channel_id, deviation in observation.items():
            try:
                mag = abs(float(deviation))
            except Exception:
                continue

            if mag < self.EPSILON:
                continue

            # Linear surprise → small positive salience
            deltas[channel_id] = mag

        return deltas
