// edit_plan.json, written by pipeline.edit.plan. Times are edited-timeline seconds unless named src_*.
// Cursor moves and clicks are in edit time too (S4), so a mark's gesture can play over a freeze.
import {CamKey} from './camera';
import {MarkLayer, MarkStyle} from './Marks';
import {OverlayLayer} from './Overlays';
import {Click, Move} from './track';

export type ClipSeg = {type: 'clip'; t: number; dur: number; src_in: number; src_out: number; speed: number;
  transition_in: null | 'cut' | 'swipe'; transition_frames?: number; tail_s?: number};
export type HoldSeg = {type: 'hold'; t: number; dur: number; src_t: number; still?: string;
  card?: {title: string; sub?: string}};   // a title card over a long live wait (R39)
export type Segment = ClipSeg | HoldSeg;

export type CaptionCue = {start: number; end: number; text: string;
  pos?: {where: string; cx: number; y: number}};

export type EditPlan = {
  video: string; fps: number; width: number; height: number; durationInFrames: number;
  gap_treatment: string;
  segments: Segment[];
  // a line plays as parts when the planner put a beat inside it (R62) or a run-on trimmed its silent tail (R25)
  narration: {line_id: string; src: string; start: number; length: number;
    parts?: {at: number; in: number; out: number}[]}[];
  cursor: {moves: Move[]; clicks: Click[]; hidden?: [number, number][]; style: {height_px: number; ring_diameter_px: number; ring_stroke_px: number}};
  camera?: CamKey[];
  privacy_masks?: {id: string; why: string; box: [number, number, number, number]; t0: number; t1: number}[];
  // R173: a recording flaw covered with a clean picture (plate: a frame-sized PNG in the run folder, source px)
  corrections?: {id: string; why: string; box: [number, number, number, number]; plate: string; t0: number; t1: number;
    frames?: [number, number]}[];   // edit frames [a, b), placed as Premiere's clips are
  marks?: {layers: MarkLayer[]; style: MarkStyle};
  overlays?: OverlayLayer[];     // cards that show text whole (R77), screen space
  click_sound?: {src: string; peak_dbfs: number; length_s: number;   // R137: one at each click ring, but
    at?: {step: string; t: number}[]};                                  // none on another's tail (the plan's list)
  captions: {burn: boolean; cues: CaptionCue[];
    style?: {font?: string; size_px?: number; box_color?: string; box_opacity?: number; line_height?: number;
      pad_x_px?: number; pad_y_px?: number; text_stroke_px?: number; corner_radius_px?: number}};
};

// Source time shown at edit time t (the incoming segment wins during a transition).
export const srcTimeAt = (segs: Segment[], t: number): number => {
  let seg = segs[0];
  for (const s of segs) if (s.t <= t) seg = s;
  if (seg.type === 'hold') return seg.src_t;
  return Math.min(seg.src_in + (t - seg.t) * seg.speed, seg.src_out);
};
