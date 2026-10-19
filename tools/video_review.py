"""Outside models review a finished video for defects, blind to each other (R191; docs/ROUND8_NOTES.md section 5).

    python tools/video_review.py frames <video.mp4> <out_dir> [--fps=5]     # frames for a frame reviewer
    python tools/video_review.py argon <frames_dir> <out_dir> [--per=60] [--jobs=6]   # Gemini 4 Argon, OpenRouter
    python tools/video_review.py gemini <video.mp4> <out_dir> [--model=gemini-3.1-pro-preview]   # Google, the video

Both get the same rubric (RUBRIC) and none of David's notes; each returns findings as JSON by video time, written to
<out_dir>/findings_<who>.json with the call's tokens, cost and seconds (costs.json beside it). Frames are 768 px wide,
about what Gemini samples a video at, so the two see the same detail. Secrets only through
pipeline.config.get_section (R4).
"""
import argparse
import base64
import concurrent.futures as cf
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.config import get_section, tool  # noqa: E402

RUBRIC = """You are reviewing a finished, narrated screen-recording tutorial (software: Amazon Quick Sight; 1920x1080;
captions burned in; animated graphics laid over the screen) just before it is published on YouTube, for viewers
watching on phones held sideways. Find every defect a careful human editor would fix before publishing. Look at least
for:
- Sound (if you can hear it): double breaths or a breath cut in two, clicks or pops, a word cut off, a level that
  jumps, a silence longer than about 2 seconds.
- Captions: a caption covering something the narration is talking about, something about to be clicked, or
  something changing on screen; captions jumping from side to side; wrong words.
- Pointing things out: the narration (or the caption) names something visible on screen (a button, field, pane,
  value, label) but nothing points to it: no rectangle, arrow or highlight.
- Timing: a graphic, or the last part of it, gone before it can be read (under about 2 seconds); a click before the
  narration has said or read what is clicked; something shown before it is mentioned.
- Picture: flicker, flashing or blinking text, a jump, a stray frame, a browser pop-up or autofill list in the way,
  something covering what the viewer needs, important things too close to the frame's edge.
- Graphics: text hard to read (low contrast), see-through backgrounds behind text, text not lined up (rows or
  columns), text cut off or overflowing its box, text too small for a phone.
Report only what you can actually see or hear; no guesses, no praise, no general advice. Answer with JSON only:
{"findings": [{"t_start": "MM:SS.s", "t_end": "MM:SS.s", "category": "sound|captions|pointing|timing|picture|graphics",
"what": "one sentence", "severity": "high|medium|low"}]} with times measured from the start of the video."""

OR_URL = "https://openrouter.ai/api/v1/chat/completions"


def mmss(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def cmd_frames(a):
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", a.video, "-vf", f"fps={a.fps},scale=768:-2",
                    "-q:v", "4", str(out / "f_%05d.jpg")], check=True)
    n = len(list(out.glob("f_*.jpg")))
    (out / "frames.json").write_text(json.dumps({"fps": a.fps, "count": n, "video": a.video}), encoding="utf-8")
    print(f"{n} frames at {a.fps} fps -> {out}")


def or_call(model, content, key):
    payload = {"model": model, "max_tokens": 16000, "usage": {"include": True},
               "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": content}]}
    t0 = time.time()
    for attempt in range(3):
        req = urllib.request.Request(OR_URL, data=json.dumps(payload).encode("utf-8"), headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "AIDV video review"})
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=900))
            break
        except Exception as e:                            # a dropped connection or a short read: retried
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    u = resp.get("usage") or {}
    if u.get("cost") is None:                             # the paid answer is kept; the missing cost is flagged in
        print(f"WARNING: no cost reported: {json.dumps(u)[:300]}", flush=True)   # the chunk's record (R149)
    return resp["choices"][0]["message"]["content"], u, round(time.time() - t0, 1)


def parse(text):
    """The findings, or None when the reply isn't the JSON asked for (cut off, say): never read as 'no findings'."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)).get("findings", []) if m else None
    except json.JSONDecodeError:
        return None


def cmd_argon(a):
    src, out = Path(a.frames_dir), Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta = json.loads((src / "frames.json").read_text(encoding="utf-8"))
    fps, frames = meta["fps"], sorted(src.glob("f_*.jpg"))
    key = get_section("openrouter")["api_key"]
    chunks = [frames[i:i + a.per] for i in range(0, len(frames), a.per)]
    done_dir = out / "argon_chunks"                       # each paid chunk is kept as it lands; a re-run skips it
    done_dir.mkdir(exist_ok=True)

    def run(k):
        done = done_dir / f"chunk_{k:03d}.json"
        if done.exists():
            d = json.loads(done.read_text(encoding="utf-8"))
            return k, d["findings"], d["cost"]
        fs = chunks[k]
        t0 = (k * a.per) / fps
        content = [{"type": "text", "text": RUBRIC + f"\n\nYou see frames {mmss(t0)} to {mmss(t0 + len(fs) / fps)} of "
                    f"the video, {fps} frames a second, each labelled with its time. There is no sound."}]
        for i, f in enumerate(fs):
            t = (k * a.per + i) / fps
            content.append({"type": "text", "text": f"Frame at {mmss(t)}"})
            content.append({"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64," + base64.b64encode(f.read_bytes()).decode()}})
        try:
            text, u, secs = or_call(a.model, content, key)
        except BaseException as e:                        # one failed chunk doesn't lose the others' paid results
            return k, None, {"chunk": k, "t0": t0, "error": str(e)[:300], "cost_usd": 0.0, "seconds": 0}
        fnd = parse(text)
        cost = {"chunk": k, "t0": t0, "frames": len(fs), "seconds": secs, "parsed": fnd is not None,
                "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                "cost_usd": u.get("cost")}
        if fnd is not None:
            done.write_text(json.dumps({"findings": fnd, "cost": cost, "raw": text}, indent=1), encoding="utf-8")
        else:
            (done_dir / f"chunk_{k:03d}.unparsed.txt").write_text(text or "", encoding="utf-8")
        return k, fnd, cost
    findings, costs, failed = [], [], []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for k, fs, c in ex.map(run, range(len(chunks))):
            costs.append(c)
            if fs is None:
                failed.append(k)
                print(f"chunk {k}: FAILED ({c.get('error') or 'reply not JSON'}), ${c['cost_usd'] or 0:.4f}", flush=True)
                continue
            findings += fs
            print(f"chunk {k}: {len(fs)} finding(s), ${c['cost_usd'] or 0:.4f}" + ("" if c["cost_usd"] is not None
                  else " (cost NOT reported)") + f", {c['seconds']}s", flush=True)
    if failed:
        print(f"chunks {failed} failed: run again to retry only those")
    who = "argon_frames"
    (out / f"findings_{who}.json").write_text(json.dumps({"model": a.model, "input": f"{fps} fps frames, 768 px, no sound",
                                                          "findings": findings}, indent=1), encoding="utf-8")
    (out / f"costs_{who}.json").write_text(json.dumps(costs, indent=1), encoding="utf-8")
    print(f"{len(findings)} findings, ${sum(c['cost_usd'] or 0 for c in costs):.3f}, "
          f"{sum(c['seconds'] for c in costs):.0f}s of calls")


def cmd_gemini(a):
    from google import genai
    from google.genai import types
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=get_section("google")["api_key"])
    t0 = time.time()
    f = client.files.upload(file=a.video)
    while f.state and f.state.name == "PROCESSING":       # the video is processed before it can be used
        time.sleep(10)
        f = client.files.get(name=f.name)
    if f.state and f.state.name != "ACTIVE":
        raise SystemExit(f"upload failed: {f.state}")
    r = client.models.generate_content(model=a.model, contents=[f, RUBRIC + "\n\nYou are given the whole video, with "
                                       "its sound."], config=types.GenerateContentConfig(
                                           response_mime_type="application/json", max_output_tokens=32768))
    um = r.usage_metadata
    secs = round(time.time() - t0, 1)
    usage = {"prompt_tokens": um.prompt_token_count, "completion_tokens": um.candidates_token_count,
             "thinking_tokens": getattr(um, "thoughts_token_count", None), "seconds": secs}
    # Google reports tokens, not cost: DeepThink's table ($1.25 / $10 per million for gemini-3.1-pro-preview), and
    # Gemini Pro's long-context tier (twice the input, 1.5x the output) assumed above 200,000 prompt tokens
    long_ctx = (usage["prompt_tokens"] or 0) > 200_000
    pin, pout = (2.5, 15.0) if long_ctx else (1.25, 10.0)
    usage["cost_usd_estimate"] = round(((usage["prompt_tokens"] or 0) * pin + ((usage["completion_tokens"] or 0) +
                                        (usage["thinking_tokens"] or 0)) * pout) / 1e6, 4)
    who = "gemini_video"
    (out / f"raw_{who}.txt").write_text(r.text or "", encoding="utf-8")   # the paid reply, kept whatever its shape
    findings = parse(r.text)
    usage["parsed"] = findings is not None
    (out / f"findings_{who}.json").write_text(json.dumps({"model": a.model, "input": "the video with sound (Google's "
                                                          "default sampling)", "findings": findings or []}, indent=1),
                                              encoding="utf-8")
    (out / f"costs_{who}.json").write_text(json.dumps(usage, indent=1), encoding="utf-8")
    try:
        client.files.delete(name=f.name)                  # the upload isn't kept at Google
    except Exception:
        pass
    print(f"{len(findings) if findings is not None else 'UNPARSED'} findings; usage {json.dumps(usage)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("frames")
    f.add_argument("video")
    f.add_argument("out_dir")
    f.add_argument("--fps", type=float, default=5)
    g = sp.add_parser("argon")
    g.add_argument("frames_dir")
    g.add_argument("out_dir")
    g.add_argument("--per", type=int, default=60)
    g.add_argument("--jobs", type=int, default=6)
    g.add_argument("--model", default="google/gemini-4-argon")
    v = sp.add_parser("gemini")
    v.add_argument("video")
    v.add_argument("out_dir")
    v.add_argument("--model", default="gemini-3.1-pro-preview")
    a = ap.parse_args(argv)
    {"frames": cmd_frames, "argon": cmd_argon, "gemini": cmd_gemini}[a.cmd](a)


if __name__ == "__main__":
    main()
