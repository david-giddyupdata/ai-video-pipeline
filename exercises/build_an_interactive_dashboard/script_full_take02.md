# Narration script: build an interactive dashboard

Rendered from `steps_full_take02.json` (version 4) by `python -m pipeline.narration.script`. Don't edit this file: notes go to Claude, who changes the steps file and renders it again.

- **Lines:** 55 approved, 29 draft, 0 written after the run or the exploration (their points are below).
- **Voiced so far:** about 16:48 at Andrew's pace, before the live footage (time-lapses, title card, 1x permission prompts).

## Not built yet

| Builds it | Capability | Steps |
|---|---|---|

## Lint

- **p5.15c:** [improvement] mark word 'clicked' is not in the line
- **p5.15c:** [improvement] mark word 'saw' is not in the line
- **p5.15c:** [improvement] mark word 'expected' is not in the line

## Part 0: Opening

Voiced about 1:45.

**p0.01** · no action (the line plays over the picture) · approved

> In this video, we'll build an interactive dashboard from a file of U.S. flight data, using Claude Code in a GitHub codespace. We won't write any code ourselves.

<sub>Spoken: In this video, we'll build an interactive dashboard from a file of U.S. flight data, using Claude Code in a GitHub code space. We won't write any code ourselves.</sub>

<sub>Episode frame (R30). Motion graphics on screen (R69): text slides over a still of the finished dashboard, rendered in Remotion; see remotion/ OpeningRecap. The take itself starts at p1.01.</sub>

**p0.02** · no action (the line plays over the picture) · approved

> Claude Code can discover the data, propose options, and build the whole solution. That's powerful, but it's also easy to get a result you didn't want if you don't know how to direct it.

**p0.03** · no action (the line plays over the picture) · approved

> This exercise uses a direction prompt. A direction prompt describes the goal, the audience, and the quality you expect, and leaves the technical decisions to the AI. It's how a manager gives direction to an analyst.

**p0.04** · no action (the line plays over the picture) · approved

> A construction prompt is the opposite. It spells out exactly what to build, such as a bar chart of flights by region, using matplotlib. Use a construction prompt when you know exactly what you want. Use a direction prompt when you know the goal, but not the path.

<sub>Spoken: A construction prompt is the opposite. It spells out exactly what to build, such as a bar chart of flights by region, using mat plot lib. Use a construction prompt when you know exactly what you want. Use a direction prompt when you know the goal, but not the path.</sub>

**p0.05** · no action (the line plays over the picture) · approved

> We'll work through the exercise in order. First, we'll find the data and open Claude Code. Then we'll ask for the dashboard, choose from Claude's options, and let it build. Finally, we'll explore the dashboard, request a fix, and save our work to GitHub.

- *improvement* variant (R71): We'll work through the exercise in order. First, we'll find the data and open Claude Code. Then we'll ask for the dashboard, choose from Claude's options, and let it build. Finally, we'll explore the dashboard, request a change, and save our work to GitHub.

**p0.06** · no action (the line plays over the picture) · approved

> To follow along, you'll need a codespace with the starter files and your Anthropic API key. The Setup video covers that, and you can access it via the description. Plan on about thirty minutes. So, let's get started.

<sub>Spoken: To follow along, you'll need a code space with the starter files and your Anthropic API key. The Setup video covers that, and you can access it via the description. Plan on about thirty minutes. So, let's get started.</sub>

## Part 1: Find your data (doc steps 1 to 6)

Voiced about 1:25.

**p1.01** · navigate · approved

> I'll start at github.com/codespaces. A codespace is a complete development workspace that runs in your browser, so there's nothing to install.

<sub>Spoken: I'll start at GitHub dot com slash codespaces. A code space is a complete development workspace that runs in your browser, so there's nothing to install.</sub>

- draw rect on *github.com/codespaces*

**p1.02** · click `a[href='/codespaces?repository_id={repo_id}']` · approved

> On the left, under By repository, I'll click my repository, my-agentic-workshop. As you can see, the list narrows to that repository's codespaces.

<sub>Spoken: On the left, under By repository, I'll click my repository, my agentic workshop. As you can see, the list narrows to that repository's codespaces.</sub>

- labels: *By repository*
- draw rect on *my-agentic-workshop*

<sub>Matched by repository id: by name, my-agentic-workshop is a prefix of every take repo (take02 of S6 clicked take06's link, 2026-10-07).</sub>

**p1.03** · click `a[href='/codespaces/{codespace_name}']`

> Then I'll click my codespace. GitHub gives every codespace a random name. This one is called {codespace_display}. Yours will have a different name.

<sub>Spoken: Then I'll click my code space. GitHub gives every code space a random name. This one is called {codespace_display}. Yours will have a different name.</sub>

- draw arrow on *codespace*
- draw arrow on *{codespace_display}*

<sub>Opens in a new tab (the link has target=_blank). Codespaces occasionally stalls on 'Setting up your codespace'; the runner reloads once after 90 s. A stopped codespace takes about a minute to start; that wait is cut in the edit. Changed 2026-10-08: "a random two-word name" became "a random name", since the full take's codespace is "<CODESPACE_DISPLAY_NAME>" (three words); draft until David approves.</sub>

**p1.04** · click `.monaco-dialog-box .monaco-button:has-text('Trust Folder')` · *conditional* · approved

> A box asks whether I trust the authors of the files in this folder. It's my own repository, so I'll click Trust Folder & Continue.

<sub>Spoken: A box asks whether I trust the authors of the files in this folder. It's my own repository, so I'll click Trust Folder and Continue.</sub>

- labels: *Trust Folder & Continue*

<sub>Appears only on a codespace's first open. The take's existing codespace is already trusted, so this step is skipped there; a fresh take repo shows it.</sub>

**p1.05** · click `.activitybar a[aria-label^='Explorer']` · *conditional* · approved

> The file list isn't showing, so I'll click the Explorer icon at the top of the bar on the far left.

<sub>Clicking Explorer while it is open would close it, so the step runs only when the file list is hidden.</sub>

**p1.06a** · click `.explorer-folders-view .monaco-list-row[aria-label='data']` · *conditional* · approved

> The Explorer, on the left, lists the files in the repository. I'll open the data folder,

<sub>A click on an expanded folder collapses it, so the take stops if data is already open (prepare resets it).</sub>

**p1.06b** · click `.explorer-folders-view .monaco-list-row[aria-label='monthlysummary.csv']` · approved

> and select monthlysummary.csv. The first line lists the columns, from location and airport code to delays, cancellations and taxi times. Each row after that is one airport in one month, about twenty-four thousand rows in all.

<sub>Spoken: and select monthly summary dot C S V. The first line lists the columns, from location and airport code to delays, cancellations and taxi times. Each row after that is one airport in one month, about twenty-four thousand rows in all.</sub>

- draw rect on *first*

**p1.06c** · click `.notifications-toasts .notification-toast:has-text('Rainbow CSV') .codicon-notifications-clear` · *conditional* · approved

> A notice offers to install the Rainbow CSV extension. We won't need it, so I'll close it with the X.

- draw rect on *notice*

## Part 2: Open Claude Code and interact (doc steps 7 to 10)

Voiced about 2:56.

**p2.07a** · click `.part.auxiliarybar .composite-bar a[aria-label="Claude Code"]` · *conditional* · approved

> Claude Code lives in the panel on the right-hand side of the screen. I'll click the Claude Code tab.

<sub>When the codespace already shows a Claude Code tab next to Chat: after a restart it does (take06, 2026-10-07). On a codespace's very first open it doesn't, so p2.07b and c run instead.</sub>

**p2.07b** · click `.part.auxiliarybar [aria-label="Additional Views"]` · *conditional* · approved

> Claude Code lives in the panel on the right-hand side of the screen. As of this writing, a new codespace doesn't show a Claude Code tab, so I'll click the three dots next to Chat,

<sub>Spoken: Claude Code lives in the panel on the right-hand side of the screen. As of this writing, a new code space doesn't show a Claude Code tab, so I'll click the three dots next to Chat,</sub>

- labels: *Chat*
- draw rect on *three*

**p2.07c** · click `.context-view >> text="Claude Code"` · *conditional* · approved

> and choose Claude Code. Notice that the Chat tab next to it is GitHub Copilot, a different assistant. We're using Claude Code in this video.

- labels: *Chat*

**p2.07d** · click `button[aria-label="Hide onboarding"]` · *conditional* · approved

> Claude Code opens with two welcome cards. We won't need them, so I'll close Learn Claude Code with its X,

- labels: *Learn Claude Code*

<sub>The doc's welcome cards, shown once Claude Code is logged in (take06, 2026-10-07): 'Learn Claude Code' closes with its Hide onboarding X; 'Auto mode is now Claude Code's default permission mode.' with its Close X.</sub>

**p2.07e** · click `button[aria-label="Close"]` · *conditional* · approved

> and then Auto mode.

- labels: *Auto mode*

<sub>The doc's welcome cards, shown once Claude Code is logged in (take06, 2026-10-07): 'Learn Claude Code' closes with its Hide onboarding X; 'Auto mode is now Claude Code's default permission mode.' with its Close X.</sub>

**p2.07f** · click `button[aria-label="New session"]` · *conditional*

> This codespace already has an earlier conversation, so I'll click New session to start fresh.

<sub>Spoken: This code space already has an earlier conversation, so I'll click New session to start fresh.</sub>

<sub>Only in a reused codespace: the panel reopens its last conversation (with any open question form) after a reconnect, and an off-camera New session does not survive it (s7_take05). A fresh repo skips this step.</sub>

**p2.08a** · type · approved

> Before we build anything, I'll give Claude two standing rules. I'll enter this prompt. Every prompt in this video is available via the description.

```text
Before we build anything, add two rules to CLAUDE.md:
- Keep this file short. When we finish a piece of work, write notes about it in a file in the docs folder, and add a one-line pointer to that file here.
- When I ask you to commit, commit to the main branch and push it to GitHub. Don't create other branches.
```

<sub>Typed at natural speed, not pasted (R67): the edit speeds the typing up or cuts its middle, so the line plays over the finished prompt. The description carries every prompt.</sub>

**p2.08b** · no action (the line plays over the picture) · approved

> These rules go in CLAUDE.md, a file that Claude reads at the start of every session, so they apply from now on.

<sub>Spoken: These rules go in Claude dot M D, a file that Claude reads at the start of every session, so they apply from now on.</sub>

- draw rect on *CLAUDE.md*

**p2.08c** · no action (the line plays over the picture) · approved

> The first rule keeps that file short. On a long project, notes pile up, and Claude would read all of them every time.

- draw rect on *short*

**p2.08d** · no action (the line plays over the picture) · approved

> The second rule keeps our work on the main branch, which GitHub shows on the repository's front page. Without it, Claude may save the work on a separate branch.

- draw rect on *main*

**p2.08e** · click `button[aria-label="Send message"]` · approved

> I'll click the send arrow. As you can see, the prompt moves into the conversation.

<sub>Send arrow confirmed in take06 (2026-10-07). The busy panel shows 'Queue another message'.</sub>

**p2.09** · wait for Claude · *live*

> Claude reads CLAUDE.md, then edits it. In this run, it adds both rules under a new Rules heading, and says it hasn't committed the change.

<sub>Spoken: Claude reads Claude dot M D, then edits it. In this run, it adds both rules under a new Rules heading, and says it hasn't committed the change.</sub>

- labels: *Rules*
- draw rect on *reads*
- draw rect on *adds*

Must cover, if it happens:

- Claude's reply: it added both rules to CLAUDE.md (doc step 9).
- If the reply shows the edit, point at the two new lines.

<sub>Usually under 20 s: real time with the cut rules (R39). Auto mode edits CLAUDE.md without a prompt. Marks (R75): the Read row and the reply's first sentence, by OCR of the panel; the reply is on screen before the wait ends (take06).</sub>

**p2.10a** · type · approved

> Now let's ask for the dashboard. I'll enter the dashboard prompt.

```text
I have a CSV of U.S. flight data. Build me a single interactive dashboard for an aviation operations team. Use data visualization best practices. Create calculated fields, filters, and parameters where they make sense. Don't limit yourself to just what's in the data; apply what you know about the airline industry and current trends to decide what's useful. Visuals should interact with each other where appropriate. Before you start building, tell me what options we have and ask any questions you need answered. Note that I want the dashboard to run here in my Codespace so I can open it in my browser. The file is at: data/monthlysummary.csv
```

<sub>Typed at natural speed, not pasted (R67): the edit speeds the typing up or cuts its middle, so the line plays over the finished prompt. The description carries every prompt.</sub>

**p2.10b** · no action (the line plays over the picture) · approved

> Notice what the prompt describes: the audience, an aviation operations team, and the quality bar, data visualization best practices.

- draw rect on *aviation*
- draw rect on *data*

<sub>The long prompt scrolls inside the message box (take06, 2:26), so the whole prompt is shown on an overlay and the highlights go on it (R77). The overlay stays up through p2.10d.</sub>

**p2.10c** · no action (the line plays over the picture) · approved

> It doesn't name a chart type, a column, or a framework. It also tells Claude to look beyond the data, and apply what it knows about the airline industry.

- draw rect on *beyond*

**p2.10d** · no action (the line plays over the picture) · approved

> Note that we ask for options before Claude builds anything. This is a best practice. Claude lays out the choices, and we make the decisions that matter.

- draw rect on *options*

**p2.10e** · click `button[aria-label="Send message"]` · approved

> I'll click the send arrow. Claude starts by reading the data.

<sub>Send arrow confirmed in take06 (2026-10-07). The busy panel shows 'Queue another message'.</sub>

**p2.10f** · wait for Claude · *live* · approved

> In this case, it counts the rows, reads the columns, and checks the other files in the data folder before it proposes anything. Then it writes up what it found.

Must cover, if it happens:

- Claude reads the CSV first, to learn the columns, before it proposes anything.

<sub>p2.10e already says Claude starts by reading the data (take06 had both, 3:00 and 3:03). The 20 s of tool calls are time-lapsed under this line (realtime_max_s 10 for this step) instead of cut, so the viewer sees the reading happen (R75).</sub>

## Part 3: Give direction, not instructions (doc step 11)

Voiced about 1:30.

**p3.11a** · scroll Claude's reply · *live*

> Claude lays out its findings, and what it could build. In this run, it offers three layouts, and recommends an executive overview. The overview puts key numbers across the top, then a map, a trend line with events marked, and a ranking. For the technology, it recommends Plotly Dash, which is already installed. It also notes what the data can't answer, such as which airline or route a flight was. Treat findings like these as things to check, not facts. Another run may suggest different charts, but the shape of the reply is what to expect: findings, options, and questions.

<sub>Spoken: Claude lays out its findings, and what it could build. In this run, it offers three layouts, and recommends an executive overview. The overview puts key numbers across the top, then a map, a trend line with events marked, and a ranking. For the technology, it recommends Plot-lee Dash, which is already installed. It also notes what the data can't answer, such as which airline or route a flight was. Treat findings like these as things to check, not facts. Another run may suggest different charts, but the shape of the reply is what to expect: findings, options, and questions.</sub>

Must cover, if it happens:

- Claude laid out the options: name the frameworks it offered and the one it recommends.
- Its plan for the page (charts, filters, parameters) in one sentence.
- Arrive on its questions ("Questions for you" in the doc's run); read one or two aloud, e.g. cancellations or alert thresholds.
- Any data quirks it found on its own (doc's run: missing coordinates, territories): findings to verify, not facts.

<sub>Reading a reply on camera (S7): the runner jumps the conversation to the start of Claude's last reply, below the pinned prompt, holds, then scrolls through it at a steady reading pace (runner READ_PX_S) and holds. The narration is written after the run (R33); the edit fits the scroll to it. The narrow panel at 2x shows too little of the reply to follow (take06, 3:17), so its main points go on an overlay, worded as what Claude may suggest (R76, R77); the scroll keeps playing beside it. Round 2 (David, 2026-10-07): the last item said the questions, one level below its sentence; it now sums up the shape of the reply and appears on 'findings' (R80; his Premiere edit moved it there).</sub>

**p3.11e** · press Escape · *conditional* · approved

> This time, Claude asks its questions in a form, starting with the layout. I could answer each one here, but instead I'll press Escape to close the form, and answer in my own words.

- draw rect on *form*

<sub>Runs between p3.11a and p3.11b (lettered e because the others were taken). Only when Claude asks with its question form (s7_take04) instead of plain text (s7_take01, take02). Escape closes the form ('Tool interrupted') and the message box takes the scripted answer (p3.11b). Checked off camera on take08, 2026-10-07. Mark (R75): the whole form, from its first question to 'Esc to cancel' (OCR span). R78: the questions clause is said before Escape. Round 2 (David, 2026-10-07): only the layout question is readable; the others sit behind tabs cut to 'La… E… C… Aud…', so the line no longer names them (R81).</sub>

**p3.11b** · type · approved

> In the box at the bottom, I'll type my answer. We'll use Plotly Dash, a Python framework for interactive web dashboards, and let Claude go with its defaults for everything else.

<sub>Spoken: In the box at the bottom, I'll type my answer. We'll use Plot-lee Dash, a Python framework for interactive web dashboards, and let Claude go with its defaults for everything else.</sub>

```text
Let's use Plotly Dash. Go with your defaults for everything else.
```

<sub>Edited 2026-10-07 after David's review of s7_take06 (docs/S7_FIX_PLAN.md): R78, the form is closed by now, so 'I could answer each of Claude's questions' moved into p3.11e. Was approved; needs David's OK.</sub>

**p3.11c** · click `button[aria-label="Send message"]` · approved

> I'll click the send arrow, and Claude starts building.

<sub>Send arrow confirmed in take06 (2026-10-07). The busy panel shows 'Queue another message'.</sub>

**p3.11d** · no action (the line plays over the picture) · approved

> That's the direction prompt at work. We set the goal and made the decision that mattered most, and Claude handles the implementation.

<sub>Plays over the first seconds of the build (live footage). Calls back to the opening (p0.03).</sub>

## Part 4: Let Claude build (doc steps 12 to 13)

Voiced about 1:40.

**p4.12** · wait for Claude · *live*

> Claude starts the build. From here, Claude may load skills, install tools, or write and run code, to do its work. We don't tell it how; it decides what the task needs. Each row in the panel is one step it takes. This build took about six minutes, so we'll speed through it. Keep an eye on the Explorer, on the left.

Must cover, if it happens:

- Title card "Claude is building: about N minutes", then a 6 to 10 s time-lapse (R39).
- If Claude loads a skill (such as dataviz): a skill is a packaged set of instructions that Claude loads only when a task calls for it. You didn't ask for it; Claude judged it relevant.
- If it hits an error, it explains it and fixes it on its own (at 1x only if David picks the moment, R39).
- New files, such as app.py and an assets folder, appear in the Explorer. The U means new, and not yet saved to GitHub.
- Dash, Plotly and pandas were already installed in the codespace, so Claude didn't need to install them.
- "Allow this bash command?" to restart the dashboard with pkill: routine, click Yes (1x, a visible click, R39, R47). Auto mode lets Claude edit and run commands, and asks before it stops a program.
- Claude's summary says it ran and tested the code but couldn't see the page: sets up Part 5.

<sub>About 7 min in the workshop walk-through; 3.8 min in take06. The dataviz skill row is on screen as the build starts (take06, 4:28), so it is named and marked during 9 s at 1x before the card (before_card_s). The rest of the build is the card and the lapse. app.py and the summary are p4.12b, after the result. Autopilot: routine prompts approved, RISKY ones stop the take. full_take02: the dataviz skill row scrolled out of the panel during p3.11d's line, before this one starts, so this take's line speaks of skills in general (R78).</sub>

**p4.12b** · no action (the line plays over the picture) · *live*

> When Claude is done, two new folders appear in the Explorer: dashboard, which holds the program, and docs, which holds its notes. The dot means they contain new files, not yet saved to GitHub. The M beside CLAUDE.md means Claude modified it. But in our case, the dashboard didn't open in the browser.

<sub>Spoken: When Claude is done, two new folders appear in the Explorer: dashboard, which holds the program, and docs, which holds its notes. The dot means they contain new files, not yet saved to GitHub. The M beside Claude dot M D means Claude modified it. But in our case, the dashboard didn't open in the browser.</sub>

- draw rect on *dashboard*
- draw rect on *docs*
- draw rect on *M*

<sub>A line-only step (after: p4.12): it rides on the footage after the build's result, consuming no footage of its own; the next step's bridge shows the picture under it. 'tests it' dropped (not visible, R75); 'in our case' (R76); David's wording for the lead-in to Ports. Round 3 (2026-10-07): 'Claude also reports that the dashboard is running' dropped: the report had scrolled out of the panel and the camera was on the Explorer (R81); back to draft for David's OK.</sub>

**p4.13a** · click `role=tab[name="Ports"]` · approved

> If it looks like Claude is done and you don't see the dashboard, check the browser tabs. If it isn't there, it's still running inside the codespace, on port 8050, and you can open it from the panel below the editor. Next to Terminal, I'll click the Ports tab.

<sub>Spoken: If it looks like Claude is done and you don't see the dashboard, check the browser tabs. If it isn't there, it's still running inside the code space, on port eighty fifty, and you can open it from the panel below the editor. Next to Terminal, I'll click the Ports tab.</sub>

- labels: *Ports*
- draw rect on *browser tabs*

<sub>R74: Codespaces opens the dashboard on its own (the template's onAutoForward: openBrowser) or not; the runner closes any tab that opens by itself, so the take always shows the Ports route. The bottom panel must be open for the Ports tab to show. Edited 2026-10-07 after David's review of s7_take06 (docs/S7_FIX_PLAN.md): David's wording ('check the browser tabs, or click the Ports tab next to the Terminal tab'); the tab strip is marked (full frame while it shows, R40). Was approved; needs David's OK.</sub>

**p4.13b** · hover `.monaco-list-row:has-text("8050")` · approved

> Port 8050 is listed here. I'll hover over its row,

<sub>Spoken: Port eighty fifty is listed here. I'll hover over its row,</sub>

<sub>Hover on the port's name (the row's centre is Running Process, which shows a tooltip). The globe is a.codicon-ports-open-browser-icon, aria-label 'Open in Browser' (s7_take02, 2026-10-07).</sub>

**p4.13c** · click `.monaco-list-row:has-text("8050") a[aria-label="Open in Browser"]` · approved

> and click the globe icon. As you can see, the dashboard opens in a new tab.

- draw arrow on *globe*

<sub>Opens the -8050.app.github.dev tab; the camera zooms out on the cut (R44) and holds full frame on the address (R40).</sub>

**p4.13d** · no action (the line plays over the picture) · approved

> Note the address, which ends in 8050.app.github.dev. Codespaces checks that you're signed in to GitHub before it shows the page, so by default, only you can open it.

<sub>Spoken: Note the address, which ends in eighty fifty dot app dot GitHub dot dev. Code spaces checks that you're signed in to GitHub before it shows the page, so by default, only you can open it.</sub>

- draw rect on *8050.app.github.dev*

<sub>From the doc's Technical Details, Port forwarding in Codespaces.</sub>

## Part 5: Explore and iterate (doc steps 14 to 16)

Voiced about 5:07.

**p5.14a** · no action (the line plays over the picture) · approved

> Now let's explore the dashboard Claude built. Your dashboard won't look exactly like this one, because Claude makes different choices each time.

<sub>Recording resumes here after the off-camera exploration (R70).</sub>

**p5.14b** · no action (the line plays over the picture) · *generated*

> At the top are the date range and the filters. Below them are five summary tiles. The Ops strain index is a calculated field Claude added. It combines delays, cancellations, and taxi times into one score, so it isn't in the raw data. The trend chart also labels industry events, such as the CrowdStrike outage. Those come from Claude's general knowledge, not from our data file.

- labels: *Ops strain index*
- fade rect on *date*
- fade rect on *tiles*
- fade rect on *Ops*
- fade rect on *CrowdStrike*

Must cover, if it happens:

- A one-sentence tour, top down, with overview marks on each region (R48 fade marks; doc's run: filters, parameters, KPI tiles, map, ranking).
- One calculated field Claude added that isn't in the raw data (e.g. cancellation rate, a prior-year comparison).
- If it added outside context, such as known disruptions labelled as outside the data: that's the prompt's "don't limit yourself to just what's in the data" at work.

**p5.14c** · click `#p24` · *generated*

> First, a filter. Under Date range, I'll click Last 24 mo. The range now runs from October 2023 to September 2025, and the tiles and the trend update.

<sub>Spoken: First, a filter. Under Date range, I'll click Last 24 months. The range now runs from October 2023 to September 2025, and the tiles and the trend update.</sub>

- labels: *Date range*, *Last 24 mo*
- draw rect on *October*

Must cover, if it happens:

- A filter: a date range or a region (e.g. a preset such as Last 12 months). Announce, act, and say what changed (R23, R24).

<sub>The October mark frames the whole range readout (R84), its OCR line box in this take.</sub>

**p5.14d** · click `#metric` · *generated*

> Next, a parameter. Under Metric, I'll open the list,

- labels: *Metric*

Must cover, if it happens:

- A parameter: the metric, an alert threshold, or the number of airports in the ranking.

**p5.14f** · click `.dash-dropdown-option:has-text("Cancellation rate")` · *generated*

> and choose Cancellation rate. The trend chart now shows the cancellation rate over time, instead of the delay.

- labels: *Cancellation rate*
- draw rect on *trend*

<sub>The metric dropdown's second click (generated, after p5.14d opens the list).</sub>

**p5.14e** · click `#focus` · *generated*

> Now let's focus on one airport. Under Airport focus, I'll open the list,

- labels: *Airport focus*

Must cover, if it happens:

- Cross-filtering: click an airport (a bar, bubble or table row) to drill in, and every chart updates.
- Why it works, in one sentence: each click goes to the Python program, which filters the data and redraws the charts (the doc's Callbacks in depth).

**p5.14g** · click `.dash-dropdown-option:has-text("ABQ")` · *generated*

> and choose Albuquerque. The tiles now show just that airport, and the trend adds its line. As the label says, clicking an airport in the charts further down does the same. Each choice goes to the Python program, which filters the data and redraws the charts.

- draw rect on *tiles*

<sub>The focus dropdown's second click: R70's drill-in. The map and the ranking are below the first screen, so the take picks the airport from the list (the runner's scroll into view would jump the page).</sub>

**p5.15a** · no action (the line plays over the picture) · *generated*

> But notice the two boxes at the ends of the date slider. After I clicked Last 24 mo, they read 45 and 68, not dates. Claude tested its code, but it can't see the page, so we need to tell it.

<sub>Spoken: But notice the two boxes at the ends of the date slider. After I clicked Last 24 months, they read 45 and 68, not dates. Claude tested its code, but it can't see the page, so we need to tell it.</sub>

- labels: *Last 24 mo*
- draw rect on *45*
- draw rect on *68*

Must cover, if it happens:

- The real defect found while exploring, marked on screen. Earlier runs: the period boxes read 57 and 68 instead of dates; the map zoomed in until it was almost blank (the doc's example).
- Pattern: "Notice that <defect>. Claude tested its code, but it can't see the page, so we need to tell it."
- With no defect, an improvement in the doc's style instead, e.g. "Add a comparison of taxi-in and taxi-out times."

**p5.15b** · switch tab · approved

> I'll switch back to the codespace tab,

<sub>Spoken: I'll switch back to the code space tab,</sub>

<sub>The runner reads the tab's place in the strip from the screen and the edit draws the move and click (switch_tab).</sub>

**p5.15c** · type · approved

> and describe the problem in the message box: what I clicked, what I saw, and what I expected. The more precisely we describe a problem, the faster Claude can fix it.

- draw rect on *clicked*
- draw rect on *saw*
- draw rect on *expected*
- *improvement* variant (R71): and describe the change I want in the message box: what I'd like to see, and where. The more precisely we describe a change, the faster Claude can make it.

```text
{feedback_prompt}
```

<sub>The prompt text is generated with the defect (variable feedback_prompt), in the doc's pattern: say what you saw, where, and what you expected. Typed at natural speed, not pasted (R67): the edit speeds the typing up or cuts its middle, so the line plays over the finished prompt. The description carries every prompt.</sub>

**p5.15d** · click `button[aria-label="Send message"]` · approved

> I'll click the send arrow.

<sub>Send arrow confirmed in take06 (2026-10-07). The busy panel shows 'Queue another message'.</sub>

**p5.15e** · wait for Claude · *live*

> Claude works on the fix. It asks before it runs a command that writes the change, and I allow it. Then, as we asked, it restarts the dashboard, so the page can load the new version.

Must cover, if it happens:

- Claude can't reproduce a visual problem on its own: it explains its fix and may ask you to check it.
- A pkill prompt to restart the dashboard is routine (1x, a visible click).

<sub>Time-lapse if over 20 s (R39).</sub>

**p5.15p** · no action (the line plays over the picture) · *live*

> In this run, Claude reports that the boxes now show month names, and asks me to reload the page to check.

- draw rect on *month*
- draw rect on *reload*

<sub>A line-only step on p5.15e's result: Claude's reply, named once it is on screen (R81).</sub>

**p5.15f** · switch tab

> I'll switch back to the dashboard tab,

- *improvement* variant (R71): Claude reports that the change is made. I'll switch back to the dashboard tab,

<sub>The runner reads the tab's place in the strip from the screen and the edit draws the move and click (switch_tab). full_take02: its first sentence (Claude reports the fix) moved to p5.15p, which names the reply once it is on screen.</sub>

**p5.15g** · press F5 · approved

> and reload the page to load the new version.

**p5.15h** · click `#p24` · *generated*

> I'll click Last 24 mo again. Now the handles show dates, but the two boxes still read 45 and 68.

<sub>Spoken: I'll click Last 24 months again. Now the handles show dates, but the two boxes still read 45 and 68.</sub>

- labels: *Last 24 mo*
- draw arrow on *dates*
- draw rect on *45*

Must cover, if it happens:

- Repeat the click that showed the defect, and confirm the fix out loud (R24).
- One round is recorded. "Each round of feedback refines the dashboard" (doc) can be said here.

<sub>The runner saves the dashboard still here, after the fix, for the opening and recap graphics (R69, R88); a second round's repeat of this click saves it again (pipeline.generated.merge). The 45 mark uses p5.15a's logged box of the min input (OCR can't read the number boxes); the slider hasn't moved.</sub>

**p5.15i** · switch tab · *generated* · *conditional*

> The boxes still show numbers, so let's tell Claude again. I'll switch back to the codespace tab,

<sub>Spoken: The boxes still show numbers, so let's tell Claude again. I'll switch back to the code space tab,</sub>

<sub>R70's second round: runs only while the defect still shows after the reload (only_if eval); p5.15j-o follow its decision.</sub>

**p5.15j** · type · *generated* · *conditional*

> and describe what I still see: the boxes still show 45 and 68, instead of dates.

```text
{feedback_prompt_2}
```

**p5.15k** · click `button[aria-label="Send message"]` · *generated* · *conditional*

> I'll click the send arrow.

**p5.15l** · wait for Claude · *live* · *conditional*

> Claude asks twice: once to change the slider, and once to stop the running dashboard so it can restart it. Each time, the prompt shows the exact command, so you can check it before you allow it. Then it checks that the dashboard is running again, and writes up what it changed.

**p5.15q** · no action (the line plays over the picture) · *live* · *conditional*

> This time, it finds what it missed. This version of Dash adds a number box at each end of every slider. Its first fix changed only the labels on the handles. So it turns the boxes off for the date slider.

- draw rect on *Dash*
- draw rect on *off*

<sub>A line-only step on p5.15l's result: Claude's reply, named once it is on screen (R81).</sub>

**p5.15m** · switch tab · *generated* · *conditional*

> I'll switch back to the dashboard tab,

**p5.15n** · press F5 · *generated* · *conditional*

> and reload the page.

**p5.15o** · click `#p24` · *generated* · *conditional*

> I'll click Last 24 mo again. Now the boxes are gone, and the handles show the dates, from October 2023 to September 2025. Each round of feedback refines the dashboard.

<sub>Spoken: I'll click Last 24 months again. Now the boxes are gone, and the handles show the dates, from October 2023 to September 2025. Each round of feedback refines the dashboard.</sub>

- labels: *Last 24 mo*
- draw arrow on *dates*

**p5.16a** · switch tab · *conditional* · approved

> When you finish exploring, it's good practice to stop the dashboard. I'll switch back to the codespace tab,

<sub>Spoken: When you finish exploring, it's good practice to stop the dashboard. I'll switch back to the code space tab,</sub>

<sub>The runner reads the tab's place in the strip from the screen and the edit draws the move and click (switch_tab).</sub>

**p5.16b** · type · approved

> and ask Claude to stop the dashboard. The dashboard is a running program, so it keeps running until something stops it.

```text
I'm done exploring for now; please stop the dashboard.
```

**p5.16c** · click `button[aria-label="Send message"]` · approved

> I'll click the send arrow.

<sub>Send arrow confirmed in take06 (2026-10-07). The busy panel shows 'Queue another message'.</sub>

**p5.16d** · wait for Claude · *live*

> Claude asks before it stops the dashboard, and I allow it. Its reply says how to start it again, if you need to.

Must cover, if it happens:

- "Allow this bash command?" for the command that stops the dashboard: Claude asks before it stops a program. Routine here: click Yes (1x, a visible click).
- Claude confirms the dashboard has stopped.

<sub>Under 20 s in the walk-through.</sub>

**p5.16e** · no action (the line plays over the picture) · approved

> In the Ports tab, notice that the dot next to port 8050 is now hollow. That means the dashboard has stopped.

<sub>Spoken: In the Ports tab, notice that the dot next to port eighty fifty is now hollow. That means the dashboard has stopped.</sub>

- draw arrow on *dot*

<sub>The status icon is codicon-ports-forwarded-with-process-icon (a filled dot) while the app runs; the row's aria-label holds localhost:8050 (take08, 2026-10-07). Measured after Claude stops the app.</sub>

**p5.16f** · scroll Claude's reply · *live*

> Claude also points out that nothing is committed yet. The dashboard, its notes, and the CLAUDE.md changes exist only in this codespace, until we save them to GitHub.

<sub>Spoken: Claude also points out that nothing is committed yet. The dashboard, its notes, and the Claude dot M D changes exist only in this code space, until we save them to GitHub.</sub>

- draw rect on *committed*

Must cover, if it happens:

- Read Claude's final report: it lists the new files (doc's run: app.py and assets/style.css).
- And side effects, such as a package it installed along the way. The report is where you learn about them.

## Part 6: Save your work to GitHub (doc steps 17 to 20)

Voiced about 1:40.

**p6.17a** · type · approved

> Before we finish, I'll ask Claude to wrap up. I'll enter the wrap-up prompt.

```text
Let's wrap up. Write notes about the dashboard in docs/dashboard.md: what it does, how to start it, where its files are, and any decisions we made. Then add a one-line pointer to that file in CLAUDE.md, so you can find the notes in future sessions.
```

<sub>Typed at natural speed, not pasted (R67): the edit speeds the typing up or cuts its middle, so the line plays over the finished prompt. The description carries every prompt.</sub>

**p6.17b** · no action (the line plays over the picture) · approved

> The prompt asks Claude to write notes about the dashboard in docs/dashboard.md, and to add a one-line pointer to them in CLAUDE.md. That's our first standing rule at work.

<sub>Spoken: The prompt asks Claude to write notes about the dashboard in docs slash dashboard dot M D, and to add a one-line pointer to them in Claude dot M D. That's our first standing rule at work.</sub>

- draw rect on *docs/dashboard.md*
- draw rect on *one-line*

**p6.17c** · no action (the line plays over the picture) · approved

> End every working session this way. Claude starts each session with no memory of the last one. It reads CLAUDE.md first, and the pointer leads it to the notes.

<sub>Spoken: End every working session this way. Claude starts each session with no memory of the last one. It reads Claude dot M D first, and the pointer leads it to the notes.</sub>

**p6.17d** · click `button[aria-label="Send message"]` · approved

> I'll click the send arrow.

<sub>Send arrow confirmed in take06 (2026-10-07). The busy panel shows 'Queue another message'.</sub>

**p6.18** · wait for Claude · *live*

> Claude writes the notes to docs/dashboard.md, and points to them from CLAUDE.md with one line. In this case, it had already written a shorter notes file during the build, so it replaced that one, to keep a single copy.

<sub>Spoken: Claude writes the notes to docs slash dashboard dot M D, and points to them from Claude dot M D with one line. In this case, it had already written a shorter notes file during the build, so it replaced that one, to keep a single copy.</sub>

- draw rect on *points*

Must cover, if it happens:

- Claude wrote the notes to docs/dashboard.md and added the one-line pointer to CLAUDE.md (doc step 18).

<sub>Under 20 s expected.</sub>

**p6.19a** · type · approved

> Now let's save our work to GitHub. I'll enter the commit prompt.

```text
Commit all of my changes to the main branch with a short message that describes what we built, and push them to GitHub.
```

<sub>Typed at natural speed, not pasted (R67): the edit speeds the typing up or cuts its middle, so the line plays over the finished prompt. The description carries every prompt.</sub>

**p6.19b** · no action (the line plays over the picture) · approved

> Notice that the prompt names the main branch, which matches our second rule. You can also commit the changes yourself with the Source Control icon on the left edge. I won't do that here, but will instead let Claude handle it.

- labels: *Source Control*
- draw arrow on *Source*
- draw rect on *main*

**p6.19c** · click `button[aria-label="Send message"]` · approved

> I'll click the send arrow.

<sub>Send arrow confirmed in take06 (2026-10-07). The busy panel shows 'Queue another message'.</sub>

**p6.20** · wait for Claude · *live*

> Claude commits the five files to the main branch, and pushes them to GitHub. In the Explorer, the dots and the M are gone: the files are in the repository now. Committing means the dashboard survives even if the codespace is deleted.

<sub>Spoken: Claude commits the five files to the main branch, and pushes them to GitHub. In the Explorer, the dots and the M are gone: the files are in the repository now. Committing means the dashboard survives even if the code space is deleted.</sub>

- draw rect on *dots*

Must cover, if it happens:

- Claude confirms the work is committed and pushed to GitHub (doc step 20).
- The U markers in the Explorer disappear: the files are in the repository now.
- Committing means the dashboard survives even if the codespace is deleted; files that live only in a codespace disappear with it.

<sub>The autopilot's RISKY list holds `git push`; this step allows it (action.allow): the push goes to the take's own repo, the one the codespace was made from.</sub>

## Part 7: Recap

Voiced about 0:44.

**p7.01** · no action (the line plays over the picture) · approved

> We used flight data to teach the mechanics, but the pattern maps directly to your own work. Set the goal, the audience, and the quality bar. Make the decisions that matter, and check the result yourself, because Claude can't see what it built.

<sub>As ep04 does before its recap: the example maps to the viewer's own work.</sub>

**p7.02** · no action (the line plays over the picture) · approved

> Let's recap. We found the flight data and opened Claude Code. We gave Claude two standing rules and a direction prompt, chose Plotly Dash from its options, and let it build. We explored the dashboard and asked Claude to fix a problem only we could see. And we saved our work to GitHub.

<sub>Spoken: Let's recap. We found the flight data and opened Claude Code. We gave Claude two standing rules and a direction prompt, chose Plot-lee Dash from its options, and let it build. We explored the dashboard and asked Claude to fix a problem only we could see. And we saved our work to GitHub.</sub>

- *improvement* variant (R71): Let's recap. We found the flight data and opened Claude Code. We gave Claude two standing rules and a direction prompt, chose Plotly Dash from its options, and let it build. We explored the dashboard, asked Claude for an improvement, and checked the result ourselves. And we saved our work to GitHub.

<sub>Mirrors the roadmap (p0.05). Motion graphics on screen (R69): text slides over a still of the finished dashboard, rendered in Remotion; see remotion/ OpeningRecap. No call to action: this video isn't published (R68).</sub>
