// Shared pieces of the overlay composition set (R131, R134): the look tokens, the panel, placement, easing, and the
// preview stage. The tokens are a copy of D:\Videos\Global Assets\motion-styles\giddyup.tokens.json
// (`npm run sync-tokens`); STYLE.md beside that file says what each one is for.
//
// Every composition is drawn from a layer object in edit time (seconds on the full sequence): t0 and t1 bound it,
// items carry their own `at` times on the spoken words (R80), and the Sequence it sits in starts at t0, so
// t = t0 + frame / fps. Outside its own shapes each one is transparent (rendered as ProRes 4444 with alpha).
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import tokens from './tokens.json';
import {loadOverlayFonts} from './fonts';

export type Variant = 'dark' | 'light';            // R140: dark on a light screen, light on a dark one
export type Look = typeof tokens.color.variant.dark;
export type Box = {x: number; y: number; w: number; h: number};   // frame px
export type Edge = 'top' | 'bottom' | 'left' | 'right';
export type TimedItem = {text: string; at: number};

export const look = (v: Variant | undefined): Look => tokens.color.variant[v === 'light' ? 'light' : 'dark'];
export const TOKENS = tokens;
export const ACCENT = tokens.color.accent;
export const SIZE = tokens.type.sizePx;
export const MOTION = tokens.motion;
export const LAYOUT = tokens.layout;

// Fonts by family name. The Windows fonts (R143) are named, never shipped: Microsoft's fonts can't go out with code
// that goes public (R95). The OFL stand-ins after them in each stack ship in fonts/ and load here (R148).
loadOverlayFonts();
type Family = {name: string; fallback: string[]; weight: number};
const fontCss = (f: Family): React.CSSProperties => ({
  fontFamily: [f.name, ...f.fallback].map((x) => (/^[a-z-]+$/.test(x) ? x : `"${x}"`)).join(', '),
  fontWeight: f.weight,
});
export const FONT = {
  heading: fontCss(tokens.type.family.heading),
  body: fontCss(tokens.type.family.body),
  wordList: fontCss(tokens.type.family.wordList),
  data: fontCss(tokens.type.family.data),
};

// A line's height for text of this size (R161): 1.15 of the font size, so a token change never squeezes a line.
export const lh = (px: number, k = 1.15) => `${Math.round(px * k)}px`;

export const rgba = (hex: string, a: number) => {
  const h = hex.replace('#', '');
  const v = (i: number) => parseInt(h.slice(i, i + 2), 16);
  return `rgba(${v(0)}, ${v(2)}, ${v(4)}, ${a})`;
};

// "Neutral data-story": one cubic-bezier, no overshoot.
const curve = Easing.bezier(...(tokens.motion.ease as [number, number, number, number]));
// Eased progress 0..1 of an animation that starts at `start` and lasts `dur` seconds, at time t.
export const prog = (t: number, start: number, dur: number) =>
  dur <= 0 ? (t >= start ? 1 : 0) : curve(Math.min(1, Math.max(0, (t - start) / dur)));
// 1 while the layer is up, easing to 0 by its last frame.
export const exitLeft = (t: number, t1: number, outS: number, fps: number) => 1 - prog(t, t1 - 1 / fps - outS, outS);

// Each item's start: its own time, but never closer than `gap` after the one before (the 80 ms stagger).
export const spaced = (ats: number[], gap: number) => {
  let prev = -Infinity;
  return ats.map((a) => (prev = Math.max(a, prev + gap)));
};

export const useEditTime = (t0: number) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  return {t: t0 + frame / fps, fps, width, height};
};

// The panel: the variant's colour at 96%, a 2 px rule, a soft shadow so it lifts off the screen.
export const Panel: React.FC<{variant: Variant; style?: React.CSSProperties; children: React.ReactNode}> =
  ({variant, style, children}) => {
    const L = look(variant);
    const p = LAYOUT.panel;
    return (
      <div style={{background: rgba(L.panel, L.panelOpacity), border: `${p.ruleWidthPx}px solid ${L.rule}`,
        borderRadius: p.radiusPx, boxShadow: p.shadow, padding: `${p.padPx[0]}px ${p.padPx[1]}px`,
        boxSizing: 'border-box', ...style}}>
        {children}
      </div>
    );
  };

// Where a panel sits: centred in a box (frame px), or against an edge of the title-safe area (R123), above the
// captions' band. Nothing given: the composition's own default edge.
export const Placed: React.FC<{box?: Box; edge?: Edge; fallback: Edge; children: React.ReactNode}> =
  ({box, edge, fallback, children}) => {
    const {width} = useVideoConfig();
    const s = LAYOUT.safePx;
    const area = box ?? {x: s.left, y: s.top, w: width - s.left - s.right, h: LAYOUT.captionTopPx - s.top};
    const e = box ? null : edge ?? fallback;
    return (
      <div style={{position: 'absolute', left: area.x, top: area.y, width: area.w, height: area.h, display: 'flex',
        justifyContent: e === 'left' ? 'flex-start' : e === 'right' ? 'flex-end' : 'center',
        alignItems: e === 'top' ? 'flex-start' : e === 'bottom' ? 'flex-end' : 'center'}}>
        {children}
      </div>
    );
  };

// The preview compositions: a layer over an optional still (in the public dir), for check stills before a render.
// Without a still the frame is transparent, as the overlay clip is.
export type PreviewProps<L> = {durationInFrames: number; fps: number; width: number; height: number; still?: string;
  layer: L};

export const PreviewStage: React.FC<{still?: string; t0: number; t1: number; children: React.ReactNode}> =
  ({still, t0, t1, children}) => {
    const {fps} = useVideoConfig();
    const f = (s: number) => Math.round(s * fps);
    return (
      <AbsoluteFill>
        {still ? <Img src={staticFile(still)} /> : null}
        <Sequence from={f(t0)} durationInFrames={Math.max(1, f(t1) - f(t0))} layout="none">{children}</Sequence>
      </AbsoluteFill>
    );
  };
