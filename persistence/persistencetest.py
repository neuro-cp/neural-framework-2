# test_runtime.py
# Deterministic persistence validation harness
# Validates BG persistence traces WITHOUT assuming semantic channels yet

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict

from loader.loader import NeuralFrameworkLoader
from engine.runtime import BrainRuntime


# ============================================================
# CONFIG
# ============================================================

DT = 0.01

PHASE_A_STEPS = 100     # seed persistence
PHASE_B_STEPS = 100     # symmetric competition
PHASE_C_STEPS = 300     # decay

POKE_MAG = 1.0

TARGET_REGION = "striatum"
TARGET_POP = "D1_MSN"

ASSEMBLY_A = 0
ASSEMBLY_B = 1


def aid(idx: int) -> str:
    return f"{TARGET_REGION}:{TARGET_POP}:{idx}"


# ============================================================
# LOAD BRAIN
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

runtime = BrainRuntime(brain, dt=DT)

print("\n=== PERSISTENCE VALIDATION TEST ===")
print(f"Target assemblies: {aid(ASSEMBLY_A)} vs {aid(ASSEMBLY_B)}")
print("-" * 80)


# ============================================================
# HELPERS
# ============================================================

def poke(idx: int):
    runtime.inject_stimulus(
        TARGET_REGION,
        population_id=TARGET_POP,
        assembly_index=idx,
        magnitude=POKE_MAG,
    )


def trace_value(idx: int) -> float:
    trace = runtime.bg_persistence.traces.get(aid(idx))
    return trace.value if trace else 0.0


def winner_label() -> str:
    w = runtime.competition_kernel.last_winner_id
    if not w:
        return "none"
    if w.endswith(f":{ASSEMBLY_A}"):
        return "A"
    if w.endswith(f":{ASSEMBLY_B}"):
        return "B"
    return "other"


# ============================================================
# PHASE A — SEED PERSISTENCE
# ============================================================

print("\n[PHASE A] Seeding persistence (poke A only)")

for step in range(PHASE_A_STEPS):
    poke(ASSEMBLY_A)
    runtime.step()

    if step % 20 == 0:
        print(
            f"t={runtime.time:5.2f}s | "
            f"trace(A)={trace_value(ASSEMBLY_A):.4f} | "
            f"trace(B)={trace_value(ASSEMBLY_B):.4f}"
        )


# ============================================================
# PHASE B — SYMMETRIC INPUT
# ============================================================

print("\n[PHASE B] Symmetric stimulation (A vs B)")

wins = {"A": 0, "B": 0, "none": 0}

for step in range(PHASE_B_STEPS):
    poke(ASSEMBLY_A)
    poke(ASSEMBLY_B)
    runtime.step()

    w = winner_label()
    wins.setdefault(w, 0)
    wins[w] += 1

    if step % 20 == 0:
        print(
            f"t={runtime.time:5.2f}s | "
            f"winner={w:5} | "
            f"trace(A)={trace_value(ASSEMBLY_A):.4f} | "
            f"trace(B)={trace_value(ASSEMBLY_B):.4f}"
        )

print("\n[PHASE B RESULT]")
print("Wins:", wins)


# ============================================================
# PHASE C — DECAY
# ============================================================

print("\n[PHASE C] Decay (no input)")

for step in range(PHASE_C_STEPS):
    runtime.step()

    if step % 50 == 0:
        print(
            f"t={runtime.time:5.2f}s | "
            f"trace(A)={trace_value(ASSEMBLY_A):.4f} | "
            f"trace(B)={trace_value(ASSEMBLY_B):.4f}"
        )


# ============================================================
# SUMMARY
# ============================================================

print("\n=== TEST COMPLETE ===")
print("Correct expectations at THIS stage:")
print("- Phase A: trace(A) rises, trace(B) ≈ 0")
print("- Phase B: winner may be 'none' (no semantic channels yet)")
print("- Phase C: traces decay smoothly toward 0")
print("=" * 80)
