import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Cam, toScreen} from './camera';
import {easeInOutCubic, Pt} from './track';
import {Hole, HighlightDim, HighlightLook, highlightAt} from './overlays/Highlighter';

// Attention marks (R48-R51), planned by pipeline/edit/plan.py. Two kinds, each in David's own look:
//  draw: Epic Pen marks in the flow, drawn by the cursor (it sits on the moving corner or the arrow's tip). They
//        appear as drawn (no fade-in), hold, then fade out. Drawn in source space inside the camera, so they grow
//        with the zoom like his live marks: ~5 px stroke, slightly rounded corners, an open chevron head.
//  fade: overview marks, an edit layer above the camera (his Premiere roadmap): 8 px square rectangles and an
//        arrow with a large filled head; they fade in, hold, fade out.
// path: an overview arrow that travels (R48, R63): {t, from, to} keys, linear between them.
export type MarkKey = {t: number; from: Pt; to: Pt};
// highlight (style dim): the Highlighter (R122, R142), everything but the box darkened; swap_from moves the lit
// region from the last highlight's box (overlays/Highlighter.tsx).
export type MarkLayer = {step: string; kind: 'rect' | 'arrow' | 'highlight'; style: 'draw' | 'fade' | 'dim';
  from: Pt; to: Pt; draw0: number; draw1: number; fade0: number; fade1: number; path?: MarkKey[];
  swap_from?: Hole};

const along = (keys: MarkKey[], t: number): {from: Pt; to: Pt} => {
  if (t <= keys[0].t) return keys[0];
  for (let i = 1; i < keys.length; i++) {
    const a = keys[i - 1], b = keys[i];
    if (t <= b.t) {
      const u = b.t > a.t ? (t - a.t) / (b.t - a.t) : 1;
      const mix = (p: Pt, q: Pt) => ({x: p.x + (q.x - p.x) * u, y: p.y + (q.y - p.y) * u});
      return {from: mix(a.from, b.from), to: mix(a.to, b.to)};
    }
  }
  return keys[keys.length - 1];
};
export type MarkStyle = {color: string; stroke_px: number; head_px: number; corner_px?: number;
  overview_stroke_px?: number; overview_head_px?: number; overview_arrow_color?: string; highlight?: HighlightLook};

const Mark: React.FC<{m: MarkLayer; t: number; cam: Cam; look: MarkStyle}> = ({m, t, cam, look}) => {
  const {width: W, height: H} = useVideoConfig();
  if (m.kind === 'highlight') {                            // source space only: the camera scales it with the picture
    const at = highlightAt(m, t);
    return at ? <HighlightDim hole={at.hole} alpha={at.alpha} width={W} height={H} look={look.highlight} /> : null;
  }
  if (t < m.draw0 || t > m.fade1) return null;
  const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
  let tip = m.to, tail = m.from, opacity = interpolate(t, [m.fade0, m.fade1], [1, 0], clamp);
  const live = m.style === 'draw';
  if (live) {
    const e = easeInOutCubic(Math.min(1, (t - m.draw0) / (m.draw1 - m.draw0)));
    tip = {x: m.from.x + (m.to.x - m.from.x) * e, y: m.from.y + (m.to.y - m.from.y) * e};
  } else if (m.path) {                                     // grows out of its tip, then travels
    const at = along(m.path, t);
    const g = interpolate(t, [m.draw0, m.draw1], [0, 1], clamp);
    tip = at.to;
    tail = {x: tip.x + (at.from.x - tip.x) * g, y: tip.y + (at.from.y - tip.y) * g};
  } else {
    opacity = Math.min(opacity, interpolate(t, [m.draw0, m.draw1], [0, 1], clamp));
  }
  const a = toScreen(cam, tail, W, H), b = toScreen(cam, tip, W, H);
  const sw = live ? look.stroke_px : (look.overview_stroke_px ?? 8);
  let shape: React.ReactNode;
  if (m.kind === 'rect') {
    const r = live ? (look.corner_px ?? 3) : 0;
    shape = <rect x={Math.min(a.x, b.x)} y={Math.min(a.y, b.y)} width={Math.abs(b.x - a.x)}
      height={Math.abs(b.y - a.y)} rx={r} ry={r} fill="none" stroke={look.color} strokeWidth={sw}
      strokeLinejoin={live ? 'round' : 'miter'} />;
  } else {
    const len = Math.hypot(b.x - a.x, b.y - a.y);
    if (len < 1) return null;
    const ux = (b.x - a.x) / len, uy = (b.y - a.y) / len;
    if (live) {                                            // open chevron: two strokes back from the tip
      const hl = Math.min(look.head_px, len * 0.5), hw = hl * 0.6;
      const base = {x: b.x - ux * hl, y: b.y - uy * hl};
      const p1 = {x: base.x - uy * hw, y: base.y + ux * hw}, p2 = {x: base.x + uy * hw, y: base.y - ux * hw};
      shape = (
        <g stroke={look.color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" fill="none">
          <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
          <polyline points={`${p1.x},${p1.y} ${b.x},${b.y} ${p2.x},${p2.y}`} />
        </g>
      );
    } else {                                               // large filled head (Arrow01)
      const color = look.overview_arrow_color ?? look.color;
      const hl = Math.min(look.overview_head_px ?? 40, len * 0.6), hw = hl * 0.6;
      const base = {x: b.x - ux * hl, y: b.y - uy * hl};
      const head = `${b.x},${b.y} ${base.x - uy * hw},${base.y + ux * hw} ${base.x + uy * hw},${base.y - ux * hw}`;
      shape = (
        <>
          <line x1={a.x} y1={a.y} x2={base.x + ux * 2} y2={base.y + uy * 2} stroke={color} strokeWidth={sw} />
          <polygon points={head} fill={color} />
        </>
      );
    }
  }
  return (
    <svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, opacity, overflow: 'visible'}}>
      {shape}
    </svg>
  );
};

// cam: the camera for screen-space marks; the identity camera for source-space marks drawn inside it.
export const Marks: React.FC<{layers: MarkLayer[]; cam: Cam; look: MarkStyle; style?: 'draw' | 'fade' | 'dim'}> = (
  {layers, cam, look, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  return <>{layers.map((m, i) => (!style || m.style === style)
    ? <Mark key={i} m={m} t={t} cam={cam} look={look} /> : null)}</>;
};
