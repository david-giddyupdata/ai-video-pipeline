"""Off-camera set-up before a take (steps.json `prepare`), run before OBS starts.

VS Code saves open editors and folder expansion inside the codespace, so a take inherits the last one's screen: the
data folder already open (a click would collapse it) and the CSV already showing. This opens the codespace in a tab of
its own, runs VS Code commands through the command palette, reloads to check the state stuck, and closes the tab.
A side effect: the codespace is running when the take opens it, so the load the edit cuts is short.
"""
COMMANDS = {
    "close_editors": "View: Close All Editors",
    "collapse_explorer": "View: Collapse Folders in Explorer",
}
TRUST_DIALOG = ".monaco-dialog-box:has-text('trust the authors')"
TRUST_WAIT_S = 12             # the trust question can come several seconds after the file tree (full take, 2026-10-08)
CLAUDE_TAB ='.part.auxiliarybar .composite-bar a[aria-label="Claude Code"]'
DATA_ROW =".explorer-folders-view .monaco-list-row[aria-label='data']"


def _ready(page):
    page.locator(DATA_ROW).first.wait_for(state="visible", timeout=180000)
    page.wait_for_timeout(3000)                     # extensions restore editors a moment after the tree appears


def _command(page, label):
    page.keyboard.press("F1")                       # Ctrl+Shift+P is Edge's InPrivate shortcut
    box = page.locator(".quick-input-widget input").first
    box.wait_for(state="visible", timeout=10000)
    box.fill(">" + label)
    page.locator(f".quick-input-list .monaco-list-row:has-text('{label.split(': ', 1)[-1]}')").first.wait_for(
        state="visible", timeout=10000)
    page.keyboard.press("Enter")
    page.wait_for_timeout(800)


def state(page):
    return page.evaluate(f"""() => ({{
      expanded: [...document.querySelectorAll(".explorer-folders-view .monaco-list-row[aria-expanded='true']")]
                  .map(r => r.getAttribute('aria-label')),
      editors: [...document.querySelectorAll('.tabs-container .tab')].map(t => t.getAttribute('aria-label')),
    }})""")


def _new_claude_session(page):
    """The panel reopens the last session (GOTCHAS): show its tab if it has one and click New session, so the take
    starts on an empty conversation. A codespace's first open has no Claude Code tab; the take opens it then."""
    tab = page.locator(CLAUDE_TAB).first
    if not (tab.count() and tab.is_visible()):
        return "no Claude Code tab yet"
    tab.click()
    for _ in range(30):
        page.wait_for_timeout(1000)
        for fr in page.frames[1:]:
            try:
                btn = fr.locator('button[aria-label="New session"]')
                if btn.count() and btn.first.is_visible():
                    btn.first.click()
                    page.wait_for_timeout(1500)
                    chat = page.locator('.part.auxiliarybar .composite-bar a[aria-label^="Chat"]').first
                    if chat.count() and chat.is_visible():    # the take opens on Chat and clicks Claude Code (p2.07a)
                        chat.click()
                        page.wait_for_timeout(1000)
                    return "new session"
            except Exception:
                continue
    raise RuntimeError("New session button not found in the Claude Code panel")


def prepare_ide(ctx, codespace_name, opts, tries=3):
    """Reset, reload, check; again if the state didn't hold (a codespace that has just started reopens README.md)."""
    todo = [label for key, label in COMMANDS.items() if opts.get(key)]
    if not todo:
        return None
    page = ctx.new_page()
    try:
        page.goto(f"https://github.com/codespaces/{codespace_name}", wait_until="domcontentloaded")
        _ready(page)
        for _ in range(TRUST_WAIT_S):                   # a codespace's first open: nothing to reset, and the trust
            if page.locator(TRUST_DIALOG).count():         # question is the take's own step (p1.04), so leave it
                return {"fresh": True}
            page.wait_for_timeout(1000)
        for attempt in range(1, tries + 1):
            # focus the workbench, not an editor: a preview editor is an iframe that keeps F1 to itself
            page.locator(".part.sidebar .composite.title").first.click()
            for label in todo:
                _command(page, label)
            _command(page, "Notifications: Clear All Notifications")
            page.wait_for_timeout(2000)             # let VS Code write its view state
            page.reload(wait_until="domcontentloaded")
            _ready(page)
            st = state(page)
            bad = (opts.get("collapse_explorer") and st["expanded"]) or (opts.get("close_editors") and st["editors"])
            print(f"  prepare attempt {attempt}: {st}", flush=True)
            if not bad:
                if opts.get("new_claude_session"):
                    st["claude"] = _new_claude_session(page)
                return st
        raise RuntimeError(f"IDE reset did not stick after {tries} tries: {st}")
    finally:
        page.close()


# -- a take that starts at Part 5 (a test take on an earlier take's codespace, R70) ----------------------------------
LINK_JS = """url => { const a = document.createElement('a'); a.href = url; a.target = '_blank'; a.textContent = 'open';
  Object.assign(a.style, {position: 'fixed', left: '0', top: '0', width: '60px', height: '30px', zIndex: '2147483647',
                          background: '#fff'}); a.id = '__aidv_link'; document.body.appendChild(a); }"""


def ensure_app(codespace, app):
    """The dashboard Part 4 leaves running: started off camera (setsid, so it outlives the ssh session) if its port
    doesn't answer. Claude stops it on camera in p5.16."""
    import subprocess
    from pipeline.vendor.claude_watch import _ssh
    check = f"import urllib.request\ntry:\n    print(urllib.request.urlopen('http://localhost:{app['port']}', timeout=5).status)\nexcept Exception as e:\n    print('down', e)\n"
    if (_ssh(codespace, check).stdout or "").strip().endswith("200"):
        return "running"
    env_cmd = ("cd /workspaces/* && (setsid nohup " + app["start"] + " > /tmp/aidv_app.log 2>&1 < /dev/null &) ; "
               "sleep 15; tail -3 /tmp/aidv_app.log")
    import os
    from pipeline.config import GH_DIR
    subprocess.run(["gh", "codespace", "ssh", "-c", codespace, "--", env_cmd], capture_output=True, text=True,
                   env=dict(os.environ, GH_CONFIG_DIR=str(GH_DIR)), timeout=180)
    if not (_ssh(codespace, check).stdout or "").strip().endswith("200"):
        raise RuntimeError(f"the app did not start on port {app['port']}")
    return "started"


def _open_session(page, title):
    """The Claude Code panel's session history (clock icon): open the session listed with this title."""
    for _ in range(20):
        fr = next((f for f in page.frames[1:] if f.locator('button[aria-label="Session history"]').count()), None)
        if fr:
            break
        page.wait_for_timeout(1000)
    else:
        raise RuntimeError("the Claude Code panel's Session history button was not found")
    fr.locator('button[aria-label="Session history"]').first.click()
    page.wait_for_timeout(1500)
    fr.locator(f'button[class*="sessionItem"]:has(span[class*="sessionName"]:text-is("{title}"))').first.click()
    page.wait_for_timeout(6000)                       # "Loading..." for a few seconds (GOTCHAS)
    banner = fr.locator('[class*="banner"] button')   # "Prefer the Terminal experience?" covers the panel's foot
    if banner.count():
        banner.first.click()


def open_tabs(page, tabs, variables, ide):
    """The take window as Parts 1 to 4 leave it: the first tab navigated, each later one opened from a link in the
    tab before it (a real click, so it lands to its right as the take's own clicks do). The IDE as p4.13 leaves it:
    the Explorer, the Claude Code panel on its last conversation, the Ports view. Returns the pages in strip order."""
    sub = lambda u: u.format(**variables)
    page.goto(sub(tabs[0]["url"]), wait_until="domcontentloaded")
    pages = [page]
    for t in tabs[1:]:
        opener = pages[-1]
        opener.evaluate(LINK_JS, sub(t["url"]))
        with opener.context.expect_page(timeout=30000) as info:
            opener.mouse.click(30, 15)
        new = info.value
        opener.evaluate("() => document.getElementById('__aidv_link')?.remove()")
        new.wait_for_load_state("domcontentloaded")
        pages.append(new)
        others = set(new.context.pages) - set(pages)
        if t["tab"] == "ide":
            new.locator(".monaco-workbench").first.wait_for(state="visible", timeout=180000)
            new.wait_for_timeout(8000)                  # extensions and the Claude Code panel settle
            new.locator(".part.sidebar .composite.title, .part.editor").first.click()
            if ide.get("show_explorer"):
                _command(new, "View: Show Explorer")
            if ide.get("ports_view"):
                _command(new, "Ports: Focus on Ports View")
            if ide.get("claude_tab"):
                tab = new.locator(CLAUDE_TAB).first
                if tab.count() and tab.is_visible():
                    tab.click()
                    new.wait_for_timeout(3000)
                if ide.get("claude_session"):           # a reconnect may open a fresh "Untitled" session (GOTCHAS)
                    _open_session(new, ide["claude_session"])
            if ide.get("close_editors"):               # a reconnect reopens the README preview, late (GOTCHAS)
                new.locator(".part.sidebar .composite.title").first.click()
                _command(new, "View: Close All Editors")
        else:
            new.wait_for_timeout(5000)
        for stray in set(new.context.pages) - set(pages) - others:   # Codespaces opens the forwarded port's page by
            stray.close()                                            # itself when the IDE connects (GOTCHAS)
        new.bring_to_front()
    return pages
