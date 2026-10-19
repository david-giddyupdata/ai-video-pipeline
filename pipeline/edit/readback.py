"""Premiere read-back (S5; R60, R61): what David changed in Premiere, against the edit we exported.

    python -m pipeline.edit.readback runs/<run_id> [<project.prproj>] [--against=runs/<run_id>/edit_plan.json]

Reads the saved project (the newest .prproj in any export round, runs/<run_id>/premiere*/, unless one is named; never
Premiere's own XML export, see GOTCHAS), the XML we exported into that folder (<run_id>.xml) and the plan it was made
from (its edit_plan.json snapshot; runs/<run_id>/edit_plan.json for exports made before the snapshot). Prints a report
and writes readback.json into the same folder:

  cuts and beats  the camera sequence's pieces of the nest: footage cut, footage replayed (a beat), each tied to the
                  narration words either side
  narration       gaps between lines, splits inside a line, trims, and whether each line still sits on its picture
  clips and keys  every other track of both sequences against the export, keyframes in plan time
  captions        text and wrap, timing against their words, style and grid position (decoded from the project)
  implies         the setting or rule each change points at (R60), with the setting's current value
  --against       a re-plan beside his cut, line by line (gaps and beats), to see how close the rules get

Times are plan (nest) seconds unless marked "his" (seconds on his camera sequence).
"""
import difflib
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from pipeline.config import EXERCISES, ROOT
from pipeline.edit import activity, sentences
from pipeline.edit.prproj import TPS, Project

CACHE = ROOT / "audio_cache"
PARAM_TOL = {"position": 0.002, "scale": 0.1, "rotation": 0.1, "opacity": 0.5}
PARAMS = {"Position": "position", "Scale": "scale", "Rotation": "rotation", "Opacity": "opacity"}
DEFAULTS = {"position": (0.5, 0.5), "scale": 100.0, "rotation": 0.0, "opacity": 100.0}


# ------------------------------------------------------------------------------------------------- loading
def _keys(static, keys):
    return {"static": static, "keys": keys}


def xml_tracks(seq, fps):
    """Our export: {track name: [clip]}, clip = {name, start, end, in, out, params}, all in seconds; keyframe times
    in the clip's media seconds. Center becomes Premiere's Position (0.5 + Center)."""
    out, nest = {}, None
    for kind in ("video", "audio"):
        for i, tr in enumerate(seq.findall(f"media/{kind}/track"), 1):
            name = tr.get("MZ.TrackName") or f"{kind[0].upper()}{i}"
            clips = []
            for c in tr.findall("clipitem"):
                params = {}
                for prm in c.findall("filter/effect/parameter"):
                    pid = {"center": "position"}.get(prm.findtext("parameterid"), prm.findtext("parameterid"))
                    if pid not in DEFAULTS:
                        continue
                    val = ((lambda e: (0.5 + float(e.findtext("value/horiz")), 0.5 + float(e.findtext("value/vert"))))
                           if pid == "position" else (lambda e: float(e.findtext("value"))))
                    keys = [(int(k.findtext("when")) / fps, val(k)) for k in prm.findall("keyframe")]
                    params[pid] = _keys(val(prm), keys)
                s, e, i_, o_ = (int(c.findtext(k)) for k in ("start", "end", "in", "out"))
                if s == -1:                                   # held by a transition (R83): the clip starts where
                    s = round(clips[-1]["end"] * fps) if clips else e - (o_ - i_)   # the last one ended, and
                if e == -1:                                   # runs out - in
                    e = s + (o_ - i_)
                clips.append({"name": c.findtext("name"), "start": s / fps, "end": e / fps, "in": i_ / fps,
                              "out": o_ / fps, "params": params})
                if c.find("sequence") is not None:
                    nest = c.find("sequence")
            out[name] = clips
    return out, nest


def prproj_tracks(seq):
    """The saved project, in the same shape as xml_tracks."""
    out = {}
    for k in ("video_tracks", "audio_tracks"):
        for tr in seq[k]:
            clips = []
            for it in tr["items"]:
                params = {}
                for comp in it["effects"]["components"]:
                    for p in comp["params"]:
                        pid = PARAMS.get(p["name"])
                        if pid is None or (pid == "opacity" and comp.get("display_name") not in (None, "Opacity")):
                            continue
                        conv = (lambda v: tuple(v)) if pid == "position" else float
                        keys = [(k_["t_ticks"] / TPS, conv(k_["value"])) for k_ in p.get("keyframes", [])]
                        params[pid] = _keys(conv(p["static"]) if p.get("static") is not None else DEFAULTS[pid], keys)
                clips.append({"name": it.get("subclip_name"), "start": it["start_ticks"] / TPS,
                              "end": it["end_ticks"] / TPS, "in": it.get("src_in_ticks", 0) / TPS,
                              "out": (it.get("src_out_ticks") or 0) / TPS, "speed": it.get("speed", 1.0),
                              "params": params})
            out[tr["name"] or tr["label"]] = clips
    return out


def side_align(where):
    """The text alignment that goes with a grid position: the export sets it this way (TTML textAlign)."""
    return "left" if where.endswith("left") else "right" if where.endswith("right") else "centre"


def line_meta(n):
    """A plan line's cache meta, with the word times it was built with (R227)."""
    from pipeline.narration import timing
    return timing.of(n)


def plan_parts(n):
    """A plan line's audio pieces on the timeline: [{at, in, out}] (one piece unless the planner split it)."""
    return n.get("parts") or [{"at": n["start"], "in": 0.0, "out": n.get("audio_s", n["length"])}]


def at_offset(parts, o, starts="at", ins="in", outs="out", tol=0.0):
    """Timeline time of audio offset o in a line laid out as parts (past the end: carried on from the last part).
    tol: an offset within tol of a part's start belongs to that part (the export rounds in points to frames)."""
    near = [p for p in parts if abs(p[ins] - o) <= tol]
    if near:
        return near[-1][starts] + o - near[-1][ins]
    for p in parts:
        if p[ins] - 1e-6 <= o < p[outs] - 1e-6:
            return p[starts] + o - p[ins]
    p = parts[-1] if o >= parts[-1][ins] else parts[0]
    return p[starts] + o - p[ins]


# ------------------------------------------------------------------------------------------------- the read-back
class Readback:
    def __init__(self, run_dir, prproj=None):
        self.run = Path(run_dir).resolve()
        if prproj is None:                        # the newest saved project in any export round that holds the edit
            saves = sorted((p for d in self.run.glob("premiere*") for p in d.glob("*.prproj")),
                           key=lambda p: p.stat().st_mtime)
            if not saves:
                raise SystemExit(f"no .prproj in {self.run}/premiere*: David saves the project in the export folder (R61)")
            empty = []
            for cand in reversed(saves):
                snap = cand.parent / "edit_plan.json"
                rid = json.loads((snap if snap.exists() else self.run / "edit_plan.json")
                                 .read_text(encoding="utf-8"))["run_id"]
                try:
                    Project(cand).parse_sequence(f"{rid} camera")
                    prproj = cand
                    break
                except KeyError:
                    empty.append(cand.name)
            if prproj is None:
                raise SystemExit(f"no saved project holds the sequence '<run> camera': {empty}")
            if empty:
                print(f"skipped {len(empty)} project(s) without the edit's sequence (an empty save?): {empty}")
        pdir = self.pdir = Path(prproj).resolve().parent
        snap = pdir / "edit_plan.json"
        self.plan = json.loads((snap if snap.exists() else self.run / "edit_plan.json").read_text(encoding="utf-8"))
        self.plan_file = snap if snap.exists() else self.run / "edit_plan.json"
        self.fps = self.plan["fps"]
        self.frame = 1 / self.fps
        rid = self.plan["run_id"]
        self.prproj = Path(prproj)
        proj = Project(self.prproj)
        self.top = proj.parse_sequence(f"{rid} camera", _depth=99)
        self.nest = proj.parse_sequence(f"{rid} source", _depth=99)
        x = ET.parse(pdir / f"{rid}.xml").getroot().find("sequence")
        self.x_top, x_nest = xml_tracks(x, self.fps)
        self.x_nest, _ = xml_tracks(x_nest, self.fps)
        self.h_top, self.h_nest = prproj_tracks(self.top), prproj_tracks(self.nest)
        ex = next((d for d in EXERCISES.iterdir() if (d / self.plan.get("steps_file", "-")).exists()), None)
        # "implies" compares with the settings as they are now; the plan's copy is what the export was made with
        self.current = (json.loads((ex / "edit_settings.json").read_text(encoding="utf-8")) if ex
                        else self.plan["settings"])
        self.lines = {n["line_id"]: n for n in self.plan["narration"]}
        self.meta = {n["line_id"]: line_meta(n) for n in self.plan["narration"]}
        steps = json.loads((ex / self.plan["steps_file"]).read_text(encoding="utf-8"))["steps"] if ex else []
        self.part = {s["id"]: s.get("part") for s in steps}
        self.report = {"project": str(self.prproj), "plan": str(self.plan_file),
                       "length": {"plan_s": round(self.plan["duration_s"], 3),
                                  "his_s": round(self.top["duration_ticks"] / TPS, 3)}}
        self.implies = []

    # -- the camera sequence's pieces of the nest
    def pieces(self):
        nest_name = f"{self.plan['run_id']} source"
        v1 = next(clips for clips in self.h_top.values() if clips and clips[0]["name"] == nest_name)
        return sorted(v1, key=lambda c: c["start"])

    def his_to_plan(self, t):
        ps = self.pieces()
        for p in ps:
            if p["start"] - 1e-6 <= t < p["end"] - 1e-6:
                return p["in"] + (t - p["start"]) * p.get("speed", 1.0)
        p = ps[-1] if t >= ps[-1]["start"] else ps[0]
        return p["in"] + (t - p["start"])

    def picture(self):
        ps, ev, act = self.pieces(), [], None
        self.events = ev
        for a, b in zip(ps, ps[1:]):
            a_out = a["in"] + (a["end"] - a["start"]) * a.get("speed", 1.0)
            d = b["in"] - a_out
            if b["start"] - a["end"] > self.frame / 2:
                ev.append({"kind": "black", "his": a["end"], "s": b["start"] - a["end"]})
            if abs(d) < self.frame / 2:
                continue                                          # a razor cut with nothing removed
            ev.append({"kind": "cut" if d > 0 else "replay", "his": round(b["start"], 4), "s": round(abs(d), 4),
                       "plan_from": round(min(a_out, b["in"]), 4), "plan_to": round(max(a_out, b["in"]), 4)})
        for p in ps:
            if abs(p.get("speed", 1.0) - 1) > 1e-3:
                ev.append({"kind": "speed", "his": p["start"], "speed": p["speed"]})
        # what the picture did in footage he cut (R25: a cut gap had nothing worth watching)
        try:
            act = activity.load(self.run, self.plan["video"])
        except Exception as e:                                    # the recording may be gone; the rest still works
            self.report["activity_error"] = str(e)
        for e in ev:
            if e["kind"] == "cut" and act is not None:
                src = [self.plan_to_src(t) for t in (e["plan_from"], e["plan_to"])]
                e["src"] = [round(s, 3) for s in src]
                e["picture_change_pct"] = round(activity.peak(act, self.fps, *src), 3)
        self.report["pieces"] = [{"his": [round(p["start"], 4), round(p["end"], 4)], "plan_in": round(p["in"], 4)}
                                 for p in ps]
        self.report["picture"] = ev
        return ev

    def plan_to_src(self, t):
        seg = self.plan["segments"][0]
        for s in self.plan["segments"]:
            if s["t"] <= t:
                seg = s
        return seg["src_t"] if seg["type"] == "hold" else seg["src_in"] + (t - seg["t"]) * seg["speed"]

    # -- narration
    def narration(self, events):
        items = sorted(self.h_top.get("Narration", []), key=lambda c: c["start"])
        out = {"items": [], "boundaries": [], "missing": sorted(set(self.lines) - {c["name"] for c in items})}
        for c in items:
            n = self.lines.get(c["name"])
            if n is None:
                out["items"].append({"line": c["name"], "note": "not in the plan"})
                continue
            expect = at_offset(plan_parts(n), c["in"], tol=1.5 * self.frame)
            drift = self.his_to_plan(c["start"]) - expect
            out["items"].append({"line": c["name"], "his": [round(c["start"], 4), round(c["end"], 4)],
                                 "in": round(c["in"], 4), "out": round(c["out"], 4),
                                 "plan_at": round(expect, 4), "drift_s": round(drift, 4)})
        used = set()
        for a, b in zip(items, items[1:]):
            na, nb = self.lines.get(a["name"]), self.lines.get(b["name"])
            if not na or not nb:
                continue
            ma, mb = self.meta[a["name"]], self.meta[b["name"]]
            gap = b["start"] - a["end"]
            near = [e for e in events if a["end"] - 0.5 - 1e-6 <= e["his"] <= b["start"] + 0.05 + 1e-6]
            used.update(id(e) for e in near)
            bd = {"his": round(a["end"], 4), "between": [a["name"], b["name"]], "picture": near}
            if a["name"] == b["name"] and abs(a["out"] - b["in"]) < self.frame:
                o = a["out"]
                left, right = sentences.word_at(ma["display_text"], ma["words"], o)
                brk = next((k for k in sentences.breaks(ma["display_text"], ma["words"])
                            if abs(k["at_s"] - o) <= k["pause_s"] / 2 + 0.1), None)
                pp = plan_parts(na)                      # a beat the plan already had at this split
                plan_beat = sum(b["at"] - (a["at"] + a["out"] - a["in"]) for a, b in zip(pp, pp[1:])
                                if abs(a["out"] - o) <= 1.5 * self.frame)
                bd.update({"kind": "beat", "added_s": round(gap - plan_beat, 4), "plan_beat_s": round(plan_beat, 4),
                           "at_audio_s": round(o, 4), "words": [left, right],
                           "pause_in_voice_s": brk["pause_s"] if brk else None,
                           "modes": [brk["before_mode"], brk["after_mode"]] if brk else None})
            else:
                plan_end = at_offset(plan_parts(na), plan_parts(na)[-1]["out"])
                plan_gap = nb["start"] - plan_end
                la, fb_ = ma["words"][-1]["end"], mb["words"][0]["start"]
                speech = (b["start"] + fb_ - b["in"]) - (a["end"] - (a["out"] - la))
                plan_speech = (nb["start"] + fb_) - (plan_end - (plan_parts(na)[-1]["out"] - la))
                bd.update({"kind": "gap", "plan_gap_s": round(plan_gap, 4), "his_gap_s": round(gap, 4),
                           "parts": [self.part.get(na["step"]), self.part.get(nb["step"])],
                           "plan_speech_gap_s": round(plan_speech, 4), "his_speech_gap_s": round(speech, 4),
                           "tail_trim_s": round(ma["length_s"] - a["out"], 4) if a["out"] < ma["length_s"] - self.frame
                           else 0.0, "head_trim_s": round(b["in"], 4) if b["in"] > self.frame else 0.0,
                           "ends_with": ma["display_text"].rstrip()[-1:],
                           "words": [ma["display_text"].rstrip()[-40:], mb["display_text"][:40]]})
            out["boundaries"].append(bd)
        out["picture_only"] = [e for e in events if id(e) not in used]
        self.report["narration"] = out
        return out

    # -- clips and keyframes on every other track
    def clips(self):
        out = []
        nest_name = f"{self.plan['run_id']} source"
        x_v1s = next(c for c in self.x_top.values() if c and c[0]["name"] == nest_name)   # one piece, or one per
        for p in self.pieces():                                                         # R83 transition
            t = self.his_to_plan(p["start"])
            x_v1 = next((x for x in x_v1s if x["start"] - self.frame <= t < x["end"]), x_v1s[0])
            d = self.param_diff(x_v1, p, x_v1["start"], t)
            if d:
                out.append({"track": "camera V1 (the nest)", "clip": f"piece at his {p['start']:.2f}", "keys": d})
                break
        for where, xt, ht, to_plan in (("camera", self.x_top, self.h_top, self.his_to_plan),
                                       ("source", self.x_nest, self.h_nest, lambda t: t)):
            for name in list(xt) + [n for n in ht if n not in xt]:
                if name in ("Narration",) or (xt.get(name) and xt[name][0]["name"] == nest_name):
                    continue
                xs, hs = xt.get(name, []), ht.get(name, [])
                if not xs and not hs:
                    continue
                if not hs:
                    out.append({"track": f"{where} {name}", "change": f"track removed or emptied ({len(xs)} clips)"})
                    continue
                pairs, rest = self.match(xs, hs)
                for c in rest["removed"]:
                    out.append({"track": f"{where} {name}", "clip": c["name"], "change": f"deleted (was {c['start']:.2f}-{c['end']:.2f})"})
                for c in rest["added"]:
                    out.append({"track": f"{where} {name}", "clip": c["name"],
                                "change": f"added at {to_plan(c['start']):.2f}-{to_plan(c['end'] - 1e-4):.2f}"})
                unchanged = 0
                for xc, hc in pairs:
                    ps, pe = to_plan(hc["start"]), to_plan(hc["end"] - 1e-4) + 1e-4
                    ch = []
                    inside = [e for e in self.events if where == "camera" and hc["start"] < e["his"] < hc["end"]
                              and e["kind"] in ("cut", "replay")]
                    same_len = abs((hc["end"] - hc["start"]) - (xc["end"] - xc["start"])) <= self.frame
                    if abs(ps - xc["start"]) > self.frame:
                        ch.append(f"moved {xc['start']:.2f} -> {ps:.2f}")
                    if same_len and inside and abs(ps - xc["start"]) <= self.frame:
                        ch.append(f"same length on his timeline, so the {' and '.join(e['kind'] for e in inside)} "
                                  f"inside it ends it at {pe:.2f} against the picture (was {xc['end']:.2f})")
                    elif abs(pe - xc["end"]) > self.frame:
                        ch.append(f"ends {xc['end']:.2f} -> {pe:.2f}")
                    if abs(hc["in"] - xc["in"]) > self.frame:
                        ch.append(f"in point {hc['in'] - xc['in']:+.2f}s")
                    keys = self.param_diff(xc, hc, xc["start"], ps)
                    if ch or keys:
                        op = hc["params"].get("opacity", _keys(100.0, []))
                        fade = self.moves("opacity", [(round(ps + t - hc["in"], 3), v) for t, v in op["keys"]])
                        out.append({"track": f"{where} {name}", "clip": xc["name"], "change": "; ".join(ch),
                                    "keys": keys, "fades": fade})
                    else:
                        unchanged += 1
                if unchanged:
                    out.append({"track": f"{where} {name}", "change": f"{unchanged} clip(s) unchanged", "quiet": True})
        self.report["clips"] = out
        return out

    # -- transitions (R83, R34): his, against the export's; Premiere keeps them apart from the clips (GOTCHAS)
    def transitions(self):
        ours = [dict(t, plan_t=round(t["t"], 4)) for t in self.plan.get("transitions") or []]
        out = {"his": [], "removed": []}
        for where, seq, to_plan in (("camera", self.top, self.his_to_plan), ("source", self.nest, lambda t: t)):
            for tr in seq["video_tracks"]:
                for t in tr["transitions"]:
                    s0, s1 = t["start_ticks"] / TPS, t["end_ticks"] / TPS
                    cut = s0 + t["alignment_ticks"] / TPS
                    p = to_plan(cut)
                    lid = next((n["line_id"] for n in self.plan["narration"]
                                if n["start"] - 2 <= p <= n["start"] + 0.5), None)
                    ours_here = next((o for o in ours if abs(o["plan_t"] - p) <= 0.2), None)
                    if ours_here:
                        ours.remove(ours_here)
                    out["his"].append({"where": f"{where} {tr['label']}", "type": t["type"], "match_name": t["match_name"],
                                       "his": [round(s0, 4), round(s1, 4)], "duration_s": round(s1 - s0, 4),
                                       "starts_at_cut": abs(t["alignment_ticks"]) < TPS / self.fps,
                                       "plan_t": round(p, 4), "before_line": lid, "ours": bool(ours_here)})
        out["removed"] = ours
        self.report["transitions"] = out
        return out

    # -- a re-timed overlay: when each item appears on his cut (he can only cut and repeat a rendered card)
    def overlay_timing(self):
        out = []
        for o in self.plan.get("overlays") or []:
            pieces = sorted((c for clips in self.h_top.values() for c in clips if c["name"] == f"overlay {o['id']}"),
                            key=lambda c: c["start"])
            if len(pieces) < 2:
                continue
            for k, it in enumerate(o.get("items") or []):
                off = it["at"] - o["t0"]
                his = next((c["start"] + max(0.0, off - c["in"]) for c in pieces
                            if c["in"] + (c["end"] - c["start"]) >= off), None)
                if his is None or abs(self.his_to_plan(his) - it["at"]) <= 1.5 * self.frame:
                    continue
                out.append({"overlay": o["id"], "item": k + 1, "text": it["text"], "plan_at": it["at"],
                            "plan_word": self.word_near(it["at"]), "his": round(his, 4),
                            "his_word": self.word_near(self.his_to_plan(his))})
        self.report["overlay_timing"] = out
        return out

    def word_near(self, t):
        """The narration word spoken at plan time t (or the next one), for reports."""
        n = max((n for n in self.plan["narration"] if n["start"] <= t + 1e-6), key=lambda n: n["start"], default=None)
        if n is None:
            return None
        o = next((p["in"] + t - p["at"] for p in reversed(plan_parts(n)) if p["at"] <= t + 1e-6), t - n["start"])
        w = next((w for w in reversed(self.meta[n["line_id"]]["words"]) if w["start"] <= o + 0.05), None)
        return w["word"] if w else None

    @staticmethod
    def match(xs, hs):
        sm = difflib.SequenceMatcher(a=[c["name"] for c in xs], b=[c["name"] for c in hs], autojunk=False)
        pairs, removed, added = [], [], []
        for op, a0, a1, b0, b1 in sm.get_opcodes():
            if op == "equal" or (op == "replace" and a1 - a0 == b1 - b0):
                pairs += list(zip(xs[a0:a1], hs[b0:b1]))
            else:
                removed += xs[a0:a1]
                added += hs[b0:b1]
        return pairs, {"removed": removed, "added": added}

    def param_diff(self, xc, hc, x_start, h_start):
        out = {}
        for pid in DEFAULTS:
            xp = xc["params"].get(pid, _keys(DEFAULTS[pid], []))
            hp = hc["params"].get(pid, _keys(DEFAULTS[pid], []))
            xk = xp["keys"] or [(None, xp["static"])]
            hk = hp["keys"] or [(None, hp["static"])]
            if self.same(pid, xk, hk):
                continue
            to_plan_x = lambda k: None if k[0] is None else round(x_start + k[0] - xc["in"], 3)
            to_plan_h = lambda k: None if k[0] is None else round(h_start + k[0] - hc["in"], 3)
            fmt_v = lambda v: (f"({v[0]:.3f}, {v[1]:.3f})" if isinstance(v, tuple) else f"{v:g}")
            out[pid] = {"was": [(to_plan_x(k), fmt_v(k[1])) for k in xk], "now": [(to_plan_h(k), fmt_v(k[1])) for k in hk],
                        "moves_was": self.moves(pid, [(to_plan_x(k), k[1]) for k in xk]),
                        "moves_now": self.moves(pid, [(to_plan_h(k), k[1]) for k in hk])}
        return out

    def same(self, pid, a, b):
        if len(a) != len(b):
            return False
        for (ta, va), (tb, vb) in zip(a, b):
            if (ta is None) != (tb is None) or (ta is not None and abs(ta - tb) > 1.5 * self.frame):
                return False
            va, vb = (va, vb) if isinstance(va, tuple) else ((va,), (vb,))
            if any(abs(p - q) > PARAM_TOL[pid] for p, q in zip(va, vb)):
                return False
        return True

    @staticmethod
    def moves(pid, keys):
        """Spans over which the value changes: [(t0, t1)], merged when they touch."""
        spans = []
        for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
            vv0, vv1 = (v0, v1) if isinstance(v0, tuple) else ((v0,), (v1,))
            if t0 is not None and any(abs(p - q) > PARAM_TOL[pid] for p, q in zip(vv0, vv1)):
                if spans and abs(spans[-1][1] - t0) < 1e-3:
                    spans[-1] = (spans[-1][0], t1)
                else:
                    spans.append((t0, t1))
        return spans

    # -- captions
    def captions(self):
        tracks = [ct for ct in self.top.get("caption_tracks", []) if ct["cues"]]
        his = [c for ct in tracks for c in ct["cues"] if c.get("caption")]
        plan_cues = self.plan["captions"]["cues"]
        style = self.plan["captions"].get("style", {})
        norm = lambda s: " ".join(s.split())
        out = {"tracks": len(tracks), "cues": [], "unmatched_his": [], "unmatched_plan": []}
        if not his:
            self.report["captions"] = out
            return out
        left = list(range(len(plan_cues)))
        for h in his:
            txt = norm(h["caption"]["text"])
            if not txt:                                           # the export's one-frame anchor cue at 0:00
                out["anchor_left_at"] = h["start_s"]
                continue
            k = next((i for i in left if norm(plan_cues[i]["text"]) == txt), None)
            edited = False
            if k is None:
                scored = [(difflib.SequenceMatcher(None, norm(plan_cues[i]["text"]), txt).ratio(), i) for i in left]
                if scored and max(scored)[0] > 0.6:
                    k, edited = max(scored)[1], True
            if k is None:
                out["unmatched_his"].append({"his": h["start_s"], "text": txt})
                continue
            left.remove(k)
            pc = plan_cues[k]
            exp0, exp1 = self.cue_on_his(pc["start"]), self.cue_on_his(pc["end"])
            cap = h["caption"]
            out["cues"].append({
                "text": txt, "edited_from": norm(pc["text"]) if edited else None,
                "his": [h["start_s"], h["end_s"]], "words_at_his": [round(exp0, 4), round(exp1, 4)],
                "lead_s": round(exp0 - h["start_s"], 4), "end_lead_s": round(exp1 - h["end_s"], 4),
                "plan_lines": pc["text"].split("\n"), "his_lines": [l.rstrip() for l in cap["lines"]],
                "plan_where": (pc.get("pos") or {}).get("where", "bottom-centre"), "his_where": cap["grid"],
                "align": cap["align"],
                "style": {"font_size": cap["font_size"], "box": cap["box_hex"] if cap["box_on"] else None,
                          "box_opacity": cap["box_opacity"], "corner_radius": cap["corner_radius"]}})
        out["unmatched_plan"] = [{"start": plan_cues[i]["start"], "text": plan_cues[i]["text"]} for i in left]
        out["cues"].sort(key=lambda c: c["his"][0])
        runs = []                                                 # consecutive cues that lead their words alike
        for c in out["cues"]:
            if runs and abs(c["lead_s"] - runs[-1]["leads"][-1]) <= 0.1:
                runs[-1]["leads"].append(c["lead_s"])
                runs[-1]["his"][1] = c["his"][1]
            else:
                runs.append({"his": list(c["his"]), "leads": [c["lead_s"]], "first": c["text"]})
        out["runs"] = [{"his": r["his"], "cues": len(r["leads"]), "first": r["first"],
                        "lead_s": round(statistics.median(r["leads"]), 3)} for r in runs]
        leads = [c["lead_s"] for c in out["cues"]]
        out["check"] = {"cues": len(out["cues"]),
                        "on_time": sum(abs(c["lead_s"]) <= 1.5 * self.frame for c in out["cues"]),
                        "in_place": sum(c["his_where"] == c["plan_where"] for c in out["cues"]),
                        "off_centre_planned": sum(c["plan_where"] != "bottom-centre" for c in out["cues"])}
        out["offset_s"] = round(statistics.median(leads), 4) if leads else 0.0
        first = min((c for c in out["cues"]), key=lambda c: c["his"][0], default=None)
        out["first_cue_at_his"] = first["his"][0] if first else None
        out["first_cue_plan"] = plan_cues[0]["start"] if plan_cues else None
        styles = Counter(json.dumps(c["style"], sort_keys=True) for c in out["cues"])
        out["style"] = json.loads(styles.most_common(1)[0][0])
        out["style_exceptions"] = [c["text"][:40] for c in out["cues"] if json.dumps(c["style"], sort_keys=True)
                                   != styles.most_common(1)[0][0]]
        out["plan_style"] = style
        self.report["captions"] = out
        return out

    def cue_on_his(self, t):
        """Where plan time t (inside a line, or its linger) lands on his timeline, following that line's words."""
        n = max((n for n in self.plan["narration"] if n["start"] <= t + 1e-6), key=lambda n: n["start"], default=None)
        if n is None:
            return t
        parts = plan_parts(n)
        o = next((p["in"] + t - p["at"] for p in reversed(parts) if p["at"] <= t + 1e-6), t - n["start"])
        mine = sorted((c for c in self.h_top.get("Narration", []) if c["name"] == n["line_id"]), key=lambda c: c["in"])
        if not mine:
            return t
        return at_offset([{"at": c["start"], "in": c["in"], "out": c["out"]} for c in mine], o)

    # -- R60: the setting or rule each change implies
    def imply(self, nar, cl, caps):
        cur, pace, cs = self.current, self.current["pacing"], self.current["captions"]
        add = lambda rule, text, setting=None, now=None: self.implies.append(
            {"rule": rule, "text": text, "setting": setting, "now": now})
        mode_beats = []
        for bd in nar["boundaries"]:
            if bd["kind"] == "gap" and abs(bd["his_gap_s"] - bd["plan_gap_s"]) > 1.5 * self.frame:
                cut = [e for e in bd["picture"] if e["kind"] == "cut"]
                still = all(e.get("picture_change_pct", 1) < pace.get("activity_min_pct", 0.5) for e in cut)
                why = (f"; the {sum(e['s'] for e in cut):.2f} s of footage he cut changes at most "
                       f"{max(e.get('picture_change_pct', 0) for e in cut):.2f}% of the frame") if cut else ""
                if bd["his_gap_s"] <= 1.5 * self.frame and bd["ends_with"] == ",":
                    add("R25", f"comma run-on {bd['between'][0]} -> {bd['between'][1]}: {bd['plan_gap_s']:.2f} s -> "
                               f"run straight on, {bd['his_speech_gap_s']:.2f} s between the words{why}",
                        "pacing.comma_pause_s", pace.get("comma_pause_s"))
                elif bd.get("parts") and bd["parts"][0] != bd["parts"][1]:   # the gap held the part pause: name it
                    add("R82", f"gap {bd['between'][0]} -> {bd['between'][1]} (Part {bd['parts'][0]} -> "
                               f"{bd['parts'][1]}): {bd['plan_gap_s']:.2f} s -> {bd['his_gap_s']:.2f} s, so the part "
                               f"pause would be {bd['his_gap_s'] - pace.get('gap_between_lines', 0.4):.2f} s{why}"
                               + (" (no picture change: dead air)" if cut and still else ""),
                        "pacing.pause_at_part_boundary", pace.get("pause_at_part_boundary"))
                else:
                    add("R25", f"gap {bd['between'][0]} -> {bd['between'][1]}: {bd['plan_gap_s']:.2f} s -> "
                               f"{bd['his_gap_s']:.2f} s{why}" + (" (no picture change: dead air)" if cut and still else ""),
                        "pacing.gap_between_lines", pace.get("gap_between_lines"))
            if bd["kind"] == "beat" and bd["added_s"] > 1.5 * self.frame:
                m = bd["modes"]
                switch = m and m[0] != m[1]
                mode_beats.append(bd)
                add("R62" if switch else "R62?",
                    f"beat +{bd['added_s']:.2f} s in {bd['between'][0]} at \"{bd['words'][0]} | {bd['words'][1]}\""
                    + (f" ({m[0]} -> {m[1]})" if m else " (not at a sentence break)")
                    + (f"; the voice's own pause there is {bd['pause_in_voice_s']:.2f} s" if bd["pause_in_voice_s"] else ""),
                    "pacing.mode_switch_beat_s", pace.get("mode_switch_beat_s"))
        # R62 cross-check: mode switches in the lines he played where he did not add a beat
        beat_at = {(b["between"][0], round(b["at_audio_s"], 1)) for b in mode_beats}
        missed = []
        for lid, m in self.meta.items():
            for k in sentences.breaks(m["display_text"], m["words"]):
                if k["before_mode"] != k["after_mode"] and not any(
                        lid == b[0] and abs(b[1] - k["at_s"]) <= k["pause_s"] / 2 + 0.1 for b in beat_at):
                    missed.append(f"{lid} \"{' '.join(k['before_text'].split()[-5:])} | "
                                  f"{' '.join(k['after_text'].split()[:5])}\" "
                                  f"({k['before_mode']} -> {k['after_mode']})")
        if missed and mode_beats:
            add("R62", f"{len(missed)} explain/instruct switch(es) where he added no beat: " + "; ".join(missed),
                "pacing.mode_switch_beat_s", pace.get("mode_switch_beat_s"))
        for c in cl:
            later, end = [], 0.0
            for pid, k in (c.get("keys") or {}).items():
                end_was = max((m[1] for m in k["moves_was"]), default=None)
                end_now = max((m[1] for m in k["moves_now"]), default=None)
                if pid != "opacity" and end_was is not None and end_now is not None and end_now > end_was + self.frame:
                    later.append(f"{pid} until {end_now:.2f} (was {end_was:.2f})")
                    end = max(end, end_now)
            if later:
                fade = c.get("fades") or []
                into = bool(fade) and end > fade[-1][0]
                add("R63", f"{c['clip']} keeps moving longer: {', '.join(later)}"
                           + (f"; its fade-out is {fade[-1][0]:.2f}-{fade[-1][1]:.2f}, so it is still moving as it fades"
                              if into else ""))
        if caps.get("cues"):
            st, plan_st = caps["style"], self.current["captions"]
            pairs = [("font size", st["font_size"], plan_st.get("size_px"), "captions.size_px", 0.5),
                     ("box colour", st["box"], plan_st.get("box_color"), "captions.box_color", None),
                     ("box opacity %", st["box_opacity"], round(plan_st.get("box_opacity", 1) * 100, 1),
                      "captions.box_opacity (x100)", 0.5),
                     ("corner radius", st["corner_radius"], plan_st.get("corner_radius_px"), "captions.corner_radius_px", 0.5)]
            for label, his_v, set_v, setting, tol in pairs:
                same = (his_v == set_v) if tol is None else (his_v is not None and set_v is not None and abs(his_v - set_v) <= tol)
                add("R52", f"caption {label}: his {his_v} vs setting {set_v}" + (" (matches)" if same else ""),
                    setting, set_v)
            k = caps["check"]
            add("R54", f"caption timing: {k['on_time']} of {k['cues']} cues start within a frame of their words"
                       + ("" if k["on_time"] == k["cues"] else " (see Timing above)"))
            add("R53", f"caption position: {k['in_place']} of {k['cues']} cues where the planner put them "
                       f"({k['off_centre_planned']} planned off bottom-centre)")
            if caps.get("anchor_left_at") is not None:
                add("R61", f"the one-frame anchor cue is still on the timeline at his {caps['anchor_left_at']:.2f} s: "
                           "delete it")
            if abs(caps["runs"][0]["lead_s"]) > 1.5 * self.frame:
                why = ""
                if caps["first_cue_at_his"] is not None and abs(caps["first_cue_at_his"]) < self.frame and \
                        abs(caps["runs"][0]["lead_s"] - caps["first_cue_plan"]) < 3 * self.frame:
                    why = (f": his first cue sits at 0:00 although its words start at {caps['first_cue_plan']:.2f} s, "
                           "so the SRT went in at the playhead with its first cue there (an import offset, not an edit)")
                add("R61", f"captions run {caps['runs'][0]['lead_s']:.2f} s ahead of their words{why}")
            for run in caps["runs"][1:]:
                add("R54?", f"from his {run['his'][0]:.2f} s ({run['cues']} cues, \"{run['first'][:28]}\" on) captions "
                            f"start {run['lead_s']:.2f} s before their words, not {caps['runs'][0]['lead_s']:.2f} s: "
                            "re-placed by hand (snapped to the narration clips?)")
            for c in caps["cues"]:
                if c["his_lines"] != c["plan_lines"]:
                    off = c["his_where"] != "bottom-centre"
                    add("R59" if off else "R59?",
                        f"cue \"{c['text'][:32]}\" rewrapped {len(c['plan_lines'])} lines "
                        f"({', '.join(str(len(l)) for l in c['plan_lines'])}) -> {len(c['his_lines'])} lines "
                        f"({', '.join(str(len(l)) for l in c['his_lines'])} chars)" + (f" at {c['his_where']}" if off else ""),
                        "captions.off_centre_max_chars" if off else "captions.max_chars",
                        cs.get("off_centre_max_chars") if off else cs.get("max_chars"))
                if c["his_where"] != c["plan_where"] or c["his_where"] != "bottom-centre":
                    if c["his_where"] == c["plan_where"]:
                        add("R53", f"cue \"{c['text'][:32]}\" at {c['his_where']}: where the planner put it (the SRT "
                                   "lost it; he put it back)")
                    elif c["his_where"] == "bottom-centre":
                        pass                                       # SRT puts every cue there; not his choice
                    else:
                        add("R53", f"cue \"{c['text'][:32]}\" moved to {c['his_where']} (planner: {c['plan_where']})")
                if c["align"] != side_align(c["his_where"]):
                    add("R59?", f"cue \"{c['text'][:32]}\" text aligned {c['align']} at {c['his_where']}",
                        "captions.align_off_centre", cs.get("align_off_centre"))
        self.report["implies"] = self.implies

    def run_all(self):
        ev = self.picture()
        nar = self.narration(ev)
        cl = self.clips()
        caps = self.captions()
        trs, ovt = self.transitions(), self.overlay_timing()
        job_p = self.pdir / "caption_titles.json"
        if job_p.exists():                    # R102: his edits to the editable titles, each one a lesson (R60)
            from pipeline.edit.ppro.titles import readback as titles_readback
            self.report["caption_titles"] = titles_readback(Project(self.prproj),
                                                            json.loads(job_p.read_text(encoding="utf-8")))
            for c in self.report["caption_titles"]:
                if c["change"] in ("rewrapped", "reworded", "moved", "moved (Motion)"):
                    self.implies.append({"rule": "R102", "text": f"title {c['change']}: \"{c['text'][:40]}\"",
                                         "setting": {"rewrapped": "captions.max_chars", "moved": None}.get(c["change"]),
                                         "now": self.current["captions"].get("max_chars")
                                         if c["change"] == "rewrapped" else None})
        self.imply(nar, cl, caps)
        for t in trs["his"]:
            if not t["ours"]:
                self.implies.append({"rule": "R83", "text": f"{t['type']} added, {t['duration_s']:.2f} s at his "
                                     f"{t['his'][0]:.2f} (plan {t['plan_t']:.2f}, before {t['before_line']})",
                                     "setting": "cuts.work_cut_transition",
                                     "now": (self.current["cuts"].get("work_cut_transition") or {}).get("type")})
        for t in trs["removed"]:
            self.implies.append({"rule": "R83?", "text": f"our {t['type']} at plan {t['plan_t']:.2f} is gone",
                                 "setting": "cuts.work_cut_transition", "now": None})
        for v in ovt:
            self.implies.append({"rule": "R80", "text": f"overlay {v['overlay']} item {v['item']} \"{v['text'][:40]}\" "
                                 f"now appears on \"{v['his_word']}\" (plan: on \"{v['plan_word']}\")",
                                 "setting": None, "now": None})
        return self.report


# ------------------------------------------------------------------------------------------------- report text
def text_report(r, plan_name):
    out = []
    p = out.append
    L = r["length"]
    p(f"Read-back of {Path(r['project']).name} against {plan_name}")
    p(f"Length: plan {L['plan_s']:.2f} s -> his {L['his_s']:.2f} s ({L['his_s'] - L['plan_s']:+.2f} s)")
    nar = r["narration"]
    p("")
    p("1. Cuts and beats (his camera sequence; times his / plan)")
    for bd in nar["boundaries"]:
        pic = "; ".join(f"{e['kind']} {e['s']:.2f} s of picture (plan {e['plan_from']:.2f}-{e['plan_to']:.2f}"
                        + (f", picture change {e['picture_change_pct']:.2f}%" if "picture_change_pct" in e else "") + ")"
                        for e in bd["picture"] if e["kind"] in ("cut", "replay"))
        if bd["kind"] == "beat" and abs(bd["added_s"]) > 0.05:
            p(f"  {bd['his']:6.2f}  beat {bd['added_s']:+.2f} s inside {bd['between'][0]}: \"{bd['words'][0]} | "
              f"{bd['words'][1]}\"" + (f"  [{bd['modes'][0]} -> {bd['modes'][1]}]" if bd["modes"] else ""))
            p(f"          picture: {pic or 'none'}")
        elif bd["kind"] == "gap" and (abs(bd["his_gap_s"] - bd["plan_gap_s"]) > 0.05 or bd["picture"]):
            p(f"  {bd['his']:6.2f}  gap {bd['between'][0]} -> {bd['between'][1]}: {bd['plan_gap_s']:.2f} s -> "
              f"{bd['his_gap_s']:.2f} s (words {bd['plan_speech_gap_s']:.2f} -> {bd['his_speech_gap_s']:.2f} s apart)"
              + (f", {bd['tail_trim_s']:.2f} s of {bd['between'][0]}'s tail trimmed" if bd["tail_trim_s"] else "")
              + (f", {bd['head_trim_s']:.2f} s of {bd['between'][1]}'s head trimmed" if bd["head_trim_s"] else ""))
            p(f"          \"...{bd['words'][0]}\" | \"{bd['words'][1]}...\"")
            p(f"          picture: {pic or 'none'}")
    for e in nar["picture_only"]:
        p(f"  {e['his']:6.2f}  {e['kind']} " + (f"{e['s']:.2f} s" if "s" in e else str(e.get("speed"))) +
          " (no narration boundary there)")
    gaps = [bd for bd in nar["boundaries"] if bd["kind"] == "gap"]
    if gaps:
        p("  Gaps between lines, plan -> his: " + ", ".join(f"{g['plan_gap_s']:.2f}->{g['his_gap_s']:.2f}" for g in gaps))
    drift = [i for i in nar["items"] if abs(i.get("drift_s", 0)) > 1.5 / 30]
    p("  Sync: " + ("every narration piece still sits on its picture (within a frame)" if not drift else
                    "; ".join(f"{i['line']} @{i['his'][0]:.2f} {i['drift_s']:+.2f} s off its picture" for i in drift)))
    if nar["missing"]:
        p(f"  Lines removed: {', '.join(nar['missing'])}")
    p("")
    p("2. Clips and keyframes")
    for c in r["clips"]:
        if c.get("quiet"):
            p(f"  {c['track']}: {c['change']}")
            continue
        p(f"  {c['track']} / {c.get('clip', '')}: {c.get('change') or 'keyframes changed'}")
        if c.get("keys"):
            p("      (key times: clip time counted from the clip's plan start)")
        for pid, k in (c.get("keys") or {}).items():
            fmt = lambda ks: ", ".join(f"{t:.2f}" if t is not None else "static" for t, _ in ks)
            mv = lambda ms: ", ".join(f"{a:.2f}-{b:.2f}" for a, b in ms) or "none"
            p(f"      {pid}: keys {fmt(k['was'])} -> {fmt(k['now'])}; changes over {mv(k['moves_was'])} -> {mv(k['moves_now'])}")
    for v in r.get("overlay_timing", []):
        p(f"  overlay {v['overlay']} item {v['item']} \"{v['text'][:44]}\": plan {v['plan_at']:.2f} on "
          f"\"{v['plan_word']}\" -> his {v['his']:.2f} on \"{v['his_word']}\" (he cut and repeated the card's pieces)")
    trs = r.get("transitions", {})
    for t in trs.get("his", []):
        p(f"  transition {t['type']} ({t['match_name']}) {t['duration_s']:.2f} s at his {t['his'][0]:.2f}-{t['his'][1]:.2f}"
          f" on {t['where']}, {'starting at' if t['starts_at_cut'] else 'around'} the cut at plan {t['plan_t']:.2f}, "
          f"before {t['before_line']}" + (" (ours)" if t["ours"] else " (his)"))
    for t in trs.get("removed", []):
        p(f"  transition {t['type']} at plan {t['plan_t']:.2f}: ours, gone from his project")
    caps = r["captions"]
    p("")
    p(f"3. Captions ({len(caps['cues'])} cues matched"
      + (f", {len(caps['unmatched_his'])} of his unmatched" if caps["unmatched_his"] else "")
      + (f", {len(caps['unmatched_plan'])} of the plan's missing" if caps["unmatched_plan"] else "") + ")")
    if caps["cues"]:
        st = caps["style"]
        p(f"  Style: {st['font_size']:g} px, box {st['box']} at {st['box_opacity']:g}%, corners {st['corner_radius']:g} px"
          + (f"; different on: {', '.join(caps['style_exceptions'])}" if caps["style_exceptions"] else ""))
        for run in caps["runs"]:
            p(f"  Timing: his {run['his'][0]:.2f}-{run['his'][1]:.2f} s, {run['cues']} cues from \"{run['first'][:28]}\": "
              f"start {run['lead_s']:.2f} s before their words")
        for c in caps["cues"]:
            notes = []
            if c["his_lines"] != c["plan_lines"]:
                notes.append(f"wrap {c['plan_lines']} -> {c['his_lines']}")
            if c["his_where"] != "bottom-centre" or c["plan_where"] != "bottom-centre":
                notes.append(f"position {c['his_where']} (planner {c['plan_where']})")
            if c["align"] != side_align(c["his_where"]):
                notes.append(f"aligned {c['align']}")
            if c["edited_from"]:
                notes.append(f"text edited from \"{c['edited_from']}\"")
            if notes:
                p(f"  his {c['his'][0]:6.2f} \"{c['text'][:36]}\": " + "; ".join(notes))
    if "caption_titles" in r:
        t = r["caption_titles"]
        p("")
        p(f"3b. Caption titles (R102): {len(t)} change(s)")
        for c in t:
            p(f"  {c['change']}: \"{c['text'][:40]}\"" + "".join(f"; {k} {c[k]}" for k in ("by", "his", "by_px",
                                                                                          "motion", "at_s") if k in c))
    p("")
    p("4. What each change implies (R60)")
    for i in r["implies"]:
        s = f"  [{i['rule']}] {i['text']}"
        if i["setting"]:
            s += f"  -> {i['setting']} = {i['now']}"
        p(s)
    return "\n".join(out)


def against(rb, plan_path):
    """A re-plan set beside his cut, line by line: the gap before each line and the beats inside it."""
    new = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    his = sorted(rb.h_top.get("Narration", []), key=lambda c: c["start"])
    rows, out = [], []
    for n in new["narration"]:
        mine = [c for c in his if c["name"] == n["line_id"]]
        parts = plan_parts(n)
        ours_beats = [round(b["at"] - (a["at"] + a["out"] - a["in"]), 2) for a, b in zip(parts, parts[1:])]
        his_beats = [round(b["start"] - a["end"], 2) for a, b in zip(mine, mine[1:])]
        rows.append({"line": n["line_id"], "ours_start": n["start"], "ours_end": parts[-1]["at"] + parts[-1]["out"] - parts[-1]["in"],
                     "his_start": mine[0]["start"] if mine else None, "his_end": mine[-1]["end"] if mine else None,
                     "ours_beats": ours_beats, "his_beats": his_beats})
    out.append(f"Re-plan {Path(plan_path).name}: {new['duration_s']:.2f} s; his cut {rb.report['length']['his_s']:.2f} s; "
               f"the exported plan {rb.plan['duration_s']:.2f} s")
    out.append(f"  {'line':12} {'gap before (ours / his)':>24}   beats inside (ours / his)")
    for prev, r in zip([None] + rows, rows):
        g_o = r["ours_start"] - prev["ours_end"] if prev else r["ours_start"]
        g_h = (r["his_start"] - prev["his_end"]) if prev and r["his_start"] is not None and prev["his_end"] is not None \
            else r["his_start"]
        flag = "" if g_h is None or abs(g_o - g_h) <= 0.1 else "  <-"
        bflag = "" if len(r["ours_beats"]) == len(r["his_beats"]) else "  <- beats differ"
        out.append(f"  {r['line']:12} {g_o:10.2f} / {g_h if g_h is None else round(g_h, 2)!s:<8}{flag:4}   "
                   f"{r['ours_beats'] or '-'} / {r['his_beats'] or '-'}{bflag}")
    return "\n".join(out)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    rb = Readback(args[0], args[1] if len(args) > 1 else None)
    r = rb.run_all()
    (rb.pdir / "readback.json").write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
    print(text_report(r, rb.plan_file.relative_to(rb.run).as_posix()))
    other = next((a.split("=", 1)[1] for a in argv if a.startswith("--against=")), None)
    if other:
        print()
        print(against(rb, other))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
