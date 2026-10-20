"""Narration, the edit plan and a 540p proxy, from an existing take, no retake (slices S3 onward).

    python -m pipeline.edit.s3 runs/<run_id> <steps file> [--gap cut|swipe|speed|all]

Voices any changed lines (pipeline.narration.build), plans the edit (pipeline.edit.plan), then renders
proxy_<tag>_<gap>.mp4 into the run folder, where <tag> comes from the steps file (steps_csc13.json -> csc13). Change exercises/<ex>/edit_settings.json and run it again for a new proxy.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.config import ROOT
from pipeline.edit.plan import plan
from pipeline.narration.build import build

REMOTION = ROOT / "remotion"
GAPS = ("cut", "swipe", "speed")


def render_proxy(run_dir, gap, tag="s3"):
    out = run_dir / f"proxy_{tag}_{gap}.mp4"
    npx = shutil.which("npx") or "npx"
    subprocess.run([npx, "remotion", "render", "src/index.ts", "EditPass", str(out),
                    f"--props={run_dir / 'edit_plan.json'}", f"--public-dir={run_dir}",
                    "--scale=0.5", "--codec=h264", "--crf=23", "--log=warn"], cwd=REMOTION, check=True)
    return out


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    gap = next((a.split("=", 1)[1] for a in argv if a.startswith("--gap=")), None)
    run_dir, steps = Path(args[0]).resolve(), Path(args[1]).resolve()
    build(steps)
    for g in (GAPS if gap == "all" else [gap]):
        p = plan(run_dir, steps, g)
        name = render_proxy(run_dir, p["gap_treatment"], steps.stem.removeprefix("steps_"))
        print(f"{name}  {p['duration_s']:.1f}s  warnings: {p['warnings'] or 'none'}")
        for n in p["notes"]:
            print("  note:", n)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main(sys.argv[1:])
