"""Join a paused take's two recordings into one (R70): Parts 1 to 4 (raw/obs_a.mkv) and Parts 5 and 6
(raw/obs_b.mkv), recorded in one codespace either side of the off-camera exploration.

    python -m pipeline.post.join runs/<run_id>

One run log holds both halves on one clock (the resume continues it). Each recording is timed by its own flash
(start, resume), so the join keeps A up to just after its last step and B from just before its first, re-encodes
them as raw/obs.mkv frame-exactly, and shifts B's events by the pause it skipped. The pause and resume flashes
are cut with the pause; what is left is one recording with a start and an end flash, as every later stage
expects. A recording_joined event marks the join, where the edit puts R34's section dissolve. The log as written
is kept as runlog_raw.jsonl, and the numbers in join.json.

A take that only resumed (Part 5 alone on an earlier take's codespace: nothing recorded before the pause) has B
alone; it is renamed raw/obs.mkv and the log is unchanged.
"""
import json
import subprocess
import sys
from pathlib import Path

from pipeline.capture.sync import detect
from pipeline.config import tool
from pipeline.driver.runlog import _VALIDATOR

TAIL_S = 0.25          # A runs on this long after its last step ends (its pause flash comes 0.5 s after it)
HEAD_S = 0.5           # B starts this long before its first step starts (its resume flash ends about 1 s before)


def _marker(events, label):
    return next((e for e in events if e["phase"] == "sync_marker" and (e.get("detail") or {}).get("label") == label),
                None)


def join(run_dir):
    run = Path(run_dir).resolve()
    raw = run / "raw"
    a_mkv, b_mkv, out = raw / "obs_a.mkv", raw / "obs_b.mkv", raw / "obs.mkv"
    lines = (run / "runlog.jsonl").read_text(encoding="utf-8").splitlines()
    header, events = json.loads(lines[0]), [json.loads(l) for l in lines[1:]]
    if not a_mkv.exists():                          # nothing recorded before the pause
        b_mkv.replace(out)
        (run / "join.json").write_text(json.dumps({"joined": False, "why": "no recording before the pause"},
                                                  indent=2), encoding="utf-8")
        return None
    m_pause, m_resume = _marker(events, "pause"), _marker(events, "resume")
    if not (m_pause and m_resume):
        raise RuntimeError("the log has no pause and resume flashes")
    fa, fps = detect(a_mkv)
    fb, fps_b = detect(b_mkv)
    if abs(fps - fps_b) > 1e-3 or not fa or not fb:
        raise RuntimeError(f"recordings differ ({fps} vs {fps_b} fps) or a flash is missing ({len(fa)}, {len(fb)})")
    off_a = fa[0]["t_start"] - _marker(events, "start")["t_mono"]     # log time -> each recording's own time
    off_b = fb[0]["t_start"] - m_resume["t_mono"]
    t_p, t_r = m_pause["t_mono"], m_resume["t_mono"]
    a_end = max(e["t_mono"] for e in events if e["phase"] == "step_end" and e["t_mono"] < t_p)
    b_start = min(e["t_mono"] for e in events if e["phase"] == "step_start" and e["t_mono"] > t_r)
    n_a = int(round((min(a_end + TAIL_S, t_p - 0.05) + off_a) * fps))   # A's frames kept: [0, n_a)
    k_b = int(round((max(b_start - HEAD_S, m_resume["detail"]["t_off"] + 0.15) + off_b) * fps))   # B's from k_b
    t_join = n_a / fps - off_a                      # the join, in A's log time
    shift = (k_b / fps - off_b) - t_join            # B's log time - shift = joined log time
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(a_mkv), "-i", str(b_mkv), "-filter_complex",
                    f"[0:v]trim=end_frame={n_a},setpts=PTS-STARTPTS[va];"
                    f"[0:a]atrim=end={n_a / fps:.6f},asetpts=PTS-STARTPTS[aa];"
                    f"[1:v]trim=start_frame={k_b},setpts=PTS-STARTPTS[vb];"
                    f"[1:a]atrim=start={k_b / fps:.6f},asetpts=PTS-STARTPTS[ab];"
                    "[va][aa][vb][ab]concat=n=2:v=1:a=1[v][a]",
                    "-map", "[v]", "-map", "[a]", "-r", str(fps), "-c:v", "libx264", "-preset", "fast", "-crf", "14",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)], check=True)
    kept = []
    for e in events:
        t = e["t_mono"]
        if t <= t_join:
            kept.append(e)
        elif t - shift >= t_join and t >= t_r:      # B, on the joined clock
            e = dict(e, t_mono=round(t - shift, 3))
            if e["phase"] == "sync_marker" and (e.get("detail") or {}).get("label") == "resume":
                continue                            # cut with the pause
            if e["phase"] == "sync_marker" and (e.get("detail") or {}).get("t_off") is not None:
                e["detail"] = dict(e["detail"], t_off=round(e["detail"]["t_off"] - shift, 3))
            kept.append(e)
    joined = {"record": "event", "t_mono": round(t_join, 3), "t_wall": m_resume["t_wall"], "step_id": None,
              "phase": "recording_joined", "action": None, "tab": None, "url_host": None, "target_css_box": None,
              "frame_chain": [], "line_id": None, "result": "ok",
              "detail": {"pause_s": round(shift, 3), "a_frames": n_a, "b_from_frame": k_b}}
    kept.append(joined)
    kept.sort(key=lambda e: e["t_mono"])
    for e in kept:
        _VALIDATOR.validate(e)
    (run / "runlog.jsonl").replace(run / "runlog_raw.jsonl")
    (run / "runlog.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [header] + kept) + "\n",
                                      encoding="utf-8")
    info = {"joined": True, "fps": fps, "offset_a_s": round(off_a, 4), "offset_b_s": round(off_b, 4),
            "a_frames": n_a, "b_from_frame": k_b, "join_log_s": round(t_join, 3), "pause_s": round(shift, 3),
            "a_last_step_end": a_end, "b_first_step_start": b_start}
    (run / "join.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


if __name__ == "__main__":
    print(json.dumps(join(sys.argv[1]), indent=2))
