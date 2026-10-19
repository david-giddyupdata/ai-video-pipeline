"""The picture-in-picture box (R220, R222, R224, R231, R232; VIDEO_RULES X6, C7): where the avatar's oval sits through
the main body, written as data, and a Premiere review of it on a still picture of the avatar (R229).

    python -m pipeline.edit.pip runs/<run_id> <approved review folder> [--out=pip_review_r1] [--still-s=13.1]
                                [--no-build | --build-only]

The box is David's Quick Series ep04 oval (research/style_study/STYLE_PROFILE.md section 6, R222): the whole frame at
35% seen through a 288 x 375 px ellipse with a 3.5 px feather and no ring. ep04 centred it at (0.9266, 0.8236) of the
frame, which cut its edge off (R231); its spots now keep the oval EDGE_PX in from the frame's edges, bottom right and
the mirrored spots in the other corners. Inside it, the cityscape behind the avatar (R232, replacing R224's teal).

The hand-overs (R231): the intro's avatar zooms down into the oval over the main body's opening chapter card and goes
straight on as this box, so the box is up from the main body's first frame (no fade, no wait), at the spot the
placement picks there, and that card doesn't move it; at the end the outro's oval takes over at "outro_spot" (the
intro's spot when it is clear over the last OUTRO_S), where a box already up stays to the last frame. Both spots are
in pip_spans.json's "handover", which pipeline.edit.stage reads for the intro's zoom-down and the outro's growth.

Where it goes (place): at every frame of the approved sequence a corner is clear when the oval, grown by CLEAR_PX,
touches none of what matters at that frame (obstacles):
  * the caption titles' boxes (C7), from the review's caption_titles.json, checked against David's saved project
    first (titles.readback: a moved or retimed title stops the run);
  * the overlay cards, by the pixels each review clip draws inside each corner's grown oval (its alpha, sampled);
  * the plan's marks and highlights while drawn, each click target from the pointer's move to it until just after the
    click, the dialogs the camera frames whole (plan.wholes), and the drawn pointer where it stays POINTER_STAY_S or
    longer (a pointer passing through doesn't move the box, as it doesn't move a caption, C3): recording-px boxes,
    mapped to the frame through the camera (camera.cam_at) at every frame;
  * what each line names, where the screen shows it during its sentence (checks.check_named's OCR);
  * the browser's address bar while the camera is at full frame (K2), and the sequence's last OUTRO_S, where the
    final dissolves into the outro (at every spot but the outro's, where the outro's own oval takes over).
The box then (R224, X6; numbers proposed for David):
  * shows only at a corner clear for at least MIN_STAY_S, so it never flickers between spots;
  * moves only by a FADE_S fade out and a FADE_S fade in at the new corner, never a slide: a span ends on the frame
    its corner stops being clear, so the fade out is over before whatever needs the space arrives;
  * hides (voice only) while no corner is clear for MIN_STAY_S, and stays hidden at least MIN_HIDDEN_S;
  * picks, among the clear corners, the one clear longest (counted up to LONG_S), then the one with the least going
    on under it (busyness: the recording's edges inside the oval), then HOME's order (bottom right first, as ep04).
The spans ({"spot": "br"|"bl"|"tr"|"tl"|"hidden", "start", "end"}, seconds on the approved sequence, with why each
hide or move happened) are in <out>/pip_spans.json: the same data drives the real Avatar IV clips later
(pipeline.edit.pip_render: the segments, their credits and their upload audio).

A presence budget (--presence, a proposal for David, 2026-10-16 night: stretch the plan credits without Avatar III):
the box shows only around the moments that matter, the exercise's list (each part's start, a new idea or step the
narration introduces, direct address to the viewer, a part's recap; by tier), and is voice only through the hands-on
stretches between them; every rule above still holds, since the budget only adds frames the box stays off.

The review (R229, R195, R104): a copy of the approved review project in a new folder, one sequence with the approved
sequence nested untouched on V1 and the still oval above it, one frame-sized PNG per corner as still clips with
Opacity keyframes for the fades, so David can move or retime any of them; a "PiP check" marker at every move and hide.
--build-only retries Premiere's part from the folder's pip_job.json.
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from pipeline.config import ROOT, tool
from pipeline.edit import camera as cam

SCALE, OVAL_W, OVAL_H, FEATHER_PX = 0.35, 288, 375, 3.5     # R222: ep04's oval
EP04_X, EP04_Y = 0.9266, 0.8236                             # ep04's centre, bottom right, in frame fractions: its edge
                                                            # ran 3 px past the frame's right and bottom (R231)
EDGE_PX = 54                                                # R231: the oval's edge this far in from the frame's edges
                                                            # at every spot (5% of 1080, title-safe's top and bottom)
HOME = ("br", "bl", "tr", "tl")                             # preference when corners tie
FADE_S = 0.3                                                # R222, R224: out 0.3 s, a jump, in 0.3 s
MIN_STAY_S = 4.0                                            # proposed: the box stays at a spot at least this long
MIN_HIDDEN_S = 2.0                                          # proposed: a voice-only stretch lasts at least this long
CLEAR_PX = 12                                               # room kept between the oval and what matters
LONG_S = 20.0                                               # a corner clear this long is as good as a longer one
OUTRO_S = 0.8                                               # the final's dissolve into the outro (ppro.final)
POINTER_SRC = (-4, -4, 26, 34)                              # the drawn pointer around its tip, recording px
POINTER_STAY_S = 0.6                                        # C3's house default (captions.cursor_stay_s)
RING_SRC = 26                                               # the click ring's radius, recording px (65 px at 1.35x)
CLICK_AFTER_S = 0.6                                         # a click target matters this long after the click
RING_S = 0.65                                               # a click's ring grows 0.35 s and fades 0.3 s (T8)
WALK_BACK_S = 3.0                                           # a stay ends at most this early to keep fades off marks
ADDRESS_SRC = (0, 0, 1920, 96)                              # the browser's tab strip and address bar, recording px
FULL_FRAME_MAX = 1.02                                       # camera scales this close to 1 are full frame (K2)
BUSY_STEP_S = 0.5                                           # the busyness tie-break's sampling
SAMPLE_FPS = 5                                              # overlay clips' drawn pixels, sampled this often
DRAWN_ALPHA = 64                                            # what an overlay draws: alpha this or more (a card's soft
                                                            # shadow, alpha 36 at most, blocked the map's corner, r5)
LINE_LEAD_S = 6.0                                           # a mark matters from its sentence's start, at most this
                                                            # before it is drawn
OVERLAY_TRACK = "Review: picked"                            # the review's overlay tracks start so
STILL_S = 13.1                                              # the intro frame for the still: eyes open, mouth closed
TEAL = ROOT / "research" / "backgrounds" / "gen" / "s4_brand_stage_code.png"    # R224's teal (round 5's box)
CITY = Path(r"D:\Videos\Global Assets\OfficeZoom_0002.jpg")  # R232: the Quick Series cityscape, 1920 x 1080, the
                                                            # picture the HeyGen looks were recorded on
MARK_NAMES = {"rect": "an orange rectangle", "arrow": "an orange arrow", "highlight": "the highlighter's lit area"}
SPOT_NAMES = {"br": "bottom right", "bl": "bottom left", "tr": "top right", "tl": "top left"}
SEQ_NAME = "PiP review: the oval on a still"
MARKER = "PiP check"
PRESENCE_LEAD_S = 0.5                                       # proposed: a moment's window opens this before its first
                                                            # sentence, so the 0.3 s fade in can be over 0.2 s before
                                                            # it (when a corner is clear and no mark is being drawn)
PRESENCE_LINGER_S = 4.0                                     # proposed: and stays this long after its last one ends
PRESENCE_MERGE_S = 8.0                                      # proposed: moments closer than this share one stay, so
                                                            # the box never blinks out and back for a few seconds
BUDGET_WHY = "a hands-on stretch: voice only (the presence budget)"


def corners(W, H):
    """Each spot's oval centre in frame px: bottom right with the oval EDGE_PX in from the right and bottom edges
    (R231), and its mirrors (whole px, rounded inwards, so every edge keeps at least EDGE_PX)."""
    cx, cy = math.floor(W - EDGE_PX - OVAL_W / 2), math.floor(H - EDGE_PX - OVAL_H / 2)
    return {"br": (cx, cy), "bl": (W - cx, cy), "tr": (cx, H - cy), "tl": (W - cx, H - cy)}


def edge_room(W, H):
    """The least room between any spot's oval and the frame's edges, px (R231: at least EDGE_PX)."""
    return min(min(cx - OVAL_W / 2, W - cx - OVAL_W / 2, cy - OVAL_H / 2, H - cy - OVAL_H / 2)
               for cx, cy in corners(W, H).values())


def touches(centre, box, grow=CLEAR_PX):
    """Whether a box (x0, y0, x1, y1) comes within grow px of the oval centred at centre: the box's nearest point to
    the centre lies inside the ellipse grown by grow on both axes."""
    a, b = OVAL_W / 2 + grow, OVAL_H / 2 + grow
    px, py = min(max(centre[0], box[0]), box[2]), min(max(centre[1], box[1]), box[3])
    return ((px - centre[0]) / a) ** 2 + ((py - centre[1]) / b) ** 2 < 1.0


def short(text, n=48):
    """A caption's text on one line, cut at a word to about n characters."""
    t = text.replace("\n", " ")
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "..."


def tc(f, fps):
    f = int(round(f))
    return f"{f // (3600 * int(fps)):02d}:{f // (60 * int(fps)) % 60:02d}:{f // int(fps) % 60:02d}:{f % int(fps):02d}"


def geom_tag(W, H):
    """The oval's geometry and the sampling, for any cache that depends on where the ovals are."""
    return f"{SCALE}|{OVAL_W}x{OVAL_H}|{json.dumps(corners(W, H))}|{CLEAR_PX}|{W}x{H}|{SAMPLE_FPS}"


def plan_sig(plan, *more):
    """What a cache made from the plan depends on: its camera, cuts, narration, marks and pointer (and more)."""
    keys = ("camera", "segments", "narration", "marks", "cursor", "click_targets", "wholes", "captions")
    return hashlib.sha256(json.dumps([plan.get(k) for k in keys] + list(more), sort_keys=True,
                                     default=str).encode()).hexdigest()[:16]


# ------------------------------------------------------------------------------------------------- obstacles
def overlay_clips(approved_dir, nest):
    """The review's overlay clips on the nested sequence: [(name, start, end, in, out, path)] in frames."""
    (xml,) = [p for p in approved_dir.glob("*_full.xml") if p.name != "captions_full.xml"]
    for s in ET.parse(xml).getroot().iter("sequence"):
        if s.findtext("name") != nest:
            continue
        files, out = {}, []
        for t in s.find("media/video").findall("track"):
            for c in t.findall("clipitem"):
                f = c.find("file")
                if f is not None and f.findtext("pathurl"):
                    files[f.get("id")] = f.findtext("pathurl")
            if not (t.get("MZ.TrackName") or "").startswith(OVERLAY_TRACK):
                continue
            for c in t.findall("clipitem"):
                url = files.get(c.find("file").get("id"))
                path = Path(unquote(re.sub(r"^file://localhost/", "", url)))
                out.append((c.findtext("name"), *(int(c.findtext(k)) for k in ("start", "end", "in", "out")), path))
        return out
    raise SystemExit(f"no sequence {nest!r} in {xml}")


def oval_masks(W, H, q, grow):
    """Each spot's oval grown by grow px, as a boolean mask at 1/q of the frame's size."""
    w, h = W // q, H // q
    yy, xx = np.mgrid[0:h, 0:w]
    yy, xx = (yy + 0.5) * q, (xx + 0.5) * q
    return {k: ((xx - cx) / (OVAL_W / 2 + grow)) ** 2 + ((yy - cy) / (OVAL_H / 2 + grow)) ** 2 < 1
            for k, (cx, cy) in corners(W, H).items()}


def drawn_hits(path, a, b, fps, W, H):
    """Which spots a transparent clip draws inside, sampled SAMPLE_FPS times a second from frame a to b of its file:
    [(frame offset, [hit per HOME spot])]: any pixel of alpha DRAWN_ALPHA or more inside the spot's oval grown by CLEAR_PX (at a
    quarter of the size, the oval grown one more quarter pixel so nothing slips between samples)."""
    q = 4
    w, h = W // q, H // q
    from pipeline.edit import alpha
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", *alpha._decoder(path), "-ss", f"{a / fps:.4f}", "-i",
                          str(path), "-t", f"{(b - a) / fps:.4f}", "-vf", f"fps={SAMPLE_FPS},scale={w}:{h}", "-pix_fmt", "rgba",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    n = len(raw) // (w * h * 4)
    if n == 0:
        raise SystemExit(f"no frames read from {path} ({a}-{b})")
    fr = np.frombuffer(raw[:n * w * h * 4], np.uint8).reshape(n, h, w, 4)[..., 3] >= DRAWN_ALPHA
    masks = oval_masks(W, H, q, CLEAR_PX + q)
    return [(round(i * fps / SAMPLE_FPS), [bool((fr[i] & masks[k]).any()) for k in HOME]) for i in range(n)]


def overlay_obstacles(approved_dir, nest, fps, W, H, cache, skip_starts=()):
    """The overlay cards: [(f0, f1, hits per spot, what)], each sample joined with the next (a moving piece is
    covered between samples). Cached in cache by clip (file, in, out, size, time). A clip starting at a frame in
    skip_starts isn't an obstacle (the opening chapter card, which the intro's oval sits over, R231)."""
    known = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    out = []
    for name, s, e, i, o, path in overlay_clips(approved_dir, nest):
        if s in skip_starts:
            continue
        st = path.stat()
        key = f"v4|{DRAWN_ALPHA}|{geom_tag(W, H)}|{path}|{i}|{o}|{st.st_size}|{st.st_mtime_ns}"
        if key not in known:
            known[key] = drawn_hits(path, i, o, fps, W, H)
        samples = known[key]
        label = re.sub(r"^[A-Z]+[0-9]+[a-z]? ", "", name)          # the review's piece id off its name
        for k, (off, hits) in enumerate(samples):
            nxt = samples[k + 1] if k + 1 < len(samples) else (e - s, [False] * len(HOME))
            both = [x or y for x, y in zip(hits, nxt[1])]
            if any(both):
                out.append((s + off, min(e, s + nxt[0] + 1), both, f"the overlay \"{label}\""))
    cache.write_text(json.dumps(known), encoding="utf-8")
    return out


def pointer_at(moves, t):
    """The drawn pointer's tip at edit time t (recording px): along a move (straight; the drawn one eases), else
    where the last move left it."""
    p = moves[0]["from"]
    for m in moves:
        if t < m["t0"]:
            break
        if t <= m["t1"]:
            u = (t - m["t0"]) / max(1e-6, m["t1"] - m["t0"])
            return m["from"]["x"] + (m["to"]["x"] - m["from"]["x"]) * u, m["from"]["y"] + (m["to"]["y"] - m["from"]["y"]) * u
        p = m["to"]
    return p["x"], p["y"]


def src_obstacles(plan, fps, cue_starts=()):
    """The plan's recording-px things: [(f0, f1, box, what)] (mapped through the camera per frame later). A click
    target matters from the start of the pointer's move to it (the step's last move with no gesture before the click,
    else its mark's approach, else 1 s before) until CLICK_AFTER_S after the click; a mark or a click target from the
    start of what is being said about it (said_from)."""
    f = lambda t: int(round(t * fps))
    lines = sorted((n["start"], n["step"]) for n in plan["narration"])
    cues = sorted(cue_starts)

    def said_from(step, t):
        """The start of what is said about a mark or click at t: the caption showing then, or the step's line if it
        started later (a line can hold an earlier sentence about something else: the visual review of round 5), at
        most LINE_LEAD_S before t, less the two fades, so the box is gone before the sentence about the thing begins
        (X6, G13), not only before its mark is drawn."""
        mine = [a for a, s_ in lines if s_ == step and a <= t + 1e-6]
        cue = [a for a in cues if a <= t + 1e-6]
        start = max(mine[-1] if mine else t - LINE_LEAD_S, cue[-1] if cue else t - LINE_LEAD_S)
        return max(min(start, t), t - LINE_LEAD_S) - 2 * FADE_S

    out = []
    for m in plan["marks"]["layers"]:
        a, c = m["from"], m["to"]
        pad = 22 if m["kind"] == "arrow" else 6
        box = [min(a["x"], c["x"]) - pad, min(a["y"], c["y"]) - pad, max(a["x"], c["x"]) + pad, max(a["y"], c["y"]) + pad]
        out.append((f(said_from(m["step"], m["draw0"])), f(m["fade1"]) + 1, box, MARK_NAMES.get(m["kind"], "a mark")))
    targets = {c["step"]: c["box"] for c in plan.get("click_targets") or []}
    moves = sorted(plan["cursor"]["moves"], key=lambda m: m["t0"])
    for c in plan["cursor"]["clicks"]:
        mine = [m for m in moves if m["step"] == c["step"] and m["t0"] <= c["t"]]
        to = [m["t0"] for m in mine if not m.get("gesture")] or [m["t0"] for m in mine if m.get("gesture") == "approach"]
        t0 = min(to[-1] if to else c["t"] - 1.0, c["t"] - 0.3, said_from(c["step"], c["t"]))
        if c["step"] in targets:
            out.append((f(t0), f(c["t"] + CLICK_AFTER_S) + 1, list(targets[c["step"]]), "what the pointer clicks"))
        x, y = c["at"]["x"], c["at"]["y"]
        out.append((f(c["t"]), f(c["t"] + RING_S) + 1, [x - RING_SRC, y - RING_SRC, x + RING_SRC, y + RING_SRC],
                    "a click's ring"))
    for w in plan.get("wholes") or []:
        if w.get("framed", True):
            out.append((f(w["t0"]), f(w["t1"]) + 1, list(w["box"]), f"the whole of {w['what']}"))
    return out


def named_obstacles(run_dir, plan, out):
    """What each line names, where it is on screen while its sentence plays (checks.check_named: OCR at the word,
    every place the term shows): [(f0, f1, box, what)]. Cached in out/named_boxes.json with the plan's signature."""
    cache, sig = out / "named_boxes.json", plan_sig(plan)
    got = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    if not isinstance(got, dict) or got.get("sig") != sig:
        from pipeline.edit import checks
        _, nb = checks.check_named(run_dir, plan, run_dir / "checks")
        got = {"sig": sig, "boxes": [[a, b, list(c), d, e] for a, b, c, d, e in nb]}
        cache.write_text(json.dumps(got), encoding="utf-8")
    fps = plan["fps"]
    return [(int(round(a * fps)), int(round(b * fps)) + 1, c, f"\"{d}\" (named in the narration)")
            for a, b, c, d, e in got["boxes"]]


def src_time(plan, t):
    """The recording's time at edit time t (as linecheck.src_at)."""
    seg = plan["segments"][0]
    for s in plan["segments"]:
        if s["t"] <= t:
            seg = s
    return seg["src_t"] if seg["type"] == "hold" else seg["src_in"] + (t - seg["t"]) * seg["speed"]


def busyness(run_dir, plan, N, out, step_s=BUSY_STEP_S):
    """How much is going on under each spot's oval (mean edge strength of the recording through the camera, without
    the edit's layers), every step_s of the sequence: [len(HOME), N] per frame, held between samples. A tie-break
    between corners clear equally long, never a reason to cover something. Cached in out/busy.npz with the plan's
    signature."""
    v = (run_dir / plan["video"]).stat()
    cache, sig = out / "busy.npz", plan_sig(plan, step_s, N, geom_tag(plan["width"], plan["height"]), v.st_size,
                                            v.st_mtime_ns)
    if cache.exists():
        z = np.load(cache)
        if str(z["sig"]) == sig:
            return z["b"]
    fps, W, H = plan["fps"], plan["width"], plan["height"]
    q, rate = 4, 2                                  # quarter size, two recording frames a second
    w, h = W // q, H // q
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(run_dir / plan["video"]), "-vf",
                          f"fps={rate},scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True,
                         check=True).stdout
    src = np.frombuffer(raw[:len(raw) // (w * h) * w * h], np.uint8).reshape(-1, h, w)
    from PIL import Image
    masks = oval_masks(W, H, q, 0)
    n = int(N / fps / step_s) + 1
    vals = np.zeros((len(HOME), n), np.float32)
    for i in range(n):
        t = i * step_s
        fr = src[min(len(src) - 1, int(round(src_time(plan, t) * rate)))]
        s, x, y = cam.cam_at(plan["camera"], t, W, H)
        box = tuple(round(v / q) for v in (x - W / 2 / s, y - H / 2 / s, x + W / 2 / s, y + H / 2 / s))
        view = np.asarray(Image.fromarray(fr).crop(box).resize((w, h), Image.BILINEAR), np.float32)
        g = np.zeros_like(view)
        g[:, 1:] += np.abs(np.diff(view, axis=1))
        g[1:, :] += np.abs(np.diff(view, axis=0))
        for j, k in enumerate(HOME):
            vals[j, i] = g[masks[k]].mean()
    b = vals[:, np.minimum(n - 1, (np.arange(N) / fps / step_s).astype(int))]
    np.savez(cache, b=b, sig=np.array(sig))
    return b


def opening_card(approved_dir):
    """The approved sequence's first chapter card (an overlay review's cards.json), or None."""
    cards = approved_dir / "cards.json"                # an overlay review's (overlays_review_rN)
    chapters = [c["layer"] for c in (json.loads(cards.read_text(encoding="utf-8")) if cards.exists() else [])
                if c["layer"].get("layout") == "chapter_card"]
    return min(chapters, key=lambda ly: ly["t0"]) if chapters else None


def keep_clear(path, approved_dir=None):
    """What a line is about that the measured obstacles can't see (a chart's plotted line, a pane's icons: text OCR can
    read, marks and targets the plan has; these it doesn't): the exercise's list, each {"t0", "t1": seconds on the
    approved sequence (the sentence about it), "box_src": [x0, y0, x1, y1] in recording px, "what"}, from round 6's
    visual review. The box keeps clear from two fades before t0, so it is gone when the sentence starts."""
    if not path:
        return []
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if approved_dir is not None and doc.get("approved") not in (None, Path(approved_dir).name):
        raise SystemExit(f"{path} lists times on {doc['approved']}, not {Path(approved_dir).name} (Fable, round 6)")
    return doc["items"]


def blocked_frames(run_dir, approved_dir, plan, out, nest, N, extra=()):
    """blocked[c, f]: corner c (HOME's order) isn't clear at frame f; why[c][f]: the first thing in the way. The
    outro's last OUTRO_S isn't in it yet (outro_block, once the outro's spot is known). extra: keep_clear's items."""
    fps, W, H = plan["fps"], plan["width"], plan["height"]
    C = corners(W, H)
    blocked = np.zeros((len(HOME), N), bool)
    why = [dict() for _ in HOME]
    cams = [cam.cam_at(plan["camera"], f / fps, W, H) for f in range(N)]

    def mark(f0, f1, box_at, what):
        for fr in range(max(0, f0), min(N, f1)):
            b = box_at(fr)
            for i, k in enumerate(HOME):
                if touches(C[k], b):
                    blocked[i, fr] = True
                    why[i].setdefault(fr, what)

    def mapped(b):
        def at(fr):
            s, x, y = cams[fr]
            return ((b[0] - x) * s + W / 2, (b[1] - y) * s + H / 2, (b[2] - x) * s + W / 2, (b[3] - y) * s + H / 2)
        return at

    counts = {}
    caps = json.loads((approved_dir / "caption_titles.json").read_text(encoding="utf-8"))["cues"]
    for c in caps:
        x, y, w, h = c["box"]
        mark(c["start_frame"], c["end_frame"], lambda fr, b=(x, y, x + w, y + h): b,
             f"the caption \"{short(c['text'])}\"")
    counts["captions"] = len(caps)
    card = opening_card(approved_dir)                  # R231: the intro's oval sits over it and goes on as the box
    skip = {int(round(card["t0"] * fps))} if card is not None and card["t0"] < 1.0 else set()
    ov = overlay_obstacles(approved_dir, nest, fps, W, H, out / "overlay_hits.json", skip)
    counts["opening chapter card exempt (frame)"] = sorted(skip)
    for f0, f1, hits, what in ov:
        for i, hit in enumerate(hits):
            if hit:
                for fr in range(max(0, f0), min(N, f1)):
                    blocked[i, fr] = True
                    why[i].setdefault(fr, what)
    counts["overlay stretches"] = len(ov)
    so = src_obstacles(plan, fps, [c["start_frame"] / fps for c in caps])
    for f0, f1, b, what in so:
        mark(f0, f1, mapped(b), what)
    counts["marks, targets, dialogs"] = len(so)
    nb = named_obstacles(run_dir, plan, out)
    for f0, f1, b, what in nb:
        mark(f0, f1, lambda fr, b=b: b, what)
    counts["named things"] = len(nb)
    for k in extra:                                    # what the line is about that no measure sees (keep_clear)
        mark(int(round((k["t0"] - 2 * FADE_S) * fps)), int(round(k["t1"] * fps)) + 1, mapped(k["box_src"]), k["what"])
    counts["kept clear by the exercise's list"] = len(extra)
    full = [fr for fr in range(N) if cams[fr][0] <= FULL_FRAME_MAX]    # K2: at full frame the address matters
    for fr in full:
        mark(fr, fr + 1, mapped(ADDRESS_SRC), "the browser's address bar (full frame)")
    counts["full-frame frames"] = len(full)
    # the pointer: where it stays POINTER_STAY_S or more in a spot's oval (C3: a pointer passing through for a moment
    # doesn't move a caption; nor the box); the move to a click is covered by the click target above
    moves = sorted(plan["cursor"]["moves"], key=lambda m: m["t0"])
    hidden = [(h[0], h[1]) if isinstance(h, (list, tuple)) else (h["t0"], h["t1"])
              for h in plan["cursor"].get("hidden") or []]
    stay = round(((plan["settings"].get("captions") or {}).get("cursor_stay_s") or POINTER_STAY_S) * fps)
    near = np.zeros((len(HOME), N), bool)
    for fr in range(N if moves else 0):
        t = fr / fps
        if not any(a <= t < b for a, b in hidden):
            x, y = pointer_at(moves, t)
            b = mapped((x + POINTER_SRC[0], y + POINTER_SRC[1], x + POINTER_SRC[2], y + POINTER_SRC[3]))(fr)
            for i, k in enumerate(HOME):
                near[i, fr] = touches(C[k], b)
    for i in range(len(HOME)):
        fr = 0
        while fr < N:
            if not near[i, fr]:
                fr += 1
                continue
            e = fr
            while e < N and near[i, e]:
                e += 1
            if e - fr >= stay:
                for g in range(fr, e):
                    blocked[i, g] = True
                    why[i].setdefault(g, "the pointer")
            fr = e
    # R231 replaces round 5's wait after the intro's dissolve: the intro's oval goes straight on as the box (place's
    # up_at_start), and the opening chapter card under it is exempt above
    return blocked, why, counts


def outro_block(blocked, why, fps, prefer=()):
    """The outro's oval takes over in the main body's last OUTRO_S (R231, R232: it appears there and grows back into
    the stage): its spot is the first of prefer (the box's corner just before, then the intro's) clear then, else the
    first of HOME that is; every other corner is blocked for those frames ("the dissolve into the outro"), so a box
    elsewhere leaves before them and a box already at the outro's spot stays to the last frame. Returns the spot (None
    when no corner is clear)."""
    N = blocked.shape[1]
    a = N - round(OUTRO_S * fps)
    clear = [k for i, k in enumerate(HOME) if not blocked[i, a:N].any()]
    spot = next((k for k in prefer if k in clear), clear[0] if clear else None)
    for i, k in enumerate(HOME):
        if k != spot:
            blocked[i, a:N] = True
            for fr in range(a, N):
                why[i].setdefault(fr, "the dissolve into the outro")
    return spot


# ------------------------------------------------------------------------------------------------- presence budget
def sentences(plan, lines, only=None):
    """Each narration line's sentences on the approved sequence: {line_id: [(text, t0, t1)]}, from its words as the
    plan's build timed them (timing.of: the aligner's where it ran, R227) mapped through the line's parts (a beat splits
    a line). A sentence ends at a word ending in . ? or ! (a word with no letters or digits, such as "&", has no
    timing). only: the line ids wanted (a line nobody asks for can't stop the run)."""
    from pipeline.narration import timing
    norm = lambda w: re.sub(r"[^a-z0-9']", "", w.lower())
    out = {}
    for n in plan["narration"]:
        if only is not None and n["line_id"] not in only:
            continue
        m = timing.of(n)
        words = m["words"]
        text = m.get("display_text") or (lines.get(n["line_id"]) or {}).get("text") or ""
        toks = [t for t in text.split() if norm(t)]
        if len(toks) != len(words):
            raise SystemExit(f"{n['line_id']}: {len(toks)} words in its text, {len(words)} timed")

        def at(w, n=n):
            for p in n["parts"]:
                if p["in"] - 1e-3 <= w <= p["out"] + 1e-3:
                    return p["at"] + w - p["in"]
            p = min(n["parts"], key=lambda p: min(abs(w - p["in"]), abs(w - p["out"])))
            return p["at"] + min(max(w, p["in"]), p["out"]) - p["in"]

        sents, cur = [], []
        for t, w in zip(toks, words):
            cur.append((t, w))
            if re.search(r"[.?!][\"')\]]*$", t):
                sents.append(cur)
                cur = []
        if cur:
            sents.append(cur)
        out[n["line_id"]] = [(" ".join(t for t, _ in s), round(at(s[0][1]["start"]), 3), round(at(s[-1][1]["end"]), 3))
                             for s in sents]
    return out


def presence(path, plan, lines, tiers, linger_s=PRESENCE_LINGER_S, approved_dir=None):
    """The moments that matter, from the exercise's list ({"moments": [{"line_id", "from": the first words of its first
    sentence, "to": of its last (default: the same one), "kind", "tier", "why"}]}, times on the approved sequence it
    names), as the windows the box may show in: [(f0, f1, what)], each from PRESENCE_LEAD_S before its first sentence
    to linger_s after its last, at least MIN_STAY_S and both fades long; windows closer than PRESENCE_MERGE_S joined.
    The first window starts at frame 0 (the intro's oval goes on as the box, R231): the list's first moment must start
    within LONG_S of it. Returns the windows and the moments resolved (their times, for the record)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if approved_dir is not None and doc.get("approved") not in (None, Path(approved_dir).name):
        raise SystemExit(f"{path} lists times on {doc['approved']}, not {Path(approved_dir).name}")
    fps, N = plan["fps"], plan["durationInFrames"]
    sents = sentences(plan, lines, {m["line_id"] for m in doc["moments"] if m["tier"] in tiers})
    flat = lambda t: re.sub(r"\W+", " ", t).lower().strip()        # quotes and brackets at either end don't count
    starts = lambda s, w: flat(s).startswith(flat(w))
    got = []
    for m in doc["moments"]:
        if m["tier"] not in tiers:
            continue
        ss = sents.get(m["line_id"])
        if ss is None:
            raise SystemExit(f"{path}: no line {m['line_id']} in the plan")
        i = next((k for k, s in enumerate(ss) if starts(s[0], m["from"])), None)
        j = next((k for k, s in enumerate(ss) if k >= (i or 0) and starts(s[0], m.get("to", m["from"]))), None)
        if i is None or j is None:
            raise SystemExit(f"{path}: {m['line_id']} has no sentence starting {m['from']!r}"
                             + (f" or {m['to']!r}" if m.get("to") else ""))
        t0, t1 = ss[i][1], ss[j][2]
        got.append({**m, "t0": t0, "t1": t1, "t0_tc": tc(t0 * fps, fps), "text": " ".join(s[0] for s in ss[i:j + 1])})
    if not got:
        raise SystemExit(f"{path}: no moments in tiers {sorted(tiers)}")
    got.sort(key=lambda m: m["t0"])
    least = round((MIN_STAY_S + 2 * FADE_S) * fps)
    wins = []
    for m in got:
        f0 = max(0, int(round((m["t0"] - PRESENCE_LEAD_S) * fps)))
        f1 = min(N, max(int(round((m["t1"] + linger_s) * fps)), f0 + least))
        what = f"{m['kind']}: \"{short(m['text'])}\""
        if wins and f0 - wins[-1][1] < round(PRESENCE_MERGE_S * fps):
            wins[-1] = (wins[-1][0], max(wins[-1][1], f1), wins[-1][2] + "; " + what)
        else:
            wins.append((f0, f1, what))
    if wins[0][0] > round(LONG_S * fps):
        raise SystemExit(f"{path}: the first moment starts at {tc(wins[0][0], fps)}, but the box is up from the main "
                         "body's first frame (R231): list the part's start")
    wins[0] = (0, max(wins[0][1], least), wins[0][2])
    return wins, got


def budget_mask(windows, N):
    """budget[c, f]: the presence budget keeps the box off frame f (outside every window), at every corner alike."""
    want = np.zeros(N, bool)
    for f0, f1, _ in windows:
        want[max(0, f0):min(N, f1)] = True
    return np.repeat(~want[None, :], len(HOME), axis=0)


# ------------------------------------------------------------------------------------------------- placement
def drawing_frames(plan, N):
    """Frames while a mark is being drawn or a click's ring appears (T8: nothing arrives then), where no fade of the
    box may fall."""
    fps = plan["fps"]
    d = np.zeros(N, bool)
    spans = [(m["draw0"], m["draw1"]) for m in plan["marks"]["layers"]]
    spans += [(c["t"], c["t"] + RING_S) for c in plan["cursor"]["clicks"]]
    for a, b in spans:
        d[max(0, int(a * fps)):min(N, int(np.ceil(b * fps)) + 1)] = True
    return d


def place(blocked, why, fps, busy=None, drawing=None, up_at_start=False):
    """The spans, as the module docstring says. blocked[c, f] in HOME's order; among corners clear at least
    MIN_STAY_S, the one clear longest (up to LONG_S), then the quietest over that stretch (busy[c, f]), then HOME's
    order. No fade falls on a frame of drawing (T8): a stay ends a little early, a return waits, if one would. Frames,
    end exclusive; a span that ends early keeps the frame its corner was needed at as "blocked_at". up_at_start: the
    box is already up at frame 0 (the intro's oval carried on, R231), at the corner picked there, with no fade in."""
    n_c, N = blocked.shape
    run = np.zeros((n_c, N + 1), int)                 # frames each corner stays clear from f on
    for f in range(N - 1, -1, -1):
        run[:, f] = np.where(blocked[:, f], 0, run[:, f + 1] + 1)
    stay, hide, long_ = round(MIN_STAY_S * fps), round(MIN_HIDDEN_S * fps), round(LONG_S * fps)
    fade = round(FADE_S * fps)
    csum = None if busy is None else np.concatenate([np.zeros((n_c, 1)), np.cumsum(busy, axis=1)], axis=1)
    drawing = np.zeros(N, bool) if drawing is None else drawing
    fade_in_ok = lambda x: not drawing[x:x + fade].any()
    fade_out_ok = lambda x: not drawing[max(0, x - fade):x].any()

    def cost(i, f):
        r = int(min(run[i, f], long_))
        quiet = 0.0 if csum is None else (csum[i, f + r] - csum[i, f]) / r
        return (-r, quiet, i)

    def pick(f, but=None):
        ok = [i for i in range(n_c) if i != but and run[i, f] >= stay]
        return min(ok, key=lambda i: cost(i, f)) if ok else None

    def blocker(i, f):
        return why[i].get(f, "nothing (clear for less than the minimum stay)")

    spans, f, h0 = [], 0, 0
    carried = up_at_start
    while True:                                         # hidden from h0: wait for a corner clear long enough
        if carried:                                     # the intro's oval goes on as the box: up at frame 0, no fade
            carried, g, c = False, 0, pick(0)
            if c is None:
                raise SystemExit("no corner is clear for MIN_STAY_S from the main body's first frame, where the "
                                 "intro's oval goes on as the box (R231)")
        else:
            g = next((x for x in range(max(f, h0 + hide if h0 else 0), N) if pick(x) is not None and fade_in_ok(x)),
                     None)
            if g is None:
                spans.append({"spot": "hidden", "f0": h0, "f1": N})
                return _explain(spans, blocker)
            if g > h0:
                spans.append({"spot": "hidden", "f0": h0, "f1": g})
            c = pick(g)
        while True:
            end = int(g + run[c, g])                  # the first frame the corner is needed
            e = end
            if end < N:                               # leave a little early rather than fade during a drawing; a
                ok = lambda x: fade_out_ok(x) and (fade_in_ok(x) or pick(x, but=c) is None)   # move needs both
                lo = max(g + stay, end - round(WALK_BACK_S * fps))      # fades clean, a hide only its fade out
                e = next((x for x in range(end, lo - 1, -1) if ok(x)), end)
            spans.append({"spot": HOME[c], "f0": int(g), "f1": min(e, N), **({"blocked_at": end} if e < end else {})})
            if e >= N:
                return _explain(spans, blocker)
            c2 = pick(e, but=c) if fade_in_ok(e) else None
            if c2 is None:
                h0 = f = e
                break
            g, c = e, c2


def _explain(spans, blocker):
    """Each span's reason: why the box left its spot (what needed the space at the next frame), and for a hidden
    span what filled each corner as it started."""
    for i, s in enumerate(spans):
        if s["spot"] != "hidden" and i + 1 < len(spans):
            s["leaves_for"] = blocker(HOME.index(s["spot"]), s.get("blocked_at", s["f1"]))
        if s["spot"] == "hidden":
            s["corners"] = {k: blocker(j, s["f0"]) for j, k in enumerate(HOME)}
            prev = spans[i - 1] if i else {}
            if prev.get("blocked_at"):                # it left a little early, so no fade fell on a mark
                k = prev["spot"]
                s["corners"][k] = blocker(HOME.index(k), prev["blocked_at"]) + " (left early: a mark was being drawn)"
    return spans


def placement(blocked, why, fps, busy=None, drawing=None, budget=None):
    """The spans with R231's hand-overs: the box is up from frame 0 at the corner picked there (the intro's oval lands
    on it); the outro's oval takes over in the last OUTRO_S at the corner the box is at just before (else the intro's)
    if clear then (outro_block). The outro's spot is chosen on what the screen shows, before any budget, so it always
    has one (its oval appears whether the box is up or not). budget[c, f]: frames a presence budget keeps the box off
    though nothing is in the way (budget_mask). blocked and why are changed in place (the outro's block, the budget).
    Returns (spans, intro_spot, outro_spot, warnings)."""
    N = blocked.shape[1]
    trial = place(blocked if budget is None else blocked | budget, why, fps, busy, drawing, up_at_start=True)
    intro_spot = trial[0]["spot"]
    pre = N - round(OUTRO_S * fps) - 1                   # a box already up there before the outro stays up (Fable,
    up = next((s["spot"] for s in trial if s["spot"] != "hidden" and s["f0"] <= pre < s["f1"]), None)   # round 6)
    outro_spot = outro_block(blocked, why, fps, prefer=[up, intro_spot])
    if outro_spot is None:
        raise SystemExit("no corner is clear in the main body's last OUTRO_S for the outro's oval (R231)")
    if budget is not None:
        for i in range(len(HOME)):
            for fr in np.flatnonzero(budget[i] & ~blocked[i]):
                why[i].setdefault(int(fr), BUDGET_WHY)
        blocked |= budget
    spans = place(blocked, why, fps, busy, drawing, up_at_start=True)
    final_up = next((s["spot"] for s in spans if s["spot"] != "hidden" and s["f0"] <= pre < s["f1"]), None)
    warnings = ([f"the box is at {final_up} just before the outro, the trial had {up}: the outro's spot ({outro_spot}) "
                 "came from the trial (Fable, round 6)"] if final_up != up and final_up is not None else [])
    if spans[0]["spot"] != intro_spot:
        raise SystemExit(f"the box starts at {spans[0]['spot']}, not {intro_spot} (the outro's block moved it)")
    return spans, intro_spot, outro_spot, warnings


def summarize(spans, fps, N):
    shown = sum(s["f1"] - s["f0"] for s in spans if s["spot"] != "hidden")
    hides = [s for s in spans if s["spot"] == "hidden" and s["f0"] > 0 and s["f1"] < N]
    moves = sum(1 for a, b in zip(spans, spans[1:]) if a["spot"] != "hidden" and b["spot"] != "hidden")
    return {"shown_s": round(shown / fps, 1), "shown_pct": round(100 * shown / N, 1), "moves": moves,
            "hides": len(hides), "hidden_s": round((N - shown) / fps, 1),
            "by_spot_s": {k: round(sum(s["f1"] - s["f0"] for s in spans if s["spot"] == k) / fps, 1) for k in HOME},
            "longest_hidden_s": round(max([s["f1"] - s["f0"] for s in hides] or [0]) / fps, 1)}


def check_spans(spans, blocked, fps, N):
    """The placement's own rules, measured on its spans: no shown frame (fades included) on a blocked corner, each
    stay at least MIN_STAY_S, each hide at least MIN_HIDDEN_S (but at the start and the end), spans tiling 0..N."""
    bad = []
    if spans[0]["f0"] != 0 or spans[-1]["f1"] != N or any(a["f1"] != b["f0"] for a, b in zip(spans, spans[1:])):
        bad.append("the spans don't tile the sequence")
    for s in spans:
        n = s["f1"] - s["f0"]
        if s["spot"] == "hidden":
            if 0 < s["f0"] and s["f1"] < N and n < round(MIN_HIDDEN_S * fps):
                bad.append(f"hidden {tc(s['f0'], fps)} for {n / fps:.2f} s, under {MIN_HIDDEN_S} s")
            continue
        if n < round(MIN_STAY_S * fps) and s["f1"] < N:
            bad.append(f"{s['spot']} at {tc(s['f0'], fps)} for {n / fps:.2f} s, under {MIN_STAY_S} s")
        if blocked[HOME.index(s["spot"]), s["f0"]:s["f1"]].any():
            bad.append(f"{s['spot']} at {tc(s['f0'], fps)} covers something")
    for a, b in zip(spans, spans[1:]):
        if a["spot"] == b["spot"]:
            bad.append(f"two spans at {a['spot']} in a row at {tc(b['f0'], fps)}")
    for a, h, b in zip(spans, spans[1:], spans[2:]):      # a blink: out and back in at a corner clear all along
        if (h["spot"] == "hidden" and a["spot"] == b["spot"] != "hidden"
                and not blocked[HOME.index(a["spot"]), h["f0"]:h["f1"]].any()):
            bad.append(f"the box blinks at the {SPOT_NAMES[a['spot']]} at {tc(h['f0'], fps)}: clear all along")
    return bad


def fades(s, N):
    """Which fades a span has: none in at frame 0 (the intro's oval carried on) and none out at the last frame (the
    outro's oval takes over), R231."""
    return {"in": s["f0"] > 0, "out": s["f1"] < N}


def fade_clashes(spans, drawing, fps):
    """T8: the fades that fall on a frame where a mark is drawn or a click's ring appears (none where avoidable)."""
    fade, out, N = round(FADE_S * fps), [], len(drawing)
    for s in spans:
        if s["spot"] == "hidden":
            continue
        has = fades(s, N)
        for a, b, what in ((s["f0"], s["f0"] + fade, "fade in"), (s["f1"] - fade, s["f1"], "fade out")):
            if not has[what.split()[1]]:
                continue
            if drawing[max(0, a):b].any():
                out.append(f"{what} at the {SPOT_NAMES[s['spot']]} at {tc(a, fps)} while a mark is drawn")
    return out


# ------------------------------------------------------------------------------------------------- the still
def oval_rgba(frame_rgb, person_x):
    """The frame (H x W x 3) at 35%, cut to the feathered ellipse centred on the person: an RGBA PIL image, OVAL_W x
    OVAL_H (pip_ep04's oval)."""
    from PIL import Image
    H, W = frame_rgb.shape[:2]
    small = Image.fromarray(frame_rgb).resize((round(W * SCALE), round(H * SCALE)), Image.LANCZOS)
    x0 = min(max(0, round(person_x * SCALE - OVAL_W / 2)), small.width - OVAL_W)
    y0 = round((small.height - OVAL_H) / 2)
    face = small.crop((x0, y0, x0 + OVAL_W, y0 + OVAL_H)).convert("RGBA")
    face.putalpha(Image.fromarray(oval_alpha()))
    return face


def oval_alpha(q=4):
    """The oval's alpha, OVAL_W x OVAL_H: opaque inside, falling linearly to 0 at the ellipse over a band of about
    FEATHER_PX, exactly as the stage's settled oval (AvatarStage's radial gradient: stop at 1 - feather / sqrt(rx ry) of
    the radius), supersampled q x q. A blur inside a canvas the ellipse's own size cut its edge off flat at the four
    sides (round 6's visual review)."""
    rx, ry = OVAL_W / 2, OVAL_H / 2
    stop = 1 - FEATHER_PX / math.sqrt(rx * ry)
    yy, xx = np.mgrid[0:OVAL_H * q, 0:OVAL_W * q]
    rho = np.hypot(((xx + 0.5) / q - rx) / rx, ((yy + 0.5) / q - ry) / ry)
    a = np.clip((1 - rho) / (1 - stop), 0, 1)
    return np.round(255 * a.reshape(OVAL_H, q, OVAL_W, q).mean(axis=(1, 3))).astype(np.uint8)


def avatar_still(run_dir, t, bg_path=CITY):
    """The intro render's frame at t (avatar/avatar.json's transparent opening, R219's look) over bg_path (cover-
    cropped to the frame): (H x W x 3 uint8, the person's centre x, from the alpha of the head's rows, the render's
    file)."""
    from PIL import Image
    from pipeline.edit import alpha
    g = json.loads((run_dir / "avatar" / "avatar.json").read_text(encoding="utf-8"))["graphics_alpha"]["opening"]
    f = alpha.rgba(run_dir / g["file"], t)
    H, W = f.shape[:2]
    bg = np.asarray(cover(Image.open(bg_path).convert("RGB"), W, H), np.float32)
    a = f[..., 3:4].astype(np.float32) / 255
    comp = (f[..., :3].astype(np.float32) * a + bg * (1 - a)).round().astype(np.uint8)
    ys, xs = np.nonzero(f[: H * 2 // 5, :, 3] > 128)             # the head: the top two fifths of the frame
    if not len(xs):
        raise SystemExit(f"no person in {g['file']} at {t} s")
    return comp, float(np.median(xs)), g["file"]


def cover(im, W, H):
    """A picture scaled to cover W x H and centre-cropped (B1 is 2560 x 1440)."""
    from PIL import Image
    k = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def corner_pngs(oval, out, W, H):
    """One frame-sized transparent PNG per spot with the oval in place (frame-sized, so Premiere's placement can't
    drift: GOTCHAS, Premiere round trip). Named by spot and a hash of the oval, so a rebuild never overwrites a file
    an open project holds."""
    from PIL import Image
    tag = hashlib.sha256(oval.tobytes() + json.dumps([corners(W, H), geom_tag(W, H)]).encode()).hexdigest()[:8]
    paths = {}
    for k, (cx, cy) in corners(W, H).items():
        p = out / f"pip_oval_{k}_{tag}.png"
        if not p.exists():
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            x0, y0 = cx - OVAL_W // 2, cy - OVAL_H // 2
            sx, sy = max(0, -x0), max(0, -y0)                       # the part of the oval inside the frame
            crop = oval.crop((sx, sy, min(OVAL_W, W - x0), min(OVAL_H, H - y0)))
            im.alpha_composite(crop, (x0 + sx, y0 + sy))
            im.save(p)
        paths[k] = p
    return paths


# ------------------------------------------------------------------------------------------------- the review
def review_xml(spans, pngs, out, run, N, fps, W, H):
    """One sequence: V1 left empty for the approved sequence (aidvStageReview nests it), the oval's clips on V2 with
    their fades as Opacity keyframes (in the still's own frames, from its 1-hour in point, as premiere.py's stills),
    an empty Caption titles track (the build wants three), A1 for the nest's sound."""
    from pipeline.edit import premiere as pr
    from pipeline.edit.ppro import titles
    root = ET.Element("xmeml", version="4")
    ids, files = pr.Ids(), pr.Files(fps)
    s = pr.Seq(SEQ_NAME, "sequence-pip", fps, W, H, N)
    s.track("video", "Approved sequence")
    box = s.track("video", "Avatar box (still)")
    s.track("video", titles.TRACK)
    s.track("audio", "Approved sequence")
    still_in = int(3600 * fps)
    still_dur = 12 * still_in
    fade = round(FADE_S * fps)
    for sp in spans:
        if sp["spot"] == "hidden":
            continue
        a, b = sp["f0"], sp["f1"]
        c = pr.clipitem(box, ids, f"avatar {sp['spot']}", a, b, still_in, still_in + b - a, still_dur, fps,
                        alpha="straight")
        files.el(c, pngs[sp["spot"]], frames=still_dur, w=W, h=H)
        pr.motion(c)
        n, has = b - a, fades(sp, N)
        keys = ([(still_in, 0.0), (still_in + fade, 100.0)] if has["in"] else [(still_in, 100.0)])
        keys += ([(still_in + n - fade, 100.0), (still_in + n, 0.0)] if has["out"] else [(still_in + n, 100.0)])
        pr.opacity(c, keys)
    pr.close_tracks(s)
    root.append(s.el)
    ET.indent(root, "\t")
    xml = out / f"{run}_pip_review.xml"
    xml.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode")
                   + "\n", encoding="utf-8")
    return xml


def markers(spans, fps, N):
    """A "PiP check" marker at every move, hide and return (R106), with what happens and why; and at the two
    hand-overs (R231)."""
    out = []
    s0, s1 = spans[0], spans[-1]
    if s0["spot"] != "hidden" and s0["f0"] == 0:
        out.append({"t": 0.0, "name": MARKER, "comment": f"The box is already up at the {SPOT_NAMES[s0['spot']]}: in "
                    "the final, the intro's oval zooms down here over the Part 1 card and goes straight on as this "
                    "box (no fade, no wait)."})
    for a, b in zip(spans, spans[1:]):
        t = b["f0"] / fps
        if a["spot"] == "hidden":
            what = f"The box fades in at the {SPOT_NAMES[b['spot']]} (voice only before this)."
        elif b["spot"] == "hidden":
            until = (f"until {tc(b['f1'], fps)}" if b["f1"] < N else "to the end of the main body")
            what = (f"The box fades out at the {SPOT_NAMES[a['spot']]}: a hands-on stretch, voice only {until} (the "
                    "presence budget)." if a.get("leaves_for") == BUDGET_WHY else
                    f"The box fades out at the {SPOT_NAMES[a['spot']]} to clear {a.get('leaves_for', '')}; "
                    f"voice only {until}, while no corner is clear for {MIN_STAY_S:g} s.")
            t = (a["f1"] - round(FADE_S * fps)) / fps                # at the fade out's start
        else:
            what = (f"The box fades out at the {SPOT_NAMES[a['spot']]} to clear {a.get('leaves_for', '')}, and "
                    f"fades in at the {SPOT_NAMES[b['spot']]}.")
            t = (a["f1"] - round(FADE_S * fps)) / fps
        out.append({"t": round(t, 4), "name": MARKER, "comment": what})
    if s1["spot"] != "hidden" and s1["f1"] == N:
        out.append({"t": round((N - round(OUTRO_S * fps)) / fps, 4), "name": MARKER, "comment": "The box stays to "
                    f"the last frame at the {SPOT_NAMES[s1['spot']]}: in the final, the outro's oval takes over here "
                    "and grows back into the cityscape."})
    return out


def captions_as_built(approved_dir):
    """R60: David's saved project against the caption titles job; the placement reads the job, so it must still be
    what he has (pipeline.edit.ppro.titles.readback). Returns the changes, empty when none."""
    from pipeline.edit import prproj
    from pipeline.edit.ppro import titles
    job = json.loads((approved_dir / "caption_titles.json").read_text(encoding="utf-8"))
    (p,) = list(approved_dir.glob("*_full.prproj"))
    return titles.readback(prproj.Project(p), job)


def build(job, approved):
    """Premiere's part (aidvStageReview): into a copy of the approved project, made only now and only where nothing is
    (R104: never into a built or saved project)."""
    import filecmp
    from pipeline.edit.ppro.bridge import call, start
    prproj = Path(job["prproj"])
    if prproj.exists() and not filecmp.cmp(approved, prproj, shallow=False):
        raise SystemExit(f"{prproj} is no longer the approved project's copy (built or saved since): use a new --out")
    shutil.copy2(approved, prproj)
    print(json.dumps(start(), ensure_ascii=False))
    r = call(f"aidvStageReview({json.dumps(job, ensure_ascii=False)})", timeout=900, reload=True)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    (prproj.parent / "build_result.json").write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0 if r.get("saved") and not r.get("problems") else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("approved_dir")
    ap.add_argument("--out", default="pip_review_r1")
    ap.add_argument("--still-s", type=float, default=STILL_S)
    ap.add_argument("--keep-clear", default=None, help="the exercise's list of what the box keeps clear of that no "
                    "measure sees (keep_clear), e.g. exercises/<ex>/pip_keep_clear.json")
    ap.add_argument("--presence", default=None, help="a presence budget: the exercise's moments that matter (e.g. "
                    "exercises/<ex>/pip_presence.json); the box shows only around them, voice only elsewhere")
    ap.add_argument("--tiers", default="1", help="the presence list's tiers that count, e.g. 1 or 1,2")
    ap.add_argument("--linger", type=float, default=PRESENCE_LINGER_S, help="seconds the box stays after a moment")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--no-build", action="store_true")
    g.add_argument("--build-only", action="store_true")
    a = ap.parse_args(argv)
    run_dir, approved_dir = Path(a.run_dir).resolve(), Path(a.approved_dir).resolve()
    out = run_dir / a.out
    out.mkdir(parents=True, exist_ok=True)
    (approved,) = list(approved_dir.glob("*_full.prproj"))
    if a.build_only:
        return build(json.loads((out / "pip_job.json").read_text(encoding="utf-8")), approved)
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    fps, W, H, run = plan["fps"], plan["width"], plan["height"], plan["run_id"]
    from pipeline.edit.ppro import final
    nest = f"{run} full"
    N = final.nest_frames(approved_dir, nest)
    if N != plan["durationInFrames"]:
        raise SystemExit(f"the approved sequence is {N} frames, the plan {plan['durationInFrames']}: not its plan")
    changed = captions_as_built(approved_dir)
    if changed:
        raise SystemExit(f"the approved project's caption titles differ from its job ({len(changed)} changes, first "
                         f"{changed[0]}): the placement would miss them")
    if edge_room(W, H) < EDGE_PX:
        raise SystemExit(f"the oval's spots keep {edge_room(W, H):.1f} px from the frame's edges, under {EDGE_PX}")
    extra = keep_clear(a.keep_clear, approved_dir)
    blocked, why, counts = blocked_frames(run_dir, approved_dir, plan, out, nest, N, extra)
    busy = busyness(run_dir, plan, N, out)
    drawing = drawing_frames(plan, N)
    budget, pres = None, None
    if a.presence:                                        # the box only around the moments that matter
        tiers = {int(t) for t in a.tiers.split(",")}
        lines = json.loads((Path(a.presence).parent / "lines.json").read_text(encoding="utf-8"))
        wins, moments = presence(a.presence, plan, lines, tiers, a.linger, approved_dir)
        budget = budget_mask(wins, N)
        pres = {"file": str(Path(a.presence).resolve()), "tiers": sorted(tiers), "lead_s": PRESENCE_LEAD_S,
                "linger_s": a.linger, "merge_s": PRESENCE_MERGE_S,
                "wanted_s": round(float((~budget[0]).sum()) / fps, 1),
                "wanted_pct": round(100 * float((~budget[0]).sum()) / N, 1),
                "windows": [{"f0": f0, "f1": f1, "start_tc": tc(f0, fps), "end_tc": tc(f1, fps), "for": w}
                            for f0, f1, w in wins], "moments": moments}
    # R231: the intro's oval lands where the box starts (the corner picked at frame 0); the outro's oval takes over in
    # the last OUTRO_S at that corner when it is clear then
    spans, intro_spot, outro_spot, warnings = placement(blocked, why, fps, busy, drawing, budget)
    for s in spans:                                       # how busy the screen is under each shown span (the record)
        if s["spot"] != "hidden":
            s["busy"] = round(float(busy[HOME.index(s["spot"]), s["f0"]:s["f1"]].mean()), 2)
    bad = check_spans(spans, blocked, fps, N)
    clashes = fade_clashes(spans, drawing, fps)
    stats = summarize(spans, fps, N)
    for s in spans:
        s.update({"start": round(s["f0"] / fps, 4), "end": round(s["f1"] / fps, 4), "start_tc": tc(s["f0"], fps),
                  "end_tc": tc(s["f1"], fps)})
    marks = markers(spans, fps, N)
    doc = {"about": "R220, R222, R224, R231, R232, X6: the picture-in-picture oval's place through the approved "
                    "sequence (pipeline.edit.pip). Times in seconds on that sequence; f0/f1 frames, end exclusive. "
                    "handover: where the intro's oval lands (the box is up there from frame 0) and where the outro's "
                    "oval appears in the last outro_s (pipeline.edit.stage reads both). presence: the presence "
                    "budget's moments and the windows the box may show in (null: none).",
           "box": {"scale": SCALE, "oval_px": [OVAL_W, OVAL_H], "feather_px": FEATHER_PX, "edge_px": EDGE_PX,
                   "edge_room_px": edge_room(W, H), "inside": str(CITY),
                   "spots": {k: list(v) for k, v in corners(W, H).items()}},
           "handover": {"intro_spot": intro_spot, "outro_spot": outro_spot, "outro_s": OUTRO_S,
                        "box_up_at_end": spans[-1]["spot"] == outro_spot and spans[-1]["f1"] == N},
           "rules": {"fade_s": FADE_S, "min_stay_s": MIN_STAY_S, "min_hidden_s": MIN_HIDDEN_S, "clear_px": CLEAR_PX,
                     "long_s": LONG_S, "pointer_stay_s": POINTER_STAY_S, "home": list(HOME),
                     "pick": "clear longest (to long_s), then quietest, then home"},
           "keep_clear": {"file": str(Path(a.keep_clear).resolve()) if a.keep_clear else None, "items": extra},
           "presence": pres,
           "fps": fps, "frames": N, "obstacles": counts, "stats": stats, "problems": bad, "fade_clashes": clashes,
           "warnings": warnings,
           "spans": spans,
           "markers": marks}
    (out / "pip_spans.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(json.dumps({"stats": stats, "problems": bad, "fade_clashes": clashes, "obstacles": counts,
                      "handover": doc["handover"]}, indent=1))
    if bad:
        return 1
    comp, px, src = avatar_still(run_dir, a.still_s, CITY)          # R232: the cityscape inside the oval
    from PIL import Image
    Image.fromarray(comp).save(out / f"avatar_still_{a.still_s:.1f}s.png")
    oval = oval_rgba(comp, px)
    oval.save(out / "pip_oval.png")
    pngs = corner_pngs(oval, out, W, H)
    xml = review_xml(spans, pngs, out, run, N, fps, W, H)
    prproj = out / f"{run}_pip_review.prproj"
    from pipeline.edit.ppro.project import BINS
    job = {"prproj": str(prproj.resolve()), "xml": str(xml.resolve()), "nest": nest, "fps": fps, "nest_frames": N,
           "still": {"render": src, "t_s": a.still_s, "person_x": px, "inside": str(CITY)},
           "pngs": {k: str(p.resolve()) for k, p in pngs.items()},
           "sequences": [{"name": SEQ_NAME, "at_frame": 0, "in_frame": 0, "out_frame": N, "markers": marks}],
           "bins": {**BINS, "media": BINS["media"] + [{"bin": "Avatar box", "match": r"[\\/]pip_oval_[^\\/]+\.png$"}]}}
    (out / "pip_job.json").write_text(json.dumps(job, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.no_build:
        return 0
    if prproj.exists():
        raise SystemExit(f"{prproj} exists (David's?); not overwriting it: use a new --out")
    return build(job, approved)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
