"""The pipeline's line into a running Premiere Pro (R102): ExtendScript sent to the AIDV panel's localhost bridge.

The panel (pipeline/edit/ppro/panel, CEP) is linked into Premiere's extensions folder by `install`, and its hidden
bridge starts with Premiere. Each start writes the port and a fresh token to ~/.giddyup/ppro_bridge.json; a call posts
ExtendScript there and gets back aidvRun's JSON. Premiere's ExtendScript runs one call at a time on its main thread.

    python -m pipeline.edit.ppro.bridge install          # link the panel; check the unsigned-panel flag
    python -m pipeline.edit.ppro.bridge ping             # Premiere's version and open project, or why not
    python -m pipeline.edit.ppro.bridge eval "<code>"    # run ExtendScript, print the result
    python -m pipeline.edit.ppro.bridge start [<project.prproj>]   # start Premiere (opening a project) and wait
    python -m pipeline.edit.ppro.bridge quit             # quit Premiere, only if no project is open

CEP panels are deprecated in favour of UXP, but UXP can't yet read or set a graphic's Source Text (GOTCHAS), which the
caption titles need; Premiere 26.3 still runs CEP and ExtendScript.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PANEL = Path(__file__).resolve().parent / "panel"
EXT_DIR = Path(os.environ.get("APPDATA", "")) / "Adobe" / "CEP" / "extensions" / "com.giddyup.aidv"
INFO = Path.home() / ".giddyup" / "ppro_bridge.json"
PPRO_EXE = Path(r"C:\Program Files\Adobe\Adobe Premiere Pro 2026\Adobe Premiere Pro.exe")
CSXS_KEY = r"Software\Adobe\CSXS.12"            # CEP 12, Premiere 2026


class BridgeError(RuntimeError):
    pass


def install():
    """Link the panel into the user's CEP extensions folder (a junction, so edits here are live after a panel
    reload) and report the unsigned-panel flag. Returns a list of what is wrong, empty when ready."""
    problems = []
    if not EXT_DIR.exists():
        EXT_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cmd", "/c", "mklink", "/J", str(EXT_DIR), str(PANEL)], check=True, capture_output=True)
    elif EXT_DIR.resolve() != PANEL.resolve():
        problems.append(f"{EXT_DIR} exists and isn't a link to {PANEL}")
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CSXS_KEY) as k:
            flag = winreg.QueryValueEx(k, "PlayerDebugMode")[0]
    except OSError:
        flag = None
    if str(flag) != "1":
        problems.append(f"HKCU\\{CSXS_KEY} PlayerDebugMode is {flag!r}; unsigned panels need \"1\"")
    return problems


def _alive(pid):
    """Whether a process with this id runs (the bridge file names the panel's process)."""
    if not pid:
        return False
    out = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], capture_output=True, text=True).stdout
    return str(int(pid)) in out


def premiere_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Adobe Premiere Pro.exe", "/NH"], capture_output=True,
                         text=True).stdout
    return "Adobe Premiere Pro.exe" in out


def call(code, timeout=120, reload=False):
    """Run ExtendScript in Premiere; returns its result (JSON-decoded). Raises BridgeError. `reload` loads aidv.jsx
    again first (after an edit to it)."""
    if not INFO.exists():
        raise BridgeError("no bridge info: is Premiere running with the AIDV panel installed?")
    try:
        info = json.loads(INFO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:      # caught mid-write by a starting bridge
        raise BridgeError(f"bridge info unreadable ({e}); try again") from e
    body = json.dumps({"code": code, "reload": reload}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{info['port']}/", data=body,
                                 headers={"x-aidv-token": info["token"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        why = ("a stale bridge file (its process has gone); restart Premiere" if not _alive(info.get("pid"))
               else "is Premiere busy, or showing a dialog? A call that timed out still runs once Premiere is free")
        raise BridgeError(f"bridge not answering ({e}): {why}") from e
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        raise BridgeError(f"not JSON from Premiere: {raw[:300]}")   # e.g. "EvalScript error." (aidv.jsx not loaded)
    if not out.get("ok"):
        raise BridgeError(f"ExtendScript error: {out.get('error')} (line {out.get('line')})")
    return out.get("result")


def ping():
    return call("({version: app.version, build: app.build, project: app.project ? app.project.path : null, "
                "sequence: app.project && app.project.activeSequence ? app.project.activeSequence.name : null})",
                timeout=10)


def quit_premiere():
    """Quit Premiere only when no project is open: one open may be David's, with unsaved work (2026-10-13: Claude
    quit Premiere with his review copy open). Returns what stopped it, or None once it quits."""
    open_now = call("(function () { var o = []; for (var k = 0; k < app.projects.numProjects; k++) "
                    "{ o.push(app.projects[k].path); } return o; })()", timeout=30)
    if open_now:
        return f"not quitting: open in Premiere: {open_now}"
    call("(function () { app.quit(); return true; })()", timeout=30)
    return None


def start(project=None, wait_s=240):
    """Start Premiere (opening `project`, if given) unless it runs, and wait until the bridge answers."""
    if not premiere_running():
        if INFO.exists():
            INFO.unlink()                                   # stale from the last session
        # Premiere can't find a project given with forward slashes ("This file path does not exist", a modal dialog)
        subprocess.Popen([str(PPRO_EXE)] + ([str(Path(project).resolve())] if project else []))
    t0 = time.time()
    while time.time() - t0 < wait_s:
        try:
            return ping()
        except BridgeError:
            time.sleep(3)
    raise BridgeError(f"Premiere's bridge didn't answer within {wait_s} s")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install")
    sub.add_parser("ping")
    e = sub.add_parser("eval")
    e.add_argument("code")
    s = sub.add_parser("start")
    s.add_argument("project", nargs="?")
    sub.add_parser("quit")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "install":
            problems = install()
            print("\n".join(problems) or f"installed: {EXT_DIR} -> {PANEL}")
            return 1 if problems else 0
        result = {"ping": ping, "eval": lambda: call(a.code), "start": lambda: start(a.project),
                  "quit": quit_premiere}[a.cmd]()
        print(json.dumps(result, indent=1, ensure_ascii=False))
    except BridgeError as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
