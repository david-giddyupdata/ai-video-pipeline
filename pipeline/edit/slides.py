"""Motion graphics for the opening and the recap (R69): text slides over a still of the finished dashboard.

    python -m pipeline.edit.slides <exercise> <opening|recap> <out_dir> [--still=<image>] [--variant=improvement] [--render]

Reads exercises/<ex>/slides.json (the on-screen text; each item appears as its at_word is spoken), lines.json and the
voiced lines in audio_cache/ (pipeline.narration.build). Lays the sequence's lines end to end with the R25 gap, times
every slide and item from the word timings, and writes <out_dir>/slides_props.json with the audio and the still copied
beside it, so <out_dir> is Remotion's public dir. --render makes <out_dir>/<sequence>.mp4 (the Slides composition).

The still is the finished dashboard from the take: the runner screenshots the dashboard tab at the step marked
`"still"` (p5.15h, after the fix: R88), so a take passes --still=runs/<id>/dashboard_still.png. Until a take has one,
pass any image.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.config import EXERCISES, ROOT
from pipeline.edit.marks import word_time
from pipeline.narration import timing

REMOTION = ROOT / "remotion"
CACHE = ROOT / "audio_cache"
FPS, W, H = 30, 1920, 1080
LEAD_S = 0.8            # the first slide is up this long before the voice starts
SLIDE_GAP_S = 0.6       # extra pause where the slide changes (a beat, as R62's at a mode switch)
TAIL_S = 1.2            # the last slide holds this long after the voice ends
FONT = Path("C:/Windows/Fonts/arialbi.ttf")


def plan(exercise, sequence, still_name, variant=None):
    ex_dir = EXERCISES / exercise
    spec = json.loads((ex_dir / "slides.json").read_text(encoding="utf-8"))
    lines = json.loads((ex_dir / "lines.json").read_text(encoding="utf-8"))
    gap = json.loads((ex_dir / "edit_settings.json").read_text(encoding="utf-8"))["pacing"]["gap_between_lines"]
    order = spec["sequences"][sequence]
    slide_of = {ln: s for s in spec["slides"] for ln in s["lines"]}
    missing = [ln for ln in order if f"dash.{ln}" not in lines and ln not in lines]
    if missing:
        sys.exit(f"not voiced yet: {missing} (run pipeline.narration.build)")

    t, starts, audio, metas, prev = LEAD_S, {}, [], {}, None
    for ln in order:
        rec = lines.get(f"dash.{ln}") or lines[ln]
        meta = timing.of(rec)                         # R227: the times the line was built with
        if prev is not None:
            t += gap + (SLIDE_GAP_S if slide_of[ln] is not slide_of[prev] else 0.0)
        starts[ln], metas[ln] = t, meta
        audio.append({"src": f"{rec['key']}.mp3", "at": round(t, 3), "line": ln, "text": rec["text"]})
        t += rec["length_s"]
        prev = ln
    total = t + TAIL_S

    def at(item):
        w = word_time(metas[item["line"]], item["at_word"], item.get("occurrence", 1))
        if w is None:
            sys.exit(f"{item['line']}: word {item['at_word']!r} not in the line")
        return round(starts[item["line"]] + w, 3)

    def text(item):                       # R71: the approved variant for this take's case, if the item has one
        return item.get("variants", {}).get(variant, item["text"]) if variant else item["text"]

    slides = []
    seq_slides = [s for s in spec["slides"] if s["lines"][0] in order]
    for i, s in enumerate(seq_slides):
        start = 0.0 if i == 0 else starts[s["lines"][0]] - SLIDE_GAP_S / 2
        nxt = seq_slides[i + 1]["lines"][0] if i + 1 < len(seq_slides) else None
        end = total if nxt is None else starts[nxt] - SLIDE_GAP_S / 2
        out = {k: v for k, v in s.items() if k not in ("items", "columns", "lines")}
        out.update(start=round(start, 3), end=round(end, 3))
        if "items" in s:
            out["items"] = [{"text": text(it), "style": it.get("style", "item"), "at": at(it)} for it in s["items"]]
        if "columns" in s:
            out["columns"] = [{"title": c["title"], "at": at(c),
                               "items": [{"text": text(it), "style": it.get("style", "item"), "at": at(it)}
                                         for it in c["items"]]} for c in s["columns"]]
        slides.append(out)
    return {"fps": FPS, "width": W, "height": H, "durationInFrames": round(total * FPS), "still": still_name,
            "sequence": sequence, "audio": audio, "slides": slides}


def build(exercise, sequence, out_dir, still, variant=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    still = Path(still)
    still_name = "still" + still.suffix.lower()
    shutil.copyfile(still, out_dir / still_name)
    (out_dir / "fonts").mkdir(exist_ok=True)               # Arial Bold Italic, loaded by @font-face as remotion-motion does
    shutil.copyfile(FONT, out_dir / "fonts" / "arialbi.ttf")
    props = plan(exercise, sequence, still_name, variant)
    for a in props["audio"]:
        shutil.copyfile(CACHE / a["src"], out_dir / a["src"])
    path = out_dir / f"{sequence}_props.json"
    path.write_text(json.dumps(props, indent=2, ensure_ascii=False), encoding="utf-8")
    return path, props


def render(props_path, out_dir, sequence):
    out_dir, props_path = Path(out_dir).resolve(), Path(props_path).resolve()   # the render runs in remotion/
    out = out_dir / f"{sequence}.mp4"
    subprocess.run([shutil.which("npx") or "npx", "remotion", "render", "src/index.ts", "Slides", str(out),
                    f"--props={props_path}", f"--public-dir={out_dir}", "--codec=h264", "--crf=18", "--log=warn"],
                   cwd=REMOTION, check=True)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    ex, seq, out_dir = args
    props_path, props = build(ex, seq, out_dir, opts["still"], opts.get("variant"))
    print(props_path, f"{props['durationInFrames'] / FPS:.1f} s, {len(props['slides'])} slides")
    if "--render" in sys.argv:
        print(render(props_path, out_dir, seq))
