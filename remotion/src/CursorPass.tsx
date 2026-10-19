import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile} from 'remotion';
import {ClickRing} from './ClickRing';
import {Cursor} from './Cursor';
import {CursorTrack} from './track';

// Slice S2: the take's raw recording with the synthetic cursor and click rings drawn on (SPEC §7.1).
// The ring sits under the cursor, so the arrow tip stays readable at the click point.
export const CursorPass: React.FC<CursorTrack> = ({video, moves, clicks}) => (
  <AbsoluteFill style={{backgroundColor: 'black'}}>
    <OffthreadVideo src={staticFile(video)} muted />
    {clicks.map((c) => <ClickRing key={`${c.step}-${c.t}`} click={c} />)}
    <Cursor moves={moves} />
  </AbsoluteFill>
);
