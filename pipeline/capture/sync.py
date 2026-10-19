"""Sync flash (SPEC §5.3): a full-viewport orange overlay shown for a moment at the start and end of every capture.

- Timing: the flash's first frame in the video, against its logged t_mono, gives the offset; two flashes give drift.
- Geometry: the flash fills exactly the visible page, so its rectangle in the video gives where the page sits in the
  frame and at what scale, whatever the browser zoom or tab layout.
"""
import time

import cv2
import numpy as np

ORANGE_BGR = np.array([49, 125, 237])          # #ED7D31
TOL = 45                                       # per-channel tolerance after video compression

_SHOW = """() => new Promise(r => {
  const d = document.createElement('div');
  d.id = '__aidv_sync';
  Object.assign(d.style, {position: 'fixed', left: '0', top: '0', width: '100vw', height: '100vh',
                          background: '#ED7D31', zIndex: '2147483647', pointerEvents: 'none', margin: '0'});
  document.documentElement.appendChild(d);
  requestAnimationFrame(() => requestAnimationFrame(() => r(true)));
})"""
_HIDE = """() => new Promise(r => {
  document.getElementById('__aidv_sync')?.remove();
  requestAnimationFrame(() => requestAnimationFrame(() => r(true)));
})"""


def flash(page, log, label, hold=0.4):
    """Show the flash, log it as a sync_marker event, remove it. Returns the logged t_mono of its appearance."""
    page.evaluate(_SHOW)
    t_on = log.now()
    size = page.evaluate("[document.documentElement.clientWidth, document.documentElement.clientHeight, "
                         "innerWidth, innerHeight]")
    time.sleep(hold)
    page.evaluate(_HIDE)
    t_off = log.now()
    log.event("sync_marker", None, t=t_on, detail={"label": label, "t_off": t_off, "client_w": size[0],
                                                   "client_h": size[1], "inner_w": size[2], "inner_h": size[3]})
    return t_on


def _mask(frame):
    return np.all(np.abs(frame.astype(np.int16) - ORANGE_BGR) <= TOL, axis=2)


def detect(video_path, min_fraction=0.5):
    """Find flashes in a video. Returns [{t_start, t_end, frames, bbox: (x0, y0, x1, y1)}] in video seconds."""
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    flashes, cur, i = [], None, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        small = cv2.resize(frame, (frame.shape[1] // 4, frame.shape[0] // 4), interpolation=cv2.INTER_AREA)
        if _mask(small).mean() >= min_fraction:
            if cur is None:
                cur = {"first": i, "frames": []}
            cur["frames"].append((i, frame))
        elif cur is not None:
            flashes.append(cur)
            cur = None
        i += 1
    if cur is not None:
        flashes.append(cur)
    cap.release()

    out = []
    for f in flashes:
        idx, frame = f["frames"][len(f["frames"]) // 2]           # middle frame: fully drawn, no tearing
        m = _mask(frame)
        rows = np.where(m.mean(axis=1) > 0.5)[0]
        cols = np.where(m.mean(axis=0) > 0.5)[0]
        out.append({"t_start": f["first"] / fps, "t_end": (f["frames"][-1][0] + 1) / fps, "frames": len(f["frames"]),
                    "bbox": (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)})
    return out, fps
