import React, {useId} from 'react';
import {measureText} from '@remotion/layout-utils';
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import CTA from './data/cta.json';
import {ACCENT, FONT, prog, TOKENS} from './kit';

// SubscribeCta (R242): the call to action's subscribe animation rebuilt in code, in four variations for David to pick,
// replacing the Motion Array clip his Quick Series used (02.Youtube SubscribesV2.mov, R232; R131: away from Motion
// Array). Measured from that clip (30 fps, 7.5 s, placed full frame in QuickArch03 at 00:07:21; research/backgrounds/
// refs_ep03/ep03_cta.json):
//   * lower left: a bell (143 px, with its two sound arcs) and a thumbs-up (159 x 136), a red bar (13 x 183,
//     #cc2221 at the top to #780f0f) at x 509, and "Thanks for Watching!" (a geometric bold, cap height 50) from x 559;
//   * the bar grows from its middle (0.13 to 0.43 s), the bell slides out left from behind it (0.43 to 0.8), then the
//     thumb (0.7 to 1.0); the words slide out right from behind it (1.2 to 1.5); a hand comes up to the bell, clicks it
//     (1.9: the bell turns 3D and rings), moves to the thumb with a red swoosh and clicks it (2.87: it turns 3D), and
//     drops away; at the end the words slide back (from 6.4), the icons slide back behind the bar, the bar shrinks
//     to its middle (to 7.4).
// The four variations (props `variant`):
//   'classic' a close copy of that; 'brand' the same in David's brand colours (the house tokens); 'pill' a compact one,
//   icons and words on one rounded pill; 'soft' the same layout with softer, calmer motion and no hand.
// Times are seconds on the clip (the stage's clock): t0 the entrance, bell and thumb the two clicks (round 7's hooks
// on "subscribe" and "thumbs": subscribeTimes below), t1 the end (gone by then). The stage places the sounds (R235:
// a whoosh as it enters, a bell on the bell's click, R137's click on the thumb's) from subscribeMoments().
// "Thanks for Watching!" keeps its own colours (G6's exemption, R235); everything else in the frame is transparent.

export type SubscribeVariant = 'classic' | 'brand' | 'pill' | 'soft';
export type SubscribeLayer = {variant: SubscribeVariant; text: string; t0: number; bell: number; thumb: number;
  t1: number; dx?: number; dy?: number};       // dx, dy: moves the whole piece from the original's place (frame px)
export type SubscribeProps = {durationInFrames: number; fps: number; width: number; height: number; still?: string;
  layer: SubscribeLayer};

// The original's own moments and each variation's whoosh: data/cta.json (one copy, read by tools/remotion_ctas.py too).
// The clip starts 1.32 s before "subscribe"; its bell is clicked 1.9 s in (as "subscribe" ends), its thumb 2.867 s in;
// it lasts 7.52 s. The whoosh starts when each variation's entrance starts moving.
export const ORIGINAL = CTA.subscribe.original;
const WHOOSH_AT: Record<SubscribeVariant, number> = CTA.subscribe.whooshAtS;

// Round 7's hooks: from the words' starts on the stage's clock. The bell rings as "subscribe" ends (0.58 s after its
// start, as in QuickArch03), the thumb 0.14 s into "thumbs" (round 7's 41.011 against 40.869), never closer than
// 0.75 s after the bell (the hand's move); the piece stays at least 4.65 s after the thumb's click (its 3D turn, the
// hold, the exit), so a late "thumbs" never lands in the exit; never before the clip's start (Fable, R242).
export const subscribeTimes = (w: {subscribe: number; thumbs: number}) => {
  const S = CTA.subscribe;
  const t0 = Math.max(0, w.subscribe - ORIGINAL.leadS);
  const bell = Math.max(t0 + ORIGINAL.bellS, w.subscribe + ORIGINAL.bellS - ORIGINAL.leadS);
  const thumb = Math.max(bell + S.minBellToThumbS, w.thumbs + S.thumbAfterWordS);
  return {t0, bell, thumb, t1: Math.max(t0 + ORIGINAL.lengthS, thumb + S.afterThumbS)};
};
// The sounds' moments for the stage (seconds on the same clock).
export const subscribeMoments = (o: SubscribeLayer) => ({whoosh: o.t0 + WHOOSH_AT[o.variant], bell: o.bell,
  click: o.thumb});

// ---- the original's geometry (frame px), and the house's colours for 'brand' ----
const BAR = {x: 509, y: 745, w: 13, h: 183};
const BELL = {x: 121, y: 775, w: 143, h: 143};
const THUMB = {x: 296, y: 774, w: 159, h: 136};
const TEXT = {x: 559, cy: 832};
const TEXT_PX = 62;                // Montserrat Bold: about the original's width (700 against 680 px), cap 44 (G3: 60+)
const RED = {top: '#cc2221', bottom: '#780f0f', swoosh: '#e0201b', on: '#ff2a1f'};
const B = TOKENS.color.brand;
type Palette = {face: string; faceShade: string; detail: string; side: [string, string]; barTop: string; barBottom: string;
  text: string; textShadow?: string; hand: string; handLine: string; swoosh: string; on: string};
const PALETTES: Record<'classic' | 'brand' | 'soft', Palette> = {
  classic: {face: '#ffffff', faceShade: '#dcdcdc', detail: '#cdcdcd', side: ['#c4c4c4', '#8e8e8e'], barTop: RED.top, barBottom: RED.bottom,
    text: '#ffffff', hand: '#ffffff', handLine: '#3a3a3a', swoosh: RED.swoosh, on: '#ffffff'},
  brand: {face: B.cream, faceShade: '#e8ddcc', detail: '#d5bf9d', side: ['#c9a06a', '#7b4622'], barTop: ACCENT, barBottom: B.copper,
    text: B.gold, textShadow: '0 2px 10px rgba(0, 0, 0, 0.45)', hand: B.cream, handLine: B.brown, swoosh: ACCENT,
    on: B.cream},
  soft: {face: '#ffffff', faceShade: '#ffffff', detail: '#ffffff', side: ['#ffffff', '#ffffff'], barTop: '#ff4b3e', barBottom: '#b3140c',
    text: '#ffffff', textShadow: '0 2px 12px rgba(0, 0, 0, 0.40)', hand: '#ffffff', handLine: '#3a3a3a',
    swoosh: RED.swoosh, on: RED.on},
};
// Montserrat Bold (OFL, installed on David's PC; R135: nothing new installed) is the nearest installed face to the
// original's geometric bold; the house's Segoe UI (G11) for the brand and soft variations; Inter where either is missing.
const MONTSERRAT: React.CSSProperties = {fontFamily: 'Montserrat, Inter, sans-serif', fontWeight: 700};
const SEGOE_BOLD: React.CSSProperties = {fontFamily: '"Segoe UI", Inter, sans-serif', fontWeight: 700};

const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const lin = (t: number, a: number, d: number) => (d <= 0 ? (t >= a ? 1 : 0) : clamp01((t - a) / d));
const easeOut = (t: number, a: number, d: number) => 1 - (1 - lin(t, a, d)) ** 3;
const easeInOut = (t: number, a: number, d: number) => {
  const p = lin(t, a, d);
  return p < 0.5 ? 4 * p * p * p : 1 - (-2 * p + 2) ** 3 / 2;
};

// ---- the shapes (each drawn in its own box, filled; the original's flat white icons) ----
// detail: the lines that part the bell's lip from its body and the thumb's fingers (on the face only)
const BellShape: React.FC<{fill: string; arcs?: boolean; detail?: string}> = ({fill, arcs = true, detail}) => (
  <>
    <circle cx={71.5} cy={14} r={9} fill={fill} />
    <path d="M71.5 20 C46 20 34 40 34 64 L34 84 C34 93 28 99 20 104 L123 104 C115 99 109 93 109 84 L109 64
      C109 40 97 20 71.5 20 Z" fill={fill} />
    <rect x={16} y={100} width={111} height={13} rx={6.5} fill={fill} />
    <path d="M58 115 A13.5 13.5 0 0 0 85 115 Z" fill={fill} />
    {arcs ? (
      <>
        <path d="M21 28 Q3 58 21 88" fill="none" stroke={fill} strokeWidth={8} strokeLinecap="round" />
        <path d="M122 28 Q140 58 122 88" fill="none" stroke={fill} strokeWidth={8} strokeLinecap="round" />
      </>
    ) : null}
    {detail ? <path d="M24 100.5 L119 100.5 M60 114 L83 114" stroke={detail} strokeWidth={2.5} strokeLinecap="round" />
      : null}
  </>
);
const ThumbShape: React.FC<{fill: string; gap?: string}> = ({fill, gap}) => (
  <>
    <rect x={0} y={54} width={40} height={82} rx={7} fill={fill} />
    <path d="M50 58 L74 56 C86 44 92 30 92 14 C92 2 108 -2 114 8 C122 22 118 42 112 54 L146 54 C156 54 160 66 152 72
      C160 78 158 90 150 92 C156 98 154 110 146 112 C151 118 148 132 138 132 L58 132 C53 132 50 128 50 124 Z"
      fill={fill} />
    {/* the fingers' gaps */}
    {gap ? [73, 92, 112].map((y) => (
      <path key={y} d={`M${y === 73 ? 122 : 120} ${y} L154 ${y}`} stroke={gap} strokeWidth={3} strokeLinecap="round" />
    )) : null}
  </>
);
// The pointing hand (its fingertip at TIP in its own 70 x 86 box).
const HAND_TIP = {x: 31, y: 4};
const HandShape: React.FC<{fill: string; line: string}> = ({fill, line}) => (
  <g strokeLinejoin="round" strokeLinecap="round">
    <path d="M26 8 C26 2 36 2 36 8 L36 38 L36 34 C36 28 46 28 46 34 L46 40 C46 34 56 34 56 40 L56 44 C56 38 66 38 66 44
      L66 62 C66 76 57 84 45 84 L38 84 C29 84 23 80 18 73 L7 57 C4 52 9 46 14 50 L26 62 Z" fill={fill} stroke={line}
      strokeWidth={4.5} />
    <path d="M46 40 L46 52 M56 44 L56 54" stroke={line} strokeWidth={3.5} fill="none" />
  </g>
);

// An icon that turns 3D when clicked (the original's): its face over a stack of copies in the side's shades, the whole
// turned about its upright; depth 0 is the flat icon.
const Turned: React.FC<{w: number; h: number; depth: number; turn: number; tilt: number; face: string; shade: string;
  side: [string, string]; children: (fill: string, face: boolean) => React.ReactNode; id: string}> =
  ({w, h, depth, turn, tilt, face, shade, side, children, id}) => {
    const uid = `${id}-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;     // unique if two pieces share a frame (Fable)
    const N = 12;
    const layers = depth > 0 ? Array.from({length: N}, (_, i) => N - i) : [];
    return (
      <div style={{width: w, height: h, transform: `perspective(700px) rotateY(${turn}deg) rotateX(${tilt}deg)`}}>
        <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{overflow: 'visible'}}>
          <defs>
            <linearGradient id={`face-${uid}`} x1="0" y1="0" x2="1" y2="0.4">
              <stop offset="0" stopColor={face} />
              <stop offset="1" stopColor={depth > 0 ? shade : face} />
            </linearGradient>
          </defs>
          {layers.map((i) => (
            <g key={i} transform={`translate(${-0.95 * i * depth} ${0.45 * i * depth})`}>
              {children(i === N ? side[1] : mix(side[0], side[1], i / N), false)}
            </g>
          ))}
          {children(`url(#face-${uid})`, true)}
        </svg>
      </div>
    );
  };
const mix = (a: string, b: string, p: number) => {
  const v = (h: string, i: number) => parseInt(h.replace('#', '').slice(i, i + 2), 16);
  const c = [0, 2, 4].map((i) => Math.round(lerp(v(a, i), v(b, i), p)));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
};

// The bell's ring after its click: a swing about its knob, dying away over about 1.2 s.
const ring = (t: number, at: number, amp: number, hz = 3.2, decay = 0.42) =>
  t < at ? 0 : amp * Math.sin(2 * Math.PI * hz * (t - at)) * Math.exp(-(t - at) / decay);
const press = (t: number, at: number, depth = 0.1) => 1 - depth * Math.max(0, 1 - Math.abs(t - at) / 0.12);

// ---- 'classic' and 'brand': the original's layout and choreography ----
const Original: React.FC<{o: SubscribeLayer; P: Palette; brand: boolean}> = ({o, P, brand}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const {t0, t1, bell, thumb} = o;
  // entrance (from t0) and exit (to t1), the original's frames
  const barIn = easeOut(t, t0 + 0.133, 0.3), barOut = easeInOut(t, t1 - 0.6, 0.47);
  const bellIn = easeOut(t, t0 + 0.433, 0.37), thumbIn = easeOut(t, t0 + 0.7, 0.3);
  const textIn = easeOut(t, t0 + 1.2, 0.3), textOut = easeInOut(t, t1 - 1.12, 0.3);
  const thumbOut = easeInOut(t, t1 - 1.02, 0.3), bellOut = easeInOut(t, t1 - 0.92, 0.32);
  const bar = barIn * (1 - barOut);
  // the clicks: the icon turns 3D (depth and a turn), the bell rings; afterwards a slow sway
  const turnIn = (at: number) => easeOut(t, at, 0.3);
  const sway = (at: number) => (t > at ? 5 * Math.sin((2 * Math.PI * (t - at)) / 3.4) : 0);
  // the brand's icons show a thin copper edge from the start (cream on the sunlit floor read at 1.8:1 without it:
  // the visual review); the click deepens it and turns them
  const edge = brand ? 0.3 : 0;
  const bD = turnIn(bell), tD = turnIn(thumb);
  // the hand: up from below to the bell, over to the thumb, then away down (its fingertip's path)
  const bellTip = {x: BELL.x + 72, y: BELL.y + 84}, thumbTip = {x: THUMB.x + 96, y: THUMB.y + 92};
  const handIn = Math.max(t0 + 1.25, bell - 0.62);
  const up = easeOut(t, handIn, Math.max(0.2, bell - 0.14 - handIn));
  const over = easeInOut(t, thumb - 0.55, 0.43);
  const away = easeInOut(t, thumb + 0.22, 0.38);
  // (it fades in RISE px below the bell and out RISE px below the thumb, as the original: never below title-safe)
  const RISE = CTA.subscribe.handRisePx;
  const hx = lerp(lerp(bellTip.x + 12, bellTip.x, up), thumbTip.x, over) + 4 * away;
  const hy = lerp(lerp(bellTip.y + RISE, bellTip.y, up), thumbTip.y, over) + RISE * away;
  const handA = lin(t, handIn, 0.12) * (1 - lin(t, thumb + 0.4, 0.2));
  const handS = Math.min(press(t, bell, 0.14), press(t, thumb, 0.14));
  // the swoosh: a short trail behind the hand from the bell's side to the thumb and a flick past it (as the
  // original's red arc), its head moving with the hand, gone as it lands
  const TRAIL = 0.38;
  const swHead = (1 + TRAIL) * easeInOut(t, thumb - 0.52, 0.6), swA = 1 - lin(t, thumb - 0.02, 0.12);
  // the words hide behind the bar by their own width (any text, not only the original's; Fable)
  const font = brand ? SEGOE_BOLD : MONTSERRAT, size = brand ? 64 : TEXT_PX, spacing = brand ? 0 : -0.5;
  const textW = measureText({text: o.text, fontFamily: String(font.fontFamily), fontSize: size,
    fontWeight: String(font.fontWeight), letterSpacing: `${spacing}px`}).width;
  const hide = TEXT.x - (BAR.x + BAR.w) + textW + 12;
  const textX = -hide * ((1 - textIn) + textOut);
  const shadow = brand ? 'drop-shadow(0 2px 6px rgba(0, 0, 0, 0.35))' : undefined;
  // parked behind the bar, an icon sits PARK px right of its edge, so even its shadow is hidden (Fable: at 4 px the
  // brand's shadow showed beside the bar)
  const PARK = 24;
  return (
    <AbsoluteFill style={{transform: `translate(${o.dx ?? 0}px, ${o.dy ?? 0}px)`}}>
      {/* the icons, seen only left of the bar (they slide out from behind it, and back) */}
      <div style={{position: 'absolute', left: 0, top: 0, width: BAR.x, height: 1080, overflow: 'hidden'}}>
        <div style={{position: 'absolute', left: BELL.x, top: BELL.y, filter: shadow,
          transform: `translateX(${(1 - bellIn + bellOut) * (BAR.x - BELL.x + PARK)}px)`}}>
          <div style={{transformOrigin: '50% 8%', transform: `rotate(${ring(t, bell, 16)}deg) scale(${press(t, bell)})`}}>
            <Turned id="bell" w={BELL.w} h={BELL.h} depth={lerp(edge, 1, bD)} turn={-24 * bD + sway(bell + 0.3) * bD}
              tilt={6 * bD} face={P.face} shade={P.faceShade} side={P.side}>
              {(f, face) => <BellShape fill={f} detail={face ? P.detail : undefined} />}
            </Turned>
          </div>
        </div>
        <div style={{position: 'absolute', left: THUMB.x, top: THUMB.y, filter: shadow,
          transform: `translateX(${(1 - thumbIn + thumbOut) * (BAR.x - THUMB.x + PARK)}px)`}}>
          <div style={{transformOrigin: '30% 90%', transform: `scale(${press(t, thumb)})`}}>
            <Turned id="thumb" w={THUMB.w} h={THUMB.h} depth={lerp(edge, 1, tD)} turn={-26 * tD + sway(thumb + 0.3) * tD}
              tilt={6 * tD} face={P.face} shade={P.faceShade} side={P.side}>
              {(f, face) => <ThumbShape fill={f} gap={face ? P.detail : undefined} />}
            </Turned>
          </div>
        </div>
      </div>
      {/* the words, seen only right of the bar */}
      <div style={{position: 'absolute', left: BAR.x + BAR.w, top: TEXT.cy - 60, width: 1400, height: 120,
        overflow: 'hidden'}}>
        <div style={{position: 'absolute', left: TEXT.x - BAR.x - BAR.w, top: 0, height: 120, display: 'flex',
          alignItems: 'center', transform: `translateX(${textX}px)`}}>
          <div style={{...font, fontSize: size, letterSpacing: spacing, lineHeight: '120px', color: P.text,
            whiteSpace: 'nowrap',
            textShadow: P.textShadow}}>{o.text}</div>
        </div>
      </div>
      {/* the bar, growing from (and shrinking to) its middle */}
      <div style={{position: 'absolute', left: BAR.x, top: BAR.y, width: BAR.w, height: BAR.h, transformOrigin: '50% 50%',
        transform: `scaleY(${bar})`, opacity: bar > 0.01 ? 1 : 0,
        background: `linear-gradient(${P.barTop}, ${P.barBottom})`}} />
      {/* the swoosh and the hand */}
      {swHead > 0 && swA > 0 ? (
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, opacity: swA}}>
          <path d={`M${BELL.x + BELL.w + 4} ${bellTip.y - 6} Q${(BELL.x + BELL.w + thumbTip.x) / 2 + 6} ` +
            `${thumbTip.y + 40} ${THUMB.x + THUMB.w + 26} ${thumbTip.y - 10}`} fill="none" stroke={P.swoosh}
            strokeWidth={4} strokeLinecap="round" pathLength={1} strokeDasharray={`${TRAIL} 3`}
            strokeDashoffset={TRAIL - swHead} />
        </svg>
      ) : null}
      {handA > 0 ? (
        <div style={{position: 'absolute', left: hx - HAND_TIP.x * 1.15, top: hy - HAND_TIP.y * 1.15, opacity: handA,
          transformOrigin: `${HAND_TIP.x * 1.15}px ${HAND_TIP.y * 1.15}px`, transform: `scale(${handS})`}}>
          <svg width={70 * 1.15} height={86 * 1.15} viewBox="0 0 70 86" style={{overflow: 'visible'}}>
            <HandShape fill={P.hand} line={P.handLine} />
          </svg>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ---- 'pill': icons and words on one rounded pill, grown from its left end ----
const PILL = {x: 121, cy: 836, h: 128, icon: 84, text: 60};
const Pill: React.FC<{o: SubscribeLayer}> = ({o}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const {t0, t1, bell, thumb} = o;
  const grow = prog(t, t0 + 0.08, 0.5), shrink = prog(t, t1 - 0.75, 0.45);
  const fade = 1 - lin(t, t1 - 0.5, 0.3);              // gone as it closes, never a lone dark circle
  const bellIn = prog(t, t0 + 0.3, 0.3), thumbIn = prog(t, t0 + 0.4, 0.3), divIn = prog(t, t0 + 0.5, 0.25);
  const textIn = prog(t, t0 + 0.58, 0.45), textOut = prog(t, t1 - 1.05, 0.35);
  const iconsOut = prog(t, t1 - 0.9, 0.3);
  const W_FULL = 1010;
  const w = lerp(PILL.h, W_FULL, grow * (1 - shrink));
  const bellOn = prog(t, bell, 0.2), thumbOn = prog(t, thumb, 0.2);
  const rip = (at: number) => (t >= at && t < at + 0.6 ? lin(t, at, 0.6) : -1);
  const ICON_Y = (PILL.h - PILL.icon) / 2;
  const bellX = 38, thumbX = 38 + PILL.icon + 26, divX = thumbX + PILL.icon + 30, textX = divX + 8 + 30;
  // a small hand, as in the original, for the two clicks
  const tipB = {x: PILL.x + bellX + 44, y: PILL.cy + 22}, tipT = {x: PILL.x + thumbX + 50, y: PILL.cy + 26};
  const handIn = Math.max(t0 + 0.9, bell - 0.55);
  const up = prog(t, handIn, Math.max(0.2, bell - 0.12 - handIn)), over = prog(t, thumb - 0.5, 0.4);
  const away = prog(t, thumb + 0.22, 0.35);
  const RISE = CTA.subscribe.handRisePx;
  const hx = lerp(lerp(tipB.x + 10, tipB.x, up), tipT.x, over), hy = lerp(lerp(tipB.y + RISE, tipB.y, up), tipT.y, over)
    + RISE * away;
  const handA = lin(t, handIn, 0.12) * (1 - lin(t, thumb + 0.35, 0.2));
  const HS = 0.82;
  const ripple = (at: number, cx: number) => {
    const p = rip(at);
    return p < 0 ? null : (
      <div style={{position: 'absolute', left: cx - 46, top: PILL.h / 2 - 46, width: 92, height: 92, borderRadius: 46,
        border: `5px solid ${RED.on}`, opacity: 0.8 * (1 - p), transform: `scale(${0.7 + 0.7 * p})`}} />
    );
  };
  return (
    <AbsoluteFill style={{transform: `translate(${o.dx ?? 0}px, ${o.dy ?? 0}px)`, opacity: fade}}>
      <div style={{position: 'absolute', left: PILL.x, top: PILL.cy - PILL.h / 2, width: w, height: PILL.h,
        borderRadius: PILL.h / 2, background: '#1f1f1f', boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)',
        opacity: lin(t, t0 + 0.02, 0.12), overflow: 'hidden'}}>
        {ripple(bell, bellX + PILL.icon / 2)}
        {ripple(thumb, thumbX + PILL.icon / 2)}
        <div style={{position: 'absolute', left: bellX, top: ICON_Y, opacity: bellIn * (1 - iconsOut),
          transform: `scale(${(0.7 + 0.3 * bellIn) * press(t, bell)})`}}>
          <div style={{transformOrigin: '50% 8%', transform: `rotate(${ring(t, bell, 14)}deg)`}}>
            <svg width={PILL.icon} height={PILL.icon} viewBox="0 0 143 143">
              <BellShape fill={mix('#ffffff', RED.on, bellOn)} />
            </svg>
          </div>
        </div>
        <div style={{position: 'absolute', left: thumbX, top: ICON_Y + 4, opacity: thumbIn * (1 - iconsOut),
          transform: `scale(${(0.7 + 0.3 * thumbIn) * press(t, thumb)})`}}>
          <svg width={PILL.icon * 1.1} height={PILL.icon * 0.94} viewBox="0 0 159 136">
            <ThumbShape fill={mix('#ffffff', RED.on, thumbOn)} gap="#1f1f1f" />
          </svg>
        </div>
        <div style={{position: 'absolute', left: divX, top: (PILL.h - 72) / 2, width: 8, height: 72, borderRadius: 4,
          background: `linear-gradient(${RED.top}, ${RED.bottom})`, transform: `scaleY(${divIn * (1 - iconsOut)})`}} />
        <div style={{position: 'absolute', left: textX, top: 0, height: PILL.h, display: 'flex', alignItems: 'center',
          clipPath: `inset(-10% ${(1 - textIn * (1 - textOut)) * 100}% -10% 0)`}}>
          <div style={{...MONTSERRAT, fontSize: PILL.text, letterSpacing: -0.5, color: '#ffffff', whiteSpace: 'nowrap'}}>
            {o.text}
          </div>
        </div>
      </div>
      {handA > 0 ? (
        <div style={{position: 'absolute', left: hx - HAND_TIP.x * HS, top: hy - HAND_TIP.y * HS, opacity: handA,
          transformOrigin: `${HAND_TIP.x * HS}px ${HAND_TIP.y * HS}px`,
          transform: `scale(${Math.min(press(t, bell, 0.14), press(t, thumb, 0.14))})`}}>
          <svg width={70 * HS} height={86 * HS} viewBox="0 0 70 86" style={{overflow: 'visible'}}>
            <HandShape fill="#ffffff" line="#3a3a3a" />
          </svg>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ---- 'soft': the original's layout, calmer: each part drifts up into place out of a blur, no hand; a click is a
// soft pulse behind the icon and the icon filling red (the house's one calm curve, G19; no overshoot) ----
const Soft: React.FC<{o: SubscribeLayer}> = ({o}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const {t0, t1, bell, thumb} = o;
  const P = PALETTES.soft;
  const part = (inAt: number, outAt: number) => {
    const i = prog(t, t0 + inAt, 0.6), x = prog(t, t1 - outAt, 0.5);
    return {a: i * (1 - x), y: (1 - i) * 24 + x * 18, blur: (1 - i) * 8 + x * 8};
  };
  const bar = prog(t, t0 + 0.05, 0.55) * (1 - prog(t, t1 - 0.62, 0.5));
  const pb = part(0.15, 0.95), pt = part(0.27, 0.85), px = part(0.4, 1.05);
  const pulse = (at: number, cx: number, cy: number, r: number) => {
    if (t < at || t > at + 0.9) {
      return null;
    }
    const p = lin(t, at, 0.9);
    return (
      <div style={{position: 'absolute', left: cx - r, top: cy - r, width: 2 * r, height: 2 * r, borderRadius: r,
        background: 'radial-gradient(circle, rgba(255, 255, 255, 0.55) 0%, rgba(255, 255, 255, 0) 70%)',
        opacity: 1 - p, transform: `scale(${0.6 + 0.9 * prog(t, at, 0.9)})`}} />
    );
  };
  const bellOn = prog(t, bell, 0.3), thumbOn = prog(t, thumb, 0.3);
  const sway = t > bell ? 8 * Math.sin(2 * Math.PI * 1.6 * (t - bell)) * Math.exp(-(t - bell) / 0.6) : 0;
  const lift = (at: number) => (t < at ? 0 : -10 * Math.sin(Math.PI * lin(t, at, 0.5)));
  const fx = (q: {a: number; y: number; blur: number}): React.CSSProperties => ({opacity: q.a,
    transform: `translateY(${q.y}px)`, filter: `blur(${q.blur}px) drop-shadow(0 3px 10px rgba(0, 0, 0, 0.35))`});
  return (
    <AbsoluteFill style={{transform: `translate(${o.dx ?? 0}px, ${o.dy ?? 0}px)`}}>
      {pulse(bell, BELL.x + BELL.w / 2, BELL.y + BELL.h / 2, 110)}
      {pulse(thumb, THUMB.x + THUMB.w / 2, THUMB.y + THUMB.h / 2, 110)}
      <div style={{position: 'absolute', left: BELL.x, top: BELL.y, ...fx(pb)}}>
        <div style={{transformOrigin: '50% 8%', transform: `rotate(${sway}deg) scale(${press(t, bell, 0.06)})`}}>
          <svg width={BELL.w} height={BELL.h} viewBox="0 0 143 143"><BellShape fill={mix('#ffffff', P.on, bellOn)} /></svg>
        </div>
      </div>
      <div style={{position: 'absolute', left: THUMB.x, top: THUMB.y, ...fx(pt)}}>
        <div style={{transformOrigin: '30% 90%', transform: `translateY(${lift(thumb)}px) scale(${press(t, thumb, 0.06)})`}}>
          <svg width={THUMB.w} height={THUMB.h} viewBox="0 0 159 136">
            <ThumbShape fill={mix('#ffffff', P.on, thumbOn)} />
          </svg>
        </div>
      </div>
      <div style={{position: 'absolute', left: BAR.x + 2, top: BAR.y, width: 8, height: BAR.h, borderRadius: 4,
        transformOrigin: '50% 100%', transform: `scaleY(${bar})`, background: `linear-gradient(${P.barTop}, ${P.barBottom})`,
        boxShadow: '0 2px 10px rgba(0, 0, 0, 0.3)'}} />
      <div style={{position: 'absolute', left: TEXT.x, top: TEXT.cy - 60, height: 120, display: 'flex', alignItems: 'center',
        ...fx(px)}}>
        <div style={{...FONT.heading, fontSize: 64, color: P.text, whiteSpace: 'nowrap',
          letterSpacing: lerp(4, 0, prog(t, t0 + 0.4, 0.7))}}>{o.text}</div>
      </div>
    </AbsoluteFill>
  );
};

export const SubscribeAnim: React.FC<{o: SubscribeLayer}> = ({o}) => {
  if (o.variant === 'pill') {
    return <Pill o={o} />;
  }
  if (o.variant === 'soft') {
    return <Soft o={o} />;
  }
  return <Original o={o} P={PALETTES[o.variant]} brand={o.variant === 'brand'} />;
};

// The four compositions (Root.tsx): the same props, each variation fixed by its composition's default.
const SAMPLE_TIMES = {t0: 0.2, bell: 0.2 + ORIGINAL.bellS, thumb: 0.2 + ORIGINAL.thumbS, t1: 0.2 + ORIGINAL.lengthS};
export const subscribeSample = (variant: SubscribeVariant): SubscribeProps => ({durationInFrames: 236, fps: 30,
  width: 1920, height: 1080, layer: {variant, text: 'Thanks for Watching!', ...SAMPLE_TIMES}});
export const SubscribePreview: React.FC<SubscribeProps> = ({still, layer}) => (
  <AbsoluteFill>
    {still ? <Img src={staticFile(still)} /> : null}
    <SubscribeAnim o={layer} />
  </AbsoluteFill>
);
