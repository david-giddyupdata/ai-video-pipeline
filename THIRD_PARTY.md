# Third-party material

Everything in this repository was written or exported by GiddyUp Data LLC and is under the MIT license in
`LICENSE`, except the items in the first table, which keep their own licenses. The other tables list tools the
pipeline uses that you install and license yourself.

## Included in this repository

| What | Where | License |
|---|---|---|
| remocn components (animated charts, icons, ink marks, number wheels) | `remotion/src/overlays/vendor/remocn/` | MIT (`LICENSE` beside them), from github.com/Remocn/remocn |
| Lucide icon shapes used by those components | `remotion/src/overlays/vendor/remocn/` | ISC (`LICENSE-lucide` beside them) |
| Tabler icons | `remotion/src/overlays/vendor/tabler/icons.ts` | MIT (`LICENSE` beside it) |
| US states map (us-atlas `states-albers-10m`) | `remotion/src/overlays/data/states-albers-10m.json` | us-atlas is ISC; the shapes come from US Census Bureau data (public domain) |
| Fonts: Caveat, Inter, JetBrains Mono | `remotion/src/overlays/fonts/` | SIL Open Font License 1.1 (`OFL-*.txt` beside them) |

The two files in `pipeline/vendor/` were copied from my own workshop material, not from a third party; their headers
say where from and what changed.

## Remotion

The overlays and edit layers are drawn with [Remotion](https://www.remotion.dev) (4.0.487), installed from npm by
`remotion/package.json`, not included here. **Remotion is not MIT.** It is free for individuals and for companies of
up to 3 people; companies of 4 or more need a paid company license. Read
[remotion.dev/license](https://www.remotion.dev/license) before you use it at work. React (MIT) and TypeScript
(Apache-2.0) come with it. `skills-lock.json` names Remotion's official agent skills (`remotion-dev/skills`), which you
install yourself.

## Used, not included (you install them)

| Tool | License | Notes |
|---|---|---|
| Playwright (Python) | Apache-2.0 | Drives the browser the lesson is recorded in |
| OBS Studio, obs-websocket, obsws-python | GPL-2.0 (OBS); see each package | Recording |
| ffmpeg / ffprobe | LGPL or GPL, depending on the build | Frame pulls, joins, loudness |
| OpenCV, NumPy, Pillow | Apache-2.0, BSD-3-Clause, MIT-CMU | Frame and image work |
| PyTorch, Hugging Face transformers | BSD-3-Clause, Apache-2.0 | Run the word-timing model |
| Qwen3-ForcedAligner-0.6B | Apache-2.0 (check the model card) | Word timings; downloaded, not included |
| rembg (BiRefNet), onnxruntime | MIT, MIT | Cuts generated art out of its background |
| RapidOCR | Apache-2.0 | Second OCR reader |
| PyMuPDF | AGPL-3.0 (or a commercial license) | Renders an Illustrator arrow to a still in `pipeline/edit/premiere.py`. If you distribute software that bundles it, or offer it as a network service, the AGPL applies to you |
| edge-tts, jsonschema, lxml, comtypes, pywin32, google-api-python-client, boto3 | See each package | Free placeholder voice, schema checks, XML, Windows automation, YouTube, AWS |

## Services and software you license yourself

- **Adobe Premiere Pro** (Adobe's terms). Paid. The export presets in `pipeline/edit/ppro/presets/` are settings files
  saved from Premiere; `pipeline/edit/ppro/titles.py` points at Premiere's own "Basic Title" template on your machine,
  which is not included.
- **ElevenLabs** (its terms). Clone only your own voice.
- **HeyGen** (its terms). The pipeline uses HeyGen's official API. Its web-app steps are described, not shipped (see
  the README).
- **Abacus.ai** (its terms). Not used by any code here; described in the documents only.
- **YouTube Data API, OpenRouter and the model providers behind it, Anthropic Claude and Claude Code, GitHub
  Codespaces** (each its own terms).
- **Windows** (Microsoft's terms). The pipeline uses Windows OCR, UI Automation and system fonts such as Segoe UI,
  Arial and Lucida Console, which it reads from `C:\Windows\Fonts` and which are not included.

## A note on look-alikes

`remotion/src/overlays/SeriesCard.tsx`, `SubscribeCta.tsx` and the subscribe card in `AvatarStage.tsx` are original
code that re-creates the look of Motion Array templates I licensed for my own videos. No Motion Array file is
included. If you reuse them, make the look your own.
