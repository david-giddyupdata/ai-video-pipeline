# Gotchas

Technical traps learned the hard way. Rules (what David decided) are in `RULES.md`; this file is how the tools
behave.

## Browser and Playwright

- **Playwright's sync API:** wait with `page.wait_for_timeout` or `expect_page`, never `time.sleep`. Sleeping stops it
  noticing new tabs.
- **The workshop Edge profile is `browser-profile\Profile 1`.** Pre-flight checks that the Copilot and Favorites
  buttons are hidden there. If port 9333 refuses, Edge was closed: restart it with the workshop's
  `automation\start_browser.ps1`.
- **Clip page boxes to the viewport, not `<html>`:** VS Code's `<html>` has zero height.
- **A `target=_blank` click shows the blank new tab at once** (the `tab_switch` event is logged seconds later). The
  edit cuts at the click and freezes the frame for the ring.
- **The sync flash:** page scrollbars draw over it, so its scale is measured against the client area.
- **Window titles** can contain characters the console can't print. Use `sys.stdout.reconfigure(errors="replace")`.

## Codespaces and VS Code

- **The codespace link on github.com/codespaces opens a new tab** (`target=_blank`). It can stall on "Setting up your
  codespace"; the runner reloads once.
- **"VS Code ready"** means the Explorer lists the repo (`.explorer-folders-view .monaco-list-row[aria-label='data']`),
  not just that the workbench frame exists.
- **VS Code keeps its view state in the codespace** (open editors, expanded folders), so a take inherits the last
  one's screen. `prepare.ide` resets it off camera. The codespace still opens a README.md preview on every new
  connection.
- **The editor tab and app tabs share the codespace name,** so match `<name>.github.dev` exactly (a prefix match picks
  the app tab). *Workshop lesson.*
- **Click into the codespace before keyboard shortcuts;** focus may sit in the terminal. *Workshop lesson.*
- **`gh codespace ssh` restarts a stopped codespace.** *Workshop lesson.*
- **Tick the `ANTHROPIC_API_KEY` Codespace secret for a take repo before creating its codespace.** The template's
  postCreate (`scripts/setup_shell.sh`) pre-approves the key for Claude Code once, at creation; with no key then, the
  panel answers "Not logged in · Please run /login". Fix: stop and start the codespace (secrets arrive at start), then
  re-run `bash scripts/setup_shell.sh` in it (prints "key approved", never the key). *take06, 2026-10-07.*
- **A one-off `gh codespace ssh -- cmd` doesn't see Codespace secrets** in its environment; check the names in
  `/workspaces/.codespaces/shared/.env-secrets` (`cut -d= -f1`, never the values, R4). *take06.*
- **A codespace's first open has no Claude Code tab** (only Chat and Additional Views); after a restart the tab sits
  next to Chat. Steps p2.07a (tab) and p2.07b/c (three dots) cover both. *take06.*
- **The Rainbow CSV toast covers the Claude Code message box** (bottom right) and swallows clicks: close it first
  (p1.06c). *take06.*

## Claude Code panel (S6 and later)

- **"Done" is not done** while a background reviewer is still running. *Workshop lesson.*
- **The panel pins the latest prompt at the top** and hides the bottom of the newest reply. *Workshop lesson.*
- **The panel opens in Auto mode.** *Workshop lesson.*
- **Logged out, the panel looks different:** no welcome cards, and the mode button says it asks before each edit.
  Logged in, a new session shows the doc's two cards ("Learn Claude Code", closed by `Hide onboarding`; "Auto mode is
  now Claude Code's default permission mode.", closed by `Close`) and Auto mode. *take06, 2026-10-07.*
- **Selectors (2026-10-07):** the panel is a webview two iframes deep; message box `[contenteditable][aria-label=
  "Message input"]` (Shift+Enter is a line break), send `button[aria-label="Send message"]`, `New session`. Busy: the
  box's `data-placeholder` reads "Queue another message" (an attribute, so match the frame's HTML, not its text). A
  short reply is busy for under 2 s. The tab: `.part.auxiliarybar .composite-bar a[aria-label="Claude Code"]`.
- **The panel reopens the last session.** Click `New session` off camera before a take, or the old conversation shows.
  `prepare.ide.new_claude_session` does it, then returns the sidebar to Chat. A codespace reconnect can also open a
  fresh "Untitled" session on its own. *2026-10-07.*
- **Conversation DOM (2026-10-07):** the scroll container is `[aria-label="Claude Code conversation"]` (class
  `messagesContainer_*`, "sticky mode": it follows new output). Each exchange is a `turn_*` div; your prompt is a
  sticky header in it (the pinned prompt). Claude's text messages have `aria-label="Claude"`, tool uses
  `"Claude, Read"`, `"Claude, Edit"`, ... Header buttons: `Bookmarks`, `Session history`, `New session`. A session
  loaded from history shows "Loading..." for a few seconds.
- **Loading a past session touches its log file** (its mtime moves), so "newest session file" is not proof that a
  session is the live one; the runner records the files it saw during each wait (`claude_state` events).

## Live steps (S7, 2026-10-07)

- **The template opens the dashboard by itself.** `.devcontainer/devcontainer.json` forwards 8050 with
  `onAutoForward: openBrowser`, so each time Claude starts the app Codespaces opens a dashboard tab in the take window
  (s7_take01: twice, mid-build). The runner closes such tabs during a wait and logs them (`tab_switch`, `closed`).
- **The GitHub tab can jump to the front with nothing logged** (s7_take02, right after Claude's first edit of
  CLAUDE.md; the IDE tab was opened from it). `document.visibilityState` in the IDE still said "visible", so the
  runner calls `bring_to_front()` unconditionally: every step start, after typing, every 3 s of a wait.
- **A tab behind another is throttled:** each Playwright mouse move took about 0.8 s (24 to 56 s pointer moves), the
  end flash never painted, and the Ports globe never appeared. Pointer moves are now time-based (fewer points, not a
  longer move) and the planner cuts the still middle of any move over `cuts.slow_move_s`.
- **Ports view (2026-10-07):** the 8050 row is "Dashboard (8050)"; its globe is `a.codicon-ports-open-browser-icon`
  (`aria-label="Open in Browser"`), in the Forwarded Address cell; `codicon-globe` is gone. The row's centre is the
  Running Process cell, which shows a tooltip on hover.
- **`lines.json` is per exercise, not per take.** Voicing a step list for another codespace replaces lines that name
  it (p1.03 "{codespace_display}"), so re-planning an older take afterwards picks up the wrong audio. Re-run
  `pipeline.narration.build` with that take's steps file first (cached, instant).
- **The Additional Views (three dots) menu is no longer a role=menu:** its "Claude Code" entry has no `menuitem`
  role. Match `.context-view >> text="Claude Code"` (s7_take03, first open of a fresh codespace).
- **A fresh codespace opens with the trust dialog,** which blocks every click behind it. `prepare` leaves such a
  codespace alone (nothing to reset); the take answers the dialog on camera (p1.04). The dialog can come several seconds after the file
  tree ("Creating a terminal process requires executing code"): prepare waits for it (`TRUST_WAIT_S`), or it would
  try to reset a fresh codespace and fail on the blocked command palette (full take, 2026-10-08).
- **Claude may ask its questions in a form** (AskUserQuestion: tabs, options with one "(Recommended)", "Submit
  answers", "Esc to cancel") instead of in its reply; the form hides the message box. Escape pressed on the form closes
  it ("Tool interrupted") and the message box returns (p3.11e). s7_take01/02 asked in text, take04/06 in a form.
- **After a reconnect the panel reopens its last conversation, open form included;** an off-camera New session on an
  empty conversation is not kept. p2.07f clicks New session on camera when a conversation shows.
- **Claude's permission prompts vary by run:** s7_take01 asked once (a `python3 - <<` edit), s7_take02 never.
- **A long prompt scrolls inside the message box** (the dashboard prompt, 640 characters: the box shows its last
  lines with a scrollbar), so marks measured on the typed text land on hidden lines (s7_take06, 2:26). Show the
  whole prompt on an overlay and highlight there (R77, `overlay` in the step).
- **The narrow panel at 2x shows too little of a reply to read along** (s7_take06, 3:17), and the question form
  takes the lower half while the reply scrolls above it. The reply's points go on an overlay (R76, R77).
- **Windows OCR on the panel:** a tool row comes back as two lines ("Read" and "CLAUDE. md"); "Both" reads as "80th"
  and "layout" as "lay)ut". `marks.ocr_box` also tries lines joined by row; match on the words that survive ("rules
  are already in", "should the dashboard").
- **What is on screen right after the send is worth a line:** the `dataviz skill` row and the first Bash calls show
  for the 10 s before the title card (s7_take06, 4:28); `timelapse.before_card_s` keeps them at 1x. app.py appears
  in the Explorer only at the end: a line-only step (`after`) names it over the result.
- **The question form's tabs truncate their titles** ("La… E… C… Aud…" at 2x), so only the open question is
  readable; the others are not on screen (R81). s7_take06, 4:00.
- **Edge's tab strip (100% scaling, 1920 wide):** the strip is grey 227; an inactive tab has no edge of its own next to
  the active tab, and the active tab is a white (255) run, y 3 to 39 (x 279 to 518 in s7_take06). OCR gives only the
  title text, so a box from OCR words cuts a tab in half. `marks.tab_boxes` takes the tabs' width and place from the
  active tab (slots are equal width while the strip isn't full). s7_take06, 5:29 (R84).
- **The from-start cursor ignored the hidden spans** (`Cursor.tsx`: the opacity branch skipped `shown()`), so every
  wait in s7_take06's first export showed the cursor (R47). Fixed 2026-10-07.

## Part 5 (2026-10-07, p5_take01 on take08)

- **A new take window doesn't come above other apps' windows** on the capture monitor (Windows keeps the foreground
  app on top), so pre-flight fails on whatever is maximized there: this session's VS Code, Snagit Editor (2026-10-07).
  Move them off the monitor first. Pre-flight only checks that the top window is Edge, so David's own Edge window
  there would pass and could cover the take: move it too. `pipeline.capture.screen` does this for every recording
  (R89). Setting a maximized window's placement only changes its restore rectangle and leaves it where it is: move it
  in the normal state, then maximize it again.
- **A reconnect opens a fresh "Untitled" Claude session,** so a take that starts at Part 5 shows an empty panel.
  Reopen the build conversation off camera: `Session history` (clock icon) lists sessions by their first prompt's
  title ("CLAUDE.md rules"); the panel then shows "Idle 6h 27m. The prompt cache has likely expired" under it.
- **Dash 4.4's RangeSlider draws number boxes at both ends** showing the raw values. A slider over month indices
  shows 0 and 68 (57 and 68 after "Last 12 months"): the defect take08 and earlier runs share. Selectors:
  `#range .dash-range-slider-min-input` / `-max-input`; dropdown options are `.dash-dropdown-option` labels.
- **A Plotly bar click chains callbacks** (clickData sets a store, the store redraws everything) with a moment in
  between when nothing is marked loading, so "Dash idle" ends too early. `explore.settle` waits until the page's
  titles, labels and graph data stop changing for 1.2 s; a click took 1.7 to 3.3 s to settle on take08.
- **A key sent over CDP never reaches the browser's own shortcuts:** F5 goes to the page and reloads nothing. The
  runner reloads with `page.reload()` for F5 and Control+R.
- **The tab strip is outside the page,** so Playwright's pointer can't reach a tab. `switch_tab` reads the strip from
  the screen (`marks.active_tab` on a grab of the capture monitor), logs the move and click in page CSS px (negative
  y), and brings the tab to the front; the edit draws the pointer.
- **Opening tabs off camera in the take's window:** `window.open` is popup-blocked without a user gesture, and CDP's
  `Target.createTarget` picks its own window. `prepare.open_tabs` clicks a link it injects into the tab before.
- **Ports after many reconnects:** take08's view listed 10 forwarded ports (VS Code's own, auto-forwarded). The 8050
  row's aria-label holds `localhost:8050`; its status icon is `codicon-ports-forwarded-with-process-icon` while the
  app runs.
- **Claude won't stop a server it didn't start.** p5_take01's test started the dashboard over ssh; Claude fixed app.py,
  left that server running ("I didn't start it"), ran its copy on 8051, and the reload showed the old page twice.
  The feedback prompt now ends "Then restart the dashboard so I can check it." In a full take Claude started the
  server itself in Part 4.
- **The real pointer shows in the recording although OBS's `capture_cursor` is off:** a hand, then a "no" sign, at
  the capture monitor's right edge through p5_take01 and most of take02 (it changes shape with what is under it).
  Pre-flight now fails when the pointer is on that monitor; during a take nothing checks it.
- **A mark on the text a step types** is measured on the finished text, but the box grows as it fills: drawn during
  the (sped-up) typing it lands above the words (p5_take02, p5.15c). The plan holds such marks until the typing ends.
- **The speech service can drop several connections in a row** (ClientConnectorError, WinError 64): the build's
  three tries ran out once. Run the build again; voiced lines are cached.
- **Heredoc Python in the Bash tool loses backslashes** (`\d`, `\s` in a regex or JS): write such scripts to a file.

## The full take (2026-10-08, full_take01 and 02)

- **Claude may want to see its own page.** In full_take01 the dataviz check installed Playwright and Chromium in a
  temporary environment, then asked for `sudo ... playwright install-deps chromium`. `sudo` is RISKY, so the take
  stopped in p4.12. R91 now allows exactly that command; full_take02's Claude didn't try (it said the codespace has
  no browser, which p5.15a's line rests on).
- **The live harvest after a join:** the joined run clock skips the pause, so one run-clock-to-wall offset put Parts
  5 and 6 468 s early, and their steps showed no tools or replies. `pipeline.post.live` maps each event by its own
  `t_wall` now.
- **Controls below the first screen:** a click target off screen is scrolled into view by Playwright
  (`scroll_into_view_if_needed`), an instant jump, and the next line's marks on the top of the page are then off
  screen (R81). full_take02's dashboard put the map and ranking below the fold, so Part 5 used the Airport focus
  dropdown, whose label names the map and bar clicks.
- **Dash 4.4's slider boxes, again:** round 1 put month names on the handles and left the number boxes (45 and 68);
  round 2 set `allow_direct_input=False`. Same two rounds as p5_take02.
- **OCR marks after a take:** a new mark on a finished take can only be OCR (`match`); `ocr_xband` keeps it in the
  Explorer when the same word is in Claude's reply. Windows OCR doesn't read Dash's number boxes at all, and reads a
  handle label "Oct 2023" as just "2023": a `box` target (frame px, from another step's logged box or an OCR line)
  covers what OCR can't, and wins over the runner's own box.
- **Resume parked the real mouse on a chart:** the runner starts with the mouse at the viewport's centre, which on
  this dashboard is a sparkline, so a Plotly tooltip ("Nov 2024: 0.5") stayed up for 45 s of Part 5 (full_take02).
  The resume now parks it at the page's top edge.
- **A cut wait dropped its approval:** waits short enough for the cut rules (not a time-lapse) ignored their
  permission prompts, and p5.16d's approval click was cut out (R39). The plan keeps every prompt at 1x now.
- **A mark measured before a cut lands on the old picture:** p6.18's word fell just before its Page Peel's cut, so
  OCR found the previous reply. Name what's new after the cut, or put the mark on a word that falls after it.
- **A line that names Claude's reply during a time-lapse** speaks before the reply exists (p5.15e/l). Split it: the
  wait's line covers the prompts and the work; a line-only step (`after`) names the reply on the result.

## The line check (R85)

- **`npx remotion still` bundles again for every frame** (about 12 s each). `remotion/scripts/stills.mjs` bundles
  once, with a slim public dir of hard links to what EditPass uses (the recording, holds, audio, fonts), and renders
  every still from it: 75 stills in about a minute.
- **The OCR test passes a word that is on screen anywhere**, not where the line means: "running" matched the
  terminal's welcome text while Claude's "the dashboard is running" had scrolled out of the panel (p4.12b). The
  report is a pointer; reading the still sheets is the check.
- **A transition on the camera nest turns the whole picture**, the cursor and a half-drawn mark with it, so R83 skips
  cuts that fall on a mark or a gesture.
- **Overlay item vs sentence (R80) is a word match**: "Findings" against "what it found" is flagged though it is the
  same subject. Judge it on the table.

## OBS

- **OBS profile switches** can reply after the client times out. Reconnect and poll; never reuse that socket.

## Voice and edit

- **edge-tts reads a short word before a full stop as an abbreviation** and runs the sentence on: "...dot GitHub dot
  dev. Code spaces" paused 0.015 s, "mat plot lib. Use" 0.18 s, where every other sentence end gets 0.485 s (Andrew,
  -15%). Both came from respelled names. Measured fixes: an ellipsis 0.485 s (used), a colon 0.50 s, a hyphen 0.35 s,
  "D E V." 0.65 s. "U.S." is a real abbreviation (0.014 s, correct). The build checks every sentence-end pause.
- **edge-tts 7 defaults to sentence boundaries.** Pass `boundary="WordBoundary"` to get word timings (they match the
  audio's pauses to about 50 ms for Andrew).
- **edge-tts 7.2.8 is refused (403) by Microsoft's service** since Edge moved on (it sends a Sec-MS-GEC version of
  Edge 143; this PC runs 155): 7.3.1 works (2026-10-18). Its connections also reset at random on this PC's IPv6 route,
  as Hugging Face's do: resolve `speech.platform.bing.com` over IPv4 (as `pipeline/hf_ipv4.py` does for the Hub) and
  retry a line on `NoAudioReceived`.
- **ElevenLabs' character times give part of each pause to the character before it.** The gap between two words
  measures about 0.2 s shorter than the silence heard (csc13.intro: 0.13 s measured, 0.22 s of silence; with an
  ellipsis 0.21 s measured, 0.44 s). `voice_clone.json` sets `sentence_pause_min_s` 0.15 for it. The clone also
  reads "Data." as a short stop, so the ellipsis fix applies to it too.
- **ElevenLabs' usage log counts about 0.22 units per character on this pay-as-you-go account,** and `previous_text`
  and `next_text` aren't counted (2026-10-12: 1,079 characters logged as 236, an 88-character line with about 200
  characters of context as 19). Read it with `/v1/usage/character-stats` (hourly); `/v1/user/subscription`'s
  `character_count` lags behind it.
- **ElevenLabs' stitching can start the next line inside a clip.** With `next_text` set, two clone clips (p2.10a2,
  p2.10c) ended in silence and then 50 ms of the next line's first sound, cut off at the file's end: a pop in Premiere
  (2026-10-12). `pipeline.narration.clean` silences such a burst and fades every clip's edges; the planner plays the
  cleaned WAV, never the cached MP3.
- **HeyGen idles through silence in supplied audio.** 1.5 s of silence on each side of a line (2026-10-12): no frozen
  frame, head motion about 70% of the speaking level, mouth closed. The render keeps the audio's exact length.
- **HeyGen v3 Avatar III renders a 7.4 s clip in about 46 s,** full frame at 1920x1080 and 30 fps in the look's own
  background, with the supplied audio's length kept exactly (2026-10-12).
- **Freezes in the edit are stills cut by ffmpeg** (`runs/<id>/holds/`). Remotion's `<Freeze>` around an
  `OffthreadVideo` showed the wrong frame.
- **Remotion renders CSS `backdrop-filter`** (blur), inside the camera transform too: privacy masks use it.
- **The runner logs a step's result late.** `expect_met` fires when its poll sees the change, 0.04 to 1.08 s after
  the picture changed (take 05). The planner uses the last picture change before it (`activity.last_active`).
- **A step's marks are addressed by their place in its `marks` list,** in the run log (`detail.mark`, a live mark's
  gesture; `text_box` boxes) and in `lines.json` (each mark's `at_s`). Add a mark after a take only at the end of the
  list, and rebuild `lines.json` (`pipeline.narration.build`) after any change to the list. Putting two new marks
  first (Section A round 3, p2.06) re-anchored the live mark on Create to "Interactive sheet": its click landed 7 s
  before its cue word, with an 8.5 s hold after it, and p2.07's logged box went unused.
- **Windows OCR on the account name:** it reads the header's name on every page but not while a modal shades the
  page (up to 80 s at a stretch in Section A), and the address bar's and the header's names sit 37 px apart in y.
  The privacy report merges sightings only at the same place in x and y, and a standing pattern's `bridge_gap_s`
  (120 s) carries the blur across what OCR misses; the regex is case-insensitive and takes OCR's O for 0. A
  pattern bridged that way blurs an empty spot through any real absence shorter than the gap (round 4).
- **The pointer's move to a click target lights its hover highlight as it enters the element,** before it arrives,
  so the recording changes mid-move (list options, field names, icons: 10 of Section A's 64 click marks). A test
  that the footage under a mark's hold is still must stop where the move starts (`click_move`), not at the arrival
  or the click (R128, round 4).
- **What a click opens has no box in the run log** (the runner logs click targets only). `pipeline.edit.appear`
  measures it from the frames, for a step's `whole` (R123): a page modal shades the page to about half (Quick Sight,
  factor 0.4 to 0.55), so the modal is the near-white box left; a menu or the Windows Open dialog changes the frame
  with no shade. A modal replacing another one (p2.05) and the Open dialog (66% of the frame) need the size limits in
  that module; a navigation brightens the page and gives no box (p2.40's tip has a fixed box).

## Premiere round trip (S5)

- **Read David's edits from the `.prproj`, not from Premiere's Final Cut XML export.** The export writes a nested
  sequence's Center as (-0.5, -0.5) at every keyframe, while the project holds the real Position (normalised 0..1,
  e.g. 0.675, 0.575 at the 1.35x hold). The XML import itself was correct, and keyframes stay linear.
  `pipeline/edit/prproj.py` (moved from `research/style_study/premiere/parse_prproj.py`, which is now a shim) reads
  tracks, nests, Motion, Opacity and captions; `pipeline.edit.readback` builds the report on it.
- **Caption text and style are base64 FlatBuffers** (`<FormattedTextData>`, after an 8-byte length and the magic
  11223344). Fields of the root's first table seen so far: 0 text runs (font size 48 at `.0[0].1.1`), 4 centre
  alignment (2; absent = left), 17 background RGB, 18 background on, 19 background opacity (%), 33 grid position
  (6 = bottom-left on a 3x3 grid numbered from top-left; absent = default bottom-centre), 34 corner radius.
  Found by diffing Premiere's auto-saves before and after an edit (`Adobe Premiere Pro Auto-Save/`), which is the
  quickest way to decode any new field.
- **An SRT carries no position,** so Premiere puts every imported caption at bottom-centre, and the planner's
  per-cue placement (R53) is lost on import.
- **An SRT dropped on the timeline starts at its first cue, not at 0:00.** Premiere put take 05's first caption at
  the playhead (0:00) although its words start at 1.03 s, so every caption ran about 1.05 s early until David
  re-placed the later ones by hand. The read-back reports this as an import offset. Until captions move to a
  positioned format, drop the SRT at the first cue's time. The export now adds a one-frame anchor cue at 0:00
  instead (drop at 0:00, delete the anchor).
- **Premiere's TTML import (tested 2026-10-06, take 05 round 2):** timing and grid position come through. All 18
  cues landed within a frame of their words with the anchor-cue drop at 0:00, and the bottom-left cue stayed
  bottom-left (displayAlign gives the row, textAlign the column). The look does not: font size, box colour and
  corners come in at Premiere's defaults, and David restyled them by hand (40 px, #5E5E5E, 10.95 px corners).
  Ideas if this is ever automated: TTML style attributes Premiere might honour (none so far), a saved Premiere
  caption track style he applies in one click, or writing the caption blocks into the `.prproj` directly (the
  FlatBuffer fields are decoded above).
- **Premiere's TTML import is not reliable for position.** Take 05 (round 2) kept every cue's grid spot; s7_take06's
  round 2, from a byte-identical header, came in at the top left, and David moved all cues to bottom-centre by hand,
  so the planner's 12 off-centre placements were lost (R53). His look: box #5E5E5E at 100%, padding 15, corners 10,
  40 px.
- **Overlapping caption cues** (one ending after the next starts) come in merged plus a duplicate. The planner must
  never write them (R85 checks).
- **Transitions are in each track's `TransitionItems`,** not among the clips (Page Peel: `AE.AE_Impact_Page_Peel`,
  1.0 s, alignment 0 = starts at the cut). The read-back lists them.
- **Premiere's FCP XML import doesn't map our "Page Peel" transition item** (effect name and id "Page Peel"): it
  arrives as "Cross Dissolve (Legacy)", shown on the timeline but not rendered in the program monitor (David,
  s7_take06 round 3). Not fixed (his call, 2026-10-07): add the Page Peel by hand at the export report's times. A
  fix would need the effect id Premiere's own FCP XML export writes for a Page Peel.
- **A transition on the camera sequence blends a frame into itself** (Fable's review, 2026-10-07). The cut is inside
  the nest, and the camera track's pieces of the nest are continuous in nest time, so both sides of a transition there
  show the same frames: the "not rendered" dissolve above may be exactly that. R83's transitions now sit on the nest's
  Recording track, between the two pieces of `raw.mp4`, where the skipped footage is the outgoing piece's handle. A
  Page Peel added by hand belongs there too. Whether Premiere then renders the imported dissolve is unchecked.
- **A rendered overlay can only be re-timed by cutting it:** David cut `reply_points` and looped one 0.53 s piece five
  times (on the Title cards track) so its last item appears 2 s earlier. Read the pieces' in-points, not the track
  names; the read-back reports overlay items' times on his cut.
- **Caption alignment is field 4:** absent = left, 2 = centre. David's bottom-left cue is left-aligned.
- **A dissolve that ends at the cut imports on the outgoing clip only.** In `<run>_full.xml` the recap's dissolve
  (alignment `end`, run on the recap's head) came in with `HasIncomingClip` false: the camera faded for 0.8 s, then
  a hard cut to the avatar (csc13 test, 2026-10-12). One that starts at the cut and runs on the outgoing clip's tail
  (the opening's) imports with both sides, so the recap join now does the same: the camera gives up 0.8 s after its
  last line as the tail.
- **An open Premiere project locks the media it uses.** ffmpeg can't overwrite them (exit 4294967283, access
  denied): `graphics/opening.mp4` while David had the test project open. Write a new file instead of replacing one
  (the logo outro's name carries its settings' hash), and don't re-encode a graphic that already exists. **Closing the
  project isn't always enough:** on 2026-10-17 (final_r5) a stage clip a just-closed project had played through
  single-frame exports stayed locked with no project open, until Premiere quit (`bridge quit`, R104, R230); a re-render
  into the same folder then failed at its join. Quit Premiere before re-rendering a built round's clips in place.
- **An export round must not reuse a folder David may have imported.** `next_round` used to reuse any round folder
  without a saved `.prproj`, so round 3 of the CSC13 test overwrote round 2's media, which David had imported into
  round 1's project. Every export now gets a fresh folder; only one left without an XML is reused.
- **An audio track's mute is the fader's Mute param,** not the track's `IsMuted`: the AmazonQuick "Outro" sequence's
  Bach bed (A4) read as live. `prproj.py` now folds it into `muted` (and `fader_muted`).

- **A nested sequence's second audio track survives the FCP XML import.** A full-sequence clip that references the
  camera sequence with `<sourcetrack><trackindex>2</trackindex>` comes in as an AudioClip with `SecondaryIndex` 1
  (the first track's has none), so R137's Clicks track plays once, not on top of the narration (round 5).
- **Write each track's clipitems in time order.** The reel's round 3 XML put one still (the ending's fly-in, at
  2:33) first on its track, ahead of the clip at 0:00. Premiere imported all 12 clips, yet its first export of the
  project drew none of that track, with no Media pending card, on three exports in a row (a later export that muted
  other tracks did draw it). In time order, both exports were whole (2026-10-18;
  `tools/reel_build.py` `fly_in`). `tools/reel_build.footage_missing` now tests every footage clip in an export.

## Scripting Premiere (R102, 2026-10-13, Premiere 26.3)

- **No script can write a graphic's text.** ExtendScript reads a native graphic's Source Text as one garbage
  character (the binary value), and `getMGTComponent()` is null on it. UXP can't read or set Source Text at all (Adobe
  forum, 2026). A Premiere-made `.mogrt` becomes a native graphic when added, so its text isn't a template parameter
  either; only After Effects templates keep one (set as JSON, `textEditValue`). So `pipeline.edit.ppro.titles` bakes
  each cue's text into a `.mogrt` of its own.
- **A graphic's Source Text is the captions' FlatBuffer** (above), param Version 3: one run, field 17/18/19/20/34 the
  background colour, on, opacity, padding (15) and roundness (10). Premiere 2019's own templates hold an older UTF-16
  JSON value (Version 2) with no background; Premiere 26.3 renders a Version 3 value spliced into such a template.
- **The box hugs the ink, not the line box:** a line with no descenders gets a shorter box (61 px against 69 px at
  40 px). Line step 48 px. PIL's ink bounds of the same font, plus 15 px, land within 1 to 3 px of Premiere's box.
- **Premiere stores a binary value once.** A later element with the same `BinaryHash` is empty (`<FormattedTextData
  ... BinaryHash="..."/>`): a caption line repeated word for word read as no text, and the read-back would have
  called it deleted (10 cues in full_take02, 1 in s7_take06 round 2). `prproj.Project.value()` falls back to the
  first copy. Found by cross-checking py-premiere (2026-10-13), which agreed with our decoder on every other field.
- **More FlatBuffer fields** (py-premiere's names, not yet checked in Premiere): root table 1 font family, 6 line
  spacing, 10 to 16 the shadow (colour, on, opacity, angle, distance, size, blur), 20 background padding; a run's
  style 2 text colour, 4/5/6 stroke colour, on, width, 8 letter spacing. By those, David's restyled captions in
  full_take02 kept Premiere's default drop shadow; his TitleTest titles (and ours) have none.
- **`BinaryHash` on a value** is 24 hex digits (not MD5, SHA or CRC) plus the value's length + 12. Premiere accepts a
  random hash in that shape; one per cue so no two values share it.
- **`sequence.importMGT()` returns null** in 26.3 though the clip is placed: find it by its start. It overwrites (no
  ripple) and gives the template's length (4.9 s here), so add cues in time order and trim each (`trackItem.end`)
  before the next, or a later one gets cut.
- **`importMGT` now and then places nothing, silently:** the title starting on the very frame where the previous
  one was just trimmed (cue 1 of the CSC13 test, 2 builds in 8). `aidvCaptionTitles` looks again for 2 s, then
  inserts again (up to twice), and finally checks the track's clip count; a retried cue is reported.
- **QE can remove a transition:** `qeTrack.getTransitionAt(i)` counts every item of the track (clips, gaps and
  transitions; some indices throw), so try each index and keep those whose `type` is "Transition"; its `remove()`
  with no arguments takes the transition off and leaves both clips as they were. QE won't add a second transition on
  a cut that has one, and says nothing: compare the track's `transitions.numItems` before and after.
- **A project path with forward slashes** on Premiere's command line opens a modal "This file path does not exist"
  dialog, and every script waits behind it. Pass a Windows path.
- **CEP still runs** (CEP 12, `CSXS.12`); an unsigned panel needs `PlayerDebugMode` = "1" under
  `HKCU\Software\Adobe\CSXS.12` (set 2026-10-13). A hidden `Custom` extension with `StartOn` `applicationActivate`
  starts with Premiere. `ScriptPath` didn't load `aidv.jsx` the first time (a syntax error: the Write tool had turned
  the escape `\u2028` (U+2028) in the regex into a real line separator, which ends an ES3 line);
  the bridge now `$.evalFile`s it itself.
- **Premiere 26 lists "Page Peel (Obsolete)" and a new "Page Peel"** (QE `getVideoTransitionList`, 157
  transitions). The XML import maps ours to the old one, hence the dissolves (R83). R105 adds the new one after
  the import: QE `trackItem.addTransition(qe.project.getVideoTransitionByName("Page Peel"), false, "00:00:01:00",
  "00:00:00:00", 0, false, true)` on the clip before the cut starts it at the cut, 1 s on that clip's handle;
  the DOM's `track.transitions` reads it back (`AE.AE_Impact_Page_Peel`). QE counts empty gaps as items
  (`type` "Empty"), so find the clip by its end time.
- **QE's `exportFramePNG(timecode, path)`** renders Premiere's own frame (alpha where nothing is), the way to check
  titles without a person: `pipeline.edit.ppro.project --frames`.

## Edge profiles, the Windows Open dialog (2026-10-14, R112, R113)

- **Edge signs a new `--user-data-dir` profile in to the Windows Microsoft account by itself,** with sync on (a "We
  are now syncing" tab). Sign it out in `edge://settings/profiles` with "Clear favorites, history, passwords..."
  ticked: Edge deletes `Default` and makes `Profile 1`, not signed in (the workshop profile is `Profile 1` too). Launch
  with `--profile-directory`; `pipeline.capture.browser` refuses to start a profile signed in to Microsoft, and one
  whose `lockfile` Edge holds without the debugging port.
- **Edge rewrites `Preferences` on exit,** so recording settings are written only while it is closed (the launcher
  does it at every start). `selectfile.last_directory` sets the folder the file chooser opens in.
- **Playwright's page list drops `edge://` pages after a navigation.** Open a fresh page in each script.
- **The Open dialog Edge opens is owned by Edge:** UI Automation lists it under Edge's window, not the desktop, so a
  search of the desktop's children misses it. Find the `#32770` window titled "Open" (and owned by `msedge.exe`)
  through Win32, then `ElementFromHandle` (`pipeline.driver.osdialog`, comtypes 1.4.17).
- **The Open dialog has three buttons named "Open"** (the file-type arrow, the split arrow, the button): the widest
  is the button. In Details view a file's ListItem spans every column; its name is a child Edit or Text element.
- **`SelectionItem.Select()` on a file fills the File name box as a click does;** `Invoke()` on Open hands the file to
  the page's `<input type=file>`. No real pointer moves (R15). An element without a pattern gives a NULL pointer,
  not a `COMError`.
- **Edge's autofill previews a saved name over typing.** A field that names itself (Quick Sight's Dashboard name)
  pops up Edge's "Saved info" list with what a rehearsal typed, and while the take types, every other frame or two
  shows Edge's tinted preview of the whole saved name (with a "Tab" chip) instead of the letters so far (Section A
  00:14:17, David's note 13). Five other Quick Sight fields didn't. `pipeline.capture.browser` now turns autofill off
  at each start (unchecked until the next one); in a finished take a step's `drop` cuts the typing.
- **The same "Saved info" list sits over whatever is below a field for as long as it has focus** (the Edit date
  format box, Section A round 6 00:03:38 to 00:03:57: the example line and the Validate button the line talks about).
  A step's `drop` can't help there (it would cut the typing and the line's anchor); a correction (R173,
  `runs/<id>/corrections.json`) covers it with the same place from a frame before the list appeared.
- **Playwright intercepts a page's file chooser only while a `filechooser` listener or `expect_file_chooser` is
  armed;** otherwise the real dialog opens (R112 wants it).

## Quick Sight (2026-10-14, Section A at 1912x996, Standard edition, the admin)

- **Quick Sight leaves hidden copies of closed dialogs in the page:** `[role=dialog]:has-text(...)`'s first match
  can be hidden, so an expect needs `>> visible=true` (the runner's own `find()` already picks visible matches).
- **The runner measures page marks with `querySelectorAll`,** so a mark's `locator` must be plain CSS: `has-text`,
  `text=` and `>> xpath` threw on full_take01 and 11 marks went unmeasured. The edit's fallback is an OCR `match` or a
  fixed frame `box`.
- **`:text-is()` misses some Quick Sight items whose text carries more than the label** (the data type options, the
  tip card's Done): `:has-text()` or `role=button[name="Done" s]`.
- **Playwright's scroll into view centres the element:** the Change data type panel jumped 460 px on camera. A
  target's `scroll: smooth` eases the panel just far enough (43 px).
- **The data type list opens upward, over its dropdown,** so a second click on the dropdown chooses Date.
- **An upload leaves a FILE data source behind even when the prep is cancelled.** The Create dataset box doesn't list
  it.
- **After Save & publish the Cancel button is a new element (`data_prep_close`)** and the view goes back to TRANSFORM.
- **Geospatial type:** pencil, then the dropdown, then the option, for every field. The next field's panel shows the
  previous field's value until changed; the field's icon in the Schema list is the truth.
- **The analysis sheet is 1600 px wide;** with the Data, Visuals and Properties panes open it scrolls sideways until
  Fit to width (`layout_view_dropdown`, then `analysis_navbar_fit_to_width`). With it, the bar chart drags above the
  line chart by its 11 px `dragHandle_div` strip on the first try, and both fit without resizing.
- **The charts are canvas:** a bar is a point in the visual's box.
- **"No data to display" lasted 40 s on a just-published dataset,** and not at all once SPICE had loaded.
- **The Owner column reads "Me" for the admin** (no account ID); the account name is in the header and every URL.
- **Standard edition: `DeleteDashboard` is Enterprise-only** (`UnsupportedUserEditionException`); `DeleteAnalysis`
  (recovery window) and `DeleteDataSet` work. `tools/qs_cleanup.py` deletes a dashboard from the Dashboards page.
- **Publish shows a "Fetching datasets status" box first:** right after the click it shades the page for about
  0.37 s, closes (two bright frames), then the Publish dashboard box fades in with its own shade, so the screen
  flashes dark, light, dark (Section A 00:14:06, David's note 12). The frames either side of the box match, so a
  step's `drop` cuts it without a visible join.
- **The line check found the wrong exercise:** it looked the steps file up by name, and two exercises have a
  `steps_full.json`. It now reads the run's own exercise from the log header.
- **The Edit date format dialog jumped 53 px for six frames just before Validate was clicked** (full_take01 frames
  6956 to 6961; Playwright bringing the button into view, then the page settling). A drop can't cut footage before a
  step's own click (the planner refuses it), so a correction shows the steady frame over them (R173).
- **A row added at the bottom of a panel can sit at the recording's own bottom edge** (the new data type dropdown, 28
  px from it): the camera never pans past the recording, so no zoom lifts it clear of R123's 100 px margin; 2x gets it
  to about 60 px. Only a take that scrolls the panel further would.

## Measuring frames

- **Seeking by time (`-ss`) can land a frame off;** count frames with `select=between(n\,a\,b)` and
  `-fps_mode passthrough` when a frame number matters (a correction's first and last frames), and check a joined
  boundary on both sides.

## Overlays and the ideas run (2026-10-15)

- **Remotion imports a `.ttf` as a file URL** (the bundler's asset rule), so overlay fonts can live beside the code
  and load with `FontFace` plus `delayRender`, whatever public dir a render uses. This project's DOM typings lack
  `FontFaceSet.add`: cast it (`remotion/src/overlays/fonts.ts`).
- **A long render can hang on the overlay fonts' load.** Round 6's export failed three times in its 28,000-frame
  cursor layer (frames 2081, 6046, 5592): a fresh browser tab's `delayRender("overlay font Inter")` never cleared,
  and neither did a 15 s `setTimeout` meant to give up on it, so the tab itself had stopped. `fonts.ts` now skips
  the load for the export's textless layers (OverlayClip `only` cursor, mark, card), and gives up after 15 s
  elsewhere; `pipeline.edit.premiere` renders with `--timeout=90000`.
- **OpenRouter has no video models (2026-10-15), and an image model's price per image doesn't follow its token
  price:** Nano Banana 2.1 ($7.50 per million output tokens) cost $0.036 an image, Gemini 3.1 Flash Image ($3) $0.067.
  An image edited from another (`--from`) keeps its style, so two states of one object match.
- **A judge model favours its own vendor's ideas,** blind or not: the GPT judge ranked both GPT models first, the
  Gemini judge put Gemini above both GPT models. Use judges that didn't compete, or read each judge's column apart.
- **A heredoc in the Bash tool eats backslashes** (again: a Python patch with a `\n` in a string became a real line
  break, and this very line did too): write such scripts with the Write tool.

## The measured checks and outside reviewers (round 8, 2026-10-15)

- **ElevenLabs can log a word ending half a second into the pause,** and a display word spoken as many ("MM/dd/yyyy"
  as "M M slash d d slash ...") is one timed word from its first letter to its last. p1.14's "yyyy." was logged as
  ending at 8.18 s; the voice stopped at 7.43. Never place anything by a logged word end: `breaths.beat_point` finds
  the last loud frame (a quiet fricative counts: an "s" sits over 3.5 kHz) and the first silence after it.
- **Breath detection depends on the loudness pass:** its compressor lifts an inhale's faint start, so the same breath
  begins about 70 ms earlier in the processed clip than in the cached MP3. A beat placed "just before the breath" from
  one splits it in the other; place it in the silence after the word (above), which both agree on. A word's breathy
  release decays straight out of the voicing and isn't an inhale: an inhale starts out of near-silence.
- **Edge's autofill preview alternates two frames each** (preview, preview, typed, typed: A A B B), so a test for
  A-B-A flips finds nothing. `checks.alternation` looks for a frame matching one 2 to 8 frames earlier while differing
  from the one just before.
- **Windows OCR reads an orange tick as "V" or "v"**: the still checks skip one-character words, or a tick is measured
  as orange text.
- **Gemini 4 Argon on OpenRouter bills about 1,120 tokens a frame** (Gemini's default image resolution, whatever the
  JPEG's size): 60 frames at 768 px cost $0.135. Gemini 3.1 Pro on a whole video through Google's API samples about
  91 tokens a second (low resolution, about 1 frame a second): a two-frame flicker or a 0.6 s graphic falls between
  its samples (round 7's test, `research/video_review/round7/RESULTS.md`).
- **Remotion's `bundle()` leaves its bundle in the temp folder on C:** (about 140 MB with the public dir), and nothing
  removed them: 759 had piled up (31 GB) when C: hit 0 bytes free mid-round (ENOSPC from `stills.mjs`).
  `scripts/stills.mjs` and `review/render.mjs` now delete their bundle when done. If a render fails with ENOSPC,
  look in `%TEMP%` for `remotion-webpack-bundle-*` and `react-motion-render*` first.
- **Remotion also leaves a copy of every input in `%TEMP%` for each render call** (`remotion-v4.0.487-assets*`), and
  never removes it: on 2026-10-16, 7,040 of them held 215 GB of C:, and a still render of a 1 GB ProRes avatar left
  1 GB per still. The render scripts (`scripts/stage.mjs`, `scripts/stills.mjs`, `review/render.mjs`) each work
  in a temp folder of their own (`aidv-render-*`, TEMP/TMP/TMPDIR pointed at it) and remove it when they end, so
  two renders at once never touch each other's files; feed Remotion small inputs (`pipeline.edit.alpha.to_webm`:
  VP9 with alpha, about 1/30 the size); and `pipeline.edit.stage` puts that temp folder under
  `G:\aidv_scratch\remotion_tmp` (David's wipeable SD card) when G: is there.
- **A paid batch must keep each call's answer as it lands:** `ex.map` re-raises the first failed call and every paid
  answer collected so far is lost; a reply cut off at `max_tokens` parses as no findings unless the raw text is kept.


## Loudness as Premiere plays it (2026-10-16, Section A's final)

- **Premiere doesn't play our audio at the level the files measure.** Spans of Section A's final sequence exported by
  Premiere itself (`exportAsMediaDirect`, its stereo "Waveform Audio 48kHz 16-bit" preset): the approved sequence's
  narration, mono files measured -14.3 LUFS by `pipeline.edit.loudness`, plays at -11.1 to -11.5 LUFS (in both
  channels at full level: +3 dB in LUFS over the mono file), while a clip the final's XML takes from a stereo file's
  first channel plays at that channel's mono LUFS (-15.1: the pan law's -3 dB on each side). So R177's -14 LUFS, as
  measured on the files, is about -11.3 in Premiere's mix, and two clips from the two routes differ by about 4 dB.
  Measure the mix Premiere renders, never the files: `final_r1/mix_check/` has the spans and the script.
- **A stereo file plays in stereo only as two clips panned to their sides** (2026-10-16, measured in Premiere's own
  export of four XML forms of the logo outro's Rossini, which is wide stereo). One clip of `sourcetrack trackindex` 1
  plays the left channel alone, centred (every XML before `final_r3` did this to the music); `premiereChannelType`
  "stereo" plays the left channel hard left and drops the right; `outputchannelindex` 1 and 2 on two tracks folds
  both to mono. Two clips, trackindex 1 and 2, on two tracks with an Audio Pan of -1 and 1 match the file exactly
  (L, R and L-R loudness). Hard-panned clips play at the file's own stereo LUFS, with no pan-law drop.
  `premiere.audio_pan`; the test and its numbers: `research/premiere_stereo/`.
- **A mono WAV clip in our own XML plays at its file's LUFS too** (the avatar's voice in `stage_review_r2`: -14.4
  against the nested narration's -11.4), 3 dB under narration the nested sequence plays. Give it
  `final.PREMIERE_MONO_DB` of clip level, as the avatar's clips in the final get; the mix check finds it either way.

## The avatar's stage (2026-10-16, R205 to R209)

- **HeyGen's transparent WebM has premultiplied edge colours** (a hair pixel at alpha 89 reads (57, 55, 47)), while
  ffmpeg, Premiere and Chrome read the alpha as straight, so the edge darkens twice into a dark outline over a light
  background. ffmpeg's `unpremultiply` filter left the frames unchanged. `pipeline.edit.alpha.fix_edges` divides the
  alpha out, fills alpha under 128 from the subject's colour inside (divided-out 8-bit values turn to coloured noise),
  and despills a 3 px band. Only `libvpx-vp9` decodes the alpha; ffmpeg's own VP9 decoder drops it.
- **A layer above a nested sequence covers the nest's own captions.** The avatar on V2 hid "so" in the approved
  sequence's first caption. Copy the covered caption titles (the same .mogrt, the same frames) onto a Caption titles
  track above the layer (`pipeline.edit.stage.stage_titles`).
- **The measured contrast check reads only what OCR reads:** a lone digit in a chip and handwriting (url.mov) passed
  unmeasured and failed 7:1 (4.96 and 4.4:1); the visual review caught both. Measure shapes of text OCR can't read by
  their pixels.
- **Long stage renders stop on a font load** (round 5, 2026-10-16): both 1,470-frame clips of the box design failed
  twice with `delayRender("overlay font Inter")` never cleared, while the 205-frame tails and every still rendered.
  `pipeline.edit.stage.render` now renders a clip in parts of 300 frames, each a fresh `renderMedia`, joins them with
  ffmpeg's concat (`-c copy`) and checks the frame count; a failed part is tried once more.
- **A full-frame box covers whatever is drawn under it.** In the box design the avatar's frame carries its own opaque
  background (B1), so the write-on drawn before the avatar vanished once the avatar grew back to full frame: the
  subscribe card and the write-on are drawn after the avatar now (`AvatarStage`).
- **ProRes 4444 of a photographic background is big:** about 2.2 MB a frame (a 56 s outro about 3.7 GB), against the
  checkerboard's few hundred KB. Keep D: in mind for stage renders.
- **Remotion merges the composition's `defaultProps` into the props a render passes.** A prop the stage plan leaves
  out takes `STAGE_SAMPLE`'s value: `checkerUntil: 2` drew a checkerboard for the first 2 s of round 6's outro (round
  5 hid it under B1). Pass every such prop explicitly (`checkerUntil: 0`); `stage.oval_alone` checks the stills.
- **`plan.captions()` wraps every cue to two lines,** whatever `max_lines` says (it calls `_wrap` with its default):
  a 3-line spot came out 40 characters wide and onto the avatar. `stage.phrase_cues` wraps to the spot's own lines.
- **Premiere 26.3 ExtendScript gives Motion Position as fractions of the frame** (`getValue()` [0.5, 0.5]) and Scale
  in percent, as the `.prproj` stores them; set them so after the XML import (`aidvClipMotion`). A 4K clip imported by
  XML comes in at 100% of its own size (no scale to frame).
- **Motion Array's QuickTime Animation `.mov` (argb) is premultiplied;** `url.mov` (ProRes 4444) is straight. FCP7 XML
  `alphatype` "black" for the first imports cleanly in Premiere (no dark fringe against QuickArch03's frame).
- **A window that grows faster than what it frames shows that thing's edge.** Round 6's outro first grew a soft ellipse
  from the oval to the frame's size: it outgrew the scaled copy of the room inside it, whose flat top edge showed. The
  window and the room now scale together (a rounded rectangle from the oval to the frame), soft-edged by an SVG mask
  (a blurred `<rect>` as a data-URI `mask-image`; CSS `clip-path` has no soft edge).
- **The stage's oval is softer than pip's picture of the same still** (2026-10-17, the still-mode trial): Remotion
  scales the avatar's video into the oval in the browser, pip's corner pictures are a Lanczos resize, about a fifth
  sharper (edge variance 2,050 against 2,430). A moving avatar hides the difference; a still at the same corner shows
  it as a one-frame snap (6,781 pixels changed by more than 12 levels at the intro's hand-over). Where a still meets the
  stage's oval at the same corner, the box shows the stage's own frame of it (`stage.meets_stage`, the
  `intro_oval_still` and `outro_oval_still` jobs).

## HeyGen's web app and Abacus's Studio images (2026-10-17, R226, R238, R241, R217)

- **HeyGen's web app shows a render's cost only as a coin badge in the editor**, not in the Generate dialog, and the
  Motion Engine defaults to Avatar V for a twin's look: set Avatar IV by hand each time. Avatar IV renders come back
  at 25 fps, so place them by time, never by frame count. A Photo Look moves with generic head motion and hand
  gestures; only "Custom motion" restrains it, at double the price, so a calm Photo Look costs what the normal look
  does (`research/heygen_plan/SAMPLE_PHOTOLOOK_r1.md`).
- **The web app's "WebM (transparent background)" works for the normal look on Avatar V and IV at 1080p** (2026-10-17,
  the intro and outro), despite the help article's "one scene, avatar at 4K" condition: Generate > Format offers it
  (the dialog shows no watermark option for WebM; Resolution 720p, 1080p, 2K marked "2x", 4k), the coins badge
  doesn't change, and the matte, placement and length match the API's Avatar III WebM. The studio's Avatar Background > Remove (free) was
  applied first; whether WebM needs it is untested. Two traps: its edge colour is **premultiplied twice** (colour about
  alpha squared times the subject; the API's WebM once), so `alpha.fix_edges` alone leaves a dark outline round the
  head (8 times the dark edge pixels): divide the alpha out once more first (`stage_edge_fix.py` `fix2` in
  `research/heygen_plan/photo_look/`); and ffprobe shows its tag as `ALPHA_MODE`, in capitals. It comes back at 25 fps
  with Opus sound. Avatar V's Motion Style opens with "More expressive motion" on (the same price off). `alpha.fix_edges`
  takes the count (`alpha.PREMULTIPLIED`: "api" 1, "webapp" 2), recorded with the render by `pipeline.edit.avatar
  webapp`. **Avatar V opens its mouth about half a second before the voice** (a breath: the intro render's mouth is
  closed to 0.96 s, open from 1.04 s, the voice at 1.556 s), so the stage's usual 0.3 s lead opened the video
  mid-breath; such a render records its own lead (`webapp --open-head=0.58`). For the same reason only the first
  second of the upload's 1.5 s pad is a true idle to take a still from: the still avatar is frame 16, 0.64 s
  (`pipeline.edit.still_avatar make`, whose contact sheet shows the eyes' and mouth's stray from the idle).
- **HeyGen's API background replacement** (`background {type: image, asset_id}` with `remove_background: true`) uses
  the same matte as its transparent WebM, so the same edge fringe shows; it is rejected with `output_format` "webm".
  A look recorded on a virtual background leaves that picture in the matte's edge; putting the avatar back on the same
  picture (the cityscape, R232) hides it.
- **Abacus Studio's price is the confirmation card's.** The estimate under the prompt bar leaves out the video
  overhead; only the card shown after Send carries the true price, so read that figure before you confirm. A second
  upload of an identical file is silently dropped: make a repeated input differ by a byte.

## A round's frames from Premiere's exports (R233, 2026-10-17, `pipeline.edit.ppro.exports`)

- **The single-frame export showed the frame a time falls in, not the nearest.** `project.frames()` put the playhead
  on the time's own tick, so 22.033 s (frame 661 written to three places) exported frame 660, one frame early
  whenever a time was rounded down. It now puts the playhead on the nearest frame's first tick, as the exports pick.
- **`exportAsMediaDirect(path, preset, 0)` exports the whole sequence and blocks Premiere until done;** it answers an
  error string (not a throw) for a bad path, and needs an absolute path (a relative one: "OutputFilePath is in a folder
  that doesn't exist!"). No Media pending frames came out of a just-opened project (checked on every export).
- **A PNG sequence's names are padded to the count's digits** (`f000.png` for 569 files, `f0000.png` for 9,467): take
  each file's index from its number. File i is the sequence's frame `i * step`, and there are `floor(frames / step)`
  of them, so the last frame or two have none.
- **A preset's Match Source wins over its frame rate.** `ADBEVideoMatchSource` is a bitmask in base64 with a checksum;
  `AAAAAA==` with checksum 2374864269 (as many of Premiere's own presets write it) turns it off, and `ADBEVideoFPS` is
  ticks per frame (25401600000 for 10 fps). Our presets are Premiere's own with only the named values changed
  (`exports.make_presets`).
- **Premiere's PNG encoder is the slow part:** about 8 frames a second on screen recordings and 5.6 on the cityscape,
  against 37 (main body) to 61 (stage) for the H.264 render; the SD card (G:, exFAT, 70 MB/s) adds about 25% over D:.
  Round 6's main body (15:47): H.264 12.8 min (0.35 GB), PNG at 10 fps 18.7 min (4.3 GB); 167 single frames took 89 s.
- **Premiere's H.264 is unflagged BT.709 limited range** (Main profile, no B-frames): decode with `in_color_matrix=bt709`
  or ffmpeg reads BT.601. Seeking with `-ss` to half a frame before the wanted one, then selecting by `n`, is exact.
- **ffmpeg can't parse a long `select`:** 103 `eq(n,k)` terms failed with "Cannot allocate memory". Pull in groups.
- **The H.264 isn't enough for small text:** at 40 Mbps it is 0.25 to 0.7 levels from the single frame on average, but
  Windows OCR read 2 to 11% of small words differently ("9eeaa7358b" as "9eeaa7368b"). The PNG sequence matched the
  single-frame export pixel for pixel.
