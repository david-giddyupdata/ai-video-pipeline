"""Post-run for slice S2: draw the synthetic cursor and click rings onto a take's raw.mp4 (SPEC §7.1).

    python -m pipeline.post.s2_cursor runs/<run_id> [--track-only]

Needs s1_report to have run first (calibration.json, raw.mp4). Writes into the run folder:
  cursor_track.json  every cursor move and click, in video seconds and video pixels (the Remotion props)
  cursor.mp4         raw.mp4 with the Cursor and ClickRing layers from remotion/ drawn on
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2

from pipeline.config import ROOT
from pipeline.post.s1_report import load_log

REMOTION = ROOT / "remotion"


def build_track(run_dir, cal, events):
    """Log time -> video time with the calibrated offset and scale; CSS px -> video px with the measured geometry."""
    g = cal["geometry_measured"]
    ox, oy, k = g["viewport_origin_px"]["x"], g["viewport_origin_px"]["y"], g["px_per_css"]
    tv = lambda t_mono: round(cal["offset_s"] + cal["scale"] * t_mono, 4)
    px = lambda p: {"x": round(ox + p["x"] * k, 1), "y": round(oy + p["y"] * k, 1)}

    # A step may move the cursor several times (a live mark: travel, draw, back off; then the move to the click).
    # Each cursor_move_start pairs with the next cursor_arrive; detail.to_css says where it went (older logs: the click
    # point). detail.gesture tags the legs of a mark; a dwell_end with detail.release is the mark's release.
    moves, clicks, checks, releases, last_act, open_ = [], [], [], [], {}, None
    for e in events:
        sid, ph, d = e["step_id"], e["phase"], e.get("detail") or {}
        if ph == "action" and sid:
            last_act[sid] = e
    for e in events:
        sid, ph, d = e["step_id"], e["phase"], e.get("detail") or {}
        if ph == "cursor_move_start":
            open_ = e
        elif ph == "cursor_arrive" and open_ is not None:
            od = open_.get("detail") or {}
            to = od.get("to_css") or last_act[sid]["detail"]["point_css"]
            mv = {"step": sid, "t0": tv(open_["t_mono"]), "t1": tv(e["t_mono"]), "from": px(od["from_css"]), "to": px(to)}
            if od.get("gesture"):
                mv.update(gesture=od["gesture"], mark=od.get("mark"))
            moves.append(mv)
            if not od.get("gesture") and sid in last_act:
                act = last_act[sid]
                b = act["target_css_box"]
                checks.append({"step": sid, "move_s": round(e["t_mono"] - open_["t_mono"], 3),
                               "pause_s": round(act["t_mono"] - e["t_mono"], 3),
                               "inside_box": b["x"] <= to["x"] <= b["x"] + b["width"]
                               and b["y"] <= to["y"] <= b["y"] + b["height"]})
            open_ = None
        elif ph == "dwell_end" and d.get("release"):
            releases.append({"step": sid, "mark": d["mark"], "t": tv(e["t_mono"])})
    for sid, act in last_act.items():
        if act["action"] in ("click", "type", "switch_tab", "drag") and (act.get("detail") or {}).get("point_css"):
            # typing: the click into the box; a tab switch: the click on the tab; a drag: the press
            clicks.append({"step": sid, "t": tv(act["t_mono"]), "at": px(act["detail"]["point_css"])})

    cap = cv2.VideoCapture(str(run_dir / "raw.mp4"))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    track = {"video": "raw.mp4", "fps": cal["fps"], "width": w, "height": h, "durationInFrames": frames,
             "moves": moves, "clicks": clicks, "releases": releases}
    (run_dir / "cursor_track.json").write_text(json.dumps(track, indent=2), encoding="utf-8")
    return track, checks


def render(run_dir):
    """The run folder is Remotion's public dir, so the composition loads raw.mp4 from it without a copy."""
    npx = shutil.which("npx") or "npx"
    subprocess.run([npx, "remotion", "render", "src/index.ts", "CursorPass", str(run_dir / "cursor.mp4"),
                    f"--props={run_dir / 'cursor_track.json'}", f"--public-dir={run_dir}",
                    "--codec=h264", "--crf=18"], cwd=REMOTION, check=True)
    return run_dir / "cursor.mp4"


def main(argv):
    run_dir = Path(argv[0]).resolve()
    header, events = load_log(run_dir)
    cal = json.loads((run_dir / "calibration.json").read_text(encoding="utf-8"))
    track, checks = build_track(run_dir, cal, events)
    for c in checks:
        print(f"{c['step']}: move {c['move_s']:.3f}s, pause before click {c['pause_s']:.3f}s, "
              f"click point inside target box: {c['inside_box']}")
    print(f"{len(track['moves'])} moves, {len(track['clicks'])} clicks, {track['durationInFrames']} frames")
    if "--track-only" not in argv:
        print(render(run_dir))


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main(sys.argv[1:])
