"""Sentence breaks inside a narration line, and whether each sentence explains or instructs (R62).

A sentence instructs when one of its clauses starts with an imperative verb ("Open the data folder,", "If a notice
offers to install ..., close it with the X."); otherwise it explains. Shared by the planner (where to put a
mode-switch beat) and the Premiere read-back (what a beat David inserted sits between).
"""
import re

IMPERATIVE = {
    "add", "check", "choose", "click", "close", "collapse", "copy", "create", "delete", "double-click", "drag",
    "enter", "expand", "find", "go", "hover", "look", "move", "open", "paste", "pick", "press", "remove", "rename",
    "right-click", "run", "save", "scroll", "select", "set", "sign", "start", "switch", "type", "use", "wait",
}
LEAD_INS = {"and", "then", "now", "next", "first", "so", "just", "finally", "also"}
# a full stop that ends an abbreviation, not a sentence ("U.S. flight data", "e.g. a map")
ABBREV = re.compile(r"(?<![\w.])(?:(?:[A-Za-z]\.){2,}|(?:e\.g|i\.e|etc|vs|approx|Dr|Mr|Mrs|Ms|St)\.)$")
NUMBERED = re.compile(r"(?<![\w.])No\.$")             # "No. 5": an abbreviation only before a number


def mode(sentence):
    """'instruct' or 'explain'."""
    for clause in re.split(r"[,;:]", sentence):
        words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]*", clause)]
        while words and words[0] in LEAD_INS:
            words = words[1:]
        if words and words[0] in IMPERATIVE:
            return "instruct"
    return "explain"


def breaks(display, words):
    """Sentence breaks between timed words: [{after (word index), at_s (mid-pause, where a line can be split),
    pause_s, before, after_text, before_mode, after_mode}]. A full stop inside a word (a URL, a file name) is not a
    break, and neither is the stop after an abbreviation (ABBREV)."""
    out, s0 = [], 0
    for i in range(len(words) - 1):
        between = display[words[i]["char"][1]:words[i + 1]["char"][0]]
        head = display[:words[i]["char"][1]] + between.strip()
        if not re.search(r"[.?!]", between) or ABBREV.search(head) or \
                (NUMBERED.search(head) and words[i + 1]["word"][:1].isdigit()):
            continue
        before = display[s0:words[i]["char"][1]].strip() + between.strip()
        nxt_end = next((words[j]["char"][1] for j in range(i + 1, len(words) - 1)
                        if re.search(r"[.?!]", display[words[j]["char"][1]:words[j + 1]["char"][0]])), len(display))
        after = display[words[i + 1]["char"][0]:nxt_end].strip()
        out.append({"after": i, "at_s": round((words[i]["end"] + words[i + 1]["start"]) / 2, 4),
                    "pause_s": round(words[i + 1]["start"] - words[i]["end"], 4),
                    "before_text": before, "after_text": after, "before_mode": mode(before), "after_mode": mode(after)})
        s0 = words[i + 1]["char"][0]
    return out


def word_at(display, words, t, n=6):
    """The n words either side of time t in a line: ('...last words before', 'first words after...')."""
    i = sum(1 for w in words if w["end"] <= t)
    left = display[words[max(0, i - n)]["char"][0]:words[i - 1]["char"][1] + 1].strip() if i else ""
    right = display[words[i]["char"][0]:words[min(len(words), i + n) - 1]["char"][1] + 1].strip() if i < len(words) else ""
    return left, right
