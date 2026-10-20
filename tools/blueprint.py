"""The blueprint (R95; PLAN "Blueprint", steps 1 to 3): stage a clean public copy of the pipeline and scan it.

    python tools/blueprint.py                  # list, copy, git init, scan, write the review
    python tools/blueprint.py --scan-only      # rescan the staged copy as it stands (after hand edits); no copy
    python tools/blueprint.py --out=<dir> --terms=<file>

R95 lets the pipeline code go public for the CSC13 talk as a clean copy: never this repo's history, runs/,
audio_cache/ or the style study's frames, and only after a scan for secrets (R4), account IDs, and codespace and
test-account names. David approves the file list and the findings before anything is pushed (step 4), so this
script stops short of that:

  1. lists AIDrivenVideo's files (git's tracked and untracked ones, plus files git ignores outside the run and media
     folders), drops what never goes public, and proposes the rest by group: code, exercise data, docs (David picks:
     PICKS below), config and research;
  2. copies the proposed files to <out> (default: the drive's GitRepos/aidv-blueprint, wiped and rebuilt on each run)
     and runs `git init` there: no commit, no remote;
  3. scans the copy and writes <out>-review.md beside it: the file list with sizes, the docs proposal, the media and
     assets that need a decision, and every finding (file:line, the match, a category, a proposed placeholder).
     Nothing is replaced; the placeholders are proposals.

The scanner holds no private value, so it can go public with the rest. What it hunts for comes from this repo's own
data (codespace names from runs/ and SESSION_HANDOFF.md; the test account, voice and avatar ids from exercises/),
the user name from the home folder, and client names from a private file outside the repo (--terms: one term per
line, or a profile with a "## Key Clients" list; default David's Kiro profile). A match that looks like a real
secret shows only its first 4 characters.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(ROOT.anchor) / "GitRepos" / "aidv-blueprint"     # this machine keeps git repos in the drive's GitRepos
TERMS = Path.home() / ".kiro" / "steering" / "david-profile.md"
MARKER = "AIDV_BLUEPRINT"                                    # in <out>/.git: the only folder a re-run may wipe

MEDIA = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg",
         ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".psd", ".ai", ".prproj", ".aep"}
ASSET = MEDIA | {".ttf", ".otf", ".woff", ".woff2", ".mogrt"}
SOURCE = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".jsx", ".json", ".jsonl", ".md", ".xml", ".html", ".css",
          ".ps1", ".sh", ".toml", ".yml", ".yaml", ".txt", ".gitignore"}
BENIGN_NUMBERS = {"254016000000": "Premiere ticks per second"}

# Never public, whatever David picks. First match gives the reason.
NEVER = [
    (lambda p: p.startswith("runs/"), "run output: raw takes, logs and exports (R95)"),
    (lambda p: p.startswith("audio_cache/"), "the voiced narration cache (R95)"),
    (lambda p: p.startswith("recordings/"), "recordings"),
    (lambda p: "__pycache__/" in p or p.endswith(".pyc"), "Python bytecode"),
    (lambda p: p.startswith(("remotion/node_modules/", "remotion/out/", "remotion/build/", "remotion/dist/")),
     "npm packages or Remotion renders"),
    (lambda p: p.startswith("research/") and re.search(r"/(frames|sheets|work)/", p), "the style study's frames (R95)"),
    (lambda p: p in ("docs/claude_settings_local.json", ".claude/settings.local.json"), "machine permissions"),
    (lambda p: p == "SESSION_HANDOFF.md", "session state: dated, names live codespaces and takes"),
    (lambda p: p == "docs/TIMING.md", "the CSC13 test's work log (R98)"),
    (lambda p: p.startswith(("docs/readback_notes/", "docs/review_r2/")), "review and read-back notes for single takes"),
    (lambda p: p.endswith(".mogrt"), "Premiere templates (Adobe-made; carry David's look)"),
    (lambda p: p.startswith("exercises/qs1_section_a/"), "Quick Sight Journey 1 course material (R109)"),
    (lambda p: p.startswith("pipeline/vendor/quicksight/"), "Quick Sight code copied from the course folder (R109)"),
    (lambda p: PurePosixPath(p).suffix.lower() in MEDIA, "media (see the assets section)"),
]

# David's picks (R95: "the docs David picks"), for docs, config and research; code and exercise data go in whole.
# A path, or a folder ending in "/"; the longest match wins. Flip a value and re-run. Unlisted docs stay out.
PICKS = {
    "CLAUDE.md": (True, "the project's map and command list: the seed of the public README"),
    "RULES.md": (True, "the numbered decision log is the blueprint's core idea; needs the path, account and look-id fixes"),
    "SPEC.md": (True, "design and file formats; the code cites its sections (SPEC §n) throughout"),
    "GOTCHAS.md": (True, "how the tools misbehave: the most reusable doc for anyone rebuilding this"),
    "PLAN.md": (False, "internal status board with dates and take names; stale the day it is published"),
    "docs/SLICE_LOG.md": (False, "history of the test takes (take and codespace names, review notes); RULES distils it"),
    "docs/S7_FIX_PLAN.md": (False, "one take's fix plan; cites runs/ folders that are not published"),
    "docs/S7_R2_REVIEW.md": (False, "one review round's notes on David's Premiere project; cites runs/"),
    ".gitignore": (True, "keeps runs/, audio_cache/ and node_modules/ out; needs the media rules (see decisions)"),
    "skills-lock.json": (True, "names the official Remotion skills to install (R9); the skills themselves stay out"),
    ".claude/settings.json": (False, "Claude Code permissions with David's OneDrive and home paths"),
    ".claude/skills/": (False, "third-party copies of remotion-dev/skills; reinstall from skills-lock.json"),
    "research/": (False, "one-off analysis of David's Quick Series projects; reads local media and Premiere files"),
    "research/style_study/STYLE_PROFILE.md": (True, "David's measured editing style, the source of the pipeline's "
                                                    "numbers; CLAUDE.md cites it"),
    "research/style_study/NARRATION.md": (True, "how David writes narration (quotes his published videos); "
                                                "CLAUDE.md cites it"),
}
GROUPS = ["code", "exercise data", "docs", "config", "research"]


# --- 1. the file list --------------------------------------------------------------------------------------------

def git_files(*args):
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", *args], capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def never(p):
    return next((why for test, why in NEVER if test(p)), None)


def candidates():
    """{path: where git has it}: tracked, untracked, or ignored (found by a walk that skips the never-public folders)."""
    found = {p: "tracked" for p in git_files() if (ROOT / p).is_file()}
    found.update({p: "untracked" for p in git_files("--others", "--exclude-standard") if p not in found})
    for dirpath, dirs, files in os.walk(ROOT):
        rel = Path(dirpath).relative_to(ROOT).as_posix()
        rel = "" if rel == "." else rel + "/"
        # a folder whose every file is never public is not walked (runs/ alone is gigabytes)
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__") and not never(f"{rel}{d}/_")]
        for f in files:
            found.setdefault(rel + f, "ignored")
    return found


def group_of(p):
    top = p.split("/")[0]
    if top in ("pipeline", "remotion", "schemas", "tools"):
        return "code"
    if top == "exercises":
        return "exercise data"
    if top == "docs" or ("/" not in p and p.endswith(".md")):
        return "docs"
    return "research" if top == "research" else "config"


def pick_key(p):
    keys = [k for k in PICKS if p == k or (k.endswith("/") and p.startswith(k))]
    return max(keys, key=len) if keys else None


def propose(p, origin):
    """(group, include, reason, pick key). include is None when the file is never public."""
    g = group_of(p)
    why = never(p)
    if why:
        return g, None, why, None
    if origin == "ignored" and PurePosixPath(p).suffix.lower() not in SOURCE and not p.endswith(".gitignore"):
        return g, None, "git-ignored and not source", None
    k = pick_key(p)
    if k:
        return g, *PICKS[k], k
    if g in ("code", "exercise data"):
        return g, True, "", None
    return g, False, "not reviewed yet: out until David picks it", None


# --- 2. the staged copy --------------------------------------------------------------------------------------------

def has_commits(path):
    return subprocess.run(["git", "-C", str(path), "rev-parse", "--verify", "-q", "HEAD"],
                          capture_output=True).returncode == 0


def wipe(path):
    """Remove a previous staging folder, and only that (git marks its objects read-only on Windows)."""
    if ROOT.is_relative_to(path) or path.is_relative_to(ROOT):
        sys.exit(f"refusing: {path} overlaps this repo")
    if any(path.iterdir()) and not (path / ".git" / MARKER).is_file():
        sys.exit(f"refusing to wipe {path}: it was not made by this script")
    if has_commits(path):
        sys.exit(f"refusing to wipe {path}: it has commits now; move or delete it by hand")

    def writable(func, p, exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onexc=writable)


def stage(out, files):
    if out.exists():
        wipe(out)
    out.mkdir(parents=True)
    for p in files:
        (out / p).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / p, out / p)
    subprocess.run(["git", "init", "-q", "-b", "main", str(out)], check=True)
    (out / ".git" / MARKER).write_text("Staged by tools/blueprint.py; a re-run wipes this folder.\n", encoding="utf-8")


def staged_files(out):
    return sorted(f.relative_to(out).as_posix() for f in out.rglob("*") if f.is_file() and ".git" not in
                  f.relative_to(out).parts)


# --- 3. the scan ---------------------------------------------------------------------------------------------------

SLUG = re.compile(r"\b([a-z]+(?:-[a-z]+){1,3}-[a-z0-9]{4,20})(?:-\d{2,5})?(?:\.app)?\.github\.dev\b")


def walk_json(node, h):
    if isinstance(node, dict):
        if node.get("engine") == "elevenlabs" and isinstance(node.get("voice"), str) and len(node["voice"]) >= 10:
            h["voice"].add(node["voice"])
        hg = node.get("heygen")
        if isinstance(hg, dict):
            h["look"].update(str(hg[k]) for k in ("look", "look_id", "avatar_id") if hg.get(k))
            if hg.get("look_name"):
                h["look_name"].add(hg["look_name"])
        for v in node.values():
            walk_json(v, h)
    elif isinstance(node, list):
        for v in node:
            walk_json(v, h)


def harvest():
    """The private values to hunt for, read from this repo's own data (never written into this file)."""
    h = {k: set() for k in ("slug", "display", "owner", "repo", "repo_id", "voice", "look", "look_name")}
    files = [f for f in (ROOT / "runs").rglob("*") if f.suffix in (".json", ".jsonl", ".md", ".txt", ".log")]
    files += [ROOT / "SESSION_HANDOFF.md", *(ROOT / "exercises").rglob("*.json"), *(ROOT / "exercises").rglob("*.md")]
    for f in files:
        if not f.is_file() or f.stat().st_size > 64 << 20:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        h["slug"].update(SLUG.findall(text))
        h["slug"].update(re.findall(r'"codespace_name"\s*:\s*"([^"<]+)"', text))
        h["display"].update(re.findall(r'"codespace_display"\s*:\s*"([^"<]+)"', text))
        h["display"].update(re.findall(r'codespace\s+"([a-z]+(?: [a-z]+){1,2})"', text))
        for owner, repo in re.findall(r'"repo"\s*:\s*"([\w.-]+)/([\w.-]+)"', text):
            h["owner"].add(owner)
            h["repo"].add(re.sub(r"-take\d+$", "", repo))
        h["repo_id"].update(re.findall(r'"repo_id"\s*:\s*"?(\d{5,})', text))
        if f.suffix == ".json" and f.stat().st_size < 8 << 20:
            try:
                walk_json(json.loads(text), h)
            except ValueError:
                pass
    # only real names (the step lists also hold "@runtime" and the like)
    h["slug"] = {s for s in h["slug"] if re.fullmatch(r"[a-z]+(?:-[a-z]+){1,3}-[a-z0-9]{4,20}", s)}
    # GitHub shows a codespace by its words: adjective-noun-<random> is "adjective noun"
    h["display"].update(" ".join(s.split("-")[:-1]) for s in h["slug"] if re.search(r"\d", s.rsplit("-", 1)[-1]))
    h["display"] = {d for d in h["display"] if re.fullmatch(r"[a-z]+(?: [a-z]+){1,2}", d)}
    return h


def private_terms(path):
    """Client and contact names from a file outside the repo: a "## Key Clients" list, or one term per line."""
    if not path.is_file():
        return [], f"`{path}` not found: client names were not scanned"
    text = path.read_text(encoding="utf-8")
    sec = re.search(r"^## Key Clients\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not sec:
        terms = {t.strip() for t in text.splitlines() if t.strip() and not t.startswith("#")}
        return sorted(terms), f"{len(terms)} terms from the private terms file"
    terms = set()
    for line in re.findall(r"^- (.+)$", sec.group(1), re.M):
        parts = re.split(r"\s+[\u2014\u2013-]+\s+", line, maxsplit=1)
        client = re.sub(r"\s*\(.*?\)", "", parts[0]).strip()
        terms |= {client, re.sub(r"\s+(Corporation|Corp\.?|Inc\.?|LLC|Ltd\.?)$", "", client)}
        if len(client.split()) >= 3:
            terms.add(" ".join(client.split()[1:]))          # a three-word client also goes by its last two words
        if len(parts) > 1:
            for c in re.sub(r"^contacts?:\s*", "", parts[1]).split(","):
                terms.update(x.strip() for x in re.split(r"[()]", c) if x.strip())
    return sorted(terms), f"{len(terms)} client and contact names from the profile's Key Clients list"


def words_rx(values, flags=re.I):
    """One regex for a set of literal values, longest first, whole words only."""
    vals = sorted({v for v in values if v}, key=len, reverse=True)
    if not vals:
        return None
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(v).replace(r"\ ", r"[ \t-]+") for v in vals)
                      + r")(?![\w])", flags)


def path_place(text):
    """(category, placeholder) for an absolute path, by where it points."""
    p = re.sub(r"[\\/]+", "/", text).rstrip("/.: ")
    low = p.lower()
    root, videos = ROOT.as_posix().lower(), ROOT.parent.as_posix().lower()
    if low == root or low.startswith(root + "/"):
        return "local path: this repo", "./" + p[len(root):].lstrip("/")
    if low == videos or low.startswith(videos + "/"):
        return "local path: video workspace", "<VIDEOS_DIR>/" + p[len(videos):].lstrip("/")
    if "onedrive" in low:
        i = low.find("/documents/")
        return "local path: OneDrive", ("<DOCUMENTS_DIR>/" + p[i + 11:]) if i >= 0 else "<DOCUMENTS_DIR>"
    m = re.match(r"(?:[a-z]:|/[a-z])/users/[^/]+/?", low)
    if m:
        return "local path: home folder", "~/" + p[m.end():]
    if re.match(r"[a-z]:/(program files|windows)\b", low):
        return "machine path: system or app", "keep, as a setting (machine-specific)"
    return "local path: other", "<LOCAL_PATH>"


DRIVE = r"\b[A-Za-z]:(?:\\\\|\\|/)(?![ntr](?:\W|$))"     # not "as e:\n" in a code string
QUOTED_PATHS = [re.compile(q + r"(?P<v>" + DRIVE + r"[^" + q + r"\n]*)" + q) for q in ('"', "'", "`")]
PATH_RX = re.compile(r"(?:" + DRIVE + r"|(?<![\w.])/[a-z]/Users/)(?:[^\s\"'`<>|;,()\[\]{}*?]|[ ](?=[A-Z0-9-]))*")
SECRET_RULES = [
    ("secret: AWS access key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("secret: private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("secret: API key or token", r"\bsk-(?:ant-)?[A-Za-z0-9_-]{16,}|\bsk_[a-f0-9]{32,}|\bgh[pousr]_[A-Za-z0-9]{20,}"
                                 r"|\bgithub_pat_\w{20,}|\bGOCSPX-[\w-]{10,}|\bAIza[\w-]{35}|\bxox[abprs]-[\w-]{10,}"
                                 r"|\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}"),
    ("secret: bearer token", r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    ("secret: AWS secret key", r"(?i)aws_?secret\w*['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{30,}"),
    ("secret: key, token or password literal",
     r"(?i)\b[\w-]*(?:api[_-]?key|secret|token|passw(?:or)?d|pwd)[\w-]*['\"]?\s*[:=]\s*['\"]"
     r"(?!https?:|<|\{)[^'\"\s]{8,}['\"]"),
]


def rules(h, clients):
    """(category, regex, placeholder or fn(text) -> (category, placeholder) or None, path scope) in priority order:
    on one line, an earlier rule's match wins its characters."""
    r = [(cat, re.compile(rx), "<SECRET: read it through get_section(), R4>", None) for cat, rx in SECRET_RULES]
    acct = "AWS account ID"
    r += [
        (acct, re.compile(r"arn:aws[\w-]*:[\w-]*:[\w-]*:(?P<v>\d{12})"), "<AWS_ACCOUNT_ID>", None),
        (acct, re.compile(r"(?<![\w.])\d{12}(?!\w)|(?<![\w.-])\d{4}-\d{4}-\d{4}(?![\w-])"),
         lambda t: None if t in BENIGN_NUMBERS else (acct, "<AWS_ACCOUNT_ID>"), None),
        ("codespace name", words_rx(h["slug"]), "<CODESPACE_NAME>", None),
        ("codespace name", SLUG, "<CODESPACE_NAME>.github.dev", None),
        ("codespace name", words_rx(h["display"]), "<CODESPACE_DISPLAY_NAME>", None),
        ("codespace name", re.compile(r'"codespace_name"\s*:\s*"(?P<v>[^"<@][^"]*)"'), "<CODESPACE_NAME>", None),
        ("codespace name", re.compile(r'"codespace_display"\s*:\s*"(?P<v>[^"<@][^"]*)"'), "<CODESPACE_DISPLAY_NAME>",
         None),
        ("test account: GitHub account", words_rx(h["owner"]), "<YOUR_GITHUB_ACCOUNT>", None),
        ("test account: repo name", re.compile(r"(?<![\w-])(?:" + "|".join(map(re.escape, sorted(h["repo"])))
                                               + r")(?:-take\d+)?(?![\w-])") if h["repo"] else None,
         "<YOUR_REPO>", None),
        ("test account: repo id", re.compile(r"(?<!\d)(?:" + "|".join(sorted(h["repo_id"])) + r")(?!\d)")
         if h["repo_id"] else None, "<GITHUB_REPO_ID>", None),
        ("likeness: ElevenLabs voice id", words_rx(h["voice"], 0), "<ELEVENLABS_VOICE_ID>", None),
        ("likeness: HeyGen look id", words_rx(h["look"], 0), "<HEYGEN_LOOK_ID>", None),
        ("likeness: HeyGen look name", words_rx(h["look_name"]), "<HEYGEN_LOOK_NAME>", None),
        ("client name", words_rx(clients), "<CLIENT>", None),
        *[("local path", rx, path_place, None) for rx in QUOTED_PATHS],     # a quoted path runs to its quote
        ("local path", PATH_RX, path_place, None),
        ("local path: OneDrive", re.compile(r"OneDrive - [\w.-]+"), "<DOCUMENTS_DIR>", None),
        ("personal: email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<EMAIL>", None),
        ("personal: phone", re.compile(r"(?<![\w.])(?:\+1[ .-]?)?\(?[2-9]\d{2}\)?[ .-]\d{3}[ .-]\d{4}(?![\w])"),
         "<PHONE>", None),
        ("personal: user name", words_rx([Path.home().name]), "<USER>", None),
        ("AWS resource name", re.compile(r"s3://(?:\(\?!)?(?P<v>[a-z0-9][a-z0-9.-]{2,62})"), "<S3_BUCKET>", None),
        ("secret store name", re.compile(r"giddyup[/]config"), "keep (a name, not a secret), or <SECRET_STORE>", None),
        ("em dash (R93)", re.compile("\u2014|\\s\u2013\\s|\\w -- \\w"), "a comma, colon, period or parentheses",
         ("exercises/", "remotion/src/")),
    ]
    return [x for x in r if x[1] is not None]


def scan(out, files, rs):
    """Every finding in the staged copy: {file, line, category, text, place, start}."""
    found = []
    for rel in files:
        raw = (out / rel).read_bytes()
        if b"\0" in raw[:8192]:
            continue                                          # binary
        for n, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
            hits = []
            for pri, (cat, rx, place, scope) in enumerate(rs):
                if scope and not rel.startswith(scope):
                    continue
                for m in rx.finditer(line):
                    g = "v" if "v" in rx.groupindex and m.group("v") else 0
                    s, e = m.span(g)
                    text = line[s:e].rstrip(" .:")
                    got = place(text) if callable(place) else (cat, place)
                    if got and text:
                        hits.append((pri, s, s + len(text), got[0], got[1], text))
            kept = []
            for pri, s, e, cat, place, text in sorted(hits):
                if any(s < ke and ks < e for ks, ke in kept):
                    continue
                kept.append((s, e))
                ctx = line[max(0, s - 25):e + 25] if cat.startswith("em dash") else text
                found.append({"file": rel, "line": n, "category": cat, "text": ctx, "place": place, "start": s})
    return sorted(found, key=lambda f: (f["category"], f["file"], f["line"], f["start"]))


# --- the review ----------------------------------------------------------------------------------------------------

SEVERITY = [("secret:", "high"), ("AWS account", "high"), ("codespace", "high"), ("test account", "high"),
            ("client", "high"), ("personal: email", "high"), ("personal: phone", "high"), ("local path", "medium"),
            ("personal: user", "medium"), ("likeness", "medium (flag)"), ("AWS resource", "medium"),
            ("machine path", "low"), ("secret store", "info"), ("em dash", "low")]


def severity(cat):
    return next((s for p, s in SEVERITY if cat.startswith(p)), "medium")


def shown(f):
    t = f["text"]
    if f["category"].startswith("secret:"):
        t = f"{t[:4]}**** ({len(t)} chars)"
    t = t.replace("\u2014", "[em dash]").replace("\u2013", "[en dash]").replace("`", "'").replace("|", "\\|")
    return t if len(t) <= 110 else t[:107] + "..."


def kb(n):
    return f"{n / 1024:,.1f}"


def external_assets(finds):
    """{absolute path: [file:line]} for the media, fonts and templates the copy points at outside itself."""
    ext = {}
    for f in finds:
        p = re.sub(r"[\\/]+", "/", f["text"])
        if f["category"].startswith(("local path", "machine path")) and PurePosixPath(p).suffix.lower() in ASSET:
            ext.setdefault(p, []).append(f"{f['file']}:{f['line']}")
    return ext


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    return out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]


def review(out, report, cands, props, files, finds, notes, sanity):
    size = {p: (out / p).stat().st_size for p in files}
    total = sum(size.values())
    by_group = {g: [p for p in files if group_of(p) == g] for g in GROUPS}
    cats = {}
    for f in finds:
        cats.setdefault(f["category"], []).append(f)
    L = [f"# AIDV blueprint review (R95)", "",
         f"Generated {datetime.now():%Y-%m-%d %H:%M} by `tools/blueprint.py` from `{ROOT}` (the working tree, so files "
         "being edited are copied as they stood). Staged copy: "
         f"`{out}` (`git init`, no commit, no remote; nothing pushed). Re-run: `python tools/blueprint.py` (wipes and "
         "rebuilds the copy) or `--scan-only` (rescans the copy as it stands). Nothing has been replaced: every "
         "placeholder below is a proposal for David.", "",
         f"**Totals:** {len(files)} files, {total / 1048576:.2f} MB staged; {len(finds)} findings in "
         f"{len({f['file'] for f in finds})} files. Sanity: {sanity}", "", "## 1. The file list, by group", ""]
    L += table(["Group", "Files staged", "KB", "Proposed out (reason in section 2 or 3)"],
               [[g, len(by_group[g]), kb(sum(size[p] for p in by_group[g])),
                 sum(1 for p, (gg, inc, *_ ) in props.items() if gg == g and inc is False)] for g in GROUPS]
               + [["**total**", len(files), kb(total), sum(1 for v in props.values() if v[1] is False)]])
    for g in GROUPS:
        if by_group[g]:
            L += ["", f"### {g} ({len(by_group[g])} files)", ""]
            L += table(["File", "KB", "Git"], [[f"`{p}`", kb(size[p]), cands.get(p, "?")] for p in by_group[g]])

    L += ["", "## 2. Docs, config and research: the proposal (David picks; flip a value in `PICKS` and re-run)", ""]
    rows, seen = [], set()
    for p, (g, inc, why, key) in sorted(props.items()):
        if g not in ("docs", "config", "research"):
            continue
        if key and key.endswith("/"):
            if key in seen:
                continue
            seen.add(key)
            n = [q for q, v in props.items() if v[3] == key]
            rows.append([f"`{key}` ({len(n)} files)", "include" if inc else "out",
                         kb(sum((ROOT / q).stat().st_size for q in n)), why])
        else:
            rows.append([f"`{p}`", {True: "include", False: "out", None: "never"}[inc], kb((ROOT / p).stat().st_size),
                         why])
    L += table(["File", "Proposal", "KB", "Reason"], rows)
    if notes["dangling"]:
        L += ["", "Included docs that cite files left out (reword or drop the reference):", ""]
        L += [f"- `{a}` cites {', '.join(f'`{b}` ({n}x)' for b, n in sorted(refs.items()))}"
              for a, refs in sorted(notes["dangling"].items())]

    L += ["", "## 3. Always left out", ""]
    out_rows = {}
    for p, (g, inc, why, key) in props.items():
        if inc is None:
            n, b = out_rows.get(why, (0, 0))
            out_rows[why] = (n + 1, b + (ROOT / p).stat().st_size)
    L += table(["Reason", "Files", "KB"], [[w, n, kb(b)] for w, (n, b) in sorted(out_rows.items())])
    L += ["", "Folders git ignores (`runs/`, `audio_cache/`, `remotion/node_modules/`, the style study's frames and "
          "sheets) are never walked, so their files are not counted here."]

    L += ["", "## 4. Media and assets needing a decision", "", "**Media and templates in the repo** (none is staged):", ""]
    media = [p for p in props if PurePosixPath(p).suffix.lower() in ASSET]
    L += table(["File", "KB", "Why out"], [[f"`{p}`", kb((ROOT / p).stat().st_size), props[p][2]] for p in media]) \
        if media else ["None outside the never-walked folders."]
    L += ["", "**Assets inside the code** (staged; the code reads them):", ""]
    inner = [p for p in files if "/assets/" in f"/{p}"]
    L += [f"- `{p}` ({kb(size[p])} KB)" for p in inner] or ["- none"]
    L += ["", "**Assets outside the repo the code or exercise data points at** (absolute paths; none can ship as is):",
          ""]
    rows = []
    for p, where in sorted(external_assets(finds).items()):
        fp = Path(p)
        rows.append([f"`{p}`", f"{fp.stat().st_size / 1048576:.1f} MB" if fp.is_file() else "not found",
                     ", ".join(where[:3]) + (f" (+{len(where) - 3})" if len(where) > 3 else "")])
    L += table(["Asset", "Size here", "Cited at"], rows) if rows else ["None found."]

    L += ["", "## 5. Provenance: `pipeline/vendor/` (R1)", "",
          "Copied from the read-only <CLIENT> workshop folder, with provenance headers. Publishing it is a licence and "
          "ownership question for David (see decisions). The headers say:", ""]
    for p in [p for p in files if p.startswith("pipeline/vendor/") and p.endswith(".py")]:
        doc = re.match(r'\s*"""(.*?)"""', (out / p).read_text(encoding="utf-8"), re.S)
        head = [x.strip() for x in (doc.group(1) if doc else "").splitlines() if x.strip()][:3]
        L += [f"- `{p}`: " + (" / ".join(shown({"text": x, "category": ""}) for x in head) or "no docstring")]

    L += ["", "## 6. Scan findings", "",
          f"Hunted for: {notes['hunted']}. Client names: {notes['terms']}. Secret-like matches show their first 4 "
          "characters only.", ""]
    for cat in sorted(cats, key=lambda c: ([s for _, s in SEVERITY].index(severity(c)), c)):
        fs = cats[cat]
        L += [f"### {cat} ({len(fs)}; {severity(cat)})", ""]
        L += table(["File:line", "Match", "Proposed placeholder"],
                   [[f"`{f['file']}:{f['line']}`", f"`{shown(f)}`", f"`{f['place']}`"] for f in fs])
        L += [""]

    L += ["## 7. Summary", ""]
    L += table(["Category", "Severity", "Findings", "Files"],
               [[c, severity(c), len(fs), len({f['file'] for f in fs})] for c, fs in
                sorted(cats.items(), key=lambda kv: ([s for _, s in SEVERITY].index(severity(kv[0])), kv[0]))]
               + [["**total**", "", len(finds), len({f['file'] for f in finds})]])
    L += ["", "No secret values were found." if not any(c.startswith("secret:") for c in cats)
          else "**Secret-like values were found: see section 6 before anything else.**", "",
          "### Decisions for David", ""]
    L += [f"{i}. {d}" for i, d in enumerate(notes["decisions"], 1)]
    report.write_text("\n".join(L) + "\n", encoding="utf-8")


def decisions(props, files, finds, out):
    cnt = lambda pre: sum(1 for f in finds if f["category"].startswith(pre))
    files_of = lambda pre: sorted({f["file"] for f in finds if f["category"].startswith(pre)})
    inc_docs = [p for p, v in props.items() if v[0] == "docs" and v[1]]
    out_docs = [p for p, v in props.items() if v[0] == "docs" and v[1] is False]
    research = [p for p, v in props.items() if v[0] == "research" and v[1]]
    d = [f"**The file list:** approve the {len(files)} staged files (section 1), or name what to add or drop.",
         f"**Docs:** in: {', '.join(inc_docs)}; out: {', '.join(out_docs)}. From research/, in: "
         f"{', '.join(research) or 'nothing'} (section 2 has the reasons).",
         "**pipeline/vendor/** was copied from workshop material (R1). If your workshop material belongs to a "
         "client or was made under contract, check before it goes public: keep it (with its headers), rewrite it, "
         "or drop it (s1, runner, prepare, preflight and explore import it, so dropping breaks capture). The same "
         "question covers exercises/ if its narration and step lists follow a client's exercise doc."]
    cfg = out / "pipeline" / "config.py"
    cfg_text = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
    if "giddyup_secrets" in cfg_text and "AIDV_SECRETS_FILE" not in cfg_text:
        d.append("**Secrets for a public user:** `pipeline/config.py` loads keys through a private helper "
                 "(`giddyup_secrets`) from a OneDrive folder, so a placeholder path alone leaves the keyed steps "
                 "(OBS, ElevenLabs, HeyGen, YouTube) unrunnable. Propose: fall back to environment variables when the "
                 "helper is absent, and say so in the README.")
    named = files_of("codespace") + files_of("test account")
    if named:
        ex = len({f for f in named if f.startswith("exercises/")})
        d.append(f"**Codespace and test-account names:** {cnt('codespace')} codespace and {cnt('test account')} "
                 f"test-account findings in {len(set(named))} files ({ex} of them exercise data). Some are narration "
                 "(\"This one is called ...\"), so a placeholder changes the line's text. They were on screen in the "
                 "video, but R95 asks for them to be scanned out and a codespace may still exist: the default is "
                 "placeholders.")
    if cnt("likeness"):
        d.append(f"**Likeness ids** ({cnt('likeness')}): the ElevenLabs voice id and the HeyGen look id and name "
                 "are not secrets (they need David's API keys), but they point at his voice clone and avatar. Keep "
                 "or placeholder?")
    ext = external_assets(finds)
    if cnt("local path") or cnt("machine path"):
        d.append(f"**Local paths** ({cnt('local path')} local, {cnt('machine path')} machine). {len(ext)} point at "
                 f"assets outside the repo ({', '.join(sorted({PurePosixPath(p).name for p in ext}))}): none can "
                 "ship as is (brand, music licence, Adobe's and Microsoft's files), so each becomes a setting with a "
                 "placeholder (section 4). The rest are the R1 workshop folder, the secrets helper and doc mentions.")
    gitignore = out / ".gitignore"
    if not (gitignore.is_file() and "*.mp4" in gitignore.read_text(encoding="utf-8")):
        d.append("**.gitignore:** the copy has only AIDrivenVideo's own .gitignore. The media rules (*.mp4, "
                 "*.wav, *.png, *.prproj, *.mogrt) came from the parent repo (the video workspace) and are "
                 "missing, and its `!remotion/*.ts` lines only exist because the parent ignores *.ts. Add the "
                 "media rules before the first commit.")
    if not ((out / "LICENSE").is_file() and (out / "README.md").is_file()):
        d.append("**LICENSE and README:** the copy lacks one or both. Pick a licence; the README can start from "
                 "CLAUDE.md. Remotion has its own licence (free for individuals and very small companies; larger "
                 "companies need a company licence): worth a line in the README.")
    old = [p for p in files if re.match(r"exercises/.*/steps_(s\d|p5_take\d+)\.json$", p)]
    if old:
        d.append(f"**Old step lists:** {len(old)} test-slice step lists ({', '.join(PurePosixPath(p).name for p in old)}) "
                 "are history; keep them as examples or ship only steps_full*.json and steps_csc13.json.")
    if cnt("em dash"):
        d.append(f"**R93:** {cnt('em dash')} em or en dashes in viewer-facing files (low priority).")
    return d


def dangling(out, files, props):
    """Included markdown that names a doc or folder left out of the copy."""
    gone = sorted({PurePosixPath(p).name for p, v in props.items()
                   if v[0] == "docs" and not v[1] and p.count("/") <= 1 and p.endswith(".md")}
                  | {"readback_notes/", "review_r2/"})
    res = {}
    for p in files:
        if p.endswith(".md"):
            text = (out / p).read_text(encoding="utf-8", errors="replace")
            refs = {g: len(re.findall(r"(?<![\w/])" + re.escape(g), text)) for g in gone}
            refs = {g: n for g, n in refs.items() if n}
            if refs:
                res[p] = refs
    return res


def check(out, files, expected):
    bad = [p for p in files if re.match(r"(runs|audio_cache|recordings)/|.*(node_modules|__pycache__)/", p)
           or re.search(r"/(frames|sheets|work)/", p) or PurePosixPath(p).suffix.lower() in ASSET]
    problems = []
    if bad:
        problems.append(f"{len(bad)} never-public files staged: {bad[:5]}")
    if expected is not None and len(files) != len(expected):
        problems.append(f"staged {len(files)} files, expected {len(expected)}")
    if not (out / ".git").is_dir():
        problems.append("no .git in the copy")
    if has_commits(out):
        problems.append("the copy has commits")
    remotes = subprocess.run(["git", "-C", str(out), "remote"], capture_output=True, text=True).stdout.strip()
    if remotes:
        problems.append(f"the copy has remotes: {remotes}")
    return "passed (no runs/, audio_cache/, node_modules/, bytecode, frames or media in the copy; git initialised " \
           "with no commit and no remote)" if not problems else "**FAILED:** " + "; ".join(problems)


def main(argv):
    opts = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in argv if a.startswith("--"))
    out = Path(opts.get("out", OUT)).resolve()
    report = out.with_name(out.name + "-review.md")
    cands = candidates()
    props = {p: propose(p, o) for p, o in sorted(cands.items())}
    chosen = [p for p, v in props.items() if v[1]]
    if "scan-only" in opts:
        if not (out / ".git" / MARKER).is_file():
            sys.exit(f"no staged copy at {out}; run without --scan-only first")
        expected = None
    else:
        stage(out, chosen)
        expected = chosen
    files = staged_files(out)
    h = harvest()
    clients, terms_note = private_terms(Path(opts.get("terms", TERMS)))
    finds = scan(out, files, rules(h, clients))
    notes = {"terms": terms_note, "dangling": dangling(out, files, props),
             "hunted": f"{len(h['slug'])} codespace names and {len(h['display'])} display forms (from runs/, "
                       f"SESSION_HANDOFF.md and exercises/), {len(h['owner'])} test account, {len(h['repo'])} repo "
                       f"name, {len(h['repo_id'])} repo id, {len(h['voice'])} voice id, {len(h['look'])} look id, "
                       "the home folder's user name, plus generic patterns for secrets, account IDs, emails, "
                       "phones and paths",
             "decisions": decisions(props, files, finds, out)}
    sanity = check(out, files, expected)
    review(out, report, cands, props, files, finds, notes, sanity)
    total = sum((out / p).stat().st_size for p in files)
    print(f"staged {len(files)} files ({total / 1048576:.2f} MB) in {out}")
    print(f"{len(finds)} findings in {len({f['file'] for f in finds})} files; sanity: {sanity.split(' (')[0]}")
    print(f"review: {report}")
    return 0 if not sanity.startswith("**FAILED") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
