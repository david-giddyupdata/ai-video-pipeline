"""The highlight reel's cut (R248, step 2): its sound, its timeline, its graphics, its captions, its Premiere project
and its two exports, from the edit list tools/reel.py reads (reel_plan.json) once the narration is voiced.

    python tools/reel_build.py audio <reel_plan.json>      # narration cleaned and leveled; the finished video's sound-ups
    python tools/reel_build.py layers <reel_plan.json>     # each beat's graphics as transparent ProRes 4444 (Remotion)
    python tools/reel_build.py xml <reel_plan.json>        # the timeline, the caption titles, <reel>/qs1a_reel.xml
    python tools/reel_build.py build <reel_plan.json>      # Premiere builds <reel>/qs1a_reel.prproj, with a marker a beat
    python tools/reel_build.py export <reel_plan.json>     # the two H.264s: standalone and talk (narration, captions off)
    python tools/reel_build.py all <reel_plan.json>        # audio, layers, xml, build, export in turn
    python tools/reel_build.py uploads <reel_plan.json>    # step 3's HeyGen uploads (nothing sent) and their credits
    python tools/reel_build.py nocap <reel_plan.json>      # a source "made_from" a copy of the final, tracks muted

The sequence (SEQUENCE) on tracks a reviewing editor can change (V4 of the rulebook):
  V1 Room                the stage's still room behind every beat that isn't the finished video full frame
  V2 Footage             the finished video and the take, full frame or scaled into a stage frame's window
  V3 Narrator            the avatar's still in the stage's left-third pose beside the cards (the HeyGen render's
                         place, R248 step 3: the render replaces this clip and nothing else moves)
  V4 Graphics            each beat's Remotion layer
  V5 Caption titles      one editable title per narration cue (R102) and one for the edit beat's sound-up line at the
                         house size; the standalone version's only (the talk version keeps the finished video's own)
  A1 Narration           the voiced lines (mono, cleaned, leveled to the house loudness), the standalone version's only
  A2, A3 Sound-ups       the finished video's own sound where it comes up, both channels (panned left and right: a
                         stereo file plays in stereo only so, GOTCHAS), in both versions
  (a plan's "note")      AI voice note (standalone only), muted in the talk version with A1 and V5
  (a plan's "fades")     Beat fades: black dipped in and out at every beat change (R248 round 3, this reel only)
  (a plan's "whoosh")    A4 Whooshes: the leveled whoosh under each beat's "enter" (its layer, or a full beat's
                         first frame, flying in), in both versions
The talk version is the same sequence exported with A1 and V5 (and the note) muted.

Sound (S1, R177): every narration line through Section A's loudness chain (a light compressor, one shared make-up gain,
a limiter) to the house's -14 LUFS; a mono WAV clip in our own XML plays at its file's loudness in Premiere's mix
(GOTCHAS), so its clips get no gain. The sound-ups (the final's own mix, which Premiere played near -11.3 LUFS) are
lowered by one shared gain to the narration's loudness, their balance (the logo music against its voice, R204) kept,
with short fades at every edge; a limiter keeps every true peak at -1 dBTP or under.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import reel                                                        # noqa: E402
from pipeline.config import tool                                   # noqa: E402

SEQUENCE = "qs1a reel"             # round 1's; a plan's "sequence" and "project" name its own (seq_name, proj_name)
PROJECT = "qs1a_reel"
TARGET_LUFS = -14.0                 # S1 / R177, as Premiere plays it (our mono WAV clips play at their files' level)
LIMIT_DBFS = -2.0                   # the house limiter's ceiling (sample peak; it measured -0.9 dBTP at -1.5)
EDGE_FADE_S = 0.02                  # every sound-up clip fades in and out this long: no click at a cut
END_FADE_S = 1.0                    # the reel's last sound-up (the logo's music, cut mid-phrase) fades out this long
CAPTION_PX, CAPTION_BOX = 48, "575757"    # C1's house look (Lucida Console 48 px, white on #575757, 7.23:1)
CAPTION_BOTTOM = 1024               # the bottom-centre caption's box bottom (Section A's cues: y 898 + 126)
CARD_CX, CARD_CHARS = 1272, 36      # beside a card, captions centre under it, narrower (C7: the card's side)
FRAME_CX, FRAME_CHARS = 960, 42     # elsewhere bottom centre, about two lines of 42 (C5)
TRACKS_V = ["Room", "Footage", "Narrator (still; the HeyGen render goes here)", "Graphics"]
NOTE_TRACK = "AI voice note (standalone only)"
FADES_TRACK = "Beat fades"          # R248 round 3 (a plan's "fades"): black, dipped in and out at every beat change
JOIN_TRACK = "Graphics (dissolving out)"   # a joined card's graphics, run on into the next beat (J1)
WHOOSH_TRACK = "Whooshes"           # the whoosh under each "enter" (both versions: it is the picture's own sound)
TRACKS_A = ["Narration", "Sound-ups left", "Sound-ups right"]
BINS = {"sequences": "Sequences",                     # (room_tone_*: Fable R7-5)
        "media": [{"bin": "Footage", "match": r"[\\/]media[\\/]"},
                  {"bin": "Narration", "match": r"[\\/]audio[\\/]narration[\\/]"},
                  {"bin": "Sound-ups", "match": r"[\\/]audio[\\/]soundup_"},
                  {"bin": "Whooshes", "match": r"[\\/]audio[\\/]whoosh_"},
                  {"bin": "Room tone", "match": r"[\\/]audio[\\/]room_tone_"},
                  {"bin": "Narrator", "match": r"[\\/]narrator[\\/]"},
                  {"bin": "Graphics", "match": r"[\\/]graphics[\\/]"},
                  {"bin": "Stills", "match": r"[\\/]public[\\/]"}]}


def opacity_keys(s_in, n, ramp=None, extend=0):
    """A still's Opacity keys (in s_in): fully up, or ramped up over ramp = (from, frames) as a fly-in does; then, for
    a joined card's still, held to its beat's end (n) and faded out over the extend frames it runs on into the next
    beat. Refuses keys that wouldn't rise in time (Fable r4 J9)."""
    keys = [(s_in, 100.0)] if ramp is None else [(s_in, 0.0), (s_in + ramp[0], 0.0), (s_in + ramp[0] + ramp[1], 100.0)]
    if extend:
        keys += [(s_in + n, 100.0), (s_in + n + extend, 0.0)]
    ts = [k for k, _ in keys]
    if ts != sorted(ts) or len(set(ts)) != len(ts):
        raise SystemExit(f"opacity keys out of order (the beat is too short for its fly-in): {keys}")
    return keys


SUFFIX_RE = re.compile(r"^(_[A-Za-z0-9]+)?$")     # an export's name suffix: empty or like _r6b (Fable B4)


def check_suffix(suffix):
    if not SUFFIX_RE.match(suffix or ""):
        raise SystemExit(f"--suffix {suffix!r}: empty, or an underscore and letters or digits (e.g. _r6b)")
    return suffix or ""


def plan_digest(plan):
    """The plan as written and the voiced lines it reads, hashed: a build, export or check refuses data made from
    another version (Fable F10)."""
    body = Path(plan.get("_path") or reel_dir(plan) / "reel_plan.json").read_bytes()
    lines_p = reel.lines_path(plan)
    return hashlib.sha256(body + (lines_p.read_bytes() if lines_p.exists() else b"")).hexdigest()[:12]


def seq_name(plan):
    return plan.get("sequence", SEQUENCE)


def proj_name(plan):
    return plan.get("project", PROJECT)


def fps_of(plan):
    return plan["fps"]


def reel_dir(plan):
    return plan["_dir"]


# ------------------------------------------------------------------------------------------------- the sound
def narration_audio(plan):
    """Every voiced line cleaned (pipeline.narration.clean: clicks, stray bursts, edge fades) and leveled
    (pipeline.edit.loudness, Section A's chain at TARGET_LUFS): {line id: wav path}, and the loudness info."""
    from pipeline.edit import loudness
    from pipeline.narration import clean
    have = reel.voiced(plan)
    d = reel_dir(plan)
    (d / "audio" / "narration").mkdir(parents=True, exist_ok=True)
    srcs = {}
    for beat in plan["beats"]:
        for k, _ in enumerate(beat.get("lines", [])):
            lid = reel.line_id(plan, beat, k)
            v = have.get(lid)
            if not v or v.get("text") != beat["lines"][k]["text"]:
                raise SystemExit(f"{lid} isn't voiced as written: run the voice build (tools/reel.py lines, then "
                                 "python -m pipeline.narration.build exercises/<ex>/<the plan's steps_file>)")
            dst = d / "audio" / "narration" / clean.wav_name(v["key"])
            if not dst.exists():
                clean.clean(ROOT / "audio_cache" / f"{v['key']}.mp3", dst)
            srcs[lid] = str(dst.relative_to(d)).replace("\\", "/")
    src_ex = plan["narration"].get("loudness_from", "qs1_section_a")      # the exercise whose loudness chain it takes
    settings = json.loads((ROOT / "exercises" / src_ex / "edit_settings.json").read_text(encoding="utf-8"))
    ld = {k: v for k, v in settings["loudness"].items() if k != "note"}
    ld["target_lufs"] = TARGET_LUFS
    mapping, info = loudness.prepare(d, list(srcs.values()), ld)
    return {lid: d / mapping[s] for lid, s in srcs.items()}, info


def media_of(plan):
    made = json.loads((reel_dir(plan) / "media" / "media.json").read_text(encoding="utf-8"))
    by_span = {reel.record_key(m): (name, m) for name, m in made.items()}

    def find(sh):
        a, b = reel.span_of(plan, sh, reel.probe(reel.source_path(plan, sh["src"])))
        key = reel.media_key(sh, a, b)
        if key not in by_span:
            raise SystemExit(f"no media for {key}: run tools/reel.py media first")
        name, m = by_span[key]
        return reel_dir(plan) / "media" / name, m
    return find


def soundups(plan):
    """The sound-up shots' sound, each a stereo WAV from its media at one shared gain that puts them at the
    narration's loudness, faded at both edges, limited: [(beat id, shot index, wav)], and the gain."""
    from pipeline.edit import loudness
    find, fps, d = media_of(plan), fps_of(plan), reel_dir(plan)
    (d / "audio").mkdir(exist_ok=True)
    spans = []
    for beat in plan["beats"]:
        for k, sh in enumerate(beat.get("shots", [])):
            if sh.get("sound") == "up":
                path, m = find(sh)
                a_in = sh.get("audio_in_s", sh["in_s"])     # a J-cut: the sound may start before the picture
                if not (m["in_s"] <= a_in <= sh["in_s"]):
                    raise SystemExit(f"{beat['id']} shot {k}: audio_in_s {a_in} outside its media or after its in")
                a = (round(a_in * fps) - m["first_frame"]) / fps
                n = round((sh["out_s"] - a_in) * fps)
                spans.append((beat["id"], k, path, a, n / fps))
    raw = []
    for bid, k, path, a, dur in spans:              # the spans as they are, to measure them together
        p = d / "audio" / f"_raw_{bid}_{k}.wav"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{a:.6f}", "-i", str(path), "-t", f"{dur:.6f}",
                        "-vn", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(p)], check=True)
        raw.append(p)
    lufs, _ = loudness.measure(raw)
    gain = round(TARGET_LUFS - lufs, 2)
    out = []
    last = plan["beats"][-1]["id"]
    for (bid, k, path, a, dur), p in zip(spans, raw):
        fo = END_FADE_S if bid == last else EDGE_FADE_S
        af = (f"volume={gain}dB,alimiter=limit={10 ** (LIMIT_DBFS / 20):.5f}:attack=5:release=50:level=false:latency=true,"
              f"afade=t=in:d={EDGE_FADE_S},afade=t=out:st={max(0.0, dur - fo):.4f}:d={fo}")
        h = hashlib.sha256(json.dumps([str(path), a, dur, af]).encode()).hexdigest()[:8]
        wav = d / "audio" / f"soundup_{bid}_{k}_{h}.wav"
        if not wav.exists():
            subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(p), "-af", af, "-c:a", "pcm_s16le",
                            "-ar", "48000", "-ac", "2", str(wav)], check=True)
        out.append((bid, k, wav))
        p.unlink()
    return out, {"sound_ups_lufs_before": lufs, "gain_db": gain}


ROOM_TRACK = "Room tone"            # R248 round 7: the narration's own room tone under the whole reel (a plan's room_tone)
from pipeline.edit.ppro.titles import PAD_PX as _TITLE_PAD   # noqa: E402
CAPTION_CHAR_PX = 29.0              # the caption's box: Lucida Console 48 px advances 29.0 px (measured, Fable R7-4)
CAPTION_PAD_PX = 2 * _TITLE_PAD     # and titles.PAD_PX a side
SAFE_RIGHT = 1824                   # title-safe's right edge (the cards' right edge too)


def sound_up_spans(plan, tl):
    """Every sound-up's span on the reel in frames, as its WAV plays (soundups: from audio_in_s to out_s; Fable R7-2:
    not the picture's length, which may run on to the next picture)."""
    fps, out = fps_of(plan), []
    for b in tl:
        for sh in b["shots"]:
            s_ = sh["shot"]
            if s_.get("sound") == "up":
                a_in = s_.get("audio_in_s", s_["in_s"])
                at = sh["at"] - round((s_["in_s"] - a_in) * fps)
                out.append((at, at + round((s_["out_s"] - a_in) * fps)))
    return out


def pauses(x, sr, min_s=0.3, trim_s=0.04, ceiling_db=-48.0):
    """A voiced line's pauses (mono float samples): runs of 10 ms windows within 8 dB of the line's own floor (its
    quietest tenth, digital silence aside), at least min_s long, trimmed trim_s each end (no word's tail or onset),
    under ceiling_db (no breath), and split around any transient (a sample over 5 times the run's RMS, or a 5 ms
    window 9 dB over the run's median 5 ms window: a tick, a lip noise; or a 10 ms window 4 dB over the run's median
    10 ms window: soft mouth texture, Fable R7-1). [(a, z)] in samples."""
    import numpy as np
    w = sr // 100
    k = len(x) // w
    if k < 10:
        return []
    env = 10 * np.log10(np.mean(np.square(x[:k * w].reshape(k, w)), axis=1) + 1e-20)
    live = env[env > -90]
    if not len(live):
        return []
    quiet = env < np.percentile(live, 10) + 8
    runs, i = [], 0
    while i < k:
        if quiet[i]:
            j = i
            while j < k and quiet[j]:
                j += 1
            runs.append((i * w, j * w))
            i = j
        else:
            i += 1
    t, out = round(trim_s * sr), []
    for a, z in runs:
        a, z = a + t, z - t
        while z - a >= min_s * sr:
            seg = x[a:z]
            rms = float(np.sqrt(np.mean(np.square(seg))))
            if 20 * np.log10(rms + 1e-12) > ceiling_db:
                break
            f = sr // 200
            n5 = len(seg) // f
            e5 = np.sqrt(np.mean(np.square(seg[:n5 * f].reshape(n5, f)), axis=1))
            g = sr // 100
            n10 = len(seg) // g
            e10 = np.sqrt(np.mean(np.square(seg[:n10 * g].reshape(n10, g)), axis=1))
            bad = np.nonzero((np.abs(seg) > 5 * rms))[0].tolist() + \
                [i * f + f // 2 for i in np.nonzero(e5 > np.median(e5) * 10 ** (9 / 20))[0]] + \
                [i * g + g // 2 for i in np.nonzero(e10 > np.median(e10) * 10 ** (4 / 20))[0]]
            if not bad:
                out.append((a, z))
                break
            cut = min(bad)                                      # keep what's before the first tick, go on after it
            if cut - round(0.02 * sr) - a >= min_s * sr:
                out.append((a, a + cut - round(0.02 * sr)))
            a = a + cut + round(0.03 * sr)
    return out


def room_tone(plan, narration, tl):
    """R248 round 7: the room-tone bed. The pauses of every voiced line (pauses: no word edges, breaths or ticks),
    each set to the plan's room_tone.rms_dbfs (about the narration's own floor, -54), joined end to end with
    equal-power crossfades into a pool; the bed draws the pool's pieces in a new shuffled order each pass (never the
    same piece across a pass's seam), so nothing repeats on a period. Its level follows the reel: in from 0 over
    fade_s, out under every sound-up (down before it starts, back after it ends, over duck_s), and out for good before
    the last one when that runs to the reel's end (the logo's music). A mono WAV at 48 kHz; measured: its level where
    it is up, the pool's length, the joins' steps against the noise's own, its envelope's strongest repeat."""
    import numpy as np
    import wave
    rt = plan.get("room_tone")
    if not rt:
        return None
    sr, fps = 48000, fps_of(plan)
    target, xf = rt.get("rms_dbfs", -54.0), round(rt.get("crossfade_s", 0.04) * sr)
    pieces, srcs = [], []
    for lid, p in sorted(narration.items()):
        raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        x = np.frombuffer(raw, np.float32).astype(np.float64)
        for a, z in pauses(x, sr, min_s=rt.get("min_piece_s", 0.3)):
            seg = x[a:z]
            g = target - 20 * np.log10(np.sqrt(np.mean(np.square(seg))) + 1e-12)
            if abs(g) <= 8:                                     # (a much quieter or louder floor isn't her room)
                pieces.append(seg * 10 ** (g / 20))
                srcs.append([lid, round(a / sr, 3), round(z / sr, 3), round(g, 1)])
    pool_s = sum(len(s) - xf for s in pieces) / sr
    if pool_s < rt.get("min_pool_s", 3.0):
        raise SystemExit(f"room tone: only {pool_s:.2f} s of clean pauses (under {rt.get('min_pool_s', 3.0)} s)")
    total = tl[-1]["f0"] + tl[-1]["n"]
    n = round(total / fps * sr)
    rng = np.random.default_rng(int(rt.get("seed", 7)))
    ramp = lambda m: (np.sin(np.linspace(0, np.pi / 2, m)), np.cos(np.linspace(0, np.pi / 2, m)))
    up, down = ramp(xf)
    seq, last, length = [], None, 0                             # the pieces' order, pass by pass
    while length < n + xf:
        order = list(rng.permutation(len(pieces)))
        if last is not None and order[0] == last and len(order) > 1:
            order[0], order[1] = order[1], order[0]
        for i in order:
            seq.append(i)
            length += len(pieces[i]) - xf
            last = i
    bed, at, joins = np.zeros(length + 2 * xf), 0, []          # overlap-added: each piece's ends crossfade
    for j, i in enumerate(seq):
        s = pieces[i].copy()
        if j:
            s[:xf] *= up
            joins.append(at + xf // 2)
        if j < len(seq) - 1:
            s[-xf:] *= down
        bed[at:at + len(s)] += s
        at += len(s) - xf
    bed = bed[:n]
    level = np.ones(n)                                          # the envelope: in, out under the sound-ups, out at the end
    fi, du = round(rt.get("fade_s", 0.5) * sr), round(rt.get("duck_s", 0.5) * sr)
    level[:fi] = np.sin(np.linspace(0, np.pi / 2, fi)) ** 2
    spans = sorted(sound_up_spans(plan, tl))
    for a_f, z_f in spans:
        a, z = round(a_f / fps * sr), round(z_f / fps * sr)
        level[max(0, a):min(n, z)] = 0
        if a > 0:
            m = min(du, a)
            level[a - m:a] = np.minimum(level[a - m:a], np.cos(np.linspace(0, np.pi / 2, m)) ** 2)
        if z < n:
            m = min(du, n - z)
            if z_f >= total - 1:
                level[z:] = 0
            else:
                level[z:z + m] = np.minimum(level[z:z + m], np.sin(np.linspace(0, np.pi / 2, m)) ** 2)
    if spans and spans[-1][1] >= total - 1:                     # the logo's music: out for good before it
        level[round(spans[-1][0] / fps * sr):] = 0
    y = bed * level
    full = level > 0.999
    m = bed.copy()
    steps = np.abs(np.diff(m))
    near = [j for j in joins if 2 <= j < len(m) - 3]                # the steps at the joins against the noise's own
    j_ratio = float(np.mean([np.abs(np.diff(m[j - 2:j + 3])).mean() for j in near]) / steps.mean()) if near else None
    e = np.array([np.sqrt(np.mean(np.square(m[i:i + 480]))) for i in range(0, min(len(m), 60 * sr) - 480, 480)])
    e = e - e.mean()
    ac = np.correlate(e, e, "full")[len(e) - 1:]
    ac = ac / ac[0]
    info = {"rms_dbfs": round(20 * np.log10(np.sqrt(np.mean(np.square(y[full]))) + 1e-12), 2),
            "peak_dbfs": round(20 * np.log10(np.abs(y).max() + 1e-12), 2), "pieces": len(pieces),
            "pool_s": round(pool_s, 2), "crossfade_s": xf / sr, "joins": len(joins),
            "join_step_ratio": round(j_ratio, 3) if j_ratio is not None else None,   # 1.0: no step at a join
            "envelope_repeat_max": round(float(np.max(ac[20:300])), 3),   # 0.2 to 3 s, 10 ms steps
            "up_spans_s": [], "sources": srcs}
    edges = np.flatnonzero(np.diff(np.concatenate([[0], full.astype(np.int8), [0]])))
    info["up_spans_s"] = [[round(a / sr, 3), round(b / sr, 3)] for a, b in zip(edges[::2], edges[1::2])]
    if info["envelope_repeat_max"] > 0.3 or (j_ratio is not None and j_ratio > 1.3):
        raise SystemExit(f"room tone: a repeat or a join shows: {info}")
    h = hashlib.sha256(np.round(y, 7).tobytes()).hexdigest()[:8]
    out = reel_dir(plan) / "audio" / f"room_tone_{h}.wav"
    for old in out.parent.glob("room_tone_*.wav"):              # (a superseded bed: Fable R7-5)
        if old != out:
            old.unlink(missing_ok=True)
    if not out.exists():
        pcm = np.clip(np.round(y * 32767), -32768, 32767).astype("<i2")
        with wave.open(str(out), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sr)
            f.writeframes(pcm.tobytes())
    return {"path": str(out), **info}


def momentary_max(path):
    """The loudest 400 ms (EBU momentary loudness, LUFS) of a short sound: its loudness as it is heard."""
    import re
    r = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af",
                        "ebur128=metadata=1,ametadata=print:key=lavfi.r128.M", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    vals = [float(v) for v in re.findall(r"lavfi\.r128\.M=(-?[\d.]+)", r)]
    return max(vals) if vals else None


def whoosh(plan):
    """R248 round 3: the plan's whoosh (a library sound) as a mono WAV whose loudest 400 ms sits at the plan's
    momentary_lufs (under the voice's own peaks, so it is heard without jumping out): (path, gain, measured)."""
    w = plan.get("whoosh")
    if not w:
        return None
    src = Path(w["file"])
    m = momentary_max(src)
    if m is None:                                               # a sound under 400 ms has no momentary reading (F11)
        raise SystemExit(f"{src}: too short to measure (under 400 ms); pick a longer whoosh")
    gain = round(w["momentary_lufs"] - m, 2)
    h = hashlib.sha256(json.dumps([str(src), src.stat().st_size, gain]).encode()).hexdigest()[:8]
    out = reel_dir(plan) / "audio" / f"whoosh_{h}.wav"
    if not out.exists():
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-af",
                        f"volume={gain}dB,alimiter=limit={10 ** (LIMIT_DBFS / 20):.5f}:level=false:latency=true",
                        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", str(out)], check=True)
    return {"path": str(out), "gain_db": gain, "source_momentary_lufs": m, "momentary_lufs": momentary_max(out)}


def audio(plan):
    nar, info = narration_audio(plan)
    ups, uinfo = soundups(plan)
    doc = {"plan_digest": plan_digest(plan), "narration": {k: str(v) for k, v in nar.items()}, "narration_loudness": info,
           "sound_ups": [[b, k, str(w)] for b, k, w in ups], "sound_ups_loudness": uinfo, "whoosh": whoosh(plan),
           "room_tone": room_tone(plan, nar, timeline(plan))}
    (reel_dir(plan) / "audio" / "audio.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(json.dumps({"narration": info, "sound_ups": uinfo}, indent=1))
    return doc


# ------------------------------------------------------------------------------------------------- the timeline
def timeline(plan):
    """Every beat in frames on the reel: its start and length, its lines (absolute frames), its shots' places and the
    media frames they show (the last picture shot of a beat runs on to the beat's end, into its handle)."""
    fps, f0, out = fps_of(plan), 0, []
    find = media_of(plan)
    for beat in plan["beats"]:
        n = round(reel.beat_length(plan, beat) * fps)
        lines_ = reel.timed_lines(plan, beat)
        if not all(x["voiced"] for x in lines_):
            raise SystemExit(f"{beat['id']}: not every line is voiced")
        places = reel.shot_places(beat)
        shots, pics = [], [k for k, sh in enumerate(beat.get("shots", [])) if not sh.get("audio_only")]
        for k, sh in enumerate(beat.get("shots", [])):
            path, m = find(sh)
            at = f0 + round(places[k] * fps)
            src0 = round(sh["in_s"] * fps) - m["first_frame"]
            length = round((sh["out_s"] - sh["in_s"]) * fps)
            nxt = [j for j in pics if j > k]
            if not sh.get("audio_only") and nxt:            # up to the next picture's first frame (Fable F9: never
                length = f0 + round(places[nxt[0]] * fps) - at   # two rounded lengths overlapping)
            vlen = length
            if pics and k == pics[-1] and "at_s" not in sh:     # (a shot placed at its own time keeps its length,
                vlen = f0 + n - at                          # Fable r2 F5) the last picture holds to the beat's end
                if src0 + vlen > m["frames"]:
                    raise SystemExit(f"{beat['id']} shot {k}: {vlen} frames from {src0} pass its media's "
                                     f"{m['frames']}: widen the plan's handle")
                if sh.get("sound") == "up" and vlen > length:   # its sound would stop before its picture (F1)
                    raise SystemExit(f"{beat['id']} shot {k}: the beat runs {vlen - length} frames past this sound-up's "
                                     "end: lengthen the shot (its out_s) to the beat")
            shots.append({"k": k, "shot": sh, "path": str(path), "at": at, "src0": src0, "len": length,
                          "vlen": vlen if not sh.get("audio_only") else 0})
        out.append({"beat": beat, "f0": f0, "n": n, "shots": shots,
                    "lines": [{**x, "at": f0 + round(x["start"] * fps)} for x in lines_]})
        f0 += n
    return out


# ------------------------------------------------------------------------------------------------- the graphics
def layer_jobs(plan, tl):
    """Each beat's Remotion layer, alone (transparent), its full length: [(beat id, job)]."""
    reel.check_joins(plan)                                      # before any render (Fable K1)
    fps, jobs = fps_of(plan), []
    for b in tl:
        beat = b["beat"]
        if not beat.get("layer"):
            continue
        lay = reel.layer_props(plan, beat)
        run_on = reel.join_frames(fps) if beat.get("join_next") else 0      # it dissolves into the next (J1)
        props = {"durationInFrames": b["n"] + run_on, "fps": fps, "width": plan["width"], "height": plan["height"],
                 "layer": lay}
        h = hashlib.sha256((json.dumps(props, sort_keys=True) + code_digest()).encode()).hexdigest()[:8]
        out = reel_dir(plan) / "graphics" / f"{beat['id']}_{h}.mov"
        jobs.append((beat["id"], {"out": str(out), "props": props}))
    return jobs


def code_digest():
    """The reel's graphics code (Reel.tsx, the kit, the tokens): a change renders every layer again."""
    ov = ROOT / "remotion" / "src" / "overlays"
    return hashlib.sha256(b"".join((ov / f).read_bytes() for f in ("Reel.tsx", "kit.tsx", "tokens.json"))).hexdigest()


def layers(plan):
    tl = timeline(plan)
    jobs = layer_jobs(plan, tl)
    todo = [j for _, j in jobs if not Path(j["out"]).exists()]
    if todo:
        reel.render(plan, todo, "layers")
    for bid, j in jobs:
        n = reel.video_frames(Path(j["out"]))
        if n != j["props"]["durationInFrames"]:
            raise SystemExit(f"{j['out']}: {n} frames, the beat has {j['props']['durationInFrames']}")
    return {bid: j["out"] for bid, j in jobs}


# ------------------------------------------------------------------------------------------------- the captions
def fits(text, width):
    """Whether text wraps into at most two lines of width (the planner's own wrap, the most even split)."""
    from pipeline.edit.plan import _wrap
    lines = _wrap(text, width).splitlines()
    return len(lines) <= 2 and all(len(x) <= width for x in lines)


def split_words(words, text, width):
    """Words (with char spans in text) -> groups that each fit two lines: whole sentences where they fit; a longer
    sentence split where the halves are most even, at a comma or colon when one is near the middle."""
    span = lambda g: text[g[0]["char"][0]:g[-1]["char"][1]]
    after = lambda w: text[w["char"][1]:w["char"][1] + 1]
    sentences, cur = [], []
    for w in words:
        cur.append(w)
        if after(w) in (".", "?", "!"):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)
    out = []

    def go(g):
        if fits(span(g), width) or len(g) < 2:
            out.append(g)
            return
        total = len(span(g))
        best = None
        for i in range(1, len(g)):
            left = len(span(g[:i]))
            score = abs(total / 2 - left) - (12 if after(g[i - 1]) in (",", ":", ";") else 0)
            if best is None or score < best[0]:
                best = (score, i)
        go(g[:best[1]])
        go(g[best[1]:])
    for snt in sentences:
        go(snt)
    return out


def card_caption_slot(plan):
    """Where a card beat's captions go (R248 round 7: right of the narrator): (centre x, characters a line), between
    her widest reach as placed (narrator_renders) plus captions_right_of_narrator.gap_px and title-safe's right edge;
    without her renders, under the card as before (CARD_CX, CARD_CHARS). Needs every render on disk (Fable R7-3)."""
    nar = plan.get("narrator") or {}
    if not nar.get("renders") or not plan.get("captions_right_of_narrator"):
        return CARD_CX, CARD_CHARS
    gone = [r for r in nar["renders"] if not Path(r).exists()]
    if gone:
        raise SystemExit(f"captions right of her need her renders first; missing {gone[0]}")
    left = narrator_renders(plan)[1][2] + plan["captions_right_of_narrator"].get("gap_px", 24)
    chars = int((SAFE_RIGHT - left - CAPTION_PAD_PX) // CAPTION_CHAR_PX)
    if chars < 24:
        raise SystemExit(f"captions right of her: only {chars} characters a line fit between x {left} and {SAFE_RIGHT}")
    return (left + SAFE_RIGHT) / 2, chars


def cues(plan, tl):
    """The narration's caption cues (C1 to C7): each line's sentences, one cue each where it fits two lines at the
    spot's width, a longer one split most evenly (at a comma near the middle when there is one); the display text
    with its punctuation (W9); a cue starts on its first word (C5) and runs to the next cue, or a little past its last
    word; never overlapping, never past its beat."""
    from pipeline.edit.plan import _wrap
    fps, out = fps_of(plan), []
    card_cx, card_chars = card_caption_slot(plan)
    for b in tl:
        card = b["beat"]["layout"] == "card"
        width = card_chars if card else FRAME_CHARS
        end_s = (b["f0"] + b["n"]) / fps
        for ln in b["lines"]:
            text, words = ln["text"], ln["words"]
            if any(w.get("char") is None for w in words):
                raise SystemExit(f"{ln['id']}: its words have no place in the text (voice it again)")
            for g in split_words(words, text, width):
                a, z = g[0]["char"][0], g[-1]["char"][1]
                while z < len(text) and text[z] in ".,:;?!'’\"":    # the punctuation after the last word
                    z += 1
                out.append({"start": b["f0"] / fps + g[0]["start"], "end": min(b["f0"] / fps + g[-1]["end"] + 0.3, end_s),
                            "text": _wrap(text[a:z], width), "cx": card_cx if card else FRAME_CX,
                            "beat": b["beat"]["id"]})
    for b in tl:                                                # a sound-up's words at the house size (the visual
        for sh in b["shots"]:                                   # review's V6), where the shot says what they are
            cap = sh["shot"].get("caption")
            if cap and not (sh["shot"]["in_s"] <= cap["in_s"] < cap["out_s"] <= sh["shot"]["out_s"]):
                raise SystemExit(f"{b['beat']['id']} shot {sh['k']}: its caption {cap['in_s']}..{cap['out_s']} isn't "
                                 "inside the shot")
            if cap:
                t0 = sh["at"] / fps + cap["in_s"] - sh["shot"]["in_s"]
                out.append({"start": t0, "end": min(sh["at"] / fps + cap["out_s"] - sh["shot"]["in_s"],
                                                    (b["f0"] + b["n"]) / fps),
                            "text": _wrap(cap["text"], FRAME_CHARS), "cx": FRAME_CX, "beat": b["beat"]["id"]})
    out.sort(key=lambda c: c["start"])
    for a, c in zip(out, out[1:]):                              # no overlap; a short gap closes onto the next cue
        if a["beat"] == c["beat"] and (a["end"] > c["start"] or c["start"] - a["end"] < 0.25):
            a["end"] = c["start"]
        elif a["end"] > c["start"]:
            a["end"] = c["start"]
    return out


def captions(plan, tl):
    from pipeline.edit.ppro import titles
    cs = cues(plan, tl)
    total = tl[-1]["f0"] + tl[-1]["n"]
    place = lambda c, bw, bh: (c["cx"] - bw / 2, CAPTION_BOTTOM - bh)
    titles.build(reel_dir(plan), cs, place, plan["width"], plan["height"], fps_of(plan), seq_name(plan), total,
                 size_px=CAPTION_PX, box_hex=CAPTION_BOX)
    return cs


# ------------------------------------------------------------------------------------------------- the XML
def build_xml(plan):
    from pipeline.edit import premiere as pr
    from pipeline.edit import stage
    from pipeline.edit.ppro import titles
    d, fps, W, H = reel_dir(plan), fps_of(plan), plan["width"], plan["height"]
    tl = timeline(plan)
    au = json.loads((d / "audio" / "audio.json").read_text(encoding="utf-8"))
    if au.get("plan_digest") != plan_digest(plan):
        raise SystemExit("audio/audio.json was made from another version of the plan: run audio again (Fable G3)")
    lay = layers(plan)
    total = tl[-1]["f0"] + tl[-1]["n"]
    ids, files = pr.Ids(), pr.Files(fps)
    s = pr.Seq(seq_name(plan), "sequence-reel", fps, W, H, total)
    nar = plan.get("narrator") or {}
    v1, v2, v3, v4 = (s.track("video", n) for n in TRACKS_V[:2] + [nar.get("track", TRACKS_V[2])] + TRACKS_V[3:])
    s.track("video", titles.TRACK)
    note = plan.get("note")                                     # R248: a standalone-only note (the AI voice's)
    v6 = s.track("video", NOTE_TRACK) if note else None
    v7 = s.track("video", FADES_TRACK) if plan.get("fades") else None
    reel.check_joins(plan)
    vj = s.track("video", JOIN_TRACK) if any(b.get("join_next") for b in plan["beats"]) else None
    a1, a2, a3 = (s.track("audio", n) for n in TRACKS_A)
    a4 = s.track("audio", WHOOSH_TRACK) if au.get("whoosh") else None
    a5 = s.track("audio", ROOM_TRACK) if au.get("room_tone") else None
    if bool(plan.get("room_tone")) != bool(au.get("room_tone")):
        raise SystemExit("audio/audio.json's room tone doesn't match the plan's: run audio again")
    if a5 is not None:                                         # R248 round 7: one clip from 0, its level in the WAV
        stage.audio_clip(a5, ids, files, "room tone", 0, Path(au["room_tone"]["path"]), fps, 0)
    s_in = int(3600 * fps)

    def still(track, png, a, b, name, fly_from=None, extend=0):
        """A still from a to b; extend: frames it runs on past b, fading out (a joined card's, J1)."""
        c = pr.clipitem(track, ids, name, a, b + extend, s_in, s_in + b + extend - a, 12 * s_in, fps, alpha="straight")
        files.el(c, png, frames=12 * s_in, w=W, h=H)
        if fly_from is None:
            pr.motion(c)
            if extend:
                pr.opacity(c, opacity_keys(s_in, b - a, None, extend))
        else:                                       # flies in (R248 r3, the visual review's V9): fly_from (s, px, px)
            fly_keys(c, *fly_from, n=b - a, extend=extend)     # one Opacity for both (Fable r4 H1)

    def fly_keys(c, at_s, dx_px, dy_px, rot=12.0, e=None, n=None, extend=0):
        """Reel.tsx enterStyle's move as Premiere keys on a still (in s_in): from (dx, dy) px, rot degrees and 55%
        into place over FLY_S from at_s, eased as backOut(x, 1.2)."""
        f0 = round(at_s * fps)
        f1 = f0 + round(reel.FLY_S * fps) if e is None else min(e - 2, f0 + round(reel.FLY_S * fps))
        ease = lambda x: 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2      # Reel.tsx's backOut(x, 1.2)
        ks = [f0 + round(i * (f1 - f0) / 10) for i in range(11)]
        kv = [ease(i / 10) for i in range(11)]
        dx, dy = dx_px / W, dy_px / H
        pr.motion(c, scale=[(s_in, 55.0)] + [(s_in + k, round(55 + 45 * v, 3)) for k, v in zip(ks, kv)],
                  rotation=[(s_in, rot)] + [(s_in + k, round(rot * (1 - v), 3)) for k, v in zip(ks, kv)],
                  center=[(s_in, (dx, dy))] + [(s_in + k, (round(dx * (1 - v), 4), round(dy * (1 - v), 4)))
                                               for k, v in zip(ks, kv)])
        fo = max(1, round(reel.FLY_S * 0.35 * fps))    # enterStyle's opacity ramp (Fable r3 follow-up G3)
        assert n or not extend, "a still that runs on needs its length (Fable K8)"
        pr.opacity(c, opacity_keys(s_in, n or 0, (f0, fo), extend))   # and a join's fade-out, in the same Opacity

    room, narrator = d / "public" / plan.get("room", "room.png"), d / "public" / nar.get("png", "narrator_left.png")
    spans = []                                                  # the room under every beat but the full-frame ones,
    for b in tl:                                                # and under a full beat's fly-in (R248 r3)
        e = round(reel.enter_s(b["beat"]) * fps)
        sp = (b["f0"], b["f0"] + b["n"]) if b["beat"]["layout"] != "full" else (b["f0"], b["f0"] + e) if e else None
        if sp and spans and spans[-1][1] == sp[0]:
            spans[-1] = (spans[-1][0], sp[1])
        elif sp:
            spans.append(sp)
    for a, z in spans:                                          # one clip per run of beats that use it
        still(v1, room, a, z, "room")
    def fly_in(b):                                              # a full beat's fly-in: its first frame flies in
        """(placed in its beat's turn: a clip out of time order on a track left Premiere's export without the
        track's footage, round 3)"""
        e = round(reel.enter_s(b["beat"]) * fps)
        if not (e and b["beat"]["layout"] == "full" and (b["beat"].get("enter") or {}).get("fly")):
            return
        sh = next(x for x in b["shots"] if x["vlen"])
        st = Path(sh["path"]).stat()
        hp = hashlib.sha256(f"{sh['path']}|{st.st_size}|{st.st_mtime_ns}|{sh['src0']}".encode()).hexdigest()[:8]
        png = d / "public" / f"fly_{b['beat']['id']}_{hp}.png"   # named by what made it: Premiere locks its media (F4)
        if not png.exists():
            subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{max(0.0, (sh['src0'] - 0.5) / fps):.4f}", "-i",
                            sh["path"], "-frames:v", "1", "-vf", "scale=in_color_matrix=bt709:out_color_matrix=bt709",
                            str(png)], check=True)
        c = pr.clipitem(v2, ids, f"{b['beat']['id']} fly-in (its first frame)", b["f0"], b["f0"] + e, s_in, s_in + e,
                        12 * s_in, fps)
        files.el(c, png, frames=12 * s_in, w=W, h=H)
        fly_keys(c, reel.FLY_AT_S, 1500, -90, 12.0, e)   # Reel.tsx's enterStyle (Fable r3 F9: the two enters rhyme)
    win = reel.window(plan)
    renders = narrator_renders(plan)[0] if nar.get("renders") else None
    if nar.get("motion") and not renders:
        raise SystemExit("narrator.motion places her renders; the placeholder still is placed already (Fable B5)")
    segs = card_segments(plan, [{"id": b["beat"]["id"], "f0": b["f0"], "n": b["n"]} for b in tl])
    if renders and len(renders) != len(segs):
        raise SystemExit(f"{len(renders)} narrator renders for {len(segs)} card segments")
    for b in tl:
        beat = b["beat"]
        flies = (beat.get("enter") or {}).get("fly")
        jo = reel.join_frames(fps) if beat.get("join_next") else 0     # runs on into the next beat (check_joins)
        ji = reel.join_frames(fps) if reel.joined_from(plan, beat) else 0   # fades in under the last one (J1)
        if beat["layout"] == "card" and not renders:
            still(v3, narrator, b["f0"], b["f0"] + b["n"], f"{nar.get('clip', 'narrator still')} ({beat['name']})",
                  (reel.FLY_AT_S + 0.15, -1500, 60, -12.0) if flies else None, jo)
        seg = next((g for g in segs if g["start"] == b["f0"]), None) if renders else None
        if seg is not None:                                     # her render, lip-synced: its time 0 is the segment's
            mov, mframes = renders[segs.index(seg) + 1]         # start less the upload's pad (R100)
            last = next(x for x in tl if x["beat"]["id"] == seg["beats"][-1])
            # into a joined beat she fades out over the segment's last half-dissolve and is gone at the change, so
            # she never shows through the next beat's footage (round 6 visual review); no run-on
            out_ = reel.join_frames(fps) // 2 if last["beat"].get("join_next") else 0
            ext = 0
            pad = round(AVATAR_PAD_S * fps)
            src_in, n_ = pad, seg["end"] - seg["start"]
            if src_in + n_ > mframes:
                raise SystemExit(f"the narrator render {mov.name} has {mframes} frames, the segment needs {src_in + n_}")
            if abs(mframes - (2 * pad + seg["end"] - seg["start"])) > 3:          # (by length: Fable N1)
                raise SystemExit(f"the narrator render {mov.name} ({mframes} frames) isn't the segment "
                                 f"{seg['beats']} ({seg['end'] - seg['start']} frames and {2 * pad} of pad)")
            c = pr.clipitem(v3, ids, f"narrator {segs.index(seg) + 1} ({', '.join(seg['beats'])})", seg["start"],
                            seg["start"] + n_, src_in, src_in + n_, mframes, fps, alpha="straight")
            files.el(c, mov, frames=mframes, w=W, h=H)
            k_, (cx_, cy_) = narrator_place(plan)
            pr.motion(c, scale=[(0, round(100 * k_, 4))], center=[(0, ((cx_ - W / 2) / W, (cy_ - H / 2) / H))])
            keys = []
            if flies:                                           # on a flying beat she fades in as its dip lifts
                fi = round(reel.FADE_S * fps)                   # (no motion: she stands; the card flies, Fable N6)
                keys += [(src_in, 0.0), (src_in + fi, 100.0)]
            if out_:
                keys += [(src_in + n_ - out_, 100.0), (src_in + n_, 0.0)]
            if keys:
                pr.opacity(c, keys)
        if note and beat["id"] in note["beats"]:
            nd = min(b["n"], round(note["dur_s"] * fps)) if note.get("dur_s") else b["n"]   # (round 5: once, ~4 s)
            ext = jo if nd == b["n"] else min(reel.join_frames(fps), b["n"] - nd)   # fading out where it ends (L4)
            still(v6, d / "public" / note["png"], b["f0"], b["f0"] + nd, f"AI voice note ({beat['name']})",
                  (reel.FLY_AT_S + 0.3, -1500, -90, -12.0) if flies else None, ext)
        fly_in(b)
        for sh in sorted(b["shots"], key=lambda x: x["at"]):    # in time order (GOTCHAS: Premiere drops a track)
            if not sh["vlen"]:
                continue
            path = Path(sh["path"])
            m_frames = reel.video_frames(path)
            c = pr.clipitem(v2, ids, f"{beat['id']} {sh['shot']['src']} {path.stem}", sh["at"], sh["at"] + sh["vlen"],
                            sh["src0"], sh["src0"] + sh["vlen"], m_frames, fps)
            files.el(c, path, frames=m_frames, w=W, h=H, audio={"rate": 48000, "channels": 2}
                     if plan["sources"][sh["shot"]["src"]].get("audio") else None)
            if beat["layout"] == "frame":                       # scaled into the stage frame's window
                k = win["w"] / W
                cx, cy = win["x"] + win["w"] / 2, win["y"] + win["h"] / 2
                pr.motion(c, scale=[(0, round(100 * k, 4))], center=[(0, ((cx - W / 2) / W, (cy - H / 2) / H))])
            fd = round(sh["shot"].get("fade_s", 0) * fps)       # faded in and out, never cut (R248: his avatar)
            if fd:
                a0, a9 = sh["src0"], sh["src0"] + sh["vlen"]
                pr.opacity(c, [(a0, 0.0), (a0 + fd, 100.0), (a9 - fd, 100.0), (a9, 0.0)])
            elif ji and sh["at"] == b["f0"]:                    # the beat's first picture, under the dissolve (J1)
                pr.opacity(c, [(sh["src0"], 0.0), (sh["src0"] + ji, 100.0)])
        if beat["id"] in lay:                               # (a joined card's on its own track, run on: J1)
            gc = stage.video_clip(vj if jo else v4, ids, files, f"graphics {beat['id']}", b["f0"],
                                  Path(lay[beat["id"]]), b["n"] + jo, fps, W, H)
            if jo:
                pr.opacity(gc, [(0, 100.0), (b["n"], 100.0), (b["n"] + jo, 0.0)])
        if a4 is not None and (beat.get("enter") or {}).get("fly"):     # the whoosh under the fly-in (R248 r3)
            stage.audio_clip(a4, ids, files, f"whoosh ({beat['name']})", b["f0"] + round(reel.FLY_AT_S * fps),
                             Path(au["whoosh"]["path"]), fps, 0)
        for ln in b["lines"]:
            stage.audio_clip(a1, ids, files, ln["id"], ln["at"], Path(au["narration"][ln["id"]]), fps, 0)
    ups = {(bid, k): Path(w) for bid, k, w in au["sound_ups"]}
    for b in tl:
        for sh in b["shots"]:
            w = ups.get((b["beat"]["id"], sh["k"]))
            if w is None:
                continue
            n = pr.probe_frames(w, fps, whole=True)
            at = sh["at"] - round((sh["shot"]["in_s"] - sh["shot"].get("audio_in_s", sh["shot"]["in_s"])) * fps)
            for track, ch, pan in ((a2, 1, -1), (a3, 2, 1)):      # both channels, panned to their sides (GOTCHAS)
                c = pr.clipitem(track, ids, f"{b['beat']['id']} sound-up", at, at + n, 0, n, n, fps)
                c.remove(c.find("alphatype"))
                files.el(c, w, frames=n, audio={"rate": 48000, "channels": 2})
                st = pr.sub(c, "sourcetrack")
                pr.sub(st, "mediatype", "audio")
                pr.sub(st, "trackindex", ch)
                pr.audio_pan(c, pan)
    fades = []
    if v7 is not None:                                          # the whole frame dips to black and back at every
        black = d / "public" / "black.png"                      # beat change (R248 r3)
        fd = round(reel.FADE_S * fps)
        for prev, b in zip(tl, tl[1:]):
            if prev["beat"].get("join_next"):                   # joined: one beat to David, a dissolve (round 4)
                continue
            a, z = b["f0"] - fd, b["f0"] + fd
            c = pr.clipitem(v7, ids, f"dip ({b['beat']['name']})", a, z, s_in, s_in + z - a, 12 * s_in, fps)
            files.el(c, black, frames=12 * s_in, w=W, h=H)
            pr.motion(c)
            pr.opacity(c, [(s_in, 0.0), (s_in + fd, 100.0), (s_in + 2 * fd, 0.0)])
            fades.append(b["f0"])
    pr.close_tracks(s)
    for kind in ("video", "audio"):                             # every track's clips in time order (GOTCHAS)
        for tr in s.el.find("media").find(kind).findall("track"):
            st = [int(c.findtext("start")) for c in tr.findall("clipitem")]
            if st != sorted(st):
                raise SystemExit(f"a {kind} track's clips aren't in time order: {st[:8]}")
    root = ET.Element("xmeml", version="4")
    root.append(s.el)
    ET.indent(root, "\t")
    xml = d / f"{proj_name(plan)}.xml"
    keep_superseded(plan)
    xml.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode")
                   + "\n", encoding="utf-8")
    cs = captions(plan, tl)
    doc = {"sequence": seq_name(plan), "fps": fps, "frames": total, "seconds": round(total / fps, 3),
           "plan_digest": plan_digest(plan),
           "beats": [{"id": b["beat"]["id"], "name": b["beat"]["name"], "f0": b["f0"], "n": b["n"],
                      "lines": [{"id": x["id"], "at": x["at"], "text": x["text"], "length": x["length"]} for x in b["lines"]],
                      "sound_ups": [{"at": a_, "len": z_ - a_} for a_, z_ in sound_up_spans(plan, [b])]}
                     for b in tl],
           "captions": cs, "fades": {"at": fades, "half_frames": round(reel.FADE_S * fps) if fades else 0,
                                     "joins": [p["f0"] + p["n"] for p in tl if p["beat"].get("join_next")]},
           "whooshes": [{"at": b["f0"] + round(reel.FLY_AT_S * fps), "beat": b["beat"]["id"]} for b in tl
                        if a4 is not None and (b["beat"].get("enter") or {}).get("fly")],
           "room_tone": ({k: au["room_tone"][k] for k in ("path", "rms_dbfs", "up_spans_s")} if a5 is not None else None)}
    (d / "timeline.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{xml}: {total} frames ({total / fps:.2f} s), {len(cs)} caption cues")
    return xml, doc


# ------------------------------------------------------------------------------------------------- Premiere
def markers(plan, doc):
    """A marker at every beat (R248): its name, and in the comment what the picture says and the narration."""
    fps, out = doc["fps"], []
    by = {b["id"]: b for b in plan["beats"]}
    for b in doc["beats"]:
        beat = by[b["id"]]
        screen = reel.screen_text(beat["layer"]) if beat.get("layer") else []
        said = " ".join(x["text"] for x in b["lines"]) or "(the finished video's own sound)"
        out.append({"t": b["f0"] / fps, "name": f"Beat: {b['name']}",
                    "comment": f"On screen: {' / '.join(x.strip() for x in screen)}. Narration: {said}"[:1000]})
    return out


def build(plan):
    from pipeline.edit.ppro.bridge import call, start
    from pipeline.edit.ppro.markers import add
    from pipeline.edit.ppro.project import media
    d = reel_dir(plan)
    xml, job = d / f"{proj_name(plan)}.xml", d / "caption_titles.json"
    prproj = d / f"{proj_name(plan)}.prproj"
    if prproj.exists():
        raise SystemExit(f"{prproj} exists (David may have changed it); move it aside to build again")
    gone = [m for m in media(xml) if not m.exists()]
    if gone:
        raise SystemExit(f"{len(gone)} media file(s) the XML uses are missing, first {gone[0]}")
    import zipfile
    broken = [c["mogrt"] for c in json.loads(job.read_text(encoding="utf-8"))["cues"]
              if not zipfile.is_zipfile(c["mogrt"]) or "definition.json" not in zipfile.ZipFile(c["mogrt"]).namelist()]
    if broken:                     # a broken template stops Premiere on a dialog (pipeline.edit.ppro.project)
        raise SystemExit(f"{len(broken)} caption template(s) missing or broken, first {broken[0]}")
    doc = json.loads((d / "timeline.json").read_text(encoding="utf-8"))
    if doc.get("plan_digest") != plan_digest(plan):
        raise SystemExit("timeline.json was made from another version of the plan: run xml again")
    print(json.dumps(start(), ensure_ascii=False))
    ok, r = False, {}
    try:
        r = call(f"aidvBuildProject({json.dumps(str(xml))}, {json.dumps(str(prproj))}, {json.dumps(str(job))}, "
                 f"{json.dumps(BINS)})", timeout=900, reload=True)
        print(json.dumps(r, ensure_ascii=False))
        ok = not r.get("missing")
    finally:                       # saved and closed when whole; closed unsaved and moved aside when not
        try:
            call("(function () { for (var k = 0; k < app.projects.numProjects; k++) { if (app.projects[k].path === %s)"
                 " { app.projects[k].closeDocument(%s, false); return true; } } return false; })()"
                 % (json.dumps(str(prproj)), "true" if ok else "false"), timeout=120)
        finally:
            if not ok and prproj.exists():
                try:
                    prproj.replace(prproj.with_suffix(".failed.prproj"))
                except OSError as e:          # Premiere may still hold it (GOTCHAS)
                    print(f"could not move the failed build aside ({e}); move {prproj} by hand", file=sys.stderr)
    if not ok:
        raise SystemExit(f"caption titles not placed: {r.get('missing')}")
    print(json.dumps(add(prproj, seq_name(plan), markers(plan, doc)), ensure_ascii=False))
    (d / "build.json").write_text(json.dumps({"prproj": str(prproj), "plan_digest": doc["plan_digest"],
                                              "frames": doc["frames"], "prproj_mtime": prproj.stat().st_mtime},
                                             indent=1), encoding="utf-8")
    return prproj


def export(plan, frames_at=(), suffix=""):
    """The two H.264s beside the project, from the one sequence: standalone (as built), talk (the narration track and
    the caption titles' track muted for the export, then unmuted; the project is closed unsaved). frames_at: seconds
    to export as Premiere's own single frames (R240) into <reel>/frames<suffix>/ while it's open. suffix (empty or like
    _r6b) names the mp4s, exports<suffix>.json and the frames' folder; existing mp4s are replaced only by an unsuffixed
    export of the same plan version (Fable B4)."""
    from pipeline.edit.ppro.bridge import call, start
    from pipeline.edit.ppro.exports import H264_PRESET, make_presets
    from pipeline.edit.ppro import titles
    d = reel_dir(plan)
    prproj = d / f"{proj_name(plan)}.prproj"
    if not H264_PRESET.exists():
        make_presets()
    suffix = check_suffix(suffix)
    outs = {"standalone": d / f"{proj_name(plan)}{suffix}_standalone.mp4",
            "talk": d / f"{proj_name(plan)}{suffix}_talk.mp4"}
    rec_p = d / f"exports{suffix}.json"
    prev = json.loads(rec_p.read_text(encoding="utf-8")) if rec_p.exists() else {}
    there = [p.name for p in outs.values() if p.exists()]
    if suffix and rec_p.exists():
        there.append(rec_p.name)
    if there and (suffix or prev.get("plan_digest") != plan_digest(plan)):
        why = ("a suffixed export is never replaced" if suffix else
               f"{rec_p.name} is missing" if not prev else "an export of another version")
        raise SystemExit(f"{there[0]} exists ({why}): "
                         "export with another --suffix, or move it aside (Fable B4)")
    talk_a = [TRACKS_A[0]] + ([ROOM_TRACK] if plan.get("room_tone") else [])   # what the talk version leaves out
                                                              # (round 7: her room tone goes with her voice)
    talk_v = [titles.TRACK] + ([NOTE_TRACK] if plan.get("note") else [])
    mute_js = """function (s, on) { var i, j, n = []; var A = %s, V = %s;
      for (i = 0; i < s.audioTracks.numTracks; i++) { for (j = 0; j < A.length; j++) {
        if (s.audioTracks[i].name === A[j]) { s.audioTracks[i].setMute(on); n.push(A[j]); } } }
      for (i = 0; i < s.videoTracks.numTracks; i++) { for (j = 0; j < V.length; j++) {
        if (s.videoTracks[i].name === V[j]) { s.videoTracks[i].setMute(on); n.push(V[j]); } } }
      return n; }""" % (json.dumps(talk_a), json.dumps(talk_v))
    unmute_js = """function (s) { var i;
      for (i = 0; i < s.audioTracks.numTracks; i++) { s.audioTracks[i].setMute(0); }
      for (i = 0; i < s.videoTracks.numTracks; i++) { s.videoTracks[i].setMute(0); } }"""
    doc = json.loads((d / "timeline.json").read_text(encoding="utf-8"))
    built = json.loads((d / "build.json").read_text(encoding="utf-8")) if (d / "build.json").exists() else {}
    if not (doc.get("plan_digest") == built.get("plan_digest") == plan_digest(plan)):
        raise SystemExit("the project, timeline.json and the plan aren't the same version: run xml and build again (G1)")
    if built.get("prproj_mtime") and abs(prproj.stat().st_mtime - built["prproj_mtime"]) > 1:
        raise SystemExit(f"{prproj.name} was saved after it was built or adopted: adopt it again (Fable B6)")
    shots_tl = timeline(plan)                          # for the footage test (footage_missing)
    print(json.dumps(start(), ensure_ascii=False))
    call("""(function () {
      if (app.projects.numProjects > 0) { throw new Error("a project is open in Premiere (" + app.projects[0].path + ")"); }
      if (!app.openDocument(%s)) { throw new Error("Premiere wouldn't open " + %s); }
      if (app.project.path !== %s) {     // none was open before: whatever is open now, this call opened (exports.export)
        var was = app.project.path;
        for (var k = app.projects.numProjects - 1; k >= 0; k--) { app.projects[k].closeDocument(false, false); }
        throw new Error("the project opened as " + was);
      }
      return true; })()""" % (json.dumps(str(prproj)), json.dumps(str(prproj)), json.dumps(str(prproj))), timeout=300)
    for p in outs.values():                          # only once Premiere has the project: a refusal keeps the last ones
        p.unlink(missing_ok=True)
    got = {}
    try:
        for name, out in outs.items():
            talk = 1 if name == "talk" else 0
            want = len(talk_a) + len(talk_v)
            said = call("""(function () {
              var s = aidvFindSequence(%s), mute = %s, unmute = %s;
              app.project.openSequence(s.sequenceID);
              unmute(s);                 // (also clears a mute set by hand: the project is closed unsaved)
              var muted = %d ? mute(s, 1) : [];
              if (%d && muted.length !== %d) {
                unmute(s);
                throw new Error("the talk version found " + muted.length + " of its %d tracks to mute: " + muted.join(", "));
              }
              var r = s.exportAsMediaDirect(%s, %s, 0);
              unmute(s);
              return {said: r, toggled: muted}; })()"""
                        % (json.dumps(seq_name(plan)), mute_js, unmute_js, talk, talk, want, want,
                           json.dumps(str(out)), json.dumps(str(H264_PRESET))), timeout=3600)
            if not out.exists():
                raise SystemExit(f"Premiere exported nothing for {name}: {said}")
            late = pending(out, fps_of(plan)) or footage_missing(plan, out, shots_tl)
            tries = 1
            while late and tries < 3:                   # media not loaded yet when the export began: export again
                out.unlink()
                call("""(function () { var s = aidvFindSequence(%s), mute = %s, unmute = %s;
                  unmute(s);
                  if (%d && mute(s, 1).length !== %d) { unmute(s); throw new Error("the talk tracks went missing"); }
                  var r = s.exportAsMediaDirect(%s, %s, 0);
                  unmute(s);
                  return r; })()""" % (json.dumps(seq_name(plan)), mute_js, unmute_js, talk, want,
                                         json.dumps(str(out)), json.dumps(str(H264_PRESET))), timeout=3600)
                late = pending(out, fps_of(plan)) or footage_missing(plan, out, shots_tl)
                tries += 1
            if late:
                raise SystemExit(f"{name}: Media pending, or footage not drawn, at {late[:5]} s after {tries} exports")
            got[name] = {"path": str(out), "frames": reel.video_frames(out), "muted": said.get("toggled") if talk else [],
                         "exports": tries}
            print(json.dumps({name: got[name]}), flush=True)
        if frames_at:
            from pipeline.edit.ppro.project import frames
            ok = frames({"sequence": seq_name(plan)}, list(frames_at), d / f"frames{suffix}")
            got["frames"] = {"times": list(frames_at), "ok": ok}
    finally:
        call("(function () { for (var k = app.projects.numProjects - 1; k >= 0; k--) { if (app.projects[k].path === %s)"
             " { app.projects[k].closeDocument(false, false); } } return true; })()" % json.dumps(str(prproj)),
             timeout=120)
    got["plan_digest"] = doc["plan_digest"]
    rec_p.write_text(json.dumps(got, indent=1), encoding="utf-8")
    return got


def keep_superseded(plan):
    """Before xml writes a new version: the last version's XML and timeline.json kept aside as
    <project>_<digest>.xml and timeline_<digest>.json, so adopt can diff the built version against the new one."""
    d = reel_dir(plan)
    tj, xml = d / "timeline.json", d / f"{proj_name(plan)}.xml"
    if not tj.exists():
        return None
    od = json.loads(tj.read_text(encoding="utf-8")).get("plan_digest")
    if not od or od == plan_digest(plan):
        return None
    shutil.copy2(tj, d / f"timeline_{od}.json")
    if xml.exists():
        shutil.copy2(xml, d / f"{proj_name(plan)}_{od}.xml")
    return od


def xml_layout(xml):
    """The FCP 7 XML's tracks: {track name: sorted [(start, end, in, file name)]} in frames (clipitems only)."""
    root = ET.parse(xml).getroot()
    names = {f.get("id"): f.findtext("name") for f in root.iter("file") if f.findtext("name")}
    out = {}
    for kind in ("video", "audio"):
        for tr in root.find("sequence").find("media").find(kind).findall("track"):
            items = [(int(c.findtext("start")), int(c.findtext("end")), int(c.findtext("in")),
                      names.get(c.find("file").get("id")) if c.find("file") is not None else None)
                     for c in tr.findall("clipitem")]
            if items:
                out[(kind, tr.get("MZ.TrackName"))] = sorted(items)
    return out


def project_layout(seq):
    """A sequence as pipeline.edit.prproj reads it: ({(kind, track name): sorted [(start, end, in, file name)]} in
    frames, {(kind, track name): [each item's effects]})."""
    ft = seq["frame_ticks"]
    fr = lambda t: round((t or 0) / ft)
    lay, fx = {}, {}
    for kind in ("video", "audio"):
        for t in seq[f"{kind}_tracks"]:
            items = t["items"]
            if not items:
                continue
            key = (kind, t["name"])
            lay[key] = sorted((fr(i.get("start_ticks")), fr(i.get("end_ticks")), fr(i.get("src_in_ticks")),
                               Path((i.get("source") or {}).get("file_path") or "").name or None) for i in items)
            fx[key] = [i.get("effects") or {} for i in items]
    return lay, fx


def motion_of(effects):
    """A clip's Motion as {param name: static value}, {} at defaults (DefaultMotion), None when keyframed."""
    if effects.get("default_motion"):
        return {}
    for c in effects.get("components", []):
        if c.get("match_name") == "AE.ADBE Motion":
            if any(p.get("keyframes") for p in c["params"]):
                return None
            return {p["name"]: p.get("static") for p in c["params"] if p.get("name")}
    return {}


def adopt_problems(xml_lay, proj_lay, proj_fx, nar_track, motion, captions_n, caption_track):
    """What keeps a saved project from being the build of the XML just written (Fable B1): every XML track's clips
    (start, end, in, file) as the project has them; the caption track as many titles as caption_titles.json; no other
    track with clips; every narrator clip's Motion exactly narrator.motion (scale, position; anchor at the centre, no
    rotation or crop). Opacity keys, filters and the titles' text aren't compared."""
    bad = []
    for key, items in xml_lay.items():
        got = proj_lay.get(key)
        if got is None:
            bad.append(f"{key[0]} track {key[1]!r} isn't in the project")
        elif got != items:
            diff = sorted(set(items) ^ set(got))
            bad.append(f"{key[0]} track {key[1]!r}: {len(items)} clips in the XML, {len(got)} in the project; "
                       f"first difference {diff[:1]}")
    for key, items in proj_lay.items():
        if key in xml_lay:
            continue
        if key == ("video", caption_track):
            if len(items) != captions_n:
                bad.append(f"{caption_track!r}: {len(items)} titles in the project, {captions_n} cues")
        else:
            bad.append(f"{key[0]} track {key[1]!r} has {len(items)} clips the XML doesn't")
    want = {"Scale": motion["scale"], "Position": list(motion["position"])}
    for n, fx in enumerate(proj_fx.get(("video", nar_track), []), 1):
        m = motion_of(fx)
        if m is None:
            bad.append(f"narrator clip {n}: its Motion is keyframed")
            continue
        sc, pos = m.get("Scale", 100.0), m.get("Position", [0.5, 0.5])
        if abs(sc - want["Scale"]) > 1e-3 or any(abs(a - b) > 1e-6 for a, b in zip(pos, want["Position"])):
            bad.append(f"narrator clip {n}: Scale {sc}, Position {pos}; the plan's motion is {want}")
        if [round(v, 6) for v in m.get("Anchor Point", [0.5, 0.5])] != [0.5, 0.5] or m.get("Rotation", 0.0) \
                or any(m.get(c, 0.0) for c in ("Crop Left", "Crop Top", "Crop Right", "Crop Bottom")):
            bad.append(f"narrator clip {n}: anchor, rotation or crop changed: {m}")
    return bad


def adopt(plan, why):
    """Record the reel's saved project as this plan's build without building it: David changed the project in
    Premiere and the change is now in the plan (R248 round 6: his narrator framing), so the project is the build of
    this plan. Run xml first. Verified, refused otherwise (Fable B1): the saved project, read back read-only (gunzipped,
    pipeline.edit.prproj), has the new XML's clips on every track, the caption titles, and narrator.motion on every
    narrator clip (adopt_problems); and the last built version's timeline_<digest>.json, kept aside by xml, differs
    from the new timeline.json in nothing but the digest (when it was kept). The project's mtime is recorded: export
    refuses a project saved since (B6). The project itself is never opened in Premiere or written."""
    from pipeline.edit.prproj import Project
    from pipeline.edit.ppro import titles
    d = reel_dir(plan)
    prproj, xml, tj = d / f"{proj_name(plan)}.prproj", d / f"{proj_name(plan)}.xml", d / "timeline.json"
    if not (why or "").strip():
        raise SystemExit("adopt needs --why: what changed in the project, and that the plan now says it")
    if not tj.exists() or not xml.exists():
        raise SystemExit("timeline.json or the XML is missing: run xml first")
    doc = json.loads(tj.read_text(encoding="utf-8"))
    if doc.get("plan_digest") != plan_digest(plan):
        raise SystemExit("timeline.json isn't this plan's: run xml first")
    if not prproj.exists():
        raise SystemExit(f"{prproj} is missing")
    nar = plan.get("narrator") or {}
    if not nar.get("motion"):
        raise SystemExit("adopt is for a project David changed whose change is in the plan; narrator.motion is unset")
    old = json.loads((d / "build.json").read_text(encoding="utf-8")) if (d / "build.json").exists() else {}
    mtime = prproj.stat().st_mtime
    seq = Project(str(prproj)).parse_sequence(seq_name(plan))
    proj_lay, proj_fx = project_layout(seq)
    cues_n = len(json.loads((d / "caption_titles.json").read_text(encoding="utf-8"))["cues"])
    bad = adopt_problems(xml_layout(xml), proj_lay, proj_fx, nar.get("track", TRACKS_V[2]), nar["motion"], cues_n,
                         titles.TRACK)
    if not proj_fx.get(("video", nar.get("track", TRACKS_V[2]))):
        bad.append("the project has no narrator clips")
    built = old.get("built_digest") if old.get("plan_digest") == doc["plan_digest"] else old.get("plan_digest")
    kept = d / f"timeline_{built}.json" if built else None
    if kept and kept.exists():
        was = {k: v for k, v in json.loads(kept.read_text(encoding="utf-8")).items() if k != "plan_digest"}
        now = {k: v for k, v in doc.items() if k != "plan_digest"}
        bad += [f"timeline.json differs from the built version's in {k!r}" for k in sorted(set(was) | set(now))
                if was.get(k) != now.get(k)]
    if bad:
        raise SystemExit("not adopted, the saved project isn't this plan's build:\n  " + "\n  ".join(bad[:20]))
    if prproj.stat().st_mtime != mtime:
        raise SystemExit(f"{prproj.name} was saved while it was being read: adopt again")
    rec = {"prproj": str(prproj), "plan_digest": doc["plan_digest"], "frames": doc["frames"], "adopted": why.strip(),
           "prproj_mtime": mtime, "built_digest": built,
           "verified": {"tracks": len(proj_lay), "narrator_clips": len(proj_fx.get(("video", nar.get("track", TRACKS_V[2]))) or []),
                        "timeline_diff": str(kept.name) if kept and kept.exists() else "the built version's timeline wasn't kept"},
           "previous": old or None}                    # the record it replaces, adoption reasons and all
    (d / "build.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return rec


def nocap(plan):
    """R248 round 3: a source the plan marks "made_from" (the finished video without its captions, for the footage
    insets) exported from a COPY of the final's project (the final itself is never opened, R104): the copy, in the
    reel's _source/ folder, opened in an empty Premiere, the named tracks of each named sequence muted, the sequence
    exported as H.264 to the source's path, the copy closed unsaved. Its frame count must match the source it stands
    in for ("same_as"), and no Media pending card."""
    import shutil
    from pipeline.edit.ppro.bridge import call, start
    from pipeline.edit.ppro.exports import H264_PRESET, make_presets
    d = reel_dir(plan)
    for key, src in plan["sources"].items():
        mf = src.get("made_from")
        if not mf:
            continue
        out = reel.source_path(plan, key)
        if out.exists():
            print(f"{key}: {out} exists; delete it to export again")
            continue
        orig = Path(mf["prproj"])
        orig = orig if orig.is_absolute() else ROOT / orig
        copy = d / "_source" / f"{orig.stem}_{key}.prproj"
        copy.parent.mkdir(exist_ok=True)
        shutil.copyfile(orig, copy)                     # the final's project read, never opened
        if not H264_PRESET.exists():
            make_presets()
        out.parent.mkdir(parents=True, exist_ok=True)
        print(json.dumps(start(), ensure_ascii=False))
        call("""(function () {
          if (app.projects.numProjects > 0) { throw new Error("a project is open in Premiere (" + app.projects[0].path + ")"); }
          if (!app.openDocument(%s)) { throw new Error("Premiere wouldn't open the copy"); }
          if (app.project.path !== %s) {
            for (var k = app.projects.numProjects - 1; k >= 0; k--) { app.projects[k].closeDocument(false, false); }
            throw new Error("the copy opened as another project");
          }
          return true; })()""" % (json.dumps(str(copy)), json.dumps(str(copy))), timeout=300)
        said = None
        try:
            for attempt in range(3):                    # the Media pending race: export again (Fable r3 F1)
                out.unlink(missing_ok=True)
                said = call("""(function () {
                  var mute = %s, done = [], name, i, s;
                  for (name in mute) {
                    s = aidvFindSequence(name);
                    if (!s) { throw new Error("no sequence " + name); }
                    for (i = 0; i < s.videoTracks.numTracks; i++) {
                      if (mute[name].indexOf(s.videoTracks[i].name) >= 0) { s.videoTracks[i].setMute(1); done.push(name + ": " + s.videoTracks[i].name); }
                    }
                  }
                  var want = 0; for (name in mute) { want += mute[name].length; }
                  if (done.length !== want) { throw new Error("muted " + done.length + " of " + want + ": " + done.join("; ")); }
                  s = aidvFindSequence(%s);
                  app.project.openSequence(s.sequenceID);
                  return {muted: done, said: s.exportAsMediaDirect(%s, %s, 0)}; })()"""
                            % (json.dumps(mf["mute"]), json.dumps(mf["sequence"]), json.dumps(str(out)),
                               json.dumps(str(H264_PRESET))), timeout=4 * 3600)
                if not out.exists():
                    raise SystemExit(f"{key}: Premiere exported nothing ({said})")
                if not used_pending(plan, key, out):
                    break
        finally:
            call("(function () { for (var k = app.projects.numProjects - 1; k >= 0; k--) { if (app.projects[k].path === %s)"
                 " { app.projects[k].closeDocument(false, false); } } return true; })()" % json.dumps(str(copy)),
                 timeout=120)
        check_nocap(plan, key, out, said["muted"])


def used_pending(plan, key, out):
    """Seconds where a made source shows Premiere's Media pending card inside a span the plan's shots use."""
    late = [float(t) for t in pending(out, fps_of(plan))]
    dur = reel.video_frames(out) / fps_of(plan)
    used = [reel.span_of(plan, sh, dur) for b in plan["beats"] for sh in b.get("shots", []) if sh["src"] == key]
    return [t for t in late if any(a <= t <= z for a, z in used)]


def check_nocap(plan, key, out, muted=None):
    """A made source is whole (the frame count of the source it stands in for) and shows no Media pending card in
    any span the plan's shots take from it (with their handles); a card elsewhere (the round 3 export showed one over
    the logo outro, 1024 to 1050 s, which no inset uses) is recorded, not refused. Refused: renamed .bad.mp4."""
    mf = plan["sources"][key]["made_from"]
    n, want = reel.video_frames(out), reel.video_frames(reel.source_path(plan, mf["same_as"]))
    late = [float(t) for t in pending(out, fps_of(plan))]
    dur = n / fps_of(plan)
    used = [reel.span_of(plan, sh, dur) for b in plan["beats"] for sh in b.get("shots", []) if sh["src"] == key]
    hit = [t for t in late if any(a <= t <= z for a, z in used)]
    if n != want or hit:
        bad = out.with_suffix(".bad.mp4")
        out.replace(bad)
        why = ([f"{n} frames, {want} wanted"] if n != want else []) + ([f"Media pending in a used span at {hit[:5]}"]
                                                                        if hit else [])
        raise SystemExit(f"{key}: {'; '.join(why)}; kept as {bad}")
    info = {"path": str(out), "frames": n, "muted": muted,
            "pending_unused": [round(late[0], 3), round(late[-1], 3)] if late else None}
    (reel_dir(plan) / "_source" / f"{key}.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps({key: info}), flush=True)


AVATAR_PAD_S = 1.5                 # R100: silence each side of a render's upload (real idle frames for handles)
CREDITS_PER_MIN = {"avatar_iv": 31, "avatar_v": 48}      # HeyGen Pro plan credits a minute (R237); a plan's
                                                          # narrator.credits_per_min overrides (a photo look: 15, R238)
PLAN_USD_PER_CREDIT = 49 / 1000                           # HeyGen Pro, $49 a month for 1,000 credits (David)


def card_segments(plan, beats):
    """Runs of card beats (where the narrator stands), as [{start, end, beats}] in frames on the reel; beats: the
    timeline's (each with id, f0, n)."""
    lay = {b["id"]: b["layout"] for b in plan["beats"]}
    segs = []
    for b in beats:
        if lay[b["id"]] != "card":
            continue
        if segs and segs[-1]["end"] == b["f0"]:
            segs[-1]["end"], segs[-1]["beats"] = b["f0"] + b["n"], segs[-1]["beats"] + [b["id"]]
        else:
            segs.append({"start": b["f0"], "end": b["f0"] + b["n"], "beats": [b["id"]]})
    return segs


def narrator_place(plan):
    """Where her render frame goes on the reel: (scale, centre px). A plan's narrator.motion is David's own Premiere
    Motion (scale %, position as Premiere stores it: the frame centre's place, 0..1 of the frame, anchor at the
    centre; R248 round 6, his 182% head-and-waist framing), else narrator.offset_px at 100%."""
    nar, W, H = plan["narrator"], plan["width"], plan["height"]
    m = nar.get("motion")
    if m:
        if "offset_px" in nar:                       # one placement, never a decoy beside it (Fable B5)
            raise SystemExit("narrator has both motion and offset_px: motion places her; drop offset_px")
        return m["scale"] / 100.0, (m["position"][0] * W, m["position"][1] * H)
    dx, dy = nar.get("offset_px", [0, 0])
    return 1.0, (W / 2 + dx, H / 2 + dy)


def place_box(box, k, centre, W, H):
    """A box in the render frame [x0, y0, x1, y1] as placed on the reel (the frame scaled k about its centre, the
    centre at centre px), clamped to the reel's frame (Fable B3)."""
    px, py = centre
    place = lambda x, c, half: round(c + k * (x - half))
    b = [place(box[0], px, W / 2), place(box[1], py, H / 2), place(box[2], px, W / 2), place(box[3], py, H / 2)]
    return [max(0, b[0]), max(0, b[1]), min(W, b[2]), min(H, b[3])]


def narrator_still(plan):
    """The narrator's still for the stills David approves (R249) and the layer stills: plan narrator.png as drawn
    (placed already), or, when narrator.motion places her renders, the first render's first spoken frame placed as
    the build places it (Fable B5): public/narrator_placed_<key>.png. Returns its name in public/."""
    nar = plan.get("narrator") or {}
    if not nar.get("motion"):
        return nar.get("png", "narrator_left.png")
    if not nar.get("renders"):
        raise SystemExit("narrator.motion places her renders; the plan has none (Fable B5)")
    from PIL import Image
    d, W, H, fps = reel_dir(plan), plan["width"], plan["height"], fps_of(plan)
    k, (px, py) = narrator_place(plan)
    src = Path(nar["renders"][0])
    st = src.stat()
    key = hashlib.sha256(f"{src}|{st.st_size}|{st.st_mtime_ns}|{k}|{px}|{py}".encode()).hexdigest()[:8]
    out = d / "public" / f"narrator_placed_{key}.png"
    if not out.exists():
        mov = narrator_renders(plan)[0][1][0]
        tmp = d / "narrator" / f"_still_{key}.png"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{AVATAR_PAD_S + 0.5:.3f}", "-i", str(mov),
                        "-frames:v", "1", "-pix_fmt", "rgba", str(tmp)], check=True)
        im = Image.open(tmp).convert("RGBA").resize((round(W * k), round(H * k)), Image.LANCZOS)
        tmp.unlink()
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.paste(im, (round(px - W * k / 2), round(py - H * k / 2)), im)
        canvas.save(out)
    return out.name


def narrator_renders(plan):
    """R248 round 6: the narrator's HeyGen renders (plan narrator.renders: one transparent WebM a card segment, in
    order, each lip-synced to its upload with AVATAR_PAD_S of silence each side) as 30 fps ProRes 4444 with alpha:
    the web app's edge colour divided out twice (alpha.PREMULTIPLIED "webapp"), then 25 fps made 30 by time (fps=30,
    frames repeated where the times fall). Also her widest reach across every frame (sampled at 5 fps), offset as
    placed: narrator/narrator.json. Returns {segment n: (mov path, frames)} and the reach box."""
    import numpy as np
    from pipeline.edit import alpha
    nar = plan["narrator"]
    d = reel_dir(plan)
    (d / "narrator").mkdir(exist_ok=True)
    fps, W, H = fps_of(plan), plan["width"], plan["height"]
    k, (px, py) = narrator_place(plan)
    out, box = {}, None
    nj = d / "narrator" / "narrator.json"                       # (every frame's alpha, read once: Fable N7)
    cache = json.loads(nj.read_text(encoding="utf-8")).get("boxes", {}) if nj.exists() else {}
    for n, src in enumerate(nar["renders"], 1):
        src = Path(src)
        st = src.stat()
        h = hashlib.sha256(f"{src}|{st.st_size}|{st.st_mtime_ns}|{alpha.PREMULTIPLIED['webapp']}|{fps}".encode()).hexdigest()[:8]
        mov = d / "narrator" / f"narrator_{n}_{h}.mov"
        if not mov.exists():
            tmp = d / "narrator" / f"_25_{mov.name}"
            alpha.to_prores(src, tmp, fix=True, premultiplied=alpha.PREMULTIPLIED["webapp"])
            subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(tmp), "-vf", f"fps={fps}", "-an",
                            "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-alpha_bits", "16",
                            "-vendor", "apl0", str(mov)], check=True)
            tmp.unlink()
        key = f"{mov.name}|{k}|{px}|{py}|clamped"
        if key in cache:
            b = cache[key]
            box = b if box is None else [min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3])]
            out[n] = (mov, reel.video_frames(mov))
            continue
        p_ = subprocess.Popen([tool("ffmpeg"), "-v", "error", "-i", str(mov), "-vf", "alphaextract,format=gray",
                               "-f", "rawvideo", "-"], stdout=subprocess.PIPE)         # every frame, one at a time
        a = np.zeros((H, W), bool)
        while True:
            buf = p_.stdout.read(W * H)
            if len(buf) < W * H:
                break
            a |= np.frombuffer(buf, np.uint8).reshape(H, W) > 16
        p_.wait()
        ys, xs = np.nonzero(a)                                  # (the far edges are max + 1)
        b = place_box([int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1], k, (px, py), W, H)
        cache[key] = b
        box = b if box is None else [min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3])]
        out[n] = (mov, reel.video_frames(mov))
    (d / "narrator" / "narrator.json").write_text(json.dumps({"reach_box": box, "scale": k, "centre_px": [px, py],
        "plan_digest": plan_digest(plan), "boxes": cache, "renders": {
        n: {"mov": str(m), "frames": f} for n, (m, f) in out.items()}}, indent=1), encoding="utf-8")
    return out, box


def avatar_uploads(plan):
    """R248 step 3: the narrator's HeyGen render as pip_render plans one: a segment per run of card beats (where the
    still stands now), each upload the leveled narration placed at its own times in the segment with AVATAR_PAD_S of
    silence each side, mono 48 kHz; avatar_upload/uploads.json says where each segment starts on the reel (the render
    then goes on the Narrator track from start - pad) and its credits by engine. Nothing is sent."""
    import numpy as np
    import wave
    d, fps = reel_dir(plan), fps_of(plan)
    au = json.loads((d / "audio" / "audio.json").read_text(encoding="utf-8"))
    if au.get("plan_digest") != plan_digest(plan):
        raise SystemExit("audio.json and the plan aren't the same version: run audio again")
    tl = {"beats": [{"id": b["beat"]["id"], "f0": b["f0"], "n": b["n"], "lines": [{"id": x["id"], "at": x["at"]}
                                                                              for x in b["lines"]]}
                    for b in timeline(plan)]}       # (from the plan, not timeline.json: xml needs the renders first)
    segs = card_segments(plan, tl["beats"])
    rates = dict(CREDITS_PER_MIN, **((plan.get("narrator") or {}).get("credits_per_min") or {}))
    out = d / "avatar_upload"
    out.mkdir(exist_ok=True)
    sr, pad = 48000, int(AVATAR_PAD_S * 48000)
    for i, sg in enumerate(segs, 1):
        n = round((sg["end"] - sg["start"]) / fps * sr) + 2 * pad
        mix = np.zeros(n, np.float64)
        for b in tl["beats"]:
            if b["id"] not in sg["beats"]:
                continue
            for ln in b["lines"]:
                with wave.open(au["narration"][ln["id"]], "rb") as w:
                    x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float64) / 32768
                at = pad + round((ln["at"] - sg["start"]) / fps * sr)
                mix[at:at + len(x)] += x[:max(0, n - at)]
        p = out / f"segment{i}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
        secs = n / sr
        sg.update({"file": str(p), "seconds": round(secs, 2), "on_reel_from_s": round(sg["start"] / fps - AVATAR_PAD_S, 3),
                   "credits": {k: round(secs / 60 * v, 1) for k, v in rates.items()},
                   "plan_usd": {k: round(secs / 60 * v * PLAN_USD_PER_CREDIT, 2) for k, v in rates.items()}})
    nar = plan.get("narrator")                                  # round 2's narrator isn't David (R248)
    look = nar.get("look", "the narrator's avatar, still to be chosen") if nar else "David Baldwin"
    doc = {"note": f"R248 step 3: not sent. Render each segment on the look '{look}' (transparent WebM, the "
                   "web app as R244's renders), then place it on the Narrator track from on_reel_from_s, scaled and "
                   "placed as the still (the stage's left-third pose: 75% about the bottom centre, 636 px left).",
           "segments": segs, "total_s": round(sum(s["seconds"] for s in segs), 2),
           "credits": {k: round(sum(s["credits"][k] for s in segs), 1) for k in rates},
           "plan_usd": {k: round(sum(s["plan_usd"][k] for s in segs), 2) for k in rates}}
    (out / "uploads.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return doc


def footage_missing(plan, mp4, tl=None):
    """Times (s) where an export doesn't show its footage: each picture shot's middle frame, its window (or the whole
    frame) inside a 10% margin, against the media's own frame, both 64 x 36 grey; a mean difference over 40 of 255
    means the clip didn't draw (round 3: Premiere exported the standalone with empty windows from 24 to 75 s and no
    Media pending card, its media not loaded yet)."""
    import numpy as np
    fps, W, H = fps_of(plan), plan["width"], plan["height"]
    tl = tl or timeline(plan)

    def grey(path, t, box):
        x, y, w, h = box
        mx, my = round(w * 0.1), round(h * 0.1)
        raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-ss", f"{max(0.0, t - 0.5 / fps):.4f}", "-i", str(path),
                              "-frames:v", "1", "-vf", f"scale={W}:{H},crop={w - 2 * mx}:{h - 2 * my}:{x + mx}:{y + my},"
                              "scale=64:36,format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.uint8).astype(float)

    win = reel.window(plan)
    out = []
    for b in tl:
        for sh in b["shots"]:
            if not sh["vlen"] or sh["vlen"] <= 2 * round(sh["shot"].get("fade_s", 0) * fps) + 2:
                continue                                            # (a faded shot's middle is at full opacity)
            mid = sh["vlen"] // 2
            box = (win["x"], win["y"], win["w"], win["h"]) if b["beat"]["layout"] == "frame" else (0, 0, W, H)
            got = grey(mp4, (sh["at"] + mid) / fps, box)
            want = grey(sh["path"], (sh["src0"] + mid) / fps, (0, 0, W, H))
            if float(np.abs(got - want).mean()) > 40:
                out.append(round((sh["at"] + mid) / fps, 2))
    return out


def pending(mp4, fps=30):
    """Seconds (every frame) where an export shows Premiere's "Media pending" card (exports.pending_frames' test: a
    yellow field over most of a 64 x 36 scan)."""
    import numpy as np
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(mp4), "-vf", "scale=64:36", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, 36, 64, 3).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    hit = (((r > 120) & (g > 0.85 * r) & (g < r) & (b < 0.5 * g)).mean(axis=(1, 2)) > 0.6)
    return [round(i / fps, 3) for i in np.nonzero(hit)[0]]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["nocap", "audio", "layers", "xml", "build", "export", "all", "uploads", "adopt"])
    ap.add_argument("--suffix", default="", help="export: a suffix for the mp4s, exports<suffix>.json and the frames "
                    "(empty, or like _r6b)")
    ap.add_argument("--why", default="", help="adopt (required): what changed in the project, now in the plan")
    ap.add_argument("plan")
    ap.add_argument("--frames", help="comma-separated seconds for Premiere's own single frames (export)")
    a = ap.parse_args(argv)
    check_suffix(a.suffix)
    plan = reel.load(a.plan)
    fr = [float(x) for x in a.frames.split(",")] if a.frames else ()
    if a.cmd in ("audio", "all"):
        audio(plan)
    if a.cmd in ("layers", "all"):
        print(json.dumps(layers(plan), indent=1))
    if a.cmd in ("xml", "all"):
        build_xml(plan)
    if a.cmd in ("build", "all"):
        build(plan)
    if a.cmd in ("export", "all"):
        print(json.dumps(export(plan, fr, a.suffix), indent=1))
    if a.cmd == "adopt":
        print(json.dumps(adopt(plan, a.why), indent=1))
    if a.cmd == "uploads":
        print(json.dumps(avatar_uploads(plan), indent=1))
    if a.cmd == "nocap":
        nocap(plan)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
