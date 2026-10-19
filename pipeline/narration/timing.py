"""A voiced line's word timings: the TTS engine's own log, or the forced aligner's (R227), and the one way to read them.

    source(voice) -> "aligner" | "engine"        a voice file's "word_timing": the aligner unless it says "engine"
    pause_min(voice, words_from) -> seconds      the shortest sentence-end pause that is heard, on those times
    aligned([(key, spoken)]) -> {key: words}     the aligner's spoken-text words per clip: from the cache, one batch
                                                 for the clips without them
    keep_display(key, display, words)            the display words the build mapped from them, kept with the cache
    meta(key, words_from=None, display=None)     the cache meta, its "words" (and "display_text") the aligner's when
                                                 words_from says so
    of(entry)                                    meta() for a lines.json entry, an edit plan's narration entry or an
                                                 avatar graphic's record, with the timing it was built with
    provenance(line) / provenance_for(lines, line_id, key)   what such an entry carries: {words_from, display_text}

Why: ElevenLabs logs a word's end up to 0.95 s into the pause after it (sentence ends logged to the clip's end), and
the planner times its beats, the next line after a comma, the marks' releases and the captions from those times. The
Qwen3 forced aligner (pipeline.ml.align) times every word against the audio itself: 0.06 s off on average, at most
0.28 s, against ElevenLabs' 0.18 s and 0.95 s (research/huggingface/INSTALL_r1.md). Its times come in 80 ms steps, so
breaths.beat_point stays the last check on where a word's sound stops before a cut or a beat.

Where it is set: the voice file's "word_timing" (exercises/<ex>/voice.json, or the steps file's voice_file). The build
records the choice per line in lines.json ("words_from": "aligner"; nothing when the engine's are used, so an engine
build writes exactly what it did before R227), the planner copies it with the line's display text into each narration
entry of edit_plan.json, and every reader loads words through meta() or of(), so a line keeps the timing it was built
with wherever it is read. Section A (R195: its approved cut stays as it is) and the CSC13 gate's exercise say "engine".

The cache: audio_cache/<key>.aligned.json beside the clip. "fields" are what the alignment was made from (the
aligner, the clip's SHA-256, the spoken text): a clip voiced again under its key (--force) or a new aligner is aligned
again by the build, anything else never is, so a re-build or a re-plan costs no aligner run; meta() refuses a cache
that no longer fits its clip rather than time new audio with old words. "spoken_words" are the aligner's; "displays"
holds them mapped onto each display text a line built from the clip shows (build.display_words, as an engine's
boundaries are mapped): two lines can share a clip (the key is the spoken text) and differ in how it is written.
"""
import hashlib
import json
from pathlib import Path

from pipeline.config import ROOT

CACHE = ROOT / "audio_cache"
SOURCES = ("aligner", "engine")
# The run-on check's floor on the aligner's times (R31, R85; WIRING_r1.md). The engine's sentence_pause_min_s was set
# against its own times, which give part of each pause to the word before it (ElevenLabs: 0.15 s measured is about
# 0.35 s heard). The aligner measures nearer the silence, in 80 ms steps: on Section A's 128 sentence ends the one the
# engine passed at 0.151 s measures 0.24 s, every other 0.32 s or more. Under 0.24 s (two steps or less) keeps every
# decision the engine made there, and is about the same pause heard
ALIGNER_PAUSE_MIN_S = 0.24
_SHA = {}


def source(voice):
    """The word timing a voice file asks for: "aligner" (the default, R227) or "engine"."""
    s = voice.get("word_timing", "aligner")
    if s not in SOURCES:
        raise SystemExit(f"word_timing {s!r}: 'aligner' or 'engine'")
    return s


def pause_min(voice, words_from):
    """The shortest sentence-end pause that counts as heard, on the times a line was built with: the voice file's
    sentence_pause_min_aligner_s (ALIGNER_PAUSE_MIN_S) for the aligner's, its sentence_pause_min_s for the engine's."""
    if words_from == "aligner":
        return voice.get("sentence_pause_min_aligner_s", ALIGNER_PAUSE_MIN_S)
    return voice.get("sentence_pause_min_s", 0.25)


def side_path(key, cache=CACHE):
    return Path(cache) / f"{key}.aligned.json"


def _sha(path):
    """A file's SHA-256, remembered while its size and time stay the same."""
    st = path.stat()
    k = (str(path), st.st_size, st.st_mtime_ns)
    if k not in _SHA:
        _SHA[k] = hashlib.sha256(path.read_bytes()).hexdigest()
    return _SHA[k]


def fields(key, spoken, cache=CACHE):
    from pipeline.ml import align
    return {"aligner": align.MODEL_ID, "language": "English", "audio_sha256": _sha(Path(cache) / f"{key}.mp3"),
            "spoken_text": spoken}


def _read(key, cache=CACHE):
    p = side_path(key, cache)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def aligned(pairs, cache=CACHE, device="cuda"):
    """{key: [{word, start, end, char}]} (the spoken text's words) for each (key, spoken text): the cached alignment
    when it was made from this clip and text by this aligner, else the aligner's, one model load for all of them."""
    out, todo = {}, {}
    for key, spoken in pairs:
        if key in out or key in todo:
            continue
        f = fields(key, spoken, cache)
        d = _read(key, cache)
        if d and d.get("fields") == f:
            out[key] = d["spoken_words"]
        else:
            todo[key] = (spoken, f)
    if todo:
        from pipeline.ml import align
        keys = list(todo)
        print(f"  aligner: {len(keys)} clip(s) to align (R227)")
        res = align.align_many([(Path(cache) / f"{k}.mp3", todo[k][0]) for k in keys], device=device)
        for k, words in zip(keys, res):                  # (display words made from an older alignment go with it)
            side_path(k, cache).write_text(json.dumps({"key": k, "fields": todo[k][1], "spoken_words": words,
                                                       "displays": {}}, indent=1, ensure_ascii=False),
                                           encoding="utf-8")
            out[k] = words
    return out


def keep_display(key, display, words, cache=CACHE):
    """Keep the display words mapped from a clip's alignment onto one display text with it (only when they changed)."""
    d = _read(key, cache)
    if d is None:
        raise FileNotFoundError(f"{side_path(key, cache)}: align the clip first (aligned())")
    shown = d.setdefault("displays", {})
    if shown.get(display) != words:
        shown[display] = words
        side_path(key, cache).write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


def meta(key, words_from=None, display=None, *, cache=CACHE):
    """A clip's cache meta (audio_cache/<key>.json). words_from "aligner": its "words" are the aligner's mapped onto
    `display` (the line's display text; without it, the clip's only one, or the meta's own), and "display_text" is that
    text; the engine's words stay as "engine_words". None or "engine": the meta exactly as the engine's build wrote it.
    An alignment made from other audio than the clip's now (a clip voiced again under its key) is refused."""
    m = json.loads((Path(cache) / f"{key}.json").read_text(encoding="utf-8"))
    if words_from in (None, "engine"):
        return m
    if words_from != "aligner":
        raise ValueError(f"words_from {words_from!r}: 'aligner' or 'engine'")
    again = "run pipeline.narration.build on the steps file again (no voice is generated for cached lines)"
    d = _read(key, cache)
    if not d:
        raise FileNotFoundError(f"{side_path(key, cache)} is missing: {again}")
    spoken = (m.get("key_fields") or {}).get("spoken_text", d["fields"].get("spoken_text"))
    if d.get("fields") != fields(key, spoken, cache):
        raise FileNotFoundError(f"{side_path(key, cache)} was made from other audio or by another aligner than "
                                f"the clip's now: {again}")
    shown = d.get("displays") or {}
    text = display if display in shown else next(iter(shown)) if display is None and len(shown) == 1 else \
        m["display_text"] if display is None and m["display_text"] in shown else None
    if text is None:
        raise FileNotFoundError(f"{side_path(key, cache)} has no display words for "
                                f"{(display or m['display_text'])[:60]!r}: {again}")
    return {**m, "display_text": text, "words": shown[text], "engine_words": m["words"], "words_from": "aligner"}


def provenance(line):
    """What an entry made from a lines.json line carries so readers time it as the build did: {words_from,
    display_text} for an aligner-timed line, nothing for an engine-timed one (so engine outputs stay as before)."""
    return {"words_from": line["words_from"], "display_text": line["text"]} if line.get("words_from") else {}


def provenance_for(lines, line_id, key):
    """provenance() for a clip made from a line (an avatar render's audio_key): the line's own while the line is still
    that clip; a clip the line has since been voiced away from keeps the engine's."""
    line = lines.get(line_id) or {}
    return provenance(line) if line.get("key") == key else {}


def of(entry, cache=CACHE):
    """The meta for a lines.json entry (its display text is "text"), an edit plan's narration entry or an avatar
    graphic's record ("display_text", from provenance()), with the timing it was built with."""
    return meta(entry.get("key") or entry["audio_key"], entry.get("words_from"),
                entry.get("display_text", entry.get("text")), cache=cache)
