// Region-dwell zoom (SPEC §7.2), planned by pipeline/edit/camera.py. Keyframes are linear (David's style: no easing).
// x, y: the source-frame point at the centre of the output; s: scale. Same maths as camera.py cam_at / to_screen.
import {Pt} from './track';

export type CamKey = {t: number; s: number; x: number; y: number};
export type Cam = {s: number; x: number; y: number};

const clampCentre = (c: Cam, W: number, H: number): Cam => {
  const hw = W / (2 * c.s), hh = H / (2 * c.s);
  return {s: c.s, x: Math.min(Math.max(c.x, hw), W - hw), y: Math.min(Math.max(c.y, hh), H - hh)};
};

export const cameraAt = (keys: CamKey[] | undefined, t: number, W: number, H: number): Cam => {
  if (!keys || keys.length === 0) return {s: 1, x: W / 2, y: H / 2};
  let c: Cam = keys[keys.length - 1];
  if (t <= keys[0].t) c = keys[0];
  else {
    for (let i = 0; i + 1 < keys.length; i++) {
      const a = keys[i], b = keys[i + 1];
      if (a.t <= t && t < b.t) {
        const u = b.t > a.t ? (t - a.t) / (b.t - a.t) : 1;
        c = {s: a.s + (b.s - a.s) * u, x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u};
        break;
      }
    }
  }
  return clampCentre(c, W, H);
};

// Source-frame point -> output point under the camera.
export const toScreen = (c: Cam, p: Pt, W: number, H: number): Pt =>
  ({x: (p.x - c.x) * c.s + W / 2, y: (p.y - c.y) * c.s + H / 2});

// CSS transform for the picture layer (transform-origin 0 0).
export const cameraTransform = (c: Cam, W: number, H: number) =>
  `translate(${W / 2 - c.x * c.s}px, ${H / 2 - c.y * c.s}px) scale(${c.s})`;
