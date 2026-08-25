# Owner-clarifications template (`<slug>-owner-clarifications.md`)

The OWNER DELTAS layer. When the Phase 2.5 interview resolves an open question, the
owner's answer is often *more authoritative than the original brainstorm* — it is later,
and it is deliberate. Those answers must never survive only as conversation state.

    APPROVED PLAN  >  OWNER CLARIFICATIONS  >  BRIEF  >  RATIONALE  >  RAW

(subject to the higher ladder: current canonical repository authority, then any later
owner-approved spec/architecture/plan.)

This file exists only when the owner has actually answered something. Its absence is
normal and valid.

## Rules that matter more than the section list

- **Exact wording, not a paraphrase.** Record what the owner said, in their words. The
  brief may then be updated to reflect it — but the owner's sentence lives here.
- **Append-only.** Never edit or delete a recorded answer. If an answer is later
  overtaken, append a new `CLAR` that says so and cite the one it supersedes. The
  validator enforces this against git: the file must still *start with* its committed
  content.
- **Every entry is addressable.** `CLAR-001`, `CLAR-002`, … Plans and briefs cite them.
- **Every entry says what it resolves and what it changes.** `resolves:` names the open
  question (`Q3`, or `none`); `affects:` names the decisions, rejections or criteria whose
  meaning changes (`D4, AC7`). Both are validated against the brief's actual IDs, so a
  clarification cannot dangle.
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
- date: <YYYY-MM-DD>
- resolves: Q2
- affects: D3, AC3
- question: <the exact question that was put to the owner>
- owner_answer: <the owner's own wording, verbatim; may run over several
  paragraphs — everything after this marker until the next `## CLAR-` heading is
  preserved as the answer>

## CLAR-002
- date: <YYYY-MM-DD>
- resolves: none
- affects: D7
- question: <…>
- owner_answer: <…>
```

## Required per entry

| Field | Rule |
|---|---|
| `date` | When the owner answered. |
| `resolves` | A `Q` id from the brief, a comma-separated list, or `none`. Validated. |
| `affects` | `D` / `R` / `AC` / `Q` ids whose meaning changes. Validated. Optional. |
| `question` | The exact question asked. An answer without its question is not provenance. |
| `owner_answer` | Non-empty, verbatim. |

## After recording

1. Fold the answer into the brief (a Clarifications section, or by updating the affected
   decision/criterion) and into the design rationale where it changes the meaning.
2. Leave the transcript untouched.
3. Re-run the coverage gate — the question's disposition should now read `ANSWERED`.

## Open questions that are not answered

A question may never simply disappear. Every `Q` must end up in exactly one state:

| State | How it is recorded |
|---|---|
| `ANSWERED` | a `CLAR` entry resolves it |
| `EXPLICITLY_DEFERRED` | `open_questions_deferred: [Q4]` in the brief frontmatter |
| `OWNER_ACCEPTED_OPEN` | `open_questions_owner_accepted: [Q2]` in the brief frontmatter |
| `BLOCKING` | none of the above — **Plan Mode may not begin** |
