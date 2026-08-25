# Context-delta template (`<slug>-context-delta.md`)

One idea, many source episodes. This file answers the only question a returning owner
or planner actually asks:

    WHAT CHANGED IN OUR UNDERSTANDING?

One `## REV-<N>` block per context revision after the first. Revision 1 is the initial
capture — there is nothing before it to differ from, so it has no block.

    python3 ~/.claude/skills/nortropic-intake/scripts/context_contract.py \
        delta --slug <slug> [--since N]

## Rules that matter more than the field list

- **Stable IDs, not narration.** Every field names `D`/`R`/`Q`/`AC`/`SRC`/episode ids.
  This is not an AI diary of the session; it exists so the owner and the planner can
  see the intellectual change in ten seconds.
- **`none` is an answer; an absent line is not.** Write `none` when nothing changed in
  that dimension. A missing field reads as "we did not look".
- **Append-only.** A block describes what was understood at that revision and is never
  rewritten. A correction is the next revision, not an edit to the last one.
- **It is checked against evidence, not believed.** Two independent witnesses:
  the manifest says which sources arrived with which episode (`DELTA_SOURCE_OMITTED`
  if one is missing here), and git says which brief IDs did not exist at the previous
  revision (`DELTA_UNDERSTATED` if a new decision, rejection or open question is not
  reported). Understating a change is a failure, not a style choice.
- **A reversal needs an owner.** If `REVERSED_DECISIONS` is non-empty, `authorized_by:`
  must name an owner delta of type `ARCHITECTURE_DECISION`, `SCOPE_DECISION` or
  `PLAN_REOPEN_DECISION`. A new brainstorm that reverses settled decisions with no
  owner decision behind it is a **SUPERSEDE wearing a continuation's clothes** — and
  the validator says so.
- **`POTENTIAL_PLAN_IMPACT` is a signal, never a verdict.** It starts with
  `NO_PLAN_IMPACT`, `PLAN_REVIEW_REQUIRED`, `PLAN_REOPEN_REQUIRED` or `NONE`, then the
  reason. The actual verdict on an approved plan is the owner's, recorded as a
  `PLAN_REVIEW_DECISION` owner delta — see `plan_contract.py impact`.

## Structure

```markdown
---
title: "<Idea title> — context delta"
type: context-delta
slug: <slug>
owner: Johnny (Nortropic)
append_only: true
---

# Context delta: <title>

## REV-2
- at: <YYYY-MM-DD>
- episodes: CHAT-002
- source_set_sha256: <the identity the manifest recorded for revision 2>
- NEW_SOURCES: SRC-004, SRC-005
- NEW_DECISIONS: D7
- CHANGED_DECISIONS: D3
- REVERSED_DECISIONS: D2
- NEW_REJECTIONS: R4
- REOPENED_REJECTIONS: none
- RESOLVED_QUESTIONS: Q4
- NEW_OPEN_QUESTIONS: Q7
- NEW_CONSTRAINTS: none
- NEW_EXTERNAL_EVIDENCE: SRC-005
- POTENTIAL_PLAN_IMPACT: PLAN_REVIEW_REQUIRED — S3 assumes the adapter shape D2 replaced
- authorized_by: CLAR-004
```

## Fields

| Field | Meaning |
|---|---|
| `at` | When this revision was sealed. |
| `episodes` | The episode id(s) that arrived with this revision. |
| `source_set_sha256` | Must match the manifest's `revision_history` entry for this revision. |
| `NEW_SOURCES` | Every `SRC` that arrived with this revision. Checked against the manifest. |
| `NEW_DECISIONS` | `D` ids that did not exist before. Checked against git. |
| `CHANGED_DECISIONS` | `D` ids whose meaning moved without being reversed. |
| `REVERSED_DECISIONS` | `D` ids the owner turned around. Requires `authorized_by`. |
| `NEW_REJECTIONS` | `R` ids added. |
| `REOPENED_REJECTIONS` | `R` ids that are back on the table — needs an owner delta too. |
| `RESOLVED_QUESTIONS` | `Q` ids now answered. |
| `NEW_OPEN_QUESTIONS` | `Q` ids raised by the new material. |
| `NEW_CONSTRAINTS` | ids of constraints the new material imposes. |
| `NEW_EXTERNAL_EVIDENCE` | `SRC` ids of material external research added. |
| `POTENTIAL_PLAN_IMPACT` | Classification + reason. A signal for the owner's review. |
| `authorized_by` | The owner delta that authorized a reversal or a reopening. |

## What this is not

Not a changelog of the session, not a summary of the new chat, and not a place to
re-argue the design. The new brainstorm itself is preserved verbatim as its own
episode transcript; the rationale explains the reasoning; this file is only the
difference between two understandings, in ids.
