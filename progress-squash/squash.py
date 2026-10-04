"""Collapse carriage-return progress frames in captured terminal output.

A progress bar redraws one terminal line by writing ``\\r`` and the next frame. A terminal
shows only the last frame; captured output keeps every one of them, so a 300-step tqdm
loop reaches the model as 300 copies of the bar.

Within each ``\\n``-separated line, the ``\\r``-separated segments are grouped into runs of
the same progress line and each run is reduced to its last frame. Two segments belong to
the same run when their *stem* matches: the visible text before the first digit or bar
glyph (``"epoch:"``, ``"remote: Counting objects:"``). A segment with a different stem,
such as an error printed between two redraws, is kept on its own line. A ``\\r`` that ends a
line (``\\r\\n``) is a line ending, not a redraw, and is left alone.
"""

from __future__ import annotations

import re

# CSI / OSC / two-byte escapes. Hermes strips ANSI only after the transform hook, so
# erase-line codes (ESC[K, ESC[2K) still sit inside the frames here.
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
# Where the stem ends: a digit, or a glyph progress bars draw with.
_STEM_END = re.compile(r"[0-9#=>|\[▀-▟─-╿]")

def footer(n: int) -> str:
    return f"[progress-squash: {n} overwritten progress frame{'' if n == 1 else 's'} removed]"


def _stem(visible: str) -> str:
    match = _STEM_END.search(visible)
    return (visible[:match.start()] if match else visible).strip()


def _squash_line(line: str) -> tuple[str, int]:
    """One ``\\n``-free line -> (rendered line, frames dropped)."""
    kept: list[tuple[str, str]] = []  # (segment, stem)
    dropped = 0
    for segment in line.split("\r"):
        visible = _ANSI.sub("", segment)
        if not visible.strip():
            continue  # a bare redraw or erase-line code carries nothing to keep
        stem = _stem(visible)
        if kept and kept[-1][1] == stem:
            kept[-1] = (segment, stem)
            dropped += 1
        else:
            kept.append((segment, stem))
    if not dropped:
        return line, 0
    return "\n".join(segment for segment, _ in kept), dropped


def squash(output: str) -> str | None:
    """Return *output* with progress frames collapsed, or ``None`` when nothing changes."""
    if "\r" not in output:
        return None
    lines = output.split("\n")
    total = 0
    for i, line in enumerate(lines):
        ending = "\r" if line.endswith("\r") else ""
        body = line[:-1] if ending else line
        if "\r" not in body:
            continue
        rendered, dropped = _squash_line(body)
        if dropped:
            lines[i] = rendered + ending
            total += dropped
    if not total:
        return None
    result = "\n".join(lines)
    separator = "" if result.endswith("\n") else "\n"
    return f"{result}{separator}{footer(total)}"
