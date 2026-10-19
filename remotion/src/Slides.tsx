// Opening and recap motion graphics (R69): text slides over a still of the finished dashboard, timed to the narration.
// Props come from pipeline.edit.slides (times in seconds). The look is David's own, ported, not imported:
//   title    FullScreenTitle (Global Assets/remotion-motion): #e4c493 Arial Bold Italic with glow, per-letter fall-back
//   list     BulletPanel: the light two-tone card, copper text, Arial Black title, slide-in spring {18, 120, 0.8}
//   compare  ComparisonTable: copper header bars, gold labels, white cells on a dark backing
//   roadmap  numbered rows on the BulletPanel card; the ep02 roadmap's 8 px #F16F05 square rectangle moves to the row
//            being named (R48, R51); with checks, kb-overlay's draw-on check mark (QuickSeries/kb-overlay)
import React from 'react';
import {AbsoluteFill, Audio, Img, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig}
  from 'remotion';

type Item = {text: string; style: 'item' | 'callout' | 'quote' | 'use'; at: number};
type Column = {title: string; at: number; items: Item[]};
type Slide = {id: string; layout: 'title' | 'list' | 'roadmap' | 'compare'; start: number; end: number; title?: string;
  kicker?: string; checks?: boolean; items?: Item[]; columns?: Column[]};
export type SlidesProps = {fps: number; width: number; height: number; durationInFrames: number; still: string;
  sequence: string; audio: {src: string; at: number}[]; slides: Slide[]};

// Brand (video-production.md; kb-overlay constants.ts)
const GOLD_LIGHT = '#e4c493';
export const COPPER = '#9A592B';
const TEAL = '#355c67';
export const MARK = '#F16F05';     // R51
const CREAM = '#f8f6f3';
const SCRIM = 'rgba(0, 0, 0, 0.55)';  // lighter than FullScreenTitle's 0.8, so the dashboard shows through
const CARD_SCRIM = 'rgba(0, 0, 0, 0.78)';   // a title card over the light IDE (R79): FullScreenTitle's own 0.8
const TITLE_FONT = "'Arial Black', Arial, sans-serif";
export const BODY_FONT = 'ArialBI, Arial, sans-serif';
const BG_ZOOM = 0.06;               // the still pushes in linearly over the whole sequence (R45: linear camera)
const EXIT_S = 0.4;
const MARK_FADE_S = 0.25;           // edit_settings marks.fade_in_s

export const fontFace = `@font-face{font-family:'ArialBI';src:url('${staticFile('fonts/arialbi.ttf')}') format('truetype');
  font-weight:bold;font-style:italic;font-display:block;}`;

// --- animations, from remotion-motion lib/animations.ts --------------------------------------------------------
const useSec = () => {
  const {fps} = useVideoConfig();
  return (s: number) => Math.round(s * fps);
};

export const reveal = (frame: number, fps: number, start: number) => {
  const local = frame - start;
  if (local < 0) return {opacity: 0, y: 20};
  const p = spring({frame: local, fps, config: {damping: 20, stiffness: 150, mass: 0.6}, durationInFrames: 18});
  return {opacity: p, y: interpolate(p, [0, 1], [20, 0])};
};

const FallBackTitle: React.FC<{text: string; start: number; size: number; color: string; glow?: boolean}> =
  ({text, start, size, color, glow}) => {
    const frame = useCurrentFrame();
    const {fps} = useVideoConfig();
    return (
      <div style={{fontFamily: BODY_FONT, fontWeight: 'bold', fontStyle: 'italic', fontSize: size, color,
        lineHeight: 1.2, display: 'flex', flexWrap: 'wrap', justifyContent: 'center',
        textShadow: glow ? `0 0 8px ${color}, 0 0 20px ${color}88, 0 0 40px ${color}44` : undefined}}>
        {/* letters grouped by word, so a line only breaks between words */}
        {text.split(' ').map((word, wi, words) => {
          const offset = words.slice(0, wi).reduce((n, w) => n + w.length + 1, 0);
          return (
            <span key={wi} style={{display: 'inline-block', whiteSpace: 'nowrap',
              marginRight: wi < words.length - 1 ? '0.28em' : 0}}>
              {word.split('').map((ch, ci) => {
                const local = frame - (start + (offset + ci) * 2);
                const p = local < 0 ? 0 : spring({frame: local, fps, config: {damping: 14, stiffness: 80, mass: 1}});
                return (
                  <span key={ci} style={{display: 'inline-block', transformOrigin: 'center bottom',
                    opacity: interpolate(p, [0, 0.3], [0, 1], {extrapolateRight: 'clamp'}),
                    transform: `perspective(800px) rotateX(${interpolate(p, [0, 1], [-60, 0])}deg) ` +
                      `scale(${interpolate(p, [0, 1], [1.4, 1])}) skewX(${interpolate(p, [0, 1], [8, 0])}deg)`}}>
                    {ch}
                  </span>
                );
              })}
            </span>
          );
        })}
      </div>
    );
  };

const Check: React.FC<{size: number; progress: number; color: string}> = ({size, progress, color}) => (
  <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}
    style={{overflow: 'visible', display: 'block', opacity: progress > 0.02 ? 1 : 0}}>
    <path d={`M ${size * 0.2} ${size * 0.54} L ${size * 0.42} ${size * 0.74} L ${size * 0.8} ${size * 0.28}`}
      fill="none" stroke={color} strokeWidth={size * 0.15} strokeLinecap="round" strokeLinejoin="round"
      pathLength={1} strokeDasharray={1} strokeDashoffset={1 - progress} />
  </svg>
);

// "Label: detail" -> the label in Arial Black, as BulletPanel does
export const Labelled: React.FC<{text: string; labelColor?: string}> = ({text, labelColor}) => {
  const i = text.indexOf(': ');
  if (i < 0) return <>{text}</>;
  return (<><span style={{fontFamily: TITLE_FONT, fontStyle: 'normal', color: labelColor}}>{text.slice(0, i + 1)}</span>
    {text.slice(i + 1)}</>);
};

// --- the BulletPanel card: half the frame, sliding in from one edge ----------------------------------------------
// top: an overlay card (R77) sits from 40 px down to 260 px above the bottom (pipeline.edit.marks overlay_box), so
// the bottom caption row stays free; the slides' cards are vertically centred.
export const Card: React.FC<{edge: 'left' | 'right'; dur: number; top?: boolean; children: React.ReactNode}> =
  ({edge, dur, top, children}) => {
    const frame = useCurrentFrame();
    const {fps, width, height} = useVideoConfig();
    const sec = useSec();
    const w = width / 2;
    const off = edge === 'right' ? w : -w;
    const pin = spring({frame, fps, config: {damping: 18, stiffness: 120, mass: 0.8}, durationInFrames: 15});
    const outStart = dur - sec(EXIT_S);
    const pout = frame < outStart ? 0 :
      spring({frame: frame - outStart, fps, config: {damping: 18, stiffness: 120, mass: 0.8}, durationInFrames: 12});
    const x = interpolate(pin, [0, 1], [off, 0]) + interpolate(pout, [0, 1], [0, off]);
    const place: React.CSSProperties = top
      ? {top: 40, height: height - 300, transform: `translate(${x}px, 0)`, overflow: 'hidden'}
      : {top: '50%', minHeight: 560, maxHeight: 1000, transform: `translate(${x}px, -50%)`};
    return (
      <div style={{position: 'absolute', width: w - 60, [edge]: 40, ...place,
        borderRadius: 28, background: 'linear-gradient(135deg, #EAF4F8 0%, #EAF4F8 45%, #E7E6DF 55%, #E7E6DF 100%)',
        boxShadow: '0 12px 40px rgba(0,0,0,0.45)', padding: top ? '48px 56px' : '70px 64px', boxSizing: 'border-box'}}>
        {children}
      </div>
    );
  };

export const CardTitle: React.FC<{text: string; size?: number}> = ({text, size}) => (
  <div style={{marginBottom: size ? 28 : 40}}>
    <FallBackTitle text={text} start={8} size={size ?? 54} color={COPPER} />
  </div>
);

// --- the title card over a long live wait (R39): "Claude is building" / "about N minutes", on a frozen frame ------
// Legible on any background (R79): a darker scrim than the slides' and a dark plate behind the text, so the gold
// reads over the light IDE as it did over the dark dashboard still.
export const TitleCard: React.FC<{title: string; sub?: string; dur: number}> = ({title, sub, dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sec = useSec();
  const r = reveal(frame, fps, sec(0.6));
  const out = interpolate(frame, [dur - sec(EXIT_S), dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: out, backgroundColor: CARD_SCRIM}}>
      <style>{fontFace}</style>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '56px 110px 64px',
        borderRadius: 28, background: 'rgba(12, 12, 12, 0.88)', boxShadow: '0 12px 48px rgba(0,0,0,0.6)'}}>
        <FallBackTitle text={title} start={0} size={100} color={GOLD_LIGHT} glow />
        {sub && (
          <div style={{marginTop: 36, opacity: r.opacity, transform: `translateY(${r.y}px)`, color: CREAM,
            fontFamily: BODY_FONT, fontWeight: 'bold', fontStyle: 'italic', fontSize: 56,
            textShadow: '0 2px 6px rgba(0,0,0,0.85)'}}>{sub}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};

// --- layouts -------------------------------------------------------------------------------------------------
const TitleSlide: React.FC<{s: Slide; dur: number}> = ({s, dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sec = useSec();
  const k = reveal(frame, fps, 0);
  const out = interpolate(frame, [dur - sec(EXIT_S), dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: out,
      backgroundColor: 'rgba(0, 0, 0, 0.35)'}}>
      {s.kicker && (
        <div style={{opacity: k.opacity, transform: `translateY(${k.y}px)`, marginBottom: 36, padding: '12px 28px',
          background: 'rgba(53,92,103,0.9)', border: `1px solid ${GOLD_LIGHT}`, borderRadius: 10, color: GOLD_LIGHT,
          fontFamily: BODY_FONT, fontWeight: 'bold', fontStyle: 'italic', fontSize: 34}}>{s.kicker}</div>
      )}
      <FallBackTitle text={s.title ?? ''} start={sec(0.3)} size={100} color={GOLD_LIGHT} glow />
      <div style={{marginTop: 48, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
        {(s.items ?? []).map((it, i) => {
          const r = reveal(frame, fps, sec(it.at - s.start));
          return (
            <div key={i} style={{opacity: r.opacity, transform: `translateY(${r.y}px)`, color: CREAM,
              fontFamily: BODY_FONT, fontWeight: 'bold', fontStyle: 'italic', fontSize: 46,
              textShadow: '0 2px 6px rgba(0,0,0,0.85)'}}>{it.text}</div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const ListSlide: React.FC<{s: Slide; dur: number; edge: 'left' | 'right'; checks: boolean}> = ({s, dur, edge, checks}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sec = useSec();
  return (
    <Card edge={edge} dur={dur}>
      <CardTitle text={s.title ?? ''} />
      {(s.items ?? []).map((it, i) => {
        const start = sec(it.at - s.start);
        const r = reveal(frame, fps, start);
        const callout = it.style === 'callout';
        const tick = interpolate(frame - start, [sec(0.15), sec(0.75)], [0, 1],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        return (
          <div key={i} style={{opacity: r.opacity, transform: `translateY(${r.y}px)`, display: 'flex',
            alignItems: 'flex-start', marginBottom: 26, marginTop: callout ? 24 : 0,
            borderLeft: callout ? `8px solid ${TEAL}` : undefined, paddingLeft: callout ? 22 : 0}}>
            {!callout && (
              <div style={{width: 56, flexShrink: 0, color: COPPER, fontFamily: TITLE_FONT, fontSize: 40,
                lineHeight: '50px'}}>
                {checks ? <div style={{paddingTop: 4}}><Check size={42} progress={tick} color={TEAL} /></div> : '•'}
              </div>
            )}
            <div style={{fontFamily: BODY_FONT, fontWeight: 'bold', fontStyle: 'italic', fontSize: 40, lineHeight: '50px',
              color: callout ? TEAL : COPPER}}>
              <Labelled text={it.text} />
            </div>
          </div>
        );
      })}
    </Card>
  );
};

const RoadmapSlide: React.FC<{s: Slide; dur: number; edge: 'left' | 'right'}> = ({s, dur, edge}) => {
  const frame = useCurrentFrame();
  const sec = useSec();
  const items = s.items ?? [];
  const ROW = 118;
  const local = (t: number) => sec(t - s.start);
  // the orange rectangle sits on the row most recently named and fades between rows (one mark at a time, R51)
  const current = items.reduce((c, it, i) => (frame >= local(it.at) ? i : c), -1);
  return (
    <Card edge={edge} dur={dur}>
      <CardTitle text={s.title ?? ''} />
      <div style={{position: 'relative', height: items.length * ROW}}>
        {items.map((it, i) => {
          const named = interpolate(frame, [local(it.at), local(it.at) + sec(MARK_FADE_S)], [0, 1],
            {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const fadeIn = interpolate(frame, [sec(0.4) + i * 3, sec(0.7) + i * 3], [0, 1],
            {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const tick = interpolate(frame - local(it.at), [sec(0.15), sec(0.75)], [0, 1],
            {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const next = items[i + 1];
          const markIn = interpolate(frame, [local(it.at) + sec(0.1), local(it.at) + sec(0.1 + MARK_FADE_S)], [0, 1],
            {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const markOut = next ? interpolate(frame, [local(next.at), local(next.at) + sec(0.1)], [1, 0],
            {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
          const mark = i === current || i === current - 1 ? Math.min(markIn, markOut) : 0;
          return (
            <div key={i} style={{position: 'absolute', top: i * ROW, left: 0, right: 0, height: ROW - 18,
              display: 'flex', alignItems: 'center', opacity: fadeIn * (0.4 + 0.6 * named)}}>
              <div style={{width: 64, height: 64, borderRadius: 32, background: TEAL, color: '#fff', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: TITLE_FONT, fontSize: 32}}>
                {s.checks && tick > 0 ? <Check size={40} progress={tick} color="#fff" /> : i + 1}
              </div>
              <div style={{marginLeft: 28, fontFamily: BODY_FONT, fontWeight: 'bold', fontStyle: 'italic', fontSize: 38,
                lineHeight: '46px', color: COPPER}}>{it.text}</div>
              <div style={{position: 'absolute', left: -18, right: -18, top: -6, bottom: -6, border: `8px solid ${MARK}`,
                opacity: mark}} />
            </div>
          );
        })}
      </div>
    </Card>
  );
};

const CompareSlide: React.FC<{s: Slide; dur: number}> = ({s, dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sec = useSec();
  const first = sec(((s.columns ?? [])[0]?.at ?? s.start) - s.start);
  const inn = interpolate(frame, [first - sec(0.3), first], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const out = interpolate(frame, [dur - sec(EXIT_S), dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: inn * out}}>
      <div style={{display: 'flex', gap: 48, padding: 48, borderRadius: 18, background: 'rgba(0,0,0,0.78)'}}>
        {(s.columns ?? []).map((c, ci) => {
          const h = reveal(frame, fps, sec(c.at - s.start));
          return (
            <div key={ci} style={{width: 760, opacity: h.opacity, transform: `translateY(${h.y}px)`}}>
              <div style={{background: COPPER, borderRadius: 8, padding: '18px 28px', color: '#fff',
                fontFamily: TITLE_FONT, fontSize: 40, marginBottom: 14}}>{c.title}</div>
              {c.items.map((it, i) => {
                const r = reveal(frame, fps, sec(it.at - s.start));
                const quote = it.style === 'quote';
                const use = it.style === 'use';
                return (
                  <div key={i} style={{opacity: r.opacity, transform: `translateY(${r.y}px)`, padding: '16px 28px',
                    marginTop: use ? 22 : 8, borderRadius: 6,
                    background: use ? 'rgba(53,92,103,0.55)' : i % 2 ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.06)',
                    fontFamily: quote ? BODY_FONT : 'Arial, sans-serif', fontWeight: quote ? 'bold' : 'normal',
                    fontStyle: quote ? 'italic' : 'normal', fontSize: 34, lineHeight: '44px',
                    color: quote ? GOLD_LIGHT : '#fff'}}>
                    <Labelled text={it.text} labelColor={GOLD_LIGHT} />
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// --- the composition -----------------------------------------------------------------------------------------
export const Slides: React.FC<SlidesProps> = ({still, audio, slides, durationInFrames}) => {
  const frame = useCurrentFrame();
  const sec = useSec();
  const zoom = 1 + BG_ZOOM * frame / Math.max(1, durationInFrames);
  let side = 0;
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <style>{fontFace}</style>
      <AbsoluteFill style={{transform: `scale(${zoom})`}}>
        <Img src={staticFile(still)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </AbsoluteFill>
      <AbsoluteFill style={{backgroundColor: SCRIM}} />
      {slides.map((s) => {
        const from = sec(s.start);
        const dur = Math.max(1, sec(s.end) - from);
        const edge: 'left' | 'right' = s.layout === 'list' || s.layout === 'roadmap' ? (side++ % 2 ? 'left' : 'right')
          : 'right';
        return (
          <Sequence key={s.id} from={from} durationInFrames={dur} layout="none">
            {s.layout === 'title' && <TitleSlide s={s} dur={dur} />}
            {s.layout === 'list' && <ListSlide s={s} dur={dur} edge={edge} checks={s.id === 'before'} />}
            {s.layout === 'roadmap' && <RoadmapSlide s={s} dur={dur} edge={edge} />}
            {s.layout === 'compare' && <CompareSlide s={s} dur={dur} />}
          </Sequence>
        );
      })}
      {audio.map((a) => (
        <Sequence key={a.src} from={sec(a.at)} layout="none">
          <Audio src={staticFile(a.src)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
