#!/usr/bin/env python3
"""Contract lint — mechanical regression check for the three-artifact contract.

Verifies that SKILL.md, the templates and the README still STATE the behavioral
contract introduced with the three-layer context model (execution brief → design
rationale → raw transcript). It checks the instructions, not a delivery — the
delivered artifacts are scored by the rubrics (evals/brief-rubric.md,
evals/rationale-rubric.md) and the capture signature (evals/capture_signature.py).

Matching is done on whitespace-normalized text (all runs of whitespace collapse to
one space), so line wrapping never breaks a check. Patterns are literal substrings;
a leading "i:" makes the match case-insensitive.

Usage (from the repo root):
  python3 evals/contract_check.py            # PASS/FAIL per check, exit 1 on any FAIL
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECKS = [
    # A. Three-artifact contract
    ("SKILL.md", "A1 names all three artifacts", [
        "`idea-<slug>.md`", "`<slug>-design-rationale.md`", "`<slug>-full-chat.md`"]),
    ("SKILL.md", "A2 delivery writes all three files", [
        "All three files written"]),
    ("SKILL.md", "A3 rationale derived independently, not copied", [
        "generate the rationale by copying the brief"]),
    # B/I. Progressive disclosure — transcript never default main context
    ("SKILL.md", "B1 implement-now never auto-loads the transcript", [
        "Do NOT automatically load `<slug>-full-chat.md`"]),
    ("SKILL.md", "B2 transcript is evidence, not working memory", [
        "not default working memory"]),
    ("SKILL.md", "I1 transcript never preloaded merely because it exists", [
        "Never preloaded merely because it exists"]),
    # C. Authority order
    ("SKILL.md", "C1 full authority ladder in order", [
        "current canonical repository authority",
        "> later owner-approved spec / architecture / plan > approved intake plan "
        "> owner clarifications > idea brief > design rationale > raw transcript"]),
    ("SKILL.md", "C2 intra-package order incl. owner clarifications", [
        "approved plan > owner clarifications > brief > rationale > transcript"]),
    ("SKILL.md", "C3 conflicts surfaced, never the old brainstorm silently", [
        "surface it during Clarify/Plan"]),
    ("references/brief-template.md", "C4 brief states canonical authority wins", [
        "i:canonical repository authority beats all intake artifacts",
        "this brief wins over rationale and transcript"]),
    ("references/design-rationale-template.md", "C5 rationale is non-authoritative", [
        "authority: non-authoritative-rationale"]),
    # D. Rationale provenance
    ("references/design-rationale-template.md", "D1 message-range tags required", [
        "(← msg N–M)", "material claim"]),
    # E. Rejection preservation
    ("references/design-rationale-template.md", "E1 rejections carry why + failure + source", [
        "REJECTED:", "FAILURE IT WOULD CREATE"]),
    # F. Unresolved preservation
    ("references/design-rationale-template.md", "F1 unresolved never silently promoted", [
        "never silently promoted"]),
    # G. Metaphor safety
    ("references/design-rationale-template.md", "G1 metaphor → principle, not literal", [
        "WHAT MUST NOT BE COPIED LITERALLY"]),
    # Rationale quality bar: evidence labels, no invented reasoning, not a spec
    ("references/design-rationale-template.md", "G2 mentioned vs independently verified", [
        "MENTIONED IN SOURCE", "INDEPENDENTLY VERIFIED"]),
    ("references/design-rationale-template.md", "G3 no reasoning beyond user-visible source", [
        "not present in the user-visible source"]),
    ("references/design-rationale-template.md", "G4 not a spec/summary/copy", [
        "an implementation plan, a generic summary"]),
    ("references/design-rationale-template.md", "G5 retrieval map + load-when ladder", [
        "## 11. Retrieval map", "## 12. What to load when",
        "Do not preload the raw transcript"]),
    # H. Owner clarification updates derived artifacts, transcript immutable
    ("SKILL.md", "H1 interview answers land in BOTH derived artifacts", [
        "folded into BOTH brief and rationale"]),
    ("SKILL.md", "H2 transcript immutable after verified capture", [
        "immutable once its capture passed verification",
        "never rewrite it to make history look cleaner"]),
    # Clarify retrieval ladder in the brief's process footer
    ("references/brief-template.md", "H3 Clarify ladder brief → rationale → targeted ranges", [
        "brief → rationale → targeted transcript",
        "never the whole transcript"]),
    ("references/brief-template.md", "H4 brief frontmatter links the rationale", [
        "design_rationale: <slug>-design-rationale.md"]),
    # J. Corpus dedup / supersede semantics intact
    ("SKILL.md", "J1 no silent duplicates", [
        "never store or build a silent duplicate"]),
    ("SKILL.md", "J2 supersede/related links intact", [
        "supersedes: [<old-slug>]", "superseded_by: <new-slug>"]),
    ("SKILL.md", "J3 supersede keeps the package navigable, no new idea for rationale", [
        "Never create a new idea merely because rationale changed"]),
    ("SKILL.md", "J4 INDEX stays one row per idea", [
        "one row per IDEA"]),
    # L. Routing intact
    ("SKILL.md", "L1 both routes still exist", [
        "IDÉBANKEN", "IMPLEMENTERA NU"]),
    ("SKILL.md", "L2 unattended default is the idea bank", [
        "Default to the idébank path", "Never default to implement-now unattended"]),
    ("SKILL.md", "L3 idea-bank route skips the interview by design", [
        "IDÉBANK route this phase is always skipped by design"]),
    # README teaches the model
    ("README.md", "R1 README names the rationale layer + authority order", [
        "<slug>-design-rationale.md", "Auktoritetsordning"]),
    # ---------------------------------------------------------------------
    # P. Approved-plan durability (the fourth artifact)
    # ---------------------------------------------------------------------
    ("SKILL.md", "P1 the fourth artifact is named and scoped to post-approval", [
        "`<slug>-approved-plan.md`", "PRE-PLAN", "POST-PLAN"]),
    ("SKILL.md", "P2 `planned` is a mechanical, validated state", [
        "`planned` is a mechanical state, not a word",
        "**Detection is mechanical and complete over the files present.**",
        "fails closed on every one of those conditions",
        "ships `hooks/pre-commit`, which runs the validator and refuses the commit"]),
    ("SKILL.md", "P2b the limits of the gate are stated, not oversold", [
        "It is a gate, not a wall", "`--no-verify` overrides it",
        "soft-passes if the skill is not installed",
        "**Invocation of Phase 4 is not mechanical.**",
        "it cannot catch a run that never reaches the gate",
        "**Fidelity is not mechanical.**",
        "It cannot prove the prose matches what the owner approved"]),
    ("SKILL.md", "P3 no plan is ever generated before owner approval", [
        "Never generate an approved plan from the brief, the rationale or the "
        "transcript before approval",
        "Silence is not approval"]),
    ("SKILL.md", "P4 a short execution prompt never replaces the plan", [
        "A short execution prompt and an approved plan are not the same artifact",
        "If the plan is long, persist the long plan"]),
    ("SKILL.md", "P5 the approved plan is not a second runtime/source of truth", [
        "not a second runtime, not a second source of truth, and\nnot an "
        "execution-state ledger",
        "the repository wins and the divergence is reported"]),
    ("SKILL.md", "P6 plan is bound to the brief by hash, never duplicated into it", [
        "approved_plan_sha256",
        "The brief points at the plan; it never\n   duplicates it"]),
    ("SKILL.md", "P7 compact instructions preserve execution identity + reload from disk", [
        "COMPACT INSTRUCTIONS",
        "re-read the approved plan from disk before deriving any future work",
        "Never reconstruct a missing approved plan\nfrom conversational memory",
        "STOP with `PLAN_IDENTITY_UNAVAILABLE`"]),
    ("SKILL.md", "P8 the pointer is a cache; repo evidence wins", [
        "a cache, never a second truth",
        "A stale pointer never overrides repository evidence"]),
    ("SKILL.md", "P9 mechanism uses CLAUDE.md, not private session storage", [
        "The supported surface is `CLAUDE.md`",
        "do not depend on Claude Code's private session storage",
        "a different agent that has only\nrepository + intake access"]),
    ("SKILL.md", "P10 fresh-session start contract is mechanical", [
        "resume \\ --slug <slug> --workstream <NAME> --target-repo <repo>",
        "PLAN_IDENTITY=<path>@sha256:<hash>",
        "PLAN_CURRENT_REPO_RECONCILIATION=",
        "NEXT_EXECUTION_POINTER=<next slice, computed — not copied from a hint>"]),
    ("SKILL.md", "P11 reopening keeps history: versioned, superseded both ways", [
        "An approved plan is never silently rewritten",
        "`supersedes_plan: <old file>`",
        "`superseded_by_plan: <new file>`"]),
    ("SKILL.md", "P12 legacy items classified, never fabricated", [
        "LEGACY_PLAN_ARTIFACT_MISSING",
        "a model reconstruction is never accepted as\nthe plan",
        "The\ntranscript is never scraped automatically"]),
    ("SKILL.md", "P13 INDEX stays one row per idea after the plan exists", [
        "Still one row per IDEA; neither the plan\n   nor the manifest gets its own row"]),
    # ---------------------------------------------------------------------
    # V. Context continuity (v2)
    # ---------------------------------------------------------------------
    ("SKILL.md", "V1 the WHERE and OWNER-DELTA layers exist", [
        "`<slug>-context-manifest.json`", "`<slug>-owner-clarifications.md`",
        "`<slug>-plan-candidate.md`"]),
    ("SKILL.md", "V2 full information ≠ full preload", [
        "full information PRESERVATION, not full preload",
        "the raw transcript is retrieved in targeted ranges, never dumped"]),
    ("SKILL.md", "V3 clarifications are durable, append-only, transcript untouched", [
        "the exact question, the owner's\nexact wording",
        "Append\nonly; never edit a recorded answer, and never rewrite the transcript"]),
    ("SKILL.md", "V4 manifest is evidence-only and refuses credentials", [
        "never from guesses**", "Never write a credential into a manifest"]),
    ("SKILL.md", "V5 the coverage gate is fail-closed before Plan Mode", [
        "PLANNING_CONTEXT_COMPLETE=YES|NO",
        "On `PLANNING_CONTEXT_COMPLETE=NO`, Plan Mode does not begin",
        "Never plan around a gap by inferring what the missing source\nprobably said"]),
    ("SKILL.md", "V6 planning reads current repo reality first", [
        "Planning is `INTENT + CURRENT REALITY → PLAN`, never `OLD BRAINSTORM → PLAN`",
        "the\nold idea never silently wins"]),
    ("SKILL.md", "V7 owner approves exact bytes, no rewrite in between", [
        "Approval names a sha256, not a vibe",
        "copies the candidate's\n   body **byte for byte**",
        "There is no model rewrite between\n   what the owner saw and what implementation uses"]),
    ("SKILL.md", "V8 coherence delta is visible before approval", [
        "**Material scope changes are never buried in hundreds of plan lines.**",
        "the owner approves with the\n   delta visible"]),
    ("SKILL.md", "V9 multi-workstream pointers cannot collide", [
        "keyed by\n`workstream=<NAME> slug=<slug>`",
        "**A repository-wide \"next task\" does not\nexist**"]),
    ("SKILL.md", "V10 execution state is observed, never authored", [
        "**Execution state is observed, never authored.**",
        "**A `verified` label is not made true by a valid approved plan.**",
        "the\nrepository wins, and the brief is corrected"]),
    ("SKILL.md", "V11 provenance is bidirectional, without a ledger", [
        "trace --slug <slug> --commit <sha>",
        "evidence →\nslice → acceptance criterion → decision → the original source",
        "no ledger, no graph database"]),
    ("SKILL.md", "V12 the plan map is derived, not stored", [
        "`map --slug <slug>` gives slice IDs and line\nranges"]),
    ("references/context-manifest-template.md", "V13 manifest contract stated", [
        "capture_status", "unavailable_owner_acknowledged", "load_bearing",
        "owner_ack", "advisory-only", "Never guess a source"]),
    ("references/owner-clarifications-template.md", "V14 clarification contract stated", [
        "APPROVED PLAN  >  OWNER CLARIFICATIONS  >  BRIEF",
        "Append-only", "The transcript is never rewritten",
        "BLOCKING"]),
    ("references/approved-plan-template.md", "V15 candidate→approval promotion stated", [
        "The owner approves **bytes**, not a promise",
        "plan_content_sha256", "approved_candidate_sha256",
        "The candidate is never mutated after approval"]),
    ("references/approved-plan-template.md", "V16 multi-repo roles + derived map", [
        "do **not** share authority", "advisory-only", "**READ ONLY**",
        "Nothing is\nstored, so the map cannot drift"]),
    ("references/brief-template.md", "V17 brief carries R ids and dispositions", [
        "R1, R2, … for explicitly REJECTED paths",
        "open_questions_deferred", "open_questions_owner_accepted",
        "`building` and `verified` are observations, not claims"]),
    ("references/approved-plan-template.md", "P14 plan template: identity + approval metadata", [
        "type: approved-plan", "approval_state: approved", "approved_by",
        "approval_evidence", "plan_version", "source_brief",
        "authority: owner-approved-execution-intent"]),
    ("references/approved-plan-template.md", "P15 plan template: nothing summarized away", [
        "## 3. Execution order", "## 5. Deferred work",
        "## 6. Rejected paths (must not be re-adopted)",
        "## 7. Owner-only transitions", "## 8. Stop conditions",
        "## 10. Current / next slice semantics",
        "## 11. Precedence & coherence patches"]),
    ("references/approved-plan-template.md", "P16 plan template: non-authority + immutability", [
        "not a second runtime, not a second source of truth",
        "An approved plan is never silently rewritten"]),
    ("references/approved-plan-template.md", "P17 plan template: bounded manual legacy recovery", [
        "LEGACY_PLAN_ARTIFACT_MISSING",
        "recovered-from-known-source",
        "Fabricating the plan is never the fallback"]),
    ("references/brief-template.md", "P18 brief carries the binding fields, not the plan", [
        "approved_plan_sha256: <sha256 of that file>",
        "never copies it in"]),
    ("references/brief-template.md", "P19 brief forbids an unearned `planned`", [
        "`planned` is earned, not written"]),
    ("README.md", "P20 README teaches the four-artifact model", [
        "<slug>-approved-plan.md"]),
]


def normalize(text):
    return re.sub(r"\s+", " ", text)


def main():
    failures = 0
    cache = {}
    for rel, label, patterns in CHECKS:
        if rel not in cache:
            path = ROOT / rel
            if not path.exists():
                print(f"FAIL  {label}  [{rel} MISSING]")
                failures += 1
                cache[rel] = None
                continue
            text = path.read_text(encoding="utf-8")
            cache[rel] = (normalize(text), normalize(text).lower())
        if cache[rel] is None:
            print(f"FAIL  {label}  [{rel} MISSING]")
            failures += 1
            continue
        norm, norm_lower = cache[rel]
        missing = []
        for pat in patterns:
            if pat.startswith("i:"):
                hit = normalize(pat[2:]).lower() in norm_lower
            else:
                hit = normalize(pat) in norm
            if not hit:
                missing.append(pat)
        if missing:
            print(f"FAIL  {label}  [{rel}: missing {missing!r}]")
            failures += 1
        else:
            print(f"PASS  {label}")
    total = len(CHECKS)
    print(f"\n{total - failures}/{total} contract checks passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
