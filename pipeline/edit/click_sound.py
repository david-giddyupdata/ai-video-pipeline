"""R137: the quiet mouse-click sound, made in code (no sample library, nothing to license, nothing binary in git).

A real click is two ticks: the press, sharp, and the release about 70 ms later, softer. Each tick here is a short
burst of noise with a damped ring (a few kHz, a couple of milliseconds), high-passed so it has no thump, scaled so the
loudest sample sits at the settings' peak (about -24 dBFS, R137) and faded at the end; the file runs 0.2 s (whole
frames at 25, 30 and 60 fps), silent after the release. The same settings always make
the same file; its name carries their hash, so a changed level never overwrites a file an open Premiere project
holds (GOTCHAS, Premiere round trip).

    python -m pipeline.edit.click_sound <out.wav> [--peak=-24]   # listen to it on its own
"""
import hashlib
import json
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
DEFAULTS = {"peak_dbfs": -24.0, "press_hz": 3200.0, "release_hz": 4300.0, "release_after_s": 0.072,
            "release_level": 0.55, "length_s": 0.2, "seed": 137}


def settings(cfg):
    """The defaults with the exercise's values over them, numbers as floats (so -24 and -24.0 name one file)."""
    s = {**DEFAULTS, **{k: v for k, v in (cfg or {}).items() if k in DEFAULTS}}
    return {k: (float(v) if isinstance(v, (int, float)) and k != "seed" else v) for k, v in s.items()}


def name(cfg):
    s = settings(cfg)
    return "click_" + hashlib.sha1(json.dumps(s, sort_keys=True).encode()).hexdigest()[:8] + ".wav"


def synth(cfg=None):
    s = settings(cfg)
    rng = np.random.default_rng(int(s["seed"]))
    n = int(s["length_s"] * SR)
    out = np.zeros(n)

    def tick(t0, level, hz, ring_s):
        m = int(0.014 * SR)
        k = int(t0 * SR)
        tt = np.arange(m) / SR
        burst = rng.standard_normal(m) * np.exp(-tt / (ring_s * 0.35))       # the contact: broadband, very short
        ring = np.sin(2 * np.pi * hz * tt) * np.exp(-tt / ring_s)           # the button's plastic ringing
        seg = (0.7 * burst + ring) * level
        seg[:24] *= np.linspace(0, 1, 24)                                   # half a millisecond of attack: no edge
        out[k:k + m] += seg[:max(0, min(m, n - k))]

    tick(0.002, 1.0, s["press_hz"], 0.0024)
    tick(0.002 + s["release_after_s"], s["release_level"], s["release_hz"], 0.0016)
    hp = np.zeros_like(out)                                                 # one-pole high-pass at about 300 Hz
    a = 1.0 / (1.0 + 2 * np.pi * 300.0 / SR)
    for i in range(1, n):
        hp[i] = a * (hp[i - 1] + out[i] - out[i - 1])
    fade = int(0.01 * SR)
    hp[-fade:] *= np.linspace(1, 0, fade)
    hp *= 10 ** (s["peak_dbfs"] / 20.0) / np.abs(hp).max()
    return hp


def write(path, cfg=None):
    """The click as 16-bit mono 48 kHz WAV at path (made once; an existing file is left as it is)."""
    path = Path(path)
    if path.exists():
        return path
    x = synth(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    tmp.replace(path)
    return path


def peak_dbfs(path):
    with wave.open(str(path), "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768.0
    return 20 * np.log10(np.abs(x).max())


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    cfg = {"peak_dbfs": float(opts["peak"])} if "peak" in opts else None
    p = Path(args[0]) if args else Path(name(cfg))
    if p.exists():
        p.unlink()
    write(p, cfg)
    print(f"{p}: {settings(cfg)['length_s'] * 1000:.0f} ms, peak {peak_dbfs(p):.1f} dBFS")
