"""The avatar on a transparent background (R206, R207): conversion to ProRes 4444 and the checks on its edges.

HeyGen's transparent renders are WebM (VP9 with an alpha channel). ffmpeg's own VP9 decoder drops the alpha; only
libvpx-vp9 keeps it, so every read of a WebM names that decoder (GOTCHAS). The deliverable is ProRes 4444 with alpha
(yuva444p10le), which Premiere and Remotion both read.

stills() composites a frame over a checkerboard, a dark and a light background, full frame and at full resolution
around the hair and shoulders, where the old render showed a light halo and a green fringe. edges() measures the
same thing in numbers: how much green the edge pixels carry over red and blue, and how much lighter they are than
the subject just inside them.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.config import tool

W, H = 1920, 1080
DARK, LIGHT = (24, 24, 24), (240, 240, 240)
CHECK_PX = 32
# full-resolution crops of the seated look (x, y, w, h), from the old render's frame
CROPS = {"hair": (700, 90, 540, 300), "right_shoulder": (1100, 560, 480, 420), "left_shoulder": (380, 640, 480, 420)}
EDGE_PX = 3                           # the band each side of the matte's edge that edges() measures


def _decoder(path):
    return ["-c:v", "libvpx-vp9"] if Path(path).suffix.lower() == ".webm" else []


def probe(path):
    out = subprocess.run([tool("ffprobe"), "-v", "error", *_decoder(path), "-show_entries",
                          "stream=codec_name,pix_fmt,width,height,r_frame_rate:stream_tags=alpha_mode:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _grow(m, n):
    """m grown by n pixels (4-neighbour)."""
    for _ in range(n):
        g = m.copy()
        g[1:] |= m[:-1]
        g[:-1] |= m[1:]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        m = g
    return m


TRUST_ALPHA = 128      # under this alpha a divided-out colour is too coarse (8-bit, x255/a): the colour comes from inside
EXTEND_PX = 6          # how far fix_edges carries the subject's colour out into the edge


def _extend(rgb, known, n):
    """rgb carried n pixels out of known into its neighbours: each new pixel the mean of its known 4-neighbours."""
    rgb, known = rgb.copy(), known.copy()
    for _ in range(n):
        acc, cnt = np.zeros_like(rgb), np.zeros(known.shape, np.float32)
        for sl_to, sl_from in (((slice(1, None),), (slice(None, -1),)), ((slice(None, -1),), (slice(1, None),)),
                               ((slice(None), slice(1, None)), (slice(None), slice(None, -1))),
                               ((slice(None), slice(None, -1)), (slice(None), slice(1, None)))):
            k = known[sl_from]
            acc[sl_to] += rgb[sl_from] * k[..., None]
            cnt[sl_to] += k
        new = ~known & (cnt > 0)
        rgb[new] = acc[new] / cnt[new][:, None]
        known |= new
    return rgb


PREMULTIPLIED = {"api": 1, "webapp": 2}    # how many times a HeyGen WebM's edge colour carries its alpha, by where it
                                          # was made: the v3 API's once, the web app's twice (2026-10-17, R244;
                                          # research/heygen_plan/photo_look/stage_premult_fit.py: C/F ~ a against a^2)


def fix_edges(frame, premultiplied=1):
    """HeyGen's WebM edge colours come premultiplied by their alpha (a hair pixel at alpha 89 reads (57, 55, 47), about
    (163, 158, 135) once divided out), while players and editors read the alpha as straight, so the edge darkens twice
    into a dark outline; and its green-screen keying leaves a faint green rim. So: the alpha divided out of the
    partial pixels; under TRUST_ALPHA, where 8-bit values divided out turn to coloured noise (a faint yellow line),
    the subject's own colour carried out from inside (_extend, the usual colour decontamination); then green held to
    the larger of red and blue on the edge band (the partial pixels and EDGE_PX inside them), the usual despill,
    nowhere else. The alpha itself is never changed. ffmpeg's unpremultiply filter left these frames unchanged
    (2026-10-16). premultiplied: how many times the colour carries the alpha (PREMULTIPLIED: the web app's WebM twice,
    so (255 / a) ** 2 comes off in one step, in float; with one division a dark outline stays, about 1,250 dark edge
    pixels a frame against 150, stage_edge_fix.py). A count the source doesn't say is never guessed: the caller
    passes it from the render's record."""
    if premultiplied not in (1, 2):
        raise ValueError(f"premultiplied {premultiplied!r}: 1 (the API's WebM) or 2 (the web app's)")
    f = frame.astype(np.float32)
    a = f[..., 3]
    part = (a > 0) & (a < 255)
    if not part.any():
        return frame
    ys, xs = np.nonzero(_grow(part, EXTEND_PX + 1))
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1      # only the edge's bounding box is worked on
    c, al, pt = f[y0:y1, x0:x1, :3], a[y0:y1, x0:x1], part[y0:y1, x0:x1]
    c = np.where(pt[..., None], np.minimum(255.0, c * ((255.0 / np.maximum(al, 1.0)) ** premultiplied)[..., None]), c)
    trusted = al >= TRUST_ALPHA
    filled = _extend(c, trusted, EXTEND_PX)
    weak = pt & ~trusted
    c = np.where(weak[..., None], filled, c)
    band = _grow(pt, EDGE_PX) & (al > 0)
    rb = np.maximum(c[..., 0], c[..., 2])
    c[..., 1] = np.where(band, np.minimum(c[..., 1], rb), c[..., 1])
    f[y0:y1, x0:x1, :3] = c
    return f.round().astype(np.uint8)


def to_prores(src, dst, start_s=None, dur_s=None, fix=True, premultiplied=1):
    """src (WebM with alpha, or any video) as ProRes 4444 with alpha, its sound as 48 kHz stereo PCM; with fix, each
    frame through fix_edges with the source's premultiplied count (decoded as RGBA to Python and encoded from there)."""
    ss = ["-ss", f"{start_s:.3f}"] if start_s else []
    t = ["-t", f"{dur_s:.3f}"] if dur_s else []
    part = Path(dst).with_name("_part_" + Path(dst).name)
    enc = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", "-vendor", "apl0",
           "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]
    if not fix:
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", *_decoder(src), *ss, "-i", str(src), *t, *enc, str(part)],
                       check=True)
        part.replace(dst)
        return Path(dst)
    v = next(x for x in probe(src)["streams"] if x.get("width"))
    w, h, rate = v["width"], v["height"], v["r_frame_rate"]
    dec = subprocess.Popen([tool("ffmpeg"), "-v", "error", *_decoder(src), *ss, "-i", str(src), *t, "-f", "rawvideo",
                            "-pix_fmt", "rgba", "-"], stdout=subprocess.PIPE)
    out = subprocess.Popen([tool("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
                            "-r", rate, "-i", "-", *ss, "-i", str(src), *t, "-map", "0:v", "-map", "1:a?", *enc,
                            str(part)], stdin=subprocess.PIPE)
    n, size = 0, w * h * 4
    try:
        while True:
            buf = dec.stdout.read(size)
            if len(buf) < size:
                break
            out.stdin.write(fix_edges(np.frombuffer(buf, np.uint8).reshape(h, w, 4), premultiplied).tobytes())
            n += 1
    except BrokenPipeError:                          # the encoder stopped: its exit code below says why
        pass
    finally:
        for f in (out.stdin, dec.stdout):
            try:
                f.close()
            except OSError:
                pass
        rc = (dec.wait(), out.wait())
    if any(rc) or not n:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"to_prores {src}: ffmpeg exit {rc}, {n} frames")
    part.replace(dst)
    return Path(dst)


def to_webm(src, dst, width=None):
    """src (with alpha) as a small VP9 WebM with alpha (yuva420p), for Remotion to read: its renders copy every input
    into the temp folder once per call, so a 1 GB ProRes input left gigabytes behind (2026-10-16). width scales it
    (url.mov's 4K is shown about 1,150 px wide). No sound."""
    vf = [f"scale={width}:-2:flags=lanczos"] if width else []
    part = Path(dst).with_name("_part_" + Path(dst).name)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", *_decoder(src), "-i", str(src), *(["-vf", ",".join(vf)] if vf
                    else []), "-an", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "18", "-b:v", "0",
                    "-auto-alt-ref", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", "-f", "webm", str(part)],
                   check=True)
    part.replace(dst)
    return Path(dst)


def rgba(src, t):
    """The frame at t seconds as an h x w x 4 uint8 array (the alpha kept)."""
    v = next(x for x in probe(src)["streams"] if x.get("width"))
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", *_decoder(src), "-ss", f"{t:.3f}", "-i", str(src),
                          "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"], capture_output=True,
                         check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(v["height"], v["width"], 4)


def background(kind, h=H, w=W):
    if kind == "checker":
        y, x = np.mgrid[0:h, 0:w]
        on = ((y // CHECK_PX) + (x // CHECK_PX)) % 2 == 0
        return np.where(on[..., None], np.uint8(204), np.uint8(153)).repeat(3, axis=2).astype(np.float32)
    return np.broadcast_to(np.array(DARK if kind == "dark" else LIGHT, np.float32), (h, w, 3)).copy()


def over(frame, kind):
    a = frame[..., 3:4].astype(np.float32) / 255
    return (frame[..., :3].astype(np.float32) * a + background(kind, *frame.shape[:2]) * (1 - a)).round().astype(np.uint8)


def stills(src, out_dir, times):
    """Composites at each time over the three backgrounds, full frame and the CROPS at full size; their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for t in times:
        f = rgba(src, t)
        for kind in ("checker", "dark", "light"):
            img = over(f, kind)
            p = out_dir / f"t{t:05.1f}_{kind}.png"
            Image.fromarray(img).save(p)
            made.append(p)
            for name, (x, y, w, h) in CROPS.items():
                p = out_dir / f"t{t:05.1f}_{kind}_{name}.png"
                Image.fromarray(img[y:y + h, x:x + w]).save(p)
                made.append(p)
        p = out_dir / f"t{t:05.1f}_matte.png"
        Image.fromarray(f[..., 3]).save(p)
        made.append(p)
    return made


def edges(frame):
    """The matte in numbers: shares of clear, solid and partial pixels; and over the edge band (partial pixels, and
    solid ones within EDGE_PX of a clear one) against the subject just inside it, the green excess (G over the larger
    of R and B, the spill a green key leaves) and the luma difference (a light halo is positive)."""
    a = frame[..., 3]
    clear, solid = a < 8, a > 247
    near_clear = clear.copy()
    for _ in range(EDGE_PX):                        # grow the clear area by EDGE_PX pixels (4-neighbour dilation)
        g = near_clear.copy()
        g[1:] |= near_clear[:-1]
        g[:-1] |= near_clear[1:]
        g[:, 1:] |= near_clear[:, :-1]
        g[:, :-1] |= near_clear[:, 1:]
        near_clear = g
    band = (~clear & ~solid) | (solid & near_clear)
    inner = near_clear.copy()
    for _ in range(EDGE_PX * 2):                    # a ring inside the band: the subject's own colour nearby
        g = inner.copy()
        g[1:] |= inner[:-1]
        g[:-1] |= inner[1:]
        g[:, 1:] |= inner[:, :-1]
        g[:, :-1] |= inner[:, 1:]
        inner = g
    inside = solid & inner & ~near_clear
    rgb = frame[..., :3].astype(np.float32)
    green = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    n = a.size

    def stat(m, v):
        return round(float(v[m].mean()), 1) if m.any() else None
    return {"clear": round(float(clear.sum()) / n, 3), "solid": round(float(solid.sum()) / n, 3),
            "partial": round(float((~clear & ~solid).sum()) / n, 4), "edge_px": int(band.sum()),
            "edge_green_excess": stat(band, green), "inside_green_excess": stat(inside, green),
            "edge_luma": stat(band, luma), "inside_luma": stat(inside, luma)}
