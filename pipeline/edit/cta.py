"""R242, R243: the "Amazon Quick Series" card and the call to action's subscribe animation, as the stage places them.
The Python side of remotion/src/overlays/data/cta.json (one copy of the timing and placement, read by SeriesCard.tsx,
SubscribeCta.tsx, tools/remotion_ctas.py and pipeline.edit.stage): each piece's layer (the props AvatarStage draws it
from, seconds on the stage clip's clock) and its sound cues (S9, R158, R235).

  * the series card (SeriesCard.tsx): in at the intro's t0S, its span spanS as QuickArch03 (settled settledS after t0,
    the exit mirrored about t1, nothing drawn in its first and last drawnFromS, its title only after goneS), at
    box; its whoosh whooshAtS after t0 (seriesCardMoments);
  * the subscribe animation (SubscribeCta.tsx subscribeTimes): round 7's hooks on the words "subscribe" and "thumbs"
    (their starts on the outro's clock): t0 leadS before "subscribe", the bell's click bellS after it, the thumb's
    click thumbAfterWordS into "thumbs" (never closer than minBellToThumbS after the bell), t1 at least lengthS after
    t0 and afterThumbS after the thumb; its sounds (subscribeMoments): the whoosh whooshAtS[variant] after t0, the bell
    on the bell's click, R137's click on the thumb's.

series_layer checks the card's words fit its box before anything renders (series_fit, GAPS_PLAN 10): each line and
the title measured in the card's font (Berlin Sans FB Demi, SeriesCard.tsx's CARD_FONT) at SeriesCard.tsx's sizes,
against the text's room in the box: its width less the inner panel's insets and the text's padding on both sides,
725 px of the 821. The right margin is this check's rule, not the layout's: the .tsx pads the panel's text on the
left only (a line could draw to 750 px of the panel, 798 of the card; the title to 773), so the check asks for a
right margin equal to the left and is only ever stricter than the render. Over FIT_STOP the stage stops (a 15-minute render would show the line cut off), from 0 to FIT_STOP it
warns (PIL and Chrome differ by a few px); the lines and the title must fit the box's height too. The wording is the
exercise's (its steps file's stage.quick.series; R243: the card's wording and size). Checked alone, before a stage:

    python -m pipeline.edit.cta fit exercises/<ex>/avatar_<prefix>.json        # exit 1 when the stage would stop
"""
import json
import math
import sys

from pipeline.config import ROOT

CTA = json.loads((ROOT / "remotion" / "src" / "overlays" / "data" / "cta.json").read_text(encoding="utf-8"))
ORIGINAL = CTA["subscribe"]["original"]
VARIANTS = ("classic", "brand", "pill", "soft")
# the subscribe variations' Remotion compositions (remotion/src/Root.tsx), for the piece rendered alone
COMPOSITIONS = {"classic": "SubscribeClassic", "brand": "SubscribeBrand", "pill": "SubscribePill",
                "soft": "SubscribeSoft"}
# "Thanks for Watching!" in every variation (right of the bar or the pill's divider), frame px (x0, y0, x1, y1)
TEXT_BOX = (530, 780, 1400, 886)


# SeriesCard.tsx's layout (the same numbers; tests/test_cta_fit.py reads them back from the .tsx): the font, the
# title's and the lines' sizes and line heights, the inner panel's side inset and the text's padding (of the card's
# width), the panel's vertical padding and the gap above it
CARD_FONT_FILE = r"C:\Windows\Fonts\BRLNSDB.TTF"          # Berlin Sans FB Demi (Chrome's "Berlin Sans FB" at 600)
TITLE_PX, LINE_PX = 64, 56
TITLE_LH, LINE_LH = 1.15, 1.12
INSET, TEXT_PAD = 0.0275, 0.031
PAD_V, GAP = 14, 10
FIT_STOP = 0.02                  # over the room by more than this: stop; by 0 to this: warn


def series_fit(title, lines, box=None):
    """How the card's words fit its box (the module's docstring): {"room_px", "lines": [{"text", "px", "over"}],
    "title": {...}, "height": {"need_px", "box_px"}, "warnings", "stop"} (over: the share past the room, negative when
    inside it)."""
    from PIL import ImageFont
    b = box or CTA["series"]["box"]
    w = b["w"]
    js_round = lambda x: math.floor(x + 0.5)             # Math.round, as the .tsx rounds (Python rounds halves to even)
    room = w - 2 * js_round(INSET * w) - 2 * js_round(TEXT_PAD * w)
    try:
        fonts = {px: ImageFont.truetype(CARD_FONT_FILE, px) for px in (TITLE_PX, LINE_PX)}
    except OSError:
        raise SystemExit(f"the series card's font {CARD_FONT_FILE} (Office's Berlin Sans FB Demi) isn't on this PC: "
                         "its words can't be measured, and Chrome would draw the stand-in (Inter)")
    meas = lambda text, px: {"text": text, "px": round(fonts[px].getlength(text), 1),
                             "over": round(fonts[px].getlength(text) / room - 1, 4)}
    got = {"room_px": room, "box": dict(b), "title": meas(title, TITLE_PX), "lines": [meas(t, LINE_PX) for t in lines]}
    need = js_round(TITLE_PX * TITLE_LH) + GAP + len(lines) * js_round(LINE_PX * LINE_LH) + 2 * PAD_V
    got["height"] = {"need_px": need, "box_px": b["h"]}
    warn, stop = [], []
    for kind, m in [("title", got["title"])] + [("line", x) for x in got["lines"]]:
        if m["over"] > FIT_STOP:
            stop.append(f"the series card's {kind} \"{m['text']}\" is {m['px']:.0f} px wide in the card's font, "
                        f"{m['over']:.1%} past its {room} px: shorter words (R243: the wording is the exercise's)")
        elif m["over"] > 0:
            warn.append(f"the series card's {kind} \"{m['text']}\" is {m['px']:.0f} px, {m['over']:.1%} past its "
                        f"{room} px (inside {FIT_STOP:.0%}: PIL and Chrome differ by a few px; check its render)")
    if not lines:
        stop.append("the series card has no line")
    if need > b["h"]:
        stop.append(f"the series card's title and {len(lines)} line(s) need {need} px of height, its box {b['h']}")
    got["warnings"], got["stop"] = warn, stop
    return got


def series_layer(title, lines, t0=None):
    """SeriesCard's layer: in at t0 (cta.json's t0S by default) for spanS, at cta.json's box; its words checked
    against the box first (series_fit: a stop raises, a warning prints)."""
    s = CTA["series"]
    t0 = s["t0S"] if t0 is None else t0
    fit = series_fit(title, lines, s["box"])
    if fit["stop"]:
        raise SystemExit("; ".join(fit["stop"]))
    for w in fit["warnings"]:
        print(f"WARNING: {w}", file=sys.stderr)
    return {"t0": t0, "t1": t0 + s["spanS"], "title": title, "lines": list(lines), "box": dict(s["box"])}


def series_shown(layer):
    """The seconds the card draws anything (its black base comes before the title): (t0 + drawnFromS, t1 -
    drawnFromS)."""
    g = CTA["series"]["drawnFromS"]
    return layer["t0"] + g, layer["t1"] - g


def series_settled(layer):
    """The seconds the card is whole and still: (t0 + settledS, t1 - settledS)."""
    s = CTA["series"]["settledS"]
    return layer["t0"] + s, layer["t1"] - s


def series_moments(layer):
    """seriesCardMoments: [(seconds, sound)]."""
    return [(layer["t0"] + CTA["series"]["whooshAtS"], "whoosh")]


def subscribe_times(words):
    """SubscribeCta.tsx subscribeTimes (the same rule): from the starts of "subscribe" and "thumbs" (seconds on the
    clip's clock) to {t0, bell, thumb, t1}; never before the clip's start; the thumb's click never inside the exit."""
    S = CTA["subscribe"]
    t0 = max(0.0, words["subscribe"] - ORIGINAL["leadS"])
    bell = max(t0 + ORIGINAL["bellS"], words["subscribe"] + ORIGINAL["bellS"] - ORIGINAL["leadS"])
    thumb = max(bell + S["minBellToThumbS"], words["thumbs"] + S["thumbAfterWordS"])
    return {"t0": t0, "bell": bell, "thumb": thumb, "t1": max(t0 + ORIGINAL["lengthS"], thumb + S["afterThumbS"])}


def subscribe_layer(variant, text, words):
    """SubscribeAnim's layer for a variation (R243: "brand"), timed on the words."""
    if variant not in VARIANTS:
        raise SystemExit(f"no subscribe variation {variant!r} (one of {VARIANTS})")
    return {"variant": variant, "text": text, **subscribe_times(words)}


def subscribe_moments(layer):
    """subscribeMoments: [(seconds, sound)]: the whoosh as the entrance starts moving, the bell on the bell's click,
    R137's click on the thumb's."""
    return [(layer["t0"] + CTA["subscribe"]["whooshAtS"][layer["variant"]], "whoosh"), (layer["bell"], "bell"),
            (layer["thumb"], "click")]


def main(argv=None):
    """python -m pipeline.edit.cta fit <avatar steps.json>: the steps file's series card (stage.quick.series) against
    its box (series_fit), before any stage render; exit 1 when it would stop the stage."""
    import argparse
    from pathlib import Path
    ap = argparse.ArgumentParser(description="the series card's words against its box (series_fit)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("steps", help="the exercise's avatar steps file (exercises/<ex>/avatar_<prefix>.json)")
    a = ap.parse_args(argv)
    ser = json.loads(Path(a.steps).read_text(encoding="utf-8"))["stage"]["quick"].get("series")
    if not ser:
        raise SystemExit(f"{a.steps} has no stage.quick.series (R243)")
    got = series_fit(ser["title"], ser["lines"])
    print(json.dumps(got, indent=1, ensure_ascii=False))
    return 1 if got["stop"] else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
