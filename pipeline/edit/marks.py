"""Attention marks (SPEC §7.4; STYLE_PROFILE §4 and §8).

draw: drawn in the flow by the cursor, as David draws them live with Epic Pen. The cursor travels to the start point,
      then a rectangle is dragged corner to corner, or an arrow grows from tail to head with the cursor at its tip.
      Starts on the naming word, no fade-in. Like Epic Pen, where he keeps the button down until he has finished
      talking about that area, it holds until the sentence that names it ends (at least hold_s), then fades out.
fade: an edit layer for overview moments; fades in on the naming word, holds, fades out. No cursor gesture.

Boxes come from the run log (text_box events, measured by the runner in the page), or, for browser chrome such as the
address bar and for marks the log lacks, from Windows OCR on the source frame.
"""
import json
import re
import subprocess

from pipeline.config import ROOT, tool
from pipeline.edit.camera import dist

WINOCR = ROOT / "pipeline" / "privacy" / "winocr.ps1"


def release_time(meta, phrase, occurrence=1, until=None):
    """End (s, from the line's start) of the discussion of the named area: the end of `until` if given, else the end
    of the sentence containing `phrase`."""
    text, pos = meta["display_text"], -1
    for _ in range(occurrence):
        pos = text.find(phrase, pos + 1)
        if pos < 0:
            return None
    if until:
        u = text.find(until, pos)
        return next((w["end"] for w in meta["words"] if u >= 0 and w["char"][0] <= u < w["char"][1]), None)
    words = [w for w in meta["words"] if w["char"][1] > pos]
    for w in words:
        if text[w["char"][1]:w["char"][1] + 1] in ".?!":
            return w["end"]
    return words[-1]["end"] if words else None


def word_time(meta, phrase, occurrence=1):
    """Start (s, from the line's start) of the display word where `phrase` begins, or None."""
    text, pos = meta["display_text"], -1
    for _ in range(occurrence):
        pos = text.find(phrase, pos + 1)
        if pos < 0:
            return None
    return next((w["start"] for w in meta["words"] if w["char"][0] <= pos < w["char"][1]), None)


def ocr_box(run_dir, src_t, match, fps, band=None, whole_line=False, xband=None):
    """Find `match` in the source frame at src_t with Windows OCR; frame px (x0, y0, x1, y1), or None.
    band: (y0, y1) to search within, e.g. the browser chrome above the page. whole_line: the box of the whole text
    line the match is in (R84: a statement framed whole, not cut at a neighbouring word). xband: (x0, x1) the match's
    centre must fall in (more of a thing already found: near it, not elsewhere on the screen)."""
    d = run_dir / "marks_ocr" / f"{int(round(src_t * fps)):06d}"
    d.mkdir(parents=True, exist_ok=True)
    png = d / "frame.png"
    if not png.exists():
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{src_t:.3f}", "-i", str(run_dir / "raw.mp4"),
                        "-frames:v", "1", str(png)], check=True)
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(WINOCR), str(d)],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    want = re.sub(r"\s+", "", match).lower()
    for rec in (json.loads(l) for l in out.splitlines() if l.strip().startswith("{")):
        for line in _rows(rec["lines"]):
            ws = line["words"]
            for i in range(len(ws)):                     # the run of words whose text starts the match in word i
                acc = ""
                for j in range(i, len(ws)):
                    acc += ws[j]["t"].lower()
                    k = acc.find(want)
                    if 0 <= k < len(ws[i]["t"]):
                        sel = ws if whole_line else ws[i:j + 1]
                        box = (min(w["x"] for w in sel), min(w["y"] for w in sel),
                               max(w["x"] + w["w"] for w in sel), max(w["y"] + w["h"] for w in sel))
                        in_y = band is None or band[0] <= box[1] < band[1]
                        in_x = xband is None or xband[0] <= (box[0] + box[2]) / 2 <= xband[1]
                        if in_y and in_x:
                            return box
                        break
                    if len(acc) > len(ws[i]["t"]) + len(want):
                        break
    return None


def whole_tabs(png, boxes, pad):
    """R84: the browser tabs that hold the OCR boxes, whole (icon to close button), as a frame-px box that lay_out's
    rect_pad_px (`pad`) grows back onto the tabs' edges. Read from the frame: the strip's grey, the toolbar below it,
    and the active tab, which shares the toolbar's colour; every tab slot is as wide as the active tab (equal widths
    while the strip isn't full). None when no active tab is found (GOTCHAS: Edge's tab strip)."""
    tab = active_tab(png)
    if tab is None:
        return None
    L, w, y0, yb = tab["left"], tab["width"], tab["top"], tab["bottom"]
    ks = [int((b[0] + b[2]) / 2 - L) // w for b in boxes]
    return (L + min(ks) * w + pad, y0 + pad, L + (max(ks) + 1) * w - 1 - pad, yb - 1 - pad)


def active_tab(image):
    """The active tab in Edge's strip (a frame's PNG path or a PIL image): {left, width, top, bottom} in frame px;
    every tab slot is as wide (equal widths while the strip isn't full), so slot k is left + k * width. None when the
    strip or the tab isn't found (GOTCHAS: Edge's tab strip)."""
    import numpy as np
    from PIL import Image
    im = image if isinstance(image, Image.Image) else Image.open(image)
    a = np.asarray(im.convert("L")).astype(int)
    H, W = a.shape
    strip = float(np.median(a[2]))
    yb = next((y for y in range(8, H // 10) if abs(np.median(a[y]) - strip) > 12 and a[y].std() < 6), None)
    if yb is None:
        return None
    bar, probe = float(np.median(a[yb])), a[max(2, yb // 5)]
    runs, x = [], 0
    while x < W:                                          # the active tab: a run of the toolbar's colour in the strip
        if abs(probe[x] - bar) <= 3:
            x1 = x
            while x1 + 1 < W and abs(probe[x1 + 1] - bar) <= 3:
                x1 += 1
            if x1 - x >= 60:
                runs.append((x, x1))
            x = x1 + 1
        else:
            x += 1
    if not runs:
        return None
    L, R = max(runs, key=lambda r: r[1] - r[0])
    w, cx = R - L + 1, (L + R) // 2
    top = max((y for y in range(0, yb // 5 + 1) if abs(a[y, cx] - bar) > 3), default=None)
    if top is None:                                       # no edge above the tab: not the strip we know
        return None
    return {"left": int(L), "width": int(w), "top": int(top + 1), "bottom": int(yb)}


def _rows(lines):
    """OCR lines, then each row of lines that sit on one text line (a tool row 'Read' + 'CLAUDE.md' comes back as two
    lines), merged left to right, so a match can run across them."""
    out, rows = list(lines), []
    for line in sorted(lines, key=lambda l: (l["words"][0]["y"], l["words"][0]["x"])):
        y, h = line["words"][0]["y"], line["words"][0]["h"]
        row = next((r for r in rows if abs(r["y"] - y) <= max(4, 0.6 * max(h, r["h"]))), None)
        if row:
            row["lines"].append(line)
        else:
            rows.append({"y": y, "h": h, "lines": [line]})
    for r in rows:
        if len(r["lines"]) > 1:
            out.append({"words": [w for l in sorted(r["lines"], key=lambda l: l["words"][0]["x"]) for w in l["words"]]})
    return out


def overlay_box(edge, W, H):
    """Where an overlay card (R77) sits in output px: half the frame less the margins, on its edge, from 40 px down
    to 260 px above the bottom (remotion/src/Overlays.tsx: Card top mode), so the bottom caption row stays free,
    three narrow lines included."""
    w = W / 2 - 60
    x0 = 40 if edge == "left" else W - 40 - w
    return (x0, 40, x0 + w, H - 260)


def arrow_points(box, W, H, ms):
    """Head just outside the box on the side facing the frame centre; tail further toward the centre."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    dx, dy = W / 2 - cx, H / 2 - cy
    n = max(1e-6, (dx * dx + dy * dy) ** 0.5)
    dx, dy = dx / n, dy / n
    hw, hh = (box[2] - box[0]) / 2, (box[3] - box[1]) / 2
    edge = min(hw / abs(dx) if abs(dx) > 1e-6 else 1e9, hh / abs(dy) if abs(dy) > 1e-6 else 1e9)
    head = (cx + dx * (edge + ms["arrow_gap_px"]), cy + dy * (edge + ms["arrow_gap_px"]))
    tail = (head[0] + dx * ms["arrow_len_px"], head[1] + dy * ms["arrow_len_px"])
    return tail, head


def overview_path(mk, ms, W, H):
    """An overview arrow's travel (R48, R63): it grows in on its first stop, then moves to each next stop so it arrives
    as that stop is named, and rests there. It rests only on stops named while it is up: a stop named after the arrow's
    release is where it heads as it fades, still moving when it is gone (David's edit of the test arrow).
    mk: {t_name, t_release, box, stops: [{t_name, box}]}. Returns (keys [{t, from, to}], draw0, draw1, fade0)."""
    pt = lambda p: {"x": round(p[0], 1), "y": round(p[1], 1)}
    tail, head = arrow_points(mk["box"], W, H, ms)
    d0 = mk["t_name"] + ms["after_name_s"]
    d1 = d0 + ms["fade_in_s"]
    named = [s for s in mk.get("stops", [])]
    last_named = max([d1] + [s["t_name"] for s in named])
    release = max(d1 + ms["hold_s"], (mk.get("t_release") or 0) + ms["release_after_s"])
    keys = [{"t": round(d0, 4), "from": pt(tail), "to": pt(head)}]
    for s in named:
        a, b = arrow_points(s["box"], W, H, ms)
        here = keys[-1]
        if s["t_name"] >= release:                      # named too late to rest on: leave toward it through the fade,
            go = max(here["t"] + ms["min_hold_s"], release - ms["overview_exit_s"])   # after resting where it is
            release = max(release, go + ms["fade_s"])
            keys += [{**here, "t": round(go, 4)}, {"t": round(release + ms["fade_s"], 4), "from": pt(a), "to": pt(b)}]
            return keys, d0, d1, release
        go = max(here["t"], s["t_name"] - ms["travel_s"])
        keys += [{**here, "t": round(go, 4)}, {"t": round(max(go, s["t_name"]), 4), "from": pt(a), "to": pt(b)}]
    release = max(release, last_named + ms["hold_s"])
    return keys, d0, d1, release


def approach_s(a, b):
    """Same move length rule as the runner (pipeline/driver/runner.py)."""
    return min(1.0, max(0.4, 0.35 + dist(a, b) / 1800))


def lay_out(marks, moves, ms, W, H):
    """marks: [{step, kind, style, t_name, box}] in edit time and frame px. moves: the logged cursor moves in edit time.
    Adds each draw mark's gesture to the cursor path, chains every move from where the cursor really is, and returns
    (moves, mark layers, warnings)."""
    warnings, layers, gestures = [], [], []
    path = sorted(moves, key=lambda m: m["t0"])
    for mk in sorted(marks, key=lambda m: m["t_name"]):
        b = mk["box"]
        if mk["kind"] == "rect":
            p = ms["rect_pad_px"]
            a, c = (b[0] - p, b[1] - p), (b[2] + p, b[3] + p)
        else:
            a, c = arrow_points(b, W, H, ms)
        d0 = mk["t_name"] + ms["after_name_s"]
        if layers and d0 < layers[-1]["fade0"]:         # R51: one mark at a time; the next is drawn as the last fades
            if layers[-1]["fade0"] - d0 > 0.3:
                warnings.append(f"{mk['step']}: {mk['kind']} drawn {layers[-1]['fade0'] - d0:.2f}s after its word "
                                f"(the mark before it was still up)")
            d0 = layers[-1]["fade0"]
        layer = {"step": mk["step"], "kind": mk["kind"], "style": mk["style"], "from": {"x": round(a[0], 1), "y": round(a[1], 1)},
                 "to": {"x": round(c[0], 1), "y": round(c[1], 1)}}
        if mk["style"] == "draw":
            # where the cursor rests just before the gesture: the end of the last move before it
            before = [m for m in path + gestures if m["t1"] <= d0]
            rest = max(before, key=lambda m: m["t1"]) if before else None
            rest_pt = (rest["to"]["x"], rest["to"]["y"]) if rest else (W / 2, H / 2)
            m = approach_s(rest_pt, a)
            t0 = d0 - 0.05 - m
            if rest and t0 < rest["t1"]:
                shift = rest["t1"] - t0
                t0, d0 = t0 + shift, d0 + shift
                if shift > 0.3:
                    warnings.append(f"{mk['step']}: {mk['kind']} drawn {shift:.2f}s after its word (the cursor was busy)")
            t0 = max(0.0, t0)
            d1 = d0 + ms["draw_s"]
            gestures.append({"step": mk["step"], "t0": round(t0, 4), "t1": round(t0 + m, 4), "to": {"x": a[0], "y": a[1]},
                             "gesture": "approach"})
            gestures.append({"step": mk["step"], "t0": round(d0, 4), "t1": round(d1, 4), "to": {"x": c[0], "y": c[1]},
                             "gesture": mk["kind"]})
            if mk["kind"] == "arrow" and ms.get("retreat_px"):
                # the cursor's body hangs down-right of its tip and would cover what the arrow names: back off
                k = ms["retreat_px"] / max(1.0, dist(a, c))
                back = (c[0] + (a[0] - c[0]) * k, c[1] + (a[1] - c[1]) * k)
                gestures.append({"step": mk["step"], "t0": round(d1 + 0.2, 4), "t1": round(d1 + 0.55, 4),
                                 "to": {"x": back[0], "y": back[1]}, "gesture": "retreat"})
            release = max(d1 + ms["hold_s"], (mk.get("t_release") or 0) + ms["release_after_s"])
            layer.update(draw0=round(d0, 4), draw1=round(d1, 4), fade0=round(release, 4))
        elif mk["kind"] == "arrow" and mk.get("stops"):
            keys, d0, d1, release = overview_path(mk, ms, W, H)
            layer.update(path=keys, draw0=round(d0, 4), draw1=round(d1, 4), fade0=round(release, 4))
        else:
            release = max(d0 + ms["fade_in_s"] + ms["hold_s"], (mk.get("t_release") or 0) + ms["release_after_s"])
            layer.update(draw0=round(d0, 4), draw1=round(d0 + ms["fade_in_s"], 4), fade0=round(release, 4))
        # the next logged move cuts the hold short: the mark is gone before the cursor heads off (then the click)
        nxt = next((mv for mv in path if mv["t0"] >= layer["draw1"] - 1e-6), None)
        if nxt and nxt["t0"] < layer["fade0"] + ms["fade_s"]:
            layer["fade0"] = round(max(layer["draw1"] + ms["min_hold_s"], nxt["t0"] - ms["fade_s"]), 4)
            if nxt["t0"] < layer["fade0"]:
                warnings.append(f"{mk['step']}: next cursor move starts {layer['fade0'] - nxt['t0']:.2f}s before the "
                                f"{mk['kind']} fades")
        layer["fade1"] = round(layer["fade0"] + ms["fade_s"], 4)
        layers.append(layer)
    # one continuous path: every move starts where the cursor is
    out, here = [], None
    for mv in sorted(path + gestures, key=lambda m: m["t0"]):
        frm = here or mv.get("from") or {"x": W / 2, "y": H / 2}
        to = {"x": round(mv["to"]["x"], 1), "y": round(mv["to"]["y"], 1)}
        out.append({"step": mv["step"], "t0": mv["t0"], "t1": mv["t1"], "from": {"x": round(frm["x"], 1), "y": round(frm["y"], 1)},
                    "to": to, **{k: mv[k] for k in ("gesture", "mark", "live") if k in mv}})
        here = to
    return out, layers, warnings
