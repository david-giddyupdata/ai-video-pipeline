"""Picture activity in a recording (R25): how much of the frame changes from one frame to the next.

The test for "something worth watching" during a silence. The cursor and marks are drawn in the edit (R17), so the
recording only changes when the page does (loading, a list narrowing, a file opening). Measured on a 192x108 grey
copy: the share of pixels that change by more than 12 levels, in percent. Cached as activity.npy in the run folder.
"""
import json
import subprocess
from pathlib import Path

import numpy as np

from pipeline.config import tool

SIZE = (192, 108)
LEVEL = 12


def load(run_dir, video="raw.mp4"):
    """Per-frame activity (%), index i = the change from frame i to frame i + 1."""
    run_dir = Path(run_dir)
    src, cache, meta = run_dir / video, run_dir / "activity.npy", run_dir / "activity.json"
    stamp = {"video": video, "size": src.stat().st_size, "mtime": src.stat().st_mtime, "scale": SIZE, "level": LEVEL}
    if cache.exists() and meta.exists() and json.loads(meta.read_text(encoding="utf-8")) == stamp:
        return np.load(cache)
    w, h = SIZE
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(src), "-vf", f"scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
    act = (np.abs(np.diff(frames, axis=0)) > LEVEL).mean(axis=(1, 2)) * 100
    np.save(cache, act)
    meta.write_text(json.dumps(stamp), encoding="utf-8")
    return act


def peak(act, fps, s0, s1):
    """The most the picture changes between source times s0 and s1 (%)."""
    i0, i1 = max(0, int(s0 * fps)), min(len(act), int(round(s1 * fps)))
    return float(act[i0:i1].max()) if i1 > i0 else 0.0


def last_active(act, fps, s0, s1, min_pct):
    """The source time of the last frame change above min_pct between s0 and s1, or None."""
    i0, i1 = max(0, int(s0 * fps)), min(len(act), int(round(s1 * fps)))
    hits = np.nonzero(act[i0:i1] > min_pct)[0]
    return None if not len(hits) else (i0 + int(hits[-1]) + 1) / fps
