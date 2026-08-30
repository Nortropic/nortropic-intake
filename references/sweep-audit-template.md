# Sweep audit — `_projects/<project>/sweep-audit.md`

The independent falsification pass over a WHOLE sweep — the project-level sibling of
the per-idea distillation audit, under the same discipline: a fresh, isolated
reviewer (no sweep context, no shared reasoning) is given the project manifest, the
source tree, the review queue and the produced idea packages, and its only job is:

> try to falsify the sweep.

Try to falsify at least: source inventory completeness, duplicate source identities,
missing or mutated raw, manifest/tree count mismatches, ideas with dangling
provenance, owner claims backed only by assistant messages, external evidence
promoted to instruction, missing source episodes, silent capture failures, duplicate
idea slugs or duplicate INDEX state, inconsistent routing relations, a false
COMPLETE status, and rerun/idempotency violations.

Rounds are appended, never edited. A round is bound to the `inventory_revision` it
audited; `finalize` refuses a sweep whose audit is not at the current revision. The
allowed finding codes (`SWEEP_AUDIT_CODE_INVALID` otherwise):

    SOURCE_INVENTORY_INCOMPLETE      DUPLICATE_SOURCE_IDENTITY
    SOURCE_MISSING_OR_MUTATED        MANIFEST_TREE_MISMATCH
    IDEA_PROVENANCE_DANGLING         OWNER_DECISION_BACKED_ONLY_BY_ASSISTANT
    EXTERNAL_EVIDENCE_PROMOTED_TO_INSTRUCTION   SOURCE_EPISODE_MISSING
    SILENT_CAPTURE_FAILURE           DUPLICATE_IDEA_SLUG
    INDEX_STATE_DUPLICATE            ROUTING_RELATION_INCONSISTENT
    FALSE_COMPLETENESS               RERUN_IDEMPOTENCY_VIOLATION

## Frontmatter

```
---
title: "<project> — sweep audit"
type: sweep-audit
project: <project>
owner: Johnny (Nortropic)
append_only: true
---
```

## A round

```
## AUDIT-3
- auditor: fresh subagent, no sweep context
- audited_at: 2026-09-03
- scope: inventory revision 3 — manifest, source tree, queue, produced ideas
- verdict: FINDINGS

### FIND-001
- finding: SILENT_CAPTURE_FAILURE
- severity: material
- evidence: CONV-007 is declared in the inventory but has no revision and no error
- quote: "…"
```

The rules, identical in spirit to the distillation audit and enforced by
`project_contract.py audit`:

- Every finding costs evidence that ADDRESSES something — a CONV id, an RQ id, a
  swept idea slug, or message numbers (`SWEEP_AUDIT_FINDING_UNEVIDENCED`).
- A round may never close a finding it raised (`SWEEP_AUDIT_FINDING_SELF_CLOSED`);
  remediation is closed by a LATER round naming it: `- remediated: FIND-001`.
- Only the owner dismisses one, by a review-queue entry whose `owner_answer` — the
  owner's own words — names the finding: `- dismissed: FIND-002 (RQ-005)` is valid
  only when RQ-005's `owner_answer` value itself mentions `FIND-002`. An owner
  answer about something else dismisses nothing, and an agent-authored line planting
  the id beside a real answer supplies nothing. Anything less is
  `SWEEP_AUDIT_DISMISSED_WITHOUT_OWNER`.
- An unremediated material finding blocks `finalize`
  (`SWEEP_AUDIT_UNREMEDIATED`), and the file is append-only against git.
- A `PASS` verdict over recorded findings is a contradiction, not a summary
  (`SWEEP_AUDIT_VERDICT_CONTRADICTED`).
