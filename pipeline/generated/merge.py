"""The generated steps into the step list (R70, R71): what the off-camera exploration chose, written by Claude as
runs/<run_id>/generated.json, merged into the exercise's steps as the take runs them.

    python -m pipeline.generated.merge runs/<run_id>      # check and write exercises/<ex>/steps_<tag>.json

generated.json:
  {"mode": "defect" | "improvement",                 # R71: improvement switches lines to their `improvement` variants
   "defect": "one sentence: what I clicked, what I saw, what I expected",
   "variables": {"feedback_prompt": "...", ...},     # the @generated variables
   "steps": {"p5.14c": {"action": {...}, "expect": {...}, "narration": {"text": "...", ...}, "marks": [...]}, ...},
   "insert": [{"after": "p5.14d", "step": {full step}}, ...],   # more steps (a dropdown's second click, round two)
   "notes": "why these interactions and this defect (R70's four tests)"}

Fields given for a step replace the step's own (narration is merged key by key, so status and source stay unless
given). Every feedback prompt (a variable named feedback_prompt...) ends with FEEDBACK_END (R87): Claude won't restart a
server it didn't start, and the reload must show the new version. The result goes beside the exercise's other step lists (the line check and the read-back find it by name)
as steps_<tag>.json, where <tag> is the run's (dashboard_20261007_p5 -> steps_p5.json).
"""
import copy
import json
import sys
from pathlib import Path

from pipeline.config import EXERCISES, RUNS
from pipeline.driver.runner import STEPS_VALIDATOR, missing

FEEDBACK_END = "Then restart the dashboard so I can check it."     # R87


def run_tag(run_dir):
    """dashboard_20261007_p5_take01 -> p5_take01"""
    return Path(run_dir).name.split("_", 2)[2]


def merge(base, gen, run_dir):
    doc = copy.deepcopy(base)
    gen = gen or {}
    by_id = {s["id"]: s for s in doc["steps"]}
    for sid, fields in (gen.get("steps") or {}).items():
        if sid not in by_id:
            raise ValueError(f"generated.json names {sid}, which is not in {base['exercise']}'s steps")
        st = by_id[sid]
        for k, v in fields.items():
            if k == "narration":
                st["narration"] = {**st["narration"], **v}
            else:
                st[k] = v
    for ins in gen.get("insert") or []:
        ids = [s["id"] for s in doc["steps"]]
        if ins["after"] not in ids or ins["step"]["id"] in ids:
            raise ValueError(f"insert after {ins['after']!r} of {ins['step']['id']!r}: no such step, or the id is taken")
        doc["steps"].insert(ids.index(ins["after"]) + 1, ins["step"])
    for st in [s for s in doc["steps"] if s.get("still")]:   # R88: the still shows the fix, so a second round's
        for s in doc["steps"]:                               # repeat of the still's click saves it again (the later
            if s is not st and s.get("only_if") and s.get("action") == st.get("action"):   # one overwrites)
                s["still"] = st["still"]
    if gen.get("mode") == "improvement":           # R71: the lines that promise a problem switch to their variants
        for st in doc["steps"]:
            v = (st["narration"].get("variants") or {}).get("improvement")
            if v:
                st["narration"]["text"] = v
    doc["variables"] = {**doc["variables"], **(gen.get("variables") or {})}
    for k, v in doc["variables"].items():         # R87: every round's prompt asks for the restart
        if k.startswith("feedback_prompt") and v not in ("@generated", "@runtime") and not v.rstrip().endswith(FEEDBACK_END):
            doc["variables"][k] = v.rstrip() + " " + FEEDBACK_END
    doc["generated"] = {k: gen[k] for k in ("mode", "defect", "notes") if k in gen}
    doc["source_doc"] += f" (merged with {Path(run_dir).name}/generated.json)"
    STEPS_VALIDATOR.validate(doc)
    return doc


def check(doc, from_id):
    """What still keeps the steps from from_id on from running: placeholders, unfilled variables, unbuilt needs."""
    ids = [s["id"] for s in doc["steps"]]
    rest = doc["steps"][ids.index(from_id):]
    problems = [f"{s['id']}: {need} ({by})" for s in rest for need, by in missing(s)]
    problems += [f"variable {k} is still {v}" for k, v in doc["variables"].items() if v in ("@generated", "@runtime")
                 and any("{" + k + "}" in json.dumps(s) for s in rest)]
    problems += [f"{s['id']}: a generated step with no narration text yet" for s in rest
                 if s["segment"] == "generated" and not s["narration"].get("text")]
    return problems


def write(doc, run_dir):
    path = EXERCISES / doc["exercise"] / f"steps_{run_tag(run_dir)}.json"
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(run_dir):
    run_dir = Path(run_dir) if Path(run_dir).exists() else RUNS / run_dir
    pz = json.loads((run_dir / "pause.json").read_text(encoding="utf-8"))
    base = json.loads((EXERCISES / pz["exercise"] / pz["steps_file"]).read_text(encoding="utf-8"))
    gen_p = run_dir / "generated.json"
    doc = merge(base, json.loads(gen_p.read_text(encoding="utf-8")) if gen_p.exists() else None, run_dir)
    problems = check(doc, pz["pause_before"])
    path = write(doc, run_dir)
    print(f"wrote {path}")
    for p in problems:
        print("NOT READY", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1]))
