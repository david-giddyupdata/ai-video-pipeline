"""The logo outro's media (R96, R204) for a stage review or a Quick Series final, with or without an earlier final.

    python -m pipeline.edit.ppro.logo runs/<run_id> [--dry]

media(run_dir, plan): the logo file of the newest final_r*/final_report.json that names one (its media.logo, as
final_quick.logo_media took it: Section A gets the very file its stage and finals use). With none (a new run: only
pipeline.edit.ppro.final wrote that report, and it needs HeyGen's MP4 graphics), the logo is made as final.prepare
makes it: the plan's logo_outro settings, else the dashboard exercise's (final.LOGO_FROM; R96: David's "Outro"
sequence, LogoAnimation.mp4 fading in over the Rossini), rendered once by premiere.logo_outro into the run's
graphics/; then its music raised to where the approved sequence's narration plays in Premiere's mix (the plan's
voice_lufs_after plus final.PREMIERE_MONO_DB) through the voice's limiter, in up to final.LOGO_PASSES passes to within
final.LOGO_MATCH_DB of that (final.logo_at, R204), its true peak at final.MIX_MAX_PEAK_DBTP or under. Each is a new
file beside the last (an open project locks the one it uses), reused when it exists. No Premiere: the level as
Premiere plays it is the final's mix check.

media_info() says where the file came from and, for a made one, its measures; dry=True makes nothing and returns
what it would take or make.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from pipeline.config import EXERCISES


def finals(run_dir):
    """The run's final_r*/final_report.json naming a logo, oldest first (by the round's number)."""
    def logo_of(p):
        return (json.loads(p.read_text(encoding="utf-8")).get("media") or {}).get("logo")
    return sorted((p for p in Path(run_dir).glob("final_r*/final_report.json") if logo_of(p)),
                  key=lambda q: int(re.sub(r"\D", "", q.parent.name) or 0))


def settings(plan):
    """The logo outro's settings (R96) and where they came from, as final.prepare reads them."""
    from pipeline.edit.ppro import final
    lg = plan["settings"].get("logo_outro")
    if lg:
        return lg, "the plan's settings (the exercise's edit_settings.json logo_outro)"
    path = EXERCISES / final.LOGO_FROM / "edit_settings.json"
    return json.loads(path.read_text(encoding="utf-8"))["logo_outro"], str(path)


def rendered_path(run_dir, lg, fps, W, H):
    """Where premiere.logo_outro puts the logo for these settings (its own naming, for the dry plan)."""
    key = json.dumps({**lg, "fps": fps, "w": W, "h": H}, sort_keys=True)
    return Path(run_dir) / "graphics" / f"logo_outro_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:8]}.mp4"


def media_info(run_dir, plan, dry=False):
    """{"logo": the file, "from": the final it came from or "made", ...}; the module's docstring."""
    from pipeline.edit import premiere as pr
    from pipeline.edit.ppro import final
    run_dir = Path(run_dir).resolve()
    got = finals(run_dir)
    if got:
        logo = Path(json.loads(got[-1].read_text(encoding="utf-8"))["media"]["logo"])
        if not logo.exists():
            raise SystemExit(f"{got[-1]} names the logo {logo}, which is missing")
        return {"logo": str(logo), "from": got[-1].parent.name, "report": str(got[-1])}
    fps, W, H = plan["fps"], plan["width"], plan["height"]
    lg, where = settings(plan)
    ld, lk = plan["settings"]["loudness"], plan["loudness"]
    target = round(lk["voice_lufs_after"] + final.PREMIERE_MONO_DB, 2)     # the narration as Premiere plays it
    if dry:
        src = rendered_path(run_dir, lg, fps, W, H)
        inputs = [lg["video"]["path"]] + [m["path"] for m in lg["music"]]
        return {"logo": None, "from": "made (dry: nothing made)", "settings": where,
                "inputs": {p: Path(p).exists() for p in inputs},
                "render": {"file": str(src), "exists": src.exists(), "by": "pipeline.edit.premiere.logo_outro",
                           "length_s": lg["length_s"], "size": [W, H], "fps": fps,
                           "video": {k: lg["video"][k] for k in ("at_s", "fade_in_s")},
                           "music": [{k: m[k] for k in ("level", "fade_out")} for m in lg["music"]]},
                "raise": {"by": "pipeline.edit.ppro.final.logo_at (R204)", "target_lufs": target,
                          "within_lu": final.LOGO_MATCH_DB, "passes": final.LOGO_PASSES,
                          "limit_dbfs": ld["limit_dbfs"], "max_true_peak_dbtp": final.MIX_MAX_PEAK_DBTP,
                          "file": f"{src.stem}.ld<hash>.mp4 beside it"}}
    missing = [p for p in [lg["video"]["path"]] + [m["path"] for m in lg["music"]] if not Path(p).exists()]
    if missing:
        raise SystemExit(f"the logo outro's sources are missing: {missing}")
    src = pr.logo_outro(run_dir, {**plan, "settings": {**plan["settings"], "logo_outro": lg}}, fps, W, H)
    logo, sound = final.logo_at(src, target, ld)
    if sound["true_peak_dbtp"] > final.MIX_MAX_PEAK_DBTP:
        raise SystemExit(f"the logo's music peaks at {sound['true_peak_dbtp']} dBTP after its limiter")
    return {"logo": str(logo), "from": "made", "settings": where, "render": str(src), "target_lufs": target,
            "sound": sound}


def media(run_dir, plan):
    """The logo outro's file (the module's docstring)."""
    return Path(media_info(run_dir, plan)["logo"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("--dry", action="store_true", help="make nothing: say what would be taken or made")
    a = ap.parse_args(argv)
    run_dir = Path(a.run_dir).resolve()
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    print(json.dumps(media_info(run_dir, plan, dry=a.dry), indent=1))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
