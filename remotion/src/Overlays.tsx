import React from 'react';
import {interpolate, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {BODY_FONT, Card, CardTitle, COPPER, fontFace, Labelled, MARK, reveal} from './Slides';
import {ChapterCard, ChapterCardLayer} from './overlays/ChapterCard';
import {ChoicePanel, ChoicePanelLayer} from './overlays/ChoicePanel';
import {MapPins, MapPinsLayer} from './overlays/MapPins';
import {TermChip, TermChipLayer} from './overlays/TermChip';
import {WordBuild, WordBuildLayer} from './overlays/WordBuild';

// Overlay cards (R77, R79), planned by pipeline/edit/plan.py from a step's `overlay`: text the viewer must read is
// shown whole on David's BulletPanel card (opaque, so legible on any background), sliding in from one edge so the
// Claude panel on the other side stays visible. Two layouts:
//   text  the whole text (a long prompt); highlights are orange outlines (R51) on phrases, fading in on the naming
//         word, holding to the end of the sentence, fading out, as overview marks do (R48)
//   list  items that appear as their word is spoken (the reply's main points, worded as what Claude may suggest, R76)
// Screen space, above the camera; in the Premiere export each overlay is its own transparent clip (only: overlay:<i>).
export type OverlayHighlight = {match: string; draw0: number; draw1: number; fade0: number; fade1: number};
export type OverlayItem = {text: string; at: number};
export type CardLayer = {id: string; step: string; layout: 'text' | 'list'; title?: string; text?: string;
  items?: OverlayItem[]; edge: 'left' | 'right'; t0: number; t1: number; highlights: OverlayHighlight[]};
// The new composition set (R131, R134; overlays/): each layout is its own component, drawn from the same kind of
// layer in edit time (t0, t1, items with `at`), so plan.overlays can carry any of them.
export type OverlayLayer = CardLayer | ChapterCardLayer | TermChipLayer | ChoicePanelLayer | WordBuildLayer
  | MapPinsLayer;

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// The text split around its highlights, each span outlined by its own opacity at time t.
const Highlighted: React.FC<{text: string; highlights: OverlayHighlight[]; t: number}> = ({text, highlights, t}) => {
  const spans: {text: string; h?: OverlayHighlight}[] = [];
  const found = highlights.map((h) => ({h, at: text.indexOf(h.match)})).filter((x) => x.at >= 0)
    .sort((a, b) => a.at - b.at);
  let pos = 0;
  for (const {h, at} of found) {
    if (at < pos) continue;                                 // overlapping highlights: the first wins
    if (at > pos) spans.push({text: text.slice(pos, at)});
    spans.push({text: h.match, h});
    pos = at + h.match.length;
  }
  if (pos < text.length) spans.push({text: text.slice(pos)});
  return <>{spans.map((s, i) => {
    if (!s.h) return <span key={i}>{s.text}</span>;
    const on = Math.min(interpolate(t, [s.h.draw0, s.h.draw1], [0, 1], clamp),
      interpolate(t, [s.h.fade0, s.h.fade1], [1, 0], clamp));
    return (
      <span key={i} style={{boxShadow: `0 0 0 ${on > 0 ? 4 : 0}px rgba(241, 111, 5, ${on})`, borderRadius: 4,
        padding: '1px 4px', margin: '0 -4px', boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone'}}>
        {s.text}
      </span>
    );
  })}</>;
};

const OverlayCard: React.FC<{o: CardLayer; dur: number}> = ({o, dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = o.t0 + frame / fps;                             // local frame -> edit time
  return (
    <Card edge={o.edge} dur={dur} top>
      <style>{fontFace}</style>
      {o.title && <CardTitle text={o.title} size={46} />}
      {o.layout === 'text' && (
        <div style={{fontFamily: BODY_FONT, fontWeight: 'bold', fontStyle: 'italic', fontSize: 30, lineHeight: '42px',
          color: COPPER}}>
          <Highlighted text={o.text ?? ''} highlights={o.highlights} t={t} />
        </div>
      )}
      {o.layout === 'list' && (o.items ?? []).map((it, i) => {
        const r = reveal(frame, fps, Math.round((it.at - o.t0) * fps));
        return (
          <div key={i} style={{opacity: r.opacity, transform: `translateY(${r.y}px)`, display: 'flex',
            alignItems: 'flex-start', marginBottom: 22}}>
            <div style={{width: 48, flexShrink: 0, color: COPPER, fontFamily: BODY_FONT, fontSize: 34, lineHeight: '44px'}}>
              •
            </div>
            <div style={{fontFamily: BODY_FONT, fontWeight: 'bold', fontStyle: 'italic', fontSize: 34, lineHeight: '44px',
              color: COPPER}}>
              <Labelled text={it.text} />
            </div>
          </div>
        );
      })}
    </Card>
  );
};

const OverlayBody: React.FC<{o: OverlayLayer; dur: number}> = ({o, dur}) => {
  switch (o.layout) {
    case 'chapter_card': return <ChapterCard o={o} />;
    case 'term_chip': return <TermChip o={o} />;
    case 'choice_panel': return <ChoicePanel o={o} />;
    case 'word_build': return <WordBuild o={o} />;
    case 'map_pins': return <MapPins o={o} />;
    default: return <OverlayCard o={o} dur={dur} />;
  }
};

export const Overlays: React.FC<{overlays: OverlayLayer[]; only?: number}> = ({overlays, only}) => {
  const {fps} = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
  return <>{overlays.map((o, i) => (only === undefined || only === i) && (
    <Sequence key={o.id} from={f(o.t0)} durationInFrames={Math.max(1, f(o.t1) - f(o.t0))} layout="none">
      <OverlayBody o={o} dur={f(o.t1) - f(o.t0)} />
    </Sequence>
  ))}</>;
};

export {MARK};
