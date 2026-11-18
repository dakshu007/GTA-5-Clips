"""Turn a raw 16:9 cut into a finished 1080×1920 Short / Reel.

Layouts
-------
* ``blur``  – gameplay zoomed into the middle, blurred copy fills the frame
* ``split`` – streamer facecam on top, gameplay below (needs a facecam box)
* ``crop``  – full-screen 9:16 crop that follows where the action is
* ``auto``  – same as crop: full-screen gameplay, facecam kept out of frame

Overlays: word-by-word karaoke captions, hook text for the first seconds,
streamer credit, progress bar. Audio is loudness-normalised to -14 LUFS.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
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
    extra: list[str] | None = None,
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
        f"Style: Sticker,{font},150,&H0000E6FF,&H0000E6FF,&H00000000,&H64000000,0,0,0,0,100,100,2,0,1,10,6,5,40,40,0,1",
        f"Style: Narr,{font},54,&H00FFFFFF,&H00FFFFFF,&H50000000,&H50000000,0,0,0,0,100,100,0,0,3,18,0,8,80,80,420,1",
        f"Style: Ending,{font},92,&H00FFFFFF,&H00FFFFFF,{pink},{pink},0,0,0,0,100,100,1,0,3,26,0,5,80,80,0,1",
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
    lines.extend(extra or [])
    return "\n".join(lines) + "\n"


def troll_ass_lines(events: list[dict], tmap, out_dur: float, ending_text: str) -> list[str]:
    """Meme stickers, narrator lines and the ending card as animated ASS events (output time)."""
    out: list[str] = []
    n_sticker = 0
    for ev in events:
        t0 = tmap(ev["t"])
        t1 = min(out_dur, tmap(ev["t"] + ev["dur"]))
        if t1 <= t0:
            continue
        text = _ass_text(ev.get("text", "")).upper()
        if ev["type"] == "sticker" and text:
            ypos = (700, 560, 820, 640)[n_sticker % 4]
            rot = (-7, 6, -4, 8)[n_sticker % 4]
            n_sticker += 1
            out.append(
                f"Dialogue: 5,{_ass_time(t0)},{_ass_time(t1)},Sticker,,0,0,0,,"
                f"{{\\an5\\pos({W // 2},{ypos})\\frz{rot}\\fscx20\\fscy20"
                f"\\t(0,110,\\fscx118\\fscy118)\\t(110,200,\\fscx100\\fscy100)\\fad(0,160)}}{text}"
            )
        elif ev["type"] == "narration" and text:
            out.append(f"Dialogue: 4,{_ass_time(t0)},{_ass_time(t1)},Narr,,0,0,0,,{{\\fad(120,120)}}{text}")
    end_text = _ass_text(ending_text).upper()
    if end_text and out_dur > 4:
        out.append(
            f"Dialogue: 6,{_ass_time(out_dur - 2.6)},{_ass_time(out_dur)},Ending,,0,0,0,,"
            f"{{\\an5\\pos({W // 2},{H // 2})\\fscx40\\fscy40\\t(0,180,\\fscx106\\fscy106)"
            f"\\t(180,300,\\fscx100\\fscy100)}}{end_text}"
        )
    return out


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


def _fonts_dir() -> Path:
    """Fonts copied into the data folder, so from clips/<id>/ they are simply ../../fonts."""
    dest = config.DATA_DIR / "fonts"
    dest.mkdir(parents=True, exist_ok=True)
    for f in config.FONTS_DIR.glob("*.otf"):
        target = dest / f.name
        if not target.exists():
            shutil.copy2(f, target)
    return dest


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


def crop_x(src_w: int, crop_w: int) -> int:
    """Left edge of the full-height 9:16 window: always the exact centre of the frame, so
    the game's own HUD and subtitles stay centred. A facecam inside it is blurred out
    (see hide_cam_filter) rather than moving the window."""
    return max(0, (src_w - crop_w) // 2) // 2 * 2


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
        x = crop_x(src_w, crop_w)
        return f"[0:v]crop={crop_w}:{src_h}:{x}:0,scale={W}:{H},setsar=1[v0]"
    # blur (default)
    fg_h = 780
    return (
        f"[0:v]split=2[a][b];"
        f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,scale={W}:{H},eq=brightness=-0.10:saturation=1.25[bg];"
        f"[b]scale=-2:{fg_h},crop='min(iw,{W})':{fg_h}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2-60,setsar=1[v0]"
    )


def _src_fps(path: Path) -> float:
    for st in media.probe(path).get("streams", []):
        if st.get("codec_type") == "video":
            num, _, den = str(st.get("avg_frame_rate") or st.get("r_frame_rate") or "30/1").partition("/")
            try:
                return float(num) / float(den or 1)
            except (ValueError, ZeroDivisionError):
                return 30.0
    return 30.0


def _expr_sum(terms: list[str]) -> str:
    return "+".join(terms) if terms else "0"


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
    audio: Path | str | None = None,
    fx: dict | None = None,
) -> float:
    """Render the final vertical video. Returns its duration.

    ``audio``: None = the clip's own audio, a path = use that audio file instead
    (e.g. game audio with the streamer's voice removed), "mute" = silence.
    ``fx``: troll edit (see troll.py) — slow-mo, zoom/shake/flash/bw, stickers, narration,
    sound effects and music. Times in ``fx`` are seconds from the (trimmed) clip start.
    """
    from .troll import TimeMap  # local import: troll imports render-free modules only

    src_dur = media.duration(raw)
    trim_start = max(0.0, min(trim_start, src_dur - 5))
    end = src_dur if trim_end is None else max(trim_start + 5, min(trim_end, src_dur))
    dur = end - trim_start

    if layout == "auto":
        layout = "crop"
    if layout == "split" and not facecam:
        layout = "crop"
    src_w, src_h = media.video_size(raw)
    cx = 0.5  # always centred: the game's HUD/subtitles are laid out around the middle

    # ---- quality: 60 fps when the source has it, optional 1440p (YouTube serves it in better quality)
    src_fps = _src_fps(raw)
    want_fps = str(style.get("fps", "auto"))
    fps = 60 if (want_fps == "60" or (want_fps == "auto" and src_fps >= 50)) else 30
    out_w, out_h = (1440, 2560) if str(style.get("resolution", "1080p")) == "1440p" else (W, H)

    fx = fx or {}
    tmap = TimeMap(fx.get("slowmo") or {})
    out_dur = dur + tmap.extra

    shifted = [
        {"w": w["w"], "s": round(tmap(w["s"] - trim_start), 2), "e": round(tmap(w["e"] - trim_start), 2)}
        for w in words
        if w["e"] > trim_start and w["s"] < end
    ]
    events = fx.get("events") or []
    extra = troll_ass_lines(events, tmap, out_dur, fx.get("ending_text", "")) if fx else []
    ass_path = out.with_suffix(".ass")
    ass_path.write_text(build_ass(shifted, out_dur, hook, credit, style, extra=extra), encoding="utf-8")

    parts: list[str] = []
    src = "[0:v]"
    if tmap.on:
        a, b = tmap.a, tmap.b
        smooth = bool(style.get("smooth_slowmo", True)) and media.has_filter("minterpolate")
        slow = f"setpts=(PTS-STARTPTS)/{tmap.f}," + (f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1" if smooth else f"fps={fps}")
        parts.append(
            f"[0:v]fps={fps},split=3[s0][s1][s2];"
            f"[s0]trim=0:{a:.3f},setpts=PTS-STARTPTS[p0];"
            f"[s1]trim={a:.3f}:{b:.3f},{slow}[p1];"
            f"[s2]trim={b:.3f},setpts=PTS-STARTPTS[p2];"
            f"[p0][p1][p2]concat=n=3:v=1:a=0[vs]"
        )
        src = "[vs]"
    parts.append(video_filter(layout, src_w, src_h, facecam, cx).replace("[0:v]", src))
    cur = "v0"

    # ---- troll camera moves: zoom punch-ins + shake (zoompan keeps a fixed output size)
    zooms, sx, sy, flashes, bws = [], [], [], [], []
    for ev in events:
        t0, t1 = tmap(ev["t"]), tmap(ev["t"] + ev["dur"])
        if ev["type"] == "zoom":
            r = min(0.15, (t1 - t0) / 3)
            zooms.append(f"0.22*between(it,{t0:.3f},{t1:.3f})*min(1,(it-{t0:.3f})/{r:.3f})*min(1,({t1:.3f}-it)/{r:.3f})")
        elif ev["type"] == "shake":
            zooms.append(f"0.07*between(it,{t0:.3f},{t1:.3f})")
            sx.append(f"between(it,{t0:.3f},{t1:.3f})*22*sin(it*71)")
            sy.append(f"between(it,{t0:.3f},{t1:.3f})*16*cos(it*57)")
        elif ev["type"] == "flash":
            flashes.append(f"between(t,{t0:.3f},{t1:.3f})")
        elif ev["type"] == "bw":
            bws.append(f"between(t,{t0:.3f},{t1:.3f})")
    if zooms:
        z = f"1+{_expr_sum(zooms)}"
        parts.append(
            f"[{cur}]zoompan=z='{z}':x='iw/2-(iw/zoom/2)+({_expr_sum(sx)})':y='ih/2-(ih/zoom/2)+({_expr_sum(sy)})'"
            f":d=1:s={W}x{H}:fps={fps}[vz]"
        )
        cur = "vz"
    if bws:
        parts.append(f"[{cur}]hue=s='1-min(1,{_expr_sum(bws)})'[vb]")
        cur = "vb"
    if flashes:
        parts.append(f"color=c=white:s={W}x{H}:r={fps},format=rgba,colorchannelmixer=aa=0.75[white];"
                     f"[{cur}][white]overlay=enable='{_expr_sum(flashes)}':shortest=1[vf]")
        cur = "vf"

    # ---- enhance + final size (text is drawn after scaling, so it stays razor sharp)
    enh = []
    if (out_w, out_h) != (W, H):
        enh.append(f"scale={out_w}:{out_h}:flags=lanczos")
    if style.get("enhance", True):
        enh.append("hqdn3d=1.2:1.2:3:3")
        enh.append("cas=0.45" if media.has_filter("cas") else "unsharp=5:5:0.5")
        enh.append("eq=saturation=1.10:contrast=1.03")
    if enh:
        parts.append(f"[{cur}]{','.join(enh)}[ve]")
        cur = "ve"

    workdir = out.parent
    if media.has_filter("subtitles"):
        # ffmpeg runs inside the clip folder with *relative* paths, so folder names with
        # quotes, colons or spaces can never break the filter syntax
        fonts = _fonts_dir()
        try:
            rel_fonts = os.path.relpath(fonts, workdir)
        except ValueError:  # different drive (Windows)
            rel_fonts = str(fonts)
        parts.append(f"[{cur}]subtitles=filename='{_esc(ass_path.name)}':fontsdir='{_esc(rel_fonts)}'[v1]")
        cur = "v1"
    else:
        # ffmpeg built without libass: still make the clip, just without burned-in text
        log.warning("ffmpeg has no 'subtitles' filter (libass) — rendering without captions/hook text")
    if style.get("progress_bar", True):
        color = "0x" + str(style.get("progress_color", "#FF2E88")).lstrip("#")
        bar_h = 14 * out_h // H
        parts.append(f"color=c={color}:s={out_w}x{bar_h}:r={fps}:d={out_dur:.3f}[bar];"
                     f"[{cur}][bar]overlay=x='-w+w*t/{out_dur:.3f}':y=H-{bar_h}:eval=frame:shortest=1[v2]")
        cur = "v2"

    # ---- audio: game audio (+ slow-mo), sound effects, narrator, music, all ducked and mixed
    span = ["-ss", f"{trim_start:.3f}", "-t", f"{dur:.3f}"]
    inputs: list[str] = []
    n_in = 1
    if audio == "mute" or (audio is None and not media.has_audio(raw)):
        inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        base = f"[{n_in}:a]"
        n_in += 1
    elif audio is not None:
        inputs += [*span, "-i", str(audio)]
        base = f"[{n_in}:a]"
        n_in += 1
    else:
        base = "[0:a]"
    fmt = "aformat=sample_rates=48000:channel_layouts=stereo"
    parts.append(f"{base}{fmt},asetpts=PTS-STARTPTS[g0]")
    game = "g0"
    if tmap.on:
        a, b = tmap.a, tmap.b
        parts.append(
            f"[{game}]asplit=3[x0][x1][x2];[x0]atrim=0:{a:.3f},asetpts=PTS-STARTPTS[q0];"
            f"[x1]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,atempo={tmap.f}[q1];"
            f"[x2]atrim={b:.3f},asetpts=PTS-STARTPTS[q2];[q0][q1][q2]concat=n=3:v=0:a=1[gs]"
        )
        game = "gs"
    mix: list[str] = []
    narr_labels: list[str] = []
    for i, (path, t, _text) in enumerate(fx.get("narration") or []):
        inputs += ["-i", str(path)]
        ms = int(tmap(t) * 1000)
        parts.append(f"[{n_in}:a]{fmt},adelay={ms}|{ms},volume=1.5[n{i}]")
        narr_labels.append(f"[n{i}]")
        n_in += 1
    music = fx.get("music")
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        vol = float(style.get("music_volume", 0.16))
        parts.append(f"[{n_in}:a]{fmt},atrim=0:{out_dur:.3f},volume={vol:.3f},"
                     f"afade=t=in:d=0.6,afade=t=out:st={max(0.0, out_dur - 1.5):.3f}:d=1.5[mus]")
        n_in += 1
    if narr_labels:
        # duck game audio + music while the narrator talks
        k = len(narr_labels)
        parts.append(f"{''.join(narr_labels)}amix=inputs={k}:normalize=0:duration=longest,apad=whole_dur={out_dur:.3f},"
                     f"asplit={3 if music else 2}[narr]{'[sc1][sc2]' if music else '[sc1]'}")
        parts.append(f"[{game}][sc1]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350[gd]")
        game = "gd"
        if music:
            parts.append("[mus][sc2]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=400[musd]")
            mix.append("[musd]")
        mix.append("[narr]")
    elif music:
        mix.append("[mus]")
    for i, (path, t, gain) in enumerate(fx.get("sfx") or []):
        inputs += ["-i", str(path)]
        ms = int(tmap(t) * 1000)
        parts.append(f"[{n_in}:a]{fmt},adelay={ms}|{ms},volume={gain:.2f}[e{i}]")
        mix.append(f"[e{i}]")
        n_in += 1
    loud = "loudnorm=I=-14:TP=-1.5:LRA=11"
    if mix:
        parts.append(f"[{game}]{''.join(mix)}amix=inputs={1 + len(mix)}:normalize=0:duration=first,"
                     f"atrim=0:{out_dur:.3f},alimiter=limit=0.95,{loud}[aout]")
    else:
        parts.append(f"[{game}]{loud}[aout]")
    graph = ";".join(parts)

    tail = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-t", f"{out_dur:.3f}", str(out)]
    bitrate = {(1440, 2560): "24M"}.get((out_w, out_h), "16M" if fps == 60 else "12M")

    def build(enc: list[str], dec: list[str]) -> list[str]:
        return [media.FFMPEG, "-v", "error", "-nostdin", "-y", *dec, *span, "-i", str(raw), *inputs,
                "-filter_complex", graph, "-map", f"[{cur}]", "-map", "[aout]", "-r", str(fps), *enc, *tail]

    media.run_encode(build, timeout=3600, cwd=workdir, bitrate=bitrate, crf=int(style.get("crf", 18)),
                     preset=str(style.get("preset", "veryfast")), hw=bool(style.get("hw_encode", True)))
    return media.duration(out)


def thumbnail(video: Path, out: Path, at: float) -> Path:
    return media.snapshot(video, at, out, width=540)


def timeline_frames(raw: Path, out_dir: Path, duration: float, n: int = 8) -> list[tuple[float, Path]]:
    """``n`` frames spread evenly over the clip, with their times — what the troll director looks at."""
    out = []
    for i in range(n):
        t = 0.4 + (max(0.8, duration - 0.8)) * i / max(1, n - 1)
        p = out_dir / f"tl_{i}.jpg"
        try:
            media.snapshot(raw, min(t, duration - 0.2), p, width=512)
            out.append((round(t, 1), p))
        except media.MediaError:
            pass
    return out


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
