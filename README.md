# AI video pipeline: a worked example

**This is an example from a real project, not software that runs unmodified.** It is the pipeline an AI agent
(Claude Code) and I built to turn a browser-based lesson into a narrated, edited training video: the agent records
the lesson on screen, narrates it in a cloned voice, plans the edit, draws the cursor, zooms and overlays in code,
and builds the project in Adobe Premiere Pro for me to review and finish. It is wired to my Windows machine, my
paid tools and my folders. Read it to see how the parts fit together, then borrow the ideas.

In the documents this project is **AIDrivenVideo**, its folder name in my workspace; **AIDV** (the Premiere
panel, the environment variables) is the same thing.

By David Baldwin, GiddyUp Data LLC. Part of the takeaway from the talk "Move Beyond the Chatbot" (October 2026).
**New to AI agents?** Start with the starter kit,
[ai-workspace-blueprints](https://github.com/david-giddyupdata/ai-workspace-blueprints): it sets up a workspace in
about 15 minutes with no programming. The other worked example is
[ai-documentation-pipeline](https://github.com/david-giddyupdata/ai-documentation-pipeline).

## What it does

- **Records a take.** Drives a real browser (Playwright over the Chrome DevTools Protocol, in its own Edge profile)
  through a step list, one action and one narration line per step, while OBS records a clean capture monitor. Every
  action is logged with its timing and the box of the element it touched.
- **Narrates.** Voices each line in a cloned voice (ElevenLabs) or a free stock voice (edge-tts), with word timings,
  then cleans each clip's edges so nothing pops.
- **Plans the edit.** Cuts dead air and waiting, times each line to the action it describes, and decides zooms,
  highlights and captions from the logged boxes, not by eye.
- **Draws in code.** Remotion (React) renders the cursor, click rings, zooms, highlight marks, chapter cards and
  overlays as transparent layers.
- **Builds the Premiere project.** Writes Final Cut Pro 7 XML that Premiere imports, then drives Premiere itself
  through a small panel and a local bridge: binned media, editable titles, markers at the moments I should check, and
  exports for the checks.
- **Checks its own work.** Measured checks on every round (captions against the screen, loudness, flicker, breaths),
  an OCR privacy scan for names and account numbers on screen, and a fresh AI reviewer before I see a round.
- **Optional avatar.** A HeyGen avatar for the intro and outro, through HeyGen's official API.

The documents matter as much as the code. `RULES.md` holds every decision I made, numbered, so the agent never
relitigates one. `GOTCHAS.md` lists how each tool misbehaves. Both grew one correction at a time.

**Where to start:** `GOTCHAS.md` (the reusable part), then `RULES.md` for the format, then `SPEC.md` for how
the pieces connect.

## What's here: for use, or as an example

| Path | What it is | Use or example |
|---|---|---|
| `GOTCHAS.md` | How Playwright, Codespaces, OBS, edge-tts, ElevenLabs, HeyGen, Remotion and Premiere's XML import and scripting actually behave, with the fix for each | **For use.** Read it before you automate any of these tools |
| `RULES.md` | My numbered decision log (R1, R2, ...), each with the date, my words, and what enforces it | **For use as a pattern.** Copy the format, not the rules: the starter kit has an empty template |
| `tools/blueprint.py` | The scanner that staged and checked this public copy: secrets, account IDs, client names, codespace names, paths | **For use**, with edits: its file rules are written for this project's layout |
| `remotion/src/overlays/` | Overlay components (callouts, checklists, maps, word builds, chapter cards) with vendored MIT and ISC pieces | **Close to reusable.** Expect to replace my colors and fonts (`tokens.json`) |
| `pipeline/edit/ppro/` | The Premiere bridge: a CEP panel, an ExtendScript file and a Python client on a token-guarded local server | **An example.** A working pattern for driving Premiere from Python; tied to Premiere Pro 2026 |
| `pipeline/` (the rest), `remotion/` (the rest), `schemas/`, `tools/` | Capture, narration, edit planning, checks, privacy, publishing | **An example.** Wired to my machine: paths, monitors, ports, profiles |
| `exercises/build_an_interactive_dashboard/` | The step lists, narration and edit settings for the first test video (a dashboard built with Claude Code in a GitHub codespace) | **An example** of what the pipeline reads. `steps_full.json` is the source; the `*_take02` pair is one take's merged copy, kept as an example of `pipeline.generated.merge` |
| `SPEC.md`, `CLAUDE.md` | The design and file formats; the agent's map of the project and its commands | **An example** of how I brief the agent |
| `research/style_study/` | My editing style and narration, measured from my published videos, which set the pipeline's numbers | **An example** of turning taste into numbers an agent can check |

Values I removed are shown as placeholders in angle brackets: `<CLIENT>`, `<YOUR_GITHUB_ACCOUNT>`,
`<CODESPACE_NAME>`, `<CODESPACE_DISPLAY_NAME>`, `<GITHUB_REPO_ID>`, `<S3_BUCKET>`, `<ELEVENLABS_VOICE_ID>`,
`<HEYGEN_LOOK_ID>`, `<QUICKSIGHT_ACCOUNT_NAME>`, `<DOCUMENTS_DIR>` (a folder on my machine) and
`<UNLISTED_VIDEO_URL>`. The stock HeyGen avatar and ElevenLabs voice one reel used are `<HEYGEN_STOCK_SEATED_ID>`,
`<HEYGEN_STOCK_LOOK_ID>`, `<HEYGEN_STOCK_AVATAR_ID>` and `<ELEVENLABS_STOCK_VOICE_ID>`. Paths such as
`D:\Videos\...` and `G:\aidv_scratch\...` are my machine's folders and are left as settings to change.

The documents also mention files that are not published here: `PLAN.md`, `SESSION_HANDOFF.md`, the `docs/` and other
`research/` folders, `runs/` (recordings), the brand media (logo, music, avatar stills, background pictures), and
the workshop's `automation\start_browser.ps1`, which starts the recording browser. They are session notes,
course material, recordings or my likeness. In place of `start_browser.ps1`, start Edge yourself:
`msedge --remote-debugging-port=9333 --user-data-dir=<dir> --profile-directory="Profile 1"`.

`VIDEO_RULES.md` is the workspace rulebook every check reads (in my workspace it lives at
`D:\Videos\Global Assets\VIDEO_RULES.md`): each rule, its numbers, the R numbers behind it, and how it's checked. It
shows the loop the pipeline runs on: a note becomes a rule, the rule becomes a check.

`remotion/package.json` has only `dev`, `typecheck` and `sync-tokens` (the last copies tokens from my workspace and
fails elsewhere). Renders are run from the Python side, which calls `node scripts/<name>.mjs` in `remotion/`
(`stage.mjs`, `stills.mjs`, `reel.mjs`, `ctas.mjs`); `tools/overlay_review.py` also calls `review/render.mjs`, which
is not published.

## What it needs, and what it costs

**Windows only.** It uses Windows OCR, Windows UI Automation (the file Open dialog, window placement) and a second
monitor for clean captures. Python 3.12 or later, Node.js, Git and Visual Studio Code with Claude Code. The main
environment's packages are in `requirements.txt`. The local models (word timings, the second OCR reader, cutouts)
run in a separate venv, `~/.venvs/aidv-ml` (torch, transformers, onnxruntime-gpu, rapidocr, rembg; see
`pipeline/ml/paths.py`), and their weights are downloaded once, by hand, into `~/.aidv-tools/models`. Prices as of
October 2026, mostly from third-party summaries; check before you buy.

> **The one big paid item is Adobe Premiere Pro.** About $22.99 a month on an annual plan billed monthly, $263.88 a
> year paid up front, or $34.99 a month with no commitment (US individual). The pipeline drives Premiere through a
> custom panel, so it can't be swapped for another editor without rebuilding that part.

| Tool | What it's for | Required? | Cost | Free alternative |
|---|---|---|---|---|
| Claude Code (in VS Code) | The agent that wrote and runs the pipeline | Required | A paid Claude plan: Pro about $20 a month, Max $100 or $200 | Other agent tools; the practices are tool-neutral |
| **Adobe Premiere Pro 2026** | Where I review and finish; the pipeline builds each round's project | Required as built | **Paid; see the box above** | DaVinci Resolve has a free edition, but the Premiere bridge won't carry over (not tested) |
| OBS Studio + obs-websocket | Records the capture monitor in its own profile | Required | Free | n/a |
| Remotion 4 (React, TypeScript) | Cursor, click rings, zooms, marks, overlays | Required | Free for individuals and companies of up to 3 people; larger companies need a company license ([remotion.dev/license](https://www.remotion.dev/license)) | n/a |
| ffmpeg / ffprobe | Frame pulls, joins, click repair, loudness | Required | Free | n/a |
| Playwright (Python), Edge | Drives the browser the lesson is recorded in | Required | Free | Chrome |
| Python packages: OpenCV, NumPy, Pillow, jsonschema, lxml, comtypes, pywin32, obsws-python and the rest of `requirements.txt` | Frame analysis, files, Windows automation | Required | Free | n/a |
| Qwen3-ForcedAligner (transformers, PyTorch), RapidOCR, rembg | Word timings, a second OCR reader, cutting art out of its background | Required as built (a GPU helps) | Free | n/a |
| **ElevenLabs** | Narration in your own cloned voice | Optional | Starter $6 a month (instant clone); Creator $22 a month (professional clone) | edge-tts, a free stock voice (not yours) |
| **HeyGen** | Avatar intro and outro | Optional | Creator $29 or Pro $49 a month on the web plans; the API is billed separately, about $0.65 a minute for Avatar III | Leave the avatar out |
| Outside AI models (OpenRouter) | Blind outside reviews of a finished video | Optional | Pay per use: about $5.40 for one video's frame review; my whole video project used about $11.50 | A fresh Claude session |
| YouTube Data API | Uploads, private only | Optional | Free | Upload by hand |

As I built it, the video example runs about $50 to $130 a month on top of the Claude plan, depending on the voice and
avatar plans, and Premiere is the largest single line.

## Secrets

Nothing here contains a key. The code reads every key through one function, `get_section()` in `pipeline/config.py`.
In this copy it reads a JSON file **outside the repository**, named by the environment variable `AIDV_SECRETS_FILE`
(default `~/.aidv/secrets.json`), with sections `elevenlabs`, `heygen`, `obs`, `youtube_oauth`, `openrouter` and
`google`. On my machine it reads AWS Secrets Manager instead. Point it at your operating system's keyring or your
company's vault if you can.

## Described, not shipped: the HeyGen and Abacus web apps

Two steps of my own work use services through their **web apps** rather than an API: HeyGen's web app renders the
avatar on my subscription's credits, and Abacus.ai's Studio made candidate video clips (it has no video API). For
those, the agent drives a separate, dedicated browser profile that I signed in to myself; it never touches sign-in,
billing or payment, and I confirm each paid step.

**The scripts that do this are not in this repository.** Automating a service's web app may break its terms of
service, and publishing a working tool for it could invite others to do the same and put accounts at risk. `RULES.md`
and `GOTCHAS.md` describe the method in prose. If you want to do something similar, read the service's terms first,
and prefer its official API: this pipeline's HeyGen avatar code (`pipeline/edit/avatar.py`) uses HeyGen's official
API, and `pipeline.edit.avatar webapp` only registers a render you downloaded yourself.

## Safety

- **The agent drives its own browser, and I sign in.** Takes run in a separate Edge profile on its own debugging
  port, never an everyday browser. Anything that browser can do as you, a script can do.
- **The auto-approver is a recording aid for a throwaway account.** `pipeline/vendor/claude_watch.py` answers Claude
  Code's permission prompts during a recorded take unless the command matches a risky pattern. I ran it only on a
  test GitHub account and a disposable codespace. Don't copy it into a real setting: a pattern list is not a safety
  boundary.
- **I run my agent with its permission prompts off.** Don't copy that. Keep the prompts on, and on a company
  computer start from the stricter settings in the starter kit's `use/settings/`.
- **The cleanup tool deletes only what it can account for.** `tools/qs_cleanup.py` deletes only Quick Sight objects
  that a snapshot and diff of its own run found (and that carry a name the run typed), or, with `orphans`, copies of
  an exact name created before a date you give. Both only print what they would do until you add `--yes`. Uploads
  go to YouTube as private; publishing is a person's job.
- **The Premiere bridge trusts local processes.** It runs any ExtendScript that a process running as your Windows
  user sends with its token. It listens only on 127.0.0.1, and the token changes at every Premiere start.
- **Synthetic media.** This pipeline narrates in a cloned voice and can add an avatar. Platforms such as YouTube have
  their own rules for disclosing realistic synthetic content; the pipeline does not handle disclosure for you. Clone
  only your own voice and likeness.
- **Prompt injection is not solved.** An agent that reads a web page or a session log can be misled by instructions
  hidden in it. Keep agents away from data and actions they don't need.

## License and contact

MIT License, copyright 2026 GiddyUp Data LLC (see `LICENSE`). Vendored components, fonts and map data keep their own
licenses, listed in [`THIRD_PARTY.md`](THIRD_PARTY.md). **The GiddyUp Data name and logo are not licensed for reuse.**
Questions or errors: open an issue. Pull requests are not accepted for now. For anything sensitive, see
[`SECURITY.md`](SECURITY.md).
