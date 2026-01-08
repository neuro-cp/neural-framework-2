import socket
import time
from pathlib import Path

# ----------------------------
# CONFIG
# ----------------------------

HOST = "127.0.0.1"
PORT = 5557

POKE_VALUE = 20
DELAY_SECONDS = 5.0

LOG_PATH = Path(r"C:\Users\Admin\Desktop\neural framework\runtime_log.txt")

REGIONS = [
    "lgn", "md", "mgb", "pulvinar", "trn", "vpl", "vpm",

    "v1", "a1", "s1", "association_cortex", "pfc",

    "striatum", "gpe", "gpi", "stn", "snc", "vta",

    "locus_coeruleus", "raphe",

    "inferior_colliculus", "superior_colliculus",

    "ca1", "ca3", "dentate_gyrus", "subiculum",

    "hypothalamus", "anterior_pituitary", "posterior_pituitary",

    "cerebellar_cortex", "deep_nuclei",

    "autonomic_system"
]

# ----------------------------
# HELPERS
# ----------------------------

def log(line: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{timestamp}] {line}"
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def send_command(cmd: str):
    with socket.create_connection((HOST, PORT), timeout=3) as sock:
        sock.sendall((cmd + "\n").encode("utf-8"))

# ----------------------------
# MAIN
# ----------------------------

log("=== BEGIN AUTOMATED REGION POKES ===")
log(f"poke strength = {POKE_VALUE}, delay = {DELAY_SECONDS}s")

for region in REGIONS:
    cmd = f"poke {region} {POKE_VALUE}"
    try:
        send_command(cmd)
        log(f"[POKE SENT] {cmd}")
    except Exception as e:
        log(f"[ERROR] {cmd} -> {e}")
    time.sleep(DELAY_SECONDS)

log("=== ALL POKES COMPLETE ===")
