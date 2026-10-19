"""The avatar's stage (R205 to R209): the intro and outro as transparent Remotion clips (AvatarStage), and a review
project in Premiere of their variants, for David to judge.

    python -m pipeline.edit.stage runs/<run_id> <avatar steps file> <approved review folder> [--out=stage_review_r1]
                                  [--no-render] [--no-build]

Reads the transparent avatar renders (avatar/avatar.json "graphics_alpha", pipeline.edit.avatar main_alpha), the
lines' word timings (audio_cache/<key>.json) and the steps file's "stage" block (the card's rows, each on its word in
the intro and ticking on its word in the recap; the moves; the variants). Every time is worked out on the stage clip:
  * the intro clip starts PAD_S - OPEN_HEAD_S into its render, nudged so the approved sequence, nested at a whole
    frame, plays its first line exactly where the avatar speaks it (R205); the clip's checkerboard (R206) gives way
    to the card grown full screen, then to the "Part 1" ChapterCard drawn as the approved sequence's own (the same
    layer from its cards.json), which takes over beneath it once both are settled; the avatar leaves after the
    carried sentence, one way per variant;
  * the outro clip starts PAD_S - RECAP_HEAD_S into its render, fades in over the approved sequence's last
    OUTRO_FADE_S (the dissolve, baked in), its voice 0.2 s after (R100); the recap card ticks; then the subscribe
    card (R209, one look per variant) and David's url.mov write-on, and the hard cut to the logo (R96).
Each clip is rendered once up to where its variants differ, then a tail per variant (remotion/scripts/stage.mjs).
The voices are the uploaded audio through the round's loudness chain, at the clip level that puts them at the
narration's level in Premiere's mix (as pipeline.edit.ppro.final does).

The review project is a copy of the approved one (R61, R104: the approved project is never opened): one short
sequence per variant, the approved sequence nested on V1 for the stretch around the join (aidvStageReview), the
stage on V2, the avatar's voice on A3, its sound cues on "Stage sounds" (R158, R137), the captions on top (the
avatar's lines, and a copy of each approved caption the avatar would cover), the logo outro after the outro.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from pipeline.config import ROOT, tool
from pipeline.edit import cta as ctas
from pipeline.edit import loudness as ldn
from pipeline.edit import premiere as pr
from pipeline.edit.avatar import CACHE, OPEN_HEAD_S, PAD_S, RECAP_HEAD_S, RECAP_TAIL_S
from pipeline.edit.ppro import final, titles
from pipeline.edit.ppro.bridge import call, start
from pipeline.edit.ppro.project import BINS
from pipeline.narration import timing

REMOTION = ROOT / "remotion"
OUTRO_FADE_S = 0.8              # the outro fades in over the approved sequence's last 0.8 s (R100's dissolve)
INTRO_NEST_S = 12.0             # how much of the approved sequence an intro sequence shows after the join
OUTRO_NEST_S = 10.0             # and an outro sequence before it
CARD_BOX = {"x": 720, "y": 60, "w": 1104, "h": 750}        # the right two thirds, above the captions (y 870, G15)
SUB_BOX = {"x": 720, "y": 300, "w": 1104, "h": 300}
URL_BOX = {"x": 800, "y": 330, "w": 960, "h": 230}
CHECK_STILLS = 8                # stills per clip for the checks and the visual review
CHUNK_FRAMES = 300              # a longer clip renders in parts of this many frames, joined after (render())
URL_WIDTH = 1280                # url.mov's 4K write-on, scaled for the stage (it shows about 1,150 px wide)
URL_BRIGHTNESS = 0.6            # its strokes darkened to reach 7:1 on the cream panel (median 8.7:1; 4.4:1 as made)
SCRATCH = Path("G:/aidv_scratch/remotion_tmp")      # Remotion's temp copies (David's wipeable SD card), else C:
# The box design (round 5; the steps file's stage "design": "box"; R220, R222, R224, R225, R228): full frame on B1,
# then the ep04 oval (pipeline.edit.pip's geometry) with the Brand Stage teal inside, B1 staying behind as the stage.
B1 = ROOT / "research" / "backgrounds" / "stage_r2" / "stage_gpt25_a.png"    # R225, 2560 x 1440 (cover-cropped)
BOX_MOVE_S = 0.6                # the shrink into the oval and the growth back: linear, as David's ep04
SIGN_BOX = (150, 80, 570, 580)  # B1's neon sign (and its cable) on the 1920 x 1080 stage: the oval keeps off it
URL_BOX_FULL = {"x": 1130, "y": 190, "w": 694, "h": 180}    # the write-on beside the full-frame avatar's head
FULL_SHIFT_X = -100             # and the avatar moved left that far at full frame, for room (the visual review, r5)
CREAM = (248, 246, 243)         # R228: the write-on recoloured cream (the tokens' cream), with no panel (R212)
# The Quick Series design (round 6; the steps file's stage "design": "quick"; R231, R232): the cityscape held still
# behind the transparent avatar; full frame, the left third beside the card, the picture-in-picture oval (at the spot
# pipeline.edit.pip's placement hands over at); the call to action is David's own QuickArch03 footage, placed by
# research/backgrounds/refs_ep03/ep03_cta.json.
CTA = ROOT / "research" / "backgrounds" / "refs_ep03" / "ep03_cta.json"
CTA_TRACK = "Call to action (QuickArch03)"
STILL_TRACK = "Avatar box (still)"
CLEAR_PX = 12                   # room kept between a caption and the avatar (pipeline.edit.pip's CLEAR_PX)
REACH_ALPHA = 64                # the avatar's reach: its pixels of alpha this or more (as pip's DRAWN_ALPHA)
SMALL_WORDS = {"a", "an", "the", "to", "and", "or", "of", "in", "on", "at", "for", "with", "by", "from", "as", "so",
               "its", "your", "my", "our", "their"}   # never the last word of a caption split (phrase_cues)
MOTION_S, ROW_IN_S = 0.5, 0.4   # the card's slide in (tokens motion.baseS) and a row's rise (AvatarStage RoadCard)


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def words_of(line):
    """A lines.json entry's words and starts, with the word times it was built with (R227)."""
    return [(norm(w["word"]), w["start"]) for w in timing.of(line)["words"]]


def at_word(words, spec):
    """A word's start in its line: spec {"word", "nth"?, "after"?}, the nth match (1 by default) at or after the
    first match of "after"."""
    w, nth, i0 = norm(spec["word"]), spec.get("nth", 1), 0
    if spec.get("after"):
        i0 = next(i for i, (x, _) in enumerate(words) if x == norm(spec["after"]))
    hits = [t for x, t in words[i0:] if x == w]
    if len(hits) < nth:
        raise SystemExit(f"no word {spec} in the line")
    return hits[nth - 1]


def quoted_words(doc):
    """The words the quick design's markers quote (R106), from the steps file, its lines and the call to action's
    file, so another exercise's markers name what its video says: the intro's last sentence ("closing"), the recap's
    sentence that opens on the card's word ("recap"), the call to action's word ("subscribe") and the url's anchor
    word ("url"), and the word the avatar moves to the left third on ("left"). Section A's: "So, let's get
    started.", "Let's recap.", "If", "Visit", "So"."""
    lines = json.loads((ROOT / "exercises" / doc["exercise"] / "lines.json").read_text(encoding="utf-8"))
    lines = lines.get("lines", lines)
    text = {s.get("graphics"): lines[s["narration"]["line_id"]]["text"] for s in doc["steps"]}
    sentences = lambda t: re.split(r"(?<=[.!?])\s+", t.strip())
    r = doc["stage"]["recap"]
    card = norm(r["card_on"]["word"])
    return {"closing": sentences(text["opening"])[-1],
            "recap": next((s for s in sentences(text["recap"]) if norm(s.split()[0]) == card), r["card_on"]["word"]),
            "subscribe": r["subscribe"]["word"],
            "url": json.loads(CTA.read_text(encoding="utf-8"))["url"]["anchor_word"],
            "left": doc["stage"]["quick"]["left_move"]["word"]}


def nest_card(approved_dir):
    """The approved sequence's first chapter card, as its review built it (cards.json), so the stage draws the same."""
    for c in json.loads((approved_dir / "cards.json").read_text(encoding="utf-8")):
        if c["layer"].get("layout") == "chapter_card":
            return c["layer"]
    raise SystemExit(f"no chapter card in {approved_dir / 'cards.json'}")


def url_box(path):
    """Where url.mov's writing sits in its own frame at its widest (its last frames), and the frame's size."""
    import numpy as np
    from pipeline.edit import alpha
    v = next(x for x in alpha.probe(path)["streams"] if x.get("width"))
    w, h = v["width"], v["height"]
    dur = float(alpha.probe(path)["format"]["duration"])
    a = alpha.rgba(path, max(0.0, dur - 0.5))[..., 3]
    ys, xs = np.nonzero(a > 16)
    return {"x": int(xs.min()), "y": int(ys.min()), "w": int(xs.max() - xs.min() + 1),
            "h": int(ys.max() - ys.min() + 1)}, w, h


def small(src, dst, width=None):
    """src as a small WebM with alpha in the stage's public folder (alpha.to_webm), made once."""
    from pipeline.edit import alpha
    if not dst.exists():
        alpha.to_webm(src, dst, width)
    return dst


def backdrop(pub, W, H):
    """The box design's pictures in the stage's public folder: B1 (R225) for the full frame and the stage behind the
    cards, the Brand Stage teal (R224) inside the oval; each cover-cropped to the frame, made once, named by its
    source's name, size and time (a new background or teal gets a new file)."""
    import hashlib
    from PIL import Image
    from pipeline.edit import pip
    tag = lambda q: hashlib.sha256(f"{q.name}|{q.stat().st_size}|{q.stat().st_mtime_ns}".encode()).hexdigest()[:8]
    names = {"full": f"stage_b1_{W}x{H}_{tag(B1)}.png", "inside": f"stage_teal_{W}x{H}_{tag(pip.TEAL)}.png"}
    for key, src in (("full", B1), ("inside", pip.TEAL)):
        if not (pub / names[key]).exists():
            pip.cover(Image.open(src).convert("RGB"), W, H).save(pub / names[key])
    return names


def person_x(render, times=(0.1, 0.4, 0.7)):
    """The person's centre in a transparent render's frame: the median x of the head (the top two fifths' opaque
    pixels) over a few frames (times: fractions of its length), so the oval centres on the face
    (pipeline.edit.pip.avatar_still's measure)."""
    import numpy as np
    from pipeline.edit import alpha
    xs, dur = [], float(alpha.probe(render)["format"]["duration"])
    for t in times:
        f = alpha.rgba(render, t * dur)
        xs.append(np.nonzero(f[: f.shape[0] * 2 // 5, :, 3] > 128)[1])
    xs = np.concatenate(xs)
    if not len(xs):
        raise SystemExit(f"no person found in {render}")
    return float(np.median(xs))


def box_spot(avoid, W, H):
    """The first of ep04's spots (pipeline.edit.pip.HOME: bottom right first) whose oval keeps clear of every box in
    avoid ({x, y, w, h}) and of B1's sign."""
    from pipeline.edit import pip
    boxes = [(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]) for b in avoid] + [SIGN_BOX]
    for k in pip.HOME:
        if not any(pip.touches(pip.corners(W, H)[k], b) for b in boxes):
            return k
    raise SystemExit(f"no spot for the oval clear of {boxes}")


def box_props(render, avoid, stage_bg, W, H):
    """AvatarStage's box (AvatarBox): ep04's oval at the spot box_spot finds, centred on the person."""
    from pipeline.edit import pip
    spot = box_spot(avoid, W, H)
    cx, cy = pip.corners(W, H)[spot]
    return {"spot": spot, "cx": cx, "cy": cy, "personX": person_x(render), "scale": pip.SCALE, "w": pip.OVAL_W,
            "h": pip.OVAL_H, "featherPx": pip.FEATHER_PX, "full": stage_bg["full"], "inside": stage_bg["inside"]}


def recolour(src, dst, rgb):
    """A transparent WebM with every pixel's colour set to rgb, its alpha kept (R228: url.mov's write-on in cream),
    made once."""
    from pipeline.edit import alpha
    if not dst.exists():
        part = dst.with_name("_part_" + dst.name)
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", *alpha._decoder(src), "-i", str(src), "-vf",
                        f"format=rgba,lutrgb=r={rgb[0]}:g={rgb[1]}:b={rgb[2]}", "-an", "-c:v", "libvpx-vp9",
                        "-pix_fmt", "yuva420p", "-crf", "18", "-b:v", "0", "-auto-alt-ref", "0", "-row-mt", "1",
                        "-deadline", "good", "-cpu-used", "2", "-f", "webm", str(part)], check=True)
        part.replace(dst)
    return dst


def plan_stage(run_dir, doc, plan, approved_dir, pub):
    """Both clips' props (common and per-variant tails) and where they sit; all times in seconds on each clip."""
    fps, W, H = plan["fps"], plan["width"], plan["height"]
    lines = json.loads((ROOT / "exercises" / doc["exercise"] / "lines.json").read_text(encoding="utf-8"))
    log = json.loads((run_dir / "avatar" / "avatar.json").read_text(encoding="utf-8"))["graphics_alpha"]
    st, rows_spec = doc["stage"], doc["stage"]["card"]
    base = {"fps": fps, "width": W, "height": H}

    # the intro
    g = log["opening"]
    g = {**g, **timing.provenance_for(lines, g["line_id"], g["audio_key"])}   # R227: captions take the line's times
    words = words_of(lines[g["line_id"]])
    first = min(n["start"] for n in plan["narration"])      # the approved sequence's first line, into the sequence
    c = g.get("carry")
    if not c:
        raise SystemExit("the intro render carries no line (the steps file's carry_into, R205): render it again")
    nest_at = round((c["at_s"] - first - (g["voice_at_s"] - OPEN_HEAD_S)) * fps)   # whole frames on the timeline
    trim = c["at_s"] - first - nest_at / fps                # the render's time at the clip's start
    tau = lambda t: g["voice_at_s"] + t - trim              # a word's time in the line -> the clip
    o = st["opening"]
    box = st.get("design") == "box"                         # round 5's box, else R208's left third
    if box and o["exits"] != ["dissolve"]:                  # the box leaves only by exit C (R215)
        raise SystemExit(f"the box design's intro exits by the dissolve alone, not {o['exits']}")
    mv = o["shrink"] if box else o["move_left"]
    move_at = tau(at_word(words, mv)) - mv["dur_s"]
    ex = o["expand"]
    card_l = nest_card(approved_dir)
    inS = json.loads((REMOTION / "src" / "overlays" / "tokens.json").read_text(encoding="utf-8"))[
        "motion"]["composition"]["chapterCard"]["inS"]       # ChapterCard's entrance
    # The Part 1 card enters exactly with the approved sequence's own (its t0 there, with its whoosh, R158): the
    # roadmap card holds through "So, let's get started." and grows to the full frame in the pause, ending then.
    card_in = nest_at / fps + card_l["t0"]
    exp_at = card_in - ex["dur_s"]
    chapter = {"t0": card_in, "kicker": card_l.get("kicker", ""), "title": card_l["title"],
               "variant": card_l["variant"], "until": card_in + inS + 0.2}
    rows = [{"text": r["text"], "level": r["level"], "at": tau(at_word(words, r))} for r in rows_spec]
    said = c["at_s"] + c["cut_s"] - trim                    # the carried sentence's end
    exit_at = nest_at / fps + card_l["t1"] - card_l.get("exit_s", 0.6)   # with the Part 1 card's own fade (the review)
    last_word = tau(timing.of(lines[g["line_id"]])["words"][-1]["end"])
    hold = 2.0 + 0.3 * max(0, len(rows_spec[-1]["text"].split()) - 5)        # T7: the last row stays up to be read
    for ok, what in ((exp_at >= rows[-1]["at"] + hold, f"the card grows {exp_at - rows[-1]['at']:.2f} s after its last "
                      f"row, under T7's {hold:.1f} s"),
                     (exp_at >= last_word, f"the card grows at {exp_at:.2f} s, before the intro's last word ends "
                      f"({last_word:.2f} s)"),
                     (exit_at >= move_at + mv["dur_s"], "the avatar's exit starts before its move has ended")):
        if not ok:
            raise SystemExit(f"the intro's timing: {what}")
    dur = round((max(exit_at + o["exit_s"], said) + 0.1) * fps + 0.5 - 1e-6)            # ceil, free of float noise
    intro = {**base, "durationInFrames": dur,
             "avatar": {"src": small(run_dir / g["file"], pub / (Path(g["file"]).stem + ".webm")).name,
                        "trimBeforeS": trim,
                        "start": "full", "moves": [{"at": move_at, "dur": mv["dur_s"], "to": "left"}]},
             "checkerUntil": exp_at + ex["dur_s"],
             "card": {"t0": move_at + mv["dur_s"], "t1": chapter["until"] + 1, "outS": 0.5, "box": CARD_BOX, "rows": rows,
                      "variant": card_l["variant"], "expand": {"at": exp_at, "dur": ex["dur_s"]}},
             "chapter": chapter}
    if box:                                                 # full frame on B1, shrinking into the oval on "So"
        stage_bg = backdrop(pub, W, H)
        intro.pop("checkerUntil")
        intro["backdrop"] = {"src": stage_bg["full"], "until": exp_at + ex["dur_s"]}
        intro["avatar"]["box"] = box_props(run_dir / g["file"], [CARD_BOX], stage_bg, W, H)
        intro["avatar"]["moves"] = [{"at": move_at, "dur": mv["dur_s"], "to": "box"}]
    split_i = round(exit_at * fps)
    intro_sounds = [[move_at + mv["dur_s"], "pop"]] + [[r["at"], "tick"] for r in rows]     # R158; the Part 1 card's
                                                                         # whoosh is the approved sequence's own
    intro_tails = {e: {**intro, "avatar": {**intro["avatar"], "exit": {"style": e, "at": exit_at, "dur": o["exit_s"]}}}
                   for e in o["exits"]}

    res = {"fps": fps, "intro": intro, "intro_tails": intro_tails, "intro_split": split_i, "nest_at": nest_at,
           "intro_trim_s": trim, "intro_render": g, "first_line_s": first, "intro_sounds": intro_sounds,
           "times": {"intro_move": move_at, "intro_expand": exp_at, "intro_carry": c["at_s"] - trim,
                     "intro_exit": exit_at}}
    if "recap" not in log:                                 # its render isn't there yet: the intro alone
        return res

    # the outro
    g2 = log["recap"]
    g2 = {**g2, **timing.provenance_for(lines, g2["line_id"], g2["audio_key"])}
    words2 = words_of(lines[g2["line_id"]])
    trim2 = PAD_S - RECAP_HEAD_S
    tau2 = lambda t: g2["voice_at_s"] + t - trim2
    r2 = st["recap"]
    card2 = tau2(at_word(words2, r2["card_on"]))           # the recap card on "Let's recap." (R80)
    sub = r2["subscribe"]
    sub_at = tau2(at_word(words2, sub))
    rows2 = [{"text": r["text"], "level": r["level"], "at": card2 + 0.5,       # once the panel is opaque (G7)
              "tick": tau2(at_word(words2, r["tick"]))} for r in rows_spec]
    end2 = g2["voice_at_s"] - trim2 + g2["voice_s"] + RECAP_TAIL_S
    u = r2["url"]
    url_web = small(Path(u["file"]), pub / (Path(u["file"]).stem + f"_{URL_WIDTH}.webm"), URL_WIDTH)
    ub, uw, uh = url_box(url_web)
    outro = {**base, "durationInFrames": round(end2 * fps), "fadeInS": OUTRO_FADE_S, "checkerUntil": end2 + 1,
             "avatar": {"src": small(run_dir / g2["file"], pub / (Path(g2["file"]).stem + ".webm")).name,
                        "trimBeforeS": trim2, "start": r2.get("start", "left"), "moves": []},
             "card": {"t0": card2, "t1": sub_at, "outS": 0.5, "box": CARD_BOX, "rows": rows2,
                      "variant": card_l["variant"]},
             "url": {"src": url_web.name,
                     "t0": tau2(at_word(words2, u)), "t1": end2, "fadeOutS": u["fade_out_s"], "box": URL_BOX,
                     "srcBox": ub, "srcW": uw, "srcH": uh, "panel": True, "brightness": URL_BRIGHTNESS}}
    card_sub = lambda lk: {"t0": sub_at, "t1": sub_at + sub["length_s"], "look": lk,
                           "bell": tau2(at_word(words2, sub["bell"])), "thumb": tau2(at_word(words2, sub["thumb"])),
                           "box": SUB_BOX}
    if box:                  # in the oval beside the cards on B1; the write-on cream with no panel (R212, R228); the
        stage_bg = backdrop(pub, W, H)                     # endings differ from the growth back, just before "Visit"
        cream = recolour(url_web, pub / (url_web.stem + "_cream.webm"), CREAM)
        outro.pop("checkerUntil")
        outro["backdrop"] = {"src": stage_bg["full"], "until": end2 + 1}
        outro["avatar"].update({"start": "box", "box": box_props(run_dir / g2["file"], [CARD_BOX, SUB_BOX, URL_BOX],
                                                                 stage_bg, W, H)})
        outro["url"] = {**outro["url"], "src": cream.name, "panel": False}
        outro["url"].pop("brightness")
        outro["subscribe"] = card_sub(r2.get("look", "brand"))              # R211: the brand look alone
        grow_at = outro["url"]["t0"] - BOX_MOVE_S                            # full frame by "Visit"
        if grow_at < outro["subscribe"]["t1"]:
            raise SystemExit(f"the outro grows back at {grow_at:.2f} s, before the subscribe card has gone")
        endings = {"oval": {}, "full": {"avatar": {**outro["avatar"], "moves": [{"at": grow_at, "dur": BOX_MOVE_S,
                                                                                 "to": "full"}],
                                                   "box": {**outro["avatar"]["box"], "fullShiftX": FULL_SHIFT_X}},
                                        "url": {**outro["url"], "box": URL_BOX_FULL}}}
        outro_tails = {e: {**outro, **endings[e]} for e in r2["endings"]}
        split2 = round(grow_at * fps) - 6                  # a little before the growth, which the tails carry
        st0 = outro["subscribe"]
        res["times"]["outro_grow"] = grow_at
    else:
        outro_tails = {lk: {**outro, "subscribe": card_sub(lk)} for lk in r2["looks"]}
        split2 = round(sub_at * fps) - 6                   # a little before the card, which the tails carry
        st0 = outro_tails[r2["looks"][0]]["subscribe"]
    res["outro_sounds"] = ([[card2, "pop"]] + [[r["tick"], "tick"] for r in rows2]
                           + [[sub_at, "pop"], [st0["bell"], "click"], [st0["thumb"], "click"], [outro["url"]["t0"], "pop"]])
    res.update({"outro": outro, "outro_tails": outro_tails, "outro_split": split2, "outro_render": g2})
    res["times"].update({"outro_card": card2, "outro_subscribe": sub_at, "outro_url": outro["url"]["t0"],
                         "outro_end": end2})
    return res


# ------------------------------------------------------------------------------------------- the Quick Series design
def room_file(pub, W, H):
    """R232: the cityscape cover-scaled to the frame in the stage's public folder, named by its source's name, size and
    time, made once."""
    import hashlib
    from PIL import Image
    from pipeline.edit import pip
    s = pip.CITY.stat()
    name = f"stage_city_{W}x{H}_{hashlib.sha256(f'{pip.CITY.name}|{s.st_size}|{s.st_mtime_ns}'.encode()).hexdigest()[:8]}.png"
    if not (pub / name).exists():
        pip.cover(Image.open(pip.CITY).convert("RGB"), W, H).save(pub / name)
    return name


def media_s(path):
    """A media file's duration in seconds (its container's)."""
    return float(json.loads(subprocess.run([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of",
                                            "json", str(path)], capture_output=True, text=True,
                                           check=True).stdout)["format"]["duration"])


def alpha_union(path, t0, t1, q=4, rate=2.0):
    """Where a transparent clip draws (alpha REACH_ALPHA or more) at any of its frames from t0 to t1 s of its file,
    sampled rate times a second: a boolean mask at 1/q of its frame size, and q."""
    import numpy as np
    from pipeline.edit import alpha
    v = next(x for x in alpha.probe(path)["streams"] if x.get("width"))
    w, h = v["width"] // q, v["height"] // q
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", *alpha._decoder(path), "-ss", f"{max(0.0, t0):.4f}", "-i",
                          str(path), "-t", f"{max(0.05, t1 - t0):.4f}", "-vf", f"fps={rate},scale={w}:{h}", "-pix_fmt",
                          "rgba", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    n = len(raw) // (w * h * 4)
    if not n:
        raise SystemExit(f"no frames read from {path} ({t0:.2f} to {t1:.2f} s)")
    fr = np.frombuffer(raw[:n * w * h * 4], np.uint8).reshape(n, h, w, 4)[..., 3] >= REACH_ALPHA
    return fr.any(axis=0), q


def mask_box(mask, q):
    """A union mask's box in its frame's px: (x0, y0, x1, y1)."""
    import numpy as np
    ys, xs = np.nonzero(mask)
    return (int(xs.min()) * q, int(ys.min()) * q, (int(xs.max()) + 1) * q, (int(ys.max()) + 1) * q)


def quick_pose(qk, place, W, H):
    """AvatarStage's quickPose: a pose's maps (k, tx, ty: x' = k x + tx) from the render's frame to the stage, for the
    avatar and the room, and its window (x0, y0, x1, y1, rx, ry)."""
    if place == "box":
        b = qk["box"]
        m = (b["scale"], b["cx"] - b["personX"] * b["scale"], b["cy"] - H / 2 * b["scale"])
        return {"avatar": m, "room": m, "win": (b["cx"] - b["w"] / 2, b["cy"] - b["h"] / 2, b["cx"] + b["w"] / 2,
                                                b["cy"] + b["h"] / 2, b["w"] / 2, b["h"] / 2)}
    if place == "left":
        s = qk["leftScale"]
        return {"avatar": (s, W / 2 * (1 - s) + qk["leftX"], H * (1 - s)), "room": (1, 0, 0),
                "win": (0, 0, qk["leftW"], H, 0, 0)}
    return {"avatar": (1, 0, 0), "room": (1, 0, 0), "win": (0, 0, W, H, 0, 0)}


def quick_state(avatar, t):
    """AvatarStage's quickState: (from, to, p) at clip time t; settled when from == to."""
    frm = avatar["start"]
    for m in sorted(avatar["moves"], key=lambda m: m["at"]):
        if t < m["at"]:
            break
        p = min(1.0, max(0.0, (t - m["at"]) / m["dur"])) if m["dur"] > 0 else 1.0
        if p < 1:
            return frm, m["to"], p
        frm = m["to"]
    return frm, frm, 1.0


def to_src(m, box):
    """A stage box (x0, y0, x1, y1) in the render's own px under the map m (k, tx, ty)."""
    k, tx, ty = m
    return ((box[0] - tx) / k, (box[1] - ty) / k, (box[2] - tx) / k, (box[3] - ty) / k)


def mask_hits(mask, q, box):
    """Whether a union mask (1/q px) has any pixel inside box (its frame's px)."""
    h, w = mask.shape
    x0, y0 = max(0, int(box[0] // q)), max(0, int(box[1] // q))
    x1, y1 = min(w, int(math.ceil(box[2] / q))), min(h, int(math.ceil(box[3] / q)))
    return x1 > x0 and y1 > y0 and bool(mask[y0:y1, x0:x1].any())


SOUNDED_DB = -40.0               # under the line's speech level: silence, as breaths.beat_point's quiet_db


def last_sound_end(run_dir, plan):
    """Where the approved sequence's last spoken sound ends, in its seconds: in the clip the edit plays (the plan's
    "src", after the loudness pass: Fable, round 7), the end of the last frame from the last word's start louder than
    SOUNDED_DB under the clip's speech (breaths' frames and speech level), through the line's parts. Measured in the
    audio: ElevenLabs logs a word's end late (GOTCHAS)."""
    import numpy as np
    from pipeline.narration import breaths
    n = max(plan["narration"], key=lambda x: x["start"])
    w = timing.of(n)["words"][-1]
    src = run_dir / n["src"]
    feat = breaths._features_of(src)
    rel = feat[:, 0] - breaths.speech_level(feat)
    t = (np.arange(len(feat)) * breaths.HOP + breaths.WIN / 2) / breaths.SR
    loud = np.flatnonzero((t >= w["start"]) & (rel > SOUNDED_DB))
    if not len(loud):
        raise SystemExit(f"no sound found after {w['word']!r} in {n['line_id']} ({src.name})")
    end = float(t[loud[-1]] + breaths.WIN / 2 / breaths.SR)
    part = next((p for p in n["parts"] if p["in"] - 1e-6 <= end <= p["out"] + 1e-6), None)
    if part is None:
        raise SystemExit(f"{n['line_id']}: its last sound ({end:.2f} s into its clip) isn't in any of its parts")
    return part["at"] + end - part["in"]


def outro_still_clear(run_dir, approved_dir, plan, pipd, spot, f0, f1, said_end):
    """R235's still at the outro's spot from approved frame f0 to f1, against everything pipeline.edit.pip keeps the
    box off (blocked_frames: captions, overlays, marks, click targets, named things, the keep-clear list, the address
    bar at full frame, the pointer), leaving out only the camera's framing of the last line ("the whole of ...", its
    step's), which has sounded by f0: a whole runs to its clip's logged end, the silent tail after its last word. pip's
    caches are read from a temporary copy (the review folder is David's: never written). Returns [(frame, what)] where
    the spot is taken."""
    import tempfile
    from pipeline.edit import pip
    spans = json.loads((pipd / "pip_spans.json").read_text(encoding="utf-8"))
    extra = pip.keep_clear((spans.get("keep_clear") or {}).get("file"), approved_dir)
    fps, orig = plan["fps"], pip.src_obstacles
    if f0 / fps < said_end:
        raise SystemExit("the outro's still would start before the main body's last word has sounded")
    step = max(plan["narration"], key=lambda x: x["start"])["step"]
    mine = {(int(round(w["t0"] * fps)), f"the whole of {w['what']}") for w in plan.get("wholes") or []
            if w.get("step") == step}                 # the last line's own framing (Fable, round 7: not every whole)

    def src_obstacles(plan_, fps_, starts=()):
        return [o for o in orig(plan_, fps_, starts) if (o[0], o[3]) not in mine]
    with tempfile.TemporaryDirectory() as d:
        for name in ("overlay_hits.json", "named_boxes.json", "busy.npz"):
            if (pipd / name).exists():
                shutil.copy2(pipd / name, Path(d) / name)
        pip.src_obstacles = src_obstacles
        try:
            blocked, why, _ = pip.blocked_frames(run_dir, approved_dir, plan, Path(d), f"{plan['run_id']} full",
                                                 spans["frames"], extra)
        finally:
            pip.src_obstacles = orig
    i = pip.HOME.index(spot)
    return [(fr, why[i].get(fr, "?")) for fr in range(f0, f1) if blocked[i, fr]]


def plan_quick(run_dir, doc, plan, approved_dir, pub, pipd):
    """Round 6 (R231, R232), all times in seconds on each clip:
      * intro: full frame on the cityscape; on "So" (the roadmap card's word) the avatar slides left and shrinks into
        the left third, the card unchanged on the right (the move ends as the word starts, the card sliding in from
        it); after "So, let's get started." the card grows into the Part 1 card while the avatar zooms down from the
        left third straight into the oval at the placement's first spot (pip_spans.json "handover"), over the card, no
        dissolve; the oval speaks the main body's first sentence (R205) and goes on as the box when the clip ends;
      * outro: the stage fades in over the approved sequence's last OUTRO_FADE_S (R100's dissolve) with the avatar in
        the oval at the outro's spot; once the sequence's last caption has gone the oval grows back, the cityscape
        filling the frame and the avatar landing in the left third, before "Let's recap." brings the recap card; in
        the pause before the call to action the card fades as the avatar returns to full frame (QuickArch03: full frame
        for it); David's own subscribe animation and url footage (ep03_cta.json) are Premiere clips above the stage,
        placed against our words by ep03's offsets; then the hard cut to the logo outro (R96).
    One left-third pose serves both clips: scaled by the steps file's quick.left_scale about the frame's bottom centre,
    its reach (every frame of both left-third stretches) card_gap_px left of the card."""
    from pipeline.edit import pip
    fps, W, H = plan["fps"], plan["width"], plan["height"]
    lines = json.loads((ROOT / "exercises" / doc["exercise"] / "lines.json").read_text(encoding="utf-8"))
    log = json.loads((run_dir / "avatar" / "avatar.json").read_text(encoding="utf-8"))["graphics_alpha"]
    st, rows_spec, qs = doc["stage"], doc["stage"]["card"], doc["stage"]["quick"]
    spans = json.loads((pipd / "pip_spans.json").read_text(encoding="utf-8"))
    pjob = json.loads((pipd / "pip_job.json").read_text(encoding="utf-8"))
    if spans["box"]["spots"] != {k: list(v) for k, v in pip.corners(W, H).items()}:
        raise SystemExit(f"{pipd}: its spots aren't pipeline.edit.pip's now; run the placement again")
    hand, N = spans["handover"], spans["frames"]
    if final.nest_frames(approved_dir, f"{plan['run_id']} full") != N:
        raise SystemExit(f"{pipd} was placed on a sequence of {N} frames, not the approved one")
    room = room_file(pub, W, H)
    # checkerUntil 0: Remotion merges the composition's defaultProps (STAGE_SAMPLE: a checkerboard for 2 s) into these
    base = {"fps": fps, "width": W, "height": H, "checkerUntil": 0}

    # the intro's timing, as round 5's (plan_stage)
    g = log["opening"]
    g = {**g, **timing.provenance_for(lines, g["line_id"], g["audio_key"])}
    words = words_of(lines[g["line_id"]])
    first = min(n["start"] for n in plan["narration"])
    c = g.get("carry")
    if not c:
        raise SystemExit("the intro render carries no line (the steps file's carry_into, R205): render it again")
    # the clip starts OPEN_HEAD_S before the line's clip in the render: PAD_S, or later where the line was shortened
    # at its start (R234: avatar.json's voice_at_s takes the cut, so the clip opens in the pause before "In"); a render
    # that opens its mouth earlier records its own lead (open_head_s: Avatar V's, so the video opens on a closed mouth)
    nest_at = round((c["at_s"] - first - (g["voice_at_s"] - g.get("open_head_s", OPEN_HEAD_S))) * fps)
    trim = c["at_s"] - first - nest_at / fps
    tau = lambda t: g["voice_at_s"] + t - trim
    o = st["opening"]
    mv, ex = qs["left_move"], o["expand"]                   # round 4's move_left is 0.7 s: it would start inside "map"
    # the move to the left third fits the pause before its word in whole frames (none of a word under it, no caption
    # up while it moves): it ends on the frame the word starts in, and starts after the word before ends, shortening
    # from dur_s only as the pause needs (min 0.4 s)
    so_t = tau(at_word(words, mv))
    end_f = math.floor(so_t * fps + 1e-6)
    prev = max(tau(w["end"]) for w in timing.of(lines[g["line_id"]])["words"] if tau(w["start"]) < so_t - 1e-6)
    start_f = max(end_f - round(mv["dur_s"] * fps), math.ceil(prev * fps - 1e-6))
    if end_f - start_f < 0.4 * fps:
        raise SystemExit(f"the pause before \"{mv['word']}\" holds only {(end_f - start_f) / fps:.2f} s for the move")
    move_at, mv_s = start_f / fps, (end_f - start_f) / fps
    card_l = nest_card(approved_dir)
    inS = json.loads((REMOTION / "src" / "overlays" / "tokens.json").read_text(encoding="utf-8"))[
        "motion"]["composition"]["chapterCard"]["inS"]
    card_in = nest_at / fps + card_l["t0"]
    exp_at = card_in - ex["dur_s"]
    chapter = {"t0": card_in, "kicker": card_l.get("kicker", ""), "title": card_l["title"],
               "variant": card_l["variant"], "until": card_in + inS + 0.2}
    rows = [{"text": r["text"], "level": r["level"], "at": tau(at_word(words, r))} for r in rows_spec]
    said = c["at_s"] + c["cut_s"] - trim
    last_word = tau(timing.of(lines[g["line_id"]])["words"][-1]["end"])
    hold = 2.0 + 0.3 * max(0, len(rows_spec[-1]["text"].split()) - 5)
    for ok, what in ((exp_at >= rows[-1]["at"] + hold, f"the card grows {exp_at - rows[-1]['at']:.2f} s after its last "
                      f"row, under T7's {hold:.1f} s"),
                     (exp_at >= last_word, f"the zoom-down starts at {exp_at:.2f} s, before the intro's last word "
                      f"ends ({last_word:.2f} s)"),
                     (move_at >= 0, "the move to the left third starts before the clip")):
        if not ok:
            raise SystemExit(f"the intro's timing: {what}")
    dur = round((said + 0.1) * fps + 0.5 - 1e-6)
    s0 = spans["spans"][0]                              # the box goes on from the oval: up at frame 0 at the intro's
    if not (s0["spot"] == hand["intro_spot"] and s0["f0"] == 0 and s0["f1"] >= dur - nest_at):    # spot, and still
        raise SystemExit(f"the box's first stay ({s0}) doesn't carry the intro's oval past the clip's end")  # there
    # R237: an intro render whose upload carries the main body through the box's first stay (pip_render's plan; the
    # web-app render, avatar.register_webapp: carry.box_until_main_s) plays the whole stay: the clip runs to the stay's
    # end and the oval fades out there with the box's own fade, as the first main-body render fades in elsewhere
    exit_ = None
    if c.get("box_until_main_s") is not None:
        if abs(c["main_from_s"] - first) > 0.5 / fps:    # the render's carried audio starts at the main body's first
            raise SystemExit(f"the intro render's carry starts at {c['main_from_s']} s of the main body, its first "
                             f"line at {first} s")
        if c["box_until_main_s"] * fps < s0["f1"] - 0.5:
            raise SystemExit(f"the intro render carries the box to {c['box_until_main_s']} s, its first stay runs to "
                             f"{s0['f1'] / fps:.3f} s")
        dur = nest_at + s0["f1"]
        if trim + dur / fps > g["length_s"] + 1e-6:
            raise SystemExit(f"the intro render ({g['length_s']:.2f} s) ends before the box's first stay does")
        fade = round(pip.FADE_S * fps)
        exit_ = {"style": "dissolve", "at": (dur - fade) / fps, "dur": fade / fps}

    # the outro's timing
    g2 = log["recap"]
    g2 = {**g2, **timing.provenance_for(lines, g2["line_id"], g2["audio_key"])}
    wl2 = timing.of(lines[g2["line_id"]])["words"]
    words2 = words_of(lines[g2["line_id"]])
    trim2 = PAD_S - RECAP_HEAD_S
    tau2 = lambda t: g2["voice_at_s"] + t - trim2
    r2 = st["recap"]
    card2 = tau2(at_word(words2, r2["card_on"]))
    end2 = g2["voice_at_s"] - trim2 + g2["voice_s"] + RECAP_TAIL_S
    caps = json.loads((approved_dir / "caption_titles.json").read_text(encoding="utf-8"))["cues"]
    o0 = N - round(OUTRO_FADE_S * fps)                      # the approved sequence's frame where the outro starts
    last_cap = max([0.0] + [(cu["end_frame"] - o0) / fps for cu in caps if cu["end_frame"] > o0])
    grow_at = max(qs["outro_grow_from_s"], last_cap)        # it fades in as it grows (ep03), once the caption has gone
    grow_s = OUTRO_FADE_S - grow_at                         # the cityscape full by the sequence's last frame
    if grow_s < qs["outro_grow_min_s"]:
        raise SystemExit(f"the outro's oval would grow in {grow_s:.2f} s (the last caption ends {last_cap:.2f} s in)")
    # R235: the avatar is there as the main body ends. The oval (a still of the outro render's first frame as the
    # stage draws it, R229, so the moving avatar takes over without a jump) fades in at the outro's spot on the first
    # whole frame after the main body's last word has sounded (measured in its audio: the oval never covers what the
    # last sentence is about while it is said), at least lead_s[0] and at most lead_s[1] before the growth
    lo, hi = qs["outro_oval_lead_s"]
    said_abs = last_sound_end(run_dir, plan)
    said_end = said_abs - o0 / fps                          # stage seconds
    still_t0 = max(math.ceil(said_end * fps - 1e-6) / fps, round((grow_at - hi) * fps) / fps)
    if grow_at - still_t0 < lo - 1e-6:
        raise SystemExit(f"the main body's last word ends {grow_at - said_end:.2f} s before the outro's growth, under "
                         f"the oval's {lo} s lead: it would cover the screen while the last sentence is said")
    if still_t0 > -pip.FADE_S and not hand["box_up_at_end"]:
        raise SystemExit(f"the oval's still would start {still_t0:.2f} s into the stage clip; it fades in before it")
    # pip cleared the outro's spot only for its last OUTRO_S (Fable, round 7): the still's earlier frames are checked
    # here against everything the placement keeps the box off
    taken = [] if hand["box_up_at_end"] else outro_still_clear(
        run_dir, approved_dir, plan, pipd, hand["outro_spot"], o0 + round(still_t0 * fps), o0 + round(grow_at * fps),
        said_abs)
    if taken:
        raise SystemExit(f"the outro's oval would cover {taken[0][1]} at the {hand['outro_spot']} spot (approved frame "
                         f"{taken[0][0]}, {len(taken)} frames): a shorter lead (quick.outro_oval_lead_s)")
    cta_at = tau2(at_word(words2, r2["subscribe"]))         # "If": the call to action
    full_end = math.floor((cta_at - qs["cta_lead_s"]) * fps + 1e-6) / fps            # a whole frame
    full_at = full_end - qs["cta_move_s"]
    before = max(tau2(w["end"]) for w in wl2 if tau2(w["start"]) < cta_at - 1e-6)
    if full_at < before or card2 < OUTRO_FADE_S:
        raise SystemExit(f"the outro's timing: the move to full frame ({full_at:.2f} s) starts before the word ahead of "
                         f"the call to action ends ({before:.2f} s), or the card comes before the stage is in")
    rows2 = [{"text": r["text"], "level": r["level"], "at": card2 + 0.5,
              "tick": tau2(at_word(words2, r["tick"]))} for r in rows_spec]
    cta = json.loads(CTA.read_text(encoding="utf-8"))
    sub, url = cta["subscribe"], cta["url"]
    anim = qs.get("subscribe")                              # R242, R243: the Remotion subscribe animation (the
    if anim:                                                # steps file's quick.subscribe), drawn by the stage on
        layer = ctas.subscribe_layer(anim["variant"], anim["text"],    # round 7's hooks, "subscribe" and "thumbs"
                                     {k: tau2(at_word(words2, {"word": k})) for k in ("subscribe", "thumbs")})
        sub_t0, sub_s = layer["t0"], layer["t1"] - layer["t0"]
        sub = {"remotion": anim["variant"], "composition": ctas.COMPOSITIONS[anim["variant"]], "layer": layer,
               "sounds_s": {k: round(t - sub_t0, 4) for t, k in ctas.subscribe_moments(layer)}}
    else:                                                   # R232's original, a Premiere clip placed as QuickArch03
        sub_t0 = tau2(at_word(words2, {"word": sub["anchor_word"]})) + sub["start_after_word_s"]
        sub_s = media_s(sub["file"])
    url_t0 = tau2(at_word(words2, {"word": url["anchor_word"]})) + url["start_after_word_s"]
    url_media_s = media_s(url["file"])
    if sub_t0 < full_end or end2 - url_t0 > url_media_s - url["in_s"] or url_t0 < sub_t0 + sub_s:
        raise SystemExit(f"the call to action's timing: subscribe {sub_t0:.2f} s (full frame by {full_end:.2f}), url "
                         f"{url_t0:.2f} to {end2:.2f} s ({url_media_s:.1f} s of footage)")

    # the left third: one pose for both clips, measured on every frame of both left-third stretches
    rend_i, rend_o = small(run_dir / g["file"], pub / (Path(g["file"]).stem + ".webm")), \
        small(run_dir / g2["file"], pub / (Path(g2["file"]).stem + ".webm"))
    m_i, q = alpha_union(rend_i, move_at + trim, exp_at + ex["dur_s"] + trim)
    m_o, _ = alpha_union(rend_o, grow_at + trim2, full_end + trim2)
    x0 = min(mask_box(m_i, q)[0], mask_box(m_o, q)[0])
    x1 = max(mask_box(m_i, q)[2], mask_box(m_o, q)[2])
    s = qs["left_scale"]
    left_x = (CARD_BOX["x"] - qs["card_gap_px"]) - W / 2 - (x1 - W / 2) * s
    if W / 2 + (x0 - W / 2) * s + left_x < qs["left_margin_min_px"]:
        raise SystemExit(f"at {s} the avatar's reach runs past the frame's left edge: a smaller left_scale")

    def quick(render, spot, person_x):
        cx, cy = pip.corners(W, H)[spot]
        return {"room": room, "leftScale": s, "leftX": round(left_x, 2), "leftW": CARD_BOX["x"] - qs["card_gap_px"] // 2,
                "box": {"cx": cx, "cy": cy, "personX": person_x, "scale": pip.SCALE, "w": pip.OVAL_W, "h": pip.OVAL_H,
                        "featherPx": pip.FEATHER_PX, "full": room, "inside": room}}

    intro = {**base, "durationInFrames": dur, "design": "quick",
             "avatar": {"src": rend_i.name, "trimBeforeS": trim, "start": "full",
                        "moves": [{"at": move_at, "dur": mv_s, "to": "left"},
                                  {"at": exp_at, "dur": ex["dur_s"], "to": "box"}],
                        **({"exit": exit_} if exit_ else {}),
                        # the oval centres on the person as the box's still does, so the two meet at the hand-over
                        "quick": quick(rend_i, hand["intro_spot"], pjob["still"]["person_x"])},
             "backdrop": {"src": room, "until": exp_at + ex["dur_s"]},
             "card": {"t0": move_at + mv_s, "t1": chapter["until"] + 1, "outS": 0.5, "box": CARD_BOX,
                      "rows": rows, "variant": card_l["variant"], "expand": {"at": exp_at, "dur": ex["dur_s"]}},
             "chapter": chapter}
    # R242, R243: the "Amazon Quick Series" card in the intro's first seconds (the steps file's quick.series), drawn
    # by the stage over the avatar; gone before the avatar moves to the left third
    ser = qs.get("series")
    intro_cue = []
    if ser:
        intro["series"] = ctas.series_layer(ser["title"], ser["lines"], ser.get("t0_s"))
        if ctas.series_shown(intro["series"])[1] > move_at:
            raise SystemExit(f"the series card shows until {ctas.series_shown(intro['series'])[1]:.2f} s, into the "
                             f"move to the left third ({move_at:.2f} s)")
        intro_cue = [[t, k] for t, k in ctas.series_moments(intro["series"])]
    # the outro: the oval fades in over the main body (the box's own fade) and grows to fill the frame over it, as
    # David's ep03 mask does, landing him in the left third; the still cityscape takes over as it lands (R100: the
    # voice 0.2 s after the main body's last frame)
    outro = {**base, "durationInFrames": round(end2 * fps), "design": "quick",       # no fade: the oval's still has
             "fadeInS": 0, "fadeInAt": 0,                     # faded in before the clip (R235), or the box is up
             "avatar": {"src": rend_o.name, "trimBeforeS": trim2, "start": "box",
                        "moves": [{"at": grow_at, "dur": grow_s, "to": "left", "wide": True},
                                  {"at": full_at, "dur": qs["cta_move_s"], "to": "full"}],
                        # centred as the box's still is, so the room inside meets it exactly at a hand-over
                        "quick": quick(rend_o, hand["outro_spot"], pjob["still"]["person_x"])},
             "backdrop": {"src": room, "from": OUTRO_FADE_S, "until": end2 + 1},
             "card": {"t0": card2, "t1": full_at, "outS": qs["cta_card_out_s"], "box": CARD_BOX, "rows": rows2,
                      "variant": card_l["variant"]}}
    if anim:
        outro["subscribeAnim"] = sub["layer"]
    f = lambda t: round(t * fps)
    ser_l = intro.get("series")
    ser_tr = [list(ctas.series_shown(ser_l)[:1]) + [ctas.series_settled(ser_l)[0]],
              [ctas.series_settled(ser_l)[1], ctas.series_shown(ser_l)[1]]] if ser_l else []
    ser_f = [f(ctas.series_settled(ser_l)[0] + 0.1), f(ser_l["t0"] + 3.0)] if ser_l else []
    sub_f = ([f(sub["layer"]["bell"]) + 2, f(sub["layer"]["thumb"]) + 14, f(sub_t0 + 5.0)] if anim else [])
    return {"fps": fps, "design": "quick", "intro": intro, "intro_tails": {"quick": intro},
            "intro_split": f(exp_at) - 6, "nest_at": nest_at, "intro_trim_s": trim, "intro_render": g,
            "intro_carries_first_stay": bool(exit_),
            "first_line_s": first, "intro_sounds": intro_cue + [[move_at + mv_s, "pop"]] + [[r["at"], "tick"] for r in rows],
            "outro": outro, "outro_tails": {"quick": outro}, "outro_split": f(full_at) - 6, "outro_render": g2,
            # R235: the subscribe animation's whoosh, bell and R137 click on its own moments (ep03_cta.json sounds_s)
            "outro_sounds": [[card2, "pop"]] + [[r["tick"], "tick"] for r in rows2]
            + [[sub_t0 + t, k] for k, t in sorted(sub.get("sounds_s", {}).items(), key=lambda kv: kv[1])],
            "outro_still": None if hand["box_up_at_end"] else {    # (the main body's own box is there already)
                "t0": still_t0, "fade_s": pip.FADE_S, "said_end": said_end, "lead_s": grow_at - still_t0},
            "cta": {"subscribe": ({"t0": sub_t0, "s": sub_s, **sub} if anim else
                                  {"file": sub["file"], "t0": sub_t0, "s": sub_s, "alpha": sub["alpha"],
                                   "sounds_s": sub.get("sounds_s", {})}),
                    "url": {"file": url["file"], "t0": url_t0, "t1": end2, "in_s": url["in_s"],
                            "motion": url["motion"], "fade_out_s": url["fade_out_s"], "alpha": url["alpha"]}},
            "pip": {"dir": str(pipd), "handover": hand, "frames": N},
            "left": {"scale": s, "x": round(left_x, 2), "reach_x": [x0, x1],    # his widest reach on the stage
                     "reach_px": [round(W / 2 + (x0 - W / 2) * s + left_x, 1), round(W / 2 + (x1 - W / 2) * s + left_x, 1)]},
            "times": {"intro_move": move_at, "intro_expand": exp_at, "intro_carry": c["at_s"] - trim,
                      "intro_end": dur / fps, **({"intro_box_out": exit_["at"]} if exit_ else {}),
                      "outro_oval_in": still_t0, "outro_grow": grow_at, "outro_card": card2,
                      "outro_full": full_at,
                      "outro_cta": cta_at, "outro_subscribe": sub_t0, "outro_url": url_t0, "outro_end": end2,
                      "outro_visit": url_t0 - url["start_after_word_s"], "outro_cta_full": full_end,
                      **({"intro_series_in": ser_l["t0"], "intro_series_gone": ctas.series_shown(ser_l)[1]}
                         if ser_l else {}),
                      **({"outro_bell": sub["layer"]["bell"], "outro_thumb": sub["layer"]["thumb"],
                          "outro_subscribe_end": sub["layer"]["t1"]} if anim else {})},
            # what moves or fades on purpose (the still checks skip text there: a fading word measures low)
            "transients": {"intro": [[move_at, move_at + mv_s + MOTION_S], [exp_at, chapter["until"] + 0.3]]
                           + [[r["at"], r["at"] + ROW_IN_S] for r in rows] + ser_tr
                           + ([[exit_["at"], dur / fps]] if exit_ else []),
                           "outro": [[0, OUTRO_FADE_S], [card2, card2 + MOTION_S + ROW_IN_S],
                                     [full_at - qs["cta_card_out_s"], full_end + 0.05]]},
            "check_frames": {"intro": ser_f + [f(move_at) + 9, f(move_at + mv_s) + 20, f(exp_at) + 6,
                                               f(exp_at) + 12, f(exp_at + ex["dur_s"]) + 3, f(card_in) + 40,
                                               nest_at + 50]
                             + ([nest_at + s0["f1"] // 2, dur - 20, dur - 4] if exit_ else []),
                             "outro": [3, f(grow_at) + 4, f(OUTRO_FADE_S) + 2, f(card2) + 25, f(full_at) + 8,
                                       f(full_end) + 6, f(sub_t0) + 60, f(url_t0) + 90] + sub_f}}


def voice(run_dir, g, trim, until, plan, out, tag):
    """The avatar's own voice for a clip: its uploaded audio from trim to until (render time), through the round's
    loudness chain (R177), as a mono file; and its clip level. A mono clip in this XML plays at its file's LUFS in
    Premiere's mix, 3 dB under the narration inside the nested sequence (the mix check measured -14.4 against -11.4,
    stage_review_r2; GOTCHAS), so the level adds final.PREMIERE_MONO_DB as pipeline.edit.ppro.final does."""
    ld, lk = plan["settings"]["loudness"], plan["loudness"]
    up = run_dir / "avatar" / json.loads((run_dir / "avatar" / "avatar.json").read_text(encoding="utf-8"))[
        "renders_alpha"][tag]["upload"]
    dst = out / f"voice_{tag}.wav"
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{trim:.4f}", "-i", str(up), "-t",
                    f"{until - trim:.4f}", "-af", ldn.chain(ld, lk["makeup_db"]) + ",aresample=48000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(dst)], check=True)
    return dst, round(lk["voice_lufs_after"] + final.PREMIERE_MONO_DB - ldn.measure([dst])[0], 1)


def audio_clip(track, ids, files, name, start, path, fps, gain_db):
    """A mono WAV on a sound track, as pipeline.edit.premiere places the narration, at gain_db."""
    n = pr.probe_frames(path, fps, whole=True)
    c = pr.clipitem(track, ids, name, start, start + n, 0, n, n, fps, premiereChannelType="mono")
    c.remove(c.find("alphatype"))
    files.el(c, path, frames=n, audio={"rate": 48000, "channels": 1})
    st = pr.sub(c, "sourcetrack")
    pr.sub(st, "mediatype", "audio")
    pr.sub(st, "trackindex", 1)
    if gain_db:
        e = pr.sub(pr.sub(c, "filter"), "effect")
        for tag, v in (("name", "Audio Levels"), ("effectid", "audiolevels"), ("effectcategory", "audiolevels"),
                       ("effecttype", "audiolevels"), ("mediatype", "audio")):
            pr.sub(e, tag, v)
        prm = pr.sub(e, "parameter", authoringApp="PremierePro")
        for tag, v in (("parameterid", "level"), ("name", "Level"), ("valuemin", 0), ("valuemax", 3.98109),
                       ("value", f"{10 ** (gain_db / 20):.5f}")):
            pr.sub(prm, tag, v)
    return c


def meets_stage(sp):
    """Where a registered still (pipeline.edit.still_avatar, R245) meets the stage's own oval at the same corner, so
    the box there shows the stage's picture of it rather than pip's corner picture (the stage draws the oval in
    Remotion, about a fifth softer than pip's Lanczos picture: a one-frame step at the hand-over on a picture that
    doesn't move, 2c's review): "intro", the box's first stay after an intro clip that doesn't carry it; "outro", a
    last stay up at the main body's end (pip's box_up_at_end), which the outro clip takes over. {"intro": bool,
    "outro": bool}; a render (moving) needs neither."""
    still = lambda key: (sp.get(key) or {}).get("source") == "still"
    return {"intro": still("intro_render") and not sp.get("intro_carries_first_stay"),
            "outro": still("outro_render") and bool(((sp.get("pip") or {}).get("handover") or {}).get("box_up_at_end"))}


def render_jobs(sp, out, only=None, stills_only=False):
    """render's jobs, a long clip split in parts: (the jobs as stage.mjs gets them, {clip key: its parts})."""
    jobs = []

    def job(key, props, a, b, stills):
        clip = None if stills_only else {"a": a, "b": b, "out": str(out / "clips" / f"{key}.mov")}
        jobs.append({"key": key, "props": props, "clip": clip,
                     "stills": [{"frame": f, "out": str(out / "stills" / f"{key}_{f:05d}.png")} for f in stills]})

    def picks(a, b, extra=()):
        n = max(2, CHECK_STILLS)
        return sorted({*(round(a + (b - a) * i / (n - 1)) for i in range(n)), *(f for f in extra if a <= f <= b)})

    fps, T = sp["fps"], sp["times"]
    f = lambda s: round(s * fps)
    i_end = sp["intro"]["durationInFrames"] - 1
    cf = sp.get("check_frames") or {}                 # the quick design names its own (mid-move, settled, ...)
    job("intro_common", sp["intro"], 0, sp["intro_split"] - 1,
        picks(0, sp["intro_split"] - 1, cf.get("intro") or [f(T["intro_move"]) + 9, f(T["intro_move"]) + 25,
                                                            f(T["intro_expand"]) + 30, f(T["intro_expand"]) + 75,
                                                            sp["nest_at"] + 50]))   # +9: mid-move
    for k, p in sp["intro_tails"].items():
        job(f"intro_{k}", p, sp["intro_split"], i_end, picks(sp["intro_split"], i_end, cf.get("intro", ())))
    if "outro" not in sp:
        o_end = None
    else:
        o_end = sp["outro"]["durationInFrames"] - 1
    if o_end is not None:
        job("outro_common", sp["outro"], 0, sp["outro_split"] - 1,
            picks(0, sp["outro_split"] - 1, cf.get("outro") or [f(T["outro_card"]) + 25, f(T["outro_subscribe"]) + 20]))
        grow = [f(T["outro_grow"]) + 9, f(T["outro_grow"]) + 25] if "outro_grow" in T else []   # mid-growth, after
        for k, p in sp["outro_tails"].items():
            job(f"outro_{k}", p, sp["outro_split"], o_end,
                picks(sp["outro_split"], o_end, cf.get("outro") or [f(T["outro_subscribe"]) + 20,
                                                                    f(T["outro_url"]) + 90, *grow]))
        if sp.get("outro_still") or meets_stage(sp)["outro"]:   # R235: the oval's still, the outro clip's own
            jobs.append({"key": "outro_oval_still", "props": sp["outro"], "clip": None,   # first frame
                         "stills": [{"frame": 0, "out": str(out / "clips" / "outro_oval_still.png")}]})
        if meets_stage(sp)["intro"]:                  # the intro clip's last frame, for the box after it
            jobs.append({"key": "intro_oval_still", "props": sp["intro"], "clip": None,
                         "stills": [{"frame": sp["intro"]["durationInFrames"] - 1,
                                     "out": str(out / "clips" / "intro_oval_still.png")}]})
        al = alone_job(sp, out)
        if al:
            jobs.append(al)
    if only:
        jobs = [j for j in jobs if j["key"] in only]
    # A long clip renders in parts of CHUNK_FRAMES, each its own renderMedia call with fresh browser tabs, joined
    # after: round 5's 1,470-frame stage clips stopped twice on a tab's font load that never settled (GOTCHAS), the
    # 205-frame tails never did. A part that fails is tried again once.
    parts, split = {}, []
    for j in jobs:
        c = j["clip"]
        if not c or c["b"] - c["a"] + 1 <= CHUNK_FRAMES:
            split.append(j)
            continue
        d = out / "clips" / "_parts"
        cuts = list(range(c["a"], c["b"] + 1, CHUNK_FRAMES))
        parts[j["key"]] = []
        for i, a in enumerate(cuts):
            p = {"key": f"{j['key']}#{i}", "props": j["props"], "stills": j["stills"] if i == 0 else [],
                 "clip": {"a": a, "b": min(c["b"], a + CHUNK_FRAMES - 1), "out": str(d / f"{j['key']}_{i:02d}.mov")}}
            parts[j["key"]].append(p)
            split.append(p)
    return split, parts


def render(sp, pub, out, only=None, stills_only=False):
    """The clips: each one's common part and its variants' tails, ProRes 4444 with alpha, and check stills. The jobs
    go to out/stage_jobs.json (out/stage_jobs_only.json for a run of some of them, so the whole list stays: Remotion
    previews and checks read it, tools/remotion_ctas.py)."""
    split, parts = render_jobs(sp, out, only, stills_only)
    env = dict(os.environ)
    if Path(SCRATCH.anchor).exists():                 # the renders' temp copies go to the scratch drive (G:)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        env.update(TEMP=str(SCRATCH), TMP=str(SCRATCH))

    def run(js, tag):
        jp = out / f"stage_jobs{tag}.json"
        jp.write_text(json.dumps({"jobs": js}, indent=1), encoding="utf-8")
        r = subprocess.run(["node", "scripts/stage.mjs", str(jp), str(pub)], cwd=REMOTION, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=env)
        got = [json.loads(x) for x in r.stdout.splitlines() if x.startswith("{")]
        return got, ([{"key": "node", "error": r.stderr[-2000:]}] if r.returncode else [])

    res, err = run(split, "_only" if only else "")
    done = {x["key"] for x in res if x.get("ok")}
    again = [j for j in split if j["key"] not in done]   # failed, or no answer at all (node stopped mid-run)
    if again:                                         # once more, in fresh tabs
        res2, err2 = run(again, "_retry")
        err += err2
        res = [x for x in res if x.get("ok")] + res2
        got = {x["key"] for x in res}
        res += [{"key": j["key"], "ok": False, "error": "no result from the renderer"} for j in again
                if j["key"] not in got]
    for key, ps in parts.items():                     # join a clip's parts once every part is there
        if all(any(x["key"] == p["key"] and x.get("ok") for x in res) for p in ps):
            lst = out / "clips" / "_parts" / f"{key}.txt"
            lst.write_text("".join(f"file '{Path(p['clip']['out']).as_posix()}'\n" for p in ps), encoding="utf-8")
            dst = out / "clips" / f"{key}.mov"
            j = subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                                "-c", "copy", str(dst)], capture_output=True, text=True)
            if j.returncode:
                res.append({"key": key, "ok": False, "error": f"joining the parts: {j.stderr[-500:]}"})
                continue
            want = ps[-1]["clip"]["b"] - ps[0]["clip"]["a"] + 1
            n = final.video_frames(dst, ps[0]["props"]["fps"])
            res.append({"key": key, "ok": n == want, **({} if n == want else {"error": f"joined {n} frames, not {want}"})})
            if n == want:                             # the parts' disk back (ProRes 4444 with B1: about 2 MB a frame)
                for p in ps:
                    Path(p["clip"]["out"]).unlink(missing_ok=True)
                lst.unlink(missing_ok=True)
    return res, [x for x in res if not x.get("ok")] + err


ALONE_PRE_S = 1.0                # the subscribe animation alone starts this long before its t0 (and runs this long
                                 # past its t1), so a stray pixel outside its span shows (subscribe_alone_check)


def alone_job(sp, out):
    """R243: the stage's subscribe animation rendered alone (its own composition, transparent ProRes), its clock
    shifted so its t0 falls ALONE_PRE_S in: where it draws (check_c7_quick's box for the captions), its text's alpha
    for the checks, and that it draws nothing before t0 or after t1. None for R232's original clip."""
    s = (sp.get("cta") or {}).get("subscribe") or {}
    if "layer" not in s:
        return None
    L, fps, o = s["layer"], sp["fps"], sp["outro"]
    d = round((ALONE_PRE_S - L["t0"]) * fps) / fps           # whole frames, so its frames sit on the stage's (Fable)
    layer = {**L, **{k: L[k] + d for k in ("t0", "bell", "thumb", "t1")}}
    n = round((layer["t1"] + ALONE_PRE_S) * fps)
    return {"key": "subscribe_alone", "id": s["composition"], "stills": [],
            "props": {"durationInFrames": n, "fps": fps, "width": o["width"], "height": o["height"], "layer": layer},
            "clip": {"a": 0, "b": n - 1, "out": str(out / "clips" / "subscribe_alone.mov")}}


def alone_path(sp, out):
    """The subscribe animation alone (alone_job's clip) and the stage time of its first frame, or None. out: the
    folder holding clips/ (a stage review or a final), or the clips folder itself."""
    s = (sp.get("cta") or {}).get("subscribe") or {}
    p = Path(out) / "clips" / "subscribe_alone.mov"
    if not p.exists() and (Path(out) / "subscribe_alone.mov").exists():
        p = Path(out) / "subscribe_alone.mov"
    if "layer" not in s or not p.exists():
        return None
    return p, -round((ALONE_PRE_S - s["layer"]["t0"]) * sp["fps"]) / sp["fps"]     # (alone_job's shift)


def subscribe_alone_check(sp, out):
    """R243: the subscribe animation draws nothing before its t0 or after its t1 (the stage carries it through the
    whole outro, so a stray pixel there would sit over the avatar). Findings."""
    from pipeline.edit import checks
    got = alone_path(sp, out)
    if not got:
        return []
    path, at = got
    L, found, fps = sp["cta"]["subscribe"]["layer"], [], sp["fps"]
    k0 = math.floor((L["t0"] - at) * fps + 1e-6)       # the alone clip's frame t0 falls in (drawn from t0 on)
    k1 = math.floor((L["t1"] - at) * fps + 1e-6) + 1   # its first frame after t1
    for a, b, what in ((0.0, (k0 + 0.5) / fps, "before"),          # through frame k0, the edge frames included
                       ((k1 - 0.5) / fps, media_s(path) - 0.01, "after")):    # (Fable, final_r4)
        m, q = alpha_union(path, a, b, rate=sp["fps"])
        if m.any():
            found.append(checks.finding("stray", "R243", at + a, f"the subscribe animation draws {what} its span "
                                        f"(at {mask_box(m, q)})"))
    return found


def check_stills(out):
    """The rulebook's measured checks (G6 and G7: R179's 7:1 and nothing see-through behind text; R187's alignment) on
    every stage still: each still is its own alpha, and its composite is the still over mid grey (the checkerboard,
    where the clip draws it, is part of the still). One OCR pass for all of them. Findings in out/checks.json."""
    from PIL import Image
    from pipeline.edit import checks
    pairs = []
    for p in sorted((out / "stills").glob("*.png")):
        im = Image.open(p).convert("RGBA")
        flat = Image.new("RGBA", im.size, (128, 128, 128, 255))
        flat.alpha_composite(im)
        comp = out / "stills_flat" / p.name
        comp.parent.mkdir(exist_ok=True)
        flat.convert("RGB").save(comp)
        pairs.append((p, comp))
    ocr = checks.ocr_many([c for _, c in pairs])
    sp = json.loads((out / "stage_plan.json").read_text(encoding="utf-8"))
    exit_f = round(sp["times"].get("intro_exit", 1e9) * sp["fps"])    # the quick design has no exit
    found, skipped = [], []
    for p, comp in pairs:
        words, label = ocr.get(str(comp), []), f"{p.stem}: "
        t = int(p.stem.split("_")[-1]) / sp["fps"]
        if any(a - 1e-6 <= t <= b for a, b in (sp.get("transients") or {}).get(p.stem.split("_")[0], [])):
            skipped.append(p.name)                     # mid-move or mid-fade by design: the visual review sees it
            continue
        alone = (p.stem.startswith("intro_") and not p.stem.startswith("intro_common")
                 and int(p.stem.split("_")[-1]) >= exit_f)   # the avatar alone, dissolving by design (exit C)
        for f in (checks.text_contrast(comp, p, label=label, words=words)
                  + ([] if alone else checks.see_through(p, label=label))
                  + checks.alignment(comp, p, label=label, words=words)):
            found.append({**f, "still": p.name})
    # a word OCR finds inside the avatar's own picture is the avatar's (the GiddyUp Data logo on his shirt, which OCR
    # reads on the Avatar V and IV renders as "09" or "Ut?"): G6 exempts the logo, and nothing of the stage is there
    # (Fable, final_r5). The avatar's alpha through its pose, as rim_scores reads it.
    pub = out.parent / "stage_public"
    if sp.get("design") == "quick" and pub.exists():
        mine = []
        for f in found:
            b, still = f.get("box"), f.get("still", "")
            kind = still.split("_")[0]
            if not b or kind not in ("intro", "outro"):
                continue
            a, _ = avatar_alpha(sp, kind, int(still.rsplit(".", 1)[0].split("_")[-1]) / sp["fps"], pub)
            if a is not None and a[b[1]:b[3], b[0]:b[2]].min() >= 245:     # the word's box wholly on him
                mine.append(f)
        found = [f for f in found if f not in mine]
        avatar_words = [{**f, "exempt": "the avatar's own picture (his shirt's logo): G6 exempts the logo"} for f in mine]
    else:
        avatar_words = []
    found += url_contrast(out) + oval_alone(out, sp) + subscribe_alone_check(sp, out)
    # G6 exempts the subscribe animation's "Thanks for Watching!" (R235): its words' findings are listed apart
    sub = (sp.get("cta") or {}).get("subscribe") or {}
    tb = ctas.TEXT_BOX

    def thanks(f):
        if "layer" not in sub or not f.get("still", "").startswith("outro") or not f.get("box"):
            return False
        t, b = int(f["still"].rsplit(".", 1)[0].split("_")[-1]) / sp["fps"], f["box"]
        return (sub["layer"]["t0"] <= t <= sub["layer"]["t1"] and b[0] < tb[2] and tb[0] < b[2] and b[1] < tb[3]
                and tb[1] < b[3])
    exempt = [{**f, "exempt": "R235: \"Thanks for Watching!\" keeps its own colours (G6)"} for f in found
              if thanks(f)] + avatar_words
    found = [f for f in found if not thanks(f)]
    (out / "checks.json").write_text(json.dumps({"stills": len(pairs), "findings": found, "exempt": exempt,
                                                 "skipped_transient": skipped}, indent=1), encoding="utf-8")
    return len(pairs), found


RIM_DARK_LV = 20                 # a rim pixel this many levels darker than both sides of the edge is a dark outline


def avatar_alpha(sp, kind, t, pub):
    """The avatar's alpha on the stage at clip time t (the clip "intro" or "outro"), carried through its pose from the
    render's own frame (the source frame Remotion shows: trimBefore is whole frames; Fable, r5), and the pose; (None,
    pose) while it moves or fades out (no settled pose)."""
    import cv2
    import numpy as np
    from pipeline.edit import alpha
    fps, W, H = sp["fps"], sp["intro"]["width"], sp["intro"]["height"]
    av = sp[kind]["avatar"]
    frm, to, _ = quick_state(av, t)
    if frm != to or (av.get("exit") and t >= av["exit"]["at"]):
        return None, None
    k, tx, ty = quick_pose(av["quick"], frm, W, H)["avatar"]
    a = alpha.rgba(pub / av["src"], (round(t * fps) + round(av["trimBeforeS"] * fps)) / fps + 1e-3)[..., 3]
    return cv2.warpAffine(a, np.float32([[k, 0, tx], [0, k, ty]]), (W, H), flags=cv2.INTER_LINEAR, borderValue=0), frm


def rim_scores(out, pub):
    """The avatar's edge on the stage's own stills (R207, R244): in each still where the avatar is settled (full frame,
    the left third, the oval), the band where its alpha is partial, carried through the pose from the render's own
    alpha at that moment, and in it the pixels darker by RIM_DARK_LV than both the subject just inside and the stage
    just outside (each carried in from its side): a dark outline that neither side explains (a web-app render's edge
    colour left premultiplied makes one, GOTCHAS). Returns [{still, pose, rim_px, dark_px}], for one round against
    another."""
    import numpy as np
    from PIL import Image
    from pipeline.edit import alpha
    sp = json.loads((out / "stage_plan.json").read_text(encoding="utf-8"))
    fps, W, H = sp["fps"], sp["intro"]["width"], sp["intro"]["height"]
    w = np.array([0.2126, 0.7152, 0.0722], np.float32)
    res = []
    for p in sorted((out / "stills").glob("*.png")):
        kind = p.stem.split("_")[0]
        if kind not in ("intro", "outro"):
            continue
        av, t = sp[kind]["avatar"], int(p.stem.split("_")[-1]) / fps
        a, frm = avatar_alpha(sp, kind, t, pub)
        if a is None:
            continue                                    # mid-move or fading: not a settled pose
        comp = np.asarray(Image.open(p).convert("RGB"), np.float32) @ w
        part = (a > 25) & (a < 230)
        if frm == "box":                                # inside the oval only (its feathered edge isn't the avatar's)
            b = av["quick"]["box"]
            yy, xx = np.mgrid[0:H, 0:W]
            part &= ((xx - b["cx"]) / (b["w"] / 2 - 6)) ** 2 + ((yy - b["cy"]) / (b["h"] / 2 - 6)) ** 2 < 1
        if not part.any():
            continue
        ys, xs = np.nonzero(part)
        y0, y1, x0, x1 = max(0, ys.min() - 12), ys.max() + 13, max(0, xs.min() - 12), xs.max() + 13
        L, A_ = comp[y0:y1, x0:x1], a[y0:y1, x0:x1]
        inside = alpha._extend(L[..., None], A_ >= 245, 10)[..., 0]
        outside = alpha._extend(L[..., None], A_ <= 5, 10)[..., 0]
        pt = part[y0:y1, x0:x1]
        dark = pt & (L < np.minimum(inside, outside) - RIM_DARK_LV)
        res.append({"still": p.name, "pose": frm, "rim_px": int(pt.sum()), "dark_px": int(dark.sum())})
    return res


def oval_alone(out, sp):
    """The quick design's stills where the stage draws the oval and nothing else (the intro once its Part 1 card has
    gone, the outro before its oval grows): every pixel outside the oval's box (plus the feather) is fully
    transparent, so the main body shows untouched around it (a checkerboard left in by the composition's default props
    was the case that prompted this, round 6)."""
    import numpy as np
    from PIL import Image
    from pipeline.edit import checks
    if sp.get("design") != "quick":
        return []
    fps, found = sp["fps"], []
    spans = {"intro": (sp["intro"]["chapter"]["until"] + 0.05, sp["intro"]["durationInFrames"] / fps),
             "outro": (0.0, sp["times"]["outro_grow"])}
    for p in sorted((out / "stills").glob("*.png")):
        kind, t = p.stem.split("_")[0], int(p.stem.split("_")[-1]) / fps
        a, b = spans[kind]
        if not a <= t < b:
            continue
        bx = sp[kind]["avatar"]["quick"]["box"]
        al = np.asarray(Image.open(p).convert("RGBA"))[..., 3].copy()
        x0, y0 = int(bx["cx"] - bx["w"] / 2 - 4), int(bx["cy"] - bx["h"] / 2 - 4)
        al[max(0, y0):y0 + int(bx["h"]) + 9, max(0, x0):x0 + int(bx["w"]) + 9] = 0
        if al.max() > 0:
            ys, xs = np.nonzero(al)
            found.append(checks.finding("stray", "R232", t, f"{p.stem}: {len(xs)} px drawn outside the oval while it is "
                                        f"alone (around x {int(np.median(xs))}, y {int(np.median(ys))})", still=p.name))
    return found


def url_contrast(out):
    """G6 for what OCR can't read: url.mov's handwriting, measured by its pixels, in each outro still where the
    writing is complete and not yet fading. On the cream panel (round 4): the strokes (pixels in the url box clearly
    darker than the panel), their median against the panel (the visual review measured 4.4:1 before the write-on was
    darkened). With no panel (R212, R228: the strokes cream over B1): in each eighth of the box across, the strokes
    (pixels within 24 of cream) against the median of everything else there, the worst eighth reported, since B1's
    lights sit behind the right end."""
    import numpy as np
    from PIL import Image
    from pipeline.edit import checks
    sp = json.loads((out / "stage_plan.json").read_text(encoding="utf-8"))
    if "outro" not in sp or sp.get("design") == "quick":   # quick: the url is David's footage in Premiere, exempt (G6)
        return []
    fps, Y = sp["fps"], np.array([0.2126, 0.7152, 0.0722], np.float32)
    cream = np.array(CREAM, np.float32)
    found = []
    for p in sorted((out / "stills").glob("outro_*.png")):
        key, t = p.stem.split("_")[1], int(p.stem.split("_")[-1]) / fps
        u = (sp["outro_tails"].get(key) or sp["outro"])["url"]
        if not u["t0"] + 3.0 <= t <= u["t1"] - u["fadeOutS"] - 0.1:      # written out, not yet fading
            continue
        x, y, w, h = (u["box"][k] for k in ("x", "y", "w", "h"))
        px = np.asarray(Image.open(p).convert("RGB"), np.float32)[y:y + h, x:x + w]
        if u.get("panel", True):
            flat = px.reshape(-1, 3)
            ink = flat[flat @ Y < 0.8 * float(cream @ Y)]
            if len(ink) < 200:
                continue
            r, what = checks.ratio(ink[np.argsort(ink @ Y)[len(ink) // 2]], cream), "(median) against its panel"
        else:
            near = (np.abs(px - cream) <= 24).all(axis=2)
            rs = []
            for i in range(8):
                a, b = w * i // 8, w * (i + 1) // 8
                ink, ground = px[:, a:b][near[:, a:b]], px[:, a:b][~near[:, a:b]]
                if len(ink) >= 50 and len(ground) >= 50:
                    rs.append(checks.ratio(np.median(ink, axis=0), np.median(ground, axis=0)))
            if not rs:
                continue
            r, what = min(rs), f"(worst eighth of {len(rs)}) against B1 behind it"
        if r < checks.MIN_RATIO:
            found.append(checks.finding("contrast", "R179", t, f"{p.stem}: the url write-on's strokes are {r:.2f}:1 "
                                        f"{what}, under 7:1", ratio=round(r, 2), still=p.name))
    return found


def video_clip(track, ids, files, name, start, path, n, fps, W, H):
    c = pr.clipitem(track, ids, name, start, start + n, 0, n, n, fps, alpha="straight")
    files.el(c, path, frames=n, w=W, h=H)
    return c


def place_sounds(seq, ids, files, events, offset_s, sounds, fps):
    """R158: the stage's sound cues on "Stage sounds" tracks (a new lane where two would overlap), each a mono clip
    (the made-in-code sounds at the approved sequence's level) with final.PREMIERE_MONO_DB, as the voice gets."""
    lanes = []
    for t, kind in sorted(events):
        path = sounds[kind]
        n = pr.probe_frames(path, fps, whole=True) or 1
        a = round((offset_s + t) * fps)
        lane = next((ln for ln in lanes if ln["end"] <= a), None)
        if lane is None:
            lane = {"end": 0, "tr": seq.track("audio", "Stage sounds" + (f" {len(lanes) + 1}" if lanes else ""))}
            lanes.append(lane)
        audio_clip(lane["tr"], ids, files, f"{kind}", a, path, fps, final.PREMIERE_MONO_DB)
        lane["end"] = a + n


def review_xml(sp, out, run, logo, gains, voices, clips=None, sounds=None):
    """One short sequence per variant: V1 left empty where the approved sequence goes (aidvStageReview nests it), the
    stage on V2, the voice on A3, the logo outro after the outro. Returns the XML and the jobs' placements."""
    fps, W, H = sp["fps"], sp["intro"]["width"], sp["intro"]["height"]
    root = ET.Element("xmeml", version="4")
    ids, files = pr.Ids(), pr.Files(fps)
    nf = lambda p: final.video_frames(p, fps)
    seqs, places = [], []
    names = {"slide": "slides aside", "corner": "shrinks to a corner", "dissolve": "dissolves",
             "red": "YouTube red", "brand": "brand colours"}
    box = "box" in sp["intro"]["avatar"]                   # round 5's box design
    spot = {"br": "bottom right", "bl": "bottom left", "tr": "top right", "tl": "top left"}
    endings = {"oval": "Outro 1: ends in the oval", "full": "Outro 2: grows back to full frame for the last line"}
    clips = clips or out / "clips"
    common_i, common_o = clips / "intro_common.mov", clips / "outro_common.mov"
    for k, letter in zip(sp["intro_tails"], "ABC"):
        name = (f"Intro {letter}: the avatar {names[k]}" if not box else
                "Intro: full frame, then the oval" + (f" ({letter})" if len(sp["intro_tails"]) > 1 else ""))
        n_c, n_t = nf(common_i), nf(clips / f"intro_{k}.mov")
        nest_n = round(INTRO_NEST_S * fps)
        total = max(n_c + n_t, sp["nest_at"] + nest_n)
        s = pr.Seq(name, f"sequence-intro-{k}", fps, W, H, total)
        v1, v2 = s.track("video", "Approved sequence"), s.track("video", "Avatar stage")
        s.track("video", titles.TRACK)                     # the captions, above the avatar (stage_titles)
        a1, a2, a3 = (s.track("audio", "Approved sequence"), s.track("audio", "Logo outro right"),
                      s.track("audio", "Avatar voice"))
        video_clip(v2, ids, files, "stage intro", 0, common_i, n_c, fps, W, H)
        video_clip(v2, ids, files, f"stage intro {k}", n_c, clips / f"intro_{k}.mov", n_t, fps, W, H)
        audio_clip(a3, ids, files, "avatar voice", 0, voices["opening"], fps, gains["opening"])
        if sounds:
            place_sounds(s, ids, files, sp["intro_sounds"], 0.0, sounds, fps)
        pr.close_tracks(s)
        root.append(s.el)
        T = sp["times"]
        first = ([{"t": 0.0, "name": "Stage check", "comment": "Full frame on your stage background (B1, the white "
                   "neon sign upper left); captions bottom centre."},
                  {"t": T["intro_move"], "name": "Stage check", "comment": "Before \"So\": the frame shrinks in 0.6 s "
                   f"(linear) into the oval at the {spot[sp['intro']['avatar']['box']['spot']]}, the teal fading in "
                   "behind you; the roadmap card slides in on \"So\", each row on its word."}] if box else
                 [{"t": T["intro_move"], "name": "Stage check", "comment": "The avatar moves to the left third as the "
                   "roadmap card slides in (R208); each row lands on its word (R80)."}])
        places.append({"name": name, "kind": "intro", "variant": k, "stage_at": 0, "frames": total,
                       "at_frame": sp["nest_at"],
                       "in_frame": 0, "out_frame": nest_n, "markers": first + [
            {"t": T["intro_expand"], "name": "Stage check", "comment": "\"So, let's get started.\": the card grows to "
             "the full frame and becomes the Part 1 card."},
            {"t": sp["nest_at"] / fps, "name": "Stage check", "comment": "Your approved sequence starts here, under the "
             "stage; the avatar speaks its first sentence (R205)."},
            {"t": T["intro_exit"], "name": "Stage check", "comment": f"The {'oval' if box else 'avatar'} {names[k]} "
             "at the sentence's end, with the Part 1 card's fade."}]})
    for k, num in zip(sp["outro_tails"], "12"):
        name = endings[k] if box else f"Outro {num}: the subscribe card in {names[k]}"
        n_c, n_t = nf(common_o), nf(clips / f"outro_{k}.mov")
        nest_n = round(OUTRO_NEST_S * fps)
        at = nest_n - round(OUTRO_FADE_S * fps)            # the stage fades in over the approved sequence's last 0.8 s
        lg = nf(logo)
        total = at + n_c + n_t + lg
        s = pr.Seq(name, f"sequence-outro-{k}", fps, W, H, total)
        v1, v2 = s.track("video", "Approved sequence and logo"), s.track("video", "Avatar stage")
        s.track("video", titles.TRACK)
        a1, a2, a3 = (s.track("audio", "Approved sequence and logo"), s.track("audio", "Logo outro right"),
                      s.track("audio", "Avatar voice"))
        video_clip(v2, ids, files, "stage outro", at, common_o, n_c, fps, W, H)
        video_clip(v2, ids, files, f"stage outro {k}", at + n_c, clips / f"outro_{k}.mov", n_t, fps, W, H)
        t3 = at + n_c + n_t
        final.media_clip(v1, ids, files, "logo outro", t3, t3 + lg, 0, lg, logo, lg, fps, W, H, True)
        final.media_clip(a1, ids, files, "logo outro", t3, t3 + lg, 0, lg, logo, lg, fps, W, H, False, pan=-1)
        final.media_clip(a2, ids, files, "logo outro right", t3, t3 + lg, 0, lg, logo, lg, fps, W, H, False,
                         channel=2, pan=1)
        audio_clip(a3, ids, files, "avatar voice", at, voices["recap"], fps, gains["recap"])
        if sounds:
            place_sounds(s, ids, files, sp["outro_sounds"], at / fps, sounds, fps)
        pr.close_tracks(s)
        root.append(s.el)
        T, a = sp["times"], at / fps
        places.append({"name": name, "kind": "outro", "variant": k, "stage_at": at, "frames": t3, "at_frame": 0,
                       "in_frame": None,
                       "out_frame": None, "nest_tail": nest_n, "v1_clips": 1,
                       "markers": [
            {"t": a, "name": "Stage check", "comment": "The outro fades in over your approved sequence's last 0.8 s."},
            {"t": a + T["outro_card"], "name": "Stage check", "comment": "\"Let's recap.\": the recap card; each row "
             "ticks on its word."},
            {"t": a + T["outro_subscribe"], "name": "Stage check", "comment": "The subscribe card in "
             f"{names[sp['outro_tails'][k]['subscribe']['look']]}."},
            *([{"t": a + T["outro_grow"], "name": "Stage check", "comment": "Before \"Visit\": the oval grows back to "
                "full frame in 0.6 s, the teal giving way to your stage background."}] if box and k == "full" else []),
            {"t": a + T["outro_url"], "name": "Stage check", "comment": "Your url.mov write-on on \"Visit\"" +
             (", cream, with no panel." if box else ".")},
            {"t": t3 / fps, "name": "Stage check", "comment": "Hard cut to the logo outro."}]})
    ET.indent(root, "\t")
    xml = out / f"{run}_stage_review.xml"
    xml.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode")
                   + "\n", encoding="utf-8")
    return xml, places


def caption_group(ws, display, at, pl):
    """The planner's cues for these words (pipeline.edit.plan.captions, at seconds on the sequence, pl its limits); a
    last cue of one word (the outro's "virtually.", left alone by the split at a move) is avoided by breaking the last
    two cues' words at the comma nearest their middle."""
    from pipeline.edit.plan import captions
    part = captions(ws, display, at, pl)
    if len(part) >= 2 and len(part[-1]["text"].split()) == 1:
        k0 = next(i for i, w in enumerate(ws) if round(at + w["start"], 3) >= part[-2]["start"] - 1e-6)
        tail = ws[k0:]
        commas = [i for i, w in enumerate(tail[:-1]) if display[w["char"][1]:w["char"][1] + 1] == ","]
        if commas:
            m = min(commas, key=lambda i: abs(i + 1 - len(tail) / 2)) + 1
            a_, b_ = captions(tail[:m], display, at, pl), captions(tail[m:], display, at, pl)
            a_[-1]["end"] = min(a_[-1]["end"], b_[0]["start"])
            part = part[:-2] + a_ + b_
    return part


def phrase_cues(ws, display, at, lim):
    """Cues for these timed words (as plan.captions makes them: start at a cue's first word, end at the next cue's
    first word, the last lingering linger_s) broken at phrases, as David's own Quick Series captions are: the words
    are cut after every comma, colon, semicolon and sentence end; a phrase longer than a cue (max_chars x max_lines) is
    split into the fewest near-even parts at word boundaries; then phrases join while they fit a cue, never across a
    sentence end once the cue holds min_chars_to_break. Each cue's text wrapped to the spot's width and lines."""
    from pipeline.edit.plan import _balanced, _end_char, _wrap
    cap = lim["max_chars"] * lim["max_lines"]
    text_of = lambda g: display[g[0]["char"][0]:_end_char(display, g[-1]["char"][1])].strip()
    # the punctuation after a group's last word, closing quotes and brackets included (",\"" ends a phrase too)
    stop = lambda g: display[g[-1]["char"][1]:_end_char(display, g[-1]["char"][1])]
    phrases, cur = [], []
    for w in ws:
        cur.append(w)
        if any(ch in ",;:.?!" for ch in stop([w])):
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)
    parts = []
    for ph in phrases:
        n = math.ceil(len(text_of(ph)) / cap)
        lines = _balanced([w["word"] for w in ph], n) if n > 1 else None
        if not lines:
            parts.append(ph)
            continue
        cuts, k = [], 0
        for line in lines[:-1]:                         # the balanced lines' word counts, mapped back to the words
            k += len(line.split(" "))
            cuts.append(k)
        for i, c in enumerate(cuts):                    # a part never ends on a small word ("...to see the"): it takes
            lo = cuts[i - 1] if i else 0                # the words that complete it ("...to see the courses") where
            hi = cuts[i + 1] if i + 1 < len(cuts) else len(ph)    # they fit a cue, else gives the small word away
            f = c
            while f < hi - 1 and norm(ph[f - 1]["word"]) in SMALL_WORDS and len(text_of(ph[lo:f + 1])) <= cap:
                f += 1
            if norm(ph[f - 1]["word"]) not in SMALL_WORDS:
                cuts[i] = f
                continue
            while c - 1 > lo and norm(ph[c - 1]["word"]) in SMALL_WORDS and len(text_of(ph[c - 1:hi])) <= cap:
                c -= 1
            cuts[i] = c
        for a_, b_ in zip([0] + cuts, cuts + [len(ph)]):
            parts.append(ph[a_:b_])
    groups = []
    for p_ in parts:
        g = groups[-1] if groups else None
        if (g and len(text_of(g + p_)) <= cap
                and not (any(ch in ".?!" for ch in stop(g)) and len(text_of(g)) >= lim["min_chars_to_break"])):
            groups[-1] = g + p_
        else:
            groups.append(p_)
    out = []
    for i, g in enumerate(groups):
        t1 = at + (groups[i + 1][0]["start"] if i + 1 < len(groups) else g[-1]["end"] + lim["linger_s"])
        out.append({"start": round(at + g[0]["start"], 3), "end": round(t1, 3),
                    "text": _wrap(text_of(g), lim["max_chars"], lim["max_lines"])})
    return out


def stage_titles(place, sp, plan, run_dir, approved_dir, out):
    """R102, R126: a review sequence's caption titles, as the final has them: the avatar's own line, cue by cue (the
    planner's captions of its words, merged as pipeline.edit.ppro.final merges them), and, in an intro, a copy of each
    of the approved sequence's caption titles that starts while the avatar is still on screen: the same .mogrt at the
    same frames, on the Caption titles track above the avatar, which would otherwise cover part of it (the nested
    sequence's own captions sit under the stage). Returns the job aidvCaptionTitles reads."""
    fps, W, H = sp["fps"], sp["intro"]["width"], sp["intro"]["height"]
    pl = plan["settings"]["captions"]
    g = sp["intro_render"] if place["kind"] == "intro" else sp["outro_render"]
    trim = sp["intro_trim_s"] if place["kind"] == "intro" else PAD_S - RECAP_HEAD_S
    meta = timing.of(g)                                        # R227: the line's own word times
    at = place["stage_at"] / fps + g["voice_at_s"] - trim
    # The box design: no caption is up while the box shrinks or grows (C7, R213: the visual review of round 5 found
    # one across each move). The words are captioned in groups split at each move, which falls in a pause; the cue
    # before a move ends as the move starts.
    av = sp[f"{place['kind']}_tails"][place["variant"]]["avatar"]
    cuts = sorted(place["stage_at"] / fps + m["at"] for m in av["moves"]) if "box" in av else []
    url = sp[f"{place['kind']}_tails"][place["variant"]].get("url")
    if "box" in av and url:                            # and the call to action's caption starts with "Visit", as the
        cuts = sorted(cuts + [place["stage_at"] / fps + url["t0"] - 0.01])     # write-on does (not mid-cue)
    groups, rest = [], list(meta["words"])
    for t in cuts:
        cut = [w["word"] for w in rest if at + w["start"] < t < at + w["end"]]
        if cut:                                        # a move or the write-on falls in a pause, never mid-word
            raise SystemExit(f"{place['name']}: a caption split at {t:.2f} s falls inside \"{cut[0]}\"")
        k = next((i for i, w in enumerate(rest) if at + w["start"] >= t), len(rest))
        groups.append((rest[:k], t))
        rest = rest[k:]
    groups.append((rest, None))
    display = meta["display_text"]
    cues = []
    for ws, t in groups:
        part = caption_group(ws, display, at, pl) if ws else []
        if part and t is not None:
            part[-1]["end"] = round(min(part[-1]["end"], t), 3)
        cues += part
    cues = final.merge_orphans(cues)
    tag = re.sub(r"[^A-Za-z0-9]+", "_", place["name"].split(":")[0]).strip("_")
    made = titles.build(out / "titles" / tag, cues, lambda c, bw, bh: pr.caption_place(c, pl, W, H, bw, bh), W, H,
                        fps, place["name"], place["frames"], size_px=pl["titles"].get("size_px", titles.SIZE_PX),
                        box_hex=pl["titles"].get("box_color"))
    job = json.loads((out / "titles" / tag / "caption_titles.json").read_text(encoding="utf-8"))
    if place["kind"] == "intro":
        gone = round(sp["times"]["intro_exit"] * fps) + round(0.7 * fps)       # the avatar is off the screen by then
        nest = json.loads((approved_dir / "caption_titles.json").read_text(encoding="utf-8"))["cues"]
        for c in nest:
            a = c["start_frame"] + place["at_frame"] - place["in_frame"]
            if a < gone and c["start_frame"] >= place["in_frame"]:
                job["cues"].append({**c, "start_frame": a, "end_frame": c["end_frame"] + place["at_frame"]
                                    - place["in_frame"], "copied_from": "the approved sequence"})
    job["cues"].sort(key=lambda c: c["start_frame"])
    for x, y in zip(job["cues"], job["cues"][1:]):
        if x["end_frame"] > y["start_frame"]:
            raise SystemExit(f"{place['name']}: caption {x['text']!r} overlaps the next ({y['text']!r})")
    return job


def box_state(avatar, t):
    """The box design's p at clip time t, as AvatarStage's BoxAvatar computes it: 0 full frame, 1 in the oval."""
    p = 1.0 if avatar["start"] == "box" else 0.0
    for m in avatar["moves"]:
        u = min(1.0, max(0.0, (t - m["at"]) / m["dur"])) if m["dur"] > 0 else float(t >= m["at"])
        p += ((1.0 if m["to"] == "box" else 0.0) - p) * u
    return p


def check_c7(places, sp):
    """VIDEO_RULES C7 and R213, measured on a box design's review sequences: while the avatar sits in the oval, no
    caption title's box comes near it (pipeline.edit.pip.touches, CLEAR_PX); while it is full frame, every caption
    starting then sits bottom centre; while it shrinks or grows, no caption is up. Every frame of each cue. Returns
    findings."""
    from pipeline.edit import pip
    fps, W, H = sp["fps"], sp["intro"]["width"], sp["intro"]["height"]
    out = []
    for pl in places:
        key = "intro" if pl["kind"] == "intro" else "outro"
        av = sp[f"{key}_tails"][pl["variant"]]["avatar"]
        if "box" not in av:
            continue
        centre = (av["box"]["cx"], av["box"]["cy"])
        gone = av["exit"]["at"] + av["exit"]["dur"] if av.get("exit") else 1e9
        for c in pl["titles"]["cues"]:
            x, y, w, h = c["box"]
            f = c["start_frame"]
            while f < c["end_frame"]:
                t = (f - pl["stage_at"]) / fps
                if 0 <= t < gone:
                    p = box_state(av, t)
                    if p >= 1.0 and pip.touches(centre, (x, y, x + w, y + h)):
                        out.append({"sequence": pl["name"], "t": round(f / fps, 2), "what": f"the caption "
                                    f"\"{c['text'][:40]}\" comes within {pip.CLEAR_PX} px of the oval"})
                        break
                    if p < 1.0 and f == c["start_frame"] and not (abs(x + w / 2 - W / 2) < 40 and y > 0.76 * H):
                        out.append({"sequence": pl["name"], "t": round(f / fps, 2), "what": f"the caption "
                                    f"\"{c['text'][:40]}\" isn't bottom centre while the avatar is full frame"})
                        break
                    if 0.05 < p < 0.95:                # the box shrinking or growing sweeps over the caption band
                        # (a cue may come or go on a move's first or last frame: its words end or start the move)
                        out.append({"sequence": pl["name"], "t": round(f / fps, 2), "what": f"the caption "
                                    f"\"{c['text'][:40]}\" is up while the box moves"})
                        break
                f += 1                                 # every frame: a 0.6 s move is 18 frames
    return out


def stage_titles_quick(place, sp, plan, approved_dir, out, qs):
    """R102, R126 and the caption rules for the Quick Series design (R213, C3, C7): the avatar's own line, cue by cue,
    split at every move (no caption is up while he moves) and at "Visit" (the url's caption starts with it), each group
    placed for the pose it plays in: full frame, bottom centre over the shirt (R213); in the left third, under the card
    in the right two thirds, wrapped to the planner's off-centre width (C3's house default); the call to action, middle
    left as QuickArch03 has it, wrapped to qs cta_caption_chars so it keeps clear of the face (C3: the subscribe
    animation and the url hold the bottom of the frame). In an intro, a copy of each approved caption title that starts
    while the stage clip is up (its Part 1 card would cover the nested sequence's own). Returns aidvCaptionTitles' job,
    each cue with its "spot"."""
    fps, W, H = sp["fps"], sp["intro"]["width"], sp["intro"]["height"]
    pl = plan["settings"]["captions"]
    kind = place["kind"]
    g = sp[f"{kind}_render"]
    trim = sp["intro_trim_s"] if kind == "intro" else PAD_S - RECAP_HEAD_S
    meta = timing.of(g)
    a0 = place["stage_at"] / fps
    at = a0 + g["voice_at_s"] - trim
    av, T = sp[kind]["avatar"], sp["times"]
    cuts = sorted({a0 + m["at"] for m in av["moves"]} | ({a0 + T["outro_visit"] - 0.01} if kind == "outro" else set()))
    groups, rest = [], list(meta["words"])
    for t in cuts:
        cut = [w["word"] for w in rest if at + w["start"] < t < at + w["end"]]
        if cut:
            raise SystemExit(f"{place['name']}: a caption split at {t:.2f} s falls inside \"{cut[0]}\"")
        k = next((i for i, w in enumerate(rest) if at + w["start"] >= t), len(rest))
        groups.append((rest[:k], t))
        rest = rest[k:]
    groups.append((rest, None))
    display = meta["display_text"]
    cta_from = T["outro_full"] + qs["cta_move_s"] if kind == "outro" else float("inf")
    limits = {"bottom": pl, "right": {**pl, "max_chars": pl["off_centre_max_chars"],
                                      "max_lines": pl["off_centre_max_lines"]},
              "cta": {**pl, "max_chars": qs["cta_caption_chars"], "max_lines": 3}}
    cues = []
    for ws, t in groups:
        if not ws:
            continue
        tc_ = at + ws[0]["start"] - a0                        # the group's first word, on the clip
        frm, to, p = quick_state(av, tc_)
        if frm != to:
            raise SystemExit(f"{place['name']}: the words from \"{ws[0]['word']}\" start while the avatar moves")
        spot = "cta" if tc_ >= cta_from - 1e-6 else ("right" if frm == "left" else "bottom")
        part = phrase_cues(ws, display, at, limits[spot])     # broken at phrases, wrapped to the spot (C3)
        if part and t is not None:
            part[-1]["end"] = round(min(part[-1]["end"], t), 3)
        for c in part:
            c["spot"] = spot
        cues += part
    merged, k = [], 0                                         # a one-word cue joins the one before (final's
    while k < len(cues):                                      # merge_orphans), within its spot and at its width
        j = k
        while j < len(cues) and cues[j]["spot"] == cues[k]["spot"]:
            j += 1
        merged += final.merge_orphans(cues[k:j], width=limits[cues[k]["spot"]]["max_chars"])
        k = j
    cues = merged

    def place_at(c, bw, bh):
        if c["spot"] == "right":                              # centred under the card, on the caption row
            return CARD_BOX["x"] + CARD_BOX["w"] / 2 - bw / 2, H - pl["margin_bottom_px"] - bh
        if c["spot"] == "cta":                                # Premiere's middle-left spot (the planner's margin)
            return qs["cta_caption_x"], H / 2 - bh / 2
        return pr.caption_place(c, pl, W, H, bw, bh)

    tag = place.get("titles_tag") or re.sub(r"[^A-Za-z0-9]+", "_", place["name"].split(":")[0]).strip("_")
    titles.build(out / "titles" / tag, cues, place_at, W, H, fps, place["name"], place["frames"],
                 size_px=pl["titles"].get("size_px", titles.SIZE_PX), box_hex=pl["titles"].get("box_color"))
    job = json.loads((out / "titles" / tag / "caption_titles.json").read_text(encoding="utf-8"))
    for jc in job["cues"]:
        jc["spot"] = next(c["spot"] for c in cues if c["text"] == jc["text"] and round(c["start"] * fps) == jc[
            "start_frame"])
    if kind == "intro":
        # copies only while the stage's cards cover the nest (the Part 1 card, to chapter.until): after that the
        # stage draws the oval alone, which keeps off captions, and an intro clip carrying the box's first stay would
        # otherwise duplicate 14 s of David's editable titles (Fable, final_r5)
        gone = place["stage_at"] + min(sp["intro"]["durationInFrames"], round(sp["intro"]["chapter"]["until"] * fps))
        for c in json.loads((approved_dir / "caption_titles.json").read_text(encoding="utf-8"))["cues"]:
            a = c["start_frame"] + place["at_frame"] - place["in_frame"]
            if a < gone and c["start_frame"] >= place["in_frame"]:
                job["cues"].append({**c, "start_frame": a, "end_frame": c["end_frame"] + place["at_frame"]
                                    - place["in_frame"], "copied_from": "the approved sequence", "spot": "bottom"})
    job["cues"].sort(key=lambda c: c["start_frame"])
    for x, y in zip(job["cues"], job["cues"][1:]):
        if x["end_frame"] > y["start_frame"]:
            raise SystemExit(f"{place['name']}: caption {x['text']!r} overlaps the next ({y['text']!r})")
    return job


def cta_boxes(sp, W, H, out=None):
    """Where the call to action draws on the frame: the subscribe animation's union over its length (R232's original
    clip is frame-sized, default Motion; R243's Remotion animation from its render alone, alone_job, in out/clips) and
    url.mov's writing at its widest under its Motion (position, scale; anchor at its centre, as Premiere's). Each (x0,
    y0, x1, y1)."""
    s, u = sp["cta"]["subscribe"], sp["cta"]["url"]
    if "file" in s:
        m, q = alpha_union(Path(s["file"]), 0.0, s["s"])
    else:
        got = alone_path(sp, out) if out else None
        if not got:
            raise SystemExit("the subscribe animation alone (clips/subscribe_alone.mov) isn't rendered: render the "
                             "stage first (its subscribe_alone job)")
        m, q = alpha_union(got[0], 0.0, media_s(got[0]))
    ub, uw, uh = url_box(Path(u["file"]))
    k = u["motion"]["scale"] / 100
    cx, cy = u["motion"]["position"][0] * W, u["motion"]["position"][1] * H
    return {"subscribe": mask_box(m, q),
            "url": (cx + (ub["x"] - uw / 2) * k, cy + (ub["y"] - uh / 2) * k, cx + (ub["x"] + ub["w"] - uw / 2) * k,
                    cy + (ub["y"] + ub["h"] - uh / 2) * k)}


def check_c7_quick(places, sp, pub, folder=None):
    """VIDEO_RULES C7 (R213), C2/G13 and R232 measured on the Quick Series design's review sequences, every third
    frame of each cue on the stage clip: no caption up while the avatar moves; in the oval, none within CLEAR_PX of it
    (pipeline.edit.pip.touches); in the left third, none within CLEAR_PX of the avatar's reach (its alpha over that
    stretch, through the pose) and the avatar's reach clear of the card; full frame, bottom centre over the shirt
    (R213), or in the call to action middle left clear of his reach; none on David's call-to-action footage while it
    plays. Returns findings and the measures."""
    from pipeline.edit import pip
    fps, W, H = sp["fps"], sp["intro"]["width"], sp["intro"]["height"]
    out, reach = [], {}
    cta = cta_boxes(sp, W, H, folder)
    grow = lambda b, d: (b[0] - d, b[1] - d, b[2] + d, b[3] + d)
    ser = sp["intro"].get("series")                     # R243: the series card, while it draws anything
    ser_box = (ser["box"]["x"], ser["box"]["y"], ser["box"]["x"] + ser["box"]["w"],
               ser["box"]["y"] + ser["box"]["h"]) if ser else None
    overlap = lambda a, b: a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    def stretch(av, t):
        """The settled stretch around clip time t: (start, end) between moves."""
        ends = sorted([0.0] + [m["at"] + m["dur"] for m in av["moves"] if m["at"] + m["dur"] <= t + 1e-6])
        starts = sorted([m["at"] for m in av["moves"] if m["at"] > t] + [float("inf")])
        return ends[-1], starts[0]

    def union(kind, a, b):
        av = sp[kind]["avatar"]
        key = (kind, round(a, 3), round(b, 3))
        if key not in reach:
            reach[key] = alpha_union(pub / av["src"], a + av["trimBeforeS"], min(b, sp[kind]["durationInFrames"] / fps)
                                     + av["trimBeforeS"])
        return reach[key]

    measured = {"cta_boxes": {k: [round(v) for v in b] for k, b in cta.items()}}
    for kind in ("intro", "outro"):                    # the avatar beside the card, never on it
        av, qk = sp[kind]["avatar"], sp[kind]["avatar"]["quick"]
        for m in av["moves"]:
            if m["to"] != "left":
                continue
            a, b = m["at"] + m["dur"], stretch(av, m["at"] + m["dur"] + 0.01)[1]
            mask, q = union(kind, a, b)
            pose = quick_pose(qk, "left", W, H)["avatar"]
            card = grow((CARD_BOX["x"], CARD_BOX["y"], CARD_BOX["x"] + CARD_BOX["w"], CARD_BOX["y"] + CARD_BOX["h"]),
                        CLEAR_PX)
            bx = mask_box(mask, q)
            right = pose[0] * bx[2] + pose[1]
            measured[f"{kind}_left_reach_right_px"] = round(right, 1)
            if mask_hits(mask, q, to_src(pose, card)):
                out.append({"sequence": kind, "t": round(a, 2), "what": f"in the left third the avatar comes within "
                            f"{CLEAR_PX} px of the card (his reach ends at x {right:.0f})"})
    for pl_ in places:
        kind = pl_["kind"]
        clip, av = sp[kind], sp[kind]["avatar"]
        qk, a0, n = av["quick"], pl_["stage_at"] / fps, clip["durationInFrames"] / fps
        centre = (qk["box"]["cx"], qk["box"]["cy"])
        for c in pl_["titles"]["cues"]:
            x, y, w, h = c["box"]
            cb = (x, y, x + w, y + h)
            t0, t1 = c["start_frame"] / fps - a0, c["end_frame"] / fps - a0
            say = lambda what: out.append({"sequence": pl_["name"], "t": round(c["start_frame"] / fps, 2),
                                           "what": f"the caption \"{c['text'][:40]}\" {what}"})
            if kind == "outro":                        # David's footage while it plays (C6 keeps captions on top;
                sub_ = sp["cta"]["subscribe"]          # they mustn't sit on it)
                for key, k0, k1 in (("subscribe", sub_["t0"], sub_["t0"] + sub_["s"]),   # (its span: any version)
                                    ("url", sp["cta"]["url"]["t0"], sp["cta"]["url"]["t1"])):
                    if t0 < k1 and k0 < t1 and overlap(grow(cb, CLEAR_PX), cta[key]):
                        say(f"sits on the {key} footage")
            if kind == "intro" and ser_box:            # the series card's box: no caption within CLEAR_PX of it
                k0, k1 = ctas.series_shown(ser)
                if t0 < k1 and k0 < t1 and overlap(grow(cb, CLEAR_PX), ser_box):
                    say(f"comes within {CLEAR_PX} px of the series card")
            card = (CARD_BOX["x"], CARD_BOX["y"], CARD_BOX["x"] + CARD_BOX["w"], CARD_BOX["y"] + CARD_BOX["h"])
            if c.get("spot") == "right" and overlap(grow(cb, CLEAR_PX), card):   # under the card, clear of it
                say(f"comes within {CLEAR_PX} px of the card")
            if t1 <= 0 or t0 >= n:
                continue
            for m in av["moves"]:                      # a cue may end or start on a move's first or last frame
                if t0 < m["at"] + m["dur"] - 1.5 / fps and t1 > m["at"] + 1.5 / fps:
                    say(f"is up while the avatar moves to {m['to']}")
                    break
            done = set()
            for f in range(c["start_frame"], c["end_frame"], 3):
                t = f / fps - a0
                if not 0 <= t < n:
                    continue
                frm, to, p = quick_state(av, t)
                if frm != to or frm in done:
                    continue
                done.add(frm)
                if frm == "box":
                    if pip.touches(centre, cb):
                        say(f"comes within {pip.CLEAR_PX} px of the oval")
                elif frm == "left" or c.get("spot") == "cta":
                    a, b = stretch(av, t)
                    mask, q = union(kind, max(a, t0), min(b, t1))
                    if mask_hits(mask, q, to_src(quick_pose(qk, frm, W, H)["avatar"], grow(cb, CLEAR_PX))):
                        say(f"comes within {CLEAR_PX} px of the avatar ({'left third' if frm == 'left' else 'full'})")
                elif not (abs(x + w / 2 - W / 2) < 40 and y > 0.76 * H):
                    say("isn't bottom centre while the avatar is full frame")
    return out, measured


def check_outro_still(places, sp, approved_dir):
    """VIDEO_RULES C7 for R235's oval over the main body's end: no caption title of the approved sequence (they play
    under the stage, inside the nest) comes within pip.CLEAR_PX of the oval from the still's first frame to the
    growth's start. Returns findings."""
    from pipeline.edit import pip
    ost, fps = sp.get("outro_still"), sp["fps"]
    if not ost:
        return []
    pl = next(p for p in places if p["kind"] == "outro")
    qk = sp["outro"]["avatar"]["quick"]["box"]
    a0 = pl["stage_at"] + round(ost["t0"] * fps)            # the outro sequence's frames
    a1 = pl["stage_at"] + round(sp["times"]["outro_grow"] * fps)
    out = []
    for c in json.loads((approved_dir / "caption_titles.json").read_text(encoding="utf-8"))["cues"]:
        s, e = (c[k] - pl["in_frame"] + pl["at_frame"] for k in ("start_frame", "end_frame"))
        x, y, w, h = c["box"]
        if s < a1 and a0 < e and pip.touches((qk["cx"], qk["cy"]), (x, y, x + w, y + h)):
            out.append({"sequence": pl["name"], "t": round(max(s, a0) / fps, 2), "what": f"the approved caption "
                        f"\"{c['text'][:40]}\" comes within {pip.CLEAR_PX} px of the outro's oval (R235)"})
    return out


def review_xml_quick(sp, out, run, logo, gains, voices, approved_n, clips=None, sounds=None, said=None):
    """The Quick Series design's review: "Intro: ..." and "Outro: ..." sequences, V1 left empty for the approved
    sequence (aidvStageReview nests it), the stage on V2, the picture-in-picture box's still (pipeline.edit.pip's spans
    and corner pictures) on its own track where the box is up in the stretch of the approved sequence shown, David's
    call-to-action footage (the outro) on a track above, the captions on top (C6). Motion for url.mov is set in
    Premiere after the import (aidvClipMotion), from the returned placements' "motion". said: the words its markers
    quote (quoted_words)."""
    from pipeline.edit import pip
    if said is None:
        raise SystemExit("review_xml_quick needs the words its markers quote (stage.quoted_words(doc))")
    fps, W, H = sp["fps"], sp["intro"]["width"], sp["intro"]["height"]
    root = ET.Element("xmeml", version="4")
    ids, files = pr.Ids(), pr.Files(fps)
    nf = lambda p: final.video_frames(p, fps)
    clips = clips or out / "clips"
    pipd = Path(sp["pip"]["dir"])
    spans = json.loads((pipd / "pip_spans.json").read_text(encoding="utf-8"))["spans"]
    pngs = json.loads((pipd / "pip_job.json").read_text(encoding="utf-8"))["pngs"]
    fade, T, f = round(pip.FADE_S * fps), sp["times"], lambda s: round(s * fps)
    spot = pip.SPOT_NAMES

    def stills(track, offset, lo, hi, first_png=None):
        """The box's still where its spans fall in [lo, hi) of this sequence (approved frame + offset); a piece cut by
        lo or hi has no fade there (the stage's own oval carries on, or the sequence ends). first_png: the first
        span's piece cut by lo shows it (meets_stage's intro picture, so the hand-over doesn't snap)."""
        got, s_in = [], int(3600 * fps)
        for s in spans:
            if s["spot"] == "hidden":
                continue
            a, b = max(s["f0"] + offset, lo), min(s["f1"] + offset, hi)
            if b <= a:
                continue
            fin = a == s["f0"] + offset and s["f0"] > 0
            fout = b == s["f1"] + offset and s["f1"] < approved_n and b < hi
            c = pr.clipitem(track, ids, f"avatar box {s['spot']}", a, b, s_in, s_in + b - a, 12 * s_in, fps,
                            alpha="straight")
            png = first_png if (first_png and s is spans[0] and a == lo) else Path(pngs[s["spot"]])
            files.el(c, png, frames=12 * s_in, w=W, h=H)
            pr.motion(c)
            k = ([(s_in, 0.0), (s_in + fade, 100.0)] if fin else [(s_in, 100.0)])
            k += ([(s_in + b - a - fade, 100.0), (s_in + b - a, 0.0)] if fout else [(s_in + b - a, 100.0)])
            pr.opacity(c, k)
            got.append((a, b, s["spot"]))
        return got

    places = []
    # the intro
    name = "Intro: full frame, the left third, then the oval"
    common_i, tail_i = clips / "intro_common.mov", clips / "intro_quick.mov"
    n_c, n_t = nf(common_i), nf(tail_i)
    nest_n = round(INTRO_NEST_S * fps)
    total = max(n_c + n_t, sp["nest_at"] + nest_n)
    s = pr.Seq(name, "sequence-intro-quick", fps, W, H, total)
    s.track("video", "Approved sequence")
    v2, v3 = s.track("video", "Avatar stage"), s.track("video", STILL_TRACK)
    s.track("video", titles.TRACK)
    s.track("audio", "Approved sequence")
    s.track("audio", "Logo outro right")
    a3 = s.track("audio", "Avatar voice")
    video_clip(v2, ids, files, "stage intro", 0, common_i, n_c, fps, W, H)
    video_clip(v2, ids, files, "stage intro (zoom-down and oval)", n_c, tail_i, n_t, fps, W, H)
    ipng = clips / "intro_oval_still.png" if meets_stage(sp)["intro"] else None
    if ipng and not ipng.exists():
        raise SystemExit(f"{ipng} is missing: render the stage again (its intro_oval_still job)")
    box_i = stills(v3, sp["nest_at"], n_c + n_t, total, ipng)
    audio_clip(a3, ids, files, "avatar voice", 0, voices["opening"], fps, gains["opening"])
    if sounds:
        place_sounds(s, ids, files, sp["intro_sounds"], 0.0, sounds, fps)
    pr.close_tracks(s)
    root.append(s.el)
    hs = spot[sp["pip"]["handover"]["intro_spot"]]
    marks = [{"t": 0.0, "comment": "Full frame on the cityscape, as in your Quick Series; captions bottom centre."},
             {"t": T["intro_move"], "comment": f"Before \"{said['left']}\": you slide left and shrink into the left "
              "third "
              f"({sp['intro']['avatar']['moves'][0]['dur']:.2f} s) as "
              "the roadmap card, unchanged, slides in on the right; each row on its word; captions under the card."},
             {"t": T["intro_expand"], "comment": f"After \"{said['closing']}\": the card grows into the Part 1 card "
              f"while you zoom down from the left third straight into the oval at the {hs} "
              f"({sp['intro']['avatar']['moves'][1]['dur']:.1f} s, linear), over the "
              "card: no dissolve, no gap."},
             {"t": sp["nest_at"] / fps, "comment": "Your approved sequence starts under the stage; the oval speaks its "
              "first sentence."},
             {"t": (n_c + n_t) / fps, "comment": "The intro's clip ends and the box goes on at the same spot (a still "
              "of you stands in for the later Avatar IV video)."}]
    places.append({"name": name, "kind": "intro", "variant": "quick", "stage_at": 0, "frames": total,
                   "at_frame": sp["nest_at"], "in_frame": 0, "out_frame": nest_n, "box_stills": box_i,
                   "markers": [{**m, "name": "Stage check"} for m in marks]})
    # the outro
    name = "Outro: the oval, the left third, then the call to action"
    common_o, tail_o = clips / "outro_common.mov", clips / "outro_quick.mov"
    n_c, n_t = nf(common_o), nf(tail_o)
    nest_n = round(OUTRO_NEST_S * fps)
    at = nest_n - round(OUTRO_FADE_S * fps)
    lg = nf(logo)
    t3 = at + n_c + n_t
    total = t3 + lg
    s = pr.Seq(name, "sequence-outro-quick", fps, W, H, total)
    v1 = s.track("video", "Approved sequence and logo")
    v2, v3, v4 = s.track("video", "Avatar stage"), s.track("video", STILL_TRACK), s.track("video", CTA_TRACK)
    s.track("video", titles.TRACK)
    a1, a2, a3 = (s.track("audio", "Approved sequence and logo"), s.track("audio", "Logo outro right"),
                  s.track("audio", "Avatar voice"))
    video_clip(v2, ids, files, "stage outro (the oval, the left third)", at, common_o, n_c, fps, W, H)
    video_clip(v2, ids, files, "stage outro (full frame)", at + n_c, tail_o, n_t, fps, W, H)
    box_o = stills(v3, nest_n - approved_n, 0, at + round(OUTRO_FADE_S * fps))
    ost = sp.get("outro_still")
    if ost:                                           # R235: the oval up as the main body ends, its still fading in,
        png = clips / "outro_oval_still.png"           # until the stage clip (the same frame, moving) takes over
        if not png.exists():
            raise SystemExit(f"{png} is missing: render the stage again (its outro_oval_still job)")
        a_, s_in = at + f(ost["t0"]), int(3600 * fps)
        c = pr.clipitem(v3, ids, "avatar oval (outro, still)", a_, at, s_in, s_in + at - a_, 12 * s_in, fps,
                        alpha="straight")
        files.el(c, png, frames=12 * s_in, w=W, h=H)
        pr.motion(c)
        pr.opacity(c, [(s_in, 0.0), (s_in + f(ost["fade_s"]), 100.0), (s_in + at - a_, 100.0)])
        box_o.append((a_, at, sp["pip"]["handover"]["outro_spot"]))
    cs, cu = sp["cta"]["subscribe"], sp["cta"]["url"]
    if "file" in cs:                                  # R232's original clip (R243's Remotion animation is the stage's)
        sa, sn = at + f(cs["t0"]), f(cs["s"])
        c = pr.clipitem(v4, ids, Path(cs["file"]).name, sa, sa + sn, 0, sn, sn, fps,
                        alpha={"premultiplied": "black"}.get(cs["alpha"], cs["alpha"]))
        files.el(c, Path(cs["file"]), frames=sn, w=W, h=H)
    ua = at + f(cu["t0"])
    un, um = t3 - ua, f(media_s(cu["file"]) - cu["in_s"])
    if un > um:
        raise SystemExit(f"url.mov holds {um} frames from its in point; the outro needs {un}")
    c = pr.clipitem(v4, ids, Path(cu["file"]).name, ua, t3, f(cu["in_s"]), f(cu["in_s"]) + un, um, fps,
                    alpha=cu["alpha"])
    files.el(c, Path(cu["file"]), frames=um, w=3840, h=2160)
    i0, kf = f(cu["in_s"]), max(1, f(cu["fade_out_s"]))
    pr.opacity(c, [(i0, 100.0), (i0 + un - kf, 100.0), (i0 + un, 0.0)])   # ep03's fade into the hard cut
    final.media_clip(v1, ids, files, "logo outro", t3, t3 + lg, 0, lg, logo, lg, fps, W, H, True)
    final.media_clip(a1, ids, files, "logo outro", t3, t3 + lg, 0, lg, logo, lg, fps, W, H, False, pan=-1)
    final.media_clip(a2, ids, files, "logo outro right", t3, t3 + lg, 0, lg, logo, lg, fps, W, H, False, channel=2,
                     pan=1)
    audio_clip(a3, ids, files, "avatar voice", at, voices["recap"], fps, gains["recap"])
    if sounds:
        place_sounds(s, ids, files, sp["outro_sounds"], at / fps, sounds, fps)
    pr.close_tracks(s)
    root.append(s.el)
    a, os_ = at / fps, spot[sp["pip"]["handover"]["outro_spot"]]
    oc = sp["outro"]["card"]
    snd = cs.get("sounds_s", {})
    marks = ([{"t": a + ost["t0"], "comment": f"As your sequence's last word ends, the oval fades in at the {os_} "
               f"({ost['fade_s']:.1f} s): you are there as the screen recording finishes, a still of the outro's own "
               "first frame for now (the Avatar IV test phase)."},
              {"t": a, "comment": "The moving avatar takes over in the oval from that same frame (no jump)."}]
             if ost else [{"t": a, "comment": "Your approved sequence's last 0.8 s, its last caption still up."}]) + [
             {"t": a + T["outro_grow"], "comment": f"The oval grows until the cityscape fills the frame "
              f"({OUTRO_FADE_S - T['outro_grow']:.1f} s, as your QuickArch03 outro's mask does), once the last "
              "caption has gone; you land in the left third."},
             {"t": a + T["outro_card"], "comment": f"\"{said['recap']}\": the recap card, unchanged, on the right; each row "
              "ticks on its word; captions under the card."},
             {"t": a + oc["t1"] - oc["outS"], "comment": f"Before \"{said['subscribe']}\": the card fades out ({oc['outS']:.1f} s), then "
              f"you return to full frame ({T['outro_cta_full'] - T['outro_full']:.1f} s), as in QuickArch03."},
             {"t": a + cs["t0"], "comment": (f"The subscribe animation, rebuilt in Remotion ({cs['remotion']} "
              "colours, R243), lower left as QuickArch03's original, starting 1.32 s before \"subscribe\"; captions "
              "middle left." if "remotion" in cs else "Your own subscribe animation from QuickArch03, placed as "
              "there (full frame, lower left), starting 1.32 s before \"subscribe\" as in QuickArch03; captions "
              "middle left, as there.") + (" Its sounds: a whoosh as it enters, a bell as the bell is clicked, our "
                                          "click as the thumb is clicked." if snd else "")},
             *([{"t": a + cs["t0"] + snd["bell"], "comment": "The hand clicks the bell: the bell sound."}]
               if "bell" in snd else []),
             *([{"t": a + cs["t0"] + snd["click"], "comment": "The hand clicks the thumb: our mouse click (R137)."}]
               if "click" in snd else []),
             {"t": a + cu["t0"], "comment": "Your own url footage from QuickArch03, placed as there (Position 0.530, "
              f"0.801; Scale 45%), its ink starting on \"{said['url']}\", fading over its last 0.13 s into the cut."},
             {"t": t3 / fps, "comment": "Hard cut to the logo outro."}]
    places.append({"name": name, "kind": "outro", "variant": "quick", "stage_at": at, "frames": t3, "at_frame": 0,
                   "in_frame": approved_n - nest_n, "out_frame": approved_n, "v1_clips": 1, "box_stills": box_o,
                   "motion": [{"track": CTA_TRACK, "start_frame": ua, "position": cu["motion"]["position"],
                               "scale": cu["motion"]["scale"], "clip": Path(cu["file"]).name}],
                   "markers": [{**m, "name": "Stage check"} for m in marks]})
    ET.indent(root, "\t")
    xml = out / f"{run}_stage_review.xml"
    xml.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode")
                   + "\n", encoding="utf-8")
    return xml, places


CUE_SOLO_MUTE = (0, 1, 2)        # the review's audio tracks muted to hear the stage's cues alone: the approved sequence
                                  # (and logo), the logo's right channel, the avatar's voice (review_xml_quick's order)
CUE_MATCH_LU = 2.0                # R235: the bell within this of the card's pop, as heard in Premiere's mix; and each
                                  # cue within this of its own file's level plus its clip gain (final.PREMIERE_MONO_DB)
CUE_HEARD_LUFS = -60.0            # a cue under this wasn't heard (a muted lane exports as -120.7: Fable, round 7)
CUE_PREROLL_S = 0.5               # ebur128's first windows are not full ones (400 ms)
# A cue's window: the bell's 1.3 s ring overlaps the thumb's click 0.97 s later, so the outro gets a "Stage sounds 2"
# lane (place_sounds); its click is measured with the bell's tail under it.


def cue_levels(path, at, cues, span_s=0.6):
    """Each cue's level in a WAV of the cues alone: the most of the momentary loudness windows ending within span_s
    (the bell's ring: 1.0 s) after the cue's time; at is the WAV's start on the same clock. [(kind, t, LUFS)]."""
    m = ldn.momentary(path)
    out = []
    for t, kind in cues:
        w = 1.0 if kind == "bell" else span_s
        vals = [v for tt, v in m if t - at < tt <= t - at + w]
        out.append((kind, round(t, 3), max(vals) if vals else None))
    return out


def mix_check(job, sp, out):
    """R177 and R204 in the mix Premiere itself renders (as pipeline.edit.ppro.final.mix_check): in one intro and one
    outro sequence, spans of the avatar's voice, the approved sequence beside it and the logo outro, exported as WAV
    and measured. R235: the stage's cues alone (CUE_SOLO_MUTE's tracks muted for the export) across the recap card's
    pop and first ticks and across the subscribe animation, each cue's momentary loudness, the bell within
    CUE_MATCH_LU of the pop; and the call to action with everything playing, for its true peak. The project is opened
    only when none is (R104) and closed unsaved."""
    fps, T = sp["fps"], sp["times"]
    seqs = {p["name"]: p for p in job["sequences"]}
    intro = next(n for n in seqs if n.startswith("Intro"))
    outro = next(n for n in seqs if n.startswith("Outro"))
    na = sp["nest_at"] / fps
    a = round(OUTRO_NEST_S * fps - OUTRO_FADE_S * fps) / fps          # where the outro stage starts
    end_o = a + sp["outro"]["durationInFrames"] / fps
    spans = {intro: {"voice": (2.0, T["intro_carry"] - 1.0), "approved": (na + 0.5, na + INTRO_NEST_S - 0.5)},
             outro: {"approved": (0.5, a - 0.2), "voice": (a + 1.5, end_o - 0.5),
                     "logo": (end_o, end_o + sp.get("logo_s", 7.2))}}
    cues = sorted((a + t, k) for t, k in sp["outro_sounds"])
    card = [c for c in cues if c[1] in ("pop", "tick")][:4]            # the card's pop and its first three ticks
    sub0 = a + sp["cta"]["subscribe"]["t0"]
    cta = [c for c in cues if sub0 - 1e-6 <= c[0] <= sub0 + sp["cta"]["subscribe"]["s"]]
    solo = {}
    if cta:
        solo = {"cues_card": (card[0][0] - CUE_PREROLL_S, card[-1][0] + 1.0),
                "cues_cta": (cta[0][0] - CUE_PREROLL_S, cta[-1][0] + 1.3)}
        spans[outro].update(solo)
        spans[outro]["cta_full_mix"] = (cta[0][0] - CUE_PREROLL_S, cta[-1][0] + 1.3)
    d = (out / "mix_check").resolve()
    d.mkdir(exist_ok=True)
    plan = {s: {k: [x, y, str(d / f"{s[:7].replace(' ', '_')}_{k}.wav"), list(CUE_SOLO_MUTE) if k in solo else []]
                for k, (x, y) in v.items()} for s, v in spans.items()}
    for v in plan.values():
        for x in v.values():
            Path(x[2]).unlink(missing_ok=True)
    code = """(function () {
      if (app.projects.numProjects > 0) { throw new Error("a project is open in Premiere (" + app.projects[0].path + ")"); }
      if (!app.openDocument(%s)) { throw new Error("Premiere wouldn't open the project"); }
      var r = {}, plan = %s, s, k, j;
      try {
        for (s in plan) {
          if (!plan.hasOwnProperty(s)) { continue; }
          var q = aidvFindSequence(s);
          app.project.openSequence(q.sequenceID);
          for (k in plan[s]) {
            if (!plan[s].hasOwnProperty(k)) { continue; }
            var mute = plan[s][k][3];
            for (j = 0; j < mute.length; j++) { q.audioTracks[mute[j]].setMute(1); }
            q.setInPoint(plan[s][k][0]);
            q.setOutPoint(plan[s][k][1]);
            r[s + " " + k] = q.exportAsMediaDirect(plan[s][k][2], %s, 1);
            for (j = 0; j < mute.length; j++) { q.audioTracks[mute[j]].setMute(0); }
          }
        }
      } finally {
        for (var i = app.projects.numProjects - 1; i >= 0; i--) {
          if (app.projects[i].path === %s) { app.projects[i].closeDocument(false, false); }
        }
      }
      return r;
    })()""" % (json.dumps(job["prproj"]), json.dumps(plan), json.dumps(final.WAV_PRESET), json.dumps(job["prproj"]))
    said = call(code, timeout=900)
    got = {}
    for s, v in plan.items():
        for k, (_, _, f, _) in v.items():
            if not Path(f).exists():
                raise SystemExit(f"Premiere exported no WAV for {s} {k} (it answered {said})")
            got[f"{s} | {k}"] = dict(zip(("lufs", "true_peak_dbtp"), ldn.measure([f])))
    diffs = {"intro_voice_vs_approved": round(got[f"{intro} | voice"]["lufs"] - got[f"{intro} | approved"]["lufs"], 1),
             "outro_voice_vs_approved": round(got[f"{outro} | voice"]["lufs"] - got[f"{outro} | approved"]["lufs"], 1),
             "logo_vs_outro_voice": round(got[f"{outro} | logo"]["lufs"] - got[f"{outro} | voice"]["lufs"], 1)}
    hot = [k for k, v in got.items() if v["true_peak_dbtp"] > final.MIX_MAX_PEAK_DBTP]
    levels, cue_ok = {}, True
    if solo:                                         # each cue as Premiere plays it, the voice and the nest muted
        levels = {"card": cue_levels(plan[outro]["cues_card"][2], solo["cues_card"][0], card),
                  "cta": cue_levels(plan[outro]["cues_cta"][2], solo["cues_cta"][0], cta)}
        pop = next((v for k, _, v in levels["card"] if k == "pop"), None)
        bell = next((v for k, _, v in levels["cta"] if k == "bell"), None)
        if not sp.get("sound_files"):
            raise SystemExit("stage_plan.json names no sound files (made before round 7): build the review again")
        # each cue's own level as Premiere plays it: its file's, plus the clip gain every cue lane has (a mono clip
        # plays at its file's LUFS in Premiere's mix; the cues carry final.PREMIERE_MONO_DB, as the voice: Fable, r7)
        own = {k: max(v for _, v in ldn.momentary(f)) + final.PREMIERE_MONO_DB for k, f in sp["sound_files"].items()}
        levels["files"] = own                         # each sound's own level, as its file plays alone
        heard = [(k, v) for x in ("card", "cta") for k, _, v in levels[x]]
        off = [(k, round(v - own[k], 1)) for k, v in heard if v is not None and k in own
               and abs(v - own[k]) > CUE_MATCH_LU and k != "click"]          # (the click has the bell's tail under it)
        levels["off_own_level"] = off
        cue_ok = (all(v is not None and v > CUE_HEARD_LUFS for _, v in heard) and not off
                  and (bell is not None and pop is not None and abs(bell - pop) <= CUE_MATCH_LU))
        diffs["bell_vs_card_pop"] = round(bell - pop, 1) if bell is not None and pop is not None else None
    res = {"spans_s": spans, "measured": got, "difference_db": diffs, "peaks_over": hot, "cue_levels_lufs": levels,
           "ok": all(abs(v) <= final.MIX_MAX_DIFF_DB for k, v in diffs.items() if k != "bell_vs_card_pop")
           and not hot and cue_ok}
    (d / "mix_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("steps")
    ap.add_argument("approved_dir")
    ap.add_argument("--out", default="stage_review_r1")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--only", default="", help="render only these jobs (comma-separated keys)")
    ap.add_argument("--stills-only", action="store_true", help="the check stills, no clips")
    ap.add_argument("--mix-check", action="store_true", help="only the mix check, on the folder's built project")
    ap.add_argument("--clips", default=None, help="use the stage clips already rendered in this folder")
    ap.add_argument("--no-premiere", action="store_true", help="everything for the review but Premiere's build")
    ap.add_argument("--build-only", action="store_true", help="Premiere's build from the folder's stage_job.json")
    ap.add_argument("--pip", default=None, help="design quick: the picture-in-picture review folder (in the run) whose "
                    "placement the intro hands over to and the outro takes over from (pip_spans.json's handover)")
    a = ap.parse_args(argv)
    run_dir, approved_dir = Path(a.run_dir).resolve(), Path(a.approved_dir).resolve()
    out = run_dir / a.out
    pub = run_dir / "stage_public"
    out.mkdir(parents=True, exist_ok=True)
    pub.mkdir(exist_ok=True)
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    doc = json.loads(Path(a.steps).read_text(encoding="utf-8"))
    if a.build_only:                                   # Premiere's part alone, into a copy never built or saved
        from pipeline.edit import pip
        c7 = out / "check_c7.json"
        if not c7.exists() or json.loads(c7.read_text(encoding="utf-8")):
            raise SystemExit(f"{c7}: missing or with findings; prepare again (--no-premiere) and fix them first")
        (approved,) = list(approved_dir.glob("*_full.prproj"))
        return pip.build(json.loads((out / "stage_job.json").read_text(encoding="utf-8")), approved)
    if a.mix_check:
        job = json.loads((out / "stage_job.json").read_text(encoding="utf-8"))
        sp = json.loads((out / "stage_plan.json").read_text(encoding="utf-8"))
        print(json.dumps(start(), ensure_ascii=False))
        res = mix_check(job, sp, out)
        print(json.dumps(res, indent=1))
        return 0 if res["ok"] else 1
    quick = doc["stage"].get("design") == "quick"         # round 6 (R231, R232)
    if quick:
        if not a.pip:
            raise SystemExit("the quick design needs --pip=<picture-in-picture review folder>")
        sp = plan_quick(run_dir, doc, plan, approved_dir, pub, (run_dir / a.pip).resolve())
    else:
        sp = plan_stage(run_dir, doc, plan, approved_dir, pub)
    (out / "stage_plan.json").write_text(json.dumps(sp, indent=1), encoding="utf-8")
    print(json.dumps(sp["times"], indent=1), "nest at frame", sp["nest_at"])
    if not a.no_render:
        res, bad = render(sp, pub, out, [k for k in a.only.split(",") if k] or None, a.stills_only)
        print(json.dumps(res, indent=1))
        if bad:
            print(json.dumps(bad, indent=1))
            return 1
        n, found = check_stills(out)                     # the measured checks on every still (G6, G7, R187)
        print(f"{n} stills checked: {len(found)} finding(s) in {out / 'checks.json'}")
        for f in found:
            print("  " + f.get("what", ""))
    if a.no_build or a.stills_only:
        return 0
    run = plan["run_id"]
    if "outro" not in sp:
        raise SystemExit("the outro's transparent render isn't there yet (pipeline.edit.avatar): no review to build")
    voices, gains = {}, {}
    for tag, key, until in (("opening", "intro", sp["intro_render"]["carry"]["at_s"] - 0.02),
                            ("recap", "outro", None)):
        g = sp[f"{key}_render"]
        trim = sp["intro_trim_s"] if tag == "opening" else PAD_S - RECAP_HEAD_S
        end = until if until else g["voice_at_s"] + g["voice_s"] + RECAP_TAIL_S
        voices[tag], gains[tag] = voice(run_dir, g, trim, end, plan, out, tag)
    from pipeline.edit.ppro import logo as logo_mod      # the last final's logo outro, or made for a run with none
    logo = logo_mod.media(run_dir, plan)                 # (R96, R204; GAPS_PLAN 3)
    sp["logo_s"] = final.video_frames(logo, sp["fps"]) / sp["fps"]
    (out / "stage_plan.json").write_text(json.dumps(sp, indent=1), encoding="utf-8")
    import importlib.util                              # the overlay sounds, made in code (tools/overlay_sounds.py)
    spec = importlib.util.spec_from_file_location("overlay_sounds", ROOT / "tools" / "overlay_sounds.py")
    snd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snd)
    peak = (plan.get("click_sound") or {}).get("peak_dbfs") or -24.0 + plan["loudness"]["effects_gain_db"]
    sounds = {k: Path(snd.write(k, peak)) for k in ("pop", "tick", "whoosh", "bell")}   # R158; R235: whoosh, bell
    sounds["click"] = run_dir / plan["click_sound"]["src"]   # R137's click, as on every demonstrated click
    sp["sound_files"] = {k: str(v) for k, v in sounds.items()}   # the mix check measures each against its file
    (out / "stage_plan.json").write_text(json.dumps(sp, indent=1), encoding="utf-8")
    nest_n = final.nest_frames(approved_dir, f"{run} full")
    clips = Path(a.clips).resolve() if a.clips else None
    xml, places = (review_xml_quick(sp, out, run, logo, gains, voices, nest_n, clips, sounds, quoted_words(doc)) if quick else
                   review_xml(sp, out, run, logo, gains, voices, clips, sounds))
    (approved,) = list(approved_dir.glob("*_full.prproj"))
    prproj = out / f"{run}_stage_review.prproj"
    if prproj.exists():
        raise SystemExit(f"{prproj} exists (David's?); not overwriting it: use a new --out")
    for p in places:                                   # an outro shows the approved sequence's last OUTRO_NEST_S
        if p["in_frame"] is None:
            p["in_frame"], p["out_frame"] = nest_n - p.pop("nest_tail"), nest_n
        p["titles"] = (stage_titles_quick(p, sp, plan, approved_dir, out, doc["stage"]["quick"]) if quick else
                       stage_titles(p, sp, plan, run_dir, approved_dir, out))
    bins = BINS if not quick else {**BINS, "media": (
        [{"bin": "Avatar box", "match": r"[\\/]intro_oval_still\.png$"}] if meets_stage(sp)["intro"] else []) + [
        {"bin": "Avatar box", "match": r"[\\/]pip_oval_[^\\/]+\.png$|[\\/]outro_oval_still\.png$"},
        {"bin": "Call to action (QuickArch03)", "match": r"SubscribesV2\.mov$|[\\/]url\.mov$"}] + BINS["media"]}
    job = {"prproj": str(prproj.resolve()), "xml": str(xml.resolve()), "nest": f"{run} full", "fps": sp["fps"],
           "nest_frames": nest_n, "sequences": places, "bins": bins}
    (out / "stage_job.json").write_text(json.dumps(job, indent=1, ensure_ascii=False), encoding="utf-8")
    if quick:                                          # VIDEO_RULES C7, R213, C2/G13: captions, the avatar, the oval,
        c7, measured = check_c7_quick(places, sp, pub, clips or out)   # the card and the call to action (the
                                                       # subscribe animation alone from the clips used: --clips too)
        c7 += check_outro_still(places, sp, approved_dir)   # R235: the oval over the main body's last seconds
        (out / "check_c7_measures.json").write_text(json.dumps(measured, indent=1), encoding="utf-8")
    else:
        c7 = check_c7(places, sp)                      # VIDEO_RULES C7, R213: captions and the oval
    (out / "check_c7.json").write_text(json.dumps(c7, indent=1), encoding="utf-8")
    print(f"C7 (captions and the oval): {len(c7)} finding(s)")
    for f in c7:
        print("  " + f["what"])
    if a.no_premiere or c7:                            # a caption on the oval is fixed before David sees it
        return 1 if c7 else 0
    shutil.copy2(approved, prproj)
    print(json.dumps(start(), ensure_ascii=False))
    r = call(f"aidvStageReview({json.dumps(job, ensure_ascii=False)})", timeout=900, reload=True)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("saved") and not r.get("problems") else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
