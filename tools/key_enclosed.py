"""Key the white a flood fill from the image's edges can't reach (David's note 11, 2026-10-15: the white inside the
padlock's shackle showed as a patch over the screen). Writes <name>_k.png beside the input; the input is kept (R154).

    python tools/key_enclosed.py <art.png> [...] [--min-area=<px>]

Near-white pixels (every channel at least WHITE, channels within SPREAD of each other) that are still opaque form
regions; each region of at least --min-area pixels (default 1% of the image: the padlocks' shackle holes are 5 to 8%
of 1024 px art, a highlight on the object far less) is keyed out. A two-pixel
ring around each keyed region is faded by how light it is, so the outline's antialiasing doesn't leave a white rim.
A file with no transparency at all (never keyed) gets its edge-connected white keyed too.

Since R227 this is the fallback: new art is cut out by BiRefNet (tools/gen_image.py --cutout, or for a picture already
made, python -m pipeline.ml.cutout <art.png>), which keys enclosed white by itself. This stays for art keyed by the
flood fill (gen_image.py --key-white) and for the padlocks' _alpha_k.png already in the Section A review (R195).
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

WHITE, SPREAD = 236, 14


def key(path, min_area=None):
    im = np.array(Image.open(path).convert("RGBA")).astype(np.int16)
    rgb, a = im[..., :3], im[..., 3]
    lo, hi = rgb.min(axis=2), rgb.max(axis=2)
    white = (lo >= WHITE) & (hi - lo <= SPREAD) & (a > 0)
    never_keyed = bool((a == 255).all())
    count, labels, stats, _ = cv2.connectedComponentsWithStats(white.astype(np.uint8), connectivity=4)
    H, W = white.shape
    if min_area is None:                               # a 500 px highlight on 1024 px art was keyed at the old fixed 400
        min_area = max(400, round(0.01 * W * H))       # (Fable's R108 review, item 5)
    keep = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        touches_edge = x == 0 or y == 0 or x + w == W or y + h == H
        if area >= min_area and (not touches_edge or never_keyed):
            keep.append(i)
    drop = np.isin(labels, keep)
    n = len(keep)
    near = np.array(Image.fromarray(np.where(drop, 255, 0).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(5))) > 0
    ring = near & ~drop
    lum = rgb.mean(axis=2)
    fade = np.clip((WHITE - lum) / (WHITE - 150), 0, 1)        # white -> 0, the outline's dark -> 1
    a2 = a.astype(np.float32)
    a2[drop] = 0
    a2[ring] = a2[ring] * fade[ring]
    im[..., 3] = np.round(a2).astype(np.int16)
    dst = path.with_name(path.stem + "_k.png")
    Image.fromarray(im.astype(np.uint8), "RGBA").save(dst)
    return dst, n, int(drop.sum())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--min-area", type=int, default=None, help="pixels; default 1%% of the image")
    a = ap.parse_args(argv)
    for f in a.files:
        dst, n, px = key(f, a.min_area)
        print(f"{f.name}: {n} region(s), {px} px keyed -> {dst.name}")


if __name__ == "__main__":
    sys.exit(main() or 0)
