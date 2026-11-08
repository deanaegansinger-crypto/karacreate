"""Which files belong to one song.

A song can come as up to three files in one folder: the original with the
singing (say a YouTube download), and the backing track and vocals split
from it by lalal.ai or another program:

    Mustang Sally.mp4
    Mustang Sally_no_vocals_split_by_lalalai.mp3
    Mustang Sally_vocals_split_by_lalalai.mp3

Whichever of them is dragged in, :func:`find_song` finds the others. lalal.ai
shortens long names (".._Cover by B._no_vocals_split_by_lalalai.mp3"), so a
long split name only has to match the start of the original's name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".opus", ".mp4", ".mkv", ".webm", ".mov", ".avi"}
WORK_SUFFIX = " (karaoke work)"
SHORTENED_NAME = 30  # split names at least this long may be cut short

_SEP = r"[\s_\-.]"
SPLIT_SUFFIX = re.compile(
    rf"""{_SEP}*[(\[]?\s*
    (?P<what>no{_SEP}*vocals?|without{_SEP}+vocals?|instrumental|backing(?:{_SEP}+track)?|minus{_SEP}+one
       |lead{_SEP}+vocals?|vocals?|voice|a{_SEP}*cappella|acapella)
    \s*[)\]]?
    (?P<extra>(?:{_SEP}*[(\[]?\s*(?:split{_SEP}+by{_SEP}+lalal{_SEP}*ai|lalal{_SEP}*ai|stems?|only|isolated|version|track|\d+)\s*[)\]]?)*)
    {_SEP}*$""",
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class Split:
    base: str  # the song's name, as written before the split words
    kind: str  # "backing" or "vocals"
    by_lalal: bool


@dataclass
class Song:
    name: str
    folder: Path
    original: Path | None
    backing: Path | None
    vocals: Path | None

    @property
    def work(self) -> Path:
        return self.folder / (self.name + WORK_SUFFIX)


def plain(name: str) -> str:
    """Lower case with separators and brackets evened out, for comparing."""
    return re.sub(r"\s+", " ", re.sub(r"[_\-.()\[\]]+", " ", name.lower())).strip()


def split_name(stem: str) -> Split | None:
    m = SPLIT_SUFFIX.search(stem)
    if not m or m.start() == 0:
        return None
    what = m.group("what").lower()
    kind = "backing" if re.match(r"no|without|instrumental|backing|minus", what) else "vocals"
    return Split(stem[: m.start()].strip(" _-."), kind, "lalal" in m.group("extra").lower())


def same_song(original: str, base: str) -> bool:
    """Is base (from a split file's name) this original's name, or the start
    of it cut short?"""
    return original == base or (len(base) >= SHORTENED_NAME and original.startswith(base))


def is_karaoke_track(path: Path) -> bool:
    """An MP3 with a CDG of the same name: one of our finished tracks."""
    return path.with_suffix(".cdg").exists() or path.with_suffix(".CDG").exists()


def _audio_files(folder: Path) -> list[Path]:
    return [f for f in sorted(folder.iterdir()) if f.is_file() and f.suffix.lower() in AUDIO_EXTS and not is_karaoke_track(f)]


def find_song(path: Path) -> Song | None:
    """The song a dragged-in file belongs to, or None for a finished
    karaoke track."""
    if is_karaoke_track(path):
        return None
    files = _audio_files(path.parent)
    if path not in files:
        files.append(path)
    splits = {f: split_name(f.stem) for f in files}

    sp = splits[path]
    if sp:
        key = plain(sp.base)
        partners = [f for f in files if splits[f] and plain(splits[f].base) == key]
        originals = [f for f in files if f not in partners and same_song(plain(f.stem), key)]
        # A name merely ending in "Vocals" isn't a split file unless lalal.ai
        # named it, or the rest of the song is there too.
        if sp.by_lalal or len(partners) > 1 or originals:
            backing = next((f for f in partners if splits[f].kind == "backing"), None)
            vocals = next((f for f in partners if splits[f].kind == "vocals"), None)
            original = originals[0] if originals else None
            name = original.stem if original else sp.base
            return Song(name, path.parent, original, backing, vocals)

    key = plain(path.stem)
    backing = vocals = None
    for f in files:
        s = splits[f]
        if f == path or not s or not same_song(key, plain(s.base)):
            continue
        if s.kind == "backing":
            backing = backing or f
        else:
            vocals = vocals or f
    return Song(path.stem, path.parent, path, backing, vocals)
