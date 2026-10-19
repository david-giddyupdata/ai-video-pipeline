"""Premiere builds the round's project itself (R61, R102): no import, no restyling, no bins to sort by hand.

    python -m pipeline.edit.ppro.project runs/<run_id>/premiere_rN [--frames=all|<s>,<s>] [--keep-open]

Starts Premiere if it isn't running (pipeline.edit.ppro.bridge), then makes <run>_full.prproj in the export folder:
the full XML imported, its items sorted into bins (BINS), one editable title per caption cue on the Caption titles
track (caption_titles.json, pipeline.edit.ppro.titles), the work-cut transitions at their cuts (transitions.json,
R105), saved and closed. It never overwrites a project that is
there: David saves his edits in that file. --frames exports Premiere's own render at the given seconds, or mid-cue for
every cue, to <export>/titles_check/ (QE exportFramePNG), to check the titles without a person.
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

from pipeline.edit.ppro.bridge import call, start

# Bins for the import's flat list (David's demo, 2026-10-13: "Audio" and "Sequences"). A media item goes to the first
# bin whose pattern matches its path; sequences to their own bin; anything else stays in the root and is reported.
BINS = {"sequences": "Sequences",
        "media": [{"bin": "Sounds", "match": r"[\\/]audio[\\/]click_[^\\/]+\.wav$"},   # R137
                  {"bin": "Narration", "match": r"[\\/]audio[\\/]"},
                  {"bin": "Graphics", "match": r"[\\/]graphics[\\/]"},
                  {"bin": "Recording", "match": r"[\\/]raw\.mp4$|[\\/]holds[\\/]|[\\/]speed[\\/]"},
                  {"bin": "Cursor, marks and overlays", "match": r"[\\/]overlays[\\/]|[\\/]overview[\\/]"},
                  {"bin": "Privacy blurs", "match": r"[\\/]privacy[\\/]blur_[^\\/]+$"},
                  {"bin": "Corrections", "match": r"[\\/]corrections[\\/]correction_[^\\/]+\.png$"},   # R173
                  {"bin": "Captions (PNG, off)", "match": r"[\\/]captions[\\/][^\\/]+\.png$"}]}


def frames(job, times_s, out_dir):
    """Premiere's own render of the job's sequence at times_s -> out_dir/frame_<ms>.png (QE exportFramePNG), each
    time's nearest frame: the playhead is put on that frame's first tick, since a time between frames shows the frame
    it falls in (22.033 s, frame 661 written to three places, showed frame 660; R233's exports pick the nearest too)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    shots = [[t, str((out_dir / f"frame_{round(t * 1000):07d}").resolve())] for t in times_s]
    call("(function () { var s = aidvFindSequence(%s); app.project.openSequence(s.sequenceID); "
         "app.enableQE(); var q = qe.project.getActiveSequence(), sh = %s, tpf = Number(s.timebase); "
         "for (var i = 0; i < sh.length; i++) { "
         "s.setPlayerPosition(String(Math.round(sh[i][0] * AIDV_TPS / tpf) * tpf)); "
         "q.exportFramePNG(q.CTI.timecode, sh[i][1]); } return true; })()"
         % (json.dumps(job["sequence"]), json.dumps(shots)), timeout=300)
    return [Path(f + ".png").exists() for _, f in shots]   # the file on disk, not QE's word (it adds the .png)


def build(export_dir, frame_times=None, keep_open=False):
    d = Path(export_dir).resolve()
    job_p = d / "caption_titles.json"
    job = json.loads(job_p.read_text(encoding="utf-8"))
    (xml,) = [p for p in d.glob("*_full.xml") if p.name != "captions_full.xml"]
    prproj = d / f"{xml.stem}.prproj"
    if prproj.exists():
        raise SystemExit(f"{prproj} exists (David's?); not overwriting it")
    bad = [c["mogrt"] for c in job["cues"] if not zipfile.is_zipfile(c["mogrt"])
           or "definition.json" not in zipfile.ZipFile(c["mogrt"]).namelist()]
    if bad:                       # a missing file or a broken .mogrt stops Premiere on a dialog, or hangs its scripting
        raise SystemExit(f"{len(bad)} title template(s) missing or broken, first {bad[0]}; re-run the export")
    gone = [m for m in media(xml) if not m.exists()]
    if gone:                      # a missing file opens Premiere's "link media" dialog, which stops every later call
        raise SystemExit(f"{len(gone)} media file(s) the XML uses are missing, first {gone[0]}")
    print(json.dumps(start(), ensure_ascii=False))
    r = call(f"aidvBuildProject({json.dumps(str(xml))}, {json.dumps(str(prproj))}, {json.dumps(str(job_p))}, "
             f"{json.dumps(BINS)})", timeout=900, reload=True)
    try:
        print(json.dumps(r, ensure_ascii=False))
        tr_p = d / "transitions.json"                 # R105: the work-cut transitions, placed here, not by David
        if tr_p.exists():
            r["transitions"] = call(f"(function () {{ var r = aidvTransitions({tr_p.read_text(encoding='utf-8')}); "
                                    "app.project.save(); return r; })()", timeout=600)
            print(json.dumps(r["transitions"], ensure_ascii=False))
        if frame_times:
            fps = job["fps"]
            times = ([(c["start_frame"] + c["end_frame"]) / 2 / fps for c in job["cues"]] if frame_times == "all"
                     else [float(t) for t in frame_times.split(",")])
            print("frames:", frames(job, times, d / "titles_check"))
    finally:                      # closed even when a step fails, so Premiere doesn't hold the round's media
        if not keep_open:
            call("(function () { for (var k = 0; k < app.projects.numProjects; k++) { if (app.projects[k].path === %s)"
                 " { app.projects[k].closeDocument(true, false); return true; } } return false; })()"
                 % json.dumps(str(prproj)), timeout=120)
    return r


def media(xml):
    """Every file an FCP 7 XML points to (<pathurl>), as paths."""
    import re
    from urllib.parse import unquote
    urls = set(re.findall(r"<pathurl>([^<]+)</pathurl>", Path(xml).read_text(encoding="utf-8")))
    return sorted(Path(unquote(re.sub(r"^file://localhost/", "", u))) for u in urls)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("export_dir")
    ap.add_argument("--frames")
    ap.add_argument("--keep-open", action="store_true")
    a = ap.parse_args(argv)
    r = build(a.export_dir, a.frames, a.keep_open)
    return 0 if not r.get("missing") and not (r.get("transitions") or {}).get("failed") else 1


if __name__ == "__main__":
    sys.exit(main())
