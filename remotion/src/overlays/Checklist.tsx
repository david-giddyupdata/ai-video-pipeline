import React from 'react';
import {evolvePath} from '@remotion/paths';
import {ACCENT, Box, Edge, exitLeft, FONT, LAYOUT, look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog, rgba,
  SIZE, spaced, TimedItem, useEditTime, Variant, lh} from './kit';

// Checklist (the overlay plan's composition 7; David's recap overlay, ep04 7:11): a recap panel, a heading and the
// items the narration sums up, each ticking on its word (items' `at`, R80; at least 80 ms apart). The rows' boxes
// stand empty from the panel's entrance, so the panel has its shape and never changes size; on its word an item's
// text fades in beside its box and an orange tick (ACCENT, R51) draws on over 0.4 s. The panel fades in with the
// house 20 px rise over 0.5 s, holds to the end of the line and fades out over 1.0 s (a recap lingers). Variant
// (R140); placement a box in frame px (the panel is centred in it) or an edge of title-safe, right by default.

export type ChecklistLayer = {id: string; step?: string; layout: 'checklist'; t0: number; t1: number;
  variant: Variant; title?: string; items: TimedItem[]; box?: Box; edge?: Edge};

const BOX_PX = 56;              // the tick box, drawn on a 24 x 24 grid
const ROW_H = 78;               // a one-line row
const LINE_H = 66;
const TEXT_MAX_W = 860;         // a longer item wraps rather than widening the panel past this
const SLIDE_PX = 14;            // an item's text slides this far towards its box as it fades in
const TICK = 'M6.5 12.5l3.8 3.8l7.7 -8.3';

export const Checklist: React.FC<{o: ChecklistLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const L = look(o.variant);
  const m = MOTION.composition.checklist;
  const p = prog(t, o.t0, MOTION.baseS);
  const starts = spaced(o.items.map((it) => Math.max(o.t0, it.at)), MOTION.staggerS);
  const textW = Math.min(TEXT_MAX_W, (o.box?.w ?? TEXT_MAX_W + 200) - 200);
  return (
    <Placed box={o.box} edge={o.edge} fallback="right">
      <div style={{opacity: p * exitLeft(t, o.t1, m.outS, fps), transform: `translateY(${(1 - p) * MOTION.risePx}px)`}}>
        <Panel variant={o.variant} style={{padding: '24px 48px 30px 36px'}}>
          {o.title && (
            <div style={{...FONT.heading, fontSize: SIZE.heading, lineHeight: lh(SIZE.heading), color: L.heading, marginBottom: 12,
              whiteSpace: 'nowrap'}}>{o.title}</div>
          )}
          {o.items.map((it, i) => {
            const tick = prog(t, starts[i], m.itemS);
            const text = prog(t, starts[i], m.itemS * 0.75);
            const draw = evolvePath(tick, TICK);
            return (
              // the box sits beside the item's first line, so a wrapped item still reads as one tick
              <div key={i} style={{display: 'flex', alignItems: 'flex-start', gap: 22,
                padding: `${(ROW_H - LINE_H) / 2}px 0`}}>
                <svg width={BOX_PX} height={BOX_PX} viewBox="0 0 24 24"
                  style={{flex: 'none', overflow: 'visible', marginTop: (LINE_H - BOX_PX) / 2}}>
                  <rect x={3} y={3} width={18} height={18} rx={3.5} fill={rgba(L.well, 0.9)}
                    stroke={tick > 0 ? L.rule : L.muted} strokeWidth={1.4} />
                  {tick > 0 && (
                    <path d={TICK} fill="none" stroke={ACCENT} strokeWidth={3} strokeLinecap="round"
                      strokeLinejoin="round" strokeDasharray={draw.strokeDasharray}
                      strokeDashoffset={draw.strokeDashoffset} />
                  )}
                </svg>
                <div style={{...FONT.body, fontSize: SIZE.body, lineHeight: `${LINE_H}px`, color: L.body, maxWidth: textW,
                  opacity: text, transform: `translateX(${(1 - text) * -SLIDE_PX}px)`}}>
                  {it.text}
                </div>
              </div>
            );
          })}
        </Panel>
      </div>
    </Placed>
  );
};

export type ChecklistProps = PreviewProps<ChecklistLayer>;

// p1.40, Part 1's recap: "one Excel sheet, with proper dates and four location fields, stored in SPICE".
export const CHECKLIST_SAMPLE: ChecklistProps = {durationInFrames: 210, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'recap-part1', layout: 'checklist', t0: 0.3, t1: 6.6, variant: 'dark', title: 'Our dataset',
    items: [{text: 'one Excel sheet', at: 1.0}, {text: 'proper dates', at: 1.9}, {text: 'four location fields', at: 3.0},
      {text: 'stored in SPICE', at: 3.9}], edge: 'right'}};

export const ChecklistPreview: React.FC<ChecklistProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><Checklist o={layer} /></PreviewStage>
);
