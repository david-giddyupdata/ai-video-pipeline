"""The final sequence (R195, R203, R96, R100): the avatar intro, David's approved review sequence nested and untouched,
the avatar outro and the logo outro, in a copy of the approved review project, for David to export.

    python -m pipeline.edit.ppro.final runs/<run_id> <approved review folder> [--out=final_r1] [--no-build|--build-only]

The approved project is copied into a new folder beside it (R61) and never opened itself (R104). Premiere finds the
copy's media by their absolute paths (some of the stored relative ones point inside the approved folder, its overlays,
so a moved run folder would need relinking, as any project would). The copy is made last, after everything that can
fail; --build-only retries Premiere's part from the folder's final_job.json (a failed build closes the copy unsaved).
In that folder:
  * the avatar graphics (pipeline.edit.avatar, avatar/avatar.json "graphics") with the round's loudness chain on their
    voice (R177: the plan's make-up gain, the chain every line got), and the logo outro (R96: the exercise's
    logo_outro settings, else the dashboard exercise's, read from David's Outro sequence) with its music at the
    voice's loudness in Premiere's mix, through the voice's limiter (R204); both are new files in runs/<id>/graphics/;
  * <run>_final.xml, one sequence "<run> final": the intro, a gap the approved sequence fills, the outro and the logo
    outro on V1, their sound on A1, the logo's right channel on A2 (its two channels panned to their sides: a clip
    taken from a stereo file's first channel alone plays that channel, centred; GOTCHAS), an empty Caption titles
    track; caption_titles.json and titles/ (the two avatar lines' cues, pipeline.edit.ppro.titles); transitions.json;
    captions_final.srt (the whole video's captions, for YouTube);
  * Premiere (aidvFinalSequence, jsx/aidv.jsx) opens the copy, imports the XML, puts the approved sequence into the
    gap as a nested clip, adds the two dissolves, the titles and "Final check" markers, saves and closes it; then the
    frame check (pipeline.edit.ppro.framecheck) renders Premiere's own frames at the joins.
Joins (R34, R100): out of the intro a 1.0 s dissolve ends at the cut, over the intro's idle tail and the approved
sequence's first frame held (its first line starts 0.3 s in, so no voice speaks while the avatar is on screen); into
the outro a 0.8 s dissolve starts at the cut, on the approved sequence's last 0.8 s (the nested clip ends that much
early on the timeline, so those frames play under the dissolve, after its last line), and the outro's voice starts
0.2 s after it (pipeline.edit.avatar RECAP_HEAD_S). A hard cut to the logo outro (R96).
"""
import argparse
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from pipeline.config import EXERCISES, tool
from pipeline.edit import loudness as ldn
from pipeline.edit import premiere as pr
from pipeline.edit.ppro import titles
from pipeline.edit.ppro.bridge import call, start
from pipeline.edit.ppro.project import BINS

INTRO_DISSOLVE_S = 1.0          # R34's section dissolve, out of the intro
OUTRO_DISSOLVE_S = 0.8          # into the outro: its 1.0 s head is this dissolve, then 0.2 s before the voice (R100)
LOGO_FROM = "build_an_interactive_dashboard"   # R96's settings, read from David's Outro sequence (2026-10-12)
# Premiere's own mix (GOTCHAS, "Loudness as Premiere plays it"): the approved sequence's mono narration plays 3 dB
# above its files' LUFS (both channels at full level), while a clip this XML takes from a stereo file's first channel
# plays at that channel's mono LUFS. So the avatar's clips get a clip level that puts them where the narration plays.
PREMIERE_MONO_DB = 3.0
MERGE_MAX_CHARS = 46            # a one-word cue joins the one before when the two fit two lines this long
MIX_MAX_DIFF_DB = 1.0           # the mix check: the avatar within this of the approved sequence at each join,
                                # and the logo's music within this of the outro's voice before it (R204)
MIX_MAX_PEAK_DBTP = -1.0        # and no span's true peak over R177's -1 dBTP (the clip level sits after the limiter)
LOGO_MATCH_DB = 0.2             # the logo's file within this of its target; up to LOGO_PASSES limiter passes
LOGO_PASSES = 3
LOGO_SILENT_LUFS = -50.0        # music under this is treated as silent (ebur128 floors at -70)
LOGO_WARN_LIMITED_DB = 3.0      # the report warns when the limiter takes more than this off the music's peaks
SIDE = "pan=mono|c0=c0-c1"      # the difference of the two channels: silent when the music has gone mono


def _hash(*parts):
    import hashlib
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:8]


def with_audio_path(src, af, tag):
    return src.with_name(f"{src.stem}.{tag}{_hash(af, src.stat().st_size, src.name)}.mp4")


def with_audio(src, af, tag):
    """src with its sound through the ffmpeg filter af, the picture copied: a new file beside it (an open project
    locks the old one), reused when it exists."""
    dst = with_audio_path(src, af, tag)
    if not dst.exists():
        part = dst.with_name("_part_" + dst.name)
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-map", "0:v", "-map", "0:a", "-c:v",
                        "copy", "-af", af + ",aresample=48000", "-ac", "2", "-c:a", "aac", "-b:a", "192k", "-movflags",
                        "+faststart", str(part)], check=True)
        part.replace(dst)
    return dst


def loudness_of(path):
    return ldn.measure([path])


def logo_at(src, target, ld):
    """R204: the logo outro's music at target LUFS, the voice's loudness in Premiere's mix, through the voice's limiter
    (ld's limit_dbfs, so its true peak stays under -1 dBTP). Its two channels play panned to their sides, at the
    file's own stereo LUFS, so no clip level is needed. The limiter takes back a little of each raise, so the gain is
    found in up to LOGO_PASSES passes. A pass this call made and didn't keep is deleted; one that already existed is
    left alone, since an earlier build's project may use it (Fable, final_r3)."""
    lim = f"alimiter=limit={10 ** (ld['limit_dbfs'] / 20):.5f}:attack=5:release=50:level=false:latency=true"
    lufs0, tp0 = loudness_of(src)
    if lufs0 < LOGO_SILENT_LUFS:
        raise SystemExit(f"the logo's music measures {lufs0} LUFS: silent, nothing to raise")
    g, made = target - lufs0, []
    for _ in range(LOGO_PASSES):
        af = f"volume={g:.2f}dB,{lim}"
        new = not with_audio_path(src, af, "ld").exists()
        dst = with_audio(src, af, "ld")
        if new:
            made.append(dst)
        lufs, tp = loudness_of(dst)
        if abs(target - lufs) <= LOGO_MATCH_DB + 1e-6:
            break
        g_next = g + target - lufs
        if made and made[-1] == dst:
            made.pop().unlink(missing_ok=True)
        g = g_next
    else:
        raise SystemExit(f"the logo's music reached {lufs} LUFS in {LOGO_PASSES} passes, not {target:.1f}: the "
                         "limiter holds it back; aim it lower")
    limited = round(tp0 + g - tp, 1)                 # how far the limiter brought the raised peaks down
    return dst, {"lufs": lufs, "true_peak_dbtp": tp, "gain_db": round(g, 2), "limited_db": limited,
                 "side_lufs": ldn.measure([dst], SIDE)[0], "clip_gain_db": 0.0,
                 **({"warning": f"the limiter takes {limited} dB off the music's peaks: listen for squashing"}
                    if limited > LOGO_WARN_LIMITED_DB else {})}


def video_frames(path, fps):
    """Frames of the video stream (the container's duration is the longer AAC stream's): its frame count, or its
    duration rounded (ffprobe prints six decimals, so a floor loses a frame one time in three at 30 fps)."""
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=nb_frames,duration", "-of", "json", str(path)], capture_output=True, text=True,
                         check=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["nb_frames"]) if str(s.get("nb_frames", "")).isdigit() else round(float(s["duration"]) * fps)


def write_srt(path, cues):
    """Plain SRT for YouTube: no anchor cue (that one is for Premiere's import, premiere.write_srt), and milliseconds
    from the rounded total, so a time just under a second never prints a second early."""
    def ts(t):
        ms = round(t * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    path.write_text("\n".join(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n"
                              for i, c in enumerate(cues, 1)), encoding="utf-8")


def nest_frames(approved_dir, seq_name):
    """The approved sequence's length in frames, from the XML its project was built from."""
    for xml in sorted(approved_dir.glob("*_full.xml")):
        for s in ET.parse(xml).getroot().iter("sequence"):
            if (s.findtext("name") or "") == seq_name:
                return int(s.findtext("duration"))
    raise SystemExit(f"no sequence named {seq_name!r} in {approved_dir}'s XML")


def media_clip(track, ids, files, name, start, end, in_, out_, path, n, fps, W, H, video, gain_db=None, channel=1,
               pan=None):
    """A clip of path on track; for sound, its channel'th channel, at gain_db, panned to pan (-1 left, 1 right)."""
    c = pr.clipitem(track, ids, name, start, end, in_, out_, n, fps)
    if not video:
        c.remove(c.find("alphatype"))
    files.el(c, path, frames=n, w=W, h=H, audio={"rate": 48000, "channels": 2})
    if not video:
        st = pr.sub(c, "sourcetrack")
        pr.sub(st, "mediatype", "audio")
        pr.sub(st, "trackindex", channel)
        if pan is not None:
            pr.audio_pan(c, pan)
        if gain_db:                           # the clip's Volume level, as Premiere's own FCP XML export writes it
            e = pr.sub(pr.sub(c, "filter"), "effect")
            for tag, v in (("name", "Audio Levels"), ("effectid", "audiolevels"), ("effectcategory", "audiolevels"),
                           ("effecttype", "audiolevels"), ("mediatype", "audio")):
                pr.sub(e, tag, v)
            p = pr.sub(e, "parameter", authoringApp="PremierePro")
            for tag, v in (("parameterid", "level"), ("name", "Level"), ("valuemin", 0), ("valuemax", 3.98109),
                           ("value", f"{10 ** (gain_db / 20):.5f}")):
                pr.sub(p, tag, v)
    return c


def merge_orphans(cues, width=MERGE_MAX_CHARS):
    """A cue of one word (the outro's last, "offer.") joins the cue before it when the two fit two lines, wrapped
    the way the planner wraps every caption (plan._wrap: the most even split)."""
    from pipeline.edit.plan import _wrap
    out = []
    for c in cues:
        if out and len(c["text"].split()) == 1 and abs(c["start"] - out[-1]["end"]) < 0.05:
            text = _wrap(out[-1]["text"].replace("\n", " ") + " " + c["text"], width)
            if text.count("\n") < 2 and max(map(len, text.split("\n"))) <= width:
                out[-1] = {**out[-1], "text": text, "end": c["end"]}
                continue
        out.append(dict(c))
    return out


def prepare(run_dir, approved_dir, out):
    """Everything but Premiere: the media, the XML, the titles, the jobs. Returns the job for aidvFinalSequence."""
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    fps, W, H, run = plan["fps"], plan["width"], plan["height"], plan["run_id"]
    (approved,) = list(approved_dir.glob("*_full.prproj"))
    nest_name, name = f"{run} full", f"{run} final"
    N = nest_frames(approved_dir, nest_name)
    out.mkdir(parents=True, exist_ok=True)
    prproj = out / f"{run}_final.prproj"
    if prproj.exists():
        raise SystemExit(f"{prproj} exists (David's?); not overwriting it: use a new --out, or --build-only to retry")

    # the sound (R177): the avatar's voice through the chain every line got; the logo's music at the voice's (R204)
    ld, lk = plan["settings"]["loudness"], plan["loudness"]
    log = json.loads((run_dir / "avatar" / "avatar.json").read_text(encoding="utf-8"))["graphics"]
    for k in ("opening", "recap"):            # a graphic of a line voiced or cut since (R234: the intro's greeting
        lid = log[k]["line_id"]               # is gone) would put the old words back: refuse (Fable, round 7)
        now = {d[lid]["key"] for d in (json.loads(p.read_text(encoding="utf-8")) for p in EXERCISES.glob("*/lines.json"))
               if lid in d}
        if now and log[k]["audio_key"] not in now:
            raise SystemExit(f"avatar.json's {k} graphic ({log[k]['file']}) was made from another clip of {lid} than "
                             "lines.json's now (R234 cut the intro's greeting): the intro and outro are the stage's "
                             "(pipeline.edit.stage) since round 6")
    gfx = {k: with_audio(run_dir / log[k]["file"], ldn.chain(ld, lk["makeup_db"]), "ld") for k in ("opening", "recap")}
    sound = {k: dict(zip(("lufs", "true_peak_dbtp"), loudness_of(p))) for k, p in gfx.items()}
    target = lk["voice_lufs_after"] + PREMIERE_MONO_DB    # where the approved sequence's narration plays in Premiere
    for k in gfx:
        sound[k]["first_channel_lufs"] = ldn.measure([gfx[k]], "pan=mono|c0=c0")[0]
        sound[k]["clip_gain_db"] = round(target - sound[k]["first_channel_lufs"], 1)
    lg = plan["settings"].get("logo_outro") or json.loads(
        (EXERCISES / LOGO_FROM / "edit_settings.json").read_text(encoding="utf-8"))["logo_outro"]
    logo_src = pr.logo_outro(run_dir, {**plan, "settings": {**plan["settings"], "logo_outro": lg}}, fps, W, H)
    logo, sound["logo"] = logo_at(logo_src, target, ld)
    if sound["logo"]["true_peak_dbtp"] > MIX_MAX_PEAK_DBTP:
        raise SystemExit(f"the logo's music peaks at {sound['logo']['true_peak_dbtp']} dBTP after its limiter")
    sound["premiere_target_lufs"] = round(target, 1)

    # the timeline, in frames
    Lo, Lr, Ll = (video_frames(p, fps) for p in (gfx["opening"], gfx["recap"], logo))
    d_in, d_out = round(INTRO_DISSOLVE_S * fps), round(OUTRO_DISSOLVE_S * fps)
    t1 = Lo                                   # the approved sequence starts where the intro ends
    t2 = t1 + N - d_out                       # it ends d_out early: the dissolve into the outro runs on that tail
    t3 = t2 + Lr                              # the logo outro, after a hard cut
    total = t3 + Ll
    first = min(n["start"] for n in plan["narration"])
    if first < 0.2:                           # R100: no voice while the avatar is on screen
        raise SystemExit(f"the approved sequence's first line starts {first:.2f} s in: too soon after the dissolve")
    said = max(n["start"] + n["length"] for n in plan["narration"])
    if said > (N - d_out) / fps:             # the last line must end before the dissolve into the outro begins
        raise SystemExit(f"the last line ends at {said:.2f} s, inside the dissolve into the outro")

    seq = pr.Seq(name, "sequence-1", fps, W, H, total)
    v1, v2 = seq.track("video", "Avatar and approved sequence"), seq.track("video", titles.TRACK)
    a1 = seq.track("audio", "Avatar and logo outro")
    a2 = seq.track("audio", "Logo outro right")
    ids, files = pr.Ids(), pr.Files(fps)
    for video, tr in ((True, v1), (False, a1)):
        media_clip(tr, ids, files, "avatar intro", 0, t1, 0, Lo, gfx["opening"], Lo, fps, W, H, video,
                   sound["opening"]["clip_gain_db"])
        media_clip(tr, ids, files, "avatar outro", t2, t3, 0, Lr, gfx["recap"], Lr, fps, W, H, video,
                   sound["recap"]["clip_gain_db"])
        media_clip(tr, ids, files, "logo outro", t3, total, 0, Ll, logo, Ll, fps, W, H, video, pan=None if video else -1)
    media_clip(a2, ids, files, "logo outro right", t3, total, 0, Ll, logo, Ll, fps, W, H, False, channel=2, pan=1)
    pr.close_tracks(seq)
    root = ET.Element("xmeml", version="4")
    root.append(seq.el)
    ET.indent(root, "\t")
    xml = out / f"{run}_final.xml"
    xml.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode")
                   + "\n", encoding="utf-8")

    # the avatar's captions as editable titles (R102, R114), in the look of the rest (R126, R192)
    pl = plan["settings"]["captions"]
    intro = [{**c, "end": min(c["end"], (t1 - d_in) / fps)}             # none runs into the dissolve
             for c in pr.graphic_cues(run_dir, plan, "opening", 0.0)]
    cues = merge_orphans(intro) + merge_orphans(pr.graphic_cues(run_dir, plan, "recap", t2 / fps))
    titles.build(out, cues, lambda c, bw, bh: pr.caption_place(c, pl, W, H, bw, bh), W, H, fps, name, t3,
                 size_px=pl["titles"].get("size_px", titles.SIZE_PX), box_hex=pl["titles"].get("box_color"))
    # the whole video's captions as text, for YouTube (R54): the avatar's, and the approved sequence's moved by t1
    job_r = json.loads((approved_dir / "caption_titles.json").read_text(encoding="utf-8"))
    review = [{"start": (c["start_frame"] + t1) / fps, "end": (c["end_frame"] + t1) / fps, "text": c["text"]}
              for c in job_r["cues"] if c["start_frame"] < N - d_out]
    write_srt(out / "captions_final.srt", [{**c, "end": min(c["end"], t3 / fps)}     # none over the logo (R96)
                                           for c in sorted(cues + review, key=lambda c: c["start"])])

    transitions = {"fps": fps, "replace": False, "transitions": [
        {"sequence": name, "track": 0, "cut_frame": t1, "frames": d_in, "type": "Cross Dissolve", "align": "end"},
        {"sequence": name, "track": 0, "cut_frame": t2, "frames": d_out, "type": "Cross Dissolve", "align": "start"}]}
    tc = lambda f: pr.timecode(f, fps)
    markers = [
        {"t": 0.0, "name": "Final check", "comment": "The avatar intro (R203): its voice at the narration's level in "
         "this mix (R177; mix_check.json)."},
        {"t": (t1 - d_in) / fps, "name": "Final check", "comment": "The dissolve into the approved sequence: the avatar "
         f"fades over its first frame; its first line starts {first:.1f} s after the cut at {tc(t1)} (R100)."},
        {"t": t2 / fps, "name": "Final check", "comment": "The dissolve into the outro, over the approved sequence's "
         f"last {OUTRO_DISSOLVE_S} s; the outro's voice starts 0.2 s after it (R100)."},
        {"t": t3 / fps, "name": "Final check", "comment": "A hard cut to the logo outro (R96); its music in stereo, "
         "at the outro voice's loudness (R204; mix_check.json)."}]
    job = {"prproj": str(prproj.resolve()), "xml": str(xml.resolve()), "sequence": name, "nest": nest_name,
           "fps": fps, "nest_frames": N, "nest_at_frame": t1, "nest_tail_frames": d_out, "transitions": transitions,
           "titles": json.loads((out / "caption_titles.json").read_text(encoding="utf-8")), "markers": markers,
           "bins": BINS}
    (out / "final_job.json").write_text(json.dumps(job, indent=1, ensure_ascii=False), encoding="utf-8")
    report = {"sequence": name, "frames": total, "length_s": round(total / fps, 2), "fps": fps,
              "intro": [0, t1], "approved": [t1, t2, N], "outro": [t2, t3], "logo": [t3, total],
              "timecodes": {"approved_starts": tc(t1), "outro_starts": tc(t2), "logo_starts": tc(t3),
                            "ends": tc(total)},
              "first_line_s": first, "last_line_end_s": round(said, 3), "sound": sound,
              "voice_target_lufs": ld["target_lufs"], "cues": len(cues),
              "media": {k: str(p) for k, p in (*gfx.items(), ("logo", logo))}}
    (out / "final_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    shutil.copy2(approved, prproj)                # last: a failure above leaves no copy to block the next run
    return job, report


def build(job):
    print(json.dumps(start(), ensure_ascii=False))
    return call(f"aidvFinalSequence({json.dumps(job, ensure_ascii=False)})", timeout=900, reload=True)


WAV_PRESET = r"C:\Program Files\Adobe\Adobe Premiere Pro 2026\MediaIO\systempresets\3F3F3F3F_57415645\Waveform Audio 48kHz 16-bit.epr"


def mix_check(job, report, out):
    """R177 at the joins and R204 at the logo, in the mix Premiere itself renders (the files don't tell, GOTCHAS):
    spans of the intro, the approved sequence's start and end, the outro and the logo outro exported as WAV through
    the sequence's in and out points (exportAsMediaDirect), each measured; the logo's channel difference too, which
    goes silent if its music plays in mono. The project is opened only when none is (R104) and closed unsaved."""
    fps, (t1, t2, _), (_, t3), (_, end) = job["fps"], report["approved"], report["outro"], report["logo"]
    d_in = round(INTRO_DISSOLVE_S * fps)
    a0, a1 = t1 / fps + 1.0, t2 / fps - 0.5           # the approved sequence, clear of both dissolves
    half = (a1 - a0) / 2                              # a short section's spans never reach into the avatar's
    spans = {"intro": (min(2.0, (t1 - d_in) / fps / 2), (t1 - d_in) / fps - 0.5),
             "approved_start": (a0, a0 + min(75.0, half)), "approved_end": (a1 - min(90.0, half), a1),
             "outro": (t2 / fps + 1.5, t3 / fps - 0.5), "logo": (t3 / fps, end / fps)}
    d = (Path(out) / "mix_check").resolve()            # Premiere writes only to an absolute path
    d.mkdir(exist_ok=True)
    code = """(function () {
      if (app.projects.numProjects > 0) { throw new Error("a project is open in Premiere (" + app.projects[0].path + ")"); }
      if (!app.openDocument(%s)) { throw new Error("Premiere wouldn't open the project"); }
      var r = {};
      try {
        var s = aidvFindSequence(%s), spans = %s, k;
        app.project.openSequence(s.sequenceID);
        for (k in spans) {
          if (!spans.hasOwnProperty(k)) { continue; }
          s.setInPoint(spans[k][0]);
          s.setOutPoint(spans[k][1]);
          r[k] = s.exportAsMediaDirect(spans[k][2], %s, 1);
        }
      } finally {
        for (var i = app.projects.numProjects - 1; i >= 0; i--) {
          if (app.projects[i].path === %s) { app.projects[i].closeDocument(false, false); }
        }
      }
      return r;
    })()""" % (json.dumps(job["prproj"]), json.dumps(job["sequence"]),
               json.dumps({k: [a, b, str(d / f"{k}.wav")] for k, (a, b) in spans.items()}), json.dumps(WAV_PRESET),
               json.dumps(job["prproj"]))
    for k in spans:
        (d / f"{k}.wav").unlink(missing_ok=True)       # a stale file would pass for this build's
    said = call(code, timeout=900)
    gone = [k for k in spans if not (d / f"{k}.wav").exists()]
    if gone:
        raise SystemExit(f"Premiere exported no WAV for {gone} (it answered {said})")
    got = {k: dict(zip(("lufs", "true_peak_dbtp"), ldn.measure([d / f"{k}.wav"]))) for k in spans}
    diffs = {"intro_join": round(got["intro"]["lufs"] - got["approved_start"]["lufs"], 1),
             "outro_join": round(got["outro"]["lufs"] - got["approved_end"]["lufs"], 1),
             "logo_vs_outro_voice": round(got["logo"]["lufs"] - got["outro"]["lufs"], 1)}
    side, file_side = ldn.measure([d / "logo.wav"], SIDE)[0], report["sound"]["logo"].get("side_lufs")
    if file_side is None:                             # a folder prepared before the check existed
        stereo = {"side_lufs": side, "ok": True, "note": "no file side measured; prepare again to check"}
    elif file_side < LOGO_SILENT_LUFS:                # mono music: its difference is silence either way
        stereo = {"side_lufs": side, "file_side_lufs": file_side, "ok": side < LOGO_SILENT_LUFS}
    else:
        stereo = {"side_lufs": side, "file_side_lufs": file_side, "ok": abs(side - file_side) <= MIX_MAX_DIFF_DB}
    hot = [k for k, v in got.items() if v["true_peak_dbtp"] > MIX_MAX_PEAK_DBTP]
    res = {"spans_s": spans, "measured": got, "difference_db": diffs, "logo_stereo": stereo, "peaks_over": hot,
           "ok": all(abs(v) <= MIX_MAX_DIFF_DB for v in diffs.values()) and stereo["ok"] and not hot}
    (d / "mix_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("approved_dir")
    ap.add_argument("--out", default="final_r1")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    a = ap.parse_args(argv)
    run_dir = Path(a.run_dir).resolve()
    out = run_dir / a.out
    if a.build_only:                              # retry Premiere's part on the copy prepare made, only while it is
        import filecmp                            # still that copy: never into a built or saved project (R104)
        job = json.loads((out / "final_job.json").read_text(encoding="utf-8"))
        report = json.loads((out / "final_report.json").read_text(encoding="utf-8"))
        (approved,) = list(Path(a.approved_dir).resolve().glob("*_full.prproj"))
        if not filecmp.cmp(approved, job["prproj"], shallow=False):
            raise SystemExit(f"{job['prproj']} is no longer the approved project's copy (built or saved since); "
                             "build into a new --out instead")
    else:
        job, report = prepare(run_dir, Path(a.approved_dir).resolve(), out)
    print(json.dumps(report, indent=1))
    if a.no_build:
        return 0
    r = build(job)
    print(json.dumps(r, ensure_ascii=False))
    bad = r.get("missing") or (r.get("transitions") or {}).get("failed") or r.get("problems") or not r.get("saved")
    if bad:
        return 1
    m = mix_check(job, report, out)
    print(json.dumps(m, indent=1))
    return 0 if m["ok"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
