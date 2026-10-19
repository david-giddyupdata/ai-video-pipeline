"""Compare two build folders' JSON and XML outputs, paths and key order normalised (GAPS_PLAN_one_shot.md, G2).

    python tools/compare_builds.py <before> <after> [--also <before2> <after2>]... [--allow=<file>]...
                                   [--save-allow=<file>]

Every .json and .xml under both folders is compared (Premiere's own Motion Graphics Template Media/ and titles_check/
aside, as regress_csc13 does). Normalised first, with regress_csc13's normaliser: <after>'s absolute path stands for
<before>'s in plain, JSON-escaped, forward-slash and file:// URL forms (either case of drive letter; the two folders
may be on different drives, the URL's D%3a included), and so does each
--also pair's (a folder the build read from, e.g. the stage's --clips=<before>/clips: --also <before> <after>); the
longest paths are replaced first; JSON is compared with its keys sorted. Nothing else: the builds write no timestamps.

Expected differences, the allow-list (G2's own expected one is built in; --allow files add to it):
    {"moved": ["clips/checks_final.json", "checks_final.json"], "why": "..."}
        when <after> has the file at its new place and <before> hasn't, <before>'s file is compared with it there
        (item 2b: run_checks writes into the final's own folder, not clips/), and neither place counts as a file
        missing on one side; a change in its content is still a difference
    {"file": "<path or glob>", "why": "..."}       any difference in that file, or its presence, is expected
    {"file": ..., "old": [...], "new": [...], "why": "..."}   that one difference exactly, as --save-allow writes them

--save-allow writes every difference found in that last form, keeping the why of any rule that allowed it, to explain
and pass back as --allow. Exit 0 when every difference is allowed, 1 when one isn't, 2 on a bad argument.
"""
import argparse
import difflib
import fnmatch
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import regress_csc13 as RC  # noqa: E402  (forms: the ways a folder's path appears; key: a difference's identity)

G2_ALLOW = [{"moved": ["clips/checks_final.json", "checks_final.json"],
             "why": "GAPS_PLAN 2b: run_checks writes checks_final.json into the final's own folder, not clips/"}]
BIG = 4000                       # lines left once the common ends are trimmed: above it, difflib's junk heuristic


def forms(p):
    """{kind: text}, the ways a folder's absolute path appears: regress_csc13's four (JSON-escaped, plain, forward
    slashes, and the file:// URL's part after the drive), each with either case of drive letter, and the URL's part
    with its drive (D%3a/...), so a build on another drive (G:\\aidv_scratch) is normalised too (Fable, A3)."""
    out = dict(zip(("escaped", "plain", "fwd", "url"), RC.forms(p)))
    fwd = out["fwd"]
    if fwd[1:2] == ":":
        for case in (str.upper, str.lower):
            for k in ("escaped", "plain", "fwd"):
                out[f"{k} {case.__name__}"] = case(out[k][0]) + out[k][1:]
            for colon in ("%3a", "%3A"):
                out[f"url {case.__name__} {colon}"] = case(fwd[0]) + colon + out["url"]
    return out


def normaliser(pairs):
    """pairs: (before, after) folders. Returns norm(text), after's paths written as before's. Forms pair up by kind,
    so a path with no drive letter (UNC) pairs only the forms both have."""
    subs = set()
    for before, after in pairs:
        fb, fa = forms(before), forms(after)
        subs |= {(fa[k], fb[k]) for k in fa.keys() & fb.keys() if fa[k] != fb[k]}
    subs = sorted(subs, key=lambda s: (-len(s[0]), s))   # a folder inside another first; a drive's URL form
                                                         # before the driveless one

    def norm(text):
        for a, b in subs:
            text = text.replace(a, b)
        return text
    return norm


def lines_of(path, norm=None):
    text = path.read_text(encoding="utf-8-sig")
    text = norm(text) if norm else text
    if path.suffix == ".json":
        try:
            text = json.dumps(json.loads(text), indent=1, sort_keys=True, ensure_ascii=False)
        except ValueError:
            pass                                         # not JSON after all: compared as text
    return text.splitlines()


def compared(folder):
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*")
            if p.suffix in (".xml", ".json") and p.is_file()
            and not any(part in RC.PREMIERE_OWN for part in p.relative_to(folder).parts)}


def changes(a, b):
    """difflib's non-equal opcodes, the common head and tail trimmed first: box_frames.json is ~10^5 lines, and
    difflib without its junk heuristic is quadratic on repeated lines."""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    j = 0
    while j < n - i and a[-1 - j] == b[-1 - j]:
        j += 1
    ma, mb = a[i:len(a) - j], b[i:len(b) - j]
    if not ma and not mb:
        return []
    sm = difflib.SequenceMatcher(None, ma, mb, autojunk=len(ma) + len(mb) > BIG)
    return [(t, i1 + i, i2 + i, j1 + i, j2 + i) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]


def diff_files(path_a, path_b, norm, label):
    a, b = lines_of(path_a), lines_of(path_b, norm)
    return [{"file": label, "at": i1 + 1, "old": a[i1:i2], "new": b[j1:j2],
             "context": a[i1 - 1].strip() if i1 else ""} for _, i1, i2, j1, j2 in changes(a, b)]


def moves_seen(moved, old_files, new_files):
    return [(s, d) for s, d in moved if s in old_files and d in new_files and d not in old_files]


def diff(before, after, norm, moved=(), old_files=None, new_files=None):
    """[{file, at, old, new}] for every difference, at = the line in before's file."""
    old_files = compared(before) if old_files is None else old_files
    new_files = compared(after) if new_files is None else new_files
    out, done_a, done_b = [], set(), set()
    for src, dst in moves_seen(moved, old_files, new_files):
        out += diff_files(before / src, after / dst, norm, f"{src} -> {dst}")
        done_b.add(dst)
        if src not in new_files:
            done_a.add(src)
    for rel in sorted((old_files - done_a) | (new_files - done_b)):
        if rel not in new_files or rel not in old_files:
            out.append({"file": rel, "at": 0, "old": ["(file present)"] if rel in old_files else [],
                        "new": ["(file present)"] if rel in new_files else []})
        else:
            out += diff_files(before / rel, after / rel, norm, rel)
    return out


def exact(r):
    return RC.key({"file": r.get("file"), "old": r.get("old", []), "new": r.get("new", [])})


def rule_for(d, rules):
    """The first rule that allows difference d, or None. A moved rule allows no difference: it only pairs files."""
    for r in rules:
        if "old" in r or "new" in r:
            if exact(r) == RC.key(d):
                return r
        elif "file" in r and fnmatch.fnmatchcase(d["file"], r["file"]):
            return r
    return None


def show(d):
    print(f"--- DIFF {d['file']}, before's line {d['at']}" + (f", after: {d['context'][:100]}" if d.get("context")
                                                              else ""))
    if len(d["old"]) == len(d["new"]) == 1:              # one changed line: show where it changes
        a, b = d["old"][0].strip(), d["new"][0].strip()
        i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        lo = max(0, i - 60)
        for sign, s in (("-", a), ("+", b)):
            print(f"  {sign} {'...' * bool(lo)}{s[lo:lo + 200]}{'...' * (len(s) > lo + 200)}")
        return
    for sign, ls in (("-", d["old"]), ("+", d["new"])):
        for ln in ls[:RC.MAX_SHOWN]:
            print(f"  {sign} {ln.strip()[:160]}")
        if len(ls) > RC.MAX_SHOWN:
            print(f"  {sign} ... {len(ls) - RC.MAX_SHOWN} more line(s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--also", nargs=2, action="append", default=[], metavar=("BEFORE", "AFTER"),
                    help="another pair of folders whose paths stand for each other")
    ap.add_argument("--allow", action="append", default=[], help="expected differences (see the docstring)")
    ap.add_argument("--save-allow", help="write this run's differences here, to explain and pass as --allow")
    a = ap.parse_args(argv)
    before, after = Path(a.before).resolve(), Path(a.after).resolve()
    for p in (before, after):
        if not p.is_dir():
            ap.error(f"no folder {p}")
    extra = []
    for f in a.allow:
        try:
            extra += json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            ap.error(f"--allow {f}: {e}")
    rules = G2_ALLOW + extra
    moved = [tuple(r["moved"]) for r in rules if "moved" in r]
    norm = normaliser([(before, after)] + [(Path(x).resolve(), Path(y).resolve()) for x, y in a.also])
    old_files, new_files = compared(before), compared(after)
    diffs = diff(before, after, norm, moved, old_files, new_files)
    allowed = [(d, rule_for(d, rules)) for d in diffs]
    new = [d for d, r in allowed if r is None]
    seen = [(d, r) for d, r in allowed if r is not None]
    moves = moves_seen(moved, old_files, new_files)
    print(f"compared {len(old_files | new_files)} file(s), {after} against {before}: {len(diffs)} difference(s), "
          f"{len(seen)} allowed, {len(new)} not explained")
    for r in extra:                                      # an --allow rule that matched nothing: worth knowing
        hit = tuple(r["moved"]) in moves if "moved" in r else any(x is r for _, x in seen)
        if not hit:
            print(f"--- allowed, not seen: {r.get('file') or r.get('moved')}: {r.get('why') or ''}")
    for src, dst in moves:
        print(f"--- moved as expected: {src} -> {dst}")
    for d, r in seen:
        print(f"--- allowed {d['file']}, before's line {d['at']}: {r.get('why') or '(no why given)'}")
    for d in new:
        show(d)
    if a.save_allow:
        Path(a.save_allow).write_text(json.dumps([{**d, "why": (r or {}).get("why", "")} for d, r in allowed],
                                                 indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {len(diffs)} difference(s) to {a.save_allow}")
    return 1 if new else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
