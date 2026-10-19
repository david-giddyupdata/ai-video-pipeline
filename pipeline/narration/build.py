"""Voice every narration line of a step list, through the audio cache (SPEC §5.4).

    python -m pipeline.narration.build <steps file> [--force]

Writes audio_cache/<key>.mp3 + <key>.json and exercises/<ex>/lines.json (line_id -> key, text, length, cue offset).
Only lines whose key changed are generated: editing a line, its respelling or the voice regenerates exactly those.
The voice is exercises/<ex>/voice.json, or the step list's own "voice_file" (the CSC13 test's clone, R98); a step
list may also name its own "pronunciation_file" and "lines_file" (R248's reel: a second voice beside the clone's files,
neither overwriting the other). A line
with an em dash (R93) stops the build before anything is voiced.

Word times (R227): the voice file's "word_timing" is "aligner" unless it says "engine". With the aligner, every line is
voiced first, then all the clips are timed in one aligner run (pipeline.narration.timing, cached beside each clip, so
a re-build aligns only new clips), and the run-on check (its floor the voice's sentence_pause_min_aligner_s, since the
engine's sentence_pause_min_s was set against its own times: timing.pause_min), cue and click offsets and marks use
those times; each line in lines.json says "words_from": "aligner" so every later reader takes the same times. With "engine" the build writes
exactly what it did before R227 (Section A and the CSC13 test, R195).
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from pipeline.config import EXERCISES, ROOT, tool
from pipeline.ml import align
from pipeline.narration import engines, timing
from pipeline.edit import sentences
from pipeline.edit.marks import release_time, word_time
from pipeline.narration.respell import load_terms, respell, spoken_to_display

CACHE = ROOT / "audio_cache"
WORD = re.compile(r"[\w][\w'’.\-/]*[\w]|[\w]")      # display words: keeps github.com/codespaces and my-agentic-workshop
DASHES = re.compile("\u2014| \u2013 |--")     # R93: an em dash, or a spaced en dash or double hyphen for one


def r93(text):
    """The em dashes (R93) in a text the viewer or David reads or hears: [(position, what)]."""
    return [(m.start(), m.group(0)) for m in DASHES.finditer(text or "")]


def cache_key(engine, spoken, tighten, prev_spoken=None, next_spoken=None):
    """A line's key is its own spoken text and the voice (R99). The neighbouring lines go to the engine as context
    when the line is voiced (ElevenLabs' previous_text and next_text, which aren't billed) but stay out of the key, so
    adding or editing a neighbour doesn't voice this line again. previous_text and next_text stay in the fields as
    None, which keeps every key made before R99 for engines without context (edge-tts) unchanged."""
    fields = {**engine.key_fields(), "spoken_text": spoken, "tighten": tighten, "previous_text": None,
              "next_text": None}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode("utf-8")).hexdigest()[:20], fields


def mp3_length(path):
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True)
    return round(float(out.stdout.strip()), 3)


def display_words(display, spoken, pieces, boundaries):
    """Engine word boundaries (spoken text) -> timed display words, for cue words and captions."""
    located, pos = [], 0
    for text, t0, t1 in boundaries:                  # find each boundary's characters in the spoken text, in order
        i = spoken.find(text, pos)
        if i < 0:
            continue
        located.append((i, i + len(text), t0, t1))
        pos = i + len(text)
    words = []
    for m in WORD.finditer(display):
        hits = []
        for s0, s1, t0, t1 in located:
            d0, d1 = spoken_to_display(pieces, s0, s1)
            if d0 is not None and d0 < m.end() and d1 > m.start():
                hits.append((t0, t1))
        if hits:
            words.append({"word": m.group(0), "start": min(h[0] for h in hits), "end": max(h[1] for h in hits),
                          "char": [m.start(), m.end()]})
    return words


def with_ellipses(spoken, pieces, stops):
    """Turn the full stops at display positions `stops` into ellipses in the spoken text, keeping the character map:
    each stop sits in a plain (not respelled) piece, which is split so the stop and its ellipsis map as one block."""
    for d in sorted(stops, reverse=True):
        k = next((i for i, (ds, de, ss, se, rs) in enumerate(pieces) if ds <= d < de and not rs), None)
        if k is None:                                         # the stop is part of a respelled term: left as it is
            continue
        ds, de, ss, se, _ = pieces[k]
        at = ss + (d - ds)                                    # the stop in the spoken text
        spoken = spoken[:at] + "..." + spoken[at + 1:]
        split = [(ds, d, ss, at, False), (d, d + 1, at, at + 3, True), (d + 1, de, at + 3, se + 2, False)]
        pieces = (pieces[:k] + [p for p in split if p[1] > p[0]]
                  + [(a, b, c + 2, e + 2, r) for a, b, c, e, r in pieces[k + 1:]])
    return spoken, pieces


def build(steps_path, force=False):
    doc = json.loads(Path(steps_path).read_text(encoding="utf-8"))
    ex_dir = EXERCISES / doc["exercise"]
    voice = json.loads((ex_dir / doc.get("voice_file", "voice.json")).read_text(encoding="utf-8"))
    engine = engines.make(voice)
    terms = load_terms(doc["exercise"], engine.name, doc.get("pronunciation_file", "pronunciation.json"))
    CACHE.mkdir(exist_ok=True)
    lines_path = ex_dir / doc.get("lines_file", "lines.json")
    lines = json.loads(lines_path.read_text(encoding="utf-8")) if lines_path.exists() else {}

    variables = doc.get("variables", {})
    sub = lambda s: re.sub(r"\{(\w+)\}", lambda m: variables.get(m.group(1), m.group(0)), s)
    marks_by_line = {s["narration"]["line_id"]: s.get("marks", []) for s in doc["steps"]}
    nars = [dict(s["narration"], text=sub(s["narration"]["text"])) for s in doc["steps"] if s.get("narration", {}).get("source", "clone") == "clone"
            and s["narration"].get("text")]
    # on-screen labels get a spoken pause before them (David, 2026-10-06): "under - By repository"; captions unchanged
    pause = voice.get("label_pause", " - ").strip()
    with_labels = lambda n: sorted(terms + [{"display": lb, "spoken": f"{pause} {respell(lb, terms)[0]}", "tighten": False}
                                            for lb in n.get("labels", [])], key=lambda t: -len(t["display"]))
    spoken = [respell(n["text"], with_labels(n), n.get("spoken")) for n in nars]
    dashed = [f"{n['line_id']}: {w!r} at {i}" for n, (sp, _, _) in zip(nars, spoken)
              for t in (n["text"], sp) for i, w in r93(t)]
    if dashed:
        raise SystemExit("R93: em dashes in the narration; use a comma, a colon, a period or parentheses:\n  "
                         + "\n  ".join(dict.fromkeys(dashed)))
    words_from = timing.source(voice)                # R227: the aligner's word times, unless the voice says "engine"
    min_pause = timing.pause_min(voice, words_from)  # (each source's own floor: the engine's times run pauses short)

    def voiced(n, sp, pieces, tighten, prev_sp, next_sp):
        key, fields = cache_key(engine, sp, tighten, prev_sp, next_sp)
        mp3, meta_path = CACHE / f"{key}.mp3", CACHE / f"{key}.json"
        if not force and mp3.exists() and meta_path.exists():
            return key, json.loads(meta_path.read_text(encoding="utf-8")), "cached"
        audio, boundaries = engine.synth(sp, prev_sp, next_sp) if engine.uses_neighbours else engine.synth(sp)
        mp3.write_bytes(audio)
        meta = {"key": key, "key_fields": fields, "context": {"previous_text": prev_sp, "next_text": next_sp}
                if engine.uses_neighbours else None, "display_text": n["text"], "length_s": mp3_length(mp3),
                "boundaries": boundaries, "words": display_words(n["text"], sp, pieces, boundaries)}
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return key, meta, "generated"

    def timed(js):
        """Each job's timed display words ("tm": the meta the rest of the build reads): the engine's, or the
        aligner's mapped onto the display text exactly as the engine's are, all of the jobs' clips in one batch."""
        if words_from == "engine":
            for j in js:
                j["tm"] = j["meta"]
            return
        spoken_words = timing.aligned([(j["key"], j["sp"]) for j in js])
        for j in js:
            words = display_words(j["n"]["text"], j["sp"], j["pieces"], align.as_boundaries(spoken_words[j["key"]]))
            timing.keep_display(j["key"], j["n"]["text"], words)
            j["tm"] = {**j["meta"], "display_text": j["n"]["text"], "words": words}

    jobs = []                                        # every line voiced first, so the aligner loads once for all
    for i, n in enumerate(nars):
        sp, pieces, tighten = spoken[i]
        alone = doc.get("standalone_lines")              # lines that don't follow each other (an intro and an outro)
        prev_sp = spoken[i - 1][0] if i > 0 and not alone else None
        next_sp = spoken[i + 1][0] if i + 1 < len(nars) and not alone else None
        key, meta, state = voiced(n, sp, pieces, tighten, prev_sp, next_sp)
        jobs.append({"n": n, "sp": sp, "pieces": pieces, "tighten": tighten, "prev": prev_sp, "next": next_sp,
                     "key": key, "meta": meta, "state": state})
    timed(jobs)
    again = []
    for j in jobs:
        n, tm = j["n"], j["tm"]
        # every sentence end is heard (R31, R85): edge-tts reads "dev." or "lib." as an abbreviation and runs on, so a
        # sentence end that paused under min_pause gets an ellipsis in the spoken text and is voiced again
        short = [b for b in sentences.breaks(n["text"], tm["words"]) if b["pause_s"] < min_pause]
        ends = {id(b): tm["words"][b["after"]]["char"][1] + re.search(r"[.?!]", n["text"][tm["words"][b["after"]]["char"][1]:]).start()
                for b in short}
        if [b for b in short if n["text"][ends[id(b)]] != "."]:      # a question or an exclamation keeps its mark
            print(f"  WARNING {n['line_id']}: a sentence end that isn't a full stop runs on "
                  f"({[b['before_text'][-30:] for b in short if n['text'][ends[id(b)]] != '.']}); fix it in the text")
            short = [b for b in short if n["text"][ends[id(b)]] == "."]
        if short and not n.get("spoken"):
            stops = [ends[id(b)] for b in short]
            j["sp"], j["pieces"] = with_ellipses(j["sp"], j["pieces"], stops)
            j["key"], j["meta"], state2 = voiced(n, j["sp"], j["pieces"], j["tighten"], j["prev"], j["next"])
            j["state"] += f", run-on at {', '.join(repr(b['before_text'][-20:]) for b in short)} re-voiced ({state2})"
            again.append(j)
        elif short:
            print(f"  WARNING {n['line_id']}: sentence end runs on ({[b['before_text'][-30:] for b in short]}); "
                  "the line has its own spoken text, so fix it there")
    timed(again)
    for j in again:
        left = [b for b in sentences.breaks(j["n"]["text"], j["tm"]["words"]) if b["pause_s"] < min_pause]
        if left:
            print(f"  WARNING {j['n']['line_id']}: sentence end still runs on after the ellipsis: "
                  f"{[b['before_text'][-30:] for b in left]}")
    for j in jobs:
        n, tm, key, sp, state = j["n"], j["tm"], j["key"], j["sp"], j["state"]
        cue = n.get("cue_word")
        cue_s = next((w["start"] for w in tm["words"] if w["word"] == cue), None) if cue else None
        click = n.get("click_word")
        click_s = next((w["start"] for w in tm["words"] if w["word"] == click), None) if click else None
        if click and click_s is None:
            print(f"  WARNING {n['line_id']}: click word {click!r} not found in the word timings")
        if cue and cue_s is None:
            print(f"  WARNING {n['line_id']}: cue word {cue!r} not found in the word timings")
        marks = []
        for m in marks_by_line.get(n["line_id"], []):
            phrase = sub(m["at_word"])
            marks.append({"at_s": word_time(tm, phrase, m.get("occurrence", 1)),
                          "release_s": release_time(tm, phrase, m.get("occurrence", 1),
                                                    sub(m["until_word"]) if m.get("until_word") else None)})
        lines[n["line_id"]] = {"key": key, "status": n.get("status", "draft"), "text": n["text"], "spoken": sp,
                               "engine": engine.name, "voice": voice.get("voice"), "length_s": tm["length_s"],
                               "cue_word": cue, "cue_offset_s": cue_s,
                               "click_word": click, "click_offset_s": click_s, "marks": marks}
        if words_from == "aligner":                  # only then: an engine build writes what it did before R227
            lines[n["line_id"]]["words_from"] = "aligner"
        print(f"{n['line_id']}: {state} {key}  {tm['length_s']:.2f}s  cue {cue!r} at {cue_s}  click {click!r} at {click_s}  | {sp}")
    lines_path.write_text(json.dumps(lines, indent=2, ensure_ascii=False), encoding="utf-8")
    return lines


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    build(sys.argv[1], force="--force" in sys.argv)
