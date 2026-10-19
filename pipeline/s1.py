"""Record a take of a step list, silently, with the run log and sync flashes (slices S1 to S5).

    python -m pipeline.s1 [--steps=steps_s4.json]   # record a new take, then build the report (default steps_s1.json)
    python -m pipeline.s1 --dry [--steps=...]       # pre-flight, the off-camera prepare, OBS setup; nothing is recorded
    python -m pipeline.s1 --resume=runs/<run_id>    # after the Part 5 pause: record the rest of the take (R70)
    python -m pipeline.s1 --steps=qs1_section_a/steps_full.json   # another exercise's step list (its own folder)
    python -m pipeline.s1 --rehearse --steps=<ex>/steps_full.json [--to=<step id>] [--fast]   # off camera, below

A rehearsal (--rehearse, CREATE_A_VIDEO stage 5) clears the capture monitor, opens the take's own window and runs
pre-flight and the prepare as a take does, then walks every step (through --to, and never past a `pause`) with the
take's Runner: no OBS, no flashes, no report. It writes runs/_rehearse/<prefix>_<yyyymmdd>_NN/: runlog.jsonl,
stills/<step id>.png (the capture monitor after each step that ran) and rehearse.json (each step's result and expect
wait, each mark measured or not, unmeasured ones listed first: GOTCHAS 397; each typed field read back). --fast drops
lines.json's lengths for the runner's defaults, so it runs before the lines are voiced. It exits 1 when a step fails
or a typed box doesn't hold what was typed (or no box had the focus). What the steps make stays in the account
(stage 5 says how to clean it).

A step list with a `pause` (R70) stops recording before that step and leaves the take's tabs open: Claude explores
the dashboard off camera (pipeline.generated.explore), writes runs/<run_id>/generated.json, and resumes the take,
which merges the generated steps (pipeline.generated.merge), voices their draft lines, reloads the dashboard, records
the rest in the same codespace and joins the two recordings (pipeline.post.join).

The run folder is named after the steps file: steps_s4.json -> runs/dashboard_<date>_s4_takeNN (a step list's
`run_prefix` replaces "dashboard"). A --steps path with a folder is read from that exercise folder; a bare name, from
the dashboard exercise's.

Uses the workshop's Edge window (CDP 9333), or the profile the step list names in `browser` (R113: quicksight, CDP
9335), in a new window of its own, which is closed at the end. David's tabs are left alone. OBS switches to the AIDV profile and scene collection for the take and back to David's afterwards. Other
windows on the capture monitor move to the left-hand one for each recording and come back after it, the pause included
(R89, pipeline.capture.screen).
"""
import hashlib
import json
import platform
import sys
import time
from datetime import date, datetime, timezone
from importlib.metadata import version
from pathlib import Path

from pipeline import preflight
from pipeline.capture import browser, screen
from pipeline.capture.obs import FPS, OBSCapture
from pipeline.capture.sync import flash
from pipeline.config import CAPTURE_MONITOR_X, EXERCISES, FRAME, RUNS
from pipeline.driver.prepare import ensure_app, open_tabs, prepare_ide
from pipeline.driver.runlog import RunLog
from pipeline.driver.runner import DEFAULT_CUE, Runner, load_steps, missing
from pipeline.post.s1_report import report
from pipeline.vendor import claude_watch, cs

STEPS_DIR = EXERCISES / "build_an_interactive_dashboard"
START_URL = "https://github.com"
REHEARSE = RUNS / "_rehearse"                 # rehearsals' folders (--rehearse), beside the takes
SLOW_EXPECT = 0.5                             # an expect that took this share of its timeout is listed in rehearse.json


def narration_lengths(doc):
    """line_id -> (length_s, cue_offset_s, click_offset_s) from lines.json (pipeline.narration.build), so the take over-records enough
    picture under each line (SPEC §6.2). Lines not voiced yet fall back to the runner's defaults."""
    import json
    path = EXERCISES / doc["exercise"] / "lines.json"
    lines = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {lid: (l["length_s"], l["cue_offset_s"] if l["cue_offset_s"] is not None else DEFAULT_CUE,
                  l.get("click_offset_s"), l.get("marks", [])) for lid, l in lines.items()}


def new_run_dir(tag, prefix="dashboard"):
    stem = f"{prefix}_{date.today():%Y%m%d}_{tag}_take"
    n = 1 + max([int(p.name[len(stem):]) for p in RUNS.glob(stem + "*") if p.name[len(stem):].isdigit()], default=0)
    d = RUNS / f"{stem}{n:02d}"
    (d / "raw").mkdir(parents=True)
    return d


def open_recording_window(ctx, start_url=START_URL):
    """A new Edge window of its own, maximized on the capture monitor, so the recorded tab strip shows only the take's
    tabs (never David's workshop tabs). Tabs the take opens (target=_blank) land in this window too."""
    cdp = ctx.browser.new_browser_cdp_session()
    with ctx.expect_page(timeout=15000) as info:      # Playwright's wait keeps its event loop running
        cdp.send("Target.createTarget", {"url": start_url, "newWindow": True})
    page = info.value
    page.wait_for_load_state("domcontentloaded")
    s = page.context.new_cdp_session(page)
    win = s.send("Browser.getWindowForTarget")["windowId"]
    s.send("Browser.setWindowBounds", {"windowId": win, "bounds": {"windowState": "normal"}})
    s.send("Browser.setWindowBounds", {"windowId": win, "bounds": {"left": CAPTURE_MONITOR_X + 40, "top": 40,
                                                                   "width": 1600, "height": 900}})
    s.send("Browser.setWindowBounds", {"windowId": win, "bounds": {"windowState": "maximized"}})
    page.bring_to_front()
    return page


def computed_geometry(page):
    """Where the page sits in the capture frame, worked out from browser metrics (a cross-check for the flash)."""
    m = page.evaluate("({sx: screenX, sy: screenY, ow: outerWidth, oh: outerHeight, iw: innerWidth, ih: innerHeight,"
                      " dpr: devicePixelRatio})")
    border = (m["ow"] - m["iw"]) / 2
    return m, {"calibration": "computed",
               "viewport_origin_px": {"x": round(m["sx"] - CAPTURE_MONITOR_X + border),
                                      "y": round(m["sy"] + m["oh"] - m["ih"] - border)},
               "px_per_css": m["dpr"], "video_px": {"w": FRAME[0], "h": FRAME[1]}, "fps": FPS}


def run_steps(runner, log, steps, after_step=None):
    """The steps in order; an error ends the take but keeps the footage (end flash, stop and save as usual).
    after_step(step), if given, runs after each step, the failed one included (a rehearsal's still)."""
    for step in steps:
        print("step", step["id"], flush=True)
        try:
            runner.run_step(step)
        except Exception as err:
            failed = f"{step['id']}: {type(err).__name__}: {err}"
            log.event("error", step["id"], url_host=runner.host(), result="fail", detail=failed[:500])
            if after_step:
                after_step(step)
            return failed
        if after_step:
            after_step(step)
    return None


def fetch_claude(run_dir, codespace, names):
    for name in sorted(names):                     # Claude's session logs, for the post-run narration (R33)
        try:
            (run_dir / "claude").mkdir(exist_ok=True)
            text = claude_watch.fetch_session(codespace, name)
            (run_dir / "claude" / name).write_text(text, encoding="utf-8")
            print(f"claude session {name}: {len(text.splitlines())} records")
        except Exception as err:
            print(f"claude session {name} not fetched: {type(err).__name__}: {err}")


def steps_file(name):
    """A bare name is in the dashboard exercise's folder; a path with a folder is relative to exercises/."""
    return EXERCISES / name if "/" in name.replace("\\", "/") else STEPS_DIR / name


def not_built(steps):
    """Prints the steps that need capabilities that aren't built; True if there are any. Called before anything
    opens, so a take (or a rehearsal) is refused up front, not halfway through."""
    gaps = [(s["id"], need, by) for s in steps for need, by in missing(s)]
    for sid, need, by in gaps:
        print(f"NOT BUILT {sid}: {need} ({by})")
    if gaps:
        print(f"{len({g[0] for g in gaps})} steps need capabilities that aren't built; nothing recorded")
    return bool(gaps)


def clear_screen():
    """R89: nothing else on the capture monitor, the pointer off it (R15). Returns the moves for screen.restore."""
    moved = screen.clear()
    for w in moved:
        print(f"moved off the capture monitor: {w['exe']} '{w['title'][:50]}'")
    if screen.park_pointer():
        print("pointer moved off the capture monitor")
    return moved


def open_take(ctx, doc, prof):
    """The take's own window (maximized on the capture monitor), pre-flight on it, then the off-camera prepare.
    Returns (page, take_pages, take_hwnd), or None when pre-flight fails (its lines printed)."""
    page = open_recording_window(ctx, prof["start_url"])
    page.wait_for_timeout(2000)
    take_hwnd = screen.take_window()
    results = preflight.check(page)
    for ok, msg in results:
        print("PASS" if ok else "FAIL", msg)
    if not all(ok for ok, _ in results):
        print("pre-flight failed; nothing recorded")
        return None

    prep = doc.get("prepare", {})
    ide = prep.get("ide")
    if prep.get("app"):                         # a take that starts at Part 5: the dashboard Part 4 left running
        print("app (off camera):", ensure_app(doc["variables"]["codespace_name"], prep["app"]), flush=True)
    if ide:
        print("prepare (off camera):", prepare_ide(ctx, doc["variables"]["codespace_name"], ide), flush=True)
        page.bring_to_front()
    take_pages = [page]
    if prep.get("tabs"):                        # the take window as Parts 1 to 4 leave it (off camera)
        take_pages = open_tabs(page, prep["tabs"], doc["variables"], ide or {})
        print("tabs (off camera):", [p.url[:60] for p in take_pages], flush=True)
        page = take_pages[-1]
        page.bring_to_front()
    return page, take_pages, take_hwnd


def log_header(log, run_dir, doc, steps_path, ctx, metrics, captures, tool_versions):
    """The run log's header (SPEC §5): the steps file, the machine, the browser, what records the take."""
    log.header(
        run_id=run_dir.name, exercise=doc["exercise"], steps_version=doc["version"],
        steps_sha256=hashlib.sha256(steps_path.read_bytes()).hexdigest(),
        started_wall=datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
        variables=doc["variables"],
        machine={"windows_scaling_pct": 100, "capture_monitor": "DISPLAY1",
                 "monitor_px": {"w": FRAME[0], "h": FRAME[1]}},
        browser={"channel": "msedge", "version": ctx.browser.version,
                 "viewport_css": {"w": metrics["iw"], "h": metrics["ih"]},
                 "device_scale_factor": metrics["dpr"], "browser_zoom_pct": 100, "tab_layout": "top"},
        captures=captures,
        tools={"python": platform.python_version(), "playwright": version("playwright"),
               "opencv": version("opencv-python"), **tool_versions})


def close_take_pages(ctx, before):
    """Close every tab opened since `before` (the take's window); David's tabs are left alone (R8)."""
    for p in ctx.pages:
        if p not in before:
            try:
                p.close()
            except Exception:
                pass


def main(dry=False, steps_name="steps_s1.json"):
    steps_path = steps_file(steps_name)
    doc = load_steps(steps_path)
    prof = browser.use(doc.get("browser", "workshop"))   # before anything connects (R113)
    pause = doc.get("pause")
    ids = [s["id"] for s in doc["steps"]]
    first = doc["steps"][:ids.index(pause["before"])] if pause else doc["steps"]   # recorded before the pause
    if not_built(first):
        return 1
    tag = steps_path.stem.removeprefix("steps_")
    ctx = cs.context()
    before = list(ctx.pages)                       # David's tabs; everything opened after this is the take's
    obs, keep = None, False
    moved = clear_screen()
    try:
        took = open_take(ctx, doc, prof)
        if took is None:
            return 1
        page, take_pages, take_hwnd = took

        run_dir = RUNS / "_dry" if dry else new_run_dir(tag, doc.get("run_prefix", "dashboard"))
        metrics, geometry = computed_geometry(page)
        obs = OBSCapture()
        obs.setup(run_dir / "raw")
        if dry:
            print("dry run OK: OBS ready, pre-flight passed")
            return 0

        log = RunLog(run_dir / "runlog.jsonl")
        log_header(log, run_dir, doc, steps_path, ctx, metrics,
                   [{"id": "obs", "method": "obs", "file": "raw/obs.mkv", "source": "screen:DISPLAY1",
                     "geometry": geometry}], obs.versions())

        settings = json.loads((EXERCISES / doc["exercise"] / "edit_settings.json").read_text(encoding="utf-8"))
        runner = Runner(ctx, page, log, doc["variables"], narration_lengths(doc), settings["marks"], take_pages,
                        doc.get("allow", []))
        failed = None
        if first:
            obs.start()
            time.sleep(1.0)
            flash(page, log, "start")
            time.sleep(1.0)
            failed = run_steps(runner, log, first)
            time.sleep(0.5)
            flash(runner.page, log, "pause" if pause and not failed else "end")
            time.sleep(1.0)
            recorded = obs.stop()
            recorded.replace(run_dir / "raw" / ("obs_a.mkv" if pause and not failed else "obs.mkv"))
        log.close()
        obs.restore()
        obs = None
        if pause and not failed:                   # R70: off camera now; the take's tabs stay open for the explore
            keep = True
            tabs = {runner.tab_name(p): p.url for p in runner.take_pages if not p.is_closed() and runner.tab_name(p)}
            (run_dir / "pause.json").write_text(json.dumps({
                "exercise": doc["exercise"], "steps_file": steps_path.name, "pause_before": pause["before"],
                "front": pause["front"], "variables": doc["variables"], "tabs": tabs,
                "tab_hosts": [p.url.split("/")[2] for p in runner.take_pages if not p.is_closed()],
                "claude_files": sorted(runner.claude_files), "mouse": list(runner.mouse),
                "recorded_before": bool(first), "log_origin_epoch": log.origin_epoch, "take_hwnd": take_hwnd},
                indent=2), encoding="utf-8")
            print(f"PAUSED before {pause['before']}: {run_dir}\n  explore: python -m pipeline.generated.explore "
                  f"{run_dir} inventory\n  then write {run_dir / 'generated.json'} and run: python -m pipeline.s1 "
                  f"--resume={run_dir}")
            return 0
        print("recorded:", run_dir)
        if runner.claude_files:                    # a take with no codespace (Quick Sight) has no Claude sessions
            fetch_claude(run_dir, doc["variables"]["codespace_name"], runner.claude_files)
        report(run_dir)
        if failed:
            print("take stopped early:", failed)
            return 1
        return 0
    finally:
        if obs is not None:
            obs.restore()
        screen.restore(moved)                      # at the pause too: David has his windows while Claude explores
        if not keep:
            close_take_pages(ctx, before)


def resume(run_dir):
    """R70's second recording: the generated steps merged in and their draft lines voiced, the dashboard reloaded,
    then the rest of the take recorded in the same window and codespace, and the two recordings joined."""
    from pipeline.generated import merge
    from pipeline.generated.explore import settle
    from pipeline.narration.build import build
    from pipeline.post.join import join
    run_dir = Path(run_dir).resolve()
    pz = json.loads((run_dir / "pause.json").read_text(encoding="utf-8"))
    base = load_steps(EXERCISES / pz["exercise"] / pz["steps_file"])   # the dashboard's: STEPS_DIR, as before
    browser.use(base.get("browser", "workshop"))       # before anything connects (R113)
    gen_p = run_dir / "generated.json"
    doc = merge.merge(base, json.loads(gen_p.read_text(encoding="utf-8")) if gen_p.exists() else None, run_dir)
    doc["variables"] = {**doc["variables"], **{k: v for k, v in pz["variables"].items()
                                               if doc["variables"].get(k) == "@runtime"}}
    problems = merge.check(doc, pz["pause_before"])
    steps_path = merge.write(doc, run_dir)
    if problems:
        for p in problems:
            print("NOT READY", p)
        print(f"{len(problems)} problem(s) in {steps_path.name}; nothing recorded")
        return 1
    print("steps:", steps_path)
    build(steps_path)                              # the generated lines' drafts, so the take records enough under them
    ids = [s["id"] for s in doc["steps"]]
    rest = doc["steps"][ids.index(pz["pause_before"]):]
    ctx = cs.context()
    pages = [next(p for p in ctx.pages if p.url.split("/")[2:3] == [h]) for h in pz["tab_hosts"]]
    obs, failed, moved = None, None, []
    try:
        runner_pages = pages
        log = None
        page = next(p for p in pages if p.url == pz["tabs"][pz["front"]] or
                    p.url.split("/")[2] == pz["tabs"][pz["front"]].split("/")[2])
        page.bring_to_front()
        keep = pz.get("take_hwnd") or screen.window_titled(page.title())
        if keep is None:
            print("the take window isn't found on the capture monitor; nothing recorded (the take is still paused)")
            return 1
        moved = screen.clear(keep={keep})          # R89, as before the first recording; the take window stays
        if screen.park_pointer():
            print("pointer moved off the capture monitor")
        page.reload(wait_until="domcontentloaded")  # R70: the dashboard as it first opens, before recording resumes
        settle(page)
        page.evaluate("window.scrollTo(0, 0)")
        results = preflight.check(page)
        for ok, msg in results:
            print("PASS" if ok else "FAIL", msg)
        if not all(ok for ok, _ in results):
            print("pre-flight failed; nothing recorded (the take is still paused)")
            return 1
        obs = OBSCapture()
        obs.setup(run_dir / "raw")
        log = RunLog(run_dir / "runlog.jsonl", origin_epoch=pz["log_origin_epoch"])
        settings = json.loads((EXERCISES / doc["exercise"] / "edit_settings.json").read_text(encoding="utf-8"))
        runner = Runner(ctx, page, log, doc["variables"], narration_lengths(doc), settings["marks"], runner_pages,
                        doc.get("allow", []))
        runner.claude_files |= set(pz["claude_files"])
        vw = page.evaluate("[innerWidth, innerHeight]")   # the real mouse parks at the page's top edge, where nothing
        runner.mouse = (vw[0] / 2, 8.0)                    # hovers: the viewport's centre sat on a sparkline and its
        page.mouse.move(*runner.mouse)                     # tooltip stayed up for 45 s (full_take02); the join's
                                                           # dissolve covers the drawn cursor's jump
        obs.start()
        time.sleep(1.0)
        flash(page, log, "resume")
        time.sleep(1.0)
        failed = run_steps(runner, log, rest)
        time.sleep(0.5)
        flash(runner.page, log, "end")
        time.sleep(1.0)
        recorded = obs.stop()
        log.close()
        recorded.replace(run_dir / "raw" / "obs_b.mkv")
        obs.restore()
        obs = None
        print("recorded:", run_dir)
        if runner.claude_files:
            fetch_claude(run_dir, doc["variables"]["codespace_name"], runner.claude_files)
        print("join:", join(run_dir))
        report(run_dir)
        if failed:
            print("take stopped early:", failed)
            return 1
        return 0
    finally:
        if obs is not None:
            obs.restore()
        screen.restore(moved)
        for p in pages:
            try:
                p.close()
            except Exception:
                pass


# -- a rehearsal (--rehearse): every step off camera, nothing recorded ---------------------------------------------

READ_FIELD_JS = """() => {
  let e = document.activeElement;
  while (e && e.shadowRoot && e.shadowRoot.activeElement) e = e.shadowRoot.activeElement;
  if (!e || e === document.body || e === document.documentElement) return null;
  const tag = e.tagName.toLowerCase();
  if (tag === 'iframe' || tag === 'frame') return {tag};       // the focus is in a frame: read it there
  const out = {tag, id: e.id || null, label: e.getAttribute('aria-label') || e.getAttribute('placeholder') || null,
               automation_id: e.getAttribute('data-automation-id')};
  const cls = typeof e.className === 'string' ? e.className : '';
  if (tag === 'input' && (e.type || '').toLowerCase() === 'password')
    return {...out, value: null, unread: 'a password box'};
  if (/xterm-helper-textarea|inputarea|ace_text-input/.test(cls))
    return {...out, value: null, unread: 'a terminal or editor input'};
  if ((tag === 'input' || tag === 'textarea') && typeof e.value === 'string') return {...out, value: e.value};
  if (e.isContentEditable) return {...out, value: e.innerText};
  return {...out, value: null, unread: 'the focus is not on a text box'};
}"""
NO_BOX = ("nothing has the focus", "the focus is not on a text box")   # unread: the keys went to no text box


def _holds_focus(frame):
    try:
        return frame.frame_element().evaluate("e => e === e.ownerDocument.activeElement")
    except Exception:                                # a webview frame can detach while it reloads
        return False


def read_field(page):
    """The focused box (READ_FIELD_JS's record), followed down into nested frames (the Claude Code panel's
    webviews), or None when nothing has the focus."""
    fr = page.main_frame
    for _ in range(8):
        info = fr.evaluate(READ_FIELD_JS)
        if not info or info["tag"] not in ("iframe", "frame"):
            return info
        fr = next((ch for ch in fr.child_frames if _holds_focus(ch)), None)
        if fr is None:
            return None
    return None


def read_back(page, text):
    """What a type step typed against what its box holds now, whitespace aside: match; contains (the box held text
    already); differs (an autofill, a lost key); unread, with why (NO_BOX's whys: the keys went to no text box)."""
    try:
        info = read_field(page)
    except Exception as err:
        return {"status": "unread", "why": f"{type(err).__name__}: {str(err)[:120]}"}
    if info is None:
        return {"status": "unread", "why": "nothing has the focus"}
    field = {k: info[k] for k in ("tag", "id", "label", "automation_id") if info.get(k)}
    if info.get("value") is None:
        return {"status": "unread", "why": info.get("unread"), "field": field}
    got, want = " ".join(info["value"].split()), " ".join(text.split())
    status = "match" if got == want else "contains" if want and want in got else "differs"
    return {"status": status, "field": field, **({} if status == "match" else {"value": info["value"][:300]})}


class RehearsalRunner(Runner):
    """The take's Runner, with each typed box read back as the typing ends: before the step's submit key, which can
    close the box (so type_end is logged just before that key, not after it as in a take). All else is the take's."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.typed = {}                              # step id -> read_back's record

    def type_text(self, sid, a, ev):
        super().type_text(sid, {k: v for k, v in a.items() if k != "submit"}, ev)
        text = self.sub(a["text"])
        self.typed[sid] = {"chars": len(text), **read_back(self.page, text)}
        if a.get("submit"):
            self.page.keyboard.press(a["submit"])


def capture_still(path, page):
    """The capture monitor as OBS would record it (a Windows dialog included), or the page alone if the grab fails.
    Returns the path, or None."""
    from PIL import ImageGrab
    try:
        ImageGrab.grab(bbox=(CAPTURE_MONITOR_X, 0, CAPTURE_MONITOR_X + FRAME[0], FRAME[1]), all_screens=True).save(path)
        return path
    except Exception:
        pass
    try:
        page.screenshot(path=str(path), timeout=10000)
        return path
    except Exception:
        return None


def new_rehearse_dir(prefix):
    stem = f"{prefix}_{date.today():%Y%m%d}_"
    n = 1 + max([int(p.name[len(stem):]) for p in REHEARSE.glob(stem + "*") if p.name[len(stem):].isdigit()],
                default=0)
    d = REHEARSE / f"{stem}{n:02d}"
    (d / "stills").mkdir(parents=True)
    return d


def rehearsal_steps(doc, to=None):
    """The steps a rehearsal walks: those before a `pause` (the steps after it are generated after the explore,
    R70), through `to`. Returns (steps, None), or (None, why not)."""
    steps, pause = doc["steps"], doc.get("pause")
    if pause:
        steps = steps[:[s["id"] for s in steps].index(pause["before"])]
    ids = [s["id"] for s in steps]
    if to is not None:
        if to not in ids:
            return None, f"--to={to}: no such step" + (f" before the pause at {pause['before']}" if pause else "")
        steps = steps[:ids.index(to) + 1]
    if not steps:
        return None, f"no steps before the pause at {pause['before']}"
    return steps, None


NOT_MEASURED = {"fail": "the step failed", "skipped": "the step was skipped (its only_if)",
                "not_run": "the step didn't run (an earlier one failed)"}


def _mark_record(step, i, mk, evs, result):
    """One mark: where its box comes from and, for a box the page gives, whether this rehearsal measured it."""
    t = mk["target"]
    rec = {"mark": i, "kind": mk["kind"], "at_word": mk.get("at_word")}
    if "locator" in t:
        rec.update(source="locator", locator=t["locator"])
    elif t.get("of") in ("action", "subject"):
        rec["source"] = t["of"]
    else:                                            # boxes the edit finds or is given: nothing to measure here
        rec["source"] = ("box" if t.get("box") else "overlay" if t.get("overlay") else
                         "ocr (browser chrome)" if t.get("chrome") else "ocr" if t.get("match") else "unknown")
        rec.update(measured=None, why="found or given in the edit, not measured in the page")
        return rec
    fallback = "ocr match" if t.get("match") else "fixed box" if t.get("box") else None
    if fallback:
        rec["fallback"] = fallback
    if result == "line_only":
        return {**rec, "measured": False, "why": "a line-only step (after): the runner measures nothing for it"}
    if result != "ok":
        return {**rec, "measured": None, "why": NOT_MEASURED[result]}
    if rec["source"] == "action":                    # the click's own box, as plan.py reads it
        box = next((e["target_css_box"] for e in evs if e["phase"] == "action" and e.get("target_css_box")), None)
        return {**rec, "measured": bool(box), "box": box, **({} if box else {
            "why": "the action logged no box (only a click, hover, type, drag or OS click does)"})}
    if rec["source"] == "subject":
        box = next((e["target_css_box"] for e in evs if e["phase"] == "text_box" and e.get("target_css_box")
                    and (e.get("detail") or {}).get("role") == "subject"), None)
        return {**rec, "measured": bool(box), "box": box,
                **({} if box else {"why": "the step's only_if found no visible subject"})}
    tb = [e for e in evs if e["phase"] == "text_box" and (e.get("detail") or {}).get("mark") == i]
    err = [e["detail"] for e in evs if e["phase"] == "error" and str(e.get("detail") or "").startswith(f"mark {i}:")]
    if tb and tb[-1]["result"] == "ok":
        return {**rec, "measured": True, "box": tb[-1]["target_css_box"]}
    why = (f"the locator threw ({err[-1]}): mark locators must be plain CSS (GOTCHAS 397)" if err else
           "no visible match once the step had settled" if tb else
           f"not measured: its tab ({t.get('tab')}) wasn't the one in front")
    return {**rec, "measured": False, "why": why}


def _first_t(evs, phase):
    return next((e["t_mono"] for e in evs if e["phase"] == phase), None)


def rehearsal_report(doc, steps_path, steps, log_path, runner, failed, stills, fast, to):
    """rehearse.json: what needs fixing first (a failed step, unmeasured marks, typed boxes that don't hold what was
    typed, slow expects), then every step's record."""
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    by_step = {}
    for e in events:
        if e["record"] == "event":
            by_step.setdefault(e["step_id"], []).append(e)
    failed_id = failed.split(": ", 1)[0] if failed else None
    records = []
    for step in steps:
        sid, evs = step["id"], by_step.get(step["id"], [])
        phases = {e["phase"] for e in evs}
        result = ("line_only" if step.get("after") else "skipped" if "step_skipped" in phases else
                  "fail" if sid == failed_id else "ok" if "step_end" in phases else "not_run")
        t_act, t_met, t0 = (_first_t(evs, ph) for ph in ("action", "expect_met", "step_start"))
        e = step["expect"]
        rec = {"id": sid, "part": step.get("part"), "action": step["action"]["type"], "result": result}
        if result == "fail":
            rec["error"] = failed
        if t0 is not None:
            rec["t_start"] = t0
            rec["duration_s"] = round(max(x["t_mono"] for x in evs) - t0, 2)
        if result in ("ok", "fail") and e["kind"] != "none":
            rec["expect"] = {"kind": e["kind"], "timeout_s": e.get("timeout_s", 15),
                             "wait_s": round(t_met - t_act, 2) if t_met is not None and t_act is not None else None}
        if any(x["phase"] == "error" and x["result"] == "timeout" for x in evs):
            rec["retried"] = True                    # on_fail retry_once: the expect was met after a reload
        if step.get("marks"):
            rec["marks"] = [_mark_record(step, i, mk, evs, result) for i, mk in enumerate(step["marks"])]
        if sid in runner.typed:
            rec["typed"] = runner.typed[sid]
        if stills.get(sid):
            rec["still"] = stills[sid].relative_to(log_path.parent).as_posix()
        records.append(rec)
    unmeasured = [{"step": r["id"], **m} for r in records for m in r.get("marks", []) if m["measured"] is False]
    typed_bad = [{"step": r["id"], **r["typed"]} for r in records if "typed" in r and
                 (r["typed"]["status"] in ("differs", "contains") or r["typed"].get("why") in NO_BOX)]
    slow = [{"step": r["id"], **r["expect"]} for r in records if (r.get("expect") or {}).get("wait_s") is not None
            and r["expect"]["wait_s"] >= SLOW_EXPECT * r["expect"]["timeout_s"]]
    counts = {k: sum(r["result"] == k for r in records) for k in ("ok", "skipped", "line_only", "fail", "not_run")}
    return {
        "ok": not failed and not typed_bad,
        "failed": failed,
        "unmeasured_marks": unmeasured,
        "typed_problems": typed_bad,
        "slow_expects": slow,
        "counts": {"walked": len(steps), "in_file": len(doc["steps"]), **counts},
        "steps_file": steps_path.relative_to(EXERCISES.parent).as_posix()
        if steps_path.is_relative_to(EXERCISES.parent) else str(steps_path),
        "exercise": doc["exercise"],
        "to": to,
        "pause_before": (doc.get("pause") or {}).get("before"),
        "timing": "fast: the runner's defaults, no lines.json" if fast else "lines.json's lengths and mark times",
        "steps": records,
    }


def print_rehearsal(out, run_dir):
    c = out["counts"]
    print(f"rehearsed {c['walked']} of {c['in_file']} steps" + (f" (through {out['to']})" if out["to"] else "") +
          f": {c['ok']} ok, {c['skipped']} skipped, {c['line_only']} line-only, {c['fail']} failed, "
          f"{c['not_run']} not run")
    for m in out["unmeasured_marks"]:
        print(f"UNMEASURED {m['step']} mark {m['mark']} ({m['kind']} on {m['at_word']!r}"
              f"{', falls back to its ' + m['fallback'] if m.get('fallback') else ''}): {m['why']}")
    for t in out["typed_problems"]:
        if t["status"] == "unread":
            print(f"TYPED {t['step']}: the keys went to no text box ({t['why']})")
        else:
            print(f"TYPED {t['step']}: the box {'holds more than' if t['status'] == 'contains' else 'differs from'} "
                  f"what was typed: {t['value'][:80]!r}")
    for s in out["slow_expects"]:
        print(f"SLOW EXPECT {s['step']}: {s['kind']} took {s['wait_s']} s of its {s['timeout_s']} s")
    if out["failed"]:
        print("rehearsal stopped:", out["failed"])
    print(f"rehearsal: {run_dir} (rehearse.json, runlog.jsonl, stills/)")
    print("anything the steps made stays in the account (CREATE_A_VIDEO stage 5: clean it before the take)")


def rehearse(steps_name, to=None, fast=False):
    """Every step of a take, off camera (CREATE_A_VIDEO stage 5): the monitor cleared, the take's own window
    maximized on the capture monitor (so every box is the take's), pre-flight, the prepare, then the steps through
    the take's Runner. No OBS object is made, no flash shown, no report built."""
    steps_path = steps_file(steps_name)
    doc = load_steps(steps_path)
    prof = browser.use(doc.get("browser", "workshop"))   # before anything connects (R113)
    steps, why = rehearsal_steps(doc, to)
    if why:
        print(why + "; nothing rehearsed")
        return 1
    if not_built(steps):
        return 1
    settings_path = EXERCISES / doc["exercise"] / "edit_settings.json"
    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    elif fast:                                       # before the exercise's files are written: no live marks drawn
        settings = {}
    else:
        print(f"{settings_path} is missing (its marks style the live marks): write the exercise's files first "
              "(CREATE_A_VIDEO stage 3), or rehearse with --fast; nothing rehearsed")
        return 1
    ctx = cs.context()
    before = list(ctx.pages)                         # David's tabs; everything opened after this is the rehearsal's
    moved = clear_screen()
    try:
        took = open_take(ctx, doc, prof)
        if took is None:
            return 1
        page, take_pages, _ = took
        run_dir = new_rehearse_dir(doc.get("run_prefix", "dashboard"))
        metrics, _ = computed_geometry(page)
        log = RunLog(run_dir / "runlog.jsonl")
        log_header(log, run_dir, doc, steps_path, ctx, metrics, [], {})   # no captures: nothing is recorded
        runner = RehearsalRunner(ctx, page, log, doc["variables"], {} if fast else narration_lengths(doc),
                                 settings.get("marks", {}), take_pages, doc.get("allow", []))
        stills = {}

        def still(step):                             # the step's picture, unless it did nothing on screen
            if not step.get("after") and runner.decided.get(step["id"]) is not False:
                stills[step["id"]] = capture_still(run_dir / "stills" / f"{step['id']}.png", runner.page)

        failed = run_steps(runner, log, steps, after_step=still)
        log.close()
        out = rehearsal_report(doc, steps_path, steps, run_dir / "runlog.jsonl", runner, failed, stills, fast, to)
        (run_dir / "rehearse.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print_rehearsal(out, run_dir)
        return 0 if out["ok"] else 1
    finally:
        screen.restore(moved)
        close_take_pages(ctx, before)


def cli(args):
    steps = next((a.split("=", 1)[1] for a in args if a.startswith("--steps=")), "steps_s1.json")
    resumed = next((a.split("=", 1)[1] for a in args if a.startswith("--resume=")), None)
    if "--rehearse" in args:
        if resumed or "--dry" in args:
            print("--rehearse goes alone: not with --dry or --resume")
            return 2
        to = next((a.split("=", 1)[1] for a in args if a.startswith("--to=")), None)
        return rehearse(steps, to=to, fast="--fast" in args)
    if "--fast" in args or any(a.startswith("--to=") for a in args):
        print("--to and --fast go with --rehearse; nothing recorded")
        return 2
    return resume(resumed) if resumed else main(dry="--dry" in args, steps_name=steps)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")   # page titles can hold characters the console code page lacks
    sys.exit(cli(sys.argv[1:]))
