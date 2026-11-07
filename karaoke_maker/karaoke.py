"""Turns timed lyrics into a CD+G lyric screen.

The look: a black screen with big lyrics, a few lines at a time. Each word
changes colour as it's sung (a "wipe", one 6-pixel tile column at a time).
When a line has been sung, the line a screenful further on takes its
place, so the next lines are always showing. After a long instrumental
break the screen clears, and the next lines appear a few seconds before
the singing comes back in. An optional title screen shows at the start.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .cdg import HEIGHT, TILE_W, WIDTH, CdgWriter, parse_color
from .layout import Layout
from .lyrics import Line, Word

BACKGROUND = 0
UNSUNG = 1
SUNG = 2
TITLE = 3

LONG_BREAK = 10.0  # seconds without singing that clears the screen
CLEAR_AFTER = 2.0  # seconds after the last word before a break clears
LEAD_IN = 5.0  # seconds a fresh screen of lines shows before singing
REPLACE_AFTER = 0.4  # seconds after a line is sung before the next replaces it
MIN_TITLE = 3.0  # shortest time worth showing the title screen for


@dataclass
class Style:
    background: str = "#000000"
    unsung: str = "#ffffff"
    sung: str = "#3399ff"
    title: str = "#ffcc00"
    text_size: str = "large"
    font: str | None = None


@dataclass
class _Shown:
    words: list[Word]
    text: object  # layout.TextLine
    slot: int
    show_at: float

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end


def _column_times(shown: _Shown) -> dict[int, float]:
    """When each tile column of a line turns to the sung colour: words wipe
    left to right across their width, spaces turn when the next word starts."""
    cols = np.nonzero(shown.text.mask.any(axis=0))[0] // TILE_W
    times: dict[int, float] = {}
    spans = shown.text.spans
    for col in sorted(set(int(c) for c in cols)):
        x = col * TILE_W + TILE_W / 2
        t = None
        for (x0, x1), w in zip(spans, shown.words):
            if x < x0:
                t = w.start
                break
            if x <= x1:
                frac = (x - x0) / max(1, x1 - x0)
                t = w.start + frac * (w.end - w.start)
                break
        if t is None:
            t = shown.words[-1].end
        times[col] = max(t, shown.show_at)
    return times


def build_cdg(lines: list[Line], duration: float, title: str = "", artist: str = "", style: Style | None = None) -> bytes:
    style = style or Style()
    from .layout import TEXT_SIZES

    layout = Layout(style.font, TEXT_SIZES[style.text_size])
    palette = [parse_color(c) for c in (style.background, style.unsung, style.sung, style.title)]
    palette += [(0, 0, 0)] * (16 - len(palette))
    writer = CdgWriter(palette=palette, background=BACKGROUND)
    picture = np.full((HEIGHT, WIDTH), BACKGROUND, dtype=np.uint8)
    h = layout.slot_height

    # Break lyric lines into what fits across the screen.
    pieces: list[list[Word]] = []
    for line in lines:
        texts = layout.wrap([w.text for w in line.words])
        i = 0
        for t in texts:
            pieces.append(line.words[i : i + len(t)])
            i += len(t)

    events: list[tuple[float, int, object]] = []  # (time, order, action)
    CLEAR, SHOW, WIPE = 0, 1, 2

    # Title screen, if there's room for it before the singing starts.
    screen_free = 0.0
    if pieces and (title or artist):
        title_end = pieces[0][0].start - LEAD_IN
        if title_end >= MIN_TITLE:
            events.append((0.0, SHOW, ("title", title, artist)))
            events.append((title_end, CLEAR, None))
            screen_free = title_end

    shown: list[_Shown] = []
    epoch = 0
    for k, words in enumerate(pieces):
        if k > 0 and words[0].start - pieces[k - 1][-1].end > LONG_BREAK:
            clear_at = pieces[k - 1][-1].end + CLEAR_AFTER
            events.append((clear_at, CLEAR, None))
            screen_free = clear_at
            epoch = k
        pos = k - epoch
        if pos < layout.slots:
            show_at = max(screen_free, pieces[epoch][0].start - LEAD_IN)
        else:
            show_at = shown[k - layout.slots].end + REPLACE_AFTER
        s = _Shown(words, layout.render([w.text for w in words]), pos % layout.slots, show_at)
        shown.append(s)
        events.append((show_at, SHOW, ("line", s)))
        for col, t in _column_times(s).items():
            events.append((t, WIPE, (s, col)))

    events.sort(key=lambda e: (e[0], e[1]))

    for time, kind, payload in events:
        if kind == CLEAR:
            picture[:] = BACKGROUND
        elif kind == SHOW and payload[0] == "title":
            _draw_title(picture, layout, payload[1], payload[2])
        elif kind == SHOW:
            s = payload[1]
            y = layout.slot_top(s.slot)
            region = picture[y : y + h]
            region[:] = BACKGROUND
            region[s.text.mask] = UNSUNG
        else:
            s, col = payload
            y = layout.slot_top(s.slot)
            x = col * TILE_W
            region = picture[y : y + h, x : x + TILE_W]
            region[s.text.mask[:, x : x + TILE_W]] = SUNG
        writer.show(time, picture)

    return writer.finish(duration)


def _draw_title(picture: np.ndarray, layout: Layout, title: str, artist: str) -> None:
    lines: list[tuple[list[str], int]] = []
    for part in layout.wrap(title.split()) if title else []:
        lines.append((part, TITLE))
    if artist:
        if lines:
            lines.append(([], BACKGROUND))  # a gap between title and artist
        for part in layout.wrap(artist.split()):
            lines.append((part, UNSUNG))
    lines = lines[: layout.slots]
    first = (layout.slots - len(lines)) // 2
    h = layout.slot_height
    for i, (words, color) in enumerate(lines):
        if not words:
            continue
        y = layout.slot_top(first + i)
        region = picture[y : y + h]
        region[layout.render(words).mask] = color
