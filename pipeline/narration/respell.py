"""Display text -> spoken text (SPEC §5.5), keeping a character map so word timings can be read back in display text.

Matching is whole-word and case-sensitive, and the longest match wins. A term may give a different spelling per engine
(`by_engine`), since each voice stumbles on different words.
"""
import json
import re

from pipeline.config import EXERCISES


def load_terms(exercise, engine, own="pronunciation.json"):
    """The common spoken forms, then the exercise's own (own: its file name; a second voice may have its own file)."""
    terms = []
    for path in (EXERCISES / "pronunciation_common.json", EXERCISES / exercise / own):
        if path.exists():
            for t in json.loads(path.read_text(encoding="utf-8"))["terms"]:
                spoken = t.get("by_engine", {}).get(engine, t["spoken"])
                if spoken != t["display"]:
                    terms.append({"display": t["display"], "spoken": spoken, "tighten": t.get("tighten", False)})
    return sorted(terms, key=lambda t: -len(t["display"]))


def respell(text, terms, override=None):
    """Returns (spoken, pieces, tighten). pieces: (disp_start, disp_end, spoken_start, spoken_end, respelled), covering
    both texts in order."""
    if override:                                    # narration.spoken: a one-off for this line, mapped as one piece
        return override, [(0, len(text), 0, len(override), True)], []
    if terms:
        pat = re.compile(r"(?<![\w-])(" + "|".join(re.escape(t["display"]) for t in terms) + r")(?![\w-])")
        by = {t["display"]: t for t in terms}
    pieces, out, tighten, pos, sp = [], [], [], 0, 0
    for m in (pat.finditer(text) if terms else []):
        if m.start() > pos:
            plain = text[pos:m.start()]
            pieces.append((pos, m.start(), sp, sp + len(plain), False))
            out.append(plain)
            sp += len(plain)
        t = by[m.group(1)]
        pieces.append((m.start(), m.end(), sp, sp + len(t["spoken"]), True))
        out.append(t["spoken"])
        sp += len(t["spoken"])
        if t["tighten"]:
            tighten.append(t["display"])
        pos = m.end()
    if pos < len(text):
        pieces.append((pos, len(text), sp, sp + len(text) - pos, False))
        out.append(text[pos:])
    return "".join(out), pieces, sorted(set(tighten))


def spoken_to_display(pieces, s0, s1):
    """Spoken character range -> display character range. Inside a respelled term, the whole term."""
    d0 = d1 = None
    for ds, de, ss, se, respelled in pieces:
        if se <= s0 or ss >= s1:
            continue
        lo = ds if respelled else ds + (max(s0, ss) - ss)
        hi = de if respelled else ds + (min(s1, se) - ss)
        d0 = lo if d0 is None else min(d0, lo)
        d1 = hi if d1 is None else max(d1, hi)
    return d0, d1
