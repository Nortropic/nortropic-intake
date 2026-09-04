#!/usr/bin/env python3
"""v4.3 suite — the six distinctions r38 paid for, each made mechanically refusable.

Every case here is a real defect that actually occurred during the Improvements r38
qualification campaign, not a hypothetical. The campaign ran eight adjudications and
seven recovery rematches to establish them; this file exists so the next one costs a
test run instead.

    CASE A  absent primary carrier + derived observation + no epistemic limit  -> FAIL
    CASE B  the same representation with a truthful limit                      -> PASS
    CASE C  externally readable, bytes unheld: readable YES, capture still NO
    CASE D  owner uploaded it; the content was authored elsewhere              -> FAIL
    CASE E  a derived observation preserves meaning, never falsifiability
    CASE F  "independent reviewers" with no stable identity: UNVERIFIED, not TRUE/FALSE
    CASE G  every new branch is demonstrably activatable

A green suite whose new branch never activates is not evidence, so the activation
report at the bottom fails the suite if any rule it claims to test never fired.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))


def _import_or_fail():
    """A stubbed module exits 0 during import and would take this suite green with it."""
    try:
        import attachment_surface as _att
        import intake_common as _ic
    except SystemExit:
        print("FAIL  a module under test exited during import — it is stubbed or broken, "
              "so this suite ran nothing and must not exit 0")
        raise SystemExit(1)
    for mod, names in ((_att, ("validate_manifest", "REDUNDANCY_DIMENSIONS",
                               "SUPPORTED_ATTACHMENT_MANIFEST_VERSIONS")),
                       (_ic, ("semantically_readable", "attachment_bytes_available",
                              "full_source_capture", "SEMANTIC_ACCESSIBILITY_STATES",
                              "VERIFICATION_STATES", "RECOVERY_EXHAUSTION_STATES"))):
        missing = [n for n in names if not hasattr(mod, n)]
        if missing:
            print("FAIL  %s is missing %s — an inert module certifies nothing"
                  % (getattr(mod, "__name__", mod), missing))
            raise SystemExit(1)
    return _att, _ic


att, _ic = _import_or_fail()
semantically_readable = _ic.semantically_readable
attachment_bytes_available = _ic.attachment_bytes_available
full_source_capture = _ic.full_source_capture

PASSED, FAILED, ACTIVATION = [], [], {}
MIN_CHECKS = 30


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print("%s %s%s" % ("PASS" if ok else "FAIL", name,
                       "" if ok else "\n      " + str(detail)[:800]))


def activates(rule, findings, name, expect=True):
    codes = [f.code for f in findings]
    hit = rule in codes
    ACTIVATION.setdefault(rule, 0)
    if hit:
        ACTIVATION[rule] += 1
    check(name, hit is expect,
          "codes=%s expected %s %s" % (codes, rule, "present" if expect else "absent"))


def row(aid, status, **kw):
    r = {"attachment_id": aid, "ordinal": int(aid.rsplit("-", 1)[1]),
         "capture_status": status, "materiality": "MATERIAL"}
    r.update(kw)
    return r


def man(rows, version=2, **kw):
    d = {"attachment_manifest_version": version, "source_id": "CONV-001", "revision": 1,
         "reconciliation": "AGREE", "declared_count": len(rows), "attachments": rows}
    d.update(kw)
    return d


def vm(d, corpus=None):
    return att.validate_manifest(d, "CONV-001", 1, "fixture", corpus)


# ================= CASE C — readable is not captured ==========================
print("\n--- CASE C: semantic access and byte capture are different axes ---")

check("C1  SOURCE_BOUND_READABLE_EXTERNAL reads as readable",
      semantically_readable("SOURCE_BOUND_READABLE_EXTERNAL") is True)
check("C2  …and is NOT bytes in hand",
      attachment_bytes_available("CAPTURED_REFERENCE_ONLY") is False)
check("C3  a readable-but-unheld MATERIAL attachment still forces FULL_SOURCE_CAPTURE=NO",
      full_source_capture(
          [row("ATT-001-001", "CAPTURED_REFERENCE_ONLY",
               semantic_accessibility="SOURCE_BOUND_READABLE_EXTERNAL",
               byte_identity="NOT_ESTABLISHED")], "AGREE", 1) == "NO",
      "this is the exact r38 CONV-007 shape: fully readable, bytes never exported")
check("C4  REFERENCE_ONLY and UNAVAILABLE are not readable",
      not semantically_readable("REFERENCE_ONLY")
      and not semantically_readable("UNAVAILABLE"))

activates("ATTACHMENT_SEMANTIC_ACCESS_MISUSED",
          vm(man([row("ATT-001-001", "RECOVERED_EXACT", content_sha256="a" * 64,
                      recovery_provenance="x",
                      semantic_accessibility="SOURCE_BOUND_READABLE_EXTERNAL")])),
          "C5  claiming bytes AND readable-without-bytes at once is refused")
activates("ATTACHMENT_SEMANTIC_ACCESS_MISUSED",
          vm(man([row("ATT-001-001", "CAPTURED_REFERENCE_ONLY",
                      semantic_accessibility="SOURCE_BOUND_READABLE_EXTERNAL",
                      byte_identity="ESTABLISHED")])),
          "C6  reading a source never establishes its historical byte identity")
activates("ATTACHMENT_SEMANTIC_ACCESS_MISSING",
          vm(man([row("ATT-001-001", "UNAVAILABLE")])),
          "C7  a v2 manifest must say whether a bytes-less source is still readable")
activates("ATTACHMENT_SEMANTIC_ACCESS_MISSING",
          vm(man([row("ATT-001-001", "UNAVAILABLE")], version=1)),
          "C8  CONTROL: a v1 manifest is not retroactively obliged", expect=False)
activates("ATTACHMENT_SEMANTIC_ACCESS_INVALID",
          vm(man([row("ATT-001-001", "UNAVAILABLE",
                      semantic_accessibility="MOSTLY_READABLE")])),
          "C9  an invented accessibility state is refused")

# ================= CASE E — redundancy preserves meaning, not evidence ========
print("\n--- CASE E: semantic redundancy is not primary-evidence preservation ---")

base = dict(semantic_accessibility="UNAVAILABLE", byte_identity="NOT_ESTABLISHED")
activates("ATTACHMENT_REDUNDANCY_ESCAPE_OVERREACHES",
          vm(man([row("ATT-001-001", "UNAVAILABLE", redundancy_escape={
              "dimensions_protected": ["PRIMARY_FALSIFIABILITY"],
              "basis": "a contemporaneous assistant observation describes it"}, **base)])),
          "E1  a derived observation may not close PRIMARY_FALSIFIABILITY unadjudicated")
activates("ATTACHMENT_REDUNDANCY_ESCAPE_OVERREACHES",
          vm(man([row("ATT-001-001", "UNAVAILABLE", redundancy_escape={
              "dimensions_protected": ["AUTHORSHIP_VISIBLE_ONLY_IN_PRIMARY"],
              "basis": "the turn is owner-labelled"}, **base)])),
          "E2  …nor AUTHORSHIP_VISIBLE_ONLY_IN_PRIMARY — the r38 CONV-001 msg-61 shape")
activates("ATTACHMENT_REDUNDANCY_ESCAPE_OVERREACHES",
          vm(man([row("ATT-001-001", "UNAVAILABLE", redundancy_escape={
              "dimensions_protected": ["EXACT_VISUAL_STRUCTURE"],
              "basis": "msg 23 describes the diagram",
              "adjudication_record": "adj-001 BAF-CONV-001-A-007: rejected"}, **base)])),
          "E3  CONTROL: an evidentiary dimension WITH an adjudication record is accepted",
          expect=False)
activates("ATTACHMENT_REDUNDANCY_ESCAPE_OVERREACHES",
          vm(man([row("ATT-001-001", "UNAVAILABLE", redundancy_escape={
              "dimensions_protected": ["CONCEPTUAL_MEANING"],
              "basis": "the frozen body carries the concept verbatim"}, **base)])),
          "E4  CONTROL: CONCEPTUAL_MEANING alone needs no adjudication", expect=False)
activates("ATTACHMENT_REDUNDANCY_ESCAPE_INVALID",
          vm(man([row("ATT-001-001", "UNAVAILABLE",
                      redundancy_escape={"basis": "it is covered elsewhere"}, **base)])),
          "E5  an escape naming no dimension cannot be checked and is refused")
check("E6  redundancy never buys capture",
      full_source_capture([row("ATT-001-001", "UNAVAILABLE", redundancy_escape={
          "dimensions_protected": ["CONCEPTUAL_MEANING"]}, **base)], "AGREE", 1) == "NO")

# ================= recovery exhaustion is earned ==============================
print("\n--- recovery exhaustion is a claim about the SEARCH, never the source ---")

REX_OK = {"state": "KNOWN_IRRECOVERABLE_IN_CURRENT_HISTORICAL_SURFACE",
          "source_existence_established": "owner msgs 13/22/61/77 carry attachment payloads",
          "surfaces_searched": ["File Library targeted recovery, six bridges"],
          "basis": ["all 55 manifest rows carry original_filename=null",
                    "no discriminating fingerprint remains"]}
activates("ATTACHMENT_RECOVERY_EXHAUSTION_UNPROVEN",
          vm(man([row("ATT-001-001", "UNAVAILABLE", **base)],
                 recovery_exhaustion={"state": "KNOWN_IRRECOVERABLE_IN_CURRENT_HISTORICAL_SURFACE"})),
          "X1  declaring irrecoverable without a basis is refused")
activates("ATTACHMENT_RECOVERY_EXHAUSTION_UNPROVEN",
          vm(man([row("ATT-001-001", "UNAVAILABLE", **base)], recovery_exhaustion=REX_OK)),
          "X2  CONTROL: an earned exhaustion record is accepted", expect=False)
activates("ATTACHMENT_RECOVERY_EXHAUSTION_OVERREACHES",
          vm(man([row("ATT-001-001", "UNAVAILABLE", **base)],
                 recovery_exhaustion=dict(REX_OK, source_never_existed=True))),
          "X3  exhausting a search never establishes the source did not exist")
check("X4  exhaustion does not convert UNAVAILABLE into captured",
      full_source_capture([row("ATT-001-001", "UNAVAILABLE", **base)], "AGREE", 1) == "NO")

# Backward compatibility at the attachment layer, mirroring V1 at the IR layer: the
# r38 manifests are v1 and must keep validating under exactly the rules they were
# written against, or this hardening would have rewritten history rather than added to it.
_v1 = vm(man([row("ATT-001-001", "CAPTURED_CONTENT", content_sha256="a" * 64)], version=1))
check("X5  a v1 manifest with none of the new fields still validates clean",
      _v1 == [], [f.code for f in _v1])

# ================= CASES A / B / D / F — the IR side =========================
print("\n--- CASES A/B/D/F: the IR contract ---")
from test_rnd_v4 import mk_corpus, run  # noqa: E402
from test_rnd_v41 import v2_ir  # noqa: E402
import re  # noqa: E402


def ir3(corpus, cid, mutate=None):
    def _m(ir):
        ir["rnd_ir_version"] = 3
        if mutate:
            mutate(ir)
    return v2_ir(corpus, cid, mutate=_m)


def expect_code(corpus, cid, code, name, present=True, mutate=None):
    ir3(corpus, cid, mutate=mutate)
    rc, out = run(corpus, "validate")
    hit = bool(re.search(r"^\s*(?:FAIL|WARN)\s+\[%s\]\s+%s\b"
                         % (re.escape(cid), re.escape(code)), out, re.M))
    ACTIVATION.setdefault(code, 0)
    if hit:
        ACTIVATION[code] += 1
    check(name, hit is present,
          "rc=%d %s %s for [%s]\n%s" % (rc, code, "missing" if present else "present", cid,
                                        "\n".join(l for l in out.splitlines()
                                                  if "[%s]" % cid in l)[:700]))


def absent_ref(ir, unc="high — the carrier is gone", limit=None):
    for it in ir["items"]:
        if it["id"] == "RND-001":
            it["evidence_refs"] = [{
                "name": "the night log the owner pasted, whose bytes were never captured",
                "source_id": "CONV-001", "messages": "1",
                "attachment_id": "ATT-001-001",
                "attachment_capture": "UNAVAILABLE",
                "source_evidence_absent": True}]
            it["uncertainty"] = unc
            it["authority_class"] = "derived"
            if limit is not None:
                it["epistemic_limit"] = limit


with tempfile.TemporaryDirectory() as td:
    corpus = mk_corpus(Path(td))

    # CASE A — the exact r38 RND-025 defect
    expect_code(corpus, "case-a", "RND_EPISTEMIC_LIMIT_MISSING",
                "A1  absent carrier + derived observation + no epistemic limit is refused",
                mutate=lambda ir: absent_ref(ir))

    # CASE B — the same representation, told truthfully
    LIMIT = {"primary_carrier_availability": "UNAVAILABLE — attachment chip, bytes never captured",
             "observation_provenance": "contemporaneous assistant observation of the historical "
                                       "primary source, same turn",
             "primary_source_falsifiability": "UNAVAILABLE",
             "unverified": ["whether the ordering is the log's or the assistant's reconstruction"],
             "actor_independence_verification": "UNVERIFIED"}
    expect_code(corpus, "case-b", "RND_EPISTEMIC_LIMIT_MISSING",
                "B1  CONTROL: the same claim WITH a truthful limit is accepted",
                present=False, mutate=lambda ir: absent_ref(ir, limit=LIMIT))
    expect_code(corpus, "case-b2", "RND_EPISTEMIC_LIMIT_INCOMPLETE",
                "B2  a limit missing primary_source_falsifiability is refused",
                mutate=lambda ir: absent_ref(ir, limit={
                    "primary_carrier_availability": "UNAVAILABLE"}))

    # CASE F — UNVERIFIED must be representable without forcing TRUE/FALSE
    expect_code(corpus, "case-f", "RND_VERIFICATION_STATE_INVALID",
                "F1  a verification field outside VERIFIED/UNVERIFIED/REFUTED is refused",
                mutate=lambda ir: absent_ref(ir, limit=dict(
                    LIMIT, actor_independence_verification="PROBABLY_INDEPENDENT")))
    expect_code(corpus, "case-f2", "RND_VERIFICATION_STATE_INVALID",
                "F2  CONTROL: UNVERIFIED is accepted — it is the positive answer",
                present=False, mutate=lambda ir: absent_ref(ir, limit=LIMIT))

    # CASE D — owner upload is not owner authorship
    def owner_upload(ir, author="OWNER"):
        ir["owner_turn_ledger"] = [{"source_id": "CONV-002", "messages": "1",
                                    "reason": "duplicate-restatement",
                                    "attachment_dependency": True,
                                    "attachment_content_author": author}]
    expect_code(corpus, "case-d", "RND_OWNER_UPLOAD_TREATED_AS_AUTHORSHIP",
                "D1  an owner turn's attachment content may not be typed OWNER",
                mutate=lambda ir: owner_upload(ir, "OWNER"))
    expect_code(corpus, "case-d2", "RND_OWNER_UPLOAD_TREATED_AS_AUTHORSHIP",
                "D2  CONTROL: UNVERIFIED authorship is accepted",
                present=False, mutate=lambda ir: owner_upload(ir, "UNVERIFIED"))
    expect_code(corpus, "case-d3", "RND_OWNER_UPLOAD_TREATED_AS_AUTHORSHIP",
                "D3  CONTROL: SEPARATELY_SOURCED is accepted",
                present=False, mutate=lambda ir: owner_upload(ir, "SEPARATELY_SOURCED"))

    # backwards compatibility — the whole point of the version boundary
    expect_code(corpus, "compat-v2", "RND_EPISTEMIC_LIMIT_MISSING",
                "V1  a version-2 compile is NOT bound by the v3 obligation",
                present=False,
                mutate=lambda ir: (ir.__setitem__("rnd_ir_version", 2), absent_ref(ir))[0])

# ================= CASE G — activation report ================================
print("\n" + "=" * 72)
print("CASE G — ACTIVATION REPORT: a branch that never fires is not evidence")
print("=" * 72)
dead = [r for r, n in ACTIVATION.items() if n == 0]
for rule in sorted(ACTIVATION):
    print("  %-46s activated %d time(s)%s"
          % (rule, ACTIVATION[rule], "   <-- NEVER FIRED" if ACTIVATION[rule] == 0 else ""))
check("G1  every rule this suite claims to test actually fired", not dead,
      "never activated: %s" % dead)

print()
print("SCOPE: structural and provenance properties only. No static validator decides "
      "whether a derived observation preserved a meaning — where that judgement is "
      "needed the contract demands an adjudication record instead of guessing.")
print()
print("%d passed, %d failed, %d checks total"
      % (len(PASSED), len(FAILED), len(PASSED) + len(FAILED)))
if len(PASSED) + len(FAILED) < MIN_CHECKS:
    print("SUITE UNDER-RAN: %d < floor %d" % (len(PASSED) + len(FAILED), MIN_CHECKS))
    sys.exit(1)
sys.exit(1 if FAILED else 0)
