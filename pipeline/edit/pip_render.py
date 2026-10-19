"""The avatar's renders behind the picture-in-picture box (R100, R205, R229, R231): from a placement (pipeline.edit.pip's
pip_spans.json), which stretches of the approved sequence need the avatar's video, the segments HeyGen renders them in,
their plan credits, and each segment's upload audio, built from the approved sequence's own voice clips. Nothing here
calls HeyGen: the renders wait for David's go on the look (R229).

    python -m pipeline.edit.pip_render plan runs/<run_id>/<pip folder> <approved review folder>
                                       --steps=exercises/<ex>/avatar_<prefix>.json [--out=<pip folder>/avatar_iv_plan.json]
    python -m pipeline.edit.pip_render audio <plan.json> <out_dir> [--only=IV-01,...] [--handle-audio=silence]
    python -m pipeline.edit.pip_render verify <out_dir> <reference>@<main-body seconds> [...] [--win=2]

The plan:
  * a stretch is a run of the box's stays joined by moves: the avatar's video is needed on every frame of it, fades
    included. At a move the old stay's last frame is its fade out's last (pipeline.edit.pip review_xml's keys) and the
    new stay's first frame shows nothing (its fade in starts at 0), so two renders can join there unseen: a move is a
    free cut, a stay is not;
  * each render carries HANDLE_S more on both sides (R100's 1.5 s: real frames for a fade moved later, never a held one);
  * stretches whose hidden gap is under twice HANDLE_S share one render (MERGE_GAP_S): their handles would overlap, so
    one render through the gap is shorter than two; at 3 s or more two renders are no longer (the rule: merge when the
    gap is under 3 s);
  * a render longer than MAX_SEGMENT_S is cut at a move or at a merged gap (greedy: each piece as long as it may be),
    so its upload WAV (48 kHz mono 16-bit, 5.76 MB a minute) stays under HeyGen's 32 MB asset limit with room, well
    inside the API's 10 minutes of audio per render and Pro's 30-minute videos (research/heygen_plan/RESEARCH.md [LIM],
    [P]); a stay longer than that would need a cut in view, and stops the plan;
  * the hand-over from the intro (R205, R231): the intro's oval goes on as the box, so a change of render during the
    box's first stay would show as a jump. The intro's render carries the main body's audio from its first line to the
    end of that first stay plus HANDLE_S, and the main body's renders take over at the first stay's end, unseen. The
    outro's oval takes over from a hidden box (handover.box_up_at_end false); a box up at the end is reported, since
    the outro's render would then have to carry the main body's end the same way;
  * credits: CREDITS_PER_MIN on a HeyGen plan ([U]: Avatar IV 31 a minute, V 48, III 4), billed by the second
    ([A], the API's rule; the plan's own rounding is unpublished, so each segment is also shown rounded up to a whole
    credit).
A segment's upload audio is the main body's own sound over its frames: the approved sequence's narration clips (its XML:
the camera sequence's Narration track) placed at their frames as Premiere plays them (whole frames, 1600 samples each
at 48 kHz). The handles hold R100's silence (handle_audio "silence", the default since R236): the avatar idles there,
mouth closed, so a stay lengthened into a handle can be faded out; "timeline" keeps the timeline's own audio there
instead (a stay lengthened into a handle stays lip-synced).
Placing a render back: Avatar IV renders come back at 25 fps from the web app (research/heygen_plan/
SAMPLE_PHOTOLOOK_r1.md), so place them by time (render second t is main-body second start + t; the lengths match to
the millisecond), not by frame, or resample them to the sequence's rate first.
"""
import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from pipeline.config import EXERCISES, tool
from pipeline.edit.avatar import CACHE, PAD_S, padded
from pipeline.narration import clean

HANDLE_S = PAD_S                    # R100: 1.5 s of spare footage on both sides of every render
MERGE_GAP_S = 2 * HANDLE_S          # two stretches closer than this share one render
MAX_SEGMENT_S = 300.0               # a render's length at most (its WAV under 32 MB with room)
UPLOAD_MAX_BYTES = 32_000_000       # HeyGen's asset upload limit ([LIM]: "Maximum file size: 32 MB")
CREDITS_PER_MIN = {"avatar_iii": 4, "avatar_iv": 31, "avatar_v": 48}   # a digital twin on a plan ([U])
PLAN_CREDITS = 1000                 # David's Pro plan, a month (R229)
ENGINE_NAMES = {"avatar_iii": "Avatar III", "avatar_iv": "Avatar IV", "avatar_v": "Avatar V"}


def tc(f, fps):
    f, r = int(round(f)), int(round(fps))
    return f"{f // (3600 * r):02d}:{f // (60 * r) % 60:02d}:{f // r % 60:02d}:{f % r:02d}"


def credits(seconds, engine):
    return seconds / 60 * CREDITS_PER_MIN[engine]


# ------------------------------------------------------------------------------------------------- the plan
def stretches(spans):
    """Runs of shown spans joined by moves: [{"f0", "f1", "moves": [frames where one stay ends and the next begins],
    "stays": [(spot, f0, f1)]}], frames end exclusive."""
    out = []
    for s in spans:
        if s["spot"] == "hidden":
            continue
        if out and out[-1]["f1"] == s["f0"]:
            out[-1]["moves"].append(s["f0"])
            out[-1]["f1"] = s["f1"]
        else:
            out.append({"f0": s["f0"], "f1": s["f1"], "moves": []})
            out[-1]["stays"] = []
        out[-1]["stays"].append((s["spot"], s["f0"], s["f1"]))
    return out


def _cut(group, H, max_f):
    """A render group (stretches sharing one render) cut into pieces of at most max_f frames, handles included, at
    moves (each piece keeps H past the move) or at the hidden gaps inside the group; greedy, each piece as long as it
    may be. Returns [(F0, F1, cut_before, cut_after)]: a piece's frames and what joins it to its neighbours."""
    a0, a1 = group[0]["f0"] - H, group[-1]["f1"] + H
    cuts = []                                         # (end of the piece before, start of the piece after, what)
    for k, st in enumerate(group):
        cuts += [(m + H, m - H, ("move", m)) for m in st["moves"]]
        if k + 1 < len(group):
            cuts.append((st["f1"] + H, group[k + 1]["f0"] - H, ("gap", st["f1"], group[k + 1]["f0"])))
    pieces, start, before = [], a0, None
    while a1 - start > max_f:
        ok = [c for c in cuts if c[1] > start and c[0] - start <= max_f]
        if not ok:
            raise SystemExit(f"no move or gap lets a render from frame {start} stay under {max_f} frames: a cut there "
                             "would show (split a stay first)")
        c = max(ok, key=lambda c: c[0])
        pieces.append((start, c[0], before, c[2]))
        start, before = c[1], c[2]
    pieces.append((start, a1, before, None))
    return pieces


def plan_renders(doc, fps=None, first_line_f=0, engine="avatar_iv", handle_s=HANDLE_S, max_s=MAX_SEGMENT_S):
    """The main body's renders for a placement (pip_spans.json's doc): {"stretches", "carry", "segments",
    "warnings"}. carry: the part of the main body the intro's render carries (main-body frames from the first line,
    first_line_f, to the end of the box's first stay plus the handle), or None when the box isn't up at frame 0."""
    fps = fps or doc["fps"]
    N, H, max_f = doc["frames"], round(handle_s * fps), round(max_s * fps)
    spans, st = doc["spans"], stretches(doc["spans"])
    warnings, carry = [], None
    if st and st[0]["f0"] == 0:                       # the intro's oval goes on as the box (R231)
        first = st[0]
        end = first["stays"][0][2]                    # the first stay's end: its fade out is over
        carry = {"f0": first_line_f, "f1": min(N, end + H), "box_f1": end,
                 "why": "the intro's oval goes on as the box (R231); a render change while it shows would jump"}
        if first["moves"] and first["moves"][0] == end:
            first["f0"], first["moves"] = end, first["moves"][1:]
            first["stays"] = first["stays"][1:]
            first["after_carry"] = True
        else:
            st = st[1:]
    groups = []
    for s in st:
        if groups and s["f0"] - groups[-1][-1]["f1"] < round(MERGE_GAP_S * fps):
            groups[-1].append(s)
        else:
            groups.append([s])
    segs = []
    for g in groups:
        for F0, F1, before, after in _cut(g, H, max_f):
            first_after_carry = g[0].get("after_carry") and F0 == g[0]["f0"] - H
            F0c, F1c = max(0, F0), min(N, F1)
            if F1c < F1:
                warnings.append(f"a render ends at the main body's end ({tc(N, fps)}) with {(N - (F1 - H)) / fps:.2f} s "
                                f"of its {handle_s} s handle")
            if F1 - H >= N and doc.get("handover", {}).get("box_up_at_end"):
                warnings.append("the box is up at the main body's end: the outro's render would have to carry the "
                                "main body's end, as the intro's carries its start (not planned)")
            stays = [(sp, max(a, F0 + (H if before else 0)), min(b, F1 - (H if after else 0)))
                     for gg in g for sp, a, b in gg["stays"] if a < F1 and b > F0]
            stays = [(sp, a, b) for sp, a, b in stays if a < b]
            visible = sum(b - a for _, a, b in stays)
            segs.append({"f0": F0c, "f1": F1c, "stays": stays, "visible_f": visible,
                         "joins": {"before": _join(before, fps, "start") if before else
                                   ("the intro's render, at the end of the box's first stay (unseen)"
                                    if first_after_carry else "a hidden stretch"),
                                   "after": _join(after, fps, "end") if after else "a hidden stretch"}})
    for i, s in enumerate(segs):
        s.update({"id": f"{ENGINE_NAMES[engine].split()[-1]}-{i + 1:02d}", "engine": engine,
                  "start": round(s["f0"] / fps, 4), "end": round(s["f1"] / fps, 4), "start_tc": tc(s["f0"], fps),
                  "end_tc": tc(s["f1"], fps), "length_s": round((s["f1"] - s["f0"]) / fps, 3),
                  "visible_s": round(s.pop("visible_f") / fps, 3),
                  "credits": round(credits((s["f1"] - s["f0"]) / fps, engine), 2),
                  "credits_whole": math.ceil(credits((s["f1"] - s["f0"]) / fps, engine) - 1e-9),
                  "stays": [{"spot": sp, "f0": a, "f1": b, "start_tc": tc(a, fps), "end_tc": tc(b, fps)}
                            for sp, a, b in s["stays"]]})
        s.update({"upload_bytes": 44 + (s["f1"] - s["f0"]) * round(clean.SR / fps) * 2})
        if s["upload_bytes"] > UPLOAD_MAX_BYTES:
            warnings.append(f"{s['id']}: its WAV would be {s['upload_bytes'] / 1e6:.1f} MB, over HeyGen's 32 MB")
    out_st = [{"f0": s["f0"], "f1": s["f1"], "start_tc": tc(s["f0"], fps), "end_tc": tc(s["f1"], fps),
               "moves": len(s["moves"]), "length_s": round((s["f1"] - s["f0"]) / fps, 3)} for s in stretches(spans)]
    return {"stretches": out_st, "carry": carry, "segments": segs, "warnings": warnings}


def _join(c, fps, side):
    if c[0] == "move":
        return f"a move at {tc(c[1], fps)}: the next render takes over unseen, {HANDLE_S} s overlapping"
    return f"a hidden gap {tc(c[1], fps)} to {tc(c[2], fps)} split between two renders"


def intro_outro(steps_doc, lines, plan, carry, fps, intro_engine="avatar_v", outro_engine="avatar_iv"):
    """The intro's and the outro's renders as avatar.py uploads them (padded: PAD_S of silence, the line, PAD_S; the
    intro then the gap and the main body's carried audio, R205), their lengths and credits."""
    pace = plan["settings"]["pacing"]
    gap = round(pace["gap_between_lines"] + pace["pause_at_part_boundary"], 3)          # R82, as main_alpha
    out = {}
    names = {"opening": "intro", "recap": "outro"}
    for st in steps_doc["steps"]:
        seq, line = st["graphics"], lines[st["narration"]["line_id"]]
        if seq not in names or names[seq] in out:
            raise SystemExit(f"the steps file's graphics {seq!r}: one opening and one recap expected")
        parts = [{"what": "silence (R100)", "s": PAD_S},
                 {"what": "the line", "line_id": st["narration"]["line_id"], "key": line["key"], "s": line["length_s"]}]
        if seq == "opening":
            engine = intro_engine
            if carry:
                parts += [{"what": "the gap (R82)", "s": gap},
                          {"what": "the main body's own audio, carried (R205, R231)", "from_f": carry["f0"],
                           "to_f": carry["f1"], "box_to_f": carry["box_f1"], "from_tc": tc(carry["f0"], fps),
                           "to_tc": tc(carry["f1"], fps), "s": round((carry["f1"] - carry["f0"]) / fps, 3)}]
            else:                                      # no box at frame 0: the intro as avatar.py renders it
                parts.append({"what": "silence (R100)", "s": PAD_S})   # (its carried sentence not counted here)
        else:
            engine = outro_engine
            parts.append({"what": "silence (R100)", "s": PAD_S})
        length = round(sum(p["s"] for p in parts), 3)
        out[names[seq]] = {
            "graphics": seq, "engine": engine, "parts": parts, "length_s": length,
            "credits": round(credits(length, engine), 2), "credits_whole": math.ceil(credits(length, engine) - 1e-9)}
    return out


def totals(segs, intro, outro, engine="avatar_iv"):
    """Section-sized sums and what the Pro plan's credits a month cover."""
    r = sum(s["length_s"] for s in segs)
    main = {"segments": len(segs), "rendered_s": round(r, 1), "rendered_min": round(r / 60, 2),
            "visible_s": round(sum(s["visible_s"] for s in segs), 1),
            "credits": round(credits(r, engine), 1), "credits_whole": sum(s["credits_whole"] for s in segs)}
    video = round(main["credits"] + intro["credits"] + outro["credits"], 1)
    whole = main["credits_whole"] + intro["credits_whole"] + outro["credits_whole"]
    return {"main_body": main, "intro": {k: intro[k] for k in ("engine", "length_s", "credits")},
            "outro": {k: outro[k] for k in ("engine", "length_s", "credits")},
            "video_credits": video, "video_credits_whole": whole,
            "pro_plan": {"credits_a_month": PLAN_CREDITS, "videos_a_month": int(PLAN_CREDITS // whole),
                         "left_after_those": PLAN_CREDITS - int(PLAN_CREDITS // whole) * whole}}


def plan_main(pip_dir, approved_dir, steps, out=None, intro_engine="avatar_v", outro_engine="avatar_iv",
              engine="avatar_iv", max_s=MAX_SEGMENT_S):
    pip_dir, approved_dir = Path(pip_dir).resolve(), Path(approved_dir).resolve()
    doc = json.loads((pip_dir / "pip_spans.json").read_text(encoding="utf-8"))
    run_dir = pip_dir.parent
    while not (run_dir / "edit_plan.json").exists():
        if run_dir.parent == run_dir:
            raise SystemExit(f"no edit_plan.json above {pip_dir}")
        run_dir = run_dir.parent
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    fps = doc["fps"]
    clips = voice_clips(approved_dir, plan["run_id"])
    check_against_plan(clips, plan)
    first_line_f = min(c["start"] for c in clips)
    r = plan_renders(doc, fps, first_line_f, engine, max_s=max_s)
    steps_doc = json.loads(Path(steps).read_text(encoding="utf-8"))
    lines = json.loads((EXERCISES / steps_doc["exercise"] / "lines.json").read_text(encoding="utf-8"))
    io = intro_outro(steps_doc, lines, plan, r["carry"], fps, intro_engine, outro_engine)
    res = {"about": "The avatar's renders behind the picture-in-picture box (pipeline.edit.pip_render): every frame the "
                    "box shows on the approved sequence comes from one segment (a render), each with R100's handles; "
                    "the intro's render carries the box's first stay (R205, R231). Frames and times on the approved "
                    "sequence; a segment's render second t is the main body's second start + t (Avatar IV renders "
                    "come back at 25 fps: place them by time, or resample to the sequence's rate first).",
           "placement": str(pip_dir / "pip_spans.json"), "approved": approved_dir.name,
           "approved_dir": str(approved_dir), "run_dir": str(run_dir), "steps": str(Path(steps).resolve()),
           "fps": fps, "frames": doc["frames"], "main_body_s": round(doc["frames"] / fps, 3),
           "box_shown_s": doc["stats"]["shown_s"], "box_shown_pct": doc["stats"]["shown_pct"],
           "rules": {"handle_s": HANDLE_S, "merge_when_gap_under_s": MERGE_GAP_S, "max_segment_s": max_s,
                     "split_at": "a move (unseen: the fades meet at a frame showing nothing) or a merged gap",
                     "credits_per_min": CREDITS_PER_MIN, "engine": engine, "plan_credits_a_month": PLAN_CREDITS,
                     "upload": "WAV, 48 kHz mono 16-bit, under 32 MB; the main body's own audio over the frames",
                     "handles": f"{HANDLE_S} s of silence at both ends (R236: `audio --handle-audio=silence`, the "
                                "default); merged gaps inside a render keep the timeline's audio"},
           **r, "intro": io["intro"], "outro": io["outro"],
           "totals": totals(r["segments"], io["intro"], io["outro"], engine)}
    out = Path(out) if out else pip_dir / "avatar_iv_plan.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res, out


# ------------------------------------------------------------------------------------------------- the audio
def voice_clips(approved_dir, run):
    """The approved sequence's narration as Premiere plays it: [{"name", "file", "start", "end", "in", "out"}] in
    main-body frames, from its XML (the camera sequence's Narration track, nested in "<run> full" at frame 0)."""
    (xml,) = [p for p in Path(approved_dir).glob("*_full.xml") if p.name != "captions_full.xml"]
    root = ET.parse(xml).getroot()
    files = {f.get("id"): Path(unquote(re.sub(r"^file://localhost/", "", f.findtext("pathurl"))))
             for f in root.iter("file") if f.findtext("pathurl")}
    seqs = {s.findtext("name"): s for s in root.iter("sequence")}
    full, cam = seqs.get(f"{run} full"), seqs.get(f"{run} camera")
    if full is None or cam is None:
        raise SystemExit(f"{xml}: no sequences {run} full and {run} camera")
    nests = [c for t in full.find("media/audio").findall("track") for c in t.findall("clipitem")
             if c.findtext("name") == f"{run} camera"]
    if not nests or {int(c.findtext("start")) - int(c.findtext("in")) for c in nests} != {0}:
        raise SystemExit(f"{xml}: the camera sequence isn't nested at frame 0 of the full one")
    tracks = [t for t in cam.find("media/audio").findall("track") if t.get("MZ.TrackName") == "Narration"]
    if len(tracks) != 1:
        raise SystemExit(f"{xml}: {len(tracks)} Narration tracks in {run} camera")
    out = []
    for c in tracks[0].findall("clipitem"):
        if c.findtext("enabled") == "FALSE":
            continue
        s, e, i, o = (int(c.findtext(k)) for k in ("start", "end", "in", "out"))
        if e - s != o - i:
            raise SystemExit(f"{xml}: {c.findtext('name')} plays at another speed")
        out.append({"name": c.findtext("name"), "file": files[c.find("file").get("id")], "start": s, "end": e,
                    "in": i, "out": o})
    out.sort(key=lambda c: c["start"])
    for a, b in zip(out, out[1:]):
        if b["start"] < a["end"]:
            raise SystemExit(f"{xml}: {a['name']} and {b['name']} overlap")
    return out


def check_against_plan(clips, plan):
    """The XML's clips are the plan's narration parts: start and in the plan's rounded to a whole frame, out within a
    frame or so (a clip ends within its file's whole frames)."""
    fps = plan["fps"]
    parts = sorted((p["at"], p["in"], p["out"], n["line_id"]) for n in plan["narration"] for p in n["parts"])
    if len(parts) != len(clips):
        raise SystemExit(f"the approved sequence has {len(clips)} narration clips, its plan {len(parts)} parts")
    for (at, i, o, lid), c in zip(parts, clips):
        if c["name"] != lid or any(abs(c[k] - v * fps) > lim + 1e-6
                                   for k, v, lim in (("start", at, 0.5), ("in", i, 0.5), ("out", o, 1.5))):
            raise SystemExit(f"{c['name']} at frame {c['start']} (its frames {c['in']} to {c['out']}) isn't the plan's "
                             f"{lid} at {at} s ({i} to {o} s)")


def timeline_audio(clips, f0, f1, fps, decoded):
    """The main body's narration over frames f0..f1 (mono, clean.SR), each clip placed at its frames, as Premiere
    plays it. decoded: a cache of the clips' samples by file."""
    spf = clean.SR / fps
    if spf != int(spf):
        raise SystemExit(f"{fps} fps doesn't divide {clean.SR} Hz")
    spf = int(spf)
    x = np.zeros((f1 - f0) * spf, np.float32)
    for c in clips:
        a, b = max(c["start"], f0), min(c["end"], f1)
        if a >= b:
            continue
        if c["file"] not in decoded:
            decoded[c["file"]] = clean.decode(c["file"])
        y = decoded[c["file"]]
        s0 = (c["in"] + a - c["start"]) * spf
        seg = y[s0:s0 + (b - a) * spf]
        x[(a - f0) * spf:(a - f0) * spf + len(seg)] += seg
    return x


def edge_fade(x, sr=clean.SR):
    """A short ramp at both ends, so a cut through a word doesn't click (EDGE_FADE_S, as the cleaned clips)."""
    n = min(len(x) // 2, int(clean.EDGE_FADE_S * sr))
    if n:
        r = np.linspace(0, 1, n, dtype=np.float32)
        x[:n] *= r
        x[-n:] *= r[::-1]
    return x


def build_audio(plan_path, out_dir, only=None, handle_audio="silence"):
    """Every segment's upload WAV (and the intro's and outro's, as avatar.py builds them, with the intro carrying the
    main body's own audio) into out_dir: [{"id", "file", "length_s", "samples", "expected_samples", "bytes", "maps"}],
    maps: [(seconds into the WAV, main-body seconds, length)] of main-body audio, for verify; listed in
    out_dir/manifest.json with the plan and the handle audio they were built with (verify reads it)."""
    p = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    fps = p["fps"]
    spf = int(clean.SR / fps)
    ex = json.loads(Path(p["steps"]).read_text(encoding="utf-8"))["exercise"]
    plan = json.loads((Path(p["run_dir"]) / "edit_plan.json").read_text(encoding="utf-8"))
    clips = voice_clips(p["approved_dir"], plan["run_id"])
    check_against_plan(clips, plan)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    decoded, built = {}, []
    for s in p["segments"]:
        if only and s["id"] not in only:
            continue
        x = timeline_audio(clips, s["f0"], s["f1"], fps, decoded)
        if handle_audio == "silence":                 # R100's silence in the handles (R236); merged gaps keep the timeline
            a, b = min(st["f0"] for st in s["stays"]), max(st["f1"] for st in s["stays"])
            x[:(a - s["f0"]) * spf] = 0
            x[(b - s["f0"]) * spf:] = 0
        dst = out_dir / f"{s['id']}_{s['start_tc'].replace(':', '')}.wav"
        clean.write_wav(dst, edge_fade(x))
        built.append({"id": s["id"], "file": str(dst), "samples": len(x), "expected_samples": (s["f1"] - s["f0"]) * spf,
                      "length_s": round(len(x) / clean.SR, 4), "bytes": dst.stat().st_size,
                      "maps": [(0.0, s["start"], s["length_s"])]})
    lines = json.loads((EXERCISES / ex / "lines.json").read_text(encoding="utf-8"))
    for k in ("intro", "outro"):
        if only and k not in only:
            continue
        r = p[k]
        line = lines[r["parts"][1]["line_id"]]
        dst = out_dir / f"{k}_upload.wav"
        base, info = padded(CACHE / f"{line['key']}.mp3", dst)            # PAD_S, the cleaned line, PAD_S
        x = clean.decode(base)
        maps = []
        if any(q["what"].startswith("the main body") for q in r["parts"]):   # R205: [z, line, gap, carry]
            gap, carry = r["parts"][2], r["parts"][3]
            head = x[:len(x) - int(PAD_S * clean.SR)]                          # padded's trailing silence off
            body = timeline_audio(clips, carry["from_f"], carry["to_f"], fps, decoded)
            if handle_audio == "silence":             # the carry's handle after the box's first stay, as above
                body[(carry["box_to_f"] - carry["from_f"]) * spf:] = 0
            body = edge_fade(body)
            at = len(head) + int(round(gap["s"] * clean.SR))
            x = np.concatenate([head, np.zeros(at - len(head), np.float32), body])
            clean.write_wav(dst, x)
            maps = [(at / clean.SR, carry["from_f"] / fps, carry["s"])]
        built.append({"id": k, "file": str(dst), "samples": len(x), "expected_samples": int(round(r["length_s"] * clean.SR)),
                      "tolerance": clean.SR // 2000 + 1,     # lines.json rounds a line's length to the millisecond
                      "length_s": round(len(x) / clean.SR, 4), "bytes": dst.stat().st_size, "maps": maps,
                      "voice_s": info["voice_s"]})
    (out_dir / "manifest.json").write_text(json.dumps({"plan": str(Path(plan_path).resolve()), "handle_audio":
                                                      handle_audio, "built": built}, indent=1), encoding="utf-8")
    return built


# ------------------------------------------------------------------------------------------------- the ovals
OVAL_MAX_PAD = 2                    # render frames a segment may lack at its end (HeyGen rounds its frame count down;
                                    # those frames are in the silent handle): its last frame repeated, and recorded
PERSON_SPREAD_PX = 24               # the renders' person centres within this of their median (one look, one framing)
PERSON_CROSS_PX = 20                # a render's median head column within this of its widest head run's centre
PERSON_RUN_MAX_PX = 500             # and that run (the head's columns) no wider than this, else the mask isn't a head
PERSON_REF_PX = 40                  # the renders' centre within this of the still's (the oval's reference framing)
OVALS_VERSION = 1                   # in each oval clip's name: a change to how they are made makes new files


def render_of(renders, seg_id):
    """A segment's render in the renders folder (<id>_*.mp4, as the web-app script saves them): exactly one."""
    got = sorted(Path(renders).glob(f"{seg_id}_*.mp4"))
    if len(got) != 1:
        raise SystemExit(f"{renders}: {len(got)} renders named {seg_id}_*.mp4, one expected")
    return got[0]


def video_info(path):
    """A video's frame rate (a float), frame count and size, from its stream."""
    import subprocess
    s = json.loads(subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=r_frame_rate,nb_frames,width,height", "-of", "json", str(path)],
                                  capture_output=True, text=True, check=True).stdout)["streams"][0]
    a, b = (int(x) for x in s["r_frame_rate"].split("/"))
    return {"fps": a / b, "frames": int(s["nb_frames"]), "width": s["width"], "height": s["height"]}


def _rgb(path, t, W, H):
    """One frame of an HD render at t s, as RGB (BT.709, as Premiere reads HD H.264)."""
    import subprocess
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-vf",
                          f"scale={W}:{H}:in_color_matrix=bt709", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    if len(raw) != W * H * 3:
        raise SystemExit(f"no frame at {t:.2f} s in {path}")
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3)


def person_x_of(path, W, H, room=None, times=(0.2, 0.35, 0.5, 0.65, 0.8)):
    """The person's centre x in an opaque render on the cityscape (the looks were recorded on it, R232; a web-app render
    shows it behind him within about 3 levels in 256): the median column of the head's rows (the top two fifths of the
    frame) that differ from the cityscape by over 40 levels, over a few frames (times: fractions of its length). The
    mask also catches a few stray background pixels across the frame (Fable, final_r4), so it is checked against the
    widest run of columns holding at least 20 head pixels: the run no wider than PERSON_RUN_MAX_PX and its centre
    within PERSON_CROSS_PX of the median, else a changed background would move every oval off the face unseen."""
    from PIL import Image
    from pipeline.edit import pip
    room = room if room is not None else np.asarray(pip.cover(Image.open(pip.CITY).convert("RGB"), W, H), np.float32)
    n = video_info(path)
    xs, cols = [], np.zeros(W, int)
    for u in times:
        f = _rgb(path, u * n["frames"] / n["fps"], W, H).astype(np.float32)
        head = np.abs(f[: H * 2 // 5] - room[: H * 2 // 5]).mean(axis=2) > 40
        xs.append(np.nonzero(head)[1])
        cols += head.sum(axis=0)
    xs = np.concatenate(xs)
    if not len(xs):
        raise SystemExit(f"no person found in {path} against the cityscape")
    med = float(np.median(xs))
    on = np.flatnonzero(cols >= 20 * len(times))
    runs = np.split(on, np.flatnonzero(np.diff(on) > 1) + 1) if len(on) else []
    run = max(runs, key=len) if runs else None
    if run is None or len(run) > PERSON_RUN_MAX_PX or abs((run[0] + run[-1]) / 2 - med) > PERSON_CROSS_PX:
        raise SystemExit(f"{path}: the head isn't where the difference from the cityscape says (median x {med:.0f}, "
                         f"widest run {None if run is None else (int(run[0]), int(run[-1]))}): has the background "
                         "changed?")
    return med


def oval_clips(spans_doc, plan_doc, renders, out_dir, W=1920, H=1080, from_f=None, ref_x=None):
    """The picture-in-picture oval's media for a final (R222, R231, R237, R241): for each stay of the placement
    (pip_spans.json's doc) from main-body frame from_f on (default: the end of the box's first stay, which the intro's
    render carries, R237), a frame-sized transparent ProRes 4444 clip of its segment's render (plan_doc: this module's
    plan, avatar_iv_plan.json) seen as pipeline.edit.pip's oval sees the still: the frame at pip.SCALE, cut to the
    feathered ellipse (pip.oval_alpha) centred on the person, at the stay's spot (frame-sized, so Premiere's placement
    can't drift: GOTCHAS). Each clip covers the stay and up to HANDLE_S more on either side inside its render (R100's
    handles: a stay can be lengthened in Premiere), at the sequence's rate, its frame k showing the render's frame that
    contains main-body time (clip_f0 + k) / fps (Avatar IV renders are 25 fps, placed by time: pip_render's rule;
    the frame an editor's timeline shows, not ffmpeg fps's nearest). No sound: the narration is the main body's own.
    One person centre for every render (the median of each render's, one look and one framing), so the oval frames
    him alike at every stay, within PERSON_REF_PX of ref_x (the still's centre, the oval's reference framing) when
    given. Files are named by what made them and reused. Returns the manifest (also out_dir/ovals.json)."""
    import hashlib
    import subprocess
    from PIL import Image
    from pipeline.edit import pip
    fps, N = spans_doc["fps"], spans_doc["frames"]
    if abs(plan_doc["fps"] - fps) > 1e-9 or plan_doc["frames"] != N:
        raise SystemExit("the render plan and the placement are on different sequences")
    H_f = round(HANDLE_S * fps)
    if from_f is None:
        from_f = (plan_doc.get("carry") or {}).get("box_f1", 0)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    room = np.asarray(pip.cover(Image.open(pip.CITY).convert("RGB"), W, H), np.float32)
    segs = plan_doc["segments"]
    stays = [s for s in spans_doc["spans"] if s["spot"] != "hidden" and s["f1"] > from_f]
    if any(s["f0"] < from_f for s in stays):
        raise SystemExit(f"a stay runs across main-body frame {from_f}, where the intro's render hands over")
    used = {}
    for s in stays:
        hit = [g for g in segs if g["f0"] <= s["f0"] and s["f1"] <= g["f1"]]
        if len(hit) != 1:
            raise SystemExit(f"the stay at {s['spot']} {tc(s['f0'], fps)} lies in {len(hit)} renders")
        used.setdefault(hit[0]["id"], hit[0])
    px = {k: person_x_of(render_of(renders, k), W, H, room) for k in used}
    med = float(np.median(list(px.values())))
    far = {k: v for k, v in px.items() if abs(v - med) > PERSON_SPREAD_PX}
    if far:
        raise SystemExit(f"renders framed unlike the rest (person centre vs the median {med:.0f}): {far}")
    if ref_x is not None and abs(med - ref_x) > PERSON_REF_PX:
        raise SystemExit(f"the renders' person centre {med:.0f} is {abs(med - ref_x):.0f} px from the still's {ref_x:.0f}")
    sw, sh = round(W * pip.SCALE), round(H * pip.SCALE)            # as pip.oval_rgba cuts the still
    x0 = min(max(0, round(med * pip.SCALE - pip.OVAL_W / 2)), sw - pip.OVAL_W)
    y0 = round((sh - pip.OVAL_H) / 2)
    alpha = pip.oval_alpha()
    geom = pip.geom_tag(W, H)
    made = []
    for s in stays:
        g = used[next(k for k, v in used.items() if v["f0"] <= s["f0"] and s["f1"] <= v["f1"])]
        path = render_of(renders, g["id"])
        info = video_info(path)
        lo, hi = max(g["f0"], s["f0"] - H_f), min(g["f1"], s["f1"] + H_f)
        src = [int(math.floor((f - g["f0"]) / fps * info["fps"] + 1e-6)) for f in range(lo, hi)]
        pad = max(0, src[-1] + 1 - info["frames"])
        if pad > OVAL_MAX_PAD:
            raise SystemExit(f"{path.name}: {info['frames']} frames, the stay at {tc(s['f0'], fps)} needs {src[-1] + 1}")
        cx, cy = pip.corners(W, H)[s["spot"]]
        ox, oy = cx - pip.OVAL_W // 2, cy - pip.OVAL_H // 2               # as pip.corner_pngs places the still
        st = path.stat()
        key = json.dumps([OVALS_VERSION, path.name, st.st_size, st.st_mtime_ns, g["f0"], lo, hi, s["spot"], round(med, 1),
                          geom, fps], sort_keys=True)
        dst = out_dir / (f"oval_{g['id']}_{s['spot']}_{lo:05d}-{hi:05d}_"
                         f"{hashlib.sha256(key.encode()).hexdigest()[:8]}.mov")
        rec = {"segment": g["id"], "render": str(path), "spot": s["spot"], "f0": s["f0"], "f1": s["f1"],
               "clip_f0": lo, "frames": hi - lo, "file": str(dst.resolve()), "src_frames": [src[0], src[-1]],
               "src_fps": info["fps"], "padded_frames": pad, "person_x": round(med, 1), "fades": pip.fades(s, N)}
        made.append(rec)
        if dst.exists():
            continue
        part = dst.with_name("_part_" + dst.name)
        dec = subprocess.Popen([tool("ffmpeg"), "-v", "error", "-i", str(path), "-an", "-vf",
                                f"scale={sw}:{sh}:flags=lanczos:in_color_matrix=bt709,crop={pip.OVAL_W}:{pip.OVAL_H}:"
                                f"{x0}:{y0}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)      # (stopped once its frames are read: a broken pipe)
        enc = subprocess.Popen([tool("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s",
                                f"{pip.OVAL_W}x{pip.OVAL_H}", "-r", str(fps), "-i", "-", "-vf",
                                f"pad={W}:{H}:{ox}:{oy}:color=black@0,scale=out_color_matrix=bt709:out_range=tv,"
                                "format=yuva444p10le", "-c:v", "prores_ks", "-profile:v", "4444", "-alpha_bits", "16",
                                "-vendor", "apl0", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace",
                                "bt709", "-color_range", "tv", "-an", "-f", "mov", str(part)], stdin=subprocess.PIPE)
        size, cur, buf, n, short = pip.OVAL_W * pip.OVAL_H * 3, -1, None, 0, 0
        try:
            for j in src:
                while cur < j:                         # the render's frames in order, up to the one this frame shows
                    b = dec.stdout.read(size)
                    if len(b) < size:
                        break
                    buf, cur = b, cur + 1
                if cur < j and (buf is None or j - cur > OVAL_MAX_PAD):    # short of what its header says
                    raise SystemExit(f"{path.name}: decoded {cur + 1} frames, the stay needs {src[-1] + 1}")
                short += cur < j                               # the last decoded frame repeated
                rgba = np.dstack([np.frombuffer(buf, np.uint8).reshape(pip.OVAL_H, pip.OVAL_W, 3), alpha])
                enc.stdin.write(rgba.tobytes())
                n += 1
        finally:
            for f in (enc.stdin, dec.stdout):
                try:
                    f.close()
                except OSError:
                    pass
            dec.kill()
            rc = (dec.wait(), enc.wait())
        if rc[1] or n != hi - lo:
            part.unlink(missing_ok=True)
            raise SystemExit(f"{dst.name}: the encoder exited {rc[1]} after {n} of {hi - lo} frames")
        part.replace(dst)
        rec["padded_frames"] = max(pad, short)
    doc = {"about": "pipeline.edit.pip_render.oval_clips: the oval's media per stay (main-body frames; clip_f0 is the "
                    "clip's first frame, the stay f0..f1 inside it)", "person_x": round(med, 1),
           "person_x_by_render": {k: round(v, 1) for k, v in px.items()}, "from_f": from_f, "clips": made}
    man, text = out_dir / "ovals.json", json.dumps(doc, indent=1)
    if not man.exists() or man.read_text(encoding="utf-8") != text:    # unchanged: left as it is (a rebuild of an
        man.write_text(text, encoding="utf-8")                          # approved final touches nothing in ovals/)
    return doc


# ------------------------------------------------------------------------------------------------- the check
def decode_ref(path):
    """A reference mix (Premiere's export: WAV or MP4) as mono samples at clean.SR (left and right averaged)."""
    import subprocess
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(path), "-vn", "-f", "f32le", "-ac", "1", "-ar",
                          str(clean.SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def lag_corr(x, r, max_lag):
    """The lag L (samples, |L| <= max_lag) at which x[t] best matches r[t + max_lag + L], r being x's length plus
    max_lag on both sides, and the normalized correlation there."""
    n = len(r) + len(x)
    nfft = 1 << (n - 1).bit_length()
    c = np.fft.irfft(np.conj(np.fft.rfft(x, nfft)) * np.fft.rfft(r, nfft), nfft)[:2 * max_lag + 1]
    k = int(np.argmax(c))
    seg = r[k:k + len(x)]
    den = math.sqrt(float(np.dot(x, x)) * float(np.dot(seg, seg)))
    return k - max_lag, (float(c[k]) / den if den else 0.0)


def verify(built, refs, win_s=2.0, max_lag_s=0.1, min_rms=0.01):
    """Each built WAV's main-body audio against Premiere's own mix of the approved sequence, window by window
    (win_s): where the WAV has speech (RMS over min_rms), the lag of the best match and its correlation. refs:
    [(samples, main-body seconds of its first sample, name)]. Returns {id: {"windows", "max_abs_lag_ms",
    "min_corr", "median_corr", "ref"}}."""
    SR, out = clean.SR, {}
    ml, w = int(max_lag_s * SR), int(win_s * SR)
    for b in built:
        x = clean.decode(b["file"])
        res = []
        for wav_at, t0, length in b["maps"]:
            a0 = int(round(wav_at * SR))
            for k in range(0, int(length * SR) - w // 2, w):
                seg = x[a0 + k:a0 + min(k + w, int(length * SR))]
                if len(seg) < SR or float(np.sqrt(np.mean(seg ** 2))) < min_rms:
                    continue
                t = t0 + k / SR                        # main-body seconds of the window's start
                for ref, r0, name in refs:
                    i = int(round((t - r0) * SR)) - ml
                    if i < 0 or i + len(seg) + 2 * ml > len(ref):
                        continue
                    lag, cor = lag_corr(seg, ref[i:i + len(seg) + 2 * ml], ml)
                    res.append({"t": round(t, 3), "ref": name, "lag_ms": round(1000 * lag / SR, 3), "corr": round(cor, 4)})
                    break
        out[b["id"]] = {"windows": len(res), "refs": sorted({r["ref"] for r in res}),
                        "max_abs_lag_ms": max([abs(r["lag_ms"]) for r in res] or [None]),
                        "min_corr": min([r["corr"] for r in res] or [None]),
                        "median_corr": float(np.median([r["corr"] for r in res])) if res else None, "detail": res}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("plan")
    a1.add_argument("pip_dir")
    a1.add_argument("approved_dir")
    a1.add_argument("--steps", required=True, help="the exercise's avatar steps file (exercises/<ex>/avatar_<prefix>"
                    ".json): the intro's line and its carry_into")
    a1.add_argument("--out", default=None)
    a1.add_argument("--max-s", type=float, default=MAX_SEGMENT_S)
    a2 = sub.add_parser("audio")
    a2.add_argument("plan")
    a2.add_argument("out_dir")
    a2.add_argument("--only", default=None)
    a2.add_argument("--handle-audio", choices=("timeline", "silence"), default="silence")   # R236
    a3 = sub.add_parser("verify")
    a3.add_argument("out_dir", help="a folder `audio` built (its manifest.json)")
    a3.add_argument("refs", nargs="+", help="<file>@<main-body seconds of its first sample>")
    a3.add_argument("--win", type=float, default=2.0, help="window length, seconds")
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        res, out = plan_main(a.pip_dir, a.approved_dir, a.steps, a.out, max_s=a.max_s)
        print(json.dumps({"segments": [{k: s[k] for k in ("id", "start_tc", "end_tc", "length_s", "credits")}
                                       for s in res["segments"]], "totals": res["totals"],
                          "warnings": res["warnings"], "out": str(out)}, indent=1))
        return 0
    if a.cmd == "audio":
        built = build_audio(a.plan, a.out_dir, set(a.only.split(",")) if a.only else None, a.handle_audio)
        print(json.dumps([{k: b[k] for k in ("id", "length_s", "samples", "expected_samples", "bytes")}
                          for b in built], indent=1))
        return 0 if all(abs(b["samples"] - b["expected_samples"]) <= b.get("tolerance", 0) and
                        b["bytes"] < UPLOAD_MAX_BYTES for b in built) else 1
    man = Path(a.out_dir) / "manifest.json"           # the WAVs as built, never rebuilt here (Fable)
    if not man.exists():
        raise SystemExit(f"{man} missing: build the WAVs with `audio` first")
    m = json.loads(man.read_text(encoding="utf-8"))
    built = m["built"]
    refs = []
    for spec in a.refs:
        f, t = spec.rsplit("@", 1)
        refs.append((decode_ref(f), float(t), Path(f).name))
    res = verify(built, refs, a.win)
    print(json.dumps({"plan": m["plan"], "handle_audio": m["handle_audio"],
                      "results": {k: {x: v[x] for x in v if x != "detail"} for k, v in res.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
