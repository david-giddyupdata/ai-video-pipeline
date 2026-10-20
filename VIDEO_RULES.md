# Video rules: one rulebook for every video

The standing rules for GiddyUp Data's narrated screen-recording tutorials, in two layers (R201):

- **Part 1, the rules:** what the viewer must get. They hold for any course and any software, recorded so that the
  pointer, zoom, marks and captions are added in the edit (X5), and name no tool, app or person. Their numbers are
  the viewer's (7:1 contrast, 56 px text, 2 s of silence).
- **Part 2, the house defaults:** how this house meets each rule today: the style numbers, colours, fonts and
  effects, the tools, the setting that holds each value, who reviews, and the checks. A course made with other tools
  keeps Part 1 and replaces Part 2.

Every builder brief, every visual review and every check before an export reads this file (R188). Each rule gives
the decisions behind it (R numbers in AIDrivenVideo's `RULES.md`, where the editor's words and the moment that
prompted each one are recorded) and how it is checked:

- **auto**: a program measures it (the checks are listed in Part 2);
- **review**: the independent reviewer's look at the round's stills before the editor sees it (V2);
- **editor**: the reviewing editor's own review.

A new preference from the reviewing editor becomes an R number in `RULES.md` and a line here: the rule in Part 1, its
number or tool in Part 2. "The house default" in a rule means Part 2's row with the same id. Pixel sizes are for a
1920x1080 frame; scale them for other output sizes.

# Part 1: the rules

## 1. Sound

- **S1 Loudness.** The finished mix sits near -14 LUFS integrated, true peak at most -1 dBTP. One shared gain raises
  the voice and every sound effect together, so their approved balance holds, and loudness is set once, never again
  at export. *R177. auto.*
- **S2 Clicks and pops are removed from every narration clip before the edit,** without damaging the speech. *R103.
  auto.*
- **S3 No double breaths.** Two inhales within about 1.5 s with no speech between lose the earlier one (muted, the
  words untouched). Single breaths stay. *R181. auto.*
- **S4 No dead air.** Lines follow each other with a short gap (house default); a gap runs longer, up to 2 s at most,
  only while something worth watching happens on screen. 2 s is a ceiling: over sped-up typing too, and over a card
  or a time-lapse (T2), which carries narration or the sound of the work. A part boundary pauses a little longer
  (house default). Close a gap with a clause in the narration, not silence. *R25, R82. auto.*
- **S5 A beat where the narration changes mode.** Where a line switches between explaining and instructing, the voice
  pauses a little longer than its own sentence pause (house default) and the picture holds; the beat falls in the
  silence after a word, never inside a breath. *R62, R181. auto.*
- **S6 A spoken pause before an on-screen label,** so the viewer hears that it names one; the caption keeps the
  normal text. *R26. auto.*
- **S7 No sentence runs on into the next.** Every sentence end gets the narrator's natural pause; a short final word
  or an unusual name never makes two sentences run together. *R31. auto.*
- **S8 A quiet click sound on each demonstrated mouse click** (house level), none on drawing a mark or releasing it.
  *R137, R168. auto.*
- **S9 Every overlay has its sound cue,** matched to what happens (a pop, a flip, a whoosh under a chapter card); a
  list ticks once per item as it appears. *R158. review.*
- **S10 Music under the logo outro plays at about the voice before it, in stereo,** true peak at most -1 dBTP, measured
  in the mix the editing program itself plays, not on the files. *R204. auto.*

## 2. Words (the narration)

- **W1 The demonstrator's voice.** First person for what the narrator does ("I'll click"), "we" and "let's" for the
  plan, "you" for what the viewer sees or does on their own; complete plain sentences, short (house default), written
  for the ear. *R29, R66. review; editor.*
- **W2 Announce, act, confirm.** A click line says where (relative to something already seen), what (the exact
  on-screen label) and, the first time, why. The order: any words the click depends on are heard and any text it
  depends on is read; then the label's name; then the click, a short beat after the name starts (house default);
  then a short clause confirms the result as it appears. *R23, R24, R28, R128, R172. auto.*
- **W3 Only what the viewer can see, and readable at that moment.** Nothing narrated from a log alone; nothing already
  gone ("I could answer each question" after the form closed); text behind a cut-off tab or scrolled out of a box
  isn't on screen. *R75, R78, R81. auto; review.*
- **W4 A result that can differ from run to run is one possibility.** When the video shows software whose output
  isn't fixed (an AI assistant, a live data feed, a sampled query), its output is framed as this run's ("In this
  case, ..."). *R76. review.*
- **W5 The public, standalone viewer.** No talk tied to a live class ("your instructor", "class key"). *R12. review.*
- **W6 The episode frame:** promise, why it matters, roadmap, the switch from talk to doing ("So, let's get
  started."), the walk-through, "Let's recap." mirroring the roadmap, then the call to action (house wording and
  footage, X7), left out of a video the reviewing editor doesn't want it in. *R30, R68, R203. editor.*
- **W7 Attention grabbers at a steady rate** (house default), each tied to what is being said, none leaning on a
  cultural reference; humour is one kind, carried by an overlay or a short motion graphic. *R129, R138. review;
  editor.*
- **W8 No em dashes** (nor a spaced en dash or double hyphen standing in for one) in anything the viewer reads or
  hears. Interface text quoted exactly as the screen shows it is the one exception (W2). *R93. auto.*
- **W9 What the viewer reads and what the voice is given are kept apart:** captions and scripts use normal spelling;
  respellings and pause marks given to the voice never reach the captions. *R31. auto.*

## 3. Captions

- **C1 Burned in and high visibility:** plain text on an opaque box, at least 7:1 (G6), at the house size, and
  editable in the editing project until export. The look (font, size, colours, padding, corners) is the house
  default. Captions follow this rule alone, not the graphics' type rules (G3, G11). *R52, R102,
  R126, R192. auto.*
- **C2 A caption never covers what its line is about,** for the whole line: what it names, marks, is about to click,
  or what changes on screen. *R53, R157, R182. auto.*
- **C3 Bottom centre unless something that stays there is in the way;** the pointer passing through for a moment
  (house default) doesn't move it, unless that passage is the action the line is about. Off centre a caption moves to
  another of the house's fixed spots and wraps narrower (house default). *R53, R59, R133. auto.*
- **C4 A caption keeps the side of the one before it** unless its place there would cover what matters. *R174.
  auto; review.*
- **C5 A caption appears as its first word is spoken;** cues never overlap. Its line length is a guideline, not a
  limit (house default). *R54, R59, R85. auto.*
- **C6 Captions sit above every overlay.** *R155. review.*
- **C7 A caption never covers the avatar** (the presenter on screen) **or its box:** it keeps clear of the
  picture-in-picture oval (X6) and of the avatar beside a card (X7); while the avatar is full frame, captions stay
  bottom centre over the shirt; while it is beside a card, they sit on the card's side. (An exception through
  the call to action waits on the reviewing editor: RULES.md, Open questions.) *R213, R231, R232. auto (the stage's
  and the box placement's checks); review.*

## 4. Pointing things out

- **P1 What a line tells the viewer to find, look at or click is pointed out** within that sentence: a mark, a
  highlight or an overlay. Panes and options count. Four kinds of on-screen name need no mark of their own: a
  landmark that only helps find something else ("next to monthlysummary, I'll click the pencil icon"), text while it
  is being typed, a result or value read out as it appears ("East is the busiest"), and the page or tab a click lands
  on. Nothing is marked a second time. One mark covers things named together; otherwise each gets its mark in turn
  (P5). *R75, R124, R171, R186, R199. auto; review.*
- **P2 A region gets the highlighter, a control a rectangle or an arrow.** The highlighter dims everything but a large
  region (a pane, both sides of a dialog); next to an overlay graphic use a rectangle instead, since the dim would
  darken the graphic. *R142, R159, R184. review.*
- **P3 Rectangle or arrow, by what reads best:** an arrow for a small target (an icon, a radio button, a caret, or a
  card with its own outline), a rectangle for a labelled control, a row, a card or a pane. *R121. auto.*
- **P4 A mark frames the whole thing it names** (the whole tab, button or row, with a small margin), never just the
  words inside it. *R84. auto.*
- **P5 The look:** one accent colour, no fill, and one mark at a time: when a sentence names things that can't share
  one mark, the earlier mark releases at the next name. Two kinds. Drawn marks look drawn by hand with a pen as they
  appear: slightly rounded corners, an open chevron arrowhead. Overview marks are square-cornered rectangles and a
  solid arrow that fade in and out. The pointer, click ring and drawn marks grow with the zoom. Colours, strokes and
  sizes are house defaults. *R46, R48, R51, R171. auto.*
- **P6 A click target's mark** is drawn during the lead-in and finished at the target's name; the click follows in
  W2's order; the mark holds long enough to be seen (house minimum). *R49, R128, R172. auto.*
- **P7 Any other mark holds until its area has been discussed:** by default the end of the sentence that names it,
  never shorter than the house minimum, unless P5 releases it for the next name. *R50. auto.*
- **P8 An overview arrow comes to rest only on what the narration names;** travelling on, it keeps moving until it
  has faded. *R63. auto.*
- **P9 Text the viewer must read is shown whole:** where the screen cuts it off (a long entry in a scrolling box, a
  reply in a narrow panel), an overlay shows it and the highlights go on the overlay. *R77. review.*
- **P10 The pointer is hidden while nobody drives the screen** (software working on its own: an AI's live work, a
  build, a long query), except for approvals, which show as normal clicks. *R47. auto.*

## 5. Timing and cuts

- **T1 Short waits are cut or sped up, never shown.** A wait under the long-wait threshold (house default) that would
  leave more than S4's ceiling before the next line is cut (the default) or sped up. Playback is otherwise 1.0x, and
  sped-up footage carries no speed label. Longer waits follow T2. *R35, R37. auto.*
- **T2 Long waits** (at or over the long-wait threshold) are time-lapsed to a few seconds; very long ones get a short card
  saying what is happening and about how long, then a time-lapse (lengths: house defaults); S4 still holds over them.
  Kept at 1x even inside a wait: a prompt that asks for a decision (a permission prompt) and chosen error-then-fix
  moments. *R39. auto.*
- **T3 Hard cuts inside a section;** a dissolve only at a section boundary (house length). The one exception inside a
  section: a cut that skips software's working time (house threshold) gets the house time-skip transition, so the
  viewer knows time has passed. *R34, R83, R90, R105. auto.*
- **T4 A cut never interrupts the narration's audio;** picture cuts may fall under a line that keeps playing. *R38.
  auto.*
- **T5 Freeze-holds are normal;** only a long one is flagged. *R36. auto.*
- **T6 An overlay item lands on its word, never before,** and says what its sentence says, at that sentence's level;
  it appears on the first word of what it sums up. T7's wait is the one exception. *R80. auto; review.*
- **T7 An overlay's last part stays up long enough to read:** at least 2 s, plus about 0.3 s a word past five
  words, before its exit. If that runs into the next overlay, the next waits up to 1 s past its word; anything
  longer flags both. *R185. auto.*
- **T8 Nothing arrives while a click ring or a mark is being drawn.** *R51, R166. auto.*

## 6. Picture

- **X1 A recording flaw that gets in the viewer's way is corrected in the edit,** not retaken: a correction layer
  shows the same place from a clean frame. A flaw in nobody's way stays. Retakes are a last resort, only when the
  recorded action itself is wrong or missing. *R20, R173. review; editor.*
- **X2 Typed text that flickers is shown whole:** where an autofill preview or anything else makes it blink, the
  typing is dropped and the text appears complete. Typing stays the default where it shows clean. *R173, R183.
  auto.*
- **X3 Private details are blurred:** account names for the whole video, other findings as the reviewing editor
  decides. Each blur is its own layer in the editing project, never baked into the recording. *R56, R116, R127. auto; editor.*
- **X4 A clean screen.** Only the take's own windows and tabs show, with toolbar extras, sidebars, notifications and
  prompts hidden; no personal account signed in; one pointer, never a stray second one. *R7, R14, R15, R16, R113.
  auto.*
- **X5 Pointer, zoom, marks and captions are added in the edit,** never baked into the recording. *R17. auto.*
- **X6 The presenter's box never covers what matters and never slides.** In picture-in-picture the avatar sits in a
  soft oval in a clear corner, kept a little in from the frame's edges so none of it is cut off (size and inset: house
  default); it moves only by fading out and fading in at another spot, and fades out to voice only while no spot is
  clear. *R220, R222, R224, R231. auto (the placement's own check); review.*
- **X7 The presenter's stage at the start and the end.** Full frame over a still background; while a card is up (the
  roadmap, the recap) the avatar moves aside and scales down beside the card (house layout), and the card stays as it
  is and is never covered. The avatar's last line at the start is the main body's first sentence. Where the avatar goes on
  through the main body, it gets there by one zoom down from the stage into the box (X6), with no dissolve and no gap,
  and the end mirrors it: the box grows back into the stage. The call to action shows the house's own subscribe
  animation and web address, placed as the house places them (house default). *R205, R208, R220, R231, R232. auto
  (C7's check); review.*

## 7. Camera

- **K1 One resting zoom, chosen so the interface text is comfortable to read** (house default, per app); zoom changes
  are rare and have a reason; pan rather than zoom. Zoom in further for a tight spot, or for small text the viewer
  must read or watch being typed (house maximum). Zoom further out, to full frame if needed, when what the line is
  about stays clearly readable there. *R42, R125, R156, R197. auto; review.*
- **K2 Full frame while a navigation's address or new page matters,** then zoom in at once on the coming work; zoom
  out on the cut at a click that opens a new tab or window. *R40, R41, R44. auto.*
- **K3 What the narration refers to sits inside title-safe, whole:** 5% of the frame in from the sides and the top,
  and clear of the caption band at the bottom (house default). A dialog the lines treat as a whole is framed at its
  own size, or panned to the part being talked about. *R123, R125. auto.*
- **K4 Text being read is lifted clear of the frame's edge** (zoom in and pan up). *R172. auto; review.*
- **K5 When an action changes something, the viewer sees everything it changes** (a guideline: a minor change in a
  corner may stay off screen). *R157. review.*
- **K6 Camera moves are linear;** a drawn pointer keeps its eased motion. *R45. auto.*
- **K7 Text a line names is at least 14 px tall in the frame** (OCR's text box); 12 px where more zoom would push out
  something that must stay in view, or at the camera's resting zoom (K1); under 12 px it isn't on screen (W3). *R81,
  R198, R202. auto.*

## 8. Graphics (overlays)

Does it earn its place?

- **G1 It says something the screen doesn't already say clearly;** no overlay over a highlight of the interface's
  own labels. *R165. review.*
- **G2 A picture before words.** If a graphic can say it without text, it does; a text chip is fine where no picture
  can. *R165, R168. review.*

Size (a phone held sideways):

- **G3 Body and label text at least 56 px, headings 60, data (monospace) text at least 52, nothing under 48 px;**
  icons at least 64 px; a labelled diagram or chart at least 480 px wide or 360 px tall; strokes at least 4 px.
  Bigger reads better, within the frame's room. Captions are C1's, not this rule's. *R161, R166. auto.*
- **G4 Keep proportions;** a chart or picture squeezed to fit looks stretched. *R166. review.*
- **G5 Text stays inside its panel;** no letter hangs off the background. *R166. review.*

Contrast and background:

- **G6 All text at least 7:1 against what is right behind it** (WCAG's enhanced level), measured. *R79, R179.
  auto.*
  Exempt: the house's own logo, its web-address write-on and the subscribe animation's "Thanks for Watching!", which
  keep their own colours (house default; R232, R235).
- **G7 An overlay that informs sits on an opaque panel.** Nothing see-through behind text, numbers, a diagram or any
  element inside it (at 96% the screen showed through and muted text fell under 7:1); see-through is for cut-out
  props and drop-ins only. *R164, R179, R194. auto; review.*
- **G8 A panel contrasts with what it sits on:** dark on a light screen, light on a dark one. *R140. auto.*

Colour and type:

- **G9 The palette passes 7:1;** the accent colour (P5's) is for shapes only (marks, ticks, pins,
  outlines, the chosen option's rectangle), never text. *R51, R180. auto.*
- **G10 Different kinds of text get different colours,** such as a setting's name against its value. *R166. review.*
- **G11 Fonts by role:** one sans-serif for headings and body, a handwritten face for a word list, a monospace for
  data; a stand-in of the same role where one is missing. Exception: the series card keeps its Quick Series face
  (Berlin Sans FB Demi), as the original card does (R243). *R143, R148, R243. auto.*
- **G12 Mixed fonts on one line share their capital height and one baseline,** each sized to match, not by point
  size; in a two-column overlay each label sits on its value's line; rows' capital tops and baselines, and columns'
  left edges, within 2 px. Labels placed on a map or picture aren't a row. *R176, R187, R195. auto.*

Placement:

- **G13 Never cover what the line is about** (the chart being described, the field being set), the click targets,
  the marks or the captions. *R152, R155, R166. auto; review.*
- **G14 Close to what the viewer looks at;** a graphic in or beside the dialog keeps attention on the dialog; one
  that mirrors the screen's own layout reads at once. *R166, R169. review.*
- **G15 Inside title-safe and clear of every caption's own box,** wherever the caption sits (C3). *R123, R155. auto;
  review.*
- **G21 An overlay that shows what the screen shows keeps the screen's order and layout:** options in the order the
  screen lists them, a value where the screen puts it (beside or under its setting). *R166, R196. review.*

Motion:

- **G16 Motion carries meaning:** in a group every item moves or none. *R166. review.*
- **G17 A panel that will grow opens at its full size at once;** the empty space tells the viewer more is coming.
  *R169. review.*
- **G18 A drawn arrow helps the eye track** to the point that matters. *R166. review.*
- **G19 One calm curve, no overshoot or bounce,** except the asides' pop. *R131. review.*
- **G20 Full-screen chapter markers at a video's section transitions.** *R141. review.*

## 9. Before the reviewing editor sees a round

- **V1 The producer runs every automatic check in Part 2 and fixes what it finds** before export. *R85, R200.*
- **V2 An independent reviewer** (not the one who made the round) **reviews stills at every line, mark, caption and
  overlay against this file;** each finding is checked in the editor's own frames before it is acted on. *R190,
  R200.*
- **V3 Anything for the reviewing editor is a timecode on the full sequence they open, with a marker there,** never
  an internal id. *R106.*
- **V4 The editing project is the edit surface:** everything arrives as something the reviewing editor can change on
  the spot. *R61, R102.*
- **V5 Once per video, an outside reviewer reads the frames blind,** on the video's first full round (the edit with
  its overlays); each finding is checked against the frames. It costs money, so the editor is reminded and asked
  before it runs. *R191, R193, R200.*
- **V6 Each of the editor's notes becomes a numbered decision before any work on it,** and a new check must first find
  the note it was built from. *R170, R200.*

# Part 2: the house defaults (GiddyUp Data, 2026)

The values below are this house's way of meeting Part 1. Section A of Quick Sight Journey 1 is the reference
exercise: its settings are `AIDrivenVideo/exercises/qs1_section_a/edit_settings.json` and `voice.json` (another
exercise's files may differ, and say so). The look's values are in `motion-styles/giddyup.tokens.json`, described in
`motion-styles/STYLE.md`. (Public copy: those files are not published; the shipped equivalents are
`exercises/build_an_interactive_dashboard/edit_settings.json` and `voice.json`, and
`remotion/src/overlays/tokens.json`.)

## Who and what

| Role | This house | R |
|---|---|---|
| The reviewing editor | David, in Premiere Pro 26.3 (release build, never beta) | R61, R73, R107 |
| The producer (runs the takes, plan, checks and builds) | Claude Code, driving Premiere through the AIDV panel's bridge; it never closes a project it didn't open | R60, R104 |
| The independent reviewer (V2) | a fresh Claude subagent, no outside call | R190 |
| The outside frame review (V5) | Gemini 4 Argon through OpenRouter, 2.5 frames a second at 768 px, blind; about $5.40 for a 16-minute video. Claude reminds David and asks first. (Gemini 3.1 Pro on the video at its default sampling found none of David's notes: not used.) | R191, R193, R200 |
| Code review | a Fable subagent reviews every code change before the work is called done | R108 |
| Overlays | ideas from several models through OpenRouter, built by a swarm, picked by David in a Premiere review project; every asset and paid run in `motion-library/CATALOG.md` | R139, R149, R153, R154, R163 |
| Rulebook review | GPT-6 Astra and Gemini 4 Argon, blind, once (round 8, `research/rules_review/round8/`) | R189 |
| Narration | David's ElevenLabs clone (`voice.json`); Microsoft's Andrew through edge-tts for Phase 0 work | R22, R94 |
| The presenter (avatar) | David's HeyGen look "David Baldwin" (`<HEYGEN_LOOK_ID>`); the intro and outro rendered transparent on Avatar III through the API (open: David's remark on Avatar III, RULES.md's open questions); the main body's picture-in-picture tested on a still in Premiere first, then rendered on Avatar IV in the HeyGen web app (Pro plan) once David agrees the look | R219, R220, R226, R229 |
| The recorder | Playwright over CDP driving a dedicated Edge window on a monitor with no taskbar, OBS Display Capture, silent, everything drawn in the edit (Remotion `EditPass`, exported as Premiere layers) | R13, R14, R17, R18, R113 |

## Defaults by rule

| Rule | Default | Where it is set | R |
|---|---|---|---|
| S1 | the gain applied in the pipeline's audio (a light compressor, then a limiter); Premiere's mixer at 0 dB; no loudness normalization at export | `loudness.target_lufs` (-14), `loudness.limit_dbfs`; `pipeline.edit.loudness` | R177 |
| S2 | a click is a spike above 4 kHz, 31 dB over its neighbourhood; repaired by ffmpeg `adeclick` within 2 ms of it; a click left after the pass is a warning | `pipeline.narration.clean` (`CLICK_DB`) | R103 |
| S3 | an inhale: between words, out of near-silence, 17 to 42 dB under the clip's speech, centred near 2 kHz | `pipeline/narration/breaths.py` | R181 |
| S4 | 0.4 s between lines; 0.8 s more at a part boundary (about 1.2 s). The recordings are silent, so a card or time-lapse is filled with narration: a line written to play during it (a line-only step with `during`) | `pacing.gap_between_lines`, `pause_at_part_boundary`, `max_silence_s` | R25, R82 |
| S5 | 0.5 s longer than the sentence pause | `pacing.mode_switch_beat_s` | R62 |
| S6 | the voice's own pause mark: `label_pause` " - " in Section A's `voice.json` (0.43 s measured on Andrew); the labels listed per line | `voice.json` `label_pause`; a step's `narration.labels` | R26 |
| S7 | an ellipsis in the spoken text before a full stop that follows a short word or a respelled name | `pronunciation.json`; `pipeline.narration.build` | R31 |
| S8 | about -24 dBFS peak before S1's gain; one short click made in code, on each click the edit draws a ring for | `click_sound.peak_dbfs`; `pipeline.edit.click_sound` | R137, R168 |
| S10 | within 1 dB of the outro voice's LUFS in Premiere's mix; the music raised through the voice's limiter; its two channels on two tracks panned to their sides; the channel difference within 1 dB of the file's | `pipeline.edit.ppro.final` (`logo_at`, `mix_check`); `pipeline.edit.premiere.audio_pan` | R204 |
| W1 | about 12 words a sentence, none over about 25 | `research/style_study/NARRATION.md` §7 to §9 (no program setting) | R29 |
| W2 | the click 0.35 s after the label's name starts | `pacing.click_after_name_s` | R23, R128 |
| W6 | "If you enjoyed this video, please subscribe and give it a thumbs up. And if your team could use training like this, consider bringing me in, in person or virtually. Visit GiddyUpData.com to see the courses I teach and the services I offer." | `research/style_study/NARRATION.md` §1 | R30 |
| W7 | two or three a minute | the overlay plan | R138 |
| W9 | display text and spoken text per line; respellings | the step lists; `pronunciation.json` | R31 |
| C1 | Lucida Console 48 px, plain white, on #575757 (7.23:1), 15 px padding, 10 px corners; one editable Premiere title per cue | `captions.titles`, `captions.stills`; `pipeline.edit.ppro.titles` | R52, R102, R126, R192 |
| C3 | Premiere's 3x3 grid of positions; off centre about 30 characters a line, up to three lines; the pointer must stay 0.6 s to move a caption | `captions.off_centre_max_chars`, `off_centre_max_lines`, `cursor_stay_s` | R53, R59, R133 |
| C5 | about two lines of 42 characters | `captions.max_lines`, `max_chars` | R59 |
| C7 | 12 px kept between a caption and the avatar's reach, the oval and the card; none up while the avatar moves (the stage's build). Round 6 puts the call to action's captions middle left (left edge at x 88, at most 22 characters a line), pending David | `pipeline.edit.stage` (`CLEAR_PX`, `check_c7_quick`); the steps file's stage `quick` (`cta_caption_x`, `cta_caption_chars`); `pipeline.edit.pip` `CLEAR_PX` | R213 |
| P2 | the highlighter is a spotlight dim (everything else to about 0.58 brightness) | `marks.highlight`; a step's highlights | R122, R142 |
| P3 | an arrow for a target whose longer side is at most 32 px | `marks.kind_auto.arrow_max_px` | R121 |
| P5 | orange #F16F05. Drawn marks in Epic Pen's look: about 5 px stroke, slightly rounded corners, an open chevron arrowhead. Overview marks in David's Premiere roadmap look: 8 px square-cornered rectangles and his `Arrow01` (filled head, #E86F3B). Cursor 36 px, click ring 65 px, sized at the 1.35x rest. | `marks.*`, `cursor.*`; `remotion/src/constants.ts` | R46, R48, R51 |
| P6, P7 | a click target's mark at least 0.6 s; any other at least 1.8 s on screen (the 0.8 s draw plus a 1.0 s hold) | `marks.click_hold_min_s`; `marks.draw_s` + `marks.hold_s` | R50, R128 |
| T1 | cut by default, above 3 s; the long-wait threshold 20 s | `cuts.gap_treatment`, `cuts.cut_above_s`; `timelapse.realtime_max_s` | R35, R37, R39 |
| T2 | 20 s to 3 min: time-lapsed to 6 to 8 s; over 3 min: a 3 s card saying what the software is doing and for about how long (the setting reads "Claude is working: about {minutes} minutes") then 6 to 10 s of time-lapse | `timelapse` (`card_text`) | R39 |
| T3 | the section dissolve 1.0 s (0.8 s into the recap; into the avatar's outro, round 6 has the oval's fade and growth instead, pending David); the time-skip transition is Premiere 26's new Page Peel, 1.0 s, for cuts that skip 1 s or more of an AI's working time, placed in Premiere by the pipeline | `cuts.section_transition`, `cuts.work_cut_transition` | R34, R83, R90, R105 |
| X3 | the account name blurred for the whole video, by pattern; other findings decided by David | `privacy.patterns`; `privacy_decisions.json` | R56, R116, R127 |
| X4 | Edge with Copilot, Favorites, split screen, extensions, the profile dot, the favourites bar, sidebar, translation offers and password prompts hidden; autofill off; a profile never signed in to Microsoft; the real pointer parked off the capture monitor; other windows moved off it during a take | `pipeline.preflight`, `pipeline.capture.browser`, `pipeline.capture.screen` | R7, R15, R16, R89, R113 |
| X6 | David's Quick Series ep04 oval: the whole frame at 35% through a 288 x 375 px ellipse, 3.5 px feather, no ring, the cityscape inside; its edge 54 px in from the frame's edges at every corner (round 6, pending David; title-safe's 96 px at the sides is the offered alternative); 0.3 s fades; a stay at least 4 s and a voice-only stretch at least 2 s (proposed); 12 px kept from what matters; what a line is about that no measure sees comes from a list made by hand from the review (round 6, pending David) | `pipeline.edit.pip` (`SCALE`, `OVAL_W`, `OVAL_H`, `FEATHER_PX`, `EDGE_PX`, `FADE_S`, `MIN_STAY_S`, `MIN_HIDDEN_S`, `CLEAR_PX`); `exercises/<ex>/pip_keep_clear.json`; `pip_spans.json` | R222, R224, R231, R232 |
| X7 | the Quick Series cityscape (`Global Assets/OfficeZoom_0002.jpg`, the picture the HeyGen looks were recorded on), held still; beside a card the avatar takes about the left third and the card the right two thirds ("something like 1/3 avatar 2/3 overlay"), with captions under the card; the avatar at 75% of full size in the left third (David's pick from R235's stills), its reach 48 px short of the card; the zoom-down into the oval 0.6 s, linear. The series card "Amazon Quick Series" / "QS Journey 1: First dashboard" in QuickArch03's look, rebuilt in Remotion (`SeriesCard.tsx`, 821 x 230 at (1004, 640), in at 0.50 s for 5.78 s, a whoosh). The call to action: the brand-colour Remotion subscribe animation (`SubscribeCta.tsx`, variant "brand", timed by "subscribe" and "thumbs"; whoosh, bell, click) and `Global Assets/url.mov` (copper, no panel), placed as at 00:07:25:22 and 00:07:34:03 of 03-QuickArch03; shared timing in `remotion/src/overlays/data/cta.json` | the steps file's stage (`design` "quick", `quick.left_scale`, `card_gap_px`, `left_move`); `pipeline.edit.stage`; `AvatarStage.tsx`; `research/backgrounds/refs_ep03/ep03_cta.json` | R205, R208, R231, R232, R235, R242, R243 |
| K1 | rest 1.35x (Quick Sight, the workshop's web apps); up to 2x for tight spots and small typed text; the Claude Code panel at 2x; a denser desktop app may rest lower | `zoom.level`, `zoom.max`; a step's `zoom.max` | R42, R72, R125, R156 |
| K3 | 96 px at the sides, 54 px at the top, 100 px at the bottom (the caption band) | `zoom.safe_px` | R123 |
| K6 | camera keyframes linear (zooms over 0.6 s, pans over 0.5 s); the drawn cursor keeps its eased path | `remotion/src/camera.ts`, `zoom.ramp_s`, `zoom.pan_s` | R45 |
| K7 | readable from 12 px (OCR box); 14 px aimed at away from the 1.35x rest (at it, Quick Sight's 12 to 13 px text is fine); named text under 14 px off the rest is listed in the check's report, not marked | `checks.MIN_READ_PX`, `SMALL_READ_PX`; `zoom.level` | R198, R202 |
| G3 | Courier New for data at least 52 px | the tokens' `type` | R161 |
| G6 | exempt from 7:1: the GiddyUp logo and the giddyupdata.com write-on (`url.mov`), in their own colours | X7's placement | R232 |
| K3, S9 | exempt: `url.mov` as QuickArch03 places it (the tail of its "g" below title-safe, no sound cue, its last 4 frames fading into the hard cut to the logo) | X7's placement | R244 |
| G7 | panels, wells and chapter cards opaque | tokens 1.2.0 | R179, R194 |
| G9 | muted gold #d0b68b on the dark variant, copper headings #7b4622 on the light variant, teal #335964; the accent orange #F16F05 | `giddyup.tokens.json`; STYLE.md's colour table | R51, R180 |
| G11 | Segoe UI for headings and body, Segoe Print for word lists, Courier New for data; Inter, Caveat and JetBrains Mono stand in where those are missing (bundled with their OFL licences) | `remotion/src/overlays/kit.tsx` font stacks; `remotion/src/overlays/fonts/` | R143, R148 |
| G12 | Courier New at about 64 to 66 px beside 56 px Segoe UI | the tokens | R187 |
| G15 | a two-line bottom-centre caption's band starts at y 870 | the overlay lint | R123, R155 |
| G19 | the motion curve | STYLE.md | R131 |

## The checks

| Check | Measures | Rules | Where | State |
|---|---|---|---|---|
| line check | per line: OCR at each named word, full-resolution mark crops, item vs sentence, sentence-end pauses, silences, caption overlaps, framing | S4, S7, W2, W3, C5, P4, T6, K3, K4 | `pipeline.edit.linecheck` | built |
| narration build | em dashes (no exception yet for quoted interface text: such a line is waived by hand), label pauses, sentence-end pauses | S6, S7, W8, W9 | `pipeline.narration.build` | built |
| click and pop pass | clicks above 4 kHz | S2 | `pipeline.narration.clean` | built |
| loudness | integrated LUFS, true peak | S1 | `pipeline.edit.loudness` | built |
| mix check | the final sequence's joins and logo outro exported by Premiere and measured: LUFS, true peak, the logo's stereo | S1, S10 | `pipeline.edit.ppro.final` `mix_check` | built |
| privacy report | OCR'd private text | X3 | `pipeline.privacy.report` | built |
| pre-flight | the capture screen, pointer, browser | X4 | `pipeline.preflight` | built |
| overlay lint and collisions | sizes, title-safe, arrivals during marks, covering; captions only in the bottom-centre band (y 870 down), so a moved caption is the review's | G3, G13, G15, T8 | `tools/overlay_review.py check` | built |
| contrast | ink against surround on rendered stills (OCR text boxes), WCAG ratio; token pairs | C1, G6, G7, G9 | `pipeline.edit.checks` tokens, text_contrast, see_through (in `overlay_review.py check`) | built |
| alignment | per row capital tops and baselines, columns' left edges | G12 | `pipeline.edit.checks` alignment (in `overlay_review.py check`) | built |
| display time | each overlay's last part up long enough; collisions | T7 | `pipeline.edit.checks` display_time, hold_for_reading (`overlay_review.py cards`, `check`) | built |
| captions over targets | every cue's box against every target, mark, highlight and named thing of an overlapping line, through the camera | C2 | `pipeline.edit.checks` captions (in the line check) | built |
| named but not pointed out | the screen's OCR against each line's labels, quoted words and interface terms; R199's four kinds and repeats listed apart; an arrow points with its head; named text under 14 px listed | P1, K7 | `pipeline.edit.checks` named (in the line check) | built |
| typed-field flicker | each typing step's field crop, frame by frame (A-B-A-B fails) | X2 | `pipeline.edit.checks` flicker (in the line check) | built |
| double breaths | inhales in the placed narration, a beat splitting one, pairs within 1.5 s | S3, S5 | `pipeline.edit.checks` breaths, `pipeline.narration.breaths` (in the line check) | built |
| Premiere frame check | Premiere's own frames of the built project | everything visible | `pipeline.edit.ppro.framecheck` | built |
| the box's placement | every frame of each stay and fade against the captions, cards, marks, click targets, named things, the resting pointer and the keep-clear list; stays and hides long enough; the inset | X6, C7 | `pipeline.edit.pip` (`pip_spans.json`) | built |
| the avatar's stage | every third frame of each cue against the avatar's reach, the oval and the card; captions off the call to action's footage; the avatar's reach clear of the card; nothing drawn outside the oval while it is alone | C7, X7 | `pipeline.edit.stage` (`check_c7_quick`, `oval_alone`) | built |
| by construction: the planner | beats, click sounds, click timing, caption placement, mark kinds and holds, the hidden pointer, cuts, time-lapses, transitions, holds, the panel variant | S5, S8, W2, C3, C4, P3, P6, P7, P8, P10, T1 to T5, G8 | `pipeline/edit/plan.py` | built |
| by construction: the camera | resting zoom, full frame at navigation, linear moves | K1, K2, K6 | `pipeline/edit/camera.py`, `remotion/src/camera.ts` | built |
| by construction: the settings and tokens | the captions' look, the marks' look, the fonts | C1, P5, G11 | `edit_settings.json`, `giddyup.tokens.json`, `kit.tsx` font stacks | built |
| by construction: the edit layers | pointer, zoom, marks, captions and blurs drawn in the edit, each its own Premiere layer | X3, X5 | `remotion/src/EditPass.tsx`, `pipeline.edit.premiere`, `pipeline.edit.ppro.project` | built |
| independent visual review | stills at every line, mark, caption and overlay against Part 1 | V2 | a fresh Claude subagent | each round |
| outside frame review | blind findings by timecode | V5 | `tools/video_review.py frames`, `argon` | once per video, on David's OK |
