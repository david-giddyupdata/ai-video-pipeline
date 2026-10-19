"""The edit plan (SPEC §6.4, §8): narration laid out by the pacing rules, picture fitted to it by the cut rules.

    python -m pipeline.edit.plan runs/<run_id> <steps file> [--gap=cut|swipe|speed]

Reads the run log, calibration.json, lines.json and exercises/<ex>/edit_settings.json. Writes into the run folder:
  edit_plan.json   segments (clip / hold, in edited-timeline seconds), narration placements, cursor, captions, warnings
  captions.srt     from the display text and word timings (no speech recognition)
  audio/           the narration clips the plan uses, copied from audio_cache/

How the picture is fitted: each step keeps [cursor move - pre, action + after] and [result - before, result + V]. Source
between kept spans is a gap. Gaps of cut_above_s or less play at 1x; longer ones get the gap treatment (cut with a
crossfade, a swipe, or a speed-up). Each click then lands on its line's cue word: when the narration needs more time
than the gaps give, more of the real footage after the previous result is shown, and a freeze-frame hold makes up any
shortfall (holds over hold_warn_s are flagged).

S4 adds, all in edited-timeline time: the cursor path with the gestures that draw marks (pipeline.edit.marks), the
camera keyframes of the region-dwell zoom (pipeline.edit.camera), and captions kept clear of both. Steps the runner
skipped (only_if) are dropped with their lines.
"""
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.config import EXERCISES, ROOT, tool
from pipeline.edit import activity
from pipeline.edit import appear
from pipeline.edit import camera as cam
from pipeline.edit import click_sound
from pipeline.edit import marks as mk
from pipeline.edit import sentences
from pipeline.edit.slides import FONT
from pipeline.narration import timing
from pipeline.narration.clean import clean as clean_clip, wav_name
from pipeline.post.s1_report import load_log
from pipeline.post.s2_cursor import build_track

CACHE = ROOT / "audio_cache"


def video_seconds(path):
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def beats(events, tv):
    """Per step, the source (video) times the edit needs."""
    out = {}
    for e in events:
        sid = e["step_id"]
        if not sid:
            continue
        s = out.setdefault(sid, {"id": sid})
        ph, t = e["phase"], tv(e["t_mono"])
        if ph == "step_start":
            s["start"], s["kind"], s["cue"] = t, e["action"], (e.get("detail") or {}).get("cue_offset_s", 0.3)
        elif ph == "cursor_move_start":
            s.setdefault("move", t)                       # the first move (a live mark's travel, or the click's move)
            d = e.get("detail") or {}
            s["dragging"] = bool(d.get("drag"))           # a drag's carry, after the press (runner.drag)
            if d.get("gesture"):
                s["live"] = True
                g = s.setdefault("gestures", {}).setdefault(d.get("mark"), {})   # each live mark's legs (R128)
                if d["gesture"] == "approach":
                    g["approach0"] = t
                if d["gesture"] in ("rect", "arrow"):
                    s.setdefault("draw", (t, d.get("mark")))  # when the first live mark started drawing
                    g["draw0"] = t
            else:
                s["click_move"] = t                       # the move to the click, after any live marks
        elif ph == "cursor_arrive":
            d = e.get("detail") or {}
            if d.get("gesture") in ("rect", "arrow"):
                s.setdefault("gestures", {}).setdefault(d.get("mark"), {})["draw1"] = t   # the shape is complete
            s["drop" if s.get("dragging") else "arrive"] = t   # the last arrival: on the click target (a drag's
                                                               # press); a drag's release point is its drop
        elif ph == "dwell_end" and (e.get("detail") or {}).get("release"):
            s.setdefault("gestures", {}).setdefault((e.get("detail") or {}).get("mark"), {})["release"] = t
        elif ph == "step_skipped":
            s["skipped"] = True
        elif ph in ("type_start", "type_end"):            # a typing step's keys: a step's `drop` may cut by them
            s["type0" if ph == "type_start" else "type1"] = t
        elif ph == "action":
            s["act"] = t
        elif ph == "expect_met":
            s["result"] = t
        elif ph == "step_end":
            s["end"] = t
    return out


class Timeline:
    def __init__(self, fps, cuts):
        self.fps, self.cuts = fps, cuts
        self.segs, self.T, self.pending, self.warnings, self.notes = [], 0.0, None, [], []
        self.lapses = []                                  # (t0, t1) of each live time-lapse, edit s
        self.drop, self.dropped = [], set()               # source spans a step leaves out (its `drop`), and the
                                                          # ones already noted

    def clip(self, src_in, src_out, speed=1.0):
        if src_out - src_in <= 1e-3:
            return
        for a, z, sid, why in self.drop:                  # footage a step leaves out: a hard cut over it (R34)
            if a < src_out - 1e-3 and z > src_in + 1e-3:
                if a > src_in + 1e-3:
                    self.clip(src_in, a, speed)
                self.pending = self.pending or "cut"
                if (a, z) not in self.dropped:
                    self.dropped.add((a, z))
                    self.notes.append(f"{sid}: {z - a:.2f}s of the recording left out at {a:.2f}s of the take, "
                                      f"a hard cut ({why})")
                if z < src_out - 1e-3:
                    n0 = len(self.segs)
                    self.clip(z, src_out, speed)
                    if len(self.segs) > n0:               # a drop joins frames that match (round 6's p2.37): a
                        self.segs[n0]["still_cut"] = True   # camera jump at the cut would show
                return
        dur = (src_out - src_in) / speed
        last = self.segs[-1] if self.segs else None
        if (not self.pending and last and last["type"] == "clip" and last["speed"] == round(speed, 3)
                and abs(last["src_out"] - src_in) < 1e-3):                # continuous footage: extend the last clip
            last["src_out"], last["dur"] = round(src_out, 4), round(last["dur"] + dur, 4)
            self.T += dur
            return
        seg = {"type": "clip", "t": round(self.T, 4), "dur": round(dur, 4), "src_in": round(src_in, 4),
               "src_out": round(src_out, 4), "speed": round(speed, 3), "transition_in": self.pending}
        if self.pending and self.segs and self.segs[-1]["type"] == "clip":
            frames = self.cuts["swipe_frames" if self.pending == "swipe" else "crossfade_frames"]
            seg["transition_frames"] = frames
            self.segs[-1]["tail_s"] = round(frames / self.fps, 4)     # outgoing clip keeps playing under the incoming
        elif self.pending:
            seg["transition_in"] = None                                # nothing to transition from (a hold)
        self.segs.append(seg)
        self.pending = None
        self.T += dur

    def hold(self, src_t, dur, why):
        if dur <= 1e-3:
            return
        for a, z, *_ in self.drop:                        # never freeze a frame a step leaves out (Fable, round 6):
            if a <= src_t < z:                            # the last frame before it
                src_t = max(0.0, a - 0.5 / self.fps)
        self.segs.append({"type": "hold", "t": round(self.T, 4), "dur": round(dur, 4), "src_t": round(src_t, 4)})
        if dur > self.cuts["hold_warn_s"]:
            self.warnings.append(f"hold of {dur:.1f}s at {self.T:.1f}s ({why})")
        self.T += dur

    def bridge(self, src_from, src_to, dmin, why, dmax=None, treatment=None):
        """Show the source between two kept spans, taking at least dmin seconds of edit time, and no more than dmax
        when that is larger than dmin (the dead-air budget: footage nobody talks over is cut down to fit). treatment
        overrides the gap treatment (typing is sped up, R67)."""
        c, g = self.cuts, src_to - src_from
        treatment = treatment or c["gap_treatment"]
        k = max(c["speed_min"], g / c["speed_max_s"]) if g > 0 else 1
        natural = g if g <= c["cut_above_s"] else (g / k if treatment == "speed" else 0.0)
        if dmax is not None and natural > max(dmin, dmax) + 1e-3:
            keep = max(dmin, dmax, 0.0)                              # 1x for what fits, then a hard cut
            self.clip(src_from, src_from + keep)
            self.pending = treatment if treatment != "speed" else "cut"
            return
        if natural >= dmin:
            if g <= c["cut_above_s"]:
                self.clip(src_from, src_to)
            elif treatment == "speed":
                self.clip(src_from, src_to, speed=k)
            else:
                self.pending = treatment
            return
        if g <= c["cut_above_s"] or dmin >= g:                       # not enough footage: all of it, then a hold
            self.clip(src_from, src_to)
            self.hold(src_to, dmin - max(g, 0), why)
        elif treatment == "speed":                                    # 1x until the line fits, the rest sped up
            x = (dmin - g / k) / (1 - 1 / k)
            self.clip(src_from, src_from + x)
            self.clip(src_from + x, src_to, speed=k)
        else:                                                         # 1x until the line fits, then cut
            self.clip(src_from, src_from + dmin)
            self.pending = treatment

    def timelapse(self, src_from, src_to, keeps, dur, card=None, full=True):
        """A live wait (R39): the footage from src_from to src_to plays in about dur seconds, sped up evenly, except
        the keeps (permission prompts, R39), which play at 1x. card: (seconds, title, sub) shown first, over the
        wait's first frame (a hold that carries the card). No speed label (R37). full: a lapse with a card holds the
        whole frame while it plays (a reply scroll, full=False, keeps its zoom)."""
        spans, pos = [], src_from
        for k0, k1 in sorted(keeps):
            k0, k1 = max(k0, pos), min(k1, src_to)
            if k1 > k0:
                spans.append((k0, k1))
                pos = k1
        slow = sum(k1 - k0 for k0, k1 in spans)
        fast = (src_to - src_from) - slow
        k = max(1.0, fast / max(0.5, dur))                # the keeps play on top of the lapse (S7: card + lapse +
                                                          # prompts within 30 s)
        if card:
            self.hold(src_from, card[0], "title card")
            self.segs[-1]["card"] = {"title": card[1], "sub": card[2]}
            self.pending = "cut"
        pos, t0 = src_from, self.T
        for k0, k1 in spans:
            self.clip(pos, k0, speed=k)
            self.clip(k0, k1)
            pos = k1
        self.clip(pos, src_to, speed=k)
        if full and card:                                 # a long build: the whole IDE at work (the panel and the
            self.lapses.append((round(t0, 4), round(self.T, 4)))   # Explorer); a short wait keeps its zoom
        self.notes.append(f"time-lapse: {src_to - src_from:.0f}s of waiting at {k:.1f}x"
                          + (f", {len(spans)} prompt(s) at 1x" if spans else "") + (", after a title card" if card else ""))

    def insert_hold(self, t, dur, why):
        """Freeze the picture at edit time t for dur seconds, pushing everything after it later (R62's beat)."""
        i = next((i for i, s in enumerate(self.segs) if s["t"] + 1e-3 < t < s["t"] + s["dur"] - 1e-3), None)
        if i is None:
            i = next((i for i, s in enumerate(self.segs) if abs(s["t"] - t) <= 1e-3), None)
            if i is None:
                return False
            src_t, at = self.to_src(t), i                              # on a boundary: no split needed
        else:
            seg = self.segs[i]
            k = t - seg["t"]
            if seg["type"] == "clip":
                cut = round(seg["src_in"] + k * seg["speed"], 4)
                rest = {**seg, "t": round(t, 4), "dur": round(seg["dur"] - k, 4), "src_in": cut, "transition_in": None}
                rest.pop("transition_frames", None)
                seg.update({"dur": round(k, 4), "src_out": cut, "tail_s": 0.0})
                src_t = cut
            else:
                rest = {**seg, "t": round(t, 4), "dur": round(seg["dur"] - k, 4)}
                seg["dur"] = round(k, 4)
                src_t = seg["src_t"]
            self.segs.insert(i + 1, rest)
            at = i + 1
        for s in self.segs[at:]:
            s["t"] = round(s["t"] + dur, 4)
        self.segs.insert(at, {"type": "hold", "t": round(t, 4), "dur": round(dur, 4), "src_t": round(src_t, 4)})
        self.T += dur
        self.notes.append(f"beat: picture held {dur:.2f}s at {t:.2f}s ({why})")
        return True

    def to_src(self, t):
        seg = self.segs[0]
        for s in self.segs:
            if s["t"] <= t:
                seg = s
        if seg["type"] == "hold":
            return seg["src_t"]
        return min(seg["src_in"] + (t - seg["t"]) * seg["speed"], seg["src_out"])

    def to_edit(self, src_t):
        for s in self.segs:
            if s["type"] == "clip" and s["src_in"] <= src_t < s["src_out"]:
                return s["t"] + (src_t - s["src_in"]) / s["speed"]
        return None

    def to_edit_near(self, src_t):
        """Like to_edit, but source time that was cut maps to the cut (the start of the next clip)."""
        t = self.to_edit(src_t)
        if t is not None:
            return t
        later = [s for s in self.segs if s["type"] == "clip" and s["src_in"] >= src_t]
        return min(later, key=lambda s: s["src_in"])["t"] if later else self.T


def line_beats(meta, pace, clip=None):
    """R62: [(at_s, beat_s)], a beat at each sentence break where the line switches between explaining and
    instructing. R181: a beat never splits a breath, so it goes in the first silence after the earlier word, measured in
    the clip (pipeline.narration.breaths.beat_point; ElevenLabs logs word ends up to half a second late, GOTCHAS): the
    pause comes first, and any inhale leads into the next sentence. Without the clip, mid-pause as before."""
    b = pace.get("mode_switch_beat_s", 0.0)
    if not b:
        return []
    out, ws = [], meta["words"]
    for k in sentences.breaks(meta["display_text"], ws):
        if k["before_mode"] == k["after_mode"]:
            continue
        w0, w1 = ws[k["after"]], ws[k["after"] + 1]
        at = k["at_s"]
        if clip is not None:
            from pipeline.narration import breaths as br
            bp = br.beat_point(clip, w0["start"], w1["start"])
            if bp is not None:
                at = round(min(max(w0["start"] + 0.1, bp), w1["start"] - 0.05), 4)
        out.append((at, b))
    return out


def mute_double_breaths(run_dir, narration, tl):
    """R181: two inhales heard within 1.5 s with no speech between lose the earlier one, the words untouched: the
    part that plays it is split around it, so it is silent and everything after stays where it was."""
    from pipeline.narration import breaths as br
    plan_like = {"narration": narration}
    pcs = br.placed(run_dir, plan_like, CACHE)
    words = br.placed_words(plan_like, CACHE)
    for a, _b in br.doubles(pcs, words):
        n = next(x for x in narration if x["line_id"] == a["line"])
        for i, p in enumerate(n["parts"]):
            s0, s1 = p["in"] + (a["t0"] - p["at"]), p["in"] + (a["t1"] - p["at"])
            if p["in"] - 1e-6 <= s0 and s1 <= p["out"] + 1e-6:
                keep = []
                if s0 - p["in"] > 0.01:
                    keep.append({"at": p["at"], "in": p["in"], "out": round(s0, 4)})
                if p["out"] - s1 > 0.01:
                    keep.append({"at": round(p["at"] + s1 - p["in"], 4), "in": round(s1, 4), "out": p["out"]})
                n["parts"][i:i + 1] = keep
                n.setdefault("muted", []).append([round(s0, 3), round(s1, 3)])
                tl.notes.append(f"{n['step']}: a double breath's first inhale muted at {a['t0']:.2f} s ({s0:.2f} to "
                                f"{s1:.2f} s of its clip, R181)")
                break


def shifted(o, beats):
    """Where audio offset o of a line lands in the line once its beats are in."""
    return o + sum(b for at, b in beats if o >= at)


def captions(words, display, start, limits):
    """Group a line's timed words into cues of at most max_lines x max_chars, breaking after sentences."""
    cues, cur = [], []
    cap = limits["max_chars"] * limits["max_lines"]
    text_of = lambda ws: display[ws[0]["char"][0]:_end_char(display, ws[-1]["char"][1])].strip()
    for w in words:
        if cur and len(text_of(cur + [w])) > cap:
            cues.append(cur)
            cur = []
        cur.append(w)
        if display[w["char"][1]:w["char"][1] + 1] in ".?!" and len(text_of(cur)) >= limits["min_chars_to_break"]:
            cues.append(cur)
            cur = []
    if cur:
        cues.append(cur)
    out = []
    for i, ws in enumerate(cues):
        t0 = start + ws[0]["start"]
        t1 = start + (cues[i + 1][0]["start"] if i + 1 < len(cues) else ws[-1]["end"] + limits["linger_s"])
        out.append({"start": round(t0, 3), "end": round(t1, 3), "text": _wrap(text_of(ws), limits["max_chars"])})
    return out


def _end_char(display, i):
    while i < len(display) and display[i] in ".,;:?!)\"'’":
        i += 1
    return i


def _wrap(text, width, max_lines=2):
    """The fewest lines (up to max_lines) whose most even split keeps every line within width; when none does, the
    most even split into max_lines (R59: the limits are guidelines)."""
    text = " ".join(text.split())
    if len(text) <= width or max_lines < 2:
        return text
    words, best = text.split(" "), None
    for k in range(2, max_lines + 1):
        lines = _balanced(words, k)
        if lines and max(map(len, lines)) <= width:
            return "\n".join(lines)
        if lines and (best is None or max(map(len, lines)) < max(map(len, best))):
            best = lines
    return "\n".join(best) if best else text


def _balanced(words, k):
    """Split words into k lines with the longest line as short as possible."""
    n = len(words)
    if n < k:
        return None
    width = lambda i, j: sum(len(w) for w in words[i:j]) + (j - i - 1)
    memo = {}

    def go(i, k):                                                     # (longest line, breaks) for words[i:] in k lines
        if (i, k) not in memo:
            memo[(i, k)] = ((width(i, n), [n]) if k == 1 else
                            min(((max(width(i, j), go(j, k - 1)[0]), [j] + go(j, k - 1)[1])
                                 for j in range(i + 1, n - k + 2)), key=lambda r: r[0]))
        return memo[(i, k)]

    cuts, i, out = go(0, k)[1], 0, []
    for j in cuts:
        out.append(" ".join(words[i:j]))
        i = j
    return out


def srt(cues):
    ts = lambda t: f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{int(t % 60):02},{int(round(t % 1 * 1000)) % 1000:03}"
    return "\n".join(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues, 1))


def _cursor_at(moves, t):
    """Same as remotion/src/track.ts cursorAt: cubic ease-in-out along each move, resting between moves."""
    if not moves:
        return None
    rest = moves[0]["from"]
    for m in moves:
        if t < m["t0"]:
            return rest
        if t < m["t1"]:
            u = (t - m["t0"]) / (m["t1"] - m["t0"])
            e = 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
            return {"x": m["from"]["x"] + (m["to"]["x"] - m["from"]["x"]) * e,
                    "y": m["from"]["y"] + (m["to"]["y"] - m["from"]["y"]) * e}
        rest = m["to"]
    return rest


def whole_subjects(executed, doc_order, b, placed, tl, run_dir, fps, z, find_box, W, H):
    """R123: each step's `whole`, the thing its line refers to that must be shown whole (a dialog, panel or menu), as
    {step, t0, t1, box} in edit s and frame px. `target: "appears"` measures what the step's action opened from the
    take's frames (pipeline.edit.appear), shown from its result until `until_step` acts (the click that closes it;
    the next step that acts by default); it is measured again just before each later step in that window acts, and
    the boxes are joined, so a dialog that grows or gives way to another is framed whole. Any other target is found
    like a mark's (a fixed box, OCR), shown through the line, or through until_step's line. An until_step the take
    skipped (only_if) gives way to the next step that ran."""
    order = [step["id"] for step, _ in executed]
    kinds = {step["id"]: step["action"]["type"] for step, _ in executed}
    acts = lambda x: kinds.get(x) not in (None, "none") and "act" in b.get(x, {})   # a line-only step has no events
    out = []
    for i, (step, s) in enumerate(executed):
        w = step.get("whole")
        if not w:
            continue
        sid, appears = step["id"], w["target"] == "appears"
        until = w.get("until_step")
        if until and until not in order:
            k = doc_order.index(until) if until in doc_order else len(doc_order)
            later = [x for x in order[i + 1:] if doc_order.index(x) > k]
            tl.notes.append(f"{sid}: whole's until_step {until} didn't run; until {later[0] if later else 'the next step that acts'}")
            until = later[0] if later else None
        if not until:
            until = next((x for x in order[i + 1:] if acts(x)), order[-1]) if appears else sid
        su = b.get(until, {})
        n, nu = placed.get(sid), placed.get(until)
        if appears:
            if "act" not in s or "result" not in s:
                tl.warnings.append(f"{sid}: whole 'appears' needs an action and its result; left out")
                continue
            nxt = next((b[x] for x in order[i + 1:] if "move" in b.get(x, {}) or "act" in b.get(x, {})), None)
            after = min(nxt.get("move", nxt.get("act", s["result"] + 1.5)), s["result"] + 3.0) if nxt \
                else s["result"] + 1.5
            box, how = appear.appeared(run_dir, s["act"] - 0.15, after, fps)
            u = order.index(until)
            for x in order[i + 2:u + 1] if box else []:              # again before each later step acts in it
                bx = b.get(x, {})
                if "move" in bx or "act" in bx:
                    more, _ = appear.appeared(run_dir, s["act"] - 0.15, bx.get("move", bx.get("act", 0) - 0.15), fps)
                    if more and more != box:
                        box = (min(box[0], more[0]), min(box[1], more[1]), max(box[2], more[2]), max(box[3], more[3]))
                        how += f", grown by {x}"
            t0 = tl.to_edit_near(s["result"])                        # framed whole as it appears; where a drop
            if any(a < s["result"] and z_ > s["act"] for a, z_, *_ in tl.drop):   # between click and result brings
                t0 = max(t0, tl.to_edit_near(s["act"]) + z["pan_s"] + 0.05)     # it closer, the camera sets off
                                                          # only after the click has landed (round 6's p2.37; Fable:
                                                          # elsewhere the approved framing stays as it was)
        else:
            box, how = find_box(sid, "whole", w["target"], n["start"]) if n else (None, None)
            t0 = n["start"] if n else None
            if w.get("from") == "result" and "result" in s:          # what the action brings up (a page it opens,
                t0 = tl.to_edit_near(s["result"])                     # R157), not the line's start
        if box is None or t0 is None:
            tl.warnings.append(f"{sid}: no box for what its line refers to ({how}); the camera can't frame it whole")
            continue
        if acts(until) and until != sid:
            t1 = tl.to_edit_near(su["act"])                         # the click that closes it
        else:
            t1 = nu["start"] + nu["length"] if nu else t0
        pad = w.get("pad_px", 8)
        box = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
        # R125: a dialog that fits at the rest level is framed whole there. One that doesn't is framed at its own
        # size when its lines treat it as a whole (fit "own": the Windows Open dialog); otherwise the camera keeps the
        # rest level and pans to what the lines name inside it (fit "pan", the default: the Create dataset box), and
        # only the captions keep off it. fit "zoom" (R157): the camera zooms out until the whole box is in title-safe
        # (both charts after Fit to width, the dashboard as it opens)
        level = cam._fit(box, z, W, H)
        mode = w.get("fit", "pan") if level < z["level"] - 1e-6 else "whole"
        framed = mode != "pan"
        out.append({"step": sid, "t0": round(t0, 4), "t1": round(max(t0, t1), 4), "box": box, "fit": mode,
                    "framed": framed, "what": w.get("what", ""), "align": w.get("align")})
        if framed:
            tl.notes.append(f"{sid}: shown whole from {t0:.2f}s to {t1:.2f}s, box {tuple(round(v) for v in box)} "
                            f"from {how}" + (" at its own size (R125)" if mode == "own" else " (R123)"))
        else:
            tl.notes.append(f"{sid}: {w.get('what', 'what it opened')} ({tuple(round(v) for v in box)}, from {how}) "
                            f"would need {level:.2f}x to show whole; the camera stays at {z['level']}x and pans to "
                            "what the lines name (R125)")
    return out


def arrows_for_small(moves, steps, ms, W, H, notes, px_per_css=1.0):
    """R121: a rectangle drawn live on a small target (an icon: a pencil, a radio button, a caret) reads better as an
    arrow. The logged gesture is redrawn in the same time: the travel ends at the arrow's tail instead of the
    rectangle's corner, the drag becomes the arrow's stroke, and the cursor backs off the tip as for any arrow
    (marks.retreat_px) when the next move leaves it room. `marks.kind_auto.arrow_max_px` is the largest target side
    that becomes an arrow; a step's mark with `kind_locked` keeps its kind."""
    auto = ms.get("kind_auto")
    if not auto:
        return moves
    out = sorted(moves, key=lambda m: m["t0"])
    for i, mv in enumerate(out):
        if not (mv.get("live") and mv.get("gesture") == "rect"):
            continue
        app = next((m for m in reversed(out[:i]) if m["step"] == mv["step"] and m.get("gesture") == "approach"
                    and m.get("mark") == mv.get("mark")), None)
        marks = steps.get(mv["step"], {}).get("marks", [])
        spec = marks[mv["mark"]] if isinstance(mv.get("mark"), int) and mv["mark"] < len(marks) else {}
        if app is None or spec.get("kind_locked"):
            continue
        p = ms["rect_pad_px"] * px_per_css                 # the runner pads in CSS px
        a, c = app["to"], mv["to"]
        box = (min(a["x"], c["x"]) + p, min(a["y"], c["y"]) + p, max(a["x"], c["x"]) - p, max(a["y"], c["y"]) - p)
        if max(box[2] - box[0], box[3] - box[1]) > auto["arrow_max_px"]:
            continue
        tail, head = mk.arrow_points(box, W, H, ms)
        app["to"] = {"x": round(tail[0], 1), "y": round(tail[1], 1)}
        mv["to"], mv["gesture"] = {"x": round(head[0], 1), "y": round(head[1], 1)}, "arrow"
        nxt = next((m for m in out[i + 1:] if m["t0"] >= mv["t1"]), None)
        if ms.get("retreat_px") and (nxt is None or nxt["t0"] >= mv["t1"] + 0.6):
            k = ms["retreat_px"] / max(1.0, ((tail[0] - head[0]) ** 2 + (tail[1] - head[1]) ** 2) ** 0.5)
            back = (head[0] + (tail[0] - head[0]) * k, head[1] + (tail[1] - head[1]) * k)
            out.append({"step": mv["step"], "t0": round(mv["t1"] + 0.2, 4), "t1": round(mv["t1"] + 0.55, 4),
                        "to": {"x": round(back[0], 1), "y": round(back[1], 1)}, "gesture": "retreat",
                        "mark": mv["mark"], "live": True})
        notes.append(f"{mv['step']}: the live mark on a {box[2] - box[0]:.0f}x{box[3] - box[1]:.0f} px target is "
                     "drawn as an arrow (R121)")
    return sorted(out, key=lambda m: m["t0"])


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def click_mark_timing(s, g, name_off, c, ms, pace):
    """R128: when a click target's live mark is drawn, held, released and clicked in the edit, from the line's own
    words. The mark is up through the lead-in and released as the target is named; the click lands
    pacing.click_after_name_s later (R23), so the confirming clause plays over the result (R24). The recorded gesture
    keeps its shape and pace (approach, draw); the hold is the edit's: marks.hold_s when the lead-in allows, longer
    when the lead-in is longer (the pointer sets off on the cue word, R23), and no shorter than marks.click_hold_min_s
    on a short line, where the gesture then starts before the line. s: the step's beats; g: the mark's recorded legs
    (source s); name_off, c: the name and cue words in the line (s, beats included). Returns (hold_s, after_s, cut_s):
    the hold between the shape's completion and the release, the click's delay after the name, and how much of the
    recorded hold (still footage) the edit cuts to fit."""
    hold_s = ms["hold_s"]
    floor = ms.get("click_hold_min_s", hold_s)
    gesture = g["draw1"] - g["approach0"]                 # the approach and the draw, as recorded
    lead = name_off - c                                   # from the cue word to the name
    if lead >= gesture + hold_s:
        hold = lead - gesture                             # the pointer sets off on the cue word (R23)
    elif name_off >= gesture + hold_s:
        hold = hold_s                                     # the gesture starts within the line, before the cue word
    else:
        hold = max(floor, name_off - gesture)             # a short line: the gesture starts with the line, or before it
    after = pace.get("click_after_name_s", 0.35)
    avail = s["act"] - g["draw1"]                         # the recorded hold, move and pause before the click
    hold = max(floor, min(hold, avail - after))           # no longer than the recording allows; below the floor a
    return hold, after, avail - (hold + after)            # freeze fills in (cut < 0)


def highlights(want, layers, ms, tl):
    """R122, R142: the highlighter, David's spotlight dim, for a large region (a whole pane, one side of a dialog).
    Everything but the region darkens (his measured 0.58 brightness) with a slow linear fade in, holds while the region
    is discussed (R50: to the end of its sentence, or until_word) and lifts. Two highlights close together are one dim
    whose lit region moves (his swaps, 0.24 to 0.52 s); the dim lifts before the next mark is drawn, faster if it must
    (R51: one mark at a time). want: [{step, t_name, t_release, box}] in edit time and frame px; layers: the marks
    already placed. Returns the highlight layers (kind 'highlight', style 'dim'), in source space like the Epic Pen
    marks, so they follow the camera."""
    hs = ms.get("highlight") or {}
    fin, swap, fout = hs.get("fade_in_s", 1.0), hs.get("swap_s", 0.3), hs.get("fade_out_s", 1.3)
    fout_min, gap, pad = hs.get("fade_out_min_s", 0.4), hs.get("swap_gap_s", 2.5), hs.get("pad_px", 6)
    others = [o for o in layers if o["kind"] != "highlight"]
    out = []
    for h in sorted(want, key=lambda h: h["t_name"]):
        d0 = h["t_name"] + ms["after_name_s"]
        prev = out[-1] if out else None
        if prev and d0 < prev["draw1"]:                   # named while the last one still fades in: it waits, or the
            tl.notes.append(f"{h['step']}: highlight at {d0:.2f}s waits {prev['draw1'] - d0:.2f}s for the last "
                            "one's fade-in")              # two dims would stack (Fable, round 5)
            d0 = prev["draw1"]
        b = h["box"]
        ly = {"step": h["step"], "kind": "highlight", "style": "dim",
              "from": {"x": round(b[0] - pad, 1), "y": round(b[1] - pad, 1)},
              "to": {"x": round(b[2] + pad, 1), "y": round(b[3] + pad, 1)},
              "draw0": round(d0, 4), "draw1": round(d0 + fin, 4),
              "fade0": round(max(d0 + fin + ms["hold_s"], (h["t_release"] or 0) + ms["release_after_s"]), 4)}
        between = prev is not None and any(prev["draw0"] < o["draw0"] < d0 for o in others)
        if prev and not between and d0 <= prev["fade0"] + gap:   # the dim stays up; the lit region moves (never
            prev["fade0"] = prev["fade1"] = ly["draw0"]           # across a mark drawn between them, R51)
            ly["swap_from"] = {"from": prev["from"], "to": prev["to"]}
            ly["draw1"] = round(d0 + swap, 4)
            tl.notes.append(f"{h['step']}: highlight moves from the last one at {d0:.2f}s (a swap, {swap:.2f}s)")
        out.append(ly)
    for ly in out:
        if "fade1" in ly:                                 # swapped out: the next one carries the dim on
            continue
        f = fout                                          # R51: the dim lifts before the next mark is drawn, one
        nxt = min((o["draw0"] for o in others            # drawn during it included, faster if it must
                   if ly["draw0"] < o["draw0"] < ly["fade0"] + fout), default=None)
        if nxt is not None:
            f = max(fout_min, min(fout, nxt - ly["fade0"]))
            fade0 = min(ly["fade0"], nxt - f)
            if fade0 < ly["draw1"]:                       # too soon even for the fastest lift: it overlaps the mark
                tl.warnings.append(f"{ly['step']}: a mark is drawn at {nxt:.2f}s, before the highlighter is fully up; "
                                   "it lifts from there over the mark (R51, one at a time)")
                fade0 = ly["draw1"]
            ly["fade0"] = round(fade0, 4)
        ly["fade1"] = round(ly["fade0"] + f, 4)
        tl.notes.append(f"{ly['step']}: highlighter up {ly['draw0']:.2f}-{ly['fade1']:.2f}s (R142)")
    for ly in out:                                        # a swapped-out one ends where the next starts
        ly.setdefault("fade1", ly["fade0"])
    return out


def xyxy(b):
    """A composition's box ({x, y, w, h}, frame px, as remotion/src/overlays/kit.tsx has it) or a corner list, as
    (x0, y0, x1, y1)."""
    return (b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]) if isinstance(b, dict) else tuple(b)


def plan_overlays(path, placed, ms, sub, tl):
    """R134, R138: the overlay plan's compositions (ChapterCard, TermChip, ChoicePanel, WordBuild, MapPins, ...) from
    exercises/<ex>/overlays.json, timed to the spoken words like a step's overlay card (R80). Each entry: id, layout
    (the composition), line (a line id) and at_word (it starts on that word), then until_word (in that line, or in
    until_line) or hold_s, else it holds to the end of the at_word's sentence; exit_s (default 0.5) is added for its
    way out. items: [{text, at_word, line?}] appear on their words. box (screen px) is where it sits (captions keep
    off it) as the compositions take it, {x, y, w, h}; variant dark, light or auto (R140, decided once the camera is
    planned); props pass through to the composition, a prop named <name>_at_word becoming <name>_at, the word's
    time; an item's until_word becomes its until. Returns the layers for plan.overlays."""
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    by_line = {n["line_id"]: n for n in placed.values()}
    metas = {}

    def meta_of(n):
        if n["key"] not in metas:
            metas[n["key"]] = timing.of(n)
        return metas[n["key"]]

    def word_at(line_id, word, end=False, occurrence=1, after=None):
        """Edit time of a word's start (or end) in a placed line, beats included; None if not found. after: (word,
        occurrence) in the same line that the search starts from (an until_word comes after its at_word)."""
        n = by_line.get(line_id)
        if not n:
            return None
        meta = meta_of(n)
        if end:
            text = meta["display_text"]
            pos = -1
            if after:
                for _ in range(after[1]):
                    pos = text.find(sub(after[0]), pos + 1)
                if pos < 0:
                    return None
            for _ in range(occurrence):
                pos = text.find(sub(word), pos + 1)
            last = pos + len(sub(word)) - 1
            w = next((x["end"] for x in meta["words"] if pos >= 0 and x["char"][0] <= last < x["char"][1]), None)
        else:
            w = mk.word_time(meta, sub(word), occurrence)
        return None if w is None else n["start"] + shifted(w, [tuple(x) for x in n.get("beats", [])])

    out = []
    for o in doc.get("overlays", []):
        if o.get("enabled") is False:
            continue
        t0 = word_at(o["line"], o["at_word"], occurrence=o.get("occurrence", 1))
        if t0 is None:
            tl.warnings.append(f"overlay {o['id']!r}: line {o['line']!r} not in the edit, or word {o['at_word']!r} "
                               "not in it; left out")
            continue
        t0 += o.get("offset_s", 0.0)
        if o.get("hold_s") is not None:
            end = t0 + o["hold_s"]
        elif o.get("until_word"):
            same = o.get("until_line", o["line"]) == o["line"]
            end = word_at(o.get("until_line", o["line"]), o["until_word"], end=True,
                          after=(o["at_word"], o.get("occurrence", 1)) if same else None)
        else:                                          # the end of the at_word's sentence (R50's default)
            n = by_line[o["line"]]
            r = mk.release_time(meta_of(n), sub(o["at_word"]), o.get("occurrence", 1))
            end = None if r is None else n["start"] + shifted(r, [tuple(x) for x in n.get("beats", [])])
        if end is None or end <= t0:
            tl.warnings.append(f"overlay {o['id']!r}: no end found (until {o.get('until_word')!r}); held 3 s")
            end = t0 + 3.0
        items = []
        for it in o.get("items", []):
            ta = word_at(it.get("line", o["line"]), it["at_word"], occurrence=it.get("occurrence", 1)) \
                if it.get("at_word") else t0
            if ta is None:
                tl.warnings.append(f"overlay {o['id']!r}: item word {it.get('at_word')!r} not found; shown from the "
                                   "start")
                ta = t0
            item = {**{k: v for k, v in it.items() if k not in ("at_word", "line", "occurrence", "until_word")},
                    "text": sub(it.get("text", "")), "at": round(ta, 4)}
            if it.get("until_word"):                   # an item that leaves early (a map label): its word's end
                same = it.get("until_line", it.get("line", o["line"])) == it.get("line", o["line"])
                tu = word_at(it.get("until_line", it.get("line", o["line"])), it["until_word"], end=True,
                             after=(it["at_word"], it.get("occurrence", 1)) if same and it.get("at_word") else None)
                if tu is not None:
                    item["until"] = round(tu, 4)
            items.append(item)
        first = min((it["at"] for it in items), default=t0)
        if first < t0:                                 # an item spoken before the overlay's word: it starts there
            tl.notes.append(f"overlay {o['id']!r}: starts {t0 - first:.2f}s early, on its first item")
            t0 = first
        props = dict(o.get("props") or {})
        for k in [k for k in props if k.endswith("_at_word")]:   # e.g. meaning_at_word -> meaning_at (edit time)
            ta = word_at(o["line"], props.pop(k))
            if ta is None:
                tl.warnings.append(f"overlay {o['id']!r}: {k} not found in the line; left at the start")
            props[k[:-len("_word")]] = round(ta if ta is not None else t0, 4)
        layer = {**props, "id": o["id"], "step": by_line[o["line"]]["step"], "layout": o["layout"],
                 "t0": round(t0, 4), "t1": round(end + ms.get("overlay_tail_s", 0.2) + o.get("exit_s", 0.5), 4),
                 "exit_s": o.get("exit_s", 0.5),        # the way out, as R185's reading time counts it
                 "items": items, "highlights": [], "variant": o.get("variant", "auto"), "plan_overlay": True}
        if o.get("box"):
            layer["box"] = o["box"]
        out.append(layer)
        tl.notes.append(f"overlay {o['id']!r} ({o['layout']}) {layer['t0']:.2f}-{layer['t1']:.2f}s, "
                        f"{len(items)} item(s)")
    out.sort(key=lambda x: x["t0"])
    for a, b in zip(out, out[1:]):                     # one overlay at a time (the plan's section 3)
        if b["t0"] < a["t1"]:
            tl.warnings.append(f"overlay {b['id']!r} starts at {b['t0']:.2f}s while {a['id']!r} is up (to "
                               f"{a['t1']:.2f}s): one at a time")
    return out


def correction_spans(run_dir, segs, tl=None):
    """R173: recording flaws covered with a clean picture of the same place (a correction layer, as David would build
    a correction sequence in Premiere). runs/<id>/corrections.json lists them in source terms: {"corrections": [{id,
    why, box: [x0, y0, x1, y1] (source px), src_t0, src_t1 (seconds: the flaw's first frame to the frame after its
    last), plate: a frame-sized PNG in the run folder (the clean picture, in source px)}]}. Each becomes the edit
    spans where the timeline shows those source frames, played or held (a freeze of a flawed frame is covered for as
    long as it holds): [{id, why, box, plate, t0, t1}] in edit seconds, drawn over the recording and under the
    cursor and marks, so it follows the camera."""
    p = Path(run_dir) / "corrections.json"
    if not p.exists():
        return []
    fps = tl.fps if tl is not None and getattr(tl, "fps", None) else 30.0
    out = []
    for c in json.loads(p.read_text(encoding="utf-8")).get("corrections", []):
        # the flaw as raw frames k0..k1 (inclusive): "frames", else the seconds' frames (a half-frame margin each side)
        k0, k1 = c.get("frames") or (round(c["src_t0"] * fps + 0.5), round(c["src_t1"] * fps - 0.5))
        frames = []                                       # edit frames that show raw k0..k1, worked out as the
        for s in segs:                                    # renderers place them (Fable, round 7): a clip from
            n_a = round(s["t"] * fps)                     # round(t * fps), its media from round(src_in * fps)
            if s["type"] == "clip":
                n_b = round((s["t"] + s["dur"]) * fps) + round((s.get("tail_s") or 0.0) * fps)   # a transition's
                i0, sp = round(s["src_in"] * fps), s["speed"]                                     # tail shows on
                lo = n_a + math.ceil((k0 - i0) / sp - 1e-9)
                hi = n_a + (k1 + 1 - i0) if sp == 1 else n_a + math.ceil((k1 + 1 - i0) / sp)
                lo, hi = max(lo, n_a), min(hi, n_b)       # [lo, hi): a sped-up piece gets a frame's margin
                if hi > lo:
                    frames.append([lo, hi])
            elif k0 <= round(s.get("src_t", -1.0) * fps) <= k1:   # a freeze of a flawed frame, for as long as it holds
                frames.append([n_a, round((s["t"] + s["dur"]) * fps)])
        frames.sort()
        merged = []
        for a, b in frames:                               # pieces that touch are one correction
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for i, (a, b) in enumerate(merged):
            out.append({"id": c["id"] + (f"_{i + 1}" if len(merged) > 1 else ""), "why": c["why"], "box": c["box"],
                        "plate": c["plate"], "t0": round(a / fps, 6), "t1": round(b / fps, 6),
                        "frames": [a, b]})                # edit frames [a, b): Premiere and the proxy alike
        if tl is not None:
            tl.notes.append(f"correction {c['id']} (R173): raw frames {k0}-{k1} in {len(merged)} span(s) of the edit, "
                            + ", ".join(f"frames {a}-{b - 1}" for a, b in merged))
    return out


def plan_media(plan):
    """Every file the EditPass composition reads from its public dir (the run folder), relative paths: what a still
    or a proxy render must link in."""
    return ([plan["video"]] + [s["still"] for s in plan["segments"] if s.get("still")] +
            [n["src"] for n in plan["narration"]] + ["fonts/arialbi.ttf"] +
            ([plan["click_sound"]["src"]] if plan.get("click_sound") else []) +   # R137
            [c["plate"] for c in plan.get("corrections") or []])                 # R173


def after_draws(layers, marks, gap=0.1, enter_s=0.5, item_s=0.4):
    """R166, R51: nothing arrives while a click ring or a mark is being drawn. An overlay whose entrance (t0 to t0 +
    enter_s), or an item whose arrival (at to at + item_s), overlaps a mark's draw waits until the draw ends, plus
    gap; R80's "on its word" yields by at most the draw's length (David's pick of the pin icon, 00:05:01 in round 1).
    Changes the layers in place; returns notes."""
    draws = sorted((m["draw0"], m.get("draw1", m["draw0"])) for m in marks if m.get("style") == "draw")

    def later(t, dur):
        for d0, d1 in draws:                           # sorted: a wait that lands in the next draw waits again
            if t < d1 and t + dur > d0:
                t = d1 + gap
        return round(t, 4)
    notes = []
    for ly in layers:
        t0 = later(ly["t0"], enter_s)
        moved = {"in": t0 - ly["t0"]} if t0 != ly["t0"] else {}
        prev = prev_orig = None
        for it in ly.get("items", []):                 # a wait never puts an item after one spoken later
            orig, at = it["at"], max(later(it["at"], item_s), t0)
            if prev is not None and orig > prev_orig and at <= prev:   # its word fell just after the draw: kept
                at = round(prev + 0.08, 4)             # after the pushed one, MOTION.staggerS apart (Fable's review)
            if at != it["at"]:
                moved[f"item {it.get('key', '')}"] = at - it["at"]
                it["at"] = at
            prev, prev_orig = at, orig
        for k in [k for k, v in ly.items() if k.endswith("_at") and isinstance(v, (int, float))]:
            v = max(later(ly[k], item_s), t0)
            if v != ly[k]:
                moved[k] = v - ly[k]
                ly[k] = v
        ly["t0"] = t0
        last = max([it["at"] for it in ly.get("items", [])] + [t0] +
                   [v for k, v in ly.items() if k.endswith("_at") and isinstance(v, (int, float))])
        if ly["t1"] < last + 1.0:                      # an item pushed late still holds before the exit
            ly["t1"] = round(last + 1.0, 4)
        if moved:
            notes.append(f"{ly['id']}: waits for a mark's draw (R166): " +
                         ", ".join(f"{k} +{v:.2f}s" for k, v in moved.items()))
    return notes


def overlay_area(o, W, H):
    """Where a plan overlay sits, frame px (x0, y0, x1, y1): its box, else the band along its edge (a composition placed
    by an edge: TermChip, ChoicePanel, WordBuild), else None (full screen, or not known)."""
    if o.get("box"):
        return xyxy(o["box"])
    return {"top": (0, 0, W, H * 0.25), "bottom": (0, H * 0.75, W, H), "left": (0, 0, W * 0.3, H),
            "right": (W * 0.7, 0, W, H)}.get(o.get("edge"))


def overlay_variants(overlays, keys, tl, run_dir, fps, W, H, layers):
    """R140: a panel contrasts with what it sits on. variant 'auto' becomes 'dark' over a light screen and 'light' over
    a dark one, from the mean brightness of the recording under its box (through the camera) as it appears. Also warns
    when a click target's mark is drawn under an overlay (the plan: none during a mark's draw, R51)."""
    from PIL import Image, ImageStat
    for o in overlays:
        if not o.get("plan_overlay"):
            continue
        for ly in layers:
            if ly["style"] == "draw" and o["t0"] < ly["draw1"] and ly["draw0"] < o["t1"]:
                tl.warnings.append(f"overlay {o['id']!r} is up while the {ly['kind']} mark of {ly['step']} is drawn "
                                   f"({ly['draw0']:.2f}s)")
                break
        if o.get("variant", "auto") != "auto":
            continue
        box = overlay_area(o, W, H) or (0, 0, W, H)
        t = min(o["t0"] + 0.5, o["t1"])
        s, cx, cy = cam.cam_at(keys, t, W, H)            # screen -> source: p = (q - W/2) / s + c
        x0, y0 = (box[0] - W / 2) / s + cx, (box[1] - H / 2) / s + cy
        x1, y1 = (box[2] - W / 2) / s + cx, (box[3] - H / 2) / s + cy
        src = tl.to_src(t)
        png = run_dir / "marks_ocr" / f"{int(round(src * fps)):06d}" / "frame.png"
        if not png.exists():
            png.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{src:.3f}", "-i", str(run_dir / "raw.mp4"),
                            "-frames:v", "1", str(png)], check=True)
        im = Image.open(png).convert("L")
        crop = im.crop((max(0, int(x0)), max(0, int(y0)), min(im.width, int(x1)), min(im.height, int(y1))))
        mean = ImageStat.Stat(crop).mean[0] if crop.width > 0 and crop.height > 0 else 128.0
        o["variant"] = "dark" if mean >= 128 else "light"
        tl.notes.append(f"overlay {o['id']!r}: {o['variant']} (the screen under it averages {mean:.0f} of 255, R140)")


def keep_clear(t0, t1, moves, clicks, targets, layers, keys, frame, subjects=(), screen_boxes=(), line_spans=()):
    """What a caption shown from t0 to t1 must not cover, in output pixels: the cursor through the cue, click rings and
    the boxes of targets clicked around it, marks on screen during it, and the subject of the line being spoken (e.g.
    the notice a conditional step closes), all through the camera; screen_boxes are already in output pixels (overlay
    cards, R77). R182: for every line spoken during the cue (line_spans: (start, end, step)), its click target and its
    marks, for the whole line, not only from a mark's draw to the click (a highlight's large region is soft). Returns
    (hard, soft, cursor): soft is a whole dialog, kept clear where possible; cursor is the cursor's box at each 0.1 s
    of the cue, so a caption moves for a cursor that stays on it, not one passing through (R133,
    captions.cursor_stay_s)."""
    W, H = frame
    scr = lambda t, x, y: cam.to_screen(keys, t, (x, y), W, H)
    clear, soft, cursor, t = [], [], [], t0
    for l0, l1, sid in line_spans:
        if l0 < t1 and t0 < l1:
            boxes = [(targets[sid], False)] if sid in targets else []   # (a big one, the whole visual, soft below)
            boxes += [((min(m["from"]["x"], m["to"]["x"]), min(m["from"]["y"], m["to"]["y"]),
                        max(m["from"]["x"], m["to"]["x"]), max(m["from"]["y"], m["to"]["y"])), m["kind"] == "highlight")
                      for m in layers if m["step"] == sid and not m.get("path")]
            boxes = [(b_, s_ or (b_[2] - b_[0]) * (b_[3] - b_[1]) > 0.15 * W * H) for b_, s_ in boxes]   # a big
            # rectangle (the empty visual, a whole chart) is a region, as a highlight: kept clear where possible
            for b, is_soft in boxes:
                for tm in (t0, (t0 + t1) / 2, t1):
                    (x0, y0), (x1, y1) = scr(tm, b[0], b[1]), scr(tm, b[2], b[3])
                    (soft if is_soft else clear).append((x0 - 16, y0 - 16, x1 + 16, y1 + 16))
    for s0, s1, b in screen_boxes:
        if s0 <= t1 and t0 <= s1:
            clear.append(tuple(b))
    for s0, s1, b, *how in subjects:                      # "soft": a whole dialog (R123), kept clear where possible
        if s0 <= t1 and t0 <= s1:
            for tm in (max(t0, s0), min(t1, s1)):
                (x0, y0), (x1, y1) = scr(tm, b[0], b[1]), scr(tm, b[2], b[3])
                (soft if how == ["soft"] else clear).append((x0 - 16, y0 - 16, x1 + 16, y1 + 16))
    while t <= t1:
        p = _cursor_at(moves, t)
        if p:
            x, y = scr(t, p["x"], p["y"])
            cursor.append((x - 16, y - 16, x + 48, y + 72))
        t += 0.1
    for k in clicks:
        if t0 - 1.5 <= k["t"] <= t1 + 0.5:
            x, y = scr(k["t"], k["at"]["x"], k["at"]["y"])
            clear.append((x - 60, y - 60, x + 60, y + 60))
            b = targets.get(k["step"])
            if b:
                (x0, y0), (x1, y1) = scr(k["t"], b[0], b[1]), scr(k["t"], b[2], b[3])
                clear.append((x0 - 16, y0 - 16, x1 + 16, y1 + 16))
    for m in layers:
        if m["draw0"] - 0.2 <= t1 and t0 <= m["fade1"]:
            tm = max(t0, m["draw0"])
            for k in [m] + m.get("path", [])[1:]:         # a travelling arrow: wherever it goes
                (ax, ay), (bx, by) = scr(tm, k["from"]["x"], k["from"]["y"]), scr(tm, k["to"]["x"], k["to"]["y"])
                clear.append((min(ax, bx) - 24, min(ay, by) - 24, max(ax, bx) + 24, max(ay, by) + 24))
    return clear, soft, cursor


def place_captions(cues, clear_for, style, frame):
    """Caption placement (R53): never cover anything the viewer needs; otherwise bottom centre. For each cue, collect
    what must stay clear (clear_for(start, end)) and take the first point of the 3x3 grid (Premiere's nine positions)
    that covers none of it: the bottom row, then the top row, then the middle row. Away from bottom centre the cue is
    wrapped narrower (R59: off_centre_max_chars, up to off_centre_max_lines) so it stays well clear. The cursor counts
    only where it stays on a spot for captions.cursor_stay_s of the cue (R133); without that setting any moment of it
    does, as before."""
    W, H = frame
    size, mx, my = style["size_px"], style["margin_x_px"], style["margin_bottom_px"]
    narrow_w = style.get("off_centre_max_chars", style["max_chars"])
    narrow_n = style.get("off_centre_max_lines", style["max_lines"])
    stay = max(1, int(round(style.get("cursor_stay_s", 0.0) / 0.1)))   # cursor samples (one per 0.1 s) that block

    def dims(text):
        lines = text.split("\n")
        return (max(len(l) for l in lines) * size * 0.6 + 2 * style["pad_x_px"],
                len(lines) * size * style["line_height"] + 2 * style["pad_y_px"])

    prev = None
    for c in cues:
        wide, narrow = c["text"], _wrap(c["text"], narrow_w, narrow_n)
        (w, h), (nw, nh) = dims(wide), dims(narrow)
        hard, soft, cursor = clear_for(c["start"], c["end"])
        top = style["top_y_px"]
        spots = [("bottom-centre", (W - w) / 2, H - my - h, w, h, wide), ("bottom-left", mx, H - my - nh, nw, nh, narrow),
                 ("bottom-right", W - mx - nw, H - my - nh, nw, nh, narrow),
                 ("top-centre", (W - nw) / 2, top, nw, nh, narrow), ("top-left", mx, top, nw, nh, narrow),
                 ("top-right", W - mx - nw, top, nw, nh, narrow), ("middle-left", mx, (H - nh) / 2, nw, nh, narrow),
                 ("middle-right", W - mx - nw, (H - nh) / 2, nw, nh, narrow),
                 ("middle-centre", (W - nw) / 2, (H - nh) / 2, nw, nh, narrow)]
        if (prev and prev["pos"]["where"] != "bottom-centre" and c["start"] - prev["end"] < 0.5
                and not re.search(r"[.?!:][\"')\]]*$", prev["text"].strip())):   # R174: a cue that finishes the last
            spots.sort(key=lambda s_: s_[0] != prev["pos"]["where"])           # one's sentence tries its spot first
        boxed = lambda cand: (cand[1], cand[2], cand[1] + cand[3], cand[2] + cand[4])
        free = lambda cand, rects: not any(_overlaps(boxed(cand), r) for r in rects)
        cursor_free = lambda cand: sum(1 for r in cursor if _overlaps(boxed(cand), r)) < stay
        pick = (next((cand for cand in spots if free(cand, hard + soft) and cursor_free(cand)), None)
                or next((cand for cand in spots if free(cand, hard)), None))
        if not pick:                                      # nothing clear: the spot that covers least of it (hard
            area = lambda cand, rects: sum(max(0, min(boxed(cand)[2], r[2]) - max(boxed(cand)[0], r[0])) *   # first)
                                           max(0, min(boxed(cand)[3], r[3]) - max(boxed(cand)[1], r[1])) for r in rects)
            pick = min(spots, key=lambda cand: (area(cand, hard), area(cand, soft)))
            c["placement_warning"] = f"no clear spot; {pick[0]} covers least"
        name, x, y, bw, _, c["text"] = pick
        c["pos"] = {"where": name, "cx": round(x + bw / 2, 1), "y": round(y, 1)}
        prev = c
    return cues


def plan(run_dir, steps_path, gap=None):
    run_dir = Path(run_dir).resolve()
    header, events = load_log(run_dir)
    cal = json.loads((run_dir / "calibration.json").read_text(encoding="utf-8"))
    doc = json.loads(Path(steps_path).read_text(encoding="utf-8"))
    ex_dir = EXERCISES / doc["exercise"]
    lines = json.loads((ex_dir / "lines.json").read_text(encoding="utf-8"))
    st = json.loads((ex_dir / "edit_settings.json").read_text(encoding="utf-8"))
    pace, cuts, vt = st["pacing"], dict(st["cuts"]), st["viewer_time"]
    tlp = st.get("timelapse", {"realtime_max_s": float("inf")})
    if gap:
        cuts["gap_treatment"] = gap
    fps = cal["fps"]
    tv = lambda t: cal["offset_s"] + cal["scale"] * t
    b = beats(events, tv)
    joins = [tv(e["t_mono"]) for e in events if e["phase"] == "recording_joined"]   # R70: two recordings, one take
    act = activity.load(run_dir)
    dropped = {st_["id"] for st_ in doc["steps"] if st_.get("drop")}
    for sid_, s in b.items():     # the result shows when the picture last changed before the runner saw it: its check
        if "result" in s and s.get("kind") != "scroll":   # polls, so the logged time can be a second late (a
                                                          # reply scroll's end is logged exactly)
            seen = activity.last_active(act, fps, s.get("act", s.get("start", s["result"])), s["result"],
                                        pace["activity_min_pct"])
            if seen is not None and s.get("type1") is not None and sid_ in dropped:   # a typing step whose flicker
                seen = max(seen, s["type1"])      # is dropped (R183): its result is the finished text, not a flicker
            if seen is not None and seen < s["result"]:
                s["result_logged"], s["result"] = s["result"], round(seen, 4)

    tl = Timeline(fps, cuts)
    # A step's `drop`: footage to leave out, each span given from one of the step's logged times to another (start,
    # move, arrive, act, result, end; a typing step's type0 and type1), plus offsets in seconds: what the take
    # recorded but the viewer shouldn't see (a loading box that flashes the screen dark, a browser's autofill
    # flickering over typed text: Section A round 6, David's notes 12 and 13)
    for st_ in doc["steps"]:
        for d in st_.get("drop") or []:
            s_ = b.get(st_["id"]) or {}
            a, z = s_.get(d["from"]), s_.get(d["to"])
            if a is None or z is None:
                tl.warnings.append(f"{st_['id']}: its drop names {d['from']!r} or {d['to']!r}, which the run log "
                                   "doesn't have; nothing left out")
                continue
            a, z = a + d.get("from_s", 0.0), z + d.get("to_s", 0.0)
            # Fable's review (round 6): a drop over the step's own click or result would leave the plan without them,
            # and one before its action would shift the picture under the line's cue word (the line is anchored on
            # footage played uncut): both are refused, not planned wrong
            inside = [k for k in ("act", "result") if s_.get(k) is not None and a <= s_[k] < z]
            if inside or ("act" in s_ and a < s_["act"]):
                tl.warnings.append(f"{st_['id']}: its drop {a:.2f}-{z:.2f}s " + (f"covers its {' and '.join(inside)}"
                                   if inside else "starts before its action") + "; nothing left out")
                continue
            if z > a:
                tl.drop.append((round(a, 4), round(z, 4), st_["id"], d.get("why", "")))
    tl.drop.sort()
    flashes = cal["flashes"]
    src_pos = flashes[0]["t_start"] + flashes[0]["frames"] / fps + cuts["after_flash_s"]   # the start flash is cut
    src_last = (flashes[-1]["t_start"] - cuts["after_flash_s"] if len(flashes) > 1          # so is the end flash
                else video_seconds(run_dir / "raw.mp4") - 0.1)        # a take that stopped early has none
    narration, caps, prev_line_end, prev_result, prev_part = [], [], None, None, None
    prev_speech_end, prev_comma, prev_s = None, False, None
    # a video that opens on a graphic (the avatar's intro, R57) dissolves into the camera: the first line waits until
    # the dissolve is over, then the usual gap, so the avatar is gone before the voice starts (David, 2026-10-12)
    first_lead = pace["picture_before_line"]
    if doc.get("opens_on_graphic"):
        first_lead = max(first_lead, (cuts.get("section_transition") or {}).get("s", 1.0) + pace["gap_between_lines"])
    if doc.get("excerpt"):        # a few steps of a longer take (R98): the picture starts just before the first one,
        first = next((b[s_["id"]] for s_ in doc["steps"] if s_["id"] in b and not s_.get("after")), None)
        if first and "start" in first:                    # not at the take's start flash
            src_pos = max(src_pos, first["start"] - cuts.get("excerpt_lead_s", 3.0))
            tl.notes.append(f"excerpt: the picture starts at {src_pos:.2f}s of the take, before {first['id']}")

    def quiet_until(t_end, base):
        """R25: the silence after a line runs past the default gap (base), up to max_silence_s, only while the
        picture changes; it ends a gap after the last change."""
        s0 = tl.to_src(t_end) if t_end <= tl.T else src_pos + (t_end - tl.T)
        last = activity.last_active(act, fps, s0, s0 + pace["max_silence_s"], pace["activity_min_pct"])
        if last is None:
            return base
        return min(t_end + pace["max_silence_s"], max(base, t_end + (last - s0) + pace["gap_between_lines"]))

    executed, section_cuts, r128_sched = [], [], {}

    def place(step, s, line, meta, bts, start, e_anchor):
        """Lay the step's line at start (edit s): the narration entry, its captions, and the R62 beats as holds."""
        nonlocal prev_line_end, prev_speech_end, prev_comma, prev_result
        key = line["key"]
        parts, a = [], 0.0                                          # the audio in pieces, one per beat
        for at, _ in bts + [(line["length_s"], 0.0)]:
            parts.append({"at": round(start + shifted(a, bts), 4), "in": round(a, 4), "out": round(at, 4)})
            a = at
        span = line["length_s"] + sum(bt for _, bt in bts)
        narration.append({"line_id": step["narration"]["line_id"], "step": step["id"], "key": key,
                          "src": f"audio/{wav_name(key)}",
                          "start": round(start, 4), "length": round(span, 4), "audio_s": line["length_s"],
                          "parts": parts, "beats": [[at, bt] for at, bt in bts],
                          "cue_word": line["cue_word"], "cue_at": round(e_anchor, 4),
                          "name_at": (round(start + shifted(line["click_offset_s"], bts), 4)
                                      if line.get("click_offset_s") is not None else None),
                          **timing.provenance(line)})   # R227: how its words were timed (nothing: the engine)
        words = [{**w, "start": shifted(w["start"], bts), "end": shifted(w["end"], bts)} for w in meta["words"]]
        caps.extend(captions(words, meta["display_text"], start, st["captions"]))
        prev_line_end = start + span
        prev_speech_end = start + words[-1]["end"]
        prev_comma = meta["display_text"].rstrip().endswith(",")
        for at, bt in bts:               # R62: a beat after the cue word holds the picture; before it, the line
            t_b = start + shifted(at - 1e-6, bts)    # simply starts earlier over the footage before the move
            k = min(sentences.breaks(meta["display_text"], meta["words"]), key=lambda x: abs(x["at_s"] - at))
            tl.notes.append(f"{step['id']}: beat {bt:.2f}s at {t_b:.2f}s, \"{k['before_text'][-28:]} | "
                            f"{k['after_text'][:28]}\" ({k['before_mode']} -> {k['after_mode']}, R62)")
            if e_anchor < t_b < tl.T - 1e-3 and tl.insert_hold(t_b, bt, f"{step['id']}: mode switch"):
                prev_result = tl.to_edit(s["result"])
        (run_dir / "audio").mkdir(exist_ok=True)               # edges faded, a stitching burst silenced (no pop)
        dst = run_dir / "audio" / wav_name(key)
        side = dst.with_suffix(".json")                       # what the pass did, kept beside the clip
        if not dst.exists() or not side.exists():
            rep = {}
            fixed = clean_clip(CACHE / f"{key}.mp3", dst, report=rep)
            side.write_text(json.dumps({"silenced": fixed, "changed": int(rep.get("changed", 0)),
                                        "clicks": [round(float(t), 3) for t, _ in rep.get("clicks", [])],
                                        "clicks_after": [round(float(t), 3) for t, _ in rep.get("clicks_after", [])]}),
                            encoding="utf-8")
            if fixed:
                tl.notes.append(f"{step['id']}: a stray burst silenced in its audio at {fixed} s (the next line's "
                                "onset from ElevenLabs' stitching)")
        done = json.loads(side.read_text(encoding="utf-8"))
        if done.get("clicks"):               # R103, R106: the export marks each one on the full sequence
            narration[-1]["clicks"] = done["clicks"]
            tl.notes.append(f"{step['id']}: {len(done['clicks'])} click(s) repaired in its audio at {done['clicks']} s "
                            f"of the clip ({done.get('changed', 0)} samples)")
        if done.get("clicks_after"):
            narration[-1]["clicks_left"] = done["clicks_after"]
            tl.warnings.append(f"{step['id']}: click(s) left in its audio after the repair (R103); the export marks "
                               "them on the full sequence for David (R106)")

    for step in doc["steps"]:
        line = lines.get(step["narration"]["line_id"]) if step.get("narration") else None
        meta = timing.of(line) if line else None      # R227: the times the line was built with
        bts = line_beats(meta, pace, CACHE / f"{line['key']}.mp3") if meta else []   # R62 beats, R181 at word ends
        part_pause = pace["pause_at_part_boundary"] if prev_part not in (None, step.get("part")) else 0.0
        if step.get("after"):
            # a line-only step (S7 p4.12b): it rides on the footage after its step's result, consuming none of its
            # own; the line follows the previous one (R25) and the next step's bridge shows the picture under it
            parent = b.get(step["after"])
            if not parent or "result" not in parent or parent.get("skipped") or not line:
                tl.warnings.append(f"{step['id']}: its step {step['after']!r} is not in the run, or the line is not "
                                   "voiced; left out")
                continue
            s = {"id": step["id"], "kind": "none", "start": parent["result"], "act": parent["result"],
                 "result": parent["result"], "cue": 0.3, "rides": True}
            c = line.get("cue_offset_s")
            c = s["cue"] if c is None else shifted(c, bts)
            during = step.get("during")      # it fills the silence over its step's action (typing, R25), so it
            if prev_line_end is None:        # follows the last line at the plain gap, before the step's result
                start = tl.T + first_lead
            elif prev_comma:
                start = prev_speech_end + pace["comma_pause_s"] - meta["words"][0]["start"]
            elif during:
                start = prev_line_end + pace["gap_between_lines"]
            else:
                start = quiet_until(prev_line_end, prev_line_end + pace["gap_between_lines"])
            if not during:
                start = max(start, (prev_result or 0.0) + pace["pause_after_result"])
            start += part_pause
            tl.notes.append(f"{step['id']}: a line-only step {'during' if during else 'after'} {step['after']}; its "
                            f"line starts at {start:.2f}s over the footage already playing")
            executed.append((step, s))
            prev_part = step.get("part")
            place(step, s, line, meta, bts, start, start + c)
            continue
        s = b.get(step["id"])
        if s and s.get("skipped"):
            tl.notes.append(f"{step['id']}: skipped in the take (only_if); left out with its line")
            continue
        if not s or "result" not in s:
            tl.warnings.append(f"{step['id']}: not in the run log, or no result; left out")
            continue
        kind = s["kind"]
        tls = {**tlp, **{k: v for k, v in (step.get("timelapse") or {}).items() if isinstance(v, (int, float))}}
        c = (line or {}).get("cue_offset_s")
        c = s["cue"] if c is None else shifted(c, bts)
        if kind in ("click", "hover", "type", "switch_tab", "drag"):   # typing starts with a move and a click into the box; a tab switch is a click; a drag, a press
            c += pace["move_after_cue_s"]
        # The anchor lands on the cue word: the start of the cursor move (announce, then act), or the navigation. A
        # step that draws a mark first was timed by the runner from the step start, which is where its line starts.
        r128 = None                                       # a click target's live mark: drawn while talking (R128)
        if s.get("live") and line and line.get("click_offset_s") is not None and "act" in s and "click_move" in s \
                and kind in ("click", "type", "drag"):
            acts_ = [i for i, m_ in enumerate(step.get("marks", [])) if m_["target"].get("of") == "action"]
            ai = acts_[-1] if acts_ else None             # the mark drawn last before the click
            gs = s.get("gestures") or {}
            g = gs.get(ai) or {}
            last_drawn = max((x.get("draw1", 0.0) for x in gs.values()), default=0.0)
            if ai is not None and g.get("draw1", 0.0) < last_drawn - 1e-6:   # another live mark follows it: the cut
                tl.warnings.append(f"{step['id']}: its click target's mark isn't the last mark drawn, so the "
                                   "recorded hold plays as recorded (R128 not applied)")   # would take that gesture
                ai = None
            if ai is not None and {"approach0", "draw0", "draw1"} <= g.keys() and g["draw1"] < s["click_move"]:
                name_off = shifted(line["click_offset_s"], bts)
                hold, after_name, cut = click_mark_timing(s, g, name_off, c, st["marks"], pace)
                k0 = g["draw1"] + 0.1                     # the cut (or freeze) sits right after the completed shape,
                still_to = s["click_move"] - 0.02         # in the still footage before the pointer sets off for the
                if cut > still_to - k0:                   # target (its move lights a hover; the edit keeps that)
                    cut = still_to - k0
                    hold = (s["act"] - g["draw1"]) - after_name - cut
                if activity.peak(act, fps, k0, still_to) >= pace["activity_min_pct"]:
                    tl.warnings.append(f"{step['id']}: the picture changes while its click mark is held, so the "
                                       "recorded hold plays as recorded (R128 not applied)")
                else:                                     # the cue word lands so that the name lands on the release
                    r128 = {"mark": ai, "hold": hold, "draw1": g["draw1"],
                            "chunk": (k0, k0 + cut) if cut > 1 / fps else None,
                            "freeze": (k0, -cut) if cut < -1 / fps else None,
                            "anchor": g["draw1"] + hold - (name_off - c)}
        if r128:
            anchor = r128["anchor"]
        elif s.get("live"):
            # the line sits where its mark's naming word lands on the recorded drawing, so a re-voiced line (new
            # wording or pauses) slides into place without a retake; otherwise the runner's timing (line at step start)
            mt = (line or {}).get("marks") or []
            t_draw, mi = s.get("draw", (None, None))
            at = shifted(mt[mi]["at_s"], bts) if t_draw is not None and mi is not None and mi < len(mt) else None
            anchor = (t_draw - at if at is not None else s["start"]) + c
        else:
            anchor = s["move"] if kind in ("click", "hover", "type", "switch_tab", "drag") else s["start"] + s["cue"]
        first_in = min(s.get("move", anchor), anchor) - cuts["keep_before_move"]
        V = max(vt.get(kind, 1.0), step.get("dwell", {}).get("min_s", 0.0))
        # a click that opens a tab shows the new, blank tab at once: stop at the click, freeze it for the ring
        opens_tab = kind == "click" and "act" in s and cam.is_nav_result(step, [e for e in events if e["step_id"] == step["id"]])
        after = 0.05 if opens_tab else cuts["keep_after_action"]
        spans = [[first_in, max(anchor, s.get("drop", s.get("act", anchor))) + after],   # a drag: to the drop
                 [s["result"] - cuts["keep_before_result"], s["result"] + V]]
        lapse = None                                      # a live wait over realtime_max_s is time-lapsed (R39)
        if kind == "wait_claude" and tls.get("before_card_s"):   # what is on screen as Claude starts (a skill
            spans[0][1] = max(spans[0][1], s["act"] + tls["before_card_s"])   # loading) is named and marked at 1x
        if kind == "wait_claude" and spans[1][0] - spans[0][1] > tls["realtime_max_s"]:
            g = s["result"] - s["act"]
            sid_events = [e for e in events if e["step_id"] == step["id"]]
            seen = [tv(e["t_mono"]) for e in sid_events if e["phase"] == "prompt_seen"]
            done = [tv(e["t_mono"]) for e in sid_events if e["phase"] == "prompt_approved"]
            keeps = [(a - tls["prompt_before_s"], next((d for d in done if d >= a), a) + tls["prompt_after_s"])
                     for a in seen]
            card = None
            if g > tls["card_above_s"]:
                text = (step.get("timelapse") or {}).get("card_text") or tls["card_text"]
                title, _, sub = text.format(minutes=max(1, round(g / 60))).partition(": ")
                card = (tls["card_s"], title, sub)
            target = tls["long_lapse_s"] if card else tls["lapse_s"]
            if line:                                      # the lapse runs at least as long as what is left of its
                kept, pos = 0.0, spans[0][1]              # line when it starts, less the result at 1x and the
                for k0, k1 in sorted(keeps):              # prompts at 1x, which play on top of the lapse (else the
                    k0, k1 = max(k0, pos), min(k1, spans[1][0])   # picture outruns the line: 7 s of silence after
                    if k1 > k0:                                   # p5.15e in p5_take02)
                        kept, pos = kept + k1 - k0, k1
                target = max(target, line["length_s"] - (card[0] if card else 0.0)
                             - (spans[0][1] - (anchor - c)) - (spans[1][1] - spans[1][0]) - kept)

            lapse = (keeps, target, card)
        if kind == "wait_claude" and lapse is None:      # R39 in a wait short enough for the cut rules too: each
            sid_events = [e for e in events if e["step_id"] == step["id"]]   # approval plays at 1x (full_take02's
            seen = [tv(e["t_mono"]) for e in sid_events if e["phase"] == "prompt_seen"]   # p5.16d cut it out)
            done = [tv(e["t_mono"]) for e in sid_events if e["phase"] == "prompt_approved"]
            for a in seen:
                spans.append([a - tls["prompt_before_s"], next((d for d in done if d >= a), a) + tls["prompt_after_s"]])
            merged = []
            for sp in sorted(spans):
                if merged and sp[0] - merged[-1][1] <= cuts["cut_above_s"]:
                    merged[-1][1] = max(merged[-1][1], sp[1])
                else:
                    merged.append(list(sp))
            spans = merged
        elif kind == "scroll":                            # a reply read on camera: its holds at 1x, the scroll
            hold = tlp.get("scroll_hold_s", 2.0)          # sped up to fit its line (or scroll_s without one)
            spans = [[first_in, s["act"] + hold], [s["result"] - hold, s["result"] + V]]
            target = max(tlp.get("scroll_s", 15.0), (line["length_s"] - c - 2 * hold) if line else 0.0)
            lapse = ([], target, None, False)
        if spans[1:] and spans[1][0] - spans[0][1] <= cuts["cut_above_s"]:
            spans = [[spans[0][0], max(spans[0][1], spans[1][1])]]
        spans[0][0] = max(spans[0][0], src_pos)                           # never replay footage already shown
        # the cue word's edit offset into the step's first span. For an R128 step the anchor is an edit-time
        # quantity (draw1 plus the edit's hold, less the lead-in), and the draw's end always precedes the cut, so the
        # offset is the same whether the recorded hold is cut, frozen or left (Fable's review, round 4: a correction
        # here for an anchor "past the cut" put seven names 0.1 to 0.16 s before their release)
        a_off = anchor - spans[0][0]
        forced = {}                                       # span boundaries that are hard cuts (0) or freezes (s),
        if r128 and (r128["chunk"] or r128["freeze"]):    # whatever the gap
            k0, k1 = r128["chunk"] or (r128["freeze"][0], r128["freeze"][0])   # R128: the recorded hold is still
            if spans[0][0] < k0 <= k1 < spans[0][1]:      # footage; the edit keeps just enough of it for its own
                spans = [[spans[0][0], k0], [k1, spans[0][1]]] + spans[1:]   # hold and the click, or freezes it
                forced[0] = r128["freeze"][1] if r128["freeze"] else 0.0     # longer when the recording is short
            else:
                r128["chunk"] = r128["freeze"] = None
        slow = None                                       # a pointer move the page made slow (s7_take02: 24 s inside
        if (kind in ("click", "hover", "type", "switch_tab") and not s.get("live") and not opens_tab and "arrive" in s  # the panel):
                and s["arrive"] - s["move"] > cuts.get("slow_move_s", 2.5)          # cut its still middle; the edit
                and spans[0][0] < s["move"] < s["arrive"] < spans[0][1]):        # draws the cursor move short
            spans = [[spans[0][0], s["move"] + 0.35], [s["arrive"] - 0.45, spans[0][1]]] + spans[1:]
            slow = 0
            tl.notes.append(f"{step['id']}: the pointer move took {s['arrive'] - s['move']:.1f}s in the take; "
                            "its middle is cut")
        # dead air (R25, think of a radio show): the next line starts gap_between_lines after this one, or runs
        # straight on after a comma; the silence runs longer, up to max_silence_s, only while the picture changes
        quiet_end = None
        if prev_line_end is None:
            e_req = first_lead + c
        else:
            if prev_comma:
                next_start = prev_speech_end + pace["comma_pause_s"] - (meta["words"][0]["start"] if meta else 0.0)
                quiet_end = next_start
            else:
                next_start = prev_line_end + pace["gap_between_lines"]
                quiet_end = quiet_until(prev_line_end, next_start)
                if quiet_end > next_start + 1e-3:
                    tl.notes.append(f"{step['id']}: the picture changes after the last line, so the silence may run "
                                    f"{quiet_end - prev_line_end:.2f}s (R25)")
            e_req = max(next_start + part_pause + c, prev_result + pace["pause_after_result"] + part_pause + c)
            # still too late: cut into the last step's still tail. It shows the result the next footage opens on,
            # and the result keeps its pause_after_result (David cut 06a's tail this way for the run-on, R25)
            last = tl.segs[-1] if tl.segs else None
            late = tl.T + a_off - c - (quiet_end + part_pause)
            if late > 1e-3 and last and last["type"] == "clip" and not tl.pending and abs(last["src_out"] - src_pos) < 1e-3:
                floor = max(last["src_in"], prev_s["result"] + pace["pause_after_result"], prev_s.get("act", 0.0) + 0.05)
                k = min(late, last["src_out"] - floor)
                if k > 1e-3 and activity.peak(act, fps, last["src_out"] - k, last["src_out"]) < pace["activity_min_pct"]:
                    last["src_out"], last["dur"] = round(last["src_out"] - k, 4), round(last["dur"] - k, 4)
                    tl.T -= k
                    tl.pending = "cut"
                    tl.notes.append(f"{step['id']}: cut {k:.2f}s of still picture from the end of {prev_s['id']} so "
                                    "the line starts on time (R25)")
        for j in [j for j in joins if src_pos < j <= spans[0][0]]:   # the Part 5 pause (R70): what follows is the
            owed = e_req - a_off - tl.T                    # second recording. The picture the last
            if owed > 1e-3:                                                 # line still needs comes from the first
                tl.bridge(src_pos, min(j, src_pos + owed), owed,            # recording's tail, not a freeze of the
                          f"{step['id']}: the first recording ends before the last line does")   # second's first
            src_pos, tl.pending = j, "cut"                                  # frame (full_take02: 12.8 s); the rest of
            section_cuts.append((step["id"], j))                            # the tail is left out
        dmin = e_req - a_off - tl.T
        dmax = None if quiet_end is None else quiet_end + part_pause + c - a_off - tl.T
        tl.bridge(src_pos, spans[0][0], dmin, f"{step['id']}: narration needs more picture than was recorded", dmax)
        span_t = tl.T
        tl.clip(*spans[0])
        e_anchor = span_t + a_off
        if opens_tab:
            tl.hold(s["act"], cuts["ring_hold_s"], f"{step['id']}: the click ring, before the new tab")
        for i, (prev, nxt) in enumerate(zip(spans, spans[1:])):  # inside a typing step: the typing, sped up (R67)
            if i in forced and forced[i] > 0:             # R128: still footage either side, so neither is seen
                tl.hold(prev[1], forced[i], f"{step['id']}: the click mark's hold outlasts the recording")
            elif i in forced:
                tl.pending = "cut"
            elif lapse:
                tl.timelapse(prev[1], nxt[0], *lapse)
            else:
                tl.bridge(prev[1], nxt[0], 0.0, f"{step['id']}: inside the step",
                          treatment="speed" if kind == "type" and i != slow else None)
            n0 = len(tl.segs)
            tl.clip(*nxt)
            if i in forced and len(tl.segs) > n0 and tl.segs[n0]["type"] == "clip":   # the first segment this added:
                tl.segs[n0]["still_cut"] = True           # a drop may split it (Fable, round 6). The mark is up
                                                          # across the cut: no camera change may hide here
        if r128:
            d1 = tl.to_edit(r128["draw1"])
            rel, clk = d1 + r128["hold"], tl.to_edit(s["act"])
            r128_sched[step["id"]] = {"mark": r128["mark"], "release": round(rel, 4), "click": round(clk, 4),
                                      "arrive": round(tl.to_edit_near(s.get("arrive", s["act"] - 0.3)), 4)}
            tl.notes.append(f"{step['id']}: click mark drawn by {d1:.2f}s, held {r128['hold']:.2f}s and released on "
                            f"the name at {rel:.2f}s; the click at {clk:.2f}s, {clk - rel:.2f}s after the name"
                            + (f"; {r128['chunk'][1] - r128['chunk'][0]:.2f}s of the recorded hold cut" if r128["chunk"]
                               else f"; the picture frozen {r128['freeze'][1]:.2f}s to lengthen the recorded hold"
                               if r128["freeze"] else "") + " (R128)")
        prev_result = tl.to_edit(s["result"])
        src_pos = spans[-1][1]
        executed.append((step, s))
        prev_part, prev_s = step.get("part"), s
        if line:
            place(step, s, line, meta, bts, e_anchor - c, e_anchor)
            if r128 and abs(narration[-1]["name_at"] - r128_sched[step["id"]]["release"]) > 1 / fps:
                tl.warnings.append(f"{step['id']}: the name lands {narration[-1]['name_at'] - r128_sched[step['id']]['release']:+.3f}s "
                                   "from the mark's release (R128 arithmetic)")

    for n, n2 in zip(narration, narration[1:]):          # a run-on: the earlier line's silent tail stops at the next
        last = n["parts"][-1]
        over = last["at"] + last["out"] - last["in"] - n2["start"]
        if over > 1e-3:
            last["out"] = round(last["out"] - over, 4)
            n["length"] = round(n["length"] - over, 4)
    prev_end = 0.0
    for n in narration:                                   # what dead air is left, and where
        gap = n["start"] - prev_end
        if gap > pace["max_silence_s"] + 0.05 and prev_end > 0:
            tl.warnings.append(f"{gap:.1f}s without narration before {n['step']} ({prev_end:.1f}-{n['start']:.1f}s)")
        prev_end = n["start"] + n["length"]
    need = max(prev_line_end or 0, prev_result or 0) + pace["end_pad"] - tl.T   # picture under the last line, then out
    show = max(0.0, min(need, src_last - src_pos))
    tl.clip(src_pos, src_pos + show)
    tl.hold(src_pos + show, need - show, "end: narration runs past the recording")

    # R83: a cut of Claude's working time (from a prompt's send to Claude going idle) gets a visible transition on
    # the camera sequence, so the viewer knows time has passed; other cuts stay hard (R34), a time-lapse needs none
    transitions, wct, cands, busy = [], cuts.get("work_cut_transition"), {}, []
    if wct:
        send = None
        for step, s in executed:
            if s["kind"] == "click" and "Send message" in json.dumps(step["action"].get("target", {})):
                send = s["act"]
            elif s["kind"] == "wait_claude" and send is not None:
                busy.append((send, s["result"]))
                send = None
        cands, prev_src = {}, None                        # the cuts of each prompt's working time; one is chosen
        for seg in tl.segs:                               # once the marks are laid out (below)
            if seg["type"] == "clip" and prev_src is not None and seg["src_in"] - prev_src > 1.5 / fps:
                mid = (prev_src + seg["src_in"]) / 2
                k = next((i for i, (a, b) in enumerate(busy) if a <= mid <= b), None)
                if k is not None:
                    cands.setdefault(k, []).append({"t": seg["t"], "s": wct["s"], "type": wct["type"],
                                                    "align": wct["align"], "skipped_s": round(seg["src_in"] - prev_src, 3)})
            prev_src = seg["src_out"] if seg["type"] == "clip" else seg["src_t"]

    track, _ = build_track(run_dir, cal, events)
    W, H = track["width"], track["height"]
    clicks = [{"step": c["step"], "t": round(tl.to_edit(c["t"]), 4), "at": c["at"]} for c in track["clicks"]
              if tl.to_edit(c["t"]) is not None]
    in_cut = {step["id"] for step, _ in executed}         # an excerpt: the other steps' moves (their live marks) are
    logged_moves = [{**m, "t0": round(tl.to_edit_near(m["t0"]), 4), "t1": round(tl.to_edit_near(m["t1"]), 4),
                     **({"live": True} if m.get("gesture") else {})} for m in track["moves"]   # not in its footage
                    if not doc.get("excerpt") or m.get("step") in in_cut]
    logged_moves = arrows_for_small(logged_moves, {st_["id"]: st_ for st_, _ in executed}, st["marks"],
                                    track["width"], track["height"], tl.notes,
                                    cal["geometry_measured"]["px_per_css"])
    hidden = []                                           # R47: no cursor in a live wait, except at its approvals
    for step, s in executed:
        if s["kind"] != "wait_claude":
            continue
        n = next((x for x in narration if x["step"] == step["id"]), None)     # through its line, which may run on
        a = tl.to_edit_near(s["act"]) + 0.3                                    # over the result (p2.09)
        z = max(tl.to_edit_near(s["result"]), n["start"] + n["length"] if n else 0.0)
        mine = [e for e in events if e["step_id"] == step["id"]]
        for e in mine:
            if e["phase"] == "cursor_move_start" and (e.get("detail") or {}).get("gesture") == "approve":
                done = next((x for x in mine if x["phase"] == "prompt_approved" and x["t_mono"] >= e["t_mono"]), e)
                s0, s1 = tl.to_edit_near(tv(e["t_mono"])) - 0.5, tl.to_edit_near(tv(done["t_mono"])) + 1.5
                if s0 > a:
                    hidden.append([round(a, 4), round(s0, 4)])
                a = max(a, s1)
        if z > a:
            hidden.append([round(a, 4), round(z, 4)])
    for step, s in executed:                              # and in a live step with no pointer: a reply read on camera,
        n = next((x for x in narration if x["step"] == step["id"]), None)       # a line over the result (s7_take06:
        if step.get("segment") == "live" and s["kind"] in ("scroll", "none") and n:   # the parked cursor sat on the
            hidden.append([round(n["start"], 4), round(n["start"] + n["length"], 4)])  # form at 3:15-3:57)
    merged = []                                           # spans that touch become one, or the cursor blinks between
    for h in sorted(hidden):                              # them; so do spans with nothing for the cursor to do between
        idle = merged and not any(merged[-1][1] - 0.3 <= m["t0"] <= h[0] + 0.3 for m in logged_moves) \
            and not any(merged[-1][1] <= c["t"] <= h[0] for c in clicks)   # (a part boundary's pause in a reply)
        if merged and (h[0] <= merged[-1][1] + 0.5 or idle):
            merged[-1][1] = max(merged[-1][1], h[1])
        else:
            merged.append(list(h))
    hidden = merged
    live_steps = {sid for sid, s in b.items() if s.get("live")}
    for n in narration:                                   # a live mark put its draw and hold before the click, unless
        if n["cue_word"] and (n["step"] not in live_steps or n["step"] in r128_sched):   # R128 re-timed it
            t_click = next((c["t"] for c in clicks if c["step"] == n["step"]), None)
            if t_click is not None:
                n["click_after_cue_s"] = round(t_click - n["cue_at"], 3)
                if n["name_at"] is not None:
                    n["click_after_name_s"] = round(t_click - n["name_at"], 3)
                    if not 0.0 <= n["click_after_name_s"] <= cuts["click_after_name_max_s"]:
                        tl.warnings.append(f"{n['step']}: click lands {n['click_after_name_s']:+.2f}s from the name "
                                           f"(take recorded with different narration timing?)")
    g = cal["geometry_measured"]
    ox, oy, k = g["viewport_origin_px"]["x"], g["viewport_origin_px"]["y"], g["px_per_css"]
    css_px = lambda b: (ox + b["x"] * k, oy + b["y"] * k, ox + (b["x"] + b["width"]) * k, oy + (b["y"] + b["height"]) * k)
    targets = {e["step_id"]: css_px(e["target_css_box"]) for e in events
               if e["phase"] == "action" and e.get("target_css_box")}

    # marks: when (the naming word in the placed line) and where (logged box, else OCR on the frame)
    ms = st["marks"]
    sub = lambda x: re.sub(r"\{(\w+)\}", lambda m_: doc["variables"].get(m_.group(1), m_.group(0)), x)
    placed = {n["step"]: n for n in narration}
    logged_boxes = {(e["step_id"], (e.get("detail") or {}).get("mark")): e.get("target_css_box")
                    for e in events if e["phase"] == "text_box" and (e.get("detail") or {}).get("role") != "subject"}
    subject_box = {e["step_id"]: css_px(e["target_css_box"]) for e in events if e["phase"] == "text_box"
                   and (e.get("detail") or {}).get("role") == "subject" and e.get("target_css_box")}
    subjects = [(placed[sid]["start"], placed[sid]["start"] + placed[sid]["length"], b)
                for sid, b in subject_box.items() if sid in placed]
    subjects += [(placed[st_["id"]]["start"], placed[st_["id"]]["start"] + placed[st_["id"]]["length"], targets[st_["id"]])
                 for st_, s_ in executed if s_["kind"] == "scroll" and st_["id"] in placed and st_["id"] in targets]
    want = []                                             # (a reply being read is a subject: captions keep off it)
    hl_want = []                                          # R122, R142: highlighter marks, scheduled after the others

    # overlays (R77, R79): a card in David's BulletPanel look, up from the step's line start to the end of
    # until_step's line; its list items appear on their words, and marks that target it become highlights on it
    overlays, by_overlay = [], {}
    for step, s in executed:
        o, n = step.get("overlay"), placed.get(step["id"])
        if not o or not n:
            continue
        until = placed.get(o.get("until_step", step["id"]), n)
        meta = timing.of(n)
        bts = [tuple(x) for x in n.get("beats", [])]
        items = []
        for it in o.get("items", []):
            w = mk.word_time(meta, sub(it["at_word"]), it.get("occurrence", 1))
            if w is None:
                tl.warnings.append(f"{step['id']}: overlay item word {it['at_word']!r} not found in the line; shown "
                                   "from the start")
                w = 0.0
            items.append({"text": sub(it["text"]), "at": round(n["start"] + shifted(w, bts), 4)})
        layer = {"id": o["id"], "step": step["id"], "layout": o["layout"], "title": sub(o.get("title") or ""),
                 "text": sub(o.get("text") or ""), "items": items, "edge": o.get("edge", "left"),
                 "t0": round(n["start"], 4), "t1": round(until["start"] + until["length"] + ms["overlay_tail_s"], 4),
                 "highlights": []}
        overlays.append(layer)
        by_overlay[o["id"]] = layer
        tl.notes.append(f"{step['id']}: overlay {o['id']!r} ({o['layout']}) {layer['t0']:.2f}-{layer['t1']:.2f}s")
    overlays += plan_overlays(ex_dir / "overlays.json", placed, ms, sub, tl)   # R134: the overlay plan's compositions

    def find_box(sid, key, target, t_name):
        """A mark target's box in frame px: the runner's logged box, else OCR of its text on the frame (with
        match_to, the box spans from one text to the other: a form, a tab strip)."""
        if target.get("box"):                           # frame px, set after the take: another step's logged box
            return tuple(target["box"]), "fixed"        # (OCR can't read it), or the whole of what the line names
        lb = logged_boxes.get((sid, key))
        if lb and lb["width"] > 0 and lb["height"] > 0:
            return css_px(lb), "log"
        if target.get("match"):
            ob = target.get("ocr_band")
            band = (0, oy) if target.get("chrome") else ((ob[0] * H, ob[1] * H) if ob else None)
            for dt in (0, 1, 2, 3):                     # the page may still be loading: try later frames too
                src_t = tl.to_src(t_name + ms["ocr_after_name_s"] + dt)
                xb = target.get("ocr_xband")                # where across the frame (the Explorer, not the panel)
                box = mk.ocr_box(run_dir, src_t, sub(target["match"]), fps, band, target.get("whole_line", False),
                                 xband=(xb[0] * W, xb[1] * W) if xb else None)
                to = mk.ocr_box(run_dir, src_t, sub(target["match_to"]), fps, band,
                                xband=(xb[0] * W, xb[1] * W) if xb else None) if box and target.get("match_to") else None
                for inc in target.get("include", []) if box else []:   # more of the thing it names (R84: the
                    ib = mk.ocr_box(run_dir, src_t, sub(inc), fps, band,    # form's own tab row), near it
                                    xband=(box[0] - 60, box[2] + 60))
                    if ib:
                        box = (min(box[0], ib[0]), min(box[1], ib[1]), max(box[2], ib[2]), max(box[3], ib[3]))
                    else:
                        tl.warnings.append(f"{sid}: mark text {inc!r} to include not found; the box leaves it out")
                if box and target.get("chrome") == "tab_strip":   # R84: whole tabs, not their titles
                    png = run_dir / "marks_ocr" / f"{int(round(src_t * fps)):06d}" / "frame.png"
                    tabs = mk.whole_tabs(png, [box] + ([to] if to else []), ms["rect_pad_px"])
                    if tabs:
                        return tabs, "ocr, whole tabs"
                    tl.warnings.append(f"{sid}: no active tab found in the strip; the box frames the titles only")
                if box and target.get("match_to"):
                    box = (min(box[0], to[0]), min(box[1], to[1]), max(box[2], to[2]), max(box[3], to[3])) if to else None
                if box:
                    return box, "ocr"
        return None, None

    for step, s in executed:
        for i, m in enumerate(step.get("marks", [])):
            if m["target"].get("of"):
                continue                                  # drawn live by the runner: comes from the log below
            n = placed.get(step["id"])
            meta = timing.of(n) if n else None
            w = mk.word_time(meta, sub(m["at_word"]), m.get("occurrence", 1)) if meta else None
            if w is None:
                tl.warnings.append(f"{step['id']}: mark word {m['at_word']!r} not found in the line; mark left out")
                continue
            bts = [tuple(x) for x in n.get("beats", [])]
            t_name = n["start"] + shifted(w, bts)
            tgt = step["action"].get("target") or {}
            if step["action"]["type"] == "type" and m["target"].get("locator") == tgt.get("locator"):
                done = [tl.to_edit_near(tv(e["t_mono"])) for e in events                # a mark on the text this
                        if e["step_id"] == step["id"] and e["phase"] == "type_end"]   # step types waits for the
                if done and t_name < done[0] + 0.2:                                     # typing to end: the box
                    tl.notes.append(f"{step['id']}: mark at {m['at_word']!r} waits {done[0] + 0.2 - t_name:.2f}s "
                                    "for the typing to end (the box was measured on the finished text)")
                    t_name = done[0] + 0.2                                              # grows as it fills (p5.15c)
            r = mk.release_time(meta, sub(m["at_word"]), m.get("occurrence", 1),
                                sub(m["until_word"]) if m.get("until_word") else None)
            if m["target"].get("overlay"):                # a highlight on the overlay card, not a mark on screen
                ov = by_overlay.get(m["target"]["overlay"])
                if not ov or sub(m["target"].get("match", "")) not in ov["text"]:
                    tl.warnings.append(f"{step['id']}: overlay highlight {m['target'].get('match')!r} has no overlay "
                                       "up, or the text is not on it; left out")
                    continue
                d0 = t_name + ms["after_name_s"]
                d1 = d0 + ms["fade_in_s"]
                f0 = max(d1 + ms["hold_s"], (n["start"] + shifted(r, bts) if r is not None else 0) + ms["release_after_s"])
                ov["highlights"].append({"match": sub(m["target"]["match"]), "draw0": round(d0, 4), "draw1": round(d1, 4),
                                         "fade0": round(f0, 4), "fade1": round(f0 + ms["fade_s"], 4)})
                tl.notes.append(f"{step['id']}: highlight on overlay {ov['id']!r} at {d0:.2f}s: "
                                f"\"{m['target']['match'][:40]}\"")
                continue
            box, how = find_box(step["id"], i, m["target"], t_name)
            if not box:
                tl.warnings.append(f"{step['id']}: no box for the {m['kind']} mark; left out")
                continue
            if m["kind"] == "highlight":                  # a large region: everything else dimmed (R142)
                hl_want.append({"step": step["id"], "t_name": t_name, "box": box,
                                "t_release": n["start"] + shifted(r, bts) if r is not None else None})
                tl.notes.append(f"{step['id']}: highlight at {t_name:.2f}s, box from {how}: "
                                f"{tuple(round(v) for v in box)}")
                continue
            tl.notes.append(f"{step['id']}: {m['kind']} mark at {t_name:.2f}s, box from {how}: "
                            f"{tuple(round(v) for v in box)}")
            stops = []                                    # an overview arrow's further stops (R48, R63)
            for k, st_ in enumerate(m.get("then", []) if m.get("style") == "fade" and m["kind"] == "arrow" else []):
                ws = mk.word_time(meta, sub(st_["at_word"]), st_.get("occurrence", 1))
                sbox = find_box(step["id"], f"{i}.{k}", st_["target"], n["start"] + shifted(ws, bts))[0] \
                    if ws is not None else None
                if sbox is None:                          # it rests only on what is named and found (R63)
                    tl.warnings.append(f"{step['id']}: arrow stop {st_['at_word']!r} not found (word or box); skipped")
                    continue
                stops.append({"t_name": n["start"] + shifted(ws, bts), "box": sbox})
            want.append({"step": step["id"], "kind": m["kind"], "style": m.get("style", "draw"), "stops": stops,
                         "t_name": t_name, "t_release": n["start"] + shifted(r, bts) if r is not None else None, "box": box})
    moves, layers, mark_warn = mk.lay_out(want, logged_moves, ms, W, H)
    tl.warnings += mark_warn
    releases = {(r["step"], r["mark"]): tl.to_edit_near(r["t"]) for r in track.get("releases", [])}
    for mv in moves:                                      # live marks: the shape follows the logged drawing move
        if mv.get("live") and mv.get("gesture") in ("rect", "arrow"):
            f0 = releases.get((mv["step"], mv.get("mark")), mv["t1"] + ms["hold_s"])
            sch = r128_sched.get(mv["step"])              # R128: a click target's mark is released on the name
            if sch and sch["mark"] == mv.get("mark"):
                f0 = sch["release"]
            layers.append({"step": mv["step"], "kind": mv["gesture"], "style": "draw", "live": True,
                           "mark": mv.get("mark"), "from": mv["from"], "to": mv["to"], "draw0": mv["t0"],
                           "draw1": mv["t1"], "fade0": round(f0, 4), "fade1": round(f0 + ms["fade_s"], 4)})
    click_at = {c["step"]: c["at"] for c in clicks}
    for sid_, sch in r128_sched.items():                  # R128: the cursor leaves the mark as it is released and
        mine = [mv for mv in moves if mv["step"] == sid_]  # arrives just before the click lands on the name (R23)
        app = next((mv for mv in mine if mv.get("gesture") == "approach" and mv.get("mark") == sch["mark"]), None)
        draw = next((mv for mv in mine if mv.get("gesture") in ("rect", "arrow") and mv.get("mark") == sch["mark"]), None)
        mv = max((x for x in mine if not x.get("gesture") and x["t0"] <= sch["click"] + 1e-3),
                 key=lambda x: x["t0"], default=None)
        pt = click_at.get(sid_)
        if draw and draw["gesture"] == "rect" and app and mv and pt and \
                cam.dist((draw["from"]["x"], draw["from"]["y"]), (pt["x"], pt["y"])) < \
                cam.dist((draw["to"]["x"], draw["to"]["y"]), (pt["x"], pt["y"])):
            # the rectangle is drawn the other way round, ending at the corner nearer the click, so the move after the
            # release is short (the footage under the gesture is still, so the direction is the edit's to choose)
            a_, c_ = dict(draw["from"]), dict(draw["to"])
            app["to"], draw["from"], draw["to"], mv["from"] = c_, c_, a_, a_
            ly = next((l for l in layers if l.get("live") and l["step"] == sid_ and l.get("mark") == sch["mark"]), None)
            if ly:
                ly["from"], ly["to"] = c_, a_
            tl.notes.append(f"{sid_}: its rectangle is drawn from the far corner, ending nearer the click (R128)")
        if mv:
            d = cam.dist((mv["from"]["x"], mv["from"]["y"]), (mv["to"]["x"], mv["to"]["y"]))
            t1 = sch["click"] - 0.05                      # the move takes 0.3 s, longer for a far target (2000 px/s
            t0 = min(sch["release"], t1 - max(0.3, d / 2000.0))   # at most), setting off before the release then
            t0 = max(t0, (draw["t1"] if draw else t0) + 0.25)     # but never before the shape is complete
            mv["t0"], mv["t1"] = round(t0, 4), round(t1, 4)
            if t0 < sch["release"] - 0.05:
                tl.notes.append(f"{sid_}: the pointer sets off for the click {sch['release'] - t0:.2f}s before the "
                                f"mark's release ({d:.0f} px to travel, R128)")
    layers += highlights(hl_want, layers, ms, tl)
    for ly in layers:                                     # when the camera must show it: as the cursor sets off
        if ly["kind"] == "highlight":
            ly["need"] = ly["draw0"]
            continue
        app = [mv for mv in moves if mv["step"] == ly["step"] and mv.get("gesture") == "approach"
               and mv["t1"] <= ly["draw0"] + 1e-3]
        ly["need"] = round(max(app, key=lambda mv: mv["t1"])["t0"], 4) if app else ly["draw0"]
    # a drawn mark is the cursor's gesture (R49), so the cursor shows for it even where R47 hides it, as for an approval
    for mv in moves:
        if mv.get("gesture") in ("approach", "rect", "arrow", "retreat"):
            g0, g1 = mv["t0"] - 0.25, mv["t1"] + (0.4 if mv["gesture"] != "approach" else 0.0)
            cut = []
            for h0, h1 in hidden:
                if h1 <= g0 or h0 >= g1:
                    cut.append([h0, h1])
                    continue
                if h0 < g0:
                    cut.append([h0, round(g0, 4)])
                if h1 > g1:
                    cut.append([round(g1, 4), h1])
            hidden = cut
    hidden = [h for h in hidden if h[1] - h[0] > 0.5]     # a sliver between two gestures would only blink
    # R83: one transition per prompt, at its last cut of Claude's work before the result (David's round 2: one at his
    # own trim, none at the cut 10 s before it), preferably clear of marks and cursor gestures: the peel turns the
    # whole picture, the pen stroke with it (s7_take06 132.5 s, mid-way through p2.09's marks). If no cut is clear,
    # the last one, flagged: David keeps the ones he wants (2026-10-07).
    busy_spans = ([(ly["draw0"] - 0.2, ly["fade1"] + 0.2) for ly in layers]
                  + [(mv["t0"] - 0.2, mv["t1"] + 0.2) for mv in moves if mv.get("gesture")])
    sec = cuts.get("section_transition")                  # R34, R70: the join of a paused take sits at a part
    for sid_, j in section_cuts if sec else []:           # boundary, under the section dissolve
        t_j = next((seg["t"] for seg in tl.segs if seg["type"] == "clip" and seg["src_in"] > j - 1.5 / fps), None)
        if t_j is not None:
            transitions.append({"t": round(t_j, 4), "s": sec["s"], "type": sec["type"], "align": sec["align"],
                                "section": True, "before_step": sid_})
            tl.notes.append(f"transition: {sec['type']} at {t_j:.2f}s, where the second recording starts ({sid_}, R70)")
    for k in sorted(cands):                               # every prompt gets one; David keeps the ones he wants
        long_ = [c for c in cands[k] if c["skipped_s"] >= wct.get("min_skip_s", 0.0)]   # R90: a cut under 1 s
        if not long_:                                                                    # hides no time
            tl.notes.append(f"transition: none for the prompt sent at {busy[k][0]:.2f}s src, its cuts skip "
                            + ", ".join(f"{c['skipped_s']:.2f}" for c in cands[k]) + f"s (under {wct['min_skip_s']}s, R90)")
            continue
        clear = [c for c in long_ if not any(a < c["t"] + c["s"] and c["t"] - 0.2 < b for a, b in busy_spans)]
        tr = clear[-1] if clear else {**long_[-1], "crosses_mark": True}
        transitions.append(tr)
        tl.notes.append(f"transition: {tr['type']} at {tr['t']:.2f}s, the last "
                        + ("clear cut" if clear else "cut (every cut of this prompt's work falls on a mark or a gesture)")
                        + f" of Claude's work for its prompt ({tr['skipped_s']:.2f}s skipped, R83)")

    # camera: beats (boxes that must be on screen, and when) and full-frame needs (navigation), SPEC §7.2
    by_step = {}
    for e in events:
        by_step.setdefault(e["step_id"], []).append(e)
    beats_, fulls = [], []
    pad = lambda bx, d: (bx[0] - d, bx[1] - d, bx[2] + d, bx[3] + d)
    for step, s in executed:
        sid = step["id"]
        V = max(vt.get(s["kind"], 1.0), step.get("dwell", {}).get("min_s", 0.0))
        mine = [ly for ly in layers if ly["step"] == sid]
        act = tl.to_edit_near(s["act"]) if "act" in s else None
        res = tl.to_edit_near(s["result"]) + V
        if step["action"]["type"] == "navigate":
            fulls.append({"step": sid, "t0": min([tl.to_edit_near(s["start"])] + [ly["need"] for ly in mine]),
                          "t1": max([res] + [ly["fade1"] for ly in mine])})
        elif s["kind"] == "switch_tab" and act is not None:      # the pointer goes up to the tab strip (R40)
            fulls.append({"step": sid, "t0": tl.to_edit_near(s.get("move", s["act"])) - 0.2, "t1": res})
        elif cam.is_nav_result(step, by_step.get(sid, [])) and act is not None:
            fulls.append({"step": sid, "t0": act, "delay": 0.35,      # after the click ring, unless a cut comes first
                          "t1": max([res] + [ly["fade1"] for ly in mine if ly["draw0"] > act])})
        if (step.get("zoom") or {}).get("mode") == "none":      # an overview (the dashboard tour, p5.14b): the whole
            n = placed.get(sid)                                 # page through its line and its marks, no beats
            fulls.append({"step": sid, "t0": min([n["start"] if n else (act if act is not None else res - V)]
                                                 + [ly["need"] for ly in mine]),
                          "t1": max([res] + ([n["start"] + n["length"]] if n else []) + [ly["fade1"] for ly in mine])})
            continue
        if sid in subject_box and sid in placed:
            beats_.append({"step": sid, "t": placed[sid]["start"], "box": subject_box[sid]})
        zon = (step.get("zoom") or {}).get("on")         # R156: what a tight step's shot is on, where the run log has
        if zon and sid in placed:                         # no box (a typed field); apart: framed on its own, even
            beats_.append({"step": sid, "t": placed[sid]["start"], "box": tuple(zon["box"]),   # inside a dialog
                           "apart": bool(zon.get("apart"))})                                  # framed whole
        for ly in mine:
            for k in ly.get("path", [])[1:]:
                beats_.append({"step": sid, "t": k["t"], "box": pad((min(k["from"]["x"], k["to"]["x"]),
                               min(k["from"]["y"], k["to"]["y"]), max(k["from"]["x"], k["to"]["x"]),
                               max(k["from"]["y"], k["to"]["y"])), ms["stroke_px"])})
            a, c = (ly["from"]["x"], ly["from"]["y"]), (ly["to"]["x"], ly["to"]["y"])
            # a mark in the browser chrome (the address bar, a tab): full frame while it shows (R40). Judged by the
            # rectangle's centre or the arrow's head, not the top edge: a rectangle's pad reaches 1 px above the page
            # on a target at the page's top (p2.19's analysis name in round 3: a needless full frame, R125)
            if (c[1] if ly["kind"] == "arrow" else (a[1] + c[1]) / 2) < oy:
                fulls.append({"step": sid, "t0": ly["need"], "t1": ly["fade1"]})
                continue
            t_need = ly["need"]
            if st["zoom"].get("safe_px"):                 # R123: never pan a mark out of view while it's up: a move
                up = [o["fade0"] for o in layers if o is not ly and o["draw0"] < ly["need"] <= o["fade1"] + 1e-6]
                if up:                                    # toward the next mark starts as the last one starts to fade
                    t_need = min(max(t_need, max(up) + st["zoom"]["pan_s"]), ly["draw1"])   # (a mark released as the
                                                          # next move starts, fade1 == need, counts as up: round 4)
            beats_.append({"step": sid, "t": t_need, "box": pad((min(a[0], c[0]), min(a[1], c[1]),
                                                                max(a[0], c[0]), max(a[1], c[1])), ms["stroke_px"])})
        if sid in targets and "arrive" in s and step["action"]["type"] not in ("navigate", "switch_tab"):
            beats_.append({"step": sid, "t": tl.to_edit_near(s["arrive"]), "box": targets[sid]})
        elif sid in targets and s["kind"] == "scroll":       # a reply read on camera: a band through the middle of
            x0, y0, x1, y1 = targets[sid]                       # the conversation, which the text scrolls through,
            half = (H / (step.get("zoom") or {}).get("max", st["zoom"]["level"]) - 2 * st["zoom"]["margin_px"]) / 2
            cy = (y0 + y1) / 2                                  # sized to fit at the step's zoom
            beats_.append({"step": sid, "t": tl.to_edit_near(s["act"]),
                           "box": (x0, max(y0, cy - half), x1, min(y1, cy + half))})
    cut_times = [round(seg["t"], 4) for prev, seg in zip(tl.segs, tl.segs[1:])
                 if ((seg["type"] == "clip" and (prev["type"] == "hold" or seg.get("transition_in") == "cut"))
                     or seg.get("card")) and not seg.get("still_cut")]   # an R128 cut joins identical frames with
                                                                        # the mark up: a camera jump there would show
    for seg in tl.segs:                                   # a title card (R39) is full frame, from its first frame
        if seg.get("card"):
            fulls.append({"step": "card", "t0": seg["t"], "t1": seg["t"] + seg["dur"]})
    for t0, t1 in tl.lapses:                              # so is a live time-lapse: the whole IDE at work, the
        fulls.append({"step": "lapse", "t0": t0, "t1": t1})   # panel and the Explorer where files appear
    tight = {st_["id"]: st_["zoom"]["max"] for st_ in doc["steps"] if (st_.get("zoom") or {}).get("max")}
    for bt in beats_:                                     # tight spots (R42): the step's own zoom.max
        if bt["step"] in tight:
            bt["level"] = tight[bt["step"]]
    wholes = whole_subjects(executed, [st_["id"] for st_ in doc["steps"]], b, placed, tl, run_dir, fps, st["zoom"],
                            find_box, W, H)
    for w in wholes:                                      # R123: what a line refers to is shown whole: the dialog's
        if not w["framed"]:                               # own beats share its box, so the camera frames all of it
            continue                                      # (a panned dialog, R125: its beats are framed on their own)
        for bt in beats_:
            if w["t0"] - st["zoom"]["pan_s"] <= bt["t"] <= w["t1"] and not bt.get("apart"):
                bt.update(box=cam._union([bt["box"], w["box"]]), whole=True, t_end=w["t1"], fit=w["fit"],
                          align=w.get("align"))
        beats_.append({"step": w["step"], "t": w["t0"], "box": w["box"], "whole": True, "t_end": w["t1"],
                       "fit": w["fit"], "align": w.get("align")})
    subjects += [(w["t0"], w["t1"], w["box"], "soft") for w in wholes]   # captions keep off it where they can
    keys, cam_notes = cam.plan_shots(beats_, fulls, cut_times, st["zoom"], W, H, oy, tl.T)
    for k0, k1 in zip(keys, keys[1:]):                    # a change on a cut lands on the cut's own frame
        if k1["t"] - k0["t"] < 1 / fps:
            fc = round(k1["t"] * fps)
            k0["t"], k1["t"] = round((fc - 1) / fps, 4), round(fc / fps, 4)
    for c in clicks:                                      # a ring never carries over a cut onto another screen
        nxt = next((t for t in cut_times if t > c["t"]), None)
        if nxt is not None:
            c["until"] = nxt
    tl.notes += cam_notes

    caps.sort(key=lambda c: c["start"])                   # a run-on line's last cue lingers into the next line's
    for c0, c1 in zip(caps, caps[1:]):                    # first: it ends where that one starts (overlapping cues
        if c0["end"] > c1["start"]:                       # come into Premiere merged plus a duplicate; R85)
            c0["end"] = c1["start"]
    overlay_variants(overlays, keys, tl, run_dir, fps, W, H, layers)   # R140: dark on light, light on dark
    cards = [(o["t0"], o["t1"], overlay_area(o, W, H) if o.get("plan_overlay")   # captions keep off the cards
              else mk.overlay_box(o["edge"], W, H))       # and the compositions (by box or edge band)
             for o in overlays if (overlay_area(o, W, H) if o.get("plan_overlay") else o.get("edge"))]
    line_spans = [(n["start"], n["start"] + n["length"], n["step"]) for n in narration]   # R182
    clear_for = lambda t0, t1: keep_clear(t0, t1, moves, clicks, targets, layers, keys, (W, H), subjects, cards,
                                          line_spans)
    caps = place_captions(caps, clear_for, st["captions"], (W, H))
    tl.warnings += [f"caption at {c['start']:.1f}s: {c['placement_warning']}" for c in caps if c.get("placement_warning")]
    masks = []                                            # privacy findings David chose to blur (R56, SPEC §10)
    rep_p, dec_p = run_dir / "privacy_report.json", run_dir / "privacy_decisions.json"
    if rep_p.exists():                                    # David's choice per finding, else the pattern's standing
        decisions = json.loads(dec_p.read_text(encoding="utf-8")) if dec_p.exists() else {}   # decision (R127)
        for f in json.loads(rep_p.read_text(encoding="utf-8"))["findings"]:
            if decisions.get(f["id"], f.get("decision")) == "blur" and "src_t0" in f:
                masks.append({"id": f["id"], "why": f["pattern"], "box": f["box"],
                              "t0": round(tl.to_edit_near(f["src_t0"]), 4), "t1": round(tl.to_edit_near(f["src_t1"]), 4)})
    corrections = correction_spans(run_dir, tl.segs, tl)  # R173: recording flaws covered with a clean picture
    loud = None
    if st.get("loudness") and narration:                  # R177: the mix at YouTube's loudness, one shared amount
        from pipeline.edit import loudness
        mapping, loud = loudness.prepare(run_dir, [n["src"] for n in narration], st["loudness"])
        for n in narration:
            n["src"] = mapping[n["src"]]
        tl.notes.append(f"loudness (R177): voice {loud['voice_lufs_before']:.1f} -> {loud['voice_lufs_after']:.1f} LUFS "
                        f"(true peak {loud['voice_true_peak_dbtp']:.1f} dBTP); effects +{loud['effects_gain_db']:.1f} dB")
    if pace.get("mute_double_breaths", True):             # R181: no double breaths, found in the audio the viewer hears
        mute_double_breaths(run_dir, narration, tl)       # (after the loudness pass, as the check reads it)
    plan_doc = {"run_id": run_dir.name if doc.get("excerpt") else header["run_id"],    # an excerpt's own folder
                "steps_file": Path(steps_path).name, "gap_treatment": cuts["gap_treatment"],
                "fps": fps, "width": track["width"], "height": track["height"], "video": "raw.mp4",
                "durationInFrames": int(round(tl.T * fps)), "duration_s": round(tl.T, 3),
                "segments": tl.segs, "narration": narration,
                "cursor": {"moves": moves, "clicks": clicks, "hidden": hidden, "style": st["cursor"]},
                "camera": keys, "marks": {"layers": layers, "style": {k: ms[k] for k in (
                    "color", "stroke_px", "head_px", "corner_px", "overview_stroke_px", "overview_head_px",
                    "overview_arrow_color", "highlight") if k in ms}},
                "captions": {"burn": st["captions"]["burn_in_proxy"], "cues": caps,
                             "style": {k: st["captions"][k] for k in ("font", "size_px", "box_color", "box_opacity",
                                       "line_height", "pad_x_px", "pad_y_px", "text_stroke_px", "corner_radius_px") if k in st["captions"]}},
                "privacy_masks": masks, "corrections": corrections, "loudness": loud,
                "overlays": overlays, "transitions": transitions,
                "wholes": wholes, "click_targets": [{"step": c["step"], "box": [round(v, 1) for v in targets[c["step"]]]}
                                                    for c in clicks if c["step"] in targets],   # R123's line check
                "warnings": tl.warnings, "notes": tl.notes,
                "settings": st}
    holds_dir = run_dir / "holds"                  # freezes are stills cut from the recording (exact frame, any renderer)
    holds_dir.mkdir(exist_ok=True)
    for seg in tl.segs:
        if seg["type"] == "hold":
            n = int(round(seg["src_t"] * fps))
            seg["still"] = f"holds/hold_{n:06d}.png"
            out = run_dir / seg["still"]
            if not out.exists():
                subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(run_dir / "raw.mp4"), "-vf",
                                rf"select=eq(n\,{n})", "-frames:v", "1", str(out)], check=True)
    cs = st.get("click_sound") or {}                      # R137: a quiet click at every click the edit rings
    if loud and cs:                                       # R177: raised with the voice, so it sits where it did
        cs = dict(cs, peak_dbfs=round(click_sound.settings(cs)["peak_dbfs"] + loud["effects_gain_db"], 2))
    if cs.get("enabled") and clicks:
        wav = click_sound.write(run_dir / "audio" / click_sound.name(cs), cs)
        length = click_sound.settings(cs)["length_s"]
        sounded, free = [], -1.0                          # one at a time: a click on another's tail gets no sound,
        for c in sorted(clicks, key=lambda c: c["t"]):    # the same in Premiere and the proxy
            if c["t"] >= free and c["t"] < tl.T:
                sounded.append({"step": c["step"], "t": c["t"]})
                free = c["t"] + length
        plan_doc["click_sound"] = {"src": f"audio/{wav.name}", "peak_dbfs": click_sound.settings(cs)["peak_dbfs"],
                                   "length_s": length, "clicks": len(sounded), "at": sounded}
        if len(sounded) < len(clicks):
            tl.notes.append(f"click sound: {len(clicks) - len(sounded)} click(s) on another's tail left silent (R137)")
    if overlays or any(seg.get("card") for seg in tl.segs):  # cards and overlays use David's Arial Bold Italic
        (run_dir / "fonts").mkdir(exist_ok=True)
        shutil.copyfile(FONT, run_dir / "fonts" / "arialbi.ttf")
    (run_dir / "edit_plan.json").write_text(json.dumps(plan_doc, indent=2), encoding="utf-8")
    (run_dir / "captions.srt").write_text(srt(caps), encoding="utf-8")
    return plan_doc


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    g = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--gap=")), None)
    p = plan(args[0], args[1], g)
    print(json.dumps({k: p[k] for k in ("duration_s", "warnings", "notes")}, indent=2))
