# Review queue — `_projects/<project>/review-queue.md`

PROJECT_SWEEP is non-interactive by default: no owner interview per historical chat,
no Plan Mode, no approvals. When the sweep hits something it cannot decide safely —
an uncertain duplicate, CONTINUE_EXISTING vs RELATED, unclear supersession, an
uncertain owner-judgment classification — the rule is:

    record → queue → continue

never "guess silently", and never "block the whole sweep". This file is where the
recording happens. It is append-only (git is the witness:
`REVIEW_QUEUE_NOT_APPEND_ONLY`), and an open item can neither vanish nor be hidden:
`coverage` and `finalize` surface every open id, and a project with open items can
end no better than `COMPLETE_WITH_OPEN_REVIEW`.

One hard boundary: a CAPTURE gap is never a review item. Completeness is computed
from source lifecycle states and never reads this queue, so queueing "CONV-007 could
not be captured" does not — and must not — make the project look complete. Capture
failures are `mark-failed` hard gaps.

## Frontmatter

```
---
title: "<project> — review queue"
type: review-queue
project: <project>
owner: Johnny (Nortropic)
append_only: true
---
```

## An item

```
## RQ-001
- date: 2026-09-01
- issue: CONV-014 may be a CONTINUE_EXISTING of gauntlet-wayfinder, or merely RELATED
- affects: CONV-014, gauntlet-wayfinder
- recommendation: hold as RELATED; the reversal test (does it overturn settled
  decisions?) is inconclusive from the transcript alone
- evidence: msg 3–19 of CONV-014; D2/D5 in idea-gauntlet-wayfinder.md
- confidence: low
- owner_judgment_required: yes
```

`affects` names CONV ids and/or idea slugs that must exist (`REVIEW_QUEUE_ORPHANED`
otherwise). `owner_judgment_required: no` is legitimate for items a later sweep pass
can settle mechanically.

## Resolving an item

A LATER entry names it — the item itself is never edited:

```
## RQ-002
- date: 2026-09-03
- resolves: RQ-001
- question: Is CONV-014 a continuation of gauntlet-wayfinder?
- owner_answer: Continuation. It refines the same idea; nothing settled is reversed.
```

An entry that resolves its own id is refused (`REVIEW_QUEUE_SELF_RESOLVED`), and a
resolution entry is PURE: one that also carries `issue`/`recommendation`/
`owner_judgment_required`/`affects`/`evidence` is refused
(`REVIEW_QUEUE_MIXED_ENTRY`) and its id still counts as OPEN — closing one ambiguity
may never smuggle a new one out of the open list, not even buried in an evidence
line. Raise the new ambiguity as its own entry with its own id.

An entry carrying `owner_answer` records the owner's EXACT words and is the only
thing a sweep-audit dismissal may cite (`SWEEP_AUDIT_DISMISSED_WITHOUT_OWNER`) — and
it dismisses only the finding the owner's OWN WORDS name: the `FIND-NNN` id must
appear in the `owner_answer` value itself, never merely in an agent-authored line
beside it, or one genuine owner answer would become a skeleton key for findings the
owner never saw. Same principle as owner deltas in single mode: owner authority
comes from the owner interaction, never from bytes asserting it.
