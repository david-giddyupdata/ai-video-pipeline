"""A round's frames from Premiere's exports (R233, R240): an H.264 of the whole sequence, the one export made by
default, and a PNG sequence for fidelity only on request (--only=png; R240 dropped it from the round: on round 6 it
took 19 minutes and 6 GB, and a frame that needs fine detail comes from the single-frame export instead), in a scratch
folder that is deleted when the round's checks and reviews are done.

    python -m pipeline.edit.ppro.exports export <built.prproj> [--sequence=<name>]... [--png-fps=N] [--only=h264|png]
                                                # --only: the kind to export (default h264, R240)
    python -m pipeline.edit.ppro.exports frames <built.prproj> <out_dir> <tc_or_s>[,...] [--sequence=<name>]
                                                [--source=h264|png|best]
    python -m pipeline.edit.ppro.exports where <built.prproj>      # the scratch folder and what is in it
    python -m pipeline.edit.ppro.exports clean <built.prproj>|--all # delete the exports (the round is done)
    python -m pipeline.edit.ppro.exports presets                    # write presets/*.epr again from Premiere's own

export: opens the project through the AIDV bridge only when no project is open in Premiere (R104), exports each named
sequence (default: every sequence the project's XML made, or "<run> full") with sequence.exportAsMediaDirect, entire
sequence, with presets/aidv_review_h264.epr (--only=png: with presets/aidv_review_png_<N>fps.epr instead; the
sequence's other kind, when made earlier, is kept), closes the project without saving, and writes exports.json beside
the files; each export is checked whole (the H.264's frame count, the PNGs numbered without a gap, neither showing
Premiere's Media pending card). A project saved since its exports were made (David's edits) makes them stale:
Exports() refuses them, and framecheck --exports makes them again. clean deletes only folders holding exports.json,
and none written to in the last 3 minutes (an export running).

frames: framecheck's contact sheet from the exports, not one Premiere call per frame. source h264 (the default): each
time's exact frame from the H.264; png: the PNG sequence's frame when it holds that exact frame, else one QE
exportFramePNG for it (the single-frame export kept for an exact moment the PNG sequence lacks); best: the PNG
sequence's frame when it holds the exact frame, else the H.264's.

In code: Exports(prproj).seq(name) gives a Seq with frame(t) (an RGB array from the H.264), png(t) (the PNG
sequence's file for that exact frame, or None), nearest_png(t), pull(times, out_dir) and scan(every_s=, start=, end=,
size=), a generator of (frame, seconds, RGB array) over the whole sequence at any rate, for checks that look at every
frame (the picture-in-picture oval against captions and cards).

The PNG sequence's rate: 10 fps (every third frame at 30 fps). Measured on round 6 (docs/SLICE_LOG.md, 2026-10-17):
Premiere's PNG encoder is the slow part (about 8 frames a second on screen recordings, 5.6 on the cityscape, against
the H.264's 37 a second on the main body), and a PNG is about 0.45 MB of screen recording or 1.7 MB of cityscape. So a
17-minute sequence at 10 fps is about 6 GB and 20 minutes of PNG export, at 30 fps about 18 GB and an hour. At 10 fps
every time is within one frame of a PNG (but the last two frames); the H.264, or the single-frame export, has the
exact frame. The PNGs are pixel-identical to the single-frame export; the H.264 is not (0.25 to 0.7 levels on
average, PSNR 47 dB, and Windows OCR reads 2 to 11% of small words differently: "7358b" as "7368b").
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import numpy as np

from pipeline.config import tool
from pipeline.edit.ppro.bridge import call, start

TPS = 254016000000                      # Premiere's ticks per second
PRESETS = Path(__file__).resolve().parent / "presets"
SYSTEM = Path(r"C:\Program Files\Adobe\Adobe Premiere Pro 2026\MediaIO\systempresets")
H264_FROM = SYSTEM / "4E49434B_48323634" / "00 - Match Source - High bitrate.epr"
PNG_FROM = SYSTEM / "3F3F3F3F_504E4720" / "PNG Sequence (Match Source).epr"
H264_PRESET = PRESETS / "aidv_review_h264.epr"
H264_MBPS = (40, 50)                    # VBR 1 pass, target and maximum: small text holds (the system preset's 10/12
KEYFRAME_EVERY = 30                     # blurs it); a key frame a second, so a seek decodes at most a second
PNG_FPS = 10                            # see the docstring
MATCH_NOTHING = ("AAAAAA==", "2374864269")   # ADBEVideoMatchSource off, as 33 of Premiere's own presets write it
SCRATCH = Path("G:/aidv_scratch/exports")    # David's wipeable SD card; else a git-ignored folder in the round
MANIFEST = "exports.json"
BUSY_MARK = "exporting.json"                 # an export running here: its Python process id


# ---------------------------------------------------------------------------------------------------------- presets

def _param(xml, ident, value=None, arb=None):
    """xml with the ExporterParam named ident given a new ParamValue (or ParamArbData and its checksum)."""
    blocks = list(re.finditer(r"<ExporterParam [^>]*>.*?</ExporterParam>", xml, re.S))
    hit = [b for b in blocks if f"<ParamIdentifier>{ident}</ParamIdentifier>" in b.group(0)]
    if len(hit) != 1:
        raise ValueError(f"{ident}: {len(hit)} params of that name in the template")
    b = hit[0].group(0)
    if value is not None:
        new, n = re.subn(r"<ParamValue>[^<]*</ParamValue>", f"<ParamValue>{value}</ParamValue>", b)
    else:
        new, n = re.subn(r'<ParamArbData Encoding="base64" Checksum="\d+">[^<]*</ParamArbData>',
                         f'<ParamArbData Encoding="base64" Checksum="{arb[1]}">{arb[0]}</ParamArbData>', b)
    if n != 1:
        raise ValueError(f"{ident}: no value to set")
    return xml[:hit[0].start()] + new + xml[hit[0].end():]


def _named(xml, name, comment):
    pid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"aidv/{name}"))
    xml = re.sub(r"<PresetID>[^<]*</PresetID>", f"<PresetID>{pid}</PresetID>", xml)
    xml = re.sub(r"<PresetName>[^<]*</PresetName>", f"<PresetName>{name}</PresetName>", xml)
    return re.sub(r"<PresetComments>[^<]*</PresetComments>", f"<PresetComments>{comment}</PresetComments>", xml)


def png_preset(fps):
    return PRESETS / f"aidv_review_png_{fps}fps.epr"


def make_presets(png_fps=(PNG_FPS,)):
    """presets/*.epr from Premiere's own system presets, changed only where named here (what Premiere's Export dialog
    writes when those fields are changed and the preset saved)."""
    PRESETS.mkdir(exist_ok=True)
    x = H264_FROM.read_text(encoding="utf-8")
    x = _param(x, "ADBEVideoTargetBitrate", f"{H264_MBPS[0]}.")
    x = _param(x, "ADBEVideoMaxBitrate", f"{H264_MBPS[1]}.")
    x = _param(x, "ADBEMPEGKeyframeRate", str(KEYFRAME_EVERY))
    x = _named(x, "AIDV review H.264", f"R233: Match Source - High bitrate at VBR 1 pass {H264_MBPS[0]}/{H264_MBPS[1]} "
               f"Mbps, a key frame every {KEYFRAME_EVERY} frames (pipeline.edit.ppro.exports)")
    H264_PRESET.write_text(x, encoding="utf-8")
    made = [H264_PRESET]
    for fps in png_fps:
        if TPS % fps:
            raise ValueError(f"{fps} fps isn't a whole number of Premiere ticks a frame")
        x = PNG_FROM.read_text(encoding="utf-8")
        x = _param(x, "ADBEVideoMatchSource", arb=MATCH_NOTHING)     # else the sequence's own rate wins
        x = _param(x, "ADBEVideoFPS", str(TPS // fps))
        x = _named(x, f"AIDV review PNG {fps} fps", f"R233: PNG Sequence at 1920 x 1080, {fps} fps, no alpha "
                   "(pipeline.edit.ppro.exports)")
        png_preset(fps).write_text(x, encoding="utf-8")
        made.append(png_preset(fps))
    return made


# ---------------------------------------------------------------------------------------------------------- folders

def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60] or "sequence"


def scratch_for(prproj):
    """Where a built project's exports go: G:/aidv_scratch/exports/<run>/<review folder>/<project> when the card is
    in, else <review folder>/_exports/<project> (runs/ is git-ignored). Keyed by the project too: a review folder can
    hold several (overlays_review_r1 holds three)."""
    return _places(prproj)[0]


def _places(prproj):
    """Where a project's exports may be, in order: the card's folder (when the card is in), then the review folder's
    _exports. Exports() reads the first fresh one, so exports made before the card went in or came out are still
    found."""
    prproj = Path(prproj).resolve()
    card = ([SCRATCH / prproj.parent.parent.name / prproj.parent.name / prproj.stem]
            if Path(SCRATCH.anchor).exists() else [])
    return card + [prproj.parent / "_exports" / prproj.stem]


def _stamp(prproj):
    st = Path(prproj).stat()
    return {"mtime": st.st_mtime, "size": st.st_size}


def _size(p):
    p = Path(p)
    return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _write(mf, man):
    tmp = mf.with_suffix(".tmp")
    tmp.write_text(json.dumps(man, indent=1), encoding="utf-8")
    tmp.replace(mf)


# ---------------------------------------------------------------------------------------------------------- export

def _sequences_in(prproj):
    """The sequences the project's own XML made (its <name>.xml beside it), else "<run> full"."""
    import xml.etree.ElementTree as ET
    xml = Path(prproj).with_suffix(".xml")
    if xml.exists():
        root = ET.parse(xml).getroot()
        top = [s.findtext("name") for s in root.findall("./sequence")] or \
              [s.findtext("name") for s in root.findall("./project/children/sequence")]
        if top:
            return top
    return [Path(prproj).stem.removesuffix("_full") + " full"]


def _png_files(d, frames, step):
    """The PNG sequence's files by its index (the digits in each name), checked whole: Premiere writes f000.png on,
    one for every step-th frame of the sequence (floor(frames / step) of them, measured 1708 -> 569, 2171 -> 723,
    28402 -> 9467). A short or gapped sequence (a full card, a stopped export) stops here, rather than every later
    frame being looked up one PNG off."""
    got = {}
    for p in d.glob("*.png"):
        m = re.fullmatch(r"\D*(\d+)\.png", p.name)
        if m:
            got[int(m.group(1))] = p.name
    want = frames // step
    if sorted(got) != list(range(len(got))) or len(got) not in (want, -(-frames // step)):
        missing = sorted(set(range(want)) - set(got))[:5]
        raise SystemExit(f"{d}: {len(got)} PNGs, {want} expected (missing from {missing})")
    return [got[i] for i in range(len(got))]


def export(prproj, sequences=None, png_fps=PNG_FPS, kinds=("h264",), out=None):
    """The exports of each sequence into the project's scratch folder; returns the manifest. kinds: the H.264 only by
    default (R240); ("png",) or ("h264", "png") on request. With one kind, the sequence's other kind is kept. R104:
    only into an empty Premiere; the project is closed unsaved, whatever happens."""
    prproj = Path(prproj).resolve()
    sequences = sequences or _sequences_in(prproj)
    out = Path(out).resolve() if out else scratch_for(prproj)     # Premiere writes only to an absolute path
    out.mkdir(parents=True, exist_ok=True)
    if not H264_PRESET.exists() or not png_preset(png_fps).exists():
        make_presets(sorted({PNG_FPS, png_fps}))
    mf = out / MANIFEST
    old = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
    if old and (old.get("prproj") != str(prproj) or old.get("stamp") != _stamp(prproj)):
        for e in old.get("sequences", {}).values():       # another project's, or made before the project was saved:
            if Path(e["dir"]).parent == out:              # no use to anyone, so not left behind unlisted
                shutil.rmtree(e["dir"], ignore_errors=True)
        old = {}
    man = {"prproj": str(prproj), "stamp": _stamp(prproj), "scratch": str(out), "sequences": old.get("sequences", {})}
    _write(mf, man)                                       # never a manifest listing folders just deleted
    print(json.dumps(start(), ensure_ascii=False))
    call("""(function () {
      if (app.projects.numProjects > 0) { throw new Error("a project is open in Premiere (" + app.projects[0].path + ")"); }
      if (!app.openDocument(%s)) { throw new Error("Premiere wouldn't open " + %s); }
      if (app.project.path !== %s) {     // none was open before: whatever is open now, this call opened
        var was = app.project.path;
        for (var k = app.projects.numProjects - 1; k >= 0; k--) { app.projects[k].closeDocument(false, false); }
        throw new Error("the project opened as " + was);
      }
      return true; })()""" % (json.dumps(str(prproj)), json.dumps(str(prproj)), json.dumps(str(prproj))), timeout=300)
    busy = out / BUSY_MARK                                # clean() leaves the folder alone while this process lives
    try:
        busy.write_text(json.dumps({"pid": os.getpid(), "started": time.time()}), encoding="utf-8")
        for name in sequences:
            d = out / slug(name)
            info = call("""(function () {
              var s = aidvFindSequence(%s);
              if (!s) { throw new Error("no sequence named " + %s); }
              return { fps: AIDV_TPS / Number(s.timebase), frames: Math.round(Number(s.end) / Number(s.timebase)),
                       width: s.frameSizeHorizontal, height: s.frameSizeVertical }; })()"""
                        % (json.dumps(name), json.dumps(name)), timeout=60)
            if (info["width"], info["height"]) != (1920, 1080):   # the PNG preset is 1920 x 1080 (no Match Source)
                raise SystemExit(f"{name} is {info['width']} x {info['height']}; the PNG preset is 1920 x 1080")
            fps = round(info["fps"], 3)
            if fps % png_fps:
                raise SystemExit(f"{name} runs at {fps} fps: the PNG sequence's {png_fps} fps isn't every n-th frame")
            entry = man["sequences"].pop(name, None)       # off the list until this export is whole again
            _write(mf, man)
            keep = entry if entry and entry["frames"] == info["frames"] and entry["fps"] == fps else None
            entry = {"name": name, "fps": fps, "frames": info["frames"], "dir": str(d),
                     **{k: v for k, v in (keep or {}).items() if k in ("h264", "png") and k not in kinds}}
            if keep is None and d.exists():
                shutil.rmtree(d)                          # a stale file would pass for this export's
            d.mkdir(parents=True, exist_ok=True)
            for kind in kinds:
                target = (d / "sequence.mp4") if kind == "h264" else (d / "png" / "f.png")
                if kind == "h264":
                    for f in d.glob("sequence*"):         # the last H.264 and any temp file of a stopped one
                        f.unlink()
                elif target.parent.exists():
                    shutil.rmtree(target.parent)
                target.parent.mkdir(exist_ok=True)
                preset = H264_PRESET if kind == "h264" else png_preset(png_fps)
                t0 = time.time()
                said = call("""(function () {
                  var s = aidvFindSequence(%s);
                  app.project.openSequence(s.sequenceID);
                  return s.exportAsMediaDirect(%s, %s, 0); })()"""
                            % (json.dumps(name), json.dumps(str(target)), json.dumps(str(preset))), timeout=4 * 3600)
                secs = round(time.time() - t0, 1)
                if kind == "h264":
                    if not target.exists():
                        raise SystemExit(f"Premiere exported no H.264 for {name} (it answered {said})")
                    n = _count_frames(target)
                    if n != info["frames"]:
                        raise SystemExit(f"{name}: the H.264 holds {n} frames, the sequence {info['frames']}")
                    late = pending_frames(Seq({**entry, "h264": {"path": str(target)}}))
                    if late:                              # media not yet loaded renders a yellow card (framecheck);
                        raise SystemExit(f"{name}: Premiere's Media pending card in the H.264 at {late[:5]} s")
                    entry["h264"] = {"path": str(target), "seconds": secs, "bytes": _size(target), "frames": n,
                                     "preset": str(preset)}       # none on round 6, about 1 s a minute to look
                else:
                    if not any(target.parent.glob("*.png")):
                        raise SystemExit(f"Premiere exported no PNG sequence for {name} (it answered {said})")
                    step = round(fps / png_fps)
                    files = _png_files(target.parent, info["frames"], step)
                    late = [i * step / fps for i in range(0, len(files), png_fps)
                            if _pending(target.parent / files[i])]           # one a second
                    if late:
                        raise SystemExit(f"{name}: Premiere's Media pending card in the PNGs at {late[:5]} s")
                    entry["png"] = {"dir": str(target.parent), "fps": png_fps, "step": step, "files": files,
                                    "seconds": secs, "bytes": _size(target.parent), "preset": str(preset)}
                print(json.dumps({"sequence": name, kind: secs}), flush=True)
            man["sequences"][name] = entry
            _write(mf, man)                               # after each sequence, so a failure keeps the rest
    finally:                                              # closed unsaved: an export changes nothing in the project
        busy.unlink(missing_ok=True)
        call("(function () { for (var k = 0; k < app.projects.numProjects; k++) { if (app.projects[k].path === %s)"
             " { app.projects[k].closeDocument(false, false); return true; } } return false; })()"
             % json.dumps(str(prproj)), timeout=120)
    return man


def _pending(png):
    from pipeline.edit.ppro.framecheck import pending
    return pending(png)


def _count_frames(mp4):
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                          "stream=nb_read_packets", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True,
                         check=True).stdout
    return int(out.strip().split(",")[0])


# ---------------------------------------------------------------------------------------------------------- reading

class Stale(RuntimeError):
    pass


class Exports:
    """A built project's exports, as exports.json lists them. Refuses them when the project was saved since (they
    would show the old edit) unless stale_ok."""

    def __init__(self, prproj, stale_ok=False, out=None):
        self.prproj = Path(prproj).resolve()
        places = [Path(out).resolve()] if out else _places(self.prproj)
        found = []
        for d in places:                                  # the first fresh one (a stale one on the card mustn't
            if (d / MANIFEST).exists():                   # hide fresh ones made while it was out)
                man = json.loads((d / MANIFEST).read_text(encoding="utf-8"))
                if man.get("prproj") == str(self.prproj):
                    found.append((d, man))
        fresh = [(d, m) for d, m in found if m["stamp"] == _stamp(self.prproj)]
        if not found:
            raise FileNotFoundError(f"no exports for {self.prproj} in {' or '.join(map(str, places))}: run "
                                    f"python -m pipeline.edit.ppro.exports export \"{self.prproj}\"")
        if not fresh and not stale_ok:
            raise Stale(f"{self.prproj} was saved after its exports were made: export again")
        self.dir, self.man = (fresh or found)[0]

    def names(self):
        return list(self.man["sequences"])

    def seq(self, name=None):
        """A sequence's exports; FileNotFoundError when it has none, or when their files have gone (check() then
        exports again)."""
        if name is None:
            if len(self.man["sequences"]) != 1:
                raise KeyError(f"name a sequence: {self.names()}")
            name = self.names()[0]
        if name not in self.man["sequences"]:
            raise FileNotFoundError(f"no exports of {name!r} in {self.dir} (there: {self.names()})")
        e = self.man["sequences"][name]
        gone = [p for p in ([e["h264"]["path"]] if "h264" in e else []) + ([e["png"]["dir"]] if "png" in e else [])
                if not Path(p).exists()]
        if gone:
            raise FileNotFoundError(f"{name}: its exports have gone ({gone[0]})")
        return Seq(e)


class Seq:
    """One sequence's exports. Frame k is the sequence's frame k: k = floor(t * fps + 0.5), the nearest frame, as
    project.frames() places the single-frame export; the H.264 holds every frame, the PNG sequence every step-th from
    frame 0 to the last whole step before the end (the last frames may have none)."""

    W, H = 1920, 1080

    def __init__(self, entry):
        self.e, self.name, self.fps, self.frames = entry, entry["name"], entry["fps"], entry["frames"]
        self.mp4 = Path(entry["h264"]["path"]) if "h264" in entry else None
        p = entry.get("png")
        self.png_dir, self.step, self.png_files = (Path(p["dir"]), p["step"], p["files"]) if p else (None, None, [])

    def index(self, t):
        return min(max(int(np.floor(t * self.fps + 0.5)), 0), self.frames - 1)   # half up, as JS Math.round

    def png(self, t):
        """The PNG sequence's file for t's exact frame, or None when it holds no such frame."""
        k = self.index(t)
        if not self.step or k % self.step or k // self.step >= len(self.png_files):
            return None
        return self.png_dir / self.png_files[k // self.step]

    def nearest_png(self, t):
        """(file, frames off) for the PNG sequence's frame nearest t (off: the PNG's frame minus t's; within
        step // 2 but at the very end), or None without a PNG sequence."""
        if not self.png_files:
            return None
        k = self.index(t)
        i = min(int(np.floor(k / self.step + 0.5)), len(self.png_files) - 1)
        return self.png_dir / self.png_files[i], i * self.step - k

    def _decode(self, first, last, keep, size=None):
        """Yield the RGB frames first..last whose index (counted from first) the select expression keep picks, in
        order, as arrays, decoding from the key frame before first. BT.709 limited range, as Premiere writes it
        (the file is unflagged, so ffmpeg would read BT.601)."""
        if self.mp4 is None:
            raise FileNotFoundError(f"{self.name}: no H.264 export")
        w, h = size or (self.W, self.H)
        vf = (f"select='{keep}',scale={w}:{h}:in_color_matrix=bt709:in_range=tv:out_range=pc"
              f":flags=bicubic+accurate_rnd+full_chroma_int,format=rgb24")
        ss = ["-ss", f"{(first - 0.5) / self.fps:.6f}"] if first > 0 else []   # the first frame at or after it
        cmd = [tool("ffmpeg"), "-v", "error", "-nostdin", *ss, "-t", f"{(last - first + 1) / self.fps:.6f}",
               "-i", str(self.mp4), "-vf", vf, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        import tempfile
        log = tempfile.TemporaryFile()                    # not a pipe: a damaged file's error per packet would fill
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log)   # one and stop ffmpeg, and this, for good
        n, tail = w * h * 3, None
        try:
            while True:
                buf = p.stdout.read(n)
                if len(buf) < n:
                    tail = len(buf)
                    break
                yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        finally:
            if tail is None:                              # the caller stopped early (a scan that found its answer)
                p.kill()
            p.stdout.close()
            p.wait()
            log.seek(0)
            err = log.read().decode("utf-8", "replace")
            log.close()
        if p.returncode or tail:
            raise RuntimeError(f"ffmpeg exit {p.returncode}, {tail} bytes of a cut-off frame: {err[-300:]}")

    GROUP_GAP, GROUP_MAX, WORKERS = 90, 16, 6      # ffmpeg can't parse a select of 103 eq() terms (out of memory)

    def frames_at(self, ks, size=None):
        """{k: RGB array} for these frame numbers, exact. Frames close together share one seek and decode (at most
        GROUP_MAX, none more than GROUP_GAP frames after the last), the groups decoded side by side. All are held in
        memory (6 MB a full frame): for many frames, scan()."""
        from concurrent.futures import ThreadPoolExecutor
        ks = sorted({min(max(int(k), 0), self.frames - 1) for k in ks})
        groups = []
        for k in ks:
            if groups and k - groups[-1][-1] <= self.GROUP_GAP and len(groups[-1]) < self.GROUP_MAX:
                groups[-1].append(k)
            else:
                groups.append([k])

        def one(g):
            got = list(self._decode(g[0], g[-1], "+".join(f"eq(n\\,{k - g[0]})" for k in g), size))
            if len(got) != len(g):
                raise RuntimeError(f"{self.name}: asked for frames {g}, ffmpeg gave {len(got)}")
            return zip(g, got)

        with ThreadPoolExecutor(self.WORKERS) as pool:
            return {k: a for pairs in pool.map(one, groups) for k, a in pairs}

    def frame(self, t, size=None):
        k = self.index(t)
        return self.frames_at([k], size)[k]

    def scan(self, every_s=None, every=1, start=0.0, end=None, size=None):
        """Yield (frame, seconds, RGB array) from start to end (seconds; the sequence's end by default), every
        every-th frame or every every_s seconds, from the H.264: a whole-sequence check's loop. size=(w, h) scales
        (a 480 x 270 scan moves a sixteenth of the bytes)."""
        step = max(1, round(every_s * self.fps)) if every_s else max(1, int(every))
        a, b = self.index(start), (self.index(end) if end is not None else self.frames - 1)
        for i, arr in enumerate(self._decode(a, b, f"not(mod(n\\,{step}))", size)):
            k = a + i * step
            yield k, k / self.fps, arr

    def pull(self, times, out_dir, source="h264"):
        """Each time's frame to out_dir/frame_<ms>.png (framecheck's names, so framecheck.sheet() reads them).
        source h264: the H.264's exact frame; best: the PNG sequence's when it holds the exact frame, else the
        H.264's; png: the PNG sequence's exact frame or nothing (the caller exports those singly). Returns
        {t: "png" | "h264" | None}."""
        from PIL import Image
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        got, need = {}, []
        for t in times:
            dst = out_dir / f"frame_{round(t * 1000):07d}.png"
            src = self.png(t) if source in ("png", "best") else None
            if src is not None:
                shutil.copyfile(src, dst)
                got[t] = "png"
            elif source == "png":
                got[t] = None
            else:
                need.append(t)
        if need:
            arrs = self.frames_at([self.index(t) for t in need])
            for t in need:
                Image.fromarray(arrs[self.index(t)]).save(out_dir / f"frame_{round(t * 1000):07d}.png")
                got[t] = "h264"
        return got


def pending_frames(seq, every_s=1.0):
    """Seconds at which the H.264 shows Premiere's "Media pending" card (framecheck.pending's test, on a 64 x 36
    scan)."""
    hits = []
    for _, t, a in seq.scan(every_s=every_s, size=(64, 36)):
        px = a.reshape(-1, 3).astype(np.float32)
        r, g, b = px[:, 0], px[:, 1], px[:, 2]
        if ((r > 120) & (g > 0.85 * r) & (g < r) & (b < 0.5 * g)).mean() > 0.6:
            hits.append(round(t, 3))
    return hits


# ---------------------------------------------------------------------------------------------------------- cleanup

BUSY_S = 180                    # a folder written to this recently may be an export still running: left alone


def _busy(r):
    """Why a folder may still be written to (an export's marker with its process alive, or a file written in the
    last BUSY_S seconds), or None."""
    from pipeline.edit.ppro.bridge import _alive
    mark = r / BUSY_MARK
    if mark.exists():
        try:
            pid = json.loads(mark.read_text(encoding="utf-8")).get("pid")
        except (json.JSONDecodeError, OSError):
            pid = None
        if pid and _alive(pid):
            return f"an export is running (process {pid})"
    age = time.time() - max((f.stat().st_mtime for f in r.rglob("*") if f.is_file()), default=0)
    return f"written {max(0, age):.0f} s ago: an export running?" if age < BUSY_S else None


def clean(prproj=None, everything=False):
    """Delete a project's exports, in both places they may be (or, with everything, every project's exports on the
    card). Only folders holding this module's exports.json, and none an export may still be writing (_busy).
    Returns the GB freed, the folders removed and those left."""
    if everything:
        if not SCRATCH.exists():
            return {"freed_gb": 0, "removed": [], "left": [], "note": f"nothing at {SCRATCH} (exports made without "
                    "the card are in each review folder's _exports: clean each project)"}
        roots = sorted(p.parent for p in SCRATCH.glob(f"*/*/*/{MANIFEST}"))
    else:
        roots = [d for d in _places(prproj) if (d / MANIFEST).exists()]
    freed, gone, left = 0, [], []
    for r in roots:
        why = _busy(r)
        if why:
            left.append(f"{r} ({why})")
            continue
        freed += _size(r)
        shutil.rmtree(r)
        gone.append(str(r))
        for up in (r.parent, r.parent.parent):            # the review's and the run's folders once empty
            if up.exists() and (up.parent == SCRATCH or up.parent.parent == SCRATCH or up.name == "_exports") \
                    and not any(up.iterdir()):
                up.rmdir()
    return {"freed_gb": round(freed / 1e9, 2), "removed": gone, "left": left}


# ---------------------------------------------------------------------------------------------------------- the sheet

def check(prproj, out_dir, times, sequence, source="h264", png_fps=PNG_FPS):
    """framecheck's sheet from the exports: makes the kinds the source needs first (h264: the H.264; png: the PNGs;
    best: both) when they are missing or the project was saved since; then each time's frame (Seq.pull), and with
    source png, a single QE frame for each time the PNG sequence lacks (framecheck.check, R104-safe). Returns (sheet,
    ok per time, source per time). A round's own export (the H.264 of every sequence, R240) is the export command."""
    from pipeline.edit.ppro import framecheck as fc
    kinds = {"h264": ("h264",), "png": ("png",), "best": ("h264", "png")}[source]
    try:
        s = Exports(prproj).seq(sequence)
        kinds = tuple(k for k in kinds if not (s.mp4 if k == "h264" else s.png_files))
        if kinds:
            raise FileNotFoundError(f"{sequence} has no {' or '.join(kinds)} export")
    except (FileNotFoundError, Stale) as why:
        print(f"exporting {' and '.join(kinds)} ({why})", flush=True)
        export(prproj, [sequence], png_fps=png_fps, kinds=kinds)
        s = Exports(prproj).seq(sequence)
    out_dir = Path(out_dir).resolve()
    got = s.pull(times, out_dir, source)
    single = [t for t, v in got.items() if v is None]
    if single:                                            # the exact moments the PNG sequence lacks
        fc.check(prproj, out_dir, single, sequence)
        got.update({t: "single" for t in single})
    files = [out_dir / f"frame_{round(t * 1000):07d}.png" for t in times]
    ok = [p.exists() and not fc.pending(p) for p in files]
    return fc.sheet(out_dir, times), ok, got


def where(prproj):
    try:
        ex = Exports(prproj, stale_ok=True)
    except FileNotFoundError:
        return {"scratch": str(scratch_for(prproj)), "exports": None}
    d, man = ex.dir, ex.man
    return {"scratch": str(d), "stale": man["stamp"] != _stamp(prproj), "gb": round(_size(d) / 1e9, 2),
            "sequences": {n: {"frames": s["frames"], "h264": s.get("h264", {}).get("path"),
                              "png": s.get("png", {}).get("dir"), "png_fps": s.get("png", {}).get("fps")}
                          for n, s in man["sequences"].items()}}


def parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("prproj")
    e.add_argument("--sequence", action="append")
    e.add_argument("--png-fps", type=int, default=PNG_FPS)
    e.add_argument("--only", choices=("h264", "png"), default="h264",
                   help="the kind to export (R240: the H.264 only by default)")
    f = sub.add_parser("frames")
    f.add_argument("prproj")
    f.add_argument("out_dir")
    f.add_argument("times")
    f.add_argument("--sequence")
    f.add_argument("--source", choices=("h264", "png", "best"), default="h264")
    w = sub.add_parser("where")
    w.add_argument("prproj")
    c = sub.add_parser("clean")
    c.add_argument("prproj", nargs="?")
    c.add_argument("--all", action="store_true")
    sub.add_parser("presets")
    return ap


def main(argv=None):
    from pipeline.edit.ppro.framecheck import secs
    a = parser().parse_args(argv)
    if a.cmd == "export":
        m = export(a.prproj, a.sequence, a.png_fps, (a.only,))
        print(json.dumps(where(a.prproj), indent=1))
        return 0 if m["sequences"] else 1
    if a.cmd == "frames":
        seq = a.sequence or (_sequences_in(a.prproj)[0] if len(_sequences_in(a.prproj)) == 1 else None)
        if seq is None:
            raise SystemExit(f"--sequence: one of {_sequences_in(a.prproj)}")
        sheet, ok, got = check(a.prproj, a.out_dir, [secs(v) for v in a.times.split(",")], seq, a.source)
        print(json.dumps({"sheet": str(sheet), "exported": sum(ok), "of": len(ok),
                          "from": {k: list(got.values()).count(k) for k in set(got.values())}}))
        return 0 if all(ok) else 1
    if a.cmd == "where":
        print(json.dumps(where(a.prproj), indent=1))
        return 0
    if a.cmd == "clean":
        if not a.all and not a.prproj:
            raise SystemExit("clean <built.prproj> or clean --all")
        print(json.dumps(clean(a.prproj, a.all)))
        return 0
    print("\n".join(str(p) for p in make_presets()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
