"""Fonts and text layout on the 300x216 CD+G screen."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .cdg import TILE_H, TILE_W, WIDTH

# Text stays inside the border: tile columns 1-48 and rows 1-16.
TEXT_LEFT = TILE_W
TEXT_WIDTH = WIDTH - 2 * TILE_W  # 288
TEXT_TOP_ROW = 1
TEXT_ROWS = 16
SIDE_MARGIN = 3  # pixels kept clear at each side of a line

FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    # Linux
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# Text sizes: how many 12-pixel tile rows each lyric line gets.
TEXT_SIZES = {"small": 2, "large": 3, "huge": 4}


def find_font(path: str | None = None) -> str | None:
    if path:
        if not Path(path).is_file():
            sys.exit(f"Font not found: {path}")
        return path
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None  # Pillow's built-in font


@lru_cache(maxsize=64)
def load_font(path: str | None, size: int) -> ImageFont.FreeTypeFont:
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def text_height(font) -> int:
    left, top, right, bottom = font.getbbox("ÁÉgjpqyHk", anchor="ls")
    return bottom - top


@lru_cache(maxsize=16)
def fit_font_size(path: str | None, box_height: int) -> int:
    """Largest font size whose tallest letters fit box_height pixels."""
    size = box_height
    while size > 6 and text_height(load_font(path, size)) > box_height - 2:
        size -= 1
    return size


@dataclass
class TextLine:
    """One line of text drawn into a slot: a mask the slot's size plus
    where each word sits across the screen."""

    mask: np.ndarray  # bool, (slot_rows * 12, 300)
    spans: list[tuple[int, int]]  # per word: (x start, x end) in screen pixels


class Layout:
    def __init__(self, font_path: str | None = None, slot_rows: int = 3) -> None:
        self.font_path = find_font(font_path)
        self.slot_rows = slot_rows
        self.slot_height = slot_rows * TILE_H
        self.slots = TEXT_ROWS // slot_rows
        self.font_size = fit_font_size(self.font_path, self.slot_height)
        self.max_width = TEXT_WIDTH - 2 * SIDE_MARGIN

    def slot_top(self, slot: int) -> int:
        """Top pixel row of a slot. Slots are centred down the screen and
        lined up with the tile rows, so a wipe never touches two lines."""
        spare = TEXT_ROWS - self.slots * self.slot_rows
        return (TEXT_TOP_ROW + spare // 2 + slot * self.slot_rows) * TILE_H

    def font(self, size: int | None = None):
        return load_font(self.font_path, size or self.font_size)

    def width(self, text: str, size: int | None = None) -> float:
        return self.font(size).getlength(text)

    def wrap(self, words: list[str]) -> list[list[str]]:
        """Split a line's words into as few lines as fit across the screen,
        with the lengths evened out rather than leaving one word alone."""
        greedy: list[list[str]] = []
        for w in words:
            if greedy and self.width(" ".join(greedy[-1] + [w])) <= self.max_width:
                greedy[-1].append(w)
            else:
                greedy.append([w])
        n, count = len(words), len(greedy)
        if count < 2:
            return greedy
        width = {(i, j): self.width(" ".join(words[i:j])) for i in range(n) for j in range(i + 1, n + 1)}
        # best[k][j]: (sum of squared line widths, cuts) for words[:j] in k
        # lines. With the number of lines fixed, the smallest sum of squares
        # is the most even split.
        inf = float("inf")
        best = [[(inf, [])] * (n + 1) for _ in range(count + 1)]
        best[0][0] = (0.0, [])
        for k in range(1, count + 1):
            for j in range(k, n + 1):
                for i in range(k - 1, j):
                    prev, cuts = best[k - 1][i]
                    w = width[(i, j)]
                    if prev == inf or (w > self.max_width and j - i > 1):
                        continue
                    score = prev + w * w
                    if score < best[k][j][0]:
                        best[k][j] = (score, cuts + [j])
        score, cuts = best[count][n]
        if score == inf:
            return greedy
        out, start = [], 0
        for c in cuts:
            out.append(words[start:c])
            start = c
        return out

    def render(self, words: list[str]) -> TextLine:
        """Draw words centred in a slot-sized mask, shrinking the font if
        a single long word doesn't fit."""
        text = " ".join(words)
        size = self.font_size
        while size > 8 and self.width(text, size) > self.max_width:
            size -= 1
        font = self.font(size)
        line_width = font.getlength(text)
        x0 = TEXT_LEFT + (TEXT_WIDTH - line_width) / 2
        img = Image.new("L", (WIDTH, self.slot_height), 0)
        draw = ImageDraw.Draw(img)
        # Centre on the letters' real height rather than the font's line box.
        _, top, _, bottom = font.getbbox("ÁÉgjpqyHk", anchor="ls")
        baseline = (self.slot_height - (bottom - top)) / 2 - top
        draw.text((x0, baseline), text, font=font, fill=255, anchor="ls")
        spans = []
        for i, w in enumerate(words):
            start = x0 + font.getlength(" ".join(words[:i]) + (" " if i else ""))
            spans.append((int(start), int(round(start + font.getlength(w)))))
        mask = np.asarray(img) >= 128
        return TextLine(mask=mask, spans=spans)
