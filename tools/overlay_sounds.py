"""The overlay sound pass (R153, R154; docs/OVERLAY_BUILD_PLAN_qs1a.md): quiet sounds made in code, as the R137 click
is (pipeline/edit/click_sound.py): no sample library, nothing to license, the same settings always make the same file.

    python tools/overlay_sounds.py [--peak=-24]      # writes them all to D:\\Videos\\Global Assets\\motion-library\\sounds

lock   a padlock clicking shut: a metal snap (two transients with a bright ring) and a low clunk, 0.35 s
pop    a soft pop for a piece arriving: a short rising sine with a fast decay, 0.12 s
whoosh a short air sweep for a full-screen card: band-passed noise that rises and falls, 0.4 s
tick   a light tick for a checklist item or a pin: a short high ping, 0.08 s
flip   a card or page flipping: two quick paper flicks, 0.16 s
bell   a small bell struck once, its ring dying away (R235: the subscribe animation's bell), 1.3 s

Each is 16-bit mono 48 kHz WAV, its loudest sample at the peak (about -24 dBFS, as the click; a sound in LEVEL_DB that
far under it, so it sounds as loud as the others), named
<kind>_<hash of its settings>.wav so a changed level never overwrites a file an open Premiere project holds.
"""
import argparse
import hashlib
import json
import wave
from pathlib import Path

import numpy as np

SR = 48000
OUT = Path(r"D:\Videos\Global Assets\motion-library\sounds")


def _env(n, attack_s, decay_s):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack_s, 1e-4), 0, 1)
    return a * np.exp(-np.maximum(0, t - attack_s) / decay_s)


def _hp(x, hz):
    y = np.zeros_like(x)
    a = 1.0 / (1.0 + 2 * np.pi * hz / SR)
    for i in range(1, len(x)):
        y[i] = a * (y[i - 1] + x[i] - x[i - 1])
    return y


def _lp(x, hz):
    y = np.zeros_like(x)
    a = (2 * np.pi * hz / SR) / (1 + 2 * np.pi * hz / SR)
    for i in range(1, len(x)):
        y[i] = y[i - 1] + a * (x[i] - y[i - 1])
    return y


def synth(kind, rng):
    if kind == "lock":
        n = int(0.35 * SR)
        x = np.zeros(n)
        for t0, lvl in ((0.004, 1.0), (0.032, 0.7)):        # the shackle hits, then the latch catches
            k, m = int(t0 * SR), int(0.06 * SR)
            tt = np.arange(m) / SR
            seg = (rng.standard_normal(m) * np.exp(-tt / 0.0015) * 0.8 +
                   (np.sin(2 * np.pi * 2350 * tt) + 0.6 * np.sin(2 * np.pi * 5100 * tt)) * np.exp(-tt / 0.02))
            x[k:k + m] += seg * lvl
        tt = np.arange(n) / SR
        x += 0.5 * np.sin(2 * np.pi * 180 * tt) * _env(n, 0.002, 0.04)   # the body's low clunk
        return _hp(x, 90)
    if kind == "pop":
        n = int(0.12 * SR)
        tt = np.arange(n) / SR
        f = 380 + 700 * (1 - np.exp(-tt / 0.02))
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.003, 0.03)
    if kind == "whoosh":
        n = int(0.4 * SR)
        noise = rng.standard_normal(n)
        band = _hp(_lp(noise, 2600), 500)
        tt = np.arange(n) / SR
        shape = np.sin(np.pi * np.clip(tt / 0.4, 0, 1)) ** 2
        return band * shape
    if kind == "tick":
        n = int(0.08 * SR)
        tt = np.arange(n) / SR
        return (np.sin(2 * np.pi * 2800 * tt) + 0.3 * rng.standard_normal(n) * np.exp(-tt / 0.002)) * _env(n, 0.0008, 0.012)
    if kind == "flip":
        n = int(0.16 * SR)
        x = np.zeros(n)
        for t0, lvl in ((0.002, 1.0), (0.045, 0.6)):
            k, m = int(t0 * SR), int(0.035 * SR)
            x[k:k + m] += rng.standard_normal(m) * _env(m, 0.002, 0.008) * lvl
        return _hp(x, 1200)
    if kind == "bell":
        # a small bell struck once (R235: the subscribe animation's bell): a soft strike, then inharmonic partials
        # (the octave and a bar's 2.76, 5.40, 8.93) each dying away at its own rate, the higher sooner; the
        # fundamental doubled 0.35% sharp so it shimmers as the animation's bell swings
        n = int(BELL_S * SR)
        tt = np.arange(n) / SR
        x = np.zeros(n)
        for ratio, amp, decay in ((1.0, 1.0, 0.55), (1.0035, 0.5, 0.55), (2.0, 0.45, 0.35), (2.76, 0.3, 0.22),
                                  (5.40, 0.14, 0.12), (8.93, 0.06, 0.07)):
            x += amp * np.sin(2 * np.pi * BELL_HZ * ratio * tt + rng.uniform(0, 2 * np.pi)) * _env(n, 0.001, decay)
        m = int(0.004 * SR)
        x[:m] += 0.4 * _hp(rng.standard_normal(m), 3000) * np.exp(-np.arange(m) / SR / 0.001)   # the strike
        return _hp(x, 300)
    raise ValueError(kind)


KINDS = ("lock", "pop", "whoosh", "tick", "flip", "bell")
BELL_HZ, BELL_S = 1046.5, 1.3      # C6; long enough for its ring to die under the voice
# A sound's level under the shared peak, so it sounds as loud as the others: a bell's ring sustains where a pop is
# gone in 0.1 s, so at the same peak it is far louder. Measured (pipeline.edit.loudness.momentary, the most of its
# 400 ms windows) at -13.2 dBFS peak: whoosh -25.3, pop -30.4, tick -33.4 LUFS; the bell set to the pop's, the
# middle of them (R235: "its level matched to the other cues").
LEVEL_DB = {"bell": -7.4}


def path_of(kind, peak):
    h = hashlib.sha1(json.dumps({"kind": kind, "peak": float(peak), "v": 1,
                                 **({"level_db": LEVEL_DB[kind]} if kind in LEVEL_DB else {})}).encode()).hexdigest()[:8]
    return OUT / f"{kind}_{h}.wav"


def write(kind, peak=-24.0):
    p = path_of(kind, peak)
    if p.exists():
        return p
    x = synth(kind, np.random.default_rng(KINDS.index(kind) + 153))
    fade = int(0.008 * SR) if kind != "bell" else int(0.15 * SR)     # the bell's ring faded, not cut
    x[:24] *= np.linspace(0, 1, 24)
    x[-fade:] *= np.linspace(1, 0, fade)
    x *= 10 ** ((peak + LEVEL_DB.get(kind, 0.0)) / 20.0) / np.abs(x).max()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    tmp.replace(p)
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--peak", type=float, default=-24.0)
    a = ap.parse_args()
    for k in KINDS:
        print(write(k, a.peak))
