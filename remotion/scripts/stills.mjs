// Many EditPass stills from one bundle (the line check, R85): `npx remotion still` bundles again for every frame
// (about 12 s each), so this bundles once with the run's media baked in as the public dir (GOTCHAS: a bundle serves
// only the public dir it was made with) and renders each frame from it.
//
//   node scripts/stills.mjs <props.json> <public dir> <out dir> <jobs.json> [scale]
//
// jobs.json: [{"frame": n, "out": "name.png"}]. Run from remotion/.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';

const [propsPath, publicDir, outDir, jobsPath, scale = '0.5'] = process.argv.slice(2);
const inputProps = JSON.parse(fs.readFileSync(propsPath, 'utf8'));
const jobs = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
// Remotion leaves temp copies of every input (remotion-v*-assets*), its bundle and Chrome profiles in the temp
// folder: 7,040 asset folders held 215 GB of C: on 2026-10-16. This run works in a temp folder of its own, made
// here and removed when it ends, so it never touches another render's files (two can run at once; Fable).
const myTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'aidv-render-'));
process.env.TEMP = process.env.TMP = process.env.TMPDIR = myTmp;    // os.tmpdir() reads these on every call
const removeTmp = () => {
  try {
    fs.rmSync(myTmp, {recursive: true, force: true, maxRetries: 10, retryDelay: 200});
  } catch (e) {
    console.error(`could not remove ${myTmp}: ${e.message}`);
  }
};
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), publicDir: path.resolve(publicDir)});
try {
  const composition = await selectComposition({serveUrl, id: 'EditPass', inputProps});
  fs.mkdirSync(outDir, {recursive: true});
  for (const j of jobs) {
    await renderStill({composition, serveUrl, inputProps, frame: j.frame, output: path.join(outDir, j.out),
      scale: Number(scale), imageFormat: 'png'});
    console.log(j.out);
  }
} finally {
  // the bundle is a copy in the temp folder (about 140 MB with the public dir): 759 of them filled C: (round 8).
  // An indexer can hold a fresh file a moment: retried, and a failure never fails the stills already written
  try {
    fs.rmSync(serveUrl, {recursive: true, force: true, maxRetries: 10, retryDelay: 200});
  } catch (e) {
    console.error(`could not remove the bundle ${serveUrl}: ${e.message}`);
  }
  removeTmp();                                 // the asset copies and browser profiles too
}
