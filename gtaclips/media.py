"""Thin wrappers around ffmpeg / ffprobe."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


class MediaError(RuntimeError):
    pass


def run(args: list[str], timeout: float | None = None, cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    # own session: a Ctrl+C on the server must not kill a cut/render half way
    proc = subprocess.run(args, capture_output=True, timeout=timeout, start_new_session=True, cwd=cwd)
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


_hwaccels: set[str] | None = None
_hwdec_broken = False


def hw_decode_args() -> list[str]:
    """On a Mac, decode video with the VideoToolbox chip (frees the CPU for everything else)."""
    global _hwaccels
    if _hwdec_broken or sys.platform != "darwin":
        return []
    if _hwaccels is None:
        try:
            out = subprocess.run([FFMPEG, "-hide_banner", "-hwaccels"], capture_output=True, timeout=30).stdout.decode(errors="replace")
            _hwaccels = {line.strip() for line in out.splitlines()[1:] if line.strip()}
        except Exception:
            _hwaccels = set()
    return ["-hwaccel", "videotoolbox"] if "videotoolbox" in _hwaccels else []


def gray_frames(
    path: str | Path,
    fps: float = 2.0,
    size: tuple[int, int] = (64, 36),
    start: float | None = None,
    length: float | None = None,
) -> np.ndarray:
    """Tiny grayscale frames, shape (n, h, w) uint8 — cheap input for motion analysis."""
    global _hwdec_broken
    w, h = size

    def attempt(dec: list[str]) -> bytes:
        args = [FFMPEG, "-v", "error", "-nostdin", *dec]
        if start is not None:
            args += ["-ss", f"{start:.3f}"]
        args += ["-i", str(path)]
        if length is not None:
            args += ["-t", f"{length:.3f}"]
        args += ["-an", "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "pipe:1"]
        proc = subprocess.run(args, capture_output=True, timeout=600, start_new_session=True)
        return proc.stdout if proc.returncode == 0 else b""

    dec = hw_decode_args()
    data = attempt(dec)
    if not data and dec:
        data = attempt([])
        if data:
            _hwdec_broken = True  # hardware decode doesn't work on this machine; stop trying
    if not data:
        return np.zeros((0, h, w), dtype=np.uint8)
    buf = np.frombuffer(data, dtype=np.uint8)
    n = buf.size // (w * h)
    return buf[: n * w * h].reshape(n, h, w)


_filters: set[str] | None = None


def has_filter(name: str) -> bool:
    """Whether this ffmpeg build includes a filter (e.g. 'subtitles' needs libass)."""
    global _filters
    if _filters is None:
        try:
            out = subprocess.run([FFMPEG, "-hide_banner", "-filters"], capture_output=True, timeout=30).stdout.decode(errors="replace")
            _filters = {parts[1] for line in out.splitlines() if len(parts := line.split()) >= 2}
        except Exception:
            _filters = set()
    return name in _filters


_encoders: set[str] | None = None


def has_encoder(name: str) -> bool:
    global _encoders
    if _encoders is None:
        try:
            out = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, timeout=30).stdout.decode(errors="replace")
            _encoders = {parts[1] for line in out.splitlines() if len(parts := line.split()) >= 2}
        except Exception:
            _encoders = set()
    return name in _encoders


_hw_broken = False


def h264_args(bitrate: str = "10M", crf: int = 20, preset: str = "veryfast", hw: bool = True) -> list[str]:
    """Encoder args: the Mac's VideoToolbox chip when available (much faster), else libx264."""
    if hw and not _hw_broken and has_encoder("h264_videotoolbox"):
        return ["-c:v", "h264_videotoolbox", "-b:v", bitrate, "-profile:v", "high", "-allow_sw", "1", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high", "-pix_fmt", "yuv420p"]


def run_encode(build, timeout: float | None = None, cwd: str | Path | None = None, **enc) -> subprocess.CompletedProcess:
    """Run ``build(encoder_args, decoder_args)`` with the Mac's video chip for decoding and
    encoding when available; if that fails, retry once fully on the CPU."""
    global _hw_broken, _hwdec_broken
    args = h264_args(**enc)
    dec = hw_decode_args() if args[1] == "h264_videotoolbox" else []
    try:
        return run(build(args, dec), timeout=timeout, cwd=cwd)
    except MediaError:
        if args[1] != "h264_videotoolbox" and not dec:
            raise
        result = run(build(h264_args(**{**enc, "hw": False}), []), timeout=timeout, cwd=cwd)
        # Only blame the hardware if the same job works on the CPU (a bad input fails both ways)
        _hw_broken = True
        _hwdec_broken = True
        return result


def snapshot(path: str | Path, at: float, out: str | Path, width: int = 1280) -> Path:
    out = Path(out)
    run(
        [FFMPEG, "-v", "error", "-nostdin", "-y", "-ss", f"{max(0.0, at):.3f}", "-i", str(path),
         "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", str(out)],
        timeout=60,
    )
    return out
