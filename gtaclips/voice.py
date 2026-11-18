"""Remove the streamer's voice and keep the game audio (optional: demucs + resemblyzer).

Live platforms deliver ONE mixed audio track (streamer mic + game), so this takes two AI
steps: Demucs splits the mix into a voices stem and a game-sounds stem, then the speaker
step (speaker.py) works out which voice is the streamer and mutes only that one, so the
in-game characters' dialogue stays in.
"""
from __future__ import annotations

import json
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


def separate_stems(mix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(2, n) float32 mix -> (voices, everything_else), each (2, n) float32."""
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
            log.warning("voice separation on %s failed (%s), trying next device", dev, exc)
    else:
        raise RuntimeError(f"voice separation failed: {last_exc}")
    sources = (sources * std + mean).cpu().numpy().astype(np.float32)
    names = list(model.sources)
    vocals = sources[names.index("vocals")]
    rest = sources[[i for i, name in enumerate(names) if name != "vocals"]].sum(0)
    return vocals, rest


def remove_voice(src: Path, out_wav: Path, timeout: float = 300.0, key: str = "default",
                 keep_dialogue: bool = True) -> str:
    """Write ``out_wav`` = ``src`` audio with the streamer's voice removed.

    keep_dialogue=True  -> only the streamer is muted; in-game character dialogue stays
                           (needs the speaker model; otherwise all voices are removed).
    keep_dialogue=False -> all voices removed, game sounds only.

    Returns what was done: "game_only" (streamer removed, dialogue kept), "no_voices"
    (every voice removed) or "" if voice separation is unavailable/failed/too slow.
    """
    global _unhealthy_until
    from . import speaker

    want = "game_only" if keep_dialogue and speaker.available() else "no_voices"
    meta = out_wav.with_suffix(".json")
    if out_wav.exists() and out_wav.stat().st_size > 1000 and meta.exists():
        try:
            if json.loads(meta.read_text()).get("mode") == want:
                return want  # already made for this clip
        except ValueError:
            pass
    if not available() or time.time() < _unhealthy_until:
        return ""
    # Wait our turn (another clip may be separating); a stuck job trips _unhealthy_until.
    if not _lock.acquire(timeout=timeout):
        return ""
    result: dict = {}

    def work() -> None:
        try:
            vocals, rest = separate_stems(_stereo_pcm(src))
            if want == "game_only":
                gain, info = speaker.streamer_mask(vocals, RATE, key)
                out = rest + vocals * gain[None, :]
                result["info"] = info
            else:
                out = rest
            tmp = out_wav.with_suffix(".tmp.wav")
            _write_wav(tmp, out)
            tmp.replace(out_wav)
            meta.write_text(json.dumps({"mode": want, **result.get("info", {})}))
            result["mode"] = want
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
        return ""
    if "error" in result:
        log.warning("voice removal failed: %s", result["error"])
        return ""
    if result.get("info"):
        log.info("streamer voice removed in %s of %s talking bits (voice learned: %s)",
                 result["info"].get("streamer_segments"), result["info"].get("segments"), result["info"].get("learned"))
    return str(result.get("mode", ""))
