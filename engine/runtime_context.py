# engine/runtime_context.py
from __future__ import annotations

from typing import Dict, Optional


GLOBAL_CONTEXT_KEY = "__global__"


class RuntimeContext:
    """
    Ephemeral runtime context buffer with domain scoping.

    PURPOSE:
    - Provide short-lived, gain-only bias signals
    - Support PFC-style working context without learning
    - Safe expansion point for attention/task sets/motivation

    CORE GUARANTEES:
    - No learning
    - No plasticity
    - Neutral when unused
    - Deterministic decay
    """

    def __init__(self, decay_tau: float = 5.0, epsilon: float = 1e-6):
        self.decay_tau = float(decay_tau)
        self.epsilon = float(epsilon)

        # key (assembly_id or GLOBAL_CONTEXT_KEY) -> domain -> scalar bias
        self._context: Dict[str, Dict[str, float]] = {}

    # ============================================================
    # Query
    # ============================================================

    def get_gain(
        self,
        assembly_id: str,
        domain: str = "global",
        *,
        allow_global_fallback: bool = True,
    ) -> float:
        """
        Return multiplicative gain for an assembly in a given domain.

        Resolution order:
        1) Exact assembly match
        2) Global context fallback (if allow_global_fallback=True)
        3) Neutral gain (1.0)
        """
        domains = self._context.get(assembly_id)

        if (not domains) and allow_global_fallback:
            domains = self._context.get(GLOBAL_CONTEXT_KEY)

        if not domains:
            return 1.0

        return 1.0 + float(domains.get(domain, 0.0))

    def get_bias(
        self,
        assembly_id: str,
        domain: str = "global",
        *,
        allow_global_fallback: bool = True,
    ) -> float:
        """
        Return additive bias (not +1 gain), useful for debugging.
        """
        domains = self._context.get(assembly_id)

        if (not domains) and allow_global_fallback:
            domains = self._context.get(GLOBAL_CONTEXT_KEY)

        if not domains:
            return 0.0

        return float(domains.get(domain, 0.0))

    # ============================================================
    # Injection
    # ============================================================

    def inject(
        self,
        assembly_id: str,
        amount: float,
        domain: str = "global",
    ) -> None:
        """
        Inject transient context bias for a specific assembly_id.

        DESIGN:
        - Accumulative
        - Gain-only (bias later interpreted as multiplicative gain)
        - No clipping or normalization
        """
        if amount == 0.0:
            return

        aid = str(assembly_id)
        domains = self._context.setdefault(aid, {})
        domains[domain] = domains.get(domain, 0.0) + float(amount)

    def inject_global(self, amount: float, domain: str = "global") -> None:
        """
        Inject a global context bias (fallback target for all assemblies).
        """
        self.inject(GLOBAL_CONTEXT_KEY, amount, domain=domain)

    def set(
        self,
        assembly_id: str,
        value: float,
        domain: str = "global",
    ) -> None:
        """
        Set (overwrite) a context bias value for an assembly/domain.
        Useful for deterministic tests.
        """
        aid = str(assembly_id)
        domains = self._context.setdefault(aid, {})
        domains[domain] = float(value)

    # ============================================================
    # Dynamics
    # ============================================================

    def step(self, dt: float) -> None:
        """
        Exponential-like decay of all context traces.
        Automatic cleanup once values fall below epsilon.
        """
        if not self._context:
            return

        tau = max(self.decay_tau, 1e-9)
        decay = float(dt) / tau

        dead_assemblies = []

        for aid, domains in list(self._context.items()):
            dead_domains = []

            for domain, value in list(domains.items()):
                new_value = value * (1.0 - decay)

                if abs(new_value) < self.epsilon:
                    dead_domains.append(domain)
                else:
                    domains[domain] = new_value

            for domain in dead_domains:
                del domains[domain]

            if not domains:
                dead_assemblies.append(aid)

        for aid in dead_assemblies:
            del self._context[aid]

    # ============================================================
    # Maintenance
    # ============================================================

    def clear(self) -> None:
        self._context.clear()

    def clear_domain(self, domain: str) -> None:
        """
        Remove a domain from all assemblies (including global).
        """
        if not self._context:
            return

        dead_assemblies = []
        for aid, domains in self._context.items():
            if domain in domains:
                del domains[domain]
            if not domains:
                dead_assemblies.append(aid)

        for aid in dead_assemblies:
            del self._context[aid]

    # ============================================================
    # Observability (read-only)
    # ============================================================

    def dump(self) -> Dict[str, Dict[str, float]]:
        return {aid: dict(domains) for aid, domains in self._context.items()}

    def stats(self, *, max_lines: Optional[int] = None) -> str:
        """
        Human-readable summary for debugging and runtime inspection.
        """
        if not self._context:
            return "CONTEXT EMPTY"

        lines = ["CONTEXT:"]
        items = sorted(self._context.items())

        if max_lines is not None:
            items = items[: max(0, int(max_lines))]

        for aid, domains in items:
            doms = " ".join(f"{d}={v:.4f}" for d, v in sorted(domains.items()))
            lines.append(f"  {aid} :: {doms}")

        if max_lines is not None and len(self._context) > len(items):
            lines.append(f"  ... ({len(self._context) - len(items)} more)")

        return "\n".join(lines)
