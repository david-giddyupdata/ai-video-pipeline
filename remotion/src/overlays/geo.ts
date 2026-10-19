// Map helpers for MapPins, written here so the project needs no map library (no npm installs):
//   - a TopoJSON decoder for us-atlas's pre-projected states file (data/states-albers-10m.json, public-domain Census
//     shapes, already in Albers USA at 975 x 610 px)
//   - the projection that file was made with, for the lower 48: d3-geo's geoAlbersUsa().scale(1300)
//     .translate([487.5, 305]), whose lower-48 part is geoAlbers().rotate([96, 0]).center([-0.6, 38.7])
//     .parallels([29.5, 45.5]) at that scale and translate (a conic equal-area projection). Points come out in the
//     file's own pixels, so a lat/long lands on the drawn states.
// No React here, so a plain Node check can import it.

export type XY = [number, number];
export type Ring = XY[];
export type Polygons = Ring[][];                              // polygons, each an outer ring and its holes

export type TopoGeometry = {type: string; id?: string; properties?: {name?: string}; arcs: number[][] | number[][][]};
export type Topology = {
  transform?: {scale: [number, number]; translate: [number, number]};
  arcs: number[][][];
  objects: Record<string, {type: string; geometries: TopoGeometry[]}>;
};

const RAD = Math.PI / 180;

// d3's conicEqualAreaRaw(29.5 deg, 45.5 deg)
const sy0 = Math.sin(29.5 * RAD);
const n = (sy0 + Math.sin(45.5 * RAD)) / 2;
const c = 1 + sy0 * (2 * n - sy0);
const r0 = Math.sqrt(c) / n;
const raw = (lambda: number, phi: number): XY => {
  const r = Math.sqrt(c - 2 * n * Math.sin(phi)) / n;
  return [r * Math.sin(lambda * n), r0 - r * Math.cos(lambda * n)];
};

const K = 1300;
const TX = 487.5;
const TY = 305;
const [CX, CY] = raw(-0.6 * RAD, 38.7 * RAD);                // the centre is in rotated coordinates, as in d3

// A latitude and longitude (degrees) in the states file's pixels: d3 rotates by +96 deg of longitude, projects, then
// scales about the centre (y up -> y down).
export const albersUsa48 = (lat: number, lon: number): XY => {
  let lambda = (lon + 96) * RAD;
  if (Math.abs(lambda) > Math.PI) lambda -= Math.round(lambda / (2 * Math.PI)) * 2 * Math.PI;
  const [x, y] = raw(lambda, lat * RAD);
  return [TX + K * (x - CX), TY - K * (y - CY)];
};

// Quantized, delta-encoded arcs -> absolute pixel coordinates.
export const decodeArcs = (topo: Topology): Ring[] => {
  const t = topo.transform;
  return topo.arcs.map((arc) => {
    if (!t) return arc.map(([x, y]) => [x, y] as XY);
    let x = 0;
    let y = 0;
    return arc.map(([dx, dy]) => {
      x += dx;
      y += dy;
      return [x * t.scale[0] + t.translate[0], y * t.scale[1] + t.translate[1]] as XY;
    });
  });
};

// A ring from its arc indexes; a negative index (~i) is arc i reversed, and each arc after the first starts where the
// last one ended, so its first point is dropped.
const ring = (arcs: Ring[], idx: number[]): Ring => {
  const out: Ring = [];
  idx.forEach((i, k) => {
    const a = i >= 0 ? arcs[i] : arcs[~i].slice().reverse();
    out.push(...(k ? a.slice(1) : a));
  });
  return out;
};

export const polygonsOf = (arcs: Ring[], g: TopoGeometry): Polygons => {
  if (g.type === 'Polygon') return [(g.arcs as number[][]).map((r) => ring(arcs, r))];
  if (g.type === 'MultiPolygon') return (g.arcs as number[][][]).map((p) => p.map((r) => ring(arcs, r)));
  return [];
};

export const pathOf = (polys: Polygons): string => polys.map((rings) => rings.map((r) =>
  'M' + r.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join('L') + 'Z').join('')).join('');

// Even-odd point-in-polygon over every ring (holes included).
export const contains = (polys: Polygons, [px, py]: XY): boolean => polys.some((rings) => {
  let inside = false;
  for (const r of rings) {
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const [xi, yi] = r[i];
      const [xj, yj] = r[j];
      if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
    }
  }
  return inside;
});

export const boundsOf = (all: Polygons[]): {x0: number; y0: number; x1: number; y1: number} => {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const polys of all) for (const rings of polys) for (const [x, y] of rings[0]) {
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
  }
  return {x0, y0, x1, y1};
};

// "29.7604, -95.3698" -> {lat, lon}, or null when the text isn't a pair.
export const parseLatLon = (text: string): {lat: number; lon: number} | null => {
  const m = text.match(/(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)/);
  return m ? {lat: Number(m[1]), lon: Number(m[2])} : null;
};
