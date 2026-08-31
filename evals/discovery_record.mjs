// Emit a REAL enumeration record by running the shipped scripts/project_discovery.js
// against a fake platform. Used by test_project_v3.py so the Python checker is fed the
// adapter's actual output rather than a hand-written fixture — the two halves of
// claim A only mean something if they meet.
//
//   node evals/discovery_record.mjs <gid> <conv-id> [<conv-id> …]   > record.json
//
// The ids are split across two cursor pages so the record carries a real page ledger.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const [gid, ...ids] = process.argv.slice(2);
if (!gid || !ids.length) {
  console.error('usage: discovery_record.mjs <gid> <conv-id> [<conv-id> …]');
  process.exit(2);
}

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SRC = fs.readFileSync(path.join(ROOT, 'scripts/project_discovery.js'), 'utf8');
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;

const J = (o) => ({ok: true, status: 200, json: async () => o});
const half = Math.max(1, Math.ceil(ids.length / 2));
const page = (list, cursor) =>
  J({items: list.map(id => ({id, title: 't-' + id, gizmo_id: gid})), cursor});

const fetchImpl = (url) => {
  if (url.startsWith('/api/auth/session')) return J({accessToken: 'tok'});
  const cursor = new URL(url, 'https://x').searchParams.get('cursor');
  if (!cursor) return page(ids.slice(0, half), 'k1');
  if (cursor === 'k1') return page(ids.slice(half), null);
  return J({items: [], cursor: null});
};

const body = SRC.replace(/^await /m, 'return await ');
process.stdout.write(await new AsyncFunction('location', 'fetch', 'window', body)(
  {hostname: 'chatgpt.com', pathname: `/g/${gid}/project`}, fetchImpl, {}));
