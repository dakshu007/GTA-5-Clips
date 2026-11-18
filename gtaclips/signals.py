"""Key-moment detection.

Every second of a stream gets a value for each signal:

* ``audio``  – loudness spikes (screams, laughter, explosions)
* ``motion`` – sudden visual action (crashes, chases, explosions)
* ``chat``   – chat velocity, weighted by hype words/emotes
* ``speech`` – hype phrases in the streamer's speech (needs faster-whisper)
* ``game``   – in-game banners read with OCR, e.g. WASTED / BUSTED (needs tesseract)

Dense signals (audio, motion, chat) are turned into 0..1 scores with a rolling
robust z-score, so each stream is compared with its own normal level. Signals are
combined with a weighted "soft OR": any strong signal can trigger on its own, and
several medium signals agreeing also trigger. A signal that is unavailable (no chat
connection, no whisper) just contributes nothing instead of diluting the others.
"""
from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from . import media

SIGNALS = ("audio", "motion", "chat", "speech", "game")
DENSE = ("audio", "motion", "chat")
BASELINE_WINDOW = 300  # seconds of history used as "normal"
CHAT_LAG = 4  # chat reacts a few seconds after the moment


def _nan_array(n: int) -> np.ndarray:
    a = np.empty(n, dtype=np.float64)
    a[:] = np.nan
    return a


@dataclass
class Moment:
    peak: float
    start: float
    end: float
    score: float
    signals: dict
    series: list = field(default_factory=list)


class Timeline:
    """Growable per-second arrays of raw signal values."""

    def __init__(self) -> None:
        self.raw: dict[str, np.ndarray] = {k: _nan_array(0) for k in SIGNALS}
        self.length = 0  # number of seconds covered by analyzed media

    def ensure(self, n: int) -> None:
        cur = len(self.raw["audio"])
        if n <= cur:
            return
        new = max(n, int(cur * 1.5) + 64)
        for k in SIGNALS:
            arr = _nan_array(new)
            arr[:cur] = self.raw[k]
            self.raw[k] = arr

    def put_max(self, sig: str, t: float, value: float) -> None:
        idx = int(t)
        if idx < 0:
            return
        self.ensure(idx + 1)
        cur = self.raw[sig][idx]
        if math.isnan(cur) or value > cur:
            self.raw[sig][idx] = value

    def add(self, sig: str, t: float, value: float) -> None:
        idx = int(t)
        if idx < 0:
            return
        self.ensure(idx + 1)
        cur = self.raw[sig][idx]
        self.raw[sig][idx] = value if math.isnan(cur) else cur + value


# ---------------------------------------------------------------- feature extraction

def audio_features(tl: Timeline, path: str | Path, offset: float, start: float | None = None, length: float | None = None) -> bool:
    pcm = media.audio_pcm(path, start=start, length=length)
    if pcm.size == 0:
        return False
    rate = 16000
    hop = rate // 2  # 0.5 s windows
    n = pcm.size // hop
    if n == 0:
        return False
    frames = pcm[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-6)
    for i, v in enumerate(db):
        tl.put_max("audio", offset + i * 0.5, float(v))
    return True


def motion_features(tl: Timeline, path: str | Path, offset: float, start: float | None = None, length: float | None = None) -> np.ndarray:
    fps = 2.0
    frames = media.gray_frames(path, fps=fps, start=start, length=length)
    if len(frames) < 2:
        return frames
    f = frames.astype(np.float32)
    diffs = np.mean(np.abs(f[1:] - f[:-1]), axis=(1, 2))
    for i, v in enumerate(diffs):
        tl.put_max("motion", offset + (i + 1) / fps, float(v))
    return frames


def _contains_phrase(text: str, phrases: list[str]) -> list[str]:
    low = f" {text.lower()} "
    hits = []
    for p in phrases:
        p = p.lower().strip()
        if not p:
            continue
        if re.fullmatch(r"[\w' ]+", p):
            if re.search(rf"(?<![\w']){re.escape(p)}(?![\w'])", low):
                hits.append(p)
        elif p in low:
            hits.append(p)
    return hits


def speech_features(tl: Timeline, words: list[dict], offset: float, phrases: list[str]) -> None:
    """Mark seconds where the streamer says a hype phrase. ``words`` = [{w, s, e}] relative to offset."""
    if not words:
        return
    for i in range(len(words)):
        window = " ".join(w["w"] for w in words[i : i + 4])
        if _contains_phrase(window, phrases):
            tl.put_max("speech", offset + words[i]["s"], 1.0)
    # mark the analyzed span as "available" (0) where nothing was said
    lo = int(offset + words[0]["s"])
    hi = int(offset + words[-1]["e"]) + 1
    tl.ensure(hi + 1)
    seg = tl.raw["speech"][lo:hi]
    seg[np.isnan(seg)] = 0.0


_ocr_lock = threading.Lock()


def ocr_features(tl: Timeline, path: str | Path, offset: float, game_words: list[str], start: float | None = None, length: float | None = None) -> bool:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return False
    fps = 0.5
    w, h = 640, 360
    args = [media.FFMPEG, "-v", "error", "-nostdin"]
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(path)]
    if length is not None:
        args += ["-t", f"{length:.3f}"]
    args += ["-an", "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "pipe:1"]
    import subprocess

    proc = subprocess.run(args, capture_output=True, timeout=600)
    if proc.returncode != 0:
        return False
    buf = np.frombuffer(proc.stdout, dtype=np.uint8)
    n = buf.size // (w * h)
    targets = [g.upper() for g in game_words if g.strip()]
    for i in range(n):
        frame = buf[i * w * h : (i + 1) * w * h].reshape(h, w)
        with _ocr_lock:
            text = pytesseract.image_to_string(Image.fromarray(frame), config="--psm 11").upper()
        hit = any(t in text for t in targets)
        tl.put_max("game", offset + i / fps, 1.0 if hit else 0.0)
    return True


# ---------------------------------------------------------------- scoring

def _smoothed(raw: np.ndarray, upto: int, smooth: int) -> np.ndarray:
    vals = raw[:upto].copy()
    if smooth > 1 and upto:
        mask = np.isnan(vals)
        fill = float(np.nanmedian(vals)) if np.any(~mask) else 0.0
        vals = np.convolve(np.where(mask, fill, vals), np.ones(smooth) / smooth, mode="same")
        vals[mask] = np.nan
    return vals


def robust_scores(raw: np.ndarray, upto: int, smooth: int = 1, min_history: int = 15, lo: int = 0, prev: np.ndarray | None = None) -> np.ndarray:
    """Rolling robust z-score mapped to 0..1. Index i only looks at history before i.

    Scores before ``lo`` are copied from ``prev`` (incremental recompute for live streams).
    """
    out = np.zeros(upto, dtype=np.float64)
    if prev is not None and lo > 0:
        k = min(lo, len(prev), upto)
        out[:k] = prev[:k]
    else:
        lo = 0
    vals = _smoothed(raw, upto, smooth)
    for i in range(lo, upto):
        v = vals[i]
        if math.isnan(v):
            continue
        hist = vals[max(0, i - BASELINE_WINDOW) : i]
        hist = hist[~np.isnan(hist)]
        if hist.size < min_history:
            continue
        med = float(np.median(hist))
        mad = float(np.median(np.abs(hist - med))) * 1.4826
        spread = max(mad, 1e-3, 0.05 * abs(med))
        z = (v - med) / spread
        out[i] = min(1.0, max(0.0, (z - 1.0) / 3.0))  # z<=1 → 0, z>=4 → 1
    return out


def combine(per_signal: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    n = len(next(iter(per_signal.values())))
    keep = np.ones(n, dtype=np.float64)
    for k, s in per_signal.items():
        c = min(0.95, 0.7 * float(weights.get(k, 1.0)))
        keep *= 1.0 - np.clip(s, 0, 1) * c
    return 1.0 - keep


class Analyzer:
    """Incremental scorer + peak picker shared by live capture and VOD processing."""

    LOOKAHEAD = 6

    def __init__(self, settings: dict, on_moment: Callable[[Moment], None], on_scores: Callable[[int, int, dict], None] | None = None):
        self.cfg = settings
        self.tl = Timeline()
        self.on_moment = on_moment
        self.on_scores = on_scores
        self.last_trigger = -1e9
        self.scanned = 0  # seconds already scanned for peaks
        self.pending: list[Moment] = []
        self.has_chat = False
        self._combined = np.zeros(0)
        self._per: dict[str, np.ndarray] = {}
        self._scored_n = 0

    def chat_rate(self, t: float, weight: float) -> None:
        self.has_chat = True
        self.tl.add("chat", t, weight)

    def advance(self, new_length: float, final: bool = False) -> None:
        """Call after features up to ``new_length`` seconds have been added."""
        self.tl.length = max(self.tl.length, int(new_length))
        n = self.tl.length
        if n <= 0:
            return
        self.tl.ensure(n + CHAT_LAG + 1)
        lo = max(0, self._scored_n - 12)
        per: dict[str, np.ndarray] = {}
        per["audio"] = robust_scores(self.tl.raw["audio"], n, smooth=1, lo=lo, prev=self._per.get("audio"))
        per["motion"] = robust_scores(self.tl.raw["motion"], n, smooth=2, lo=lo, prev=self._per.get("motion"))
        if self.has_chat:
            # chat[t] is scored from messages CHAT_LAG seconds later (people react after the moment)
            chat = np.nan_to_num(self.tl.raw["chat"][: n + CHAT_LAG], nan=0.0)
            chat = np.pad(chat, (0, max(0, n + CHAT_LAG - len(chat))))[CHAT_LAG : CHAT_LAG + n]
            chat_lo = max(0, lo - CHAT_LAG - 4)
            per["chat"] = robust_scores(chat, n, smooth=4, lo=chat_lo, prev=self._per.get("chat"))
        self._scored_n = n
        for ev in ("speech", "game"):
            arr = np.nan_to_num(self.tl.raw[ev][:n], nan=0.0)
            if np.any(arr > 0):
                # spread event hits ±1 s so they line up with the reaction
                spread = np.maximum.reduce([arr, np.roll(arr, 1), np.roll(arr, -1)])
                per[ev] = spread
        weights = self.cfg.get("weights", {})
        combined = combine(per, weights)
        self._combined, self._per = combined, per
        if self.on_scores:
            self.on_scores(max(0, n - 30), n, self.snapshot(max(0, n - 30), n))
        self._scan(final)

    def snapshot(self, lo: int, hi: int) -> dict:
        return {
            "combined": [round(float(x), 3) for x in self._combined[lo:hi]],
            "signals": {k: [round(float(x), 3) for x in v[lo:hi]] for k, v in self._per.items()},
        }

    def _scan(self, final: bool) -> None:
        cfg = self.cfg
        thr = float(cfg.get("threshold", 0.55))
        warm = float(cfg.get("warmup", 20))
        cooldown = float(cfg.get("cooldown", 35))
        n = len(self._combined)
        limit = n if final else n - self.LOOKAHEAD
        c = self._combined
        for t in range(self.scanned, max(self.scanned, limit)):
            if t < warm or c[t] < thr or t - self.last_trigger < cooldown:
                continue
            lo, hi = max(0, t - self.LOOKAHEAD), min(n, t + self.LOOKAHEAD + 1)
            if c[t] < np.max(c[lo:hi]) or (t > lo and np.argmax(c[lo:hi]) + lo != t):
                continue
            self.last_trigger = t
            self.pending.append(self._build_moment(t))
        self.scanned = max(self.scanned, limit)
        self._flush(final)

    def _build_moment(self, peak: int) -> Moment:
        cfg = self.cfg
        pre, post = float(cfg.get("pre_roll", 12)), float(cfg.get("post_roll", 8))
        start = max(0.0, peak - pre)
        end = peak + post
        sig = {k: round(float(v[peak]), 3) for k, v in self._per.items()}
        sig["top"] = max(sig, key=lambda k: sig[k] * float(cfg.get("weights", {}).get(k, 1.0))) if sig else "audio"
        return Moment(peak=float(peak), start=start, end=end, score=round(float(self._combined[peak]), 3), signals=sig)

    def _flush(self, final: bool) -> None:
        cfg = self.cfg
        thr = float(cfg.get("threshold", 0.55))
        min_len, max_len = float(cfg.get("min_len", 15)), float(cfg.get("max_len", 58))
        n = len(self._combined)
        ready: list[Moment] = []
        for m in self.pending:
            # let the clip run on while the action continues
            end = m.end
            while end < n and end - m.start < max_len and self._combined[int(end)] > thr * 0.6:
                end += 1
            if end - m.start < min_len:
                end = m.start + min_len
            end = min(end, m.start + max_len)
            if end + 1 <= n or final:
                m.end = float(min(end, n)) if final else float(end)
                lo, hi = int(m.start), int(min(m.end, n))
                m.series = [round(float(x), 3) for x in self._combined[lo:hi]]
                ready.append(m)
            else:
                m.end = end
        for m in ready:
            self.pending.remove(m)
            if m.end - m.start >= 5:
                self.on_moment(m)
