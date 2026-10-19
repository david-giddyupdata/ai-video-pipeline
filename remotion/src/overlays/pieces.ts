import {Box, Edge, Variant} from './kit';

// The layer every one-off overlay piece is drawn from (the overlay build, docs/OVERLAY_BUILD_PLAN_qs1a.md). Times are
// edit time, seconds on the full sequence: t0 and t1 bound the piece (t1 includes its way out), and each item carries
// its own `at`, the start of the spoken word it lands on (R80), computed by pipeline/edit/plan.py plan_overlays from
// the manifest's at_word. A piece's card says which item keys it has and what each one shows; `props` holds anything
// else the card fixes (a counter's text, a list of names). `pin` is the thing in the recording the piece points at,
// a box in source-frame px, for PinnedBox (pinned.tsx); `box` or `edge` place an unpinned piece (Placed in kit.tsx).
export type PieceItem = {key: string; text: string; at: number; until?: number};

export type PieceLayer = {id: string; step?: string; layout: 'piece'; piece: string; t0: number; t1: number;
  variant: Variant; items: PieceItem[]; box?: Box; edge?: Edge; pin?: Box; props?: Record<string, unknown>};

// The item with this key; a piece's card guarantees the keys it lists.
export const item = (o: PieceLayer, key: string) => {
  const it = o.items.find((i) => i.key === key);
  if (!it) throw new Error(`piece ${o.id}: no item '${key}'`);
  return it;
};
