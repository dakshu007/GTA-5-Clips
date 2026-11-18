"""Turn a raw 16:9 cut into a finished 1080×1920 Short / Reel.

Layouts
-------
* ``blur``  – gameplay zoomed into the middle, blurred copy fills the frame
* ``split`` – streamer facecam on top, gameplay below (needs a facecam box)
* ``crop``  – full-screen 9:16 crop that follows where the action is
* ``auto``  – split if the streamer has a facecam box, otherwise blur

Overlays: word-by-word karaoke captions, hook text for the first seconds,
streamer credit, progress bar. Audio is loudness-normalised to -14 LUFS.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np

from . import config, media

log = logging.getLogger(__name__)

W, H = 1080, 1920

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF\U00002B00-\U00002BFF️‍]+"
)


def strip_emoji(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _EMOJI_RE.sub("", text)).strip()


def ass_color(hex_color: str, alpha: int = 0) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_text(text: str) -> str:
    return strip_emoji(text).replace("\\", "").replace("{", "(").replace("}", ")")


def chunk_words(words: list[dict], max_words: int = 3, max_gap: float = 0.6) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur and (len(cur) >= max_words or w["s"] - cur[-1]["e"] > max_gap or re.search(r"[.!?,]$", cur[-1]["w"])):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(
    words: list[dict],
    duration: float,
    hook: str,
    credit: str,
    style: dict,
) -> str:
    font = "Inter Black"
    size = int(style.get("caption_size", 84))
    base = ass_color(style.get("caption_color", "#FFFFFF"))
    hi = ass_color(style.get("highlight_color", "#FFE600"))
    pink = ass_color(style.get("progress_color", "#FF2E88"), alpha=0x10)
    y = int(H * float(style.get("caption_position", 0.70)))
    hook_secs = float(style.get("hook_seconds", 3.0))

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{font},{size},{base},{base},&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,7,3,5,60,60,0,1",
        f"Style: Hook,{font},70,&H00FFFFFF,&H00FFFFFF,{pink},{pink},0,0,0,0,100,100,0,0,3,22,0,8,90,90,230,1",
        f"Style: Credit,{font},38,&H30FFFFFF,&H30FFFFFF,&H90000000,&H00000000,0,0,0,0,100,100,1,0,1,3,0,2,40,40,80,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    hook = _ass_text(hook).upper()
    if hook:
        lines.append(
            f"Dialogue: 2,{_ass_time(0)},{_ass_time(min(hook_secs, duration))},Hook,,0,0,0,,"
            f"{{\\fad(120,250)\\t(0,180,\\fscx106\\fscy106)\\t(180,320,\\fscx100\\fscy100)}}{hook}"
        )
    credit = _ass_text(credit)
    if credit:
        lines.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(duration)},Credit,,0,0,0,,{credit}")

    if style.get("captions", True):
        for chunk in chunk_words(words):
            for i, w in enumerate(chunk):
                start = w["s"]
                end = chunk[i + 1]["s"] if i + 1 < len(chunk) else max(w["e"], start + 0.25)
                if end <= 0 or start >= duration:
                    continue
                parts = []
                for j, x in enumerate(chunk):
                    t = _ass_text(x["w"]).upper()
                    if not t:
                        continue
                    if j == i:
                        parts.append(f"{{\\c{hi}\\fscx108\\fscy108}}{t}{{\\c{base}\\fscx100\\fscy100}}")
                    else:
                        parts.append(t)
                if not parts:
                    continue
                pop = "\\t(0,90,\\fscx104\\fscy104)\\t(90,160,\\fscx100\\fscy100)" if i == 0 else ""
                lines.append(
                    f"Dialogue: 3,{_ass_time(start)},{_ass_time(min(end, duration))},Caption,,0,0,0,,"
                    f"{{\\an5\\pos({W // 2},{y}){pop}}}" + " ".join(parts)
                )
    return "\n".join(lines) + "\n"


def action_center(path: str | Path) -> float:
    """Horizontal centre (0..1) of on-screen motion — where a 9:16 crop should sit."""
    frames = media.gray_frames(path, fps=2, size=(96, 54))
    if len(frames) < 3:
        return 0.5
    diff = np.abs(frames[1:].astype(np.float32) - frames[:-1].astype(np.float32)).mean(axis=(0, 1))
    if diff.sum() <= 0:
        return 0.5
    xs = np.linspace(0, 1, diff.size)
    c = float((diff * xs).sum() / diff.sum())
    return float(min(0.75, max(0.25, 0.5 + (c - 0.5) * 1.4)))


def _esc(path: Path | str) -> str:
    p = str(path).replace("\\", "/")
    return p.replace(":", r"\:").replace("'", r"\'").replace(",", r"\,")


def hide_cam_filter(src_w: int, src_h: int, facecam: dict) -> str:
    """Filter chain [0:v] -> [src] that blurs the streamer's facecam out of the gameplay."""
    pad = 0.01  # a little margin so the cam's border doesn't peek out
    fx = max(0.0, float(facecam.get("x", 0)) - pad)
    fy = max(0.0, float(facecam.get("y", 0)) - pad)
    fw = min(1.0 - fx, float(facecam.get("w", 0.25)) + 2 * pad)
    fh = min(1.0 - fy, float(facecam.get("h", 0.25)) + 2 * pad)
    x, y = int(fx * src_w) // 2 * 2, int(fy * src_h) // 2 * 2
    w, h = max(16, int(fw * src_w) // 2 * 2), max(16, int(fh * src_h) // 2 * 2)
    w, h = min(w, src_w - x), min(h, src_h - y)
    # shrink to a few pixels and blow back up = heavy, smooth blur
    return (
        f"[0:v]split=2[base][camsrc];"
        f"[camsrc]crop={w}:{h}:{x}:{y},scale=12:12,scale={w}:{h}:flags=bilinear[camblur];"
        f"[base][camblur]overlay={x}:{y}[src];"
    )


def video_filter(layout: str, src_w: int, src_h: int, facecam: dict | None, cx: float) -> str:
    """Build the filtergraph that produces [v0] at 1080x1920.

    In blur/crop layouts a configured facecam box is blurred out, so only gameplay shows.
    """
    if layout in ("blur", "crop") and facecam:
        return hide_cam_filter(src_w, src_h, facecam) + _layout_filter(layout, src_w, src_h, facecam, cx).replace("[0:v]", "[src]", 1)
    return _layout_filter(layout, src_w, src_h, facecam, cx)


def _layout_filter(layout: str, src_w: int, src_h: int, facecam: dict | None, cx: float) -> str:
    if layout == "split" and facecam:
        fx, fy = float(facecam.get("x", 0)), float(facecam.get("y", 0))
        fw, fh = max(0.05, float(facecam.get("w", 0.25))), max(0.05, float(facecam.get("h", 0.25)))
        cam_h, game_h = 700, H - 700
        game_w_scaled = int(round(src_w * game_h / src_h / 2) * 2)
        gx = int(min(max(0, game_w_scaled * cx - W / 2), max(0, game_w_scaled - W)))
        return (
            f"[0:v]split=2[g][f];"
            f"[f]crop=iw*{fw:.4f}:ih*{fh:.4f}:iw*{fx:.4f}:ih*{fy:.4f},"
            f"scale={W}:{cam_h}:force_original_aspect_ratio=increase,crop={W}:{cam_h}[cam];"
            f"[g]scale=-2:{game_h},crop={W}:{game_h}:{gx}:0[game];"
            f"[cam][game]vstack=inputs=2,setsar=1[v0]"
        )
    if layout == "crop":
        crop_w = int(src_h * 9 / 16 / 2) * 2
        crop_w = min(crop_w, src_w)
        x = int(min(max(0, src_w * cx - crop_w / 2), src_w - crop_w))
        return f"[0:v]crop={crop_w}:{src_h}:{x}:0,scale={W}:{H},setsar=1[v0]"
    # blur (default)
    fg_h = 780
    return (
        f"[0:v]split=2[a][b];"
        f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,scale={W}:{H},eq=brightness=-0.10:saturation=1.25[bg];"
        f"[b]scale=-2:{fg_h},crop='min(iw,{W})':{fg_h}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2-60,setsar=1[v0]"
    )


def render(
    raw: Path,
    out: Path,
    *,
    layout: str,
    facecam: dict | None,
    words: list[dict],
    hook: str,
    credit: str,
    style: dict,
    trim_start: float = 0.0,
    trim_end: float | None = None,
) -> float:
    """Render the final vertical video. Returns its duration."""
    src_dur = media.duration(raw)
    trim_start = max(0.0, min(trim_start, src_dur - 5))
    end = src_dur if trim_end is None else max(trim_start + 5, min(trim_end, src_dur))
    dur = end - trim_start

    if layout == "auto":
        layout = "split" if facecam else "blur"
    src_w, src_h = media.video_size(raw)
    cx = action_center(raw) if layout in ("crop", "split") else 0.5

    shifted = [
        {"w": w["w"], "s": round(w["s"] - trim_start, 2), "e": round(w["e"] - trim_start, 2)}
        for w in words
        if w["e"] > trim_start and w["s"] < end
    ]
    ass_path = out.with_suffix(".ass")
    ass_path.write_text(build_ass(shifted, dur, hook, credit, style), encoding="utf-8")

    graph = video_filter(layout, src_w, src_h, facecam, cx)
    if media.has_filter("subtitles"):
        graph += f";[v0]subtitles=filename='{_esc(ass_path)}':fontsdir='{_esc(config.FONTS_DIR)}'[v1]"
        last = "v1"
    else:
        # ffmpeg built without libass: still make the clip, just without burned-in text
        log.warning("ffmpeg has no 'subtitles' filter (libass) — rendering without captions/hook text")
        last = "v0"
    if style.get("progress_bar", True):
        color = "0x" + str(style.get("progress_color", "#FF2E88")).lstrip("#")
        graph += f";color=c={color}:s={W}x14:r=30:d={dur:.3f}[bar];[{last}][bar]overlay=x='-w+w*t/{dur:.3f}':y=H-14:eval=frame:shortest=1[v2]"
        last = "v2"

    has_a = media.has_audio(raw)
    args = [media.FFMPEG, "-v", "error", "-nostdin", "-y", "-ss", f"{trim_start:.3f}", "-t", f"{dur:.3f}", "-i", str(raw)]
    if not has_a:
        args += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    args += ["-filter_complex", graph, "-map", f"[{last}]", "-map", "0:a:0" if has_a else "1:a:0"]
    if has_a:
        args += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    tail = ["-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(out)]
    media.run_encode(lambda enc: args + ["-r", "30", *enc] + tail, timeout=1800,
                     bitrate="10M", crf=int(style.get("crf", 20)), preset=str(style.get("preset", "veryfast")),
                     hw=bool(style.get("hw_encode", True)))
    return media.duration(out)


def thumbnail(video: Path, out: Path, at: float) -> Path:
    return media.snapshot(video, at, out, width=540)


def ai_frames(raw: Path, out_dir: Path, peak_offset: float, count: int = 4) -> list[Path]:
    """A few frames around the peak for the AI editor to look at."""
    dur = media.duration(raw)
    times = sorted({max(0.2, min(dur - 0.2, t)) for t in (peak_offset - 4, peak_offset - 1, peak_offset + 1, peak_offset + 4)})[:count]
    paths = []
    for i, t in enumerate(times):
        p = out_dir / f"ai_{i}.jpg"
        try:
            media.snapshot(raw, t, p, width=512)
            paths.append(p)
        except media.MediaError:
            pass
    return paths
