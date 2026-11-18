"""The orchestrator: live workers, VOD jobs, the render queue, the post scheduler,
auto-watch (go-live detection) and stats refresh."""
from __future__ import annotations

import asyncio
import logging
import shutil
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from . import ai, auth, bus, capture, chat, config, db, media, publishers, render, signals, speech, voice
from .db import Clip, Post, Run, Streamer, utcnow

log = logging.getLogger(__name__)

ACTIVE_RUN = ("starting", "live", "processing", "downloading")


class Engine:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.render_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="render")
        self.job_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vod")
        self.publish_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="publish")
        self.io_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="io")
        self.live: dict[int, LiveWorker] = {}
        self.vod_cancel: dict[int, threading.Event] = {}
        self._tasks: list[asyncio.Task] = []
        self._render_queue: set[int] = set()
        self.stages: dict[int, dict] = {}  # clip_id -> {stage, since} while a render job runs
        self._rq_lock = threading.Lock()

    # ------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        bus.bind_loop(self.loop)
        self._recover()
        self._tasks = [
            asyncio.create_task(self._scheduler_loop()),
            asyncio.create_task(self._autowatch_loop()),
            asyncio.create_task(self._stats_loop()),
        ]

    async def shutdown(self) -> None:
        for t in self._tasks:
            t.cancel()
        for w in list(self.live.values()):
            w.request_stop()
        for ev in self.vod_cancel.values():
            ev.set()
        for w in list(self.live.values()):
            w.join(timeout=10)
        for pool in (self.render_pool, self.job_pool, self.publish_pool, self.io_pool):
            pool.shutdown(wait=False, cancel_futures=True)

    def _recover(self) -> None:
        """After a restart: close dangling runs, resume unfinished renders and posts."""
        with db.session() as s:
            for run in s.scalars(select(Run).where(Run.status.in_(ACTIVE_RUN))):
                run.status = "stopped"
                run.error = run.error or "server restarted"
                run.ended_at = utcnow()
            for p in s.scalars(select(Post).where(Post.status == "posting")):
                p.status = "scheduled"
            for st in s.scalars(select(Streamer)):
                st.is_live = False
            todo = [c.id for c in s.scalars(select(Clip).where(Clip.status.in_(("detected", "rendering"))))]
        for cid in todo:
            self.enqueue_render(cid)
        for d in config.BUFFERS_DIR.glob("run_*"):
            shutil.rmtree(d, ignore_errors=True)

    # ------------------------------------------------------------ live

    def start_live(self, streamer_id: int | None = None, url: str | None = None, simulate: str | None = None) -> int:
        st: dict | None = None
        with db.session() as s:
            if streamer_id is not None:
                row = s.get(Streamer, streamer_id)
                if not row:
                    raise ValueError("streamer not found")
                st = row.to_dict()
                for w in self.live.values():
                    if w.streamer and w.streamer["id"] == streamer_id and w.is_alive():
                        raise ValueError(f"{row.name} is already being watched")
                url = row.url
            if not url and not simulate:
                raise ValueError("no stream URL")
            if st:
                label = st["name"]
            elif simulate:
                label = f"Replay · {Path(simulate).name}"
            else:
                label = url or "Stream"
            run = Run(streamer_id=streamer_id, kind="live", source=simulate or url or "", status="starting", title=label)
            s.add(run)
            s.flush()
            run_id = run.id
        worker = LiveWorker(self, run_id, st, url or "", simulate)
        self.live[run_id] = worker
        worker.start()
        bus.activity("live", f"Started watching {label}", run_id=run_id)
        bus.publish("run", run=self.run_dict(run_id))
        return run_id

    def stop_run(self, run_id: int) -> None:
        w = self.live.get(run_id)
        if w:
            w.request_stop()
        ev = self.vod_cancel.get(run_id)
        if ev:
            ev.set()

    def run_dict(self, run_id: int) -> dict:
        with db.session() as s:
            run = s.get(Run, run_id)
            d = run.to_dict() if run else {}
        w = self.live.get(run_id)
        if w:
            d["live"] = w.status_dict()
        return d

    def update_run(self, run_id: int, **fields) -> None:
        with db.session() as s:
            run = s.get(Run, run_id)
            if not run:
                return
            for k, v in fields.items():
                setattr(run, k, v)
        bus.publish("run", run=self.run_dict(run_id))

    # ------------------------------------------------------------ VOD

    def start_vod(self, source: str, streamer_id: int | None = None, is_url: bool = False, title: str = "") -> int:
        with db.session() as s:
            run = Run(streamer_id=streamer_id, kind="vod", source=source, status="downloading" if is_url else "processing",
                      title=title or Path(source).name)
            s.add(run)
            s.flush()
            run_id = run.id
        self.vod_cancel[run_id] = threading.Event()
        self.job_pool.submit(self._vod_job, run_id, source, streamer_id, is_url)
        bus.activity("vod", f"VOD queued: {title or source}", run_id=run_id)
        bus.publish("run", run=self.run_dict(run_id))
        return run_id

    def _vod_job(self, run_id: int, source: str, streamer_id: int | None, is_url: bool) -> None:
        cancel = self.vod_cancel[run_id]
        try:
            path = source
            if is_url:
                last = [0.0]

                def prog(p: float) -> None:
                    if p - last[0] >= 0.02:
                        last[0] = p
                        self.update_run(run_id, progress=round(p * 0.3, 3))

                path = str(capture.download_vod(source, config.UPLOADS_DIR, prog))
                self.update_run(run_id, source=path, status="processing", progress=0.3)
            cfg = db.get_settings("detection")
            render_cfg = db.get_settings("render")
            total = media.duration(path)
            if total <= 0:
                raise RuntimeError("could not read video duration")
            moments: list[signals.Moment] = []
            an = signals.Analyzer(cfg, on_moment=moments.append)
            chunk = 60.0
            base = 0.3 if is_url else 0.0
            has_audio = media.has_audio(path)
            off = 0.0
            while off < total:
                if cancel.is_set():
                    self.update_run(run_id, status="stopped", ended_at=utcnow())
                    return
                length = min(chunk, total - off)
                if has_audio:
                    signals.audio_features(an.tl, path, off, start=off, length=length)
                signals.motion_features(an.tl, path, off, start=off, length=length)
                if cfg.get("use_ocr"):
                    signals.ocr_features(an.tl, path, off, cfg.get("game_words", []), start=off, length=length)
                if cfg.get("use_whisper_live") and speech.available():
                    try:
                        words = speech.transcribe(path, render_cfg.get("whisper_model", "base"), start=off, length=length)
                        signals.speech_features(an.tl, words, off, cfg.get("speech_words", []))
                    except Exception as exc:
                        log.warning("speech signal skipped: %s", exc)
                off += length
                an.advance(off)
                self.update_run(run_id, progress=round(base + (1 - base) * off / total * 0.98, 3),
                                stats={"duration": round(total), "analyzed": round(off), "moments": len(moments)})
            an.advance(total, final=True)
            limit = int(cfg.get("max_clips_per_vod", 20))
            best = sorted(moments, key=lambda m: m.score, reverse=True)[:limit]
            for m in sorted(best, key=lambda m: m.start):
                self.create_clip(run_id, streamer_id, m)
            self.update_run(run_id, status="done", progress=1.0, ended_at=utcnow(),
                            stats={"duration": round(total), "analyzed": round(total), "moments": len(moments), "clips": len(best)})
            bus.activity("vod", f"VOD analyzed: {len(best)} clips found", run_id=run_id)
        except Exception as exc:
            log.exception("VOD job failed")
            self.update_run(run_id, status="error", error=str(exc)[:500], ended_at=utcnow())
            bus.activity("vod", f"VOD failed: {exc}", level="error", run_id=run_id)
        finally:
            self.vod_cancel.pop(run_id, None)

    # ------------------------------------------------------------ clips

    def create_clip(self, run_id: int, streamer_id: int | None, m: signals.Moment, raw_from: capture.LiveCapture | None = None) -> int:
        signals_d = dict(m.signals)
        signals_d["series"] = m.series[-90:]
        with db.session() as s:
            clip = Clip(run_id=run_id, streamer_id=streamer_id, start=m.start, end=m.end, peak=m.peak,
                        score=m.score, signals=signals_d, status="detected", duration=m.end - m.start)
            s.add(clip)
            s.flush()
            cid = clip.id
        clip_dir = config.CLIPS_DIR / str(cid)
        clip_dir.mkdir(parents=True, exist_ok=True)
        if raw_from is not None:
            try:
                raw_from.cut(m.start, m.end, clip_dir / "raw.mp4")
                with db.session() as s:
                    s.get(Clip, cid).raw_path = str(clip_dir / "raw.mp4")
            except Exception as exc:
                self._clip_failed(cid, f"cut failed: {exc}")
                return cid
        bus.activity("moment", f"Key moment detected (score {m.score:.2f}, {m.signals.get('top', '?')})", clip_id=cid, run_id=run_id)
        self.enqueue_render(cid)
        return cid

    def enqueue_render(self, clip_id: int, **opts) -> None:
        with self._rq_lock:
            if clip_id in self._render_queue and not opts:
                return
            self._render_queue.add(clip_id)
        self.render_pool.submit(self._render_job, clip_id, **opts)

    def _clip_failed(self, clip_id: int, err: str) -> None:
        with db.session() as s:
            c = s.get(Clip, clip_id)
            if c:
                c.status = "failed"
                c.error = err[:1000]
                d = c.to_dict()
        bus.publish("clip", clip=d)
        bus.activity("clip", f"Clip #{clip_id} failed: {err[:160]}", level="error", clip_id=clip_id)

    def stage(self, clip_id: int, stage: str | None) -> None:
        if stage is None:
            self.stages.pop(clip_id, None)
        else:
            self.stages[clip_id] = {"stage": stage, "since": time.time()}
        bus.publish("clip_stage", id=clip_id, stage=stage)

    def _render_job(self, clip_id: int, layout: str | None = None, rerun_ai: bool = False) -> None:
        try:
            self._render(clip_id, layout, rerun_ai)
        except Exception as exc:
            log.exception("render failed")
            self._clip_failed(clip_id, str(exc))
        finally:
            self.stage(clip_id, None)
            with self._rq_lock:
                self._render_queue.discard(clip_id)

    def _render(self, clip_id: int, layout_override: str | None, rerun_ai: bool) -> None:
        with db.session() as s:
            clip = s.get(Clip, clip_id)
            if not clip:
                return
            run = s.get(Run, clip.run_id)
            st = s.get(Streamer, clip.streamer_id) if clip.streamer_id else None
            clip.status = "rendering"
            clip.error = ""
            c = clip.to_dict()
            c["raw_path"], c["words"] = clip.raw_path, clip.words or []
            run_d = run.to_dict() if run else {}
            st_d = st.to_dict() if st else None
        bus.publish("clip", clip=c)

        render_cfg = db.get_settings("render")
        ai_cfg = db.get_settings("ai")
        general = db.get_settings("general")
        det_cfg = db.get_settings("detection")
        clip_dir = config.CLIPS_DIR / str(clip_id)
        clip_dir.mkdir(parents=True, exist_ok=True)
        raw = clip_dir / "raw.mp4"
        self.stage(clip_id, "Preparing")
        if not raw.exists():
            if run_d.get("kind") == "vod" and Path(run_d.get("source", "")).exists():
                capture.cut_file(run_d["source"], c["start"], c["end"], raw)
            else:
                raise RuntimeError("raw clip is missing (live buffer expired)")

        timings: dict[str, float] = {}
        t_step = time.time()
        audio_mode = str(render_cfg.get("audio_mode", "game_only"))
        words = c["words"]
        # captions transcribe the streamer's voice — pointless when that voice is removed
        want_captions = render_cfg.get("captions", True) and audio_mode == "original"
        if not words and speech.available() and want_captions:
            self.stage(clip_id, "Writing captions")
            try:
                words = speech.transcribe(raw, render_cfg.get("whisper_model", "base"))
            except Exception as exc:  # model download blocked, out of memory, ...
                log.warning("transcription failed, rendering without captions: %s", exc)
                bus.activity("clip", f"Captions skipped for #{clip_id}: speech model unavailable ({str(exc)[:80]})", level="warn")
        if not want_captions:
            words = []
        transcript = speech.words_to_text(words)
        timings["captions"] = time.time() - t_step
        raw_dur = media.duration(raw)
        peak_off = max(0.0, c["peak"] - c["start"])

        streamer_name = st_d["name"] if st_d else (run_d.get("title") or "Streamer")
        verdict = c["ai"] if c["ai"] and not rerun_ai else None
        t_step = time.time()
        if verdict is None:
            self.stage(clip_id, "AI editor")
            frames = render.ai_frames(raw, clip_dir, peak_off)
            verdict = ai.review_clip(frames=frames, transcript=transcript, signals=c["signals"], streamer=streamer_name,
                                     duration=raw_dur, ai_cfg=ai_cfg, game=general.get("game", "GTA VI"),
                                     min_len=float(det_cfg.get("min_len", 15)))
            for f in frames:
                f.unlink(missing_ok=True)
            fresh_ai = True
        else:
            fresh_ai = False

        facecam = st_d.get("facecam") if st_d else None
        if layout_override:
            layout = layout_override
        elif c["layout"] and not fresh_ai:
            layout = c["layout"]
        elif st_d and st_d.get("layout") not in (None, "", "auto"):
            layout = st_d["layout"]
        else:
            layout = render_cfg.get("default_layout", "auto")
        if layout == "split" and not facecam:
            layout = "crop"
        if layout not in ("blur", "split", "crop"):
            layout = "crop"  # auto: full-screen 9:16 gameplay, facecam kept out of frame

        hook = c["hook"] if (c["hook"] and not fresh_ai) else verdict.get("hook", "")
        purl = capture.platform_url(st_d["platform"], st_d["channel"], st_d["url"]) if st_d else ""
        template = str(render_cfg.get("credit_template", "") or "")
        credit = template.replace("{platform_url}", purl or streamer_name).replace("{name}", streamer_name) if template else ""

        # Clips the AI editor turns down are not rendered (rendering is the slow part).
        # They get a thumbnail and land in "Skipped"; restoring one renders it then.
        if fresh_ai and not layout_override and ai_cfg.get("auto_reject", True) and (
            not verdict.get("keep", True) or float(verdict.get("virality", 50)) < float(ai_cfg.get("min_virality", 35))
        ):
            thumb = render.thumbnail(raw, clip_dir / "thumb.jpg", max(0.5, min(raw_dur - 0.5, peak_off)))
            with db.session() as s:
                clip = s.get(Clip, clip_id)
                if not s.scalars(select(Post).where(Post.clip_id == clip_id, Post.status.in_(("scheduled", "posting", "posted")))).first():
                    clip.words, clip.transcript, clip.ai = words, transcript, verdict
                    clip.virality = float(verdict.get("virality", 50))
                    clip.hook, clip.layout = hook, layout
                    clip.title = clip.title or verdict.get("title", "")
                    clip.caption = clip.caption or verdict.get("caption", "")
                    clip.hashtags = clip.hashtags or verdict.get("hashtags", [])
                    clip.thumb_path, clip.raw_path = str(thumb), str(raw)
                    clip.status = "rejected"
                    d = clip.to_dict()
                else:
                    d = None
            if d:
                bus.publish("clip", clip=d)
                bus.activity("clip", f"AI skipped a clip: {verdict.get('reason', '')[:140]}", level="muted", clip_id=clip_id)
                return

        timings["ai"] = time.time() - t_step
        trim_start = float(verdict.get("trim_start", 0) or 0)
        trim_end_cut = float(verdict.get("trim_end", 0) or 0)
        # never let trimming push a clip below the minimum length the owner chose
        min_len = min(float(det_cfg.get("min_len", 15)), raw_dur)
        if raw_dur - trim_start - trim_end_cut < min_len:
            trim_start = trim_end_cut = 0.0
        audio: Path | str | None = None
        t_step = time.time()
        if audio_mode == "mute":
            audio = "mute"
        elif audio_mode == "game_only" and media.has_audio(raw):
            if voice.available():
                self.stage(clip_id, "Removing streamer voice")
                game_wav = clip_dir / "game_audio.wav"
                if voice.remove_voice(raw, game_wav):
                    audio = game_wav
                else:
                    bus.activity("clip", f"Clip #{clip_id}: voice removal failed — kept original audio", level="warn", clip_id=clip_id)
            elif not getattr(self, "_warned_voice", False):
                self._warned_voice = True
                bus.activity("clip", "Game-only audio needs the voice-removal model: run  pip install -r requirements-ml.txt  then restart",
                             level="warn")
        timings["voice"] = time.time() - t_step
        tmp = clip_dir / "video.tmp.mp4"
        t_step = time.time()
        self.stage(clip_id, "Rendering video")
        out_dur = render.render(raw, tmp, layout=layout, facecam=facecam, words=words, hook=hook, credit=credit,
                                style=render_cfg, trim_start=trim_start, trim_end=raw_dur - trim_end_cut if trim_end_cut else None,
                                audio=audio)
        timings["video"] = time.time() - t_step
        final = clip_dir / "video.mp4"
        tmp.replace(final)
        if tmp.with_suffix(".ass").exists():
            tmp.with_suffix(".ass").replace(clip_dir / "captions.ass")
        thumb = render.thumbnail(final, clip_dir / "thumb.jpg", max(0.5, min(out_dur - 0.5, peak_off - trim_start)))

        with db.session() as s:
            clip = s.get(Clip, clip_id)
            clip.words = words
            clip.transcript = transcript
            clip.video_path = str(final)
            clip.thumb_path = str(thumb)
            clip.raw_path = str(raw)
            clip.duration = out_dur
            clip.layout = layout
            if fresh_ai:
                clip.ai = verdict
                clip.virality = float(verdict.get("virality", 50))
                clip.hook = hook
                clip.title = verdict.get("title", "") if (not clip.title or rerun_ai) else clip.title
                clip.caption = verdict.get("caption", "") if (not clip.caption or rerun_ai) else clip.caption
                clip.hashtags = verdict.get("hashtags", []) if (not clip.hashtags or rerun_ai) else clip.hashtags
            else:
                clip.hook = hook
            reject = ai_cfg.get("auto_reject", True) and fresh_ai and (
                not verdict.get("keep", True) or clip.virality < float(ai_cfg.get("min_virality", 35))
            )
            has_posts = s.scalars(select(Post).where(Post.clip_id == clip_id, Post.status.in_(("scheduled", "posting", "posted")))).first()
            if has_posts:
                clip.status = "scheduled" if has_posts.status != "posted" else "posted"
            else:
                clip.status = "rejected" if reject else "ready"
            d = clip.to_dict()
        bus.publish("clip", clip=d)
        took = " · ".join(f"{k} {v:.0f}s" for k, v in timings.items() if v >= 1)
        log.info("clip #%s rendered (%s)", clip_id, took)
        if d["status"] == "ready":
            bus.activity("clip", f"Clip ready: {d['title'] or d['hook']}  ({took})", clip_id=clip_id)
        elif d["status"] == "rejected":
            bus.activity("clip", f"AI skipped a clip: {verdict.get('reason', '')[:140]}", level="muted", clip_id=clip_id)

        sched = db.get_settings("schedule")
        if (d["status"] == "ready" and sched.get("autopilot") and st_d and st_d.get("permission")
                and d["virality"] >= float(sched.get("autopilot_min_virality", 70))):
            try:
                self.schedule_clip(clip_id, sched.get("platforms") or ["youtube"])
                bus.activity("autopilot", f"Autopilot scheduled clip #{clip_id} (virality {d['virality']:.0f})", clip_id=clip_id)
            except Exception as exc:
                bus.activity("autopilot", f"Autopilot could not schedule #{clip_id}: {exc}", level="warn", clip_id=clip_id)

    # ------------------------------------------------------------ scheduling

    def _tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(db.get_settings("general").get("timezone") or "UTC")
        except Exception:
            return ZoneInfo("UTC")

    def next_free_slot(self, platform: str, s) -> datetime:
        cfg = db.get_settings("schedule")
        tz = self._tz()
        slots = []
        for x in cfg.get("slots") or ["18:00"]:
            try:
                hh, mm = (int(v) for v in str(x).split(":"))
                slots.append((hh, mm))
            except ValueError:
                continue
        slots = sorted(set(slots)) or [(18, 0)]
        taken = {
            p.scheduled_at.replace(tzinfo=timezone.utc) if p.scheduled_at.tzinfo is None else p.scheduled_at
            for p in s.scalars(select(Post).where(Post.platform == platform, Post.status.in_(("scheduled", "posting", "posted"))))
        }
        taken_keys = {t.astimezone(timezone.utc).strftime("%Y%m%d%H%M") for t in taken}
        now = datetime.now(tz)
        for day in range(0, 60):
            d = (now + timedelta(days=day)).date()
            for hh, mm in slots:
                cand = datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz)
                if cand <= now + timedelta(minutes=2):
                    continue
                if cand.astimezone(timezone.utc).strftime("%Y%m%d%H%M") not in taken_keys:
                    return cand.astimezone(timezone.utc)
        return (now + timedelta(days=60)).astimezone(timezone.utc)

    def schedule_clip(self, clip_id: int, platforms: list[str], when: datetime | None = None) -> list[dict]:
        out = []
        with db.session() as s:
            clip = s.get(Clip, clip_id)
            if not clip or not clip.video_path:
                raise ValueError("clip has no rendered video yet")
            st = s.get(Streamer, clip.streamer_id) if clip.streamer_id else None
            if st and not st.permission:
                raise PermissionError(f"Mark that you have {st.name}'s permission (Streams page) before posting their clips")
            for p in platforms:
                if p not in ("youtube", "instagram"):
                    continue
                exists = s.scalars(select(Post).where(Post.clip_id == clip_id, Post.platform == p,
                                                      Post.status.in_(("scheduled", "posting", "posted")))).first()
                if exists:
                    continue
                at = when or self.next_free_slot(p, s)
                post = Post(clip_id=clip_id, platform=p, scheduled_at=at, status="scheduled")
                s.add(post)
                s.flush()
                out.append(post.to_dict())
            if out or s.scalars(select(Post).where(Post.clip_id == clip_id, Post.status == "scheduled")).first():
                clip.status = "scheduled"
            d = clip.to_dict()
        bus.publish("clip", clip=d)
        for p in out:
            bus.publish("post", post=p)
        if out:
            bus.activity("schedule", f"Clip #{clip_id} scheduled on {', '.join(p['platform'] for p in out)}", clip_id=clip_id)
        return out

    async def _scheduler_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(15)
                now = utcnow()
                due: list[int] = []
                with db.session() as s:
                    for p in s.scalars(select(Post).where(Post.status == "scheduled", Post.scheduled_at <= now)):
                        p.status = "posting"
                        due.append(p.id)
                for pid in due:
                    self.publish_pool.submit(self._publish_job, pid)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("scheduler loop")

    def post_now(self, post_id: int) -> None:
        with db.session() as s:
            p = s.get(Post, post_id)
            if not p or p.status in ("posting", "posted"):
                return
            p.status = "posting"
            p.scheduled_at = utcnow()
        self.publish_pool.submit(self._publish_job, post_id)

    def _publish_job(self, post_id: int) -> None:
        with db.session() as s:
            p = s.get(Post, post_id)
            clip = s.get(Clip, p.clip_id)
            st = s.get(Streamer, clip.streamer_id) if clip.streamer_id else None
            post = p.to_dict()
            c = clip.to_dict()
            video = Path(clip.video_path)
            st_d = st.to_dict() if st else None
        bus.publish("post", post=post)
        tags = c["hashtags"] or []
        credit = ""
        if st_d:
            credit = f"🎥 {st_d['name']} — {capture.platform_url(st_d['platform'], st_d['channel'], st_d['url'])}"
        try:
            if not video.exists():
                raise publishers.PublishError("rendered video file is missing")
            if post["platform"] == "youtube":
                desc = "\n\n".join(x for x in [c["caption"], credit, " ".join(tags)] if x)
                res = publishers.youtube_upload(video, c["title"] or c["hook"], desc, tags)
            else:
                caption = "\n\n".join(x for x in [c["caption"] or c["title"], credit, " ".join(tags)] if x)
                public_url = None
                base = db.get_settings("general").get("public_base_url", "")
                if base:
                    public_url = f"{base.rstrip('/')}/public/media/{auth.sign_media(c['id'])}"
                res = publishers.instagram_upload(video, caption, public_url)
            with db.session() as s:
                p = s.get(Post, post_id)
                p.status = "posted"
                p.posted_at = utcnow()
                p.external_id = res["external_id"]
                p.url = res.get("url", "")
                p.error = ""
                post = p.to_dict()
                clip = s.get(Clip, p.clip_id)
                remaining = s.scalars(select(Post).where(Post.clip_id == clip.id, Post.status.in_(("scheduled", "posting")))).first()
                if not remaining:
                    clip.status = "posted"
                c = clip.to_dict()
            bus.publish("post", post=post)
            bus.publish("clip", clip=c)
            bus.activity("posted", f"Posted to {post['platform']}: {c['title'] or c['hook']}", post_id=post_id, url=post["url"])
        except Exception as exc:
            max_retries = int(db.get_settings("schedule").get("max_retries", 3))
            with db.session() as s:
                p = s.get(Post, post_id)
                p.attempts += 1
                p.error = str(exc)[:1000]
                if p.attempts < max_retries and not isinstance(exc, PermissionError):
                    p.status = "scheduled"
                    p.scheduled_at = utcnow() + timedelta(minutes=10 * p.attempts)
                else:
                    p.status = "failed"
                post = p.to_dict()
            bus.publish("post", post=post)
            bus.activity("posted", f"{post['platform']} upload failed (try {post['attempts']}): {str(exc)[:160]}", level="error", post_id=post_id)

    # ------------------------------------------------------------ auto-watch

    async def _autowatch_loop(self) -> None:
        await asyncio.sleep(5)
        while True:
            try:
                with db.session() as s:
                    targets = [st.to_dict() for st in s.scalars(select(Streamer).where(Streamer.auto_watch.is_(True)))]
                watching = {w.streamer["id"] for w in self.live.values() if w.streamer and w.is_alive()}
                for st in targets:
                    if st["id"] in watching:
                        continue
                    live, info = await asyncio.get_running_loop().run_in_executor(self.io_pool, capture.is_live, st["url"])
                    with db.session() as s:
                        row = s.get(Streamer, st["id"])
                        if row:
                            row.is_live = live
                            row.last_checked = utcnow()
                            bus.publish("streamer", streamer=row.to_dict())
                    if live:
                        bus.activity("live", f"{st['name']} just went live — {info[:80]}")
                        try:
                            self.start_live(st["id"])
                        except ValueError:
                            pass
                await asyncio.sleep(120)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("autowatch loop")
                await asyncio.sleep(60)

    def check_live(self, streamer_id: int) -> dict:
        with db.session() as s:
            row = s.get(Streamer, streamer_id)
            url = row.url
        live, info = capture.is_live(url)
        with db.session() as s:
            row = s.get(Streamer, streamer_id)
            row.is_live = live
            row.last_checked = utcnow()
            d = row.to_dict()
        bus.publish("streamer", streamer=d)
        return {"live": live, "info": info, "streamer": d}

    # ------------------------------------------------------------ stats

    async def _stats_loop(self) -> None:
        await asyncio.sleep(30)
        while True:
            try:
                await asyncio.get_running_loop().run_in_executor(self.io_pool, self.refresh_stats)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("stats loop")
            await asyncio.sleep(1800)

    def refresh_stats(self) -> dict:
        since = utcnow() - timedelta(days=45)
        with db.session() as s:
            posts = [(p.id, p.platform, p.external_id) for p in s.scalars(
                select(Post).where(Post.status == "posted", Post.posted_at >= since))]
        results: dict[int, dict] = {}
        errors: list[str] = []
        yt = [(pid, ext) for pid, plat, ext in posts if plat == "youtube" and ext]
        if yt:
            try:
                stats = publishers.youtube_stats([e for _, e in yt])
                for pid, ext in yt:
                    if ext in stats:
                        results[pid] = stats[ext]
            except Exception as exc:
                errors.append(f"YouTube: {exc}")
        for pid, plat, ext in posts:
            if plat == "instagram" and ext:
                try:
                    results[pid] = publishers.instagram_stats(ext)
                except Exception as exc:
                    errors.append(f"Instagram: {exc}")
                    break
        now = utcnow()
        with db.session() as s:
            for pid, st in results.items():
                p = s.get(Post, pid)
                p.views, p.likes, p.comments = st["views"], st["likes"], st["comments"]
                p.stats_updated_at = now
                hist = list(p.history or [])
                hist.append({"ts": now.isoformat(), "views": st["views"]})
                p.history = hist[-200:]
        if results:
            bus.publish("stats", updated=len(results))
        return {"updated": len(results), "errors": errors}


class LiveWorker(threading.Thread):
    def __init__(self, engine: Engine, run_id: int, streamer: dict | None, url: str, simulate: str | None):
        super().__init__(daemon=True, name=f"live-{run_id}")
        self.engine = engine
        self.run_id = run_id
        self.streamer = streamer
        self.url = url
        self.simulate = simulate
        self._stop = threading.Event()
        self.cap: capture.LiveCapture | None = None
        self.listener = None
        self.chat_q: deque = deque(maxlen=50000)
        self.moments = 0
        self.last_scores: dict = {}

    def request_stop(self) -> None:
        self._stop.set()

    def status_dict(self) -> dict:
        cap = self.cap
        return {
            "timeline": round(cap.timeline_end, 1) if cap else 0,
            "moments": self.moments,
            "chat_connected": bool(self.listener and self.listener.connected),
            "chat_messages": self.listener.count if self.listener else 0,
            "chat_error": self.listener.error if self.listener else "",
        }

    def _on_chat(self, wall: float, weight: float, _text: str) -> None:
        self.chat_q.append((wall, weight))

    def _on_scores(self, lo: int, hi: int, snap: dict) -> None:
        self.last_scores = snap
        bus.publish("scores", run_id=self.run_id, t0=lo, t1=hi, **snap, status=self.status_dict())

    def run(self) -> None:
        cfg = db.get_settings("detection")
        render_cfg = db.get_settings("render")
        yt_key = db.get_settings("youtube").get("api_key", "")
        streamer_id = self.streamer["id"] if self.streamer else None
        buf_dir = config.BUFFERS_DIR / f"run_{self.run_id}"
        cap = capture.LiveCapture(self.url, buf_dir, simulate=self.simulate)
        self.cap = cap

        def on_moment(m: signals.Moment) -> None:
            self.moments += 1
            self.engine.create_clip(self.run_id, streamer_id, m, raw_from=cap)

        an = signals.Analyzer(cfg, on_moment=on_moment, on_scores=self._on_scores)
        if self.streamer and not self.simulate:
            self.listener = chat.make_listener(
                self.streamer["platform"], self.streamer["channel"], self.streamer["url"], self._on_chat,
                cfg.get("hype_words", []), yt_key,
            )
            if self.listener and self.engine.loop:
                asyncio.run_coroutine_threadsafe(self.listener.run(), self.engine.loop)
        error = ""
        processed_any = False
        try:
            cap.start()
            self.engine.update_run(self.run_id, status="live")
            if self.streamer:
                with db.session() as s:
                    row = s.get(Streamer, self.streamer["id"])
                    if row:
                        row.is_live = True
                        bus.publish("streamer", streamer=row.to_dict())
            last_new = time.time()
            buffer_s = float(cfg.get("buffer_minutes", 15)) * 60
            chat_delay = float(cfg.get("chat_delay", 0))
            carry: list = []
            while not self._stop.is_set():
                segs = carry + cap.poll_segments()
                carry = []
                for seg in segs:
                    if not seg.path.exists():
                        continue
                    signals.audio_features(an.tl, seg.path, seg.t0)
                    signals.motion_features(an.tl, seg.path, seg.t0)
                    if cfg.get("use_ocr"):
                        signals.ocr_features(an.tl, seg.path, seg.t0, cfg.get("game_words", []))
                    if cfg.get("use_whisper_live") and speech.available():
                        try:
                            words = speech.transcribe(seg.path, render_cfg.get("whisper_model", "base"))
                            signals.speech_features(an.tl, words, seg.t0, cfg.get("speech_words", []))
                        except Exception as exc:
                            log.warning("speech signal skipped: %s", exc)
                if segs:
                    processed_any = True
                    last_new = time.time()
                    while self.chat_q:
                        wall, w = self.chat_q.popleft()
                        t = cap.wall_to_timeline(wall)
                        if t is not None and t - chat_delay >= 0:
                            an.chat_rate(t - chat_delay, w)
                    an.advance(cap.timeline_end)
                    protect = min((m.start for m in an.pending), default=None)
                    cap.prune(buffer_s, protect_from=protect)
                    if int(cap.timeline_end) % 20 < 5:
                        self.engine.update_run(self.run_id, stats={"duration": round(cap.timeline_end), "moments": self.moments,
                                                                  "chat_messages": self.listener.count if self.listener else 0})
                if not segs and not cap.alive():
                    # capture exited: pick up the final segment(s), then finish
                    time.sleep(1.5)
                    carry = cap.poll_segments()
                    if not carry:
                        break
                    continue
                if time.time() - last_new > 120:
                    error = "no new video for 2 minutes (stream ended or stalled)"
                    break
                self._stop.wait(1.0)
            # flush: clip anything still pending at the end of the stream
            if processed_any:
                an.advance(cap.timeline_end, final=True)
        except Exception as exc:
            log.exception("live worker crashed")
            error = str(exc)
        finally:
            cap.stop()
            if self.listener:
                self.listener.stop()
            if not processed_any and not error:
                error = "could not read the stream: " + (" | ".join(cap.log_tail[-3:]) or "offline or unsupported")
            status = "stopped" if self._stop.is_set() else ("ended" if processed_any else "error")
            self.engine.update_run(self.run_id, status=status, error=error if status == "error" else "", ended_at=utcnow(),
                                   stats={"duration": round(cap.timeline_end), "moments": self.moments,
                                          "chat_messages": self.listener.count if self.listener else 0})
            bus.activity("live", f"Stopped watching run #{self.run_id} ({status}) — {self.moments} moments",
                         level="error" if status == "error" else "info", run_id=self.run_id)
            cap.cleanup()
            self.engine.live.pop(self.run_id, None)
            if self.streamer:
                with db.session() as s:
                    row = s.get(Streamer, self.streamer["id"])
                    if row:
                        row.is_live = False
                        bus.publish("streamer", streamer=row.to_dict())


engine = Engine()
