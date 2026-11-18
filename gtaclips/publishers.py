"""Uploaders for YouTube Shorts (Data API v3) and Instagram Reels (Graph API)."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

from . import db, media

log = logging.getLogger(__name__)


class PublishError(RuntimeError):
    pass


# ================================================================ YouTube

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
YT_API = "https://www.googleapis.com/youtube/v3"
YT_UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
YT_SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


_yt_token: dict = {"token": "", "exp": 0.0}


def youtube_redirect_uri(base_url: str) -> str:
    return base_url.rstrip("/") + "/oauth/youtube/callback"


def youtube_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    q = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": YT_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH}?{urlencode(q)}"


def youtube_exchange_code(code: str, redirect_uri: str) -> dict:
    cfg = db.get_settings("youtube")
    r = httpx.post(GOOGLE_TOKEN, data={
        "code": code,
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=30)
    if r.status_code != 200:
        raise PublishError(f"Google token exchange failed: {r.text[:300]}")
    tok = r.json()
    if not tok.get("refresh_token"):
        raise PublishError("Google did not return a refresh token. Remove the app's access in your Google account and connect again.")
    db.update_settings("youtube", {"refresh_token": tok["refresh_token"]})
    _yt_token.update(token=tok["access_token"], exp=time.time() + int(tok.get("expires_in", 3600)))
    try:
        ch = httpx.get(f"{YT_API}/channels", params={"part": "snippet", "mine": "true"},
                       headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=30).json()
        title = ch["items"][0]["snippet"]["title"] if ch.get("items") else ""
        db.update_settings("youtube", {"channel_title": title})
    except Exception:  # channel name is cosmetic
        pass
    return tok


def youtube_access_token() -> str:
    if _yt_token["token"] and _yt_token["exp"] > time.time() + 60:
        return _yt_token["token"]
    cfg = db.get_settings("youtube")
    if not cfg.get("refresh_token"):
        raise PublishError("YouTube is not connected (Settings → Accounts)")
    r = httpx.post(GOOGLE_TOKEN, data={
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "refresh_token": cfg["refresh_token"],
        "grant_type": "refresh_token",
    }, timeout=30)
    if r.status_code != 200:
        raise PublishError(f"YouTube token refresh failed: {r.text[:300]}")
    data = r.json()
    _yt_token.update(token=data["access_token"], exp=time.time() + int(data.get("expires_in", 3600)))
    return _yt_token["token"]


def youtube_upload(video: Path, title: str, description: str, tags: list[str]) -> dict:
    cfg = db.get_settings("youtube")
    token = youtube_access_token()
    if cfg.get("add_shorts_tag", True) and "#shorts" not in (title + description).lower():
        description = (description + "\n#Shorts").strip()
    meta = {
        "snippet": {
            "title": title[:100] or "Clip",
            "description": description[:4900],
            "tags": [t.lstrip("#") for t in tags][:30],
            "categoryId": str(cfg.get("category_id") or "20"),
        },
        "status": {
            "privacyStatus": cfg.get("privacy") or "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    size = video.stat().st_size
    with httpx.Client(timeout=httpx.Timeout(60, read=600, write=600)) as c:
        init = c.post(
            YT_UPLOAD,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(size),
            },
            json=meta,
        )
        if init.status_code != 200 or "location" not in init.headers:
            raise PublishError(f"YouTube upload init failed ({init.status_code}): {init.text[:400]}")
        with video.open("rb") as f:
            up = c.put(init.headers["location"], content=f.read(), headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
        if up.status_code not in (200, 201):
            raise PublishError(f"YouTube upload failed ({up.status_code}): {up.text[:400]}")
        try:
            vid = up.json()["id"]
        except Exception:  # uploaded fine, response unreadable: don't retry (would duplicate)
            log.warning("YouTube upload succeeded but the response had no video id")
            return {"external_id": "", "url": ""}
    return {"external_id": vid, "url": f"https://youtube.com/shorts/{vid}"}


def youtube_stats(ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    token = youtube_access_token()
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        r = httpx.get(f"{YT_API}/videos", params={"part": "statistics", "id": ",".join(ids[i : i + 50])},
                      headers={"Authorization": f"Bearer {token}"}, timeout=30)
        r.raise_for_status()
        for item in r.json().get("items", []):
            st = item.get("statistics", {})
            out[item["id"]] = {
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
            }
    return out


# ================================================================ Instagram

def _ig(cfg: dict) -> tuple[str, str, str]:
    if not cfg.get("user_id") or not cfg.get("access_token"):
        raise PublishError("Instagram is not connected (Settings → Accounts)")
    return f"https://graph.facebook.com/{cfg.get('graph_version') or 'v23.0'}", cfg["user_id"], cfg["access_token"]


def _ig_error(r: httpx.Response) -> str:
    try:
        body = r.json()
    except Exception:
        return f"HTTP {r.status_code}: {r.text[:300]}"
    if "debug_info" in body:  # the upload host (rupload) answers in its own format
        d = body["debug_info"] or {}
        return f"{d.get('type', 'error')}: {d.get('message', '')} (HTTP {r.status_code})"
    err = body.get("error", {})
    msg = err.get("error_user_msg") or err.get("message") or r.text[:300]
    return f"{msg} (code {err.get('code')}{', ' + str(err['error_subcode']) if err.get('error_subcode') else ''})"


IG_MAX_W = 1080  # Instagram stores and plays Reels at 1080x1920; sending more only risks a failed upload


def instagram_file(video: Path) -> Path:
    """A copy of the clip made exactly to Instagram's Reels spec.

    Instagram re-encodes every Reel to 1080x1920 anyway. Sending it a clean 1080p file
    (H.264 High, closed GOP, peak bitrate well under its 25 Mbps limit, AAC 48 kHz, moov atom
    first) uploads faster, avoids "ProcessingFailedError", and our sharp Lanczos downscale
    looks better than Instagram's own.
    """
    out = video.with_name(video.stem + "_ig.mp4")
    if out.exists() and out.stat().st_size > 1000 and out.stat().st_mtime >= video.stat().st_mtime:
        return out
    w, _h = media.video_size(video)
    fps = 30.0
    for st in media.probe(video).get("streams", []):
        if st.get("codec_type") == "video":
            num, _, den = str(st.get("avg_frame_rate") or "30/1").partition("/")
            try:
                fps = float(num) / float(den or 1)
            except (ValueError, ZeroDivisionError):
                pass
    fps = 60 if fps > 50 else 30
    vf = f"scale={IG_MAX_W}:-2:flags=lanczos," if w > IG_MAX_W else ""
    vf += "setsar=1,format=yuv420p"
    tmp = out.with_name(out.stem + ".tmp.mp4")

    def build(enc: list[str], dec: list[str]) -> list[str]:
        rate = ["-maxrate", "16M", "-bufsize", "24M", "-level", "4.2"] if enc[1] == "libx264" else []
        return [media.FFMPEG, "-v", "error", "-nostdin", "-y", *dec, "-i", str(video), "-map", "0:v:0", "-map", "0:a:0?",
                "-vf", vf, "-r", str(fps), *enc, *rate, "-g", str(fps * 2), "-bf", "2",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", str(tmp)]

    try:
        media.run_encode(build, timeout=900, bitrate="12M", crf=17, preset="medium")
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)
    return out


def instagram_check() -> dict:
    cfg = db.get_settings("instagram")
    base, uid, token = _ig(cfg)
    r = httpx.get(f"{base}/{uid}", params={"fields": "username,media_count", "access_token": token}, timeout=30)
    if r.status_code != 200:
        raise PublishError(_ig_error(r))
    data = r.json()
    db.update_settings("instagram", {"username": data.get("username", "")})
    return data


def _ig_container_and_upload(c: httpx.Client, base: str, uid: str, token: str, cfg: dict, video: Path,
                             caption: str, public_url: str | None) -> str:
    mode = cfg.get("upload_mode", "resumable")
    params = {
        "media_type": "REELS",
        "caption": caption[:2150],
        "share_to_feed": "true" if cfg.get("share_to_feed", True) else "false",
        "access_token": token,
    }
    if mode == "url":
        if not public_url:
            raise PublishError("Instagram URL mode needs a Public base URL in Settings → General")
        params["video_url"] = public_url
    else:
        params["upload_type"] = "resumable"
    r = c.post(f"{base}/{uid}/media", data=params)
    if r.status_code != 200:
        raise PublishError(f"Instagram container failed: {_ig_error(r)}")
    container = r.json()["id"]
    if mode != "url":
        upload_uri = r.json().get("uri") or f"https://rupload.facebook.com/ig-api-upload/{cfg.get('graph_version') or 'v23.0'}/{container}"
        size = video.stat().st_size
        with video.open("rb") as f:
            up = c.post(upload_uri, content=f.read(), headers={
                "Authorization": f"OAuth {token}",
                "offset": "0",
                "file_size": str(size),
                "Content-Type": "application/octet-stream",
            })
        if up.status_code != 200:
            raise _UploadFailed(f"Instagram video upload failed: {_ig_error(up)}")
    return container


class _UploadFailed(PublishError):
    """The video bytes were refused; Meta says to start again with a new container."""


def instagram_upload(video: Path, caption: str, public_url: str | None = None) -> dict:
    cfg = db.get_settings("instagram")
    base, uid, token = _ig(cfg)
    if cfg.get("upload_mode", "resumable") != "url":
        video = instagram_file(video)
    with httpx.Client(timeout=httpx.Timeout(60, read=600, write=600)) as c:
        container = ""
        for attempt in range(3):
            try:
                container = _ig_container_and_upload(c, base, uid, token, cfg, video, caption, public_url)
                break
            except _UploadFailed as exc:
                log.warning("Instagram upload attempt %d failed: %s", attempt + 1, exc)
                if attempt == 2:
                    raise
                time.sleep(8 * (attempt + 1))
        # wait for Instagram to process the video
        deadline = time.time() + 600
        status = ""
        while time.time() < deadline:
            st = c.get(f"{base}/{container}", params={"fields": "status_code,status", "access_token": token})
            status = st.json().get("status_code", "") if st.status_code == 200 else ""
            if status == "FINISHED":
                break
            if status in ("ERROR", "EXPIRED"):
                raise PublishError(f"Instagram processing failed: {st.json().get('status', status)} — check the clip meets "
                                   "Reels limits (3 s – 15 min, under 300 MB)")
            time.sleep(6)
        if status != "FINISHED":
            raise PublishError("Instagram processing timed out")
        pub = c.post(f"{base}/{uid}/media_publish", data={"creation_id": container, "access_token": token})
        if pub.status_code != 200:
            raise PublishError(f"Instagram publish failed: {_ig_error(pub)}")
        # published — from here on nothing may raise, or the retry would post it twice
        try:
            media_id = pub.json()["id"]
        except Exception:
            return {"external_id": "", "url": ""}
        link = ""
        try:
            info = c.get(f"{base}/{media_id}", params={"fields": "permalink", "access_token": token})
            if info.status_code == 200:
                link = info.json().get("permalink", "")
        except Exception as exc:
            log.warning("Instagram permalink lookup failed: %s", exc)
    return {"external_id": media_id, "url": link}


def instagram_stats(media_id: str) -> dict:
    cfg = db.get_settings("instagram")
    base, _uid, token = _ig(cfg)
    out = {"views": 0, "likes": 0, "comments": 0}
    r = httpx.get(f"{base}/{media_id}", params={"fields": "like_count,comments_count", "access_token": token}, timeout=30)
    if r.status_code == 200:
        d = r.json()
        out["likes"] = int(d.get("like_count", 0))
        out["comments"] = int(d.get("comments_count", 0))
    for metric in ("views", "plays"):  # Meta renamed plays → views; try both
        r = httpx.get(f"{base}/{media_id}/insights", params={"metric": metric, "access_token": token}, timeout=30)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                vals = data[0].get("values") or [{}]
                out["views"] = int(vals[0].get("value", 0) or data[0].get("total_value", {}).get("value", 0))
                break
    return out
