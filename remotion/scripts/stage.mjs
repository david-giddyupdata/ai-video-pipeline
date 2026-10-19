// The avatar stage's renderer (pipeline/edit/stage.py runs it): one bundle of src/index.ts, then for each job its
// check stills and its clip, frames a..b of the AvatarStage composition as ProRes 4444 with alpha.
//
//   node scripts/stage.mjs <jobs.json> <public dir>      (run from remotion/)
//
// jobs.json: {"jobs": [{"key", "id"?, "props", "stills": [{"frame", "out"}], "clip": {"a", "b", "out"} | null}]}
// (id: the composition, AvatarStage by default; R243's subscribe animation alone is SubscribeBrand). One JSON line
// per job on stdout: {"key", "ok", "error"?}. A job that throws is reported and the rest go on.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const [jobsPath, publicDir] = process.argv.slice(2);
const {jobs} = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
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
process.on('exit', removeTmp);       // the bundle, the asset copies and the browser profiles with it
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), publicDir: path.resolve(publicDir)});
for (const j of jobs) {
  const inputProps = j.props;
  try {
    const composition = await selectComposition({serveUrl, id: j.id || 'AvatarStage', inputProps});
    for (const s of j.stills || []) {
      fs.mkdirSync(path.dirname(s.out), {recursive: true});
      await renderStill({composition, serveUrl, inputProps, frame: s.frame, output: s.out, imageFormat: 'png',
        timeoutInMilliseconds: 120000});
    }
    if (j.clip) {
      fs.mkdirSync(path.dirname(j.clip.out), {recursive: true});
      await renderMedia({composition, serveUrl, inputProps, codec: 'prores', proResProfile: '4444',
        pixelFormat: 'yuva444p10le', imageFormat: 'png', muted: true, frameRange: [j.clip.a, j.clip.b],
        outputLocation: j.clip.out, overwrite: true, timeoutInMilliseconds: 120000});
    }
    console.log(JSON.stringify({key: j.key, ok: true}));
  } catch (e) {
    console.log(JSON.stringify({key: j.key, ok: false, error: String(e && e.message ? e.message : e).slice(0, 2000)}));
  }
}
