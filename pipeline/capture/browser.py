"""The Edge profiles takes record in (config.BROWSERS), and the launcher for the Quick Sight one (R113).

    python -m pipeline.capture.browser start quicksight   # stage the course data, then Edge on its own profile and port
    python -m pipeline.capture.browser status             # which profiles answer on their CDP ports

The workshop profile (port 9333) is started by the workshop's own automation\\start_browser.ps1 (R1); this module only
knows its port. Each start writes the workshop profile's recording settings into the Quick Sight profile (Edge
must be closed then): Copilot, Favorites and the sidebar buttons off (R16), no password, translation or autofill offers, and the file chooser
opening in the staged copy of the course's Data folder (R112). David signs it in to Quick Sight by hand, off camera
(R4, R110); it is never signed in to Microsoft (as R7).
"""
import json
import shutil
import subprocess
import sys
import urllib.request

from pipeline import config

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

SEED = {   # the workshop profile's toolbar settings (read 2026-10-14), plus R16's offers and the file chooser's folder
    "browser": {"show_discover_toolbar_button": False, "show_toolbar_bookmarks_button": False,
                "show_toolbar_edge_generic_sidebar_button": False, "show_downloads_hub_pinned": False,
                "show_toolbar_performance_center_button": 0},
    "bookmark_bar": {"show_on_all_tabs": False},
    "credentials_enable_service": False,
    "profile": {"password_manager_enabled": False},
    "translate": {"enabled": False},
    # Edge's "Saved info" suggestions: a name a rehearsal typed is previewed over the take's typing, frame by frame
    # (Section A, 00:14:17, David's note 13). Not checked live yet: Edge reads this at its next start
    "autofill": {"enabled": False, "profile_enabled": False, "credit_card_enabled": False},
}


def use(name):
    """Point the pipeline's CDP connection (pipeline.vendor.cs) at this profile. Call before anything connects."""
    config.CDP_URL = f"http://127.0.0.1:{config.BROWSERS[name]['cdp']}"
    return config.BROWSERS[name]


def answers(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
            return json.load(r).get("Browser")
    except OSError:
        return None


def stage_data(prof):
    """Copy the course download's Data folder (read-only source) to the folder the Open dialog shows. Existing files
    are left alone, so a copy that a take used never changes under it."""
    src, dst = prof["data_src"], prof["data_dir"]
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in sorted(src.iterdir()):
        if f.is_file() and not (dst / f.name).exists():
            shutil.copy2(f, dst / f.name)
            copied.append(f.name)
    return copied


def profile(prof):
    """(folder name, Microsoft account or '') of the profile Edge opens. Edge signs a new profile in to the Windows
    Microsoft account by itself; signing it out with "clear data" replaces Default with "Profile 1" (GOTCHAS)."""
    try:
        state = json.loads((prof["dir"] / "Local State").read_text(encoding="utf-8"))["profile"]
    except (OSError, KeyError, ValueError):
        return "Default", ""
    name = state.get("last_used") or "Default"
    return name, state.get("info_cache", {}).get(name, {}).get("user_name", "")


def in_use(prof):
    """Edge holds the profile's lockfile open while it runs, so it can't be opened for writing then."""
    lock = prof["dir"] / "lockfile"
    if not lock.exists():
        return False
    try:
        with open(lock, "a"):
            return False
    except PermissionError:
        return True


def merge(node, seed_doc):
    for k, v in seed_doc.items():
        if isinstance(v, dict) and isinstance(node.get(k), dict):
            merge(node[k], v)
        else:
            node[k] = v


def seed(prof, folder):
    """Write the recording settings into the profile's Preferences, keeping everything else. Only while Edge is
    closed: it rewrites the file on exit. Applied at every start, so a setting Edge changed comes back."""
    prefs = prof["dir"] / folder / "Preferences"
    prefs.parent.mkdir(parents=True, exist_ok=True)
    doc = json.loads(prefs.read_text(encoding="utf-8")) if prefs.exists() else {}
    merge(doc, {**SEED, "selectfile": {"last_directory": str(prof["data_dir"])}})
    prefs.write_text(json.dumps(doc), encoding="utf-8")


def start(name):
    prof = config.BROWSERS[name]
    if "dir" not in prof:
        raise SystemExit(f"{name}: started by its own launcher (the workshop's start_browser.ps1)")
    if answers(prof["cdp"]):
        print(f"{name}: already running on port {prof['cdp']}")
        return 0
    if in_use(prof):                               # Edge on this profile, but without the debugging port
        print(f"{name}: Edge already has {prof['dir']} open without port {prof['cdp']}. Close that Edge window, "
              "then start again. Not started.")
        return 1
    if prof.get("data_src"):
        print("staged:", stage_data(prof) or "nothing new", "->", prof["data_dir"])
    folder, account = profile(prof)
    if account:                                    # as R7: a recording profile is never signed in to Microsoft
        print(f"{name}: profile {folder} is signed in to Microsoft ({account}). Sign it out in edge://settings/"
              f"profiles with 'Clear favorites, history, passwords...' ticked, then start again. Not started.")
        return 1
    seed(prof, folder)
    subprocess.Popen([EDGE, f"--remote-debugging-port={prof['cdp']}", f"--user-data-dir={prof['dir']}",
                      f"--profile-directory={folder}", "--no-first-run", "--no-default-browser-check",
                      prof["start_url"]])
    print(f"{name}: Edge started on port {prof['cdp']} (profile {folder}, recording settings applied)")
    return 0


def status():
    for name, prof in config.BROWSERS.items():
        signed = ""
        if "dir" in prof:
            folder, account = profile(prof)
            signed = f"; profile {folder}, " + (f"SIGNED IN to Microsoft as {account}" if account else
                                                 "not signed in to Microsoft")
        print(f"{name:10} port {prof['cdp']}: {answers(prof['cdp']) or 'not running'}{signed}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["start"] and len(args) == 2:
        sys.exit(start(args[1]))
    if args[:1] == ["status"]:
        sys.exit(status())
    print(__doc__)
    sys.exit(2)
