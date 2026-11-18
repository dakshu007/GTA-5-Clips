"""Tell the streamer's voice apart from in-game character voices.

Pipeline (after Demucs has split the clip into a *voices* stem and a *game sounds* stem):

1. Find the bits of the voices stem where someone is talking.
2. Give each bit a speaker voiceprint (resemblyzer, weights ship with the package).
3. Decide which voice is the streamer: the streamer talks in nearly every clip, while each
   game character only shows up now and then. We keep a per-streamer list of voices seen
   across clips; the one seen in the most clips is the streamer. Until it has been seen in
   two clips, the voice that talks the most in the current clip is assumed to be the streamer.
4. Mute only the streamer's bits — game dialogue stays in.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import numpy as np

from . import config

log = logging.getLogger(__name__)

RATE = 16000
SAME_SPEAKER = 0.80  # cosine similarity above which two voiceprints are one speaker
STREAMER_MATCH = 0.72  # a bit is the streamer's if it is at least this close to the streamer print
MAX_CANDIDATES = 24

_encoder = None
_enc_lock = threading.Lock()
_store_lock = threading.Lock()


def available() -> bool:
    try:
        import resemblyzer  # noqa: F401
        import torch  # noqa: F401
    except Exception:
        return False
    return True


def _get_encoder():
    global _encoder
    with _enc_lock:
        if _encoder is None:
            from resemblyzer import VoiceEncoder  # type: ignore

            _encoder = VoiceEncoder(device="cpu", verbose=False)
    return _encoder


# ---------------------------------------------------------------- talking detection

def speech_segments(mono: np.ndarray, rate: int = RATE, max_len: float = 2.0) -> list[tuple[int, int]]:
    """Sample ranges where the voices stem has someone talking, cut into <= max_len pieces."""
    hop = int(rate * 0.03)
    n = mono.size // hop
    if n == 0:
        return []
    frames = mono[: n * hop].reshape(n, hop)
    db = 20 * np.log10(np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-9)
    loud = np.percentile(db, 95)
    if loud < -55:  # stem is basically silent
        return []
    thr = max(-50.0, loud - 24.0)
    active = db > thr
    segs: list[list[int]] = []
    gap_ok = int(0.25 / 0.03)
    i = 0
    while i < n:
        if not active[i]:
            i += 1
            continue
        j = i
        quiet = 0
        while j < n and quiet <= gap_ok:
            quiet = 0 if active[j] else quiet + 1
            j += 1
        end = j - quiet
        if (end - i) * 0.03 >= 0.35:
            segs.append([i * hop, end * hop])
        i = j
    out: list[tuple[int, int]] = []
    piece = int(max_len * rate)
    for s, e in segs:
        k = s
        while k < e:
            ke = min(e, k + piece)
            if e - ke < piece * 0.4:  # don't leave a tiny tail piece
                ke = e
            out.append((k, ke))
            k = ke
    return out


def _embed(chunks: list[np.ndarray]) -> np.ndarray:
    enc = _get_encoder()
    embs = []
    for c in chunks:
        c = c.astype(np.float32)
        rms = np.sqrt(np.mean(c ** 2)) + 1e-9
        c = c * (10 ** (-26 / 20) / rms)  # level-match so loudness doesn't change the print
        embs.append(enc.embed_utterance(np.clip(c, -1, 1)))
    e = np.array(embs, dtype=np.float32)
    return e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)


def _cluster(embs: np.ndarray) -> list[list[int]]:
    clusters: list[list[int]] = []
    cents: list[np.ndarray] = []
    for i, e in enumerate(embs):
        sims = [float(c @ e) for c in cents]
        if sims and max(sims) >= SAME_SPEAKER:
            k = int(np.argmax(sims))
            clusters[k].append(i)
            c = np.mean(embs[clusters[k]], axis=0)
            cents[k] = c / (np.linalg.norm(c) + 1e-9)
        else:
            clusters.append([i])
            cents.append(e)
    return clusters


# ---------------------------------------------------------------- per-streamer voice memory

def _store_path(key: str) -> Path:
    d = config.DATA_DIR / "voiceprints"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def load_prints(key: str) -> list[dict]:
    p = _store_path(key)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return []


def save_prints(key: str, cands: list[dict]) -> None:
    cands = sorted(cands, key=lambda c: (c["clips"], c["seconds"]), reverse=True)[:MAX_CANDIDATES]
    _store_path(key).write_text(json.dumps(cands))


def reset_prints(key: str) -> None:
    _store_path(key).unlink(missing_ok=True)


def streamer_print(cands: list[dict]) -> np.ndarray | None:
    """The voice seen in the most clips — once it has been seen in at least 2."""
    if not cands:
        return None
    best = max(cands, key=lambda c: (c["clips"], c["seconds"]))
    if best["clips"] < 2:
        return None
    return np.array(best["emb"], dtype=np.float32)


def _remember(cands: list[dict], cents: list[np.ndarray], secs: list[float]) -> list[dict]:
    """Add this clip's voices to the per-streamer memory. A voice counts ONCE per clip, so a
    game character who speaks several times in one cutscene can't outvote the streamer."""
    seen_this_clip: set[int] = set()
    for cent, s in zip(cents, secs):
        sims = [float(np.array(c["emb"]) @ cent) for c in cands]
        if sims and max(sims) >= SAME_SPEAKER:
            k = int(np.argmax(sims))
            c = cands[k]
            w = max(1.0, c["seconds"])
            m = np.array(c["emb"]) * w + cent * s  # duration-weighted running mean
            c["emb"] = (m / (np.linalg.norm(m) + 1e-9)).round(5).tolist()
            if k not in seen_this_clip:
                c["clips"] += 1
                seen_this_clip.add(k)
            c["seconds"] = round(c["seconds"] + s, 1)
        else:
            cands.append({"emb": cent.round(5).tolist(), "clips": 1, "seconds": round(s, 1)})
            seen_this_clip.add(len(cands) - 1)
    return cands


# ---------------------------------------------------------------- main entry

def streamer_mask(vocals: np.ndarray, rate: int, key: str) -> tuple[np.ndarray, dict]:
    """Gain curve (same length as vocals) that is 0 where the streamer talks, 1 elsewhere.

    ``vocals`` is the (channels, n) voices stem at ``rate``. Returns (gain, info).
    """
    mono = vocals.mean(axis=0) if vocals.ndim == 2 else vocals
    n = mono.size
    gain = np.ones(n, dtype=np.float32)
    # resample to 16 kHz for analysis
    idx = np.arange(0, n, rate / RATE)
    m16 = np.interp(idx, np.arange(n), mono).astype(np.float32)
    segs = speech_segments(m16)
    info = {"segments": len(segs), "streamer_segments": 0, "learned": False}
    if not segs:
        return gain, info
    embs = _embed([m16[s:e] for s, e in segs])
    clusters = _cluster(embs)
    secs = [sum((segs[i][1] - segs[i][0]) / RATE for i in cl) for cl in clusters]
    cents = []
    for cl in clusters:
        c = np.mean(embs[cl], axis=0)
        cents.append(c / (np.linalg.norm(c) + 1e-9))
    with _store_lock:
        # remember this clip's voices first, so a voice that also talked in an earlier clip
        # is recognised as the streamer straight away
        cands = _remember(load_prints(key), cents, secs)
        known = streamer_print(cands)
        if known is not None:
            info["learned"] = True
            # Each talking bit goes to the CLOSEST known voice; it's muted only if that is the
            # streamer (and it's a reasonable match) — a game character who merely sounds a bit
            # like the streamer stays in, because their own voice is closer.
            others = [np.array(c["emb"], dtype=np.float32) for c in cands
                      if float(np.array(c["emb"]) @ known) < SAME_SPEAKER]
            is_streamer = []
            for e in embs:
                s_sim = float(e @ known)
                o_sim = max((float(e @ o) for o in others), default=-1.0)
                is_streamer.append(s_sim >= STREAMER_MATCH and s_sim >= o_sim)
        else:
            # not learned yet: the voice that talks most in this clip is the streamer
            top = int(np.argmax(secs))
            members = set(clusters[top])
            is_streamer = [i in members for i in range(len(segs))]
        save_prints(key, cands)
    fade = int(0.04 * rate)
    ramp = np.linspace(1, 0, fade, dtype=np.float32) if fade else np.zeros(0, dtype=np.float32)
    for (s, e), mute in zip(segs, is_streamer):
        if not mute:
            continue
        info["streamer_segments"] += 1
        a, b = int(s * rate / RATE), min(n, int(e * rate / RATE))
        gain[a:b] = 0.0
        if fade and a - fade >= 0:
            gain[a - fade : a] = np.minimum(gain[a - fade : a], ramp)
        if fade and b + fade <= n:
            gain[b : b + fade] = np.minimum(gain[b : b + fade], ramp[::-1])
    return gain, info
