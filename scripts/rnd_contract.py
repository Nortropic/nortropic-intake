#!/usr/bin/env python3
"""RND_COMPILE contract — the derived R&D layer, validated (v4).

`rnd_contract.py` governs `_rnd/<compile>/`: a typed, derived, rebuildable
representation of what ALREADY-CAPTURED material actually contains. It is the third
contract next to `plan_contract.py` (HOW) and `project_contract.py` (WHICH sources):
this one answers WHAT THE CORPUS KNOWS — and, through the coverage lens, what it
does NOT.

The laws this module exists to enforce, mechanically where a machine can and by
refusing the vocabulary where it cannot:

    RAW EVIDENCE SURVIVES SYNTHESIS.       EVIDENCE != AUTHORITY.
    INTAKE != BACKLOG.                     OPTION != COMMITMENT.
    FREQUENCY != IMPORTANCE.               RECENCY != CORRECTNESS.
    DEFERRED != FORGOTTEN.                 SILENCE = UNKNOWN.
    CURRENT VERIFIED REALITY OUTRANKS COMPILED MEMORY.
    ACTIVATION BELONGS TO EXECUTIVE FUNCTION.
    EXECUTION BELONGS TO THE AUTONOMY KERNEL.

Structural guarantees, deliberate and load-bearing:
  * The command surface can read the corpus and write ONLY `_rnd/<compile>/`.
    There is no command that writes an idea package, opens a plan, moves a
    lifecycle status, records an approval, or installs a pointer. A capability
    that does not exist cannot be laundered into.
  * The IR's vocabulary has no priority, no score, no disposition, no lifecycle.
    Refusing the fields is how "Intake is not a backlog" survives contact with a
    model that would helpfully rank things.
  * The derived layer is deletable: everything under `_rnd/<compile>/` can be
    removed and rebuilt from the same source set without losing one byte of
    evidence, because evidence never lives here.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from intake_common import (  # noqa: E402
    Finding, corpus_root, fails, git_head_blob, parse_transcript_roles,
    read_json, report, sha256_file, sha256_text, transcript_source_region,
    transcript_source_sha256, write_json, ROLE_ASSISTANT, ROLE_OWNER,
    TRANSCRIPT_HEADER_RE, SHA256_RE,
)

IR_VERSION = 1
IR_NAME = "rnd-ir.json"
RENDER_NAME = "RND-COVERAGE.md"
AUDIT_NAME = "compile-audit.md"
RND_DIRNAME = "_rnd"

COMPILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
ITEM_ID_RE = re.compile(r"^RND-\d{3,}$")
FIND_ID_RE = re.compile(r"^FIND-\d{3,}$")
RQ_ID_RE = re.compile(r"^RQ-\d{3,}$")
MSG_RANGE_RE = re.compile(r"^(\d+)(?:\s*[-–]\s*(\d+))?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The core ontology — seven kinds, closed on purpose. Failure modes, operating laws,
# candidate primitives, patterns and external analogies are tags/relations on these,
# never new first-class kinds; expanding this tuple requires a contract + eval that
# demonstrates the small set loses a material semantic distinction.
KINDS = ("OBSERVATION", "OWNER_DECISION", "DERIVED_JUDGMENT", "HYPOTHESIS",
         "REQUIREMENT", "OPTION", "UNKNOWN")
AUTHORITY_CLASSES = ("owner", "evidence", "derived")
RELATIONS = ("supports", "contradicts", "refines", "depends-on", "relates-to",
             "supersedes", "answers")

# The baseline coverage lens — a DIAGNOSTIC lens, never an exhaustive ontology of
# Nortropic. All twelve rows are mandatory in every compile; a lens with no
# evidence is UNKNOWN, never absent, and UNKNOWN never counts as resolved.
BASELINE_LENSES = (
    "truth-trust", "professional-excellence", "organization",
    "executive-function", "continuity-operate-forever",
    "identity-data-economics", "learning-evolution", "rnd-intake",
    "assurance-red-team", "lovability-product-experience", "reality-dogfood",
    "explicit-unknowns-deferred",
)
COVERAGE_STATES = ("WELL_EXPLORED", "PARTIALLY_EXPLORED", "NEEDS_RESEARCH",
                   "NEEDS_REALITY", "OWNER_DECISION", "INTENTIONALLY_DEFERRED",
                   "UNKNOWN")
# Deferral is an owner act (DEFERRED != FORGOTTEN), and "the owner decided this
# lens" is an owner claim — both must rest on at least one OWNER_DECISION item.
OWNER_BACKED_STATES = ("OWNER_DECISION", "INTENTIONALLY_DEFERRED")

# INTAKE != BACKLOG, enforced at the vocabulary level: these keys may not appear
# ANYWHERE in an IR, so there is no field for a priority signal to hide in. An idea
# mentioned twenty times is one item with twenty provenance entries, never a
# heavier one.
PRIORITIZATION_KEYS = {"priority", "importance", "rank", "weight", "urgency",
                       "frequency"}
SCORE_KEYS = {"score"}
LIFECYCLE_KEYS = {"status", "implement_now", "task", "plan", "backlog",
                  "milestone", "deadline"}
DISPOSITION_KEYS = {"disposition"}

# Referenced, never copied: the IR points into the corpus and must not become a
# second copy of it. Caps are generous for a claim and tight for a quote.
CLAIM_MAX = 1000
QUOTE_MAX = 500

AUDIT_CODES = (
    "RND_BACKLOG_LAUNDERING", "RND_AUTHORITY_LAUNDERING",
    "RND_OWNER_PROVENANCE_LAUNDERED", "RND_FREQUENCY_BIAS", "RND_RECENCY_BIAS",
    "RND_NEGATIVE_SPACE_OMITTED", "RND_ONTOLOGY_EXPANSION", "RND_SECOND_TRUTH",
    "RND_PLANNING_ENTERED", "RND_COLLAPSED_TO_SINGLE_IDEA",
    "RND_COVERAGE_OVERSTATED",
)

STANDING_LINES = (
    "RAW_EVIDENCE_SURVIVES_SYNTHESIS=YES",
    "EVIDENCE_IS_AUTHORITY=NO",
    "INTAKE_IS_BACKLOG=NO",
    "OPTION_IS_COMMITMENT=NO",
    "FREQUENCY_IS_IMPORTANCE=NO",
    "ACTIVATION_BELONGS_TO=EXECUTIVE_FUNCTION",
    "EXECUTION_BELONGS_TO=AUTONOMY_KERNEL",
    "CURRENT_VERIFIED_REPO_REALITY_OUTRANKS_COMPILED_MEMORY=YES",
    "RND_DISPOSITION_AUTHORITY=NONE",
    "REALITY_POINTERS_REQUIRE_FRESH_READ=YES",
)


# ---------------------------------------------------------------- discovery --

def rnd_root(corpus):
    return Path(corpus) / RND_DIRNAME


def compile_dir(corpus, compile_id):
    return rnd_root(corpus) / compile_id


def list_compiles(corpus):
    root = rnd_root(corpus)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and (p / IR_NAME).exists())


def load_ir(corpus, compile_id):
    """(ir dict | None, findings). Malformed input is a finding, never a crash."""
    findings = []
    if not COMPILE_ID_RE.match(compile_id or ""):
        findings.append(Finding(compile_id or "?", "RND_COMPILE_ID_INVALID",
                                "compile id must match [a-z0-9][a-z0-9-]* — got %r"
                                % compile_id))
        return None, findings
    path = compile_dir(corpus, compile_id) / IR_NAME
    data, err = read_json(path)
    if err:
        findings.append(Finding(compile_id, "RND_IR_MISSING" if "exist" in err
                                else "RND_IR_MALFORMED", "%s %s" % (path, err)))
        return None, findings
    if not isinstance(data, dict):
        findings.append(Finding(compile_id, "RND_IR_MALFORMED",
                                "IR root must be an object"))
        return None, findings
    return data, findings


# ------------------------------------------------------------- source set ---

def parse_msg_range(spec):
    m = MSG_RANGE_RE.match(str(spec).strip())
    if not m:
        return None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    if lo < 1 or hi < lo:
        return None
    return lo, hi


class BoundSource(object):
    """One bound source: recorded identity + lazily verified bytes."""

    def __init__(self, corpus, rec):
        self.rec = rec
        self.source_id = str(rec.get("source_id", "")).strip()
        self.path = Path(corpus) / str(rec.get("path", "")).strip()
        self.recorded_sha = str(rec.get("source_sha256", "")).strip().lower()
        self.excluded = str(rec.get("excluded", "")).strip()
        self._text = None
        self._roles = None
        self._count = None

    def read(self):
        if self._text is None:
            self._text = self.path.read_text(encoding="utf-8")
        return self._text

    def verify(self, compile_id, findings):
        """Raw evidence survives synthesis — checked, not assumed."""
        if self.excluded:
            return False
        if not self.path.exists():
            findings.append(Finding(compile_id, "RND_SOURCE_FILE_MISSING",
                                    "%s: %s does not exist"
                                    % (self.source_id, self.path)))
            return False
        actual = transcript_source_sha256(self.read())
        if self.recorded_sha and actual != self.recorded_sha:
            findings.append(Finding(
                compile_id, "RND_SOURCE_HASH_MISMATCH",
                "%s: bytes on disk hash to %s… but the IR binds %s… — the evidence "
                "this compile was derived from is not the evidence on disk"
                % (self.source_id, actual[:12], self.recorded_sha[:12])))
            return False
        return True

    def roles(self):
        if self._roles is None:
            region, _ = transcript_source_region(self.read())
            self._roles = parse_transcript_roles(region)
        return self._roles

    def message_count(self):
        if self._count is None:
            region, found = transcript_source_region(self.read())
            self._count = (len(TRANSCRIPT_HEADER_RE.findall(region))
                           if found else 0)
        return self._count


def bind_sources(corpus, ir):
    src = ir.get("source_set")
    out = {}
    if not isinstance(src, dict):
        return out
    for rec in src.get("sources") or []:
        if isinstance(rec, dict):
            b = BoundSource(corpus, rec)
            if b.source_id:
                out[b.source_id] = b
    return out


def project_review_queue_owner_answers(corpus, project):
    """{RQ id: owner_answer text} for entries that carry the owner's exact words."""
    answers = {}
    path = Path(corpus) / "_projects" / project / "review-queue.md"
    if not path.exists():
        return answers
    text = path.read_text(encoding="utf-8")
    entries = re.split(r"^##\s+(RQ-\d{3,})\s*$", text, flags=re.M)
    for i in range(1, len(entries) - 1, 2):
        rq, body = entries[i], entries[i + 1]
        m = re.search(r"^-\s*owner_answer:\s*(.+)$", body, re.M)
        if m and m.group(1).strip():
            answers[rq] = m.group(1).strip()
    return answers


# ------------------------------------------------------- vocabulary guards --

def scan_forbidden_keys(node, path, findings, compile_id):
    """No field exists for a backlog to hide in — recursively."""
    if isinstance(node, dict):
        for key, value in node.items():
            lk = str(key).strip().lower()
            base = lk.rsplit("_", 1)[-1]
            here = "%s.%s" % (path, key)
            if lk in DISPOSITION_KEYS:
                findings.append(Finding(
                    compile_id, "RND_DISPOSITION_FORBIDDEN",
                    "%s: KEEP/ADAPT/MERGE/… is Recompile's verdict against fresh "
                    "repo reality, never Intake's" % here))
            elif lk in SCORE_KEYS or base in SCORE_KEYS:
                findings.append(Finding(
                    compile_id, "RND_SCORE_FORBIDDEN",
                    "%s: no single-number reduction — lovability and its relatives "
                    "are diagnostic signals, not a score" % here))
            elif lk in PRIORITIZATION_KEYS or base in PRIORITIZATION_KEYS:
                findings.append(Finding(
                    compile_id, "RND_PRIORITIZATION_FORBIDDEN",
                    "%s: INTAKE != BACKLOG — frequency/recency/importance carry no "
                    "weight here" % here))
            elif lk in LIFECYCLE_KEYS:
                findings.append(Finding(
                    compile_id, "RND_LIFECYCLE_FIELD_FORBIDDEN",
                    "%s: a compile never holds lifecycle, tasks or plans" % here))
            scan_forbidden_keys(value, here, findings, compile_id)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            scan_forbidden_keys(value, "%s[%d]" % (path, idx), findings, compile_id)


# ------------------------------------------------------------- validation ---

def validate_compile(corpus, compile_id):
    ir, findings = load_ir(corpus, compile_id)
    if ir is None:
        return findings, None
    cid = compile_id

    if ir.get("rnd_ir_version") != IR_VERSION:
        findings.append(Finding(cid, "RND_IR_VERSION_UNSUPPORTED",
                                "rnd_ir_version=%r; this contract is version %d"
                                % (ir.get("rnd_ir_version"), IR_VERSION)))
    if str(ir.get("compile_id", "")).strip() != cid:
        findings.append(Finding(cid, "RND_COMPILE_ID_MISMATCH",
                                "directory %r vs compile_id %r"
                                % (cid, ir.get("compile_id"))))
    if str(ir.get("mode", "")).strip() != "RND_COMPILE":
        findings.append(Finding(cid, "RND_MODE_INVALID",
                                "mode must be RND_COMPILE, got %r" % ir.get("mode")))
    # The derived layer carries no execution authority — as a recorded fact the
    # file itself must state, so a consumer that reads only the IR still sees it.
    if ir.get("derived_layer") is not True or \
            str(ir.get("execution_authority", "")).strip().lower() != "none":
        findings.append(Finding(
            cid, "RND_AUTHORITY_CLAIMED",
            "derived_layer must be true and execution_authority must be 'none' — "
            "a compile is a reading, never a runtime"))

    scan_forbidden_keys(ir, "ir", findings, cid)

    # --- source set -----------------------------------------------------
    src = ir.get("source_set")
    sources = bind_sources(corpus, ir)
    rq_answers = {}
    if not isinstance(src, dict) or \
            str(src.get("kind", "")) not in ("project", "explicit"):
        findings.append(Finding(cid, "RND_SOURCE_SET_INVALID",
                                "source_set.kind must be 'project' or 'explicit'"))
        src = {}
    included = {sid: b for sid, b in sources.items() if not b.excluded}
    if not included:
        findings.append(Finding(cid, "RND_SOURCE_SET_EMPTY",
                                "a compile of nothing understands nothing"))
    for sid, b in sources.items():
        if not b.excluded and not b.recorded_sha:
            findings.append(Finding(cid, "RND_SOURCE_SET_INVALID",
                                    "%s carries no source_sha256 — an unbound "
                                    "source cannot witness anything" % sid))
    if str(src.get("kind", "")) == "project":
        project = str(src.get("project", "")).strip()
        if not project:
            findings.append(Finding(cid, "RND_SOURCE_SET_INVALID",
                                    "project-bound source_set names no project"))
        else:
            rq_answers = project_review_queue_owner_answers(corpus, project)
            manifest, err = read_json(Path(corpus) / "_projects" / project
                                      / "project-manifest.json")
            if err:
                findings.append(Finding(cid, "RND_SOURCE_SET_INVALID",
                                        "bound project %r: manifest %s"
                                        % (project, err), level="WARN"))
            elif isinstance(manifest, dict):
                # A proof is about the set that existed when it was measured: a
                # project that has since grown makes the compile STALE (recompile
                # against the new revision), never invalid.
                rev = manifest.get("inventory_revision")
                sha = str(manifest.get("inventory_sha256", "")).strip()
                if (rev != src.get("inventory_revision")
                        or (sha and sha != str(src.get("inventory_sha256", "")).strip())):
                    findings.append(Finding(
                        cid, "RND_SOURCE_SET_STALE",
                        "bound at inventory_revision=%s, project is at %s — the "
                        "compile describes the set it measured; recompile to "
                        "describe today's" % (src.get("inventory_revision"), rev),
                        level="WARN"))
    for b in sources.values():
        b.verify(cid, findings)

    # --- items ----------------------------------------------------------
    items = ir.get("items")
    if not isinstance(items, list):
        findings.append(Finding(cid, "RND_IR_MALFORMED", "items must be a list"))
        items = []
    by_id = {}
    owner_backed = set()
    activation_count = 0
    pointer_count = 0
    for idx, item in enumerate(items):
        where = "items[%d]" % idx
        if not isinstance(item, dict):
            findings.append(Finding(cid, "RND_IR_MALFORMED",
                                    "%s is not an object" % where))
            continue
        iid = str(item.get("id", "")).strip()
        if not ITEM_ID_RE.match(iid):
            findings.append(Finding(cid, "RND_ITEM_ID_INVALID",
                                    "%s: id %r must match RND-NNN" % (where, iid)))
            continue
        if iid in by_id:
            findings.append(Finding(cid, "RND_ITEM_ID_DUPLICATE", iid))
            continue
        by_id[iid] = item

        kind = str(item.get("kind", "")).strip()
        if kind not in KINDS:
            findings.append(Finding(
                cid, "RND_KIND_INVALID",
                "%s: %r — the ontology is closed at %d kinds; express it as a "
                "tag/relation/property, or bring the contract+eval that proves a "
                "material semantic distinction is lost" % (iid, kind, len(KINDS))))
            kind = None

        claim = str(item.get("claim", "")).strip()
        if not claim:
            findings.append(Finding(cid, "RND_CLAIM_MISSING", iid))
        elif len(claim) > CLAIM_MAX:
            findings.append(Finding(cid, "RND_RAW_DUPLICATION",
                                    "%s: claim is %d chars (max %d) — reference "
                                    "the corpus, never re-house it"
                                    % (iid, len(claim), CLAIM_MAX)))
        quote = str(item.get("quote", "")).strip()
        if len(quote) > QUOTE_MAX:
            findings.append(Finding(cid, "RND_RAW_DUPLICATION",
                                    "%s: quote is %d chars (max %d)"
                                    % (iid, len(quote), QUOTE_MAX)))
        if not str(item.get("scope", "")).strip():
            findings.append(Finding(cid, "RND_SCOPE_MISSING", iid))
        if "uncertainty" not in item or not str(item.get("uncertainty", "")).strip():
            findings.append(Finding(cid, "RND_UNCERTAINTY_MISSING",
                                    "%s: uncertainty is explicit here, even when "
                                    "it is 'none — verbatim owner statement'" % iid))

        ac = str(item.get("authority_class", "")).strip()
        if ac not in AUTHORITY_CLASSES:
            findings.append(Finding(cid, "RND_AUTHORITY_CLASS_INVALID",
                                    "%s: %r" % (iid, ac)))
        elif kind == "OWNER_DECISION" and ac != "owner":
            findings.append(Finding(cid, "RND_AUTHORITY_CLASS_INVALID",
                                    "%s: an OWNER_DECISION carries "
                                    "authority_class 'owner'" % iid))
        elif kind is not None and kind != "OWNER_DECISION" and ac == "owner":
            findings.append(Finding(
                cid, "RND_AUTHORITY_LAUNDERING",
                "%s: %s claims authority_class 'owner' — owner authority exists "
                "only on OWNER_DECISION items with owner provenance" % (iid, kind)))

        if str(item.get("activation_condition", "")).strip():
            activation_count += 1
        rp = item.get("reality_pointer")
        if rp is not None:
            pointer_count += 1
            if not isinstance(rp, dict) or \
                    not DATE_RE.match(str(rp.get("observed_at", "")).strip()):
                findings.append(Finding(
                    cid, "RND_REALITY_POINTER_UNDATED",
                    "%s: a repo-reality pointer without observed_at would read as "
                    "timeless truth — it is a dated observation" % iid))

        # provenance
        prov = item.get("provenance")
        prov = prov if isinstance(prov, list) else []
        resolved_any = False
        roles_seen = set()
        for p in prov:
            if not isinstance(p, dict):
                findings.append(Finding(cid, "RND_PROVENANCE_UNBOUND",
                                        "%s: provenance entry is not an object"
                                        % iid))
                continue
            rq = str(p.get("rq", "")).strip()
            if rq:
                if not RQ_ID_RE.match(rq):
                    findings.append(Finding(cid, "RND_PROVENANCE_UNBOUND",
                                            "%s: %r is not an RQ id" % (iid, rq)))
                elif rq not in rq_answers:
                    findings.append(Finding(
                        cid, "RND_OWNER_DECISION_RQ_UNANSWERED" if
                        kind == "OWNER_DECISION" else "RND_PROVENANCE_UNBOUND",
                        "%s: %s carries no owner_answer in the bound project's "
                        "review queue" % (iid, rq)))
                else:
                    resolved_any = True
                    roles_seen.add(ROLE_OWNER)
                continue
            sid = str(p.get("source_id", "")).strip()
            b = sources.get(sid)
            if b is None or b.excluded:
                findings.append(Finding(cid, "RND_PROVENANCE_UNBOUND",
                                        "%s cites %r, which the source set does "
                                        "not bind" % (iid, sid or "?")))
                continue
            if not b.path.exists() or (
                    b.recorded_sha
                    and transcript_source_sha256(b.read()) != b.recorded_sha):
                continue      # the per-source finding is already recorded once
            spec = p.get("messages")
            if spec is None:
                resolved_any = True     # whole-source citation
                continue
            rng = parse_msg_range(spec)
            count = b.message_count()
            if rng is None or rng[1] > count:
                findings.append(Finding(
                    cid, "RND_PROVENANCE_OUT_OF_RANGE",
                    "%s cites %s msg %s of a %d-message capture — an unreachable "
                    "citation is what an invented claim produces"
                    % (iid, sid, spec, count)))
                continue
            resolved_any = True
            roles = b.roles()
            for n in range(rng[0], rng[1] + 1):
                roles_seen.add(roles.get(n, "unknown"))
        if not prov or not resolved_any:
            findings.append(Finding(cid, "RND_ITEM_UNSOURCED",
                                    "%s: every derived item cites the evidence "
                                    "it stands on" % iid))
        if kind == "OWNER_DECISION":
            # Role-aware, fail-closed, exactly as SINGLE mode: an assistant turn
            # can never impersonate the owner, and an unclassifiable one never
            # supplies the backing the assistant turns lack.
            if ROLE_OWNER in roles_seen:
                owner_backed.add(iid)
            elif ROLE_ASSISTANT in roles_seen:
                findings.append(Finding(
                    cid, "RND_OWNER_DECISION_ASSISTANT_ONLY",
                    "%s: every provable cited turn is the assistant's — "
                    "'Johnny decided X' said by an assistant is a proposal, "
                    "not an owner decision" % iid))
            elif resolved_any:
                findings.append(Finding(
                    cid, "RND_OWNER_DECISION_ROLE_UNPROVEN",
                    "%s: no cited turn provably carries the owner's voice — the "
                    "honest kind for this content is OBSERVATION or "
                    "DERIVED_JUDGMENT" % iid))

    # relations — second pass, so forward references are fine
    for iid, item in by_id.items():
        rels = item.get("relations")
        rels = rels if isinstance(rels, list) else []
        for rel in rels:
            if not isinstance(rel, dict):
                findings.append(Finding(cid, "RND_RELATION_INVALID",
                                        "%s: relation is not an object" % iid))
                continue
            rv = str(rel.get("rel", "")).strip()
            target = str(rel.get("target", "")).strip()
            if rv not in RELATIONS:
                findings.append(Finding(cid, "RND_RELATION_INVALID",
                                        "%s: rel %r" % (iid, rv)))
                continue
            tgt = by_id.get(target)
            if tgt is None:
                findings.append(Finding(cid, "RND_RELATION_DANGLING",
                                        "%s → %r" % (iid, target)))
                continue
            if rv == "supersedes" and \
                    str(tgt.get("kind", "")).strip() == "OWNER_DECISION":
                src_kind = str(item.get("kind", "")).strip()
                if src_kind != "OWNER_DECISION" or iid not in owner_backed:
                    findings.append(Finding(
                        cid, "RND_DECISION_SUPERSEDED_WITHOUT_OWNER",
                        "%s (%s) supersedes %s, an owner decision — only a newer "
                        "owner decision with owner provenance may do that; newer "
                        "evidence that disagrees is a 'contradicts' relation, and "
                        "both items survive" % (iid, src_kind or "?", target)))

    # --- coverage -------------------------------------------------------
    coverage = ir.get("coverage")
    coverage = coverage if isinstance(coverage, list) else []
    seen_lenses = {}
    for idx, row in enumerate(coverage):
        if not isinstance(row, dict):
            findings.append(Finding(cid, "RND_IR_MALFORMED",
                                    "coverage[%d] is not an object" % idx))
            continue
        lens = str(row.get("lens", "")).strip()
        state = str(row.get("state", "")).strip()
        if lens in seen_lenses:
            findings.append(Finding(cid, "RND_COVERAGE_DUPLICATE_LENS", lens))
            continue
        seen_lenses[lens] = row
        if state not in COVERAGE_STATES:
            findings.append(Finding(cid, "RND_COVERAGE_STATE_INVALID",
                                    "%s: %r" % (lens or "?", state)))
            continue
        basis = row.get("basis")
        basis = basis if isinstance(basis, list) else []
        missing = [b for b in basis if str(b).strip() not in by_id]
        if missing:
            findings.append(Finding(cid, "RND_COVERAGE_BASIS_DANGLING",
                                    "%s: %s" % (lens, ", ".join(map(str, missing)))))
        if state == "UNKNOWN":
            if basis:
                findings.append(Finding(
                    cid, "RND_COVERAGE_CONTRADICTED",
                    "%s: UNKNOWN with a basis is a contradiction — either the "
                    "evidence supports a state, or the row is honestly unknown"
                    % lens))
        elif not basis:
            findings.append(Finding(
                cid, "RND_COVERAGE_UNEVIDENCED",
                "%s: %s with no basis — a lens without evidence is UNKNOWN, "
                "and UNKNOWN never counts as resolved" % (lens, state)))
        if state in OWNER_BACKED_STATES:
            kinds_in_basis = {str(by_id[str(b).strip()].get("kind", "")).strip()
                              for b in basis if str(b).strip() in by_id}
            if "OWNER_DECISION" not in kinds_in_basis:
                findings.append(Finding(
                    cid, "RND_COVERAGE_OWNER_STATE_UNBACKED",
                    "%s: %s needs at least one OWNER_DECISION item in its basis — "
                    "deferral is an owner act" % (lens, state)))
    for lens in BASELINE_LENSES:
        if lens not in seen_lenses:
            findings.append(Finding(
                cid, "RND_COVERAGE_LENS_MISSING",
                "%s: the row is UNKNOWN when nothing supports it — it is never "
                "omitted, because a model must not call a corpus complete by "
                "failing to imagine the missing category" % lens))

    # --- render freshness ----------------------------------------------
    render_path = compile_dir(corpus, cid) / RENDER_NAME
    if render_path.exists():
        expected = render_coverage(corpus, cid, ir)
        if render_path.read_text(encoding="utf-8") != expected:
            findings.append(Finding(
                cid, "RND_RENDER_STALE",
                "%s no longer matches `render` output — the IR is canonical and "
                "the rendering is regenerated, never edited" % RENDER_NAME))

    summary = {
        "items": len(by_id),
        "by_kind": {k: sum(1 for i in by_id.values()
                           if str(i.get("kind", "")).strip() == k) for k in KINDS},
        "activation_conditions": activation_count,
        "reality_pointers": pointer_count,
        "coverage_rows": len(seen_lenses),
        "sources": len([b for b in sources.values() if not b.excluded]),
        "excluded_sources": len([b for b in sources.values() if b.excluded]),
    }
    return findings, summary


# ------------------------------------------------------------------ audit ---

def parse_audit(text):
    """[{round fields, findings: [...]}] — same append-only round shape as the
    sweep audit, bound to ir_sha256 instead of an inventory revision."""
    rounds = []
    parts = re.split(r"^##\s+AUDIT-(\d+)\s*$", text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        number, body = int(parts[i]), parts[i + 1]
        fields = dict(re.findall(r"^-\s*([a-z_]+):\s*(.*)$", body, re.M))
        entries = []
        chunks = re.split(r"^###\s+(FIND-\d{3,})\s*$", body, flags=re.M)
        for j in range(1, len(chunks) - 1, 2):
            fid, fbody = chunks[j], chunks[j + 1]
            ffields = dict(re.findall(r"^-\s*([a-z_]+):\s*(.*)$", fbody, re.M))
            entries.append({"id": fid, "fields": ffields})
        rounds.append({"number": number, "fields": fields, "findings": entries})
    return rounds


def validate_audit(corpus, compile_id, ir):
    findings = []
    cid = compile_id
    path = compile_dir(corpus, cid) / AUDIT_NAME
    ir_path = compile_dir(corpus, cid) / IR_NAME
    current_sha = sha256_file(ir_path) if ir_path.exists() else ""
    if not path.exists():
        return findings, {"audited": False, "reason": "no %s yet" % AUDIT_NAME}
    text = path.read_text(encoding="utf-8")
    rounds = parse_audit(text)
    if not rounds:
        findings.append(Finding(cid, "RND_AUDIT_MALFORMED",
                                "%s contains no AUDIT-N round" % AUDIT_NAME))
        return findings, {"audited": False, "reason": "malformed"}

    raised = {}
    closed = set()
    for rnd in rounds:
        f = rnd["fields"]
        label = "AUDIT-%d" % rnd["number"]
        scope = f.get("scope", "")
        m = re.search(r"ir_sha256=([0-9a-fA-F]{64})", scope)
        rnd["ir_sha256"] = m.group(1).lower() if m else ""
        if not m:
            findings.append(Finding(cid, "RND_AUDIT_MALFORMED",
                                    "%s: scope names no ir_sha256 — an audit of an "
                                    "unidentified IR audits nothing" % label))
        for key in ("auditor", "audited_at", "verdict"):
            if not f.get(key, "").strip():
                findings.append(Finding(cid, "RND_AUDIT_MALFORMED",
                                        "%s: missing %s" % (label, key)))
        verdict = f.get("verdict", "").strip()
        if verdict == "PASS" and rnd["findings"]:
            findings.append(Finding(cid, "RND_AUDIT_VERDICT_CONTRADICTED",
                                    "%s: PASS over recorded findings" % label))
        own_ids = set()
        for e in rnd["findings"]:
            fid, ff = e["id"], e["fields"]
            own_ids.add(fid)
            if fid in raised:
                findings.append(Finding(cid, "RND_AUDIT_MALFORMED",
                                        "%s: duplicate %s" % (label, fid)))
            raised[fid] = {"round": rnd["number"],
                           "severity": ff.get("severity", "").strip(),
                           "code": ff.get("finding", "").strip()}
            if ff.get("finding", "").strip() not in AUDIT_CODES:
                findings.append(Finding(cid, "RND_AUDIT_CODE_INVALID",
                                        "%s: %r" % (fid, ff.get("finding"))))
            evidence = ff.get("evidence", "").strip()
            if not re.search(r"(RND-\d{3,}|CONV-\d{3,}|EXP-\d{3,}|RQ-\d{3,}|"
                             r"msg\s*\d+|lens\s+[a-z-]+)", evidence):
                findings.append(Finding(
                    cid, "RND_AUDIT_FINDING_UNEVIDENCED",
                    "%s: evidence must address something real — an item id, a "
                    "source, an RQ, a message range or a lens" % fid))
            if ff.get("severity", "").strip() == "material" and \
                    not ff.get("quote", "").strip():
                findings.append(Finding(cid, "RND_AUDIT_FINDING_UNEVIDENCED",
                                        "%s: material findings quote the words "
                                        "they rest on" % fid))
        for closer_key in ("remediated", "dismissed"):
            value = f.get(closer_key, "").strip()
            if not value:
                continue
            for m2 in re.finditer(r"(FIND-\d{3,})(?:\s*\(([^)]+)\))?", value):
                fid, via = m2.group(1), (m2.group(2) or "").strip()
                if fid in own_ids:
                    findings.append(Finding(
                        cid, "RND_AUDIT_FINDING_SELF_CLOSED",
                        "%s closes %s in the round that raised it — raising a "
                        "finding must never be free" % (label, fid)))
                    continue
                if fid not in raised:
                    findings.append(Finding(cid, "RND_AUDIT_MALFORMED",
                                            "%s closes unknown %s" % (label, fid)))
                    continue
                if closer_key == "dismissed":
                    ok = False
                    src = ir.get("source_set") if isinstance(ir, dict) else None
                    if via and RQ_ID_RE.match(via) and isinstance(src, dict) and \
                            src.get("kind") == "project":
                        answers = project_review_queue_owner_answers(
                            corpus, str(src.get("project", "")).strip())
                        # The owner's OWN words must name the finding — an
                        # agent-authored id planted beside a real answer is not
                        # an owner dismissal.
                        ok = fid in answers.get(via, "")
                    if not ok:
                        findings.append(Finding(
                            cid, "RND_AUDIT_DISMISSED_WITHOUT_OWNER",
                            "%s: dismissal of %s cites no owner-answered RQ whose "
                            "answer names it — findings are remediated or they "
                            "stand" % (label, fid)))
                        continue
                closed.add(fid)

    latest = rounds[-1]
    open_material = [fid for fid, meta in raised.items()
                     if meta["severity"] == "material" and fid not in closed]
    audited = (latest.get("ir_sha256") == current_sha and not open_material)
    if latest.get("ir_sha256") and latest["ir_sha256"] != current_sha:
        findings.append(Finding(
            cid, "RND_AUDIT_STALE",
            "latest round audited ir_sha256=%s…, the IR is now %s… — re-audit "
            "the current identity" % (latest["ir_sha256"][:12], current_sha[:12]),
            level="WARN"))
    for fid in open_material:
        findings.append(Finding(cid, "RND_AUDIT_UNREMEDIATED",
                                "%s (material) is neither remediated by a later "
                                "round nor owner-dismissed" % fid))

    # Append-only against git — the one witness outside the writing agent's control.
    rel = str(path.relative_to(Path(corpus)))
    committed = git_head_blob(Path(corpus), rel)
    if committed is not None and not text.startswith(committed.rstrip("\n")):
        findings.append(Finding(cid, "RND_AUDIT_APPEND_ONLY_VIOLATED",
                                "%s differs from its committed prefix" % AUDIT_NAME))
    return findings, {"audited": audited, "open_material": open_material,
                      "rounds": len(rounds)}


# ------------------------------------------------------------------ render --

def render_coverage(corpus, compile_id, ir):
    """Deterministic rendering of the IR's coverage — the RND-COVERAGE.md bytes.

    Same contract as PROJECT.md: a stamped RENDERING, regenerated never edited,
    while the IR stays canonical. Determinism is the point — eval class H deletes
    the derived layer and requires the rebuild to reproduce these bytes exactly.
    """
    ir_path = compile_dir(corpus, compile_id) / IR_NAME
    ir_sha = sha256_file(ir_path) if ir_path.exists() else "?"
    src = ir.get("source_set") if isinstance(ir.get("source_set"), dict) else {}
    items = [i for i in (ir.get("items") or []) if isinstance(i, dict)]
    by_kind = {}
    for i in items:
        k = str(i.get("kind", "?")).strip() or "?"
        by_kind[k] = by_kind.get(k, 0) + 1
    kinds_line = "  ".join("%s=%d" % (k, by_kind.get(k, 0)) for k in KINDS)
    activation = sum(1 for i in items
                     if str(i.get("activation_condition", "")).strip())
    pointers = sum(1 for i in items if i.get("reality_pointer") is not None)
    rows = {str(r.get("lens", "")).strip(): r
            for r in (ir.get("coverage") or []) if isinstance(r, dict)}

    lines = []
    lines.append("# R&D coverage — %s" % (str(ir.get("compile_id", compile_id))))
    lines.append("")
    lines.append("STAMPED RENDERING of `%s` — regenerate with "
                 "`rnd_contract.py render`; never edit, never canonical." % IR_NAME)
    lines.append("")
    lines.append("    IR_SHA256=%s" % ir_sha)
    if src.get("kind") == "project":
        lines.append("    SOURCE_SET=project %s inventory_revision=%s sources=%d"
                     % (src.get("project", "?"), src.get("inventory_revision", "?"),
                        len([s for s in (src.get("sources") or [])
                             if isinstance(s, dict) and not s.get("excluded")])))
    else:
        lines.append("    SOURCE_SET=explicit sources=%d"
                     % len([s for s in (src.get("sources") or [])
                            if isinstance(s, dict) and not s.get("excluded")]))
    lines.append("    ITEMS=%d  (%s)" % (len(items), kinds_line))
    lines.append("    ACTIVATION_CONDITIONS=%d (information only — they activate "
                 "nothing)" % activation)
    lines.append("    REALITY_POINTERS=%d (fresh-at-recompile required)" % pointers)
    lines.append("")
    lines.append("| lens | state | basis |")
    lines.append("|---|---|---|")
    listed = list(BASELINE_LENSES) + sorted(set(rows) - set(BASELINE_LENSES))
    for lens in listed:
        row = rows.get(lens)
        if row is None:
            state, basis = "ROW MISSING — contract violation", ""
        else:
            state = str(row.get("state", "?")).strip()
            basis = ", ".join(str(b).strip() for b in (row.get("basis") or []))
        lines.append("| %s | %s | %s |" % (lens, state, basis))
    lines.append("")
    for standing in STANDING_LINES:
        lines.append("    " + standing)
    lines.append("")
    return "\n".join(lines)


# -------------------------------------------------------------------- CLI ---

def cmd_init(args):
    corpus = corpus_root(args.corpus)
    cid = args.compile
    if not COMPILE_ID_RE.match(cid or ""):
        die_msg = "compile id must match [a-z0-9][a-z0-9-]*"
        print("FAIL: %s" % die_msg)
        return 1
    target = compile_dir(corpus, cid)
    ir_path = target / IR_NAME
    if ir_path.exists():
        print("FAIL: %s exists — a rebuild is an explicit deletion first, never a "
              "silent overwrite" % ir_path)
        return 1

    sources, note = [], ""
    if args.project:
        manifest, err = read_json(Path(corpus) / "_projects" / args.project
                                  / "project-manifest.json")
        if err or not isinstance(manifest, dict):
            print("FAIL: project %r: manifest %s" % (args.project, err or "invalid"))
            return 1
        kind = "project"
        excluded = 0
        for s in manifest.get("sources") or []:
            if not isinstance(s, dict):
                continue
            revisions = [r for r in (s.get("revisions") or []) if isinstance(r, dict)]
            sid = str(s.get("source_id", "")).strip()
            if not revisions:
                sources.append({"source_id": sid,
                                "excluded": "no captured revision — a gap, "
                                            "recorded rather than hidden"})
                excluded += 1
                continue
            last = revisions[-1]
            rec = {"source_id": sid,
                   "revision": last.get("revision"),
                   "path": str(last.get("path", "")).strip(),
                   "source_sha256": str(last.get("source_sha256", "")).strip()}
            if not rec["source_sha256"]:
                # legacy revision — recompute from bytes, exactly as capture does
                p = Path(corpus) / rec["path"]
                if p.exists():
                    rec["source_sha256"] = transcript_source_sha256(
                        p.read_text(encoding="utf-8"))
            sources.append(rec)
        source_set = {
            "kind": kind, "project": args.project,
            "inventory_revision": manifest.get("inventory_revision"),
            "inventory_sha256": manifest.get("inventory_sha256"),
            "sources": sources,
        }
        if excluded:
            note = "EXCLUDED_SOURCES=%d (uncaptured — visible, not absorbed)" % excluded
    elif args.source:
        for idx, rel in enumerate(args.source):
            p = Path(corpus) / rel
            if not p.exists():
                print("FAIL: explicit source %s does not exist under the corpus"
                      % rel)
                return 1
            sources.append({
                "source_id": "EXP-%03d" % (idx + 1), "path": rel,
                "source_sha256": transcript_source_sha256(
                    p.read_text(encoding="utf-8")),
            })
        source_set = {"kind": "explicit", "sources": sources}
    else:
        print("FAIL: bind a source set — --project <name> or --source <path> "
              "(repeatable); RND_COMPILE consumes already-captured material only")
        return 1

    ir = {
        "rnd_ir_version": IR_VERSION,
        "compile_id": cid,
        "title": args.title or cid,
        "created": args.at or "",
        "mode": "RND_COMPILE",
        "derived_layer": True,
        "execution_authority": "none",
        "source_set": source_set,
        "items": [],
        "coverage": [{"lens": lens, "state": "UNKNOWN", "basis": [], "note": ""}
                     for lens in BASELINE_LENSES],
    }
    target.mkdir(parents=True, exist_ok=True)
    write_json(ir_path, ir)
    print("initialized %s" % ir_path)
    print("SOURCES_BOUND=%d" % len([s for s in sources if not s.get("excluded")]))
    if note:
        print(note)
    print("all %d coverage lenses start UNKNOWN — evidence moves them, "
          "silence never does" % len(BASELINE_LENSES))
    print("next: derive items into %s, then `validate --compile %s`"
          % (IR_NAME, cid))
    return 0


def cmd_validate(args):
    corpus = corpus_root(args.corpus)
    compiles = [args.compile] if args.compile else list_compiles(corpus)
    if not compiles:
        print("FAIL: no compiles found under %s — is the corpus path right?"
              % rnd_root(corpus))
        return 1
    findings = []
    for cid in compiles:
        f, _ = validate_compile(corpus, cid)
        findings.extend(f)
        ir, _ = load_ir(corpus, cid)
        if ir is not None:
            af, meta = validate_audit(corpus, cid, ir)
            findings.extend(af)
            print("RND_COMPILE_AUDITED=%s  [%s]%s"
                  % ("YES" if meta.get("audited") else "NO", cid,
                     "" if meta.get("audited") else "  (%s)"
                     % (", ".join(meta.get("open_material") or [])
                        or meta.get("reason", "audit not at current identity"))))
    return report(findings, "rnd validate",
                  quiet_pass="every compile holds its contract")


def cmd_coverage(args):
    corpus = corpus_root(args.corpus)
    ir, findings = load_ir(corpus, args.compile)
    if ir is None:
        return report(findings, "rnd coverage")
    vfind, summary = validate_compile(corpus, args.compile)
    print(render_coverage(corpus, args.compile, ir))
    if summary:
        print("EXCLUDED_SOURCES=%d" % summary["excluded_sources"])
    hard = fails(vfind)
    print("RND_COMPILE_VALID=%s" % ("YES" if not hard else "NO"))
    if hard:
        for f in hard:
            print(f)
    return 1 if hard else 0


def cmd_render(args):
    corpus = corpus_root(args.corpus)
    ir, findings = load_ir(corpus, args.compile)
    if ir is None:
        return report(findings, "rnd render")
    text = render_coverage(corpus, args.compile, ir)
    if args.write:
        out = compile_dir(corpus, args.compile) / RENDER_NAME
        out.write_text(text, encoding="utf-8")
        print("wrote %s (deterministic — rerunning render reproduces it exactly)"
              % out)
    else:
        print(text)
    return 0


def cmd_audit(args):
    corpus = corpus_root(args.corpus)
    ir, findings = load_ir(corpus, args.compile)
    if ir is None:
        return report(findings, "rnd audit")
    af, meta = validate_audit(corpus, args.compile, ir)
    print("RND_COMPILE_AUDITED=%s" % ("YES" if meta.get("audited") else "NO"))
    if meta.get("open_material"):
        print("OPEN_MATERIAL=%s" % ",".join(meta["open_material"]))
    return report(findings + af, "rnd audit",
                  quiet_pass="audit discipline holds")


def cmd_status(args):
    corpus = corpus_root(args.corpus)
    ir, findings = load_ir(corpus, args.compile)
    if ir is None:
        return report(findings, "rnd status")
    vfind, summary = validate_compile(corpus, args.compile)
    af, meta = validate_audit(corpus, args.compile, ir)
    src = ir.get("source_set") if isinstance(ir.get("source_set"), dict) else {}
    print("COMPILE=%s" % args.compile)
    print("SOURCE_SET=%s%s" % (src.get("kind", "?"),
                               " project=%s inventory_revision=%s"
                               % (src.get("project"), src.get("inventory_revision"))
                               if src.get("kind") == "project" else ""))
    if summary:
        print("ITEMS=%d  %s" % (summary["items"],
                                "  ".join("%s=%d" % (k, summary["by_kind"][k])
                                          for k in KINDS)))
        print("ACTIVATION_CONDITIONS=%d (information only)"
              % summary["activation_conditions"])
        print("REALITY_POINTERS=%d (fresh-at-recompile required)"
              % summary["reality_pointers"])
    print("RND_COMPILE_VALID=%s" % ("YES" if not fails(vfind) else "NO"))
    print("RND_COMPILE_AUDITED=%s" % ("YES" if meta.get("audited") else "NO"))
    for standing in STANDING_LINES:
        print(standing)
    return 1 if fails(vfind + af) else 0


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", help="corpus root (default: "
                        "$NORTROPIC_INTAKE_CORPUS or ~/nortropic/innovation-intake)")
    top = argparse.ArgumentParser(
        prog="rnd_contract.py",
        description="RND_COMPILE: derived R&D layer — typed items, coverage lens, "
                    "compile audit. Reads the corpus; writes only _rnd/<compile>/. "
                    "No plans, no approvals, no lifecycle, no pointers — those "
                    "commands do not exist here, on purpose.")
    sub = top.add_subparsers(dest="command")

    p = sub.add_parser("init", parents=[common],
                       help="bind a compile to an already-captured source set")
    p.add_argument("--compile", required=True)
    p.add_argument("--project", help="bind a PROJECT_SWEEP corpus by name")
    p.add_argument("--source", action="append",
                   help="corpus-relative transcript path (repeatable) for an "
                        "explicit source set")
    p.add_argument("--title")
    p.add_argument("--at", help="YYYY-MM-DD")

    p = sub.add_parser("validate", parents=[common],
                       help="falsify one compile, or every compile")
    p.add_argument("--compile")

    for name, helptext in (("coverage", "coverage lens + standing laws"),
                           ("render", "deterministic RND-COVERAGE.md"),
                           ("audit", "compile-audit discipline"),
                           ("status", "one-screen summary")):
        p = sub.add_parser(name, parents=[common], help=helptext)
        p.add_argument("--compile", required=True)
        if name == "render":
            p.add_argument("--write", action="store_true")

    args = top.parse_args(argv)
    if not args.command:
        top.print_help()
        return 2
    return {"init": cmd_init, "validate": cmd_validate, "coverage": cmd_coverage,
            "render": cmd_render, "audit": cmd_audit,
            "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
