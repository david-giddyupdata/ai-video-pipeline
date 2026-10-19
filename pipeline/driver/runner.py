"""Step runner (SPEC §4, §6.2). Drives one step list in the attached Edge window and logs every event.

Scope so far (S1, S4, S6, S7, Part 5, Quick Sight): navigate, click, hover, type (into the Claude Code panel too; R67;
select_all and submit for a box whose text is replaced), drag, key and none (a line over the picture), switch_tab (a
click on another tab of the take's window), a click in a Windows dialog the page opened (action.os: R112's Open
dialog, through UI Automation), wait_claude and scroll, with
the expectations visible / hidden / url_contains / text_in_frame / claude_idle / none; targets in the page or in the
Claude Code panel's nested webview frames; tab switching when a click opens a new tab; conditional steps (only_if, with
an optional JS test of a tab's page: R70's second feedback round); the boxes of a step's marks, measured once the
step's result has settled and logged as text_box events for the edit; and a page screenshot for steps marked still. The mouse really moves along an eased path, so hover states in the page match the cursor that
the edit draws later; the real Windows pointer never moves.
"""
import json
import math
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import jsonschema

from pipeline.config import SCHEMAS
from pipeline.edit.marks import approach_s, arrow_points
from pipeline.vendor import claude_watch as cw

STEPS_VALIDATOR = jsonschema.Draft202012Validator(
    json.loads((SCHEMAS / "steps.schema.json").read_text(encoding="utf-8")))

PAUSE_BEFORE_CLICK = 0.3          # p in SPEC §6.2
CLICK_AFTER_NAME = 0.35           # click lands this long after the target's name starts (David's median, ep. 02)
DEFAULT_CUE = 0.3                 # c when a line has no cue word (or no narration yet)
VIEWER_TIME = {"click": 1.0, "hover": 1.2, "key": 1.0, "navigate": 1.5, "type": 1.0, "none": 0.0,
               "wait_claude": 3.0, "scroll": 0.0, "switch_tab": 1.0, "drag": 1.0}
TYPE_DELAY_MS = 45                # per character: a quick typist; the edit speeds long prompts up anyway (R67)
OVER_RECORD = 1.0                 # extra footage after viewer time; the edit trims it
NARRATION_PAD = 1.5               # footage past the end of the narration line
LONG_WAIT_S = 3.0                 # a wait longer than this is cut in the edit (cut_above_s, SPEC §6.4)

# What a take can run today. Each slice that builds a piece removes it here; missing() reads this table.
NOT_BUILT = {
    "action:approve_prompt": "wait_claude approves prompts itself",
    "action:wait": "when needed",
    "expect:new_tab": "when needed",
    "highlights": "draw a rect mark on the text instead",
    "locator:todo": "when built (a generated step: the exploration writes it, pipeline.generated.merge)",
}
CLAUDE_POLL_S = 0.5               # the panel's state (permission prompts are answered within a second)
LOG_POLL_S = 5.0                  # Claude's session log over gh (a call takes 2 to 5 s)
IDLE_CONFIRM_S = 2.0              # the panel must stay idle this long
IDLE_NO_LOG_S = 10.0              # idle this long with no readable log also counts as done
SCROLL_HOLD_S = 2.0               # a reply scroll holds still before and after it moves
SMOOTH_SCROLL_MS = 600            # target.scroll smooth: the panel's eased scroll to a target
READ_PX_S = 30.0                  # reading pace of a reply scroll (CSS px a second); the edit may speed it up
TODO_LOCATOR = "TODO"             # a locator starting with this is a placeholder, confirmed when the step is built


def missing(step):
    """The capabilities this step needs that aren't built yet: [(need, slice that builds it)]. Empty: it can run."""
    a, e, nar = step["action"], step["expect"], step["narration"]
    needs = []
    kind = a["type"]
    if kind == "type":
        kind = "paste" if a.get("typing_mode") == "paste" else "type"
    needs.append(f"action:{kind}")
    needs.append(f"expect:{e['kind']}")
    targets = [a.get("target") or {}, e, *(m["target"] for m in step.get("marks", []))]
    needs += [f"frame:{t['frame']}" for t in targets if t.get("frame")]
    needs += [f"tab:{t['tab']}" for t in targets if t.get("tab")]
    locators = [a.get("target", {}).get("locator", ""), e.get("locator", ""),
                step.get("only_if", {}).get("locator", ""),
                *(m["target"].get("locator", "") for m in step.get("marks", []))]
    if any(loc.startswith(TODO_LOCATOR) for loc in locators):
        needs.append("locator:todo")
    if step.get("highlights"):
        needs.append("highlights")
    if step.get("timelapse"):
        needs.append("timelapse")
    if nar["status"] == "pending_post_run":
        needs.append("narration:after_run")
    needs.append(f"segment:{step['segment']}")
    seen = []
    for n in needs:
        if n in NOT_BUILT and n not in seen:
            seen.append(n)
    return [(n, NOT_BUILT[n]) for n in seen]


def load_steps(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    STEPS_VALIDATOR.validate(doc)
    return doc


class Runner:
    def __init__(self, context, page, log, variables, narration_len=None, mark_style=None, take_pages=None, allow=()):
        self.ctx, self.page, self.log = context, page, log
        self.allow = list(allow)                      # the step list's own allows (R91), on top of each step's
        self.vars = variables
        self.take_pages = list(take_pages or [page])   # the take window's tabs, in tab-strip order (switch_tab)
        self.narration_len = narration_len or {}      # line_id -> (length_s, cue_offset_s[, click_offset_s[, marks]])
        self.mark_style = mark_style or {}            # edit_settings.json "marks": geometry and timing of live marks
        self.subject = None                           # CSS box of the element this step's only_if found
        self.claude_files = set()                     # Claude session logs this take wrote (fetched after the run)
        self.decided = {}                             # step id -> its only_if's outcome (only_if.same_as)
        vw = page.evaluate("[innerWidth, innerHeight]")
        self.mouse = (vw[0] / 2, vw[1] / 2)
        self.page.mouse.move(*self.mouse)
        self.virtual = False                          # a Windows dialog is up: moves are drawn, not made (os_click)

    # -- helpers ---------------------------------------------------------------------------------------------------
    def sub(self, s):
        for k, v in self.vars.items():
            s = s.replace("{" + k + "}", v)
        return s

    def host(self):
        return urlparse(self.page.url).hostname

    def tab_name(self, page):
        """github, ide ({codespace_name}.github.dev exactly) or dashboard (its -8050.app.github.dev): GOTCHAS, the
        editor tab and the app tab share the codespace name."""
        host = urlparse(page.url).hostname or ""
        if host.endswith("quicksight.aws.amazon.com"):
            return "quicksight"
        cs = self.vars.get("codespace_name", "")
        if host == f"{cs}.github.dev":
            return "ide"
        if host == f"{cs}-8050.app.github.dev":
            return "dashboard"
        return "github" if host.endswith("github.com") else None

    def tab_page(self, name):
        live = [p for p in self.take_pages if not p.is_closed()]
        return next((p for p in live if self.tab_name(p) == name), None)

    def frames(self, frame):
        """Where a target may live: the page itself, or, for the Claude Code panel, any nested webview frame."""
        main = self.page.main_frame
        return [main] if frame in (None, "main") else [f for f in self.page.frames if f != main]

    def find(self, frame, sel):
        """The first visible match in those frames, or None."""
        for fr in self.frames(frame):
            try:
                loc = fr.locator(self.sub(sel))
                for i in range(loc.count()):
                    if loc.nth(i).is_visible():
                        return loc.nth(i)
            except Exception:                           # a webview frame can detach while it reloads
                continue
        return None

    def wait_state(self, frame, sel, state, timeout_s):
        """Polls until sel is visible (returns it) or hidden (returns True); None on timeout. Waits with Playwright's
        own timer, so the sync API's event loop keeps running."""
        end = time.time() + timeout_s
        while True:
            loc = self.find(frame, sel)
            if state == "visible" and loc is not None:
                return loc
            if state == "hidden" and loc is None:
                return True
            if time.time() >= end:
                return None
            self.page.wait_for_timeout(100)

    def frame_text(self, frame):
        """The frames' visible text and their HTML, so a placeholder ("Queue another message", the busy Claude Code
        panel; the workshop's watch.py) counts as well as typed text."""
        out = []
        for fr in self.frames(frame):
            try:
                out += [fr.locator("body").inner_text(timeout=1000), fr.content()]
            except Exception:
                continue
        return " ".join(" ".join(out).split())

    def locate(self, target):
        for sel in [target["locator"], *target.get("fallback", [])]:
            loc = self.find(target["frame"], sel)
            if loc is not None:
                return loc
        raise RuntimeError(f"locator not found: {target['locator']}")

    def move_mouse(self, x, y, duration):
        """Ease-in-out path from the current position, at up to ~60 moves per second. Each point is where the path
        should be now, so a page that is slow to take mouse events (inside the Claude panel after a reply, each
        move took about 0.8 s in s7_take02, stretching a 0.5 s move to 24 s) gets fewer points, not a longer move."""
        if self.virtual:                                # the page's pointer can't reach a Windows dialog, and its
            time.sleep(max(0.0, duration))              # moves would hover the page beneath: the edit draws this one
            self.mouse = (x, y)
            return
        x0, y0 = self.mouse
        start = time.perf_counter()
        while True:
            u = min(1.0, (time.perf_counter() - start) / duration) if duration > 0 else 1.0
            e = 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
            self.page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
            if u >= 1.0:
                break
            delay = 1 / 60 - (time.perf_counter() - start) % (1 / 60)
            time.sleep(delay)
        self.mouse = (x, y)

    def only_if(self, step):
        """True to run the step. A false condition skips the step (logged) or stops the take (a precondition)."""
        cond = step.get("only_if")
        if not cond:
            return True
        ok = self._only_if(step, cond)
        self.decided[step["id"]] = ok
        return ok

    def _only_if(self, step, cond):
        try:
            if cond.get("same_as") in self.decided:     # one decision for a group of steps (R70's second round)
                if not self.decided[cond["same_as"]]:
                    raise TimeoutError(f"as {cond['same_as']}")
                return True
            if cond.get("eval"):                # a JS test of a tab's page (R70: the defect still shows after the fix)
                pg = self.tab_page(cond["tab"]) if cond.get("tab") else self.page
                if pg is None or not pg.evaluate(cond["eval"]):
                    raise TimeoutError(f"eval false: {cond['eval'][:80]}")
                return True
            loc = self.wait_state(cond.get("frame"), cond["locator"], cond["state"], cond.get("timeout_s", 1))
            if loc is None:
                raise TimeoutError(cond["locator"])
            if cond["state"] == "visible":      # the thing the line talks about: captions keep clear of it
                b = loc.bounding_box()
                self.subject = b
                self.log.event("text_box", step["id"], url_host=self.host(), result="ok" if b else "fail",
                               box={k: round(v, 1) for k, v in b.items()} if b else None, frame_chain=["main"],
                               detail={"role": "subject", "locator": cond["locator"]})
            return True
        except Exception:
            what = (f"as {cond['same_as']}" if cond.get("same_as") in self.decided else
                    cond.get("eval", "")[:80] or f"{cond['locator']} {cond['state']}")
            if cond.get("otherwise", "skip") == "stop_take":
                self.log.event("error", step["id"], url_host=self.host(), result="fail",
                               detail=f"precondition not met: {what}")
                raise RuntimeError(f"{step['id']}: precondition not met ({what})")
            self.log.event("step_skipped", step["id"], url_host=self.host(), line_id=step["narration"]["line_id"],
                           detail={"only_if": cond.get("eval") or cond["locator"], "state": cond["state"]})
            return False

    MARK_BOX_JS = """([sel, match, pick, whole]) => {
      const els = [...document.querySelectorAll(sel)].filter(e => { const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0; });
      if (!els.length) return null;
      const el = pick === 'topmost' ? els.reduce((a, b) => b.getBoundingClientRect().top < a.getBoundingClientRect().top ? b : a) : els[0];
      let r = whole ? el.getBoundingClientRect() : null;   // a region (an overview mark): the element itself
      if (match && !whole) {                           // the box of the matching text, not the whole element
        const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        let full = '', nodes = [];
        while (walk.nextNode()) { nodes.push([walk.currentNode, full.length]); full += walk.currentNode.data; }
        const i = full.indexOf(match);
        if (i >= 0) {
          const at = k => { for (let j = nodes.length - 1; j >= 0; j--) if (nodes[j][1] <= k) return [nodes[j][0], k - nodes[j][1]]; };
          const range = document.createRange();
          range.setStart(...at(i)); range.setEnd(...at(i + match.length - 1)); range.setEnd(range.endContainer, range.endOffset + 1);
          r = range.getBoundingClientRect();
        }
      }
      if (!r) {                                        // text extent: the union of the element's children
        const kids = [...el.querySelectorAll('span')].map(k => k.getBoundingClientRect()).filter(b => b.width > 0);
        r = kids.length ? kids.reduce((a, b) => ({left: Math.min(a.left, b.left), top: Math.min(a.top, b.top),
              right: Math.max(a.right, b.right), bottom: Math.max(a.bottom, b.bottom)})) : el.getBoundingClientRect();
      }
      const guard = el.closest('.overflow-guard');    // an editor's visible area; else the viewport (VS Code's <html> has no height)
      const clip = guard ? guard.getBoundingClientRect() : {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
      const x0 = Math.max(r.left, clip.left), y0 = Math.max(r.top, clip.top);
      const x1 = Math.min(r.right, clip.right), y1 = Math.min(r.bottom, clip.bottom);
      return {x: x0, y: y0, width: x1 - x0, height: y1 - y0};
    }"""

    def measure_marks(self, step):
        """Log each page mark's box (CSS px) after the result has settled. Browser-chrome marks are found by OCR in
        the edit instead."""
        for i, mk in enumerate(step.get("marks", [])):
            t = mk["target"]
            if "locator" not in t:
                continue
            box, args = None, [self.sub(t["locator"]), self.sub(t["match"]) if t.get("match") else None,
                               t.get("pick", "first"), bool(t.get("whole_element"))]
            if t.get("tab") and self.tab_name(self.page) not in (None, t["tab"]):
                continue                                # measured on its own tab only (the step that shows it)
            for fr in self.frames(t.get("frame")):     # in a webview frame, offset by the frame's place in the page
                try:
                    box = fr.evaluate(self.MARK_BOX_JS, args)
                    if box and fr != self.page.main_frame:
                        off = fr.frame_element().bounding_box()
                        box = {**box, "x": box["x"] + off["x"], "y": box["y"] + off["y"]}
                except Exception as err:
                    box = None
                    if t.get("frame") in (None, "main"):
                        self.log.event("error", step["id"], url_host=self.host(), result="fail",
                                       detail=f"mark {i}: {type(err).__name__}")
                if box:
                    break
            if box and (box["width"] <= 0 or box["height"] <= 0):
                box = None
            if box:
                box = {k: round(v, 1) for k, v in box.items()}
            self.log.event("text_box", step["id"], tab=t.get("tab"), url_host=self.host(), box=box,
                           frame_chain=["main"] if t.get("frame") in (None, "main") else ["main", "claude_panel"],
                           result="ok" if box else "fail",
                           detail={"mark": i, "kind": mk["kind"], "locator": t["locator"]})

    # -- one step --------------------------------------------------------------------------------------------------
    def mark_gesture(self, step, i, mk, box, t0, timing, ev):
        """Draw one mark live, as David does with Epic Pen: travel to its start, draw it on the naming word, hold the
        button until the area has been discussed, release. Every leg is a logged cursor move (detail.gesture); the
        release is a dwell_end event. The edit draws the shape from these. Returns the release time."""
        ms, sid = self.mark_style, step["id"]
        vw, vh = self.page.evaluate("[innerWidth, innerHeight]")
        b = (box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"])
        if mk["kind"] == "rect":
            pad = ms["rect_pad_px"]
            a, c = (b[0] - pad, b[1] - pad), (b[2] + pad, b[3] + pad)
        else:
            a, c = arrow_points(b, vw, vh, ms)
        at = t0 + timing["at_s"]
        release = max(at + ms["draw_s"] + ms["hold_s"], t0 + (timing["release_s"] or 0) + ms["release_after_s"])
        m = approach_s(self.mouse, a)
        legs = [("approach", a, m, at - 0.05 - m), (mk["kind"], c, ms["draw_s"], at)]
        if mk["kind"] == "arrow" and ms.get("retreat_px"):          # keep the cursor's body off what the arrow names
            k = ms["retreat_px"] / max(1.0, math.dist(a, c))
            legs.append(("retreat", (c[0] + (a[0] - c[0]) * k, c[1] + (a[1] - c[1]) * k), 0.35,
                         at + ms["draw_s"] + 0.2))
        for gesture, to, dur, start in legs:
            wait = start - self.log.now()
            if wait > 0:
                time.sleep(wait)
            self.log.event("cursor_move_start", sid, tab=self.tab(step), url_host=self.host(),
                           box={k: round(v, 1) for k, v in box.items()}, frame_chain=["main"],
                           detail={"from_css": {"x": round(self.mouse[0], 1), "y": round(self.mouse[1], 1)},
                                   "to_css": {"x": round(to[0], 1), "y": round(to[1], 1)},
                                   "gesture": gesture, "mark": i}, **ev)
            self.move_mouse(*to, dur)
            self.log.event("cursor_arrive", sid, tab=self.tab(step), url_host=self.host(), frame_chain=["main"],
                           detail={"gesture": gesture, "mark": i}, **ev)
        wait = release - self.log.now()
        if wait > 0:
            time.sleep(wait)
        self.log.event("dwell_end", sid, tab=self.tab(step), url_host=self.host(),
                       detail={"mark": i, "kind": mk["kind"], "release": True}, **ev)
        return release

    def run_step(self, step):
        self.subject = None
        if step.get("after"):                            # a line-only step: the edit places it (pipeline.edit.plan)
            return
        if not self.only_if(step):
            return
        sid, a, nar = step["id"], step["action"], step["narration"]
        kind, line = a["type"], nar["line_id"]
        if kind == "type" and a.get("focused"):          # typing into the box a click step left active: no move, no
            kind = "type_focused"                        # click (the edit times it like a key press, on its cue)
        if not a.get("os"):                              # (a Windows dialog the page opened stays in front)
            self.front()                                 # the take's tab must be the one on screen (and not throttled)
        vals = self.narration_len.get(line, (0.0, DEFAULT_CUE))
        n_len, cue, click_at = vals[0], vals[1], (vals[2] if len(vals) > 2 else None)
        mark_times = vals[3] if len(vals) > 3 else []
        ev = dict(action=kind, line_id=line)
        t0 = self.log.event("step_start", sid, tab=self.tab(step), url_host=self.host(),
                            detail={"narration_len_s": n_len, "cue_offset_s": cue,
                                    "click_offset_s": click_at}, **ev)

        if kind == "navigate":
            time.sleep(max(0.0, cue))
            self.page.goto(self.sub(a["url"]), wait_until="domcontentloaded")
            t_act = self.log.event("action", sid, tab=self.tab(step), url_host=self.host(), result="ok",
                                   detail={"url_host": urlparse(self.sub(a["url"])).hostname}, **ev)
        elif kind in ("none", "key"):              # a line over the picture, or a key press on its cue word
            time.sleep(max(0.0, cue))
            if kind == "key" and a.get("target"):          # pressed on an element: the key lands in its frame
                self.locate(a["target"]).press(a["key"])   # (the Claude panel's webview has its own focus)
            elif kind == "key" and a["key"] in ("F5", "Control+R"):   # a key sent over CDP goes to the page, never
                self.page.reload(wait_until="domcontentloaded")         # to the browser's own reload shortcut
            elif kind == "key":
                self.page.keyboard.press(a["key"])
            t_act = self.log.event("action", sid, tab=self.tab(step), url_host=self.host(), result="ok",
                                   detail={"key": a["key"]} if kind == "key" else None, **ev)
        elif kind == "type_focused":
            wait = cue - (self.log.now() - t0)
            if wait > 0:
                time.sleep(wait)
            t_act = self.log.event("action", sid, tab=self.tab(step), url_host=self.host(), result="ok",
                                   detail={"focused": True}, **ev)
            self.type_text(sid, a, ev)
        elif kind == "click" and a.get("os"):
            t_act = self.os_click(step, ev, t0, cue, click_at, mark_times)
        elif kind == "drag":
            t_act = self.drag(step, ev, t0, cue, click_at)
        elif kind in ("click", "hover", "type"):
            loc = self.locate(a["target"])
            self.reveal(loc, a["target"])
            box = loc.bounding_box()
            fx, fy = (a["target"].get("point") or {}).get("x", 0.5), (a["target"].get("point") or {}).get("y", 0.5)
            px, py = box["x"] + box["width"] * fx, box["y"] + box["height"] * fy
            released = None
            for i, mk in enumerate(step.get("marks", [])):      # marks on the target or subject come before the click
                of = mk["target"].get("of")
                mbox = box if of == "action" else self.subject if of == "subject" else None
                if of and mbox and i < len(mark_times) and mark_times[i]["at_s"] is not None:
                    released = self.mark_gesture(step, i, mk, mbox, t0, mark_times[i], ev)
            wait = cue - (self.log.now() - t0)          # announce first: the move starts on the cue word (SPEC §6.2)
            if wait > 0:
                time.sleep(wait)
            dist = math.dist(self.mouse, (px, py))
            m = min(1.0, max(0.4, 0.35 + dist / 1800))
            cbox = {k: round(v, 1) for k, v in box.items()}
            chain = ["main"] if a["target"]["frame"] == "main" else ["main", "claude_panel"]
            self.log.event("cursor_move_start", sid, tab=self.tab(step), url_host=self.host(), box=cbox,
                           frame_chain=chain, detail={"from_css": {"x": round(self.mouse[0], 1),
                                                                   "y": round(self.mouse[1], 1)},
                                                      "to_css": {"x": round(px, 1), "y": round(py, 1)}}, **ev)
            self.move_mouse(px, py, m)
            self.log.event("cursor_arrive", sid, tab=self.tab(step), url_host=self.host(), box=cbox,
                           frame_chain=chain, **ev)
            hold = PAUSE_BEFORE_CLICK                  # point first, click as the name is said (SPEC §6.2)
            if click_at is not None:
                hold = max(hold, t0 + click_at + CLICK_AFTER_NAME - self.log.now())
            if released is not None:                    # the mark has faded before the click lands
                hold = max(hold, released + self.mark_style["fade_s"] + 0.05 - self.log.now())
            time.sleep(hold)
            pages_before = len(self.ctx.pages)
            if kind in ("click", "type"):               # typing starts with a click into the box
                self.page.mouse.click(px, py)
            if kind == "click" and a.get("select_all"):  # "click in the box and select its text" (a type step follows)
                self.page.keyboard.press("Control+A")
            t_act = self.log.event("action", sid, tab=self.tab(step), url_host=self.host(), box=cbox,
                                   frame_chain=chain, result="ok",
                                   detail={"point_css": {"x": round(px, 1), "y": round(py, 1)}}, **ev)
            if kind == "click":
                self._follow_new_tab(step, pages_before)
            if kind == "type":
                self.type_text(sid, a, ev)
                self.front()
        elif kind == "switch_tab":
            t_act = self.switch_tab(step, ev, t0, cue, click_at)
        elif kind == "wait_claude":
            t_act = self.log.event("action", sid, tab=self.tab(step), url_host=self.host(), result="ok", **ev)
            self.wait_claude(step, ev)
        elif kind == "scroll":
            t_act = self.scroll_reply(step, ev)
        else:
            raise NotImplementedError(f"action {kind} is not built")

        t_res = self.expect(step)
        dwell = step.get("dwell", {}).get("min_s", 0.0)
        v = max(VIEWER_TIME.get(kind, 1.0), dwell)
        end = max(t0 + n_len + NARRATION_PAD, t_res + v + OVER_RECORD)
        if t_res - t_act > LONG_WAIT_S:            # the edit cuts the wait, so the line may play over the result
            end = max(end, t_res + n_len + NARRATION_PAD)
        self.page.wait_for_timeout(max(0.0, end - self.log.now() - 0.3) * 1000)
        self.measure_marks(step)
        self.page.wait_for_timeout(max(0.0, end - self.log.now()) * 1000)
        if step.get("still"):                      # a page screenshot for the opening and recap graphics (R69)
            self.page.screenshot(path=str(Path(self.log.path).parent / step["still"]))
        self.log.event("step_end", sid, tab=self.tab(step), url_host=self.host(), result="ok", **ev)

    def switch_tab(self, step, ev, t0, cue, click_at):
        """A click on another tab of the take's window (p5.15b: back to the codespace). The browser's tab strip is
        outside the page, so the pointer can't go there: the tab's place is read from the screen (the capture monitor,
        as the recording sees it), the move and the click are logged in page CSS px (above the page: negative y) for
        the edit to draw (R17), and the tab is brought to the front on the click."""
        from PIL import ImageGrab
        from pipeline.config import CAPTURE_MONITOR_X, FRAME
        from pipeline.edit.marks import active_tab
        sid, name = step["id"], step["action"]["target"]["tab"]
        dest = self.tab_page(name)
        if dest is None:
            raise RuntimeError(f"no {name} tab in the take's window")
        order = [p for p in self.take_pages if not p.is_closed()]
        k = order.index(dest) - order.index(self.page)
        g = self.page.evaluate("({sx: screenX, sy: screenY, ow: outerWidth, oh: outerHeight, iw: innerWidth, "
                               "ih: innerHeight})")
        border = (g["ow"] - g["iw"]) / 2
        ox, oy = g["sx"] + border, g["sy"] + g["oh"] - g["ih"] - border   # the page's top left, on the screen
        shot = ImageGrab.grab(bbox=(CAPTURE_MONITOR_X, 0, CAPTURE_MONITOR_X + FRAME[0], FRAME[1]), all_screens=True)
        tab = active_tab(shot)
        if tab is None:
            raise RuntimeError("the take window's tab strip was not found on the capture monitor")
        L, w, y0, y1 = tab["left"], tab["width"], tab["top"], tab["bottom"]
        px, py = CAPTURE_MONITOR_X + L + (k + 0.5) * w - ox, (y0 + y1) / 2 - oy   # its title's middle, page CSS px
        box = {"x": round(CAPTURE_MONITOR_X + L + k * w - ox, 1), "y": round(y0 - oy, 1), "width": w,
               "height": y1 - y0}
        wait = cue - (self.log.now() - t0)
        if wait > 0:
            time.sleep(wait)
        m = min(1.0, max(0.4, 0.35 + math.dist(self.mouse, (px, py)) / 1800))
        self.log.event("cursor_move_start", sid, tab=name, url_host=self.host(), box=box, frame_chain=["main"],
                       detail={"from_css": {"x": round(self.mouse[0], 1), "y": round(self.mouse[1], 1)},
                               "to_css": {"x": round(px, 1), "y": round(py, 1)}, "chrome": "tab_strip"}, **ev)
        time.sleep(m)                                   # the pointer can't leave the page: the edit draws the move
        self.mouse = (px, py)
        self.log.event("cursor_arrive", sid, tab=name, url_host=self.host(), box=box, frame_chain=["main"], **ev)
        hold = PAUSE_BEFORE_CLICK
        if click_at is not None:
            hold = max(hold, t0 + click_at + CLICK_AFTER_NAME - self.log.now())
        time.sleep(hold)
        dest.bring_to_front()
        self.page = dest
        t_act = self.log.event("action", sid, tab=name, url_host=self.host(), box=box, frame_chain=["main"],
                               result="ok", detail={"point_css": {"x": round(px, 1), "y": round(py, 1)},
                                                    "chrome": "tab_strip", "slot": k}, **ev)
        self.log.event("tab_switch", sid, url_host=self.host(), detail={"reason": "switch_tab", "to": name})
        return t_act

    SMOOTH_SCROLL_JS = """async (el, ms) => {
      let c = el.parentElement;                         // the nearest panel that scrolls
      while (c && !(c.scrollHeight > c.clientHeight + 1 && /(auto|scroll)/.test(getComputedStyle(c).overflowY)))
        c = c.parentElement;
      if (!c) return null;
      const r = el.getBoundingClientRect(), cr = c.getBoundingClientRect(), m = 24;
      const top = Math.max(cr.top, 0), bottom = Math.min(cr.bottom, innerHeight);
      let d = 0;
      if (r.bottom + m > bottom) d = r.bottom + m - bottom; else if (r.top - m < top) d = r.top - m - top;
      if (!d) return 0;
      const a = c.scrollTop, t0 = performance.now(), sb = c.style.scrollBehavior;
      c.style.scrollBehavior = 'auto';                  // a CSS smooth scroll would lag each step behind
      await new Promise(done => { const tick = now => { const u = Math.min(1, (now - t0) / ms);
        c.scrollTop = a + d * (u < .5 ? 2 * u * u : 1 - (-2 * u + 2) ** 2 / 2);
        if (u < 1) requestAnimationFrame(tick); else done(); }; requestAnimationFrame(tick);
        setTimeout(done, ms + 1000); });                // a stalled animation frame never hangs the step
      c.scrollTop = a + d; c.style.scrollBehavior = sb;
      return d;
    }"""

    def reveal(self, loc, target):
        """Bring a target into view. Playwright's own scroll centres the element at once; with target.scroll smooth,
        the nearest scrolling panel eases just far enough instead (Quick Sight's data type list: the centring jump moved
        the panel 460 px on camera, where 43 px eased was enough)."""
        if target.get("scroll") == "smooth":
            d = loc.evaluate(self.SMOOTH_SCROLL_JS, SMOOTH_SCROLL_MS)
            if d is None:
                loc.scroll_into_view_if_needed()
            elif d:
                self.page.wait_for_timeout(150)
        else:
            loc.scroll_into_view_if_needed()

    def page_origin(self):
        """Where the page's top left sits on the screen, in screen px (every monitor at 100%, so CSS px = screen px)."""
        g = self.page.evaluate("({sx: screenX, sy: screenY, ow: outerWidth, oh: outerHeight, iw: innerWidth, "
                               "ih: innerHeight})")
        border = (g["ow"] - g["iw"]) / 2
        return g["sx"] + border, g["sy"] + g["oh"] - g["ih"] - border

    def os_click(self, step, ev, t0, cue, click_at, mark_times):
        """A click in a Windows dialog the page opened (R112: the upload's Open dialog, shown whole). The page's pointer
        can't reach the dialog and the real one stays off the capture monitor (R15), so the move and the click are
        logged in page CSS px for the edit to draw, as switch_tab does, and UI Automation does what the click does:
        it selects the item (the File name box follows) or presses the button. A mark on the target (of: action) is
        drawn first, as for any click (R49)."""
        from pipeline.driver import osdialog
        sid, spec = step["id"], step["action"]["os"]
        dlg = osdialog.find_dialog(spec["window"], spec.get("timeout_s", 10))
        if spec.get("folder") and osdialog.folder(dlg) != self.sub(spec["folder"]):
            raise RuntimeError(f"the {spec['window']} dialog shows {osdialog.folder(dlg)}, not {self.sub(spec['folder'])}")
        is_item = bool(spec.get("item"))
        el = osdialog.item(dlg, self.sub(spec["item"])) if is_item else osdialog.button(dlg, spec["button"])
        l, t, r, b = osdialog.name_box(dlg, el) if is_item else osdialog.box(el)   # a file: its name, not the row
        ox, oy = self.page_origin()
        box = {"x": round(l - ox, 1), "y": round(t - oy, 1), "width": r - l, "height": b - t}
        fx, fy = (spec.get("point") or {}).get("x", 0.5), (spec.get("point") or {}).get("y", 0.5)
        px, py = box["x"] + box["width"] * fx, box["y"] + box["height"] * fy
        what = {"os": spec["window"], **({"item": self.sub(spec["item"])} if is_item else {"button": spec["button"]})}
        self.virtual = True
        try:
            released = None
            for i, mk in enumerate(step.get("marks", [])):
                if mk["target"].get("of") == "action" and i < len(mark_times) and mark_times[i]["at_s"] is not None:
                    released = self.mark_gesture(step, i, mk, box, t0, mark_times[i], ev)
            wait = cue - (self.log.now() - t0)
            if wait > 0:
                time.sleep(wait)
            m = min(1.0, max(0.4, 0.35 + math.dist(self.mouse, (px, py)) / 1800))
            self.log.event("cursor_move_start", sid, tab=self.tab(step), url_host=self.host(), box=box,
                           frame_chain=["main"], detail={"from_css": {"x": round(self.mouse[0], 1),
                                                                      "y": round(self.mouse[1], 1)},
                                                         "to_css": {"x": round(px, 1), "y": round(py, 1)}, **what}, **ev)
            self.move_mouse(px, py, m)
            self.log.event("cursor_arrive", sid, tab=self.tab(step), url_host=self.host(), box=box,
                           frame_chain=["main"], **ev)
            hold = PAUSE_BEFORE_CLICK
            if click_at is not None:
                hold = max(hold, t0 + click_at + CLICK_AFTER_NAME - self.log.now())
            if released is not None:
                hold = max(hold, released + self.mark_style["fade_s"] + 0.05 - self.log.now())
            time.sleep(max(0.0, hold))
            if is_item:
                osdialog.select(el)
                want, end = self.sub(spec["item"]), time.time() + 1.0
                while (got := osdialog.file_name(dlg)) not in (None, want) and time.time() < end:
                    time.sleep(0.1)                                     # the box follows the selection a moment later
                if got is not None and got != want:                     # a miss would only show at the next expect
                    raise RuntimeError(f"selected {self.sub(spec['item'])!r} but the File name box holds {got!r}")
            else:
                osdialog.invoke(el)
            return self.log.event("action", sid, tab=self.tab(step), url_host=self.host(), box=box,
                                  frame_chain=["main"], result="ok",
                                  detail={"point_css": {"x": round(px, 1), "y": round(py, 1)}, **what}, **ev)
        finally:
            self.virtual = False

    def drag(self, step, ev, t0, cue, click_at):
        """Press on the target, carry it with the button held to `to` (another target's point) or `by` (a CSS offset
        from the press), release: Quick Sight's visuals are moved and resized this way. The pointer really moves, so the
        page sees a real drag, and the edit draws it like any move (R17); the click ring marks the press."""
        sid, a = step["id"], step["action"]
        loc = self.locate(a["target"])
        self.reveal(loc, a["target"])
        box = loc.bounding_box()
        fx, fy = (a["target"].get("point") or {}).get("x", 0.5), (a["target"].get("point") or {}).get("y", 0.5)
        px, py = box["x"] + box["width"] * fx, box["y"] + box["height"] * fy
        if a.get("to"):
            dbox = self.locate(a["to"]).bounding_box()
            dx, dy = (a["to"].get("point") or {}).get("x", 0.5), (a["to"].get("point") or {}).get("y", 0.5)
            tx, ty = dbox["x"] + dbox["width"] * dx, dbox["y"] + dbox["height"] * dy
        else:
            tx, ty = px + a["by"]["x"], py + a["by"]["y"]
        cbox = {k: round(v, 1) for k, v in box.items()}
        x0, y0 = min(box["x"], tx - 20), min(box["y"], ty - 20)     # press and drop: what the camera must frame
        both = {"x": round(x0, 1), "y": round(y0, 1), "width": round(max(box["x"] + box["width"], tx + 20) - x0, 1),
                "height": round(max(box["y"] + box["height"], ty + 20) - y0, 1)}
        wait = cue - (self.log.now() - t0)
        if wait > 0:
            time.sleep(wait)
        m = min(1.0, max(0.4, 0.35 + math.dist(self.mouse, (px, py)) / 1800))
        self.log.event("cursor_move_start", sid, tab=self.tab(step), url_host=self.host(), box=cbox,
                       frame_chain=["main"], detail={"from_css": {"x": round(self.mouse[0], 1),
                                                                  "y": round(self.mouse[1], 1)},
                                                     "to_css": {"x": round(px, 1), "y": round(py, 1)}}, **ev)
        self.move_mouse(px, py, m)
        self.log.event("cursor_arrive", sid, tab=self.tab(step), url_host=self.host(), box=cbox, frame_chain=["main"],
                       **ev)
        hold = PAUSE_BEFORE_CLICK
        if click_at is not None:
            hold = max(hold, t0 + click_at + CLICK_AFTER_NAME - self.log.now())
        time.sleep(max(0.0, hold))
        self.page.mouse.down()
        t_act = self.log.event("action", sid, tab=self.tab(step), url_host=self.host(), box=both, frame_chain=["main"],
                               result="ok", detail={"point_css": {"x": round(px, 1), "y": round(py, 1)},
                                                    "drag_to_css": {"x": round(tx, 1), "y": round(ty, 1)}}, **ev)
        self.log.event("cursor_move_start", sid, tab=self.tab(step), url_host=self.host(), box=both,
                       frame_chain=["main"],
                       detail={"from_css": {"x": round(px, 1), "y": round(py, 1)},
                               "to_css": {"x": round(tx, 1), "y": round(ty, 1)}, "drag": True}, **ev)
        self.move_mouse(tx, ty, min(1.6, max(0.8, 0.5 + math.dist((px, py), (tx, ty)) / 900)))
        self.log.event("cursor_arrive", sid, tab=self.tab(step), url_host=self.host(), frame_chain=["main"], **ev)
        time.sleep(0.15)                                 # the drop target settles under the pointer before the release
        self.page.mouse.up()
        return t_act

    def front(self):
        """Bring the take's tab to the front, every time: in s7_take02 the GitHub tab (the IDE tab's opener) came to
        the front just after Claude's first edit, with nothing logged, while document.visibilityState in the IDE still
        said "visible". The IDE then ran in the background (throttled: 24 s pointer moves) and off camera."""
        try:
            self.page.bring_to_front()
        except Exception:
            pass

    # -- live steps (S7) ---------------------------------------------------------------------------------------------
    def wait_claude(self, step, ev):
        """A live wait (SPEC §3): until Claude's turn is over. The panel says busy or idle and shows permission
        prompts; the session log (read over gh in the background) says whether the turn really ended, so a background
        reviewer still running doesn't count as done (workshop lesson). Routine prompts are approved with a visible,
        logged click (R39, R47); a RISKY one stops the take; a question from Claude ends the wait (it waits for us).
        Every change in the log is a claude_state event, which the edit's time-lapse and the post-run narration read."""
        sid = step["id"]
        max_s = step["action"].get("max_wait_s") or step["expect"].get("timeout_s", 600)
        t_start, latest, stop = self.log.now(), {}, threading.Event()

        def poll_log():
            while not stop.is_set():
                latest.update(cw.status(self.vars["codespace_name"]), seen=time.time())
                stop.wait(LOG_POLL_S)

        threading.Thread(target=poll_log, daemon=True).start()
        logged, idle_since = None, None
        ours = set(self.ctx.pages)
        try:
            while True:
                if self.log.now() - t_start > max_s:
                    raise TimeoutError(f"Claude still working after {max_s:.0f} s")
                for p in [p for p in self.ctx.pages if p not in ours]:
                    self.close_stray_tab(sid, p)
                if int(self.log.now() - t_start) % 3 == 0:
                    self.front()
                ui = cw.state(self.page)
                s = dict(latest)
                key = (s.get("state"), s.get("n"), s.get("last_tool"))
                if s and key != logged:
                    logged = key
                    if s.get("file"):
                        self.claude_files.add(s["file"])
                    self.log.event("claude_state", sid, url_host=self.host(), detail={
                        "ui": ui, **{k: s.get(k) for k in ("state", "last_tool", "n", "tools", "sub_age", "age",
                                                           "file", "err") if k in s}})
                if ui == "attention":
                    idle_since = None
                    if not self.answer_prompt(step, ev):
                        self.log.event("claude_question", sid, url_host=self.host(),
                                       detail={"text": cw.prompt_text(self.page)[:300]})
                        return
                    continue
                if ui == "busy":
                    idle_since = None
                else:
                    idle_since = idle_since or time.time()
                    quiet = time.time() - idle_since
                    fresh = s.get("seen", 0) > idle_since
                    if quiet >= IDLE_CONFIRM_S and fresh and s.get("state") == "done" and s.get("age", 0) > 4 \
                            and not cw.waiting_on_reviewer(s):
                        return
                    if quiet >= IDLE_NO_LOG_S and fresh and s.get("state") in ("error", "none"):
                        self.log.event("error", sid, url_host=self.host(), result="ok",
                                       detail=f"session log unreadable ({s.get('err', '')[:80]}); the panel's idle state decides")
                        return
                    if quiet >= 45:                    # the log disagrees with an idle panel for too long
                        self.log.event("error", sid, url_host=self.host(), result="ok",
                                       detail=f"panel idle 45 s while the log says {s.get('state')}; treated as done")
                        return
                self.page.wait_for_timeout(CLAUDE_POLL_S * 1000)
        finally:
            stop.set()

    def close_stray_tab(self, sid, p):
        """A tab that opened by itself during a live wait: the template forwards port 8050 with onAutoForward
        openBrowser, so Codespaces opens the dashboard whenever Claude starts it (s7_take01: twice). It would cover
        the take, and the IDE tab behind it is throttled (pointer moves took 30 to 56 s). Logged, closed, and the
        take's tab brought back."""
        try:
            p.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        self.log.event("tab_switch", sid, url_host=urlparse(p.url).hostname,
                       detail={"reason": "opened on its own (port auto-forward); closed", "closed": True})
        p.close()
        self.page.bring_to_front()

    def answer_prompt(self, step, ev):
        """A permission prompt: logged (prompt_seen), then approved with the Yes button as a normal click
        (prompt_approved). False when the panel wants attention but shows no Yes button: a question for us."""
        sid = step["id"]
        txt = cw.prompt_text(self.page)
        yes = self.wait_state("claude_panel", cw.YES_BUTTON, "visible", 3)
        if yes is None:
            return False
        box = {k: round(v, 1) for k, v in yes.bounding_box().items()}
        self.log.event("prompt_seen", sid, url_host=self.host(), box=box, frame_chain=["main", "claude_panel"],
                       detail={"text": txt[:500]}, **ev)
        rest = txt                                        # an allow covers only what it matches: anything risky
        for a in step["action"].get("allow", []) + self.allow:    # left in the command still stops the take
            rest = re.sub(a, " ", rest, flags=re.I)
        if cw.RISKY.search(rest):
            self.log.event("error", sid, url_host=self.host(), result="fail", detail=f"RISKY prompt: {txt[:300]}")
            raise RuntimeError(f"RISKY prompt held for David: {txt[:120]!r}")
        self.page.wait_for_timeout(1500)                  # long enough to read at 1x before the click (R39)
        px, py = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.log.event("cursor_move_start", sid, tab="ide", url_host=self.host(), box=box,
                       frame_chain=["main", "claude_panel"],
                       detail={"from_css": {"x": round(self.mouse[0], 1), "y": round(self.mouse[1], 1)},
                               "to_css": {"x": round(px, 1), "y": round(py, 1)}, "gesture": "approve"}, **ev)
        self.move_mouse(px, py, min(1.0, max(0.4, 0.35 + math.dist(self.mouse, (px, py)) / 1800)))
        self.log.event("cursor_arrive", sid, tab="ide", url_host=self.host(), box=box,
                       frame_chain=["main", "claude_panel"], **ev)
        time.sleep(PAUSE_BEFORE_CLICK)
        self.page.mouse.click(px, py)
        self.log.event("prompt_approved", sid, tab="ide", url_host=self.host(), box=box,
                       frame_chain=["main", "claude_panel"], result="ok",
                       detail={"point_css": {"x": round(px, 1), "y": round(py, 1)}}, **ev)
        end = time.time() + 5
        while time.time() < end and cw.state(self.page) == "attention":
            self.page.wait_for_timeout(200)
        return True

    SCROLL_PLAN_JS = """(sel) => {
      const c = document.querySelector(sel);
      if (!c) return null;
      const turns = [...c.querySelectorAll('[class*="turn_"]')];
      const turn = turns[turns.length - 1];
      if (!turn) return null;
      const msgs = [...turn.querySelectorAll('[aria-label^="Claude"]')];
      let i = msgs.length - 1;                          // the reply: Claude's text after its last tool use
      while (i > 0 && msgs[i - 1].getAttribute('aria-label') === 'Claude') i--;
      const first = msgs[i];
      if (!first) return null;
      const head = turn.querySelector('[class*="stickyHeader"]');
      const cr = c.getBoundingClientRect(), fr = first.getBoundingClientRect();
      const hh = head ? head.getBoundingClientRect().height : 0;
      const start = Math.max(0, c.scrollTop + fr.top - cr.top - hh - 8);
      const end = Math.max(start, c.scrollHeight - c.clientHeight);
      const words = msgs.slice(i).map(m => m.innerText).join(' ').split(/\\s+/).length;
      return {start: Math.round(start), end: Math.round(end), now: Math.round(c.scrollTop), header_px: Math.round(hh),
              words, box: {x: cr.x, y: cr.y, width: cr.width, height: cr.height}};
    }"""
    SCROLL_RUN_JS = """([sel, a, b, ms]) => new Promise(done => {
      const c = document.querySelector(sel), t0 = performance.now();
      const tick = now => { const u = Math.min(1, (now - t0) / ms); c.scrollTop = a + (b - a) * u;
        if (u < 1) requestAnimationFrame(tick); else done(c.scrollTop); };
      requestAnimationFrame(tick);
    })"""

    def scroll_reply(self, step, ev):
        """Read Claude's last reply on camera: jump to its start (below the pinned prompt), hold, scroll through it
        at a steady reading pace, hold. The narration is written after the run (R33); the edit cuts or speeds the
        scroll to fit it. A failure is logged and the take goes on: nothing later depends on the scroll."""
        sid, sel = step["id"], step["action"]["target"]["locator"]
        fr = next((f for f in self.frames("claude_panel") if self._has(f, sel)), None)
        plan = fr.evaluate(self.SCROLL_PLAN_JS, sel) if fr else None
        if not plan:
            return self.log.event("action", sid, url_host=self.host(), result="fail", detail="no reply to scroll", **ev)
        off = fr.frame_element().bounding_box()
        plan["box"] = {k: round(plan["box"][k] + (off["x"] if k == "x" else off["y"] if k == "y" else 0), 1)
                       for k in plan["box"]}
        fr.evaluate("([s, y]) => { document.querySelector(s).scrollTop = y; }", [sel, plan["start"]])
        t_act = self.log.event("action", sid, url_host=self.host(), box=plan["box"], result="ok",
                               frame_chain=["main", "claude_panel"], detail=plan, **ev)
        self.page.wait_for_timeout(SCROLL_HOLD_S * 1000)
        dur = min(90.0, (plan["end"] - plan["start"]) / READ_PX_S)
        if dur > 0.2:
            self.log.event("scroll_start", sid, url_host=self.host(), detail={"from": plan["start"], "to": plan["end"],
                                                                          "dur_s": round(dur, 2)}, **ev)
            top = fr.evaluate(self.SCROLL_RUN_JS, [sel, plan["start"], plan["end"], dur * 1000])
            self.log.event("scroll_end", sid, url_host=self.host(), detail={"top": top}, **ev)
        self.page.wait_for_timeout(SCROLL_HOLD_S * 1000)
        return t_act

    @staticmethod
    def _has(frame, sel):
        try:
            return frame.locator(sel).count() > 0
        except Exception:
            return False

    def type_text(self, sid, a, ev):
        """Type into the focused box: natural typing (full) or all at once (paste). A newline is Shift+Enter, which the
        Claude Code panel takes as a line break rather than Send."""
        text = self.sub(a["text"])
        self.log.event("type_start", sid, url_host=self.host(),
                       detail={"chars": len(text), "mode": a.get("typing_mode", "full")}, **ev)
        if a.get("select_all"):                       # the box's own text goes (a name or format being replaced)
            self.page.keyboard.press("Control+A")
        for i, line in enumerate(text.split("\n")):
            if i:
                self.page.keyboard.press("Shift+Enter")
            if a.get("typing_mode") == "paste":
                self.page.keyboard.insert_text(line)
            elif line:
                self.page.keyboard.type(line, delay=TYPE_DELAY_MS)
        if a.get("submit"):                           # Enter: Quick Sight's name boxes have no Save button
            self.page.keyboard.press(a["submit"])
        self.log.event("type_end", sid, url_host=self.host(), **ev)

    def _follow_new_tab(self, step, pages_before):
        """Switch to a tab the click opened. Waits with Playwright's own timer: time.sleep would block the sync API's
        event loop, so the new tab would never register. Steps whose expected result is in another tab (expect.tab
        differs from the target's tab) get up to 15 s; others get a short check."""
        sid = step["id"]
        expects_new = step["expect"].get("tab") not in (None, step["action"]["target"]["tab"])
        t_end = time.time() + (15.0 if expects_new else 1.0)
        while time.time() < t_end:
            if len(self.ctx.pages) > pages_before:
                new = self.ctx.pages[-1]
                new.bring_to_front()
                new.mouse.move(*self.mouse)
                self.page = new
                self.take_pages.append(new)              # opened from a link: to the right, at the strip's end
                self.log.event("tab_switch", sid, url_host=self.host(), detail={"reason": "click opened a new tab"})
                return
            self.page.wait_for_timeout(100)

    def tab(self, step):
        return step["action"].get("target", {}).get("tab") or step["expect"].get("tab")

    def expect(self, step):
        try:
            return self._expect(step)
        except Exception as err:
            if step.get("on_fail") != "retry_once":
                raise
            self.log.event("error", step["id"], url_host=self.host(), result="timeout",
                           detail=f"expect not met ({type(err).__name__}); reloading once")
            self.page.reload(wait_until="domcontentloaded")
            return self._expect(step)

    def _expect(self, step):
        e = step["expect"]
        timeout = e.get("timeout_s", 15) * 1000
        if e["kind"] in ("visible", "hidden") and e.get("frame") not in (None, "main"):
            if self.wait_state(e["frame"], e["locator"], e["kind"], timeout / 1000) is None:
                raise TimeoutError(f"{e['locator']} not {e['kind']} in {e['frame']}")
        elif e["kind"] == "text_in_frame":
            value, end = " ".join(self.sub(e["value"]).split()), time.time() + timeout / 1000
            while value not in self.frame_text(e.get("frame", "claude_panel")):
                if time.time() >= end:
                    raise TimeoutError(f"text not in {e.get('frame')}: {value[:40]}")
                self.page.wait_for_timeout(200)
        elif e["kind"] == "claude_idle":
            if step["action"]["type"] != "wait_claude":          # wait_claude has already waited for it
                self.wait_claude(step, dict(action=step["action"]["type"], line_id=step["narration"]["line_id"]))
        elif e["kind"] in ("visible", "hidden"):
            self.page.locator(self.sub(e["locator"])).first.wait_for(state=e["kind"], timeout=timeout)
        elif e["kind"] == "url_contains":
            value = self.sub(e["value"])
            self.page.wait_for_url(lambda u: value in u, timeout=timeout)
        elif e["kind"] != "none":
            raise NotImplementedError(f"expect {e['kind']} is not in slice S1")
        return self.log.event("expect_met", step["id"], url_host=self.host(), result="ok",
                              detail={"kind": e["kind"]})
