// Renders R242's pieces (the series card, the subscribe variations) and their previews over a round's stage: one bundle
// of src/index.ts, then for each job its stills and its clip, frames a..b of the job's composition, as transparent
// ProRes 4444 (codec "prores") or H.264 (codec "h264", a preview).
//
//   node scripts/ctas.mjs <jobs.json> <public dir>      (run from remotion/)
//
// jobs.json: {"jobs": [{"key", "id", "props", "stills": [{"frame", "out"}], "clip": {"a", "b", "out", "codec"} | null}]}.
// One JSON line per job on stdout: {"key", "ok", "error"?}. A job that throws is reported and the rest go on.
// Like scripts/stage.mjs, the run works in a temp folder of its own (GOTCHAS: Remotion leaves a copy of every input
// and its bundle in the temp folder), on G:\aidv_scratch when that card is there, removed when the run ends.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const [jobsPath, publicDir] = process.argv.slice(2);
const {jobs} = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
const scratch = 'G:\\aidv_scratch\\remotion_tmp';
const base = fs.existsSync('G:\\') ? (fs.mkdirSync(scratch, {recursive: true}), scratch) : os.tmpdir();
const myTmp = fs.mkdtempSync(path.join(base, 'aidv-render-'));
process.env.TEMP = process.env.TMP = process.env.TMPDIR = myTmp;    // os.tmpdir() reads these on every call
const removeTmp = () => {
  try {
    fs.rmSync(myTmp, {recursive: true, force: true, maxRetries: 10, retryDelay: 200});
  } catch (e) {
    console.error(`could not remove ${myTmp}: ${e.message}`);
  }
};
process.on('exit', removeTmp);       // the bundle, the asset copies and the browser profiles with it
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => process.exit(130));    // a stopped run still cleans up (Fable)
}
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), publicDir: path.resolve(publicDir)});
for (const j of jobs) {
  const inputProps = j.props;
  try {
    const composition = await selectComposition({serveUrl, id: j.id, inputProps});
    for (const s of j.stills || []) {
      fs.mkdirSync(path.dirname(s.out), {recursive: true});
      await renderStill({composition, serveUrl, inputProps, frame: s.frame, output: s.out, imageFormat: 'png',
        timeoutInMilliseconds: 120000});
    }
    if (j.clip) {
      fs.mkdirSync(path.dirname(j.clip.out), {recursive: true});
      const prores = j.clip.codec === 'prores';
      await renderMedia({composition, serveUrl, inputProps, muted: true, frameRange: [j.clip.a, j.clip.b],
        outputLocation: j.clip.out, overwrite: true, timeoutInMilliseconds: 120000,
        ...(prores ? {codec: 'prores', proResProfile: '4444', pixelFormat: 'yuva444p10le', imageFormat: 'png'}
          : {codec: 'h264', crf: 16, pixelFormat: 'yuv420p', imageFormat: 'jpeg', jpegQuality: 95})});
    }
    console.log(JSON.stringify({key: j.key, ok: true}));
  } catch (e) {
    console.log(JSON.stringify({key: j.key, ok: false, error: String(e && e.message ? e.message : e).slice(0, 2000)}));
  }
}
