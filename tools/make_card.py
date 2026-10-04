"""Render docs/card.png, the 1200x600 catalog card.

Everything on the card is computed here from tests/fixtures/git-clone.txt (real
``git clone --progress`` output captured through Hermes's terminal tool) and the plugin's
own ``squash()``: the character counts, the number of frames removed, the raw frames shown
as "before" and the lines shown as "after". No Hermes install is needed.

    python tools/make_card.py --fonts /path/to/fonts

Fonts (OFL), from google/fonts at commit 9710da1eacb3be272583c3224dcb70f9da6eadbb:
    ofl/dmsans/DMSans[opsz,wght].ttf          -> DMSans.ttf
        sha256 8cd08d97e89c24d0aa92edd2f0f4c8ee6195eee9b7c9f154865a58b02f0c1c0d
    ofl/jetbrainsmono/JetBrainsMono[wght].ttf -> JetBrainsMono.ttf
        sha256 48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda

The plugin page hero crops the card to rows 110-490 at its widest; everything drawn here
must sit inside rows 132-468 (about 20px of air on each side), and the script asserts it.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1200, 600
BAND = (132, 468)
MARGIN_X = 96
FONT_SHA256 = {
    "DMSans.ttf": "8cd08d97e89c24d0aa92edd2f0f4c8ee6195eee9b7c9f154865a58b02f0c1c0d",
    "JetBrainsMono.ttf": "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda",
}

BG = (15, 17, 21)
PANEL = (24, 27, 33)
PANEL_EDGE = (44, 48, 56)
TEXT = (236, 238, 241)
MUTED = (150, 156, 166)
BEFORE = (240, 128, 120)
AFTER = (126, 214, 160)


def load_plugin():
    plugin_dir = ROOT / "progress-squash"
    spec = importlib.util.spec_from_file_location(
        "progress_squash_card", plugin_dir / "__init__.py", submodule_search_locations=[str(plugin_dir)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def font(path: Path, size: int, weight: int, opsz: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    f.set_variation_by_axes([opsz, weight] if opsz is not None else [weight])
    return f


def clip(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> str:
    if draw.textlength(text, font=f) <= width:
        return text
    while text and draw.textlength(text + "…", font=f) > width:
        text = text[:-1]
    return text + "…"


def draw_frames(d: ImageDraw.ImageDraw, xy, prefix: str, frames: list[str], f, width: int) -> None:
    """Draw frames joined by a muted literal "\\r", cut with "…" where the row runs out."""
    x, y = xy
    right = x + width - d.textlength("…", font=f)
    pieces = [(prefix, BEFORE)] if prefix else []
    for i, frame in enumerate(frames):
        if i:
            pieces.append(("\\r", MUTED))
        pieces.append((frame, BEFORE))
    for text, colour in pieces:
        for ch in text:
            w = d.textlength(ch, font=f)
            if x + w > right:
                d.text((x, y), "…", font=f, fill=BEFORE)
                return
            d.text((x, y), ch, font=f, fill=colour)
            x += w


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fonts", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "card.png")
    args = parser.parse_args()
    for name, digest in FONT_SHA256.items():
        actual = hashlib.sha256((args.fonts / name).read_bytes()).hexdigest()
        assert actual == digest, f"{name}: sha256 {actual} != pinned {digest}"

    plugin = load_plugin()
    with open(ROOT / "tests" / "fixtures" / "git-clone.txt", encoding="utf-8-sig", newline="") as fh:
        raw = fh.read()
    squashed = plugin.squash(raw)
    assert squashed is not None
    removed = int(re.search(r"\[progress-squash: (\d+) overwritten", squashed).group(1))

    # "Before": the run of "Resolving deltas" frames as the model receives it, each \r drawn as
    # the two characters "\r" in a muted colour.
    resolving = next(line for line in raw.split("\n") if line.startswith("Resolving deltas"))
    frames = resolving.split("\r")
    assert len(frames) > 3, "fixture no longer has a multi-frame Resolving deltas line"
    # "After": the same line and the footer, exactly as squash() returns them.
    after = [line for line in squashed.split("\n") if line.startswith("Resolving deltas")]
    assert after == [frames[-1]], after
    after.append(squashed.split("\n")[-1])

    dm = args.fonts / "DMSans.ttf"
    mono = args.fonts / "JetBrainsMono.ttf"
    title_f = font(dm, 58, 700, 36)
    sub_f = font(dm, 26, 400, 14)
    label_f = font(dm, 18, 600, 14)
    code_f = font(mono, 20, 400)

    ink = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ink)
    # The title's line box starts ~17px above its ink; this centres the ink in BAND.
    y = BAND[0] - 7
    d.text((MARGIN_X, y), "progress-squash", font=title_f, fill=TEXT)
    y += 74
    d.text((MARGIN_X, y), f"git clone --progress: {len(raw):,} → {len(squashed):,} characters for the model",
           font=sub_f, fill=MUTED)
    y += 50

    pad, line_h = 18, 30
    panel_top = y
    panel_bottom = panel_top + pad * 2 + 22 + line_h * 2 + 12 + 22 + line_h * len(after) - 6
    d.rounded_rectangle((MARGIN_X - 4, panel_top, W - MARGIN_X + 4, panel_bottom), radius=12,
                        fill=PANEL, outline=PANEL_EDGE, width=2)
    x = MARGIN_X + pad
    text_w = W - 2 * MARGIN_X - 2 * pad
    ty = panel_top + pad
    d.text((x, ty), f"BEFORE · {len(frames)} redraws of one line", font=label_f, fill=BEFORE)
    ty += 22
    # Two rows, each starting on a frame boundary: the first frames, then "…" and frames
    # from the middle of the run.
    for prefix, start in (("", 0), ("… ", len(frames) // 2)):
        draw_frames(d, (x, ty), prefix, frames[start:], code_f, text_w)
        ty += line_h
    ty += 12
    d.text((x, ty), f"AFTER · {removed} frames removed from the whole clone", font=label_f, fill=AFTER)
    ty += 22
    for line in after:
        d.text((x, ty), clip(d, line, code_f, text_w), font=code_f, fill=TEXT)
        ty += line_h

    left, top, right, bottom = ink.getbbox()
    assert BAND[0] <= top and bottom <= BAND[1], f"ink rows {top}-{bottom} outside {BAND}"
    assert 0 < left and right < W, f"ink columns {left}-{right} outside the card"

    card = Image.new("RGBA", (W, H), BG + (255,))
    card.alpha_composite(ink)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    card.convert("RGB").save(args.out, optimize=True)
    print(f"{args.out} ink rows {top}-{bottom}, columns {left}-{right}")
    print(f"  {len(raw)} -> {len(squashed)} chars, {removed} frames removed, {len(frames)} on the shown line")


if __name__ == "__main__":
    main()
