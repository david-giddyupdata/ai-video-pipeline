import React from 'react';
import {useVideoConfig} from 'remotion';
import {ACCENT, Box, Edge, exitLeft, FONT, LAYOUT, look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog, rgba,
  SIZE, spaced, TimedItem, useEditTime, Variant, lh} from './kit';

// ChoicePanel (the overlay plan's composition 3; the kinetic list's pops and the orange box): two or three options
// side by side, each popping on its word (items' `at`, R80; at least 80 ms apart), and the chosen one outlined in
// the accent orange as R51's overview rectangle (8 px, square corners), on its own word (chosen_at; by default half
// a second after the last option). An item reads "Label: what it does"; the label is the heading, the rest the body.
// 0.5 s panel in (fade, 20 px rise), each option a 0.25 s pop (no overshoot), 0.4 s out. Variant (R140); placement
// a box in frame px or an edge of title-safe.

export type ChoicePanelLayer = {id: string; step?: string; layout: 'choice_panel'; t0: number; t1: number;
  variant: Variant; title?: string; items: TimedItem[]; chosen?: number; chosen_at?: number; box?: Box; edge?: Edge};

const GAP = 32;
const OPTION_MAX_W = 680;

const split = (text: string) => {
  const i = text.indexOf(': ');
  return i < 0 ? {label: text, detail: ''} : {label: text.slice(0, i), detail: text.slice(i + 2)};
};

export const ChoicePanel: React.FC<{o: ChoicePanelLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const {width} = useVideoConfig();
  const L = look(o.variant);
  const m = MOTION.composition.choicePanel;
  const p = prog(t, o.t0, m.inS);
  const starts = spaced(o.items.map((it) => it.at), m.itemGapMinS);
  const n = Math.max(1, o.items.length);
  const pad = 46 * 2 + LAYOUT.panel.ruleWidthPx * 2;      // the panel's side padding (room for the orange outline)
  const room = (o.box?.w ?? width - LAYOUT.safePx.left - LAYOUT.safePx.right) - pad - GAP * (n - 1);
  const optionW = Math.min(OPTION_MAX_W, Math.floor(room / n));
  const chosenAt = o.chosen_at ?? (starts.length ? starts[starts.length - 1] + 0.5 : o.t0);
  const mark = o.chosen !== undefined ? prog(t, chosenAt, m.markS) : 0;
  const ol = LAYOUT.chosenOutline;
  return (
    <Placed box={o.box} edge={o.edge} fallback="top">
      <div style={{opacity: p * exitLeft(t, o.t1, m.outS, fps), transform: `translateY(${(1 - p) * MOTION.risePx}px)`}}>
        <Panel variant={o.variant} style={{padding: '34px 46px 38px'}}>
          {o.title && (
            <div style={{...FONT.heading, fontSize: SIZE.label, lineHeight: lh(SIZE.label), color: L.muted, marginBottom: 18}}>
              {o.title}
            </div>
          )}
          <div style={{display: 'flex', gap: GAP, alignItems: 'stretch'}}>
            {o.items.map((it, i) => {
              const q = prog(t, starts[i], m.itemS);
              const {label, detail} = split(it.text);
              const chosen = i === o.chosen;
              return (
                <div key={i} style={{position: 'relative', width: optionW, boxSizing: 'border-box', padding: '20px 30px 24px',
                  background: L.well, border: `${LAYOUT.panel.ruleWidthPx}px solid ${rgba(L.rule, 0.5)}`,
                  borderRadius: 10, opacity: q, transform: `scale(${0.9 + 0.1 * q})`}}>
                  <div style={{...FONT.heading, fontSize: SIZE.heading, lineHeight: lh(SIZE.heading), color: L.heading}}>{label}</div>
                  {detail && (
                    <div style={{...FONT.body, fontSize: SIZE.body, lineHeight: lh(SIZE.body), color: L.body, marginTop: 4}}>
                      {detail}
                    </div>
                  )}
                  {chosen && (
                    <div style={{position: 'absolute', inset: -(ol.gapPx + ol.widthPx), border: `${ol.widthPx}px solid ${ACCENT}`,
                      opacity: mark, transform: `scale(${1.06 - 0.06 * mark})`}} />
                  )}
                </div>
              );
            })}
          </div>
        </Panel>
      </div>
    </Placed>
  );
};

export type ChoicePanelProps = PreviewProps<ChoicePanelLayer>;

// The shortlist's row 15 (00:12:54:04): "Clicking a bar instead would highlight that one region".
export const CHOICE_PANEL_SAMPLE: ChoicePanelProps = {durationInFrames: 150, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'choice-click', layout: 'choice_panel', t0: 0.3, t1: 4.8, variant: 'dark',
    items: [{text: 'Click the title: selects the chart', at: 0.9}, {text: 'Click a bar: highlights one region', at: 1.6}],
    chosen: 0, chosen_at: 2.4, edge: 'top'}};

export const ChoicePanelPreview: React.FC<ChoicePanelProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><ChoicePanel o={layer} /></PreviewStage>
);
