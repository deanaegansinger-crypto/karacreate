"""Audio in and out (through FFmpeg) and vocal removal (Demucs)."""

from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np


def ffmpeg_exe() -> str:
    """FFmpeg on the PATH, or the copy that comes with imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("FFmpeg not found. Run Install.bat again, or install FFmpeg.")


def load_audio(path: Path, rate: int = 44100, channels: int = 2) -> np.ndarray:
    """Any audio or video file as float32 samples, shape (channels, n)."""
    cmd = [
        ffmpeg_exe(), "-nostdin", "-v", "error", "-i", str(path),
        "-vn", "-f", "f32le", "-ac", str(channels), "-ar", str(rate), "-",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        sys.exit(f"Couldn't read {path}:\n{result.stderr.decode(errors='replace')}")
    samples = np.frombuffer(result.stdout, dtype=np.float32)
    return samples.reshape(-1, channels).T.copy()


def save_wav(path: Path, audio: np.ndarray, rate: int = 44100) -> None:
    """Write (channels, n) float samples as 16-bit WAV."""
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").T.copy()
    with wave.open(str(path), "wb") as f:
        f.setnchannels(audio.shape[0])
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(pcm.tobytes())


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / f.getframerate()


def save_mp3(src: Path, dest: Path, title: str = "", artist: str = "", bitrate: str = "192k", copy: bool = False) -> None:
    """Encode src as MP3, or with copy=True take an MP3's audio unchanged
    and just set its title and artist."""
    codec = ["-map", "0:a", "-codec:a", "copy", "-map_metadata", "-1"] if copy else ["-codec:a", "libmp3lame", "-b:a", bitrate]
    cmd = [ffmpeg_exe(), "-nostdin", "-v", "error", "-y", "-i", str(src), *codec]
    if title:
        cmd += ["-metadata", f"title={title}"]
    if artist:
        cmd += ["-metadata", f"artist={artist}"]
    cmd.append(str(dest))
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        sys.exit(f"Couldn't write {dest}:\n{result.stderr.decode(errors='replace')}")


def pick_device(device: str = "auto") -> str:
    if device != "auto":
        return device
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def free_memory() -> None:
    """Give memory from a finished model back, so the next fits in 8 GB."""
    import gc

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def separate(path: Path, vocals_out: Path, music_out: Path, model_name: str = "htdemucs", device: str = "auto") -> None:
    """Split a song into its vocals and everything else (the backing track)."""
    from .models import avoid_symlinks

    avoid_symlinks()
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    device = pick_device(device)
    model = get_model(model_name)
    model.eval()
    rate = model.samplerate
    mix = torch.from_numpy(load_audio(path, rate=rate, channels=model.audio_channels))
    ref = mix.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    with torch.no_grad():
        sources = apply_model(model, ((mix - mean) / std)[None], device=device, shifts=1, split=True, overlap=0.25, progress=True)[0]
    sources = sources * std + mean
    vocal_index = model.sources.index("vocals")
    vocals = sources[vocal_index]
    music = sum(sources[i] for i in range(len(model.sources)) if i != vocal_index)
    save_wav(vocals_out, vocals.cpu().numpy(), rate)
    save_wav(music_out, music.cpu().numpy(), rate)
    del model, mix, sources, vocals, music
