# engine/context_hooks.py
from __future__ import annotations

from typing import List

from engine.population_model import PopulationModel
from engine.runtime_context import RuntimeContext


class PFCContextHook:
    """
    PFC → RuntimeContext interface.

    PURPOSE:
    - Translate sustained PFC activity into transient context bias
    - Provide working-memory-like influence
    - Never override BG or competition

    DESIGN:
    - Activity-thresholded
    - Gain-only
    - Decay handled by RuntimeContext
    """

    def __init__(
        self,
        activity_threshold: float = 0.15,
        injection_gain: float = 0.05,
    ):
        self.activity_threshold = activity_threshold
        self.injection_gain = injection_gain

    def apply(
        self,
        pfc_assemblies: List[PopulationModel],
        context: RuntimeContext,
    ) -> None:
        """
        Inject context bias from active PFC assemblies.
        """
        for p in pfc_assemblies:
            a = p.output()
            if a >= self.activity_threshold:
                context.inject(
                    p.assembly_id,
                    amount=self.injection_gain * a,
                )
