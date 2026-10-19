import React, {createContext, useContext} from 'react';
import {useVideoConfig} from 'remotion';
import {CamKey, cameraAt, toScreen} from '../camera';
import {Box, LAYOUT} from './kit';

// Pinning an overlay to something on the screen recording (the overlay build's PinnedBox, R125's camera). Overlays
// are drawn in screen space, above the camera, so a piece that sits beside or on a thing in the recording follows
// that thing through the camera's pans and zooms. The camera keys come from the edit plan (`camera`), handed down by
// whoever renders the piece; the target is a box in source-frame px (the raw recording), as the plan's click targets
// and marks are. Without keys the camera is the identity, so a preview without a plan still lays out.

export const CameraKeys = createContext<CamKey[] | undefined>(undefined);

// Where a source-frame box is on the screen at edit time t.
export const usePinnedBox = (pin: Box, t: number): Box => {
  const keys = useContext(CameraKeys);
  const {width, height} = useVideoConfig();
  const c = cameraAt(keys, t, width, height);
  const a = toScreen(c, {x: pin.x, y: pin.y}, width, height);
  return {x: a.x, y: a.y, w: pin.w * c.s, h: pin.h * c.s};
};

export type Side = 'right' | 'left' | 'above' | 'below' | 'over';

// A w x h box (screen px) beside the pinned target on `side`, `gap` px away (centred on it for 'over'), kept inside
// title-safe and above the captions' band. Its children lay out from the box's own top-left corner.
export const PinnedBox: React.FC<{pin: Box; t: number; side: Side; w: number; h: number; gap?: number;
  children: React.ReactNode}> = ({pin, t, side, w, h, gap = 24, children}) => {
  const {width} = useVideoConfig();
  const b = usePinnedBox(pin, t);
  const cx = b.x + b.w / 2, cy = b.y + b.h / 2;
  let x = side === 'right' ? b.x + b.w + gap : side === 'left' ? b.x - gap - w : cx - w / 2;
  let y = side === 'below' ? b.y + b.h + gap : side === 'above' ? b.y - gap - h : cy - h / 2;
  const s = LAYOUT.safePx;
  x = Math.min(Math.max(x, s.left), width - s.right - w);
  y = Math.min(Math.max(y, s.top), LAYOUT.captionTopPx - h);
  return <div style={{position: 'absolute', left: x, top: y, width: w, height: h}}>{children}</div>;
};
