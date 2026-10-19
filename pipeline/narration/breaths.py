"""Breaths in narration (R181): found in a clip, mapped onto the edit, and the double ones reported.

An inhale is unvoiced, broadband noise between words: in the clone's clips it sits 17 to 36 dB below the clip's own
speech level (the loudness pass's compressor narrows the gap), lasts 0.15 to 0.6 s, with a spectral centroid near
2 kHz and a zero-crossing rate about 0.2 (p1.03 at 6.36 to 6.72 s: -40 to -29 dBFS after the loudness pass). A
fricative ("s") is louder and sits higher (centroid over 4 kHz); voiced speech has a flat-free spectrum and a low
zero-crossing rate. Only the gaps between words are searched (the word timings), and ElevenLabs gives part of each
pause to the word before it (GOTCHAS: p1.14's "yyyy." logged as ending 0.4 s into the pause), so the search runs from
the earlier word's start, and a breath must start out of near-silence (a word's breathy release decays out of it).

    detect(path, words) -> [{t0, t1, rel_db}]          clip seconds
    placed(plan, cache) -> [{line, t0, t1, src_t0, ...}]   edit seconds, one per audible piece (a beat that splits a
                                                        breath gives two pieces)
    doubles(pieces, words) -> [(a, b)]                   two inhales within 1.5 s with no speech between
"""
import json
import subprocess
from pathlib import Path

import numpy as np

from pipeline.config import tool

SR = 16000
HOP, WIN = 160, 480                                   # 10 ms hop, 30 ms window
CFG = {"rel_db": (-42.0, -12.0), "zcr": (0.08, 0.5), "centroid_hz": (800.0, 4000.0), "flatness_min": 0.02,
       "min_s": 0.15, "max_s": 0.8, "bridge_frames": 2, "pair_s": 1.5, "lead_s": 0.3,
       "onset_frames": 6, "onset_quiet_db": -35.0, "peak_max_db": -14.0, "one_breath_gap_s": 0.25}


def load(path):
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le",
                          "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def features(x):
    """Per frame: level (dBFS), zero-crossing rate, spectral centroid (Hz), spectral flatness."""
    n = max(0, (len(x) - WIN) // HOP)
    if not n:
        return np.zeros((0, 4))
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n)[:, None]
    f = x[idx]
    rms = 20 * np.log10(np.sqrt(np.mean(f ** 2, axis=1)) + 1e-9)
    zcr = np.mean(np.abs(np.diff(np.sign(f), axis=1)), axis=1) / 2
    sp = np.abs(np.fft.rfft(f * np.hanning(WIN), axis=1)) + 1e-12
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    cen = (sp * freqs).sum(axis=1) / sp.sum(axis=1)
    p = sp ** 2
    flat = np.exp(np.mean(np.log(p), axis=1)) / np.mean(p, axis=1)
    return np.stack([rms, zcr, cen, flat], axis=1)


def speech_level(feat):
    """The clip's speech level: the median of its louder frames (voiced speech)."""
    if not len(feat):
        return -20.0
    rms = feat[:, 0]
    return float(np.median(rms[rms >= np.percentile(rms, 60)]))


def detect(path, words, cfg=CFG, x=None):
    """Breaths in a clip, [{t0, t1, rel_db}] in clip seconds, searched only between words (and before the first)."""
    x = load(path) if x is None else x
    feat = features(x)
    if not len(feat):
        return []
    lvl = speech_level(feat)
    t = (np.arange(len(feat)) * HOP + WIN / 2) / SR
    rel = feat[:, 0] - lvl
    ok = ((rel >= cfg["rel_db"][0]) & (rel <= cfg["rel_db"][1]) & (feat[:, 1] >= cfg["zcr"][0]) &
          (feat[:, 1] <= cfg["zcr"][1]) & (feat[:, 2] >= cfg["centroid_hz"][0]) & (feat[:, 2] <= cfg["centroid_hz"][1])
          & (feat[:, 3] >= cfg["flatness_min"]))
    zones = []                                        # where a breath can be: before the first word, and from each
    prev = [None] + words                             # word's start to the next word's (ElevenLabs can log a word
    starts = [w["start"] for w in words] + [len(x) / SR]   # ending half a second into the pause, p1.14's "yyyy."; the
    for w, s in zip(prev, starts):                    # voicing tests and the quiet onset keep the word itself out)
        zones.append((w["start"] + 0.05 if w else 0.0, s + 0.02))
    inzone = np.zeros(len(t), bool)
    for a, b in zones:
        inzone |= (t >= a) & (t <= b)
    ok &= inzone
    out, i, n = [], 0, len(ok)
    while i < n:
        if not ok[i]:
            i += 1
            continue
        j, gap = i, 0
        while j + 1 < n and (ok[j + 1] or (gap < cfg["bridge_frames"] and j + 2 < n and ok[j + 2])):
            gap = gap + 1 if not ok[j + 1] else 0
            j += 1
        t0, t1 = t[i] - WIN / 2 / SR, t[j] + WIN / 2 / SR
        # an inhale starts out of near-silence; a run that decays straight out of a voiced word is that word's breathy
        # release (p1.14 at 7.29 s: -11 dB under speech, falling), not a breath, and muting it would clip the word
        onset_quiet = i == 0 or float(rel[max(0, i - cfg["onset_frames"]):i].min()) <= cfg["onset_quiet_db"]
        if onset_quiet and float(rel[i:j + 1].max()) <= cfg["peak_max_db"] and cfg["min_s"] <= t1 - t0 <= cfg["max_s"]:
            q = i                                     # the quiet stretch just before it: where a beat can go (R181);
            while q > 0 and rel[q - 1] <= cfg["onset_quiet_db"]:   # silence reads the same before and after the
                q -= 1                                # loudness pass, a breath's faint start doesn't
            out.append({"t0": round(float(t0), 3), "t1": round(float(t1), 3),
                        "rel_db": round(float(np.median(rel[i:j + 1])), 1),
                        "quiet0": round(float(t[q] - HOP / 2 / SR), 3), "quiet1": round(float(t[i] - HOP / 2 / SR), 3)})
        i = j + 1
    merged = []                                       # an inhale with a brief catch in it is one breath, not two
    for b in out:                                     # (p1.26: two pieces 0.15 s apart; muting the first would leave
        if merged and b["t0"] - merged[-1]["t1"] < cfg["one_breath_gap_s"]:   # half a breath, R181's complaint)
            merged[-1] = dict(merged[-1], t1=b["t1"])
        else:
            merged.append(b)
    return merged


def beat_point(path, t_from, t_to, loud_db=-14.0, quiet_db=-40.0, min_quiet=5, look_s=0.3):
    """Where a beat can split a line (R181): after the earlier word's last loud frame (searched from t_from, its start,
    to t_to, the next word's start: a display word such as "MM/dd/yyyy" is spoken as many, and ElevenLabs logs word
    ends late, GOTCHAS), in the first real silence (min_quiet frames under quiet_db against the clip's speech): its
    start (20 ms in); else the quietest moment within look_s after the word. Never inside the word, its breathy release or an
    inhale, in the raw clip or after the loudness pass (Fable: at the silence's middle a beat sat 25 ms before a heard
    breath; at its start there is room). None when the clip has no loud frame there."""
    feat = _features_of(path)
    if not len(feat):
        return None
    rel = feat[:, 0] - speech_level(feat)
    t = (np.arange(len(feat)) * HOP + WIN / 2) / SR
    idx = np.nonzero((t >= t_from) & (t < t_to))[0]
    loud = [i for i in idx if rel[i] > loud_db or (rel[i] > -32 and feat[i, 2] > 3500)]   # a word's fricative ("s")
    # is quiet but high; an inhale sits near 2 kHz
    if not loud:
        return None
    k, end = loud[-1], idx[-1]
    i = k + 1
    while i <= end:
        if rel[i] <= quiet_db:
            j = i
            while j + 1 <= end and rel[j + 1] <= quiet_db:
                j += 1
            if j - i + 1 >= min_quiet:                 # its start, just past the word: the most room before an
                return round(float(t[i] + 0.02), 3)    # inhale, whose detected onset moves with the loudness pass
            i = j + 1
        else:
            i += 1
    span = np.arange(k + 1, min(end + 1, k + 1 + int(look_s * SR / HOP)))
    return round(float(t[span[np.argmin(rel[span])]]), 3) if len(span) else None


_FEAT = {}


def _features_of(path):
    path = str(path)
    if path not in _FEAT:
        _FEAT[path] = features(load(path))
    return _FEAT[path]


def clip_breaths(path, words, words_from=None):
    """detect() with a cache beside the clip (<clip>.breaths.json), keyed by the detector's settings, the clip, and
    whose word times set the search zones: the aligner's (R227) differ from the engine's for the same clip, so they
    are a key of their own; an engine-timed clip keeps the key it had before R227."""
    path = Path(path)
    side = path.with_name(path.name + ".breaths.json")
    st = path.stat()                                  # the clip itself too: a clip cleaned again under its name
    sig = json.dumps([CFG, st.st_size, st.st_mtime_ns] + (["aligner"] if words_from == "aligner" else []),
                     sort_keys=True)
    if side.exists():
        d = json.loads(side.read_text(encoding="utf-8"))
        if d.get("cfg") == sig:
            return d["breaths"]
    b = detect(path, words)
    side.write_text(json.dumps({"cfg": sig, "breaths": b}), encoding="utf-8")
    return b


def placed(run_dir, plan, cache):
    """Every breath of every placed line as the viewer hears it, edit seconds: one entry per audible piece (a part
    that plays some of it). A breath a beat splits gives two pieces with the same src span."""
    from pipeline.narration import timing
    run_dir, out = Path(run_dir), []
    for n in plan["narration"]:
        meta = timing.of(n, cache)                    # R227: the times (and display text) the line was built with
        src = run_dir / n["src"]
        for k, b in enumerate(clip_breaths(src, meta["words"], n.get("words_from"))):
            pieces = []
            for p in n.get("parts") or [{"at": n["start"], "in": 0.0, "out": n["audio_s"]}]:
                a, z = max(b["t0"], p["in"]), min(b["t1"], p["out"])
                if z - a > 0.02:
                    pieces.append((p["at"] + a - p["in"], p["at"] + z - p["in"]))
            for i, (a, z) in enumerate(pieces):
                out.append({"line": n["line_id"], "step": n["step"], "breath": k, "piece": i, "pieces": len(pieces),
                            "t0": round(a, 3), "t1": round(z, 3), "src_t0": b["t0"], "src_t1": b["t1"],
                            "rel_db": b["rel_db"]})
    return sorted(out, key=lambda r: r["t0"])


def placed_words(plan, cache):
    """Every word's (start, end) in edit seconds, through each line's parts."""
    from pipeline.narration import timing
    ws = []
    for n in plan["narration"]:
        meta = timing.of(n, cache)
        parts = n.get("parts") or [{"at": n["start"], "in": 0.0, "out": n["audio_s"]}]
        for w in meta["words"]:
            p = next((q for q in reversed(parts) if q["in"] <= w["start"] + 1e-6), parts[0])
            ws.append((p["at"] + w["start"] - p["in"], p["at"] + w["end"] - p["in"]))
    return sorted(ws)


def doubles(pieces, words, pair_s=CFG["pair_s"]):
    """Two inhales heard within pair_s with no speech between them: [(earlier, later)]. Speech between means a word
    that starts after the first inhale ends and before the second begins (a logged word end runs into the pause, so
    ends aren't used)."""
    out = []
    for a, b in zip(pieces, pieces[1:]):
        if b["t0"] - a["t0"] > pair_s:
            continue
        if any(a["t1"] - 0.05 <= ws < b["t0"] for ws, _ in words):
            continue
        out.append((a, b))
    return out
