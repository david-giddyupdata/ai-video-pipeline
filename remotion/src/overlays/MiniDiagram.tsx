import React from 'react';
import {Img, staticFile} from 'remotion';
import {evolvePath} from '@remotion/paths';
import {Box, Edge, exitLeft, FONT, LAYOUT, look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog, rgba, SIZE,
  useEditTime, Variant, lh} from './kit';
import {TABLER, TablerName} from './vendor/tabler/icons';

// MiniDiagram (the overlay plan's composition 9): a few boxes and arrows drawn on in order, each on its own spoken
// word (items' `at`, R80), on a panel. Items, laid out left to right in list order:
//   node   a labelled box. "Heading: detail" (or "Heading, detail") puts the detail on a second line in body type.
//          A small Tabler glyph sits in each box when every node in the diagram has one (the item's `icon`, or a
//          guess from its text: bar chart, line chart, dashboard, ...); `icon: 'none'` turns a node's off.
//   arrow  an arrow drawn on from the node before it to the node after it, its text a small label above the shaft.
//   lock   on: a node's key. The open padlock (o.art.open) drops into the right of that node at the item's word (its
//          room kept from the start) and swaps to the closed one (o.art.closed) 0.3 s later with a small settle:
//          the lock clicking shut. The sound is added later as audio (o.sound names it); nothing here plays it.
// Every element keeps its space from the start, so the panel never changes size. The panel fades in (20 px rise)
// with the first element; each element is 0.5 s (motion.composition.miniDiagram.elementS); 0.5 s out. An element
// whose word comes before the one listed ahead of it still draws on its own word (never before it). Variant (R140);
// placement a box in frame px or an edge of title-safe (top by default).

export type DiagramItem = {key: string; kind: 'node' | 'arrow' | 'lock'; text: string; at: number; on?: string;
  icon?: TablerName | 'none'};
export type MiniDiagramLayer = {id: string; step?: string; layout: 'mini_diagram'; t0: number; t1: number;
  variant: Variant; items: DiagramItem[]; art?: {open: string; closed: string}; sound?: string; box?: Box;
  edge?: Edge};

const GLYPH = 64;               // a node's glyph, px
const ARROW_W = 180;            // an arrow's length, px
const NODE_H = 150;             // every node the same height, so a one-line node and a two-line one line up
const LOCK = 150;               // the padlock art's square, px (the lock itself fills the middle 62% x 84% of it)
const LOCK_SLOT = 98;           // the room kept for it at the right of its node
const LOCK_SWAP_S = 0.3;        // open, then shut this long after its word
const SETTLE_S = 0.2;
const GUESS: [RegExp, TablerName][] = [[/\bbar\b/i, 'chart-bar'], [/\bline\b/i, 'chart-line'],
  [/dashboard/i, 'layout-dashboard'], [/\bfilter/i, 'filter'], [/\btable\b/i, 'table'], [/\bmap\b/i, 'map'],
  [/\bdata(set)?\b/i, 'database'], [/\bfile\b/i, 'file']];

const split = (text: string) => {
  const m = /^(.*?)(: |, )(.*)$/.exec(text);
  return m ? {head: m[1], detail: m[3]} : {head: text, detail: ''};
};
const glyphOf = (it: DiagramItem): TablerName | null =>
  it.icon === 'none' ? null : it.icon ?? GUESS.find(([re]) => re.test(it.text))?.[1] ?? null;

// Each element's start: its own word, at least 80 ms after any element whose word comes just before it (in time,
// not list order, so nothing is pushed off its word by an element listed ahead of it).
const starts = (items: DiagramItem[]) => {
  const order = items.map((it, i) => i).sort((a, b) => items[a].at - items[b].at);
  const s = items.map((it) => it.at);
  let prev = -Infinity;
  for (const i of order) s[i] = prev = Math.max(items[i].at, prev + MOTION.staggerS);
  return s;
};

const Glyph: React.FC<{name: TablerName; p: number; color: string}> = ({name, p, color}) => (
  <svg width={GLYPH} height={GLYPH} viewBox="0 0 24 24" style={{flex: 'none', overflow: 'visible'}}>
    {TABLER[name].map((d, i) => (
      <path key={i} d={d} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
        {...evolvePath(p, d)} />
    ))}
  </svg>
);

export const MiniDiagram: React.FC<{o: MiniDiagramLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const L = look(o.variant);
  const m = MOTION.composition.miniDiagram;
  const at = starts(o.items);
  const first = Math.max(o.t0, Math.min(...at));
  const p = prog(t, first, m.elementS);
  const nodes = o.items.filter((it) => it.kind === 'node');
  const glyphs = nodes.length > 0 && nodes.every((n) => glyphOf(n) !== null);
  const locks = o.items.map((it, i) => ({it, s: at[i]})).filter(({it}) => it.kind === 'lock' && it.on);
  const shaft = 'M 6 0 L ' + (ARROW_W - 8) + ' 0';
  const head = `M ${ARROW_W - 30} -16 L ${ARROW_W - 8} 0 L ${ARROW_W - 30} 16`;

  const row = o.items.map((it, i) => {
    const q = prog(t, at[i], m.elementS);
    if (it.kind === 'arrow') {
      return (
        <div key={it.key} style={{width: ARROW_W, height: NODE_H, flex: 'none', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', margin: '0 6px'}}>
          <div style={{...FONT.body, fontSize: SIZE.label, lineHeight: lh(SIZE.label), color: L.muted, whiteSpace: 'nowrap',
            marginBottom: 6, opacity: prog(t, at[i] + m.elementS * 0.3, m.elementS * 0.7)}}>{it.text}</div>
          <svg width={ARROW_W} height={24} viewBox={`0 -12 ${ARROW_W} 24`} style={{overflow: 'visible'}}>
            <path d={shaft} fill="none" stroke={L.muted} strokeWidth={5} strokeLinecap="round"
              {...evolvePath(Math.min(1, q / 0.8), shaft)} />
            <path d={head} fill="none" stroke={L.muted} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round"
              {...evolvePath(Math.max(0, (q - 0.7) / 0.3), head)} />
          </svg>
          <div style={{height: 64}} />
        </div>
      );
    }
    if (it.kind !== 'node') return null;
    const {head: h, detail} = split(it.text);
    const g = glyphs ? glyphOf(it) : null;
    const lock = o.art ? locks.find((l) => l.it.on === it.key) : undefined;
    let lockEl: React.ReactNode = null;
    if (lock && o.art) {
      const land = prog(t, lock.s, 0.25);
      const shut = t >= lock.s + LOCK_SWAP_S;
      const settle = prog(t, lock.s + LOCK_SWAP_S, SETTLE_S);
      const scale = shut ? 1.07 - 0.07 * settle : 1;
      const dy = -28 * (1 - land) + (shut ? 3 * settle : 0);
      lockEl = (
        <div style={{position: 'relative', flex: 'none', width: LOCK_SLOT, height: NODE_H - 8, marginLeft: 4}}>
          <Img src={staticFile(shut ? o.art.closed : o.art.open)} style={{position: 'absolute', width: LOCK, height: LOCK,
            left: (LOCK_SLOT - LOCK) / 2, top: (NODE_H - 8 - LOCK) / 2, opacity: land,
            transform: `translateY(${dy}px) scale(${scale})`, transformOrigin: '50% 80%'}} />
        </div>
      );
    }
    return (
      <div key={it.key} style={{position: 'relative', flex: 'none', height: NODE_H, boxSizing: 'border-box',
        display: 'flex', alignItems: 'center', gap: 16, padding: `0 ${lockEl ? 18 : 28}px 0 ${g ? 22 : 28}px`,
        background: L.well, border: `${LAYOUT.panel.ruleWidthPx}px solid ${rgba(L.rule, 0.5)}`, borderRadius: 10,
        opacity: Math.min(1, q * 1.6), transform: `scale(${0.94 + 0.06 * q})`}}>
        {g && <Glyph name={g} p={q} color={L.heading} />}
        <div style={{whiteSpace: 'nowrap'}}>
          <div style={{...FONT.heading, fontSize: SIZE.heading, lineHeight: lh(SIZE.heading, 1.1), color: L.heading}}>{h}</div>
          {detail && (
            <div style={{...FONT.body, fontSize: SIZE.body, lineHeight: lh(SIZE.body, 1.1), color: L.body}}>{detail}</div>
          )}
        </div>
        {lockEl}
      </div>
    );
  });

  return (
    <Placed box={o.box} edge={o.edge} fallback="top">
      <div style={{opacity: p * exitLeft(t, o.t1, m.outS, fps), transform: `translateY(${(1 - p) * MOTION.risePx}px)`}}>
        <Panel variant={o.variant} style={{display: 'flex', alignItems: 'center', padding: '18px 30px'}}>
          {row}
        </Panel>
      </div>
    </Placed>
  );
};

export type MiniDiagramProps = PreviewProps<MiniDiagramLayer>;

// S17 (00:13:13:21): "An action lets a click on one visual change what the other visuals show." A lock item
// (kind 'lock', on: a node's key) also needs o.art, PNGs in the public dir (the review build's are in review/public).
export const MINI_DIAGRAM_SAMPLE: MiniDiagramProps = {durationInFrames: 150, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'action-filter', layout: 'mini_diagram', t0: 0.3, t1: 4.8, variant: 'dark',
    items: [{key: 'bar', kind: 'node', text: 'Bar chart', at: 0.6}, {key: 'click', kind: 'arrow', text: 'click', at: 1.2},
      {key: 'line', kind: 'node', text: 'Line chart, filtered', at: 1.9}], edge: 'top'}};

export const MiniDiagramPreview: React.FC<MiniDiagramProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><MiniDiagram o={layer} /></PreviewStage>
);
