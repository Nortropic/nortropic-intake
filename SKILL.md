---
name: nortropic-intake
description: Load a brainstorm into Claude Code as the understanding and context of what Johnny intends to implement. Captures a conversation — the active ChatGPT or Claude tab, this Claude conversation, or (in local Claude Code with Chrome) any chat by URL — with a host-aware, fail-closed extraction playbook, then distills it into a self-contained idea brief (decisions incl. rejected paths, EARS acceptance criteria, open questions) plus a design-rationale file preserving why the design took its shape (reasoning chains, rejections, trade-offs, message-level provenance), with the verbatim transcript kept as linked evidence. Delivers all three as real .md files into the idea-corpus repo (idébanken) and, when implementing now, into the current working session so Claude Code can plan and build from them; it writes files and an index row but never commits or pushes. Use whenever Johnny asks to harvest, load or bring a brainstorm or chat into Claude Code, "harvest this URL", "arkivera vart samtal", "kor intake", "spara/lägg idén i idébanken" / park an idea for later, give Claude Code the context for an idea, or turn a discussion into an implementation brief — Swedish or English, even if unnamed. Do NOT use merely to discuss or summarize a chat, or to edit an existing brief.
---

# Nortropic intake: brainstorm → understanding for Claude Code

**One job:** turn a brainstorm into the understanding Claude Code needs to implement it.
The output is three local files — a progressive-disclosure ladder, smallest first:

1. `idea-<slug>.md` — the **execution brief**: the smallest self-contained context from
   which Claude Code correctly understands WHAT Johnny intends. The default (and normally
   only) intake artifact loaded into the implementing/planning session.
2. `<slug>-design-rationale.md` — the **design rationale**: WHY the brief ended up as it
   did — reasoning chains, decisions with fuller why, rejected paths and the failure each
   would create, trade-offs, a retrieval map into the transcript. Not preloaded; read on
   demand when architecture choices are ambiguous, two implementations both satisfy the
   brief, a reviewer needs design intent, or a premise may have changed.
3. `<slug>-full-chat.md` — the **raw transcript**: complete verbatim evidence. Never
   preloaded merely because it exists; read targeted message ranges only when the
   rationale is insufficient, exact wording matters, or provenance must be audited.

Right context, not maximum context: execution needs the *what*; architecture sometimes
needs the *why*; raw history is retrieved only when ambiguity remains. Three different
jobs — never three copies of the same content.

**Authority order (highest wins):**

    current canonical repository authority
    (the target repo's constitution, rulebook, approved architecture)
      > later owner-approved spec / architecture / plan
      > idea brief
      > design rationale
      > raw transcript

Intake artifacts preserve intent and provenance — they never supersede current
repository authority. A brainstorm cannot silently override a later approved
architecture; a rationale is not execution authority merely because it is detailed; an
old raw message cannot resurrect a rejected or superseded design. Within one intake
package, brief > rationale > transcript on intentional interpretation. If current
canonical authority genuinely conflicts with the idea, surface it during Clarify/Plan —
never silently choose the old brainstorm.

Why distill: a coding agent works best from a decision-only brief — a raw transcript
contains dead ends it may faithfully implement (this really happened: a plan rejected two
messages later). All three are kept because Johnny wants the *what* (brief), the *why*
(rationale) and the *evidence* (transcript), each in its lane.

**The corpus repo is the durable home; committing and pushing are not this skill's job.**
Every delivery writes the three files into the corpus repo
`~/nortropic/innovation-intake/<slug>/` and upserts one row in its root `INDEX.md`
(see Phase 3) — plain file writes in the working tree. The skill never commits, never
pushes, never uploads to Drive; those remain separate, explicit steps Johnny asks for
himself. Whether a run *also* continues into clarification and plan mode is decided by
the routing question in Phase 0.5.

## Where it runs & where the brief lands

The capture source depends on the environment; the deliverable is always the three files
as local context for the current work.

- **Local Claude Code** (the main case — shell + Chrome via `claude --chrome`): capture the
  active/opened tab, this conversation, or any chat by URL (Source C). Write the three
  files into the corpus repo (and read the brief into the session when implementing now);
  the routing answer from Phase 0.5 decides whether the run stops at storage (idébank)
  or continues into the Phase 2.5 interview and plan mode.
- **Cowork / Chrome side panel, or a plain Claude chat** (no access to Johnny's project
  files): capture the ChatGPT/Claude tab (Source A) or this conversation (Source B), then
  deliver the three files to Johnny so he can drop them into his Claude Code session.

## Phase 0 — Scope (usually silent)

Derive a short kebab-case slug from the chat's topic (e.g. `gauntlet-quality-layer`).
Only ask Johnny when something is genuinely ambiguous: unclear slug, or the chat clearly
contains several separate ideas that deserve separate briefs. Otherwise state your
interpretation in one line and proceed — he may be away from the keyboard.

## Phase 0.5 — Route the idea (ask FIRST)

Immediately after the slug, before any capture: ask Johnny (AskUserQuestion) — or follow
what he already said in the request — where this idea goes. Two routes, one question:

- **IDÉBANKEN** (store for later): capture → distill → corpus check + link + index →
  store with `status: idea`, open questions left INTACT — **no** Phase 2.5 interview now;
  they are clarified later, when the idea is pulled to build. Then STOP. Do not enter
  plan mode.
- **IMPLEMENTERA NU** (build this session): capture → distill → corpus check + link +
  index → Phase 2.5 interview (clarify the open questions) → `status: clarified` →
  offer/enter plan mode.

Unattended default: if Johnny is not at the keyboard — a scheduled/headless run, or
AskUserQuestion cannot be answered (use the same presence signal Phase 2.5 uses to skip
the interview) — do NOT block on the routing question. Default to the idébank path: it is
the safe, non-destructive choice — archives with `status: idea`, holds no interview,
starts no plan mode or build. Never default to implement-now unattended. State the
assumption at delivery ("Ingen vid tangentbordet — defaultade till idébanken; säg till om
du vill implementera nu istället") so Johnny can redirect.

Both routes ALWAYS run the corpus check (Phase 2.8 — never store or build a duplicate)
and ALWAYS write brief + rationale + transcript to the corpus repo with an `INDEX.md`
row — the idébank advantage is that a build session months later receives a small
execution brief, a retrievable design rationale and raw provenance, without having to
rediscover the intellectual history. Routing changes only (a) whether Phase 2.5 runs now
or is deferred, and (b) whether the run ends at storage or continues into plan mode.

When an idea-bank idea is later pulled to build, that IS the implement-now flow, started
from the stored brief instead of a fresh capture: corpus re-check (has anything
superseded or joined it since?), Phase 2.5 interview, `status: clarified`, plan mode.
The `status` frontmatter field models the whole lifecycle:
`idea → clarified → planned → building → verified` (plus terminal `superseded`).

## Phase 1 — Capture the conversation

First identify the source; the two paths differ completely in mechanics but produce the
same transcript format.

**Source A — a ChatGPT or Claude chat tab.** Read `references/extraction.md` **before
writing any browser JavaScript**, and **try the data layer first**: run
`scripts/data_capture.js` (Step 0 of the playbook — host-aware, with VERIFIED adapters
for both chatgpt.com and claude.ai) — it fetches the conversation JSON from the site's
own backend API with the page's own session, walks the parent chain into a linear
thread (`current_node → parent` on ChatGPT; `current_leaf_message_uuid →
parent_message_uuid` on claude.ai), and keeps only user-visible turns. It is lossless
and immune to the window-virtualized DOM (turns unmount offscreen; scraping a long chat
stalls 15+ minutes and misses messages). Only when the endpoint fails or returns
non-text, fall back to the DOM playbook in the same file (probe → render pass →
extract; both sites' selectors verified Aug 2026 — on drift, see Site adapters and
`OVERRIDE_TURN`). Both paths end in the same slice transfer + fail-closed verification.

**Source B — the current Claude conversation ("arkivera vårt samtal").** No browser, no
extraction: write the transcript directly from your own context. Rules that keep it
honest: reproduce Johnny's and your messages verbatim — never paraphrase; skip tool-call
internals, but note delivered artifacts in one bracketed line where they mattered to a
decision; if older history has been compacted by the system, mark that segment
`[Avsnitt komprimerat av systemet — ej ordagrant]` and set `fidelity: partial` in the
metadata header instead of pretending it is verbatim. The whole extraction playbook and
checklist steps 1–5 collapse into one item: transcript written from context with the
fidelity check done. The interview happens in Phase 2.5, after the summary (not before) —
see there.

**Source C — a chat by URL (local Claude Code + Chrome only).** When Johnny says "harvest
this URL" / "skörda den här" with a link, open it with the Chrome integration in his
logged-in browser, then capture exactly as Source A: **data layer first**
(`scripts/data_capture.js` is host-aware — verified adapters for both a chatgpt.com and
a claude.ai URL; the conversation id is the last URL segment), DOM playbook only as
fallback; slice transfer and verification apply unchanged (the browser tools are the
same `claude-in-chrome` tools the playbook targets). Never modify anything on the page —
read only. Two notes: on claude.ai the DOM fallback is a LAST resort — the transcript is
hard-virtualized (see the Claude adapter notes in the playbook's Site adapters section)
so the data-layer adapter is strongly preferred; and if the URL is the very conversation
you are running in, prefer Source B (writing from context is higher fidelity than
scraping your own transcript). The point of this source is that one local agent harvests
the brainstorm and immediately has it as context to plan and build.

Non-negotiable quality gates before Phase 2 (fail closed — do not hand over silently
incomplete understanding):

- Message count and role sequence captured and stated.
- First and last message verifiably present in the assembled export.
- No truncation: reassembled transfer passes the length + JSON-parse checks from the playbook.
- Code fences balanced in every message.
- Attachments (pasted-text/file chips) inventoried — on the data-layer path from message
  metadata, on the DOM path from the chips; contents captured best-effort with a strict
  time box per chip — a hanging preview modal must produce a placeholder, never a
  stalled run (see the Attachments section of the playbook). Report skipped attachments
  at delivery.

Then build `<slug>-full-chat.md`: metadata header (source project + chat title, URL,
export date, message count, one-line purpose = what Johnny intends to implement), a short
"Innehåll i korthet" paragraph, a note explaining citation-chip lines (ChatGPT), then every
message under `## Meddelande N — <Johnny (användare) | ChatGPT/Claude (assistent)>`
separated by `---`. Keep message content verbatim — no rewriting, no summarizing, no
cleanup beyond the documented junk-line removal.

## Phase 2 — Distill: execution brief + design rationale

Two derived artifacts, each built from the transcript with message-level provenance.
Different jobs: do NOT generate the rationale by copying the brief and adding prose —
derive it independently from the source.

**A. The execution brief.**
Read `references/brief-template.md` and follow its structure exactly. The essence:

- **Self-contained**: readable without the transcript; names systems, files, interfaces.
- **Right altitude**: destination + quality bar, never an implementation plan.
- **Decision log**: what was decided AND what was explicitly rejected in the chat, each
  with a one-line rationale ("— because …"). Rejected paths are the most dangerous
  omissions — an agent given only the transcript may implement a well-specified idea
  that was later discarded. The rationale line carries the most important *why* into the
  brief; the fuller design logic lives in the design rationale, and the complete
  reasoning stays in the transcript — pulled on demand in the Clarify step via the
  retrieval ladder brief → rationale → targeted transcript ranges (all layers preserved,
  none polluting the others).
- **EARS acceptance criteria** ("WHEN … THE system SHALL …") that map ~1:1 to tests.
- **Explicit out-of-scope**, an end-to-end **verification** step, **open questions** for
  Claude Code to interview Johnny about before planning, and the **process footer**
  (Clarify → Plan → Implement fresh → Adversarial review).
- Target 2–3 pages (~1000 words); hard max 1600 for genuinely high-complexity sources
  (see the template's length rule). Front matter `status` set by routing: `idea` on the
  idébank route; the Phase 2.5 interview sets `clarified`.

Handling side-tracks (a brainstorm is full of them): sort every tangent into one of three
buckets so none is silently dropped — **decided** (goes in the decision log), **rejected**
(logged with its "because"), or **explored-but-unresolved** (becomes an open question).
The single most dangerous mistake is mis-labelling: reading an explored side-track as a
decision, or burying a real decision as a side-track. Phase 2.5 exists to catch exactly that.

**B. The design rationale.**
Read `references/design-rationale-template.md` and follow its structure exactly. The
essence: preserve the design logic — core thesis, reasoning chain, decisions with fuller
why than the brief's one-liners, explicit rejections with the failure each would create,
explored-but-unresolved ideas kept unresolved, trade-offs, metaphor → functional-principle
translations where the source uses metaphors, external evidence marked MENTIONED IN
SOURCE vs INDEPENDENTLY VERIFIED, pivots — every material claim with a `(← msg N–M)`
source tag, closing with a retrieval map (topic → message range) and a what-to-load-when
section. It is NOT an implementation plan, a summary, or a copy of either neighbor, and
it never claims reasoning absent from the user-visible source.

## Phase 2.5 — Confirm against the side-tracks, then interview (when Johnny is present)

Run this whenever Johnny is at the keyboard (local Claude Code, or brainstorming live) —
**after** the summary, because only the distilled brief separates signal from the chat's
side-tracks, so the interview is grounded in a clean picture instead of the messy thread.

1. Show a tight summary: the **decisions**, the **parked side-tracks** (rejected +
   explored-but-unresolved), and the **open questions** — only the compact material
   needed for validation; never dump the design rationale.
2. Interview with `AskUserQuestion`, in this order: (a) are the decisions right as stated?
   (b) are the parked side-tracks correctly parked — none of them is actually a decision
   you made? (c) answers to the open questions.
3. Fold his answers into the brief (a "Clarifications" section), promote any confirmed
   side-track to a decision, and set `status: clarified`. Now the understanding is
   validated, not just extracted.

Owner corrections change the DERIVED artifacts only: update the brief as above, and
update the design rationale wherever the correction changes its meaning — a decision
changed in the interview is recorded in both as later/current intent, citing the
interview. The raw transcript is immutable evidence: never rewrite it to make history
look cleaner.

If Johnny is NOT present (a harvest running unattended), skip the interview: leave the open
questions and parked side-tracks in the brief for the build-phase Clarify step, and say so
at delivery. On the **IDÉBANK route this phase is always skipped by design** — open
questions stay intact until the idea is pulled to build.

## Phase 2.8 — Corpus check: cross-link + dedup (both routes, before delivery)

Before delivering anything, scan the corpus repo for related briefs: read every
`<slug>/idea-*.md` frontmatter (title, slug, plus which systems/tags the brief touches)
and compare against the new idea on slug, title, keywords and shared system. Outcomes:

- **Probable duplicate or evolution of an existing brief** → STOP and ask Johnny
  (AskUserQuestion): does the new brief **SUPERSEDE** the old one, is it **RELATED**, or
  are they distinct? Fail closed — never store or build a silent duplicate.
- **SUPERSEDES**: the new brief gets `supersedes: [<old-slug>]`; the old brief is edited
  to `status: superseded` + `superseded_by: <new-slug>`, and its `INDEX.md` row updated.
- **RELATED**: both briefs list each other under `related: [<slug>, …]`.
- **Distinct**: no links; proceed.

A supersede applies to the idea package as a whole: the old slug keeps its rationale and
transcript, and the supersede/related links on the briefs keep the package navigable.
Never create a new idea merely because rationale changed — rationale updates stay under
the same slug.

Precedent in the corpus: `gauntlet-wayfinder` supersedes `gauntlet-quality-layer` (the
earlier Drive-era brief of the same idea).

## Phase 3 — Deliver into the corpus (and, on implement-now, as working context)

The deliverable is the three files in the corpus, indexed — plus, on the implement-now
route, the brief available to the current session.

**In local Claude Code** (the main case): write all three into the corpus repo
`~/nortropic/innovation-intake/<slug>/` — the idea folder sits directly in the repo root
(`<slug>/`, not `ideas/<slug>/`; the brief template's `intended_repo_path` agrees).

- `idea-<slug>.md` — the execution brief (primary context).
- `<slug>-design-rationale.md` — the design rationale (on-demand companion).
- `<slug>-full-chat.md` — the transcript (linked evidence).

Then upsert this idea's row in `INDEX.md` at the repo root — one row per IDEA, never per
artifact (the `links` field may point at brief/rationale/chat if useful, but the INDEX
never becomes a document inventory):
`slug | title | STATUS | created | links` — the STATUS column shows idea vs clarified vs
building, so the bank and the work-in-progress are visible in one glance. Update the row
again whenever a corpus check changes links or status (e.g. a supersede). The repo root
also carries a `CLAUDE.md` that orients any Claude Code session in the corpus (structure,
conventions, trust layer, pointer to INDEX.md); keep it accurate if conventions change.
Never overwrite an existing file silently — if either name exists, ask version vs replace
(the Phase 2.8 corpus check should already have surfaced a same-idea collision).

Route endings differ (Phase 0.5): on **IDÉBANK**, report the paths + a 3–5 sentence
Swedish summary of what he intends to implement, and stop — no interview, no plan mode.
On **IMPLEMENTERA NU**, additionally read the brief into the working session as context,
give the same Swedish summary, and **offer to take the brief into plan mode** (the
natural next step — this skill hands off the understanding; the building continues from
there).

**Implement-now context policy (explicit and testable).** Default main context is
`idea-<slug>.md` and nothing else from the intake package. Do NOT automatically load
`<slug>-full-chat.md`, and do not dump the full design rationale into main context
either — the architect/planner reads the rationale when the work genuinely requires it.
Access by role:

- implementer → brief
- architect / planner → brief, + rationale when useful
- falsifier / reviewer → brief, + rationale for intent comparison
- targeted research subagent → selected rationale sections, + selected raw-chat message
  ranges if evidence is needed (use the rationale's retrieval map)

The full transcript is durable evidence, not default working memory.

**Elsewhere** (Cowork / Chrome side panel, or a plain Claude chat — no access to his
project files): deliver all three files to Johnny (SendUserFile) with the same Swedish summary,
so he can drop them into the corpus himself.

The skill writes files and the index row — it does **not** commit, push, or upload to
Drive. Making the corpus state durable in git history is a separate, explicit decision
Johnny makes himself.

## Execution checklist

Copy this into your working notes at the start of a run and tick items off — the order
matters, and skipped steps are exactly where past runs went wrong:

```
[ ] 0.  Slug decided (ask only on genuine ambiguity / multiple ideas)
[ ] 0.5 Route decided FIRST (asked, or already stated): IDÉBANK or IMPLEMENTERA NU
        (unattended — Johnny not at the keyboard: do not block; default to IDÉBANK,
        never implement-now, and state the assumption at delivery)
[ ] 1.  Data-layer capture (scripts/data_capture.js): count, roles, first/last
        previews, total chars printed; size sanity-checked (visible text, no raw model);
        attachments inventoried from metadata
[ ] 2.  FALLBACK ONLY if step 1 failed or returned non-text: DOM playbook —
        probe (scripts/probe.js), render pass until 0 expanders, attachments one
        time-boxed attempt each, extract (scripts/extract.js; on DLP block: masked
        secret scan FIRST)
[ ] 3.  Slice transfer complete, every slice ends with #END#
[ ] 4.  Verification (scripts/reassemble_verify.py): length, JSON, roles, fences
[ ] 5.  Truncation smell check: no code block starts/ends mid-construct — else back to 2
[ ] 6.  full-chat.md built (metadata, attachment list, messages verbatim)
[ ] 7.  idea-<slug>.md per references/brief-template.md (decisions with "because" and
        (← msg N) provenance, rejected paths, side-tracks sorted, EARS criteria,
        open questions, invariants pointer, design_rationale link in frontmatter)
[ ] 7.4 <slug>-design-rationale.md per references/design-rationale-template.md —
        derived from the transcript independently of the brief; (← msg N–M) on every
        material claim; rejections with the failure each would create; unresolved
        stays unresolved; retrieval map + what-to-load-when; NOT a spec, summary or
        copy of brief/transcript
[ ] 7.5 IMPLEMENTERA NU only (and Johnny present): compact summary shown (decisions,
        parked side-tracks, open questions — never the full rationale), interview held,
        answers folded into BOTH brief and rationale where meaning changes,
        status: clarified; transcript untouched. IDÉBANK: skip by design — open
        questions stay intact, status: idea
[ ] 7.8 Corpus check (Phase 2.8): related briefs scanned, supersedes/related/
        superseded_by set, old brief + index updated on supersede; asked on any
        probable duplicate — never a silent one
[ ] 8.  All three files written to the corpus repo <slug>/ + INDEX.md row upserted
        (one row per idea, not per artifact; IMPLEMENTERA NU: the brief — and only
        the brief — read into the working session)
[ ] 9.  Swedish summary + skipped-attachment list. IDÉBANK: stop here.
        IMPLEMENTERA NU: offer to take the brief into plan mode
```

Source B (current Claude conversation): steps 1–5 are replaced by
`[ ] transcript written from context, verbatim, fidelity noted` and
`[ ] live interview held on unresolved decisions before the brief`.
Steps 0 and 6–9 apply unchanged.

Source C (chat by URL, local Claude Code): prepend `[ ] opened URL in Chrome,
read-only` before step 1; steps 1–9 then run exactly as above (same playbook).

Delivery (steps 8–9): corpus repo + INDEX.md row in local Claude Code, or hand the
files to Johnny elsewhere. No commit, no push, no Drive — see Phase 3.

## Conventions

- Transcript file: Swedish metadata/headers. Brief and rationale: English (agent-facing
  convention in this system), Swedish is fine if Johnny asks.
- Naming: `idea-<slug>.md` (brief), `<slug>-design-rationale.md` (rationale) and
  `<slug>-full-chat.md` (transcript), delivered together into the corpus repo under
  `<slug>/` in the root.
- The raw transcript is immutable once its capture passed verification for that intake
  event: derived interpretation may evolve; the capture is never rewritten because later
  clarification changed the design. If the CAPTURE itself was incomplete or incorrect,
  correct it explicitly — re-run the capture, tell Johnny what was wrong, and keep the
  `fidelity:` metadata truthful — never edit history silently. Compacted/unavailable
  history keeps the existing fail-closed partial-fidelity semantics.
- Never place credentials or secrets in the export; see the content-filter section of
  `references/extraction.md` for how to handle sensitive-looking content safely.
- Scope guard: this skill produces understanding and stores it in the corpus — file
  writes + one index row, nothing more. No commit, no push, no Drive upload. If Johnny
  wants the corpus committed or archived elsewhere, that is a separate step he asks for
  explicitly.
- Repeatable evals live in `evals/` (trigger queries, golden capture signature,
  brief rubric, rationale rubric, contract lint) — run them after any change to this
  skill; see `evals/README.md`.
