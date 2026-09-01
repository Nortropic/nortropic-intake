# R&D compile — `_rnd/<compile>/` (RND_COMPILE mode)

One compile turns ALREADY-CAPTURED material — a PROJECT_SWEEP corpus, or an explicit
source set — into a typed, derived, rebuildable understanding of what the material
actually contains. It is a reading, not a runtime: the derived layer carries **no
execution authority**, decides **no disposition**, and can be deleted and rebuilt
without touching one byte of evidence.

The standing laws, stated once and enforced by `scripts/rnd_contract.py` and the
v4 eval suite:

    RAW EVIDENCE SURVIVES SYNTHESIS.        EVIDENCE ≠ AUTHORITY.
    INTAKE ≠ BACKLOG.                       OPTION ≠ COMMITMENT.
    INNOVATION ≠ WORK.                      FREQUENCY ≠ IMPORTANCE.
    RECENCY ≠ CORRECTNESS.                  ATTENTION ≠ STRATEGY.
    DEFERRED ≠ FORGOTTEN.                   SILENCE = UNKNOWN.
    CURRENT VERIFIED REALITY OUTRANKS COMPILED MEMORY.
    ACTIVATION BELONGS TO EXECUTIVE FUNCTION.
    EXECUTION BELONGS TO THE AUTONOMY KERNEL.

## The three artifacts — and why only three

    _rnd/<compile>/rnd-ir.json        the derived R&D IR — CANONICAL
    _rnd/<compile>/RND-COVERAGE.md    stamped RENDERING of the IR's coverage
    _rnd/<compile>/compile-audit.md   independent falsification, append-only

`rnd-ir.json` is the one derived truth; `RND-COVERAGE.md` is generated from it by
`render` exactly the way `PROJECT.md` renders a project manifest — deterministic,
re-derivable, never edited by hand, never canonical (`RND_RENDER_STALE` when it
drifts). Nothing else is created: no per-item files, no summary documents, no second
index. Deleting the whole `_rnd/<compile>/` directory destroys nothing but derived
work, because every byte of evidence lives in the sweep corpus or the idea packages
it was compiled from — that deletability is checked, not assumed.

## The IR shape

```json
{
  "rnd_ir_version": 1,
  "compile_id": "improvements-r29",
  "title": "Improvements — R&D compile",
  "created": "2026-09-01",
  "mode": "RND_COMPILE",
  "derived_layer": true,
  "execution_authority": "none",
  "source_set": {
    "kind": "project",
    "project": "improvements",
    "inventory_revision": 29,
    "inventory_sha256": "<from the project manifest at compile time>",
    "sources": [
      {"source_id": "CONV-001", "revision": 1,
       "path": "_projects/improvements/sources/CONV-001/conversation.md",
       "source_sha256": "<the recorded revision identity>"}
    ]
  },
  "items": [
    {
      "id": "RND-001",
      "kind": "OWNER_DECISION",
      "claim": "Approved plans are never silently rewritten; supersession is recorded in both directions.",
      "scope": "intake / plan lifecycle",
      "provenance": [{"source_id": "CONV-003", "revision": 1, "messages": "12-15"}],
      "authority_class": "owner",
      "relations": [{"rel": "refines", "target": "RND-004"}],
      "uncertainty": "none — verbatim owner statement",
      "tags": ["operating-law"]
    },
    {
      "id": "RND-002",
      "kind": "HYPOTHESIS",
      "claim": "A per-repo learning ledger would shorten the trustworthy learning loop.",
      "scope": "learning infrastructure",
      "provenance": [{"source_id": "CONV-011", "revision": 1, "messages": "40-52"}],
      "authority_class": "derived",
      "relations": [{"rel": "contradicts", "target": "RND-017"}],
      "uncertainty": "high — argued once, never tested",
      "tags": ["candidate-primitive"],
      "activation_condition": "if repo count exceeds ~10 and cross-repo lessons repeat"
    }
  ],
  "coverage": [
    {"lens": "truth-trust", "state": "WELL_EXPLORED",
     "basis": ["RND-001", "RND-004"], "note": "…"},
    {"lens": "identity-data-economics", "state": "UNKNOWN", "basis": [], "note": ""}
  ]
}
```

## The core ontology — seven kinds, closed on purpose

    OBSERVATION        something the material states or shows (authority_class: evidence)
    OWNER_DECISION     the owner decided it, with owner provenance (authority_class: owner)
    DERIVED_JUDGMENT   the compiler's synthesis across evidence (authority_class: derived)
    HYPOTHESIS         a testable belief, not yet tested
    REQUIREMENT        a stated "must hold" — owner-backed or derived, never external-only
    OPTION             a possible path; an OPTION is never a commitment
    UNKNOWN            an explicitly recognized gap

Failure modes, operating laws, candidate primitives, patterns and external analogies
are expressed as **tags, relations and properties on these seven** — never as new
first-class kinds. A new local term of art does not get a new kind
(`RND_KIND_INVALID`); the ontology expands only when an adversarial eval demonstrates
that the small set loses a material semantic distinction, and that demonstration is
recorded as contract + eval, not as prose.

Rules the validator enforces per item:

- **Every item is sourced.** At least one provenance entry, each resolving to a bound
  source (`RND_ITEM_UNSOURCED`, `RND_PROVENANCE_UNBOUND`), whose bytes still hash to
  the recorded revision identity (`RND_SOURCE_HASH_MISMATCH` — raw survives synthesis
  is checked, not assumed), with message ranges inside the transcript
  (`RND_PROVENANCE_OUT_OF_RANGE`).
- **OWNER_DECISION comes only from owner provenance.** At least one cited message
  must resolve — through the transcript's own role headers, the same v3.0 mechanism
  SINGLE uses — to a turn the OWNER spoke. Assistant-only backing fails
  (`RND_OWNER_DECISION_ASSISTANT_ONLY`): an assistant saying *"Johnny decided X"* is
  a proposal. Unprovable roles fail closed (`RND_OWNER_DECISION_ROLE_UNPROVEN`) —
  an undecidable speaker never passes as the owner; the honest kind for such content
  is OBSERVATION or DERIVED_JUDGMENT. Only OWNER_DECISION may carry
  `authority_class: owner`; any other kind claiming it is
  `RND_AUTHORITY_LAUNDERING`.
- **Supersession of an owner decision needs an owner.** A `supersedes` relation whose
  target is an OWNER_DECISION is valid only from another OWNER_DECISION
  (`RND_DECISION_SUPERSEDED_WITHOUT_OWNER`). Newer evidence that disagrees is a
  `contradicts` relation — both items survive; recency never silently wins.
- **No priority machinery exists to launder.** The fields `priority`, `importance`,
  `rank`, `score`, `weight`, `urgency`, `backlog`, `frequency` (and their spellings)
  are refused anywhere in the IR (`RND_PRIORITIZATION_FORBIDDEN`) — an idea mentioned
  twenty times is one idea with twenty provenance entries, not a heavier one. So are
  `status`, `disposition`, `implement_now`, `task`, `plan`
  (`RND_LIFECYCLE_FIELD_FORBIDDEN`, `RND_DISPOSITION_FORBIDDEN`): KEEP / ADAPT /
  MERGE / SIMPLIFY / EXPERIMENT / DEFER / REJECT / NEEDS_EVIDENCE /
  ALREADY_IMPLEMENTED are **Recompile's** verdicts, made later against fresh repo
  reality — never Intake's. What Intake MAY preserve is an owner's explicit
  reject/defer as an OWNER_DECISION with provenance, which is a fact about the past,
  not a disposition of the future. A single `lovability_score` — or any single-number
  reduction of product experience — is refused the same way
  (`RND_SCORE_FORBIDDEN`).
- **`activation_condition` is information.** A recorded trigger condition activates
  nothing: no task, no plan, no status transition, no IMPLEMENT_NOW routing. The
  tool surface makes this structural — `rnd_contract.py` has no command that writes
  an idea package, opens a plan, or moves a lifecycle status — and the eval suite
  proves a compile leaves every existing idea package, approved plan and INDEX row
  byte-identical.
- **Claims are concise; evidence is referenced, not copied.** `claim` is capped, an
  optional `quote` is capped harder (`RND_RAW_DUPLICATION`) — the IR points into the
  corpus, it never becomes a second copy of it.
- **Current reality is pointed at, never cached as truth.** An item may carry a
  `reality_pointer` (`{"repo", "ref", "observed_at"}`); `observed_at` is mandatory
  (`RND_REALITY_POINTER_UNDATED`) and the tools print, on every coverage/status run:
  `REALITY_POINTERS_REQUIRE_FRESH_READ=YES` — Recompile reads the target repos
  fresh, and CURRENT VERIFIED REPO REALITY outranks COMPILED R&D MEMORY, always.

## The baseline coverage lens — a diagnostic, never an ontology

Twelve lenses, all mandatory in every compile, in this canonical order:

    truth-trust                    professional-excellence
    organization                   executive-function
    continuity-operate-forever     identity-data-economics
    learning-evolution             rnd-intake
    assurance-red-team             lovability-product-experience
    reality-dogfood                explicit-unknowns-deferred

States: `WELL_EXPLORED | PARTIALLY_EXPLORED | NEEDS_RESEARCH | NEEDS_REALITY |
OWNER_DECISION | INTENTIONALLY_DEFERRED | UNKNOWN`.

- A lens with no supporting evidence is `UNKNOWN` with an empty basis — the row is
  never omitted (`RND_COVERAGE_LENS_MISSING`) and UNKNOWN never counts as resolved.
- A non-UNKNOWN state must cite item ids that exist (`RND_COVERAGE_UNEVIDENCED`,
  `RND_COVERAGE_BASIS_DANGLING`); an UNKNOWN with a basis is a contradiction
  (`RND_COVERAGE_CONTRADICTED`).
- `OWNER_DECISION` and `INTENTIONALLY_DEFERRED` states require at least one
  OWNER_DECISION item in the basis (`RND_COVERAGE_OWNER_STATE_UNBACKED`) — deferral
  is an owner act; DEFERRED ≠ FORGOTTEN.
- Extra lenses beyond the twelve are allowed (the baseline may grow), but no model
  may call a corpus complete because it failed to imagine a missing category — the
  baseline is a floor, explicitly a **diagnostic lens and never an exhaustive
  ontology of Nortropic**.

Cross-cutting review lenses — Mission Command (intent without micromanaged method),
VSM (operations/coordination/inside-now/outside-then/identity represented or
explicitly deferred), Hoshin/catchball (intent down, reality up), Theory of
Constraints (real system constraint vs local optimization), Cynefin (standardizing
the still-emergent), HRO (judgment with relevant expertise, not rank), SRE (day-2,
degraded states, recovery, decommissioning), FinOps (spend traceable to verified
outcome), Deming/PDSA (hypothesis + prediction before claimed learning),
Lovable/Linear (crafted, fast to magic, not merely correct), middle-out / narrow
waist (does this widen the core, or can the complexity stay at the edge?) — are
**diagnostic questions for coverage notes and audit rounds**. They are evidence,
analogies and review lenses; none of them becomes architecture authority through
Intake, and none of them is an automatic build requirement.

The middle-out compression lens is preserved verbatim as review vocabulary: grow
outward faster than inward; new complexity belongs at the edge until independent
domains converge; generalize after convergence, not before; prefer expressive
compression over ontological expansion; a good abstraction removes more concepts
from consumers than it introduces; truth is preserved losslessly while attention may
be aggressively compressed; scale through edge replication, not central special
cases; hierarchy is for accountability and decision rights, not normal routing;
recurring high-bandwidth coordination is a boundary smell until justified; shared
scaffolding needs a reason to exist and a sunset condition; optimize the Shortest
Trustworthy Learning Loop, not raw output volume; interactive owner-facing cognition
and unattended background work may run to different latency objectives; internal
complexity is acceptable — **leaked** complexity is a defect.

Lovability/desirability signals — time-to-magic, stuckness, bypass pressure (the
temptation to go around Nortropic and work directly in Claude Code), complexity
leakage, calm/quiet healthy operation, clarity, craft/taste, "every interruption
earns its interruption" — are diagnostic signals a coverage note or audit round may
cite. They are never KPI authority and never reduce to a single score.

## The compile audit — `compile-audit.md`

Same discipline as the sweep audit: a fresh, isolated reviewer gets the bound source
set and the IR, and tries to FALSIFY the compile. Rounds are appended, never edited,
each bound to the `ir_sha256` it audited; a round never closes its own finding; a
material finding blocks the compile from being called audited; `PASS` over recorded
findings is a contradiction. For a project-bound compile, only an owner-answered
review-queue entry naming the finding dismisses it; an explicit-set compile has no
dismissal path — findings are remediated or they stand. Codes
(`RND_AUDIT_CODE_INVALID` otherwise):

    RND_BACKLOG_LAUNDERING           typed understanding presented as work queue
    RND_AUTHORITY_LAUNDERING         evidence or synthesis wearing owner authority
    RND_OWNER_PROVENANCE_LAUNDERED   owner backing that does not survive role checks
    RND_FREQUENCY_BIAS               repetition treated as importance
    RND_RECENCY_BIAS                 newer material silently outranking an owner decision
    RND_NEGATIVE_SPACE_OMITTED       a gap the lens should show, absent or overstated
    RND_ONTOLOGY_EXPANSION           a tag's job done by an invented kind
    RND_SECOND_TRUTH                 derived layer contradicting or duplicating source truth
    RND_PLANNING_ENTERED             the compile produced plan/task/lifecycle artifacts
    RND_COLLAPSED_TO_SINGLE_IDEA     a mixed corpus flattened into "one buildable idea"
    RND_COVERAGE_OVERSTATED          a lens called explored beyond its basis

## Boundaries the audit owns, not `validate` — recorded honestly

`validate` is mechanical and fail-closed over everything a machine can decide: the
vocabulary, provenance binding, role-aware owner backing, the closed ontology, and
the **negative** side of coverage — no lens omitted, `UNKNOWN` whenever the basis is
empty, `UNKNOWN` never carrying a basis, and every non-UNKNOWN state citing item ids
that exist. What it deliberately does **not** decide is judgement, and saying so is
part of the honest record (an independent review pressed on exactly these):

- **Positive coverage is the audit's call.** `validate` proves a `WELL_EXPLORED`
  lens cites real items; it cannot prove those items genuinely explore that lens.
  Overstatement is `RND_COVERAGE_OVERSTATED` — a **compile-audit** code, not a
  validate code — for the same reason the distillation audit, not the validator,
  judges whether a brief's decisions are semantically right.
- **A backlog can still be encoded in free text.** The key-stem guard refuses every
  priority/score/lifecycle field, and a bare rank *token* in a `tags` value
  (`P0`, `#3`) is refused too — but a de-facto ordering smuggled into prose (`claim`,
  `note`) or into item **order** is a semantic smell the audit hunts
  (`RND_BACKLOG_LAUNDERING`), not something the vocabulary guard can see. Item order
  in the IR carries no meaning and no tool reads it as rank.
- **Claim fidelity is judgement.** `validate` caps a claim's length and binds its
  provenance; whether the claim faithfully states what the source said is
  `RND_SECOND_TRUTH`, an audit finding.
- **Role truth is inherited from capture, and header framing is the boundary.** The
  owner gate resolves roles only from block-opening headers and refuses an
  out-of-sequence one, which closes header text pasted into a message body. What it
  cannot distinguish is a capture that reproduces the builder's exact turn framing —
  a conversation whose subject matter *is* this transcript format — the same
  documented residual the single-mode capture carries; the source-set hash binds the
  bytes, and the audit reads the words.

These are the same shape as the frozen skill's accepted residual risks: mechanical
where a machine can be trusted, independent-audit where judgement is required, and
never a false claim that structure proves semantics.

## What RND_COMPILE never does

No capture of new authority from external text. No IMPLEMENTERA NU question. No Plan
Mode. No approved plans. No idea-status transitions. No prioritization. No
work/task/mission creation. No interviews. No commits, no pushes. It reads verified
evidence and writes `_rnd/<compile>/` — nothing else. When a real implementation is
later activated, the road is the ordinary SINGLE implement-now lane, from the idea
package — never from the IR.
