import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {CURSOR_APPEAR_LEAD_S, CURSOR_FADE_S, CURSOR_FROM_START, CURSOR_HEIGHT_PX} from './constants';
import {cursorAt, Move, Pt} from './track';

// Standard arrow on a 12 x 19 grid; the tip (0, 0) is the hotspot.
const ARROW = 'M0.5 0.5 L0.5 16.2 L4.4 12.6 L7.1 18.6 L9.5 17.6 L6.9 11.7 L11.8 11.7 Z';
const GRID_H = 19;

// t: the time the moves are in (source seconds in CursorPass, edit seconds in EditPass); defaults to this frame's time.
// map: track point -> output point. In EditPass the cursor is drawn in source space inside the camera, so it grows
// with the zoom (R46).
// hidden: spans with no cursor (R47: live waits, except their approvals); it fades over HIDE_FADE_S at each edge.
const HIDE_FADE_S = 0.2;
const shown = (hidden: [number, number][], t: number) => Math.min(1, ...hidden.map(([a, b]) =>
  t <= a || t >= b ? 1 : Math.max(0, Math.min(1, Math.max((a + HIDE_FADE_S - t) / HIDE_FADE_S, (t - b + HIDE_FADE_S) / HIDE_FADE_S)))));

export const Cursor: React.FC<{moves: Move[]; t?: number; height?: number; map?: (p: Pt) => Pt;
  hidden?: [number, number][]}> = ({moves, t: tSrc, height = CURSOR_HEIGHT_PX, map = (p) => p, hidden = []}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (moves.length === 0) return null;
  const t = tSrc ?? frame / fps;
  const first = moves[0].t0;
  if (!CURSOR_FROM_START && t < first - CURSOR_APPEAR_LEAD_S) return null;
  // Rest at the first move's start point (viewport centre, where the runner parks the mouse) until it moves.
  const p = map(cursorAt(moves, Math.max(t, first))!);
  // (the hidden spans apply either way: the from-start cursor used to skip them, so waits showed it, s7_take06)
  const appear = CURSOR_FROM_START ? 1 : interpolate(t, [first - CURSOR_APPEAR_LEAD_S, first - CURSOR_APPEAR_LEAD_S + CURSOR_FADE_S],
    [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const opacity = appear * shown(hidden, t);
  if (opacity <= 0) return null;
  const k = height / GRID_H;
  return (
    <svg
      width={12 * k + 4}
      height={height + 4}
      viewBox={`0 0 ${12 + 4 / k} ${GRID_H + 4 / k}`}
      style={{position: 'absolute', left: p.x, top: p.y, opacity, overflow: 'visible',
        filter: 'drop-shadow(1px 2px 2px rgba(0,0,0,0.35))'}}
    >
      <path d={ARROW} fill="#FFFFFF" stroke="#000000" strokeWidth={1} strokeLinejoin="round" />
    </svg>
  );
};
