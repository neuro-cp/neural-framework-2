from __future__ import annotations

from typing import Iterable, Any, Dict, List

from engine.salience.salience_field import SalienceField
from engine.salience.salience_policy import SaliencePolicy
from engine.salience.observations import collect_salience_observations
from engine.salience.sources.salience_source import SalienceSource, SalienceUpdate


class SalienceEngine:
    """
    Salience coordination engine.

    PURPOSE:
    - Collect read-only observations from the runtime
    - Query salience sources for proposed updates
    - Enforce SaliencePolicy
    - Inject approved updates into SalienceField

    DESIGN GUARANTEES:
    - Stateless across steps
    - Deterministic given inputs
    - No runtime mutation
    - No learning
    - No decision authority
    """

    def __init__(self, sources: Iterable[SalienceSource]):
        self.sources: List[SalienceSource] = list(sources)

    # --------------------------------------------------
    # Step
    # --------------------------------------------------

    def step(self, runtime: Any, field: SalienceField) -> None:
        """
        Execute one salience update step.

        ORDER:
        1. Collect observations (read-only)
        2. Ask each source for proposed updates
        3. Apply policy gating
        4. Inject approved updates into field
        """
        observations: Dict[str, Any] = collect_salience_observations(runtime)

        for source in self.sources:
            try:
                updates = source.compute(observations)
            except Exception:
                # Salience sources fail closed
                continue

            for update in updates:
                if not isinstance(update, SalienceUpdate):
                    continue

                if not SaliencePolicy.allow_update(update.channel_id, update.delta):
                    continue

                field.inject(update.channel_id, update.delta)
