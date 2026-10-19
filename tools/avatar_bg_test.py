"""R214, R219: a short paid test of a HeyGen look on HeyGen's own background replacement (its matte, composited by
HeyGen onto an image we give it), for the box-or-transparency choice.

    python tools/avatar_bg_test.py runs/<run_id> --look=<look id> --engine=avatar_iv --background=<png> [--seconds=10]
                                   [--name=<tag>] [--no-render]

The first --seconds of the intro's uploaded audio (runs/<id>/avatar/opening_upload.wav: its 1.5 s of silence, then the
line) is rendered as MP4 with that look and engine, HeyGen putting --background behind the avatar
(pipeline.edit.avatar.render's background). The wallet is read before and after (the cost, also when HeyGen refuses).
Then full-resolution stills at three times, to check the head's edges and the shoulders where the old look's matte
left an olive line and a dark sliver (research/matting/). Everything goes in
runs/<id>/avatar/bg_test/, the log in bg_test.json. --no-render redoes the stills from the last render.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.config import tool                  # noqa: E402
from pipeline.edit import avatar                  # noqa: E402


def opt(argv, name, default=None):
    return next((a.split("=", 1)[1] for a in argv if a.startswith(f"--{name}=")), default)


def stills(mp4, out_dir, dur):
    """Full-resolution frames at three times."""
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for t in (min(2.5, dur / 4), dur / 2, max(0.0, dur - 1.0)):
        full = out_dir / f"t{t:04.1f}_full.png"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1",
                        str(full)], check=True)
        made.append(full)
    return made


def main(argv):
    run_dir = Path(next(a for a in argv if not a.startswith("--"))).resolve()
    look, engine, bg = opt(argv, "look"), opt(argv, "engine", "avatar_iv"), opt(argv, "background")
    secs = float(opt(argv, "seconds", 10))
    tag = opt(argv, "name", f"{look[:6]}_{engine}")
    d = run_dir / "avatar" / "bg_test"
    d.mkdir(parents=True, exist_ok=True)
    log_p = d / "bg_test.json"
    log = json.loads(log_p.read_text(encoding="utf-8")) if log_p.exists() else {"renders": []}
    if "--no-render" not in argv:
        if not (look and bg):
            sys.exit("--look and --background are needed for a render")
        audio = d / f"test_upload_{secs:g}s.wav"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(run_dir / "avatar" / "opening_upload.wav"),
                        "-t", f"{secs:.3f}", "-c:a", "pcm_s16le", str(audio)], check=True)
        mp4 = d / f"bg_test_{tag}_{int(time.time())}.mp4"
        before = avatar.wallet()
        entry = {"seconds": secs, "look": look, "engine": engine, "background": str(bg), "resolution": "1080p",
                 "wallet_before": before}
        try:
            entry.update(avatar.render(audio, look, engine, "1080p", f"{run_dir.name} bg test {tag}", mp4,
                                       background=bg))
            entry["file"] = mp4.name
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
    mp4 = d / last["file"]
    dur = float(avatar.probe(mp4)["format"]["duration"])
    made = stills(mp4, d / f"stills_{Path(last['file']).stem}", dur)
    print(f"{len(made)} stills in {made[0].parent}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
