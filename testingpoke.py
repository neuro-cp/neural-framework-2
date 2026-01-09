import socket
import time
from pathlib import Path

# ----------------------------
# CONFIG
# ----------------------------

HOST = "127.0.0.1"
PORT = 5557

LOG_PATH = Path(r"C:\Users\Admin\Desktop\neural framework\runtime_log.txt")

BASELINE_WAIT = 5.0
POKE_VALUE = 20
STRIATUM_REPEATS = 5
DELAY_SECONDS = 2.5

TOP_N = 5   # how many assemblies to query

# ----------------------------
# HELPERS
# ----------------------------

def log(line: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{timestamp}] {line}"
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def send_command(cmd: str, expect_reply: bool = True) -> str:
    with socket.create_connection((HOST, PORT), timeout=3) as sock:
        sock.sendall((cmd + "\n").encode("utf-8"))
        if not expect_reply:
            return ""
        sock.settimeout(1.0)
        try:
            data = sock.recv(4096)
            return data.decode("utf-8").strip()
        except Exception:
            return ""

def poke(region: str, mag: float):
    cmd = f"poke {region} {mag}"
    send_command(cmd, expect_reply=False)
    log(f"[POKE] {cmd}")

def snapshot(label: str, region: str):
    """
    Pull structured diagnostics from the runtime and log them.
    """
    log(f"[SNAPSHOT] {label}")

    stats = send_command(f"stats {region}")
    if stats:
        log(f"[STATS] {stats}")

    top = send_command(f"top {region} {TOP_N}")
    if top:
        # 'top' prints internally, but also returns a summary line
        log(f"[TOP] {top}")

# ----------------------------
# MAIN
# ----------------------------

log("=== BEGIN CONTROLLED POKE EXPERIMENTS ===")

# -------------------------------------------------
# EXPERIMENT A — BASELINE
# -------------------------------------------------

log("[EXP A] Baseline stabilization")
time.sleep(BASELINE_WAIT)

snapshot("baseline", "striatum")

# -------------------------------------------------
# EXPERIMENT B — STRIATUM COMPETITION
# -------------------------------------------------

log("[EXP B] Repeated STRIATUM stimulation")

for i in range(STRIATUM_REPEATS):
    poke("striatum", POKE_VALUE)
    time.sleep(DELAY_SECONDS)
    snapshot(f"striatum_repeat_{i+1}", "striatum")

# Give downstream nuclei time to respond
time.sleep(5.0)

snapshot("post_striatum_decay", "striatum")
snapshot("post_striatum_gpi", "gpi")
snapshot("post_striatum_gpe", "gpe")

# -------------------------------------------------
# EXPERIMENT C — CORTICAL BIAS
# -------------------------------------------------

log("[EXP C] PFC → STRIATUM bias test")

poke("pfc", POKE_VALUE)
time.sleep(1.5)

snapshot("post_pfc", "pfc")
snapshot("pre_bias_striatum", "striatum")

poke("striatum", POKE_VALUE)
time.sleep(5.0)

snapshot("post_bias_striatum", "striatum")
snapshot("post_bias_gpi", "gpi")

# -------------------------------------------------
# CLEANUP
# -------------------------------------------------

log("=== ALL EXPERIMENTS COMPLETE ===")
