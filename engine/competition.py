from __future__ import annotations

from typing import Dict, List, Optional


class CompetitionKernel:
    """
    Channel-aware competition kernel.

    PURPOSE:
    - Induce lateral competition among assemblies
    - Support competition across semantic channels (e.g. D1 vs D2)
    - Produce stable dominance signals for downstream gating

    DESIGN GUARANTEES:
    - No learning
    - No oscillations
    - No hard winner-take-all
    - Fully bounded
    - Deterministic by default
    """

    def __init__(
        self,
        inhibition_strength: float = 0.4,
        persistence_gain: float = 0.2,
        dominance_tau: float = 0.5,
        min_activity: float = 0.0,
        dominance_floor: float = 1e-6,
        contrast_gain: float = 1.0,
        epsilon_bias: float = 0.0,
        channel_key: str = "subpopulation",
    ):
        self.inhibition_strength = inhibition_strength
        self.persistence_gain = persistence_gain
        self.dominance_tau = dominance_tau
        self.min_activity = min_activity
        self.dominance_floor = dominance_floor
        self.contrast_gain = contrast_gain
        self.epsilon_bias = epsilon_bias
        self.channel_key = channel_key

        # Smoothed dominance per semantic channel
        self._dominance: Dict[str, float] = {}

        # Diagnostics (public, read-only by convention)
        self.last_global_dominance: float = 0.0
        self.last_winner_channel: Optional[str] = None
        self.last_dominance_map: Dict[str, float] = {}

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def apply(
        self,
        assemblies: List,
        dt: float,
        external_gain: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Apply competition across semantic channels.

        external_gain:
            Optional per-assembly multiplicative bias applied
            ONLY to effective activity during competition.
            This does NOT modify state, weights, or parameters.
        """

        if not assemblies:
            self._clear_outputs()
            return 0.0

        # --------------------------------------------------
        # Step 1: group assemblies into semantic channels
        # --------------------------------------------------
        channels: Dict[str, List] = {}

        for a in assemblies:
            ch = getattr(a, self.channel_key, None) or "default"
            channels.setdefault(ch, []).append(a)

        # --------------------------------------------------
        # Step 2: compute channel outputs (ephemeral bias)
        # --------------------------------------------------
        channel_output: Dict[str, float] = {}

        for ch, plist in channels.items():
            total = 0.0
            for p in plist:
                gain = 1.0
                if external_gain is not None:
                    gain = external_gain.get(p.assembly_id, 1.0)

                val = max(p.output(), self.min_activity)
                total += val * gain

            channel_output[ch] = max(total, self.dominance_floor)

        total_output = sum(channel_output.values())
        if total_output <= 0.0:
            self._clear_outputs()
            return 0.0

        # --------------------------------------------------
        # Step 3: instantaneous normalized dominance
        # --------------------------------------------------
        inst = {ch: v / total_output for ch, v in channel_output.items()}

        # Optional deterministic symmetry breaker
        if self.epsilon_bias > 0.0:
            for i, ch in enumerate(sorted(inst)):
                inst[ch] += self.epsilon_bias * (i + 1)

        # Renormalize
        norm = sum(inst.values())
        inst = {ch: v / norm for ch, v in inst.items()}

        # --------------------------------------------------
        # Step 4: smooth dominance (pure inertia, no learning)
        # --------------------------------------------------
        for ch, d in inst.items():
            prev = self._dominance.get(ch, d)
            self._dominance[ch] = prev + (dt / self.dominance_tau) * (d - prev)

        # --------------------------------------------------
        # Step 5: channel-level lateral inhibition
        # --------------------------------------------------
        mean_dom = sum(self._dominance.values()) / len(self._dominance)

        for ch, plist in channels.items():
            own = self._dominance.get(ch, 0.0)

            suppress = 0.0
            for och, od in self._dominance.items():
                if och != ch:
                    suppress += max(od - own, 0.0)

            inhibition = self.inhibition_strength * suppress
            resistance = self.persistence_gain * max(
                self.contrast_gain * (own - mean_dom), 0.0
            )

            net = max(inhibition - resistance, 0.0)

            for p in plist:
                p.input -= net / max(len(plist), 1)

        # --------------------------------------------------
        # Step 6: expose dominance diagnostics
        # --------------------------------------------------
        winner_ch = max(self._dominance, key=self._dominance.get)
        winner_val = self._dominance[winner_ch]

        self.last_global_dominance = winner_val
        self.last_winner_channel = winner_ch
        self.last_dominance_map = dict(self._dominance)

        return winner_val

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _clear_outputs(self) -> None:
        self.last_global_dominance = 0.0
        self.last_winner_channel = None
        self.last_dominance_map = {}
