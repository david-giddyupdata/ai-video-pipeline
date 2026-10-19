"""Blur rectangles in a finished video for given time spans (privacy findings David chose to blur, SPEC §10).

    python -m pipeline.privacy.blur <in.mp4> <out.mp4> <spans.json>

spans.json: [{"t0": 59.4, "t1": 62.0, "box": [x, y, w, h], "why": "AWS account ID"}]
Video is re-encoded once at near-lossless quality; audio is copied untouched. The input is never modified.
"""
import json
import subprocess
import sys
from pathlib import Path

from pipeline.config import tool


def blur(src, dst, spans):
    if Path(src).resolve() == Path(dst).resolve():
        raise ValueError("output must be a new file")
    chain, last = [], "0:v"
    for i, s in enumerate(spans):
        x, y, w, h = s["box"]
        chain.append(f"[{last}]split[b{i}][c{i}];[c{i}]crop={w}:{h}:{x}:{y},boxblur=luma_radius=12:luma_power=4:"
                     f"chroma_radius=6:chroma_power=2[p{i}];"
                     f"[b{i}][p{i}]overlay={x}:{y}:enable='between(t,{s['t0']},{s['t1']})'[v{i}]")
        last = f"v{i}"
    subprocess.run([tool("ffmpeg"), "-y", "-v", "error", "-stats", "-i", str(src), "-filter_complex", ";".join(chain),
                    "-map", f"[{last}]", "-map", "0:a?", "-c:v", "libx264", "-crf", "15", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(dst)], check=True)


if __name__ == "__main__":
    blur(sys.argv[1], sys.argv[2], json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")))
