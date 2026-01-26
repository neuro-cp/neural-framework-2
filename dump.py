from pathlib import Path

# ==============================
# CONFIG
# ==============================

# CHANGE THIS to your project root
PROJECT_ROOT = Path(r"C:\Users\Admin\Desktop\neural framework")

# Output file on Desktop
OUTPUT_FILE = Path.home() / "Desktop" / "STRUCTURE_DUMP_CHECKPOINT30.txt"

# Directories to ignore
IGNORE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    "env",
}

# File extensions to ignore (optional)
IGNORE_EXTS = {
    ".pyc",
    ".pyo",
}

# ==============================
# STRUCTURE DUMP
# ==============================

def dump_structure(root: Path, out_path: Path) -> None:
    lines = []

    for path in sorted(root.rglob("*")):
        # Skip ignored directories
        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        # Skip ignored file types
        if path.is_file() and path.suffix in IGNORE_EXTS:
            continue

        rel = path.relative_to(root)
        indent = "  " * (len(rel.parts) - 1)

        if path.is_dir():
            lines.append(f"{indent}{rel.name}/")
        else:
            lines.append(f"{indent}{rel.name}")

    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Structure dump written to:\n{out_path}")


if __name__ == "__main__":
    dump_structure(PROJECT_ROOT, OUTPUT_FILE)
