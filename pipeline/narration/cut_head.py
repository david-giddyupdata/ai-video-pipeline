"""R234: a voiced line shortened at its start, with nothing voiced again: the clip cut in the pause before a word.

    python -m pipeline.narration.cut_head <steps file> <line_id> <word> [--apply]

Section A's intro starts at "In this video" (R234): the greeting before it is cut from the clip already voiced. The
cut is found in the audio, never at a logged word end (ElevenLabs logs ends late, GOTCHAS): the silence after the word
before (breaths.beat_point, on the cleaned clip as every reader hears it), then the word's own onset (the first 10 ms
window over ONSET_DB). The new clip starts the original clip's own lead before that onset (measured the same way), so
it begins as a freshly voiced clip would; the cut must fall inside the silence.

What it writes (with --apply; without, it only reports):
  * audio_cache/<new key>.mp3 and .json: the cut clip under the key pipeline.narration.build gives the shortened text
    (build.cache_key: the spoken text and the voice), so the build finds it cached and never calls the engine; the
    meta's word times and boundaries are the original's shifted by the cut (the same engine times, so every beat and
    card row lands on the same sound as before), and "cut_from" names the clip it came from and where;
  * the steps file's narration text for the line, shortened;
  * lines.json, by pipeline.narration.build itself, run with the engine's synth disabled (it raises if called).
A render made from the long clip (pipeline.edit.avatar) serves the shortened line by starting cut_s later
(avatar.main_alpha reads "cut_from"); a new render (Avatar V) uploads the shortened clip (avatar.padded on the line's
key), as pipeline.edit.pip_render does.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from pipeline.config import EXERCISES, tool
from pipeline.narration import breaths, build, clean, engines, timing
from pipeline.narration.respell import load_terms, respell

ONSET_DB = -50.0          # a 10 ms window louder than this is sound (the clone's pauses measure -90 to -180 dBFS)
WIN_S = 0.01
MAX_ALIGN_MS = 1.0        # the cut clip, decoded, sits within this of the original from the cut (encoder delay)


def onset(x, t_from, sr=clean.SR):
    """The first 10 ms window from t_from whose RMS is over ONSET_DB, in seconds (5 ms steps)."""
    n, step = int(WIN_S * sr), int(0.005 * sr)
    for k in range(int(t_from * sr), len(x) - n, step):
        if 20 * np.log10(np.sqrt(np.mean(x[k:k + n] ** 2)) + 1e-12) > ONSET_DB:
            return round(k / sr, 4)
    return None


def find_cut(key, words, i, tmp):
    """Where to cut the clip so it starts at words[i]: (cut_s, measures)."""
    clean.clean(build.CACHE / f"{key}.mp3", tmp)
    x = clean.decode(tmp)
    quiet = breaths.beat_point(tmp, words[i - 1]["start"], words[i]["start"])
    tmp.unlink()
    if quiet is None:
        raise SystemExit(f"no silence found before {words[i]['word']!r}")
    on = onset(x, quiet)
    lead = onset(x, 0.0)                               # the clip's own lead before its first sound
    if on is None or lead is None:
        raise SystemExit("no sound found after the silence, or at the clip's start")
    cut = round(max(quiet, on - lead), 3)
    gap = x[int(quiet * clean.SR):int(on * clean.SR)]
    return cut, {"silence_from_s": quiet, "onset_s": on, "lead_s": lead,
                 "silence_peak_dbfs": round(float(20 * np.log10(np.abs(gap).max() + 1e-12)), 1) if len(gap) else None}


def cut_mp3(src, dst, cut_s, sr, bitrate):
    """src from cut_s to its end as MP3 (decoded and cut sample-exact, then encoded at the source's rate and bitrate).
    Checked: decoded again, it matches the source from cut_s within MAX_ALIGN_MS (the encoder's delay is in its header)."""
    part = dst.with_name("_part_" + dst.name)
    try:
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-af", f"atrim=start={cut_s}", "-ar",
                        str(sr), "-ac", "1", "-c:a", "libmp3lame", "-b:a", str(bitrate), "-f", "mp3", str(part)],
                       check=True)
    except subprocess.CalledProcessError:
        part.unlink(missing_ok=True)
        raise
    a, b = clean.decode(src), clean.decode(part)
    a = a[int(round(cut_s * clean.SR)):]
    n = min(len(a), len(b), clean.SR * 5)
    m = int(0.01 * clean.SR)
    xc = [float(np.dot(a[m:n - m], b[m + d:n - m + d])) for d in range(-m, m + 1)]
    lag = int(np.argmax(xc)) - m
    if abs(lag) > MAX_ALIGN_MS / 1000 * clean.SR:
        part.unlink()
        raise SystemExit(f"the cut clip sits {lag} samples off the original")
    part.replace(dst)
    return lag


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 3:
        print(__doc__)
        return 2
    steps_path, line_id, word = Path(args[0]), args[1], args[2]
    apply = "--apply" in argv
    doc = json.loads(steps_path.read_text(encoding="utf-8"))
    ex = EXERCISES / doc["exercise"]
    lines = json.loads((ex / doc.get("lines_file", "lines.json")).read_text(encoding="utf-8"))   # a second voice's own
    voice = json.loads((ex / doc.get("voice_file", "voice.json")).read_text(encoding="utf-8"))
    if timing.source(voice) != "engine":
        raise SystemExit("this cut shifts the engine's word times; a line on the aligner's would be aligned again")
    old = lines[line_id]
    meta = json.loads((build.CACHE / f"{old['key']}.json").read_text(encoding="utf-8"))
    if meta.get("cut_from"):
        raise SystemExit(f"{line_id} is already a cut clip ({meta['cut_from']})")
    words = meta["words"]
    i = next((k for k, w in enumerate(words) if k and w["word"] == word), None)
    if i is None:
        raise SystemExit(f"no word {word!r} after the first in {line_id}")
    tmp = Path(build.CACHE / f"_cut_{old['key']}.wav")
    cut, measured = find_cut(old["key"], words, i, tmp)
    c0 = words[i]["char"][0]
    text = old["text"][c0:]
    step = next(s for s in doc["steps"] if s.get("narration", {}).get("line_id") == line_id)
    if step["narration"]["text"] != old["text"] or step["narration"].get("spoken"):
        raise SystemExit("the steps file's text isn't lines.json's (or has its own spoken text): build first")
    engine = engines.make(voice)
    terms = load_terms(doc["exercise"], engine.name)
    sp, pieces, tighten = respell(text, sorted(terms, key=lambda t: -len(t["display"])), None)
    key, fields = build.cache_key(engine, sp, tighten)
    if old["spoken"][len(old["spoken"]) - len(sp):] != sp:
        raise SystemExit("the shortened spoken text isn't the end of the old one (a respelling changed): not a cut")
    shift_b = [(t, round(a - cut, 3), round(b - cut, 3)) for t, a, b in meta["boundaries"] if a >= cut - 1e-6]
    new_words = build.display_words(text, sp, pieces, shift_b)
    shifted = [{"word": w["word"], "start": round(w["start"] - cut, 3), "end": round(w["end"] - cut, 3),
                "char": [w["char"][0] - c0, w["char"][1] - c0]} for w in words[i:]]
    same = len(new_words) == len(shifted) and all(a == b for a, b in zip(new_words, shifted))
    report = {"line_id": line_id, "old_key": old["key"], "new_key": key, "cut_s": cut, **measured,
              "old_length_s": old["length_s"], "removed_text": old["text"][:c0].strip(), "new_text_starts": text[:40],
              "words_match_shifted": same}
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if not same:
        raise SystemExit("the build's display words from the shifted boundaries differ from the shifted words")
    if not apply:
        return 0
    raw0 = steps_path.read_text(encoding="utf-8")      # the file is partly hand-laid-out: only the text changes
    was = json.dumps(old["text"], ensure_ascii=False)
    if raw0.count(was) != 1:
        raise SystemExit(f"the line's text is in {steps_path} {raw0.count(was)} times, not once")
    step["narration"]["text"] = text
    raw = raw0.replace(was, json.dumps(text, ensure_ascii=False))
    if json.loads(raw) != doc:
        raise SystemExit("rewriting the text changed more than the text")
    probe = json.loads(subprocess.run([tool("ffprobe"), "-v", "error", "-show_entries", "stream=sample_rate,bit_rate",
                                       "-of", "json", str(build.CACHE / f"{old['key']}.mp3")], capture_output=True,
                                      text=True, check=True).stdout)["streams"][0]
    mp3, side = build.CACHE / f"{key}.mp3", build.CACHE / f"{key}.json"
    if mp3.exists() or side.exists():
        raise SystemExit(f"{mp3} or its meta exists already")
    lines_path = ex / doc.get("lines_file", "lines.json")
    lines_raw = lines_path.read_text(encoding="utf-8")

    def no_voice(*a, **k):
        raise RuntimeError("cut_head: the build tried to voice a line; nothing may be voiced (R234)")

    orig_make = engines.make

    def make_silent(v):                                # the build's engine, unable to voice anything
        e = orig_make(v)
        e.synth = no_voice
        return e
    try:                                               # all or nothing (Fable, round 7): on any failure the steps
        lag = cut_mp3(build.CACHE / f"{old['key']}.mp3", mp3, cut, int(probe["sample_rate"]),   # file, lines.json
                      int(probe["bit_rate"]))                                                  # and the cache go back
        new_meta = {"key": key, "key_fields": fields, "context": meta.get("context"), "display_text": text,
                    "length_s": build.mp3_length(mp3), "boundaries": shift_b, "words": new_words,
                    "cut_from": {"key": old["key"], "at_s": cut, "why": "R234: the line starts at its word "
                                 f"{word!r}; cut in the pause before it, nothing voiced again", **measured,
                                 "decoded_lag_samples": lag}}
        side.write_text(json.dumps(new_meta, indent=2, ensure_ascii=False), encoding="utf-8")
        steps_path.write_text(raw, encoding="utf-8")
        engines.make = make_silent
        try:
            out = build.build(str(steps_path))     # lines.json, written only at its end
        finally:
            engines.make = orig_make
        if out[line_id]["key"] != key:
            raise SystemExit(f"lines.json's {line_id} has key {out[line_id]['key']}, not {key}")
    except BaseException:
        steps_path.write_text(raw0, encoding="utf-8")
        lines_path.write_text(lines_raw, encoding="utf-8")
        mp3.unlink(missing_ok=True)
        side.unlink(missing_ok=True)
        print("cut_head: failed; the steps file, lines.json and the cache are as they were")
        raise
    print(f"{line_id}: {old['key']} -> {key}, {new_meta['length_s']:.3f} s (was {old['length_s']:.3f} s)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
