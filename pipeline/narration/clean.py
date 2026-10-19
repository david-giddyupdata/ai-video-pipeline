"""A narration clip as the edit plays it: WAV at 48 kHz, clicks repaired, edges faded, a stray burst at either end
silenced.

ElevenLabs' request stitching (next_text) can start the next line's first sound in the last 50 ms of a clip, after
the line's closing pause, and the file stops in the middle of it: a pop where the clip ends (csc13 test, p2.10a2 and
p2.10c, 2026-10-12). A short burst at the very end (or start) of a clip, cut off from the speech by a pause, is that
artifact: it is faded to silence. Every clip also gets a few milliseconds of fade at both edges, so no clip starts or
stops on a non-zero sample. The length never changes, so the line's word timings still hold.

Inside the speech, a click is an isolated spike in the band above 4 kHz: a 0.5 ms frame at least CLICK_DB above the
median of the 20 ms on its louder side, and no more than 2 ms wide (R103). Measured on 2026-10-13: 33 minutes of
edge-tts speech never pass 22.4 dB, the clone's sharpest consonant (the final t of "prompt", csc13 p2.10b) reaches
29.2 dB, and the CSC13 test's one click (p2.10d at 7.43 s, in the closure before "choices") 33.8 dB. Only the few
milliseconds around a click take ffmpeg's adeclick. Run over the whole clip, it rewrites the speech instead: 9,000 to
21,000 samples a clip at its defaults (up to -17 dBFS, most of it below 4 kHz), the plosives (t, k, p, d, up to
-25 dBFS) at t=4, and at t=8 it still touches plosives and misses the click. The detector is not adeclick's own, so
the clicks it finds after the repair are evidence, not the filter's claim.

    python -m pipeline.narration.clean <src> [<src>...] --report     # what the pass changes, per clip; writes nothing
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

from pipeline.config import tool

SR = 48000
VERSION = 2                       # the pass; a cleaned clip's file name carries it (wav_name), so a changed pass writes
                                  # new files and a project David saved keeps the audio it was cut with (R61)
FRAME_S = 0.01                    # the loudness envelope's step
FLOOR = 0.003                     # RMS under this is silence (the clone's pauses measure 0.0000 to 0.0001)
BURST_MAX_S = 0.15                # a stray burst is at most this long ...
PAUSE_MIN_S = 0.15                # ... and cut off from the speech by at least this much silence
EDGE_FADE_S = 0.008
EDGE_DB = -60.0                   # a first or last sample louder than this would pop (the edge fade removes it)
BAND_HZ = 4000.0                  # clicks are measured above this (a 1 kHz raised-cosine edge) ...
CLICK_FRAME_S = 0.0005            # ... as the RMS of frames this long
CLICK_MAX_S = 0.002               # a click is at most this wide; its neighbourhood starts this far off on each side ...
CLICK_CONTEXT_S = 0.020           # ... and spans this much (its median level)
CLICK_DB = 31.0                   # a click stands this far above the louder side (consonants: up to 29.2 dB)
BAND_FLOOR_DB = -80.0             # a side counts as no quieter than this (the clone's pauses: -80 to -92 dB)
GATE_RAMP_S = 0.001               # adeclick's result is kept within CLICK_MAX_S of a click, faded in and out over this
DECLICK = "adeclick"              # its defaults (55 ms windows, AR order 2, threshold 2) repaired injected clicks best
PAD_S = 0.12                      # mirrored audio on both sides: adeclick's overlap-add start-up rewrote the first
                                  # 41 ms of a clip (up to -21 dBFS) and the band filter wraps around


def decode(path, sr=SR):
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr),
                          "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def pcm16(x):
    return (np.clip(x, -1, 1) * 32767).astype(np.int16)


def write_wav(path, x, sr=SR):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16(x).tobytes())


def dbfs(v):
    return round(20 * float(np.log10(v)), 1) if v > 0 else None


def stray_burst(x, sr=SR, from_end=True):
    """Samples of a short burst at one end that a pause cuts off from the speech, or None."""
    win = int(FRAME_S * sr)
    env = np.sqrt(np.mean(x[:len(x) // win * win].reshape(-1, win) ** 2, axis=1))
    loud = list(env > FLOOR)
    if from_end:
        loud = loud[::-1]
    if not loud or not loud[0]:
        return None
    burst = next((i for i, v in enumerate(loud) if not v), len(loud))
    pause = next((i for i, v in enumerate(loud[burst:]) if v), len(loud) - burst)
    if burst * FRAME_S > BURST_MAX_S or pause * FRAME_S < PAUSE_MIN_S or burst + pause >= len(loud):
        return None
    n = (burst + pause // 2) * win                       # cut in the middle of the pause
    return (len(x) - n, len(x)) if from_end else (0, n)


def band_frames(x, sr=SR):
    """RMS of x above BAND_HZ, per CLICK_FRAME_S frame."""
    p = min(int(PAD_S * sr), len(x) - 1)
    xp = np.pad(x.astype(np.float64), p, mode="reflect")
    f = np.fft.rfftfreq(len(xp), 1 / sr)
    gain = 0.5 - 0.5 * np.cos(np.pi * np.clip((f - BAND_HZ) / 1000 + 0.5, 0, 1))
    h = np.fft.irfft(np.fft.rfft(xp) * gain, len(xp))[p:p + len(x)]
    fr = int(CLICK_FRAME_S * sr)
    m = len(h) // fr
    return np.sqrt(np.mean(h[:m * fr].reshape(m, fr) ** 2, axis=1)) + 1e-12


def clicks(x, sr=SR):
    """Clicks inside x (the faded edges aside): [(t_s, dB above the louder side)]."""
    e = band_frames(x, sr)
    n, g, w = len(e), int(CLICK_MAX_S / CLICK_FRAME_S), int(CLICK_CONTEXT_S / CLICK_FRAME_S)
    if n < 2 * (g + w) + 1:
        return []
    win = np.lib.stride_tricks.sliding_window_view(np.pad(e, g + w, mode="reflect"), w)
    side = np.maximum(np.median(win[:n], axis=1), np.median(win[2 * g + w + 1:], axis=1))   # w frames each side,
    bg = np.maximum(side, 10 ** (BAND_FLOOR_DB / 20))                                       # g frames away
    above = 20 * np.log10(e / bg)
    peak = np.lib.stride_tricks.sliding_window_view(np.pad(e, g, mode="edge"), 2 * g + 1).max(axis=1)
    edge = int((EDGE_FADE_S + CLICK_MAX_S) / CLICK_FRAME_S)
    found = []
    for i in np.flatnonzero((above >= CLICK_DB) & (e >= peak)):
        if not edge <= i < n - edge:
            continue
        mid = np.sqrt(e[i] * bg[i])                        # halfway (in dB) between the spike and its neighbourhood
        a = z = i
        while a > 0 and e[a - 1] > mid and z - a < g:
            a -= 1
        while z < n - 1 and e[z + 1] > mid and z - a < g:
            z += 1
        if z - a < g:                                      # at most CLICK_MAX_S wide
            found.append((round((i + 0.5) * CLICK_FRAME_S, 3), round(float(above[i]), 1)))
    return found


def adeclick(x, sr=SR):
    """x through ffmpeg's DECLICK in float, with PAD_S of mirrored audio on both sides; the same length back."""
    p = min(int(PAD_S * sr), len(x) - 1)
    xp = np.pad(x, p, mode="reflect").astype(np.float32)
    out = subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                          "-af", DECLICK, "-f", "f32le", "-"], input=xp.tobytes(), capture_output=True,
                         check=True).stdout
    y = np.frombuffer(out, np.float32)
    if len(y) != len(xp):
        raise RuntimeError(f"{DECLICK} returned {len(y)} samples for {len(xp)}")
    return y[p:p + len(x)]


def declick(x, sr=SR):
    """x with its clicks repaired, and what changed: {"clicks": [(t_s, dB)], "clicks_after": [...], "changed": 16-bit
    samples, "diff_max_db", "diff_rms_db": dBFS of the change, None if nothing changed}."""
    found, y = clicks(x, sr), x
    if found:
        hw, rp = int(CLICK_MAX_S * sr), int(GATE_RAMP_S * sr)
        shape = np.concatenate([np.sin(np.linspace(0, np.pi / 2, rp)) ** 2, np.ones(2 * hw),
                                np.cos(np.linspace(0, np.pi / 2, rp)) ** 2])
        gate = np.zeros(len(x))
        for t, _ in found:
            a = int(t * sr) - hw - rp
            lo, hi = max(a, 0), min(a + len(shape), len(x))
            gate[lo:hi] = np.maximum(gate[lo:hi], shape[lo - a:hi - a])
        y = (x + gate * (adeclick(x, sr) - x)).astype(np.float32)
    d = y.astype(np.float64) - x
    return y, {"clicks": found, "clicks_after": clicks(y, sr) if found else [],
               "changed": int(np.count_nonzero(pcm16(y) != pcm16(x))),
               "diff_max_db": dbfs(np.abs(d).max()), "diff_rms_db": dbfs(np.sqrt(np.mean(d ** 2)))}


def process(x, sr=SR):
    """Decoded samples -> the clip as the edit plays it, and declick()'s report plus "silenced" ([(start_s, end_s)])
    and "edges_db" (the source's first and last sample, dBFS)."""
    x = np.array(x, np.float32)                        # a copy: the bursts and fades work in place
    edges = [dbfs(abs(float(x[0]))), dbfs(abs(float(x[-1])))]
    silenced, f = [], int(EDGE_FADE_S * sr)
    for from_end in (True, False):
        b = stray_burst(x, sr, from_end)
        if b:
            a, z = b
            if from_end:
                x[a:a + f] *= np.linspace(1, 0, f)
                x[a + f:] = 0
            else:
                x[:z - f] = 0
                x[z - f:z] *= np.linspace(0, 1, f)
            silenced.append((round(a / sr, 3), round(z / sr, 3)))
    x, report = declick(x, sr)                         # after the bursts (already silenced), before the edge fades
    x[:f] *= np.linspace(0, 1, f)
    x[-f:] *= np.linspace(1, 0, f)
    return x, {**report, "silenced": silenced, "edges_db": edges}


def wav_name(key):
    """The cleaned clip's file name in runs/<id>/audio/ (version 1, before the click pass, was <key>.wav)."""
    return f"{key}.c{VERSION}.wav"


def clean(src, dst, sr=SR, report=None):
    """src (any audio) -> dst (16-bit mono WAV at sr). Returns what was silenced, [(start_s, end_s)]; a dict passed
    as report gets process()'s report."""
    x, rep = process(decode(src, sr), sr)
    write_wav(dst, x, sr)
    if report is not None:
        report.update(rep)
    return rep["silenced"]


def main(argv):
    srcs = [a for a in argv if not a.startswith("--")]
    if "--report" not in argv or not srcs:
        print("usage: python -m pipeline.narration.clean <src> [<src>...] --report")
        return 2
    show = lambda v: "-" if v is None else f"{v:.1f}"
    print(f"{'clip':20s} {'line':24s} {'clicks':>6s} {'changed':>7s} {'max dBFS':>8s} {'rms dBFS':>8s} "
          f"{'edges dBFS':>14s}  clicks at s (dB above), stray bursts silenced")
    for s in srcs:
        _, r = process(decode(s))
        meta = Path(s).with_suffix(".json")                 # an audio_cache clip's sidecar names its line
        text = json.loads(meta.read_text(encoding="utf-8")).get("display_text", "") if meta.exists() else ""
        edges = "/".join(show(v) + ("!" if v is not None and v > EDGE_DB else "") for v in r["edges_db"])
        notes = [f"{t:.3f} ({a:.1f})" for t, a in r["clicks"]] + [f"silenced {a:.3f}-{z:.3f}" for a, z in r["silenced"]]
        print(f"{Path(s).stem[:20]:20s} {text[:24]:24s} {len(r['clicks']):>2d} -> {len(r['clicks_after']):<1d} "
              f"{r['changed']:>7d} {show(r['diff_max_db']):>8s} {show(r['diff_rms_db']):>8s} {edges:>14s}  "
              f"{', '.join(notes)}")
    print(f"clicks: before -> after the repair; edges: the source's first/last sample (! louder than {EDGE_DB:.0f}, "
          "faded); max and rms: the de-click's change alone")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
