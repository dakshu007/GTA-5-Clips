"""Remove the streamer's voice and keep the game audio (optional dependency: demucs).

Live platforms deliver ONE mixed audio track (streamer mic + game), so the only way to
get "game audio only" is AI source separation. Demucs splits the mix into vocals and
everything else; we keep everything else. Note: it removes *all* speech, including
in-game character dialogue — engines, guns, music and explosions stay.
"""
from __future__ import annotations

import logging
import threading
import time
import wave
from pathlib import Path

import numpy as np

from . import media

log = logging.getLogger(__name__)

RATE = 44100
_model = None
_lock = threading.Lock()
_unhealthy_until = 0.0


def available() -> bool:
    try:
        import demucs  # noqa: F401
        import torch  # noqa: F401
    except Exception:
        return False
    return True


def _load_model():
    global _model
    if _model is None:
        from demucs.pretrained import get_model  # type: ignore

        log.info("loading voice-removal model (first run downloads ~80 MB)")
        _model = get_model("htdemucs")
        _model.eval()
    return _model


def _stereo_pcm(path: Path) -> np.ndarray:
    import subprocess

    proc = subprocess.run(
        [media.FFMPEG, "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "2", "-ar", str(RATE), "-f", "f32le", "pipe:1"],
        capture_output=True, timeout=300, start_new_session=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise media.MediaError("could not decode audio for voice removal")
    return np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2).T.copy()  # (2, n)


def _write_wav(path: Path, audio: np.ndarray) -> None:
    pcm = (np.clip(audio.T, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def separate_game_audio(mix: np.ndarray) -> np.ndarray:
    """(2, n) float32 mix -> (2, n) float32 with vocals removed."""
    import torch  # type: ignore
    from demucs.apply import apply_model  # type: ignore

    model = _load_model()
    wav = torch.from_numpy(mix)
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    wav = (wav - mean) / std
    devices = ["mps", "cpu"] if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else ["cpu"]
    last_exc: Exception | None = None
    for dev in devices:
        try:
            with torch.no_grad():
                sources = apply_model(model, wav[None], device=dev, split=True, overlap=0.1, progress=False)[0]
            break
        except Exception as exc:  # e.g. an op missing on Apple's MPS backend
            last_exc = exc
            log.warning("voice removal on %s failed (%s), trying next device", dev, exc)
    else:
        raise RuntimeError(f"voice removal failed: {last_exc}")
    sources = sources * std + mean
    keep = [i for i, name in enumerate(model.sources) if name != "vocals"]
    return sources[keep].sum(0).cpu().numpy().astype(np.float32)


def remove_voice(src: Path, out_wav: Path, timeout: float = 300.0) -> bool:
    """Write ``out_wav`` = ``src`` audio without voices. Returns False if unavailable/failed/too slow."""
    global _unhealthy_until
    if out_wav.exists() and out_wav.stat().st_size > 1000:
        return True
    if not available() or time.time() < _unhealthy_until:
        return False
    if not _lock.acquire(timeout=5):
        return False
    result: dict = {}

    def work() -> None:
        try:
            game = separate_game_audio(_stereo_pcm(src))
            tmp = out_wav.with_suffix(".tmp.wav")
            _write_wav(tmp, game)
            tmp.replace(out_wav)
            result["ok"] = True
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc
        finally:
            _lock.release()

    t = threading.Thread(target=work, daemon=True, name="voice-removal")
    t.start()
    t.join(timeout)
    if t.is_alive():
        _unhealthy_until = time.time() + 600
        log.warning("voice removal took longer than %.0fs — using original audio for now", timeout)
        return False
    if "error" in result:
        log.warning("voice removal failed: %s", result["error"])
        return False
    return bool(result.get("ok"))
