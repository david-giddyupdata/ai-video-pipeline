"""CSC13 regression check: re-plan and re-export a scratch copy of the CSC13 test run, and diff it against round 4.

    python tools/regress_csc13.py --tag=<tag> [--known=<file>] [--save-known=<file>] [--setup-only]

1. Copies runs/csc13_test_20261012 to runs/_scratch_csc13_<tag>/csc13_test_20261012. The copy keeps the run folder's
   own name, so the plan's run_id, the sequence names and their uuids come out as in the original. raw.mp4 is
   hard-linked (it is only ever read); the export rounds (premiere*/) and the line check's images are left out;
   everything else is copied, so nothing in the original is written. An existing scratch folder of that tag is
   replaced.
2. Re-plans it: python -m pipeline.edit.plan <copy> exercises/build_an_interactive_dashboard/steps_csc13.json
   (round 4's plan: the CSC13 steps file, default gap treatment).
3. Exports it: python -m pipeline.edit.premiere <copy> --no-render --out=<copy>/premiere_check
   The line check is not re-run (it OCRs): round 4's report is copied and marked newer than the new plan, so the
   export copies it, as round 4's export did.
4. Diffs every .xml and .json the export wrote (edit_plan.json included: the export's copy of the new plan) against
   runs/csc13_test_20261012/premiere_r3/ (round 4, and the plan snapshot it was made from).

Normalised before the diff: absolute paths (the copy's folder and premiere_check stand for the original's folder and
premiere_r3, in plain, JSON-escaped, forward-slash and file:// URL forms), and JSON key order. Nothing else: the
outputs carry no timestamps, and the sequence uuids derive from the names. Premiere's own files in premiere_r3
(Motion Graphics Template Media/, titles_check/, the .prproj) are not compared; the .mogrt titles and PNG/MOV media
are not compared either (binary).

Exit 0 when there is no difference, or every one is listed in --known (a file --save-known wrote from an earlier
run, e.g. one made before a code change, with a "why" to fill in); else 1. --setup-only makes the copy and stops,
for tests that add their own inputs (a privacy report, say) before planning: then run with --reuse to plan, export
and diff that copy without copying again.
"""
import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs" / "csc13_test_20261012"
ROUND = RUN / "premiere_r3"
STEPS = ROOT / "exercises" / "build_an_interactive_dashboard" / "steps_csc13.json"
PREMIERE_OWN = ("Motion Graphics Template Media", "titles_check")      # Premiere wrote these, not the export
SKIP_TOP = ("linecheck",)                                              # its images aren't inputs; report.md is
MAX_SHOWN = 14                                                         # lines shown per difference


def scratch_dir(tag):
    if not tag or any(c in tag for c in r"\/:*?\"<>| ."):
        raise SystemExit(f"bad --tag {tag!r}: letters, digits, - and _ only")
    return ROOT / "runs" / f"_scratch_csc13_{tag}"


def make_copy(tag):
    """runs/_scratch_csc13_<tag>/csc13_test_20261012, a copy of the run without its export rounds."""
    base = scratch_dir(tag)
    assert base.parent == ROOT / "runs" and base.name.startswith("_scratch_csc13_")
    if base.exists():
        shutil.rmtree(base)
    copy = base / RUN.name
    copy.mkdir(parents=True)
    for p in RUN.iterdir():
        if p.name.startswith("premiere") or p.name in SKIP_TOP:
            continue
        dst = copy / p.name
        if p.name == "raw.mp4":
            try:
                os.link(p, dst)                          # read only, by the planner (holds) and the export
            except OSError:
                shutil.copy2(p, dst)
        elif p.is_dir():
            shutil.copytree(p, dst)
        else:
            shutil.copy2(p, dst)
    return copy


def run(cmd, log):
    t = time.time()
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log.write_text(r.stdout + "\n--- stderr ---\n" + r.stderr, encoding="utf-8")
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        raise SystemExit(f"failed ({r.returncode}): {' '.join(map(str, cmd))}; log {log}")
    return time.time() - t


def plan_and_export(copy):
    t_plan = run([sys.executable, "-m", "pipeline.edit.plan", str(copy), str(STEPS)], copy / "_plan_console.txt")
    lc = RUN / "linecheck" / "report.md"                 # round 4's line check, standing in for a re-run
    if lc.exists():
        (copy / "linecheck").mkdir(exist_ok=True)
        dst = copy / "linecheck" / "report.md"
        shutil.copy2(lc, dst)
        now = time.time() + 1
        os.utime(dst, (now, now))                         # the copy only: the original keeps its time
    out = copy / "premiere_check"
    if out.exists():
        shutil.rmtree(out)
    t_exp = run([sys.executable, "-m", "pipeline.edit.premiere", str(copy), "--no-render", f"--out={out}"],
                copy / "_premiere_console.txt")
    return out, t_plan, t_exp


def forms(p):
    """The ways a folder's absolute path appears in the outputs."""
    s = str(Path(p).resolve())
    fwd = s.replace("\\", "/")
    return [s.replace("\\", "\\\\"), s, fwd, quote(fwd[2:])]


def normaliser(copy, out):
    pairs = []
    for new, old in ((out, ROUND), (copy, RUN)):          # the export folder first: it is inside the copy
        pairs += list(zip(forms(new), forms(old)))

    def norm(text):
        for a, b in pairs:
            text = text.replace(a, b)
        return text
    return norm


def lines_of(path, norm):
    text = norm(path.read_text(encoding="utf-8"))
    if path.suffix == ".json":
        text = json.dumps(json.loads(text), indent=1, sort_keys=True, ensure_ascii=False)
    return text.splitlines()


def compared(folder):
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*")
                  if p.suffix in (".xml", ".json") and p.is_file()
                  and not any(part in PREMIERE_OWN for part in p.relative_to(folder).parts))


def diff(out, norm):
    """[{file, at, old, new}] for every difference, at = the line number in round 4's file."""
    diffs = []
    old_files, new_files = set(compared(ROUND)), set(compared(out))
    for rel in sorted(old_files | new_files):
        if rel not in new_files or rel not in old_files:
            diffs.append({"file": rel, "at": 0, "old": ["(file present)"] if rel in old_files else [],
                          "new": ["(file present)"] if rel in new_files else []})
            continue
        a, b = lines_of(ROUND / rel, norm), lines_of(out / rel, norm)
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag != "equal":
                diffs.append({"file": rel, "at": i1 + 1, "old": a[i1:i2], "new": b[j1:j2],
                              "context": a[i1 - 1].strip() if i1 else ""})
    return diffs


def key(d):
    return json.dumps([d["file"], d["old"], d["new"]], ensure_ascii=False)


def show(d, label):
    print(f"--- {label} {d['file']}, round 4 line {d['at']}" + (f", after: {d['context'][:100]}" if d.get("context")
                                                                else ""))
    if len(d["old"]) == len(d["new"]) == 1:              # one changed line: show where it changes
        a, b = d["old"][0].strip(), d["new"][0].strip()
        i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        j = next((k for k, (x, y) in enumerate(zip(a[::-1], b[::-1])) if x != y or k >= min(len(a), len(b)) - i),
                 0)
        lo = max(0, i - 40)
        for sign, s in (("-", a), ("+", b)):
            print(f"  {sign} {'...' * bool(lo)}{s[lo:len(s) - j + 40][:240]}{'...' * (len(s) - j + 40 < len(s))}")
        return
    for sign, ls in (("-", d["old"]), ("+", d["new"])):
        for ln in ls[:MAX_SHOWN]:
            print(f"  {sign} {ln.strip()[:160]}")
        if len(ls) > MAX_SHOWN:
            print(f"  {sign} ... {len(ls) - MAX_SHOWN} more line(s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tag", required=True)
    ap.add_argument("--known", help="differences already explained (a --save-known file)")
    ap.add_argument("--save-known", help="write this run's differences here, to explain and pass as --known later")
    ap.add_argument("--setup-only", action="store_true", help="make the copy and stop")
    ap.add_argument("--reuse", action="store_true", help="plan, export and diff the copy already there")
    a = ap.parse_args(argv)
    copy = scratch_dir(a.tag) / RUN.name
    if a.reuse:
        if not copy.exists():
            raise SystemExit(f"no copy at {copy}; run without --reuse first")
    else:
        copy = make_copy(a.tag)
        print(f"copy: {copy}")
    if a.setup_only:
        return 0
    out, t_plan, t_exp = plan_and_export(copy)
    print(f"re-planned in {t_plan:.0f}s, exported (--no-render) in {t_exp:.0f}s to {out}")
    run_plan, exp_plan = copy / "edit_plan.json", out / "edit_plan.json"
    if run_plan.read_bytes() != exp_plan.read_bytes():
        print("NOTE: the export's edit_plan.json is not a byte copy of the run's plan")
    diffs = diff(out, normaliser(copy, out))
    known = {}
    if a.known:
        known = {key(d): d for d in json.loads(Path(a.known).read_text(encoding="utf-8"))}
    new = [d for d in diffs if key(d) not in known]
    seen = [d for d in diffs if key(d) in known]
    gone = [d for k, d in known.items() if k not in {key(x) for x in diffs}]
    files = len(set(compared(ROUND)) | set(compared(out)))
    print(f"compared {files} file(s) against {ROUND.relative_to(ROOT)}: {len(diffs)} difference(s), "
          f"{len(seen)} known, {len(new)} not explained" + (f"; {len(gone)} known one(s) no longer seen" if gone
                                                            else ""))
    for d in seen:
        print(f"--- known {d['file']}, round 4 line {d['at']}: {known[key(d)].get('why') or '(no why given)'}")
    for d in new:
        show(d, "DIFF")
    for d in gone:
        print(f"--- known, no longer seen: {d['file']}: {d.get('why') or ''}")
    if a.save_known:
        prev = {key(d): d.get("why", "") for d in known.values()}
        Path(a.save_known).write_text(json.dumps([{**d, "why": prev.get(key(d), "")} for d in diffs], indent=1,
                                                 ensure_ascii=False), encoding="utf-8")
        print(f"wrote {len(diffs)} difference(s) to {a.save_known}")
    return 1 if new else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
