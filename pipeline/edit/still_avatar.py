"""The still avatar (R245: the one-shot renders nothing in HeyGen, the avatar is one picture for the whole video, as
R229's still-first tests were): a frame of the look "David Baldwin" (R219), registered as a run's intro and outro
"renders", so pipeline.edit.pip (avatar_still), pipeline.edit.stage (plan_quick, voice) and the final read it as they
read a render.

    python -m pipeline.edit.still_avatar sheet <render> --out=<sheet.jpg>               # the frames to pick from
    python -m pipeline.edit.still_avatar make <render> --at=<s> [--why="..."] [--out=<still.png>] [--force-look]
    python -m pipeline.edit.still_avatar register <avatar steps.json> runs/<run_id> [--still=<still.png>]

sheet and make: <render> is an edge-fixed transparent render of the look in a run's graphics/ (the ProRes 4444
pipeline.edit.alpha.to_prores made, named in that run's avatar/avatar.json graphics_alpha), read from its first frame
to where its upload's voice starts (its renders_alpha voice_at_s: avatar.PAD_S of silence, where HeyGen idles with
the mouth closed, R100). The sheet shows the head of every frame there over the cityscape (pip.CITY, R232), each
labelled with its frame, its time and how far its eyes and its mouth stray from the window's median frame (a blink or
a lip movement stands out). make saves frame round(at * fps) as STILL (an RGBA PNG at the render's size, straight
alpha, its edges as the render's fix left them), a JSON beside it (the source, the time, the look id, why that frame)
and the sheet with that frame outlined (SHEET). Section A's still: the registered Avatar V intro, R237. A render of
another look than R219's is refused unless --force-look (its JSON then names only that look's id; register checks it
against the steps file's heygen.look).

register: for each step of the avatar steps file whose "graphics" is opening or recap, the upload main_alpha would
send HeyGen (avatar.padded: the line's cleaned clip with PAD_S of silence each side; for a step's carry_into, the main
body's first sentence after R82's part-boundary gap, R205), built but never sent; and the still held for exactly that
long as a VP9 WebM with alpha (graphics/<seq>_still_<tag>_alpha.webm, at the plan's rate, no sound: the stage takes
the voice from the upload, stage.voice). avatar.json gets renders_alpha[seq] (source "still", status "done", engine
"still" in its inputs, the upload, the file, the carry) and graphics_alpha[seq], as main_alpha writes them; a record
replaced moves to renders_alpha_history and graphics_alpha_history, as register_webapp does. The same inputs
registered again keep their records. The intro's record carries no box_until_main_s: its clip ends after the carried
sentence (round 6's way) and the box's still serves the rest of its first stay. A later paid render
(avatar.main_alpha) stops at "rendered from other inputs ... --rerender", on purpose. Nothing is paid or uploaded.
pipeline.edit.avatar --no-render keeps a registered still as it is (main_alpha skips its record; Fable, wave 1, E1).
The final with a still in the box: pipeline.edit.ppro.final_quick --still.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

from pipeline.config import EXERCISES, tool

ASSETS = Path(r"D:\Videos\Global Assets\avatar")
STILL = ASSETS / "david_baldwin_still_1080p.png"
SHEET = ASSETS / "david_baldwin_still_1080p_sheet.jpg"
LOOK = {"id": "<HEYGEN_LOOK_ID>", "name": "David Baldwin", "rule": "R219"}
SOURCE = ENGINE = "still"                 # renders_alpha's source and engine for a registered still
SEQS = ("opening", "recap")
GOP_S = 10                                # a keyframe every 10 s in the held WebM (a seek decodes from one)
# the sheet: the head of each frame, from a crop of the render's frame around the head (the top two fifths' opaque
# pixels, as pip.avatar_still finds the person), scaled; the eye and mouth bands as fractions of the crop's height
# (R219's look, seated: eyes about 0.45 down, mouth about 0.72)
CROP_W, CROP_H, CROP_ABOVE = 400, 520, 10
TILE_SCALE, COLS, LABEL_H, GAP = 0.6, 8, 24, 8
EYES, MOUTH = (0.36, 0.56), (0.63, 0.85)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render_record(render):
    """The run's avatar.json records of a render in its graphics/: (run_dir, seq, graphics_alpha, renders_alpha)."""
    render = Path(render).resolve()
    run_dir = render.parent.parent
    log_path = run_dir / "avatar" / "avatar.json"
    if not log_path.exists():
        raise SystemExit(f"{render} isn't in a run's graphics/ ({log_path} missing)")
    log = json.loads(log_path.read_text(encoding="utf-8"))
    for seq, g in (log.get("graphics_alpha") or {}).items():
        if (run_dir / g["file"]).resolve() == render:
            r = (log.get("renders_alpha") or {}).get(seq) or {}
            if r.get("source") == SOURCE:
                raise SystemExit(f"{render} is a registered still, not a render")
            return run_dir, seq, g, r
    raise SystemExit(f"{render} isn't a current graphics_alpha file of {log_path}")


def frames(render, n):
    """The render's first n frames as an n x h x w x 4 uint8 array, decoded in order (frame k is the k-th; no seek)."""
    from pipeline.edit import alpha
    v = next(x for x in alpha.probe(render)["streams"] if x.get("width"))
    w, h = v["width"], v["height"]
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", *alpha._decoder(render), "-i", str(render), "-frames:v",
                          str(n), "-f", "rawvideo", "-pix_fmt", "rgba", "-"], capture_output=True, check=True).stdout
    k = len(raw) // (w * h * 4)
    if k < n:
        raise SystemExit(f"{render}: {k} frames read, {n} wanted")
    return np.frombuffer(raw, np.uint8)[:n * w * h * 4].reshape(n, h, w, 4)


def window(render):
    """What sheet and make read: (run_dir, seq, renders_alpha record, fps as a Fraction, frames in the silence)."""
    from pipeline.edit import alpha, avatar
    run_dir, seq, _, r = render_record(render)
    v = next(x for x in alpha.probe(render)["streams"] if x.get("width"))
    fps = Fraction(v["r_frame_rate"])
    voice_at = r.get("voice_at_s", avatar.PAD_S)          # the upload's voice: its silence before (R100)
    n = int(np.ceil(float(voice_at * fps) - 1e-9))        # frames k with k / fps < voice_at
    return run_dir, seq, r, fps, n


def head_box(f):
    """The crop around the head (x0, y0, x1, y1) in the frame, from its alpha, as pip.avatar_still finds the person."""
    H, W = f.shape[:2]
    ys, xs = np.nonzero(f[: H * 2 // 5, :, 3] > 128)
    if not len(xs):
        raise SystemExit("no person in the frame")
    cx, top = int(np.median(xs)), int(ys.min())
    x0 = min(max(0, cx - CROP_W // 2), W - CROP_W)
    y0 = min(max(0, top - CROP_ABOVE), H - CROP_H)
    return x0, y0, x0 + CROP_W, y0 + CROP_H


def city(W, H):
    """The cityscape (pip.CITY, R232) cover-cropped to W x H, as float32 RGB."""
    from PIL import Image
    from pipeline.edit import pip
    return np.asarray(pip.cover(Image.open(pip.CITY).convert("RGB"), W, H), np.float32)


def over(f, bg):
    """f (h x w x 4, straight alpha) over bg (h x w x 3) as uint8 RGB."""
    a = f[..., 3:4].astype(np.float32) / 255
    return (f[..., :3].astype(np.float32) * a + bg * (1 - a)).round().astype(np.uint8)


def strays(heads):
    """How far each head crop's eye and mouth bands stray from the window's median crop (mean absolute difference in
    levels, over the composite): a blink or a lip movement stands out against the idle."""
    med = np.median(heads, axis=0)
    h = heads.shape[1]
    out = []
    for c in heads:
        d = np.abs(c.astype(np.float32) - med).mean(axis=2)
        out.append({"eyes": round(float(d[round(EYES[0] * h):round(EYES[1] * h)].mean()), 2),
                    "mouth": round(float(d[round(MOUTH[0] * h):round(MOUTH[1] * h)].mean()), 2)})
    return out


def _font(px):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", px)
    except OSError:
        return ImageFont.load_default()


def contact_sheet(render, out, chosen=None):
    """The sheet of the render's frames in its upload's leading silence (the module's docstring); chosen: a frame to
    outline. Returns (the sheet's path, the frames' measures)."""
    from PIL import Image, ImageDraw
    run_dir, seq, r, fps, n = window(render)
    fr = frames(render, n)
    x0, y0, x1, y1 = head_box(fr[0])
    bg = city(fr.shape[2], fr.shape[1])[y0:y1, x0:x1]
    heads = np.stack([over(f[y0:y1, x0:x1], bg) for f in fr])
    meas = strays(heads)
    tw, th = round(CROP_W * TILE_SCALE), round(CROP_H * TILE_SCALE)
    rows = -(-n // COLS)
    head_h = 40
    H, W = fr.shape[1:3]
    sw, sh = W // 4, H // 4                                 # the chosen frame whole, over the city and its matte
    grid_h = head_h + rows * (th + LABEL_H + GAP) + GAP
    sheet = Image.new("RGB", (COLS * (tw + GAP) + GAP, grid_h + ((sh + LABEL_H + GAP) if chosen is not None else 0)),
                      (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    d.text((GAP, 10), f"{Path(render).name} ({run_dir.name}, {seq}): frames 0 to {n - 1} ({float((n - 1) / fps):.2f} "
                      f"s) at {fps} fps, before the upload's voice at {float(r.get('voice_at_s', n / fps)):.2f} s; "
                      f"head x {x0}-{x1}, y {y0}-{y1}; e / m: eyes / mouth, mean levels off the window's median",
           fill=(230, 230, 230), font=_font(16))
    if chosen is not None:
        f = fr[chosen]
        sheet.paste(Image.fromarray(over(f, city(W, H))).resize((sw, sh), Image.LANCZOS), (GAP, grid_h))
        sheet.paste(Image.fromarray(f[..., 3]).convert("RGB").resize((sw, sh), Image.LANCZOS), (2 * GAP + sw, grid_h))
        d.text((GAP + 2, grid_h + sh + 3), f"chosen: frame {chosen} ({float(chosen / fps):.2f} s), over the cityscape "
                                           "and its matte", fill=(255, 200, 0), font=_font(15))
    for k, (c, m) in enumerate(zip(heads, meas)):
        X, Y = GAP + (k % COLS) * (tw + GAP), head_h + GAP + (k // COLS) * (th + LABEL_H + GAP)
        sheet.paste(Image.fromarray(c).resize((tw, th), Image.LANCZOS), (X, Y))
        if k == chosen:
            d.rectangle((X - 4, Y - 4, X + tw + 3, Y + th + LABEL_H + 3), outline=(255, 200, 0), width=4)
        d.text((X + 2, Y + th + 3), f"f{k:02d} {float(k / fps):.2f}s  e{m['eyes']:.1f} m{m['mouth']:.1f}",
               fill=(255, 200, 0) if k == chosen else (220, 220, 220), font=_font(15))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=90)
    return out, [{"frame": k, "t_s": round(float(k / fps), 4), **m} for k, m in enumerate(meas)]


def make(render, at, out=STILL, sheet=None, why=None, force_look=False):
    """The still: frame round(at * fps) of render, inside its upload's leading silence (R100), as an RGBA PNG; its
    JSON beside it; the contact sheet with that frame outlined. A render of another look than R219's only with
    force_look. Returns the JSON."""
    from PIL import Image
    render, out = Path(render).resolve(), Path(out).resolve()
    run_dir, seq, r, fps, n = window(render)
    k = round(at * fps)
    if not 0 <= k < n:
        raise SystemExit(f"--at={at}: frame {k}, outside the upload's leading silence (frames 0 to {n - 1}, R100)")
    if r.get("look") != LOOK["id"] and not force_look:
        raise SystemExit(f"{render} is of look {r.get('look')}, not {LOOK['name']} ({LOOK['id']}, R219): "
                         "--force-look to take it anyway")
    sheet = Path(sheet) if sheet else (SHEET if out == STILL else out.with_name(out.stem + "_sheet.jpg"))
    sheet, meas = contact_sheet(render, sheet, chosen=k)
    f = frames(render, k + 1)[k]
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(f), "RGBA").save(out)
    meta = {"about": "The still avatar (R245, R229): one frame of the look's edge-fixed transparent render, inside its "
                     "upload's leading silence (R100: idling, mouth closed); registered as a run's intro and outro by "
                     "python -m pipeline.edit.still_avatar register.",
            "file": out.name, "size": [int(f.shape[1]), int(f.shape[0])],
            "mode": "RGBA, straight alpha, its edges as the render's fix left them (pipeline.edit.alpha.fix_edges)",
            "sha256": sha256(out), "look": dict(LOOK) if r.get("look") == LOOK["id"] else {"id": r.get("look")},
            "source": {"render": str(render), "run": run_dir.name, "graphics": seq,
                       **{k_: r[k_] for k_ in ("source", "engine", "file", "upload", "premultiplied", "voice_at_s",
                                                "notes") if k_ in r}},
            "t_s": round(float(k / fps), 4), "frame": k, "fps": str(fps),
            "window": {"s": [0, r.get("voice_at_s")], "frames": [0, n - 1],
                       "what": "the upload's leading silence (R100), before its voice"},
            "measures": meas[k], "why": why, "contact_sheet": str(sheet),
            "made_by": "python -m pipeline.edit.still_avatar make", "made": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cost_usd": 0.0}
    out.with_suffix(".json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    return meta


# ------------------------------------------------------------------------------------------------- the run's render
def hold(png, dst, n, fps):
    """png held for n frames at fps as a VP9 WebM with alpha (yuva420p, lossless: the alpha exact to a level, the
    colour off only by 4:2:0; about 1.4 MB for 48 s), no sound. Realtime speed 8: lossless either way, three times
    faster than good at 4 (14 s against 43 s for 1,431 frames, 2026-10-17)."""
    part = Path(dst).with_name("_part_" + Path(dst).name)
    fps = Fraction(fps).limit_denominator(1001)
    rate = f"{fps.numerator}/{fps.denominator}"
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-loop", "1", "-framerate", rate, "-i", str(png), "-frames:v",
                    str(n), "-an", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-lossless", "1", "-g",
                    str(round(GOP_S * float(fps))), "-auto-alt-ref", "0", "-row-mt", "1", "-deadline", "realtime",
                    "-cpu-used", "8", "-f", "webm", str(part)], check=True)
    part.replace(dst)
    return Path(dst)


def wav_s(path):
    """A WAV's length in seconds, from its samples."""
    import wave
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def register(steps_path, run_dir, still=STILL):
    """The module's docstring, register. Returns avatar.json's graphics_alpha records it wrote or kept."""
    from PIL import Image
    from pipeline.edit import alpha, avatar
    from pipeline.narration import timing
    run_dir, still = Path(run_dir).resolve(), Path(still).resolve()
    meta = json.loads(still.with_suffix(".json").read_text(encoding="utf-8"))
    sha = sha256(still)
    if meta.get("sha256") != sha:
        raise SystemExit(f"{still} changed since its JSON was written: make it again")
    doc = json.loads(Path(steps_path).read_text(encoding="utf-8"))
    lines = json.loads((EXERCISES / doc["exercise"] / "lines.json").read_text(encoding="utf-8"))
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    look, fps = meta["look"]["id"], plan["fps"]
    rate = Fraction(fps).limit_denominator(1001)          # 30.0 -> 30/1, 29.97 -> 30000/1001
    if (doc.get("heygen") or {}).get("look") not in (None, look):
        raise SystemExit(f"the steps file's look is {doc['heygen']['look']}, the still's {look}: a later render would "
                         "show another person")
    with Image.open(still) as im:
        W, H = im.size
    if (W, H) != (plan["width"], plan["height"]):
        raise SystemExit(f"{still.name} is {W}x{H}, the plan's frame {plan['width']}x{plan['height']}")
    pace = plan["settings"]["pacing"]
    gap = round(pace["gap_between_lines"] + pace["pause_at_part_boundary"], 3)     # R82, as main_alpha
    (run_dir / "avatar").mkdir(exist_ok=True)
    (run_dir / "graphics").mkdir(exist_ok=True)
    log_path = run_dir / "avatar" / "avatar.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {"renders": {}}
    rel = lambda q: os.path.relpath(q, run_dir / "avatar")          # avatar.json's paths are from avatar/
    save = lambda: log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    done = {}
    for step in doc["steps"]:
        seq = step.get("graphics")
        if seq not in SEQS:
            continue
        line = lines[step["narration"]["line_id"]]
        c = step.get("carry_into")
        inputs = {"audio_key": line["key"], "look": look, "engine": ENGINE, "resolution": f"{H}p",
                  "carry": [lines[c["line_id"]]["key"], c["until_word"], gap] if c else None, "pad_s": avatar.PAD_S,
                  "still": sha[:16]}
        tag = hashlib.sha256(json.dumps([inputs, fps], sort_keys=True).encode()).hexdigest()[:8]
        upload = run_dir / "avatar" / f"{seq}_upload_still_{tag}.wav"
        webm = run_dir / "graphics" / f"{seq}_still_{tag}_alpha.webm"
        r0 = (log.get("renders_alpha") or {}).get(seq) or {}
        g0 = (log.get("graphics_alpha") or {}).get(seq) or {}
        if (r0.get("source") == SOURCE and r0.get("inputs") == inputs and upload.exists() and webm.exists()
                and g0.get("file") == f"graphics/{webm.name}"):
            print(f"  {seq}: the still's record ({g0['file']}) has these inputs: kept")
            done[seq] = g0
            continue
        carry = tuple(inputs["carry"]) if c else None
        _, parts = avatar.padded(avatar.CACHE / f"{line['key']}.mp3", upload, carry,
                                 timing.provenance(lines[c["line_id"]]) if c else None)
        if carry:
            parts["carry"]["line_id"] = c["line_id"]
        up_s = wav_s(upload)
        n = round(up_s * fps)
        if not webm.exists():                             # its tag: the same inputs, picture and rate
            hold(still, webm, n, rate)
        dur = float(alpha.probe(webm)["format"]["duration"])
        if abs(dur - up_s) > 1 / fps + 1e-6:
            raise SystemExit(f"{webm.name} is {dur:.3f} s, its upload {up_s:.3f} s")
        r = {"status": "done", "source": SOURCE, "inputs": inputs, "line_id": step["narration"]["line_id"],
             "audio_key": line["key"], "audio_s": line["length_s"], "engine": ENGINE, "look": look,
             "pad_s": avatar.PAD_S, "file": rel(webm), "upload": rel(upload), **parts, "duration_s": round(dur, 4),
             "upload_s": round(up_s, 4), "frames": n, "fps": f"{rate.numerator}/{rate.denominator}",
             "still": {"png": str(still), "sha256": sha, "render": meta["source"]["render"], "t_s": meta["t_s"]},
             "cost_usd": 0.0, "made": time.strftime("%Y-%m-%dT%H:%M:%S")}
        renders = log.setdefault("renders_alpha", {})
        if seq in renders:
            log.setdefault("renders_alpha_history", []).append({"graphics": seq, **renders[seq]})
        renders[seq] = r
        g = {k: r[k] for k in ("line_id", "audio_key", "voice_at_s", "voice_s", "pad_s", "source", "engine")}
        g.update({"file": f"graphics/{webm.name}", "length_s": dur})
        if r.get("carry"):
            g["carry"] = r["carry"]
        g.update(timing.provenance_for(lines, g["line_id"], g["audio_key"]))     # R227, as main_alpha
        ga = log.setdefault("graphics_alpha", {})
        if seq in ga:
            log.setdefault("graphics_alpha_history", []).append({"graphics": seq, **ga[seq]})
        ga[seq] = g
        save()
        done[seq] = g
        print(f"  {seq}: graphics/{webm.name}, {dur:.3f} s ({n} frames at {fps} fps; upload {up_s:.3f} s), voice at "
              f"{g['voice_at_s']} s" + (f", the carried line at {g['carry']['at_s']} s" if g.get("carry") else ""))
    missing = [s for s in SEQS if s not in done]
    if missing:
        raise SystemExit(f"the steps file has no step for {missing} (a step's \"graphics\")")
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet", help="the contact sheet of a render's leading silence")
    s.add_argument("render")
    s.add_argument("--out", required=True, help="the sheet's path (never beside the render: the run's folder is "
                   "the run's)")
    m = sub.add_parser("make", help="the still, its JSON and the sheet")
    m.add_argument("render")
    m.add_argument("--at", type=float, required=True, help="seconds into the render, inside its upload's silence")
    m.add_argument("--out", default=str(STILL))
    m.add_argument("--why", default=None, help="why this frame (into the JSON)")
    m.add_argument("--force-look", action="store_true", help="take a render of another look than R219's")
    g = sub.add_parser("register", help="the still as a run's intro and outro render")
    g.add_argument("steps")
    g.add_argument("run_dir")
    g.add_argument("--still", default=str(STILL))
    a = ap.parse_args(argv)
    if a.cmd == "sheet":
        path, meas = contact_sheet(a.render, a.out)
        print(json.dumps({"sheet": str(path), "frames": meas}, indent=1))
    elif a.cmd == "make":
        print(json.dumps(make(a.render, a.at, a.out, why=a.why, force_look=a.force_look), indent=1,
                         ensure_ascii=False))
    else:
        print(json.dumps(register(a.steps, a.run_dir, a.still), indent=1))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
