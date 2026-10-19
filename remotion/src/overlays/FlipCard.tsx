import React from 'react';
import {Box, Edge, exitLeft, FONT, look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog, rgba, SIZE, spaced,
  useEditTime, Variant, lh} from './kit';

// FlipCard (the overlay plan's composition 10; David's direction for p1.04: CSV then XLSX "scaling from 0 to 100% or
// flipping like a flip chart, one card after another"): a small flip chart. Each item is a page, its text in Courier
// New (R143: file endings, formats, values), hung from a bar. The first page swings down onto the pad on its word;
// each next page is uncovered on its own word (items' `at`, R80; at least 80 ms apart) as the page above it lifts up
// and over the bar, hinged at its top edge (a flip-chart page turn), cardS each (0.35 s, the house easing, no
// overshoot). A page shades as it turns edge-on, so the turn reads in depth. An optional title sits above in Segoe UI
// Semibold, wrapping to the pad's width so the panel stays narrow. The panel fades in with a 20 px rise as the first
// page lands and fades out over outS (0.3 s); nothing moves during a hold. Every page takes the widest item's size,
// so the panel never changes size, and a page is drawn only from its word, so nothing shows early. Variant (R140);
// placement a box in frame px or an edge of title-safe (the top by default).

export type FlipItem = {key?: string; text: string; at: number};
export type FlipCardLayer = {id: string; step?: string; layout: 'flip_card'; t0: number; t1: number;
  variant: Variant; title?: string; items: FlipItem[]; box?: Box; edge?: Edge};

const CH = 0.6;                 // Courier New's advance, in em
const PAGE_PAD = 44;            // a page's side padding
const PAGE_MIN_W = 320;
const PAGE_H = 116;
const COL_MIN_W = 420;          // the title wraps to the pad's width, but no narrower than this
const BAR_H = 14;               // the flip chart's bar; the pages hang just under it
const PERSPECTIVE = 700;        // px, from the hinge
const SHADE = 0.45;             // a turning page's shade at edge-on

export const FlipCard: React.FC<{o: FlipCardLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const L = look(o.variant);
  const m = MOTION.composition.flipCard;
  const n = o.items.length;
  const starts = spaced(o.items.map((it) => it.at), MOTION.staggerS);
  const p = prog(t, o.t0, m.cardS);
  const longest = Math.max(1, ...o.items.map((it) => it.text.length));
  const pageW = Math.max(PAGE_MIN_W, Math.ceil(longest * CH * SIZE.data) + PAGE_PAD * 2);
  const colW = o.title ? Math.max(pageW, COL_MIN_W) : pageW;

  // Each page's angle about its top edge: 90 is edge-on toward the viewer (the first page swings down from there),
  // 0 flat on the pad; a page lifts back to 90 on the next page's word and is gone after.
  const pages = o.items.map((it, i) => {
    if (t < starts[i]) return null;
    const down = i === 0 ? 1 - prog(t, starts[i], m.cardS) : 0;
    const lift = i + 1 < n ? prog(t, starts[i + 1], m.cardS) : 0;
    if (lift >= 1) return null;
    const a = Math.min(90, 90 * (down + lift));
    return (
      <div key={i} style={{position: 'absolute', inset: 0, zIndex: n - i, background: L.chip, borderRadius: 8,
        display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', transformOrigin: '50% 0',
        transform: `perspective(${PERSPECTIVE}px) rotateX(${a}deg)`}}>
        <div style={{...FONT.data, fontSize: SIZE.data, lineHeight: `${PAGE_H}px`, color: L.chipText,
          whiteSpace: 'nowrap'}}>{it.text}</div>
        {a > 0 && (
          <div style={{position: 'absolute', inset: 0, background: rgba(L.panel, SHADE * Math.sin((a * Math.PI) / 180))}} />
        )}
      </div>
    );
  });

  return (
    <Placed box={o.box} edge={o.edge} fallback="top">
      <div style={{opacity: p * exitLeft(t, o.t1, m.outS, fps), transform: `translateY(${(1 - p) * MOTION.risePx}px)`}}>
        <Panel variant={o.variant} style={{width: colW + 80 + 4, padding: '22px 40px 30px', display: 'flex',
          flexDirection: 'column', alignItems: 'center'}}>
          {o.title && (
            <div style={{...FONT.heading, fontSize: SIZE.heading, lineHeight: lh(SIZE.heading), color: L.heading, maxWidth: colW,
              textAlign: 'center', textWrap: 'balance', marginBottom: 18}}>{o.title}</div>
          )}
          <div style={{width: pageW + 28, height: BAR_H, borderRadius: BAR_H / 2, background: rgba(L.chip, 0.55),
            position: 'relative', zIndex: n + 1}} />
          <div style={{position: 'relative', width: pageW, height: PAGE_H, marginTop: -4}}>{pages}</div>
        </Panel>
      </div>
    </Placed>
  );
};

export type FlipCardProps = PreviewProps<FlipCardLayer>;

// p1.04 (00:00:54:28): "Both show an Excel icon, so the ending is what tells them apart."
export const FLIP_CARD_SAMPLE: FlipCardProps = {durationInFrames: 150, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'flip-ending', layout: 'flip_card', t0: 0.3, t1: 4.8, variant: 'dark',
    title: 'Same icon, different ending', items: [{key: 'csv', text: '.csv', at: 0.3}, {key: 'xlsx', text: '.xlsx', at: 1.43}],
    edge: 'top'}};

export const FlipCardPreview: React.FC<FlipCardProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><FlipCard o={layer} /></PreviewStage>
);
