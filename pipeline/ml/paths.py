"""Where the local models and their venv live, and the one way the pipeline calls into that venv.

Everything sits outside the repo and OneDrive (machine defaults): the venv under ~/.venvs, the weights under
~/.aidv-tools/models. Weights are fetched once, by hand, through pipeline/hf_ipv4.py (this PC's IPv6 route to
Hugging Face resets TLS); research/huggingface/INSTALL_r1.md lists each file, its source and its licence.

run(worker, job) writes the job as JSON, runs workers/<worker>.py in the venv's Python, isolated (-I: the
worker sees only the venv's own packages, never the pipeline or the current folder) and offline (HF_HUB_OFFLINE: a
missing weight file fails loudly rather than downloading), and returns the worker's JSON reply.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

HOME = Path.home()
VENV = HOME / ".venvs" / "aidv-ml"                    # Python 3.14: torch 2.14.1+cu130, transformers 5.20.1,
VENV_PY = VENV / "Scripts" / "python.exe"            # onnxruntime-gpu 1.31.0, rapidocr 3.10.0, rembg 2.0.85
TOOLS = HOME / ".aidv-tools"
MODELS = TOOLS / "models"
WORKERS = Path(__file__).resolve().parent / "workers"

# Qwen3-ForcedAligner-0.6B, transformers-native weights (Apache-2.0)
ALIGNER = MODELS / "Qwen3-ForcedAligner-0.6B-hf"
# PP-OCRv6 medium from PaddlePaddle's own repos (Apache-2.0); the small pair ships inside the rapidocr wheel
OCR_DET_MEDIUM = MODELS / "PP-OCRv6_medium_det_onnx" / "inference.onnx"
OCR_REC_MEDIUM = MODELS / "PP-OCRv6_medium_rec_onnx" / "inference.onnx"
OCR_REC_KEYS = MODELS / "PP-OCRv6_medium_rec_onnx" / "rec_keys.txt"   # the character list from its inference.yml
# rembg's model folder (U2NET_HOME): birefnet-general.onnx (MIT). Never rembg's default model: bria-rmbg is
# RMBG-2.0, non-commercial, and is not here
REMBG_HOME = MODELS / "rembg"


def run(worker, job, timeout=3600):
    """Run workers/<worker>.py in the venv on `job` (a JSON-able dict); its JSON reply."""
    if not VENV_PY.exists():
        raise FileNotFoundError(f"the ML venv is missing: {VENV_PY} (research/huggingface/INSTALL_r1.md)")
    env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", U2NET_HOME=str(REMBG_HOME),
               PYTHONIOENCODING="utf-8")
    with tempfile.TemporaryDirectory(prefix="aidv_ml_") as tmp:
        jp, rp = Path(tmp) / "job.json", Path(tmp) / "reply.json"
        jp.write_text(json.dumps(job), encoding="utf-8")
        res = subprocess.run([str(VENV_PY), "-I", str(WORKERS / f"{worker}.py"), str(jp), str(rp)],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                             timeout=timeout)
        if res.returncode or not rp.exists():
            raise RuntimeError(f"{worker} failed ({res.returncode}):\n{res.stderr[-3000:]}")
        return json.loads(rp.read_text(encoding="utf-8"))
