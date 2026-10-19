"""Runs in the ML venv only (pipeline.ml.paths.run): RapidOCR with PP-OCRv6 on each image of a job.

    job:   {"images": [path], "model": "small"|"medium", "device": "cpu"|"cuda", "chars": false,
            "det_params": {...}, "det": path, "rec": path, "keys": path}   (det/rec/keys for medium; small ships in
                                                                            the wheel)
    reply: {"device", "providers", "load_s", "images": [{"path", "seconds", "line_boxes_only",
            "lines": [{"text", "score", "box": [x, y, w, h], "words": [{"t", "x", "y", "w", "h", "score"}]}]}]}

A line is what the detector found as one run of text; words are the recogniser's pieces of it (with chars: one box
per character instead, for measuring where letters sit). Boxes are frame pixels, axis-aligned around RapidOCR's
four corners. A line whose word boxes rapidocr couldn't place comes back as one word with the line's box
(line_boxes_only counts them), so a caller matching text still finds it.
"""
import json
import sys
import time

import onnxruntime as ort


def axis_box(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = int(round(min(xs))), int(round(min(ys)))
    return [x0, y0, int(round(max(xs))) - x0, int(round(max(ys))) - y0]


def squash(s):
    return "".join(s.split())


def read_lines(eng, path):
    """[{text, score, box, words}] and how many lines got only their line box. rapidocr drops a line whose word
    boxes all fail and then numbers the rest wrongly (or raises IndexError in its score filter), so words are
    matched to lines by their text, and a failed read is redone without word boxes."""
    try:
        r, fallback = eng(path), False
    except IndexError:
        r, fallback = eng(path, return_word_box=False), True
    if not r.txts:
        return [], 0
    pieces = [] if fallback else [ws for ws in (r.word_results or ()) if ws]
    lines, j, bare = [], 0, 0
    for box, txt, score in zip(r.boxes, r.txts, r.scores):
        lbox = axis_box(box.tolist())
        words = []
        if j < len(pieces) and squash("".join(w[0] for w in pieces[j])) in squash(txt):
            words = [dict(zip("xywh", axis_box(b)), t=w, score=round(float(s), 4)) for w, s, b in pieces[j]
                     if b is not None]
            j += 1
        if not words:
            words, bare = [dict(zip("xywh", lbox), t=txt, score=round(float(score), 4))], bare + 1
        lines.append({"text": txt, "score": round(float(score), 4), "box": lbox, "words": words})
    return lines, bare


def main(job_path, reply_path):
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    dev = job.get("device", "cpu")
    if dev == "cuda":
        ort.preload_dlls()          # the CUDA and cuDNN DLLs come from the nvidia-* wheels in this venv
    from rapidocr import RapidOCR
    params = {"Global.log_level": "warning", "Global.return_word_box": True,
              "Global.return_single_char_box": bool(job.get("chars")),
              "EngineConfig.onnxruntime.use_cuda": dev == "cuda",
              # the recogniser sees a new crop width almost every line; an exhaustive cuDNN search per shape
              # costs far more than it saves
              "EngineConfig.onnxruntime.cuda_ep_cfg.cudnn_conv_algo_search": "HEURISTIC"}
    params.update({f"Det.{k}": v for k, v in (job.get("det_params") or {}).items()})
    if job.get("model") == "medium":
        params.update({"Det.model_path": job["det"], "Rec.model_path": job["rec"], "Rec.rec_keys_path": job["keys"]})
    t = time.perf_counter()
    eng = RapidOCR(params=params)
    for load in ("_load_det_model", "_load_cls_model", "_load_rec_model"):   # rapidocr loads on first use; load
        if hasattr(eng, load):                                                # now, so an image's time is its own
            getattr(eng, load)()
    load_s = time.perf_counter() - t
    det = getattr(eng, "text_det", None)
    providers = det.session.session.get_providers() if det is not None else []
    images = []
    for path in job["images"]:
        t = time.perf_counter()
        lines, bare = read_lines(eng, path)
        images.append({"path": path, "seconds": round(time.perf_counter() - t, 4), "line_boxes_only": bare,
                       "lines": lines})
    with open(reply_path, "w", encoding="utf-8") as f:
        json.dump({"device": dev, "providers": providers, "load_s": round(load_s, 2), "images": images}, f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
