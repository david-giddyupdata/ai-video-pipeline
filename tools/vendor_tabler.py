"""R153: Tabler outline icons (github.com/tabler/tabler-icons, MIT) as path data for the overlay library.

    python tools/vendor_tabler.py [<name> ...]     # default: the list below

Writes remotion/src/overlays/vendor/tabler/icons.ts: each icon a list of SVG path strings on Tabler's 24x24 grid
(circles, lines, rects, polylines and ellipses converted to paths), so a composition can draw each stroke on with
@remotion/paths evolvePath, recolour it from the tokens, or scale it. Tabler's own invisible bounding path
("M0 0h24v24H0z") is dropped. A name Tabler doesn't have is reported and skipped. Re-run to refresh.
"""
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "remotion" / "src" / "overlays" / "vendor" / "tabler"
RAW = "https://raw.githubusercontent.com/tabler/tabler-icons/main/"
DEFAULT = ["hourglass", "hourglass-high", "hourglass-low", "hourglass-empty", "pin", "pinned", "plane",
           "plane-arrival", "plane-departure", "salt", "bottle", "app-window", "file-spreadsheet", "table", "map-pin",
           "map", "stack-2", "pointer", "click", "hand-click", "number-123", "abc", "calendar-event", "file-type-csv",
           "file-type-xls", "world", "search", "zoom-in", "lock", "lock-open", "chart-bar", "chart-line", "filter",
           "layout-dashboard", "cloud", "database", "clock", "arrow-right", "arrow-down", "check", "circle-check",
           "x", "file", "files", "folder", "tag", "eye", "list-check", "checkbox", "stamp", "rubber-stamp",
           "device-desktop", "browser", "arrows-horizontal", "arrows-minimize", "layers-subtract", "rotate",
           "calendar", "calendar-month", "clock-hour-4", "alarm", "bell", "bell-ringing", "thumb-up"]


def fmt(v):
    return f"{float(v):g}"


def to_path(el):
    tag, a = el.tag.split("}")[-1], el.attrib
    if tag == "path":
        return a["d"]
    if tag == "circle":
        cx, cy, r = (float(a[k]) for k in ("cx", "cy", "r"))
        return f"M{fmt(cx - r)} {fmt(cy)}a{fmt(r)} {fmt(r)} 0 1 0 {fmt(2 * r)} 0a{fmt(r)} {fmt(r)} 0 1 0 {fmt(-2 * r)} 0"
    if tag == "ellipse":
        cx, cy, rx, ry = (float(a[k]) for k in ("cx", "cy", "rx", "ry"))
        return (f"M{fmt(cx - rx)} {fmt(cy)}a{fmt(rx)} {fmt(ry)} 0 1 0 {fmt(2 * rx)} 0"
                f"a{fmt(rx)} {fmt(ry)} 0 1 0 {fmt(-2 * rx)} 0")
    if tag == "line":
        return f"M{a['x1']} {a['y1']}L{a['x2']} {a['y2']}"
    if tag in ("polyline", "polygon"):
        pts = re.split(r"[\s,]+", a["points"].strip())
        pairs = [f"{pts[i]} {pts[i + 1]}" for i in range(0, len(pts) - 1, 2)]
        return "M" + "L".join(pairs) + ("Z" if tag == "polygon" else "")
    if tag == "rect":
        x, y, w, h = (float(a.get(k, 0)) for k in ("x", "y", "width", "height"))
        r = float(a.get("rx", 0))
        if not r:
            return f"M{fmt(x)} {fmt(y)}h{fmt(w)}v{fmt(h)}h{fmt(-w)}Z"
        return (f"M{fmt(x + r)} {fmt(y)}h{fmt(w - 2 * r)}a{fmt(r)} {fmt(r)} 0 0 1 {fmt(r)} {fmt(r)}v{fmt(h - 2 * r)}"
                f"a{fmt(r)} {fmt(r)} 0 0 1 {fmt(-r)} {fmt(r)}h{fmt(-(w - 2 * r))}a{fmt(r)} {fmt(r)} 0 0 1 {fmt(-r)} {fmt(-r)}"
                f"v{fmt(-(h - 2 * r))}a{fmt(r)} {fmt(r)} 0 0 1 {fmt(r)} {fmt(-r)}Z")
    return None


def main(names):
    icons, missing = {}, []
    for n in names:
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{RAW}icons/outline/{n}.svg",
                                                               headers={"User-Agent": "aidv-vendor/1.0"}), timeout=60) as r:
                root = ET.fromstring(r.read())
        except urllib.error.HTTPError:
            missing.append(n)
            continue
        paths = [p for p in (to_path(el) for el in root.iter()) if p and p.replace(" ", "") != "M0 0h24v24H0z".replace(" ", "")]
        icons[n] = paths
    OUT.mkdir(parents=True, exist_ok=True)
    body = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in icons.items())
    (OUT / "icons.ts").write_text(
        "// Tabler outline icons (github.com/tabler/tabler-icons, MIT, LICENSE beside this file), written by\n"
        "// tools/vendor_tabler.py: each icon a list of SVG paths on a 24x24 grid, drawn with a 2 px round stroke.\n"
        "export type TablerName = keyof typeof TABLER;\n"
        f"export const TABLER = {{\n{body},\n}} as const;\n", encoding="utf-8")
    with urllib.request.urlopen(urllib.request.Request(RAW + "LICENSE", headers={"User-Agent": "aidv-vendor/1.0"}),
                                timeout=60) as r:
        (OUT / "LICENSE").write_bytes(r.read())
    print(f"{len(icons)} icons" + (f"; not in Tabler: {missing}" if missing else ""))


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
