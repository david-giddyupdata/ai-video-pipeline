"""The final in the Quick Series design (R231, R232, R235, R237, R241 to R243; R195, R96, R204): the whole video as one
Premiere sequence, for David to export.

    python -m pipeline.edit.ppro.final_quick runs/<run_id> <avatar steps.json> <approved review folder>
        --pip=<pip folder> (--renders=<renders folder> | --still) [--out=final_rN] [--clips=<folder>] [--no-render]
        [--no-premiere] [--build-only] [--mix-check] [--scan] [--frames] [--cta-check]

--still (R245: no HeyGen, the avatar one picture for the whole video; GAPS_PLAN 2b): the box's stays are the
placement's still (pip_job.json's corner pictures), each faded as pipeline.edit.pip's review places it, through to the
outro; no render plan (avatar_iv_plan.json), no renders or their check. The run's intro and outro are what
pipeline.edit.still_avatar register made them, so the intro's clip ends after the carried sentence and the box's first
stay goes on as the stage's own last frame of the oval (stage.meets_stage: no step at the hand-over); a last stay
up at the main body's end is the outro clip's first frame. Without it (--renders), Section A's path, unchanged:

  * the intro: pipeline.edit.stage's Quick Series stage (plan_quick: the cityscape, the left third, the zoom-down into
    the oval), with the steps file's series card (R243) drawn over its first seconds;
  * the main body: the approved sequence nested untouched (R195), and above it the picture-in-picture oval through
    the placement's stays (the pip folder's pip_spans.json, R237's P55): each stay from the Avatar IV renders
    (pip_render.oval_clips: frame-sized transparent clips of each render seen through the oval at its spot, placed by
    time, with R100's handles as media), fading FADE_S in and out (Opacity keys David can move), hidden for voice only
    between (R224). The box's first stay is the intro's render's (R237): the intro's own oval while its clip runs, then
    its still (pip_job's corner picture, as round 7) until the Avatar V intro render carries it. No clip of a render
    has sound: the narration is the nested sequence's own (checked in the mix, mix_check's "doubled voice");
  * the outro: the stage's outro (R235: the oval's still up as the main body's last word dies away, growing into the
    left third beside the recap card), the call to action with the stage's Remotion subscribe animation (R243, its
    whoosh, bell and click, R235), David's url.mov as a clip (R232), the hard cut to the logo outro (R96, R204);
  * the captions: the avatar's lines as editable titles (R102, R126), placed by the stage's rules (R213: bottom
    centre at full frame, beside the card in the left third, middle left through the call to action), and a copy of
    each approved caption the intro's stage would cover.
In a copy of the approved review project (R61, R104: never opened itself; built only when Premiere has no project
open), by aidvStageReview: one sequence "<run> final", the approved sequence nested on V1 at the intro's join.
The measured checks run before Premiere (the stage's stills, C7, the outro's oval, the placement against everything it
keeps clear of); --mix-check measures Premiere's own mix; --scan checks Premiere's H.264 export of the sequence
(pipeline.edit.ppro.exports) frame by frame: the oval shows the planned render frame at every frame it is up, and
nothing a caption or a mark draws comes within CLEAR_PX of it.
"""
import argparse
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from pipeline.config import ROOT
from pipeline.edit import cta as ctas
from pipeline.edit import pip, pip_render, stage
from pipeline.edit import premiere as pr
from pipeline.edit.ppro import final, logo as logo_mod, titles
from pipeline.edit.ppro.bridge import call, start
from pipeline.edit.ppro.project import BINS

MARKER = "Final check"
PIP_MARKER = "PiP"
BOX_TRACK = "Avatar box"
URL_TRACK = "Call to action (url)"
STILL_WHAT = "the still"         # box_frames' and the scan's name for a frame of the still (the corner's picture)
INTRO_STILL_WHAT = "the intro's still"   # the first stay after the intro clip, the stage's own picture of it
OUTRO_STILL_WHAT = "the outro's still"   # a last stay up at the end, the outro clip's first frame


def seq_name(run):
    return f"{run} final"


# ------------------------------------------------------------------------------------------------- the media
def sounds_for(run_dir, plan):
    """The stage's sound cues, made in code (tools/overlay_sounds.py, R158; R235's whoosh and bell) at the plan's
    click level, and R137's click."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("overlay_sounds", ROOT / "tools" / "overlay_sounds.py")
    snd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snd)
    peak = (plan.get("click_sound") or {}).get("peak_dbfs") or -24.0 + plan["loudness"]["effects_gain_db"]
    sounds = {k: Path(snd.write(k, peak)) for k in ("pop", "tick", "whoosh", "bell")}
    sounds["click"] = run_dir / plan["click_sound"]["src"]
    return sounds


def logo_media(run_dir, plan):
    """The logo outro (R96, R204: its music at the voice's loudness, in stereo): the last final's, or made for a run
    with none (pipeline.edit.ppro.logo, GAPS_PLAN 3)."""
    return logo_mod.media(run_dir, plan)


def still_stays(spans_doc, pjob):
    """--still: the box's stays after its first (the intro's, build_xml), each the still at its corner (pip_job.json's
    pngs, as pipeline.edit.pip's review places them) with pip.fades' fades: records shaped as oval_clips' (segment
    STILL_WHAT, spot, f0, f1, fades, file)."""
    N = spans_doc["frames"]
    return [{"segment": STILL_WHAT, "spot": s["spot"], "f0": s["f0"], "f1": s["f1"], "fades": pip.fades(s, N),
             "file": str(Path(pjob["pngs"][s["spot"]]))} for s in spans_doc["spans"][1:] if s["spot"] != "hidden"]


def jobs_of(sp, clips, out):
    """--clips: the stage jobs the clips were rendered from (stage_jobs.json beside their clips/ folder), checked
    against this plan's (stage.render_jobs: the same props for every clip and part, or the clips are another
    plan's) and copied into the final's own folder, where tools/remotion_ctas.py reads them (--cta-check); the
    clips' build is only read. Returns the copy, or None when the clips' folder holds no jobs file (the frame
    counts, layout(), are then the only check)."""
    src, dst = Path(clips).parent / "stage_jobs.json", Path(out) / "stage_jobs.json"
    if not src.exists():
        return None
    norm = lambda jobs: json.loads(json.dumps({j["key"]: j["props"] for j in jobs}, sort_keys=True))
    want_jobs = stage.render_jobs(sp, Path(out))[0]
    got, want = norm(json.loads(src.read_text(encoding="utf-8"))["jobs"]), norm(want_jobs)
    clip_keys = {j["key"] for j in want_jobs if j.get("clip")}       # every clip and part this plan renders; a
    if any(got.get(k) != want.get(k) for k in clip_keys | set(got)):   # still job a later --only made is checked
        raise SystemExit(f"the clips in {clips} were rendered from another stage plan ({src}): render them again")
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    return dst


def stage_pictures(sp, clips, still):
    """stage.meets_stage's pictures, the stage's own frames of the oval (rendered with the stage clips): {"intro":
    clips/intro_oval_still.png or None, "outro": clips/outro_oval_still.png or None (--still only: a render's last
    stay is its oval clip)}. A picture planned but missing, or one drawing anything outside the oval's box at its
    corner, stops the build."""
    from PIL import Image
    meet = stage.meets_stage(sp)
    h = sp["pip"]["handover"]
    got = {"intro": (Path(clips) / "intro_oval_still.png", h["intro_spot"]) if meet["intro"] else None,
           "outro": (Path(clips) / "outro_oval_still.png", h["outro_spot"]) if meet["outro"] and still else None}
    for k, v in got.items():
        if v is None:
            continue
        png, spot = v
        if not png.exists():
            raise SystemExit(f"{png} is missing: render the stage again (its {k}_oval_still job)")
        a = np.asarray(Image.open(png).convert("RGBA"))[..., 3].copy()
        cx, cy = pip.corners(a.shape[1], a.shape[0])[spot]
        a[cy - pip.OVAL_H // 2 - 1:cy + pip.OVAL_H // 2 + 2, cx - pip.OVAL_W // 2 - 1:cx + pip.OVAL_W // 2 + 2] = 0
        if a.max() > 0:                                  # (a pixel of margin: an anti-aliased edge, Fable w3 F5)
            ys, xs = np.nonzero(a)
            raise SystemExit(f"{png} draws outside the oval at the {spot} corner (x {xs.min()} to {xs.max()}, y "
                             f"{ys.min()} to {ys.max()}): not the stage's oval alone; what the stage still draws "
                             "there (a card, the backdrop) ends after the intro clip")
    return {k: (v[0] if v else None) for k, v in got.items()}


def outro_meets(stills, meet, N, outro_spot):
    """--still with the box up at the main body's end (stage_pictures' "outro"): its last stay shows the outro clip's
    first frame (outro_oval_still.png), which the clip takes over at the same spot. Changes stills in place; True
    when it did."""
    last = stills[-1] if stills else None
    if meet.get("outro") and last and last["f1"] == N and last["spot"] == outro_spot:
        last.update({"file": str(meet["outro"]), "segment": OUTRO_STILL_WHAT})
        return True
    return False


def renders_ok(renders, ids):
    """The renders a final uses passed their check (research/heygen_plan/photo_look/body_check.py: frames, rate,
    length, sound against the upload at 0 ms lag): its check.json beside them."""
    ck = Path(renders) / "check.json"
    if not ck.exists():
        raise SystemExit(f"{ck} missing: check the renders first (body_check.py)")
    got = {c["id"]: c for c in json.loads(ck.read_text(encoding="utf-8"))}
    bad = [k for k in ids if not (got.get(k) or {}).get("ok")]
    if bad:
        raise SystemExit(f"renders not checked or failed: {bad}")


# ------------------------------------------------------------------------------------------------- the sequence
def still_clip(track, ids, files, png, a, b, fade, fin, fout, fps, W, H, name):
    """A frame-sized PNG of the oval (the box's still) from a to b with its fades, as pipeline.edit.pip's review."""
    s_in = int(3600 * fps)
    c = pr.clipitem(track, ids, name, a, b, s_in, s_in + b - a, 12 * s_in, fps, alpha="straight")
    files.el(c, Path(png), frames=12 * s_in, w=W, h=H)
    pr.motion(c)
    k = [(s_in, 0.0), (s_in + fade, 100.0)] if fin else [(s_in, 100.0)]
    k += [(s_in + b - a - fade, 100.0), (s_in + b - a, 0.0)] if fout else [(s_in + b - a, 100.0)]
    pr.opacity(c, k)


def oval_clip(track, ids, files, rec, at, fade, fps, W, H, until):
    """One stay of the box from its render's oval clip (pip_render.oval_clips): the stay's frames, the clip's handles
    kept as media, its fades as Opacity keys (in the clip's own frames, as the stills'). A stay up at the main body's
    end stops at until, where the outro's stage takes the oval over (Fable, final_r4: never above the stage's oval)."""
    end = min(at + rec["f1"], until)
    i0, i1 = rec["f0"] - rec["clip_f0"], end - at - rec["clip_f0"]
    c = pr.clipitem(track, ids, f"avatar {rec['segment']} {rec['spot']}", at + rec["f0"], end, i0, i1,
                    rec["frames"], fps, alpha="straight")
    files.el(c, Path(rec["file"]), frames=rec["frames"], w=W, h=H)
    pr.motion(c)
    k = [(i0, 0.0), (i0 + fade, 100.0)] if rec["fades"]["in"] else [(i0, 100.0)]
    k += [(i1 - fade, 100.0), (i1, 0.0)] if rec["fades"]["out"] else [(i1, 100.0)]
    pr.opacity(c, k)


def layout(sp, N, clips, logo, fps):
    """Where everything sits on the final sequence, in frames."""
    nf = lambda p: final.video_frames(p, fps)
    n_ci, n_ti = nf(clips / "intro_common.mov"), nf(clips / "intro_quick.mov")
    n_co, n_to = nf(clips / "outro_common.mov"), nf(clips / "outro_quick.mov")
    if n_ci + n_ti != sp["intro"]["durationInFrames"] or n_co + n_to != sp["outro"]["durationInFrames"]:
        raise SystemExit("the stage clips' lengths aren't the stage plan's: render them again")
    nest_at = sp["nest_at"]
    outro_at = nest_at + N - round(stage.OUTRO_FADE_S * fps)     # the outro fades in over the main body's last 0.8 s
    t3 = outro_at + n_co + n_to
    return {"nest_at": nest_at, "intro_end": n_ci + n_ti, "intro_split": n_ci, "outro_at": outro_at,
            "outro_split": outro_at + n_co, "logo_at": t3, "logo_frames": nf(logo), "end": t3 + nf(logo), "N": N}


def build_xml(sp, out, run, L, clips, logo, voices, gains, sounds, ovals, spans_doc, pjob, fps, W, H, stills=None,
              first_png=None):
    """The final's XML: one sequence, V1 empty but for the logo (aidvStageReview nests the approved sequence there).
    The box's stays after the first: the renders' oval clips (ovals), or with --still the still at each corner
    (stills: still_stays; ovals None). first_png: the first stay's picture after the intro clip (stage_pictures's
    "intro"), else pip's corner picture."""
    ids, files = pr.Ids(), pr.Files(fps)
    f = lambda t: round(t * fps)
    fade = round(pip.FADE_S * fps)
    s = pr.Seq(seq_name(run), "sequence-final", fps, W, H, L["end"])
    v1 = s.track("video", "Approved sequence and logo")
    v2, v3, v4 = s.track("video", "Avatar stage"), s.track("video", BOX_TRACK), s.track("video", URL_TRACK)
    s.track("video", titles.TRACK)
    a1, a2, a3 = (s.track("audio", "Approved sequence and logo"), s.track("audio", "Logo outro right"),
                  s.track("audio", "Avatar voice"))
    stage.video_clip(v2, ids, files, "stage intro", 0, clips / "intro_common.mov", L["intro_split"], fps, W, H)
    stage.video_clip(v2, ids, files, "stage intro (zoom-down and oval)", L["intro_split"], clips / "intro_quick.mov",
                     L["intro_end"] - L["intro_split"], fps, W, H)
    at, N = L["nest_at"], L["N"]
    # the box's first stay: the intro's own oval while its clip runs, then the still (the Avatar V intro will carry it)
    first = spans_doc["spans"][0]
    if not (first["spot"] == sp["pip"]["handover"]["intro_spot"] and first["f0"] == 0
            and (ovals is None or first["f1"] <= ovals["from_f"])):
        raise SystemExit(f"the box's first stay {first} isn't the intro's (R237)")
    if at + first["f1"] > L["intro_end"]:               # (the still's intro clip ends after the carried sentence)
        still_clip(v3, ids, files, first_png or pjob["pngs"][first["spot"]], L["intro_end"], at + first["f1"], fade, False,
                   first["f1"] < N, fps, W, H, f"avatar box {first['spot']} (still)" if stills is not None else
                   f"avatar box {first['spot']} (still: the intro render carries it)")
    for rec in (ovals or {}).get("clips", []):
        oval_clip(v3, ids, files, rec, at, fade, fps, W, H, L["outro_at"])
    # --still: each stay the still at its corner; one up at the main body's end stops where the outro's stage takes the
    # oval over (as oval_clip's)
    for rec in stills or ():
        still_clip(v3, ids, files, rec["file"], at + rec["f0"], min(at + rec["f1"], L["outro_at"]), fade,
                   rec["fades"]["in"], rec["fades"]["out"], fps, W, H, f"avatar box {rec['spot']} (still)")
    # the outro: the stage, R235's still before it, the url, the logo
    stage.video_clip(v2, ids, files, "stage outro (the oval, the left third)", L["outro_at"], clips / "outro_common.mov",
                     L["outro_split"] - L["outro_at"], fps, W, H)
    stage.video_clip(v2, ids, files, "stage outro (full frame)", L["outro_split"], clips / "outro_quick.mov",
                     L["logo_at"] - L["outro_split"], fps, W, H)
    ost = sp.get("outro_still")
    if ost:
        png = clips / "outro_oval_still.png"
        if not png.exists():
            raise SystemExit(f"{png} is missing: render the stage again (its outro_oval_still job)")
        a_, s_in = L["outro_at"] + f(ost["t0"]), int(3600 * fps)
        c = pr.clipitem(v3, ids, "avatar oval (outro, still)", a_, L["outro_at"], s_in, s_in + L["outro_at"] - a_,
                        12 * s_in, fps, alpha="straight")
        files.el(c, png, frames=12 * s_in, w=W, h=H)
        pr.motion(c)
        pr.opacity(c, [(s_in, 0.0), (s_in + f(ost["fade_s"]), 100.0), (s_in + L["outro_at"] - a_, 100.0)])
    cs, cu = sp["cta"]["subscribe"], sp["cta"]["url"]
    if "file" in cs:
        raise SystemExit("the stage plan has R232's original subscribe clip: the final draws R243's Remotion animation "
                         "(the steps file's stage.quick.subscribe)")
    ua, t3 = L["outro_at"] + f(cu["t0"]), L["logo_at"]
    un, um = t3 - ua, f(stage.media_s(cu["file"]) - cu["in_s"])
    if un > um:
        raise SystemExit(f"url.mov holds {um} frames from its in point; the outro needs {un}")
    c = pr.clipitem(v4, ids, Path(cu["file"]).name, ua, t3, f(cu["in_s"]), f(cu["in_s"]) + un, um, fps,
                    alpha=cu["alpha"])
    files.el(c, Path(cu["file"]), frames=um, w=3840, h=2160)
    i0, kf = f(cu["in_s"]), max(1, f(cu["fade_out_s"]))
    pr.opacity(c, [(i0, 100.0), (i0 + un - kf, 100.0), (i0 + un, 0.0)])   # ep03's fade into the hard cut
    lg = L["logo_frames"]
    final.media_clip(v1, ids, files, "logo outro", t3, t3 + lg, 0, lg, logo, lg, fps, W, H, True)
    final.media_clip(a1, ids, files, "logo outro", t3, t3 + lg, 0, lg, logo, lg, fps, W, H, False, pan=-1)
    final.media_clip(a2, ids, files, "logo outro right", t3, t3 + lg, 0, lg, logo, lg, fps, W, H, False, channel=2,
                     pan=1)
    stage.audio_clip(a3, ids, files, "avatar voice (intro)", 0, voices["opening"], fps, gains["opening"])
    stage.audio_clip(a3, ids, files, "avatar voice (outro)", L["outro_at"], voices["recap"], fps, gains["recap"])
    events = [(t, k) for t, k in sp["intro_sounds"]] + [(L["outro_at"] / fps + t, k) for t, k in sp["outro_sounds"]]
    stage.place_sounds(s, ids, files, events, 0.0, sounds, fps)
    pr.close_tracks(s)
    root = ET.Element("xmeml", version="4")
    root.append(s.el)
    ET.indent(root, "\t")
    xml = out / f"{run}_final.xml"
    xml.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode")
                   + "\n", encoding="utf-8")
    motion = [{"track": URL_TRACK, "start_frame": ua, "position": cu["motion"]["position"],
               "scale": cu["motion"]["scale"], "clip": Path(cu["file"]).name}]
    return xml, motion


def box_frames(L, spans_doc, ovals, sp, fps, stills=None, first_what=STILL_WHAT):
    """Every frame of the final where the box shows, from the XML's own placement: [(frame, spot, opacity 0..1,
    what)]: the intro's oval after its zoom-down, its still, each render's stay (or with --still each stay's still,
    stills), the outro's still and its oval before the growth."""
    fade = round(pip.FADE_S * fps)
    at, N, out = L["nest_at"], L["N"], []
    first = spans_doc["spans"][0]
    for fr in range(round((sp["times"]["intro_expand"] + sp["intro"]["avatar"]["moves"][1]["dur"]) * fps) + 1,
                    at + first["f1"]):
        q = 1.0 if fr < at + first["f1"] - fade else (at + first["f1"] - fr) / fade
        out.append((fr, first["spot"], q, "the intro's oval" if fr < L["intro_end"] else first_what))
    for rec in (ovals or {}).get("clips", []) + list(stills or ()):
        for fr in range(at + rec["f0"], min(at + rec["f1"], L["outro_at"])):
            k = fr - at
            q = min(1.0, (k - rec["f0"]) / fade if rec["fades"]["in"] else 1.0,
                    (rec["f1"] - k) / fade if rec["fades"]["out"] else 1.0)
            out.append((fr, rec["spot"], q, rec["segment"]))
    ost = sp.get("outro_still")
    if ost:
        a_ = L["outro_at"] + round(ost["t0"] * fps)
        g = L["outro_at"] + round(sp["times"]["outro_grow"] * fps)
        for fr in range(a_, g):
            out.append((fr, sp["pip"]["handover"]["outro_spot"], min(1.0, (fr - a_) / round(ost["fade_s"] * fps)),
                        "the outro's oval"))
    elif sp["pip"]["handover"].get("box_up_at_end"):     # the box up to the end: the outro clip's oval takes over
        g = L["outro_at"] + round(sp["times"]["outro_grow"] * fps)   # at the same spot (Fable w3 F2)
        for fr in range(L["outro_at"], g):
            out.append((fr, sp["pip"]["handover"]["outro_spot"], 1.0, "the outro's oval"))
    return out


def markers(sp, L, spans_doc, approved_dir, fps, doc, still=False):
    """R106: a "Final check" marker at each moment named in the README, and a "PiP" marker at every move and hide of
    the box (the placement's own, on the final's frames). doc: the avatar steps file (its stage.quick: the series
    card's words and the left third's scale; the words the markers quote, stage.quoted_words); still: --still's
    box."""
    qs, said = doc["stage"]["quick"], stage.quoted_words(doc)
    T, at = sp["times"], L["nest_at"]
    oa = L["outro_at"] / fps
    mk = lambda t, c: {"t": round(t, 4), "name": MARKER, "comment": c}
    ser = qs["series"]
    first_stay = (mk(L["intro_end"] / fps - pip.FADE_S, "The intro's render carries the oval through the box's first "
                     "stay (R237); it fades out here as the " + ("still" if still else "first main-body render")
                     + " fades in at the next spot.")
                  if sp.get("intro_carries_first_stay") else
                  mk(L["intro_end"] / fps, "The intro's clip ends; the box goes on at the same spot as the still, as it "
                     "does at every stay (R245: the avatar a still picture for the whole video).") if still else
                  mk(L["intro_end"] / fps, "The intro's clip ends; the box goes on at the same spot as a still until an "
                     "intro render carries the box's first stay (R237)."))
    out = [mk(0.0, "The intro: full frame on the cityscape; captions bottom centre."),
           mk(T["intro_series_in"], f"The \"{ser['title']}\" card (R243: \"{' / '.join(ser['lines'])}\"), in "
              f"with its whoosh, gone by {T['intro_series_gone']:.2f} s."),
           mk(T["intro_move"], f"Before \"{said['left']}\": you slide into the left third "
              f"({qs['left_scale']:.0%}) as the roadmap card slides in."),
           mk(T["intro_expand"], f"After \"{said['closing']}\": the card grows into the Part 1 card while you zoom "
              f"down into the oval ({sp['intro']['avatar']['moves'][1]['dur']:g} s)."),
           mk(at / fps, "The approved sequence starts under the stage (nested, untouched, R195); the oval speaks its "
              "first sentence."),
           first_stay]
    for c in json.loads((approved_dir / "cards.json").read_text(encoding="utf-8")):
        ly = c["layer"]
        if ly.get("layout") == "chapter_card" and ly["t0"] > 1.0:
            out.append(mk(at / fps + ly["t0"], f"{ly.get('kicker', '')}: {ly['title']} (the approved sequence's card)"))
    # the box's moves and hides, written by pipeline.edit.pip.markers on the final's own frames (R106: every time a
    # marker names is on the sequence David opens, not on the nested main body)
    shifted = [{**s, "f0": s["f0"] + at, "f1": s["f1"] + at} for s in spans_doc["spans"]]
    for m in pip.markers(shifted, fps, L["N"] + at):
        out.append({**m, "name": PIP_MARKER})
    ost, ospot = sp.get("outro_still"), pip.SPOT_NAMES[sp["pip"]["handover"]["outro_spot"]]
    if ost:
        out.append(mk(oa + ost["t0"], "As the main body's last word dies away, the outro's oval fades in at the "
                      f"{ospot} (a still of the outro's first frame, R235)."))
    elif sp["pip"]["handover"].get("box_up_at_end"):
        out.append(mk(oa, f"The outro's oval takes the box over at the {ospot}, the same picture, no fade (R231)."))
    out += [mk(oa + T["outro_grow"], "The oval grows until the cityscape fills the frame; you land in the left third."),
            mk(oa + T["outro_card"], f"\"{said['recap']}\": the recap card; each row ticks on its word."),
            mk(oa + T["outro_full"] - sp["outro"]["card"]["outS"], f"Before \"{said['subscribe']}\": the card fades, "
               "you return to full "
               "frame."),
            mk(oa + T["outro_subscribe"], "The subscribe animation (R243: the brand Remotion variation), with its "
               "whoosh; captions middle left."),
            mk(oa + T["outro_bell"], "The bell's click: the bell sound."),
            mk(oa + T["outro_thumb"], "The thumb's click: our mouse click (R137)."),
            mk(oa + T["outro_url"], f"Your url.mov, its ink starting on \"{said['url']}\"."),
            mk(L["logo_at"] / fps, "Hard cut to the logo outro (R96, R204).")]
    return sorted(out, key=lambda m: m["t"])


REVIEW_MARKER = "Review note"


def review_notes(out, fps):
    """R106: what the round's visual review asks the editor to look at, as markers: out/review_markers.json, [{"tc"
    (HH:MM:SS:FF on the final sequence) or "t" (seconds), "comment"}] or pipeline.edit.ppro.markers' {"sequence",
    "markers"}, when the round has one."""
    p = out / "review_markers.json"
    if not p.exists():
        return []
    sec = lambda v: (lambda h, m, s_, f_: h * 3600 + m * 60 + s_ + f_ / fps)(*(int(x) for x in v.split(":")))
    doc = json.loads(p.read_text(encoding="utf-8"))
    notes = doc["markers"] if isinstance(doc, dict) else doc     # (pipeline.edit.ppro.markers' file reads too)
    return [{"t": round(n["t"] if "t" in n else sec(n["tc"]), 4), "name": n.get("name", REVIEW_MARKER),
             "comment": n["comment"]} for n in notes]


def titles_job(sp, plan, approved_dir, out, qs, L, run):
    """The avatar's captions (both stage places, pipeline.edit.stage.stage_titles_quick) as one aidvCaptionTitles job
    on the final sequence, and the two places (for the checks)."""
    places = [{"name": seq_name(run), "titles_tag": "intro", "kind": "intro", "variant": "quick", "stage_at": 0,
               "frames": L["logo_at"], "at_frame": L["nest_at"], "in_frame": 0, "out_frame": L["N"]},
              {"name": seq_name(run), "titles_tag": "outro", "kind": "outro", "variant": "quick",
               "stage_at": L["outro_at"], "frames": L["logo_at"], "at_frame": L["nest_at"], "in_frame": 0,
               "out_frame": L["N"]}]
    for p in places:
        p["titles"] = stage.stage_titles_quick(p, sp, plan, approved_dir, out, qs)
    job = {**places[0]["titles"], "cues": sorted(places[0]["titles"]["cues"] + places[1]["titles"]["cues"],
                                                 key=lambda c: c["start_frame"])}
    for x, y in zip(job["cues"], job["cues"][1:]):
        if x["end_frame"] > y["start_frame"]:
            raise SystemExit(f"caption {x['text']!r} overlaps the next ({y['text']!r})")
    (out / "caption_titles.json").write_text(json.dumps(job, indent=1, ensure_ascii=False), encoding="utf-8")
    return job, places


# ------------------------------------------------------------------------------------------------- the checks
def placement_check(run_dir, approved_dir, plan, pipd, spans_doc, N):
    """The placement's stays against everything it keeps the box off (pipeline.edit.pip.blocked_frames: captions,
    overlays, marks, click targets, named things, the keep-clear list, the address bar, the pointer), every frame of
    every stay and fade, measured again here (the presence budget in a pass of its own). Read from a
    temporary copy of the pip folder's caches (that folder is a review David may have open: never written)."""
    import tempfile
    extra = pip.keep_clear((spans_doc.get("keep_clear") or {}).get("file"), approved_dir)
    with tempfile.TemporaryDirectory() as d:
        for name in ("overlay_hits.json", "named_boxes.json", "busy.npz"):
            if (pipd / name).exists():
                shutil.copy2(pipd / name, Path(d) / name)
        blocked, why, counts = pip.blocked_frames(run_dir, approved_dir, plan, Path(d), f"{plan['run_id']} full", N,
                                                  extra)
    # two passes: what the box covers, against the obstacles alone; then the stays and hides as placed (lengths,
    # blinks) with the presence budget's windows keeping the box off too, where a stay outside them reads as such
    cover = [c for c in pip.check_spans(spans_doc["spans"], blocked, plan["fps"], N) if "covers" in c or "tile" in c]
    pres = spans_doc.get("presence")
    if pres:
        budget = pip.budget_mask([(w["f0"], w["f1"], w["for"]) for w in pres["windows"]], N)
        placed = [c.replace("covers something", "shows outside the presence budget's windows") if "covers" in c else c
                  for c in pip.check_spans(spans_doc["spans"], blocked | budget, plan["fps"], N)]
    else:
        placed = pip.check_spans(spans_doc["spans"], blocked, plan["fps"], N)
    bad = sorted(set(cover) | {c for c in placed if c not in cover})
    return {"problems": bad, "obstacles": counts, "stays": sum(1 for s in spans_doc["spans"] if s["spot"] != "hidden"),
            "keep_clear_items": len(extra)}


def run_checks(run_dir, approved_dir, plan, pipd, spans_doc, sp, places, pub, out, N, clips=None):
    """C7 and the outro's oval (pipeline.edit.stage), the placement re-measured; written to the final's own folder,
    out/checks_final.json, never into clips (a --clips folder is another build's: GAPS_PLAN 2b). clips: the stage
    clips' folder (the subscribe animation rendered alone is there), out/clips by default."""
    found = {}
    c7, measured = stage.check_c7_quick(places, sp, pub, clips or out / "clips")
    c7 += stage.check_outro_still(places, sp, approved_dir)
    found["c7"] = c7
    found["c7_measures"] = measured
    found["placement"] = placement_check(run_dir, approved_dir, plan, pipd, spans_doc, N)
    (out / "checks_final.json").write_text(json.dumps(found, indent=1, default=str), encoding="utf-8")
    return found


# ------------------------------------------------------------------------------------------------- the mix
SOLO_MUTE = (0, 1, 2)            # the approved sequence and logo, the logo's right channel, the avatar's voice


def mix_check(job, sp, L, out, spans_doc, fps):
    """R177, R204, R235 in the mix Premiere itself renders (as pipeline.edit.stage.mix_check), on the final sequence:
    the avatar's voice against the approved sequence beside it at both joins, the logo's music against the outro's
    voice, every true peak; the stage's cues alone (the voice and the nest muted) against their own files; and no
    doubled voice: a stretch of a long Avatar IV stay exported from the final and from the approved sequence itself
    (in the same project) must match sample for sample (a render's own sound in the mix would add the voice again).
    The project is opened only when none is (R104) and closed unsaved."""
    from pipeline.edit import loudness as ldn
    name, nest = job["sequences"][0]["name"], job["nest"]
    T, at = sp["times"], L["nest_at"] / fps
    oa, t3, end = L["outro_at"] / fps, L["logo_at"] / fps, L["end"] / fps
    stays = sorted((s for s in spans_doc["spans"] if s["spot"] != "hidden" and s["f0"] > 0),
                   key=lambda s: s["f0"] - s["f1"])
    st = stays[0]                                      # the longest stay
    body = ((st["f0"] + 30) / fps, (st["f1"] - 30) / fps)   # main-body seconds, clear of its fades
    spans = {name: {"intro_voice": (2.0, T["intro_carry"] - 1.0),
                    "approved_start": (L["intro_end"] / fps + 0.5, L["intro_end"] / fps + 60.0),
                    "approved_end": (oa - 60.0, oa - 0.2), "outro_voice": (oa + 1.5, t3 - 0.5), "logo": (t3, end),
                    "body_stay": (at + body[0], at + body[1])},
             nest: {"body_stay": body}}
    first = spans_doc["spans"][0]                      # the box's first stay: with an intro render carrying it (R237),
    carry = (2.0, first["f1"] / fps - 1.0)             # its render plays over the nest's narration there too
    if sp.get("intro_carries_first_stay") and carry[1] - carry[0] >= 4.0:
        spans[name]["carry_stay"] = (at + carry[0], at + carry[1])
        spans[nest]["carry_stay"] = carry
    intro_cues = sorted((t, k) for t, k in sp["intro_sounds"])
    outro_cues = sorted((oa + t, k) for t, k in sp["outro_sounds"])
    ser = [c for c in intro_cues if c[1] == "whoosh"][:1]
    card = [c for c in outro_cues if c[1] in ("pop", "tick")][:4]
    sub0 = oa + sp["cta"]["subscribe"]["t0"]
    cta_ = [c for c in outro_cues if sub0 - 1e-6 <= c[0] <= sub0 + sp["cta"]["subscribe"]["s"]]
    solo = {"cues_series": (ser[0][0] - stage.CUE_PREROLL_S, ser[0][0] + 1.0),
            "cues_card": (card[0][0] - stage.CUE_PREROLL_S, card[-1][0] + 1.0),
            "cues_cta": (cta_[0][0] - stage.CUE_PREROLL_S, cta_[-1][0] + 1.3)}
    spans[name].update(solo)
    spans[name]["cta_full_mix"] = solo["cues_cta"]
    d = (out / "mix_check").resolve()
    d.mkdir(exist_ok=True)
    plan = {s: {k: [x, y, str(d / f"{'final' if s == name else 'approved'}_{k}.wav"),
                    list(SOLO_MUTE) if (s == name and k in solo) else []] for k, (x, y) in v.items()}
            for s, v in spans.items()}
    for v in plan.values():
        for x in v.values():
            Path(x[2]).unlink(missing_ok=True)
    code = """(function () {
      if (app.projects.numProjects > 0) { throw new Error("a project is open in Premiere (" + app.projects[0].path + ")"); }
      if (!app.openDocument(%s)) { throw new Error("Premiere wouldn't open the project"); }
      var r = {}, plan = %s, s, k, j;
      try {
        for (s in plan) {
          if (!plan.hasOwnProperty(s)) { continue; }
          var q = aidvFindSequence(s);
          app.project.openSequence(q.sequenceID);
          for (k in plan[s]) {
            if (!plan[s].hasOwnProperty(k)) { continue; }
            var mute = plan[s][k][3];
            for (j = 0; j < mute.length; j++) { q.audioTracks[mute[j]].setMute(1); }
            q.setInPoint(plan[s][k][0]);
            q.setOutPoint(plan[s][k][1]);
            r[s + " " + k] = q.exportAsMediaDirect(plan[s][k][2], %s, 1);
            for (j = 0; j < mute.length; j++) { q.audioTracks[mute[j]].setMute(0); }
          }
        }
      } finally {
        for (var i = app.projects.numProjects - 1; i >= 0; i--) {
          if (app.projects[i].path === %s) { app.projects[i].closeDocument(false, false); }
        }
      }
      return r;
    })()""" % (json.dumps(job["prproj"]), json.dumps(plan), json.dumps(final.WAV_PRESET), json.dumps(job["prproj"]))
    said = call(code, timeout=1200)
    got = {}
    for s, v in plan.items():
        for k, (_, _, fpath, _) in v.items():
            if not Path(fpath).exists():
                raise SystemExit(f"Premiere exported no WAV for {s} {k} (it answered {said})")
            got[f"{'final' if s == name else 'approved'} | {k}"] = dict(zip(("lufs", "true_peak_dbtp"),
                                                                            ldn.measure([fpath])))
    g = lambda k: got[f"final | {k}"]["lufs"]
    diffs = {"intro_voice_vs_approved_start": round(g("intro_voice") - g("approved_start"), 1),
             "outro_voice_vs_approved_end": round(g("outro_voice") - g("approved_end"), 1),
             "logo_vs_outro_voice": round(g("logo") - g("outro_voice"), 1)}
    hot = [k for k, v in got.items() if v["true_peak_dbtp"] > final.MIX_MAX_PEAK_DBTP]
    # no doubled voice: the final's mix over a long stay against the approved sequence's own, sample for sample
    a_, b_ = (pip_render.decode_ref(plan[s]["body_stay"][2]) for s in (name, nest))
    n = min(len(a_), len(b_))
    lag, corr = pip_render.lag_corr(a_[2400:n - 2400], b_[:n], 2400) if n > 9600 else (None, None)
    resid = (float(np.sqrt(np.mean((a_[:n] - b_[:n]) ** 2)) / max(1e-9, float(np.sqrt(np.mean(b_[:n] ** 2)))))
             if n else None)
    doubled = {"stay": f"{st['spot']} {st['start_tc']} to {st['end_tc']} (main body)",
               "final_lufs": g("body_stay"), "approved_lufs": got["approved | body_stay"]["lufs"],
               "lufs_diff": round(g("body_stay") - got["approved | body_stay"]["lufs"], 2),
               "lag_samples": lag, "corr": None if corr is None else round(corr, 5),
               "residual_vs_approved": None if resid is None else round(resid, 5)}
    doubled["ok"] = bool(abs(doubled["lufs_diff"]) <= 0.2 and lag == 0 and resid is not None and resid < 0.01)
    if "carry_stay" in spans[name]:                    # the same test over the carried first stay (Fable, r5)
        a2, b2 = (pip_render.decode_ref(plan[s]["carry_stay"][2]) for s in (name, nest))
        n2 = min(len(a2), len(b2))
        lag2, _ = pip_render.lag_corr(a2[2400:n2 - 2400], b2[:n2], 2400)
        res2 = float(np.sqrt(np.mean((a2[:n2] - b2[:n2]) ** 2)) / max(1e-9, float(np.sqrt(np.mean(b2[:n2] ** 2)))))
        doubled["carry_stay"] = {"span_s": [round(x, 3) for x in spans[nest]["carry_stay"]],
                                 "lufs_diff": round(g("carry_stay") - got["approved | carry_stay"]["lufs"], 2),
                                 "lag_samples": lag2, "residual_vs_approved": round(res2, 5)}
        doubled["ok"] = doubled["ok"] and lag2 == 0 and res2 < 0.01
    # each cue as Premiere plays it (the voice and the nest muted), against its own file's level plus its clip gain
    levels = {"series": stage.cue_levels(plan[name]["cues_series"][2], solo["cues_series"][0], ser),
              "card": stage.cue_levels(plan[name]["cues_card"][2], solo["cues_card"][0], card),
              "cta": stage.cue_levels(plan[name]["cues_cta"][2], solo["cues_cta"][0], cta_)}
    own = {k: max(v for _, v in ldn.momentary(fp)) + final.PREMIERE_MONO_DB for k, fp in sp["sound_files"].items()}
    heard = [(k, v) for x in levels for k, _, v in levels[x]]
    off = [(k, round(v - own[k], 1)) for k, v in heard if v is not None and k in own
           and abs(v - own[k]) > stage.CUE_MATCH_LU and k != "click"]
    pop = next((v for k, _, v in levels["card"] if k == "pop"), None)
    bell = next((v for k, _, v in levels["cta"] if k == "bell"), None)
    cue_ok = (all(v is not None and v > stage.CUE_HEARD_LUFS for _, v in heard) and not off
              and bell is not None and pop is not None and abs(bell - pop) <= stage.CUE_MATCH_LU)
    diffs["bell_vs_card_pop"] = None if bell is None or pop is None else round(bell - pop, 1)
    res = {"spans_s": spans, "measured": got, "difference_db": diffs, "peaks_over": hot,
           "cue_levels_lufs": {**levels, "files": own, "off_own_level": off}, "doubled_voice": doubled,
           "ok": all(abs(v) <= final.MIX_MAX_DIFF_DB for k, v in diffs.items() if k != "bell_vs_card_pop")
           and not hot and cue_ok and doubled["ok"]}
    (d / "mix_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


# ------------------------------------------------------------------------------------------------- the scan
RING_PX = pip.CLEAR_PX           # the band outside the oval where nothing of a caption or a mark may show
CAPTION_GREY = (0x57, 0x57, 0x57)    # C1's caption box
ACCENT = (0xF1, 0x6F, 0x05)          # P5's marks
RING_MIN_PX = 20                 # solid pixels of either (a caption box's fill, a mark's stroke) in the band to list
MATCH_MAX = 6.0                  # mean levels between the export's oval and the planned render frame (H.264 noise
                                 # and its 4:2:0 chroma: about 1 to 3)


def _ring():
    """The band RING_PX wide outside the oval, as a mask over the oval's box grown by RING_PX."""
    yy, xx = np.mgrid[0:pip.OVAL_H + 2 * RING_PX, 0:pip.OVAL_W + 2 * RING_PX]
    cx, cy = (pip.OVAL_W + 2 * RING_PX) / 2, (pip.OVAL_H + 2 * RING_PX) / 2
    e = lambda g: ((xx + 0.5 - cx) / (pip.OVAL_W / 2 + g)) ** 2 + ((yy + 0.5 - cy) / (pip.OVAL_H / 2 + g)) ** 2
    return (e(0) > 1.0) & (e(RING_PX) <= 1.0)


def _solid(band, colour, tol, k):
    """Pixels within tol of colour that sit in a k x k block of such pixels (a box's fill or a stroke, not the
    anti-aliased edge of the screen's own text)."""
    from PIL import Image, ImageFilter
    m = (np.abs(band.astype(int) - np.array(colour)).max(axis=2) <= tol).astype(np.uint8) * 255
    return np.asarray(Image.fromarray(m).filter(ImageFilter.MinFilter(k))) > 0


def _clip_frames(path, spot, a, b, W, H):
    """Frames a..b-1 of an oval clip, its oval's box only, as RGB (BT.709, as Premiere reads it)."""
    import subprocess
    from pipeline.config import tool
    cxs, cys = pip.corners(W, H)[spot]
    x0, y0 = cxs - pip.OVAL_W // 2, cys - pip.OVAL_H // 2
    raw = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(path), "-vf",
                          f"select='between(n\\,{a}\\,{b - 1})',crop={pip.OVAL_W}:{pip.OVAL_H}:{x0}:{y0},"
                          "scale=in_color_matrix=bt709:in_range=tv:out_range=pc", "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    got = np.frombuffer(raw, np.uint8).reshape(-1, pip.OVAL_H, pip.OVAL_W, 3)
    if len(got) != b - a:
        raise SystemExit(f"{path}: {len(got)} of frames {a} to {b - 1}")
    return got


def scan(prproj, out, run):
    """Premiere's H.264 of the final (pipeline.edit.ppro.exports; export it first) against the build's own placement
    (box_frames.json): at every frame the box is up at full opacity, the oval's opaque inside is the planned picture
    (the render's frame from its oval clip, or the still: the picture of the corner the frame's box is at, so --still's
    stays at every corner are each compared with their own) within MATCH_MAX levels, and of the clip's frames before,
    at and after it the planned one is the closest (lip sync: Premiere placed each clip by its frames); at every frame
    the box shows at all, the band RING_PX outside the oval holds no solid caption-box grey or mark orange (C7, X6:
    nothing of a caption or a mark within CLEAR_PX of the box). Results in out/scan.json."""
    from PIL import Image
    from pipeline.edit.ppro import exports
    meta = json.loads((out / "final_report.json").read_text(encoding="utf-8"))
    fps, W, H, at = meta["fps"], 1920, 1080, meta["layout"]["nest_at"]
    ex = exports.Exports(prproj).seq(seq_name(run))
    by_frame = {fr: (spot, q, what) for fr, spot, q, what in
                json.loads((out / "box_frames.json").read_text(encoding="utf-8"))}
    inside, ring = pip.oval_alpha() == 255, _ring()
    corner_pngs, stills_rgb = meta.get("still_pngs") or {}, {}

    def still_of(spot):
        """The still's picture at a corner (--still's still_pngs; else the first stay's, the only corner it shows at)."""
        if spot not in stills_rgb:
            stills_rgb[spot] = np.asarray(Image.open(corner_pngs.get(spot) or meta["still_png"]).convert("RGB"))
        return stills_rgb[spot]
    res = {"frames_box_up": 0, "compared": 0, "worst_match": [], "sync_off": [], "ring": [], "ring_frames": 0,
           "match_mean": None}
    diffs = []

    def box_of(spot):
        cxs, cys = pip.corners(W, H)[spot]
        return cxs - pip.OVAL_W // 2, cys - pip.OVAL_H // 2

    def look(k, arr):
        """The ring test on one exported frame; the oval's inside as floats, or None when not at full opacity."""
        spot, q, what = by_frame[k]
        res["frames_box_up"] += 1
        x0, y0 = box_of(spot)
        band = arr[y0 - RING_PX:y0 + pip.OVAL_H + RING_PX, x0 - RING_PX:x0 + pip.OVAL_W + RING_PX]
        if band.shape[:2] == ring.shape:
            g = int((_solid(band, CAPTION_GREY, 10, 5) & ring).sum())
            o = int((_solid(band, ACCENT, 40, 3) & ring).sum())
            if g > RING_MIN_PX or o > RING_MIN_PX:
                res["ring_frames"] += 1
                if len(res["ring"]) < 400:
                    res["ring"].append({"frame": k, "tc": pip.tc(k, fps), "spot": spot, "grey_px": g, "orange_px": o,
                                        "what": what})
        return arr[y0:y0 + pip.OVAL_H, x0:x0 + pip.OVAL_W].astype(np.float32) if q >= 1.0 else None

    counts = {}

    def note(k, what, d):
        counts[what if not what.startswith("IV-") else "the Avatar IV renders"] = counts.get(
            what if not what.startswith("IV-") else "the Avatar IV renders", 0) + 1
        res["compared"] += 1
        diffs.append(d)
        if d > MATCH_MAX:
            res["worst_match"].append({"frame": k, "tc": pip.tc(k, fps), "what": what, "mean_diff": round(d, 2)})

    covered = set()
    for c in (meta.get("ovals") or {}).get("clips", []):   # each render's stay, its clip's frames beside it
        a, b = at + c["f0"], at + c["f1"]
        j0 = c["f0"] - c["clip_f0"]
        lo, hi = max(0, j0 - 1), min(c["frames"], j0 + (b - a) + 1)
        planned = _clip_frames(c["file"], c["spot"], lo, hi, W, H)
        for k, t, arr in ex.scan(start=a / fps, end=(b - 1) / fps):
            covered.add(k)
            got = look(k, arr)
            if got is None:
                continue
            j = k - a + j0 - lo
            ds = {o: float(np.abs(got - planned[j + o])[inside].mean()) for o in (-1, 0, 1)
                  if 0 <= j + o < len(planned)}
            note(k, c["segment"], ds[0])
            best = min(ds, key=ds.get)
            if best != 0 and ds[best] < ds[0] - 0.5:     # a neighbour clearly closer: Premiere showed another frame
                res["sync_off"].append({"frame": k, "tc": pip.tc(k, fps), "what": c["segment"], "off": best,
                                        "diffs": {str(o): round(v, 2) for o, v in ds.items()}})
    # the stage's own oval (the intro's render through the box's first stay, R237; the outro's before its growth)
    # against the stage clip's frames, and the stills against their pictures: each frame of the export's oval is the
    # planned one, and of its neighbours the planned one is the closest
    clips_dir, Lo = Path(meta["media"]["clips"]), meta["layout"]
    outro_still = Path(meta["media"]["clips"]) / "outro_oval_still.png"
    intro_still = Path(meta["media"]["clips"]) / "intro_oval_still.png"
    pics = {OUTRO_STILL_WHAT: np.asarray(Image.open(outro_still).convert("RGB")) if outro_still.exists() else None,
            INTRO_STILL_WHAT: np.asarray(Image.open(intro_still).convert("RGB")) if intro_still.exists() else None}

    def source(k):
        """(what, clip path, the clip's frame) or (what, picture) for the box's frame k outside the renders."""
        what = by_frame[k][2]
        if what == STILL_WHAT:
            return STILL_WHAT, None, None
        if what == "the intro's oval":
            return ((what, clips_dir / "intro_quick.mov", k - Lo["intro_split"]) if k >= Lo["intro_split"] else
                    (what, clips_dir / "intro_common.mov", k))
        if what == "the outro's oval":
            return (("the outro's still", None, None) if k < Lo["outro_at"] else
                    (what, clips_dir / "outro_common.mov", k - Lo["outro_at"]))
        return what, None, None

    rest = sorted(k for k in by_frame if k not in covered)
    runs, cur = [], []
    for k in rest:                                       # runs of frames from one source, consecutive
        if cur and (k != cur[-1] + 1 or source(k)[:2] != source(cur[-1])[:2]):   # (a still beside the outro's:
                                                                                # two runs, Fable w2 F1)
            runs.append(cur)
            cur = []
        cur.append(k)
    runs += [cur] if cur else []
    for r in runs:
        what, path, j0 = source(r[0])
        planned = None
        if path is not None:
            lo = max(0, j0 - 1)
            n_clip = final.video_frames(path, fps)      # one past the run, inside the clip (Fable, r5)
            planned = _clip_frames(path, by_frame[r[0]][0], lo, min(n_clip, j0 + len(r) + 1), W, H)
        for k, t, arr in ex.scan(start=r[0] / fps, end=r[-1] / fps):
            got = look(k, arr)
            if got is None:
                continue
            x0, y0 = box_of(by_frame[k][0])
            if path is None:
                what_k = source(k)[0]
                pic = still_of(by_frame[k][0]) if what_k == STILL_WHAT else pics.get(what_k)
                if pic is None and what_k in (INTRO_STILL_WHAT, OUTRO_STILL_WHAT):   # (Fable w3 F4)
                    raise SystemExit(f"{what_k}: its picture in {meta['media']['clips']} is missing; the scan "
                                     f"can't compare frame {k}")
                if pic is not None:
                    note(k, what_k, float(np.abs(got - pic[y0:y0 + pip.OVAL_H, x0:x0 + pip.OVAL_W])[inside].mean()))
                continue
            j = source(k)[2] - lo
            ds = {o: float(np.abs(got - planned[j + o])[inside].mean()) for o in (-1, 0, 1)
                  if 0 <= j + o < len(planned)}
            note(k, what, ds[0])
            best = min(ds, key=ds.get)
            if best != 0 and ds[best] < ds[0] - 0.5:
                res["sync_off"].append({"frame": k, "tc": pip.tc(k, fps), "what": what, "off": best,
                                        "diffs": {str(o): round(v, 2) for o, v in ds.items()}})
    res["by_source"] = {w: n for w, n in sorted(counts.items())}
    res["match_mean"] = round(float(np.mean(diffs)), 2) if diffs else None
    res["match_max"] = round(float(np.max(diffs)), 2) if diffs else None
    res["worst_match"] = sorted(res["worst_match"], key=lambda x: -x["mean_diff"])[:50]
    res["ok"] = not res["worst_match"] and not res["sync_off"] and not res["ring_frames"]
    (out / "scan.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


# ------------------------------------------------------------------------------------------------- the review's frames
def review_times(out):
    """The moments the round's visual review looks at (V2), each (final seconds, what): the series card through its
    entrance, hold and exit; the intro's moves and its join into the main body; every move and hide of the box (mid
    fade in, just in, just before the fade out, mid fade out); the outro's oval, its growth, the recap card, the call to
    action through the subscribe animation's moments and the url; the cut to the logo."""
    sp = json.loads((out / "stage_plan.json").read_text(encoding="utf-8"))
    rep = json.loads((out / "final_report.json").read_text(encoding="utf-8"))
    fps, L, T = sp["fps"], rep["layout"], sp["times"]
    at, oa = L["nest_at"] / fps, L["outro_at"] / fps
    fr = lambda k: round(k) / fps
    ser = sp["intro"]["series"]
    out_t = [(0.0, "the intro's first frame")]
    out_t += [(ser["t0"] + x, f"series card: in +{x:.2f} s") for x in (0.3, 0.6, 0.9, 1.2, 1.6, 3.0)]
    out_t += [(ser["t1"] - x, f"series card: out -{x:.2f} s") for x in (1.0, 0.6, 0.4)]
    out_t += [(T["intro_move"] + 0.3, "the move to the left third"), (T["intro_move"] + 3.0, "the left third, roadmap"),
              (T["intro_expand"] + 0.15, "zoom-down starts"), (T["intro_expand"] + 0.45, "zoom-down"),
              (T["intro_expand"] + 0.75, "the oval over the Part 1 card"), (at + 1.0, "the main body under the oval"),
              ]
    first = json.loads((Path(sp["pip"]["dir"]) / "pip_spans.json").read_text(encoding="utf-8"))["spans"][0]
    if sp.get("intro_carries_first_stay"):         # R237: the intro's render through the box's first stay
        out_t += [(fr(L["nest_at"] + 60), "the first stay: the intro's render in the oval"),
                  (fr((L["nest_at"] + L["intro_end"]) / 2), "the first stay, mid"),
                  (fr(L["intro_end"] - 12), "the first stay before its fade out"),
                  (fr(L["intro_end"] - 4), "the first stay fading out")]
    else:
        out_t += [(fr(L["intro_end"] - 1), "the intro clip's last frame"), (fr(L["intro_end"]), "the still's first frame"),
                  (fr(L["nest_at"] + first["f1"] - 5), "the still fading out (first stay's end)")]
    for c in (rep.get("ovals") or {}).get("clips", []) + rep.get("box_stills", []):     # a render's stay or the still's
        a, b, w = L["nest_at"] + c["f0"], L["nest_at"] + c["f1"], f"{c['segment']} at the {pip.SPOT_NAMES[c['spot']]}"
        if c["fades"]["in"]:
            out_t += [(fr(a + 4), f"{w}: fading in"), (fr(a + 12), f"{w}: in")]
        out_t += [(fr((a + b) / 2), f"{w}: mid stay")]
        if c["fades"]["out"]:
            out_t += [(fr(b - 12), f"{w}: before its fade out"), (fr(b - 4), f"{w}: fading out")]
    ost, sub = sp.get("outro_still") or {}, sp["cta"]["subscribe"]["layer"]
    if ost:
        out_t += [(oa + ost["t0"] + 0.15, "the outro's oval fading in"), (oa + ost["t0"] + 0.5, "the outro's oval")]
    elif sp["pip"]["handover"].get("box_up_at_end"):    # the hand-over from the box to the outro's clip
        out_t += [(fr(L["outro_at"] - 1), "the last stay's last frame"),
                  (fr(L["outro_at"]), "the outro clip's first frame (the oval taken over)")]
    out_t += [(oa + T["outro_grow"] + 0.15, "the growth"), (oa + T["outro_card"] + 0.6, "the recap card"),
              (oa + T["outro_card"] + 20.0, "the recap card, rows ticked"),
              (oa + T["outro_full"] + 0.2, "back to full frame"), (oa + sub["t0"] + 0.3, "subscribe: +0.30 s"),
              (oa + sub["t0"] + 0.85, "subscribe: +0.85 s"), (oa + sub["t0"] + 1.6, "subscribe: words in"),
              (oa + sub["bell"] + 0.05, "subscribe: the bell's click"), (oa + sub["bell"] + 0.3, "the bell rings"),
              (oa + sub["thumb"] + 0.05, "subscribe: the thumb's click"), (oa + sub["thumb"] + 0.45, "after the thumb"),
              (oa + sub["t0"] + 5.0, "subscribe: the hold"), (oa + sub["t1"] - 0.7, "subscribe: the exit"),
              (oa + T["outro_url"] + 1.0, "url: writing"), (oa + T["outro_url"] + 3.0, "url: written"),
              (fr(L["logo_at"] - 1), "the last frame before the logo"), (fr(L["logo_at"] + 1), "the logo outro")]
    return [(round(t, 4), w) for t, w in out_t]


def review_frames(prproj, out, run, per_sheet=6):
    """The review's frames from Premiere's H.264 (pipeline.edit.ppro.exports; R240), each to out/review/frame_<ms>.png
    and on labelled sheets of per_sheet (two across, 960 px each): out/review/sheet_NN.png and times.json."""
    from PIL import Image, ImageDraw, ImageFont
    from pipeline.edit.ppro import exports
    d = out / "review"
    times = review_times(out)
    ex = exports.Exports(prproj).seq(seq_name(run))
    ex.pull([t for t, _ in times], d)
    font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 24)
    w, h = 960, 540
    sheets = []
    for i in range(0, len(times), per_sheet):
        part = times[i:i + per_sheet]
        im = Image.new("RGB", (2 * w, h * ((len(part) + 1) // 2)), (20, 20, 20))
        for j, (t, what) in enumerate(part):
            fr = Image.open(d / f"frame_{round(t * 1000):07d}.png").convert("RGB").resize((w, h))
            dr = ImageDraw.Draw(fr)
            label = f"{pr.timecode(round(t * ex.fps), ex.fps)}  {what}"
            dr.rectangle((0, 0, 12 + dr.textlength(label, font=font), 34), fill=(20, 20, 20))
            dr.text((6, 2), label, font=font, fill=(255, 220, 0))
            im.paste(fr, ((j % 2) * w, (j // 2) * h))
        p = d / f"sheet_{i // per_sheet + 1:02d}.png"
        im.save(p)
        sheets.append(str(p))
    (d / "times.json").write_text(json.dumps([{"t": t, "tc": pr.timecode(round(t * ex.fps), ex.fps), "what": w_,
                                               "frame": str(d / f"frame_{round(t * 1000):07d}.png")}
                                              for t, w_ in times], indent=1), encoding="utf-8")
    return sheets


# ------------------------------------------------------------------------------------------------- R243's measures
def cta_check(prproj, out, run):
    """R243's two measures on the built final: the series card's clearance from the avatar's face, on the intro's own
    render (tools/remotion_ctas.py check --only=card: its "face" entry, 12 px wanted), and "Thanks for Watching!"
    against what is behind it in Premiere's own frames (tools/remotion_ctas.py text_pixels: the words' ink from the
    animation rendered alone, stage.alone_job, against a ring around the letters; G6 exempts the words, R235, so the
    figure says how well they read). Premiere's frames come from its single-frame export (fine detail, R240), opened
    only when no project is (R104). Results in out/cta_check/cta_check.json."""
    import subprocess
    from pipeline.config import tool
    from pipeline.edit.ppro import framecheck
    sp = json.loads((out / "stage_plan.json").read_text(encoding="utf-8"))
    rep = json.loads((out / "final_report.json").read_text(encoding="utf-8"))
    fps, oa = sp["fps"], rep["layout"]["outro_at"] / sp["fps"]
    L = sp["cta"]["subscribe"]["layer"]
    times = [L["thumb"] + 0.8, L["t0"] + 5.0]                # stage seconds (remotion_ctas's check_at)
    d = (out / "cta_check").resolve()
    d.mkdir(exist_ok=True)
    got = stage.alone_path(sp, Path(rep["media"]["clips"]))     # the clips the final used (--clips: another build's)
    if not got:
        raise SystemExit("no subscribe animation rendered alone in this folder")
    alone, a0 = got
    finals = [round((oa + t) * fps) / fps for t in times]
    framecheck.check(prproj, d, finals, seq_name(run))
    import importlib.util
    spec = importlib.util.spec_from_file_location("remotion_ctas", ROOT / "tools" / "remotion_ctas.py")
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    res = {"thanks_for_watching": []}
    for t, ft in zip(times, finals):
        comp = d / f"frame_{round(ft * 1000):07d}.png"
        k = round((t - a0) * fps)
        al = d / f"alone_{k:05d}_alpha.png"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", str(alone), "-vf", f"select=eq(n\\,{k})",
                        "-frames:v", "1", "-pix_fmt", "rgba", str(al)], check=True)
        res["thanks_for_watching"].append({"stage_s": round(t, 3), "final_tc": pr.timecode(round(ft * fps), fps),
                                           "premiere_frame": str(comp),
                                           **(rc.text_pixels(comp, al, ctas.TEXT_BOX) or {"error": "no ink found"})})
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "remotion_ctas.py"), "check", str(out), str(d / "card"),
                        "--only=card"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    if r.returncode:
        raise SystemExit(f"remotion_ctas check failed: {r.stderr[-2000:]}")
    card = json.loads((d / "card" / "checks.json").read_text(encoding="utf-8"))["card"]
    res["series_card"] = {"face": card.get("face"), "findings": card.get("findings"),
                          "frames": [{k: f[k] for k in ("t", "overlay_box", "inside_title_safe", "captions")}
                                     for f in card.get("frames", [])]}
    (d / "cta_check.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res


# ------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("steps")
    ap.add_argument("approved_dir")
    ap.add_argument("--pip", required=True, help="the placement's folder in the run (pip_spans.json, pip_job.json; "
                    "avatar_iv_plan.json with --renders)")
    box = ap.add_mutually_exclusive_group(required=True)
    box.add_argument("--renders", help="the Avatar IV renders' folder (<id>_*.mp4, check.json)")
    box.add_argument("--still", action="store_true", help="R245: the box the placement's still through every stay "
                     "(no renders; the intro and outro as pipeline.edit.still_avatar register made them)")
    ap.add_argument("--out", default="final_r4")
    ap.add_argument("--clips", default=None, help="use the stage clips already rendered in this folder")
    ap.add_argument("--no-render", action="store_true", help="the stage clips are in --out already")
    ap.add_argument("--no-premiere", action="store_true", help="everything but Premiere's build")
    ap.add_argument("--build-only", action="store_true", help="Premiere's build from the folder's final_job.json")
    ap.add_argument("--mix-check", action="store_true", help="only the mix check, on the folder's built project")
    ap.add_argument("--scan", action="store_true", help="only the scan of Premiere's H.264 export")
    ap.add_argument("--frames", action="store_true", help="only the review's frames from Premiere's H.264 export")
    ap.add_argument("--cta-check", action="store_true", help="only R243's measures (the card's face clearance, "
                    "\"Thanks for Watching!\" in Premiere's frames)")
    a = ap.parse_args(argv)
    run_dir, approved_dir = Path(a.run_dir).resolve(), Path(a.approved_dir).resolve()
    out, pipd = run_dir / a.out, (run_dir / a.pip).resolve()
    renders = None if a.still else (run_dir / a.renders).resolve()
    pub = run_dir / "stage_public"
    pub.mkdir(exist_ok=True)
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    fps, W, H, run = plan["fps"], plan["width"], plan["height"], plan["run_id"]
    (approved,) = list(approved_dir.glob("*_full.prproj"))
    if a.build_only or a.mix_check or a.scan or a.cta_check or a.frames:
        job = json.loads((out / "final_job.json").read_text(encoding="utf-8"))
        if a.frames:
            print(json.dumps(review_frames(Path(job["prproj"]), out, run), indent=1))
            return 0
        if a.cta_check:
            print(json.dumps(start(), ensure_ascii=False))
            print(json.dumps(cta_check(Path(job["prproj"]), out, run), indent=1, default=str))
            return 0
        if a.scan:
            r = scan(Path(job["prproj"]), out, run)
            print(json.dumps({k: v for k, v in r.items() if k not in ("ring",)}, indent=1)[:4000])
            return 0 if r["ok"] else 1
        if a.build_only:
            return pip.build({k: v for k, v in job.items() if k != "stage_places"}, approved)
        sp = json.loads((out / "stage_plan.json").read_text(encoding="utf-8"))
        rep = json.loads((out / "final_report.json").read_text(encoding="utf-8"))
        spans_doc = json.loads((pipd / "pip_spans.json").read_text(encoding="utf-8"))
        print(json.dumps(start(), ensure_ascii=False))
        r = mix_check(job, sp, rep["layout"], out, spans_doc, fps)
        print(json.dumps(r, indent=1))
        return 0 if r["ok"] else 1
    out.mkdir(parents=True, exist_ok=True)
    prproj = out / f"{run}_final.prproj"
    if prproj.exists():
        raise SystemExit(f"{prproj} exists (David's?); not overwriting it: use a new --out")
    doc = json.loads(Path(a.steps).read_text(encoding="utf-8"))
    qs = doc["stage"]["quick"]
    if not (qs.get("series") and qs.get("subscribe")):
        raise SystemExit("the steps file's stage.quick has no series card or subscribe animation (R243)")
    spans_doc = json.loads((pipd / "pip_spans.json").read_text(encoding="utf-8"))
    rplan = None
    if not a.still:                                      # the renders' plan, made on this very placement
        rplan = json.loads((pipd / "avatar_iv_plan.json").read_text(encoding="utf-8"))
        if Path(rplan["placement"]).resolve() != (pipd / "pip_spans.json").resolve():
            raise SystemExit(f"{pipd / 'avatar_iv_plan.json'} was planned on {rplan['placement']}")
    N = final.nest_frames(approved_dir, f"{run} full")
    if spans_doc["frames"] != N:
        raise SystemExit(f"{pipd} was placed on {spans_doc['frames']} frames, the approved sequence is {N}")
    sp = stage.plan_quick(run_dir, doc, plan, approved_dir, pub, pipd)
    (out / "stage_plan.json").write_text(json.dumps(sp, indent=1), encoding="utf-8")
    print(json.dumps(sp["times"], indent=1), "nest at frame", sp["nest_at"])
    clips = Path(a.clips).resolve() if a.clips else out / "clips"
    if a.clips:                                          # the clips' jobs: this plan's, and beside the final
        jobs_of(sp, clips, out)
    if not a.no_render and not a.clips:
        res, bad = stage.render(sp, pub, out)
        print(json.dumps(res, indent=1))
        if bad:
            print(json.dumps(bad, indent=1))
            return 1
    if not a.clips:
        n, still_found = stage.check_stills(out)         # G6, G7, R187 on the stage's stills; R243's alone check
        print(f"{n} stills checked: {len(still_found)} finding(s) in {out / 'checks.json'}")
        for f in still_found:
            print("  " + f.get("what", ""))
    else:                                                # the stills were checked with their render; the alone
        still_found = stage.subscribe_alone_check(sp, clips)   # check runs on the clips used
    strays = [f for f in still_found if f.get("check") == "stray"]   # drawn where nothing may be: gate the build
    # the media: the voices, the cues, the logo, the box's ovals (or its still at each corner)
    voices, gains = {}, {}
    for tag, key, until in (("opening", "intro", sp["intro_render"]["carry"]["at_s"] - 0.02), ("recap", "outro", None)):
        g = sp[f"{key}_render"]
        trim = sp["intro_trim_s"] if tag == "opening" else stage.PAD_S - stage.RECAP_HEAD_S
        end = until if until else g["voice_at_s"] + g["voice_s"] + stage.RECAP_TAIL_S
        voices[tag], gains[tag] = stage.voice(run_dir, g, trim, end, plan, out, tag)
    logo = logo_media(run_dir, plan)
    sp["logo_s"] = final.video_frames(logo, fps) / fps
    sounds = sounds_for(run_dir, plan)
    sp["sound_files"] = {k: str(v) for k, v in sounds.items()}
    (out / "stage_plan.json").write_text(json.dumps(sp, indent=1), encoding="utf-8")
    pjob = json.loads((pipd / "pip_job.json").read_text(encoding="utf-8"))
    meet = stage_pictures(sp, clips, a.still)            # the stage's own picture where the box meets its oval
    if a.still:
        ovals, stills = None, still_stays(spans_doc, pjob)
        outro_meets(stills, meet, N, sp["pip"]["handover"]["outro_spot"])
        missing = sorted({s["file"] for s in stills if not Path(s["file"]).exists()})
        if missing:
            raise SystemExit(f"the placement's still pictures are missing: {missing}")
    else:
        renders_ok(renders, [g["id"] for g in rplan["segments"]])
        ovals, stills = pip_render.oval_clips(spans_doc, rplan, renders, renders / "ovals", W, H,
                                              ref_x=pjob["still"]["person_x"]), None
    L = layout(sp, N, clips, logo, fps)
    xml, motion = build_xml(sp, out, run, L, clips, logo, voices, gains, sounds, ovals, spans_doc, pjob, fps, W, H,
                            stills, meet["intro"])
    tj, places = titles_job(sp, plan, approved_dir, out, qs, L, run)
    found = run_checks(run_dir, approved_dir, plan, pipd, spans_doc, sp, places, pub, out, N, clips)
    boxes = box_frames(L, spans_doc, ovals, sp, fps, stills, INTRO_STILL_WHAT if meet["intro"] else STILL_WHAT)
    tc = lambda fr: pr.timecode(fr, fps)
    report = {"sequence": seq_name(run), "fps": fps, "frames": L["end"], "length_s": round(L["end"] / fps, 2),
              "layout": L, "timecodes": {"approved_starts": tc(L["nest_at"]), "intro_clip_ends": tc(L["intro_end"]),
                                         "outro_starts": tc(L["outro_at"]), "logo_starts": tc(L["logo_at"]),
                                         "ends": tc(L["end"])},
              "ovals": ovals, "still_png": pjob["pngs"][spans_doc["spans"][0]["spot"]],
              "box_frames": "box_frames.json", "box_shown_s": round(len(boxes) / fps, 1),
              "media": {"logo": str(logo), "voices": {k: str(v) for k, v in voices.items()}, "clips": str(clips)},
              "voice_gains_db": gains, "checks": {k: v for k, v in found.items() if k != "c7_measures"}}
    if a.still:                                          # the scan's picture at each corner, and the stays it shows at
        report.update({"box": "still", "still_pngs": pjob["pngs"], "box_stills": stills})
    (out / "final_report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    (out / "box_frames.json").write_text(json.dumps([list(b) for b in boxes]), encoding="utf-8")
    bins = {**BINS, "media": ([{"bin": "Avatar box", "match": r"[\\/]intro_oval_still\.png$"}] if meet["intro"] else [])
            + [   # (the intro's still in its bin when used, Fable w3 F1)
        {"bin": "Avatar box", "match": r"[\\/](pip_oval_[^\\/]+\.png|outro_oval_still\.png|oval_IV-[^\\/]+\.mov)$"},
        {"bin": "Call to action (url)", "match": r"[\\/]url\.mov$"},
        {"bin": "Avatar stage", "match": r"[\\/]clips[\\/](intro|outro)_[^\\/]+\.mov$"},
        {"bin": "Avatar voice", "match": r"[\\/]voice_(opening|recap)\.wav$"},
        {"bin": "Sounds", "match": r"[\\/]motion-library[\\/]sounds[\\/][^\\/]+\.wav$"}] + BINS["media"]}
    stage_places = [{k: v for k, v in p.items()} for p in places]
    job = {"prproj": str(prproj.resolve()), "xml": str(xml.resolve()), "nest": f"{run} full", "fps": fps,
           "nest_frames": N, "bins": bins, "stage_places": stage_places,
           "sequences": [{"name": seq_name(run), "at_frame": L["nest_at"], "in_frame": 0, "out_frame": N,
                          "v1_clips": 1, "titles": tj, "motion": motion,
                          "markers": markers(sp, L, spans_doc, approved_dir, fps, doc, a.still)
                          + review_notes(out, fps)}]}
    (out / "final_job.json").write_text(json.dumps(job, indent=1, ensure_ascii=False), encoding="utf-8")
    problems = found["c7"] + found["placement"]["problems"] + strays
    print(json.dumps({"c7": found["c7"], "placement": found["placement"], "length": report["timecodes"]}, indent=1))
    if a.no_premiere or problems:
        return 1 if problems else 0
    rc = pip.build({k: v for k, v in job.items() if k != "stage_places"}, approved)
    if rc:
        return rc
    print(json.dumps(start(), ensure_ascii=False))
    m = mix_check(job, sp, L, out, spans_doc, fps)
    print(json.dumps(m, indent=1))
    return 0 if m["ok"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
