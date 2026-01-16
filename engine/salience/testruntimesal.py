from __future__ import annotations

import time
from pathlib import Path

from loader.loader import NeuralFrameworkLoader
from engine.runtime import BrainRuntime
from engine.salience.salience_field import SalienceField
from engine.command_server import start_command_server


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[2]   # project root
DT = 0.01
STEPS = 50


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=== RUNTIME + SALIENCE SMOKE TEST ===")

    # --------------------------------------------------------
    # Load + compile brain (canonical loader path)
    # --------------------------------------------------------
    loader = NeuralFrameworkLoader(ROOT)

    loader.load_neuron_bases()
    loader.load_regions()
    loader.load_profiles()

    brain = loader.compile(
        expression_profile="minimal",
        state_profile="awake",
        compound_profile="experimental",
    )

    # --------------------------------------------------------
    # Runtime
    # --------------------------------------------------------
    runtime = BrainRuntime(brain, dt=DT)

    # --------------------------------------------------------
    # Salience field (standalone for now)
    # --------------------------------------------------------
    salience = SalienceField(
        decay_tau=3.0,
        max_value=1.0,
    )

    # --------------------------------------------------------
    # Start command server (for inspection)
    # --------------------------------------------------------
    start_command_server(runtime)

    print("[OK] Runtime initialized")
    print("[OK] Salience field initialized")
    print("[OK] Command server running")
    print()

    # --------------------------------------------------------
    # Minimal stepping loop
    # --------------------------------------------------------
    for i in range(STEPS):
        runtime.step()

        if i % 10 == 0:
            gate = runtime.snapshot_gate_state()
            print(
                f"[STEP {i:03d}] "
                f"t={gate['time']:.3f} "
                f"relief={gate['relief']:.3f} "
                f"winner={gate.get('winner')}"
            )

        time.sleep(0.01)

    print()
    print("=== SMOKE TEST COMPLETE ===")
    print("Try commands: help, gate, striatum, decision")


if __name__ == "__main__":
    main()
