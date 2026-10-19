"""Region-dwell zoom (SPEC §7.2, §7.3; David's framing decisions and S4 notes of 2026-10-06).

The camera follows *beats*: moments when a box must be on screen (a click target as the cursor arrives, a mark as the
cursor sets off to draw it, the subject of a line as the line starts). Navigation needs *full* frame: a navigate step
until its URL has been shown (its marks released), and a click that opens a new tab from the click until the new
page has been seen. Between those:
  - zoom in as soon as the full-frame need ends (not waiting for the next line), on the coming beats that fit at `level`;
  - a beat outside the view: ease out slightly if everything still fits at `refit_min` (a wide mark stays on screen),
    otherwise pan to the beat's region (nearby work: pan, don't zoom out and back in);
  - zoom out at a click that opens a new tab; at a cut the change is instant and so unseen.
Moves are linear (R45). The camera rests at `level`; a step with `zoom.max` in steps.json (a tight spot) lets its
shot go further, up to the cap `max` (R42).

R123 (`zoom.safe_px`): every beat sits inside the title-safe area of the output frame, a margin per side, and a beat
marked `whole` (a dialog, panel or menu the line refers to) is shown whole. Where keeping the browser chrome out would
crowd a box against the top, the chrome shows whole. Without `safe_px` the camera keeps one margin, `margin_px`, on
every side (the dashboard exercise's framing, unchanged).

R125: `level` (1.35x) is the norm and zoom changes are rare. A whole dialog that fits at `level` is framed there; one
that doesn't is framed at its own size when the step says so (`fit: "own"`: the box fills the frame, no title-safe
margin, as the Windows Open dialog), else the planner leaves it out of the beats and the camera pans to what the lines
name inside it (`fit: "pan"`, the default). An ease-out (R43) never goes below `refit_min`; where that can't keep the
browser chrome out, the camera pans instead. Full frame is for navigation (R40, R44) and nothing else.

R157: a step whose action changes something the viewer must see whole (both charts after they fit, the dashboard as it
opens, the filter at work) gives `fit: "zoom"`: the camera zooms out until the box sits inside title-safe, full frame
at most. R156: with `reframe_on_level` (Section A) a tight step's beats get a closer shot of their own, then the
camera goes back to the rest level; the dashboard exercise keeps the old behaviour.

Camera keyframes are {t, s, x, y}: edit time, scale, and the source-frame point at the centre of the output. The
renderer interpolates linearly between keyframes and keeps the view inside the frame (remotion/src/camera.ts).
"""
import math

NAV_EXPECT = ("url_contains", "new_tab")


def clamp_centre(s, x, y, W, H):
    hw, hh = W / (2 * s), H / (2 * s)
    return min(max(x, hw), W - hw), min(max(y, hh), H - hh)


def cam_at(keys, t, W, H):
    """(s, x, y) at edit time t; same as remotion/src/camera.ts cameraAt."""
    if not keys:
        return 1.0, W / 2, H / 2
    k0 = keys[0]
    if t <= k0["t"]:
        s, x, y = k0["s"], k0["x"], k0["y"]
    else:
        s, x, y = keys[-1]["s"], keys[-1]["x"], keys[-1]["y"]
        for a, b in zip(keys, keys[1:]):
            if a["t"] <= t < b["t"]:
                u = (t - a["t"]) / (b["t"] - a["t"]) if b["t"] > a["t"] else 1.0
                s, x, y = a["s"] + (b["s"] - a["s"]) * u, a["x"] + (b["x"] - a["x"]) * u, a["y"] + (b["y"] - a["y"]) * u
                break
    x, y = clamp_centre(s, x, y, W, H)
    return s, x, y


def to_screen(keys, t, p, W, H):
    s, x, y = cam_at(keys, t, W, H)
    return (p[0] - x) * s + W / 2, (p[1] - y) * s + H / 2


def _union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def margins(z):
    """(left, top, right, bottom) in output px: R123's title-safe area, else margin_px on every side."""
    sp = z.get("safe_px")
    if sp:
        return sp["left"], sp["top"], sp["right"], sp["bottom"]
    m = z["margin_px"]
    return m, m, m, m


def _fit(box, z, W, H):
    if z.get("safe_px"):
        mL, mT, mR, mB = margins(z)
        return min((W - mL - mR) / max(1.0, box[2] - box[0]), (H - mT - mB) / max(1.0, box[3] - box[1]))
    m = z["margin_px"]
    w, h = box[2] - box[0] + 2 * m, box[3] - box[1] + 2 * m
    return min(W / w, H / h)


def safe_centre(box, s, z, W, H, page_top):
    """R123: the centre that puts box in the middle of the safe area at scale s, moved as little as needed to keep
    the browser chrome out, or, when that would crowd the box against the top, moved up to show the chrome whole."""
    mL, mT, mR, mB = margins(z)
    want_x = (box[0] + box[2]) / 2 - ((mL + W - mR) / 2 - W / 2) / s
    want_y = (box[1] + box[3]) / 2 - ((mT + H - mB) / 2 - H / 2) / s
    hw, hh = W / (2 * s), H / (2 * s)
    span = lambda lo, hi, want: min(max(want, lo), hi) if lo <= hi else (lo + hi) / 2
    x = span(box[2] + mR / s - hw, box[0] - mL / s + hw, want_x)     # the box inside the safe area, left to right
    y_lo, y_hi = box[3] + mB / s - hh, box[1] - mT / s + hh            # and top to bottom
    y = span(y_lo, y_hi, want_y)
    if z.get("crop_chrome") and H / s <= H - page_top:                 # in the page: keep the browser chrome out
        no_chrome = page_top + hh
        if no_chrome <= y_hi:
            y = max(y, no_chrome)
        elif y_lo <= hh <= y_hi:                                       # it would crowd the top: show the chrome whole
            y = hh
    return clamp_centre(s, x, y, W, H)


def plan_shots(beats, fulls, cuts, z, W, H, page_top, T):
    """beats: [{t, box, step}] (edit s, frame px); fulls: [{t0, t1, step}]; cuts: edit times of hard cuts.
    Returns (keyframes, notes)."""
    notes = []
    if not z.get("enabled", True):
        return [], notes
    cap = min(z["max"], z.get("soft_factor", 1.5) * z.get("capture_px_per_output_px", 1.0))  # §7.3; David accepts 2x softness
    FULL = {"s": 1.0, "x": W / 2, "y": H / 2}

    base = z["level"]
    lvl = lambda e: max(base, e.get("level") or base)                    # a tight-spot step (zoom.max) may go further
    safe = bool(z.get("safe_px"))
    mL, mT, mR, mB = margins(z)
    whole_floor = z.get("whole_min_level", 1.0)                          # R123: a whole dialog zooms out to full frame
    reframe = bool(z.get("reframe_on_level"))                            # R156 (Section A): see the beat loop
    floor_of = lambda es, fl: min(fl, whole_floor) if any(e.get("whole") for e in es) else fl

    def shot(boxes, floor=None, level=None, strict=False, align=None):
        """The shot that frames boxes: None when none fits above floor. strict: None too when no shot above floor
        keeps a strip of browser chrome out (an ease-out then gives way to a pan, R125); otherwise the shot with the
        strip is returned, as before, since a beat left unframed would mean full frame for nothing. align "left": the
        box against the left of title-safe, not centred, so a caption has room on the right (R157)."""
        box = _union(boxes)
        s = min(level or base, cap, _fit(box, z, W, H))
        whole_ok = (floor or z["min_level"]) <= 1.0                     # a whole dialog: full frame at least
        if s < (floor or z["min_level"]):
            return dict(FULL) if whole_ok else None
        if s <= 1.0 or (safe and whole_ok and s < z["min_level"]):       # nothing smaller than the screen, nor a
            return dict(FULL)                                            # 1.05x wobble on a near-screen-sized dialog
        if safe:
            s = math.floor(s * 1000) / 1000                              # stored rounded down: the box still fits
            cx, cy = safe_centre(box, s, z, W, H, page_top)
            top = cy - H / (2 * s)
            if z.get("crop_chrome") and 0.5 < top < page_top - 0.5:     # a strip of browser chrome would show: zoom
                tries = []                                               # out until the view starts at the page, or
                if box[3] > page_top:                                    # shows the chrome whole (R123)
                    tries.append((H - mB) / (box[3] - page_top))
                tries.append((H - mB) / box[3])
                for s2 in sorted({math.floor(v * 1000) / 1000 for v in tries if v < s}, reverse=True):
                    if s2 < (floor or z["min_level"]) or s2 <= 1.0:   # never below the shot's floor: an ease-out
                        continue                              # stays above refit_min (R43, R125); a whole dialog
                    c2 = safe_centre(box, s2, z, W, H, page_top)      # below the floor goes full frame (the else)
                    t2 = c2[1] - H / (2 * s2)
                    if not 0.5 < t2 < page_top - 0.5 and fits({"s": s2, "x": c2[0], "y": c2[1]}, box):
                        s, (cx, cy) = s2, c2
                        break
                else:
                    if whole_ok:                              # no shot above the floor keeps the chrome strip out
                        return dict(FULL)
                    if strict:
                        return None
            if align == "left":
                cx = clamp_centre(s, box[0] - mL / s + W / (2 * s), cy, W, H)[0]
            return {"s": s, "x": round(cx, 1), "y": round(cy, 1)}
        else:
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            if z.get("crop_chrome") and H / s <= H - page_top:             # in the page: keep the browser chrome out
                cy = max(cy, page_top + H / (2 * s))
            cx, cy = clamp_centre(s, cx, cy, W, H)
        return {"s": round(s, 3), "x": round(cx, 1), "y": round(cy, 1)}

    def own_shot(box):
        """R125: a dialog the lines treat as a whole is framed at its own size: its box fills the frame with no
        title-safe margin (its own edge is the frame's edge), never below the screen's own size."""
        s = math.floor(min(W / max(1.0, box[2] - box[0]), H / max(1.0, box[3] - box[1])) * 1000) / 1000
        if s <= 1.0:
            return dict(FULL)
        cx, cy = clamp_centre(s, (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, W, H)
        return {"s": s, "x": round(cx, 1), "y": round(cy, 1)}

    def fits(c, box):
        s = c["s"]
        hw, hh = W / (2 * s), H / (2 * s)
        x0, y0 = max(0.0, c["x"] - hw), max(0.0, c["y"] - hh)          # a margin at the screen's own edge can't be had:
        x1, y1 = min(W, c["x"] + hw), min(H, c["y"] + hh)              # the view stops there (R123)
        edge = lambda v, lim: abs(v - lim) < 0.5
        tol = 0.5                                                        # px: rounding of stored keyframes
        return ((box[0] >= x0 + mL / s - tol or edge(x0, 0)) and (box[2] <= x1 - mR / s + tol or edge(x1, W)) and
                (box[1] >= y0 + mT / s - tol or edge(y0, 0)) and (box[3] <= y1 - mB / s + tol or edge(y1, H)) and
                x0 - tol <= box[0] and box[2] <= x1 + tol and y0 - tol <= box[1] and box[3] <= y1 + tol) if safe else \
               (c["x"] - hw + mL / s <= box[0] and box[2] <= c["x"] + hw - mR / s and
                c["y"] - hh + mT / s <= box[1] and box[3] <= c["y"] + hh - mB / s)

    events = sorted([("full", f["t0"], f) for f in fulls] + [("beat", b["t"], b) for b in beats],
                    key=lambda e: (e[1], e[0] != "full"))
    keys = [{"t": 0.0, **FULL}]
    add = lambda t, c: keys.append({"t": round(max(t, keys[-1]["t"]), 4), **c})
    cur, boxes, full_until, shot_start, cur_level, cur_whole = None, [], 0.0, None, base, False
    cur_want = base                                                      # the level the shot's beats asked for
    own_until, cur_own = 0.0, False                                      # a dialog framed at its own size (R125)

    def ahead(i, first):
        """The run of beats from events[i] on, up to the next full need, that fit together at their level (a whole
        dialog's beats share its box, so they group at the level the dialog allows). Returns (boxes, level, floor)."""
        group, level, members = [first["box"]], lvl(first), [first]
        if first.get("whole"):
            level = min(level, max(whole_floor, _fit(first["box"], z, W, H)))
        for kind, t, e in events[i + 1:]:
            if kind == "full" or e.get("whole") != first.get("whole") or e.get("t_end") != first.get("t_end"):
                break                                                    # a dialog's shot holds only its own beats
            if reframe and lvl(e) != lvl(first):                         # R156: a tight step's shot is its own
                break
            want = max(level, lvl(e)) if not e.get("whole") else min(level, max(whole_floor, _fit(e["box"], z, W, H)))
            lim = math.floor(min(want, cap) * 1000) / 1000 if safe else min(want, cap)   # shot() rounds down
            if e["t"] < full_until or (shot(group + [e["box"]], level=want, floor=floor_of(members + [e], z["min_level"]))
                                       or {}).get("s", 0) < lim - 1e-6:
                break
            group.append(e["box"])
            members.append(e)
            level = want
        return group, level, floor_of(members, z["min_level"])

    def close(t_out, delay=0.0, cut_by=None):
        nonlocal cur, shot_start
        if cur is None:
            return
        if t_out - keys[shot_start]["t"] < z["min_dwell_s"]:              # too short to be worth a zoom
            notes.append(f"zoom at {keys[shot_start]['t']:.1f}s lasts under {z['min_dwell_s']}s; full view")
            del keys[shot_start:]
        else:
            cut = next((c for c in cuts if t_out <= c <= min(t_out + z["ramp_s"] + 1.0,
                                                              cut_by if cut_by is not None else float("inf"))), None)
            if cut is not None:                                          # unseen across a cut
                add(cut - 0.001, cur)
                add(cut, FULL)
            else:
                add(t_out + delay, cur)
                add(t_out + delay + z["ramp_s"], FULL)
            notes.append(f"zoom out at {keys[-1]['t']:.1f}s" + (" (on the cut)" if cut is not None else ""))
        cur, shot_start = None, None

    for i, (kind, t, e) in enumerate(events):
        if kind == "full":
            close(e["t0"], e.get("delay", 0.0))
            full_until, cur_whole = max(full_until, e["t1"]), False
            continue
        if t < full_until - 1e-6:
            continue                                                     # the full frame is still needed
        if t < own_until - 1e-6:
            continue                                                     # inside a dialog framed at its own size
        if e.get("fit") == "own":                                        # R125: the dialog's box fills the frame
            nxt = own_shot(e["box"])
            if nxt == FULL:                                              # as big as the screen: full frame
                close(max(t - z["ramp_s"], keys[-1]["t"]), cut_by=t)
                full_until, cur_whole = max(full_until, e.get("t_end", t)), False
                notes.append(f"{e['step']}: full frame until {full_until:.1f}s, the whole of what it opened (R125)")
                continue
            if cur:
                add(t - z["pan_s"], cur)
                add(t, nxt)
            else:
                in0 = max(full_until, keys[-1]["t"], t - z["ramp_s"])
                shot_start = len(keys)
                add(in0, FULL)
                add(in0 + z["ramp_s"], nxt)
            own_until = e.get("t_end", t)
            notes.append(f"{e['step']}: {nxt['s']}x at ({nxt['x']:.0f}, {nxt['y']:.0f}) by {t:.1f}s, the whole of what "
                         f"it opened at its own size, until {own_until:.1f}s (R125)")
            cur, boxes, cur_level, cur_whole, cur_own = nxt, [e["box"]], base, True, True
            cur_want = lvl(e)
            continue
        # R123: a shot framed for a whole dialog holds only the dialog's own beats; the first beat after it closes is
        # framed afresh (a full-frame dialog shot would otherwise "fit" everything after it). The same for a dialog
        # framed at its own size (R125): its near-screen-sized view would "fit" the next dialog too (Fable's review,
        # round 4: 1.093x held 49 s past the Open dialog), so the first beat after it is re-framed, and the move
        # back starts as the dialog closes (R41), not only when that beat comes
        leaving_whole = (cur_whole and not e.get("whole")) or cur_own
        was_own, cur_own = cur_own, False
        # R156: with reframe_on_level, a beat of a tight step (zoom.max) gets its own closer shot even where the rest
        # view already shows it (typed text too small to read at 1.35x), and the first beat after it goes back to
        # the rest level; without it a tight step only goes further when a new shot starts (R42, the dashboard)
        level_change = reframe and cur is not None and abs(lvl(e) - cur_want) > 1e-6   # wanted, not what a dialog
                                                                        # clamped it to (Fable, round 6)
        if cur and fits(cur, e["box"]) and not leaving_whole and not level_change:
            boxes.append(e["box"])
            continue
        if cur:
            wide = None if (leaving_whole or e.get("whole") or level_change) else \
                shot(boxes + [e["box"]], floor=z["refit_min"], level=cur_level, strict=True)   # a new dialog: follow
            if wide is not None and wide == cur:                                  # it, not the union with what it covers
                boxes.append(e["box"])
                continue
            if wide:                                                     # ease out so the new box fits too
                add(t - z["ramp_s"], cur)
                add(t, wide)
                notes.append(f"{e['step']}: ease out to {wide['s']}x by {t:.1f}s so its box stays on screen")
                cur, boxes = wide, boxes + [e["box"]]
                continue
            group, glevel, gfloor = ahead(i, e)
            nxt = shot(group, level=glevel, floor=gfloor, align=e.get("align"))
            if nxt == FULL:                                              # a dialog too big to zoom on: zoom out, and
                close(max(t - z["ramp_s"], keys[-1]["t"]), cut_by=t)     # stay out until it closes (R123)
                full_until = max(full_until, e.get("t_end", t))
                cur_whole = False
                notes.append(f"{e['step']}: full frame until {full_until:.1f}s, the whole of what it opened (R123)")
                continue
            if nxt and (safe or e.get("whole")) and nxt == cur:          # framed so already: no keyframes
                boxes, cur_whole, cur_want = group, True, lvl(e)
                continue
            if nxt:
                t_pan = max(keys[-1]["t"], min(t - z["pan_s"], own_until)) if was_own else t - z["pan_s"]
                add(t_pan, cur)
                add(t_pan + z["pan_s"] if was_own else t, nxt)
                notes.append(f"{e['step']}: pan to {nxt['s']}x at ({nxt['x']:.0f}, {nxt['y']:.0f}) by "
                             f"{keys[-1]['t']:.1f}s" + (" (the whole of what it opened, R123)" if e.get("whole") else "")
                             + (" (back from the dialog's own size as it closes, R125)" if was_own else ""))
                cur, boxes, cur_level, cur_whole = nxt, group, glevel, bool(e.get("whole"))
                cur_want = lvl(e)
            else:
                close(t - z["ramp_s"])
                cur_whole = False
            continue
        group, glevel, gfloor = ahead(i, e)
        nxt = shot(group, level=glevel, floor=gfloor, align=e.get("align"))
        if not nxt:
            continue
        cur_whole = bool(e.get("whole"))
        if nxt == FULL:                                                  # a whole dialog seen in the full view: no zoom
            full_until = max(full_until, e.get("t_end", t))              # until it closes
            cur_whole = False
            notes.append(f"{e['step']}: full frame until {full_until:.1f}s, the whole of what it opened (R123)")
            continue
        in0 = max(full_until, keys[-1]["t"], t - (z["ramp_s"] if e.get("whole") else z["max_early_s"]))
        shot_start = len(keys)
        add(in0, FULL)
        add(in0 + z["ramp_s"], nxt)
        notes.append(f"{e['step']}: zoom in to {nxt['s']}x at ({nxt['x']:.0f}, {nxt['y']:.0f}) from {in0:.1f}s"
                     + (f" ({in0 + z['ramp_s'] - t:.1f}s after it was needed)" if in0 + z["ramp_s"] > t + 0.05 else ""))
        cur, boxes, cur_level = nxt, group, glevel
        cur_want = lvl(e)
    if cur is not None and T - keys[shot_start]["t"] < z["min_dwell_s"]:
        del keys[shot_start:]
    return (keys if len(keys) > 1 else []), notes


def is_nav_result(step, step_events):
    """The click leaves the page: a new tab, or the expectation is in another tab than the action's target. A step
    whose action has no target (a wait for Claude, a line over the picture) never is one: its camera stays where
    the work is (S7: the p2.09 marks in the panel at 2x, R72)."""
    act_tab = (step["action"].get("target") or {}).get("tab")
    return (any(e["phase"] == "tab_switch" and not (e.get("detail") or {}).get("closed") for e in step_events)
            or step["expect"]["kind"] == "new_tab"
            or (act_tab is not None and step["expect"].get("tab") not in (None, act_tab)))


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
