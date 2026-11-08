"""Finds the sung words and when each one is sung (WhisperX)."""

from __future__ import annotations

from pathlib import Path

from .audio import free_memory, load_audio, pick_device
from .lyrics import Word


def transcribe(vocals: Path, model_name: str = "turbo", language: str | None = None, device: str = "auto") -> list[Word]:
    """Words with start and end times, from the separated vocal track.

    Whisper first hears the words, then WhisperX's alignment model pins
    each word to the moment it's sung. Running it on the vocals alone,
    rather than the full mix, makes both steps far more accurate.
    """
    from .models import avoid_symlinks

    avoid_symlinks()
    import whisperx

    device = pick_device(device)
    compute_type = "float16" if device == "cuda" else "int8"
    audio = load_audio(vocals, rate=16000, channels=1)[0]

    model = whisperx.load_model(model_name, device, compute_type=compute_type, language=language)
    result = model.transcribe(audio, batch_size=8 if device == "cuda" else 4, language=language)
    lang = result.get("language") or language or "en"
    del model
    free_memory()

    align_model, metadata = whisperx.load_align_model(language_code=lang, device=device)
    aligned = whisperx.align(result["segments"], align_model, metadata, audio, device, return_char_alignments=False)

    words: list[Word] = []
    for segment in aligned["segments"]:
        seg_words = segment.get("words", [])
        for i, w in enumerate(seg_words):
            text = str(w.get("word", "")).strip()
            if not text:
                continue
            start, end = w.get("start"), w.get("end")
            if start is None or end is None:
                # Numbers and symbols can come back untimed: borrow from
                # neighbours, or the segment, and let the lyric matcher sort it.
                start = words[-1].end if words else float(segment.get("start", 0.0))
                nxt = next((x.get("start") for x in seg_words[i + 1 :] if x.get("start") is not None), None)
                end = nxt if nxt is not None else float(segment.get("end", start + 0.3))
            words.append(Word(text, float(start), float(end)))
    return words
