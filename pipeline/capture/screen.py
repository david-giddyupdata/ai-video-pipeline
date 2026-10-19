"""R89: the capture monitor is cleared of other windows before a take and given back after it.

    python -m pipeline.capture.screen            # list what covers the capture monitor (moves nothing)
    python -m pipeline.capture.screen clear      # move it off and park the pointer; the moves go to MOVED_FILE
    python -m pipeline.capture.screen restore    # put back whatever MOVED_FILE lists

A new take window doesn't come above other apps' windows (Windows keeps the foreground app on top), and an Edge window
of David's own passes pre-flight's topmost check yet could cover the take (GOTCHAS, Part 5). So every visible window
that covers a real part of the capture monitor moves to the leftmost other monitor, keeping its place and state
(a maximized window stays maximized there), and goes back after the take. The real pointer, if it is on the capture
monitor, moves to the centre of the primary monitor (R15); it is not moved back.

The moves are also written to MOVED_FILE, so a take that dies before its own restore can be undone by hand.
"""
import json
import sys

import win32api
import win32con
import win32gui

from pipeline.config import RUNS
from pipeline.preflight import _cloaked, _exe, capture_monitor

MIN_OVERLAP_PX = 200          # a maximized window on the next monitor overlaps the capture monitor by its 8 px border
MOVED_FILE = RUNS / "_moved_windows.json"
SKIP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


def _target_monitor(cap):
    """The leftmost monitor that isn't the capture monitor (David's left-hand one)."""
    others = [win32api.GetMonitorInfo(h)["Monitor"] for h, _, _ in win32api.EnumDisplayMonitors()]
    others = [m for m in others if m != cap]
    return min(others, key=lambda m: m[0])


def covering(keep=()):
    """Visible top-level windows that cover a real part of the capture monitor, in z-order."""
    cap = capture_monitor()["Monitor"]
    found = []

    def cb(hwnd, _):
        if hwnd in keep or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd) or _cloaked(hwnd):
            return True
        if win32gui.GetClassName(hwnd) in SKIP_CLASSES:
            return True
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex & win32con.WS_EX_TRANSPARENT and ex & win32con.WS_EX_LAYERED:
            return True                                                # click-through overlays draw nothing
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        if min(r, cap[2]) - max(l, cap[0]) > MIN_OVERLAP_PX and min(b, cap[3]) - max(t, cap[1]) > MIN_OVERLAP_PX:
            found.append({"hwnd": hwnd, "exe": _exe(hwnd), "title": win32gui.GetWindowText(hwnd)[:80]})
        return True

    win32gui.EnumWindows(cb, None)
    return found


def park_pointer():
    """R15: the real pointer off the capture monitor (to the primary's centre). Returns where it went, or None."""
    cap = capture_monitor()["Monitor"]
    x, y = win32api.GetCursorPos()
    if not (cap[0] <= x < cap[2] and cap[1] <= y < cap[3]):
        return None
    prim = next(win32api.GetMonitorInfo(h)["Monitor"] for h, _, _ in win32api.EnumDisplayMonitors()
                if win32api.GetMonitorInfo(h)["Flags"] & 1)
    to = ((prim[0] + prim[2]) // 2, (prim[1] + prim[3]) // 2)
    win32api.SetCursorPos(to)
    return to


def _place(hwnd, show, rect):
    """Move a window to rect in its normal state, then maximize it there if it was maximized: setting the placement of
    a maximized window only changes its restore rectangle, and it stays on its monitor (tested 2026-10-07)."""
    pl = win32gui.GetWindowPlacement(hwnd)
    win32gui.SetWindowPlacement(hwnd, (pl[0], win32con.SW_SHOWNOACTIVATE, pl[2], pl[3], rect))
    if show == win32con.SW_SHOWMAXIMIZED:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)


def clear(keep=()):
    """Move every covering window (except the hwnds in keep) to the target monitor; returns the moves for restore."""
    cap = capture_monitor()["Monitor"]
    tgt = _target_monitor(cap)
    dx, dy = tgt[0] - cap[0], tgt[1] - cap[1]
    moved = []
    for w in covering(keep):
        try:
            pl = win32gui.GetWindowPlacement(w["hwnd"])        # (flags, showCmd, minpos, maxpos, normal rect)
            l, t, r, b = pl[4]
            _place(w["hwnd"], pl[1], (l + dx, t + dy, r + dx, b + dy))
            moved.append({**w, "placement": [pl[0], pl[1], list(pl[2]), list(pl[3]), list(pl[4])]})
        except Exception as err:                                # an elevated window refuses (UIPI); pre-flight says so
            print(f"could not move {w['exe']} '{w['title']}': {err}")
    if moved:
        old = json.loads(MOVED_FILE.read_text(encoding="utf-8")) if MOVED_FILE.exists() else []
        MOVED_FILE.write_text(json.dumps(old + moved, indent=1), encoding="utf-8")
    return moved


def restore(moved=None):
    """Put the moved windows back where they were (a window that has since closed is skipped)."""
    if moved is None:
        moved = json.loads(MOVED_FILE.read_text(encoding="utf-8")) if MOVED_FILE.exists() else []
    back = 0
    for w in reversed(moved):
        if not win32gui.IsWindow(w["hwnd"]):
            continue
        p = w["placement"]
        try:
            _place(w["hwnd"], p[1], tuple(p[4]))
            back += 1
        except Exception as err:
            print(f"could not restore {w['exe']} '{w['title']}': {err}")
    hw = {w["hwnd"] for w in moved}
    if MOVED_FILE.exists():
        left = [w for w in json.loads(MOVED_FILE.read_text(encoding="utf-8")) if w["hwnd"] not in hw]
        if left:
            MOVED_FILE.write_text(json.dumps(left, indent=1), encoding="utf-8")
        else:
            MOVED_FILE.unlink()
    return back


def take_window():
    """The take's own Edge window: the msedge window on top of the capture monitor once it has been cleared."""
    on = covering()
    return next((w["hwnd"] for w in on if w["exe"] == "msedge.exe"), None)


def window_titled(title):
    """An Edge window on the capture monitor whose active tab has this title (its window title starts with it)."""
    return next((w["hwnd"] for w in covering() if w["exe"] == "msedge.exe" and w["title"].startswith(title[:40])), None)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "clear":
        for w in clear():
            print("moved", w["exe"], repr(w["title"]))
        print("pointer parked at", park_pointer())
    elif cmd == "restore":
        print("restored", restore())
    else:
        for w in covering():
            print(w["exe"], repr(w["title"]))
