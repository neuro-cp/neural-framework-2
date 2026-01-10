import socket
import time
from pathlib import Path
from typing import Iterable


# ============================================================
# CONFIG
# ============================================================

HOST = "127.0.0.1"
PORT = 5557

LOG_PATH = Path(r"C:\Users\Admin\Desktop\neural framework\runtime_log.txt")

BASELINE_STEPS = 300        # ~3s @ dt=0.01
SHORT_DELAY = 150           # ~1.5s
RECOVERY_DELAY = 400        # ~4s

POKE_MAG = 25.0
TOP_N = 5

REGIONS = ("vpl", "s1", "trn")


# ============================================================
# SOCKET HELPERS
# ============================================================

def _send(cmd: str, expect_reply: bool = True) -> str:
    with socket.create_connection((HOST, PORT), timeout=3) as sock:
        sock.sendall((cmd + "\n").encode("utf-8"))
        if not expect_reply:
            return ""
        sock.settimeout(1.0)
        try:
            return sock.recv(4096).decode("utf-8").strip()
        except Exception:
            return ""


# ============================================================
# LOGGING
# ============================================================

def log(line: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] {line}"
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def snapshot(label: str, regions: Iterable[str]):
    log(f"[SNAPSHOT] {label}")
    for r in regions:
        stats = _send(f"stats {r}")
        if stats:
            log(f"[STATS] {stats}")
        top = _send(f"top {r} {TOP_N}")
        if top:
            log(f"[TOP] {r} :: {top}")


def poke(region: str, mag: float):
    _send(f"poke {region} {mag}", expect_reply=False)
    log(f"[POKE] {region} {mag}")


def wait_steps(n: int):
    # runtime runs independently; we just wait wall time
    time.sleep(n * 0.01)


# ============================================================
# EXPERIMENT
# ============================================================

log("=== BEGIN THALAMOCORTICAL GATING PROBE ===")

# ------------------------------------------------------------
# A. BASELINE
# ------------------------------------------------------------

log("[A] Baseline stabilization")
wait_steps(BASELINE_STEPS)
snapshot("baseline", REGIONS)

# ------------------------------------------------------------
# B. VPL RELAY DRIVE
# ------------------------------------------------------------

log("[B] VPL relay excitation (feedforward sensory)")
poke("vpl", POKE_MAG)

wait_steps(SHORT_DELAY)
snapshot("post_vpl_short", REGIONS)

wait_steps(RECOVERY_DELAY)
snapshot("post_vpl_recovery", REGIONS)

# ------------------------------------------------------------
# C. TRN INHIBITION
# ------------------------------------------------------------

log("[C] TRN inhibitory pulse (gating suppression)")
poke("trn", POKE_MAG)

wait_steps(SHORT_DELAY)
snapshot("post_trn_short", REGIONS)

wait_steps(RECOVERY_DELAY)
snapshot("post_trn_recovery", REGIONS)

# ------------------------------------------------------------
# D. CORTICOTHALAMIC FEEDBACK
# ------------------------------------------------------------

log("[D] S1 corticothalamic feedback (top-down bias)")
poke("s1", POKE_MAG)

wait_steps(SHORT_DELAY)
snapshot("post_s1_short", REGIONS)

wait_steps(RECOVERY_DELAY)
snapshot("post_s1_recovery", REGIONS)

# ------------------------------------------------------------
# END
# ------------------------------------------------------------

log("=== EXPERIMENT COMPLETE ===")
