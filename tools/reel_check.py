"""The reel's measured checks (R248; the rulebook's V1), on Premiere's own exports of the reel's sequence.

    python tools/reel_check.py <reel_plan.json> [--suffix _r6b]
        # checks the exports exports<suffix>.json names; writes <reel>/checks<suffix>/checks.json and the frames the
        # review reads (Fable B4)

  * sound (S1, S10): each export's integrated loudness and true peak (ffmpeg's EBU R128 meter), within 1 LU of -14
    and at -1 dBTP or under; the narration's and the sound-ups' loudness apart (each span measured in stereo, the
    spans' power averaged), within 2 dB of each other; the talk export silent wherever only the narration plays (its
    track muted); a 10 ms window at every edge of a sound-up for a click;
  * no doubled voice: no narration line overlaps a sound-up, from the timeline;
  * the captions (C1 to C7, G15): every cue's box inside the frame and 12 px or more from everything the beat's own
    layer draws (its alpha, rendered alone at the cue's middle frame: the panels, labels and cards wherever they
    really are), never on the narrator's still; the talk export without them (the caption's box differs from the
    standalone's, and hardly a pixel elsewhere);
  * the graphics' text (G6, G7): each beat's last frame before its fade-out from the standalone export against the
    beat's layer alone at the same frame: every word OCR reads at 7:1 or more and on an opaque panel
    (pipeline.edit.checks.text_contrast, see_through);
  * every picture shot drawn in both exports (reel_build.footage_missing);
  * R248 round 7: the room-tone bed at its level in the standalone export's gaps (where it is up and no line, sound-up
    or whoosh plays: the median 50 ms window within 3 dB of the plan's, under 2% of them holes below -70 dBFS), and
    the talk export silent there (the bed muted with her voice);
  * R248 round 3: every beat change dips to black in both exports (the frame at the change under 4 of 255 on
    average), and each whoosh's loudest 400 ms in the standalone export between -26 and -14 LUFS (heard, never
    louder than the voice).
It refuses an export made from another version of the plan (timeline.json's plan digest).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np                                                  # noqa: E402

import reel                                                         # noqa: E402
import reel_build                                                   # noqa: E402
from pipeline.config import tool                                    # noqa: E402

CLEAR_PX = 12
NARRATOR_REACH_X = 660                      # round 1's still's right edge; a plan's narrator PNG gives its own


def png_box(path):
    """The alpha's bounding box of a frame-sized PNG (x0, y0, x1, y1), or None."""
    from PIL import Image
    return Image.open(path).getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()


def ebur(path, a=None, b=None):
    """Integrated LUFS and true peak (dBTP) of path (or its a..b seconds), in stereo as it plays."""
    cmd = [tool("ffmpeg"), "-hide_banner", "-nostats"] + (["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}"] if a is not None
                                                          else []) + ["-i", str(path), "-vn", "-af",
                                                                      "ebur128=peak=true", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    i = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", r)
    p = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", r)
    num = lambda v: float(v) if v not in (None, "-inf") else None
    return (num(i[-1]) if i else None, num(p[-1]) if p else None)


def spans_lufs(path, spans):
    """The spans' loudness together: each measured in stereo, their powers averaged by length (Fable F3: a mono fold
    under-reads wide stereo)."""
    tot, w = 0.0, 0.0
    for a, z in spans:
        lufs, _ = ebur(path, a, z)
        if lufs is not None:
            tot += (z - a) * 10 ** (lufs / 10)
            w += z - a
    return round(10 * np.log10(tot / w), 1) if w else None


def pcm(path, a, b, sr=48000):
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-ss", f"{a:.4f}", "-i", str(path), "-t", f"{b - a:.4f}",
                          "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32)


def db(x):
    return 20 * np.log10(np.sqrt(np.mean(x.astype(float) ** 2)) + 1e-9) if len(x) else -200.0


def frame(path, t, out, fps):
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{max(0.0, t - 0.5 / fps):.4f}", "-i", str(path),
                    "-frames:v", "1", "-vf", "scale=in_color_matrix=bt709:out_color_matrix=bt709", str(out)], check=True)
    return out


def screenshot_word(panel, note, box, word):
    """Whether a contrast finding's word is a screenshot's own (inside the image panel and not in the reel's own note
    under it: Fable F1), so it isn't the reel's text to fix."""
    if not box:
        return False
    norm = lambda x: "".join(ch for ch in x.lower() if ch.isalnum())
    if norm(word) and norm(word) in [norm(w) for w in note.split()]:
        return False
    return (panel["x"] <= box[0] and box[2] <= panel["x"] + panel["w"] and panel["y"] <= box[1]
            and box[3] <= panel["y"] + panel["h"])


def cue_frames(c, b, lay, fps):
    """The frames (in the beat) at which a cue's clearance is measured (J3): its last (the layer at its fullest, G2),
    its quarters (items rising in), and every key moment of a moving element inside the cue (the pointer's pop at its
    peak, its flight's start, middle and end)."""
    a, z = c["start_frame"] - b["f0"], c["end_frame"] - 1 - b["f0"]
    fr = {z} | {round(a + (z - a) * q) for q in (0.25, 0.5, 0.75)}
    p = lay.get("pointer")
    if p:
        peak = 2 / 3 if p.get("edge") else 0.542                # backOut(x, 1.0) and (x, 2.2) peak there (K3)
        for t in (p["at"] + 0.4 * peak, p["fly0"], (p["fly0"] + p["fly1"]) / 2, p["fly1"]):
            f = round(t * fps)
            if a <= f <= z:
                fr.add(f)
    return sorted(max(0, min(b["n"] - 1, f)) for f in fr)


def run(plan, suffix=""):
    from PIL import Image
    suffix = reel_build.check_suffix(suffix)
    d = plan["_dir"]
    out = d / f"checks{suffix}"
    (out / "frames").mkdir(parents=True, exist_ok=True)
    tl = json.loads((d / "timeline.json").read_text(encoding="utf-8"))
    ex = json.loads((d / f"exports{suffix}.json").read_text(encoding="utf-8"))
    if not (tl.get("plan_digest") == ex.get("plan_digest") == reel_build.plan_digest(plan)):   # Fable G1
        raise SystemExit("the exports, timeline.json and the plan aren't the same version: rebuild and export")
    fps = tl["fps"]
    sa, talk = Path(ex["standalone"]["path"]), Path(ex["talk"]["path"])
    res = {"findings": []}
    bad = lambda check, **kw: res["findings"].append({"check": check, **kw})
    nar = plan.get("narrator") or {}
    nj = d / "narrator" / "narrator.json"
    if nar.get("renders"):                                 # her renders' widest reach, as placed (round 6)
        if not nj.exists() or json.loads(nj.read_text(encoding="utf-8")).get("plan_digest") != reel_build.plan_digest(plan):
            raise SystemExit("narrator/narrator.json is missing or of another plan: run reel_build.py xml (Fable N8)")
        reach = json.loads(nj.read_text(encoding="utf-8"))["reach_box"][2]
    else:
        reach = png_box(d / "public" / nar["png"])[2] if nar.get("png") else NARRATOR_REACH_X   # Fable r2 F4
    note = plan.get("note")
    note_box = png_box(d / "public" / note["png"]) if note else None
    note_beats = set(note["beats"]) if note else set()
    beat_of = lambda f: next((b["id"] for b in tl["beats"] if b["f0"] <= f < b["f0"] + b["n"]), None)

    # -- frames: both exports whole, no Media pending card
    for k, p in (("standalone", sa), ("talk", talk)):
        n = reel.video_frames(p)
        res[f"{k}_frames"] = n
        if n != tl["frames"]:
            bad("length", what=f"{k} has {n} frames, the sequence {tl['frames']}")
        late = reel_build.pending(p, fps)
        if late:
            bad("media pending", what=f"{k} shows Premiere's Media pending card", at=late[:10])
        gone = reel_build.footage_missing(plan, p)
        if gone:
            bad("footage", what=f"{k} doesn't show its footage", at=gone[:10])

    # -- sound
    res["standalone_lufs"], res["standalone_tp"] = ebur(sa)
    res["talk_lufs"], res["talk_tp"] = ebur(talk)
    for k in ("standalone", "talk"):
        lufs, tp = res[f"{k}_lufs"], res[f"{k}_tp"]
        if lufs is None or abs(lufs - reel_build.TARGET_LUFS) > 1.0:
            bad("loudness", what=f"the {k} export measures {lufs} LUFS, not within 1 LU of {reel_build.TARGET_LUFS}")
        if tp is None or tp > -1.0:
            bad("true peak", what=f"the {k} export's true peak is {tp} dBTP, over -1")
    nar = [(x["at"] / fps, x["at"] / fps + x["length"]) for b in tl["beats"] for x in b["lines"]]
    ups = [(u["at"] / fps, (u["at"] + u["len"]) / fps) for b in tl["beats"] for u in b["sound_ups"]]
    res["narration_lufs"] = spans_lufs(sa, nar)
    res["sound_ups_lufs"] = spans_lufs(sa, ups)
    if None in (res["narration_lufs"], res["sound_ups_lufs"]) or abs(res["narration_lufs"] - res["sound_ups_lufs"]) > 2:
        bad("balance", what=f"narration {res['narration_lufs']} against the sound-ups {res['sound_ups_lufs']} LUFS")
    quiet = []
    for a, z in nar:                                  # the talk export: nothing where only the narration plays
        lvl = db(pcm(talk, a + 0.05, z - 0.05))
        if lvl > -60:
            quiet.append({"at": round(a, 2), "db": round(lvl, 1)})
    res["talk_under_narration"] = quiet
    if quiet:
        bad("talk sound", what=f"the talk export isn't silent under {len(quiet)} narration line(s)", at=quiet[:5])
    rt = tl.get("room_tone")                          # R248 round 7: the bed where it is up and nothing else plays
    if rt:
        busy = ([(a - 0.2, z + 0.2) for a, z in nar] + [(a - 0.1, z + 0.1) for a, z in ups]
                + [(w["at"] / fps - 0.1, w["at"] / fps + 0.8) for w in tl.get("whooshes", [])])
        ts = []
        for a, z in rt["up_spans_s"]:
            t = a + 0.1
            while t + 0.05 < z - 0.1:
                if not any(u0 < t + 0.05 and t < u1 for u0, u1 in busy):
                    ts.append(t)
                t += 0.05
        def levels(pth, ts):                          # 50 ms windows, read in one pass per export
            x = pcm(pth, 0, tl["frames"] / fps)
            n = int(0.05 * 48000)
            return [db(x[int(t * 48000):int(t * 48000) + n]) for t in ts]
        s_lv, t_lv = levels(sa, ts), levels(talk, ts)
        res["room_tone"] = {"windows": len(s_lv), "standalone_median_dbfs": round(float(np.median(s_lv)), 1) if s_lv else None,
                            "standalone_holes": int(sum(v < -70 for v in s_lv)),
                            "talk_max_dbfs": round(float(max(t_lv)), 1) if t_lv else None, "target_dbfs": rt["rms_dbfs"]}
        r_ = res["room_tone"]
        if not s_lv or abs(r_["standalone_median_dbfs"] - rt["rms_dbfs"]) > 3 or r_["standalone_holes"] > 0.02 * len(s_lv):
            bad("room tone", what=f"the bed doesn't hold its level in the standalone export's gaps: {r_}")
        if t_lv and r_["talk_max_dbfs"] > -70:
            bad("room tone", what=f"the talk export isn't silent in the gaps (its room tone muted): {r_}")
    clicks = []
    for a, z in ups:                                  # every sound-up edge, 10 ms in from it
        for t in (a, z - 0.01):
            lvl = db(pcm(sa, t, t + 0.01))
            if lvl > -30:
                clicks.append({"at": round(t, 3), "db": round(lvl, 1)})
    res["edges"] = clicks
    if clicks:
        bad("edges", what="a sound-up starts or ends loud (a click risk)", at=clicks)
    doubled = [(round(a, 2), round(u0, 2)) for a, z in nar for u0, u1 in ups if a < u1 and u0 < z]
    if doubled:
        bad("doubled voice", what="a narration line overlaps a sound-up", at=doubled)

    # -- R248 round 3: the dips at the beat changes, the whooshes' level
    dips = []
    for f in tl.get("fades", {}).get("at", []):
        for k, pth in (("standalone", sa), ("talk", talk)):
            im = Image.open(frame(pth, f / fps, out / "frames" / "_dip.png", fps)).convert("L")
            lvl = float(np.asarray(im, float).mean())
            dips.append({"at": round(f / fps, 3), "export": k, "mean": round(lvl, 1)})
            if lvl > 4:                                 # (a frame off reads 8 to 10 over the teal room)
                bad("fade", what=f"the {k} export isn't black at the beat change at {f / fps:.2f} s ({lvl:.1f})")
    for f in tl.get("fades", {}).get("joins", []):        # a joined change dissolves, never dark (both exports, J6)
        for k, pth in (("standalone", sa), ("talk", talk)):
            im = Image.open(frame(pth, f / fps, out / "frames" / "_dip.png", fps)).convert("L")
            lvl = float(np.asarray(im, float).mean())
            dips.append({"at": round(f / fps, 3), "export": k, "mean": round(lvl, 1), "join": True})
            if lvl < 20:
                bad("join", what=f"the {k} export's joined beat change at {f / fps:.2f} s goes dark ({lvl:.1f})")
        nb = next((x for x in plan["beats"] if x["id"] == beat_of(f)), {})
        if (nb.get("enter") or {}).get("fly"):                 # the far side flies in under it: not a still blend;
            dips.append({"at": round(f / fps, 3), "join_blend": "skipped: the far side flies in"})   # (never dark:
            continue                                                                                  # checked above)
        jf = reel.join_frames(fps)                             # mid-dissolve is a blend of its ends (Fable K6)
        ends_ = [np.asarray(Image.open(frame(sa, g / fps, out / "frames" / "_dip.png", fps)).convert("L"), float)
                 for g in (f - 1, f + jf // 2, f + jf + 1)]
        a0, m, a1 = ends_
        spread = float(np.abs(a1 - a0).mean())
        err = float(np.abs(m - (a0 + a1) / 2).mean())
        dips.append({"at": round(f / fps, 3), "join_blend_err": round(err, 1), "join_spread": round(spread, 1)})
        if spread < 5 or err > 0.35 * spread:
            bad("join", what=f"the joined change at {f / fps:.2f} s isn't a dissolve (mid-frame off the blend by "
                             f"{err:.1f}, the ends {spread:.1f} apart)")
    (out / "frames" / "_dip.png").unlink(missing_ok=True)
    res["dips"] = dips
    wl = []
    for w in tl.get("whooshes", []):
        a = w["at"] / fps
        cut = out / "frames" / "_whoosh.wav"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", str(sa), "-t", "0.8",
                        "-vn", "-c:a", "pcm_s16le", str(cut)], check=True)
        m = reel_build.momentary_max(cut)
        cut.unlink(missing_ok=True)
        wl.append({"at": round(a, 2), "beat": w["beat"], "momentary_lufs": m})
        if m is None or not -26 <= m <= -14:
            bad("whoosh", what=f"the whoosh at {a:.2f} s peaks at {m} LUFS momentary, not between -26 and -14")
    res["whooshes"] = wl

    # -- each beat's layer alone: at its last frames (the graphics check) and at every cue's middle (the captions')
    cap = json.loads((d / "caption_titles.json").read_text(encoding="utf-8"))
    beats = {x["id"]: x for x in plan["beats"]}
    jobs, ends, cue_alpha = [], [], []
    for b in tl["beats"]:
        beat = beats[b["id"]]
        if not beat.get("layer"):
            continue
        props = {"durationInFrames": b["n"], "fps": fps, "width": 1920, "height": 1080,
                 "layer": reel.layer_props(plan, beat)}
        fd = tl.get("fades", {}).get("half_frames", 0)
        if b["f0"] + b["n"] in tl.get("fades", {}).get("joins", []):
            fd = 0                                     # a joined card fades out after its end, in the next beat (J1)
        k = b["n"] - 2 - fd                            # the beat's last frames before its fade-out: every item up
        png = frame(sa, (b["f0"] + k) / fps, out / "frames" / f"{b['id']}_end.png", fps)
        jobs.append({"out": str(out / "frames" / f"{b['id']}_alpha.png"), "frame": k, "props": props})
        ends.append((b["id"], png, out / "frames" / f"{b['id']}_alpha.png", (b["f0"] + k) / fps))
        for i, c in enumerate(cap["cues"]):
            if b["f0"] <= c["start_frame"] < b["f0"] + b["n"]:
                for j, fr in enumerate(cue_frames(c, b, props["layer"], fps)):   # across the cue (J3)
                    p = out / "frames" / f"_cue{i:03d}_{j}_alpha.png"
                    jobs.append({"out": str(p), "frame": fr, "props": props})
                    cue_alpha.append((i, c, b["id"], p, round((b["f0"] + fr) / fps, 2)))
    reel.render(plan, jobs, "alpha")

    # -- captions
    for c in cap["cues"]:
        x, y, w, h = c["box"]
        if x < 0 or y < 0 or x + w > 1920 or y + h > 1080:
            bad("caption", what=f"cue at frame {c['start_frame']} leaves the frame", box=c["box"])
    flagged = set()                                   # one finding a cue and kind, whichever frame shows it first
    for i, c, bid, p, when in cue_alpha:
        a = np.asarray(Image.open(p).convert("RGBA").getchannel("A"))
        x, y, w, h = c["box"]
        near = a[max(0, y - CLEAR_PX):y + h + CLEAR_PX, max(0, x - CLEAR_PX):x + w + CLEAR_PX]
        if (near > 128).sum() > 0 and (i, "near") not in flagged:
            flagged.add((i, "near"))
            ys, xs = np.nonzero(near > 128)
            bad("caption", what=f"cue \"{c['text'][:30]}\" within {CLEAR_PX} px of the layer in {bid}", at=when,
                box=c["box"], at_px=[int(xs.min()) + max(0, x - CLEAR_PX), int(ys.min()) + max(0, y - CLEAR_PX)])
        if beats[bid]["layout"] == "card" and x < reach + CLEAR_PX and (i, "narrator") not in flagged:
            flagged.add((i, "narrator"))
            bad("caption", what=f"cue \"{c['text'][:30]}\" reaches the narrator in {bid}", box=c["box"])
        p.unlink(missing_ok=True)
    diffs = []                                        # the talk export without captions
    for c in cap["cues"]:
        t = (c["start_frame"] + c["end_frame"]) / 2 / fps
        fa = frame(sa, t, out / "frames" / "_a.png", fps)
        fb = frame(talk, t, out / "frames" / "_b.png", fps)
        A = np.asarray(Image.open(fa).convert("L"), float)
        B = np.asarray(Image.open(fb).convert("L"), float)
        x, y, w, h = c["box"]
        inside = float(np.abs(A[y:y + h, x:x + w] - B[y:y + h, x:x + w]).mean())
        mask = np.ones_like(A, bool)
        mask[y:y + h, x:x + w] = False
        if note_box and beat_of(c["start_frame"]) in note_beats:     # the standalone-only note isn't a caption (F1)
            nx0, ny0, nx1, ny1 = note_box
            mask[max(0, ny0 - 2):ny1 + 2, max(0, nx0 - 2):nx1 + 2] = False
        outside = int((np.abs(A - B)[mask] > 20).sum())        # pixels clearly different elsewhere (Fable F6)
        diffs.append({"t": round(t, 2), "inside": round(inside, 1), "outside_px": outside})
        if inside < 10 or outside > 400:
            bad("talk captions", what=f"at {t:.2f} s the talk export isn't the standalone without the caption "
                                      f"(inside {inside:.1f}, {outside} px different elsewhere)")
    res["talk_caption_diffs"] = diffs
    for f in (out / "frames" / "_a.png", out / "frames" / "_b.png"):
        f.unlink(missing_ok=True)

    # -- graphics' text: Premiere's frame against the layer alone at the same frame
    from pipeline.edit import checks
    shots_ = {}                                        # an image panel's own text (a screenshot's UI) isn't ours
    for b in plan["beats"]:
        lay = b.get("layer") or {}
        if (lay.get("panel") or {}).get("type") == "image":
            shots_[b["id"]] = (lay.get("windowBox") or reel.window(plan), lay["panel"].get("note", ""))
    inside = lambda bid, box, word: bid in shots_ and screenshot_word(shots_[bid][0], shots_[bid][1], box, word)
    for bid, png, alpha, t in ends:
        for f in checks.text_contrast(str(png), str(alpha), t, f"{bid}: ") + checks.see_through(str(alpha), t, f"{bid}: "):
            if f.get("word") and inside(bid, f.get("box"), f["word"]):
                res.setdefault("screenshot_text", []).append({"beat": bid, "word": f["word"], "ratio": f.get("ratio")})
                continue
            bad("graphics", beat=bid, **{k: v for k, v in f.items() if k in ("what", "message", "detail", "ratio",
                                                                            "word", "box", "share")} or f)
    res["graphics_frames"] = [str(e[1]) for e in ends]
    res["plan_digest"] = tl.get("plan_digest")                 # which build these checks are of (J10)
    (out / "checks.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("talk_caption_diffs", "graphics_frames")}, indent=1,
                     ensure_ascii=False)[:6000])
    return res


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("plan")
    ap.add_argument("--suffix", default="", help="the exports' suffix (reel_build.py export --suffix)")
    a = ap.parse_args()
    sys.exit(0 if not run(reel.load(a.plan), a.suffix)["findings"] else 1)
