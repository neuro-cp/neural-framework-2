from __future__ import annotations

import socket
import threading
from typing import List, Optional, Tuple, Dict, Any


# ============================================================
# Helpers
# ============================================================

def _basic_stats(values: List[float]) -> Optional[Tuple[float, float]]:
    if not values:
        return None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, var ** 0.5


def _resolve_region(runtime, region_label: str) -> str:
    """
    Resolve user-supplied region label to runtime region key.
    """
    if hasattr(runtime, "_resolve_region_key"):
        rk = runtime._resolve_region_key(region_label)  # type: ignore[attr-defined]
        if rk:
            return rk
    return region_label


# ============================================================
# Region diagnostics
# ============================================================

def _region_stats(runtime, region_label: str) -> str:
    region_id = _resolve_region(runtime, region_label)
    region = runtime.region_states.get(region_id)
    if not region:
        return f"ERROR: unknown region '{region_label}' (resolved='{region_id}')"

    acts, outs = [], []
    for plist in region["populations"].values():
        for pop in plist:
            acts.append(float(getattr(pop, "activity", 0.0)))
            outs.append(float(pop.output()))

    if not acts:
        return f"{region_id} MASS=0.0000 MEAN=0.0000 STD=0.0000 N=0"

    stats = _basic_stats(acts)
    if not stats:
        return f"{region_id} MASS=0.0000 MEAN=0.0000 STD=0.0000 N=0"

    mean, std = stats
    return (
        f"{region_id} "
        f"MASS={sum(outs):.4f} "
        f"MEAN={mean:.4f} "
        f"STD={std:.4f} "
        f"N={len(acts)}"
    )


def _top_assemblies(runtime, region_label: str, n: int) -> str:
    region_id = _resolve_region(runtime, region_label)
    region = runtime.region_states.get(region_id)
    if not region:
        return f"ERROR: unknown region '{region_label}' (resolved='{region_id}')"

    rows = []
    for plist in region["populations"].values():
        for pop in plist:
            rows.append((pop.assembly_id, float(pop.output())))

    if not rows:
        return "EMPTY"

    rows.sort(key=lambda x: x[1], reverse=True)
    top = rows[: max(1, n)]
    return " | ".join(f"{aid} :: {val:.4f}" for aid, val in top)


# ============================================================
# Context diagnostics
# ============================================================

def _dump_context(runtime) -> str:
    if not hasattr(runtime, "context"):
        return "CONTEXT: runtime has no context"

    ctx = runtime.context.dump()
    if not ctx:
        return "CONTEXT EMPTY"

    region_totals: Dict[str, float] = {}
    region_counts: Dict[str, int] = {}
    region_domains: Dict[str, set] = {}

    for assembly_id, domains in ctx.items():
        if assembly_id == "__global__":
            region = "__global__"
        else:
            region = assembly_id.split(":", 1)[0]

        region_counts[region] = region_counts.get(region, 0) + 1
        region_totals.setdefault(region, 0.0)

        for d, v in domains.items():
            region_totals[region] += float(v)
            region_domains.setdefault(region, set()).add(str(d))

    lines = ["CONTEXT:"]
    for region in sorted(region_totals):
        lines.append(
            f"  {region:<14} "
            f"assemblies={region_counts.get(region, 0):<4} "
            f"total={region_totals[region]:.4f} "
            f"domains={','.join(sorted(region_domains.get(region, [])))}"
        )

    return "\n".join(lines)


def _dump_context_full(runtime) -> str:
    if not hasattr(runtime, "context"):
        return "CONTEXT: runtime has no context"
    return runtime.context.stats()


# ============================================================
# Striatum / BG diagnostics
# ============================================================

def _dump_striatum(runtime) -> str:
    snap = getattr(runtime, "_last_striatum_snapshot", None)
    if not snap:
        return "STRIATUM: no data"

    dominance = snap.get("dominance", {})
    if not dominance:
        return "STRIATUM: empty"

    lines = [f"STRIATUM @ t={snap.get('time', 0.0):.3f}"]

    if snap.get("winner") is not None:
        lines.append(f"winner={snap['winner']}")

    for ch, val in sorted(dominance.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"{ch}={float(val):.6f}")

    return "\n".join(lines)


def _dump_striatum_diag(runtime) -> str:
    ck = getattr(runtime, "competition_kernel", None)
    if ck is None:
        return "STRIATUM_DIAG: no competition kernel"

    try:
        return ck.format_diagnostics(precision=7)
    except Exception as e:
        return f"STRIATUM_DIAG: error ({e})"


def _dump_gate(runtime) -> str:
    if hasattr(runtime, "snapshot_gate_state"):
        try:
            s = runtime.snapshot_gate_state()
            return (
                "GATE:\n"
                f"  t={float(s.get('time', 0.0)):.3f}\n"
                f"  relief={float(s.get('relief', 1.0)):.4f}\n"
                f"  winner={s.get('winner', None)}"
            )
        except Exception as e:
            return f"GATE: error ({e})"

    return "GATE: no data"


def _dump_decision(runtime) -> str:
    """
    Explicit decision latch snapshot.
    Read-only, fires once per episode.
    """
    if not hasattr(runtime, "get_decision_state"):
        return "DECISION: runtime does not support decision latch"

    state = runtime.get_decision_state()
    if not state:
        return "DECISION: none"

    lines = ["DECISION:"]
    for k, v in state.items():
        lines.append(f"  {k} = {v}")

    return "\n".join(lines)


# ============================================================
# Part B controls (minimal + safe)
# ============================================================

def _set_sustain(runtime, n: int) -> str:
    if not hasattr(runtime, "_decision_sustain_required"):
        return "ERROR: runtime does not expose _decision_sustain_required"
    try:
        n2 = max(1, int(n))
        setattr(runtime, "_decision_sustain_required", n2)
        return f"OK sustain {n2}"
    except Exception as e:
        return f"ERROR: sustain set failed ({e})"


def _get_sustain(runtime) -> str:
    if hasattr(runtime, "_decision_sustain_required"):
        return f"SUSTAIN: {int(getattr(runtime, '_decision_sustain_required'))}"
    if hasattr(runtime, "DECISION_SUSTAIN_STEPS"):
        return f"SUSTAIN: {int(getattr(runtime, 'DECISION_SUSTAIN_STEPS'))}"
    return "SUSTAIN: unknown"


def _reset_latch(runtime) -> str:
    # Only resets decision latch state; does not touch dynamics.
    try:
        if hasattr(runtime, "_decision_fired"):
            setattr(runtime, "_decision_fired", False)
        if hasattr(runtime, "_decision_counter"):
            setattr(runtime, "_decision_counter", 0)
        if hasattr(runtime, "_decision_state"):
            setattr(runtime, "_decision_state", None)
        return "OK reset_latch"
    except Exception as e:
        return f"ERROR: reset_latch failed ({e})"


# ============================================================
# TCP Server
# ============================================================

def start_command_server(runtime, host: str = "127.0.0.1", port: int = 5557):
    """
    Lightweight TCP command server for runtime instrumentation.
    Read-only except for explicit stimulus injection + Part B latch controls.
    """

    def help_text() -> str:
        return (
            "Commands:\n"
            "  poke <region> <mag>\n"
            "  stats <region>\n"
            "  top <region> <N>\n"
            "  context | ctx\n"
            "  ctxfull\n"
            "  striatum | stri\n"
            "  striatum_diag | stri_diag\n"
            "  gate\n"
            "  decision\n"
            "  sustain [N]        (query or set latch sustain steps)\n"
            "  reset_latch        (clear one-shot decision latch)\n"
            "  help"
        )

    def handle_command(cmd: str) -> str:
        cmd = (cmd or "").strip()
        if not cmd:
            return "ERROR: empty command"

        parts = cmd.split()
        op = parts[0].lower()

        if op in ("help", "?"):
            return help_text()

        # -------------------------------
        # Mutating command (explicit)
        # -------------------------------
        if op == "poke":
            if len(parts) != 3:
                return "ERROR: poke <region> <mag>"
            try:
                mag = float(parts[2])
            except ValueError:
                return "ERROR: magnitude must be float"
            runtime.inject_stimulus(region_id=parts[1], magnitude=mag)
            return f"OK poke {parts[1]} {mag}"

        # -------------------------------
        # Part B latch controls (explicit)
        # -------------------------------
        if op == "sustain":
            if len(parts) == 1:
                return _get_sustain(runtime)
            if len(parts) == 2:
                try:
                    n = int(parts[1])
                except ValueError:
                    return "ERROR: sustain N must be int"
                return _set_sustain(runtime, n)
            return "ERROR: sustain [N]"

        if op == "reset_latch":
            return _reset_latch(runtime)

        # -------------------------------
        # Read-only diagnostics
        # -------------------------------
        if op == "stats" and len(parts) == 2:
            return _region_stats(runtime, parts[1])

        if op == "top" and len(parts) == 3:
            try:
                return _top_assemblies(runtime, parts[1], int(parts[2]))
            except ValueError:
                return "ERROR: N must be int"

        if op in ("context", "ctx"):
            return _dump_context(runtime)

        if op == "ctxfull":
            return _dump_context_full(runtime)

        if op in ("striatum", "stri"):
            return _dump_striatum(runtime)

        if op in ("striatum_diag", "stri_diag"):
            return _dump_striatum_diag(runtime)

        if op == "gate":
            return _dump_gate(runtime)

        if op == "decision":
            return _dump_decision(runtime)

        return "ERROR: unknown command"

    def server_loop():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen(5)
            print(f"[CMD] Listening on {host}:{port}")

            while True:
                conn, _ = s.accept()
                with conn:
                    try:
                        data = conn.recv(4096)
                        if not data:
                            continue
                        result = handle_command(data.decode("utf-8").strip())
                    except Exception as e:
                        result = f"ERROR: {e}"

                    conn.sendall((result + "\n").encode("utf-8"))

    threading.Thread(target=server_loop, daemon=True).start()
