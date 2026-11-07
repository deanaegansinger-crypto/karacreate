"""karaoke-maker: turn a song (with vocals) into an MP3+CDG karaoke track.

  prepare SONG   split off the vocals, find the words and their timings,
                 and write a lyrics.txt to check
  build WORKDIR  make the MP3+CDG from the (corrected) lyrics.txt
  make SONG      both in one go, without stopping to check the lyrics
  preview CDG    save a picture of the karaoke screen at a given time
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

WORK_SUFFIX = " (karaoke work)"
VOCALS = "vocals.wav"
MUSIC = "instrumental.wav"
WORDS = "words.json"
LYRICS = "lyrics.txt"
INFO = "info.json"

LYRICS_HELP = """\
# Check the lyrics below against the video, fix any wrong words, then save
# and close this window. Keep one sung line per line: each line here is a
# line on the karaoke screen (long ones wrap). Words you add or change get
# their timing from the words around them.
# Lines starting with # and blank lines are ignored.
#
"""

# Bits YouTube uploads put in their names that aren't part of the title.
JUNK = re.compile(
    r"\s*[\(\[][^\)\]]*(lyric|official|video|audio|visuali[sz]er|hd|4k|remaster)[^\)\]]*[\)\]]"
    r"|\s+-?\s*lyrics?\s*$",
    re.IGNORECASE,
)


def guess_title_artist(stem: str) -> tuple[str, str]:
    name = JUNK.sub("", stem).replace("_", " ").strip(" -")
    name = re.sub(r"\s+", " ", name)
    if " - " in name:
        artist, title = name.split(" - ", 1)
        return title.strip(), artist.strip()
    return name, ""


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .") or "karaoke"


def work_dir_for(song: Path) -> Path:
    return song.with_name(song.stem + WORK_SUFFIX)


def read_header(lyrics_path: Path) -> dict[str, str]:
    """'# Title: ...' and '# Artist: ...' lines at the top of lyrics.txt."""
    out = {}
    for raw in lyrics_path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"#\s*(title|artist)\s*:\s*(.*)$", raw.strip(), re.IGNORECASE)
        if m:
            out[m.group(1).lower()] = m.group(2).strip()
    return out


def cmd_prepare(args) -> Path:
    from .audio import free_memory, separate
    from .lyrics import draft_lines, load_words, read_lyrics, save_words
    from .transcribe import transcribe

    song = Path(args.song).resolve()
    if not song.is_file():
        sys.exit(f"File not found: {song}")
    work = Path(args.work).resolve() if args.work else work_dir_for(song)
    work.mkdir(parents=True, exist_ok=True)
    title, artist = guess_title_artist(song.stem)
    (work / INFO).write_text(json.dumps({"source": str(song), "title": title, "artist": artist}, indent=1), encoding="utf-8")

    if args.redo or not (work / MUSIC).exists() or not (work / VOCALS).exists():
        print(f"[1/2] Removing the vocals (Demucs {args.demucs_model}). This takes a few minutes...", flush=True)
        separate(song, work / VOCALS, work / MUSIC, model_name=args.demucs_model, device=args.device)
        free_memory()  # hand the vocal model's memory back before Whisper loads
    else:
        print("[1/2] Vocals already removed: skipping.")

    if args.redo or not (work / WORDS).exists():
        print(f"[2/2] Listening for the words (Whisper {args.whisper_model})...", flush=True)
        words = transcribe(work / VOCALS, model_name=args.whisper_model, language=args.language, device=args.device)
        save_words(work / WORDS, words)
    else:
        print("[2/2] Words already found: skipping.")
        words = load_words(work / WORDS)

    lyrics_path = work / LYRICS
    if args.lyrics:
        body = "\n".join(read_lyrics(Path(args.lyrics)))
    elif lyrics_path.exists() and not args.redo:
        print(f"Keeping your existing {lyrics_path}")
        return work
    else:
        body = "\n".join(draft_lines(words))
    lyrics_path.write_text(f"{LYRICS_HELP}# Title: {title}\n# Artist: {artist}\n\n{body}\n", encoding="utf-8")
    print(f"Lyrics to check: {lyrics_path}")
    return work


def cmd_build(args) -> list[Path]:
    from .audio import save_mp3, wav_duration
    from .karaoke import Style, build_cdg
    from .lyrics import load_words, read_lyrics, time_lyrics, write_lrc

    work = Path(args.work).resolve()
    for name in (MUSIC, WORDS, LYRICS):
        if not (work / name).exists():
            sys.exit(f"{work / name} is missing: run 'prepare' first.")
    info = json.loads((work / INFO).read_text(encoding="utf-8")) if (work / INFO).exists() else {}
    header = read_header(work / LYRICS)
    title = args.title or header.get("title") or info.get("title", "")
    artist = args.artist or header.get("artist") or info.get("artist", "")

    lines = time_lyrics(read_lyrics(work / LYRICS), load_words(work / WORDS))
    if not lines:
        sys.exit(f"No lyrics in {work / LYRICS}")
    duration = wav_duration(work / MUSIC)
    style = Style(sung=args.sung_color, unsung=args.unsung_color, text_size=args.text_size, font=args.font)
    cdg = build_cdg(lines, duration, title=title if args.title_screen else "", artist=artist if args.title_screen else "", style=style)

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (Path(info["source"]).parent if info.get("source") else work.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = safe_filename(f"{artist} - {title}" if artist else title or work.name)
    mp3, cdg_path, lrc = (out_dir / f"{base}.{ext}" for ext in ("mp3", "cdg", "lrc"))
    print("Making the MP3...", flush=True)
    save_mp3(work / MUSIC, mp3, title=title, artist=artist)
    cdg_path.write_bytes(cdg)
    outputs = [mp3, cdg_path]
    if args.lrc:
        write_lrc(lrc, lines, title, artist)
        outputs.append(lrc)
    print("Done:")
    for p in outputs:
        print(f"  {p}")
    if args.clean:
        shutil.rmtree(work)
    return outputs


def cmd_make(args) -> None:
    args.work = str(cmd_prepare(args))
    cmd_build(args)


def cmd_preview(args) -> None:
    from PIL import Image

    from .cdg import CdgDecoder

    dec = CdgDecoder(Path(args.cdg).read_bytes())
    dec.seek(args.at)
    img = Image.fromarray(dec.rgb()).resize((600, 432), Image.NEAREST)
    out = Path(args.output or f"{Path(args.cdg).stem} {args.at:.1f}s.png")
    img.save(out)
    print(out)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="karaoke-maker", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    def prepare_opts(sp):
        sp.add_argument("song", help="MP4, MP3 or any audio/video file of the song with vocals")
        sp.add_argument("--work", help="folder for the in-between files (default: next to the song)")
        sp.add_argument("--lyrics", help="a text file of the lyrics, one sung line per line, to use instead of the recognised words")
        sp.add_argument("--whisper-model", default="turbo", help="Whisper model: turbo (default), large-v3 (slower, needs more memory), small (fastest)")
        sp.add_argument("--language", help="the song's language code, e.g. en (default: detect)")
        sp.add_argument("--demucs-model", default="htdemucs", help="htdemucs (default) or htdemucs_ft (cleaner, 4x slower)")
        sp.add_argument("--device", default="auto", help="cuda (NVIDIA graphics card), cpu, or auto")
        sp.add_argument("--redo", action="store_true", help="start again even if earlier steps are done")

    def build_opts(sp):
        sp.add_argument("--out-dir", help="where to save the MP3+CDG (default: next to the song)")
        sp.add_argument("--title", help="song title (default: from lyrics.txt or the file name)")
        sp.add_argument("--artist", help="artist (default: from lyrics.txt or the file name)")
        sp.add_argument("--text-size", choices=["small", "large", "huge"], default="large", help="lyric size: 8, 5 or 4 lines on screen")
        sp.add_argument("--sung-color", default="#3399ff", help="colour words turn when sung (default #3399ff, blue)")
        sp.add_argument("--unsung-color", default="#ffffff", help="colour of words still to sing (default white)")
        sp.add_argument("--font", help="a .ttf font file (default: Arial Bold)")
        sp.add_argument("--no-title-screen", dest="title_screen", action="store_false", help="don't show the title at the start")
        sp.add_argument("--lrc", action="store_true", help="also save an .lrc timed-lyrics file")
        sp.add_argument("--clean", action="store_true", help="delete the work folder afterwards")

    sp = sub.add_parser("prepare", help="remove vocals and find the words")
    prepare_opts(sp)
    sp.set_defaults(func=cmd_prepare)

    sp = sub.add_parser("build", help="make the MP3+CDG from a work folder")
    sp.add_argument("work", help="the work folder 'prepare' made")
    build_opts(sp)
    sp.set_defaults(func=cmd_build)

    sp = sub.add_parser("make", help="prepare and build in one go")
    prepare_opts(sp)
    build_opts(sp)
    sp.set_defaults(func=cmd_make)

    sp = sub.add_parser("preview", help="save a picture of a CDG screen")
    sp.add_argument("cdg")
    sp.add_argument("--at", type=float, required=True, help="time in seconds")
    sp.add_argument("-o", "--output", help="PNG to write")
    sp.set_defaults(func=cmd_preview)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
