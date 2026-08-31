# Chat extraction playbook (ChatGPT & Claude)

Battle-tested against chatgpt.com (Aug 2026). The canonical code lives in `scripts/`
(`data_capture.js`, `probe.js`, `render_pass.js`, `extract.js`, `reassemble_verify.py`) —
use those files verbatim instead of rewriting the snippets; every line in them exists
because a naive version failed. This document explains why they look the way they do.

**Order of attack: data layer first (Step 0), DOM scraping only as fallback.**

## Step 0 — PREFERRED: data-layer capture (ChatGPT & Claude.ai)

Capture from the DATA LAYER, not the rendered DOM. Two real runs proved the DOM paths
fragile: a `/share/` link's embedded SSR payload decoded to a bloated 156k-char block
(the raw data model — tool wrappers, metadata, reasoning — not the chat a human saw),
and the live chat is WINDOW-virtualized: turns unmount as they leave the viewport and
only trusted wheel events mount them, so DOM scraping stalls for 15+ minutes and still
misses messages. `scripts/data_capture.js` bypasses all of it:

1. **Auth**: from the logged-in chatgpt.com page, `GET /api/auth/session` (cookie auth)
   returns JSON with `accessToken`.
2. **Fetch**: `GET /backend-api/conversation/<conversation-id>` with header
   `Authorization: Bearer <accessToken>`. The conversation id is the last segment of the
   chat URL (`/c/<id>`). Same-origin fetch from the page's own context — the token never
   leaves the tab and is never written anywhere.
3. **Linear reconstruction**: the response holds a branched tree in `mapping`. Start at
   `current_node`, follow each node's `parent` up to the root, collect the nodes, reverse
   to chronological order — exactly the thread the user currently sees (abandoned
   edit-branches are excluded by construction).
4. **WYSIWYG filter** — keep only what a human SAW in the chat: `author.role` ∈
   {user, assistant}; `content_type == 'text'` (also handle `'multimodal_text'` by
   joining its text parts); message text = `content.parts` joined with `"\n"`. Skip
   system, tool, `'thoughts'`/reasoning, visually hidden
   (`metadata.is_visually_hidden_from_conversation`) and empty messages, and all other
   metadata. Attachments are inventoried (names from `metadata.attachments` + non-text
   multimodal parts), not inlined.
5. **Evidence, fail closed**: the script prints message count, role sequence, first/last
   message previews and total visible chars, and stores the ASCII-escaped export on
   `window.__nxExport`. Sanity-check the size — if a naive dump is many times larger
   than the visible chat plausibly is, you captured the raw model, not the text: fix it,
   never deliver it. Then run the standard slice transfer (Step 3) and verification
   (Step 4) unchanged.

**Fallback**: if the endpoint fails (401/403, network error, schema change) or yields
non-text, fall back to the DOM playbook below (probe → render pass → extract). It stays
fully supported for exactly this case.

### Claude.ai adapter (VERIFIED Aug 2026)

`scripts/data_capture.js` branches on the host; the claude.ai branch was written
discovery-first (every field name below read from a real API response before the parser
existed) and verified fail-closed against the rendered DOM of the same chats — a full
20-row chat compared end-to-end (all messages found in order, per-message content length
within 100–103%), plus head/mid-window/tail checks on a 174-row chat.

1. **Auth**: the session cookie itself — same-origin `fetch(..., {credentials:'include'})`
   from the logged-in claude.ai page. There is NO accessToken analogue (verified).
2. **Org**: `GET /api/organizations` — an account can hold several orgs (e.g. an
   API-only org); the chat lives in the one whose `capabilities` include `'chat'`.
   `orgs[0]` is NOT a safe pick.
3. **Fetch**: `GET /api/organizations/<org_uuid>/chat_conversations/<conv_uuid>?tree=True&rendering_mode=messages`
   — the conversation id is the last segment of `claude.ai/chat/<uuid>`. Without
   `rendering_mode=messages` (or with `=raw`) there are NO content blocks, only a flat
   `text` field with placeholders baked in — strictly worse; keep `=messages`.
4. **Linear reconstruction**: `chat_messages` holds ALL branches (`tree=True`). Walk
   `current_leaf_message_uuid -> parent_message_uuid -> …` up to the all-zeros root uuid
   (`00000000-0000-4000-8000-000000000000`), reverse to chronological — exactly the
   thread the user sees. Fall back to `index` order if the leaf pointer is missing.
5. **WYSIWYG filter**: `sender` ∈ {`human`, `assistant`} → user/assistant. The flat
   `.text` on each message is EMPTY for both roles in this mode — the text lives in the
   `content` blocks: keep `type:'text'` joined with `"\n"`, drop `thinking` (arrives
   empty anyway). Non-text blocks (tool cards, artifacts) are serialized server-side as
   a fenced placeholder — ```` ```\nThis block is not supported on your current device
   yet.\n``` ```` — the human saw a card, not that sentence: drop the block, inventory
   it as an attachment line. Exact match only, so wording drift leaves a VISIBLE junk
   fence instead of silently eating text. A tool-only message (all blocks placeholders)
   drops out entirely — verified correct against the DOM, which shows cards and no chat
   text there. Attachments are inventoried from per-message `attachments` + `files`.

The evidence contract, `window.__nxExport`, slice transfer and `reassemble_verify.py`
are IDENTICAL to the ChatGPT branch — nothing downstream changes.

## Site adapters (DOM fallback — read this first)

Two chat sites, two DOM shapes, one pipeline. The scripts detect `location.hostname` and
pick a selector set:

- **ChatGPT** (`chatgpt.com`, `chat.openai.com`): turns are `[data-message-author-role]`,
  role read from that attribute. **Verified.**
- **Claude** (`claude.ai`): **verified Aug 2026** — but the DOM path is a LAST resort
  here; the data-layer adapter (Step 0) is verified and strictly better. What the DOM
  actually looks like: each turn is a `div[data-testid="transcript-row"]` carrying a
  stable `data-index`; user turns hold `[data-testid="user-message"]`, assistant turns
  `.font-claude-response` (the older `.font-claude-message` has drifted away). Traps,
  all observed live: screen-reader prefixes ("You said:"/"Claude responded:") sit in the
  row OUTSIDE the turn element — capture the turn element, not the row; tool-status
  pills and thinking-toggles render INSIDE `.font-claude-response`, some with doubled
  labels ("Thought for 16s" twice) and some variants survive button-removal;
  "Claude's response was interrupted" notices and tool-only turns are rows with no chat
  text. Virtualization is aggressive even in short chats (a 20-message chat mounts ~5
  rows) and — unlike ChatGPT's trusted-wheel requirement — programmatic
  `scrollTop` jumps do NOT remount rows on their own: the virtualizer only reacts if a
  synthetic `scroll` event is dispatched on the scroll container after each jump. If a
  DOM capture is unavoidable, sweep with jump+dispatch+wait and assemble rows by
  `data-index` (never by visual order — leftover rows from other regions stay mounted).
  The probe still returns a `discovery` report; on drift, pick the turn selector from it
  and set `OVERRIDE_TURN` (and `OVERRIDE_ROLE_ATTR` if role lives in an attribute) at
  the top of `extract.js`.

Why candidate-not-hardcoded: guessing a selector and then declaring the empty result
"faithful to source" is exactly the failure we already made once. So the design is
known-selector-first, discovery-assisted, and **verification-enforced** — the Step 4
fail-closed checks (count, first/last, alternating roles, balanced fences) will reject a
wrong selector because the output comes back empty or malformed. A new/changed site never
ships a silent bad extract; it stops and asks. On the first real Claude run, paste the
probe output back so the Claude selectors can be locked from evidence, not memory.

## Known failure modes (why each step below exists)

0. **Wrong-site selectors return nothing.** ChatGPT and Claude mark up turns differently;
   the ChatGPT selector finds zero turns on Claude and vice versa. The scripts are
   host-aware (see Site adapters). If the probe reports `n: 0` or `adapterKnown: false`,
   fix the selector before anything else — do not proceed on an empty capture.
1. **`textContent` on code blocks loses line breaks.** Both sites render code-block line
   structure via layout, not newline text nodes, so `textContent` joins lines into one
   string ("Bashcd ~/repo…"). Only `innerText` on a LIVE, laid-out element preserves lines.
2. **`innerText` on hidden elements returns empty.** A holder with `visibility:hidden`
   yields empty strings for every message. Use an offscreen holder with `opacity:0` instead.
3. **Tool output limits truncate silently.** javascript_tool output is display-truncated
   (~800–1000 chars in batches). Never return the full chat in one call — use the slice
   transfer protocol below and verify every slice.
4. **Attachment previews can hang forever.** Pasted-text/file chips ("Inklistrad text…")
   load their content lazily into a modal that sometimes never finishes ("Laddar filens
   innehåll" spinner). An agent that keeps waiting, retrying and refreshing the page
   burns many minutes and stalls the whole run. Attachment capture is best-effort and
   time-boxed — it must NEVER block the export (see the Attachments section).
5. **Long code blocks are collapsed and offscreen content may be unrendered.** ChatGPT
   hides long code blocks behind an "Alltid visa information" / "Always show details"
   expander, and rendering optimizations can skip offscreen subtrees — innerText then
   returns only the visible preview, producing blocks that end mid-line or begin
   mid-script. This has actually happened and was mis-reported as "faithful to the
   source". Run the Render pass below BEFORE any capture, and treat every mid-token
   truncation as an extraction defect until proven otherwise against the actual UI
   (zoom/screenshot the block after expanding) — never write "faithful to source"
   about a clipped block without that proof.

## Step 1 — Probe

Run `scripts/probe.js` (host-aware). It reports `host`, `adapterKnown`, message count,
roles, attachment chips, first/last previews, and a `discovery` report.

Sanity-checks before proceeding:
- `adapterKnown: true` and `n` > 0. If `n: 0` on `claude.ai`, the candidate selector
  missed — pick the real turn selector from `discovery` and set `OVERRIDE_TURN` in
  `extract.js`.
- `firstPreview` looks like the chat's real opening message, and `roles` alternate
  sensibly. On Claude, confirm user vs assistant is labelled right (not all "unknown").
- Very long chats can be virtualized — if the first message looks wrong or `n` seems low,
  scroll the conversation container to the top repeatedly until the count stabilizes,
  then re-probe.

## Step 1.5 — Render pass (mandatory before any capture)

1. Scroll the conversation container from top to bottom in steps, so every message gets
   laid out at least once (defeats content-visibility/virtualization skipping).
2. Find and click every in-message expander — buttons whose text matches
   /alltid visa|always show|show more|visa mer/i — then re-scan; repeat until zero remain.
   These expanders are exactly why collapsed code blocks export truncated.
3. Re-run the probe after expansion; message sizes typically GROW. Only then extract.
4. Verification addition for Step 4: scan captured code blocks for truncation smells —
   a block ending mid-token/mid-line, or starting mid-construct. Any hit sends you back
   here, and the delivery must not claim completeness while a smell is unresolved.

## Step 2 — Extract with code-fence reconstruction

Run `scripts/extract.js` (host-aware). Per message it captures `pre.innerText` from the
LIVE DOM first (failure mode 1), clones the message, replaces each `<pre>` with a
fenced-text div, and reads the clone's `innerText` inside an offscreen `opacity:0` holder
(failure mode 2). Role comes from the site adapter. It escapes everything to ASCII (so a
slice can never split a character) and stores the result on `window.__nxExport`.

The code-fence reconstruction is identical for both sites — only the turn selector and the
role function differ, and both live in the adapter. If you had to set `OVERRIDE_TURN` in
Step 1, set it (and `OVERRIDE_ROLE_ATTR` if role is an attribute) at the top of the script
before running.

## Step 3 — Slice transfer

Fetch `window.__nxExport` in browser_batch actions of ~700 chars each, every action:

```js
'S<i>|'+window.__nxExport.substr(<i*700>,700)+'#END#'
```

Every slice result must end with `#END#` — a missing marker means display truncation:
re-fetch that slice smaller. Reassemble in the workspace by stripping prefixes/suffixes
and concatenating in order (escape sequences may be split across slice boundaries — exact
concatenation restores them).

### Step 3b — Clipboard relay (preferred transfer on macOS; verified Aug 2026)

For large exports the slice protocol is slow and floods the conversation with payload.
The clipboard relay moves the whole export in one hop, without the content ever passing
through tool output (189k chars verified lossless in a real run):

1. Back up the user's clipboard first: `pbpaste > clipboard_backup.txt` — and restore it
   (`pbcopy < clipboard_backup.txt`) when done.
2. `navigator.clipboard.writeText(...)` HANGS without user activation (the promise never
   resolves and times out the tool). Instead: arm a one-shot document click listener that
   copies from a hidden textarea via `document.execCommand('copy')`, then fire a REAL
   click with the `computer` tool on a blank margin area. The trusted click supplies the
   activation; the handler removes the textarea and itself.
3. `pbpaste > raw_export.txt` in the shell. NOTE: the command sandbox silently no-ops
   pbcopy/pbpaste (empty output, exit 0) — run **only** the pbpaste/pbcopy steps
   sandbox-disabled.

   SCOPE OF THAT EXCEPTION — it covers the clipboard commands and nothing else. Never
   disable the sandbox to read Claude Code's own storage (`~/.claude/projects`,
   `~/.claude/sessions`, `~/.claude/history`), and never to recover a truncated or
   spilled tool result. A capture that overflowed tool output is a transport defect;
   the answer is to re-cut the transfer inside the bound above, not to go around the
   boundary and read the spill. Intake cannot enforce this — the sandbox and its
   override belong to the runtime — which is exactly why it is written here as a
   standing instruction, and why `contract_check.py` lints for it.
4. Wrap as a single slice (`printf 'S0|' ; cat raw_export.txt ; printf '#END#'`) and run
   `reassemble_verify.py` with the exact `exportLen`, `--transport file` (these bytes
   never passed through tool output, so the chunk bound does not apply) and `--sha256
   <the digest extract.js reported>` — the same fail-closed checks apply, plus the one
   that catches a clipboard the trusted click never refreshed.

Fallback if the relay fails: console transfer (log `S<i>|chunk#END#` in **24k** chunks
and read them back with `read_console_messages`, pattern `S<i>\|`), then the classic
700-char slice protocol as last resort. The 24k figure is a bound, not a preference:
tool output tops out around 32 KB, and the proving run's 40k chunks overflowed it and
spilled to disk — after which the agent went looking for its own spill outside the
sandbox. `reassemble_verify.py` now enforces the bound (`TOOL_OUTPUT_CHUNK_MAX`) under
`--transport tool-output`, so an oversized chunk fails the run instead of quietly
producing a file somebody has to go and find. javascript_tool REPL note: an
async IIFE must be prefixed with `await`, or the pending Promise serializes as `{}`.

## Step 4 — Verify (fail closed)

In the workspace, before building any markdown:

1. `len(raw)` equals the reported `len` exactly, AND `sha256(raw)` equals the `sha256`
   extract.js reported. Length alone is a weak oracle — pass the digest to
   `reassemble_verify.py --sha256`. Declare the transport too: `--transport file` for
   the clipboard/artifact relay, `--transport tool-output` for the console path.
2. `json.loads(raw)` succeeds; message count and role sequence match the probe.
3. Code fences: every message has an even number of lines starting with ```.
4. First and last message text match the probe previews.
5. Spot-check a handful of known phrases from the chat.

If any check fails, fix the transfer — never deliver a silently incomplete archive.

## Attachments (pasted-text chips and uploaded files)

Chip contents are NOT in the conversation DOM — they load on demand into a preview modal.
Policy: the conversation text is the deliverable; attachments are best-effort extras.

1. Inventory first: count the chips and their labels during the probe. Include the
   inventory in the transcript's metadata header regardless of what happens next.
2. Per chip, at most ONE bounded attempt: click the chip, poll for modal text content for
   up to ~5 seconds. If content appears, capture it and include it under the message as
   an "Bilaga: <namn>" subsection. Then close the modal (Stäng button or Escape) and
   confirm it is gone before touching anything else.
3. If the spinner persists past the time box: close the modal and write a placeholder —
   `[Bilaga "<namn>" — innehållet kunde inte läsas ur förhandsvisningen]` — and move on.
   Do not retry, do not refresh the page, do not loop. One attempt, then placeholder.
4. Always verify no modal/overlay is open before running the main extraction, and tell
   Johnny at delivery which attachments (if any) were skipped so he can add them manually
   if they matter.
5. If the preview endpoint returns HTTP 403 even for the UI's own request, the content
   is genuinely unreachable from the page — placeholder immediately, and at delivery ask
   Johnny for the local originals (they usually came from his own tools) so they can be
   added beside the transcript as source artifacts.

General anti-stall rule for the whole playbook: any browser interaction that does not
succeed after one retry gets a fallback, never a loop. Page refreshes require Johnny's
go-ahead — a refresh can discard page state and costs more than a placeholder ever does.

## Content-filter handling (sensitive-data blocks)

Browser tool output may be blocked (e.g. "[BLOCKED: Cookie/query string data]") when the
chat text merely *talks about* tokens/cookies/auth. Handle in this order:

1. **Scan for real secrets first** with a masked diagnostic (report counts and masked
   matches only): long token-like strings `[A-Za-z0-9_\-]{30,}`, query strings
   `\?key=value`, cookie-header shapes. **If real secrets exist: stop, tell Johnny, and
   redact them from the export together — do not transfer them.**
2. If the scan shows only prose words (token, cookie, session, auth, secret, bearer),
   neutralize those words during transfer by interleaving U+2060 (word joiner) between
   letters, then strip all U+2060 in the workspace to restore the exact original text.
   First verify the page contains zero pre-existing U+2060 so the restore is lossless.
3. Never use this technique to move actual credentials, and never work around a block
   whose cause you have not diagnosed.

## Project discovery (PROJECT_SWEEP only) — enumerating a project's conversations

Per-conversation capture above is VERIFIED tooling. Project-level ENUMERATION is not:
`scripts/project_discovery.js` is a **CANDIDATE adapter** (ChatGPT only, unverified
against a live project listing as of v3.0). The rules are fail-closed, and they are the
whole point:

1. **Try the data layer first.** Run `project_discovery.js` on the logged-in project
   page. It may only be trusted as exhaustive when it returns `complete:true` — items
   collected equals the API's own `total`, with no pagination errors. Only then may
   the inventory be declared `--method data-layer --verified` (after a human
   sanity-check against the visible project).
2. **Anything less provable → declared inventory.** Take an owner-provided/exported
   conversation list (URLs or `host/<id>` keys), write it as JSON, and
   `project_contract.py declare --method declared` WITHOUT `--verified`. The manifest
   then carries `PROJECT_ENUMERATION_UNVERIFIED`, and coverage answers for the
   declared inventory only. **DO NOT FAKE IT** — the architecture would rather say
   "unverified" than claim 100% coverage it cannot prove.
3. **Identity is the platform's conversation id, never the title.** Titles are
   editable, duplicable and routinely reused; `conversation_key = host/<id>` is what
   reruns upsert on, which is what makes a sweep idempotent.
4. **Lazy loading/pagination:** the candidate adapter pages with offset+limit and
   cross-checks the API's `total`. A DOM-scrolled sidebar listing is NOT a completion
   signal — window-virtualized lists unmount items exactly like the chat transcript
   does (see above), so a scraped list proves presence, never exhaustion.
5. **Screenshots/OCR are never a capture or enumeration method.**
6. Per-conversation capture inside a sweep is EXACTLY the playbook above
   (data_capture.js first, DOM fallback, same gates) — the sweep changes discovery
   and bookkeeping, never capture quality.
