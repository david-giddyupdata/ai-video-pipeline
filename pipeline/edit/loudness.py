"""R177: the whole mix raised to YouTube's playback loudness by one shared amount, the balance David approved kept.

The voice gets a light compressor (its peaks stand far above its average: a plain gain to -14 LUFS would put the
limiter to work on about one window in six), make-up gain to the target and a true-peak limiter; the make-up is
measured over all the lines together, so every line gets the same chain. The effects (clicks, overlay sounds) are
raised by what the voice's loudness rose, so each still sits where it did against the voice. Settings: an
exercise's edit_settings.json "loudness" block:

    {"target_lufs": -14.0, "pre_gain_db": 8.0, "limit_dbfs": -1.5,
     "compressor": {"threshold_db": -22, "ratio": 3, "attack_ms": 5, "release_ms": 150, "knee": 4}}

Each processed line is a new file beside its source (audio/<stem>.ld<hash>.wav, the hash of the chain and the
source's bytes), so a project that holds the old one keeps it (R61), and an existing file is reused.
"""
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from pipeline.config import tool


def _db(x):
    return 10 ** (x / 20)


def _comp(c):
    return (f"acompressor=threshold={_db(c['threshold_db']):.5f}:ratio={c['ratio']}:attack={c['attack_ms']}:"
            f"release={c['release_ms']}:knee={c['knee']}:detection=rms")


def chain(ld, makeup_db):
    """The voice's ffmpeg filter chain with this make-up gain."""
    return (f"volume={ld['pre_gain_db']}dB,{_comp(ld['compressor'])},volume={makeup_db:.2f}dB,"
            f"alimiter=limit={_db(ld['limit_dbfs']):.5f}:attack=5:release=50:level=false:latency=true")


def measure(files, af=None):
    """Integrated loudness (LUFS) and true peak (dBTP) of the files played one after another, through af."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for p in files:
            f.write("file '" + str(Path(p).resolve()).replace("\\", "/").replace("'", "'\\''") + "'\n")
        lst = f.name
    try:
        r = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-f", "concat", "-safe", "0", "-i", lst, "-af",
                            (af + "," if af else "") + "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    finally:
        Path(lst).unlink(missing_ok=True)
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)[-1])


def momentary(path, af=None):
    """EBU R128 momentary loudness (a 400 ms K-weighted window) every 100 ms of a file, through af: [(t_s, LUFS)], t
    the window's end (ffmpeg's ebur128 frame log). Half a second of silence is added so a short sound's last windows
    are measured whole. For a sound effect's level against another's (R235: the bell matched to the other cues)."""
    r = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af",
                        (af + "," if af else "") + "apad=pad_dur=0.5,ebur128=framelog=info", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return [(float(t), float(m)) for t, m in re.findall(r"t:\s*(-?[\d.]+)\s+TARGET:\S+ LUFS\s+M:\s*(-?[\d.]+)", r)]


def prepare(run_dir, srcs, ld):
    """Process the lines (srcs: paths relative to run_dir) for the target. Returns ({src: new src}, info): info is
    what the plan records (the voice before and after, the make-up, the effects' gain), cached in audio/ by the
    sources and the settings, since measuring takes a few seconds per minute of speech."""
    run_dir = Path(run_dir)
    srcs = list(dict.fromkeys(srcs))
    digest = lambda f: hashlib.sha1(f.read_bytes()).hexdigest()   # by content: a line re-cleaned to the same length
    sig = hashlib.sha256(json.dumps({"ld": ld, "src": [(s, digest(run_dir / s)) for s in srcs], "v": 2},   # is new
                                    sort_keys=True).encode()).hexdigest()[:10]
    info_p = run_dir / "audio" / f"loudness_{sig}.json"
    if info_p.exists():
        info = json.loads(info_p.read_text(encoding="utf-8"))
    else:
        before, _ = measure([run_dir / s for s in srcs])
        partial = f"volume={ld['pre_gain_db']}dB,{_comp(ld['compressor'])}"
        mid, _ = measure([run_dir / s for s in srcs], partial)
        info = {"target_lufs": ld["target_lufs"], "voice_lufs_before": before,   # to 0.1 dB, so a re-voiced line
                "makeup_db": round(ld["target_lufs"] - mid, 1)}                  # rarely renames the other 85
    mapping = {}
    af = chain(ld, info["makeup_db"])
    for s in srcs:
        src = run_dir / s
        h = hashlib.sha256(json.dumps({"af": af, "src": digest(src), "name": src.name}).encode()).hexdigest()[:8]
        out = src.with_name(f"{src.stem}.ld{h}.wav")
        if not out.exists():
            part = out.with_name("_part_" + out.name)
            subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-af", af, "-ar", "48000", "-ac", "1",
                            "-c:a", "pcm_s16le", str(part)], check=True)
            part.replace(out)
        mapping[s] = str(Path(s).with_name(out.name)).replace("\\", "/")
    if "voice_lufs_after" not in info:
        after, tp = measure([run_dir / mapping[s] for s in srcs])
        info.update({"voice_lufs_after": after, "voice_true_peak_dbtp": tp,
                     "effects_gain_db": round(after - info["voice_lufs_before"], 2)})
        info_p.write_text(json.dumps(info, indent=1), encoding="utf-8")
    return mapping, info
