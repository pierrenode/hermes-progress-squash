"""progress-squash: show the model the progress bar a terminal shows, not every redraw.

Registers one ``transform_terminal_output`` hook. Hermes calls it with the captured output
of a terminal command (and, on newer releases, of background-process polls) before the
output limit and secret redaction run; the hook returns the output with carriage-return
progress frames collapsed (see ``squash.py``), or ``None`` to leave it byte-identical.
Pure string processing: no tools, network, files, subprocesses or settings.
"""

from __future__ import annotations

from .squash import squash


def _transform_terminal_output(output=None, **kwargs):
    if not isinstance(output, str):
        return None
    return squash(output)


def register(ctx) -> None:
    ctx.register_hook("transform_terminal_output", _transform_terminal_output)
