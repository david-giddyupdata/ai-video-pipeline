"""What a step's action made appear (R123): the box of a dialog, modal or menu, measured from the take's own frames.

The camera shows the whole of what a line refers to; a step's `whole: {"target": "appears"}` asks for the box of what
its click opened. Two frames are compared: just before the action, and just before the next step's first move (the
thing is fully drawn by then). Two ways to read them:
  - what changed: pixels of the second frame that the first, scaled by one factor, doesn't explain. The factor
    absorbs the shade a page modal lays over the page (Quick Sight darkens it to about half), so the modal is what's
    left; a menu or the Windows Open dialog changes the frame with no shade at all (factor 1).
  - the bright box over a shade: when the page got darker (a modal opened) or the change covers most of the frame (a
    modal replaced another modal, or the page behind it changed too), the modal is the largest near-white region of
    the second frame, since nothing under the shade is that bright.
Neither reads a page that got brighter (a modal closed, a navigation): that returns None.
"""
import subprocess
from collections import deque

from pipeline.config import tool

TOL = 18.0            # a pixel changed: more than this (0-255, any channel) off the first frame scaled by the factor
SHADE_K = 0.8         # the page got darker than this factor: a modal's shade came up
BRIGHTER_K = 1.15     # the page got brighter than this: something closed, or the page changed
WHITE = 235           # near-white: a modal's body, never the shaded page
CELL = 4              # px per cell for the component search
MAX_FRAC = 0.5        # a "change" over half the frame isn't one dialog,
MAX_FRAC_UNSHADED = 0.75   # unless the page behind is untouched (the Windows Open dialog is 66% of the frame)


def frame(run_dir, src_t, fps):
    """The source frame at src_t as an RGB float array, cached in runs/<id>/appear/."""
    import numpy as np
    from PIL import Image
    d = run_dir / "appear"
    d.mkdir(exist_ok=True)
    png = d / f"{int(round(src_t * fps)):06d}.png"
    if not png.exists():
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{max(0.0, src_t):.3f}", "-i",
                        str(run_dir / "raw.mp4"), "-frames:v", "1", str(png)], check=True)
    if not png.exists():                                  # past the recording's end: ffmpeg writes nothing
        return None
    return np.asarray(Image.open(png).convert("RGB")).astype(np.float32)


def largest_box(mask):
    """Bounding box (x0, y0, x1, y1) in px of the largest 8-connected region of mask, read on CELL-px cells; and its
    area in px. (None, 0) when the mask is empty."""
    h, w = mask.shape
    m = mask[: h // CELL * CELL, : w // CELL * CELL].reshape(h // CELL, CELL, w // CELL, CELL).mean(axis=(1, 3)) > 0.05
    rows, cols = m.shape
    seen = m.copy()
    seen[:] = False
    best, best_n = None, 0
    for y0 in range(rows):
        for x0 in range(cols):
            if not m[y0, x0] or seen[y0, x0]:
                continue
            q, n = deque([(y0, x0)]), 0
            seen[y0, x0] = True
            bx = [x0, y0, x0, y0]
            while q:
                y, x = q.popleft()
                n += 1
                bx = [min(bx[0], x), min(bx[1], y), max(bx[2], x), max(bx[3], y)]
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < rows and 0 <= xx < cols and m[yy, xx] and not seen[yy, xx]:
                            seen[yy, xx] = True
                            q.append((yy, xx))
            if n > best_n:
                best, best_n = bx, n
    if best is None:
        return None, 0
    return (best[0] * CELL, best[1] * CELL, (best[2] + 1) * CELL, (best[3] + 1) * CELL), best_n * CELL * CELL


def appeared(run_dir, src_before, src_after, fps):
    """(box, how) of what appeared between the two source times, or (None, why not)."""
    import numpy as np
    a, b = frame(run_dir, src_before, fps), frame(run_dir, src_after, fps)
    if a is None or b is None:
        return None, "a frame past the recording's end"
    H, W = a.shape[:2]
    la, lb = a.mean(axis=2), b.mean(axis=2)
    bright = la > 120
    k = float(np.median(lb[bright] / la[bright])) if bright.any() else 1.0
    if k > BRIGHTER_K:
        return None, f"the page got brighter (factor {k:.2f}): something closed or the page changed"
    span = lambda bx: (bx[2] - bx[0]) * (bx[3] - bx[1]) if bx else W * H
    box, _ = largest_box(np.abs(b - k * a).max(axis=2) > TOL)
    most = MAX_FRAC_UNSHADED if abs(k - 1.0) < 0.03 else MAX_FRAC      # the page behind untouched: a big window
    if k >= SHADE_K and box is not None and span(box) <= most * W * H:
        return box, f"what changed (factor {k:.2f})"
    wbox, _ = largest_box(b.min(axis=2) > WHITE)
    if wbox is not None and span(wbox) <= MAX_FRAC * W * H:
        return wbox, f"the bright box over the page's shade (factor {k:.2f})"
    return None, f"no single box (factor {k:.2f}, the change spans {span(box) / (W * H):.0%} of the frame)"
