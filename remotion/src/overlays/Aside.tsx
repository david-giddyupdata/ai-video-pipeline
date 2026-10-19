import React from 'react';
import {Img, OffthreadVideo, Sequence, staticFile, useVideoConfig} from 'remotion';
import {Box, Edge, exitLeft, FONT, LAYOUT, look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog, rgba, SIZE,
  useEditTime, Variant, lh} from './kit';
import {PieceItem} from './pieces';
import artTable from './data/aside_art.json';

// Aside (the overlay plan's composition 5; David's drop-in asides of ep03: the brain in an oval vignette at 2:23, the
// piggy bank popping over its disc at 6:14): an attention grabber (R138) that drops in on its noun. Two kinds:
//   art    a PNG with alpha in the public dir (o.art.main). An oval plate in the panel's colour (R140: dark on a light
//          screen) grows on the word, and the art pops over it with the asides' pop (MOTION.pop: 0.76 s to a peak
//          of 1.1 and back, the one place R131 allows overshoot; done with prog, not spring), holds, and leaves with
//          a fade and a small shrink (0.5 s). The art is drawn at its content's size: data/aside_art.json holds each
//          file's opaque box (or o.art.content / o.art.size give it), so wide transparent margins don't shrink it.
//   video  an .mp4 in the public dir (o.video.main), shown inside a soft oval vignette or a rounded panel, so nothing
//          needs keying (R150's Abacus clips: first frame on the panel's colour). It starts on the word, muted, and
//          the whole frame pops. Untested: no clip exists yet.
// o.frame picks the frame: 'oval' (the default), 'panel' (the house rounded panel) or 'none' (the art alone, with the
// panel's shadow). An optional label (FONT.heading) sits in a chip tucked under the plate, on label_at (by default as
// the pop settles). Height: o.height in frame px, kept to 25 to 40% of the frame (34% by default), and inside o.box
// when one is given. Placement: a box in frame px or an edge of title-safe (right by default).

export type AsideFrame = 'oval' | 'panel' | 'none';
export type AsideArt = {main: string; content?: Box; size?: {w: number; h: number}};
export type AsideVideo = {main: string; from?: number; aspect?: number};
export type AsideLayer = {id: string; step?: string; layout: 'aside'; t0: number; t1: number; variant: Variant;
  items: PieceItem[]; art?: AsideArt; video?: AsideVideo; frame?: AsideFrame; label?: string; label_at?: number;
  height?: number; box?: Box; edge?: Edge};

const KNOWN = artTable.art as Record<string, {w: number; h: number; content: Box}>;
const OVAL = {w: 1.18, h: 1.3};    // the oval plate around the art's content box
const PANEL_PAD = 0.12;            // the rounded panel's padding, a share of the art's height
const FROM = 0.3;                  // the pop starts at 30% of the size
const LABEL_H = 84;                // the label chip (60 px heading type, R161)
const LABEL_TUCK = 22;             // how far the chip tucks under the plate's lower edge
const OUT_SCALE = 0.92;            // the shrink as it fades out (the piggy bank's shrink)
const DEFAULT_H = 0.34;            // of the frame's height
const MAX_W = 0.4;                 // of title-safe's width, when no box is given

// The asides' pop: up to the peak, then a settle back to 1, each leg on the house curve, so the motion is continuous
// and lands still. `seen` is its opacity, full a fifth of the way up.
const pop = (t: number, start: number, dur: number) => {
  const peak = MOTION.pop.peakScale;
  const up = prog(t, start, dur * 0.57);
  const settle = prog(t, start + dur * 0.57, dur * 0.43);
  return {scale: FROM + (peak - FROM) * up - (peak - 1) * settle, seen: Math.min(1, up * 2.5)};
};

export const Aside: React.FC<{o: AsideLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const {width, height} = useVideoConfig();
  const L = look(o.variant);
  const m = MOTION.composition.aside;
  const d = MOTION.pop.durationS;
  const it = o.items.find((i) => i.key === 'pop') ?? o.items[0];
  const at = Math.max(o.t0, it?.at ?? o.t0);
  const frame: AsideFrame = o.frame ?? 'oval';
  const video = o.video;
  const art = video ? undefined : o.art;

  // What is drawn, and its shape: the art's opaque box in its own pixels, or the clip's aspect.
  const known = art ? KNOWN[art.main] : undefined;
  const size = art?.size ?? known;
  const content = art?.content ?? known?.content ?? (size ? {x: 0, y: 0, w: size.w, h: size.h} : undefined);
  const aspect = video ? video.aspect ?? 16 / 9 : content ? content.w / content.h : 1;

  // Sizes: the whole aside 25 to 40% of the frame's height, the plate above the label, the art inside the plate.
  let total = Math.min(0.4 * height, Math.max(0.25 * height, o.height ?? DEFAULT_H * height));
  if (o.box) total = Math.min(total, o.box.h);
  const tuck = o.label ? LABEL_H - LABEL_TUCK : 0;
  let plateH = total - tuck;
  let artH = video ? plateH : frame === 'oval' ? plateH / OVAL.h : frame === 'panel' ? plateH / (1 + 2 * PANEL_PAD) : plateH;
  let artW = artH * aspect;
  let plateW = video ? artW : frame === 'oval' ? Math.max(artW * OVAL.w, plateH * 0.9) :
    frame === 'panel' ? artW + 2 * PANEL_PAD * artH : artW;
  const maxW = o.box ? o.box.w : (width - LAYOUT.safePx.left - LAYOUT.safePx.right) * MAX_W;
  if (plateW > maxW) {
    const f = maxW / plateW;
    [plateW, plateH, artW, artH] = [plateW * f, plateH * f, artW * f, artH * f];
  }

  // Time: the plate grows on the word, the art pops just after it; a clip's whole frame pops; the label lands as
  // the pop settles; everything leaves together.
  const plateQ = prog(t, at, d * 0.35);       // the disc grows nearly opaque from small, as the piggy bank's does
  const artPop = pop(t, at + d * 0.12, d * 0.88);
  const framePop = pop(t, at, d);
  const lq = o.label ? prog(t, o.label_at ?? at + d * 0.6, 0.3) : 0;
  const out = exitLeft(t, o.t1, m.outS, fps);

  const plateStyle: React.CSSProperties = {position: 'absolute', left: 0, top: 0, width: plateW, height: plateH};
  let body: React.ReactNode;
  if (video) {
    const mask = `radial-gradient(ellipse closest-side, ${rgba(L.panel, 1)} 74%, ${rgba(L.panel, 0)} 100%)`;
    const clip = (
      <Sequence from={Math.round((at - o.t0) * fps)} layout="none">
        <OffthreadVideo src={staticFile(video.main)} trimBefore={Math.round((video.from ?? 0) * fps)} muted
          style={{width: '100%', height: '100%', objectFit: 'cover', display: 'block'}} />
      </Sequence>
    );
    const shown = {opacity: framePop.seen, transform: `scale(${framePop.scale})`};
    body = frame === 'panel' ? (
      <div style={{...plateStyle, ...shown}}>
        <Panel variant={o.variant} style={{width: '100%', height: '100%', padding: 0, overflow: 'hidden'}}>{clip}</Panel>
      </div>
    ) : (
      <div style={{...plateStyle, ...shown, overflow: 'hidden', borderRadius: frame === 'oval' ? '50%' : 0,
        ...(frame === 'oval' ? {maskImage: mask, WebkitMaskImage: mask} : {})}}>{clip}</div>
    );
  } else if (art) {
    const s = content ? artW / content.w : 1;
    const img = content && size ? (
      <Img src={staticFile(art.main)} style={{position: 'absolute', left: -content.x * s, top: -content.y * s,
        width: size.w * s, height: size.h * s, maxWidth: 'none'}} />
    ) : (
      <Img src={staticFile(art.main)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
    );
    body = (
      <>
        {frame !== 'none' && (
          <div style={{...plateStyle, opacity: Math.min(1, plateQ * 4), transform: `scale(${0.15 + 0.85 * plateQ})`}}>
            <Panel variant={o.variant} style={{width: '100%', height: '100%', padding: 0,
              ...(frame === 'oval' ? {borderRadius: '50%'} : {})}}>{null}</Panel>
          </div>
        )}
        <div style={{position: 'absolute', left: (plateW - artW) / 2, top: (plateH - artH) / 2, width: artW,
          height: artH, opacity: artPop.seen, transform: `scale(${artPop.scale})`, transformOrigin: '50% 60%',
          filter: frame === 'none' ? `drop-shadow(${LAYOUT.panel.shadow})` : undefined}}>
          <div style={{position: 'relative', width: '100%', height: '100%', overflow: 'hidden'}}>{img}</div>
        </div>
      </>
    );
  }

  return (
    <Placed box={o.box} edge={o.edge} fallback="right">
      <div style={{position: 'relative', width: plateW, height: plateH + tuck, flex: 'none', opacity: out,
        transform: `scale(${OUT_SCALE + (1 - OUT_SCALE) * out})`}}>
        {body}
        {o.label && (
          <div style={{position: 'absolute', left: 0, right: 0, top: plateH - LABEL_TUCK, display: 'flex',
            justifyContent: 'center', opacity: lq, transform: `translateY(${(1 - lq) * MOTION.risePx * 0.5}px)`}}>
            <Panel variant={o.variant} style={{height: LABEL_H, padding: '0 28px', display: 'flex', alignItems: 'center',
              whiteSpace: 'nowrap'}}>
              <div style={{...FONT.heading, fontSize: SIZE.heading, lineHeight: lh(SIZE.heading), color: L.heading}}>{o.label}</div>
            </Panel>
          </div>
        )}
      </div>
    </Placed>
  );
};

export type AsideProps = PreviewProps<AsideLayer>;

// Spot 9's aside (00:06:48:02): "When you upload a file, Quick Sight stores the data there", the SPICE jars.
export const ASIDE_SAMPLE: AsideProps = {durationInFrames: 150, fps: 30, width: 1920, height: 1080, still: '',
  layer: {id: 'aside-spice', layout: 'aside', t0: 0.5, t1: 4.5, variant: 'dark',
    art: {main: 'spice_jars_gemini-nano-banana-2.1_alpha.png'}, items: [{key: 'pop', text: 'spice jars', at: 0.6}],
    edge: 'right'}};

export const AsidePreview: React.FC<AsideProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><Aside o={layer} /></PreviewStage>
);
