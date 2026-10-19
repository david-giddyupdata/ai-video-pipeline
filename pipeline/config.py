"""Project paths and machine settings. Secrets are read at run time, never stored in this repo.

Public copy: get_section() reads a JSON file outside the repo (AIDV_SECRETS_FILE, default ~/.aidv/secrets.json:
{"elevenlabs": {"api_key": ...}, "heygen": {"api_key": ...}, "obs": {"websocket_password": ...},
"youtube_oauth": {...}}). The author's own copy reads AWS Secrets Manager through a private helper instead
(AIDV_SECRETS_HELPER: the folder holding giddyup_secrets.py). Swap in your OS keyring or vault if you prefer.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
EXERCISES = ROOT / "exercises"
RUNS = ROOT / "runs"

CDP_URL = "http://127.0.0.1:9333"          # the workshop's Edge profile (start_browser.ps1); a step list's
                                           # `browser` switches it (pipeline.capture.browser.use)
GH_DIR = Path.home() / ".workshop" / "gh"     # the test account's gh sign-in (R58)

# The Edge profiles takes record in. The workshop's is started by its own automation\start_browser.ps1 (R1);
# the Quick Sight one by `python -m pipeline.capture.browser start quicksight` (R113). Both live outside OneDrive.
BROWSERS = {
    "workshop": {"cdp": 9333, "start_url": "https://github.com", "host": "github.com"},
    "quicksight": {"cdp": 9335, "dir": Path.home() / ".qs-video" / "edge-profile",
                   "start_url": "https://us-east-1.quicksight.aws.amazon.com/sn/start",
                   "host": "us-east-1.quicksight.aws.amazon.com",
                   # R112: the Open dialog shows a copy of the course download, never the OneDrive original
                   "data_src": Path(r"<DOCUMENTS_DIR>\Learning-David-Pc\QuickSight"
                                    r"\QuickSightCourse2027\QuickSight1\QuickSightJourney1\Data"),
                   "data_dir": Path.home() / "Downloads" / "QuickSightJourney1" / "Data"},
}
CAPTURE_MONITOR_X = 1920                  # right-hand monitor (DISPLAY1); no taskbar there
FRAME = (1920, 1080)

OBS_HOST, OBS_PORT = "localhost", 4455
OBS_PROFILE = "AIDV"                       # pipeline's own OBS profile and scene collection;
OBS_COLLECTION = "AIDV"                    # David's "Untitled" ones are restored after each take
OBS_SCENE = "AIDV Capture"
OBS_SOURCE = "AIDV Right Monitor"

_HELPER = os.environ.get("AIDV_SECRETS_HELPER")      # the author's private AWS Secrets Manager helper (optional)
_SECRETS_FILE = Path(os.environ.get("AIDV_SECRETS_FILE", Path.home() / ".aidv" / "secrets.json"))


def get_section(name):
    """One section of the secrets ({key: value}). Values are never written to files or printed."""
    if _HELPER:
        if _HELPER not in sys.path:
            sys.path.insert(0, _HELPER)
        from giddyup_secrets import get_section as _get
        return _get(name)
    if not _SECRETS_FILE.is_file():
        raise SystemExit(f"no secrets: set AIDV_SECRETS_FILE to a JSON file outside the repo (section {name!r} needed)")
    return json.loads(_SECRETS_FILE.read_text(encoding="utf-8"))[name]


def tool(name):
    """ffmpeg/ffprobe: PATH first, then winget's Links folder (a shell opened before the install lacks it)."""
    import shutil
    found = shutil.which(name)
    if found:
        return found
    winget = Path.home() / "AppData/Local/Microsoft/WinGet"
    for cand in [winget / "Links" / f"{name}.exe", *sorted(winget.glob(f"Packages/Gyan.FFmpeg*/*/bin/{name}.exe"))]:
        if cand.exists():
            return str(cand)
    raise FileNotFoundError(f"{name} not found; install with: winget install Gyan.FFmpeg")
