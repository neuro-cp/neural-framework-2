from __future__ import annotations

from typing import Dict, Any


def collect_salience_observations(runtime) -> Dict[str, Any]:
    """
    Collect read-only salience-relevant observations from the runtime.

    RULES:
    - No state
    - No mutation
    - No salience injection
    - No policy logic

    This function is allowed to *look* at runtime internals,
    but must never change them.
    """

    obs: Dict[str, Any] = {}

    # --------------------------------------------------
    # Time
    # --------------------------------------------------
    obs["time"] = float(getattr(runtime, "time", 0.0))
    obs["dt"] = float(getattr(runtime, "dt", 0.0))

    # --------------------------------------------------
    # Gate / BG state
    # --------------------------------------------------
    if hasattr(runtime, "snapshot_gate_state"):
        gate = runtime.snapshot_gate_state()
        obs["gate_relief"] = float(gate.get("relief", 1.0))
        obs["gate_winner"] = gate.get("winner")

    # --------------------------------------------------
    # Striatum competition snapshot
    # --------------------------------------------------
    snap = getattr(runtime, "_last_striatum_snapshot", None)
    if snap:
        obs["striatum_winner"] = snap.get("winner")
        obs["striatum_dominance"] = dict(snap.get("dominance", {}))
        obs["striatum_instant"] = dict(snap.get("instant", {}))

    # --------------------------------------------------
    # Decision latch (read-only)
    # --------------------------------------------------
    if hasattr(runtime, "get_decision_state"):
        obs["decision"] = runtime.get_decision_state()

    # --------------------------------------------------
    # Population-level activity (coarse)
    # --------------------------------------------------
    region_activity: Dict[str, float] = {}

    for region_key, state in getattr(runtime, "region_states", {}).items():
        pops = [
            p
            for plist in state.get("populations", {}).values()
            for p in plist
        ]
        if not pops:
            continue

        mean_out = sum(float(p.output()) for p in pops) / len(pops)
        region_activity[region_key] = mean_out

    obs["region_activity"] = region_activity

    return obs
