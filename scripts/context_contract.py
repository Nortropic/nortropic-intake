#!/usr/bin/env python3
"""Context contract — WHERE the thinking came from, and whether it is complete.

Companion to `plan_contract.py` (which owns HOW: candidate → approval → plan).
This tool owns the source side of an intake package:

  <slug>-context-manifest.json     WHERE   source map + integrity + execution targets
  <slug>-owner-clarifications.md   DELTAS  exact owner Q&A, append-only, CLAR-* IDs

and the gate that decides whether Plan Mode may begin at all.

Subcommands
-----------
  manifest init --slug S      Scaffold a manifest from what is on disk (hashes computed).
  manifest --slug S           Validate the manifest: IDs, integrity, secrets, targets.
  clarifications --slug S     Validate the clarifications artifact and its references.
  coverage --slug S [--target-repo P ...]
                              The pre-Plan gate. Prints PLANNING_CONTEXT_COMPLETE=YES|NO.
  trace --slug S --id ID      Bidirectional provenance for one stable ID.
  trace --slug S --commit SHA Start from implementation evidence and walk back to source.
  validate [--slug S ...]     Corpus sweep: structural validity, legacy items as WARN.

Corpus root: --corpus, else $NORTROPIC_INTAKE_CORPUS, else ~/nortropic/innovation-intake.

What this is NOT
----------------
Not a knowledge base, not a graph database, not a second index. It reads the plain
files of one idea folder, hashes them, and answers questions about coverage and
provenance. Every answer is recomputed from the files each time, so nothing here can
go stale or become a second source of truth.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from intake_common import (  # noqa: E402
    Finding, corpus_root, expand, fails, fm_list, fm_str, git_evidence, git_head_blob,
    id_kind, parse_ids, read_frontmatter, read_json, report, scan_credentials,
    sha256_file, sha256_text, write_json, PROVENANCE_RE, REF_RE,
)

MANIFEST_VERSION = 1

SOURCE_KINDS = {
    "chat-transcript", "attachment", "pasted-text", "image", "external-url",
    "repository", "commit", "owner-clarifications", "related-package",
    "superseded-package", "research", "design-rationale", "brief",
}
CAPTURE_STATUS = {
    "captured",                        # content is here and hashes match
    "not_load_bearing",                # exists, but nothing depends on it
    "unavailable_owner_acknowledged",  # gone; the owner accepted planning without it
    "pending",                         # not yet captured — blocks planning if load-bearing
}
# Execution targets carry roles because Nortropic repos do not share authority.
TARGET_ROLES = {
    "canonical-system":  "owner-gated system authority; Intake may never author its truth",
    "operator-product":  "implementation target for product work",
    "advisory-only":     "READ ONLY — reference material, never a write target",
    "intake-corpus":     "the intake corpus itself",
}
SOURCE_ID_RE = re.compile(r"^SRC-\d{3,}$")
CLAR_ID_RE = re.compile(r"^CLAR-\d{3,}$")

Q_DISPOSITIONS = ("ANSWERED", "EXPLICITLY_DEFERRED", "OWNER_ACCEPTED_OPEN", "BLOCKING")

# A source tag must ADDRESS something: message numbers in the transcript, a manifest
# source id, or a clarification. "(← owner said so)" names nothing and is not provenance.
MSG_TAG_RE = re.compile(r"\bmsg\.?\s*\d+", re.I)
RESOLVABLE_TAG_RE = re.compile(r"\b(SRC-\d+|CLAR-\d+)\b|\bmsg\.?\s*\d+", re.I)


# ------------------------------------------------------------ package paths --

class Package(object):
    """The file layout of one idea folder. Paths only — no interpretation."""

    def __init__(self, corpus, slug):
        self.slug = slug
        self.corpus = Path(corpus)
        self.folder = self.corpus / slug
        self.brief = self.folder / ("idea-%s.md" % slug)
        self.rationale = self.folder / ("%s-design-rationale.md" % slug)
        self.transcript = self.folder / ("%s-full-chat.md" % slug)
        self.manifest = self.folder / ("%s-context-manifest.json" % slug)
        self.clarifications = self.folder / ("%s-owner-clarifications.md" % slug)

    def exists(self):
        return self.brief.exists()


# ---------------------------------------------------------------- manifest --

def validate_manifest(pkg, findings, require=True):
    """Returns the parsed manifest dict (or None). Appends findings."""
    if not pkg.manifest.exists():
        if require:
            findings.append(Finding(
                pkg.slug, "LEGACY_CONTEXT_MANIFEST_MISSING",
                "no %s — packages captured before the context contract have none; "
                "build one when this idea is next activated, never from guesses"
                % pkg.manifest.name, level="WARN"))
        return None

    raw = pkg.manifest.read_text(encoding="utf-8")
    for label, excerpt in scan_credentials(raw):
        findings.append(Finding(
            pkg.slug, "MANIFEST_CREDENTIAL_LEAK",
            "%s: %s near %r — a manifest records WHERE a source lives and must never "
            "turn a credential into durable metadata; sanitize the URL or mark the "
            "source redacted" % (pkg.manifest.name, label, excerpt)))

    data, err = read_json(pkg.manifest)
    if data is None:
        findings.append(Finding(pkg.slug, "MANIFEST_UNREADABLE",
                                "%s %s" % (pkg.manifest.name, err)))
        return None
    if not isinstance(data, dict):
        findings.append(Finding(pkg.slug, "MANIFEST_UNREADABLE",
                                "%s: top level must be an object" % pkg.manifest.name))
        return None

    if data.get("manifest_version") != MANIFEST_VERSION:
        findings.append(Finding(pkg.slug, "MANIFEST_VERSION_INVALID",
                                "manifest_version=%r, expected %d"
                                % (data.get("manifest_version"), MANIFEST_VERSION)))
    if str(data.get("slug", "")).strip() != pkg.slug:
        findings.append(Finding(pkg.slug, "MANIFEST_SLUG_MISMATCH",
                                "manifest slug=%r does not match the folder"
                                % data.get("slug")))

    _validate_targets(pkg, data, findings)
    _validate_sources(pkg, data, findings)
    return data


def _validate_targets(pkg, data, findings):
    targets = data.get("execution_targets")
    if not isinstance(targets, list) or not targets:
        findings.append(Finding(
            pkg.slug, "EXECUTION_TARGETS_MISSING",
            "manifest declares no execution_targets — planning must know which "
            "repositories it is planning against, and with what authority"))
        return
    seen = set()
    for i, t in enumerate(targets):
        where = "execution_targets[%d]" % i
        if not isinstance(t, dict):
            findings.append(Finding(pkg.slug, "EXECUTION_TARGET_INVALID",
                                    "%s is not an object" % where))
            continue
        repo = str(t.get("repo", "")).strip()
        role = str(t.get("role", "")).strip()
        if not repo:
            findings.append(Finding(pkg.slug, "EXECUTION_TARGET_INVALID",
                                    "%s has no repo" % where))
        elif repo in seen:
            findings.append(Finding(pkg.slug, "EXECUTION_TARGET_INVALID",
                                    "%s duplicates repo %r" % (where, repo)))
        else:
            seen.add(repo)
        if role not in TARGET_ROLES:
            findings.append(Finding(
                pkg.slug, "EXECUTION_TARGET_ROLE_INVALID",
                "%s role=%r must be one of %s — roles carry the authority difference "
                "between repos and may not be omitted"
                % (where, role, sorted(TARGET_ROLES))))


def _validate_sources(pkg, data, findings):
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        findings.append(Finding(pkg.slug, "MANIFEST_NO_SOURCES",
                                "manifest lists no sources"))
        return

    seen_ids, referenced_paths = set(), set()
    for i, s in enumerate(sources):
        where = "sources[%d]" % i
        if not isinstance(s, dict):
            findings.append(Finding(pkg.slug, "SOURCE_INVALID", "%s is not an object" % where))
            continue
        sid = str(s.get("source_id", "")).strip()
        if not SOURCE_ID_RE.match(sid):
            findings.append(Finding(pkg.slug, "SOURCE_ID_INVALID",
                                    "%s source_id=%r must look like SRC-001" % (where, sid)))
        elif sid in seen_ids:
            findings.append(Finding(pkg.slug, "SOURCE_ID_DUPLICATE",
                                    "%s reuses %s — a source ID is a stable address and "
                                    "must be unique" % (where, sid)))
        else:
            seen_ids.add(sid)
        label = sid or where

        kind = str(s.get("kind", "")).strip()
        if kind not in SOURCE_KINDS:
            findings.append(Finding(pkg.slug, "SOURCE_KIND_INVALID",
                                    "%s kind=%r must be one of %s"
                                    % (label, kind, sorted(SOURCE_KINDS))))
        status = str(s.get("capture_status", "")).strip()
        if status not in CAPTURE_STATUS:
            findings.append(Finding(pkg.slug, "SOURCE_CAPTURE_STATUS_INVALID",
                                    "%s capture_status=%r must be one of %s"
                                    % (label, status, sorted(CAPTURE_STATUS))))
        if not isinstance(s.get("load_bearing"), bool):
            findings.append(Finding(pkg.slug, "SOURCE_LOAD_BEARING_INVALID",
                                    "%s load_bearing must be true or false — whether "
                                    "planning depends on this source is never implicit"
                                    % label))
        if status == "not_load_bearing" and s.get("load_bearing") is True:
            findings.append(Finding(pkg.slug, "SOURCE_STATUS_CONTRADICTS_LOAD_BEARING",
                                    "%s is load_bearing but marked not_load_bearing" % label))
        if status == "unavailable_owner_acknowledged":
            ack = s.get("owner_ack")
            if not isinstance(ack, dict) or not str(ack.get("date", "")).strip() \
                    or not str(ack.get("note", "")).strip():
                findings.append(Finding(
                    pkg.slug, "SOURCE_OWNER_ACK_MISSING",
                    "%s claims the owner accepted planning without it, so owner_ack "
                    "{date, note} is required — the acknowledgement itself must be "
                    "durable" % label))

        path = str(s.get("path", "")).strip()
        if path:
            if path.startswith("/") or ".." in Path(path).parts:
                findings.append(Finding(pkg.slug, "SOURCE_PATH_INVALID",
                                        "%s path=%r must be relative to the idea folder"
                                        % (label, path)))
                continue
            referenced_paths.add(path)
            target = pkg.folder / path
            if status == "captured":
                if not target.exists():
                    findings.append(Finding(pkg.slug, "SOURCE_FILE_MISSING",
                                            "%s is marked captured but %s does not exist"
                                            % (label, path)))
                    continue
                # A string check is not containment: a symlink keeps a relative-looking
                # path while the bytes live elsewhere, so the package would not actually
                # carry the source it claims to have captured.
                try:
                    if not str(target.resolve()).startswith(
                            str(pkg.folder.resolve()) + os.sep):
                        findings.append(Finding(
                            pkg.slug, "SOURCE_PATH_INVALID",
                            "%s: %s resolves to %s, outside the idea folder — a captured "
                            "source must be content of this package, not a link to it"
                            % (label, path, target.resolve())))
                        continue
                    if target.is_file() and target.stat().st_nlink > 1:
                        findings.append(Finding(
                            pkg.slug, "SOURCE_PATH_INVALID",
                            "%s: %s is hard-linked from elsewhere (st_nlink=%d) — editing "
                            "the other path would silently break this source's hash"
                            % (label, path, target.stat().st_nlink)))
                        continue
                except OSError as exc:
                    findings.append(Finding(pkg.slug, "SOURCE_PATH_INVALID",
                                            "%s: %s: %s" % (label, path, exc)))
                    continue
                declared = str(s.get("sha256", "")).strip().lower()
                actual = sha256_file(target)
                if not declared:
                    findings.append(Finding(pkg.slug, "SOURCE_HASH_MISSING",
                                            "%s is captured but records no sha256 "
                                            "(actual %s)" % (label, actual)))
                elif declared != actual:
                    findings.append(Finding(
                        pkg.slug, "SOURCE_HASH_MISMATCH",
                        "%s records %s but %s hashes to %s — the source changed after "
                        "capture, or the manifest is stale"
                        % (label, declared[:16] + "…", path, actual[:16] + "…")))
        elif status == "captured" and kind in ("external-url", "repository", "commit"):
            if not str(s.get("origin", "")).strip():
                findings.append(Finding(pkg.slug, "SOURCE_ORIGIN_MISSING",
                                        "%s is a %s marked captured but records no origin"
                                        % (label, kind)))
        elif status == "captured":
            findings.append(Finding(pkg.slug, "SOURCE_PATH_MISSING",
                                    "%s is marked captured but has neither path nor "
                                    "an origin-bearing kind" % label))

    # The artifacts that always exist must be addressable in the manifest.
    for artifact, kind in ((pkg.transcript, "chat-transcript"),
                           (pkg.clarifications, "owner-clarifications")):
        if artifact.exists() and artifact.name not in referenced_paths:
            findings.append(Finding(
                pkg.slug, "SOURCE_UNMAPPED",
                "%s exists in the package but no manifest source points at it — every "
                "piece of source material must be addressable" % artifact.name))


def cmd_manifest_init(pkg, args):
    """Scaffold a manifest from what is verifiably on disk. Never invents sources."""
    if pkg.manifest.exists() and not args.force:
        print("REFUSED: %s already exists (pass --force to regenerate the scaffold)"
              % pkg.manifest.name)
        return 2
    if not pkg.exists():
        print("FAIL: no brief at %s" % pkg.brief)
        return 1

    sources, n = [], 0

    def add(path, kind, load_bearing, note=None):
        nonlocal n
        if not path.exists():
            return
        n += 1
        entry = {
            "source_id": "SRC-%03d" % n,
            "kind": kind,
            "name": path.name,
            "path": path.name,
            "sha256": sha256_file(path),
            "capture_status": "captured",
            "load_bearing": load_bearing,
        }
        if kind == "chat-transcript":
            fm, _, _ = read_frontmatter(path)
            entry["fidelity"] = fm_str(fm, "fidelity") or "full"
        if note:
            entry["note"] = note
        sources.append(entry)

    add(pkg.transcript, "chat-transcript", True)
    add(pkg.rationale, "design-rationale", True)
    add(pkg.clarifications, "owner-clarifications", True)

    data = {
        "manifest_version": MANIFEST_VERSION,
        "slug": pkg.slug,
        "execution_targets": [],
        "sources": sources,
    }
    write_json(pkg.manifest, data)
    print("Scaffolded %s with %d source(s) from files actually present." % (
        pkg.manifest.name, len(sources)))
    print("")
    print("This is a SCAFFOLD, not a finished manifest. You must still add, by hand and")
    print("from evidence — never from guesses:")
    print("  * every attachment, pasted document and image the brainstorm relied on")
    print("  * external URLs, repositories and commits that were materially inspected")
    print("  * execution_targets with roles (%s)" % ", ".join(sorted(TARGET_ROLES)))
    print("  * capture_status: pending for anything load-bearing you have not captured")
    return 0


# ---------------------------------------------------------- clarifications --

def parse_clarifications(path):
    """[{id, date, resolves, affects, question, owner_answer, raw}] in file order.

    `owner_answer` deliberately absorbs the rest of its block so multi-paragraph
    owner wording is preserved exactly as written, never reflowed into one line.
    """
    _, body, _ = read_frontmatter(path)
    entries = []
    heads = list(re.finditer(r"^##\s*(CLAR-\d+)\s*$", body, re.M))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        block = body[h.end():end]
        entry = {"id": h.group(1), "raw": block, "affects": [], "line": body[:h.start()].count("\n") + 1}
        lines = block.splitlines()
        for j, line in enumerate(lines):
            m = re.match(r"^\s*[-*]\s*(date|resolves|affects|question|owner_answer)\s*:\s*(.*)$",
                         line)
            if not m:
                continue
            key, value = m.group(1), m.group(2).strip()
            if key == "owner_answer":
                rest = "\n".join(lines[j + 1:]).strip()
                entry["owner_answer"] = (value + ("\n" + rest if rest else "")).strip()
                break
            if key == "affects":
                entry["affects"] = [v.strip() for v in value.split(",") if v.strip()]
            else:
                entry[key] = value
        entries.append(entry)
    return entries


def validate_clarifications(pkg, findings, brief_ids=None):
    """Returns parsed clarifications ([] when the artifact does not exist)."""
    if not pkg.clarifications.exists():
        return []

    fm, _, fm_errors = read_frontmatter(pkg.clarifications)
    for err in fm_errors:
        findings.append(Finding(pkg.slug, "CLARIFICATIONS_FRONTMATTER_AMBIGUOUS",
                                "%s: %s" % (pkg.clarifications.name, err)))
    if fm_str(fm, "type") != "owner-clarifications":
        findings.append(Finding(pkg.slug, "CLARIFICATIONS_TYPE_INVALID",
                                "type=%r, expected owner-clarifications" % fm_str(fm, "type")))
    if fm_str(fm, "slug") != pkg.slug:
        findings.append(Finding(pkg.slug, "CLARIFICATIONS_SLUG_MISMATCH",
                                "slug=%r does not match the folder" % fm_str(fm, "slug")))

    entries = parse_clarifications(pkg.clarifications)
    if not entries:
        findings.append(Finding(pkg.slug, "CLARIFICATIONS_EMPTY",
                                "%s exists but contains no `## CLAR-NNN` entries"
                                % pkg.clarifications.name))

    seen = set()
    for e in entries:
        if not CLAR_ID_RE.match(e["id"]):
            findings.append(Finding(pkg.slug, "CLARIFICATION_ID_INVALID",
                                    "%s must look like CLAR-001" % e["id"]))
        if e["id"] in seen:
            findings.append(Finding(pkg.slug, "CLARIFICATION_ID_DUPLICATE",
                                    "%s appears more than once" % e["id"]))
        seen.add(e["id"])
        for field in ("date", "question", "owner_answer"):
            if not str(e.get(field, "")).strip():
                findings.append(Finding(
                    pkg.slug, "CLARIFICATION_INCOMPLETE",
                    "%s has no %s — an owner answer without its exact question, its "
                    "date and the owner's own wording is not durable provenance"
                    % (e["id"], field)))
        resolves = str(e.get("resolves", "")).strip()
        if not resolves:
            findings.append(Finding(pkg.slug, "CLARIFICATION_INCOMPLETE",
                                    "%s does not say which open question it resolves "
                                    "(use `none` if it resolves none)" % e["id"]))
        elif brief_ids is not None and resolves.lower() != "none":
            for ref in [r.strip() for r in resolves.split(",") if r.strip()]:
                if ref not in brief_ids:
                    findings.append(Finding(
                        pkg.slug, "CLARIFICATION_ORPHANED",
                        "%s resolves %s, which is not an ID in the brief" % (e["id"], ref)))
        if brief_ids is not None:
            for ref in e.get("affects", []):
                if ref not in brief_ids:
                    findings.append(Finding(
                        pkg.slug, "CLARIFICATION_ORPHANED",
                        "%s affects %s, which is not an ID in the brief" % (e["id"], ref)))

    _check_append_only(pkg, findings)
    return entries


def _check_append_only(pkg, findings):
    """Owner wording is never rewritten. When git has a committed version, the new
    file must still start with it — additions only."""
    rel = "%s/%s" % (pkg.slug, pkg.clarifications.name)
    committed = git_head_blob(pkg.corpus, rel)
    if committed is None:
        return  # untracked or brand new: nothing to violate yet
    current = pkg.clarifications.read_text(encoding="utf-8")
    if not current.startswith(committed):
        findings.append(Finding(
            pkg.slug, "CLARIFICATIONS_NOT_APPEND_ONLY",
            "%s no longer starts with its committed content — owner clarifications are "
            "append-only; correct a record by appending a new CLAR that supersedes it, "
            "never by editing what the owner said" % pkg.clarifications.name))


# ----------------------------------------------------------------- the gate --

def _safe_resolve(path):
    try:
        return str(Path(path).resolve())
    except OSError:
        return None


class Coverage(object):
    def __init__(self, slug):
        self.slug = slug
        self.findings = []
        self.counts = {}
        self.missing = []
        self.targets = []

    def block(self, reason):
        self.missing.append(reason)


def open_question_dispositions(fm, ids, clarifications):
    """Q ID -> disposition. A question may never simply disappear."""
    deferred = set(fm_list(fm, "open_questions_deferred"))
    accepted = set(fm_list(fm, "open_questions_owner_accepted"))
    answered = set()
    for e in clarifications:
        for ref in [r.strip() for r in str(e.get("resolves", "")).split(",") if r.strip()]:
            answered.add(ref)
    out = {}
    for qid in sorted(q for q in ids if q.startswith("Q")):
        if qid in answered:
            out[qid] = "ANSWERED"
        elif qid in deferred:
            out[qid] = "EXPLICITLY_DEFERRED"
        elif qid in accepted:
            out[qid] = "OWNER_ACCEPTED_OPEN"
        else:
            out[qid] = "BLOCKING"
    return out


def assess_coverage(pkg, target_repo_overrides=None):
    """The pre-Plan gate. Returns a Coverage object; never raises."""
    cov = Coverage(pkg.slug)
    f = cov.findings

    if not pkg.exists():
        f.append(Finding(pkg.slug, "BRIEF_MISSING", "no %s" % pkg.brief))
        cov.block("the execution brief")
        return cov

    fm, body, fm_errors = read_frontmatter(pkg.brief)
    for err in fm_errors:
        f.append(Finding(pkg.slug, "BRIEF_FRONTMATTER_AMBIGUOUS", err))

    ids = parse_ids(body)
    kinds = {"D": [], "R": [], "AC": [], "Q": []}
    for key in sorted(ids):
        prefix = "AC" if key.startswith("AC") else key[0]
        if prefix in kinds:
            kinds[prefix].append(key)

    # ID-shaped lines inside a code fence are invisible to the parser by design (so a
    # quoted template does not create phantom entries) — which is also a one-line way to
    # hide a real blocking question. Say so rather than let it pass silently.
    from intake_common import fence_spans
    for a, b in fence_spans(body):
        hidden = sorted({m.group("id") for m in
                         re.finditer(r"^\s*(?:[-*]\s*)?(?P<id>(?:D|R|Q|AC)\d+)\.\s+",
                                     body[a:b], re.M)})
        if hidden:
            f.append(Finding(
                pkg.slug, "IDS_HIDDEN_IN_CODE_FENCE",
                "the brief has %s inside a fenced code block, where the contract cannot "
                "see them. Move real entries out of the fence, or renumber the example."
                % ", ".join(hidden)))
            cov.block("%s — currently hidden inside a code fence" % ", ".join(hidden))

    # --- artifacts -------------------------------------------------------
    for path, label, blocking in ((pkg.rationale, "design rationale", True),
                                  (pkg.transcript, "raw transcript", False)):
        if not path.exists():
            f.append(Finding(pkg.slug, "PACKAGE_ARTIFACT_MISSING",
                             "%s is absent" % path.name,
                             level="FAIL" if blocking else "WARN"))
            if blocking:
                cov.block("the %s (%s)" % (label, path.name))

    # --- manifest --------------------------------------------------------
    manifest = validate_manifest(pkg, f, require=True)
    if manifest is None:
        cov.block("the context manifest (%s) — run `manifest init` and complete it"
                  % pkg.manifest.name)
    if any(x.level == "FAIL" for x in f if x.code.startswith(("MANIFEST", "SOURCE", "EXECUTION_TARGET"))):
        cov.block("a valid context manifest (see the manifest findings above)")

    # --- sources ---------------------------------------------------------
    captured = acked = pending = not_load = 0
    if manifest:
        for s in manifest.get("sources", []):
            if not isinstance(s, dict):
                continue
            status = str(s.get("capture_status", "")).strip()
            lb = s.get("load_bearing") is True
            if status == "captured":
                captured += 1
            elif status == "unavailable_owner_acknowledged":
                acked += 1
            elif status == "not_load_bearing":
                not_load += 1
            elif status == "pending":
                pending += 1
                if lb:
                    f.append(Finding(
                        pkg.slug, "LOAD_BEARING_SOURCE_PENDING",
                        "%s (%s) is load-bearing and still PENDING — a perfect brief "
                        "must not hide missing source evidence. Capture it, or record "
                        "an explicit owner acknowledgement."
                        % (s.get("source_id", "?"), s.get("name", "?"))))
                    cov.block("load-bearing source %s (%s)"
                              % (s.get("source_id", "?"), s.get("name", "?")))
    cov.counts["sources_captured"] = captured
    cov.counts["sources_owner_acknowledged"] = acked
    cov.counts["sources_not_load_bearing"] = not_load
    cov.counts["sources_pending"] = pending

    # --- clarifications --------------------------------------------------
    clarifications = validate_clarifications(pkg, f, brief_ids=set(ids))
    cov.counts["clarifications"] = len(clarifications)
    if any(x.level == "FAIL" for x in f if x.code.startswith("CLARIFICATION")):
        cov.block("valid owner clarifications")

    # --- traceability ----------------------------------------------------
    manifest_ids = set()
    if manifest:
        manifest_ids = {str(s.get("source_id", "")).strip()
                        for s in (manifest.get("sources") or []) if isinstance(s, dict)}
    clar_ids = {e["id"] for e in clarifications}

    def resolvable(entry):
        """A tag counts as traced only if it ADDRESSES a real source."""
        for tag in entry["provenance"]:
            if MSG_TAG_RE.search(tag):
                return True
            for ref in re.findall(r"\b(SRC-\d+|CLAR-\d+)\b", tag):
                if ref in manifest_ids or ref in clar_ids:
                    return True
        return False

    for prefix, label in (("D", "decision"), ("R", "rejection"),
                          ("AC", "acceptance criterion")):
        entries = kinds[prefix]
        traced = [i for i in entries if resolvable(ids[i])]
        cov.counts["%s_total" % prefix] = len(entries)
        cov.counts["%s_traced" % prefix] = len(traced)
        for i in entries:
            if i in traced:
                continue
            if not ids[i]["provenance"]:
                f.append(Finding(
                    pkg.slug, "PROVENANCE_MISSING",
                    "%s (%s) carries no `(← …)` source tag — every %s must be "
                    "source-backed before planning" % (i, label, label),
                    level="FAIL"))
            else:
                f.append(Finding(
                    pkg.slug, "PROVENANCE_UNRESOLVABLE",
                    "%s (%s) has a source tag %r that addresses nothing — it must name "
                    "message numbers in the transcript, a manifest SRC id, or a CLAR"
                    % (i, label, ids[i]["provenance"][:1]), level="FAIL"))
        if entries and len(traced) < len(entries):
            cov.block("source tags on %d %s(s)" % (len(entries) - len(traced), label))

    if not kinds["D"]:
        f.append(Finding(pkg.slug, "NO_DECISIONS",
                         "the brief records no D-numbered decisions"))
        cov.block("at least one identified decision (D1, D2, …)")
    if not kinds["AC"]:
        f.append(Finding(pkg.slug, "NO_ACCEPTANCE_CRITERIA",
                         "the brief records no AC-numbered acceptance criteria"))
        cov.block("at least one identified acceptance criterion (AC1, AC2, …)")
    if not kinds["R"] and re.search(r"^\s*REJECTED", body, re.M | re.I):
        f.append(Finding(
            pkg.slug, "LEGACY_REJECTION_IDS_MISSING",
            "the brief has a REJECTED block but no R-numbered entries — give each "
            "rejected path a stable R id before planning, so the plan can be checked "
            "against it", level="FAIL"))
        cov.block("stable R ids for the rejected paths")

    # --- open questions --------------------------------------------------
    dispositions = open_question_dispositions(fm, ids, clarifications)
    tally = {d: 0 for d in Q_DISPOSITIONS}
    for qid, disposition in dispositions.items():
        tally[disposition] += 1
        if disposition == "BLOCKING":
            f.append(Finding(
                pkg.slug, "OPEN_QUESTION_BLOCKING",
                "%s has no disposition — answer it (a CLAR that resolves it), defer it "
                "(`open_questions_deferred`) or accept it open "
                "(`open_questions_owner_accepted`). It may not simply vanish." % qid))
    cov.counts["Q_total"] = len(dispositions)
    for d in Q_DISPOSITIONS:
        cov.counts["Q_%s" % d.lower()] = tally[d]
    if tally["BLOCKING"]:
        cov.block("a disposition for %d open question(s)" % tally["BLOCKING"])

    # --- supersession ----------------------------------------------------
    superseded_by = fm_str(fm, "superseded_by")
    if superseded_by:
        f.append(Finding(pkg.slug, "PACKAGE_SUPERSEDED",
                         "this brief is superseded by %r — plan the successor, not this"
                         % superseded_by))
        cov.block("an unsuperseded package (this one is superseded by %s)" % superseded_by)
    for rel_key in ("supersedes", "related"):
        for other in fm_list(fm, rel_key):
            if not (pkg.corpus / other / ("idea-%s.md" % other)).exists():
                f.append(Finding(pkg.slug, "CORPUS_LINK_DANGLING",
                                 "%s: %s references %r, which is not in the corpus"
                                 % (pkg.brief.name, rel_key, other)))
    cov.counts["supersession_resolved"] = 0 if superseded_by else 1

    # --- current repository reality --------------------------------------
    declared = []
    if manifest:
        for t in manifest.get("execution_targets", []) or []:
            if isinstance(t, dict) and str(t.get("repo", "")).strip():
                declared.append((str(t["repo"]).strip(), str(t.get("role", "")).strip()))
    # An override must name the SAME repository, not merely share its last path segment:
    # matching on basename let a throwaway `…/fake/nortropic-system` stand in for the
    # real one, and the report then printed real git evidence for a path that is absent.
    overrides = {}
    for candidate in (target_repo_overrides or []):
        cpath = expand(candidate)
        overrides[str(cpath)] = cpath
        try:
            overrides[str(cpath.resolve())] = cpath
        except OSError:
            pass
    inspected = 0
    for repo, role in declared:
        declared_path = expand(repo)
        path = declared_path
        for key in (str(declared_path), _safe_resolve(declared_path)):
            if key and key in overrides:
                path = overrides[key]
                break
        evidence = git_evidence(path) if path.exists() else None
        if evidence:
            inspected += 1
            cov.targets.append({"repo": repo, "role": role, "evidence": evidence})
        else:
            cov.targets.append({"repo": repo, "role": role, "evidence": None})
            f.append(Finding(
                pkg.slug, "TARGET_REPO_NOT_INSPECTED",
                "execution target %r could not be inspected (%s) — a brainstorm may be "
                "old, so planning must read current repository reality first"
                % (repo, "not a git repository" if path.exists() else "path not found")))
            cov.block("inspection of execution target %r" % repo)
    cov.counts["targets_declared"] = len(declared)
    cov.counts["targets_inspected"] = inspected

    return cov


def print_coverage(cov, pkg):
    c = cov.counts
    complete = not cov.missing and not fails(cov.findings)
    print("PLANNING_CONTEXT_COMPLETE=%s" % ("YES" if complete else "NO"))
    print("SLUG=%s" % cov.slug)
    print("PACKAGE=%s" % pkg.folder)
    print("")
    print("decisions traced            %s/%s" % (c.get("D_traced", 0), c.get("D_total", 0)))
    print("rejections traced           %s/%s" % (c.get("R_traced", 0), c.get("R_total", 0)))
    print("acceptance criteria traced  %s/%s" % (c.get("AC_traced", 0), c.get("AC_total", 0)))
    print("open questions              %s total — answered %s, deferred %s, "
          "owner-accepted %s, blocking %s"
          % (c.get("Q_total", 0), c.get("Q_answered", 0),
             c.get("Q_explicitly_deferred", 0), c.get("Q_owner_accepted_open", 0),
             c.get("Q_blocking", 0)))
    print("owner clarifications        %s" % c.get("clarifications", 0))
    print("sources                     captured %s, owner-acknowledged %s, "
          "not load-bearing %s, PENDING %s"
          % (c.get("sources_captured", 0), c.get("sources_owner_acknowledged", 0),
             c.get("sources_not_load_bearing", 0), c.get("sources_pending", 0)))
    print("execution targets inspected %s/%s"
          % (c.get("targets_inspected", 0), c.get("targets_declared", 0)))
    print("supersession resolved       %s" % ("YES" if c.get("supersession_resolved") else "NO"))
    for t in cov.targets:
        ev = t["evidence"]
        print("  - %-28s role=%-17s %s" % (
            t["repo"], t["role"],
            ("head:%s branch:%s dirty:%s" % (ev["head"][:12], ev["branch"], ev["dirty"]))
            if ev else "NOT INSPECTED"))
        if t["role"] == "advisory-only":
            print("      %s" % TARGET_ROLES["advisory-only"])
    if cov.findings:
        print("")
        for finding in cov.findings:
            print(finding)
    if not complete:
        print("")
        print("MISSING_CONTEXT:")
        for m in cov.missing:
            print("  - %s" % m)
        print("")
        print("Plan Mode must not begin. Recover the missing context above, or record an")
        print("explicit owner decision (deferral / acknowledged-unavailable) — never")
        print("plan around a gap by inferring what the missing source probably said.")
    return 0 if complete else 1


# --------------------------------------------------------------- traversal --

def build_links(pkg):
    """The provenance graph, rebuilt from files on every call. Never stored."""
    links = {"nodes": {}, "forward": {}, "backward": {}}

    def node(nid, kind, label, where):
        links["nodes"][nid] = {"id": nid, "kind": kind, "label": label, "where": where}
        links["forward"].setdefault(nid, set())
        links["backward"].setdefault(nid, set())

    def edge(a, b):
        if a in links["nodes"] and b in links["nodes"]:
            links["forward"][a].add(b)
            links["backward"][b].add(a)

    fm, body, _ = read_frontmatter(pkg.brief) if pkg.exists() else ({}, "", [])
    ids = parse_ids(body)
    for i, entry in ids.items():
        node(i, id_kind(i) or "brief-entry", entry["text"][:120], pkg.brief.name)

    manifest, _ = read_json(pkg.manifest) if pkg.manifest.exists() else (None, None)
    transcript_src = None
    if isinstance(manifest, dict):
        for s in manifest.get("sources", []) or []:
            if not isinstance(s, dict):
                continue
            sid = str(s.get("source_id", "")).strip()
            if not sid:
                continue
            node(sid, "source", "%s (%s)" % (s.get("name", "?"), s.get("kind", "?")),
                 pkg.manifest.name)
            if s.get("kind") == "chat-transcript":
                transcript_src = sid

    # `(← msg 26, 37)` means "the transcript, at these messages". Only a tag that names
    # actual message numbers earns that edge — prose containing the word "msg" is not
    # provenance, and claiming an edge for it would be the tool inventing evidence.
    for i, entry in ids.items():
        for tag in entry["provenance"]:
            for ref in REF_RE.findall(tag):
                edge(i, ref)
            if MSG_TAG_RE.search(tag) and transcript_src:
                edge(i, transcript_src)

    for e in parse_clarifications(pkg.clarifications) if pkg.clarifications.exists() else []:
        node(e["id"], "owner-clarification",
             str(e.get("owner_answer", ""))[:120], pkg.clarifications.name)
        for ref in [r.strip() for r in str(e.get("resolves", "")).split(",") if r.strip()]:
            if ref.lower() != "none":
                edge(e["id"], ref)
        for ref in e.get("affects", []):
            edge(e["id"], ref)

    plan = _current_plan_path(pkg, fm)
    if plan and plan.exists():
        _, plan_body, _ = read_frontmatter(plan)
        from intake_common import parse_slices  # local import keeps the module boundary
        for sid, s in parse_slices(plan_body).items():
            node(sid, "plan-slice", s["heading"], plan.name)
            for ref in s["refs"]:
                edge(sid, ref)

    # implementation evidence, when the brief records it
    commit = fm_str(fm, "execution_commit")
    if commit:
        eid = "COMMIT:%s" % commit[:12]
        node(eid, "implementation-evidence",
             "%s @ %s" % (fm_str(fm, "execution_repo") or "?", commit[:12]), pkg.brief.name)
        slice_id = fm_str(fm, "execution_slice")
        if slice_id:
            edge(eid, slice_id)
    return links


def _current_plan_path(pkg, fm):
    ref = fm_str(fm, "approved_plan")
    if ref and "/" not in ref:
        return pkg.folder / ref
    return None


def walk(links, start, direction, depth=6):
    seen, order, frontier = {start}, [], [(start, 0)]
    while frontier:
        nid, d = frontier.pop(0)
        if d >= depth:
            continue
        for nxt in sorted(links[direction].get(nid, ())):
            if nxt not in seen:
                seen.add(nxt)
                order.append((nxt, d + 1))
                frontier.append((nxt, d + 1))
    return order


def cmd_trace(pkg, args):
    if not pkg.exists():
        print("FAIL: no brief at %s" % pkg.brief)
        return 1
    links = build_links(pkg)

    start = args.id
    if args.commit:
        matches = [n for n in links["nodes"]
                   if n.startswith("COMMIT:") and args.commit.startswith(n.split(":", 1)[1])
                   or n == "COMMIT:%s" % args.commit[:12]]
        if not matches:
            print("PROVENANCE_UNRESOLVED")
            print("No implementation evidence in %s references commit %s."
                  % (pkg.brief.name, args.commit))
            print("Record it with execution_repo / execution_commit / execution_slice in")
            print("the brief frontmatter, or in the PR/commit trailer convention.")
            return 1
        start = matches[0]

    if start not in links["nodes"]:
        print("PROVENANCE_UNRESOLVED")
        print("%r is not a known ID in this package." % start)
        known = sorted(links["nodes"])
        print("Known IDs: %s" % (", ".join(known[:40]) + ("…" if len(known) > 40 else "")))
        return 1

    def show(nid, indent):
        n = links["nodes"][nid]
        print("%s%-14s %-22s %s" % (" " * indent, n["kind"], nid, n["label"]))

    print("TRACE_ID=%s" % start)
    print("PACKAGE=%s" % pkg.folder)
    print("")
    print("TOWARDS SOURCE (what this rests on):")
    forward = walk(links, start, "forward")
    show(start, 2)
    for nid, d in forward:
        show(nid, 2 + 2 * d)
    if not forward:
        print("    (nothing — this is a root source)")
    print("")
    print("TOWARDS IMPLEMENTATION (what rests on this):")
    backward = walk(links, start, "backward")
    show(start, 2)
    for nid, d in backward:
        show(nid, 2 + 2 * d)
    if not backward:
        print("    (nothing yet cites this)")
    print("")
    reached = {links["nodes"][n]["kind"] for n, _ in forward + backward}
    print("REACHES_SOURCE=%s" % ("YES" if "source" in reached else "NO"))
    print("REACHES_IMPLEMENTATION=%s" % ("YES" if "implementation-evidence" in reached else "NO"))
    return 0


# ------------------------------------------------------------ corpus sweep --

def iter_slugs(corpus):
    corpus = Path(corpus)
    if not corpus.is_dir():
        sys.exit("FAIL: corpus %s does not exist" % corpus)
    for child in sorted(corpus.iterdir()):
        if child.is_dir() and not child.name.startswith(".") and any(child.glob("idea-*.md")):
            yield child.name


def cmd_validate(args):
    corpus = corpus_root(args.corpus)
    slugs = args.slug or list(iter_slugs(corpus))
    if not slugs:
        print("FAIL: %s contains no idea packages — a mis-pathed corpus must not go "
              "green with zero coverage" % corpus)
        return 1
    findings, ok = [], 0
    for slug in slugs:
        pkg = Package(corpus, slug)
        local = []
        if not pkg.exists():
            local.append(Finding(slug, "BRIEF_MISSING", "no idea-%s.md" % slug))
        else:
            fm, body, fm_errors = read_frontmatter(pkg.brief)
            for err in fm_errors:
                local.append(Finding(slug, "BRIEF_FRONTMATTER_AMBIGUOUS", err))
            validate_manifest(pkg, local, require=True)
            validate_clarifications(pkg, local, brief_ids=set(parse_ids(body)))
        findings.extend(local)
        if not fails(local):
            ok += 1
            print("PASS  [%s]  manifest=%s clarifications=%s" % (
                slug,
                "yes" if pkg.manifest.exists() else "—",
                "yes" if pkg.clarifications.exists() else "—"))
        for finding in local:
            print(finding)
    print("\n%d/%d packages satisfy the context contract" % (ok, len(slugs)))
    hard = fails(findings)
    if findings:
        print("codes: %s" % ", ".join(sorted({f.code for f in findings})))
    return 1 if hard else 0


# ------------------------------------------------------------------- main --

def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", default=argparse.SUPPRESS)

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", default=None)
    sub = ap.add_subparsers(dest="cmd")

    m = sub.add_parser("manifest", parents=[common], help="validate (or init) the manifest")
    m.add_argument("action", nargs="?", choices=["init"], default=None)
    m.add_argument("--slug", required=True)
    m.add_argument("--force", action="store_true")

    c = sub.add_parser("clarifications", parents=[common],
                       help="validate the owner-clarifications artifact")
    c.add_argument("--slug", required=True)

    g = sub.add_parser("coverage", parents=[common], help="the pre-Plan-Mode gate")
    g.add_argument("--slug", required=True)
    g.add_argument("--target-repo", action="append", default=[],
                   help="override a declared target's path (repeatable)")
    # There is deliberately no --lenient flag. A gate with a documented bypass is not a
    # gate; legacy leniency belongs to the corpus sweep, which is a different command.

    t = sub.add_parser("trace", parents=[common], help="bidirectional provenance")
    t.add_argument("--slug", required=True)
    t.add_argument("--id")
    t.add_argument("--commit")

    v = sub.add_parser("validate", parents=[common], help="corpus sweep")
    v.add_argument("--slug", action="append")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 2

    if args.cmd == "validate":
        return cmd_validate(args)

    pkg = Package(corpus_root(getattr(args, "corpus", None)), args.slug)

    if args.cmd in ("manifest", "clarifications", "coverage", "trace") and not pkg.exists():
        print("FAIL: no idea package at %s" % pkg.folder)
        print("A mistyped slug must not read as a passing check.")
        return 1

    if args.cmd == "manifest":
        if args.action == "init":
            return cmd_manifest_init(pkg, args)
        findings = []
        validate_manifest(pkg, findings, require=True)
        return report(findings, "manifest", quiet_pass="PASS  [%s]  manifest valid" % args.slug)
    if args.cmd == "clarifications":
        if not pkg.clarifications.exists():
            print("NONE  [%s]  no %s — valid: clarifications exist only when the owner "
                  "has answered something" % (args.slug, pkg.clarifications.name))
            return 0
        findings = []
        _, body, _ = read_frontmatter(pkg.brief) if pkg.exists() else ({}, "", [])
        entries = validate_clarifications(pkg, findings, brief_ids=set(parse_ids(body)))
        return report(findings, "clarifications",
                      quiet_pass="PASS  [%s]  %d clarification(s) valid and append-only"
                                 % (args.slug, len(entries)))
    if args.cmd == "coverage":
        cov = assess_coverage(pkg, args.target_repo)
        return print_coverage(cov, pkg)
    if args.cmd == "trace":
        if not args.id and not args.commit:
            ap.error("trace: --id or --commit is required")
        return cmd_trace(pkg, args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
