"""Downloading the AI models."""

from __future__ import annotations

import os


def avoid_symlinks() -> None:
    """Make the model downloader copy files instead of making symlinks.

    The Hugging Face downloader links files in its cache with symlinks.
    Windows only allows those for administrators or with Developer Mode on,
    and the downloader's own check for that can get it wrong, which ends in
    "WinError 1314: A required privilege is not held by the client". Copying
    always works; it just takes a little more disk space.
    """
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    if os.name != "nt":
        return
    try:
        from huggingface_hub import file_download
    except ImportError:
        return
    if hasattr(file_download, "are_symlinks_supported"):
        file_download.are_symlinks_supported = lambda *args, **kwargs: False


def download(whisper_model: str = "turbo", language: str = "en") -> None:
    """Fetch the word-recognition models now, so the first song doesn't wait."""
    avoid_symlinks()
    import whisperx
    from faster_whisper import WhisperModel

    print(f"Whisper {whisper_model}...", flush=True)
    WhisperModel(whisper_model, device="cpu", compute_type="int8")
    print(f"Word timing model ({language})...", flush=True)
    whisperx.load_align_model(language_code=language, device="cpu")
    print("Models ready.")
