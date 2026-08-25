#!/usr/bin/env python3
"""Approved-plan contract — the mechanical gate behind `status: planned`.

`planned` is not a word an agent may write; it is a provable state. This script is
the proof. It validates the fourth intake artifact (`<slug>-approved-plan.md`), the
brief's binding to it, and the supersession chain — and it resolves a plan for a
fresh session that has nothing but a slug.

Subcommands
-----------
  validate [--slug S ...]        Validate the corpus (or the named slugs). Exit 1 on FAIL.
  validate --plan-file F         Check one plan artifact alone, before it is bound.
  resume --slug S                Fresh-session loader: prove the plan identity, print
                                 the reload block. Exit 2 on PLAN_IDENTITY_UNAVAILABLE.
  pointer --slug S --into FILE   Write/update the reload-pointer block in a CLAUDE.md.
  hash FILE                      sha256 of a file (the identity the brief records).

Corpus root: --corpus (accepted before or after the subcommand), else
$NORTROPIC_INTAKE_CORPUS, else ~/nortropic/innovation-intake.

What this is NOT
----------------
Not a database, not a task ledger, not execution state. It reads files and compares
hashes. The approved plan is durable owner intent; the target repository is
implementation truth; the pointer block is a cache. On conflict, repository evidence
wins and the discrepancy is reported — never silently resolved.

What it can and cannot prove
----------------------------
It proves IDENTITY and SHAPE: that a plan exists, is owner-approved by its own
metadata, is bound to the brief by hash, is the current version, and that none of the
eleven required sections has been emptied out. It cannot prove that prose is faithful
to what the owner actually approved — no tool can. It fails closed on everything it
can check, and says plainly what it cannot.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_CORPUS = Path.home() / "nortropic" / "innovation-intake"

# Lifecycle states that REQUIRE a durable approved plan.
PLAN_REQUIRED_STATES = {"planned", "building", "verified"}
# States where a plan must NOT yet be bound (a plan implies at least `planned`).
PRE_PLAN_STATES = {"idea", "clarified", "ready-for-clarification"}
VALID_BRIEF_STATES = PLAN_REQUIRED_STATES | PRE_PLAN_STATES | {"superseded"}

PLAN_FILE_RE_TMPL = r"^{slug}-approved-plan(?:-v(\d+))?\.md$"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# Required plan frontmatter: field -> allowed values (None = any non-empty value).
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
}

# Required body sections: (number, regex fragment identifying the heading).
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
# Sections that can never honestly be a placeholder: the plan IS these. This detects
# placeholders, not fidelity — no length test can tell a terse honest answer from a
# padded empty one, so the floor is deliberately low and the placeholder list explicit.
SUBSTANTIVE_SECTIONS = {2, 3, 9}
SUBSTANTIVE_MIN_WORDS = 4
PLACEHOLDER_RE = re.compile(
    r"^(none|n/?a|tbd|todo|later|see (the )?(chat|plan|transcript)|-{1,3}|\.)\.?$", re.I)

# `approved_by` must name the owner. An agent approving its own plan is the exact
# failure this artifact exists to prevent, so a self-naming value is refused. Only
# unambiguous self-references count: bare "AI" is a normal part of a company name
# (`Nortropic AI`) and must not block a legitimate approval.
SELF_APPROVAL_RE = re.compile(
    r"\b(claude|chatgpt|gpt-?\d*|llm|copilot|the model|this model|the assistant|"
    r"the agent|an? ai\b|ai agent|myself|itself)\b", re.I)
SELF_APPROVAL_EXACT = {"ai", "bot", "model", "agent", "assistant", "self",
                       "the ai", "the bot", "the model", "the agent"}

POINTER_BEGIN = "<!-- NORTROPIC-ACTIVE-PLAN:BEGIN -->"
POINTER_END = "<!-- NORTROPIC-ACTIVE-PLAN:END -->"


# ---------------------------------------------------------------- parsing --

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)
# YAML starts a comment at ` #` — one space is enough. Matching that exactly is what
# keeps this reader from disagreeing with a YAML-aware one. A value that must contain
# a `#` goes in quotes, where nothing is stripped.
_TRAILING_COMMENT_RE = re.compile(r"\s+#.*$")


def read_frontmatter(path):
    """Flat `key: value` frontmatter reader. Returns (fields, body, errors).

    Deliberately not a YAML parser — intake frontmatter is flat by contract. Anything
    a YAML reader would interpret differently (nested keys, duplicate keys, a value
    that runs onto the next line) is reported as an error rather than guessed at, so
    the gate can never disagree with what a human reading the file sees.
    """
    raw = Path(path).read_text(encoding="utf-8")
    raw = raw.lstrip("﻿")  # a BOM would otherwise defeat the leading `---` match
    m = _FM_RE.match(raw)
    if not m:
        return {}, raw, []
    fm, errors = {}, []
    for offset, line in enumerate(m.group(1).splitlines()):
        lineno = offset + 2
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace():
            errors.append("line %d: indented/nested frontmatter is not allowed — "
                          "intake frontmatter is flat `key: value`: %r"
                          % (lineno, line.strip()))
            continue
        if ":" not in line:
            errors.append("line %d: value ran onto its own line, or not a `key: value` "
                          "line — keep every value on one line: %r"
                          % (lineno, line.strip()))
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        quote = value[0] if value and value[0] in "\"'" else None
        if quote is None:
            value = _TRAILING_COMMENT_RE.sub("", value).strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                value = [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]
        else:
            if len(value) < 2 or value[-1] != quote:
                errors.append("line %d: unterminated quoted value for %r — keep every "
                              "frontmatter value on one line" % (lineno, key))
                continue
            value = value[1:-1]
        if key in fm:
            errors.append("line %d: duplicate key %r — which one is authoritative is "
                          "not decidable" % (lineno, key))
        fm[key] = value
    return fm, raw[m.end():], errors


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def plan_version_from_name(name, slug):
    m = re.match(PLAN_FILE_RE_TMPL.format(slug=re.escape(slug)), name)
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else 1


def is_bare_filename(ref):
    return bool(ref) and "/" not in ref and "\\" not in ref and not ref.startswith(".")


def fence_spans(text):
    """(start, end) spans of fenced code blocks — ``` and ~~~, any info string."""
    spans = []
    open_at, marker = None, None
    for m in re.finditer(r"^[ \t]*(`{3,}|~{3,})[^\n]*$", text, re.M):
        token = m.group(1)[0] * 3
        if open_at is None:
            open_at, marker = m.start(), token
        elif token == marker:
            spans.append((open_at, m.end()))
            open_at, marker = None, None
    if open_at is not None:            # unclosed fence swallows the rest
        spans.append((open_at, len(text)))
    return spans


def section_bodies(body):
    """number -> (heading text, section content) for every `## N. …` heading.

    Headings inside a fenced code block do not count: a plan that quotes the template
    in a ```markdown block has not written those sections, it has pasted them.
    Fenced content INSIDE a real section still counts as that section's content —
    commands and snippets are legitimate plan material.
    """
    spans = fence_spans(body)
    out = {}
    heads = [h for h in re.finditer(r"^##\s*(\d+)\.\s*([^\n]*)$", body, re.M)
             if not any(a <= h.start() < b for a, b in spans)]
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        out[int(h.group(1))] = (h.group(2).strip(), body[h.end():end])
    return out


# ------------------------------------------------------------- validation --

class Finding(object):
    def __init__(self, slug, code, detail):
        self.slug = slug
        self.code = code
        self.detail = detail

    def __str__(self):
        return "FAIL  [%s]  %s — %s" % (self.slug, self.code, self.detail)


def validate_slug(corpus, slug):
    """Validate one idea package. Returns (findings, facts)."""
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

    fm, _, fm_errors = read_frontmatter(brief_path)
    for err in fm_errors:
        findings.append(Finding(slug, "BRIEF_FRONTMATTER_AMBIGUOUS",
                                "idea-%s.md: %s" % (slug, err)))
    status = (fm.get("status") or "").strip()
    facts["status"] = status
    facts["brief"] = str(brief_path)

    if status not in VALID_BRIEF_STATES:
        findings.append(Finding(slug, "BRIEF_STATUS_INVALID",
                                "status=%r is not a lifecycle value" % status))
        return findings, facts

    plan_ref = (fm.get("approved_plan") or "").strip()
    plan_sha = (fm.get("approved_plan_sha256") or "").strip()
    facts["approved_plan"] = plan_ref or None

    # --- the invariant: planned|building|verified <=> a bound, approved plan ---
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

    if not (fm.get("plan_approved_at") or "").strip():
        findings.append(Finding(slug, "PLAN_APPROVAL_METADATA_MISSING",
                                "brief binds a plan but records no plan_approved_at"))

    pfm, pbody, pfm_errors = read_frontmatter(plan_path)
    for err in pfm_errors:
        findings.append(Finding(slug, "PLAN_FRONTMATTER_AMBIGUOUS",
                                "%s: %s" % (plan_ref, err)))
    facts["plan_version"] = pfm.get("plan_version")
    findings.extend(_check_plan_artifact(slug, plan_path, pfm, pbody, expect_current=True))

    # brief plan_version, when present, must agree with the bound plan
    brief_pv = (fm.get("plan_version") or "").strip()
    if brief_pv and str(pfm.get("plan_version", "")).strip() != brief_pv:
        findings.append(Finding(slug, "PLAN_VERSION_MISMATCH",
                                "brief plan_version=%s, plan file says %s"
                                % (brief_pv, pfm.get("plan_version"))))

    findings.extend(_check_chain(corpus, slug, plan_ref))
    _check_orphan_plans(corpus, slug, plan_ref, findings)
    return findings, facts


def _check_plan_artifact(slug, plan_path, pfm, pbody, expect_current):
    """Field + section checks on one plan file."""
    out = []
    name = plan_path.name

    for field, allowed in PLAN_REQUIRED_FIELDS.items():
        value = pfm.get(field)
        value = value.strip() if isinstance(value, str) else value
        if not value:
            code = ("PLAN_APPROVAL_METADATA_MISSING"
                    if field in ("approved_at", "approved_by", "approval_evidence",
                                 "approval_state", "plan_version")
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

    approved_by = str(pfm.get("approved_by", "")).strip()
    if approved_by and (SELF_APPROVAL_RE.search(approved_by)
                        or approved_by.lower() in SELF_APPROVAL_EXACT):
        out.append(Finding(slug, "PLAN_NOT_APPROVED",
                           "%s: approved_by=%r names the agent — this field must name "
                           "the owner who approved the plan" % (name, approved_by)))

    brief_sha = str(pfm.get("source_brief_sha256", "")).strip()
    if brief_sha and not SHA256_RE.match(brief_sha):
        out.append(Finding(slug, "PLAN_METADATA_INVALID",
                           "%s: source_brief_sha256=%r is not a sha256" % (name, brief_sha)))

    if str(pfm.get("slug", "")).strip() != slug:
        out.append(Finding(slug, "PLAN_SLUG_MISMATCH",
                           "%s: slug=%r does not match the idea folder %r"
                           % (name, pfm.get("slug"), slug)))

    expected_brief = "idea-%s.md" % slug
    if str(pfm.get("source_brief", "")).strip() != expected_brief:
        out.append(Finding(slug, "PLAN_SOURCE_BRIEF_MISMATCH",
                           "%s: source_brief=%r, expected %r"
                           % (name, pfm.get("source_brief"), expected_brief)))

    for field in ("supersedes_plan", "superseded_by_plan"):
        ref = str(pfm.get(field, "")).strip()
        if ref and not is_bare_filename(ref):
            out.append(Finding(slug, "PLAN_PATH_INVALID",
                               "%s: %s=%r must be a bare filename in the same idea "
                               "folder" % (name, field, ref)))

    name_version = plan_version_from_name(name, slug)
    if name_version is None:
        out.append(Finding(slug, "PLAN_FILENAME_INVALID",
                           "%s does not match <slug>-approved-plan[-vN].md" % name))
    elif str(pfm.get("plan_version", "")).strip() not in ("", str(name_version)):
        out.append(Finding(slug, "PLAN_VERSION_MISMATCH",
                           "%s: plan_version=%s contradicts the filename (v%d)"
                           % (name, pfm.get("plan_version"), name_version)))

    if expect_current:
        if str(pfm.get("status", "")).strip() == "superseded" or pfm.get("superseded_by_plan"):
            out.append(Finding(slug, "PLAN_SUPERSEDED_POINTER",
                               "%s is superseded (superseded_by_plan=%r) — the brief "
                               "must point at the current version"
                               % (name, pfm.get("superseded_by_plan"))))

    out.extend(_check_plan_sections(slug, name, pbody))
    return out


def _check_plan_sections(slug, name, pbody):
    """Every required section must exist AND carry content.

    A heading with nothing under it is exactly the summarized-away plan this contract
    exists to prevent, and it is indistinguishable from omission to a resuming session.
    """
    out = []
    found = section_bodies(pbody)
    for number, fragment in PLAN_REQUIRED_SECTIONS:
        entry = found.get(number)
        label = fragment.replace(r"\s*", " ")
        if not entry or not re.search(fragment, entry[0], re.I):
            out.append(Finding(slug, "PLAN_SECTION_MISSING",
                               "%s: no '## %d. …%s…' section — the approved plan may "
                               "not summarize this away" % (name, number, label)))
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
    return out


def _check_chain(corpus, slug, current_ref):
    """Walk supersedes_plan backwards: history must stay traceable both ways."""
    out = []
    folder = Path(corpus) / slug
    seen = {current_ref}
    ref = current_ref
    while True:
        pfm, _, _ = read_frontmatter(folder / ref)
        prev = (pfm.get("supersedes_plan") or "").strip()
        if not prev:
            return out
        if not is_bare_filename(prev):
            return out  # already reported as PLAN_PATH_INVALID
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
        if str(prev_fm.get("status", "")).strip() != "superseded":
            out.append(Finding(slug, "PLAN_SUPERSESSION_BROKEN",
                               "%s is superseded by %s but its status is %r, not "
                               "'superseded'" % (prev, ref, prev_fm.get("status"))))
        if str(prev_fm.get("superseded_by_plan", "")).strip() != ref:
            out.append(Finding(slug, "PLAN_SUPERSESSION_BROKEN",
                               "%s: superseded_by_plan=%r does not point back to %s"
                               % (prev, prev_fm.get("superseded_by_plan"), ref)))
        # a historical version stays a readable, owner-approved artifact
        out.extend(_check_plan_artifact(slug, prev_path, prev_fm, prev_body,
                                        expect_current=False))
        ref = prev


def _check_orphan_plans(corpus, slug, current_ref, findings):
    """Every plan file in the folder must be reachable from the brief's pointer."""
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
        ref = (pfm.get("supersedes_plan") or "").strip()
    for name in on_disk:
        if name not in reachable:
            findings.append(Finding(
                slug, "PLAN_ORPHANED",
                "%s exists but is not reachable from the brief's approved_plan "
                "pointer — bind it or record its supersession" % name))


def iter_slugs(corpus):
    """Every directory that holds an intake brief, matching name or not."""
    corpus = Path(corpus)
    if not corpus.is_dir():
        sys.exit("FAIL: corpus %s does not exist" % corpus)
    for child in sorted(corpus.iterdir()):
        if child.is_dir() and not child.name.startswith(".") and \
                any(child.glob("idea-*.md")):
            yield child.name


# ------------------------------------------------------------- pointer io --

def locate_pointer_block(text):
    """(start, end) of the block, (None, None) if absent, or raise ValueError."""
    starts = [m.start() for m in re.finditer(re.escape(POINTER_BEGIN), text)]
    if len(starts) > 1:
        raise ValueError("%d pointer blocks found — which one is active is not "
                         "decidable; remove the extras by hand" % len(starts))
    if not starts:
        if POINTER_END in text:
            raise ValueError("a pointer END marker appears with no BEGIN — refusing to "
                             "guess where the block starts")
        return None, None
    end = text.find(POINTER_END, starts[0])
    if end == -1:
        raise ValueError("pointer block is opened but never closed")
    return starts[0], end + len(POINTER_END)


def read_pointer(path):
    p = Path(path)
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    try:
        start, end = locate_pointer_block(text)
    except ValueError:
        return None
    if start is None:
        return None
    fields = {}
    for line in text[start:end].splitlines():
        m = re.match(r"^\s*(?:[-*]\s*)?([A-Z][A-Z0-9_]+):\s*(.*?)\s*$", line)
        if m:
            fields[m.group(1)] = m.group(2)
    return fields


def render_pointer(workstream, slug, plan_path, plan_sha, target_repo, execution_pointer):
    return "\n".join([
        POINTER_BEGIN,
        "## Active approved plan — reload pointer (NOT authority)",
        "",
        "ACTIVE_WORKSTREAM: %s" % workstream,
        "ACTIVE_INTAKE_SLUG: %s" % slug,
        "ACTIVE_APPROVED_PLAN_PATH: %s" % plan_path,
        "ACTIVE_APPROVED_PLAN_SHA256: %s" % plan_sha,
        "TARGET_REPO: %s" % target_repo,
        "CURRENT_EXECUTION_POINTER: %s" % execution_pointer,
        "",
        "Reload rule (applies after `/compact`, automatic compaction, and in every fresh",
        "session): re-read the approved plan from ACTIVE_APPROVED_PLAN_PATH and verify its",
        "sha256 before deriving, planning or continuing any future work. Never reconstruct",
        "a missing approved plan from conversational memory or from a draft; if the file or",
        "its recorded identity cannot be proven, STOP with PLAN_IDENTITY_UNAVAILABLE.",
        "",
        "These fields are a cache, not state. The approved plan is durable owner intent;",
        "this repository is implementation truth. CURRENT_EXECUTION_POINTER is a hint that",
        "must be recomputed by reconciling the plan against the repository — where it",
        "conflicts with repository evidence, the repository wins, the hint is discarded,",
        "and the discrepancy is reported.",
        "",
        "Resolve mechanically:",
        "    python3 ~/.claude/skills/nortropic-intake/scripts/plan_contract.py \\",
        "        resume --slug %s --target-repo ." % slug,
        POINTER_END,
    ])


def write_pointer(into, rendered):
    p = Path(into)
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    start, end = locate_pointer_block(text)  # may raise ValueError
    if start is not None:
        new = text[:start] + rendered + text[end:]
    else:
        sep = "" if (not text or text.endswith("\n\n")) else ("\n" if text.endswith("\n") else "\n\n")
        new = text + sep + rendered + "\n"
    p.write_text(new, encoding="utf-8")


def git_evidence(repo):
    def run(*args):
        try:
            out = subprocess.run(["git", "-C", str(repo)] + list(args),
                                 capture_output=True, text=True, timeout=15)
        except Exception:
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    head = run("rev-parse", "HEAD")
    if head is None:
        return None
    return {
        "head": head,
        "branch": run("rev-parse", "--abbrev-ref", "HEAD") or "?",
        "dirty": "YES" if run("status", "--porcelain") else "NO",
    }


# ------------------------------------------------------------ subcommands --

def cmd_validate(args):
    if args.plan_file:
        return _validate_plan_file(Path(args.plan_file))
    corpus = Path(args.corpus)
    slugs = args.slug or list(iter_slugs(corpus))
    all_findings = []
    for slug in slugs:
        findings, facts = validate_slug(corpus, slug)
        all_findings.extend(findings)
        if findings:
            for f in findings:
                print(f)
        else:
            plan = facts.get("approved_plan")
            print("PASS  [%s]  status=%s  plan=%s" % (
                slug, facts.get("status", "?"), plan or "—"))
    print("\n%d/%d idea packages satisfy the approved-plan contract"
          % (len(slugs) - len({f.slug for f in all_findings}), len(slugs)))
    if all_findings:
        codes = sorted({f.code for f in all_findings})
        print("codes: %s" % ", ".join(codes))
    return 1 if all_findings else 0


def _validate_plan_file(path):
    """Check one plan artifact in isolation — used BEFORE it is bound to the brief.

    Deliberately does not check the brief binding or the folder's reachability: at this
    point in the flow the plan exists and the brief has not been touched yet. The full
    `validate` run after binding is still the gate on `status: planned`.
    """
    if not path.exists():
        print("FAIL  [%s]  PLAN_FILE_MISSING — %s" % (path.name, path))
        return 1
    pfm, pbody, errors = read_frontmatter(path)
    findings = []
    slug = str(pfm.get("slug", "")).strip()
    for err in errors:
        findings.append(Finding(path.name, "PLAN_FRONTMATTER_AMBIGUOUS", err))
    if not slug:
        findings.append(Finding(path.name, "PLAN_METADATA_MISSING",
                                "no slug in frontmatter"))
    else:
        findings.extend(_check_plan_artifact(slug, path, pfm, pbody, expect_current=True))
    for f in findings:
        print(f)
    if findings:
        print("\nplan artifact NOT ready to bind — fix the findings above")
        return 1
    print("PASS  [%s]  plan artifact well-formed  slug=%s  version=%s"
          % (path.name, slug, pfm.get("plan_version")))
    print("sha256=%s" % sha256_file(path))
    print("Bind it into idea-%s.md (approved_plan, approved_plan_sha256, plan_version,\n"
          "plan_approved_at, status: planned), then run the full `validate`." % slug)
    return 0


def cmd_resume(args):
    corpus = Path(args.corpus)
    slug = args.slug
    findings, facts = validate_slug(corpus, slug)
    if findings:
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
        print("Next step is Clarify → Plan Mode → owner approval, not execution.")
        return 2

    plan_path = Path(facts["plan_path"]).resolve()
    print("PLAN_IDENTITY=%s@sha256:%s" % (plan_path, facts["plan_sha256"]))
    print("PLAN_STATUS=APPROVED")
    print("PLAN_VERSION=%s" % facts.get("plan_version"))
    print("INTAKE_STATUS=%s" % status)
    print("BRIEF=%s" % Path(facts["brief"]).resolve())
    print("DESIGN_RATIONALE=on-demand (not preloaded)")
    print("RAW_TRANSCRIPT=on-demand (not preloaded)")

    pfm, _, _ = read_frontmatter(plan_path)
    declared_repo = str(pfm.get("canonical_execution_repo", "")).strip() or "unknown"
    target = args.target_repo
    if target:
        ev = git_evidence(target)
        print("TARGET_REPO=%s" % Path(target).resolve())
        if ev:
            print("TARGET_REPO_EVIDENCE=head:%s branch:%s dirty:%s"
                  % (ev["head"][:12], ev["branch"], ev["dirty"]))
        else:
            print("TARGET_REPO_EVIDENCE=UNAVAILABLE (not a git repository)")
    else:
        print("TARGET_REPO=%s (declared by the plan; pass --target-repo to prove it)"
              % declared_repo)
        print("TARGET_REPO_EVIDENCE=NOT_REQUESTED")

    hint, stale = None, False
    if args.pointer:
        fields = read_pointer(args.pointer)
        if fields is None:
            print("POINTER=ABSENT_OR_UNREADABLE (%s)" % args.pointer)
        else:
            drift = []
            if fields.get("ACTIVE_INTAKE_SLUG") not in (None, slug):
                drift.append("slug %r" % fields.get("ACTIVE_INTAKE_SLUG"))
            if fields.get("ACTIVE_APPROVED_PLAN_SHA256", "").lower() != facts["plan_sha256"]:
                drift.append("sha %r" % fields.get("ACTIVE_APPROVED_PLAN_SHA256"))
            if fields.get("ACTIVE_APPROVED_PLAN_PATH") not in (None, str(plan_path)):
                drift.append("path %r" % fields.get("ACTIVE_APPROVED_PLAN_PATH"))
            stale = bool(drift)
            if stale:
                print("POINTER_STALE=YES (%s)" % "; ".join(drift))
                print("POINTER_OVERRIDDEN_BY=corpus+repository evidence")
            else:
                print("POINTER_STALE=NO")
                hint = fields.get("CURRENT_EXECUTION_POINTER")

    if stale:
        print("NEXT_EXECUTION_POINTER=UNSET (stale pointer discarded — recompute from "
              "plan vs repo)")
    else:
        print("NEXT_EXECUTION_POINTER=%s"
              % (("%s (HINT — unverified)" % hint) if hint else "UNSET"))
    print("PLAN_CURRENT_REPO_RECONCILIATION=PENDING_AGENT_READ")
    print("")
    print("Now read the approved plan at PLAN_IDENTITY in full, read the current state of")
    print("the target repository, and recompute PLAN_CURRENT_REPO_RECONCILIATION and")
    print("NEXT_EXECUTION_POINTER from that comparison. Any hint above is a cache: where it")
    print("disagrees with repository evidence, the repository wins — report the discrepancy.")
    return 0


def cmd_pointer(args):
    corpus = Path(args.corpus)
    findings, facts = validate_slug(corpus, args.slug)
    if findings or "plan_path" not in facts:
        print("PLAN_IDENTITY_UNAVAILABLE — refusing to write a pointer to an unproven plan")
        for f in findings:
            print(f)
        return 2
    rendered = render_pointer(
        workstream=args.workstream or args.slug,
        slug=args.slug,
        plan_path=Path(facts["plan_path"]).resolve(),
        plan_sha=facts["plan_sha256"],
        target_repo=args.target_repo or "unknown",
        execution_pointer=args.execution_pointer or "UNSET (recompute from repo state)",
    )
    if args.print_only:
        print(rendered)
        return 0
    try:
        write_pointer(args.into, rendered)
    except ValueError as exc:
        print("POINTER_BLOCK_AMBIGUOUS — %s: %s" % (args.into, exc))
        return 2
    print("Pointer block written to %s" % Path(args.into).resolve())
    print("PLAN_IDENTITY=%s@sha256:%s" % (Path(facts["plan_path"]).resolve(),
                                          facts["plan_sha256"]))
    return 0


def cmd_hash(args):
    path = Path(args.file)
    if not path.is_file():
        print("FAIL: %s is not a readable file" % path)
        return 1
    print(sha256_file(path))
    return 0


def main(argv=None):
    corpus_default = os.environ.get("NORTROPIC_INTAKE_CORPUS", str(DEFAULT_CORPUS))
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", default=argparse.SUPPRESS,
                        help="corpus root (may also be given before the subcommand)")

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", default=corpus_default)
    sub = ap.add_subparsers(dest="cmd")

    v = sub.add_parser("validate", parents=[common],
                       help="validate the corpus or named slugs")
    v.add_argument("--slug", action="append")
    v.add_argument("--plan-file", help="check one plan artifact in isolation, before "
                                       "it is bound to the brief")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("resume", parents=[common], help="fresh-session loader")
    r.add_argument("--slug", required=True)
    r.add_argument("--target-repo")
    r.add_argument("--pointer", help="a CLAUDE.md carrying the reload-pointer block")
    r.set_defaults(func=cmd_resume)

    p = sub.add_parser("pointer", parents=[common],
                       help="write/update the reload-pointer block")
    p.add_argument("--slug", required=True)
    p.add_argument("--into", help="file to write the block into (e.g. the target repo's CLAUDE.md)")
    p.add_argument("--workstream")
    p.add_argument("--target-repo")
    p.add_argument("--execution-pointer")
    p.add_argument("--print-only", action="store_true")
    p.set_defaults(func=cmd_pointer)

    h = sub.add_parser("hash", parents=[common], help="sha256 of a file")
    h.add_argument("file")
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
