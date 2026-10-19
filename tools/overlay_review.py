"""The overlay build's harness (R149 to R154; docs/OVERLAY_BUILD_PLAN_qs1a.md): cards, checks, renders and the
Premiere review project for an exercise's overlays (Section A's by default).

    python tools/overlay_review.py init runs/<run_id>/premiere_rN exercises/<ex>/overlays_review.json
           --out=overlays_review_r1 --work=research/overlay_build/<prefix> [--steps=...] [--art=...]
                                                          # a new exercise's review round: <run>/<out>/round.json
    python tools/overlay_review.py cards                  # manifest -> timed cards, variants, collision report
    python tools/overlay_review.py check <key>            # one builder's version: lint, types, stills, checks
    python tools/overlay_review.py render [<key> ...]     # final clips of every version that passed (one bundle)
    python tools/overlay_review.py judge-input            # what Claude's judge reads -> <work>/judge_input.json
    python tools/overlay_review.py xml [--require-picks]  # the source round's full XML + the review tracks, markers
    python tools/overlay_review.py build                  # Premiere builds the review project, then the markers

Every subcommand but init takes --review=<review folder> (the folder init made: its round.json names the run, the
source round, the manifest, the steps file, the art and the work folder). Without it the harness runs Section A's
round 4 exactly as before (the constants below). With it, configure() sets the constants from round.json, and any
write outside the review folder, the work folder and the Remotion review tree's entries/, public/ and _tsc/ is
refused (writable()), so a constant missed here can't write into Section A's approved overlays_review_r4. The work
folder (research/overlay_build/<prefix>) holds what isn't put beside the project David opens: the blind key
(builders_key.json; init copies Section A's when there is none), picks.json, clip_index.json, judge_input.json, and
overlay_build.py's brief, costs, scoreboard and replies. It is one exercise's: init refuses another exercise's work
folder (Section A's qs1a, one whose work.json or a round names another manifest, one holding pieces this manifest
hasn't) and marks a new one as this manifest's (work.json).

Two contracts the stage needs, checked by `cards` before it writes a card: no piece id that another exercise's
manifest uses (remotion/review/items/ is shared: another exercise's A01 would overwrite Section A's A01.*.tsx); and
a chapter card at the main body's first line, the earliest chapter card and the first in cards.json, on the picked
track (pipeline.edit.stage.nest_card and pipeline.edit.pip.opening_card read it; R141, R231).

Claude's picks (R245, the one-shot, in place of R163's picks by David in the review project). After every version is
checked, a fresh Claude subagent judges, as R190's reviews are run (free, no outside call). Its input, written by
`judge-input` to <work>/judge_input.json: each piece on the picked track with more than one passing builder version,
its card (cards/<piece>.json: what it shows, its line, its times) and, per version, its check report
(checks/<key>.json: status, warnings, the measured checks) and contact sheet (checks/<key>/sheet.png: the version
over the real frames at its key times), with the rulebook to judge by (VIDEO_RULES.md, section 8: G1 to G21). The
versions are named blind, by their clips' names (A01.Builder-A; a judge favours its own vendor, GOTCHAS), each sheet
copied to <work>/judge/<name>.png. Its output: <work>/picks.json, {"<piece>": "<version>", ..., "_about": "who
picked, when, by what"}, a version being its blind name or its key (A01.argon); `xml` reads it, resolving a blind
name through the clip index that `render` writes. Each pick and its reason also go into exercises/<ex>/ONE_SHOT.md.
`xml --require-picks` stops on a piece of the picked track with several builder versions and no pick, or a pick
that names none of its clips.

The manifest (exercises/qs1_section_a/overlays_review.json) uses the overlays.json schema that pipeline/edit/plan.py
reads (plan_overlays), so a pick copies straight into the edit later; each entry adds a `review` block (where it
came from, what it shows, its route and track). A one-off piece has layout "piece" and props {piece, ...}; its
versions are remotion/review/items/<id>.<builder>.tsx, each exporting `Piece: React.FC<{o: PieceLayer}>`. A
library composition renders as version "lib". Each review round has a folder of its own (REVIEW: its cards,
checks, frame cache, clips, sounds and project), so a new round never changes media a project David has opened uses
(R61). Round 4 sits on round 8 of the edit (SOURCE_ROUND); each round's times come from its own plan, so nothing is taken
from an earlier round. Times are edit time, seconds on the full sequence (equal to the source round's plan time); reports
give timecodes.
"""
import argparse
import os
import threading
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUN = ROOT / "runs" / "qs1a_20261014_full_take01"
SOURCE_ROUND = RUN / "premiere_r10"                       # round 8 as built (premiere_r9 replaced before David saw it)
REVIEW = RUN / "overlays_review_r4"                       # review round 4, on round 8 (round 3: overlays_review_r3,
                                                          # on round 7; round 2: overlays_review_r2, on round 6;
                                                          # round 1: overlays_review_r1, on round 5)
OUT = REVIEW                                              # the project, clips and sounds
ROUND_N = int(REVIEW.name.rsplit("_r", 1)[1])            # the review round's number (its markers' "Changed:")
MEDIA = [OUT / "overlays"]
MANIFEST = ROOT / "exercises" / "qs1_section_a" / "overlays_review.json"
STEPS = ROOT / "exercises" / "qs1_section_a" / "steps_full.json"
REMOTION = ROOT / "remotion"
ITEMS = REMOTION / "review" / "items"
ENTRIES = REMOTION / "review" / "entries"
PUBLIC = REMOTION / "review" / "public"                   # art the pieces use (staticFile), copied in by name
ART = ROOT / "research" / "overlay_ideas" / "qs1a" / "art"
VIDEO_LIB = ROOT.parent / "Global Assets" / "motion-library" / "video"   # generated clips (R153)
BLIND_KEY = ROOT / "research" / "overlay_build" / "qs1a" / "builders_key.json"   # builder -> letter; not beside the
                                                                                 # project David opens
WORK = BLIND_KEY.parent                                   # the blind key, picks, clip index (and the builders' files)
SECTION_A_MANIFEST, SECTION_A_WORK = MANIFEST, WORK       # whose work folder qs1a is, whatever configure() sets
GUARD = None                 # with --review: the folders this round may write in (writable()); None: no guard
CONFIGURED = None             # with --review: the review folder whose round.json set the constants above


def _abs(p):
    """A round.json path: relative to AIDrivenVideo, or absolute."""
    p = Path(p)
    return (p if p.is_absolute() else ROOT / p).resolve()


def _rel(p):
    """A path as round.json keeps it: relative to AIDrivenVideo where it is inside it, posix."""
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def round_of(folder):
    """A review folder's round number, from its name (overlays_review_r4 -> 4)."""
    m = re.search(r"_r(\d+)$", Path(folder).name)
    if not m:
        raise SystemExit(f"{folder}: a review folder is named <name>_r<N> (overlays_review_r1), for its round number")
    return int(m.group(1))


def configure(review=None):
    """The constants from a review folder's round.json (init writes it); None keeps Section A's round 4. Once
    configured, writable() refuses every write outside the review folder, the work folder and the Remotion review
    tree's generated folders."""
    global RUN, SOURCE_ROUND, REVIEW, OUT, ROUND_N, MEDIA, MANIFEST, STEPS, ART, BLIND_KEY, WORK, GUARD, CONFIGURED
    if review is None:
        return
    review = Path(review).resolve()
    rj_p = review / "round.json"
    if not rj_p.exists():
        raise SystemExit(f"{rj_p} not found: make the round with `overlay_review.py init` first")
    rj = json.loads(rj_p.read_text(encoding="utf-8"))
    RUN, SOURCE_ROUND = _abs(rj["run"]), _abs(rj["source_round"])
    REVIEW = OUT = review
    ROUND_N = int(rj.get("round") or round_of(review))
    MEDIA = [OUT / "overlays"]
    MANIFEST, STEPS, ART = _abs(rj["manifest"]), _abs(rj["steps"]), _abs(rj["art"])
    WORK = _abs(rj["work"])
    BLIND_KEY = WORK / "builders_key.json"
    GUARD = (REVIEW, WORK, ENTRIES.resolve(), PUBLIC.resolve(), (REMOTION / "review" / "_tsc").resolve())
    CONFIGURED = review


def writable(path):
    """path, if this round may write it: with --review, only inside the review folder, the work folder and the
    Remotion review tree's entries/, public/ and _tsc/ (never another round's folder, Section A's approved
    overlays_review_r4 above all); without it, anything, as before. Two writes stay outside it on purpose:
    tools/overlay_sounds.write adds a sound kind it hasn't made yet to the shared library (Global
    Assets/motion-library/sounds, R153; the copy into overlays/sounds/ is guarded), and overlay_build.py writes the
    builders' files into the shared remotion/review/items/, which contract 1 (no piece id of another exercise's)
    protects. Neither is a route into a round's folder."""
    if GUARD is not None:
        p = Path(path).resolve()
        if not any(p == g or g in p.parents for g in GUARD):
            raise SystemExit(f"refusing to write {p}: outside this round's folders ({', '.join(map(str, GUARD))})")
    return path

ALLOWED_IMPORTS = re.compile(r"^(react|remotion|@remotion/(paths|shapes|layout-utils|transitions)|"
                             r"\.\./\.\./src/(camera|overlays/(kit|pieces|pinned|geo|tokens\.json|vendor/.+)))$")
LINT = [  # (pattern, problem): one look across builders (the plan's lint, from both reviews)
    (r"\bspring\s*\(", "spring(): use prog() and the tokens' easing (R131: no overshoot but the asides)"),
    (r"['\"`]#[0-9a-fA-F]{3,8}\b", "a hex colour: take colours from look(o.variant) or ACCENT"),
    (r"\bfontFamily\s*:", "fontFamily: use FONT.heading, FONT.body, FONT.wordList or FONT.data (R143, R148)"),
    (r"\bMath\.random\s*\(|\bDate\.now\s*\(", "randomness or the clock: every frame must render the same"),
    (r"\buseEffect\s*\(|\bsetTimeout\s*\(|\bsetInterval\s*\(", "effects or timers: draw from the frame alone"),
]


def tc(t, fps=30):
    f = round(t * fps)
    return f"{f // (3600 * int(fps)):02d}:{f // (60 * int(fps)) % 60:02d}:{f // int(fps) % 60:02d}:{f % int(fps):02d}"


def plan_path():
    """The plan the review sits on: the source round's copy (its export wrote it), else the run's current plan."""
    p = SOURCE_ROUND / "edit_plan.json"
    return p if p.exists() else RUN / "edit_plan.json"


def load_plan():
    return json.loads(plan_path().read_text(encoding="utf-8"))


def write_json(path, obj):
    """Atomic: written beside, then swapped in, so a check running at the same time never reads half a file."""
    import time
    writable(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}_{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    for attempt in range(20):                             # Windows refuses a swap while a reader has the file open
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.1)
    os.replace(tmp, path)


# ------------------------------------------------------------------------------------------------ real frames
def frames_of(times, plan):
    """EditPass stills at full size for these edit times (cached in REVIEW/frames/f_<frame>.png): one bundle, the
    media hard-linked into a slim public dir, as pipeline/edit/linecheck.py does."""
    fps, N = plan["fps"], plan["durationInFrames"]
    want = sorted({max(0, min(N - 1, round(t * fps))) for t in times})
    import hashlib                                        # one cache per plan: a re-planned edit (another round's
    sig = hashlib.sha256(json.dumps(plan, sort_keys=True).encode("utf-8")).hexdigest()[:10]   # camera, marks,
    out = REVIEW / "frames" / sig                         # corrections) never reuses the last plan's frames
    writable(out).mkdir(parents=True, exist_ok=True)

    class Frames(dict):                                   # a frame past the ends reads as the nearest real one
        def __missing__(self, f):
            return dict.__getitem__(self, max(0, min(N - 1, f)))

    result = Frames({f: out / f"f_{f:06d}.png" for f in want})
    if all(p.exists() for p in result.values()):
        return result
    with FileLock(out / ".lock"):                         # one renderer at a time; the others wait, then reuse
        _render_frames([f for f in want if not (out / f"f_{f:06d}.png").exists()], plan, out)
    return result


class FileLock:
    """A lock across processes (several builders' checks run at once): a file made exclusively, removed after;
    a lock older than 15 minutes is a crashed holder's and is broken."""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        import time
        while True:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 900:
                        self.path.unlink(missing_ok=True)
                except FileNotFoundError:
                    pass
                time.sleep(0.5)

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def _render_frames(todo, plan, out):
    if todo:
        pub = REVIEW / f"_public_frames_{os.getpid()}_{threading.get_ident()}"   # one per caller: checks run at once
        shutil.rmtree(writable(pub), ignore_errors=True)
        writable(out)
        from pipeline.edit.plan import plan_media
        for rel in plan_media(plan):
            src, dst = RUN / rel, pub / rel
            if src.exists() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    dst.hardlink_to(src)
                except OSError:
                    shutil.copy2(src, dst)
        jobs = out / f"_jobs_{os.getpid()}_{threading.get_ident()}.json"
        jobs.write_text(json.dumps([{"frame": f, "out": f"f_{f:06d}.png"} for f in todo]), encoding="utf-8")
        try:
            subprocess.run(["node", "scripts/stills.mjs", str(plan_path()), str(pub), str(out), str(jobs),
                            "1"], cwd=REMOTION, check=True, capture_output=True)
        finally:
            shutil.rmtree(pub, ignore_errors=True)
            jobs.unlink(missing_ok=True)


# ------------------------------------------------------------------------------------------------------ cards
class Log:
    def __init__(self):
        self.warnings, self.notes = [], []


def screen_area(layer, plan, t):
    """The screen box (x, y, w, h) a piece covers, for its variant and the collision report: its box, its pinned
    target's screen box widened by a typical piece, or the title-safe band its edge implies."""
    from pipeline.edit import camera as cam
    W, H = plan["width"], plan["height"]
    if layer.get("box"):
        b = layer["box"]
        return b["x"], b["y"], b["w"], b["h"]
    if layer.get("pin"):
        p = layer["pin"]
        s, cx, cy = cam.cam_at(plan.get("camera"), t, W, H)
        x, y = (p["x"] - cx) * s + W / 2, (p["y"] - cy) * s + H / 2
        return max(0, x - 120), max(0, y - 120), p["w"] * s + 240, p["h"] * s + 240
    e = layer.get("edge") or "top"
    return {"top": (96, 54, W - 192, 300), "bottom": (96, 560, W - 192, 310), "left": (96, 54, 640, 816),
            "right": (W - 736, 54, 640, 816)}.get(e, (96, 54, W - 192, 816))


def brightness(png, area):
    from PIL import Image, ImageStat
    x, y, w, h = (int(v) for v in area)
    im = Image.open(png).convert("L")
    return ImageStat.Stat(im.crop((x, y, min(im.width, x + w), min(im.height, y + h)))).mean[0]


def foreign_ids(manifest=None):
    """The piece ids other exercises' overlay manifests use, {id: manifest}: every exercise's versions live in the one
    remotion/review/items/ folder (<id>.<builder>.tsx), so an id two exercises share overwrites one's pieces with the
    other's. Manifests in this manifest's own exercise folder aren't another exercise's."""
    mine = Path(manifest or MANIFEST).resolve()
    out = {}
    for p in sorted((ROOT / "exercises").glob("*/overlays_review*.json")):
        if p.resolve().parent == mine.parent:
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:      # an unreadable manifest can't be shown not to clash
            raise SystemExit(f"can't read {p} to check its piece ids against this manifest's: {e}")
        for o in doc.get("overlays", []):
            out.setdefault(o["id"], p)
    return out


def opening_contract(layers, meta, track_of, plan):
    """What the stage needs of the cards, or None when it holds: a chapter card at the main body's first line (the
    source round's first narration line), on the picked track, the earliest chapter card and the first in the cards,
    since pipeline.edit.stage.nest_card takes the first in cards.json and pipeline.edit.pip.opening_card the earliest
    (R141: chapter cards at section changes; R231: the zoom down into the oval over the Part 1 card)."""
    first = plan["narration"][0]
    chapters = [ly for ly in layers if ly.get("layout") == "chapter_card"]
    if not chapters:
        return (f"no chapter card in the manifest's timed cards: the stage and the pip need one at the main body's "
                f"first line, {first['line_id']} (R141, R231)")
    c0 = min(chapters, key=lambda ly: ly["t0"])
    if c0 is not chapters[0]:
        return (f"the first chapter card in the cards ({chapters[0]['id']}) isn't the earliest ({c0['id']}): the "
                "stage's nest_card and the pip's opening_card would take different cards; order the manifest by time")
    if meta[c0["id"]].get("line") != first["line_id"]:
        return (f"the first chapter card, {c0['id']}, is on {meta[c0['id']].get('line')}, not the main body's first "
                f"line {first['line_id']}: the stage and the pip open on it (R141, R231)")
    if track_of.get(c0["id"], "picked") != "picked":
        return f"the first chapter card, {c0['id']}, is on the {track_of[c0['id']]!r} track, not the picked one"
    return None


def cmd_cards(_):
    from pipeline.edit import plan as planner
    plan = load_plan()
    doc = json.loads(STEPS.read_text(encoding="utf-8"))
    sub = lambda x: re.sub(r"\{(\w+)\}", lambda m_: doc["variables"].get(m_.group(1), m_.group(0)), x)
    placed = {n["step"]: n for n in plan["narration"]}
    log = Log()
    full = json.loads(MANIFEST.read_text(encoding="utf-8"))
    other = foreign_ids()                                 # contract 1: remotion/review/items/ is shared
    clash = sorted({o["id"] for o in full["overlays"]} & other.keys())
    if clash:
        raise SystemExit("piece ids another exercise's manifest uses (their versions share remotion/review/items/; "
                         "rename them in " + _rel(MANIFEST) + "): " +
                         "; ".join(f"{i} ({_rel(other[i])})" for i in clash))
    kept = dict(full, overlays=[o for o in full["overlays"] if not o.get("review", {}).get("dropped")])
    live = REVIEW / "_tmp" / "manifest.json"                # David's dropped pieces left out (R163, R168)
    write_json(live, kept)
    layers = planner.plan_overlays(live, placed, plan["settings"]["marks"], sub, log)
    for n in planner.after_draws(layers, plan.get("marks", {}).get("layers", [])):   # R166: not during a draw
        print("note:", n)
    from pipeline.edit import checks as ck                # R185: the last part stays long enough to read; the next
    track_of = {o["id"]: o.get("review", {}).get("track", "picked") for o in kept["overlays"]}   # piece on the
    for n in ck.hold_for_reading([ly for ly in layers if track_of.get(ly["id"]) == "picked"]):  # track waits up to 1 s
        print("note:", n)
        if n.startswith("R185 flag"):
            log.warnings.append(n)
    for n in planner.after_draws(layers, plan.get("marks", {}).get("layers", [])):   # a held-back entrance can land
        print("note (after R185):", n)                                              # in a draw: R166 again
    meta = {o["id"]: o for o in kept["overlays"]}
    fps, N = plan["fps"], plan["durationInFrames"]
    end = (N - 1) / fps
    for ly in layers:                     # word-timed props (meaning_at_word -> meaning_at) are plan_overlays' own
        if ly["t1"] > end:                                # a piece running past the sequence ends with it
            log.warnings.append(f"{ly['id']}: its exit ran past the sequence end; cut at {tc(end, fps)}")
            ly["t1"] = round(end, 4)
        timed = [(k, v) for k, v in ly.items() if k.endswith("_at") and isinstance(v, (int, float))]
        timed += [(f"item {it.get('key', i)}", it["at"]) for i, it in enumerate(ly.get("items", []))]
        for k, t in timed:
            if not (ly["t0"] - 1e-3 <= t <= ly["t1"] - 0.3):
                log.warnings.append(f"{ly['id']}: {k} at {tc(t, fps)} is outside the piece ({tc(ly['t0'], fps)} to "
                                    f"{tc(ly['t1'], fps)}, less its exit): it would never show")
    broken = opening_contract(layers, meta, track_of, plan)   # contract 2, before any card is written
    if broken:
        raise SystemExit(broken)
    frames = frames_of([ly["t0"] + 0.5 for ly in layers], plan)
    cards = []
    for ly in layers:
        review = meta[ly["id"]].get("review", {})
        if ly.get("variant", "auto") == "auto":            # R140: dark on a light screen, light on a dark one
            png = frames[max(0, min(plan["durationInFrames"] - 1, round((ly["t0"] + 0.5) * fps)))]
            mean = brightness(png, screen_area(ly, plan, ly["t0"] + 0.5))
            ly["variant"] = "dark" if mean >= 128 else "light"
            ly["_brightness"] = round(mean)
        ly.pop("plan_overlay", None)
        card = {"layer": ly, "review": review, "t0_tc": tc(ly["t0"], fps), "t1_tc": tc(ly["t1"], fps),
                "items_tc": [{"key": it.get("key"), "text": it.get("text"), "at_tc": tc(it["at"], fps)}
                             for it in ly.get("items", [])]}
        write_json(REVIEW / "cards" / f"{ly['id']}.json", card)
        cards.append(card)
    write_json(REVIEW / "cards.json", cards)
    frames_of([t for c in cards for _, t in check_times(c["layer"])], plan)   # every check's frames, cached once
    report = collisions(cards, plan)
    writable(REVIEW / "collisions.md").write_text(report, encoding="utf-8")
    for w in log.warnings:
        print("warning:", w)
    print(f"{len(cards)} cards -> {REVIEW / 'cards'}; collisions -> {REVIEW / 'collisions.md'}")


def collisions(cards, plan):
    """One overlay at a time on the main track, no overlay over a click mark's draw (R51), nothing in the captions'
    band: reported, not enforced; David judges in Premiere (R149)."""
    fps = plan["fps"]
    main = sorted((c for c in cards if c["review"].get("track", "picked") == "picked"), key=lambda c: c["layer"]["t0"])
    lines = ["# Overlay collisions (reported, not enforced)", "", "Times are timecodes on the full sequence.", ""]
    lines.append("## One at a time (main track)")
    n = 0
    for a, b in zip(main, main[1:]):
        if b["layer"]["t0"] < a["layer"]["t1"]:
            n += 1
            lines.append(f"- {a['layer']['id']} ({a['t0_tc']} to {a['t1_tc']}) is still up when {b['layer']['id']} "
                         f"starts at {b['t0_tc']}")
    lines += [] if n else ["- none"]
    lines += ["", "## Arriving during a click mark's draw (R51, R166)"]
    n = 0
    draws = [m for m in plan.get("marks", {}).get("layers", []) if m.get("style") == "draw"]
    for c in main:                                    # an entrance or an item's arrival, not the hold: a piece may
        ly = c["layer"]                               # stay up while marks are drawn beside it
        ev = [("its entrance", ly["t0"], ly["t0"] + 0.5)] + \
             [(f"item {it.get('key', '')}", it["at"], it["at"] + 0.4) for it in ly.get("items", [])]
        hit = [f"{name} at {tc(a, fps)} with the {m['kind']} of {m['step']} drawn at {tc(m['draw0'], fps)}"
               for name, a, b in ev for m in draws if a < m.get("draw1", m["draw0"]) and b > m["draw0"]]
        if hit:
            n += 1
            lines.append(f"- {ly['id']} ({c['t0_tc']} to {c['t1_tc']}): " + "; ".join(hit))
    lines += [] if n else ["- none"]
    lines += ["", "## In the captions' band (below y 870)"]
    n = 0
    for c in cards:
        x, y, w, h = screen_area(c["layer"], plan, c["layer"]["t0"])
        if y + h > 870 and c["layer"].get("layout") != "chapter_card":
            n += 1
            lines.append(f"- {c['layer']['id']} at {c['t0_tc']}: its area reaches y {round(y + h)}")
    lines += [] if n else ["- none"]
    from pipeline.edit import checks as ck                # R185, after the cards' holds
    lines += ["", "## Up long enough to read (R185)"]
    short = ck.display_time([c["layer"] for c in main])
    lines += [f"- {f['tc']} {f['what']}" for f in short] or ["- none"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------------ check
LIB_IMPORTS = re.compile(r"^(react|remotion|@remotion/(paths|shapes|layout-utils|transitions)|\.\./camera|\.\./track|"
                         r"\./(kit|pieces|pinned|geo|tokens\.json|vendor/.+|data/.+))$")


def library():
    return json.loads((REMOTION / "review" / "library.json").read_text(encoding="utf-8"))["layouts"]


MIN_PX = json.loads((REMOTION / "src" / "overlays" / "tokens.json").read_text(encoding="utf-8"))["type"]["minPx"]
COLOUR_WORDS = r"white|black|red|green|blue|gray|grey|orange|yellow|purple|pink|brown|navy|teal|gold|silver|cyan|magenta"
LINT_MORE = [  # holes Fable's harness review found (R108)
    (r"""['"`]#['"`]\s*\+|\+\s*['"`]#""", "a hex colour built by concatenation: colours from look(o.variant) or ACCENT"),
    (r"\b(rgba?|hsla?)\(\s*\d", "a literal rgb()/hsl() colour: colours from look(o.variant) or ACCENT (kit's rgba(hex, a) "
                                "with a token is fine)"),
    (rf"""(color|background|backgroundColor|fill|stroke|borderColor)\s*:\s*['"`]({COLOUR_WORDS})['"`]""",
     "a named colour: colours from look(o.variant) or ACCENT"),
    (rf"""['"`][^'"`\n]*\bsolid\s+({COLOUR_WORDS})\b""", "a named colour in a border: colours from look(o.variant)"),
    (r"(?<![\w-])font\s*:", "the font: shorthand: use FONT.* and fontSize"),
    (r"""\bfontSize\s*:\s*['"`]\s*([0-9]|[1-3][0-9]|4[0-7])(\.\d+)?px""", "a fontSize under 48 px (R161)"),
    (r"\bfontSize\s*:[^,}\n]*\*\s*0?\.\d", "a fontSize scaled down: nothing under 48 px (R161)"),
    (r"""\bimport\s+['"]|\brequire\s*\(|\bimport\s*\(""", "a side-effect, require() or dynamic import"),
]


def strip_comments(src):
    """The code without // and /* */ comments (a comment that names a banned word isn't the banned thing)."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(^|[^:'\"`\\])//[^\n]*", r"\1", src, flags=re.M)


def lint(src, lib=False):
    code = strip_comments(src)
    problems = [why for pat, why in LINT + LINT_MORE if re.search(pat, code)]
    for m in re.finditer(r"fontSize\s*:\s*(\d+)", code):
        if int(m.group(1)) < MIN_PX:
            problems.append(f"fontSize {m.group(1)}: nothing under {MIN_PX} px at 1080p (tokens type.minPx, R161)")
    for m in re.finditer(r"""from\s+['"]([^'"]+)['"]""", code):
        mod = m.group(1)
        rest = re.sub(r"^(\.\./)+|^\./", "", mod)
        if not (LIB_IMPORTS if lib else ALLOWED_IMPORTS).match(mod) or ".." in rest.split("/"):
            problems.append(f"import from {mod!r}: only react, remotion, @remotion/paths|shapes|layout-utils|"
                            "transitions, and ../../src/camera or ../../src/overlays/(kit|pieces|pinned|geo|tokens|vendor)")
    if not lib and not re.search(r"export\s+const\s+Piece\b", code):
        problems.append("no `export const Piece: React.FC<{o: PieceLayer}>`")
    return list(dict.fromkeys(problems))


def tsc_errors(rel):
    """Type errors in one file (and what it imports), from a tsconfig of its own: quicker than the whole project,
    and another builder's broken file can't show up here. A type check that doesn't run is an error, not a pass."""
    cfg = REMOTION / "review" / "_tsc" / (re.sub(r"[^\w.-]", "_", rel) + ".json")
    writable(cfg).parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"extends": "../../tsconfig.json", "compilerOptions": {"noEmit": True},
                               "files": ["../../" + rel, "../../remotion-env.d.ts"], "include": []}), encoding="utf-8")
    r = subprocess.run(["npx", "tsc", "-p", cfg.relative_to(REMOTION).as_posix(), "--pretty", "false"],
                       cwd=REMOTION, capture_output=True, text=True, shell=True)
    out = (r.stdout or "") + (r.stderr or "")
    errs = [ln for ln in out.splitlines() if re.search(r"\(\d+,\d+\): error TS", ln)]
    if r.returncode and not errs:
        errs = [f"the type check didn't run: {out.strip()[-400:]}"]
    return errs, out


def entry_for(keys, name, layouts=None):
    """A generated entry: the library compositions (review/library.json) whose files exist, or only `layouts`, and
    the builders' items `keys`."""
    ENTRIES.mkdir(parents=True, exist_ok=True)
    lib = {k: v for k, v in library().items() if (REMOTION / v["file"]).exists() and (layouts is None or k in layouts)}
    lines = ["// Written by tools/overlay_review.py; don't edit.", "import {registerRoot} from 'remotion';",
             "import {AnyFC, ReviewRoot, setItems} from '../ReviewClip';"]
    lines += [f"import {{{v['export']} as L{i}}} from '../../{v['file'][:-4]}';" for i, (k, v) in enumerate(lib.items())]
    lines += [f"import {{Piece as P{i}}} from '../items/{k}';" for i, k in enumerate(keys)]
    lines.append("setItems({" + ", ".join(f"{k}: L{i} as AnyFC" for i, k in enumerate(lib)) + "}, {" +
                 ", ".join(f"{json.dumps(k)}: P{i} as AnyFC" for i, k in enumerate(keys)) + "});")
    lines.append("registerRoot(ReviewRoot);")
    p = writable(ENTRIES / f"{name}.ts")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def sync_public(cards):
    """The art files the cards name (props.art: file names in ART, Section A's research/overlay_ideas/qs1a/art/),
    copied into the review bundle's public dir."""
    writable(PUBLIC).mkdir(parents=True, exist_ok=True)
    for c in cards:
        art = c["layer"].get("art")
        names = [n for n in (art.values() if isinstance(art, dict) else []) if isinstance(n, str)]
        vid = c["layer"].get("video")                     # a generated clip (Aside's video mode), from the library
        if isinstance(vid, dict) and vid.get("main"):
            names.append(vid["main"])
        for name in names:
            src = next((d / name for d in (ART, VIDEO_LIB) if (d / name).exists()), None)
            if src and not (PUBLIC / name).exists():
                shutil.copy2(src, writable(PUBLIC / name))


def run_render(entry, jobs, plan):
    jp = REVIEW / "_tmp" / f"jobs_{entry.stem}.json"
    write_json(jp, {"common": {"fps": plan["fps"], "width": plan["width"], "height": plan["height"],
                               "durationInFrames": plan["durationInFrames"], "camera": plan.get("camera")},
                    "jobs": jobs})
    r = subprocess.run(["node", "review/render.mjs", str(entry.relative_to(REMOTION)).replace("\\", "/"), str(jp),
                        str(PUBLIC)], cwd=REMOTION, capture_output=True, text=True)
    res = {}
    for ln in (r.stdout or "").splitlines():
        try:
            o = json.loads(ln)
            res[o["key"]] = o
        except (json.JSONDecodeError, KeyError):
            pass
    if r.returncode and not res:
        raise SystemExit(f"render failed: {(r.stderr or r.stdout)[-3000:]}")
    return res


def check_times(ly):
    """The times a version is looked at: in, each item's word just before and after, mid-hold, out."""
    t0, t1 = ly["t0"], ly["t1"]
    ts = [("in", min(t1, t0 + 0.6))]
    items = ly.get("items", [])
    for i, it in enumerate(items):
        nxt = items[i + 1]["at"] if i + 1 < len(items) else t1 - 0.6
        ts += [(f"item{i}_{it.get('key', i)}_before", max(t0, it["at"] - 0.05)),
               (f"item{i}_{it.get('key', i)}_after", min(t1, it["at"] + 0.12)),   # R80: on its word, within 0.1 s
               (f"item{i}_{it.get('key', i)}_late", min(t1, it["at"] + 0.35))]    # a thin line drawing on starts faint
        # settled: entrances (0.5 s) and the part's own fade done, before the next part or the exit (the measured
        # checks look here and at mid-hold, never at a fade: Fable's round 8 review); none when the next part comes
        # within 0.45 s, since it would land in this one's fade
        s_ = min(t1 - 0.6, it["at"] + 0.9, nxt - 0.05)
        if s_ - it["at"] >= 0.45:
            ts.append((f"item{i}_{it.get('key', i)}_set", s_))
    ts += [("hold", (max([t0] + [it["at"] for it in ly.get("items", [])]) + t1) / 2), ("out", max(t0, t1 - 0.04))]
    return ts


def cmd_check(a):
    from PIL import Image, ImageChops, ImageDraw
    key = a.key
    pid = key.split(".")[0]
    card = json.loads((REVIEW / "cards" / f"{pid}.json").read_text(encoding="utf-8"))
    ly = card["layer"]
    is_lib = key.endswith(".lib")                         # a library composition: its file in review/library.json
    f = REMOTION / library()[ly["layout"]]["file"] if is_lib else ITEMS / f"{key}.tsx"
    plan = load_plan()
    fps = plan["fps"]
    rep = {"key": key, "piece": pid, "file": str(f), "problems": [], "warnings": [], "stills": [],
           "sha256": sha256_of(f), "layer": layer_hash(ly)}
    if not f.exists():
        rep["problems"].append(f"no file {f}")
    else:
        rep["problems"] += lint(f.read_text(encoding="utf-8"), lib=is_lib)
        mine, _ = tsc_errors(f.relative_to(REMOTION).as_posix())
        rep["problems"] += [f"type error: {ln}" for ln in mine]
    if not rep["problems"]:
        times = check_times(ly)
        out = REVIEW / "checks" / key
        shutil.rmtree(writable(out), ignore_errors=True)
        sync_public([card])
        jobs = [{"key": key, "version": "lib" if is_lib else key, "layer": ly, "clip": None,
                 "stills": [{"frame": round(t * fps), "out": str(out / f"raw_{name}.png")} for name, t in times]}]
        entry = entry_for([] if is_lib else [key], f"check-{key}", layouts=[ly["layout"]] if is_lib else [])
        res = run_render(entry, jobs, plan).get(key, {"ok": False, "error": "no result"})
        if not res["ok"]:
            rep["problems"].append(f"render error: {res.get('error')}")
        else:
            bg = frames_of([t for _, t in times], plan)
            raw = {name: Image.open(out / f"raw_{name}.png").convert("RGBA") for name, _ in times}
            for name, t in times:
                frame = Image.open(bg[round(t * fps)]).convert("RGBA")
                frame.alpha_composite(raw[name])
                p = out / f"{name}.png"
                frame.convert("RGB").save(p)
                rep["stills"].append({"name": name, "tc": tc(t, fps), "file": str(p)})
            full = ly.get("full_frame") or ly.get("layout") == "chapter_card"
            visible = lambda im: sum(im.getchannel("A").histogram()[9:])          # pixels with alpha above 8
            for name, im in raw.items():
                clear = im.getchannel("A").histogram()[0] / (im.width * im.height)
                if not full and clear < 0.25 and name not in ("out",):
                    rep["problems"].append(f"{name}: only {clear:.0%} of the frame is transparent (not an overlay?)")
            if visible(raw["hold"]) < 200:
                rep["problems"].append("nothing is visible at mid-hold")
            if visible(raw["out"]) > 2000:
                rep["problems"].append(f"still visible at its last frame {tc(ly['t1'], fps)}: the exit isn't finished")
            for i, it in enumerate(ly.get("items", [])):
                k = f"item{i}_{it.get('key', i)}"
                changed = lambda b: sum(ImageChops.difference(raw[k + "_before"], raw[k + b]).convert("L")
                                        .histogram()[25:]) >= 300
                if not changed("_after") and not changed("_late"):
                    rep["problems"].append(f"item {it.get('key', i)!r} ({it.get('text')!r}): nothing changes at its "
                                           f"word, {tc(it['at'], fps)} (R80)")
                elif not changed("_after"):
                    rep["warnings"].append(f"item {it.get('key', i)!r}: barely visible 0.1 s after its word "
                                           f"{tc(it['at'], fps)}; clear by 0.35 s (a slow draw-on?)")
            # R179, R187, R185: the measured checks (pipeline.edit.checks) on the stills at each item's word and
            # mid-hold: text at 7:1 with nothing see-through behind it, rows and columns lined up, the last part up
            # long enough. A false alarm is waived in the manifest's review block ("waive": {"R187": "why"}).
            from pipeline.edit import checks as ck
            waive = card["review"].get("waive") or {}
            look = [(n, t) for n, t in times if n.endswith("_set") or n == "hold"]
            ocrd = ck.ocr_many([out / f"{n}.png" for n, _ in look])
            measured = ck.see_through(out / "raw_hold.png", dict(times)["hold"], "mid-hold: ") if not full else []
            for n, t in look:
                comp, alpha = out / f"{n}.png", out / f"raw_{n}.png"
                measured += ck.text_contrast(comp, alpha, t, words=ocrd[str(comp)])
                measured += ck.alignment(comp, alpha, t, words=ocrd[str(comp)])
            measured += ck.display_time([ly])
            seen_m = set()
            for m in measured:                            # one line per word or row, at its first still
                k = (m["rule"], m["what"])
                if k in seen_m:
                    continue
                seen_m.add(k)
                line = f"{m['rule']} {m['tc'] or ''}: {m['what']}"
                if m["rule"] in waive:
                    rep["warnings"].append(f"waived ({waive[m['rule']]}): {line}")
                else:
                    rep["problems"].append(line)
            rep["measured"] = measured
            bbox = raw["hold"].getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()   # solid, not shadow
            if bbox and not full:
                if bbox[3] > 870 and not ly.get("over_captions"):
                    rep["warnings"].append(f"reaches y {bbox[3]} at mid-hold, into the captions' band (below 870)")
                if bbox[0] < 90 or bbox[2] > plan["width"] - 90 or bbox[1] < 50:      # title-safe 96/54, 6 px slack
                    rep["warnings"].append(f"outside title-safe at mid-hold: {bbox}")
            from PIL import ImageFont
            font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26)
            sheet = Image.new("RGB", (960 * 2, 540 * ((len(times) + 1) // 2)), (20, 20, 20))
            for i, s in enumerate(rep["stills"]):
                im = Image.open(s["file"]).resize((960, 540))
                d = ImageDraw.Draw(im)
                d.rectangle((0, 0, 960, 38), fill=(20, 20, 20))
                d.text((10, 3), f"{s['name']}   {s['tc']}", font=font, fill=(255, 220, 0))
                sheet.paste(im, ((i % 2) * 960, (i // 2) * 540))
            sheet.save(out / "sheet.png")
            rep["sheet"] = str(out / "sheet.png")
    rep["status"] = "pass" if not rep["problems"] else "fail"
    write_json(REVIEW / "checks" / f"{key}.json", rep)
    print(json.dumps({k: rep[k] for k in ("key", "status", "problems", "warnings")} | {"sheet": rep.get("sheet")},
                     indent=1, ensure_ascii=False))
    return 0 if rep["status"] == "pass" else 1


# ----------------------------------------------------------------------------------------------------- render
def passing():
    keys = []
    cards = {c["layer"]["id"]: c["layer"] for c in json.loads((REVIEW / "cards.json").read_text(encoding="utf-8"))}
    for p in sorted((REVIEW / "checks").glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("status") == "pass" and Path(r["file"]).exists() and r.get("sha256") == sha256_of(Path(r["file"])) \
                and r["piece"] in cards and r.get("layer") == layer_hash(cards[r["piece"]]):
            keys.append(r["key"])                         # a file edited, or a card re-timed, since its check: again
    return keys


def layer_hash(ly):
    """What a clip is rendered from besides the code: the whole card layer (times, items, variant, props)."""
    import hashlib
    return hashlib.sha256(json.dumps(ly, sort_keys=True).encode("utf-8")).hexdigest()


def sha256_of(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None


def cmd_render(a):
    plan = load_plan()
    fps, N = plan["fps"], plan["durationInFrames"]
    cards = {c["layer"]["id"]: c for c in json.loads((REVIEW / "cards.json").read_text(encoding="utf-8"))}
    log = REVIEW / "render_log.json"
    done = json.loads(log.read_text(encoding="utf-8")) if log.exists() else {}
    built = sorted(OUT.glob("*_full.prproj"))
    if built:                   # R61: a built project uses these clips (David may have it open); fixes go to a new round
        raise SystemExit(f"{built[0]} is built; this round's clips aren't re-rendered (R61). Start the next review "
                         "round for changes (`init` and --review; Section A's: REVIEW, SOURCE_ROUND at the top of "
                         "this file)")
    writable(OUT / "overlays")
    if a.keys:
        keys = a.keys
    else:                       # every version that passed its check, unless its clip is already of this very file
        files = {json.loads(p.read_text(encoding="utf-8"))["key"]: json.loads(p.read_text(encoding="utf-8"))["file"]
                 for p in (REVIEW / "checks").glob("*.json")}
        ok = passing()
        keys = [k for k in ok if pid_of(k) in cards and (a.all or not done.get(k, {}).get("ok")
                or done[k].get("sha256") != sha256_of(files[k])
                or done[k].get("layer") != layer_hash(cards[pid_of(k)]["layer"]))]   # an item's time counts too
        print(f"{len(keys)} version(s) to render ({len(ok) - len(keys)} already rendered from the same file)")
        stale = sorted(r["key"] for r in (json.loads(p.read_text(encoding="utf-8"))
                                          for p in (REVIEW / "checks").glob("*.json"))
                       if r.get("status") == "pass" and r["piece"] in cards and r["key"] not in ok
                       and r.get("sha256") == sha256_of(Path(r["file"])))
        if stale:               # passed, same file, but its card was re-timed since (Fable's R108 review, item 1)
            print(f"check again first (the card changed since the check): {' '.join(stale)}")
    sync_public(list(cards.values()))
    items = [k for k in keys if not k.endswith(".lib")]
    index_p = WORK / "clip_index.json"   # clip name -> version key; kept with the blind key, not beside the project
    index = json.loads(index_p.read_text(encoding="utf-8")) if index_p.exists() else {}
    jobs = []
    for k in keys:
        ly = cards[pid_of(k)]["layer"]
        a_, b_ = round(ly["t0"] * fps), min(N - 1, round(ly["t1"] * fps))
        name = blind_name(k)                              # refuses a builder the blind key doesn't know
        for old in [n for n, v in index.items() if v == k and n != name]:   # a renamed version's old clip goes
            (OUT / "overlays" / f"{old}.mov").unlink(missing_ok=True)       # (this round's only: R61)
            index.pop(old)
        index[name] = k
        (OUT / "overlays").mkdir(parents=True, exist_ok=True)
        jobs.append({"key": k, "version": "lib" if k.endswith(".lib") else k, "layer": ly, "stills": [],
                     "clip": {"a": a_, "b": b_, "out": str(OUT / "overlays" / f"{name}.mov")}})
    write_json(index_p, index)
    layouts = sorted({cards[pid_of(k)]["layer"]["layout"] for k in keys if k.endswith(".lib")})
    try:
        res = run_render(entry_for(items, "wave", layouts=layouts), jobs, plan)
    except SystemExit as e:                               # one file can break a whole bundle: then one at a time
        print(f"the wave's bundle failed ({str(e)[:300]}); rendering each version on its own")
        res = {}
        for j in jobs:
            k = j["key"]
            lib = k.endswith(".lib")
            try:
                res.update(run_render(entry_for([] if lib else [k], f"one-{k}", layouts=[j["layer"]["layout"]]
                                                if lib else []), [j], plan))
            except SystemExit as e1:
                res[k] = {"key": k, "ok": False, "error": str(e1)[:2000]}
    for k, r_ in res.items():                             # what each clip was made from, for the next pass
        rep = json.loads((REVIEW / "checks" / f"{k}.json").read_text(encoding="utf-8"))
        ly = cards[pid_of(k)]["layer"]
        r_.update({"sha256": sha256_of(rep["file"]), "t0": ly["t0"], "t1": ly["t1"], "layer": layer_hash(ly)})
    old = done
    old.update(res)
    write_json(log, old)
    bad = [k for k, r in res.items() if not r["ok"]]
    print(f"{len(res) - len(bad)} of {len(jobs)} clips rendered -> {OUT / 'overlays'}" +
          (f"; failed: {bad}" if bad else ""))


# -------------------------------------------------------------------------------------------- xml and build
def cmd_xml(a=None):
    """The source round's full sequence with the review tracks above its own (its Caption titles track keeps its name
    and index, since the panel inserts the titles by name). Clips on a track never overlap: each track is
    lane-packed. --require-picks (Claude's picks, R245): stop, before anything is written, on a piece of the picked
    track with several builder versions and no pick in the work folder's picks.json, or a pick naming none of its
    clips."""
    from pipeline.edit import premiere as pm
    writable(OUT)
    plan = load_plan()
    fps, W, H, N = plan["fps"], plan["width"], plan["height"], plan["durationInFrames"]
    (src,) = [p for p in SOURCE_ROUND.glob("*_full.xml") if p.name != "captions_full.xml"]
    tree = ET.parse(src)
    root = tree.getroot()
    full = next(s for s in root.iter("sequence") if (s.findtext("name") or "").endswith(" full"))
    video = full.find("./media/video")
    ids = pm.Ids()
    ids.n = max([int(m) for m in re.findall(r'id="clipitem-(\d+)"', src.read_text(encoding="utf-8"))] or [0]) + 1000
    nfile = [max([int(m) for m in re.findall(r'id="file-(\d+)"', src.read_text(encoding="utf-8"))] or [0]) + 1000]

    def file_el(parent, path, frames):
        nfile[0] += 1
        f = pm.sub(parent, "file", id=f"file-{nfile[0]}")
        pm.sub(f, "name", Path(path).name)
        pm.sub(f, "pathurl", pm.pathurl(path))
        pm.rate(f, fps)
        pm.sub(f, "duration", frames)
        sc = pm.sub(pm.sub(pm.sub(f, "media"), "video"), "samplecharacteristics")
        pm.rate(sc, fps)
        for k, v in (("width", W), ("height", H), ("anamorphic", "FALSE"), ("pixelaspectratio", "square"),
                     ("fielddominance", "none")):
            pm.sub(sc, k, v)

    cards = {c["layer"]["id"]: c for c in json.loads((REVIEW / "cards.json").read_text(encoding="utf-8"))}
    picks_p = WORK / "picks.json"                       # names the picked model: kept with the blind key
    picks = json.loads(picks_p.read_text(encoding="utf-8")) if picks_p.exists() else {}
    letters = blind()
    index_p = WORK / "clip_index.json"
    index = json.loads(index_p.read_text(encoding="utf-8")) if index_p.exists() else {}
    # Where each clip goes: a piece's card names its track ("picked" unless it's an alternate, a map extra, a video
    # prop...). On the picked track a piece shows one version: its library composition, else picks.json's choice,
    # else its first builder version; every other builder version goes to that builder's own track, named by the
    # blind letter in builders_key.json (Fable's review: David's picks, not Claude's, are the keep rate).
    clips, seen = {}, set()
    for mov in [m for d in MEDIA for m in sorted(d.glob("*.mov"))]:   # this round's clip wins over the last round's
        if mov.stem in seen:
            continue
        seen.add(mov.stem)
        if mov.stem not in index:                         # only clips render made and indexed (no stale names)
            print(f"left out (not in the clip index): {mov.name}")
            continue
        key = index[mov.stem]
        if pid_of(key) not in cards:                      # a piece David dropped (R163, R168): its clip stays (R154)
            print(f"left out (no card: dropped from the manifest): {mov.name}")
            continue
        clips.setdefault(pid_of(key), []).append((key, mov))
    rlog_p = REVIEW / "render_log.json"
    rlog = json.loads(rlog_p.read_text(encoding="utf-8")) if rlog_p.exists() else {}
    stale = [k for kms in clips.values() for k, _ in kms
             if rlog.get(k, {}).get("layer") != layer_hash(cards[pid_of(k)]["layer"])]
    if stale:                   # a clip rendered from another card would sit at the new time with its items off their
        raise SystemExit("clips rendered from an older card (check and render them again): " + " ".join(stale))  # words
    if getattr(a, "require_picks", False):
        unpicked = missing_picks(clips, cards, picks, index)
        if unpicked:
            raise SystemExit(f"--require-picks: {len(unpicked)} piece(s) of the picked track need a pick in {picks_p} "
                             "(the judge's output; `judge-input` lists what it reads):\n  " + "\n  ".join(unpicked))

    # R155: captions sit above every overlay, so the review tracks go in below the caption tracks (the panel finds
    # "Caption titles" by name, wherever it is)
    first_caption = next(i for i, el in enumerate(video) if el.tag == "track"
                         and el.get("MZ.TrackName") in ("Captions", "Caption titles"))
    added = [0]

    def review_track(parent, label):
        el = pm.sub(parent, "track", **{"MZ.TrackName": label})
        if parent is video:
            parent.remove(el)
            parent.insert(first_caption + added[0], el)
            added[0] += 1
        return el
    by_track, report, markers = {}, [], []
    for pid, kms in clips.items():
        c = cards.get(pid)
        if not c:
            continue
        track = c["review"].get("track", "picked")
        keys = [k for k, _ in kms]
        # the shown version: the library's, else David's or the integrator's pick, else the first by blind letter
        # (never by model name, so no builder is favoured)
        shown = next((k for k in keys if k.endswith(".lib")), None) or pick_key(picks.get(pid), index) or \
            sorted(keys, key=lambda k: blind_name(k))[0]
        if len([k for k in keys if not k.endswith(".lib")]) > 1 and pid not in picks:
            report.append(f"note: {pid} has no pick in picks.json; showing {blind_name(shown)}")
        for key, mov in kms:
            builder = key.split(".", 1)[1]
            letter = "Integrator" if builder == "claude" else letters.get(builder, builder)
            if track == "picked":
                t = "picked" if key == shown else ("Integrator" if builder == "claude" else f"Builder {letter}")
            else:                                         # alternates and extras keep each builder apart too
                t = track if builder == "lib" else (f"{track}, Integrator" if builder == "claude"
                                                    else f"{track}, Builder {letter}")
            by_track.setdefault(t, []).append((c, key, mov))
    order = ["picked"] + sorted(t for t in by_track if t.startswith("Builder ")) + \
            [t for t in by_track if t != "picked" and not t.startswith("Builder ")]
    for name in order:
        if name not in by_track:
            continue
        lanes = []
        for c, key, mov in sorted(by_track[name], key=lambda x: x[0]["layer"]["t0"]):
            ly = c["layer"]
            a_, b_ = round(ly["t0"] * fps), min(N, round(ly["t1"] * fps) + 1)
            lane = next((ln for ln in lanes if ln["end"] <= a_), None)
            if lane is None:
                label = "Review: " + name + (f" {len(lanes) + 1}" if lanes else "")
                lane = {"end": 0, "el": review_track(video, label), "label": label}
                lanes.append(lane)
            ci = pm.clipitem(lane["el"], ids, f"{pid_of(key)} {c['review'].get('what', '')}"[:60], a_, b_, 0,
                             b_ - a_, b_ - a_, fps, alpha="straight")
            file_el(ci, mov, b_ - a_)
            lane["end"] = b_
            if name == "picked":
                builder = key.split(".", 1)[1]
                who = ("a library composition" if key.endswith(".lib")
                       else "Claude's own version (the integrator)" if builder == "claude"
                       else f"Builder {letters.get(builder, builder)}'s version" +
                       (f" ({MODEL_NAMES[builder]})" if REVEALED and builder in MODEL_NAMES else ""))
                more = (" Other versions and alternates are on the Review tracks above, switched off."
                        if len(clips.get(pid_of(key), [])) > 1 or by_track.keys() - {"picked"} else "")
                change = c["review"].get(f"r{ROUND_N}_change")   # what this round changed, in David's words
                markers.append({"t": round(ly["t0"], 3), "name": f"Overlay: {c['review'].get('what', ly['id'])}"[:60],
                                "comment": f"From {plain_source(c['review'].get('source', 'the plan'))}. Shown: {who}."
                                           + (f" Changed: {change}" if change else "") + more})
        for ln in lanes:
            pm.sub(ln["el"], "enabled", "TRUE" if name == "picked" else "FALSE")
            pm.sub(ln["el"], "locked", "FALSE")
        report.append(f"{name}: {len(by_track[name])} clip(s) on {len(lanes)} track(s)")

    # The sound pass (R158: it stays): each shown overlay's sounds, one track per kind so David can set a kind's
    # level (and no track is near empty, note 7), all on. Sounds are made in code (tools/overlay_sounds).
    import importlib.util
    spec = importlib.util.spec_from_file_location("overlay_sounds", ROOT / "tools" / "overlay_sounds.py")
    snd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snd)
    audio = full.find("./media/audio")
    evs = {}
    for c, key, mov in by_track.get("picked", []):
        for t, kind in sound_events(c["layer"]):
            evs.setdefault(kind, set()).add((round(t, 4), kind, c["layer"]["id"]))   # two versions, one sound
    peak = ((plan.get("click_sound") or {}).get("peak_dbfs")     # the click's level (R137, R177)
            or -24.0 + ((plan.get("loudness") or {}).get("effects_gain_db") or 0.0))
    for kind in sorted(evs):
        label, picked, enabled = f"Review: sounds, {kind}", sorted(evs[kind]), True
        lanes = []
        for t, kind, pid in picked:
            c = cards[pid]
            src_wav = writable(OUT / "overlays" / "sounds" / snd.write(kind, peak).name)   # under overlays/: the
                                                                                            # build bins it
            if not src_wav.exists():
                src_wav.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(snd.write(kind, peak), src_wav)
            with __import__("wave").open(str(src_wav)) as w:
                nf = max(1, int(w.getnframes() / w.getframerate() * fps))   # floored: never past the media's end
            a_ = round(t * fps)
            if a_ >= N:
                continue
            b_ = min(N, a_ + nf)
            lane = next((ln for ln in lanes if ln["end"] <= a_), None)
            if lane is None:
                lane = {"end": 0, "el": pm.sub(audio, "track", **{"MZ.TrackName": label + (f" {len(lanes) + 1}"
                                                                                           if lanes else "")})}
                lanes.append(lane)
            ci = pm.clipitem(lane["el"], ids, f"{kind} {c['layer']['id']}", a_, b_, 0, b_ - a_, nf, fps,
                             premiereChannelType="mono")
            ci.remove(ci.find("alphatype"))
            nfile[0] += 1
            fe = pm.sub(ci, "file", id=f"file-{nfile[0]}")
            pm.sub(fe, "name", src_wav.name)
            pm.sub(fe, "pathurl", pm.pathurl(src_wav))
            pm.rate(fe, fps)
            pm.sub(fe, "duration", nf)
            au = pm.sub(pm.sub(fe, "media"), "audio")
            sc = pm.sub(au, "samplecharacteristics")
            pm.sub(sc, "depth", 16)
            pm.sub(sc, "samplerate", 48000)
            pm.sub(au, "channelcount", 1)
            st = pm.sub(ci, "sourcetrack")
            pm.sub(st, "mediatype", "audio")
            pm.sub(st, "trackindex", 1)
            lane["end"] = b_
        for ln in lanes:
            pm.sub(ln["el"], "enabled", "TRUE" if enabled else "FALSE")
            pm.sub(ln["el"], "locked", "FALSE")
        if picked:
            report.append(f"{label}: {len(picked)} sound(s) on {len(lanes)} track(s)" + ("" if enabled else ", off"))
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / src.name
    if (OUT / f"{src.stem}.prproj").exists():             # David may have opened this round's project: a new
        raise SystemExit(f"{OUT} already holds a built project; review rounds don't overwrite (R61)")   # round
    tree.write(writable(out), encoding="UTF-8", xml_declaration=True)
    shutil.copy2(SOURCE_ROUND / "caption_titles.json", writable(OUT / "caption_titles.json"))
    write_json(OUT / "markers.json", {"sequence": full.findtext("name"), "markers": markers})
    print("\n".join(report) + f"\n-> {out}")


def pick_key(pick, index):
    """A picks.json value as a version key: a key as it is (A01.argon), or a clip's blind name (A01.Builder-A, as
    Claude's blind judge names versions) through the clip index."""
    return index.get(pick, pick) if isinstance(pick, str) else pick


def missing_picks(clips, cards, picks, index=None):
    """The picked track's pieces that lack a usable pick: several builder versions (a library composition shows as it
    is) and no pick, or a pick that names none of the piece's clips (then no version would show)."""
    index = index or {}
    out = []
    for pid, kms in sorted(clips.items()):
        c = cards.get(pid)
        keys = sorted(k for k, _ in kms)
        if not c or c["review"].get("track", "picked") != "picked" or any(k.endswith(".lib") for k in keys):
            continue
        if pid not in picks:
            if len(keys) > 1:
                out.append(f"{pid}: {len(keys)} versions ({', '.join(keys)}) and no pick")
        elif pick_key(picks[pid], index) not in keys:
            out.append(f"{pid}: its pick {picks[pid]!r} is none of its clips ({', '.join(keys)})")
    return out


def cmd_judge_input(_):
    """What Claude's judge reads (the module docstring's "Claude's picks"), blind: each piece on the picked track with
    more than one passing builder version, its card, and per version (by its clip's blind name) the check's status,
    warnings and measured checks and a copy of its contact sheet -> <work>/judge_input.json, <work>/judge/*.png.
    Reports the picks already in <work>/picks.json against it."""
    cards = {c["layer"]["id"]: c for c in json.loads((REVIEW / "cards.json").read_text(encoding="utf-8"))}
    by_piece = {}
    for k in passing():
        by_piece.setdefault(pid_of(k), []).append(k)
    picks_p = WORK / "picks.json"
    picks = json.loads(picks_p.read_text(encoding="utf-8")) if picks_p.exists() else {}
    index_p = WORK / "clip_index.json"
    index = json.loads(index_p.read_text(encoding="utf-8")) if index_p.exists() else {}
    pieces, todo = [], []
    for pid, keys in sorted(by_piece.items()):
        c = cards[pid]
        if c["review"].get("track", "picked") != "picked" or any(k.endswith(".lib") for k in keys) or len(keys) < 2:
            continue
        versions = []
        for k in sorted(keys, key=blind_name):
            rep = json.loads((REVIEW / "checks" / f"{k}.json").read_text(encoding="utf-8"))
            sheet = None
            if rep.get("sheet") and Path(rep["sheet"]).exists():
                sheet = WORK / "judge" / f"{blind_name(k)}.png"
                writable(sheet).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(rep["sheet"], sheet)
            versions.append({"version": blind_name(k), "sheet": str(sheet) if sheet else None,
                             "status": rep.get("status"), "warnings": rep.get("warnings", []),
                             "measured": [{f: m.get(f) for f in ("rule", "tc", "what")}
                                          for m in rep.get("measured", [])]})
        ly = c["layer"]
        pieces.append({"piece": pid, "what": c["review"].get("what"),
                       "source": plain_source(c["review"].get("source", "")), "layout": ly.get("layout"),
                       "on_screen": f"{c['t0_tc']} to {c['t1_tc']}", "items": c.get("items_tc", []),
                       "versions": versions})
        if pick_key(picks.get(pid), index) not in keys:
            todo.append(pid)
    rulebook = ROOT.parent / "Global Assets" / "VIDEO_RULES.md"
    doc = {"task": "For each piece, pick the version that best meets the rulebook's graphics rules (Part 1, section "
                   "8: G1 to G21; R245: Claude's picks), from its contact sheet and its checks. Write the picks to "
                   f"{picks_p} as {{\"<piece>\": \"<version>\", ..., \"_about\": \"who picked, when, by what\"}} "
                   "and each pick's reason to the exercise's ONE_SHOT.md.",
           "rulebook": str(rulebook), "review": str(REVIEW), "picks": str(picks_p), "pieces": pieces}
    write_json(WORK / "judge_input.json", doc)
    print(f"{len(pieces)} piece(s) to judge -> {WORK / 'judge_input.json'}; {len(todo)} without a pick yet"
          + (f": {' '.join(todo)}" if todo else ""))


def work_conflict(work, manifest):
    """Why `work` can't be this manifest's work folder, or None: it is another exercise's (Section A's qs1a; one whose
    work.json, or a round under runs/, names another manifest), or it already holds pieces this manifest hasn't
    (picks.json, clip_index.json, scoreboard.json). A new exercise's costs, scoreboard and picks would otherwise mix
    into another's (Fable's wave 1 review, D1)."""
    work, manifest = Path(work).resolve(), Path(manifest).resolve()
    if work == SECTION_A_WORK.resolve() and manifest != SECTION_A_MANIFEST.resolve():
        return (f"{_rel(work)} is Section A's work folder ({_rel(SECTION_A_MANIFEST)}); give this exercise its own, "
                "research/overlay_build/<prefix>")
    mark = work / "work.json"
    if mark.exists():
        owner = json.loads(mark.read_text(encoding="utf-8")).get("manifest")
        if not owner or _abs(owner) != manifest:
            return f"{_rel(work)} is {owner or 'an unnamed manifest'}'s work folder (its work.json)"
    for rj_p in sorted((ROOT / "runs").glob("*/overlays_review_*/round.json")):
        try:
            rj = json.loads(rj_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if rj.get("work") and _abs(rj["work"]) == work and _abs(rj.get("manifest") or ".") != manifest:
            return f"{_rel(work)} is the work folder of {_rel(rj_p.parent)}, a round of {rj.get('manifest')}"
    ids = {o["id"] for o in json.loads(manifest.read_text(encoding="utf-8"))["overlays"]}
    held = {}
    for name, pieces in (("picks.json", lambda d: [k for k in d if not k.startswith("_")]),
                         ("clip_index.json", lambda d: [pid_of(v) for v in d.values()]),
                         ("scoreboard.json", lambda d: [pid_of(k) for k in d])):
        if (work / name).exists():
            for i in pieces(json.loads((work / name).read_text(encoding="utf-8"))):
                held.setdefault(i, set()).add(name)
    foreign = sorted(set(held) - ids)
    if foreign:
        files = sorted(set().union(*(held[i] for i in foreign)))
        return (f"{_rel(work)} already holds pieces this manifest hasn't ({' '.join(foreign[:12])}"
                f"{' ...' if len(foreign) > 12 else ''}, in {', '.join(files)}): another exercise's work folder")
    return None


def cmd_init(a):
    """A new review round's folder and its round.json (the inputs the constants come from with --review), and the work
    folder, given Section A's blind key when it has none (the same letter for the same builder in every video)."""
    import time
    src = Path(a.source_round).resolve()
    if not (src / "edit_plan.json").exists() or not [p for p in src.glob("*_full.xml") if p.name != "captions_full.xml"]:
        raise SystemExit(f"{src}: not a Premiere round's export (edit_plan.json and <run>_full.xml)")
    if not (src / "caption_titles.json").exists():
        print(f"warning: {src} has no caption_titles.json; xml copies it into the review folder")
    run = src.parent
    manifest = Path(a.manifest).resolve()
    steps = Path(a.steps).resolve() if a.steps else manifest.parent / "steps_full.json"
    for p in (manifest, steps):
        if not p.exists():
            raise SystemExit(f"{p} not found")
    review = Path(a.out) if Path(a.out).is_absolute() else run / a.out
    review = review.resolve()
    n = round_of(review)
    work = Path(a.work).resolve()
    art = Path(a.art).resolve() if a.art else ROOT / "research" / "overlay_ideas" / work.name / "art"
    why = work_conflict(work, manifest)                   # one exercise's costs, scoreboard and picks per folder
    if why:
        raise SystemExit(f"--work: {why}")
    held =[p.name for p in (review / "cards.json", review / "checks", review / "overlays") if p.exists()] + \
        [p.name for p in review.glob("*.prproj")]
    if held:                                              # R61: a round David may have opened is never written again
        raise SystemExit(f"{review} already holds a round ({', '.join(held)}): a new round gets a new folder (R61)")
    rj = {"round": n, "run": _rel(run), "source_round": _rel(src), "manifest": _rel(manifest), "steps": _rel(steps),
          "art": _rel(art), "work": _rel(work)}
    rj_p = review / "round.json"
    if rj_p.exists():
        old = json.loads(rj_p.read_text(encoding="utf-8"))
        if {k: v for k, v in old.items() if k != "made"} == rj:
            print(f"{rj_p}: already made with these inputs")
            return 0
        raise SystemExit(f"{rj_p} exists with other inputs; a new round gets a new folder")
    global GUARD
    GUARD = (review, work)
    write_json(rj_p, dict(rj, made=time.strftime("%Y-%m-%d %H:%M:%S")))
    mark = work / "work.json"                             # whose folder it is (Section A's qs1a is known by name)
    if work != SECTION_A_WORK.resolve() and not mark.exists():
        write_json(mark, {"manifest": _rel(manifest), "made": time.strftime("%Y-%m-%d %H:%M:%S")})
    key = work / "builders_key.json"
    if not key.exists():
        write_json(key, json.loads(BLIND_KEY.read_text(encoding="utf-8")))
        print(f"{key}: Section A's blind key ({_rel(BLIND_KEY)})")
    if not art.exists():
        print(f"note: no art folder yet ({art}); pieces that name art (props.art) need it")
    clash = sorted({o["id"] for o in json.loads(manifest.read_text(encoding="utf-8"))["overlays"]}
                   & foreign_ids(manifest).keys())
    if clash:
        print("warning: piece ids another exercise's manifest uses (cards will stop): " + " ".join(clash))
    print(f"round {n} -> {rj_p}\n  then: python tools/overlay_review.py cards --review={review}")
    return 0


MODEL_WORDS = r"Fable|Opus|Sonnet|Haiku|Gemini|GPT|Grok|Astra|Argon|Sol|Luna|Claude|Kling|DeepSeek|Kimi"
REVEALED = True                 # the blind test ended with David's picks (R163): markers may name each builder's model
MODEL_NAMES = {"argon": "Gemini 4 Argon", "opus": "Claude Opus 5.5", "sol": "GPT-6.1 Sol", "astra": "GPT-6 Astra",
               "fable": "Claude Fable 5.1", "claude": "Claude, the integrator"}


def plain_source(src):
    """A piece's source without the ideas run's model credits, e.g. 'shortlist A12 (Fable, Opus; ...)' -> 'shortlist
    A12': in a marker beside 'Builder A' a model's name invites a guess at who built it (the blind test)."""
    return re.sub(rf"\s*\((?=[^)]*\b({MODEL_WORDS}))[^)]*\)", "", src).strip()


def pid_of(key):
    return key.split(".")[0]


def sound_events(ly):
    """The candidate sounds for a shown overlay, (edit time, kind): a whoosh under a chapter card, a pop as a chip,
    panel, aside or piece arrives, a tick per checklist item, word, region or pin, a flip per card, and the lock where
    a padlock shuts. One kind per overlay keeps the pass quiet (David's Quick Series has almost none)."""
    lay, items = ly.get("layout"), ly.get("items", [])
    if ly.get("sound_each"):                              # R158: a list whose every item ticks in (A14, A16)
        return [(it["at"], ly["sound_each"]) for it in items]
    if lay == "chapter_card":
        return [(ly["t0"], "whoosh")]
    if lay in ("checklist", "word_build", "region_map"):
        return [(it["at"], "tick") for it in items]
    if lay in ("flip_card", "calendar_flip"):
        return [(it["at"], "flip") for it in items]
    if lay == "mini_diagram":
        return [(it["at"] + (0.3 if it.get("kind") == "lock" else 0), "lock" if it.get("kind") == "lock" else "pop")
                for it in items if it.get("kind") != "arrow"]           # the padlock shuts 0.3 s after its word
    if lay == "map_pins":
        return [(it["at"], "tick") for it in items if it.get("kind") in ("pin", "city", "ticks")]
    if lay == "choice_panel":
        return [(it["at"], "pop") for it in items]
    if lay == "source_flow":                              # a pop as each part arrives, not on its text changes
        return [(it["at"], "pop") for it in items if it.get("key") in ("source", "dataset", "branch", "upload")]
    return [(items[0]["at"] if items else ly["t0"], "pop")]


def blind():
    return json.loads(BLIND_KEY.read_text(encoding="utf-8")) if BLIND_KEY.exists() else {}


def blind_name(key):
    """A clip's file name, which Premiere shows in its bins: the builder's blind letter, never its model."""
    pid, builder = key.split(".", 1)
    if builder == "lib":
        return key
    if builder == "claude":                               # the integrator's own pieces (not in the calibration)
        return f"{pid}.Integrator"
    letters = blind()
    if builder not in letters:
        raise SystemExit(f"{key}: builder {builder!r} isn't in the blind key ({BLIND_KEY}); refusing to name its clip")
    return f"{pid}.Builder-{letters[builder]}"


def cmd_build(_):
    from pipeline.edit.ppro import markers as mk, project
    project.build(writable(OUT))
    (xml,) = [p for p in OUT.glob("*_full.xml") if p.name != "captions_full.xml"]
    m = json.loads((OUT / "markers.json").read_text(encoding="utf-8"))
    if m["markers"]:
        print(json.dumps(mk.add(OUT / f"{xml.stem}.prproj", m["sequence"], m["markers"]), ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    rv = "the review folder `init` made (its round.json); none: Section A's round 4"
    ap.add_argument("--review", default=None, help=rv)
    common = argparse.ArgumentParser(add_help=False)      # --review after the subcommand too
    common.add_argument("--review", default=argparse.SUPPRESS, help=rv)
    sp = ap.add_subparsers(dest="cmd", required=True)
    i = sp.add_parser("init", help="a new exercise's review round: round.json")
    i.add_argument("source_round", help="runs/<run_id>/premiere_rN, the round the review sits on")
    i.add_argument("manifest", help="exercises/<ex>/overlays_review.json")
    i.add_argument("--out", required=True, help="the review folder, in the run (overlays_review_r1) or absolute")
    i.add_argument("--work", required=True, help="research/overlay_build/<prefix>: blind key, picks, builders' files")
    i.add_argument("--steps", help="default: steps_full.json beside the manifest")
    i.add_argument("--art", help="default: research/overlay_ideas/<the work folder's name>/art")
    sp.add_parser("cards", parents=[common])
    c = sp.add_parser("check", parents=[common])
    c.add_argument("key")
    r = sp.add_parser("render", parents=[common])
    r.add_argument("keys", nargs="*")
    r.add_argument("--all", action="store_true", help="render every passing version again")
    sp.add_parser("judge-input", parents=[common], help="what Claude's judge reads -> <work>/judge_input.json")
    x = sp.add_parser("xml", parents=[common])
    x.add_argument("--require-picks", action="store_true",
                   help="stop on a picked-track piece with several versions and no pick in <work>/picks.json")
    sp.add_parser("build", parents=[common])
    a = ap.parse_args(argv)
    if a.cmd == "init":
        return cmd_init(a)
    configure(a.review)
    return {"cards": cmd_cards, "check": cmd_check, "render": cmd_render, "judge-input": cmd_judge_input,
            "xml": cmd_xml, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)
