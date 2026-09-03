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
    Finding, corpus_root, fails, git_head_blob, git_immutability,
    read_json, report, sha256_file, sha256_text, transcript_source_region,
    transcript_source_sha256, write_json, ROLE_ASSISTANT, ROLE_OWNER,
    ROLE_UNKNOWN, TRANSCRIPT_HEADER_RE,
    _OWNER_ROLE_RE, _ASSISTANT_ROLE_RE,
)

IR_VERSION = 1
# v4.1 — the SEMANTIC COVERAGE obligations. Strictly ADDITIVE and VERSIONED: an
# `rnd_ir_version: 1` compile validates under exactly the v4.0 rules it was published
# against (the r38 witness stays green and reproducible), and `rnd_ir_version: 2`
# carries every v4.0 rule PLUS the obligations below. Nothing is removed, no closed
# vocabulary is widened, no guard is weakened — so a compile that passes v4.1 also
# passes v4.0, and a semantic PASS can never be bought by relaxing the contract.
#
# These exist because an external SOURCE->IR falsification (improvements r38) showed
# the v4.0 contract green (0 FAIL, 0 WARN) over a compile with 619 MATERIAL semantic
# omissions. Reproduced mechanically: the six items that thirty-one audit rounds were
# fought to ADD could be deleted again and validate still reported green. v4.0
# validates STRUCTURE and PROVENANCE INTEGRITY; it never asks whether the compile
# UNDERSTOOD the corpus. Each rule below turns one of those blind spots into a
# question the compile must answer in the file itself.
IR_VERSION_SEMANTIC = 2
SUPPORTED_IR_VERSIONS = (IR_VERSION, IR_VERSION_SEMANTIC)
IR_NAME = "rnd-ir.json"
RENDER_NAME = "RND-COVERAGE.md"
AUDIT_NAME = "compile-audit.md"
RND_DIRNAME = "_rnd"

COMPILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
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

# v4.1 --- OWNER AUTHORITY BASIS (root cause C) -------------------------------
# `authority_class` has three values and every OWNER_DECISION carries the same one,
# so the field cannot distinguish an owner who WORDED a decision from an owner who
# assented to text the assistant wrote. In r38 that left free-text caveats as the only
# guard: 57 of 76 OWNER_DECISIONs needed one. A caveat a machine cannot read is not a
# guard. AUTHORITY_CLASSES is NOT widened — this is a second, orthogonal axis:
# authority_class says WHOSE authority, owner_authority_basis says HOW it was acquired.
#   CLAIM ABOUT OWNER != OWNER CLAIM.  OWNER-LABELLED MESSAGE != OWNER-AUTHORED CONTENT.
OWNER_AUTHORITY_BASES = (
    "owner-authored",                   # the decision content is in the owner's own words
    "owner-directive",                  # owner sent the work a direction; content authored elsewhere
    "owner-adoption-of-assistant-text",  # owner adopted text the assistant wrote
    "owner-attestation",                # owner confirmed a fact, not a design
    "owner-answered-rq",                # via an owner_answer in the review queue
    "contested",                        # the cited source does not settle it
)

# v4.1 --- STANDING (root cause B) --------------------------------------------
# NEGATIVE KNOWLEDGE. The r38 corpus held 296 rejection findings (~17 owner-voiced) and
# the IR names NOT-BUILDING twice as a required output, then leaves the slot empty —
# because there was nowhere to put it. `disposition` is forbidden vocabulary (rightly:
# it is Recompile's verdict word and a backlog would hide there), so the natural word
# was banned while an arbitrary unenforced field passed. That is the worst of both
# worlds. `standing` is the sanctioned home: it is EPISTEMIC state in the corpus, never
# work state, it orders nothing, and it is evidenced like any other claim.
# Purpose: a later Recompile must not rediscover a killed idea as a live requirement.
STANDINGS = ("PROPOSAL", "REJECTED", "DEFERRED", "SUPERSEDED",
             "HISTORICAL", "CURRENT_CANDIDATE")

# v4.1 --- OWNER TURN LEDGER (root cause A) -----------------------------------
# DENSITY, without an importance score that could be Goodharted. Byte volume must not
# decide semantic preservation: r38 compressed near-uniformly per KB (0.032 vs 0.029
# items/KB) while blind semantic density ran 4x higher in the strategic sources, so a
# short owner reversal lost to a long debugging thread. The obligation is therefore
# tied to a MATERIAL DISTINCTION that can be counted without ranking anything: the
# owner's own turns. Every owner-role turn is either carried by an item's provenance
# or explicitly accounted for here. No turn is weighted; each is present or explained.
OWNER_TURN_REASONS = (
    "pasted-machine-output",    # the turn is agent/terminal output, not owner prose
    "interface-submission",     # a form/checkbox submission, no owner prose
    "acknowledgement-only",     # "ok", "tack" — carries no content
    "question-only",            # a question that settles nothing
    "duplicate-restatement",    # verbatim repeat of a turn already carried
    "no-material-content",      # read in full; carries no material distinction
)

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

# INTAKE != BACKLOG, enforced at the vocabulary level: no key ANYWHERE in an IR may
# carry a priority/score/lifecycle/disposition WORD as one of its segments, so there
# is no field for a backlog to hide in. An idea mentioned twenty times is one item
# with twenty provenance entries, never a heavier one.
#
# Matched by EXACT SEGMENT (word + plural/inflection), over both `_`/`-`/space AND
# camelCase boundaries. Two independent reviews shaped this: the first showed an
# exact-KEY set let `priority_level`/`urgency_class`/`priorities` through, and a naive
# stem-PREFIX fix then (a) still missed camelCase `lovabilityScore`/`itemRank` and
# (b) over-fired on innocent words that merely START with a stem (`plane`, `plant`,
# `planning_notes`, `taskonomy`). Exact-segment over camelCase-split keys catches the
# real ordering/lifecycle fields in any casing and leaves innocent compounds alone.
# The cleverly-disguised ordering (a field named to dodge the vocabulary) is the
# compile audit's job — RND_BACKLOG_LAUNDERING — not the key guard's.
_FORBIDDEN_SEGMENTS = {}
for _word, _code in (
    # prioritization / ranking / frequency-recency weighting
    ("priority", "RND_PRIORITIZATION_FORBIDDEN"),
    ("priorities", "RND_PRIORITIZATION_FORBIDDEN"),
    ("prioritization", "RND_PRIORITIZATION_FORBIDDEN"),
    ("prioritisation", "RND_PRIORITIZATION_FORBIDDEN"),
    ("importance", "RND_PRIORITIZATION_FORBIDDEN"),
    ("prioritize", "RND_PRIORITIZATION_FORBIDDEN"),
    ("prioritise", "RND_PRIORITIZATION_FORBIDDEN"),
    # common estimation/scoring proxies an independent review flagged as bypasses
    ("impact", "RND_PRIORITIZATION_FORBIDDEN"),
    ("effort", "RND_PRIORITIZATION_FORBIDDEN"),
    ("severity", "RND_PRIORITIZATION_FORBIDDEN"),
    ("tier", "RND_PRIORITIZATION_FORBIDDEN"),
    ("rank", "RND_PRIORITIZATION_FORBIDDEN"),
    ("ranks", "RND_PRIORITIZATION_FORBIDDEN"),
    ("ranking", "RND_PRIORITIZATION_FORBIDDEN"),
    ("rankings", "RND_PRIORITIZATION_FORBIDDEN"),
    ("weight", "RND_PRIORITIZATION_FORBIDDEN"),
    ("weights", "RND_PRIORITIZATION_FORBIDDEN"),
    ("weighting", "RND_PRIORITIZATION_FORBIDDEN"),
    ("urgency", "RND_PRIORITIZATION_FORBIDDEN"),
    ("frequency", "RND_PRIORITIZATION_FORBIDDEN"),
    ("frequencies", "RND_PRIORITIZATION_FORBIDDEN"),
    ("recency", "RND_PRIORITIZATION_FORBIDDEN"),
    # score
    ("score", "RND_SCORE_FORBIDDEN"),
    ("scores", "RND_SCORE_FORBIDDEN"),
    ("scoring", "RND_SCORE_FORBIDDEN"),
    # lifecycle / work
    ("status", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("task", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("tasks", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("plan", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("plans", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("backlog", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("backlogs", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("milestone", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("milestones", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("deadline", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("deadlines", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("sprint", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("sprints", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("roadmap", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("implement", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    ("implementation", "RND_LIFECYCLE_FIELD_FORBIDDEN"),
    # disposition (Recompile's verdict vocabulary)
    ("disposition", "RND_DISPOSITION_FORBIDDEN"),
    ("dispositions", "RND_DISPOSITION_FORBIDDEN"),
):
    _FORBIDDEN_SEGMENTS[_word] = _code

_CAMEL_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_SEGMENT_SPLIT_RE = re.compile(r"[_\-\s]+")


def _key_segments(key):
    s = _CAMEL_2.sub(r"\1 \2", _CAMEL_1.sub(r"\1 \2", str(key)))
    return [seg for seg in _SEGMENT_SPLIT_RE.split(s.lower()) if seg]


_SIBILANT_END_RE = re.compile(r"(?:s|x|z|ch|sh)$")


def _lemmas(seg):
    """The segment plus its light inflectional variants, so the forbidden set can be
    the BASE words and still catch plurals/gerunds/participles. Two independent
    reviews shaped this: the first found a hardcoded plural list missed `importances`/
    `statuses`/`weightings`; the second found `-ed`/`-ized` participles (`ranked`,
    `weighted`, `prioritized`) slipped through and that a blunt `-es` strip collapsed
    `planes`->`plan`. Cheap, deterministic, no NLP: strip common English suffixes,
    guarding `-es` to sibilant stems so `planes`/`cutting_planes` are left alone."""
    forms = {seg}
    if seg.endswith("ies") and len(seg) > 4:      # priorities -> priority
        forms.add(seg[:-3] + "y")
    if seg.endswith("es") and len(seg) > 3:       # statuses -> status (sibilant only)
        base = seg[:-2]
        if _SIBILANT_END_RE.search(base):
            forms.add(base)
    if seg.endswith("s") and len(seg) > 2:        # ranks -> rank; planes -> plane
        forms.add(seg[:-1])
    if seg.endswith("ing") and len(seg) > 5:      # weighting -> weight; scoring -> score
        forms.add(seg[:-3])
        forms.add(seg[:-3] + "e")
    if seg.endswith("ed") and len(seg) > 4:       # ranked -> rank; scored -> score
        forms.add(seg[:-2])
        forms.add(seg[:-1])
    if seg.endswith("ized") and len(seg) > 6:     # prioritized -> prioritize
        forms.add(seg[:-1])
        forms.add(seg[:-4])
    if seg.endswith("ised") and len(seg) > 6:     # prioritised -> prioritise
        forms.add(seg[:-1])
        forms.add(seg[:-4])
    return forms


def _forbidden_key(key):
    """(code, matched-segment) if any segment of `key` — or a light inflection of it —
    IS a forbidden base word (across `_`/`-`/space and camelCase boundaries), else
    (None, None)."""
    for seg in _key_segments(key):
        for form in _lemmas(seg):
            code = _FORBIDDEN_SEGMENTS.get(form)
            if code:
                return code, seg
    return None, None

# Referenced, never copied: the IR points into the corpus and must not become a
# second copy of it. Caps are generous for a claim and tight for a quote.
CLAIM_MAX = 1000
QUOTE_MAX = 500
# An RQ-backed OWNER_DECISION must quote a SUBSTANTIAL run of the owner's answer, not
# a stray letter — the floor that closes the single-character substring bypass.
_QUOTE_MIN_CHARS = 16
_QUOTE_MIN_WORDS = 3

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


# --------------------------------------------------- genuine message roles --

# A genuine message header OPENS a message block: it sits at the very start of the
# source region, or the non-blank line immediately before it is a horizontal-rule
# separator (`---`/`***`/`___`) — which is exactly how the capture pipeline frames
# every turn. An `## Meddelande N — <roll>` line sitting INSIDE a message body is
# not a block opener, and an independent review proved why this matters: without
# this anchor, a header pasted into an assistant turn's body mints a phantom owner
# turn out of assistant/external text, and OWNER_DECISION would trust it. The shared
# `parse_transcript_roles` (used by v3 too) stays untouched; this is a stricter,
# v4-local reading laid over the owner-authority surface RND_COMPILE adds.
_SEPARATOR_RE = re.compile(r"(?:-{3,}|\*{3,}|_{3,})\Z")
# v4.1: a bare, conservative signal that a cited range rests on something EXTERNAL.
# Deliberately narrow — a link is unambiguous evidence, where a capitalised word is not.
_URL_RE = re.compile(r"https?://[^\s)\]>\"']+")


def _opens_block(region, start):
    before = region[:start].rstrip()
    if not before:
        return True                       # the region's first header
    last_line = before.rsplit("\n", 1)[-1].strip()
    return bool(_SEPARATOR_RE.fullmatch(last_line))


def genuine_message_roles(region):
    """({message number: role}, well_formed) over BLOCK-OPENING headers only.

    well_formed is False when the block-opening headers do not number a contiguous
    1..N — a shape the owner-authority gate treats as fail-closed, since an
    out-of-sequence header is exactly what an injected one produces.
    """
    roles = {}
    numbers = []
    for m in TRANSCRIPT_HEADER_RE.finditer(region):
        if not _opens_block(region, m.start()):
            continue
        n = int(m.group(1))
        numbers.append(n)
        label = m.group(2)
        is_owner = bool(_OWNER_ROLE_RE.search(label))
        is_assistant = bool(_ASSISTANT_ROLE_RE.search(label))
        if is_owner == is_assistant:
            role = ROLE_UNKNOWN
        else:
            role = ROLE_OWNER if is_owner else ROLE_ASSISTANT
        if n in roles and roles[n] != role:
            roles[n] = ROLE_UNKNOWN
        else:
            roles[n] = role
    well_formed = numbers == list(range(1, len(numbers) + 1))
    return roles, well_formed


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
        self.base = Path(corpus).resolve()
        self.source_id = str(rec.get("source_id", "")).strip()
        self.rel = str(rec.get("path", "")).strip()
        self.path = Path(corpus) / self.rel
        self.recorded_sha = str(rec.get("source_sha256", "")).strip().lower()
        self.excluded = str(rec.get("excluded", "")).strip()
        # An independent oracle for the header-injection residual: the count the
        # capture recorded for this revision, cross-checked against the genuine
        # block-opening headers parsed from the bytes.
        self.recorded_count = rec.get("message_count")
        self._text = None
        self._roles = None
        self._well_formed = None
        self._count = None
        self._texts = None

    def read(self):
        if self._text is None:
            self._text = self.path.read_text(encoding="utf-8")
        return self._text

    def _within_corpus(self):
        try:
            self.path.resolve().relative_to(self.base)
            return True
        except ValueError:
            return False

    def verify(self, compile_id, findings):
        """Raw evidence survives synthesis — checked, not assumed."""
        if self.excluded:
            return False
        # A bound source must live INSIDE the corpus. An independent review showed a
        # manifest/IR `path` with `../` binds an external file as an authoritative
        # source at validate time — the same escape the CLI now blocks, on the path
        # actually consumed.
        if Path(self.rel).is_absolute() or not self._within_corpus():
            findings.append(Finding(
                compile_id, "RND_SOURCE_PATH_ESCAPES",
                "%s: path %r resolves outside the corpus root — a compile binds "
                "only captured material under the corpus" % (self.source_id,
                                                             self.rel)))
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
        # Genuine block-opening headers must number what the capture recorded — a
        # transcript carrying MORE headers than turns has an injected one.
        if isinstance(self.recorded_count, int) and self.recorded_count >= 0 \
                and self.message_count() != self.recorded_count:
            findings.append(Finding(
                compile_id, "RND_SOURCE_MESSAGE_COUNT_MISMATCH",
                "%s: %d block-opening message headers on disk, but the capture "
                "recorded %d turns — an extra header is what an injected owner "
                "turn produces" % (self.source_id, self.message_count(),
                                   self.recorded_count)))
            return False
        return True

    def _parse(self):
        if self._roles is None:
            region, found = transcript_source_region(self.read())
            if not found:
                self._roles, self._well_formed, self._count = {}, False, 0
            else:
                self._roles, self._well_formed = genuine_message_roles(region)
                self._count = len(self._roles)

    def message_texts(self):
        """{message number: body text} over BLOCK-OPENING headers only.

        v4.1 needs the owner's actual WORDS, not just the role, to tell an owner who
        worded a decision from an owner who assented to assistant text. Reuses the
        same block-opening anchor as `genuine_message_roles`, so a header pasted into
        a body cannot mint a phantom owner turn's text any more than it can mint the
        role.
        """
        if self._texts is None:
            region, _found = transcript_source_region(self.read())
            opens = [m for m in TRANSCRIPT_HEADER_RE.finditer(region)
                     if _opens_block(region, m.start())]
            texts = {}
            for i, m in enumerate(opens):
                end = opens[i + 1].start() if i + 1 < len(opens) else len(region)
                texts[int(m.group(1))] = region[m.end():end]
            self._texts = texts
        return self._texts

    def roles(self):
        self._parse()
        return self._roles

    def well_formed(self):
        self._parse()
        return self._well_formed

    def message_count(self):
        self._parse()
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


# The derived layer, matched anywhere in a normalized relative path. A source that
# resolves through `_rnd/` is agent-authored output, never captured input.
_RND_PATH_RE = re.compile(r"(?:^|/)%s(?:/|$)" % re.escape(RND_DIRNAME))


def _manifest_witness(manifest):
    """{source_id: {path, sha256, message_count}} from the LATEST revision of each
    manifest source — the authoritative, swept record a compile's sources must match.

    The anchor is the manifest's `sha256` (the WHOLE captured file), which every real
    manifest revision carries and the sweep computed at capture. An independent review
    caught an earlier version reading a `source_sha256` field the real manifests do
    not write, and comparing incompatible hash types — so the sha dimension silently
    never fired. `sha256_file(bound path)` is compared to THIS value, which binds the
    bound bytes to the sweep's own record rather than to the IR's self-report.
    """
    out = {}
    for s in (manifest.get("sources") or []):
        if not isinstance(s, dict):
            continue
        sid = str(s.get("source_id", "")).strip()
        revs = [r for r in (s.get("revisions") or []) if isinstance(r, dict)]
        if not sid or not revs:
            continue
        last = revs[-1]
        out[sid] = {
            "path": str(last.get("path", "")).strip(),
            "sha256": str(last.get("sha256", "")).strip().lower(),
            "message_count": last.get("message_count"),
        }
    return out


def project_review_queue_owner_answers(corpus, project):
    """{RQ id: owner_answer text} for entries that carry the owner's exact words.

    The caller validates `project` against PROJECT_RE first, so this path can only
    ever resolve inside `_projects/<slug>/` — the IR cannot steer it elsewhere.
    """
    answers = {}
    if not PROJECT_RE.match(project or ""):
        return answers
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

def _norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


_MESSAGES = {
    "RND_DISPOSITION_FORBIDDEN":
        "%s: %r opens a disposition stem — KEEP/ADAPT/MERGE/… is Recompile's "
        "verdict against fresh repo reality, never Intake's",
    "RND_SCORE_FORBIDDEN":
        "%s: %r opens a score stem — no single-number reduction; lovability and "
        "its relatives are diagnostic signals, not a score",
    "RND_PRIORITIZATION_FORBIDDEN":
        "%s: %r opens a priority stem — INTAKE != BACKLOG, and frequency/recency/"
        "importance carry no weight here",
    "RND_LIFECYCLE_FIELD_FORBIDDEN":
        "%s: %r opens a lifecycle stem — a compile never holds lifecycle, tasks "
        "or plans",
}
# A pure priority TOKEN encoded into a free-text list value — the tags-as-backlog
# smell an independent review flagged. Kept narrow so a real tag like
# "ranking-algorithms" or "24/7" is untouched: only a bare rank token (`P0`, `p3`),
# a `key:number` micro-record, or a `#<n>` position is refused as an ordering
# smuggled past the key guard. Ratios like `24/7` and `1/2` are NOT rank tokens.
_PRIORITY_TOKEN_RE = re.compile(
    r"^(?:p\d+|prio(?:rity)?\s*[:=-]?\s*\d+|rank\s*[:=-]?\s*\d+|#\d+)$", re.I)


def scan_forbidden_keys(node, path, findings, compile_id, in_tags=False):
    """No field exists for a backlog to hide in — recursively, by STEM PREFIX on
    every key segment, plus a narrow check for a rank token smuggled into a tags
    list value."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = "%s.%s" % (path, key)
            code, stem = _forbidden_key(key)
            if code:
                findings.append(Finding(compile_id, code,
                                        _MESSAGES[code] % (here, str(key))))
            scan_forbidden_keys(value, here, findings, compile_id,
                                in_tags=str(key).strip().lower() == "tags")
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            scan_forbidden_keys(value, "%s[%d]" % (path, idx), findings,
                                compile_id, in_tags=in_tags)
    elif in_tags and isinstance(node, str) and _PRIORITY_TOKEN_RE.match(node.strip()):
        findings.append(Finding(
            compile_id, "RND_PRIORITIZATION_FORBIDDEN",
            "%s: tag %r is a bare rank token — a de-facto ordering encoded in a "
            "free-text field is still a backlog" % (path, node.strip())))


# --------------------------------------------------------------- git witness --

def _quote_in_assistant_turn(qn, sources):
    """True when the normalised quote sits verbatim inside any ASSISTANT turn of any
    bound, verified source. Cheap and decidable: it answers "were these words already
    said by the assistant?", never the undecidable "did the owner mean them?"."""
    for b in sources.values():
        if b.excluded or not b.path.exists():
            continue
        try:
            if not b.well_formed():
                continue
            roles = b.roles()
            texts = b.message_texts()
        except Exception:
            continue
        for n, role in roles.items():
            if role == ROLE_ASSISTANT and qn in _norm(texts.get(n, "")):
                return True
    return False


def _report_git_witness(corpus, src, sources, findings, cid):
    """Anchor the compile's evidence base to git — the one witness an editing agent
    does not control — and return ABSENT | PARTIAL | PRESENT.

    The evidence base is: every bound source file, plus (project mode) the manifest
    and the review-queue that owner_answers are read from. A file committed and then
    changed is tampering (FAIL). A file never committed contributes to a PARTIAL/
    ABSENT witness — a legitimate fresh run, reported not blocked, exactly as
    SINGLE/PROJECT_SWEEP report `immutability witness ABSENT|PARTIAL|PRESENT`.
    Owner authority asserted over an unwitnessed evidence base is honestly labelled
    as such: RND_OWNER_PROVENANCE_UNWITNESSED (WARN), because bytes an agent can
    still author are not yet the committed swept record.
    """
    corpus = Path(corpus)
    rels = []
    for b in sources.values():
        if not b.excluded and b.rel:
            rels.append(b.rel)
    project = str(src.get("project", "")).strip() if isinstance(src, dict) else ""
    if src.get("kind") == "project" and PROJECT_RE.match(project or ""):
        rels.append("_projects/%s/project-manifest.json" % project)
        rq = corpus / "_projects" / project / "review-queue.md"
        if rq.exists():
            rels.append("_projects/%s/review-queue.md" % project)
    committed = tracked = 0
    for rel in rels:
        state, detail = git_immutability(corpus, rel, corpus / rel)
        if state == "MUTATED":
            findings.append(Finding(
                cid, "RND_EVIDENCE_MUTATED",
                "%s differs from its committed version — the git witness caught a "
                "post-commit change to the compile's evidence base" % rel))
            tracked += 1
        elif state == "UNCHANGED":
            committed += 1
            tracked += 1
        # UNTRACKED: not yet committed — counts toward a non-PRESENT witness
    if not rels:
        return "ABSENT"
    if committed == len(rels):
        return "PRESENT"
    state = "PARTIAL" if tracked else "ABSENT"
    # The evidence base is not fully git-witnessed; say so once, plainly — never
    # silently treat asserted owner authority as witnessed. Any OWNER_DECISION in
    # this compile rests on bytes an agent could still author until commit.
    findings.append(Finding(
        cid, "RND_EVIDENCE_BASE_UNWITNESSED",
        "the evidence base is git-witnessed %s (%d/%d committed) — any owner "
        "provenance rests on bytes an agent could still author until the corpus is "
        "committed; commit it to witness the compile" % (state, committed, len(rels)),
        level="WARN"))
    return state


# ------------------------------------------------------------- validation ---

def validate_compile(corpus, compile_id):
    ir, findings = load_ir(corpus, compile_id)
    if ir is None:
        return findings, None
    cid = compile_id

    ir_version = ir.get("rnd_ir_version")
    if ir_version not in SUPPORTED_IR_VERSIONS:
        findings.append(Finding(cid, "RND_IR_VERSION_UNSUPPORTED",
                                "rnd_ir_version=%r; this contract supports %s"
                                % (ir_version, ", ".join(map(str,
                                                            SUPPORTED_IR_VERSIONS)))))
    # v4.1 obligations apply only to a compile that declares itself version 2. A
    # version-1 compile is validated by exactly the rules it was published against,
    # so an already-published witness stays green and byte-reproducible; the newer
    # rules are opt-in per compile and never retroactive.
    semantic = (ir_version == IR_VERSION_SEMANTIC)
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
        # The derived layer is OUTPUT, never INPUT. A source path under `_rnd/` is
        # an agent-writable file masquerading as captured evidence — an independent
        # review minted a phantom owner turn exactly this way. The compile consumes
        # only already-captured material, never its own products.
        if not b.excluded and _RND_PATH_RE.search(b.rel.replace("\\", "/")):
            findings.append(Finding(
                cid, "RND_SOURCE_IN_DERIVED_LAYER",
                "%s binds %r under the derived layer _rnd/ — the compile consumes "
                "captured evidence, never its own output" % (sid, b.rel)))

    if str(src.get("kind", "")) == "project":
        project = str(src.get("project", "")).strip()
        # The project is a corpus-relative SLUG, re-validated HERE (not only at init):
        # an independent review read this raw field at validate time and traversed to
        # an agent-writable review-queue (`../_rnd/…`) to launder an owner decision.
        if not PROJECT_RE.match(project):
            findings.append(Finding(
                cid, "RND_SOURCE_SET_INVALID",
                "project-bound source_set names %r, which is not a project slug — "
                "the review queue and manifest are read from _projects/<slug>/, "
                "never a path the IR can steer outside it" % project))
        else:
            rq_answers = project_review_queue_owner_answers(corpus, project)
            manifest, err = read_json(Path(corpus) / "_projects" / project
                                      / "project-manifest.json")
            if err or not isinstance(manifest, dict):
                # A project compile whose manifest cannot be read cannot witness its
                # sources at all — unverifiable, not merely stale.
                findings.append(Finding(cid, "RND_SOURCE_SET_INVALID",
                                        "bound project %r: manifest %s — sources "
                                        "cannot be witnessed" % (project,
                                                                 err or "invalid")))
            else:
                rev = manifest.get("inventory_revision")
                sha = str(manifest.get("inventory_sha256", "")).strip()
                # A proof is about the set that existed when it was measured: a
                # project that has since grown makes the compile STALE (recompile
                # against the new revision), never invalid.
                if (rev != src.get("inventory_revision")
                        or (sha and sha != str(src.get("inventory_sha256", "")).strip())):
                    findings.append(Finding(
                        cid, "RND_SOURCE_SET_STALE",
                        "bound at inventory_revision=%s, project is at %s — the "
                        "compile describes the set it measured; recompile to "
                        "describe today's" % (src.get("inventory_revision"), rev),
                        level="WARN"))
                # Every bound source must be WITNESSED by the manifest: same
                # source_id, same path, and the bound bytes' WHOLE-FILE sha256 equal
                # to the manifest's recorded `sha256` for that revision. This binds
                # the bound bytes to the sweep's own record, not to the IR's
                # self-report. The count oracle likewise reads from the manifest.
                witness = _manifest_witness(manifest)
                for sid, b in sources.items():
                    if b.excluded:
                        continue
                    w = witness.get(sid)
                    if w is None:
                        findings.append(Finding(
                            cid, "RND_SOURCE_NOT_WITNESSED",
                            "%s is not a source the project manifest witnesses — a "
                            "compile reads only swept, captured conversations" % sid))
                        continue
                    if b.rel != w["path"]:
                        findings.append(Finding(
                            cid, "RND_SOURCE_NOT_WITNESSED",
                            "%s: bound path %r is not the manifest revision path %r"
                            % (sid, b.rel, w["path"])))
                    elif w["sha256"] and b.path.exists() and \
                            sha256_file(b.path) != w["sha256"]:
                        findings.append(Finding(
                            cid, "RND_SOURCE_NOT_WITNESSED",
                            "%s: bound bytes do not hash to the manifest's recorded "
                            "capture (sha256) — not the witnessed conversation" % sid))
                    elif not w["sha256"] and not isinstance(w["message_count"], int):
                        # Neither independent binding is present: the manifest
                        # revision records no `sha256` AND no `message_count`, so the
                        # whole-file anchor and the count oracle both silently no-op.
                        # An independent review flagged this same silent-skip class;
                        # report it (WARN) rather than let a witness quietly bind
                        # nothing. Real sweeps always write sha256, so this fires
                        # only on a malformed/legacy manifest — recorded, not blocked.
                        findings.append(Finding(
                            cid, "RND_SOURCE_WITNESS_INCOMPLETE",
                            "%s: the manifest revision records neither sha256 nor "
                            "message_count — nothing independent binds these bytes to "
                            "the sweep; re-capture or re-sweep to witness them" % sid,
                            level="WARN"))
                    # Trust the manifest's recorded count, not the IR's self-report.
                    if isinstance(w["message_count"], int):
                        b.recorded_count = w["message_count"]

    for b in sources.values():
        b.verify(cid, findings)

    # --- git witness: the one record an editing agent does not control -----
    # Every immutability guarantee in this skill anchors to git, because a hash a
    # file records about itself proves only self-consistency. An independent review
    # showed a compile's owner provenance could be forged by an agent that authored
    # the review-queue or a source in the working tree — the same write access the
    # sweep uses. So validate reports the witness state and refuses post-commit
    # tampering, exactly as SINGLE/PROJECT_SWEEP do; an uncommitted corpus is a
    # legitimate fresh run, reported (not blocked) as ABSENT/PARTIAL.
    witness_state = _report_git_witness(corpus, src, sources, findings, cid)

    # --- items ----------------------------------------------------------
    items = ir.get("items")
    if not isinstance(items, list):
        findings.append(Finding(cid, "RND_IR_MALFORMED", "items must be a list"))
        items = []
    by_id = {}
    owner_backed = set()
    activation_count = 0
    standings_seen = {}
    cited_owner_msgs = {}
    owner_authored_unquoted = set()
    evidence_gap_items = []
    cited_external = set()
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

        # --- v4.1 owner_authority_basis (root cause C) ----------------------
        basis = str(item.get("owner_authority_basis", "")).strip()
        if semantic:
            if kind == "OWNER_DECISION":
                if not basis:
                    findings.append(Finding(
                        cid, "RND_OWNER_BASIS_MISSING",
                        "%s: an OWNER_DECISION states HOW the owner's authority was "
                        "acquired — free text is not a machine-readable guard, and "
                        "'the owner decided it' is the claim under test" % iid))
                elif basis not in OWNER_AUTHORITY_BASES:
                    findings.append(Finding(
                        cid, "RND_OWNER_BASIS_INVALID",
                        "%s: owner_authority_basis %r is not one of %s"
                        % (iid, basis, ", ".join(OWNER_AUTHORITY_BASES))))
            elif basis:
                findings.append(Finding(
                    cid, "RND_OWNER_BASIS_MISPLACED",
                    "%s: %s carries owner_authority_basis — the basis for owner "
                    "authority exists only where owner authority does" % (iid, kind)))

        # --- v4.1 standing (root cause B) -----------------------------------
        standing = str(item.get("standing", "")).strip()
        if semantic and standing:
            if standing not in STANDINGS:
                findings.append(Finding(
                    cid, "RND_STANDING_INVALID",
                    "%s: standing %r is not one of %s — this is epistemic state in "
                    "the corpus, never work state"
                    % (iid, standing, ", ".join(STANDINGS))))
            else:
                standings_seen[iid] = standing

        # --- v4.1 evidence_refs integrity (root cause E) ---------------------
        refs = item.get("evidence_refs")
        if semantic and refs is not None:
            if not isinstance(refs, list):
                findings.append(Finding(cid, "RND_EVIDENCE_REF_INVALID",
                                        "%s: evidence_refs is not a list" % iid))
            else:
                for ref in refs:
                    if not isinstance(ref, dict) or \
                            not str(ref.get("name", "")).strip():
                        findings.append(Finding(
                            cid, "RND_EVIDENCE_REF_INVALID",
                            "%s: every evidence_ref names the entity it retains"
                            % iid))

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
        owner_specific = False   # a targeted owner-decision finding already fired
        item_quote = str(item.get("quote", "")).strip()
        item_owner_text = []     # v4.1: the owner's own words in the cited ranges
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
                    if kind == "OWNER_DECISION":
                        # One answered RQ is not a blank cheque for any claim: the
                        # decision must QUOTE a SUBSTANTIAL run of the owner's own
                        # words from that very answer — an independent review showed
                        # a single letter ("is", "e") satisfied a bare substring
                        # test and laundered an unrelated fabricated decision. The
                        # quote proves the owner SAID it; whether the derived claim
                        # faithfully reflects those words is the compile audit's
                        # job (RND_OWNER_PROVENANCE_LAUNDERED / RND_SECOND_TRUTH),
                        # exactly as for a message-cited owner turn — the two owner
                        # paths are deliberately symmetric.
                        qn = _norm(item_quote)
                        if (len(qn) >= _QUOTE_MIN_CHARS
                                and len(qn.split()) >= _QUOTE_MIN_WORDS
                                and qn in _norm(rq_answers[rq])):
                            roles_seen.add(ROLE_OWNER)
                        else:
                            findings.append(Finding(
                                cid, "RND_OWNER_DECISION_RQ_UNSUPPORTED",
                                "%s: an OWNER_DECISION backed by %s must `quote` a "
                                "substantial run (>=%d chars, >=%d words) of the "
                                "owner's OWN answer — an answered RQ backs the "
                                "decision it answers, never an unrelated claim "
                                "pinned beside a stray letter"
                                % (iid, rq, _QUOTE_MIN_CHARS, _QUOTE_MIN_WORDS)))
                            owner_specific = True
                    else:
                        roles_seen.add(ROLE_OWNER)   # owner words as evidence
                continue
            sid = str(p.get("source_id", "")).strip()
            b = sources.get(sid)
            if b is None or b.excluded:
                findings.append(Finding(cid, "RND_PROVENANCE_UNBOUND",
                                        "%s cites %r, which the source set does "
                                        "not bind" % (iid, sid or "?")))
                continue
            # A source whose path escapes the corpus, is missing, whose bytes no
            # longer hash to the bound identity, or whose header count disagrees
            # with the capture, resolves NOTHING and grants no role — its per-source
            # finding is already recorded once by verify(). Never read or trust
            # out-of-corpus or tampered bytes here.
            if (Path(b.rel).is_absolute() or not b._within_corpus()
                    or not b.path.exists()
                    or (b.recorded_sha
                        and transcript_source_sha256(b.read()) != b.recorded_sha)
                    or (isinstance(b.recorded_count, int)
                        and b.message_count() != b.recorded_count)):
                continue
            spec = p.get("messages")
            if spec is None:
                resolved_any = True     # whole-source citation grants NO role
                continue
            rng = parse_msg_range(spec)
            count = b.message_count()
            if rng is None or rng[1] > count:
                findings.append(Finding(
                    cid, "RND_PROVENANCE_OUT_OF_RANGE",
                    "%s cites %s msg %s of a %d-message capture — an unreachable "
                    "citation is what an invented claim (or an injected header) "
                    "produces" % (iid, sid, spec, count)))
                continue
            resolved_any = True
            if not b.well_formed():
                # Block-opening headers that do not number 1..N mean the transcript
                # was tampered/injected: no role from it is trustworthy.
                roles_seen.add(ROLE_UNKNOWN)
                continue
            roles = b.roles()
            for n in range(rng[0], rng[1] + 1):
                r = roles.get(n, ROLE_UNKNOWN)
                roles_seen.add(r)
                if r == ROLE_OWNER and semantic:
                    # v4.1: an owner turn a compile CITES is a turn it accounted for.
                    cited_owner_msgs.setdefault(sid, set()).add(n)
                    item_owner_text.append(b.message_texts().get(n, ""))
            if semantic and str(item.get("authority_class", "")).strip() == \
                    "evidence" and _URL_RE.search(
                        "".join(b.message_texts().get(n, "")
                                for n in range(rng[0], rng[1] + 1))):
                cited_external.add(iid)
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
            elif owner_specific:
                pass                      # a targeted finding already fired
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
            # v4.1 (root cause C): `owner-authored` is the strongest basis a decision
            # can claim — it asserts the CONTENT is in the owner's own words. It is
            # therefore the one basis a machine can falsify: the item's quote must sit
            # inside an owner TURN, not merely inside an owner-cited RANGE. An owner
            # turn that pastes an agent report is owner-labelled, not owner-authored,
            # and this is what separates them.
            if semantic and basis == "owner-authored":
                qn = _norm(item_quote)
                joined = _norm(" ".join(item_owner_text))
                if not qn:
                    findings.append(Finding(
                        cid, "RND_OWNER_AUTHORED_UNQUOTED",
                        "%s: owner_authority_basis 'owner-authored' carries no quote "
                        "— the owner's own words are the evidence for the claim that "
                        "they are the owner's own words" % iid))
                elif joined and qn in joined and _quote_in_assistant_turn(
                        qn, sources):
                    # The decisive case the r38 review found: CONV-012 msg 1 is an
                    # owner-LABELLED turn whose 7,126 content characters are verbatim
                    # an earlier ASSISTANT turn the owner pasted back. Both blind
                    # slots read it as owner voice. Text the owner relayed is text
                    # the owner adopted, never text the owner authored — and unlike
                    # "did he mean it", that is decidable: the same words are sitting
                    # in an assistant turn of a bound source.
                    findings.append(Finding(
                        cid, "RND_OWNER_AUTHORED_IS_RELAYED",
                        "%s: the quote also appears verbatim in an ASSISTANT turn of "
                        "a bound source — an owner-labelled message that relays "
                        "assistant text is 'owner-adoption-of-assistant-text', not "
                        "'owner-authored'" % iid))
                elif not joined or qn not in joined:
                    findings.append(Finding(
                        cid, "RND_OWNER_AUTHORED_UNSUPPORTED",
                        "%s: the quote is not inside an owner TURN of its cited "
                        "ranges — an owner-labelled message that pastes machine "
                        "output is not owner-authored content; the honest basis is "
                        "'owner-directive', 'owner-adoption-of-assistant-text' or "
                        "'contested'" % iid))

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

    # --- v4.1 semantic coverage obligations ------------------------------
    # Each block below turns one measured blind spot into a question the IR must
    # answer in the file. None of them ranks anything, and none of them can be
    # satisfied by copying raw: every one is a DISTINCTION the compile must account
    # for, not a volume it must reproduce.
    if semantic:
        # (B) standing: SUPERSEDED is a relation, not an adjective. An item may not
        # simply declare itself replaced — something must replace it, or a later
        # Recompile cannot tell what is live.
        for iid, standing in standings_seen.items():
            if standing == "SUPERSEDED" and not any(
                    str(r.get("rel", "")).strip() == "supersedes"
                    and str(r.get("target", "")).strip() == iid
                    for other in by_id.values()
                    for r in (other.get("relations") or [])
                    if isinstance(r, dict)):
                findings.append(Finding(
                    cid, "RND_STANDING_UNSUPPORTED",
                    "%s: standing SUPERSEDED with nothing superseding it — record "
                    "the item that replaced it, or the corpus cannot say what is "
                    "live" % iid))

        # (A) the owner-turn ledger — density without an importance score.
        ledger = ir.get("owner_turn_ledger")
        if not isinstance(ledger, list):
            findings.append(Finding(
                cid, "RND_OWNER_LEDGER_MISSING",
                "a version-2 compile accounts for every owner turn in every bound "
                "source: carried by an item's provenance, or listed here with a "
                "reason. Byte volume must not decide what survives — the owner's "
                "own turns are the distinction that does"))
        else:
            declared = {}
            for e in ledger:
                if not isinstance(e, dict):
                    findings.append(Finding(cid, "RND_OWNER_LEDGER_INVALID",
                                            "ledger entry is not an object"))
                    continue
                lsid = str(e.get("source_id", "")).strip()
                reason = str(e.get("reason", "")).strip()
                rng = parse_msg_range(e.get("messages"))
                if lsid not in sources or sources[lsid].excluded:
                    findings.append(Finding(
                        cid, "RND_OWNER_LEDGER_INVALID",
                        "ledger cites %r, which the source set does not bind"
                        % (lsid or "?")))
                    continue
                if rng is None:
                    findings.append(Finding(
                        cid, "RND_OWNER_LEDGER_INVALID",
                        "%s: ledger entry has no message range" % lsid))
                    continue
                if reason not in OWNER_TURN_REASONS:
                    findings.append(Finding(
                        cid, "RND_OWNER_LEDGER_REASON_INVALID",
                        "%s msg %s: %r is not one of %s — 'unimportant' is not a "
                        "reason a corpus may give for dropping the owner's voice"
                        % (lsid, e.get("messages"), reason,
                           ", ".join(OWNER_TURN_REASONS))))
                    continue
                for n in range(rng[0], rng[1] + 1):
                    declared.setdefault(lsid, set()).add(n)
            for sid, b in sorted(sources.items()):
                if b.excluded or not b.path.exists() or not b.well_formed():
                    continue
                owner_turns = {n for n, r in b.roles().items() if r == ROLE_OWNER}
                unaccounted = sorted(owner_turns
                                     - cited_owner_msgs.get(sid, set())
                                     - declared.get(sid, set()))
                if unaccounted:
                    shown = ", ".join(map(str, unaccounted[:12]))
                    findings.append(Finding(
                        cid, "RND_OWNER_TURN_UNACCOUNTED",
                        "%s: %d owner turn(s) neither cited by any item nor declared "
                        "in the ledger (msg %s%s) — silence about the owner's own "
                        "words is the one silence a compile may not keep"
                        % (sid, len(unaccounted), shown,
                           ", …" if len(unaccounted) > 12 else "")))

        # (F) lens blindness — the instrument must be able to report its own
        # category blindness. Known lenses are scaffolding, never a definition of
        # what the world is allowed to contain.
        unlensed = ir.get("unlensed")
        if not isinstance(unlensed, list):
            findings.append(Finding(
                cid, "RND_UNLENSED_DECLARATION_MISSING",
                "a version-2 compile answers, explicitly, which material "
                "distinctions fit NONE of the known lenses — an empty list is a "
                "valid answer, an absent field is a question never asked"))
            unlensed = []
        in_basis = set()
        for row in coverage:
            if isinstance(row, dict):
                for bref in (row.get("basis") or []):
                    in_basis.add(str(bref).strip())
        declared_unlensed = set()
        for u in unlensed:
            if not isinstance(u, dict) or not str(u.get("distinction", "")).strip():
                findings.append(Finding(cid, "RND_UNLENSED_INVALID",
                                        "every unlensed entry names its distinction"))
                continue
            for ref in (u.get("items") or []):
                declared_unlensed.add(str(ref).strip())
        orphans = sorted(set(by_id) - in_basis - declared_unlensed)
        if orphans:
            findings.append(Finding(
                cid, "RND_ITEM_UNLENSED_UNDECLARED",
                "%d item(s) sit in no lens basis and are not declared unlensed "
                "(%s%s) — an item the coverage instrument cannot see is an item the "
                "instrument cannot report as missing"
                % (len(orphans), ", ".join(orphans[:12]),
                   ", …" if len(orphans) > 12 else "")))

        # (D) progression — EXACT SOURCE RANGE != FINAL SEMANTIC STATE. A compile may
        # not classify a claim as current having read only the passage that states it;
        # the correction five messages later is in the same conversation.
        prog = ir.get("progression")
        prog_map = {}
        if not isinstance(prog, list):
            findings.append(Finding(
                cid, "RND_PROGRESSION_MISSING",
                "a version-2 compile records, per bound source, how far it read "
                "before fixing semantic state — a range that stops before the "
                "refutation leaves the refuted position standing"))
        else:
            for e in prog:
                if isinstance(e, dict):
                    prog_map[str(e.get("source_id", "")).strip()] = \
                        e.get("examined_through")
            for sid, b in sorted(sources.items()):
                if b.excluded or not b.path.exists():
                    continue
                total = b.message_count()
                seen_through = prog_map.get(sid)
                if not isinstance(seen_through, int):
                    findings.append(Finding(
                        cid, "RND_PROGRESSION_MISSING",
                        "%s: no examined_through — the compile cannot say it checked "
                        "for a later correction it never looked for" % sid))
                elif seen_through < total:
                    findings.append(Finding(
                        cid, "RND_PROGRESSION_INCOMPLETE",
                        "%s: examined_through=%d of %d messages — the remainder may "
                        "correct, reverse or supersede what the cited ranges say"
                        % (sid, seen_through, total)))

        # (E) evidence behind a surviving conclusion. Narrow on purpose: only an
        # `evidence` item whose cited range demonstrably rests on an external link.
        for iid in sorted(cited_external):
            if not (by_id.get(iid, {}).get("evidence_refs") or []):
                findings.append(Finding(
                    cid, "RND_EVIDENCE_DISCARDED",
                    "%s: an evidence item whose cited range carries an external "
                    "reference retains none — a conclusion that outlives the evidence "
                    "for it cannot be falsified, re-researched or reproduced" % iid))

        # (G) cross-source synthesis: allowed, DERIVED, and provenance-bound.
        xs = ir.get("cross_source")
        if xs is not None:
            if not isinstance(xs, list):
                findings.append(Finding(cid, "RND_CROSS_SOURCE_INVALID",
                                        "cross_source is not a list"))
                xs = []
            for x in xs:
                if not isinstance(x, dict):
                    findings.append(Finding(cid, "RND_CROSS_SOURCE_INVALID",
                                            "cross_source entry is not an object"))
                    continue
                xid = str(x.get("id", "")).strip() or "?"
                if str(x.get("authority_class", "")).strip() == "owner" or \
                        str(x.get("owner_authority_basis", "")).strip():
                    findings.append(Finding(
                        cid, "RND_CROSS_SOURCE_AUTHORITY",
                        "%s: a cross-source synthesis is DERIVED — meaning that "
                        "emerges between conversations was authored by no one, least "
                        "of all the owner" % xid))
                srcs = {str(pp.get("source_id", "")).strip()
                        for pp in (x.get("provenance") or [])
                        if isinstance(pp, dict)}
                unbound = sorted(t for t in srcs
                                 if t and (t not in sources or sources[t].excluded))
                if unbound:
                    findings.append(Finding(
                        cid, "RND_CROSS_SOURCE_UNBOUND",
                        "%s cites %s, which the source set does not bind"
                        % (xid, ", ".join(unbound))))
                elif len([t for t in srcs if t]) < 2:
                    findings.append(Finding(
                        cid, "RND_CROSS_SOURCE_SINGLE_SOURCE",
                        "%s: a cross-source meaning cites at least two sources — one "
                        "source is a source finding, not a synthesis" % xid))

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
        "git_witness": witness_state,
        "source_set_kind": str(src.get("kind", "")).strip() or "?",
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
        # A project name is a corpus-relative slug, never a path — an independent
        # review showed `--project ../evilproj` binding a manifest outside the
        # corpus. Same discipline as the compile id.
        if not PROJECT_RE.match(args.project or ""):
            print("FAIL: --project %r is not a project slug — a compile binds a "
                  "swept project by name, never by path" % args.project)
            return 1
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
            mc = last.get("message_count")
            if isinstance(mc, int):
                rec["message_count"] = mc
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
        base = Path(corpus).resolve()
        for idx, rel in enumerate(args.source):
            # already-captured material only: an explicit source must live INSIDE
            # the corpus. Reject absolute paths and any `..`/symlink that resolves
            # outside — an independent review showed both bound uncaptured,
            # unswept, unverified external files as authoritative sources.
            if Path(rel).is_absolute():
                print("FAIL: --source %s is absolute — a compile consumes "
                      "already-captured material inside the corpus, never an "
                      "arbitrary path" % rel)
                return 1
            resolved = (base / rel).resolve()
            try:
                rel_norm = resolved.relative_to(base)
            except ValueError:
                print("FAIL: --source %s escapes the corpus root (%s) — a compile "
                      "binds only captured material under the corpus" % (rel, base))
                return 1
            if _RND_PATH_RE.search(str(rel_norm).replace("\\", "/")):
                print("FAIL: --source %s is under the derived layer _rnd/ — the "
                      "compile consumes captured evidence, never its own output"
                      % rel)
                return 1
            if not resolved.exists():
                print("FAIL: explicit source %s does not exist under the corpus"
                      % rel)
                return 1
            text = resolved.read_text(encoding="utf-8")
            region, found = transcript_source_region(text)
            _roles, _ = genuine_message_roles(region) if found else ({}, False)
            sources.append({
                "source_id": "EXP-%03d" % (idx + 1), "path": str(rel_norm),
                "source_sha256": transcript_source_sha256(text),
                "message_count": len(_roles),
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
        print("RND_IMMUTABILITY_WITNESS=%s" % summary.get("git_witness", "?"))
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
    if summary:
        print("RND_IMMUTABILITY_WITNESS=%s (evidence base git-anchored; ABSENT/"
              "PARTIAL = uncommitted fresh run)" % summary.get("git_witness", "?"))
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
