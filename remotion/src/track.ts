// The cursor track that pipeline.post.s2_cursor writes from runlog.jsonl + calibration.json.
// Times are video seconds and positions are video pixels; all log -> video mapping happens in Python.

export type Pt = {x: number; y: number};

export type Move = {step: string; t0: number; t1: number; from: Pt; to: Pt};
export type Click = {step: string; t: number; at: Pt; until?: number};

export type CursorTrack = {
  video: string;               // file name inside --public-dir (the run folder)
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  moves: Move[];
  clicks: Click[];
};

// Same curve as pipeline/driver/runner.py:move_mouse: cubic ease-in-out on a straight line.
export const easeInOutCubic = (u: number) =>
  u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2;

// Where the cursor is at video time t, or null before the first move starts.
export const cursorAt = (moves: Move[], t: number): Pt | null => {
  if (moves.length === 0 || t < moves[0].t0) return null;
  let rest = moves[0].from;
  for (const m of moves) {
    if (t < m.t0) return rest;
    if (t < m.t1) {
      const e = easeInOutCubic((t - m.t0) / (m.t1 - m.t0));
      return {x: m.from.x + (m.to.x - m.from.x) * e, y: m.from.y + (m.to.y - m.from.y) * e};
    }
    rest = m.to;
  }
  return rest;
};
