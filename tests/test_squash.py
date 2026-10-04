"""The squash transform on its own (no Hermes install; runs on every OS in CI)."""

from __future__ import annotations

import re

import pytest

from conftest import PLUGIN_DIR, REPO_ROOT, fixture


@pytest.fixture(scope="module")
def squash(plugin):
    return plugin.squash


def test_tqdm_capture_keeps_only_the_final_bar(squash):
    raw = fixture("tqdm.txt")
    out = squash(raw)
    assert out.splitlines()[0] == "epoch: 100%|##########| 40/40"
    assert "\r" not in out
    assert len(out) < len(raw) // 10


def test_git_clone_capture_keeps_every_phase_and_the_remote_message(squash):
    raw = fixture("git-clone.txt")
    out = squash(raw)
    lines = out.splitlines()
    for phase in ("remote: Counting objects: 100% (11886/11886), done.",
                  "remote: Compressing objects: 100% (10624/10624), done.",
                  "Receiving objects: 100% (11886/11886)",
                  "Resolving deltas: 100% (167/167), done."):
        assert any(line.startswith(phase) for line in lines), phase
    # The remote's summary arrived between two "Receiving objects" redraws; it is a
    # different line and survives.
    assert any(line.startswith("remote: Total 11886") for line in lines)
    assert not any(re.match(r"Resolving deltas: +\d+% \(\d+/167\)$", line) for line in lines)
    assert "\r" not in out
    assert len(out) < len(raw) // 20


@pytest.mark.parametrize("text", [
    "plain output\nwith lines\n",
    "",
    "windows\r\nline endings\r\n",
    "\ronly one frame\n",
    "Downloading 10%\rERROR: disk full\rDownloading 20%\n",
])
def test_nothing_to_collapse_returns_none(squash, text):
    # None tells Hermes to keep the output byte-identical.
    assert squash(text) is None


def test_a_message_after_the_frames_is_kept(squash):
    out = squash("Downloading 10%\rDownloading 20%\rDownloading 30%\rERROR: disk full\n")
    assert out == "Downloading 30%\nERROR: disk full\n[progress-squash: 2 overwritten progress frames removed]"


def test_crlf_endings_survive_around_collapsed_frames(squash):
    out = squash("step 1/3\rstep 2/3\rstep 3/3\r\nnext\r\n")
    assert out == "step 3/3\r\nnext\r\n[progress-squash: 2 overwritten progress frames removed]"


def test_erase_line_codes_do_not_split_a_run(squash):
    raw = "\x1b[2K\rStep 1/3\x1b[K\r\x1b[2KStep 2/3\x1b[K\r\x1b[2KStep 3/3\x1b[K\ndone\n"
    out = squash(raw)
    assert out.splitlines()[:2] == ["\x1b[2KStep 3/3\x1b[K", "done"]
    assert out.endswith("[progress-squash: 2 overwritten progress frames removed]")


def test_a_bar_drawn_before_the_numbers_is_one_line(squash):
    # The bar fills up between frames; the stem must stop at its first glyph.
    raw = "\rget |#     | 10%\rget |###   | 50%\rget |######| 100%\n"
    assert squash(raw) == "get |######| 100%\n[progress-squash: 2 overwritten progress frames removed]"


def test_footer_is_singular_for_one_frame(squash):
    assert squash("a 1%\ra 2%").endswith("[progress-squash: 1 overwritten progress frame removed]")


def test_output_is_stable_under_a_second_pass(squash):
    once = squash(fixture("git-clone.txt"))
    assert squash(once) is None


def test_hook_ignores_non_string_output(plugin):
    assert plugin._transform_terminal_output(output=None) is None
    assert plugin._transform_terminal_output(output=b"a 1%\ra 2%") is None


def test_hook_accepts_every_payload_field(plugin):
    out = plugin._transform_terminal_output(command="tqdm", output="a 1%\ra 2%", returncode=0,
                                            task_id="", env_type="local", tool_call_id="call_1")
    assert out.startswith("a 2%\n")


def test_register_matches_the_manifest(plugin):
    registered = []

    class Ctx:
        def register_hook(self, name, callback):
            registered.append(name)

    plugin.register(Ctx())
    manifest = (PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8-sig")
    declared = re.findall(r"^  - (\w+)$", manifest.split("provides_hooks:", 1)[1], re.M)
    assert registered == declared == ["transform_terminal_output"]


def test_plugin_readme_is_the_repo_readme():
    # The catalog page renders <subdir>/README.md at the pinned commit.
    assert (PLUGIN_DIR / "README.md").read_bytes() == (REPO_ROOT / "README.md").read_bytes()
