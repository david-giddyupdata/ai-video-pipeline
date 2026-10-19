import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import CTA from './data/cta.json';
import {Box, prog} from './kit';

// SeriesCard (R242): the "Amazon Quick Series" card of David's Quick Series, rebuilt in code to replace the Motion
// Array "Unique Cards" Card 09 he used (R131: away from Motion Array). Measured from 03-QuickArch03.mp4 (25 fps; the
// card's nest starts at 00:00:00:13) and its source clips (Card 09 C1/C2.mov, the nest "02Card 09-Arch" in
// AmazonQuick.prproj, read from a copy):
//   * the look: a rounded card, black with a curved band low on it, magenta into orange into pale gold towards the
//     bottom right (an ellipse centred above the card's left third: GRAD), a thin light outline, the series name in
//     Berlin Sans FB Demi bold, white, and the episode's title in a darker see-through inner panel;
//   * the entrance (seconds from t0): the title wipes on left to right (0.34 to 0.88) while it rises and grows to
//     size; a faint outline of the card shows (0.5 to 0.84); the band rises from the bottom (0.62 to 1.10) and the
//     card fills in black behind it (0.72 to 1.52); the inner panel fades in (1.08 to 1.26) and the episode's title
//     wipes up into it (1.18 to 1.34);
//   * the exit is the entrance played backwards (the original's last piece is the same clip reversed), mirrored
//     about t1: in this composition every part's state is a function of tau = min(t - t0, t1 - t). QuickArch03 has
//     t1 - t0 = 5.78 s: settled from 1.52 s, the exit starting at 4.26 s, gone at 5.44 s.
// Placement is the caller's (box, frame px): the original's 968 x 424 at the frame's bottom-right corner is outside
// title-safe (G15), so a stage puts it inside, clear of the captions and the avatar's face.
// Text follows the house's sizes, not the original's (G3: the title at least 60 px; the episode's title at least 56
// against the original's 33, which a phone can't read); the layout follows the text (the title, then the inner panel
// with one line or more), so the card's proportions follow its box; the inner panel is darker than the original's so
// the white text keeps 7:1 over the band's gold (G6). Everything outside the card is transparent (ProRes 4444).

export type SeriesCardLayer = {t0: number; t1: number; title: string; lines: string[]; box: Box};
export type SeriesCardProps = {durationInFrames: number; fps: number; width: number; height: number;
  still?: string; layer: SeriesCardLayer};

// Berlin Sans FB Demi (Office's, on David's PC: named, never shipped, R95, R148), then Inter as the stand-in. Chrome
// files the Demi under the family "Berlin Sans FB" at weight 600 (700 is the heavier Berlin Sans FB Bold, and the name
// "Berlin Sans FB Demi" matches nothing: tested 2026-10-17).
const CARD_FONT: React.CSSProperties = {fontFamily: '"Berlin Sans FB", Inter, sans-serif', fontWeight: 600};
const REF_W = 968;                 // the original card's width on QuickArch03's frame (px): motion distances scale by it
const TITLE_PX = 64;               // G3: a heading at least 60
const LINE_PX = 56;                // G3: labels at least 56 (David, 2026-10-17: one line, "QS Journey 1: First dashboard")
const RADIUS = 0.0413;             // corner radius / card width (40 px on the original's 968)

// The band: an ellipse centred at (0.25 w, -0.95 h) with radii (1.05 w, 1.6 h); colour by normalised radius r, fitted
// on QuickArch03's frame 80 (r < 0.9 black). CSS stops are r / 1.3 of the gradient's ray.
const GRAD_STOPS: [number, string][] = [[0.95, '#16010c'], [1.0, '#53042f'], [1.05, '#99194d'], [1.1, '#be594a'],
  [1.15, '#c88740'], [1.2, '#c89746'], [1.25, '#ccbb63'], [1.3, '#cdc269']];
const grad = (w: number, h: number, core: string, dropY: number) => {
  const R = 1.3;
  const stops = GRAD_STOPS.map(([r, c]) => `${c} ${((100 * r) / R).toFixed(1)}%`).join(', ');
  return `radial-gradient(ellipse ${R * 1.05 * w}px ${R * 1.6 * h}px at ${0.25 * w}px ${(-0.95 + dropY) * h}px, ` +
    `${core} 0%, ${core} ${((100 * 0.9) / R).toFixed(1)}%, ${stops})`;
};

// Each part's progress at tau (seconds into the entrance), measured from QuickArch03's frames (module comment).
const between = (tau: number, a: number, b: number) => Math.min(1, Math.max(0, (tau - a) / (b - a)));   // a to b
export const seriesCardState = (tau: number) => ({
  title: prog(tau, 0.34, 0.54),                          // the wipe, decelerating (52 px a frame falling to 16)
  titleMove: prog(tau, 0, 1.2),                          // rises and grows (87.75% to 100%) as it wipes on
  outline: between(tau, 0.5, 0.84),
  band: prog(tau, 0.62, 0.48),                           // rises from the card's bottom edge
  fill: interpolate(tau, [0.72, 1.0, 1.2, 1.4, 1.52], [0, 0.24, 0.45, 0.8, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),   // the measured darkening: slow, then quick
  // a plain black base under the band, there before the title's first letter: the original's letters typed over the
  // presenter's dark shirt, ours over the sofa and the windows (3.4:1 at round 1's visual review), so the card's black
  // stands at 0.65 behind them from the start (G6, G7; 11.9:1 at the least since), the band still rising over it
  base: 0.65 * prog(tau, CTA.series.drawnFromS, 0.16),   // cta.json: the card draws from here (pipeline.edit.cta)
  panel: between(tau, 1.08, 1.26),
  lines: prog(tau, 1.18, 0.16),
});
export const SERIES_CARD_SETTLED_S = CTA.series.settledS;   // from t0; the exit starts this long before t1
export const SERIES_CARD_GONE_S = CTA.series.goneS;         // the title shows from this after t0 to this before t1
// Its sound cue (S9, R158): the library's whoosh as the title starts; the stage places it (seconds on its clock).
export const seriesCardMoments = (o: SeriesCardLayer) => ({whoosh: o.t0 + CTA.series.whooshAtS});
// (a span t1 - t0 under 2 x settledS never settles, under 2 x goneS shows nothing: the stage keeps QuickArch03's 5.78)

export const SeriesCard: React.FC<{o: SeriesCardLayer}> = ({o}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const tau = Math.min(t - o.t0, o.t1 - t);
  if (tau <= 0) {
    return null;
  }
  const s = seriesCardState(tau);
  const {x, y, w, h} = o.box;
  const k = w / REF_W;
  const r = Math.round(RADIUS * w);
  const titleRise = (1 - s.titleMove) * 31 * k;          // 31 px on the original's frame
  const titleScale = 0.8775 + 0.1225 * s.titleMove;
  // the layout from the text: the title's line, a gap, the inner panel (its lines and padding), the rest split a
  // third above and two thirds below, where the band's gold shows (as on the original)
  const inset = Math.round(0.0275 * w);                  // the inner panel's side inset
  const textPad = Math.round(0.031 * w);                 // the episode's title inside the panel
  const titleLine = Math.round(TITLE_PX * 1.15), lineH = Math.round(LINE_PX * 1.12), padV = 14, gap = 10;
  const panelH = o.lines.length * lineH + 2 * padV;
  const top = Math.round(Math.max(0, h - titleLine - gap - panelH) * 0.35);
  const panelTop = top + titleLine + gap, panelBottom = h - panelTop - panelH;
  const pad = inset + textPad;                           // the title's left edge on the episode title's
  return (
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h}}>
      {/* the outline the card fills into: the original's faint grey frame with a light rule */}
      <div style={{position: 'absolute', inset: 0, borderRadius: r, opacity: s.outline,
        background: 'rgba(60, 60, 60, 0.22)', boxShadow: 'inset 0 0 0 2px rgba(255, 255, 255, 0.45)',
        transform: `scale(${0.94 + 0.06 * s.outline})`}} />
      <div style={{position: 'absolute', inset: 0, borderRadius: r, opacity: s.base, background: '#010100'}} />
      {/* the band alone (transparent core), rising from below, then the whole card filling in black over it */}
      <div style={{position: 'absolute', inset: 0, borderRadius: r, overflow: 'hidden', opacity: Math.min(1, 1.6 * s.band)}}>
        <div style={{position: 'absolute', inset: 0, background: grad(w, h, 'rgba(22, 1, 12, 0)', 0.55 * (1 - s.band))}} />
      </div>
      <div style={{position: 'absolute', inset: 0, borderRadius: r, opacity: s.fill, background: grad(w, h, '#010100', 0),
        boxShadow: 'inset 0 0 0 2px rgba(255, 255, 255, 0.4)'}} />
      {/* the inner panel: see-through dark over the band, dark enough for 7:1 (G6) */}
      <div style={{position: 'absolute', left: inset, right: inset, top: panelTop, bottom: panelBottom,
        borderRadius: Math.round(r * 0.45), background: 'rgba(16, 14, 14, 0.66)', opacity: s.panel,
        boxShadow: 'inset 0 0 0 1px rgba(255, 255, 255, 0.10)'}} />
      <div style={{position: 'absolute', left: inset, right: inset, top: panelTop, bottom: panelBottom,
        display: 'flex', flexDirection: 'column', justifyContent: 'center', paddingLeft: textPad,
        clipPath: `inset(${(1 - s.lines) * 100}% 0 0 0)`}}>
        <div style={{transform: `translateY(${(1 - s.lines) * 14 * k}px)`}}>
          {o.lines.map((l, i) => (
            <div key={i} style={{...CARD_FONT, fontSize: LINE_PX, lineHeight: `${Math.round(LINE_PX * 1.12)}px`,
              color: '#ffffff', whiteSpace: 'nowrap'}}>{l}</div>
          ))}
        </div>
      </div>
      {/* the series name: wipes on left to right while it rises and grows (its left edge stays put) */}
      <div style={{position: 'absolute', left: pad, top, transformOrigin: '0 50%',
        transform: `translateY(${titleRise}px) scale(${titleScale})`}}>
        <div style={{...CARD_FONT, fontSize: TITLE_PX, lineHeight: `${Math.round(TITLE_PX * 1.15)}px`, color: '#ffffff',
          whiteSpace: 'nowrap', clipPath: `inset(-10% ${(1 - s.title) * 100}% -10% 0)`}}>{o.title}</div>
      </div>
    </div>
  );
};

// The card for Section A (R242; David's line, 2026-10-17: "QS Journey 1: First dashboard", on one line), placed for
// the intro's first seconds: inside title-safe at the right (x to 1824), its bottom above the overlay lint's caption
// band (y 870; 19 px above the bottom-centre caption's 888), at least 12 px from the beard on both axes in those
// seconds (stage_review_r7's render; tools/remotion_ctas.py check measures it on any render), 821 x 230: as wide as a
// 56 px line needs, which only the room under the beard gives (beside the head, x 1100 on, is 724 wide).
export const SERIES_CARD_BOX: Box = CTA.series.box;
export const SERIES_CARD_SAMPLE: SeriesCardProps = {durationInFrames: 180, fps: 30, width: 1920, height: 1080,
  layer: {t0: 0.0, t1: CTA.series.spanS, title: 'Amazon Quick Series', lines: CTA.series.lines, box: SERIES_CARD_BOX}};

export const SeriesCardPreview: React.FC<SeriesCardProps> = ({still, layer}) => (
  <AbsoluteFill>
    {still ? <Img src={staticFile(still)} /> : null}
    <SeriesCard o={layer} />
  </AbsoluteFill>
);

