"""The avatar's intro and outro (R57, R97): HeyGen lip-syncs David's look to lines already voiced in the clone.

    python -m pipeline.edit.avatar <avatar steps file> runs/<run_id> [--no-render] [--rerender]
    python -m pipeline.edit.avatar webapp <avatar steps file> runs/<run_id> opening|recap <render.webm> <upload.wav>
                                   --engine=avatar_v [--notes=...] [--open-head=0.58]   # R244: register_webapp

With "output_format": "webm" in the steps file's "heygen" block, the renders are transparent (R206) and go through
main_alpha instead (its docstring): resumable, logged apart, kept whole as ProRes 4444 for the avatar's stage.

The steps file lists the lines (voiced first by pipeline.narration.build, so their audio is in audio_cache/) and its
"heygen" block names the look, the engine and the resolution. Each step's "graphics" field says where its clip goes:
"opening" or "recap". For each line: upload its audio (POST /v3/assets), render (POST /v3/videos, type avatar, the
audio as audio_asset_id), poll (GET /v3/videos/{id}) and download to runs/<id>/avatar/. The wallet balance before
and after each render goes in runs/<id>/avatar/avatar.json, which is the cost of that render.

The audio uploaded is the line's cleaned clip (pipeline.narration.clean) with PAD_S of silence on both sides, so
HeyGen renders the avatar idling there: the dissolves run on real frames, never a freeze (David, 2026-10-12).

Then runs/<id>/graphics/<opening|recap>_<video id>.mp4, the files the Premiere splice (pipeline.edit.premiere, R69)
places around the camera sequence, trimmed from the render and scaled to the plan's frame and rate. The opening keeps
OPEN_HEAD_S before its voice and OPEN_TAIL_S after it (the dissolve into the camera runs on that tail). The recap keeps
RECAP_HEAD_S before its voice (the dissolve in runs on its start, and the voice waits until it is over) and
RECAP_TAIL_S after it, before the hard cut to the logo (R96). Each render gets a file of its own, since an open
Premiere project locks the one it uses. --no-render skips HeyGen and rebuilds what is missing from clips already
downloaded. avatar.json's "graphics" block names each graphic's file, its line and where its voice starts, for the
splice and the full sequence's captions.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import numpy as np

from pipeline.config import EXERCISES, ROOT, get_section, tool
from pipeline.narration import clean, timing

API = "https://api.heygen.com"
CACHE = ROOT / "audio_cache"
PAD_S = 1.5                             # silence uploaded on both sides of the line: HeyGen renders the avatar idling
OPEN_HEAD_S, OPEN_TAIL_S = 0.3, 1.2     # the tail holds the 1.0 s dissolve into the camera, after 0.2 s of idling
RECAP_HEAD_S, RECAP_TAIL_S = 1.0, 0.5   # the 0.8 s dissolve in (premiere SLIDE_LEAD_S), then 0.2 s, then the voice


def call(method, path, body=None, files=None, timeout=120):
    headers = {"X-Api-Key": get_section("heygen")["api_key"], "Accept": "application/json"}
    data = None
    if files:                                             # multipart/form-data, one file field
        b = uuid.uuid4().hex
        name, payload, ctype = files
        data = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode() + payload + f"\r\n--{b}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={b}"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HeyGen {method} {path}: {e.code} {e.read().decode('utf-8', 'replace')[:400]}") from None


def wallet():
    d = call("GET", "/v3/users/me").get("data", {})
    return (d.get("wallet") or {}).get("remaining_balance")


def carry_part(key, until_word, tmp, prov=None):
    """R205: the start of a carried line, up to the silence before until_word, as the line's cleaned audio (the same
    clip the main body plays). The cut is where that silence starts, found in the audio (breaths.beat_point), never at
    the logged word end, which ElevenLabs logs late (GOTCHAS). prov: the carried line's timing.provenance() (R227;
    the search runs between word starts either way). Returns the samples and the cut in seconds."""
    from pipeline.narration import breaths
    words = timing.of({"key": key, **(prov or {})})["words"]
    norm = lambda w: re.sub(r"[^a-z0-9']", "", w.lower())               # as pipeline.edit.stage.at_word
    i = next(k for k, w in enumerate(words) if k and norm(w["word"]) == norm(until_word))
    clean.clean(CACHE / f"{key}.mp3", tmp)
    cut = breaths.beat_point(tmp, words[i - 1]["start"], words[i]["start"])
    if cut is None:
        raise SystemExit(f"no silence found before {until_word!r} in {key}")
    x = clean.decode(tmp)
    tmp.unlink()
    return x[:int(round(cut * clean.SR))], cut


def padded(mp3, dst, carry=None, carry_prov=None):
    """The line's cleaned clip with PAD_S of silence before and after, as a WAV to upload. carry: (key, until_word,
    gap_s), the start of the main body's first line after gap_s (R205), lip-synced in the same render, its words timed
    as carry_prov says (R227). Returns the file and where its parts are (seconds into the upload)."""
    tmp = dst.with_suffix(".clean.wav")
    clean.clean(mp3, tmp)
    x = clean.decode(tmp)
    tmp.unlink()
    z = np.zeros(int(PAD_S * clean.SR), np.float32)
    parts, info = [z, x], {"voice_at_s": PAD_S, "voice_s": round(len(x) / clean.SR, 3)}
    if carry:
        key, until, gap = carry
        y, cut = carry_part(key, until, dst.with_suffix(".carry.wav"), carry_prov)
        parts += [np.zeros(int(round(gap * clean.SR)), np.float32), y]
        info["carry"] = {"key": key, "until_word": until, "gap_s": gap, "cut_s": cut,
                         "at_s": round(PAD_S + (len(x) + int(round(gap * clean.SR))) / clean.SR, 3)}
    clean.write_wav(dst, np.concatenate(parts + [z]))
    return dst, info


def render(audio, look, engine, resolution, title, out, output_format="mp4", background=None):
    """Upload, render and download (submit, then fetch). output_format "webm": the avatar on a transparent background
    (R206), for a look trained with background separation; HeyGen refuses it otherwise ("The avatar must be trained
    with matting enabled"). background: an image file HeyGen puts behind the avatar instead of the look's own room
    (its remove_background, the same matte as the WebM), an MP4; HeyGen rejects it with webm."""
    ids = submit(audio, look, engine, resolution, title, output_format, background)
    return {**ids, **fetch(ids["video_id"], out)}


def submit(audio, look, engine, resolution, title, output_format="mp4", background=None):
    """render()'s first half: upload and submit; returns the ids, for a log written before the wait."""
    ctype = "audio/wav" if audio.suffix == ".wav" else "audio/mpeg"
    asset = call("POST", "/v3/assets", files=(audio.name, audio.read_bytes(), ctype))["data"]["asset_id"]
    body = {"type": "avatar", "avatar_id": look, "audio_asset_id": asset, "engine": {"type": engine},
            "resolution": resolution, "aspect_ratio": "16:9", "title": title}
    if output_format != "mp4":
        body["output_format"] = output_format
    ids = {"asset_id": asset}
    if background:
        bg = Path(background)
        ids["background_asset_id"] = call("POST", "/v3/assets", files=(
            bg.name, bg.read_bytes(), "image/jpeg" if bg.suffix.lower() in (".jpg", ".jpeg") else "image/png"))[
            "data"]["asset_id"]
        body.update(background={"type": "image", "asset_id": ids["background_asset_id"]}, remove_background=True)
    vid = call("POST", "/v3/videos", body)["data"]["video_id"]
    print(f"  {title}: asset {asset}, video {vid}; rendering")
    return {**ids, "video_id": vid}


NET_ERRORS = (OSError, urllib.error.URLError)          # a dropped connection (WinError 10054), a timeout
NET_TRIES = 8


def _retry(what, f):
    for i in range(NET_TRIES):
        try:
            return f()
        except NET_ERRORS as e:                            # an HTTP error is a RuntimeError from call(): not retried
            if i == NET_TRIES - 1:
                raise
            print(f"  {what}: {e!r}; retrying in {5 * 2 ** i} s")
            time.sleep(5 * 2 ** i)


def fetch(vid, out):
    """render()'s second half: wait for video vid and download it to out, retrying dropped connections (HeyGen reset
    one mid-download, 2026-10-16), so a render already paid for is never lost or submitted twice."""
    t0 = time.time()
    while True:
        d = _retry("poll", lambda: call("GET", f"/v3/videos/{vid}")["data"])
        if d["status"] == "completed":
            break
        if d["status"] == "failed":
            raise RuntimeError(f"HeyGen render failed: {d.get('failure_code')} {d.get('failure_message')}")
        if time.time() - t0 > 3600:
            raise RuntimeError(f"HeyGen render {vid} still {d['status']} after an hour")
        time.sleep(15)
    part = out.with_name("_part_" + out.name)
    _retry("download", lambda: urllib.request.urlretrieve(d["video_url"], part))
    part.replace(out)
    return {"render_s": round(time.time() - t0), "duration_s": d.get("duration")}


def probe(path):
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate"
                          ":format=duration", "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def to_graphics(src, dst, fps, W, H, start_s, dur_s):
    """The part of the HeyGen render from start_s for dur_s, at the plan's size and rate (real frames only)."""
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={fps},"
          "format=yuv420p")
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{start_s:.3f}", "-i", str(src), "-t", f"{dur_s:.3f}",
                    "-vf", vf, "-af", "aresample=48000", "-ac", "2", "-c:v", "libx264", "-crf", "16", "-preset",
                    "medium", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)], check=True)


def main(steps_path, run_dir, do_render=True, rerender=False):
    run_dir = Path(run_dir).resolve()
    doc = json.loads(Path(steps_path).read_text(encoding="utf-8"))
    lines = json.loads((EXERCISES / doc["exercise"] / "lines.json").read_text(encoding="utf-8"))
    hg = doc["heygen"]
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    (run_dir / "avatar").mkdir(exist_ok=True)
    (run_dir / "graphics").mkdir(exist_ok=True)
    log_path = run_dir / "avatar" / "avatar.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {"renders": {}}
    fmt = hg.get("output_format", "mp4")
    if fmt == "webm":                     # R206: transparent renders, logged apart, so the MP4 builds keep theirs
        return main_alpha(doc, lines, hg, plan, run_dir, log, log_path, do_render, rerender)
    for step in doc["steps"]:
        seq, line = step["graphics"], lines[step["narration"]["line_id"]]
        if do_render:
            raw = run_dir / "avatar" / f"{seq}_heygen_{int(time.time())}.mp4"
            upload, _ = padded(CACHE / f"{line['key']}.mp3", run_dir / "avatar" / f"{seq}_upload.wav")
            before = wallet()
            r = render(upload, hg["look"], hg["engine"], hg["resolution"], f"{run_dir.name} {seq}", raw)
            after = wallet()
            r.update({"line_id": step["narration"]["line_id"], "audio_key": line["key"], "audio_s": line["length_s"],
                      "engine": hg["engine"], "look": hg["look"], "pad_s": PAD_S, "file": raw.name,
                      "wallet_before": before, "wallet_after": after,
                      "cost_usd": round(before - after, 4) if before is not None and after is not None else None})
            log["renders"][seq] = r
            log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
            print(f"  {seq}: {r['duration_s']} s rendered in {r['render_s']} s; wallet {before} -> {after}")
        r = log["renders"][seq]
        raw, pad = run_dir / "avatar" / r.get("file", f"{seq}_heygen.mp4"), r.get("pad_s", 0.0)
        if pad < max(OPEN_HEAD_S, OPEN_TAIL_S, RECAP_HEAD_S, RECAP_TAIL_S):
            raise SystemExit(f"{seq}: the render has {pad} s of padding; render it again (without --no-render)")
        head, tail = (OPEN_HEAD_S, OPEN_TAIL_S) if seq == "opening" else (RECAP_HEAD_S, RECAP_TAIL_S)
        dst = run_dir / "graphics" / f"{seq}_{r['video_id'][:8]}.mp4"     # its own file: an open project locks
        if not dst.exists():                                               # the one it uses
            to_graphics(raw, dst, plan["fps"], plan["width"], plan["height"], pad - head, head + r["audio_s"] + tail)
        # what the splice and the full sequence's captions need: the file, its line, and where its voice starts
        log.setdefault("graphics", {})[seq] = {"file": f"graphics/{dst.name}", "line_id": step["narration"]["line_id"],
                                               "audio_key": line["key"], "voice_at_s": head, "tail_s": tail,
                                               **timing.provenance(line)}    # R227: its captions take the line's times
        log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
        p = probe(dst)
        print(f"  graphics/{dst.name}: {float(p['format']['duration']):.2f} s "
              f"(HeyGen {float(probe(raw)['format']['duration']):.2f} s, voice at {head} s, {tail} s after it)")
    return log


def main_alpha(doc, lines, hg, plan, run_dir, log, log_path, do_render, rerender=False):
    """R206: the avatar on a transparent background, WebM from HeyGen (R207 step 1), kept whole as ProRes 4444 with
    alpha with its edges fixed (pipeline.edit.alpha), for the avatar's stage (the Remotion composition places and
    trims it). A step's "carry_into" ({"line_id", "until_word"}) appends that line's start, up to the silence before
    until_word, after the part boundary's gap (R205, R82), so the avatar lip-syncs the main body's first sentence in
    the same render. Logged in avatar.json under "renders_alpha" and "graphics_alpha".

    Paid once (Fable, stage r1): each submission is logged ("submitted", its video id) before the wait, and a
    submitted render is always fetched first, whatever has changed since, so one already paid for is never orphaned;
    a render HeyGen failed is marked "failed" and the next run submits anew. A step rendered from other inputs (its
    line, the carried line and gap, the look and engine) stops the run unless --rerender; a replaced record moves to
    "renders_alpha_history", never overwritten."""
    from pipeline.edit import alpha
    pace = plan["settings"]["pacing"]
    gap = round(pace["gap_between_lines"] + pace["pause_at_part_boundary"], 3)     # R82: about 1.2 s
    renders = log.setdefault("renders_alpha", {})
    save = lambda: log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    def finish(r, raw):
        try:
            r.update(fetch(r["video_id"], raw))
        except RuntimeError as e:                          # HeyGen says failed, or an hour passed: free the step
            r.update({"status": "failed", "error": str(e)})
            save()
            raise SystemExit(f"video {r['video_id']}: {e}; the next run submits it again")
        after = wallet()
        r.update({"status": "done", "wallet_after": after, "cost_usd": round(r["wallet_before"] - after, 4)
                  if r.get("wallet_before") is not None and after is not None else None})
        save()

    for step in doc["steps"]:
        seq, line = step["graphics"], lines[step["narration"]["line_id"]]
        c = step.get("carry_into")
        inputs = {"audio_key": line["key"], "look": hg["look"], "engine": hg["engine"], "resolution": hg["resolution"],
                  "carry": [lines[c["line_id"]]["key"], c["until_word"], gap] if c else None, "pad_s": PAD_S}
        # R234: a line shortened at its start (pipeline.narration.cut_head) is served by the render of the clip it was
        # cut from, starting cut_s later: that render counts as current when its inputs are the line's but for that
        # clip's key. A new render (another engine or look, or --rerender) uploads the short clip.
        cut = json.loads((CACHE / f"{line['key']}.json").read_text(encoding="utf-8")).get("cut_from")
        served = {**inputs, "audio_key": cut["key"]} if cut and not rerender else None
        current = lambda rr: rr.get("inputs") == inputs or (served is not None and rr.get("inputs") == served)
        r = renders.get(seq)
        if r and r.get("source") == "webapp":             # R244: made in the web app on plan credits, registered by
            print(f"  {seq}: the web app's render ({r['file']}), registered by `webapp`: kept")   # register_webapp;
            continue                                      # never re-submitted here (the API would bill the wallet)
        if r and r.get("source") == "still" and not do_render:   # R245: pipeline.edit.still_avatar's registered still
            print(f"  {seq}: the still ({r['file']}), registered by still_avatar: kept")   # (no video_id, no ProRes);
            continue                                      # a paid render goes on to "rendered from other inputs" below
        if do_render and r and r.get("status") == "submitted":
            print(f"  {seq}: resuming video {r['video_id']}, submitted earlier")
            finish(r, run_dir / "avatar" / r["file"])
            if not current(r):
                print(f"  {seq}: that render was made from other inputs than the steps file's now")
        r = renders.get(seq)
        done = r is not None and r.get("status") == "done" and (run_dir / "avatar" / r["file"]).exists()
        if do_render and r and r.get("status") == "done" and not done and not rerender:
            raise SystemExit(f"{seq}: its render ({r['file']}) is missing from avatar/; a new render costs money: "
                             "run with --rerender to make it")
        if do_render and done and not current(r) and not rerender:
            raise SystemExit(f"{seq}: rendered from other inputs ({r.get('inputs')} against {inputs}); a new render "
                             "costs money: run with --rerender to make it")
        if do_render and not (done and current(r)):
            if r:
                log.setdefault("renders_alpha_history", []).append({"graphics": seq, **r})
            stamp = int(time.time())
            raw = run_dir / "avatar" / f"{seq}_heygen_alpha_{stamp}.webm"
            carry = tuple(inputs["carry"]) if c else None
            upload, parts = padded(CACHE / f"{line['key']}.mp3", run_dir / "avatar" / f"{seq}_upload_alpha_{stamp}.wav",
                                   carry, timing.provenance(lines[c["line_id"]]) if c else None)
            if carry:
                parts["carry"]["line_id"] = c["line_id"]
            before = wallet()
            r = renders[seq] = {"status": "submitted", "inputs": inputs, "line_id": step["narration"]["line_id"],
                                "audio_key": line["key"], "audio_s": line["length_s"], "engine": hg["engine"],
                                "look": hg["look"], "pad_s": PAD_S, "file": raw.name, "upload": upload.name, **parts,
                                "wallet_before": before,
                                **submit(upload, hg["look"], hg["engine"], hg["resolution"],
                                         f"{run_dir.name} {seq} alpha", output_format="webm")}
            save()
            finish(r, raw)
            print(f"  {seq}: {r['duration_s']} s rendered in {r['render_s']} s; wallet {before} -> {r['wallet_after']}")
        r = renders.get(seq)
        if r is None:
            raise SystemExit(f"{seq}: never rendered; run without --no-render")
        if r.get("status") == "submitted":
            raise SystemExit(f"{seq}: video {r.get('video_id')} isn't downloaded yet; run again to resume it")
        if r.get("status") != "done":
            raise SystemExit(f"{seq}: its render {r.get('status')} ({r.get('error')}); a new run submits it again (paid)")
        raw = run_dir / "avatar" / r["file"]
        dst = run_dir / "graphics" / f"{seq}_{r['video_id'][:8]}_alpha.mov"
        if not dst.exists():
            alpha.to_prores(raw, dst, premultiplied=alpha.PREMULTIPLIED[r.get("source", "api")])
        g = {k: r[k] for k in ("line_id", "audio_key", "voice_at_s", "voice_s", "pad_s") if k in r}
        g.update({"file": f"graphics/{dst.name}", "length_s": float(alpha.probe(dst)["format"]["duration"])})
        if cut and r.get("audio_key") == cut["key"]:       # the render's clip starts cut_s before the short line's,
            # whatever the inputs say now (--no-render after an engine change keeps the cut: Fable, round 7)
            g.update({"audio_key": line["key"], "voice_at_s": round(r["voice_at_s"] + cut["at_s"], 3),
                      "voice_s": round(r["voice_s"] - cut["at_s"], 3), "cut_from": {"key": cut["key"],
                                                                                     "at_s": cut["at_s"]}})
        if r.get("carry"):
            g["carry"] = r["carry"]
        g.update(timing.provenance_for(lines, g["line_id"], g["audio_key"]))   # R227 (never in the render's
                                                                                # inputs: a paid render stays valid)
        log.setdefault("graphics_alpha", {})[seq] = g
        log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
        print(f"  graphics/{dst.name}: {g['length_s']:.2f} s, voice at {g.get('voice_at_s')} s"
              + (f", the carried line at {g['carry']['at_s']} s" if g.get("carry") else ""))
    return log


def register_webapp(steps_path, run_dir, seq, webm, upload, engine, notes=None, open_head_s=None):
    """R244: a transparent render made in the HeyGen web app (R226: plan credits, never the API's wallet) from an upload
    pipeline.edit.pip_render built (its folder's manifest.json names the render plan that laid the upload out: the
    line, the gap, the main body's carried audio), registered as the stage's render for seq ("opening" or "recap"):
    renders_alpha[seq] (source "webapp": its edge colour premultiplied twice, alpha.PREMULTIPLIED; the record replaced
    moves to renders_alpha_history) and graphics_alpha[seq] (the ProRes 4444 the stage reads, its edges fixed with that
    count; the one replaced moves to graphics_alpha_history). An intro whose upload carries the main body past its
    first sentence (R237: the box's first stay) records where: carry.main_from_s (main-body seconds at carry.at_s, the
    render's time), carry.until_main_s (the carried audio's end) and carry.box_until_main_s (the box's first stay's
    end), which pipeline.edit.stage reads to run the intro's clip through that stay. open_head_s: how long before the
    line's clip the intro's picture starts, when this render needs another lead than OPEN_HEAD_S (Avatar V opens its
    mouth about half a second before the voice, so its intro starts earlier, on a closed mouth: final_r5's visual
    review), measured on the render and recorded with it. Nothing is paid or uploaded."""
    from pipeline.edit import alpha
    run_dir, webm, upload = Path(run_dir).resolve(), Path(webm).resolve(), Path(upload).resolve()
    doc = json.loads(Path(steps_path).read_text(encoding="utf-8"))
    lines = json.loads((EXERCISES / doc["exercise"] / "lines.json").read_text(encoding="utf-8"))
    man = json.loads((upload.parent / "manifest.json").read_text(encoding="utf-8"))
    rid = {"opening": "intro", "recap": "outro"}[seq]
    at_root = lambda q: (Path(q) if Path(q).is_absolute() else ROOT / q).resolve()    # the manifest's paths are
    built = next((b for b in man["built"] if b["id"] == rid and at_root(b["file"]) == upload), None)   # from ROOT
    if built is None:
        raise SystemExit(f"{upload} isn't the {rid} upload of {upload.parent / 'manifest.json'}")
    rplan = json.loads(at_root(man["plan"]).read_text(encoding="utf-8"))
    fps = rplan["fps"]
    parts = rplan[rid]["parts"]
    line = next(q for q in parts if q.get("line_id"))
    step = next(st for st in doc["steps"] if st["graphics"] == seq)
    if step["narration"]["line_id"] != line["line_id"] or lines[line["line_id"]]["key"] != line["key"]:
        raise SystemExit(f"the upload's line ({line['line_id']}, {line['key']}) isn't the steps file's {seq} line now")
    pr_ = alpha.probe(webm)
    v = next(x for x in pr_["streams"] if x.get("width"))
    dur = float(pr_["format"]["duration"])
    if abs(dur - built["length_s"]) > 0.1:                # HeyGen keeps the upload's length (to its 0.1 s)
        raise SystemExit(f"{webm.name} is {dur:.2f} s, its upload {built['length_s']:.2f} s")
    log_path = run_dir / "avatar" / "avatar.json"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    rel = lambda q: os.path.relpath(q, run_dir / "avatar")          # avatar.json's paths are from avatar/
    r = {"status": "done", "source": "webapp", "premultiplied": alpha.PREMULTIPLIED["webapp"], "engine": engine,
         "look": doc["heygen"]["look"], "line_id": line["line_id"], "audio_key": line["key"], "audio_s": line["s"],
         "pad_s": PAD_S, "voice_at_s": PAD_S, "voice_s": built.get("voice_s", line["s"]), "file": rel(webm),
         "upload": rel(upload), "duration_s": round(dur, 4), "fps": v["r_frame_rate"], "plan": man["plan"],
         **({"notes": notes} if notes else {})}
    carry = next((q for q in parts if q.get("from_f") is not None), None)
    if carry:
        c = step.get("carry_into") or {}
        if not built["maps"] or not c:
            raise SystemExit(f"the {rid} upload carries the main body but the steps file or the manifest doesn't say how")
        at_s, main_from_s, _ = built["maps"][0]
        ckey = lines[c["line_id"]]["key"]
        _, cut = carry_part(ckey, c["until_word"], run_dir / "avatar" / f"_{seq}_carry_check.wav",
                            timing.provenance(lines[c["line_id"]]))
        (run_dir / "avatar" / f"_{seq}_carry_check.wav").unlink(missing_ok=True)
        r["carry"] = {"key": ckey, "line_id": c["line_id"], "until_word": c["until_word"],
                      "gap_s": next(q["s"] for q in parts if q["what"].startswith("the gap")), "cut_s": cut,
                      "at_s": round(at_s, 4), "main_from_s": round(main_from_s, 4),
                      "until_main_s": round(carry["to_f"] / fps, 4), "box_until_main_s": round(carry["box_to_f"] / fps, 4)}
    renders = log.setdefault("renders_alpha", {})
    if seq in renders:
        log.setdefault("renders_alpha_history", []).append({"graphics": seq, **renders[seq]})
    renders[seq] = r
    import hashlib
    tag = hashlib.sha256(f"{webm.name}|{webm.stat().st_size}|{r['premultiplied']}".encode()).hexdigest()[:8]
    dst = run_dir / "graphics" / f"{seq}_webapp_{engine}_{tag}_alpha.mov"
    if not dst.exists():
        alpha.to_prores(webm, dst, premultiplied=r["premultiplied"])
    if open_head_s is not None:
        if not 0 < open_head_s <= r["voice_at_s"]:
            raise SystemExit(f"open_head_s {open_head_s}: between 0 and the line's start ({r['voice_at_s']} s)")
        r["open_head_s"] = open_head_s
    g = {k: r[k] for k in ("line_id", "audio_key", "voice_at_s", "voice_s", "pad_s", "source", "engine",
                           "open_head_s") if k in r}
    g.update({"file": f"graphics/{dst.name}", "length_s": float(alpha.probe(dst)["format"]["duration"])})
    if r.get("carry"):
        g["carry"] = r["carry"]
    g.update(timing.provenance_for(lines, g["line_id"], g["audio_key"]))
    ga = log.setdefault("graphics_alpha", {})
    if seq in ga:
        log.setdefault("graphics_alpha_history", []).append({"graphics": seq, **ga[seq]})
    ga[seq] = g
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps({"render": r, "graphics": {k: g[k] for k in ("file", "length_s", "voice_at_s")}}, indent=1))
    return g


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {a[2:].split("=", 1)[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    if args and args[0] == "webapp":     # R244: python -m pipeline.edit.avatar webapp <steps.json> runs/<run_id>
        # opening|recap <render.webm> <upload.wav> --engine=avatar_v [--notes=...]: no upload, no payment
        if "engine" not in opt:
            raise SystemExit("webapp: --engine=avatar_v|avatar_iv (the engine the web app rendered on) is required")
        register_webapp(args[1], args[2], args[3], args[4], args[5], opt["engine"], opt.get("notes"),
                        float(opt["open-head"]) if "open-head" in opt else None)
    else:
        main(args[0], args[1], do_render="--no-render" not in sys.argv, rerender="--rerender" in sys.argv)
