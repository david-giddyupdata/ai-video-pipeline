import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {AvatarStage, StageProps} from './AvatarStage';
import {SeriesCard, SeriesCardLayer} from './SeriesCard';
import {SubscribeAnim, SubscribeLayer} from './SubscribeCta';

// CtaPreview (R242's samples): one of the new pieces over the stage it will join, for David to judge before anything
// is wired in. The stage is drawn from a round's own AvatarStage props (its cityscape, its avatar, its moves); the
// captions are stand-ins drawn from the round's caption titles (their boxes and text, C1's house look: Lucida Console
// 48 px, white on #575757, 15 px padding, 10 px corners), so the piece's clearance from them shows. Not a library piece.

export type PreviewCue = {t0: number; t1: number; text: string; box: [number, number, number, number]};
export type CtaPreviewProps = {durationInFrames: number; fps: number; width: number; height: number;
  stage: StageProps; captions: PreviewCue[]; series?: SeriesCardLayer; subscribe?: SubscribeLayer};

const Caption: React.FC<{c: PreviewCue}> = ({c}) => {
  const [x, y, w, h] = c.box;
  const lines = c.text.split('\n');
  return (
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h, boxSizing: 'border-box',
      background: '#575757', borderRadius: 10, padding: '15px 15px', display: 'flex', flexDirection: 'column',
      justifyContent: 'center'}}>
      {lines.map((l, i) => (
        <div key={i} style={{fontFamily: '"Lucida Console", monospace', fontSize: 48, color: '#ffffff',
          lineHeight: `${Math.floor((h - 30) / lines.length)}px`, whiteSpace: 'pre'}}>{l}</div>
      ))}
    </div>
  );
};

export const CtaPreview: React.FC<CtaPreviewProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  return (
    <AbsoluteFill style={{background: '#000000'}}>
      <AvatarStage {...p.stage} />
      {p.series ? <SeriesCard o={p.series} /> : null}
      {p.subscribe ? <SubscribeAnim o={p.subscribe} /> : null}
      {p.captions.filter((c) => t >= c.t0 && t < c.t1).map((c, i) => <Caption key={i} c={c} />)}
    </AbsoluteFill>
  );
};
