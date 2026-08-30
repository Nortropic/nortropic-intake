# Plan candidate & approved plan (`<slug>-plan-candidate.md` → `<slug>-approved-plan.md`)

The HOW layer: **execution order**. It exists only after Plan Mode has produced a plan and
the owner has explicitly approved it. It is the durable home of owner-approved execution
intent — the thing that used to live only in a conversation and disappeared at the first
compaction.

The package model:

    PRE-PLAN   idea-<slug>.md (WHAT) · <slug>-design-rationale.md (WHY)
               <slug>-full-chat.md (RAW) · <slug>-context-manifest.json (WHERE)
               <slug>-owner-clarifications.md (OWNER DELTAS)
    POST-PLAN  + <slug>-plan-candidate.md (HOW, proposed — what the owner reads)
               + <slug>-approved-plan.md  (HOW, approved — the same body, promoted)

## Two files, one document

The owner approves **bytes**, not a promise. So the plan exists twice, on purpose:

1. **The candidate** is written straight out of Plan Mode. The owner reads *this file*.
2. **The approved plan** is produced by promotion — its body is copied byte for byte;
   only frontmatter is added (who approved, when, and the hashes that prove it).

A plan's **content identity** is the sha256 of its body, everything after the frontmatter.
Candidate and approved plan therefore have the same content identity by construction, and
the validator recomputes it:

    plan_content_sha256          == sha256(approved plan body)
                                 == sha256(candidate body)
    approved_candidate_sha256    == sha256(the candidate FILE the owner read)

## Bound to the understanding it was approved against

An approved plan also records `context_revision` + `source_set_sha256`: **which source
set the owner approved it from**. This is provenance, never authority — the context
package does not tell the plan what to do. It exists so that when the idea receives
another brainstorm, the mismatch is *detectable* instead of silent:

    APPROVED_PLAN_CONTEXT_REVISION=3
    CURRENT_CONTEXT_REVISION=4
    PLAN_CONTEXT_STALE=YES
    PLAN_INVALID=NO          <- these are different things

**Stale is not invalid.** A plan approved against an older understanding is not thereby
wrong, and discarding a good plan because new material arrived would be its own failure.
What is forbidden is executing on as if nothing had happened: `resume` stops with
`PLAN_CONTEXT_STALE=YES` and `PLAN_IMPACT_CLASSIFICATION=UNRECORDED` until the owner
records a verdict. `plan_contract.py impact` shows the exact delta behind the mismatch
and which slices cite the changed ids; the owner's answer becomes a
`PLAN_REVIEW_DECISION` owner delta — `NO_PLAN_IMPACT`, `PLAN_REVIEW_REQUIRED` or
`PLAN_REOPEN_REQUIRED`. Ambiguity resolves to review, never to an automatic reopen; only
the owner reopens an approved plan.

## Plan-mode owner decisions must be cited

When the owner decides something *while the plan is being made* — "take B, but keep X
from A" — it is recorded as an owner delta before approval, and this plan must cite its
id. `approve` refuses otherwise (`PLAN_OWNER_DELTA_UNCITED`), because a decision that
survives only in the Plan Mode conversation does not survive.

The candidate is never mutated after approval. It stays in the package as the receipt for
exactly what was on screen when the owner said yes. There is no model rewrite between
*what the owner saw* and *what implementation uses* — and if anything drifts, the plan
stops validating.

    python3 …/plan_contract.py coherence --slug <slug>      # the delta the owner reads
    python3 …/plan_contract.py approve   --slug <slug> \
        --candidate-sha <the sha the owner approved> \
        --approved-by "Johnny (Nortropic)" --approved-at 2026-08-25 \
        --evidence "owner approved candidate <sha12> in session"

`approve` refuses if the sha the owner approved is not the candidate on disk — that is the
case where the document changed between reading and approval, and it must never be
resolved by promoting the newer bytes.

## Rules that matter more than the section list

- **Never generated before approval.** No approved plan is ever derived from the brief,
  the rationale or the transcript. It is written from the Plan Mode output the owner
  approved, and only after that approval. A model-reconstructed plan is not an approved
  plan — if the owner-approved output cannot be reproduced, there is no plan and the
  brief stays `clarified`.
- **Fidelity over brevity.** Persist the plan the owner approved. Do NOT summarize away
  execution order, scope boundaries, decisions, deferred work, plan-critical rejected
  paths, owner-only transitions, stop conditions, acceptance criteria, current/next slice
  semantics, or explicit precedence/coherence patches. If the approved output is long,
  the artifact is long. The short execution prompt used to kick off a build session is a
  **different thing**: it may point at this file, it may never replace it.
- **Not authority over the repository.** The approved plan preserves owner intent and
  provenance. It never overrides the constitution, the rulebook, frozen gates, current
  published production truth, or a later owner-approved transition. It is not a second
  runtime, not a second source of truth, and not an execution-state ledger. When the plan
  and current repository truth disagree, the repository wins and the divergence is
  reported to the owner — never silently reconciled in the plan's favour.
- **Immutable after approval.** An approved plan is never silently rewritten. Corrections
  of substance create a new version (see *Reopening*); the previous version is preserved
  and the supersession is recorded in both directions.
- **Bound by identity.** After the file is written, its sha256 is recorded in the brief
  (`approved_plan_sha256`) together with `status: planned`. The brief points at the plan;
  it never duplicates it.
- **Mechanically validated.** `scripts/plan_contract.py validate` must pass before the
  brief may say `planned`. It checks the frontmatter, every section below (heading *and*
  content — an empty heading is a FAIL, and §2/§3/§9 may never be a placeholder), the hash
  binding and the supersession chain. Fail closed: no valid plan, no `planned`.
  What it cannot check is fidelity — that the prose is what the owner actually approved.
  That is your discipline, not the validator's.
- **Frontmatter is flat and one value per line.** No nested keys, no duplicate keys, no
  value running onto the next line. The validator refuses ambiguity rather than guessing,
  so that what it reads is always what a human reading the file sees.
- **`approved_by` names the owner.** A model may not approve its own plan; values naming
  the agent are refused.

**On `source_brief_sha256`.** It is provenance, not a binding. The brief changes in the
very next step — binding adds `approved_plan` and friends — so this hash can never be
re-verified against the live brief; only its format is checked. The verified binding runs
the other way: brief → `approved_plan_sha256` → this file. Record the brief's hash as it
stood when the plan was approved, so a later reader can see which version of the WHAT this
HOW was approved against.

## Versioning / reopening

Deterministic and file-based; no machinery beyond names and two frontmatter fields.

- v1 is `<slug>-approved-plan.md`. Version N≥2 is `<slug>-approved-plan-v<N>.md`.
- The owner deliberately reopening a plan produces a NEW file. The old file is kept
  byte-for-byte except for two added fields: `status: superseded` and
  `superseded_by_plan: <new file>`. `approval_state: approved` stays — it was approved,
  and history is not edited to look cleaner.
- The new file carries `supersedes_plan: <old file>` and `plan_version: <N>`.
- The brief's `approved_plan` / `approved_plan_sha256` / `plan_version` are updated to the
  new file in the same step. The pointer moves deliberately, never by drift.
- `plan_version` must equal the version in the filename.

## Structure (use exactly these sections; all eleven are required)

A section with nothing to say says `None.` — explicitly. Silence is indistinguishable
from omission, and omission is the defect this artifact exists to prevent.

```markdown
---
title: "<Idea title> — approved plan v<N>"
type: approved-plan
status: approved            # approved | superseded (the artifact's own lifecycle)
approval_state: approved    # immutable historical fact — never downgraded
slug: <slug>
owner: Johnny (Nortropic)
approved_at: <YYYY-MM-DD>
approved_by: Johnny (Nortropic)
approval_evidence: "<how the owner approved — one line, e.g. plan mode accepted 2026-08-25, owner said kör på>"
plan_version: <N>
source_brief: idea-<slug>.md
source_brief_sha256: <sha256 of the brief as it stood at approval time — provenance only>
canonical_execution_repo: <repo path or remote, or `unknown`>
execution_targets: [<repo>=<role>, <repo>=<role>]   # multi-repo plans; roles below
plan_source: claude-code-plan-mode   # | owner-authored | recovered-from-known-source
fidelity: full                       # full | partial (partial = recovered; owner must verify)
authority: owner-approved-execution-intent
plan_content_sha256: <sha256 of this file's body — the identity the owner approved>
approved_candidate: <slug>-plan-candidate.md
approved_candidate_sha256: <sha256 of that candidate FILE, unmutated>
# Attestation strength — durable since v3.0, written by `approve`, never by hand.
# STRONG: the candidate's bytes were already committed when the approval ran.
# WEAK: --allow-uncommitted-candidate was used; the receipt attests only that this
# process was handed that sha. A plan without these fields predates v3.0 and is
# reported as LEGACY_UNKNOWN — a weak approval stays visibly weak forever, and a
# legacy one is NEVER retroactively promoted to STRONG.
approval_attestation: STRONG        # STRONG | WEAK
approval_git_anchor: UNCHANGED      # the git anchor observed at approval time
# Living context — PROVENANCE, not authority: the understanding this plan was approved
# against. Copied from the candidate at approval; `approve` refuses a candidate whose
# binding does not match the package's current revision.
context_revision: <N>
source_set_sha256: <that revision's source-set identity>
# supersedes_plan: <slug>-approved-plan.md        # on v2+
# superseded_by_plan: <slug>-approved-plan-v2.md  # added to the OLD file when superseded
---

# Approved plan: <title> (v<N>)

## 1. Authority boundary
State plainly, in this file: this plan preserves owner-approved execution intent and its
provenance. It does not override the constitution, the rulebook, frozen gates, current
published production truth, or any later owner-approved transition. Current repository
truth wins on conflict; the divergence is reported, not silently resolved. This file is
not a runtime, not a second source of truth, not an execution-state ledger.
Precedence: current canonical repository authority > later owner-approved
spec/architecture/plan > THIS approved plan > idea brief > design rationale > transcript.

## 2. Scope boundaries
What is in scope for this plan and what is explicitly outside it — including neighbouring
work that must not be pulled in opportunistically.

## 3. Execution order

### S1 — <slice heading>
What this slice delivers, in the order the owner approved. Name the brief's stable IDs it
rests on: `Implements D1.` / `Covers AC1, AC2.` / `CLAR-001 applies.` Slices must be
numbered S1..Sn without gaps — they are the addresses that acceptance criteria, `resume`,
the plan map and implementation evidence all point at.

### S2 — <slice heading>
…

This is the section that must never be compressed into a summary. If the approved Plan
Mode output was long, it is long here.

## 4. Decisions carried into execution
Decisions the plan depends on, each with its one-line why. Includes decisions made during
plan review that are not in the brief.

## 5. Deferred work
Explicitly deferred items — what, and until when/what condition. Deferred is not
rejected; keeping the distinction is what stops a later session from either dropping the
work or building it early.

## 6. Rejected paths (must not be re-adopted)
Plan-critical rejections with the failure each would create. A future session reading
only this file must not re-propose them.

## 7. Owner-only transitions
Steps that require the owner and may never be taken autonomously (merges, promotions,
freezes, publication, scope changes, plan reopening).

## 8. Stop conditions
The conditions under which execution must stop rather than proceed — including
`PLAN_IDENTITY_UNAVAILABLE` (plan file or recorded identity cannot be proven) and any
plan-specific blockers.

## 9. Acceptance criteria
How the plan as a whole is judged done, in checkable form. Slice-level criteria may live
in §3; this section carries the end-to-end bar.

## 10. Current / next slice semantics
How a resuming session determines where execution actually stands: which repository
evidence corresponds to which slice, and how "current" and "next" are computed. State
explicitly that this is computed by reconciling the plan against the repository — any
stored pointer is a hint that repository evidence overrides.

## 11. Precedence & coherence patches
Explicit patches the owner attached to the plan: precedence rules between this plan and
other documents, coherence fixes, corrections to the brief that the plan carries. `None.`
if the approved output contained none.

## Provenance
Where this plan came from: the session/date, how the owner approved it, and — for
`plan_source: recovered-from-known-source` — exactly which known source it was recovered
from and how the owner verified it. Never "reconstructed from memory".
```

## Multi-repo plans

A Nortropic plan may legitimately span repositories that do **not** share authority. Each
target carries a role, and the roles survive into `resume` and the plan map:

| Role | Authority |
|---|---|
| `canonical-system` | Owner-gated system authority; Intake may never author its truth |
| `operator-product` | Implementation target for product work |
| `advisory-only` | **READ ONLY** — reference material, never a write target |
| `intake-corpus` | The intake corpus itself |

Each target repository remains the truth for its own implementation state. Intake does not
become a multi-repo execution-state database; `resume` reads each repo and reports what it
finds, and where a repo contradicts the plan or the brief's label, the repository wins.

## The plan map (derived, never stored)

A long approved plan should not be preloaded whole for a small slice. Ask for its
structure instead:

    python3 …/plan_contract.py map --slug <slug>

It prints slice IDs, headings, line ranges, the IDs each slice covers, owner-only slices
and the execution targets — recomputed from the approved plan on every call. Nothing is
stored, so the map cannot drift and cannot become a second source of truth. The approved
plan remains canonical.

## Recovery of a legacy plan (bounded, manual, owner-verified)

For an item that is already `planned`/`building` with no plan artifact — the validator
reports `LEGACY_PLAN_ARTIFACT_MISSING` — the only permitted path is:

1. The owner names the known source of the approved plan (a file, a document, an export).
   The transcript is not automatically scraped, and a model reconstruction is never
   accepted as the plan.
2. The plan is persisted from that source with `plan_source: recovered-from-known-source`
   and `fidelity: partial` until the owner confirms it is complete.
3. The owner verifies it and confirms approval; `fidelity` is set to `full` only then.
4. It is bound (hash + brief pointer) and the validator must pass.

If no known source exists, the honest outcome is to move the brief back to `clarified`
and re-plan. Fabricating the plan is never the fallback.
