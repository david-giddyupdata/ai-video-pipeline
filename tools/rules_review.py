"""Outside models review the rulebook for rules tied to one video or tool (R189; docs/ROUND8_NOTES.md section 4.3).

    python tools/rules_review.py <out_dir> [--who=astra,argon] [--rulebook=<path>]

One call per model through OpenRouter, run in parallel and blind to each other: each gets the same prompt and the
rulebook, nothing else, and answers with JSON. Written to <out_dir>/rules_review_<who>.json (the findings, the raw
reply, tokens, cost and seconds). Their answers and Claude's merge go to David, not into the rulebook. Secrets only
through pipeline.config.get_section (R4).
"""
import argparse
import concurrent.futures as cf
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.config import get_section  # noqa: E402

RULEBOOK = ROOT.parent / "Global Assets" / "VIDEO_RULES.md"
MODELS = {"astra": "openai/gpt-6-astra", "argon": "google/gemini-4-argon"}
OR_URL = "https://openrouter.ai/api/v1/chat/completions"

PROMPT = """Below is the rulebook for a series of narrated screen-recording tutorial videos. The rules were written
down one by one while editing the first two videos: a Claude Code exercise in a GitHub Codespace and an Amazon Quick
Sight exercise in a browser. They were recorded by an automated pipeline (OBS, Playwright driving Edge, Remotion for
graphics, an AI voice clone, Adobe Premiere for the final edit), and the editor reviews every video in Premiere.

The same rulebook must now hold for whole video courses: many videos on other software (Tableau, Power BI, Quick
Sight, Python and SQL tools, AI coding assistants), possibly recorded by hand rather than by the pipeline, with other
screens, layouts and narrators.

Review the rulebook for rules that are tied to these first videos, this app, this recorder or tool chain, or this
screen layout, rather than holding for any video in a course. For each such rule:
- say what it is tied to and why that won't hold elsewhere;
- give the rule restated so it holds for any video in a course, keeping its intent and its numbers where they are
  about the viewer (sizes, times, contrast) rather than about the tool;
- say whether a tool-specific detail should move out of the rulebook (into a per-video or per-tool settings file)
  rather than be restated.
Also list any rule that contradicts another, and any number that looks arbitrary for a general rule. Skip rules
that already hold generally; don't praise or summarise.

Answer with JSON only:
{"tied": [{"rule": "the rule id, e.g. S8", "tied_to": "video|app|recorder|toolchain|layout|other", "why": "...",
"restated": "...", "move_out": "what should move to a per-video or per-tool file, or null"}],
"contradictions": [{"rules": ["X1", "Y2"], "what": "..."}],
"arbitrary_numbers": [{"rule": "...", "number": "...", "why": "..."}]}

THE RULEBOOK:

"""


def call(model, text, key):
    payload = {"model": model, "max_tokens": 32000, "usage": {"include": True},
               "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": text}]}
    t0 = time.time()
    for attempt in range(3):
        req = urllib.request.Request(OR_URL, data=json.dumps(payload).encode("utf-8"), headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "AIDV rules review"})
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=900))
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    u = resp.get("usage") or {}
    return resp["choices"][0]["message"]["content"], u, round(time.time() - t0, 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out_dir")
    ap.add_argument("--who", default="astra,argon")
    ap.add_argument("--rulebook", default=str(RULEBOOK))
    a = ap.parse_args(argv)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    text = PROMPT + Path(a.rulebook).read_text(encoding="utf-8")
    key = get_section("openrouter")["api_key"]

    def one(who):
        path = out / f"rules_review_{who}.json"
        if path.exists():                                 # a paid, parsed answer is never asked for twice
            done = json.loads(path.read_text(encoding="utf-8"))
            if done.get("parsed"):
                return who, done
        raw, u, secs = call(MODELS[who], text, key)
        m = re.search(r"\{.*\}", raw or "", re.S)
        try:
            parsed = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            parsed = None
        rec = {"who": who, "model": MODELS[who], "seconds": secs, "prompt_tokens": u.get("prompt_tokens"),
               "completion_tokens": u.get("completion_tokens"), "cost_usd": u.get("cost"), "parsed": parsed is not None,
               "review": parsed, "raw": raw}
        if path.exists() and not parsed:                  # an earlier unparsed answer is kept beside, not lost
            path.rename(path.with_name(f"{path.stem}.unparsed_{int(time.time())}.json"))
        path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
        return who, rec

    with cf.ThreadPoolExecutor(2) as ex:
        for who, rec in ex.map(one, a.who.split(",")):
            n = len((rec.get("review") or {}).get("tied") or [])
            print(f"{who} ({rec['model']}): {n} tied rule(s), parsed {rec['parsed']}, ${rec['cost_usd']}, "
                  f"{rec['seconds']}s")


if __name__ == "__main__":
    main()
