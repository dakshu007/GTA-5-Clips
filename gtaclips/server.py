"""FastAPI app: owner-only dashboard + JSON API + live event stream."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import shutil
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from . import analytics, auth, bus, capture, config, db, media, publishers, speech
from .db import Clip, Post, Run, Streamer, utcnow
from .engine import engine

log = logging.getLogger(__name__)

CSRF_HEADER = "x-gtaclips"
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".ts", ".flv", ".webm", ".m4v"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    await engine.start()
    if not auth.is_configured():
        code = auth.setup_code()
        banner = "=" * 60
        print(f"\n{banner}\n  FIRST-RUN SETUP CODE:  {code}\n  Open the dashboard and use this code to create your password.\n{banner}\n", flush=True)
    yield
    await engine.shutdown()


app = FastAPI(title="GTA Clip Engine", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    )
    return resp


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"


def require_auth(request: Request) -> None:
    if not auth.validate_session_token(request.cookies.get(auth.COOKIE_NAME)):
        raise HTTPException(401, "Not signed in")
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(403, "Missing CSRF header")


Auth = Depends(require_auth)


def _set_session(resp: JSONResponse, request: Request) -> JSONResponse:
    resp.set_cookie(auth.COOKIE_NAME, auth.make_session_token(), max_age=auth.SESSION_MAX_AGE, httponly=True,
                    samesite="lax", secure=_https(request), path="/")
    return resp


# ================================================================ pages

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html = (config.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


# ================================================================ auth

@app.get("/api/auth/status")
async def auth_status(request: Request) -> dict:
    return {
        "configured": auth.is_configured(),
        "authed": auth.validate_session_token(request.cookies.get(auth.COOKIE_NAME)),
    }


@app.post("/api/auth/setup")
async def auth_setup(request: Request) -> JSONResponse:
    body = await request.json()
    if auth.is_configured():
        raise HTTPException(409, "Already set up — sign in instead")
    ip = _ip(request)
    if wait := auth.locked_out(ip):
        raise HTTPException(429, f"Too many attempts. Try again in {wait // 60 + 1} min")
    code = str(body.get("code", "")).strip().upper()
    if not secrets.compare_digest(code, auth.setup_code()):
        auth.record_failure(ip)
        raise HTTPException(403, "Wrong setup code — it's printed in the server console")
    try:
        auth.set_password(str(body.get("password", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    auth.clear_failures(ip)
    bus.activity("security", "Owner password created")
    return _set_session(JSONResponse({"ok": True}), request)


@app.post("/api/auth/login")
async def auth_login(request: Request) -> JSONResponse:
    body = await request.json()
    ip = _ip(request)
    if wait := auth.locked_out(ip):
        raise HTTPException(429, f"Too many attempts. Try again in {wait // 60 + 1} min")
    await asyncio.sleep(0.4)  # slow down guessing
    if not auth.check_password(str(body.get("password", ""))):
        auth.record_failure(ip)
        bus.activity("security", f"Failed sign-in from {ip}", level="warn")
        raise HTTPException(401, "Wrong password")
    auth.clear_failures(ip)
    return _set_session(JSONResponse({"ok": True}), request)


@app.post("/api/auth/logout")
async def auth_logout() -> JSONResponse:
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE_NAME, path="/")
    return resp


@app.post("/api/auth/password", dependencies=[Auth])
async def change_password(request: Request) -> JSONResponse:
    body = await request.json()
    if not auth.check_password(str(body.get("current", ""))):
        raise HTTPException(403, "Current password is wrong")
    try:
        auth.set_password(str(body.get("new", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    bus.activity("security", "Password changed — other devices signed out")
    return _set_session(JSONResponse({"ok": True}), request)


@app.post("/api/auth/logout-all", dependencies=[Auth])
async def logout_all() -> JSONResponse:
    auth.revoke_all_sessions()
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE_NAME, path="/")
    return resp


# ================================================================ live events

@app.get("/api/stream", dependencies=[Auth])
async def event_stream(request: Request) -> StreamingResponse:
    q = bus.subscribe()

    async def gen():
        try:
            yield "retry: 3000\n\n"
            yield f"data: {json.dumps({'type': 'hello', 'ts': time.time()})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(msg, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/overview", dependencies=[Auth])
async def overview() -> dict:
    data = await asyncio.get_running_loop().run_in_executor(None, analytics.overview)
    data["live"] = {rid: w.status_dict() for rid, w in engine.live.items()}
    data["events"] = db.recent_events(40)
    return data


# ================================================================ streamers

@app.post("/api/streamers/parse", dependencies=[Auth])
async def parse_streamer(request: Request) -> dict:
    body = await request.json()
    try:
        return capture.parse_source(str(body.get("url", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/streamers", dependencies=[Auth])
async def list_streamers() -> list[dict]:
    with db.session() as s:
        out = []
        for st in s.scalars(select(Streamer).order_by(Streamer.name)):
            d = st.to_dict()
            d["clips"] = len(s.scalars(select(Clip.id).where(Clip.streamer_id == st.id)).all())
            d["watching"] = next((rid for rid, w in engine.live.items() if w.streamer and w.streamer["id"] == st.id), None)
            out.append(d)
        return out


STREAMER_FIELDS = {"name", "platform", "channel", "url", "permission", "auto_watch", "layout", "facecam", "cpm", "notes"}


@app.post("/api/streamers", dependencies=[Auth])
async def add_streamer(request: Request) -> dict:
    body = await request.json()
    try:
        parsed = capture.parse_source(str(body.get("url", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    with db.session() as s:
        st = Streamer(
            name=str(body.get("name") or parsed["name"])[:120],
            platform=parsed["platform"],
            channel=parsed["channel"],
            url=parsed["url"],
            permission=bool(body.get("permission", False)),
            auto_watch=bool(body.get("auto_watch", False)),
            layout=str(body.get("layout", "auto")),
            cpm=float(body.get("cpm", 0) or 0),
        )
        s.add(st)
        s.flush()
        d = st.to_dict()
    bus.activity("streamer", f"Added streamer {d['name']} ({d['platform']})")
    return d


@app.patch("/api/streamers/{sid}", dependencies=[Auth])
async def edit_streamer(sid: int, request: Request) -> dict:
    body = await request.json()
    with db.session() as s:
        st = s.get(Streamer, sid)
        if not st:
            raise HTTPException(404)
        if "url" in body and body["url"] != st.url:
            parsed = capture.parse_source(body["url"])
            st.platform, st.channel, st.url = parsed["platform"], parsed["channel"], parsed["url"]
        for k, v in body.items():
            if k in STREAMER_FIELDS and k not in ("url", "platform", "channel"):
                if k == "layout" and v not in ("auto", "split", "blur", "crop"):
                    continue
                if k == "cpm":
                    v = float(v or 0)
                setattr(st, k, v)
        d = st.to_dict()
    bus.publish("streamer", streamer=d)
    return d


@app.delete("/api/streamers/{sid}", dependencies=[Auth])
async def delete_streamer(sid: int) -> dict:
    for rid, w in list(engine.live.items()):
        if w.streamer and w.streamer["id"] == sid:
            engine.stop_run(rid)
    with db.session() as s:
        st = s.get(Streamer, sid)
        if not st:
            raise HTTPException(404)
        for c in s.scalars(select(Clip).where(Clip.streamer_id == sid)):
            c.streamer_id = None
        for r in s.scalars(select(Run).where(Run.streamer_id == sid)):
            r.streamer_id = None
        s.delete(st)
    return {"ok": True}


@app.post("/api/streamers/{sid}/watch", dependencies=[Auth])
async def watch_streamer(sid: int) -> dict:
    try:
        rid = engine.start_live(sid)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"run_id": rid}


@app.post("/api/streamers/{sid}/check", dependencies=[Auth])
async def check_streamer(sid: int) -> dict:
    return await asyncio.get_running_loop().run_in_executor(engine.io_pool, engine.check_live, sid)


@app.get("/api/streamers/{sid}/frame", dependencies=[Auth])
async def streamer_frame(sid: int) -> FileResponse:
    """A full 16:9 frame from this streamer, for drawing the facecam box."""
    src: Path | None = None
    for rid, w in engine.live.items():
        if w.streamer and w.streamer["id"] == sid and w.cap and w.cap.segments:
            src = w.cap.segments[-1].path
    if src is None:
        with db.session() as s:
            c = s.scalars(select(Clip).where(Clip.streamer_id == sid, Clip.raw_path != "").order_by(Clip.id.desc())).first()
            if c and Path(c.raw_path).exists():
                src = Path(c.raw_path)
    if src is None or not src.exists():
        raise HTTPException(404, "No footage yet — watch the stream or process a VOD first")
    out = config.CLIPS_DIR / f"frame_{sid}.jpg"
    await asyncio.get_running_loop().run_in_executor(None, lambda: media.snapshot(src, 1.0, out, width=1280))
    return FileResponse(out, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ================================================================ runs / live / vod

@app.get("/api/runs", dependencies=[Auth])
async def list_runs(limit: int = 30) -> list[dict]:
    with db.session() as s:
        rows = [r.to_dict() for r in s.scalars(select(Run).order_by(Run.id.desc()).limit(min(limit, 200)))]
    for r in rows:
        w = engine.live.get(r["id"])
        if w:
            r["live"] = w.status_dict()
    return rows


@app.post("/api/runs/{rid}/stop", dependencies=[Auth])
async def stop_run(rid: int) -> dict:
    engine.stop_run(rid)
    return {"ok": True}


@app.post("/api/live", dependencies=[Auth])
async def watch_url(request: Request) -> dict:
    body = await request.json()
    simulate = body.get("simulate")
    if simulate:
        p = Path(simulate)
        if not p.is_absolute():
            p = config.UPLOADS_DIR / p
        p = p.resolve()
        if not p.is_relative_to(config.UPLOADS_DIR.resolve()) or not p.is_file():
            raise HTTPException(400, "Replay only works for files in the uploads folder")
        simulate = str(p)
    try:
        rid = engine.start_live(streamer_id=body.get("streamer_id"), url=body.get("url"), simulate=simulate)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"run_id": rid}


def _safe_name(name: str) -> str:
    stem = re.sub(r"[^\w.-]+", "_", Path(name).stem)[:80] or "upload"
    return f"{int(time.time())}_{stem}"


@app.post("/api/vod/upload", dependencies=[Auth])
async def vod_upload(file: UploadFile = File(...), streamer_id: str = Form("")) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(400, f"Unsupported file type {ext or '?'} — use {', '.join(sorted(VIDEO_EXT))}")
    dest = config.UPLOADS_DIR / (_safe_name(file.filename or "upload") + ext)
    with dest.open("wb") as f:
        while chunk := await file.read(4 * 1024 * 1024):
            f.write(chunk)
    sid = int(streamer_id) if streamer_id.strip().isdigit() else None
    rid = engine.start_vod(str(dest), sid, title=file.filename or dest.name)
    return {"run_id": rid}


@app.post("/api/vod/url", dependencies=[Auth])
async def vod_url(request: Request) -> dict:
    body = await request.json()
    url = str(body.get("url", "")).strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(400, "Paste a full http(s) link")
    sid = body.get("streamer_id")
    rid = engine.start_vod(url, int(sid) if sid else None, is_url=True, title=url)
    return {"run_id": rid}


# ================================================================ clips

def _clip_or_404(s, cid: int) -> Clip:
    c = s.get(Clip, cid)
    if not c:
        raise HTTPException(404, "clip not found")
    return c


@app.get("/api/clips", dependencies=[Auth])
async def list_clips(status: str = "", streamer_id: int | None = None, limit: int = 200) -> list[dict]:
    with db.session() as s:
        q = select(Clip).order_by(Clip.id.desc()).limit(min(limit, 500))
        if status:
            q = q.where(Clip.status.in_(status.split(",")))
        if streamer_id:
            q = q.where(Clip.streamer_id == streamer_id)
        clips = [c.to_dict() for c in s.scalars(q)]
        ids = [c["id"] for c in clips]
        posts: dict[int, list] = {}
        if ids:
            for p in s.scalars(select(Post).where(Post.clip_id.in_(ids))):
                posts.setdefault(p.clip_id, []).append(p.to_dict())
        names = {st.id: st.name for st in s.scalars(select(Streamer))}
    for c in clips:
        c["posts"] = posts.get(c["id"], [])
        c["streamer"] = names.get(c["streamer_id"], "")
    return clips


@app.get("/api/clips/{cid}", dependencies=[Auth])
async def get_clip(cid: int) -> dict:
    with db.session() as s:
        c = _clip_or_404(s, cid)
        d = c.to_dict()
        d["posts"] = [p.to_dict() for p in s.scalars(select(Post).where(Post.clip_id == cid))]
        st = s.get(Streamer, c.streamer_id) if c.streamer_id else None
        d["streamer"] = st.name if st else ""
        d["streamer_permission"] = st.permission if st else True
    return d


@app.patch("/api/clips/{cid}", dependencies=[Auth])
async def edit_clip(cid: int, request: Request) -> dict:
    body = await request.json()
    rerender = False
    with db.session() as s:
        c = _clip_or_404(s, cid)
        if "title" in body:
            c.title = str(body["title"])[:300]
        if "caption" in body:
            c.caption = str(body["caption"])[:2200]
        if "hashtags" in body:
            tags = body["hashtags"]
            if isinstance(tags, str):
                tags = tags.split()
            c.hashtags = [t if t.startswith("#") else f"#{t}" for t in (str(x).strip() for x in tags) if t][:15]
        if "hook" in body and str(body["hook"]) != c.hook:
            c.hook = str(body["hook"])[:200]
            rerender = True
        d = c.to_dict()
    if rerender and d["status"] not in ("rendering", "detected"):
        engine.enqueue_render(cid, layout=d["layout"] or None)
    bus.publish("clip", clip=d)
    return d


@app.post("/api/clips/{cid}/approve", dependencies=[Auth])
async def approve_clip(cid: int, request: Request) -> dict:
    body = await request.json()
    platforms = body.get("platforms") or db.get_settings("schedule").get("platforms") or ["youtube"]
    when = None
    if body.get("when"):
        try:
            when = datetime.fromisoformat(str(body["when"]).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "bad date")
    try:
        posts = engine.schedule_clip(cid, platforms, when)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if body.get("now"):
        for p in posts:
            engine.post_now(p["id"])
    return {"posts": posts}


@app.post("/api/clips/{cid}/reject", dependencies=[Auth])
async def reject_clip(cid: int) -> dict:
    with db.session() as s:
        c = _clip_or_404(s, cid)
        for p in s.scalars(select(Post).where(Post.clip_id == cid, Post.status == "scheduled")):
            p.status = "cancelled"
        c.status = "rejected"
        d = c.to_dict()
    bus.publish("clip", clip=d)
    return d


@app.post("/api/clips/{cid}/restore", dependencies=[Auth])
async def restore_clip(cid: int) -> dict:
    with db.session() as s:
        c = _clip_or_404(s, cid)
        c.status = "ready" if c.video_path else "detected"
        d = c.to_dict()
    if d["status"] == "detected":
        engine.enqueue_render(cid)
    bus.publish("clip", clip=d)
    return d


@app.post("/api/clips/{cid}/rerender", dependencies=[Auth])
async def rerender_clip(cid: int, request: Request) -> dict:
    body = await request.json()
    layout = body.get("layout")
    if layout and layout not in ("auto", "split", "blur", "crop"):
        raise HTTPException(400, "bad layout")
    with db.session() as s:
        c = _clip_or_404(s, cid)
        c.status = "rendering"
        d = c.to_dict()
    bus.publish("clip", clip=d)
    engine.enqueue_render(cid, layout=layout, rerun_ai=bool(body.get("rerun_ai")))
    return d


@app.delete("/api/clips/{cid}", dependencies=[Auth])
async def delete_clip(cid: int) -> dict:
    with db.session() as s:
        c = _clip_or_404(s, cid)
        if s.scalars(select(Post).where(Post.clip_id == cid, Post.status == "posted")).first():
            raise HTTPException(400, "Clip has been posted — reject it instead of deleting")
        for p in s.scalars(select(Post).where(Post.clip_id == cid)):
            s.delete(p)
        s.delete(c)
    shutil.rmtree(config.CLIPS_DIR / str(cid), ignore_errors=True)
    bus.publish("clip_deleted", id=cid)
    return {"ok": True}


def _clip_file(cid: int, attr: str) -> Path:
    with db.session() as s:
        c = _clip_or_404(s, cid)
        path = Path(getattr(c, attr) or "")
    if not path.is_file():
        raise HTTPException(404, "file not ready")
    return path


@app.get("/api/clips/{cid}/video", dependencies=[Auth])
async def clip_video(cid: int) -> FileResponse:
    return FileResponse(_clip_file(cid, "video_path"), media_type="video/mp4")


@app.get("/api/clips/{cid}/thumb", dependencies=[Auth])
async def clip_thumb(cid: int) -> FileResponse:
    return FileResponse(_clip_file(cid, "thumb_path"), media_type="image/jpeg")


@app.get("/api/clips/{cid}/download", dependencies=[Auth])
async def clip_download(cid: int) -> FileResponse:
    path = _clip_file(cid, "video_path")
    return FileResponse(path, media_type="video/mp4", filename=f"clip_{cid}.mp4")


@app.get("/public/media/{token}")
async def public_media(token: str) -> FileResponse:
    """Short-lived signed link so Instagram can fetch a video (URL upload mode only)."""
    cid = auth.verify_media(token)
    if cid is None:
        raise HTTPException(404)
    return FileResponse(_clip_file(cid, "video_path"), media_type="video/mp4")


# ================================================================ posts

@app.get("/api/posts", dependencies=[Auth])
async def list_posts(status: str = "", limit: int = 300) -> list[dict]:
    with db.session() as s:
        q = select(Post).order_by(Post.scheduled_at.desc()).limit(min(limit, 1000))
        if status:
            q = q.where(Post.status.in_(status.split(",")))
        posts = [p.to_dict() for p in s.scalars(q)]
        clips = {c.id: c for c in s.scalars(select(Clip).where(Clip.id.in_([p["clip_id"] for p in posts])))} if posts else {}
        names = {st.id: st.name for st in s.scalars(select(Streamer))}
    for p in posts:
        c = clips.get(p["clip_id"])
        p["title"] = (c.title or c.hook) if c else ""
        p["streamer"] = names.get(c.streamer_id, "") if c else ""
        p["has_thumb"] = bool(c and c.thumb_path)
    return posts


@app.post("/api/posts/{pid}/now", dependencies=[Auth])
async def post_now(pid: int) -> dict:
    engine.post_now(pid)
    return {"ok": True}


@app.post("/api/posts/{pid}/cancel", dependencies=[Auth])
async def cancel_post(pid: int) -> dict:
    with db.session() as s:
        p = s.get(Post, pid)
        if not p:
            raise HTTPException(404)
        if p.status in ("posting", "posted"):
            raise HTTPException(400, f"Post is already {p.status}")
        p.status = "cancelled"
        d = p.to_dict()
        clip = s.get(Clip, p.clip_id)
        if clip and not s.scalars(select(Post).where(Post.clip_id == clip.id, Post.status.in_(("scheduled", "posting", "posted")))).first():
            clip.status = "ready"
            bus.publish("clip", clip=clip.to_dict())
    bus.publish("post", post=d)
    return d


@app.post("/api/posts/{pid}/retry", dependencies=[Auth])
async def retry_post(pid: int) -> dict:
    with db.session() as s:
        p = s.get(Post, pid)
        if not p:
            raise HTTPException(404)
        p.status = "scheduled"
        p.attempts = 0
        p.error = ""
        p.scheduled_at = utcnow()
        d = p.to_dict()
    bus.publish("post", post=d)
    return d


@app.patch("/api/posts/{pid}", dependencies=[Auth])
async def reschedule_post(pid: int, request: Request) -> dict:
    body = await request.json()
    try:
        when = datetime.fromisoformat(str(body["scheduled_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        raise HTTPException(400, "bad date")
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    with db.session() as s:
        p = s.get(Post, pid)
        if not p or p.status != "scheduled":
            raise HTTPException(400, "only scheduled posts can be moved")
        p.scheduled_at = when
        d = p.to_dict()
    bus.publish("post", post=d)
    return d


# ================================================================ analytics

@app.get("/api/analytics", dependencies=[Auth])
async def get_analytics() -> dict:
    return await asyncio.get_running_loop().run_in_executor(None, analytics.overview)


@app.post("/api/analytics/refresh", dependencies=[Auth])
async def refresh_analytics() -> dict:
    return await asyncio.get_running_loop().run_in_executor(engine.io_pool, engine.refresh_stats)


@app.get("/api/analytics/autotune", dependencies=[Auth])
async def autotune() -> dict:
    return analytics.autotune_proposal()


@app.post("/api/analytics/autotune/apply", dependencies=[Auth])
async def autotune_apply() -> dict:
    prop = analytics.autotune_proposal()
    if not prop["ready"]:
        raise HTTPException(400, f"Need {prop['needed']} posted clips with views (have {prop['have']})")
    db.update_settings("detection", {"weights": prop["proposed"]})
    bus.activity("tuning", "Detection weights auto-tuned from your view data")
    return prop


# ================================================================ settings

def _base_url(request: Request) -> str:
    base = db.get_settings("general").get("public_base_url") or ""
    return base.rstrip("/") if base else str(request.base_url).rstrip("/")


@app.get("/api/settings", dependencies=[Auth])
async def get_settings(request: Request) -> dict:
    yt = db.get_settings("youtube")
    ig = db.get_settings("instagram")
    return {
        "settings": db.redacted_settings(),
        "status": {
            "whisper": speech.available(),
            "tesseract": shutil.which("tesseract") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "ffmpeg_libass": media.has_filter("subtitles"),
            "youtube_connected": bool(yt.get("refresh_token")),
            "youtube_channel": yt.get("channel_title", ""),
            "instagram_connected": bool(ig.get("user_id") and ig.get("access_token")),
            "instagram_username": ig.get("username", ""),
            "youtube_redirect_uri": publishers.youtube_redirect_uri(_base_url(request)),
            "ai_key_set": bool(db.get_settings("ai").get("api_key")),
        },
    }


@app.put("/api/settings/{section}", dependencies=[Auth])
async def put_settings(section: str, request: Request) -> dict:
    if section not in db.DEFAULT_SETTINGS:
        raise HTTPException(404)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400)
    clean = {}
    for k, v in body.items():
        if k not in db.DEFAULT_SETTINGS[section]:
            continue
        if (section, k) in db.SECRET_KEYS and isinstance(v, str) and "•" in v:
            continue  # unchanged secret placeholder
        clean[k] = v
    if section == "general" and "timezone" in clean:
        from zoneinfo import ZoneInfo

        try:
            ZoneInfo(clean["timezone"])
        except Exception:
            raise HTTPException(400, f"Unknown timezone {clean['timezone']}")
    db.update_settings(section, clean)
    return db.redacted_settings()[section]


@app.post("/api/settings/youtube/connect", dependencies=[Auth])
async def youtube_connect(request: Request) -> dict:
    cfg = db.get_settings("youtube")
    if not cfg.get("client_id") or not cfg.get("client_secret"):
        raise HTTPException(400, "Save your Google OAuth client ID and secret first")
    state = auth.sign_state({"n": secrets.token_hex(8)})
    return {"url": publishers.youtube_auth_url(cfg["client_id"], publishers.youtube_redirect_uri(_base_url(request)), state)}


@app.get("/oauth/youtube/callback")
async def youtube_callback(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    if not auth.validate_session_token(request.cookies.get(auth.COOKIE_NAME)):
        return RedirectResponse("/#/settings?yt=signin")
    if error or not code or not auth.verify_state(state):
        return RedirectResponse(f"/#/settings?yt=error&msg={error or 'bad_state'}")
    try:
        await asyncio.get_running_loop().run_in_executor(
            None, publishers.youtube_exchange_code, code, publishers.youtube_redirect_uri(_base_url(request)))
    except publishers.PublishError as exc:
        log.warning("youtube oauth: %s", exc)
        return RedirectResponse("/#/settings?yt=error")
    bus.activity("accounts", "YouTube channel connected")
    return RedirectResponse("/#/settings?yt=ok")


@app.post("/api/settings/youtube/disconnect", dependencies=[Auth])
async def youtube_disconnect() -> dict:
    db.update_settings("youtube", {"refresh_token": "", "channel_title": ""})
    publishers._yt_token.update(token="", exp=0)
    return {"ok": True}


@app.post("/api/settings/instagram/test", dependencies=[Auth])
async def instagram_test() -> dict:
    try:
        data = await asyncio.get_running_loop().run_in_executor(None, publishers.instagram_check)
    except publishers.PublishError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, **data}


@app.post("/api/settings/ai/test", dependencies=[Auth])
async def ai_test() -> dict:
    import anthropic

    cfg = db.get_settings("ai")

    def call() -> str:
        client = anthropic.Anthropic(api_key=cfg["api_key"]) if cfg.get("api_key") else anthropic.Anthropic()
        r = client.messages.create(model=cfg.get("model") or "claude-opus-5-5", max_tokens=200,
                                   output_config={"effort": "low"},
                                   messages=[{"role": "user", "content": "Reply with exactly: ready"}])
        return next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()

    try:
        reply = await asyncio.get_running_loop().run_in_executor(None, call)
    except anthropic.AuthenticationError:
        raise HTTPException(400, "Anthropic rejected the API key")
    except Exception as exc:
        raise HTTPException(400, f"AI test failed: {exc}")
    return {"ok": True, "reply": reply}
