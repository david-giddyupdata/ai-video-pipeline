"""
prproj.py -- extract editing decisions from an Adobe Premiere Pro project (.prproj).

Purpose
    Read-only extraction of timeline structure from a Premiere project so an editor's
    style (zooms, overlays, transitions, audio levels, speed changes) can be measured.
    Written for D:\\Videos\\QuickSeries\\AmazonQuick.prproj (Premiere 2026, project
    Version 45) but nothing in it is specific to that project.

Usage
    python -m pipeline.edit.prproj PROJECT.prproj --list
        List every sequence with its duration, frame rate and export targets.
    python -m pipeline.edit.prproj PROJECT.prproj --sequence "02-QuickInterface05" --out ep02.json
        Extract one sequence (by exact name or ObjectUID) to JSON.

    The project is opened read-only. A .prproj is gzip-compressed XML; a plain XML
    file is also accepted.

File-format notes (reverse-engineered; treat as best effort)
    * Top-level objects are children of <PremiereData>. They carry ObjectID (int) or
      ObjectUID (guid); references are ObjectRef (-> ObjectID) or ObjectURef (-> ObjectUID).
    * Time is in ticks: 254,016,000,000 ticks per second.
    * Sequence -> TrackGroups -> {Video,Audio,Data}TrackGroup -> Tracks (ObjectURef)
      -> {Video,Audio}ClipTrack -> ClipItems/TrackItems -> {Video,Audio}ClipTrackItem.
      TrackItem/Start (omitted when 0) and TrackItem/End are sequence ticks.
      ClipTrackItem/SubClip -> SubClip -> Clip (VideoClip/AudioClip: InPoint, OutPoint,
      PlaybackSpeed, PlayBackwards, FrameHold, AdjustmentLayer) and MasterClip.
      Clip/Source -> VideoMediaSource/AudioMediaSource -> Media (FilePath) or
      VideoSequenceSource/AudioSequenceSource -> Sequence (a nested sequence).
    * Effects: ClipTrackItem/ComponentOwner/Components -> VideoComponentChain /
      AudioComponentChain -> Components -> VideoFilterComponent / AudioFilterComponent
      -> Params -> *ComponentParam. When a VideoComponentChain says DefaultMotion=true /
      DefaultOpacity=true the intrinsic Motion/Opacity components are not stored (they
      are at defaults: scale 100, position centre, opacity 100).
    * Param values: <StartKeyframe> holds the static value ("time,value,..."), and
      <Keyframes> holds "time,value,inInterp,outInterp,tangents...;" entries.
      Scalars have 8 fields; points ("x:y", normalised 0..1 of the frame) have 14.
      Interpolation code 0 = linear (confirmed: tangent = straight-line slope, influence
      1/6). Other codes (5, 4, 2) are NOT decoded with certainty; they are reported raw
      and flagged as 'non-linear (uncertain)'.
    * Keyframe times on clip effects are in the clip's MEDIA time (source ticks, i.e. they
      include the clip InPoint). Sequence time = item.start + (kf - InPoint) / speed.
      This was checked empirically (see 'kf_time_base_check' in the output) rather than
      taken from documentation.
    * Audio "Level"/"Volume" values are linear gain where 0.17782794 = 0 dB
      (= 10^(-15/20); Premiere's slider tops out at +15 dB). dB = 20*log10(v) + 15.
    * Markers: Markers -> Marker -> DVAMarker JSON (mStartTime.ticks, mDuration, mName,
      mComment, mType). Sequence markers live on the sequence's own MasterClip's clips.
    * Essential Graphics text: 'AE.ADBE Text' component, param 'Source Text', base64
      flatbuffer. Text strings are recovered heuristically (length-prefixed UTF-8 runs);
      the font name usually appears among them.
    * Captions: CaptionDataClipTrackItem -> BlockVector -> Block/FormattedTextData, a base64
      FlatBuffer after an 8-byte length and the magic 11223344. decode_caption() reads the
      fields decoded so far (S5, by diffing auto-saves around single edits; GOTCHAS).
    Moved here from research/style_study/premiere/parse_prproj.py for pipeline.edit.readback.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import math
import re
import struct
import sys
from pathlib import Path

try:
    from lxml import etree as ET
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as ET  # type: ignore

TPS = 254016000000  # ticks per second
VIDEO_MT = "228cda18-3625-4d2d-951e-348879e4ed93"
AUDIO_MT = "80b8e3d5-6dca-4195-aefb-cb5f407ab009"
DATA_MT = "d8143ffe-eec4-4d2a-a909-d5f7bf094dc5"
STILL_EXT = {".png", ".jpg", ".jpeg", ".psd", ".ai", ".tif", ".tiff", ".bmp", ".gif", ".svg"}
AUDIO_EXT = {".mp3", ".wav", ".aif", ".aiff", ".m4a", ".aac"}


def sec(ticks) -> float | None:
    if ticks is None:
        return None
    return round(int(ticks) / TPS, 4)


def gain_to_db(v: float) -> float | None:
    if v is None:
        return None
    if v <= 0:
        return float("-inf")
    return round(20 * math.log10(v) + 15, 2)


class Project:
    def __init__(self, path: str | Path):
        raw = Path(path).read_bytes()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        self.root = ET.fromstring(raw)
        self.byid: dict[str, object] = {}
        self.byuid: dict[str, object] = {}
        for e in self.root:
            if e.get("ObjectID"):
                self.byid[e.get("ObjectID")] = e
            if e.get("ObjectUID"):
                self.byuid[e.get("ObjectUID")] = e
        # Premiere stores a binary value once: a later copy with the same BinaryHash is an empty element (a caption
        # line repeated word for word read as no text, so the read-back called David's kept line deleted; found by
        # cross-checking against py-premiere, 2026-10-13: 10 cues in full_take02, 1 in s7_take06 round 2)
        self.binary: dict[str, str] = {}
        for e in self.root.iter():
            h = e.get("BinaryHash")
            if h and (e.text or "").strip() and h not in self.binary:
                self.binary[h] = e.text
        # sequence uid -> MasterClip element (for sequence markers)
        self._seq_master: dict[str, object] = {}
        for mc in (e for e in self.root if e.tag == "MasterClip"):
            for c in mc.findall("Clips/Clip"):
                clip = self.ref(c)
                if clip is None:
                    continue
                src = self.ref(clip.find("Clip/Source"))
                if src is not None and src.tag.endswith("SequenceSource"):
                    seq = src.find("SequenceSource/Sequence")
                    if seq is not None:
                        self._seq_master.setdefault(seq.get("ObjectURef"), mc)

    # -- references -------------------------------------------------------------
    def value(self, el):
        """A binary element's base64 text, from its first copy when this one is empty (see self.binary)."""
        if el is None:
            return None
        return el.text if (el.text or "").strip() else self.binary.get(el.get("BinaryHash"))

    def ref(self, el):
        if el is None:
            return None
        if el.get("ObjectRef"):
            return self.byid.get(el.get("ObjectRef"))
        if el.get("ObjectURef"):
            return self.byuid.get(el.get("ObjectURef"))
        return None

    # -- sequences --------------------------------------------------------------
    def sequences(self):
        out = []
        for s in (e for e in self.root if e.tag == "Sequence"):
            info = {"uid": s.get("ObjectUID"), "name": s.findtext("Name")}
            fr, dur = None, 0
            for tg in s.findall("TrackGroups/TrackGroup"):
                g = self.ref(tg.find("Second"))
                if g is None:
                    continue
                if g.tag == "VideoTrackGroup":
                    fr = g.findtext("TrackGroup/FrameRate")
                for tr in g.findall("TrackGroup/Tracks/Track"):
                    t = self.ref(tr)
                    if t is None:
                        continue
                    for ti in t.findall("ClipTrack/ClipItems/TrackItems/TrackItem"):
                        it = self.ref(ti)
                        if it is not None:
                            end = it.find(".//TrackItem/End")
                            if end is not None:
                                dur = max(dur, int(end.text))
            info["fps"] = round(TPS / int(fr), 3) if fr else None
            info["duration_s"] = sec(dur)
            info["exports"] = self._exports(s)
            out.append(info)
        return out

    @staticmethod
    def _exports(s):
        res = []
        props = s.find("Node/Properties")
        if props is None:
            return res
        for p in props:
            if p.tag.startswith("ExportSettings.Info.") and p.text:
                try:
                    j = json.loads(p.text)
                except ValueError:
                    continue
                if j.get("DoExport"):
                    res.append({"dest": p.tag.split(".")[-1], "path": j.get("OutPath"),
                                "out_point_s": sec(j.get("OutPoint"))})
        return res

    def find_sequence(self, key):
        for s in (e for e in self.root if e.tag == "Sequence"):
            if s.get("ObjectUID") == key or s.findtext("Name") == key:
                return s
        raise KeyError(key)

    # -- values / keyframes -------------------------------------------------------
    @staticmethod
    def _parse_value(v: str):
        if v is None:
            return None
        if ":" in v:
            try:
                x, y = v.split(":")
                return [float(x), float(y)]
            except ValueError:
                return v
        if v in ("true", "false"):
            return v == "true"
        try:
            return float(v)
        except ValueError:
            return v

    def parse_param(self, p):
        d = {"name": (p.findtext("Name") or "").strip() or None, "kind": p.tag}
        sk = p.findtext("StartKeyframe")
        if sk:
            d["static"] = self._parse_value(sk.split(",")[1])
        cv = p.findtext("CurrentValue")
        if cv is not None and "static" not in d:
            d["static"] = self._parse_value(cv)
        kfs = p.findtext("Keyframes")
        if kfs:
            out = []
            for k in kfs.strip().strip(";").split(";"):
                f = k.split(",")
                if len(f) < 2:
                    continue
                kd = {"t_ticks": int(f[0]), "value": self._parse_value(f[1])}
                if len(f) >= 4:
                    kd["interp_codes"] = [int(f[2]), int(f[3])]
                    kd["interp"] = "linear" if f[2] == "0" and f[3] == "0" else "non-linear (uncertain code)"
                if len(f) >= 8:
                    try:
                        kd["influence_in_out"] = [round(float(f[5]), 4), round(float(f[7]), 4)]
                    except ValueError:
                        pass
                if len(f) >= 10:
                    kd["spatial_codes"] = [f[8], f[9]]
                out.append(kd)
            d["keyframes"] = out
        if p.tag == "ArbVideoComponentParam":
            b = self.value(p.find("StartKeyframeValue"))
            if b and d["name"] == "Source Text":
                d["text_strings"] = extract_strings(b)
                doc = decode_caption(b)             # a graphic's text has the captions' schema (FlatBuffer, magic)
                if doc:
                    d["text"] = doc["text"]
                    d["text_style"] = {k: doc[k] for k in ("font_size", "align", "box_on", "box_hex", "box_opacity",
                                                           "corner_radius")}
        return d

    def parse_component(self, c):
        d = {"tag": c.tag}
        if c.tag == "VideoFilterComponent":
            d["match_name"] = c.findtext("MatchName")
            d["display_name"] = c.findtext("Component/DisplayName")
            plist = c.findall("Component/Params/Param")
        elif c.tag == "AudioFilterComponent":
            d["match_name"] = c.findtext("FilterMatchName")
            d["display_name"] = c.findtext("AudioComponent/Component/DisplayName")
            plist = c.findall("AudioComponent/Component/Params/Param")
        else:
            d["match_name"] = c.findtext(".//MatchName") or c.findtext(".//FilterMatchName")
            plist = c.findall(".//Params/Param")
        d["params"] = []
        for pr in plist:
            p = self.ref(pr)
            if p is not None:
                d["params"].append(self.parse_param(p))
        subs = c.findall("SubComponents/SubComponent")
        if subs:  # masks (AE.ADBE AEMask2) attached to an effect
            d["sub_components"] = []
            for sc in subs:
                sub = self.ref(sc)
                if sub is not None:
                    sd = self.parse_component(sub)
                    sd["instance_name"] = sub.findtext("Component/InstanceName")
                    d["sub_components"].append(sd)
        return d

    def parse_chain(self, owner):
        """owner: element containing ComponentOwner/Components."""
        chain = self.ref(owner.find(".//ComponentOwner/Components"))
        if chain is None:
            return {"components": []}
        res = {"default_motion": chain.findtext("DefaultMotion") == "true",
               "default_opacity": chain.findtext("DefaultOpacity") == "true",
               "components": []}
        for c in chain.findall("ComponentChain/Components/Component"):
            comp = self.ref(c)
            if comp is not None:
                res["components"].append(self.parse_component(comp))
        return res

    def markers(self, markers_el):
        m = self.ref(markers_el)
        out = []
        if m is None:
            return out
        for mk in m.findall("Markers/Marker"):
            o = self.ref(mk.find("Second"))
            if o is None:
                continue
            try:
                j = json.loads(o.findtext("DVAMarker"))["DVAMarker"]
            except (TypeError, ValueError, KeyError):
                continue
            out.append({
                "t_ticks": j.get("mStartTime", {}).get("ticks"),
                "duration_ticks": (j.get("mDuration") or {}).get("ticks", 0),
                "name": j.get("mName"), "comment": j.get("mComment"), "type": j.get("mType"),
            })
        return out

    # -- media ------------------------------------------------------------------
    def source_info(self, clip_el):
        src = self.ref(clip_el.find("Clip/Source"))
        if src is None:
            return {"kind": "unknown"}
        if src.tag.endswith("SequenceSource"):
            seq = self.byuid.get(src.find("SequenceSource/Sequence").get("ObjectURef"))
            return {"kind": "nested_sequence", "sequence_uid": seq.get("ObjectUID") if seq is not None else None,
                    "sequence_name": seq.findtext("Name") if seq is not None else None}
        media = self.ref(src.find("MediaSource/Media"))
        if media is None:
            return {"kind": "unknown", "source_tag": src.tag}
        fp = media.findtext("FilePath") or media.findtext("ActualMediaFilePath")
        title = media.findtext("Title")
        info = {"file_path": fp, "title": title, "original_duration_s": sec(src.findtext("OriginalDuration"))}
        vs = self.ref(media.find("VideoStream"))
        if vs is not None and vs.findtext("FrameRect"):
            r = [int(x) for x in vs.findtext("FrameRect").split(",")]
            info["frame_w"], info["frame_h"] = r[2] - r[0], r[3] - r[1]
            info["is_still"] = vs.findtext("IsStill") == "true"
        if fp and fp.isdigit():
            # synthetic media: FilePath is a FourCC as an int ('GRPH' graphic, 'COLR' matte, ...)
            info["kind"] = "synthetic"
            info["fourcc"] = int(fp).to_bytes(4, "big").decode("latin-1")
            info["file_path"] = None
        elif fp:
            ext = Path(fp).suffix.lower()
            info["kind"] = ("still" if ext in STILL_EXT else "audio_file" if ext in AUDIO_EXT else "video_file")
        else:
            info["kind"] = "synthetic"  # graphics, adjustment layer, colour matte, etc.
            info["implementation_id"] = media.findtext("ImplementationID")
        return info

    # -- track items --------------------------------------------------------------
    def parse_item(self, it, track_kind):
        ti = it.find("ClipTrackItem/TrackItem")
        start = int(ti.findtext("Start") or 0)
        end = int(ti.findtext("End"))
        sub = self.ref(it.find("ClipTrackItem/SubClip"))
        d = {"object_id": it.get("ObjectID"), "start_ticks": start, "end_ticks": end}
        clip = None
        if sub is not None:
            d["subclip_name"] = sub.findtext("Name")
            mc = self.ref(sub.find("MasterClip"))
            d["master_clip_name"] = mc.findtext("Name") if mc is not None else None
            clip = self.ref(sub.find("Clip"))
        if clip is not None:
            c = clip.find("Clip")
            d["src_in_ticks"] = int(c.findtext("InPoint") or 0)
            d["src_out_ticks"] = int(c.findtext("OutPoint")) if c.findtext("OutPoint") else None
            d["speed"] = float(c.findtext("PlaybackSpeed") or 1.0)
            d["reverse"] = c.findtext("PlayBackwards") == "true"
            if clip.findtext("FrameHold") is not None:
                d["frame_hold_raw"] = clip.findtext("FrameHold")  # meaning not confirmed
            if clip.findtext("AdjustmentLayer") is not None:
                d["adjustment_layer"] = clip.findtext("AdjustmentLayer") == "true"
            d["source"] = self.source_info(clip)
            d["clip_markers"] = self.markers(c.find("MarkerOwner/Markers"))
        d["effects"] = self.parse_chain(it.find("ClipTrackItem"))
        if it.find("HeadTransition") is not None or it.find("TailTransition") is not None:
            d["has_transition_refs"] = True
        return d

    def parse_transition(self, it):
        ti = it.find("TransitionTrackItem/TrackItem")
        start = int(ti.findtext("Start") or 0)
        end = int(ti.findtext("End"))
        comp = self.ref(it.find("VideoFilterComponent")) if it.find("VideoFilterComponent") is not None else None
        return {"object_id": it.get("ObjectID"),
                "type": it.findtext("TransitionTrackItem/DisplayName"),
                "match_name": it.findtext("TransitionTrackItem/MatchName"),
                "start_ticks": start, "end_ticks": end,
                "alignment_ticks": int(it.findtext("TransitionTrackItem/Alignment") or 0),
                "has_outgoing": it.findtext("TransitionTrackItem/HasOutgoingClip") == "true",
                "has_incoming": it.findtext("TransitionTrackItem/HasIncomingClip") == "true",
                "params": self.parse_component(comp)["params"] if comp is not None else []}

    def parse_track(self, t, kind, index):
        node = t.find("ClipTrack/Track")
        props = node.find("Node/Properties") if node is not None else None
        d = {"kind": kind, "index": index,
             "label": f"{'V' if kind == 'video' else 'A'}{index + 1}",
             "name": props.findtext("MZ.TrackName") if props is not None else None,
             "muted": t.findtext(".//IsMuted") == "true",
             "locked": t.findtext(".//IsLocked") == "true",
             "items": [], "transitions": []}
        for ref in t.findall("ClipTrack/ClipItems/TrackItems/TrackItem"):
            it = self.ref(ref)
            if it is not None:
                d["items"].append(self.parse_item(it, kind))
        for ref in t.findall("ClipTrack/TransitionItems/TrackItems/TrackItem"):
            it = self.ref(ref)
            if it is not None:
                d["transitions"].append(self.parse_transition(it))
        if kind == "audio":
            d["track_effects"] = self.parse_chain(t.find("AudioTrack") if t.find("AudioTrack") is not None else t)
            # an audio track's mute button is the fader's Mute param, not IsMuted (AmazonQuick "Outro", A4; ep04's
            # 03/A1): fold it into "muted" so a reader can't take a muted bed for a live one
            fader_mute = [p.get("static") for c in d["track_effects"].get("components", [])
                          if c.get("tag") == "AudioFader" for p in c.get("params", []) if p["name"] == "Mute"]
            d["fader_muted"] = bool(fader_mute and fader_mute[0])
            d["muted"] = d["muted"] or d["fader_muted"]
        d["items"].sort(key=lambda x: x["start_ticks"])
        return d

    # -- flattening ---------------------------------------------------------------
    def shallow(self, uid):
        """Parse one sequence without recursing into nested sequences (cached)."""
        if not hasattr(self, "_shallow"):
            self._shallow = {}
        if uid not in self._shallow:
            self._shallow[uid] = self.parse_sequence(uid, _depth=99)
        return self._shallow[uid]

    def flatten(self, top_uid, kind, transitions_out=None, markers_out=None):
        """Map every clip of `kind` ('video'|'audio') in the nested-sequence tree onto
        top-level sequence time.

        A clip at child time u appears at top time a + b*u. Nested clip at parent
        [start,end) with source in-point `in` and speed `sp` maps child time u to parent
        time start + (u - in)/sp. Frame-held nested clips freeze the child at one
        instant ('frozen_child_t'); their descendants are listed but their keyframes are
        not mapped. Returns a list of flat items with times in seconds.
        """
        out = []
        top = self.shallow(top_uid)
        fr = top.get("frame_ticks")

        def keyframes_to_top(it, a, b, frozen, comps_in=None):
            comps = []
            for c in (it["effects"]["components"] if comps_in is None else comps_in):
                cc = {k: v for k, v in c.items() if k not in ("params", "sub_components")}
                if c.get("sub_components"):
                    cc["sub_components"] = keyframes_to_top(it, a, b, frozen, c["sub_components"])
                cc["params"] = []
                for p in c["params"]:
                    pp = dict(p)
                    if p.get("keyframes"):
                        ks = []
                        for k in p["keyframes"]:
                            kk = dict(k)
                            ct = (it["start_ticks"] + (k["t_ticks"] - it.get("src_in_ticks", 0)) / it.get("speed", 1.0)) / TPS
                            kk["t_seq_local_s"] = round(ct, 4)
                            kk["t_top_s"] = None if frozen else round(a + b * ct, 4)
                            del kk["t_ticks"]
                            ks.append(kk)
                        pp["keyframes"] = ks
                    cc["params"].append(pp)
                comps.append(cc)
            return comps

        def walk(uid, a, b, lo, hi, path, ipath, hidden, frozen_t):
            seq = self.shallow(uid)
            tracks = seq["video_tracks"] if kind == "video" else seq["audio_tracks"]
            if markers_out is not None and frozen_t is None:
                for m in seq.get("sequence_markers", []):
                    t = a + b * (m["t_ticks"] or 0) / TPS
                    if lo - 1e-6 <= t <= hi + 1e-6:
                        markers_out.append({"sequence": seq["name"], "t_top_s": round(t, 4),
                                            "duration_s": round((m["duration_ticks"] or 0) / TPS * b, 4),
                                            "name": m["name"], "comment": m["comment"], "type": m["type"]})
            for tr in tracks:
                if transitions_out is not None and frozen_t is None:
                    for t in tr["transitions"]:
                        ts, te = a + b * t["start_ticks"] / TPS, a + b * t["end_ticks"] / TPS
                        if te > lo + 1e-6 and ts < hi - 1e-6:
                            transitions_out.append({
                                "sequence": seq["name"], "track": tr["label"], "path": path + [f"{seq['name']}/{tr['label']}"],
                                "type": t["type"], "match_name": t["match_name"],
                                "top_start_s": round(ts, 4), "top_end_s": round(te, 4),
                                "duration_s": round(te - ts, 4),
                                "cut_point_top_s": round(ts + b * t["alignment_ticks"] / TPS, 4),
                                "has_outgoing": t["has_outgoing"], "has_incoming": t["has_incoming"]})
                tr_hidden = tr["muted"]
                if kind == "audio":
                    for c in tr.get("track_effects", {}).get("components", []):
                        for p in c["params"]:
                            if p["name"] == "Mute" and p.get("static") is True:
                                tr_hidden = True
                for idx, it in enumerate(tr["items"]):
                    s, e = it["start_ticks"] / TPS, it["end_ticks"] / TPS
                    if frozen_t is not None:
                        if not (s <= frozen_t < e):
                            continue
                        vlo, vhi = lo, hi
                    else:
                        vlo, vhi = max(lo, a + b * s), min(hi, a + b * e)
                    if vhi - vlo <= 1e-6:
                        continue
                    sp = it.get("speed", 1.0) or 1.0
                    src = it.get("source", {})
                    flat = {
                        "path": path + [f"{seq['name']}/{tr['label']}"],
                        "item_path": ipath + [f"{seq['name']}/{tr['label']}#{idx}"],
                        "depth": len(path),
                        "track": tr["label"],
                        "top_start_s": round(vlo, 4), "top_end_s": round(vhi, 4),
                        "top_dur_s": round(vhi - vlo, 4),
                        "local_start_s": round(s, 4), "local_end_s": round(e, 4),
                        "name": src.get("sequence_name") or (src.get("title") if src.get("title") and "/" in src.get("title") and src.get("file_path") and src["file_path"].lower().endswith((".psd", ".ai"))  # layered PSD/AI import: "Layer/file.psd"
                                                             else Path(src["file_path"].replace("\\", "/")).name if src.get("file_path") else src.get("title") or it.get("subclip_name")),
                        "source": src,
                        "src_in_s": sec(it.get("src_in_ticks")),
                        "src_out_s": sec(it.get("src_out_ticks")),
                        "speed": sp, "effective_speed": round(sp / b, 6) if b else None,
                        "reverse": it.get("reverse", False),
                        "frame_hold": {"1": "in_point", "2": "out_point", "4": "playhead"}.get(it.get("frame_hold_raw"), it.get("frame_hold_raw")) if it.get("frame_hold_raw") else None,
                        "inside_frozen_parent": frozen_t is not None,
                        "hidden_or_muted": hidden or tr_hidden,
                        "clip_markers": it.get("clip_markers", []),
                        "components": keyframes_to_top(it, a, b, frozen_t is not None),
                    }
                    out.append(flat)
                    if src.get("kind") == "nested_sequence" and src.get("sequence_uid") and len(path) < 8:
                        cin = it.get("src_in_ticks", 0) / TPS
                        if frozen_t is not None:
                            child_frozen = cin + (frozen_t - s) * sp
                        elif it.get("frame_hold_raw") == "1":
                            child_frozen = cin
                        elif it.get("frame_hold_raw") == "2":
                            child_frozen = (it.get("src_out_ticks") or it.get("src_in_ticks")) / TPS - (fr or 0) / TPS
                        else:
                            child_frozen = None
                        na, nb = a + b * (s - cin / sp), b / sp
                        walk(src["sequence_uid"], na, nb, vlo, vhi, flat["path"], flat["item_path"], hidden or tr_hidden, child_frozen)

        dur = top["duration_ticks"] / TPS
        walk(top_uid, 0.0, 1.0, 0.0, dur, [], [], False, None)
        out.sort(key=lambda x: (x["top_start_s"], x["depth"]))
        return out

    def parse_sequence(self, key, _depth=0, _seen=None):
        s = self.find_sequence(key)
        _seen = _seen if _seen is not None else {}
        out = {"uid": s.get("ObjectUID"), "name": s.findtext("Name"), "exports": self._exports(s),
               "video_tracks": [], "audio_tracks": [], "data_tracks": 0}
        for tg in s.findall("TrackGroups/TrackGroup"):
            g = self.ref(tg.find("Second"))
            if g is None:
                continue
            if g.tag == "VideoTrackGroup":
                fr = int(g.findtext("TrackGroup/FrameRate"))
                out["frame_ticks"] = fr
                out["fps"] = round(TPS / fr, 3)
                out["frame_rect"] = g.findtext("FrameRect")
                kind, key2 = "video", "video_tracks"
            elif g.tag == "AudioTrackGroup":
                kind, key2 = "audio", "audio_tracks"
            else:
                out["data_tracks"] = len(g.findall("TrackGroup/Tracks/Track"))
                out["caption_tracks"] = []
                for i, tr in enumerate(g.findall("TrackGroup/Tracks/Track")):
                    t = self.ref(tr)
                    if t is None:
                        continue
                    cues = []
                    for ref in t.findall(".//ClipItems/TrackItems/TrackItem"):
                        it = self.ref(ref)
                        if it is None:
                            continue
                        ti = it.find(".//ClipTrackItem/TrackItem")
                        texts, caption = [], None
                        for b in it.findall("BlockVector/BlockVectorItem"):
                            blk = self.ref(b)
                            ftd = self.value(blk.find("FormattedTextData")) if blk is not None else None
                            if ftd:
                                texts += extract_strings(ftd)
                                caption = caption or decode_caption(ftd)
                        cues.append({"start_s": sec(int(ti.findtext("Start") or 0)), "end_s": sec(int(ti.findtext("End"))),
                                     "strings": texts, "caption": caption})
                    props = t.find(".//Track/Node/Properties")
                    out["caption_tracks"].append({"index": i, "tag": t.tag, "muted": t.findtext(".//IsMuted") == "true",
                                                  "name": props.findtext("MZ.TrackName") if props is not None else None,
                                                  "cues": cues})
                continue
            for i, tr in enumerate(g.findall("TrackGroup/Tracks/Track")):
                t = self.ref(tr)
                if t is not None:
                    out[key2].append(self.parse_track(t, kind, i))
        ends = [it["end_ticks"] for k in ("video_tracks", "audio_tracks") for tr in out[k] for it in tr["items"]]
        out["duration_ticks"] = max(ends) if ends else 0
        mc = self._seq_master.get(s.get("ObjectUID"))
        out["sequence_markers"] = []
        if mc is not None:
            seen = set()
            for c in mc.findall("Clips/Clip"):
                clip = self.ref(c)
                if clip is None:
                    continue
                for m in self.markers(clip.find("Clip/MarkerOwner/Markers")):
                    k = (m["t_ticks"], m["name"], m["comment"])
                    if k not in seen:
                        seen.add(k)
                        out["sequence_markers"].append(m)
        if _depth >= 99:  # shallow parse
            out["nested_sequence_uids"] = {
                it["source"]["sequence_uid"]: it["source"]["sequence_name"]
                for k in ("video_tracks", "audio_tracks") for tr in out[k] for it in tr["items"]
                if it.get("source", {}).get("kind") == "nested_sequence"}
            return out
        # nested sequences (recursive, once each)
        nested = {}
        for k in ("video_tracks", "audio_tracks"):
            for tr in out[k]:
                for it in tr["items"]:
                    src = it.get("source", {})
                    if src.get("kind") == "nested_sequence" and src.get("sequence_uid") and _depth < 4:
                        uid = src["sequence_uid"]
                        if uid not in _seen:
                            _seen[uid] = None
                            _seen[uid] = self.parse_sequence(uid, _depth + 1, _seen)
                        nested[uid] = src["sequence_name"]
        out["nested_sequence_uids"] = nested
        if _depth == 0:
            out["nested_sequences"] = {u: v for u, v in _seen.items() if v is not None}
        return out


class _FB:
    """Just enough FlatBuffers to read a table's fields by number."""

    def __init__(self, buf: bytes):
        self.b = buf

    def u8(self, o): return self.b[o]
    def u16(self, o): return struct.unpack_from("<H", self.b, o)[0]
    def u32(self, o): return struct.unpack_from("<I", self.b, o)[0]
    def i32(self, o): return struct.unpack_from("<i", self.b, o)[0]
    def f32(self, o): return struct.unpack_from("<f", self.b, o)[0]

    def field(self, t, i):
        """Absolute offset of field i of the table at t, or None when absent (the schema default applies)."""
        vt = t - self.i32(t)
        if 4 + 2 * i >= self.u16(vt):
            return None
        o = self.u16(vt + 4 + 2 * i)
        return t + o if o else None

    def table(self, t, i):
        p = self.field(t, i)
        return None if p is None else p + self.u32(p)

    def vector(self, t, i):
        p = self.field(t, i)
        if p is None:
            return []
        v = p + self.u32(p)
        return [v + 4 + 4 * k + self.u32(v + 4 + 4 * k) for k in range(self.u32(v))]

    def string(self, t, i):
        p = self.field(t, i)
        if p is None:
            return None
        s = p + self.u32(p)
        return self.b[s + 4:s + 4 + self.u32(s)].decode("utf-8", "replace")


GRID = ["top-left", "top-centre", "top-right", "middle-left", "middle-centre", "middle-right",
        "bottom-left", "bottom-centre", "bottom-right"]
ALIGN = {0: "left", 1: "right", 2: "centre"}            # 1 is a guess: only 0 (absent) and 2 have been seen


def decode_caption(b64: str) -> dict | None:
    """One caption block's text and look. Field numbers are those of the root's first table (GOTCHAS):
    0 text runs (each: 0 text, 1 style with 1 = font size), 4 alignment (absent = left), 17 box RGB (3 bytes),
    18 box on, 19 box opacity %, 33 grid position (0..8 from top-left; absent = bottom-centre), 34 corner radius."""
    try:
        raw = base64.b64decode(re.sub(r"\s+", "", b64))
    except ValueError:
        return None
    if len(raw) < 16 or raw[8:12] != bytes.fromhex("44332211"):
        return None
    fb = _FB(raw[12:])
    t = fb.table(fb.u32(0), 0)
    if t is None:
        return None
    runs = fb.vector(t, 0)
    text = "".join(fb.string(r, 0) or "" for r in runs)
    size = None
    if runs and fb.table(runs[0], 1) is not None and fb.field(fb.table(runs[0], 1), 1) is not None:
        size = round(fb.f32(fb.field(fb.table(runs[0], 1), 1)), 2)
    opt = lambda i, read, default=None: default if fb.field(t, i) is None else read(fb.field(t, i))
    rgb_t = fb.table(t, 17)
    rgb = None if rgb_t is None else [0 if fb.field(rgb_t, k) is None else fb.u8(fb.field(rgb_t, k)) for k in range(3)]
    grid_t = fb.table(t, 33)
    grid = 7 if grid_t is None or fb.field(grid_t, 0) is None else fb.u32(fb.field(grid_t, 0))
    return {"text": text, "lines": text.split("\r"), "font_size": size,
            "align": ALIGN.get(opt(4, fb.u32, 0), str(opt(4, fb.u32, 0))),
            "box_on": bool(opt(18, fb.u8, 0)),
            "box_rgb": rgb, "box_hex": None if rgb is None else "#" + "".join(f"{v:02X}" for v in rgb),
            "box_opacity": round(opt(19, fb.f32, 0.0), 2),
            "grid": GRID[grid] if 0 <= grid < 9 else str(grid),
            "corner_radius": round(opt(34, fb.f32, 0.0), 2)}


def extract_strings(b64: str) -> list[str]:
    """Heuristic: find length-prefixed (uint32 LE) UTF-8 strings in a flatbuffer blob."""
    try:
        data = base64.b64decode(re.sub(r"\s+", "", b64))
    except ValueError:
        return []
    found = []
    for i in range(0, len(data) - 5):
        (n,) = struct.unpack_from("<I", data, i)
        if 1 <= n <= 4000 and i + 4 + n < len(data) and data[i + 4 + n] == 0:
            chunk = data[i + 4:i + 4 + n]
            try:
                s = chunk.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if all(ch.isprintable() or ch in "\r\n\t" for ch in s) and any(ch.isalpha() for ch in s):
                found.append(s)
    # de-dup preserving order
    seen, res = set(), []
    for s in found:
        if s not in seen:
            seen.add(s)
            res.append(s)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("project")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--sequence")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(errors="replace")
    p = Project(a.project)
    if a.list:
        for s in p.sequences():
            print(json.dumps(s))
        return
    if a.sequence:
        d = p.parse_sequence(a.sequence)
        txt = json.dumps(d, indent=1, default=str)
        if a.out:
            Path(a.out).write_text(txt, encoding="utf-8")
        else:
            print(txt)


if __name__ == "__main__":
    main()
