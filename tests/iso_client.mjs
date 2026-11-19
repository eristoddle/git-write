// isomorphic-git client for tests/test_server_isomorphic_git.py — the same
// client the Veneer plugin syncs with. Loaded from interop/node_modules via
// createRequire so interop/ itself stays untouched. Prints one JSON object
// and exits nonzero when a required step fails.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

// interop/ is a sibling of tests/ in the repo root.
const repoRoot = path.resolve(import.meta.dirname, '..');
const require = createRequire(path.join(repoRoot, 'interop', 'index.js'));
const git = require('isomorphic-git');
const http = require('isomorphic-git/http/node');

const [, , port, token] = process.argv;
const base = `http://127.0.0.1:${port}`;
const auth = { username: 'writer', password: token };
const author = { name: 'Iso Writer', email: 'iso@example.com' };
const results = { push: false, clone: false, pull: false, badTokenRejected: false };

const dir = path.join(os.tmpdir(), 'iso-server-test');
fs.rmSync(dir, { recursive: true, force: true });
fs.mkdirSync(dir, { recursive: true });

async function step(name, fn) {
  try {
    await fn();
    return true;
  } catch (err) {
    console.error(`${name} failed: ${err.message || err}`);
    return false;
  }
}

// 1. push: init, commit, push to the server (auto-creates the bare repo)
const a = path.join(dir, 'a');
fs.mkdirSync(a);
await git.init({ fs, dir: a, defaultBranch: 'main' });
fs.writeFileSync(path.join(a, 'novel.txt'), 'chapter one');
await git.add({ fs, dir: a, filepath: 'novel.txt' });
await git.commit({ fs, dir: a, message: 'first', author });
results.push = await step('push', () =>
  git.push({ fs, http, dir: a, url: `${base}/novel.git`, remoteRef: 'main', onAuth: () => auth }));

// 2. clone into a second working copy
const b = path.join(dir, 'b');
fs.mkdirSync(b);
results.clone = await step('clone', () =>
  git.clone({ fs, http, dir: b, url: `${base}/novel.git`, ref: 'main', singleBranch: true, onAuth: () => auth }));

// 3. pull: a new commit pushed from a arrives in b
fs.writeFileSync(path.join(a, 'novel.txt'), 'chapter two');
await git.add({ fs, dir: a, filepath: 'novel.txt' });
await git.commit({ fs, dir: a, message: 'second', author });
await git.push({ fs, http, dir: a, url: `${base}/novel.git`, remoteRef: 'main', onAuth: () => auth });
results.pull = await step('pull', async () => {
  await git.pull({ fs, http, dir: b, ref: 'main', fastForwardOnly: true, author, onAuth: () => auth });
  const pulled = fs.readFileSync(path.join(b, 'novel.txt'), 'utf8');
  if (pulled !== 'chapter two') throw new Error(`pulled content is ${JSON.stringify(pulled)}`);
});

// 4. a wrong token must be rejected by the same client
results.badTokenRejected = await step('wrong token rejected', async () => {
  try {
    await git.push({
      fs, http, dir: a, url: `${base}/rejected.git`, remoteRef: 'main',
      onAuth: () => ({ username: 'writer', password: 'wrong-token' }),
    });
    return false;
  } catch {
    return true;  // expected: the server must refuse the wrong token
  }
});

fs.rmSync(dir, { recursive: true, force: true });
console.log(JSON.stringify(results));
process.exit(results.push && results.clone && results.pull && results.badTokenRejected ? 0 : 1);
