"""R242's samples: the "Amazon Quick Series" card and the subscribe animation's four variations, rendered alone
(transparent ProRes 4444, frame-sized) and as previews over a stage review round's own intro and outro (the cityscape,
the avatar, stand-ins for the round's captions), with the round's voice and the call to action's sounds, plus contact
sheets and the measured checks.

    python tools/remotion_ctas.py render <stage review dir> <out dir> [--only=card,classic,brand,pill,soft] [--no-clips]
    python tools/remotion_ctas.py check <stage review dir> <out dir> [--only=...]

The stage review dir is a round of pipeline.edit.stage (stage_jobs.json, stage_job.json, stage_plan.json, the voice
WAVs); its run's stage_public is the bundle's public dir. Nothing here touches Premiere or spends money.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REMOTION = ROOT / "remotion"
SCRATCH = Path("G:/aidv_scratch/remotion_ctas") if Path("G:/").exists() else None

from pipeline.edit.cta import COMPOSITIONS as COMP, TEXT_BOX, VARIANTS  # noqa: E402  (one copy)
NAMES = {"classic": "A: close copy", "brand": "B: brand colours", "pill": "C: compact pill", "soft": "D: soft motion"}
# One copy of the pieces' timing and placement, shared with remotion/src/overlays (SeriesCard.tsx, SubscribeCta.tsx)
CTA = json.loads((REMOTION / "src/overlays/data/cta.json").read_text(encoding="utf-8"))
SERIES_BOX = CTA["series"]["box"]
SERIES_SPAN_S = CTA["series"]["spanS"]   # t1 - t0 as QuickArch03
SERIES_T0 = CTA["series"]["t0S"]         # the proposal: as QuickArch03's card, half a second into the intro
ORIGINAL = CTA["subscribe"]["original"]
WHOOSH_AT = CTA["subscribe"]["whooshAtS"]
CARD_WIN = (0.0, 7.0)              # the card's preview: the intro's first 7 s
SUB_PAD = (0.75, 0.55)             # the subscribe previews: from t0 - 0.75 to t1 + 0.55
SAFE = (96, 54, 1824, 980)         # title-safe (tokens layout.safePx)


def stage_inputs(review: Path):
    """A stage review round's (pipeline.edit.stage) or a final's (pipeline.edit.ppro.final_quick: its final_job.json
    "stage_places") stage props, plan and captions. A stage that already draws the pieces (R243: AvatarStage's series
    and subscribeAnim) has them taken out, so a preview or a check draws each piece once."""
    jobs = json.loads((review / "stage_jobs.json").read_text(encoding="utf-8"))["jobs"]
    if (review / "stage_job.json").exists():
        places = json.loads((review / "stage_job.json").read_text(encoding="utf-8"))["sequences"]
    else:
        places = json.loads((review / "final_job.json").read_text(encoding="utf-8"))["stage_places"]
    plan = json.loads((review / "stage_plan.json").read_text(encoding="utf-8"))
    bare = lambda pr: {k: v for k, v in pr.items() if k not in ("series", "subscribeAnim")}
    series = next(j["props"] for j in jobs if j["key"].startswith("intro_common")).get("series")
    intro = bare(next(j["props"] for j in jobs if j["key"].startswith("intro_common")))
    outro = bare(next(j["props"] for j in jobs if j["key"].startswith("outro_quick")))
    fps = plan["fps"]
    cues = {}
    for s in places:
        at = s["stage_at"]
        cues[s["kind"]] = [{"t0": (c["start_frame"] - at) / fps, "t1": (c["end_frame"] - at) / fps,
                            "text": c["text"], "box": c["box"]} for c in s["titles"]["cues"]]
    return {"intro": intro, "outro": outro, "cues": cues, "plan": plan, "fps": fps, "series": series}


def line_of(line_id):
    """A voiced line's lines.json entry, found by its id across exercises/*/lines.json (as pipeline.edit.ppro.final
    reads them: the ids carry the exercise's run_prefix, so one exercise holds it)."""
    hits = []
    for p in sorted((ROOT / "exercises").glob("*/lines.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        d = d.get("lines", d)
        if line_id in d:
            hits.append((p, d[line_id]))
    if len(hits) != 1:
        raise SystemExit(f"the line {line_id} is in {len(hits)} exercises' lines.json ({[str(p) for p, _ in hits]})")
    return hits[0][1]


def outro_words(plan):
    """The call to action's words on the outro stage's clock (as pipeline.edit.stage reads them)."""
    from pipeline.narration import timing
    g = plan["outro_render"]
    lines = {g["line_id"]: line_of(g["line_id"])}
    trim = plan["outro"]["avatar"]["trimBeforeS"]
    tau = lambda t: g["voice_at_s"] + t - trim
    out = {}
    for w in timing.of(lines[g["line_id"]])["words"]:
        k = w["word"].strip(".,!?").lower()
        if k in ("subscribe", "thumbs") and k not in out:
            out[k] = tau(w["start"])
    return out


def subscribe_times(words):
    """remotion/src/overlays/SubscribeCta.tsx subscribeTimes (the same rule, one Python copy: pipeline.edit.cta)."""
    from pipeline.edit import cta
    return cta.subscribe_times(words)


def pieces(si, only):
    """Each piece's layer, its preview window and its moments (stage seconds)."""
    fps = si["fps"]
    out = {}
    if "card" in only:                 # where the stage put it (R243), else cta.json's proposal
        layer = si.get("series") or {"t0": SERIES_T0, "t1": SERIES_T0 + SERIES_SPAN_S, "title": "Amazon Quick Series",
                                     "lines": list(CTA["series"]["lines"]), "box": SERIES_BOX}
        t0 = layer["t0"]
        taus = [0.3, 0.45, 0.6, 0.75, 0.9, 1.05, 1.2, 1.35, 1.6, 3.0]
        moments = [(t0 + x, f"in +{x:.2f} s") for x in taus] + \
                  [(layer["t1"] - x, f"out -{x:.2f} s") for x in (1.3, 1.0, 0.8, 0.6, 0.45)]
        out["card"] = {"kind": "series", "layer": layer, "win": CARD_WIN, "stage": "intro", "moments": moments,
                       "sounds": [(t0 + CTA["series"]["whooshAtS"], "whoosh")],         # S9 (seriesCardMoments)
                       "check_at": [t0 + 0.6, t0 + 1.0, t0 + 2.0, t0 + 3.0]}
    if any(v in only for v in VARIANTS):
        tm = subscribe_times(outro_words(si["plan"]))
        for v in VARIANTS:
            if v not in only:
                continue
            layer = {"variant": v, "text": "Thanks for Watching!", **tm}
            t0, b, th, t1 = tm["t0"], tm["bell"], tm["thumb"], tm["t1"]
            moments = [(t0 + x, f"+{x:.2f} s") for x in (0.3, 0.55, 0.85, 1.35)] + \
                      [(b - 0.3, "hand to bell"), (b + 0.05, "bell click"), (b + 0.3, "bell rings"),
                       (th - 0.25, "to the thumb"), (th + 0.05, "thumb click"), (th + 0.45, "after"),
                       (t0 + 5.0, "hold"), (t1 - 1.0, "exit"), (t1 - 0.7, "exit"), (t1 - 0.35, "exit")]
            out[v] = {"kind": "subscribe", "layer": layer, "win": (t0 - SUB_PAD[0], t1 + SUB_PAD[1]),
                      "stage": "outro", "moments": moments,
                      "sounds": [(t0 + WHOOSH_AT[v], "whoosh"), (b, "bell"), (th, "click")],
                      "check_at": [th + 0.8, t0 + 5.0]}
    return out


def preview_props(si, p):
    st = si[p["stage"]]
    props = {"durationInFrames": st["durationInFrames"], "fps": st["fps"], "width": st["width"], "height": st["height"],
             "stage": st, "captions": si["cues"][p["stage"]]}
    props["series" if p["kind"] == "series" else "subscribe"] = p["layer"]
    return props


def alone_props(si, p, dur_frames):
    st = si[p["stage"]]
    return {"durationInFrames": dur_frames, "fps": st["fps"], "width": st["width"], "height": st["height"],
            "layer": p["layer"]}


def run_jobs(jobs, public, tag):
    import tempfile
    if SCRATCH:
        SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH) as td:        # the jobs file goes with it (Fable)
        work = Path(td) / f"jobs_{tag}.json"
        work.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")
        r = subprocess.run(["node", "scripts/ctas.mjs", str(work), str(public)], cwd=REMOTION, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    res = [json.loads(x) for x in r.stdout.splitlines() if x.startswith("{")]
    bad = [x for x in res if not x.get("ok")]
    if r.returncode or bad or len(res) != len(jobs):
        raise SystemExit(f"render failed ({tag}): {bad or r.stderr[-3000:]}")
    return res


def mux(video, out, voice, a, b, sounds, files):
    """The preview's audio: the round's voice from a to b, each sound at its moment (seconds on the stage clock)."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(voice)]
    filt, labels = ["[1:a]aresample=48000,aformat=channel_layouts=mono[v]"], ["[v]"]
    for i, (t, k) in enumerate(sounds):
        cmd += ["-i", str(files[k])]
        ms = max(0, round((t - a) * 1000))
        filt.append(f"[{i + 2}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}[s{i}]")
        labels.append(f"[s{i}]")
    filt.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first[m]")
    cmd += ["-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[m]", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-shortest", str(out)]
    subprocess.run(cmd, check=True)


def sheet(rows, out, title, thumb_w=480, crop=(0, 0, 1920, 1080)):
    """rows: [(row label, [(png, caption)])] -> one labelled contact sheet of each still's crop (x0, y0, x1, y1)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("arial.ttf", 18)
    big = ImageFont.truetype("arialbd.ttf", 24)
    cols = max(len(r[1]) for r in rows)
    th = round(thumb_w * (crop[3] - crop[1]) / (crop[2] - crop[0]))
    lab = 26
    W = cols * thumb_w + (200 if any(r[0] for r in rows) else 10)
    H = 44 + len(rows) * (th + lab + 8)
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 8), title, fill=(0, 0, 0), font=big)
    for r, (label, cells) in enumerate(rows):
        y = 44 + r * (th + lab + 8)
        d.text((10, y + lab + th // 2 - 10), label, fill=(0, 0, 0), font=big)
        for c, (png, cap) in enumerate(cells):
            x = W - (cols - c) * thumb_w
            im = Image.open(png).convert("RGB").crop(crop).resize((thumb_w - 4, th), Image.LANCZOS)
            img.paste(im, (x, y + lab))
            d.text((x + 2, y + 3), cap, fill=(0, 0, 0), font=font)
    img.save(out)
    return out


def cmd_render(a):
    review, out = Path(a.review).resolve(), Path(a.out).resolve()
    only = set(a.only.split(",")) if a.only else {"card", *VARIANTS}
    si = stage_inputs(review)
    fps = si["fps"]
    public = review.parent / "stage_public"
    P = pieces(si, only)
    plan = si["plan"]
    sounds = {k: Path(v) for k, v in plan["sound_files"].items()}
    voices = {"intro": review / "voice_opening.wav", "outro": review / "voice_recap.wav"}
    stills_dir = out / "stills"
    jobs, meta = [], {}
    for k, p in P.items():
        a0, b0 = p["win"]
        fa, fb = round(a0 * fps), round(b0 * fps) - 1
        pv = (SCRATCH or out) / f"_preview_{k}.mp4"
        jobs.append({"key": f"preview_{k}", "id": "CtaPreview", "props": preview_props(si, p),
                     "stills": [{"frame": round(t * fps), "out": str(stills_dir / f"{k}_{round(t * fps):05d}.png")}
                                for t, _ in p["moments"]],
                     "clip": {"a": fa, "b": fb, "out": str(pv), "codec": "h264"}})
        meta[k] = {"preview_silent": pv, "a": fa / fps, "b": (fb + 1) / fps}
    run_jobs(jobs, public, "previews")
    for k, p in P.items():
        m = meta[k]
        name = "series_card" if k == "card" else f"subscribe_{k}"
        mux(m["preview_silent"], out / f"preview_{name}.mp4", voices[p["stage"]], m["a"], m["b"], p["sounds"], sounds)
        m["preview_silent"].unlink(missing_ok=True)
    if not a.no_clips:                 # the pieces alone, frame-sized and transparent (their own clock from 0)
        cj = []
        for k, p in P.items():
            if p["kind"] == "series":
                lay = {**p["layer"], "t0": 0.0, "t1": SERIES_SPAN_S}
                n = round(SERIES_SPAN_S * fps)
                cj.append({"key": f"clip_{k}", "id": "SeriesCard", "props": {**alone_props(si, p, n), "layer": lay},
                           "stills": [], "clip": {"a": 0, "b": n - 1, "out": str(out / "clips" / "series_card.mov"),
                                                  "codec": "prores"}})
            else:
                L = p["layer"]
                lay = {**L, "t0": 0.0, "bell": L["bell"] - L["t0"], "thumb": L["thumb"] - L["t0"],
                       "t1": L["t1"] - L["t0"]}
                n = round(lay["t1"] * fps) + 1
                cj.append({"key": f"clip_{k}", "id": COMP[k], "props": {**alone_props(si, p, n), "layer": lay},
                           "stills": [], "clip": {"a": 0, "b": n - 1, "out": str(out / "clips" / f"subscribe_{k}.mov"),
                                                  "codec": "prores"}})
        run_jobs(cj, public, "clips")
    # the contact sheets: the card's own; the subscribe variations side by side at the same moments
    if "card" in P:
        p = P["card"]
        cells = [(stills_dir / f"card_{round(t * fps):05d}.png", f"{t:.2f} s ({lab})") for t, lab in p["moments"]]
        sheet([("", cells[:5]), ("", cells[5:10]), ("", cells[10:])], out / "sheet_series_card.png",
              "Amazon Quick Series card over round 7's intro: stage seconds (the card from 0.50 s; entrance, hold, "
              "exit); the captions are stand-ins drawn from round 7's caption boxes", thumb_w=600,
              crop=(400, 260, 1920, 1080))
    vs = [v for v in VARIANTS if v in P]
    cta_crop = (40, 420, 1340, 1000)                 # the captions' middle-left spot and the animation, lower left
    rows = []
    for v in vs:
        p = P[v]
        cells = [(stills_dir / f"{v}_{round(t * fps):05d}.png", f"{t:.2f} s {lab}") for t, lab in p["moments"]]
        rows.append((NAMES[v], cells))
        sheet([("", cells[:7]), ("", cells[7:])], out / f"sheet_subscribe_{v}.png",
              f"Subscribe animation {NAMES[v]}, over round 7's outro: stage seconds (bell click {p['layer']['bell']:.2f}, "
              f"thumb click {p['layer']['thumb']:.2f}); captions are stand-ins from round 7's", thumb_w=520,
              crop=cta_crop)
    if len(vs) > 1:                                  # all four side by side at the same moments
        sheet(rows, out / "sheet_subscribe_all.png", "Subscribe animation, the four variations at the same moments "
              "(stage seconds)", thumb_w=300, crop=cta_crop)
    pj = out / "pieces.json"                          # (merged with an earlier run's other pieces, as checks.json)
    prev = json.loads(pj.read_text(encoding="utf-8")) if pj.exists() else {}
    pj.write_text(json.dumps({**prev, **P}, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"out": str(out), "pieces": sorted(P)}))


def cmd_check(a):
    """The measured checks on stills: G6 contrast and G7 see-through (pipeline.edit.checks), G15 title-safe and the
    captions' clearance, the card's clearance from the avatar's face, and the text sizes (OCR'd word heights)."""
    import numpy as np
    from PIL import Image
    from pipeline.edit import checks
    review, out = Path(a.review).resolve(), Path(a.out).resolve()
    only = set(a.only.split(",")) if a.only else {"card", *VARIANTS}
    si = stage_inputs(review)
    fps = si["fps"]
    public = review.parent / "stage_public"
    P = pieces(si, only)
    cdir = out / "check"
    jobs = []
    for k, p in P.items():
        for t in p["check_at"]:
            f = round(t * fps)
            st = si[p["stage"]]
            comp = "SeriesCard" if p["kind"] == "series" else COMP[k]
            props = {**preview_props(si, p), "captions": []}         # the piece's own text only
            jobs.append({"key": f"comp_{k}_{f}", "id": "CtaPreview", "props": props,
                         "stills": [{"frame": f, "out": str(cdir / f"{k}_{f:05d}_comp.png")}], "clip": None})
            jobs.append({"key": f"alpha_{k}_{f}", "id": comp, "props": alone_props(si, p, st["durationInFrames"]),
                         "stills": [{"frame": f, "out": str(cdir / f"{k}_{f:05d}_alpha.png")}], "clip": None})
    run_jobs(jobs, public, "checks")
    report = {}
    for k, p in P.items():
        fl = []
        for t in p["check_at"]:
            f = round(t * fps)
            comp, alpha = cdir / f"{k}_{f:05d}_comp.png", cdir / f"{k}_{f:05d}_alpha.png"
            words = checks.ocr_many([comp])[str(comp)]
            ow = checks.overlay_words(comp, alpha, words)
            exempt = p["kind"] == "subscribe"          # G6's exemption: "Thanks for Watching!" (R235)
            # the card's entrance and exit: its body fills in behind the title on purpose, so the see-through findings
            # there are the motion's (as the stage's "transients"); the ratio is still measured
            L = p["layer"]
            transient = p["kind"] == "series" and min(t - L["t0"], L["t1"] - t) < CTA["series"]["settledS"]
            con = checks.text_contrast(comp, alpha, t, f"{k} ", words)
            fl += [{**x, "exempt": exempt or ("transient" if transient and "see-through" in x["what"] else False)}
                   for x in con]
            if p["kind"] == "series" and not transient:
                fl += checks.see_through(alpha, t, f"{k} ")
            fl += [{**x, "exempt": "transient"} if transient else x            # a word mid-wipe has no whole capitals
                   for x in checks.alignment(comp, alpha, t, f"{k} ", words=words)]
            A = np.asarray(Image.open(alpha).convert("RGBA").getchannel("A"))
            ys, xs = np.nonzero(A > 16)
            box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
            safe_ok = box and box[0] >= SAFE[0] and box[1] >= SAFE[1] and box[2] <= SAFE[2] and box[3] <= SAFE[3]
            cue_gap = []
            for c in si["cues"][p["stage"]]:
                if c["t0"] <= t < c["t1"] and box:
                    x, y, w, h = c["box"]
                    dx = max(x - box[2], box[0] - (x + w), 0)
                    dy = max(y - box[3], box[1] - (y + h), 0)
                    cue_gap.append({"cue": c["text"].replace("\n", " "), "gap_px": int(max(dx, dy))})
            sizes = [{"word": w[0], "ocr_h": round(w[4], 1)} for w in ow]
            if not safe_ok:                                   # the measures judge, not only report (Fable)
                fl.append(checks.finding("title_safe", "G15", t, f"{k} reaches outside title-safe: {box}"))
            for g in cue_gap:
                if g["gap_px"] < 12:
                    fl.append(checks.finding("captions", "G15", t, f"{k} is {g['gap_px']} px from the caption "
                                             f"\"{g['cue']}\" (12 px wanted)"))
            words_px = text_pixels(comp, alpha, TEXT_BOX) if p["kind"] == "subscribe" else None
            report.setdefault(k, []).append({"t": round(t, 3), "frame": f, "overlay_box": box,
                                             "inside_title_safe": bool(safe_ok), "captions": cue_gap,
                                             "ocr_words": sizes, "text_pixels": words_px})
        report[k] = {"frames": report[k], "findings": fl}
    if "card" in P:
        report["card"]["face"] = fc = face_clearance(si, P["card"], public)
        if not fc["ok"]:
            report["card"]["findings"].append(checks.finding("face", "C7", None, f"the card is {fc['gap_px']} px from "
                                                             f"the avatar's face at {fc['nearest_face_px']} (12 wanted)"))
    old = out / "checks.json"                        # a run with --only updates its pieces and keeps the rest
    merged = {**(json.loads(old.read_text(encoding="utf-8")) if old.exists() else {}), **report}
    old.write_text(json.dumps(merged, indent=1, default=str), encoding="utf-8")
    for k, r in report.items():
        print(k, json.dumps({"findings": [(x["what"], x.get("exempt")) for x in r["findings"]],
                             "text_pixels": [f.get("text_pixels") for f in r["frames"]],
                             "frames": [(f["t"], f["overlay_box"], f["inside_title_safe"], f["captions"])
                                        for f in r["frames"]]}, default=str))




def text_pixels(comp_png, alpha_png, box):
    """The words' contrast by their pixels (GOTCHAS: OCR misses text with nothing behind it, so the OCR check above
    reads little or none of it): the ink is the piece's own solid pixels in the box (alpha over 200) or, on an opaque
    pill, its light pixels; the ground is what is right around the letters (a 6 px ring outside the ink, beyond the
    text's own shadow on a see-through piece). Ratios of the ink's median against the ground's median and its
    lightest tenth (the worst place). G6 exempts these words (R235); the figure says how well they read."""
    import numpy as np
    from PIL import Image, ImageFilter
    x0, y0, x1, y1 = box
    rgb = np.asarray(Image.open(comp_png).convert("RGB"))[y0:y1, x0:x1].astype(float)
    a = np.asarray(Image.open(alpha_png).convert("RGBA").getchannel("A"))[y0:y1, x0:x1]
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    solid = a > 200
    opaque = solid.mean() > 0.3                         # a panel fills much of the box (the pill): split it by light
    if opaque:
        ink = solid & (lum > np.percentile(lum[solid], 85))
    else:
        ink = solid
    if ink.sum() < 50:
        return None
    grow = lambda m, n: np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(n))) > 0
    ring = grow(ink, 13) & ~grow(ink, 3)
    ring &= solid if opaque else (a < 24)               # on the panel; or the screen itself, not the text's shadow
    if ring.sum() < 50:
        return None
    from pipeline.edit import checks
    k = np.median(rgb[ink], axis=0)
    g = rgb[ring]
    gl = g @ np.array([0.2126, 0.7152, 0.0722])
    light = np.median(g[gl >= np.percentile(gl, 90)], axis=0)
    med = np.median(g, axis=0)
    hexs = lambda c: "#%02x%02x%02x" % tuple(int(round(v)) for v in c)
    return {"ink": hexs(k), "ground_median": hexs(med), "ratio_median": round(checks.ratio(k, med), 2),
            "ground_lightest_tenth": hexs(light), "ratio_worst": round(checks.ratio(k, light), 2),
            "on_panel": bool(opaque)}


def face_clearance(si, p, public):
    """The card against the avatar's face on every frame the card shows, from the intro render's own picture (VP9 with
    alpha: libvpx-vp9 decodes it): the head (all of the avatar above the jaw, row 560 on round 7's render; below it
    the collar starts) and the beard (light, unsaturated pixels down to row 720 within the jaw's width, opened 3 x 3). The
    gap is the least distance (px, the larger of the two axes) from any of it to the card's box."""
    import numpy as np
    import tempfile
    from PIL import Image, ImageFilter
    st = si["intro"]
    L = p["layer"]
    a0, a1 = L["t0"] + CTA["series"]["drawnFromS"], L["t1"] - CTA["series"]["drawnFromS"]   # all it draws
    av = st["avatar"]
    if av["start"] != "full" or any(m["at"] < a1 for m in av["moves"]):
        raise SystemExit("the face check reads the render full frame and still: the avatar moves while the card shows")
    src = public / av["src"]
    U = None
    with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-c:v", "libvpx-vp9", "-ss",
                        f"{st['avatar']['trimBeforeS'] + a0:.3f}", "-i", str(src), "-t", f"{a1 - a0:.3f}", "-vf",
                        "format=rgba", str(Path(td) / "a%04d.png")], check=True)
        for f in sorted(Path(td).glob("a*.png")):
            a = np.asarray(Image.open(f).convert("RGBA")).astype(int)
            al = a[..., 3] > 64
            mx, mn = a[..., :3].max(axis=2), a[..., :3].min(axis=2)
            beard = al & (mx > 130) & (mx - mn < 45)
            beard[720:] = False
            jaw = np.nonzero(al[540:640].any(axis=0))[0]      # the beard hangs within the jaw's width, not the lit shoulder
            if len(jaw):
                beard[:, :jaw.min()] = False
                beard[:, jaw.max() + 1:] = False
            beard = np.asarray(Image.fromarray((beard * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))
                               .filter(ImageFilter.MaxFilter(3))) > 0
            face = beard | np.vstack([al[:560], np.zeros_like(al[560:])])
            U = face if U is None else (U | face)
    if U is None or not U.any():
        raise SystemExit(f"no avatar frames read from {src} for the face check")
    b = L["box"]
    x0, y0, x1, y1 = b["x"], b["y"], b["x"] + b["w"] - 1, b["y"] + b["h"] - 1
    ys, xs = np.nonzero(U)
    d = np.maximum(np.maximum(np.maximum(x0 - xs, xs - x1), 0), np.maximum(np.maximum(y0 - ys, ys - y1), 0))
    k = int(d.argmin())
    return {"frames_s": [round(a0, 2), round(a1, 2)], "card": [x0, y0, x1, y1], "gap_px": int(d[k]),
            "nearest_face_px": [int(xs[k]), int(ys[k])], "ok": bool(d[k] >= 12)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("render", "check"):
        c = sp.add_parser(name)
        c.add_argument("review")
        c.add_argument("out")
        c.add_argument("--only")
        if name == "render":
            c.add_argument("--no-clips", action="store_true")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(errors="replace")
    {"render": cmd_render, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
