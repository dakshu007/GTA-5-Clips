"""Speech-to-text with faster-whisper (optional dependency).

Gives word-level timestamps used for burned-in captions, the AI editor's context,
and the ``speech`` hype signal. If faster-whisper is not installed, everything
still works — clips just have no captions or transcript.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

_model = None
_model_name: str | None = None
_lock = threading.Lock()


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def _get_model(name: str):
    global _model, _model_name
    if _model is not None and _model_name == name:
        return _model
    from faster_whisper import WhisperModel  # type: ignore

    log.info("loading whisper model %s (first run downloads it)", name)
    _model = WhisperModel(name, device="auto", compute_type="int8", download_root=str(config.MODELS_DIR))
    _model_name = name
    return _model


def transcribe(path: str | Path, model_name: str = "base", start: float | None = None, length: float | None = None) -> list[dict]:
    """Return [{w, s, e}] word timings (seconds, relative to ``start`` or the file start)."""
    if not available():
        return []
    from . import media

    audio = media.audio_pcm(path, start=start, length=length)
    if audio.size < 16000 * 0.5:
        return []
    with _lock:  # whisper models aren't safe to share across threads concurrently
        model = _get_model(model_name)
        segments, _info = model.transcribe(audio, word_timestamps=True, vad_filter=True, beam_size=1)
        words: list[dict] = []
        for seg in segments:
            for w in seg.words or []:
                text = w.word.strip()
                if text:
                    words.append({"w": text, "s": round(float(w.start), 2), "e": round(float(w.end), 2)})
    return words


def words_to_text(words: list[dict]) -> str:
    return " ".join(w["w"] for w in words).strip()
