"""Premiere's own frames of a built project at given times, on one contact sheet (the round's frame check).

    python -m pipeline.edit.ppro.framecheck <built.prproj> <out_dir> <tc_or_s>[,<tc_or_s>...] [--sequence=<name>]

Opens the project through the AIDV bridge only when no project is open in Premiere (R104: never touch a project it
didn't open), exports each frame of the full sequence (QE exportFramePNG, pipeline.edit.ppro.project.frames), closes
it without saving, and writes <out_dir>/sheet.png with each frame's timecode. Times are seconds or HH:MM:SS:FF at
30 fps on the full sequence (R106).

    ... --exports[=h264|png|best]

R233: the same sheet from the round's two exports (pipeline.edit.ppro.exports: an H.264 and a PNG sequence of the
whole sequence, in the scratch folder), made first when there are none or the project was saved since: h264 (the
default) each exact frame from the H.264; png the PNG sequence's frame where it holds that exact frame, else one
exportFramePNG for it; best the PNG where it has the frame, else the H.264. Delete the exports when the round's work
is done: python -m pipeline.edit.ppro.exports clean <built.prproj>.
"""
import json
import sys
import time
from pathlib import Path

from pipeline.edit.ppro.bridge import call, start
from pipeline.edit.ppro.project import frames


def secs(v, fps=30):
    if ":" in v:
        h, m, s, f = (int(x) for x in v.split(":"))
        return h * 3600 + m * 60 + s + f / fps
    return float(v)


def tc(t, fps=30):
    f = round(t * fps)
    return f"{f // (3600 * fps):02d}:{f // (60 * fps) % 60:02d}:{f // fps % 60:02d}:{f % fps:02d}"


def check(prproj, out_dir, times, sequence):
    prproj, out_dir = Path(prproj).resolve(), Path(out_dir).resolve()
    print(json.dumps(start(), ensure_ascii=False))
    call("""(function () {
      if (app.projects.numProjects > 0) { throw new Error("a project is open in Premiere (" + app.projects[0].path + ")"); }
      if (!app.openDocument(%s)) { throw new Error("Premiere wouldn't open " + %s); }
      return true; })()""" % (json.dumps(str(prproj)), json.dumps(str(prproj))), timeout=300)
    try:
        ok = frames({"sequence": sequence}, times, out_dir)
        for attempt in range(4):                          # a just-opened project renders "Media pending" (yellow)
            late = [t for t in times if pending(out_dir / f"frame_{round(t * 1000):07d}.png")]   # until its media load
            if not late:
                break
            time.sleep(10)
            frames({"sequence": sequence}, late, out_dir)
        ok = [p.exists() and not pending(p) for p in (out_dir / f"frame_{round(t * 1000):07d}.png" for t in times)]
    finally:                                              # closed unsaved: a frame check changes nothing
        call("(function () { for (var k = 0; k < app.projects.numProjects; k++) { if (app.projects[k].path === %s)"
             " { app.projects[k].closeDocument(false, false); return true; } } return false; })()"
             % json.dumps(str(prproj)), timeout=120)
    return sheet(out_dir, times), ok


def pending(png):
    """Premiere's "Media pending" card: a flat yellow frame with the words in many languages. Most of the frame must
    be that yellow (measured 163 to 197 red, green 0.92 of red, blue under 70, dimmer under the edit's layers), so a
    gold title or a yellow chart isn't taken for it."""
    import numpy as np
    from PIL import Image
    if not png.exists():
        return False
    px = np.asarray(Image.open(png).convert("RGB").resize((64, 36)), dtype=np.float32).reshape(-1, 3)
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    yellow = (r > 120) & (g > 0.85 * r) & (g < r) & (b < 0.5 * g)
    # 0.3, not 0.6: with an overlay card and a caption over it the card measured 0.53 and passed as a frame (stage
    # round 7, the outro's first three); the highest real frame in 794 earlier frame-check frames measured 0.089
    return bool(yellow.mean() > 0.3)


def sheet(out_dir, times, w=960):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26)
    h = w * 9 // 16
    im = Image.new("RGB", (w * 2, h * ((len(times) + 1) // 2)), (20, 20, 20))
    for i, t in enumerate(times):
        p = out_dir / f"frame_{round(t * 1000):07d}.png"
        if not p.exists():
            continue
        fr = Image.open(p).convert("RGB").resize((w, h))
        d = ImageDraw.Draw(fr)
        d.rectangle((0, 0, 220, 38), fill=(20, 20, 20))
        d.text((10, 3), tc(t), font=font, fill=(255, 220, 0))
        im.paste(fr, ((i % 2) * w, (i // 2) * h))
    out = out_dir / "sheet.png"
    im.save(out)
    return out


def main(argv):
    seq = next((a.split("=", 1)[1] for a in argv if a.startswith("--sequence=")), None)
    src = next((a.split("=", 1)[1] if "=" in a else "h264" for a in argv if a.split("=")[0] == "--exports"), None)
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 3 or src not in (None, "h264", "png", "best"):
        raise SystemExit(__doc__)
    prproj, out_dir, spec = args
    if seq is None:                                       # the full sequence: "<run> full"
        from pipeline.edit.ppro.exports import _sequences_in
        seq, made = Path(prproj).stem.removesuffix("_full") + " full", _sequences_in(prproj)
        if seq not in made:                               # before Premiere opens anything
            if len(made) != 1:
                raise SystemExit(f"--sequence=: the project's XML made {made}")
            seq = made[0]
    times = [secs(v) for v in spec.split(",")]
    if src:                                               # R233: from the two exports
        from pipeline.edit.ppro import exports
        out, ok, got = exports.check(prproj, out_dir, times, seq, src)
        print(json.dumps({"sheet": str(out), "exported": sum(ok), "of": len(ok),
                          "from": {k: list(got.values()).count(k) for k in set(got.values())}}))
        return 0 if all(ok) else 1
    out, ok = check(prproj, out_dir, times, seq)
    print(json.dumps({"sheet": str(out), "exported": sum(ok), "of": len(ok)}))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
