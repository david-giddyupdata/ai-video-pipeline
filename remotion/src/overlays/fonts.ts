import {continueRender, delayRender, getInputProps} from 'remotion';
import caveat from './fonts/Caveat-Variable.ttf';
import inter from './fonts/Inter-Variable.ttf';
import jetbrainsMono from './fonts/JetBrainsMono-Variable.ttf';

// R148: three free OFL fonts ship with the overlays (their licences are beside them in fonts/), so a copy of this
// project renders the same where the Windows fonts are missing: Inter stands in for Segoe UI, Caveat for Segoe Print,
// JetBrains Mono for Courier New (the token stacks in tokens.json name them after the Windows fonts, R143). They are
// variable fonts, so one file serves every weight. Each is registered with the page once; a frame waits for it.
const FAMILIES: [string, string, string][] = [
  ['Inter', inter, '100 900'],
  ['Caveat', caveat, '400 700'],
  ['JetBrains Mono', jetbrainsMono, '100 800'],
];

const LOAD_LIMIT_MS = 15000;
let started = false;

// The export's cursor, mark and title-card layers (OverlayClip with only 'cursor', 'mark:<i>', 'card:<i>') draw none
// of these fonts, and in round 6's export a browser tab of the 28,000-frame cursor render stuck on this load
// altogether (not even the limit below fired), three times: those layers don't load them.
const textless = () => {
  const only = (getInputProps() as {only?: unknown}).only;
  return typeof only === 'string' && /^(cursor|mark:|card:)/.test(only);
};

export const loadOverlayFonts = () => {
  if (started || typeof document === 'undefined' || textless()) {
    return;
  }
  started = true;
  for (const [family, url, weight] of FAMILIES) {
    const handle = delayRender(`overlay font ${family}`);
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        continueRender(handle);
      }
    };
    // A load that never settles (one browser tab of a long render, round 6's export: the cursor layer stopped at
    // frame 2081, then 6046) mustn't stop the render: after LOAD_LIMIT_MS the stack's next font is used. The stacks
    // name the Windows fonts first, so on David's PC nothing changes.
    const limit = setTimeout(() => {
      console.warn(`overlay font ${family} still loading after ${LOAD_LIMIT_MS} ms; going on without it`);
      finish();
    }, LOAD_LIMIT_MS);
    new FontFace(family, `url(${url}) format('truetype')`, {weight})
      .load()
      .then((face) => {
        (document.fonts as unknown as {add: (f: FontFace) => void}).add(face);   // (older DOM typings lack add)
        clearTimeout(limit);
        finish();
      })
      .catch((err) => {                                    // a missing font falls back down its stack; never hang
        console.warn(`overlay font ${family} did not load`, err);
        clearTimeout(limit);
        finish();
      });
  }
};
