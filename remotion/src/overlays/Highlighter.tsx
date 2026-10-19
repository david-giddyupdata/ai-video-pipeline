import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {easeInOutCubic, Pt} from '../track';

// The Highlighter (R122, R142; the overlay plan's composition 8): David's layer spotlight. Everything but a large
// region (a whole pane, one side of a dialog) is darkened to his measured brightness of about 0.58 (a black layer at
// 42%); the dim fades in slowly and linearly (1.0 s), the lit region moves between neighbours (a swap, 0.3 s), and
// the dim lifts (1.3 s, faster when the next mark is close). In the edit it is drawn in source space, inside the
// camera, so it follows the zoom like the Epic Pen marks (Marks.tsx); pipeline/edit/plan.py `highlights` times it.

export type Hole = {from: Pt; to: Pt};
export type HighlightTiming = {draw0: number; draw1: number; fade0: number; fade1: number; swap_from?: Hole};
export type HighlightLook = {dim_opacity?: number; corner_px?: number};

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// The dim and its hole at time t (s), or null when it isn't up.
export const highlightAt = (h: HighlightTiming & Hole, t: number): {alpha: number; hole: Hole} | null => {
  if (t < h.draw0 || t > h.fade1) return null;
  const out = h.fade1 > h.fade0 ? interpolate(t, [h.fade0, h.fade1], [1, 0], clamp) : (t < h.fade1 ? 1 : 0);
  if (h.swap_from) {                                       // the dim is already up: the lit region moves
    const u = easeInOutCubic(interpolate(t, [h.draw0, h.draw1], [0, 1], clamp));
    const mix = (a: Pt, b: Pt) => ({x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u});
    return {alpha: out, hole: {from: mix(h.swap_from.from, h.from), to: mix(h.swap_from.to, h.to)}};
  }
  return {alpha: Math.min(out, interpolate(t, [h.draw0, h.draw1], [0, 1], clamp)), hole: {from: h.from, to: h.to}};
};

// One frame of the dim: a frame-sized dark layer with a rounded hole (even-odd fill), in the given space's pixels.
export const HighlightDim: React.FC<{hole: Hole; alpha: number; width: number; height: number;
  look?: HighlightLook}> = ({hole, alpha, width, height, look}) => {
  const x0 = Math.min(hole.from.x, hole.to.x), y0 = Math.min(hole.from.y, hole.to.y);
  const x1 = Math.max(hole.from.x, hole.to.x), y1 = Math.max(hole.from.y, hole.to.y);
  const r = Math.min(look?.corner_px ?? 8, (x1 - x0) / 2, (y1 - y0) / 2);
  // a margin past the frame so no edge shows under a camera move
  const m = Math.max(width, height);
  const outer = `M${-m},${-m} H${width + m} V${height + m} H${-m} Z`;
  const inner = `M${x0 + r},${y0} H${x1 - r} A${r},${r} 0 0 1 ${x1},${y0 + r} V${y1 - r} A${r},${r} 0 0 1 ${x1 - r},${y1}`
    + ` H${x0 + r} A${r},${r} 0 0 1 ${x0},${y1 - r} V${y0 + r} A${r},${r} 0 0 1 ${x0 + r},${y0} Z`;
  return (
    <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
      <path d={`${outer} ${inner}`} fillRule="evenodd" fill="black" fillOpacity={(look?.dim_opacity ?? 0.42) * alpha} />
    </svg>
  );
};

// A preview composition: the highlighter over a still from the run (public dir), for check stills before a render.
export type HighlighterProps = {durationInFrames: number; fps: number; width: number; height: number;
  still: string; highlights: (HighlightTiming & Hole)[]; look?: HighlightLook};

export const Highlighter: React.FC<HighlighterProps> = ({still, highlights, look}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      {still ? <Img src={staticFile(still)} /> : null}
      {highlights.map((h, i) => {
        const at = highlightAt(h, t);
        return at ? <HighlightDim key={i} hole={at.hole} alpha={at.alpha} width={width} height={height} look={look} />
          : null;
      })}
    </AbsoluteFill>
  );
};
