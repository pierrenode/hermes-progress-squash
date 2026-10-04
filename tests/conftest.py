"""Shared helpers: the plugin loaded the way Hermes loads it, and the captured fixtures.

tests/fixtures/*.txt are real terminal-tool output captured through Hermes (tqdm and
``git clone --progress``); they keep their bare ``\\r`` bytes (see .gitattributes).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "progress-squash"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_plugin():
    name = "progress_squash_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fixture(name: str) -> str:
    with open(FIXTURES / name, encoding="utf-8-sig", newline="") as fh:
        return fh.read()


def progress_script(frames: int, label: str = "Downloading model.bin") -> str:
    """Python source that redraws one progress line *frames* times, then prints a result."""
    return (
        "import sys\n"
        f"for i in range({frames} + 1):\n"
        f"    sys.stdout.write('\\r{label} |' + '#' * (i * 20 // {frames}) + ' ' * (20 - i * 20 // {frames})"
        f" + '| ' + str(i * 100 // {frames}) + '%')\n"
        "    sys.stdout.flush()\n"
        "print('\\nsaved model.bin')\n"
    )


@pytest.fixture(scope="session")
def plugin():
    return load_plugin()
