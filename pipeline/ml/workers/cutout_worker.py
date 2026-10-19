"""Runs in the ML venv only (pipeline.ml.paths.run): rembg cutouts with a BiRefNet model, one session for all items.

    job:   {"model": "birefnet-general", "device": "cpu"|"cuda", "decontaminate": false, "alpha_matting": false,
            "items": [{"src", "dst"}]}
    reply: {"device", "providers", "load_s", "items": [{"src", "dst", "seconds"}]}

Only BiRefNet models (MIT) are allowed: rembg's default, bria-rmbg, is BRIA's RMBG-2.0, licensed non-commercial, and
rembg falls back to it whenever no session is named. Every call here names one, and a model whose weights aren't
already in U2NET_HOME is refused rather than downloaded.
"""
import json
import os
import sys
import time
from pathlib import Path

import onnxruntime as ort

ALLOWED = ("birefnet-general", "birefnet-general-lite", "birefnet-massive", "birefnet-portrait", "birefnet-hrsod",
           "birefnet-dis", "birefnet-cod")


def main(job_path, reply_path):
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    model = job["model"]
    if model not in ALLOWED:
        raise SystemExit(f"{model}: not a BiRefNet model; only {', '.join(ALLOWED)} (bria-rmbg is non-commercial)")
    weights = Path(os.environ["U2NET_HOME"]) / f"{model}.onnx"
    if not weights.exists():
        raise SystemExit(f"{weights} is missing: fetch it first (research/huggingface/INSTALL_r1.md)")
    dev = job.get("device", "cpu")
    so = ort.SessionOptions()
    providers = ["CPUExecutionProvider"]
    if dev == "cuda":
        ort.preload_dlls()
        # BiRefNet at 1024 px needs about 6.5 GB of the card's 8: with onnxruntime's memory-pattern plan on, every
        # image after the first spilled into shared system memory and took 28 s instead of 1 (INSTALL_r1.md)
        so.enable_mem_pattern = False
        providers = [("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC",
                                                "arena_extend_strategy": "kSameAsRequested"}), "CPUExecutionProvider"]
    from PIL import Image
    from rembg import new_session, remove
    t = time.perf_counter()
    session = new_session(model, sess_opts=so, providers=providers)
    load_s = time.perf_counter() - t
    items = []
    for it in job["items"]:
        t = time.perf_counter()
        out = remove(Image.open(it["src"]).convert("RGB"), session=session,
                     decontaminate=bool(job.get("decontaminate")), alpha_matting=bool(job.get("alpha_matting")))
        Path(it["dst"]).parent.mkdir(parents=True, exist_ok=True)
        out.save(it["dst"])
        items.append({"src": it["src"], "dst": it["dst"], "seconds": round(time.perf_counter() - t, 3)})
    with open(reply_path, "w", encoding="utf-8") as f:
        json.dump({"device": dev, "providers": session.inner_session.get_providers(), "load_s": round(load_s, 2),
                   "items": items}, f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
