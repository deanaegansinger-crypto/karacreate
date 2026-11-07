import numpy as np

from karaoke_maker.cdg import CdgDecoder
from karaoke_maker.karaoke import SUNG, TITLE, UNSUNG, build_cdg
from karaoke_maker.lyrics import time_lyrics, Word


def song():
    lyric = ["Here comes the first line", "and here is the second one", "a third line to sing", "the final line"]
    rec, t = [], 10.0
    for line in lyric:
        for w in line.split():
            rec.append(Word(w.lower(), t, t + 0.4))
            t += 0.5
        t += 1.0
    return time_lyrics(lyric, rec)


def frame(data, t):
    d = CdgDecoder(data)
    d.seek(t)
    return d.pixels


def test_title_then_lines_then_wipe():
    lines = song()
    data = build_cdg(lines, 30.0, title="Test Song", artist="Someone")

    title = frame(data, 2.0)
    assert (title == TITLE).any() and (title == UNSUNG).any()

    before = frame(data, 9.0)  # lines showing, nothing sung yet
    assert (before == UNSUNG).any() and not (before == SUNG).any() and not (before == TITLE).any()

    mid = frame(data, 11.0)  # part way through the first line
    assert (mid == SUNG).any() and (mid == UNSUNG).any()

    end = frame(data, 29.0)  # everything sung
    assert (end == SUNG).any() and not (end == UNSUNG).any()


def test_wipe_follows_the_singing():
    rec = [Word(w, 10.0 + i * 0.5, 10.4 + i * 0.5) for i, w in enumerate("one two three four".split())]
    lines = time_lyrics(["one two", "three four"], rec)
    data = build_cdg(lines, 20.0)
    sung = [int((frame(data, t) == SUNG).sum()) for t in np.arange(9.5, 13, 0.1)]
    assert sung == sorted(sung)  # only ever grows while the lines are on screen
    assert sung[0] == 0 and sung[-1] > 0
    assert len(set(sung)) > 10  # a gradual wipe, not a jump per line


def test_sung_lines_make_way_for_later_ones():
    lines = song()  # wraps to six screen lines: more than fit
    data = build_cdg(lines, 30.0)
    assert (frame(data, 29.0) == SUNG).sum() > 0


def test_long_break_clears_the_screen():
    rec = [Word("one", 5.0, 6.0), Word("two", 60.0, 61.0)]
    lines = time_lyrics(["one", "two"], rec)
    data = build_cdg(lines, 70.0)
    assert not frame(data, 30.0).any()  # cleared during the break
    assert (frame(data, 56.0) == UNSUNG).any()  # next line back before singing


def test_long_lines_wrap_evenly():
    from karaoke_maker.layout import Layout

    layout = Layout()
    words = "Well I woke up this morning and the sun was in my eyes".split()
    parts = layout.wrap(words)
    assert [w for p in parts for w in p] == words
    assert all(layout.width(" ".join(p)) <= layout.max_width for p in parts)
    assert min(len(p) for p in parts) >= 2  # no word left on its own
