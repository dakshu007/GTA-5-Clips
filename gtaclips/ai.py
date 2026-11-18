"""AI editor: Claude watches a few frames + reads the transcript and decides whether the
moment is worth posting, then writes the hook, title, caption and hashtags.

Works without an API key too — it falls back to template copy so the pipeline never stalls.
"""
from __future__ import annotations

import base64
import json
import logging
import random
from pathlib import Path

import anthropic

log = logging.getLogger(__name__)

SCHEMA = {
    "type": "object",
    "properties": {
        "keep": {"type": "boolean", "description": "Is this a genuinely postable moment?"},
        "virality": {"type": "integer", "description": "0-100 estimate of how well this performs as a Short"},
        "reason": {"type": "string", "description": "One sentence: what happens and why it works (or doesn't)"},
        "hook": {"type": "string", "description": "On-screen hook text for the first 3 seconds, max 7 words, no emoji"},
        "title": {"type": "string", "description": "YouTube Shorts title, max 80 characters, may include 1 emoji"},
        "caption": {"type": "string", "description": "Instagram Reel caption, 1-2 short lines, may include emoji"},
        "hashtags": {"type": "array", "items": {"type": "string"}, "description": "5-8 hashtags each starting with #"},
        "trim_start": {"type": "number", "description": "Seconds to cut from the start of the clip (0 if none)"},
        "trim_end": {"type": "number", "description": "Seconds to cut from the end of the clip (0 if none)"},
        "layout": {"type": "string", "enum": ["auto", "blur", "split", "crop"], "description": "Best vertical layout"},
    },
    "required": ["keep", "virality", "reason", "hook", "title", "caption", "hashtags", "trim_start", "trim_end", "layout"],
    "additionalProperties": False,
}

SYSTEM = """You are the editor for a gaming Shorts/Reels channel that posts clips from live streams of {game}.
You get frames from a short stream clip, the streamer's speech transcript, and the detection signals that flagged it.
Decide whether it's worth posting and write the packaging.

Rules:
- keep=false for dead air, menus, loading screens, AFK, ads/intermissions, or nothing visibly happening.
- The hook is the most important line: it must make someone stop scrolling in the first second. Describe the
  situation, not the outcome ("He stole a cop car with the cop inside"), max 7 words, no emoji, no hashtags.
- Never invent things that are not in the frames or transcript. No fake claims, no misleading clickbait.
- Always credit the streamer by name in the caption.
- Trim only dead time at the start or end; the clip must stay at least {min_len:.0f} seconds long.
- Style: {style}"""


def _client(api_key: str) -> anthropic.Anthropic:
    # short timeout: a stuck request must not hold up the render queue
    opts = {"timeout": 120.0, "max_retries": 1}
    return anthropic.Anthropic(api_key=api_key, **opts) if api_key else anthropic.Anthropic(**opts)


def _b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode()


def describe_signals(signals: dict) -> str:
    names = {
        "audio": "streamer audio spike (scream/laugh/explosion)",
        "motion": "sudden on-screen action",
        "chat": "chat exploded",
        "speech": "streamer said a hype phrase",
        "game": "in-game banner (WASTED/BUSTED/etc.)",
    }
    parts = [f"{names.get(k, k)}={v:.2f}" for k, v in signals.items() if k != "top" and isinstance(v, (int, float)) and v > 0.05]
    return ", ".join(parts) or "weak signals"


def fallback(streamer: str, signals: dict, transcript: str, ai_cfg: dict, game: str) -> dict:
    """Template copy when there is no API key or the API call fails."""
    top = signals.get("top", "audio")
    hooks = {
        "chat": ["Chat could not believe this", "Chat went absolutely feral", "Everyone in chat saw this"],
        "audio": ["Wait for his reaction", "He was NOT ready for this", "Listen to this reaction"],
        "motion": ["Watch what happens next", "This escalated way too fast", "Nobody expected this"],
        "speech": ["He actually said it", "Wait for it", "He called it"],
        "game": ["Wasted in record time", "Busted in seconds", "That went wrong fast"],
    }
    hook = random.choice(hooks.get(top, hooks["motion"]))
    tag_name = "".join(ch for ch in streamer if ch.isalnum())
    tags = list(ai_cfg.get("default_hashtags") or [])
    if tag_name:
        tags = [f"#{tag_name}"] + tags
    quote = transcript.strip().split(".")[0][:60] if transcript else ""
    title = f"{streamer} in {game} 💀" if not quote else f"\"{quote}\" — {streamer} {game} 💀"
    return {
        "keep": True,
        "virality": 50,
        "reason": f"Auto-detected ({describe_signals(signals)}). No AI review — add an Anthropic key for better picks.",
        "hook": hook,
        "title": title[:95],
        "caption": f"{hook} 😭\n🎥 {streamer}",
        "hashtags": tags[:8],
        "trim_start": 0.0,
        "trim_end": 0.0,
        "layout": "auto",
        "source": "template",
    }


def review_clip(
    *,
    frames: list[Path],
    transcript: str,
    signals: dict,
    streamer: str,
    duration: float,
    ai_cfg: dict,
    game: str,
    min_len: float = 12.0,
) -> dict:
    if not ai_cfg.get("enabled", True):
        return fallback(streamer, signals, transcript, ai_cfg, game)
    api_key = ai_cfg.get("api_key") or ""
    content: list[dict] = []
    for f in frames:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(f)}})
    content.append({
        "type": "text",
        "text": (
            f"Streamer: {streamer}\nClip length: {duration:.0f}s\n"
            f"Detection signals at the peak: {describe_signals(signals)}\n"
            f"Transcript of the streamer (may be empty or partial):\n\"\"\"\n{transcript[:3000] or '(no speech detected)'}\n\"\"\"\n"
            f"Frames are in time order around the peak moment.\n"
            f"Suggested hashtags to draw from: {' '.join(ai_cfg.get('default_hashtags') or [])}"
        ),
    })
    try:
        client = _client(api_key)
        request = dict(
            model=ai_cfg.get("model") or "claude-opus-5-5",
            max_tokens=16000,
            system=SYSTEM.format(game=game, style=ai_cfg.get("style", ""), min_len=min_len),
            messages=[{"role": "user", "content": content}],
            output_config={"effort": ai_cfg.get("effort") or "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        try:
            # server-side fallback: if the model declines, the API retries on a fallback model
            resp = client.beta.messages.create(**request, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        except anthropic.BadRequestError as exc:
            if "fallback" not in str(exc).lower():
                raise
            resp = client.messages.create(**request)
    except anthropic.AuthenticationError:
        log.warning("Anthropic key rejected; using template copy")
        out = fallback(streamer, signals, transcript, ai_cfg, game)
        out["reason"] = "Anthropic API key was rejected — check Settings → AI. " + out["reason"]
        return out
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
        log.warning("AI review failed: %s", exc)
        out = fallback(streamer, signals, transcript, ai_cfg, game)
        out["reason"] = f"AI review failed ({type(exc).__name__}); used template copy."
        return out
    except Exception as exc:  # e.g. no credentials configured at all
        log.info("AI review unavailable: %s", exc)
        return fallback(streamer, signals, transcript, ai_cfg, game)

    if resp.stop_reason == "refusal":
        out = fallback(streamer, signals, transcript, ai_cfg, game)
        out["reason"] = "AI declined to review this clip; used template copy."
        return out
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return fallback(streamer, signals, transcript, ai_cfg, game)
    data["virality"] = int(max(0, min(100, data.get("virality", 50))))
    data["hashtags"] = [h if h.startswith("#") else f"#{h}" for h in data.get("hashtags", []) if h.strip()][:10]
    data["trim_start"] = max(0.0, float(data.get("trim_start", 0)))
    data["trim_end"] = max(0.0, float(data.get("trim_end", 0)))
    if duration - data["trim_start"] - data["trim_end"] < min(min_len, duration):
        data["trim_start"] = data["trim_end"] = 0.0
    data["source"] = "claude"
    data["model"] = resp.model
    return data
