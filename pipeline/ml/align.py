"""Word times from any audio and the text spoken in it: Qwen3-ForcedAligner-0.6B (Apache-2.0), run locally.

    align(audio, text) -> [{word, start, end, char}]
    align_many([(audio, text), ...]) -> one such list per pair, one model load for all
    as_boundaries(words) -> [(text, start, end)], the engines' boundary shape (pipeline.narration.engines)

The same shape as an audio_cache line's "words": seconds from the clip's start, and char, the word's [start, end)
in the text given. Give it the spoken text (respellings and all, as the voice said it); build.display_words() maps
as_boundaries() onto the display text exactly as it maps an engine's own boundaries.

Why: ElevenLabs logs word ends up to half a second into the following pause (GOTCHAS), edge-tts has its own
timings, and Vosk is the weaker choice for recorded audio. A forced aligner times every word against the audio
itself, for any voice. Its times come in 80 ms steps, so breaths.beat_point stays the final word on where a word's
sound stops before a cut or a beat. Measured against both: research/huggingface/INSTALL_r1.md.

Runs in the ML venv (torch, transformers) through pipeline.ml.paths.run; audio is converted to 16 kHz mono first.
At most 5 minutes of audio per pair.
"""
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from pipeline.config import tool
from pipeline.ml import paths

MAX_S = 300.0
# what a cached alignment was made by (pipeline.narration.timing): the weights' Hub revision, and this module's own
# mapping of the aligner's tokens onto the text (bump the suffix when _spans or the conversion changes)
MODEL_ID = "Qwen/Qwen3-ForcedAligner-0.6B-hf@c07281df/map1"


def _kept(ch):
    """The characters the aligner keeps from a text (its processor's rule): letters, digits, the ASCII apostrophe."""
    return ch == "'" or unicodedata.category(ch)[0] in "LN"


def _spans(text, tokens):
    """Each aligner token's [start, end) in text. The tokens are the text's kept characters, split at whitespace,
    in order, so walking the kept characters places every token exactly (github.com/codespaces is one token)."""
    kept = [i for i, ch in enumerate(text) if _kept(ch)]
    out, k = [], 0
    for tok in tokens:
        idx = kept[k:k + len(tok)]
        if len(idx) != len(tok) or "".join(text[i] for i in idx) != tok:
            where = f"character {idx[0]}" if idx else "the text's end"
            raise ValueError(f"aligner token {tok!r} doesn't match the text at {where}")
        out.append([idx[0], idx[-1] + 1])
        k += len(tok)
    return out


def _wav16k(src, dst):
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(dst)], check=True)


def align_many(pairs, language="English", device="cuda", stats=None):
    """[(audio path, text)] -> [[{word, start, end, char}]]. stats: a dict to receive the run's timings."""
    with tempfile.TemporaryDirectory(prefix="aidv_align_") as tmp:
        items = []
        for i, (audio, text) in enumerate(pairs):
            wav = Path(tmp) / f"{i:04d}.wav"
            _wav16k(audio, wav)
            if wav.stat().st_size / 32000 > MAX_S:
                raise ValueError(f"{audio}: over {MAX_S:.0f} s; split it first")
            items.append({"id": str(i), "wav": str(wav), "text": text})
        reply = paths.run("align_worker", {"model": str(paths.ALIGNER), "device": device, "language": language,
                                           "items": items})
    if stats is not None:
        stats.update({"device": reply["device"], "load_s": reply["load_s"],
                      "items": [{k: it[k] for k in ("audio_s", "seconds")} for it in reply["items"]]})
    out = []
    for (audio, text), it in zip(pairs, reply["items"]):
        spans = _spans(text, [w["text"] for w in it["words"]])
        out.append([{"word": text[a:b], "start": w["start"], "end": w["end"], "char": [a, b]}
                    for w, (a, b) in zip(it["words"], spans)])
    return out


def align(audio, text, language="English", device="cuda"):
    """Word times for one clip and the text spoken in it."""
    return align_many([(audio, text)], language, device)[0]


def as_boundaries(words):
    """[(text, start, end)]: what an engine returns, for narration.build.display_words."""
    return [(w["word"], w["start"], w["end"]) for w in words]
