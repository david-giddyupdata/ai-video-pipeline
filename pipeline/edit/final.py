"""The approval gate and the final render (S5; R55, R56).

    python -m pipeline.edit.final runs/<run_id> --approve    # only when David says the proxy is approved
    python -m pipeline.edit.final runs/<run_id>              # the 1080p render, if this exact plan is approved

--approve records approval.json for the current edit_plan.json, and only if the proxy he reviewed was rendered from
that plan (pipeline.edit.review stamps it). Any re-plan changes the plan's fingerprint and needs a new approval.

The render is Remotion's EditPass at full size from the same plan as the proxy, so it matches what he approved; it is
written to runs/<run_id>/final/<run_id>_1080p.mp4 with final.json (plan fingerprint, approval, length check). Privacy
findings still open, or marked retake, are listed; they never block (R56). Blurs are in the plan (privacy_masks).
"""
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.config import ROOT, tool
from pipeline.edit.review import plan_sha, proxy_path

REMOTION = ROOT / "remotion"


def approve(run_dir):
    run_dir = Path(run_dir).resolve()
    sha = plan_sha(run_dir)
    stamp = run_dir / "review" / "proxy_plan.sha"
    if not stamp.exists() or stamp.read_text().strip() != sha:
        raise SystemExit("the proxy was not rendered from the current plan: run pipeline.edit.review first, and have "
                         "David review that proxy")
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    rec = {"plan_sha256": sha, "proxy": proxy_path(run_dir, plan).name, "by": "David (recorded by Claude)",
           "approved_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    (run_dir / "approval.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def privacy_left(run_dir):
    rp = Path(run_dir) / "privacy_report.json"
    if not rp.exists():
        return ["no privacy report (python -m pipeline.privacy.report)"]
    dec_p = Path(run_dir) / "privacy_decisions.json"
    dec = json.loads(dec_p.read_text(encoding="utf-8")) if dec_p.exists() else {}
    out = []
    for f in json.loads(rp.read_text(encoding="utf-8"))["findings"]:
        d = dec.get(f["id"], "open")
        if d in ("open", "retake"):
            out.append(f"{f['t0']:.1f}s {f['pattern']} ({f['where']}): {d}")
    return out


def render(run_dir):
    run_dir = Path(run_dir).resolve()
    sha = plan_sha(run_dir)
    ap = run_dir / "approval.json"
    approval = json.loads(ap.read_text(encoding="utf-8")) if ap.exists() else None
    if not approval:
        raise SystemExit("not approved: no final render without David's approval of a proxy (R55)")
    if approval["plan_sha256"] != sha:
        raise SystemExit("the plan changed after it was approved: review the new proxy and approve again (R55)")
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    out_dir = run_dir / "final"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{plan['run_id']}_1080p.mp4"
    subprocess.run([shutil.which("npx") or "npx", "remotion", "render", "src/index.ts", "EditPass", str(out),
                    f"--props={run_dir / 'edit_plan.json'}", f"--public-dir={run_dir}", "--codec=h264", "--crf=18",
                    "--log=warn"], cwd=REMOTION, check=True)
    probe = json.loads(subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_packets",
                                       "-show_entries", "stream=width,height,nb_read_packets", "-of", "json", str(out)],
                                      capture_output=True, text=True, check=True).stdout)["streams"][0]
    frames = int(probe["nb_read_packets"])
    check = {"frames": frames, "plan_frames": plan["durationInFrames"], "size": f"{probe['width']}x{probe['height']}",
             "matches_plan": frames == plan["durationInFrames"] and probe["width"] == plan["width"]}
    left = privacy_left(run_dir)
    (out_dir / "final.json").write_text(json.dumps({"video": out.name, "plan_sha256": sha, "approval": approval,
                                                    "check": check, "privacy_open": left}, indent=2), encoding="utf-8")
    return out, check, left


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    if "--approve" in argv:
        rec = approve(args[0])
        print(f"approved plan {rec['plan_sha256'][:12]} ({rec['proxy']}) at {rec['approved_at']}")
        return 0
    out, check, left = render(args[0])
    print(f"{out}  {check['size']}, {check['frames']} frames (plan {check['plan_frames']})"
          f"{'' if check['matches_plan'] else '  MISMATCH'}")
    for line in left:
        print("  privacy (advisory):", line)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
