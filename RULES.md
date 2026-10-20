# Rules: David's decisions, one home each

Every rule the pipeline follows lives here once, numbered. Other files point to it ("see R23") and never restate it.
Numbers (sizes, times, colours) live in `exercises/<ex>/edit_settings.json` or `voice.json`; a rule names the setting
that enforces it. Where two sources disagreed, the newest dated decision won; the losers are listed at the end, with
the conflicts still open for David.

Numbers are never reused or renumbered; a new rule takes the next free number in whichever group fits.
Each entry: **rule**, then *who and when*, then *enforced by*. "Not built" means the rule stands but no code does it
yet. David's words in quotes are verbatim, typos included.

## Hard limits

- **R1 The workshop folder is read-only.** `<DOCUMENTS_DIR>\Learning-David-Pc\Workshops\2026-10-08_<CLIENT>`.
  Code from it is copied into `pipeline/vendor/` with a provenance header (source path, copy date, changes), never
  imported or edited. *Brief constraint, 2026-10-05.* *Enforced by:* `pipeline/vendor/` headers.
- **R2 Test account <YOUR_GITHUB_ACCOUNT>.** The account the takes run in. Its date limit (S6 and later after
  2026-10-08; send nothing to Claude, change no repo) is lifted by R64. *David, 2026-10-06.*
- **R64 The whole exercise starts now, before the Oct 8 workshop.** Takes may create repos and codespaces, send
  prompts to Claude Code, and use or change the existing workshop repo and codespace. Their codespaces use the
  workshop's class key (the `ANTHROPIC_API_KEY` Codespace secret). The exercise doc and template are final. The first
  target is a rough cut of all six parts: Andrew's voice, no intro, outro or avatar. R3 (create, never delete) and R4
  (secrets) still hold. *David, 2026-10-06; he accepted the risk to the workshop setup and the class key's budget.*
  Claude still prefers fresh take repos (R19) and says so before a take touches the workshop codespace. David
  deletes the test account's repo and codespace before the class (2026-10-07).
- **R3 Create, never delete.** The automation may create repos (`my-agentic-workshop-take<NN>`) and codespaces. It
  never deletes them; David deletes old takes in batches. *David, 2026-10-05.* The full take uses a fresh repo named
  exactly `my-agentic-workshop`, so p1.02's line is true; test takes keep the `-take<NN>` names. David deleted the old
  test repo and codespace on 2026-10-07. *Claude's recommendation, accepted by David, 2026-10-07.*
- **R4 Secrets.** Read only through `pipeline.config.get_section()` (AWS Secrets Manager `giddyup/config`); never
  written to a file in this project or printed. Claude never touches secret forms, never types passwords or keys into
  a page, and never screenshots a form that holds a real key value. *David, 2026-10-05/06.* *Enforced by:*
  `pipeline/config.py`.
- **R5 YouTube: private uploads only.** The pipeline may upload, private only. The OAuth client is in `giddyup/config`
  → `youtube_oauth`, the token at `~\.giddyup\youtube_token.json`; both are shared with GiddyUpSocial
  and never go back under OneDrive. Public release is David's, by hand in YouTube Studio. *David, 2026-10-06.*
  *Enforced by:* `pipeline/publish/youtube.py` (`PRIVACY = "private"`, checked after upload).
  **Exception, at David's word:** Section A's tutorial (<UNLISTED_VIDEO_URL>) and its highlight reel go to
  **unlisted** once uploaded; Claude set it through the API. Uploads still go up private first. *David, 2026-10-19*
  ("Please change from private to unlisted.").
- **R6 Phase 0 uses no paid APIs.** Narration is Microsoft's Andrew through edge-tts; ElevenLabs arrives in Phase 1;
  no HeyGen avatar in Phase 0. *David, 2026-10-06.* *Enforced by:* `voice.json` `engine`.
- **R7 The workshop Edge profile is never signed in to Microsoft,** or personal data would appear on camera. It stays
  signed in to GitHub as <YOUR_GITHUB_ACCOUNT>. *David, 2026-10-06.* *Enforced by:* pre-flight profile check (SPEC §9).
- **R8 The workshop browser is shared.** Claude asks before taking over a window David may be rehearsing in and never
  closes his tabs. *David, 2026-10-06.*
- **R9 Skill installs come from official repositories only,** into `.claude/skills/`, with versions in
  `skills-lock.json`. *2026-10-05.*
- **R10 Machine-wide file searches use es.exe** (Everything), not recursive `Get-ChildItem`. *David.*
- **R11 The published Quick Series videos stay unchanged.** They are a style source only. *David, 2026-10-06.*
- **R60 The pipeline makes the editing judgement calls; David does the final review.** The goal is a video he can
  publish with minimal further editing. Where a rule leaves a choice (a tight spot, a cut or a speed-up, where a
  caption goes), the pipeline decides from what is on screen, not by waiting for a note. David's notes and edits are
  exceptions, and each one is a lesson: Claude proposes the setting or rule change it implies. *David, 2026-10-06.*
- **R12 The audience is the public, standalone viewer,** not the workshop cohort. No "class key" or "your
  instructor"; say "your Anthropic API key" and point to a separate Setup video. *David, 2026-10-05.*
- **R58 The test account's GitHub CLI sign-in is kept** after the workshop for video work
  (`%USERPROFILE%\.workshop\gh`, `GH_DIR` in `pipeline/config.py`), overriding the workshop's post-workshop
  cleanup. *David, 2026-10-05.*

## Capture and takes

- **R13 OBS records the right-hand monitor.** Display Capture of DISPLAY1 (x = 1920), which has no taskbar, in the
  pipeline's own `AIDV` profile and scene collection; David's `Untitled` ones are restored after every take, even a
  failed one. *David, 2026-10-06 (slice S1).* *Enforced by:* `pipeline/capture/obs.py`; pre-flight (work area equals
  bounds).
- **R14 Each take opens its own Edge window,** maximized on that monitor, so the recorded tab strip shows only the
  take's tabs. Nothing else may cover the monitor. *S1, 2026-10-06.* *Enforced by:* pre-flight (topmost window).
- **R15 The real pointer stays off the capture monitor** during a take, and OBS "Capture Cursor" is off. *David,
  2026-10-06.* *Enforced by:* pre-flight (the pointer's position, checked since 2026-10-07: OBS's setting did not keep
  it out of p5_take01/02, GOTCHAS); `obs.py` (`capture_cursor: False`). The sliver at the right edge of p5_take02's
  full-frame shots is accepted as it is, with no blur (*David, 2026-10-07: "It's fine"*).
- **R89 The pipeline clears the capture monitor itself.** Before each recording (the first and, after the Part 5
  pause, the second) every other window that covers the capture monitor moves to the left-hand monitor, keeping its
  state, and the real pointer moves to the primary monitor (R15); the windows come back after each recording.
  *David, 2026-10-07 (VS Code, Snagit and his Edge window were moved by hand for p5_take01/02).* *Enforced by:*
  `pipeline/capture/screen.py` (`clear`, `restore`, `park_pointer`; `runs/_moved_windows.json` lists what is moved
  until it is back), called by `pipeline.s1` and its `--resume`.
- **R16 Edge toolbar items are hidden in recordings:** Copilot, Favorites, split screen, extensions, the profile
  notification dot; also the favourites bar, sidebar, translation offers and password prompts. *David, 2026-10-06.*
  *Enforced by:* pre-flight checks Copilot and Favorites (`HIDDEN_TOOLBAR`); the rest is not checked yet.
- **R17 Cursor, zoom, marks and captions are drawn in the edit,** never baked into the recording, so style and timing
  change without a retake. Tools that draw a cursor into the recording are ruled out. *Brief decision 10; David,
  2026-10-06.* *Enforced by:* Remotion `EditPass`.
- **R18 The recorder over-records; pacing is made in the edit.** Capture is silent; a step records until its line's
  length plus a pad, and after a wait longer than the cut threshold it records a full line's length after the result
  (the end-freeze fix). *Brief decision 9; fix 2026-10-06.* *Enforced by:* `runner.py` `NARRATION_PAD`,
  `LONG_WAIT_S`.
- **R19 One exercise, one take.** Parts are never spliced from different takes (the codespace name shows in the tab
  and URL). A failed take starts again on a fresh take repo. *Workshop rule, 2026-10-05.* For the full take, R92.
- **R92 A failed full take starts again on a new codespace in the same repo** when the take left the repo untouched
  (nothing committed or pushed): the repo must be named exactly `my-agentic-workshop` (R3), its API key secret is
  already ticked, and a new codespace starts as clean as a fresh repo's. The stopped codespace stays until David
  deletes it (R3). *David, 2026-10-08 (full_take01 stopped at p4.12).*
- **R20 Retakes are a last resort.** Fix what you can in the edit by cutting, stretching or freezing: re-voiced lines,
  new sentences, pauses and pacing are edit changes (a re-voiced line slides onto the existing take). Retake only when
  the recorded action itself is wrong or missing, and before proposing one, say why the edit can't do it. *David,
  2026-10-06.* *Enforced by:* `plan.py` (live-step anchor).
- **R21 Tool versions are pinned and logged in every run header;** the edit warns on an unknown version. *Brief
  deviation 12, 2026-10-05.* *Enforced by:* run-log header (SPEC §5).

## Narration

- **R22 The Phase 0 voice is Andrew (`en-US-AndrewNeural`) at −15%.** *David approved, 2026-10-06.* *Enforced by:*
  `voice.json` `rate`.
- **R94 The Phase 1 voice is David's ElevenLabs clone "David Teacher"** (voice `<ELEVENLABS_VOICE_ID>`), called through
  ElevenLabs' own API (`/v1/text-to-speech/{voice}/with-timestamps`), not OpenRouter: OpenRouter's ElevenLabs route
  offers only preset voices and returns no timestamps. The model is `eleven_multilingual_v2` until a pronunciation
  test says otherwise. The account's pay-as-you-go plan voices the clone; its `can_use_professional_voice_cloning:
  False` only blocks training new clones. ElevenLabs and HeyGen calls are approved for Phase 1 work; report the
  credits used. *David, 2026-10-12 ("sounds fine," on `runs/_voice_test_20261012/`).* *Enforced by:*
  `engines.ElevenLabs`, chosen by a voice file: `voice_clone.json` for the CSC13 test (R98); `voice.json` is still
  Andrew's.
- **R99 Only what changed is voiced, and paid for.** A line is voiced again only when its own words or the voice
  change. Adding or editing a neighbouring line doesn't re-voice it: the neighbours go to ElevenLabs as context
  (`previous_text`, `next_text`), which isn't billed. This matches the ElevenLabs web app, where only the changed
  section is charged. *David, 2026-10-12.* Measured that day: adding p2.10a2 (88 characters, with about 200 characters
  of context) voiced that line alone and logged 19 units, the same 0.22 units per character as every earlier call.
  *Enforced by:* `build.cache_key()` (a line's own spoken text and the voice); the clone's earlier clips were re-keyed,
  not re-voiced.
- **R103 Narration gets a click and pop pass before the edit, every time,** as David's own recordings go through
  Audition's click removal before he ever hears a pop. Don't wait for him to find one. *David, 2026-10-13* (round 3's
  pops were gone; he wants the pass to be standing, not a fix after the fact). *Enforced by:*
  `pipeline.narration.clean` (built 2026-10-13): edge fades, ElevenLabs' stitching bursts silenced, and clicks inside
  the speech found by its own detector (a spike above 4 kHz, `CLICK_DB` 31 dB over its neighbourhood: the clone's
  sharpest consonant measures 29.2) and repaired by ffmpeg's `adeclick` within 2 ms of each click only (run on whole
  clips it rewrote the plosives). The plan's notes list each repair; a click left after it is a warning. The CSC13
  test had one (p2.10d at 7.43 s, 42 samples). Cleaned clips are named `<key>.c<VERSION>.wav`, so a new pass never
  changes audio under a saved project (R61). Audition can't run unattended; iZotope RX 12 (De-click) is installed but
  its licence is unchecked.
- **R23 Announce, then act.** The pointer starts moving on `cue_word` (the start of the phrase that says where), and
  the click lands 0.35 s after `click_word` (the target's name) starts. The edit warns when a click falls outside the
  window after its name. *David, 2026-10-06 (after S3).* *Enforced by:* `runner.py` `CLICK_AFTER_NAME`;
  `cuts.click_after_name_max_s`; `pacing.move_after_cue_s`.
- **R24 Confirm the result out loud.** After a click, a short clause says what changed, so the result is narrated
  while it appears (announce, act, confirm). *David's style, NARRATION §2; 2026-10-06.*
- **R25 No dead air.** Think of a radio talk show. The gap between lines is `pacing.gap_between_lines` (0.4 s). It
  runs longer, up to 2 s, only while something worth watching happens on screen, which the edit can measure as the
  picture changing during the gap. A line ending in a comma runs straight into the next ("Open the data folder, and
  select…"). Close gaps in the narration (a clause confirming the result), not with silence; the edit cuts silent
  footage to fit and warns about gaps it can't close. 2 s is a ceiling, not an allowance. *David, 2026-10-06 (his
  Premiere edits cut 1.5 s and 2.0 s gaps the planner had left).* *Enforced by:* `pacing.gap_between_lines`,
  `max_silence_s`, `activity_min_pct` (the picture-change test, `pipeline/edit/activity.py`), `comma_pause_s` (the
  silence between the words of a run-on); `plan.py` also takes a step's result from the picture (the runner logs it
  up to 1.1 s late) and cuts still footage off the end of the previous step when a line would start late. On take 05
  this reproduces both of his gap edits exactly. The ceiling holds over sped-up typing too: 3.3 s of silence while the
  dashboard prompt was typed was too long (David, 2026-10-12, CSC13 test). Such a gap is closed with a line that plays
  during the step's action (a line-only step with `during`), and the line check reports any gap over the ceiling,
  moving picture or not.
- **R26 On-screen labels get a spoken pause before them** ("under - By repository"). Every label named in a line is
  listed in `narration.labels`; the spoken text gets the voice's `label_pause` (Andrew " - ", 0.43 s; ElevenLabs a
  `<break>`). Captions are unchanged. *David, 2026-10-06.* *Enforced by:* `voice.json` `label_pause`;
  `pipeline/narration/build.py`.
- **R27 Humor: a little here and there.** Superseded by R65 (no humor).
- **R28 A click line says where, what, and (first time) why:** the place relative to something already seen, the
  exact on-screen label, and on first mention its purpose. *NARRATION §3, 2026-10-06.*
- **R29 Lines are written for the ear.** Sentences of about 12 words, none over about 25. Literal values get a spoken
  form with commas as pacing marks. Anything that varies per take (names, IDs) is explained, not just read.
  *NARRATION §7–§9, 2026-10-06.*
- **R30 Episode frame:** promise → why it matters → roadmap → "So, let's get started." → walk-through → "Let's
  recap." (mirroring the roadmap) → the standard call to action, word for word (NARRATION §1). *2026-10-06.*
- **R31 Display text and spoken text are separate.** Captions and the approved script use the display text; the voice
  gets the spoken text, respelled locally before sending. Do whatever helps the voice get it right (escalation in SPEC
  §5.5). *David, brief deviation 3, 2026-10-06.* *Enforced by:* `pronunciation.json`,
  `exercises/pronunciation_common.json`; a sentence that ends on a respelled term gets an ellipsis in the spoken text, because edge-tts
  reads "dev." or "lib." as an abbreviation and runs on (GOTCHAS); the build checks every sentence-end pause (R85).
- **R32 Neighbouring lines are sent with each line** on any engine that supports request stitching; editing one line
  regenerates it and its two neighbours. *David, 2026-10-06.* Not built (ElevenLabs, Phase 1).
  **Amended by R99 (2026-10-12):** the neighbours go to ElevenLabs as unbilled context only; editing a line re-voices
  that line alone, never its neighbours (built: `build.cache_key()`).
- **R62 A beat where the narration changes mode.** At a sentence break inside a line where the narration switches
  between explaining and instructing, the picture holds and the voice pauses about 0.5 s longer than its own sentence
  pause. *David, 2026-10-06, from his Premiere edits:* +0.6 s at "…lists the files in your repository. | Open the data
  folder," (explain → instruct) and +0.4 s at "…and select monthlysummary.csv. | The first line lists…" (instruct →
  explain). He called it a feel; refine the number as more of his edits come in. *Enforced by:*
  `pacing.mode_switch_beat_s` (0.5; 0 turns it off), `pipeline/edit/sentences.py` (instruct = a clause starting with
  an imperative verb), `plan.py` (splits the line, holds the picture when the beat falls after the cue word). See the
  *David confirmed, 2026-10-06:* a beat at every explain/instruct switch, as written. On take 05 that is six
  beats where his own edit had two (72.39 s against his 70.30 s); the rule wins over that edit.
- **R129 A little humor comes back, paired with overlays.** An occasional light aside, carried by an overlay or a
  short motion graphic, as in David's Quick Series (03-QuickArch03, 04-Knowledge_Bases04 in
  `D:\Videos\QuickSeries\AmazonQuick.prproj`); the narration may be rewritten to set them up. How often and where is
  settled in the overlay plan (R130). *David, 2026-10-14* ("several of those things are attached to a bit of humor,
  which is why I was thinking we might do a bit of rewriting of the text"; asked, he chose to revisit R65). Replaces
  R65.
- **R65 No humor. The script is straight.** Superseded by R129 (2026-10-14). No asides, jokes or wry lines, and no drop-in clips or gag sound effects.
  Explanation, contrast and warnings stay, in plain words. *David, 2026-10-07, on the whole-exercise draft.* Replaces
  R27.
- **R66 The narration matches the tone and voice of the Quick Series** (ep02 Interface, ep03 Architecture, ep04
  Knowledge Bases; scripts in `D:\Videos\QuickSeries`). How that voice works is in `research/style_study/NARRATION.md`:
  the demonstrator in the first person ("I'll click …"), "we" and "let's" for the plan, "you" for what the viewer sees
  or does on their own, complete plain sentences. *David, 2026-10-07.*
- **R67 Prompts may be typed instead of pasted.** A long prompt is typed at natural speed, and the edit speeds the
  typing up or cuts its middle, so the take doesn't depend on pasting into the Claude panel. The narration says "I'll
  enter this prompt"; the description carries every prompt for viewers to copy. *David, 2026-10-07.* *Enforced by:*
  `typing_mode: full` in steps; the speed-up is not built (S6, with `cuts.speed_max_s`, R37).
- **R68 This exercise video is not published,** so its script has no call to action; R30's frame ends at the recap.
  *David, 2026-10-07.* The same holds for the remaining videos (Cleaning Data, Combining Weather and Flight Data,
  Document Your Project): no call to action. *David, 2026-10-07.* **Amended by R203 (2026-10-16):** what decides the
  call to action is whether David wants it in the video, not whether the video is published.
- **R69 The opening and the recap have motion graphics on screen,** never a bare browser: text slides in Remotion,
  timed to the narration, over a still of the finished dashboard taken from the take. *David, 2026-10-07 ("we need some
  motion graphics"; the dashboard still is the pipeline's job).* *Enforced by:* `exercises/<ex>/slides.json` (the on-screen text),
  `pipeline.edit.slides` and `remotion/src/Slides.tsx` (David's FullScreenTitle, BulletPanel, ComparisonTable and ep02
  roadmap looks, ported); the runner saves the still at the step marked `still`. The splice: `pipeline.edit.premiere`
  writes `<run>_full.xml` (opening + the camera sequence + recap, R34's dissolves) when `runs/<id>/graphics/` holds
  them.
- **R70 The pipeline picks Part 5 itself; David reviews it at the proxy.** No approval before recording. The take
  stops recording after Part 4 (the dashboard open) and resumes for Parts 5 and 6 in the same codespace: two recordings
  of one take (R19), joined at the Part 4/5 section boundary under R34's dissolve. In between, with capture off, Claude
  explores this take's dashboard and picks 3 to 4 interactions and one defect that is (1) visible on screen within
  seconds, (2) describable in one sentence (what I clicked, what I saw, what I expected: the doc's feedback pattern),
  (3) plausibly fixed in one round, and (4) shown fixed by repeating the same click. The doc's own example (the map
  zoomed in until it is almost blank) is preferred when it occurs. The dashboard is reloaded before recording resumes.
  If the reload still shows the defect, a second round of feedback follows on camera; after two rounds the take stops
  and asks David. *David, 2026-10-07.* *Enforced by:* the steps' `pause` (`pipeline.s1` stops recording and leaves the
  take's tabs open; `--resume` reloads the dashboard and records the rest); `pipeline.generated.explore` (the
  off-camera look: controls, tries, screenshots) and `generated.json`, which `pipeline.generated.merge` folds into
  `steps_<run tag>.json`; the second round as conditional steps (`only_if.eval`, `same_as`) and a stop at p5.16a
  (`otherwise: stop_take`); `pipeline.post.join` (one recording, one clock) and the plan's cut at the join.
- **R86 Finish the dashboard video first; then the next exercises, which chain.** The dashboard video is completed
  (Part 5, Part 6, the graphics splice, one full take) before any other exercise. The next exercises are Cleaning
  Data, Combining Weather and Flight Data, and Document Your Project, in that order, and they chain: each starts from
  the repo the previous exercise left, the dashboard exercise first. So their takes run in order on the same repo
  (R19 per exercise), and a script names the files the earlier exercises produced. *David, 2026-10-07.* The Setup
  video R12 points to is not on the list yet.
- **R71 With no visible defect, Part 5 asks for an improvement** in the doc's style ("Add a comparison of taxi-in and
  taxi-out times."), and the lines that promise a problem switch to their approved `improvement` variants (p5.15c,
  p5.15f, p7.02, and the roadmap's on-screen "Explore and request a change"). *David, 2026-10-07.* *Enforced by:*
  `narration.variants` in steps, `variants` in `slides.json`; `generated.json` `mode: improvement` switches the steps'
  lines (`pipeline.generated.merge`); the slides' variant is chosen at the graphics splice (not built).
- **R87 Every feedback prompt ends "Then restart the dashboard so I can check it."**, every round, every take, though
  the doc's pattern is only "what I clicked, what I saw, what I expected". Claude won't stop a server it didn't start
  (p5_take01), and the reload must show the new version. *David, 2026-10-07.* *Enforced by:*
  `pipeline.generated.merge` (`FEEDBACK_END`, added to any `feedback_prompt*` variable that lacks it).
- **R88 The opening and recap still is the dashboard after the fix,** not as it first opened. *David, 2026-10-07.*
  *Enforced by:* `still` on p5.15h (the repeat of the defect's click) in the steps; `pipeline.generated.merge` gives
  a second round's repeat of that click the same `still`, and the later one overwrites the first.
- **R74 The dashboard "may or may not" open on its own; the video shows where to click if it doesn't.** The template
  forwards port 8050 with `onAutoForward: openBrowser`, so Codespaces may open the dashboard by itself while Claude
  builds. p4.13 says so, then shows the Ports tab and the globe as the way to open it. *David, 2026-10-07 (replacing
  the doc's "it will likely not open").* *Enforced by:* p4.13a's text; the runner closes tabs that open by themselves
  during a live wait (`close_stray_tab`), so the take always shows the Ports route.
- **R75 Narrate only what the viewer can see, and point to it.** A line that names something on screen (a file, a
  reply, a form, CLAUDE.md) gets a mark or arrow on it. Nothing comes from the session log alone: if Claude did it
  but the screen doesn't show it (a skill loaded, a file written, "it tested the code"), show it, put it in an
  overlay, or speak in general terms ("Claude may install tools or write code to do its work"), or leave it out.
  *David, 2026-10-07, on s7_take06 (2:14 "Claude checks CLAUDE.md" with no mark; 4:28 dataviz and app.py not on
  screen; 4:47 "tests it" not shown).*
- **R76 Claude's choices are one possibility; say so.** LLMs are non-deterministic: live lines frame what Claude did
  as this run ("In this case, ...", "Claude may suggest ..."), and the reply walk-through mentions things Claude
  *likely* suggests, as examples. *David, 2026-10-07.*
- **R77 Text the viewer must read is shown whole.** When it is cut off on screen (a long prompt in the message box
  with a scrollbar, a reply in the narrow panel), an overlay shows the whole text and the highlights go on the
  overlay, not on half-hidden screen text. Widening the side panel is the other option (harder to automate).
  *David, 2026-10-07 (2:26: the rule marks drawn where the prompt had scrolled out of the box; 3:17: the reply
  scroll shows too little to follow).*
- **R124 Every on-screen thing a line names gets its mark, panes and options included.** R75 holds for overview lines
  too ("The Data pane on the left lists our fields"): Claude doesn't trim a draft's marks to save time. *David,
  2026-10-14, Section A round 1: 00:08:38:22 to 00:08:59:20 ("Interactive sheet" and "Pixel-Perfect report" named but
  not pointed out), 00:09:02:21 (the Data pane named but not shown: "point it out with a rectangle or an arrow").*
  *Enforced by:* the steps' marks; the camera keeps each one in title-safe (R123). *David approved round 3's marks,
  2026-10-14.*
- **R132 Section A's lines are fine for now, not final.** A draft line heard in a round and left alone isn't approved:
  the lines may change as overlays are layered on (R130). *David, 2026-10-14* ("They are ok for now but I really
  don't know how things will work as we begin to layer on overlays").
- **R78 Don't talk about something already gone.** A line refers to what is on screen now: say it before it is
  dismissed (the question form before Escape), or not at all. *David, 2026-10-07 (4:09: "I could answer each of
  Claude's questions" after the form was closed).*
- **R79 Every overlay is legible on any background,** light ones included (the title card at 4:28 was hard to read
  over the light IDE). *David, 2026-10-07.*
- **R80 An overlay item says what its sentence says.** Each item on a list overlay sums up the sentence spoken while
  it appears, at that sentence's level: a sentence about the shape of the reply gets "Shape of the reply: findings,
  options, and questions", not the questions themselves. The item appears on the first word of what it sums up
  ("findings", not "questions"). *David, 2026-10-07, round 2 (3:53; in Premiere he moved the last bullet 2 s earlier,
  onto "findings").* *Enforced by:* the item's `at_word`; the line check's item/sentence table (R85).
- **R81 On screen means readable at that moment.** A line names something as on screen only if the viewer can read
  it in the frame as it is named. A question behind a tab whose title is cut to "Aud…", text scrolled out of a box, or
  a row that appears later doesn't count: leave it out, or say where it is. Sharpens R75. *David, 2026-10-07, round 2
  (4:00: the form showed only the layout question; "how to handle 2020" and "who the audience is" sat behind its
  tabs).* *Enforced by:* the line check (R85), OCR of the frame at each named thing's word.
- **R91 Claude may install a headless browser's system libraries on camera.** When Claude asks to run
  `sudo ... playwright install-deps` (to screenshot its own dashboard and check the layout), the runner clicks Yes
  where the viewer sees it, the prompt plays at 1x (R39), and a live line says what it is, as this run's choice (R76).
  Any other sudo, or anything risky chained onto it, still stops the take. *David, 2026-10-08 (full_take01 stopped
  on it in p4.12).* *Enforced by:* `allow` in the step list (every live wait), `runner.py` (an allow removes only what
  it matches from the prompt, and whatever is still RISKY stops the take).
- **R33 Live-step narration is written after the run** from the Claude log and stills; David approves it. *Brief,
  2026-10-05.* *Enforced by:* `pipeline.post.live` (the harvest Claude drafts from); lines go in
  as `draft` until David approves (S7).
- **R93 No em dashes.** Nothing the pipeline writes for the viewer or for David's approval uses an em dash (—): narration
  (display and spoken text), captions, slides, overlays, title cards, scripts and video descriptions. A spaced en dash
  or a double hyphen standing in for one counts too. Use a comma, a colon, a period or parentheses instead. The em
  dash reads as machine-written. *David, 2026-10-12.* *Enforced by:* `pipeline.narration.build` `r93()` (stops the
  build before anything is voiced) and the line check (R85: any text in the plan). Slides and video descriptions
  aren't checked yet. The exercises' step lists have none as of 2026-10-12.
- **R181 No double breaths.** Two inhales within about 1.5 s with no speech between them (a beat splitting a line, two
  lines butted together, a cut) lose the earlier one: it is muted, the words untouched. Single breaths stay. A beat
  (R62) never splits a breath: it is placed at a word's end, from the word timings. *David, 2026-10-15, on round 7*
  (00:01:15:06 to 00:01:16:00: p1.03's beat split the audio at 6.6 s, inside an inhale, so half a breath, a 0.5 s
  pause and the rest were heard; "Those should be muted without cutting out the words. I'm not saying that every
  breath should be muted. But double breaths are a problem"). *Enforced by:* `pipeline/narration/breaths.py` (inhales
  between words: 17 to 42 dB under the clip's speech, out of near-silence, centred near 2 kHz; one with a catch under
  0.25 s is one breath), `plan.line_beats` (a beat in the first silence after the earlier word, `breaths.beat_point`),
  `plan.mute_double_breaths` (after the loudness pass), the check `pipeline.edit.checks` breaths. Built 2026-10-15
  (round 8): it found note 2 and three more split breaths on round 7; none on round 8.

## Cuts and pacing

- **R34 Hard cuts between pieces of a recording;** no crossfade. A 1.0 s dissolve appears only at a section
  boundary. *David's style, adopted 2026-10-06.* *Enforced by:* `cuts.crossfade_frames: 0`. The section dissolve is
  built only at a paused take's join (R70, `cuts.section_transition`, listed for Premiere; EditPass shows a hard
  cut). R83 adds the one other place a transition goes: a cut of Claude's working time. The dissolve into the recap
  graphics is as long as the recap's still lead-in allows (0.8 s); *David, 2026-10-07: "0.8 s is fine"*, so the
  approved recap timing stays.
- **R35 Waits are cut, never shown.** A wait that would leave more than 2 s before the next line can start (R25) is
  cut or sped up; both are timing tools, chosen per case. The default gap treatment is `cut` (David's pick in S3).
  *David, 2026-10-06.* *Enforced by:* `cuts.gap_treatment`, `cuts.cut_above_s`.
- **R36 Freeze-holds are normal;** the edit warns only above a long hold. *David's style, adopted 2026-10-06.*
  *Enforced by:* `cuts.hold_warn_s`.
- **R37 Playback is 1.0x by default.** Speed-ups are for timing: typing, and waits that aren't cut (R35). Sped-up
  footage carries no on-screen speed label ("×4"), time-lapses included. *Brief; David, 2026-10-06.* *Enforced by:*
  `cuts.speed_min`, `cuts.speed_max_s`; `EditPass` draws no badge.
- **R38 A cut never splits a narration line;** the line keeps playing over the picture after the cut. *SPEC §6.4,
  2026-10-05.* *Enforced by:* `plan.py`.
- **R39 Live waits:** under 20 s real time with the cut rules; 20 s to 3 min time-lapsed to 6 to 8 s; over 3 min a
  3 s title card ("Claude is building: about N minutes") then a 6 to 10 s time-lapse. Permission prompts and
  David-approved error-then-fix moments stay at 1×. *Brief decision 3, deviation 10, 2026-10-06.* *Enforced by:* `timelapse` in `edit_settings.json`,
  `plan.py` `Timeline.timelapse` (prompts kept at 1x from the run log); error-then-fix moments are not picked yet.
- **R82 A part boundary pauses about 1.2 s between lines, not 1.9 s.** The extra pause at a part change is 0.8 s on
  top of the 0.4 s gap (it was an unreviewed 1.5 s SPEC default). *David, 2026-10-07, round 2: he cut two of the three
  part-boundary gaps, all over a still picture, 1.90 → 1.07 s (Part 2/3) and 1.90 → 1.30 s (Part 3/4); 1.2 s is
  their mean.* *Enforced by:* `pacing.pause_at_part_boundary`.
- **R83 A cut that skips Claude's working time gets a visible transition:** a 1.0 s Page Peel (David's ep04 look:
  send, page peel, the finished answer; another visible transition would do). It tells the viewer time has passed.
  Only cuts made while Claude is working (between a prompt's send and Claude going idle) get one; page-load and other
  cuts stay hard (R34), and a time-lapse needs none (its speed shows the time). *David, 2026-10-07, round 2 (4:39: he
  put a Page Peel where he had cut dead air mid-build; "a visible transition marks skipped time").* *Enforced by:*
  `cuts.work_cut_transition` (type and length), `plan.py` (`transitions` in the plan: one at each prompt, at the last cut
  of Claude's work before its result, preferring a cut clear of marks and cursor gestures, else flagged; *David,
  2026-10-07: a transition at each prompt, and he keeps the ones he wants*), `pipeline.edit.premiere`
  (transition items on the nest's Recording track at the cut, where the skipped footage is the outgoing piece's
  handle; Premiere imports them as a Cross Dissolve (Legacy), GOTCHAS, and David adds the Page Peel by hand for now).
  R90 drops the transition where the skipped time is too short to matter. **Amended by R105:** the pipeline places the
  Page Peel in Premiere; David no longer adds it by hand.
- **R105 The pipeline puts the work-cut transitions in place in Premiere; David never fixes them by hand.** R83's
  transition is Premiere 26's new Page Peel, or another still-supported transition as plain to the viewer ("a slap
  in the face that gets noticed"); never the Page Peel Premiere 26 retired, which the XML import maps ours to (it
  arrives as a dissolve). *David, 2026-10-13* ("I'd rather not have to manually fix transitions. I'm ok with using
  the new page peel"). *Enforced by:* `cuts.work_cut_transition.in_premiere`; `pipeline.edit.premiere` writes
  hard cuts and `transitions.json`, and `pipeline.edit.ppro.project` places each one with QE's `addTransition`
  and reads it back (`aidvTransitions`; tested 2026-10-13 on a scratch build: placed 25.0 to 26.0 s, rendered).
- **R90 No transition for a prompt whose cuts all skip under 1 s** of Claude's work: such a cut hides no real time.
  A prompt with any longer cut keeps its one transition (R83). *David, 2026-10-07 (four of p5_take02's five Page
  Peels skipped 0.24 to 0.60 s; s7_take06 had one at 0.31 s).* *Enforced by:* `cuts.work_cut_transition.min_skip_s`
  (1.0), `plan.py` (a note names each prompt left without one).

## Camera

- **R40 Full frame while a navigation's URL or new page matters,** so the URL and tabs are visible. *David,
  2026-10-06 (framing decision and S4 notes).* *Enforced by:* `camera.py` (navigate and new-tab steps),
  `zoom.min_full_s`.
- **R41 Then zoom in at once** on the coming work, as soon as the full-frame need ends, not waiting for the next line.
  *David's S4 notes, 2026-10-06.* *Enforced by:* `camera.py`, `zoom.max_early_s`.
- **R42 The camera rests at 1.35x and goes up to 2x only for tight spots;** a little softness is fine at 2x. A tight
  spot is chosen by the pipeline (R60: where the text in focus would be too small on a phone; not built yet) or by a
  note, which sets the step's `zoom.max` in steps.json. *David,
  2026-10-06 (replaces the 1.5x cap).* *Enforced by:* `zoom.level` (rest), `zoom.max` (cap), `zoom.soft_factor`;
  step `zoom.max`.
- **R72 The Claude Code panel steps zoom to 2x** (`zoom.max: 2` on each step whose work is in the panel): its text is
  too small to read at the 1.35x rest. *David, 2026-10-07, after the S6 test take.* *Enforced by:* step `zoom.max`
  (R42); set in the steps next session.
- **R43 A beat outside the view: ease out slightly** if a wide mark still fits, otherwise **pan**. Nearby work is
  panned to, not zoomed out of and back in. *David's S4 notes, 2026-10-06.* *Enforced by:* `zoom.refit_min`,
  `zoom.pan_s`.
- **R44 Zoom out at a click that opens a new tab,** on the cut. *David's S4 notes, 2026-10-06.* *Enforced by:*
  `camera.py`, `cuts.ring_hold_s`.
- **R123 What the narration refers to sits inside title-safe, and whole.** The screen not fitting the frame at the
  1.35x rest is fine, but anything a line refers to (a mark, a click target, a dialog, a panel, a menu) sits inside
  the title-safe area of the zoomed view, never against its edge: 96 px from the left and right of the output frame,
  54 px from the top, and 100 px from the bottom, where captions and YouTube's progress bar sit. When a dialog, panel
  or menu is referred to, the whole of it fits inside those margins; if it can't at 1.35x, the camera zooms out, to
  full frame if needed, rather than crop it. The camera follows what a step opens (the Windows Open dialog, a page
  modal, a menu) until it closes. Where keeping the browser chrome out would crowd a box against the top, the chrome
  shows whole instead. The pipeline frames this itself: David doesn't fix camera keyframes. Things at the screen's own
  edge (the Data pane at x 8) can't get the margin; the camera goes as far as the frame allows. *David, 2026-10-14,
  Section A round 1* (00:00:43:06 the Open dialog crowded at the top; 00:01:10:21 part of a dialog; 00:06:39:07 the
  dataset name out of view; 00:09:02:21 the Data pane out of view; "Make the pipeline do that itself"; he accepted
  Claude's title-safe recommendation: "Do it"). *Enforced by:* `zoom.safe_px`, `zoom.whole_min_level`, a step's
  `whole` (its box measured from the take's frames, `appears`), `camera.py`; the line check's framing check (R85).
  *David approved round 3's framing, 2026-10-14* ("These look good": the eight round-3 checks). R125 replaces the
  "zoom out, to full frame if needed" part.
- **R125 1.35x is the norm; zoom changes are rare and have a reason.** "135% is great." Zoom out further only when
  the viewer really needs to see the whole screen, not one part of it; zoom in further now and then to bring focus to
  one place, especially for a longer stretch (R42's tight spots). Otherwise pan: lots of zooming in and out makes
  viewers ill. A dialog the lines treat as a whole is framed at its own size, not the screen's: the Windows Open
  dialog at about 1.15x ("whatever zoom level the dialog box is"), not full frame; a dialog a little too big for the
  1.35x view is panned to the part being talked about, not eased out to. Full frame for nothing is a bug: 00:11:56:29
  in round 3 (p2.19's mark, padded 1 px above the page, was read as a mark in the browser bar, R40). The Open
  dialog's empty file-list space is white space David would cut out by hand and zoom in further; noted, no reshoot.
  R40 and R44 (full frame while a navigation's URL or new page matters) stand: there the viewer needs the whole
  screen. *David, 2026-10-14, on round 3* ("If you zoom out to the whole screen like at 00:11:56:29, it's too small to
  see"; "it's good that you don't go beyond 135%"). Replaces R123's zoom-out. *Enforced by:* `camera.py` (a step's
  `whole` is framed whole at `zoom.level` when it fits there; when it doesn't, the step's `whole.fit` says what
  happens: "own" frames it at its own size, the box filling the frame with no title-safe margin (`own_shot`; the Open
  dialog comes out at 1.093x), "pan", the default, keeps the level and the planner leaves the dialog out of the
  camera's beats, so it pans to what the lines name inside it; an ease-out never goes below `zoom.refit_min`, the
  camera pans instead); `plan.py`'s chrome-mark test judges a rectangle by its centre and an arrow by its head, so a
  pad reaching above the page no longer reads as the browser bar. Built 2026-10-14 (round 4): Section A's camera has
  three levels, 1.0 at the start, 1.093 through the Open dialog, 1.35 everywhere else, and 22 moves, all pans.
  R197 lets the camera zoom further out while what the line is about stays clearly readable there.
- **R45 Camera moves are linear;** the cursor keeps its eased motion. *David, 2026-10-06.* *Enforced by:*
  `remotion/src/camera.ts`, `zoom.ramp_s`.
- **R197 Zoom out further when what the line is about stays clearly readable there.** Under R125's 1.35x norm, the
  camera may zoom out, to full frame if needed, when the thing the line talks about is big enough to read clearly at
  the lower zoom: at 00:10:56 on round 8's sequence the new visual's large "You need to add or remove ..." text would
  have read at 100%, where 1.35x cropped it. In every video. Amends R125. *David, 2026-10-16* ("If the text/object
  being discussed is large enough to be clearly seen when zoomed out further, zomming out further is ok"; not worth a
  re-render for Section A, R195). *Enforced by:* not built (`camera.py`: a step's `whole` checked at the lower zoom
  against R198's text floor).
- **R198 Text a line names is at least 14 px tall in the output frame; 12 px where fitting everything leaves no
  room.** Measured as OCR's text box on the 1920x1080 frame. 14 px is the aim; 12 px is acceptable where more zoom
  would push out something that must stay in view; under 12 px the text isn't on screen (R81). In every video.
  *David, 2026-10-16* (on Fable's suggestion to raise the named check's floor from 12 to 14 px: "14 is desirable but
  in cases where we cannot fit everythong on the screen, 12 is acceptable. That, or a variation of that, should be
  reported as a universal rule"). *Enforced by:* the named check's floor stays 12 px (`checks.MIN_READ_PX`); a first
  mention under 14 px (`SMALL_READ_PX`) is listed as "R198 small" in `checks/report.md`, not made a marker, because at
  R125's 1.35x rest Quick Sight's interface text measures 12 to 13 px (21 named labels on round 8): R202 settles it.
  The camera's zoom choice doesn't use it yet.
- **R202 12 px is fine at the 1.35x rest.** R198's 14 px aim doesn't move the camera off its rest: named text 12 to
  13 px tall at 1.35x reads well enough. The aim applies where the camera is elsewhere (a dialog at its own size, a
  zoom-in). Amends R198. *David, 2026-10-16* (asked whether 12 px is fine at the 1.35x rest or small-text apps should
  rest at about 1.5x: "12px is fine at 1.35x"). *Enforced by:* the named check lists "R198 small" only where the
  camera isn't at `zoom.level`; on round 8 that leaves three labels in the Windows Open dialog (00:01:26 to
  00:01:45, framed at its own 1.093x), R198's own exception.

## Cursor and marks

- **R46 The cursor, click rings and Epic Pen marks grow with the zoom,** as David's real pointer and live marks do
  in his recordings. They are drawn in source space inside the camera, sized to look right at the 1.35x rest: the
  cursor 36 px (about 48 px on screen, David's S2 size), the ring 65 px (about 88 px). The cursor is visible from
  frame 0 at its parked point. *David, 2026-10-06 (S2 sizes; growth with zoom).* *Enforced by:*
  `cursor.height_px`, `cursor.ring_diameter_px`; `EditPass` draws them inside `Camera`.
- **R47 In live segments the cursor is hidden,** except for autopilot approvals, which show as normal clicks.
  *SPEC §7.1, 2026-10-05.* *Enforced by:* `plan.py` `cursor.hidden`, `remotion/src/Cursor.tsx`.
- **R48 Marks come in two kinds, and both are used.** In the flow: drawn-gesture arrows and rectangles that appear as
  drawn, with no fade-in (David draws them live with Epic Pen; ep02 1:14–1:25). Overview moments: edit-layer marks
  that fade in and out and are sometimes animated (ep02 0:23–0:30: rectangles on regions, an arrow that grows and then
  travels between them). *David, 2026-10-06.* *Enforced by:* `marks.fade_in_s` (overview), `plan.py`.
- **R49 A mark on a click target is drawn live, before the click:** draw, hold, release, then click. A fast cursor
  needs a drawn cue. *David, 2026-10-06.* *Enforced by:* `runner.py` `mark_gesture`, `marks.draw_s`,
  `marks.release_after_s`.
- **R50 A drawn mark holds until its area has been discussed:** by default the end of the sentence that names it,
  with no maximum; `until_word` overrides. The floor for a short sentence is 1.8 s on screen (the draw plus
  `marks.hold_s`). *David, 2026-10-06 (he holds the Epic Pen click until he is done
  talking about that area).* *Enforced by:* `marks.hold_s`, `marks.min_hold_s`, `marks.fade_s`. **Amended by R128:**
  for a click target the hold ends at the click, not at the end of the sentence.
- **R51 Marks look like David's own, by kind; one accent colour.** Orange #F16F05, no fill, one mark at a time; the
  click ring uses the same orange.
  - *Epic Pen marks* match his live look: about 5 px stroke (growing with the zoom, R46), slightly rounded corners,
    an open chevron arrowhead.
  - *Overview marks* match his Premiere roadmap: 8 px square-cornered rectangles, and his `Arrow01` (large filled
    head, #E86F3B), constant size in screen space.
  *David, 2026-10-06.* *Enforced by:* `marks.color`, `stroke_px`, `corner_px`, `head_px`, `overview_*`;
  `remotion/src/constants.ts` `RING_COLOR`.
- **R63 An overview arrow comes to rest only on what the narration names.** When it travels away with nothing to
  point at, it keeps moving until it has faded, so it never seems to point at something unimportant. *David,
  2026-10-06 (he slowed the test arrow's travel and turn to end with its fade).* *Enforced by:* `marks.py`
  `overview_path` (a step mark's `then` stops; it rests on each named stop, at least `marks.min_hold_s`; a stop named
  after its release becomes a move through the fade, `marks.overview_exit_s`), `marks.travel_s`; exported to Premiere
  as Arrow01 keyframes. No exercise uses overview marks yet; tested on take 05 with a scratch step.
- **R84 A mark frames the whole thing it names:** the whole tab (icon to close button), the whole button, the whole
  row, with a small margin, never just the words inside it. OCR finds the text; the box comes from the element (its
  page box, or for the browser's tabs, the tab shapes in the frame). *David, 2026-10-07, round 2 (5:29: the box ran
  from the first tab's title to the second's and clipped the second tab).* *Enforced by:* `marks.py` (chrome tab
  targets frame whole tabs); the line check's full-resolution mark crops (R85).

- **R121 Marks mix rectangles and arrows, each chosen by what reads best.** *David, 2026-10-14, on round 2's SPICE
  arrow* ("I like it. I like mixing rectangles and arrows. Use both across the video, chosen by what reads best").
  The pipeline chooses (R60): an arrow for a small target (an icon such as a pencil, a radio button or a caret), where
  a rectangle would be a tiny box, and for a card that already has its own outline; a rectangle for a labelled
  control, a row, a card or a pane (R84). A step's mark may name its kind, and `kind_locked` keeps it. *Enforced
  by:* `marks.kind_auto` (`arrow_max_px`), `plan.py` (a drawn rectangle on a small target is redrawn as an arrow in
  the same time, from the logged gesture). *David approved round 3's arrows, 2026-10-14* ("These look good").
- **R122 Spotlight dimming is one of David's styles:** in his own editing he sometimes dims every part of the screen
  except what is being discussed. It belongs to the motion-style project, not to the pipeline yet. *David,
  2026-10-14.* Not built.
- **R128 A click target's mark is drawn while the line is spoken, and the click lands on the name.** The mark is
  drawn during the lead-in ("On the left, I'll click ..."), released at the target's name, and the click lands 0.35 s
  after the name (R23), so the confirming clause plays over the result (R24) and no silence opens around the click.
  For a click target, R50's hold ends at the click, not at the end of the sentence; R49's order (draw, hold, release,
  click) stands. The cursor and marks are drawn in the edit, so the planner re-times them and cuts the recorded hold
  (still footage) to fit; no retake. *David, 2026-10-14, on round 3's silences* (00:01:24:10 to 00:01:28:12,
  00:05:27:01 to 00:05:29:00, 00:05:55:16 to 00:05:57:22: "I don't see why the editing can't be such so that the
  drawing happens while the vocal is in play"). Claude's diagnosis: R49 plus R50's hold put each click 2 to 3.6 s
  after its name, after the line had ended (at 00:01:24 the line said "the buttons below become available" before
  the click). *Enforced by:* `plan.py` (`click_mark_timing` and the R128 schedule: the recorded approach and draw
  keep their pace; the hold is `marks.hold_s`, longer when the lead-in from the cue word allows so the pointer sets
  off on the cue word (R23), never under `marks.click_hold_min_s` (0.6 s) on a short line, where the gesture starts
  before the line instead, and never longer than the recording holds; the mark is released on the name and the click
  lands `pacing.click_after_name_s` (0.35 s) later; the recorded hold's still footage is cut right after the
  completed shape, or frozen longer when the recording is short; a hover lit by the pointer's move to the target is
  kept, so the cut stops before that move; after the release the pointer reaches the target in 0.3 s, at most
  2000 px/s, so a rectangle is drawn from the corner far from the click, ending near it). Built 2026-10-14 (round 4):
  all 64 live click marks of Section A, 74 s of still hold cut, every click 0.35 to 0.37 s after its name, the video
  15:07 instead of 15:44.
- **R184 A named region gets the highlighter; a named control gets a rectangle or an arrow.** A pane, list or other
  region a line names is shown with the highlighter (the spotlight dim: everything else dimmed); a button, field or
  other control with an R51 rectangle or an arrow (R121). R159 still holds beside an overlay (a rectangle, not the
  dim). Applies R142 and R171. *David, 2026-10-15, on round 7* (00:04:31:28, the Schema pane named with nothing on
  it: "should in someway highlight the Schema pane. I'd suggest dimming everything else"). *Enforced by:* the steps'
  highlights (R142); the named-but-not-pointed-out check (R186).
- **R186 Everything a line names that is on screen is pointed out, in every video, and it is checked.** R171 as a
  rule for all videos: each label, quoted word or interface term a line names that the viewer can see then gets a
  mark, a highlight or an overlay within that sentence. *David, 2026-10-15, on round 7* (00:14:27:08, "Action 1"
  named with no mark: "This implies a rule that could be followed for all videos"). *Enforced by:* the check
  `pipeline.edit.checks` named (each label, quoted word or capitalised term a line names that OCR reads on screen, at
  least 12 px tall, needs a mark that frames it during its sentence, read at the mark's own time; a dialog the camera
  frames whole counts; repeats and a step's `not_pointed` waivers are listed apart). Built 2026-10-15 (round 8): it
  found notes 5 and 7 on round 7; 20 first mentions remain on round 8, for David's scope decision. R199 narrows it.
- **R199 R186 narrowed: mark what the line tells the viewer to find, look at or click.** Four kinds of on-screen
  names need no mark of their own: a landmark that only helps find something else ("next to monthlysummary, I'll
  click the pencil icon"), text while it is being typed, a result or value read out as it appears ("East is the
  busiest", "Activation is Select"), and the page or tab a click lands on ("It takes you back to the My stuff page").
  Nothing is marked a second time. Round 8's 20 unmarked names stay as they are (R195). Narrows R186, and R75, R124
  and R171 with it. *David, 2026-10-16* (Claude's recommendation: "let's go with your recommendation"). *Enforced
  by:* the check `pipeline.edit.checks` named: `not_needed()` reads each unmarked name's sentence for the four kinds
  (listed as waived, not markers); a term named before at the same place is a repeat; an arrow points at the text
  near its head, and the click target's own name is pointed out by its mark. Built 2026-10-16: on round 8 it leaves
  one of the 20 (the "Sheet 1" tab at 00:13:01, "The tab above the title still reads Sheet 1"); the arrow on SPICE
  at 00:07:18, missed before (its head stops at the word's corner), now counts.

- **R61 Premiere is David's edit surface.** Every edit is also exported as a Premiere sequence
  (`pipeline.edit.premiere`) he can open, change and save:
  - Overview marks are native layers he can move, retime, fade and re-aim (his `Arrow01`, sized rectangle images).
  - Epic Pen marks and the cursor are transparent clips, one per mark and one per cursor move. He can move, trim,
    fade or delete them, but not reshape them.
  - The recording, cursor and Epic Pen marks sit in one nested sequence with the camera on the nest. **Zoom the
    nest, not the footage inside it**, or the cursor and marks drift off their targets.
  - Captions come in as `captions.xml` (TTML, each cue in its grid position, R53), which he imports and drags to
    0:00, then deletes the one-frame anchor cue (R54). `captions.srt` is a fallback without positions.
  - Each export goes to its own folder (`premiere/`, then `premiere_r2/`, ...) once he has saved a project in the
    last one, so a new export never changes media his saved project uses.
  - He saves the `.prproj` in the export folder. Claude reads it back, reports what changed, and proposes the
    setting or rule each change implies (R60).
  *David, 2026-10-06.* *Enforced by:* `pipeline.edit.premiere` (the export, with a snapshot of the plan it was made
  from) and `pipeline.edit.readback` (the read-back report and `--against` a re-plan; GOTCHAS for the format).

- **R104 Premiere builds the project; David opens it.** The pipeline drives Premiere itself (its scripting, through
  the AIDV panel's bridge): it imports the round's XML, adds the caption titles and saves `<run>_full.prproj` in the
  export folder, so the import and the caption placing are no longer David's grunt work. The project is organised
  in bins, not left flat as an XML import leaves it (his demo had "Audio" and "Sequences" bins; the structure
  is the pipeline's to choose). *David, 2026-10-13* ("that removes human grunt work. Thumbs up"; "the project is
  quite flat"). *Enforced by:* `pipeline.edit.ppro.project` (`BINS`), `pipeline/edit/ppro/panel/jsx/aidv.jsx`. Claude may run
  Premiere on David's machine while he works in other programs (David, 2026-10-13: "I can live with that"). It never
  closes or quits a project it didn't open: on 2026-10-13 it quit Premiere with David's review copy open (a scratch
  build; nothing of his was saved or lost on disk). `bridge quit` refuses while any project is open.
- **R106 A time David should check is a timecode on the sequence he opens, and a marker there.** Never a line id
  ("p2.10d") or a time inside a clip or a nested sequence: anything Claude asks him to look at or listen to (a
  repaired click, a flag, a question) is named by its timecode on the full sequence and carries a sequence marker
  in the project. *David, 2026-10-13* ("I do not know what p2.10d means"). *Enforced by:* `plan.py` (each line's
  repaired clicks), `pipeline.edit.premiere` (markers on the full sequence and the export summary's timecodes).
- **R107 Premiere stays on the release build; no beta.** A project saved in the beta can't be opened in the
  release, so beta-only features (UXP `MogrtText`, 27.0) wait for a release. *David, 2026-10-13.*

## Captions

- **R126 Captions are 48 px and plain: no word highlight.** David's TitleTest look (R102) at 48 px instead of 40.
  If a word highlight is ever used (short-form, say), it is a Remotion overlay on its own transparent layer, so the
  picture under it (screen or avatar) is unaltered. *David, 2026-10-14, after the A/B in
  `runs/qs1a_20261014_full_take01/caption_ab/`* ("60px is too large and the highlight is too distracting"; for
  karaoke: "Remotion burn in but ... with transparent background so that the main screen ... is unaltered").
  *Enforced by:* `captions.titles.size_px` and `captions.stills.size_px` (48 in Section A's `edit_settings.json`;
  other exercises keep 40 until David says); `pipeline.edit.ppro.titles` writes the size into each title's text value
  (`text_value`: the run's style table) and sizes its box from it (`line_step`, Premiere's auto leading of 1.2 x the
  size). Built 2026-10-14 (round 4); Premiere's own frames of the round 5 build show a 57 to 58 px line pitch, the
  48 px size.
- **R133 A caption leaves bottom centre only for something that stays there.** A mark, a click target or a dialog
  being talked about moves it; the cursor passing through for a moment doesn't. *David, 2026-10-14, round 3*
  ("No reason why caption at 00:01:20:03 should go to bottom left": the cursor crossed bottom centre on its way to
  the radio button). Sharpens R53. *Enforced by:* `captions.cursor_stay_s` (0.6 s in Section A's settings): `plan.py`
  `keep_clear` returns the cursor's box at each 0.1 s of the cue, and `place_captions` moves a caption for the cursor
  only when it sits on the spot for that long; without the setting any moment of it does (the dashboard exercise,
  unchanged). Built 2026-10-14 (round 4): the 00:01:20:03 caption stays at bottom centre.
- **R182 A caption never covers what its line is about, for the whole line.** What the line names, marks or is about
  to click stays clear of every caption cue of that line, not only from the mark's draw to the click. Sharpens R53
  and R133. *David, 2026-10-15, on round 7* (00:02:55:13: the line's first cue sat at bottom centre on the dropdown
  at 2x, because `keep_clear` protected the click target only from the draw to the click; "caption blocks important
  drop down. Should be a rule checking for this sort of thing"). *Enforced by:* `plan.keep_clear` (every line spoken
  during a cue: its click target and marks for the whole line, a big box or a highlight kept clear where possible),
  `plan.place_captions` (no clear spot: the one that covers least), the check `pipeline.edit.checks` captions. Built
  2026-10-15 (round 8): note 3 and the Apply button clear.
- **R192 The caption box is #575757, so captions pass R179's 7:1.** White text on David's #5E5E5E measured 6.48:1;
  #575757 measures 7.23:1, a change hard to see. *David, 2026-10-15* (offered #575757, exempting captions, or
  #595959 at exactly 7.0: "Let's go with A"). Replaces the box colour of R101 and R102 (and R52's #5F5F5F).
  *Enforced by:* `captions.stills.box_color`, `captions.box_color` and the titles' background in Section A's
  `edit_settings.json` and `pipeline.edit.ppro.titles`; the contrast check.

- **R52 Captions are burned in and high visibility,** never relying on platform CC, because the videos go to several
  platforms: Lucida Console 48 px, outlined and shadowed white text on a dark grey box (#5F5F5F) with **no
  transparency** (a see-through box changes with whatever is behind it) and corners rounded at 7 px. *David,
  2026-10-06 (in Premiere he chose a grey box with rounded corners; he asked for no transparency and a dark grey close
  to that pick; #5F5F5F is also the grey of his published captions).* *Enforced by:* `captions.font`, `size_px`,
  `box_color`, `box_opacity` (1.0), `corner_radius_px`, `text_stroke_px`. **Amended by R101, R102, R126 and R192:**
  editable titles with plain text (no outline), 48 px, on a #575757 box with 15 px padding and 10 px corners.
- **R53 Caption placement: two rules, and the first wins.** (1) A caption never covers the focus point at that
  moment, anything the viewer needs to see. (2) Otherwise it sits at bottom centre. When bottom centre is in the way,
  the caption moves to another point of a 3×3 grid (Premiere's nine positions), even if that means some jumping
  around. Each cue is placed clear of the cursor, click rings, marks and targets. *David, 2026-10-06.* *Enforced by:*
  `plan.py` `place_captions`, `captions.top_y_px`, `margin_bottom_px`; in Premiere, `pipeline.edit.premiere` writes
  `captions.xml` (TTML) with one full-screen region per grid point (untested in Premiere until David's next import;
  the read-back counts cues in place).
- **R59 Two lines and about 42 characters a line are guidelines, not limits.** A cue may run to more or fewer lines
  when the moment calls for it. When a caption moves off bottom-centre, wrap it narrower (three lines is fine) so it
  stays well clear of what it is avoiding. *David, 2026-10-06 (he re-wrapped the 1:02 caption into three lines at
  bottom-left).* *Enforced by:* `captions.max_lines`, `captions.max_chars` (wrap defaults);
  `captions.off_centre_max_chars` (30) and `off_centre_max_lines` (3) for every spot but bottom-centre (`plan.py`
  `place_captions`). On take 05 this gives his three-line wrap of the 1:02 caption word for word.
- **R54 Captions come from the display text and its timings,** with no speech recognition, and are also exported as
  `captions.srt`. A caption appears as its first word is spoken, wherever the edit is viewed, Premiere included.
  *Brief, 2026-10-05; David, 2026-10-06 (his take 05 captions ran 1.05 s early after the SRT import: "I would prefer
  if they line up more precisely with the voice").* *Enforced by:* `plan.py` (a cue starts on its first word's
  timing); the export's caption files open with a one-frame anchor cue at 0:00, so a drop at 0:00 lands every cue on
  its words; `pipeline.edit.readback` checks it (cues within a frame).
- **R101 Captions arrive in the editor as clips in David's look,** one transparent full-frame PNG per cue on the full
  sequence's Captions track, at the planner's spot (R53): nothing to import or restyle, and he can still move, retime
  or delete any caption by hand (the human stays in the loop). His look is his restyle of full_take02's captions
  (read back 2026-10-08): Lucida Console 40 px, white, on a #5E5E5E box with 15 px padding and 10 px corners; it
  replaces R52's numbers for these clips. The TTML and SRT are still written, for YouTube's captions. *David,
  2026-10-12.* *Enforced by:* `captions.stills` in `edit_settings.json`; `pipeline.edit.premiere` `caption_stills()`.
  To be replaced by editable titles (R102): a PNG's text can't be edited.
- **R102 The AI makes a first pass of quality; the human finishes in the editor.** Anything David may want to adjust
  arrives in the editor in a form he can change on the spot, so a small change never sends the work back through the
  pipeline. Captions in particular are editable text: adding a line break or fixing a word must take seconds in
  Premiere. This is the point of his CSC13 pitch: don't rely on AI for everything; put the human in the loop where
  it's cheap, and the video editor is that place. *David, 2026-10-13* (on R101's PNG captions; his model is the
  `TitleTest` sequence in `runs/csc13_test_20261012/premiere_r2/csc13_test_20261012_full.prproj`: captions rebuilt as
  titles, #5E5E5E background at 100%, 15 px around the text, roundness 10, placed by hand). *Enforced by:*
  `captions.titles` in `edit_settings.json`; `pipeline.edit.ppro.titles` (one `.mogrt` per cue in his TitleTest
  look at the planner's spot; `pipeline.edit.ppro.project` then has Premiere build `<run>_full.prproj` in the export folder with one native
  title per cue on the Caption titles track, through the AIDV panel's bridge, `pipeline/edit/ppro/`). The PNG
  Captions track (R101) is kept, switched off. *David, 2026-10-13, on the first build:* "They work fine. No problem
  using the normal video tracks and double clicking lets me change text wherever." The text is plain, as in his TitleTest:
  R52's outline is retired for these (David, 2026-10-13: "Caption outline settled").

## Review, privacy and release

- **R55 No final render without David's approval of a proxy.** Superseded by R73 (review in Premiere).
- **R73 Premiere is where David reviews and finishes; no proxy by default.** Each round Claude exports the Premiere
  sequence (R61), checks its own work with stills and contact sheets, and reads David's saved project back (R60). The
  540p proxy and `timeline.html` are made only on request (a phone check, a quick look away from Premiere). The final
  video is David's export from Premiere; `pipeline.edit.final` (the 1080p render and approval gate) stays for a later
  hands-off path. *David, 2026-10-07 ("my preference is Premiere"; renders for both were double work).* Replaces
  R55.
- **R108 Fable checks every code change independently.** Once code changes, calls and installs are made and
  tested, a Fable subagent reviews them before the work is called done; Claude verifies each finding against the
  code and fixes what holds up, and the review and its outcome go in `docs/SLICE_LOG.md`. *David, 2026-10-13*
  ("once any code changes and calls and installs and subsequent testing are done, a call needs to be made to Fable
  for independent checking"; Fable reviewed the Premiere export and `pipeline/` on 2026-10-07).
- **R85 Before every export, Claude runs the line check and fixes what it finds before David sees it.** For every
  narration line:
  1. a full-resolution still, OCR'd, at each word that names something: the thing is readable then (R75, R81);
  2. each mark cropped at full resolution: it frames the whole thing (R84);
  3. each overlay item beside the sentence it rides on (R80);
  4. the voiced pause at every sentence end: none runs on (R31);
  5. no silence over a still picture beyond the rules (R25, R82);
  6. no overlapping caption cues.

  The report goes in the export folder; anything it can't settle goes to David as a question with the round.
  *David, 2026-10-07, round 2 ("which check would have caught it before I saw it": each of his five notes maps to one
  of these).* *Enforced by:* `pipeline.edit.linecheck`.
- **R56 Privacy checks advise; David decides.** Scans never stop a take or block approval. They report findings by
  video time; David marks each blur, ignore or retake. Raw footage keeps whatever was on screen and stays local in the
  git-ignored `runs/`. *David, 2026-10-06 (brief decision 17).* *Enforced by:* `pipeline.privacy.report` (OCR of the
  kept footage; masked text only, R4), `privacy_decisions.json` (his choices), the plan's `privacy_masks` (blurred in
  the proxy and the final render); `pipeline.edit.final` lists open findings and never blocks.
- **R57 The avatar appears only in the intro and outro.** *Brief decision 15.* Not built (Phase 4).
  **Superseded for Section A by R231 (2026-10-16):** the avatar goes on through the main body as picture-in-picture.
  Whether that holds for later videos is open (Open questions for David, at the end).
- **R100 The avatar never freezes, and it is gone before anyone else speaks.** The audio HeyGen lip-syncs to has
  1.5 s of silence on both sides, so the frames around the line are real (the avatar idles there with its mouth
  closed), never held frames. The camera's first line starts after the intro's dissolve has finished, plus the usual
  gap; the outro's voice starts 0.2 s after the dissolve into it. *David, 2026-10-12* (he proposed filler words such as
  "test, test" around the line; silence was tried first, since spoken filler would move the lips with no sound, and
  the avatar idled through it: no frozen frame, mouth closed). *Enforced by:* `pipeline.edit.avatar` (`PAD_S`,
  `OPEN_*`, `RECAP_*`); the step list's `opens_on_graphic` (the planner's first line); `premiere.camera_span`.
  **Amended by R205 (2026-10-16):** the intro no longer ends before the camera's first line; the avatar speaks it.
  **And by R231:** the avatar no longer leaves after the intro; it goes on through the main body as picture-in-picture.
  The 1.5 s pads stand (R205). The outro's 0.2 s counts from a dissolve that round 6 replaced with the oval's fade and
  growth (R232's mirror), counting it from the main body's end instead: open (Open questions for David).
- **R205 The avatar's intro runs into the main body: its last line is the main body's first sentence.** In Section
  A, "Every analysis begins with data, so that's where we'll start." HeyGen lip-syncs to the main body's own audio for
  that sentence, appended to the intro's audio after the usual gap, in the same render, so the avatar never jumps
  between renders and the main body's captions stay in time. The sentence is heard once, from the main body's audio.
  The avatar's picture carries across the join and leaves when the sentence ends; how it leaves (slides aside, shrinks
  to a corner, dissolves) is David's pick from variants. Kept from R100: 1.5 s of silence on each side of every avatar
  line, as spare footage; the outro's voice 0.2 s after the dissolve into it. *David, 2026-10-16* (on R100's first
  half: "I would still hold to this as it gives us extra tape to work with."; on the second: "I would say that this
  is false. The main body's first line should be the last part of the Avatar's speaking."). *Enforced by:*
  `pipeline.edit.avatar` (a step's `carry_into`, `carry_part`: cut at the silence the audio shows), `pipeline.edit.stage`
  (the intro clip trimmed so the nested approved sequence's first line lands where the avatar speaks it, its own
  Part 1 card handing over under the stage); built in `stage_review_r3` (2026-10-16); the final build is next.
  **Settled by R215 (the dissolve), then amended by R231:** the avatar doesn't leave when the sentence ends: at the
  hand-over it zooms down into the picture-in-picture oval (no dissolve, no gap; from the left third, R232) and goes
  on through the main body.
- **R206 The avatar is shown on a transparent background first.** Reviewed over a checkerboard or a solid colour; the
  background behind it is chosen later. *David, 2026-10-16* ("I'd like to see with transparent background to begin
  with. Therefore any solid color or even the photoshop checkered grid would suffice."). *Enforced by:*
  `remotion/src/overlays/AvatarStage.tsx` (`checkerUntil`). **Settled by R232** (after R225's B1, now set aside): the
  background is the Quick Series cityscape, held still behind the transparent avatar.
- **R207 Removing the avatar's background: HeyGen first, then local tools, then After Effects, then a cloud GPU.**
  (1) HeyGen's own: WebM with transparency from `POST /v3/videos` (`output_format` "webm", for looks trained with
  background separation), or HeyGen's background removal on an existing render; (2) an open-source tool on this
  PC's graphics card (Robust Video Matting first); (3) After Effects' Object Matte, by hand, for a single bad shot,
  since it can't be scripted; (4) an EC2 GPU machine, only if the first three can't do it. Hugging Face, blocked on
  this machine, may be opened if needed (David is admin). *David, 2026-10-16* ("If we need to fire up an EC2 machine
  with gpu ... that is possible and should be noted as such but I don't want to start there."; "This plan is good.";
  "Yes we can move AE from second to third."; "I'm admin on this machine so we can, if necessary, access Hugging
  Face."). The research: `docs/FINAL_R3_PLAN.md`. *Enforced by:* step 1 worked (2026-10-16): `pipeline.edit.avatar`
  (`output_format` "webm"), `pipeline.edit.alpha` (`fix_edges`: HeyGen's edges come premultiplied, plus a despill);
  `tools/avatar_alpha_test.py` for a look's 10 s test. **Still live under R232:** the intro and outro stay transparent
  renders, so the avatar can move and scale over the still cityscape. *Note (a fact, not a decision):* Hugging Face
  isn't blocked on this machine; its IPv6 route to CloudFront resets TLS and IPv4 works (`pipeline/hf_ipv4.py`), which
  is how R227's tools were installed.
- **R208 The avatar may slide while it speaks.** It may move across the frame to make room for graphics during a
  line, not only in a pause. *David, 2026-10-16* ("I guess by movement you mean the whole avatar slides? It can slide
  while speaking."). *Enforced by:* `AvatarStage.tsx` (the avatar's `moves`), `avatar_qs1a.json` "stage".
  **Limited by R224 and R232:** the slide is the stage's alone (in the intro, into the left third beside the roadmap
  card; in the outro, the mirror beside the recap card); the picture-in-picture box never slides, it moves by fades.
- **R209 The subscribe card is rebuilt in Remotion, in two looks for David to pick.** It replaces the Motion Array
  card (R131: away from Motion Array): a close copy of the old one (a YouTube-red bar, the bell, the thumbs-up,
  "Thanks for watching") and the same layout in David's brand colours. His `url.mov` write-on follows it, then the
  hard cut to the logo outro (R96). *David, 2026-10-16* ("Rebuild subscribe card in remotion."; "Yes" to "a close copy
  of the old one ... or your brand colours?", read by Claude as both, to compare; he didn't object). *Enforced by:*
  `AvatarStage.tsx` `SubscribeCard` (looks "red" and "brand"), `UrlWriteOn`. **Settled by R211:** the brand look.
  **Superseded by R232:** the original Quick Series subscribe animation, placed as in QuickArch03, replaces the
  Remotion card.
- **R211 The subscribe card is the brand-colour look.** Of R209's two, the brand look (Outro 2 in `stage_review_r4`)
  is the one; the YouTube-red copy is dropped. *David, 2026-10-16* ("I definitely prefer the more brand centric
  options in Outro 2."). *Enforced by:* the final's stage plan (`look` "brand"), from `final_r4`. **Superseded by
  R232:** the original Quick Series subscribe animation replaces the Remotion card, in either look.
- **R212 The giddyupdata.com write-on has no panel behind it.** `url.mov` is drawn straight over what's behind it, as
  David made it; the cream panel (and the darkening that kept its strokes 7:1 on that panel) goes. If its own colour
  falls under 7:1 on the chosen background, Claude proposes a soft shadow, never a panel. *David, 2026-10-16* ("Note
  that the giddyupdata.com cursive script in the outro has a background. It shouldn't."). *Enforced by:*
  `AvatarStage.tsx` `UrlWriteOn`, from `final_r4`; its contrast measured on the chosen background (G6). **Amended by
  R232:** the url footage exactly as at 00:07:34:03 of QuickArch03 (its own copper, its place and size there), still
  with no panel; as David's logo it is exempt from 7:1, so the shadow fallback doesn't arise. Built in round 6:
  `pipeline.edit.stage` places `url.mov` as a Premiere clip on the track "Call to action (QuickArch03)".
- **R213 Captions never cover the avatar.** Wherever the avatar is on screen, its captions and the approved
  sequence's copied caption sit clear of it; with the avatar in the left third, in the right two thirds. Where
  they go while it is full frame is David's pick (open). *David, 2026-10-16* ("Note that we have some issues with
  the CC overlapping the avatar."). *Enforced by:* `pipeline.edit.stage` (`stage_titles`), from `final_r4`; to be
  added to the measured checks (VIDEO_RULES C7). **Amended the same day:** while the avatar is full frame, captions
  stay bottom centre (over the shirt, as talking-head videos do); only the left third moves them. *David* ("where
  captions go while you're full frame. - bottom, center"). **Open (round 6, `stage_review_r6c` decision 4):**
  through the call to action round 6 puts the captions middle left, at QuickArch03's place, because the subscribe
  animation and the url hold the bottom of the frame; if David agrees, R213 gets that exception. **Measured since
  round 6:** `pipeline.edit.stage` `check_c7_quick` (every third frame of each cue against the avatar's reach, the
  oval and the card) and `pipeline.edit.pip` (the oval keeps `CLEAR_PX`, 12 px, from every caption).
- **R215 The intro's avatar leaves by dissolving (exit C).** Of R205's three exits, the dissolve with the Part 1
  card's fade; slide (A) and shrink-to-corner (B) are dropped. *David, 2026-10-16* (stage review: "C").
  *Enforced by:* the final's stage plan (`exit` "dissolve"), from `final_r4`. **Superseded by R231:** the avatar
  zooms down into the picture-in-picture oval, with no dissolve and no gap (from the left third, R232).
- **R216 The outro's gap between the subscribe card and the write-on stays empty for now.** About 5 s with nothing
  on the right (Section A: during "...consider bringing me in, in person or virtually."); no card added, the
  subscribe card not held. *David, 2026-10-16* ("just leave blank for now"). *Enforced by:* the stage plan as built.
  **Moot in round 6's layout** (`stage_review_r6c`; Claude's reading of R232's call to action placed as in
  QuickArch03): the avatar is full frame through the call to action, so the gap is the avatar talking, with nothing
  added. The rule stands if a later layout brings the empty side back.
- **R217 Image generation goes through Abacus.ai first; OpenRouter only where Abacus can't.** R150's Studio
  session makes the images. OpenRouter (`tools/gen_image.py`) stays for what Abacus can't do. *David, 2026-10-16*
  ("Please use abacus.ai. [...] DON'T use openrouter if you CAN use abacus.ai."). *Enforced by:* the session plan;
  Abacus's own cost shown before each Generate (GOTCHAS).
- **R218 The avatar's background: an openly artificial brand stage, chosen after the neon logo.** David leans to
  the Brand Stage look (`research/backgrounds/review_r1/s4_brand_stage_code_sign.png`): a background that is
  plainly graphic avoids a room that looks fake. First the GiddyUp logo as a real-looking neon sign (from
  `CircleOnly.svg`, the mark without lettering), made by image models from the logo, several to look at; then the
  background's colours, picked to contrast with that sign. *David, 2026-10-16* ("I like actually having a background
  but am concerned that it will look artificial and just having an obviously artificial background to start with
  kinda alleviates the problem."; "Let's get some instances of the 'neon giddyupdata logo' to look at before we
  decide on the exact background of the room."). *Enforced by:* `research/backgrounds/` (the neon round next).
  **Superseded by R232:** the background is the Quick Series cityscape; the brand stage is set aside.
- **R214 The avatar's transparency waits for the background.** No more work on removing the avatar's background
  (R207's local tools, the left edge's olive line) until David picks the background: the edge that shows depends on
  what's behind it, and an avatar in a masked box (a picture-in-picture circle or rectangle) over a chosen room needs
  no transparent render at all, which would free the engine choice (HeyGen's WebM is proven only on Avatar III,
  through the API). The research goes on. *David, 2026-10-16* ("That is very clever. Let's delay working on the
  transparency for a bit until we decide on those background images."). *Enforced by:* the session plan.
  **Settled by R220:** the box. **R232 then chose the background** (the cityscape, held still behind the transparent
  avatar), so the wait is over: the intro and outro stay transparent renders (R220, R207), and the main body's oval
  shows the cityscape the looks were recorded on.
- **R220 The avatar sits in a box, not floating free.** Full frame, the avatar and its background shrink together
  into a box (a circle or a rounded rectangle, David's pick from variants) and grow back; nothing of the avatar
  stands on its own over the screen or the cards. The edge HeyGen's matte leaves matters least at box size. The
  intro and outro are still rendered transparent on Avatar III (R219; the same price as MP4), and the pipeline puts
  them on the background and in the box, so the background (R218) can change without a paid re-render; HeyGen's
  own background replacement is the fallback for plan-credit renders that can't be transparent. Whether the box stays
  up through the main body (picture-in-picture throughout, Avatar IV) is still open (its cost: `research/
  heygen_plan/RESEARCH.md`). *David, 2026-10-16* ("Box", to "Box or free-floating?"; "Avatar III" for the intro and
  outro on the new look). *Enforced by:* `AvatarStage.tsx` (the box, to build), from `final_r4`. **Amended by R231
  and R232:** the box stays up through the main body as picture-in-picture (R231 settles the question above); its
  shape is R222 and R224's oval; in the intro and outro the avatar moves and scales over the still cityscape, into the
  left third beside the cards, and shrinks with its background into the oval only at the hand-over, growing back out
  of it in the outro (R231, R232).
  Built: `AvatarStage.tsx`, `pipeline/edit/stage.py` and `pipeline/edit/pip.py` (round 6). Open: David's remark on
  Avatar III for the intro and outro (Open questions for David).
- **R221 Avatar III through the API until a HeyGen plan is chosen; the picture-in-picture is agreed on stills
  first.** No HeyGen subscription yet. The main body's box (R220) is designed on stills (shape, size, place) and
  nothing is rendered for it until David agrees the look. *David, 2026-10-16* ("Before we commit on a subscription
  plan on Heygen, I want to stay with Avatar III via API. Also, I'd like to work on the PiP for the rest of the video.
  However, I DO NOT want to generate video yet. I only want an image of the avatar so that we can agree on the look
  and size and placement before we commit."). *Enforced by:* the session plan; `research/pip/pip_mock.py`
  (`research/pip/mock_r1/`). **Amended by R226 and R229:** David has a HeyGen Pro subscription; Avatar III through the
  API stays for test renders, and the web app makes the Avatar IV renders once the look is agreed.
- **R222 In picture-in-picture the avatar moves around, sized as in David's Quick Series.** No corner is reserved:
  the box goes to whichever corner is clear, as in Knowledge Bases 04 (`research/style_study/STYLE_PROFILE.md`
  section 6): the whole frame at 35% through a 288 x 375 px oval with a 3.5 px feather and no ring, bottom right at
  (0.9266, 0.8236) of the frame and the mirrored spots in the other corners; a move is a 0.3 s fade out, a jump and
  a 0.3 s fade in; hidden while an overlay needs the space. *David, 2026-10-16* ("we can move the avatar around when
  it is PiP mode. You can see how I'm sizing my avatar in 04-Knowledge_Bases04"). *Enforced by:* stills first
  (`research/pip/pip_ep04.py`, `research/pip/mock_r2/`, R221); the planner's corner choice from its own mark, card
  and caption boxes, to build after David agrees the stills. **Settled further by R224.** **Amended by R231:** the
  spots sit further in from the frame's edges than ep04's, which cut the oval off (round 6: 54 px from every edge,
  `pipeline.edit.pip` `EDGE_PX`; 54 or title-safe's 96 px at the sides is `pip_review_r2e` decision 1). Built:
  `pipeline/edit/pip.py` (`pip_spans.json`).
- **R223 The neon sign is GPT Image 2.5's white one.** `research/backgrounds/neon_r1/neon_white_gpt25.png` (the horse
  mark in white glass tubes on a clear acrylic disc); its brand-colour twin (`neon_brand_gpt25.png`) is the runner-up.
  The background (R218) is chosen next, to contrast with a white sign. *David, 2026-10-16* ("These are my two
  favorites: neon_brand_gpt25, neon_white_gpt25. I think I prefer the neon_white."). *Enforced by:*
  `research/backgrounds/` (the background round next). **Superseded by R232:** set aside with R225's wall (the
  background is the cityscape); the sign stays in the library and the catalogue (R154).
- **R224 The picture-in-picture box is the oval, teal inside; it never slides: it fades out and fades in elsewhere,
  or fades to voice only.** R222's ep04 oval, with the Brand Stage teal behind the avatar for now (the background
  inside may change once R218's is chosen). The box moves only by fading out and fading in at another spot, never by
  sliding; when no spot on the screen is clear, it fades out and the narration goes on as voice only until there is
  room again. R208's slide is the intro's stage only, never the box. *David, 2026-10-16* ("Oval and, for now, teal
  inside the box."; "PiP can move to different spots (rule, it never 'slides', it just fades and then reappears in
  another location.). PiP can fade so that there is only voice over if there's no place on the screen for it to
  display for a time."). *Enforced by:* the planner's box placement, to build; until then `research/pip/`.
  **Amended by R231 and R232:** the oval sits further in from the frame's edges (R231; 54 px in round 6) and shows the
  cityscape, not teal (R232). Built: `pipeline/edit/pip.py` (round 6, `pip_review_r2e`).
- **R225 The avatar's background is B1: GPT Image 2.5's teal wall with the white neon sign upper left.**
  `research/backgrounds/stage_r2/stage_gpt25_a.png` (a photographed-looking wall rebuilt by GPT Image 2.5 on Abacus
  from R223's sign, warm out-of-focus lights on the right, light pooling low); the sign stays upper left, beside the
  avatar at full frame. Behind the intro and outro's full frame; the picture-in-picture oval keeps its teal (R224).
  *David, 2026-10-16* ("B1: GPT Image 2.5", and "Yes" to keeping the sign upper left). *Enforced by:* the next stage
  build. **Superseded by R232:** the background is the Quick Series cityscape, held still behind the avatar, and the
  oval shows it too; the teal wall with the neon sign is set aside (built in round 5, `stage_review_r5b`).
- **R226 David has a HeyGen subscription: renders made in the HeyGen web app on plan credits; the API work goes on
  as before.** Plan-credit renders (Avatar IV and V) are made in the HeyGen web app; R221's Avatar III through the
  API is unchanged. *David, 2026-10-16* ("I've subscribed to HeyGen. You can access via the UI. Doesn't impact our API
  work."). *Enforced by:* the session plan.
- **R227 Word timing comes from the Qwen3 forced aligner and art cutouts from BiRefNet; the new OCR reads beside
  Windows OCR.** The aligner replaces the TTS engines' logged word ends and Vosk (0.06 s off on average against
  ElevenLabs' 0.18 s), with `breaths.beat_point` still the last check before a cut or beat; rembg with BiRefNet
  (`-dc`) replaces white flood-fill keying for generated art, flood fill kept as the fallback; RapidOCR with PP-OCRv6
  is a second reader where Windows OCR fails, never instead of it. *David, 2026-10-16* ("I agree with your
  recommendations.", on `research/huggingface/INSTALL_r1.md`). *Enforced by:* `pipeline/ml/` (`align.py`,
  `cutout.py`, `ocr.py`); wiring them into `pipeline.narration`, `tools/gen_image.py` and the checks is next. **Wired
  in, 2026-10-16:** `pipeline/narration/timing.py` (the aligner's word times, on for new exercises, off for Section A
  and the CSC13 base), `tools/gen_image.py --cutout` (BiRefNet; `--key-white` the fallback) and RapidOCR as the
  line check's second reader.
- **R228 The giddyupdata.com write-on is cream.** With no panel behind it (R212), `url.mov`'s copper can't reach 7:1
  on the teal wall; recoloured cream it measures about 11:1. *David, 2026-10-16* ("Yes", to "OK to make it cream
  (11:1)?"). *Enforced by:* `AvatarStage.tsx` `UrlWriteOn`, at the next stage build. **Superseded by R232:** the url
  footage in its own copper colours, as in QuickArch03, exempt from 7:1 as David's logo.
- **R229 The avatar's look and feel is tested in Premiere on a still picture first; Avatar IV through the HeyGen web
  app only once David is satisfied; Avatar III on the API for any test render meanwhile.** David's HeyGen plan is Pro
  (1,000 credits a month). The first line of testing places a still of the avatar (in its oval, on its background) in
  a Premiere review; no video is rendered for the picture-in-picture until the look is agreed; then the web app makes
  the Avatar IV renders on plan credits. Any test render before that spends the API wallet on Avatar III. *David,
  2026-10-16* ("I got pro. For now use up the API credits using Avatar III if we need further testing. Remember, we're
  just using a pic for our first line of testing in Premiere. When we're satisfied with look and feel, we'll use the UI
  for Avatar IV."). *Enforced by:* the session plan; renders made in the HeyGen web app on plan credits.
  Built for the box: `pipeline.edit.pip` (the review on a still, `pip_review_r2e`).
- **R230 Claude may restart a stuck Premiere.** When the bridge stops answering (a hang or a dialog nobody can see),
  Claude may quit and restart Premiere, or end its process if it is hung, as long as no project of David's is open
  (R104 still stands: check `app.projects` first whenever the bridge answers; never close his work). Claude may ask
  David to kill other processes. *David, 2026-10-16* ("I had to restart Premiere. You are welcome to restart Premiere
  in the future if you experience such trouble. Let me know if you need any processes killed."). *Enforced by:*
  `pipeline.edit.ppro.bridge` (`quit`, `start`), the session plan.
- **R231 The avatar goes on through the main body as picture-in-picture: from full frame it shrinks into the oval,
  kept a little in from the frame's edges.** Replaces R136 (and R57) for Section A: the avatar no longer appears in
  the intro and outro only. At the hand-over into the main body the avatar zooms down from full size straight into
  the picture-in-picture oval, layered over the main body's opening card; no dissolve and no gap (replaces R215's
  dissolve, which made the face leave and come back 2.6 s later). The oval's size and its teal inside are agreed; it
  sits further in from the frame's edges than ep04's spot, which cut it off. From `pip_review_r1b`: the box over a
  pane the narration is on (00:09:53:05, and 00:12:40:16 to 00:14:32:13) is fine, and so are the voice-only
  stretches (00:00:26 to 00:01:08, the last 41 s). *David, 2026-10-16* ("Can the face just zoom down from full size
  to PiP? I think it could be layered over the overlay at 00:00:01:23 and it would be fine."; "Note that the PiP is
  always a little too close to the edge. It is getting slightly cut off."; "Teal and size is fine."; "Yes, we are
  working on a rule change. The avatar will shrink from Full screen to PiP."; "Fine" twice). *Enforced by:*
  `pipeline/edit/pip.py` (the inset, the hand-over), at the next build. **Amended by R232:** the oval shows the
  cityscape, not teal, and the zoom-down starts from the left third, where the avatar sits beside the roadmap card,
  not from full size. Built in round 6 (`pip_review_r2e`, `stage_review_r6c`): the oval 54 px in from every edge
  (`pip_review_r2e` decision 1), up from the main body's first frame, the zoom-down 0.6 s and linear.
- **R232 The intro and outro go back to the Quick Series look: the cityscape, the avatar beside the cards, the
  original call to action and url footage.** The background is the cityscape David's Quick Series uses
  (`D:\Videos\Global Assets\OfficeZoom_0002.jpg`, the picture the HeyGen looks were recorded on), held still behind
  the transparent avatar so the avatar can move and scale; it is also what the picture-in-picture oval shows
  (replacing R224's teal) and R225's teal wall with the neon sign is set aside. When the roadmap card comes in, the
  card stays as it is, in the right two thirds, and the avatar slides left and scales down to fit the left third or so
  (not half and half); at the hand-over it zooms down from there into the oval (R231). The outro mirrors it: the
  oval grows back on the cityscape, the avatar beside the recap card. The call to action is the original subscribe
  animation from David's Quick Series, placed as at 00:07:25:22 of the 03-QuickArch03 sequence in
  `D:\Videos\QuickSeries\AmazonQuick.prproj` (supersedes R209 and R211's Remotion card); the url write-on is exactly
  the url footage used at 00:07:34:03 of the same sequence, in its own copper colours across the lower part of the
  frame with no panel (supersedes R212's and R228's colour and placement); as David's logo it is exempt from the 7:1
  rule. *David, 2026-10-16* ("I want to go back to the old way of the cityscape background"; "Yes but not 50-50.
  Something like 1/3 avatar 2/3 overlay or whatever fits."; "The card stays as is. The avatar moves over to
  accommodate."; "I'd just suggest taking exactly the website url footage that is in QuickArch03."; "Yes" to the card
  on the right with the avatar moving left; "The original placed in the same way."; "Yes" to the logo being exempt;
  "Everything else is as you say."). *Enforced by:* `AvatarStage.tsx`, `pipeline/edit/stage.py`, `pipeline/edit/pip.py`
  at round 6. Built in round 6 (`stage_review_r6c`, the steps file's stage `design` "quick"); its README's decisions
  are David's, and those that touch other rules are in Open questions for David.
- **R233 A round's frames come from two Premiere exports: an H.264 for speed and a PNG sequence for fidelity, both
  deleted when the work is done.** Premiere exports the whole review sequence once as H.264 (ffmpeg pulls any frame,
  and the checks can scan every frame) and once as a full-resolution PNG sequence (pulled whenever a check needs finer
  detail than the H.264 gives, such as small text); both go to a scratch folder and are deleted once the round's
  checks and reviews are finished. They replace most single-frame exports, which stay for an exact moment the PNG
  sequence lacks. *David, 2026-10-16* ("we should consider two exports. One ... to PNG and the other to H.264. That
  way you can have the speed and flexibility of H.264 and pull in a PNG whenever you want to check out smaller text at
  finer fidelity. Also, they can all be deleted once the work is done."). *Enforced by:*
  `pipeline/edit/ppro/exports.py` (both exports through the bridge, exact frames, a whole-sequence scan, `clean`),
  presets in `pipeline/edit/ppro/presets/`, `framecheck --exports`; built and tested on round 6 (2026-10-17: the
  PNG sequence at 10 fps; slower than single frames, 36.5 min against 89 s, but every frame scannable).
  **Amended 2026-10-17 (R240):** the H.264 of the whole sequence, plus full-resolution PNGs only of the frames that
  need fine detail (the single-frame export, seconds each), not a whole PNG sequence (19 min and 6 GB on round 6).
- **R234 The intro starts at "In this video".** The greeting ("Hi, I'm David Baldwin with GiddyUp Data.") is cut.
  The cut is made in the voice clip and the avatar render already made, at the pause before "In", so nothing is
  re-voiced or re-rendered; the next render (Avatar V) uses the shortened audio. Amends R203 (the intro approved as
  drafted). *David, 2026-10-17* ("Remove the opening that says, hi, I'm David Baldwin. With GiddyUp Data. Start with
  'In this video'."). *Enforced by:* `exercises/qs1_section_a/avatar_qs1a.json`, `pipeline.edit.stage`, at round 7.
- **R235 Round 6's answers: the avatar is on screen as the main body ends and grows into the outro; sounds on the
  subscribe animation; the picture-in-picture as built.** At the outro's start the avatar is already there: its
  oval (in this test phase the still picture, R229) is up as the screen recording finishes and grows from the oval to
  its outro size. The subscribe animation gets sound: a whoosh as it enters, a bell as the bell is clicked, the click
  sound (R137) on the thumb. "Thanks for Watching!" keeps its own colours, exempt from 7:1 like the logo and url
  (amends R232). Kept: the zoom-down's and the growth's shape; captions middle left through the call to action
  (R213's exception); the call to action's timing on "subscribe" and "thumbs"; the oval 54 px in from the edges
  (R231); 15 moves and 11 voice-only stretches; captions within about 20 px of the box; the small overlaps the
  reviewer listed; the hand-made keep-clear list. The left third's size is being chosen from stills at 70, 75 and 80%
  (part of the avatar's arm may be cut off by the frame's edge, as long as the card is clear). *David, 2026-10-17*
  ("we really should see a PNG ... Expanding from an oval to the size it needs to be at the beginning of the
  outro."; "I'd like sounds on the subscribe animation perhaps a swooshing sound as the whole animation enters.
  Perhaps ... a bell sound as the clicking is done. On the bell, and perhaps just our click sound when clicking on
  the thumb."; "It's fine" to the T's contrast, the moves and the caption clearance; ticks on the captions, the timing
  and the inset). *Enforced by:* `pipeline.edit.stage`, `AvatarStage.tsx`, `tools/overlay_sounds.py` (a bell), at
  round 7.
  **Confirmed 2026-10-17 on round 7:** the oval's 0.87 s lead before it grows (outro 00:00:08:22 to 00:00:09:18,
  over the line chart's left end while the last caption is up) is fine (David: "00:00:08:22 to 00:00:09:18 is fine.").
- **R236 A render's handles hold R100's silence, not the timeline's speech.** Each Avatar IV render keeps 1.5 s of
  silence at both ends (the avatar idles, mouth closed), so a stay lengthened into a handle can be faded out rather
  than show a closed mouth over speech. The cost is the same either way: HeyGen bills by the second of video, and the
  handles come to about 32 s a video (21 of them), about 16 credits on Avatar IV. *David, 2026-10-17* ("I think that
  the answer is R100's silence ... I could always fade out the video"; "I'm ok with 1.5 s at either end but I still
  want to know the cost", answered: the same for both). *Enforced by:* `pipeline/edit/pip_render.py`
  (`--handle-audio=silence` as the default).
- **R237 The avatar's engines and budget: Avatar V for the intro, Avatar IV for the outro and the main body, never
  Avatar III in what viewers see; the main body at the P55 presence budget.** Avatar III only for test renders. The
  picture-in-picture box shows at the moments that matter (part starts, new ideas, tips, recaps; about 55% of the
  main body) and goes voice only through the hands-on stretches (`research/pip/presence_budget/`, about 378 credits a
  video, two a month on the Pro plan). The intro's render carries the box's first stay (to its first move), so the
  pose never jumps. Renders about 5 minutes long. *David, 2026-10-17* ("yes" to V for the intro and IV for the outro;
  ticked "Avatar III never in anything viewers see"; "P55"; "ok" to the intro's render through the first stay; "I
  don't care" on render length). *Enforced by:* `pipeline/edit/pip.py` (`exercises/qs1_section_a/pip_presence.json`),
  `pipeline/edit/pip_render.py`.
- **R238 The first paid render is one sample of the main body, through the HeyGen web app, on an Avatar IV Photo
  Look.** The stretch from 00:08:10 to 00:08:35 of the main body, rendered through the web app on plan credits (not
  the API) to work out that process, on a Photo Look (16 credits a minute against 31) to judge whether it holds at
  oval size. Everything else in the main body stays the still picture until David approves the sample; the intro and
  outro are rendered whole (V and IV) only once everything else is as good as can be known. *David, 2026-10-17*
  ("start with just that one sample, work out the kinks before we do any of the intro outro recording"; "let's go
  ahead and test that on the photo look"). *Enforced by:* the session plan; the HeyGen web app (R226).
- **R239 The picture-in-picture and the Quick Series stage hold for every video; this video first, then the
  blueprint (its 2026-10-20 date stands).** R231's picture-in-picture through the main body and R232's stage
  (cityscape, left third, original call to action) apply to every video, not Section A alone. The blueprint stays on
  hold (R210) until this video is finished, and its date for the CSC13 talk still stands. *David, 2026-10-17* ("Every
  video"; "Yes. My goal is to finish this video and then work on the other things that need doing including the
  blueprint."). *Enforced by:* the session plan.
- **R240 Frames for checks: one H.264 of the whole sequence, and full-resolution PNGs only where needed.** Amends
  R233: the PNG sequence is dropped (on round 6 it took 19 minutes and 6 GB); any frame that needs fine detail (small
  text, alignment) comes from Premiere's single-frame export (seconds each); the H.264 serves the whole-sequence scans.
  *David, 2026-10-17* ("do you think it would make sense to output to the former and only to the later for those
  frames where it is needed?", answered yes). *Enforced by:* `pipeline/edit/ppro/exports.py`, `framecheck.py`.
- **R241 The main body's avatar is David's normal "David Baldwin" look on Avatar IV; the Photo Look is dropped.**
  Sample test A (00:08:10 to 00:08:35, 13 plan credits) moved his head about half as much as the Photo Look (39
  against 68 px a second over the oval's 22 s) and never brought a hand into the oval (the Photo Look: 28% of the
  time); the Photo Look's motion can only be calmed by HeyGen's "Custom motion", which doubles its price to about the
  normal look's. The main body renders on this look at R237's P55 budget (about 291 credits a video). *David,
  2026-10-17* ("Let's just run the normal avatar look. Do not rerun the photo look."; "Yes", to "is this look good
  enough to approve for the main body?"). *Enforced by:* `pipeline/edit/pip_render.py` (the look `<HEYGEN_LOOK_ID>`),
  `research/heygen_plan/SAMPLE_PHOTOLOOK_r1.md` (both tests).
- **R242 Round 7 approved; the main body's renders go ahead; the series card and the subscribe animation rebuilt in
  Remotion.** The intro and outro design of `stage_review_r7` is approved. The main body's Avatar IV renders (R237,
  R241, P55) go ahead through the HeyGen web app once Claude has rebuilt the render plan (the shorter intro, P55) and
  sent David its segments and total (about 291 plan credits expected); then the intro (V) and outro (IV), whole, once
  everything else is settled. The "Amazon Quick Series" card (lower right, as at 2 s into QuickArch03) is rebuilt in
  Remotion in the same look, its second line "Quick Sight Journey 1: Build your first dashboard". The subscribe
  animation is rebuilt in Remotion in 3 or 4 variations for David to pick (replacing the Motion Array original of
  R232); the url write-on stays David's own `url.mov`. The outside frame review (Gemini 4 Argon, about $5.40) runs
  once on the finished video, after asking. *David, 2026-10-17* (ticks on each; "Your e.g. is fine."; "3 or 4
  Remotion variations please"). *Enforced by:* `pipeline/edit/pip_render.py`, renders made in the HeyGen
  web app on plan credits, Remotion compositions to build.
- **R243 The series card reads "Amazon Quick Series" / "QS Journey 1: First dashboard"; the subscribe animation is
  the brand-colour Remotion variation.** The shorter second line lets the card grow (labels at the rulebook's size)
  and move as the room allows. Of the four subscribe variations, the brand-colour one (`remotion_ctas_r1/
  preview_subscribe_brand.mp4`). *David, 2026-10-17* ("Let's go with QS Journey 1: First dashboard and then adjust the
  size and positioning based on the extra space that gives us."; "Of the 4 variations, I like
  preview_subscribe_brand.mp4"). *Enforced by:* the Remotion pieces (`runs/qs1a_20261014_full_take01/remotion_ctas_r1/`),
  wired into the stage at the final assembly.
  **Confirmed 2026-10-17:** the re-sized card (829 x 230 px, the title 64 px, the second line 56 px on one line, lower
  right under the beard) is fine (David: "it's fine"). Re-run its beard clearance on the Avatar V intro
  (`python tools/remotion_ctas.py check`, the "face" entry).
- **R244 final_r4's calls: all fine as built; the intro (Avatar V) and outro (Avatar IV) renders go ahead; the outside
  frame review runs without asking.** The oval 15 px from a caption (00:01:49:27 to 00:01:54:09; 16 px at
  00:10:19:22), over part of Quick Sight's blue notice (00:03:00:21) and about 3 px from the "+ Add" button
  (00:10:59:17 to 00:11:17:14, from 00:12:02:01): fine. `url.mov` stays exactly as QuickArch03 places it (00:17:17:10):
  the tail of its "g" below title-safe, no sound cue, its last 4 frames fading into the hard cut to the logo, so it
  is exempt from K3 and S9 there (VIDEO_RULES' exceptions table). The first stay's 10 s still (00:00:45:03 to
  00:00:54:29) closes with the Avatar V intro render. The intro on Avatar V and the outro on Avatar IV (about 47 and
  30 plan credits, R237) go ahead. Gemini 4 Argon's frame review of this video (about $5.40, R191, R193) runs on the
  finished video without asking first (amends R200's ask for this video). *David, 2026-10-17* ("Fine for each.";
  "This is fine as is."; "Ok"; "fine" to the renders; "Don't ask, just review."). *Enforced by:*
  `pipeline/edit/ppro/final_quick.py`; `tools/video_review.py`.
- **R245 The one-shot build of the next video (B-Data Sources > Connect to Athena): no checkpoints, no HeyGen.**
  Claude builds the whole video to a finished Premiere project without stopping for David, who reviews only the
  result (his one manual step: signing in to Quick Sight off camera, R110). No length target: "the length will be
  what the length will be". Claude picks the overlays (a judge model plus the rulebook), reviewed by David at the end
  (in place of R163's picks in a review project). The narration is voiced in ElevenLabs as usual; **no HeyGen renders**:
  the avatar is a still picture for the whole video (the intro's stage, the picture-in-picture oval, the outro), as
  R229's still-first tests were. Before the take Claude deletes the orphaned "Athena-Feb2021Flights" data sources and
  datasets left in the account by the manual walk (a one-off extension of R119, which otherwise never deletes data
  sources). The final take's objects stay, since the S3 and Redshift exercises reopen "B-Data Sources"; only retakes'
  objects are deleted. The procedure the one-shot follows, and fixes where it is wrong, is a new
  `CREATE_A_VIDEO.md` beside `CLAUDE.md`. *David, 2026-10-17* (on `docs/ONE_SHOT_athena_review.md`: "Correct"; "The
  length will be what the length will be."; "Yes"; "Delete them"; "Yes"; "That's fine."; "Do not generate the
  Heygen. DO generate the 11 labs. Just put in a screenshot of the avitar for all the video."). *Enforced by:*
  `CREATE_A_VIDEO.md` (to write); the one-shot session's plan. *Open:* the spending caps for the overlay build and the
  outside frame review (R200) on this video.
- **R246 Before the one-shot: the pipeline's gaps are fixed first, as their own step; its spending caps.** The gaps
  `CREATE_A_VIDEO.md` found (Section A hard-coded in the overlay tools, the call-to-action renderer, the render plan
  and the HeyGen scripts; no still-avatar path through the stage and the final; the logo outro taken from an earlier
  final; the steps schema rejecting fields Section A uses; no off-camera rehearsal) are fixed before the one-shot
  runs, with Fable reviewing the code (R108), so the one-shot tests the pipeline instead of mostly fixing it. The
  one-shot then runs once David has approved `final_r5`. Its caps: the overlay build up to $10 (Abacus first while its
  credits last, R217), and the outside frame review once, about $4.50, without asking (R200). Settles R245's open
  item. *David, 2026-10-17* ("Ok for all three", to: fix the gaps first with Fable reviewing; when to start; the caps
  of $10 and about $4.50). *Enforced by:* `CREATE_A_VIDEO.md`; the one-shot session's plan.
- **R247 final_r5 is approved: Section A is finished; a 90-second highlight reel of the process comes next.**
  `runs/qs1a_20261014_full_take01/final_r5` is the finished video, its README's calls taken as built: Avatar V's
  silent breath before "In" (00:00:00:05) and the beard at the series card's corner for two frames (00:00:02:27)
  stay; Argon's 15 rule-breaking items inside the approved main body stay (R195); OpenRouter is not topped up, so
  00:08:24 to 00:08:48 stays unreviewed by Argon and the one-shot's overlay ideas use Claude and Abacus only (R246's
  cap unchanged). Before the one-shot: a 90-second video from this one showing the highlights of how it was built,
  not Quick Sight ("whatever shows the most of our work"). *David, 2026-10-17* ("I've reviewed the video and am
  satisfied."; "Before we do the one-shot in QS, can you create a 90 second video from the video just completed? The
  goal is to show the highlights. The highlights are not about QS but about our video building process.").
  *Enforced by:* the session plan.
- **R248 The highlight reel: for the CSC13 talk; its story is that AI made the video, from capture to final edit;
  the video's own sound only; the real numbers at the end.** About 90 s, 16:9, played in David's talk on
  2026-10-20. It shows the chain of AI work, stage by stage (the capture, the narration, the edit, the graphics, the
  avatar, the checks, the assembly in Premiere), with behind-the-scenes material where it shows that work; the
  making of the video is the means, not the subject. Sound: the finished video's own audio, and no other music (the
  logo outro's Rossini only if the logo outro is one of the moments shown). The end card gives the real numbers from
  the logs, costs included. *David, 2026-10-17* ("Tuesday's CSC13 talk"; "The video's own audio but with no
  additional music. If the music at the end of the video is one of the things we showcase, that is fine. But no other
  music."; "the focus is not on the creation of the video itself, but AI created the video - all the way from
  capture to final edit."; "Yes, with the real numbers"). *Enforced by:* the reel's plan.
  **Amended 2026-10-17:** the process is detailed, and the rules most of all: each of David's decisions becomes a
  numbered rule (`RULES.md`), the rulebook every check and AI reviewer reads (`VIDEO_RULES.md`, each rule with how
  it's checked), and the procedure (`CREATE_A_VIDEO.md`), which is what makes further automation such as the
  one-shot possible. *David* ("detailing our process will be important. All the stuff about creating the rules is
  especially important because that is what will allow further automation - like our oneshots.").
  **Amended again 2026-10-17:** the reel names the technologies, above all the calls to other AIs and AI tools (the
  talk's focus), and the conventional tools too (OBS, Premiere, Remotion and the rest), each with what it did. *David*
  ("we'll need to mention the technologies used - especially calls to other AIs and AI tools since that is the focus
  of the talk. Yes, of course, we'll want to mention OBS, Premiere, Remotion, etc.").
  And the subagents: Fable's grading above all, and any smaller models given the routine work, each with what it
  did and how often, counted from the session logs. *David* ("also the subagents that were called - especially the
  grading work by Fable but also if you called other lesser models for grunt work.").
  **The sound, changed:** a new narration in David's ElevenLabs clone says how each thing was done, in place of the
  video's own audio carrying the reel (still no music beyond the logo outro's, if shown). No HeyGen render: a still
  picture of the avatar stands in for now (`Global Assets/avatar/david_baldwin_still_1080p.png`). *David* ("I think
  we actually may need another call to 11labs to narrate how things were done. Instead of a call to Heygen, let's
  just use a png as a place holder to begin with.").
  **Two uses:** played in the talk, where David may let the narration run or narrate it himself over the picture,
  and sent on its own to prospective clients about the workflow. So the picture carries the story without the
  narration (on-screen labels and numbers readable at a distance, beats long enough to talk over), the words suit a
  client (business terms first, the tools named but explained), and the reel ends with how to reach GiddyUp Data.
  David reads the script before it is voiced. *David* ("I will play this during the talk on Tuesday. I may or may
  not let the audio run the whole time. I might play the role of narrator. However, I also want the video to work
  as a standalone so that I can send to potential clients regarding our workflow."; "I'll read it.").
  **Before David reads the script,** Gemini 4 Argon reviews it through DeepThink against the rules and processes
  (`VIDEO_RULES.md`, R248 with its amendments, the narration style), each finding checked and what holds fixed.
  *David* ("Before I read it, make sure it is reviewed with our rules and processes. Let's use deepthink with
  Argon.").
  **The costs:** subscriptions shown as flat monthly amounts (Claude $200, HeyGen Pro $49, Abacus $20), with only
  the measurable shares allocated; ElevenLabs is paid per use; OpenRouter counts only this project's logged calls.
  The reel makes clear that later videos cost less: cost per finished minute for Section A against the reel's own,
  lower because the rules are written and far fewer calls go to other AIs. *David* ("We should make it clear that
  future videos cost less. For example, if we break down the cost per minute, the price of this 90s demo video
  should be less since all the rules are in place and thus there are fewer calls to various AIs.").
  **The reel's avatar is rendered in HeyGen, in three steps:** (1) David reads the script; (2) he approves the
  layout and plays the reel with its audio, the avatar still a picture; (3) then the HeyGen render replaces the
  picture, with nothing else changing. The reel's costs include that render. *David* ("I do plan on making a HeyGen
  render. I just want to do it in three parts: 1. Read the script 2. Approve the video layout and play including
  audio 3. Render Heygen").
  **David's notes on the script (draft 2):** the voice says no numbers (a total, such as the total cost, at most);
  numbers appear on screen only, and few of them: the reel walks through the whole process, and David gives the
  details in person. Its message: AI grades AI and shows David only the best, so no human time is wasted otherwise.
  *David* ("Voice should not say the numbers. Numbers can appear as on screen. It might be permissible for the voice
  to say some totals such as total cost."; "AI grades AI and only shows me the best. Human time not wasted
  otherwise."; "Lots of numbers make people sleep. Better to just go over the whole process. I can cover details in
  person.").
  **Draft 3 approved, with its five calls:** about 2:38 as it stands; the video's own voice comes up twice in the
  talk version too; the cost line says "about forty-six dollars, plus my Claude subscription"; "140 decisions in
  these four days"; ElevenLabs about $1.25 until David gives the billed figure. Next: voice it, cut the layout, and
  David plays it with its audio (step 2). Claude may restart Premiere. *David, 2026-10-18* ("The 5 items under Your
  calls are fine. You're welcome to restart Premiere. Please proceed.").
  **The reel's narrator is not David:** hearing his voice narrate the lesson and then narrate the reel confuses, so
  the reel's narration is another voice, in the third person, rewritten with care (more changes than the pronouns).
  A first test uses one of Microsoft's female neural voices, as the pipeline's Microsoft Andrew voice does. Claude
  writes the script itself, with no outside review: Fable reviews it internally, and David reads it before the reel
  is reworked. *David, 2026-10-18* ("It is confusing to hear my voice as the narrator in the original video, and then
  to hear my voice as the narrator in this explanatory reel. Therefore, I'd like to use another voice instead of
  mine"; "change the narration as well to third person"; "Let's run a test locally with ... one of the female
  Microsoft voices"; "do not send out for a review of the text. Instead, write that text yourself and then just send
  it for an internal review to Fable. Also, let me read the text. Before you rework the video.").
  **David's rewrite of draft 4:** "tutorial" for the lesson throughout; his own wording for the opening, the
  capture, the avatar, the checks (merged with the helper agents), the software, his final say over the edit, the
  one-shot ("even less human interaction") and the cost (predicted under $1 a produced minute, testing, voice and
  avatar included, Claude's $200 a month not), woven in by Claude and reviewed with Gemini 4 Argon through DeepThink;
  the final narrative goes to David before the video is reworked. In the video: David's avatar fades in for "A chart
  is only as good as the data under it.", and a placeholder marks where the narrator's own avatar (which David will
  supply) will show. *David, 2026-10-18.*
  **Draft 6 approved:** the cost line is wording B (about two dollars a finished minute, voice, avatar and the calls
  to other AIs included, the monthly Claude subscription not); "17 minutes" is spoken; Claude's wording changes stand
  ("Claude's code", "building and review", "a second Claude model"). Next: voice it in Microsoft's Emma and cut the
  next iteration for David to play, the narrator's avatar still a placeholder. *David, 2026-10-18* ("1. B 2. Just say
  17 minutes. 3. Your wording changes are fine.").
  **Round 2 notes (for this reel only, never for the tutorials):** the whole frame fades out and in at every beat
  change; the open-to-main and main-to-ending transitions take a second or two more, with a whoosh from
  `Global Assets/motion-library/sounds/` and the graphics flying in; every beat between them sits on
  `runs/qs1a_20261014_full_take01/stage_public/stage_teal_1920x1080.png`, not the cityscape; listed items (steps,
  tools, the checks header) appear as the narrator says them, with livelier entries for the tools; no captions
  inside the footage insets; the narrator (Emma now, a HeyGen stock avatar later) at her normal rate, never slowed;
  the presenter beat's corner change led by the tutorial's pointer arrow, flying and spinning to the new corner;
  the checks beat in the 1:58 layout (the narrator's placeholder large on the left, few words on the right): "87
  issues were flagged. Only 15 required David's help.", then the duties and their AIs; no model version numbers on
  screen (they age the video); the agents header matches the narration ("Claude and its helper agents");
  "no smaller models" goes; Graphics lists the image models whose graphics were kept, and the Hugging Face tools
  are named only where the logs show they ran on this tutorial. *David, 2026-10-18.*
  **Round 3 notes (this reel only):** a new first beat before the tutorial's open, the narrator's avatar (placeholder
  until the HeyGen narrator) saying the presentation reviews an end-to-end process for making videos with AI
  automation at every step and minimal human intervention until final approval, then a whoosh and the entry into the
  open; the beat after the open says "What you just saw was the beginning of a 17-minute tutorial. The work was
  directed by a human and resulted in a list of rules designed to further automate future tutorials. The workflow
  starts with the capture..."; the final-say line adds "For example," and its header becomes "Example Rule", with
  an underline drawn under Rule, Check and Fixed as each is spoken; the Claude subscription is no longer spoken, only
  shown, in parentheses; the presenter beat's arrow larger, reaching past the inset, tan like the frames' outline,
  with a dark grey border and a shadow; "its spice jars and padlocks, kept" goes; the slide-ins with their whoosh at
  the start and end stay. *David, 2026-10-18.*
  **Round 4 notes (this reel only):** a "process line" across the right two-thirds under the title bar, from the
  whoosh at about 0:21: nine numbered circles (Capture, Narration, Edit, Graphics, Presenter, Checks, The Agents, The
  Tools, Rules), each label hidden until its beat, lit during it, grey after; it fades out after Rules (One shot and
  the cost run off it); the headers' numbers match its circles; both versions show it. "The finished tutorial" on
  the open; the opening beat's placeholder stays left; "directed by a human" stays; the length is fine; the
  presenter loses "always by fading" and says "Never obscures what matters"; "**Markers** show David where to look";
  "This reel's narrator" shows once in the whole reel; dead space in the cards (as under "Recording: OBS") is
  tightened. Stills of each beat's layout with the process line go to David before the round 5 build.
  *David, 2026-10-18.*
  **Round 5 layout notes (this reel only):** the process line goes inside the title bar, which grows at its bottom to
  hold it, the line stretching the bar's full width; no separate box; it first shows at about 00:00:39:15 (Capture),
  not at 0:21; the beats that had no title bar (6 Checks, 7 The Agents, 9 Rules) get one, so the title shows whenever
  the line does; titles may differ slightly from the line's labels; the Presenter clip stays; the Tools card's drawn
  track panel becomes a real screenshot of the final tutorial's Premiere timeline with its markers (taken from a copy
  of its project). A few full-size stills for David this round. *David, 2026-10-18.*
  **Round 5 approved, and the narrator chosen:** the Presenter card reads "David's avatar / Position changes as
  needed"; the rest of round 5 stands (the dissolve into Capture included). The narrator's avatar is HeyGen's stock
  **Meilin** (avatar ID <HEYGEN_STOCK_SEATED_ID>), lip-synced to Emma's audio, transparent, in the
  placeholder's slot; the render goes ahead. *David, 2026-10-18* ("It seems like we're close. Are we ready to call to
  HeyGen?"; "Meilin - <HEYGEN_STOCK_SEATED_ID>").
  **The look:** that ID was Meilin's seated look 07, which floats once its chair and table are cut out; David chose her
  standing look **01** instead (rust blouse; look ID <HEYGEN_STOCK_LOOK_ID>, avatar ID
  <HEYGEN_STOCK_AVATAR_ID>), on Avatar IV. *David, 2026-10-18* ("01").
  **Her voice, not Emma's:** Meilin speaks in the voice HeyGen gives her, from the script's text; the reel's whole
  narration moves to that voice so the narrator sounds the same on and off camera (off-camera lines from the same
  voice by the cheapest faithful route, priced for David first if it costs more than her four segments). *David,
  2026-10-18* ("Not emma's voice!"; "She comes with her own voice. Let's use that.").
  **The voice, settled:** her shipped voice (HeyGen's "Claire Lawson Uplifting") is HeyGen's private copy, out of
  reach off camera, and HeyGen credits go only to her four on-camera segments; so the whole narration is ElevenLabs'
  **Constance Lee** (voice ID <ELEVENLABS_STOCK_VOICE_ID>), and HeyGen lip-syncs her segments to that audio. *David,
  2026-10-18* ("whatever allows us to save those credits best is what works for me"; "02 Constance Lee works for
  me.").
  **Round 6 notes (this reel only):** David's own framing of Meilin (Scale 182%, Position 0.1927, 0.6778) is the
  plan's; captions on her beats move right of her; the speed and her gestures stay. New lines: the opening begins "My
  name is Meilin and I am an AI avatar." and ends "The following brief demo is the opening of a tutorial from David
  Baldwin of GiddyUp Data."; after the open, "The full 17-minute tutorial is on GiddyUp Data's YouTube channel. It
  was directed by David and resulted in a list of rules...", with the link on screen; the card says "Directed by
  David". A room-tone bed, as David's hand-made one did: built from the pauses in the narration, seamless, at the
  narration's own floor, from the start with fades, out under the tutorial's sound and the logo music; no white noise.
  *David, 2026-10-19* ("I agree with your three recommendations.").
- **R249 Visual work goes to David first as a contact sheet of real stills.** Before a full build or export of a
  layout change, render stills from the real compositions over the real footage (not mockups), at the moments that
  matter, and send one labelled contact sheet (beat name and full-sequence timecode under each still) plus a few
  full-size frames; David answers from his phone, and the build waits for his OK. *David, 2026-10-18* ("Nice way to
  share btw. Please make a note or a rule or whatever for future."). *Enforced by:* the session plan.
- **R96 Every video ends with the logo outro,** after the avatar finishes speaking: a hard cut to black, then the
  "Outro" sequence in the ProjectMedia bin of `D:\Videos\QuickSeries\AmazonQuick.prproj` (`LogoAnimation.mp4` fading
  in, over the Rossini, William Tell, only). *David, 2026-10-12;* the sequence's second bed (Bach's "Quoniam tu
  solus") is muted on its track there, and David wants only the Rossini. *Enforced by:* `edit_settings.json`
  `logo_outro` (the sequence's times and level); `pipeline.edit.premiere` `logo_outro()` renders it and puts it last
  in `<run>_full.xml`.
- **R97 The avatar is the HeyGen look "David Baldwin (Eye Contact Correction)"** (`<HEYGEN_LOOK_ID>`),
  rendered through the v3 API (`POST /v3/videos`) on Avatar III (`avatar_iii`) for the CSC13 test, chosen from the
  engines' prices (III is the cheapest). *David, 2026-10-12.* *Enforced by:* `pipeline.edit.avatar` (the steps file's
  `heygen` block). **The look is superseded by R219.**
- **R219 The avatar is the HeyGen look "David Baldwin"** (`<HEYGEN_LOOK_ID>`): glasses, the navy
  GiddyUp Data shirt, recorded at 1920x1080 (the old look's footage is 1280x720), all three engines. Not "David
  Baldwin (Eye Contact Correction)" (R97's) nor "David Baldwin -- 1". The intro and outro are rendered again on it.
  It was recorded in front of the same penthouse picture as the others, so HeyGen's matte can show the same faint
  fringe (`runs/qs1a_20261014_full_take01/avatar/bg_test/`: Avatar IV, 10 s, HeyGen's own background replacement on
  the Brand Stage, $0.81). *David, 2026-10-16* ("I would like to rerun the intro/outro using 'David Baldwin' and NOT
  under the other two for HeyGen."). *Enforced by:* the steps file's `heygen.look` (`exercises/qs1_section_a/
  avatar_qs1a.json`), at the re-render; the engine waits on the wallet or a plan (R97's III fits the wallet; IV and
  V don't). **Engine settled by R220, R226 and R229:** the intro and outro on Avatar III through the API (rendered
  2026-10-16), the main body on Avatar IV through the web app on the Pro plan once the look is agreed. Open: David's
  remark on Avatar III (Open questions for David).
- **R95 The pipeline code may go public** as part of the blueprint for David's CSC13 talk (2026-10-20). What gets
  published is a clean copy, not this repo's history, without `runs/`, `audio_cache/` or study frames. It is scanned
  first for secrets, account IDs, and codespace and test-account names. David approves the file list before anything
  is pushed. It goes to a new public GitHub repo and must be live by 2026-10-20. *David, 2026-10-12.* *Enforced by:*
  not built (PLAN, Blueprint). R4 already keeps secrets out of the code. **Hold lifted 2026-10-19 (R210 amended).**
- **R210 The blueprint is on hold.** No work on it until David says. *David, 2026-10-16* ("We're not ready for the
  blueprint yet. Hold off on that."). *Enforced by:* the session plan. **Amended 2026-10-19:** the hold is lifted.
  David released the pipeline for publication on 2026-10-19, as the public repo `ai-video-pipeline`, one of three
  behind giddyupdata.com/blueprints.html for the CSC13 talk. R95 still governs: a clean, scanned copy whose file list
  David approves. *David, 2026-10-19.*
- **R98 The CSC13 test cut is short:** the avatar intro, steps p2.10a to p2.10f of full_take02 (the dashboard prompt,
  with its overlay and the four highlights drawn on it, plus David's line p2.10a2 over the typing, R25) in the clone
  (R94), the avatar outro, and the logo outro (R96). It's built in a new folder, `runs/csc13_test_20261012/`, with its
  own Premiere project; full_take02 and David's project stay as they are. A retake is allowed. Its work blocks go in `docs/TIMING.md`, and the total David quotes
  covers this test only. *David, 2026-10-12.* *Enforced by:* `steps_csc13.json` (`excerpt`, `voice_file`),
  `avatar_csc13.json`.
- **R188 One rulebook, in one place, for every video.** The standing rules for what the viewer meets (sound,
  captions, pointing things out, timing, picture, camera, graphics) live in one file in `D:\Videos\Global Assets\`,
  replacing `motion-styles/CHECKLIST.md` (a pointer is left there). Every builder brief, visual review and
  pre-export check reads it; each rule there gives its numbers, the R numbers behind it and how it is checked
  (automatic, Claude's visual review, or David). RULES.md stays the record of decisions. *David, 2026-10-15* ("I'd
  rather have it in one place. I doubt the AI cares that will be reading the rules"). Replaces R170's checklist file.
  *Enforced by:* not built (`D:\Videos\Global Assets\VIDEO_RULES.md`; `tools/overlay_build.py`, `BUILDER_BRIEF.md`).
- **R189 GPT-6 Astra and Gemini 4 Argon review the rulebook for rules tied to one video or tool.** One call each,
  blind to each other, asking which rules are tied to this video, app, recorder or layout and how to state them so
  they hold for whole courses. Their answers and Claude's merge go to David, not into the file. *David, 2026-10-15*
  ("I want to call Astra and Argon to review the rules to ensure that locally centric rules we've been creating can be
  applied to future videos").
- **R190 Each round, a fresh Claude subagent reviews the stills before David sees them.** Stills at every line,
  mark, caption and overlay, judged against the rulebook (R188), with no outside call; Claude checks each finding
  against the frames. Outside models are for the rules review (R189) and occasional non-Claude checks. *David,
  2026-10-15* ("Can't you call a subagent so that we don't phone out?").
- **R191 The video review experiment: two outside reviewers, blind.** "Gemini" (Gemini 3.1 Pro through Google's API)
  watches a finished round's video with sound; "Argon" (Gemini 4 Argon through OpenRouter) reads 5 frames a second of
  it, no sound. Neither knows of the other or of David's notes; both get the same rubric and return findings by
  timecode, scored against David's notes (a hit is the same issue within about 2 s) and every other finding checked
  against the frames, with each one's cost and time. No Grok. *David, 2026-10-15* ("Let's run both Gemini and Argon
  ... make sure they don't know about each other and then compare the results ... No need to call Grock").
  *Enforced by:* `tools/video_review.py`; `docs/ROUND8_NOTES.md` section 5. **Amended by R193:** Argon reads 2.5
  frames a second.
- **R193 Argon reads 2.5 frames a second, not 5.** A pilot chunk measured about 1,120 tokens a frame ($0.135 for 60
  frames, against an estimate made at 258), so 5 fps would have cost about $10.70 for round 7; 2.5 fps is about $5.35.
  Amends R191. *David, 2026-10-15* (offered 5 fps, 2.5 fps or holding Argon: "2.5 fps"). *Enforced by:*
  `tools/video_review.py frames --fps=2.5`.
- **R200 Every round works the way round 8 did; the outside frame review runs once per video, with a reminder.**
  Every round: David's notes become R numbers before any work, and the rulebook (R188) is what every check and review
  reads; the measured checks run before every export, and a new check must first find the note it came from; a fresh
  Claude subagent reviews the stills before David sees a round, each finding checked in Premiere's own frames (R190);
  Fable reviews the code (R108). Each video's overlays come from the overlay build of 2026-10-15 (ideas from several
  models, R139; the swarm, R149; David's picks in a Premiere review project, R163). Once per video, on its first full
  round (the edit with its overlays), Gemini 4 Argon reads its frames blind (R191, R193: about $5.40 for a 16-minute
  video) and each finding is checked against the frames; it costs money, so Claude reminds David and asks before
  running it. *David, 2026-10-16* (round 8 "seems to be a winning formula"; on Claude's recommendation: "let's go with
  your recommendation but you will need to remind me about the external checking"). Round 8 ran on Claude Opus 5.5,
  as round 7 did (the session logs), so the difference was the way of working. *Enforced by:* VIDEO_RULES.md section
  9; `SESSION_HANDOFF.md`'s next steps.
- **R201 The rulebook in two layers, with the ten wording fixes (R189's review accepted).** VIDEO_RULES.md states
  what the viewer must get, free of tool, app and people names, with the viewer-based numbers (7:1, 56 px, 2 s); the
  house defaults (style numbers and tool bindings: 0.35 s, 1.35x, Page Peel, Epic Pen's look, the fonts, who reviews)
  are listed apart, each naming the rule it serves and the setting that holds it, so a course made with other tools
  keeps the rules and swaps the defaults. The ten contradictions in `research/rules_review/round8/MERGE.md` are fixed
  as worded there. No decision changes. *David, 2026-10-16* ("I agree", to the split, the ten fixes and everything
  else MERGE.md lists). *Enforced by:* `D:\Videos\Global Assets\VIDEO_RULES.md`.

## Quick Sight Journey 1, Section A (the second exercise)

The source is Section A ("A-First Build") of `QuickSight Journey 1 - draft.docx` in the course's Course Design folder,
read-only like the workshop folder (R1). Its code copies go in `pipeline/vendor/quicksight/`.

- **R109 Section A records as the Quick Sight admin, on the Standard edition.** No Author is created (none exists
  since 2026-10-14). The admin's user name is the AWS account ID, so it shows wherever an owner is listed (the
  dataset picker's Owner column); the privacy report flags it and David decides (R56). The exercise and its copied
  Quick Sight code are course material and never go public. *David, 2026-10-14* ("There shouldn't be any difference
  between the admin interface and the author interface for what we are doing here"; "We're running Standard").
  *Enforced by:* `tools/blueprint.py` `NEVER` (`exercises/qs1_section_a/`, `pipeline/vendor/quicksight/`).
- **R110 Login is left out of the first pass.** David signs in by hand, off camera, once in the Quick Sight profile
  (R113), and the video starts signed in. The manual's Login page prints the class password: it never appears on
  screen. *David, 2026-10-14.* *Enforced by:* `steps_full.json` starts at My stuff; `pipeline.capture.browser` keeps the sign-in in the
  profile.
- **R111 Essential Concepts waits for the second pass, if it is made at all** (no screen work; cards would suit it).
  *David, 2026-10-14* ("We may skip").
- **R112 The upload's Windows Open dialog is shown whole,** never intercepted, so the edit can keep it, cut it or blur
  parts of it later. It is driven by the keyboard and UI Automation, never the real pointer (R15); the drawn cursor
  shows the clicks. The folder it shows is a copy of the course Data folder outside OneDrive. *David, 2026-10-14*
  ("show the whole dialog box. That way, we can choose to cut later or maybe just blur stuff out"). *Enforced by:* `pipeline.driver.osdialog` (UI Automation through comtypes),
  the runner's `action.os` clicks (`os_click`), `pipeline.capture.browser` (stages the Data folder, seeds
  `selectfile.last_directory`).
- **R113 Quick Sight takes use their own Edge profile and port (9335),** outside OneDrive, never signed in to
  Microsoft (as R7), toolbar items hidden (as R16). The workshop's Edge (9333) and the course's Chrome (9334) are left
  as they are. *David, 2026-10-14* ("Edge, I think, should be fine"). *Enforced by:* `pipeline.capture.browser`
  (`start quicksight`, `status`; refuses a profile signed in to Microsoft), the step list's `browser`,
  `config.BROWSERS`.
- **R114 Section A has captions,** as editable titles (R102). *David, 2026-10-14.* *Enforced by:* `captions.titles` in
  Section A's `edit_settings.json`; `export.full_without_graphics` gives the first pass its full sequence, where the
  titles go.
- **R115 The full Section A take is recorded now,** Connect to Data and Create Analysis (no Login, R110; no Essential
  Concepts, R111), without a separate test slice; the rework demo (a changed line, cursor move and mark, then a new
  export round from the same take) runs on it. The draft is recorded as it stands, though the student walk's 35
  Section A findings are still unruled. *David, 2026-10-14* ("Go ahead and do the full take for the section A - minus
  the login," after Claude's note on the unruled findings).
- **R116 Privacy masks reach the Premiere export.** Each blur David chooses (R56) is its own clip inside the nest,
  above the recording: a blurred crop of the same frames, so it follows the zoom, and he can trim, move or switch it
  off. It is never baked into the recording. *David, 2026-10-14* (approved Claude's proposal; until then masks
  existed only in the Remotion render). *Enforced by:* `pipeline.edit.premiere` (`privacy_blurs`, `blur_media`: one
  ProRes 4444 clip per recording piece a blur spans, in `<export>/privacy/`, on the nest's blur tracks below the
  cursor; a marker at each blur's full-sequence timecode, R106); `pipeline.edit.ppro.project` bin "Privacy blurs".
  Tested on scratch copies of the CSC13 run (`runs/_scratch_csc13_masks/`); not yet imported into Premiere.
- **R117 Order of work after 2026-10-14: the videos, then the talks, then the blueprint** (R95; its QR code still
  has to open a live repo by 2026-10-20). The CSC13 cut needs no more work from the pipeline. *David, 2026-10-14*
  ("There's nothing I want to do with this"; "I don't wish to work on the blueprint until later"). **Amended by
  R130** (the overlay plan runs alongside the videos) **and R210** (the blueprint on hold; its date open).

- **R118 The video may show steps the manual doesn't have; the manual stays as it is.** Where the screen needs
  more than the manual says, the video does it and the narration says why: Fit to width before the charts are
  moved ("you can also just use the scrollbar"), the scroll to the new flight_date row, Done on the tip that pops up
  after publishing, and, after the manual's last step, a click on the East bar to show the filter action working.
  None of these goes into the manual. *David, 2026-10-14* (on the narration draft's questions: "Don't add step to
  manual, you should mention that in the video. The student may choose to just use the scrollbar"; the East bar:
  "Yes. Don't add to manual"; the added steps: "yes but don't add to manual").
- **R119 Claude may delete the Quick Sight datasets, analyses and dashboards its own runs create,** and nothing
  else: rehearsals and failed takes leave them behind, and they would show in the next take's lists. Only assets
  that appeared during Claude's own run (snapshot before, compare after) are deleted; analyses keep Quick Sight's
  recovery window. Data sources and users are not covered: leftovers are listed for David. *David, 2026-10-14* ("You
  can delete the quick sight data set and analysis and dashboard"). *Enforced by:* `tools/qs_cleanup.py`. The five
  file data sources left by uploads stay as they are (*David, 2026-10-14:* "Don't worry about them").
- **R120 Round 2's line and cue changes are reverted; its SPICE arrow stays.** p2.17 keeps round 1's line ("Both
  charts now fit on the screen, one above the other, so there's no need to resize them."): the added "If yours don't,
  drag a chart's bottom-right corner to resize it." was unnecessary wording. p2.43's cue word is "On" again ("I'll"
  made the click land 1.5 s after "East"; David had no opinion on the word itself). *David, 2026-10-14, on round 2.*
  *Enforced by:* `steps_full.json`; R121 for the arrow.
- **R127 The account name is blurred for the whole video:** `<QUICKSIGHT_ACCOUNT_NAME>` in the Quick Sight header (every
  frame) and in the address bar (wherever the browser bar shows), as standing masks in the Premiere export (R116).
  *David, 2026-10-14* ("Agreed. Blur it."). *Enforced by:* `privacy.patterns` in Section A's `edit_settings.json`
  (the name as a regex that survives OCR's spacing, with the standing decision `blur` and a 4 s merge gap, so two
  missed OCR samples leave no hole); `pipeline.privacy.report` (the exercise's patterns beside the built-in ones; the
  match's own characters get the box, so in the address bar only the name is blurred, not the URL; a finding takes
  its pattern's decision unless `privacy_decisions.json` says otherwise); `plan.py` masks every blur finding; R116's
  clips in the export. The header shows the name at the same place on every page but the analysis editor, so the
  report's findings, not a fixed box, say where and when. Built 2026-10-14 (round 4).
- **R130 The overlay plan runs alongside the videos.** David's motion-style brief (2026-10-14) becomes, first, an
  overlay plan for these videos, worked out from his own Quick Series overlays rather than third-party styles:
  `D:\Videos\QuickSeries\AmazonQuick.prproj`, sequence 03-QuickArch03 (an overlay at 00:00:01:00, a text scroll at
  00:00:09:13, motion graphics at 00:01:14:18, 00:02:23:14, 00:02:42:06, 00:03:00:14, 00:03:45:02, 00:04:55:17,
  00:06:14:07, 00:06:43:19, 00:07:21:14, 00:07:31:10) and the many overlays in 04-Knowledge_Bases04. David finds it
  hard to describe what he wants, so the plan is discussed in detail from those examples. It runs alongside the
  videos, ahead of the talks; the blueprint must still be live by Tue 2026-10-20 (R95). Amends R117. *David,
  2026-10-14* (asked when: "Alongside the videos"; on the brief's style catalogue: "I'm not really sure what this is
  going to get us ... Perhaps we need to have one of our future steps as discussing an overlay plan in more detail").
  **R210 (2026-10-16):** the blueprint is on hold; whether R95's 2026-10-20 date still stands is open.
- **R131 Motion-style answers (David's brief, step 1's questions).** Get away from Motion Array altogether (he uses
  its templates, music, sound effects and footage today). Nobody else works for GiddyUp, so Remotion's licence is
  free (up to 3 people, contractors counted from Remotion 5.0). Fonts: free OFL fonts (Inter, Archivo, Geist) may be
  installed, and fonts already on the PC may be used too; check each one's licence for video. The default energy
  is iart-ai's "Neutral data-story". David's brand colours seed the look's colour tokens. A new composition set,
  not BulletPanel and TitlePanel extended, informed by his Premiere and After Effects overlays (R130). Spotlight
  dimming is R122. *David, 2026-10-14.* The resource assessment is
  `<DOCUMENTS_DIR>\Learning-David-Pc\motion_styles_step1_assessment.md`.
  **Amended by R232 (2026-10-16):** the call to action uses the original subscribe animation from David's Quick Series,
  in place of R209's Remotion rebuild. R232 doesn't name Motion Array, but the animation is the Motion Array element
  R209 set out to replace (`D:\Videos\MotionArray\`).
- **R134 Where the overlay work lives.** The new composition set (R131) goes inside `AIDrivenVideo/remotion/`: one
  Remotion project, the pipeline renders the overlays from the plan, and it ships in the blueprint (R95). The brand
  tokens and the style document go to `D:\Videos\Global Assets\motion-styles\`, where other projects can use them.
  *David, 2026-10-14* ("Your recommendation is fine"). *Enforced by:* not built (the overlay plan, R130).
- **R135 Fonts are installed only with David's OK.** Until then the overlays use fonts already on the PC; when a
  free OFL font (Inter, Archivo, Geist) would be needed, Claude says so and waits. Refines R131. *David, 2026-10-14*
  ("let me know when/if they need installation").
- **R136 Section A's avatar is the intro and outro only;** no picture-in-picture avatar during the screen work
  (R57 holds for this video). *David, 2026-10-14* ("I'll only use Avatar for intro and outro for this video").
  **Superseded by R231 (2026-10-16):** the avatar goes on through Section A's main body as picture-in-picture.
- **R203 Section A's avatar intro and outro are approved as drafted, with the call to action.** The intro carries
  R30's promise, why, roadmap and "So, let's get started."; the outro the recap and the standard call to action. What
  decides the call to action (R30, R68) is whether David wants it in the video, not whether it is "published".
  *David, 2026-10-16* (on `exercises/qs1_section_a/script_avatar_qs1a.md`: "Yes to both. I think by Section A is
  published you mean that I want to have the call to action. I do."). *Enforced by:* `avatar_qs1a.json` (status
  approved); `pipeline.narration.build` and `pipeline.edit.avatar`; `pipeline.edit.ppro.final` built the final
  sequence 2026-10-16 (`runs/qs1a_20261014_full_take01/final_r2/`: the intro, the approved sequence nested, the outro,
  the logo outro, R96), its joins' loudness checked in Premiere's own mix.
- **R204 The logo outro's music plays at about the voice's loudness.** In Section A's final the music sat about 13 dB
  under the avatar's voice (-24.1 against -11.3 LUFS in Premiere's mix); in David's published Knowledge Bases episode
  the logo music measures -27.0 LUFS against his voice's -27.3 over the minute before it. So the music matches the
  voice before it, measured in Premiere's mix, peaks held under -1 dBTP. Applies to every video's logo outro (R96).
  *David, 2026-10-16* ("The music seems a bit low in volume compared to the avatar speech"). *Enforced by:*
  `pipeline.edit.ppro.final` `logo_at()` (the logo file raised through the voice's limiter to the narration's level
  in Premiere's mix; its two channels panned to their sides, `premiere.audio_pan`, since a first-channel clip played
  the left channel alone) and `mix_check` (the logo against the outro's voice, and its stereo); built in `final_r3`
  (2026-10-16: -11.5 against -11.3 LUFS, -1.6 dBTP). The review projects' full sequence (`pipeline.edit.premiere`)
  plays the logo in stereo but at the Outro sequence's own level, a placeholder: the final sets R204's.
  **Confirmed by David on `final_r3`, 2026-10-16** ("Music volume is good."): the limiter's 5.3 dB off the music's
  peaks stands.
- **R137 A quiet click sound on each mouse click.** One short sample at each click the edit draws a ring for, "not
  too loud": Claude's proposal is about -24 dBFS peak, nothing on drawn marks or releases, and David sets the level
  in Premiere if he wants it changed. *David, 2026-10-15* ("what do you think of a click sound when clicking with
  the mouse? Not too loud"). Not built (round 5: a Clicks audio track in the export from the plan's clicks).
- **R138 Attention grabbers, not humour: two or three a minute, each tied to the content.** The word for R129's
  asides is "attention grabber": anything that brings something onto the screen, or says something, that holds the
  eye a little; humour is one kind, not the only one. Not every one is big (ep03's magnifying glass counts). Each
  ties into what is being said (no dancing aliens for no reason), and none leans on a cultural reference (no Spice
  Girls: a viewer in India should get it as well as one in Texas; US cities are fine). The spoken text stays as it
  is unless a line is rewritten on purpose. *David, 2026-10-15.* Sharpens R129; the plan is
  `docs/OVERLAY_PLAN_qs1a.md`.
- **R139 Overlay ideas come from four models through OpenRouter, and Claude shortlists before David looks.** Each
  model gets the script, the inventory of David's own overlays and the rules, and is asked for three or four ideas a
  minute, more than will be used; Claude picks a first "best candidates" list; David reviews that list. The artwork:
  built locally in Remotion (or HyperFrames where it fits) when the layout must be exact (a table laid out just so),
  or generated through OpenRouter's image and video models when there's leeway (spice bottles); a few pennies a call
  is fine, and the cheapest and quickest good result wins. *David, 2026-10-15.* Not built.
- **R140 A panel contrasts with what it sits on:** dark on a light screen, light on a dark one. *David,
  2026-10-15.* Not built.
- **R141 Full-screen chapter markers at a video's section transitions** (before the dashboard is published, say),
  rather than lower-third cards. *David, 2026-10-15.* Not built.
- **R142 Marks first; highlighters for large regions.** Clarity decides what is used: arrows and rectangles for most
  things, and a highlighter (the spotlight dim, R122) only where a large section of the screen is meant, such as the
  whole Data pane, or both sides of a dialog (round 4 at 00:08:18:21, the Create analysis box, had an arrow and a
  rectangle where two highlighters would read better). *David, 2026-10-15.* Not built.
- **R143 Display fonts: Segoe Print for a word list, Courier New for data.** David likes the Segoe Print list of ep03
  (00:00:11:19) and the Courier New of ep04's Remotion graphics (00:01:47:13 on 04-Knowledge_Bases02); more fonts
  are welcome. Both are on the PC; R135 still holds for installs. *David, 2026-10-15.*
- **R144 The overlay ideas go out first, so David reviews the shortlist while Claude works on the edit.** In a
  session that has both, the ideas run and Claude's shortlist come before the edit round, and the shortlist goes to
  David as soon as it exists. *David, 2026-10-15* ("Can you send the work to openrouter first so that we can get
  the list of ideas that you shortlist so that I can review them while you're working on other things such as
  reworking the prproj?"). *Enforced by:* the session order; `tools/ideas_run.py`.
- **R145 Overlay ideas runs compare the mid tier with the frontier tier, on cost and quality.** The same bundle
  goes to the frontier models as well as the mid-tier ones, and the result reports each model's cost and what it
  contributed, so the choice of models for later videos rests on measurements: David plans to do a lot of this.
  Quality is judged twice: Claude's shortlist (which versions it used) and blind scores from non-Claude judges
  (`ideas_run.py judge`), since the shortlister and three contestants are Claude models. *David, 2026-10-15* ("I'd
  like to compare the cost and quality of the mid tier and frontier models regarding our 'interesting overlays'.
  It will drive future video work since I'm planning on doing lots of this."). *Enforced by:* `tools/ideas_run.py`
  (`ask`, `judge`, `costs.json`); the comparison in `research/overlay_ideas/qs1a/SHORTLIST.md` section D.
- **R146 No more OpenRouter calls until David asks.** The ideas run is done and David is working in the shortlist
  (`research/overlay_ideas/qs1a/SHORTLIST.md`); Claude doesn't call OpenRouter again (ideas, judges or images) until
  he asks, and leaves the shortlist file to him. *David, 2026-10-15* ("Please stop calling openrouter. I've already
  done that work in shortlist.md"). Before his message: seven idea calls ($2.77), two judges ($0.46) and five images
  ($0.24). *Enforced by:* Claude; `tools/ideas_run.py` and `tools/gen_image.py` are run only on his say-so.
- **R147 Round 5 answers.** The ".csv" in p1.04 stays under the both-files mark (no mark of its own, no reword, no
  pause); the Visuals pane keeps its highlighter beside the Data pane's (R142 applied to it); overlay panels stay at
  96% opacity; how the map covers the two-minute geospatial stretch is David's to work out later; the blueprint's ten
  answers and the talk's QR code come from him later (R95's 2026-10-20 deadline stands). *David, 2026-10-15* ("It is
  fine as is"; "Good call. Leave it"; "The opacity is fine as is. Don't worry about the 2 minute geospatial stretch
  and how we do the map. I'll work on that later"; on the blueprint: "I'll work on this later"). **Amended by R152**
  (the map is in the overlay build after all), **R179 and R194** (panels opaque, not 96%) **and R210** (the blueprint
  on hold; its date open).
- **R148 Three free OFL fonts are installed: Inter, Caveat and JetBrains Mono.** They are installed on the PC and
  bundled with the overlay compositions (their OFL licences beside them), so the public copy renders the same
  anywhere. On this PC R143's picks stay first (Segoe Print for word lists, Courier New for data) with Segoe UI for
  headings and body; the OFL fonts stand in wherever those Windows fonts are missing (Inter for Segoe UI, Caveat for
  Segoe Print, JetBrains Mono for Courier New). R135's OK, given for these three. *David, 2026-10-15* ("I would like
  the extra fonts installed," on Claude's question about the public copy). *Enforced by:* `remotion/src/overlays/fonts/`
  and `kit.tsx`'s font stacks.
- **R149 Section A's overlays are all built and judged in Premiere, by a swarm.** Every idea is generated and placed
  on the round's full sequence in a separate Premiere review project, and David judges them there: the shortlist's
  new ideas, its changes to planned spots and its runners-up (`research/overlay_ideas/qs1a/SHORTLIST.md`), and the
  overlay plan's twenty spots (`docs/OVERLAY_PLAN_qs1a.md`). Anything that sits over the screen is transparent. The
  build is swarmed: outside models (OpenRouter, the provider keys DeepThink uses, Abacus) and parallel Claude
  builders, and each builder's cost, time and keep rate is logged, since the swarm goes into the talks. Artwork is
  built in Remotion (or HyperFrames), or generated by image and video models and brought in through Remotion. One prop
  is tried in a few looks before the rest are made. Spending is capped at $25 cash across the paid APIs for this
  round; Abacus credits are reported separately. npm installs into `AIDrivenVideo/remotion/` are fine. This is David
  asking for OpenRouter calls again (R146), for the build. *David, 2026-10-15* ("generate every idea in the
  shortlist.md and overlay in Premiere. We'll judge it by what it looks like there"; "transparancy is going to be
  important in many cases"; "I want to swarm this. This will actually be good for the talks"; "$25 seems wise";
  "NPM installs are fine"; "Testing first is good"; on the twenty spots: "Didn't we say to move forward with all of
  them?"). *Enforced by:* the build plan, `docs/OVERLAY_BUILD_PLAN_qs1a.md` (not built yet).
- **R150 Abacus video is made in the Studio, in a browser profile David signed in to himself.** Abacus has no
  video API (checked 2026-10-15: the Studio runs on private web calls, the Python SDK has no generate call, and
  RouteLLM lists no video endpoint), so the Studio is used through a separate, dedicated browser profile that
  David signed in to himself, and David confirms each paid step. Claude never touches the sign-in (R4) and never
  enables API metering or buys credits without asking. *David, 2026-10-15* (offered by hand or by Claude: "(b)";
  "I'll leave the Abacus sign-in open so that we can use it as needed moving forward"). *Enforced by:* the build
  plan.
- **R151 The build plan is reviewed before the swarm runs, by Fable 5.1 and Gemini 4 Argon.** A Fable subagent and
  one non-Claude critic, Gemini 4 Argon (the newest Gemini; DeepThink still defaults to gemini-3.1-pro-preview), poke
  holes in the plan and offer alternatives before anything is built. Outside models for this work are each vendor's
  newest. *David, 2026-10-15* ("do you think we should make a call to a subagent - Fable - to ponder our plan and
  poke holes in it or offer alternatives?"; "We should use the later models for these. We have a later Gemini model
  that will give us better results"; "The reviewers are fine").
- **R152 The map stays up through the whole geospatial stretch, clear of what matters on screen.** Section A's
  two-minute geospatial stretch (00:04:05 to 00:06:25 on round 5's full sequence) is in the overlay build after all:
  the map (the overlay plan's spot 7, the shortlist's B2 to B4) may stay up the entire time, provided it never covers
  what the viewer needs (the click targets, the marks, the fields being set, the captions). Amends R147's "I'll work
  on that later". *David, 2026-10-15* ("The two minute mapping stretch is something that I want to address. I'm ok
  with having the map up the entire time provided it doesn't get away of important stuff"). *Enforced by:* the build
  plan (placement from the plan's click targets and marks over the stretch). **Amended by R175:** the map builds
  with the line (the coordinates fade as it arrives; the states, latitude lines, longitude lines and cities come with
  their words).
- **R153 Overlay resources go into a library for later tutorials, and existing art is reused.** The overlay work is
  meant to serve many tutorials in this style, so what's made here (compositions, icons, generated art, sounds) is
  kept where later projects can pick from it, not only inside this video's project; nothing that already exists is
  remade (the spice jars and padlocks generated on 2026-10-15 in `research/overlay_ideas/qs1a/art/` are used as
  they are). *David, 2026-10-15* ("My hope is to use our efforts here to make many tutorials using a simliar style.
  That means that resources can be reused ... I also want resources in a library that can be picked form in the
  future so that we don't reinvint the wheel"; "If we have existing artifacts such as spice jars and padlocks, we
  need to keep them and use them"). Extends R134. *Enforced by:* the build plan.
- **R154 One catalogue says where every overlay asset is and what it cost.** `D:\Videos\Global
  Assets\motion-library\CATALOG.md` lists every asset made for the overlays (compositions, icons, generated art and
  video, sounds, fonts) with where it lives, what it is, what made it, its licence, its cost and the videos that use
  it, and every paid run (ideas, reviews, builders) with its cost and where its outputs are. Nothing paid for is
  deleted: unpicked versions stay where they are and stay listed. The library itself (R153): compositions in
  `AIDrivenVideo/remotion/src/overlays/`, art, icons and sounds in `D:\Videos\Global Assets\motion-library\`, style
  rules in `D:\Videos\Global Assets\motion-styles\STYLE.md`; builders' versions stay in the review area until David
  picks. *David, 2026-10-15* ("I do ask that you record somewhere so that we can easily see where the
  bodies are buried in the future. I don't want to lose assets we spend money and time on if they look like they'll
  be useful in the future"; "The above is fine"). *Enforced by:* the catalogue; pointers in `AIDrivenVideo/CLAUDE.md`
  and the workspace's `context-index.md`.
- **R155 Captions sit above every overlay.** A chapter card or any overlay must never cover the captions; the caption
  layer is the top of the stack. *David, 2026-10-15* (the Part 1 card at 00:00:01:02 "obscures the captions. Captions
  should be on top"). Not built: the review project puts the overlay tracks above Caption titles.
- **R156 1.35x stays the norm, but small typed text may get more zoom.** Where the viewer must read something small
  being typed (the dataset name at 00:06:28:16, the analysis name at 00:11:34:02, the dashboard name at 00:14:17:19),
  the camera may go to about 2x and pan; other places may qualify. Amends R125. *David, 2026-10-15* ("135% should be the
  max normally ... at 00:06:28:16 is one of the places we might think of breaking that guideline ... I zoomed in to
  200% and panned a bit ... it looked ok and, I think, would be helpful"). Not built.
- **R157 When an action changes something on screen, the viewer sees everything it changes.** A guideline, not an
  absolute: a minor change in a corner may stay off screen, but the East bar's filter at 00:14:59:19 needs both the
  bar chart and the line chart in view, and the claim at 00:11:18:25 that both charts fit needs them shown fitting. The
  camera zooms out as needed, and a caption moves when it would cover what changes. *David, 2026-10-15* ("when an
  action impacts something on the screen, everything that is being impacted should be seen. I guess I'd call that more
  of a guideline"; "The CC is covering the portion of the line chart ... the CC will need to go somewhere else"). Not
  built; extends R133.
- **R158 The overlay sound pass stays.** Each overlay's sound cues the viewer that something worth noticing is happening
  (David unmuted it and liked it: clicks, explanatory notes, section cards); a ticked item that appears gets its tick
  sound too (the rename lines at 00:12:12:15 and 00:12:38:27 had none). *David, 2026-10-15* ("I like them. The
  different sound effects help cue the viewer ... It was intuitive to associate the noises used with the action"). Not
  built: the sounds are switched off in the review project and one sound per overlay is placed.
- **R159 A tip or a highlight next to an overlay is a rectangle, not the dim.** Where an overlay graphic is on screen,
  the spotlight dim (R122, R142) would darken it and lose its contrast, so the thing to look at gets an R51 rectangle
  instead (the tip at 00:14:37:12). Refines R142. *David, 2026-10-15* ("I'm concerned that the graphic will be less
  visible if we darken the rest of the screen"). Not built.
- **R160 Explain data source against dataset, with new narration.** At 00:00:24 (p1.02) the video explains what a
  data source is, what a dataset is, and how they differ, with an example of each (the guide's glossary; the plumbing
  analogy: the source is the pipe, the dataset the water drawn through it; one source feeds many datasets; uploaded
  files keep no connection), in new lines voiced with David's ElevenLabs clone and a bigger overlay than the one-line
  chip. *David, 2026-10-15* ("There should be a bit more explanation here and thus a bit more overlay ... we'll need to
  send to 11labs for a little more vocal"). Not built: the wording is to be drafted for his approval.
- **R161 Overlays are sized for a phone held sideways (landscape-first).** At 1080p: body and label text at least
  56 px (was 40), headings 60 (was 46), Courier New data text at least 52 px (its small x-height reads like 44 px
  Segoe UI), nothing under 48 px; icons at least 64 px; a labelled diagram at least 480 px wide (or 360 px tall);
  strokes at least 4 px. Captions stay 48 px (R126). Portrait viewing isn't the target: there no text under about
  55 to 95 px reads comfortably. *David, 2026-10-15* (picked "Landscape-first" from the phone research: no published
  standard covers text in video on phones; the numbers come from reading thresholds (ISO 9241-303's 16 to 22
  arcminute capitals, Legge's 0.2 degree x-height) on a 65 to 73 mm tall landscape video at 30 to 35 cm, cross-checked
  with the BBC's 67.5 px subtitles, CEA-608's 44 px and the UK and French TV-advert minimums). Answers his notes 3
  and 4. *Enforced by:* `remotion/src/overlays/tokens.json` (`type.minPx`, `type.sizePx`; graphics floors in
  `layout`), the harness's lint (`tools/overlay_review.py`). Not built.
- **R162 The data source passage (R160) is the full version (about 46 s), and David reviews its words first.** No
  line goes to ElevenLabs until he has read it with the lines before and after it. *David, 2026-10-15* ("Full but I
  need to review the text before you send to 11labs. Also, be sure to include before and after text"). He approved
  the draft as written the same day ("Voice it as written"; `research/overlay_build/qs1a/DATASET_PASSAGE_draft.md`):
  p1.02 loses its last sentence and the new line is the line-only step p1.02a.
- **R163 David's picks for Section A's overlays (review round 1).** The version he keeps of each piece, the props
  answer (the spice jars coded, not video) and the pieces he dropped (the Interactive / Pixel-Perfect panel, the
  pin-icon text chip) are listed, with his reasons, in `research/overlay_build/qs1a/PICKS_DAVID_r1.md`; they are the
  talks' keep rate. *David, 2026-10-15 evening* (by track in the round 1 project). Not built: the picks go into
  `exercises/qs1_section_a/overlays.json` next session. **Amended by R169:** B01 is Builder A's version, not
  Builder E's.
- **R164 Informational overlays have no see-through background.** The screen showing through an explanatory graphic
  distracts; transparency stays possible elsewhere (a cut-out prop, a drop-in), but an overlay that informs sits on
  a solid panel. *David, 2026-10-15* ("I find the transparancy of V8 a little distracting and would prefer none. I
  guess I have a leaning to not use transparancy for informational graphics since the 'shining through' of
  underlying stuff on the screen is a bit distracting. I'm not saying we'd never use transparancy"). Whether R147's
  96% panels count as see-through is to confirm with him. Not built. **Settled by R167** (the 96% panels don't
  count), **then R179 and R194** (the panels opaque).
- **R165 An overlay earns its place, and a picture beats words.** No overlay where the screen already says it
  clearly (a highlight on the interface's own labels, 00:08:26 in round 1). Where a graphic can say it without text,
  it does: reading takes attentive processing, so text is slower to understand (00:05:01). *David, 2026-10-15.*
- **R166 What David's picks taught (overlay design).** Bigger reads better, within R161 (several picks); different
  kinds of text get different colours, such as a setting's name against its value, so the eye needn't read to tell
  them apart (00:13:32); motion carries meaning, so in a group move every item or none (one spice jar moving begs a
  reason, 00:06:52); nothing arrives while a click ring or mark is being drawn (00:05:01; R51's collision report);
  never cover what the line is about (00:09:36's total over the line chart); keep proportions (narrow charts looked
  stretched, 00:11:09); a panel that opens at its full size tells the viewer more is coming (00:03:10); a graphic
  that mirrors the screen's own layout reads at once (00:15:05); a drawn arrow helps the eye track (00:09:41); a
  graphic placed inside the dialog keeps attention on the dialog (00:02:50). Times are on round 5's sequence (the
  round 1 review project). *David, 2026-10-15.* Not built: a checklist for builders' briefs and Claude's reviews.
- **R167 The house panels at 96% opacity are not see-through under R164.** R164 is about the builders' see-through
  backgrounds (and anything as transparent); the library compositions' panels stay at R147's 96%. *David,
  2026-10-15* ("I'm ok with the house panels at 96% opacity"). **Superseded by R179 and R194:** the house panels
  are opaque; 96% is retired.
- **R168 The pieces R163 didn't name.** A05 (text date to real date): Builder E's version (V4 in round 1). A11 (the
  region map): as it is. C01 (a second document retracts): dropped (A01 is kept). S06 (MM = month chip): dropped (B01
  replaced it). The padlock: the coded version (S19, V5); the video (S19v) leaves the video but stays in the library
  and the catalogue (R154). A14s: dropped (A14 kept). The library pieces stay as built; S12 and S16, the text-only term
  chips, stay too: R165 doesn't bar a text chip where no picture says it ("I don't see how we could have a picture
  that communicates what we want to communicate"). The click sound's level stays (-24 dBFS peak, R137). *David,
  2026-10-15.*
- **R169 B01 is Builder A's version: a panel opens at its full height at once.** The viewer sees the empty space and
  expects more to come; a preference for panels that will grow (R166). Replaces R163's B01 pick (Builder E); R164
  applies (an opaque panel), and it sits close to what the viewer looks at, his reason for E's version. *David,
  2026-10-15* ("I prefer the Argon version because I want the full height right away. That way the user sees the empty
  space and expects additional information to display. That is a preference").
- **R170 Claude makes the post-pick fixes; in the talks that is the human in the loop, written down as rules.** The
  fixes David asks for after his picks are Claude's, not sent back to the builders. In the talks it isn't "training":
  the models don't change; David's preferences become written rules (R164 to R169 and on) that go into every builder
  brief and Claude review through a checklist, built this round. Whether later videos go faster is measured (the next
  video's first-pass keep rate and fix requests against Section A's), not assumed. *David, 2026-10-15* ("I want you to
  make the fixes. Regarding the talk, this is part of human in the loop ... training the AI with my preferences";
  on the rulebook wording: "granted"; on the checklist: "agreed"). **Amended by R188:** the checklist is the one
  rulebook, `D:\Videos\Global Assets\VIDEO_RULES.md`.
- **R171 What the narration names on screen is pointed out.** In most cases, information on the screen that a line
  refers to gets a visual pointer (an R51 rectangle or an arrow), and one mark covers everything the line names
  together: latitude and longitude both at 00:04:50:24, the Geospatial type's "State" at 00:05:44:01, the X axis well at
  00:10:03:02 (round 6's full sequence). Extends R85 and R142. *David, 2026-10-15* ("This is another case of info on
  the screen being referenced which, in most cases, should result in the information being pointed out visually").
- **R172 A click waits until the words it depends on are read, and what is read stays clear of the frame's edge.**
  At 00:02:59:01 (round 6) the Select a data type dropdown was clicked before its text was read (00:03:02:07), so the
  viewer never saw the text: the rectangle holds on the text until it is read, then the click. Text near the bottom
  breaks R123's title-safe; zooming in and panning up is preferred, for readability too. Refines R128. *David,
  2026-10-15* ("The click should be delayed until the text has been read"; "One way to address this would be to zoom
  in which would be fine and even preferable for readability").
- **R173 A recording flaw is corrected in the edit, not retaken, where it gets in the viewer's way.** Edge's "Saved
  info" list over the Edit date format box (00:03:38:15 to 00:03:57:15, round 6) covers the Validate button the line
  talks about: it is covered with a clean picture of the same place from before it appeared, a correction layer, as
  David would build a correction sequence in Premiere. Where a flaw is in nobody's way, it stays (the same list over
  the Publish dashboard box, 00:14:56). Typed text shown pasted is a fine fallback where the typing can't be shown
  clean; typing is preferred, since it shows movement. *David, 2026-10-15* ("retake or fake it ... I'd probably create
  a 'correction' sequence in Premiere"; "It doesn't bother me there because it isn't getting in the way of anything the
  viewer needs to be looking at"; "Here you paste instead of type. That is fine! ... I prefer the typing as it shows
  some movement, but pasting is a reasonable fall back").
- **R174 A caption keeps the side of the one before it.** A caption that finishes the previous one's sentence doesn't
  jump across the screen ("them." at the far left at 00:12:05:00, round 6, after a caption at the far right) unless
  its place there would cover what matters. *David, 2026-10-15.*
- **R175 The map through the geospatial stretch builds with the line.** The coordinates (00:04:52:15, round 6) fade
  when the map arrives (00:04:56:00); the map comes alone, without the orange pin dropping on Houston; the three states
  (Texas, Illinois, New York) light up with dest_state's rectangle (00:04:58:21), the latitude lines come with
  latitude (00:05:34:00), the longitude lines with longitude (00:06:08:13), and the cities with dest_city (about
  00:06:30:10), held until the map leaves, so they're on screen long enough to read. The pin-icon zoom (B04, 00:05:40)
  stays. Amends R152's placement plan. *David, 2026-10-15* ("the bit about the lat long coordinates sticking around for
  the whole time seems odd. Better that they should fade").
- **R176 Labels and their values line up row by row.** In a two-column overlay (A14's Renamed list, A16's defaults),
  each label sits on the same line as its value. *David, 2026-10-15* (00:13:19:16 and 00:14:20:18, round 6).
- **R177 The whole mix is raised to YouTube's loudness by one shared gain.** The voice and every sound effect go up
  by the same amount, so the program sits near -14 LUFS integrated (YouTube's playback level; David's Quick Series
  episodes measured -25.5 and -26.5) and the balance he approved stays; a true-peak limiter at -1 dBTP keeps the
  loudest syllables from clipping. The gain is in the pipeline's audio, so his Premiere mixer stays at 0 dB and the
  export adds no loudness normalization of its own. *David, 2026-10-15* ("please raise ALL of the sound to typical
  YouTube volume ... the voice should be increased by x% ... The sound effects should have their volume raised by
  x%"). Keeps R137's click level relative to the voice. Measured 2026-10-16 in the mix Premiere itself renders
  (Section A's final, GOTCHAS "Loudness as Premiere plays it"): the narration plays at about -11.3 LUFS, not -14,
  because `pipeline.edit.loudness` measures the mono files and Premiere plays them in both channels at full level.
  Section A stays as approved (YouTube turns a loud video down to its level; true peaks hold at -1.4); the next video's
  loudness pass should aim 3 dB lower, checked in Premiere's mix.
- **R178 Review round 2 answers.** Kept as Claude made them: A14 fully opaque, gold rather than orange in B01's minutes
  line, C05's + and = and A09's outline, S04's options in their order, C05's illustrative numbers, A13 below R161's
  diagram size; the Publish dashboard box's autofill list stays (R173). *David, 2026-10-15* ("These are all fine").
  **Amended by R196:** for later work an overlay keeps the screen's order; S04's order stays as built in Section A
  (R195).
- **R179 Text contrast is measured: at least 7:1 for all text against what is right behind it.** WCAG's enhanced
  level, for overlays, captions (R192) and any text the pipeline draws. Nothing see-through sits behind any text,
  panel or element inside a composition (R164 reaches inside compositions). Claude's reading, 2026-10-15: the house
  panels go opaque, replacing R167's 96%, because at 96% the screen showed through SourceFlow's panel and R180's
  muted gold measured 6.24:1 over a white screen (7.05:1 opaque); the wells (the boxes behind an option's or a
  card's text) moved a shade off the panel so the heading and body keep 7:1 on them. Reversible in the tokens. *David, 2026-10-15, on overlay round 3* (00:00:37:22 and 00:01:04:25 on round 7's sequence: SourceFlow's
  "no data inside" and "no connection", grey text on the see-through grey pipe; "7:1"; "It would be helped if there
  was no transparency on the grey background but even then I think the text would need to be lighter"). *Enforced
  by:* `pipeline.edit.checks` tokens (every text colour pair in the look's tokens and the captions' settings) and
  text_contrast (OCR'd words of an overlay on its settled stills, ink against what is behind it, and the overlay's
  alpha opaque behind it), in `tools/overlay_review.py check`. Built 2026-10-15 (round 8): note 1 found.
- **R180 The palette at 7:1.** Muted gold on the dark variant `#d0b68b`, copper headings on the light variant
  `#7b4622`, teal `#335964`; orange for shapes only (marks, ticks, pins, outlines), never for text. *David,
  2026-10-15* ("Yes", to the nearest shades that pass). *Enforced by:* not built (`giddyup.tokens.json`, STYLE.md's
  colour table; A18's "East" and C06's stamp lose their orange text).
- **R183 Typed text that flickers is shown pasted.** Where Edge's autofill preview or anything else makes typed text
  blink, the typing is dropped and the text appears whole: R173's fallback becomes the rule there. Typing stays the
  default where it shows clean. *David, 2026-10-15, on round 7* (00:03:38:13, the format box: "Better to simply
  paste in the text rather than to have the blinking effect"). *Enforced by:* a step's `drop`; the check
  `pipeline.edit.checks` flicker (a typing step's field returning to an earlier picture three or more times in what
  the edit shows; Edge's preview alternates two frames each). Built 2026-10-15 (round 8): note 4 found; p1.14 dropped.
- **R185 An overlay's last part stays up long enough to read.** Its last revealed part stays at least 2 s, plus about
  0.3 s a word past five words, before the overlay's exit. If that runs into the next overlay, the next one waits up
  to 1 s past its word; anything longer flags both. *David, 2026-10-15, on overlay round 3* (00:10:15:11 to
  00:10:17:12, C05's total up under a second; "let's say 2 s"; on the reading allowance: "sounds good"; on the
  collision default: "Yes"). *Enforced by:* `pipeline.edit.checks` hold_for_reading (in `tools/overlay_review.py
  cards`) and display_time (in `check` and the collisions report). Built 2026-10-15 (round 8): note 6 found; C05 and
  ten more held; S09, C04 and A18 flagged (the next piece, or the video's end, is too close).
- **R187 Mixed fonts on one line share their capital height and baseline.** Where two fonts sit on one row (a label
  in Segoe UI, a value in Courier New), each is sized so their capitals are the same height, on one baseline. At
  56 px Segoe UI that means Courier New at about 64 to 66 px; the panel widens, or the value wraps under its label.
  *David, 2026-10-15, on overlay round 3* (00:13:24:07, A14 and A16: "Can you see how the text to the right is lower
  than the text on the left?"; round 3's 4 px lift centred the rows, but Courier New's 29 px capitals against Segoe
  UI's 38 still started lower). *Enforced by:* not built (the alignment check: per row, capital tops and baselines
  within 2 px; columns' left edges within 2 px). Built 2026-10-15 (round 8): `pipeline.edit.checks` alignment
  (baselines from words with no descending letters, capital tops from words starting with a capital, columns by ink
  with an allowance for letter shapes), in `tools/overlay_review.py check`; it found note 8 on round 3's A14 and A16.
  It doesn't cover labels placed on a map or picture (A11's region labels), R195.
- **R194 Panels are opaque: R179's reading confirmed.** The house panels, wells and chapter cards stay fully opaque;
  R167's 96% is retired. *David, 2026-10-16, on overlay round 4* ("Yes, let's make panels opaque"; the panel at
  00:00:34:09 on round 8's sequence). *Enforced by:* `giddyup.tokens.json` 1.2.0; the contrast check's see-through
  test.
- **R195 Round 8 and overlay round 4 answers: Section A's edit is final.** Round 8 with overlay round 4
  (`runs/qs1a_20261014_full_take01/overlays_review_r4/`) is the cut, with no more edits; the avatar intro and outro
  (R136) are added to it. Kept as built: the three overlays R185 flags (the SPICE card at 00:07:26, Cancel to Close at
  00:07:57, the last one at 00:15:44, each 0.3 to 0.4 s short); the defaults overlay's values under their settings
  (00:14:20); the Properties pane at 1.35x (00:13:38 to 00:14:32); the last 39 s at full frame (00:15:07); the new
  visual's crop (00:10:56, R197) and the data-prep options' order (00:02:14:21, R196), neither worth a re-render; the
  map's region labels as they are (00:11:13:27), so R187 doesn't reach labels placed on a map. Times on round 8's
  sequence. *David, 2026-10-16* ("The results this time are quite good. There were subtle changes made here and there
  that were very much for the better. I'm quite happy with the video as is and would be good with no more edits";
  "Yes"; "It's fine"; "It looks fine. No alignment adjustments are required"). **Amended by R231:** the avatar's
  picture-in-picture goes over the main body too, with R136 superseded; the approved cut itself is nested untouched.
- **R196 An overlay that shows what the screen shows keeps the screen's order and layout.** Options are listed in
  the order the screen lists them; a value sits where the screen puts it (under its setting when the screen does). In
  every video, where it applies: it reads at once (R166), and a mark and its overlay twin land on the same side.
  *David, 2026-10-16, on overlay round 4* (00:02:14:21: the data-prep options overlay listed its options opposite to
  the dialog, so two rectangles sat on Edit/Preview data on opposite sides: "our 'for all videos' set of rules should
  have a rule saying that overlays should reflect screen order layout where applicable"; on the defaults overlay's
  values under their settings, 00:14:20: "it now more exactly reflects the layout of the screen, but also because it
  uses the space better and has larger text"). Replaces R178's kept order of S04 for later work; Section A's stays as
  built (R195). *Enforced by:* the builders' briefs (VIDEO_RULES G21); Claude's visual review.

## Superseded text (the newer rule won)

| Old text | Where | Replaced by |
|---|---|---|
| S6 and later wait until after 2026-10-08; send nothing to Claude, change no repo | R2; PLAN; CLAUDE.md | R64 (start now) |
| Zoom cap 1.5x with 1080p capture | SPEC §1.2 item 6, §7.3; CLAUDE.md "up to 1.5x"; `zoom.rule` | R42 (2x) |
| Zoom eases in over 0.6 s, finishing as the cursor arrives | SPEC §7.2 rule 7 | R45 (linear) |
| Zoom only groups that dwell 4 s; one zoom per group | SPEC §7.2 rules 1–3 | R40–R44 (beat-based camera, `camera.py`) |
| "About 1.2x while the work stays in the page"; zoom level 2.0 | STYLE_PROFILE §8.1; `zoom.level` | R42 (rest 1.35x, tight spots to 2x) |
| Mark hold "at least 2 s" | old CLAUDE.md | R50 (1.8 s floor) |
| "×N" speed badge | SPEC §6.5; `EditPass` | R37 (no badge) |
| S4 zoom starts about 0.35 s before the clause | STYLE_PROFILE §1 | R41 (in at once when the full-frame need ends) |
| Every cut gets a 4-frame crossfade | SPEC §6.4 rule 6 | R34 |
| Holds over 2 s are flagged; retake if a hold is over 2 s | SPEC §1.2 item 2, §8 warnings; PLAN appendix §10 | R20, R36 (`hold_warn_s` 6) |
| `pause_after_result` 0.8 s | SPEC §6.4 table | `edit_settings.json` (0.5); numbers live there |
| R55: approve a 540p proxy before the final render | R55; `pipeline.edit.review`, `final` | R73 (review in Premiere) |
| R27: about one dry aside a minute, with drop-ins | R27; NARRATION §6; PLAN Phase 1 | R65 (no humor) |
| David adds the Page Peel by hand (R83's transitions import as a dissolve) | R83; GOTCHAS | R105 (the pipeline places them in Premiere) |
| Outlined and shadowed caption text | R52 | R101, R102 (David's plain TitleTest look) |
| R65: no humor, the script is straight | R65; NARRATION.md §2 | R129 (a little humor, with overlays) |
| The camera's first line starts after the intro's dissolve; the avatar is gone before anyone else speaks | R100 | R205 (the avatar speaks the main body's first sentence) |
| The logo's music at the outro clip's level, keeping the Outro sequence's balance | `pipeline.edit.ppro.final` | R204 (at the voice's loudness) |
| A dialog that can't fit at 1.35x: zoom out, to full frame if needed | R123 | R125 (1.35x the norm; a dialog at its own size, or a pan) |
| A click target's mark held to the end of its sentence, then the click | R49, R50 | R128 (drawn while talking; the click on the name) |
| Caption 40 px (TitleTest look) | R101, R102 | R126 (48 px, plain) |
| Caption box #5E5E5E (#5F5F5F in R52): 6.48:1 with white text | R52, R101, R102 | R192 (#575757, 7.23:1) |
| `motion-styles/CHECKLIST.md` as the builders' and reviewers' checklist | R170 | R188 (`Global Assets/VIDEO_RULES.md`) |
| House panels at 96% opacity | R147, R167 | R179, R194 (opaque; confirmed by David 2026-10-16) |
| S04's options in the order David kept, opposite to the dialog's | R178 | R196 (the screen's order; Section A's stays, R195) |
| No zoom out from 1.35x without the whole screen being needed | R125 | R197 (zoom out while what's talked about stays readable) |
| Motion-style work after the talks and blueprint | R117 (as Claude read it) | R130 (alongside the videos) |
| Highlights: rounded #ED7D31 outline, 3 px, 150 ms fades | SPEC §7.4 | R48, R51 (text highlights in S6 are still to be styled) |
| Click ring #ED7D31 | SPEC §7.1; `constants.ts` | R51 (#F16F05) |
| Cursor and marks at a constant size under zoom; square 6 px Epic Pen marks | R46, R51 (first versions) | R46, R51 (grow with zoom; David's live look) |
| "No fixed line limit" vs a 42 × 2 limit | STYLE_PROFILE §8.4; `edit_settings.json` | R59 (guidelines) |
| Captions exported as SRT, burning optional | SPEC §8 | R52 |
| Caption box #1E1E1E at 88%, square corners | `edit_settings.json` | R52 (#5F5F5F opaque, 7 px corners) |
| 2 s of silence between lines is fine | planner behaviour under R25 | R25 (0.4 s default; up to 2 s only with screen activity) |
| `pause_at_part_boundary` 1.5 s (1.9 s between lines at a part change) | SPEC §6.4 table; `edit_settings.json` | R82 (0.8 s, about 1.2 s between lines) |
| Upload by hand; "there is no API uploader" | SPEC §2 stage 8; PLAN appendix §11 | R5 (private uploads allowed; public by hand) |
| Editing a line regenerates it and its two neighbours | R32 | R99 (neighbours are unbilled context; only the changed line is voiced) |
| No call to action because the video isn't published | R68; VIDEO_RULES W6 | R203 (whether David wants it in the video) |
| The map "I'll work on that later" | R147 | R152 (in the overlay build), R175 (it builds with the line) |
| B01: Builder E's version | R163 | R169 (Builder A's, full height at once) |
| Argon at 5 frames a second | R191 | R193 (2.5) |
| The avatar in the intro and outro only, no picture-in-picture | R57, R136; PLAN | R231 (picture-in-picture through Section A's main body) |
| The look "David Baldwin (Eye Contact Correction)" | R97 | R219 ("David Baldwin") |
| No HeyGen subscription; Avatar III until a plan is chosen | R221 | R226, R229 (Pro plan; Avatar IV in the web app once the look is agreed) |
| The avatar leaves when the main body's first sentence ends, by an exit David picks | R205 | R215, then R231 (it zooms down into the oval and stays) |
| The intro's avatar leaves by dissolving (exit C) | R215 | R231 (the zoom-down into the oval, no dissolve, no gap) |
| The avatar may slide anywhere while it speaks | R208 | R224 (never the box), R232 (the stage's move to the left third) |
| The avatar and its background shrink together into the box straight from full frame | R220 | R232 (first the avatar moves over the still cityscape into the left third beside the card; into the oval at the hand-over, R231) |
| An openly artificial brand stage; the white neon sign; B1's teal wall | R218, R223, R225; SESSION_HANDOFF | R232 (the Quick Series cityscape) |
| Teal inside the picture-in-picture oval | R224, R225, R231 | R232 (the cityscape) |
| The oval at ep04's spot, (0.9266, 0.8236) and mirrored | R222; VIDEO_RULES X6 | R231 (further in from the edges; 54 px in round 6) |
| The subscribe card rebuilt in Remotion, the brand look | R209, R211 | R232 (the original Quick Series subscribe animation, placed as in QuickArch03) |
| Away from Motion Array altogether | R131 | R232 (for the call to action's subscribe animation) |
| The write-on cream; a soft shadow if it falls under 7:1 | R212, R228 | R232 (the url footage in its own copper, as in QuickArch03, exempt from 7:1) |

## Open questions for David

Where two live rules meet and David hasn't decided (found in the consistency pass of 2026-10-16 night,
`research/reviews/rules_consistency_20261016.md`). Round 6's other decisions (the left third's size, the window's
shape, the call to action's timing, the oval's inset, how often the box moves) are picks, not conflicts: they are in
`stage_review_r6c` and `pip_review_r2e`'s READMEs.

1. **Captions through the call to action:** R213 keeps captions bottom centre while the avatar is full frame; round 6
   puts them middle left, at QuickArch03's place, because the subscribe animation and the url hold the bottom
   (`stage_review_r6c` decision 4).
2. **The subscribe animation's lettering and 7:1:** R179 and VIDEO_RULES G6 ask 7:1 for all text, exempting only the
   logo and the write-on (R232); R232 also asks for the original animation placed as in QuickArch03, where the tip of
   "Thanks for Watching!"'s "T" measures 1.7:1 at the shirt's edge (decision 7: widen the exemption, or accept it).
3. **The subscribe animation's sound:** R158 and VIDEO_RULES S9 give every overlay its sound cue; R232's original,
   placed as in QuickArch03, plays with no sound (decision 6).
4. **The outro's start:** R100 and R205 start the outro's voice 0.2 s after the dissolve into it, and R34 (VIDEO_RULES
   T3) gives the dissolve into the recap 0.8 s; with R232's mirror, round 6 has no dissolve there (the oval fades in
   and grows after the main body's last caption) and counts the 0.2 s from the main body's end instead (decision 3).
5. **Later videos:** R231 replaces R57 for Section A only, and R232 doesn't say. Do the picture-in-picture through the
   main body and the Quick Series stage hold for every video, or does R57 (the avatar in the intro and outro only)
   stand for the next ones?
6. **Avatar III in what viewers see:** R219 and R220 put the intro and outro on transparent Avatar III renders (the
   ones in round 6); David said tonight "Avatar IV is fine. Avatar III is not so fine.", with Avatar V for the intro
   and Avatar IV for the outro to confirm (SESSION_HANDOFF section 0, item 4). Not an R number yet.
7. **The blueprint's date:** R210 holds the blueprint and leaves open whether R95's 2026-10-20 still stands; R117,
   R130 and R147 still give the date.

**Still open (not a conflict):** the default browser zoom (100% now; SPEC said 125% for VS Code) waits for David's
phone check. R232 (newer) wins over R131's "away from Motion Array" for the subscribe animation.
