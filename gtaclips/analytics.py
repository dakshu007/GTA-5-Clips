"""Numbers for the dashboard: views, estimated earnings, what kind of moment performs best,
and data-driven tuning of the detection weights."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import func, select

from . import db
from .db import Clip, Post, Run, Streamer, utcnow


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def earnings_for(post: Post, streamer: Streamer | None, money: dict) -> float:
    rpm = float(money.get("youtube_rpm", 0) if post.platform == "youtube" else money.get("instagram_rpm", 0))
    cpm = float(streamer.cpm) if streamer and streamer.cpm else float(money.get("default_cpm", 0))
    return post.views / 1000.0 * (rpm + cpm)


def overview() -> dict:
    money = db.get_settings("money")
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    with db.session() as s:
        clip_counts = dict(s.execute(select(Clip.status, func.count()).group_by(Clip.status)).all())
        post_counts = dict(s.execute(select(Post.status, func.count()).group_by(Post.status)).all())
        clips_today = s.scalar(select(func.count()).select_from(Clip).where(Clip.created_at >= today)) or 0
        streamers = {st.id: st for st in s.scalars(select(Streamer))}
        posts = list(s.scalars(select(Post).where(Post.status == "posted")))
        clips = {c.id: c for c in s.scalars(select(Clip).where(Clip.id.in_([p.clip_id for p in posts])))} if posts else {}
        active_runs = [r.to_dict() for r in s.scalars(select(Run).where(Run.status.in_(("starting", "live", "processing", "downloading"))))]

        views = sum(p.views for p in posts)
        earn_total = 0.0
        by_platform: dict[str, dict] = defaultdict(lambda: {"views": 0, "posts": 0, "earnings": 0.0})
        by_streamer: dict[str, dict] = defaultdict(lambda: {"views": 0, "posts": 0, "earnings": 0.0})
        by_signal: dict[str, list[int]] = defaultdict(list)
        by_day: dict[str, dict] = defaultdict(lambda: {"views": 0, "posts": 0})
        top: list[dict] = []
        for p in posts:
            c = clips.get(p.clip_id)
            st = streamers.get(c.streamer_id) if c and c.streamer_id else None
            e = earnings_for(p, st, money)
            earn_total += e
            by_platform[p.platform]["views"] += p.views
            by_platform[p.platform]["posts"] += 1
            by_platform[p.platform]["earnings"] += e
            name = st.name if st else "Uploads"
            by_streamer[name]["views"] += p.views
            by_streamer[name]["posts"] += 1
            by_streamer[name]["earnings"] += e
            if c:
                by_signal[(c.signals or {}).get("top", "audio")].append(p.views)
            day = (_aware(p.posted_at) or utcnow()).date().isoformat()
            by_day[day]["views"] += p.views
            by_day[day]["posts"] += 1
            if c:
                top.append({"clip_id": c.id, "title": c.title or c.hook, "platform": p.platform, "views": p.views,
                            "likes": p.likes, "url": p.url, "streamer": name, "earnings": round(e, 2)})

    days = []
    start = (utcnow() - timedelta(days=29)).date()
    for i in range(30):
        d = (start + timedelta(days=i)).isoformat()
        days.append({"day": d, **by_day.get(d, {"views": 0, "posts": 0})})
    top.sort(key=lambda x: x["views"], reverse=True)
    return {
        "clips": clip_counts,
        "posts": post_counts,
        "clips_today": clips_today,
        "views": views,
        "earnings": round(earn_total, 2),
        "currency": money.get("currency", "$"),
        "by_platform": {k: {**v, "earnings": round(v["earnings"], 2)} for k, v in by_platform.items()},
        "by_streamer": sorted(({"name": k, **v, "earnings": round(v["earnings"], 2)} for k, v in by_streamer.items()),
                              key=lambda x: x["views"], reverse=True),
        "by_signal": {k: {"posts": len(v), "avg_views": round(sum(v) / len(v)) if v else 0} for k, v in by_signal.items()},
        "days": days,
        "top": top[:10],
        "active_runs": active_runs,
    }


def autotune_proposal(min_posts: int = 8) -> dict:
    """Correlate each signal's strength at the peak with how many views the clip got.

    Signals that predict views get more weight; signals that don't get less.
    """
    cfg = db.get_settings("detection")
    weights = dict(cfg.get("weights", {}))
    with db.session() as s:
        rows = s.execute(select(Clip.signals, func.sum(Post.views)).join(Post, Post.clip_id == Clip.id)
                         .where(Post.status == "posted").group_by(Clip.id)).all()
    if len(rows) < min_posts:
        return {"ready": False, "needed": min_posts, "have": len(rows), "current": weights, "proposed": weights, "correlations": {}}
    views = np.array([math.log1p(v or 0) for _sig, v in rows])
    corr: dict[str, float] = {}
    proposed = dict(weights)
    for k in weights:
        x = np.array([float((sig or {}).get(k, 0) or 0) for sig, _v in rows])
        if np.std(x) < 1e-6 or np.std(views) < 1e-6:
            continue
        r = float(np.corrcoef(x, views)[0, 1])
        if math.isnan(r):
            continue
        corr[k] = round(r, 3)
        proposed[k] = round(min(2.5, max(0.2, weights[k] * (1 + 0.6 * r))), 2)
    return {"ready": True, "have": len(rows), "current": weights, "proposed": proposed, "correlations": corr}
