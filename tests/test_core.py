"""Fast tests for detection, parsing, auth and caption logic (no network, no GPU)."""
from __future__ import annotations

import numpy as np
import pytest

from gtaclips import auth, capture, chat, render, signals


# ---------------------------------------------------------------- URL parsing

@pytest.mark.parametrize(
    "text,platform,channel",
    [
        ("https://www.twitch.tv/xQc", "twitch", "xQc"),
        ("twitch.tv/summit1g/", "twitch", "summit1g"),
        ("kaicenat", "twitch", "kaicenat"),
        ("https://kick.com/adinross", "kick", "adinross"),
        ("https://www.youtube.com/@IShowSpeed", "youtube", "@IShowSpeed"),
        ("https://www.youtube.com/channel/UC123/live", "youtube", "UC123"),
    ],
)
def test_parse_source(text, platform, channel):
    p = capture.parse_source(text)
    assert p["platform"] == platform
    assert p["channel"] == channel


def test_parse_twitch_vod_has_no_channel():
    p = capture.parse_source("https://www.twitch.tv/videos/123456")
    assert p["platform"] == "twitch" and p["channel"] == ""


def test_platform_url():
    assert capture.platform_url("twitch", "abc", "") == "twitch.tv/abc"
    assert capture.platform_url("other", "", "https://www.example.com/x/") == "example.com/x"


# ---------------------------------------------------------------- auth

def test_password_hash_roundtrip():
    h = auth.hash_password("correct horse")
    assert auth.verify_password("correct horse", h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("x", "garbage")


def test_lockout_after_failures():
    ip = "203.0.113.9"
    auth.clear_failures(ip)
    for _ in range(auth.MAX_FAILS):
        assert auth.locked_out(ip) == 0
        auth.record_failure(ip)
    assert auth.locked_out(ip) > 0
    auth.clear_failures(ip)
    assert auth.locked_out(ip) == 0


# ---------------------------------------------------------------- chat

def test_message_weight_hype_beats_plain():
    words = ["lmao", "kekw", "💀", "no way"]
    plain = chat.message_weight("what time is it", words)
    hype = chat.message_weight("NO WAY KEKW 💀💀", words)
    assert plain == 1.0
    assert hype > plain + 1


def test_twitch_irc_parsing():
    got = []
    tc = chat.TwitchChat("chan", lambda ts, w, text: got.append((w, text)), ["lmao"])
    tc._handle("@badge-info=;bits=500;color= :u!u@u.tmi.twitch.tv PRIVMSG #chan :lmao that was insane")
    tc._handle(":u!u@u.tmi.twitch.tv PRIVMSG #chan :hello")
    tc._handle("@msg-id=sub :tmi.twitch.tv USERNOTICE #chan :thanks for the sub")
    assert [t for _, t in got] == ["lmao that was insane", "hello", "thanks for the sub"]
    assert got[0][0] > got[1][0]  # hype word + bits weigh more
    assert got[2][0] >= 4  # subs are big events


# ---------------------------------------------------------------- detection

def _feed(an: signals.Analyzer, audio_db: np.ndarray, chat_rate: np.ndarray | None = None):
    for t, v in enumerate(audio_db):
        an.tl.put_max("audio", t, float(v))
        an.tl.put_max("motion", t, 1.0)
        if chat_rate is not None:
            an.chat_rate(t, float(chat_rate[t]))


CFG = {
    "threshold": 0.55, "weights": {"audio": 1.0, "chat": 1.3, "speech": 0.9, "motion": 0.5, "game": 1.2},
    "pre_roll": 10, "post_roll": 6, "min_len": 15, "max_len": 58, "cooldown": 25, "warmup": 20,
}


def test_analyzer_finds_audio_spikes():
    rng = np.random.default_rng(0)
    audio = -40 + rng.normal(0, 1.0, 200)
    audio[80:83] = -8  # scream
    audio[150:152] = -6  # explosion
    found = []
    an = signals.Analyzer(CFG, on_moment=found.append)
    _feed(an, audio)
    an.advance(200, final=True)
    peaks = [m.peak for m in found]
    assert len(found) == 2, peaks
    assert 79 <= peaks[0] <= 83 and 149 <= peaks[1] <= 152
    for m in found:
        assert CFG["min_len"] <= m.end - m.start <= CFG["max_len"]
        assert m.start <= m.peak <= m.end


def test_moderate_scream_triggers_without_chat():
    """No chat connection: a clear-but-not-extreme audio spike must still be clipped."""
    rng = np.random.default_rng(5)
    audio = -30 + rng.normal(0, 2.0, 200)  # busy game audio, ~2 dB wobble
    audio[120:122] = -30 + 9  # streamer yells ~4.5 sigma above normal
    found = []
    an = signals.Analyzer(CFG, on_moment=found.append)
    _feed(an, audio)
    an.advance(200, final=True)
    assert len(found) == 1 and 118 <= found[0].peak <= 123


def test_analyzer_quiet_stream_has_no_moments():
    rng = np.random.default_rng(1)
    found = []
    an = signals.Analyzer(CFG, on_moment=found.append)
    _feed(an, -40 + rng.normal(0, 1.0, 300))
    an.advance(300, final=True)
    assert found == []


def test_chat_spike_alone_triggers():
    rng = np.random.default_rng(2)
    audio = -40 + rng.normal(0, 0.5, 200)
    rate = rng.poisson(2, 200).astype(float)
    rate[124:132] = 40  # chat explodes a few seconds after the moment at ~120
    found = []
    an = signals.Analyzer(CFG, on_moment=found.append)
    _feed(an, audio, rate)
    an.advance(200, final=True)
    assert len(found) == 1
    assert found[0].signals["top"] == "chat"
    assert 115 <= found[0].peak <= 130


def test_incremental_matches_batch():
    """Feeding a live stream 4 s at a time must find the same moments as one pass."""
    rng = np.random.default_rng(3)
    audio = -40 + rng.normal(0, 1.0, 240)
    audio[100:103] = -5
    batch, live = [], []
    a1 = signals.Analyzer(CFG, on_moment=batch.append)
    _feed(a1, audio)
    a1.advance(240, final=True)
    a2 = signals.Analyzer(CFG, on_moment=live.append)
    for start in range(0, 240, 4):
        for t in range(start, start + 4):
            a2.tl.put_max("audio", t, float(audio[t]))
            a2.tl.put_max("motion", t, 1.0)
        a2.advance(start + 4)
    a2.advance(240, final=True)
    assert [m.peak for m in batch] == [m.peak for m in live]


def test_combine_soft_or():
    one = signals.combine({"audio": np.array([1.0]), "chat": np.array([0.0])}, {"audio": 1.0, "chat": 1.3})
    two = signals.combine({"audio": np.array([0.6]), "chat": np.array([0.6])}, {"audio": 1.0, "chat": 1.3})
    none = signals.combine({"audio": np.array([0.0])}, {"audio": 1.0})
    assert none[0] == 0
    assert one[0] > 0.55  # one strong signal can trigger
    assert two[0] > 0.55  # two medium signals agreeing also trigger


# ---------------------------------------------------------------- captions

def test_chunk_words_breaks_on_gaps_and_punctuation():
    words = [{"w": w, "s": s, "e": s + 0.3} for w, s in [("no", 0), ("way", 0.3), ("bro!", 0.6), ("he", 0.9), ("did", 2.5)]]
    chunks = render.chunk_words(words)
    assert [[w["w"] for w in c] for c in chunks] == [["no", "way", "bro!"], ["he"], ["did"]]


def test_build_ass_has_hook_credit_and_highlight():
    words = [{"w": "hello", "s": 0.1, "e": 0.4}, {"w": "chat", "s": 0.5, "e": 0.9}]
    ass = render.build_ass(words, 10, "He stole a cop car 💀", "🎥 twitch.tv/x", {"captions": True, "highlight_color": "#FFE600"})
    assert "HE STOLE A COP CAR" in ass and "💀" not in ass
    assert "twitch.tv/x" in ass
    assert ass.count("Style: Caption") == 1
    assert "\\c&H0000E6FF" in ass  # yellow highlight in ASS BGR order


def test_ass_color():
    assert render.ass_color("#FF2E88") == "&H00882EFF"


def test_video_filter_layouts():
    assert "vstack" in render.video_filter("split", 1920, 1080, {"x": 0.7, "y": 0.7, "w": 0.3, "h": 0.3}, 0.5)
    assert "boxblur" in render.video_filter("blur", 1920, 1080, None, 0.5)
    assert render.video_filter("crop", 1920, 1080, None, 0.5).startswith("[0:v]crop=606:1080")


# ---------------------------------------------------------------- Kick realtime config

def test_parse_kick_pusher_config():
    body = {"data": {"connections": [
        {"credentials": {"url": "wss://realtime.example"}, "provider": "centrifugo"},
        {"credentials": {"app_key": "abc", "cluster": "eu"}, "provider": "pusher"},
    ]}}
    cfg = chat.parse_pusher_config(body)
    assert cfg == {"app_key": "abc", "cluster": "eu"}
    assert chat.pusher_url(cfg) == "wss://ws-eu.pusher.com/app/abc?protocol=7&client=js&version=8.4.0&flash=false"
    with pytest.raises(ValueError):
        chat.parse_pusher_config({"data": {"connections": [{"provider": "centrifugo", "credentials": {}}]}})


def test_facecam_hidden_in_blur_and_crop_but_used_in_split():
    fc = {"x": 0.7, "y": 0.7, "w": 0.3, "h": 0.3}
    blur = render.video_filter("blur", 1920, 1080, fc, 0.5)
    crop = render.video_filter("crop", 1920, 1080, fc, 0.5)
    split = render.video_filter("split", 1920, 1080, fc, 0.5)
    assert "[camblur]" in blur and "[src]split=2[a][b]" in blur
    assert "[camblur]" in crop and "[src]crop=" in crop
    assert "[camblur]" not in split and "vstack" in split
    assert "[camblur]" not in render.video_filter("blur", 1920, 1080, None, 0.5)


def test_full_screen_crop_is_exactly_centred():
    for src_w, src_h in ((1920, 1080), (1280, 720), (2560, 1440)):
        crop_w = int(src_h * 9 / 16 / 2) * 2
        x = render.crop_x(src_w, crop_w)
        left, right = x, src_w - (x + crop_w)
        assert abs(left - right) <= 2, (src_w, left, right)
    f = render.video_filter("crop", 1920, 1080, {"x": 0.7, "y": 0.6, "w": 0.3, "h": 0.4}, 0.5)
    assert "crop=606:1080:656:0" in f and "[camblur]" in f  # centred + cam blurred, not dodged


def test_back_to_back_moments_never_overlap():
    cfg = dict(CFG, pre_roll=25, post_roll=15, min_len=40, max_len=55, cooldown=25, threshold=0.5)
    rng = np.random.default_rng(7)
    audio = -40 + rng.normal(0, 1.0, 400)
    for peak in (100, 140, 175, 260):  # hype keeps coming
        audio[peak:peak + 3] = -5
        audio[peak + 3:peak + 25] = -25  # and stays loud for a while
    found = []
    an = signals.Analyzer(cfg, on_moment=found.append)
    _feed(an, audio)
    an.advance(400, final=True)
    spans = sorted((m.start, m.end) for m in found)
    assert len(spans) >= 2
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert e1 <= s2, spans  # no shared footage
    for s, e in spans:
        assert e - s >= 39, spans


# ---------------------------------------------------------------- streamer voice learning (no model needed)

def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_voice_counts_once_per_clip_so_cutscenes_cant_outvote_the_streamer():
    from gtaclips import speaker

    streamer, npc = _unit([1, 0, 0]), _unit([0, 1, 0])
    cands: list = []
    # clip 1: a cutscene — the game character talks in 3 separate bits, the streamer once
    cands = speaker._remember(cands, [npc, npc, npc, streamer], [3.0, 3.0, 3.0, 1.0])
    # clip 2 and 3: normal gameplay, only the streamer talks
    cands = speaker._remember(cands, [streamer], [4.0])
    cands = speaker._remember(cands, [streamer], [4.0])
    learned = speaker.streamer_print(cands)
    assert learned is not None and float(learned @ streamer) > 0.99
    assert max(c["clips"] for c in cands if float(np.array(c["emb"]) @ npc) > 0.9) == 1


def test_speech_segments_finds_talking_and_splits_long_bits():
    from gtaclips import speaker

    rate = speaker.RATE
    silence = np.zeros(rate, dtype=np.float32)
    talk = (0.3 * np.sin(np.linspace(0, 2000, int(rate * 4.5)))).astype(np.float32)
    segs = speaker.speech_segments(np.concatenate([silence, talk, silence]))
    assert segs and all(e - s <= int(2.0 * rate * 1.41) for s, e in segs)
    covered = sum(e - s for s, e in segs) / rate
    assert 4.0 <= covered <= 4.8
    assert segs[0][0] >= int(0.9 * rate)
    assert speaker.speech_segments(silence) == []


# ---------------------------------------------------------------- troll edit

def test_troll_plan_is_clamped_and_capped():
    from gtaclips import troll

    raw = {
        "slowmo": {"enabled": True, "start": 10, "end": 30},  # too long -> 2.5 s max
        "events": [{"type": "sticker", "t": i, "dur": 1, "text": f"LOL {i}", "sound": ""} for i in range(9)]
        + [{"type": "narration", "t": 2, "dur": 99, "text": "x " * 40, "sound": ""},
           {"type": "teleport", "t": 1, "dur": 1, "text": "", "sound": ""},
           {"type": "zoom", "t": 50, "dur": 1, "text": "", "sound": ""}],
        "music_mood": "jazz-fusion",
    }
    p = troll.validate(raw, 20.0)
    assert p["slowmo"] == {"enabled": True, "start": 10.0, "end": 12.5}
    assert sum(e["type"] == "sticker" for e in p["events"]) == 4
    narr = [e for e in p["events"] if e["type"] == "narration"][0]
    assert len(narr["text"].split()) <= 14 and narr["dur"] <= 6
    assert all(e["type"] != "teleport" for e in p["events"])
    assert all(0 <= e["t"] <= 20 and e["t"] + e["dur"] <= 20.01 for e in p["events"])
    assert p["music_mood"] == "funny"


def test_slowmo_time_map():
    from gtaclips import troll

    tm = troll.TimeMap({"enabled": True, "start": 10, "end": 12}, factor=0.5)
    assert tm.extra == 2.0
    assert tm(5) == 5 and tm(11) == 12 and tm(12) == 14 and tm(20) == 22


def test_sound_requests_match_builtins():
    from gtaclips import trollkit

    assert trollkit.nearest_builtin("vine boom bass impact") == "boom"
    assert trollkit.nearest_builtin("sad violin fail") == "sad_trombone"
    assert trollkit.nearest_builtin("cartoon whoosh") == "whoosh"
    assert trollkit.nearest_builtin("something weird") == "boom"


def test_troll_ass_has_stickers_narration_and_ending():
    from gtaclips import troll

    events = [{"type": "sticker", "t": 1, "dur": 1, "text": "NAH", "sound": ""},
              {"type": "narration", "t": 2, "dur": 2, "text": "He had one job", "sound": ""}]
    lines = render.troll_ass_lines(events, troll.TimeMap({"enabled": False}), 30.0, "Follow for part 2")
    joined = "\n".join(lines)
    assert "Sticker" in joined and "NAH" in joined and "HE HAD ONE JOB" in joined and "FOLLOW FOR PART 2" in joined


def test_elevenlabs_requests(monkeypatch, tmp_path):
    import httpx

    from gtaclips import config, db, trollkit

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    db.init(f"sqlite:///{tmp_path}/t.sqlite")
    db.update_settings("elevenlabs", {"api_key": "sk-test", "voice_id": "VOICE1"})
    seen = []

    def fake_post(url, params=None, json=None, headers=None, timeout=None):
        seen.append((url, params, json, headers))
        return httpx.Response(200, content=b"ID3" + b"\0" * 1000)

    monkeypatch.setattr(trollkit.httpx, "post", fake_post)
    trollkit.el_sfx("vine boom", 1.0)
    trollkit.el_sfx("vine boom", 1.0)  # cached: no second request
    trollkit.el_tts("He had one job")
    trollkit.el_music("phonk", 40)
    urls = [u for u, *_ in seen]
    assert urls == ["https://api.elevenlabs.io/v1/sound-generation",
                    "https://api.elevenlabs.io/v1/text-to-speech/VOICE1",
                    "https://api.elevenlabs.io/v1/music"]
    assert all(h["xi-api-key"] == "sk-test" for *_, h in seen)
    assert seen[0][2]["text"] == "vine boom" and seen[0][2]["duration_seconds"] == 1.0
    assert seen[1][2]["text"] == "He had one job" and seen[1][1]["output_format"] == "mp3_44100_128"
    assert seen[2][2]["force_instrumental"] is True and seen[2][2]["music_length_ms"] == 40000


def test_troll_director_uses_claude_json(monkeypatch, tmp_path):
    import json as _json
    from types import SimpleNamespace

    from gtaclips import ai, troll

    plan = {"keep": True, "virality": 91, "reason": "r", "hook": "He did NOT see that", "title": "t", "caption": "c",
            "hashtags": ["#GTA6"], "slowmo": {"enabled": True, "start": 3, "end": 4.5},
            "events": [{"type": "zoom", "t": 3, "dur": 1, "text": "", "sound": ""}], "music_mood": "phonk",
            "ending_text": "Part 2?"}
    captured = {}

    class FakeMessages:
        def create(self, **kw):
            captured.update(kw)
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=_json.dumps(plan))])

    monkeypatch.setattr(ai, "_client", lambda key: SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()), messages=FakeMessages()))
    img = tmp_path / "f.jpg"
    img.write_bytes(b"\xff\xd8\xff")
    out = troll.plan_with_ai(frames=[(1.0, img)], transcript="", hype=[0.1, 0.9], duration=20, streamer="x",
                             ai_cfg={"enabled": True, "model": "claude-opus-5-5"}, game="GTA VI")
    assert out["source"] == "claude" and out["virality"] == 91
    assert captured["output_config"]["format"]["schema"]["properties"]["events"]
    assert any(b.get("type") == "image" for b in captured["messages"][0]["content"])
