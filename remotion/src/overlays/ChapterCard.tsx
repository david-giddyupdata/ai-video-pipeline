import React from 'react';
import {AbsoluteFill} from 'remotion';
import {exitLeft, FONT, look, MOTION, PreviewProps, PreviewStage, prog, rgba, SIZE, TOKENS, useEditTime, Variant}
  from './kit';

// ChapterCard (R141; the overlay plan's composition 1): a full-screen chapter marker at a section transition, the
// part's name, in the spirit of David's FullScreenTitle markers (a scrim over the picture, the title centred in gold).
// The new set's look (R131): the panel colour as the scrim, Segoe UI Semibold, a short rule, and "Neutral
// data-story" motion: 1.0 s in (scrim, kicker, rule, then the title word by word, 80 ms apart, no overshoot), held,
// 0.6 s out. Variant (R140): dark on a light screen, light on a dark one. Fonts by name only (R135, R143).

export type ChapterCardLayer = {id: string; step?: string; layout: 'chapter_card'; t0: number; t1: number;
  variant: Variant; title: string; kicker?: string};

const SCRIM_OPACITY = TOKENS.color.scrimOpacity;   // the screen shows faintly through, as under FullScreenTitle
const RISE = MOTION.risePx;

export const ChapterCard: React.FC<{o: ChapterCardLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const L = look(o.variant);
  const {inS, outS} = MOTION.composition.chapterCard;
  const a = t - o.t0;                                      // seconds since the card began
  const scrim = prog(a, 0, inS * 0.5);
  const kicker = prog(a, inS * 0.15, inS * 0.4);
  const rule = prog(a, inS * 0.3, inS * 0.5);
  const words = o.title.split(' ');
  const wordS = inS * 0.45;
  const first = inS * 0.4;
  const stagger = words.length > 1 ? Math.min(MOTION.staggerS, (inS - first - wordS) / (words.length - 1)) : 0;
  const out = exitLeft(t, o.t1, outS, fps);
  // the rule separates the kicker from the title, or underlines a title that stands alone
  const ruleBar = <div style={{width: 300, height: 4, margin: o.kicker ? '30px 0 34px' : '40px 0 0', background: L.rule,
    transform: `scaleX(${rule})`}} />;
  return (
    <AbsoluteFill style={{opacity: out}}>
      <AbsoluteFill style={{background: rgba(L.panel, SCRIM_OPACITY * scrim)}} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
        {o.kicker && (
          <div style={{...FONT.heading, fontSize: SIZE.chapterKicker, letterSpacing: '0.14em', textTransform: 'uppercase',
            color: o.variant === 'light' ? L.muted : L.body, opacity: kicker,
            transform: `translateY(${(1 - kicker) * RISE}px)`}}>
            {o.kicker}
          </div>
        )}
        {o.kicker && ruleBar}
        <div style={{...FONT.heading, fontSize: SIZE.chapterTitle, lineHeight: 1.15, color: L.heading, maxWidth: 1600,
          display: 'flex', flexWrap: 'wrap', justifyContent: 'center', textAlign: 'center'}}>
          {words.map((w, i) => {
            const p = prog(a, first + i * stagger, wordS);
            return (
              <span key={i} style={{display: 'inline-block', whiteSpace: 'nowrap', opacity: p,
                transform: `translateY(${(1 - p) * RISE}px)`, marginRight: i < words.length - 1 ? '0.26em' : 0}}>
                {w}
              </span>
            );
          })}
        </div>
        {!o.kicker && ruleBar}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export type ChapterCardProps = PreviewProps<ChapterCardLayer>;

export const CHAPTER_CARD_SAMPLE: ChapterCardProps = {durationInFrames: 120, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'chapter-1', layout: 'chapter_card', t0: 0, t1: 4, variant: 'dark', kicker: 'Part 1',
    title: 'Connect to Data'}};

export const ChapterCardPreview: React.FC<ChapterCardProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><ChapterCard o={layer} /></PreviewStage>
);
