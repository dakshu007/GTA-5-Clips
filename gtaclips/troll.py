"""Troll edit: Claude plans a meme-style edit, HYPECUT renders it.

The plan is a list of timed effects on the clip: zoom punch-ins, screen shake, white flash,
one smooth slow-motion window, black-and-white "freeze" moments, meme stickers, sound
effects, narrator lines (voiced by ElevenLabs if configured), a background music mood and
an ending card. Everything is validated and clamped before rendering, and there is a
template plan for when no AI key is set.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import anthropic

from . import ai, trollkit

log = logging.getLogger(__name__)

EVENT_TYPES = ["zoom", "shake", "flash", "bw", "sticker", "sfx", "narration"]
MOODS = ["none", *trollkit.MUSIC_MOODS.keys()]

SCHEMA = {
    "type": "object",
    "properties": {
        "keep": {"type": "boolean"},
        "virality": {"type": "integer"},
        "reason": {"type": "string"},
        "hook": {"type": "string", "description": "On-screen hook for the first 2.5 s, max 7 words, no emoji"},
        "title": {"type": "string", "description": "YouTube Shorts title, max 80 chars, may include 1 emoji"},
        "caption": {"type": "string", "description": "Instagram caption, 1-2 lines, may include emoji"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "slowmo": {
            "type": "object",
            "properties": {"enabled": {"type": "boolean"}, "start": {"type": "number"}, "end": {"type": "number"}},
            "required": ["enabled", "start", "end"],
            "additionalProperties": False,
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": EVENT_TYPES},
                    "t": {"type": "number", "description": "seconds from the start of the clip"},
                    "dur": {"type": "number"},
                    "text": {"type": "string", "description": "sticker text or narrator line; empty otherwise"},
                    "sound": {"type": "string", "description": "for sfx: a sound name from the list, or a short description"},
                },
                "required": ["type", "t", "dur", "text", "sound"],
                "additionalProperties": False,
            },
        },
        "music_mood": {"type": "string", "enum": MOODS},
        "ending_text": {"type": "string", "description": "ending card, max 5 words, no emoji"},
    },
    "required": ["keep", "virality", "reason", "hook", "title", "caption", "hashtags", "slowmo", "events",
                 "music_mood", "ending_text"],
    "additionalProperties": False,
}

SYSTEM = """You are a top meme editor making viral TROLL edits of {game} gameplay for YouTube Shorts and Reels.
You get frames from the clip (each labelled with its time), the hype curve and any speech. Plan an edit that
makes people watch to the end and rewatch.

Editing language (use it with timing, not randomly):
- zoom: fast punch-in on the funniest/impact moment (dur 0.4-1.5 s)
- shake: screen shake on crashes, explosions, hits (dur 0.3-1.0 s)
- flash: white flash on a big impact (dur 0.1)
- bw: black-and-white "and that's when it all went wrong" moment, usually near the end (dur 1-3 s)
- sticker: big meme text that pops on screen (max 4 words, no emoji), e.g. "NAH", "BRO REALLY", "CALCULATED", "L"
- sfx: a sound effect. Prefer these names: {sounds}. You may also describe a sound (e.g. "cartoon slide whistle").
- narration: a short troll narrator line (max 12 words) spoken over the clip, like a sarcastic documentary voice
- slowmo: at most ONE slow-motion window of 0.8-2.5 s right on the key moment
- music_mood: background music feel ({moods})

Rules:
- The edit must follow the story of the clip: setup -> escalation -> payoff -> punchline. Put the biggest
  effects ON the payoff, not before it. 6-12 events total; never more than one sticker on screen at once.
- Start with something in the first second (sound + sticker or narration) so nobody scrolls away.
- Write ORIGINAL lines in meme style. Never quote movies, songs or copyrighted catchphrases word for word.
- Nothing hateful, sexual, or targeting real people; roast the in-game situation, not the streamer.
- Only describe what is visible in the frames or said in the transcript.
- keep=false if nothing funny/interesting happens. Score virality strictly: 90+ only for an instant must-watch.
- Times are seconds from the clip start, within 0..{duration:.1f}.
- Style: {style}"""


def _b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode()


def plan_with_ai(*, frames: list[tuple[float, Path]], transcript: str, hype: list[float], duration: float,
                 streamer: str, ai_cfg: dict, game: str) -> dict | None:
    """Ask Claude for a troll edit plan. Returns None if the AI is off or fails."""
    if not ai_cfg.get("enabled", True):
        return None
    sounds = ", ".join(list(trollkit.BUILTIN) + [p.stem for p in trollkit.library("sfx")][:30])
    content: list[dict] = []
    for t, f in frames:
        content.append({"type": "text", "text": f"frame at {t:.1f}s:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(f)}})
    curve = " ".join(f"{i}s:{v:.2f}" for i, v in enumerate(hype) if i % 2 == 0)
    content.append({"type": "text", "text": (
        f"Streamer: {streamer}\nClip length: {duration:.1f}s\nHype curve (0-1, per second): {curve or 'n/a'}\n"
        f"Speech in the clip:\n\"\"\"\n{transcript[:2500] or '(none)'}\n\"\"\"\nPlan the troll edit.")})
    try:
        client = ai._client(ai_cfg.get("api_key") or "")
        request = dict(
            model=ai_cfg.get("model") or "claude-opus-5-5",
            max_tokens=16000,
            system=SYSTEM.format(game=game, sounds=sounds, moods=", ".join(MOODS), duration=duration,
                                 style=ai_cfg.get("style", "")),
            messages=[{"role": "user", "content": content}],
            output_config={"effort": ai_cfg.get("effort") or "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        try:
            resp = client.beta.messages.create(**request, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        except anthropic.BadRequestError as exc:
            if "fallback" not in str(exc).lower():
                raise
            resp = client.messages.create(**request)
    except Exception as exc:  # no key, network, rate limit...
        log.warning("troll plan from AI failed, using template: %s", exc)
        return None
    if resp.stop_reason == "refusal":
        return None
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    data["source"] = "claude"
    return data


def template_plan(*, duration: float, peak: float, top_signal: str) -> dict:
    """A solid default troll edit built around the detected peak (used without an AI key)."""
    p = max(1.5, min(duration - 1.5, peak))
    stickers = {"chat": "CHAT SAW IT", "audio": "NAH", "motion": "BRO REALLY", "game": "CALCULATED"}
    return {
        "keep": True, "virality": 50, "reason": "Template troll edit around the detected peak.",
        "hook": "Wait for it", "title": "", "caption": "", "hashtags": [],
        "slowmo": {"enabled": True, "start": max(0.0, p - 0.6), "end": min(duration, p + 0.9)},
        "events": [
            {"type": "sfx", "t": 0.05, "dur": 0.7, "text": "", "sound": "whoosh"},
            {"type": "sfx", "t": max(0.0, p - 2.2), "dur": 2.2, "text": "", "sound": "suspense"},
            {"type": "zoom", "t": p - 0.1, "dur": 1.2, "text": "", "sound": ""},
            {"type": "shake", "t": p, "dur": 0.6, "text": "", "sound": ""},
            {"type": "flash", "t": p, "dur": 0.1, "text": "", "sound": ""},
            {"type": "sfx", "t": p, "dur": 1.2, "text": "", "sound": "boom"},
            {"type": "sticker", "t": p + 0.2, "dur": 1.4, "text": stickers.get(top_signal, "NAH"), "sound": ""},
            {"type": "bw", "t": max(0.0, duration - 3.0), "dur": 2.5, "text": "", "sound": ""},
            {"type": "sfx", "t": max(0.0, duration - 3.0), "dur": 2.6, "text": "", "sound": "sad_trombone"},
        ],
        "music_mood": "funny",
        "ending_text": "Follow for part 2",
        "source": "template",
    }


def _num(v, default: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if f == f and abs(f) != float("inf") else default


def validate(plan: dict, duration: float) -> dict:
    """Clamp everything into safe, renderable ranges."""
    out = dict(plan)
    sm = plan.get("slowmo") or {}
    a, b = _num(sm.get("start")), _num(sm.get("end"))
    a, b = max(0.0, min(a, duration)), max(0.0, min(b, duration))
    if sm.get("enabled") and b - a >= 0.6:
        b = min(b, a + 2.5)
        out["slowmo"] = {"enabled": True, "start": round(a, 2), "end": round(b, 2)}
    else:
        out["slowmo"] = {"enabled": False, "start": 0.0, "end": 0.0}
    limits = {"zoom": (0.3, 2.0), "shake": (0.2, 1.2), "flash": (0.06, 0.25), "bw": (0.5, 3.5), "sticker": (0.6, 2.5),
              "sfx": (0.1, 6.0), "narration": (0.5, 6.0)}
    caps = {"sticker": 4, "narration": 3, "sfx": 8, "zoom": 4, "shake": 4, "flash": 4, "bw": 1}
    counts: dict[str, int] = {}
    events = []
    for ev in sorted(plan.get("events") or [], key=lambda e: _num(e.get("t"))):
        kind = ev.get("type")
        if kind not in limits:
            continue
        counts[kind] = counts.get(kind, 0) + 1
        if counts[kind] > caps[kind]:
            continue
        lo, hi = limits[kind]
        # start early enough that even the shortest version of the effect fits inside the clip
        t = max(0.0, min(_num(ev.get("t")), duration - lo))
        dur = min(max(lo, min(_num(ev.get("dur"), lo), hi)), duration - t)
        text = str(ev.get("text") or "").strip()
        if kind == "sticker":
            text = " ".join(text.split()[:4])[:28]
            if not text:
                continue
        if kind == "narration":
            text = " ".join(text.split()[:14])
            if not text:
                continue
        events.append({"type": kind, "t": round(t, 2), "dur": round(dur, 2), "text": text,
                       "sound": str(ev.get("sound") or "").strip()[:120]})
    out["events"] = events
    out["music_mood"] = plan.get("music_mood") if plan.get("music_mood") in MOODS else "funny"
    out["ending_text"] = " ".join(str(plan.get("ending_text") or "").split()[:6])[:40]
    out["hook"] = " ".join(str(plan.get("hook") or "").split()[:8])
    return out


class TimeMap:
    """Clip time -> output time, accounting for the slow-motion window."""

    def __init__(self, slowmo: dict, factor: float = 0.5):
        self.on = bool(slowmo.get("enabled"))
        self.a, self.b, self.f = float(slowmo.get("start", 0)), float(slowmo.get("end", 0)), factor

    @property
    def extra(self) -> float:
        return (self.b - self.a) * (1 / self.f - 1) if self.on else 0.0

    def __call__(self, t: float) -> float:
        if not self.on or t <= self.a:
            return t
        if t < self.b:
            return self.a + (t - self.a) / self.f
        return t + self.extra
