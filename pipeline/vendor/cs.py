"""Browser helpers for the workshop's Edge window.

Copied 2026-10-06 from
  <DOCUMENTS_DIR>\\Learning-David-Pc\\Workshops\\2026-10-08_<CLIENT>\\automation\\cs.py
Changes: removed ROOT/EXERCISE/SHOT_DIR and shot()/peek() (manual screenshots); page() can match an exact host
(workshop lesson: the editor tab and the -8050 app tab share the codespace name, so a prefix match picks the wrong tab);
CDP URL comes from pipeline.config, read when the browser connects (2026-10-14: a step list's `browser`
switches it, R113). The workshop original is untouched.
"""
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from pipeline import config

_pw = None
_browser = None


def browser():
    global _pw, _browser
    if _browser is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.connect_over_cdp(config.CDP_URL)
    return _browser


def context():
    return browser().contexts[0]


def page(url_contains=None, host=None):
    """Tab whose host equals `host`, or whose URL contains `url_contains`; else the last tab."""
    pages = context().pages
    for pg in pages:
        if (host and urlparse(pg.url).hostname == host) or (url_contains and url_contains in pg.url):
            return pg
    return pages[-1] if pages else context().new_page()


def find(pg, selector=None, text=None, exact=True):
    """First visible element in the page or any embedded frame (VS Code webviews such as the Claude Code panel live in
    nested iframes)."""
    for fr in pg.frames:
        loc = fr.get_by_text(text, exact=exact) if text else fr.locator(selector)
        try:
            for i in range(loc.count()):
                if loc.nth(i).is_visible():
                    return loc.nth(i)
        except Exception:
            continue
    return None


def frame_with(pg, selector):
    """First frame containing selector (e.g. the Claude Code webview)."""
    for fr in pg.frames:
        try:
            if fr.locator(selector).count():
                return fr
        except Exception:
            continue
    return None


def tabs():
    for i, pg in enumerate(context().pages):
        print(i, pg.url)


if __name__ == "__main__":
    tabs()
