from __future__ import annotations

import importlib
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

    If no differentiation file exists for a region, nothing happens.
    """

    BASE_PATH = Path(__file__).resolve().parent

    @classmethod
    def apply(cls, *, runtime) -> None:
        """
        Apply differentiation to all regions that define it.
        """
        region_map = cls._collect_region_assemblies(runtime)

        for region_name, assemblies in region_map.items():
            module = cls._load_region_module(region_name)
            if module is None:
                continue

            if not hasattr(module, "differentiate"):
                raise RuntimeError(
                    f"[assembly_differentiation] "
                    f"{region_name}.py exists but defines no `differentiate()`"
                )

            module.differentiate(
                region_name=region_name,
                assemblies=assemblies,
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

    @staticmethod
    def _region_seed(region_name: str) -> int:
        """
        Stable region-level seed.
        """
        return hash(("assembly_differentiation", region_name))
