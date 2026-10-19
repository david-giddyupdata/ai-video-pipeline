"""The off-camera exploration of Part 5 (R70): Claude looks at this take's dashboard while nothing records, and picks
the interactions and the defect (or the improvement, R71) that the generated steps show.

    python -m pipeline.generated.explore runs/<run_id> inventory          # controls, boxes, screenshots
    python -m pipeline.generated.explore runs/<run_id> try '<json>'       # one interaction, then a screenshot
    python -m pipeline.generated.explore runs/<run_id> shot [name]        # the viewport as it is now
    python -m pipeline.generated.explore runs/<run_id> reload             # back to the dashboard's first state

An interaction is the same target a step uses: {"locator": "#p-12"} or {"locator": "#bar .point path", "nth": 3},
with an optional {"point": {"x": 0.5, "y": 0.5}} and {"scroll": true} to bring it into view first. A dropdown is two
clicks. Each try waits for Dash's callbacks to settle and writes explore/try_<n>.png and a line in explore/log.jsonl
(what changed: titles, labels, the selection chip, the graphs' trace counts), which Claude reads to write
generated.json (pipeline.generated.merge).

Works on the take's own dashboard tab (the take is paused, pipeline.s1); before a take exists, on a window of its own
at the take's size on the capture monitor, so boxes and screenshots match what the camera will see.
"""
import json
import sys
import time
from pathlib import Path

from pipeline.config import CAPTURE_MONITOR_X, RUNS
from pipeline.vendor import cs

INVENTORY_JS = """() => {
  const box = el => { const r = el.getBoundingClientRect();
    return {x: Math.round(r.x), y: Math.round(r.y + scrollY), w: Math.round(r.width), h: Math.round(r.height)}; };
  const text = el => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 120);
  const out = {viewport: {w: innerWidth, h: innerHeight}, page_h: document.documentElement.scrollHeight,
               title: document.title, controls: [], graphs: [], headings: []};
  for (const el of document.querySelectorAll('button, .dash-dropdown, .Select, .rc-slider, input[type=checkbox], '
                                             + 'input[type=radio], input[type=number], .dash-table-container')) {
    const lab = el.closest('label');
    out.controls.push({tag: el.tagName.toLowerCase(), id: el.id || el.closest('[id]')?.id || null,
                       cls: (el.className && el.className.baseVal === undefined ? el.className : '').slice(0, 60),
                       text: text(lab || el), checked: el.checked ?? null, box: box(lab || el)});
  }
  for (const g of document.querySelectorAll('.js-plotly-plot')) {
    const id = g.closest('[id]')?.id || g.id;
    const data = (g.data || []).map(t => ({type: t.type, name: t.name || null, n: (t.x || t.lat || t.z || []).length}));
    const kinds = ['.bars .point', '.scattergeo .point', '.scatterlayer .point', '.heatmaplayer'].map(s =>
      [s, g.querySelectorAll(s).length]).filter(k => k[1]);
    out.graphs.push({id, box: box(g), traces: data, points: Object.fromEntries(kinds),
                     annotations: [...g.querySelectorAll('.annotation-text')].map(text).slice(0, 12)});
  }
  for (const h of document.querySelectorAll('h1, h3, .flab, .kpi, .chip, #range-label, #scope-note'))
    out.headings.push({id: h.id || null, text: text(h), box: box(h)});
  return out;
}"""

SETTLE_JS = """() => !document.querySelector('[data-dash-is-loading="true"], ._dash-loading')"""

STATE_JS = """() => {
  const t = s => [...document.querySelectorAll(s)].map(e => (e.innerText || '').trim().replace(/\\s+/g, ' '));
  return {titles: t('h3'), range: t('#range-label'), scope: t('#scope-note'), kpis: t('.kpi'),
          graphs: [...document.querySelectorAll('.js-plotly-plot')].map(g => ({id: g.closest('[id]')?.id,
            traces: (g.data || []).map(tr => (tr.x || tr.lat || tr.z || []).length)})),
          errors: t('.dash-fe-error__title, .dash-debug-alert')};
}"""


def dashboard_url(run_dir):
    pause = Path(run_dir) / "pause.json"
    if pause.exists():
        return json.loads(pause.read_text(encoding="utf-8"))["tabs"]["dashboard"]
    header = json.loads((Path(run_dir) / "runlog.jsonl").read_text(encoding="utf-8").splitlines()[0])
    return f"https://{header['variables']['codespace_name']}-8050.app.github.dev/"


def own_window(ctx, url):
    """A window of the take's size on the capture monitor, for exploring before a take exists."""
    cdp = ctx.browser.new_browser_cdp_session()
    with ctx.expect_page(timeout=15000) as info:
        cdp.send("Target.createTarget", {"url": url, "newWindow": True})
    page = info.value
    s = page.context.new_cdp_session(page)
    win = s.send("Browser.getWindowForTarget")["windowId"]
    s.send("Browser.setWindowBounds", {"windowId": win, "bounds": {"windowState": "normal"}})
    s.send("Browser.setWindowBounds", {"windowId": win, "bounds": {"left": CAPTURE_MONITOR_X + 40, "top": 40,
                                                                   "width": 1600, "height": 900}})
    s.send("Browser.setWindowBounds", {"windowId": win, "bounds": {"windowState": "maximized"}})
    return page


def dashboard_page(run_dir, open_if_missing=True):
    url = dashboard_url(run_dir)
    host = url.split("/")[2]
    ctx = cs.context()
    page = next((p for p in ctx.pages if p.url.split("/")[2:3] == [host]), None)
    if page is None and open_if_missing:
        page = own_window(ctx, url)
    page.bring_to_front()
    settle(page)
    return page


def settle(page, timeout_s=30, quiet_s=1.2):
    """Until Dash has no callback running and the page's state (titles, labels, the graphs' data) has stopped
    changing for quiet_s: a click can chain callbacks (a bar click sets the selection, which redraws everything) with
    a moment between them when nothing is marked loading."""
    end = time.time() + timeout_s
    page.wait_for_load_state("domcontentloaded")
    last, since = None, time.time()
    while time.time() < end:
        try:
            now = json.dumps(page.evaluate(STATE_JS)) if page.locator(".js-plotly-plot").count() else None
            busy = not page.evaluate(SETTLE_JS)
        except Exception:
            now, busy = None, True
        if now != last or busy or now is None:
            last, since = now, time.time()
        elif time.time() - since >= quiet_s:
            break
        page.wait_for_timeout(200)
    page.wait_for_timeout(300)


def out_dir(run_dir):
    d = Path(run_dir) / "explore"
    d.mkdir(exist_ok=True)
    return d


def log(run_dir, rec):
    with open(out_dir(run_dir) / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def inventory(run_dir):
    page = dashboard_page(run_dir)
    page.evaluate("window.scrollTo(0, 0)")
    inv = page.evaluate(INVENTORY_JS)
    d = out_dir(run_dir)
    (d / "inventory.json").write_text(json.dumps(inv, indent=1, ensure_ascii=False), encoding="utf-8")
    page.screenshot(path=str(d / "viewport.png"))
    page.screenshot(path=str(d / "full_page.png"), full_page=True)
    print(f"viewport {inv['viewport']}, page height {inv['page_h']}; {len(inv['controls'])} controls, "
          f"{len(inv['graphs'])} graphs -> {d}")
    for g in inv["graphs"]:
        print(f"  graph #{g['id']} at y {g['box']['y']} h {g['box']['h']}: {g['traces']} {g['points']}")
    return inv


def try_action(run_dir, spec):
    page = dashboard_page(run_dir)
    before = page.evaluate(STATE_JS)
    loc = page.locator(spec["locator"]).nth(spec.get("nth", 0))
    if spec.get("scroll"):
        loc.scroll_into_view_if_needed()
    box = loc.bounding_box()
    if box is None:
        raise RuntimeError(f"not visible: {spec['locator']}")
    p = spec.get("point") or {}
    x, y = box["x"] + box["width"] * p.get("x", 0.5), box["y"] + box["height"] * p.get("y", 0.5)
    page.mouse.move(x, y)
    page.wait_for_timeout(300)
    t0 = time.time()
    page.mouse.click(x, y)
    settle(page)
    after = page.evaluate(STATE_JS)
    n = len(list(out_dir(run_dir).glob("try_*.png"))) + 1
    png = out_dir(run_dir) / f"try_{n:02d}.png"
    page.screenshot(path=str(png))
    changed = {k: after[k] for k in after if after[k] != before[k]}
    rec = {"n": n, "spec": spec, "box_css": {k: round(v, 1) for k, v in box.items()}, "settle_s": round(time.time() - t0, 2),
           "scroll_y": page.evaluate("scrollY"), "changed": changed, "png": png.name}
    log(run_dir, rec)
    print(json.dumps(rec, indent=1, ensure_ascii=False))
    return rec


def shot(run_dir, name="shot"):
    page = dashboard_page(run_dir)
    png = out_dir(run_dir) / f"{name}.png"
    page.screenshot(path=str(png))
    print(png)


def reload(run_dir):
    page = dashboard_page(run_dir)
    page.reload(wait_until="domcontentloaded")
    settle(page)
    page.evaluate("window.scrollTo(0, 0)")
    print("reloaded", page.url)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    run, cmd, *rest = sys.argv[1:]
    run = Path(run) if Path(run).is_absolute() or Path(run).exists() else RUNS / run
    if cmd == "inventory":
        inventory(run)
    elif cmd == "try":
        try_action(run, json.loads(rest[0]))
    elif cmd == "shot":
        shot(run, *(rest[:1]))
    elif cmd == "reload":
        reload(run)
    else:
        sys.exit(f"unknown command {cmd!r}")
