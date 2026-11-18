"""Thin wrappers around ffmpeg / ffprobe."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


class MediaError(RuntimeError):
    pass


def run(args: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        tail = proc.stderr.decode(errors="replace")[-1500:]
        raise MediaError(f"{Path(args[0]).name} failed ({proc.returncode}): {tail}")
    return proc


def probe(path: str | Path) -> dict:
    proc = run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], timeout=60)
    return json.loads(proc.stdout or b"{}")


def duration(path: str | Path) -> float:
    info = probe(path)
    try:
        return float(info["format"]["duration"])
    except (KeyError, ValueError):
        for st in info.get("streams", []):
            if st.get("duration"):
                return float(st["duration"])
    return 0.0


def video_size(path: str | Path) -> tuple[int, int]:
    for st in probe(path).get("streams", []):
        if st.get("codec_type") == "video":
            return int(st["width"]), int(st["height"])
    raise MediaError("no video stream")


def has_audio(path: str | Path) -> bool:
    return any(st.get("codec_type") == "audio" for st in probe(path).get("streams", []))


def audio_pcm(path: str | Path, start: float | None = None, length: float | None = None, rate: int = 16000) -> np.ndarray:
    """Decode audio to mono float32 PCM in [-1, 1]. Returns empty array if no audio."""
    args = [FFMPEG, "-v", "error", "-nostdin"]
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(path)]
    if length is not None:
        args += ["-t", f"{length:.3f}"]
    args += ["-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "pipe:1"]
    proc = subprocess.run(args, capture_output=True, timeout=600)
    if proc.returncode != 0 or not proc.stdout:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def gray_frames(
    path: str | Path,
    fps: float = 2.0,
    size: tuple[int, int] = (64, 36),
    start: float | None = None,
    length: float | None = None,
) -> np.ndarray:
    """Tiny grayscale frames, shape (n, h, w) uint8 — cheap input for motion analysis."""
    w, h = size
    args = [FFMPEG, "-v", "error", "-nostdin"]
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(path)]
    if length is not None:
        args += ["-t", f"{length:.3f}"]
    args += ["-an", "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "pipe:1"]
    proc = subprocess.run(args, capture_output=True, timeout=600)
    if proc.returncode != 0 or not proc.stdout:
        return np.zeros((0, h, w), dtype=np.uint8)
    buf = np.frombuffer(proc.stdout, dtype=np.uint8)
    n = buf.size // (w * h)
    return buf[: n * w * h].reshape(n, h, w)


def snapshot(path: str | Path, at: float, out: str | Path, width: int = 1280) -> Path:
    out = Path(out)
    run(
        [FFMPEG, "-v", "error", "-nostdin", "-y", "-ss", f"{max(0.0, at):.3f}", "-i", str(path),
         "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", str(out)],
        timeout=60,
    )
    return out
