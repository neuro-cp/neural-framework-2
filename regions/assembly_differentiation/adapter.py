from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Dict, List

from engine.population_model import PopulationModel


# ============================================================
# Assembly Differentiation Adapter
# ============================================================

class AssemblyDifferentiationAdapter:
    """
    Compile-time assembly differentiation.

    This adapter:
    - Runs AFTER assemblies are created
    - Runs BEFORE runtime stepping
    - Applies deterministic, region-scoped structural traits
    - Never touches dynamic state (activity, output)
    - Is a pure function of assembly identity

    Structural authority is defined by config/assembly_control.json.
    """

    # Path: neural framework/regions/assembly_differentiation/
    BASE_PATH = Path(__file__).resolve().parent

    # Path: neural framework/config/assembly_control.json
    CONTROL_PATH = (
        Path(__file__).resolve().parents[2] / "config" / "assembly_control.json"
    )

    # --------------------------------------------------------
    # Public entry point
    # --------------------------------------------------------

    @classmethod
    def apply(cls, *, runtime) -> None:
        """
        Apply differentiation to all structurally-declared regions.
        """
        region_map = cls._collect_region_assemblies(runtime)
        control = cls._load_assembly_control()

        for region_name, assemblies in region_map.items():
            # Only regions declared in control file may differentiate
            expected_n = control.get(region_name)
            if expected_n is None:
                continue

            module = cls._load_region_module(region_name)
            if module is None:
                continue

            if not hasattr(module, "differentiate"):
                raise RuntimeError(
                    f"[assembly_differentiation] "
                    f"{region_name}.py exists but defines no `differentiate()`"
                )

            # Bound assemblies to declared structural count
            if len(assemblies) <= expected_n:
                bounded = assemblies
            else:
                bounded = assemblies[:expected_n]

            module.differentiate(
                region_name=region_name,
                assemblies=bounded,
                seed=cls._region_seed(region_name),
            )

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    @classmethod
    def _collect_region_assemblies(
        cls,
        runtime,
    ) -> Dict[str, List[PopulationModel]]:
        """
        Gather assemblies grouped by region.
        """
        regions: Dict[str, List[PopulationModel]] = {}

        for region_name, region_state in runtime.region_states.items():
            pops = region_state.get("populations", {}) or {}
            for plist in pops.values():
                for assembly in plist:
                    regions.setdefault(region_name, []).append(assembly)

        return regions

    @classmethod
    def _load_region_module(cls, region_name: str):
        """
        Load regions/assembly_differentiation/<region>.py if it exists.
        """
        module_path = cls.BASE_PATH / f"{region_name}.py"
        if not module_path.exists():
            return None

        return importlib.import_module(
            f"regions.assembly_differentiation.{region_name}"
        )

    @classmethod
    def _load_assembly_control(cls) -> Dict[str, int]:
        """
        Load canonical assembly counts per region.
        """
        if not cls.CONTROL_PATH.exists():
            raise RuntimeError(
                "[assembly_differentiation] config/assembly_control.json not found"
            )

        with open(cls.CONTROL_PATH, "r") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise RuntimeError(
                "[assembly_differentiation] assembly_control.json must map region -> int"
            )

        return data

    @staticmethod
    def _region_seed(region_name: str) -> int:
        """
        Stable region-level seed.
        """
        return hash(("assembly_differentiation", region_name))
