"""R139: overlay ideas (attention grabbers, R138) from several models through OpenRouter.

    python tools/ideas_run.py bundle <export_dir> <steps.json> <out_dir>   # the bundle the models read
           [--about=<file>] [--plan-doc=<file>|none] [--sections=1,2,3,4] [--rulebook[=<VIDEO_RULES.md>]]
    python tools/ideas_run.py ask <out_dir> --models=a,b,c,d [--effort=medium]   # one call per model, in parallel
    python tools/ideas_run.py judge <out_dir> --models=x,y   # blind scores of every idea (no model names), per judge
    python tools/ideas_run.py summary <out_dir>              # the judges' scores per contestant (no calls)

Every command but summary calls OpenRouter: only on David's say-so (R146). A judge that also competed favours its
own vendor's ideas (2026-10-15): prefer judges that didn't compete, or read each judge's own column apart.

The bundle: the script with each line's timecode on the full sequence (the export's edit_plan.json; the full sequence
is the camera from 0:00 when the export has no opening graphic), the overlay plan's sections 1 to 4, the rules the
ideas must follow, and the inventory's one-line readings of David's own overlays. Each reply is saved as it came
(<model>.raw.json), its ideas as <model>.ideas.json, and its cost as OpenRouter reported it (costs.json). The key is
read through pipeline.config.get_section (R4) and never written or printed.

The bundle's flags, for another exercise (with none, Section A's bundle exactly as before): --about, a file with the
video in a paragraph (from the exercise's BRIEF.md; a "# " first line is its title) in place of Section A's;
--plan-doc, the overlay plan to quote ("none": no plan), and --sections, its numbered sections to quote (with any
plan but Section A's own sections 1 to 4, the task's "already planned" and "compositions" lines are worded for that
plan, not Section A's); --rulebook, the rulebook's graphics rules (VIDEO_RULES.md, Part 1's "Graphics" section: G1
to G21, R188's one rulebook) in place of RULE_IDS's decisions from RULES.md (which list superseded R136).
"""
import argparse
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PLAN_DOC = ROOT / "docs" / "OVERLAY_PLAN_qs1a.md"
INVENTORY = ROOT / "research" / "style_study" / "overlays" / "INVENTORY.md"
RULES = ROOT / "RULES.md"
RULE_IDS = ("R80", "R122", "R129", "R136", "R138", "R139", "R140", "R141", "R142", "R143")
PLAN_SECTIONS = (1, 2, 3, 4)
RULEBOOK = ROOT.parent / "Global Assets" / "VIDEO_RULES.md"     # --rulebook's default (R188)
URL = "https://openrouter.ai/api/v1/chat/completions"
ABOUT = ("# Quick Sight Journey 1, Section A: the overlay ideas run (R139)\n\n"   # Section A's; --about replaces it
         "A screen-recorded tutorial: the narrator (David, first person) uploads an Excel file to Amazon Quick Sight, "
         "sets the data types, then builds an analysis with two charts and publishes it as a dashboard. The viewers "
         "are business analysts new to Quick Sight. Timecodes are on the finished video (30 fps).")
PLANNED = {  # the task's lines that depend on the plan quoted: Section A's (its plan's sections 1 to 4), another
    "qs1a": ('- The twenty spots in "Where they go in Section A" and David\'s directions in "Attention grabbers" are '
             "already\n  planned: don't repeat them. You may propose a small grabber on a line near one of them.\n",
             "- Use the compositions of section 2 by name where one fits; a new kind is fine if it earns its place.\n"),
    "plan": ("- What the overlay plan below already places is planned: don't repeat it. You may propose a small grabber "
             "on a\n  line near one of its spots.\n",
             "- Use the compositions the overlay plan below names, by name, where one fits; a new kind is fine if it "
             "earns its\n  place.\n"),
    "none": ("", "- Name a composition for each (a chip, a panel, a word build, a checklist, ...); a new kind is fine "
                 "if it\n  earns its place.\n"),
}

SYSTEM = ("You are a motion-graphics director for short software training videos. You propose overlays that hold the "
          "viewer's eye and always serve what the narrator is saying at that moment. You answer with JSON only.")

TASK = """## Your task

Propose attention grabbers for this video, which runs {minutes:.0f} minutes: three or four for every minute of video,
so about {n_low} to {n_high} in all. That is more than will be used; a shortlist is picked from all the models' ideas.

- Each idea rides on one narration line: give that line's timecode exactly as the script shows it, and the exact
  words from that line where the idea appears.
- Each one ties into what is being said at that moment (no dancing aliens for no reason). Humour is one kind, not
  the only one; most should be small (an icon flash, a chip, a word build, a looping icon over a long hold).
- Nothing culturally targeted: no pop-culture, celebrity, sports, film or music references, no idioms that only
  work in one country. A viewer in India must get it as well as one in Texas. US cities are fine.
- The spoken text stays as it is. If an idea only works with a reworded line, set "needs_line_change" to the new
  wording; otherwise leave it empty.
- One overlay at a time. The screen is a Quick Sight web page (light) most of the time; panels contrast with what
  they sit on.
{planned}- Spread the ideas across the whole video, not bunched at the start.
{compositions}
Answer with one JSON object and nothing else:

{{"ideas": [{{"timecode": "HH:MM:SS:FF", "at_words": "...", "what_appears": "...", "composition": "TermChip | ... | new: <name>",
  "size": "small | big", "enters": "...", "leaves": "...", "hold_s": 2.5, "ties_to": "...",
  "build": "local (Remotion, exact layout) | generated (image or video model, loose)", "sound": "", "needs_line_change": ""}}]}}
"""


def tc(t, fps):
    f = int(round(t * fps))
    fr, s = f % int(fps), f // int(fps)
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}:{fr:02d}"


def plan_sections(text, wanted):
    """The overlay plan's numbered sections (## n. ...), by number."""
    parts = re.split(r"(?m)^(?=## )", text)
    out = []
    for p in parts:
        m = re.match(r"## (\d+)\.", p)
        if m and int(m.group(1)) in wanted:
            out.append(p.strip())
    return "\n\n".join(out)


def sections_named(nums):
    """'sections 1 to 4', 'sections 1 and 2', 'section 3'."""
    s = sorted(nums)
    if len(s) == 1:
        return f"section {s[0]}"
    if len(s) > 2 and s == list(range(s[0], s[-1] + 1)):
        return f"sections {s[0]} to {s[-1]}"
    return "sections " + ", ".join(map(str, s[:-1])) + f" and {s[-1]}"


def rulebook_graphics(text):
    """The rulebook's graphics rules (R188): Part 1's numbered "Graphics" section, its heading a level down so it
    sits under the bundle's own."""
    for p in re.split(r"(?m)^(?=## )", text):
        if re.match(r"## \d+\. Graphics\b", p):
            return "#" + p.strip()
    raise SystemExit("no '## <n>. Graphics' section in the rulebook")


def rule_blocks(text, ids):
    out = []
    for rid in ids:
        m = re.search(rf"(?ms)^- \*\*{rid} .*?(?=^- \*\*R\d+|^## |^\Z|\n\n)", text)
        if m:
            out.append(re.sub(r"\s*\n\s*", " ", m.group(0).strip()))
    return "\n".join(out)


def inventory_lines(text):
    """One line per overlay of David's: episode, time, kind, humour, entrance and exit, what it does, what was said."""
    out, ep = [], None
    for ln in text.splitlines():
        m = re.match(r"## Episode (\d+)", ln)
        if m:
            ep = f"ep{m.group(1)}"
            continue
        if not ln.startswith("| ") or ln.startswith("| #") or ln.startswith("|---"):
            continue
        c = [x.strip() for x in ln.strip("|").split("|")]
        if len(c) < 13 or not c[0].isdigit():
            continue
        said = c[10][:110] + ("..." if len(c[10]) > 110 else "")
        out.append(f"- {ep} {c[1]} {c[2]}{' (humour: ' + c[11] + ')' if c[11] else ''}: {c[12]}. In {c[8]}; out "
                   f"{c[9]}. Said: \"{said}\"")
    return "\n".join(out)


def bundle(export_dir, steps_path, out_dir, about=None, plan_doc=PLAN_DOC, sections=PLAN_SECTIONS, rulebook=None):
    """The bundle; about, plan_doc ("none" or None: no plan), sections and rulebook as the module docstring says (the
    defaults: Section A's bundle)."""
    export_dir, out_dir = Path(export_dir), Path(out_dir)
    plan_doc = None if plan_doc in (None, "none") else Path(plan_doc)
    sections = tuple(sorted(set(sections)))
    plan = json.loads((export_dir / "edit_plan.json").read_text(encoding="utf-8"))
    doc = json.loads(Path(steps_path).read_text(encoding="utf-8"))
    lines = json.loads((ROOT / "exercises" / doc["exercise"] / "lines.json").read_text(encoding="utf-8"))
    steps = {s["id"]: s for s in doc["steps"]}
    parts = doc.get("parts") or {}                         # {"1": "Connect to Data", ...}
    fps = plan["fps"]
    rows, prev_part = [], None
    for n in plan["narration"]:
        st = steps.get(n["step"], {})
        part = st.get("part")
        if part != prev_part:
            name = parts.get(str(part)) if isinstance(parts, dict) else None
            rows.append(f"\n### Part {part}{': ' + name if name else ''}\n")
            prev_part = part
        text = lines[n["line_id"]]["text"]
        what = []
        a = st.get("action") or {}
        if a.get("type") and a["type"] != "none":
            what.append(a["type"])
        labels = (st.get("narration") or {}).get("labels") or []
        if labels:
            what.append("names on screen: " + ", ".join(labels))
        if (st.get("whole") or {}).get("what"):
            what.append("shows " + st["whole"]["what"])
        rows.append(f"[{tc(n['start'], fps)} to {tc(n['start'] + n['length'], fps)}] {text}"
                    + (f"  (screen: {'; '.join(what)})" if what else ""))
    minutes = plan["duration_s"] / 60
    if about:                                             # the video in a paragraph (the exercise's BRIEF.md)
        head = Path(about).read_text(encoding="utf-8").strip()
        if not head.startswith("# "):
            head = "# The overlay ideas run (R139)\n\n" + head
        head += f"\n\nTimecodes are on the finished video ({fps:g} fps)."
    else:
        head = ABOUT
    if plan_doc is None:
        kind = "none"
    else:
        kind = "qs1a" if plan_doc.resolve() == PLAN_DOC.resolve() and sections == PLAN_SECTIONS else "plan"
    planned, compositions = PLANNED[kind]
    plan_part = [] if plan_doc is None else [
        f"## The overlay plan ({sections_named(sections)})",
        "",
        plan_sections(plan_doc.read_text(encoding="utf-8"), set(sections)),
        "",
    ]
    if rulebook:                                          # R188: the one rulebook's graphics rules
        rules_part = ["## The rules (the rulebook's graphics rules)", "",
                      rulebook_graphics(Path(rulebook).read_text(encoding="utf-8")), ""]
    else:
        rules_part = ["## The rules (David's decisions)", "", rule_blocks(RULES.read_text(encoding="utf-8"), RULE_IDS),
                      ""]
    body = "\n".join([
        head,
        "",
        TASK.format(minutes=minutes, n_low=int(minutes * 3), n_high=int(minutes * 4), planned=planned,
                    compositions=compositions),
        "## The script, with timecodes",
        "\n".join(rows),
        "",
        *plan_part,
        *rules_part,
        "## David's own overlays, one line each (the inventory of his Quick Series episodes 03 and 04)",
        "",
        inventory_lines(INVENTORY.read_text(encoding="utf-8")),
        "",
    ])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bundle.md").write_text(body, encoding="utf-8")
    meta = {"export": str(export_dir), "steps": str(steps_path), "fps": fps, "duration_s": plan["duration_s"],
            "lines": {n["line_id"]: {"start": n["start"], "length": n["length"], "key": n["key"],
                                     "timecode": tc(n["start"], fps)} for n in plan["narration"]}}
    given = {"about": about and str(about), "plan_doc": "none" if plan_doc is None else str(plan_doc),
             "sections": list(sections), "rulebook": rulebook and str(rulebook)}
    defaults = {"about": None, "plan_doc": str(PLAN_DOC), "sections": list(PLAN_SECTIONS), "rulebook": None}
    meta.update({k: v for k, v in given.items() if v != defaults[k]})   # only what differs from Section A's
    (out_dir / "bundle_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"bundle: {out_dir / 'bundle.md'} ({len(body):,} characters, {len(plan['narration'])} lines, "
          f"{minutes:.1f} min)")


def parse_ideas(text, field="ideas"):
    """The first JSON object in a reply (fenced or bare) -> its list (ideas, or a judge's scores)."""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw).get(field, [])


def ask_one(model, body, effort, key, out_dir, results, prefix=""):
    payload = {"model": model, "max_tokens": 32000, "usage": {"include": True},
               "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}]}
    if effort:
        payload["reasoning"] = {"effort": effort}
    name = prefix + model.replace("/", "_")
    t0 = time.time()
    for attempt in range(3):
        req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                              "X-Title": "AIDV overlay ideas"})
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=900))
            break
        except Exception as e:                             # a dropped connection, a short read or a non-JSON body
            try:                                           # too: retried, and the last failure recorded, so no model
                err = e.read().decode("utf-8", "replace")[:400] if hasattr(e, "read") else ""   # drops out silently
            except Exception:
                err = ""
            if attempt == 2:
                results[model] = {"error": f"{type(e).__name__}: {e} {err}".strip()}
                return
            time.sleep(5 * (attempt + 1))
    (out_dir / f"{name}.raw.json").write_text(json.dumps(resp, indent=1), encoding="utf-8")
    u = resp.get("usage") or {}
    rec = {"model": resp.get("model", model), "seconds": round(time.time() - t0, 1),
           "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
           "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
           "cost_usd": u.get("cost")}
    try:
        text = resp["choices"][0]["message"]["content"] or ""
        ideas = parse_ideas(text, "scores" if prefix else "ideas")
        (out_dir / f"{name}.{'scores' if prefix else 'ideas'}.json").write_text(json.dumps(ideas, indent=1),
                                                                             encoding="utf-8")
        rec["ideas"] = len(ideas)
    except Exception as e:                                 # the reply is kept as it came; parse it by hand
        rec["parse_error"] = repr(e)[:300]
    results[model] = rec


def ask(out_dir, models, effort):
    from pipeline.config import get_section
    out_dir = Path(out_dir)
    body = (out_dir / "bundle.md").read_text(encoding="utf-8")
    key = get_section("openrouter")["api_key"]
    results = {}
    th = [threading.Thread(target=ask_one, args=(m, body, effort, key, out_dir, results)) for m in models]
    for t in th:
        t.start()
    for t in th:
        t.join()
    costs_p = out_dir / "costs.json"
    log = json.loads(costs_p.read_text(encoding="utf-8")) if costs_p.exists() else []
    log.append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "effort": effort, "results": results})
    costs_p.write_text(json.dumps(log, indent=1), encoding="utf-8")
    total = 0.0
    for m in models:
        r = results.get(m, {})
        if "error" in r:
            print(f"{m}: ERROR {r['error']}")
            continue
        total += r.get("cost_usd") or 0.0
        print(f"{m}: {r.get('ideas', '?')} ideas, ${r.get('cost_usd') or 0:.4f} ({r.get('prompt_tokens')} in, "
              f"{r.get('completion_tokens')} out, {r.get('reasoning_tokens')} reasoning), {r.get('seconds')} s"
              + (f"; parse error {r['parse_error']}" if r.get("parse_error") else ""))
    print(f"total ${total:.4f}")


JUDGE_TASK = """## Your task: score these overlay ideas

Several sources proposed the attention grabbers below for this video (sources are hidden; ids are random). Score
every idea on its own merits, against the script, the plan and the rules above. 1 is poor, 5 is excellent.

- tied: tied to what is being said at that moment
- adds: adds something the screen and the narration don't already show (a restatement of on-screen text scores low)
- eye: holds the viewer's eye; a viewer would notice it and be glad of it
- fit: follows the rules (nothing culturally targeted, the spoken text unchanged, items say what their sentence
  says, one overlay at a time, doesn't repeat a planned spot) and can be built as described
- use: true if you would put it in the video

Answer with one JSON object and nothing else:
{{"scores": [{{"id": "...", "tied": 1, "adds": 1, "eye": 1, "fit": 1, "use": false}}]}}

## The ideas ({n})

{ideas}
"""


def judge(out_dir, models, effort):
    """Blind scores: every model's ideas, shuffled under random ids, scored by each judge model (judge_<model>.json);
    the key (judge_key.json) maps ids back to the model and the idea."""
    import random
    from pipeline.config import get_section
    out_dir = Path(out_dir)
    pool = []
    for p in sorted(out_dir.glob("*.ideas.json")):
        src = p.name.split(".ideas")[0]
        for i, idea in enumerate(json.loads(p.read_text(encoding="utf-8"))):
            pool.append((src, i, idea))
    rng = random.Random(139)
    rng.shuffle(pool)
    key, rows = {}, []
    for k, (src, i, idea) in enumerate(pool):
        iid = f"{rng.randrange(36 ** 4):04x}{k:03d}"
        key[iid] = {"model": src, "index": i}
        rows.append(f"- id {iid} | {idea.get('timecode')} | at \"{idea.get('at_words')}\" | {idea.get('composition')}, "
                    f"{idea.get('size')} | {idea.get('what_appears')} | ties to: {idea.get('ties_to')}"
                    + (f" | needs line change: {idea['needs_line_change']}" if idea.get("needs_line_change") else ""))
    (out_dir / "judge_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    bundle = (out_dir / "bundle.md").read_text(encoding="utf-8")
    bundle = bundle[:bundle.find("## Your task")] + bundle[bundle.find("## The script"):]   # the context, not the ask
    body = bundle + "\n\n" + JUDGE_TASK.format(n=len(rows), ideas="\n".join(rows))
    (out_dir / "judge_bundle.md").write_text(body, encoding="utf-8")
    key_ = get_section("openrouter")["api_key"]
    results = {}
    th = [threading.Thread(target=ask_one, args=(m, body, effort, key_, out_dir, results, "judge_")) for m in models]
    for t in th:
        t.start()
    for t in th:
        t.join()
    costs_p = out_dir / "costs.json"
    log = json.loads(costs_p.read_text(encoding="utf-8")) if costs_p.exists() else []
    log.append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "effort": effort, "judge": True, "results": results})
    costs_p.write_text(json.dumps(log, indent=1), encoding="utf-8")
    for m in models:
        r = results.get(m, {})
        print(f"judge {m}: " + (f"ERROR {r['error']}" if "error" in r else
                                f"{r.get('ideas', '?')} scores, ${r.get('cost_usd') or 0:.4f}, {r.get('seconds')} s"
                                + (f"; parse error {r['parse_error']}" if r.get("parse_error") else "")))


def summary(out_dir):
    """The blind judges' scores per contestant (R145), from judge_key.json and judge_*.scores.json: mean of the four
    scores, mean "eye", and the share each judge would use, per judge -> judge_summary.json and a printed table.
    Judges that also competed favour their own vendor (2026-10-15), so read each judge's column on its own."""
    out_dir = Path(out_dir)
    key = json.loads((out_dir / "judge_key.json").read_text(encoding="utf-8"))
    res = {}
    for jp in sorted(out_dir.glob("judge_*.scores.json")):
        judge_name = jp.name[len("judge_"):-len(".scores.json")]
        agg = {}
        for sc in json.loads(jp.read_text(encoding="utf-8")):
            k = key.get(str(sc.get("id")))
            if not k:
                continue
            a = agg.setdefault(k["model"], {"n": 0, "mean": 0.0, "eye": 0.0, "use": 0})
            vals = [float(sc.get(f) or 0) for f in ("tied", "adds", "eye", "fit")]
            a["n"] += 1
            a["mean"] += sum(vals) / 4
            a["eye"] += vals[2]
            a["use"] += bool(sc.get("use"))
        res[judge_name] = {m: {"n": a["n"], "mean": round(a["mean"] / a["n"], 2), "eye": round(a["eye"] / a["n"], 2),
                               "use_pct": round(100 * a["use"] / a["n"])} for m, a in agg.items()}
    (out_dir / "judge_summary.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    models = sorted({m for r in res.values() for m in r})
    judges = sorted(res)
    print("model | " + " | ".join(f"{j}: mean, eye, use" for j in judges))
    for m in models:
        print(m + " | " + " | ".join(
            f"{res[j][m]['mean']:.2f}, {res[j][m]['eye']:.2f}, {res[j][m]['use_pct']}%" if m in res[j] else "-"
            for j in judges))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bundle")
    b.add_argument("export_dir")
    b.add_argument("steps")
    b.add_argument("out_dir")
    b.add_argument("--about", help="the video in a paragraph (a file; '# ' first line: its title); default Section A's")
    b.add_argument("--plan-doc", default=str(PLAN_DOC), help="the overlay plan to quote, or 'none'")
    b.add_argument("--sections", default=",".join(map(str, PLAN_SECTIONS)), help="its numbered sections to quote")
    b.add_argument("--rulebook", nargs="?", const=str(RULEBOOK), default=None,
                   help=f"quote the rulebook's graphics rules in place of RULE_IDS (default file {RULEBOOK})")
    a = sub.add_parser("ask")
    a.add_argument("out_dir")
    a.add_argument("--models", required=True)
    a.add_argument("--effort", default="medium")
    j = sub.add_parser("judge")
    j.add_argument("out_dir")
    j.add_argument("--models", required=True)
    j.add_argument("--effort", default="medium")
    sm = sub.add_parser("summary")
    sm.add_argument("out_dir")
    args = ap.parse_args()
    models = [m.strip() for m in getattr(args, "models", "").split(",") if m.strip()]
    if args.cmd == "bundle":
        bundle(args.export_dir, args.steps, args.out_dir, about=args.about, plan_doc=args.plan_doc,
               sections=[int(x) for x in args.sections.split(",") if x.strip()], rulebook=args.rulebook)
    elif args.cmd == "summary":
        summary(args.out_dir)
    elif args.cmd == "judge":
        judge(args.out_dir, models, args.effort or None)
    else:
        ask(args.out_dir, models, args.effort or None)


if __name__ == "__main__":
    main()
