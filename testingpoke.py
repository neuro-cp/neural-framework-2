from __future__ import annotations

import socket
import time
import csv
from pathlib import Path
from typing import Optional, Tuple


# ============================================================
# CONFIG
# ============================================================

HOST = "127.0.0.1"
PORT = 5557

BASE_DIR = Path(r"C:\Users\Admin\Desktop\neural framework")
LOG_PATH = BASE_DIR / "runtime_log.txt"
CSV_PATH = BASE_DIR / "dominance_trace.csv"

DT = 0.01

# -------------------------
# Timing
# -------------------------
BASELINE_WAIT = 6.0
DECAY_WAIT = 4.0

HOOK_STEPS = 25
HOOK_WAIT = DT * HOOK_STEPS

# -------------------------
# Magnitudes
# -------------------------
SMALL_POKE = 1.0


# ============================================================
# LOGGING
# ============================================================

def log(line: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] {line}"
    print(msg)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# ============================================================
# CSV TRACE (STRICT CONTRACT)
# ============================================================

def init_csv() -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["step", "winner", "D1", "D2"])


def append_csv(step: int, winner: str, d1: float, d2: float) -> None:
    """
    Write exactly ONE row:
    step (int), winner (str), D1 (float), D2 (float)
    """
    try:
        row = [int(step), str(winner), float(d1), float(d2)]
    except Exception as e:
        log(f"[CSV ERROR] Row skipped: {e}")
        return

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


# ============================================================
# TCP SEND
# ============================================================

def send(cmd: str, expect_reply: bool = True, timeout: float = 3.0) -> str:
    try:
        with socket.create_connection((HOST, PORT), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((cmd.strip() + "\n").encode("utf-8"))

            if not expect_reply:
                return ""

            data = sock.recv(16384)
            return data.decode("utf-8", errors="replace").strip()

    except Exception as e:
        return f"ERROR: {e}"


# ============================================================
# PARSING — SINGLE SOURCE OF TRUTH
# ============================================================

def parse_striatum_diag(out: str) -> Optional[Tuple[str, float, float]]:
    """
    Extract winner, D1, D2 from diagnostic text.
    Returns None if parsing fails.
    """
    d1 = None
    d2 = None
    winner = None

    for raw in out.splitlines():
        line = raw.strip()

        if line.startswith("D1:"):
            try:
                d1 = float(line.split(":", 1)[1])
            except ValueError:
                pass

        elif line.startswith("D2:"):
            try:
                d2 = float(line.split(":", 1)[1])
            except ValueError:
                pass

        elif line.startswith("Winner:"):
            winner = line.split(":", 1)[1].strip()

    if d1 is None or d2 is None:
        return None

    return (winner or "", d1, d2)


# ============================================================
# SNAPSHOTS
# ============================================================

def snap_region(tag: str, region: str) -> None:
    log(f"[SNAPSHOT] {tag} :: {region}")
    out = send(f"stats {region}")
    log(out if out else "NO DATA")


def snap_context(tag: str) -> None:
    log(f"[CONTEXT] {tag}")
    out = send("ctx")
    log(out if out else "CONTEXT EMPTY")


def snap_striatum(tag: str) -> None:
    log(f"[STRIATUM] {tag}")
    out = send("striatum")
    log(out if out else "NO DATA")


def snap_striatum_diag(tag: str, step: int) -> None:
    log(f"[STRIATUM_DIAG] {tag}")
    out = send("striatum_diag")

    if not out:
        log("NO DIAGNOSTICS")
        return

    log(out)

    parsed = parse_striatum_diag(out)
    if parsed is None:
        log("CSV SKIP — parse failed")
        return

    winner, d1, d2 = parsed
    append_csv(step, winner, d1, d2)


def snap_striatum_full(tag: str, step: int) -> None:
    snap_striatum(tag)
    snap_striatum_diag(tag, step)


# ============================================================
# INPUT
# ============================================================

def poke(region: str, mag: float) -> None:
    send(f"poke {region} {mag}", expect_reply=False)
    log(f"[POKE] {region} {mag}")


# ============================================================
# MAIN — TEST 2 ONLY
# ============================================================

log("=== BEGIN TEST 2 — TIME INTEGRATION ONLY ===")
init_csv()

# -------------------------
# Baseline
# -------------------------
log("[BASELINE] Stabilization")
time.sleep(BASELINE_WAIT)

snap_region("baseline", "pfc")
snap_region("baseline", "striatum")
snap_region("baseline", "gpi")
snap_context("baseline")
snap_striatum_full("baseline", step=0)

# -------------------------
# Integration
# -------------------------
log("[TEST 2] Time-integration (many small striatal pokes)")

for i in range(1, 21):
    poke("striatum", SMALL_POKE)
    time.sleep(HOOK_WAIT)

    if i % 5 == 0:
        snap_striatum_full(f"integrate_{i}", step=i)

# -------------------------
# Decay
# -------------------------
time.sleep(DECAY_WAIT)
snap_striatum_full("integrate_decay", step=999)

log("[TEST 2] Complete")
log("=== TEST COMPLETE ===")
