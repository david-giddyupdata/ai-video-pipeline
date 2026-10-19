"""The highlight reel (R248): a short video of how AI made Section A, cut from the finished video and its sources.

    python tools/reel.py media <reel_plan.json>             # every shot's source span -> <reel>/media/ (with handles)
    python tools/reel.py privacy <reel_plan.json> [--fps=2] [--only=<file>,...]   # OCR the media for private text
    python tools/reel.py lines <reel_plan.json>              # the plan's narration as a steps file for the voice build
    python tools/reel.py stills <reel_plan.json>             # a check still of every beat (Remotion, remotion/scripts/reel.mjs)
    python tools/reel.py table|script <reel_plan.json>       # the beat table; script.md's beats (between its markers)

reel_plan.json (in the reel's folder, e.g. runs/<run>/reel_r1/) is the edit list: the sources, then the beats in
order, each with its shots (a source and its in and out seconds) and what it shows. `media` cuts each shot's span,
handle_s either side, into a file of its own in <reel>/media/, so the reel's Premiere project never depends on a
scratch export that is deleted when a round is done:

  * a shot of the finished video ("final": Premiere's H.264 of the final sequence, R240) becomes ProRes 422 HQ with
    its sound as 48 kHz PCM, the picture as Premiere made it (its blurs included, R127);
  * a shot of the take ("raw": raw.mp4) or of the driver's boxes ("debug": debug_boxes.mp4) becomes ProRes 422 HQ
    with every blur finding of the run's privacy report blurred where and while it shows (R56, R127): the account
    name is blurred in the finished video, but these two files are the unblurred recording. The box is grown and
    blurred as the edit's own masks are (premiere.MASK_PAD_PX, MASK_BLUR_PX). A finding David marked "ignore" in
    privacy_decisions.json stays clear; every other one is blurred, open or not (the reel is shown outside).

`privacy` reads frames of the media (default 2 a second) with Windows OCR and looks for the privacy report's patterns
(the built-in ones: email, the 12-digit account number, keys and secrets, and the exercise's own, the account name):
any hit is printed masked (never the text itself, R4) and makes the command exit 1.

Each file's name carries a hash of what made it (the source's size, the span, the boxes), so a changed shot writes a
new file instead of one an open project holds (Premiere locks its media, GOTCHAS), and an existing one is reused.
"""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import tool                                   # noqa: E402
from pipeline.edit.premiere import MASK_BLUR_PX, MASK_PAD_PX       # noqa: E402
from pipeline.privacy.report import SAMPLE_S                        # noqa: E402

BLURRED = ("raw", "debug")            # the sources that are the take's own, unblurred recording


def load(plan_path):
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["_dir"] = plan_path.parent
    plan["_path"] = str(plan_path)
    fill_fields(plan)
    return plan


def fill_fields(plan):
    """R248 round 7: a layer's text may name a plan field as {name} (plan "fields", e.g. the YouTube pointer until
    David gives the URL): filled in on load; an unknown name refuses, and so does any {name} in a spoken line (it
    would be voiced as written: Fable R7-7)."""
    import re
    fields = {k: v for k, v in (plan.get("fields") or {}).items() if k != "note"}
    odd = [k for k, v in fields.items() if not isinstance(v, str)]
    if odd:
        raise SystemExit(f"plan fields must be text: {odd}")

    def fill(v, where):
        if isinstance(v, str):
            def one(m):
                if m.group(1) not in fields:
                    raise SystemExit(f"{where}: no plan field {m.group(1)!r} for {m.group(0)}")
                return fields[m.group(1)]
            return re.sub(r"\{(\w+)\}", one, v)
        if isinstance(v, list):
            return [fill(x, where) for x in v]
        if isinstance(v, dict):
            return {k: fill(x, where) for k, x in v.items()}
        return v
    for b in plan.get("beats", []):
        if b.get("layer"):
            b["layer"] = fill(b["layer"], b.get("id"))
        for ln in b.get("lines", []):
            if re.search(r"\{\w+\}", ln.get("text", "")):
                raise SystemExit(f"{b.get('id')}: a spoken line can't name a field ({ln['text'][:40]}...)")


def source_path(plan, key):
    p = Path(plan["sources"][key]["path"])
    return p if p.is_absolute() else ROOT / p


def run_dir(plan):
    return ROOT / "runs" / plan["run"]


def spans(plan):
    """Every distinct (source, in, out) the beats' shots use, with the handles: {(src, a, b): [shot ids]}."""
    h, out = float(plan.get("handle_s", 1.0)), {}
    for beat in plan["beats"]:
        for k, sh in enumerate(beat.get("shots", [])):
            src = sh["src"]
            if src not in plan["sources"]:
                raise SystemExit(f"{beat['id']} shot {k}: unknown source {src!r}")
            dur = probe(source_path(plan, src))
            if not 0 <= sh["in_s"] < sh["out_s"] <= dur:
                raise SystemExit(f"{beat['id']} shot {k}: {sh['in_s']}..{sh['out_s']} is outside {src} (0..{dur:.3f})")
            a, b = span_of(plan, sh, dur)
            made = plan["sources"][src].get("made_from")       # a made source's span with Premiere's Media pending
            info = plan["_dir"] / "_source" / f"{src}.json"     # card (reel_build.check_nocap) is refused (F1)
            if made and not info.exists():
                raise SystemExit(f"{src} has no {info.name}: run reel_build.py nocap (check_nocap writes it)")
            if made:
                bad = json.loads(info.read_text(encoding="utf-8")).get("pending_unused")
                if bad and a <= bad[1] and bad[0] <= b:
                    raise SystemExit(f"{beat['id']} shot {k}: {src} shows Media pending {bad[0]}..{bad[1]} s: export "
                                     "it again (reel_build.py nocap) or take the shot elsewhere")
            out.setdefault(media_key(sh, a, b), []).append(f"{beat['id']}.{k}")
    return out


def media_key(sh, a, b):
    """A shot's media: its source, span, crop and its own blur boxes (each a different file of the same span)."""
    return (sh["src"], a, b, tuple(sh["crop"]) if sh.get("crop") else None,
            tuple(tuple(x) for x in sh["blur_px"]) if sh.get("blur_px") else None)


def record_key(m):
    """media.json's record -> media_key's tuple."""
    return (m["src"], m["in_s"], m["out_s"], tuple(m["crop"]) if m.get("crop") else None,
            tuple(tuple(x) for x in m["blur_px"]) if m.get("blur_px") else None)


def span_of(plan, sh, dur):
    """A shot's media span with its handles, snapped outward to whole frames (Fable F1: a cut that starts between
    frames would hold source frame ceil(a*fps) while its sound starts at a, a frame apart). Seconds, 3 decimals."""
    fps, h = plan["fps"], float(plan.get("handle_s", 1.0))
    last = math.floor(dur * fps + 1e-6)
    f0 = max(0, math.floor((sh["in_s"] - h) * fps + 1e-6))
    f1 = min(last, math.ceil((sh["out_s"] + h) * fps - 1e-6))
    return round(f0 / fps, 3), round(f1 / fps, 3)


def probe(path):
    r = subprocess.run([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def blur_boxes(plan, a, b):
    """The run's blur findings that show between source seconds a and b: [(x0, y0, x1, y1, t0, t1)], t relative to a,
    the box grown by MASK_PAD_PX and kept inside the frame (even sizes, for the crop)."""
    rd = run_dir(plan)
    rep = json.loads((rd / "privacy_report.json").read_text(encoding="utf-8"))
    dec_p = rd / "privacy_decisions.json"
    decisions = json.loads(dec_p.read_text(encoding="utf-8")) if dec_p.exists() else {}
    W, H = plan["width"], plan["height"]
    out = []
    for f in rep["findings"]:
        d = decisions.get(f["id"], f.get("decision", "open"))
        d = d.get("decision", "open") if isinstance(d, dict) else d
        if d == "ignore" or f["src_t1"] < a or f["src_t0"] > b:
            continue
        x0, y0, x1, y1 = f["box"]
        x0, y0 = max(0, int(x0) - MASK_PAD_PX), max(0, int(y0) - MASK_PAD_PX)
        x1, y1 = min(W, int(x1 + 0.999) + MASK_PAD_PX), min(H, int(y1 + 0.999) + MASK_PAD_PX)
        x1 -= (x1 - x0) % 2
        y1 -= (y1 - y0) % 2
        # src_t0 is the first sampled sighting: the name may have shown up to a sample earlier (Fable F5)
        out.append((x0, y0, x1, y1, max(0.0, f["src_t0"] - SAMPLE_S - a), min(b, f["src_t1"]) - a))
    return out


def media_name(plan, src, a, b, boxes, crop=None):
    p = source_path(plan, src)
    made = json.dumps({"src": str(p), "bytes": p.stat().st_size, "a": a, "b": b, "boxes": boxes,
                       "blur": [MASK_PAD_PX, MASK_BLUR_PX], "crop": crop, "v": 2}, sort_keys=True)
    h = hashlib.sha256(made.encode("utf-8")).hexdigest()[:8]
    return f"{src}_{a:.3f}_{b:.3f}".replace(".", "p") + f"_{h}.mov"


def cut(plan, src, a, b, out_dir, crop=None, blur_px=None):
    """One source span -> ProRes 422 HQ (and PCM sound for a source that has it), blurred where the take needs it;
    crop [x, y, w, h] (frame px, 16:9) takes that region, after the blur, scaled up to the frame (the visual review's V7:
    the driver's box too small to see from a room)."""
    boxes = blur_boxes(plan, a, b) if src in BLURRED else []
    for x0, y0, x1, y1 in blur_px or []:                    # the shot's own boxes, its whole length (R248 round 4:
        x0, y0, x1, y1 = int(x0), int(y0), int(x1 + 0.999), int(y1 + 0.999)   # the analysis ID in the address bar)
        x0, y0 = max(0, x0 - MASK_PAD_PX), max(0, y0 - MASK_PAD_PX)
        x1, y1 = min(plan["width"], x1 + MASK_PAD_PX), min(plan["height"], y1 + MASK_PAD_PX)
        boxes.append((x0, y0, x1 - (x1 - x0) % 2, y1 - (y1 - y0) % 2, 0.0, b - a))
    path = out_dir / media_name(plan, src, a, b, boxes, list(crop) if crop else None)
    if path.exists():
        return path, boxes
    fps = plan["fps"]
    n = round((b - a) * fps)                       # a and b sit on the frame grid (span_of)
    half = 0.5 / fps
    # Seek half a frame early so the first frame kept is source frame a*fps, then take exactly n frames
    # (premiere.blur_media's way); the sound is trimmed from a itself. Premiere's H.264 is BT.709 limited range with
    # no flags (GOTCHAS): stay in YUV (no RGB round trip), keep 4:2:2 through the overlay, and tag the frames.
    chain = ("[0:v]setpts=PTS-STARTPTS,format=yuv422p10le,"
             "setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709")
    last = "[vcrop]" if crop else "[vout]"
    graph = [chain + ("[v0]" if boxes else last)]
    for i, (x0, y0, x1, y1, t0, t1) in enumerate(boxes):
        graph.append(f"[v{i}]split[base{i}][c{i}];[c{i}]crop={x1 - x0}:{y1 - y0}:{x0}:{y0},gblur=sigma={MASK_BLUR_PX}"
                     f"[b{i}];[base{i}][b{i}]overlay={x0}:{y0}:format=auto:"
                     f"enable='between(t,{t0 - half:.4f},{t1 + half:.4f})'"
                     + (f"[v{i + 1}]" if i + 1 < len(boxes) else last))
    if crop:
        cx, cy, cw, ch = crop
        graph.append(f"[vcrop]crop={cw}:{ch}:{cx}:{cy},scale={plan['width']}:{plan['height']}:flags=lanczos,"
                     f"format=yuv422p10le[vout]")
    has_audio = plan["sources"][src].get("audio", False)
    if has_audio:
        graph.append(f"[0:a]atrim=start={half:.6f}:duration={n / fps:.6f},asetpts=PTS-STARTPTS[aout]")
    part = out_dir / f"_part_{path.name}"
    cmd = [tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{max(0.0, a - half):.6f}", "-i", str(source_path(plan, src)),
           "-filter_complex", ";".join(graph), "-map", "[vout]", "-frames:v", str(n), "-r", str(fps),
           "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le", "-color_primaries", "bt709",
           "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]
    cmd += ["-map", "[aout]", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"] if has_audio else ["-an"]
    subprocess.run(cmd + ["-f", "mov", str(part)], check=True)
    got = video_frames(part)
    if got != n:
        raise SystemExit(f"{path.name}: {got} frames written, {n} wanted")
    part.replace(path)
    return path, boxes


def video_frames(path):
    """The video stream's frame count, counted (not the container's duration, which the sound can lengthen)."""
    r = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                        "stream=nb_read_packets", "-of", "csv=p=0", str(path)], capture_output=True, text=True,
                       check=True)
    return int(r.stdout.strip().strip(","))


def media(plan):
    out_dir = plan["_dir"] / "media"
    out_dir.mkdir(parents=True, exist_ok=True)
    made = {}
    for (src, a, b, crop, bpx), shots in spans(plan).items():
        path, boxes = cut(plan, src, a, b, out_dir, crop, bpx)
        made[path.name] = {"src": src, "in_s": a, "out_s": b, "crop": list(crop) if crop else None,
                           "blur_px": [list(x) for x in bpx] if bpx else None,
                           "first_frame": round(a * plan["fps"]),
                           "shots": shots, "blurred": boxes, "frames": video_frames(path)}
        print(f"{path.name}: {src} {a:.3f}..{b:.3f} for {', '.join(shots)}" + (f", {len(boxes)} blur(s)" if boxes else ""))
    (out_dir / "media.json").write_text(json.dumps(made, indent=1), encoding="utf-8")
    return made


def ocr_folder(folder):
    from pipeline.privacy.report import WINOCR
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(WINOCR), str(folder)],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return [json.loads(ln) for ln in out.splitlines() if ln.strip().startswith("{")]


def patterns(plan):
    from pipeline.privacy.report import with_exercise
    rd = run_dir(plan)
    ep = json.loads((rd / "edit_plan.json").read_text(encoding="utf-8"))
    return with_exercise(((ep.get("settings") or {}).get("privacy") or {}).get("patterns", []))


def privacy(plan, fps=2.0, only=None, files=None):
    """Windows OCR on frames of the reel's media (or the given image or video files): [(file, t, pattern, masked)]."""
    from pipeline.privacy.report import masked, matches
    pats = patterns(plan)
    media_dir = plan["_dir"] / "media"
    files = [Path(f) for f in files] if files else sorted(media_dir.glob("*.mov"))
    if only:
        files = [f for f in files if f.name in only]
    hits = []
    with tempfile.TemporaryDirectory(prefix="reel_ocr_") as tmp:
        for f in files:
            work = Path(tmp) / f.stem
            work.mkdir()
            if f.suffix.lower() in (".png", ".jpg"):
                shutil.copy(f, work / "000000.png")
            else:
                subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(f), "-vf",
                                f"fps={fps},scale=in_color_matrix=bt709:out_color_matrix=bt709", str(work / "%06d.png")],
                               check=True)
            recs = ocr_folder(work)
            n = 0
            for rec in recs:
                n += 1
                k = int(Path(rec["file"]).stem)
                for name, text, _box in matches(rec, pats):
                    hits.append((f.name, round(max(0, k - 1) / fps, 2), name, masked(text)))
            print(f"{f.name}: {n} frames read, {sum(1 for h in hits if h[0] == f.name)} hit(s)")
    return hits


def lines(plan):
    """The plan's narration as a steps file the voice build reads (pipeline.narration.build): one line-only step per
    narrated line, in order, so ElevenLabs gets each line's neighbours (R32, R99)."""
    ex = plan["narration"]["exercise"]
    steps = []
    for beat in plan["beats"]:
        for k, ln in enumerate(beat.get("lines", [])):
            steps.append({"id": f"{beat['id']}.{k + 1}", "action": "none",
                          "narration": {"line_id": f"{plan['narration']['prefix']}.{beat['id']}.{k + 1}",
                                        "text": ln["text"], "status": "draft",
                                        **({"labels": ln["labels"]} if ln.get("labels") else {})}})
    nar = plan["narration"]
    doc = {"exercise": ex, "version": 1, "about": f"R248: the reel's narration, from {plan['_dir'].name}/reel_plan.json "
           "(tools/reel.py lines); voiced by pipeline.narration.build", "steps": steps,
           **{k: nar[k] for k in ("voice_file", "pronunciation_file", "lines_file") if nar.get(k)}}
    out = ROOT / "exercises" / ex / nar.get("steps_file", "steps_reel.json")
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{out}: {len(steps)} lines")
    return out


# ------------------------------------------------------------------------------------------------- timing
LEAD_S, GAP_S = 0.4, 0.45          # a beat's first line starts LEAD_S in; lines GAP_S apart (pacing.gap_between_lines)
TAIL_S = 0.5                       # a beat ends this long after its last line (with the next lead: under 1 s between beats)
WINDOW = {"x": 96, "y": 182, "w": 1024, "h": 576}      # Reel.tsx's REEL.window


def window(plan):
    """The footage window's box: the plan's own (round 5 moves it under the process line), else Reel.tsx's."""
    return plan.get("window", WINDOW)


def note_width(text, size=48):
    """An image panel's note as Reel.tsx sets it (Segoe UI, SIZE_SMALL), in px."""
    from PIL import ImageFont
    return ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", size).getlength(text)


def process_xs(pr_, pl=90, pr=74, pad=7, size=26):
    """The stops' centres in the process band, spaced so the gaps between their labels (each as wide as its lit chip)
    are equal: a long label ("The Agents") gets the room it needs (round 5's fresh-eyes review)."""
    from PIL import ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", pr_.get("size", size))
    w = [font.getlength(s) + 2 * pad for s in pr_["stops"]]
    span = pr_["box"]["w"] - pl - pr
    gap = (span - (sum(w) - w[0] / 2 - w[-1] / 2)) / (len(w) - 1)
    xs, x = [pl], pl
    for a, b in zip(w, w[1:]):
        x += a / 2 + gap + b / 2
        xs.append(round(x, 1))
    return xs


def process_state(plan, beat):
    """The process line in a beat (R248 round 5): None outside its span, else its props for Reel.tsx's Process: the
    stops, the lit one (-1 before the first stop's beat), its box, and its entry on the span's first beat."""
    pr_ = plan.get("process")
    if not pr_:
        return None
    ids = [b["id"] for b in plan["beats"]]
    a, z = ids.index(pr_["span"][0]), ids.index(pr_["span"][1])
    i = ids.index(beat["id"])
    if not a <= i <= z:
        return None
    lit = [pr_["beats"][x] for x in ids[a:i + 1] if x in pr_["beats"]]
    cur = pr_["beats"].get(beat["id"], -1)
    out = {"stops": pr_["stops"], "current": cur, "box": pr_["box"], "xs": process_xs(pr_),
           **({"size": pr_["size"]} if pr_.get("size") else {}), **({"inHeader": True} if pr_.get("in_header", pr_["box"]["x"] == 0) else {})}   # (a box at x 0 is the bar's own)
    if cur < 0 and lit:                                         # (between stops: the last one stays lit)
        out["current"] = lit[-1]
    if i == a and (beat.get("enter") or {}).get("fly"):         # it flies in with the span's first fly-in
        out.update({"enterAt": FLY_AT_S, "enterDur": FLY_S})
    elif i == a and pr_.get("reveal"):                          # or draws in, left to right, once its beat is up
        out["revealAt"] = round(join_frames(plan["fps"]) / plan["fps"] if joined_from(plan, beat) else 0.3, 3)
        if pr_.get("revealDur"):
            out["revealDur"] = pr_["revealDur"]
    return out
INTRO_IN_FINAL_S = 0.617           # the intro clip's time 0 on the final (its "A" at 7.863 s sounds at 8.48 s)
MOTION_S = 0.5                     # Reel.tsx's ease-in (the tokens' motion.baseS): a label is whole this long after it starts
FADE_S = 0.3                       # R248 round 3 (a plan's "fades"): the whole frame dips this long out and in at a beat change
FLY_AT_S, FLY_S = FADE_S, 0.9      # a beat's "enter": its layer (or its first picture) flies in once the dip has lifted
                                   # (Fable r3 F3), for FLY_S


def join_frames(fps):
    """A joined beat change's dissolve (R248 round 4, J1): the outgoing card runs on this long into the next beat,
    fading out while the next beat's footage and panels fade in."""
    return 2 * round(FADE_S * fps)


def check_joins(plan):
    """A join_next only where the build makes a whole dissolve of it (Fable r4 H4, J7): from a card with no footage
    into the next beat, which isn't a card, carries no AI-voice note (the card's still and note run on into it), has
    no faded first picture (its own fade-in is the dissolve's), and, if full frame, flies in over the room."""
    beats = plan["beats"]
    note = set((plan.get("note") or {}).get("beats", []))
    for i, b in enumerate(beats):
        if not b.get("join_next"):
            continue
        nxt = beats[i + 1] if i + 1 < len(beats) else None
        why = None
        if b["layout"] != "card" or any(not s.get("audio_only") for s in b.get("shots", [])):
            why = "it isn't a card without footage"
        elif nxt is None:
            why = "it is the last beat"
        elif nxt["layout"] == "card":
            why = f"{nxt['id']} is a card"
        elif nxt["id"] in note:
            why = f"{nxt['id']} carries the AI-voice note"
        elif nxt["layout"] == "full" and not (nxt.get("enter") or {}).get("fly"):
            why = f"{nxt['id']} is full frame without a fly-in (no room under its first frame)"
        elif nxt["layout"] != "full" and (nxt.get("enter") or {}).get("fly"):
            why = f"{nxt['id']}'s layer flies in, which would hide it under the dissolve (Fable K7)"
        else:
            pics = [s for s in nxt.get("shots", []) if not s.get("audio_only")]
            if pics and pics[0].get("fade_s") and nxt["layout"] == "frame":
                why = f"{nxt['id']}'s first picture fades on its own"
        if why:
            raise SystemExit(f"{b['id']}: join_next can't make a dissolve here: {why}")


def joined_from(plan, beat):
    """The beat whose join_next dissolves into this one, or None."""
    ids = [b["id"] for b in plan["beats"]]
    i = ids.index(beat["id"])
    return plan["beats"][i - 1] if i and plan["beats"][i - 1].get("join_next") else None


def enter_s(beat):
    """The extra time a beat with an "enter" (R248 round 3: the open into the main part, the main part into the
    ending) takes before its narration or its first shot: its graphics fly in, with a whoosh."""
    e = beat.get("enter") or {}
    x = float(e.get("extra_s", 0.0))
    if e.get("fly") and x < FLY_AT_S + FLY_S:                  # (Fable r3 follow-up G4)
        raise SystemExit(f"{beat['id']}: enter.extra_s {x} is shorter than the fly ({FLY_AT_S + FLY_S:.1f} s)")
    return x


def voiced(plan):
    """The voiced lines (exercises/<ex>/lines.json) by line id, or {} before the voice build has run."""
    p = lines_path(plan)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def lines_path(plan):
    """The voiced lines' file: the plan's narration "lines_file" (a second voice keeps its own), else lines.json."""
    return ROOT / "exercises" / plan["narration"]["exercise"] / plan["narration"].get("lines_file", "lines.json")


def line_id(plan, beat, k):
    return f"{plan['narration']['prefix']}.{beat['id']}.{k + 1}"


def words_of(text):
    import re
    return re.findall(r"[\w$][\w'’.,$:%-]*", text)


def timed_lines(plan, beat):
    """Each narrated line's place in its beat: [{text, start, length, words: [{w, start, end}], voiced}], from the voice
    build when it has run, else estimated at the plan's words_per_s (so the draft's beat lengths are estimates)."""
    lead = LEAD_S if joined_from(plan, beat) is None else max(LEAD_S, join_frames(plan["fps"]) / plan["fps"])
    have, rate, t, out = voiced(plan), plan.get("words_per_s", 2.25), lead + enter_s(beat), []   # (Fable K2)
    for k, ln in enumerate(beat.get("lines", [])):
        v = have.get(line_id(plan, beat, k))
        if v and v.get("text") == ln["text"]:
            meta = json.loads((ROOT / "audio_cache" / f"{v['key']}.json").read_text(encoding="utf-8"))
            ws = [{"w": w["word"], "start": t + w["start"], "end": t + w["end"], "char": w.get("char")}
                  for w in meta["words"]]
            length, is_voiced = v["length_s"], True
        else:
            names = words_of(ln["text"])
            ws = [{"w": w, "start": t + i / rate, "end": t + (i + 0.9) / rate} for i, w in enumerate(names)]
            length, is_voiced = len(names) / rate, False
        out.append({"text": ln["text"], "start": round(t, 3), "length": round(length, 3), "words": ws,
                    "voiced": is_voiced, "id": line_id(plan, beat, k)})
        t += length + GAP_S
    return out


def _letters(x):
    return "".join(ch for ch in x.lower() if ch.isalnum())


def cue_time(lines_, cue, default, after=-1.0, misses=None):
    """The start of the first word beginning with `cue` (case-insensitive, letters and digits only: the voice's
    spoken "Re-motion" is the cue "Remotion") that starts after `after` (the row above's cue, so rows appear in order:
    Fable F2), else default."""
    for ln in lines_:
        for w in ln["words"]:
            if w["start"] > after + 0.002 and _letters(w["w"]).startswith(_letters(cue)):   # (after is rounded)
                return round(w["start"], 3)
    if misses is not None:                                      # a cue no word answers (Fable r3 F5)
        misses.append(cue)
    return default


def cues_in_order(lines_, cues, start=0.4, step=0.3, misses=None):
    """Times for items said in order: each on its cue word (after the item before), or step after the one before."""
    out, last = [], -1.0
    for i, c in enumerate(cues):
        dflt = max(last + step, start + i * step)
        at = cue_time(lines_, c, dflt, last, misses) if c else dflt
        out.append(at)
        last = at
    return out


def shot_places(beat):
    """Each shot's start in its beat: sequential shots one after another; a shot with its own at_s (audio only, or a
    picture faded in over the beat, R248's avatar on the clone line) there, outside the sequence."""
    t, out = enter_s(beat), []
    for sh in beat.get("shots", []):
        if "at_s" in sh:
            out.append(sh["at_s"])
        else:
            out.append(t)
            t += sh["out_s"] - sh["in_s"]
    return out


def timeline_panel(plan, panel):
    """The final's video tracks and markers as the assembly beat draws them, read from the final's own .prproj
    (cached beside the plan)."""
    cache = plan["_dir"] / "final_tracks.json"
    if not cache.exists():
        from pipeline.edit.prproj import Project, sec
        rd = run_dir(plan)
        p = Project(rd / "final_r5" / f"{plan['run']}_final.prproj")      # read only
        d = p.parse_sequence(f"{plan['run']} final")
        job = json.loads((rd / "final_r5" / "final_job.json").read_text(encoding="utf-8"))
        notes = json.loads((rd / "final_r5" / "review_markers.json").read_text(encoding="utf-8"))["markers"]
        prproj = rd / "final_r5" / f"{plan['run']}_final.prproj"
        doc = {"from": str(prproj), "dur": round(sec(d["duration_ticks"]), 3),
               "tracks": [{"name": t["name"], "clips": [[round(sec(i["start_ticks"]), 2), round(sec(i["end_ticks"]), 2)]
                                                        for i in t["items"]]} for t in d["video_tracks"]],
               "markers": sorted({round(m["t"], 2) for m in job["sequences"][0]["markers"] + notes})}
        cache.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    doc = json.loads(cache.read_text(encoding="utf-8"))
    short = {"Approved sequence and logo": "Approved edit", "Avatar stage": "Avatar stage", "Avatar box": "Avatar oval",
             "Call to action (url)": "Web address", "Caption titles": "Captions"}
    return {"type": "timeline", "at": 0.3, "dur": doc["dur"], "markers": doc["markers"], "note": panel["note"],
            "tracks": [{"name": short.get(t["name"], t["name"]), "clips": t["clips"]} for t in doc["tracks"]]}


def karaoke_panel(plan, beat, panel):
    """The intro line the narration beat shows, its words timed as the final plays them, from the audio shot's start."""
    have = json.loads((ROOT / "exercises" / panel.get("exercise", "qs1_section_a") / "lines.json").read_text(encoding="utf-8"))
    meta = json.loads((ROOT / "audio_cache" / f"{have[panel.get('line_id', 'qs1a.intro')]['key']}.json").read_text(encoding="utf-8"))
    sh = next(s for s in beat["shots"] if s.get("audio_only") or s.get("karaoke"))
    want = words_of(panel["line"])
    ws = meta["words"]
    for i in range(len(ws)):
        got = [w["word"] for w in ws[i:i + len(want)]]
        if [g.lower() for g in got] == [w.lower().strip(".") for w in want]:
            at = sh["at_s"]
            return {"type": "karaoke", "at": at, "note": panel["note"],
                    **({"hideAt": at} if not sh.get("audio_only") else {}),
                    "words": [{"w": want[j], "start": round(w["start"] + INTRO_IN_FINAL_S - sh["in_s"], 3),
                               "end": round(w["end"] + INTRO_IN_FINAL_S - sh["in_s"], 3)}
                              for j, w in enumerate(ws[i:i + len(want)])]}
    raise SystemExit(f"{beat['id']}: '{panel['line']}' not found in the intro's word times")


def layer_props(plan, beat):
    """The Remotion layer (Reel.tsx) for a beat, its times from the narration (voiced or estimated)."""
    lay = json.loads(json.dumps(beat["layer"]))
    tl = timed_lines(plan, beat)
    miss = []                                                   # cues no word answered: refused once voiced (F5)
    if (beat.get("enter") or {}).get("fly") and beat["layout"] != "full":      # R248 r3: the layer flies in whole
        if beat["layout"] == "frame" and any(not s.get("audio_only") for s in beat.get("shots", [])):
            raise SystemExit(f"{beat['id']}: a frame beat with footage can't fly in (its footage would stay put)")
        lay["enter"] = {"at": FLY_AT_S, "dur": FLY_S}
    if lay.get("titleCue"):                                     # a card's title flies in on its word
        lay["titleAt"] = cue_time(tl, lay.pop("titleCue"), 0.4, misses=miss)
    if lay["kind"] in ("card", "board"):
        for col in [lay] + lay.get("columns", []):
            last = -1.0
            for i, r in enumerate(col.get("rows", [])):
                if bool(r.get("mark")) != bool(r.get("markCue")):   # a mark needs its word and a word its mark (J5)
                    raise SystemExit(f"{beat['id']}: row {i} has mark {r.get('mark')!r} and markCue {r.get('markCue')!r}")
                if r.get("mark") and not r["text"].startswith(r["mark"]):
                    raise SystemExit(f"{beat['id']}: row {i}'s mark {r['mark']!r} isn't the start of its text")
                if r.get("markCue"):                            # its first word underlined as it is said
                    r["markAt"] = cue_time(tl, r.pop("markCue"), max(last + 0.3, 0.4 + i * 0.3), last, miss)
                if r.get("cue"):
                    r["at"] = cue_time(tl, r.pop("cue"), max(last + 0.3, 0.4 + i * 0.3), last, miss)
                else:
                    r["at"] = r.get("at", max(last + 0.3, 0.4 + i * 0.3))
                if r.get("markAt") is not None:                 # drawn once the row has risen (Fable r4 H3, J4:
                    r["markAt"] = round(max(r["markAt"], r["at"] + MOTION_S), 3)   # the rise is MOTION_S)
                if r["at"] < last:
                    raise SystemExit(f"{beat['id']}: row {i} ({r['text'][:30]}) comes before the row above it")
                last = r["at"]
        if lay.get("footer") and (lay["footer"].get("mark") or lay["footer"].get("markCue")):
            raise SystemExit(f"{beat['id']}: a footer can't carry a mark (Fable K5)")
        if lay.get("footer"):
            lay["footer"]["at"] = cue_time(tl, lay["footer"].pop("cue"), 1.2, misses=miss) if lay["footer"].get("cue") else 1.2
    src = joined_from(plan, beat)
    if src is not None:                                         # it fades in under the card's fade-out (J1)
        lay["fadeIn"] = round(join_frames(plan["fps"]) / plan["fps"], 3)
    ps = process_state(plan, beat)
    if ps:
        lay["process"] = ps
    if lay["kind"] == "chip" and enter_s(beat):                # a chip over an entered full beat: after the fly
        lay["at"] = round(lay.get("at", 0.0) + enter_s(beat), 3)
    if lay["kind"] == "frame":
        places = shot_places(beat)
        wb = lay.pop("windowBox", None)                         # (a panel-only beat may size its own window)
        if wb and any(not s.get("audio_only") for s in beat.get("shots", [])):
            raise SystemExit(f"{beat['id']}: a windowBox is for a panel; footage goes in the plan's window (Fable L1)")
        win = wb or window(plan)
        p_ = lay.get("panel") or {}
        if p_.get("type") == "image" and p_.get("note") and note_width(p_["note"]) > win["w"] - 20:
            raise SystemExit(f"{beat['id']}: the image panel's note is wider than its panel (Fable F4)")
        if "toolCues" in lay:                                   # the tools build as they are said (R248 r3)
            lay["toolsAt"] = cues_in_order(tl, lay.pop("toolCues"), 0.6, misses=miss)
        if lay.get("keyCue"):
            lay["keyAt"] = cue_time(tl, lay.pop("keyCue"), 0.15, misses=miss)
        if lay.get("ruleCue") or lay.get("toolsAt"):
            after = max(lay.get("toolsAt") or [0.0])
            lay["ruleAt"] = (cue_time(tl, lay.pop("ruleCue"), after + 0.6, after, miss) if lay.get("ruleCue")
                             else after + 0.6)
        if lay.get("pointer"):
            lay["pointer"] = pointer_props(beat, lay["pointer"], places, window(plan))
        lay["windows"] = [{"box": win, "label": sh.get("label"), "at": round(places[k], 3),
                           "until": round(places[k] + sh["out_s"] - sh["in_s"], 3)}
                          for k, sh in enumerate(beat.get("shots", [])) if not sh.get("audio_only")] or [{"box": win}]
        if lay["windows"][-1].get("label"):
            lay["windows"][-1]["until"] = beat_length(plan, beat)      # the last view holds to the beat's end (F8)
        p = lay.get("panel")
        if p and p["type"] == "timeline":
            lay["panel"] = timeline_panel(plan, p)
        elif p and p["type"] == "karaoke":
            lay["panel"] = karaoke_panel(plan, beat, p)
        elif p and p["type"] == "bars":
            p["at"] = 0.3
    if miss and all(x["voiced"] for x in tl):
        raise SystemExit(f"{beat['id']}: no spoken word answers the cue(s) {miss}")
    return lay


def pointer_props(beat, pt, places, win=None):
    """The presenter beat's pointer (Reel.tsx Pointer) from the plan's terms: its tips in the shot's own frame px
    (scaled into the window), its times in the shot's source seconds (placed where the shot plays in the beat)."""
    sh, at = beat["shots"][pt["shot"]], places[pt["shot"]]
    win = win or WINDOW
    k = win["w"] / 1920
    xy = lambda v: (round(win["x"] + v[0] * k, 1), round(win["y"] + v[1] * k, 1))
    when = lambda s: round(at + s - sh["in_s"], 3)
    (x0, y0), (x1, y1) = xy(pt["tip0"]), xy(pt["tip1"])
    return {"x0": x0, "y0": y0, "a0": pt["dir0"], "x1": x1, "y1": y1, "a1": pt["dir1"],
            "at": when(pt["at_src"]), "fly0": when(pt["fly_src"][0]), "fly1": when(pt["fly_src"][1]),
            "gone": when(pt["gone_src"]), "len": pt.get("len", 170), "stroke": pt.get("stroke", 8),
            "head": pt.get("head", 40), "color": pt.get("color", "#E86F3B"), "turns": pt.get("turns", 1),
            **({"edge": pt["edge"]} if pt.get("edge") else {}), **({"len1": pt["len1"]} if pt.get("len1") else {})}


def beat_length(plan, beat):
    """The beat's length: the plan's draft, or longer when the narration or the shots need more (a beat's own
    "tail_s" holds its last items longer)."""
    tl = timed_lines(plan, beat)
    need = (tl[-1]["start"] + tl[-1]["length"] + beat.get("tail_s", TAIL_S)) if tl else 0.0
    places = shot_places(beat)
    for k, sh in enumerate(beat.get("shots", [])):
        need = max(need, places[k] + sh["out_s"] - sh["in_s"])
    return round(max(beat.get("dur_s", 0.0), need), 3)


# ------------------------------------------------------------------------------------------------- check stills
def still_jobs(plan, out_dir):
    """A check still of each beat over its background and footage (as Premiere will place them): one per footage shot
    (at the shot's middle) for a frame beat, the layer over the footage itself for a full-frame beat with a layer (the
    open's label, Fable F3), else the beat's last frame. Footage stills come from the media (run `media` first)."""
    pub = plan["_dir"] / "public"
    (pub / "stills").mkdir(parents=True, exist_ok=True)
    mj = plan["_dir"] / "media" / "media.json"
    if not mj.exists():
        raise SystemExit(f"{mj} missing: run `python tools/reel.py media {plan['_dir'] / 'reel_plan.json'}` first")
    made = json.loads(mj.read_text(encoding="utf-8"))
    by_span = {record_key(m): name for name, m in made.items()}
    fps, jobs = plan["fps"], []
    full_box = {"x": 0, "y": 0, "w": plan["width"], "h": plan["height"]}
    for beat in plan["beats"]:
        dur = beat_length(plan, beat)
        n = max(1, round(dur * fps))
        base = {"durationInFrames": n, "fps": fps, "width": plan["width"], "height": plan["height"]}
        if beat["layout"] == "full" and not beat.get("layer"):
            continue
        lay = layer_props(plan, beat)
        import reel_build
        nar_png = reel_build.narrator_still(plan) if beat["layout"] == "card" else None   # as placed (Fable B5)
        bg = {"still": plan.get("room", "room.png"), **({"narrator": nar_png} if beat["layout"] == "card" else {})}
        places = shot_places(beat)
        shots = [(k, sh) for k, sh in enumerate(beat.get("shots", [])) if not sh.get("audio_only")]   # F7
        if beat["layout"] in ("frame", "full") and shots:
            for k, sh in shots:
                a, b = span_of(plan, sh, probe(source_path(plan, sh["src"])))
                key = media_key(sh, a, b)
                if key not in by_span:
                    raise SystemExit(f"{beat['id']} shot {k}: no media for {key}; run `media` again")
                mid = (sh["out_s"] - sh["in_s"]) / 2
                # a full-frame beat's label must be whole in its still (its at plus the ease-in)
                at = (max(mid, lay.get("at", 0.0) - places[k] + MOTION_S) if beat["layout"] == "full"
                      else mid)                             # (a chip's at is beat time; the seek is shot time: J8)
                png = pub / "stills" / f"{beat['id']}_{k}.png"
                subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{sh['in_s'] - a + at:.3f}", "-i",
                                str(plan["_dir"] / "media" / by_span[key]), "-frames:v", "1", "-vf",
                                "scale=in_color_matrix=bt709:out_color_matrix=bt709", str(png)], check=True)
                frame = min(n - 1, round((places[k] + at) * fps))
                props = {**base, "layer": lay, "shots": [{"src": f"stills/{png.name}",
                                                          "box": full_box if beat["layout"] == "full" else window(plan)}]}
                if beat["layout"] == "frame":
                    props.update(bg)
                jobs.append({"out": str(out_dir / f"{beat['id']}_{k}.png"), "frame": frame, "props": props})
        else:
            jobs.append({"out": str(out_dir / f"{beat['id']}.png"), "frame": n - 1, "props": {**base, **bg, "layer": lay}})
    return jobs


def layout_stills(plan, out_dir):
    """R248 round 5: the layout stills David approves before a build: one full-size still a beat at its middle, as the
    sequence will show it (Remotion's layer over the room, the narrator's still and the real footage frame, then the
    AI-voice note and the caption up at that moment, drawn as Premiere's title draws it), the layer alone beside each
    (for the contrast and caption checks); a plan's "layout_extra" [[beat, seconds, tag]] adds stills. The checks,
    close-ups and contact sheet are made from these by the caller. Returns the stills."""
    import reel_build
    from PIL import Image, ImageDraw, ImageFont
    from pipeline.edit.ppro import titles
    out_dir.mkdir(parents=True, exist_ok=True)
    pub = plan["_dir"] / "public"
    (pub / "stills").mkdir(parents=True, exist_ok=True)
    fps, W, H = plan["fps"], plan["width"], plan["height"]
    tl = reel_build.timeline(plan)                              # (the voiced lines and the media: run media first)
    cues = reel_build.cues(plan, tl)
    nar_png = reel_build.narrator_still(plan)                   # as the build places her (Fable B5)
    jobs, made = [], []
    extra = {(x[0], round(x[1] * fps)): x[2] for x in plan.get("layout_extra", [])}
    for b, f, tag in [(b, f, tag) for b in tl for f, tag in [(b["n"] // 2, "mid"), (max(0, b["n"] - 12), "end")]
                      + [(k[1], v) for k, v in extra.items() if k[0] == b["beat"]["id"]]]:
        beat, n = b["beat"], b["n"]                             # (mid: as asked; end: every item up, before the dip)
        lay = layer_props(plan, beat) if beat.get("layer") else {"kind": "chip", "title": "", "at": 1e9,   # (none: an
                                                                 "box": {"x": 0, "y": 0, "w": 1, "h": 1}}  # unseen one)
        props = {"durationInFrames": n, "fps": fps, "width": W, "height": H, "layer": lay}
        shots = []
        for sh in b["shots"]:                                   # the picture up at the middle frame
            if sh["vlen"] and sh["at"] <= b["f0"] + f < sh["at"] + sh["vlen"]:
                src = sh["src0"] + (b["f0"] + f - sh["at"])
                png = pub / "stills" / f"layout_{beat['id']}_{tag}.png"
                subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{max(0.0, (src - 0.5) / fps):.4f}", "-i",
                                sh["path"], "-frames:v", "1", "-vf",
                                "scale=in_color_matrix=bt709:out_color_matrix=bt709", str(png)], check=True)
                box = {"x": 0, "y": 0, "w": W, "h": H} if beat["layout"] == "full" else window(plan)
                shots = [{"src": f"stills/{png.name}", "box": box}]
        bg = {}
        if beat["layout"] != "full":
            bg["still"] = plan.get("room", "room.png")
        if beat["layout"] == "card":
            bg["narrator"] = nar_png
        name = f"{beat['id']}_{tag}_{b['f0'] + f:05d}"
        jobs.append({"out": str(out_dir / f"{name}.png"), "frame": f, "props": {**props, **bg, "shots": shots}})
        jobs.append({"out": str(out_dir / "_alpha" / f"{name}.png"), "frame": f, "props": props})
        made.append((name, b, f))
    (out_dir / "_alpha").mkdir(exist_ok=True)
    render(plan, jobs, "layout")
    note = plan.get("note")
    font = ImageFont.truetype(titles.FONT_FILE, reel_build.CAPTION_PX)
    for name, b, f in made:                                     # the note and the caption, as Premiere lays them
        im = Image.open(out_dir / f"{name}.png").convert("RGBA")
        if note and b["beat"]["id"] in note["beats"] and f / fps < note.get("dur_s", 1e9):
            im = Image.alpha_composite(im, Image.open(pub / note["png"]).convert("RGBA"))
        now = (b["f0"] + f) / fps
        for c in cues:
            if c["start"] <= now < c["end"]:
                lines = c["text"].split("\n")
                l, tp, r, bt = titles.ink_box(lines, reel_build.CAPTION_PX)
                bw, bh = r - l + 2 * titles.PAD_PX, bt - tp + 2 * titles.PAD_PX
                x, y = c["cx"] - bw / 2, reel_build.CAPTION_BOTTOM - bh
                d = ImageDraw.Draw(im)
                d.rectangle((x, y, x + bw, y + bh), fill="#" + reel_build.CAPTION_BOX)
                ax, ay = x + titles.PAD_PX - l, y + titles.PAD_PX - tp
                for k, ln in enumerate(lines):
                    d.text((ax, ay + k * titles.line_step(reel_build.CAPTION_PX)), ln, font=font, fill="white",
                           anchor="ls")
                b.setdefault("_cue", {})[name] = {"box": [round(x), round(y), round(bw), round(bh)], "text": c["text"]}
        im.convert("RGB").save(out_dir / f"{name}.png")
    return made


def render(plan, jobs, name):
    """Run remotion/scripts/reel.mjs on the jobs (Remotion's temp on G:'s scratch when there, GOTCHAS)."""
    jp = plan["_dir"] / f"_{name}_jobs.json"
    jp.write_text(json.dumps(jobs, indent=1), encoding="utf-8")
    tmp = Path(r"G:\aidv_scratch\remotion_tmp")
    cmd = ["node", "scripts/reel.mjs", str(plan["_dir"] / "public"), str(jp)] + ([str(tmp)] if tmp.parent.exists() else [])
    r = subprocess.run(cmd, cwd=ROOT / "remotion", shell=False)
    if r.returncode:
        raise SystemExit(f"reel.mjs failed ({r.returncode}); see above")


# ------------------------------------------------------------------------------------------------- the script
def tc(s, fps=30):
    f = round(s * fps)
    return f"{f // (3600 * fps):02d}:{f // (60 * fps) % 60:02d}:{f // fps % 60:02d}:{f % fps:02d}"


def screen_text(lay):
    """What the picture says, as plain lines (what carries a beat when the narration is muted)."""
    out = []
    k = lay["kind"]
    if k == "chip":
        out.append(f"{lay['title']}: {lay.get('text', '')}")
    elif k == "frame":
        out.append(f"Header: \"{lay['num']}  {lay['name']} | {lay['what']}\"")
        out.append(f"Key: \"{lay['keyBig']}\", \"{lay['keySmall']}\"")
        out.append("Tools: " + ", ".join(f"\"{x}\"" for x in lay["tools"]))
        out.append(f"Rule: \"{lay['rule']}\"")
        p = lay.get("panel") or {}
        if p.get("type") == "karaoke":
            out.append(f"Panel: \"{p['line']}\", its words underlined as they are heard; \"{p['note']}\"")
        elif p.get("type") == "bars":
            out.append(f"Panel: \"{p['title']}\": " + (", ".join(f"\"{r['label']}\"" for r in p["rows"])
                       + " (bars to scale, no numbers shown)" if p.get("showN") is False else
                       ", ".join(f"{r['label']} {r['n']}" for r in p["rows"])))
        elif p.get("type") == "timeline":
            out.append(f"Panel: the final's Premiere tracks and markers, drawn from {p.get('source', 'its .prproj')}; "
                       f"\"{p['note']}\"")
    else:
        out.append(f"Title: \"{lay['title']}\"")
        if lay.get("stages"):
            out.append("Stages: " + "; ".join(f"{i} {s}" for i, s in enumerate(lay["stages"])))
        for col in [lay] + lay.get("columns", []):
            if col is not lay:
                out.append(f"Column \"{col['head']}\":")
            for r in col.get("rows", []):
                out.append(f"  \"{(r.get('big', '') + ' ') if r.get('big') else ''}{r['text']}\"")
        if lay.get("chips"):
            out.append("Chips: " + ", ".join(f"\"{c}\"" for c in lay["chips"]))
        if lay.get("footer"):
            f = lay["footer"]
            out.append(f"Footer: \"{(f.get('big', '') + ' ') if f.get('big') else ''}{f['text']}\"")
    return out


def script(plan):
    """reel_r1/script.md's beat table, from the plan (the narration, the footage, the screen text, the lengths)."""
    t, rows, words, sound_up = 0.0, [], 0, 0.0
    for beat in plan["beats"]:
        dur = beat_length(plan, beat)
        tl = timed_lines(plan, beat)
        words += sum(len(words_of(x["text"])) for x in tl)
        places = shot_places(beat)
        shots = []
        for k, sh in enumerate(beat.get("shots", [])):
            where = f"{sh['src']} {tc(sh['in_s'])} to {tc(sh['out_s'])}" if sh["src"] == "final" else \
                f"{sh['src']} {sh['in_s']:.2f} to {sh['out_s']:.2f} s"
            snd = sh.get("sound", "none")
            if snd == "up":
                sound_up += sh["out_s"] - sh["in_s"]
            shots.append(f"at {places[k]:.1f} s: {where} ({'sound up' if snd == 'up' else 'muted' if snd == 'muted' else 'no sound'}"
                         f"{', label ' + repr(sh['label']) if sh.get('label') else ''}): {sh.get('what', '')}")
        rows.append({"beat": beat, "t0": t, "dur": dur, "lines": tl, "shots": shots,
                     "screen": screen_text(beat["layer"]) if beat.get("layer") else []})
        t += dur
    return rows, t, words, sound_up


BEATS_START, BEATS_END = "<!-- beats: written by tools/reel.py script -->", "<!-- end of beats -->"


def beats_markdown(plan):
    """The beat-by-beat part of script.md: for each beat its timecodes on the reel, length, footage, screen text,
    narration and sound in each export."""
    rows, total, words, up = script(plan)
    out = [f"Draft length **{tc(total)}** ({total:.1f} s): {words} narrated words "
           f"({'voiced' if all(x['voiced'] for r in rows for x in r['lines']) else 'estimated at ' + str(plan.get('words_per_s', 2.25)) + ' words a second, not voiced'}), "
           f"{up:.1f} s with the finished video's own sound up.", ""]
    for r in rows:
        b = r["beat"]
        out.append(f"### {tc(r['t0'])} to {tc(r['t0'] + r['dur'])} ({r['dur']:.1f} s): {b['name']} [{b['id']}]")
        out.append("")
        lay = {"full": "the finished video, full frame", "frame": "a stage frame: header, footage window or panel, "
               "the key-number column", "card": "the stage layout: the narrator's still in the left third, the card on "
               "the right", "board": "a full-width board, voice only"}[b["layout"]]
        out.append(f"- **Picture:** {lay}.")
        for s in r["shots"]:
            out.append(f"  - {s}")
        if r["screen"]:
            out.append("- **On screen (carries the beat when muted):**")
            out += [f"  - {x.strip()}" for x in r["screen"]]
        if r["lines"]:
            for x in r["lines"]:
                out.append(f"- **Narration** (from {x['start']:.1f} s, about {x['length']:.1f} s): \"{x['text']}\"")
        else:
            out.append("- **Narration:** none (the finished video's own sound).")
        ups = [s for s in b.get("shots", []) if s.get("sound") == "up"]
        talk = "the sound-up listed above, nothing else" if ups else "silent (labels only)"
        out.append(f"- **Sound:** standalone: {'the narration, then ' if r['lines'] and ups else ''}"
                   f"{'the finished video, sound up' if ups else 'the narration' if r['lines'] else 'none'}; "
                   f"talk: {talk}.")
        out.append("")
    return "\n".join(out)


def write_script(plan):
    """script.md beside the plan: the hand-written parts kept, the beats between the markers rewritten."""
    p = plan["_dir"] / "script.md"
    body = beats_markdown(plan)
    if p.exists():
        s = p.read_text(encoding="utf-8")
        a, b = s.find(BEATS_START), s.find(BEATS_END)
        if a < 0 or b < 0:
            raise SystemExit(f"{p} has no beat markers; add {BEATS_START} and {BEATS_END} where the beats go")
        s = s[:a + len(BEATS_START)] + "\n\n" + body + "\n" + s[b:]
    else:
        s = f"# The reel's script\n\n{BEATS_START}\n\n{body}\n{BEATS_END}\n"
    p.write_text(s, encoding="utf-8")
    print(p)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["media", "privacy", "lines", "stills", "layout", "table", "script"])
    ap.add_argument("plan")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--only")
    ap.add_argument("--files", help="comma-separated image or video files to read instead of the media")
    a = ap.parse_args(argv)
    plan = load(a.plan)
    if a.cmd == "media":
        media(plan)
    elif a.cmd == "privacy":
        hits = privacy(plan, a.fps, a.only.split(",") if a.only else None, a.files.split(",") if a.files else None)
        for h in hits:
            print("  HIT", *h)
        return 1 if hits else 0
    elif a.cmd == "lines":
        lines(plan)
    elif a.cmd == "stills":
        out = plan["_dir"] / "stills"
        render(plan, still_jobs(plan, out), "stills")
    elif a.cmd == "script":
        write_script(plan)
    elif a.cmd == "layout":
        layout_stills(plan, plan["_dir"] / "layout_stills")
    else:
        rows, total, words, up = script(plan)
        for r in rows:
            b = r["beat"]
            print(f"{tc(r['t0'])}  {b['id']:4s} {b['name']:16s} {r['dur']:5.1f} s  "
                  + " / ".join(f"[{x['start']:.1f}+{x['length']:.1f}] {x['text']}" for x in r["lines"]))
        print(f"total {total:.1f} s ({tc(total)}), {words} narrated words, {up:.1f} s of sound up")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
