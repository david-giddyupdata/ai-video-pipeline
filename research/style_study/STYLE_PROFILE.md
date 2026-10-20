# David's editing style, as pipeline rules (Quick Series ep02–ep04)

*Public copy: the sources below are not published; this file is the conclusion.*

Built 2026-10-06 from three sources that were cross-checked against each other:
- **Pixels:** `interface/`, `architecture/`, `knowledge_bases/` `REVIEW.md` (frame timing against word timings).
- **Premiere:** `premiere_reconciled/SUMMARY.md`. Two independent parses of `AmazonQuick.prproj`, with every
  disagreement settled against the XML and the exported frames. Where the pixels and Premiere disagree, Premiere
  wins on *what* was done and the pixels win on *what the viewer sees*.
- **Narration:** `NARRATION.md` (scripts and measured delivery).

This file is the measurement. What David decided from it is in `RULES.md` (cited as R#); the numbers the pipeline
uses are in `edit_settings.json`.

## 1. Timing against the narration (the core of the style)

| Observation | David's numbers | Pipeline |
|---|---|---|
| The pointer starts moving as the clause about the item begins | ep02: live annotation starts −0.07 s (median) from the clause start | R23 (`cue_word`) |
| The mark (box or arrow) is on screen when the item is named | ep02/ep03 boxes: +0.06 to +0.15 s from the noun | R48, R49 (`at_word`) |
| The click lands just after the name | ep02: name +0.36 s (median) | R23 (take 05 measured +0.38 / +0.43) |
| Camera moves start on the transition word ("next", "below", "on the right") | ep03: −0.15 s (median) | R41 (in at once when the full-frame need ends) |
| He does not copy his own flaws | ep02 pointing up to 5 s early; ep04 clicks up to 3.3 s late | R23: warns outside `click_after_name_max_s` |

## 2. Cuts, waits and speed

- **Hard cuts between pieces of a recording.** 118 pieces across ep02 and ep04, all hard cuts. A dissolve appears only
  at a section boundary (ep04: 5 Cross Dissolves or Page Peels, all 1.0 s). Adopted as R34.
- **Waits are cut, never shown.** Page loads never appear. Long explanations get a **freeze-hold** of the screen (ep02
  14 holds, ep04 13, median 3–4 s, max 8.4 s). Freezes are normal in his work. Adopted as R35, R36.
- **Speed:** ep02 plays the recording at 1.0x with short 0.75x/1.25x stretches. ep04 plays at **1.5x** throughout,
  with 2.0–2.6x for typing and 0.73–0.8x on the moment of a result. There is never a speed badge. The 1.5x made up
  for a live hand; the pipeline paces by the edit (R37).
- **Narration over the result:** after a long wait, the line keeps playing over the result (R18).

## 3. Camera (zoom and pan)

- **Linear moves, no easing at all.** All 431 keyframes in ep04 and every one in ep02/ep03 are linear, with straight
  paths. The "eased" look the pixel study saw was a scale and a fade overlapping.
- **Ramps 0.5–0.6 s** (pooled median 0.60, IQR 0.45–0.80; ep02 UI moves median 0.50). Pans and zooms take the same time.
- **Levels on screen recordings: 1.12–1.48x, typically 1.2–1.35.** Diagrams go to 1.5–2.0x.
- **It sits zoomed.** About one move per minute, and holds of about 20 s median (4.4 s minimum, up to minutes).
  ep02 sits at 1.21x for 89% of the video; ep04's demo rests at 1.23x, which crops out the browser chrome.
- **Pan rather than zoom out and back in** when the next item is nearby.
- **Slow push** (100→160% over 47 s) is used only on a still image, never on UI.

## 4. Attention marks

- **On screen recordings he draws them live with the mouse:** an arrow grows from tail to head with the pointer at the
  tip (0.6–1.0 s), or a rectangle is dragged corner to corner (0.7–1.5 s). It holds about 2 s, fades out over about
  0.25 s, then the click follows. Pointing and marking are one gesture.
- **On static material and overview moments** (stills, diagrams, the intro roadmap) they are edit layers.
  Boxes fade in and out over 0.2–0.3 s, linear. The roadmap arrow scales in and then travels between regions
  with rotation. Items in a list cross-fade with about 0.2 s overlap.
- **Style:** orange #F16F05, 5–8 px stroke, square corners, no fill. The stroke stays the same thickness under zoom.
  One mark at a time.
- **Spotlight (diagrams only):** everything outside the target is darkened (Brightness −100); the first fade takes
  1.07 s, and the lit window moves with the camera.

## 5. Captions

- Burned in, **Lucida Console 48 px**, white on a dark box (#5F5F5F, about 63% opaque), square corners.
- At most 42 characters per line (ep04). He lets 3–5-line cues through; the pixel study counts that as a flaw.
- **Placed per cue to avoid the presenter and the UI being discussed** (bottom-centre while the presenter is
  bottom-right, bottom-left while it is centred; moved to the top when the subject is low on screen).

## 6. Presenter (HeyGen; Phase 1 and later)

- Full-screen intro of 13–23 s, then a **linear 0.6 s shrink to 35%**: an ellipse of 288×375 px with a 3.5 px
  feather, centred at (0.9266, 0.8236) bottom-right.
- It moves to another corner when it would cover the content: in ep04 by fading out (0.3 s), jumping and fading in
  (0.3 s); in ep02 by a 0.3 s slide. It is hidden while an overlay needs the space.
- Full-screen outro of 15–32 s. The voice in ep02 and ep04 is the HeyGen render's own audio.

## 7. Episode frame and sound

- Title card (a licensed template) over the intro. Outro: Subscribe 7.5 s, url 5.3 s, a **hard cut to black**, then
  the logo fades in over 0.67 s and plays for 6 s.
- **Music only in the outro** (William Tell, about −7 dB, 2.5 s fade at the end). No music bed under the narration,
  almost no sound effects.
- Narration: see `NARRATION.md`. Promise → why → roadmap → "So, let's get started." → walk-through → "Let's recap."
  → the standard call to action. 120–145 words per minute while talking, median pause 0.35 s.

## 8. David's decisions (2026-10-06)

Moved to `RULES.md`: framing and zoom (R40 to R45), the two kinds of marks with the ep02 roadmap and Epic Pen detail
(R48 to R51), drop-ins with humor (R27, dropped by R65), linear zooms with an eased cursor (R45), and captions (R52, R53). The ep02
roadmap's measured detail: a rectangle fades onto each named region, and Arrow01 (large filled head, #E86F3B) scales in
from 0 in 0.7 s, then travels and rotates to the next region (hops 27.0–27.4 s and 29.1–30.1 s) while the previous
rectangle fades out. Drop-in examples: ep02 0:49 shrugging woman, 4:29 rabbit hole, 9:56 car.

## 9. Lessons about the method

- **Pixel studies alone get the timing right but misread the mechanics.** For example, a 9-frame slide read as a
  one-frame jump, two overlapping linear moves as easing, and the Consolas font. The pixel study also produced one
  false defect (a "garbled label" that was just a box cut off at the frame edge), which was refuted by looking at the
  frames.
- **A project file alone misses what is baked into the recording** (live-drawn marks) and what the viewer actually
  sees (moves hidden under an overlay).
- **Two independent parsers caught each other's bugs:** a speed field read at the wrong XML level, a missed −7 dB
  nest gain, a missed marker. Use both sources, and check every claim before it becomes a rule.
