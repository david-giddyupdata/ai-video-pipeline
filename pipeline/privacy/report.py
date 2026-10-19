"""The advisory privacy report (S5; R56, SPEC §10): what a viewer could read that may be private, by video time.

    python -m pipeline.privacy.report runs/<run_id> [--no-second-reader]

OCRs the footage the edit keeps (one frame a second of the edited timeline, plus every click and result), so findings
in cut footage never appear. R227: RapidOCR reads again, beside Windows OCR and never instead, the frames where Windows
OCR read nothing or nearly matched a pattern (NEAR: a 12-digit run with OCR's look-alike letters in it, an @ with no
address, a key's prefix with no key); a finding that rests on RapidOCR alone says so ("reader": "rapidocr") and stays
open whatever its pattern's standing decision, since RapidOCR can invent a digit, and one whose span RapidOCR widened
says that ("widened_by": "rapidocr"). Windows OCR's sightings are placed first, so ids, spans and boxes are as before
when RapidOCR adds nothing. --no-second-reader, or the
exercise's edit_settings.json "privacy": {"second_reader": false}, turns it off. Each finding gives the video time span, the pattern, where on screen, a masked form of the
text and a thumbnail. Writes into the run folder:

  privacy_report.json   the findings; never the matched text itself (R4), only a masked form and a hash
  privacy/thumbs/       one thumbnail per finding (local, git-ignored, like the raw footage)
  privacy_decisions.json  David's choice per finding id: "blur", "ignore" or "retake". Kept across re-runs; the
                        planner turns "blur" into privacy_masks in edit_plan.json. Open findings block nothing.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.config import ROOT, tool
from pipeline.edit.camera import to_screen

WINOCR = ROOT / "pipeline" / "privacy" / "winocr.ps1"
PATTERNS = [                                    # SPEC §10
    ("email address", r"[\w.+-]+@[\w-]+\.[\w.]+"),
    ("12-digit number (an AWS account ID?)", r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"),
    ("Anthropic API key", r"sk-ant-[\w-]{8,}"),
    ("AWS access key", r"AKIA[0-9A-Z]{16}"),
    ("GitHub token", r"gh[pousr]_[A-Za-z0-9]{20,}"),
    ("key, secret or token assignment", r"[A-Z_]*(?:KEY|SECRET|TOKEN)[A-Z_]*\s*[=:]\s*\S{8,}"),
]
# R227: what Windows OCR nearly read as a pattern, each with the patterns it stands for: a frame where one turns up
# and none of those matched is read again. Windows OCR's misreads in our stills: l for 1, I for l, O for 0
NEAR = [
    ({"12-digit number (an AWS account ID?)"}, r"(?<!\w)[\dOoIl|]{4}[ -]?[\dOoIl|]{4}[ -]?[\dOoIl|]{4}(?!\w)"),
    ({"email address"}, r"[\w.+-] ?@ ?[\w-]"),       # text on both sides: Windows OCR reads icons as a lone "@"
    ({"Anthropic API key", "AWS access key", "GitHub token", "key, secret or token assignment"},
     r"sk-ant|AKIA|gh[pousr]_|(?i:key|secret|token)\s*[=:]"),
]
SAMPLE_S = 1.0
MERGE_GAP_S = 2.5                               # samples of the same finding this close make one span


def src_at(plan, t):
    seg = plan["segments"][0]
    for s in plan["segments"]:
        if s["t"] <= t:
            seg = s
    return seg["src_t"] if seg["type"] == "hold" else min(seg["src_in"] + (t - seg["t"]) * seg["speed"], seg["src_out"])


def masked(text):
    t = text.strip()
    return t[:2] + "…" + t[-2:] if len(t) > 6 else "…"


def where(box, W, H):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    row = "top" if cy < H / 3 else "bottom" if cy > 2 * H / 3 else "middle"
    col = "left" if cx < W / 3 else "right" if cx > 2 * W / 3 else "centre"
    return f"{row} {col}" if (row, col) != ("middle", "centre") else "centre"


def matches(rec, patterns=PATTERNS):
    """(pattern name, matched text, box in frame px) for every pattern hit in one OCR'd frame. The box spans the
    matched characters, a character's width to spare each side, not the whole OCR words: an account name inside a
    URL (R127) gets its own box, not the address bar's."""
    out = []
    for line in rec["lines"]:
        ws, text, spans = line["words"], "", []
        for w in ws:
            if text:
                text += " "
            spans.append((len(text), len(text) + len(w["t"])))
            text += w["t"]
        for name, pat in patterns:
            for m in re.finditer(pat, text):
                sel = [(w, a, b) for w, (a, b) in zip(ws, spans) if a < m.end() and b > m.start()]
                if sel:
                    (w0, a0, _), (w1, a1, _) = sel[0], sel[-1]
                    cw0, cw1 = w0["w"] / max(1, len(w0["t"])), w1["w"] / max(1, len(w1["t"]))
                    x0 = w0["x"] + max(0, m.start() - a0 - 1) * cw0
                    x1 = w1["x"] + min(len(w1["t"]), m.end() - a1 + 1) * cw1
                    out.append((name, m.group(0), (x0, min(w["y"] for w, *_ in sel), x1,
                                                   max(w["y"] + w["h"] for w, *_ in sel))))
    return out


def near_miss(rec, patterns):
    """R227: a frame Windows OCR read nothing on, or where it nearly matched a pattern (NEAR) without matching it, is
    one the second reader looks at again."""
    if not any(ln["words"] for ln in rec["lines"]):
        return True
    text = "\n".join(" ".join(w["t"] for w in ln["words"]) for ln in rec["lines"])
    hit = {n for n, pat in patterns if re.search(pat, text)}
    for names, pat in NEAR:
        if names & hit:
            continue
        for m in re.finditer(pat, text):
            if "12-digit number (an AWS account ID?)" in names and sum(c.isdigit() for c in m.group(0)) < 8:
                continue                                 # mostly letters: a word, not a misread number
            return True
    return False


def records2(pngs):
    """R227: RapidOCR's line records on the stills given ({str path: [{text, x, y, words}]})."""
    from pipeline.ml import ocr as ml_ocr
    return ml_ocr.second_read(pngs)


def with_exercise(extra):
    """The patterns a report looks for: the built-in ones and the exercise's own (edit_settings.json
    privacy.patterns). An exercise pattern named like a built-in one replaces it, in its place, with its own regex or,
    when it gives none, the built-in's: so the 12-digit account number can carry a standing decision (R127's "blur")
    without a second pattern of the same regex doubling every finding. The others follow the built-ins, in order."""
    built = dict(PATTERNS)
    own = {p["name"]: (p.get("regex") or built[p["name"]]) if p["name"] in built else p["regex"] for p in extra}
    return [(n, own.get(n, r)) for n, r in PATTERNS] + [(n, r) for n, r in own.items() if n not in built]


def report(run_dir, second_reader=True):
    run_dir = Path(run_dir).resolve()
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    fps, W, H, T = plan["fps"], plan["width"], plan["height"], plan["duration_s"]
    # the exercise's own patterns (edit_settings.json privacy.patterns, R127): each may carry a standing decision,
    # which a finding takes unless David's privacy_decisions.json says otherwise, and its own merge gap; one named
    # like a built-in pattern replaces it (with_exercise)
    extra = (plan.get("settings") or {}).get("privacy", {}).get("patterns", [])
    patterns = with_exercise(extra)
    default_decision = {p["name"]: p.get("decision", "open") for p in extra}
    merge_gap = {p["name"]: p.get("merge_gap_s", MERGE_GAP_S) for p in extra}
    times = [round(k * SAMPLE_S, 3) for k in range(int(T / SAMPLE_S) + 1)]
    times += [c["t"] for c in plan["cursor"]["clicks"]] + [c["t"] + 1.0 for c in plan["cursor"]["clicks"]]
    frames = {}                                  # source frame -> the edit times it is shown at
    for t in sorted(t for t in times if 0 <= t < T):
        frames.setdefault(int(round(src_at(plan, t) * fps)), []).append(t)
    work = run_dir / "privacy" / "frames"
    work.mkdir(parents=True, exist_ok=True)
    for n in frames:
        png = work / f"{n:06d}.png"
        if not png.exists():
            subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{n / fps:.4f}", "-i",
                            str(run_dir / plan["video"]), "-frames:v", "1", str(png)], check=True)
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(WINOCR), str(work)],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    hits, again = [], []
    for rec in (json.loads(l) for l in out.splitlines() if l.strip().startswith("{")):
        n = int(Path(rec["file"]).stem)
        if n not in frames:
            continue
        for name, text, box in matches(rec, patterns):
            for t in frames[n]:
                hits.append({"t": t, "src_n": n, "pattern": name, "text": text, "box": box, "reader": "windows"})
        if near_miss(rec, patterns):
            again.append(n)
    second = {"frames": 0, "findings": 0, "note": None}
    if second_reader and (plan.get("settings") or {}).get("privacy", {}).get("second_reader", True) and again:
        try:                                             # R227: on those frames only, beside Windows OCR
            r2 = records2([work / f"{n:06d}.png" for n in again])
        except Exception as e:                           # the venv or the GPU unavailable: Windows OCR's stand
            r2 = None
            second["note"] = f"not run: {type(e).__name__}: {str(e)[-200:]}"
        if r2 is not None:
            second["frames"] = len(again)
            for n in again:
                seen = {(h["pattern"], h["text"]) for h in hits if h["src_n"] == n}   # Windows OCR's own, kept
                rec = {"lines": r2[str((work / f"{n:06d}.png").resolve())]}
                for name, text, box in matches(rec, patterns):
                    if (name, text) in seen:
                        continue
                    for t in frames[n]:
                        hits.append({"t": t, "src_n": n, "pattern": name, "text": text, "box": box,
                                     "reader": "rapidocr"})
    # one finding per pattern, text and place, spanning the times it is on screen. Windows OCR's sightings come first,
    # in time order, so they make the findings exactly as before R227 (their ids, which David's decisions are keyed
    # by, their spans and their boxes); RapidOCR's then join a finding they fall within the merge gap of (widening
    # its span either way), or make their own
    findings = []
    for h in sorted(hits, key=lambda h: (h["reader"] != "windows", h["pattern"], h["text"], h["t"])):
        gap = merge_gap.get(h["pattern"], MERGE_GAP_S)
        f = next((f for f in findings if f["pattern"] == h["pattern"] and f["_text"] == h["text"]
                  and f["t0"] - gap <= h["t"] <= f["t1"] + gap
                  and abs(f["box"][1] - h["box"][1]) < 40 and abs(f["box"][0] - h["box"][0]) < 60), None)
        # (the same place: the account name in the address bar and in the header sit 37 px apart in y, and merged
        # into one box across the whole top strip until x was tested too, round 4)
        if f:
            if h["reader"] == "rapidocr" and not f["t0"] <= h["t"] <= f["t1"]:
                f["_widened"] = True                      # RapidOCR's sighting moves a span's end (listed, R227)
            f["t0"], f["t1"] = min(f["t0"], h["t"]), max(f["t1"], h["t"])
            f["src_n0"], f["src_n1"] = min(f["src_n0"], h["src_n"]), max(f["src_n1"], h["src_n"])
            f["_boxes"].append((h["reader"], list(h["box"])))   # the box is settled below, from every sighting
            continue
        digest = hashlib.sha256(h["text"].encode()).hexdigest()[:12]
        # the id survives a re-plan: pattern, text, the source second it first shows and where, as a third of the
        # screen (the same name in the address bar and the header, in the same second, got one id until the place was
        # added, round 4; a third is coarse enough that OCR's jitter of a few pixels keeps the id)
        place = where(h["box"], W, H)
        fid = hashlib.sha256(f"{h['pattern']}|{digest}|{round(h['src_n'] / fps)}|{place}".encode()).hexdigest()[:8]
        while any(f["id"] == fid for f in findings):      # two places in one third in one second: a suffix
            fid = hashlib.sha256(fid.encode()).hexdigest()[:8]
        findings.append({"id": fid, "pattern": h["pattern"], "_text": h["text"], "masked": masked(h["text"]),
                         "text_sha": digest, "t0": h["t"], "t1": h["t"], "src_n": h["src_n"], "src_n0": h["src_n"],
                         "src_n1": h["src_n"], "box": list(h["box"]), "_boxes": [(h["reader"], list(h["box"]))]})
    # a finding's box is the median of its sightings, not their union: one OCR reading that took in the header's
    # caret or the row below made round 4's name blur 30 px tall for 10 px text, and it covered part of Save &
    # publish (David moved every blur clip by hand, 2026-10-15)
    # (R227: from Windows OCR's sightings when it has any; RapidOCR's boxes sit 4 to 7 px taller than the letters)
    for f in findings:
        sightings = f.pop("_boxes")
        bs = [b for r, b in sightings if r == "windows"] or [b for _, b in sightings]
        f["box"] = [float(sorted(b[k] for b in bs)[len(bs) // 2]) for k in range(4)]
        if all(r == "rapidocr" for r, _ in sightings):
            f["reader"] = "rapidocr"                      # resting on RapidOCR alone
    # a standing pattern (bridge_gap_s, R127): sightings at the same place closer than that are one finding, so the
    # blur runs through the stretches where OCR can't read it (the header dimmed under a modal, up to 80 s in
    # Section A) but not across a real absence (a hover bubble seen twice, seven minutes apart)
    bridge = {p["name"]: p["bridge_gap_s"] for p in extra if p.get("bridge_gap_s")}
    if bridge:                                            # (Windows OCR's findings first, as above: R227)
        joined = []
        for f in sorted(findings, key=lambda f: (f.get("reader") == "rapidocr", f["pattern"], f["t0"])):
            g = bridge.get(f["pattern"])
            m = next((m for m in joined if g and m["pattern"] == f["pattern"] and f["t0"] - m["t1"] <= g
                      and m["t0"] - f["t1"] <= g
                      and abs(m["box"][1] - f["box"][1]) < 40 and abs(m["box"][0] - f["box"][0]) < 60), None)
            if m:                                         # (the earlier sighting's box, a median already, stands)
                if f.get("reader") == "rapidocr":         # (only RapidOCR's can lie before it, or widen it)
                    if f["t0"] < m["t0"] or f["t1"] > m["t1"]:
                        m["_widened"] = True
                    m["t0"], m["src_n0"] = min(m["t0"], f["t0"]), min(m["src_n0"], f["src_n0"])
                m["t1"], m["src_n1"] = max(m["t1"], f["t1"]), max(m["src_n1"], f["src_n1"])
            else:
                joined.append(f)
        findings = joined
    thumbs = run_dir / "privacy" / "thumbs"
    shutil.rmtree(thumbs, ignore_errors=True)
    thumbs.mkdir(parents=True)
    dec_path = run_dir / "privacy_decisions.json"
    decisions = json.loads(dec_path.read_text(encoding="utf-8")) if dec_path.exists() else {}
    from PIL import Image
    for f in findings:
        del f["_text"]
        if f.pop("_widened", False) and f.get("reader") != "rapidocr":
            f["widened_by"] = "rapidocr"                  # its blur runs longer on RapidOCR's word alone (R227)
        b = f["box"]
        (sx0, sy0) = to_screen(plan.get("camera") or [], f["t0"], (b[0], b[1]), W, H)
        (sx1, sy1) = to_screen(plan.get("camera") or [], f["t0"], (b[2], b[3]), W, H)
        f["where"] = where((sx0, sy0, sx1, sy1), W, H)
        f["t1"] = round(f["t1"] + SAMPLE_S, 3) if f["t1"] + SAMPLE_S <= T else T
        # a finding resting on RapidOCR alone never takes a standing decision: RapidOCR can invent a digit (R227)
        f["decision"] = decisions.get(f["id"], "open" if f.get("reader") == "rapidocr"
                                      else default_decision.get(f["pattern"], "open"))
        f["src_t0"], f["src_t1"] = round(f.pop("src_n0") / fps, 3), round(f.pop("src_n1") / fps + SAMPLE_S, 3)
        im = Image.open(run_dir / "privacy" / "frames" / f"{f['src_n']:06d}.png")
        pad = 120
        im.crop((max(0, b[0] - pad), max(0, b[1] - pad // 2), min(im.width, b[2] + pad),
                 min(im.height, b[3] + pad // 2))).save(thumbs / f"{f['id']}.png")
        f["thumb"] = f"privacy/thumbs/{f['id']}.png"
    findings.sort(key=lambda f: f["t0"])
    second["findings"] = sum(f.get("reader") == "rapidocr" for f in findings)
    doc = {"run_id": plan["run_id"], "plan_duration_s": T, "samples": len(frames),
           "patterns": [p for p, _ in patterns], "findings": findings, "second_reader": second,
           "note": "Advisory (R56): mark each finding blur, ignore or retake in privacy_decisions.json; open ones "
                   "block nothing. Masked text only (R4)."}
    (run_dir / "privacy_report.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc


def main(argv):
    if not [a for a in argv if not a.startswith("--")]:
        print(__doc__)
        return 2
    argv = [a for a in argv if not a.startswith("--")] + [a for a in argv if a.startswith("--")]
    doc = report(argv[0], second_reader="--no-second-reader" not in argv)
    sr = doc["second_reader"]
    print(f"{doc['samples']} frames read; {len(doc['findings'])} finding(s); second reader (R227): "
          + (sr["note"] or f"{sr['frames']} frame(s) read again, {sr['findings']} finding(s) on RapidOCR alone"))
    for f in doc["findings"]:
        m, s = divmod(f["t0"], 60)
        alone = ("  (RapidOCR alone)" if f.get("reader") == "rapidocr"
                 else "  (span widened by RapidOCR)" if f.get("widened_by") else "")
        print(f"  {int(m)}:{s:04.1f}-{f['t1']:.1f}s  {f['pattern']}, {f['where']}  {f['masked']}  [{f['decision']}]  "
              f"id {f['id']}{alone}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
