import socket
import time

# ----------------------------
# CONFIG
# ----------------------------

HOST = "127.0.0.1"
PORT = 5557

# Log-scale poke magnitudes
POKE_VALUES = [20, 100, 500, 2500, 10000]
DELAY_SECONDS = 5.0

REGIONS = [
    "lgn", "md", "mgb", "pulvinar", "trn", "vpl", "vpm",
    "v1", "a1", "s1", "association_cortex", "pfc",
    "striatum", "gpe", "gpi", "stn", "snc", "vta",
    "locus_coeruleus", "raphe",
    "inferior_colliculus", "superior_colliculus",
    "ca1", "ca3", "dentate_gyrus", "subiculum",
    "hypothalamus", "anterior_pituitary", "posterior_pituitary",
    "cerebellar_cortex", "deep_nuclei",
    "autonomic_system",
]

# ----------------------------
# HELPERS
# ----------------------------

def send_command(cmd: str):
    with socket.create_connection((HOST, PORT), timeout=3) as sock:
        sock.sendall((cmd + "\n").encode("utf-8"))

# ----------------------------
# MAIN
# ----------------------------

print("=== BEGIN LOG-SCALE REGION POKE SWEEP ===")
print(f"poke values = {POKE_VALUES}, delay = {DELAY_SECONDS}s")

for poke_value in POKE_VALUES:
    print(f"\n--- BEGIN POKE STRENGTH: {poke_value} ---")

    for region in REGIONS:
        cmd = f"poke {region} {poke_value}"
        try:
            send_command(cmd)
            print(f"[SENT] {cmd}")
        except Exception as e:
            print(f"[ERROR] {cmd} -> {e}")

        time.sleep(DELAY_SECONDS)

    print(f"--- END POKE STRENGTH: {poke_value} ---")

print("\n=== ALL POKES COMPLETE ===")
