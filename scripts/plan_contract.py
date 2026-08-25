#!/usr/bin/env python3
"""Approved-plan contract — the mechanical gate behind `status: planned`.

`planned` is not a word an agent may write; it is a provable state. This script is
the proof. It owns the HOW side of an intake package:

  <slug>-plan-candidate.md    what Plan Mode produced and the owner actually read
  <slug>-approved-plan.md     the same body, promoted, bound by hash to the brief

Companion: `context_contract.py` owns the source side (manifest, clarifications,
coverage gate, provenance tracing).

Subcommands
-----------
  validate [--slug S ...]        Validate the corpus (or named slugs). Exit 1 on FAIL.
  validate --plan-file F         Check one plan/candidate artifact alone.
  coherence --slug S             Brief-vs-plan delta the owner reads before approving.
  approve --slug S --candidate-sha X --approved-by "..." --evidence "..."
                                 Promote the candidate the owner approved. Body copied
                                 verbatim; refuses if X is not the candidate on disk.
  map --slug S                   Derived plan map (JSON on stdout). Never stored.
  resume --slug S                Fresh-session loader: full context-package identity.
  pointer --slug S --into FILE   Write/update this workstream's reload-pointer block.
  hash FILE                      sha256 of a file. `--body` hashes content identity.

Corpus root: --corpus (before or after the subcommand), else $NORTROPIC_INTAKE_CORPUS,
else ~/nortropic/innovation-intake.

Exact approval
--------------
The owner approves BYTES, not a promise. A plan's content identity is the sha256 of
its body (everything after the frontmatter), so a candidate and the plan promoted from
it are provably the same document even though their metadata differs by design. The
candidate file is never mutated afterwards: it stays in the package as evidence of
exactly what was on screen when the owner said yes.

What this is NOT
----------------
Not a database, not a task ledger, not execution state. The approved plan is durable
owner intent; each target repository is the truth for its own implementation state;
pointers are caches. On conflict, repository evidence wins and the discrepancy is
reported — never silently resolved.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from intake_common import (  # noqa: E402
    Finding, SHA256_RE, body_sha256, corpus_root, expand, fails, fm_list, fm_str,
    git_commit_exists, git_evidence, git_immutability, id_kind, parse_ids, parse_slices,
    read_frontmatter, sha256_file, sha256_text,
)
import context_contract as ctx  # noqa: E402

# Lifecycle states that REQUIRE a durable approved plan.
PLAN_REQUIRED_STATES = {"planned", "building", "verified"}
# States where a plan must NOT yet be bound (a plan implies at least `planned`).
PRE_PLAN_STATES = {"idea", "clarified", "ready-for-clarification"}
# States Intake may only OBSERVE, never author from its own say-so.
EXECUTION_OBSERVED_STATES = {"building", "verified"}
VALID_BRIEF_STATES = PLAN_REQUIRED_STATES | PRE_PLAN_STATES | {"superseded"}

PLAN_FILE_RE_TMPL = r"^{slug}-approved-plan(?:-v(\d+))?\.md$"
CANDIDATE_FILE_RE_TMPL = r"^{slug}-plan-candidate(?:-v(\d+))?\.md$"

PLAN_REQUIRED_FIELDS = {
    "type": {"approved-plan"},
    "status": {"approved", "superseded"},
    "approval_state": {"approved"},
    "slug": None,
    "owner": None,
    "approved_at": None,
    "approved_by": None,
    "approval_evidence": None,
    "plan_version": None,
    "source_brief": None,
    "source_brief_sha256": None,
    "canonical_execution_repo": None,
    "plan_source": {"claude-code-plan-mode", "owner-authored", "recovered-from-known-source"},
    "fidelity": {"full", "partial"},
    "authority": {"owner-approved-execution-intent"},
    "plan_content_sha256": None,
    "approved_candidate": None,
    "approved_candidate_sha256": None,
}
CANDIDATE_REQUIRED_FIELDS = {
    "type": {"plan-candidate"},
    "status": {"candidate"},
    "slug": None,
    "owner": None,
    "created": None,
    "plan_version": None,
    "source_brief": None,
    "source_brief_sha256": None,
    "canonical_execution_repo": None,
    "plan_source": {"claude-code-plan-mode", "owner-authored", "recovered-from-known-source"},
    "fidelity": {"full", "partial"},
}

PLAN_REQUIRED_SECTIONS = [
    (1, r"authority boundary"),
    (2, r"scope boundaries"),
    (3, r"execution order"),
    (4, r"decisions carried"),
    (5, r"deferred"),
    (6, r"rejected paths"),
    (7, r"owner-only transitions"),
    (8, r"stop conditions"),
    (9, r"acceptance criteria"),
    (10, r"current\s*/\s*next slice"),
    (11, r"precedence"),
]
SUBSTANTIVE_SECTIONS = {2, 3, 9}
SUBSTANTIVE_MIN_WORDS = 4
PLACEHOLDER_RE = re.compile(
    r"^(none|n/?a|tbd|todo|later|see (the )?(chat|plan|transcript)|-{1,3}|\.)\.?$", re.I)

SELF_APPROVAL_RE = re.compile(
    r"\b(claude|chatgpt|gpt-?\d*|llm|copilot|the model|this model|the assistant|"
    r"the agent|an? ai\b|ai agent|myself|itself)\b", re.I)
SELF_APPROVAL_EXACT = {"ai", "bot", "model", "agent", "assistant", "self",
                       "the ai", "the bot", "the model", "the agent"}

POINTER_BEGIN = "<!-- NORTROPIC-ACTIVE-PLAN:BEGIN"
POINTER_END = "<!-- NORTROPIC-ACTIVE-PLAN:END"
MARKER_RE = re.compile(
    r"<!--\s*NORTROPIC-ACTIVE-PLAN:(BEGIN|END)((?:\s+\w+=[^\s>]+)*)\s*-->")


# ---------------------------------------------------------------- helpers --

def is_bare_filename(ref):
    return bool(ref) and "/" not in ref and "\\" not in ref and not ref.startswith(".")


def plan_version_from_name(name, slug, template=PLAN_FILE_RE_TMPL):
    m = re.match(template.format(slug=re.escape(slug)), name)
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else 1


def parse_execution_targets(fm):
    """`execution_targets: [path=role, path=role]` -> [(repo, role)]. Flat by design."""
    out = []
    for item in fm_list(fm, "execution_targets"):
        repo, _, role = item.partition("=")
        out.append((repo.strip(), role.strip()))
    return out


def section_map(body):
    from intake_common import section_bodies
    return section_bodies(body)


# ------------------------------------------------------------- validation --

def validate_slug(corpus, slug):
    """Validate one idea package's plan side. Returns (findings, facts)."""
    findings = []
    facts = {"slug": slug}
    folder = Path(corpus) / slug
    brief_path = folder / ("idea-%s.md" % slug)

    if not brief_path.exists():
        others = sorted(p.name for p in folder.glob("idea-*.md")) if folder.is_dir() else []
        if others:
            findings.append(Finding(
                slug, "PACKAGE_NAME_MISMATCH",
                "folder %s holds %s, not idea-%s.md — a package whose brief does not "
                "match its folder is invisible to every slug-addressed check"
                % (slug, others, slug)))
        else:
            findings.append(Finding(slug, "BRIEF_MISSING", "no %s" % brief_path))
        return findings, facts

    fm, brief_body, fm_errors = read_frontmatter(brief_path)
    for err in fm_errors:
        findings.append(Finding(slug, "BRIEF_FRONTMATTER_AMBIGUOUS",
                                "idea-%s.md: %s" % (slug, err)))
    status = fm_str(fm, "status")
    facts["status"] = status
    facts["brief"] = str(brief_path)
    facts["brief_ids"] = parse_ids(brief_body)

    brief_slug = fm_str(fm, "slug")
    if brief_slug and brief_slug != slug:
        findings.append(Finding(
            slug, "PACKAGE_NAME_MISMATCH",
            "idea-%s.md declares slug=%r — a package whose brief names another idea is "
            "addressed as one thing and reads as another" % (slug, brief_slug)))

    if status not in VALID_BRIEF_STATES:
        findings.append(Finding(slug, "BRIEF_STATUS_INVALID",
                                "status=%r is not a lifecycle value" % status))
        return findings, facts

    plan_ref = fm_str(fm, "approved_plan")
    plan_sha = fm_str(fm, "approved_plan_sha256")
    facts["approved_plan"] = plan_ref or None

    if status in PLAN_REQUIRED_STATES and not plan_ref:
        findings.append(Finding(
            slug, "LEGACY_PLAN_ARTIFACT_MISSING",
            "status=%s requires approved_plan; brief has none. Recover the "
            "owner-approved plan from a known source or move status back to "
            "clarified — never fabricate it." % status))
        return findings, facts

    if status in PRE_PLAN_STATES and plan_ref:
        findings.append(Finding(
            slug, "PLAN_WITHOUT_PLANNED_STATUS",
            "approved_plan is bound but status=%s; a bound plan means at least "
            "planned" % status))

    if not plan_ref:
        _check_orphan_plans(corpus, slug, None, findings)
        findings.extend(_check_execution_state(slug, folder, fm, facts))
        return findings, facts

    if not is_bare_filename(plan_ref):
        findings.append(Finding(slug, "PLAN_PATH_INVALID",
                                "approved_plan must be a bare filename in the idea "
                                "folder, got %r" % plan_ref))
        return findings, facts

    plan_path = folder / plan_ref
    if not plan_path.exists():
        findings.append(Finding(slug, "PLAN_FILE_MISSING", "%s does not exist" % plan_path))
        return findings, facts
    try:
        if plan_path.resolve().parent != folder.resolve():
            findings.append(Finding(
                slug, "PLAN_PATH_INVALID",
                "%s resolves to %s, outside the idea folder — the plan must be content "
                "of this package, not a link to elsewhere"
                % (plan_ref, plan_path.resolve())))
            return findings, facts
        if plan_path.stat().st_nlink > 1:
            findings.append(Finding(
                slug, "PLAN_PATH_INVALID",
                "%s is hard-linked from elsewhere (st_nlink=%d) — editing the other "
                "path would silently break this package's recorded hash"
                % (plan_ref, plan_path.stat().st_nlink)))
            return findings, facts
    except OSError as exc:
        findings.append(Finding(slug, "PLAN_PATH_INVALID", "%s: %s" % (plan_ref, exc)))
        return findings, facts
    facts["plan_path"] = str(plan_path)

    actual_sha = sha256_file(plan_path)
    facts["plan_sha256"] = actual_sha
    if not plan_sha:
        findings.append(Finding(slug, "PLAN_HASH_MISSING",
                                "brief records no approved_plan_sha256 (actual %s)" % actual_sha))
    elif not SHA256_RE.match(plan_sha):
        findings.append(Finding(slug, "PLAN_HASH_MALFORMED",
                                "approved_plan_sha256=%r is not a sha256" % plan_sha))
    elif plan_sha.lower() != actual_sha:
        findings.append(Finding(
            slug, "PLAN_HASH_MISMATCH",
            "brief records %s, file is %s — the approved plan changed after "
            "approval, or the pointer is stale" % (plan_sha, actual_sha)))

    if not fm_str(fm, "plan_approved_at"):
        findings.append(Finding(slug, "PLAN_APPROVAL_METADATA_MISSING",
                                "brief binds a plan but records no plan_approved_at"))

    pfm, pbody, pfm_errors = read_frontmatter(plan_path)
    for err in pfm_errors:
        findings.append(Finding(slug, "PLAN_FRONTMATTER_AMBIGUOUS",
                                "%s: %s" % (plan_ref, err)))
    facts["plan_version"] = pfm.get("plan_version")
    facts["plan_fm"] = pfm
    facts["plan_slices"] = parse_slices(pbody)
    findings.extend(_check_plan_artifact(slug, plan_path, pfm, pbody, expect_current=True))
    findings.extend(_check_exact_approval(slug, folder, plan_path, pfm, pbody))

    brief_pv = fm_str(fm, "plan_version")
    if brief_pv and str(pfm.get("plan_version", "")).strip() != brief_pv:
        findings.append(Finding(slug, "PLAN_VERSION_MISMATCH",
                                "brief plan_version=%s, plan file says %s"
                                % (brief_pv, pfm.get("plan_version"))))

    findings.extend(_check_chain(corpus, slug, plan_ref))
    _check_orphan_plans(corpus, slug, plan_ref, findings)
    findings.extend(_check_execution_state(slug, folder, fm, facts))
    return findings, facts


def _check_plan_artifact(slug, plan_path, pfm, pbody, expect_current, candidate=False):
    """Field + section checks on one plan or candidate file."""
    out = []
    name = plan_path.name
    required = CANDIDATE_REQUIRED_FIELDS if candidate else PLAN_REQUIRED_FIELDS

    for field, allowed in required.items():
        value = pfm.get(field)
        value = value.strip() if isinstance(value, str) else value
        if not value:
            code = ("PLAN_APPROVAL_METADATA_MISSING"
                    if field in ("approved_at", "approved_by", "approval_evidence",
                                 "approval_state", "plan_version",
                                 "approved_candidate", "approved_candidate_sha256")
                    else "PLAN_METADATA_MISSING")
            out.append(Finding(slug, code, "%s: missing required field %r" % (name, field)))
            continue
        if allowed and str(value) not in allowed:
            code = {"type": "PLAN_TYPE_INVALID",
                    "approval_state": "PLAN_NOT_APPROVED",
                    "status": "PLAN_STATUS_INVALID",
                    "authority": "PLAN_AUTHORITY_INVALID"}.get(field, "PLAN_METADATA_INVALID")
            out.append(Finding(slug, code, "%s: %s=%r must be one of %s"
                               % (name, field, value, sorted(allowed))))

    if not candidate:
        approved_by = fm_str(pfm, "approved_by")
        if approved_by and (SELF_APPROVAL_RE.search(approved_by)
                            or approved_by.lower() in SELF_APPROVAL_EXACT):
            out.append(Finding(slug, "PLAN_NOT_APPROVED",
                               "%s: approved_by=%r names the agent — this field must "
                               "name the owner who approved the plan" % (name, approved_by)))

    for field in ("source_brief_sha256", "plan_content_sha256",
                  "approved_candidate_sha256"):
        value = fm_str(pfm, field)
        if value and not SHA256_RE.match(value):
            out.append(Finding(slug, "PLAN_METADATA_INVALID",
                               "%s: %s=%r is not a sha256" % (name, field, value)))

    if fm_str(pfm, "slug") != slug:
        out.append(Finding(slug, "PLAN_SLUG_MISMATCH",
                           "%s: slug=%r does not match the idea folder %r"
                           % (name, pfm.get("slug"), slug)))

    expected_brief = "idea-%s.md" % slug
    if fm_str(pfm, "source_brief") != expected_brief:
        out.append(Finding(slug, "PLAN_SOURCE_BRIEF_MISMATCH",
                           "%s: source_brief=%r, expected %r"
                           % (name, pfm.get("source_brief"), expected_brief)))

    for field in ("supersedes_plan", "superseded_by_plan", "approved_candidate"):
        ref = fm_str(pfm, field)
        if ref and not is_bare_filename(ref):
            out.append(Finding(slug, "PLAN_PATH_INVALID",
                               "%s: %s=%r must be a bare filename in the same idea "
                               "folder" % (name, field, ref)))

    template = CANDIDATE_FILE_RE_TMPL if candidate else PLAN_FILE_RE_TMPL
    name_version = plan_version_from_name(name, slug, template)
    if name_version is None:
        out.append(Finding(slug, "PLAN_FILENAME_INVALID",
                           "%s does not match <slug>-%s[-vN].md"
                           % (name, "plan-candidate" if candidate else "approved-plan")))
    elif str(pfm.get("plan_version", "")).strip() not in ("", str(name_version)):
        out.append(Finding(slug, "PLAN_VERSION_MISMATCH",
                           "%s: plan_version=%s contradicts the filename (v%d)"
                           % (name, pfm.get("plan_version"), name_version)))

    if expect_current and not candidate:
        if fm_str(pfm, "status") == "superseded" or pfm.get("superseded_by_plan"):
            out.append(Finding(slug, "PLAN_SUPERSEDED_POINTER",
                               "%s is superseded (superseded_by_plan=%r) — the brief "
                               "must point at the current version"
                               % (name, pfm.get("superseded_by_plan"))))

    out.extend(_check_targets(slug, name, pfm))
    out.extend(_check_plan_sections(slug, name, pbody))
    return out


def _check_targets(slug, name, pfm):
    out = []
    targets = parse_execution_targets(pfm)
    if not targets:
        return out
    seen = set()
    for repo, role in targets:
        if not repo:
            out.append(Finding(slug, "EXECUTION_TARGET_INVALID",
                               "%s: an execution_targets entry has no repo" % name))
            continue
        if repo in seen:
            out.append(Finding(slug, "EXECUTION_TARGET_INVALID",
                               "%s: execution_targets repeats %r" % (name, repo)))
        seen.add(repo)
        if role not in ctx.TARGET_ROLES:
            out.append(Finding(
                slug, "EXECUTION_TARGET_ROLE_INVALID",
                "%s: execution_targets entry %r has role=%r; must be one of %s — a "
                "plan spanning repos must preserve their authority differences"
                % (name, repo, role, sorted(ctx.TARGET_ROLES))))
    canonical = fm_str(pfm, "canonical_execution_repo")
    if canonical and canonical != "unknown" and seen and canonical not in seen:
        out.append(Finding(slug, "EXECUTION_TARGET_INVALID",
                           "%s: canonical_execution_repo=%r is not among execution_targets"
                           % (name, canonical)))
    return out


def _check_plan_sections(slug, name, pbody):
    out = []
    found = section_map(pbody)
    for number, fragment in PLAN_REQUIRED_SECTIONS:
        entry = found.get(number)
        label = fragment.replace(r"\s*", " ")
        if not entry or not re.search(fragment, entry[0], re.I):
            out.append(Finding(slug, "PLAN_SECTION_MISSING",
                               "%s: no '## %d. …%s…' section — the plan may not "
                               "summarize this away" % (name, number, label)))
            continue
        content = entry[1].strip()
        if not content:
            out.append(Finding(slug, "PLAN_SECTION_EMPTY",
                               "%s: §%d (%s) is an empty heading — write the content, "
                               "or `None.` if the approved plan genuinely had none"
                               % (name, number, label)))
            continue
        if number in SUBSTANTIVE_SECTIONS:
            if PLACEHOLDER_RE.match(content) or len(content.split()) < SUBSTANTIVE_MIN_WORDS:
                out.append(Finding(
                    slug, "PLAN_SECTION_SUMMARIZED_AWAY",
                    "%s: §%d (%s) is a placeholder (%r) — this section can never "
                    "honestly be one; persist what the owner approved"
                    % (name, number, label, content[:60])))

    slices = parse_slices(pbody)
    if not slices:
        out.append(Finding(
            slug, "PLAN_SLICES_MISSING",
            "%s: §3 contains no `### S1 — …` slices. Execution order needs addressable "
            "slices so acceptance criteria, resume and implementation evidence can "
            "point at them." % name))
    else:
        numbers = sorted(int(s[1:]) for s in slices)
        if numbers != list(range(1, len(numbers) + 1)):
            out.append(Finding(slug, "PLAN_SLICE_IDS_INVALID",
                               "%s: slice ids are %s — they must run S1..S%d without "
                               "gaps or duplicates"
                               % (name, sorted(slices), len(numbers))))
    return out


def _check_exact_approval(slug, folder, plan_path, pfm, pbody):
    """The owner approved bytes. Prove the plan carries exactly those bytes."""
    out = []
    name = plan_path.name
    declared_content = fm_str(pfm, "plan_content_sha256")
    actual_content = sha256_text(pbody)
    if declared_content and SHA256_RE.match(declared_content) \
            and declared_content.lower() != actual_content:
        out.append(Finding(
            slug, "PLAN_CONTENT_SHA_MISMATCH",
            "%s: plan_content_sha256=%s but the body hashes to %s — the plan's content "
            "changed after approval" % (name, declared_content[:16] + "…",
                                        actual_content[:16] + "…")))

    cand_ref = fm_str(pfm, "approved_candidate")
    cand_sha = fm_str(pfm, "approved_candidate_sha256")
    if not cand_ref or not is_bare_filename(cand_ref):
        return out
    cand_path = folder / cand_ref
    if not cand_path.exists():
        out.append(Finding(
            slug, "PLAN_CANDIDATE_MISSING",
            "%s: approved_candidate=%s does not exist — the artifact the owner actually "
            "read is the receipt for this approval and must be kept" % (name, cand_ref)))
        return out
    actual_cand = sha256_file(cand_path)
    if cand_sha and SHA256_RE.match(cand_sha) and cand_sha.lower() != actual_cand:
        out.append(Finding(
            slug, "PLAN_CANDIDATE_SHA_MISMATCH",
            "%s: approved_candidate_sha256=%s but %s hashes to %s — the candidate the "
            "owner approved was altered after approval"
            % (name, cand_sha[:16] + "…", cand_ref, actual_cand[:16] + "…")))
    cand_body = body_sha256(cand_path)
    if cand_body != actual_content:
        out.append(Finding(
            slug, "PLAN_CANDIDATE_BODY_DIVERGED",
            "%s: the approved plan's body (%s) is not the candidate's body (%s) — what "
            "the owner saw and what implementation uses must be the same document"
            % (name, actual_content[:16] + "…", cand_body[:16] + "…")))

    # Hashes recorded inside these files prove only internal consistency: an editor who
    # changes the plan can change them too. Git history is the one witness outside that
    # control, so once an approval is committed its bytes are frozen.
    corpus = folder.parent
    for artifact in (plan_path, cand_path):
        rel = "%s/%s" % (folder.name, artifact.name)
        state, detail = git_immutability(corpus, rel, artifact)
        if state == "MUTATED":
            out.append(Finding(
                slug, "PLAN_MUTATED_AFTER_COMMIT",
                "%s — an approved plan and the candidate it was promoted from are "
                "immutable once committed. Re-binding the recorded hashes does not make "
                "an edit legitimate. To change the plan, cut a new version." % detail))
    return out


def _check_execution_state(slug, folder, fm, facts):
    """`building`/`verified` are OBSERVATIONS. Intake may not author them.

    Shape is checked here (corpus-wide, no repos needed). The evidence itself is
    proved by `resume`, where the target repositories are actually present — and if
    the repo contradicts the label, the repository wins.
    """
    out = []
    status = fm_str(fm, "status")
    if status not in EXECUTION_OBSERVED_STATES:
        for field in ("execution_repo", "execution_commit", "execution_slice",
                      "verification_evidence"):
            if fm_str(fm, field):
                out.append(Finding(
                    slug, "EXECUTION_EVIDENCE_UNEXPECTED",
                    "brief records %s but status=%s — execution evidence belongs to "
                    "building/verified" % (field, status)))
        return out

    required = ["execution_repo", "execution_commit", "execution_slice"]
    if status == "verified":
        required.append("verification_evidence")
    for field in required:
        if not fm_str(fm, field):
            out.append(Finding(
                slug, "EXECUTION_EVIDENCE_MISSING",
                "status=%s requires %s. A `%s` label is not made true by a valid plan — "
                "Intake may observe implementation state, never author it"
                % (status, field, status)))

    commit = fm_str(fm, "execution_commit")
    if commit and not re.match(r"^[0-9a-fA-F]{7,40}$", commit):
        out.append(Finding(slug, "EXECUTION_EVIDENCE_MALFORMED",
                           "execution_commit=%r is not a commit sha" % commit))
    slice_id = fm_str(fm, "execution_slice")
    if slice_id:
        slices = facts.get("plan_slices") or {}
        if slices and slice_id not in slices:
            out.append(Finding(
                slug, "EXECUTION_EVIDENCE_UNKNOWN_SLICE",
                "execution_slice=%s is not a slice in the approved plan (%s)"
                % (slice_id, ", ".join(sorted(slices)) or "none")))
    return out


def _check_chain(corpus, slug, current_ref):
    out = []
    folder = Path(corpus) / slug
    seen = {current_ref}
    ref = current_ref
    while True:
        pfm, _, _ = read_frontmatter(folder / ref)
        prev = fm_str(pfm, "supersedes_plan")
        if not prev:
            return out
        if not is_bare_filename(prev):
            return out
        if prev in seen:
            out.append(Finding(slug, "PLAN_SUPERSESSION_BROKEN",
                               "supersession cycle at %s" % prev))
            return out
        seen.add(prev)
        prev_path = folder / prev
        if not prev_path.exists():
            out.append(Finding(slug, "PLAN_SUPERSESSION_BROKEN",
                               "%s supersedes %s, which does not exist — owner-approved "
                               "history must never be dropped" % (ref, prev)))
            return out
        prev_fm, prev_body, prev_errors = read_frontmatter(prev_path)
        for err in prev_errors:
            out.append(Finding(slug, "PLAN_FRONTMATTER_AMBIGUOUS", "%s: %s" % (prev, err)))
        if fm_str(prev_fm, "status") != "superseded":
            out.append(Finding(slug, "PLAN_SUPERSESSION_BROKEN",
                               "%s is superseded by %s but its status is %r, not "
                               "'superseded'" % (prev, ref, prev_fm.get("status"))))
        if fm_str(prev_fm, "superseded_by_plan") != ref:
            out.append(Finding(slug, "PLAN_SUPERSESSION_BROKEN",
                               "%s: superseded_by_plan=%r does not point back to %s"
                               % (prev, prev_fm.get("superseded_by_plan"), ref)))
        out.extend(_check_plan_artifact(slug, prev_path, prev_fm, prev_body,
                                        expect_current=False))
        ref = prev


def _check_orphan_plans(corpus, slug, current_ref, findings):
    folder = Path(corpus) / slug
    if not folder.is_dir():
        return
    on_disk = sorted(p.name for p in folder.iterdir()
                     if plan_version_from_name(p.name, slug) is not None)
    if not on_disk:
        return
    reachable = set()
    ref = current_ref
    while ref and is_bare_filename(ref) and (folder / ref).exists() and ref not in reachable:
        reachable.add(ref)
        pfm, _, _ = read_frontmatter(folder / ref)
        ref = fm_str(pfm, "supersedes_plan")
    for name in on_disk:
        if name not in reachable:
            findings.append(Finding(
                slug, "PLAN_ORPHANED",
                "%s exists but is not reachable from the brief's approved_plan "
                "pointer — bind it or record its supersession" % name))


def iter_slugs(corpus):
    corpus = Path(corpus)
    if not corpus.is_dir():
        sys.exit("FAIL: corpus %s does not exist" % corpus)
    for child in sorted(corpus.iterdir()):
        if child.is_dir() and not child.name.startswith(".") and any(child.glob("idea-*.md")):
            yield child.name


# --------------------------------------------------------------- pointers --

def _marker_attrs(text):
    attrs = {}
    for part in text.split():
        if "=" in part:
            k, _, v = part.partition("=")
            attrs[k.strip()] = v.strip()
    return attrs


def parse_pointer_blocks(text):
    """[(key, start, end, fields)] for every pointer block. Raises on ambiguity."""
    blocks, open_marker = [], None
    for m in MARKER_RE.finditer(text):
        kind, attrs = m.group(1), _marker_attrs(m.group(2) or "")
        key = (attrs.get("workstream"), attrs.get("slug"))
        if kind == "BEGIN":
            if open_marker is not None:
                raise ValueError("a pointer block is opened before the previous one "
                                 "is closed")
            open_marker = (key, m.start())
        else:
            if open_marker is None:
                raise ValueError("a pointer END marker appears with no BEGIN — refusing "
                                 "to guess where the block starts")
            if open_marker[0] != key:
                raise ValueError("pointer block opened for %r closes as %r"
                                 % (open_marker[0], key))
            blocks.append((key, open_marker[1], m.end()))
            open_marker = None
    if open_marker is not None:
        raise ValueError("pointer block is opened but never closed")

    seen = set()
    out = []
    for key, start, end in blocks:
        if key in seen:
            raise ValueError("two pointer blocks share the key %r — which is active is "
                             "not decidable" % (key,))
        seen.add(key)
        fields = {}
        for line in text[start:end].splitlines():
            fm = re.match(r"^\s*(?:[-*]\s*)?([A-Z][A-Z0-9_]+):\s*(.*?)\s*$", line)
            if fm:
                fields[fm.group(1)] = fm.group(2)
        out.append({"key": key, "start": start, "end": end, "fields": fields})
    return out


def select_pointer(blocks, workstream, slug):
    """Pick this session's block. Fail closed rather than guess between workstreams."""
    if not blocks:
        return None, "ABSENT"
    exact = [b for b in blocks if b["key"] == (workstream, slug)]
    if exact:
        return exact[0], "OK"
    by_slug = [b for b in blocks if b["key"][1] == slug]
    if len(by_slug) == 1 and workstream is None:
        return by_slug[0], "OK"
    if len(by_slug) > 1:
        return None, "AMBIGUOUS"
    legacy = [b for b in blocks if b["key"] == (None, None)]
    if legacy and len(legacy) == 1:
        block = legacy[0]
        if block["fields"].get("ACTIVE_INTAKE_SLUG") in (None, slug):
            return block, "LEGACY"
    if len(blocks) > 1:
        return None, "AMBIGUOUS"
    return None, "OTHER_WORKSTREAM"


def render_pointer(workstream, slug, plan_path, plan_sha, targets, execution_pointer):
    marker = " workstream=%s slug=%s" % (workstream, slug)
    lines = [
        POINTER_BEGIN + marker + " -->",
        "## Active approved plan — %s / %s (reload pointer, NOT authority)"
        % (workstream, slug),
        "",
        "ACTIVE_WORKSTREAM: %s" % workstream,
        "ACTIVE_INTAKE_SLUG: %s" % slug,
        "ACTIVE_APPROVED_PLAN_PATH: %s" % plan_path,
        "ACTIVE_APPROVED_PLAN_SHA256: %s" % plan_sha,
    ]
    for repo, role in targets:
        lines.append("TARGET_REPO: %s=%s" % (repo, role))
    if not targets:
        lines.append("TARGET_REPO: unknown")
    lines += [
        "CURRENT_EXECUTION_POINTER: %s" % execution_pointer,
        "",
        "Reload rule (applies after `/compact`, automatic compaction, and in every fresh",
        "session): re-read the approved plan from ACTIVE_APPROVED_PLAN_PATH and verify its",
        "sha256 before deriving, planning or continuing any future work. Never reconstruct",
        "a missing approved plan from conversational memory or from a draft; if the file or",
        "its recorded identity cannot be proven, STOP with PLAN_IDENTITY_UNAVAILABLE.",
        "",
        "This block belongs to ONE workstream. Several may coexist in this file — resolve",
        "yours by workstream+slug before using any of them. A repository-wide \"next task\"",
        "does not exist; only a next slice within a named workstream does.",
        "",
        "These fields are a cache, not state. The approved plan is durable owner intent;",
        "each target repository is truth for its own implementation state. "
        "CURRENT_EXECUTION_POINTER",
        "is a hint that must be recomputed by reconciling the plan against the repositories —",
        "where it conflicts with repository evidence, the repository wins, the hint is",
        "discarded, and the discrepancy is reported.",
        "",
        "Resolve mechanically:",
        "    python3 ~/.claude/skills/nortropic-intake/scripts/plan_contract.py \\",
        "        resume --slug %s --workstream %s --target-repo ." % (slug, workstream),
        POINTER_END + marker + " -->",
    ]
    return "\n".join(lines)


def write_pointer(into, rendered, workstream, slug):
    p = Path(into)
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    blocks = parse_pointer_blocks(text)  # may raise ValueError
    mine = [b for b in blocks if b["key"] == (workstream, slug)]
    if mine:
        b = mine[0]
        new = text[:b["start"]] + rendered + text[b["end"]:]
    else:
        sep = "" if (not text or text.endswith("\n\n")) else ("\n" if text.endswith("\n") else "\n\n")
        new = text + sep + rendered + "\n"
    p.write_text(new, encoding="utf-8")
    return len(blocks) + (0 if mine else 1)


# ------------------------------------------------------------ subcommands --

def cmd_validate(args):
    if args.plan_file:
        return _validate_plan_file(Path(args.plan_file))
    corpus = corpus_root(args.corpus)
    slugs = args.slug or list(iter_slugs(corpus))
    if not slugs:
        print("FAIL: %s contains no idea packages — a mis-pathed corpus must not go "
              "green with zero coverage" % corpus)
        return 1
    all_findings = []
    for slug in slugs:
        findings, facts = validate_slug(corpus, slug)
        all_findings.extend(findings)
        if not fails(findings):
            print("PASS  [%s]  status=%s  plan=%s" % (
                slug, facts.get("status", "?"), facts.get("approved_plan") or "—"))
        for f in findings:
            print(f)
    bad = {f.slug for f in fails(all_findings)}
    print("\n%d/%d idea packages satisfy the approved-plan contract"
          % (len(slugs) - len(bad), len(slugs)))
    if all_findings:
        print("codes: %s" % ", ".join(sorted({f.code for f in all_findings})))
    return 1 if bad else 0


def _validate_plan_file(path):
    if not path.exists():
        print("FAIL  [%s]  PLAN_FILE_MISSING — %s" % (path.name, path))
        return 1
    pfm, pbody, errors = read_frontmatter(path)
    findings = []
    slug = fm_str(pfm, "slug")
    candidate = fm_str(pfm, "type") == "plan-candidate"
    for err in errors:
        findings.append(Finding(path.name, "PLAN_FRONTMATTER_AMBIGUOUS", err))
    if not slug:
        findings.append(Finding(path.name, "PLAN_METADATA_MISSING",
                                "no slug in frontmatter"))
    else:
        findings.extend(_check_plan_artifact(slug, path, pfm, pbody,
                                             expect_current=True, candidate=candidate))
        if not candidate:
            findings.extend(_check_exact_approval(slug, path.parent, path, pfm, pbody))
    for f in findings:
        print(f)
    if fails(findings):
        print("\nartifact NOT ready — fix the findings above")
        return 1
    kind = "plan candidate" if candidate else "approved plan"
    print("PASS  [%s]  %s well-formed  slug=%s  version=%s"
          % (path.name, kind, slug, pfm.get("plan_version")))
    print("file_sha256=%s" % sha256_file(path))
    print("content_sha256=%s   <- content identity (body only); shared with the "
          "promoted plan" % sha256_text(pbody))
    if candidate:
        print("")
        print("Commit the candidate, show the owner `coherence`, then approve the FILE "
              "sha:")
        print("  plan_contract.py approve --slug %s --candidate-sha %s \\"
              % (slug, sha256_file(path)))
        print("      --approved-by \"<owner>\" --approved-at <YYYY-MM-DD> \\")
        print("      --evidence \"<how they approved>\"")
        print("  (--candidate-sha takes the FILE sha above, not the content sha.)")
    return 0


def cmd_coherence(args):
    """The delta an owner reads before approving. Stable IDs, no prose summary."""
    corpus = corpus_root(args.corpus)
    slug = args.slug
    folder = Path(corpus) / slug
    brief_path = folder / ("idea-%s.md" % slug)
    if not brief_path.exists():
        print("FAIL: no brief at %s" % brief_path)
        return 1
    fm, brief_body, _ = read_frontmatter(brief_path)
    ids = parse_ids(brief_body)

    plan_path = Path(args.plan) if args.plan else _default_plan_for_coherence(folder, slug, fm)
    if plan_path is None or not plan_path.exists():
        print("FAIL: no plan candidate or approved plan found for %s" % slug)
        print("Pass --plan <file>, or write %s-plan-candidate.md first." % slug)
        return 1
    pfm, pbody, _ = read_frontmatter(plan_path)
    slices = parse_slices(pbody)
    # Acceptance criteria are "covered" only when a SLICE covers them. Being mentioned
    # somewhere in the prose is not coverage — that is how a dropped requirement hides.
    slice_cited = set()
    for s in slices.values():
        slice_cited.update(s["refs"])
    cited = set(slice_cited) | REF_ALL(pbody)

    clarifications = ctx.parse_clarifications(folder / ("%s-owner-clarifications.md" % slug)) \
        if (folder / ("%s-owner-clarifications.md" % slug)).exists() else []
    clar_ids = {e["id"] for e in clarifications}

    def group(prefix):
        return sorted((i for i in ids if (i.startswith("AC") if prefix == "AC"
                                          else i[0] == prefix and not i.startswith("AC"))),
                      key=lambda x: int(re.sub(r"\D", "", x)))

    decisions, rejections, acs, questions = (group("D"), group("R"), group("AC"), group("Q"))
    covered = lambda group_ids: [i for i in group_ids if i in cited]  # noqa: E731
    dropped = lambda group_ids: [i for i in group_ids if i not in cited]  # noqa: E731
    ac_covered = [i for i in acs if i in slice_cited]
    ac_dropped = [i for i in acs if i not in slice_cited]

    unknown_refs = sorted(r for r in cited
                          if r not in ids and r not in clar_ids and not r.startswith(("S", "SRC-")))
    reopened = [r for r in rejections if r in cited and _reopens(pbody, r)]
    new_decisions = _plan_only_decisions(pbody, slices)
    owner_only = sorted(s for s, v in slices.items() if v["owner_only"])
    dispositions = ctx.open_question_dispositions(fm, ids, clarifications)
    unresolved = [q for q, d in dispositions.items() if d == "BLOCKING"]

    print("PLAN CANDIDATE COHERENCE — %s" % slug)
    print("candidate: %s" % plan_path.name)
    print("file_sha256:    %s" % sha256_file(plan_path))
    print("content_sha256: %s" % sha256_text(pbody))
    print("")
    print("DECISIONS_PRESERVED=%d/%d %s" % (len(covered(decisions)), len(decisions),
                                            _fmt(dropped(decisions), "missing")))
    print("REJECTIONS_PRESERVED=%d/%d %s" % (len(covered(rejections)), len(rejections),
                                             _fmt(dropped(rejections), "missing")))
    print("ACCEPTANCE_CRITERIA_COVERED=%d/%d %s"
          % (len(ac_covered), len(acs), _fmt(ac_dropped, "uncovered by any slice")))
    answered = [q for q, d in dispositions.items() if d == "ANSWERED"]
    deferred = [q for q, d in dispositions.items() if d == "EXPLICITLY_DEFERRED"]
    accepted = [q for q, d in dispositions.items() if d == "OWNER_ACCEPTED_OPEN"]
    # "Resolved" means answered. Deferred and accepted-open are dispositions, not
    # answers, and are reported separately rather than folded into a flattering count.
    print("OPEN_QUESTIONS_RESOLVED=%d/%d %s%s%s"
          % (len(answered), len(questions), _fmt(deferred, "deferred"),
             (" " + _fmt(accepted, "accepted-open")) if accepted else "",
             (" " + _fmt(unresolved, "BLOCKING")) if unresolved else ""))
    print("OUT_OF_SCOPE_PRESERVED=%s" % ("YES" if re.search(
        r"^##\s*2\.", pbody, re.M) else "UNKNOWN"))
    print("")
    print("NEW_PLAN_DECISIONS=%d" % len(new_decisions))
    for d in new_decisions:
        print("    + %s" % d)
    print("SCOPE_EXPANSIONS=%d" % len(unknown_refs))
    for r in unknown_refs:
        print("    ? %s referenced by the plan but unknown to brief/clarifications" % r)
    print("DROPPED_REQUIREMENTS=%d" % len(ac_dropped))
    for a in ac_dropped:
        print("    - %s %s" % (a, ids[a]["text"][:80]))
    print("REOPENED_REJECTIONS=%d" % len(reopened))
    for r in reopened:
        print("    ! %s %s" % (r, ids[r]["text"][:80]))
    print("NEW_OWNER_ONLY_TRANSITIONS=%d %s" % (len(owner_only), _fmt(owner_only, "")))
    print("")
    print("SLICES:")
    for sid in sorted(slices, key=lambda x: int(x[1:])):
        s = slices[sid]
        print("  %-4s %-52s covers %s" % (sid, s["heading"][:52],
                                          ", ".join(s["refs"]) or "—"))
    print("")
    material = bool(ac_dropped or reopened or unknown_refs)
    print("OWNER_REVIEW_REQUIRED=%s" % ("YES — material delta above" if material
                                        else "review the delta, then approve"))
    print("Approve exactly this candidate (FILE sha):")
    print("  plan_contract.py approve --slug %s --candidate-sha %s \\"
          % (slug, sha256_file(plan_path)))
    print("      --approved-by \"<owner>\" --approved-at <YYYY-MM-DD> \\")
    print("      --evidence \"<how they approved>\"%s"
          % ("  --accept-delta" if material else ""))
    return 0


def REF_ALL(text):
    from intake_common import REF_RE
    from intake_common import outside_fences
    return {m.group(0) for m in outside_fences(text, list(REF_RE.finditer(text)))}


def _fmt(items, label):
    return ("(%s: %s)" % (label, ", ".join(items))) if items and label else (
        ("(%s)" % ", ".join(items)) if items else "")


def _reopens(pbody, rid):
    """Does the plan cite a rejected path as something it will now do?"""
    for m in re.finditer(re.escape(rid) + r"\b", pbody):
        window = pbody[max(0, m.start() - 160):m.start() + 160].lower()
        if re.search(r"\b(re-?adopt|reopen|now do|implement|revisit|unblock)\b", window):
            return True
    return False


def _plan_only_decisions(pbody, slices):
    """`## 4. Decisions carried into execution` entries with no brief ID reference."""
    sections = section_map(pbody)
    entry = sections.get(4)
    if not entry:
        return []
    out = []
    for line in entry[1].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not re.match(r"^[-*]\s+", stripped):
            continue
        if re.search(r"\b(D\d+|CLAR-\d+|AC\d+)\b", stripped):
            continue
        out.append(re.sub(r"^[-*]\s+", "", stripped)[:110])
    return out


def _default_plan_for_coherence(folder, slug, fm):
    approved = fm_str(fm, "approved_plan")
    candidates = sorted(p for p in folder.glob("%s-plan-candidate*.md" % slug))
    if candidates:
        return candidates[-1]
    if approved and (folder / approved).exists():
        return folder / approved
    return None


def cmd_approve(args):
    """Promote the exact candidate the owner approved. No rewrite in between."""
    corpus = corpus_root(args.corpus)
    slug = args.slug
    folder = Path(corpus) / slug
    cand_path = Path(args.candidate) if args.candidate else \
        _latest_candidate(folder, slug)
    if cand_path is None or not cand_path.exists():
        print("FAIL: no plan candidate found for %s" % slug)
        return 1

    actual = sha256_file(cand_path)
    if args.candidate_sha.lower() != actual:
        print("APPROVAL_REFUSED")
        print("owner approved sha256: %s" % args.candidate_sha)
        print("candidate on disk:     %s  (%s)" % (actual, cand_path.name))
        print("")
        print("These are different documents. The owner approved bytes that are not the")
        print("bytes on disk — do not promote. Re-show the current candidate and get a")
        print("fresh approval, or restore the candidate the owner actually read.")
        return 2

    # The sha the owner approved is a string this process was handed. Git history is the
    # one witness outside the writing agent's control, so a candidate that is committed
    # (and unmodified) is bytes that demonstrably existed before this approval ran.
    rel = "%s/%s" % (slug, cand_path.name)
    anchor, _ = git_immutability(corpus, rel, cand_path)
    if anchor != "UNCHANGED" and not args.allow_uncommitted_candidate:
        print("APPROVAL_REFUSED — candidate is not anchored in git (%s)" % anchor.lower())
        print("")
        print("Commit the candidate BEFORE the owner reviews it, so the bytes they read")
        print("exist in history and cannot be quietly restated afterwards:")
        print("    git -C %s add %s && git -C %s commit -m 'plan candidate: %s'"
              % (corpus, rel, corpus, slug))
        print("")
        print("Approving an uncommitted candidate is possible with")
        print("--allow-uncommitted-candidate, and is recorded as a weaker approval:")
        print("the receipt then attests only that this process was handed that sha.")
        return 2

    # The coherence delta must be seen, not merely producible. Material deltas require
    # an explicit acknowledgement rather than a report nobody consumed.
    delta = _material_delta(corpus, slug, cand_path)
    if delta and not args.accept_delta:
        print("APPROVAL_REFUSED — the candidate carries a material delta from the brief:")
        for line in delta:
            print("  %s" % line)
        print("")
        print("Show the owner `coherence --slug %s`, then re-run with --accept-delta"
              % slug)
        print("once they have approved the delta itself — not just the plan.")
        return 2

    findings = []
    pfm, pbody, errors = read_frontmatter(cand_path)
    for err in errors:
        findings.append(Finding(slug, "PLAN_FRONTMATTER_AMBIGUOUS", err))
    findings.extend(_check_plan_artifact(slug, cand_path, pfm, pbody,
                                         expect_current=True, candidate=True))
    # The self-approval rule applies at approval time, not only when a later validate
    # happens to run: a model may not sign for the owner.
    if SELF_APPROVAL_RE.search(args.approved_by) \
            or args.approved_by.strip().lower() in SELF_APPROVAL_EXACT:
        findings.append(Finding(slug, "PLAN_NOT_APPROVED",
                                "--approved-by=%r names the agent; this must name the "
                                "owner who approved the plan" % args.approved_by))
    if fails(findings):
        print("APPROVAL_REFUSED — the candidate does not satisfy the plan contract:")
        for f in findings:
            print(f)
        return 1

    version = int(str(pfm.get("plan_version", "1")).strip() or "1")
    plan_name = "%s-approved-plan.md" % slug if version == 1 else \
        "%s-approved-plan-v%d.md" % (slug, version)
    plan_path = folder / plan_name
    if plan_path.exists() and not args.force:
        print("APPROVAL_REFUSED: %s already exists. An approved plan is never silently "
              "rewritten — cut a new version instead." % plan_name)
        return 1

    prev = args.supersedes or _current_approved(folder, slug)
    fmlines = [
        "---",
        'title: "%s"' % (fm_str(pfm, "title") or "%s — approved plan v%d" % (slug, version)),
        "type: approved-plan",
        "status: approved",
        "approval_state: approved",
        "slug: %s" % slug,
        "owner: %s" % fm_str(pfm, "owner"),
        "approved_at: %s" % args.approved_at,
        "approved_by: %s" % args.approved_by,
        'approval_evidence: "%s"' % args.evidence.replace('"', "'"),
        "plan_version: %d" % version,
        "source_brief: %s" % fm_str(pfm, "source_brief"),
        "source_brief_sha256: %s" % fm_str(pfm, "source_brief_sha256"),
        "canonical_execution_repo: %s" % fm_str(pfm, "canonical_execution_repo"),
        "plan_source: %s" % fm_str(pfm, "plan_source"),
        "fidelity: %s" % fm_str(pfm, "fidelity"),
        "authority: owner-approved-execution-intent",
        "plan_content_sha256: %s" % sha256_text(pbody),
        "approved_candidate: %s" % cand_path.name,
        "approved_candidate_sha256: %s" % actual,
    ]
    targets = fm_list(pfm, "execution_targets")
    if targets:
        fmlines.append("execution_targets: [%s]" % ", ".join(targets))
    if prev:
        fmlines.append("supersedes_plan: %s" % prev)
    fmlines.append("---")

    # The body is copied byte for byte. This is the whole point.
    plan_path.write_text("\n".join(fmlines) + "\n" + pbody, encoding="utf-8")

    if prev:
        prev_path = folder / prev
        ptext = prev_path.read_text(encoding="utf-8")
        ptext = re.sub(r"^status: approved$", "status: superseded", ptext, count=1, flags=re.M)
        if "superseded_by_plan:" not in ptext:
            ptext = re.sub(r"^(authority: .*)$", r"\1\nsuperseded_by_plan: " + plan_name,
                           ptext, count=1, flags=re.M)
        prev_path.write_text(ptext, encoding="utf-8")

    print("APPROVED")
    print("PLAN=%s" % plan_path)
    print("PLAN_FILE_SHA256=%s" % sha256_file(plan_path))
    print("PLAN_CONTENT_SHA256=%s" % sha256_text(pbody))
    print("APPROVED_CANDIDATE=%s@sha256:%s" % (cand_path.name, actual))
    print("CANDIDATE_GIT_ANCHOR=%s" % anchor)
    print("PROMOTION=body copied byte-for-byte from the candidate (mechanically checked)")
    print("APPROVAL_ATTESTATION=%s"
          % ("the approved sha was already in git history when this ran; the bytes "
             "predate the approval" if anchor == "UNCHANGED" else
             "WEAK — candidate was not committed; this attests only that this process "
             "was handed that sha"))
    print("")
    print("What this does NOT prove: that a human read these bytes. No tool can. It")
    print("proves the promoted plan is the candidate, and that the candidate existed")
    print("before approval. The human link is the evidence string you recorded.")
    print("")
    print("Next, bind it:")
    print("  in idea-%s.md frontmatter set" % slug)
    print("    approved_plan: %s" % plan_name)
    print("    approved_plan_sha256: %s" % sha256_file(plan_path))
    print("    plan_version: %d" % version)
    print("    plan_approved_at: %s" % args.approved_at)
    print("    status: planned")
    print("  then: plan_contract.py validate --slug %s" % slug)
    return 0


def _material_delta(corpus, slug, plan_path):
    """Dropped acceptance criteria, reopened rejections, unknown references.

    The same computation the coherence report prints — reused so approval cannot
    proceed past a delta the report would have shown.
    """
    folder = Path(corpus) / slug
    brief_path = folder / ("idea-%s.md" % slug)
    if not brief_path.exists():
        return []
    _, brief_body, _ = read_frontmatter(brief_path)
    ids = parse_ids(brief_body)
    _, pbody, _ = read_frontmatter(plan_path)
    slices = parse_slices(pbody)
    slice_cited = set()
    for s in slices.values():
        slice_cited.update(s["refs"])
    cited = set(slice_cited) | REF_ALL(pbody)
    clar_path = folder / ("%s-owner-clarifications.md" % slug)
    clar_ids = {e["id"] for e in ctx.parse_clarifications(clar_path)} \
        if clar_path.exists() else set()

    out = []
    for i in sorted(i for i in ids if i.startswith("AC")):
        if i not in slice_cited:
            out.append("DROPPED_REQUIREMENT %s %s" % (i, ids[i]["text"][:70]))
    for i in sorted(i for i in ids if i.startswith("R") and not i.startswith("AC")):
        if i in cited and _reopens(pbody, i):
            out.append("REOPENED_REJECTION %s %s" % (i, ids[i]["text"][:70]))
    for ref in sorted(cited):
        if ref not in ids and ref not in clar_ids and not ref.startswith(("S", "SRC-")):
            out.append("SCOPE_EXPANSION %s referenced by the plan, unknown to the brief"
                       % ref)
    return out


def _latest_candidate(folder, slug):
    found = sorted(folder.glob("%s-plan-candidate*.md" % slug),
                   key=lambda p: plan_version_from_name(p.name, slug, CANDIDATE_FILE_RE_TMPL) or 0)
    return found[-1] if found else None


def _current_approved(folder, slug):
    live = []
    for p in folder.glob("%s-approved-plan*.md" % slug):
        pfm, _, _ = read_frontmatter(p)
        if fm_str(pfm, "status") == "approved":
            live.append(p.name)
    return sorted(live)[-1] if live else None


def cmd_map(args):
    """Derived on demand, never stored: a stored map is a second truth that can drift.

    Fails closed on ANY finding — `map` is the documented way to pick slices without
    reading the whole plan, so serving an unvalidated (possibly tampered) plan here
    would put slices nobody approved in front of an implementer.
    """
    corpus = corpus_root(args.corpus)
    findings, facts = validate_slug(corpus, args.slug)
    if "plan_path" not in facts or fails(findings):
        print(json.dumps({"error": "PLAN_IDENTITY_UNAVAILABLE",
                          "note": "the plan did not validate; refusing to serve slices "
                                  "from an unproven plan",
                          "findings": [str(f) for f in findings]}, indent=2))
        return 2
    plan_path = Path(facts["plan_path"])
    pfm, pbody, _ = read_frontmatter(plan_path)
    sections = section_map(pbody)
    slices = parse_slices(pbody)
    out = {
        "derived": True,
        "note": "Recomputed from the approved plan on every call. Never stored, so it "
                "cannot drift. The approved plan remains canonical.",
        "slug": args.slug,
        "plan": str(plan_path),
        "plan_file_sha256": facts["plan_sha256"],
        "plan_content_sha256": sha256_text(pbody),
        "plan_version": pfm.get("plan_version"),
        "sections": {str(n): {"heading": v[0], "words": len(v[1].split())}
                     for n, v in sorted(sections.items())},
        "slices": [
            {"id": sid, "heading": s["heading"], "lines": [s["line"], s["end_line"]],
             "refs": s["refs"], "owner_only": s["owner_only"]}
            for sid, s in sorted(slices.items(), key=lambda kv: int(kv[0][1:]))
        ],
        "owner_only_slices": sorted((s for s, v in slices.items() if v["owner_only"]),
                                    key=lambda x: int(x[1:])),
        "execution_targets": [{"repo": r, "role": role}
                              for r, role in parse_execution_targets(pfm)],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_resume(args):
    corpus = corpus_root(args.corpus)
    slug = args.slug
    findings, facts = validate_slug(corpus, slug)
    if fails(findings):
        print("PLAN_IDENTITY_UNAVAILABLE")
        print("SLUG=%s" % slug)
        for f in findings:
            print(f)
        print("\nSTOP. Do not reconstruct the approved plan from conversational memory,")
        print("from a draft, or from the transcript. Recover it from a known source with")
        print("the owner, or move the brief back to status: clarified.")
        return 2

    status = facts.get("status")
    if status in PRE_PLAN_STATES:
        print("PLAN_IDENTITY_UNAVAILABLE")
        print("SLUG=%s" % slug)
        print("INTAKE_STATUS=%s" % status)
        print("No approved plan exists yet — this idea has not passed owner plan approval.")
        print("Next step is Clarify → context coverage → Plan Mode → owner approval.")
        return 2

    pkg = ctx.Package(corpus, slug)
    plan_path = Path(facts["plan_path"]).resolve()
    pfm = facts["plan_fm"]
    _, pbody, _ = read_frontmatter(plan_path)

    # The context package is VALIDATED here, not assumed. Printing identity hashes for
    # artifacts nobody checked would make an unearned YES look earned.
    ctx_findings = []
    ctx.validate_manifest(pkg, ctx_findings, require=True)
    ctx.validate_clarifications(pkg, ctx_findings,
                                brief_ids=set(facts.get("brief_ids") or {}))
    ctx_fails = fails(ctx_findings)
    if ctx_fails:
        print("CONTEXT_PACKAGE_VALID=NO")
        for f in ctx_fails:
            print(f)
        print("")
        print("STOP. The approved plan may be provable, but the context it rests on is")
        print("not. Repair the findings above (or run `context_contract.py coverage")
        print("--slug %s` for the full gate) before deriving any further work." % slug)
        return 2
    print("CONTEXT_PACKAGE_VALID=YES")
    for f in ctx_findings:
        print(f)          # WARN-level, e.g. a legacy package with no manifest yet
    print("ACTIVE_WORKSTREAM=%s" % (args.workstream or "UNSET (pass --workstream)"))
    print("SLUG=%s" % slug)
    print("PACKAGE=%s" % pkg.folder)
    print("")
    print("BRIEF_IDENTITY=%s@sha256:%s" % (pkg.brief.name, sha256_file(pkg.brief)[:16] + "…"))
    for label, path in (("RATIONALE_IDENTITY", pkg.rationale),
                        ("SOURCE_MANIFEST_IDENTITY", pkg.manifest),
                        ("CLARIFICATION_IDENTITY", pkg.clarifications)):
        print("%s=%s" % (label, ("%s@sha256:%s" % (path.name, sha256_file(path)[:16] + "…"))
                         if path.exists() else "ABSENT"))
    print("PLAN_IDENTITY=%s@sha256:%s" % (plan_path, facts["plan_sha256"]))
    print("PLAN_CONTENT_SHA256=%s" % sha256_text(pbody))
    print("PLAN_STATUS=APPROVED")
    print("PLAN_VERSION=%s" % facts.get("plan_version"))
    print("APPROVAL_RECEIPT=%s by %s on %s; candidate %s@sha256:%s"
          % (fm_str(pfm, "approval_state") or "?", fm_str(pfm, "approved_by") or "?",
             fm_str(pfm, "approved_at") or "?", fm_str(pfm, "approved_candidate") or "—",
             (fm_str(pfm, "approved_candidate_sha256") or "")[:16] + "…"))
    print("INTAKE_STATUS=%s" % status)
    print("DESIGN_RATIONALE=on-demand (not preloaded)")
    print("RAW_TRANSCRIPT=on-demand (not preloaded)")
    print("RAW_LOOKUP_AVAILABLE=%s" % ("YES" if pkg.transcript.exists() else "NO"))

    # ---- target repositories -------------------------------------------
    targets = parse_execution_targets(pfm)
    if not targets:
        canonical = fm_str(pfm, "canonical_execution_repo")
        targets = [(canonical, "operator-product")] if canonical and canonical != "unknown" else []
    overrides = {Path(p).name: p for p in (args.target_repo or [])}
    print("")
    print("TARGET_REPOS:")
    observations = []
    if not targets:
        print("  (none declared by the plan)")
    for repo, role in targets:
        path = expand(overrides.get(Path(repo).name, repo))
        ev = git_evidence(path) if path.exists() else None
        observations.append((repo, role, ev))
        print("  - repo=%s role=%s" % (repo, role))
        if ev:
            print("    TARGET_REPO_EVIDENCE=head:%s branch:%s dirty:%s"
                  % (ev["head"][:12], ev["branch"], ev["dirty"]))
        else:
            print("    TARGET_REPO_EVIDENCE=NOT_INSPECTED")
        if role == "advisory-only":
            print("    TARGET_REPO_WRITABLE=NO — %s" % ctx.TARGET_ROLES["advisory-only"])

    # ---- execution-state observation ------------------------------------
    print("")
    print("EXECUTION_STATE_CLAIMED=%s" % status)
    print(_observe_execution(facts, observations, corpus, slug))

    # ---- pointer --------------------------------------------------------
    hint, stale = None, False
    if args.pointer:
        hint, stale = _resolve_pointer(args.pointer, args.workstream, slug,
                                       facts["plan_sha256"], plan_path)
    if stale:
        print("NEXT_EXECUTION_POINTER=UNSET (stale pointer discarded — recompute from "
              "plan vs repo)")
    else:
        print("NEXT_EXECUTION_POINTER=%s"
              % (("%s (HINT — unverified)" % hint) if hint else "UNSET"))
    print("PLAN_CURRENT_REPO_RECONCILIATION=PENDING_AGENT_READ")

    # ---- ordered load plan ----------------------------------------------
    print("")
    print("CONTEXT_LOAD_ORDER (smallest first — do not preload past what you need):")
    print("  1. %s                      the WHAT" % pkg.brief.name)
    if pkg.clarifications.exists():
        print("  2. %s   owner deltas; outrank the brief" % pkg.clarifications.name)
    print("  3. %s     the approved plan (use `map` to pick slices)" % plan_path.name)
    print("  4. current repository state for each target above")
    print("  ON DEMAND: %s (design intent), targeted transcript ranges via the "
          "rationale's retrieval map, manifest sources by SRC id"
          % pkg.rationale.name)
    print("")
    print("Now read the approved plan at PLAN_IDENTITY (or the slices you need via")
    print("`plan_contract.py map --slug %s`), read the current state of every target" % slug)
    print("repository, and recompute PLAN_CURRENT_REPO_RECONCILIATION and")
    print("NEXT_EXECUTION_POINTER from that comparison. Any hint above is a cache: where")
    print("it disagrees with repository evidence, the repository wins — report it.")
    return 0


def _observe_execution(facts, observations, corpus, slug):
    """Repo reality beats the brief's own label. Always."""
    fm, _, _ = read_frontmatter(Path(facts["brief"]))
    status = facts.get("status")
    if status not in EXECUTION_OBSERVED_STATES:
        return "EXECUTION_STATE_OBSERVED=NOT_CLAIMED (nothing to contradict)"
    repo = fm_str(fm, "execution_repo")
    commit = fm_str(fm, "execution_commit")
    match = None
    for declared, role, ev in observations:
        if ev and (Path(declared).name == Path(repo).name or declared == repo):
            match = ev
            break
    if match is None:
        return ("EXECUTION_STATE_OBSERVED=UNVERIFIABLE (target repo %r not inspected)\n"
                "EXECUTION_STATE_PRECEDENCE=repository evidence would win if available; "
                "treat the %s label as unproven" % (repo, status))
    if not commit:
        return "EXECUTION_STATE_OBSERVED=UNVERIFIABLE (no execution_commit recorded)"
    if not git_commit_exists(match["repo"], commit):
        return ("EXECUTION_STATE_CONTRADICTED=YES\n"
                "  brief claims %s at %s@%s, but that commit does not exist in the "
                "repository.\n"
                "  REPOSITORY WINS. Treat this item as unverified and correct the brief."
                % (status, repo, commit[:12]))
    return ("EXECUTION_STATE_OBSERVED=CONFIRMED (%s@%s exists; slice %s)\n"
            "  Confirmed means the commit exists — not that the work is correct. The "
            "repository remains truth for its own state."
            % (repo, commit[:12], fm_str(fm, "execution_slice") or "?"))


def _resolve_pointer(path, workstream, slug, plan_sha, plan_path):
    try:
        text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
        blocks = parse_pointer_blocks(text)
    except (ValueError, OSError) as exc:
        print("POINTER=UNREADABLE (%s: %s)" % (path, exc))
        return None, False
    block, state = select_pointer(blocks, workstream, slug)
    if state == "ABSENT":
        print("POINTER=ABSENT (%s)" % path)
        return None, False
    if state == "AMBIGUOUS":
        keys = ", ".join("%s/%s" % (k or "?", s or "?") for k, s in
                         [b["key"] for b in blocks])
        print("POINTER_AMBIGUOUS=YES (%d blocks: %s)" % (len(blocks), keys))
        print("POINTER_UNUSED=pass --workstream to select yours; a repository-wide "
              "\"next task\" does not exist")
        return None, True
    if state == "OTHER_WORKSTREAM":
        print("POINTER=NONE_FOR_THIS_WORKSTREAM (other workstreams' blocks left alone)")
        return None, False
    fields = block["fields"]
    if state == "LEGACY":
        print("POINTER_FORMAT=LEGACY_UNKEYED (rewrite it with `pointer --workstream …`)")
    drift = []
    if fields.get("ACTIVE_INTAKE_SLUG") not in (None, slug):
        drift.append("slug %r" % fields.get("ACTIVE_INTAKE_SLUG"))
    if fields.get("ACTIVE_APPROVED_PLAN_SHA256", "").lower() != plan_sha:
        drift.append("sha %r" % fields.get("ACTIVE_APPROVED_PLAN_SHA256"))
    if fields.get("ACTIVE_APPROVED_PLAN_PATH") not in (None, str(plan_path)):
        drift.append("path %r" % fields.get("ACTIVE_APPROVED_PLAN_PATH"))
    if workstream and fields.get("ACTIVE_WORKSTREAM") not in (None, workstream):
        drift.append("workstream %r" % fields.get("ACTIVE_WORKSTREAM"))
    if drift:
        print("POINTER_STALE=YES (%s)" % "; ".join(drift))
        print("POINTER_OVERRIDDEN_BY=corpus+repository evidence")
        return None, True
    print("POINTER_STALE=NO")
    return fields.get("CURRENT_EXECUTION_POINTER"), False


def cmd_pointer(args):
    corpus = corpus_root(args.corpus)
    findings, facts = validate_slug(corpus, args.slug)
    if fails(findings) or "plan_path" not in facts:
        print("PLAN_IDENTITY_UNAVAILABLE — refusing to write a pointer to an unproven plan")
        for f in findings:
            print(f)
        return 2
    if not args.workstream:
        print("REFUSED: --workstream is required. Several workstreams may point at the")
        print("same repository, and an unkeyed pointer is how one silently becomes the")
        print("repository's \"next task\".")
        return 2
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", args.workstream):
        print("REFUSED: --workstream=%r must be a single token of letters, digits, "
              "-, _ or . " % args.workstream)
        print("The name goes into the block's HTML marker; whitespace there produces a")
        print("marker no reader can match, so the block would be appended again on every")
        print("run and found by none.")
        return 2

    pfm = facts["plan_fm"]
    targets = parse_execution_targets(pfm)
    if not targets:
        canonical = fm_str(pfm, "canonical_execution_repo")
        targets = [(canonical, "operator-product")] if canonical and canonical != "unknown" else []
    rendered = render_pointer(
        workstream=args.workstream,
        slug=args.slug,
        plan_path=Path(facts["plan_path"]).resolve(),
        plan_sha=facts["plan_sha256"],
        targets=targets,
        execution_pointer=args.execution_pointer or "UNSET (recompute from repo state)",
    )
    if args.print_only:
        print(rendered)
        return 0
    try:
        total = write_pointer(args.into, rendered, args.workstream, args.slug)
    except (ValueError, OSError) as exc:
        print("POINTER_BLOCK_AMBIGUOUS — %s: %s" % (args.into, exc))
        return 2
    print("Pointer block written to %s" % Path(args.into).resolve())
    print("WORKSTREAM=%s SLUG=%s" % (args.workstream, args.slug))
    print("BLOCKS_IN_FILE=%d (other workstreams left untouched)" % total)
    print("PLAN_IDENTITY=%s@sha256:%s" % (Path(facts["plan_path"]).resolve(),
                                          facts["plan_sha256"]))
    return 0


def cmd_hash(args):
    path = Path(args.file)
    if not path.is_file():
        print("FAIL: %s is not a readable file" % path)
        return 1
    print(body_sha256(path) if args.body else sha256_file(path))
    return 0


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", default=argparse.SUPPRESS)

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", default=None)
    sub = ap.add_subparsers(dest="cmd")

    v = sub.add_parser("validate", parents=[common], help="validate the corpus or slugs")
    v.add_argument("--slug", action="append")
    v.add_argument("--plan-file", help="check one plan/candidate artifact in isolation")
    v.set_defaults(func=cmd_validate)

    co = sub.add_parser("coherence", parents=[common],
                        help="brief-vs-plan delta for owner review")
    co.add_argument("--slug", required=True)
    co.add_argument("--plan", help="candidate/plan file (default: newest candidate)")
    co.set_defaults(func=cmd_coherence)

    a = sub.add_parser("approve", parents=[common],
                       help="promote the exact candidate the owner approved")
    a.add_argument("--slug", required=True)
    a.add_argument("--candidate", help="candidate file (default: newest)")
    a.add_argument("--candidate-sha", required=True,
                   help="the FILE sha256 the owner approved (not the content sha)")
    a.add_argument("--accept-delta", action="store_true",
                   help="the owner approved the coherence delta too, not just the plan")
    a.add_argument("--allow-uncommitted-candidate", action="store_true",
                   help="approve a candidate that is not yet in git history; recorded "
                        "as a weaker attestation")
    a.add_argument("--approved-by", required=True)
    a.add_argument("--approved-at", required=True)
    a.add_argument("--evidence", required=True)
    a.add_argument("--supersedes", help="approved plan this replaces")
    a.add_argument("--force", action="store_true")
    a.set_defaults(func=cmd_approve)

    m = sub.add_parser("map", parents=[common], help="derived plan map (JSON)")
    m.add_argument("--slug", required=True)
    m.set_defaults(func=cmd_map)

    r = sub.add_parser("resume", parents=[common], help="fresh-session loader")
    r.add_argument("--slug", required=True)
    r.add_argument("--workstream")
    r.add_argument("--target-repo", action="append", default=[])
    r.add_argument("--pointer", help="a CLAUDE.md carrying reload-pointer blocks")
    r.set_defaults(func=cmd_resume)

    p = sub.add_parser("pointer", parents=[common],
                       help="write/update this workstream's pointer block")
    p.add_argument("--slug", required=True)
    p.add_argument("--workstream")
    p.add_argument("--into")
    p.add_argument("--execution-pointer")
    p.add_argument("--print-only", action="store_true")
    p.set_defaults(func=cmd_pointer)

    h = sub.add_parser("hash", parents=[common], help="sha256 of a file")
    h.add_argument("file")
    h.add_argument("--body", action="store_true",
                   help="hash the content identity (body after frontmatter)")
    h.set_defaults(func=cmd_hash)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    if args.cmd == "pointer" and not args.into and not args.print_only:
        ap.error("pointer: --into or --print-only is required")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
