from __future__ import annotations

from pathlib import Path

from loader.loader import NeuralFrameworkLoader
from engine.runtime import BrainRuntime
from engine.drivers.visual_temporal_driver import VisualTemporalDriver


ROOT = Path(__file__).resolve().parents[2]


# ============================================================
# Brain compilation
# ============================================================
def compile_brain() -> dict:
    loader = NeuralFrameworkLoader(ROOT)
    loader.load_neuron_bases()
    loader.load_regions()
    loader.load_profiles()
    return loader.compile(
        expression_profile="minimal",
        state_profile="awake",
        compound_profile="experimental",
    )


# ============================================================
# Helpers
# ============================================================
def region_mass(runtime: BrainRuntime, region_id: str) -> float:
    snap = runtime.snapshot_region_stats(region_id)
    if not snap:
        return 0.0
    return float(snap["mass"])


def population_mass(runtime: BrainRuntime, region_id: str, population: str) -> float:
    region = runtime.region_states.get(region_id)
    if not region:
        return 0.0
    pops = region.get("populations", {})
    if population not in pops:
        return 0.0
    return sum(float(p.output()) for p in pops[population])


# ============================================================
# Experiment
# ============================================================
def main() -> None:
    brain = compile_brain()
    rt = BrainRuntime(brain, dt=0.01)

    # ------------------------------------------------------------
    # Stabilization parameters
    # ------------------------------------------------------------
    STABILIZATION_SECONDS = 20.0
    STABILIZATION_STEPS = int(STABILIZATION_SECONDS / rt.dt)  # 2000 steps

    # ------------------------------------------------------------
    # Visual stimulus parameters
    # ------------------------------------------------------------
    STIM_DURATION_STEPS = 140
    STIM_ONSET = STABILIZATION_STEPS
    STIM_OFFSET = STABILIZATION_STEPS + STIM_DURATION_STEPS

    driver = VisualTemporalDriver(
        onset_step=STIM_ONSET,
        offset_step=STIM_OFFSET,
        magnitude=0.60,  # increased amplitude (was 0.25)
    )

    print("\n=== FORCED VISUAL STIMULATION (20s STABILIZATION + MASS TRACE) ===")
    print(
        f"{'step':>6} | "
        f"{'VI':>6} {'LGN':>6} {'V1':>8} {'PULV':>6} | "
        f"{'VI_SIG':>6} {'LGN_REL':>8} | state"
    )

    last_on = False

    total_steps = STIM_OFFSET + 200  # extra tail to observe decay

    for step in range(total_steps):
        driver.step(rt)
        rt.step()

        stim_on = driver.onset_step <= driver.step_count <= driver.offset_step

        # --- boundary markers ---
        if stim_on and not last_on:
            print(f"\n--- STIMULUS ON (after {STABILIZATION_SECONDS:.1f}s stabilization) ---")
        if not stim_on and last_on:
            print("\n--- STIMULUS OFF ---")

        last_on = stim_on

        # --- sample regularly ---
        if step % 20 == 0:  # slower sampling during long warm-up
            vi = region_mass(rt, "visual_input")
            lgn = region_mass(rt, "lgn")
            v1 = region_mass(rt, "v1")
            pul = region_mass(rt, "pulvinar")

            vi_sig = population_mass(rt, "visual_input", "VISUAL_SIGNAL")
            lgn_rel = population_mass(rt, "lgn", "RELAY_CELLS")

            if step < STABILIZATION_STEPS:
                state = "WARM"
            else:
                state = "ON " if stim_on else "OFF"

            print(
                f"{step:6d} | "
                f"{vi:6.3f} {lgn:6.3f} {v1:8.3f} {pul:6.3f} | "
                f"{vi_sig:6.3f} {lgn_rel:8.3f} | {state}"
            )

    print("\n=== END ===")


if __name__ == "__main__":
    main()
