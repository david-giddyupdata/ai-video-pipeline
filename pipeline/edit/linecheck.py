"""The line check (R85): every narration line against the screen at its moments, before an export round.

    python -m pipeline.edit.linecheck runs/<run_id> [--no-stills] [--no-second-reader]

Each of David's round-2 notes on s7_take06 maps to one check (docs/S7_R2_REVIEW.md). Writes runs/<run_id>/linecheck/:

  report.md     the findings, then a table per line: each sentence with the words it names that are not readable on
                screen while it is spoken (R75, R81), overlay items beside their sentences (R80), sentence-end pauses
                (R31), silences over a still picture (R25, R82), caption overlaps, the cursor in live steps (R47),
                em dashes in any text the plan shows (R93)
  marks/        every mark cropped at full resolution with its box drawn (R84): does it frame the whole thing?
  sheets/       EditPass stills (what the viewer sees, captions on) at each line's first word, each mark, each overlay
                item and each transition, six to a sheet with the line beside each, for Claude to read through

On screen: the source frame cropped to the camera's view at that moment, OCR'd with Windows OCR, less what an overlay
card covers, plus the card's own text and a title card's. Content words of four or more letters (no stop words) count
as readable when an OCR word matches them closely. R227: a named word (a label, a quoted word, an interface term)
Windows OCR didn't read is looked for again by RapidOCR (pipeline.ml.ocr.second_read) on those frames only, never
instead of Windows OCR; what only RapidOCR read is listed in its own table (--no-second-reader, or the exercise's
edit_settings.json "checks": {"second_reader": false}, turns it off). The check advises: Claude reads the report and the sheets, fixes
what is wrong, and lists what it can't settle as questions for David with the round.
"""
import difflib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.config import ROOT, tool
from pipeline.edit import activity, sentences
from pipeline.edit import marks as mk
from pipeline.edit.camera import cam_at
from pipeline.ml import ocr as ml_ocr
from pipeline.narration import timing
from pipeline.narration.build import r93

CACHE = ROOT / "audio_cache"
REMOTION = ROOT / "remotion"
STOP = set("""about above after again against also among another because been before being below between both but
could does doing down during each even every from further have having here into itself just like made make many
more most much must near only other over same should since some such than that their them then there these they
this those through under until upon very what when where which while will with within without would your yours
it's isn't don't we'll i'll you'll that's what's here's there's let's we're you're they're won't can't doesn't
didn't each else ever first last next once still them they'll time way well were whose case""".split())


def src_at(plan, t):
    """Source time and segment at edit time t."""
    seg = plan["segments"][0]
    for s in plan["segments"]:
        if s["t"] <= t:
            seg = s
    return (seg["src_t"] if seg["type"] == "hold" else seg["src_in"] + (t - seg["t"]) * seg["speed"]), seg


def shown_change(plan, act, fps, t):
    """The picture change (activity %) in the frame the viewer sees at edit time t: none in a freeze."""
    s, seg = src_at(plan, t)
    if seg["type"] == "hold":
        return 0.0
    i = int(round(s * fps))
    return float(act[i]) if 0 <= i < len(act) else 0.0


def frames(run, plan, times, out):
    """Source frames at edit times, cropped to the camera's view and scaled to the output size: what the viewer sees
    of the recording (without the edit's layers)."""
    from PIL import Image
    W, H = plan["width"], plan["height"]
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, t in enumerate(times):
        p = out / f"f{i:04d}_{t:08.3f}.png"
        if not p.exists():
            s, _ = src_at(plan, t)
            raw = out / "_raw.png"
            subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{s:.3f}", "-i", str(run / plan["video"]),
                            "-frames:v", "1", str(raw)], check=True)
            k, cx, cy = cam_at(plan["camera"], t, W, H)
            box = (cx - W / 2 / k, cy - H / 2 / k, cx + W / 2 / k, cy + H / 2 / k)
            Image.open(raw).crop(tuple(round(v) for v in box)).resize((W, H)).save(p)
        paths.append(p)
    return paths


def ocr(folder):
    """{file name: [(text, x, y, w, h)]} for every image in the folder (Windows OCR, one PowerShell call)."""
    res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(ROOT / "pipeline" / "privacy" / "winocr.ps1"), str(folder)],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    out = {}
    for rec in (json.loads(l) for l in res.splitlines() if l.strip().startswith("{")):
        out[rec["file"]] = [(w["t"], w["x"], w["y"], w["w"], w["h"]) for ln in rec["lines"] for w in ln["words"]]
    return out


def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def content_words(text):
    return [w for w in dict.fromkeys(re.findall(r"[A-Za-z0-9][A-Za-z0-9'.,-]*[A-Za-z0-9]", text))
            if len(norm(w)) >= 4 and w.lower() not in STOP and not re.fullmatch(r"[\d,.]+", w) or re.fullmatch(r"\d{3,}", w)]


def readable(word, seen):
    """A content word is readable when an OCR word (or two joined) matches it closely."""
    n = norm(word)
    if any(n in s or (len(s) >= 4 and s in n and len(s) >= len(n) - 2) for s in seen):
        return True
    return any(difflib.SequenceMatcher(None, n, s).ratio() >= 0.8 for s in seen)


def check(run_dir, stills=True, second_reader=True):
    """second_reader False (--no-second-reader), or the plan's settings "checks": {"second_reader": false}: Windows
    OCR alone, as before R227."""
    from pipeline.edit import checks as ck
    run = Path(run_dir).resolve()
    plan = json.loads((run / "edit_plan.json").read_text(encoding="utf-8"))
    W, H, fps = plan["width"], plan["height"], plan["fps"]
    st = plan["settings"]
    with (run / "runlog.jsonl").open(encoding="utf-8") as f:   # the run's own exercise: two exercises have a
        ex = json.loads(f.readline()).get("exercise", "")       # steps_full.json, and a glob found the other one
    sp = ROOT / "exercises" / ex / plan["steps_file"]
    sp = sp if sp.exists() else next(ROOT.glob(f"exercises/*/{plan['steps_file']}"))
    doc = json.loads(sp.read_text(encoding="utf-8"))
    voice = json.loads((sp.parent / doc.get("voice_file", "voice.json")).read_text(encoding="utf-8"))   # as the build
    steps = doc["steps"]
    by_id = {s["id"]: s for s in steps}
    out = run / "linecheck"
    shutil.rmtree(out, ignore_errors=True)            # (a sheet open in a viewer can't be removed; it is replaced)
    out.mkdir(exist_ok=True)
    findings, rows = [], []
    metas = {n["line_id"]: timing.of(n) for n in plan["narration"]}     # R227: the times each line was built with

    def at(n, o):                                     # audio offset in a line -> edit time
        return next((p["at"] + o - p["in"] for p in reversed(n["parts"]) if p["in"] <= o + 1e-6), n["start"] + o)

    # sentences and the moments to look at: each sentence's first and last word
    sents = []
    for n in plan["narration"]:
        m = metas[n["line_id"]]
        ws, text = m["words"], m["display_text"]
        cuts = [b["after"] for b in sentences.breaks(text, ws)] + [len(ws) - 1]
        a = 0
        for z in cuts:
            sents.append({"line": n["line_id"], "step": n["step"], "text": text[ws[a]["char"][0]:ws[z]["char"][1] + 1].strip(),
                          "t0": at(n, ws[a]["start"]) + 0.15, "t1": at(n, ws[z]["start"]) + 0.15})
            a = z + 1
    times = sorted({round(t, 2) for s in sents for t in (s["t0"], s["t1"])})
    fdir = out / "frames"
    paths = frames(run, plan, times, fdir)
    words = ocr(fdir)

    def visible(t, ws):
        """The normalised words the viewer can read at t: the frame's OCR words less what an overlay card covers,
        plus the card's own text (a title card covers the frame), and adjacent pairs joined."""
        cards = [mk.overlay_box(o["edge"], W, H) for o in plan.get("overlays") or [] if o["t0"] <= t <= o["t1"]]
        vis = [norm(w[0]) for w in ws
               if not any(c[0] <= w[1] + w[3] / 2 <= c[2] and c[1] <= w[2] + w[4] / 2 <= c[3] for c in cards)]
        for o in plan.get("overlays") or []:            # the card's own text, as far as it is up
            if o["t0"] <= t <= o["t1"]:
                vis += [norm(x) for x in (o.get("title", "") + " " + o.get("text", "")).split()]
                vis += [norm(x) for it in o["items"] if it["at"] <= t for x in it["text"].split()]
        _, seg = src_at(plan, t)
        if seg.get("card"):                              # a title card covers the frame
            vis = [norm(x) for x in (seg["card"]["title"] + " " + seg["card"].get("sub", "")).split()]
        seen = {v for v in vis if v}
        for i in range(len(vis) - 1):                   # OCR splits "CLAUDE. md": joined pairs count too
            seen.add(vis[i] + vis[i + 1])
        return seen

    seen_at = {t: visible(t, words.get(p.name, [])) for t, p in zip(times, paths)}
    for s in sents:
        seen = seen_at[round(s["t0"], 2)] | seen_at[round(s["t1"], 2)]
        cw = content_words(s["text"])
        s["missing"] = [w for w in cw if not readable(w, seen)]
        s["found"] = [w for w in cw if w not in s["missing"]]
    # R227: a named word (a label, a quoted word, an interface term) Windows OCR didn't read is looked for again by
    # RapidOCR, on those frames only; what only it reads is listed as such, since it can invent a number or a word
    on = second_reader and (st.get("checks") or {}).get("second_reader", True)
    second = {"frames": 0, "words": 0, "note": None if on else "off: --no-second-reader or the settings"}
    if on:
        named = {}
        nar = {n["line_id"]: n for n in plan["narration"]}
        for s in sents:
            labels = ((by_id.get(nar[s["line"]]["step"]) or {}).get("narration") or {}).get("labels") or []
            toks = {norm(x) for term in ck.line_terms(metas[s["line"]]["display_text"], labels) for x in term.split()}
            named[id(s)] = [w for w in s["missing"] if norm(w) in toks]
        again = sorted({round(t, 2) for s in sents if named[id(s)] for t in (s["t0"], s["t1"])})
        if again:
            path_at = dict(zip(times, paths))
            try:
                read2 = ml_ocr.second_read([path_at[t] for t in again])
            except Exception as e:                               # the venv or the GPU unavailable: Windows OCR's
                read2 = None                                     # results stand, and the report says so
                second["note"] = f"not run: {type(e).__name__}: {str(e)[-200:]}"
            if read2 is not None:
                second["frames"] = len(again)
                seen2 = {t: visible(t, ml_ocr.words_of(read2[str(Path(path_at[t]).resolve())])) for t in again}
                for s in sents:
                    if not named[id(s)]:
                        continue
                    both = seen_at[round(s["t0"], 2)] | seen_at[round(s["t1"], 2)]
                    both |= seen2.get(round(s["t0"], 2), set()) | seen2.get(round(s["t1"], 2), set())
                    s["second"] = [w for w in named[id(s)] if readable(w, both)]
                    s["missing"] = [w for w in s["missing"] if w not in s["second"]]
                    s["found"] += s["second"]
                    second["words"] += len(s["second"])

    # R80: overlay items beside their sentences
    items = []
    for o in plan.get("overlays") or []:
        for k, it in enumerate(o["items"]):
            s = next((x for x in sents if x["t0"] - 0.4 <= it["at"] <= x["t1"] + 1.0), None)
            label = it["text"].split(":")[0]
            shared = [w for w in content_words(label) if s and readable(w, {norm(x) for x in s["text"].split()})]
            items.append({"overlay": o["id"], "item": k + 1, "text": it["text"], "at": it["at"],
                          "sentence": s["text"] if s else None, "label_in_sentence": bool(shared)})
            if not shared:
                findings.append(f"R80: overlay {o['id']} item {k + 1} \"{label}\" is not what its sentence is about: "
                                f"\"{s['text'] if s else '?'}\"")

    # R31: every sentence end is heard
    for n in plan["narration"]:
        m = metas[n["line_id"]]
        floor = timing.pause_min(voice, n.get("words_from"))   # each source's own floor, as the build (R227)
        for b in sentences.breaks(m["display_text"], m["words"]):
            if b["pause_s"] < floor:
                findings.append(f"R31: {n['line_id']} runs on at \"{b['before_text'][-30:]}\" ({b['pause_s']:.3f} s pause)")

    # R25, R82: silences over a still picture beyond what the rules allow
    pace, act = st["pacing"], activity.load(run, plan["video"])
    silences = []
    for n1, n2 in zip(plan["narration"], plan["narration"][1:]):
        end = n1["parts"][-1]["at"] + n1["parts"][-1]["out"] - n1["parts"][-1]["in"]
        p1, p2 = (by_id.get(n1["step"]) or {}).get("part"), (by_id.get(n2["step"]) or {}).get("part")
        allow = pace["gap_between_lines"] + (pace["pause_at_part_boundary"] if p1 != p2 else 0.0)
        gap = n2["start"] - end
        if gap > allow + 0.1:
            # what the viewer sees in the gap, frame by frame (a cut's skipped footage isn't seen; a freeze is still);
            # as the planner's quiet_until, the silence may run on a gap after the picture last changed (R25)
            seen = [(t, shown_change(plan, act, fps, t)) for t in
                    [end + k / fps for k in range(int((n2["start"] - end) * fps) + 1)]]
            moving = [t for t, v in seen if v >= pace["activity_min_pct"]]
            if moving:
                allow = max(allow, min(moving[-1] - end + max(pace["gap_between_lines"], pace["pause_after_result"]),
                                       pace["max_silence_s"]))
            still = gap > allow + 0.1 and not [t for t in moving if t > end + allow]
            silences.append({"between": [n1["step"], n2["step"]], "gap": round(gap, 2), "allow": round(allow, 2),
                             "still": still, "at": round(end, 2)})
            if still:
                findings.append(f"R25: {gap:.2f} s of silence at {end:.2f} s ({n1['step']} -> {n2['step']}), "
                                f"{gap - allow:.2f} s over the {allow:.2f} s allowed, over a still picture")
            elif gap > pace["max_silence_s"] + (pace["pause_at_part_boundary"] if p1 != p2 else 0.0) + 0.05:
                # 2 s is a ceiling, moving picture or not (sped-up typing too: David, csc13 test, 2026-10-12)
                findings.append(f"R25: {gap:.2f} s of silence at {end:.2f} s ({n1['step']} -> {n2['step']}), over the "
                                f"{pace['max_silence_s']:.1f} s ceiling; close it with narration")

    # captions never overlap; the cursor is hidden in live steps (R47)
    cues = plan["captions"]["cues"]
    for c0, c1 in zip(cues, cues[1:]):
        if c0["end"] > c1["start"] + 1e-3:
            findings.append(f"captions overlap at {c1['start']:.2f} s: \"{c0['text'][:30]}\" / \"{c1['text'][:30]}\"")
    hidden = plan["cursor"].get("hidden", [])
    gestures = [(m["t0"] - 0.3, m["t1"] + (2.0 if m.get("gesture") == "approve" else 0.5))   # the planner shows
                for m in plan["cursor"]["moves"]                    # an approval's cursor until 1.5 s after the click
                if m.get("gesture") in ("approach", "rect", "arrow", "retreat", "approve")]
    for n in plan["narration"]:
        stp = by_id.get(n["step"]) or {}
        if stp.get("segment") == "live" and (stp.get("action") or {}).get("type") in ("scroll", "none", "wait_claude"):
            shown = [t for t in (n["start"] + n["length"] * k for k in (0.25, 0.5, 0.75))
                     if not any(a <= t <= b for a, b in hidden) and not any(a <= t <= b for a, b in gestures)]
            if shown:
                findings.append(f"R47: the cursor shows during live step {n['step']} at {shown[0]:.1f} s "
                                "(not drawing a mark)")

    # R93: no em dash in anything the viewer reads (captions, overlays, cards, titles)
    def texts(o, at=""):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from texts(v, f"{at}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from texts(v, f"{at}[{i}]")
        elif isinstance(o, str) and " " in o:            # words, not ids or paths
            yield at, o
    for at, t in texts(plan):
        for i, w in r93(t):
            findings.append(f"R93: {w!r} in {at.lstrip('.')}: \"{t[max(0, i - 30):i + 30]}\"")

    # R123: what a line refers to sits inside title-safe, whole
    findings += framing(plan)

    # R84: every mark cropped at full resolution, with its box
    mark_rows = mark_crops(run, plan, out / "marks")

    # what the viewer sees, for reading through: EditPass stills
    shots = []
    if stills:
        shots = sheets(run, plan, sents, out / "sheets")

    # R179 to R187: the measured checks (pipeline.edit.checks), in the same report
    measured, _ = ck.run_edit(run, second_reader=second_reader)
    findings += [f"{f['rule']}: {f['what']}" + (f" at {f['t']:.2f} s ({f['tc']})" if f["t"] is not None else "")
                 for f in measured if not f["rule"].endswith((" repeat", " waived", " small", " second reader"))]
                 # those are listed in checks/report.md, not made into markers (R198's small text: 1.35x puts Quick
                 # Sight's at 12-13 px; R227's terms pointed out only as RapidOCR reads them)

    write_report(out / "report.md", plan, findings, sents, items, silences, mark_rows, shots, second)
    (out / "findings.json").write_text(json.dumps([   # R106: the export puts a marker at each timed finding
        {"rule": f.split(":", 1)[0].split(" ")[0],
         "t": None if f.startswith(("R31", "R80", "R93"))      # these quote narration: a time in it isn't theirs
         else float(m.group(1)) if (m := re.search(r" at (\d+(?:\.\d+)?) s\b", f)) else None,
         "text": f} for f in findings], indent=1), encoding="utf-8")
    return findings, out


def framing(plan):
    """R123: each mark (drawn, and as it starts to fade), each click target at its click and each whole dialog (as it
    appears, and before it closes) inside the title-safe area of the view (zoom.safe_px, output px). A side where the
    view already stops at the screen's own edge can't have the margin, and isn't flagged. Runs only with safe_px."""
    z = plan["settings"]["zoom"]
    if not z.get("safe_px"):
        return []
    W, H, keys = plan["width"], plan["height"], plan["camera"]
    sp, stroke = z["safe_px"], plan["marks"]["style"].get("stroke_px", 5)
    targets = {}
    for e in plan.get("click_targets") or []:
        targets[e["step"]] = e["box"]
    out, seen = [], set()

    def test(what, step, t, b, margins=None):
        m_ = margins or sp
        s, x, y = cam_at(keys, t, W, H)
        v0x, v0y, v1x, v1y = x - W / (2 * s), y - H / (2 * s), x + W / (2 * s), y + H / (2 * s)
        gaps = {"left": ((b[0] - v0x) * s, m_["left"], v0x > 0.5), "top": ((b[1] - v0y) * s, m_["top"], v0y > 0.5),
                "right": ((v1x - b[2]) * s, m_["right"], v1x < W - 0.5),
                "bottom": ((v1y - b[3]) * s, m_["bottom"], v1y < H - 0.5)}
        bad = [(side, g, m) for side, (g, m, movable) in gaps.items() if g < m - 2 and movable]
        if bad and (step, what) not in seen:
            seen.add((step, what))
            side, g, m = min(bad, key=lambda x: x[1] - x[2])
            out.append(f"R123: {what} ({step}) at {t:.2f} s " + (f"is cut off at the {side} of the view ({-g:.0f} px out)"
                       if g < 0 else f"sits {g:.0f} px from the {side} of the view (title-safe {m} px)"))

    box_of = lambda p: (min(p["from"]["x"], p["to"]["x"]) - stroke, min(p["from"]["y"], p["to"]["y"]) - stroke,
                        max(p["from"]["x"], p["to"]["x"]) + stroke, max(p["from"]["y"], p["to"]["y"]) + stroke)
    # R125: inside a dialog framed at its own size (the Open dialog), its edge is the frame's edge, so marks and
    # click targets there (the Open button at its bottom right) can't have the title-safe margin either; only the
    # pad may fall outside. Captions keep off them (R53).
    loose = {"left": -8, "top": -8, "right": -8, "bottom": -8}
    owns = [(w["t0"], w["t1"]) for w in plan.get("wholes") or [] if w.get("framed", True) and w.get("fit") == "own"]
    in_own = lambda t: any(a <= t <= b for a, b in owns)
    for ly in plan["marks"]["layers"]:
        if ly.get("path"):                                # an overview arrow: each stop as it rests there
            for k in ly["path"]:
                test(f"the {ly['kind']} mark", ly["step"], max(k["t"], ly["draw1"]), box_of(k))
            continue
        for t in (ly["draw1"], ly["fade0"] - 0.05):      # a highlighted region (R142) may be a pane at the frame's
            test(f"the {ly['kind']} mark", ly["step"], t, box_of(ly),          # edge: in view is enough
                 margins=loose if in_own(t) or ly["kind"] == "highlight" else None)
    for c in plan["cursor"]["clicks"]:
        if c["step"] in targets:
            test("the click target", c["step"], c["t"], targets[c["step"]], margins=loose if in_own(c["t"]) else None)
    for w in plan.get("wholes") or []:
        if not w.get("framed", True):                     # a panned dialog (R125) isn't framed whole: nothing to test
            continue
        own = w.get("fit") == "own"                       # framed at its own size: its edge may be the frame's edge
        for t in (w["t0"] + z.get("ramp_s", 0.6), w["t1"] - 0.05):
            test("what it opened, whole" + (" (at its own size)" if own else ""), w["step"], max(w["t0"], t),
                 w["box"], margins=loose if own else None)
    return out


def mark_crops(run, plan, out):
    from PIL import Image, ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    color = plan["marks"]["style"].get("color", "#F16F05")
    for i, m in enumerate(plan["marks"]["layers"]):
        t = m["draw1"] + 0.3
        s, _ = src_at(plan, t)
        raw = out / "_raw.png"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{s:.3f}", "-i", str(run / plan["video"]),
                        "-frames:v", "1", str(raw)], check=True)
        im = Image.open(raw).convert("RGB")
        a, c = m["from"], m["to"]
        x0, y0, x1, y1 = min(a["x"], c["x"]), min(a["y"], c["y"]), max(a["x"], c["x"]), max(a["y"], c["y"])
        d = ImageDraw.Draw(im)
        if m["kind"] in ("rect", "highlight"):
            d.rectangle([x0, y0, x1, y1], outline=color, width=3)
        else:
            d.line([a["x"], a["y"], c["x"], c["y"]], fill=color, width=4)
        pad = 70
        box = (max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad))
        crop = im.crop(tuple(round(v) for v in box))
        crop = crop.resize((crop.width * 2, crop.height * 2))
        p = out / f"mark_{i:02d}_{m['step']}_{m['kind']}.png"
        crop.save(p)
        rows.append({"i": i, "step": m["step"], "kind": m["kind"], "t": round(m["draw0"], 2), "file": p.name})
    (out / "_raw.png").unlink(missing_ok=True)
    return rows


def sheets(run, plan, sents, out):
    """EditPass stills at the moments that matter, six to a sheet with the words being spoken."""
    from PIL import Image, ImageDraw, ImageFont
    out.mkdir(parents=True, exist_ok=True)
    fps = plan["fps"]
    want = []
    for n in plan["narration"]:
        want.append((n["start"] + 0.3, f"{n['step']} starts"))
    for m in plan["marks"]["layers"]:
        want.append((m["draw1"] + 0.2, f"{m['step']} {m['kind']} mark"))
    for o in plan.get("overlays") or []:
        for k, it in enumerate(o["items"]):
            want.append((it["at"] + 0.6, f"{o['id']} item {k + 1}"))
        for h in o.get("highlights") or []:
            want.append((h["draw1"] + 0.2, f"{o['id']} highlight"))
    for tr in plan.get("transitions") or []:
        want.append((tr["t"] - 0.2, f"{tr['type']} (before the cut)"))
        want.append((tr["t"] + 0.2, f"{tr['type']} (after the cut)"))
    want.sort()
    jobs = [{"frame": max(0, min(plan["durationInFrames"] - 1, round(t * fps))), "t": t, "why": why} for t, why in want]
    for i, j in enumerate(jobs):
        j["out"] = f"s{i:03d}_{j['frame']:06d}.png"
    # one bundle for every still (remotion/scripts/stills.mjs), its public dir the media EditPass uses, hard-linked
    pub = out.parent / "_public"
    shutil.rmtree(pub, ignore_errors=True)
    from pipeline.edit.plan import plan_media
    for rel in plan_media(plan):                          # R137's click, R173's correction plates included
        src, dst = run / rel, pub / rel
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                dst.hardlink_to(src)
            except OSError:
                shutil.copy2(src, dst)
    (out / "_jobs.json").write_text(json.dumps([{"frame": j["frame"], "out": j["out"]} for j in jobs]), encoding="utf-8")
    subprocess.run(["node", "scripts/stills.mjs", str(run / "edit_plan.json"), str(pub), str(out), str(out / "_jobs.json"),
                    "0.5"], cwd=REMOTION, check=True, capture_output=True)
    shutil.rmtree(pub, ignore_errors=True)
    shots = []
    for j in jobs:
        s = next((x for x in sents if x["t0"] - 0.6 <= j["t"] <= x["t1"] + 1.2), None)
        shots.append({"t": round(j["t"], 2), "why": j["why"], "file": out / j["out"], "said": s["text"] if s else ""})
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for k in range(0, len(shots), 6):
        group = shots[k:k + 6]
        sheet = Image.new("RGB", (2 * 960 + 30, 3 * (540 + 70) + 10), "white")
        d = ImageDraw.Draw(sheet)
        for j, sh in enumerate(group):
            x, y = 10 + (j % 2) * 970, 10 + (j // 2) * 610
            sheet.paste(Image.open(sh["file"]).convert("RGB").resize((960, 540)), (x, y))
            label = f"{sh['t']:.2f} s  {sh['why']}:  {sh['said']}"
            lines = [label[i:i + 105] for i in range(0, len(label), 105)][:3]
            for li, ln in enumerate(lines):
                d.text((x, y + 545 + li * 20), ln, fill="black", font=font)
        sheet.save(out / f"sheet_{k // 6 + 1:02d}.png")
    return shots


def write_report(path, plan, findings, sents, items, silences, marks, shots, second=None):
    L = [f"# Line check: {plan['run_id']} ({plan['duration_s']:.1f} s)", "",
         "R85. Advisory: Claude reads this and the sheets, fixes what is wrong, and asks David about the rest.", "",
         "## Findings", ""]
    L += [f"- {f}" for f in findings] or ["- none"]
    L += ["", "## Sentences: named words not readable on screen while spoken (R75, R81)", "",
          "Each entry is a judgment call: a word the line presents as on screen must be readable; words about ideas "
          "need not be.", "", "| t | step | sentence | not on screen |", "|---|---|---|---|"]
    for s in sents:
        if s["missing"]:
            L.append(f"| {s['t0']:.1f} | {s['step']} | {s['text'][:110]} | {', '.join(s['missing'])} |")
    second = second or {}
    L += ["", "## Read by RapidOCR alone (R227, the second reader)", "",
          "Named words (four letters or more, as above) Windows OCR didn't read and RapidOCR did, on those frames "
          "only "
          f"({second.get('frames', 0)} frames read again" + (f"; {second['note']}" if second.get("note") else "")
          + "). RapidOCR can invent a number or a word: check each on the sheet before relying on it.", "",
          "| t | step | sentence | read by RapidOCR alone |", "|---|---|---|---|"]
    L += [f"| {s['t0']:.1f} | {s['step']} | {s['text'][:110]} | {', '.join(s['second'])} |"
          for s in sents if s.get("second")] or ["| | | none | |"]
    L += ["", "## Overlay items and their sentences (R80)", "", "| item | appears | sentence | label in it |",
          "|---|---|---|---|"]
    L += [f"| {i['overlay']} {i['item']}: {i['text']} | {i['at']:.2f} | {i['sentence']} | "
          f"{'yes' if i['label_in_sentence'] else '**no**'} |" for i in items]
    L += ["", "## Silences over the default gap (R25, R82)", "", "| at | between | gap | allowed | still picture |",
          "|---|---|---|---|---|"]
    L += [f"| {s['at']:.2f} | {' -> '.join(s['between'])} | {s['gap']:.2f} | {s['allow']:.2f} | "
          f"{'**yes**' if s['still'] else 'no'} |" for s in silences]
    L += ["", "## Marks at full resolution (R84): marks/", ""]
    L += [f"- {m['t']:.2f} s {m['step']} {m['kind']}: `marks/{m['file']}`" for m in marks]
    if shots:
        L += ["", f"## Stills: sheets/ ({len(shots)} moments, six to a sheet)", ""]
        L += [f"- {s['t']:.2f} s {s['why']}" for s in shots]
    L += ["", "## Transitions (R83, R34)", ""]
    L += [f"- {t['type']} at {t['t']:.2f} s (the join of the two recordings, before {t['before_step']}, R70)"
          if t.get("section") else
          f"- {t['type']} at {t['t']:.2f} s ({t['skipped_s']:.2f} s of Claude's work skipped"
          + (", on a mark or gesture" if t.get("crosses_mark") else "") + ")"
          for t in plan.get("transitions") or []] or ["- none"]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    f, out = check(args[0], stills="--no-stills" not in sys.argv, second_reader="--no-second-reader" not in sys.argv)
    print(f"{len(f)} finding(s); report: {out / 'report.md'}")
    for x in f:
        print(" -", x)
