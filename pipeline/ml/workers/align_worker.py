"""Runs in the ML venv only (pipeline.ml.paths.run): Qwen3-ForcedAligner-0.6B word times for each item of a job.

    job:   {"model": dir, "device": "cuda"|"cpu", "language": "English",
            "items": [{"id", "wav" (16 kHz mono PCM16), "text"}]}
    reply: {"device", "load_s", "items": [{"id", "audio_s", "seconds", "words": [{"text", "start", "end"}]}]}

One model load serves every item. The aligner gives each word a start and an end in 80 ms steps (its timestamp
classes), forced to the text it is given: it never mishears, it only places. Up to 5 minutes of audio per item.
"""
import json
import sys
import time
import wave

import numpy as np
import torch
from transformers import AutoModelForTokenClassification, AutoProcessor


def read_wav(path):
    with wave.open(path, "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (16000, 1, 2):
            raise ValueError(f"{path}: needs 16 kHz mono PCM16 (pipeline.ml.align converts)")
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0


def main(job_path, reply_path):
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    dev = job.get("device", "cuda")
    if dev == "cuda" and not torch.cuda.is_available():
        dev = "cpu"
    t = time.perf_counter()
    proc = AutoProcessor.from_pretrained(job["model"])
    model = AutoModelForTokenClassification.from_pretrained(
        job["model"], dtype=torch.bfloat16 if dev == "cuda" else torch.float32).to(dev).eval()
    load_s = time.perf_counter() - t
    items = []
    for it in job["items"]:
        audio = read_wav(it["wav"])
        t = time.perf_counter()
        inputs, word_lists = proc.prepare_forced_aligner_inputs(audio=audio, transcript=it["text"],
                                                                language=job.get("language", "English"))
        inputs = inputs.to(model.device, model.dtype)
        with torch.inference_mode():
            logits = model(**inputs).logits
        stamps = proc.decode_forced_alignment(logits=logits, input_ids=inputs["input_ids"], word_lists=word_lists,
                                              timestamp_token_id=model.config.timestamp_token_id)[0]
        items.append({"id": it["id"], "audio_s": round(len(audio) / 16000, 3),
                      "seconds": round(time.perf_counter() - t, 4),
                      "words": [{"text": s["text"], "start": s["start_time"], "end": s["end_time"]} for s in stamps]})
    with open(reply_path, "w", encoding="utf-8") as f:
        json.dump({"device": dev, "load_s": round(load_s, 2), "items": items}, f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
