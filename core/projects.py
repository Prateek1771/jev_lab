"""Find the numbered project folders and import their experiments. Used by both UIs (app.py, api/)."""

import importlib
from functools import cache
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"   # projects/01_classification, … one folder per experiment


@cache
def discover() -> dict[str, ModuleType]:
    """{"01": module, ...} in folder order. Folder names start with a digit, so `import 01_classification` is a
    SyntaxError; importlib takes a string and does not care."""
    return {p.name[:2]: importlib.import_module(f"projects.{p.name}.experiment")
            for p in sorted(PROJECTS.glob("[0-9][0-9]_*")) if (p / "experiment.py").exists()}


def about_path(module: ModuleType) -> Path:
    return Path(module.__file__).parent / "about.md"


def traced(module: ModuleType) -> bool:
    """Multi-step projects set Result.trace_url; they are the ones that call trace_url()."""
    return "trace_url(" in Path(module.__file__).read_text(encoding="utf-8")
