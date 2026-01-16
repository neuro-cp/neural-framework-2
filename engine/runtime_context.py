from __future__ import annotations

from typing import Dict, Optional
import time
import uuid

from memory.context.context_memory import ContextMemory
from memory.context.context_policy import ContextPolicy
from memory.context.context_trace import ContextTrace


GLOBAL_CONTEXT_KEY = "__global__"


class RuntimeContext:
    """
    Runtime-facing context system.

    PURPOSE:
    - Provide short-lived, gain-style bias signals
    - Support PFC-style working context
    - Gate trace creation into ContextMemory via policy

    CORE GUARANTEES:
    - No learning
    - No plasticity
    - No decision authority
    - Neutral when unused
    """

    def __init__(self, decay_tau: float = 5.0, epsilon: float = 1e-6):
        self.decay_tau = float(decay_tau)
        self.epsilon = float(epsilon)

        # --------------------------------------------------
        # Ephemeral context gains
        # key (assembly_id or GLOBAL_CONTEXT_KEY) -> domain -> bias
        # --------------------------------------------------
        self._context: Dict[str, Dict[str, float]] = {}

        # --------------------------------------------------
        # Context memory (write-only from runtime)
        # --------------------------------------------------
        self._memory = ContextMemory(decay_tau=decay_tau)

        # --------------------------------------------------
        # Trace eligibility bookkeeping
        # --------------------------------------------------
        self._above_since: Dict[str, float] = {}
        self._trace_emitted: Dict[str, bool] = {}

    # ============================================================
    # Query (READ-ONLY)
    # ============================================================

    def get_gain(
        self,
        assembly_id: str,
        domain: str = "global",
        *,
        allow_global_fallback: bool = True,
    ) -> float:
        """
        Return multiplicative gain for an assembly.

        Resolution order:
        1) Assembly-specific domain
        2) Global fallback
        3) Neutral (1.0)
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
        Return additive bias (for diagnostics).
        """
        domains = self._context.get(assembly_id)

        if (not domains) and allow_global_fallback:
            domains = self._context.get(GLOBAL_CONTEXT_KEY)

        if not domains:
            return 0.0

        return float(domains.get(domain, 0.0))

    # ============================================================
    # Injection (WRITE PATH)
    # ============================================================

    def add_gain(
        self,
        assembly_id: str,
        delta: float,
        domain: str = "global",
    ) -> None:
        """
        Inject a context gain for an assembly.

        This is the ONLY supported external write path.
        """
        if not ContextPolicy.allow_update(assembly_id, domain, delta):
            return

        aid = str(assembly_id)
        domains = self._context.setdefault(aid, {})

        current = domains.get(domain, 0.0)
        new_value = ContextPolicy.clamp_gain(current + delta, domain)
        domains[domain] = new_value

        now = time.time()

        # Track trace eligibility
        if new_value >= ContextPolicy.TRACE_GAIN_THRESHOLD:
            if aid not in self._above_since:
                self._above_since[aid] = now
        else:
            self._above_since.pop(aid, None)
            self._trace_emitted.pop(aid, None)

    def add_global_gain(self, delta: float, domain: str = "global") -> None:
        """
        Inject global context gain.
        """
        self.add_gain(GLOBAL_CONTEXT_KEY, delta, domain)

    def set(
        self,
        assembly_id: str,
        value: float,
        domain: str = "global",
    ) -> None:
        """
        Deterministic overwrite (testing only).
        """
        aid = str(assembly_id)
        domains = self._context.setdefault(aid, {})
        domains[domain] = float(value)

    # ============================================================
    # Dynamics
    # ============================================================

    def step(self, dt: float) -> None:
        """
        Advance time.

        Responsibilities:
        - Check trace eligibility
        - Emit at most one trace per sustained episode
        - Decay ephemeral gains
        - Decay context memory
        """
        now = time.time()

        # --- Trace eligibility ---
        for aid, start_t in list(self._above_since.items()):
            if self._trace_emitted.get(aid, False):
                continue

            domains = self._context.get(aid)
            if not domains:
                continue

            gain = domains.get("global", 0.0)
            duration = now - start_t

            if ContextPolicy.should_create_trace(
                gain=gain,
                duration=duration,
                domain="global",
            ):
                trace = ContextTrace(
                    trace_id=str(uuid.uuid4()),
                    context={"assembly": aid},
                    strength=gain,
                )
                self._memory.add(trace)
                self._trace_emitted[aid] = True

        # --- Ephemeral decay ---
        if self._context:
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

        # --- Memory decay ---
        self._memory.step(dt)

    # ============================================================
    # Maintenance
    # ============================================================

    def clear(self) -> None:
        self._context.clear()
        self._above_since.clear()
        self._trace_emitted.clear()

    def clear_domain(self, domain: str) -> None:
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
    # Observability
    # ============================================================

    def dump(self) -> Dict[str, Dict[str, float]]:
        return {aid: dict(domains) for aid, domains in self._context.items()}

    def stats(self) -> Dict[str, float]:
        return {
            "gain_count": len(self._context),
            "max_gain": max(
                (max(domains.values()) for domains in self._context.values()),
                default=0.0,
            ),
            "memory": self._memory.stats(),
        }
