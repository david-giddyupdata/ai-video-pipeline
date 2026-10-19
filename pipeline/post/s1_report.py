"""Post-run for slice S1: find the sync flashes, calibrate timing and geometry, render the debug video.

    python -m pipeline.post.s1_report runs/<run_id>

Writes into the run folder:
  calibration.json   offset and drift (log time -> video time), page geometry measured from the flash vs computed
  raw.mp4            the OBS recording remuxed to MP4 (no re-encode), for easy playback
  debug_boxes.mp4    the recording with each logged target box, click point and step label drawn on
  stills/            one PNG per click, one frame before the click (cursor arrived, box on target)
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2

from pipeline.capture.sync import detect
from pipeline.config import tool

ORANGE = (49, 125, 237)        # BGR #ED7D31
RED = (40, 40, 220)


def load_log(run_dir):
    recs = [json.loads(l) for l in (run_dir / "runlog.jsonl").read_text(encoding="utf-8").splitlines()]
    return recs[0], recs[1:]


def calibrate(run_dir, header, events):
    cap = header["captures"][0]
    video = run_dir / cap["file"]
    flashes, fps = detect(video)
    markers = [e for e in events if e["phase"] == "sync_marker"]
    if len(flashes) == 1 and len(markers) == 2:   # the end flash never showed (drawn in a tab that wasn't in front,
        markers = markers[:1]                      # s7_take01): calibrate on the start flash alone, flagged below
    if len(flashes) != len(markers) or not markers:
        raise RuntimeError(f"found {len(flashes)} flashes in the video but {len(markers)} sync markers in the log")
    if len(markers) == 1:                    # a take that crashed before its end flash: assume no drift (S1 measured
        tm1, tv1 = markers[0]["t_mono"], flashes[0]["t_start"]   # at most 2 frames over a take); flagged below
        scale, offset, drift_frames = 1.0, tv1 - tm1, 0.0
    else:
        (tm1, tm2), (tv1, tv2) = (markers[0]["t_mono"], markers[-1]["t_mono"]), (flashes[0]["t_start"], flashes[-1]["t_start"])
        scale = (tv2 - tv1) / (tm2 - tm1)
        offset = tv1 - tm1 * scale
        drift_frames = ((tv2 - tv1) - (tm2 - tm1)) * fps
    x0, y0, x1, y1 = flashes[0]["bbox"]
    d = markers[0].get("detail") or {}
    if "client_w" in d:                      # scrollbars draw over the flash, so measure against the client area
        sx, sy = (x1 - x0) / d["client_w"], (y1 - y0) / d["client_h"]
        scale_px = round((sx + sy) / 2, 4)
    else:                                    # older logs: no horizontal scrollbar on these pages, so use the height
        sx, sy = (x1 - x0) / header["browser"]["viewport_css"]["w"], (y1 - y0) / header["browser"]["viewport_css"]["h"]
        scale_px = round(sy, 4)
    measured = {"viewport_origin_px": {"x": x0, "y": y0}, "px_per_css": scale_px,
                "scale_x": round(sx, 4), "scale_y": round(sy, 4), "flash_bbox": [x0, y0, x1, y1]}
    computed = cap["geometry"]
    diff = max(abs(x0 - computed["viewport_origin_px"]["x"]), abs(y0 - computed["viewport_origin_px"]["y"]))
    cal = {"video": cap["file"], "fps": fps, "offset_s": round(offset, 4), "scale": round(scale, 6),
           "drift_frames": round(drift_frames, 2),
           "flashes": [{"t_start": round(f["t_start"], 3), "frames": f["frames"], "bbox": f["bbox"]} for f in flashes],
           "geometry_measured": measured, "geometry_computed": computed, "geometry_diff_px": diff,
           **({"single_flash": True} if len(markers) == 1 else {})}
    (run_dir / "calibration.json").write_text(json.dumps(cal, indent=2), encoding="utf-8")
    return cal


def _steps(events):
    """Per click step: box, timing and click point, from the log."""
    out = {}
    for e in events:
        sid = e["step_id"]
        if not sid:
            continue
        s = out.setdefault(sid, {"id": sid})
        if e["phase"] == "step_start":
            s["start"], s["action"] = e["t_mono"], e["action"]
        elif e["phase"] == "cursor_move_start":
            s["move"], s["box"] = e["t_mono"], e["target_css_box"]
        elif e["phase"] == "action":
            s["act"] = e["t_mono"]
            s["point"] = (e.get("detail") or {}).get("point_css")
        elif e["phase"] == "expect_met":
            s["result"] = e["t_mono"]
        elif e["phase"] == "step_end":
            s["end"] = e["t_mono"]
    return list(out.values())


def render_debug(run_dir, cal, events):
    g = cal["geometry_measured"]
    ox, oy, k = g["viewport_origin_px"]["x"], g["viewport_origin_px"]["y"], g["px_per_css"]
    to_px = lambda x, y: (int(round(ox + x * k)), int(round(oy + y * k)))
    steps = _steps(events)
    cap = cv2.VideoCapture(str(run_dir / cal["video"]))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = run_dir / "debug_boxes.mp4"
    ff = subprocess.Popen([tool("ffmpeg"), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                           "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "18",
                           "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    stills = run_dir / "stills"
    stills.mkdir(exist_ok=True)
    still_at = {round((s["act"] * cal["scale"] + cal["offset_s"]) * fps) - 1: s["id"] for s in steps if "act" in s}
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        tm = (i / fps - cal["offset_s"]) / cal["scale"]
        label = None
        for s in steps:
            if s.get("start", 1e9) <= tm <= s.get("end", -1):
                label = f"{s['id']} {s['action']}"
            if s.get("box") and s["move"] <= tm <= min(s.get("end", 1e9), s.get("act", 1e9) + 0.6):
                b = s["box"]
                cv2.rectangle(frame, to_px(b["x"], b["y"]), to_px(b["x"] + b["width"], b["y"] + b["height"]), ORANGE, 2)
            if s.get("point") and s["act"] <= tm <= s["act"] + 0.6:
                p = to_px(s["point"]["x"], s["point"]["y"])
                cv2.circle(frame, p, 7, RED, -1)
                cv2.circle(frame, p, 16, RED, 2)
        hud = f"t_log {tm:7.2f}s  video {i / fps:7.2f}s" + (f"   {label}" if label else "")
        cv2.rectangle(frame, (0, h - 34), (760, h), (0, 0, 0), -1)
        cv2.putText(frame, hud, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        if i in still_at:
            cv2.imwrite(str(stills / f"{still_at[i]}_click.png"), frame)
        ff.stdin.write(frame.tobytes())
        i += 1
    cap.release()
    ff.stdin.close()
    ff.wait()
    return out


def remux(run_dir, cal):
    out = run_dir / "raw.mp4"
    subprocess.run([tool("ffmpeg"), "-y", "-loglevel", "error", "-i", str(run_dir / cal["video"]), "-c", "copy",
                    str(out)], check=True)
    return out


def report(run_dir):
    run_dir = Path(run_dir)
    header, events = load_log(run_dir)
    cal = calibrate(run_dir, header, events)
    remux(run_dir, cal)
    render_debug(run_dir, cal, events)
    g = cal["geometry_measured"]
    print(f"flashes found: {len(cal['flashes'])}; offset {cal['offset_s']:.3f}s; drift {cal['drift_frames']:+.2f} frames")
    print(f"page origin in video {g['viewport_origin_px']}, scale {g['px_per_css']} "
          f"(x {g['scale_x']}, y {g['scale_y']}); computed-vs-measured {cal['geometry_diff_px']} px")
    print("wrote:", ", ".join(p.name for p in [run_dir / "raw.mp4", run_dir / "debug_boxes.mp4", run_dir / "stills"]))
    return cal


if __name__ == "__main__":
    report(sys.argv[1])
