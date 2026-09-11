#!/usr/bin/env python3
"""v4.4 suite — IR VERSION 4: atomic records, every turn, every contradiction,
every record's lineage. Document sources cited by line.

Every FAIL code introduced by version 4 has a POSITIVE check (the control passes
without it) and a MUTANT check (planting exactly the defect produces exactly the
code). Version seal: a version-2/3 compile is never touched by a version-4 rule.

Families:
  A  atomicity — ATOM-1..4 (owner decision D4: semantic, validatable, mutable)
  T  total turn accountability — owner AND assistant (owner principle 6)
  R  contradiction reconciliation — RESOLVED by supersession or UNRESOLVED as UNKNOWN
  L  lineage — fingerprint-proved relation to the previous compile (D6)
  D  document sources — line provenance, no roles, no owner authority
  S  version seal, audit obligation, render determinism

Usage (from the skill root):  python3 evals/test_rnd_v44.py
"""
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_rnd_v4 import (  # noqa: E402
    check, control_clean, expect_code, install_compile, mk_corpus, run,
    write_json, RESULTS,
)
from test_rnd_v41 import v2_ir  # noqa: E402
import rnd_contract as rc  # noqa: E402
import re  # noqa: E402


def expect_warn(out, code, cid):
    return bool(re.search(r"WARN\s+\[%s\]\s+%s\b" % (re.escape(cid), re.escape(code)), out))

MIN_CHECKS = 70


# --------------------------------------------------------------- fixtures --

def v4_ir(corpus, cid, mutate=None, baseline=None):
    """A version-4 compile that satisfies every v4.4 obligation — the control.

    Built on the v4.1 control: CONV-001 turns 1,3,4,5 and CONV-002 turn 2 are cited
    by GOOD_ITEMS; CONV-001 msg 2 (assistant) and CONV-002 msg 1 (owner) are
    ledgered. Every record is ATOMIC and fingerprinted; owner decisions, the
    requirement and the option carry a standing; no record contradicts another, so
    the register is honestly empty.
    """
    path = v2_ir(corpus, cid)
    ir = json.loads(path.read_text(encoding="utf-8"))
    ir["rnd_ir_version"] = 4
    ir["turn_ledger"] = [
        {"source_id": "CONV-001", "messages": "2", "reason": "elaboration-no-new-claim"},
        {"source_id": "CONV-002", "messages": "1", "reason": "duplicate-restatement"},
    ]
    ir.pop("owner_turn_ledger", None)
    ir["contradiction_register"] = []
    ir["retired"] = []
    standings = {"RND-001": "CURRENT_CANDIDATE", "RND-003": "CURRENT_CANDIDATE",
                 "RND-004": "PROPOSAL", "RND-007": "CURRENT_CANDIDATE"}
    for it in ir["items"]:
        it["atomicity"] = "ATOMIC"
        if it["id"] in standings:
            it["standing"] = standings[it["id"]]
        it["fingerprint"] = rc.record_fingerprint(it)
    if baseline:
        bpath = corpus / "_rnd" / baseline / "rc.IR_NAME"
        bpath = corpus / "_rnd" / baseline / rc.IR_NAME
        ir["lineage_baseline"] = {"compile": baseline,
                                  "ir_sha256": rc.sha256_file(bpath)}
    if mutate:
        mutate(ir)
    write_json(path, ir)
    return path


def item(ir, iid):
    for it in ir["items"]:
        if it["id"] == iid:
            return it
    raise KeyError(iid)


def refingerprint(ir):
    for it in ir["items"]:
        it["fingerprint"] = rc.record_fingerprint(it)


# -------------------------------------------------------------- scenarios --

def scenario_control_and_seal(tmp):
    corpus = mk_corpus(tmp)
    v4_ir(corpus, "control-ok")
    v2_ir(corpus, "v2-untouched")
    install_compile(corpus, "v1-untouched")
    rc_, out = run(corpus, "validate")
    check("S v4 control satisfies every v4.4 obligation", control_clean(out), out)
    for code in ("RND_ATOMICITY_MISSING", "RND_FINGERPRINT_MISSING",
                 "RND_TURN_LEDGER_MISSING", "RND_CONTRADICTION_REGISTER_MISSING",
                 "RND_STANDING_MISSING"):
        check("S %s never reaches a version-2 compile" % code,
              not expect_code(out, code, "v2-untouched"), out)
        check("S %s never reaches a version-1 compile" % code,
              not expect_code(out, code, "v1-untouched"), out)
    # a v4 compile still owes the v2 and v3 obligations (superset)
    v4_ir(corpus, "v4-no-progression",
          mutate=lambda ir: ir.__setitem__("progression", []))
    rc_, out = run(corpus, "validate", "--compile", "v4-no-progression")
    check("S version 4 is a superset — v2 progression rule still binds",
          expect_code(out, "RND_PROGRESSION_MISSING", "v4-no-progression"), out)
    # init --atomic stamps version 4 with the v4 fields present
    rc_, out = run(corpus, "init", "--compile", "fresh-v4", "--project", "demo",
                   "--atomic", "--at", "2026-09-11")
    fresh = json.loads((corpus / "_rnd" / "fresh-v4" / "rnd-ir.json").read_text())
    check("S init --atomic stamps rnd_ir_version 4 and the v4 fields",
          fresh["rnd_ir_version"] == 4 and fresh.get("turn_ledger") == []
          and fresh.get("contradiction_register") == [] and "retired" in fresh, out)
    rc_, out = run(corpus, "init", "--compile", "scoped-v4", "--project", "demo",
                   "--atomic", "--only", "CONV-001", "--at", "2026-09-11")
    scoped = json.loads((corpus / "_rnd" / "scoped-v4" / "rnd-ir.json").read_text())
    excl = [s for s in scoped["source_set"]["sources"] if s.get("excluded")]
    check("S init --only records the out-of-scope source as EXCLUDED, visibly",
          len(excl) == 1 and excl[0]["source_id"] == "CONV-002"
          and scoped["source_set"].get("scope") == ["CONV-001"], json.dumps(scoped["source_set"]))
    # F-1: completeness against the manifest
    v4_ir(corpus, "drop-source", mutate=lambda ir: ir["source_set"].__setitem__(
        "sources", [x for x in ir["source_set"]["sources"] if x["source_id"] != "CONV-002"]))

    def false_gap(ir):
        for x in ir["source_set"]["sources"]:
            if x["source_id"] == "CONV-002":
                x.clear()
                x.update({"source_id": "CONV-002", "excluded": "no captured revision — a gap, "
                                                                "recorded rather than hidden"})
    v4_ir(corpus, "false-gap", mutate=false_gap)

    def scope_phrase_no_list(ir):
        for x in ir["source_set"]["sources"]:
            if x["source_id"] == "CONV-002":
                x.clear()
                x.update({"source_id": "CONV-002",
                          "excluded": "outside the compile's declared scope (--only) — not "
                                      "compiled, not absorbed"})
    v4_ir(corpus, "scope-no-list", mutate=scope_phrase_no_list)

    def scoped_ok(ir):
        scope_phrase_no_list(ir)
        ir["source_set"]["scope"] = ["CONV-001"]
        ir["turn_ledger"] = [e for e in ir["turn_ledger"] if e["source_id"] != "CONV-002"]
        ir["progression"] = [p for p in ir["progression"] if p["source_id"] != "CONV-002"]
        ir["items"] = [i for i in ir["items"] if i["id"] != "RND-005"]
        for row in ir["coverage"]:
            row["basis"] = [b for b in row["basis"] if b != "RND-005"]
    v4_ir(corpus, "scoped-ok", mutate=scoped_ok)

    def v2_scope_phrase(ir):
        scope_phrase_no_list(ir)
        ir["source_set"]["scope"] = ["CONV-001"]
    v2_ir(corpus, "v2-scope-list", mutate=v2_scope_phrase)
    rc_, out = run(corpus, "validate")
    check("F-1 dropping a captured source from the IR is RND_SOURCE_SET_INCOMPLETE",
          expect_code(out, "RND_SOURCE_SET_INCOMPLETE", "drop-source"), out)
    check("F-1 excluding a captured source as 'no captured revision' is INCOMPLETE",
          expect_code(out, "RND_SOURCE_SET_INCOMPLETE", "false-gap"), out)
    check("F-1 the scope phrase without a declared scope list is INCOMPLETE",
          expect_code(out, "RND_SOURCE_SET_INCOMPLETE", "scope-no-list"), out)
    check("F-1 a declared scope (init --only) validates and is reported SCOPED (WARN)",
          not expect_code(out, "RND_SOURCE_SET_INCOMPLETE", "scoped-ok")
          and expect_warn(out, "RND_SOURCE_SET_SCOPED", "scoped-ok"), out)
    check("F-6 a version-2 compile cannot declare a scope — INVALID, and the exclusion is "
          "still the pre-existing FAIL", expect_code(out, "RND_SOURCE_SET_INVALID", "v2-scope-list")
          and expect_code(out, "RND_SOURCE_SET_INCOMPLETE", "v2-scope-list"), out)
    f, summary = rc.validate_compile(corpus, "scoped-ok")
    check("F-1 the summary reports a scoped compile as PARTIAL", summary.get("scope") == "PARTIAL",
          str(summary))
    f, summary = rc.validate_compile(corpus, "control-ok")
    check("F-1 the summary reports a full compile as FULL", summary.get("scope") == "FULL",
          str(summary))


def scenario_a_atomicity(tmp):
    corpus = mk_corpus(tmp)
    v4_ir(corpus, "control-ok")
    # ATOM-3 missing / invalid
    v4_ir(corpus, "atom-missing", mutate=lambda ir: item(ir, "RND-002").pop("atomicity"))
    v4_ir(corpus, "atom-invalid",
          mutate=lambda ir: item(ir, "RND-002").__setitem__("atomicity", "SINGLE"))
    rc_, out = run(corpus, "validate")
    check("A control has no atomicity finding", control_clean(out), out)
    check("A a record without atomicity is refused",
          expect_code(out, "RND_ATOMICITY_MISSING", "atom-missing"), out)
    check("A an atomicity outside ATOMIC/COMPOSITE is refused",
          expect_code(out, "RND_ATOMICITY_INVALID", "atom-invalid"), out)

    # ATOM-1: a scoped supersession proves the target is compound
    def scoped(ir):
        item(ir, "RND-007")["relations"] = [
            {"rel": "supersedes", "target": "RND-001",
             "scope": "the queue clause only; the evidence clause stands"}]
        item(ir, "RND-001")["standing"] = "SUPERSEDED"
        refingerprint(ir)
    v4_ir(corpus, "atom-partial", mutate=scoped)
    rc_, out = run(corpus, "validate", "--compile", "atom-partial")
    check("A ATOM-1: a relation reaching only PART of a record is refused",
          expect_code(out, "RND_CLAIM_PARTIALLY_SUPERSEDED", "atom-partial"), out)

    # ATOM-2: a composite container with two atomic parts is fine; state on it is not
    def composite(ir):
        ir["items"].append({
            "id": "RND-010", "kind": "OBSERVATION", "atomicity": "COMPOSITE",
            "claim": "The queue decision and the evidence law, read together.",
            "scope": "infrastructure", "provenance": [
                {"source_id": "CONV-001", "revision": 1, "messages": "1"}],
            "authority_class": "evidence", "uncertainty": "none",
            "tags": [], "relations": [{"rel": "composed_of", "target": "RND-001"},
                                      {"rel": "composed_of", "target": "RND-003"}]})
        ir["coverage"][0]["basis"].append("RND-010")
        refingerprint(ir)
    v4_ir(corpus, "composite-ok", mutate=composite)

    def composite_with_state(ir):
        composite(ir)
        item(ir, "RND-010")["standing"] = "PROPOSAL"
        refingerprint(ir)
    v4_ir(corpus, "composite-state", mutate=composite_with_state)

    def composite_one_part(ir):
        composite(ir)
        item(ir, "RND-010")["relations"] = [{"rel": "composed_of", "target": "RND-001"}]
        refingerprint(ir)
    v4_ir(corpus, "composite-one", mutate=composite_one_part)

    def composite_nested(ir):
        composite(ir)
        item(ir, "RND-001")["atomicity"] = "COMPOSITE"
        item(ir, "RND-001").pop("standing", None)
        item(ir, "RND-001")["relations"] = [{"rel": "composed_of", "target": "RND-003"},
                                            {"rel": "composed_of", "target": "RND-004"}]
        refingerprint(ir)
    v4_ir(corpus, "composite-nested", mutate=composite_nested)

    def composite_contradicts(ir):
        composite(ir)
        item(ir, "RND-005")["relations"] = [{"rel": "contradicts", "target": "RND-010"}]
        ir["contradiction_register"] = [{"pair": ["RND-005", "RND-010"],
                                         "state": "UNRESOLVED", "unknown": "RND-006"}]
        item(ir, "RND-006")["relations"] = [{"rel": "relates-to", "target": "RND-005"},
                                            {"rel": "relates-to", "target": "RND-010"}]
        refingerprint(ir)
    v4_ir(corpus, "composite-contra", mutate=composite_contradicts)

    def composite_kind_mismatch(ir):
        composite(ir)
        item(ir, "RND-010")["kind"] = "OPTION"
        item(ir, "RND-010")["authority_class"] = "derived"
        refingerprint(ir)
    v4_ir(corpus, "composite-kind", mutate=composite_kind_mismatch)

    def composed_but_atomic(ir):
        item(ir, "RND-002")["relations"].append({"rel": "composed_of", "target": "RND-003"})
        refingerprint(ir)
    v4_ir(corpus, "composed-atomic", mutate=composed_but_atomic)
    rc_, out = run(corpus, "validate")
    check("A ATOM-2: a container with two atomic parts passes",
          not expect_code(out, "RND_COMPOSITE_PARTS_MISSING", "composite-ok")
          and not expect_code(out, "RND_COMPOSITE_CARRIES_STATE", "composite-ok")
          and not expect_code(out, "RND_COMPOSITE_NESTED", "composite-ok"), out)
    check("A ATOM-2: a container carrying standing is refused",
          expect_code(out, "RND_COMPOSITE_CARRIES_STATE", "composite-state"), out)
    check("A ATOM-2: a container with one part is refused",
          expect_code(out, "RND_COMPOSITE_PARTS_MISSING", "composite-one"), out)
    check("A ATOM-2: a container of containers is refused",
          expect_code(out, "RND_COMPOSITE_NESTED", "composite-nested"), out)
    check("A ATOM-2: contradicting a container is refused",
          expect_code(out, "RND_COMPOSITE_CARRIES_STATE", "composite-contra"), out)
    check("A composed_of on a non-composite record is refused",
          expect_code(out, "RND_ATOMICITY_INVALID", "composed-atomic"), out)
    check("A (F-11) an OPTION container of OBSERVATION parts is RND_COMPOSITE_KIND_MISMATCH "
          "— standing cannot be dodged through a container of another kind",
          expect_code(out, "RND_COMPOSITE_KIND_MISMATCH", "composite-kind"), out)

    # ATOM-4: the compound-suspect WARN points, never decides
    def compound(ir):
        it = item(ir, "RND-003")
        it["claim"] = ("(a) every derived artifact must be deletable; (b) the ledger "
                       "is deferred until the corpus grows; (c) identity questions "
                       "are parked; " * 4)
        refingerprint(ir)
    v4_ir(corpus, "compound-suspect", mutate=compound)
    rc_, out = run(corpus, "validate", "--compile", "compound-suspect")
    check("A ATOM-4: an enumerated multi-clause claim is flagged as a WARN",
          expect_warn(out, "RND_CLAIM_COMPOUND_SUSPECT", "compound-suspect"), out)
    check("A ATOM-4 is a WARN, not a FAIL — the audit decides", rc_ == 0, out)


def scenario_t_total_turn_accountability(tmp):
    corpus = mk_corpus(tmp)
    v4_ir(corpus, "control-ok")
    v4_ir(corpus, "no-ledger", mutate=lambda ir: ir.pop("turn_ledger"))
    v4_ir(corpus, "assistant-lost",
          mutate=lambda ir: ir.__setitem__("turn_ledger", ir["turn_ledger"][1:]))
    v4_ir(corpus, "owner-lost",
          mutate=lambda ir: ir.__setitem__("turn_ledger", ir["turn_ledger"][:1]))
    v4_ir(corpus, "bad-reason",
          mutate=lambda ir: ir["turn_ledger"][0].__setitem__("reason", "unimportant"))
    v4_ir(corpus, "role-mismatch",
          mutate=lambda ir: ir["turn_ledger"][0].__setitem__("reason", "question-only"))
    v4_ir(corpus, "range-past-end",
          mutate=lambda ir: ir["turn_ledger"][0].__setitem__("messages", "2-9"))
    v4_ir(corpus, "unbound-source",
          mutate=lambda ir: ir["turn_ledger"][0].__setitem__("source_id", "CONV-099"))
    v4_ir(corpus, "ledger-twice",
          mutate=lambda ir: ir["turn_ledger"].append(
              {"source_id": "CONV-001", "messages": "2", "reason": "tool-or-machine-output"}))
    v4_ir(corpus, "ledger-cited",
          mutate=lambda ir: ir["turn_ledger"].append(
              {"source_id": "CONV-001", "messages": "4", "reason": "elaboration-no-new-claim"}))
    rc_, out = run(corpus, "validate")
    check("T control accounts for every turn of every role", control_clean(out), out)
    check("T no turn_ledger at all is refused",
          expect_code(out, "RND_TURN_LEDGER_MISSING", "no-ledger"), out)
    check("T an uncited, unledgered ASSISTANT turn is reported",
          expect_code(out, "RND_TURN_UNACCOUNTED", "assistant-lost")
          and "CONV-001: 1 turn(s)" in out and "assistant 1" in out, out)
    check("T an uncited, unledgered OWNER turn is reported by the v4 rule too",
          expect_code(out, "RND_TURN_UNACCOUNTED", "owner-lost"), out)
    check("T 'unimportant' is not a reason", expect_code(
        out, "RND_TURN_LEDGER_REASON_INVALID", "bad-reason"), out)
    check("T an owner reason on an assistant turn is a role mismatch",
          expect_code(out, "RND_TURN_LEDGER_ROLE_MISMATCH", "role-mismatch"), out)
    check("T a range past the end of the source is refused",
          expect_code(out, "RND_TURN_LEDGER_INVALID", "range-past-end"), out)
    check("T a ledger entry into an unbound source is refused",
          expect_code(out, "RND_TURN_LEDGER_INVALID", "unbound-source"), out)
    check("T (F-17) the same turn ledgered twice is invalid",
          expect_code(out, "RND_TURN_LEDGER_INVALID", "ledger-twice"), out)
    check("T (F-17) a turn both cited and ledgered is invalid",
          expect_code(out, "RND_TURN_LEDGER_INVALID", "ledger-cited"), out)
    # an entry that fails validation must not silently discharge the turn
    check("T a mis-roled entry does not account for its turn",
          expect_code(out, "RND_TURN_UNACCOUNTED", "role-mismatch"), out)
    # the render shows the ledger and the summary carries the ratio
    f, summary = rc.validate_compile(corpus, "control-ok")
    check("T summary reports TURNS_ACCOUNTED=100% for the control",
          summary.get("turns_accounted") == "100%", str(summary))
    f, summary = rc.validate_compile(corpus, "assistant-lost")
    check("T summary reports a ratio below 100% when a turn is missing",
          summary.get("turns_accounted") not in ("100%", "-"), str(summary))

    # ratio guard: ledgering almost every assistant turn is not compiling
    corpus2 = mk_corpus(Path(tmp) / "big")
    long_src = corpus2 / "_projects/demo/sources/CONV-001/conversation.md"
    text = long_src.read_text(encoding="utf-8")
    extra = "".join("\n---\n\n## Meddelande %d — ChatGPT (assistent)\n\nFyllnad %d.\n"
                    % (n, n) for n in range(6, 31))
    long_src.write_text(text + extra, encoding="utf-8")
    man = json.loads((corpus2 / "_projects/demo/project-manifest.json").read_text())
    for s in man["sources"]:
        if s["source_id"] == "CONV-001":
            import hashlib
            s["revisions"][0]["message_count"] = 30
            s["revisions"][0]["sha256"] = hashlib.sha256(
                long_src.read_bytes()).hexdigest()
    write_json(corpus2 / "_projects/demo/project-manifest.json", man)

    def ledger_all(ir):
        ir["turn_ledger"].append({"source_id": "CONV-001", "messages": "6-30",
                                  "reason": "no-material-content"})
        for p in ir["progression"]:
            if p["source_id"] == "CONV-001":
                p["examined_through"] = 30
    v4_ir(corpus2, "mostly-ledgered", mutate=ledger_all)
    rc_, out = run(corpus2, "validate", "--compile", "mostly-ledgered")
    check("T ledgering ~all assistant turns trips the ratio guard",
          expect_code(out, "RND_ASSISTANT_TURNS_MOSTLY_LEDGERED", "mostly-ledgered"), out)


def scenario_r_contradictions(tmp):
    corpus = mk_corpus(tmp)
    v4_ir(corpus, "control-ok")

    def contradicting(ir):
        # RND-005 (the external demand) contradicts RND-001 (owner: no queue switch)
        item(ir, "RND-005")["relations"] = [{"rel": "contradicts", "target": "RND-001"}]
        refingerprint(ir)

    def unresolved_ok(ir):
        contradicting(ir)
        item(ir, "RND-006")["relations"] = [{"rel": "relates-to", "target": "RND-001"},
                                            {"rel": "relates-to", "target": "RND-005"}]
        ir["contradiction_register"] = [{"pair": ["RND-001", "RND-005"],
                                         "state": "UNRESOLVED", "unknown": "RND-006"}]
        refingerprint(ir)

    def resolved_ok(ir):
        contradicting(ir)
        # the owner's later decision supersedes RND-001; RND-001 stands SUPERSEDED
        item(ir, "RND-007")["relations"] = [{"rel": "supersedes", "target": "RND-001"}]
        item(ir, "RND-001")["standing"] = "SUPERSEDED"
        ir["contradiction_register"] = [{"pair": ["RND-001", "RND-005"],
                                         "state": "RESOLVED", "resolved_by": "RND-007"}]
        refingerprint(ir)

    def unregistered(ir):
        contradicting(ir)

    def no_register(ir):
        contradicting(ir)
        ir.pop("contradiction_register")

    def bad_pair(ir):
        ir["contradiction_register"] = [{"pair": ["RND-001", "RND-002"],
                                         "state": "UNRESOLVED", "unknown": "RND-006"}]

    def unbacked(ir):
        contradicting(ir)
        ir["contradiction_register"] = [{"pair": ["RND-001", "RND-005"],
                                         "state": "RESOLVED", "resolved_by": "RND-007"}]
        refingerprint(ir)          # RND-007 supersedes nothing

    def unresolved_no_unknown(ir):
        contradicting(ir)
        ir["contradiction_register"] = [{"pair": ["RND-001", "RND-005"],
                                         "state": "UNRESOLVED", "unknown": "RND-002"}]
        refingerprint(ir)          # RND-002 is a HYPOTHESIS, not UNKNOWN

    def resolved_by_side(ir):
        contradicting(ir)
        item(ir, "RND-005")["relations"].append({"rel": "supersedes", "target": "RND-001"})
        item(ir, "RND-001")["standing"] = "SUPERSEDED"
        ir["contradiction_register"] = [{"pair": ["RND-001", "RND-005"],
                                         "state": "RESOLVED", "resolved_by": "RND-005"}]
        refingerprint(ir)

    def resolved_by_dead(ir):
        resolved_ok(ir)
        item(ir, "RND-007")["standing"] = "REJECTED"
        refingerprint(ir)

    def resolved_by_unknown(ir):
        contradicting(ir)
        item(ir, "RND-006")["relations"] = [{"rel": "supersedes", "target": "RND-005"}]
        item(ir, "RND-005")["standing"] = "SUPERSEDED"
        ir["contradiction_register"] = [{"pair": ["RND-001", "RND-005"],
                                         "state": "RESOLVED", "resolved_by": "RND-006"}]
        refingerprint(ir)

    def bad_state(ir):
        contradicting(ir)
        ir["contradiction_register"] = [{"pair": ["RND-001", "RND-005"],
                                         "state": "IGNORED"}]
        refingerprint(ir)

    for cid, m in (("contra-unresolved-ok", unresolved_ok), ("contra-resolved-ok", resolved_ok),
                   ("contra-unregistered", unregistered), ("contra-no-register", no_register),
                   ("contra-bad-pair", bad_pair), ("contra-unbacked", unbacked),
                   ("contra-no-unknown", unresolved_no_unknown), ("contra-bad-state", bad_state),
                   ("contra-by-side", resolved_by_side), ("contra-by-dead", resolved_by_dead),
                   ("contra-by-unknown", resolved_by_unknown)):
        v4_ir(corpus, cid, mutate=m)
    rc_, out = run(corpus, "validate")
    check("R control (no contradictions, empty register) passes", control_clean(out), out)
    check("R an UNRESOLVED pair with an UNKNOWN record naming both passes",
          not expect_code(out, "RND_CONTRADICTION_UNRECONCILED", "contra-unresolved-ok")
          and not expect_code(out, "RND_CONTRADICTION_REGISTER_INVALID",
                              "contra-unresolved-ok"), out)
    check("R a pair RESOLVED by an owner supersession with SUPERSEDED standing passes",
          not expect_code(out, "RND_CONTRADICTION_RESOLUTION_UNBACKED", "contra-resolved-ok")
          and not expect_code(out, "RND_CONTRADICTION_UNRECONCILED", "contra-resolved-ok")
          and not expect_code(out, "RND_DECISION_SUPERSEDED_WITHOUT_OWNER",
                              "contra-resolved-ok"), out)
    check("R a contradicts pair absent from the register is unreconciled",
          expect_code(out, "RND_CONTRADICTION_UNRECONCILED", "contra-unregistered"), out)
    check("R no register at all is refused",
          expect_code(out, "RND_CONTRADICTION_REGISTER_MISSING", "contra-no-register"), out)
    check("R a register entry over a pair that does not contradict is refused",
          expect_code(out, "RND_CONTRADICTION_REGISTER_INVALID", "contra-bad-pair"), out)
    check("R RESOLVED by a record that supersedes neither side is unbacked",
          expect_code(out, "RND_CONTRADICTION_RESOLUTION_UNBACKED", "contra-unbacked"), out)
    check("R UNRESOLVED without an UNKNOWN record is unreconciled",
          expect_code(out, "RND_CONTRADICTION_UNRECONCILED", "contra-no-unknown"), out)
    check("R a state outside RESOLVED/UNRESOLVED is refused",
          expect_code(out, "RND_CONTRADICTION_REGISTER_INVALID", "contra-bad-state"), out)
    check("R (F-12) one side of the pair cannot resolve it",
          expect_code(out, "RND_CONTRADICTION_RESOLUTION_UNBACKED", "contra-by-side"), out)
    check("R (F-12) a REJECTED resolver is not live and cannot resolve",
          expect_code(out, "RND_CONTRADICTION_RESOLUTION_UNBACKED", "contra-by-dead"), out)
    check("R (F-12) an UNKNOWN record cannot resolve a contradiction",
          expect_code(out, "RND_CONTRADICTION_RESOLUTION_UNBACKED", "contra-by-unknown"), out)
    check("R both sides of a resolved contradiction survive as records",
          all(iid in json.loads((corpus / "_rnd/contra-resolved-ok/rnd-ir.json").read_text())
              ["items"].__repr__() for iid in ("RND-001", "RND-005")), "")


def scenario_l_lineage(tmp):
    corpus = mk_corpus(tmp)
    v4_ir(corpus, "base")

    def same_all(ir):
        for it in ir["items"]:
            it["lineage"] = [{"id": it["id"], "relation": "SAME"}]
    v4_ir(corpus, "lin-same", baseline="base", mutate=same_all)

    def revised(ir):
        same_all(ir)
        it = item(ir, "RND-002")
        it["claim"] = it["claim"] + " (revised wording)"
        it["lineage"] = [{"id": "RND-002", "relation": "REVISED"}]
        refingerprint(ir)
    v4_ir(corpus, "lin-revised", baseline="base", mutate=revised)

    def false_same(ir):
        same_all(ir)
        it = item(ir, "RND-002")
        it["claim"] = it["claim"] + " (changed)"
        refingerprint(ir)          # still claims SAME
    v4_ir(corpus, "lin-false-same", baseline="base", mutate=false_same)

    def false_revised(ir):
        same_all(ir)
        item(ir, "RND-002")["lineage"] = [{"id": "RND-002", "relation": "REVISED"}]
    v4_ir(corpus, "lin-false-revised", baseline="base", mutate=false_revised)

    def dangling(ir):
        same_all(ir)
        item(ir, "RND-002")["lineage"] = [{"id": "RND-099", "relation": "SAME"}]
    v4_ir(corpus, "lin-dangling", baseline="base", mutate=dangling)

    def undeclared(ir):
        same_all(ir)
        item(ir, "RND-002").pop("lineage")      # identical to base, presented as NEW
    v4_ir(corpus, "lin-undeclared", baseline="base", mutate=undeclared)

    def no_baseline(ir):
        same_all(ir)
        ir.pop("lineage_baseline")
    v4_ir(corpus, "lin-no-baseline", baseline="base", mutate=no_baseline)

    def wrong_sha(ir):
        same_all(ir)
        ir["lineage_baseline"]["ir_sha256"] = "0" * 64
    v4_ir(corpus, "lin-wrong-sha", baseline="base", mutate=wrong_sha)

    def retired_undeclared(ir):
        same_all(ir)
        ir["items"] = [it for it in ir["items"] if it["id"] != "RND-002"]
        for row in ir["coverage"]:
            row["basis"] = [b for b in row["basis"] if b != "RND-002"]
        for it in ir["items"]:
            it["relations"] = [r for r in it["relations"] if r["target"] != "RND-002"]
    v4_ir(corpus, "lin-retired", baseline="base", mutate=retired_undeclared)

    def retired_declared(ir):
        retired_undeclared(ir)
        ir["retired"] = [{"id": "RND-002", "reason": "hypothesis withdrawn — folded "
                                                     "into RND-004 on re-reading"}]
    v4_ir(corpus, "lin-retired-ok", baseline="base", mutate=retired_declared)

    def split_same(ir):
        same_all(ir)
        item(ir, "RND-002")["lineage"] = [{"id": "RND-002", "relation": "SPLIT_FROM"}]
    v4_ir(corpus, "lin-split-same", baseline="base", mutate=split_same)

    def split_new_source(ir):
        same_all(ir)
        it = item(ir, "RND-002")
        it["claim"] = "A per-repo learning ledger may shorten the loop (first half)."
        it["provenance"].append({"source_id": "CONV-002", "revision": 1, "messages": "2"})
        it["lineage"] = [{"id": "RND-002", "relation": "SPLIT_FROM"}]
        refingerprint(ir)
    v4_ir(corpus, "lin-split-single", baseline="base", mutate=split_new_source)

    def split_ok(ir):
        same_all(ir)
        it = item(ir, "RND-002")
        it["claim"] = "A per-repo learning ledger may shorten the loop (first half)."
        it["lineage"] = [{"id": "RND-002", "relation": "SPLIT_FROM"}]
        ir["items"].append(dict(json.loads(json.dumps(it)), id="RND-011",
                                claim="… and the loop it shortens is the trustworthy one "
                                      "(second half).",
                                lineage=[{"id": "RND-002", "relation": "SPLIT_FROM"}]))
        ir["coverage"][1]["basis"].append("RND-011")
        refingerprint(ir)
    v4_ir(corpus, "lin-split-ok", baseline="base", mutate=split_ok)

    def merged_single(ir):
        same_all(ir)
        it = item(ir, "RND-002")
        it["claim"] = "Merged wording of the ledger hypothesis and the deferral option."
        it["lineage"] = [{"id": "RND-002", "relation": "MERGED_FROM"}]
        refingerprint(ir)
    v4_ir(corpus, "lin-merged-single", baseline="base", mutate=merged_single)

    def merged_ok(ir):
        merged_single(ir)
        item(ir, "RND-002")["lineage"].append({"id": "RND-004", "relation": "MERGED_FROM"})
        ir["items"] = [i for i in ir["items"] if i["id"] != "RND-004"]
        for row in ir["coverage"]:
            row["basis"] = [b for b in row["basis"] if b != "RND-004"]
        for i in ir["items"]:
            i["relations"] = [r for r in i["relations"] if r["target"] != "RND-004"]
        ir["turn_ledger"].append({"source_id": "CONV-001", "messages": "4",
                                  "reason": "elaboration-no-new-claim"})
        refingerprint(ir)
    v4_ir(corpus, "lin-merged-ok", baseline="base", mutate=merged_ok)

    def bad_entry(ir):
        same_all(ir)
        item(ir, "RND-002")["lineage"] = [{"id": "RND-001", "relation": "COPIED"}]
    v4_ir(corpus, "lin-bad-entry", baseline="base", mutate=bad_entry)

    rc_, out = run(corpus, "validate")
    check("L SAME lineage over equal fingerprints passes",
          not any(expect_code(out, c, "lin-same") for c in (
              "RND_LINEAGE_RELATION_FALSE", "RND_LINEAGE_DANGLING",
              "RND_LINEAGE_UNDECLARED", "RND_LINEAGE_BASELINE_MISMATCH",
              "RND_LINEAGE_INVALID")), out)
    check("L REVISED over a changed claim passes",
          not expect_code(out, "RND_LINEAGE_RELATION_FALSE", "lin-revised"), out)
    check("L SAME over a changed fingerprint is false",
          expect_code(out, "RND_LINEAGE_RELATION_FALSE", "lin-false-same"), out)
    check("L REVISED over an equal fingerprint is false",
          expect_code(out, "RND_LINEAGE_RELATION_FALSE", "lin-false-revised"), out)
    check("L lineage to an id the baseline lacks dangles",
          expect_code(out, "RND_LINEAGE_DANGLING", "lin-dangling"), out)
    check("L an identical record presented as NEW is an undeclared SAME",
          expect_code(out, "RND_LINEAGE_UNDECLARED", "lin-undeclared"), out)
    check("L lineage without a lineage_baseline is invalid",
          expect_code(out, "RND_LINEAGE_INVALID", "lin-no-baseline"), out)
    check("L a baseline whose IR bytes moved is refused",
          expect_code(out, "RND_LINEAGE_BASELINE_MISMATCH", "lin-wrong-sha"), out)
    check("L a baseline record that vanished without a reason is a WARN",
          expect_warn(out, "RND_LINEAGE_RETIRED_UNDECLARED", "lin-retired"), out)
    check("L a declared retirement with a reason silences the WARN",
          not expect_warn(out, "RND_LINEAGE_RETIRED_UNDECLARED", "lin-retired-ok"), out)
    check("L a lineage entry with an unknown relation is invalid",
          expect_code(out, "RND_LINEAGE_INVALID", "lin-bad-entry"), out)
    check("L (F-13) SPLIT_FROM over an equal fingerprint is false — it is SAME",
          expect_code(out, "RND_LINEAGE_RELATION_FALSE", "lin-split-same"), out)
    check("L (F-13) a 'part' citing a source the whole never cited is false",
          expect_code(out, "RND_LINEAGE_RELATION_FALSE", "lin-split-single"), out)
    check("L (F-13) a split into two records passes",
          not expect_code(out, "RND_LINEAGE_RELATION_FALSE", "lin-split-ok"), out)
    check("L (F-13) MERGED_FROM naming one baseline record is false",
          expect_code(out, "RND_LINEAGE_RELATION_FALSE", "lin-merged-single"), out)
    check("L (F-13) a merge of two baseline records passes",
          not expect_code(out, "RND_LINEAGE_RELATION_FALSE", "lin-merged-ok")
          and not expect_warn(out, "RND_LINEAGE_RETIRED_UNDECLARED", "lin-merged-ok"), out)
    # fingerprint integrity
    v4_ir(corpus, "fp-missing", mutate=lambda ir: item(ir, "RND-002").pop("fingerprint"))
    v4_ir(corpus, "fp-stale", mutate=lambda ir: item(ir, "RND-002").__setitem__(
        "claim", item(ir, "RND-002")["claim"] + " edited after fingerprinting"))
    rc_, out = run(corpus, "validate")
    check("L a record without a fingerprint is refused",
          expect_code(out, "RND_FINGERPRINT_MISSING", "fp-missing"), out)
    check("L a fingerprint that no longer recomputes is refused",
          expect_code(out, "RND_FINGERPRINT_MISMATCH", "fp-stale"), out)
    check("L the fingerprint ignores the id — same content, different id, same print",
          rc.record_fingerprint(dict(item(json.loads((corpus / "_rnd/base/rnd-ir.json")
                                                     .read_text()), "RND-002"), id="RND-777"))
          == item(json.loads((corpus / "_rnd/base/rnd-ir.json").read_text()),
                  "RND-002")["fingerprint"], "")
    # standing obligation
    v4_ir(corpus, "standing-missing",
          mutate=lambda ir: item(ir, "RND-001").pop("standing"))
    rc_, out = run(corpus, "validate", "--compile", "standing-missing")
    check("L/B an OWNER_DECISION without standing is refused in version 4",
          expect_code(out, "RND_STANDING_MISSING", "standing-missing"), out)


def scenario_d_document_sources(tmp):
    corpus = mk_corpus(tmp)
    import hashlib
    doc_dir = corpus / "_projects/demo/sources/DOC-001"
    doc_dir.mkdir(parents=True)
    doc = doc_dir / "document.md"
    doc.write_text("# Masterplan\n\nLine two says the ledger is optional.\n"
                   "Line four is a diagram caption.\n", encoding="utf-8")
    man_path = corpus / "_projects/demo/project-manifest.json"
    man = json.loads(man_path.read_text())
    man["sources"].append({
        "source_id": "DOC-001", "kind": "document", "title": "Masterplan",
        "evidence_role": "external_reference", "origin": "file://masterplan",
        "discovered_at": "2026-09-11", "state": "CAPTURED",
        "used_in": [{"source_id": "CONV-001", "messages": "3"}],
        "revisions": [{"revision": 1, "path": "_projects/demo/sources/DOC-001/document.md",
                       "sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
                       "byte_length": len(doc.read_bytes()), "line_count": 4,
                       "media_type": "text/markdown", "captured_at": "2026-09-11",
                       "adapter": "file", "verified": True}],
        "errors": []})
    write_json(man_path, man)

    def cite_doc(ir):
        item(ir, "RND-002")["provenance"].append(
            {"source_id": "DOC-001", "revision": 1, "lines": "2-3"})
        ir["progression"].append({"source_id": "DOC-001", "examined_through": 0})
        refingerprint(ir)
    v4_ir(corpus, "doc-ok", mutate=cite_doc)
    ir = json.loads((corpus / "_rnd/doc-ok/rnd-ir.json").read_text())
    docrec = [s for s in ir["source_set"]["sources"] if s["source_id"] == "DOC-001"]
    check("D init binds a document source by whole-file sha256 and line_count",
          docrec and docrec[0].get("kind") == "document"
          and docrec[0].get("line_count") == 4 and docrec[0].get("sha256"), json.dumps(docrec))

    def cite_beyond(ir):
        cite_doc(ir)
        item(ir, "RND-002")["provenance"][-1]["lines"] = "2-9"
        refingerprint(ir)
    v4_ir(corpus, "doc-beyond", mutate=cite_beyond)

    def owner_from_doc(ir):
        cite_doc(ir)
        item(ir, "RND-001")["provenance"] = [
            {"source_id": "DOC-001", "revision": 1, "lines": "2"}]
        refingerprint(ir)
        ir["turn_ledger"].append({"source_id": "CONV-001", "messages": "1",
                                  "reason": "duplicate-restatement"})
    v4_ir(corpus, "doc-owner", mutate=owner_from_doc)
    rc_, out = run(corpus, "validate")
    check("D a line citation inside the document resolves", not any(
        expect_code(out, c, "doc-ok") for c in ("RND_PROVENANCE_OUT_OF_RANGE",
                                                "RND_PROVENANCE_UNBOUND",
                                                "RND_SOURCE_HASH_MISMATCH")), out)
    rc_, out_ok = run(corpus, "validate", "--compile", "doc-ok")
    check("D the document-bound compile validates CLEAN (0 FAIL) — green for the right "
          "reason", not re.search(r"^FAIL\s+\[doc-ok\]", out_ok, re.M), out_ok)
    check("D a line citation past the document is out of range",
          expect_code(out, "RND_PROVENANCE_OUT_OF_RANGE", "doc-beyond"), out)
    check("D a document can never back an OWNER_DECISION",
          expect_code(out, "RND_OWNER_DECISION_ROLE_UNPROVEN", "doc-owner")
          or expect_code(out, "RND_OWNER_DECISION_ASSISTANT_ONLY", "doc-owner")
          or expect_code(out, "RND_OWNER_AUTHORED_UNSUPPORTED", "doc-owner"), out)
    doc.write_text(doc.read_text() + "\nappended after binding\n", encoding="utf-8")
    rc_, out = run(corpus, "validate", "--compile", "doc-ok")
    check("D a document whose bytes moved after binding is refused",
          expect_code(out, "RND_SOURCE_HASH_MISMATCH", "doc-ok"), out)


def scenario_s_audit_and_render(tmp):
    corpus = mk_corpus(tmp)
    v4_ir(corpus, "control-ok")
    cdir = corpus / "_rnd/control-ok"
    ir_sha = rc.sha256_file(cdir / "rnd-ir.json")
    audit = ("---\ntitle: audit\ntype: compile-audit\ncompile: control-ok\n"
             "append_only: true\n---\n\n## AUDIT-1\n- auditor: fresh reviewer\n"
             "- audited_at: 2026-09-11\n- scope: ir_sha256=%s\n- verdict: PASS\n"
             % ir_sha)
    (cdir / "compile-audit.md").write_text(audit, encoding="utf-8")
    rc_, out = run(corpus, "validate", "--compile", "control-ok")
    check("S a v4 audit round without atomicity_reviewed is not an audit",
          expect_code(out, "RND_AUDIT_ATOMICITY_UNREVIEWED", "control-ok")
          and "RND_COMPILE_AUDITED=NO" in out, out)
    (cdir / "compile-audit.md").write_text(audit + "- atomicity_reviewed: yes\n",
                                           encoding="utf-8")
    rc_, out = run(corpus, "validate", "--compile", "control-ok")
    check("S with atomicity_reviewed: yes the v4 compile is audited",
          not expect_code(out, "RND_AUDIT_ATOMICITY_UNREVIEWED", "control-ok")
          and "RND_COMPILE_AUDITED=YES" in out, out)
    # F-10 / F-8: a WARN is a question the audit answers BY ID
    def suspect(ir):
        it = item(ir, "RND-003")
        it["claim"] = ("Three releases landed: (1) a permission gap was fixed; (2) workflow "
                       "code could escape its sandbox; (3) a deny rule ignored a trailing "
                       "slash; the assistant concludes that containment is measured, never "
                       "assumed, and proposes challenger fixtures after the slice.")
        refingerprint(ir)
        ir["turn_ledger"].append({"source_id": "CONV-001", "messages": "5",
                                  "reason": "no-material-content"})
        ir["items"] = [i for i in ir["items"] if i["id"] not in ("RND-006", "RND-007")]
        for row in ir["coverage"]:
            row["basis"] = [b for b in row["basis"] if b not in ("RND-006", "RND-007")]
            if row["state"] != "UNKNOWN" and not row["basis"]:
                row["state"] = "UNKNOWN"
    v4_ir(corpus, "suspect", mutate=suspect)
    sdir = corpus / "_rnd/suspect"
    s_sha = rc.sha256_file(sdir / "rnd-ir.json")
    base_audit = ("---\ntitle: audit\ntype: compile-audit\ncompile: suspect\n"
                  "append_only: true\n---\n\n## AUDIT-1\n- auditor: fresh reviewer\n"
                  "- audited_at: 2026-09-11\n- scope: ir_sha256=%s\n- verdict: PASS\n"
                  "- atomicity_reviewed: yes\n" % s_sha)
    (sdir / "compile-audit.md").write_text(base_audit, encoding="utf-8")
    rc_, out = run(corpus, "validate", "--compile", "suspect")
    check("S (F-10) a compound-suspect record the audit does not name by id is "
          "RND_AUDIT_ATOMICITY_UNREVIEWED", expect_warn(out, "RND_CLAIM_COMPOUND_SUSPECT", "suspect")
          and expect_code(out, "RND_AUDIT_ATOMICITY_UNREVIEWED", "suspect")
          and "RND_COMPILE_AUDITED=NO" in out, out)
    check("S (F-8) an owner turn ledgered no-material-content the audit does not name is "
          "RND_AUDIT_LEDGER_UNREVIEWED", expect_code(out, "RND_AUDIT_LEDGER_UNREVIEWED", "suspect"),
          out)
    (sdir / "compile-audit.md").write_text(
        base_audit + "- compound_suspects_reviewed: RND-003 (judged compound — a FIND would "
        "follow; here named for the obligation)\n- owner_ledger_reviewed: CONV-001:5\n",
        encoding="utf-8")
    rc_, out = run(corpus, "validate", "--compile", "suspect")
    check("S (F-10/F-8) naming the suspect and the owner turn by id discharges both",
          not expect_code(out, "RND_AUDIT_ATOMICITY_UNREVIEWED", "suspect")
          and not expect_code(out, "RND_AUDIT_LEDGER_UNREVIEWED", "suspect")
          and "RND_COMPILE_AUDITED=YES" in out, out)
    check("S (F-10) the fused 'facts; the assistant concludes' shape is a suspect at 300 chars",
          rc.compound_suspect("Three releases landed and were relayed with citation chips in "
                              "the weekly watch report as the assistant read them; the "
                              "assistant concludes that containment is measured externally "
                              "and never assumed from a flag, and proposes fixtures.")
          and rc.compound_suspect("(1) one thing was fixed; (2) another thing was fixed; (3) a "
                                  "third thing was fixed in the very same release train that "
                                  "week, which the report lists in order for the reader to see "
                                  "and to weigh them one by one as separate facts.")
          and not rc.compound_suspect("One claim, one sentence."), "")
    # render is deterministic and shows the v4 sections
    rc_, out = run(corpus, "render", "--compile", "control-ok", "--write")
    first = (cdir / "RND-COVERAGE.md").read_text(encoding="utf-8")
    rc_, out = run(corpus, "render", "--compile", "control-ok", "--write")
    second = (cdir / "RND-COVERAGE.md").read_text(encoding="utf-8")
    check("S render reproduces byte-identically", first == second, "")
    check("S the rendering carries the version-4 sections",
          "ATOMICITY=ATOMIC 7" in first and "TURN_LEDGER=2" in first
          and "CONTRADICTION_REGISTER=0" in first and "LINEAGE_BASELINE=none" in first,
          first)
    rc_, out = run(corpus, "validate", "--compile", "control-ok")
    check("S a fresh rendering is not stale",
          not expect_code(out, "RND_RENDER_STALE", "control-ok"), out)


def main():
    scenarios = (scenario_control_and_seal, scenario_a_atomicity,
                 scenario_t_total_turn_accountability, scenario_r_contradictions,
                 scenario_l_lineage, scenario_d_document_sources,
                 scenario_s_audit_and_render)
    for sc in scenarios:
        tmp = tempfile.mkdtemp(prefix="rnd-v44-")
        try:
            sc(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    passed = sum(1 for r in RESULTS if r[1])
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        if not ok:
            print("FAIL  %s\n      %s" % (name, str(detail)[:1500]))
    print("%d/%d checks passed" % (passed, len(RESULTS)))
    if len(RESULTS) < MIN_CHECKS:
        print("FAIL: only %d checks ran (floor %d)" % (len(RESULTS), MIN_CHECKS))
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
