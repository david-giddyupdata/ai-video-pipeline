"""Words and their boxes on stills with RapidOCR and PP-OCRv6 (Apache-2.0), beside Windows OCR.

    ocr(folder) -> {file name: [(text, x, y, w, h)]}           linecheck.ocr()'s shape, a drop-in
    records(folder) -> {file name: [{text, x, y, words}]}      winocr.ps1's line records (marks, privacy)
    read(pngs) -> [{path, seconds, lines}]                     everything, per image, with scores
    second_read(pngs) -> {path: [{text, x, y, words}]}         R227's second reader: these stills only, cached
    words_of(lines) -> [(text, x, y, w, h)]                    a still's line records as linecheck.ocr() words

Why: Windows OCR skips small numeric input boxes (Dash's 45 and 68), runs a two-line tooltip into one line, and its
boxes move from frame to frame (GOTCHAS, the lessons). PP-OCRv6 detects each line of text on its own and gives word
boxes, or one box per character (chars=True) for measuring where letters sit. Measured against Windows OCR on our
own stills: research/huggingface/INSTALL_r1.md.

model: "medium" (det 62 MB + rec 77 MB, PaddlePaddle's own ONNX) reads best; "small" (10 + 21 MB) ships inside the
rapidocr wheel and is faster. device: "cpu" or "cuda" (onnxruntime-gpu); both run in the ML venv through
pipeline.ml.paths.run, one call for all the images. Words are the recogniser's pieces of a line, so punctuation
stays on its word ("performance,"), as in Windows OCR.
"""
import hashlib
import json
from pathlib import Path

from pipeline.ml import paths

# R227: RapidOCR reads beside Windows OCR, never instead. Medium on the GPU (about 0.5 s a still after 3 s starting):
# it reads two-line labels, small numbers and underscored names Windows OCR misses, but its boxes sit 4 to 7 px taller
# than the letters' ink and move a few px between near-identical frames, and it invents a lone "0" now and then
# (INSTALL_r1.md, item 2). So callers use it on the stills where Windows OCR missed, to find text, not to measure it.
SECOND = {"model": "medium", "device": "cuda"}
PAD_PX = 5                  # a box's height over the ink (median of 4 to 7): take it off before a readability test
CACHE_NAME = "_rapidocr.json"

# The detector's own settings, from PaddlePaddle's inference.yml for PP-OCRv6 small and medium alike (ImageNet
# normalisation, DB thresholds); rapidocr's defaults (0.5/0.5, 0.3, 0.5, unclip 1.6) are for older models and pad
# every box. use_dilation off as in PaddleOCR's DBPostProcess.
DET_PARAMS = {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225], "thresh": 0.2, "box_thresh": 0.45,
              "unclip_ratio": 1.4, "max_candidates": 3000, "use_dilation": False}


def read(pngs, model="medium", device="cpu", chars=False, stats=None):
    """[{path, seconds, line_boxes_only, lines: [{text, score, box, words: [{t, x, y, w, h, score}]}]}], one per
    image, in order."""
    if model not in ("small", "medium"):
        raise ValueError(f"model {model!r}: small or medium")
    pngs = [str(Path(p).resolve()) for p in pngs]
    if not pngs:
        return []
    job = {"images": pngs, "model": model, "device": device, "chars": chars, "det_params": DET_PARAMS}
    if model == "medium":
        job.update(det=str(paths.OCR_DET_MEDIUM), rec=str(paths.OCR_REC_MEDIUM), keys=str(paths.OCR_REC_KEYS))
    reply = paths.run("ocr_worker", job)
    if stats is not None:
        stats.update({k: reply[k] for k in ("device", "providers", "load_s")})
    return reply["images"]


def _images(folder):
    """The images winocr.ps1 reads: *.png and *.jpg under the folder, by name."""
    return sorted((p for p in Path(folder).rglob("*") if p.suffix.lower() in (".png", ".jpg")), key=lambda p: p.name)


def records(folder, model="medium", device="cpu"):
    """{file name: [{text, x, y, words: [{t, x, y, w, h}]}]}: winocr.ps1's records, for code that works by line."""
    imgs = _images(folder)
    out = {}
    for p, rec in zip(imgs, read(imgs, model, device)):
        out[p.name] = [{"text": ln["text"], "x": ln["box"][0], "y": ln["box"][1],
                        "words": [{k: w[k] for k in ("t", "x", "y", "w", "h")} for w in ln["words"]]}
                       for ln in rec["lines"] if ln["words"]]
    return out


def ocr(folder, model="medium", device="cpu"):
    """{file name: [(text, x, y, w, h)]} for every image in the folder: linecheck.ocr()'s return, word by word."""
    return {name: [(w["t"], w["x"], w["y"], w["w"], w["h"]) for ln in lines for w in ln["words"]]
            for name, lines in records(folder, model, device).items()}


def _sig(p, model):
    """What a cached reading was made from: the model, the detector's settings, the still's size and time."""
    st = p.stat()
    return [model, hashlib.sha256(json.dumps(DET_PARAMS, sort_keys=True).encode()).hexdigest()[:12], st.st_size,
            st.st_mtime_ns]


def second_read(pngs, model=SECOND["model"], device=SECOND["device"]):
    """R227's second reader on just these stills: {str(path): [{text, x, y, words: [{t, x, y, w, h}]}]}, winocr.ps1's
    line records. Each still's folder keeps what was read (_rapidocr.json, keyed by the file's size and time and the
    model), so a check run again reads nothing twice; the rest go to RapidOCR in one call."""
    pngs = [Path(p).resolve() for p in dict.fromkeys(str(p) for p in pngs)]
    out, todo, caches = {}, [], {}
    for p in pngs:
        c = caches.setdefault(p.parent, None)
        if c is None:
            f = p.parent / CACHE_NAME
            try:
                c = caches[p.parent] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            except ValueError:                        # a cache cut short: read again
                c = caches[p.parent] = {}
        hit = c.get(p.name)
        if hit and hit.get("sig") == _sig(p, model):
            out[str(p)] = hit["lines"]
        else:
            todo.append(p)
    if todo:
        for p, rec in zip(todo, read(todo, model, device)):
            lines = [{"text": ln["text"], "x": ln["box"][0], "y": ln["box"][1],
                      "words": [{k: w[k] for k in ("t", "x", "y", "w", "h")} for w in ln["words"]]}
                     for ln in rec["lines"] if ln["words"]]
            out[str(p)] = lines
            caches[p.parent][p.name] = {"sig": _sig(p, model), "lines": lines}
        for d in {p.parent for p in todo}:
            (d / CACHE_NAME).write_text(json.dumps(caches[d]), encoding="utf-8")
    return out


def words_of(lines):
    """[(text, x, y, w, h)]: a still's line records as linecheck.ocr()'s words."""
    return [(w["t"], w["x"], w["y"], w["w"], w["h"]) for ln in lines for w in ln["words"]]
