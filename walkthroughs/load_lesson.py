"""Load one local teaching snapshot; no upstream runtime or network access."""
import importlib.util
from pathlib import Path
import sys


def load(name):
    path = Path(__file__).resolve().parents[1] / 'lessons' / name / 'code.py'
    module_name = 'teaching_snapshot_' + name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
