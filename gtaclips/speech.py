"""Speech-to-text with faster-whisper (optional dependency).

Gives word-level timestamps used for burned-in captions, the AI editor's context,
and the ``speech`` hype signal. If faster-whisper is not installed, everything
still works — clips just have no captions or transcript.
"""
from __future__ import annotations

import logging
import threading
import time
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


_unhealthy_until = 0.0


def _transcribe_locked(audio, model_name: str) -> list[dict]:
    model = _get_model(model_name)
    segments, _info = model.transcribe(audio, word_timestamps=True, vad_filter=True, beam_size=1)
    words: list[dict] = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                words.append({"w": text, "s": round(float(w.start), 2), "e": round(float(w.end), 2)})
    return words


def transcribe(path: str | Path, model_name: str = "base", start: float | None = None, length: float | None = None,
               timeout: float = 240.0) -> list[dict]:
    """Return [{w, s, e}] word timings (seconds, relative to ``start`` or the file start).

    Never blocks the render queue for long: if the model download or transcription takes
    longer than ``timeout`` (or another transcription is stuck), it gives up and returns
    no words so the clip still renders, just without captions.
    """
    global _unhealthy_until
    if not available() or time.time() < _unhealthy_until:
        return []
    from . import media

    audio = media.audio_pcm(path, start=start, length=length)
    if audio.size < 16000 * 0.5:
        return []
    # Wait our turn (another clip may be transcribing). A *stuck* job is caught by the
    # unhealthy flag above, which the caller that timed out sets for 10 minutes.
    if not _lock.acquire(timeout=timeout):
        log.warning("speech model busy/stuck — skipping captions for this clip")
        return []
    result: dict = {}

    def work() -> None:
        try:
            result["words"] = _transcribe_locked(audio, model_name)
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc
        finally:
            _lock.release()

    t = threading.Thread(target=work, daemon=True, name="whisper")
    t.start()
    t.join(timeout)
    if t.is_alive():
        # leave it running in the background (it holds the lock); skip speech for 10 min
        _unhealthy_until = time.time() + 600
        raise TimeoutError(f"speech-to-text took longer than {timeout:.0f}s (model download or slow CPU)")
    if "error" in result:
        raise result["error"]
    return result.get("words", [])


def words_to_text(words: list[dict]) -> str:
    return " ".join(w["w"] for w in words).strip()
