"""Local models from the Hugging Face survey (research/huggingface/INSTALL_r1.md), as thin wrappers beside the
pipeline's own methods. Wired in by R227 (research/huggingface/WIRING_r1.md): the aligner gives narration word times
(pipeline.narration.timing), BiRefNet cuts generated art out (tools/gen_image.py --cutout), RapidOCR reads again where
Windows OCR missed (the line check, the named check, the privacy report).

    align.py    word times from audio and its script (Qwen3-ForcedAligner-0.6B)
    ocr.py      words and boxes on stills (RapidOCR with PP-OCRv6), in linecheck.ocr()'s shape
    cutout.py   a PNG's subject on a transparent background (rembg with BiRefNet)

The models need torch, onnxruntime and their CUDA libraries, which stay out of the pipeline's own Python: they live
in a venv (paths.VENV_PY), and each wrapper runs a worker script there (workers/) through paths.run(). The weights
live under paths.MODELS, outside the repo and OneDrive; workers never download anything.
"""
