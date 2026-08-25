# Evals — run these after ANY change to this skill

Six checks, all repeatable. Zero regression = all six pass. Five of them measure the
skill's outputs and its stated contract without touching the capture/distill/verify
pipeline; the sixth (approved-plan falsification) executes the real validator against
real corpora built on disk.

## 1. Trigger eval (`trigger.json`)

Does the SKILL.md description still activate on the right requests and stay quiet on the
wrong ones?

1. Read `trigger.json`.
2. Spawn a FRESH judge (subagent, no other context). Give it ONLY: the current SKILL.md
   frontmatter `description` and the bare `query` strings — **never** the `expect` labels.
3. Ask for a trigger / no-trigger verdict per query (one line of reasoning each).
4. Diff verdicts against `expect`. Pass = 16/16. On mismatch: fix the description (or,
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
