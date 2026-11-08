"""karaoke-maker: turn a song (with vocals) into an MP3+CDG karaoke track.

  prepare SONG   split off the vocals, find the words and their timings,
                 and write a lyrics.txt to check
  build WORKDIR  make the MP3+CDG from the (corrected) lyrics.txt
  make SONG      both in one go, without stopping to check the lyrics
  batch FILES    any number of songs, checking each one's lyrics in turn
  preview CDG    save a picture of the karaoke screen at a given time
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from .songs import WORK_SUFFIX, Song, find_song  # noqa: F401

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
    name = JUNK.sub("", stem).replace("_", " ").replace(" – ", " - ").replace(" — ", " - ").strip(" -.")
    name = re.sub(r"\s+", " ", name)
    if " - " in name:
        artist, title = name.split(" - ", 1)
        return title.strip(), artist.strip()
    return name, ""


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .") or "karaoke"


def read_header(lyrics_path: Path) -> dict[str, str]:
    """'# Title: ...' and '# Artist: ...' lines at the top of lyrics.txt."""
    out = {}
    for raw in lyrics_path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"#\s*(title|artist)\s*:\s*(.*)$", raw.strip(), re.IGNORECASE)
        if m:
            out[m.group(1).lower()] = m.group(2).strip()
    return out


def _use_file(src: Path, dest: Path, label: str, song_seconds: float) -> None:
    from .audio import load_audio, save_wav

    audio = load_audio(src)
    seconds = audio.shape[1] / 44100
    if abs(seconds - song_seconds) > 1.0:
        print(f"  Warning: the {label} ({seconds:.1f}s) isn't the same length as the song ({song_seconds:.1f}s).\n"
              f"  If it was trimmed, the lyrics will be out of time with it.")
    save_wav(dest, audio)


def song_from_args(args) -> Song:
    """The song to work on: from the dragged-in file, plus any --backing and
    --vocals given."""
    path = Path(args.song).resolve()
    if not path.is_file():
        sys.exit(f"File not found: {path}")
    song = find_song(path)
    if song is None:
        sys.exit(f"{path.name} is already a finished karaoke track (it has a .cdg with it).")
    if getattr(args, "backing", None):
        song.backing = Path(args.backing).resolve()
    if getattr(args, "vocals", None):
        song.vocals = Path(args.vocals).resolve()
    return song


def cmd_prepare(args) -> Path:
    return prepare_song(song_from_args(args), args)


def prepare_song(song: Song, args) -> Path:
    from .audio import free_memory, load_audio, separate
    from .lyrics import draft_lines, load_words, read_lyrics, save_words
    from .transcribe import transcribe

    backing, vocals, original = song.backing, song.vocals, song.original
    for p in (backing, vocals):
        if p and not p.is_file():
            sys.exit(f"File not found: {p}")
    if not original and not (backing and vocals):
        have = backing or vocals
        sys.exit(f"Only found {have.name}. Put lalal.ai's other file (the "
                 f"{'vocals' if backing else 'no vocals'} one) next to it, or the original song with the singing.")
    for label, p in (("Song", original), ("Backing track", backing), ("Vocals", vocals)):
        if p:
            print(f"  {label}: {p.name}")
    work = Path(args.work).resolve() if getattr(args, "work", None) else song.work
    work.mkdir(parents=True, exist_ok=True)
    title, artist = guess_title_artist(song.name)

    old = json.loads((work / INFO).read_text(encoding="utf-8")) if (work / INFO).exists() else {}
    info = {"source": str(original or backing), "folder": str(song.folder), "title": title, "artist": artist,
            "backing": str(backing) if backing else None, "vocals": str(vocals) if vocals else None}
    # Starting again for a step if its input file changed (say, lalal.ai
    # files added after a first run with Demucs).
    redo_backing = args.redo or not (work / MUSIC).exists() or old.get("backing") != info["backing"]
    redo_vocals = args.redo or not (work / VOCALS).exists() or old.get("vocals") != info["vocals"]
    redo_words = args.redo or redo_vocals or not (work / WORDS).exists()
    (work / INFO).write_text(json.dumps(info, indent=1), encoding="utf-8")

    # Everything is lined up against the original, or the vocals without one.
    reference = original or vocals
    ref_seconds = load_audio(reference, rate=8000, channels=1).shape[1] / 8000 if (backing or vocals) else 0.0
    if backing and redo_backing:
        _use_file(backing, work / MUSIC, "backing track", ref_seconds)
    if vocals and redo_vocals:
        _use_file(vocals, work / VOCALS, "vocals file", ref_seconds)

    need_demucs = (not backing and redo_backing) or (not vocals and redo_vocals)
    if need_demucs:
        missing = " and ".join(n for n, have in (("no-vocals", backing), ("vocals", vocals)) if not have)
        print(f"No lalal.ai {missing} file found next to {original.name}.")
        print(f"[1/2] Removing the vocals with Demucs {args.demucs_model} instead. This is slower: a few minutes...", flush=True)
        tmp_vocals, tmp_music = work / "demucs vocals.wav", work / "demucs instrumental.wav"
        separate(original, tmp_vocals, tmp_music, model_name=args.demucs_model, device=args.device)
        free_memory()  # hand the vocal model's memory back before Whisper loads
        for tmp, final, keep_yours in ((tmp_vocals, work / VOCALS, vocals), (tmp_music, work / MUSIC, backing)):
            if keep_yours:
                tmp.unlink()  # yours is used instead
            else:
                tmp.replace(final)
    elif not (backing and vocals):
        print("[1/2] Vocals already removed: skipping.")
    else:
        print("[1/2] Using your split files: no need to remove the vocals.")

    if redo_words:
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

    folder = info.get("folder") or (str(Path(info["source"]).parent) if info.get("source") else None)
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (Path(folder) if folder else work.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = safe_filename(f"{artist} - {title}" if artist else title or work.name)
    inputs = {Path(p).resolve() for p in (info.get("source"), info.get("backing"), info.get("vocals")) if p}
    if (out_dir / f"{base}.mp3").resolve() in inputs:
        base += " (Karaoke)"  # never write over the song you started from
    mp3, cdg_path, lrc = (out_dir / f"{base}.{ext}" for ext in ("mp3", "cdg", "lrc"))
    print("Making the MP3...", flush=True)
    backing = info.get("backing")
    if backing and Path(backing).suffix.lower() == ".mp3" and Path(backing).is_file():
        # Already an MP3 (lalal.ai's are): keep it as it is, no re-encoding.
        save_mp3(Path(backing), mp3, title=title, artist=artist, copy=True)
    else:
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


def edit(path: Path) -> None:
    """Open the lyrics for checking and wait until the editor is closed."""
    import os
    import subprocess

    if os.name == "nt":
        subprocess.run(["notepad.exe", str(path)])
    else:
        input(f"Check {path}, then press Enter...")


def cmd_batch(args) -> None:
    """What Make Karaoke.bat runs: any mix of songs and their split files.
    The slow part runs for every song first, so it can be left; then each
    song's lyrics open in turn for checking before its files are made."""
    import traceback

    songs: dict[Path, Song] = {}
    for f in args.files:
        path = Path(f).resolve()
        if not path.is_file():
            print(f"Skipping {path.name}: not a file.")
            continue
        song = find_song(path)
        if song is None:
            print(f"Skipping {path.name}: it's already a finished karaoke track.")
        elif song.work not in songs:
            songs[song.work] = song

    failed: list[str] = []
    ready: list[Path] = []
    for song in songs.values():
        print(f"\n=== {song.name} ===", flush=True)
        try:
            ready.append(prepare_song(song, args))
        except SystemExit as e:
            print(e.code)
            failed.append(song.name)
        except Exception:
            traceback.print_exc()
            failed.append(song.name)

    made: list[str] = []
    for work in ready:
        name = work.name[: -len(WORK_SUFFIX)]
        print(f"\n=== {name}: check the lyrics in Notepad, then save and close it ===", flush=True)
        edit(work / LYRICS)
        args.work = str(work)
        try:
            cmd_build(args)
            made.append(name)
        except SystemExit as e:
            print(e.code)
            failed.append(name)
        except Exception:
            traceback.print_exc()
            failed.append(name)

    print()
    if made:
        print(f"Made {len(made)} karaoke track{'s' if len(made) != 1 else ''}: the MP3 and CDG files are next to the songs.")
    if failed:
        print("These didn't work, see the messages above: " + "; ".join(failed))
        sys.exit(1)


def cmd_make(args) -> None:
    work = cmd_prepare(args)
    if work:
        args.work = str(work)
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


def cmd_download_models(args) -> None:
    from .models import download

    download(args.whisper_model, args.language)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="karaoke-maker", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    def listening_opts(sp):
        sp.add_argument("--whisper-model", default="turbo", help="Whisper model: turbo (default), large-v3 (slower, needs more memory), small (fastest)")
        sp.add_argument("--language", help="the song's language code, e.g. en (default: detect)")
        sp.add_argument("--demucs-model", default="htdemucs", help="htdemucs (default) or htdemucs_ft (cleaner, 4x slower)")
        sp.add_argument("--device", default="auto", help="cuda (NVIDIA graphics card), cpu, or auto")
        sp.add_argument("--redo", action="store_true", help="start again even if earlier steps are done")

    def prepare_opts(sp):
        sp.add_argument("song", help="the song with vocals (MP4, MP3...), or one of its lalal.ai files")
        sp.add_argument("--work", help="folder for the in-between files (default: next to the song)")
        sp.add_argument("--backing", help="a backing track (vocals removed) from another program, e.g. lalal.ai, to use as the karaoke audio")
        sp.add_argument("--vocals", help="the vocals on their own from another program, e.g. lalal.ai, to time the lyrics from")
        sp.add_argument("--lyrics", help="a text file of the lyrics, one sung line per line, to use instead of the recognised words")
        listening_opts(sp)

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

    sp = sub.add_parser("batch", help="prepare, check and build any number of songs (what Make Karaoke.bat runs)")
    sp.add_argument("files", nargs="+", help="songs and/or their lalal.ai files, in any mix")
    listening_opts(sp)
    sp.add_argument("--lyrics", help=argparse.SUPPRESS)
    build_opts(sp)
    sp.set_defaults(func=cmd_batch)

    sp = sub.add_parser("preview", help="save a picture of a CDG screen")
    sp.add_argument("cdg")
    sp.add_argument("--at", type=float, required=True, help="time in seconds")
    sp.add_argument("-o", "--output", help="PNG to write")
    sp.set_defaults(func=cmd_preview)

    sp = sub.add_parser("download-models", help="fetch the AI models now (Install.bat does this)")
    sp.add_argument("--whisper-model", default="turbo")
    sp.add_argument("--language", default="en")
    sp.set_defaults(func=cmd_download_models)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
