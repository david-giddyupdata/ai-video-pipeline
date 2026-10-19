"""The measured checks (R179 to R187; D:\\Videos\\Global Assets\\VIDEO_RULES.md, "The checks"), run before every export
and, for the overlays, inside tools/overlay_review.py check. Each reports by timecode on the full sequence (R106).

    python -m pipeline.edit.checks runs/<run_id> [--plan=<edit_plan.json>] [--only=captions,named,flicker,breaths,tokens]
                                   [--no-second-reader]

Edit checks (on a plan; written to <plan's folder>/checks/report.md and findings.json):
  captions   R182  every caption cue against what its line names, marks or clicks, for the whole line
  named      R186  every label, quoted word or interface term a line names that is on screen, against the marks,
                   highlights and overlays within its sentence; RapidOCR reads again where Windows OCR missed (R227)
  flicker    R183  each typing step's field, frame by frame: an A-B-A-B alternation fails, and a `drop` is proposed
  breaths    R181  two inhales within 1.5 s with no speech between (a beat splitting a breath is one case)
  tokens     R179  every text colour against its background in the look's tokens and the captions' settings

Still checks (on a rendered overlay: the composite over the real frame and the overlay's own alpha), used by the
harness: text_contrast (R179: 7:1, nothing see-through behind text), see_through (R179, R164), alignment (R187:
capital tops and baselines per row, left edges per column, within 2 px); display_time (R185) on timed layers.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from pipeline.config import ROOT, tool
from pipeline.edit import camera as cam
from pipeline.edit import marks as mk
from pipeline.edit import sentences
from pipeline.ml import ocr as ml_ocr
from pipeline.narration import timing

CACHE = ROOT / "audio_cache"
TOKENS = ROOT / "remotion" / "src" / "overlays" / "tokens.json"
MIN_RATIO = 7.0                                       # R179
MIN_READ_PX = 12                                      # R81: OCR text shorter than this on the output isn't readable
SMALL_READ_PX = 14                                    # R198: named text should be at least this tall on the output
ARROW_REACH = 30                                      # an arrow points at the text its head is within this of (px)
TARGET_REACH = 24                                     # and, on a click step, at the text this near its target's box
NAMED_IGNORE = {"quick sight", "amazon", "amazon quick", "windows", "edge", "i"}   # names the screen always shows


def tc(t, fps=30):
    f = round(t * fps)
    return f"{f // (3600 * int(fps)):02d}:{f // (60 * int(fps)) % 60:02d}:{f // int(fps) % 60:02d}:{f % int(fps):02d}"


def finding(check, rule, t, what, **more):
    return {"check": check, "rule": rule, "t": None if t is None else round(t, 3), "tc": None if t is None else tc(t),
            "what": what, **more}


# ------------------------------------------------------------------------------------------------ colour maths
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = c[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a, b):
    la, lb = sorted((luminance(_rgb(a) if isinstance(a, str) else a), luminance(_rgb(b) if isinstance(b, str) else b)),
                    reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check_tokens(tokens=None, captions=None):
    """R179, R180: each variant's text colours on its panel and its wells, the chip, and the captions' text on their
    box; a panel that isn't opaque; orange named as a text colour."""
    tokens = tokens or json.loads(TOKENS.read_text(encoding="utf-8"))
    out = []
    for name, v in tokens["color"]["variant"].items():
        if v.get("panelOpacity", 1.0) < 1.0:
            out.append(finding("tokens", "R179", None, f"the {name} variant's panel is {v['panelOpacity']:.0%} "
                                                       "opaque: the screen shows through behind its text"))
        pairs = [(k, v[k], bg, v[bg]) for k in ("heading", "body") for bg in ("panel", "well") if v.get(k)]
        pairs.append(("muted", v["muted"], "panel", v["panel"]))   # muted text sits on the panel, never on a well
        pairs.append(("chipText", v["chipText"], "chip", v["chip"]))
        for k, fg, bgk, bg in pairs:
            r = ratio(fg, bg)
            if r < MIN_RATIO:
                out.append(finding("tokens", "R179", None, f"{name} variant: {k} {fg} on {bgk} {bg} is {r:.2f}:1, under "
                                                           f"{MIN_RATIO:.0f}:1"))
    for k in ("heading", "body", "muted", "chipText"):
        for name, v in tokens["color"]["variant"].items():
            if v.get(k, "").lower() == tokens["color"]["accent"].lower():
                out.append(finding("tokens", "R180", None, f"{name} variant's {k} is the orange accent: orange is for "
                                                           "shapes only"))
    for where, c in (captions or {}).items():
        fg, bg = c.get("text_color", "#FFFFFF"), c.get("box_color")
        if bg and ratio(fg, bg) < MIN_RATIO:
            out.append(finding("tokens", "R179", None, f"captions ({where}): {fg} on {bg} is {ratio(fg, bg):.2f}:1, "
                                                       f"under {MIN_RATIO:.0f}:1 (R192)"))
    return out


# ------------------------------------------------------------------------------------------ captions (R182)
def cue_box(c, style):
    """A cue's box in output px, as the planner placed it (place_captions' own measure)."""
    lines = c["text"].split("\n")
    size = style["size_px"]
    w = max(len(l) for l in lines) * size * 0.6 + 2 * style.get("pad_x_px", 18)
    h = len(lines) * size * style.get("line_height", 1.25) + 2 * style.get("pad_y_px", 8)
    x0 = c["pos"]["cx"] - w / 2
    return (x0, c["pos"]["y"], x0 + w, c["pos"]["y"] + h)


def _overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 0 and min(a[3], b[3]) - max(a[1], b[1]) > 0


def _screen_box(keys, t, b, W, H, pad=0):
    (x0, y0), (x1, y1) = cam.to_screen(keys, t, (b[0], b[1]), W, H), cam.to_screen(keys, t, (b[2], b[3]), W, H)
    return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)


def _in_view(b, W, H):
    return b[2] > 0 and b[0] < W and b[3] > 0 and b[1] < H


def check_captions(plan, named_boxes=()):
    """R182: a caption never covers what its line is about, for the whole line: its click target, its marks and
    highlights (drawn yet or not), and the things it names (named_boxes: [(t0, t1, screen box, label, step)]),
    through the camera, sampled every 0.2 s of the cue."""
    W, H, keys = plan["width"], plan["height"], plan["camera"]
    style = dict(plan["settings"]["captions"], **plan["captions"].get("style", {}))
    lines = [(n["start"], n["start"] + n["length"], n["step"]) for n in plan["narration"]]
    targets = {c["step"]: c["box"] for c in plan.get("click_targets") or []}
    marks_by = {}
    for m in plan["marks"]["layers"]:
        marks_by.setdefault(m["step"], []).append((m["kind"], _mark_box(m)))
    region = lambda kind, b: kind == "highlight" or (b[2] - b[0]) * (b[3] - b[1]) > 0.15 * W * H
    cover = lambda a, b: max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    out, seen = [], set()
    for c in plan["captions"]["cues"]:
        box = cue_box(c, style)
        steps = [s for l0, l1, s in lines if l0 < c["end"] and c["start"] < l1]
        things = []
        for s in steps:
            if s in targets:
                things.append((f"the click target of {s}", targets[s], region("rect", targets[s])))
            things += [(f"the {k} mark of {s}", b, region(k, b)) for k, b in marks_by.get(s, [])]
        t = c["start"]
        area = (box[2] - box[0]) * (box[3] - box[1])
        while t <= c["end"] - 0.05:
            for what, b, big in things:              # a region (a pane, the whole visual) counts when the caption
                sb = _screen_box(keys, t, b, W, H, pad=0 if big else 8)   # covers a real part of it
                hit = cover(box, sb) > 0.3 * area if big else _overlap(box, sb)
                if _in_view(sb, W, H) and hit and (c["start"], what) not in seen:
                    seen.add((c["start"], what))
                    out.append(finding("captions", "R182", t, f"the caption \"{c['text'][:40]}\" ({c['pos']['where']}) "
                                       f"covers {what}", cue_start=c["start"]))
            for n0, n1, sb, label, s in named_boxes:
                if s in steps and n0 <= t <= n1 and _overlap(box, sb) and (c["start"], label) not in seen:
                    seen.add((c["start"], label))
                    out.append(finding("captions", "R182", t, f"the caption \"{c['text'][:40]}\" ({c['pos']['where']}) "
                                       f"covers \"{label}\", which its line names", cue_start=c["start"]))
            t += 0.2
    return out


# --------------------------------------------------------------------------- named but not pointed out (R186)
def _steps_doc(run, plan):
    with (run / "runlog.jsonl").open(encoding="utf-8") as f:
        ex = json.loads(f.readline()).get("exercise", "")
    sp = ROOT / "exercises" / ex / plan["steps_file"]
    return json.loads(sp.read_text(encoding="utf-8")), sp.parent


def line_terms(text, labels):
    """What a line names: its labels, its quoted words, and capitalised words or runs of them inside a sentence
    (interface terms such as "Action 1"), each with its character position."""
    terms = {}
    for lb in labels or []:
        i = text.find(lb)
        if i >= 0:
            terms.setdefault(lb, i)
    for m in re.finditer(r"[\"“]([^\"”]{2,40})[\"”]", text):
        terms.setdefault(m.group(1), m.start(1))
    for m in re.finditer(r"\b([A-Z][\w-]*(?:\s+(?:[A-Z][\w-]*|\d+))*)", text):
        w, before = m.group(1), text[:m.start(1)].rstrip(" \"“'(")
        if not before or before[-1] in ".?!:":           # a sentence's first word is capitalised anyway
            continue
        if len(w) >= 3 and w.lower() not in NAMED_IGNORE and w.split()[0] not in ("I", "I'll", "I'm"):
            terms.setdefault(w, m.start(1))
    return terms


def _norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def find_on_screen(term, words):
    """Boxes (output px) where the term's words appear in order on one OCR line, or the term as one OCR word."""
    toks = [_norm(t) for t in re.findall(r"[\w]+", term) if _norm(t)]
    if not toks:
        return []
    ws = [(_norm(w[0]), w) for w in words]
    hits = []
    for i, (n, w) in enumerate(ws):
        if n == toks[0] or (len(toks) == 1 and n.startswith(toks[0]) and len(toks[0]) >= 4):
            run, j = [w], i
            for t in toks[1:]:
                if j + 1 < len(ws) and ws[j + 1][0] == t and abs(ws[j + 1][1][2] - w[2]) < w[4]:
                    run.append(ws[j + 1][1])
                    j += 1
                else:
                    break
            if len(run) == len(toks):
                hits.append((min(r[1] for r in run), min(r[2] for r in run), max(r[1] + r[3] for r in run),
                             max(r[2] + r[4] for r in run)))
        elif len(toks) > 1 and n == "".join(toks):
            hits.append((w[1], w[2], w[1] + w[3], w[2] + w[4]))
    return hits


def _src_box(keys, t, b, W, H):
    """An output-px box at edit time t as recording px (through the camera)."""
    s, cx, cy = cam.cam_at(keys, t, W, H)
    return ((b[0] - W / 2) / s + cx, (b[1] - H / 2) / s + cy, (b[2] - W / 2) / s + cx, (b[3] - H / 2) / s + cy)


def _grow(b, d):
    return (b[0] - d, b[1] - d, b[2] + d, b[3] + d)


def _mark_box(m):
    a, c = m["from"], m["to"]
    return (min(a["x"], c["x"]), min(a["y"], c["y"]), max(a["x"], c["x"]), max(a["y"], c["y"]))


# R199: the four kinds of named thing that need no mark of their own, read from the sentence around the name
DESTINATION = re.compile(r"(?:takes? you(?: back)? to|lands? on|returns? to|opens,? on|you're(?: back)? on)\s+"
                         r"(?:the\s+)?$", re.I)              # told after the click, never "I'll switch to"
LANDMARK = re.compile(r"(?:next to|to the (?:right|left) of|(?:right|left) of|beside|below|above|under|underneath|near|"
                      r"at the (?:top|bottom) of)\s+(?:the\s+)?$", re.I)
ON_LANDMARK = re.compile(r"\b(?:icon|arrow|caret|chevron|button|pencil|link|pin|dot|handle|row|box|field|menu|tab|"
                         r"toggle)\s+on\s+(?:the\s+)?$", re.I)                # "the arrow on the Add button"
IN_PANE = re.compile(r"\b(?:in|inside|within|from|back in)\s+the\s+$", re.I)    # "In the Data pane, I'll click"
PANE_WORD = re.compile(r"^\s+(?:pane|list|menu|bar|box|tab|section|panel|well|row)\b", re.I)
TYPED = re.compile(r"\b(?:I'll type|and type|then type|type in|typing|typed|I'll enter|and enter|"
                   r"replace .* with)\b", re.I)                               # in the term's own clause
LOOK = re.compile(r"\b(?:notice|look at|you can see|you'll see|see|watch|find|spot|at the (?:top|bottom)\b|"
                  r"at the (?:far )?(?:left|right|end)\b|along the (?:top|bottom|left|right)|"
                  r"(?:top|bottom|upper|lower)[ -](?:left|right)|on the (?:left|right)\b|above the|below the|beneath|"
                  r"in the corner|in the middle)", re.I)
READ_BEFORE = re.compile(r"\b(?:is|are|reads|named|called|set to)\s+(?:the\s+)?$", re.I)
VALUE_AFTER = re.compile(r"^\s+(?:is|are)\s+the\s+\w+est\b"                    # "East is the busiest"
                         r"|^(?:\s+[\w-]+)?\s+is\s+[A-Z]")                      # "Target visuals is All visuals"
STATE_AFTER = re.compile(r"^(?:\s+[\w-]+){0,2}\s+(?:becomes?|opens?|appears?)\b(?P<rest>[^.;!?]*)", re.I)
PLACE = re.compile(r"\b(?:under|in|on|at|next to|above|below|beside|inside)\b", re.I)   # "appears under Actions"
CLAUSE_BREAK = re.compile(r",\s+(?:and|then|so|but)\b|[.;!?]")
INSTRUCTION = re.compile(r"\b(?:I'll|I|we'll|let's)\s+(?:\w+\s+)?(?:click|open|choose|select|expand|press|drag|"
                         r"tick|turn on|switch on|pick|type|enter|go|switch)\b", re.I)
WORD_BREAK = re.compile(r"\b(?:which|where|and|then|so|but|while)\b|[.;!?]", re.I)


def _clause(before):
    """The part of the text before a term that belongs to the term's own clause."""
    cuts = list(CLAUSE_BREAK.finditer(before))
    return before[cuts[-1].end():] if cuts else before


def not_needed(term, sentence, at, step):
    """R199: why a term a line names needs no mark of its own, or None when it does. sentence is the sentence's
    text, at the term's offset in it. The kinds: the page or tab a click lands on (told after the click), a landmark
    that only helps find something else, text being typed, and a result or value read out as it appears. A sentence
    that sends the eye somewhere ("Notice", "at the top right", "above the title") keeps its finding unless the name
    is a landmark or the step's typed text; a clause that tells the narrator's action before the term ("I'll open
    the dropdown that reads Select a data type") is never a read-out; something that appears at a place ("Action 1
    now appears under Actions") is a thing to find. The click target's own name is pointed out by its mark
    (check_named)."""
    before, after = sentence[:at], sentence[at + len(term):]
    clause = _clause(before)
    told = INSTRUCTION.search(clause)
    act = step.get("action") or {}
    if DESTINATION.search(before) and not told:
        return "where a click lands"
    if LANDMARK.search(before) or ON_LANDMARK.search(before) or (
            IN_PANE.search(before) and PANE_WORD.search(after) and INSTRUCTION.search(after)):
        return "a landmark"
    if act.get("type") == "type" and term.lower() in (act.get("text") or "").lower():
        return "typed"
    if LOOK.search(sentence):
        return None
    if TYPED.search(clause):
        return "typed"
    if told:
        return None
    if READ_BEFORE.search(before) or VALUE_AFTER.search(after):
        return "read out as it appears"
    if (m := STATE_AFTER.search(after)) and not PLACE.search(m.group("rest")):
        return "read out as it appears"               # "the Select button becomes available"
    return None


def names_click_target(term, sentence, at, step):
    """The term names the step's click target: it is one of the step's labels and is the click word, or follows the
    click word (as a whole word) in the same clause within four words ("I'll click the third icon, Vertical bar
    chart"; not "I'll click Save, which puts Action 1 ...")."""
    n = step.get("narration") or {}
    cw = n.get("click_word")
    if not cw or term not in (n.get("labels") or []) or (step.get("action") or {}).get("type") != "click":
        return False
    if sentence[at:].startswith(cw):
        return True
    hits = list(re.finditer(r"\b" + re.escape(cw) + r"\b", sentence[:at]))
    if not hits:
        return False
    between = sentence[hits[-1].end():at]
    return not WORD_BREAK.search(between) and len(between.split()) <= 4


def check_named(run, plan, out_dir, second_reader=True, stats=None):
    """R186: each term a line names that the viewer can read at its word needs a mark, a highlight or an overlay on
    it within its sentence: a mark up during the sentence (any step's) with the term under it, read by OCR at the
    mark's own time (a click changes the screen 0.35 s after the name, so the term's own moment may show the next
    page). An arrow points at the text near its head; the click target's own name is pointed out by the target's
    mark. R199 narrows it: a landmark, typed text, a result or value read out, or where a click lands needs no mark
    (`not_needed`, listed as waived), and a term named before at the same place is a repeat, never marked again.
    R198: a first mention under 14 px tall is a finding of its own. Mentions of one term in one line are judged
    together. Returns (findings, named_boxes for check_captions: where each named term is on screen while its
    sentence plays).

    R227, the second reader: RapidOCR (pipeline.ml.ocr.second_read) reads again only the frames where Windows OCR
    missed: a term's mention frames when Windows OCR read it at none of them, and the frames of the marks up during
    its sentences when no mark had it under it. A term on screen only as RapidOCR reads it is judged like any other,
    its findings saying so (reader "rapidocr"; no R198 size finding, since RapidOCR's boxes sit 4 to 7 px taller than
    the letters); a term pointed out only as RapidOCR reads it under the mark is listed as "R186 second reader",
    never a marker. second_reader False, or the plan's settings "checks": {"second_reader": false}: Windows OCR
    alone. stats: a dict to receive what the second reader did."""
    from pipeline.edit import linecheck as lc
    W, H, keys = plan["width"], plan["height"], plan["camera"]
    doc, _ = _steps_doc(run, plan)
    by_id = {s["id"]: s for s in doc["steps"]}
    ignore = {x.lower() for x in (plan["settings"].get("checks") or {}).get("named_ignore", [])} | NAMED_IGNORE
    jobs = []
    for n in plan["narration"]:
        meta = timing.of(n)                           # R227: the times the line was built with
        text, ws = meta["display_text"], meta["words"]
        parts = n.get("parts") or [{"at": n["start"], "in": 0.0, "out": n["audio_s"]}]
        at = lambda o, parts=parts, n=n: next((p["at"] + o - p["in"] for p in reversed(parts) if p["in"] <= o + 1e-6),
                                              n["start"] + o)
        cuts = [b["after"] for b in sentences.breaks(text, ws)] + [len(ws) - 1]
        spans, a = [], 0
        for z in cuts:
            spans.append((ws[a]["char"][0], ws[z]["char"][1], at(ws[a]["start"]), at(ws[z]["end"])))
            a = z + 1
        labels = ((by_id.get(n["step"]) or {}).get("narration") or {}).get("labels") or []
        terms = line_terms(text, labels)
        for term in list(terms):                      # a capitalised word inside a longer named term is that term
            if term not in labels and any(term != o and term.lower() in o.lower() for o in terms):
                terms.pop(term)
        for term in terms:
            if term.lower() in ignore:
                continue
            mentions = []
            for mm in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text):   # not "Data" in "Datasets"
                w = next((x for x in ws if x["char"][0] <= mm.start() < x["char"][1] + 1), None)
                sp = next((s for s in spans if s[0] <= mm.start() <= s[1]), spans[-1])
                if w is not None:
                    mentions.append({"t": round(at(w["start"]) + 0.3, 2), "s0": sp[2], "s1": sp[3],
                                     "sent": text[sp[0]:sp[1] + 1], "off": mm.start() - sp[0]})
            if mentions:
                jobs.append({"step": n["step"], "term": term, "mentions": mentions, "explicit": term in labels})
    layers = plan["marks"]["layers"]
    mark_t = [round(min(m["draw1"] + 0.2, m["fade0"]), 2) for m in layers]
    times = sorted({mt["t"] for j in jobs for mt in j["mentions"]} | set(mark_t))
    import hashlib                                    # frames are named by time only: one folder per camera and cut
    sig = hashlib.sha256(json.dumps([plan["camera"], plan["segments"]], sort_keys=True).encode()).hexdigest()[:10]
    fdir = out_dir / f"named_frames_{sig}"            # list, so a re-plan never reuses one (a viewer may hold a file)
    paths = lc.frames(run, plan, times, fdir)
    words = lc.ocr(fdir)
    seen_at = {t: words.get(p.name, []) for t, p in zip(times, paths)}
    targets = {c["step"]: c["box"] for c in plan.get("click_targets") or []}

    def under_mark(m, t, ws):
        """The OCR words (of ws, the frame at t) that mark m points out."""
        if m["kind"] == "arrow":                      # an arrow points with its head, which stops at the text's edge;
            hb = _screen_box(keys, t, (m["to"]["x"], m["to"]["y"], m["to"]["x"], m["to"]["y"]), W, H, pad=1)
            tb = _screen_box(keys, t, targets[m["step"]], W, H, pad=TARGET_REACH) if m["step"] in targets else None
            return [w for w in ws                     # on a click step's small target it points out the label beside
                    if _overlap(_grow((w[1], w[2], w[1] + w[3], w[2] + w[4]), ARROW_REACH), hb)
                    or (tb and _overlap(tb, (w[1], w[2], w[1] + w[3], w[2] + w[4])))]   # it (a tab's caret)
        sb = _screen_box(keys, t, _mark_box(m), W, H, pad=10)
        return [w for w in ws if _overlap(sb, (w[1], w[2], w[1] + w[3], w[2] + w[4]))]

    def legible(term, ws, pad=0):                     # text under 12 px on screen isn't readable (R81); pad: a
        return [h for h in find_on_screen(term, ws) if h[3] - h[1] - pad >= MIN_READ_PX]   # reader's box excess

    up = lambda m, mt: m["draw0"] <= mt["s1"] + 0.5 and m["fade1"] >= mt["s0"] - 0.3   # the mark is up then
    under = [(m, under_mark(m, t, seen_at[t])) for m, t in zip(layers, mark_t)]   # each mark and what it points out
    on = second_reader and (plan["settings"].get("checks") or {}).get("second_reader", True)
    second_at = {}                                    # R227: RapidOCR's words, on the frames Windows OCR missed
    info = {"frames": 0, "note": None if on else "off: --no-second-reader or the settings"}
    if on:
        again = set()
        for j in jobs:
            cand = [mt for mt in j["mentions"] if legible(j["term"], seen_at[mt["t"]])]
            if not cand:                              # not read at any mention: is it there?
                cand = j["mentions"]
                again |= {mt["t"] for mt in cand}
            if not any(find_on_screen(j["term"], ws_) for m, ws_ in under for mt in cand if up(m, mt)):
                again |= {t for m, t in zip(layers, mark_t) if any(up(m, mt) for mt in cand)}   # under a mark?
        if again:
            path_at = dict(zip(times, paths))
            try:
                r2 = ml_ocr.second_read([path_at[t] for t in sorted(again)])
                second_at = {t: ml_ocr.words_of(r2[str(Path(path_at[t]).resolve())]) for t in again}
                info["frames"] = len(again)
            except Exception as e:                    # the venv or the GPU unavailable: Windows OCR stands
                info["note"] = f"not run: {type(e).__name__}: {str(e)[-200:]}"
    under2 = [(m, under_mark(m, t, second_at[t])) for m, t in zip(layers, mark_t) if t in second_at]
    if stats is not None:
        stats.update(info)
    out, named_boxes, done_terms = [], [], []
    for j in sorted(jobs, key=lambda j: j["mentions"][0]["t"]):
        shown = [(mt, legible(j["term"], seen_at[mt["t"]])) for mt in j["mentions"]]
        shown = [(mt, h) for mt, h in shown if h]
        alone = not shown and bool(second_at)         # on screen only as RapidOCR reads it (R227)
        if alone:
            shown = [(mt, legible(j["term"], second_at[mt["t"]], ml_ocr.PAD_PX)) for mt in j["mentions"]
                     if mt["t"] in second_at]
            shown = [(mt, h) for mt, h in shown if h]
        if not shown:
            continue                                  # not readable on screen then: the line check's business (R81)
        say = " (read by RapidOCR alone, R227: Windows OCR didn't read it)" if alone else ""
        more = {"reader": "rapidocr"} if alone else {}
        for mt, hits in shown:                        # the step's own labels only: a capitalised word can match
            if j["explicit"]:                         # the same word elsewhere on screen (a chart's title)
                named_boxes += [(mt["s0"], mt["s1"], h, j["term"], j["step"]) for h in hits]
        pointed = any(find_on_screen(j["term"], ws_) for m, ws_ in under for mt, _ in shown if up(m, mt))
        for o in plan.get("overlays") or []:          # an overlay that shows the term counts as pointing it out
            if any(o["t0"] <= mt["s1"] and mt["s0"] <= o["t1"] for mt, _ in shown) and \
                    j["term"].lower() in json.dumps(o).lower():
                pointed = True
        for w in plan.get("wholes") or []:            # a dialog the camera frames whole (R123) that the term names
            if w.get("framed", True) and j["term"].lower() in (w.get("what") or "").lower() and \
                    any(w["t0"] <= mt["s1"] and mt["s0"] <= w["t1"] for mt, _ in shown):
                pointed = True
        step = by_id.get(j["step"]) or {}
        if not pointed and any(names_click_target(j["term"], m_["sent"], m_["off"], step) and any(
                m["step"] == j["step"] and m["draw0"] <= m_["s1"] + 0.5 and m["fade1"] >= m_["s0"] - 0.3
                for m in layers) for m_, _ in shown):
            pointed = True                            # the click target's own name: its mark is on the target
        second_pointed = not pointed and any(find_on_screen(j["term"], ws_) for m, ws_ in under2 for mt, _ in shown
                                             if up(m, mt))   # R227: under the mark only as RapidOCR reads it
        pointed = pointed or second_pointed
        mt, hits = shown[0]
        words_ = frozenset(_norm(x) for x in j["term"].split())
        here = [_src_box(keys, m_["t"], h, W, H) for m_, hs in shown for h in hs]   # where it is on the recording
        first = next(((t_, sec) for ws_, t_, boxes, sec in done_terms
                      if (ws_ <= words_ or words_ <= ws_)                 # "Visuals" ~ "Visuals pane"
                      and any(_overlap(_grow(a, 30), b) for a in boxes for b in here)), None)   # and the same place
        before = first[0] if first else None
        seeded = bool(first and first[1])             # R227: that first mention was judged on RapidOCR's word alone
        why = (step.get("not_pointed") or {}).get(j["term"])
        kinds = [not_needed(j["term"], m_["sent"], m_["off"], step) for m_, _ in shown]
        small = min(h[3] - h[1] for h in hits)        # the smallest match: a bigger stray can't hide a small label
        rest = abs(cam.cam_at(keys, mt["t"], W, H)[0] - ((plan["settings"].get("zoom") or {}).get("level") or 1.35))
        if before is None and not alone and small < SMALL_READ_PX and rest > 0.01:   # R198, R202: 12 px is fine
            # at the camera's rest; elsewhere (a dialog at its own size, a zoom-in) aim at 14 px; listed, not a
            # marker. Not from RapidOCR's boxes, which overstate the height (R227)
            out.append(finding("named", "R198 small", mt["t"] - 0.3, f"{j['step']} names \"{j['term']}\", on "
                               f"screen {small:.0f} px tall (R198 aims at 14)", step=j["step"], term=j["term"]))
        if pointed:
            done_terms.append((words_, mt["t"], here, alone or second_pointed))
            if second_pointed:                        # listed for a look at the mark's crop, never a marker
                out.append(finding("named", "R186 second reader", mt["t"] - 0.3, f"{j['step']} names "
                                   f"\"{j['term']}\": pointed out, but only RapidOCR read it "
                                   + ("on screen and under the mark" if alone else "under the mark")
                                   + " (R227: Windows OCR didn't); check the mark's crop", step=j["step"],
                                   term=j["term"], reader="rapidocr"))
        elif why:                                     # left unmarked on purpose, with the step's reason
            done_terms.append((words_, mt["t"], here, alone))
            out.append(finding("named", "R186 waived", mt["t"] - 0.3, f"{j['step']} names \"{j['term']}\", not "
                               f"pointed out: {why}" + say, step=j["step"], term=j["term"], **more))
        elif before is not None:                      # pointed out (or waived) before: never marked again (R199)
            out.append(finding("named", "R186 repeat", mt["t"] - 0.3, f"{j['step']} names \"{j['term']}\" again; it "
                               f"was first named at {tc(before)}" + (say or (" (that first mention was judged as "
                               "RapidOCR alone read it, R227)" if seeded else "")), step=j["step"], term=j["term"],
                               **(more or ({"reader": "rapidocr"} if seeded else {}))))
        elif all(kinds):                              # R199: a kind of name that needs no mark of its own
            out.append(finding("named", "R186 waived", mt["t"] - 0.3, f"{j['step']} names \"{j['term']}\": "
                               f"{kinds[0]}, no mark needed (R199)" + say, step=j["step"], term=j["term"], **more))
        else:                                         # a miss never hides a later miss (it doesn't seed repeats)
            out.append(finding("named", "R186", mt["t"] - 0.3, f"{j['step']} names \"{j['term']}\", on screen at "
                               f"{tuple(round(v) for v in hits[0])}, and no mark in its sentence points it out"
                               + ("" if j["explicit"] else " (a capitalised term, not in the step's labels)") + say,
                               step=j["step"], term=j["term"], box=[round(v) for v in hits[0]],
                               explicit=j["explicit"], t_box=mt["t"], **more))
    return out, named_boxes


# --------------------------------------------------------------------------------- typed-field flicker (R183)
def _gray_frames(video, t0, t1, fps, scale=2):
    """Grey frames of the source from t0 to t1, every frame, at 1/scale size: (first frame number, array)."""
    from PIL import Image
    k0, k1 = int(t0 * fps), int(t1 * fps) + 1
    W, H = 1920 // scale, 1080 // scale
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-ss", f"{max(0, k0 / fps - 1):.3f}", "-i", str(video), "-ss",
                          f"{k0 / fps - max(0, k0 / fps - 1):.3f}", "-frames:v", str(k1 - k0), "-vf",
                          f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8)
    return k0, a[:len(a) // (W * H) * W * H].reshape(-1, H, W).astype(np.int16)


def alternation(fr, box=None, back=8, same=0.12, moved=0.3):
    """Frames where the picture goes back to what it was a few frames before (A..B..A): [(i, j, d_prev)], frame i
    matching frame j (2 to `back` frames earlier, mean difference under `same`) while differing from frame i-1 by more
    than `moved`. box (x0, y0, x1, y1) in the arrays' px limits it to the field. Typing only moves forward (each letter
    adds); an autofill preview that comes and goes (Edge's saved "MM/dd/yyyy" between "MM" and "MM/d", two frames
    each, round 7 at 00:03:38) keeps going back; a blinking caret goes back about twice a second."""
    if box:
        fr = fr[:, box[1]:box[3], box[0]:box[2]]
    d = lambda a, b: float(np.mean(np.abs(fr[a] - fr[b])))
    out = []
    for i in range(2, len(fr)):
        dp = d(i, i - 1)
        if dp <= moved:
            continue
        j = next((j for j in range(i - 2, max(-1, i - back - 1), -1) if d(i, j) < same), None)
        if j is not None:
            out.append((i, j, round(dp, 2)))
    return out


def check_flicker(run, plan, scale=2):
    """R183: each typing step's footage that the edit shows, the field (where the typing changes the picture) frame by
    frame; three or more A-B-A flips fail, and a `drop` from type0 to type1 is proposed (as p2.39's)."""
    cal = json.loads((run / "calibration.json").read_text(encoding="utf-8"))
    tv = lambda t: cal["offset_s"] + cal["scale"] * t
    fps = plan["fps"]
    evs = [json.loads(l) for l in (run / "runlog.jsonl").read_text(encoding="utf-8").splitlines()[1:] if l.strip()]
    spans = {}
    for e in evs:
        if e.get("phase") in ("type_start", "type_end"):
            spans.setdefault(e["step_id"], {})[e["phase"]] = tv(e["t_mono"])
    out = []
    for sid, sp in spans.items():
        if "type_start" not in sp or "type_end" not in sp:
            continue
        s0, s1 = sp["type_start"] - 0.1, sp["type_end"] + 0.4
        shown = []                                    # the source frames the edit plays from this span
        for seg in plan["segments"]:
            if seg["type"] != "clip":
                continue
            a, b = max(s0, seg["src_in"]), min(s1, seg["src_out"])
            if b > a:
                shown.append((a, b, seg["t"] + (a - seg["src_in"]) / seg["speed"], seg["speed"]))
        if not shown:
            continue
        k0, fr = _gray_frames(run / plan["video"], s0, s1, fps, scale)
        if len(fr) < 4:
            continue
        ch = np.abs(np.diff(fr, axis=0)).max(axis=0) > 24     # where the typing changed anything: the field
        ys, xs = np.nonzero(ch)
        if not len(xs):
            continue
        box = (max(0, xs.min() - 2), max(0, ys.min() - 2), xs.max() + 3, ys.max() + 3)
        flips = [(k0 + i) / fps for i, *_ in alternation(fr, box)]
        seen = [f for f in flips if any(a <= f <= b for a, b, *_ in shown)]
        if len(seen) >= 3:
            a, b, t_e, speed = next(x for x in shown if x[0] <= seen[0] <= x[1])
            t = t_e + (seen[0] - a) / speed           # source seconds to edit seconds (typing may be sped up, R67)
            out.append(finding("flicker", "R183", t, f"{sid}: the typed field flickers ({len(seen)} returns to an "
                               f"earlier picture in "
                               f"{seen[-1] - seen[0] + 1 / fps:.2f} s of footage the edit shows); show it pasted: "
                               f"\"drop\": [{{\"from\": \"type0\", \"to\": \"type1\"}}] on the step",
                               step=sid, box_src=[int(v * scale) for v in box],
                               src_flips=[round(f, 3) for f in seen]))
    return out


# --------------------------------------------------------------------------------------- double breaths (R181)
def check_breaths(run, plan):
    from pipeline.narration import breaths as br
    pcs = br.placed(run, plan, CACHE)
    ws = br.placed_words(plan, CACHE)
    out = []
    for p in pcs:
        if p["pieces"] > 1 and p["piece"] == 0:
            out.append(finding("breaths", "R181", p["t0"], f"{p['step']}: a beat splits a breath ({p['src_t0']:.2f} to "
                               f"{p['src_t1']:.2f} s of its clip): part of it, a pause, then the rest", step=p["step"]))
    for a, b in br.doubles(pcs, ws):
        if a["line"] == b["line"] and a["breath"] == b["breath"]:
            continue                                  # the split breath above, already reported
        out.append(finding("breaths", "R181", a["t0"], f"two breaths {b['t0'] - a['t0']:.2f} s apart with no speech "
                           f"between ({a['step']} at {tc(a['t0'])}, {b['step']} at {tc(b['t0'])}): mute the first",
                           step=a["step"]))
    return out


# ------------------------------------------------------------------------- still checks (overlays: R179, R187)
def _ocr_image(png):
    from pipeline.edit import linecheck as lc
    tmp = Path(png).parent / f"_ocr_{Path(png).stem}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    shutil.copy2(png, tmp / "a.png")
    try:
        return lc.ocr(tmp).get("a.png", [])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ocr_many(pngs):
    """{png path: OCR words} for several images in one Windows OCR call."""
    from pipeline.edit import linecheck as lc
    pngs = [Path(p) for p in pngs]
    if not pngs:
        return {}
    tmp = pngs[0].parent / "_ocr_batch"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    try:
        for i, p in enumerate(pngs):
            shutil.copy2(p, tmp / f"{i:03d}.png")
        res = lc.ocr(tmp)
        return {str(p): res.get(f"{i:03d}.png", []) for i, p in enumerate(pngs)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def overlay_words(composite_png, alpha_png, words=None):
    """OCR words of the overlay's own text: on the composite, where the overlay layer is solid. words: the
    composite's OCR, if already read (ocr_many)."""
    from PIL import Image
    a = np.asarray(Image.open(alpha_png).convert("RGBA").getchannel("A"))
    out = []
    for w in (_ocr_image(composite_png) if words is None else words):
        x, y, ww, hh = (int(round(v)) for v in w[1:])
        if ww < 4 or hh < 4 or len(re.sub(r"\W", "", w[0])) < 2:   # a tick or a pin read as "V": a shape, not text
            continue
        cx, cy = min(a.shape[1] - 1, x + ww // 2), min(a.shape[0] - 1, y + hh // 2)
        if a[cy, cx] > 200:
            out.append(w)
    return out


def ink_and_ground(rgb, box):
    """The text's ink and what is right behind it in a word box: the pixels split by luminance (the larger group is the
    ground); the ink is the group's most extreme tenth (antialiased edges aside)."""
    x0, y0, x1, y1 = box
    px = rgb[y0:y1, x0:x1].reshape(-1, 3).astype(float)
    if len(px) < 20:
        return None
    lum = px @ np.array([0.2126, 0.7152, 0.0722])
    lo, hi = np.percentile(lum, 5), np.percentile(lum, 95)
    if hi - lo < 4:
        return None
    thr = (lo + hi) / 2
    dark, light = px[lum < thr], px[lum >= thr]
    ground, ink = (light, dark) if len(light) >= len(dark) else (dark, light)
    gl = ground @ np.array([0.2126, 0.7152, 0.0722])
    il = ink @ np.array([0.2126, 0.7152, 0.0722])
    g = tuple(np.median(ground, axis=0))
    k = ink[np.argsort(il)[: max(1, len(il) // 10)]] if np.median(il) < np.median(gl) else \
        ink[np.argsort(il)[-max(1, len(il) // 10):]]
    return tuple(np.median(k, axis=0)), g


def text_contrast(composite_png, alpha_png, t=None, label="", words=None):
    """R179: each word of the overlay's text at least 7:1 against what is right behind it, and nothing see-through
    behind it (the layer's alpha around the word fully opaque)."""
    from PIL import Image
    rgb = np.asarray(Image.open(composite_png).convert("RGB"))
    a = np.asarray(Image.open(alpha_png).convert("RGBA").getchannel("A"))
    out = []
    for w in overlay_words(composite_png, alpha_png, words):
        x, y, ww, hh = (int(round(v)) for v in w[1:])
        box = (max(0, x - 3), max(0, y - 3), min(rgb.shape[1], x + ww + 3), min(rgb.shape[0], y + hh + 3))
        r = ink_and_ground(rgb, box)
        if r:
            cr = ratio(r[0], r[1])
            if cr < MIN_RATIO:
                out.append(finding("contrast", "R179", t, f"{label}\"{w[0]}\" is {cr:.2f}:1 against what is behind it "
                                   f"(ink {'#%02x%02x%02x' % tuple(int(v) for v in r[0])} on "
                                   f"{'#%02x%02x%02x' % tuple(int(v) for v in r[1])}), under 7:1",
                                   word=w[0], ratio=round(cr, 2), box=list(box)))
        ring = a[box[1]:box[3], box[0]:box[2]]
        if ring.size and np.percentile(ring, 10) < 250:
            out.append(finding("contrast", "R179", t, f"{label}\"{w[0]}\" sits on a see-through background (the "
                               f"overlay's alpha behind it {int(np.percentile(ring, 10))} of 255)", word=w[0],
                               box=list(box)))
    return out


def see_through(alpha_png, t=None, label=""):
    """R179, R164: inside an overlay's solid body, no see-through part (a panel at 96%, a pipe left hollow). The body is
    the alpha's solid area filled in; its outer 6 px (antialiasing, the shadow) is left out."""
    from PIL import Image, ImageFilter
    im = Image.open(alpha_png).convert("RGBA").getchannel("A")
    solid = im.point(lambda v: 255 if v > 200 else 0)
    if not solid.getbbox():
        return []
    body = solid.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.MinFilter(15))   # close small holes
    inner = np.asarray(body.filter(ImageFilter.MinFilter(13))) > 0
    a = np.asarray(im)
    part = inner & (a > 8) & (a < 245)
    hollow = inner & (a <= 8)
    n = int(inner.sum())
    out = []
    if n and (part.sum() + hollow.sum()) / n > 0.005:
        ys, xs = np.nonzero(part | hollow)
        out.append(finding("see_through", "R179", t, f"{label}{(part.sum() + hollow.sum()) / n:.1%} of the overlay's "
                           f"body is see-through (alpha under 245), around x {int(np.median(xs))}, y {int(np.median(ys))}",
                           share=round(float((part.sum() + hollow.sum()) / n), 4)))
    return out


DESCENDS = set("gjpqyQJ,;()[]{}/@$|")                 # letters and marks that reach below the baseline


def _glyph_lines(gray, box, ink_dark, text=""):
    """A word's capital top, baseline and ink left edge (frame px), from its ink and its OCR text: the baseline is the
    lowest ink row, used only for a word with no descending letter or mark (None otherwise: "types" and "yyyy" reach
    below it); the capital top is the first ink row over its first letter (about the first 0.6 of the text height in
    width), used only when that letter is a capital (None otherwise); the left edge is the first ink
    column. A row of ink across the whole box (a rule, a box's edge) is left out first."""
    x0, y0, x1, y1 = box
    g = gray[y0:y1, x0:x1].astype(float)
    if g.size == 0:
        return None
    lo, hi = np.percentile(g, 5), np.percentile(g, 95)
    if hi - lo < 20:
        return None
    ink = g < (lo + hi) / 2 if ink_dark else g > (lo + hi) / 2
    ink[ink.mean(axis=1) > 0.8, :] = False
    rows, cols = ink.sum(axis=1), np.nonzero(ink.sum(axis=0))[0]
    filled = np.nonzero(rows >= 2)[0]
    if len(filled) < 3 or not len(cols):
        return None
    base = None if set(text) & DESCENDS else float(filled[-1] + y0)
    top = None
    if text[:1].isupper():                             # a capital (a digit can stand taller: Courier New's do)
        first = ink[:, cols[0]:cols[0] + max(3, int(0.6 * ink.shape[0]))]
        frows = np.nonzero(first.sum(axis=1) >= 2)[0]
        top = float(frows[0] + y0) if len(frows) else None
    return top, base, float(cols[0] + x0)


def alignment(composite_png, alpha_png, t=None, label="", tol=2.0, words=None):
    """R187, R176: per line of the overlay's text (words side by side, no wider apart than about their height), the
    baselines within tol px, and the capital tops of its capitalised words within tol + 1 px (two fonts or two sizes
    on one line: a lowercase word's top is its x-height, so it isn't compared); per column (three or more lines whose
    ink starts within 12 px), the left edges within tol px plus 8% of the text's height (letters' own side spaces)."""
    from PIL import Image
    gray = np.asarray(Image.open(composite_png).convert("L"))
    words = overlay_words(composite_png, alpha_png, words)
    meas = []
    for w in words:
        x, y, ww, hh = (int(round(v)) for v in w[1:])
        box = (max(0, x - 1), max(0, y - 1), min(gray.shape[1], x + ww + 1), min(gray.shape[0], y + hh + 1))
        g = gray[box[1]:box[3], box[0]:box[2]]
        dark = float(np.median(g)) > 128             # light ground: dark ink
        r = _glyph_lines(gray, box, dark, w[0])
        if r:
            meas.append({"w": w[0], "x": x, "y": y, "h": hh, "w_px": ww, "top": r[0], "base": r[1], "left": r[2]})
    bands = []                                        # words whose middles are level
    for m in sorted(meas, key=lambda m: m["y"] + m["h"] / 2):
        band = next((r for r in bands if abs((r[0]["y"] + r[0]["h"] / 2) - (m["y"] + m["h"] / 2)) < 0.5 * min(
            r[0]["h"], m["h"])), None)
        (band.append(m) if band is not None else bands.append([m]))
    rows = []                                         # split a band where words stand far apart (separate elements)
    for band in bands:
        band.sort(key=lambda m: m["x"])
        cur = [band[0]]
        for m in band[1:]:
            prev = cur[-1]
            if m["x"] - (prev["x"] + prev["w_px"]) > 2.5 * max(prev["h"], m["h"]):
                rows.append(cur)
                cur = []
            cur.append(m)
        rows.append(cur)
    out = []
    for r in rows:
        if len(r) < 2:
            continue
        based = [m for m in r if m["base"] is not None]
        bases = [m["base"] for m in based] or [0.0]
        caps = [m for m in r if m["top"] is not None]
        if max(bases) - min(bases) > tol:
            lo, hi = min(based, key=lambda m: m["base"]), max(based, key=lambda m: m["base"])
            out.append(finding("alignment", "R187", t, f"{label}row \"{' '.join(m['w'] for m in r)[:50]}\": baselines "
                               f"differ by {max(bases) - min(bases):.0f} px (\"{hi['w']}\" sits lower than "
                               f"\"{lo['w']}\")", spread=round(max(bases) - min(bases), 1)))
        elif len(caps) >= 2 and max(m["top"] for m in caps) - min(m["top"] for m in caps) > tol + 1:
            tops = [m["top"] for m in caps]
            out.append(finding("alignment", "R187", t, f"{label}row \"{' '.join(m['w'] for m in r)[:50]}\": capital "
                               f"tops differ by {max(tops) - min(tops):.0f} px (two sizes or fonts on one line)",
                               spread=round(max(tops) - min(tops), 1)))
    firsts = [r[0] for r in rows]
    cols = []
    for f in sorted(firsts, key=lambda m: m["left"]):
        col = next((c for c in cols if abs(c[0]["left"] - f["left"]) <= 12), None)
        (col.append(f) if col is not None else cols.append([f]))
    for c in cols:
        spread = max(m["left"] for m in c) - min(m["left"] for m in c)
        if len(c) >= 3 and spread > tol + 0.08 * max(m["h"] for m in c):
            out.append(finding("alignment", "R187", t, f"{label}a column's left edges differ by {spread:.0f} px ("
                               + ", ".join(m["w"] for m in c[:4]) + ")", spread=round(spread, 1)))
    return out


# --------------------------------------------------------------------------------------- display time (R185)
EXIT_S = {"chapter_card": 0.6, "term_chip": 0.3, "choice_panel": 0.4, "word_build": 0.5, "map_pins": 0.5,
          "region_map": 0.5, "mini_diagram": 0.5, "checklist": 1.0, "aside": 0.5, "flip_card": 0.3,
          "calendar_flip": 0.4, "source_flow": 0.5}


def reading_s(text, base=2.0, per_word=0.3, free_words=5):
    """R185: how long an overlay's last part stays before its exit: 2 s, plus 0.3 s a word past five."""
    n = len(re.findall(r"[\w$%.,'-]+", text or ""))
    return base + per_word * max(0, n - free_words)


def last_part(ly):
    """(time, text) of what an overlay reveals last: its last item, or a timed prop (<name>_at), else its start."""
    cands = [(it["at"], it.get("text", "")) for it in ly.get("items", [])]
    cands += [(v, str(ly.get(k[:-3]) or "")) for k, v in ly.items() if k.endswith("_at") and isinstance(v, (int, float))]
    return max(cands, key=lambda c: c[0]) if cands else (ly["t0"], ly.get("title", "") or "")


def exit_of(ly):
    return ly["exit_s"] if ly.get("exit_s") is not None else EXIT_S.get(ly.get("layout"), 0.5)


def display_time(layers, label_of=lambda ly: ly["id"]):
    """R185 as a check: each overlay's last part up for its reading time before its exit begins."""
    out = []
    for ly in layers:
        t, text = last_part(ly)
        need = reading_s(text)
        up = ly["t1"] - exit_of(ly) - t
        if up < need - 0.05:
            out.append(finding("display_time", "R185", t, f"{label_of(ly)}: its last part (\"{text[:30]}\") is up "
                               f"{max(0.0, up):.1f} s before its exit; it needs {need:.1f} s", id=ly["id"]))
    return out


def _not_before(ly):
    """A layer whose start moved later: its items and timed props (<name>_at) no earlier than its new start."""
    for it in ly.get("items", []):
        it["at"] = round(max(it["at"], ly["t0"]), 4)
    for k in [k for k, v in ly.items() if k.endswith("_at") and isinstance(v, (int, float))]:
        ly[k] = round(max(ly[k], ly["t0"]), 4)


def hold_for_reading(layers, max_push_s=1.0):
    """R185 applied: each layer's end moved so its last part stays its reading time; where that runs into the next
    layer on the same track, the next one waits up to max_push_s past its word; past that both are flagged. Changes the
    layers in place; returns notes (flags start with "R185 flag")."""
    notes = []
    order = sorted(layers, key=lambda ly: ly["t0"])
    for a, b in zip(order, order[1:] + [None]):
        t, text = last_part(a)
        want = round(t + reading_s(text) + exit_of(a), 4)
        if a["t1"] >= want:
            continue
        notes.append(f"{a['id']}: held {want - a['t1']:.2f} s longer, so its last part stays {reading_s(text):.1f} s "
                     "(R185)")
        before = a["t1"]
        a["t1"] = want
        if b is not None and b["t0"] < a["t1"]:
            push = a["t1"] - b["t0"]
            if push <= max_push_s:
                b["t0"] = round(b["t0"] + push, 4)
                _not_before(b)
                notes.append(f"{b['id']}: waits {push:.2f} s for {a['id']} (R185)")
            else:                                     # the next waits the most it may; this one holds until then,
                b["t0"] = round(b["t0"] + max_push_s, 4)   # never over it; both flagged with the shortfall
                _not_before(b)
                short = a["t1"] - b["t0"]
                a["t1"] = max(before, b["t0"])        # never shorter than it was (an overlap by design stays)
                notes.append(f"R185 flag: {a['id']} needs {push:.2f} s of {b['id']}'s time (more than "
                             f"{max_push_s:.0f} s): {b['id']} waits {max_push_s:.0f} s and {a['id']}'s last part is up "
                             f"{short:.2f} s short; both flagged")
    return notes


# ------------------------------------------------------------------------------------------------ the report
def run_edit(run_dir, plan_path=None, only=None, second_reader=True):
    run = Path(run_dir).resolve()
    pp = Path(plan_path) if plan_path else run / "edit_plan.json"
    plan = json.loads(pp.read_text(encoding="utf-8"))
    out_dir = pp.parent / "checks"
    out_dir.mkdir(exist_ok=True)
    want = set(only or ["tokens", "named", "captions", "flicker", "breaths"])
    found, named_boxes, second = [], [], {}
    if "tokens" in want:
        caps = plan["settings"]["captions"]
        found += check_tokens(captions={"stills": caps.get("stills") or {}, "burned": {
            "text_color": "#FFFFFF", "box_color": caps.get("box_color")},
            "titles": {"text_color": "#FFFFFF", "box_color": (caps.get("titles") or {}).get("box_color")}})
    if "named" in want or "captions" in want:
        nf, named_boxes = check_named(run, plan, out_dir, second_reader=second_reader, stats=second)
        if "named" in want:
            found += nf
    if "captions" in want:
        found += check_captions(plan, named_boxes)
    if "flicker" in want:
        found += check_flicker(run, plan)
    if "breaths" in want:
        found += check_breaths(run, plan)
    if plan.get("overlays"):
        found += display_time([o for o in plan["overlays"] if o.get("plan_overlay")])
    found.sort(key=lambda f: (f["t"] is None, f["t"] or 0))
    (out_dir / "findings.json").write_text(json.dumps(found, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Measured checks: {plan['run_id']} ({pp.parent.name})", "",
             "R179 to R187 (`D:\\Videos\\Global Assets\\VIDEO_RULES.md`, \"The checks\"). Times are timecodes on the "
             "full sequence.", ""]
    for name in ("tokens", "named", "captions", "flicker", "breaths", "display_time"):
        fs = [f for f in found if f["check"] == name]
        if name in want or fs:
            lines += [f"## {name} ({len(fs)})", ""] + [f"- {f['tc'] or '(no time)'} {f['rule']}: {f['what']}"
                                                         for f in fs] + (["- none"] if not fs else []) + [""]
            if name == "named" and second:            # R227: what the second reader did
                lines += [f"Second reader (RapidOCR, R227): {second.get('frames', 0)} frame(s) Windows OCR missed "
                          "on read again" + (f"; {second['note']}" if second.get("note") else "") + ".", ""]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return found, out_dir


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {a.split("=", 1)[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    f, d = run_edit(args[0], opt.get("plan"), opt["only"].split(",") if "only" in opt else None,
                    second_reader="--no-second-reader" not in sys.argv)
    print(f"{len(f)} finding(s); report: {d / 'report.md'}")
    for x in f:
        print(f" - {x['tc'] or '-'} {x['rule']} {x['check']}: {x['what']}")
