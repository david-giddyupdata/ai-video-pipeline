"""Post-run harvest for live steps (R33, SPEC §3): what Claude did during each live step, from the run log and the
session logs the take fetched (runs/<id>/claude/*.jsonl), plus stills of the recording every 15 s and at each
permission prompt. Claude drafts the live narration from it (to each step's `points`); David approves the wording.

    python -m pipeline.post.live runs/<run_id> <steps.json>

Writes runs/<id>/live_harvest.json and live_harvest.md, and stills to runs/<id>/stills_live/.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from pipeline.config import tool
from pipeline.post.s1_report import load_log

STILL_EVERY_S = 15.0


def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def session_records(run_dir):
    recs = []
    for f in sorted((run_dir / "claude").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("timestamp") and r.get("type") in ("user", "assistant"):
                recs.append(r)
    return sorted(recs, key=lambda r: r["timestamp"])


def digest(recs):
    """Tool uses, errors, skills, files written and Claude's text, in order, each with its wall time."""
    out = []
    for r in recs:
        content = (r.get("message") or {}).get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for c in content or []:
            if not isinstance(c, dict):
                continue
            t = _ts(r["timestamp"])
            if c.get("type") == "tool_use":
                inp = c.get("input") or {}
                what = inp.get("file_path") or inp.get("command") or inp.get("skill") or inp.get("description") or ""
                out.append({"t": t, "kind": "tool", "name": c.get("name"), "what": str(what)[:200]})
            elif c.get("type") == "tool_result" and c.get("is_error"):
                body = c.get("content")
                body = body if isinstance(body, str) else json.dumps(body)[:400]
                out.append({"t": t, "kind": "error", "what": body[:400]})
            elif c.get("type") == "text" and r["type"] == "assistant" and c.get("text", "").strip():
                out.append({"t": t, "kind": "text", "what": c["text"]})
    return out


def still(raw, src_t, path):
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{src_t:.3f}", "-i", str(raw), "-frames:v", "1",
                    "-vf", "scale=960:-1", "-q:v", "3", str(path)], check=True)


def harvest(run_dir, steps_path):
    run_dir = Path(run_dir).resolve()
    header, events = load_log(run_dir)
    cal = json.loads((run_dir / "calibration.json").read_text(encoding="utf-8"))
    doc = json.loads(Path(steps_path).read_text(encoding="utf-8"))
    live = [s for s in doc["steps"] if s["segment"] == "live"]
    wall = lambda e: _ts(e["t_wall"])     # each event's own wall time: a joined take's run clock skips the pause (R70)
    tv = lambda t: cal["offset_s"] + cal["scale"] * t                # run clock -> recording time
    items = digest(session_records(run_dir))
    (run_dir / "stills_live").mkdir(exist_ok=True)
    out = []
    for step in live:
        ev = [e for e in events if e["step_id"] == step["id"]]
        if not ev:
            continue
        e0 = next(e for e in ev if e["phase"] == "step_start")
        e1 = next((e for e in ev if e["phase"] == "step_end"), ev[-1])
        t0, t1 = e0["t_mono"], e1["t_mono"]
        sent = e0
        if step["action"]["type"] == "wait_claude":
            sent = max((e for e in events if e["phase"] == "action" and e["t_mono"] <= t0
                        and e["step_id"] != step["id"]), key=lambda e: e["t_mono"], default=e0)
        # Claude starts at the send (the step before a wait): a quick turn can end before the wait step starts
        mine = [{**i, "at_s": round(i["t"] - wall(e0), 1)} for i in items if wall(sent) <= i["t"] <= wall(e1)]
        prompts = [{"at_s": round(e["t_mono"] - t0, 1), "phase": e["phase"], "text": (e.get("detail") or {}).get("text")}
                   for e in ev if e["phase"] in ("prompt_seen", "prompt_approved", "claude_question")]
        stills, t = [], t0
        marks = sorted({t0, t1} | {e["t_mono"] for e in ev if e["phase"] in ("prompt_seen", "scroll_start", "scroll_end")})
        while t < t1:
            marks.append(t)
            t += STILL_EVERY_S
        for tm in sorted(set(round(m, 1) for m in marks)):
            p = run_dir / "stills_live" / f"{step['id']}_{tm - t0:06.1f}.jpg"
            if not p.exists():
                still(run_dir / "raw.mp4", tv(tm), p)
            stills.append(p.name)
        reply = next((i["what"] for i in reversed([i for i in items if i["t"] <= wall(e1)]) if i["kind"] == "text"), "")
        out.append({"step": step["id"], "action": step["action"]["type"], "wait_s": round(t1 - t0, 1),
                    "points": step["narration"].get("points", []), "prompts": prompts,
                    "tools": [{k: i[k] for k in ("at_s", "name", "what")} for i in mine if i["kind"] == "tool"],
                    "errors": [{k: i[k] for k in ("at_s", "what")} for i in mine if i["kind"] == "error"],
                    "texts": [{k: i[k] for k in ("at_s", "what")} for i in mine if i["kind"] == "text"],
                    "last_reply": reply, "stills": stills})
    (run_dir / "live_harvest.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    md = [f"# Live harvest: {run_dir.name}", ""]
    for h in out:
        md += [f"## {h['step']} ({h['action']}, {h['wait_s']} s)", "", "Points: " + " / ".join(h["points"]), ""]
        md += [f"- {p['at_s']:>6} s {p['phase']}: {(p['text'] or '')[:160]!r}" for p in h["prompts"]]
        md += [f"- {x['at_s']:>6} s tool {x['name']}: {x['what'][:120]}" for x in h["tools"]]
        md += [f"- {x['at_s']:>6} s ERROR: {x['what'][:160]}" for x in h["errors"]]
        md += ["", "Claude's text in this step:", ""] + [f"> [{x['at_s']} s] " + x["what"].replace("\n", "\n> ")
                                                         for x in h["texts"]] + [""]
        if h["action"] == "scroll" and not h["texts"]:
            md += ["The reply on screen (read during the scroll):", "", "> " + h["last_reply"].replace("\n", "\n> "), ""]
    (run_dir / "live_harvest.md").write_text("\n".join(md), encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    for h in harvest(sys.argv[1], sys.argv[2]):
        print(h["step"], h["wait_s"], "s,", len(h["tools"]), "tools,", len(h["errors"]), "errors,",
              len(h["prompts"]), "prompt events,", len(h["stills"]), "stills")
