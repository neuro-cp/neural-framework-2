# test_runtime.py
# Interactive runtime + TCP command server (instrumentation-only)

from __future__ import annotations

import time
import os
import sys
import math
from pathlib import Path
from typing import Optional, List

from loader.loader import NeuralFrameworkLoader
from engine.runtime import BrainRuntime
from engine.command_server import start_command_server


# ============================================================
# PLATFORM INPUT HANDLING
# ============================================================

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import msvcrt
else:
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old_term_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)


def key_available() -> bool:
    if IS_WINDOWS:
        return msvcrt.kbhit()
    return bool(select.select([sys.stdin], [], [], 0)[0])


def read_key() -> str:
    if IS_WINDOWS:
        return msvcrt.getwch()
    return sys.stdin.read(1)


# ============================================================
# UI CONFIG (DEFAULTS)
# ============================================================

VIEW_MODE = "populations"   # regions | populations | assemblies
SHOW_ZERO = False
UI_INTERVAL = 1.0


# ============================================================
# STATS HELPERS
# ============================================================

def _basic_stats(values: List[float]):
    if not values:
        return None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, math.sqrt(var)


def region_stats(runtime: BrainRuntime, region_id: str):
    region = runtime.region_states.get(region_id)
    if not region:
        return None

    acts, outs = [], []
    for plist in region["populations"].values():
        for pop in plist:
            acts.append(pop.activity)
            outs.append(pop.output())

    if not acts:
        return None

    mean, std = _basic_stats(acts)
    return {
        "mass": sum(outs),
        "mean": mean,
        "std": std,
        "n": len(acts),
    }


def population_stats(runtime: BrainRuntime):
    rows = []

    for rid, region in runtime.region_states.items():
        for pop_name, plist in region["populations"].items():
            acts = [p.activity for p in plist]
            outs = [p.output() for p in plist]

            if not acts and not SHOW_ZERO:
                continue

            if not acts:
                rows.append((rid, pop_name, 0, 0.0, 0.0))
                continue

            mean, _ = _basic_stats(acts)
            rows.append((
                rid,
                pop_name,
                len(plist),
                sum(outs),
                mean,
            ))

    return rows


def assembly_rows(runtime: BrainRuntime, region_filter: Optional[str] = None):
    rows = []
    for rid, region in runtime.region_states.items():
        if region_filter and rid != region_filter:
            continue
        for plist in region["populations"].values():
            for pop in plist:
                rows.append((
                    pop.assembly_id,
                    pop.activity,
                    pop.output(),
                    rid,
                ))
    return rows


# ============================================================
# COMMAND HANDLING
# ============================================================

def apply_command(runtime: BrainRuntime, cmd: str) -> str:
    global VIEW_MODE, SHOW_ZERO

    parts = cmd.strip().split()
    if not parts:
        return "."

    head = parts[0].lower()

    if head == "help":
        return (
            "Commands:\n"
            "  poke <region|all> <mag>\n"
            "  view regions | populations | assemblies\n"
            "  toggle zeros\n"
            "  stats <region>\n"
            "  dump <region>\n"
            "  help"
        )

    if head == "poke" and len(parts) == 3:
        mag = float(parts[2])
        if parts[1] == "all":
            for r in runtime.region_states:
                runtime.inject_stimulus(r, magnitude=mag)
            return f"POKE all += {mag}"
        runtime.inject_stimulus(parts[1], magnitude=mag)
        return f"POKE {parts[1]} += {mag}"

    if head == "view" and len(parts) == 2:
        if parts[1] in ("regions", "populations", "assemblies"):
            VIEW_MODE = parts[1]
            return f"View -> {VIEW_MODE.upper()}"
        return "Invalid view."

    if head == "toggle" and parts[1] == "zeros":
        SHOW_ZERO = not SHOW_ZERO
        return f"Show zeros -> {SHOW_ZERO}"

    if head == "stats" and len(parts) == 2:
        s = region_stats(runtime, parts[1])
        if not s:
            return "No data."
        return (
            f"{parts[1]} "
            f"MASS={s['mass']:.4f} "
            f"MEAN={s['mean']:.4f} "
            f"STD={s['std']:.4f}"
        )

    if head == "dump" and len(parts) == 2:
        rows = assembly_rows(runtime, parts[1])
        print("\nASSEMBLIES:")
        for aid, act, out, _ in rows:
            print(f"{aid:55} {act:10.6f} {out:10.6f}")
        return f"Dumped {len(rows)} assemblies."

    return "Unknown command."


# ============================================================
# LOAD + RUN
# ============================================================

root = Path("C:/Users/Admin/Desktop/neural framework")
loader = NeuralFrameworkLoader(root)
loader.load_neuron_bases()
loader.load_regions()
loader.load_profiles()

brain = loader.compile(
    expression_profile="human_default",
    state_profile="awake",
    compound_profile="experimental",
)

runtime = BrainRuntime(brain, dt=0.01)
runtime.apply_command = lambda c: apply_command(runtime, c)
start_command_server(runtime)

print("\nLIVE RUNTIME | TCP + Keyboard")
print("Port 5557 | Ctrl+C to quit")
print("Default view: POPULATIONS")
print("-" * 110)


# ============================================================
# MAIN LOOP
# ============================================================

next_ui = UI_INTERVAL
t0 = time.perf_counter()
cmd_buffer = ""
last_msg = "Ready."

try:
    while True:
        runtime.step()

        while key_available():
            ch = read_key()
            if ch in ("\n", "\r"):
                if cmd_buffer.strip():
                    last_msg = apply_command(runtime, cmd_buffer)
                cmd_buffer = ""
            elif ch in ("\b", "\x7f"):
                cmd_buffer = cmd_buffer[:-1]
            elif ch == "\x03":
                raise KeyboardInterrupt
            elif ch.isprintable():
                cmd_buffer += ch

        if runtime.time >= next_ui:
            next_ui += UI_INTERVAL
            print("\n" + "-" * 110)
            print(f"t={runtime.time:.2f}s | view={VIEW_MODE}")

            if VIEW_MODE == "regions":
                print(f"{'REGION':20} {'MASS':>10} {'MEAN':>10} {'STD':>10} {'N':>6}")
                for rid in runtime.region_states:
                    s = region_stats(runtime, rid)
                    if not s and not SHOW_ZERO:
                        continue
                    if not s:
                        print(f"{rid:20} {0:10.4f} {0:10.4f} {0:10.4f} {0:6}")
                    else:
                        print(
                            f"{rid:20} "
                            f"{s['mass']:10.4f} "
                            f"{s['mean']:10.4f} "
                            f"{s['std']:10.4f} "
                            f"{s['n']:6}"
                        )

            elif VIEW_MODE == "populations":
                print(f"{'REGION':15} {'POPULATION':25} {'ASM':>5} {'MASS':>10} {'MEAN':>10}")
                for rid, pop, n, mass, mean in population_stats(runtime):
                    print(f"{rid:15} {pop:25} {n:5d} {mass:10.4f} {mean:10.4f}")

            print("-" * 110)
            print(f"last: {last_msg}")
            print(f"> {cmd_buffer}", end="", flush=True)

        elapsed = time.perf_counter() - t0
        if runtime.time > elapsed:
            time.sleep(runtime.time - elapsed)

except KeyboardInterrupt:
    print("\nStopped.")

finally:
    if not IS_WINDOWS:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_term_settings)
