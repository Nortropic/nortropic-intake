#!/usr/bin/env python3
"""Falsification suite for the approved-plan contract (`scripts/plan_contract.py`).

Every case below is built as a real corpus on disk in a temp dir and run through the
real validator/loader — no mocks. The suite is deliberately weighted towards
falsification: the happy path is three cases, the ways a plan can be unprovable are
fifteen. A contract that only passes its happy path proves nothing.

Includes the named regression scenario
  APPROVED_PLAN_SURVIVES_COMPACTION_AND_FRESH_SESSION
which reproduces the real failure (approved plan lost to compaction) against the new
design, in a process that has no conversational context at all.

Usage (from the skill root):
  python3 evals/test_plan_contract.py            # exit 1 on any failure
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN_CONTRACT = ROOT / "scripts" / "plan_contract.py"

RESULTS = []
MIN_CHECKS = 85   # floor on checks actually executed; see main()


# ------------------------------------------------------------- fixtures ----

PLAN_SECTIONS = """
# Approved plan: {title} (v{version})

## 1. Authority boundary
Preserves owner-approved execution intent. Does not override the constitution, the
rulebook, frozen gates or current published production truth. Repository truth wins on
conflict; the divergence is reported. Not a runtime, not a second source of truth.

## 2. Scope boundaries
In: the three slices in §3. Out: everything else in the corpus.

## 3. Execution order

### S1 — Foundation
Build the durable artifact and its eleven sections. Covers AC1.

### S2 — The loader
Resolve the plan from the slug alone and verify its hash. Covers AC1.

### S3 — The pointer
Install the keyed reload pointer in the target repository. Covers AC1.

## 4. Decisions carried into execution
D1. File-based binding by sha256 — because a hash is checkable by a fresh session.

## 5. Deferred work
Backfill of legacy items — deferred until the owner names a known source.

## 6. Rejected paths (must not be re-adopted)
A plan database — it would create a second execution truth.

## 7. Owner-only transitions
Merge, publication, plan reopening.

## 8. Stop conditions
PLAN_IDENTITY_UNAVAILABLE; any conflict between plan and repository truth.

## 9. Acceptance criteria
A fresh session recovers the exact plan from the slug alone.

## 10. Current / next slice semantics
Computed by reconciling this plan against the repository. Stored pointers are hints.

## 11. Precedence & coherence patches
None.

## Provenance
Plan Mode output approved by the owner on 2026-08-25.
"""


def plan_text(for_slug, version=1, title="Test idea", **overrides):
    fm = {
        "title": '"%s — approved plan v%d"' % (title, version),
        "type": "approved-plan",
        "status": "approved",
        "approval_state": "approved",
        "slug": for_slug,
        "owner": "Johnny (Nortropic)",
        "approved_at": "2026-08-25",
        "approved_by": "Johnny (Nortropic)",
        "approval_evidence": '"plan mode accepted in session 2026-08-25"',
        "plan_version": str(version),
        "source_brief": "idea-%s.md" % for_slug,
        "source_brief_sha256": "0" * 64,
        "canonical_execution_repo": "unknown",
        "plan_source": "claude-code-plan-mode",
        "fidelity": "full",
        "authority": "owner-approved-execution-intent",
        "approved_candidate": ("%s-plan-candidate.md" % for_slug if version == 1
                               else "%s-plan-candidate-v%d.md" % (for_slug, version)),
    }
    body = overrides.pop("body", None)
    for key, value in overrides.items():
        if value is None:
            fm.pop(key, None)
        else:
            fm[key] = value
    if body is None:
        body = PLAN_SECTIONS.format(title=title, version=version)
    # Content identity must be computed the way the tool computes it, or the fixture
    # would be testing the fixture's idea of a body rather than the contract's.
    fm.setdefault("plan_content_sha256", _content_sha(fm, body))
    # AUTO is replaced with the real hash once the matching candidate is on disk. A
    # test that sets this field explicitly keeps its value untouched.
    fm.setdefault("approved_candidate_sha256", "AUTO")
    lines = ["---"] + ["%s: %s" % (k, v) for k, v in fm.items()] + ["---"]
    return "\n".join(lines) + "\n" + body


def _content_sha(fm, body):
    """The body hash as `intake_common.read_frontmatter` would compute it."""
    lines = ["---"] + ["%s: %s" % (k, v) for k, v in fm.items()] + ["---"]
    text = "\n".join(lines) + "\n" + body
    sys.path.insert(0, str(ROOT / "scripts"))
    from intake_common import read_frontmatter, sha256_text as st
    import tempfile as _tf
    with _tf.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        name = fh.name
    try:
        return st(read_frontmatter(name)[1])
    finally:
        os.unlink(name)


def candidate_text(for_slug, version=1, title="Test idea", body=None):
    """The candidate whose body the approved plan must reproduce exactly."""
    fm = {
        "title": '"%s — plan candidate v%d"' % (title, version),
        "type": "plan-candidate",
        "status": "candidate",
        "slug": for_slug,
        "owner": "Johnny (Nortropic)",
        "created": "2026-08-25",
        "plan_version": str(version),
        "source_brief": "idea-%s.md" % for_slug,
        "source_brief_sha256": "0" * 64,
        "canonical_execution_repo": "unknown",
        "plan_source": "claude-code-plan-mode",
        "fidelity": "full",
    }
    if body is None:
        body = PLAN_SECTIONS.format(title=title, version=version)
    lines = ["---"] + ["%s: %s" % (k, v) for k, v in fm.items()] + ["---"]
    return "\n".join(lines) + "\n" + body


def brief_text(slug, status="idea", **extra):
    fm = {
        "title": '"Test idea"',
        "type": "idea-brief",
        "status": status,
        "slug": slug,
        "owner": "Johnny (Nortropic)",
        "created": "2026-08-25",
        "source_conversation": "%s-full-chat.md" % slug,
        "design_rationale": "%s-design-rationale.md" % slug,
        "intended_repo_path": "%s/idea-%s.md" % (slug, slug),
    }
    for key, value in extra.items():
        if value is None:
            fm.pop(key, None)
        else:
            fm[key] = value
    lines = ["---"] + ["%s: %s" % (k, v) for k, v in fm.items()] + ["---"]
    return "\n".join(lines) + "\n\n# Idea brief: Test idea\n"


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


CONTROL_SLUG = "control-ok"


def add_control(corpus):
    """A package that must ALWAYS pass, in every fixture.

    Without it, `expect_fail` is satisfied by a validator that rejects everything —
    the assertion "this state fails" only means something alongside "and a valid
    state still passes, in the same run".
    """
    folder = Path(corpus) / CONTROL_SLUG
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ("idea-%s.md" % CONTROL_SLUG)).write_text(
        brief_text(CONTROL_SLUG, status="clarified"), encoding="utf-8")
    return corpus


def _write_matching_candidate(folder, slug, plan_text_value):
    """Every approved plan in a fixture gets the candidate it was promoted from.

    Named by the plan's own `approved_candidate` field and carrying the plan's exact
    body, so the exact-approval proof holds for valid fixtures — and so a test that
    breaks it on purpose breaks only that.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from intake_common import read_frontmatter
    import tempfile as _tf
    with _tf.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(plan_text_value)
        name = fh.name
    try:
        fm, body, _ = read_frontmatter(name)
    finally:
        os.unlink(name)
    ref = str(fm.get("approved_candidate", "")).strip()
    if not ref or "/" in ref:
        return None
    version = int(str(fm.get("plan_version", "1")).strip() or "1")
    cand = folder / ref
    cand.write_text(candidate_text(slug, version, body=body), encoding="utf-8")
    return sha256_text(cand.read_text(encoding="utf-8"))


def _settle_plan(folder, plan_name, slug):
    """Write the candidate, then resolve the plan's AUTO candidate hash from disk."""
    path = folder / plan_name
    text = path.read_text(encoding="utf-8")
    cand_sha = _write_matching_candidate(folder, slug, text)
    if cand_sha and "approved_candidate_sha256: AUTO" in text:
        path.write_text(text.replace("approved_candidate_sha256: AUTO",
                                     "approved_candidate_sha256: %s" % cand_sha),
                        encoding="utf-8")


def make_corpus(tmp, slug="test-idea", status="idea", plan=None, plan_name=None,
                bind_sha=None, brief_extra=None, extra_files=None):
    """Build a corpus on disk. `plan` is the plan file text, or None for no plan."""
    corpus = Path(tmp) / "corpus"
    folder = corpus / slug
    folder.mkdir(parents=True, exist_ok=True)
    add_control(corpus)
    (folder / ("%s-full-chat.md" % slug)).write_text("# transcript\n", encoding="utf-8")
    (folder / ("%s-design-rationale.md" % slug)).write_text("# rationale\n", encoding="utf-8")

    extra = dict(brief_extra or {})
    for name, text in (extra_files or {}).items():
        (folder / name).write_text(text, encoding="utf-8")
        if re.search(r"-approved-plan(-v\d+)?\.md$", name):
            _settle_plan(folder, name, slug)
    if plan is not None:
        name = plan_name or ("%s-approved-plan.md" % slug)
        (folder / name).write_text(plan, encoding="utf-8")
        _settle_plan(folder, name, slug)
        extra.setdefault("approved_plan", name)
        extra.setdefault(
            "approved_plan_sha256",
            bind_sha or sha256_text((folder / name).read_text(encoding="utf-8")))
        extra.setdefault("plan_approved_at", "2026-08-25")
    # `building`/`verified` are OBSERVATIONS: the contract now requires evidence, so
    # every fixture that claims one supplies it. Tests that attack the evidence itself
    # override these explicitly.
    if status in ("building", "verified"):
        extra.setdefault("execution_repo", "~/nortropic/verkstadsgolvet")
        extra.setdefault("execution_commit", "a1b2c3d4e5f6")
        extra.setdefault("execution_slice", "S1")
        if status == "verified":
            extra.setdefault("verification_evidence", "docs/evidence/ac1.md")

    (folder / ("idea-%s.md" % slug)).write_text(
        brief_text(slug, status=status, **extra), encoding="utf-8")
    return corpus


def run(args, corpus=None):
    cmd = [sys.executable, str(PLAN_CONTRACT)]
    if corpus:
        cmd += ["--corpus", str(corpus)]
    cmd += args
    env = dict(os.environ)
    env.pop("NORTROPIC_INTAKE_CORPUS", None)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout + proc.stderr


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS " if condition else "FAIL ", name,
                        ("  — %s" % detail) if (detail and not condition) else ""))


def expect_fail(name, corpus, code, slug="test-idea"):
    """The named state must fail with the named code, ATTACHED TO ITS OWN SLUG, while
    the control package in the same corpus still passes. All three or the check fails."""
    rc, out = run(["validate"], corpus)
    attached = re.search(r"^FAIL\s+\[%s\]\s+%s\b" % (re.escape(slug), re.escape(code)),
                         out, re.M) is not None
    control_ok = re.search(r"^PASS\s+\[%s\]" % re.escape(CONTROL_SLUG), out, re.M) is not None
    check(name, rc == 1 and attached and control_ok,
          "rc=%d attached=%s control_ok=%s, expected %s on [%s] in:\n%s"
          % (rc, attached, control_ok, code, slug, out.strip()))


def expect_pass(name, corpus, slug="test-idea"):
    rc, out = run(["validate"], corpus)
    named = re.search(r"^PASS\s+\[%s\]" % re.escape(slug), out, re.M) is not None
    check(name, rc == 0 and named, "rc=%d named=%s:\n%s" % (rc, named, out.strip()))


# ---------------------------------------------------------------- cases ----

def case_01_planned_without_plan(tmp):
    corpus = make_corpus(tmp, status="planned")
    expect_fail("01  status: planned with no approved_plan → FAIL",
                corpus, "LEGACY_PLAN_ARTIFACT_MISSING")


def case_02_plan_file_missing(tmp):
    corpus = make_corpus(tmp, status="planned", brief_extra={
        "approved_plan": "test-idea-approved-plan.md",
        "approved_plan_sha256": "a" * 64})
    expect_fail("02  approved_plan path missing → FAIL", corpus, "PLAN_FILE_MISSING")


def case_03_hash_mismatch(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"),
                         bind_sha="b" * 64)
    expect_fail("03  approved_plan sha256 mismatch → FAIL", corpus, "PLAN_HASH_MISMATCH")


def case_03b_hash_missing(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    brief = corpus / "test-idea" / "idea-test-idea.md"
    brief.write_text(re.sub(r"approved_plan_sha256:.*\n", "", brief.read_text()),
                     encoding="utf-8")
    expect_fail("03b approved_plan with no recorded sha256 → FAIL",
                corpus, "PLAN_HASH_MISSING")


def case_04_wrong_slug(tmp):
    corpus = make_corpus(tmp, status="planned",
                         plan=plan_text("test-idea", slug="some-other-idea"))
    expect_fail("04  approved plan carries the wrong slug → FAIL",
                corpus, "PLAN_SLUG_MISMATCH")


def case_05_not_owner_approved(tmp):
    corpus = make_corpus(tmp, status="planned",
                         plan=plan_text("test-idea", approval_state="draft"))
    expect_fail("05a plan approval_state != approved → FAIL", corpus, "PLAN_NOT_APPROVED")
    corpus2 = make_corpus(Path(tmp) / "b", status="planned",
                          plan=plan_text("test-idea", approved_by=None))
    expect_fail("05b plan without approved_by → FAIL",
                corpus2, "PLAN_APPROVAL_METADATA_MISSING")
    corpus3 = make_corpus(Path(tmp) / "c", status="planned",
                          plan=plan_text("test-idea", approval_evidence=None))
    expect_fail("05c plan without approval_evidence → FAIL",
                corpus3, "PLAN_APPROVAL_METADATA_MISSING")


def case_06_clarified_without_plan(tmp):
    corpus = make_corpus(tmp, status="clarified")
    expect_pass("06  status: clarified with no plan → VALID", corpus)


def case_07_building_with_plan(tmp):
    corpus = make_corpus(tmp, status="building", plan=plan_text("test-idea"))
    expect_pass("07  status: building with a valid approved plan → VALID", corpus)


def case_08_verified_with_plan(tmp):
    corpus = make_corpus(tmp, status="verified", plan=plan_text("test-idea"))
    expect_pass("08  status: verified with a valid approved plan → VALID", corpus)


def case_09_supersession(tmp):
    slug = "test-idea"
    v1 = plan_text(slug, version=1, status="superseded",
                   superseded_by_plan="%s-approved-plan-v2.md" % slug)
    v2 = plan_text(slug, version=2, supersedes_plan="%s-approved-plan.md" % slug)
    corpus = make_corpus(tmp, status="building", plan=v2,
                         plan_name="%s-approved-plan-v2.md" % slug,
                         brief_extra={"plan_version": "2"},
                         extra_files={"%s-approved-plan.md" % slug: v1})
    expect_pass("09a superseded plan history stays traceable → VALID", corpus)

    # the brief may not point at a superseded version
    corpus_b = make_corpus(Path(tmp) / "b", status="building", plan=v1,
                           extra_files={"%s-approved-plan-v2.md" % slug: v2})
    expect_fail("09b brief pointing at a superseded plan → FAIL",
                corpus_b, "PLAN_SUPERSEDED_POINTER")

    # history may not be dropped
    v2_orphan = plan_text(slug, version=2, supersedes_plan="%s-approved-plan.md" % slug)
    corpus_c = make_corpus(Path(tmp) / "c", status="building", plan=v2_orphan,
                           plan_name="%s-approved-plan-v2.md" % slug,
                           brief_extra={"plan_version": "2"})
    expect_fail("09c superseded version deleted from history → FAIL",
                corpus_c, "PLAN_SUPERSESSION_BROKEN")

    # a plan file nobody points at is not silently tolerated
    corpus_d = make_corpus(Path(tmp) / "d", status="building", plan=plan_text(slug),
                           extra_files={"%s-approved-plan-v2.md" % slug:
                                        plan_text(slug, version=2)})
    expect_fail("09d unreachable plan version in the folder → FAIL",
                corpus_d, "PLAN_ORPHANED")


def case_10_loader_deterministic(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    expected = sha256_text((corpus / "test-idea" / "test-idea-approved-plan.md")
                           .read_text(encoding="utf-8"))
    rc1, out1 = run(["resume", "--slug", "test-idea"], corpus)
    rc2, out2 = run(["resume", "--slug", "test-idea"], corpus)
    identity = re.search(r"PLAN_IDENTITY=(\S+)", out1)
    check("10  fresh-session loader resolves the plan deterministically",
          rc1 == 0 and out1 == out2 and identity is not None
          and identity.group(1).endswith("@sha256:" + expected)
          and "PLAN_STATUS=APPROVED" in out1,
          "rc=%d, stable=%s\n%s" % (rc1, out1 == out2, out1.strip()))


def case_11_stale_pointer(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    pointer = Path(tmp) / "CLAUDE.md"
    rc, out = run(["pointer", "--slug", "test-idea", "--workstream", "TESTWS", "--into", str(pointer),
                   "--execution-pointer", "slice 2 of 3"], corpus)
    written = pointer.read_text(encoding="utf-8") if pointer.exists() else ""
    check("11a pointer block lands in the file with the proven identity",
          rc == 0 and "NORTROPIC-ACTIVE-PLAN:BEGIN" in written
          and "NORTROPIC-ACTIVE-PLAN:END" in written
          and sha256_text((corpus / "test-idea" / "test-idea-approved-plan.md")
                          .read_text(encoding="utf-8")) in written
          and "ACTIVE_INTAKE_SLUG: test-idea" in written
          and "CURRENT_EXECUTION_POINTER: slice 2 of 3" in written,
          "rc=%d, file=%r" % (rc, written[:300]))

    # the plan legitimately moves on (v2); the pointer now names a dead sha
    v1 = plan_text("test-idea", version=1, status="superseded",
                   superseded_by_plan="test-idea-approved-plan-v2.md")
    v2 = plan_text("test-idea", version=2,
                   supersedes_plan="test-idea-approved-plan.md")
    folder = corpus / "test-idea"
    (folder / "test-idea-approved-plan.md").write_text(v1, encoding="utf-8")
    (folder / "test-idea-approved-plan-v2.md").write_text(v2, encoding="utf-8")
    _settle_plan(folder, "test-idea-approved-plan.md", "test-idea")
    _settle_plan(folder, "test-idea-approved-plan-v2.md", "test-idea")
    v1 = (folder / "test-idea-approved-plan.md").read_text(encoding="utf-8")
    v2 = (folder / "test-idea-approved-plan-v2.md").read_text(encoding="utf-8")
    brief = folder / "idea-test-idea.md"
    text = brief.read_text(encoding="utf-8")
    text = text.replace("approved_plan: test-idea-approved-plan.md",
                        "approved_plan: test-idea-approved-plan-v2.md")
    text = re.sub(r"approved_plan_sha256: .*",
                  "approved_plan_sha256: %s" % sha256_text(v2), text)
    brief.write_text(text, encoding="utf-8")

    rc, out = run(["resume", "--slug", "test-idea", "--pointer", str(pointer)], corpus)
    identity = re.search(r"PLAN_IDENTITY=(\S+)", out)
    check("11b stale pointer is reported, corpus/repo evidence wins",
          rc == 0 and "POINTER_STALE=YES" in out
          and "POINTER_OVERRIDDEN_BY=corpus+repository evidence" in out
          and identity is not None
          and identity.group(1).endswith("@sha256:" + sha256_text(v2))
          and "test-idea-approved-plan-v2.md@" in identity.group(1),
          "rc=%d\n%s" % (rc, out.strip()))
    check("11c the stale hint is DISCARDED, not forwarded as the next pointer",
          re.search(r"^NEXT_EXECUTION_POINTER=UNSET \(stale pointer discarded", out, re.M)
          is not None and "slice 2 of 3" not in out,
          out.strip())
    check("11d the superseded version's identity never appears as the answer",
          rc == 0 and "PLAN_STATUS=APPROVED" in out and "PLAN_VERSION=2" in out
          and sha256_text(v1) not in out, "rc=%d\n%s" % (rc, out.strip()))

    # a fresh pointer, in agreement with the corpus, may pass its hint through
    run(["pointer", "--slug", "test-idea", "--workstream", "TESTWS", "--into", str(pointer),
         "--execution-pointer", "slice 3 of 3"], corpus)
    rc, out = run(["resume", "--slug", "test-idea", "--pointer", str(pointer)], corpus)
    check("11e a fresh pointer's hint is passed through, still labelled unverified",
          rc == 0 and "POINTER_STALE=NO" in out
          and "NEXT_EXECUTION_POINTER=slice 3 of 3 (HINT — unverified)" in out,
          out.strip())


def case_12_reload_contract(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    rc, out = run(["pointer", "--slug", "test-idea", "--workstream", "TESTWS", "--print-only"], corpus)
    plan_path = str((corpus / "test-idea" / "test-idea-approved-plan.md").resolve())
    check("12  reload/compaction contract points back to the plan on disk",
          rc == 0 and plan_path in out
          and "re-read the approved plan" in out
          and "PLAN_IDENTITY_UNAVAILABLE" in out
          and "Never reconstruct" in out
          and "cache, not state" in out,
          out.strip())


def case_13_progressive_disclosure(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    rc, out = run(["resume", "--slug", "test-idea"], corpus)
    check("13  loader keeps rationale + transcript on-demand, never preloaded",
          rc == 0
          and "DESIGN_RATIONALE=on-demand (not preloaded)" in out
          and "RAW_TRANSCRIPT=on-demand (not preloaded)" in out
          and "full-chat" not in out.replace("RAW_TRANSCRIPT", ""),
          out.strip())


def case_14_no_private_transcript_path(tmp):
    """LINT (not a behavioural test): the mechanism must never depend on Claude Code's
    private session storage. Kept in the suite because it is the property most easily
    lost by a well-meaning doc edit."""
    offenders = []
    for path in list((ROOT / "scripts").glob("*.py")) + \
            [ROOT / "SKILL.md", ROOT / "README.md",
             ROOT / "references" / "approved-plan-template.md",
             ROOT / "references" / "brief-template.md"]:
        text = path.read_text(encoding="utf-8")
        for pattern in (r"\.claude/projects", r"\.claude/sessions", r"\.claude/history",
                        r"conversation transcript path"):
            if re.search(pattern, text):
                offenders.append("%s: %s" % (path.name, pattern))
    check("14  (lint) no private conversation/transcript path required anywhere",
          not offenders, "; ".join(offenders))


def case_15_fail_closed_on_missing_plan(tmp):
    """Plan gone after compaction: stop, never reconstruct."""
    corpus = make_corpus(tmp, status="building", plan=plan_text("test-idea"))
    (corpus / "test-idea" / "test-idea-approved-plan.md").unlink()
    rc, out = run(["resume", "--slug", "test-idea"], corpus)
    check("15a plan file gone → PLAN_IDENTITY_UNAVAILABLE, exit 2",
          rc == 2 and "PLAN_IDENTITY_UNAVAILABLE" in out
          and "Do not reconstruct" in out, "rc=%d\n%s" % (rc, out.strip()))

    corpus2 = make_corpus(Path(tmp) / "b", status="clarified")
    rc, out = run(["resume", "--slug", "test-idea"], corpus2)
    check("15b no plan yet → loader refuses to invent one",
          rc == 2 and "PLAN_IDENTITY_UNAVAILABLE" in out
          and "has not passed owner plan approval" in out, "rc=%d\n%s" % (rc, out.strip()))

    corpus3 = make_corpus(Path(tmp) / "c", status="planned", plan=plan_text("test-idea"))
    pointer = Path(tmp) / "c" / "CLAUDE.md"
    run(["pointer", "--slug", "test-idea", "--workstream", "TESTWS", "--into", str(pointer)], corpus3)
    (corpus3 / "test-idea" / "test-idea-approved-plan.md").unlink()
    rc, out = run(["resume", "--slug", "test-idea", "--pointer", str(pointer)], corpus3)
    check("15c a pointer to a vanished plan does not rescue it",
          rc == 2 and "PLAN_IDENTITY_UNAVAILABLE" in out, "rc=%d\n%s" % (rc, out.strip()))


# ------------------------------------------------ extra falsification ------

def case_16_sections_not_summarized_away(tmp):
    full = plan_text("test-idea")
    for number, heading in ((3, "## 3. Execution order"), (5, "## 5. Deferred work"),
                            (8, "## 8. Stop conditions"),
                            (10, "## 10. Current / next slice semantics"),
                            (11, "## 11. Precedence & coherence patches")):
        stripped = re.sub(r"\n%s\n.*?(?=\n## |\Z)" % re.escape(heading), "\n", full,
                          flags=re.S)
        corpus = make_corpus(Path(tmp) / ("s%d" % number), status="planned", plan=stripped)
        expect_fail("16  approved plan missing §%d → FAIL" % number,
                    corpus, "PLAN_SECTION_MISSING")


def case_17_plan_without_planned_status(tmp):
    corpus = make_corpus(tmp, status="clarified", plan=plan_text("test-idea"))
    expect_fail("17  plan bound but status still clarified → FAIL",
                corpus, "PLAN_WITHOUT_PLANNED_STATUS")


def case_18_path_traversal(tmp):
    corpus = make_corpus(tmp, status="planned", brief_extra={
        "approved_plan": "../other-idea/idea.md", "approved_plan_sha256": "c" * 64})
    expect_fail("18  approved_plan escaping the idea folder → FAIL",
                corpus, "PLAN_PATH_INVALID")


def case_19_version_filename_binding(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea", version=3),
                         brief_extra={"plan_version": "3"})
    expect_fail("19  plan_version contradicting the filename → FAIL",
                corpus, "PLAN_VERSION_MISMATCH")


def case_20_pointer_refuses_unproven_plan(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"),
                         bind_sha="d" * 64)
    pointer = Path(tmp) / "CLAUDE.md"
    rc, out = run(["pointer", "--slug", "test-idea", "--workstream", "TESTWS", "--into", str(pointer)], corpus)
    check("20  pointer refuses to advertise an unproven plan",
          rc == 2 and "PLAN_IDENTITY_UNAVAILABLE" in out and not pointer.exists(),
          "rc=%d\n%s" % (rc, out.strip()))


def case_21_wrong_source_brief(tmp):
    corpus = make_corpus(tmp, status="planned",
                         plan=plan_text("test-idea", source_brief="idea-elsewhere.md"))
    expect_fail("21  plan pointing at another brief → FAIL",
                corpus, "PLAN_SOURCE_BRIEF_MISMATCH")


def case_22_authority_boundary_required(tmp):
    corpus = make_corpus(tmp, status="planned",
                         plan=plan_text("test-idea", authority="execution-authority"))
    expect_fail("22  plan claiming execution authority → FAIL",
                corpus, "PLAN_AUTHORITY_INVALID")


def case_23_empty_sections(tmp):
    """A plan gutted to headings is the summarized-away failure in artifact form."""
    full = plan_text("test-idea")
    gutted = re.sub(r"(^## \d+\.[^\n]*\n).*?(?=\n## |\Z)", r"\1\n", full,
                    flags=re.S | re.M)
    corpus = make_corpus(tmp, status="planned", plan=gutted)
    expect_fail("23a plan gutted to bare headings → FAIL", corpus, "PLAN_SECTION_EMPTY")

    for number, heading in ((2, "## 2. Scope boundaries"),
                            (3, "## 3. Execution order"),
                            (9, "## 9. Acceptance criteria")):
        thin = re.sub(r"(\n%s\n).*?(?=\n## |\Z)" % re.escape(heading), r"\1None.\n", full,
                      flags=re.S)
        c = make_corpus(Path(tmp) / ("p%d" % number), status="planned", plan=thin)
        expect_fail("23b §%d reduced to a placeholder → FAIL" % number,
                    c, "PLAN_SECTION_SUMMARIZED_AWAY")

    # §11 legitimately says `None.` — that must stay valid
    ok = full.replace("## 11. Precedence & coherence patches\nNone.",
                      "## 11. Precedence & coherence patches\nNone.")
    c = make_corpus(Path(tmp) / "ok", status="planned", plan=ok)
    expect_pass("23c §11 saying `None.` stays VALID", c)


def case_24_frontmatter_ambiguity(tmp):
    """The gate must never read the frontmatter differently from a YAML reader."""
    base = plan_text("test-idea")

    nested = base.replace("authority: owner-approved-execution-intent",
                          "authority: owner-approved-execution-intent\n"
                          "review_notes:\n  status: approved\n  approval_state: approved")
    real = nested.replace("status: approved\n", "status: draft\n", 1) \
                 .replace("approval_state: approved\n", "approval_state: rejected\n", 1)
    corpus = make_corpus(tmp, status="planned", plan=real)
    expect_fail("24a nested keys cannot smuggle an approval → FAIL",
                corpus, "PLAN_FRONTMATTER_AMBIGUOUS")

    dup = base.replace("approval_state: approved",
                       "approval_state: approved\napproval_state: rejected")
    c = make_corpus(Path(tmp) / "d", status="planned", plan=dup)
    expect_fail("24b duplicate key → FAIL (not last-wins)",
                c, "PLAN_FRONTMATTER_AMBIGUOUS")

    multiline = base.replace(
        'approval_evidence: "plan mode accepted in session 2026-08-25"',
        'approval_evidence: "owner approved; see notes\n'
        '  status: NOT APPROVED — this was only a draft"')
    c = make_corpus(Path(tmp) / "m", status="planned", plan=multiline)
    expect_fail("24c a value running onto the next line → FAIL",
                c, "PLAN_FRONTMATTER_AMBIGUOUS")

    bom = "﻿" + base
    c = make_corpus(Path(tmp) / "b", status="planned", plan=bom)
    expect_pass("24d a UTF-8 BOM does not defeat the parser", c)


def case_25_self_approval(tmp):
    for who in ("the model itself", "Claude", "the assistant", "AI agent"):
        corpus = make_corpus(Path(tmp) / re.sub(r"\W", "", who), status="planned",
                             plan=plan_text("test-idea", approved_by=who))
        expect_fail("25  approved_by=%r (the agent, not the owner) → FAIL" % who,
                    corpus, "PLAN_NOT_APPROVED")


def case_26_malformed_hashes(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"),
                         bind_sha="deadbeef")
    expect_fail("26a approved_plan_sha256 that is not a sha256 → FAIL",
                corpus, "PLAN_HASH_MALFORMED")
    c = make_corpus(Path(tmp) / "b", status="planned",
                    plan=plan_text("test-idea", source_brief_sha256="not-a-hash"))
    expect_fail("26b source_brief_sha256 that is not a sha256 → FAIL",
                c, "PLAN_METADATA_INVALID")


def case_27_missing_binding_date(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    brief = corpus / "test-idea" / "idea-test-idea.md"
    brief.write_text(re.sub(r"plan_approved_at:.*\n", "", brief.read_text()),
                     encoding="utf-8")
    expect_fail("27  binding without plan_approved_at → FAIL",
                corpus, "PLAN_APPROVAL_METADATA_MISSING")


def case_28_symlink_escape(tmp):
    """A plan file that is really somewhere else is not content of this package."""
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    outside = Path(tmp) / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    real = outside / "test-idea-approved-plan.md"
    folder = corpus / "test-idea"
    link = folder / "test-idea-approved-plan.md"
    real.write_text(link.read_text(encoding="utf-8"), encoding="utf-8")
    link.unlink()
    link.symlink_to(real)
    expect_fail("28  approved_plan symlinked outside the idea folder → FAIL",
                corpus, "PLAN_PATH_INVALID")


def case_29_supersession_path_escape(tmp):
    slug = "test-idea"
    v2 = plan_text(slug, version=2, supersedes_plan="../stash/%s-approved-plan.md" % slug)
    corpus = make_corpus(tmp, status="planned", plan=v2,
                         plan_name="%s-approved-plan-v2.md" % slug,
                         brief_extra={"plan_version": "2"})
    expect_fail("29  history parked outside the idea folder → FAIL",
                corpus, "PLAN_PATH_INVALID")


def case_30_package_name_mismatch(tmp):
    """A brief whose filename does not match its folder must not be invisible."""
    corpus = Path(tmp) / "corpus"
    folder = corpus / "webbforvaltningen"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "idea-webb.md").write_text(
        brief_text("webb", status="planned"), encoding="utf-8")
    add_control(corpus)
    expect_fail("30  package whose brief name ≠ folder name is reported, not skipped",
                corpus, "PACKAGE_NAME_MISMATCH", slug="webbforvaltningen")


def case_31_long_supersession_chain(tmp):
    """65+ deliberate replans must not be mistaken for orphaned history."""
    slug = "test-idea"
    corpus = Path(tmp) / "corpus"
    folder = corpus / slug
    folder.mkdir(parents=True, exist_ok=True)
    total = 70
    names = ["%s-approved-plan.md" % slug] + \
            ["%s-approved-plan-v%d.md" % (slug, n) for n in range(2, total + 1)]
    for i, name in enumerate(names):
        version = i + 1
        kw = {}
        if version < total:
            kw["status"] = "superseded"
            kw["superseded_by_plan"] = names[i + 1]
        if version > 1:
            kw["supersedes_plan"] = names[i - 1]
        (folder / name).write_text(plan_text(slug, version=version, **kw), encoding="utf-8")
        _settle_plan(folder, name, slug)
    current = folder / names[-1]
    (folder / ("idea-%s.md" % slug)).write_text(
        brief_text(slug, status="building", approved_plan=names[-1],
                   approved_plan_sha256=sha256_text(current.read_text(encoding="utf-8")),
                   plan_version=str(total), plan_approved_at="2026-08-25",
                   execution_repo="~/nortropic/verkstadsgolvet",
                   execution_commit="a1b2c3d4e5f6", execution_slice="S1"),
        encoding="utf-8")
    add_control(corpus)
    expect_pass("31  a %d-version supersession chain stays VALID" % total, corpus,
                slug=slug)


def case_32_pointer_block_ambiguity(tmp):
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    pointer = Path(tmp) / "CLAUDE.md"
    pointer.write_text("# Repo\n\n<!-- NORTROPIC-ACTIVE-PLAN:END -->\n", encoding="utf-8")
    rc, out = run(["pointer", "--slug", "test-idea", "--workstream", "TESTWS", "--into", str(pointer)], corpus)
    check("32a a stray END marker → refuse to write, not silently append",
          rc == 2 and "POINTER_BLOCK_AMBIGUOUS" in out, "rc=%d\n%s" % (rc, out.strip()))

    pointer.write_text("# Repo\n", encoding="utf-8")
    for _ in range(3):
        run(["pointer", "--slug", "test-idea", "--workstream", "TESTWS", "--into", str(pointer)], corpus)
    text = pointer.read_text(encoding="utf-8")
    check("32b repeated writes are idempotent — exactly one block",
          text.count("NORTROPIC-ACTIVE-PLAN:BEGIN") == 1
          and text.count("NORTROPIC-ACTIVE-PLAN:END") == 1
          and read_pointer_slug(text) == "test-idea",
          text[:400])


def read_pointer_slug(text):
    m = re.search(r"^ACTIVE_INTAKE_SLUG:\s*(\S+)", text, re.M)
    return m.group(1) if m else None


def case_33_cli_ergonomics(tmp):
    """Every command the docs print must run as printed."""
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    proc = subprocess.run(
        [sys.executable, str(PLAN_CONTRACT), "validate", "--corpus", str(corpus)],
        capture_output=True, text=True)
    check("33a --corpus works AFTER the subcommand too",
          proc.returncode == 0 and "2/2 idea packages" in proc.stdout
          and "PASS  [test-idea]" in proc.stdout,
          "rc=%d\n%s" % (proc.returncode, (proc.stdout + proc.stderr).strip()))

    rc, out = run(["hash", str(Path(tmp) / "nope.md")], corpus)
    check("33b hash on a missing file fails cleanly, no traceback",
          rc == 1 and "Traceback" not in out and "not a readable file" in out, out.strip())


def case_34_fenced_template_smuggling(tmp):
    """Quoting the template in a code fence is pasting sections, not writing them.

    This is the plausible-accident form of the summarized-away plan: an agent that
    pastes the template as a reference block would otherwise satisfy all eleven
    sections while the real body says "see the chat".
    """
    fm = plan_text("test-idea").split("---\n")[1]
    template = PLAN_SECTIONS.format(title="Test idea", version=1)
    smuggled = ("---\n" + fm + "---\n"
                "# Approved plan\n\nThe actual plan was too long, see the chat.\n\n"
                "Here is the template I was told to follow:\n\n"
                "```markdown\n" + template + "\n```\n")
    corpus = make_corpus(tmp, status="planned", plan=smuggled)
    expect_fail("34a sections quoted inside a code fence do not count → FAIL",
                corpus, "PLAN_SECTION_MISSING")

    # ...while a code block INSIDE a real section is legitimate plan material
    with_code = plan_text("test-idea").replace(
        "Slice 1 — foundation. Slice 2 — the loader. Slice 3 — the pointer.",
        "Slice 1 — foundation, verified with:\n\n```bash\npython3 plan_contract.py "
        "validate\n```\n\nSlice 2 — the loader. Slice 3 — the pointer.")
    c = make_corpus(Path(tmp) / "ok", status="planned", plan=with_code)
    expect_pass("34b a fenced snippet inside a real section stays VALID", c)


def case_35_terse_but_honest_plan(tmp):
    """The placeholder check must not punish a short, complete answer."""
    # Edit the BODY, then build the plan around it, so the content hash is computed
    # over the final bytes. Editing a plan after its hash exists is tampering — which
    # case R3 tests on purpose, and which must not be how a fixture is built.
    body = PLAN_SECTIONS.format(title="Test idea", version=1)
    body = re.sub(r"(## 2\. Scope boundaries\n).*?(?=\n## )",
                  r"\1Only the intake skill. No repo changes.\n", body, flags=re.S)
    body = re.sub(r"(## 9\. Acceptance criteria\n).*?(?=\n## )",
                  r"\1`validate` exits 0 on the corpus.\n", body, flags=re.S)
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea", body=body))
    expect_pass("35a a terse but complete §2/§9 stays VALID", corpus)

    for placeholder in ("TBD", "None.", "see the chat", "later", "N/A"):
        thin_body = re.sub(r"(## 3\. Execution order\n).*?(?=\n## )",
                           r"\1%s\n" % placeholder,
                           PLAN_SECTIONS.format(title="Test idea", version=1), flags=re.S)
        thin = plan_text("test-idea", body=thin_body)
        c = make_corpus(Path(tmp) / re.sub(r"\W", "", placeholder), status="planned",
                        plan=thin)
        expect_fail("35b §3 = %r → FAIL" % placeholder,
                    c, "PLAN_SECTION_SUMMARIZED_AWAY")


def case_36_owner_names_not_false_positives(tmp):
    """approved_by must refuse the agent without refusing the owner's own org name."""
    for who in ("Johnny (Nortropic)", "Johnny (Nortropic AI)", "Johnny — Nortropic AI AB",
                "Ai Nguyen", "Aiko Tanaka", "Bo Modéer"):
        corpus = make_corpus(Path(tmp) / re.sub(r"\W", "", who), status="planned",
                             plan=plan_text("test-idea", approved_by=who))
        expect_pass("36a approved_by=%r (a real owner) stays VALID" % who, corpus)
    for who in ("Claude", "the model itself", "AI agent", "assistant", "an AI"):
        corpus = make_corpus(Path(tmp) / ("x" + re.sub(r"\W", "", who)), status="planned",
                             plan=plan_text("test-idea", approved_by=who))
        expect_fail("36b approved_by=%r (the agent) → FAIL" % who,
                    corpus, "PLAN_NOT_APPROVED")


def case_37_yaml_comment_parity(tmp):
    """A single space before `#` starts a YAML comment; the gate must agree."""
    single = plan_text("test-idea").replace(
        "approved_at: 2026-08-25", "approved_at: 2026-08-25 # approved in plan mode")
    corpus = make_corpus(tmp, status="planned", plan=single)
    expect_pass("37a a one-space `# comment` is stripped, as YAML would", corpus)

    versioned = plan_text("test-idea").replace(
        "plan_version: 1", "plan_version: 1 # first version")
    c = make_corpus(Path(tmp) / "v", status="planned", plan=versioned)
    expect_pass("37b a comment on a constrained field does not corrupt its value", c)


def case_38_hardlinked_plan(tmp):
    """A plan hard-linked from outside is not sole content of this package."""
    corpus = make_corpus(tmp, status="planned", plan=plan_text("test-idea"))
    outside = Path(tmp) / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    link = corpus / "test-idea" / "test-idea-approved-plan.md"
    os.link(str(link), str(outside / "copy.md"))
    expect_fail("38  approved_plan hard-linked from outside the package → FAIL",
                corpus, "PLAN_PATH_INVALID")


# ------------------------------------------------- named regression --------

def regression_survives_compaction(tmp):
    """APPROVED_PLAN_SURVIVES_COMPACTION_AND_FRESH_SESSION.

    Reproduces the real failure against the new design. A long approved plan is
    persisted and bound; a target repo is created and advanced; the pointer is
    installed. Then the session is destroyed — this is modelled honestly, as a new
    process whose ONLY inputs are the repository and the intake corpus. Nothing about
    the plan is carried in memory.
    """
    slug = "webbforvaltningen-regression"
    long_body = PLAN_SECTIONS.format(title="Webbförvaltningen (regression fixture)",
                                     version=1)
    long_body += "\n" + "\n".join(
        "Slice %d — detail line that a summary would have destroyed." % i
        for i in range(1, 120))
    repo_path = Path(tmp) / "target-repo"
    corpus = make_corpus(tmp, slug=slug, status="building",
                         plan=plan_text(slug, title="Webbförvaltningen (regression "
                                                    "fixture)", body=long_body,
                                        canonical_execution_repo=str(repo_path)))
    plan_file = corpus / slug / ("%s-approved-plan.md" % slug)
    plan_sha = sha256_text(plan_file.read_text(encoding="utf-8"))

    repo = repo_path
    repo.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, env=env)
    (repo / "CLAUDE.md").write_text("# Target repo\n", encoding="utf-8")
    (repo / "slice1.txt").write_text("slice 1 implemented\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "slice 1"], check=True, env=env)

    rc, out = run(["pointer", "--slug", slug, "--workstream", "WEBBFORVALTNINGEN",
                   "--into", str(repo / "CLAUDE.md"),
                   "--execution-pointer", "slice 1 done"], corpus)
    claude_md = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    check("R1  pointer block is actually in the target repo's CLAUDE.md",
          rc == 0 and "# Target repo" in claude_md          # pre-existing content kept
          and "ACTIVE_INTAKE_SLUG: %s" % slug in claude_md
          and "ACTIVE_WORKSTREAM: WEBBFORVALTNINGEN" in claude_md
          and plan_sha in claude_md
          and "re-read the approved plan" in claude_md,
          "rc=%d, file=%r" % (rc, claude_md[:300]))

    # ---- compaction happens here: everything conversational is gone ----
    rc, out = run(["resume", "--slug", slug, "--target-repo", str(repo),
                   "--pointer", str(repo / "CLAUDE.md")], corpus)
    check("R2  fresh session recovers the exact plan identity after compaction",
          rc == 0 and ("PLAN_IDENTITY=%s@sha256:%s" % (plan_file.resolve(), plan_sha)) in out
          and "PLAN_STATUS=APPROVED" in out,
          "rc=%d\n%s" % (rc, out.strip()))

    # R3: identity is VERIFIED against the bytes on disk, not merely echoed. Tamper with
    # the file and the same command must now refuse.
    original = plan_file.read_text(encoding="utf-8")
    plan_file.write_text(original + "\nA line nobody approved.\n", encoding="utf-8")
    rc_t, out_t = run(["resume", "--slug", slug, "--target-repo", str(repo)], corpus)
    plan_file.write_text(original, encoding="utf-8")
    rc_r, out_r = run(["resume", "--slug", slug, "--target-repo", str(repo)], corpus)
    check("R3  identity is verified against the bytes: post-approval edit → refusal",
          rc_t == 2 and "PLAN_IDENTITY_UNAVAILABLE" in out_t
          and "PLAN_HASH_MISMATCH" in out_t
          and rc_r == 0 and plan_sha in out_r,
          "tampered rc=%d / restored rc=%d\n%s" % (rc_t, rc_r, out_t.strip()))

    check("R4  target repository evidence is read, not assumed",
          "TARGET_REPO_EVIDENCE=head:" in out and "branch:main" in out, out.strip())
    check("R5  reconciliation is left to the agent, not faked by the tool",
          "PLAN_CURRENT_REPO_RECONCILIATION=PENDING_AGENT_READ" in out
          and "the repository wins" in out, out.strip())

    # R6: the tool cannot stop a model from writing a thin plan, but it CAN refuse one.
    # Gut the long plan down to headings and it must no longer validate.
    gutted = re.sub(r"(^## \d+\.[^\n]*\n).*?(?=\n## |\Z)", r"\1\n", original,
                    flags=re.S | re.M)
    plan_file.write_text(gutted, encoding="utf-8")
    rc_g, out_g = run(["validate", "--plan-file", str(plan_file)], corpus)
    plan_file.write_text(original, encoding="utf-8")
    rc_i, out_i = run(["validate", "--plan-file", str(plan_file)], corpus)
    check("R6  a plan summarized down to headings is REFUSED, the intact one accepted",
          rc_g == 1 and ("PLAN_SECTION_EMPTY" in out_g
                         or "PLAN_SECTION_SUMMARIZED_AWAY" in out_g)
          and rc_i == 0 and "well-formed" in out_i,
          "gutted rc=%d / intact rc=%d\n%s\n%s"
          % (rc_g, rc_i, out_g.strip(), out_i.strip()))

    # R7: recovery needs nothing but the slug and the corpus — no owner, no old chat, no
    # cwd, no environment. Run it from / with a scrubbed environment.
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    proc = subprocess.run(
        [sys.executable, str(PLAN_CONTRACT), "--corpus", str(corpus),
         "resume", "--slug", slug],
        capture_output=True, text=True, cwd="/", env=env)
    check("R7  recovery needs only slug + corpus: no owner, no session, no environment",
          proc.returncode == 0 and plan_sha in proc.stdout
          and "PLAN_IDENTITY_UNAVAILABLE" not in proc.stdout,
          "rc=%d\n%s" % (proc.returncode, (proc.stdout + proc.stderr).strip()))

    # and the counterfactual: the pre-fix world, where nothing was persisted
    corpus_before = make_corpus(Path(tmp) / "before", slug=slug, status="building")
    rc, out = run(["resume", "--slug", slug], corpus_before)
    check("R8  counterfactual (pre-fix, no durable plan) fails closed instead of guessing",
          rc == 2 and "LEGACY_PLAN_ARTIFACT_MISSING" in out
          and "Do not reconstruct" in out, "rc=%d\n%s" % (rc, out.strip()))


# ------------------------------------------------------------------ main ---

CASES = [
    case_01_planned_without_plan, case_02_plan_file_missing, case_03_hash_mismatch,
    case_03b_hash_missing, case_04_wrong_slug, case_05_not_owner_approved,
    case_06_clarified_without_plan, case_07_building_with_plan,
    case_08_verified_with_plan, case_09_supersession, case_10_loader_deterministic,
    case_11_stale_pointer, case_12_reload_contract, case_13_progressive_disclosure,
    case_14_no_private_transcript_path, case_15_fail_closed_on_missing_plan,
    case_16_sections_not_summarized_away, case_17_plan_without_planned_status,
    case_18_path_traversal, case_19_version_filename_binding,
    case_20_pointer_refuses_unproven_plan, case_21_wrong_source_brief,
    case_22_authority_boundary_required, case_23_empty_sections,
    case_24_frontmatter_ambiguity, case_25_self_approval, case_26_malformed_hashes,
    case_27_missing_binding_date, case_28_symlink_escape,
    case_29_supersession_path_escape, case_30_package_name_mismatch,
    case_31_long_supersession_chain, case_32_pointer_block_ambiguity,
    case_33_cli_ergonomics, case_34_fenced_template_smuggling,
    case_35_terse_but_honest_plan, case_36_owner_names_not_false_positives,
    case_37_yaml_comment_parity, case_38_hardlinked_plan,
]


def main():
    if not PLAN_CONTRACT.exists():
        sys.exit("FAIL: %s missing" % PLAN_CONTRACT)
    for case in CASES:
        tmp = tempfile.mkdtemp(prefix="plan-contract-")
        try:
            case(tmp)
        except KeyboardInterrupt:
            raise
        # BaseException, not Exception: a stubbed dependency raises SystemExit, which
        # would otherwise unwind the suite to a green exit code having run nothing.
        except BaseException as exc:
            check("%s raised %s" % (case.__name__, type(exc).__name__), False,
                  str(exc)[:300])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n--- APPROVED_PLAN_SURVIVES_COMPACTION_AND_FRESH_SESSION ---")
    tmp = tempfile.mkdtemp(prefix="plan-regression-")
    try:
        regression_survives_compaction(tmp)
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        check("regression raised %s" % type(exc).__name__, False, str(exc)[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [name for name, ok, _ in RESULTS if not ok]
    print("\n%d/%d checks passed" % (len(RESULTS) - len(failed), len(RESULTS)))
    if failed:
        print("failed: %s" % ", ".join(failed))
    # A suite that exits 0 having run nothing reports success. A stub that raises
    # SystemExit(0) mid-run is not an Exception and would otherwise slip past.
    if len(RESULTS) < MIN_CHECKS:
        print("\nSUITE DID NOT RUN: only %d checks executed, expected at least %d."
              % (len(RESULTS), MIN_CHECKS))
        sys.exit(1)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
