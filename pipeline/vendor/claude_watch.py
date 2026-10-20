"""Watching Claude Code during a live step: the panel's state, permission prompts, and the session log.

Copied 2026-10-07 from the workshop's automation folder (read-only, R1):
  <DOCUMENTS_DIR>\\Learning-David-Pc\\Workshops\\2026-10-08_<CLIENT>\\automation\\
    watch.py      state()                      unchanged
    autopilot.py  RISKY, prompt_text()         unchanged
    approve.py    the Yes button's name        as a locator string, so the runner clicks it through its logged path
    claude_log.py REMOTE, status()             GH_DIR from pipeline.config; status(file=) reads a named session file
    _work/teach/dashboard.py  wait_claude()'s reviewer test (sub_age, "I'll report back")  as waiting_on_reviewer()
Added: fetch_session() pulls a whole session JSONL for the post-run narration (SPEC §11). The workshop originals are
untouched. Everything here only reads: the gh connection runs a read-only script in the codespace.
"""
import json
import os
import re
import subprocess

from pipeline.config import GH_DIR

ATTENTION = ("Allow this", "Do you want to", "Esc to cancel")
YES_BUTTON = r"role=button[name=/^\s*1?\s*Yes\b/]"
# Public copy: <S3_BUCKET> below is a placeholder, so the s3 rm lookahead never matches a real bucket and every
# `s3 rm` counts as RISKY (stricter than the original). Put your own bucket back to allow its student- prefix.
RISKY = re.compile(
    r"git\s+push|datasets/|aws\s+iam|--profile|rm\s+-rf\s+/(?!workspaces|tmp/)|"
    r"s3\s+rm\s+s3://(?!<S3_BUCKET>/student-)|sudo|curl[^|]*\|\s*(ba)?sh",
    re.I,
)


def state(p):
    """'attention' if Claude is waiting on a permission/question, 'busy', or 'idle'."""
    html = ""
    for fr in p.frames:
        if fr == p.main_frame:
            continue  # VS Code's own notifications ("Do you want to install...") are not Claude prompts
        try:
            html += fr.content()
        except Exception:
            continue
    if any(a in html for a in ATTENTION):
        return "attention"
    if "Queue another message" in html or re.search(r">\s*[1-9]\d* agents?\s*<", html):
        return "busy"   # main loop running, or a background reviewer agent still working
    return "idle"


def prompt_text(p):
    for fr in p.frames:
        if fr == p.main_frame:
            continue  # only the Claude Code webview, not VS Code notifications
        try:
            t = fr.locator("body").inner_text()
        except Exception:
            continue
        i = t.find("Allow this")
        if i < 0:
            i = t.find("Do you want to")
        if i >= 0:
            j = t.find("Esc to cancel", i)
            return t[i:j if j > 0 else i + 3000]
    return ""


REMOTE = r'''
import glob, json, os, sys, time
want = sys.argv[1] if len(sys.argv) > 1 else ""
files = sorted(glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")), key=os.path.getmtime)
if want:
    files = [f for f in files if os.path.basename(f) == want] or files
if not files:
    print(json.dumps({"state": "none"})); raise SystemExit
f = files[-1]
recs = []
for line in open(f, encoding="utf-8", errors="replace"):
    try: recs.append(json.loads(line))
    except Exception: pass
msgs = [r for r in recs if r.get("type") in ("user", "assistant")]
last = msgs[-1] if msgs else {}
m = last.get("message", {}) or {}
content = m.get("content") if isinstance(m.get("content"), list) else []
kinds = [c.get("type") for c in content if isinstance(c, dict)]
tools, text = [], ""
for r in msgs:
    for c in (r.get("message", {}) or {}).get("content", []) if isinstance((r.get("message", {}) or {}).get("content"), list) else []:
        if isinstance(c, dict) and c.get("type") == "tool_use":
            inp = c.get("input", {})
            tools.append(c.get("name", "") + ":" + str(inp.get("file_path") or inp.get("command") or inp.get("description") or "")[:80])
        if isinstance(c, dict) and c.get("type") == "text" and r.get("type") == "assistant":
            text = c.get("text", "")
done = last.get("type") == "assistant" and m.get("stop_reason") == "end_turn" and "tool_use" not in kinds
subs = glob.glob(os.path.join(f[:-6], "subagents", "*.jsonl"))
sub_age = round(time.time() - max(os.path.getmtime(x) for x in subs)) if subs else 99999
print(json.dumps({"state": "done" if done else "working", "sub_age": sub_age, "age": round(time.time() - os.path.getmtime(f)),
                  "file": os.path.basename(f), "n": len(msgs), "tools": len(tools), "last_tool": tools[-1] if tools else "",
                  "last_kind": last.get("type", "") + ":" + ",".join(kinds), "text": text[-3000:]}))
'''

FETCH = r'''
import glob, os, sys
for f in glob.glob(os.path.expanduser("~/.claude/projects/*/" + sys.argv[1])):
    sys.stdout.write(open(f, encoding="utf-8", errors="replace").read())
'''


def _ssh(codespace, script, *args, timeout=90):
    env = dict(os.environ, GH_CONFIG_DIR=str(GH_DIR))
    return subprocess.run(["gh", "codespace", "ssh", "-c", codespace, "--", "python3", "-", *args], input=script,
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=timeout)


def status(codespace, file=""):
    try:
        r = _ssh(codespace, REMOTE, *([file] if file else []))
    except subprocess.TimeoutExpired:
        return {"state": "error", "err": "timeout"}
    out = (r.stdout or "").strip().splitlines()
    try:
        return json.loads(out[-1])
    except Exception:
        return {"state": "error", "err": (r.stderr or r.stdout)[-300:]}


def waiting_on_reviewer(s):
    """'Done' is not done while a background reviewer runs (workshop lesson)."""
    return s.get("sub_age", 99999) < 45 or bool(re.search(
        r"(I'll|I will) report (back|once|when)|re-?checking", s.get("text", "")[-400:], re.I))


def fetch_session(codespace, file):
    """The whole session JSONL (the file name from status()), as text."""
    return _ssh(codespace, FETCH, file, timeout=180).stdout
