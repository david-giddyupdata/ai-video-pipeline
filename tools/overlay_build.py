"""The overlay build's outside builders (R149, R151; docs/OVERLAY_BUILD_PLAN_qs1a.md): one-off pieces written by
models through OpenRouter under the same brief and the same loop as the Claude builders.

    python tools/overlay_build.py <piece> [<piece> ...] --builders=argon,sol,astra [--cap=14] [--jobs=6]
           [--review=<review folder>]

--review: the review round tools/overlay_review.py init made (its round.json); the harness is configured from it
(overlay_review.configure), every check runs with it, and the brief, costs, scoreboard and replies are the round's
work folder's (research/overlay_build/<prefix>/: copy qs1a/BUILDER_BRIEF.md there first, its first line naming the
video's subject and length). A piece id another exercise's manifest uses is refused (remotion/review/items/ is
shared). Without it: Section A's round 4 and research/overlay_build/qs1a/, as before.

For each piece and builder: the brief (research/overlay_build/qs1a/BUILDER_BRIEF.md), the library code a builder
needs (kit.tsx, pieces.ts, pinned.tsx, TermChip.tsx as an example), the piece's card and two real frames go to the
model; its file is written to remotion/review/items/<piece>.<builder>.tsx and checked (tools/overlay_review.py
check); on problems or warnings it gets the report and the contact sheet and repairs, at most twice (the loop every
builder gets). Each call's cost, as OpenRouter reports it, goes to research/overlay_build/qs1a/costs.json; each
piece's outcome to scoreboard.json. The run stops starting calls once the cap (USD, this run) is reached. The key is
read through the secret store and never printed (R4).
"""
import argparse
import base64
import io
import json
import re
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
QS = ROOT / "research" / "overlay_build" / "qs1a"
ITEMS = ROOT / "remotion" / "review" / "items"
OV = ROOT / "remotion" / "src" / "overlays"
RULEBOOK = ROOT.parent / "Global Assets" / "VIDEO_RULES.md"   # R188 (was R170's checklist): every brief carries it
URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS = {"argon": "google/gemini-4-argon", "sol": "openai/gpt-6.1-sol", "astra": "openai/gpt-6-astra"}
LOCK = threading.Lock()
SPENT = [0.0]


def _orv():
    """tools/overlay_review.py as a module (tools/ isn't a package)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("overlay_review", ROOT / "tools" / "overlay_review.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ORV = _orv()
REVIEW = ORV.REVIEW                # the harness's current review round (Fable's R108 review, item 3)


def configure(review=None):
    """The harness's round (ORV.configure) and the work folder as this module's QS; None keeps Section A's."""
    global REVIEW, QS
    if review is None:
        return
    ORV.configure(review)
    REVIEW, QS = ORV.REVIEW, ORV.WORK

SYSTEM = ("You are a senior motion designer who writes Remotion (React) code. You write one complete TypeScript file "
          "exactly to the brief's contract. Reply with the file in a single ```tsx fenced block, then at most three "
          "short lines on your choices. No other code blocks.")


def jpeg_b64(path, w=960):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im = im.resize((w, round(im.height * w / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def context_text():
    parts = [(QS / "BUILDER_BRIEF.md").read_text(encoding="utf-8"),
             "\n\n" + RULEBOOK.read_text(encoding="utf-8")]   # R188: David's preferences, one rulebook
    for name in ("kit.tsx", "pieces.ts", "pinned.tsx", "TermChip.tsx"):
        parts.append(f"\n\n# remotion/src/overlays/{name}\n```tsx\n{(OV / name).read_text(encoding='utf-8')}\n```")
    tok = json.loads((OV / "tokens.json").read_text(encoding="utf-8"))
    parts.append("\n\n# tokens.json (color, type, layout, motion)\n```json\n" +
                 json.dumps({k: tok[k] for k in ("color", "type", "layout", "motion")}, indent=1) + "\n```")
    return "".join(parts)


def frames_for(card, plan):
    """The real frames under the piece at its entrance and its mid-hold (from the harness's frame cache)."""
    orv = ORV
    ly = card["layer"]
    ats = [it["at"] for it in ly.get("items", [])] or [ly["t0"]]
    times = [ly["t0"] + 0.5, (max(ats) + ly["t1"]) / 2]
    fr = orv.frames_of(times, plan)
    return [fr[max(0, min(plan["durationInFrames"] - 1, round(t * plan["fps"])))] for t in times], times


def call(model, messages, key):
    payload = {"model": model, "max_tokens": 16000, "usage": {"include": True}, "reasoning": {"effort": "medium"},
               "messages": messages}
    t0 = time.time()
    for attempt in range(3):
        req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"), headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "AIDV overlay build"})
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=900))
            break
        except Exception as e:                            # a dropped connection or a short read: retried
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    u = resp.get("usage") or {}
    if u.get("cost") is None:                             # a call with no reported cost would never advance the cap
        raise RuntimeError(f"{model}: OpenRouter reported no cost for this call; stopping rather than guessing")
    return resp, {"model": resp.get("model", model), "seconds": round(time.time() - t0, 1),
                  "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                  "cost_usd": u.get("cost")}


def log_cost(rec):
    with LOCK:
        SPENT[0] += rec["cost_usd"] or 0.0
        p = ORV.writable(QS / "costs.json")
        rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        rows.append(rec)
        p.write_text(json.dumps(rows, indent=1), encoding="utf-8")


def extract(text):
    m = re.findall(r"```(?:tsx|typescript|ts)?\s*\n(.*?)```", text or "", flags=re.S)
    return max(m, key=len) if m else None


def run_check(key):
    r = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "overlay_review.py"), "check", key] +
                       ([f"--review={ORV.CONFIGURED}"] if ORV.CONFIGURED else []),   # the same round's check
                       cwd=ROOT, capture_output=True, text=True)
    rep_p = REVIEW / "checks" / f"{key}.json"
    return json.loads(rep_p.read_text(encoding="utf-8")) if rep_p.exists() else {"status": "fail", "problems": [
        f"check crashed: {(r.stderr or r.stdout)[-1500:]}"], "warnings": []}


def build_one(pid, builder, key_, ctx, plan, cap):
    orv = ORV
    card = json.loads((REVIEW / "cards" / f"{pid}.json").read_text(encoding="utf-8"))
    key = f"{pid}.{builder}"
    frames, times = frames_for(card, plan)
    card_text = json.dumps({"piece": pid, "builder": builder, "file": f"remotion/review/items/{key}.tsx",
                            "what": card["review"].get("what"), "card": card["review"].get("card"),
                            "source": card["review"].get("source"), "layer_at_render_time": card["layer"],
                            "items_timecodes": card["items_tc"], "on_screen": f"{card['t0_tc']} to {card['t1_tc']}"},
                           indent=1)
    user = [{"type": "text", "text": ctx + "\n\n# YOUR PIECE (its card)\n```json\n" + card_text + "\n```\n\n"
             f"The two images are the real screen under your piece at {orv.tc(times[0])} (its entrance) and "
             f"{orv.tc(times[1])} (mid-hold), at half size (multiply positions by 2 for frame px). Write "
             f"remotion/review/items/{key}.tsx."},
            {"type": "image_url", "image_url": {"url": jpeg_b64(frames[0])}},
            {"type": "image_url", "image_url": {"url": jpeg_b64(frames[1])}}]
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    outcome = {"piece": pid, "builder": builder, "attempts": 0, "status": "fail", "cost_usd": 0.0, "seconds": 0.0,
               "passed_after": None, "warnings_left": None}
    best_code, best_warnings = None, None
    for attempt in range(3):                              # the first build and at most two repairs
        if SPENT[0] >= cap:
            outcome["stopped"] = f"cap ${cap} reached"
            break
        try:
            resp, rec = call(MODELS[builder], messages, key_)
        except Exception as e:
            outcome["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            break
        rec.update({"what": f"build {key} attempt {attempt + 1}", "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        log_cost(rec)
        outcome["attempts"] += 1
        outcome["cost_usd"] = round(outcome["cost_usd"] + (rec["cost_usd"] or 0), 6)
        outcome["seconds"] = round(outcome["seconds"] + rec["seconds"], 1)
        text = resp["choices"][0]["message"].get("content") or ""
        ORV.writable(QS / "builds" / key).mkdir(parents=True, exist_ok=True)
        (QS / "builds" / key / f"reply_{attempt + 1}.md").write_text(text, encoding="utf-8")
        code = extract(text)
        if not code:
            rep = {"status": "fail", "problems": ["no ```tsx block in the reply"], "warnings": []}
        else:
            (ITEMS / f"{key}.tsx").write_text(code, encoding="utf-8")
            rep = run_check(key)
        if rep["status"] == "pass":                       # the best passing file so far, kept to fall back on
            best_code, best_warnings = code, len(rep.get("warnings", []))
        outcome["status"], outcome["warnings_left"] = rep["status"], len(rep.get("warnings", []))
        if rep["status"] == "pass" and not rep.get("warnings"):
            outcome["passed_after"] = attempt
            break
        if rep["status"] == "pass" and outcome["passed_after"] is None:
            outcome["passed_after"] = attempt
        if attempt == 2:
            break
        fix = [{"type": "text", "text": "The check's report on your file:\n```json\n" + json.dumps(
            {k: rep.get(k) for k in ("status", "problems", "warnings")}, indent=1) + "\n```\n" +
            ("Its contact sheet follows (your piece over the real frames at its key times; each panel is labelled). "
             if rep.get("sheet") else "") + "Fix every problem and any warning you can, and reply with the whole "
             "corrected file in one ```tsx block."}]
        if rep.get("sheet"):
            fix.append({"type": "image_url", "image_url": {"url": jpeg_b64(rep["sheet"], w=1280)}})
        messages += [{"role": "assistant", "content": text}, {"role": "user", "content": fix}]
    if outcome["status"] != "pass" and best_code:         # a repair that failed never replaces a version that passed
        (ITEMS / f"{key}.tsx").write_text(best_code, encoding="utf-8")
        rep = run_check(key)                              # so its check (and file hash) are of the file on disk
        outcome.update({"status": rep["status"], "warnings_left": len(rep.get("warnings", [])),
                        "restored": f"the last passing attempt (with {best_warnings} warning(s))"})
    with LOCK:
        p = ORV.writable(QS / "scoreboard.json")
        board = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        board[key] = outcome
        p.write_text(json.dumps(board, indent=1), encoding="utf-8")
    print(json.dumps(outcome), flush=True)
    return outcome


def main(argv=None):
    from pipeline.config import get_section
    orv = ORV
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pieces", nargs="+")
    ap.add_argument("--builders", default="argon,sol,astra")
    ap.add_argument("--cap", type=float, default=14.0)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--review", default=None, help="the review folder overlay_review.py init made; none: Section A's")
    a = ap.parse_args(argv)
    configure(a.review)
    if a.review:
        if not (QS / "BUILDER_BRIEF.md").exists():
            raise SystemExit(f"no {QS / 'BUILDER_BRIEF.md'}: copy research/overlay_build/qs1a/BUILDER_BRIEF.md there "
                             "and change its first line (the video's subject and length)")
        other = ORV.foreign_ids()
        clash = [p for p in a.pieces if p in other]
        if clash:
            raise SystemExit("piece ids another exercise's manifest uses (remotion/review/items/ is shared): "
                             + " ".join(f"{p} ({other[p]})" for p in clash))
        missing = [p for p in a.pieces if not (REVIEW / "cards" / f"{p}.json").exists()]
        if missing:
            raise SystemExit(f"no card in {REVIEW / 'cards'} for: {' '.join(missing)} (run overlay_review.py cards)")
    key_ = get_section("openrouter")["api_key"]
    ctx = context_text()
    plan = orv.load_plan()
    jobs = [(p, b) for p in a.pieces for b in a.builders.split(",")]
    with ThreadPoolExecutor(a.jobs) as ex:
        outs = list(ex.map(lambda pb: build_one(pb[0], pb[1], key_, ctx, plan, a.cap), jobs))
    print(f"done: {sum(o['status'] == 'pass' for o in outs)} of {len(outs)} pass; this run ${SPENT[0]:.2f}")


if __name__ == "__main__":
    main()
