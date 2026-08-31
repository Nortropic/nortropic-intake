# Evals — run these after ANY change to this skill

Eleven checks, all repeatable. Zero regression = all eleven pass. The first five run the
skill's own suites against real files and real git repositories; the two v3.1 suites
drive the shipped scripts directly — one under node against a fake platform, one against
`reassemble_verify.py` in temp directories; the last three execute the real validators
against the real corpus. The numbers in the block below are the section numbers further
down, which is why they do not start at 1 — sections 1–5 cover the trigger eval, the
capture goldens and the rubrics, which are judged rather than run.

```bash
python3 evals/contract_check.py                       # 1 — contract lint
python3 evals/test_plan_contract.py                   # 6 — approved-plan falsification
python3 evals/test_context_v2.py                      # 7 — context continuity A–L
python3 evals/test_context_v21.py                     # 8 — living context C1–C15, T1–T8
python3 evals/test_project_v3.py                      # 9 — v3: roles, attestation, sweep
python3 evals/test_transport_v31.py                   # 10 — v3.1: bounded transport
node    evals/test_discovery_v31.mjs                  # 11 — v3.1: cursor enumeration
python3 scripts/plan_contract.py validate             # the real corpus
python3 scripts/context_contract.py validate          # the real corpus
python3 scripts/project_contract.py validate          # real projects, when any exist
```

The two v3.1 suites exist because the Improvements proving run found things the
previous nine could not have caught:

* `test_discovery_v31.mjs` runs the **real shipped** `scripts/project_discovery.js`
  under a fake platform — not a Python reimplementation of it, which would have proved
  only that the copy agrees with itself. Before v3.1 no eval executed any of the
  browser-side JS at all, which is why a discovery adapter that called the wrong
  endpoint shipped and was only found by a live run. It also exercises `extract.js`'s
  transport digest against a minimal DOM. It needs `node`; the workflow declares it with
  `setup-node` rather than relying on the runner image happening to have one.
* `test_transport_v31.py` exercises `scripts/reassemble_verify.py`, which no suite
  covered either: the >32 KB chunk that spilled during the proving run, the
  equal-length stale-clipboard payload a missed trusted click leaves behind, the
  framing shapes a broken transfer actually makes (T1–T9), and the trust-boundary
  family (T10–T13) that pins Intake's own vocabulary about the runtime's storage and
  the sandbox override.

The discovery suite also executes BOTH capture scripts — `data_capture.js` (preferred)
and `extract.js` (DOM fallback) — against minimal fakes, because the transport digest
that closes finding D is theirs to produce, and a digest wired to only one of them is
exactly the defect that shipped in this release's first draft.

Every code the tools can print is a contract surface. The transport ones:
`TRANSPORT_CHUNK_OVERSIZE`, `TRANSPORT_DIGEST_MISMATCH`, `TRANSPORT_DIGEST_UNVERIFIED`,
`TRANSPORT_SLICE_MERGED`, `TRANSPORT_SLICE_TRUNCATED`, `TRANSPORT_SLICE_REFETCHED`,
`TRANSPORT_INCOMPLETE`, `TRANSPORT_TAIL_MISSING`, `TRANSPORT_PAYLOAD_SHORT`,
`TRANSPORT_LENGTH_UNEXPLAINED`. The capture one that says the manifest is out of step
with the bytes: `SOURCE_IDENTITY_RECORD_STALE`.

(`project_contract.py validate` legitimately fails with "contains no project
manifests" until the first real sweep has run — that is the mis-pathed-corpus guard
doing its job, not a regression.)

Workflows exist for both repos — `.github/workflows/intake-contract.yml` here and
`corpus-contract.yml` in the corpus — and a workflow is only *running* once the file is
pushed, only *enforcing* once it is a **required status check** in branch protection.
For THIS repo both steps are now done: `main` requires the `contract` check (verified
against the branch-protection API on 2026-08-31, `strict: true`), so a red run blocks the
merge. `enforce_admins` is off, so an admin can still override — that is a person
deciding, not a gate that silently is not there. The corpus repo's own hook remains a
local gate, overridable with `--no-verify`.

CI additionally runs a **mutation guard**: it stubs out each of the five modules
(`plan_contract`, `context_contract`, `project_contract`, `intake_common`,
`reassemble_verify`) in turn — plus all three shipped browser scripts
(`project_discovery.js`, against both the discovery suite and the v3 suite whose
enumeration-evidence fixtures are its real output; `extract.js`; `data_capture.js`) —
and requires
the suites that depend on the stubbed module to fail for every combination. This catches the failure mode where a stub raises
`SystemExit(0)` mid-run and the suite exits green having executed almost nothing — which
is why every suite also asserts a floor (`MIN_CHECKS`) on checks actually executed.

## 1. Trigger eval (`trigger.json`)

Does the SKILL.md description still activate on the right requests and stay quiet on the
wrong ones?

1. Read `trigger.json`.
2. Spawn a FRESH judge (subagent, no other context). Give it ONLY: the current SKILL.md
   frontmatter `description` and the bare `query` strings — **never** the `expect` labels.
3. Ask for a trigger / no-trigger verdict per query (one line of reasoning each).
4. Diff verdicts against `expect`. Pass = 20/20. On mismatch: fix the description (or,
   if the world changed, the query set) — never coach the judge.

## 2. Capture-diff (`capture_signature.py` + `golden/`)

Does a known chat still produce the same capture signature? Guards the transcript body
format (`## Meddelande N — <roll>`, separators, junk-line rules) and the fail-closed
invariants (contiguous numbering, balanced fences, header count = body count).

```bash
# verify against the goldens (the regression test) — run ALL THREE:
python3 evals/capture_signature.py \
  ~/nortropic/innovation-intake/gauntlet-wayfinder/gauntlet-wayfinder-full-chat.md \
  --check evals/golden/gauntlet-wayfinder.signature.json
python3 evals/capture_signature.py \
  evals/golden/agent-workflow-claudeai-full-chat.md \
  --check evals/golden/agent-workflow-claudeai.signature.json
python3 evals/capture_signature.py \
  ~/nortropic/innovation-intake/nortropic-organization-os/nortropic-organization-os-full-chat.md \
  --check evals/golden/nortropic-organization-os.signature.json

# (re)generate a golden — ONLY from a real, verified delivery, never hand-written:
python3 evals/capture_signature.py <path>/<slug>-full-chat.md > evals/golden/<slug>.signature.json
```

Golden fixtures must have measured shape: generate them from an actual delivered
transcript that passed the skill's own verification, then commit the JSON here. If the
transcript format legitimately changes, re-run the capture on the same source chat and
regenerate — a golden is only updated with a new measurement, never edited by hand.

Current goldens fall in two classes — do not mix them up:

**LEGACY CAPTURE FIXTURES** (two-artifact era; guard extraction only):
- `golden/gauntlet-wayfinder.signature.json` — ChatGPT data-layer capture, 75 messages
  (29 user / 46 assistant), source: `~/nortropic/innovation-intake/gauntlet-wayfinder/`.
- `golden/agent-workflow-claudeai.signature.json` — claude.ai data-layer capture,
  18 messages (10 user / 8 assistent), source chat: claude.ai/chat/
  e8403718-9c9f-453c-8ae5-1d5d53f198fc ("Automatisera agent-workflow med Claude").
  Its transcript (`golden/agent-workflow-claudeai-full-chat.md`) is a LOCAL, gitignored
  fixture — a private chat stays out of git; only the signature JSON is committed. If
  the transcript is missing on this machine, regenerate it by re-running the data-layer
  capture on that chat (adapter in `scripts/data_capture.js`, transcript format per
  SKILL.md Phase 1) — the signature must still match, that is the regression test.

**VNEXT THREE-LAYER GOLDEN** (the reference case for the brief+rationale+transcript
contract):
- `golden/nortropic-organization-os.signature.json` — ChatGPT data-layer capture,
  57 messages (29 user / 28 assistent), chat "Skapa Kommunen" (Organization OS
  brainstorm). The full package lives in the corpus:
  `~/nortropic/innovation-intake/nortropic-organization-os/` (brief + design rationale +
  transcript). Blessed 2026-08-25 after independent review: brief rubric 17/20 PASS (no
  critical zeros), rationale rubric 20/20 PASS, adversarial package check STRONG (all
  seven defect questions NO). Use its brief and rationale as the known-good examples for
  checks 3 and 5, and as the calibration reference for the vNext quality bar (see below).
  Legacy-fixture leniencies never apply to vNext artifacts.

## 3. Brief rubric (`brief-rubric.md`)

Scores a delivered `idea-<slug>.md` 0–20. Use on every new brief before delivery, and on
a known-good brief after template changes (it should still pass). Fresh reviewer
(subagent) gets only: the brief, the transcript path, the rubric. Pass = ≥16/20 and no
zero on criteria marked (critical). Note: pre-existing briefs written before the
provenance/invariants additions score 0–1 on R4/R10 by design, and briefs captured
before the three-artifact contract score 1 on R9's `design_rationale` link — that flags
backfill work, not a regression.

**vNext thresholds (recommended, calibrated on the first vNext golden; owner may adjust):**
new-contract briefs pass at **≥17/20**, new rationales at **≥18/20**, both with no
critical zeros — the Organization OS package scored 17/20 (brief, before its review
fixes were applied) and 20/20 (rationale) under honest independent review, so these
bars demand that standard without requiring perfection. The legacy 15/20 fixture level
is never a pass for new artifacts.

## 4. Contract lint (`contract_check.py`)

Mechanical check that SKILL.md, the templates and the README still state the behavioral
contract: brief + rationale + transcript delivery, the post-approval fourth artifact,
progressive disclosure (implement-now never preloads the raw chat), the authority ladder
(current canonical repo authority > owner-approved spec > approved intake plan > brief >
rationale > transcript), rationale provenance/rejection/unresolved/metaphor requirements,
transcript immutability, approved-plan durability (the P-series: mechanical `planned`,
no plan before approval, short prompt ≠ plan, compact/reload rules, pointer-as-cache,
versioning, legacy classification), and the untouched dedup/routing semantics.

```bash
# from the repo root — exit 1 on any FAIL:
python3 evals/contract_check.py
```

It lints the instructions, not a delivery: pair it with the rubrics (which score real
artifacts) and the capture signature (which guards extraction). If a check legitimately
needs rewording because the contract intentionally changed, update the pattern together
with the doc change — never delete a check to make a drift pass.

## 5. Rationale rubric (`rationale-rubric.md`)

Scores a delivered `<slug>-design-rationale.md` 0–20. Use on every new rationale before
delivery, and on a known-good rationale after template changes. Fresh reviewer
(subagent) gets only: the rationale, the brief, the transcript path, the rubric. Pass =
≥16/20 and no zero on criteria marked (critical). Ideas captured under the two-artifact
contract have no rationale yet — absence there flags backfill, not a regression; the
first rationale delivered by a real run becomes the known-good example.

## 6. Approved-plan falsification (`test_plan_contract.py`)

Executes `scripts/plan_contract.py` against corpora built on disk — no mocks. Weighted
towards falsification: three happy-path cases against ~20 ways a plan can be unprovable
(missing, unbound, wrong hash, wrong slug, unapproved, superseded pointer, broken
supersession, orphaned version, escaped path, section summarized away, plan bound at the
wrong lifecycle state, filename/version drift, pointer to an unproven plan).

```bash
python3 evals/test_plan_contract.py     # exit 1 on any failure

# and against the REAL corpus (must stay green; legacy items surface here):
python3 scripts/plan_contract.py validate
```

It ends with the named regression scenario
**`APPROVED_PLAN_SURVIVES_COMPACTION_AND_FRESH_SESSION`**, which reproduces the failure
this contract exists to prevent: a long approved plan is persisted and bound, a target
repo is advanced, the pointer is installed — then the session is destroyed (modelled
honestly as a new process with no conversational context) and the plan must still be
recovered by identity and hash, with reconciliation left to the agent. The counterfactual
case (`R8`) runs the same scenario with no durable plan and asserts it fails closed with
`LEGACY_PLAN_ARTIFACT_MISSING` rather than guessing.

The suite also guards a negative property that is easy to lose (`case 14`): nothing in
the scripts, SKILL.md, README or the templates may require a private conversation or
session path. The mechanism must work for a fresh agent that has only repository +
intake access.

## 7. Context continuity (`test_context_v2.py`)

The realistic end-to-end scenarios, built as real packages and real git repositories:

| | Scenario | Proves |
|---|---|---|
| A | long brainstorm | raw preserved, rejections keep ids, Plan Mode never preloads the transcript |
| B | load-bearing attachment missing | planning blocked until captured **or** owner-acknowledged, and the acknowledgement itself is durable |
| C | clarification changes the design | raw still says X, the owner's Y is durable and traceable, editing it is refused |
| D | plan introduces new scope | new decisions, dropped ACs and reopened rejections all visible before approval |
| E | exact approval | wrong sha refused, substituted candidate refused, promoted body provably identical, post-approval edit refused |
| F/G | compaction, fresh agent | a new process with a scrubbed env and `cwd=/` recovers the whole package |
| H | two workstreams, one repo | keyed pointers coexist; neither overwrites nor answers for the other |
| I | multi-repo plan | both targets inspected, advisory-only stays read-only, invented roles fail |
| J | stale pointer | the hint is discarded, the corpus identity wins, the discrepancy is named |
| K | execution status lie | `verified` without evidence fails; a fabricated commit is contradicted by the repo |
| L | bidirectional provenance | AC → source and commit → slice → AC → decision → source both resolve |

It ends with the **mutation matrix** (13 planted failures, each required to fail for its
own code while a control package passes in the same run) and the **final acceptance
test**: brainstorm → coverage → candidate → coherence → exact approval → bind → pointer →
destroy the session → recover from the slug alone → traverse one requirement back to its
source.

Every `expect_fail` in these suites asserts three things at once: the run fails, the
finding is attached to the right slug, and the control package still passes. A validator
that rejects everything cannot satisfy any of them — CI enforces that with the mutation
guard.

## 8. Living context (`test_context_v21.py`)

One idea across many brainstorms, plus the source-trust boundary. Same construction: real
packages, real git repositories, the real validators, no mocks.

| | Scenario | Proves |
|---|---|---|
| C1 | same idea, second brainstorm | old RAW byte-identical, new RAW its own episode, revision increments, delta generated, no new slug, no silent overwrite |
| C2 | second brainstorm reverses a decision | history still says A, current WHAT says B, the delta reports the reversal, and a reversal with no owner delta is refused |
| C3 | new brainstorm resolves an old question | Q moves deferred → ANSWERED with owner-delta provenance |
| C4 | approved plan becomes stale | `PLAN_CONTEXT_STALE=YES`, `resume` stops (rc 3), never silently ignored |
| C5 | no plan impact | the owner's `NO_PLAN_IMPACT` verdict resumes execution; the plan file is untouched; the verdict does not itself bump the revision |
| C6 | plan reopen | old plan preserved byte for byte, v2 approved through the normal path, chain validates both ways |
| C7 | owner decision during Plan Mode | approval is REFUSED until the plan cites the owner delta |
| C8/C9 | web and GitHub provenance | URL/title/access time/class/supports and repo+commit+path retrievable; incomplete premises refused |
| C10/C11 | distillation auditor | a material finding blocks; remediation closes it by appending; an unevidenced finding and a PASS-over-findings verdict both fail; a clean package passes in the same run |
| C12 | fresh planner context | mandatory set present, raw transcripts on-demand and never dumped, one standing trust rule |
| C13 | ChatGPT independence | a scrubbed process at `cwd=/` recovers everything; the handoff is pointers, not a restated plan |
| C14 | two active workstreams | continuing one touches neither the other's pointer nor its package |
| C15 | pointer retirement | the named block goes, the other stays byte-identical, no intake artifact changes, wrong/ambiguous retirement removes nothing |
| T1–T8 | source trust | injection-shaped page stays evidence; foreign README gains no authority; an attachment cannot forge owner approval; source text cannot switch the workstream; owner adoption is the legitimate path; a declared target keeps canonical authority; ambiguity fails closed; the auditor has a code for source→decision escalation |

It ends with an **18-case mutation matrix** covering both families: altered source-set
identity, a source appended without a revision, duplicate episode ids, an overwritten raw
episode, rewritten/truncated revision history, a manifest downgraded out of revision
tracking, a fabricated owner delta, stripped external provenance, a suppressed audit
finding, an understated delta, an omitted new source, evidence promoted to instruction
authority, missing trust classification, forged owner authority, foreign-repo authority,
a plan claiming the latest revision while bound to an older identity, a plan with its
context binding removed, and retiring the wrong workstream's pointer.

## 9. v3 suite (`test_project_v3.py`)

The owner-ordered v3.0 regressions, same construction as suites 6–8 (real files, real
git, the real validators, control fixtures, MIN_CHECKS floor):

| | Family | Proves |
|---|---|---|
| A1–A7 | role-aware provenance | an assistant "decision" never passes as owner-backed; a real owner message does; mixed ranges resolve to the part carrying authority; external text confers nothing; legacy role-less transcripts report UNKNOWN honestly |
| B5–B9 | approval strength | WEAK is persisted and reported; STRONG stays STRONG; a pre-v3 plan is LEGACY_UNKNOWN, never promoted; a post-commit WEAK→STRONG flip fails |
| C8–C12 | project source model | stable CONV identities from platform ids; same-title conversations stay separate; reruns upsert; updates become traceable revisions; old raw survives byte-identically |
| D13–D17 | project coverage | capture failures are hard gaps; manifest ↔ tree in both directions; interrupted sweeps resume from the manifest; a hand-asserted COMPLETE fails |
| E17–E21 | idea routing | one chat → many ideas; many chats → one idea; ambiguity queues without blocking; duplicate INDEX rows fail |
| F21–F24 | mode separation | a full synthetic sweep produces no plans and no interviews, lands ideas at `status: idea`, and completes unattended via CLI alone |
| G25–G29 | audit & trust | dangling/hash-unlinked provenance; self-closed audit findings; owner-less dismissals; tampered hashes; mutated raw; assistant proposals refused downstream of a sweep |
| H30–H31 | side effects | the tooling never commits the corpus; every command runs against a tmp `--corpus` |
| I32–I42 | source identity vs builder metadata (v3.1) | the CONV-012 reproducer: byte-identical messages under a re-worded `**Syfte:**` line mint NO revision, and neither does a later `**Exportdatum:**`; a changed message or a changed speaker still does; the old raw survives; an interrupted write is refused rather than overwritten; a legacy revision with no recorded identity reaches the same no-op without migration; and a `source_sha256` the bytes cannot back is caught by both `capture` and `validate` |
| J39–J48 | enumeration evidence (v3.1) | `--verified` without `--evidence` is refused; so are a record naming the v3.0 query endpoint, one describing another project, an all-null or unbalanced cursor ledger, a padded item count, and the adapter's own reported count disagreement; a real record from the shipped adapter DOES verify, is archived in-corpus, and is re-checked for tampering; a pre-v3.1 claim stays valid as legacy without being promoted |

No real project is ever swept by the evals — every fixture is synthetic and torn down.
The J-family fixtures are produced by running the SHIPPED `scripts/project_discovery.js`
under node (`evals/discovery_record.mjs`), so the checker is fed what the adapter really
writes rather than a hand-built record that would only prove the two agree with a
fixture.
