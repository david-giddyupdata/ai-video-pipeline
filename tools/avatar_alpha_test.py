"""R207 step 1: can HeyGen render David's look on a transparent background? One short paid test render (R206).

    python tools/avatar_alpha_test.py runs/<run_id> <avatar steps file> [--seconds=10] [--no-render]

The first --seconds of the intro's uploaded audio (runs/<id>/avatar/opening_upload.wav: its 1.5 s of silence, then
the line) is rendered as WebM (output_format "webm") with the steps file's look, engine and resolution. The wallet is
read before and after (the cost, also when HeyGen refuses). Then the WebM becomes ProRes 4444 with alpha
(pipeline.edit.alpha), with check stills over a checkerboard, a dark and a light background, full-resolution crops
of the hair and shoulders, and the edge numbers. Everything goes in runs/<id>/avatar/alpha_test/, the log in
alpha_test.json. --no-render redoes the checks on the last render.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.config import tool                  # noqa: E402
from pipeline.edit import alpha, avatar           # noqa: E402


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    run_dir, steps = Path(args[0]).resolve(), Path(args[1]).resolve()
    secs = float(next((a.split("=", 1)[1] for a in argv if a.startswith("--seconds=")), 10))
    hg = json.loads(steps.read_text(encoding="utf-8"))["heygen"]
    d = run_dir / "avatar" / "alpha_test"
    d.mkdir(parents=True, exist_ok=True)
    log_p = d / "alpha_test.json"
    log = json.loads(log_p.read_text(encoding="utf-8")) if log_p.exists() else {"renders": []}
    if "--no-render" not in argv:
        audio = d / f"test_upload_{secs:g}s.wav"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(run_dir / "avatar" / "opening_upload.wav"),
                        "-t", f"{secs:.3f}", "-c:a", "pcm_s16le", str(audio)], check=True)
        webm = d / f"alpha_test_{int(time.time())}.webm"
        before = avatar.wallet()
        entry = {"seconds": secs, "look": hg["look"], "engine": hg["engine"], "resolution": hg["resolution"],
                 "wallet_before": before}
        try:
            entry.update(avatar.render(audio, hg["look"], hg["engine"], hg["resolution"],
                                       f"{run_dir.name} alpha test", webm, output_format="webm"))
            entry["file"] = webm.name
        except (RuntimeError, OSError) as e:          # a refusal, or the network: the paid call is logged either way
            entry["error"] = str(e)
        after = avatar.wallet()
        entry.update({"wallet_after": after,
                      "cost_usd": round(before - after, 4) if before is not None and after is not None else None})
        log["renders"].append(entry)
        log_p.write_text(json.dumps(log, indent=2), encoding="utf-8")
        print(json.dumps(entry, indent=1))
        if "error" in entry:
            return 2
    last = next(r for r in reversed(log["renders"]) if r.get("file"))
    webm = d / last["file"]
    info = alpha.probe(webm)
    mov = alpha.to_prores(webm, webm.with_suffix(".mov"))
    dur = float(info["format"]["duration"])
    times = [round(t, 1) for t in (min(2.0, dur / 4), dur / 2, max(0.0, dur - 1.5))]
    stills = alpha.stills(mov, d / "stills", times)
    checks = {"webm": info, "mov": alpha.probe(mov), "edges": {f"{t:.1f}": alpha.edges(alpha.rgba(mov, t))
                                                                 for t in times}}
    last["checks"] = checks
    log_p.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=1))
    print(f"{len(stills)} stills in {d / 'stills'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
