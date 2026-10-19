// AIDV's ExtendScript in Premiere Pro (R102). Loaded by the AIDV panel and the hidden bridge (CSXS/manifest.xml).
// aidvRun(code) is the bridge's entry: it evaluates code and answers JSON {ok, result} or {ok: false, error}.
// The caption titles (aidvCaptionTitles) are added from a job file the export writes (pipeline/edit/ppro/titles.py).

if (typeof JSON !== "object") { JSON = {}; }
(function () {
  // ExtendScript is ES3: no native JSON. A small stringify; parse trusts its input (our own files).
  function q(s) {
    return '"' + s.replace(/[\\"\u0000-\u001f\u2028\u2029]/g, function (c) {
      var m = { "\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t" }[c];
      return m || "\\u" + ("0000" + c.charCodeAt(0).toString(16)).slice(-4);
    }) + '"';
  }
  function str(v) {
    if (v === null || v === undefined) { return "null"; }
    var t = typeof v;
    if (t === "number") { return isFinite(v) ? String(v) : "null"; }
    if (t === "boolean") { return String(v); }
    if (t === "string") { return q(v); }
    if (t === "function") { return "null"; }
    var out = [], k;
    if (v instanceof Array) {
      for (k = 0; k < v.length; k++) { out.push(str(v[k])); }
      return "[" + out.join(",") + "]";
    }
    for (k in v) {
      if (v.hasOwnProperty(k) && typeof v[k] !== "function") { out.push(q(k) + ":" + str(v[k])); }
    }
    return "{" + out.join(",") + "}";
  }
  if (typeof JSON.stringify !== "function") { JSON.stringify = function (v) { return str(v); }; }
  if (typeof JSON.parse !== "function") { JSON.parse = function (s) { return eval("(" + s + ")"); }; }
})();

function aidvRun(code) {
  try {
    return JSON.stringify({ ok: true, result: eval(code) });
  } catch (e) {
    return JSON.stringify({ ok: false, error: String(e), line: e.line });
  }
}

function aidvReadText(path) {
  var f = new File(path);
  f.encoding = "UTF-8";
  if (!f.open("r")) { throw new Error("can't open " + path); }
  var s = f.read();
  f.close();
  return s;
}

var AIDV_TPS = 254016000000;          // Premiere's ticks per second

function aidvFindSequence(name) {
  for (var i = 0; i < app.project.sequences.numSequences; i++) {
    if (app.project.sequences[i].name === name) { return app.project.sequences[i]; }
  }
  return null;
}

// R102: one editable title per caption cue. job is caption_titles.json (pipeline/edit/ppro/titles.py): each cue's
// .mogrt already holds its text, look and place, so this only adds them on the job's track and sets their lengths.
// importMGT overwrites (no ripple) and gives each title the template's 4.9 s, so the cues go in time order, each
// trimmed before the next. In Premiere 26.3 importMGT returns null: the new title is found by its start.
function aidvCaptionTitles(job, seq) {
  seq = seq || aidvFindSequence(job.sequence);
  if (!seq) { throw new Error("no sequence named \"" + job.sequence + "\" in this project"); }
  app.project.openSequence(seq.sequenceID);
  var vi = -1, i, j;
  for (i = 0; i < seq.videoTracks.numTracks; i++) {
    if (seq.videoTracks[i].name === job.track) { vi = i; }
  }
  if (vi < 0) { throw new Error("\"" + seq.name + "\" has no track named \"" + job.track + "\""); }
  var tr = seq.videoTracks[vi];
  if (tr.clips.numItems) {
    throw new Error("\"" + job.track + "\" already holds " + tr.clips.numItems + " clips: delete them first");
  }
  var tpf = AIDV_TPS / job.fps, added = 0, missing = [];
  function at(t0) {
    for (var j = tr.clips.numItems - 1; j >= 0; j--) {
      if (Math.abs(Number(tr.clips[j].start.ticks) - t0) < tpf / 2) { return tr.clips[j]; }
    }
    return null;
  }
  // importMGT now and then places nothing and says nothing (1 cue in 22 runs' worth, 2026-10-13, right after the XML
  // import): look again after a pause, then insert once more, before calling a cue missing.
  var retried = [];
  for (i = 0; i < job.cues.length; i++) {
    var c = job.cues[i], t0 = Math.round(c.start_frame * tpf), it = null, k;
    for (k = 0; k < 3 && !it; k++) {
      if (k) { retried.push(i); }
      seq.importMGT(c.mogrt, String(t0), vi, 0);
      for (j = 0; j < 8 && !it; j++) {
        it = at(t0);
        if (!it) { $.sleep(250); }
      }
    }
    if (!it) { missing.push(i); continue; }
    var e = new Time();
    e.ticks = String(Math.round(c.end_frame * tpf));
    it.end = e;
    added++;
  }
  if (tr.clips.numItems !== added) { missing.push("track holds " + tr.clips.numItems + " clips, " + added + " placed"); }
  return { added: added, missing: missing, retried: retried, sequence: seq.name, track: job.track };
}

// The AIDV panel's button: pick an export folder's caption_titles.json.
function aidvCaptionTitlesDialog() {
  var f = File.openDialog("The export folder's caption_titles.json", "*.json");
  if (!f) { return { message: "Cancelled." }; }
  var job = JSON.parse(aidvReadText(f.fsName));
  var r = aidvCaptionTitles(job, aidvFindSequence(job.sequence) || app.project.activeSequence);
  r.message = "Added " + r.added + " caption titles to \"" + r.sequence + "\" (" + r.track + ")." +
              (r.missing.length ? " Not placed: cues " + r.missing.join(", ") + "." : "");
  return r;
}

// Bins for what an XML import leaves flat in the root (David, 2026-10-13: "the project is quite flat"). bins:
// {sequences: <bin>, media: [{bin, match}]}, match a regex on the item's media path; the first match wins.
function aidvOrganize(p, bins) {
  var root = p.rootItem, made = {}, items = [], moved = 0, left = [], i, k;
  function bin(name) {
    if (!made[name]) {
      for (var j = 0; j < root.children.numItems; j++) {
        var c = root.children[j];
        if (c.type === ProjectItemType.BIN && c.name === name) { made[name] = c; }
      }
      if (!made[name]) { root.createBin(name); return bin(name); }
    }
    return made[name];
  }
  for (i = 0; i < root.children.numItems; i++) { items.push(root.children[i]); }   // moving changes the indices
  for (i = 0; i < items.length; i++) {
    var it = items[i], target = null;
    if (it.type === ProjectItemType.BIN) { continue; }
    if (it.isSequence()) {
      target = bins.sequences;
    } else {
      var path = it.getMediaPath() || "";
      for (k = 0; k < bins.media.length && !target; k++) {
        if (new RegExp(bins.media[k].match, "i").test(path)) { target = bins.media[k].bin; }
      }
    }
    if (target) { it.moveBin(bin(target)); moved++; } else { left.push(it.name); }
  }
  return { moved: moved, left_in_root: left };
}

// R105: work-cut transitions placed in Premiere, at a cut between two clips of a sequence's video track. job is the
// export's transitions.json: {fps, replace, transitions: [{sequence, track, cut_frame, frames, type, align}]}; with
// replace, a transition already on the cut is removed first (else the cut is reported, untouched). QE's addTransition on the outgoing
// clip (addToStart false) with alignment 0 starts the transition at the cut, running on that clip's handle (checked
// 2026-10-13: the new Page Peel, AE.AE_Impact_Page_Peel, 1.0 s at a 25.0 s cut came back as 25.0 to 26.0). Each one
// is read back from the DOM; a transition that isn't there, or isn't where it should be, is reported.
// The transition named exactly so: Premiere 26 lists "Page Peel" and "Page Peel (Obsolete)", and by-name lookup is
// documented nowhere (the premiere-pro-mcp project found it empty on some builds), so the list is scanned first.
function aidvTransitionNamed(name) {
  var l = qe.project.getVideoTransitionList();
  for (var i = 0; l && i < l.length; i++) {
    if (l[i] && l[i].name === name) { return l[i]; }
  }
  return qe.project.getVideoTransitionByName(name);
}

// Removes the transitions on a sequence's video track that touch the given cuts (seconds), or all of them when cuts
// is null: QE's getTransitionAt(i) counts every item of the track (clips, gaps, transitions alike, and some indices
// throw), so each index is tried and only a "Transition" is removed; remove() with no arguments leaves the clips as
// they were (checked 2026-10-13: a Page Peel at 25.0 s removed, both clips still 13.967-25.000 and 25.000-36.767).
function aidvRemoveTransitions(seq, track, cuts, fps) {
  app.project.openSequence(seq.sequenceID);
  app.enableQE();
  var qt = qe.project.getActiveSequence().getVideoTrackAt(track), removed = [], i, k;
  for (i = qt.numItems - 1; i >= 0; i--) {
    var tr = null;
    try { tr = qt.getTransitionAt(i); if (String(tr.type) !== "Transition") { tr = null; } } catch (e) { tr = null; }
    if (!tr) { continue; }
    var a = tr.start.secs, b = tr.end.secs, hit = !cuts;
    for (k = 0; cuts && k < cuts.length; k++) {
      if (cuts[k] > a - 0.5 / fps && cuts[k] < b + 0.5 / fps) { hit = true; }
    }
    if (hit && tr.remove()) { removed.push([a, b]); }
  }
  return removed;
}

function aidvTransitions(job) {
  app.enableQE();
  var placed = [], failed = [], fps = job.fps, i, k;
  function tc(f) {
    var s = Math.floor(f / fps), ff = f % fps;
    function two(n) { return (n < 10 ? "0" : "") + n; }
    return two(Math.floor(s / 3600)) + ":" + two(Math.floor(s / 60) % 60) + ":" + two(s % 60) + ":" + two(ff);
  }
  for (i = 0; i < job.transitions.length; i++) {
    var t = job.transitions[i], seq = aidvFindSequence(t.sequence), cut = t.cut_frame / fps;
    if (!seq) { failed.push({ cut_s: cut, why: "no sequence named " + t.sequence }); continue; }
    app.project.openSequence(seq.sequenceID);
    var qt = qe.project.getActiveSequence().getVideoTrackAt(t.track), out = null;
    for (k = 0; k < qt.numItems; k++) {
      var it = qt.getItemAt(k);
      if (it.type === "Clip" && Math.abs(it.end.secs - cut) < 0.5 / fps) { out = it; }
    }
    var fx = aidvTransitionNamed(t.type);
    if (!out || !fx) { failed.push({ cut_s: cut, why: !out ? "no clip ends at the cut" : "no transition " + t.type }); continue; }
    if (job.replace) { aidvRemoveTransitions(seq, t.track, [cut], fps); app.project.openSequence(seq.sequenceID); }
    var n0 = seq.videoTracks[t.track].transitions.numItems;   // QE won't put a second one on a cut, silently
    out.addTransition(fx, false, tc(t.frames), "00:00:00:00", { start: 0, centre: 0.5, end: 1 }[t.align] || 0,
                      false, true);
    var dom = seq.videoTracks[t.track].transitions, got = null;
    if (dom.numItems !== n0 + 1) { failed.push({ cut_s: cut, why: "none added (the cut may hold one already)" }); continue; }
    for (k = 0; k < dom.numItems; k++) {
      if (Math.abs(dom[k].start.seconds - cut) < 0.5 / fps || Math.abs(dom[k].end.seconds - cut) < 0.5 / fps) { got = dom[k]; }
    }
    if (got && got.name === t.type) {
      placed.push({ cut_s: cut, start: got.start.seconds, end: got.end.seconds, match: got.matchName });
    } else {
      failed.push({ cut_s: cut, why: got ? "came in as " + got.name : "not placed" });
    }
  }
  return { placed: placed, failed: failed };
}

// Unattended (pipeline.edit.ppro.project): a new project in the export folder with the full XML imported, its items
// in bins, the caption titles added and the project saved, for David to open.
function aidvBuildProject(xml, prproj, jobPath, bins) {
  // Only into an empty Premiere: every later call works on app.project, and a round's sequence names repeat the last
  // round's, so with David's project open the titles could land in his (Fable's review, 2026-10-13).
  if (app.projects.numProjects > 0) {
    throw new Error("a project is open in Premiere (" + app.projects[0].path + "); the build runs only with none open");
  }
  if (!app.newProject(prproj)) { throw new Error("Premiere wouldn't create " + prproj); }
  var p = app.project;
  if (p.path !== prproj) {
    for (var k = 0; k < app.projects.numProjects; k++) {
      if (app.projects[k].path === prproj) { p = app.projects[k]; }
    }
  }
  if (p.path !== prproj) { throw new Error("the new project isn't open: " + p.path); }
  var before = p.sequences.numSequences;       // importFiles' return value proves little; count what came in
  p.importFiles([xml], true, p.rootItem, false);
  if (p.sequences.numSequences <= before) { throw new Error("the import brought no sequences: " + xml); }
  var r = aidvCaptionTitles(JSON.parse(aidvReadText(jobPath)));
  if (bins) { r.bins = aidvOrganize(p, bins); }
  p.save();
  r.project = p.path;
  return r;
}

// The final sequence (pipeline/edit/ppro/final.py; R195, R203): in a copy of the approved review project, the XML's
// "<run> final" (the avatar intro, a gap, the outro, the logo outro) gets the approved sequence put into the gap as a
// nested clip. Its source out point is set first, job.nest_tail_frames before its end, so the overwrite stops where
// the outro starts and those frames are the handle the dissolve into the outro runs on. Then the dissolves
// (aidvTransitions), the avatar's caption titles (aidvCaptionTitles), the check markers and the bins. Only into an
// empty Premiere (R104); it saves and closes the project it opened, and on a failure closes it unsaved.
function aidvFinalSequence(job) {
  if (app.projects.numProjects > 0) {
    throw new Error("a project is open in Premiere (" + app.projects[0].path + "); the build runs only with none open");
  }
  if (!app.openDocument(job.prproj)) { throw new Error("Premiere wouldn't open " + job.prproj); }
  var p = app.project, r = { problems: [] }, saved = false, i;
  try {
    if (p.path !== job.prproj) { throw new Error("the open project is " + p.path + ", not " + job.prproj); }
    var src = aidvFindSequence(job.nest);
    if (!src) { throw new Error("no sequence named \"" + job.nest + "\" in " + job.prproj); }
    var tpf = AIDV_TPS / job.fps, n = Math.round(Number(src.end) / tpf);
    if (n !== job.nest_frames) {               // a frame off would shorten the dissolve into the outro, silently
      throw new Error("\"" + job.nest + "\" is " + n + " frames; its XML says " + job.nest_frames);
    }
    var before = p.sequences.numSequences;
    p.importFiles([job.xml], true, p.rootItem, false);
    var fin = aidvFindSequence(job.sequence);
    if (!fin || p.sequences.numSequences <= before) { throw new Error("the import brought no sequence " + job.sequence); }
    var item = src.projectItem, at = new Time(), outp = new Time();
    at.ticks = String(Math.round(job.nest_at_frame * tpf));
    outp.ticks = String(Math.round((job.nest_frames - job.nest_tail_frames) * tpf));
    item.setInPoint(0, 4);                     // from its first frame, whatever in point it was left with
    item.setOutPoint(outp.seconds, 4);
    fin.videoTracks[0].overwriteClip(item, at);
    item.clearInPoint();
    item.clearOutPoint();
    var v = null, a = null, want = job.nest_at_frame + job.nest_frames - job.nest_tail_frames, c;
    for (i = 0; i < fin.videoTracks[0].clips.numItems; i++) {
      c = fin.videoTracks[0].clips[i];
      if (Math.abs(Number(c.start.ticks) / tpf - job.nest_at_frame) < 0.5) { v = c; }
    }
    if (!v) { throw new Error("the approved sequence wasn't placed at frame " + job.nest_at_frame); }
    r.nest = { start: Math.round(Number(v.start.ticks) / tpf), end: Math.round(Number(v.end.ticks) / tpf),
               in_frame: Math.round(Number(v.inPoint.ticks) / tpf), out_frame: Math.round(Number(v.outPoint.ticks) / tpf),
               want_end: want, name: v.name };
    if (r.nest.end !== want) { r.problems.push("the nested clip ends at frame " + r.nest.end + ", not " + want); }
    for (i = 0; i < fin.audioTracks[0].clips.numItems; i++) {
      c = fin.audioTracks[0].clips[i];
      if (Math.abs(Number(c.start.ticks) / tpf - job.nest_at_frame) < 0.5) { a = c; }
    }
    if (!a) { r.problems.push("no nested sound on A1 at frame " + job.nest_at_frame); }
    r.v1 = [];
    for (i = 0; i < fin.videoTracks[0].clips.numItems; i++) {
      c = fin.videoTracks[0].clips[i];
      r.v1.push([c.name, Math.round(Number(c.start.ticks) / tpf), Math.round(Number(c.end.ticks) / tpf)]);
    }
    r.transitions = aidvTransitions(job.transitions);
    if (r.transitions.failed.length) { r.problems.push("transitions failed: " + r.transitions.failed.length); }
    r.titles = aidvCaptionTitles(job.titles, fin);
    if (r.titles.missing.length) { r.problems.push("titles not placed: " + r.titles.missing.join(", ")); }
    for (i = 0; i < job.markers.length; i++) {
      var m = fin.markers.createMarker(job.markers[i].t);
      m.name = job.markers[i].name;
      m.comments = job.markers[i].comment || "";
    }
    if (job.bins) { r.bins = aidvOrganize(p, job.bins); }
    r.frames = Math.round(Number(fin.end) / tpf);
    p.save();
    saved = true;
    r.project = p.path;
  } finally {
    for (i = app.projects.numProjects - 1; i >= 0; i--) {
      if (app.projects[i].path === job.prproj) { app.projects[i].closeDocument(false, false); }
    }
  }
  r.saved = saved;
  return r;
}

// A clip's Motion set as David's own project has it (R232: QuickArch03's url.mov, Position and Scale), after the XML
// import, which normalises an imported Center by the clip's own media size (GOTCHAS). spec: {track, start_frame,
// position: [x, y] as fractions of the frame (the .prproj's own values), scale: percent}. Premiere 26 gives Position
// as fractions; were it pixels (a value over 2), it is set in pixels. Returns the values before and after.
function aidvClipMotion(seq, spec, fps) {
  var tpf = AIDV_TPS / fps, tr = null, c = null, mo = null, pos = null, sc = null, i;
  for (i = 0; i < seq.videoTracks.numTracks; i++) {
    if (seq.videoTracks[i].name === spec.track) { tr = seq.videoTracks[i]; }
  }
  if (!tr) { throw new Error(seq.name + ": no track " + spec.track); }
  for (i = 0; i < tr.clips.numItems; i++) {
    if (Math.abs(Number(tr.clips[i].start.ticks) / tpf - spec.start_frame) < 0.5) { c = tr.clips[i]; }
  }
  if (!c) { throw new Error(seq.name + ": no clip at frame " + spec.start_frame + " on " + spec.track); }
  for (i = 0; i < c.components.numItems; i++) {
    if (c.components[i].displayName === "Motion") { mo = c.components[i]; }
  }
  if (!mo) { throw new Error(c.name + " has no Motion"); }
  for (i = 0; i < mo.properties.numItems; i++) {
    if (mo.properties[i].displayName === "Position") { pos = mo.properties[i]; }
    if (mo.properties[i].displayName === "Scale") { sc = mo.properties[i]; }
  }
  if (!pos || !sc) { throw new Error(c.name + ": its Motion has no Position or Scale"); }
  var before = { position: pos.getValue(), scale: sc.getValue() };
  var px = before.position[0] > 2;
  pos.setValue(px ? [spec.position[0] * seq.frameSizeHorizontal, spec.position[1] * seq.frameSizeVertical]
                  : [spec.position[0], spec.position[1]], true);
  sc.setValue(spec.scale, true);
  return { clip: c.name, before: before, after: { position: pos.getValue(), scale: sc.getValue() }, pixels: px };
}

// The avatar stage's review project (pipeline/edit/stage.py; R205 to R209): in a copy of the approved review project,
// each of the XML's short sequences gets a stretch of the approved sequence nested on V1: the job's source in and out
// frames, overwritten at its frame (the stage clip on V2 sits above it). Then each sequence's markers and the bins.
// Only into an empty Premiere (R104); it saves and closes the project it opened, and on a failure closes it unsaved.
function aidvStageReview(job) {
  if (app.projects.numProjects > 0) {
    throw new Error("a project is open in Premiere (" + app.projects[0].path + "); the build runs only with none open");
  }
  if (!app.openDocument(job.prproj)) { throw new Error("Premiere wouldn't open " + job.prproj); }
  var p = app.project, r = { problems: [], placed: [] }, saved = false, i, k;
  try {
    if (p.path !== job.prproj) { throw new Error("the open project is " + p.path + ", not " + job.prproj); }
    var src = aidvFindSequence(job.nest);
    if (!src) { throw new Error("no sequence named \"" + job.nest + "\" in " + job.prproj); }
    var tpf = AIDV_TPS / job.fps, n = Math.round(Number(src.end) / tpf);
    if (n !== job.nest_frames) { throw new Error("\"" + job.nest + "\" is " + n + " frames; its XML says " + job.nest_frames); }
    var before = p.sequences.numSequences;
    p.importFiles([job.xml], true, p.rootItem, false);
    if (p.sequences.numSequences <= before) { throw new Error("the import brought no sequences: " + job.xml); }
    var item = src.projectItem;
    for (k = 0; k < job.sequences.length; k++) {
      var s = job.sequences[k], seq = aidvFindSequence(s.name);
      if (!seq) { r.problems.push("no sequence " + s.name); continue; }
      var at = new Time(), tin = new Time(), tout = new Time();
      at.ticks = String(Math.round(s.at_frame * tpf));
      tin.ticks = String(Math.round(s.in_frame * tpf));
      tout.ticks = String(Math.round(s.out_frame * tpf));
      if (seq.videoTracks.numTracks < 3 || seq.videoTracks[0].clips.numItems > (s.v1_clips || 0)) {
        throw new Error(s.name + ": its V1 isn't the empty track the XML left for the approved sequence");
      }
      var v2n = seq.videoTracks[1].clips.numItems;
      item.setInPoint(tin.seconds, 4);
      item.setOutPoint(tout.seconds, 4);
      seq.videoTracks[0].overwriteClip(item, at);
      if (seq.videoTracks[1].clips.numItems !== v2n) { r.problems.push(s.name + ": the overwrite changed V2, the stage"); }
      item.clearInPoint();
      item.clearOutPoint();
      var c = null, a = null, ci;
      for (i = 0; i < seq.videoTracks[0].clips.numItems; i++) {
        ci = seq.videoTracks[0].clips[i];
        if (Math.abs(Number(ci.start.ticks) / tpf - s.at_frame) < 0.5) { c = ci; }
      }
      for (i = 0; i < seq.audioTracks[0].clips.numItems; i++) {
        ci = seq.audioTracks[0].clips[i];
        if (Math.abs(Number(ci.start.ticks) / tpf - s.at_frame) < 0.5) { a = ci; }
      }
      if (!c) { r.problems.push(s.name + ": the approved sequence wasn't placed at frame " + s.at_frame); continue; }
      if (!a) { r.problems.push(s.name + ": no nested sound on A1 at frame " + s.at_frame); }
      var got = { sequence: s.name, start: Math.round(Number(c.start.ticks) / tpf), end: Math.round(Number(c.end.ticks) / tpf),
                  in_frame: Math.round(Number(c.inPoint.ticks) / tpf) };
      if (got.end - got.start !== s.out_frame - s.in_frame || got.in_frame !== s.in_frame) {
        r.problems.push(s.name + ": placed frames " + got.start + "-" + got.end + " from " + got.in_frame +
                        ", wanted " + s.at_frame + " for " + (s.out_frame - s.in_frame) + " from " + s.in_frame);
      }
      r.placed.push(got);
      for (i = 0; i < (s.motion || []).length; i++) {       // clips placed as David's own project has them (R232)
        r.motion = r.motion || [];
        var mr = aidvClipMotion(seq, s.motion[i], job.fps);
        r.motion.push(mr);
        var want = s.motion[i], gotp = mr.after.position, gs = mr.after.scale;
        if (mr.before.scale !== 100) {         // Premiere's Default Media Scaling resized it on import: 45% would then
          r.problems.push(s.name + ": " + mr.clip + " came in at Scale " + mr.before.scale + ", not 100");   // be off
        }
        if (Math.abs(gs - want.scale) > 0.01 || (!mr.pixels && (Math.abs(gotp[0] - want.position[0]) > 1e-4 ||
            Math.abs(gotp[1] - want.position[1]) > 1e-4))) {
          r.problems.push(s.name + ": " + mr.clip + "'s Motion reads back " + gotp + " / " + gs);
        }
      }
      for (i = 0; i < (s.markers || []).length; i++) {
        var m = seq.markers.createMarker(s.markers[i].t);
        m.name = s.markers[i].name;
        m.comments = s.markers[i].comment || "";
      }
      if (s.titles && s.titles.cues.length) {          // the captions on their track above the avatar (R102)
        var tt = aidvCaptionTitles(s.titles, seq);
        r.titles = r.titles || [];
        r.titles.push({ sequence: s.name, added: tt.added, missing: tt.missing, retried: tt.retried });
        if (tt.missing.length) { r.problems.push(s.name + ": caption titles not placed: " + tt.missing.join(", ")); }
      }
    }
    if (job.bins) { r.bins = aidvOrganize(p, job.bins); }
    p.save();
    saved = true;
    r.project = p.path;
  } finally {
    for (i = app.projects.numProjects - 1; i >= 0; i--) {
      if (app.projects[i].path === job.prproj) { app.projects[i].closeDocument(false, false); }
    }
  }
  r.saved = saved;
  return r;
}
