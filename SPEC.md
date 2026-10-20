# AI-Driven Training Video Pipeline: Specification

Design and file formats. Behaviour David decided lives in `RULES.md` and is cited here as R#; numbers live in
`exercises/<ex>/edit_settings.json`. Status and next steps are in `PLAN.md` (not published). Restructured
2026-10-06: section numbers are unchanged because the code cites them.

## 1. Purpose and scope

This pipeline turns a browser-based exercise into a finished YouTube tutorial: David's cloned voice, captions, a visible
cursor, zooms, a branded intro and outro, and optionally a HeyGen avatar. When the product's interface changes, a new
take is recorded by script, not by hand.

- **In scope:** exercises that run in a browser, such as GitHub Codespaces with Claude Code, Amazon Quick and
  QuickSight, and Dash apps.
- **Out of scope for capture:** Power BI Desktop and Tableau Desktop. David records those by hand, and they reuse only
  the narration stage (§2, stage 2) and the assembly stages (stages 6 and 7).
- **Test exercise:** *Build an Interactive Dashboard* (<CLIENT> workshop, `Exercises/Build_an_Interactive_Dashboard.docx`,
  20 steps in 6 Parts).
- **Audience:** the public, standalone YouTube viewer (R12). Narration is adapted from the manual.

### 1.1 Settled in the 2026-10-05 planning session

The test account's GitHub CLI sign-in is kept (R58); each take gets a fresh repo and codespace, never deleted by the
automation (R3); Part 5 is a third segment type, **generated** (§3); the audience is public (R12).

### 1.2 Deviations from the brief (reviewed with David, 2026-10-06)

The brief had 20 numbered decisions. David reviewed each place where this spec differs from or sharpens it; each
outcome now lives in one place.

| # | Deviation | Now in |
|---|---|---|
| 1 | Segment type (`scripted`, `live`, `generated`) is set per step, not per Part | §3 |
| 2 | "Narration finished" means the cached clip's length; the recorder over-records and pacing is made in the edit | R18; §6.2, §6.4 |
| 3 | The narration cache key covers everything that changes the audio; display text vs spoken text; pronunciation toolkit | R31, R32; §5.4, §5.5 |
| 4 | The log stores page coordinates; video coordinates come from geometry measured off the sync flash | §5.3 |
| 5 | The cursor is drawn in the edit | R17; §7.1 |
| 6 | The 1920×1080 frame includes the browser's tabs and address bar (no F11); browser zoom is per exercise; zoom where the work stays | R40–R45; §7.2 |
| 7 | Long prompts are pasted and held while the narration explains them; highlights light up named text | §6.3, §7.4 |
| 8 | Edit approval uses a proxy and an HTML timeline | R55; §8 |
| 9 | Privacy scans are advisory; David decides | R56; §10 |
| 10 | Teachable moments (permission prompts) stay at 1× inside a time-lapse | R39; §6.5 |
| 11 | Workshop code is copied, not imported | R1; §11 |
| 12 | Tool versions are pinned and logged | R21; §5.3 |

The remaining decisions stand as written: 1, 4, 9, 11, 13, 15, 18, 19 and 20. Decision 18 is confirmed: YouTube's
`videos.insert` documentation says uploads from unverified API projects are locked private.

## 2. Architecture by stage

```
 docx ─► [1 Author] ─► steps.json ─► [2 Narrate] ─► audio cache + alignment
                                            │
 lock-down ─► [0 Pre-flight] ──────────────┴─► [3 Run + silent capture] ─► raw video(s) + runlog.jsonl + stills
                                                         │
                                                 [4 Post-run] ─► Claude log, live-step narration, time-lapse picks,
                                                         │        generated step list (Part 5) ─► back to [3]
                                                         ▼
                                               [5 Privacy report] ─► [6 Edit plan + proxy] ─► David approves
                                                                                          │
                                                                    [7 Render] ◄──────────┘ ─► [8 Upload]
```

| # | Stage | Input | Output | Human gate |
|---|---|---|---|---|
| 0 | **Pre-flight and lock-down** | §9 checklist; `steps.json` | `preflight.json` (pass or fail for each item) | Run is blocked on any failure |
| 1 | **Author the step list** | The exercise .docx (text and screenshots); earlier runs | `exercises/<ex>/steps.json`, written by Claude | David approves the narration text |
| 2 | **Narrate** | The `narration` blocks in `steps.json`; `pronunciation.json` | `audio_cache/<key>.mp3` plus `<key>.json` (length, character alignment); `lines.json` manifest | David listens to new lines (spot check) |
| 3 | **Run and capture** | `steps.json`; a fresh take repo; the locked machine | Raw video (one or more files), `runlog.jsonl`, stills | None; the run stops on its own if a step fails |
| 4 | **Post-run** | Run log; Claude session log (`claude_log`); stills | Narration drafts for live steps; time-lapse picks; for Part 5, `steps_generated.json` | David approves live narration and the generated step list |
| 5 | **Privacy report** | Raw video; DOM-scan events in the log | `privacy_report.json` (findings by proxy time); blur masks for findings David marks | Advisory only. David decides blur, ignore or retake while reviewing the proxy. |
| 6 | **Edit plan** | Run log; audio lengths; `edit_settings.json` | `edit_plan.json`; proxy MP4 (540p); `timeline.html` | **David approves** (decision 14) |
| 7 | **Render** | Approved edit plan; raw video; audio; brand assets; intro, outro and avatar clips | Final MP4 (1080p); `captions.srt`; `chapters.txt` | David watches the final cut |
| 8 | **Upload** | Final MP4, captions, chapters, title and description | A private YouTube video (`pipeline/publish/youtube.py`); public release by hand (R5) | David |

Silent capture (decision 6) means that stages 2, 6 and 7 can be rerun without touching stage 3. Editing a narration
line reruns 2→6→7. Changing a zoom rule reruns 6→7. Only a change to the product's UI or to the step list's actions
needs a new take.

## 3. Segment types

| | **scripted** | **live** | **generated** |
|---|---|---|---|
| Example (Dashboard) | Open the CSV; open the Claude Code panel; type a prompt; click Send | Wait for Claude's reply or for the build; read Claude's report | Part 5: click this run's filters, report a real defect |
| Who writes the actions | Claude, from the docx, before the take | Nobody: the driver waits (with a `wait_claude` or `wait` action) and the autopilot approves routine prompts | Claude, after exploring the running dashboard **off camera**, with David's approval |
| Who writes the narration, and when | Claude, before the take (pre-written); David approves | Claude, **after** the run, from the Claude log and stills; David approves | Claude, after exploring and before recording; David approves |
| Timing source | Narration length, cue word and expected result (§6) | Real time, compressed by the time-lapse rules (§6.5) | Same as scripted |
| Failure | Expected result missing by the timeout, or a locator not found → **stop the take** | Timeout (build > 25 min) or a RISKY prompt → **stop the take** | Same as scripted; also if the dashboard state differs from what the exploration found |
| Cursor, zoom, highlights | Full rules (§7) | Approvals and other teachable moments only | Full rules |

Privacy findings never stop a take (R56).

The **generated** procedure runs after the build finishes and before Part 5 is recorded (R70, R71):

1. The take stops recording after Part 4, with the dashboard open; the codespace and the dashboard keep running.
2. With capture off, Claude drives the dashboard tab and reads its layout, controls and charts (screenshots of each
   state).
3. Claude picks 3 to 4 interactions that make the point of Part 5 (a date range, a parameter, a drill-in) and **one
   real defect** that passes R70's four tests, preferring the doc's blank-map example. Without one, it writes an
   improvement request in the doc's style and the take uses the `improvement` variants (R71).
4. Claude writes `runs/<take>/steps_generated.json` in the same format as `steps.json`: the interactions with their
   narration (to their `points`), the defect line, and the feedback prompt (`feedback_prompt`). No approval before
   recording; David reviews the result at the proxy (R70).
5. The driver reloads the dashboard to reset the state, resumes recording, and runs Parts 5 and 6 with the generated
   steps in place of the placeholders. If the reload after Claude's fix still shows the defect, it sends a second
   round of feedback; after two rounds it stops the take and asks David.

**One exercise, one take** (R19).

## 4. Step list format (`steps.json`)

Decision 4 makes the step list the source of truth. Each step has **one** action and **one** narration line. A manual
step that needs two clicks becomes two pipeline steps (`p2.07a` and `p2.07b`).

### 4.1 JSON Schema

The schema is `schemas/steps.schema.json` (the only copy). A step has `id`, `part`, `segment`, one `action` (with its
`target`: tab, frame, locator), one `expect`, and one `narration` (`text`, `spoken`, `cue_word`, `click_word`,
`labels`, `status`, `source`, and for live or generated lines `points`, what the line written later must cover). Optional: `only_if` (conditional steps), `marks` (§7.4), `highlights`,
`dwell`, `zoom`, `timelapse`, `privacy_mask`, `on_fail`, `notes`, `still` (a page screenshot saved to the run folder,
the dashboard still under the opening and recap), `overlay` (a card that shows text whole, §7.4) and `after` (a
line-only step that rides on the footage after another step's result, §6.5). A file may name its parts (`parts`,
the doc's titles).

The opening and recap graphics (R69) have their own text file, `exercises/<ex>/slides.json`: slides of four layouts
(title, list, compare, roadmap) whose items appear on their `at_word`. `pipeline.edit.slides` times them from the voiced
lines and renders the `Slides` composition over the still.

A locator starting with `TODO` is a placeholder until the slice that builds the step confirms it. `runner.missing()`
lists what a step needs that isn't built (from `runner.NOT_BUILT`); `pipeline.s1` refuses a steps file with any gap
before anything opens, and `pipeline.narration.script` renders the file as the script David approves
(`script_<name>.md`, with the gaps, the prompts, and a lint against NARRATION §9).

### 4.2 Worked example: Part 2 of the Dashboard exercise

This covers opening the Claude Code panel, typing the CLAUDE.md rules prompt, sending it, and Claude's live reply. The
locators come from `_work/teach/dashboard.py` and `cs.py`. The Send button's selector has not been confirmed yet.

```json
{
  "exercise": "build_an_interactive_dashboard",
  "version": 1,
  "source_doc": "Exercises/Build_an_Interactive_Dashboard.docx",
  "audience": "public",
  "variables": { "repo": "<YOUR_GITHUB_ACCOUNT>/my-agentic-workshop-take01", "codespace_name": "@runtime" },
  "steps": [
    {
      "id": "p2.07a", "manual_step": 7, "part": 2, "segment": "scripted",
      "action": { "type": "click",
        "target": { "tab": "ide", "frame": "main",
          "locator": ".part.auxiliarybar [aria-label=\"Additional Views\"]" } },
      "expect": { "kind": "visible", "tab": "ide", "frame": "main", "locator": "role=menuitem[name=\"Claude Code\"]", "timeout_s": 5 },
      "narration": { "line_id": "dash.p2.07a",
        "text": "Claude Code lives in the panel on the right. In a new codespace there's no Claude Code tab yet, so click the three dots next to Chat.",
        "cue_word": "click", "status": "draft", "source": "clone" }
    },
    {
      "id": "p2.07b", "manual_step": 7, "part": 2, "segment": "scripted",
      "action": { "type": "click",
        "target": { "tab": "ide", "frame": "main", "locator": "role=menuitem[name=\"Claude Code\"]",
          "fallback": ["text=Claude Code"] } },
      "expect": { "kind": "visible", "tab": "ide", "frame": "claude_panel",
        "locator": "[contenteditable][aria-label=\"Message input\"]", "timeout_s": 15 },
      "narration": { "line_id": "dash.p2.07b", "text": "Then choose Claude Code.",
        "cue_word": "choose", "status": "draft", "source": "clone" },
      "dwell": { "min_s": 1.5 }
    },
    {
      "id": "p2.08a", "manual_step": 8, "part": 2, "segment": "scripted",
      "action": { "type": "type", "typing_mode": "paste",
        "target": { "tab": "ide", "frame": "claude_panel", "locator": "[contenteditable][aria-label=\"Message input\"]" },
        "text": "Before we build anything, add two rules to CLAUDE.md:\n- Keep this file short. When we finish a piece of work, write notes about it in a file in the docs folder, and add a one-line pointer to that file here.\n- When I ask you to commit, commit to the main branch and push it to GitHub. Don't create other branches." },
      "expect": { "kind": "text_in_frame", "frame": "claude_panel", "value": "Don't create other branches", "timeout_s": 5 },
      "narration": { "line_id": "dash.p2.08a",
        "text": "Before building anything, paste in two standing rules for a file called CLAUDE.md. The first keeps that file short, with notes in a docs folder. The second keeps all your work on the main branch. Claude reads CLAUDE.md at the start of every session, so these rules stick.",
        "spoken": null, "cue_word": "paste", "status": "draft", "source": "clone" },
      "highlights": [
        { "match": "Keep this file short.", "cue_word": "short" },
        { "match": "commit to the main branch", "cue_word": "main" }
      ],
      "dwell": { "reading_words": 52 },
      "zoom": { "mode": "auto" }
    },
    {
      "id": "p2.08b", "manual_step": 8, "part": 2, "segment": "scripted",
      "action": { "type": "click",
        "target": { "tab": "ide", "frame": "claude_panel", "locator": "button[aria-label*=\"Send\"]" } },
      "expect": { "kind": "text_in_frame", "frame": "claude_panel", "value": "Queue another message", "timeout_s": 10 },
      "narration": { "line_id": "dash.p2.08b", "text": "Send it.", "cue_word": "Send", "status": "draft", "source": "clone" },
      "notes": "Send-button selector to be confirmed in slice S6 (the panel sits inside nested cross-origin iframes)."
    },
    {
      "id": "p2.09", "manual_step": 9, "part": 2, "segment": "live",
      "action": { "type": "wait_claude", "max_wait_s": 240 },
      "expect": { "kind": "claude_idle", "timeout_s": 240 },
      "narration": { "line_id": "dash.p2.09", "text": null, "cue_word": null, "status": "pending_post_run", "source": "clone" },
      "timelapse": { "mode": "auto", "keep_events": ["prompt_seen", "prompt_approved"] }
    }
  ]
}
```

The narration for `p2.09` is written after the run from what Claude actually said. A typical line would be: "Claude
added both rules to CLAUDE.md and showed us the change."

## 5. Run log format (`runlog.jsonl`)

The first line is a header record, and every later line is an event record. Times are seconds on a monotonic clock
(`t_mono`), measured from `mono_origin` in the header. Wall-clock time is kept as well, for matching against the Claude
session log.

### 5.1 JSON Schema

The schema is `schemas/runlog.schema.json` (the only copy); each line is validated against it. The header carries the
run id, steps version and hash, variables, machine, browser, captures (each with its `geometry` and `sync`), tool
versions and the narration profile. Events carry `t_mono`, `t_wall`, `step_id`, `phase`, the target's page box and
`frame_chain`, `line_id`, `result` and `detail`.

### 5.2 Worked example: the log for `p2.08b` and the start of `p2.09`

```jsonl
{"record":"header","run_id":"dashboard_20261012_take01","exercise":"build_an_interactive_dashboard","steps_version":1,"steps_sha256":"3f9c…","started_wall":"2026-10-12T14:02:11.204-05:00","variables":{"repo":"<YOUR_GITHUB_ACCOUNT>/my-agentic-workshop-take01","codespace_name":"<CODESPACE_NAME>"},"machine":{"windows_scaling_pct":100,"capture_monitor":"DISPLAY1","monitor_px":{"w":1920,"h":1080}},"browser":{"channel":"msedge","version":"141.0.3537.57","viewport_css":{"w":1536,"h":778},"device_scale_factor":1.25,"browser_zoom_pct":125,"tab_layout":"top"},"captures":[{"id":"obs","method":"obs","file":"raw/obs.mkv","source":"screen:DISPLAY1","geometry":{"calibration":"sync_marker","viewport_origin_px":{"x":0,"y":107},"px_per_css":1.25,"video_px":{"w":1920,"h":1080},"fps":60},"sync":{"start_marker_t_mono":0.0,"end_marker_t_mono":2710.4,"start_marker_video_s":null,"end_marker_video_s":null}},{"id":"ide_cast","method":"page_screencast","file":"raw/ide.webm","source":"tab:ide","geometry":{"calibration":"sync_marker","viewport_origin_px":{"x":0,"y":0},"px_per_css":1.25,"video_px":{"w":1920,"h":972},"fps":30}}],"tools":{"python":"3.14.0","playwright":"1.63.0","obs":"32.0.1","obs_websocket":"5.6.2","edge":"141.0.3537.57"},"narration_profile":"a41be0c2…"}
{"record":"event","t_mono":412.310,"t_wall":"2026-10-12T14:09:03.514-05:00","step_id":"p2.08b","phase":"step_start","action":"click","tab":"ide","url_host":"<CODESPACE_NAME>.github.dev","target_css_box":null,"frame_chain":[],"line_id":"dash.p2.08b","result":null,"detail":{"narration_len_s":0.92,"cue_offset_s":0.08}}
{"record":"event","t_mono":412.318,"t_wall":"2026-10-12T14:09:03.522-05:00","step_id":"p2.08b","phase":"cursor_move_start","action":"click","tab":"ide","url_host":"<CODESPACE_NAME>.github.dev","target_css_box":{"x":1490.0,"y":807.5,"width":24.0,"height":24.0},"frame_chain":["main","iframe.webview","iframe#active-frame"],"line_id":"dash.p2.08b","result":null,"detail":{"from_css":{"x":1180,"y":760}}}
{"record":"event","t_mono":412.851,"t_wall":"2026-10-12T14:09:04.055-05:00","step_id":"p2.08b","phase":"cursor_arrive","action":"click","tab":"ide","url_host":"<CODESPACE_NAME>.github.dev","target_css_box":{"x":1490.0,"y":807.5,"width":24.0,"height":24.0},"frame_chain":["main","iframe.webview","iframe#active-frame"],"line_id":"dash.p2.08b","result":null,"detail":null}
{"record":"event","t_mono":413.153,"t_wall":"2026-10-12T14:09:04.357-05:00","step_id":"p2.08b","phase":"action","action":"click","tab":"ide","url_host":"<CODESPACE_NAME>.github.dev","target_css_box":{"x":1490.0,"y":807.5,"width":24.0,"height":24.0},"frame_chain":["main","iframe.webview","iframe#active-frame"],"line_id":"dash.p2.08b","result":"ok","detail":{"point_css":{"x":1502.0,"y":819.5}}}
{"record":"event","t_mono":413.902,"t_wall":"2026-10-12T14:09:05.106-05:00","step_id":"p2.08b","phase":"expect_met","action":null,"tab":"ide","url_host":"<CODESPACE_NAME>.github.dev","target_css_box":null,"frame_chain":["main","iframe.webview","iframe#active-frame"],"line_id":"dash.p2.08b","result":"ok","detail":"Queue another message"}
{"record":"event","t_mono":414.903,"t_wall":"2026-10-12T14:09:06.107-05:00","step_id":"p2.08b","phase":"step_end","action":null,"tab":"ide","url_host":"<CODESPACE_NAME>.github.dev","target_css_box":null,"frame_chain":[],"line_id":"dash.p2.08b","result":"ok","detail":null}
{"record":"event","t_mono":414.910,"t_wall":"2026-10-12T14:09:06.114-05:00","step_id":"p2.09","phase":"step_start","action":"wait_claude","tab":"ide","url_host":"<CODESPACE_NAME>.github.dev","target_css_box":null,"frame_chain":[],"line_id":"dash.p2.09","result":null,"detail":null}
{"record":"event","t_mono":420.955,"t_wall":"2026-10-12T14:09:12.159-05:00","step_id":"p2.09","phase":"claude_state","action":null,"tab":null,"url_host":null,"target_css_box":null,"frame_chain":[],"line_id":null,"result":null,"detail":{"state":"working","last_tool":"Edit:CLAUDE.md","sub_age":99999}}
```

**Coordinates in the Claude Code panel.** The panel is a VS Code webview: an iframe inside an iframe, both cross-origin.
Playwright documents `bounding_box()` as returning coordinates relative to the main frame's viewport, child frames
included. Nothing confirms that for out-of-process (cross-origin) iframes. Slice S6 tests it, and the step logs
`frame_chain` so a correction can be applied later if it turns out to be needed. The fallback is to add each frame
element's own `bounding_box()` along the chain.

### 5.3 Mapping to video and keeping in sync

- **Mapping:** `video_px = viewport_origin_px + css_px × px_per_css`. These values come from the capture's `geometry`.
  Zoom, cursor and highlight rendering use only this mapping.
- **Sync marker:** a full-viewport orange (#ED7D31) overlay injected into the active tab for 200 ms at the start and
  end of each capture, and after any change of browser zoom or tab layout. Each one is logged as a `sync_marker` event.
- **Timing:** obs-websocket events carry no timestamps, so post-run detection finds the marker frames in each video.
  Two markers give both the offset and the drift.
- **Geometry calibration:** the marker fills exactly the visible page, so the edges of the orange rectangle in the
  video give `viewport_origin_px` and `px_per_css` directly (`calibration: "sync_marker"`). That holds whatever the
  browser zoom and wherever the tabs sit: top, vertical down the side, or none. Geometry worked out from browser
  metrics (`computed`) is logged as a cross-check. A difference of more than 2 px is a warning.
- **Page screencast:** gets its own markers in the same way.
- **Tool versions** go into the header on every run. If the edit stage finds an unknown version, it warns.

### 5.4 Narration cache key

```
key = sha256(json.dumps({
  "engine": "elevenlabs", "voice_id": ..., "model_id": ..., "voice_settings": {...},
  "dictionaries": [{"id": ..., "version_id": ...}],      # only if server-side dictionaries are used
  "spoken_text": <display text after respelling (§5.5)>,
  "tighten": [<terms whose inner gaps were tightened>],
  "previous_text": <neighbour's spoken text or null>, "next_text": <neighbour's spoken text or null>,
  "output_format": "mp3_44100_128"
}, sort_keys=True))[:20]
```

- **Files:** `audio_cache/<key>.mp3` and `audio_cache/<key>.json`, holding the length, the `request-id`, and the
  character alignment from `/v1/text-to-speech/{voice_id}/with-timestamps`.
- **`exercises/<ex>/lines.json`** maps `line_id → key`, along with status and text.
- **Neighbouring lines** (R32) go into the key only on engines with request stitching. ElevenLabs says stitching is
  not available on `eleven_v3`. Phase 0's edge-tts key leaves them out.
- **Live source** (`source: live`): `recordings/<line_id>__<sha8(text)>.wav`. When the text changes, the take is
  marked stale, and pre-flight lists the stale takes for David to record again.
- **Captions use the display text** (R31). "Tab Low" never appears on screen.

### 5.5 Pronunciation toolkit

The principle is R31. The display text is the approved script and the captions ("Tableau", "CLAUDE.md"); the spoken
text is what the voice gets ("Tab Low", "Claude dot M D"). Label pauses (R26) are added to the spoken text too.

- **Respelling happens locally, before sending,** not only through ElevenLabs' server-side dictionaries. That makes
  what was sent visible, works on every model, and the cache key covers it automatically.

`exercises/<ex>/pronunciation.json` (plus a shared `pronunciation_common.json` for terms used in every course):

```json
{
  "terms": [
    { "display": "CLAUDE.md", "spoken": "Claude dot M D", "tried": ["Claude dot MD", "Claude M D"], "tighten": false },
    { "display": "Tableau", "spoken": "Tab Low", "tried": ["Tab-Low", "Tablow", "Tab-loh"], "tighten": true }
  ]
}
```

Escalate, in this order, until David accepts the term by ear:

1. **Respell** it in the table. Matching is whole-word and case-sensitive, and the longest match wins.
2. **Audition.** `narration audition "<term>"` generates every candidate spelling inside a **real sentence from the
   script**, because words sound different in context. The clips are labelled side by side. David picks one; it
   becomes `spoken`, and the losing candidates go into `tried`.
3. **Phonetic rules** (IPA or CMU) through an ElevenLabs dictionary, on models that support them. Support differs by
   model, and ElevenLabs' own docs disagree, so check on the chosen model.
4. **Tighten.** For terms marked `tighten`, the character timestamps locate the term in the audio. Any silence inside
   it longer than 40 ms is shortened to about 15 ms with a 5 ms crossfade, closing the gap between "Tab" and "Low".
   Audio is never spliced in from a different generation, because the tone wouldn't match.
5. **Per-line override:** `narration.spoken` for a one-off that the table shouldn't apply everywhere.
6. **Record that line live** (`source: live`) if nothing else works.

Changing a table entry regenerates exactly the lines that contain the term.

## 6. Timing model

### 6.1 Three clocks (decision 9)

| Clock | Meaning | Source |
|---|---|---|
| **Automation time** | How long the machine takes (page loads, Claude thinking, typing) | Run log |
| **Viewer time** | How long the viewer needs to see a step: the click, its result, any text to read | Rules in §6.3 |
| **Narration time** | Length of the line | Audio cache (`<key>.json`) |

The raw recording follows automation time. The edited timeline follows viewer time and narration time. Automation time
in excess of those is cut or time-lapsed (R35, R37, R39).

### 6.2 How the driver paces a scripted step (during the run)

For step *i* with narration length `N`, cue offset `c` (the start time of `cue_word` in the alignment, or 0.3 s if
there is no cue word), cursor travel `m` and pause before the click `p = 0.3 s`:

```
t0            = step_start (virtual narration starts here; nothing plays)
cursor start  = t0 + c              ; announce, then act (R23)
cursor arrive = cursor start + m          ; m = clamp(0.35 + dist_css/1800, 0.4, 1.0) s
action        = max(cursor arrive + p, t0 + k + 0.35)   ; k = start of click_word (the target's name), if set
result        = first time expect is met  (failure if > timeout_s → stop the take)
step_end      = max(t0 + N + 1.5,  result + V + 1.0)  ; V = viewer time (§6.3); generous on purpose
              ; and ≥ result + N + 1.5 when result − action > LONG_WAIT_S (the edit cuts the wait, so the line plays after it)
```

The driver over-records (R18): cutting extra footage is free; inventing missing footage means freeze frames. A step
with marks also holds for each mark's draw, hold and release before the click (R49, R50; `runner.mark_gesture`).

### 6.3 Viewer time, `V`

| Action | Minimum after the result |
|---|---|
| click, key, hover, navigate | `viewer_time.<action>` in `edit_settings.json` (a navigate counts from the page load) |
| type, `full` (prompts of about 80 characters or less) | typing at a natural 12 to 15 characters per second, then 1.0 s |
| type, `paste` (longer prompts) | appears at once; the zoom holds while the narration walks through the key phrases (with highlights, §7.4), for at least the reading time |
| Any step with `reading_words` | **reading time = min(12, max(2.0, reading_words ÷ 3.0)) s**. That is 180 words per minute, capped at 12 s, because viewers can pause to read a long block. |
| `dwell.min_s` | Overrides with a larger value |

### 6.4 Pacing and cut rules (decision 11), applied in `edit_settings.json`

The finished video plays at human pacing, made here by cutting and by lining voice up with picture (R18). The edit lays
the narration first, using the `pacing` settings, then fits the picture to it with the `cuts` settings:

| Setting | Meaning |
|---|---|
| `pacing.gap_between_lines` | Silence between consecutive lines |
| `pacing.pause_after_result` | Picture-only time after a click's result before the next line |
| `pacing.pause_at_part_boundary` | Extra pause at a Part change (0.8 s, R82) |
| `pacing.picture_before_line` | Picture before a line's first word |
| `pacing.max_silence_s` | Longest gap without talking (R25); longer gaps are cut down or warned |
| `cuts.keep_before_move`, `keep_after_action`, `keep_before_result` | Footage kept around each action |
| `cuts.cut_above_s` | Gaps longer than this get the gap treatment; shorter ones stay at 1× |
| `cuts.gap_treatment` | `cut` (default, R35), `swipe` or `speed` (`speed_min`, `speed_max_s`) |
| `cuts.hold_warn_s` | Freeze-holds longer than this are warned (R36) |
| `cuts.work_cut_transition` | The transition on a cut of Claude's working time (R83): type, length, alignment |

1. Keep footage around every action and its result, out to the end of its line.
2. Gaps longer than `cut_above_s` get the gap treatment; joins are hard cuts (R34).
3. A cut never splits a line (R38).
4. If the picture runs out before the line does, hold a frame (an ffmpeg still, GOTCHAS) and warn above `hold_warn_s`.
5. A cut of Claude's working time (from a prompt's send to Claude going idle) gets a 1.0 s Page Peel on the camera
   sequence, one per prompt at its last cut before the result (R83); the plan lists them in `transitions`. `EditPass`
   shows them as hard cuts; Premiere gets transition items (below).

### 6.5 Live waits: time-lapse and title cards (decision 3)

The treatments by wait length are R39; no speed label is shown (R37). Kept at 1× inside
any time-lapse (`keep_events`):

- Permission prompts, from `prompt_seen` to 2 s after `prompt_approved`.
- **Error-then-fix moments** proposed by Claude from the session log, where a failing tool result is followed by the
  fix. David approves them in the edit plan.

Live-step narration (written after the run) is laid over the time-lapse and the 1× moments.

**As built (S7, 2026-10-07).** Recording: the runner's `wait_claude` polls the panel every 0.5 s (busy, idle,
attention) and Claude's session log over gh every 5 s in a background thread; done means the panel idle for 2 s and
the log's turn ended with no reviewer still running. A permission prompt is logged (`prompt_seen`), held 1.5 s, and
approved with a logged cursor move and click (`prompt_approved`); a RISKY one stops the take; attention with no Yes
button is a question (`claude_question`) and ends the wait. Tabs that open by themselves during a wait (the
template's `onAutoForward: openBrowser` on port 8050) are closed and logged. A `scroll` step jumps to the start of
Claude's last reply below the pinned prompt and scrolls through it at `READ_PX_S`. After the take the session logs go
to `runs/<id>/claude/`; `pipeline.post.live` digests them per live step with stills (`live_harvest.md`). Edit:
`edit_settings.json` `timelapse` (a lapse of `lapse_s`, or `card_s` of title card plus `long_lapse_s`; the prompts
play on top at 1x; a lapse stretches to fit its line; a reply scroll is sped to `scroll_s` or its line). The card is a
hold carrying `card` (Remotion `TitleCard`; in Premiere its own transparent track). The cursor is hidden during waits
except approvals (`cursor.hidden`, R47).

**After David's review of s7_take06 (R75 to R79, 2026-10-07; `docs/S7_FIX_PLAN.md`).** A wait step may override
the lapse threshold (`timelapse.realtime_max_s`: the tool calls that read the data are seen sped up rather than cut)
and hold 1x footage before the card (`timelapse.before_card_s`: the skill row on screen as the build starts is named
and marked first). A lapse stretches only to what is left of its line after the prelude and the result at 1x, so a
line may finish over the result. A **line-only step** (`after: "<step>"`, action `none`) rides on the footage after
that step's result: the runner skips it, the edit lays its line after the previous one (R25) and the next step's
bridge keeps the picture rolling under it (p4.12b: app.py and the summary, after the build). A wait is never a
navigation for the camera (its action has no target), so the panel stays at its zoom through a short wait and its
lapse; a lapse with a title card (a long build) holds the whole frame, the panel and the Explorer where files appear.

### 6.6 Everything is computed on the edited timeline (decision 12)

The edit stage first builds the cut list and lays the narration, and only then places zooms, highlights and cursor animation, in
edited-timeline time. Moving a cut never needs a new recording.

## 7. Cursor, camera and marks

Everything here is drawn in the edit (R17) and placed on the edited timeline (§6.6).

### 7.1 Cursor (decision 10)

- **The real pointer stays out of the capture** (R15).
- **The synthetic cursor is drawn by Remotion from `cursor_move_start` / `cursor_arrive` / `action` events,** as an
  arrow sprite sized by `cursor.height_px`, in source space inside the camera so it grows with the zoom (R46). It moves from its last resting point along a slight arc with
  ease-in-out (R45), starts on the cue word and clicks after the target's name (R23).
- **The click effect** is a ring that grows to `cursor.ring_diameter_px` over 350 ms and fades out, with no sound
  (colour: R51).
- **After the click,** the cursor rests on the target through the result. On the next step it moves from that point.
- **While typing,** the cursor moves 60 px down and to the right of the input before `type_start`, so it doesn't cover
  the text.
- **During live segments** see R47.
- **Playwright moves the page's mouse along the same path** (`mouse.move(x, y, steps=N)`), so hover states in the page
  match what the viewer sees. A drawn mark's gesture is a mouse path too (R49).

### 7.2 Camera: beats and full-frame spans

The rules are R40 to R45; the numbers are `edit_settings.json` `zoom`; the code is `pipeline/edit/camera.py` (planning)
and `remotion/src/camera.ts` (rendering).

- **Beats** are moments when a box must be on screen: a click target as the cursor arrives, a mark as the cursor sets
  off to draw it, the subject of a line as the line starts.
- **Full-frame spans** are where navigation matters: a navigate step until its URL has been shown (its marks released),
  and a click that opens a new tab from the click until the new page has been seen.
- **Between them** the camera zooms in on the coming beats that fit at `zoom.level` (at least `min_level`; a beat
  from a step with `zoom.max` raises its shot's level, up to the cap), keeping
  `margin_px` around them and cropping the browser chrome (`crop_chrome`); it refits or pans for a beat outside the
  view.
- **Keyframes** are `{t, s, x, y}`: edit time, scale, and the source-frame point at the centre of the output. The
  renderer interpolates linearly and keeps the view inside the frame. At a cut the change is instant.
- **Per step,** `steps.json` can force a zoom (`zoom.mode: manual` with `region_css`) or block one (`zoom.mode: none`).

### 7.3 Zoom cap

Replaced by R42 (`zoom.max`). The old 1.5x cap from 1080p capture is gone; a supersampled source is needed only if
the phone check finds 2x too soft.

### 7.4 Marks and highlights

The kinds, timing and style of marks are R48 to R51; the numbers are `edit_settings.json` `marks`.

- **Step list:** each of a step's `marks` has a `kind` (`rect`, `arrow`, or `highlight`: a large region such as a pane
  or a card lit while everything else is dimmed, R142), a `style` (`draw` in the flow, `fade` for
  overview moments), the naming word `at_word`, an optional `until_word`, and a `target`: the step's own click target
  or the element its `only_if` found (`of`), a `locator` with `match` text, or browser chrome (`chrome:
  address_bar`, found by OCR). Schema: `schemas/steps.schema.json`. `highlights: [{match, cue_word, occurrence, style}]` light up
  text on screen as the narration names it (§4.1).
- **Position:** the driver measures page targets during the take (page coordinates, logged). Text the page can't
  report, and browser chrome such as the address bar, is found by Windows OCR in the video frame
  (`pipeline/privacy/winocr.ps1`). The same OCR route serves hand-recorded desktop videos (Phase 6).
- **Live marks** (`of: action` or `subject`, R49) are performed by the runner as mouse gestures; the edit draws the
  shape from the logged gesture. **Synthesized marks** (everything else) are placed by `plan.py` on their naming word.
- **Camera:** a mark outside the current view is a beat (§7.2).
- **Text highlights** (a phrase in a pasted prompt, each half of `SUM(Profit)/SUM(Sales)`): not built; their style is
  decided in S6.
- **Overlays (R77, R79; S7, 2026-10-07):** a step's `overlay` puts a card in David's BulletPanel look (opaque, so
  legible on any background) on one edge of the frame, from the step's line start to the end of `until_step`'s
  line. `layout: text` shows a whole text (the dashboard prompt, which scrolls inside the message box); marks whose
  `target.overlay` names the card become **highlights** on it: an orange outline (R51) that fades in on the naming
  word, holds to the end of the sentence (`until_word` overrides), fades out, like an overview mark (R48). `layout:
  list` shows items that appear on their `at_word` (the reply's main points, worded as what Claude *may* suggest,
  R76). The card runs from 40 px down to 260 px above the bottom, so the bottom caption row stays free; captions keep
  off it (`marks.overlay_box`). `edit_plan.json` carries `overlays`; Remotion `Overlays` draws them in screen space
  above the camera; the Premiere export renders one transparent clip per card on an "Overlays" track.
- **OCR spans:** a target with `match_to` boxes from one text to another (the question form from its first question
  to "Esc to cancel"; the tab strip from the first tab's title to the second's, `chrome: tab_strip`). OCR lines on
  one row are also read joined (a tool row comes back as "Read" and "CLAUDE.md" separately).

## 8. Edit settings, edit plan and approval (decisions 13 and 14)

Three kinds of file, kept separate so cuts and zooms can change without a re-recording:

| File | Owner | Changes when |
|---|---|---|
| `exercises/<ex>/steps.json` | Claude writes it; David approves the narration | The actions or narration change |
| `runs/<take>/runlog.jsonl` | The driver; never edited | Never (a new take writes a new log) |
| `exercises/<ex>/edit_settings.json` | David and Claude | Cut, zoom, cursor, time-lapse or caption rules change |
| `runs/<take>/edit_plan.json` | Generated from the three above | Every time stage 6 runs |

`edit_plan.json` lists, in edited-timeline seconds:

- clips (source file, in, out, speed)
- holds
- narration placements
- zoom keyframes
- cursor keyframes
- title cards
- highlight keyframes
- privacy masks (only the findings David chose to blur)
- caption cues
- warnings (holds over `hold_warn_s`, gaps over `max_silence_s`, clicks outside `click_after_name_max_s`, unmatched
  sync markers, geometry mismatch, mark not found)

**Approval package:**
- `edit_plan.json`
- a 540p proxy MP4 with everything in place (narration, cursor, highlights, zooms, title cards, captions)
- `timeline.html`: one row per step, with thumbnails, kept and cut spans, zoom and highlight bars, warnings, and the
  privacy findings as markers (§10)

**Notes by proxy time** and the approval gate: R55, with retakes as a last resort (R20). Built (S5):
`python -m pipeline.edit.review runs/<take>` renders the proxy and writes `timeline.html` (lanes for picture,
narration, captions, zoom, marks and privacy; steps with thumbnails; notes by time copied to Claude; privacy choices
copied as `privacy_decisions.json`; a phone view). `python -m pipeline.edit.final runs/<take> --approve` records David's
approval for that exact plan; without `--approve` it renders `final/<take>_1080p.mp4` and refuses any other plan.

**Premiere export** (R61): `pipeline/edit/premiere.py` writes `runs/<take>/premiere/` from `edit_plan.json`: a Final
Cut Pro 7 XML (a top sequence with the camera on a nested source sequence, overview marks and narration), transparent
ProRes 4444 clips rendered by the Remotion `OverlayClip` composition (`only: cursor | mark:<i>`), overview marks as
native layers (rectangle images; Arrow01 with keys per stop), `captions.xml` (TTML, nine full-screen regions = the
caption grid) and `captions.srt`, both with a one-frame anchor cue at 0:00. Its docstring holds the track layout and Premiere's XML conventions (Center normalised by media size,
keyframe times in the clip's own frames, 1-hour in points on stills).
With R83 transitions the camera track's nest is cut into pieces, each with its slice of the camera keys and a
`transitionitem` between them (start or end -1 where a transition holds the clip, Premiere's convention);
`<run>_hard_cuts.xml` is the same edit without them, in case the import refuses them.

**The line check** (R85): `python -m pipeline.edit.linecheck runs/<take>` before every export round. It OCRs the source
frame cropped to the camera's view at each sentence's first and last word (less what an overlay card covers, plus the
card's text) and lists the sentence's words not readable then (R75, R81); sets each overlay item beside its sentence
(R80); measures every sentence-end pause (R31); finds silences over a still picture beyond `gap_between_lines` plus the
part pause (R25, R82), overlapping captions and a cursor shown in a live step (R47); crops every mark at full resolution
(R84); and renders EditPass stills (captions on) at every line start, mark, overlay item and transition, six to a sheet.
Claude reads the report and the sheets, fixes what is wrong, and lists the rest as questions with the round.

**Captions** (R52 to R54): cues are cut from the display text and word timings, wrapped by `captions.max_chars` and
`max_lines` (guidelines, R59), placed per cue by `plan.py` `place_captions`, burned in by `EditPass`, and written to
`captions.srt`. **Chapters** (`chapters.txt`) come from Part boundaries on the edited timeline, ready to paste into
the YouTube description.

## 9. Machine lock-down checklist (pre-flight, decision 16)

Pre-flight writes `preflight.json`, and any failure blocks the run.

| Area | Check | Automated? |
|---|---|---|
| Display | Capture monitor is the **right-hand monitor** (DISPLAY1, x = 1920), 1920×1080 at Windows scaling 100% | Yes (screen bounds) |
| Display | **No taskbar on the capture monitor** (R13): its working area must equal its full 1920×1080 bounds, so that a maximized Edge fills the frame exactly | Yes (blocks the run) |
| Capture | OBS Display Capture of the right-hand monitor in the `AIDV` profile (R13); the take's own Edge window maximized there (R14). Display Capture replaced Window Capture in S1 because OBS finds windows by title, and Edge's title changes on every page. | Yes (the topmost window on the monitor must be Edge; the window must be maximized there) |
| Display | The real pointer is off the capture monitor; OBS "Capture Cursor" is off (R15) | Pointer yes; OBS setting yes (through obs-websocket) |
| Notifications | Windows Do Not Disturb is on; Teams and Outlook are closed; no Windows Update restart is pending | Partly (process list); David confirms DND |
| Browser | Edge is started by the workshop's `start_browser` with its own profile, CDP on port 9333, signed out of the Microsoft account (R7) | Yes (profile check) |
| Browser | Browser zoom and tab layout (top, vertical or none) match the exercise's settings (the default zoom waits for David's phone check) | Yes (reads `innerWidth`, `devicePixelRatio`, window bounds; recorded in the run header) |
| Browser | Toolbar items hidden for recordings (R16) | Partly (Copilot and Favorites) |
| VS Code | Do Not Disturb is on (bell); theme and font size are fixed. These are set before capture starts, off camera | Yes (command palette, off camera) |
| Account | Signed in as **<YOUR_GITHUB_ACCOUNT>** only; the take repo was created fresh from the template; the codespace has been created and the trust prompt not yet answered | Yes (`gh` with the test account's config dir) |
| Secrets | `ANTHROPIC_API_KEY` Codespace secret reaches the take repo, by a per-take tick or by being scoped to all repositories (David decides before S6). David does any tick (R4). | Checked (the secret's name only) |
| Claude log | `gh codespace ssh` works through `%USERPROFILE%\.workshop\gh` | Yes |
| Narration | Every `scripted` and `generated` line is `approved` and present in the cache under its current key | Yes |
| Tools | Pinned versions match the lock file; ffmpeg on PATH; OBS is running with the pipeline's profile and scene | Yes |
| Disk | At least 20 GB free on the drive holding `runs/` | Yes |
| Privacy | No email address, AWS account number or key value is visible on the starting screen (DOM scan). A finding is a warning, never a block (R56). | Yes (advisory) |

## 10. Privacy (decision 17): advisory report, David decides

The checks advise and David decides (R56). This section is the mechanics.

**During capture:** at every `step_end` and every 10 s during live waits, the driver scans the visible text of every
frame in the active tab. A match is logged as a `dom_privacy_hit` event, and recording continues. These are the
patterns:

- email addresses: `[\w.+-]+@[\w-]+\.[\w.]+`
- 12-digit numbers: `\b\d{12}\b`, also with dashes, `\b\d{4}-\d{4}-\d{4}\b`
- `sk-ant-[\w-]{8,}`
- `AKIA[0-9A-Z]{16}`
- `gh[pousr]_[A-Za-z0-9]{20,}`
- `[A-Z_]*(KEY|SECRET|TOKEN)[A-Z_]*\s*[=:]\s*\S{8,}` (the `[A-Z_]*` after it catches `AWS_ACCESS_KEY_ID=`)

**After capture:** OCR runs on frames sampled at 1 fps and on every event frame. Windows' built-in OCR is preferred,
because it needs no install. It uses the same patterns.

- **Built (2026-10-06):** `pipeline/privacy/winocr.ps1` OCRs a folder of frames and returns word boxes.
  `pipeline/privacy/blur.py` blurs boxes over time spans in a finished video and never overwrites its input.
- **Where Quick Sight shows an AWS account ID on screen:** the account dropdown (its "Username" can be the ID),
  the S3 knowledge-base wizard's instance-account field, and the AWS console header. Steps that open these screens
  should expect a finding.

**The report** (`privacy_report.json`, also shown as markers on `timeline.html`):

- Each finding gives the **proxy time**, the pattern and a thumbnail, for example "2:32: possible email address,
  top right".
- Findings in footage the edit cut out are dropped, so the report covers only what viewers would see.
- For each finding, David chooses **blur** (a `privacy_mask` box over that time span in the edit plan), **ignore**
  (for example, a 12-digit row count in the data), or **retake**.
- An open finding doesn't block anything. It just stays on the list until David marks it.

**Raw footage** keeps whatever was on screen (R56). If a finding was a real exposure, David decides whether to delete
that take's raw files once the final video is done. Keys and passwords: R4.

## 11. Reuse of workshop scripts

Source folder: `<DOCUMENTS_DIR>\Learning-David-Pc\Workshops\2026-10-08_<CLIENT>\automation\`.
Read-only (R1): files are copied into `pipeline/vendor/` with a provenance header.

| Workshop file | What is reused | How |
|---|---|---|
| `start_browser.ps1` | Edge with its own profile and CDP port 9333; the persistent GitHub sign-in | Copied. The window is maximised on the capture monitor, and browser zoom is applied from the exercise's settings. The same profile directory is reused, so the sign-in carries over. |
| `cs.py` | `browser()` (`connect_over_cdp`), `page(url_contains)`, `find()`, `frame_with()`, `tabs()` | Copied. ROOT, EXERCISE and SHOT_DIR removed. `page()` matches the exact host `{codespace_name}.github.dev` (workshop lesson: a prefix match picks the app tab). |
| `approve.py` | `click_yes()` | Copied, then wrapped so each approval goes through the logged-click path (cursor and events). |
| `autopilot.py` | `RISKY` regex and `prompt_text()` | Copied. The loop itself is not reused: the driver's `wait_claude` replaces it. |
| `watch.py` | `state()` | Copied, but used **only** to detect permission prompts. "Busy" or "idle" comes from the Claude log, because UI strings change. |
| `claude_log.py` | `status()` and its REMOTE script | Copied. A `fetch_session()` is added to pull the full session JSONL for post-run narration. Note: `gh codespace ssh` restarts a stopped codespace. |
| `teach.py` | The `_mp3()` / `prepare()` pattern (retry, prepare lines ahead, cache) | Pattern only. The backend becomes ElevenLabs and the key follows §5.4. Word and MediaPlayer code is not reused. |
| `_work/teach/dashboard.py` | Locators (Explorer, CSV row, Additional Views, Ports tab with globe for 8050, Plotly bar click point, Source Control), `type_prompt()`, `wait_claude()` reviewer logic (`sub_age`, "I'll report back") | Reference, used to seed `steps.json`. Its codespace name and step numbers are out of date. |
| `annotate.py` | `Shot` (crop, box, padding) in orange #ED7D31 | Copied for contact sheets, privacy-mask previews and timeline thumbnails. |
| `annotate_*.py` | Per-exercise crop coordinates | Not reused. They are for still screenshots. |
| `snap2x.py`, `_work/gh_narrow.py` | CDP `Emulation.setDeviceMetricsOverride` | Reference for screencast supersampling. The 860 px narrow width is **not** used. |

Workshop lessons that carry over are in `GOTCHAS.md`.

## 12. Folder layout

This is the private project's layout as planned on 2026-10-05, kept as written. The published copy differs: it
adds `pipeline/ml/`, `pipeline/generated/`, `pipeline/publish/` and `tools/`, and has none of `author/`, `intro/`,
`brand/`, `docs/`, `SESSION_HANDOFF.md`, `PLAN.md`, `schemas/edit_plan.schema.json` or `.claude/skills/`.

`./` is a subfolder of the VideoProduction workspace (`D:\Videos`), so it already inherits that
workspace's hooks and steering. It needs no `projects.json` entry.

```
AIDrivenVideo/
  CLAUDE.md  RULES.md  GOTCHAS.md  SESSION_HANDOFF.md  SPEC.md  PLAN.md  .gitignore
  docs/SLICE_LOG.md         slice results
  pipeline/                 Python package
    vendor/                 copied workshop helpers with provenance headers (§11)
    preflight.py            stage 0
    author/                 stage 1: docx → steps.json drafts
    narration/              stage 2: ElevenLabs client, cache, pronunciation sync, live-take manifest
    driver/                 stage 3: step runner, cursor-path mouse moves, expect checks, logger, autopilot hook
    capture/                OBS (obs-websocket) controller, page screencast, sync markers
    post/                   stage 4: Claude-log fetch, live narration drafts, time-lapse picks, generated steps
    privacy/                stage 5: DOM patterns, OCR scan, report
    edit/                   stage 6: edit_plan builder, proxy render, timeline.html
  schemas/                  steps.schema.json, runlog.schema.json, edit_plan.schema.json
  exercises/
    build_an_interactive_dashboard/
      steps.json  lines.json  pronunciation.json  edit_settings.json
    pronunciation_common.json   terms shared by every course (Tableau, QuickSight, CLAUDE.md, ...)
  runs/                     (git-ignored) <run_id>/ raw/ runlog.jsonl stills/ claude_session.jsonl
                            steps_generated.json privacy_report.json edit_plan.json proxy.mp4 timeline.html final/
  audio_cache/              (git-ignored) <key>.mp3 + <key>.json
  recordings/               (git-ignored) live narration takes <line_id>__<sha8>.wav
  remotion/                 tutorial assembly: Cursor, ClickRing, ZoomCamera, Cuts, Captions, TitleCard compositions
  intro/                    intro, outro and chapter transitions (HyperFrames or Remotion, per question D)
  brand/                    pointers to Global Assets (logo, colours, fonts); no copies of large media
  .claude/skills/training-video/SKILL.md   (later, outline in PLAN.md)
```

- **Git:** media, the audio cache, recordings and runs are git-ignored. `D:\Videos\.gitignore` already excludes
  binaries; this folder adds its own entries.
- **Keys:** R4 (`pipeline/config.py`).
- **Skill installs** (R9):
  - `playwright-cli install --skills`
  - `npx skills add elevenlabs/skills`
  - `npx skills add remotion-dev/skills`
  - HyperFrames through `claude plugin marketplace add heygen-com/hyperframes`, only if question D picks it.

## 13. Open questions (A, B and C settled by slices S1 and S2; D, E and F open)

Evidence was gathered on 2026-10-05 from official repositories and docs (sources at the end).

### A. Browser driving: Python Playwright over CDP, or the Playwright CLI?

- **Known:** `playwright-cli attach --cdp=http://127.0.0.1:9333` attaches to an already-running browser by URL (also
  `--cdp=msedge` by channel, or through the Playwright Extension). `detach` leaves the browser running. Its snapshot
  merges iframe content with frame-prefixed refs. `install --skills` puts a skill into `.claude/skills/playwright-cli`.
  Python CDP (`cs.py`) is proven on this exact Edge profile and panel.
- **Unknown:** whether the CLI reaches into **cross-origin nested** webview iframes (its tests use `data:` iframes).
  Also whether `run-code` exposes bounding boxes and timing precise enough for the run log.
- **Settled: Python CDP** (S1 passed). The CLI is an optional check (PLAN, A*) any time after slice S1. If it
  reaches into the webview, it becomes Claude's tool for exploring off camera in generated segments, where its
  snapshot format suits an agent. The recorder stays in Python.

### B. Capture: OBS, a page-level screencast, or Playwright's own video?

- **OBS through obs-websocket v5:** it captures the screen, so every tab is included. Recording is started and
  stopped from the script. Events carry no timestamps, so sync uses the visual markers (§5.3). On this hardware it is
  limited to 1080p capture; zooms above 1x are slightly soft (accepted up to 2x, R42).
- **Page screencast** (the CLI's `video-start`, or `page.screencast` in Playwright 1.59 and later): it captures one
  tab, so the dashboard tab and the IDE tab are stitched together at `tab_switch` events. It can render at DPR 2 above
  monitor resolution. Use it only with its cursor and action overlays turned off, because the cursor is drawn in the
  edit (§7.1). **Unknown:** whether it works on an attached (CDP) session.
  - **This conflicts with the 1920×1080 frame from §1.2 item 6.** A screencast contains only the page. It has no tabs
    and no address bar, so it can't produce the "video and capture frame including the browser's tabs" that David
    chose. It qualifies only if David accepts page-only footage, or as a source for sharp zoomed shots under an OBS
    base layer. That tilts B toward OBS.
- **`recordVideo` (context video):** options are set when a context is created, so it can't apply to the existing
  signed-in context. In the stable release it is VP8 at a hard-coded 1 Mbit/s and 25 fps, which looks poor at 1080p.
  Main has VP9, scaled bitrate and an fps option, not yet released. **Expected to be ruled out.**
- **Settled: OBS** (S1 passed: sync drift, geometry, the new tab), because only OBS keeps tabs and the address bar in
  the frame. A page screencast is tested only if the phone check shows 2x zooms aren't legible enough. Then it would supply sharp zoom shots under the OBS base. Supersampling can't share an OBS
  take, because emulating DPR 2 changes the visible window.

### C. playwright-recast, or our own cursor, click, zoom and cut layers?

- **Known:** it turns Playwright traces into demo videos. Its input is a `trace.zip` (needed) plus a WebM (recommended)
  and it needs ffmpeg on PATH. Features: idle and network speed-up, cursor overlay, click ripples, manual, automatic or
  AI-chosen zoom, SRT/VTT subtitles, voiceover (ElevenLabs among others), and popups and new tabs merged into one
  video. Output is MP4 at up to 4K, 60 fps. MIT licence, 65 stars, v0.23.0 (2026-10-04): pre-1.0 and changing fast.
- **Unknown:** whether a trace recorded on an **attached** context (with `context.tracing.start`, outside Playwright
  Test) is accepted. Also whether its zoom and cut rules can be set to §6 and §7 and fed our narration timing.
- **Settled: our own Remotion layers** (S2 accepted, 2026-10-06). recast is dropped.

### D. Assembly: Remotion or HyperFrames?

- **Remotion:** already in use in this workspace (`QuickSeries/kb-overlay`: centralised timing constants, ProRes 4444
  alpha). Official skills are in `remotion-dev/skills`.
- **HyperFrames (HeyGen):** HTML, CSS and GSAP rendered to MP4 by seeking each frame in headless Chrome and encoding
  with FFmpeg. Apache-2.0, very active (v0.8.134 on 2026-10-05), with official skills through the Claude Code plugin
  marketplace. **Unknown:** whether it outputs alpha (WebM or ProRes 4444).
- **Recommendation:** Remotion for tutorial assembly, which is data-driven from `edit_plan.json`. HyperFrames is a
  candidate for intros, outros and chapter transitions, in separate folders.
- **Decided by:** the Phase 4 bake-off: the same 6 s branded intro built in each, one hour each.

### E. Narration: ElevenLabs clone, live voice, or a mix?

- The narration stage takes either source for each line (`source: clone | live`), so this choice doesn't block the
  architecture.
- **Known:** pronunciation dictionaries (alias rules work on every model; phoneme-rule support depends on the model,
  and ElevenLabs' own docs disagree, so verify it on the chosen model). Character timestamps come from
  `with-timestamps`. Request stitching is not available on `eleven_v3`.
- **Risk (from David's research):** people who know the real speaker, such as his students, reject a clone that sounds
  slightly off.
- **Decided by:** a Phase 1 stretch test, once the clone replaces Andrew. Three lines are recorded both live and by the clone, and David plus one
  person who knows his voice listen blind. Possible outcomes: clone everywhere; live for intros and outros; or live
  everywhere, with the clone used only for drafts and timing.

### F. HeyGen v3: supplied audio and a transparent avatar?

- **Known:**
  - `POST /v3/videos` accepts exactly one of `script` with `voice_id`, `audio_url`, or `audio_asset_id`.
  - `output_format: "webm"` returns WebM with a real alpha channel for avatars trained with matting (the default for
    recently created avatars). It is not available for `cinematic_avatar`.
  - The engines listed are `avatar_iii`, `avatar_iv` (default) and `avatar_v`. This differs from the workspace's April
    note, which said v3 lacked Avatar III, so recheck it.
  - v1 and v2 sunset on 2026-10-31.
- **Unknown:** whether WebM with alpha works together with supplied audio. The old v1 WebM endpoint did not accept
  uploaded audio. Also whether David's two Digital Twins (created before April 2026) were trained with matting.
- **Decided by:** one 10 s API test with an ElevenLabs line uploaded as an asset and `output_format: "webm"`, then a
  check of the alpha channel. It is independent of Phase 0, and the avatar is skipped in testing. Running it before
  October 31 keeps the v2 API as a fallback if v3 fails.

### Sources

- Playwright CLI: <https://github.com/microsoft/playwright-cli>, <https://playwright.dev/agent-cli/commands/attach>,
  <https://playwright.dev/agent-cli/commands/video-recording>, <https://playwright.dev/agent-cli/skills>
- Playwright video and screencast: <https://playwright.dev/docs/videos>, <https://playwright.dev/docs/api/class-screencast>,
  <https://github.com/microsoft/playwright/issues/31424>
- Locator bounding box: <https://playwright.dev/python/docs/api/class-locator>
- playwright-recast: <https://github.com/ThePatriczek/playwright-recast>
- HeyGen: <https://developers.heygen.com/reference/create-video>,
  <https://developers.heygen.com/transparent-background-videos>, <https://developers.heygen.com/endpoint-version-comparison>
- HyperFrames: <https://github.com/heygen-com/hyperframes>
- ElevenLabs: <https://github.com/elevenlabs/skills>,
  <https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/pronunciation-dictionaries>,
  <https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps>,
  <https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/request-stitching>
- Remotion skills: <https://github.com/remotion-dev/skills>
- obs-websocket: <https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md>
- YouTube upload restriction: <https://developers.google.com/youtube/v3/docs/videos/insert>
