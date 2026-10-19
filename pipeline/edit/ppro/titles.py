"""Editable caption titles (R102): one Premiere graphic per caption cue, in David's look, at the planner's spot (R53).

Premiere's scripting can't write a graphic's text: ExtendScript reads a native graphic's Source Text as binary, UXP
can't read or set it, and a Premiere-made Motion Graphics Template (.mogrt) becomes a native graphic when it's added,
so its text isn't a template parameter either (GOTCHAS). So each cue gets a .mogrt of its own with its text and place
already in it, and the AIDV panel's ExtendScript (aidvCaptionTitles, jsx/aidv.jsx) adds them to the sequence and sets
their lengths. In Premiere each one is an ordinary graphic: David double-clicks the text to change a word or add a line
break, and moves, retimes or deletes it like any clip.

How a cue's .mogrt is made:
  * The skeleton is Premiere's own Basic Title.mogrt (definition.json + project.prgraphic, a zip holding a gzipped
    .prproj with one graphic clip).
  * Its Source Text param is replaced by David's (assets/caption_title_param.xml: his first TitleTest title, read
    2026-10-13): Lucida Console 40 px, white, left-aligned, a #5E5E5E background at 100% with 15 px around the text and
    roundness 10. The value is a FlatBuffer behind a 12-byte header (u64 length, magic 11223344), the schema of
    Premiere's captions (prproj.decode_caption): root table -> table 0 -> field 0 the text runs, each run field 0 its
    text. The cue's text is appended at the buffer's end and the run's offset repointed to it (offsets only point
    forward, so nothing else moves); the old string stays as dead bytes, blanked.
  * BinaryHash: 24 hex digits (a hash Premiere computes; not MD5, SHA or CRC) and the value's length plus 12. A unique
    random one per cue, so Premiere never mistakes one cue's value for another's.
  * Premiere draws the box around the text's ink (not its line box) plus the 15 px, so a box's size depends on its
    letters. ink_box() renders the lines with the same font and line step to find it (within 1 to 3 px of Premiere's
    own render, measured 2026-10-13), and the text layer's Position puts the anchor (first baseline, left) where the
    box lands at the planner's spot (premiere.caption_place, as the caption stills do).
"""
import base64
import gzip
import io
import json
import re
import secrets
import struct
import uuid
import zipfile
from pathlib import Path


ASSETS = Path(__file__).resolve().parent / "assets"
STYLE = ASSETS / "caption_title_param.xml"
SKELETON = Path(r"C:\Program Files\Adobe\Adobe Premiere Pro 2026\Essential Graphics\Basic Title.mogrt")
MAGIC = bytes.fromhex("44332211")
SKELETON_PARAM_ID = "73"            # the skeleton's Source Text param (ObjectID in its .prproj)
SKELETON_POS_ID = "75"              # its text layer's Position param
FONT_FILE = "C:/Windows/Fonts/lucon.ttf"    # David's title: Lucida Console 40 px, 15 px around the ink
SIZE_PX, PAD_PX = 40, 15            # the TitleTest look's size; an exercise may set captions.titles.size_px (R126: 48)
LINE_STEP = 48                      # baseline to baseline in Premiere at 40 px (measured): 1.2 x the size
TRACK = "Caption titles"            # the full sequence's track for them, above the PNG Captions track


def line_step(size_px):
    """Baseline to baseline in Premiere at size_px: its auto leading, 1.2 x the size (48 px at 40, measured)."""
    return round(size_px * LINE_STEP / SIZE_PX)


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def _field(b, t, i):
    vt = t - struct.unpack_from("<i", b, t)[0]
    if 4 + 2 * i >= struct.unpack_from("<H", b, vt)[0]:
        return None
    o = struct.unpack_from("<H", b, vt + 4 + 2 * i)[0]
    return t + o if o else None


def text_value(style_raw: bytes, text: str, size_px=None, box_hex=None) -> bytes:
    """David's Source Text value with its one run's text replaced by `text` (lines joined by \\r), its font size set
    to size_px when given (the run's style table, field 1) and its box colour to box_hex (the first table's field 17,
    a table of three one-byte fields; R192); prproj.decode_caption reads both back."""
    if style_raw[8:12] != MAGIC:
        raise ValueError("not a Premiere text value (no 11223344 magic)")
    fb = bytearray(style_raw[12:])
    root = _u32(fb, 0)
    t0 = _field(fb, root, 0)
    t0 += _u32(fb, t0)
    if box_hex:
        rgb_t = _field(fb, t0, 17)
        if rgb_t is None:
            raise ValueError("the style value has no box colour to set")
        rgb_t += _u32(fb, rgb_t)
        want = bytes.fromhex(box_hex.lstrip("#"))
        for k in range(3):
            p = _field(fb, rgb_t, k)
            if p is None:                               # an absent channel is 0 and has no byte to write
                if want[k]:
                    raise ValueError(f"the box colour's channel {k} is absent; can't set {box_hex}")
                continue
            fb[p] = want[k]
    runs = _field(fb, t0, 0)
    runs += _u32(fb, runs)
    if _u32(fb, runs) != 1:
        raise ValueError(f"expected one text run, found {_u32(fb, runs)}")
    run = runs + 4 + _u32(fb, runs + 4)
    if size_px is not None:                             # R126: the size lives in the run's style table
        style = _field(fb, run, 1)
        size = _field(fb, style + _u32(fb, style), 1) if style is not None else None
        if size is None:
            raise ValueError("the style value has no font size field to set")
        struct.pack_into("<f", fb, size, float(size_px))
    slot = _field(fb, run, 0)                           # the run's offset to its text
    old = slot + _u32(fb, slot)                         # blanked, so no reader finds the template's words
    fb[old + 4:old + 4 + _u32(fb, old)] = bytes(_u32(fb, old))
    struct.pack_into("<I", fb, old, 0)
    fb.extend(b"\0" * (-len(fb) % 4))
    new = len(fb)
    data = text.encode("utf-8")
    fb.extend(struct.pack("<I", len(data)) + data + b"\0")
    fb.extend(b"\0" * (-len(fb) % 4))
    struct.pack_into("<I", fb, slot, new - slot)
    return struct.pack("<Q", len(fb)) + MAGIC + bytes(fb)


def binary_hash(value: bytes) -> str:
    h = secrets.token_hex(12)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:24]}{len(value) + 12:08x}"


def _style():
    xml = STYLE.read_text(encoding="utf-8")
    m = re.search(r'<StartKeyframeValue Encoding="base64" BinaryHash="[^"]+">([^<]+)<', xml)
    return xml, base64.b64decode(re.sub(r"\s+", "", m.group(1)))


def _xml_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\r", "&#13;")


def mogrt(out: Path, text: str, anchor_px, frame=(1920, 1080), name="AIDV Caption", size_px=SIZE_PX, box_hex=None):
    """Write a .mogrt holding one title in David's look at size_px: `text` (lines split on \\n), its anchor (the
    first line's baseline, left) at anchor_px in a frame of `frame` pixels."""
    text = text.replace("\r\n", "\n").replace("\n", "\r")
    param_xml, style_raw = _style()
    value = text_value(style_raw, text, size_px, box_hex)
    b64 = base64.b64encode(value).decode()
    param = re.sub(r'<StartKeyframeValue Encoding="base64" BinaryHash="[^"]+">[^<]+<',
                   lambda _: f'<StartKeyframeValue Encoding="base64" BinaryHash="{binary_hash(value)}">{b64}\n\t\t<',
                   param_xml)
    param = re.sub(r'<ArbVideoComponentParam ObjectID="\d+"', f'<ArbVideoComponentParam ObjectID="{SKELETON_PARAM_ID}"',
                   param, count=1)

    src = zipfile.ZipFile(SKELETON)
    inner = zipfile.ZipFile(io.BytesIO(src.read("project.prgraphic")))
    (inner_name,) = inner.namelist()
    proj = gzip.decompress(inner.read(inner_name)).decode("utf-8")
    proj, n = re.subn(r'<ArbVideoComponentParam ObjectID="%s".*?</ArbVideoComponentParam>' % SKELETON_PARAM_ID,
                      lambda _: param.strip(), proj, flags=re.S)
    assert n == 1, "skeleton's Source Text param not found"
    x, y = anchor_px[0] / frame[0], anchor_px[1] / frame[1]
    proj, n = re.subn(r'(<PointComponentParam ObjectID="%s".*?<StartKeyframe>-?\d+,)[^,]+,[^,]+,' % SKELETON_POS_ID,
                      lambda m: f"{m.group(1)}{x:.10f},{y:.10f},", proj, count=1, flags=re.S)
    assert n == 1, "skeleton's text Position param not found"
    proj = proj.replace("<InstanceName>Your Title Here</InstanceName>", f"<InstanceName>{_xml_text(text)}</InstanceName>")
    proj = re.sub(r"<BE.RushInspectorPanel.MogrtIdentifier>[^<]+<",
                  f"<BE.RushInspectorPanel.MogrtIdentifier>{uuid.uuid4()}<", proj)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(inner_name, gzip.compress(proj.encode("utf-8")))

    d = json.loads(src.read("definition.json"))
    d["capsuleID"] = str(uuid.uuid4())                  # Premiere keys templates by it: one per cue
    d["capsuleName"] = name
    d["capsuleNameLocalized"] = {"strDB": [{"localeString": "en_US", "str": name}]}
    d["clientControls"][0]["value"] = {"strDB": [{"localeString": "en_US", "str": text}]}
    d["sourceInfoLocalized"] = {"en_US": d["sourceInfoLocalized"]["en_US"]}
    d["usedFontsLocalized"] = {"en_US": ["LucidaConsole"]}
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("definition.json", json.dumps(d))
        z.writestr("project.prgraphic", buf.getvalue())
        z.writestr("thumb.png", src.read("thumb.png"))
    return out


def ink_box(lines, size_px=SIZE_PX):
    """(left, top, right, bottom) of the lines' ink relative to the anchor (the first baseline, left)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(FONT_FILE, size_px)
    step = line_step(size_px)
    ox, oy = 2 * size_px, 2 * size_px
    im = Image.new("L", (int(max(font.getlength(l) for l in lines)) + 2 * ox, step * len(lines) + 2 * oy))
    d = ImageDraw.Draw(im)
    for k, line in enumerate(lines):
        d.text((ox, oy + k * step), line, font=font, fill=255, anchor="ls")
    l, t, r, b = im.getbbox() or (ox, oy, ox, oy)
    return l - ox, t - oy, r - ox, b - oy


def build(out, cues, place, W, H, fps, seq_name, end_frame, size_px=SIZE_PX, box_hex=None):
    """One .mogrt per cue in out/titles/ and the job aidvCaptionTitles reads (out/caption_titles.json): [(cue,
    mogrt)]. place(cue, bw, bh) -> the box's top-left corner (premiere.caption_place). Times are whole frames on the
    full sequence, none past end_frame (the logo outro, R96). size_px: the text size (R126: 48 for Section A)."""
    if abs(fps - round(fps)) > 1e-9:                    # Premiere ticks per frame are whole only at whole rates
        raise ValueError(f"caption titles need a whole frame rate, not {fps}")
    tdir = out / "titles"
    tdir.mkdir(parents=True, exist_ok=True)
    job, made = [], []
    for i, c in enumerate(cues):
        a, b = max(0, round(c["start"] * fps)), min(end_frame, round(c["end"] * fps))
        if b <= a:
            continue
        lines = c["text"].split("\n")
        l, t, r, bt = ink_box(lines, size_px)
        bw, bh = r - l + 2 * PAD_PX, bt - t + 2 * PAD_PX
        x, y = place(c, bw, bh)
        anchor = (x + PAD_PX - l, y + PAD_PX - t)
        m = mogrt(tdir / f"cap_{i:03d}.mogrt", c["text"], anchor, (W, H), size_px=size_px, box_hex=box_hex)
        job.append({"start_frame": a, "end_frame": b, "text": c["text"], "mogrt": str(m.resolve()),
                    "box": [round(x), round(y), round(bw), round(bh)], "anchor": [round(v, 1) for v in anchor]})
        made.append((c, m))
    (out / "caption_titles.json").write_text(json.dumps(
        {"note": "R102: one editable title per cue. The AIDV panel (Window > Extensions > AIDV) adds them to the "
                 "sequence below, on its track of this name; pipeline.edit.ppro.project does it unattended.",
         "sequence": seq_name, "track": TRACK, "fps": fps, "size_px": size_px, "cues": job}, indent=1,
        ensure_ascii=False), encoding="utf-8")
    return made


def readback(project, job, W=1920, H=1080):
    """David's changes to the titles (R60): the saved project's Caption titles track against the job, one entry per
    change: deleted, added, retimed, reworded (wrap included), moved. project: a prproj.Project."""
    seq = project.parse_sequence(job["sequence"])
    track = next((t for t in seq["video_tracks"] if t["name"] == job["track"]), None)
    if track is None:
        return [{"change": f"the {job['track']} track is gone"}]
    tpf = 254016000000 / job["fps"]
    his = []
    for it in track["items"]:
        comps = it["effects"]["components"]
        txt = next((p for c in comps if c["match_name"] == "AE.ADBE Text" for p in c["params"]
                    if p["name"] == "Source Text"), {})
        pos = next((p.get("static") for c in comps if c["match_name"] == "AE.ADBE Text" for p in c["params"]
                    if p["name"] == "Position"), None)
        motion = next((p.get("static") for c in comps if c["match_name"] == "AE.ADBE Motion" for p in c["params"]
                       if p["name"] == "Position"), None)
        his.append({"a": round(it["start_ticks"] / tpf), "b": round(it["end_ticks"] / tpf),
                    "text": (txt.get("text") or "").replace("\r", "\n"),
                    "anchor": [pos[0] * W, pos[1] * H] if isinstance(pos, list) else None,
                    "motion": motion if isinstance(motion, list) and motion != [0.5, 0.5] else None})
    if not his:                   # an XML imported by hand: the track came in empty (pipeline.edit.ppro.project fills it)
        return [{"text": "", "change": f"no titles on the {job['track']} track"}]
    out, used = [], set()
    for i, c in enumerate(job["cues"]):
        k = max((j for j in range(len(his)) if j not in used),
                key=lambda j: min(c["end_frame"], his[j]["b"]) - max(c["start_frame"], his[j]["a"]), default=None)
        if k is None or min(c["end_frame"], his[k]["b"]) <= max(c["start_frame"], his[k]["a"]):
            out.append({"cue": i, "text": c["text"], "change": "deleted"})
            continue
        used.add(k)
        h = his[k]
        if (h["a"], h["b"]) != (c["start_frame"], c["end_frame"]):
            out.append({"cue": i, "text": c["text"], "change": "retimed",
                        "by": f"start {(h['a'] - c['start_frame']) / job['fps']:+.2f} s, "
                              f"end {(h['b'] - c['end_frame']) / job['fps']:+.2f} s"})
        if h["text"] != c["text"]:
            kind = "rewrapped" if h["text"].split() == c["text"].split() else "reworded"
            out.append({"cue": i, "text": c["text"], "change": kind, "his": h["text"]})
        if h["anchor"] and c.get("anchor") and max(abs(h["anchor"][0] - c["anchor"][0]),
                                                   abs(h["anchor"][1] - c["anchor"][1])) > 2:
            out.append({"cue": i, "text": c["text"], "change": "moved",
                        "by_px": [round(h["anchor"][0] - c["anchor"][0]), round(h["anchor"][1] - c["anchor"][1])]})
        if h["motion"]:
            out.append({"cue": i, "text": c["text"], "change": "moved (Motion)", "motion": h["motion"]})
    out += [{"text": his[j]["text"], "change": "added", "at_s": round(his[j]["a"] / job["fps"], 2)}
            for j in range(len(his)) if j not in used]
    return out
