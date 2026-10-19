import React from 'react';
import {Box, Edge, exitLeft, FONT, LAYOUT, look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog, rgba, SIZE,
  useEditTime, Variant} from './kit';

// CalendarFlip (the overlay plan's composition 11; David's direction for p1.09, "just a calendar, months flipping:
// time passing, no gag"): a small wall calendar on the house panel. Its page shows a month and year (Segoe UI
// Semibold on the chip colour) over that month's days, drawn as cells in a week grid that starts on the right
// weekday (weekends in the muted colour), so each page looks different as it goes. On the 'flip' item's word (R80)
// the pages turn up over the rings, one after another, starting from `start` ('YYYY-MM'): `months` turns, so the
// calendar ends on start + months and holds it. Each turn is tokens' motion.composition.calendarFlip.monthS (0.3 s).
// When the layer is too short for one-after-another turns plus the 0.5 s hold, the turns overlap (at least the 80 ms
// stagger apart) and then the hold shortens to HOLD_MIN_S; only then do the turns themselves speed up. The turns
// tip away from the viewer, so a turning page stays inside its own outline. 0.5 s in (fade, 20 px rise), 0.4 s out.
// About 256 x 305 px. Variant (R140); placement a box in frame px or an edge of title-safe (right by default).

export type CalendarItem = {key?: string; text: string; at: number};
export type CalendarFlipLayer = {id: string; step?: string; layout: 'calendar_flip'; t0: number; t1: number;
  variant: Variant; items: CalendarItem[]; start: string; months: number; box?: Box; edge?: Edge};

const PAGE_W = 320;
const HEADER_H = 80;
const CELL = 28;
const CELL_GAP = 11;
const GRID_TOP = 18;
const GRID_BOTTOM = 20;
const PAGE_H = HEADER_H + GRID_TOP + 6 * CELL + 5 * CELL_GAP + GRID_BOTTOM;
const PAGE_R = 10;
const RING_W = 12;
const RING_H = 28;
const RING_TOP = -15;                // the rings stand this far above the page's top edge, the turns' hinge
const RINGS_AT = [0.22, 0.78];       // across the page
const PAD_EDGES = [6, 3];            // the pages under this one, showing below it (px)
const PERSPECTIVE = 1000;
const HOLD_MIN_S = 0.3;              // the last month's shortest hold before the exit, when the layer is tight
const TURN_MIN_S = 0.15;

const MONTH = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
const DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const SAKAMOTO = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4];

const leap = (y: number) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
const daysIn = (y: number, m: number) => (m === 1 && leap(y) ? 29 : DAYS[m]);
// The weekday of the 1st (0 Sunday), by Sakamoto's method: arithmetic only, the same on every frame.
const firstWeekday = (y: number, m: number) => {
  const yy = m < 2 ? y - 1 : y;
  return (yy + Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400) + SAKAMOTO[m] + 1) % 7;
};

const monthAt = (o: CalendarFlipLayer, k: number) => {
  const m = /^(\d{4})-(\d{2})$/.exec(o.start);
  if (!m || +m[2] < 1 || +m[2] > 12) throw new Error(`calendar_flip ${o.id}: start '${o.start}' is not YYYY-MM`);
  const i = +m[1] * 12 + (+m[2] - 1) + k;
  return {y: Math.floor(i / 12), m: i % 12};
};

// When each page turns and for how long: one after another at monthS when there is room for that and the hold;
// otherwise overlapping, then a shorter hold, then shorter turns.
const schedule = (o: CalendarFlipLayer, fps: number) => {
  const c = MOTION.composition.calendarFlip;
  const n = Math.max(0, Math.round(o.months));
  const flip = o.items.find((i) => i.key === 'flip') ?? o.items[0];
  if (!flip || n === 0) return {n: 0, starts: [] as number[], turnS: c.monthS};
  const room = o.t1 - 1 / fps - c.outS - flip.at;          // from the word to the start of the exit
  let turnS = c.monthS;
  let gap = c.monthS;
  const span = () => turnS + gap * (n - 1);
  if (span() + MOTION.minHoldS > room) {
    gap = n > 1 ? Math.max(MOTION.staggerS, Math.min(c.monthS, (room - MOTION.minHoldS - turnS) / (n - 1))) : 0;
    if (span() + HOLD_MIN_S > room) turnS = Math.max(TURN_MIN_S, room - HOLD_MIN_S - gap * (n - 1));
    // many months in a short layer: closer than the stagger rather than turning on through the exit
    if (n > 1 && span() + HOLD_MIN_S > room) gap = Math.max(1 / fps, (room - HOLD_MIN_S - turnS) / (n - 1));
  }
  return {n, starts: Array.from({length: n}, (_, k) => flip.at + k * gap), turnS};
};

const Page: React.FC<{y: number; m: number; paper: string; ink: string; o: CalendarFlipLayer}> = ({y, m, paper, ink, o}) => {
  const L = look(o.variant);
  const first = firstWeekday(y, m);
  const days = daysIn(y, m);
  return (
    <div style={{position: 'absolute', left: 0, top: 0, width: PAGE_W, height: PAGE_H, background: paper,
      borderRadius: PAGE_R, overflow: 'hidden'}}>
      <div style={{...FONT.heading, fontSize: SIZE.label, height: HEADER_H, lineHeight: `${HEADER_H + 12}px`,
        background: L.chip, color: L.chipText, textAlign: 'center', whiteSpace: 'nowrap'}}>
        {MONTH[m]} {y}
      </div>
      <div style={{display: 'grid', gridTemplateColumns: `repeat(7, ${CELL}px)`, gridAutoRows: CELL, gap: CELL_GAP,
        justifyContent: 'center', paddingTop: GRID_TOP}}>
        {Array.from({length: 42}, (_, s) => {
          const day = s - first + 1;
          const weekend = s % 7 === 0 || s % 7 === 6;
          const real = day >= 1 && day <= days;
          return (
            <div key={s} style={{borderRadius: 4, background: !real ? 'transparent'
              : weekend ? rgba(L.muted, 0.6) : rgba(ink, 0.2)}} />
          );
        })}
      </div>
    </div>
  );
};

export const CalendarFlip: React.FC<{o: CalendarFlipLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const L = look(o.variant);
  const c = MOTION.composition.calendarFlip;
  const paper = o.variant === 'light' ? L.well : L.body;     // a cream page on the brown panel, a beige one on cream
  const ink = o.variant === 'light' ? L.body : L.panel;      // the brown, for cells and the turning page's shade
  const p = prog(t, o.t0, MOTION.baseS);
  const {n, starts, turnS} = schedule(o, fps);
  const turn = starts.map((s) => prog(t, s, turnS));
  const base = turn.findIndex((q) => q === 0);               // the page under every turning one
  const shown = base < 0 ? n : base;
  const turning = turn.map((q, k) => ({q, k})).filter(({q}) => q > 0 && q < 1).reverse();   // the earliest on top
  const page = (k: number) => {
    const {y, m} = monthAt(o, k);
    return <Page y={y} m={m} paper={paper} ink={ink} o={o} />;
  };
  return (
    <Placed box={o.box} edge={o.edge} fallback="right">
      <div style={{opacity: p * exitLeft(t, o.t1, c.outS, fps), transform: `translateY(${(1 - p) * MOTION.risePx}px)`}}>
        <Panel variant={o.variant} style={{padding: `${-RING_TOP + 12}px 16px ${PAD_EDGES[0] + 16}px`}}>
          <div style={{position: 'relative', width: PAGE_W, height: PAGE_H}}>
            {PAD_EDGES.map((d) => (
              <div key={d} style={{position: 'absolute', left: d / 2, right: d / 2, top: d, height: PAGE_H,
                background: paper, borderRadius: PAGE_R, border: `${LAYOUT.panel.ruleWidthPx}px solid ${rgba(ink, 0.35)}`,
                boxSizing: 'border-box'}} />
            ))}
            {page(shown)}
            {turning.map(({q, k}) => (
              <div key={k} style={{position: 'absolute', left: 0, top: 0, width: PAGE_W, height: PAGE_H,
                transformOrigin: '50% 0', transform: `perspective(${PERSPECTIVE}px) rotateX(${-88 * q}deg)`,
                backfaceVisibility: 'hidden'}}>
                {page(k)}
                <div style={{position: 'absolute', inset: 0, borderRadius: PAGE_R, background: rgba(ink, 0.4 * q)}} />
              </div>
            ))}
            {RINGS_AT.map((x) => (
              <div key={x} style={{position: 'absolute', left: x * PAGE_W - RING_W / 2, top: RING_TOP, width: RING_W,
                height: RING_H, borderRadius: RING_W / 2, background: L.rule,
                border: `${LAYOUT.panel.ruleWidthPx}px solid ${rgba(ink, 0.8)}`, boxSizing: 'border-box'}} />
            ))}
          </div>
        </Panel>
      </div>
    </Placed>
  );
};

export type CalendarFlipProps = PreviewProps<CalendarFlipLayer>;

// The overlay plan's row 5 (00:02:06, p1.09): "Stored as text, they can't drive a chart over time", with room for the
// turns to run one after another.
export const CALENDAR_FLIP_SAMPLE: CalendarFlipProps = {durationInFrames: 165, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'calendar-months', layout: 'calendar_flip', t0: 0.5, t1: 5.3, variant: 'dark',
    items: [{key: 'flip', text: 'months', at: 2.0}], start: '2020-01', months: 6, edge: 'right'}};

export const CalendarFlipPreview: React.FC<CalendarFlipProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><CalendarFlip o={layer} /></PreviewStage>
);
