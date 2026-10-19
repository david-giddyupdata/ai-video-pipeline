import React from 'react';
import {AbsoluteFill, Audio, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame,
  useVideoConfig} from 'remotion';
import {Cam, cameraAt, cameraTransform} from './camera';
import {ClickRing} from './ClickRing';
import {Cursor} from './Cursor';
import {Marks} from './Marks';
import {Overlays} from './Overlays';
import {TitleCard} from './Slides';
import {CaptionCue, ClipSeg, EditPlan, HoldSeg, Segment} from './plan';
import {easeInOutCubic} from './track';

// Slices S3-S4: the take cut to the edit plan, with narration, the zoom camera, the cursor, marks and burned-in
// captions (SPEC §6.4, §7, §8). Each segment is a Sequence; a clip followed by a transition keeps playing for tail_s
// under the incoming clip. The camera scales the picture together with the cursor, click rings and Epic Pen marks,
// which are drawn in source space and so grow with the zoom (David, 2026-10-06; as in his own recordings). Overview
// marks and captions sit outside the camera, in screen space.

const ClipLayer: React.FC<{seg: ClipSeg; next?: Segment; video: string}> = ({seg, next, video}) => {
  const frame = useCurrentFrame();                          // local to this segment's Sequence
  const {fps, width} = useVideoConfig();
  const durF = Math.round(seg.dur * fps);
  const inF = seg.transition_frames ?? 0;
  const opts = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeInOutCubic} as const;
  let style: React.CSSProperties = {};
  if (seg.transition_in === 'cut' && frame < inF) {
    style = {opacity: interpolate(frame, [0, inF], [0, 1], opts)};
  } else if (seg.transition_in === 'swipe' && frame < inF) {
    style = {transform: `translateX(${interpolate(frame, [0, inF], [width, 0], opts)}px)`};
  }
  if (frame >= durF && next?.type === 'clip' && next.transition_in === 'swipe') {    // outgoing half of a swipe
    const tailF = Math.max(1, Math.round((seg.tail_s ?? 0) * fps));
    style = {transform: `translateX(${interpolate(frame - durF, [0, tailF], [0, -width], opts)}px)`};
  }
  return (
    <AbsoluteFill style={style}>
      <OffthreadVideo src={staticFile(video)} trimBefore={Math.round(seg.src_in * fps)} playbackRate={seg.speed}
        muted />
    </AbsoluteFill>
  );
};

// A freeze shows the exact recorded frame, cut out by the planner (Remotion's <Freeze> around a video showed the
// wrong frame in S3 take 05).
const HoldLayer: React.FC<{seg: HoldSeg}> = ({seg}) => (
  <AbsoluteFill>
    <Img src={staticFile(seg.still ?? '')} />
  </AbsoluteFill>
);

type CaptionStyle = EditPlan['captions']['style'];

// Captions (R52, R53): high visibility, burned in, never covering what the viewer needs. Lucida Console on an opaque
// dark grey box with rounded corners, white text with a black outline and drop shadow. The planner picks each cue's spot (pos); default bottom
// centre.
const boxColor = (hex = '#1E1E1E', alpha = 0.88) => {
  const n = parseInt(hex.replace('#', ''), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
};

const Captions: React.FC<{cues: CaptionCue[]; look?: CaptionStyle}> = ({cues, look}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const cue = cues.find((c) => c.start <= t && t < c.end);
  if (!cue) return null;
  const size = look?.size_px ?? 48;
  const stroke = look?.text_stroke_px ?? 3;
  const pos = cue.pos ?? {where: 'bottom-centre', cx: width / 2, y: height - 56 - 2 * size};
  return (
    <div style={{position: 'absolute', left: pos.cx, top: pos.y, transform: 'translateX(-50%)',
      padding: `${look?.pad_y_px ?? 8}px ${look?.pad_x_px ?? 18}px`, borderRadius: look?.corner_radius_px ?? 0, whiteSpace: 'pre',
      background: boxColor(look?.box_color, look?.box_opacity), color: 'white', textAlign: 'center',
      font: `${size}px/${look?.line_height ?? 1.25} "${look?.font ?? 'Lucida Console'}", Consolas, monospace`,
      WebkitTextStroke: `${stroke}px black`, paintOrder: 'stroke fill',
      textShadow: '2px 2px 4px rgba(0, 0, 0, 0.9)', boxShadow: '0 2px 10px rgba(0, 0, 0, 0.5)'}}>
      {cue.text}
    </div>
  );
};

const IDENTITY = (W: number, H: number): Cam => ({s: 1, x: W / 2, y: H / 2});

// Cursor, click rings and Epic Pen marks in source space. only: 'cursor' (cursor and rings), 'mark:<i>' (one mark
// layer), or everything in the flow.
export const SourceOverlay: React.FC<{plan: EditPlan; only?: string}> = ({plan, only}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const t = frame / fps;
  const {moves, clicks, style} = plan.cursor;
  const layers = plan.marks?.layers ?? [];
  const mark = only?.startsWith('mark:') ? layers[Number(only.slice(5))] : undefined;
  const showCursor = !only || only === 'cursor';
  return (
    <AbsoluteFill>
      {plan.marks && !only && <Marks layers={layers} cam={IDENTITY(W, H)} look={plan.marks.style} style="dim" />}
      {plan.marks && !only && <Marks layers={layers} cam={IDENTITY(W, H)} look={plan.marks.style} style="draw" />}
      {plan.marks && mark && <Marks layers={[mark]} cam={IDENTITY(W, H)} look={plan.marks.style} />}
      {showCursor && clicks.map((c) => (
        <ClickRing key={c.step} click={c} diameter={style.ring_diameter_px} stroke={style.ring_stroke_px} />
      ))}
      {showCursor && <Cursor moves={moves} t={t} height={style.height_px} hidden={plan.cursor.hidden} />}
    </AbsoluteFill>
  );
};

// Recording flaws covered with a clean picture of the same place (R173): the plate's pixels inside the box, in source
// space inside the camera, so they follow the zoom; under the blurs, the cursor and the marks.
const Corrections: React.FC<{plan: EditPlan}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  return <>{(plan.corrections ?? []).filter((c) => (c.frames ? c.frames[0] <= frame && frame < c.frames[1]
    : c.t0 <= t && t < c.t1)).map((c) => (
    <div key={c.id} style={{position: 'absolute', left: c.box[0], top: c.box[1], width: c.box[2] - c.box[0],
      height: c.box[3] - c.box[1], overflow: 'hidden'}}>
      <Img src={staticFile(c.plate)} style={{position: 'absolute', left: -c.box[0], top: -c.box[1]}} />
    </div>
  ))}</>;
};

// Privacy findings David chose to blur (R56): drawn in source space inside the camera, so they follow the zoom.
const PrivacyMasks: React.FC<{plan: EditPlan}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  return <>{(plan.privacy_masks ?? []).filter((m) => m.t0 <= t && t <= m.t1).map((m) => (
    <div key={m.id} style={{position: 'absolute', left: m.box[0] - 6, top: m.box[1] - 6,
      width: m.box[2] - m.box[0] + 12, height: m.box[3] - m.box[1] + 12,
      backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)'}} />
  ))}</>;
};

const OverviewMarks: React.FC<{plan: EditPlan}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  if (!plan.marks) return null;
  return <Marks layers={plan.marks.layers} cam={cameraAt(plan.camera, frame / fps, W, H)} look={plan.marks.style}
    style="fade" />;
};

// Title cards over long live waits (R39), in screen space over the held frame.
const Cards: React.FC<{plan: EditPlan; only?: number}> = ({plan, only}) => {
  const {fps} = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
  return <>{plan.segments.map((seg, i) => seg.type === 'hold' && seg.card && (only === undefined || only === i) && (
    <Sequence key={i} from={f(seg.t)} durationInFrames={Math.max(1, f(seg.t + seg.dur) - f(seg.t))}>
      <TitleCard title={seg.card.title} sub={seg.card.sub} dur={f(seg.t + seg.dur) - f(seg.t)} />
    </Sequence>
  ))}</>;
};

// One transparent layer for the Premiere export (pipeline.edit.premiere), rendered as ProRes 4444. only:
// 'cursor', 'mark:<i>', 'card:<segment index>' or 'overlay:<i>'.
export const OverlayClip: React.FC<EditPlan & {only?: string}> = (props) => props.only?.startsWith('card:')
  ? <Cards plan={props} only={Number(props.only.slice(5))} />
  : props.only?.startsWith('overlay:')
    ? <Overlays overlays={props.overlays ?? []} only={Number(props.only.slice(8))} />
    : <SourceOverlay plan={props} only={props.only} />;

const Camera: React.FC<{plan: EditPlan; children: React.ReactNode}> = ({plan, children}) => {
  const frame = useCurrentFrame();
  const {fps, width: W, height: H} = useVideoConfig();
  const cam = cameraAt(plan.camera, frame / fps, W, H);
  return <AbsoluteFill style={{transformOrigin: '0 0', transform: cameraTransform(cam, W, H)}}>{children}</AbsoluteFill>;
};

export const EditPass: React.FC<EditPlan> = (plan) => {
  const {fps} = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      <Camera plan={plan}>
      {plan.segments.map((seg, i) => {
        const len = Math.max(1, f(seg.t + seg.dur) - f(seg.t) + (seg.type === 'clip' ? f(seg.tail_s ?? 0) : 0));
        return (
          <Sequence key={i} from={f(seg.t)} durationInFrames={len}>
            {seg.type === 'clip'
              ? <ClipLayer seg={seg} next={plan.segments[i + 1]} video={plan.video} />
              : <HoldLayer seg={seg} />}
          </Sequence>
        );
      })}
        <Corrections plan={plan} />
        <PrivacyMasks plan={plan} />
        <SourceOverlay plan={plan} />
      </Camera>
      {plan.narration.flatMap((n) => (n.parts ?? [{at: n.start, in: 0, out: n.length}]).map((p, k) => (
        <Sequence key={`${n.line_id}-${k}`} from={f(p.at)} durationInFrames={Math.max(1, f(p.out) - f(p.in))}>
          <Audio src={staticFile(n.src)} trimBefore={f(p.in)} />
        </Sequence>
      )))}
      {plan.click_sound && (plan.click_sound.at ?? plan.cursor.clicks).map((c) => (
        <Sequence key={`click-${c.step}-${c.t}`} from={f(c.t)} durationInFrames={Math.max(1, f(plan.click_sound!.length_s))}>
          <Audio src={staticFile(plan.click_sound!.src)} />
        </Sequence>
      ))}
      <OverviewMarks plan={plan} />
      <Overlays overlays={plan.overlays ?? []} />
      <Cards plan={plan} />
      {plan.captions.burn && <Captions cues={plan.captions.cues} look={plan.captions.style} />}
    </AbsoluteFill>
  );
};
