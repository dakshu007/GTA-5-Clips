"""Sounds for troll edits: built-in effects, your own sound folder, and ElevenLabs.

Where a sound comes from, in order:
1. Your folder  data/trollkit/sfx  and  data/trollkit/music  (files you have the rights to)
2. ElevenLabs (if an API key is set): sound effects, narrator voice, background music
3. Built-in effects synthesised with ffmpeg — always available, original, copyright-safe

Everything generated is cached on disk, so each sound is only paid for once.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import httpx

from . import config, db, media

log = logging.getLogger(__name__)

API = "https://api.elevenlabs.io/v1"
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

# Built-in effects: name -> (ffmpeg lavfi source, duration). All synthesised, no samples used.
BUILTIN: dict[str, tuple[str, float]] = {
    "boom": ("sine=f=48:d=1.4,volume='exp(-2.8*t)':eval=frame,asetrate=48000*1.0,aresample=48000[a];"
             "anoisesrc=d=0.08:c=brown:a=0.9,volume=1.4[b];[a][b]amix=inputs=2:normalize=0,acompressor=threshold=0.2:ratio=4", 1.4),
    "whoosh": ("anoisesrc=d=0.7:c=pink:a=0.8,bandpass=f=900:width_type=h:w=1400,volume='sin(PI*t/0.7)':eval=frame,"
               "aphaser=in_gain=0.6:speed=2", 0.7),
    "ding": ("sine=f=1568:d=1.2,volume='exp(-3.5*t)':eval=frame[a];sine=f=2349:d=1.2,volume='0.5*exp(-4.5*t)':eval=frame[b];"
             "[a][b]amix=inputs=2:normalize=0", 1.2),
    "record_scratch": ("anoisesrc=d=0.45:c=white:a=0.7,bandpass=f=2500:width_type=h:w=3000,"
                       "volume='if(lt(mod(t,0.11),0.07),1,0.15)':eval=frame,vibrato=f=18:d=0.9", 0.45),
    "sad_trombone": ("aevalsrc=exprs='(0.5*sin(2*PI*392*t)+0.25*sin(4*PI*392*t)+0.12*sin(6*PI*392*t))*min(1,t*20)':d=0.45:s=48000[a];"
                     "aevalsrc=exprs='(0.5*sin(2*PI*370*t)+0.25*sin(4*PI*370*t)+0.12*sin(6*PI*370*t))*min(1,t*20)':d=0.45:s=48000[b];"
                     "aevalsrc=exprs='(0.5*sin(2*PI*349*t)+0.25*sin(4*PI*349*t)+0.12*sin(6*PI*349*t))*min(1,t*20)':d=0.45:s=48000[c];"
                     "aevalsrc=exprs='(0.5*sin(2*PI*330*t+3*sin(2*PI*5*t))+0.25*sin(4*PI*330*t))*min(1,t*20)*min(1,(1.3-t)*3)':d=1.3:s=48000[e];"
                     "[a][b][c][e]concat=n=4:v=0:a=1,lowpass=f=2200", 2.65),
    "airhorn": ("aevalsrc=exprs='0.25*(sgn(sin(2*PI*466*t))+sgn(sin(2*PI*554*t))+sgn(sin(2*PI*698*t)))"
                "*if(lt(mod(t,0.3),0.24),1,0.15)':d=0.9:s=48000,lowpass=f=3200", 0.9),
    "pop": ("sine=f=900:d=0.12,volume='exp(-30*t)':eval=frame,asetrate=48000*1.4,aresample=48000", 0.12),
    "suspense": ("sine=f=110:d=2.2,volume='t/2.2':eval=frame,vibrato=f=7:d=0.4[a];"
                 "anoisesrc=d=2.2:c=pink:a=0.25,lowpass=f=600,volume='t/2.2':eval=frame[b];[a][b]amix=inputs=2:normalize=0", 2.2),
    "bonk": ("sine=f=180:d=0.35,volume='exp(-12*t)':eval=frame[a];anoisesrc=d=0.03:c=white:a=0.8[b];"
             "[a][b]amix=inputs=2:normalize=0", 0.35),
    "riser": ("aevalsrc=exprs='0.5*sin(2*PI*(200*t+250*t*t))*(t/1.6)':d=1.6:s=48000,vibrato=f=12:d=0.3", 1.6),
}

# Keywords -> built-in, used when the AI asks for a sound we don't have and ElevenLabs is off
KEYWORDS = [
    (r"boom|bass|impact|vine|hit|slam|drop", "boom"),
    (r"whoosh|swoosh|swipe|fast|zoom|wind", "whoosh"),
    (r"ding|bell|correct|ping", "ding"),
    (r"scratch|record|stop|freeze|rewind", "record_scratch"),
    (r"trombone|fail|sad|wah|lose", "sad_trombone"),
    (r"horn|air|mlg|party", "airhorn"),
    (r"pop|bubble|click", "pop"),
    (r"suspense|tension|uh.?oh|wait", "suspense"),
    (r"bonk|knock|thud|smack", "bonk"),
    (r"rise|riser|build", "riser"),
]

MUSIC_MOODS = {
    "funny": "playful bouncy comedic instrumental, pizzicato and bassoon, cartoon chase energy, no vocals",
    "suspense": "tense ticking suspense instrumental, low strings and pulsing synth, building tension, no vocals",
    "epic": "epic trailer instrumental, big drums and brass hits, heroic, no vocals",
    "phonk": "dark drift phonk instrumental, cowbell melody, heavy 808 bass, aggressive, no vocals",
    "sad": "over-dramatic sad violin instrumental, comedic melodrama, no vocals",
    "chill": "laid-back lofi hip hop instrumental, mellow keys, vinyl crackle, no vocals",
}


def kit_dir(kind: str) -> Path:
    d = config.DATA_DIR / "trollkit" / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    d = config.DATA_DIR / "trollkit" / ".cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def library(kind: str) -> list[Path]:
    return sorted(p for p in kit_dir(kind).iterdir() if p.suffix.lower() in AUDIO_EXT and p.is_file())


def _key(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def builtin(name: str) -> Path:
    """Render a built-in effect to a cached wav."""
    graph, dur = BUILTIN[name]
    out = cache_dir() / f"builtin_v2_{name}.wav"
    if not out.exists():
        raw = out.with_suffix(".raw.wav")
        media.run([media.FFMPEG, "-v", "error", "-nostdin", "-y", "-filter_complex",
                   f"{graph},aformat=sample_rates=48000:channel_layouts=stereo[out]",
                   "-map", "[out]", "-t", f"{dur:.2f}", str(raw)], timeout=60)
        # peak-normalise to -3 dB so every effect lands at the same level
        stats = media.run([media.FFMPEG, "-nostdin", "-i", str(raw), "-af", "volumedetect", "-f", "null", "-"],
                          timeout=60).stderr.decode(errors="replace")
        m = re.search(r"max_volume:\s*(-?[\d.]+) dB", stats)
        gain = -3.0 - float(m.group(1)) if m else 0.0
        media.run([media.FFMPEG, "-v", "error", "-nostdin", "-y", "-i", str(raw), "-af", f"volume={gain:.2f}dB",
                   str(out)], timeout=60)
        raw.unlink(missing_ok=True)
    return out


def nearest_builtin(text: str) -> str:
    low = text.lower()
    for pattern, name in KEYWORDS:
        if re.search(pattern, low):
            return name
    return "boom"


# ---------------------------------------------------------------- ElevenLabs

def el_settings() -> dict:
    return db.get_settings("elevenlabs")


def el_enabled() -> bool:
    cfg = el_settings()
    return bool(cfg.get("enabled", True) and cfg.get("api_key"))


def _el_post(path: str, body: dict, params: dict | None = None, timeout: float = 120) -> bytes:
    cfg = el_settings()
    r = httpx.post(f"{API}{path}", params=params or {}, json=body,
                   headers={"xi-api-key": cfg["api_key"], "Accept": "audio/mpeg"}, timeout=timeout)
    if r.status_code != 200:
        try:
            detail = r.json().get("detail")
            msg = detail.get("message") if isinstance(detail, dict) else str(detail)
        except Exception:
            msg = r.text[:200]
        raise RuntimeError(f"ElevenLabs {path} failed ({r.status_code}): {msg}")
    return r.content


def el_voices() -> list[dict]:
    cfg = el_settings()
    r = httpx.get(f"{API}/voices", headers={"xi-api-key": cfg["api_key"]}, timeout=30)
    r.raise_for_status()
    return [{"voice_id": v["voice_id"], "name": v.get("name", ""), "labels": v.get("labels") or {}}
            for v in r.json().get("voices", [])]


def el_sfx(prompt: str, seconds: float | None = None) -> Path:
    cfg = el_settings()
    out = cache_dir() / f"sfx_{_key(prompt, str(seconds), cfg.get('sfx_model', ''))}.mp3"
    if out.exists() and out.stat().st_size > 500:
        return out
    body: dict = {"text": prompt[:400], "prompt_influence": 0.5}
    if seconds:
        body["duration_seconds"] = max(0.5, min(5.0, float(seconds)))
    if cfg.get("sfx_model"):
        body["model_id"] = cfg["sfx_model"]
    out.write_bytes(_el_post("/sound-generation", body))
    return out


def el_tts(text: str) -> Path:
    cfg = el_settings()
    voice_id = cfg.get("voice_id") or ""
    if not voice_id:
        voices = el_voices()
        if not voices:
            raise RuntimeError("no ElevenLabs voices available on this account")
        voice_id = voices[0]["voice_id"]
        db.update_settings("elevenlabs", {"voice_id": voice_id})
    model = cfg.get("tts_model") or "eleven_multilingual_v2"
    out = cache_dir() / f"tts_{_key(text, voice_id, model)}.mp3"
    if out.exists() and out.stat().st_size > 500:
        return out
    body = {"text": text[:300], "model_id": model,
            "voice_settings": {"stability": 0.35, "similarity_boost": 0.8, "style": 0.6, "use_speaker_boost": True}}
    out.write_bytes(_el_post(f"/text-to-speech/{voice_id}", body, params={"output_format": "mp3_44100_128"}))
    return out


def el_music(mood: str, seconds: float) -> Path:
    """One cached track per mood (reused across clips, so it's only generated once)."""
    cfg = el_settings()
    prompt = MUSIC_MOODS.get(mood, MUSIC_MOODS["funny"])
    out = cache_dir() / f"music_{mood}_{_key(prompt, cfg.get('music_model', ''))}.mp3"
    if out.exists() and out.stat().st_size > 5000:
        return out
    body: dict = {"prompt": prompt, "music_length_ms": int(max(30.0, min(90.0, seconds)) * 1000), "force_instrumental": True}
    if cfg.get("music_model"):
        body["model_id"] = cfg["music_model"]
    out.write_bytes(_el_post("/music", body, params={"output_format": "mp3_44100_128"}, timeout=300))
    return out


# ---------------------------------------------------------------- resolving what the plan asks for

def resolve_sfx(want: str, seconds: float | None = None, allow_el: bool = True) -> Path:
    """A sound for ``want``: a file name from your sfx folder, a built-in name, or a description."""
    want = (want or "").strip()
    stem = want.lower().removeprefix("library:").strip()
    for p in library("sfx"):
        if p.stem.lower() == stem or p.name.lower() == stem:
            return p
    if stem in BUILTIN:
        return builtin(stem)
    if allow_el and el_enabled() and el_settings().get("use_sfx", True) and want:
        try:
            return el_sfx(want, seconds)
        except Exception as exc:  # out of credits, network...
            log.warning("ElevenLabs sound effect failed, using built-in: %s", exc)
    return builtin(nearest_builtin(want))


def resolve_music(mood: str, seconds: float) -> Path | None:
    if not mood or mood == "none":
        return None
    files = library("music")
    by_mood = [p for p in files if p.stem.lower().startswith(mood)]
    if by_mood or files:
        pick = (by_mood or files)
        return pick[int(hashlib.sha1(mood.encode()).hexdigest(), 16) % len(pick)]
    if el_enabled() and el_settings().get("use_music", True):
        try:
            return el_music(mood, seconds)
        except Exception as exc:
            log.warning("ElevenLabs music failed, no music for this clip: %s", exc)
    return None


def resolve_narration(text: str) -> Path | None:
    if not text.strip() or not (el_enabled() and el_settings().get("use_voice", True)):
        return None
    try:
        return el_tts(text)
    except Exception as exc:
        log.warning("ElevenLabs narration failed, showing the line as text only: %s", exc)
        return None
