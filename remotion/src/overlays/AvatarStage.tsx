import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ChapterCard} from './ChapterCard';
import {SeriesCard, SeriesCardLayer} from './SeriesCard';
import {SubscribeAnim, SubscribeLayer} from './SubscribeCta';
import {ACCENT, Box, FONT, lh, look, MOTION, prog, rgba, SIZE, Variant} from './kit';
import {TABLER, TablerName} from './vendor/tabler/icons';

// AvatarStage (R205 to R209): the avatar's intro or outro as one transparent clip (ProRes 4444 with alpha) for the
// final sequence, built by pipeline/edit/stage.py. The avatar is HeyGen's transparent render (pipeline.edit.avatar
// main_alpha), placed full frame or shrunk to the left third (R208: it may move while it speaks), over a checkerboard
// until a real background is chosen (R206). Its graphics sit on the right two thirds, above the captions' band:
//   * the roadmap card (intro): each part and step lands on its spoken word (R80, T6), a to-do list of empty boxes;
//     at "So, let's get started." it grows to the full frame and becomes the "Part 1" ChapterCard, drawn exactly as
//     the approved sequence's own card, which takes over beneath it once both are settled;
//   * the recap card (outro): the same card, all its rows up, each ticking on the word that recaps it;
//   * the subscribe card (R209), in two looks, and David's url.mov write-on (the call to action);
//   * R242, R243: the "Amazon Quick Series" card (SeriesCard.tsx, `series`) in the intro's first seconds, and the
//     call to action's subscribe animation (SubscribeCta.tsx, `subscribeAnim`, the brand variation) in the outro,
//     each drawn after the avatar on the stage's own clock (their layers' times are seconds on this clip).
// All times are seconds on the stage clip (frame / fps). Only ChapterCard and url.mov sit in a Sequence: the card
// reads its time from its own start (kit.useEditTime), and the video plays from its own first frame.

// The box design (round 5, R220, R222, R224, R225): the avatar's whole frame, its own background behind it, shrinks
// linearly (as David's ep04) into the picture-in-picture oval and grows back. Full frame the background is `full` (B1,
// the neon sign wall); in the oval it is `inside` (the Brand Stage teal), the two cross-fading as it shrinks. The oval:
// the frame at `scale` through a w x h ellipse with a `featherPx` soft edge, no ring, centred on the person (personX
// in the render's frame) and placed with its centre at (cx, cy) on the stage. Its moves are 'full' <-> 'box'.
export type AvatarBox = {cx: number; cy: number; personX: number; scale: number; w: number; h: number;
  featherPx: number; full: string; inside: string; fullShiftX?: number};
// The Quick Series design (round 6, R231, R232): the transparent avatar over a still room (the cityscape, the stage's
// backdrop), in three poses: 'full' as HeyGen renders it; 'left', scaled by leftScale about the frame's bottom centre
// and moved leftX, beside the card; 'box', the whole frame (room and avatar) at box.scale through the oval centred on
// the person. Every move is linear (as David's ep04). A move to or from 'box' carries the room with the avatar inside
// a window that closes from the pose's own area (the whole frame, or the left region up to leftW) to the oval and
// rounds off (a hard edge while it moves; the feathered oval once settled), so the room shrinks with him; a move
// between 'full' and 'left' moves the avatar alone over the still room.
export type AvatarQuick = {room: string; leftScale: number; leftX: number; leftW: number; box: AvatarBox};
export type AvatarPlace = 'full' | 'left' | 'box';
// wide: a move out of the oval whose window opens to the whole frame (the outro's growth over the main body, as
// David's ep03 mask grows to full frame), not just the pose's own area; the backdrop takes over as it lands.
export type AvatarMove = {at: number; dur: number; to: AvatarPlace; wide?: boolean};
export type AvatarExit = {style: 'slide' | 'corner' | 'dissolve'; at: number; dur: number};
export type RoadRow = {text: string; at: number; level: 0 | 1; tick?: number};
export type StageCard = {t0: number; t1: number; outS: number; box: Box; rows: RoadRow[]; variant: Variant;
  expand?: {at: number; dur: number}};
export type StageChapter = {t0: number; until: number; kicker: string; title: string; variant: Variant};
export type StageSubscribe = {t0: number; t1: number; look: 'red' | 'brand'; bell: number; thumb: number; box: Box};
export type StageUrl = {src: string; t0: number; t1: number; fadeOutS: number; box: Box; srcBox: Box;
  srcW: number; srcH: number; panel: boolean; brightness?: number};
export type StageProps = {durationInFrames: number; fps: number; width: number; height: number;
  avatar: {src: string; trimBeforeS: number; start: AvatarPlace; moves: AvatarMove[]; exit?: AvatarExit;
    box?: AvatarBox; quick?: AvatarQuick};
  backdrop?: {src: string; until: number; from?: number};   // a full-frame picture behind everything, from..until
  checkerUntil?: number;           // the checkerboard shows until this time; the stage is transparent after
  fadeInS?: number;                // the whole stage fades in over this (the outro's dissolve, baked in)
  fadeInAt?: number;               // from this time (0 by default); nothing of the stage shows before it
  card?: StageCard; chapter?: StageChapter; subscribe?: StageSubscribe; url?: StageUrl;
  series?: SeriesCardLayer;        // R242, R243: the series card, over the avatar
  subscribeAnim?: SubscribeLayer;  // R242, R243: the Remotion subscribe animation (replaces R232's original)
};

// Where the avatar sits: full frame as HeyGen renders it, or shrunk about its bottom centre into the left third,
// its head clear of a centred chapter title and its shoulders clear of the right two thirds.
const PLACES: Record<'full' | 'left', {x: number; scale: number}> = {full: {x: 0, scale: 1}, left: {x: -660, scale: 0.62}};
const CHECK_PX = 32;               // the checkerboard's squares, as pipeline.edit.alpha draws them (204 and 153 grey)
const SLIDE_IN_PX = 140;           // the cards slide in from the right this far

const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

const Checker: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: 'rgb(204, 204, 204)',
    backgroundImage: 'conic-gradient(rgb(153, 153, 153) 25%, transparent 0 50%, rgb(153, 153, 153) 0 75%, transparent 0)',
    backgroundSize: `${CHECK_PX * 2}px ${CHECK_PX * 2}px`}} />
);

const Icon: React.FC<{name: TablerName; size: number; color: string; fill?: string; stroke?: number;
  style?: React.CSSProperties}> = ({name, size, color, fill, stroke = 2, style}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{overflow: 'visible', ...style}}>
    {TABLER[name].map((d, i) => (
      <path key={i} d={d} fill={i === 0 && fill ? fill : 'none'} stroke={color} strokeWidth={stroke}
        strokeLinecap="round" strokeLinejoin="round" />
    ))}
  </svg>
);

// Linear progress, for the box's shrink and growth (David's ep04: a linear 0.6 s shrink; K6's camera moves too).
const lin = (t: number, start: number, dur: number) =>
  dur <= 0 ? (t >= start ? 1 : 0) : Math.min(1, Math.max(0, (t - start) / dur));

// The box design's avatar: p is 0 full frame, 1 in the oval. The content (the frame: background and avatar) scales by
// k about the person's centre, which travels from where it is to the oval's centre. While it moves, the frame's own
// rectangle closes in on the oval's box and its corners round off until it is the ellipse (a clip in content px, so it
// never runs past the frame's edge: an ellipse larger than the frame had cut it flat, the visual review of round 5);
// settled, the oval is a w x h ellipse on screen with a featherPx soft edge. fullShiftX moves the avatar alone (not
// its background, which must stay registered with the stage's own B1) sideways at full frame, to make room.
const BoxAvatar: React.FC<{a: StageProps['avatar']; t: number}> = ({a, t}) => {
  const {fps, width: W, height: H} = useVideoConfig();
  const b = a.box as AvatarBox;
  let p = a.start === 'box' ? 1 : 0;
  for (const m of a.moves) {
    p = lerp(p, m.to === 'box' ? 1 : 0, lin(t, m.at, m.dur));
  }
  const k = lerp(1, b.scale, p);
  const ax = b.personX, ay = H / 2;                        // the content's anchor: the person's centre
  const sx = lerp(ax, b.cx, p), sy = lerp(ay, b.cy, p);    // where it lands on the stage
  const rx = b.w / 2 / b.scale, ry = b.h / 2 / b.scale;    // the oval in content px
  let clip: React.CSSProperties = {};
  if (p >= 1) {
    const feather = b.featherPx / k;                       // content px, so the edge is featherPx on screen
    // the gradient's stops are fractions of each axis's radius: the band is about featherPx along both
    const stop = Math.max(0, 100 * (1 - feather / Math.sqrt(rx * ry)));
    const mask = `radial-gradient(ellipse ${rx}px ${ry}px at ${ax}px ${ay}px, #000 ${stop}%, transparent 100%)`;
    clip = {maskImage: mask, WebkitMaskImage: mask};
  } else if (p > 0) {
    const inset = `inset(${lerp(0, ay - ry, p)}px ${lerp(0, W - ax - rx, p)}px ${lerp(0, H - ay - ry, p)}px ` +
      `${lerp(0, ax - rx, p)}px round ${lerp(0, rx, p)}px / ${lerp(0, ry, p)}px)`;
    clip = {clipPath: inset, WebkitClipPath: inset};
  }
  // B1 inside gives way to the teal over the first 40% of a shrink (and comes back over the last 40% of a growth),
  // so the shrinking frame's own small copy of the sign is gone early rather than ghosting the move (at 1 - 2p a
  // faint second sign still showed mid-shrink: the visual review's re-check, round 5).
  const fullBg = Math.min(1, Math.max(0, 1 - 2.5 * p));
  const shift = (b.fullShiftX ?? 0) * (1 - p);
  let opacity = 1;
  if (a.exit) {
    opacity = 1 - lin(t, a.exit.at, a.exit.dur);           // exit C, the dissolve (R215): the only exit of the box
  }
  return (
    <AbsoluteFill style={{opacity}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: W, height: H, transformOrigin: '0 0',
        transform: `translate(${sx - ax * k}px, ${sy - ay * k}px) scale(${k})`, ...clip}}>
        <Img src={staticFile(b.inside)} style={{position: 'absolute', width: W, height: H}} />
        <Img src={staticFile(b.full)} style={{position: 'absolute', width: W, height: H, opacity: fullBg}} />
        <AbsoluteFill style={{transform: `translateX(${shift}px)`}}>
          <OffthreadVideo src={staticFile(a.src)} transparent muted trimBefore={Math.round(a.trimBeforeS * fps)} />
        </AbsoluteFill>
      </div>
    </AbsoluteFill>
  );
};

// A pose's maps from the render's frame to the stage (k, tx, ty: x' = k x + tx), for the avatar and the room, and its
// window (x0, y0, x1, y1 and the corners' radii).
type Affine = [number, number, number];
type Pose = {avatar: Affine; room: Affine; win: [number, number, number, number, number, number]};
const quickPose = (q: AvatarQuick, place: AvatarPlace, W: number, H: number): Pose => {
  if (place === 'box') {
    const b = q.box, k = b.scale;
    const m: Affine = [k, b.cx - b.personX * k, b.cy - (H / 2) * k];
    return {avatar: m, room: m, win: [b.cx - b.w / 2, b.cy - b.h / 2, b.cx + b.w / 2, b.cy + b.h / 2, b.w / 2, b.h / 2]};
  }
  const one: Affine = [1, 0, 0];
  if (place === 'left') {
    const s = q.leftScale;
    return {avatar: [s, (W / 2) * (1 - s) + q.leftX, H * (1 - s)], room: one, win: [0, 0, q.leftW, H, 0, 0]};
  }
  return {avatar: one, room: one, win: [0, 0, W, H, 0, 0]};
};
const mixPose = (a: Pose, b: Pose, p: number): Pose => ({
  avatar: a.avatar.map((v, i) => lerp(v, b.avatar[i], p)) as Affine,
  room: a.room.map((v, i) => lerp(v, b.room[i], p)) as Affine,
  win: a.win.map((v, i) => lerp(v, b.win[i], p)) as Pose['win'],
});
const affine = (m: Affine): React.CSSProperties => ({position: 'absolute', left: 0, top: 0, transformOrigin: '0 0',
  transform: `translate(${m[1]}px, ${m[2]}px) scale(${m[0]})`});

// Where the moves have the avatar at t: the settled place before the next move, or a move under way (from, to, p).
export const quickState = (a: StageProps['avatar'], t: number) => {
  let from: AvatarPlace = a.start;
  for (const m of [...a.moves].sort((x, y) => x.at - y.at)) {
    if (t < m.at) {
      break;
    }
    const p = lin(t, m.at, m.dur);
    if (p < 1) {
      return {from, to: m.to, p, wide: !!m.wide};
    }
    from = m.to;
  }
  return {from, to: from, p: 1, wide: false};
};

const QuickAvatar: React.FC<{a: StageProps['avatar']; t: number}> = ({a, t}) => {
  const {fps, width: W, height: H} = useVideoConfig();
  const q = a.quick as AvatarQuick;
  const s = quickState(a, t);
  const end = quickPose(q, s.to, W, H);
  if (s.wide) {                                              // the window opens to the whole frame
    end.win = [0, 0, W, H, 0, 0];
  }
  const pose = mixPose(quickPose(q, s.from, W, H), end, s.p);
  const boxed = s.from === 'box' || s.to === 'box';          // the room travels with him only to or from the oval
  const settled = s.from === 'box' && s.to === 'box';
  let clip: React.CSSProperties = {};
  const b = q.box;
  // the oval's soft edge (no ring): opaque to featherPx inside the ellipse, then to nothing at it
  const soft = (cx: number, cy: number, rx: number, ry: number): React.CSSProperties => {
    const stop = Math.max(0, 100 * (1 - b.featherPx / Math.sqrt(rx * ry)));
    const mask = `radial-gradient(ellipse ${rx}px ${ry}px at ${cx}px ${cy}px, #000 ${stop}%, transparent 100%)`;
    return {maskImage: mask, WebkitMaskImage: mask};
  };
  if (settled) {
    clip = soft(b.cx, b.cy, b.w / 2, b.h / 2);
  } else if (boxed) {
    // The window closing in on the oval (or opening out of it), soft-edged all the way: a rounded rectangle blurred
    // over featherPx (at the oval it is the oval, its edge's midpoint where the settled oval's is), an SVG mask. An
    // edge on the frame's is pushed past it, so the frame itself never has a soft border. The room copy inside scales
    // with the window, so it always fills it (an ellipse grown past the room's copy showed its edge, round 6).
    // pushed out by d at the frame's edge, by less as it moves in, not at all 2 x featherPx in (continuous, so the
    // edge never jumps; no soft rim on the frame's edge in a move's last frames: Fable, round 6)
    const f = b.featherPx, out = (v: number, edge: number, d: number) =>
      v + d * Math.max(0, 1 - Math.abs(v - edge) / (2 * f));
    let [x0, y0, x1, y1, rx, ry] = pose.win;
    x0 = out(x0, 0, -2 * f);
    y0 = out(y0, 0, -2 * f);
    x1 = out(x1, W, 2 * f);
    y1 = out(y1, H, 2 * f);
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${W}' height='${H}'><defs><filter id='s' x='-5%' ` +
      `y='-5%' width='110%' height='110%'><feGaussianBlur stdDeviation='${f / 2}'/></filter></defs><rect ` +
      `x='${x0 + f / 2}' y='${y0 + f / 2}' width='${Math.max(0, x1 - x0 - f)}' height='${Math.max(0, y1 - y0 - f)}' ` +
      `rx='${Math.max(0, rx - f / 2)}' ry='${Math.max(0, ry - f / 2)}' fill='black' filter='url(#s)'/></svg>`;
    const mask = `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}")`;
    clip = {maskImage: mask, WebkitMaskImage: mask, maskSize: `${W}px ${H}px`, WebkitMaskSize: `${W}px ${H}px`,
      maskRepeat: 'no-repeat', WebkitMaskRepeat: 'no-repeat'};
  }
  // an exit fades the whole pose out (R237: an intro render that carries the box's first stay fades out with the box's
  // own FADE_S at the stay's end, the first main-body render fading in elsewhere)
  const opacity = a.exit ? 1 - lin(t, a.exit.at, a.exit.dur) : 1;
  return (
    <AbsoluteFill style={{...clip, opacity}}>
      {boxed ? <Img src={staticFile(q.room)} style={{...affine(pose.room), width: W, height: H}} /> : null}
      <div style={{...affine(pose.avatar), width: W, height: H}}>
        <OffthreadVideo src={staticFile(a.src)} transparent muted trimBefore={Math.round(a.trimBeforeS * fps)} />
      </div>
    </AbsoluteFill>
  );
};

const Avatar: React.FC<{a: StageProps['avatar']; t: number}> = ({a, t}) => {
  const {fps} = useVideoConfig();
  if (a.quick) {
    return <QuickAvatar a={a} t={t} />;
  }
  if (a.box) {
    return <BoxAvatar a={a} t={t} />;
  }
  let st = PLACES[a.start === 'box' ? 'full' : a.start];
  for (const m of a.moves) {
    const p = prog(t, m.at, m.dur);
    const to = PLACES[m.to === 'box' ? 'full' : m.to];
    st = {x: lerp(st.x, to.x, p), scale: lerp(st.scale, to.scale, p)};
  }
  let {x, scale} = st;
  let opacity = 1;
  if (a.exit) {
    const p = prog(t, a.exit.at, a.exit.dur);
    if (a.exit.style === 'slide') {
      x -= 820 * p;                                        // off the left edge, the way the card's text reads
    } else if (a.exit.style === 'corner') {
      x = lerp(x, -820, p);                                // into the bottom-left corner, shrinking, then gone
      scale = lerp(scale, 0.18, p);
      opacity = 1 - prog(t, a.exit.at + a.exit.dur * 0.6, a.exit.dur * 0.4);
    } else {
      opacity = 1 - p;
    }
  }
  return (
    <AbsoluteFill style={{transform: `translateX(${x}px) scale(${scale})`, transformOrigin: '50% 100%', opacity}}>
      <OffthreadVideo src={staticFile(a.src)} transparent muted trimBefore={Math.round(a.trimBeforeS * fps)} />
    </AbsoluteFill>
  );
};

// The roadmap (intro) and recap (outro) card: part headings with their number, steps under them with a box each. A
// row's text rises in on its word; a tick draws in its box on its own word (recap). The panel opens at its full size
// (G17), opaque (G7), and slides in from the right.
const ROW_H = {0: 88, 1: 70};
const BOX = 50;
const CHIP = 72;                // the part's number: gold with its dark digit (8.1:1, G6); a tick rings it in the accent
const CHIP_DIGIT = 52;          // at least G3's 48 px
const RING = 6;
const RoadCard: React.FC<{c: StageCard; t: number}> = ({c, t}) => {
  const {width, height} = useVideoConfig();
  const L = look(c.variant);
  const inP = prog(t, c.t0, MOTION.baseS);
  const out = 1 - prog(t, c.t1 - c.outS, c.outS);
  const ex = c.expand ? prog(t, c.expand.at, c.expand.dur) : 0;
  const content = 1 - Math.min(1, ex * 2.5);               // the rows fade out as the panel starts to grow
  const b = {x: lerp(c.box.x, 0, ex), y: lerp(c.box.y, 0, ex), w: lerp(c.box.w, width, ex), h: lerp(c.box.h, height, ex)};
  let part = 0;
  return (
    <div style={{position: 'absolute', left: b.x, top: b.y, width: b.w, height: b.h, opacity: inP * out,
      transform: `translateX(${(1 - inP) * SLIDE_IN_PX}px)`, background: L.panel,
      border: ex < 1 ? `2px solid ${rgba(L.rule, 1 - ex)}` : 'none', borderRadius: lerp(14, 0, ex),
      boxShadow: ex < 1 ? '0 10px 30px rgba(0, 0, 0, 0.35)' : 'none', boxSizing: 'border-box', overflow: 'hidden'}}>
      <div style={{padding: '34px 48px', opacity: content}}>
        {c.rows.map((r, i) => {
          const p = prog(t, r.at, 0.4);
          const tick = r.tick !== undefined ? prog(t, r.tick, 0.4) : 0;
          if (r.level === 0) {
            part += 1;
            return (
              <div key={i} style={{display: 'flex', alignItems: 'center', gap: 22, height: ROW_H[0], opacity: p,
                transform: `translateY(${(1 - p) * MOTION.risePx}px)`, marginTop: i ? 10 : 0}}>
                <div style={{...FONT.heading, width: CHIP, height: CHIP, borderRadius: CHIP / 2, flex: 'none',
                  background: L.chip, color: L.chipText, fontSize: CHIP_DIGIT, lineHeight: `${CHIP}px`,
                  textAlign: 'center', boxShadow: tick > 0 ? `0 0 0 ${RING * tick}px ${ACCENT}` : 'none'}}>{part}</div>
                <div style={{...FONT.heading, fontSize: SIZE.heading, lineHeight: lh(SIZE.heading), color: L.heading,
                  whiteSpace: 'nowrap'}}>{r.text}</div>
              </div>
            );
          }
          return (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 22, height: ROW_H[1], paddingLeft: 86,
              opacity: p, transform: `translateX(${(1 - p) * -14}px)`}}>
              <svg width={BOX} height={BOX} viewBox="0 0 24 24" style={{flex: 'none', overflow: 'visible'}}>
                <rect x={3} y={3} width={18} height={18} rx={3.5} fill={rgba(L.well, 0.9)}
                  stroke={tick > 0 ? L.rule : L.muted} strokeWidth={2} />
                {tick > 0 && (
                  <path d="M6.5 12.5l3.8 3.8l7.7 -8.3" fill="none" stroke={ACCENT} strokeWidth={3}
                    strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1}
                    strokeDashoffset={1 - tick} />
                )}
              </svg>
              <div style={{...FONT.body, fontSize: SIZE.body, lineHeight: lh(SIZE.body), color: L.body,
                whiteSpace: 'nowrap'}}>{r.text}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// The subscribe card (R209), rebuilt from David's Motion Array card: a vertical bar, the bell and the thumbs-up, and
// "Thanks for watching!" sliding out from behind the bar; a hand clicks the bell on "subscribe" and the thumb on
// "thumbs". On an opaque panel (G7), so its text keeps 7:1 over any background. 'red': the old card's YouTube red
// bar on YouTube's dark grey; 'brand': the brand brown with the gold, the bar in the one accent (a shape, G9).
const SUB_TEXT = 64;            // a heading (G3: 60 at least); the card keeps inside title-safe (G15)
const SUB_LOOKS = {
  red: {panel: '#212121', text: '#FFFFFF', icon: '#FFFFFF', bar: '#FF0000', on: '#FF0000'},
  brand: {panel: '#432613', text: '#e4c493', icon: '#f8f6f3', bar: ACCENT, on: ACCENT},
};
const SubscribeCard: React.FC<{s: StageSubscribe; t: number}> = ({s, t}) => {
  const K = SUB_LOOKS[s.look];
  const inP = prog(t, s.t0, 0.45);
  const bar = prog(t, s.t0, 0.3);
  const icons = [prog(t, s.t0 + 0.2, 0.35), prog(t, s.t0 + 0.28, 0.35)];
  const text = prog(t, s.t0 + 0.35, 0.5);
  const out = 1 - prog(t, s.t1 - 0.5, 0.5);
  const bellOn = t >= s.bell, thumbOn = t >= s.thumb;
  const ring = t >= s.bell ? Math.sin((t - s.bell) * 26) * 14 * Math.max(0, 1 - (t - s.bell) / 0.9) : 0;
  const press = (at: number) => 1 - 0.1 * Math.max(0, 1 - Math.abs(t - at) / 0.12);
  // the hand: in from below right, to the bell for its click, then to the thumb for its own
  const ICON = 112, GAP = 30;
  const bellC = {x: 40 + ICON / 2, y: 36 + ICON / 2}, thumbC = {x: 40 + ICON + GAP + ICON / 2, y: 36 + ICON / 2};
  const handIn = Math.max(s.t0 + 0.3, s.bell - 0.6);         // never before the card is in
  const toBell = prog(t, handIn + 0.05, Math.max(0.2, s.bell - handIn - 0.1)), toThumb = prog(t, s.thumb - 0.55, 0.45);
  const hx = lerp(lerp(bellC.x + 260, bellC.x, toBell), thumbC.x, toThumb) + 18;
  const hy = lerp(lerp(bellC.y + 220, bellC.y, toBell), thumbC.y, toThumb) + 24;
  const hand = prog(t, handIn, 0.25) * (1 - prog(t, s.thumb + 0.5, 0.3));
  return (
    <div style={{position: 'absolute', left: s.box.x, top: s.box.y, width: s.box.w, height: s.box.h, display: 'flex',
      alignItems: 'center', justifyContent: 'center', opacity: out}}>
      <div style={{position: 'relative', display: 'flex', alignItems: 'center', gap: GAP, padding: '36px 48px 36px 40px',
        background: K.panel, borderRadius: 14, boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)', opacity: inP,
        transform: `translateX(${(1 - inP) * SLIDE_IN_PX}px)`}}>
        <div style={{opacity: icons[0], transform: `scale(${press(s.bell)}) rotate(${ring}deg)`, transformOrigin: '50% 10%'}}>
          <Icon name={bellOn ? 'bell-ringing' : 'bell'} size={ICON} color={bellOn ? K.on : K.icon}
            fill={bellOn ? K.on : undefined} />
        </div>
        <div style={{opacity: icons[1], transform: `scale(${press(s.thumb)})`}}>
          <Icon name="thumb-up" size={ICON} color={thumbOn ? K.on : K.icon} fill={thumbOn ? K.on : undefined} />
        </div>
        <div style={{width: 10, height: 150, background: K.bar, borderRadius: 2, transform: `scaleY(${bar})`}} />
        <div style={{overflow: 'hidden', padding: '6px 0 16px', margin: '-6px 0 -16px'}}>
          <div style={{...FONT.heading, fontSize: SUB_TEXT, lineHeight: lh(SUB_TEXT), color: K.text, whiteSpace: 'nowrap',
            transform: `translateX(${(1 - text) * -110}%)`}}>Thanks for watching!</div>
        </div>
        {hand > 0 && (
          <div style={{position: 'absolute', left: hx, top: hy, opacity: hand}}>
            <Icon name="hand-click" size={88} color={K.icon} fill={K.panel} stroke={1.8} />
          </div>
        )}
      </div>
    </div>
  );
};

// David's url.mov (a 4K handwritten giddyupdata.com write-on, 25 fps) scaled so its writing (srcBox, in its own
// pixels) fills box; on a cream panel when `panel`, so its copper strokes contrast with what is behind (G7).
const UrlWriteOn: React.FC<{u: StageUrl; t: number}> = ({u, t}) => {
  const {fps} = useVideoConfig();
  const k = Math.min(u.box.w / u.srcBox.w, u.box.h / u.srcBox.h);
  const inP = prog(t, u.t0, 0.3);
  const out = 1 - prog(t, u.t1 - 1 / fps - u.fadeOutS, u.fadeOutS);      // gone by the clip's last frame
  const left = u.box.x + (u.box.w - u.srcBox.w * k) / 2 - u.srcBox.x * k;
  const top = u.box.y + (u.box.h - u.srcBox.h * k) / 2 - u.srcBox.y * k;
  return (
    <AbsoluteFill style={{opacity: out}}>
      {u.panel && (
        <div style={{position: 'absolute', left: u.box.x - 40, top: u.box.y - 30, width: u.box.w + 80,
          height: u.box.h + 60, background: '#f8f6f3', borderRadius: 14, opacity: inP,
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)'}} />
      )}
      <Sequence from={Math.round(u.t0 * fps)} layout="none">
        <div style={{position: 'absolute', left, top, width: u.srcW * k, height: u.srcH * k}}>
          <OffthreadVideo src={staticFile(u.src)} transparent muted style={{width: '100%', height: '100%',
            filter: u.brightness !== undefined ? `brightness(${u.brightness})` : undefined}} />
        </div>
      </Sequence>
    </AbsoluteFill>
  );
};

export const AvatarStage: React.FC<StageProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const fade = p.fadeInS ? prog(t, p.fadeInAt ?? 0, p.fadeInS) : 1;
  const ch = p.chapter;
  return (
    <AbsoluteFill style={{opacity: fade}}>
      {p.checkerUntil !== undefined && t < p.checkerUntil ? <Checker /> : null}
      {p.backdrop && t < p.backdrop.until && t >= (p.backdrop.from ?? 0) ? (
        <Img src={staticFile(p.backdrop.src)} style={{position: 'absolute', width: p.width, height: p.height}} />
      ) : null}
      {p.card && t < (ch ? ch.until : p.card.t1) ? <RoadCard c={p.card} t={t} /> : null}
      {ch && t < ch.until ? (
        <Sequence from={Math.round(ch.t0 * fps)} layout="none">
          <AbsoluteFill>
            <ChapterCard o={{id: 'stage-chapter', layout: 'chapter_card', t0: ch.t0, t1: ch.until + 60,
              variant: ch.variant, title: ch.title, kicker: ch.kicker}} />
          </AbsoluteFill>
        </Sequence>
      ) : null}
      <Avatar a={p.avatar} t={t} />
      {p.series ? <SeriesCard o={p.series} /> : null}
      {p.subscribeAnim ? <SubscribeAnim o={p.subscribeAnim} /> : null}
      {p.subscribe ? <SubscribeCard s={p.subscribe} t={t} /> : null}
      {p.url && t >= p.url.t0 ? <UrlWriteOn u={p.url} t={t} /> : null}
    </AbsoluteFill>
  );
};

export const STAGE_SAMPLE: StageProps = {durationInFrames: 60, fps: 30, width: 1920, height: 1080,
  avatar: {src: 'avatar.mov', trimBeforeS: 0, start: 'full', moves: []}, checkerUntil: 2};
