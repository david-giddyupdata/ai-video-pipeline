import React from 'react';
import {Box, Edge, exitLeft, FONT, look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog, rgba, SIZE, spaced,
  useEditTime, Variant, lh} from './kit';

// WordBuild (the overlay plan's composition 4; David's kinetic word list of ep03, 00:00:11:19): a list or an acronym
// that builds word by word on the spoken words (items' `at`, R80), in Segoe Print (R143). Each word is a 0.25 s pop
// (a quick scale-up, no overshoot: the informative energy); the panel fades in over 0.5 s and out over 0.5 s.
//   list     one word or phrase a row
//   acronym  the acronym's letters stand down the left from the start, in outline (the acronym has been named); each
//            word fills its letter and pops in beside it ("S" + "uper-fast")
//   data     a pattern built piece by piece in Courier New (R143), a label beneath each piece and the separator
//            appearing with the piece after it: "MM / dd / yyyy" over "month, day, four-digit year"
// Variant (R140); placement a box in frame px or an edge of title-safe (right by default, a data row at the top).

export type WordItem = {text: string; at: number; label?: string};
export type WordBuildLayer = {id: string; step?: string; layout: 'word_build'; t0: number; t1: number;
  variant: Variant; mode: 'list' | 'acronym' | 'data'; title?: string; items: WordItem[]; sep?: string; box?: Box;
  edge?: Edge};

const POP_FROM = 0.6;           // a word starts at 60% of its size
const OUTLINE = 2;              // an acronym letter before its word: its outline at full strength, filled on its word
                                // (R179: the dimmed letter measured 1.7:1; the outline is the heading colour, 8.3:1)

export const WordBuild: React.FC<{o: WordBuildLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const L = look(o.variant);
  const m = MOTION.composition.wordBuild;
  const p = prog(t, o.t0, m.inS);
  const starts = spaced(o.items.map((it) => it.at), MOTION.staggerS);
  const pop = (i: number) => prog(t, starts[i], m.wordS);
  const popStyle = (q: number, origin: string): React.CSSProperties => ({display: 'inline-block', opacity: Math.min(1, q * 1.6),
    transform: `scale(${POP_FROM + (1 - POP_FROM) * q})`, transformOrigin: origin});
  const title = o.title && (
    <div style={{...FONT.heading, fontSize: SIZE.heading, lineHeight: lh(SIZE.heading), color: L.heading, marginBottom: 10,
      textAlign: o.mode === 'data' ? 'center' : 'left'}}>{o.title}</div>
  );

  let body: React.ReactNode;
  if (o.mode === 'data') {
    const sep = (o.sep ?? '/').trim();
    body = (
      <div style={{display: 'flex', alignItems: 'flex-start', gap: 6}}>
        {o.items.map((it, i) => {
          const q = pop(i);
          return (
            <React.Fragment key={i}>
              {i > 0 && sep && (
                <div style={{...FONT.data, fontSize: SIZE.data, lineHeight: lh(SIZE.data, 1.25), color: L.muted, opacity: Math.min(1, q * 1.6),
                  padding: '0 16px'}}>{sep}</div>
              )}
              <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center',
                minWidth: it.text.length * 0.6 * SIZE.data + 24}}>
                <div style={{...FONT.data, fontSize: SIZE.data, lineHeight: lh(SIZE.data, 1.25), color: L.heading, ...popStyle(q, 'center bottom')}}>
                  {it.text}
                </div>
                {it.label && (
                  // a label wider than its piece wraps (Courier New is 0.6 em a character), so a long one ("four-digit
                  // year") doesn't push its piece away from the separator
                  <div style={{...FONT.body, fontSize: SIZE.label, lineHeight: lh(SIZE.label), color: L.body, textAlign: 'center',
                    maxWidth: Math.max(140, it.text.length * 0.6 * SIZE.data + 60),
                    opacity: prog(t, starts[i] + m.wordS * 0.4, m.wordS)}}>{it.label}</div>
                )}
              </div>
            </React.Fragment>
          );
        })}
      </div>
    );
  } else if (o.mode === 'acronym') {
    // the letter and the rest of its word sit in one line of text, so the word reads whole ("Super-fast")
    body = o.items.map((it, i) => {
      const q = pop(i);
      return (
        <div key={i} style={{...FONT.wordList, height: Math.round(SIZE.wordListInitial * 1.2), lineHeight: lh(SIZE.wordListInitial, 1.2), whiteSpace: 'nowrap'}}>
          <span style={{fontSize: SIZE.wordListInitial, color: rgba(L.heading, q), WebkitTextStroke: `${OUTLINE}px ${L.heading}`}}>
            {it.text.slice(0, 1)}
          </span>
          <span style={{fontSize: SIZE.wordList, color: L.body, ...popStyle(q, 'left 70%')}}>{it.text.slice(1)}</span>
        </div>
      );
    });
  } else {
    body = o.items.map((it, i) => (
      <div key={i} style={{...FONT.wordList, fontSize: SIZE.wordList, lineHeight: lh(SIZE.wordList, 1.45), color: L.body, whiteSpace: 'nowrap'}}>
        <span style={popStyle(pop(i), 'left center')}>{it.text}</span>
      </div>
    ));
  }

  return (
    <Placed box={o.box} edge={o.edge} fallback={o.mode === 'data' ? 'top' : 'right'}>
      <div style={{opacity: p * exitLeft(t, o.t1, m.outS, fps)}}>
        <Panel variant={o.variant} style={{padding: o.mode === 'data' ? '22px 44px 26px' : '24px 48px 28px 32px'}}>
          {title}
          {body}
        </Panel>
      </div>
    </Placed>
  );
};

export type WordBuildProps = PreviewProps<WordBuildLayer>;

// p1.38: "It stands for Super-fast, Parallel, In-memory Calculation Engine."
export const WORD_BUILD_SAMPLE: WordBuildProps = {durationInFrames: 150, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'spice', layout: 'word_build', t0: 0.3, t1: 4.8, variant: 'dark', mode: 'acronym',
    items: [{text: 'Super-fast', at: 0.8}, {text: 'Parallel', at: 1.3}, {text: 'In-memory', at: 1.8},
      {text: 'Calculation', at: 2.3}, {text: 'Engine', at: 2.8}], edge: 'right'}};

export const WordBuildPreview: React.FC<WordBuildProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><WordBuild o={layer} /></PreviewStage>
);
