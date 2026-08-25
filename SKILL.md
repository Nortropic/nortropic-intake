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

**A fourth artifact appears after owner-approved planning — and only then:**

4. `<slug>-approved-plan.md` — the **approved plan**: HOW, in the execution order the
   owner approved in Plan Mode. Never generated from the brief, never written before the
   owner approves. It is bound to the brief by sha256, and it is what turns `status:
   planned` from a word into a provable state. See Phase 4 and
   `references/approved-plan-template.md`.

The package model, stated once:

    PRE-PLAN    WHAT (brief) / WHY (rationale) / RAW (transcript)
    POST-PLAN   WHAT / WHY / RAW / APPROVED PLAN (how + execution order)

**Authority order (highest wins):**

    current canonical repository authority
    (the target repo's constitution, rulebook, approved architecture)
      > later owner-approved spec / architecture / plan
      > approved intake plan
      > idea brief
      > design rationale
      > raw transcript

Intake artifacts preserve intent and provenance — they never supersede current
repository authority. A brainstorm cannot silently override a later approved
architecture; a rationale is not execution authority merely because it is detailed; an
old raw message cannot resurrect a rejected or superseded design. Within one intake
package, approved plan > brief > rationale > transcript on intentional interpretation.
If current canonical authority genuinely conflicts with the idea, surface it during
Clarify/Plan — never silently choose the old brainstorm.

The approved plan is the strongest intake artifact and still not execution authority. It
preserves owner-approved execution intent and its provenance; it does not override the
constitution, the rulebook, frozen gates, current published production truth, or a later
owner-approved transition. It is not a second runtime, not a second source of truth, and
not an execution-state ledger. Where the plan and current repository truth disagree, the
repository wins and the divergence is reported to the owner — never silently reconciled
in the plan's favour.

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
  offer/enter plan mode → owner approves the plan → Phase 4 persists and binds it →
  `status: planned` → fresh implementation session (Phase 5).

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

**`planned` is a mechanical state, not a word.** `status: planned | building | verified`
is valid only when the brief is bound to a valid approved-plan artifact: the file exists,
its sha256 matches `approved_plan_sha256`, it carries the right slug and owner-approval
metadata, none of its eleven required sections has been emptied out, and it is the current
(non-superseded) version. Without that, status may not advance past `clarified`. See
Phase 4.

Be precise about what is mechanical here, because the difference is the whole point:

- **Detection is mechanical and complete over the files present.**
  `scripts/plan_contract.py validate` fails closed on every one of those conditions, over
  the whole corpus, run by anyone with the files and nothing else. A `planned` brief with
  no provable plan cannot hide — it fails loudly as `LEGACY_PLAN_ARTIFACT_MISSING`. The
  corpus repo ships `hooks/pre-commit`, which runs the validator and refuses the commit on
  failure; once installed (`chmod +x` + the symlink, see the corpus `CLAUDE.md`) it keeps
  an unprovable state out of git history. It is a gate, not a wall: `--no-verify`
  overrides it, and it soft-passes if the skill is not installed on that machine. Both are
  the owner's explicit choice, never a silent default.
- **Invocation of Phase 4 is not mechanical.** Nothing forces a session to persist a plan
  in the first place — that is this skill's instruction, followed by a model. So the rule
  that matters most is the simple one: **never write `planned` without running the
  validator, and never skip Phase 4 after an approved plan.** The gate catches the state;
  it cannot catch a run that never reaches the gate.
- **Fidelity is not mechanical.** The validator proves a plan exists, is owner-approved by
  its metadata, is hash-bound, and has no hollowed-out sections. It cannot prove the prose
  matches what the owner approved. Persisting the approved output faithfully is a
  discipline, not a check.

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

## Phase 4 — Persist the approved plan (the only way to reach `planned`)

This phase exists because of a real failure: a large plan was brainstormed, taken through
intake, planned in Plan Mode, shortened into an execution prompt and successfully built
from — and then, after long-session compaction, the detailed future plan was simply gone.
The source files still existed; the approved plan had no durable home. The lifecycle said
`planned`; nothing on disk proved it. That must be impossible by construction.

**Trigger — all three, in this order, or this phase does not run:**

1. Clarification is complete (`status: clarified`).
2. Plan Mode has produced a plan.
3. Johnny has **explicitly approved that plan**. Silence is not approval; "looks good so
   far" mid-review is not approval; your own confidence is never approval.

Never generate an approved plan from the brief, the rationale or the transcript before
approval. If you cannot point at the owner-approved Plan Mode output, there is no
approved plan and the brief stays `clarified`.

**Steps.**

1. **Persist the exact approved plan** to `<slug>/<slug>-approved-plan.md` in the corpus,
   following `references/approved-plan-template.md`. Preserve the approved output with
   enough fidelity to resume execution: execution order, scope boundaries, decisions,
   deferred work, plan-critical rejected paths, owner-only transitions, stop conditions,
   acceptance criteria, current/next slice semantics, precedence/coherence patches. If
   the approved plan is long, persist the long plan. **A short execution prompt and an
   approved plan are not the same artifact** — the prompt may point at the plan, it may
   never replace it.
2. **Check the artifact alone, before touching the brief** (paths are absolute so the
   command runs from anywhere):

       PC=~/.claude/skills/nortropic-intake/scripts/plan_contract.py
       CORPUS=~/nortropic/innovation-intake
       python3 $PC validate --plan-file $CORPUS/<slug>/<slug>-approved-plan.md

   Fix findings; never bypass them.
3. **Bind** — write into the brief's frontmatter: `approved_plan`,
   `approved_plan_sha256` (the hash the check just printed, or `python3 $PC hash <file>`),
   `plan_version`, `plan_approved_at`, and `status: planned`. The brief points at the
   plan; it never duplicates it. Then run the full gate — `python3 $PC validate --slug
   <slug>` — and it must pass before the status change counts as done. If it cannot be
   made to pass, the brief goes back to `clarified`; it never stays at an unproven
   `planned`.
4. **Upsert the `INDEX.md` row** — status only. Still one row per IDEA; the plan file
   never gets its own row.
5. **Install the reload pointer** (below) where the work will actually happen.

**Reopening / versioning.** An approved plan is never silently rewritten. When Johnny
deliberately replans: keep the old file, add `status: superseded` +
`superseded_by_plan: <new file>` to it, write the new version as
`<slug>-approved-plan-v<N>.md` with `supersedes_plan: <old file>`, move the brief's
pointer and hash deliberately, and re-validate. `approval_state: approved` on the old
file stays — it was approved, and history is not edited to look cleaner. The validator
walks the chain in both directions and fails on a broken or orphaned link.

**Reload pointer (compaction & fresh-session continuity).** The durable plan lives on
disk; memory only needs enough to find it again. Do not store the plan in memory, and do
not depend on Claude Code's private session storage — the mechanism must survive
`/compact`, automatic compaction, a fresh session, and a different agent that has only
repository + intake access.

The supported surface is `CLAUDE.md` — project instructions are re-read in every session,
including after compaction, and they travel with the repository. Write a delimited block
into the target repo's `CLAUDE.md` (ask first; some repos forbid agent edits to it):

    python3 $PC pointer --slug <slug> --into <target-repo>/CLAUDE.md \
        --workstream <NAME> --target-repo <target-repo> --execution-pointer "<hint>"

It writes `ACTIVE_WORKSTREAM`, `ACTIVE_INTAKE_SLUG`, `ACTIVE_APPROVED_PLAN_PATH`,
`ACTIVE_APPROVED_PLAN_SHA256`, `TARGET_REPO`, `CURRENT_EXECUTION_POINTER` plus the reload
rule. It refuses to write a pointer to a plan that does not validate. The same block may
be mirrored into an auto-memory file or `/compact` instructions if Johnny uses them — as
a convenience copy only, never as the mechanism the design depends on.

**COMPACT INSTRUCTIONS — never summarize away active execution identity.** Preserve
across any compaction: active workstream, active intake slug, approved-plan path,
approved-plan sha256, target repository, and the current execution pointer if one exists.
After compaction, **re-read the approved plan from disk before deriving any future work**;
verify its sha256 against the recorded identity. Never reconstruct a missing approved plan
from conversational memory, from a draft, or from the transcript. If the plan file or its
recorded identity cannot be proven, **STOP with `PLAN_IDENTITY_UNAVAILABLE`** and say what
could not be proven.

**Pointer semantics — a cache, never a second truth.** The approved plan is durable owner
intent; the target repository is implementation truth; any pointer is convenience. On
resume, recompute the current position by reconciling the plan against repository state.
A stale pointer never overrides repository evidence: where they conflict, the repository
wins and the discrepancy is reported. `plan_contract.py resume` prints `POINTER_STALE=YES`,
**discards the stale hint entirely** (`NEXT_EXECUTION_POINTER=UNSET (stale pointer
discarded …)`) and reports the identity it proved from the corpus instead. A hint from a
pointer that still agrees with the corpus is passed through, and even then it is labelled
`HINT — unverified`: it is an input to reconciliation, never its result.

## Phase 5 — Fresh implementation session (start contract)

For an item at `planned` / `building`, a fresh session must be able to start from the slug
and target-repo access alone — no old conversation, no memory of the plan:

    python3 ~/.claude/skills/nortropic-intake/scripts/plan_contract.py \
        resume --slug <slug> --target-repo <repo> [--pointer <repo>/CLAUDE.md]

It proves the plan identity and prints the start block; then read the approved plan in
full, read current repository truth, and reconcile the two. Report:

    PLAN_IDENTITY=<path>@sha256:<hash>
    PLAN_STATUS=APPROVED
    PLAN_CURRENT_REPO_RECONCILIATION=<what the plan expects vs what the repo shows>
    NEXT_EXECUTION_POINTER=<next slice, computed — not copied from a hint>

The loader prints `PLAN_CURRENT_REPO_RECONCILIATION=PENDING_AGENT_READ` because it does
not and must not compute that itself; the last two lines are **yours to compute** from the
plan and the repository. Any `HINT — unverified` value the loader passes through is an
input to that comparison, never its answer.

Load order stays progressive: brief + approved plan are the working context; the design
rationale is read when design intent is genuinely needed; the raw transcript only in
targeted ranges. Then build, review adversarially, and move `status` to `building` /
`verified` per the actual lifecycle. If `resume` exits with `PLAN_IDENTITY_UNAVAILABLE`,
stop there — that is the fail-closed outcome, not a prompt to reconstruct the plan.

**Legacy items (no approved plan).** `idea` / `clarified` without a plan are perfectly
valid — nothing to backfill. An item already at `planned` / `building` with no plan
artifact is reported as `LEGACY_PLAN_ARTIFACT_MISSING` and is a FAIL, not a warning. The
only permitted recovery is bounded and manual: Johnny names the known source of the
approved plan, it is persisted with `plan_source: recovered-from-known-source` and
`fidelity: partial`, he verifies it, then it is bound and `fidelity: full` is set. The
transcript is never scraped automatically and a model reconstruction is never accepted as
the plan. If no known source exists, the honest outcome is `status: clarified` and a
re-plan.

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

After plan mode, ONLY once Johnny has explicitly approved the plan (Phase 4):

```
[ ] 10. Owner approval is explicit and quotable — else STOP; status stays clarified
[ ] 11. <slug>-approved-plan.md written per references/approved-plan-template.md:
        the exact approved plan, all eleven sections, nothing summarized away
        (execution order, scope, decisions, deferred, rejected, owner-only
        transitions, stop conditions, acceptance, current/next slice, precedence)
[ ] 12. plan_contract.py validate --plan-file <plan> PASSES; brief then bound with
        approved_plan + approved_plan_sha256 + plan_version + plan_approved_at +
        status: planned; plan_contract.py validate --slug <slug> PASSES after
        binding; INDEX.md status updated (one row per idea, no row for the plan)
[ ] 13. Reload pointer installed where the work happens (plan_contract.py pointer
        --into <target-repo>/CLAUDE.md, asked first); resume verified:
        plan_contract.py resume --slug <slug> --target-repo <repo> prints
        PLAN_IDENTITY + PLAN_STATUS=APPROVED
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
  `<slug>/` in the root. After owner approval, `<slug>-approved-plan.md` joins them —
  version N≥2 is `<slug>-approved-plan-v<N>.md`, and `plan_version` must equal the
  version in the filename.
- The approved plan is immutable after approval: substantive change means a new version
  with supersession recorded in both directions, never an in-place rewrite. Owner-approved
  execution intent is never mutated without a trace.
- Never let a pointer become state: the approved plan is durable intent, the target repo
  is implementation truth, `CURRENT_EXECUTION_POINTER` is a hint that must be recomputed
  on resume. Repository evidence wins on conflict, and the discrepancy is reported.
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
  brief rubric, rationale rubric, contract lint, approved-plan falsification suite) —
  run them after any change to this skill; see `evals/README.md`.
