# test_runtime.py  (Cross-platform interactive runtime + TCP command server)
from __future__ import annotations

import time
import os
import sys
from pathlib import Path

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
# UI CONFIG
# ============================================================

SHOW_ASSEMBLIES = True
SHOW_ZERO_REGIONS = False
UI_INTERVAL = 1.0


# ============================================================
# SNAPSHOT FUNCTIONS
# ============================================================

def snapshot_aggregate(runtime: BrainRuntime, *, show_zero: bool):
    rows = []

    for region_id, region in runtime.region_states.items():
        total_act = total_fr = count = 0

        for assemblies in region["populations"].values():
            for pop in assemblies:
                total_act += pop.activity
                total_fr += pop.firing_rate
                count += 1

        if count == 0 and not show_zero:
            continue

        rows.append((
            region_id,
            (total_act / count) if count else 0.0,
            (total_fr / count) if count else 0.0,
            count,
        ))

    rows.sort(key=lambda x: x[0])
    return rows


def snapshot_assemblies(runtime: BrainRuntime, *, region_filter: str | None = None):
    rows = []

    for region_id, region in runtime.region_states.items():
        if region_filter and region_id != region_filter:
            continue

        for assemblies in region["populations"].values():
            for pop in assemblies:
                rows.append((pop.assembly_id, pop.activity, pop.firing_rate, region_id))

    rows.sort(key=lambda x: x[0])
    return rows


def dump_region_assemblies(runtime: BrainRuntime, region_id: str) -> str:
    if region_id not in runtime.region_states:
        return f"Unknown region: {region_id}"

    rows = snapshot_assemblies(runtime, region_filter=region_id)
    if not rows:
        return f"{region_id} has 0 assemblies."

    print("\n" + "=" * 90)
    print(f"DUMP REGION: {region_id}  (assemblies={len(rows)})")
    print(f"{'ASSEMBLY ID':55} {'ACT':>10} {'FR':>10}")
    print("-" * 90)
    for aid, act, fr, _ in rows:
        print(f"{aid:55} {act:10.4f} {fr:10.4f}")
    print("=" * 90 + "\n")

    return f"Dumped {len(rows)} assemblies for {region_id}."


# ============================================================
# COMMAND HANDLING (SINGLE SOURCE OF TRUTH)
# ============================================================

def apply_command(runtime: BrainRuntime, cmd: str) -> str:
    global SHOW_ASSEMBLIES, SHOW_ZERO_REGIONS

    parts = cmd.strip().split()
    if not parts:
        return "."

    head = parts[0].lower()

    # -----------------------
    # Help
    # -----------------------

    if head == "help":
        return (
            "Commands:\n"
            "  poke <region|all> <mag>\n"
            "  state [name]\n"
            "  view assemblies | view regions\n"
            "  toggle view | toggle zeros\n"
            "  dump <region>\n"
            "  help"
        )

    # -----------------------
    # Stimulus
    # -----------------------

    if head == "poke":
        if len(parts) != 3:
            return "Usage: poke <region|all> <magnitude>"
        try:
            mag = float(parts[2])
        except ValueError:
            return "Magnitude must be numeric"

        if parts[1] == "all":
            for rid in runtime.region_states:
                runtime.inject_stimulus(rid, magnitude=mag)
            return f"POKE all += {mag}"

        runtime.inject_stimulus(parts[1], magnitude=mag)
        return f"POKE {parts[1]} += {mag}"

    # -----------------------
    # Brain state (INERT)
    # -----------------------

    if head == "state":
        if len(parts) == 1:
            return f"brain_state = {runtime.get_state()}"
        runtime.set_state(parts[1])
        return f"brain_state -> {runtime.get_state()}"

    # -----------------------
    # View controls
    # -----------------------

    if head == "view" and len(parts) == 2:
        SHOW_ASSEMBLIES = (parts[1] == "assemblies")
        return f"View = {'ASSEMBLIES' if SHOW_ASSEMBLIES else 'REGIONS'}"

    if head == "toggle" and len(parts) == 2:
        if parts[1] == "view":
            SHOW_ASSEMBLIES = not SHOW_ASSEMBLIES
            return f"Toggled view -> {'ASSEMBLIES' if SHOW_ASSEMBLIES else 'REGIONS'}"
        if parts[1] == "zeros":
            SHOW_ZERO_REGIONS = not SHOW_ZERO_REGIONS
            return f"Toggled zeros -> {'SHOW' if SHOW_ZERO_REGIONS else 'HIDE'}"

    # -----------------------
    # Dump
    # -----------------------

    if head == "dump" and len(parts) == 2:
        return dump_region_assemblies(runtime, parts[1])

    return "Unknown command (type: help)"


# ============================================================
# LOAD BRAIN
# ============================================================

DEFAULT_ROOT = Path("C:/Users/Admin/Desktop/neural framework")
FALLBACK_ROOT = Path(__file__).resolve().parent
root = DEFAULT_ROOT if DEFAULT_ROOT.exists() else FALLBACK_ROOT

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

# Expose command handler to TCP server
runtime.apply_command = lambda cmd: apply_command(runtime, cmd)

# Start TCP command server
start_command_server(runtime)

print("\nLIVE RUNTIME")
print("Keyboard + TCP input enabled (port 5557)")
print("Ctrl+C to quit | type 'help' for commands")
print("-" * 80)


# ============================================================
# MAIN LOOP
# ============================================================

next_ui_time = UI_INTERVAL
t0 = time.perf_counter()
cmd_buffer = ""
last_msg = "Ready."

try:
    while True:
        runtime.step()

        while key_available():
            ch = read_key()

            if ch in ("\r", "\n"):
                if cmd_buffer.strip():
                    last_msg = apply_command(runtime, cmd_buffer)
                cmd_buffer = ""

            elif ch in ("\x7f", "\b"):
                cmd_buffer = cmd_buffer[:-1]

            elif ch == "\x03":
                raise KeyboardInterrupt

            elif ch.isprintable():
                cmd_buffer += ch

        if runtime.time >= next_ui_time:
            next_ui_time += UI_INTERVAL

            print("\n" + "-" * 80)
            print(f"t={runtime.time:.2f}s | state={runtime.get_state()}")

            if SHOW_ASSEMBLIES:
                print(f"{'ASSEMBLY ID':55} {'ACT':>10} {'FR':>10}")
                print("-" * 80)
                for aid, act, fr, _ in snapshot_assemblies(runtime):
                    print(f"{aid:55} {act:10.4f} {fr:10.4f}")
            else:
                print(f"{'REGION':20} {'MEAN_ACT':>10} {'MEAN_FR':>10} {'ASSEMBLIES':>10}")
                print("-" * 80)
                for rid, act, fr, n in snapshot_aggregate(runtime, show_zero=SHOW_ZERO_REGIONS):
                    print(f"{rid:20} {act:10.4f} {fr:10.4f} {n:10d}")

            print("-" * 80)
            print(f"last: {last_msg}")
            print(f"> {cmd_buffer}", end="", flush=True)

        target_wall = runtime.time
        elapsed = time.perf_counter() - t0
        if target_wall > elapsed:
            time.sleep(target_wall - elapsed)

except KeyboardInterrupt:
    print("\nStopped.")

finally:
    if not IS_WINDOWS:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_term_settings)
