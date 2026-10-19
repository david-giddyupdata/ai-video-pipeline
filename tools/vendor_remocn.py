"""R153: copy chosen remocn pieces (github.com/Remocn/remocn, MIT) into the overlay library, without its installer.

    python tools/vendor_remocn.py [<name> ...]     # default: the list below

Each registry artifact (registry-artifacts/<name>.json) holds its source; it is written to
remotion/src/overlays/vendor/remocn/<name>/index.ts(x) with a provenance header, its shadcn path aliases rewritten to
relative imports, "use client" dropped, and the Google-fonts JetBrains Mono loader replaced by the library's data font
(FONT.data in kit.tsx: Courier New first, R143; the bundled JetBrains Mono behind it, R148). Registry dependencies are
followed. The pieces use spring() and their own timings: a composition that uses one sets its timing from the tokens
(R131's no-overshoot easing). Re-run to refresh; files are overwritten.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "remotion" / "src" / "overlays" / "vendor" / "remocn"
RAW = "https://raw.githubusercontent.com/Remocn/remocn/main/"
DEFAULT = ["icons-core", "icon-database", "icon-cloud", "icon-upload", "icon-search", "icon-lock", "icon-calendar",
           "icon-clock", "icon-timer", "icon-monitor", "icon-check", "icon-check-circle", "icon-file-text",
           "icon-bar-chart-3", "icon-trending-down", "icon-filter", "icon-layout-grid", "icon-arrow-right",
           "icon-arrow-down", "icon-download", "icon-image", "matrix-decode", "rolodex-flip", "number-wheel",
           "rolling-number", "marker-highlight", "ink-arrow", "ink-underline", "scribble-circle",
           "animated-bar-chart", "animated-line-chart"]
ALIASES = {"@/lib/remocn-icons": "../icons-core", "@/lib/remocn/stop-motion": "../stop-motion",
           "@/components/remocn/brush": "../brush"}
HEADER = ("// Vendored from github.com/Remocn/remocn (MIT, LICENSE beside this folder), registry-artifacts/{name}.json,\n"
          "// fetched {date} by tools/vendor_remocn.py: path aliases made relative, \"use client\" dropped{font}.\n"
          "// Icon paths are Lucide's (ISC, LICENSE-lucide). Edit the composition that uses it, not this file.\n")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "aidv-vendor/1.0"}), timeout=60) as r:
        return r.read().decode("utf-8")


def rewrite(src):
    font = ""
    src = re.sub(r'^\s*"use client";\s*\n', "", src)
    for a, rel in ALIASES.items():
        src = src.replace(f'"{a}"', f'"{rel}"')
    # R131: no overshoot but the asides. remocn's springs are underdamped (icons-core: damping 18, stiffness 220,
    # mass 0.7, about 4% overshoot), so every spring here is clamped.
    src, n = re.subn(r"(spring\(\{[^;]*?config:\s*\{)", r"\1 overshootClamping: true,", src, flags=re.S)
    src, m = re.subn(r"config: args\.config,", "config: {...args.config, overshootClamping: true},", src)
    n += m
    if n:
        font += ", springs clamped (no overshoot, R131)"
    if "@remotion/google-fonts/JetBrainsMono" in src:
        src = re.sub(r'import \{ loadFont as (\w+) \} from "@remotion/google-fonts/JetBrainsMono";\n',
                     'import {FONT} from "../../../kit";\n', src)
        src = re.sub(r"const \{ fontFamily: (\w+) \} = \w+\(\);", r"const \1 = FONT.data.fontFamily as string;", src)
        font = ", the Google-fonts loader swapped for FONT.data"
    return src, font


def vendor(names, date):
    done, todo = set(), list(names)
    while todo:
        name = todo.pop(0)
        if name in done:
            continue
        art = json.loads(get(f"{RAW}registry-artifacts/{name}.json"))
        for dep in art.get("registryDependencies") or []:
            todo.append(dep.split("/")[-1])
        for f in art.get("files", []):
            src, font = rewrite(f["content"])
            dst = OUT / name / Path(f["path"]).name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(HEADER.format(name=name, date=date, font=font) + src, encoding="utf-8")
        npm = [d for d in art.get("dependencies") or [] if d not in ("remotion", "@remotion/paths", "react",
                                                                     "@remotion/google-fonts")]
        print(f"{name}: {len(art.get('files', []))} file(s)" + (f"; npm deps {npm}" if npm else ""))
        done.add(name)
    (OUT / "LICENSE").write_text(get(RAW + "LICENSE"), encoding="utf-8")
    (OUT / "LICENSE-lucide").write_text(get("https://raw.githubusercontent.com/lucide-icons/lucide/main/LICENSE"),
                                        encoding="utf-8")


if __name__ == "__main__":
    import datetime
    vendor(sys.argv[1:] or DEFAULT, datetime.date.today().isoformat())
