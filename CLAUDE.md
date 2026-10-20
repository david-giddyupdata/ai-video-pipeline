# AIDrivenVideo: automated training-video pipeline

> **Public copy:** `SESSION_HANDOFF.md`, `PLAN.md` and `docs/` are not published; this file is kept as an example
> of the agent's brief.

Turns a browser-based exercise into a narrated YouTube tutorial. Test case: *Build an Interactive Dashboard*
(<CLIENT> workshop).

**Starting a session? Read `SESSION_HANDOFF.md` first.** It says where work stopped and what is next.
**Wrapping up?** Rewrite `SESSION_HANDOFF.md` (current state only, no history). A new David decision goes into
`RULES.md` as the next R number, and nowhere else; other files point to it.

| File | Holds |
|---|---|
| `RULES.md` | Every David decision, numbered R1, R2, ... Don't relitigate them. |
| `GOTCHAS.md` | How the tools misbehave (Playwright, Codespaces, OBS, edge-tts, Remotion). |
| `SPEC.md` | Design and file formats. |
| `PLAN.md` | Phase and slice status, and what's next. `docs/SLICE_LOG.md` has the slice results. |
| `research/style_study/` | David's measured style (`STYLE_PROFILE.md`) and narration (`NARRATION.md`). |
| `VIDEO_RULES.md` (in the workspace: `D:\Videos\Global Assets\VIDEO_RULES.md`) | The one rulebook for every video (R188): each rule, its numbers, its R numbers, how it's checked. Briefs and reviews read it. |
| `D:\Videos\Global Assets\motion-library\CATALOG.md` | Every overlay asset and paid run: where it is, what made it, what it cost (R153, R154). |
| `docs/OVERLAY_BUILD_PLAN_qs1a.md` | The overlay build (R149 to R154): the swarm, the review project, the budget. |

## Hard limits (details in RULES.md)

- **Workshop folder is read-only** (R1). Copy into `pipeline/vendor/` with a provenance header.
- **Test account <YOUR_GITHUB_ACCOUNT>:** the whole exercise may be built now, class key included (R64, lifting
  R2's date). Create repos and codespaces, never delete them (R3).
- **Secrets** only through `pipeline.config.get_section()`; never written or printed; Claude never touches secret
  forms (R4).
- **YouTube uploads are private only** (R5). **Phase 0 uses no paid APIs** (R6).

## Commands

```
python -m pipeline.preflight                       # monitor, taskbar, topmost window, Edge window, zoom
python -m pipeline.capture.screen [clear|restore]  # R89: other windows off the capture monitor and back (s1 does it)
python -m pipeline.capture.obs                     # OBS dry check: switch to AIDV, report, switch back
python -m pipeline.s1 [--dry] [--steps=steps_csc13.json]   # record a take (silent, logged); --dry records nothing
                                                   # a step list with a `pause` stops before Part 5 (R70), tabs kept open
python -m pipeline.s1 --rehearse --steps=<ex>/steps_full.json [--to=<step id>] [--fast]   # every step off camera, no
                                                   # OBS: runs/_rehearse/<prefix>_<date>_NN/rehearse.json, a still a step
python tools/qs_cleanup.py snapshot|diff <file.json>   # R119: the account before a rehearsal or take; what it added
python tools/qs_cleanup.py delete <file.json> --names=A,B [--data-sources] [--yes]   # only what that run made (R245:
                                                   # --data-sources its data source too); orphans --name= --before= [--yes]
python -m pipeline.generated.explore runs/<run_id> inventory|try '<json>'|shot|reload   # Part 5, off camera
python -m pipeline.generated.merge runs/<run_id>   # runs/<id>/generated.json -> exercises/<ex>/steps_<tag>.json
python -m pipeline.s1 --resume=runs/<run_id>       # record the rest of a paused take, join the recordings, report
python -m pipeline.post.s1_report runs/<run_id>    # flashes -> calibration.json, raw.mp4, debug_boxes.mp4, stills/
python -m pipeline.post.s2_cursor runs/<run_id>    # cursor_track.json -> Remotion (remotion/) -> cursor.mp4
python -m pipeline.post.live runs/<run_id> <steps.json>   # live steps: Claude's session log + stills -> live_harvest.md (R33 drafts)
python -m pipeline.narration.build <steps.json>    # voice changed lines -> audio_cache/, exercises/<ex>/lines.json
python -m pipeline.narration.script <steps.json>   # the script for David's approval -> exercises/<ex>/script_<name>.md
python -m pipeline.edit.slides <ex> <opening|recap> <out_dir> --still=<png> [--render]   # R69 graphics -> <seq>.mp4
                                                   # out_dir runs/<id>/graphics: the export adds <run>_full.xml (splice)
python -m pipeline.edit.avatar <avatar_steps.json> runs/<run_id> [--no-render] [--rerender]   # R97: HeyGen (paid)
                                                   # -> graphics/opening.mp4, recap.mp4; cost in avatar/avatar.json
python -m pipeline.edit.avatar webapp <avatar_steps.json> runs/<run_id> opening|recap <render.webm> <upload.wav>
          --engine=avatar_v|avatar_iv [--open-head=0.58] [--notes=...]   # R244: register a HeyGen web-app render
                                                   # (no upload, no payment): its edges fixed for the web app's double
                                                   # premultiplication (alpha.PREMULTIPLIED); it becomes the stage's
python -m pipeline.edit.still_avatar register <avatar_steps.json> runs/<run_id>   # R245: the still avatar as the run's
                                                   # intro and outro "render" (the uploads built, nothing sent; a held
                                                   # transparent WebM each); make <render> --at=<s> / sheet: the still
                                                   # (D:\Videos\Global Assets\avatar\david_baldwin_still_1080p.png)
python -m pipeline.edit.s3 runs/<run_id> <steps.json> [--gap=cut|swipe|speed|all]   # plan + 540p proxy (on request, R73)
python -m pipeline.edit.linecheck runs/<run_id>  # R85: every line against the screen, before each export round
                                                   # (runs the measured checks too: captions, named, flicker, breaths;
                                                   # RapidOCR reads again where Windows OCR missed, R227)
python -m pipeline.edit.checks runs/<run_id> [--plan=<edit_plan.json>] [--only=...]   # R179-R187's checks alone
python -m pipeline.edit.premiere runs/<run_id> [--test-overview] [--no-render]   # Premiere XML + transparent layers (R61)
python -m pipeline.edit.ppro.project runs/<run_id>/premiere_rN [--frames=all]   # Premiere builds
                                                   # <run>_full.prproj there: binned, an editable title per cue (R102)
python -m pipeline.edit.ppro.bridge install|ping|start|eval "<jsx>"   # the AIDV panel: Premiere driven from Python
python -m pipeline.edit.ppro.markers <built.prproj> <markers.json>   # R106: "Round N check" markers on the full sequence
python -m pipeline.edit.ppro.framecheck <built.prproj> <out_dir> <tc>[,<tc>...]   # Premiere's own frames + sheet (R104-safe)
          [--exports[=h264|png|best]]              # R233, R240: the sheet from the round's H.264 export (made if missing;
                                                   # png and best use the PNG sequence too, made for them)
python -m pipeline.edit.ppro.exports export|where|clean <built.prproj> [--sequence=<name>] [--only=png]   # R240: an
                                                   # H.264 of each sequence in G:\aidv_scratch\exports (--only=png: the
                                                   # 10 fps PNG sequence instead); clean when the round's checks and
                                                   # reviews are done (in code: Exports(prproj).seq(name).frame/png/pull/scan)
python -m pipeline.edit.ppro.final runs/<run_id> <approved review folder> [--out=final_rN]   # R195, R203: avatar
                                                   # intro + the approved sequence nested + outro + logo outro
python -m pipeline.edit.ppro.final_quick runs/<run_id> <avatar steps.json> <approved review folder> --pip=<pip folder>
          --renders=<renders folder>|--still [--out=final_rN] [--no-premiere|--build-only|--mix-check|--scan|--frames|--cta-check]
                                                   # the Quick Series final (R231 to R243): the stage with the series
                                                   # card and the Remotion subscribe animation, the approved sequence
                                                   # nested, the Avatar IV renders in the oval (pip_render.oval_clips)
                                                   # or with --still the placement's still at every stay (R245), url.mov,
                                                   # the logo; --scan checks Premiere's H.264 export
python -m pipeline.edit.ppro.logo runs/<run_id> [--dry]   # R96, R204: the logo outro the stage and final use (the
                                                   # newest final's, else made from the dashboard's logo_outro)
python -m pipeline.edit.cta fit <avatar steps.json>   # the series card's words against its box (stage stops >2% over)
python -m pipeline.edit.stage runs/<run_id> <avatar steps.json> <approved review folder> [--out=stage_review_rN]
          [--stills-only] [--only=<jobs>] [--no-render] [--clips=<folder>] [--no-build] [--mix-check]
          [--no-premiere] [--build-only] [--pip=<pip review folder>]   # R205-R209: the avatar's stage + review;
                                                   # stage "design": "quick" is round 6's (R231, R232: the cityscape,
                                                   # the left third, the oval; --pip for its hand-over spots), "box" r5's
python -m pipeline.edit.pip runs/<run_id> <approved review folder> [--out=pip_review_rN] [--no-build|--build-only]
          [--keep-clear=exercises/<ex>/pip_keep_clear.json]   # R222, R224, R231, X6: the oval's place (pip_spans.json)
                                                   # + a Premiere review on a still (R229); keep-clear: what a line is
                                                   # about that no measure sees (Section A's list: always pass it)
python -m pipeline.edit.pip_render plan runs/<run_id>/<pip folder> <approved> --steps=<avatar steps.json>   # the
                                                   # Avatar IV render plan (R237); audio, verify: its uploads
python tools/overlay_review.py init runs/<run_id>/premiere_rN exercises/<ex>/overlays_review.json --out=overlays_review_r1
          --work=research/overlay_build/<prefix>   # an exercise's overlay round; then cards, check <key>, render,
                                                   # judge-input, xml [--require-picks], build, each --review=<folder>
                                                   # (none: Section A's round 4); overlay_build.py ... --review= too
python tools/ideas_run.py bundle <export> <steps.json> <out> [--about=<file>] [--plan-doc=<file>|none] [--rulebook]
python tools/regress_csc13.py --tag=<tag> --known=runs/_scratch_csc13_base/known_r204.json   # the CSC13 gate (G1)
python tools/compare_builds.py <before> <after> [--also <b> <a>] [--allow=<file>]   # two builds' JSON and XML (G2)
python tools/avatar_alpha_test.py runs/<run_id> <avatar steps.json> [--seconds=10]   # R207: a look's transparency (paid)
python tools/video_review.py frames|argon|gemini ...   # R191: outside models review a finished video, blind (costs)
python tools/rules_review.py <out_dir>             # R189: Astra and Argon review VIDEO_RULES.md, blind (costs)
python -m pipeline.edit.readback runs/<run_id> [--against=<edit_plan.json>]   # David's .prproj edits vs the export
python -m pipeline.privacy.report runs/<run_id>    # advisory privacy findings by video time (R56); an exercise
                                                   # pattern named like a built-in replaces it (the 12-digit one's "blur")
python -m pipeline.ml.cutout <art.png> [...]       # R227: BiRefNet cutout beside it (<name>_alpha.png); new art:
                                                   # tools/gen_image.py --cutout (--key-white: the flood-fill fallback)
python -m pipeline.edit.review runs/<run_id>       # proxy + timeline.html (on request only, R73)
python -m pipeline.edit.final runs/<run_id> [--approve]   # 1080p render + gate (unused for now: the final is David's Premiere export, R73)
python -m pipeline.publish.youtube <video.mp4> --title="..." [--description="..."]   # private upload (R5)
```

The Edge window must be running with CDP on port 9333 (the workshop's `automation\start_browser.ps1`).
