# progress-squash

A Hermes plugin that collapses carriage-return progress bars in terminal output
to the frame a terminal would show, so the model reads one line instead of every
redraw.

## Why

A progress bar redraws its line by writing `\r` and the next frame. Your
terminal shows the last frame. Hermes captures the raw stream, so the model gets
all of them. Measured through Hermes's own `terminal` tool:

| Command | Output the model gets | With progress-squash |
|---|---|---|
| a 300-step `tqdm` loop | 17,396 characters | about 120 characters |
| `git clone --progress` of an 11,886-object repository | 18,308 characters | 519 characters |

The frames use up the turn's context and count against the terminal output limit
(`tool_output.max_bytes`, 50,000 characters by default) without telling the
model anything the last frame does not.

## What it does

For each line of output, the `\r`-separated frames of the same progress line are
reduced to the last one:

```
Receiving objects:   0% (1/11886)\rReceiving objects:   1% (119/11886)\r … \rReceiving objects: 100% (11886/11886), 67.61 MiB | 102.56 MiB/s, done.
```

becomes

```
Receiving objects: 100% (11886/11886), 67.61 MiB | 102.56 MiB/s, done.
[progress-squash: 396 overwritten progress frames removed]
```

Two frames belong to the same progress line when the text before their first
digit or bar character matches (`epoch:`, `Receiving objects:`). Anything else
written between redraws, such as an error or `git`'s `remote: Total …` summary,
is kept on its own line. The footer tells the model how many frames were
removed. If you see it in a transcript, the plugin did the rewrite.

Left as they are:

- output with no carriage return, byte for byte (the hook returns `None`);
- Windows line endings (`\r\n`);
- a line with a single frame, or with no two consecutive frames of the same
  progress line.

## Install

```bash
hermes plugins install progress-squash
hermes plugins enable progress-squash
```

Restart Hermes afterwards (CLI, gateway or desktop backend); hooks are registered
when plugins load. Nothing to configure.

## Where it applies

- Foreground `terminal` tool output: Hermes 0.21.0 and later.
- Background-process output (`process_manage` poll, wait and log results and
  completion notifications): Hermes 0.21.5 and later.

Hermes caps what it keeps of a command's output while it is still running (a
head/tail window of `tool_output.max_bytes`) and calls this hook afterwards.
Output the cap already dropped is gone before the plugin runs. The plugin saves
the tokens that remain; it does not bring back the middle of a very long log.

If another plugin also registers `transform_terminal_output`, Hermes uses the
first one that returns a string.

## Security and footprint

- `register()` registers one hook, `transform_terminal_output`. No tools,
  commands, middleware or settings.
- No network access, no subprocesses, no files read or written, no environment
  variables or credentials read.
- The hook only sees the output string Hermes passes it and returns a rewritten
  copy. Hermes redacts secrets after the hook, so nothing the plugin returns
  skips redaction.
- Pure Python standard library (`re`), no dependencies.

## Compatibility

Hermes 0.21.0 (`v2026.8.31`) or newer. CI runs the test suite against that
release and against Hermes `main` every day.

## Development

```bash
python -m pytest tests/test_squash.py                    # no Hermes needed
PYTHONPATH=../hermes-agent python -m pytest tests        # against a Hermes checkout
```

`tests/fixtures/` holds real `tqdm` and `git clone --progress` output captured
through Hermes's terminal tool, with its `\r` bytes intact. The Hermes tests
install the plugin under a fresh `HERMES_HOME`, enable it with the CLI and run a
command through the real terminal tool, with and without the plugin.

## License

MIT
