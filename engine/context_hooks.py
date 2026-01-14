# engine/context_hooks.py
from __future__ import annotations

from typing import Iterable, Optional

from engine.population_model import PopulationModel
from engine.runtime_context import RuntimeContext, GLOBAL_CONTEXT_KEY


class PFCContextHook:
    """
    PFC → RuntimeContext interface.

    FUNCTIONAL ROLE:
    - Interpret sustained PFC activity as task-relevant context
    - Translate activity into transient, gain-only bias
    - Provide working-memory-like influence across timesteps

    HARD GUARANTEES:
    - Gain-only (never writes activity or parameters)
    - Soft-thresholded (no brittle all-or-none gating)
    - Stateless (no memory inside the hook)
    - Decay handled exclusively by RuntimeContext

    IMPORTANT SEMANTIC FIX:
    - By default, writes into GLOBAL_CONTEXT_KEY so downstream regions
      (e.g., striatum) can consume the signal without requiring assembly-id
      alignment across regions.
    """

    def __init__(
        self,
        activity_threshold: float = 0.02,
        injection_gain: float = 0.05,
        target_domain: str = "global",
        max_inject_per_step: Optional[float] = None,
        inject_to_global: bool = True,
    ):
        # Threshold above baseline cortical noise
        self.activity_threshold = float(activity_threshold)

        # Linear gain applied to suprathreshold activity
        self.injection_gain = float(injection_gain)

        # Explicit domain this hook writes into
        self.target_domain = str(target_domain)

        # Optional safety cap (None = uncapped)
        self.max_inject_per_step = (
            None if max_inject_per_step is None else float(max_inject_per_step)
        )

        # If True, inject into GLOBAL_CONTEXT_KEY instead of per-assembly IDs
        self.inject_to_global = bool(inject_to_global)

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def apply(
        self,
        pfc_assemblies: Iterable[PopulationModel],
        context: RuntimeContext,
        domain: Optional[str] = None,
    ) -> None:
        """
        Inspect PFC assemblies and inject context bias for those
        exceeding the activity threshold.

        NOTES:
        - Soft gating: (activity - threshold)
        - Context accumulation + decay handled by RuntimeContext
        - Default injection target is GLOBAL_CONTEXT_KEY to avoid silent
          consumer mismatch (PFC assembly ids != striatum assembly ids).
        """
        dom = self.target_domain if domain is None else str(domain)

        for p in pfc_assemblies:
            activity = p.output()

            # Soft thresholding
            excess = activity - self.activity_threshold
            if excess <= 0.0:
                continue

            amount = self.injection_gain * excess

            if self.max_inject_per_step is not None:
                amount = min(amount, self.max_inject_per_step)

            target = GLOBAL_CONTEXT_KEY if self.inject_to_global else p.assembly_id

            context.inject(
                assembly_id=target,
                amount=amount,
                domain=dom,
            )
