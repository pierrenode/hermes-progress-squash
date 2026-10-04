"""The plugin inside a real Hermes: run with Hermes importable (CI checks out the release
floor and main). Each test installs the plugin under a fresh HERMES_HOME, enables it with
the CLI and drives Hermes's own terminal tool in a separate process."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys

import pytest

from conftest import PLUGIN_DIR, progress_script

_PROBE = r"""
import json, sys
from tools.terminal_tool import terminal_tool
res = json.loads(terminal_tool(command=sys.argv[1], timeout=60))
print(json.dumps({"output": res.get("output", ""), "exit_code": res.get("exit_code")}))
"""

_BACKGROUND_PROBE = r"""
import json, sys
from hermes_cli.plugins import discover_plugins
from tools import process_registry
discover_plugins()
fn = getattr(process_registry, "transform_process_output", None)
out = None if fn is None else fn(sys.argv[1], command="tqdm", returncode=None, task_id="")
print(json.dumps({"supported": fn is not None, "output": out}))
"""


def _env(home) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "OPENAI", "ANTHROPIC"))}
    env["HERMES_HOME"] = str(home)
    return env


def _home(tmp_path, *, enabled: bool):
    home = tmp_path / ("with" if enabled else "without")
    home.mkdir()
    if enabled:
        shutil.copytree(PLUGIN_DIR, home / "plugins" / "progress-squash")
        subprocess.run([sys.executable, "-m", "hermes_cli.main", "plugins", "enable", "progress-squash"],
                       env=_env(home), check=True, capture_output=True, text=True, timeout=180,
                       stdin=subprocess.DEVNULL)
    return home


def _terminal(home, command: str) -> dict:
    proc = subprocess.run([sys.executable, "-c", _PROBE, command], env=_env(home), check=True,
                          capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _python_command(source: str) -> str:
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(source)}"


def test_terminal_tool_shows_the_final_frame(tmp_path):
    command = _python_command(progress_script(300))
    without = _terminal(_home(tmp_path, enabled=False), command)["output"]
    with_plugin = _terminal(_home(tmp_path, enabled=True), command)["output"]

    assert without.count("Downloading model.bin") == 301  # every redraw reaches the model
    assert with_plugin.splitlines() == [
        "Downloading model.bin |####################| 100%",
        "saved model.bin",
        "[progress-squash: 300 overwritten progress frames removed]",
    ]
    assert len(with_plugin) * 50 < len(without)


def test_output_without_carriage_returns_is_unchanged(tmp_path):
    command = _python_command("print('line one'); print('line two\\r'); print('done')")
    without = _terminal(_home(tmp_path, enabled=False), command)
    with_plugin = _terminal(_home(tmp_path, enabled=True), command)
    assert with_plugin == without


def test_background_process_output_is_collapsed_where_hermes_supports_it(tmp_path):
    home = _home(tmp_path, enabled=True)
    proc = subprocess.run([sys.executable, "-c", _BACKGROUND_PROBE, "pull 10%\rpull 60%\rpull 100%\n"],
                          env=_env(home), check=True, capture_output=True, text=True, timeout=180,
                          stdin=subprocess.DEVNULL)
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    if not result["supported"]:
        pytest.skip("this Hermes release does not pass background-process output through the hook")
    assert result["output"] == "pull 100%\n[progress-squash: 2 overwritten progress frames removed]"
