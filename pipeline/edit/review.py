"""The review page (S5; R55, R56): the proxy, the edit laid out by video time, notes by time, privacy decisions.

    python -m pipeline.edit.review runs/<run_id> [--no-render]

Renders the 540p proxy of the current edit_plan.json (unless --no-render and it is already there), pulls a thumbnail
per narration line, and writes runs/<run_id>/timeline.html. Open it in Edge from the run folder.

On the page:
  lanes      picture (clips, freezes, cuts), narration, captions, zoom, marks, privacy findings; click to seek
  steps      one row per line: thumbnail, time, the line, its warnings
  phone      the proxy at phone width, for legibility (R42, R60)
  notes      add a note at the playhead; "Copy notes for Claude" puts them on the clipboard by video time (R55)
  privacy    mark each finding blur, ignore or retake; "Copy decisions" gives privacy_decisions.json (R56)
  approval   the plan's fingerprint and whether this exact plan is approved (pipeline.edit.final)
The page writes no files: notes and choices live in the browser until copied.
"""
import hashlib
import html
import json
import subprocess
import sys
from pathlib import Path

from pipeline.config import ROOT, tool
from pipeline.edit.camera import cam_at
from pipeline.narration import timing

CACHE = ROOT / "audio_cache"


def plan_sha(run_dir):
    return hashlib.sha256((Path(run_dir) / "edit_plan.json").read_bytes()).hexdigest()


def proxy_path(run_dir, plan):
    tag = Path(plan["steps_file"]).stem.removeprefix("steps_")
    return Path(run_dir) / f"proxy_{tag}_{plan['gap_treatment']}.mp4"


def lanes(plan, report):
    T = plan["duration_s"]
    pct = lambda t: round(100 * max(0.0, min(t, T)) / T, 3)
    span = lambda a, b, cls, title: {"l": pct(a), "w": max(0.15, pct(b) - pct(a)), "cls": cls, "title": title, "t": a}
    pic = []
    for k, s in enumerate(plan["segments"]):
        end = s["t"] + s["dur"]
        if s["type"] == "hold":
            pic.append(span(s["t"], end, "hold", f"freeze {s['dur']:.2f}s at {s['t']:.2f}s"))
        else:
            pic.append(span(s["t"], end, "clip", f"footage {s['t']:.2f}-{end:.2f}s (source {s['src_in']:.1f}-{s['src_out']:.1f}s)"))
            if k and s.get("transition_in") == "cut":
                pic.append(span(s["t"] - 0.05, s["t"] + 0.05, "cut", f"cut at {s['t']:.2f}s"))
    nar = []
    for n in plan["narration"]:
        for p in n.get("parts") or [{"at": n["start"], "in": 0, "out": n["length"]}]:
            nar.append(span(p["at"], p["at"] + p["out"] - p["in"], "line", f"{n['line_id']} {p['at']:.2f}s"))
    caps = [span(c["start"], c["end"], "cue" + (" off" if (c.get("pos") or {}).get("where", "bottom-centre")
                                                 != "bottom-centre" else ""),
                 f"{c['start']:.2f}s {(c.get('pos') or {}).get('where', '')}: {c['text']}") for c in plan["captions"]["cues"]]
    zoom, t = [], 0.0
    W, H = plan["width"], plan["height"]
    while t < T:                                           # zoom level in 0.25 s steps, merged
        s = cam_at(plan.get("camera") or [], t, W, H)[0]
        lvl = "z2" if s > 1.6 else "z1" if s > 1.02 else None
        if lvl and zoom and zoom[-1]["cls"] == lvl and abs(zoom[-1]["_end"] - t) < 1e-6:
            zoom[-1]["_end"] = t + 0.25
        elif lvl:
            zoom.append({**span(t, t + 0.25, lvl, ""), "_end": t + 0.25})
        t += 0.25
    for z in zoom:
        z.update(span(z["t"], z.pop("_end"), z["cls"], f"zoom {'tight (up to 2x)' if z['cls'] == 'z2' else 'rest 1.35x'} "
                                                       f"from {z['t']:.2f}s"))
    marks = [span(m["draw0"], m["fade1"], "mark " + m["style"], f"{m['kind']} ({m['style']}) {m['step']} {m['draw0']:.2f}s")
             for m in plan.get("marks", {}).get("layers", [])]
    priv = [span(f["t0"], f["t1"], "priv " + f["decision"], f"{f['pattern']}, {f['where']} ({f['decision']})")
            for f in (report or {}).get("findings", [])]
    return [("Picture", pic), ("Narration", nar), ("Captions", caps), ("Zoom", zoom), ("Marks", marks),
            ("Privacy", priv)]


def thumbs(run_dir, plan, proxy):
    out = Path(run_dir) / "review" / "thumbs"
    out.mkdir(parents=True, exist_ok=True)
    res = {}
    for n in plan["narration"]:
        t = n.get("cue_at") or n["start"] + 0.5
        jpg = out / f"{n['line_id']}.jpg"
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(proxy), "-frames:v", "1",
                        "-vf", "scale=320:-2", str(jpg)], check=True)
        res[n["line_id"]] = f"review/thumbs/{jpg.name}"
    return res


def build(run_dir, render=True):
    run_dir = Path(run_dir).resolve()
    plan = json.loads((run_dir / "edit_plan.json").read_text(encoding="utf-8"))
    proxy = proxy_path(run_dir, plan)
    sha = plan_sha(run_dir)
    stamp = run_dir / "review" / "proxy_plan.sha"
    if render and not (proxy.exists() and stamp.exists() and stamp.read_text().strip() == sha):
        from pipeline.edit.s3 import render_proxy
        render_proxy(run_dir, plan["gap_treatment"], Path(plan["steps_file"]).stem.removeprefix("steps_"))
        stamp.parent.mkdir(exist_ok=True)
        stamp.write_text(sha)
    if not proxy.exists():
        raise SystemExit(f"no proxy at {proxy}; run without --no-render")
    stale = not (stamp.exists() and stamp.read_text().strip() == sha)
    rp = run_dir / "privacy_report.json"
    report = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else None
    ap = run_dir / "approval.json"
    approval = json.loads(ap.read_text(encoding="utf-8")) if ap.exists() else None
    approved = bool(approval and approval.get("plan_sha256") == sha)
    th = thumbs(run_dir, plan, proxy)
    steps = []
    for n in plan["narration"]:
        meta = timing.of(n)
        warn = [w for w in plan["warnings"] if n["step"] in w]
        steps.append({"id": n["step"], "line": n["line_id"], "t": n["start"], "text": meta["display_text"],
                      "thumb": th[n["line_id"]], "warn": warn,
                      "beats": len(n.get("beats", []))})
    data = {"run": plan["run_id"], "duration": plan["duration_s"], "proxy": proxy.name, "sha": sha[:12],
            "stale_proxy": stale, "approved": approved, "approval": approval, "lanes": lanes(plan, report),
            "steps": steps, "warnings": plan["warnings"], "findings": (report or {}).get("findings", []),
            "privacy_samples": (report or {}).get("samples"), "has_report": report is not None}
    page = TEMPLATE.replace("__TITLE__", html.escape(f"Review {plan['run_id']}")).replace(
        "__DATA__", json.dumps(data).replace("</", "<\\/"))
    out = run_dir / "timeline.html"
    out.write_text(page, encoding="utf-8")
    return out, data


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f6f4;--panel:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--accent:#F16F05;--clip:#8fb3d9;
--hold:#d9a441;--cut:#c0392b;--cue:#7a9e7e;--off:#3f7f6a;--z1:#b7a6d9;--z2:#7d5fc4;--mark:#F16F05;--priv:#c0392b;
--ok:#2e7d32}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--panel:#1f1f1d;--ink:#ecebe6;
--muted:#a3a29b;--line:#34332f;--clip:#4f7aa8;--hold:#b5852a;--cue:#5f8763;--off:#4fa585;--z1:#6f5fa0;--z2:#9b7fe6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,Segoe UI,sans-serif}
header{padding:14px 16px;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:8px 18px;align-items:baseline}
h1{font-size:18px;margin:0}h2{font-size:15px;margin:0 0 8px}.muted{color:var(--muted)}.pill{padding:2px 8px;border-radius:99px;
font-size:12px;border:1px solid var(--line)}.pill.ok{background:var(--ok);color:#fff;border:0}.pill.warn{background:var(--cut);color:#fff;border:0}
main{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px;padding:16px;max-width:1500px;margin:auto}
@media (max-width:980px){main{grid-template-columns:1fr}}
section{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px}
.player{display:flex;justify-content:center;background:#000;border-radius:6px}video{width:100%;display:block}
.phone .player{background:var(--bg)}.phone video{width:390px;max-width:100%;border:10px solid #111;border-radius:28px}
.lanes{margin-top:10px}.lane{display:grid;grid-template-columns:84px 1fr;align-items:center;gap:8px;margin:4px 0}
.track{position:relative;height:18px;background:var(--bg);border-radius:3px;cursor:pointer}
.track div{position:absolute;top:2px;bottom:2px;border-radius:2px}.clip{background:var(--clip)}.hold{background:var(--hold)}
.cut{background:var(--cut);top:0!important;bottom:0!important}.line{background:var(--accent);opacity:.75}.cue{background:var(--cue)}
.cue.off{background:var(--off);outline:2px solid var(--ink)}.z1{background:var(--z1)}.z2{background:var(--z2)}
.mark{background:var(--mark);opacity:.6}.mark.fade{opacity:.9;outline:1px dashed var(--ink)}.mark.dim{opacity:.35}.priv{background:var(--priv)}
.priv.ignore{opacity:.35}.head{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink);pointer-events:none}
.steps{display:grid;gap:8px;margin-top:12px}.step{display:grid;grid-template-columns:160px 1fr;gap:10px;align-items:start;
cursor:pointer;padding:6px;border-radius:6px}.step:hover{background:var(--bg)}.step img{width:160px;border-radius:4px;display:block}
.t{font-variant-numeric:tabular-nums;color:var(--muted);font-size:13px}.warn{color:var(--cut);font-size:13px}
textarea{width:100%;min-height:60px;font:inherit;padding:6px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
button,select{font:inherit;padding:5px 10px;border-radius:6px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer}
button.primary{background:var(--accent);color:#fff;border:0}.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
ul{padding-left:18px;margin:6px 0}li{margin:3px 0}.note button{padding:0 6px;margin-left:6px}
.finding{display:grid;grid-template-columns:110px 1fr;gap:8px;margin:8px 0}.finding img{width:110px;border-radius:4px}
aside section{margin-bottom:16px}code{font-size:12px}
</style></head><body>
<header><h1 id="title"></h1><span class="muted" id="meta"></span><span id="status"></span>
<label><input type="checkbox" id="phone"> Phone view</label></header>
<main><div>
<section><div class="player"><video id="v" controls preload="auto"></video></div>
<div class="lanes" id="lanes"></div></section>
<section style="margin-top:16px"><h2>Steps</h2><div class="steps" id="steps"></div></section>
</div><aside>
<section><h2>Notes by video time</h2><textarea id="note" placeholder="What should change here?"></textarea>
<div class="row"><button class="primary" id="add">Add at playhead</button><button id="copy">Copy notes for Claude</button></div>
<ul id="notes"></ul></section>
<section><h2>Privacy</h2><div id="privacy"></div></section>
<section><h2>Warnings</h2><ul id="warnings"></ul></section>
<section><h2>Approval</h2><div id="approval"></div></section>
</aside></main>
<script>
const D = __DATA__;
const $ = (id) => document.getElementById(id);
const fmt = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;
const v = $('v'); v.src = D.proxy;
$('title').textContent = D.run;
$('meta').textContent = `${fmt(D.duration)} · plan ${D.sha}`;
$('status').innerHTML = (D.stale_proxy ? '<span class="pill warn">proxy older than the plan</span> ' : '') +
  (D.approved ? '<span class="pill ok">approved</span>' : '<span class="pill">not approved</span>');
const store = (() => { try { return window.localStorage; } catch (e) { return null; } })();
const key = `review:${D.run}:${D.sha}`;
const load = (k, d) => { try { return JSON.parse(store.getItem(k)) ?? d; } catch (e) { return d; } };
const save = (k, x) => { try { store.setItem(k, JSON.stringify(x)); } catch (e) {} };
$('phone').onchange = (e) => document.body.classList.toggle('phone', e.target.checked);
const heads = [];
for (const [name, items] of D.lanes) {
  const lane = document.createElement('div'); lane.className = 'lane';
  lane.innerHTML = `<span class="t">${name}</span>`;
  const tr = document.createElement('div'); tr.className = 'track';
  for (const it of items) { const d = document.createElement('div'); d.className = it.cls;
    d.style.left = it.l + '%'; d.style.width = it.w + '%'; d.title = it.title; tr.appendChild(d); }
  const h = document.createElement('div'); h.className = 'head'; tr.appendChild(h); heads.push(h);
  tr.onclick = (e) => { const r = tr.getBoundingClientRect(); v.currentTime = (e.clientX - r.left) / r.width * D.duration; };
  lane.appendChild(tr); $('lanes').appendChild(lane);
}
v.ontimeupdate = () => heads.forEach((h) => h.style.left = (100 * v.currentTime / D.duration) + '%');
for (const s of D.steps) {
  const el = document.createElement('div'); el.className = 'step';
  el.innerHTML = `<img src="${s.thumb}" alt=""><div><div class="t">${fmt(s.t)} · ${s.id}${s.beats ? ` · ${s.beats} beat(s)` : ''}</div>
    <div class="txt"></div>${s.warn.map((w) => `<div class="warn"></div>`).join('')}</div>`;
  el.querySelector('.txt').textContent = s.text;
  el.querySelectorAll('.warn').forEach((w, i) => w.textContent = s.warn[i]);
  el.onclick = () => { v.currentTime = s.t; v.play(); };
  $('steps').appendChild(el);
}
let notes = load(key + ':notes', []);
const drawNotes = () => { $('notes').innerHTML = '';
  notes.sort((a, b) => a.t - b.t).forEach((n, i) => { const li = document.createElement('li'); li.className = 'note';
    li.textContent = `${fmt(n.t)} ${n.text}`; const b = document.createElement('button'); b.textContent = '×';
    b.onclick = () => { notes.splice(i, 1); save(key + ':notes', notes); drawNotes(); }; li.appendChild(b);
    li.ondblclick = () => { v.currentTime = n.t; }; $('notes').appendChild(li); }); };
$('add').onclick = () => { const text = $('note').value.trim(); if (!text) return;
  notes.push({t: Math.round(v.currentTime * 10) / 10, text}); $('note').value = ''; save(key + ':notes', notes); drawNotes(); };
$('copy').onclick = () => navigator.clipboard.writeText(
  `Review notes for ${D.run} (plan ${D.sha}):\n` + notes.map((n) => `${fmt(n.t)} ${n.text}`).join('\n'));
drawNotes();
const choices = load(key + ':privacy', {});
if (!D.has_report) $('privacy').innerHTML = '<p class="muted">No report yet: <code>python -m pipeline.privacy.report runs/' + D.run + '</code></p>';
else if (!D.findings.length) $('privacy').innerHTML = `<p class="muted">Nothing found in ${D.privacy_samples} frames of the kept footage.</p>`;
for (const f of D.findings) {
  const el = document.createElement('div'); el.className = 'finding';
  el.innerHTML = `<img src="${f.thumb}" alt=""><div><div class="t">${fmt(f.t0)}–${fmt(f.t1)} · ${f.where}</div><div class="txt"></div>
    <select><option>open</option><option>blur</option><option>ignore</option><option>retake</option></select></div>`;
  el.querySelector('.txt').textContent = `${f.pattern}: ${f.masked}`;
  const sel = el.querySelector('select'); sel.value = choices[f.id] ?? f.decision;
  sel.onchange = () => { choices[f.id] = sel.value; save(key + ':privacy', choices); };
  el.querySelector('img').onclick = () => { v.currentTime = f.t0; };
  $('privacy').appendChild(el);
}
if (D.findings.length) { const b = document.createElement('button'); b.textContent = 'Copy decisions';
  b.onclick = () => { const out = {}; D.findings.forEach((f) => { const c = choices[f.id] ?? f.decision; if (c !== 'open') out[f.id] = c; });
    navigator.clipboard.writeText(JSON.stringify(out, null, 2)); }; $('privacy').appendChild(b); }
$('warnings').innerHTML = D.warnings.length ? '' : '<li class="muted">None</li>';
D.warnings.forEach((w) => { const li = document.createElement('li'); li.textContent = w; $('warnings').appendChild(li); });
$('approval').innerHTML = D.approved
  ? `<p>Approved ${D.approval.approved_at} for plan ${D.sha}. The final render may run.</p>`
  : `<p class="muted">Tell Claude “approve” once this proxy is right. Approval is for this exact plan (${D.sha}); any re-plan needs a new one.</p>`;
</script></body></html>
"""


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    out, data = build(args[0], render="--no-render" not in argv)
    print(f"{out}  ({len(data['steps'])} lines, {len(data['findings'])} privacy finding(s), "
          f"{'approved' if data['approved'] else 'not approved'}{', proxy stale' if data['stale_proxy'] else ''})")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
