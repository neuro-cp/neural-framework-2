# loader/loader.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List


# ============================================================
# TEMP DEBUG CONTROL
# ============================================================
ASSEMBLY_DOWNSCALE: float = 0.01
# ============================================================


class NeuralFrameworkLoader:
    """
    Loads neuron bases, region definitions, profile JSON files,
    and global configuration. Produces a compiled, semantically
    resolved brain definition with deferred routing logic.
    """

    # ----------------------------
    # Init
    # ----------------------------

    def __init__(self, root_path: str | Path):
        self.root = Path(root_path)

        self.neuron_path = self.root / "neuron"
        self.regions_path = self.root / "regions"
        self.profiles_path = self.root / "profiles"
        self.config_path = self.root / "config"

        self.neuron_bases: Dict[str, Any] = {}
        self.regions: Dict[str, Any] = {}
        self.profiles: Dict[str, Any] = {}

        self.brain_map: Optional[Dict[str, Any]] = None
        self.region_aliases: Optional[Dict[str, Any]] = None
        self.routing_defaults: Optional[Dict[str, Any]] = None

        # Canonical resolution tables
        self._alias_to_group: Dict[str, str] = {}
        self._group_to_regions: Dict[str, List[str]] = {}

        self.compiled_brain: Optional[Dict[str, Any]] = None

    # ----------------------------
    # File helpers
    # ----------------------------

    def _load_json(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_folder(self, folder: Path) -> dict:
        data: Dict[str, Any] = {}
        if not folder.exists():
            return data

        for file in folder.rglob("*.json"):
            key = file.stem
            if key in data:
                rel = str(file.relative_to(folder)).replace("\\", "/")
                raise RuntimeError(
                    f"Duplicate JSON stem '{key}' under {folder} (conflict at: {rel})"
                )
            data[key] = self._load_json(file)

        return data

    # ----------------------------
    # Region identity helpers
    # ----------------------------

    @staticmethod
    def _is_base_region(region_id: str) -> bool:
        return region_id.endswith("_base")

    def _build_alias_tables(self) -> None:
        """
        Build deterministic alias tables.
        Aliases map -> semantic group, never directly to regions.
        """
        self._alias_to_group.clear()
        self._group_to_regions.clear()

        if not self.region_aliases:
            return

        aliases = self.region_aliases.get("aliases", {})
        for group, names in aliases.items():
            group_key = group.upper()
            self._group_to_regions[group_key] = []

            for name in names:
                self._alias_to_group[name.lower()] = group_key

        # Populate group → concrete region list
        for region_id, blob in self.regions.items():
            if self._is_base_region(region_id):
                continue

            parent = (blob.get("parent_region") or "").upper()
            if parent in self._group_to_regions:
                self._group_to_regions[parent].append(region_id)

            # Allow region_id itself as alias
            self._alias_to_group[region_id.lower()] = region_id.lower()

    def resolve_region_group(self, name: str) -> Optional[str]:
        """
        Resolve an alias to a semantic group name (uppercase),
        or None if unknown.
        """
        if not name:
            return None
        return self._alias_to_group.get(name.lower())

    def expand_region_group(self, group: str) -> List[str]:
        """
        Expand a semantic group into concrete regions.
        Never returns base regions.
        """
        if not group:
            return []
        return list(self._group_to_regions.get(group.upper(), []))

    def resolve_concrete_region(self, name: str) -> Optional[str]:
        """
        Resolve a name to a concrete region ID.
        Exact match only. Base regions are never returned.
        """
        if not name:
            return None

        key = name.lower()
        if key in self.regions and not self._is_base_region(key):
            return key

        return None

    # ----------------------------
    # Config loading
    # ----------------------------

    def load_global_dynamics(self) -> Tuple[dict, Optional[str]]:
        candidates = [
            self.config_path / "global_dynamics.json",
            self.config_path / "global_config.json",
            self.root / "global_dynamics.json",
            self.root / "global_config.json",
        ]
        for p in candidates:
            if p.exists():
                return self._load_json(p), str(p)
        return {}, None

    def load_routing_defaults(self) -> Optional[dict]:
        path = self.config_path / "routing_defaults.json"
        if path.exists():
            return self._load_json(path)
        return None

    # ----------------------------
    # Load phases
    # ----------------------------

    def load_neuron_bases(self) -> None:
        self.neuron_bases = self._load_folder(self.neuron_path)

    def load_regions(self) -> None:
        self.regions.clear()
        self.brain_map = None
        self.region_aliases = None

        if not self.regions_path.exists():
            return

        for file in self.regions_path.rglob("*.json"):
            blob = self._load_json(file)
            t = str(blob.get("type", "") or "")

            if t == "BrainMap":
                self.brain_map = blob
                continue

            if t == "RegionAliasRegistry":
                self.region_aliases = blob
                continue

            if ASSEMBLY_DOWNSCALE != 1.0:
                pops = blob.get("populations")
                if isinstance(pops, dict):
                    for pop in pops.values():
                        if isinstance(pop, dict) and "count" in pop:
                            try:
                                original = int(pop["count"])
                                pop["count"] = max(
                                    1, int(round(original * ASSEMBLY_DOWNSCALE))
                                )
                            except Exception:
                                pass

            key = file.stem
            if key in self.regions:
                rel = str(file.relative_to(self.regions_path)).replace("\\", "/")
                raise RuntimeError(
                    f"Duplicate region stem '{key}' under regions/ (conflict at: {rel})"
                )

            self.regions[key] = blob

        self._build_alias_tables()

    def load_profiles(self) -> None:
        self.profiles = self._load_folder(self.profiles_path)

    # ----------------------------
    # Validation
    # ----------------------------

    def validate(self) -> None:
        if not self.neuron_bases:
            raise RuntimeError("Neuron bases not loaded.")
        if not self.regions:
            raise RuntimeError("Regions not loaded.")

    # ----------------------------
    # Routing resolution (deferred)
    # ----------------------------

    def resolve_routing_target(
        self,
        abstract_target: str,
        source_region: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolve an abstract target (e.g. THALAMUS, CORTEX) to a concrete
        region using routing defaults. Does not mutate structure.
        """
        if not self.routing_defaults or not abstract_target:
            return None

        rules = self.routing_defaults.get("rules", {})
        rule = rules.get(abstract_target.upper())
        if not rule:
            return None

        # Contextual resolution (sensory / motor)
        if context and isinstance(rule, dict):
            ctx = rule.get(context)
            if isinstance(ctx, dict) and source_region:
                return ctx.get(source_region.upper())
            if isinstance(ctx, str):
                return ctx

        # Default / fallback
        if isinstance(rule, dict):
            return rule.get("default_target") or rule.get("fallback")

        return None

    # ----------------------------
    # Compilation
    # ----------------------------

    def compile(
        self,
        expression_profile: str = "minimal",
        state_profile: str = "awake",
        compound_profile: str = "experimental",
    ) -> dict:
        self.validate()

        global_dyn, global_dyn_path = self.load_global_dynamics()
        self.routing_defaults = self.load_routing_defaults()

        self.compiled_brain = {
            "neuron_bases": self.neuron_bases,
            "regions": self.regions,
            "profiles": {
                "expression": self.profiles.get(expression_profile),
                "state": self.profiles.get(state_profile),
                "compound": self.profiles.get(compound_profile),
            },
            "brain_map": self.brain_map,
            "region_aliases": self.region_aliases,
            "alias_tables": {
                "alias_to_group": self._alias_to_group,
                "group_to_regions": self._group_to_regions,
            },
            "routing_defaults": self.routing_defaults,
            "routing_resolver": self.resolve_routing_target,
            "global_dynamics": global_dyn,
            "global_dynamics_loaded_from": global_dyn_path,
            "assembly_downscale": ASSEMBLY_DOWNSCALE,
        }

        return self.compiled_brain
