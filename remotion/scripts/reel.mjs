// The highlight reel's layers (R248; tools/reel.py): one bundle, then each job a still (a check frame, with the
// background and footage stills it names) or a transparent ProRes 4444 clip (the layer alone, for Premiere).
//
//   node scripts/reel.mjs <public dir> <jobs.json> [tmp parent]
//
// jobs.json: [{"out": "<file>", "props": {...ReelProps}, "frame": n}]: with "frame" a PNG still of that frame at
// full size, without it the whole layer as ProRes 4444 with alpha (R61: PNG frames, so the alpha survives;
// GOTCHAS). Run from remotion/. Remotion's temp copies go in a folder of their own under [tmp parent] (G:'s scratch
// when given), removed at the end, as scripts/stills.mjs does (GOTCHAS: they filled C: twice).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const [publicDir, jobsPath, tmpParent] = process.argv.slice(2);
const jobs = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
// G:'s scratch when given (made if missing, so a render never falls back to C: silently; GOTCHAS, Fable F9)
if (tmpParent) {
  fs.mkdirSync(tmpParent, {recursive: true});
}
const parent = tmpParent || os.tmpdir();
const myTmp = fs.mkdtempSync(path.join(parent, 'aidv-render-'));
process.env.TEMP = process.env.TMP = process.env.TMPDIR = myTmp;
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), publicDir: path.resolve(publicDir)});
let failed = 0;
try {
  for (const j of jobs) {
    fs.mkdirSync(path.dirname(j.out), {recursive: true});
    try {
      const composition = await selectComposition({serveUrl, id: 'Reel', inputProps: j.props});
      if (j.frame !== undefined) {
        await renderStill({composition, serveUrl, inputProps: j.props, frame: j.frame, output: j.out,
          imageFormat: 'png'});
      } else {
        const part = j.out.replace(/(\.[^.]+)$/, '.part$1');
        await renderMedia({composition, serveUrl, inputProps: j.props, codec: 'prores', proResProfile: '4444',
          pixelFormat: 'yuva444p10le', imageFormat: 'png', outputLocation: part, timeoutInMilliseconds: 90000});
        fs.renameSync(part, j.out);
      }
      console.log(j.out);
    } catch (e) {
      failed++;
      console.error(`FAILED ${j.out}: ${e.message}`);
    }
  }
} finally {
  try {
    fs.rmSync(serveUrl, {recursive: true, force: true, maxRetries: 10, retryDelay: 200});
  } catch (e) {
    console.error(`could not remove the bundle ${serveUrl}: ${e.message}`);
  }
  try {
    fs.rmSync(myTmp, {recursive: true, force: true, maxRetries: 10, retryDelay: 200});
  } catch (e) {
    console.error(`could not remove ${myTmp}: ${e.message}`);
  }
}
process.exit(failed ? 1 : 0);
