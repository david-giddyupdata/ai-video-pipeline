import React from 'react';
import {evolvePath} from '@remotion/paths';
import {Box, Edge, exitLeft, FONT, LAYOUT, look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog, rgba, SIZE,
  useEditTime, Variant, lh} from './kit';
import {TABLER, TablerName} from './vendor/tabler/icons';

// SourceFlow (R160, Section A round 6): a data source against a dataset, as plumbing. The source is a pipe from where
// the data lives (database, cloud, file); a dataset is the water drawn through it, prepared; one source feeds many
// datasets; an uploaded file keeps no connection. Each part arrives on its own spoken word (items' `at`, R80); every
// part keeps its place from the start, so the panel never changes size. Items, by key (any may be left out):
//   source   the source well and the pipe drawn on: "Heading: detail" ("Data source: the connection")
//   empty    a label under the empty pipe ("no data inside"), gone when the water flows
//   dataset  the first dataset card: "Heading: detail" ("Dataset: the data, prepared")
//   flow     water runs along the pipe and fills the first card (motion.composition.sourceFlow.flowS)
//   branch   the pipe branches to a second card, which fills too: its text is the card's heading ("Dataset")
//   first    the first card's detail changes to this text ("Every sale")
//   second   the second card's detail, from nothing to this text ("West region only")
//   upload   the bottom row: "Heading: detail" ("Uploaded file: no connection"): a file, two pipe ends with nothing
//            between them (the detail above the gap), and a dataset card of its own (the dataset item's heading)
// Sizes are R161's (text at least 56 px, icons 64 px, strokes at least 4 px). Variant (R140): dark on a light screen;
// the water is the variant's water colour. The pipe's labels are body text (cream on the dark variant): R179's 7:1
// against the opaque panel (round 8: in muted gold on the 96% panel they measured 3.3 to 4.3:1, David's note 1). Placement: a box in frame px (the panel centred in it), else centred in
// title-safe above the captions.

export type FlowItem = {key: string; text?: string; at: number};
export type SourceFlowLayer = {id: string; step?: string; layout: 'source_flow'; t0: number; t1: number;
  variant: Variant; items: FlowItem[]; sources?: TablerName[]; box?: Box; edge?: Edge};

const W = 1500;                 // the drawing, inside the panel's padding
const H = 600;
const WELL_W = 460;             // the source column
const WELL_H = 300;
const CARD_X = 860;             // the dataset cards' column: the pipe's 400 px between hold a 56 px label with room
const CARD_W = W - CARD_X;
const CARD_H = 168;
const ROW = [105, 315, 525];    // centre lines: the main pipe, the branch, the upload row
const BRANCH_X = 640;
const ICON = 64;
const PIPE = 44;                // the tube's outer width; its wall is 6 px each side (strokes at least 4, R161)
const WALL = 6;
const LABEL = SIZE.label;       // the pipe's own labels ("no data inside", "no connection"): R161's label size
// Line heights from the kit (R161: 1.15 of the size), as CSS and as numbers for placing.
const HEAD_LH = lh(SIZE.heading);
const BODY_LH = lh(SIZE.body);
const LABEL_LH = lh(LABEL);
const px = (cssPx: string) => parseFloat(cssPx);

const split = (text?: string) => {
  const m = /^(.*?): (.*)$/.exec(text ?? '');
  return m ? {head: m[1], detail: m[2]} : {head: text ?? '', detail: ''};
};

const Icon: React.FC<{name: TablerName; size: number; color: string; p?: number}> = ({name, size, color, p = 1}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{flex: 'none', overflow: 'visible'}}>
    {TABLER[name].map((d, i) => (
      <path key={i} d={d} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
        {...evolvePath(p, d)} />
    ))}
  </svg>
);

export const SourceFlow: React.FC<{o: SourceFlowLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const L = look(o.variant);
  const m = MOTION.composition.sourceFlow;
  const items = o.items ?? [];
  const at = (key: string) => items.find((it) => it.key === key)?.at;
  const item = (key: string) => items.find((it) => it.key === key);
  const shown = (key: string, dur = m.partS) => {
    const a = at(key);
    return a === undefined ? 0 : prog(t, a, dur);
  };
  // the panel opens on the first item's word; with no items at all, at t0 (Math.min of nothing is Infinity)
  const first = items.length ? Math.max(o.t0, Math.min(...items.map((it) => it.at))) : o.t0;
  const p = prog(t, first, MOTION.baseS);

  const src = split(item('source')?.text);
  const ds = split(item('dataset')?.text);
  const up = split(item('upload')?.text);
  const pSource = shown('source');
  const pPipe = shown('source', m.partS * 1.6);
  const pEmpty = shown('empty') * (1 - shown('flow', 0.3));
  const pCard1 = shown('dataset');
  const pFlow = shown('flow', m.flowS);
  const pBranch = shown('branch', m.partS * 1.4);
  const pBranchFlow = shown('branch', m.flowS + m.partS);
  const pUpload = shown('upload');
  const swap1 = shown('first', 0.35);
  const pSecond = shown('second', 0.35);

  const main = `M ${WELL_W} ${ROW[0]} L ${CARD_X} ${ROW[0]}`;
  const branch = `M ${BRANCH_X} ${ROW[0]} L ${BRANCH_X} ${ROW[1] - 40} Q ${BRANCH_X} ${ROW[1]} ${BRANCH_X + 40} ${ROW[1]} `
    + `L ${CARD_X} ${ROW[1]}`;
  const stubs = [`M ${WELL_W} ${ROW[2]} L ${WELL_W + 90} ${ROW[2]}`, `M ${CARD_X - 90} ${ROW[2]} L ${CARD_X} ${ROW[2]}`];
  const tube = (d: string, q: number, key: string) => (
    <g key={key}>
      <path d={d} fill="none" stroke={L.rule} strokeWidth={PIPE} strokeLinecap="butt" strokeLinejoin="round"
        {...evolvePath(q, d)} />
      <path d={d} fill="none" stroke={L.well} strokeWidth={PIPE - 2 * WALL} strokeLinecap="butt" strokeLinejoin="round"
        {...evolvePath(q, d)} />
    </g>
  );
  const water = (d: string, q: number, key: string) => q > 0 && (
    <path key={key} d={d} fill="none" stroke={L.water} strokeWidth={PIPE - 2 * WALL - 8} strokeLinecap="butt"
      strokeLinejoin="round" {...evolvePath(q, d)} />
  );

  const card = (y: number, q: number, head: string, detail: React.ReactNode, key: string) => (
    <div key={key} style={{position: 'absolute', left: CARD_X, top: y - CARD_H / 2, width: CARD_W, height: CARD_H,
      boxSizing: 'border-box', borderRadius: 12, border: `${LAYOUT.panel.ruleWidthPx + 2}px solid ${rgba(L.rule, 0.7)}`,
      background: L.well, overflow: 'hidden', opacity: q, transform: `scale(${0.94 + 0.06 * q})`}}>
      <div style={{position: 'relative', display: 'flex', alignItems: 'center', gap: 22, height: '100%',
        padding: '0 26px'}}>
        <Icon name="table" size={ICON} color={L.heading} p={q} />
        <div style={{whiteSpace: 'nowrap'}}>
          <div style={{...FONT.heading, fontSize: SIZE.heading, lineHeight: HEAD_LH, color: L.heading}}>{head}</div>
          {detail !== null && (
            <div style={{...FONT.body, fontSize: SIZE.body, lineHeight: BODY_LH, color: L.body, position: 'relative',
              height: px(BODY_LH)}}>{detail}</div>
          )}
        </div>
      </div>
    </div>
  );
  const swap = (from: string, to: string | undefined, q: number) => (
    <>
      <span style={{position: 'absolute', left: 0, top: 0, opacity: to ? 1 - q : 1}}>{from}</span>
      {to && <span style={{position: 'absolute', left: 0, top: 0, opacity: q}}>{to}</span>}
    </>
  );
  const sources = o.sources ?? ['database', 'cloud', 'file'];

  return (
    <Placed box={o.box} edge={o.edge} fallback="top">
      <div style={{opacity: p * exitLeft(t, o.t1, m.outS, fps), transform: `translateY(${(1 - p) * MOTION.risePx}px)`}}>
        <Panel variant={o.variant} style={{padding: '24px 36px'}}>
          <div style={{position: 'relative', width: W, height: H}}>
            <svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
              {pPipe > 0 && tube(main, pPipe, 'main')}
              {pBranch > 0 && tube(branch, pBranch, 'branch')}
              {pUpload > 0 && stubs.map((d, i) => tube(d, pUpload, `stub${i}`))}
              {water(main, Math.min(1, pFlow / 0.7), 'w-main')}
              {water(branch, Math.min(1, Math.max(0, (pBranchFlow - 0.35) / 0.65)), 'w-branch')}
            </svg>

            {/* the source well: where the data lives, then what the source is */}
            <div style={{position: 'absolute', left: 0, top: 20, width: WELL_W, height: WELL_H,
              boxSizing: 'border-box', padding: '26px 24px', borderRadius: 12, background: L.well,
              border: `${LAYOUT.panel.ruleWidthPx}px solid ${rgba(L.rule, 0.5)}`, opacity: pSource,
              transform: `translateX(${(1 - pSource) * -16}px)`}}>
              <div style={{display: 'flex', gap: 30, justifyContent: 'center'}}>
                {sources.map((name, i) => <Icon key={name} name={name} size={ICON} color={L.heading}
                  p={shown('source', m.partS + 0.1 * i)} />)}
              </div>
              <div style={{...FONT.heading, fontSize: SIZE.heading, lineHeight: HEAD_LH, color: L.heading, marginTop: 26,
                textAlign: 'center', whiteSpace: 'nowrap'}}>{src.head}</div>
              <div style={{...FONT.body, fontSize: SIZE.body, lineHeight: BODY_LH, color: L.body, textAlign: 'center',
                whiteSpace: 'nowrap'}}>{src.detail}</div>
            </div>

            {/* the empty pipe's label */}
            <div style={{position: 'absolute', left: WELL_W, width: CARD_X - WELL_W, top: ROW[0] + PIPE / 2 + 8,
              ...FONT.body, fontSize: LABEL, lineHeight: LABEL_LH, color: L.body, textAlign: 'center',
              whiteSpace: 'nowrap', opacity: pEmpty}}>{item('empty')?.text}</div>

            {card(ROW[0], pCard1, ds.head, swap(ds.detail, item('first')?.text, swap1), 'c1')}
            {card(ROW[1], shown('branch'), item('branch')?.text ?? ds.head,
              <span style={{opacity: pSecond}}>{item('second')?.text}</span>, 'c2')}

            {/* the upload row: a file, no connection, a dataset of its own */}
            <div style={{position: 'absolute', left: 0, top: ROW[2] - 70, width: WELL_W, height: 140,
              boxSizing: 'border-box', display: 'flex', alignItems: 'center', gap: 20, padding: '0 20px',
              borderRadius: 12, background: L.well, border: `${LAYOUT.panel.ruleWidthPx}px solid ${rgba(L.rule, 0.5)}`,
              opacity: pUpload, transform: `translateX(${(1 - pUpload) * -16}px)`}}>
              <Icon name="file" size={ICON} color={L.heading} p={pUpload} />
              <div style={{...FONT.body, fontSize: SIZE.body, lineHeight: BODY_LH, color: L.body,
                whiteSpace: 'nowrap'}}>{up.head}</div>
            </div>
            <div style={{position: 'absolute', left: WELL_W, width: CARD_X - WELL_W,
              top: ROW[2] - PIPE / 2 - px(LABEL_LH) - 4,
              ...FONT.body, fontSize: LABEL, lineHeight: LABEL_LH, color: L.body, textAlign: 'center',
              whiteSpace: 'nowrap', opacity: shown('upload', m.partS * 1.5)}}>{up.detail}</div>
            {card(ROW[2], pUpload, ds.head, null, 'c3')}
          </div>
        </Panel>
      </div>
    </Placed>
  );
};

export type SourceFlowProps = PreviewProps<SourceFlowLayer>;

// p1.02a (Section A, R160): "A data source is a connection ... An uploaded file, like ours, keeps no connection."
export const SOURCE_FLOW_SAMPLE: SourceFlowProps = {durationInFrames: 420, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'source-dataset', layout: 'source_flow', t0: 0.3, t1: 13.8, variant: 'dark', items: [
    {key: 'source', text: 'Data source: the connection', at: 0.6}, {key: 'empty', text: 'no data inside', at: 2.4},
    {key: 'dataset', text: 'Dataset: the data, prepared', at: 3.6}, {key: 'flow', at: 5.4},
    {key: 'branch', text: 'Dataset', at: 7.4}, {key: 'first', text: 'Every sale', at: 9.0},
    {key: 'second', text: 'West region only', at: 10.0}, {key: 'upload', text: 'Uploaded file: no connection', at: 11.4}]}};

export const SourceFlowPreview: React.FC<SourceFlowProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><SourceFlow o={layer} /></PreviewStage>
);
