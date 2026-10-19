import React from 'react';
import {Box, Edge, exitLeft, FONT, LAYOUT, look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog, SIZE,
  useEditTime, Variant, lh} from './kit';

// TermChip (the overlay plan's composition 2; ep03's white text plate, ep04's chips): one line, a term and its
// meaning, placed near the thing named. The term sits in a chip (teal on cream, gold on brown), the meaning beside it
// in body type; Courier New for a term that is data (R143), such as a date format. 0.3 s fade with a 20 px rise in,
// 0.3 s fade out. The meaning may land later, on its own word (meaning_at); its space is kept from the start so the
// panel never changes size. Placement: a box in frame px (the panel is centred in it) or an edge of title-safe.

export type TermChipLayer = {id: string; step?: string; layout: 'term_chip'; t0: number; t1: number;
  variant: Variant; term: string; meaning: string; meaning_at?: number; data?: boolean; box?: Box; edge?: Edge};

export const TermChip: React.FC<{o: TermChipLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const L = look(o.variant);
  const {inS, outS, risePx} = MOTION.composition.termChip;
  const p = prog(t, o.t0, inS);
  const meaning = o.meaning_at !== undefined && o.meaning_at > o.t0 ? prog(t, o.meaning_at, inS) : 1;
  const chip = LAYOUT.chip;
  return (
    <Placed box={o.box} edge={o.edge} fallback="top">
      <div style={{opacity: p * exitLeft(t, o.t1, outS, fps), transform: `translateY(${(1 - p) * risePx}px)`}}>
        <Panel variant={o.variant} style={{display: 'flex', alignItems: 'center', gap: 24, padding: '14px 32px 14px 16px',
          whiteSpace: 'nowrap'}}>
          <div style={{...(o.data ? FONT.data : FONT.heading), fontSize: SIZE.label, lineHeight: lh(SIZE.label),
            background: L.chip, color: L.chipText, borderRadius: chip.radiusPx,
            padding: `${chip.padPx[0]}px ${chip.padPx[1] + 4}px`}}>
            {o.term}
          </div>
          <div style={{...FONT.body, fontSize: SIZE.body, lineHeight: lh(SIZE.body), color: L.body, opacity: meaning}}>
            {o.meaning}
          </div>
        </Panel>
      </div>
    </Placed>
  );
};

export type TermChipProps = PreviewProps<TermChipLayer>;

export const TERM_CHIP_SAMPLE: TermChipProps = {durationInFrames: 120, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'term-dataset', layout: 'term_chip', t0: 0.5, t1: 3.5, variant: 'dark', term: 'Dataset',
    meaning: 'your data, prepared for analysis', edge: 'top'}};

export const TermChipPreview: React.FC<TermChipProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><TermChip o={layer} /></PreviewStage>
);
