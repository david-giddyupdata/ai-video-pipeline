import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Box, FONT, LAYOUT, lh, look, MOTION, prog, rgba, SIZE, TOKENS} from './kit';

// The highlight reel's graphics (R248; tools/reel.py): one transparent layer per beat, drawn over the reel's
// background (the stage's room, the narrator's still) and its footage, which Premiere places (V4: everything stays
// editable there). Four kinds:
//   frame  a stage of the chain ("1 Capture" ...): the header, a gold rule round the footage window (or a panel drawn
//          in it: the narration's words in time, the review's findings, the final's timeline), and a column with the
//          stage's key number, its tools and the rule behind it;
//   card   the stage layout's card (the roadmap card's box, R232), the narrator's still in the left third beside it;
//   board  a full-width card (the AIs and software, the numbers);
//   chip   a label over full-frame footage.
// The look is the overlays' dark variant (opaque brown panels, gold headings, cream body: 8.3:1 and 12.8:1, R179,
// R180), Segoe UI (Inter where it's missing), nothing under 56 px but the captions' own (R161). Times are seconds from
// the layer's first frame; every item eases in on its `at` (R131: one calm curve).

export type ReelRow = {text: string; at?: number; big?: string; quote?: boolean; muted?: boolean; small?: boolean;
  plain?: boolean; rule?: boolean; nowrap?: boolean; mark?: string; markAt?: number; upright?: boolean};
// upright: a rule row set upright (round 7b: a link, where an italic 1 reads as 7)
// mark: the row's first word(s), underlined as the narrator says them (markAt; R248 round 4, this reel only)   // plain: no bullet; rule: the italic gold line; nowrap: one line
// R248 round 3 (this reel only): a layer may fly in whole (enter), a card's title may fly in on its word (titleAt), a
// frame's tools build as they are said (toolsAt; pop: the livelier entry), and the presenter beat's pointer arrow
// points at the avatar, then flies and spins to its new corner (pointer, reel px and seconds).
export type ReelEnter = {at: number; dur: number};
// R248 round 5 (this reel only): the process line, nine numbered stops across the right two-thirds under the title
// bar; a stop's label is hidden before its beat, lit (the house chip) during it, grey after; the circles always show.
export type ReelProcess = {stops: string[]; current: number; box: Box; enterAt?: number; enterDur?: number;
  xs?: number[]; revealAt?: number; revealDur?: number; size?: number; inHeader?: boolean};
// (round 5 r2: inHeader: inside the title bar, its box relative to it; revealAt: drawn in left to right from then)
// a card's or board's title bar:
export type ReelHead = {num: number; name: string; what: string; box?: Box};   // xs: each stop's centre in the band, spaced by its label's width (reel.process_state)
// fadeIn (any layer): the whole layer fades in over this many seconds (the far side of a joined dissolve, J1)
export type ReelPointer = {x0: number; y0: number; a0: number; x1: number; y1: number; a1: number; at: number;
  fly0: number; fly1: number; gone: number; len: number; stroke: number; head: number; color: string; turns: number;
  edge?: string; len1?: number};   // len1: its length once landed (round 5: short where it starts, long where it lands)   // edge: a filled arrow (round 4: the frames' tan, a dark grey border), color "rule" = that tan
export type Word = {w: string; start: number; end: number};
export type ReelPanel =
  | {type: 'karaoke'; at: number; words: Word[]; note: string; hideAt?: number}   // hideAt: fades out (footage under)
  | {type: 'bars'; at: number; title: string; rows: {label: string; n: number}[]; note?: string; showN?: boolean}
  | {type: 'timeline'; at: number; dur: number; tracks: {name: string; clips: [number, number][]}[];
      markers: number[]; note: string};
// image: a picture in the window (round 5 r2: a screenshot of the final's Premiere timeline, from a copy of its project)
export type ReelImage = {type: 'image'; src: string; at?: number; note?: string};
type AnyPanel = ReelPanel | ReelImage;
export type ReelWindow = {box: Box; label?: string; at?: number; until?: number};   // the label's time
export type ReelLayer =
  | {kind: 'frame'; num: number; name: string; what: string; keyBig: string; keySmall: string; tools: string[];
      rule: string; windows: ReelWindow[]; panel?: AnyPanel; toolsAt?: number[]; keyAt?: number; ruleAt?: number;
      pop?: boolean; pointer?: ReelPointer; enter?: ReelEnter; fadeIn?: number; process?: ReelProcess;
      column?: Box; fit?: boolean; header?: Box}
  | {kind: 'card'; title: string; rows: ReelRow[]; box?: Box; stages?: string[]; stagesAt?: number; titleAt?: number;
      enter?: ReelEnter; fadeIn?: number; process?: ReelProcess; num?: number; compact?: boolean; fit?: boolean;
      head?: ReelHead}
  | {kind: 'board'; title: string; columns?: {head: string; rows: ReelRow[]}[]; chips?: string[]; footer?: ReelRow;
      enter?: ReelEnter; fadeIn?: number; process?: ReelProcess; box?: Box; num?: number; compact?: boolean;
      head?: ReelHead}
  | {kind: 'chip'; title: string; text?: string; at: number; box: Box; fadeIn?: number; process?: ReelProcess};

const L = look('dark');
const ACC = TOKENS.color.accent;          // shapes only (R180)
const IN_S = 0.4;
const RISE = MOTION.risePx;
const PANEL: React.CSSProperties = {position: 'absolute', background: rgba(L.panel, 1), boxSizing: 'border-box',
  border: `${LAYOUT.panel.ruleWidthPx}px solid ${L.rule}`, borderRadius: LAYOUT.panel.radiusPx,
  boxShadow: LAYOUT.panel.shadow};
const BODY = SIZE.body;                   // 56
const BAL = {textWrap: 'balance'} as React.CSSProperties;   // balanced breaks, no one-word last line (V9)
const HEAD = SIZE.heading;                // 60
const SIZE_SMALL = TOKENS.type.minPx;     // 48: the floor (R161), for a small-print line only

// the house's places for a reel frame (1920 x 1080; title-safe 96 / 54, captions from y 870)
export const REEL = {
  header: {x: 96, y: 54, w: 1728, h: 104},
  window: {x: 96, y: 182, w: 1024, h: 576},
  column: {x: 1144, y: 182, w: 680, h: 576},
  card: {x: 720, y: 60, w: 1104, h: 750},          // the stage's card (stage_plan's card box)
  board: {x: 96, y: 54, w: 1728, h: 796},
};

const useT = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return frame / fps;
};

const lin = (t: number, at: number, dur: number) => Math.min(1, Math.max(0, (t - at) / Math.max(1e-6, dur)));
const backOut = (x: number, c1 = 1.70158) => 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2;   // overshoots, settles
const inOut = (x: number) => (x < 0.5 ? 4 * x ** 3 : 1 - (-2 * x + 2) ** 3 / 2);

// A whole layer flying in from the right, turning and growing into place (the open into the main part, R248 r3).
const enterStyle = (t: number, e?: ReelEnter, fadeIn?: number): React.CSSProperties => {
  if (!e) return fadeIn ? {opacity: lin(t, 0, fadeIn)} : {};
  const x = lin(t, e.at, e.dur), k = backOut(x, 1.2);
  return {transform: `translate(${(1 - k) * 1500}px, ${(1 - k) * -90}px) rotate(${(1 - k) * 12}deg) scale(${0.55 + 0.45 * k})`,
    opacity: Math.min(1, lin(t, e.at, e.dur * 0.35)), transformOrigin: '60% 50%'};
};

// A title flying in on its word: in from the left, past its place and back.
const Fly: React.FC<{t: number; at?: number; style?: React.CSSProperties; children: React.ReactNode}> =
  ({t, at, style, children}) => {
    if (at === undefined) return <div style={style}>{children}</div>;
    const k = backOut(lin(t, at, 0.6), 1.6);
    return <div style={{opacity: lin(t, at, 0.15), transform: `translateX(${(1 - k) * -700}px) rotate(${(1 - k) * -6}deg)`,
      transformOrigin: 'left center', ...style}}>{children}</div>;
  };

// The tools beat's livelier entry: in from the right, spun and scaled up past full size, a gold ring flashing out.
const Pop: React.FC<{t: number; at: number; children: React.ReactNode}> = ({t, at, children}) => {
  const x = lin(t, at, 0.5), k = backOut(x, 1.8);
  const ring = lin(t, at + 0.25, 0.55);
  return (
    <div style={{position: 'relative', opacity: Math.min(1, x * 4),
      transform: `translateX(${(1 - k) * 160}px) scale(${0.2 + 0.8 * k}) rotate(${(1 - k) * -24}deg)`,
      transformOrigin: 'left center'}}>
      {t >= at + 0.25 && ring < 1 ? <div style={{position: 'absolute', left: -14, right: -14, top: -6, bottom: -6,
        border: `4px solid ${L.heading}`, borderRadius: 14, opacity: 1 - ring, transform: `scale(${1 + 0.25 * ring})`}} /> : null}
      {children}
    </div>
  );
};

const GREY = '#bababa';       // a passed stop's label and circle: 7.1:1 on the panel

const Process: React.FC<{t: number; p: ReelProcess; bare?: boolean}> = ({t, p, bare}) => {
  const b = p.box, n = p.stops.length, PL = 90, PR = 74, cy = 21, R = 17, FS = p.size ?? 26;
  const gap = (b.w - PL - PR) / (n - 1);
  const xOf = (i: number) => p.xs?.[i] ?? PL + i * gap;
  const k = p.enterAt === undefined ? 1 : backOut(lin(t, p.enterAt, p.enterDur ?? 0.9), 1.2);
  const op = p.enterAt === undefined ? 1 : Math.min(1, lin(t, p.enterAt, (p.enterDur ?? 0.9) * 0.35));
  const rv0 = p.revealAt === undefined ? 1 : inOut(lin(t, p.revealAt, p.revealDur ?? 0.9));   // drawn in left to right
  const keep = Math.min(1, (xOf(0) + 90) / b.w);                // (stop 1 and its chip whole from the start)
  const rv = keep + (1 - keep) * rv0;
  return (
    <div style={{...(bare ? {position: 'absolute'} : PANEL), ...place(b), opacity: op,
      transform: `translateX(${(1 - k) * 1300}px)`, clipPath: rv < 1 ? `inset(0 ${(1 - rv) * 100}% 0 0)` : undefined}}>
      <div style={{position: 'absolute', left: xOf(0), width: xOf(n - 1) - xOf(0), top: cy - 2, height: 4, background: L.rule,
        opacity: 0.55}} />
      {p.stops.map((name, i) => {
        const x = xOf(i), past = i < p.current, now = i === p.current;
        return (
          <React.Fragment key={i}>
            <div style={{position: 'absolute', left: x - R, top: cy - R, width: 2 * R, height: 2 * R, borderRadius: R,
              boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: now ? L.heading : past ? GREY : L.panel,
              border: now ? `4px solid ${ACC}` : past ? 'none' : `3px solid ${L.body}`,
              ...FONT.heading, fontSize: 21, lineHeight: 1, color: now || past ? L.panel : L.body}}>{i + 1}</div>
            {i <= p.current ? (
              <div style={{position: 'absolute', left: x, top: cy + R + 3, transform: 'translateX(-50%)',
                whiteSpace: 'nowrap', ...FONT.heading, fontSize: FS, lineHeight: `${FS + 3}px`,
                padding: now ? '0 7px' : 0, borderRadius: 6,
                background: now ? L.chip : 'transparent', color: now ? L.chipText : GREY}}>{name}</div>
            ) : null}
          </React.Fragment>
        );
      })}
    </div>
  );
};

// A numbered title (the process line's number for a card or a board, R248 round 5).
const Numbered: React.FC<{num?: number; size: number; children: React.ReactNode}> = ({num, size, children}) =>
  num === undefined ? <>{children}</> : (
    <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
      <div style={{width: size, height: size, flex: `0 0 ${size}px`, borderRadius: size / 2, background: L.heading,
        color: L.panel, display: 'flex', alignItems: 'center', justifyContent: 'center', ...FONT.heading,
        fontSize: size * 0.72, lineHeight: 1}}>{num}</div>
      {children}
    </div>
  );

const Rise: React.FC<{t: number; at?: number; style?: React.CSSProperties; children: React.ReactNode}> =
  ({t, at = 0, style, children}) => {
    const p = prog(t, at, MOTION.baseS);
    return <div style={{opacity: p, transform: `translateY(${(1 - p) * RISE}px)`, ...style}}>{children}</div>;
  };

const place = (b: Box): React.CSSProperties => ({left: b.x, top: b.y, width: b.w, height: b.h});

const Header: React.FC<{t: number; num: number; name: string; what: string; box?: Box; process?: ReelProcess}> =
  ({t, num, name, what, box, process}) => {
    const b = box ?? REEL.header;
    const row = process ? process.box.y : b.h;                // the title row; the line under it (round 5 r2)
    return (
      <div style={{...PANEL, ...place(b), opacity: prog(t, 0, IN_S)}}>
        <div style={{position: 'absolute', left: 0, top: 0, right: 0, height: row, display: 'flex', alignItems: 'center',
          padding: '0 36px', gap: 28}}>
          <div style={{width: 76, height: 76, flex: '0 0 76px', borderRadius: 38, background: L.heading, color: L.panel,
            display: 'flex', alignItems: 'center', justifyContent: 'center', ...FONT.heading, fontSize: HEAD, lineHeight: 1}}>
            {num}</div>
          <div style={{...FONT.heading, fontSize: 64, color: L.heading, whiteSpace: 'nowrap'}}>{name}</div>
          <div style={{width: 4, height: 64, background: L.rule, opacity: 0.6}} />
          <div style={{...FONT.body, fontSize: BODY, color: L.body, whiteSpace: 'nowrap'}}>{what}</div>
        </div>
        {process ? <Process t={t} p={process} bare /> : null}
      </div>
    );
  };

const Column: React.FC<{t: number; keyBig: string; keySmall: string; tools: string[]; rule: string;
  toolsAt?: number[]; keyAt?: number; ruleAt?: number; pop?: boolean; box?: Box; fit?: boolean}> =
  ({t, keyBig, keySmall, tools, rule, toolsAt, keyAt, ruleAt, pop, box, fit}) => {
    const tool = (x: string) => (
      <div style={{display: 'flex', alignItems: 'flex-start', gap: 18, ...FONT.heading, fontSize: BODY,
        lineHeight: lh(BODY, 1.0), color: L.body, ...BAL}}>
        <div style={{width: 16, height: 16, flex: '0 0 16px', background: L.heading, transform: 'rotate(45deg)',
          marginTop: (Number.parseInt(lh(BODY, 1.0), 10) - 16) / 2}} />
        {x}
      </div>
    );
    return (
      <div style={{...PANEL, ...place(box ?? REEL.column), ...(fit ? {height: 'auto'} : {}),
        padding: '16px 32px 16px', display: 'flex', flexDirection: 'column', opacity: prog(t, 0.15, IN_S)}}>
        <Rise t={t} at={keyAt ?? 0.15}>
          <div style={{...FONT.heading, fontSize: 72, lineHeight: lh(72, 1.02), color: L.heading}}>{keyBig}</div>
          <div style={{...FONT.body, fontSize: BODY, lineHeight: lh(BODY, 1.04), color: L.body, ...BAL}}>{keySmall}</div>
        </Rise>
        <div style={{height: 3, flex: '0 0 3px', background: L.rule, opacity: 0.5 * prog(t, toolsAt?.[0] ?? 0.15, IN_S),
          margin: '10px 0 8px'}} />
        {tools.map((x, i) => {
          const at = toolsAt?.[i];
          if (at === undefined) return <div key={i}>{tool(x)}</div>;
          return pop ? <Pop key={i} t={t} at={at}>{tool(x)}</Pop> : <Rise key={i} t={t} at={at}>{tool(x)}</Rise>;
        })}
        {fit ? null : <div style={{flex: 1}} />}
        <div style={{height: 3, flex: '0 0 3px', background: L.rule, opacity: 0.5 * prog(t, ruleAt ?? 0.15, IN_S),
          margin: fit ? '12px 0 10px' : '0 0 10px'}} />
        {/* (the italic rule keeps its 1.08 leading: two lines of it read better a little apart) */}
        <Rise t={t} at={ruleAt ?? 0.15}>
          <div style={{...FONT.body, fontSize: BODY, lineHeight: lh(BODY, 1.08), color: L.heading, fontStyle: 'italic', ...BAL}}>
            {rule}
          </div>
        </Rise>
      </div>
    );
  };

// The tutorial's own overview arrow (its marks' look: a stroke and a large filled head), pointing at the avatar, then
// flying on an arc and spinning to point at it in its new corner as it fades in there.
const Pointer: React.FC<{t: number; p: ReelPointer}> = ({t, p}) => {
  if (t < p.at) return null;
  const u = inOut(lin(t, p.fly0, p.fly1 - p.fly0));
  const x = p.x0 + (p.x1 - p.x0) * u, y = p.y0 + (p.y1 - p.y0) * u - Math.sin(Math.PI * u) * 140;
  const d = (((p.a1 - p.a0) % 360) + 360) % 360 + 360 * p.turns;    // the heading change plus whole turns (Fable r3 F2)
  const a = p.a0 + d * u;
  const k = backOut(lin(t, p.at, 0.4), p.edge ? 1.0 : 2.2);   // the big arrow's pop peaks at 1.04, not 1.15 (J3)
  const op = Math.min(1, lin(t, p.at, 0.12)) * (1 - lin(t, p.gone, 0.3));
  if (op <= 0) return null;
  const hw = p.head * 0.6;
  const len = p.len + ((p.len1 ?? p.len) - p.len) * u;
  const fill = p.color === 'rule' ? L.rule : p.color;
  const w2 = p.stroke / 2;
  return (
    <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', opacity: op,
      filter: p.edge ? 'drop-shadow(6px 9px 8px rgba(0,0,0,0.55))' : 'drop-shadow(2px 3px 3px rgba(0,0,0,0.45))'}}>
      <g transform={`translate(${x} ${y}) rotate(${a}) scale(${k})`}>
        {p.edge
          ? <polygon points={`${-len},${-w2} ${-p.head},${-w2} ${-p.head},${-hw} 0,0 ${-p.head},${hw} ${-p.head},${w2} ${-len},${w2}`}
              fill={fill} stroke={p.edge} strokeWidth={4} strokeLinejoin="round" />
          : <>
              <line x1={-p.len} y1={0} x2={-p.head + 2} y2={0} stroke={fill} strokeWidth={p.stroke} strokeLinecap="round" />
              <polygon points={`0,0 ${-p.head},${-hw} ${-p.head},${hw}`} fill={fill} />
            </>}
      </g>
    </svg>
  );
};

// A footage window: Premiere puts the clip in the box; this draws its gold rule and its label chip.
const Win: React.FC<{t: number; w: ReelWindow}> = ({t, w}) => {
  const b = w.box;
  return (
    <>
      <div style={{position: 'absolute', left: b.x - 4, top: b.y - 4, width: b.w + 8, height: b.h + 8,
        boxSizing: 'border-box', border: `4px solid ${L.rule}`, borderRadius: 6, opacity: prog(t, 0, IN_S)}} />
      {w.label && t >= (w.at ?? 0) && t < (w.until ?? Infinity) ? (
        <div style={{position: 'absolute', left: b.x, top: b.y + b.h - 2,
          opacity: prog(t, Math.max(0.2, w.at ?? 0), IN_S)}}>
          <div style={{background: L.panel, border: `2px solid ${L.rule}`, borderRadius: '0 0 10px 10px',
            padding: '2px 20px 6px', ...FONT.heading, fontSize: BODY, lineHeight: lh(BODY), color: L.heading}}>
            {w.label}
          </div>
        </div>
      ) : null}
    </>
  );
};

const Karaoke: React.FC<{t: number; p: Extract<ReelPanel, {type: 'karaoke'}>; box: Box}> = ({t, p, box}) => (
  <div style={{position: 'absolute', ...place(box), background: L.body, borderRadius: 6, padding: '56px 64px',
    boxSizing: 'border-box', display: 'flex', flexDirection: 'column', justifyContent: 'center',
    opacity: prog(t, 0, IN_S) * (p.hideAt === undefined ? 1 : 1 - prog(t, p.hideAt, IN_S))}}>
    <div style={{display: 'flex', flexWrap: 'wrap', columnGap: '0.3em', rowGap: 18, ...FONT.heading, fontSize: 84,
      lineHeight: lh(84, 1.1), color: L.panel}}>
      {p.words.map((w, i) => {
        const on = prog(t, p.at + w.start, Math.max(0.08, Math.min(0.3, w.end - w.start)));
        return (
          <span key={i} style={{position: 'relative', display: 'inline-block', whiteSpace: 'nowrap'}}>
            {w.w}
            <span style={{position: 'absolute', left: 0, right: 0, bottom: -8, height: 8, background: ACC,
              transformOrigin: 'left', transform: `scaleX(${on})`}} />
          </span>
        );
      })}
    </div>
    <div style={{...FONT.body, fontSize: BODY, lineHeight: lh(BODY), color: L.panel, marginTop: 48}}>{p.note}</div>
  </div>
);

const Bars: React.FC<{t: number; p: Extract<ReelPanel, {type: 'bars'}>; box: Box}> = ({t, p, box}) => {
  const max = Math.max(1, ...p.rows.map((r) => r.n));
  const labelW = p.showN === false ? 600 : 520;
  return (
    <div style={{...PANEL, ...place(box), padding: '34px 44px', display: 'flex', flexDirection: 'column',
      opacity: prog(t, 0, IN_S)}}>
      <div style={{...FONT.heading, fontSize: HEAD, lineHeight: lh(HEAD), color: L.heading, marginBottom: 22, ...BAL}}>
        {p.title}
      </div>
      {p.rows.map((r, i) => {
        const g = prog(t, p.at + i * 0.35, 0.6);
        return (
          <div key={i} style={{display: 'flex', alignItems: 'center', height: 80, opacity: prog(t, p.at + i * 0.35, 0.3)}}>
            <div style={{width: labelW, ...FONT.body, fontSize: BODY, color: L.body, whiteSpace: 'nowrap'}}>{r.label}</div>
            <div style={{height: 44, width: (box.w - 88 - labelW - (p.showN === false ? 0 : 110)) * (r.n / max) * g,
              background: L.heading,
              borderRadius: 4}} />
            {p.showN === false ? null
              : <div style={{...FONT.heading, fontSize: BODY, color: L.heading, marginLeft: 18}}>{r.n}</div>}
          </div>
        );
      })}
      {p.note ? <div style={{...FONT.body, fontSize: BODY, lineHeight: lh(BODY), color: L.body, marginTop: 'auto'}}>
        {p.note}</div> : null}
    </div>
  );
};

const Timeline: React.FC<{t: number; p: Extract<ReelPanel, {type: 'timeline'}>; box: Box}> = ({t, p, box}) => {
  const nameW = 390, padX = 40;
  const rowH = Math.min(78, Math.floor((box.h - 60 - 40 - 84) / Math.max(1, p.tracks.length)));   // fits its box (r5)
  const laneW = box.w - 2 * padX - nameW;
  const x = (s: number) => (s / p.dur) * laneW;
  return (
    <div style={{...PANEL, ...place(box), padding: `30px ${padX}px`, opacity: prog(t, 0, IN_S)}}>
      <div style={{position: 'absolute', left: padX, top: 28, ...FONT.heading, fontSize: SIZE_SMALL, lineHeight: '40px',
        color: L.body, whiteSpace: 'nowrap'}}>Markers</div>
      <div style={{position: 'relative', marginLeft: nameW, height: 40}}>
        {p.markers.map((m, i) => (
          <div key={i} style={{position: 'absolute', left: x(m) - 11, top: 4, width: 22, height: 30,
            background: ACC, clipPath: 'polygon(0 0, 100% 0, 100% 62%, 50% 100%, 0 62%)',
            opacity: prog(t, p.at + 0.4 + (m / p.dur) * 1.2, 0.2)}} />
        ))}
      </div>
      {p.tracks.map((tr, i) => (
        <div key={i} style={{display: 'flex', alignItems: 'center', height: rowH}}>
          <div style={{width: nameW, ...FONT.heading, fontSize: BODY, color: L.body, whiteSpace: 'nowrap'}}>{tr.name}</div>
          <div style={{position: 'relative', width: laneW, height: Math.min(52, rowH - 6), background: L.well,
            borderRadius: 4}}>
            {tr.clips.map(([a, b], k) => {
              const g = prog(t, p.at + (a / p.dur) * 1.2, 0.3);
              return <div key={k} style={{position: 'absolute', left: x(a), width: Math.max(4, x(b) - x(a)), top: 4,
                height: Math.max(4, Math.min(52, rowH - 6) - 8), background: L.heading, opacity: g, borderRadius: 3,
                boxShadow: `inset -2px 0 0 ${L.panel}`}} />;
            })}
          </div>
        </div>
      ))}
      <div style={{...FONT.body, fontSize: BODY, lineHeight: lh(BODY), color: L.body, marginTop: 18}}>{p.note}</div>
    </div>
  );
};

const Rows: React.FC<{t: number; rows: ReelRow[]; size?: number; bigPx?: number; gap?: number}> =
  ({t, rows, size = BODY, bigPx = 84, gap = 22}) => (
  <>
    {rows.map((r, i) => (
      <Rise key={i} t={t} at={r.at ?? 0.3 + i * 0.25} style={{display: 'flex', alignItems: r.big ? 'baseline' : 'flex-start',
        gap: 22, marginTop: gap}}>
        {r.big ? <div style={{...FONT.heading, fontSize: bigPx, lineHeight: lh(bigPx, 1.0), color: L.heading,
          whiteSpace: 'nowrap', flex: '0 0 auto'}}>{r.big}</div>
          : r.small || r.plain || r.rule ? null : <div style={{width: 18, height: 18, flex: '0 0 18px', background: L.heading,
            transform: 'rotate(45deg)', alignSelf: 'flex-start', marginTop: (Number.parseInt(lh(size), 10) - 18) / 2}} />}
        <div style={{...FONT.body, fontSize: r.small ? SIZE_SMALL : size, lineHeight: lh(r.small ? SIZE_SMALL : size),
          color: r.rule ? L.heading : L.body, fontStyle: (r.quote || r.rule) && !r.upright ? 'italic' : 'normal',
          ...(r.nowrap ? {whiteSpace: 'nowrap'} : BAL)}}>
          {r.mark && r.text.startsWith(r.mark) ? <>
            <span style={{position: 'relative', display: 'inline-block'}}>
              {r.mark}
              <span style={{position: 'absolute', left: 0, right: 0, bottom: -2, height: 6, background: ACC,
                borderRadius: 3, transformOrigin: 'left', transform: `scaleX(${prog(t, r.markAt ?? Infinity, 0.45)})`}} />
            </span>{r.text.slice(r.mark.length)}</> : r.text}
        </div>
      </Rise>
    ))}
  </>
);

// A written procedure's stages (CREATE_A_VIDEO.md's 0 to 12), numbered in two columns, appearing in order.
const Stages: React.FC<{t: number; stages: string[]; at: number}> = ({t, stages, at}) => {
  const half = Math.ceil(stages.length / 2);
  return (
    <div style={{display: 'grid', gridTemplateRows: `repeat(${half}, auto)`, gridAutoFlow: 'column', columnGap: 40,
      rowGap: 2, marginTop: 18}}>
      {stages.map((x, i) => (
        <Rise key={i} t={t} at={at + i * 0.12} style={{display: 'flex', alignItems: 'baseline', gap: 14,
          ...FONT.body, fontSize: BODY, lineHeight: lh(BODY, 1.08), color: L.body, whiteSpace: 'nowrap'}}>
          <span style={{...FONT.heading, color: L.heading, minWidth: 54, textAlign: 'right'}}>{i}</span>{x}
        </Rise>
      ))}
    </div>
  );
};

// Names as chips, several to a row (the software board).
const Chips: React.FC<{t: number; chips: string[]}> = ({t, chips}) => (
  <div style={{display: 'flex', flexWrap: 'wrap', gap: '26px 28px', marginTop: 40}}>
    {chips.map((x, i) => (
      <Rise key={i} t={t} at={0.3 + i * 0.1} style={{background: L.well, border: `2px solid ${L.rule}`, borderRadius: 12,
        padding: '10px 30px', ...FONT.heading, fontSize: HEAD, lineHeight: lh(HEAD), color: L.body}}>{x}</Rise>
    ))}
  </div>
);

export const ReelLayerView: React.FC<{o: ReelLayer}> = ({o}) => {
  const t = useT();
  if (o.kind === 'frame') {
    const main = o.windows[0]?.box ?? REEL.window;
    const body = (
      <AbsoluteFill style={enterStyle(t, o.enter, o.fadeIn)}>
        <Header t={t} num={o.num} name={o.name} what={o.what} box={o.header}
          process={o.process?.inHeader && o.header ? o.process : undefined} />
        {o.panel?.type === 'karaoke' ? <Karaoke t={t} p={o.panel} box={main} /> : null}
        {o.panel?.type === 'bars' ? <Bars t={t} p={o.panel} box={main} /> : null}
        {o.panel?.type === 'timeline' ? <Timeline t={t} p={o.panel} box={main} /> : null}
        {o.panel?.type === 'image' ? (
          <div style={{...PANEL, ...place(main), padding: 10, opacity: prog(t, o.panel.at ?? 0, IN_S), display: 'flex',
            flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8}}>
            <Img src={staticFile(o.panel.src)} style={{maxWidth: '100%', maxHeight: o.panel.note ? '86%' : '100%',
              objectFit: 'contain', borderRadius: 4}} />
            {o.panel.note ? <div style={{...FONT.body, fontSize: SIZE_SMALL, lineHeight: lh(SIZE_SMALL), color: L.body,
              whiteSpace: 'nowrap'}}>
              {o.panel.note}</div> : null}
          </div>) : null}
        {o.panel && o.panel.type !== 'karaoke' ? null : o.windows.map((w, i) => <Win key={i} t={t} w={w} />)}
        <Column t={t} keyBig={o.keyBig} keySmall={o.keySmall} tools={o.tools} rule={o.rule} toolsAt={o.toolsAt}
          keyAt={o.keyAt} ruleAt={o.ruleAt} pop={o.pop} box={o.column} fit={o.fit} />
        {o.pointer ? <Pointer t={t} p={o.pointer} /> : null}
      </AbsoluteFill>
    );
    return o.process && !(o.process.inHeader && o.header)
      ? <AbsoluteFill>{body}<Process t={t} p={o.process} /></AbsoluteFill> : body;
  }
  if (o.kind === 'card') {
    const b = o.box ?? REEL.card;
    const T = o.compact ? 64 : 72;
    const card = (
      <AbsoluteFill style={enterStyle(t, o.enter, o.fadeIn)}>
        <div style={{...PANEL, left: b.x, top: b.y, width: b.w, minHeight: o.fit ? undefined : b.h,
          padding: o.compact ? '28px 48px 32px' : '40px 56px', opacity: prog(t, 0, IN_S)}}>
          <Fly t={t} at={o.titleAt}>
            <Numbered num={o.num} size={64}>
              <div style={{...FONT.heading, fontSize: T, lineHeight: lh(T, 1.1), color: L.heading, ...BAL,
                whiteSpace: 'pre-line'}}>{o.title}</div>
            </Numbered>
            <div style={{height: 4, width: 300, background: L.rule, margin: o.compact ? '14px 0 2px' : '22px 0 6px'}} />
          </Fly>
          {o.stages && o.stages.length ? <Stages t={t} stages={o.stages} at={o.stagesAt ?? 0.4} /> : null}
          <Rows t={t} rows={o.rows} bigPx={o.compact ? 64 : 72} gap={o.compact ? 10 : 18} />
        </div>
      </AbsoluteFill>
    );
    if (o.head) return <AbsoluteFill>{card}<AbsoluteFill style={enterStyle(t, o.enter, o.fadeIn)}>
      <Header t={t} {...o.head} process={o.process?.inHeader ? o.process : undefined} /></AbsoluteFill>
      {o.process && !o.process.inHeader ? <Process t={t} p={o.process} /> : null}</AbsoluteFill>;
    return o.process ? <AbsoluteFill>{card}<Process t={t} p={o.process} /></AbsoluteFill> : card;
  }
  if (o.kind === 'board') {
    const b = o.box ?? REEL.board;
    const T = o.compact ? 64 : 72;
    const board = (
      <AbsoluteFill style={enterStyle(t, o.enter, o.fadeIn)}>
        <div style={{...PANEL, ...place(b), padding: o.compact ? '30px 48px 26px' : '30px 56px 34px', display: 'flex',
          flexDirection: 'column', opacity: prog(t, 0, IN_S), overflow: 'hidden'}}>
          <Numbered num={o.num} size={64}>
            <div style={{...FONT.heading, fontSize: T, lineHeight: lh(T, 1.1), color: L.heading, ...BAL}}>{o.title}</div>
          </Numbered>
          {o.chips ? <Chips t={t} chips={o.chips} /> : null}
          <div style={{display: 'flex', gap: 64, marginTop: 10}}>
            {(o.columns ?? []).map((c, i) => (
              <div key={i} style={{flex: 1}}>
                <Rise t={t} at={0.2 + i * 0.2} style={{...FONT.heading, fontSize: HEAD, lineHeight: lh(HEAD),
                  color: L.heading, borderBottom: `3px solid ${rgba(L.rule, 0.6)}`, paddingBottom: 8, marginTop: 18}}>
                  {c.head}
                </Rise>
                <Rows t={t} rows={c.rows} bigPx={o.compact ? 64 : 72} gap={o.compact ? 8 : 16} />
              </div>
            ))}
          </div>
          {o.footer ? <div style={{marginTop: 'auto', borderTop: `3px solid ${rgba(L.rule, 0.6)}`}}>
            <Rows t={t} rows={[o.footer]} bigPx={o.compact ? 64 : 72} gap={o.compact ? 8 : 14} /></div> : null}
        </div>
      </AbsoluteFill>
    );
    if (o.head) return <AbsoluteFill>{board}<AbsoluteFill style={enterStyle(t, o.enter, o.fadeIn)}>
      <Header t={t} {...o.head} process={o.process?.inHeader ? o.process : undefined} /></AbsoluteFill>
      {o.process && !o.process.inHeader ? <Process t={t} p={o.process} /> : null}</AbsoluteFill>;
    return o.process ? <AbsoluteFill>{board}<Process t={t} p={o.process} /></AbsoluteFill> : board;
  }
  return (
    <AbsoluteFill style={enterStyle(t, undefined, o.fadeIn)}>
      <Rise t={t} at={o.at} style={{...PANEL, left: o.box.x, top: o.box.y, width: o.box.w, padding: '20px 36px',
        display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
        <div style={{...FONT.heading, fontSize: HEAD, lineHeight: lh(HEAD), color: L.heading}}>{o.title}</div>
        {o.text ? <div style={{...FONT.body, fontSize: BODY, lineHeight: lh(BODY), color: L.body}}>{o.text}</div> : null}
      </Rise>
    </AbsoluteFill>
  );
};

// The render's props: the layer, and for check stills a background (in the public dir) and footage stills placed in
// the windows, as Premiere will place the clips.
export type ReelProps = {durationInFrames: number; fps: number; width: number; height: number; layer: ReelLayer;
  still?: string; narrator?: string; shots?: {src: string; box: Box}[]};

export const Reel: React.FC<ReelProps> = ({layer, still, narrator, shots}) => (
  <AbsoluteFill>
    {still ? <Img src={staticFile(still)} style={{position: 'absolute', width: 1920, height: 1080}} /> : null}
    {narrator ? <Img src={staticFile(narrator)} style={{position: 'absolute', width: 1920, height: 1080}} /> : null}
    {(shots ?? []).map((s, i) => <Img key={i} src={staticFile(s.src)} style={{position: 'absolute', ...place(s.box)}} />)}
    <ReelLayerView o={layer} />
  </AbsoluteFill>
);

export const REEL_SAMPLE: ReelProps = {durationInFrames: 90, fps: 30, width: 1920, height: 1080,
  layer: {kind: 'frame', num: 1, name: 'Capture', what: 'An AI agent drives the browser', keyBig: '1 take',
    keySmall: '17 min 48 s, nobody on the mouse', tools: ['Claude Code', 'Playwright', 'OBS Studio'],
    rule: 'Nothing is drawn on the recording.', windows: [{box: REEL.window}]}};
