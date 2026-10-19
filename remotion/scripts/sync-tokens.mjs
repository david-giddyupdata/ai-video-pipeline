// Copies the shared look tokens (R134) into this project, where the overlay compositions read them:
//   D:\Videos\Global Assets\motion-styles\giddyup.tokens.json  ->  src/overlays/tokens.json
// The shared file is the source; edit it there and run `npm run sync-tokens`. A copy of this project that has no
// Global Assets folder (the public blueprint, R95) keeps the tokens.json it shipped with.
//
//   node scripts/sync-tokens.mjs [source.json]
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const source = path.resolve(process.argv[2]
  ?? path.join(here, '..', '..', '..', 'Global Assets', 'motion-styles', 'giddyup.tokens.json'));
const target = path.join(here, '..', 'src', 'overlays', 'tokens.json');

if (!fs.existsSync(source)) {
  console.error(`sync-tokens: no tokens at ${source}; src/overlays/tokens.json is left as it is.`);
  process.exit(1);
}
const text = fs.readFileSync(source, 'utf8');
JSON.parse(text);                                           // refuse to copy a broken file
const before = fs.existsSync(target) ? fs.readFileSync(target, 'utf8') : null;
if (before === text) {
  console.log(`sync-tokens: ${path.relative(process.cwd(), target)} is already up to date.`);
} else {
  fs.mkdirSync(path.dirname(target), {recursive: true});
  fs.writeFileSync(target, text);
  console.log(`sync-tokens: copied ${source} -> ${path.relative(process.cwd(), target)}`);
}
