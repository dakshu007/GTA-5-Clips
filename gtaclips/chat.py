"""Live chat listeners. Each one calls ``on_message(wall_time, weight, text)``.

* Twitch – anonymous read-only IRC over WebSocket (no account needed).
* YouTube – official Data API live chat polling (needs a YouTube API key in Settings).
* Kick – the public Pusher WebSocket the Kick website uses (best effort).
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import sys
import time
from typing import Callable

import httpx
import websockets

log = logging.getLogger(__name__)

OnMessage = Callable[[float, float, str], None]

HYPE_EMOTES = {"kekw", "omegalul", "lul", "pog", "pogchamp", "poggers", "pogu", "lulw", "monkas", "pepelaugh", "icant", "aware", "kappa", "ez"}


def message_weight(text: str, hype_words: list[str]) -> float:
    """1 per message, more for hype words, emotes and ALL-CAPS spam."""
    low = text.lower()
    weight = 1.0
    hits = 0
    for w in hype_words:
        w = w.lower().strip()
        if not w:
            continue
        if re.fullmatch(r"[\w' ]+", w):
            if re.search(rf"(?<![\w']){re.escape(w)}(?![\w'])", low):
                hits += 1
        elif w in low:
            hits += 1
    tokens = set(re.findall(r"[a-z]+", low))
    hits += len(tokens & HYPE_EMOTES)
    weight += min(hits, 4) * 0.75
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        weight += 0.5
    return weight


class ChatListener:
    def __init__(self, on_message: OnMessage, hype_words: list[str]):
        self.on_message = on_message
        self.hype_words = hype_words
        self.connected = False
        self.count = 0
        self.error = ""
        self._stop = asyncio.Event()

    def emit(self, text: str, extra: float = 0.0, ts: float | None = None) -> None:
        self.count += 1
        self.on_message(ts or time.time(), message_weight(text, self.hype_words) + extra, text)

    def stop(self) -> None:
        """Safe to call from any thread."""
        loop = getattr(self, "_loop", None)
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._stop.set)
        else:
            self._stop.set()

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        backoff = 2.0
        while not self._stop.is_set():
            try:
                await self._run_once()
                backoff = 2.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # network blips are normal for long streams
                self.connected = False
                self.error = str(exc)[:200]
                log.warning("%s chat error: %s", type(self).__name__, exc)
            if self._stop.is_set():
                break
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff + random.random())
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 60)
        self.connected = False

    async def _run_once(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


class TwitchChat(ChatListener):
    URL = "wss://irc-ws.chat.twitch.tv:443"

    def __init__(self, channel: str, on_message: OnMessage, hype_words: list[str]):
        super().__init__(on_message, hype_words)
        self.channel = channel.lower().lstrip("#")

    async def _run_once(self) -> None:
        async with websockets.connect(self.URL, ping_interval=60, open_timeout=20) as ws:
            await ws.send("CAP REQ :twitch.tv/tags twitch.tv/commands")
            await ws.send("PASS SCHMOOPIIE")
            await ws.send(f"NICK justinfan{random.randint(10000, 99999)}")
            await ws.send(f"JOIN #{self.channel}")
            self.connected = True
            self.error = ""
            while not self._stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                for line in str(raw).split("\r\n"):
                    if not line:
                        continue
                    if line.startswith("PING"):
                        await ws.send("PONG :tmi.twitch.tv")
                        continue
                    self._handle(line)

    def _handle(self, line: str) -> None:
        tags = {}
        rest = line
        if line.startswith("@"):
            tag_str, _, rest = line[1:].partition(" ")
            for kv in tag_str.split(";"):
                k, _, v = kv.partition("=")
                tags[k] = v
        if " PRIVMSG " in rest:
            text = rest.split(" :", 1)[1] if " :" in rest else ""
            extra = 0.0
            if tags.get("bits"):
                extra += min(5.0, int(tags["bits"] or 0) / 100)
            self.emit(text, extra)
        elif " USERNOTICE " in rest:  # subs, gift subs, raids
            text = rest.split(" :", 1)[1] if " :" in rest else tags.get("msg-id", "sub")
            self.emit(text, extra=3.0)


KICK_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
# Fallback if Kick's realtime API can't be reached. Kick rotated its old key in Oct 2026.
KICK_DEFAULT_PUSHER = {"app_key": "34bf7a0ff419a2a775b9", "cluster": "us2"}


def pusher_url(cfg: dict) -> str:
    return f"wss://ws-{cfg['cluster']}.pusher.com/app/{cfg['app_key']}?protocol=7&client=js&version=8.4.0&flash=false"


def parse_pusher_config(data: dict) -> dict:
    """Pick the Pusher entry out of Kick's realtime connection descriptor."""
    for c in (data.get("data") or {}).get("connections") or []:
        cred = c.get("credentials") or {}
        if c.get("provider") == "pusher" and cred.get("app_key") and cred.get("cluster"):
            return {"app_key": cred["app_key"], "cluster": cred["cluster"]}
    raise ValueError("no pusher connection in Kick realtime config")


class KickChat(ChatListener):
    def __init__(self, slug: str, on_message: OnMessage, hype_words: list[str]):
        super().__init__(on_message, hype_words)
        self.slug = slug.lower()
        self.channel_id: int | None = None
        self.chatroom_id: int | None = None
        self.pusher: dict | None = None

    async def _resolve(self) -> tuple[int, int]:
        """Channel id + chatroom id. kick.com sits behind Cloudflare, so plain HTTP requests
        often get 403 — reuse streamlink's Kick plugin, which carries the browser cookies and
        headers it already obtained for the video (and can re-solve the challenge with Chrome)."""
        errors = []
        try:
            return await asyncio.to_thread(kick_channel_via_streamlink, self.slug)
        except Exception as exc:
            errors.append(f"streamlink: {exc}")
        try:
            async with httpx.AsyncClient(timeout=15, headers={"User-Agent": KICK_UA, "Accept": "application/json"}) as c:
                r = await c.get(f"https://kick.com/api/v2/channels/{self.slug}")
                r.raise_for_status()
                d = r.json()
                return int(d["id"]), int(d["chatroom"]["id"])
        except Exception as exc:
            errors.append(f"direct: {exc}")
        raise RuntimeError("Kick blocked the chat lookup (Cloudflare). " + " | ".join(errors)[:300])

    async def _pusher_config(self) -> dict:
        """Ask Kick which Pusher app key/cluster its chat uses right now (they rotate it)."""
        body = {"client": {"id": "hypecut", "type": "web"}, "capabilities": {"accepted_providers": [{"provider": "pusher"}]}}
        url = f"https://web.kick.com/api/v1/realtime/channels/{self.channel_id}/chat/connection"
        headers = {"User-Agent": KICK_UA, "Accept": "application/json", "Content-Type": "application/json",
                   "Referer": "https://kick.com/", "Origin": "https://kick.com"}
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(url, json=body, headers=headers)
                r.raise_for_status()
                return parse_pusher_config(r.json())
        except Exception as exc:
            log.warning("Kick realtime config lookup failed (%s); using default chat key", exc)
            return dict(KICK_DEFAULT_PUSHER)

    async def _run_once(self) -> None:
        if self.chatroom_id is None:
            self.channel_id, self.chatroom_id = await self._resolve()
        if self.pusher is None or self.error.startswith("pusher 4001"):
            self.pusher = await self._pusher_config()
        async with websockets.connect(pusher_url(self.pusher), open_timeout=20) as ws:
            await ws.send(json.dumps({"event": "pusher:subscribe", "data": {"auth": "", "channel": f"chatrooms.{self.chatroom_id}.v2"}}))
            while not self._stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                msg = json.loads(raw)
                ev = msg.get("event", "")
                if ev == "pusher:error":
                    err = msg.get("data") or {}
                    if isinstance(err, str):
                        err = json.loads(err or "{}")
                    self.pusher = None  # fetch a fresh key on the next attempt
                    raise RuntimeError(f"pusher {err.get('code')}: {err.get('message')}")
                if ev == "pusher_internal:subscription_succeeded":
                    self.connected = True
                    self.error = ""
                elif ev == "pusher:ping":
                    await ws.send(json.dumps({"event": "pusher:pong", "data": {}}))
                elif ev.endswith("ChatMessageEvent"):
                    self.connected = True
                    data = json.loads(msg.get("data") or "{}")
                    self.emit(str(data.get("content", "")))
                elif ev.endswith(("SubscriptionEvent", "GiftedSubscriptionsEvent")):
                    self.emit("sub", extra=3.0)


def kick_channel_via_streamlink(slug: str) -> tuple[int, int]:
    """(channel_id, chatroom_id) using streamlink's Cloudflare-cleared Kick session."""
    from streamlink import Streamlink

    session = Streamlink()
    _name, plugincls, resolved = session.resolve_url(f"https://kick.com/{slug}")
    plugin = plugincls(session, resolved)  # loads streamlink's cached Kick cookies + headers
    api = f"https://kick.com/api/v2/channels/{slug}"

    def get():
        headers = plugin._get_api_headers() if hasattr(plugin, "_get_api_headers") else {"Accept": "application/json"}
        return plugin.session.http.get(api, headers=headers, raise_for_status=False, timeout=20)

    res = get()
    if res.status_code == 403 and hasattr(plugin, "_get_cookies_from_webbrowser") and plugin._get_cookies_from_webbrowser():
        res = get()
    if res.status_code != 200:
        raise RuntimeError(f"Kick API returned {res.status_code}")
    d = res.json()
    return int(d["id"]), int(d["chatroom"]["id"])


class YouTubeChat(ChatListener):
    API = "https://www.googleapis.com/youtube/v3"

    def __init__(self, video_url: str, api_key: str, on_message: OnMessage, hype_words: list[str]):
        super().__init__(on_message, hype_words)
        self.video_url = video_url
        self.api_key = api_key
        self.video_id: str | None = None
        self.chat_id: str | None = None

    async def _resolve_video_id(self) -> str:
        m = re.search(r"(?:v=|youtu\.be/|/live/|/shorts/)([\w-]{11})", self.video_url)
        if m:
            return m.group(1)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "yt_dlp", "--no-warnings", "--skip-download", "--print", "id", self.video_url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
        vid = out.decode().strip().splitlines()[-1] if out.strip() else ""
        if not vid:
            raise RuntimeError(f"could not resolve live video id: {err.decode()[-200:]}")
        return vid

    async def _run_once(self) -> None:
        if not self.api_key:
            raise RuntimeError("YouTube chat needs a YouTube API key in Settings → Accounts")
        async with httpx.AsyncClient(timeout=20) as c:
            if not self.video_id:
                self.video_id = await self._resolve_video_id()
            if not self.chat_id:
                r = await c.get(f"{self.API}/videos", params={"part": "liveStreamingDetails", "id": self.video_id, "key": self.api_key})
                r.raise_for_status()
                items = r.json().get("items", [])
                self.chat_id = (items[0].get("liveStreamingDetails") or {}).get("activeLiveChatId") if items else None
                if not self.chat_id:
                    raise RuntimeError("stream has no active live chat")
            page = None
            self.connected = True
            self.error = ""
            first = True
            while not self._stop.is_set():
                params = {"liveChatId": self.chat_id, "part": "snippet", "key": self.api_key, "maxResults": 2000}
                if page:
                    params["pageToken"] = page
                r = await c.get(f"{self.API}/liveChat/messages", params=params)
                r.raise_for_status()
                data = r.json()
                page = data.get("nextPageToken")
                if not first:  # first page is backlog
                    for item in data.get("items", []):
                        sn = item.get("snippet", {})
                        text = sn.get("displayMessage", "")
                        extra = 3.0 if sn.get("type") in ("superChatEvent", "newSponsorEvent", "membershipGiftingEvent") else 0.0
                        self.emit(text, extra)
                first = False
                # quota: each poll costs units, so never poll faster than every 8 s
                wait = max(8.0, data.get("pollingIntervalMillis", 8000) / 1000)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=wait)
                except asyncio.TimeoutError:
                    pass


def make_listener(platform: str, channel: str, url: str, on_message: OnMessage, hype_words: list[str], youtube_api_key: str = "") -> ChatListener | None:
    if platform == "twitch" and channel:
        return TwitchChat(channel, on_message, hype_words)
    if platform == "kick" and channel:
        return KickChat(channel, on_message, hype_words)
    if platform == "youtube":
        return YouTubeChat(url, youtube_api_key, on_message, hype_words)
    return None
