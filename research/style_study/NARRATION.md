# How David writes narration (from the Quick Series, episodes 02–04)

Sources: `02-QuickInterface01_narration.txt`, `03-QuickArch03_updated.srt`, `04CreateKnowledgeBaseScript.txt`, and the
measured audio (`pacing.json`). Quotes are verbatim. This guide is for drafting pipeline narration (`steps.json`) that
sounds like David, and for checking drafts before he reviews them.

## 1. Shape of an episode

Every episode uses the same frame:

1. **Promise:** "In this video, we'll …" (one sentence on what we'll do).
2. **Why it matters, and the risk of not knowing:** "That's powerful, but it's also easy to feel lost before you know
   where everything lives." / "… easy to lose the plot if you only see the product one screen at a time."
3. **Roadmap in spatial or logical order:** "We'll move through the navigation panel on the left, the home page in the
   center, and the chat panel on the right." / "We'll move from the top down: …"
4. **Concept before mechanics** when there is a concept (ep. 04): use case → definition → best practice → scope note.
5. **"So, let's get started."** marks the switch from talk to doing. All three episodes use it.
6. **The walk-through**, in the order the roadmap promised.
7. **"Let's recap."** The recap mirrors the roadmap's order and wording.
8. **The same call to action, word for word:** "If you enjoyed this video, please subscribe and give it a thumbs up. And
   if your team could use training like this, consider bringing me in, in person or virtually. Visit GiddyUpData.com to
   see the courses I teach and the services I offer."

## 2. Instructions: announce, act, confirm

R66 makes this the voice for pipeline scripts. The narrator is the person doing the exercise, not a coach giving
orders: "I'll paste in the prompt", not "Paste in the prompt". Sentences are complete and plain; clipped ones ("Send
it.") aren't his. Phrases he reaches for: "Notice that …", "Note that … This is a best practice.", "As you can see, …",
"as of this writing", "available via the description", and before the recap, how the example maps to the viewer's own
work ("We're using the Mitchell family to teach the mechanics, but the pattern maps directly to the enterprise.").

- **First person, present or future, before the action:** "I'll select Amazon S3." / "I'll proceed to the next window
  in the wizard by clicking 'Next.'" / "Next I'll scope to a specific folder by selecting 'Add specific content' …"
- **The result is confirmed out loud:** "As you can see, this collapses the chat …" / "Now, if I click on the 'X', you
  can see that the chat panel is entirely removed." / "In the response, I can see that Quick accesses both …"
- **He says what he is *not* doing:** "I'll not click it now but will instead click on the 'Collapse' option." / "I won't
  upload now, but if I did, …" / "I'll keep the default and NOT point to a different AWS account."
- **He directs attention before a repeat:** "Now let's repeat the process. Watch for any differences as we create a
  second knowledge base." / "Notice that this first screen looks different."
- **Labels are quoted UI text:** "Add specific content", "Create", "Open Chat". The step's narration should name the
  button exactly as the screen shows it.

## 3. Locating things: place first, then name, then purpose

- "In the upper-left corner there's an Explore button that toggles the left-hand navigation panel."
- "Next to the account-name dropdown you'll see Help, and next to Help you'll see an 'X'."
- Chains anchor each item to the previous one: "Below Chat Agents is Spaces." / "Below Spaces are Flows." / "Next to
  the paper clip icon is …"

Adopted as R28; the cursor moves on the cue word (R23).

## 4. Definitions

- Pattern: **term → plain definition → when or why you'd use it.** "Spaces are collaborative workspaces for organizing
  knowledge around a team, project, or business domain."
- Ties new terms to ones the audience knows: "QuickSight is a BI tool like Tableau or Microsoft Power BI, but …"
- **He disarms confusing UI head-on:** "The first field in the popup wizard is a bit confusing. 'Name', in this context
  is not the name of the S3 bucket … Nor is it the name of the knowledge base … Instead, it's the name of the
  connection." This is exactly what the "random name" line in p1.03 was missing.
- **Best practice is flagged as such:** "Note that we're scoping each knowledge base to a clear purpose. This is a best
  practice." The reason follows in one sentence.

## 5. Scope management

- Says what is out of scope and moves on: "We are not reviewing Scenarios in this video series." / "We don't cover these
  in this video series."
- Forward references: "In a future video we'll create a custom chat agent …" / "We'll talk about the manifests folder in
  a future video."
- Backward references: "Previously in this video series, we set up an S3 bucket …" / "the main web workspace we
  previously reviewed".
- Dates claims: "as of this writing".

## 6. Dry asides: measured, back in use with overlays

**R129 (David, 2026-10-14) replaces R65:** a little humor comes back, an occasional light aside carried by an overlay
or a short motion graphic, as in the published episodes. How often and where is settled in the overlay plan (R130);
until then, draft no asides. This section is the record of how the episodes did it.


- "Favorites is empty right now — a fittingly humble start."
- "Automations … they're a power-user rabbit hole. We're going to wave at it and keep walking."
- "And Fast is, well... fast."
- "Same brain, different set of hands."
- "Yes, the arrows cross. That is on purpose; the AI pulls from both paths."
- "This bottom layer is easy to ignore in a demo, and expensive to ignore in production."
- "Chat Privacy is for the questions you'd rather Quick didn't remember about you later."

The asides are short, never mocking the viewer, and usually carry a real point (a contrast, a warning). An aside never
stands in for the instruction; it follows it.

The drop-in examples are in ep02, *Interface*
(https://www.youtube.com/watch?v=XAOeZiBmc2A):
- The shrugging woman at 0:49. The gag exits by playing in reverse.
- The rabbit at 4:29, on "power-user rabbit hole". It pops in with a scale-up of about 0.5 s and plays about 4.7 s.
- The car at 9:56 (not yet measured).

## 6a. Dead air

The rule is R25 (at most 2 s without talking). Gaps the edit can't close come from the take itself: a mark held after
the line ends, the click, then a page load. Close them in the narration with a confirming clause after the click
(R24), so the result is narrated while it loads.

## 7. Spoken text is written for the ear

He respells literal values for the voice in the script itself:
- "s3 colon slash slash quicksweet, hyphen, class, hyphen 4 3 2 1"
- "I'll enter 'QS, S3, Connection.'" (commas slow the voice between tokens)
- "financial_documents slash, directory"

This is the pipeline's display text vs spoken text split (SPEC §5.5). His habit of **commas as pacing marks inside
literal values** belongs in the respelling table's spoken forms.

## 8. Measured delivery (published audio)

| Measure | Interface | Architecture | Knowledge Bases |
|---|---|---|---|
| Words per minute while talking | 144 | 125 | 131 |
| Words per minute over the whole span | 138 | 122 | 120 |
| Median pause | 0.35 s | 0.37 s | 0.37 s |
| 90th-percentile pause | 1.0 s | 1.0 s | 1.5 s |
| Pauses ≥ 2 s | 1 | 0 | 8 (waiting for the AI's answers) |
| Median sentence length | 12 words | 11 words | 13 words |
| 90th-percentile sentence | 22 words | 21 words | 22 words |
| First word after the start | 0.5 s | 0.4 s | 0.1 s |

**Compared with Andrew (edge-tts, rate +0%):** p1.03 runs at about 160–175 words per minute, noticeably faster than
David's 125–145. David approved −15% (R22).

## 9. Checklist for a pipeline narration draft

- [ ] Each click line says where, what and (first time) why; the cue word starts the move (R28, R23).
- [ ] Results are confirmed in a short follow-up clause where the change is visible (R24).
- [ ] Written for the ear: sentences ~12 words, none over ~25; literal values have a spoken form; per-take values are
      explained (R29).
- [ ] Out-of-scope items are named and dismissed in one sentence (§5).
- [ ] Asides only where the overlay plan puts one, each with its overlay (R129, R130).
- [ ] Actions in the first person ("I'll click …"), as the episodes do; "you" for what the viewer sees or does on their
      own (R66, §2).
- [ ] No gap over 2 s without talking (R25).
- [ ] Every on-screen label named in a line is listed in `narration.labels` (R26).
- [ ] Episode frame and the standard call to action (R30).
