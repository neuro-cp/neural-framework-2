from __future__ import annotations

from typing import Dict

from engine.salience.salience_policy import SaliencePolicy


class SalienceField:
    """
    Ephemeral salience signal field.

    PURPOSE:
    - Store short-lived attentional / novelty / urgency signals
    - Apply continuous decay
    - Provide fast read access for runtime gain modulation

    DESIGN GUARANTEES:
    - No learning
    - No persistence
    - No cognition
    - No decision authority
    - No source ownership
    """

    def __init__(
        self,
        *,
        decay_tau: float = 3.0,
        max_value: float = 1.0,
    ):
        self.decay_tau = float(decay_tau)
        self.max_value = float(max_value)

        # assembly_id -> salience value
        self._values: Dict[str, float] = {}

        # Optional structural sparsity gate (off by default)
        self._sparsity_gate = None


    # --------------------------------------------------
    # Injection (single write path)
    # --------------------------------------------------

    def inject(self, assembly_id: str, delta: float) -> None:
        """
        Inject salience delta for a single assembly.

        This method assumes:
        - Policy has already been checked upstream
        - Delta has already been source-clipped
        """
        if not SaliencePolicy.allow_update(assembly_id, delta):
            return

        current = self._values.get(assembly_id, 0.0)
        updated = SaliencePolicy.clamp(current + float(delta))
        self._values[assembly_id] = min(updated, self.max_value)

    # --------------------------------------------------
    # Read access
    # --------------------------------------------------

    def get(self, assembly_id: str) -> float:
        if self._sparsity_gate is not None:
            if not self._sparsity_gate.allows(assembly_id):
                return 0.0

        return float(self._values.get(assembly_id, 0.0))

    # --------------------------------------------------
    # Structural sparsity (optional)
    # --------------------------------------------------

    def routing_bias(self, assembly_id: str) -> float:
        """
        Read-only routing preference derived from salience.

        PURPOSE:
        - Bias routing selection when multiple equivalent routes exist
        - Must NOT scale activity, gain, or firing
        - Must NOT force selection
        - Fail-open if salience or sparsity gate blocks

        Returns:
            float in [0.0, 1.0]
        """
        if self._sparsity_gate is not None:
            if not self._sparsity_gate.allows(assembly_id):
                return 0.0

        return float(self._values.get(assembly_id, 0.0))


    def attach_sparsity_gate(self, gate) -> None:
        """
        Attach a SalienceSparsityGate.

        - Gate must implement: allows(assembly_id) -> bool
        - If not attached, salience behaves exactly as before
        """
        self._sparsity_gate = gate


    # --------------------------------------------------
    # Dynamics
    # --------------------------------------------------

    def step(self, dt: float) -> None:
        """
        Apply continuous exponential decay.
        """
        if self.decay_tau <= 0.0:
            self._values.clear()
            return

        decay = float(dt) / self.decay_tau

        for key in list(self._values.keys()):
            v = self._values[key] * (1.0 - decay)
            if v <= 1e-6:
                del self._values[key]
            else:
                self._values[key] = v

    # --------------------------------------------------
    # Diagnostics
    # --------------------------------------------------

    def dump(self) -> Dict[str, float]:
        return dict(self._values)
