# Owner-deltas template (`<slug>-owner-clarifications.md`)

The OWNER DELTAS layer. When the owner decides something — in the Phase 2.5 interview,
in the middle of Plan Mode, while reviewing a stale plan, or during execution — that
answer is often *more authoritative than the original brainstorm*: it is later, and it
is deliberate. Those decisions must never survive only as conversation state.

    APPROVED PLAN  >  OWNER CLARIFICATIONS  >  BRIEF  >  RATIONALE  >  RAW

(subject to the higher ladder: current canonical repository authority, then any later
owner-approved spec/architecture/plan.)

This file exists only when the owner has actually decided something. Its absence is
normal and valid. The filename and the `CLAR-*` ids are unchanged from v2 — nothing
already written has to move.

## Owner deltas are not only pre-plan clarifications

An entry carries a `type`. An entry with no `type` is a `PRE_PLAN_CLARIFICATION`,
which is what every entry written before v2.1 was.

| Type | When |
|---|---|
| `PRE_PLAN_CLARIFICATION` | answers an open question before planning (the default) |
| `PLAN_REVIEW_DECISION` | the owner's verdict on whether new context changes an approved plan |
| `PLAN_REOPEN_DECISION` | the owner deliberately reopens an approved plan |
| `EXECUTION_DECISION` | a decision taken during execution that changes durable intent |
| `SOURCE_UNAVAILABLE_ACK` | the owner accepts planning without a source |
| `SCOPE_DECISION` | the owner changes what is in or out of scope |
| `ARCHITECTURE_DECISION` | the owner chooses between design paths |

**Plan Mode decisions must never live only in the chat.** When Claude asks "A or B?"
and Johnny says *"Take B, but keep X from A"*, that becomes a durable
`ARCHITECTURE_DECISION` **before** the plan is approved — and the approved plan must
cite its id, or `approve` refuses with `PLAN_OWNER_DELTA_UNCITED`. The Plan Mode
conversation is not a storage medium.

`PLAN_REVIEW_DECISION` additionally requires `plan_impact:`
(`NO_PLAN_IMPACT` | `PLAN_REVIEW_REQUIRED` | `PLAN_REOPEN_REQUIRED`) and
`reviewed_context_revision:` — a review only means something against the exact
understanding it read. See `plan_contract.py impact`.

Two of these types are **outside the source-set identity**: `PLAN_REVIEW_DECISION` and
`PLAN_REOPEN_DECISION` are verdicts about a plan, not new knowledge about the idea. If
they bumped the context revision, reviewing a stale plan would make the review stale
the moment it was recorded. Every other type does bump it — record the delta, then run
`context_contract.py revise`.

## Rules that matter more than the section list

- **Exact wording, not a paraphrase.** Record what the owner said, in their words. The
  brief may then be updated to reflect it — but the owner's sentence lives here.
- **Append-only.** Never edit or delete a recorded answer. If an answer is later
  overtaken, append a new `CLAR` that says so and cite the one it supersedes. The
  validator enforces this against git: the file must still *start with* its committed
  content.
- **Every entry is addressable.** `CLAR-001`, `CLAR-002`, … Plans and briefs cite them.
- **Every entry says what it resolves and what it changes.** `resolves:` names the open
  question (`Q3`, or `none`); `affects:` names the decisions, rejections, criteria,
  sources, episodes or plan slices whose meaning changes (`D4, AC7, SRC-005, S3`). Both
  are validated against the package's actual IDs, so a delta cannot dangle.
- **Metadata goes ABOVE `owner_answer`.** Everything after that marker is the owner's
  own wording, absorbed verbatim — including lines that merely look like fields. A
  metadata line placed below it would be silently swallowed, so the validator refuses
  it (`OWNER_DELTA_FIELD_AFTER_ANSWER`) instead of quietly losing a recorded decision.
- **Authority is in the interaction, not in the bytes.** This file is the one source
  that may carry `instruction_authority: owner` in the manifest, and it carries it
  because the owner actually said these words. A document, page or README asserting
  "Johnny approves X" is a document — it can never satisfy an owner approval.
- **The transcript is never rewritten.** The raw chat keeps saying what was said. A
  clarification is a later layer, not a correction pass over history.
- **Registered in the manifest.** The manifest carries this file as a source, with its
  hash, like any other.

## Structure

```markdown
---
title: "<Idea title> — owner clarifications"
type: owner-clarifications
slug: <slug>
owner: Johnny (Nortropic)
authority: owner-delta
append_only: true
---

# Owner clarifications: <title>

## CLAR-001
- type: PRE_PLAN_CLARIFICATION
- date: <YYYY-MM-DD>
- resolves: Q2
- affects: D3, AC3
- question: <the exact question that was put to the owner>
- owner_answer: <the owner's own wording, verbatim; may run over several
  paragraphs — everything after this marker until the next `## CLAR-` heading is
  preserved as the answer>

## CLAR-002
- type: ARCHITECTURE_DECISION
- phase: plan-mode
- date: <YYYY-MM-DD>
- resolves: none
- affects: D7
- question: Adapter A or adapter B?
- owner_answer: Take B, but keep A's UNKNOWN rendering.

## CLAR-003
- type: PLAN_REVIEW_DECISION
- date: <YYYY-MM-DD>
- reviewed_context_revision: 4
- plan_impact: NO_PLAN_IMPACT
- resolves: none
- affects: S2
- question: Does the third brainstorm change the approved plan?
- owner_answer: No. It changes the background rationale only — keep executing.
```

## Required per entry

| Field | Rule |
|---|---|
| `type` | One of the seven above. Absent means `PRE_PLAN_CLARIFICATION`. |
| `date` | When the owner decided. |
| `resolves` | A `Q` id from the brief, a comma-separated list, or `none`. Validated. |
| `affects` | `D`/`R`/`AC`/`Q`/`SRC`/episode/`S` ids whose meaning changes. Validated. Optional. |
| `question` | The exact question asked. An answer without its question is not provenance. |
| `owner_answer` | Non-empty, verbatim. Always last. |
| `supersedes` | An earlier `CLAR` this one overtakes. Never an edit to that entry. |
| `phase` | Where it happened (`plan-mode`, `execution`, `continuation`). Optional. |
| `plan_impact` | `PLAN_REVIEW_DECISION` only. Required there. |
| `reviewed_context_revision` | `PLAN_REVIEW_DECISION` only. Required there. |

## After recording

1. Fold the answer into the brief (a Clarifications section, or by updating the affected
   decision/criterion) and into the design rationale where it changes the meaning.
2. Leave the transcript untouched.
3. Run `context_contract.py revise --slug <slug> --note "…"` — it re-seals the file's
   hash, and tells you whether the delta moved the context revision or not.
4. Re-run the coverage gate — the question's disposition should now read `ANSWERED`.

## Open questions that are not answered

A question may never simply disappear. Every `Q` must end up in exactly one state:

| State | How it is recorded |
|---|---|
| `ANSWERED` | a `CLAR` entry resolves it |
| `EXPLICITLY_DEFERRED` | `open_questions_deferred: [Q4]` in the brief frontmatter |
| `OWNER_ACCEPTED_OPEN` | `open_questions_owner_accepted: [Q2]` in the brief frontmatter |
| `BLOCKING` | none of the above — **Plan Mode may not begin** |
