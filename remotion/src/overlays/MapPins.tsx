import React from 'react';
import {evolvePath} from '@remotion/paths';
import {ACCENT, Box, Edge, exitLeft, FONT, LAYOUT, look, MOTION, Panel, PreviewProps, PreviewStage, prog, rgba, SIZE,
  spaced, useEditTime, Variant, lh} from './kit';
import {albersUsa48, boundsOf, decodeArcs, parseLatLon, pathOf, polygonsOf, Topology, XY} from './geo';
import {TABLER} from './vendor/tabler/icons';
import statesTopo from './data/states-albers-10m.json';

// MapPins (David's direction; the overlay plan's composition 9): a map of the lower 48 that says "geocoded data"
// through the geospatial fields (p1.18 to p1.34), each beat on its own word (items' `at`, R80):
//   pair       before the map, a bare lat/long pair as plain numbers (B2); when its pin comes, the pair drops onto
//              that pin and becomes its label
//   map        the map's own entrance, when it comes later than t0 (after a pair); the land draws in west to east
//   state      the named state lights up                                     (dest_state)
//   lat_lines  lines of latitude draw across, west to east                   (latitude)
//   lon_lines  lines of longitude draw down, north to south                  (longitude)
//   pin        a pin drops on a literal lat/long pair, the pair beside it    (latitude and longitude together)
//   city       a city point pops with its name                               (dest_city)
//   count      the corner counter, "1 of 4  dest_state" ... "4 of 4  dest_city"
//   ticks      the fields named in its text ("dest_state, latitude, ...") tick one by one over the map, which fades
//              back under them (B3)
// 0.5 s map in, 0.25 s a pin, state or city, 0.6 s a set of lines, 0.6 s a pair's drop, 0.5 s out; no overshoot.
// Items on one word (three states, three cities) ripple 50 ms apart, so all land within 0.1 s of it. A label sits
// on the side given (left, right, above, below), on a plate of the panel colour, so it reads over a lit state; a
// label that would leave the panel moves below or above its point instead. `until` fades an item's label out early;
// a pin's label also gives way when a city is named on the same point. The shapes are us-atlas's states-albers-10m
// (public-domain Census data, Albers USA at 975 x 610 px); points are placed with the projection that file was made
// with (geo.ts), so Houston lands in Texas. Variant (R140); placement a box in frame px (the panel is centred at its
// top), else a 720 x 540 box against an edge of title-safe (default: the right, 140 px down, clear of a left-hand
// pane and of the captions).

export type MapSide = 'left' | 'right' | 'above' | 'below';
export type MapItem = {text: string; at: number; kind: 'state' | 'pin' | 'city' | 'lat_lines' | 'lon_lines' | 'count'
  | 'pair' | 'map' | 'ticks'; key?: string; lat?: number; lon?: number; side?: MapSide; until?: number};
export type MapPinsLayer = {id: string; step?: string; layout: 'map_pins'; t0: number; t1: number; variant: Variant;
  items: MapItem[]; box?: Box; edge?: Edge};

// --- the shapes, decoded once -----------------------------------------------------------------------------------
const topo = statesTopo as unknown as Topology;
const ARCS = decodeArcs(topo);
const STATES = topo.objects.states.geometries
  .filter((g) => g.id !== '02' && g.id !== '15')              // the lower 48 and DC: no Alaska or Hawaii insets
  .map((g) => {
    const polys = polygonsOf(ARCS, g);
    const b = boundsOf([polys]);
    return {name: g.properties?.name ?? '', d: pathOf(polys), polys, cx: (b.x0 + b.x1) / 2};
  });
const B = boundsOf(STATES.map((s) => s.polys));
const VIEW = {x: B.x0 - 6, y: B.y0 - 6, w: B.x1 - B.x0 + 12, h: B.y1 - B.y0 + 12};

const line = (pts: XY[]) => 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join('L');
const range = (a: number, b: number, step: number) => Array.from({length: Math.floor((b - a) / step) + 1}, (_, i) => a + i * step);
const PARALLELS = range(25, 50, 5).map((lat) => line(range(-128, -64, 1).map((lon) => albersUsa48(lat, lon))));
const MERIDIANS = range(-120, -70, 10).map((lon) => line(range(52, 22, -1).map((lat) => albersUsa48(lat, lon))));
const CHECK = TABLER['check'][0];

const LINE_DRAWN = 0.85;        // a line's opacity while it draws
const LINE_REST = 0.55;         // and once its set has been drawn (round 4: 0.35 left them too faint to read)
const HEADER_H = 72;
const DEFAULT_BOX = {w: 720, h: 540, top: 140};
const SWEEP_S = 0.4;            // the land draws in west to east over this, after the map's word
const GROUP_GAP_S = 0.05;       // items of a kind on one word ripple this far apart
const PAIR_GLIDE_S = 0.6;       // a pair's drop onto its pin; the pin lands in its second half
const TICK_GAP_S = 0.15;        // one field's tick to the next
const TICK_S = 0.3;             // a tick drawing on
const MAP_DIM = 0.15;           // the map's opacity under the ticked fields (its labels and counter go)
const LABEL_LINE = 64;          // a label's line height (px; 56 px type, R161)
const CHAR_EM = {data: 0.6, heading: 0.58};   // a label's width per character, for fitting it inside the panel

// --- labels -----------------------------------------------------------------------------------------------------
// A label is anchored to a point by its near edge: a right-hand label by its left middle, an above label by its
// bottom middle, and so on, so it can scale about that edge (a pair dropping onto its pin) and stay put.
type Anchor = {side: MapSide | 'centre'; ax: number; ay: number};
const ORIGIN = {right: 'left center', left: 'right center', above: 'center bottom', below: 'center top',
  centre: 'center center'};
const SHIFT = {right: 'translate(0, -50%)', left: 'translate(-100%, -50%)', above: 'translate(-50%, -100%)',
  below: 'translate(-50%, 0)', centre: 'translate(-50%, -50%)'};

const labelText = (it: MapItem) => (it.kind === 'pin' || it.kind === 'pair' ? it.text.replace(/,\s*/, ',\n') : it.text);
const labelSize = (text: string, data: boolean) => {
  const lines = text.split('\n');
  return {w: Math.max(...lines.map((l) => l.length)) * CHAR_EM[data ? 'data' : 'heading'] * SIZE.label + 28,
    h: lines.length * LABEL_LINE + 8};
};

type Limits = {x0: number; y0: number; x1: number; y1: number};
// The anchor for a label of size w x h on the side asked, beside a point. Where a pin stands on the point (head), a
// label beside it centres on the pin's head, 29 px up, and one above clears its top, 48 px up; one below clears a
// city's dot (dot) or the pin's tip. A side label that would leave the panel goes below its point, else above; an
// above or below label slides sideways to stay inside.
const fit = (want: MapSide, x: number, y: number, head: boolean, dot: boolean, w: number, h: number,
  lim: Limits): Anchor => {
  const gap = head ? 26 : 20;
  const mid = head ? y - 29 : y;
  const at = (s: MapSide): Anchor => s === 'right' ? {side: s, ax: x + gap, ay: mid}
    : s === 'left' ? {side: s, ax: x - gap, ay: mid}
    : s === 'above' ? {side: s, ax: x, ay: y - (head ? 54 : 20)} : {side: s, ax: x, ay: y + (dot ? 18 : 12)};
  const fits = (a: Anchor) => {
    const [l, r] = a.side === 'right' ? [a.ax, a.ax + w] : a.side === 'left' ? [a.ax - w, a.ax] : [a.ax - w / 2, a.ax + w / 2];
    const [top, bottom] = a.side === 'above' ? [a.ay - h, a.ay] : a.side === 'below' ? [a.ay, a.ay + h]
      : [a.ay - h / 2, a.ay + h / 2];
    return {x: l >= lim.x0 && r <= lim.x1, y: top >= lim.y0 && bottom <= lim.y1};
  };
  const slide = (a: Anchor): Anchor => a.side === 'above' || a.side === 'below'
    ? {...a, ax: Math.min(lim.x1 - w / 2, Math.max(lim.x0 + w / 2, a.ax))} : a;
  const order: MapSide[] = want === 'right' || want === 'left'
    ? [want, 'below', 'above', want === 'right' ? 'left' : 'right'] : [want, want === 'above' ? 'below' : 'above'];
  for (const s of order) {
    const f = fits(at(s));
    if (f.y && (f.x || s === 'above' || s === 'below')) return slide(at(s));
  }
  return slide(at(want));
};

const Plate: React.FC<{a: Anchor; data: boolean; variant: Variant; opacity: number; scale?: number; lift?: number;
  children: React.ReactNode}> = ({a, data, variant, opacity, scale = 1, lift = 0, children}) => {
  const L = look(variant);
  return (
    <div style={{position: 'absolute', left: a.ax, top: a.ay, transformOrigin: ORIGIN[a.side],
      transform: `translateY(${lift}px) ${SHIFT[a.side]} scale(${scale})`, opacity, whiteSpace: 'pre',
      textAlign: a.side === 'left' ? 'right' : 'left', ...(data ? FONT.data : FONT.heading), fontSize: SIZE.label,
      lineHeight: `${LABEL_LINE}px`, color: L.body, background: L.panel, border: `2px solid ${rgba(L.rule, 0.7)}`,
      borderRadius: 8, padding: '2px 12px'}}>
      {children}
    </div>
  );
};

// --- pieces -----------------------------------------------------------------------------------------------------
const Pin: React.FC<{x: number; y: number; p: number; ring: string}> = ({x, y, p, ring}) => (
  <g transform={`translate(${x} ${y - (1 - p) * 40})`} opacity={p}>
    <path d="M0,0 C-4,-11 -16,-17 -16,-29 A16,16 0 1 1 16,-29 C16,-17 4,-11 0,0 Z" fill={ACCENT} stroke={ring}
      strokeWidth={2.5} />
    <circle cx={0} cy={-29} r={6} fill={ring} />
  </g>
);

// The ticked fields: Courier New names (R143), an orange tick drawing on before each, one after another.
const Ticks: React.FC<{it: MapItem; t: number; variant: Variant}> = ({it, t, variant}) => {
  const L = look(variant);
  const names = it.text.split(/\s*,\s*/).filter(Boolean);
  const size = SIZE.data;
  return (
    <div style={{opacity: prog(t, it.at, MOTION.composition.mapPins.pinS)}}>
      {names.map((name, i) => {
        const q = prog(t, it.at + i * TICK_GAP_S, TICK_S);
        const tick = evolvePath(q, CHECK);
        return (
          <div key={i} style={{display: 'flex', alignItems: 'center', gap: 18, whiteSpace: 'pre'}}>
            <svg width={size} height={size} viewBox="0 0 24 24" style={{flex: 'none'}}>
              <path d={CHECK} fill="none" stroke={ACCENT} strokeWidth={3.2} strokeLinecap="round" strokeLinejoin="round"
                strokeDasharray={tick.strokeDasharray} strokeDashoffset={tick.strokeDashoffset} opacity={q > 0 ? 1 : 0} />
            </svg>
            <div style={{...FONT.data, fontSize: size, lineHeight: `${size + 12}px`, color: L.body}}>{name}</div>
          </div>
        );
      })}
    </div>
  );
};

const boxOf = (o: MapPinsLayer, width: number): Box => {
  if (o.box) return o.box;
  const s = LAYOUT.safePx;
  const {w, h, top} = DEFAULT_BOX;
  const e = o.edge ?? 'right';
  return {w, h, x: e === 'left' ? s.left : e === 'right' ? width - s.right - w : (width - w) / 2,
    y: e === 'top' ? s.top : e === 'bottom' ? LAYOUT.captionTopPx - h : top};
};

// --- the composition --------------------------------------------------------------------------------------------
export const MapPins: React.FC<{o: MapPinsLayer}> = ({o}) => {
  const {t, fps, width} = useEditTime(o.t0);
  const L = look(o.variant);
  const m = MOTION.composition.mapPins;
  const box = boxOf(o, width);
  const pad = LAYOUT.panel.padPx;
  const rule = LAYOUT.panel.ruleWidthPx;
  const of = (kind: MapItem['kind']) => o.items.filter((it) => it.kind === kind);
  const counts = of('count');
  const header = counts.length ? HEADER_H : 0;
  const k = Math.min((box.w - pad[1] * 2 - rule * 2) / VIEW.w, (box.h - pad[0] * 2 - rule * 2 - header) / VIEW.h);
  const mapW = VIEW.w * k;
  const mapH = VIEW.h * k;
  const panelX = (box.w - (mapW + pad[1] * 2 + rule * 2)) / 2;
  const mx = panelX + rule + pad[1];                   // the map's top left in the box
  const my = rule + pad[0] + header;
  const lim = {x0: -pad[1] + 6, x1: mapW + pad[1] - 6, y0: -(pad[0] + header) + 6, y1: mapH + pad[0] - 6};
  const px = ([x, y]: XY): XY => [(x - VIEW.x) * k, (y - VIEW.y) * k];
  const where = (it: MapItem): XY | null => {
    const ll = it.lat !== undefined && it.lon !== undefined ? {lat: it.lat, lon: it.lon} : parseLatLon(it.text);
    return ll ? px(albersUsa48(ll.lat, ll.lon)) : null;
  };
  const same = (a: XY | null, b: XY | null) => !!a && !!b && Math.hypot(a[0] - b[0], a[1] - b[1]) < 2;

  // the map's entrance: its own item, or the layer's start
  const mapAt = Math.max(o.t0, of('map')[0]?.at ?? o.t0);
  const p = prog(t, mapAt, m.inS);
  const rise = (1 - p) * MOTION.risePx;
  const ticks = of('ticks')[0];
  const fade = ticks ? prog(t, ticks.at, MOTION.baseS) : 0;
  const dim = 1 - (1 - MAP_DIM) * fade;              // the map under the ticks
  const hide = 1 - fade;                             // its labels and counter
  const ripple = (kind: 'state' | 'city') => {
    const items = of(kind);
    const starts = spaced(items.map((it) => it.at), GROUP_GAP_S);
    return items.map((it, i) => ({it, start: starts[i], at: kind === 'city' ? where(it) : null}));
  };
  const states = ripple('state');
  const cities = ripple('city');

  // pins, with the pair that drops onto one (the first pin on the pair's point, or with its text, after it)
  const pair = of('pair')[0];
  const pairAt = pair ? where(pair) : null;
  const pins = of('pin').map((it) => {
    const at = where(it);
    const city = cities.find((c) => c.it.at > it.at && same(c.at, at));
    return {it, at, until: it.until ?? city?.start};
  });
  const pairPin = pair ? pins.find((q) => q.at && q.it.at >= pair.at && (same(q.at, pairAt) || q.it.text === pair.text))
    : undefined;
  const labelP = (start: number, until?: number) => prog(t, start + m.pinS * 0.4, m.pinS)
    * (until !== undefined ? 1 - prog(t, until, m.pinS) : 1);

  // a set of lines draws on (80 ms apart), then recedes so the states and pins read over it
  const lines = (kind: 'lat_lines' | 'lon_lines', paths: string[]) => of(kind).map((it, j) => {
    const settle = LINE_DRAWN - (LINE_DRAWN - LINE_REST)
      * prog(t, it.at + (paths.length - 1) * MOTION.staggerS + m.lineS, MOTION.baseS);
    return (
      <g key={`${kind}-${j}`} opacity={settle}>
        {paths.map((d, i) => {
          const q = prog(t, it.at + i * MOTION.staggerS, m.lineS);
          // round 4 (the visual review): 4 px (R161's floor) in the lighter muted colour; at 2 px in mapLines they
          // measured 2.3:1 on the land and all but vanished on a phone
          return <path key={i} d={d} fill="none" stroke={L.muted} strokeWidth={4 / k} pathLength={1}
            strokeDasharray="1 1" strokeDashoffset={1 - q} opacity={q > 0 ? 1 : 0} />;
        })}
      </g>
    );
  });
  const clipId = `mapclip-${o.id.replace(/[^A-Za-z0-9_-]/g, '')}`;

  // the pair: plain numbers in the middle of the map's space, at data size; on its pin's word it shrinks to label
  // size and drops beside the pin (the pin lands as it arrives), and stays on as that pin's label
  let pairEl: React.ReactNode = null;
  if (pair) {
    const text = labelText(pair);
    const sz = labelSize(text, true);
    const big = SIZE.data / SIZE.label;
    const inP = prog(t, pair.at, MOTION.composition.termChip.inS);
    const lift = (1 - inP) * MOTION.risePx;
    if (pairPin?.at) {
      const end = fit(pairPin.it.side ?? 'right', pairPin.at[0], pairPin.at[1], true, false, sz.w, sz.h, lim);
      const sx = end.side === 'right' ? -big * sz.w / 2 : end.side === 'left' ? big * sz.w / 2 : 0;
      const sy = end.side === 'below' ? -big * sz.h / 2 : end.side === 'above' ? big * sz.h / 2 : 0;
      const g = prog(t, pairPin.it.at, PAIR_GLIDE_S);
      const a: Anchor = {side: end.side, ax: mx + mapW / 2 + sx + (end.ax - mapW / 2 - sx) * g,
        ay: my + mapH / 2 + sy + (end.ay + rise - mapH / 2 - sy) * g};
      const gone = pairPin.until !== undefined ? 1 - prog(t, pairPin.until, m.pinS) : 1;
      pairEl = <Plate a={a} data variant={o.variant} opacity={inP * gone * (g > 0 ? hide : 1)} scale={big + (1 - big) * g}
        lift={lift}>{text}</Plate>;
    } else {
      pairEl = <Plate a={{side: 'centre', ax: mx + mapW / 2, ay: my + mapH / 2}} data variant={o.variant}
        opacity={inP * (1 - prog(t, mapAt, m.pinS))} scale={big} lift={lift}>{text}</Plate>;
    }
  }

  return (
    <div style={{position: 'absolute', left: box.x, top: box.y, width: box.w, height: box.h,
      opacity: exitLeft(t, o.t1, m.outS, fps)}}>
      <div style={{position: 'absolute', inset: 0, opacity: p, transform: `translateY(${rise}px)`}}>
        <Panel variant={o.variant} style={{position: 'absolute', left: panelX, top: 0}}>
          {counts.length > 0 && (
            <div style={{position: 'relative', height: header, opacity: hide}}>
              {counts.map((c, i) => {
                const next = counts[i + 1];
                const q = prog(t, c.at, m.pinS) * (next ? 1 - prog(t, next.at, m.pinS) : 1);
                return (
                  <div key={i} style={{position: 'absolute', left: 0, top: 0, ...FONT.data, fontSize: SIZE.dataSmall,
                    lineHeight: lh(SIZE.dataSmall), color: L.heading, whiteSpace: 'pre', opacity: q}}>{c.text}</div>
                );
              })}
            </div>
          )}
          <div style={{position: 'relative', width: mapW, height: mapH}}>
            <svg width={mapW} height={mapH} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}
              opacity={dim}>
              <defs>
                <clipPath id={clipId}>
                  {STATES.map((st) => <path key={st.name} d={st.d} />)}
                </clipPath>
              </defs>
              <g transform={`scale(${k}) translate(${-VIEW.x} ${-VIEW.y})`}>
                {STATES.map((st) => (
                  <path key={st.name} d={st.d} fill={L.mapLand} stroke={L.mapBorder} strokeWidth={1.5}
                    vectorEffect="non-scaling-stroke"
                    opacity={prog(t, mapAt + SWEEP_S * (st.cx - B.x0) / (B.x1 - B.x0), m.pinS)} />
                ))}
                {states.map(({it, start}, i) => {
                  const st = STATES.find((x) => x.name.toLowerCase() === it.text.trim().toLowerCase());
                  return st ? <path key={i} d={st.d} fill={L.mapLit} opacity={prog(t, start, m.pinS)} stroke={L.mapBorder}
                    strokeWidth={1.5} vectorEffect="non-scaling-stroke" /> : null;
                })}
                <g clipPath={`url(#${clipId})`}>
                  {lines('lat_lines', PARALLELS)}
                  {lines('lon_lines', MERIDIANS)}
                </g>
              </g>
              {cities.filter(({at}) => at).map(({start, at}, i) => {
                const q = prog(t, start, m.pinS);
                return <circle key={`c${i}`} cx={at![0]} cy={at![1]} r={10 * q} fill={L.dot} stroke={L.dotRing} strokeWidth={3.5} />;
              })}
              {pins.filter(({at}) => at).map((q, i) => (
                <Pin key={`p${i}`} x={q.at![0]} y={q.at![1]} ring={L.dotRing}
                  p={prog(t, q === pairPin ? q.it.at + PAIR_GLIDE_S / 2 : q.it.at, m.pinS)} />
              ))}
            </svg>
          </div>
        </Panel>
        <div style={{position: 'absolute', left: mx, top: my, width: mapW, height: mapH}}>
          <div style={{position: 'absolute', inset: 0, opacity: hide}}>
            {pins.filter((q) => q.at && q !== pairPin).map((q, i) => {
              const text = labelText(q.it);
              const sz = labelSize(text, true);
              return <Plate key={`pl${i}`} a={fit(q.it.side ?? 'right', q.at![0], q.at![1], true, false, sz.w, sz.h, lim)} data
                variant={o.variant} opacity={labelP(q.it.at, q.until)}>{text}</Plate>;
            })}
            {cities.filter(({at}) => at).map(({it, start, at}, i) => {
              const sz = labelSize(it.text, false);
              const onPin = pins.some((q) => same(q.at, at));
              return <Plate key={`cl${i}`} a={fit(it.side ?? 'right', at![0], at![1], onPin, true, sz.w, sz.h, lim)}
                data={false} variant={o.variant} opacity={labelP(start, it.until)}>{it.text}</Plate>;
            })}
          </div>
          {ticks && (
            <div style={{position: 'absolute', left: mapW / 2, top: (mapH - header) / 2, transform: 'translate(-50%, -50%)'}}>
              <Ticks it={ticks} t={t} variant={o.variant} />
            </div>
          )}
        </div>
      </div>
      {pairEl}
    </div>
  );
};

export type MapPinsProps = PreviewProps<MapPinsLayer>;

// p1.18 to p1.34, compressed: the bare pair, which drops onto Houston as the map comes; the four fields in the order
// they are set, the states of dest_state, two more lat/long pairs, the cities (the pairs give way to their names),
// then the four fields ticked.
export const MAP_PINS_SAMPLE: MapPinsProps = {durationInFrames: 450, fps: 30, width: 1920, height: 1080,
  still: '', layer: {id: 'geo-fields', layout: 'map_pins', t0: 0.3, t1: 14.5, variant: 'dark', items: [
    {kind: 'pair', text: '29.7604, -95.3698', at: 0.3},
    {kind: 'map', text: '', at: 2.0},
    {kind: 'pin', text: '29.7604, -95.3698', at: 2.0, side: 'right'},
    {kind: 'count', text: '1 of 4  dest_state', at: 3.0},
    {kind: 'state', text: 'Texas', at: 3.4},
    {kind: 'state', text: 'Illinois', at: 3.4},
    {kind: 'state', text: 'New York', at: 3.4},
    {kind: 'count', text: '2 of 4  latitude', at: 4.6},
    {kind: 'lat_lines', text: 'latitude', at: 4.8},
    {kind: 'count', text: '3 of 4  longitude', at: 6.2},
    {kind: 'lon_lines', text: 'longitude', at: 6.4},
    {kind: 'pin', text: '41.8781, -87.6298', at: 7.6, side: 'left', until: 9.8},
    {kind: 'pin', text: '40.7128, -74.0060', at: 8.1, side: 'above', until: 9.8},
    {kind: 'count', text: '4 of 4  dest_city', at: 9.8},
    {kind: 'city', text: 'Houston', lat: 29.7604, lon: -95.3698, at: 10.1, side: 'below'},
    {kind: 'city', text: 'Chicago', lat: 41.8781, lon: -87.6298, at: 10.1, side: 'above'},
    {kind: 'city', text: 'New York', lat: 40.7128, lon: -74.0060, at: 10.1, side: 'right'},
    {kind: 'ticks', text: 'dest_state, latitude, longitude, dest_city', at: 12.0},
  ]}};

export const MapPinsPreview: React.FC<MapPinsProps> = ({still, layer}) => (
  <PreviewStage still={still} t0={layer.t0} t1={layer.t1}><MapPins o={layer} /></PreviewStage>
);
