"""Premiere Pro export (slice S5): the edit plan as a Final Cut Pro 7 XML that David opens and changes in Premiere.

    python -m pipeline.edit.premiere runs/<run_id> [--test-overview] [--no-render] [--out=<folder>]

Writes runs/<run_id>/premiere/ (later rounds premiere_r2/, ... once David has saved a project in the last one):
  <run_id>.xml        import with File > Import; save the .prproj in this folder so the pipeline can read his edits
  overlays/           transparent ProRes 4444 clips: the cursor (cut into one clip per move) and one per Epic Pen mark
  overview/           overview-mark images (rectangles sized to their target)
  privacy/            with privacy blurs (R116): blurred crops of the recording, frame-sized, transparent around the box
  captions.xml        the captions as TTML, each cue in its grid position (R53): import it, drag it to 0:00 on the
                      camera sequence, delete the one-frame anchor cue at 0:00 (it makes every cue land on its words,
                      R54). FCP 7 XML has no captions.
  captions.srt        the same cues without positions, as a fallback
  <run>_full.xml      with graphics (R69, R97): the whole video; its Captions track holds the cues as PNG clips (R101)
  caption_titles.json, titles/   with captions.titles on (R102): one .mogrt per cue of the full sequence, for its
                      empty Caption titles track. `python -m pipeline.edit.ppro.project <this folder>` has Premiere
                      build <run>_full.prproj here with them in place; the PNG Captions track comes in switched off.
  export_report.json  what went where, and what the XML could not carry
  edit_plan.json      the plan this export was made from, so a later re-plan can't change what the read-back
                      (pipeline.edit.readback) compares his edits with

Layout (R17, R42, R48-R51; David, 2026-10-06):
  "<run> camera" (top)  V1 the nest, with the camera as Scale/Center keyframes; V2+ overview marks in screen space;
                        A1 narration, one clip per line (two or more when a beat splits it, R62).
  "<run> source" (nest) V1 the recording (cuts, freezes as stills, R83's transitions on its cuts); then, only when
                        the plan has privacy blurs, "Privacy blurs N" (R116, privacy_blurs); the cursor; the Epic Pen
                        marks. Zoom the nest, never the footage inside it, so the cursor, marks and blurs stay on
                        their targets.

Conventions are Premiere's own FCP XML export's: Center = (where the clip's centre lands - frame / 2) / media size,
y down; Scale in % of the media's size; Rotation in degrees clockwise; keyframe <when> in the clip's in/out frames;
stills carry a 1-hour in point. Premiere's XML keyframes are linear, like the camera (R45).
"""
import copy
import hashlib
import json
import math
import shutil
import uuid
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

from pipeline.config import EXERCISES, ROOT, tool
from pipeline.edit.slides import FONT
from pipeline.narration import timing

REMOTION = ROOT / "remotion"
ARROW_AI = Path(r"D:\Videos\QuickSeries\Screenshots\Arrow01.ai")   # David's roadmap arrow (ep02 0:22-0:34)
STILL_IN_HOURS = 1
MASK_PAD_PX, MASK_BLUR_PX = 6, 14     # R116: EditPass's PrivacyMasks (the box grown 6 px a side, CSS blur(14px), a
MASK_HANDLE_S = 1.0                   # Gaussian of that sigma); media either side of a blur piece, to extend it


# ---------------------------------------------------------------------------------------------------- XML helpers
def sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el


def rate(parent, fps):
    r = sub(parent, "rate")
    sub(r, "timebase", int(round(fps)))
    sub(r, "ntsc", "FALSE")
    return r


def pathurl(p):
    p = str(Path(p).resolve()).replace("\\", "/")
    drive, rest = p[0], p[2:]
    return f"file://localhost/{drive}%3a{quote(rest)}"


def fmt(v):
    if isinstance(v, float):
        out = f"{v:.6f}".rstrip("0").rstrip(".")
        return "0" if out in ("-0", "") else out
    return str(v)


class Files:
    """<file> elements: the full description the first time a file is used, a bare reference after that."""

    def __init__(self, fps):
        self.fps, self.ids = fps, {}

    def el(self, parent, path, *, frames, w=None, h=None, audio=None):
        key = str(Path(path).resolve())
        if key in self.ids:
            return sub(parent, "file", id=self.ids[key])
        fid = self.ids[key] = f"file-{len(self.ids) + 1}"
        f = sub(parent, "file", id=fid)
        sub(f, "name", Path(path).name)
        sub(f, "pathurl", pathurl(path))
        rate(f, self.fps)
        sub(f, "duration", frames)
        media = sub(f, "media")
        if w:
            sc = sub(sub(media, "video"), "samplecharacteristics")
            rate(sc, self.fps)
            sub(sc, "width", w)
            sub(sc, "height", h)
            sub(sc, "anamorphic", "FALSE")
            sub(sc, "pixelaspectratio", "square")
            sub(sc, "fielddominance", "none")
        if audio:
            a = sub(media, "audio")
            sc = sub(a, "samplecharacteristics")
            sub(sc, "depth", 16)
            sub(sc, "samplerate", audio["rate"])
            sub(a, "channelcount", audio["channels"])
        return f


def param(effect, pid, name, keys, *, vmin=None, vmax=None, point=False):
    """keys: [(when, value)]; one key = a static value. Point values are (horiz, vert)."""
    p = sub(effect, "parameter", authoringApp="PremierePro")
    sub(p, "parameterid", pid)
    sub(p, "name", name)
    if vmin is not None:
        sub(p, "valuemin", vmin)
        sub(p, "valuemax", vmax)

    def value(parent, v):
        if point:
            val = sub(parent, "value")
            sub(val, "horiz", fmt(v[0]))
            sub(val, "vert", fmt(v[1]))
        else:
            sub(parent, "value", fmt(v))

    value(p, keys[0][1])
    if len(keys) > 1:
        for when, v in keys:
            kf = sub(p, "keyframe")
            sub(kf, "when", when)
            value(kf, v)
    return p


def effect(clip, name, eid):
    e = sub(sub(clip, "filter"), "effect")
    sub(e, "name", name)
    sub(e, "effectid", eid)
    sub(e, "effectcategory", "motion")
    sub(e, "effecttype", "motion")
    sub(e, "mediatype", "video")
    sub(e, "pproBypass", "false")
    return e


def motion(clip, *, scale=None, rotation=None, center=None):
    e = effect(clip, "Basic Motion", "basic")
    param(e, "scale", "Scale", scale or [(0, 100.0)], vmin=0, vmax=1000)
    param(e, "rotation", "Rotation", rotation or [(0, 0.0)], vmin=-8640, vmax=8640)
    param(e, "center", "Center", center or [(0, (0.0, 0.0))], point=True)
    param(e, "centerOffset", "Anchor Point", [(0, (0.0, 0.0))], point=True)


def opacity(clip, keys):
    param(effect(clip, "Opacity", "opacity"), "opacity", "Opacity", keys, vmin=0, vmax=100)


def audio_pan(clip, value):
    """A sound clip's pan, -1 hard left to 1 hard right. A stereo file plays in stereo only as two clips, its first
    and second channels (sourcetrack trackindex 1 and 2) on two tracks panned -1 and 1: one clip of the first channel
    plays that channel alone, centred, and premiereChannelType "stereo" or outputchannelindex lose a side or fold it
    to mono (measured in Premiere's own export, 2026-10-16; GOTCHAS)."""
    e = sub(sub(clip, "filter"), "effect")
    for tag, v in (("name", "Audio Pan"), ("effectid", "audiopan"), ("effectcategory", "audiopan"),
                   ("effecttype", "audiopan"), ("mediatype", "audio")):
        sub(e, tag, v)
    p = sub(e, "parameter", authoringApp="PremierePro")
    for tag, v in (("parameterid", "pan"), ("name", "Pan"), ("valuemin", -1), ("valuemax", 1), ("value", value)):
        sub(p, tag, v)


class Seq:
    def __init__(self, name, sid, fps, w, h, frames):
        self.name = name
        self.el = ET.Element("sequence", id=sid)
        sub(self.el, "uuid", str(uuid.uuid5(uuid.NAMESPACE_URL, f"aidv/{name}/{sid}")))
        sub(self.el, "duration", frames)
        rate(self.el, fps)
        sub(self.el, "name", name)
        media = sub(self.el, "media")
        self.video = sub(media, "video")
        sc = sub(sub(self.video, "format"), "samplecharacteristics")
        rate(sc, fps)
        for k, v in (("width", w), ("height", h), ("anamorphic", "FALSE"), ("pixelaspectratio", "square"),
                     ("fielddominance", "none"), ("colordepth", 24)):
            sub(sc, k, v)
        self.audio = sub(media, "audio")
        sub(self.audio, "numOutputChannels", 2)
        asc = sub(sub(self.audio, "format"), "samplecharacteristics")
        sub(asc, "depth", 16)
        sub(asc, "samplerate", 48000)
        self.vtracks, self.atracks = [], []

    def track(self, kind, name):
        t = sub(self.video if kind == "video" else self.audio, "track", **{"MZ.TrackName": name})
        (self.vtracks if kind == "video" else self.atracks).append(t)
        return t


def close_tracks(seq):
    for t in seq.vtracks + seq.atracks:
        close_tracks_one(t)


def close_tracks_one(t):
    sub(t, "enabled", "TRUE")
    sub(t, "locked", "FALSE")


class Ids:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return f"clipitem-{self.n}"


def clipitem(track, ids, name, start, end, in_, out, duration, fps, alpha="none", **extra):
    c = sub(track, "clipitem", id=ids(), **extra)
    sub(c, "name", name)
    sub(c, "enabled", "TRUE")
    sub(c, "duration", duration)
    rate(c, fps)
    for k, v in (("start", start), ("end", end), ("in", in_), ("out", out)):
        sub(c, k, v)
    sub(c, "alphatype", alpha)
    return c


# ---------------------------------------------------------------------------------------------- media helpers
def probe_frames(path, fps, whole=False):
    """Length in frames. whole=True rounds down, so an audio clip's out point never passes the end of its media."""
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True).stdout.strip()
    n = float(out) * fps
    return int(math.floor(n + 1e-6)) if whole else int(math.ceil(n - 1e-6))


def speed_clip(raw, seg, frames, fps, out_dir):
    """A sped-up piece rendered by ffmpeg at its edit speed, so Premiere plays it at 1x. FCP 7 XML can carry a speed
    (Time Remap), but how Premiere reads its in and out points is untested; a file of its own is exact, as a freeze's
    still is."""
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"speed_{round(seg['src_in'] * fps):06d}_{seg['speed']}x.mp4"
    if not out.exists():
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{seg['src_in']:.4f}", "-i", str(raw),
                        "-t", f"{seg['src_out'] - seg['src_in']:.4f}", "-vf",
                        f"setpts=(PTS-STARTPTS)/{seg['speed']},fps={fps}", "-frames:v", str(frames), "-an",
                        "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out


def npx():
    return shutil.which("npx") or "npx"


def bundle(out_dir):
    pub = out_dir.parent / "_public"
    pub.mkdir(exist_ok=True)                          # the overlays use no media: keep the bundle small
    (pub / "fonts").mkdir(exist_ok=True)              # but a title card (R39) uses David's Arial Bold Italic
    shutil.copyfile(FONT, pub / "fonts" / "arialbi.ttf")
    subprocess.run([npx(), "remotion", "bundle", "src/index.ts", f"--out-dir={out_dir}", f"--public-dir={pub}",
                    "--log=warn"], cwd=REMOTION, check=True)


def render_overlay(bundle_dir, plan, only, a, b, out, tmp):
    """Frames a..b (inclusive) of one source-space layer, transparent (ProRes 4444 with alpha)."""
    props = tmp / f"props_{only.replace(':', '_')}.json"
    props.write_text(json.dumps({**plan, "only": only}), encoding="utf-8")
    subprocess.run([npx(), "remotion", "render", str(bundle_dir), "OverlayClip", str(out), f"--props={props}",
                    f"--frames={a}-{b}", "--codec=prores", "--prores-profile=4444", "--pixel-format=yuva444p10le",
                    "--image-format=png", "--muted", "--log=warn",
                    "--timeout=90000"], cwd=REMOTION, check=True)   # a busy PC loads the overlay fonts slowly (round 6)


# ------------------------------------------------------------------------------------------------- the export
def camera_keys(keys, fps, W, H):
    """Plan camera keys -> nest Basic Motion keys. A change on a cut (two keys in one frame) becomes old on the frame
    before and new on the frame itself. Premiere interpolates Scale and Center linearly, but Center is s times the
    planner's linear (x, y), so moves are bisected until the two paths differ by under 1 px."""
    def at(k):
        s = k["s"]
        return s * 100.0, (-(k["x"] - W / 2) * s / W, -(k["y"] - H / 2) * s / H)

    def err(a, b, u):                                    # px between Premiere's line and the planner's path at u
        m = {kk: a[kk] + (b[kk] - a[kk]) * u for kk in ("t", "s", "x", "y")}
        ca, cb, cm = at(a)[1], at(b)[1], at(m)[1]
        return max(abs(ca[0] + (cb[0] - ca[0]) * u - cm[0]) * W, abs(ca[1] + (cb[1] - ca[1]) * u - cm[1]) * H), m

    def refine(a, b, out):
        if round(b["t"] * fps) - round(a["t"] * fps) <= 1:
            return
        worst = max((err(a, b, u) for u in (0.25, 0.5, 0.75)), key=lambda e: e[0])
        if worst[0] > 1.0:
            mid = err(a, b, 0.5)[1]
            refine(a, mid, out)
            out.append((round(mid["t"] * fps), *at(mid)))
            refine(mid, b, out)

    out = []
    for i, k in enumerate(keys):
        f = round(k["t"] * fps)
        if out and f <= out[-1][0]:                      # a cut: the old view holds through the frame before
            prev = out[-2][0] if len(out) > 1 else -1
            if f - 1 > prev:
                out[-1] = (f - 1, *out[-1][1:])
        elif i:
            refine(keys[i - 1], k, out)
        out.append((f, *at(k)))
    return [(f, s) for f, s, _ in out], [(f, c) for f, _, c in out]


def nest_track(t1, ids, nest, run_id, N, fps, scale_k, center_k):
    """The camera sequence's V1: the nest under the camera keys, in one piece. R83's transitions are inside the
    nest, on the recording's cuts (work_transitions): the nest is continuous, so a transition out here would blend a
    frame into itself (Fable's review, 2026-10-07)."""
    c = clipitem(t1, ids, f"{run_id} source", 0, N, 0, N, N, fps)
    c.remove(c.find("alphatype"))
    c.append(nest.el)
    motion(c, scale=scale_k, center=center_k)


def work_transitions(v1, trs, fps):
    """R83's transitions on the nest's Recording track, at the cuts of Claude's work: the outgoing piece runs on into
    the footage the cut skipped (its handle), so the picture before the cut gives way to the one after it. Premiere's
    FCP XML convention: a clip's start (end) is -1 where a transition holds it. Returns ([(item, out_clip, in_clip,
    frame)], [(frame, why) left out])."""
    clips = [c for c in v1 if c.tag == "clipitem"]
    by_start = {int(c.find("start").text): c for c in clips}
    by_end = {int(c.find("end").text): c for c in clips}
    done, skipped = [], []
    for a, tr in sorted(trs.items()):
        cin, cout = by_start.get(a), by_end.get(a)
        if cin is None or cout is None:
            skipped.append((a, "no cut of the recording there"))
            continue
        d = min(round(tr["s"] * fps), int(cin.find("end").text) - a)
        handle = int(cout.find("duration").text) - int(cout.find("out").text)
        if handle < d:                                    # a sped-up piece is a file of its own, with no footage after
            skipped.append((a, f"the piece before the cut has {handle} frames after it, {d} needed"))
            continue
        ti = ET.Element("transitionitem")
        for tag, v in (("start", a), ("end", a + d), ("alignment", tr.get("align", "start"))):
            sub(ti, tag, v)
        rate(ti, fps)
        e = sub(ti, "effect")
        for tag, v in (("name", tr["type"]), ("effectid", tr["type"]), ("effectcategory", tr["type"]),
                       ("effecttype", "transition"), ("mediatype", "video"), ("wipecode", 0),
                       ("wipeaccuracy", 100), ("startratio", 0), ("endratio", 1), ("reverse", "FALSE")):
            sub(e, tag, v)
        v1.insert(list(v1).index(cin), ti)
        cout.find("end").text, cin.find("start").text = "-1", "-1"
        done.append((ti, cout, cin, a))
    return done, skipped


def blur_media(src, first, count, box, tag, out_dir, fps, W, H):
    """count frames of src from its frame `first` (count None: src is a still), blurred inside box (frame px, x0 y0 x1
    y1) and transparent elsewhere, frame-sized: ProRes 4444 with alpha like the cursor and mark clips, or a PNG for a
    still. Video is cropped and blurred in YUV, so the box keeps the recording's colours. The name carries a hash of
    what made the file: a re-export writes a new file instead of one an open project holds (Premiere locks its media,
    GOTCHAS), and an existing file is reused."""
    x0, y0, x1, y1 = box
    made = json.dumps({"src": src.name, "bytes": src.stat().st_size, "first": first, "count": count, "box": box,
                       "blur": MASK_BLUR_PX, "fps": fps, "frame": [W, H]}, sort_keys=True)
    h = hashlib.sha256(made.encode("utf-8")).hexdigest()[:8]
    tag = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(tag))
    path = out_dir / (f"blur_{tag}_{src.stem}_{h}.png" if count is None
                      else f"blur_{tag}_{src.stem}_{first:06d}_{count}f_{h}.mov")
    if path.exists():
        return path
    out_dir.mkdir(parents=True, exist_ok=True)
    part = out_dir / f"_part_{path.name}"
    crop = f"crop={x1 - x0}:{y1 - y0}:{x0}:{y0},gblur=sigma={MASK_BLUR_PX}"
    if count is None:
        cmd = ["-i", str(src), "-vf", f"{crop},format=rgba,pad={W}:{H}:{x0}:{y0}:color=black@0", "-frames:v", "1",
               "-update", "1", "-f", "image2"]
    else:                     # half a frame early, so the first frame kept is `first` (raw.mp4 has a frame at n / fps)
        cmd = ["-ss", f"{max(0.0, (first - 0.5) / fps):.6f}", "-i", str(src), "-frames:v", str(count), "-an", "-vf",
               f"setpts=N/({fps}*TB),format=yuv444p,{crop},format=yuva444p10le,pad={W}:{H}:{x0}:{y0}:color=black@0",
               "-r", str(fps), "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-alpha_bits",
               "16", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
               "-f", "mov"]
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", *cmd, str(part)], check=True)
    part.replace(path)
    return path


def correction_media(plate, box, out_dir, W, H):
    """R173: a frame-sized PNG, transparent but for the plate's pixels inside box (source px). Named by a hash of what
    made it, so a re-export writes a new file instead of one an open project holds."""
    from PIL import Image
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    made = json.dumps({"plate": plate.name, "bytes": plate.stat().st_size, "box": [x0, y0, x1, y1], "frame": [W, H]},
                      sort_keys=True)
    path = out_dir / f"correction_{plate.stem}_{hashlib.sha256(made.encode()).hexdigest()[:8]}.png"
    if not path.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        im.paste(Image.open(plate).convert("RGBA").crop((x0, y0, x1, y1)), (x0, y0))
        im.save(path)
    return path


def corrections(nest, ids, files, plan, run_dir, out, fps, W, H, N, still_in, still_dur, report):
    """R173: each recording flaw the plan covers (plan["corrections"], pipeline.edit.plan.correction_spans) as a still
    clip on a Corrections track of the camera nest, above the recording and below the blurs, cursor and marks, so it
    follows the camera like the recording; David can switch a track off to see the flaw it covers."""
    cs = plan.get("corrections") or []
    lanes = []
    for c in sorted(cs, key=lambda c: c["t0"]):
        a, b = c.get("frames") or (math.ceil(c["t0"] * fps - 1e-6), math.ceil(c["t1"] * fps - 1e-6))  # the
        a, b = max(0, a), min(N, b)                       # plan's edit frames [a, b), the proxy's too
        if b <= a:
            report["not_carried"].append(f"correction {c['id']}: no frame in the edit; left out")
            continue
        png = correction_media(run_dir / c["plate"], c["box"], out / "corrections", W, H)
        lane = next((ln for ln in lanes if ln["end"] <= a), None)
        if lane is None:
            lane = {"end": 0, "track": nest.track("video", f"Corrections {len(lanes) + 1}")}
            lanes.append(lane)
        ci = clipitem(lane["track"], ids, f"correction {c['id']}: {c['why']}"[:60], a, b, still_in, still_in + b - a,
                      still_dur, fps, alpha="straight")
        files.el(ci, png, frames=still_dur, w=W, h=H)
        lane["end"] = b
    if cs:
        report["nest"]["Corrections"] = (
            f"{len(cs)} correction(s) (R173) on {len(lanes)} track(s) above the recording: " + "; ".join(
                f"{c['id']} {timecode(round(c['t0'] * fps), fps)}-{timecode(round(c['t1'] * fps), fps)} ({c['why']})"
                for c in cs) + ". Media in corrections/: frame-sized, transparent but for the clean picture")


def privacy_blurs(nest, ids, files, plan, shown, trs, out, fps, W, H, N, still_in, still_dur, report):
    """R116: each blur David chose (R56: the plan's privacy_masks, from privacy_decisions.json) as clips in the nest,
    on tracks of their own above the recording and below the cursor and marks, so it follows the camera and he can
    trim, move or switch it off; the recording itself is untouched. A blur covers the frames EditPass blurs (t0 <= t
    <= t1) and is cut where the recording is: one piece per piece of the recording it spans (shown: start, end,
    media, the media frame at start, its length or None for a still), each a blurred crop of that piece's own frames
    (raw.mp4 from the same in point, a sped-up piece's file, a freeze's still), with handles. A piece that reaches a
    cut with a transition (R83, R105; trs: frame -> (length, alignment)) runs on with its media through the frames
    the transition shows of it, as the recording does; overlapping pieces go on a further track. Returns
    [(start, end, mask, [piece])] in nest frames, for the report and the full sequence's markers (R106)."""
    masks = plan.get("privacy_masks") or []
    handle = round(MASK_HANDLE_S * fps)
    early = lambda d, align: {"center": d // 2, "end": d}.get(align, 0)   # transition frames before the cut
    placed, todo = [], []
    for m in masks:
        a = max(0, math.ceil(m["t0"] * fps - 1e-6))
        b = min(N, math.floor(m["t1"] * fps + 1e-6) + 1)
        bx = [max(0, math.floor(m["box"][0]) - MASK_PAD_PX), max(0, math.floor(m["box"][1]) - MASK_PAD_PX),
              min(W, math.ceil(m["box"][2]) + MASK_PAD_PX), min(H, math.ceil(m["box"][3]) + MASK_PAD_PX)]
        if b <= a or bx[2] <= bx[0] or bx[3] <= bx[1]:
            report["not_carried"].append(f"privacy blur {m['id']}: no frame or no box inside the picture; left out")
            continue
        name, mine = f"blur {m['why']} ({m['id']})", []
        for s0, s1, src, i0, n in shown:
            x0, x1 = max(a, s0), min(b, s1)
            if x1 <= x0:
                continue
            if x1 == s1 and s1 in trs:
                x1 += trs[s1][0] - early(*trs[s1])
            if x0 == s0 and s0 in trs:
                x0 -= early(*trs[s0])
            if n is None:                                 # a freeze: its still, blurred, held as long as needed
                mine.append((x0, x1, blur_media(src, 0, None, bx, m["id"], out / "privacy", fps, W, H), None, None))
                continue
            m0 = i0 + x0 - s0                             # the media frame under x0, as on the recording track
            if m0 < 0:
                x0, m0 = x0 - m0, 0
            x1 = min(x1, x0 + n - m0)
            if x1 <= x0:
                continue
            h0, h1 = min(handle, m0), max(0, min(handle, n - (m0 + x1 - x0)))
            mov = blur_media(src, m0 - h0, h0 + x1 - x0 + h1, bx, m["id"], out / "privacy", fps, W, H)
            mine.append((x0, x1, mov, h0, h0 + x1 - x0 + h1))
        placed.append((a, b, m, mine))
        todo += [(p, name) for p in mine]
    lanes = []                                            # packed onto as few tracks as fit, as the marks are
    for (x0, x1, media, i0, dur), name in sorted(todo, key=lambda pn: pn[0][0]):
        lane = next((ln for ln in lanes if ln["end"] <= x0), None)
        if lane is None:
            lane = {"end": 0, "track": nest.track("video", f"Privacy blurs {len(lanes) + 1}")}
            lanes.append(lane)
        if dur is None:
            c = clipitem(lane["track"], ids, name, x0, x1, still_in, still_in + x1 - x0, still_dur, fps,
                         alpha="straight")
            files.el(c, media, frames=still_dur, w=W, h=H)
        else:
            c = clipitem(lane["track"], ids, name, x0, x1, i0, i0 + x1 - x0, dur, fps, alpha="straight")
            files.el(c, media, frames=dur, w=W, h=H)
        lane["end"] = x1
    if placed:
        report["nest"]["Privacy"] = (
            f"{len(placed)} blur(s) (R116) in {len(todo)} clip(s) on {len(lanes)} track(s) between the recording "
            "and the cursor, one clip per piece of the recording a blur spans: " + "; ".join(
                f"{m['id']} ({m['why']}) {timecode(a, fps)}-{timecode(b, fps)} on \"{plan['run_id']} camera\", "
                f"{len(p)} piece(s)" for a, b, m, p in placed)
            + ". Media in privacy/: frame-sized, transparent but for the blurred box (ProRes 4444; a freeze's a PNG)")
    return placed


GRAPHICS = ("opening", "recap")
SLIDE_LEAD_S = 0.8                                        # pipeline.edit.slides: the recap's still slide before its voice


def camera_span(plan, fps, N, opening, recap):
    """The camera sequence's frames between the graphics: the opening and recap slides carry the Part 0 and recap
    lines (slides.json's sequences), so the camera starts a second before the first line after them and ends a second
    after the last line before the recap; else the opening and recap would play twice (full_take02)."""
    found = list(EXERCISES.glob(f"*/{plan['steps_file']}"))
    spec = found[0].parent / "slides.json" if found else None
    seqs = json.loads(spec.read_text(encoding="utf-8"))["sequences"] if spec and spec.exists() else {}
    gfx_ids = set(seqs.get("opening", [])) | set(seqs.get("recap", []))
    rest = [n for n in plan["narration"] if n["step"] not in gfx_ids]
    c_in, c_out = 0, N
    lead = ((plan["settings"]["cuts"].get("section_transition") or {}).get("s", 1.0)   # the opening's dissolve is
            + plan["settings"]["pacing"]["gap_between_lines"])                       # over before the voice starts
    if opening and rest and any(n["step"] in seqs.get("opening", []) for n in plan["narration"]):
        c_in = max(0, round((min(n["start"] for n in rest) - lead) * fps))
    if recap and rest and any(n["step"] in seqs.get("recap", []) for n in plan["narration"]):
        c_out = min(N, round((max(n["start"] + n["length"] for n in rest) + 1.0) * fps))
    return c_in, c_out


def logo_outro(run_dir, plan, fps, W, H):
    """R96: the logo outro as one file at the sequence's size and rate (graphics/logo_outro_<key>.mp4): black, the
    logo fading in, the music at its level and fading out, all from edit_settings.json's logo_outro (read from David's
    'Outro' sequence). Each version of the settings gets its own file: a project David has open locks the one it
    uses, and keeps playing it."""
    lg = plan["settings"].get("logo_outro")
    if not lg:
        return None
    key = json.dumps({**lg, "fps": fps, "w": W, "h": H}, sort_keys=True)
    path = run_dir / "graphics" / f"logo_outro_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:8]}.mp4"
    if path.exists():
        return path
    v, L = lg["video"], lg["length_s"]
    tail = max(0.0, L - v["at_s"] - probe_frames(v["path"], fps, whole=True) / fps)
    chains = [f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={fps},"
              f"fade=t=in:st=0:d={v['fade_in_s']},tpad=start_mode=add:start_duration={v['at_s']}:stop_mode=add:"
              f"stop_duration={tail:.4f}:color=black,trim=duration={L},format=yuv420p[v]"]
    for i, m in enumerate(lg["music"], 1):
        f0, f1 = m["fade_out"]
        chains.append(f"[{i}:a]atrim=duration={L},aresample=48000,volume={m['level']},"
                      f"afade=t=out:st={f0}:d={f1 - f0}:curve=tri[m{i}]")
    n = len(lg["music"])
    chains.append("".join(f"[m{i}]" for i in range(1, n + 1)) + f"amix=inputs={n}:normalize=0,"
                  f"aformat=channel_layouts=stereo[a]")
    cmd = [tool("ffmpeg"), "-v", "error", "-y", "-i", v["path"]]
    for m in lg["music"]:
        cmd += ["-i", m["path"]]
    cmd += ["-filter_complex", ";".join(chains), "-map", "[v]", "-map", "[a]", "-t", str(L), "-c:v", "libx264",
            "-crf", "16", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(path)]
    path.parent.mkdir(exist_ok=True)
    subprocess.run(cmd, check=True)
    return path


def caption_place(c, pl, W, H, bw, bh):
    """Top-left corner of a cue's box of bw x bh at the planner's spot (R53; pl: the planner's caption layout). The
    box keeps its edge on its grid row (the bottom edge on the bottom row, the top edge on the top row, the middle in
    the middle) and its centre x; a graphic's cue, with no spot, sits bottom centre."""
    n = c["text"].count("\n") + 1
    pl_h = n * pl["size_px"] * pl["line_height"] + 2 * pl["pad_y_px"]            # the planner's box height
    pos = c.get("pos") or {"where": "bottom-centre", "cx": W / 2, "y": H - pl["margin_bottom_px"] - pl_h}
    row = pos["where"].split("-")[0]
    y = {"top": pos["y"], "middle": pos["y"] + pl_h / 2 - bh / 2, "bottom": pos["y"] + pl_h - bh}[row]
    return min(max(0, pos["cx"] - bw / 2), W - bw), y


def caption_stills(out, cues, plan, W, H):
    """One transparent full-frame PNG per cue in David's look (captions.stills), at the planner's spot: [(cue, png)]."""
    from PIL import Image, ImageDraw, ImageFont
    st, pl = plan["settings"]["captions"]["stills"], plan["settings"]["captions"]   # pl: the planner's layout
    font = ImageFont.truetype(st["font_file"], st["size_px"])
    step, pad = round(st["size_px"] * st["line_height"]), st["pad_px"]
    (out / "captions").mkdir(exist_ok=True)
    made = []
    for i, c in enumerate(cues):
        lines = c["text"].split("\n")
        tw = max(round(font.getlength(l)) for l in lines)
        bw, bh = tw + 2 * pad, len(lines) * step + 2 * pad
        x, y = caption_place(c, pl, W, H, bw, bh)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([round(x), round(y), round(x + bw), round(y + bh)], radius=st["corner_radius_px"],
                            fill=st["box_color"])
        for k, line in enumerate(lines):
            lw = font.getlength(line)
            d.text((x + (bw - lw) / 2, y + pad + k * step), line, font=font, fill=st["text_color"])
        png = out / "captions" / f"cap_{i:03d}.png"
        im.save(png)
        made.append((c, png))
    return made


def graphic_cues(run_dir, plan, seq, at):
    """The captions of the line an avatar graphic speaks (avatar/avatar.json's "graphics", pipeline.edit.avatar),
    with the graphic's media starting at `at` seconds on the full sequence. Slides graphics have none here yet."""
    log_p = run_dir / "avatar" / "avatar.json"
    g = (json.loads(log_p.read_text(encoding="utf-8")).get("graphics") or {}).get(seq) if log_p.exists() else None
    if not g:
        return []
    from pipeline.edit.plan import captions
    meta = timing.of(g)                                       # R227: the line's own word times
    return captions(meta["words"], meta["display_text"], at + g["voice_at_s"], plan["settings"]["captions"])


def assembly(run_dir, out, plan, camera_el, fps, W, H, N, blurs=()):
    """R69, R34: the opening and recap graphics (runs/<id>/graphics/<seq>.mp4, pipeline.edit.slides --render) around
    the camera sequence, nested, with the section dissolve at each join: <run> full, in <run>_full.xml, so the main
    XML (which the read-back compares against) is unchanged. The dissolve out of the opening runs on the slide's
    tail hold (its handle); into the recap it ends at the cut, over the recap's still lead-in before its voice.
    blurs (privacy_blurs) get a marker where each starts on the full sequence (R106, R116)."""
    log_p = run_dir / "avatar" / "avatar.json"                  # an avatar graphic names its own file (each render
    named = (json.loads(log_p.read_text(encoding="utf-8")).get("graphics") or {}) if log_p.exists() else {}  # gets one)
    gfx = {k: run_dir / (named.get(k) or {}).get("file", f"graphics/{k}.mp4") for k in GRAPHICS}
    gfx = {k: p for k, p in gfx.items() if p.exists()}
    if not gfx and not (plan["settings"].get("export") or {}).get("full_without_graphics"):
        return None                                   # (a first pass with no graphics yet still wants the full
                                                      # sequence, for its caption titles and Premiere's build, R104)
    sec = plan["settings"]["cuts"].get("section_transition") or {"type": "Cross Dissolve", "s": 1.0}
    d = round(sec["s"] * fps)
    cam = copy.deepcopy(camera_el)
    ids = Ids()
    ids.n = max([int(e.get("id").rsplit("-", 1)[1]) for e in cam.iter("clipitem") if e.get("id")] + [0])
    files = Files(fps)
    taken = max([int(e.get("id").rsplit("-", 1)[1]) for e in cam.iter("file") if e.get("id")] + [0])
    files.ids = {f"_taken_{i}": None for i in range(taken)}     # new file ids follow the camera sequence's
    lo = probe_frames(gfx["opening"], fps, whole=True) if "opening" in gfx else 0
    lr = probe_frames(gfx["recap"], fps, whole=True) if "recap" in gfx else 0
    dr = min(d, round(SLIDE_LEAD_S * fps)) if lr else 0
    o_out = max(0, lo - d) if lo else 0                   # the opening ends a dissolve before its media does
    c_in, c_out = camera_span(plan, fps, N, bool(lo), bool(lr))   # the graphics carry their own lines
    # into the recap the dissolve starts at the cut and runs on the camera's tail, as out of the opening it runs on the
    # opening's: Premiere imports a dissolve that ends at the cut on the outgoing clip only, so it played as a fade and
    # a hard cut (csc13 test, 2026-10-12). The camera gives up dr frames after its last line for that tail; the recap
    # starts at the cut with its still lead-in under the dissolve, so its voice starts where it did.
    said = max([n["start"] + n["length"] for n in plan["narration"] if n["start"] * fps < c_out] + [0.0])
    k = min(dr, max(0, c_out - math.ceil((said + 0.2) * fps))) if lr else 0
    N0, N = N, c_out - c_in - k
    r_in = dr - k if lr else 0                            # k == dr: the recap's whole lead-in plays, under the dissolve
    total = o_out + N + lr - (dr - k if k < dr else 0) if lr else o_out + N
    logo = logo_outro(run_dir, plan, fps, W, H)           # R96: a hard cut to it after the last graphic
    lgf = probe_frames(logo, fps, whole=True) if logo else 0
    end, total = total, total + lgf
    full = Seq(f"{plan['run_id']} full", "sequence-3", fps, W, H, total)
    v1, a1 = full.track("video", "Graphics and camera"), full.track("audio", "Graphics and narration")

    def transition(track, start, end, align):
        ti = sub(track, "transitionitem")
        for tag, v in (("start", start), ("end", end), ("alignment", align)):
            sub(ti, tag, v)
        rate(ti, fps)
        e = sub(ti, "effect")
        for tag, v in (("name", sec["type"]), ("effectid", sec["type"]), ("effectcategory", "Dissolve"),
                       ("effecttype", "transition"), ("mediatype", "video")):
            sub(e, tag, v)

    def media_clip(track, kind, name, start, end, in_, out_, path, n, video, channel=1, pan=None):
        c = clipitem(track, ids, name, start, end, in_, out_, n, fps)
        if not video:
            c.remove(c.find("alphatype"))
        files.el(c, path, frames=n, w=W, h=H, audio={"rate": 48000, "channels": 2})
        if not video:
            st = sub(c, "sourcetrack")
            sub(st, "mediatype", "audio")
            sub(st, "trackindex", channel)
            if pan is not None:
                audio_pan(c, pan)
        return c

    if lo:
        media_clip(v1, "video", "opening", 0, -1, 0, o_out, gfx["opening"], lo, True)
        transition(v1, o_out, o_out + d, "start")
    c = clipitem(v1, ids, f"{plan['run_id']} camera", -1 if lo else 0, -1 if lr and k else N + o_out, c_in,
                 c_out - k, N0, fps)
    c.remove(c.find("alphatype"))
    c.append(cam)
    if lr:
        if k:
            transition(v1, o_out + N, o_out + N + k, "start")
        media_clip(v1, "video", "recap", -1 if k else o_out + N, end, r_in, lr, gfx["recap"], lr, True)
    if lgf:
        media_clip(v1, "video", "logo outro", end, total, 0, lgf, logo, lgf, True)
    if lo:
        media_clip(a1, "audio", "opening", 0, o_out, 0, o_out, gfx["opening"], lo, False)
    c = clipitem(a1, ids, f"{plan['run_id']} camera", o_out, o_out + N, c_in, c_out - k, N0, fps)
    c.remove(c.find("alphatype"))
    sub(c, "sequence", id=cam.get("id"))
    st = sub(c, "sourcetrack")
    sub(st, "mediatype", "audio")
    sub(st, "trackindex", 1)
    if plan.get("click_sound"):                           # R137: the camera's Clicks track (its A2), on its own track
        a2 = full.track("audio", "Clicks")                # here too, so David sets the level on the sequence he opens
        c = clipitem(a2, ids, f"{plan['run_id']} camera clicks", o_out, o_out + N, c_in, c_out - k, N0, fps)
        c.remove(c.find("alphatype"))
        sub(c, "sequence", id=cam.get("id"))
        st = sub(c, "sourcetrack")
        sub(st, "mediatype", "audio")
        sub(st, "trackindex", 2)
    if lr:
        media_clip(a1, "audio", "recap", o_out + N, end, r_in, lr, gfx["recap"], lr, False)
    if lgf:                                               # the music in stereo: its channels on two tracks (audio_pan)
        media_clip(a1, "audio", "logo outro", end, total, 0, lgf, logo, lgf, False, pan=-1)
        media_clip(full.track("audio", "Logo outro right"), "audio", "logo outro right", end, total, 0, lgf, logo, lgf,
                   False, channel=2, pan=1)
    # the captions of the whole video: the intro's line, the camera's cues where the camera plays, the outro's line
    shift, c0, c1 = (o_out - c_in) / fps, c_in / fps, (c_in + N) / fps
    cam_cues = [{**c, "start": round(c["start"] + shift, 3), "end": round(min(c["end"], c1) + shift, 3)}
                for c in plan["captions"]["cues"] if c0 - 0.01 <= c["start"] < c1]
    cues = ((graphic_cues(run_dir, plan, "opening", 0.0) if lo else []) + cam_cues
            + (graphic_cues(run_dir, plan, "recap", (o_out + N - r_in) / fps) if lr else []))
    n_gfx = len(cues) - len(cam_cues)
    if n_gfx:
        write_ttml(out / "captions_full.xml", cues, plan["captions"].get("style", {}), fps, W, H)
        write_srt(out / "captions_full.srt", cues, fps)
    n_still = 0                    # the captions as clips in David's look, one per cue, on a track of their own
    if plan["settings"]["captions"].get("stills"):
        capt = full.track("video", "Captions")
        still_in = int(STILL_IN_HOURS * 3600 * fps)
        for c, png in caption_stills(out, cues, plan, W, H):
            a, b = max(0, round(c["start"] * fps)), min(end, round(c["end"] * fps))   # none over the logo (R96)
            if b <= a:
                continue
            ci = clipitem(capt, ids, c["text"].replace("\n", " ")[:40], a, b, still_in, still_in + b - a,
                          12 * still_in, fps, alpha="straight")
            files.el(ci, png, frames=12 * still_in, w=W, h=H)
            motion(ci)
            n_still += 1
    n_titles = 0                   # R102: the same cues as editable titles, which Premiere adds (pipeline.edit.ppro)
    if plan["settings"]["captions"].get("titles", {}).get("enabled"):
        from pipeline.edit.ppro import titles
        full.track("video", titles.TRACK)                   # empty here: the titles go on it in Premiere
        pl = plan["settings"]["captions"]
        n_titles = len(titles.build(out, cues, lambda c, bw, bh: caption_place(c, pl, W, H, bw, bh), W, H, fps,
                                    full.name, end, size_px=pl["titles"].get("size_px", titles.SIZE_PX),   # R126
                                    box_hex=pl["titles"].get("box_color")))   # R192
    checks = []                    # R106: what David should check, as times on this sequence, each one a marker
    for n in plan["narration"]:                           # R103: clicks in a clip's time, repaired or left
        for t, name, says in ([(t, "Click repaired (R103)", "A click in the narration was repaired here")
                               for t in n.get("clicks", [])]
                              + [(t, "Click left (R103)", "A click the repair couldn't remove is here")
                                 for t in n.get("clicks_left", [])]):
            part = next((q for q in n["parts"] if q["in"] <= t < q["out"]), None)
            pf = round((part["at"] + t - part["in"]) * fps) if part else None
            if pf is not None and c_in <= pf < c_in + N:
                meta = timing.of(n)
                word = next((w["word"] for w in meta["words"] if w["start"] >= t), None)  # where, in words
                checks.append((o_out + pf - c_in, name, says
                               + (f", just before \"{word.strip(' ,.')}\"" if word else "")
                               + ". Listen for anything left of it."))
    lc = run_dir / "linecheck" / "findings.json"          # R85, R106: each timed line-check finding, if the check
    if lc.exists() and lc.stat().st_mtime >= (run_dir / "edit_plan.json").stat().st_mtime:   # is of this plan
        for f in json.loads(lc.read_text(encoding="utf-8")):
            pf = round(f["t"] * fps) if f.get("t") is not None else None
            if pf is not None and c_in <= pf < c_in + N:
                checks.append((o_out + pf - c_in, f"Line check {f['rule']} (R85)", f["text"]))
    for a, b, m, _ in blurs:                              # R116: each blur, where the camera plays it
        if a < c_in + N and b > c_in:
            at, until = o_out + max(a, c_in) - c_in, o_out + min(b, c_in + N) - c_in
            checks.append((at, "Privacy blur (R116)", f"Blur {m['id']} ({m['why']}) from here to "
                           f"{timecode(until, fps)}: check it covers the text all the way"))
    for c in plan.get("corrections") or []:               # R173: each correction, where the camera plays it
        a, b = c.get("frames") or (math.ceil(c["t0"] * fps - 1e-6), math.ceil(c["t1"] * fps - 1e-6))
        if a < c_in + N and b > c_in:
            at, until = o_out + max(a, c_in) - c_in, o_out + min(b, c_in + N) - c_in
            checks.append((at, "Correction (R173)", f"Correction {c['id']} ({c['why']}) from here to "
                           f"{timecode(until, fps)}: a clean picture over the recording; switch the Corrections "
                           "track off in the camera sequence to see what it covers"))
    for at, name, comment in sorted(checks):
        mk = sub(full.el, "marker")
        for tag, v in (("comment", comment), ("name", name), ("in", at), ("out", -1)):
            sub(mk, tag, v)
    close_tracks(full)
    if n_titles and n_still:       # the PNG captions stay, switched off, until the titles have replaced them
        capt.find("enabled").text = "FALSE"
    root = ET.Element("xmeml", version="4")
    root.append(full.el)
    ET.indent(root, "\t")
    path = out / f"{plan['run_id']}_full.xml"
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode")
                    + "\n", encoding="utf-8")
    return (f"{path.name}: <run> full = " + " + ".join([f"opening ({o_out / fps:.1f}s)"] * bool(lo) + [
            f"camera ({N / fps:.1f}s)"] + [f"recap ({(lr - r_in) / fps:.1f}s)"] * bool(lr)
            + [f"logo outro ({lgf / fps:.1f}s, R96)"] * bool(lgf))
            + f", a {sec['type']} at each join (R34, R69). Import it instead of the main XML to review the whole "
            "video; the camera and source sequences come in with it. "
            + (f"The captions are on its Captions track ({n_still} clips in David's look, nothing to import). "
               if n_still and not n_titles else "")
            + (f"{n_titles} caption titles (editable, R102) go on its {titles.TRACK} track in Premiere "
               "(caption_titles.json; the PNG Captions track is kept, switched off). " if n_titles else "")
            + (f"captions_full.xml/.srt hold the same {len(cues)} cues ({n_gfx} of them the graphics' lines) as text, "
               "for YouTube or for importing instead" if n_gfx else "Captions go on the camera sequence (captions.xml)")
            + "".join(f". Check at {timecode(at, fps)} on \"{full.name}\": {name} (a marker there)"
                      for at, name, _ in sorted(checks)))


def timecode(frame, fps):
    """HH:MM:SS:FF, as Premiere shows a sequence time (whole-frame rates)."""
    r = round(fps)
    s, f = divmod(int(frame), r)
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}:{f:02d}"


def arrow_geometry(png):
    """Native size and tip of David's Arrow01 (tail upper right, tip lower left)."""
    from PIL import Image
    im = Image.open(png)
    alpha = im.split()[3]
    w, h = im.size
    x0 = im.getbbox()[0]
    ys = [y for y in range(h) if alpha.getpixel((x0 + 1, y)) > 128] or [h // 2]
    return w, h, (x0 + 1, sum(ys) / len(ys))  # (width, height, tip)


def next_round(run_dir):
    """premiere/ for the first export, then premiere_r2/, premiere_r3/, ...: every export round gets a folder of its
    own, so a round David imported keeps the media and plan snapshot his project points at, even when he saved the
    project elsewhere (csc13 test: round 3 overwrote round 2, which he had imported into round 1's project). Only a
    folder an export left unfinished (no XML yet) is reused."""
    for k in range(1, 100):
        out = run_dir / ("premiere" if k == 1 else f"premiere_r{k}")
        if not out.exists() or not (any(out.glob("*.prproj")) or any(out.glob("*.xml"))):
            return out
    raise SystemExit("too many export rounds")


def export(run_dir, test_overview=False, do_render=True, out=None):
    run_dir = Path(run_dir).resolve()
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    fps, W, H, N = plan["fps"], plan["width"], plan["height"], plan["durationInFrames"]
    f = lambda t: round(t * fps)
    out = Path(out).resolve() if out else next_round(run_dir)
    (out / "overlays").mkdir(parents=True, exist_ok=True)
    (out / "overview").mkdir(exist_ok=True)
    tmp = out / "_tmp"
    tmp.mkdir(exist_ok=True)
    report = {"run": plan["run_id"], "fps": fps, "frames": N, "nest": {}, "top": {}, "not_carried": []}
    files, ids = Files(fps), Ids()
    still_in = int(STILL_IN_HOURS * 3600 * fps)
    still_dur = 12 * still_in

    # -- transparent layers, rendered from one bundle
    layers = plan.get("marks", {}).get("layers", [])
    marks = [(i, m) for i, m in enumerate(layers) if m["style"] in ("draw", "dim")]   # dim: the highlighter (R142)
    cursor_mov = out / "overlays" / "cursor.mov"
    mark_movs = {i: out / "overlays" / f"mark_{i:02d}_{m['step']}_{m['kind']}.mov" for i, m in marks}
    cards = [(k, seg) for k, seg in enumerate(plan["segments"]) if seg.get("card")]     # R39, over long live waits
    card_movs = {k: out / "overlays" / f"card_{k:03d}.mov" for k, _ in cards}
    overlays = list(enumerate(plan.get("overlays") or []))                             # R77, text shown whole
    overlay_movs = {i: out / "overlays" / f"overlay_{i:02d}_{o['id']}.mov" for i, o in overlays}
    if do_render:
        bdir = tmp / "bundle"
        bundle(bdir)
        render_overlay(bdir, plan, "cursor", 0, N - 1, cursor_mov, tmp)
        for i, m in marks:
            render_overlay(bdir, plan, f"mark:{i}", f(m["draw0"]), min(N - 1, f(m["fade1"])), mark_movs[i], tmp)
        for k, seg in cards:
            render_overlay(bdir, plan, f"card:{k}", f(seg["t"]), f(seg["t"] + seg["dur"]) - 1, card_movs[k], tmp)
        for i, o in overlays:
            render_overlay(bdir, plan, f"overlay:{i}", f(o["t0"]), min(N - 1, f(o["t1"]) - 1), overlay_movs[i], tmp)

    # -- the nest: recording, cursor, Epic Pen marks (source space, edited time)
    nest = Seq(f"{plan['run_id']} source", "sequence-2", fps, W, H, N)
    v1 = nest.track("video", "Recording")
    raw = run_dir / plan["video"]
    raw_frames = probe_frames(raw, fps)
    segs = plan["segments"]
    shown = []                                            # what each piece of V1 shows, for the privacy blurs (R116):
    for k, seg in enumerate(segs):                        # (start, end, media, its frame at start, its frames or None)
        s0 = f(seg["t"])
        s1 = f(segs[k + 1]["t"]) if k + 1 < len(segs) else N
        if s1 <= s0:
            continue
        if seg["type"] == "hold":
            still = run_dir / seg["still"]
            c = clipitem(v1, ids, f"freeze {seg['t']:.1f}s", s0, s1, still_in, still_in + s1 - s0, still_dur, fps)
            files.el(c, still, frames=still_dur, w=W, h=H)
            shown.append((s0, s1, still, 0, None))
        elif abs(seg["speed"] - 1.0) > 1e-3:              # sped up (typing, R67): its own file, placed at 1x
            sped = speed_clip(raw, seg, s1 - s0, fps, out / "speed")
            n = probe_frames(sped, fps, whole=True)
            c = clipitem(v1, ids, f"{seg['speed']}x {seg['t']:.1f}s", s0, s1, 0, min(n, s1 - s0), n, fps)
            files.el(c, sped, frames=n, w=W, h=H)
            shown.append((s0, s1, sped, 0, n))
        else:
            i0 = f(seg["src_in"])
            c = clipitem(v1, ids, raw.name, s0, s1, i0, i0 + s1 - s0, raw_frames, fps)
            files.el(c, raw, frames=raw_frames, w=W, h=H)
            shown.append((s0, s1, raw, i0, raw_frames))
    trs = {f(tr["t"]): tr for tr in plan.get("transitions") or [] if 0 < f(tr["t"]) < N}
    placed_trs, skipped_trs = work_transitions(v1, trs, fps)
    tr_frames = {a: (int(ti.find("end").text) - int(ti.find("start").text), trs[a].get("align", "start"))
                 for ti, _, _, a in placed_trs}           # in the XML or for Premiere to place (R105): either way
    report["nest"]["V1"] = (f"{len(v1) - len(placed_trs)} recording pieces and freezes"
                            + (f", {len(placed_trs)} transition(s) on its cuts (R83: "
                               + ", ".join(f"{trs[a]['type']} at {trs[a]['t']:.2f}s"
                                           + (" (crosses a mark)" if trs[a].get("crosses_mark") else "")
                                           for *_, a in placed_trs) + ")" if placed_trs else ""))
    if placed_trs and (plan["settings"]["cuts"].get("work_cut_transition") or {}).get("in_premiere"):
        # R105: Premiere places them (pipeline.edit.ppro.project): its XML import maps ours to the Page Peel it
        # retired in 26.0, which arrives as a dissolve. The XML keeps hard cuts; transitions.json lists the cuts.
        jobs = []
        for ti, cout, cin, a in placed_trs:
            jobs.append({"sequence": nest.name, "track": 0, "cut_frame": a, "type": trs[a]["type"],
                         "frames": int(ti.find("end").text) - int(ti.find("start").text),
                         "align": trs[a].get("align", "start")})
            v1.remove(ti)
            cout.find("end").text, cin.find("start").text = str(a), str(a)
        (out / "transitions.json").write_text(json.dumps({"fps": fps, "transitions": jobs}, indent=1),
                                              encoding="utf-8")
        report["nest"]["V1"] += " (in transitions.json, for Premiere to place: R105)"
        placed_trs = []
    for a, why in skipped_trs:
        report["not_carried"].append(f"transition at {a / fps:.2f}s: {why}; left as a hard cut")

    corrections(nest, ids, files, plan, run_dir, out, fps, W, H, N, still_in, still_dur, report)   # R173
    blurs = privacy_blurs(nest, ids, files, plan, shown, tr_frames, out, fps, W, H, N, still_in, still_dur, report)

    dims = [(i, m) for i, m in marks if m["style"] == "dim"]   # R142: the highlighter sits below the cursor, so the
    dim_lanes = []                                        # pointer stays bright over the dim, as in the proxy
    for i, m in sorted(dims, key=lambda im: im[1]["draw0"]):
        a, b = f(m["draw0"]), min(N, f(m["fade1"]) + 1)
        lane = next((ln for ln in dim_lanes if ln["end"] <= a), None)
        if lane is None:
            lane = {"end": 0, "track": nest.track("video", f"Highlighter {len(dim_lanes) + 1}")}
            dim_lanes.append(lane)
        c = clipitem(lane["track"], ids, f"highlight {m['step']}", a, b, 0, b - a, b - a, fps, alpha="straight")
        files.el(c, mark_movs[i], frames=b - a, w=W, h=H)
        lane["end"] = b

    v2 = nest.track("video", "Cursor")
    starts = {0: "cursor (rest)"}
    for m in plan["cursor"]["moves"]:                     # one clip per move; moves starting on one frame share it
        if 0 < f(m["t0"]) < N:
            starts.setdefault(f(m["t0"]), f"cursor {m['step']}")
    bounds = sorted(starts) + [N]
    names = [starts[b] for b in bounds[:-1]]
    for (a, b), name in zip(zip(bounds, bounds[1:]), names):
        c = clipitem(v2, ids, name, a, b, a, b, N, fps, alpha="straight")
        files.el(c, cursor_mov, frames=N, w=W, h=H)
    report["nest"]["V2"] = f"cursor in {len(bounds) - 1} clips (one per move), click rings included"

    lanes = []                                            # Epic Pen marks, packed onto as few tracks as fit
    for i, m in sorted(marks, key=lambda im: im[1]["draw0"]):
        if m["style"] == "dim":                           # on its own tracks, below the cursor (above)
            continue
        a, b = f(m["draw0"]), min(N, f(m["fade1"]) + 1)
        lane = next((ln for ln in lanes if ln["end"] <= a), None)
        if lane is None:
            lane = {"end": 0, "track": nest.track("video", f"Marks {len(lanes) + 1}")}
            lanes.append(lane)
        c = clipitem(lane["track"], ids, f"{m['kind']} {m['step']}", a, b, 0, b - a, b - a, fps, alpha="straight")
        files.el(c, mark_movs[i], frames=b - a, w=W, h=H)
        lane["end"] = b
    report["nest"]["V3+"] = (f"{len(marks) - len(dims)} Epic Pen marks on {len(lanes)} track(s)"
                             + (f"; {len(dims)} highlighter(s) (R142) on {len(dim_lanes)} track(s) below the cursor"
                                if dims else ""))
    close_tracks(nest)

    # -- the top sequence: the nest under the camera, overview marks, narration
    top = Seq(f"{plan['run_id']} camera", "sequence-1", fps, W, H, N)
    t1 = top.track("video", "Camera (nest)")
    scale_k, center_k = camera_keys(plan.get("camera") or [{"t": 0, "s": 1, "x": W / 2, "y": H / 2}], fps, W, H)
    nest_track(t1, ids, nest, plan["run_id"], N, fps, scale_k, center_k)
    report["top"]["V1"] = f"nest with {len(scale_k)} camera keyframes (Scale, Center)"

    ov = overview_tracks(top, ids, files, plan, out, fps, W, H, still_in, still_dur)
    if ov:
        report["top"]["overview"] = ov
    if test_overview:
        report["top"]["overview_test"] = test_overview_pair(top, ids, files, plan, out, fps, W, H, N, still_in,
                                                            still_dur)

    if overlays:                                          # overlay cards (R77): screen space, over the camera
        ot = top.track("video", "Overlays")
        for i, o in overlays:
            a, b = f(o["t0"]), min(N, f(o["t1"]))
            c = clipitem(ot, ids, f"overlay {o['id']}", a, b, 0, b - a, b - a, fps, alpha="straight")
            files.el(c, overlay_movs[i], frames=b - a, w=W, h=H)
        report["top"]["overlays"] = f"{len(overlays)} overlay card(s) (R77) on their own track"

    if cards:                                             # title cards: screen space, over the camera
        tc = top.track("video", "Title cards")
        for k, seg in cards:
            a, b = f(seg["t"]), f(seg["t"] + seg["dur"])
            c = clipitem(tc, ids, f"{seg['card']['title']} card", a, b, 0, b - a, b - a, fps, alpha="straight")
            files.el(c, card_movs[k], frames=b - a, w=W, h=H)
        report["top"]["title cards"] = f"{len(cards)} title card(s) (R39) on their own track"

    a1 = top.track("audio", "Narration")
    pieces = 0
    for n in plan["narration"]:                           # one clip per part: a beat (R62) splits a line in two
        src = run_dir / n["src"]
        nf = probe_frames(src, fps, whole=True)
        for p in n.get("parts") or [{"at": n["start"], "in": 0.0, "out": nf / fps}]:
            i0, i1 = f(p["in"]), min(nf, f(p["out"]))
            s0 = f(p["at"])
            c = clipitem(a1, ids, n["line_id"], s0, s0 + i1 - i0, i0, i1, nf, fps, premiereChannelType="mono")
            c.remove(c.find("alphatype"))
            files.el(c, src, frames=nf, audio={"rate": 48000 if src.suffix == ".wav" else 24000, "channels": 1})
            st = sub(c, "sourcetrack")
            sub(st, "mediatype", "audio")
            sub(st, "trackindex", 1)
            pieces += 1
    report["top"]["A1"] = f"{len(plan['narration'])} narration lines in {pieces} clips"
    cs = plan.get("click_sound")
    if cs:                                                # R137: a quiet click at each click ring, on its own track,
        a2 = top.track("audio", "Clicks")                 # where David sets the level
        src = run_dir / cs["src"]
        nf = probe_frames(src, fps, whole=True)
        last, n_clicks = -1, 0
        for c in sorted(cs.get("at") or plan["cursor"]["clicks"], key=lambda c: c["t"]):   # the plan's sounded clicks
            s0 = f(c["t"])
            if s0 < max(0, last) or s0 >= N:              # one at a time; a click on another's tail is left out
                continue
            s1 = min(N, s0 + nf)
            ci = clipitem(a2, ids, f"click {c['step']}", s0, s1, 0, s1 - s0, nf, fps, premiereChannelType="mono")
            ci.remove(ci.find("alphatype"))
            files.el(ci, src, frames=nf, audio={"rate": 48000, "channels": 1})
            st = sub(ci, "sourcetrack")
            sub(st, "mediatype", "audio")
            sub(st, "trackindex", 1)
            last, n_clicks = s1, n_clicks + 1
        report["top"]["A2"] = (f"Clicks: {n_clicks} click sounds (R137, peak {cs['peak_dbfs']} dBFS; set the track's "
                               "level in Premiere)")
    close_tracks(top)

    cues = plan["captions"]["cues"]
    write_ttml(out / "captions.xml", cues, plan["captions"].get("style", {}), fps, W, H)
    write_srt(out / "captions.srt", cues, fps)
    report["captions"] = (f"captions.xml (TTML, {len(cues)} cues, each in its grid position) and captions.srt (no "
                          "position). Import captions.xml, drag it to 0:00 on the camera sequence, then delete the "
                          "one-frame anchor cue at 0:00.")
    report["not_carried"] += ["captions: FCP 7 XML has no caption tracks; import captions.xml (see 'captions')",
                              "cursor and Epic Pen marks: shape and style are baked into their clips"]

    root = ET.Element("xmeml", version="4")
    root.append(top.el)
    ET.indent(root, "\t")
    xml_path = out / f"{plan['run_id']}.xml"
    write_xml = lambda p: p.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'
                                       + ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    write_xml(xml_path)
    full = assembly(run_dir, out, plan, top.el, fps, W, H, N, blurs)   # before the fallback strips the transitions
    if full:
        report["full"] = full
        ld = plan.get("loudness")                         # R177 raises the plan's narration and effects; the opening,
        if ld and any(w in full for w in ("opening (", "recap (", "logo outro (")):   # recap and logo outro carry
            report["not_carried"].append(                 # their own audio at the old level (Fable, round 7)
                f"R177: the opening, recap and logo outro audio isn't raised with the voice (+{ld['effects_gain_db']} dB "
                "in the camera's narration and effects): raise it on their clips in Premiere, or build the graphics "
                "from the processed lines")
    if placed_trs:                   # the transition items are untested in Premiere's import: a fallback without them
        for ti, cout, cin, a in placed_trs:
            v1.remove(ti)
            cout.find("end").text, cin.find("start").text = str(a), str(a)
        ET.indent(root, "\t")
        write_xml(out / f"{plan['run_id']}_hard_cuts.xml")
        report["nest"]["fallback"] = (f"{plan['run_id']}_hard_cuts.xml: the same edit with hard cuts, if the "
                                      "transitions stop the import (they are listed under the nest's V1)")
    (out / "export_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    shutil.copy2(run_dir / "edit_plan.json", out / "edit_plan.json")   # what pipeline.edit.readback compares with
    lc = run_dir / "linecheck" / "report.md"                            # R85: the line check made for this plan
    if lc.exists() and lc.stat().st_mtime >= (run_dir / "edit_plan.json").stat().st_mtime:
        shutil.copy2(lc, out / "linecheck_report.md")
    else:
        report["not_carried"].append("linecheck_report.md: no line check newer than this plan (R85: run "
                                     "pipeline.edit.linecheck before the export)")
    shutil.rmtree(tmp, ignore_errors=True)
    return xml_path, report


# ---------------------------------------------------------------------------------------------------- captions
# Premiere imports a caption file as a clip whose in point is its first cue, so wherever it is dropped becomes the
# first cue's time (take 05's captions ran 1.05 s early from a drop at 0:00). Both files therefore open with a
# one-frame anchor cue at 0:00: dropped at 0:00, every cue lands on its words (R54); David deletes the anchor.
ANCHOR = "\u00a0"   # a no-break space
# Premiere treats every TTML region as full-screen and keeps only its alignment, which is its own 3x3 caption grid:
# displayAlign gives the row, textAlign the column (R53).
GRID_ALIGN = {"top": "before", "middle": "center", "bottom": "after"}
GRID_TEXT = {"left": "left", "centre": "center", "right": "right"}


def _cue_list(cues, fps):
    """The anchor, then the cues; one that starts under the anchor (an intro's first words at 0:00) starts after it."""
    first = [{"start": 0.0, "end": 1 / fps, "text": ANCHOR, "pos": {"where": "bottom-centre"}}]
    return first + [c if c["start"] >= 1 / fps else {**c, "start": 1 / fps} for c in cues if c["end"] > 2 / fps]


def write_srt(path, cues, fps):
    ts = lambda t: f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{int(t % 60):02},{int(round(t % 1 * 1000)) % 1000:03}"
    path.write_text("\n".join(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n"
                              for i, c in enumerate(_cue_list(cues, fps), 1)), encoding="utf-8")


def write_ttml(path, cues, style, fps, W, H):
    """TTML (DFXP) with nine full-screen regions, one per grid position, and the planner's look."""
    tt = ET.Element("tt", {"xmlns": "http://www.w3.org/ns/ttml", "xmlns:tts": "http://www.w3.org/ns/ttml#styling",
                           "xmlns:ttp": "http://www.w3.org/ns/ttml#parameter", "ttp:timeBase": "media",
                           "ttp:frameRate": str(int(round(fps))), "tts:extent": f"{W}px {H}px", "xml:lang": "en"})
    head = sub(tt, "head")
    box = style.get("box_color", "#5F5F5F").lstrip("#")
    sub(sub(head, "styling"), "style", **{"xml:id": "caption", "tts:fontFamily": style.get("font", "Lucida Console"),
                                          "tts:fontSize": f"{style.get('size_px', 48)}px", "tts:color": "#FFFFFFFF",
                                          "tts:backgroundColor": f"#{box}{round(style.get('box_opacity', 1) * 255):02X}"})
    layout = sub(head, "layout")
    for row, da in GRID_ALIGN.items():
        for col, ta in GRID_TEXT.items():
            sub(layout, "region", **{"xml:id": f"{row}-{col}", "tts:origin": "0% 0%", "tts:extent": "100% 100%",
                                     "tts:displayAlign": da, "tts:textAlign": ta})
    div = sub(sub(tt, "body", style="caption"), "div")
    clock = lambda t: f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{t % 60:06.3f}"
    for c in _cue_list(cues, fps):
        p = sub(div, "p", begin=clock(c["start"]), end=clock(c["end"]),
                region=(c.get("pos") or {}).get("where", "bottom-centre"))
        lines = c["text"].split("\n")
        p.text = lines[0]
        for line in lines[1:]:
            sub(p, "br").tail = line
    ET.indent(tt, "  ")
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(tt, encoding="unicode") + "\n",
                    encoding="utf-8")


# ---------------------------------------------------------------------------------------------- overview marks
def arrow_asset(out, W, H):
    """David's Arrow01 centred on a frame-sized transparent canvas (so Center and Scale mean the same whether Premiere
    normalises by media or sequence size). Returns (png, tip offset from the canvas centre)."""
    import fitz
    from PIL import Image
    png = out / "overview" / "Arrow01.png"
    art = out / "overview" / "Arrow01_art.png"
    fitz.open(ARROW_AI)[0].get_pixmap(alpha=True, dpi=72).save(str(art))
    aw, ah, tip = arrow_geometry(art)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ox, oy = (W - aw) // 2, (H - ah) // 2
    canvas.alpha_composite(Image.open(art).convert("RGBA"), (ox, oy))
    canvas.save(png)
    art.unlink()
    return png, (ox + tip[0] - W / 2, oy + tip[1] - H / 2)


def arrow_centre(off, k, rot, target, W, H):
    """Center that puts the arrow's tip on target (screen px) at scale k and rotation rot (degrees clockwise)."""
    r = math.radians(rot)
    dx, dy = off[0] * k, off[1] * k
    tx, ty = dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
    return ((target[0] - tx - W / 2) / W, (target[1] - ty - H / 2) / H)


def overview_tracks(top, ids, files, plan, out, fps, W, H, still_in, still_dur):
    """The planned overview marks (style fade) as native layers above the nest: rectangles as frame-sized images with
    opacity fades, arrows as David's Arrow01 with Scale (grow in), Rotation and Center keys at every stop (R48, R61,
    R63). Positions follow the camera at each key; between keys Premiere moves them in straight lines."""
    from PIL import Image, ImageDraw
    from pipeline.edit.camera import cam_at

    layers = [m for m in plan.get("marks", {}).get("layers", []) if m["style"] == "fade"]
    if not layers:
        return None
    f = lambda t: round(t * fps)
    color = plan["marks"]["style"].get("color", "#F16F05")
    stroke = plan["marks"]["style"].get("overview_stroke_px", 8)

    def scr(t, p):
        s, cx, cy = cam_at(plan["camera"], t, W, H)
        return ((p["x"] - cx) * s + W / 2, (p["y"] - cy) * s + H / 2)

    rects, arrows, k = None, None, 0.6
    png = off = None
    for i, m in enumerate(layers):
        a, b = f(m["draw0"]), f(m["fade1"])
        w = lambda t: still_in + f(t) - a
        fades = [(w(m["draw0"]), 0.0), (w(m["draw1"]), 100.0), (w(m["fade0"]), 100.0), (w(m["fade1"]), 0.0)]
        if m["kind"] == "rect":
            rects = rects if rects is not None else top.track("video", "Overview rectangles")
            mid = (m["draw1"] + m["fade0"]) / 2
            (x0, y0), (x1, y1) = scr(mid, m["from"]), scr(mid, m["to"])
            img = out / "overview" / f"rect_{i:02d}_{m['step']}.png"
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(im).rectangle([round(min(x0, x1)), round(min(y0, y1)), round(max(x0, x1)), round(max(y0, y1))],
                                         outline=color, width=stroke)
            im.save(img)
            c = clipitem(rects, ids, f"rect {m['step']}", a, b, still_in, still_in + b - a, still_dur, fps, alpha="straight")
            files.el(c, img, frames=still_dur, w=W, h=H)
            motion(c)
            opacity(c, fades)
            continue
        arrows = arrows if arrows is not None else top.track("video", "Overview arrows")
        if png is None:
            png, off = arrow_asset(out, W, H)
        native = math.degrees(math.atan2(off[1], off[0]))           # Arrow01 points from its centre to its tip
        keys = m.get("path") or [{"t": m["draw0"], "from": m["from"], "to": m["to"]}]
        rot, ctr = [], []
        for key in keys:
            tail, tip = scr(key["t"], key["from"]), scr(key["t"], key["to"])
            r = math.degrees(math.atan2(tip[1] - tail[1], tip[0] - tail[0])) - native
            prev = rot[-1][1] if rot else 0.0
            r = prev + (r - prev + 180) % 360 - 180           # the short way round: Premiere tweens the numbers
            rot.append((w(key["t"]), round(r, 3)))
            ctr.append((w(key["t"]), arrow_centre(off, k, r, tip, W, H)))
        c = clipitem(arrows, ids, f"Arrow01 {m['step']}", a, b, still_in, still_in + b - a, still_dur, fps,
                     alpha="straight")
        files.el(c, png, frames=still_dur, w=W, h=H)
        motion(c, scale=[(w(m["draw0"]), 0.0), (w(m["draw1"]), k * 100)], rotation=rot, center=ctr)
        opacity(c, [(w(m["fade0"]), 100.0), (w(m["fade1"]), 0.0)])
    return (f"{sum(m['kind'] == 'rect' for m in layers)} rectangle(s), "
            f"{sum(m['kind'] == 'arrow' for m in layers)} arrow(s) (Arrow01 at {round(k * 100)}%)")


def test_overview_pair(top, ids, files, plan, out, fps, W, H, N, still_in, still_dur):
    """Test only (David, 2026-10-06): one overview rectangle and David's Arrow01, in screen space above the nest,
    during "The Explorer, on the left, ..." while the camera holds at 1.35x. Exercises Opacity, Scale, Center and
    Rotation keyframes on stills, and Arrow01.ai through XML. Not part of the steps."""
    import fitz
    from PIL import Image, ImageDraw
    from pipeline.edit.camera import cam_at

    f = lambda t: round(t * fps)
    color = plan["marks"]["style"].get("color", "#F16F05")
    stroke = plan["marks"]["style"].get("overview_stroke_px", 8)
    s, cx, cy = cam_at(plan["camera"], 40.0, W, H)
    scr = lambda x, y: ((x - cx) * s + W / 2, (y - cy) * s + H / 2)

    # Both images are frame-sized (1920x1080, transparent): Center and Scale then mean the same whether Premiere
    # normalises by media or by sequence size, and its Default Media Scaling preference cannot resize them.
    # rectangle on the Explorer's file list (source px 55..348 x 150..684), drawn in place
    (x0, y0), (x1, y1) = scr(55, 150), scr(348, 684)
    rect_png = out / "overview" / "rect_explorer.png"
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([round(x0), round(y0), round(x1), round(y1)], outline=color, width=stroke)
    im.save(rect_png)
    v2 = top.track("video", "Overview rectangles")
    a, b = f(38.0), f(42.7)
    c = clipitem(v2, ids, "rect Explorer (test)", a, b, still_in, still_in + b - a, still_dur, fps, alpha="straight")
    files.el(c, rect_png, frames=still_dur, w=W, h=H)
    motion(c)
    fade = f(0.25)
    opacity(c, [(still_in, 0.0), (still_in + fade, 100.0), (still_in + b - a - fade, 100.0), (still_in + b - a, 0.0)])
    pos = ((x0 + x1) / 2, (y0 + y1) / 2)

    # Arrow01, centred on a frame-sized canvas: scale in on "data", travel and turn to "README.md" (both visible
    # before data is opened), fade out
    art = out / "overview" / "Arrow01_art.png"
    pix = fitz.open(ARROW_AI)[0].get_pixmap(alpha=True, dpi=72)
    pix.save(str(art))
    aw, ah, tip = arrow_geometry(art)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ox, oy = (W - aw) // 2, (H - ah) // 2
    canvas.alpha_composite(Image.open(art).convert("RGBA"), (ox, oy))
    png = out / "overview" / "Arrow01.png"
    canvas.save(png)
    art.unlink()
    off = (ox + tip[0] - W / 2, oy + tip[1] - H / 2)          # tip relative to the canvas centre (the anchor)
    k = 0.6

    def centre_for(target, rot):
        r = math.radians(rot)
        dx, dy = off[0] * k, off[1] * k
        tx, ty = dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
        return ((target[0] - tx - W / 2) / W, (target[1] - ty - H / 2) / H)

    t_data, t_readme = scr(160, 322), scr(165, 517)         # just right of the labels
    a, b = f(38.2), f(42.7)
    v3 = top.track("video", "Overview arrows")
    c = clipitem(v3, ids, "Arrow01 (test)", a, b, still_in, still_in + b - a, still_dur, fps, alpha="straight")
    files.el(c, png, frames=still_dur, w=W, h=H)
    w = lambda t: still_in + f(t) - a
    c1, c2 = centre_for(t_data, 0.0), centre_for(t_readme, 12.0)
    motion(c, scale=[(w(38.2), 0.0), (w(38.9), k * 100), (w(42.7), k * 100)],
           rotation=[(w(38.2), 0.0), (w(40.6), 0.0), (w(41.4), 12.0), (w(42.7), 12.0)],
           center=[(w(38.2), c1), (w(40.6), c1), (w(41.4), c2), (w(42.7), c2)])
    opacity(c, [(w(38.2), 100.0), (w(42.4), 100.0), (w(42.7) - 1, 0.0)])
    return {"rect": f"{rect_png.name} (frame-sized) box {x1 - x0:.0f}x{y1 - y0:.0f} at ({pos[0]:.0f}, {pos[1]:.0f}), "
                    "fades 0.25 s, 38.0-42.7 s",
            "arrow": f"Arrow01.png (David's Arrow01.ai, {aw}x{ah}, centred on a frame-sized canvas) at 60%: scales in "
                     f"38.2-38.9 s on 'data', travels and turns 12 deg to "
                     f"'README.md' 40.6-41.4 s, fades 42.4-42.7 s"}


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    out = next((a.split("=", 1)[1] for a in argv if a.startswith("--out=")), None)
    xml, report = export(args[0], test_overview="--test-overview" in argv, do_render="--no-render" not in argv, out=out)
    print(xml)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
