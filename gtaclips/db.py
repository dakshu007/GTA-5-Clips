"""SQLite storage: streamers, runs, clips, posts, activity log and settings."""
from __future__ import annotations

import copy
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from . import config


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)


class Streamer(Base):
    __tablename__ = "streamers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    platform: Mapped[str] = mapped_column(String(20))  # twitch | youtube | kick | other
    channel: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(500))
    permission: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_watch: Mapped[bool] = mapped_column(Boolean, default=False)
    layout: Mapped[str] = mapped_column(String(20), default="auto")  # auto | split | blur | crop
    facecam: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {x,y,w,h} as 0..1 fractions
    cpm: Mapped[float] = mapped_column(Float, default=0.0)  # $ paid per 1k views (campaign / deal)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "channel": self.channel,
            "url": self.url,
            "permission": self.permission,
            "auto_watch": self.auto_watch,
            "layout": self.layout,
            "facecam": self.facecam,
            "cpm": self.cpm,
            "notes": self.notes,
            "is_live": self.is_live,
            "last_checked": iso(self.last_checked),
            "created_at": iso(self.created_at),
        }


class Run(Base):
    """One capture session: a live stream being watched, or a VOD being processed."""

    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    streamer_id: Mapped[int | None] = mapped_column(ForeignKey("streamers.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(10))  # live | vod
    source: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="starting")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "streamer_id": self.streamer_id,
            "kind": self.kind,
            "source": self.source,
            "title": self.title,
            "status": self.status,
            "progress": self.progress,
            "error": self.error,
            "stats": self.stats or {},
            "started_at": iso(self.started_at),
            "ended_at": iso(self.ended_at),
        }


class Clip(Base):
    __tablename__ = "clips"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    streamer_id: Mapped[int | None] = mapped_column(ForeignKey("streamers.id"), nullable=True)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    peak: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    transcript: Mapped[str] = mapped_column(Text, default="")
    words: Mapped[list] = mapped_column(JSON, default=list)
    title: Mapped[str] = mapped_column(String(300), default="")
    hook: Mapped[str] = mapped_column(String(200), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    ai: Mapped[dict] = mapped_column(JSON, default=dict)
    virality: Mapped[float] = mapped_column(Float, default=0.0)
    layout: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(20), default="detected")
    raw_path: Mapped[str] = mapped_column(String(500), default="")
    video_path: Mapped[str] = mapped_column(String(500), default="")
    thumb_path: Mapped[str] = mapped_column(String(500), default="")
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "streamer_id": self.streamer_id,
            "start": self.start,
            "end": self.end,
            "peak": self.peak,
            "score": self.score,
            "signals": self.signals or {},
            "transcript": self.transcript,
            "title": self.title,
            "hook": self.hook,
            "caption": self.caption,
            "hashtags": self.hashtags or [],
            "ai": self.ai or {},
            "virality": self.virality,
            "layout": self.layout,
            "status": self.status,
            "has_video": bool(self.video_path),
            "has_thumb": bool(self.thumb_path),
            "duration": self.duration,
            "error": self.error,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey("clips.id"))
    platform: Mapped[str] = mapped_column(String(20))  # youtube | instagram
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled|posting|posted|failed|cancelled
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    external_id: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    history: Mapped[list] = mapped_column(JSON, default=list)  # [{ts, views}]
    error: Mapped[str] = mapped_column(Text, default="")
    stats_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "clip_id": self.clip_id,
            "platform": self.platform,
            "status": self.status,
            "scheduled_at": iso(self.scheduled_at),
            "posted_at": iso(self.posted_at),
            "attempts": self.attempts,
            "external_id": self.external_id,
            "url": self.url,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "error": self.error,
            "stats_updated_at": iso(self.stats_updated_at),
        }


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    level: Mapped[str] = mapped_column(String(10), default="info")
    kind: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ts": iso(self.ts),
            "level": self.level,
            "kind": self.kind,
            "message": self.message,
            "data": self.data or {},
        }


_engine = None
_SessionLocal: sessionmaker | None = None
_init_lock = threading.Lock()


def init(db_url: str | None = None) -> None:
    global _engine, _SessionLocal
    with _init_lock:
        config.ensure_dirs()
        url = db_url or f"sqlite:///{config.DB_PATH}"
        _engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(_engine, "connect")
        def _pragmas(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

        Base.metadata.create_all(_engine)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


@contextmanager
def session() -> Iterator[Session]:
    if _SessionLocal is None:
        init()
    assert _SessionLocal is not None
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------------------------------------------------------------- settings

DEFAULT_SETTINGS: dict[str, Any] = {
    "general": {
        "game": "GTA VI",
        "timezone": "UTC",
        "public_base_url": "",  # e.g. https://clips.example.com (needed for YouTube OAuth redirect)
    },
    "detection": {
        "threshold": 0.55,
        "weights": {"audio": 1.0, "chat": 1.3, "speech": 0.9, "motion": 0.5, "game": 1.2},
        "pre_roll": 25.0,
        "post_roll": 15.0,
        "min_len": 40.0,
        "max_len": 55.0,
        "cooldown": 25.0,
        "warmup": 20.0,
        "buffer_minutes": 15,
        "max_clips_per_vod": 20,
        "chat_delay": 0.0,
        "hype_words": [
            "lmao", "lmfao", "kekw", "omegalul", "lul", "lol", "💀", "😂", "🤣", "w", "pog", "pogchamp",
            "poggers", "clip", "clip it", "no way", "noway", "bro", "wtf", "insane", "holy", "ez", "gg",
            "oh my god", "omg", "letsgo", "lets go", "huge", "crazy",
        ],
        "speech_words": [
            "no way", "oh my god", "what the", "let's go", "lets go", "bro", "dude", "are you kidding",
            "did you see", "clip that", "clip it", "insane", "holy", "run", "go go go", "nooo", "yes",
        ],
        "game_words": ["WASTED", "BUSTED", "MISSION PASSED", "MISSION FAILED", "WANTED"],
        "use_whisper_live": False,
        "use_ocr": False,
    },
    "render": {
        "default_layout": "auto",
        "captions": True,
        "caption_color": "#FFFFFF",
        "highlight_color": "#FFE600",
        "caption_size": 84,
        "caption_position": 0.70,
        "hook_seconds": 3.0,
        "credit_template": "🎥 {platform_url}",
        "progress_bar": True,
        "progress_color": "#FF2E88",
        "whisper_model": "base",
        "crf": 18,
        "preset": "veryfast",
        "hw_encode": True,
        "resolution": "1440p",  # 1080p | 1440p (YouTube serves 1440p uploads in better quality)
        "fps": "auto",  # auto = 60 when the gameplay is 60 fps | 60 | 30
        "enhance": True,  # light denoise + sharpen + colour pop
        "smooth_slowmo": True,  # interpolate slow-motion frames instead of repeating them
        "edit_style": "highlight",  # highlight | troll
        "music_volume": 0.16,
        "audio_mode": "game_only",  # game_only (mute streamer, keep game dialogue) | no_voices | original | mute
    },
    "ai": {
        "enabled": True,
        "api_key": "",
        "model": "claude-opus-5-5",
        "effort": "medium",
        "auto_reject": True,
        "min_virality": 35,
        "style": "Hype, funny, short. Gen-Z gaming Shorts energy. No clickbait lies.",
        "default_hashtags": ["#GTA6", "#GTAVI", "#gaming", "#shorts", "#twitch"],
    },
    "schedule": {
        "slots": ["11:30", "14:30", "17:30", "20:30"],
        "platforms": ["youtube", "instagram"],
        "autopilot": False,
        "autopilot_min_virality": 70,
        "max_retries": 3,
    },
    "youtube": {
        "client_id": "",
        "client_secret": "",
        "refresh_token": "",
        "channel_title": "",
        "api_key": "",  # for reading live chat
        "privacy": "public",
        "category_id": "20",
        "add_shorts_tag": True,
    },
    "instagram": {
        "user_id": "",
        "access_token": "",
        "graph_version": "v23.0",
        "upload_mode": "resumable",  # resumable | url
        "share_to_feed": True,
        "username": "",
    },
    "elevenlabs": {
        "enabled": True,
        "api_key": "",
        "voice_id": "",
        "voice_name": "",
        "use_voice": True,
        "use_sfx": True,
        "use_music": True,
        "tts_model": "",
        "sfx_model": "",
        "music_model": "",
    },
    "money": {
        "youtube_rpm": 0.06,  # $ per 1k Shorts views (own-channel ad share estimate)
        "instagram_rpm": 0.0,
        "default_cpm": 0.0,
        "currency": "$",
    },
}

SECRET_KEYS = {
    ("ai", "api_key"),
    ("youtube", "client_secret"),
    ("youtube", "refresh_token"),
    ("youtube", "api_key"),
    ("instagram", "access_token"),
    ("elevenlabs", "api_key"),
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def get_settings(section: str) -> dict:
    with session() as s:
        row = s.get(Setting, section)
        stored = row.value if row else {}
    return _merge(DEFAULT_SETTINGS.get(section, {}), stored or {})


def all_settings() -> dict:
    return {k: get_settings(k) for k in DEFAULT_SETTINGS}


def update_settings(section: str, values: dict) -> dict:
    with session() as s:
        row = s.get(Setting, section)
        current = dict(row.value) if row and row.value else {}
        merged = _merge(current, values)
        if row:
            row.value = json.loads(json.dumps(merged))
        else:
            s.add(Setting(key=section, value=merged))
    return get_settings(section)


def redacted_settings() -> dict:
    """Settings for the UI: secrets are replaced by a 'set/unset' marker."""
    out = all_settings()
    for section, key in SECRET_KEYS:
        val = out.get(section, {}).get(key)
        out[section][key] = "••••••••" if val else ""
    return out


def get_kv(key: str, default: Any = None) -> Any:
    with session() as s:
        row = s.get(Setting, key)
        return row.value if row else default


def set_kv(key: str, value: Any) -> None:
    with session() as s:
        row = s.get(Setting, key)
        if row:
            row.value = value
        else:
            s.add(Setting(key=key, value=value))


def log_event(kind: str, message: str, level: str = "info", **data: Any) -> dict:
    with session() as s:
        ev = Event(kind=kind, message=message, level=level, data=data)
        s.add(ev)
        s.flush()
        out = ev.to_dict()
    return out


def recent_events(limit: int = 60) -> list[dict]:
    with session() as s:
        rows = s.scalars(select(Event).order_by(Event.id.desc()).limit(limit)).all()
        return [r.to_dict() for r in rows]
