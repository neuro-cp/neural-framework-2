import json
from pathlib import Path


class NeuralFrameworkLoader:
    """
    Loads neuron bases, region definitions, and profile JSON files from a project root.
    Compiles them into a single 'brain' dict used by BrainRuntime.

    Folder layout assumed (relative to root_path):
      neuron/        -> neuron base jsons
      regions/       -> region jsons (may be nested in subfolders)
      profiles/      -> profile jsons
      config/        -> global dynamics config json (preferred name: global_dynamics.json)

    Notes:
      - Region keys in the compiled brain are the JSON filenames (stems), not the internal 'region_id'.
      - Global dynamics config is loaded from config/global_dynamics.json, with fallback to
        config/global_config.json for backward compatibility.
    """

    def __init__(self, root_path: str | Path):
        self.root = Path(root_path)

        self.neuron_path = self.root / "neuron"
        self.regions_path = self.root / "regions"
        self.profiles_path = self.root / "profiles"
        self.config_path = self.root / "config"

        self.neuron_bases: dict = {}
        self.regions: dict = {}
        self.profiles: dict = {}

        self.compiled_brain: dict | None = None

    # ----------------------------
    # Low-level helpers
    # ----------------------------

    def _load_json(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_folder(self, folder: Path) -> dict:
        data = {}
        if not folder.exists():
            return data
        for file in folder.rglob("*.json"):
            data[file.stem] = self._load_json(file)
        return data

    # ----------------------------
    # Config
    # ----------------------------

    def load_global_dynamics(self) -> tuple[dict, str | None]:
        """
        Load global dynamics config.

        Returns:
          (config_dict, loaded_from_path_str_or_None)
        """
        candidates = [
            self.config_path / "global_dynamics.json",
            self.config_path / "global_config.json",   # backward-compat
            self.root / "global_dynamics.json",         # extra fallback
            self.root / "global_config.json",           # extra fallback
        ]
        for p in candidates:
            if p.exists():
                return self._load_json(p), str(p)
        return {}, None

    # ----------------------------
    # Load phases
    # ----------------------------

    def load_neuron_bases(self) -> None:
        self.neuron_bases = self._load_folder(self.neuron_path)

    def load_regions(self) -> None:
        self.regions = self._load_folder(self.regions_path)

    def load_profiles(self) -> None:
        self.profiles = self._load_folder(self.profiles_path)

    # ----------------------------
    # Validation
    # ----------------------------

    def validate(self) -> None:
        if not self.neuron_bases:
            raise RuntimeError("Neuron bases not loaded (neuron/ is empty or missing).")
        if not self.regions:
            raise RuntimeError("Regions not loaded (regions/ is empty or missing).")

    # ----------------------------
    # Compilation
    # ----------------------------

    def compile(
        self,
        expression_profile: str = "minimal",
        state_profile: str = "awake",
        compound_profile: str = "experimental",
    ) -> dict:
        """
        Compile the full brain dictionary.
        """
        self.validate()

        global_dyn, global_dyn_path = self.load_global_dynamics()

        self.compiled_brain = {
            "neuron_bases": self.neuron_bases,
            "regions": self.regions,
            "expression_profile": self.profiles.get(expression_profile),
            "state_profile": self.profiles.get(state_profile),
            "compound_profile": self.profiles.get(compound_profile),
            "global_dynamics": global_dyn,
            "global_dynamics_loaded_from": global_dyn_path,
        }

        return self.compiled_brain
