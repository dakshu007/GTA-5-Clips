"""In-process pub/sub that feeds the dashboard's live Server-Sent Events stream.

Workers run in threads; the web server runs an asyncio loop. ``publish`` is safe to
call from any thread.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any

from . import db

_loop: asyncio.AbstractEventLoop | None = None
_subscribers: set[asyncio.Queue] = set()
_lock = threading.Lock()


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    with _lock:
        _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    with _lock:
        _subscribers.discard(q)


def _deliver(msg: dict) -> None:
    with _lock:
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass  # slow client; drop rather than block the engine


def publish(msg_type: str, **payload: Any) -> None:
    msg = {"type": msg_type, **payload}
    loop = _loop
    if loop is None or loop.is_closed():
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        _deliver(msg)
    else:
        loop.call_soon_threadsafe(_deliver, msg)


def activity(kind: str, message: str, level: str = "info", **data: Any) -> None:
    """Persist an activity-feed entry and push it live to the dashboard."""
    ev = db.log_event(kind, message, level=level, **data)
    publish("activity", event=ev)
