from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple


# ------------------------------------------------------------
# Config (tune freely)
# ------------------------------------------------------------

ACTIVE_THRESHOLD = 0.01
TOP_K = 10


# ------------------------------------------------------------
# Helpers (mirrors yesterday’s logic)
# ------------------------------------------------------------

def load_dump(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fraction_active(assemblies: List[Dict]) -> float:
    if not assemblies:
        return 0.0
    active = sum(1 for a in assemblies if a["output"] > ACTIVE_THRESHOLD)
    return active / len(assemblies)


def total_mass(assemblies: List[Dict]) -> float:
    return sum(a["output"] for a in assemblies)


def top_k_assemblies(
    assemblies: List[Dict],
    k: int,
) -> List[Tuple[str, float]]:
    rows = [
        (a["assembly_id"], a["output"])
        for a in assemblies
        if a["output"] > 0.0
    ]
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows[:k]


def tier_counts(assemblies: List[Dict]) -> Dict[str, int]:
    tiers = {
        "high": 0,   # strong recruitment
        "mid": 0,    # moderate
        "low": 0,    # weak but nonzero
        "zero": 0,   # silent
    }

    for a in assemblies:
        out = a["output"]
        if out > 0.2:
            tiers["high"] += 1
        elif out > 0.05:
            tiers["mid"] += 1
        elif out > 0.0:
            tiers["low"] += 1
        else:
            tiers["zero"] += 1

    return tiers


def overlap_fraction(
    top_a: List[Tuple[str, float]],
    top_b: List[Tuple[str, float]],
) -> float:
    if not top_a:
        return 0.0
    ids_a = {aid for aid, _ in top_a}
    ids_b = {aid for aid, _ in top_b}
    return len(ids_a & ids_b) / len(ids_a)


# ------------------------------------------------------------
# Main analysis
# ------------------------------------------------------------

def analyze_pair(baseline_path: Path, poke_path: Path) -> None:
    base = load_dump(baseline_path)
    poke = load_dump(poke_path)

    base_asm = base["assemblies"]
    poke_asm = poke["assemblies"]

    print("=" * 80)
    print(f"REGION: {base['region']}")
    print(f"BASELINE STEP: {base['step']}")
    print(f"POKE STEP: {poke['step']}")
    print("=" * 80)

    # -------------------------
    # Baseline stats
    # -------------------------

    base_mass = total_mass(base_asm)
    base_frac = fraction_active(base_asm)
    base_top = top_k_assemblies(base_asm, TOP_K)
    base_tiers = tier_counts(base_asm)

    print("\n[BASELINE]")
    print(f"Total mass:       {base_mass:.6f}")
    print(f"Fraction active:  {base_frac:.4f}")
    print(f"Tiers:            {base_tiers}")
    print("Top assemblies:")
    for aid, val in base_top:
        print(f"  {aid:<60} {val:.6f}")

    # -------------------------
    # Post-poke stats
    # -------------------------

    poke_mass = total_mass(poke_asm)
    poke_frac = fraction_active(poke_asm)
    poke_top = top_k_assemblies(poke_asm, TOP_K)
    poke_tiers = tier_counts(poke_asm)

    print("\n[POST-POKE]")
    print(f"Total mass:       {poke_mass:.6f}")
    print(f"Fraction active:  {poke_frac:.4f}")
    print(f"Tiers:            {poke_tiers}")
    print("Top assemblies:")
    for aid, val in poke_top:
        print(f"  {aid:<60} {val:.6f}")

    # -------------------------
    # Recruitment deltas
    # -------------------------

    overlap = overlap_fraction(base_top, poke_top)

    print("\n[RECRUITMENT SUMMARY]")
    print(f"Δ mass:           {poke_mass - base_mass:.6f}")
    print(f"Δ fraction:       {poke_frac - base_frac:.4f}")
    print(f"Top-K overlap:    {overlap:.4f}")
    print("=" * 80)


# ------------------------------------------------------------
# CLI entry
# ------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python recruitment_stats_from_dump.py <baseline.json> <poke.json>")
        sys.exit(1)

    analyze_pair(Path(sys.argv[1]), Path(sys.argv[2]))