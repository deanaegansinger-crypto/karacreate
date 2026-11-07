"""Lyrics and word timings.

The speech recogniser gives us words with times, but it mishears some of
them. The user corrects the lyrics as plain text, one sung line per text
line. :func:`time_lyrics` lines the corrected words up with the recognised
ones: matching words take the recognised times, and words the recogniser
got wrong or missed share out the time around them.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

MIN_WORD = 0.12  # seconds: shortest time a word gets highlighted over
LINE_GAP = 0.8  # seconds of silence that starts a new line in a draft
MAX_LINE_WORDS = 9


@dataclass
class Word:
    text: str
    start: float
    end: float

    def to_json(self) -> dict:
        return {"word": self.text, "start": round(self.start, 3), "end": round(self.end, 3)}


@dataclass
class Line:
    words: list[Word]

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


def normalise(word: str) -> str:
    """Lower case, accents and punctuation removed: what we compare on."""
    word = unicodedata.normalize("NFKD", word)
    word = "".join(c for c in word if not unicodedata.combining(c))
    return re.sub(r"[^\w]", "", word.lower())


def load_words(path: Path) -> list[Word]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Word(w["word"], float(w["start"]), float(w["end"])) for w in data]


def save_words(path: Path, words: list[Word]) -> None:
    Path(path).write_text(json.dumps([w.to_json() for w in words], indent=1, ensure_ascii=False), encoding="utf-8")


def read_lyrics(path: Path) -> list[str]:
    """Lyric lines from a text file. Blank lines and lines starting with #
    are skipped, so the user can leave notes and section gaps."""
    lines = []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            lines.append(s)
    return lines


def draft_lines(words: list[Word]) -> list[str]:
    """Split recognised words into lines for the user to correct: a new
    line after a pause or once a line gets long."""
    lines: list[list[Word]] = []
    for w in words:
        if not lines or w.start - lines[-1][-1].end > LINE_GAP or len(lines[-1]) >= MAX_LINE_WORDS:
            lines.append([])
        lines[-1].append(w)
    return [" ".join(w.text.strip() for w in line) for line in lines]


def time_lyrics(lyric_lines: list[str], recognised: list[Word]) -> list[Line]:
    """Give every word of the lyrics a start and end time."""
    tokens: list[tuple[int, str]] = []  # (line index, word as written)
    for i, text in enumerate(lyric_lines):
        for w in text.split():
            tokens.append((i, w))
    if not tokens:
        return []
    recognised = [w for w in recognised if normalise(w.text)]
    times: list[tuple[float, float] | None] = [None] * len(tokens)

    a = [normalise(w) for _, w in tokens]
    b = [normalise(w.text) for w in recognised]
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                r = recognised[j1 + k]
                times[i1 + k] = (r.start, r.end)
        elif op == "replace":
            # Misheard words: spread the recognised span over the real words.
            start, end = recognised[j1].start, recognised[j2 - 1].end
            _spread(times, tokens, i1, i2, start, end)

    _fill_gaps(times, tokens, recognised)
    _make_monotonic(times)

    lines: list[Line] = []
    for (line_no, text), t in zip(tokens, times):
        assert t is not None
        while line_no >= len(lines):
            lines.append(Line([]))
        lines[line_no].words.append(Word(text, t[0], t[1]))
    return [line for line in lines if line.words]


def _spread(times, tokens, i1: int, i2: int, start: float, end: float) -> None:
    weights = [max(1, len(normalise(tokens[i][1]))) for i in range(i1, i2)]
    total = sum(weights)
    t = start
    for i, wgt in zip(range(i1, i2), weights):
        d = (end - start) * wgt / total
        times[i] = (t, t + d)
        t += d


def _fill_gaps(times, tokens, recognised: list[Word]) -> None:
    """Words nothing matched get the time between their timed neighbours."""
    n = len(times)
    song_end = recognised[-1].end if recognised else 0.0
    i = 0
    while i < n:
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < n and times[j] is None:
            j += 1
        before = times[i - 1][1] if i > 0 else None
        after = times[j][0] if j < n else None
        count = j - i
        if before is None and after is None:
            before, after = 0.0, max(song_end, count * 0.5)
        elif before is None:
            before = max(0.0, after - count * 0.5)
        elif after is None:
            after = before + count * 0.5
        # A missing word right after a long gap (e.g. a line the recogniser
        # skipped after an instrumental) sits just before the next words,
        # not stretched across the gap.
        if after - before > count * 1.5:
            if i > 0 and tokens[i][0] == tokens[i - 1][0]:
                after = before + count * 0.5
            else:
                before = after - count * 0.5
        _spread(times, tokens, i, j, before, after)
        i = j


def _make_monotonic(times) -> None:
    prev_end = 0.0
    for k, (s, e) in enumerate(times):
        s = max(s, prev_end)
        e = max(e, s + MIN_WORD)
        times[k] = (s, e)
        prev_end = e


def write_lrc(path: Path, lines: list[Line], title: str = "", artist: str = "") -> None:
    """Enhanced LRC: line times plus <mm:ss.xx> word times."""

    def stamp(t: float) -> str:
        m, s = divmod(max(0.0, t), 60)
        return f"{int(m):02d}:{s:05.2f}"

    out = []
    if title:
        out.append(f"[ti:{title}]")
    if artist:
        out.append(f"[ar:{artist}]")
    for line in lines:
        words = " ".join(f"<{stamp(w.start)}>{w.text}" for w in line.words)
        out.append(f"[{stamp(line.start)}]{words}")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
