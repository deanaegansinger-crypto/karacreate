"""MP4 karaoke video: the CD+G lyric screen played into a video with the
backing track, for anything that can't play MP3+CDG (TVs, phones, Windows'
own player)."""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

from .audio import NO_WINDOW, ffmpeg_exe
from .cdg import HEIGHT, PACKETS_PER_SECOND, PACKET_SIZE, WIDTH, CdgDecoder

FPS = 25


def render_mp4(cdg: bytes, audio: Path, dest: Path, title: str = "", artist: str = "", height: int = 720) -> None:
    """Write dest: 16:9 video, the 300x216 lyric screen scaled up and
    centred on black, with the audio."""
    decoder = CdgDecoder(cdg)
    seconds = len(cdg) / PACKET_SIZE / PACKETS_PER_SECOND
    frames = math.ceil(seconds * FPS)
    screen_w = round(height * WIDTH / HEIGHT / 2) * 2
    out_w = round(height * 16 / 9 / 2) * 2
    cmd = [
        ffmpeg_exe(), "-nostdin", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-vf", f"scale={screen_w}:{height}:flags=lanczos,pad={out_w}:{height}:(ow-iw)/2:0:black",
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
    ]
    if title:
        cmd += ["-metadata", f"title={title}"]
    if artist:
        cmd += ["-metadata", f"artist={artist}"]
    cmd.append(str(dest))
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, **NO_WINDOW)
    try:
        for i in range(frames):
            decoder.seek(i / FPS)
            proc.stdin.write(decoder.rgb().tobytes())
            if i % (FPS * 30) == 0:
                print(f"  video: {i // FPS // 60}:{i // FPS % 60:02d} of {int(seconds) // 60}:{int(seconds) % 60:02d}", flush=True)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0:
        sys.exit(f"Couldn't make the video {dest.name}:\n{err}")
