"""Stream ingest: platform URL parsing, live checks, rolling segment buffer, clip cutting."""
from __future__ import annotations

import csv
import json
import logging
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from . import media

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- URL helpers

def parse_source(text: str) -> dict:
    """Turn whatever the user pasted (URL or bare name) into platform/channel/url."""
    raw = text.strip()
    if not raw:
        raise ValueError("empty source")
    if "://" not in raw and "." not in raw.split("/")[0]:
        # bare channel name → assume Twitch
        name = raw.lstrip("@")
        return {"platform": "twitch", "channel": name, "url": f"https://www.twitch.tv/{name}", "name": name}
    if "://" not in raw:
        raw = "https://" + raw
    u = urlparse(raw)
    host = (u.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    parts = [p for p in u.path.split("/") if p]
    if host.endswith("twitch.tv"):
        if not parts:
            raise ValueError("Twitch URL has no channel")
        ch = parts[0]
        if ch == "videos":  # VOD link
            return {"platform": "twitch", "channel": "", "url": raw, "name": "Twitch VOD"}
        return {"platform": "twitch", "channel": ch, "url": f"https://www.twitch.tv/{ch}", "name": ch}
    if host.endswith("kick.com"):
        if not parts:
            raise ValueError("Kick URL has no channel")
        return {"platform": "kick", "channel": parts[0], "url": f"https://kick.com/{parts[0]}", "name": parts[0]}
    if host.endswith(("youtube.com", "youtu.be")):
        handle = next((p for p in parts if p.startswith("@")), "")
        if handle:
            return {"platform": "youtube", "channel": handle, "url": f"https://www.youtube.com/{handle}/live", "name": handle.lstrip("@")}
        if len(parts) >= 2 and parts[0] in ("channel", "c", "user"):
            return {"platform": "youtube", "channel": parts[1], "url": f"https://www.youtube.com/{parts[0]}/{parts[1]}/live", "name": parts[1]}
        return {"platform": "youtube", "channel": "", "url": raw, "name": "YouTube"}
    return {"platform": "other", "channel": "", "url": raw, "name": host or raw}


def platform_url(platform: str, channel: str, url: str) -> str:
    if platform == "twitch" and channel:
        return f"twitch.tv/{channel}"
    if platform == "kick" and channel:
        return f"kick.com/{channel}"
    if platform == "youtube" and channel:
        return f"youtube.com/{channel}"
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def streamlink_cmd() -> list[str]:
    return [sys.executable, "-m", "streamlink"]


def ytdlp_cmd() -> list[str]:
    return [sys.executable, "-m", "yt_dlp"]


def is_live(url: str, timeout: float = 45) -> tuple[bool, str]:
    """Ask streamlink whether the channel currently has a playable stream."""
    try:
        proc = subprocess.run(streamlink_cmd() + ["--json", url], capture_output=True, timeout=timeout)
        data = json.loads(proc.stdout or b"{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return False, f"check failed: {exc}"
    if data.get("streams"):
        title = (data.get("metadata") or {}).get("title") or ""
        return True, title
    return False, data.get("error", "offline")


def download_vod(url: str, out_dir: Path, on_progress=None) -> Path:
    """Download a past broadcast / video with yt-dlp (≤1080p) and return the file path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    template = str(out_dir / "%(id)s.%(ext)s")
    args = ytdlp_cmd() + [
        "--no-warnings", "--newline", "--no-playlist",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4", "-o", template, "--print", "after_move:filepath", url,
    ]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    final = ""
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        m = re.search(r"\[download\]\s+([\d.]+)%", line)
        if m and on_progress:
            on_progress(float(m.group(1)) / 100)
        if line.startswith("/") and Path(line).exists():
            final = line
    proc.wait()
    if proc.returncode != 0 or not final:
        raise RuntimeError("yt-dlp could not download that URL (private, region-locked or unsupported?)")
    return Path(final)


# ---------------------------------------------------------------- live capture

@dataclass
class Segment:
    path: Path
    t0: float  # start on the run timeline (seconds)
    t1: float
    wall: float  # wall-clock time when the segment finished


class LiveCapture:
    """streamlink → ffmpeg → rolling buffer of short MPEG-TS segments.

    ``simulate`` replays a local file in real time (handy for testing the live path).
    """

    def __init__(self, url: str, out_dir: Path, simulate: str | None = None, segment_time: int = 4, quality: str = "1080p60,1080p,936p60,720p60,720p,best"):
        self.url = url
        self.dir = out_dir
        self.simulate = simulate
        self.segment_time = segment_time
        self.quality = quality
        self.segments: list[Segment] = []
        self._seen = 0
        self._procs: list[subprocess.Popen] = []
        self._lock = threading.Lock()
        self.timeline_end = 0.0
        self.started_wall = 0.0
        self.log_tail: list[str] = []

    @property
    def list_file(self) -> Path:
        return self.dir / "segments.csv"

    def start(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        seg_pattern = str(self.dir / "seg_%07d.ts")
        ff_out = [
            "-map", "0:v:0?", "-map", "0:a:0?", "-c", "copy",
            "-f", "segment", "-segment_time", str(self.segment_time), "-reset_timestamps", "1",
            "-segment_list", str(self.list_file), "-segment_list_type", "csv", "-segment_format", "mpegts",
            seg_pattern,
        ]
        self.started_wall = time.time()
        if self.simulate:
            ff = subprocess.Popen(
                [media.FFMPEG, "-v", "error", "-nostdin", "-re", "-i", self.simulate] + ff_out,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            self._procs = [ff]
        else:
            sl_args = streamlink_cmd() + [
                "--stdout", "--retry-open", "3", "--stream-segment-threads", "2", "--hls-live-edge", "3",
                "--twitch-low-latency", "--kick-low-latency", self.url, self.quality,
            ]
            sl = subprocess.Popen(sl_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ff = subprocess.Popen(
                [media.FFMPEG, "-v", "error", "-nostdin", "-fflags", "+genpts", "-i", "pipe:0"] + ff_out,
                stdin=sl.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            assert sl.stdout is not None
            sl.stdout.close()  # ffmpeg owns the pipe now
            self._procs = [sl, ff]
        for p in self._procs:
            threading.Thread(target=self._drain, args=(p,), daemon=True).start()

    def _drain(self, proc: subprocess.Popen) -> None:
        if proc.stderr is None:
            return
        for line in iter(proc.stderr.readline, b""):
            text = line.decode(errors="replace").strip()
            if text:
                self.log_tail = (self.log_tail + [text])[-20:]

    def alive(self) -> bool:
        return bool(self._procs) and all(p.poll() is None for p in self._procs)

    def poll_segments(self) -> list[Segment]:
        """Return segments completed since the last call."""
        if not self.list_file.exists():
            return []
        try:
            with self.list_file.open(newline="") as f:
                rows = list(csv.reader(f))
        except OSError:
            return []
        new: list[Segment] = []
        now = time.time()
        for row in rows[self._seen :]:
            if len(row) < 3:
                break
            name, s, e = row[0], float(row[1]), float(row[2])
            dur = max(0.0, e - s)
            if dur <= 0:
                self._seen += 1
                continue
            seg = Segment(self.dir / name, self.timeline_end, self.timeline_end + dur, now)
            self.timeline_end += dur
            new.append(seg)
            self._seen += 1
        with self._lock:
            self.segments.extend(new)
        return new

    def wall_to_timeline(self, wall: float) -> float | None:
        """Map a wall-clock timestamp (e.g. a chat message) onto the run timeline."""
        with self._lock:
            if not self.segments:
                return None
            last = self.segments[-1]
        return last.t1 - (last.wall - wall)

    def prune(self, keep_seconds: float, protect_from: float | None = None) -> None:
        cutoff = self.timeline_end - keep_seconds
        if protect_from is not None:
            cutoff = min(cutoff, protect_from)
        with self._lock:
            keep, drop = [], []
            for s in self.segments:
                (drop if s.t1 < cutoff else keep).append(s)
            self.segments = keep
        for s in drop:
            s.path.unlink(missing_ok=True)

    def earliest(self) -> float:
        with self._lock:
            return self.segments[0].t0 if self.segments else 0.0

    def cut(self, start: float, end: float, out: Path) -> Path:
        with self._lock:
            segs = [s for s in self.segments if s.t1 > start and s.t0 < end and s.path.exists()]
        if not segs:
            raise RuntimeError("clip window is no longer in the buffer")
        lst = out.with_suffix(".txt")
        lst.write_text("".join(f"file '{concat_quote(s.path)}'\n" for s in segs))
        ss = max(0.0, start - segs[0].t0)
        try:
            media.run_encode(lambda enc, dec: [
                media.FFMPEG, "-v", "error", "-nostdin", "-y", *dec, "-f", "concat", "-safe", "0", "-i", str(lst),
                "-ss", f"{ss:.3f}", "-t", f"{end - start:.3f}", *enc,
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
            ], timeout=600, bitrate="16M", crf=18)
        finally:
            lst.unlink(missing_ok=True)
        return out

    def stop(self) -> None:
        for p in reversed(self._procs):
            if p.poll() is None:
                p.terminate()
        deadline = time.time() + 8
        for p in self._procs:
            try:
                p.wait(timeout=max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                p.kill()

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def concat_quote(path: Path) -> str:
    """Path for a single-quoted entry in an ffmpeg concat list (a quote becomes '\\'')."""
    return path.as_posix().replace("'", "'\\''")


def cut_file(src: str | Path, start: float, end: float, out: Path) -> Path:
    media.run_encode(lambda enc, dec: [
        media.FFMPEG, "-v", "error", "-nostdin", "-y", *dec, "-ss", f"{max(0.0, start):.3f}", "-i", str(src),
        "-t", f"{end - start:.3f}", "-map", "0:v:0", "-map", "0:a:0?", *enc,
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
    ], timeout=900, bitrate="16M", crf=18)
    return out
