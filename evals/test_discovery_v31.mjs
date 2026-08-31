// v3.1 suite — project enumeration by cursor. Runs the REAL shipped
// scripts/project_discovery.js against a fake platform; no reimplementation, no mock
// of the thing under test. Every scenario is a shape the Improvements proving run
// either measured or would have had to survive.
//
//   A1  two cursor pages then exhaustion  -> exact union, verifiable
//   A2  the same conversation on two pages -> one stable source
//   A3  same title, different ids          -> two sources (title is never identity)
//   A4  a listing carrying a foreign chat  -> membership NOT established
//   A4b the v3.0 endpoint, filter ignored  -> cannot be reached, cannot be verified
//   A5  cursor still outstanding           -> exhaustion NOT proved
//   A5b a cursor that never advances       -> a loop is not a proof
//   A6  empty project, cursor exhausted    -> valid zero-membership, verifiable
//   A7  rerun                              -> byte-identical inventory
//   A8  a total that disagrees             -> refuses to call it exhausted
//
// Usage (from the skill root):  node evals/test_discovery_v31.mjs
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SRC = fs.readFileSync(path.join(ROOT, 'scripts/project_discovery.js'), 'utf8');
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;

// A suite that exits 0 having run nothing reports success it did not earn.
const MIN_CHECKS = 20;
const RESULTS = [];
function check(name, cond, detail = '') {
  RESULTS.push([name, !!cond]);
  console.log(`${cond ? 'PASS ' : 'FAIL '}  ${name}` +
              (detail && !cond ? `\n        — ${detail}` : ''));
}

const GID = 'g-p-improvements0000';
const LOC = {hostname: 'chatgpt.com', pathname: `/g/${GID}/project`};
const J = (o) => ({ok: true, status: 200, json: async () => o});

async function discover(pageFn, {loc = LOC, window = {}} = {}) {
  const fetchImpl = (url) => url.startsWith('/api/auth/session')
    ? J({accessToken: 'tok'})
    : pageFn(url, new URL(url, 'https://x').searchParams.get('cursor'));
  const body = SRC.replace(/^await /m, 'return await ');
  return JSON.parse(await new AsyncFunction('location', 'fetch', 'window', body)(
    loc, fetchImpl, window));
}

// A scenario that THROWS has proved nothing, so it records a failure rather than
// killing the run — otherwise the mutation guard's signal is a stack trace and the
// checks after the crash silently never happen.
async function scenario(label, fn) {
  try { await fn(); }
  catch (e) { check(`${label} (scenario raised)`, false, String(e && e.message || e)); }
}

const conv = (id, title = 't-' + id, extra = {}) => ({id, title, ...extra});
// Pages keyed by the cursor that asks for them; `cursor` absent ends the walk.
const paged = (pages) => (url, cursor) => {
  const p = pages[cursor === null ? '' : cursor];
  if (!p) return {ok: false, status: 404, json: async () => ({})};
  return J(p);
};

// ---- A1 ------------------------------------------------------------------
const P1 = Array.from({length: 20}, (_, i) => conv(`c-${i + 1}`));
const P2 = Array.from({length: 7}, (_, i) => conv(`c-${i + 21}`));
const twoPages = paged({'': {items: P1, cursor: 'k1'}, k1: {items: P2, cursor: null}});
await scenario('A1a', async () => {
  const r = await discover(twoPages);
  check('A1a cursor page 1 -> page 2 -> exhausted: exhaustion is proved mechanically',
        r.exhaustion.proven === true && r.exhaustion.pages_walked === 2,
        JSON.stringify(r.exhaustion));
  const keys = r.items.map(i => i.key).sort();
  const want = [...P1, ...P2].map(c => 'chatgpt.com/' + c.id).sort();
  check('A1b the union is exactly the two pages, no more and no less',
        r.collected === 27 && JSON.stringify(keys) === JSON.stringify(want),
        `collected=${r.collected}`);
  check('A1c an exhausted, path-scoped enumeration is verifiable',
        r.verifiable === true && /MAY be\s+declared --verified/.test(r.note), r.note);
  check('A1d the terminal signal is recorded, not assumed',
        r.exhaustion.terminal_signal === 'cursor-absent', String(r.exhaustion.terminal_signal));
});

// ---- A2 ------------------------------------------------------------------
await scenario('A2', async () => {
  const r = await discover(paged({
    '': {items: [conv('dup'), conv('x1')], cursor: 'k1'},
    k1: {items: [conv('dup'), conv('x2')], cursor: null}}));
  check('A2 the same conversation on two cursor pages is ONE stable source',
        r.collected === 3 && r.duplicates_dropped === 1 &&
        new Set(r.items.map(i => i.key)).size === 3, JSON.stringify(r.items.map(i => i.key)));
});

// ---- A3 ------------------------------------------------------------------
await scenario('A3', async () => {
  const r = await discover(paged({'': {items: [conv('id-a', 'Kvalitetsgrinden'),
                                              conv('id-b', 'Kvalitetsgrinden')], cursor: null}}));
  check('A3 same title, different ids stay two conversations (title is never identity)',
        r.collected === 2 && r.items[0].title === r.items[1].title &&
        r.items[0].key !== r.items[1].key, JSON.stringify(r.items));
});

// ---- A4 ------------------------------------------------------------------
await scenario('A4a', async () => {
  const r = await discover(paged({'': {items: [
    conv('mine', 't', {gizmo_id: GID}),
    conv('theirs', 't', {gizmo_id: 'g-p-someone-else'})], cursor: null}}));
  check('A4a a listing containing another project\'s conversation cannot be verified',
        r.verifiable === false && r.membership.foreign_items.includes('theirs'),
        JSON.stringify(r.membership));
  check('A4b the refusal says membership — not merely "incomplete"',
        /membership is NOT established/.test(r.exhaustion.reason), r.exhaustion.reason);
  check('A4c and it prints the fail-closed code the contract names',
        /PROJECT_ENUMERATION_UNVERIFIED/.test(r.note), r.note);
});

// ---- A4b: the exact v3.0 defect -----------------------------------------
await scenario('A4d', async () => {
  // The proving run measured this: /backend-api/conversations?...&gizmo_id=<gid>
  // accepts the filter and answers with the ACCOUNT. v3.0 called that endpoint and
  // would have reported complete:true over 800 foreign conversations.
  let filterEndpointCalled = false;
  const account = Array.from({length: 80}, (_, i) => conv(`acct-${i + 1}`));
  const r = await discover((url, cursor) => {
    if (url.startsWith('/backend-api/conversations')) {
      filterEndpointCalled = true;                     // filter accepted, then ignored
      return J({items: account, total: account.length});
    }
    return paged({'': {items: P1, cursor: 'k1'}, k1: {items: P2, cursor: null}})(url, cursor);
  });
  check('A4d the unfiltered account endpoint is never called at all',
        filterEndpointCalled === false);
  check('A4e enumeration reaches the path-scoped project endpoint instead',
        r.endpoint === `/backend-api/gizmos/${GID}/conversations` &&
        r.membership.scope === 'path-scoped-project-endpoint', r.endpoint);
  check('A4f the 27 real members are what gets enumerated, not the 80-chat account',
        r.collected === 27 && r.items.every(i => /^chatgpt\.com\/c-/.test(i.key)),
        `collected=${r.collected}`);
});

// ---- A5 ------------------------------------------------------------------
await scenario('A5a', async () => {
  const r = await discover(paged({'': {items: P1, cursor: 'k1'}}));   // page 2 is 404
  check('A5a a cursor still outstanding is NOT exhaustion',
        r.exhaustion.proven === false && r.verifiable === false, JSON.stringify(r.exhaustion));
  check('A5b the reason is recorded for audit, never blank',
        typeof r.exhaustion.reason === 'string' && r.exhaustion.reason.length > 0,
        r.exhaustion.reason);
  check('A5c partial items are still returned — as a DECLARED inventory, unverified',
        r.collected === 20 && /PROJECT_ENUMERATION_UNVERIFIED/.test(r.note), r.note);
});
await scenario('A5d', async () => {
  const stuck = (url, cursor) => J({items: [conv('c-' + (cursor || '0'))], cursor: 'same'});
  const r = await discover(stuck);
  check('A5d a cursor that never advances is a loop, not an exhaustion proof',
        r.exhaustion.proven === false && /did not advance/.test(r.exhaustion.reason),
        r.exhaustion.reason);
});

// ---- A6 ------------------------------------------------------------------
await scenario('A6', async () => {
  const r = await discover(paged({'': {items: [], cursor: null}}));
  check('A6 an empty project with an exhausted cursor is a VALID zero-membership result',
        r.exhaustion.proven === true && r.collected === 0 && r.verifiable === true &&
        r.exhaustion.terminal_signal === 'cursor-absent-empty-page',
        JSON.stringify(r.exhaustion));
});

// ---- A7 ------------------------------------------------------------------
await scenario('A7a', async () => {
  const a = await discover(twoPages), b = await discover(twoPages);
  check('A7a a rerun produces a byte-identical inventory',
        JSON.stringify(a.items) === JSON.stringify(b.items));
  check('A7b including the exhaustion evidence',
        JSON.stringify(a.exhaustion) === JSON.stringify(b.exhaustion));
});

// ---- A8 ------------------------------------------------------------------
await scenario('A8a', async () => {
  const r = await discover(paged({'': {items: P1, cursor: null, total: 27}}));
  check('A8a a volunteered total that DISAGREES blocks the exhaustion claim',
        r.exhaustion.proven === false && r.verifiable === false, JSON.stringify(r.exhaustion));
  check('A8b the disagreement is stated, not swallowed',
        /DISAGREES/.test(r.count_oracle), r.count_oracle);
  const ok = await discover(twoPages);
  check('A8c an ABSENT total is not a defect — this endpoint never sends one',
        ok.verifiable === true && /absent/.test(ok.count_oracle), ok.count_oracle);
});

// ---- host / id guards ----------------------------------------------------
await scenario('A9a', async () => {
  const r = await discover(twoPages, {loc: {hostname: 'claude.ai', pathname: '/'}});
  check('A9a an unknown host fails closed to a declared inventory',
        /no project-discovery adapter/.test(r.error || ''), JSON.stringify(r));
  const r2 = await discover(twoPages, {loc: {hostname: 'chatgpt.com', pathname: '/'}});
  check('A9b no project id in the URL is refused — account listing is not enumeration',
        /no project id in URL/.test(r2.error || ''), JSON.stringify(r2));
});

// ---- lint: the broken endpoint is gone for good --------------------------
check('A10 the v3.0 filter-query endpoint no longer appears as a request in the adapter',
      !/fetch\([^)]*\/backend-api\/conversations\?/.test(SRC));

const failed = RESULTS.filter(([, ok]) => !ok);
console.log(`\n${RESULTS.length - failed.length}/${RESULTS.length} checks passed`);
if (RESULTS.length < MIN_CHECKS) {
  console.log(`FAIL: only ${RESULTS.length} checks executed (floor ${MIN_CHECKS}) — ` +
              `a suite that runs nothing proves nothing`);
  process.exit(1);
}
process.exit(failed.length ? 1 : 0);
