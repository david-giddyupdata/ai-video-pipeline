import React from 'react';
import {measureText} from '@remotion/layout-utils';
import {ACCENT, Box, Edge, exitLeft, FONT, LAYOUT, look, Look, MOTION, Panel, Placed, PreviewProps, PreviewStage, prog,
  rgba, SIZE, spaced, useEditTime, Variant} from './kit';
import {boundsOf, contains, decodeArcs, pathOf, polygonsOf, Topology, XY} from './geo';
import statesTopo from './data/states-albers-10m.json';

// RegionMap (the overlay build's region map, shortlist A11): a small map of the lower 48 that shows a field's region
// values, each beat on its own word (items' `at`, R80):
//   <region>  that region's states shade in with its own tint, and its name lands on a tag in the same tint
//   pulse     the region named by the item's text pulses the accent orange twice, then holds lit
// An item's region is the one named by its key or its text (case doesn't matter: 'east' or 'East'). A region with no
// lower-48 states (Alaska, Hawaii, territories: the data's "Other") is a chip under the map instead, the place names
// beside it ("AK, HI, territories", on two lines in a narrow panel; the chip is always whole, R161 sizes); its row
// is kept from the start so the panel never changes size. The tints are
// the variant's map colours in the order the regions are listed (mapLit, mapTint2, dot, then round again); the tags
// sit where they lie most inside their region, nearest its middle. 0.5 s map in (fade, 20 px rise), 0.3 s a region,
// 0.25 s a tag or the chip, 0.5 s out; no overshoot. The shapes are us-atlas's states-albers-10m, as in MapPins.
// Variant (R140); placement a box in frame px (the panel takes the box's width and is centred in it), an edge of
// title-safe, or by default the strip between Quick Sight's open Data and Visuals panes and the sheet's right half.

export type RegionItem = {key: string; text: string; at: number};
export type RegionMapLayer = {id: string; step?: string; layout: 'region_map'; t0: number; t1: number; variant: Variant;
  items: RegionItem[]; regions: Record<string, string[]>; box?: Box; edge?: Edge};

// --- the shapes, decoded once (as MapPins) -----------------------------------------------------------------------
const topo = statesTopo as unknown as Topology;
const ARCS = decodeArcs(topo);
const STATES = topo.objects.states.geometries
  .filter((g) => g.id !== '02' && g.id !== '15')              // the lower 48 and DC: no Alaska or Hawaii insets
  .map((g) => {
    const polys = polygonsOf(ARCS, g);
    return {name: g.properties?.name ?? '', d: pathOf(polys), polys, bb: boundsOf([polys])};
  });
const B = boundsOf(STATES.map((s) => s.polys));
const VIEW = {x: B.x0 - 6, y: B.y0 - 6, w: B.x1 - B.x0 + 12, h: B.y1 - B.y0 + 12};
const ALL_D = STATES.map((s) => s.d).join('');
const INDEX = new Map(STATES.map((s, i) => [s.name.toLowerCase(), i]));
const ABBR: Record<string, string> = {alaska: 'AK', hawaii: 'HI'};    // the only states off the lower-48 map

// Which state each 6 px cell (the file's px) falls in, for placing the tags; built on first use.
const CELL = 6;
const COLS = Math.ceil(VIEW.w / CELL);
const ROWS = Math.ceil(VIEW.h / CELL);
let GRID: Int16Array | null = null;
const grid = () => {
  if (GRID) return GRID;
  const g = new Int16Array(COLS * ROWS).fill(-1);
  for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
    const p: XY = [VIEW.x + (c + 0.5) * CELL, VIEW.y + (r + 0.5) * CELL];
    for (let i = 0; i < STATES.length; i++) {
      const b = STATES[i].bb;
      if (p[0] < b.x0 || p[0] > b.x1 || p[1] < b.y0 || p[1] > b.y1) continue;
      if (contains(STATES[i].polys, p)) {
        g[r * COLS + c] = i;
        break;
      }
    }
  }
  return (GRID = g);
};

// The centre (the file's px) of a w x h tag (the file's px) for a region: of the spots clear of the tags already
// placed (`taken`, the file's px) where the tag lies most inside the region (within 3%), the one nearest the region's
// middle.
const tagSpot = (members: Set<number>, w: number, h: number, taken: Box[]): XY => {
  const g = grid();
  const W1 = COLS + 1;
  const sat = new Int32Array(W1 * (ROWS + 1));                // summed-area table of the region's cells
  let n = 0, sx = 0, sy = 0;
  for (let r = 0; r < ROWS; r++) {
    let row = 0;
    for (let c = 0; c < COLS; c++) {
      const inside = members.has(g[r * COLS + c]) ? 1 : 0;
      row += inside;
      if (inside) { n++; sx += c + 0.5; sy += r + 0.5; }
      sat[(r + 1) * W1 + c + 1] = sat[r * W1 + c + 1] + row;
    }
  }
  if (!n) return [VIEW.x + VIEW.w / 2, VIEW.y + VIEW.h / 2];
  const mx = sx / n, my = sy / n;
  const cw = Math.min(COLS, Math.max(1, Math.round(w / CELL)));
  const ch = Math.min(ROWS, Math.max(1, Math.round(h / CELL)));
  const frac = (r: number, c: number) => (sat[(r + ch) * W1 + c + cw] - sat[r * W1 + c + cw] - sat[(r + ch) * W1 + c]
    + sat[r * W1 + c]) / (cw * ch);
  const clear = (r: number, c: number) => {
    const x0 = VIEW.x + c * CELL, y0 = VIEW.y + r * CELL, x1 = x0 + cw * CELL, y1 = y0 + ch * CELL;
    return taken.every((b) => x1 <= b.x || x0 >= b.x + b.w || y1 <= b.y || y0 >= b.y + b.h);
  };
  let best = -1;
  for (let r = 0; r + ch <= ROWS; r++) for (let c = 0; c + cw <= COLS; c++) {
    if (clear(r, c)) best = Math.max(best, frac(r, c));
  }
  let at: XY = [mx, my];
  let near = Infinity;
  for (let r = 0; r + ch <= ROWS; r++) for (let c = 0; c + cw <= COLS; c++) {
    if (frac(r, c) < best - 0.03 || !clear(r, c)) continue;
    const d = (c + cw / 2 - mx) ** 2 + (r + ch / 2 - my) ** 2;
    if (d < near) { near = d; at = [c + cw / 2, r + ch / 2]; }
  }
  return [VIEW.x + at[0] * CELL, VIEW.y + at[1] * CELL];
};

// "Alaska, Hawaii, Puerto Rico, ..." -> ["AK", "HI", "territories"] (shown as "AK, HI, territories")
const offMapParts = (names: string[]) => {
  const abbr = (x: string) => ABBR[x.trim().toLowerCase()];
  const rest = names.filter((x) => !abbr(x));
  return [...names.map(abbr).filter((x): x is string => Boolean(x)), ...(rest.length > 1 ? ['territories'] : rest)];
};

// The place names in lines no wider than `room` px, broken only after a comma ("AK, HI," / "territories").
const wrapParts = (parts: string[], room: number, width: (s: string) => number) => {
  const lines: string[] = [];
  let cur = '';
  parts.forEach((p, i) => {
    const next = cur ? `${cur}, ${p}` : p;
    if (cur && width(next + (i < parts.length - 1 ? ',' : '')) > room) {
      lines.push(`${cur},`);
      cur = p;
    } else cur = next;
  });
  if (cur) lines.push(cur);
  return lines;
};

// --- layout and motion ------------------------------------------------------------------------------------------
const PANEL_W = 640;
const DEFAULT_BOX: Box = {x: 640, y: 200, w: PANEL_W, h: 520};
const PAD = {top: 22, side: 24, bottom: 24};
const RULE = LAYOUT.panel.ruleWidthPx;
const TAG_LINE = 64;
const TAG_PAD = 10;
const TAG_RULE = 2;
const TAG_GAP = 14;                                    // screen px between two tags
const ROW_GAP = 16;
const OFF_GAP = 16;                                    // the off-map chip to its place names
const ROW_H = TAG_LINE + TAG_RULE * 2;
const FILL_S = 0.3;
const TAG_DELAY_S = 0.08;
// the pulse: up, a short hold, back down to a trace, up again and held
const PULSE = {upS: 0.25, holdS: 0.15, downS: 0.25, low: 0.15};
const pulse = (t: number, at: number) => {
  const {upS, holdS, downS, low} = PULSE;
  const down = at + upS + holdS;
  return prog(t, at, upS) - (1 - low) * prog(t, down, downS) + (1 - low) * prog(t, down + downS, upS);
};

const tagStyle = (L: Look, background: string, color: string): React.CSSProperties => ({
  ...FONT.heading, fontSize: SIZE.label, lineHeight: `${TAG_LINE}px`, color, background, whiteSpace: 'nowrap',
  border: `${TAG_RULE}px solid ${L.panel}`, borderRadius: 8, padding: `0 ${TAG_PAD}px`, position: 'relative',
  overflow: 'hidden'});

// --- the composition --------------------------------------------------------------------------------------------
export const RegionMap: React.FC<{o: RegionMapLayer}> = ({o}) => {
  const {t, fps} = useEditTime(o.t0);
  const L = look(o.variant);
  const m = MOTION.composition.mapPins;
  const tints = [L.mapLit, L.mapTint2, L.dot];       // each a tag's background too: 7:1 under its text (R179)
  const names = Object.keys(o.regions ?? {});
  const regionOf = (it: RegionItem) => names.find((r) => r.toLowerCase() === it.key.toLowerCase())
    ?? names.find((r) => r.toLowerCase() === it.text.trim().toLowerCase());
  const starts = spaced(o.items.map((it) => it.at), MOTION.staggerS);
  const timed = o.items.map((it, i) => ({it, at: starts[i], region: regionOf(it), pulse: it.key === 'pulse'}));

  // the regions on the map (with their states' indexes and tint) and the one off it
  const onMap = names.map((name) => ({name, states: (o.regions[name] ?? [])
    .map((s) => INDEX.get(s.trim().toLowerCase())).filter((i): i is number => i !== undefined)}))
    .filter((r) => r.states.length > 0)
    .map((r, j) => ({...r, tint: tints[j % tints.length], d: r.states.map((i) => STATES[i].d).join('')}));
  const offName = names.find((n) => !onMap.some((r) => r.name === n));
  const offItem = timed.find((x) => !x.pulse && x.region !== undefined && x.region === offName);

  const box = o.box ?? (o.edge ? undefined : DEFAULT_BOX);
  const panelW = box ? box.w : PANEL_W;
  const innerW = panelW - PAD.side * 2 - RULE * 2;
  const widthOf = (family: React.CSSProperties, text: string, size: number) =>
    measureText({...family, text, fontSize: size} as Parameters<typeof measureText>[0]).width;

  // The off-map row: its chip whole (it never shrinks), the place names beside it, broken after a comma onto a
  // second line when the panel is too narrow for one ("AK, HI," / "territories" in a 520 px panel). The map keeps the
  // size a one-line row leaves it; a second line grows the panel, still centred on its box.
  const offChipW = offItem ? Math.ceil(widthOf(FONT.heading, offItem.it.text, SIZE.label)) + (TAG_PAD + TAG_RULE) * 2 : 0;
  const offLines = offItem && offName ? wrapParts(offMapParts(o.regions[offName] ?? []), innerW - offChipW - OFF_GAP,
    (s) => widthOf(FONT.body, s, SIZE.body)) : [];
  const offH = Math.max(ROW_H, offLines.length * TAG_LINE);
  const fixedH = PAD.top + PAD.bottom + RULE * 2 + (offItem ? ROW_GAP + ROW_H : 0);
  const k = Math.min(innerW / VIEW.w, box ? (box.h - fixedH) / VIEW.h : Infinity);
  const mapW = VIEW.w * k;
  const mapH = VIEW.h * k;

  // each shown region's tag, placed in the regions' order, clear of the ones before it (TAG_GAP apart)
  const taken: Box[] = [];
  const tags = onMap.flatMap((r) => {
    const shown = timed.find((x) => !x.pulse && x.region === r.name);
    if (!shown) return [];
    const label = shown.it.text;
    const w = widthOf(FONT.heading, label, SIZE.label) + (TAG_PAD + TAG_RULE) * 2;
    const [cx, cy] = tagSpot(new Set(r.states), w / k, ROW_H / k, taken);
    const x = Math.min(mapW - w / 2, Math.max(w / 2, (cx - VIEW.x) * k));
    const y = Math.min(mapH - ROW_H / 2, Math.max(ROW_H / 2, (cy - VIEW.y) * k));
    taken.push({x: VIEW.x + (x - w / 2 - TAG_GAP) / k, y: VIEW.y + (y - ROW_H / 2 - TAG_GAP) / k,
      w: (w + TAG_GAP * 2) / k, h: (ROW_H + TAG_GAP * 2) / k});
    return [{r, shown, label, x, y}];
  });

  const p = prog(t, o.t0, m.inS);
  return (
    <Placed box={box} edge={o.edge} fallback="top">
      <div style={{opacity: p * exitLeft(t, o.t1, m.outS, fps), transform: `translateY(${(1 - p) * MOTION.risePx}px)`}}>
        <Panel variant={o.variant} style={{width: panelW, padding: `${PAD.top}px ${PAD.side}px ${PAD.bottom}px`}}>
          <div style={{position: 'relative', width: mapW, height: mapH, margin: '0 auto'}}>
            <svg width={mapW} height={mapH} style={{position: 'absolute', left: 0, top: 0}}>
              <g transform={`scale(${k}) translate(${-VIEW.x} ${-VIEW.y})`}>
                <path d={ALL_D} fill={L.mapLand} />
                {onMap.map((r) => {
                  const shown = timed.filter((x) => !x.pulse && x.region === r.name);
                  const lit = timed.filter((x) => x.pulse && x.region === r.name);
                  const q = shown.length ? prog(t, shown[0].at, FILL_S) : 0;
                  const a = lit.length ? Math.max(...lit.map((x) => pulse(t, x.at))) : 0;
                  return (
                    <g key={r.name}>
                      {q > 0 && <path d={r.d} fill={r.tint} opacity={q} />}
                      {a > 0 && <path d={r.d} fill={ACCENT} opacity={a} />}
                    </g>
                  );
                })}
                <path d={ALL_D} fill="none" stroke={L.mapBorder} strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
              </g>
            </svg>
            {tags.map(({r, shown, label, x, y}) => {
              const q = prog(t, shown.at + TAG_DELAY_S, m.pinS);
              const lit = timed.filter((x) => x.pulse && x.region === r.name);
              const a = lit.length ? Math.max(...lit.map((x) => pulse(t, x.at))) : 0;
              return (
                <div key={r.name} style={{position: 'absolute', left: x, top: y, opacity: q,
                  transform: `translate(-50%, -50%) scale(${0.92 + 0.08 * q})`}}>
                  <div style={tagStyle(L, r.tint, L.panel)}>
                    {/* the pulse outlines the tag in orange (R180: orange for shapes, never behind text) */}
                    {a > 0 && <div style={{position: 'absolute', inset: 0, border: `${TAG_RULE + 2}px solid ${ACCENT}`,
                      borderRadius: 8, opacity: a}} />}
                    <span style={{position: 'relative'}}>{label}</span>
                  </div>
                </div>
              );
            })}
          </div>
          {offItem && offName && (() => {
            const q = prog(t, offItem.at, m.pinS);
            return (
              <div style={{display: 'flex', alignItems: 'flex-start', gap: OFF_GAP, height: offH, marginTop: ROW_GAP,
                opacity: q, transform: `translateY(${(1 - q) * 8}px)`}}>
                <div style={{...tagStyle(L, L.well, L.body), border: `${TAG_RULE}px solid ${rgba(L.rule, 0.6)}`,
                  flex: 'none'}}>
                  {offItem.it.text}
                </div>
                <div style={{...FONT.body, fontSize: SIZE.body, lineHeight: `${TAG_LINE}px`, color: L.body,
                  paddingTop: TAG_RULE, minWidth: 0}}>
                  {offLines.map((line, i) => <div key={i} style={{whiteSpace: 'nowrap'}}>{line}</div>)}
                </div>
              </div>
            );
          })()}
        </Panel>
      </div>
    </Placed>
  );
};

export type RegionMapProps = PreviewProps<RegionMapLayer>;

// Shortlist A11 (00:10:25:04 to 00:10:41:25), compressed: the regions of dest_region as they're named, then "East is
// the busiest".
export const REGION_MAP_SAMPLE: RegionMapProps = {durationInFrames: 210, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'dest-region', layout: 'region_map', t0: 0.3, t1: 6.5, variant: 'dark', items: [
    {key: 'east', text: 'East', at: 0.3},
    {key: 'central', text: 'Central', at: 0.9},
    {key: 'west', text: 'West', at: 1.5},
    {key: 'other', text: 'Other', at: 2.6},
    {key: 'pulse', text: 'East', at: 4.4},
  ], regions: {
    East: ['Connecticut', 'Delaware', 'Florida', 'Georgia', 'Maine', 'Maryland', 'Massachusetts', 'New Hampshire',
      'New Jersey', 'New York', 'North Carolina', 'Ohio', 'Pennsylvania', 'Rhode Island', 'South Carolina', 'Vermont',
      'Virginia', 'West Virginia'],
    Central: ['Alabama', 'Arkansas', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana', 'Michigan',
      'Minnesota', 'Mississippi', 'Missouri', 'Nebraska', 'North Dakota', 'Oklahoma', 'South Dakota', 'Tennessee',
      'Texas', 'Wisconsin'],
    West: ['Arizona', 'California', 'Colorado', 'Idaho', 'Montana', 'Nevada', 'New Mexico', 'Oregon', 'Utah',
      'Washington', 'Wyoming'],
    Other: ['Alaska', 'Hawaii', 'Puerto Rico', 'U.S. Pacific Trust Territories and Possessions', 'U.S. Virgin Islands'],
  }}};

export const RegionMapPreview: React.FC<RegionMapProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><RegionMap o={layer} /></PreviewStage>
);
