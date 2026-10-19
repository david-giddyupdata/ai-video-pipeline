"""Pre-flight checks for a take (SPEC §9), the subset slice S1 needs. Any failure blocks the run.

    python -m pipeline.preflight
"""
import ctypes
import json
import sys
from pathlib import Path

import win32api
import win32con
import win32gui
import win32process

from pipeline.config import CAPTURE_MONITOR_X, FRAME

# Toolbar buttons hidden in the workshop profile (David, 2026-10-06). Edge stores them in the profile's Preferences.
HIDDEN_TOOLBAR = {"browser.show_discover_toolbar_button": "Copilot", "browser.show_toolbar_bookmarks_button": "Favorites"}


def capture_monitor():
    for hmon, _, _ in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(hmon)
        if info["Monitor"][0] == CAPTURE_MONITOR_X and info["Monitor"][1] == 0:
            return info
    raise RuntimeError(f"no monitor at x={CAPTURE_MONITOR_X}")


def _cloaked(hwnd):
    val = ctypes.c_int(0)
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(val), ctypes.sizeof(val))   # DWMWA_CLOAKED
    return val.value != 0


def _exe(hwnd):
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        h = win32api.OpenProcess(0x1000, False, pid)                  # PROCESS_QUERY_LIMITED_INFORMATION
        return win32process.GetModuleFileNameEx(h, 0).rsplit("\\", 1)[-1].lower()
    except Exception:
        return "?"


def top_window_on(rect):
    """First visible top-level window, in z-order, that covers a real part of the capture monitor."""
    found = []

    def cb(hwnd, _):
        if found or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd) or _cloaked(hwnd):
            return True
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex & win32con.WS_EX_TRANSPARENT and ex & win32con.WS_EX_LAYERED:
            return True                                                # click-through overlays draw nothing
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        w, h = min(r, rect[2]) - max(l, rect[0]), min(b, rect[3]) - max(t, rect[1])
        if w > 200 and h > 200:
            found.append((hwnd, win32gui.GetWindowText(hwnd), win32gui.GetClassName(hwnd), _exe(hwnd), (l, t, r, b)))
        return True

    win32gui.EnumWindows(cb, None)
    return found[0] if found else None


def toolbar_hidden(page):
    """The Copilot and Favorites buttons are off in the recording profile (read from its Preferences file)."""
    out = []
    tmp = page.context.new_page()
    try:
        tmp.goto("edge://version", wait_until="domcontentloaded")
        line = next(l for l in tmp.inner_text("body").splitlines() if l.startswith("Profile path"))
    finally:
        tmp.close()
    prefs = json.loads((Path(line.split("	", 1)[1].strip()) / "Preferences").read_text(encoding="utf-8"))
    for key, name in HIDDEN_TOOLBAR.items():
        node = prefs
        for part in key.split("."):
            node = node.get(part, {}) if isinstance(node, dict) else {}
        out.append((node is False, f"{name} toolbar button hidden ({key} = {node if node != {} else 'unset'})"))
    return out


def check(page=None):
    """Returns a list of (ok, message). Pass the recording page to also check the Edge window bounds."""
    out = []
    mon = capture_monitor()
    m, w = mon["Monitor"], mon["Work"]
    size = (m[2] - m[0], m[3] - m[1])
    out.append((size == FRAME, f"capture monitor {size[0]}x{size[1]} (need {FRAME[0]}x{FRAME[1]})"))
    out.append((w == m, f"no taskbar on the capture monitor (work area {w} vs bounds {m})"))
    x, y = win32api.GetCursorPos()                     # R15: OBS's capture_cursor off doesn't keep it out (a hand at
    out.append((not (m[0] <= x < m[2] and m[1] <= y < m[3]),   # the right edge in p5_take01/02, 2026-10-07)
                f"real pointer off the capture monitor (at {x}, {y})"))
    top = top_window_on(m)
    ok = bool(top) and top[3] == "msedge.exe"
    out.append((ok, f"topmost window on the capture monitor: {top[3] if top else None} '{(top[1] if top else '')[:60]}'"))
    if page is not None:
        cdp = page.context.new_cdp_session(page)
        b = cdp.send("Browser.getWindowForTarget")["bounds"]
        out.append((b.get("windowState") == "maximized" and b["left"] - m[0] == -8 and b["width"] == FRAME[0] + 16,
                    f"Edge maximized on the capture monitor ({b})"))
        z = page.evaluate("[devicePixelRatio, Math.round(outerWidth / innerWidth * 100)]")
        out.append((z[0] == 1, f"browser zoom 100% for S1 (devicePixelRatio {z[0]})"))
        out += toolbar_hidden(page)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")   # page titles can hold characters the console code page lacks
    from pipeline.vendor import cs
    results = check(cs.page("github.com"))
    for ok, msg in results:
        print("PASS" if ok else "FAIL", msg)
    sys.exit(0 if all(ok for ok, _ in results) else 1)
