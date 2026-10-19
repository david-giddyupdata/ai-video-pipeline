"""The narration script for David's approval, rendered from a steps file (which stays the source of truth).

    python -m pipeline.narration.script exercises/<ex>/steps_full.json   # -> exercises/<ex>/script_full.md

Lists every line part by part with its action, what it needs that isn't built yet (runner.missing), its labels,
highlights and marks, the prompts as they appear on screen, and, for lines written after the run (R33)
or the exploration (Part 5), the points they must cover. A lint checks the draft against NARRATION §9: sentence
length (R29), cue and click words (R23), label, highlight and mark words present in the line.
"""
import json
import re
import sys
from pathlib import Path

from pipeline.config import EXERCISES
from pipeline.driver.runner import NOT_BUILT, load_steps, missing
from pipeline.narration.respell import load_terms, respell

WORDS_PER_S = 2.17            # Andrew at -15%, measured on take 05's eight lines (label pauses included)
MAX_SENTENCE_WORDS = 25       # R29
NEED_LABEL = {
    "action:type": "typing", "action:paste": "paste", "action:key": "key press", "action:scroll": "reading scroll",
    "action:switch_tab": "tab switch", "action:none": "narration-only step", "action:wait_claude": "wait for Claude",
    "action:approve_prompt": "approve a prompt", "action:wait": "wait", "expect:text_in_frame": "panel text check",
    "expect:claude_idle": "Claude-idle check", "expect:new_tab": "new-tab check",
    "frame:claude_panel": "targets in the Claude panel", "tab:dashboard": "the dashboard tab",
    "highlights": "text highlights", "narration:after_run": "narration written after the run",
    "timelapse": "time-lapse", "segment:generated": "generated steps (Part 5)", "locator:todo": "a locator to confirm",
}
STATUS = {"approved": "approved", "draft": "draft", "pending_post_run": "written after the run"}


def words(text):
    return [w.strip(".,;:!?\"'()") for w in text.split()]


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def lint(step):
    out = lint_text(step, step["narration"].get("text"))
    for case, alt in step["narration"].get("variants", {}).items():
        out += [f"[{case}] {m}" for m in lint_text(step, alt)]
    return out


def lint_text(step, text):
    n, out = step["narration"], []
    if not text:
        return out
    ws = words(text)
    for s in sentences(text):
        if len(s.split()) > MAX_SENTENCE_WORDS:
            out.append(f"sentence of {len(s.split())} words (R29): \"{s[:60]}...\"")
    cue, click = n.get("cue_word"), n.get("click_word")
    for name, w in (("cue word", cue), ("click word", click)):
        if w and w not in ws:
            out.append(f"{name} {w!r} is not a word of the line")
    if cue and click and cue in ws and click in ws and ws.index(click) < ws.index(cue):
        out.append(f"click word {click!r} first occurs before the cue word {cue!r} (R23 matches the first one)")
    for label in n.get("labels", []):
        if label not in text:
            out.append(f"label {label!r} is not in the line")
    for h in step.get("highlights", []):
        if h["cue_word"] not in ws:
            out.append(f"highlight cue {h['cue_word']!r} is not a word of the line")
    for m in step.get("marks", []):
        if "{" not in m["at_word"] and m["at_word"] not in text:
            out.append(f"mark word {m['at_word']!r} is not in the line")
    return out


def seconds(step):
    n = step["narration"]
    if not n.get("text"):
        return 0.0
    return len(n["text"].split()) / WORDS_PER_S


def mmss(s):
    return f"{int(s // 60)}:{int(round(s % 60)):02d}"


def describe_action(step):
    a = step["action"]
    kind = a["type"]
    if kind == "type":
        kind = "paste" if a.get("typing_mode") == "paste" else "type"
    what = {"none": "no action (the line plays over the picture)", "wait_claude": "wait for Claude",
            "paste": "paste a prompt", "type": "type", "scroll": "scroll Claude's reply",
            "switch_tab": "switch tab", "key": f"press {a.get('key')}"}.get(kind, kind)
    if a.get("os"):                                 # R112: a click in a Windows dialog
        o = a["os"]
        return f"{o.get('item') and 'select' or 'click'} `{o.get('item') or o.get('button')}` in the {o['window']} dialog"
    if kind in ("click", "hover", "drag"):
        loc = a["target"]["locator"]
        what += "" if loc.startswith("TODO") else f" `{loc}`"
    return what


def render(doc, steps_name):
    voice = json.loads((EXERCISES / doc["exercise"] / doc.get("voice_file", "voice.json")).read_text(encoding="utf-8"))
    terms = load_terms(doc["exercise"], voice["engine"], doc.get("pronunciation_file", "pronunciation.json"))
    parts = doc.get("parts", {})
    steps = doc["steps"]
    counts = {k: sum(1 for s in steps if s["narration"]["status"] == k) for k in STATUS}
    total = sum(seconds(s) for s in steps)
    gaps = {}
    for s in steps:
        for need, by in missing(s):
            gaps.setdefault((by, need), []).append(s["id"])
    lints = [(s["id"], msg) for s in steps for msg in lint(s)]

    out = [f"# Narration script: {doc['exercise'].replace('_', ' ')}", "",
           f"Rendered from `{steps_name}` (version {doc['version']}) by `python -m pipeline.narration.script`. "
           "Don't edit this file: notes go to Claude, who changes the steps file and renders it again.", "",
           f"- **Lines:** {counts['approved']} approved, {counts['draft']} draft, "
           f"{counts['pending_post_run']} written after the run or the exploration (their points are below).",
           f"- **Voiced so far:** about {mmss(total)} at Andrew's pace, before the live footage (time-lapses, "
           "title card, 1x permission prompts).",
           ""]
    out += ["## Not built yet", "", "| Builds it | Capability | Steps |", "|---|---|---|"]
    order = list(NOT_BUILT)
    for (by, need), ids in sorted(gaps.items(), key=lambda kv: (kv[0][0], order.index(kv[0][1]))):
        span = ids[0] if len(ids) == 1 else f"{len(ids)} steps: {', '.join(ids)}"
        out.append(f"| {by} | {NEED_LABEL.get(need, need)} | {span} |")
    out.append("")
    if lints:
        out += ["## Lint", ""] + [f"- **{sid}:** {msg}" for sid, msg in lints] + [""]

    for part in sorted({s["part"] for s in steps}):
        ps = [s for s in steps if s["part"] == part]
        manual = sorted({s["manual_step"] for s in ps if s.get("manual_step")})
        span = f" (doc steps {manual[0]} to {manual[-1]})" if len(manual) > 1 else \
            f" (doc step {manual[0]})" if manual else ""
        title = parts.get(str(part), "")
        out += [f"## Part {part}: {title}{span}", "", f"Voiced about {mmss(sum(seconds(s) for s in ps))}.", ""]
        for s in ps:
            n = s["narration"]
            head = f"**{s['id']}** · {describe_action(s)}"
            if s["segment"] != "scripted":
                head += f" · *{s['segment']}*"
            if s.get("only_if"):
                head += " · *conditional*"
            if n["status"] != "draft":
                head += f" · {STATUS[n['status']]}"
            need = missing(s)
            if need:
                head += " · needs " + ", ".join(f"{NEED_LABEL.get(x, x)} ({by})" for x, by in need)
            out.append(head)
            out.append("")
            if n.get("text"):
                out.append(f"> {n['text']}")
                out.append("")
                spoken = respell(n["text"], terms, n.get("spoken"))[0]
                if spoken != n["text"]:
                    out += [f"<sub>Spoken: {spoken}</sub>", ""]
            extras = []
            if n.get("labels"):
                extras.append("labels: " + ", ".join(f"*{x}*" for x in n["labels"]))
            for h in s.get("highlights", []):
                extras.append(f"highlight \"{h['match']}\" on *{h['cue_word']}*")
            for m in s.get("marks", []):
                extras.append(f"{m.get('style', 'draw')} {m['kind']} on *{m['at_word']}*")
            for case, alt in n.get("variants", {}).items():
                extras.append(f"*{case}* variant (R71): {alt}")
            if extras:
                out += [f"- {e}" for e in extras] + [""]
            if s["action"]["type"] == "type":
                out += ["```text", s["action"]["text"], "```", ""]
            if n.get("points"):
                out += ["Must cover, if it happens:", ""] + [f"- {p}" for p in n["points"]] + [""]
            if s.get("notes"):
                out += [f"<sub>{s['notes']}</sub>", ""]
    return "\n".join(out).rstrip() + "\n"


def main(path):
    path = Path(path)
    doc = load_steps(path)
    md = path.with_name("script_" + path.stem.removeprefix("steps_") + ".md")
    md.write_text(render(doc, path.name), encoding="utf-8")
    lints = [(s["id"], m) for s in doc["steps"] for m in lint(s)]
    print(md, f"({len(lints)} lint findings)")
    for sid, m in lints:
        print(f"  {sid}: {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
