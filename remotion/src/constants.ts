// Cursor and click style, SPEC §7.1. Every tunable for slice S2 lives here.

export const CURSOR_HEIGHT_PX = 48;        // arrow height at 1080p (David 2026-10-06: 1.5-2x the 28 px start, for phones)
export const CURSOR_FROM_START = true;      // visible from frame 0 at the parked point (David 2026-10-06)
export const CURSOR_APPEAR_LEAD_S = 0.25;  // otherwise: fade in at the start point this long before the first move
export const CURSOR_FADE_S = 0.15;

export const RING_COLOR = '#F16F05';  // R51: same orange as the marks
export const RING_MAX_DIAMETER_PX = 88;    // grows 0 -> 88 px (David 2026-10-06: doubled from 44, for phones)
export const RING_GROW_S = 0.35;           // over 350 ms
export const RING_FADE_S = 0.3;            // then fades out
export const RING_STROKE_PX = 5;
