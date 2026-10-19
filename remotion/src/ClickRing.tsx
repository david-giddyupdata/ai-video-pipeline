import React from 'react';
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {RING_COLOR, RING_FADE_S, RING_GROW_S, RING_MAX_DIAMETER_PX, RING_STROKE_PX} from './constants';
import {Click, Pt} from './track';

export const ClickRing: React.FC<{click: Click; diameter?: number; stroke?: number; map?: (p: Pt) => Pt}> = (
  {click, diameter = RING_MAX_DIAMETER_PX, stroke = RING_STROKE_PX, map = (p) => p}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const dt = frame / fps - click.t;
  if (dt < 0 || dt > RING_GROW_S + RING_FADE_S || (click.until !== undefined && frame / fps >= click.until)) return null;
  const d = interpolate(dt, [0, RING_GROW_S], [0, diameter],
    {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const opacity = interpolate(dt, [RING_GROW_S, RING_GROW_S + RING_FADE_S], [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const at = map(click.at);
  return (
    <div
      style={{
        position: 'absolute', left: at.x - d / 2, top: at.y - d / 2, width: d, height: d,
        borderRadius: '50%', border: `${stroke}px solid ${RING_COLOR}`, boxSizing: 'border-box', opacity,
      }}
    />
  );
};
