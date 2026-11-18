"""Built-in background beats for troll edits, synthesised from scratch with numpy.

No samples, no downloads, no credits: every loop is generated from sine waves and noise,
so it is original and copyright-safe. Each mood is rendered once to a seamless loop
(note tails wrap around to the start) and cached; the renderer loops it under the clip.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
VERSION = 1


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


class _Loop:
    """A circular buffer: sounds that run past the end continue at the start, so the loop is seamless."""

    def __init__(self, bpm: float, beats: int):
        self.beat = 60.0 / bpm
        self.n = int(round(beats * self.beat * SR))
        self.left = np.zeros(self.n)
        self.right = np.zeros(self.n)

    def add(self, beat: float, sig: np.ndarray, gain: float = 1.0, pan: float = 0.0) -> None:
        start = int(round(beat * self.beat * SR)) % self.n
        sig = sig[: self.n] * gain
        idx = (np.arange(len(sig)) + start) % self.n
        np.add.at(self.left, idx, sig * (1 - max(0.0, pan)))
        np.add.at(self.right, idx, sig * (1 + min(0.0, pan)))


def _t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def _noise(seconds: float, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-1, 1, int(seconds * SR))


def _smooth(x: np.ndarray, width: int) -> np.ndarray:
    """Cheap low-pass (moving average)."""
    if width <= 1:
        return x
    return np.convolve(x, np.ones(width) / width, mode="same")


def kick(punch: float = 1.0) -> np.ndarray:
    t = _t(0.5)
    f = 46 + 120 * punch * np.exp(-t * 30)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    click = _noise(0.5, 1) * np.exp(-t * 400) * 0.3
    return np.tanh((body + click) * 1.6)


def snare(seed: int = 2) -> np.ndarray:
    t = _t(0.3)
    n = np.diff(_noise(0.3, seed), prepend=0) * 0.5 * np.exp(-t * 16)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * 0.5
    return n + tone


def clap() -> np.ndarray:
    t = _t(0.25)
    env = sum(np.exp(-np.clip(t - d, 0, None) * 90) * (t >= d) for d in (0.0, 0.012, 0.024))
    return np.diff(_noise(0.25, 7), prepend=0) * 0.45 * (env + np.exp(-t * 14) * 0.6)


def hat(open_: bool = False, seed: int = 3) -> np.ndarray:
    t = _t(0.25 if open_ else 0.06)
    n = np.diff(np.diff(_noise(len(t) / SR, seed), prepend=0), prepend=0) * 0.25
    return n * np.exp(-t * (14 if open_ else 90))


def tick() -> np.ndarray:
    t = _t(0.03)
    return np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 300)


def pluck(midi: float, dur: float = 0.35, bright: float = 0.5) -> np.ndarray:
    t, f = _t(dur), _hz(midi)
    s = np.sin(2 * np.pi * f * t) + bright * 0.5 * np.sin(4 * np.pi * f * t) + bright * 0.25 * np.sin(6 * np.pi * f * t)
    return s * np.exp(-t * 9) * np.minimum(1, t * 400)


def bass808(midi: float, dur: float) -> np.ndarray:
    t = _t(dur)
    f = _hz(midi) * (1 + 0.6 * np.exp(-t * 40))
    s = np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.2)
    return s * np.exp(-t * 1.2) * np.minimum(1, t * 300) * np.minimum(1, (dur - t) * 40)


def cowbell(midi: float) -> np.ndarray:
    t, f = _t(0.35), _hz(midi)
    sq = np.sign(np.sin(2 * np.pi * f * t)) + np.sign(np.sin(2 * np.pi * f * 1.48 * t))
    return _smooth(sq, 6) * 0.35 * np.exp(-t * 11)


def pad(midis: list[float], dur: float, vibrato: float = 0.0) -> np.ndarray:
    t = _t(dur)
    s = np.zeros_like(t)
    for i, m in enumerate(midis):
        for det in (-0.08, 0.08):
            f = _hz(m + det)
            ph = 2 * np.pi * f * t + (vibrato * np.sin(2 * np.pi * 5.5 * t + i) if vibrato else 0)
            s += np.sin(ph) + 0.3 * np.sin(2 * ph)
    env = np.minimum(1, t / min(0.4, dur / 3)) * np.minimum(1, (dur - t) / min(0.5, dur / 3))
    return s / (len(midis) * 2) * env


def keys(midis: list[float], dur: float) -> np.ndarray:
    """Soft electric-piano chord."""
    t = _t(dur)
    s = sum(np.sin(2 * np.pi * _hz(m) * t) + 0.25 * np.sin(2 * np.pi * _hz(m) * 4 * t) * np.exp(-t * 8) for m in midis)
    return s / len(midis) * np.exp(-t * 1.5) * np.minimum(1, t * 200)


def brass(midis: list[float], dur: float) -> np.ndarray:
    t = _t(dur)
    s = np.zeros_like(t)
    for m in midis:
        f = _hz(m)
        s += sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, 7))
    return _smooth(s / len(midis), 8) * np.minimum(1, t * 25) * np.exp(-t * 1.8)


def tom(midi: float) -> np.ndarray:
    t = _t(0.6)
    f = _hz(midi) * (1 + 0.5 * np.exp(-t * 20))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)


# ---------------------------------------------------------------- moods

def _phonk() -> _Loop:
    L = _Loop(140, 32)
    roots = [42, 42, 45, 40]  # F#1 F#1 A1 E1 per bar
    bell = [66, 69, 66, 73, 71, 69, 66, 64]  # cowbell riff (8ths)
    for bar in range(8):
        b0, r = bar * 4, roots[bar % 4]
        for k in (0, 1.5, 2.5):
            L.add(b0 + k, kick(1.2), 0.9)
        L.add(b0, bass808(r, 1.4), 0.55)
        L.add(b0 + 2.5, bass808(r + (3 if bar % 2 else 0), 1.2), 0.5)
        L.add(b0 + 1, clap(), 0.55)
        L.add(b0 + 3, clap(), 0.55)
        for e in range(8):
            L.add(b0 + e / 2, hat(seed=e), 0.35 if e % 2 else 0.2, pan=0.3)
            note = bell[e] + (-2 if bar % 4 == 3 else 0)
            L.add(b0 + e / 2, cowbell(note), 0.33, pan=-0.2)
    return L


def _funny() -> _Loop:
    L = _Loop(132, 32)
    chords = [(48, [64, 67, 72]), (53, [65, 69, 72]), (55, [62, 67, 71]), (48, [64, 67, 72])]
    melody = [72, 74, 76, 72, 79, 77, 76, 74, 72, 74, 76, 79, 81, 79, 76, None]
    for bar in range(8):
        b0 = bar * 4
        root, tri = chords[bar % 4]
        for k in range(4):  # oom-pah
            L.add(b0 + k, pluck(root if k % 2 == 0 else root + 7, 0.3, 0.9), 0.7)
            for m in tri:
                L.add(b0 + k + 0.5, pluck(m, 0.18, 0.3), 0.22, pan=0.25)
            L.add(b0 + k, kick(0.6), 0.45 if k % 2 == 0 else 0.0)
            L.add(b0 + k + 0.5, hat(seed=k), 0.2, pan=-0.3)
        if bar % 2 == 1:
            L.add(b0 + 1, snare(), 0.35)
            L.add(b0 + 3, snare(), 0.35)
        for i in range(4):
            m = melody[(bar % 4) * 4 + i]
            if m:
                L.add(b0 + i, pluck(m + (12 if bar >= 4 else 0), 0.25, 0.6), 0.32, pan=-0.15)
    return L


def _suspense() -> _Loop:
    L = _Loop(100, 32)
    for beat in range(32):
        L.add(beat, bass808(28, 0.45), 0.5)
        L.add(beat + 0.18, kick(0.4), 0.25)  # heartbeat double
        for e in (0, 0.5):
            L.add(beat + e, tick(), 0.18, pan=0.4 if e else -0.4)
    for bar in range(8):
        L.add(bar * 4, pad([52, 53, 59] if bar % 2 else [52, 55, 58], 4 * 0.6, vibrato=0.6), 0.32)
    return L


def _epic() -> _Loop:
    L = _Loop(90, 16)
    chords = [[50, 57, 62], [46, 53, 58], [48, 55, 60], [45, 52, 57]]  # Dm Bb C A
    for bar in range(4):
        b0 = bar * 4
        L.add(b0, pad([c - 12 for c in chords[bar]] + chords[bar], 4 * 60 / 90), 0.35)
        L.add(b0, brass(chords[bar], 1.3), 0.3)
        L.add(b0 + 2.5, brass(chords[bar], 0.6), 0.22)
        for k, (g, m) in enumerate([(0, None), (1.5, 45), (2, None), (3, 43), (3.5, 40)]):
            L.add(b0 + g, kick(1.0) if m is None else tom(m), 0.8 if m is None else 0.6, pan=0.0 if m is None else (-0.3 if k % 2 else 0.3))
        L.add(b0 + 1, snare(5), 0.5)
        L.add(b0 + 3, snare(6), 0.5)
    return L


def _sad() -> _Loop:
    L = _Loop(70, 16)
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    tune = [76, 74, 72, 71]
    beat_s = 60 / 70
    for bar in range(4):
        b0 = bar * 4
        L.add(b0, pad(chords[bar], 4 * beat_s), 0.4)
        L.add(b0, pad([chords[bar][0] - 12], 4 * beat_s), 0.35)
        L.add(b0, pad([tune[bar]], 2 * beat_s, vibrato=1.2), 0.25, pan=-0.2)
        L.add(b0 + 2, pad([tune[bar] - 2], 2 * beat_s, vibrato=1.2), 0.22, pan=0.2)
    return L


def _chill() -> _Loop:
    L = _Loop(84, 16)
    chords = [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59]]  # Fmaj7 Em7 Dm7 Cmaj7
    beat_s = 60 / 84
    for bar in range(4):
        b0 = bar * 4
        L.add(b0, keys(chords[bar], 4 * beat_s), 0.45)
        L.add(b0 + 2.5, keys(chords[bar][1:], 1.5 * beat_s), 0.2, pan=0.2)
        L.add(b0, kick(0.5), 0.55)
        L.add(b0 + 2.5, kick(0.5), 0.45)
        L.add(b0 + 1, snare(9), 0.25)
        L.add(b0 + 3, snare(9), 0.25)
        for e in range(8):
            L.add(b0 + e / 2 + (0.08 if e % 2 else 0), hat(seed=20 + e), 0.14, pan=-0.25)
    return L


MOODS = {"phonk": _phonk, "funny": _funny, "suspense": _suspense, "epic": _epic, "sad": _sad, "chill": _chill}


def make(mood: str, out: Path) -> Path:
    """Render a mood loop to a 48 kHz stereo wav."""
    L = MOODS.get(mood, _funny)()
    stereo = np.stack([L.left, L.right], axis=1)
    # same loudness for every mood (RMS about -19 dBFS), then soft-clip the peaks
    stereo = stereo * (0.11 / max(1e-9, float(np.sqrt(np.mean(stereo ** 2)))))
    stereo = np.tanh(stereo * 1.2) / 1.2
    stereo = stereo / max(1.0, np.abs(stereo).max() / 0.89)  # never above about -1 dBFS
    pcm = (stereo * 32767).astype("<i2")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    tmp.replace(out)
    return out
