from __future__ import annotations

import json
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
    if hasattr(runtime, "_resolve_region_key"):
        rk = runtime._resolve_region_key(region_label)
        if rk:
            return rk
    return region_label


def _get_salience(runtime):
    return getattr(runtime, "salience", None)

def _dump_control(runtime) -> str:
    if not hasattr(runtime, "get_control_state"):
        return "CONTROL: unsupported"

    state = runtime.get_control_state()
    if not state:
        return "CONTROL: none"

    if hasattr(state, "to_dict"):
        return "CONTROL:\n" + json.dumps(state.to_dict(), indent=2)

    return f"CONTROL: {state}"



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

    mean, std = _basic_stats(acts)
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
        return f"ERROR: unknown region '{region_label}'"

    rows = []
    for plist in region["populations"].values():
        for pop in plist:
            rows.append((pop.assembly_id, float(pop.output())))

    if not rows:
        return "EMPTY"

    rows.sort(key=lambda x: x[1], reverse=True)
    return " | ".join(
        f"{aid} :: {val:.4f}" for aid, val in rows[: max(1, n)]
    )


# ============================================================
# Context diagnostics
# ============================================================

def _dump_context(runtime) -> str:
    ctx = getattr(runtime, "context", None)
    if not ctx:
        return "CONTEXT: unavailable"

    dump = ctx.dump()
    if not dump:
        return "CONTEXT EMPTY"

    return "\n".join(
        f"{k}: {v}" for k, v in dump.items()
    )


def _dump_context_full(runtime) -> str:
    ctx = getattr(runtime, "context", None)
    if not ctx:
        return "CONTEXT: unavailable"
    return str(ctx.stats())


# ============================================================
# Salience diagnostics
# ============================================================

def _dump_salience(runtime) -> str:
    sal = _get_salience(runtime)
    if not sal:
        return "SALIENCE: not enabled"

    stats = sal.stats()
    if not stats:
        return "SALIENCE EMPTY"

    return (
        "SALIENCE:\n"
        f"  count={stats.get('count', 0)}\n"
        f"  mean={stats.get('mean', 0.0):.4f}\n"
        f"  max={stats.get('max', 0.0):.4f}"
    )


def _dump_salience_full(runtime) -> str:
    sal = _get_salience(runtime)
    if not sal:
        return "SALIENCE: not enabled"
    return sal.dump()


def _salience_set(runtime, assembly_id: str, value: float) -> str:
    sal = _get_salience(runtime)
    if not sal:
        return "ERROR: salience not enabled"
    sal.set(assembly_id, float(value))
    return f"OK salience {assembly_id} = {value}"


def _salience_clear(runtime) -> str:
    sal = _get_salience(runtime)
    if not sal:
        return "ERROR: salience not enabled"
    sal.clear()
    return "OK salience cleared"


# ============================================================
# Striatum / BG diagnostics
# ============================================================

def _dump_striatum(runtime) -> str:
    snap = getattr(runtime, "_last_striatum_snapshot", None)
    if not snap:
        return "STRIATUM: no data"

    lines = [f"STRIATUM @ t={snap.get('time', 0.0):.3f}"]
    if snap.get("winner") is not None:
        lines.append(f"winner={snap['winner']}")

    for ch, val in sorted(
        snap.get("dominance", {}).items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        lines.append(f"{ch}={val:.6f}")

    return "\n".join(lines)


def _dump_gate(runtime) -> str:
    if not hasattr(runtime, "snapshot_gate_state"):
        return "GATE: unavailable"

    s = runtime.snapshot_gate_state()
    return (
        "GATE:\n"
        f"  t={s.get('time', 0.0):.3f}\n"
        f"  relief={s.get('relief', 1.0):.4f}\n"
        f"  winner={s.get('winner')}"
    )


def _dump_decision(runtime) -> str:
    if not hasattr(runtime, "get_decision_state"):
        return "DECISION: unsupported"

    d = runtime.get_decision_state()
    if not d:
        return "DECISION: none"

    return "DECISION:\n" + "\n".join(f"  {k}={v}" for k, v in d.items())

# ============================================================
# VTA Value diagnostics
# ============================================================

def _dump_value(runtime) -> str:
    val = getattr(runtime, "value_signal", None)
    if not val:
        return "VALUE: not enabled"

    return f"VALUE: {val.get():.4f}"


def _set_value(runtime, x: float) -> str:
    val = getattr(runtime, "value_signal", None)
    pol = getattr(runtime, "value_policy", None)

    if not val or not pol:
        return "ERROR: value system not enabled"

    t = getattr(runtime, "time", 0.0)

    new_val = pol.apply(
        current_value=val.get(),
        proposed_value=float(x),
        t=t,
    )

    val.set(new_val)
    return f"OK value = {val.get():.4f}"


def _clear_value(runtime) -> str:
    val = getattr(runtime, "value_signal", None)
    if not val:
        return "ERROR: value system not enabled"

    val.reset()
    return "OK value reset"


# ============================================================
# Latch controls
# ============================================================

def _set_sustain(runtime, n: int) -> str:
    try:
        runtime._decision_sustain_required = max(1, int(n))
        return f"OK sustain {n}"
    except Exception as e:
        return f"ERROR: {e}"


def _get_sustain(runtime) -> str:
    return f"SUSTAIN: {getattr(runtime, '_decision_sustain_required', '?')}"


def _reset_latch(runtime) -> str:
    runtime._decision_fired = False
    runtime._decision_counter = 0
    runtime._decision_state = None
    return "OK reset_latch"


# ============================================================
# TCP Server
# ============================================================

def start_command_server(runtime, host: str = "127.0.0.1", port: int = 5557):

    def help_text() -> str:
        return (
            "Commands:\n"
            "  poke <region> <mag>\n"
            "  poke_pop <region> <population> <mag>\n"
            "  poke_asm <region> <population> <idx> <mag>\n"
            "  stats <region>\n"
            "  top <region> <N>\n"
            "  context | ctx\n"
            "  ctxfull\n"
            "  salience\n"
            "  salience_full\n"
            "  salience_set <assembly> <value>\n"
            "  salience_clear\n"
            "  striatum | stri\n"
            "  gate\n"
            "  decision\n"
            "  sustain [N]\n"
            "  reset_latch\n"
            "  control\n"
            "  value\n"
            "  value_set <x>\n"
            "  value_clear\n"
            "  help"
        )

    def handle(cmd: str) -> str:
        parts = cmd.strip().split()
        if not parts:
            return "ERROR: empty command"

        op = parts[0].lower()

        if op in ("help", "?"):
            return help_text()

        if op == "poke" and len(parts) == 3:
            runtime.inject_stimulus(parts[1], magnitude=float(parts[2]))
            return "OK"

        if op == "poke_pop" and len(parts) == 4:
            runtime.inject_stimulus(parts[1], parts[2], magnitude=float(parts[3]))
            return "OK"

        if op == "poke_asm" and len(parts) == 5:
            runtime.inject_stimulus(parts[1], parts[2], int(parts[3]), float(parts[4]))
            return "OK"

        if op == "stats":
            return _region_stats(runtime, parts[1])

        if op == "top":
            return _top_assemblies(runtime, parts[1], int(parts[2]))

        if op in ("context", "ctx"):
            return _dump_context(runtime)

        if op == "ctxfull":
            return _dump_context_full(runtime)

        if op == "salience":
            return _dump_salience(runtime)

        if op == "salience_full":
            return _dump_salience_full(runtime)

        if op == "salience_set" and len(parts) == 3:
            return _salience_set(runtime, parts[1], float(parts[2]))

        if op == "salience_clear":
            return _salience_clear(runtime)

        if op in ("striatum", "stri"):
            return _dump_striatum(runtime)

        if op == "gate":
            return _dump_gate(runtime)

        if op == "decision":
            return _dump_decision(runtime)

        if op == "sustain":
            return _get_sustain(runtime) if len(parts) == 1 else _set_sustain(runtime, int(parts[1]))

        if op == "reset_latch":
            return _reset_latch(runtime)

        if op == "control":
            return _dump_control(runtime)
        
        if op == "value":
            return _dump_value(runtime)

        if op == "value_set" and len(parts) == 2:
            try:
                x = float(parts[1])
            except ValueError:
                return "ERROR: invalid value"
            return _set_value(runtime, x)

        if op == "value_clear":
            return _clear_value(runtime)
        
        # -----------------------------
        # Pre-decision salience priming
        # -----------------------------
        if op == "psm_prime" and len(parts) == 3:
            target = parts[1]
            try:
                gain = float(parts[2])
            except ValueError:
                return "ERROR: invalid gain"

            if not hasattr(runtime, "apply_psm_prime"):
                return "ERROR: PSM not supported"

            runtime.apply_psm_prime(target, gain)
            return f"OK psm_prime {target} += {gain}"

        return "ERROR: unknown command"

    def loop():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen(5)
            print(f"[CMD] Listening on {host}:{port}")

            while True:
                conn, _ = s.accept()
                with conn:
                    data = conn.recv(4096)
                    if not data:
                        continue
                    try:
                        resp = handle(data.decode("utf-8"))
                    except Exception as e:
                        resp = f"ERROR: {e}"
                    conn.sendall((resp + "\n").encode("utf-8"))

    threading.Thread(target=loop, daemon=True).start()
