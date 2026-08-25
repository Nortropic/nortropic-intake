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
        "> later owner-approved spec / architecture / plan > idea brief > design rationale > raw transcript"]),
    ("SKILL.md", "C2 intra-package order brief > rationale > transcript", [
        "brief > rationale > transcript"]),
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
