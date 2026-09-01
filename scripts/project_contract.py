#!/usr/bin/env python3
"""Project contract — PROJECT_SWEEP's coverage ledger and completeness gate.

Third contract, own lifecycle. `context_contract.py` owns one idea's source side and
`plan_contract.py` owns one idea's plan side; this tool owns the PROJECT layer that
sits above both when a whole ChatGPT/Claude project (or an explicit conversation
list) is swept into the corpus:

  _projects/<project>/project-manifest.json   WHICH conversations, in what state
  _projects/<project>/sources/CONV-NNN/       immutable full-chat bytes, per revision
  _projects/<project>/review-queue.md         ambiguities: recorded, queued, never lost
  _projects/<project>/sweep-audit.md          independent falsification, append-only
  _projects/<project>/PROJECT.md              generated human summary (stamped)

Subcommands
-----------
  init --project P --title T        Scaffold a project manifest.
  declare --project P --inventory F Register a conversation inventory (bulk upsert)
                                    and record HOW it was enumerated, honestly.
  register --project P --url U      Upsert one conversation by canonical identity.
  capture --project P --source ID --file F
                                    Record captured bytes as the next immutable
                                    revision; verify the transcript format; fail
                                    closed to CAPTURED+error on a bad capture.
  mark-extracted / mark-routed / mark-failed
                                    Advance (or hard-fail) one source's lifecycle.
  status --project P                Per-source lifecycle + next actions (resume).
  coverage --project P              The completeness gate. Never a score.
  audit --project P                 Validate the independent sweep audit.
  report --project P [--write]      Render PROJECT.md from the manifest.
  validate [--project P ...]        Structural sweep: manifest vs tree, hashes,
                                    identities, idea links, queue, audit, INDEX.
  finalize --project P              End the sweep in an HONEST terminal state.

Corpus root: --corpus, else $NORTROPIC_INTAKE_CORPUS, else ~/nortropic/innovation-intake.

The mode boundary, stated once
------------------------------
PROJECT_SWEEP is corpus ingest, not IMPLEMENT_NOW. Nothing in this tool interviews
the owner, opens Plan Mode, or approves anything — there is no interactive path to
have. Ambiguities are recorded in the review queue and the sweep continues; capture
integrity and source coverage fail closed. Ideas the sweep produces are ordinary
idea packages at `status: idea`, policed by the two existing contracts unchanged.

Source lifecycle (per conversation):

    DISCOVERED → CAPTURED → VERIFIED → EXTRACTED → ROUTED → COMPLETE
                                 ↑ (a new revision re-enters here)
    FAILED (explicit hard failure — a gap that can never read as complete)

What this is NOT
----------------
Not a database, not a scheduler, not the sweep itself. The sweep is performed by an
agent following SKILL.md; this tool is the mechanical record of what was discovered,
captured, verified, extracted and routed — recomputed from plain files on every call,
so "Claude thinks it read everything" is never the evidence. It writes files under
`_projects/` and never commits, never pushes, never touches an idea package.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from intake_common import (  # noqa: E402
    Finding, corpus_root, fails, fm_str, git_head_blob, git_immutability,
    parse_transcript_roles, read_frontmatter, read_json, report, sha256_file,
    sha256_text, transcript_source_sha256, write_json, ROLE_UNKNOWN,
)
import context_contract as ctx  # noqa: E402

PROJECT_MANIFEST_VERSION = 1
PROJECTS_DIR = "_projects"

SOURCE_STATES = ("DISCOVERED", "CAPTURED", "VERIFIED", "EXTRACTED", "ROUTED",
                 "COMPLETE", "FAILED")
ENUM_METHODS = ("none", "declared", "data-layer", "mixed")
# The only endings scripts/project_discovery.js can report. A terminal signal is a
# measurement, so free text in that field is an assertion wearing its clothes.
TERMINAL_SIGNALS = ("cursor-absent", "cursor-absent-empty-page")
PROJECT_END_STATES = ("COMPLETE", "COMPLETE_WITH_OPEN_REVIEW", "INCOMPLETE_HARD_GAPS")

CONV_ID_RE = re.compile(r"^CONV-\d{3,}$")
RQ_ID_RE = re.compile(r"^RQ-\d{3,}$")
# A conversation is identified by host + platform conversation id — never by title.
KEY_RE = re.compile(r"^[a-z0-9.-]+/[A-Za-z0-9_-]{8,}$")
FAIL_STAGES = ("discover", "capture", "verify", "extract", "route")

# What an adversarial sweep audit is allowed to conclude. A finding outside this set
# is commentary, not a falsification attempt.
SWEEP_AUDIT_CODES = (
    "SOURCE_INVENTORY_INCOMPLETE", "DUPLICATE_SOURCE_IDENTITY",
    "SOURCE_MISSING_OR_MUTATED", "MANIFEST_TREE_MISMATCH",
    "IDEA_PROVENANCE_DANGLING", "OWNER_DECISION_BACKED_ONLY_BY_ASSISTANT",
    "EXTERNAL_EVIDENCE_PROMOTED_TO_INSTRUCTION", "SOURCE_EPISODE_MISSING",
    "SILENT_CAPTURE_FAILURE", "DUPLICATE_IDEA_SLUG", "INDEX_STATE_DUPLICATE",
    "ROUTING_RELATION_INCONSISTENT", "FALSE_COMPLETENESS",
    "RERUN_IDEMPOTENCY_VIOLATION",
)
AUDIT_SEVERITIES = ("material", "minor")


def today():
    return datetime.date.today().isoformat()


# ------------------------------------------------------------------- layout --

class Project(object):
    """The file layout of one project. Paths only — no interpretation."""

    def __init__(self, corpus, name):
        self.name = name
        self.corpus = Path(corpus)
        self.folder = self.corpus / PROJECTS_DIR / name
        self.manifest = self.folder / "project-manifest.json"
        self.summary = self.folder / "PROJECT.md"
        self.queue = self.folder / "review-queue.md"
        self.audit = self.folder / "sweep-audit.md"
        self.sources_dir = self.folder / "sources"

    def exists(self):
        return self.manifest.exists()

    def source_dir(self, source_id):
        return self.sources_dir / source_id

    def rel(self, path):
        return str(Path(path).relative_to(self.corpus))


def conversation_key(url_or_key):
    """Canonical `host/<conversation-id>` identity, or None when undecidable.

    Identity comes from the platform's own conversation id — NEVER from a title,
    which is editable, duplicable and routinely reused. An input this function
    cannot resolve to a stable id is refused rather than guessed at.
    """
    raw = (url_or_key or "").strip()
    if not raw:
        return None
    if KEY_RE.match(raw) and "://" not in raw:
        return raw
    m = re.match(r"^(?:https?://)?(?:www\.)?([^/?#]+)([^?#]*)", raw)
    if not m:
        return None
    host, path = m.group(1).lower(), m.group(2) or ""
    for pattern in (r"/c/([0-9a-fA-F-]{20,})",        # chatgpt.com/c/<id>
                    r"/chat/([0-9a-fA-F-]{20,})"):    # claude.ai/chat/<id>
        found = re.search(pattern, path)
        if found:
            return "%s/%s" % (host, found.group(1).lower())
    segment = path.rstrip("/").rsplit("/", 1)[-1]
    if re.match(r"^[A-Za-z0-9_-]{16,}$", segment):
        return "%s/%s" % (host, segment)
    return None


# ---------------------------------------------------------------- manifest --

def load_manifest(proj, findings):
    if not proj.manifest.exists():
        findings.append(Finding(proj.name, "PROJECT_MANIFEST_MISSING",
                                "no %s — run `init` first" % proj.manifest))
        return None
    data, err = read_json(proj.manifest)
    if data is None or not isinstance(data, dict):
        findings.append(Finding(proj.name, "PROJECT_MANIFEST_UNREADABLE",
                                "%s %s" % (proj.manifest.name, err or "is not an object")))
        return None
    if data.get("project_manifest_version") != PROJECT_MANIFEST_VERSION:
        findings.append(Finding(proj.name, "PROJECT_MANIFEST_VERSION_INVALID",
                                "project_manifest_version=%r, expected %d"
                                % (data.get("project_manifest_version"),
                                   PROJECT_MANIFEST_VERSION)))
    if str(data.get("project", "")).strip() != proj.name:
        findings.append(Finding(proj.name, "PROJECT_NAME_MISMATCH",
                                "manifest project=%r does not match the folder"
                                % data.get("project")))
    return data


def source_by_id(data, source_id):
    for s in data.get("sources") or []:
        if isinstance(s, dict) and s.get("source_id") == source_id:
            return s
    return None


def latest_revision(source):
    revisions = source.get("revisions") or []
    return revisions[-1] if revisions else None


def effective_state(source):
    """The state the RECORD supports — recomputed, never trusted from the label.

    `COMPLETE` is the one state `finalize` may store beyond what this derives
    (ROUTED at the latest revision + the project-level audit condition), so ROUTED
    here is compatible with a stored COMPLETE; anything else contradicting the
    stored label is the false-completeness the validator exists to catch.
    """
    if source.get("state") == "FAILED":
        return "FAILED"
    revisions = source.get("revisions") or []
    if not revisions:
        return "DISCOVERED"
    latest = revisions[-1]
    if latest.get("verified") is not True:
        return "CAPTURED"
    n = len(revisions)
    if source.get("extracted_revision") != n:
        return "VERIFIED"
    if source.get("routed_revision") != n:
        return "EXTRACTED"
    return "ROUTED"


def inventory_identity(data):
    """Deterministic identity of the project's source inventory.

    One line per source (canonical key + every captured revision hash) plus one line
    for how the inventory was enumerated. Volatile processing state (extraction,
    routing, errors) is deliberately excluded: the identity answers "which raw
    material does this project rest on", and the sweep audit binds to exactly that.
    """
    lines = []
    for s in data.get("sources") or []:
        if not isinstance(s, dict):
            continue
        key = str(s.get("conversation_key", "")).strip() or "-"
        hashes = ",".join(str(r.get("sha256", "")).strip()
                          for r in (s.get("revisions") or []) if isinstance(r, dict))
        lines.append("SRC %s %s" % (key, hashes or "-"))
    enum = data.get("enumeration") or {}
    lines.append("ENUM %s %s %s"
                 % (str(enum.get("method", "none")),
                    "verified" if enum.get("verified") is True else "unverified",
                    str(enum.get("declared_inventory_sha256", "")).strip() or "-"))
    lines.sort()
    return sha256_text("\n".join(lines) + "\n"), lines


def bump_inventory(proj, data, at, note):
    """Seal the inventory identity when — and only when — the material moved."""
    identity, _ = inventory_identity(data)
    if identity == str(data.get("inventory_sha256", "")).strip():
        return False
    data["inventory_revision"] = int(data.get("inventory_revision") or 0) + 1
    data["inventory_sha256"] = identity
    history = data.get("inventory_history") or []
    history.append({"revision": data["inventory_revision"],
                    "inventory_sha256": identity, "at": at, "note": note})
    data["inventory_history"] = history
    return True


def save(proj, data):
    write_json(proj.manifest, data)


# ------------------------------------------------------------ review queue --

RQ_META_KEYS = ("date", "issue", "affects", "recommendation", "evidence",
                "confidence", "owner_judgment_required", "resolves", "question")
_RQ_FIELD_RE = re.compile(
    r"^\s*[-*]\s*(%s|owner_answer)\s*:\s*(.*)$" % "|".join(RQ_META_KEYS))


def parse_review_queue(path):
    """[{id, fields..., owner_answer?}], in file order. `owner_answer` absorbs the
    rest of its block so the owner's exact wording is preserved unreflowed."""
    _, body, _ = read_frontmatter(path)
    entries = []
    heads = list(re.finditer(r"^##\s*(RQ-\d+)\s*$", body, re.M))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        block = body[h.end():end]
        entry = {"id": h.group(1), "raw": block}
        lines = block.splitlines()
        for j, line in enumerate(lines):
            m = _RQ_FIELD_RE.match(line)
            if not m:
                continue
            key, value = m.group(1), m.group(2).strip()
            if key == "owner_answer":
                rest = "\n".join(lines[j + 1:]).strip()
                entry["owner_answer"] = (value + ("\n" + rest if rest else "")).strip()
                break
            entry.setdefault(key, value)
        entries.append(entry)
    return entries


def open_review_items(entries):
    """RQ ids raised and not yet resolved by a LATER entry. Never hidden, never lost.

    An entry that carries `resolves:` AND item-defining fields (`issue`, …) is
    counted as OPEN anyway: closing one ambiguity may not smuggle a new one out of
    the open list — the validator separately refuses the mixed shape.
    """
    resolved = {}
    for position, e in enumerate(entries):
        for rid in re.findall(r"\bRQ-\d+\b", str(e.get("resolves", ""))):
            resolved.setdefault(rid, position)
    out = []
    for position, e in enumerate(entries):
        if str(e.get("resolves", "")).strip() and not _raises_item(e):
            continue                      # a PURE resolution record, not an item
        closes = resolved.get(e["id"])
        if closes is None or closes <= position:
            out.append(e["id"])
    return out


def _raises_item(entry):
    # `affects`/`evidence` are included on purpose: a concern buried solely in an
    # evidence line on a resolution entry is still a concern leaving the open list.
    return any(str(entry.get(field, "")).strip()
               for field in ("issue", "recommendation", "owner_judgment_required",
                             "affects", "evidence"))


def validate_review_queue(proj, data, findings):
    if not proj.queue.exists():
        return []
    fm, _, fm_errors = read_frontmatter(proj.queue)
    for err in fm_errors:
        findings.append(Finding(proj.name, "REVIEW_QUEUE_FRONTMATTER_AMBIGUOUS",
                                "%s: %s" % (proj.queue.name, err)))
    if fm_str(fm, "type") != "review-queue":
        findings.append(Finding(proj.name, "REVIEW_QUEUE_TYPE_INVALID",
                                "%s: type=%r, expected review-queue"
                                % (proj.queue.name, fm_str(fm, "type"))))
    entries = parse_review_queue(proj.queue)
    known_ids = {s.get("source_id") for s in (data or {}).get("sources") or []
                 if isinstance(s, dict)}
    known_slugs = {slug for s in (data or {}).get("sources") or []
                   if isinstance(s, dict) for slug in (s.get("ideas") or [])}
    seen = set()
    for e in entries:
        if not RQ_ID_RE.match(e["id"]):
            findings.append(Finding(proj.name, "REVIEW_QUEUE_ID_INVALID",
                                    "%s must look like RQ-001" % e["id"]))
        if e["id"] in seen:
            findings.append(Finding(proj.name, "REVIEW_QUEUE_ID_DUPLICATE",
                                    "%s appears more than once" % e["id"]))
        seen.add(e["id"])
        resolves = str(e.get("resolves", "")).strip()
        if resolves:
            for rid in re.findall(r"\bRQ-\d+\b", resolves):
                if rid == e["id"]:
                    findings.append(Finding(
                        proj.name, "REVIEW_QUEUE_SELF_RESOLVED",
                        "%s resolves itself — an item is closed by a LATER entry, "
                        "or it was never really open" % e["id"]))
                elif rid not in seen:
                    findings.append(Finding(
                        proj.name, "REVIEW_QUEUE_ORPHANED",
                        "%s resolves %s, which no earlier entry raised" % (e["id"], rid)))
            if _raises_item(e):
                findings.append(Finding(
                    proj.name, "REVIEW_QUEUE_MIXED_ENTRY",
                    "%s both resolves an earlier item and raises a new one (it carries "
                    "issue/recommendation/owner_judgment_required) — closing one "
                    "ambiguity may not smuggle a new one out of the open list. Write "
                    "TWO entries: a pure resolution, and a fresh item with its own id."
                    % e["id"]))
            continue
        for field in ("date", "issue", "affects", "recommendation",
                      "owner_judgment_required"):
            if not str(e.get(field, "")).strip():
                findings.append(Finding(
                    proj.name, "REVIEW_QUEUE_INCOMPLETE",
                    "%s records no %s — a queued ambiguity must say what is unclear, "
                    "what it touches, what the sweep recommends, and whether the "
                    "owner's judgment is actually required" % (e["id"], field)))
        ojr = str(e.get("owner_judgment_required", "")).strip().lower()
        if ojr and ojr not in ("yes", "no"):
            findings.append(Finding(proj.name, "REVIEW_QUEUE_INCOMPLETE",
                                    "%s owner_judgment_required=%r must be yes or no"
                                    % (e["id"], ojr)))
        for ref in re.split(r"[,\s]+", str(e.get("affects", ""))):
            ref = ref.strip()
            if not ref:
                continue
            if CONV_ID_RE.match(ref):
                if ref not in known_ids:
                    findings.append(Finding(
                        proj.name, "REVIEW_QUEUE_ORPHANED",
                        "%s affects %s, which is not a source in this project"
                        % (e["id"], ref)))
            elif not re.match(r"^[a-z0-9][a-z0-9-]*$", ref):
                findings.append(Finding(
                    proj.name, "REVIEW_QUEUE_ORPHANED",
                    "%s affects %r, which is neither a CONV id nor a slug"
                    % (e["id"], ref)))
            elif known_slugs and ref not in known_slugs \
                    and not (proj.corpus / ref / ("idea-%s.md" % ref)).exists():
                findings.append(Finding(
                    proj.name, "REVIEW_QUEUE_ORPHANED",
                    "%s affects %r, which is neither a swept idea nor a corpus package"
                    % (e["id"], ref)))
    _append_only_project(proj, proj.queue, "REVIEW_QUEUE_NOT_APPEND_ONLY", findings,
                         "a queued ambiguity is never edited away; resolve it with a "
                         "later entry that names it")
    return entries


def _append_only_project(proj, path, code, findings, rule):
    """Git is the only witness an editing agent does not control."""
    if not path.exists():
        return
    committed = git_head_blob(proj.corpus, proj.rel(path))
    if committed is None:
        return
    if not path.read_text(encoding="utf-8").startswith(committed):
        findings.append(Finding(proj.name, code,
                                "%s no longer starts with its committed content — %s"
                                % (path.name, rule)))


# ------------------------------------------------------------- sweep audit --

def validate_sweep_audit(proj, data, findings, require=False):
    """The independent falsification pass over the WHOLE sweep.

    Same discipline as the per-idea distillation audit: append-only rounds, findings
    with evidence, no round may close a finding it raised, and dismissal needs the
    owner — here recorded as a review-queue entry carrying the owner's exact words.
    """
    queue_entries = parse_review_queue(proj.queue) if proj.queue.exists() else []
    # An owner answer dismisses ONLY the finding it actually addresses: the cited RQ
    # must carry the owner's words AND those words themselves must name the FIND id.
    # The OWNER_ANSWER value alone is searched — never the agent-authored issue/
    # recommendation lines, where a planted id would let an agent ride a genuine
    # owner answer about something else. Without this, one owner answer becomes a
    # skeleton key that waves away findings the owner never saw.
    owner_answered = {e["id"]: str(e.get("owner_answer", "")).strip()
                      for e in queue_entries
                      if str(e.get("owner_answer", "")).strip()}

    if not proj.audit.exists():
        if require:
            findings.append(Finding(
                proj.name, "SWEEP_AUDIT_MISSING",
                "no %s — a sweep is not finished until a fresh, isolated reviewer has "
                "tried to falsify its coverage and its routing" % proj.audit.name))
        return []
    fm, _, fm_errors = read_frontmatter(proj.audit)
    for err in fm_errors:
        findings.append(Finding(proj.name, "SWEEP_AUDIT_FRONTMATTER_AMBIGUOUS",
                                "%s: %s" % (proj.audit.name, err)))
    if fm_str(fm, "type") != "sweep-audit":
        findings.append(Finding(proj.name, "SWEEP_AUDIT_TYPE_INVALID",
                                "%s: type=%r, expected sweep-audit"
                                % (proj.audit.name, fm_str(fm, "type"))))
    if fm_str(fm, "project") != proj.name:
        findings.append(Finding(proj.name, "SWEEP_AUDIT_PROJECT_MISMATCH",
                                "%s: project=%r does not match the folder"
                                % (proj.audit.name, fm_str(fm, "project"))))

    rounds = ctx.parse_audit_rounds(proj.audit)
    if not rounds:
        findings.append(Finding(proj.name, "SWEEP_AUDIT_INCOMPLETE",
                                "%s contains no `## AUDIT-<revision>` round"
                                % proj.audit.name))
        return []
    numbers = [r["revision"] for r in rounds]
    if numbers != sorted(numbers):
        findings.append(Finding(
            proj.name, "SWEEP_AUDIT_INCOMPLETE",
            "%s: audit rounds are %s — rounds are appended, so their inventory "
            "revisions never decrease" % (proj.audit.name, numbers)))

    known_ids = {s.get("source_id") for s in (data or {}).get("sources") or []
                 if isinstance(s, dict)}
    known_slugs = {slug for s in (data or {}).get("sources") or []
                   if isinstance(s, dict) for slug in (s.get("ideas") or [])}
    entries = [f for r in rounds for f in r["findings"]]
    states = ctx.audit_finding_states(rounds)
    seen = set()
    for r in rounds:
        for field in ("auditor", "audited_at", "scope", "verdict"):
            if not str(r.get(field, "")).strip():
                findings.append(Finding(
                    proj.name, "SWEEP_AUDIT_INCOMPLETE",
                    "AUDIT-%d records no %s — an audit that cannot say who ran it, "
                    "when, over what, and what it concluded is not evidence"
                    % (r["revision"], field)))
        verdict = str(r.get("verdict", "")).strip()
        if verdict and verdict not in ("PASS", "FINDINGS"):
            findings.append(Finding(proj.name, "SWEEP_AUDIT_INCOMPLETE",
                                    "AUDIT-%d: verdict=%r must be PASS or FINDINGS"
                                    % (r["revision"], verdict)))
        if verdict == "PASS" and r["findings"]:
            findings.append(Finding(
                proj.name, "SWEEP_AUDIT_VERDICT_CONTRADICTED",
                "AUDIT-%d: verdict=PASS while it records %d finding(s)"
                % (r["revision"], len(r["findings"]))))
        if verdict == "FINDINGS" and not r["findings"]:
            findings.append(Finding(
                proj.name, "SWEEP_AUDIT_VERDICT_CONTRADICTED",
                "AUDIT-%d: verdict=FINDINGS with no `### FIND-NNN` entries"
                % r["revision"]))
        for key in ("remediated", "dismissed"):
            for fid in re.findall(r"\bFIND-\d+\b", str(r.get(key, ""))):
                if fid not in states:
                    findings.append(Finding(
                        proj.name, "SWEEP_AUDIT_FINDING_ORPHANED",
                        "AUDIT-%d %s: %s was never raised by any round"
                        % (r["revision"], key, fid)))
                elif any(f["id"] == fid for f in r["findings"]):
                    findings.append(Finding(
                        proj.name, "SWEEP_AUDIT_FINDING_SELF_CLOSED",
                        "AUDIT-%d raises %s and closes it in the same round — a "
                        "finding is closed by a LATER round, after the record was "
                        "actually changed. Closing it here would make raising one free."
                        % (r["revision"], fid)))
        dismissed_line = str(r.get("dismissed", ""))
        for fid in re.findall(r"\bFIND-\d+\b", dismissed_line):
            cited_rq = re.findall(r"\bRQ-\d+\b", dismissed_line)
            backed = any(rq in owner_answered
                         and re.search(r"\b%s\b" % re.escape(fid), owner_answered[rq])
                         for rq in cited_rq)
            if not backed:
                findings.append(Finding(
                    proj.name, "SWEEP_AUDIT_DISMISSED_WITHOUT_OWNER",
                    "AUDIT-%d dismisses %s without citing a review-queue entry whose "
                    "OWNER_ANSWER itself names %s — a finding is never waved away by "
                    "the same lineage that ran the sweep, and an owner answer about "
                    "something else dismisses nothing (nor does an agent-authored "
                    "line that plants the id next to a real answer). Record the "
                    "owner's decision on THIS finding, in their own words naming %s, "
                    "and cite that RQ." % (r["revision"], fid, fid, fid)))

    for e in entries:
        if e["id"] in seen:
            findings.append(Finding(proj.name, "SWEEP_AUDIT_FINDING_DUPLICATE",
                                    "%s appears more than once" % e["id"]))
        seen.add(e["id"])
        code = str(e.get("finding", "")).strip()
        if code not in SWEEP_AUDIT_CODES:
            findings.append(Finding(
                proj.name, "SWEEP_AUDIT_CODE_INVALID",
                "%s finding=%r must be one of %s — the audit reports defects in the "
                "sweep's record, not opinions about the ideas"
                % (e["id"], code or None, list(SWEEP_AUDIT_CODES))))
        severity = str(e.get("severity", "")).strip()
        if severity not in AUDIT_SEVERITIES:
            findings.append(Finding(proj.name, "SWEEP_AUDIT_FINDING_INCOMPLETE",
                                    "%s severity=%r must be one of %s"
                                    % (e["id"], severity or None, list(AUDIT_SEVERITIES))))
        evidence = str(e.get("evidence", "")).strip()
        addressed = bool(re.search(r"\b(CONV-\d+|RQ-\d+|SRC-\d+)\b", evidence)
                         or re.search(r"\bmsgs?\.?\s*\d+", evidence, re.I)
                         or any(slug in evidence for slug in known_slugs)
                         or any(str(i) in evidence for i in known_ids))
        if not addressed:
            findings.append(Finding(
                proj.name, "SWEEP_AUDIT_FINDING_UNEVIDENCED",
                "%s: evidence=%r addresses nothing — a finding must name a CONV id, "
                "an RQ id, a swept idea slug, or message numbers, or it is an "
                "assertion" % (e["id"], evidence or None)))

    material_open = sorted(e["id"] for e in entries
                           if str(e.get("severity", "")).strip() == "material"
                           and states.get(e["id"], ["open"])[0] == "open")
    if material_open:
        findings.append(Finding(
            proj.name, "SWEEP_AUDIT_UNREMEDIATED",
            "%s: %s are material and still open — remediate the sweep record and "
            "append a re-audit round that names them, or record the owner's explicit "
            "dismissal. A material finding is never closed by deleting it."
            % (proj.audit.name, ", ".join(material_open))))

    _append_only_project(proj, proj.audit, "SWEEP_AUDIT_NOT_APPEND_ONLY", findings,
                         "an audit finding is never edited or deleted to make a sweep "
                         "look clean; remediate and APPEND a round that closes it by name")
    return rounds


def audited_inventory_revision(proj):
    if not proj.audit.exists():
        return None
    rounds = ctx.parse_audit_rounds(proj.audit)
    return max((r["revision"] for r in rounds), default=None)


# --------------------------------------------------- structural validation --

def _validate_enumeration(proj, data, findings):
    enum = data.get("enumeration")
    if not isinstance(enum, dict):
        findings.append(Finding(proj.name, "ENUMERATION_INVALID",
                                "manifest records no enumeration object — HOW the "
                                "inventory was obtained is part of the claim"))
        return
    method = str(enum.get("method", "")).strip()
    if method not in ENUM_METHODS:
        findings.append(Finding(proj.name, "ENUMERATION_INVALID",
                                "enumeration.method=%r must be one of %s"
                                % (method, list(ENUM_METHODS))))
    if not isinstance(enum.get("verified"), bool):
        findings.append(Finding(proj.name, "ENUMERATION_INVALID",
                                "enumeration.verified must be true or false — never "
                                "implicit"))
    if enum.get("verified") is True and method in ("none", ""):
        findings.append(Finding(
            proj.name, "ENUMERATION_CLAIM_INVALID",
            "enumeration claims verified=true with method=%r — a verification claim "
            "must say what was verified. DO NOT FAKE IT: an unprovable enumeration is "
            "PROJECT_ENUMERATION_UNVERIFIED, never a claimed full coverage."
            % (method or None)))

    # Since v3.1 a verified claim carries its own machine-checked evidence. Projects
    # enumerated before that cannot retroactively grow one, and inventing it would be
    # a forged proof — so a legacy claim stays VALID and is reported as legacy. It is
    # recorded, not promoted: the reader learns the claim rests on the operator's
    # cross-checks and the owner's confirmation, not on a re-checkable record.
    evidence = enum.get("evidence")
    if enum.get("verified") is True and method not in ("none", ""):
        if not isinstance(evidence, dict):
            findings.append(Finding(
                proj.name, "ENUMERATION_EVIDENCE_LEGACY_ABSENT",
                "enumeration.verified=true carries no evidence record — this claim "
                "predates the v3.1 evidence contract and rests on the operator's "
                "cross-checks, not on a re-checkable proof. Valid as history; a NEW "
                "verified declaration requires --evidence.", level="WARN"))
        elif evidence.get("membership_scope") != "path-scoped-project-endpoint":
            findings.append(Finding(
                proj.name, "ENUMERATION_CLAIM_INVALID",
                "enumeration evidence records membership_scope=%r — only an endpoint "
                "carrying the project id in its PATH establishes membership"
                % evidence.get("membership_scope")))
        elif not evidence.get("terminal_signal"):
            findings.append(Finding(
                proj.name, "ENUMERATION_CLAIM_INVALID",
                "enumeration evidence names no terminal_signal — exhaustion must say "
                "what ended the cursor walk"))
        else:
            # The archived record has to still be there, and still be the bytes the
            # claim was checked against.
            rel = str(evidence.get("record") or "").strip()
            target = proj.corpus / rel if rel else None
            if not rel:
                findings.append(Finding(
                    proj.name, "ENUMERATION_EVIDENCE_MISSING",
                    "enumeration evidence records no archived path — a proof nobody "
                    "can re-read is not evidence"))
            elif not target.is_file():
                findings.append(Finding(
                    proj.name, "ENUMERATION_EVIDENCE_MISSING",
                    "enumeration evidence points at %s, which does not exist — the "
                    "record that backs a verified claim must survive with the corpus"
                    % rel))
            elif sha256_file(target) != str(evidence.get("sha256", "")).strip().lower():
                findings.append(Finding(
                    proj.name, "ENUMERATION_EVIDENCE_TAMPERED",
                    "%s no longer hashes to the digest recorded with the claim — the "
                    "proof was edited after it was accepted" % rel))
            else:
                # And the archived bytes are re-checked, not merely counted. Verifying
                # only the digest would make the claim answerable to whatever was
                # archived — the same asymmetry this file refuses for transcripts,
                # where the verdict is recomputed from the content every sweep. The
                # manifest is a file the writing agent controls; the bytes are not.
                _, refusals = check_enumeration_evidence(
                    target,
                    [{"key": s.get("conversation_key"), "url": s.get("url")}
                     for s in (data.get("sources") or []) if isinstance(s, dict)],
                    origin=str(data.get("origin") or ""))
                for r in refusals:
                    findings.append(Finding(
                        proj.name, "ENUMERATION_CLAIM_INVALID",
                        "the archived proof %s does not carry the claim it backs: %s. "
                        "If the project simply GREW since the proof was taken, this is "
                        "not tampering and the remedy is not an edit: re-run discovery "
                        "and declare again with the new record. A proof is about the "
                        "set that existed when it was measured." % (rel, r)))


def _validate_sources(proj, data, findings):
    seen_ids, seen_keys = set(), {}
    recorded_paths = set()
    for i, s in enumerate(data.get("sources") or []):
        where = "sources[%d]" % i
        if not isinstance(s, dict):
            findings.append(Finding(proj.name, "SOURCE_INVALID",
                                    "%s is not an object" % where))
            continue
        sid = str(s.get("source_id", "")).strip()
        if not CONV_ID_RE.match(sid):
            findings.append(Finding(proj.name, "SOURCE_ID_INVALID",
                                    "%s source_id=%r must look like CONV-001"
                                    % (where, sid)))
            continue
        if sid in seen_ids:
            findings.append(Finding(proj.name, "SOURCE_ID_DUPLICATE",
                                    "%s reuses %s" % (where, sid)))
            continue
        seen_ids.add(sid)
        key = str(s.get("conversation_key", "")).strip()
        if not KEY_RE.match(key):
            findings.append(Finding(
                proj.name, "SOURCE_KEY_INVALID",
                "%s conversation_key=%r must be host/<platform-conversation-id> — "
                "identity comes from the platform's id, never from a title"
                % (sid, key)))
        elif key in seen_keys:
            findings.append(Finding(
                proj.name, "DUPLICATE_SOURCE_IDENTITY",
                "%s and %s both claim conversation %s — one conversation is ONE "
                "source; a rerun must upsert, never duplicate" % (seen_keys[key], sid, key)))
        else:
            seen_keys[key] = sid

        state = str(s.get("state", "")).strip()
        if state not in SOURCE_STATES:
            findings.append(Finding(proj.name, "SOURCE_STATE_INVALID",
                                    "%s state=%r must be one of %s"
                                    % (sid, state, list(SOURCE_STATES))))
            continue

        revisions = s.get("revisions") or []
        numbers = []
        for j, r in enumerate(revisions):
            if not isinstance(r, dict):
                findings.append(Finding(proj.name, "SOURCE_REVISION_INVALID",
                                        "%s revisions[%d] is not an object" % (sid, j)))
                continue
            numbers.append(r.get("revision"))
            rel = str(r.get("path", "")).strip()
            if not rel:
                findings.append(Finding(proj.name, "SOURCE_REVISION_INVALID",
                                        "%s revisions[%d] records no path" % (sid, j)))
                continue
            recorded_paths.add(rel)
            target = proj.corpus / rel
            if not target.exists():
                findings.append(Finding(
                    proj.name, "SOURCE_FILE_MISSING",
                    "%s revision %s: %s does not exist — raw source evidence must "
                    "survive; a swept conversation is never deleted after distillation"
                    % (sid, r.get("revision"), rel)))
                continue
            declared = str(r.get("sha256", "")).strip().lower()
            actual = sha256_file(target)
            if not declared:
                findings.append(Finding(proj.name, "SOURCE_REVISION_INVALID",
                                        "%s revision %s records no sha256 (actual %s)"
                                        % (sid, r.get("revision"), actual)))
            elif declared != actual:
                findings.append(Finding(
                    proj.name, "PROJECT_SOURCE_HASH_MISMATCH",
                    "%s revision %s records %s… but %s hashes to %s… — the bytes "
                    "changed after capture, or the manifest is stale"
                    % (sid, r.get("revision"), declared[:16], rel, actual[:16])))
            state_git, _ = git_immutability(proj.corpus, rel, target)
            if state_git == "MUTATED":
                findings.append(Finding(
                    proj.name, "PROJECT_SOURCE_MUTATED",
                    "%s revision %s (%s) no longer matches its committed bytes — a "
                    "captured revision is immutable; an updated conversation is a NEW "
                    "revision, and history is never rewritten"
                    % (sid, r.get("revision"), rel)))
            # The verification VERDICT is recomputed from the bytes on every sweep —
            # never trusted from the stored flag. A hand-flipped `verified: true` on a
            # capture that fails the format checks is exactly how a hard gap would
            # dress up as coverage, and the manifest is a file the writing agent
            # controls; the bytes are not.
            raw = target.read_text(encoding="utf-8")

            # Same rule, same reason, for source identity. `capture` compares against
            # this field to decide whether a rerun is a no-op, so a wrong value there
            # SWALLOWS a genuine revision: the tool reports CAPTURE_UNCHANGED, the new
            # bytes are never written, and nothing downstream can tell. A decision
            # that fail-closed has to answer to the content, not to the manifest.
            declared_src = str(r.get("source_sha256", "")).strip().lower()
            if declared_src:
                actual_src = transcript_source_sha256(raw)
                if declared_src != actual_src:
                    findings.append(Finding(
                        proj.name, "PROJECT_SOURCE_IDENTITY_MISMATCH",
                        "%s revision %s records source_sha256 %s… but the conversation "
                        "in %s hashes to %s… — capture compares reruns against this "
                        "field, so a stale or forged value silently swallows the next "
                        "real revision"
                        % (sid, r.get("revision"), declared_src[:16], rel,
                           actual_src[:16])))

            actual_ok, actual_detail, _ = verify_transcript_format(raw)
            if bool(r.get("verified")) != actual_ok:
                findings.append(Finding(
                    proj.name, "SOURCE_VERIFICATION_INCONSISTENT",
                    "%s revision %s records verified=%r but the bytes at %s %s — the "
                    "verification verdict is derived from the content, and a flag the "
                    "content cannot back is a forged one%s"
                    % (sid, r.get("revision"), r.get("verified"), rel,
                       "pass the format checks" if actual_ok
                       else "FAIL the format checks",
                       "" if actual_ok else (": %s" % actual_detail))))
        if numbers != list(range(1, len(numbers) + 1)):
            findings.append(Finding(
                proj.name, "SOURCE_REVISION_INVALID",
                "%s revisions run %s — they must run 1..N with no gaps or reordering"
                % (sid, numbers)))

        derived = effective_state(s)
        if state == "COMPLETE" and derived != "ROUTED":
            findings.append(Finding(
                proj.name, "FALSE_COMPLETENESS",
                "%s is labelled COMPLETE but its record supports only %s — a label "
                "is not evidence, and a completeness the files cannot back is exactly "
                "what this contract exists to make impossible" % (sid, derived)))
        elif state not in ("COMPLETE", derived):
            findings.append(Finding(
                proj.name, "SOURCE_STATE_INCONSISTENT",
                "%s is labelled %s but its record supports %s — the state is derived "
                "from the files, never asserted past them" % (sid, state, derived)))

        _validate_idea_links(proj, s, sid, findings)

    # Tree ↔ manifest, both directions: every recorded file exists (above), and every
    # file on disk is recorded — an unrecorded capture is a silent one.
    if proj.sources_dir.is_dir():
        for path in sorted(proj.sources_dir.rglob("*")):
            if path.is_file():
                rel = proj.rel(path)
                if rel not in recorded_paths:
                    findings.append(Finding(
                        proj.name, "MANIFEST_TREE_MISMATCH",
                        "%s exists on disk but no manifest revision records it — an "
                        "unrecorded capture reads as coverage nobody can check" % rel))


def _validate_idea_links(proj, s, sid, findings):
    """Idea provenance is a hash link, not a hope.

    A swept idea package must carry this conversation as one of its own episode
    transcripts, byte-identical to a recorded revision. That is what makes
    `1 chat → many ideas` and `many chats → one idea` checkable instead of asserted.
    """
    revision_hashes = {str(r.get("sha256", "")).strip().lower()
                       for r in (s.get("revisions") or []) if isinstance(r, dict)}
    for slug in s.get("ideas") or []:
        folder = proj.corpus / slug
        brief = folder / ("idea-%s.md" % slug)
        if not brief.exists():
            findings.append(Finding(
                proj.name, "IDEA_PROVENANCE_DANGLING",
                "%s claims idea %r, but %s does not exist" % (sid, slug, brief.name)))
            continue
        transcripts = [folder / ("%s-full-chat.md" % slug)] \
            + sorted(folder.glob("%s-full-chat-*.md" % slug))
        linked = any(t.exists() and sha256_file(t) in revision_hashes
                     for t in transcripts)
        if not linked:
            findings.append(Finding(
                proj.name, "IDEA_EPISODE_HASH_UNLINKED",
                "%s claims idea %r, but no episode transcript in %s/ is byte-identical "
                "to any recorded revision of this conversation — provenance is a hash "
                "link, and this one links to nothing" % (sid, slug, slug)))


def _validate_inventory_history(proj, data, findings):
    identity, _ = inventory_identity(data)
    declared = str(data.get("inventory_sha256", "")).strip()
    revision = data.get("inventory_revision")
    if not isinstance(revision, int) or revision < 0:
        findings.append(Finding(proj.name, "INVENTORY_HISTORY_INVALID",
                                "inventory_revision=%r must be an integer ≥ 0" % revision))
        return
    if revision > 0 and declared != identity:
        findings.append(Finding(
            proj.name, "INVENTORY_IDENTITY_STALE",
            "inventory_sha256=%s… but the inventory now hashes to %s… — the source "
            "set changed without a sealed revision"
            % ((declared or "-")[:16], identity[:16])))
    history = data.get("inventory_history") or []
    numbers = [e.get("revision") for e in history if isinstance(e, dict)]
    if revision > 0 and numbers != list(range(1, revision + 1)):
        findings.append(Finding(
            proj.name, "INVENTORY_HISTORY_INVALID",
            "inventory_history runs %s against inventory_revision=%s — revisions run "
            "1..N with no gaps, duplicates or reordering" % (numbers, revision)))
    for e in history:
        if isinstance(e, dict):
            for field in ("inventory_sha256", "at", "note"):
                if not str(e.get(field, "")).strip():
                    findings.append(Finding(
                        proj.name, "INVENTORY_HISTORY_INVALID",
                        "inventory_history revision %s has no %s"
                        % (e.get("revision"), field)))
    # Append-only against git, same witness discipline as every other history here.
    committed = git_head_blob(proj.corpus, proj.rel(proj.manifest))
    if committed is not None:
        try:
            old = json.loads(committed)
        except ValueError:
            old = None
        old_history = old.get("inventory_history") if isinstance(old, dict) else None
        if isinstance(old_history, list):
            if len(history) < len(old_history):
                findings.append(Finding(
                    proj.name, "INVENTORY_HISTORY_TRUNCATED",
                    "inventory_history has %d entries but %d are committed — a "
                    "project's capture history is append-only"
                    % (len(history), len(old_history))))
            else:
                for i, old_entry in enumerate(old_history):
                    if history[i] != old_entry:
                        findings.append(Finding(
                            proj.name, "INVENTORY_HISTORY_REWRITTEN",
                            "inventory_history[%d] differs from its committed version "
                            "— an earlier revision is never edited" % i))
                        break


def _validate_index(proj, data, findings):
    """The corpus INDEX stays coherent under bulk ingestion: one row per idea."""
    index = proj.corpus / "INDEX.md"
    swept = {slug for s in (data or {}).get("sources") or []
             if isinstance(s, dict) for slug in (s.get("ideas") or [])}
    if not index.exists():
        if swept:
            findings.append(Finding(proj.name, "INDEX_ROW_MISSING",
                                    "the corpus has no INDEX.md but the sweep recorded "
                                    "ideas: %s" % ", ".join(sorted(swept)), level="WARN"))
        return
    text = index.read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"^\|?\s*([a-z0-9][a-z0-9-]*)\s*\|", line)
        if not m:
            continue
        slug = m.group(1)
        rows[slug] = rows.get(slug, 0) + 1
    for slug, count in sorted(rows.items()):
        if count > 1:
            findings.append(Finding(
                proj.name, "INDEX_DUPLICATE_ROW",
                "INDEX.md carries %d rows for %r — one row per idea; a duplicate row "
                "means two states for one thing" % (count, slug)))
    for slug in sorted(swept):
        if slug not in rows:
            findings.append(Finding(
                proj.name, "INDEX_ROW_MISSING",
                "swept idea %r has no INDEX.md row — upsert it (one row per idea)"
                % slug, level="WARN"))


def _validate_summary(proj, findings):
    if not proj.summary.exists():
        return
    fm, _, _ = read_frontmatter(proj.summary)
    stamp = fm_str(fm, "manifest_sha256")
    actual = sha256_file(proj.manifest) if proj.manifest.exists() else ""
    if stamp and stamp.lower() != actual:
        findings.append(Finding(
            proj.name, "PROJECT_SUMMARY_STALE",
            "PROJECT.md was rendered from manifest %s… but the manifest is now %s… — "
            "re-run `report --write`; the manifest stays canonical"
            % (stamp[:16], actual[:16]), level="WARN"))


def validate_project(proj):
    findings = []
    data = load_manifest(proj, findings)
    if data is None:
        return findings, None
    _validate_enumeration(proj, data, findings)
    _validate_sources(proj, data, findings)
    _validate_inventory_history(proj, data, findings)
    validate_review_queue(proj, data, findings)
    validate_sweep_audit(proj, data, findings, require=False)
    _validate_index(proj, data, findings)
    _validate_summary(proj, findings)
    stored = str(data.get("project_status", "")).strip()
    if stored:
        derived = derive_project_status(proj, data)
        if stored != derived:
            findings.append(Finding(
                proj.name, "FALSE_COMPLETENESS",
                "manifest claims project_status=%s but the record supports %s — a "
                "sweep's end state is derived from the files, never asserted past them"
                % (stored, derived)))
    return findings, data


# ---------------------------------------------------------------- coverage --

def hard_gap_sources(data):
    out = []
    for s in data.get("sources") or []:
        if isinstance(s, dict) and effective_state(s) in ("DISCOVERED", "CAPTURED",
                                                          "FAILED"):
            out.append(s)
    return out


def unfinished_sources(data):
    out = []
    for s in data.get("sources") or []:
        if isinstance(s, dict) and effective_state(s) in ("VERIFIED", "EXTRACTED"):
            out.append(s)
    return out


def derive_project_status(proj, data):
    if hard_gap_sources(data):
        return "INCOMPLETE_HARD_GAPS"
    queue_entries = parse_review_queue(proj.queue) if proj.queue.exists() else []
    if open_review_items(queue_entries):
        return "COMPLETE_WITH_OPEN_REVIEW"
    return "COMPLETE"


def cmd_coverage(proj, args):
    findings, data = validate_project(proj)
    if data is None:
        for f in findings:
            print(f)
        return 1
    sources = [s for s in data.get("sources") or [] if isinstance(s, dict)]
    hard = hard_gap_sources(data)
    # A verification verdict the bytes cannot back is a hard gap wearing a flag —
    # the findings are the truth here, not the stored state.
    forged = {m.group(1) for f in findings
              if f.code == "SOURCE_VERIFICATION_INCONSISTENT"
              for m in [re.match(r"^(CONV-\d+)", f.detail)] if m}
    for s in sources:
        if s.get("source_id") in forged and s not in hard:
            hard.append(s)
    unfinished = unfinished_sources(data)
    queue_entries = parse_review_queue(proj.queue) if proj.queue.exists() else []
    open_items = open_review_items(queue_entries)
    enum = data.get("enumeration") or {}
    revision = data.get("inventory_revision") or 0
    audited = audited_inventory_revision(proj)
    audit_current = audited == revision and revision > 0 and not any(
        f.code == "SWEEP_AUDIT_UNREMEDIATED" for f in findings)

    by_state = {}
    for s in sources:
        by_state[effective_state(s)] = by_state.get(effective_state(s), 0) + 1

    print("PROJECT_COVERAGE — %s" % proj.name)
    print("INVENTORY_REVISION=%s" % revision)
    print("SOURCES=%d  %s" % (len(sources), "  ".join(
        "%s:%d" % (state, by_state[state]) for state in SOURCE_STATES
        if state in by_state) or "(none)"))
    print("SOURCE_COVERAGE_COMPLETE=%s" % ("YES" if sources and not hard else "NO"))
    for s in hard:
        latest = latest_revision(s)
        print("  HARD_GAP %s %s state=%s%s"
              % (s.get("source_id"), s.get("conversation_key"), effective_state(s),
                 (" — " + str((s.get("errors") or [{}])[-1].get("detail", ""))[:80])
                 if s.get("errors") else
                 ("" if latest else " — never captured")))
    print("PROCESSING_COMPLETE=%s" % ("YES" if sources and not hard and not unfinished
                                      else "NO"))
    for s in unfinished:
        print("  UNFINISHED %s state=%s (latest revision %d, extracted %s, routed %s)"
              % (s.get("source_id"), effective_state(s),
                 len(s.get("revisions") or []), s.get("extracted_revision"),
                 s.get("routed_revision")))
    print("AUDIT_CURRENT=%s (audited inventory revision %s of %s)"
          % ("YES" if audit_current else "NO", audited or "none", revision))
    print("OPEN_REVIEW_ITEMS=%d%s" % (len(open_items),
                                      (" (%s)" % ", ".join(open_items))
                                      if open_items else ""))
    verified = enum.get("verified") is True
    print("PROJECT_ENUMERATION_VERIFIED=%s (method=%s)"
          % ("YES" if verified else "NO", enum.get("method", "none")))
    if not verified:
        print("PROJECT_ENUMERATION_UNVERIFIED — completeness below is against the "
              "DECLARED inventory only; the platform's project may hold conversations "
              "this sweep never saw. Never report it as full project coverage.")
    status = derive_project_status(proj, data)
    if forged and status != "INCOMPLETE_HARD_GAPS":
        status = "INCOMPLETE_HARD_GAPS"
    finalizable = bool(sources) and not unfinished and audit_current \
        and not fails(findings)
    print("PROJECT_STATUS=%s%s" % (status if finalizable else "NOT_FINALIZABLE",
                                   "" if finalizable else
                                   " (would be %s once processing and audit are "
                                   "current)" % status))
    if findings:
        print("")
        for f in findings:
            print(f)
    return 1 if fails(findings) or not finalizable or status != "COMPLETE" else 0


# ------------------------------------------------------------- subcommands --

def cmd_init(proj, args):
    if proj.exists():
        print("REFUSED: %s already exists — a project manifest is never scaffolded "
              "over" % proj.manifest)
        return 2
    proj.folder.mkdir(parents=True, exist_ok=True)
    proj.sources_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "project_manifest_version": PROJECT_MANIFEST_VERSION,
        "project": proj.name,
        "title": args.title or proj.name,
        "platform": args.platform or "chatgpt",
        "origin": args.origin or "",
        "created": args.at or today(),
        "enumeration": {"method": "none", "verified": False,
                        "declared_inventory_sha256": "", "note": ""},
        "project_status": "",
        "inventory_revision": 0,
        "inventory_sha256": "",
        "inventory_history": [],
        "sources": [],
    }
    save(proj, data)
    print("Scaffolded %s" % proj.manifest)
    print("PROJECT=%s  PLATFORM=%s" % (proj.name, data["platform"]))
    print("ENUMERATION=none/unverified — declare an inventory next.")
    print("  # owner-declared list (no proof of exhaustion):")
    print("  project_contract.py declare --project %s --inventory <list.json> \\"
          % proj.name)
    print("      --method declared")
    print("  # or a proved data-layer enumeration — --verified REQUIRES --evidence,")
    print("  # and the proof is bound to the project's origin:")
    print("  project_contract.py declare --project %s \\" % proj.name)
    print("      --inventory <discovery.json> --evidence <discovery.json> \\")
    if not (data.get("origin") or "").strip():
        print("      --origin https://chatgpt.com/g/g-p-…/project \\")
    print("      --method data-layer --verified")
    return 0


def _upsert_source(proj, data, url, title, at, key=None):
    """Upsert by canonical conversation identity. Returns (source, created)."""
    resolved = key or conversation_key(url)
    if not resolved:
        return None, ("cannot derive a stable conversation identity from %r — "
                      "identity comes from the platform's conversation id, never from "
                      "a title. Pass a URL containing the id, or --key host/<id>."
                      % url)
    for s in data.get("sources") or []:
        if isinstance(s, dict) and s.get("conversation_key") == resolved:
            if title and title != s.get("title"):
                s["title"] = title           # titles are informational, ids are identity
            if url and not s.get("url"):
                s["url"] = url
            return s, False
    sid = "CONV-%03d" % (len(data.get("sources") or []) + 1)
    source = {"source_id": sid, "conversation_key": resolved, "url": url or "",
              "title": title or "", "discovered_at": at, "state": "DISCOVERED",
              "revisions": [], "extracted_revision": 0, "routed_revision": 0,
              "ideas": [], "extraction_note": "", "errors": []}
    data.setdefault("sources", []).append(source)
    return source, True


def cmd_register(proj, args):
    findings = []
    data = load_manifest(proj, findings)
    if data is None or fails(findings):
        for f in findings:
            print(f)
        return 1
    at = args.at or today()
    source, created = _upsert_source(proj, data, args.url, args.title, at,
                                     key=args.key)
    if source is None:
        print("REGISTER_REFUSED — %s" % created)
        return 2
    changed = bump_inventory(proj, data, at, "register %s" % source["source_id"])
    save(proj, data)
    print("%s %s" % ("REGISTERED" if created else "ALREADY_KNOWN", source["source_id"]))
    print("CONVERSATION_KEY=%s" % source["conversation_key"])
    print("INVENTORY_REVISION=%s%s" % (data["inventory_revision"],
                                       "" if changed else " (unchanged)"))
    return 0


# A ChatGPT project id is `g-p-<32 hex>` plus a slug derived from the CURRENT title:
# `g-p-6a86d9dc…-improvements`. Renaming the project on the platform rewrites the slug
# and nothing else, so identity lives in the hex — comparing the whole token would make
# a rename look like a different project and refuse the next verified enumeration.
_STABLE_GID_RE = re.compile(r"^(g-p-[0-9a-f]{16,})(?:-.*)?$", re.I)


def stable_project_id(gid):
    m = _STABLE_GID_RE.match(str(gid or "").strip())
    return (m.group(1).lower() if m else str(gid or "").strip().lower())


def project_id_from_origin(origin):
    m = re.search(r"/g/(g-p-[A-Za-z0-9-]+)", str(origin or ""))
    return m.group(1) if m else ""


def check_enumeration_evidence(path, inventory, origin=""):
    """(summary, refusals) — re-check a discovery record; never take its word for it.

    v3.0 made `--verified` an operator assertion with nothing behind it, and the
    proving run showed what that costs: the shipped adapter would have reported
    `complete: true` over 800 conversations belonging to the account rather than the
    project, because the endpoint accepted a `gizmo_id` filter and ignored it. So the
    claim now has to carry its proof, and the proof is re-read here:

      * membership is established by the request PATH, not by a query filter the
        platform may drop, and no item may belong to another project;
      * exhaustion is the cursor's own terminal signal, walked page by page — not
        arithmetic against a `total` this endpoint never sends;
      * the record must be about THIS project — the id in the endpoint has to be the
        one the manifest's own origin names, or a self-consistent record about some
        other project would verify this one;
      * the page ledger must describe a walk that adds up: pages that account for the
        items collected, cursors that chain and are actually PRESENT on every page but
        the last, and a last page that ends;
      * and the evidence must describe THIS inventory, item for item, or it is
        evidence about something else.

    Be exact about what this cannot do. It re-reads a record for internal consistency
    and agreement with the inventory; it cannot prove an HTTP request ever happened.
    A careful forgery that keeps every number consistent will pass, which is why
    references/extraction.md says never to hand-write one: the value of the proof is
    that a machine produced it. What this closes is the realistic failure — a record
    reconstructed, summarized or half-remembered by an agent, which stops agreeing
    with itself almost immediately.
    """
    record, err = read_json(Path(path))
    if err or not isinstance(record, dict):
        return None, ["%s %s" % (path, err or "must be a JSON object")]

    refusals = []
    # `or {}` defends a falsy non-dict and nothing else: `"membership": true` sails
    # through it and crashes on the first .get(). A validator that raises inside a
    # corpus-wide sweep takes every project after it down with it, so every field this
    # function reaches into is type-checked before it is read.
    refusals_types = []
    membership = record.get("membership")
    if not isinstance(membership, dict):
        if membership is not None:
            refusals_types.append("membership=%r is not an object" % (membership,))
        membership = {}
    exhaustion = record.get("exhaustion")
    if not isinstance(exhaustion, dict):
        if exhaustion is not None:
            refusals_types.append("exhaustion=%r is not an object" % (exhaustion,))
        exhaustion = {}
    refusals.extend(refusals_types)

    # A record describes itself; these checks read what it describes. `scope:
    # "path-scoped-project-endpoint"` is a label anyone can type — the endpoint it
    # names is the thing that either carries the project id in its path or does not.
    endpoint = str(record.get("endpoint") or "")
    pid = str(record.get("projectId") or "")
    if not pid:
        refusals.append("the record names no projectId, so nothing can be checked "
                        "against it")
    expected_path = "/backend-api/gizmos/%s/conversations" % pid
    if not pid or endpoint.split("?")[0] != expected_path:
        refusals.append("endpoint=%r is not %r — the label on the scope is not the "
                        "proof; the request path is" % (endpoint, expected_path))
    if re.search(r"[?&]gizmo_id=", endpoint):
        refusals.append("endpoint carries a gizmo_id QUERY filter — this platform "
                        "accepts that filter and then answers with the whole account; "
                        "that is the v3.0 defect, not a verification")

    # …and it has to be a proof about THIS project. Everything above is internal
    # consistency: a record that names someone else's project consistently would sail
    # through it and verify an inventory it never enumerated.
    want_gid = project_id_from_origin(origin)
    if not want_gid:
        refusals.append("this project's manifest records no origin containing a "
                        "/g/g-p-… project id, so the evidence cannot be bound to it. "
                        "Pass --origin <project URL> on this declare (or set it at "
                        "init); an unbindable proof is not one")
    elif pid and stable_project_id(pid) != stable_project_id(want_gid):
        refusals.append("the evidence enumerates project %r but this project's origin "
                        "is %r — a proof about another project proves nothing here"
                        % (pid, want_gid))

    # The cursor ledger has to show a walk that actually happened and actually ended.
    for field in ("collected", "duplicates_dropped"):
        if field in record and not isinstance(record.get(field), int):
            refusals.append("%s=%r is not a whole number — a count that is not a number "
                            "cannot be reconciled with anything"
                            % (field, record.get(field)))
            record = dict(record, **{field: 0})

    pages = exhaustion.get("pages")
    walked = exhaustion.get("pages_walked")
    if isinstance(pages, list) and not all(isinstance(pg, dict) for pg in pages):
        refusals.append("the page ledger contains entries that are not objects — a "
                        "ledger that cannot be read cannot demonstrate a walk")
        pages = []
    if not isinstance(pages, list) or not pages:
        refusals.append("exhaustion records no page ledger — a walk nobody can inspect "
                        "is not a demonstrated walk")
    elif walked != len(pages):
        refusals.append("exhaustion claims %r page(s) but the ledger holds %d — the "
                        "count and the evidence disagree" % (walked, len(pages)))
    elif (pages[-1] or {}).get("cursor_out") is not None:
        refusals.append("the last page still hands out a cursor (%r) — the walk "
                        "stopped, it did not finish"
                        % (pages[-1] or {}).get("cursor_out"))
    else:
        # The ledger's own numbers have to account for the result it claims.
        if (pages[0] or {}).get("cursor_in") is not None:
            refusals.append("the first page was fetched WITH a cursor (%r) — a walk "
                            "that starts mid-stream has not enumerated the beginning"
                            % (pages[0] or {}).get("cursor_in"))
        for a in pages[:-1]:
            if (a or {}).get("cursor_out") is None:
                refusals.append("page %r ends the walk (no cursor) but is not the last "
                                "page — an all-null ledger is what a record written "
                                "from memory looks like, not one a cursor walk produced"
                                % (a or {}).get("page"))
                break
        for a, b in zip(pages, pages[1:]):
            if (a or {}).get("cursor_out") != (b or {}).get("cursor_in"):
                refusals.append("the cursor chain breaks between page %r and %r "
                                "(%r handed out, %r used) — these pages are not one "
                                "walk" % ((a or {}).get("page"), (b or {}).get("page"),
                                          (a or {}).get("cursor_out"),
                                          (b or {}).get("cursor_in")))
                break
        try:
            seen_items = sum(int((pg or {}).get("items") or 0) for pg in pages)
        except (TypeError, ValueError):
            seen_items = None
            refusals.append("a page records a non-numeric item count — a ledger that "
                            "cannot be added up cannot demonstrate anything")
        if seen_items is None:
            pass
        else:
            want = ((record.get("collected") or 0)
                    + (record.get("duplicates_dropped") or 0))
            if seen_items != want:
                refusals.append("the ledger saw %d item(s) across its pages but the "
                                "record claims %d collected + %d duplicate(s) dropped "
                                "— the walk does not account for the result"
                                % (seen_items, record.get("collected") or 0,
                                   record.get("duplicates_dropped") or 0))

    # The adapter's own extra oracle, when it fired, is not allowed to be ignored.
    oracle = str(record.get("count_oracle") or "")
    if oracle.strip().upper().startswith("DISAGREES"):
        refusals.append("the record's own count oracle says %r — a disagreement the "
                        "adapter reported cannot be declared as a verification"
                        % oracle[:120])

    items = record.get("items")
    if not isinstance(items, list):
        refusals.append("the record carries no items list")
    elif record.get("collected") != len(items):
        refusals.append("collected=%r but %d item(s) are listed — a count that does "
                        "not match what it counts proves nothing"
                        % (record.get("collected"), len(items)))

    if membership.get("scope") != "path-scoped-project-endpoint":
        refusals.append("membership.scope=%r — only an endpoint that carries the "
                        "project id in its PATH establishes membership; a query "
                        "filter this platform may silently drop does not"
                        % membership.get("scope"))
    foreign = membership.get("foreign_items")
    if foreign is None:
        foreign = []
    elif not isinstance(foreign, list):
        refusals.append("membership.foreign_items=%r is not a list" % (foreign,))
        foreign = []
    if foreign:
        refusals.append("the listing returned %d conversation(s) belonging to another "
                        "project (%s) — that is not this project's membership"
                        % (len(foreign), ", ".join(map(str, foreign[:3]))))
    if exhaustion.get("proven") is not True:
        refusals.append("exhaustion.proven is not true (%s) — an enumeration that "
                        "cannot demonstrate the cursor ran out is "
                        "PROJECT_ENUMERATION_UNVERIFIED"
                        % (exhaustion.get("reason") or "no reason recorded"))
    if exhaustion.get("terminal_signal") not in TERMINAL_SIGNALS:
        refusals.append("terminal_signal=%r is not one of %s — exhaustion must name a "
                        "signal the adapter can actually emit, not an assertion in "
                        "free text"
                        % (exhaustion.get("terminal_signal"), list(TERMINAL_SIGNALS)))
    if record.get("verifiable") is not True:
        refusals.append("the record does not claim verifiable:true")

    ev_keys, unresolved = set(), 0
    for item in (items if isinstance(items, list) else []):
        key = (conversation_key(str(item.get("key") or item.get("url") or ""))
               if isinstance(item, dict) else None)
        if key is None:
            unresolved += 1          # dropping these would let extras hide in the set
        else:
            ev_keys.add(key)
    if unresolved:
        refusals.append("%d evidence item(s) carry no resolvable conversation "
                        "identity — an unreadable item is not a member" % unresolved)
    if isinstance(items, list) and len(ev_keys) + unresolved != len(items):
        refusals.append("the record lists %d item(s) but only %d distinct "
                        "conversation(s) — the comparison below is a set, so a "
                        "duplicated item would otherwise pad the count"
                        % (len(items), len(ev_keys)))
    inv_keys = set()
    for item in inventory:
        if isinstance(item, dict):
            inv_keys.add(conversation_key(str(item.get("key") or item.get("url") or "")))
    inv_keys.discard(None)
    if ev_keys != inv_keys:
        refusals.append("the evidence enumerates %d conversation(s) but the inventory "
                        "declares %d, differing by %d — a proof about a different set "
                        "proves nothing about this one"
                        % (len(ev_keys), len(inv_keys),
                           len(ev_keys ^ inv_keys)))

    summary = {
        "sha256": sha256_file(Path(path)),
        "source": record.get("source"),
        "endpoint": record.get("endpoint"),
        "membership_scope": membership.get("scope"),
        "membership_established_by": membership.get("established_by"),
        "terminal_signal": exhaustion.get("terminal_signal"),
        "pages_walked": exhaustion.get("pages_walked"),
        "collected": record.get("collected"),
        "duplicates_dropped": record.get("duplicates_dropped"),
        "count_oracle": record.get("count_oracle"),
    }
    return summary, refusals


def cmd_declare(proj, args):
    findings = []
    data = load_manifest(proj, findings)
    if data is None or fails(findings):
        for f in findings:
            print(f)
        return 1
    inventory, err = read_json(Path(args.inventory))
    # A discovery record IS an inventory — its `items` list is the enumeration. The
    # documented v3.1 command passes the same file to --inventory and --evidence, so
    # accept either shape rather than making the only worked example impossible to run.
    if isinstance(inventory, dict) and isinstance(inventory.get("items"), list):
        inventory = inventory["items"]
    if err or not isinstance(inventory, list):
        print("DECLARE_REFUSED — %s %s" % (args.inventory,
                                           err or "must be a JSON list of "
                                           "{url|key,title}, or a discovery record "
                                           "whose `items` is one"))
        return 1
    at = args.at or today()
    created = known = refused = 0
    for i, item in enumerate(inventory):
        if not isinstance(item, dict):
            print("  REFUSED item %d: not an object" % i)
            refused += 1
            continue
        source, was_created = _upsert_source(
            proj, data, str(item.get("url", "")).strip(),
            str(item.get("title", "")).strip(), at,
            key=str(item.get("key", "")).strip() or None)
        if source is None:
            print("  REFUSED item %d: %s" % (i, was_created))
            refused += 1
        elif was_created:
            created += 1
        else:
            known += 1
    method = args.method or "declared"
    verified = bool(args.verified)

    # The project's origin is an OWNER declaration of which project this is; the
    # evidence then proves enumeration WITHIN it. `init` takes it, but a project
    # scaffolded without one had no way back — and `init` refuses to run twice — so the
    # verified path was permanently unreachable. It can be supplied here instead.
    if getattr(args, "origin", None):
        existing = str(data.get("origin") or "").strip()
        # Compare the project IDENTITY, not the URL text. `stable_project_id` exists so
        # a rename — which rewrites the id's trailing slug, and with it the whole URL —
        # is not read as a different project; applying it only inside the evidence
        # check and not here would refuse the rename at the previous gate instead.
        # A URL that carries no project id at all cannot be compared, so it is refused.
        old_gid = stable_project_id(project_id_from_origin(existing))
        new_gid = stable_project_id(project_id_from_origin(args.origin))
        if existing and old_gid and new_gid and old_gid != new_gid:
            print("DECLARE_REFUSED — this project already records origin %r (project "
                  "%s); changing which project a corpus is about is not a declare-time "
                  "edit" % (existing, old_gid))
            return 1
        if existing and (not old_gid or not new_gid) and existing != args.origin:
            print("DECLARE_REFUSED — this project records origin %r and %r carries no "
                  "comparable /g/g-p-… project id, so the two cannot be shown to be "
                  "the same project" % (existing, args.origin))
            return 1
        data["origin"] = args.origin

    evidence = None
    if getattr(args, "evidence", None):
        evidence, refusals = check_enumeration_evidence(
            args.evidence, inventory, origin=str(data.get("origin") or ""))
        if refusals:
            print("ENUMERATION_VERIFICATION_REFUSED — the evidence does not carry the "
                  "proof it is offered for:")
            for r in refusals:
                print("  - %s" % r)
            if verified:
                print("PROJECT_ENUMERATION_UNVERIFIED — nothing was declared. Re-run "
                      "discovery, or declare --method declared WITHOUT --verified.")
                return 1
            evidence = None
    elif verified:
        # The v3.0 hole: a boolean nobody had to earn.
        print("ENUMERATION_VERIFICATION_REFUSED — --verified requires --evidence, a "
              "discovery record showing membership scope and mechanical cursor "
              "exhaustion. An operator's word is not a completion signal; DO NOT FAKE "
              "IT. Declare without --verified to record "
              "PROJECT_ENUMERATION_UNVERIFIED honestly.")
        return 1

    enum = data.get("enumeration") or {}
    enum.update({
        "method": method,
        "verified": verified,
        "declared_inventory_sha256": sha256_file(Path(args.inventory)),
        "note": args.note or enum.get("note", ""),
    })
    # An evidence record belongs to the declaration it was checked against. A later
    # declaration without one must not inherit the old proof and leave the manifest
    # describing an inventory that is no longer there.
    if evidence:
        # Archive the record beside the manifest. A digest of a file that lives at an
        # absolute path on one operator's laptop is not something an auditor can check,
        # and a proof nobody can re-read is the shape of trust this architecture
        # refuses everywhere else — RAW SOURCE SURVIVES applies to the proof too.
        dest = proj.folder / ("enumeration-evidence-r%d.json"
                              % (int(data.get("inventory_revision") or 0) + 1))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(Path(args.evidence).read_bytes())
        evidence["record"] = proj.rel(dest)
        enum["evidence"] = evidence
    else:
        enum.pop("evidence", None)
    data["enumeration"] = enum
    bump_inventory(proj, data, at, "declare inventory (%s, %d item(s))"
                   % (method, len(inventory)))
    save(proj, data)
    print("DECLARED=%d new, %d already known, %d refused" % (created, known, refused))
    print("ENUMERATION_METHOD=%s  VERIFIED=%s" % (method,
                                                  "YES" if verified else "NO"))
    if evidence:
        print("ENUMERATION_EVIDENCE=%s  pages=%s  terminal=%s  collected=%s"
              % (evidence["sha256"][:16], evidence["pages_walked"],
                 evidence["terminal_signal"], evidence["collected"]))
    if not verified:
        print("PROJECT_ENUMERATION_UNVERIFIED — coverage will answer for this declared "
              "inventory only. Claim --verified only with --evidence: a discovery "
              "record whose membership is path-scoped and whose cursor was walked to "
              "its own terminal signal; DO NOT FAKE IT.")
    print("INVENTORY_REVISION=%s" % data["inventory_revision"])
    return 1 if refused else 0


def verify_transcript_format(text):
    """The fail-closed shape checks a captured conversation must pass.

    The same invariants the single-intake capture enforces: parseable message
    headers, contiguous 1..N numbering, non-empty bodies, balanced fences, and a
    provable speaker role on every message (a sweep's own captures always carry
    roles; an unprovable speaker would poison role-aware provenance downstream).
    Returns (ok, detail, message_count).
    """
    headers = list(re.finditer(r"^##\s*(?:Meddelande|Message)\s+(\d+)[^\n]*$",
                               text, re.M))
    if not headers:
        return False, "no '## Meddelande N — <roll>' message headers found", 0
    numbers = [int(h.group(1)) for h in headers]
    if numbers != list(range(1, len(numbers) + 1)):
        return False, ("message numbering not contiguous 1..%d: %s…"
                       % (len(numbers), numbers[:10])), len(numbers)
    roles = parse_transcript_roles(text)
    unknown = sorted(n for n, role in roles.items() if role == ROLE_UNKNOWN)
    if len(roles) != len(numbers) or unknown:
        return False, ("speaker role unprovable for message(s) %s — every captured "
                       "message must carry its role in the header"
                       % (", ".join(str(n) for n in unknown) or "?")), len(numbers)
    for i, h in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        content = re.sub(r"\n---\s*$", "", text[h.end():end].strip()).strip()
        if not content:
            return False, "message %d has an empty body" % numbers[i], len(numbers)
        if sum(1 for line in content.split("\n")
               if line.startswith("```")) % 2:
            return False, ("unbalanced code fence in message %d — a truncated capture "
                           "is exactly what this catches" % numbers[i]), len(numbers)
    return True, "", len(numbers)


def cmd_capture(proj, args):
    findings = []
    data = load_manifest(proj, findings)
    if data is None or fails(findings):
        for f in findings:
            print(f)
        return 1
    source = source_by_id(data, args.source)
    if source is None:
        print("CAPTURE_REFUSED — %s is not a source in this project (register it "
              "first; a capture nobody discovered is a provenance hole)" % args.source)
        return 2
    src_file = Path(args.file)
    if not src_file.is_file():
        print("CAPTURE_REFUSED — %s is not a readable file" % src_file)
        return 2
    text = src_file.read_text(encoding="utf-8")
    digest = sha256_text(text)
    source_digest = transcript_source_sha256(text)
    at = args.at or today()

    # A revision answers to the CONVERSATION, never to the header the builder wrote
    # about it. Compare on source identity, recomputed from the bytes on disk — the
    # recorded field is a cross-check, not the answer.
    #
    # This decision is the one place a wrong value does real damage: if it says
    # "unchanged" it returns 0, writes nothing, and a genuine new revision is gone with
    # no trace anywhere. So it is derived from content for the same reason the
    # verification verdict is, and a stored value that disagrees is reported rather
    # than quietly preferred. Revisions captured before the field existed simply have
    # nothing to cross-check, and reach the same answer without being migrated.
    for r in source.get("revisions") or []:
        prior = proj.corpus / str(r.get("path", "")).strip()
        recorded = str(r.get("source_sha256", "")).strip().lower()
        known = ""
        if prior.is_file():
            known = transcript_source_sha256(prior.read_text(encoding="utf-8"))
            if recorded and recorded != known:
                print("SOURCE_IDENTITY_RECORD_STALE — revision %s records "
                      "source_sha256 %s… but %s holds %s…; using the bytes. Run "
                      "`validate` — the manifest is out of step with the corpus."
                      % (r.get("revision"), recorded[:16], proj.rel(prior), known[:16]))
        if known and known == source_digest:
            if str(r.get("sha256", "")).strip().lower() == digest:
                print("CAPTURE_UNCHANGED — these bytes are already revision %s of %s; a "
                      "rerun never duplicates a source" % (r.get("revision"), args.source))
            else:
                print("CAPTURE_UNCHANGED — revision %s of %s already holds this exact "
                      "conversation; only derived builder/header metadata differs, which "
                      "is not a source change and never mints a revision"
                      % (r.get("revision"), args.source))
            print("SOURCE_SHA256=%s" % source_digest)
            return 0

    n = len(source.get("revisions") or []) + 1
    dest = proj.source_dir(args.source) / (
        "conversation.md" if n == 1 else "conversation-r%d.md" % n)
    if dest.exists():
        print("CAPTURE_REFUSED — %s already exists; a captured revision is never "
              "overwritten" % proj.rel(dest))
        return 2
    ok, detail, message_count = verify_transcript_format(text)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")

    source.setdefault("revisions", []).append({
        "revision": n, "path": proj.rel(dest), "sha256": digest,
        "source_sha256": source_digest,
        "captured_at": at, "message_count": message_count,
        "adapter": args.adapter or "data-layer", "verified": bool(ok),
        "verify_detail": detail,
    })
    if ok:
        source["state"] = "VERIFIED"
    else:
        source["state"] = "CAPTURED"
        source.setdefault("errors", []).append(
            {"at": at, "stage": "verify", "detail": detail})
    bump_inventory(proj, data, at, "capture %s r%d" % (args.source, n))
    save(proj, data)
    print("CAPTURED %s revision %d → %s" % (args.source, n, proj.rel(dest)))
    print("SHA256=%s  MESSAGES=%d  ADAPTER=%s" % (digest, message_count,
                                                  args.adapter or "data-layer"))
    print("SOURCE_SHA256=%s (identity: the conversation, not the built header)"
          % source_digest)
    print("VERIFIED=%s%s" % ("YES" if ok else "NO", "" if ok else " — " + detail))
    if not ok:
        print("STATE=CAPTURED (hard gap until a verified capture lands — this can "
              "never read as complete)")
    print("INVENTORY_REVISION=%s" % data["inventory_revision"])
    return 0 if ok else 1


def cmd_mark(proj, args, kind):
    findings = []
    data = load_manifest(proj, findings)
    if data is None or fails(findings):
        for f in findings:
            print(f)
        return 1
    source = source_by_id(data, args.source)
    if source is None:
        print("REFUSED — %s is not a source in this project" % args.source)
        return 2
    at = args.at or today()
    state = effective_state(source)
    latest = len(source.get("revisions") or [])

    if kind == "failed":
        if args.stage not in FAIL_STAGES:
            print("REFUSED — --stage must be one of %s" % list(FAIL_STAGES))
            return 2
        if not (args.detail or "").strip():
            print("REFUSED — --detail is required: a hard failure without its reason "
                  "is a silent one")
            return 2
        source["state"] = "FAILED"
        source.setdefault("errors", []).append(
            {"at": at, "stage": args.stage, "detail": args.detail})
        save(proj, data)
        print("MARKED_FAILED %s (stage=%s) — this is a HARD gap: the project can no "
              "longer read as complete" % (args.source, args.stage))
        return 0

    if kind == "extracted":
        if state not in ("VERIFIED", "EXTRACTED", "ROUTED"):
            print("REFUSED — %s is %s; extraction is recorded only over a verified "
                  "capture" % (args.source, state))
            return 2
        ideas = [i.strip() for i in (args.ideas or "").split(",") if i.strip()]
        if not ideas and not args.no_ideas:
            print("REFUSED — pass --ideas slug1,slug2 or --no-ideas --note '<why>'")
            return 2
        if args.no_ideas and not (args.note or "").strip():
            print("REFUSED — --no-ideas needs --note: a conversation that produced "
                  "nothing durable must say so explicitly")
            return 2
        probe = []
        for slug in ideas:
            _validate_idea_links(proj, dict(source, ideas=[slug]), args.source, probe)
        if probe:
            print("REFUSED — the idea links do not hold:")
            for f in probe:
                print(f)
            print("Deliver the conversation into each idea package as an episode "
                  "transcript (byte-identical to a recorded revision) BEFORE marking.")
            return 1
        source["ideas"] = ideas
        source["extraction_note"] = args.note or ""
        source["extracted_revision"] = latest
        source["state"] = "EXTRACTED"
        save(proj, data)
        print("MARKED_EXTRACTED %s at revision %d → ideas: %s"
              % (args.source, latest, ", ".join(ideas) or "none (%s)" % args.note))
        return 0

    if kind == "routed":
        if state != "EXTRACTED":
            print("REFUSED — %s is %s; routing is recorded only after extraction at "
                  "the latest revision" % (args.source, state))
            return 2
        source["routed_revision"] = latest
        source["state"] = "ROUTED"
        save(proj, data)
        print("MARKED_ROUTED %s at revision %d" % (args.source, latest))
        return 0
    return 2


def cmd_status(proj, args):
    findings, data = validate_project(proj)
    if data is None:
        for f in findings:
            print(f)
        return 1
    print("PROJECT=%s  INVENTORY_REVISION=%s" % (proj.name,
                                                 data.get("inventory_revision")))
    enum = data.get("enumeration") or {}
    print("ENUMERATION=%s (%s)" % (enum.get("method", "none"),
                                   "verified" if enum.get("verified") is True
                                   else "UNVERIFIED"))
    actions = []
    for s in data.get("sources") or []:
        if not isinstance(s, dict):
            continue
        state = effective_state(s)
        latest = len(s.get("revisions") or [])
        print("  %-9s %-11s r%-2d ex:%-2s rt:%-2s %-30s %s"
              % (s.get("source_id"), state, latest,
                 s.get("extracted_revision"), s.get("routed_revision"),
                 str(s.get("conversation_key", ""))[:30],
                 ", ".join(s.get("ideas") or []) or "—"))
        if state == "DISCOVERED":
            actions.append("capture %s" % s.get("source_id"))
        elif state == "CAPTURED":
            actions.append("re-capture %s (last capture failed verification: %s)"
                           % (s.get("source_id"),
                              (latest_revision(s) or {}).get("verify_detail", "?")))
        elif state == "VERIFIED":
            actions.append("extract %s (revision %d not yet distilled)"
                           % (s.get("source_id"), latest))
        elif state == "EXTRACTED":
            actions.append("route %s" % s.get("source_id"))
        elif state == "FAILED":
            actions.append("FAILED %s — owner-visible hard gap" % s.get("source_id"))
    queue_entries = parse_review_queue(proj.queue) if proj.queue.exists() else []
    open_items = open_review_items(queue_entries)
    revision = data.get("inventory_revision") or 0
    audited = audited_inventory_revision(proj)
    if audited != revision:
        actions.append("run the sweep audit at inventory revision %s (last audited: %s)"
                       % (revision, audited or "never"))
    print("OPEN_REVIEW_ITEMS=%d%s" % (len(open_items),
                                      " (%s)" % ", ".join(open_items)
                                      if open_items else ""))
    print("NEXT_ACTIONS:%s" % ("" if actions else " none — run coverage/finalize"))
    for a in actions:
        print("  - %s" % a)
    for f in findings:
        print(f)
    return 1 if fails(findings) else 0


def cmd_audit_cli(proj, args):
    findings = []
    data = load_manifest(proj, findings)
    rounds = validate_sweep_audit(proj, data, findings, require=True)
    if proj.audit.exists() and rounds:
        states = ctx.audit_finding_states(rounds)
        print("SWEEP_AUDIT=%s" % proj.audit.name)
        print("AUDITED_INVENTORY_REVISION=%s"
              % (max((r["revision"] for r in rounds), default="?")))
        for r in rounds:
            print("  AUDIT-%-3d %-34s %s" % (r["revision"],
                                             str(r.get("scope", "?"))[:34],
                                             r.get("verdict", "?")))
            for e in r["findings"]:
                state, closed_at, _ = states.get(e["id"], ["open", None, None])
                print("      %-9s %-44s %-9s %s"
                      % (e["id"], str(e.get("finding", "?"))[:44],
                         e.get("severity", "?"),
                         state + (" @AUDIT-%s" % closed_at if closed_at else "")))
    return report(findings, "sweep audit",
                  quiet_pass="PASS  [%s]  sweep audit valid" % proj.name)


def cmd_report(proj, args):
    findings, data = validate_project(proj)
    if data is None:
        for f in findings:
            print(f)
        return 1
    enum = data.get("enumeration") or {}
    queue_entries = parse_review_queue(proj.queue) if proj.queue.exists() else []
    open_items = open_review_items(queue_entries)
    lines = [
        "---",
        'title: "%s — project sweep"' % data.get("title", proj.name),
        "type: project-summary",
        "project: %s" % proj.name,
        "manifest_sha256: %s" % sha256_file(proj.manifest),
        "generated: derived from project-manifest.json — the manifest stays canonical",
        "---",
        "",
        "# %s" % data.get("title", proj.name),
        "",
        "Platform: %s — %s" % (data.get("platform"), data.get("origin") or "no origin"),
        "Enumeration: %s (%s)" % (enum.get("method", "none"),
                                  "verified" if enum.get("verified") is True
                                  else "UNVERIFIED — declared inventory only"),
        "Inventory revision: %s" % data.get("inventory_revision"),
        "Open review items: %d%s" % (len(open_items),
                                     " (%s)" % ", ".join(open_items)
                                     if open_items else ""),
        "",
        "| source | state | rev | conversation | ideas |",
        "|---|---|---|---|---|",
    ]
    for s in data.get("sources") or []:
        if isinstance(s, dict):
            lines.append("| %s | %s | %d | %s | %s |"
                         % (s.get("source_id"), effective_state(s),
                            len(s.get("revisions") or []),
                            s.get("conversation_key", ""),
                            ", ".join(s.get("ideas") or []) or "—"))
    rendered = "\n".join(lines) + "\n"
    if args.write:
        proj.summary.write_text(rendered, encoding="utf-8")
        print("Wrote %s (stamped with the manifest hash it was rendered from)"
              % proj.summary)
    else:
        print(rendered)
    return 0


def cmd_finalize(proj, args):
    findings, data = validate_project(proj)
    if data is None:
        for f in findings:
            print(f)
        return 1
    hard_fails = fails(findings)
    if hard_fails:
        print("FINALIZE_REFUSED — the project record does not validate:")
        for f in hard_fails:
            print(f)
        return 1
    sources = [s for s in data.get("sources") or [] if isinstance(s, dict)]
    if not sources:
        print("FINALIZE_REFUSED — a project with no sources has swept nothing")
        return 1
    unfinished = unfinished_sources(data)
    if unfinished:
        print("FINALIZE_REFUSED — %d source(s) are captured but not yet extracted/"
              "routed at their latest revision:" % len(unfinished))
        for s in unfinished:
            print("  %s state=%s" % (s.get("source_id"), effective_state(s)))
        print("A sweep ends when every source is treated or explicitly hard-failed — "
              "not when the remainder is quietly skipped.")
        return 1
    revision = data.get("inventory_revision") or 0
    audited = audited_inventory_revision(proj)
    if audited != revision:
        print("FINALIZE_REFUSED — the sweep audit covers inventory revision %s, but "
              "the project is at %s. An unaudited sweep is not finished; run the "
              "independent falsification pass first." % (audited or "nothing", revision))
        return 1

    at = args.at or today()
    for s in sources:
        if effective_state(s) == "ROUTED":
            s["state"] = "COMPLETE"
    status = derive_project_status(proj, data)
    data["project_status"] = status
    data["finalized_at"] = at
    save(proj, data)

    enum = data.get("enumeration") or {}
    verified = enum.get("verified") is True
    queue_entries = parse_review_queue(proj.queue) if proj.queue.exists() else []
    open_items = open_review_items(queue_entries)
    hard = hard_gap_sources(data)
    print("PROJECT_STATUS=%s" % status)
    print("PROJECT_ENUMERATION_VERIFIED=%s (method=%s)"
          % ("YES" if verified else "NO", enum.get("method", "none")))
    if not verified:
        print("PROJECT_ENUMERATION_UNVERIFIED — this status answers for the declared "
              "inventory only.")
    print("HARD_GAPS=%s" % (", ".join(s.get("source_id", "?") for s in hard) or "NONE"))
    print("OPEN_REVIEW_ITEMS=%s" % (", ".join(open_items) or "NONE"))
    print("")
    print("KERNEL_HANDOFF (these lines travel together — a handoff that hides the")
    print("gaps or the enumeration status is a false completeness):")
    print("  PROJECT=%s" % proj.name)
    print("  PROJECT_STATUS=%s" % status)
    print("  ENUMERATION=%s/%s" % (enum.get("method", "none"),
                                   "verified" if verified else "UNVERIFIED"))
    print("  INVENTORY_REVISION=%s  SOURCES=%d  IDEAS=%s"
          % (revision, len(sources),
             ", ".join(sorted({slug for s in sources
                               for slug in (s.get("ideas") or [])})) or "none"))
    print("  HARD_GAPS=%s" % (", ".join(s.get("source_id", "?") for s in hard) or "NONE"))
    print("  OPEN_REVIEW_ITEMS=%s" % (", ".join(open_items) or "NONE"))
    print("  MANIFEST=%s" % proj.manifest)
    return 0 if status == "COMPLETE" else 1


def cmd_validate_all(args):
    corpus = corpus_root(args.corpus)
    root = Path(corpus) / PROJECTS_DIR
    names = args.project or (
        sorted(p.name for p in root.iterdir()
               if p.is_dir() and (p / "project-manifest.json").exists())
        if root.is_dir() else [])
    if not names:
        print("FAIL: %s contains no project manifests — a mis-pathed corpus must not "
              "go green with zero coverage" % root)
        return 1
    all_findings = []
    for name in names:
        proj = Project(corpus, name)
        # One malformed project must not take the sweep down with it. An uncaught
        # exception here is worse than any finding it could have reported: every
        # project sorted after the bad one is never validated at all, and the run
        # LOOKS like it stopped rather than like it passed — but nothing says which
        # projects were never reached. A crash is itself a finding, so it is recorded
        # as one and the sweep continues.
        try:
            findings, data = validate_project(proj)
        except Exception as exc:                                  # noqa: BLE001
            findings = [Finding(name, "PROJECT_VALIDATION_CRASHED",
                                "validating this project raised %s: %s — the manifest "
                                "is malformed in a way the contract does not model. "
                                "Treated as a failure, and the remaining projects were "
                                "still validated."
                                % (type(exc).__name__, exc))]
            data = None
        all_findings.extend(findings)
        if not fails(findings):
            print("PASS  [%s]  sources=%d status=%s"
                  % (name, len((data or {}).get("sources") or []),
                     (data or {}).get("project_status") or "in-progress"))
        for f in findings:
            print(f)
    bad = {f.slug for f in fails(all_findings)}
    print("\n%d/%d projects satisfy the project contract"
          % (len(names) - len(bad), len(names)))
    if all_findings:
        print("codes: %s" % ", ".join(sorted({f.code for f in all_findings})))
    return 1 if bad else 0


# ------------------------------------------------------------------- main --

def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", default=argparse.SUPPRESS)

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", default=None)
    sub = ap.add_subparsers(dest="cmd")

    def add(name, help_text, **kw):
        p = sub.add_parser(name, parents=[common], help=help_text)
        p.add_argument("--project", required=kw.get("project", True))
        return p

    p = add("init", "scaffold a project manifest")
    p.add_argument("--title")
    p.add_argument("--platform", choices=["chatgpt", "claude", "other"])
    p.add_argument("--origin")
    p.add_argument("--at")

    p = add("declare", "register a conversation inventory (bulk upsert)")
    p.add_argument("--inventory", required=True)
    p.add_argument("--method", choices=["declared", "data-layer", "mixed"])
    p.add_argument("--verified", action="store_true",
                   help="claim the enumeration is provably exhaustive — requires "
                        "--evidence; DO NOT FAKE IT")
    p.add_argument("--evidence",
                   help="the enumeration evidence record written by "
                        "scripts/project_discovery.js — re-checked here, not trusted. "
                        "May be the same file as --inventory")
    p.add_argument("--origin",
                   help="the project URL, when init did not record one — evidence is "
                        "bound to it, so a verified enumeration needs it")
    p.add_argument("--note")
    p.add_argument("--at")

    p = add("register", "upsert one conversation by canonical identity")
    p.add_argument("--url")
    p.add_argument("--key", help="host/<conversation-id> when no URL exists")
    p.add_argument("--title")
    p.add_argument("--at")

    p = add("capture", "record captured bytes as the next immutable revision")
    p.add_argument("--source", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--adapter", choices=["data-layer", "dom"])
    p.add_argument("--at")

    p = add("mark-extracted", "record which ideas a verified capture produced")
    p.add_argument("--source", required=True)
    p.add_argument("--ideas")
    p.add_argument("--no-ideas", action="store_true")
    p.add_argument("--note")
    p.add_argument("--at")

    p = add("mark-routed", "record that extraction was routed against the corpus")
    p.add_argument("--source", required=True)
    p.add_argument("--at")

    p = add("mark-failed", "record an explicit hard failure — never a silent gap")
    p.add_argument("--source", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--detail", required=True)
    p.add_argument("--at")

    add("status", "per-source lifecycle + next actions (resume support)")
    add("coverage", "the completeness gate — counts and states, never a score")
    add("audit", "validate the independent sweep audit")

    p = add("report", "render PROJECT.md from the manifest")
    p.add_argument("--write", action="store_true")

    p = add("finalize", "end the sweep in an honest terminal state")
    p.add_argument("--at")

    p = sub.add_parser("validate", parents=[common], help="structural corpus sweep")
    p.add_argument("--project", action="append")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 2
    if args.cmd == "validate":
        return cmd_validate_all(args)

    proj = Project(corpus_root(getattr(args, "corpus", None)), args.project)
    if args.cmd != "init" and not proj.exists():
        print("FAIL: no project at %s" % proj.folder)
        print("A mistyped project name must not read as a passing check.")
        return 1

    if args.cmd == "init":
        return cmd_init(proj, args)
    if args.cmd == "declare":
        return cmd_declare(proj, args)
    if args.cmd == "register":
        return cmd_register(proj, args)
    if args.cmd == "capture":
        return cmd_capture(proj, args)
    if args.cmd == "mark-extracted":
        return cmd_mark(proj, args, "extracted")
    if args.cmd == "mark-routed":
        return cmd_mark(proj, args, "routed")
    if args.cmd == "mark-failed":
        return cmd_mark(proj, args, "failed")
    if args.cmd == "status":
        return cmd_status(proj, args)
    if args.cmd == "coverage":
        return cmd_coverage(proj, args)
    if args.cmd == "audit":
        return cmd_audit_cli(proj, args)
    if args.cmd == "report":
        return cmd_report(proj, args)
    if args.cmd == "finalize":
        return cmd_finalize(proj, args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
