#!/usr/bin/env python3
"""v4.1 suite — SEMANTIC COVERAGE under adversarial pressure.

v4.0 validates STRUCTURE and PROVENANCE INTEGRITY. It cannot ask whether a compile
UNDERSTOOD its corpus. An external SOURCE->IR falsification of `improvements-r38`
proved the gap is not theoretical: `validate` reported 0 FAIL / 0 WARN over a compile
carrying 619 MATERIAL semantic omissions, and the six items thirty-one audit rounds
were fought to ADD could be deleted again with the contract still green.

Every family here answers to one owner-ordered remediation class (the letters):

  A  a short LATER owner reversal is not lost to a long EARLIER discussion — the
     owner-turn ledger makes byte volume irrelevant to what must be accounted for.
  B  pasted machine output inside an owner-LABELLED message never becomes
     owner-AUTHORED content; relayed assistant text is decidably not the owner's.
  C  an owner "yes" to a direction does not own every nested assistant mechanism.
  D  an assistant saying "Johnny decided X" never makes X owner-authored (v4.0 rule,
     re-proved here so the new basis field cannot become a way around it).
  E  proposal + later rejection resolves to REJECTED/SUPERSEDED, never
     proposal-as-current — negative knowledge has a sanctioned, evidenced home.
  F  material evidence is not destroyed when the surviving conclusion cannot be
     falsified or re-researched without it.
  G  a finding that fits NO known lens is still preserved — the instrument can
     report its own category blindness.
  H  a cross-source contradiction is not summarised into false consensus, and a
     synthesis never acquires owner authority.
  I  inflating item count does not by itself buy a semantic PASS.
  J  near-lossless copying is not the easy path to coverage.

  VERSION SEAL: every rule above applies to `rnd_ir_version: 2` ONLY. A published
  version-1 compile is validated by exactly the rules it was published against, so
  the r38 witness stays green and byte-reproducible. Proved here, not asserted.

Same construction as the v4 suite: real files, real temp corpora, the real validator,
control fixtures that must PASS in the same run as every planted failure, and a
MIN_CHECKS floor so a suite that runs nothing cannot exit green.

Usage (from the skill root):
  python3 evals/test_rnd_v41.py
"""
import copy
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_rnd_v4 import (  # noqa: E402
    GOOD_ITEMS, base_coverage, check, control_clean, expect_code, install_compile,
    mk_corpus, run, write_json, RESULTS, _whole_file_sha,
)

MIN_CHECKS = 78


# --------------------------------------------------------------- fixtures --

def v2_ir(corpus, cid, items=None, coverage=None, mutate=None):
    """A version-2 compile that SATISFIES every v4.1 obligation — the control.

    CONV-001 owner turns are 1, 3, 5 (all cited by GOOD_ITEMS); CONV-002's owner turn
    1 is cited by nothing, so the ledger must account for it. Everything else here is
    the minimum a version-2 compile owes: a basis per owner decision, a progression
    record per source, and an explicit answer to "what fits no lens?".
    """
    def _v2(ir):
        ir["rnd_ir_version"] = 2
        # `owner-authored` is the strongest basis and the contract makes it earn its
        # keep: the quote must be the owner's OWN words from a cited owner turn.
        quotes = {"RND-001": "Vi bygger ingen egen kö. Det är beslutat.",
                  "RND-007": "Identitets- och ekonomifrågorna skjuter vi upp "
                             "medvetet tills Recompile."}
        for it in ir["items"]:
            if it["kind"] == "OWNER_DECISION":
                it.setdefault("owner_authority_basis", "owner-authored")
                it.setdefault("quote", quotes.get(it["id"], ""))
        ir["owner_turn_ledger"] = [
            {"source_id": "CONV-002", "messages": "1",
             "reason": "duplicate-restatement"}]
        ir["progression"] = [{"source_id": "CONV-001", "examined_through": 5},
                             {"source_id": "CONV-002", "examined_through": 2}]
        ir["unlensed"] = []
        # a version-2 compile must ANSWER the cross-source question; empty is a valid
        # answer, absent is not
        ir["cross_source"] = []
        # Every item must be visible to the coverage instrument — but SPREAD across
        # lenses. The old control dumped all-but-one into a single lens, which is the
        # vacuity pattern RND_COVERAGE_LENS_VACUOUS now refuses: a control that is
        # itself vacuous cannot certify anything.
        ids = [i["id"] for i in ir["items"]]
        for k, row in enumerate(ir["coverage"][:3]):
            row["basis"] = sorted(set(row.get("basis") or []) |
                                  {x for j, x in enumerate(ids) if j % 3 == k})
            if row["state"] == "UNKNOWN":
                row["state"] = "PARTIALLY_EXPLORED"
        if mutate:
            mutate(ir)
    return install_compile(corpus, cid, items=items, coverage=coverage, mutate=_v2)


def owner_quote(ir, iid, quote, basis="owner-authored"):
    for it in ir["items"]:
        if it["id"] == iid:
            it["quote"] = quote
            it["owner_authority_basis"] = basis


# -------------------------------------------------------------- scenarios --

def scenario_version_seal(tmp):
    """The published contract is not rewritten under a live compile."""
    corpus = mk_corpus(tmp)
    install_compile(corpus, "v1-untouched")          # version 1, as published
    v2_ir(corpus, "control-ok")
    rc, out = run(corpus, "validate")
    check("v1 compile still validates clean under v4.1",
          not expect_code(out, "RND_OWNER_LEDGER_MISSING", "v1-untouched")
          and not expect_code(out, "RND_PROGRESSION_MISSING", "v1-untouched"), out)
    check("v2 control satisfies every v4.1 obligation", control_clean(out), out)
    # a v1 compile may carry v4.1 vocabulary without the v4.1 rules reaching it
    install_compile(corpus, "v1-standing",
                    mutate=lambda ir: ir["items"][0].__setitem__("standing", "NOPE"))
    rc, out = run(corpus, "validate")
    check("v4.1 vocabulary is not enforced retroactively on v1",
          not expect_code(out, "RND_STANDING_INVALID", "v1-standing"), out)
    shutil.rmtree(corpus / "_rnd" / "v1-standing")


def scenario_a_short_reversal_survives_volume(tmp):
    """A: the owner's own turns are the unit of account, never bytes."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")
    # drop the ledger entry: CONV-002 msg 1 — the owner's LATER reversal, one line
    # against a long earlier thread — is now accounted for by nothing.
    v2_ir(corpus, "lost-reversal",
          mutate=lambda ir: ir.__setitem__("owner_turn_ledger", []))
    rc, out = run(corpus, "validate")
    check("A an uncited owner turn is reported by source and number",
          expect_code(out, "RND_OWNER_TURN_UNACCOUNTED", "lost-reversal"), out)
    check("A the report names the source it lost", "CONV-002" in out, out)
    check("A control still clean in the same run", control_clean(out), out)
    # "unimportant" is not a reason a corpus may give for dropping the owner's voice
    v2_ir(corpus, "bad-reason", mutate=lambda ir: ir.__setitem__(
        "owner_turn_ledger", [{"source_id": "CONV-002", "messages": "1",
                               "reason": "unimportant"}]))
    rc, out = run(corpus, "validate")
    check("A the ledger reason vocabulary is closed",
          expect_code(out, "RND_OWNER_LEDGER_REASON_INVALID", "bad-reason"), out)
    # and a compile may not simply omit the ledger
    v2_ir(corpus, "no-ledger",
          mutate=lambda ir: ir.pop("owner_turn_ledger", None))
    rc, out = run(corpus, "validate")
    check("A the ledger is mandatory at version 2",
          expect_code(out, "RND_OWNER_LEDGER_MISSING", "no-ledger"), out)


def scenario_b_relayed_text_is_not_owner_authored(tmp):
    """B: an owner-LABELLED message that relays assistant text is not owner-AUTHORED."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")
    # CONV-002 msg 2 is not the owner's; CONV-001 msg 2 IS an assistant turn whose
    # words a compile might try to pass off as the owner's own.
    v2_ir(corpus, "relayed", mutate=lambda ir: owner_quote(
        ir, "RND-001", "Johnny decided we will switch to framework X"))
    rc, out = run(corpus, "validate")
    check("B a quote that also sits in an assistant turn is refused as owner-authored",
          expect_code(out, "RND_OWNER_AUTHORED_IS_RELAYED", "relayed")
          or expect_code(out, "RND_OWNER_AUTHORED_UNSUPPORTED", "relayed"), out)
    # the honest basis passes on the same bytes
    v2_ir(corpus, "adopted", mutate=lambda ir: owner_quote(
        ir, "RND-001", "Johnny decided we will switch to framework X",
        basis="owner-adoption-of-assistant-text"))
    rc, out = run(corpus, "validate")
    check("B the same content passes as owner-adoption-of-assistant-text",
          not expect_code(out, "RND_OWNER_AUTHORED_IS_RELAYED", "adopted")
          and not expect_code(out, "RND_OWNER_AUTHORED_UNSUPPORTED", "adopted"), out)
    check("B control still clean in the same run", control_clean(out), out)




def scenario_b2_relay_requires_order(tmp):
    """B (order): relaying is a claim about ORIGIN, so it needs the assistant text to
    come FIRST.

    Two shapes look identical to a rule that only asks "do these words also sit in an
    assistant turn?":

      relay  assistant says it, THEN the owner pastes it back  -> not owner-authored
      echo   the owner says it, THEN the assistant quotes back -> still the owner's

    r38 RND-010 is the second shape (CONV-023: owner msg 14, assistant msg 28). An
    unordered rule demotes it and strips owner authority the owner really has — the
    same class of loss as granting authority he never had, in the other direction.
    Order is decidable inside one transcript and undecidable across two, which is why
    the rule reads message numbers within a source and never compares sources.
    """
    corpus = mk_corpus(tmp)
    src = corpus / "_projects" / "demo" / "sources" / "CONV-002" / "conversation.md"
    RELAY = "Vi byter till framework X. Det är avgjort."
    ECHO = "Bekräfta först när den är Sparad i INBOX."
    # sits in an ASSISTANT turn of the OTHER source (CONV-001 msg 2)
    FOREIGN = "Johnny decided we will switch to framework X. That is settled."
    text = src.read_text(encoding="utf-8").rstrip() + (
        "\n\n---\n\n## Meddelande 3 — ChatGPT (assistent)\n\n%s\n"
        "\n---\n\n## Meddelande 4 — Johnny (användare)\n\n%s\n"
        "\n---\n\n## Meddelande 5 — Johnny (användare)\n\n%s\n"
        "\n---\n\n## Meddelande 6 — ChatGPT (assistent)\n\n%s\n"
        "\n---\n\n## Meddelande 7 — Johnny (användare)\n\n%s\n" % (
            RELAY, RELAY, ECHO, ECHO, FOREIGN))
    src.write_text(text, encoding="utf-8")
    mpath = corpus / "_projects" / "demo" / "project-manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    for entry in manifest["sources"]:
        if entry["source_id"] == "CONV-002":
            rev = entry["revisions"][0]
            rev["sha256"] = _whole_file_sha(text)
            rev["message_count"] = text.count("## Meddelande ")
    write_json(mpath, manifest)

    def add(ir):
        ir["items"].append({
            "id": "RND-101", "kind": "OWNER_DECISION",
            "claim": "The system switches to framework X.", "scope": "infrastructure",
            "provenance": [{"source_id": "CONV-002", "revision": 1, "messages": "4"}],
            "authority_class": "owner", "relations": [], "tags": [],
            "uncertainty": "none", "quote": RELAY,
            "owner_authority_basis": "owner-authored"})
        ir["items"].append({
            "id": "RND-102", "kind": "OWNER_DECISION",
            "claim": "An intake save is confirmed only once the effect is verified.",
            "scope": "intake", "provenance": [
                {"source_id": "CONV-002", "revision": 1, "messages": "5"}],
            "authority_class": "owner", "relations": [], "tags": [],
            "uncertainty": "none", "quote": ECHO,
            "owner_authority_basis": "owner-authored"})
        ir["items"].append({
            "id": "RND-103", "kind": "OWNER_DECISION",
            "claim": "The switch to framework X is settled.", "scope": "infrastructure",
            "provenance": [{"source_id": "CONV-002", "revision": 1, "messages": "7"}],
            "authority_class": "owner", "relations": [], "tags": [],
            "uncertainty": "none", "quote": FOREIGN,
            "owner_authority_basis": "owner-authored"})
        ir["progression"] = [{"source_id": "CONV-001", "examined_through": 5},
                             {"source_id": "CONV-002", "examined_through": 7}]
        _ids = [i["id"] for i in ir["items"]]
        for _k, _row in enumerate(ir["coverage"][:3]):
            _row["basis"] = sorted(set(_row.get("basis") or []) |
                                   {x for _j, x in enumerate(_ids) if _j % 3 == _k})

    v2_ir(corpus, "order", mutate=add)
    rc, out = run(corpus, "validate")
    check("B2 the owner pasting EARLIER assistant text is refused as owner-authored",
          expect_code(out, "RND_OWNER_AUTHORED_IS_RELAYED", "order")
          and "RND-101" in out, out)
    check("B2 the assistant quoting the owner BACK leaves authorship intact",
          "RND-102" not in out.replace("RND-102x", ""), out)
    # the same words in an assistant turn of ANOTHER source: order is undecidable, so
    # this is a WARN about uniqueness, never the relay FAIL.
    warned = re.search(r"WARN\s+\[order\]\s+RND_OWNER_AUTHORED_ECHOED_ELSEWHERE"
                       r"[^\n]*RND-103", out)
    check("B2 an owner quote echoed in a FOREIGN assistant turn warns, not fails",
          bool(warned)
          and not expect_code(out, "RND_OWNER_AUTHORED_ECHOED_ELSEWHERE", "order"),
          out)
    relay_lines = [l for l in out.splitlines()
                   if "RND_OWNER_AUTHORED_IS_RELAYED" in l and "RND-103" in l]
    check("B2 the foreign echo is not miscounted as a relay", not relay_lines, out)


def scenario_c_direction_does_not_own_mechanism(tmp):
    """C: assent to a direction is not authorship of every nested mechanism."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")
    v2_ir(corpus, "nested", mutate=lambda ir: owner_quote(
        ir, "RND-001", "a nested mechanism the owner never worded anywhere"))
    rc, out = run(corpus, "validate")
    check("C a mechanism the owner never worded cannot claim owner-authored",
          expect_code(out, "RND_OWNER_AUTHORED_UNSUPPORTED", "nested"), out)
    v2_ir(corpus, "directive", mutate=lambda ir: owner_quote(
        ir, "RND-001", "a nested mechanism the owner never worded anywhere",
        basis="owner-directive"))
    rc, out = run(corpus, "validate")
    check("C owner-directive is the honest basis for a commissioned mechanism",
          not expect_code(out, "RND_OWNER_AUTHORED_UNSUPPORTED", "directive"), out)
    # the basis field may not be sprayed onto non-decisions to imply authority
    v2_ir(corpus, "misplaced", mutate=lambda ir: [
        it.__setitem__("owner_authority_basis", "owner-authored")
        for it in ir["items"] if it["kind"] == "HYPOTHESIS"])
    rc, out = run(corpus, "validate")
    check("C owner_authority_basis exists only where owner authority does",
          expect_code(out, "RND_OWNER_BASIS_MISPLACED", "misplaced"), out)


def scenario_d_assistant_claim_is_not_owner(tmp):
    """D: 'the assistant said the owner decided X' is still not an owner decision."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")
    v2_ir(corpus, "laundered", mutate=lambda ir: [
        it.update({"provenance": [{"source_id": "CONV-001", "revision": 1,
                                   "messages": "2"}]})
        for it in ir["items"] if it["id"] == "RND-001"])
    rc, out = run(corpus, "validate")
    check("D an assistant-only citation cannot back an OWNER_DECISION",
          expect_code(out, "RND_OWNER_DECISION_ASSISTANT_ONLY", "laundered"), out)
    check("D the new basis field does not open a way around it",
          not control_clean(out, "laundered"), out)
    # a decision with no basis at all is refused at version 2
    v2_ir(corpus, "no-basis", mutate=lambda ir: [
        it.pop("owner_authority_basis", None)
        for it in ir["items"] if it["kind"] == "OWNER_DECISION"])
    rc, out = run(corpus, "validate")
    check("D every OWNER_DECISION states HOW authority was acquired",
          expect_code(out, "RND_OWNER_BASIS_MISSING", "no-basis"), out)
    v2_ir(corpus, "bad-basis", mutate=lambda ir: [
        it.__setitem__("owner_authority_basis", "owner")
        for it in ir["items"] if it["kind"] == "OWNER_DECISION"])
    rc, out = run(corpus, "validate")
    check("D the basis vocabulary is closed",
          expect_code(out, "RND_OWNER_BASIS_INVALID", "bad-basis"), out)


def scenario_e_negative_knowledge(tmp):
    """E: a rejected path stays rejected — NOT-BUILDING has a home and a witness."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")
    # an item may not declare itself replaced with nothing replacing it
    v2_ir(corpus, "orphan-superseded", mutate=lambda ir: [
        it.__setitem__("standing", "SUPERSEDED")
        for it in ir["items"] if it["id"] == "RND-004"])
    rc, out = run(corpus, "validate")
    check("E SUPERSEDED without a superseding item is refused",
          expect_code(out, "RND_STANDING_UNSUPPORTED", "orphan-superseded"), out)
    # the honest shape: the later owner decision supersedes, the option carries it
    def resolved(ir):
        for it in ir["items"]:
            if it["id"] == "RND-004":
                it["standing"] = "SUPERSEDED"
            if it["id"] == "RND-007":
                it["relations"] = [{"rel": "supersedes", "target": "RND-004"}]
    v2_ir(corpus, "resolved", mutate=resolved)
    rc, out = run(corpus, "validate")
    check("E a superseded proposal with its superseder validates",
          not expect_code(out, "RND_STANDING_UNSUPPORTED", "resolved"), out)
    rc_k, out_k = run(corpus, "validate")
    check("E REJECTED is expressible without minting a kind",
          not re.search(r"RND_ITEM_KIND_INVALID", out_k), out_k)
    v2_ir(corpus, "rejected-ok", mutate=lambda ir: [
        it.__setitem__("standing", "REJECTED")
        for it in ir["items"] if it["id"] == "RND-004"])
    rc, out = run(corpus, "validate")
    check("E REJECTED needs no relation and stays inside the seven kinds",
          not expect_code(out, "RND_STANDING_UNSUPPORTED", "rejected-ok")
          and not expect_code(out, "RND_KIND_INVALID", "rejected-ok"), out)
    v2_ir(corpus, "bad-standing", mutate=lambda ir:
          ir["items"][0].__setitem__("standing", "WONTFIX"))
    rc, out = run(corpus, "validate")
    check("E the standing vocabulary is closed",
          expect_code(out, "RND_STANDING_INVALID", "bad-standing"), out)
    check("E control still clean in the same run", control_clean(out), out)


def scenario_f_evidence_survives_the_conclusion(tmp):
    """F: a conclusion that outlives its evidence cannot be falsified."""
    corpus = mk_corpus(tmp)
    # plant an external reference in a source the compile cites as evidence
    src = corpus / "_projects/demo/sources/CONV-002/conversation.md"
    text = src.read_text(encoding="utf-8").replace(
        "You must switch the system to framework X immediately.",
        "Per https://example.org/study-2026 you must switch to framework X.")
    src.write_text(text, encoding="utf-8")
    man = corpus / "_projects/demo/project-manifest.json"
    m = json.loads(man.read_text(encoding="utf-8"))
    import hashlib
    for s in m["sources"]:
        if s["source_id"] == "CONV-002":
            s["revisions"][0]["sha256"] = hashlib.sha256(
                text.encode("utf-8")).hexdigest()
    write_json(man, m)
    v2_ir(corpus, "dropped-evidence")
    rc, out = run(corpus, "validate")
    check("F an evidence item resting on an external reference must retain it",
          expect_code(out, "RND_EVIDENCE_DISCARDED", "dropped-evidence"), out)
    v2_ir(corpus, "kept-evidence", mutate=lambda ir: [
        it.__setitem__("evidence_refs", [{"name": "example.org study 2026",
                                          "source_id": "CONV-002",
                                          "messages": "2"}])
        for it in ir["items"] if it["id"] == "RND-005"])
    rc, out = run(corpus, "validate")
    check("F retaining the named reference clears it",
          not expect_code(out, "RND_EVIDENCE_DISCARDED", "kept-evidence"), out)
    v2_ir(corpus, "empty-ref", mutate=lambda ir: [
        it.__setitem__("evidence_refs", [{"source_id": "CONV-002"}])
        for it in ir["items"] if it["id"] == "RND-005"])
    rc, out = run(corpus, "validate")
    check("F an evidence_ref that names nothing is refused",
          expect_code(out, "RND_EVIDENCE_REF_INVALID", "empty-ref"), out)


def scenario_g_lens_blindness(tmp):
    """G: the instrument must be able to report what it cannot categorise."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")
    v2_ir(corpus, "no-declaration", mutate=lambda ir: ir.pop("unlensed", None))
    rc, out = run(corpus, "validate")
    check("G the unlensed question must be asked, even to answer 'none'",
          expect_code(out, "RND_UNLENSED_DECLARATION_MISSING", "no-declaration"), out)
    # an item in no lens basis and not declared unlensed is invisible to coverage
    v2_ir(corpus, "invisible", mutate=lambda ir: ir["coverage"][0].__setitem__(
        "basis", ["RND-001"]))
    rc, out = run(corpus, "validate")
    check("G an item the instrument cannot see is reported",
          expect_code(out, "RND_ITEM_UNLENSED_UNDECLARED", "invisible"), out)
    # declaring it unlensed is a legitimate answer — the finding is PRESERVED
    def declared(ir):
        ir["coverage"][0]["basis"] = ["RND-001"]
        ir["unlensed"] = [{"distinction": "market positioning has no baseline lens",
                           "items": [i["id"] for i in ir["items"]
                                     if i["id"] not in ("RND-001", "RND-007")]}]
    v2_ir(corpus, "declared-unlensed", mutate=declared)
    rc, out = run(corpus, "validate")
    check("G a finding that fits no lens is preserved by declaring it",
          not expect_code(out, "RND_ITEM_UNLENSED_UNDECLARED", "declared-unlensed"),
          out)
    # the fixture this needs was never created, so the assertion was dead. Build it:
    # drop one baseline lens row and prove the twelve stay mandatory at version 2.
    def _drop_lens(ir):
        ir["coverage"] = [r for r in ir["coverage"]
                          if r["lens"] != "reality-dogfood"]
    v2_ir(corpus, "trimmed", mutate=_drop_lens)
    rc_t, out_t = run(corpus, "validate")
    check("G the twelve baseline lenses remain mandatory",
          expect_code(out_t, "RND_COVERAGE_LENS_MISSING", "trimmed"), out_t)


def scenario_h_cross_source_without_false_consensus(tmp):
    """H: synthesis is derived, provenance-bound, and never owner-authoritative."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")
    v2_ir(corpus, "xs-owner", mutate=lambda ir: ir.__setitem__("cross_source", [
        {"id": "X-001", "statement": "both threads agree", "authority_class": "owner",
         "provenance": [{"source_id": "CONV-001", "messages": "1"},
                        {"source_id": "CONV-002", "messages": "1"}]}]))
    rc, out = run(corpus, "validate")
    check("H a synthesis may not acquire owner authority",
          expect_code(out, "RND_CROSS_SOURCE_AUTHORITY", "xs-owner"), out)
    v2_ir(corpus, "xs-single", mutate=lambda ir: ir.__setitem__("cross_source", [
        {"id": "X-002", "statement": "a lone reading",
         "provenance": [{"source_id": "CONV-001", "messages": "1"}]}]))
    rc, out = run(corpus, "validate")
    check("H one source is a finding, not a cross-source meaning",
          expect_code(out, "RND_CROSS_SOURCE_SINGLE_SOURCE", "xs-single"), out)
    v2_ir(corpus, "xs-unbound", mutate=lambda ir: ir.__setitem__("cross_source", [
        {"id": "X-003", "statement": "invented convergence",
         "provenance": [{"source_id": "CONV-001"}, {"source_id": "CONV-404"}]}]))
    rc, out = run(corpus, "validate")
    check("H a synthesis cannot cite a source the set does not bind",
          expect_code(out, "RND_CROSS_SOURCE_UNBOUND", "xs-unbound"), out)
    # a real contradiction survives as a contradiction
    def contra(ir):
        ir["cross_source"] = [
            {"id": "X-004", "type": "contradiction",
             "statement": "the two sources disagree and both readings stand",
             "provenance": [{"source_id": "CONV-001", "messages": "1"},
                            {"source_id": "CONV-002", "messages": "1"}]}]
    v2_ir(corpus, "xs-contradiction", mutate=contra)
    rc, out = run(corpus, "validate")
    check("H a preserved contradiction validates",
          control_clean(out, "xs-contradiction"), out)


def scenario_ij_volume_buys_nothing(tmp):
    """I/J: neither more items nor more bytes is a route to coverage."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")
    # I — 60 extra items, none of them accounting for the owner turn that is missing
    padded = copy.deepcopy(GOOD_ITEMS)
    for n in range(60):
        padded.append({
            "id": "RND-%03d" % (100 + n), "kind": "OBSERVATION",
            "claim": "restatement %d of an already-carried observation" % n,
            "scope": "padding",
            "provenance": [{"source_id": "CONV-001", "revision": 1,
                            "messages": "3"}],
            "authority_class": "evidence", "relations": [],
            "uncertainty": "none", "tags": []})
    def pad(ir):
        ir["owner_turn_ledger"] = []
        _ids = [i["id"] for i in ir["items"]]
        for _k, _row in enumerate(ir["coverage"][:3]):
            _row["basis"] = sorted(set(_row.get("basis") or []) |
                                   {x for _j, x in enumerate(_ids) if _j % 3 == _k})
    v2_ir(corpus, "inflated", items=padded, mutate=pad)
    rc, out = run(corpus, "validate")
    check("I sixty extra items do not account for one missing owner turn",
          expect_code(out, "RND_OWNER_TURN_UNACCOUNTED", "inflated"), out)
    # J — near-lossless copying is refused by the raw-duplication ceiling
    fat = copy.deepcopy(GOOD_ITEMS)
    fat[0]["claim"] = "x" * 4000
    v2_ir(corpus, "near-lossless", items=fat)
    rc, out = run(corpus, "validate")
    check("J re-housing raw instead of understanding it is refused",
          expect_code(out, "RND_RAW_DUPLICATION", "near-lossless"), out)
    check("I/J control still clean in the same run", control_clean(out), out)


def scenario_d_progression(tmp):
    """The range that stops before the refutation — root cause D."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")
    v2_ir(corpus, "stopped-short", mutate=lambda ir: ir.__setitem__(
        "progression", [{"source_id": "CONV-001", "examined_through": 3},
                        {"source_id": "CONV-002", "examined_through": 2}]))
    rc, out = run(corpus, "validate")
    check("D reading to msg 3 of 5 cannot fix a final semantic state",
          expect_code(out, "RND_PROGRESSION_INCOMPLETE", "stopped-short"), out)
    v2_ir(corpus, "no-progression", mutate=lambda ir: ir.pop("progression", None))
    rc, out = run(corpus, "validate")
    check("D the progression record is mandatory at version 2",
          expect_code(out, "RND_PROGRESSION_MISSING", "no-progression"), out)
    check("D control still clean in the same run", control_clean(out), out)




def scenario_k_cheap_compliance_is_refused(tmp):
    """K: every version-2 obligation must cost something to satisfy.

    An adversarial review satisfied the whole semantic layer at zero semantic cost —
    a rnd_ir_version 2 compile over the real 30-source r38 corpus carrying ONE item
    out of 202 validated 0 FAIL / 0 WARN. Four lines did it: one ledger entry per
    source reading `"1-99999" / no-material-content`, `examined_through: 999999`,
    an empty `unlensed`, and `evidence_refs: [{"name": "x"}]`. That is the exact
    failure this contract exists to close, reproduced one level up inside it.

    Each check below is one of those lines.
    """
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")

    # a range wide enough to cover everything accounts for nothing
    v2_ir(corpus, "wide-ledger", mutate=lambda ir: ir.__setitem__(
        "owner_turn_ledger", [{"source_id": s, "messages": "1-99999",
                               "reason": "no-material-content"}
                              for s in ("CONV-001", "CONV-002")]))
    # ... and neither does one that sweeps in turns that are not the owner's
    v2_ir(corpus, "blanket-ledger", mutate=lambda ir: ir.__setitem__(
        "owner_turn_ledger", [{"source_id": "CONV-002", "messages": "1-2",
                               "reason": "no-material-content"}]))
    # reading past the end of the transcript is not reading
    v2_ir(corpus, "over-read", mutate=lambda ir: ir.__setitem__(
        "progression", [{"source_id": "CONV-001", "examined_through": 999999},
                        {"source_id": "CONV-002", "examined_through": 999999}]))
    # a bare name is not a reference anyone can chase
    v2_ir(corpus, "bare-ref", mutate=lambda ir: ir["items"][0].__setitem__(
        "evidence_refs", [{"name": "x"}]))
    # a reference has to be findable where it says it lives
    v2_ir(corpus, "absent-ref", mutate=lambda ir: ir["items"][0].__setitem__(
        "evidence_refs", [{"name": "the Treaty of Westphalia",
                           "source_id": "CONV-001", "messages": "1"}]))
    # the cross-source question must be answered, not skipped
    v2_ir(corpus, "no-xs", mutate=lambda ir: ir.pop("cross_source", None))
    # a synthesis points at the turns it rests on
    v2_ir(corpus, "xs-unanchored", mutate=lambda ir: ir.__setitem__(
        "cross_source", [{"id": "XS-1", "claim": "c", "authority_class": "derived",
                          "provenance": [{"source_id": "CONV-001"},
                                         {"source_id": "CONV-002"}]}]))
    # an item cannot declare itself replaced by itself
    v2_ir(corpus, "self-supersede", mutate=lambda ir: [
        ir["items"][0].__setitem__("standing", "SUPERSEDED"),
        ir["items"][0].__setitem__("relations", [
            {"rel": "supersedes", "target": ir["items"][0]["id"]}])])
    # a declaration that points at nothing declares nothing
    v2_ir(corpus, "ghost-unlensed", mutate=lambda ir: ir.__setitem__(
        "unlensed", [{"distinction": "d", "items": ["RND-999"]}]))
    # a one-character "quote" matches by accident
    v2_ir(corpus, "tiny-quote", mutate=lambda ir: owner_quote(ir, "RND-001", "."))

    # a lens listing every item discharges the visibility obligation while the
    # coverage table says nothing. Needs more items than the base fixture carries.
    def _dump_all_in_one_lens(ir):
        base = copy.deepcopy(ir["items"][1])
        for k in range(8, 14):
            extra = copy.deepcopy(base)
            extra["id"] = "RND-%03d" % k
            extra["claim"] = "Filler distinction %d." % k
            extra.pop("standing", None)
            ir["items"].append(extra)
        for row in ir["coverage"]:
            row["basis"] = []
        ir["coverage"][0]["basis"] = [i["id"] for i in ir["items"]]
        ir["coverage"][0]["state"] = "PARTIALLY_EXPLORED"
        ir["unlensed"] = []
    v2_ir(corpus, "one-lens", mutate=_dump_all_in_one_lens)

    rc, out = run(corpus, "validate")
    # pinned to the specific complaint: a second check (non-owner turns) also fires
    # on this fixture, so asserting only the code cannot tell the two apart.
    check("K a ledger range past the end of the source is refused",
          bool(re.search(r"FAIL\s+\[wide-ledger\]\s+RND_OWNER_LEDGER_INVALID"
                         r"[^\n]*runs past the source", out)), out)
    check("K a ledger entry covering non-owner turns is refused",
          expect_code(out, "RND_OWNER_LEDGER_INVALID", "blanket-ledger"), out)
    check("K examined_through past the end of the transcript is refused",
          expect_code(out, "RND_PROGRESSION_INVALID", "over-read"), out)
    check("K an unanchored evidence_ref is refused",
          bool(re.search(r"FAIL\s+\[bare-ref\]\s+RND_EVIDENCE_REF_INVALID[^\n]*"
                         r"carries no source_id/messages", out)), out)
    check("K omitting cross_source does not discharge the question",
          expect_code(out, "RND_CROSS_SOURCE_INVALID", "no-xs"), out)
    check("K a cross-source entry with no message range is refused",
          expect_code(out, "RND_CROSS_SOURCE_INVALID", "xs-unanchored"), out)
    check("K an item cannot supersede itself",
          expect_code(out, "RND_STANDING_UNSUPPORTED", "self-supersede"), out)
    check("K an unlensed declaration naming no real item is refused",
          expect_code(out, "RND_UNLENSED_INVALID", "ghost-unlensed"), out)
    check("K a one-character owner quote is not evidence of authorship",
          expect_code(out, "RND_OWNER_AUTHORED_UNQUOTED", "tiny-quote"), out)
    check("K a lens listing every item reports nothing and is refused",
          expect_code(out, "RND_COVERAGE_LENS_VACUOUS", "one-lens"), out)
    check("K control still clean in the same run", control_clean(out), out)


def scenario_l_ordering_and_fail_closed(tmp):
    """L: two ways the guards were more permissive than they looked."""
    corpus = mk_corpus(tmp)
    v2_ir(corpus, "control-ok")

    # An `owner-authored` quote that is pure assistant text from ANOTHER source AND
    # sits in no owner turn it cites used to draw only the cross-source WARN, because
    # that branch preceded the unsupported FAIL — leaving the contract stricter about
    # an invented quote than about laundered assistant text.
    def _launder(ir):
        # cites an OWNER turn of CONV-002, but quotes an ASSISTANT turn of CONV-001
        ir["items"].append({
            "id": "RND-201", "kind": "OWNER_DECISION",
            "claim": "The switch to framework X is settled.", "scope": "infra",
            "provenance": [{"source_id": "CONV-002", "revision": 1,
                            "messages": "1"}],
            "authority_class": "owner", "relations": [], "tags": [],
            "uncertainty": "none",
            "quote": "Johnny decided we will switch to framework X. That is settled.",
            "owner_authority_basis": "owner-authored"})
        ir["owner_turn_ledger"] = []
        _ids = [i["id"] for i in ir["items"]]
        for _k, _row in enumerate(ir["coverage"][:3]):
            _row["basis"] = sorted(set(_row.get("basis") or []) |
                                   {x for _j, x in enumerate(_ids) if _j % 3 == _k})
    v2_ir(corpus, "laundered", mutate=_launder)
    # A transcript whose headers do not number 1..N used to delete the ledger
    # obligation for its whole source: fail-open where v4.0 fails closed.
    corpus2 = mk_corpus(tmp + "-2")
    v2_ir(corpus2, "corrupt", mutate=lambda ir: ir.__setitem__(
        "owner_turn_ledger", []))
    bad = corpus2 / "_projects" / "demo" / "sources" / "CONV-002" / "conversation.md"
    t = bad.read_text(encoding="utf-8").replace("## Meddelande 2 —",
                                                "## Meddelande 7 —")
    bad.write_text(t, encoding="utf-8")

    rc, out = run(corpus, "validate")
    check("L laundered assistant text fails, it does not merely warn",
          expect_code(out, "RND_OWNER_AUTHORED_UNSUPPORTED", "laundered")
          and not re.search(r"WARN\s+\[laundered\]\s+"
                            r"RND_OWNER_AUTHORED_ECHOED_ELSEWHERE", out), out)
    check("L control still clean in the same run", control_clean(out), out)
    rc2, out2 = run(corpus2, "validate")
    check("L a corrupted transcript does not delete the ledger obligation",
          rc2 != 0 and bool(re.search(
              r"FAIL\s+\[corrupt\]\s+RND_OWNER_TURN_UNACCOUNTED[^\n]*"
              r"do not number 1\.\.N", out2)), out2)




def scenario_m_round_two(tmp):
    """M: the second adversarial review's findings.

    Round 1 raised the price of cheap compliance from four lines of JSON to about
    sixty lines of Python. Round 2 showed that still buys a green compile: the
    PUBLISHED 202-item r38 — the one measured at 619 material omissions — passes
    version 2 unchanged after a mechanical upgrade that stamps `owner-directive` on
    every owner decision (no quote test), pastes each range's own URL back as an
    evidence_ref name (so the token test matches by construction), enumerates
    uncited owner turns as `no-material-content`, and sets `examined_through` from
    the file. Each check here is one of the moves that made that possible.
    """
    corpus = mk_corpus(tmp)
    # A long owner turn, so "no-material-content" and the word floor have something
    # real to be wrong about; the base fixture's turns are all one sentence.
    LONG = ("Jag vill att vi bestämmer den här ordningen nu och håller den: "
            "kontraktet ska bära beslutet, inte prosan runt omkring det, och "
            "varje regel ska gå att falsifiera mot källan i stället för mot en "
            "formulering som råkar finnas i filen. Det är viktigt för mig. "
            "Se https://example.invalid/kontrakt-v2 för bakgrunden. "
            "ansvarsfördelningen kontraktsefterlevnaden är kvar att lösa. "
            "Johnny decided we will switch to framework X. That is settled.")
    src = corpus / "_projects" / "demo" / "sources" / "CONV-002" / "conversation.md"
    text = src.read_text(encoding="utf-8").rstrip() + (
        "\n\n---\n\n## Meddelande 3 — Johnny (användare)\n\n%s\n" % LONG)
    src.write_text(text, encoding="utf-8")
    mpath = corpus / "_projects" / "demo" / "project-manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    for entry in manifest["sources"]:
        if entry["source_id"] == "CONV-002":
            rev = entry["revisions"][0]
            rev["sha256"] = _whole_file_sha(text)
            rev["message_count"] = text.count("## Meddelande ")
    write_json(mpath, manifest)

    def _ledger3(ir):
        ir["owner_turn_ledger"].append(
            {"source_id": "CONV-002", "messages": "3",
             "reason": "duplicate-restatement"})
        for prow in ir["progression"]:
            if prow["source_id"] == "CONV-002":
                prow["examined_through"] = 3
    v2_ir(corpus, "control-ok", mutate=_ledger3)
    install_compile(corpus, "v1-here")          # version 1, on purpose

    # excluding most of the corpus excuses you from most of the contract
    def _excl(ir):
        _ledger3(ir)
        for srec in ir["source_set"]["sources"]:
            if srec.get("source_id") == "CONV-002":
                srec["excluded"] = "not read"
        ir["owner_turn_ledger"] = [e for e in ir["owner_turn_ledger"]
                                   if e["source_id"] != "CONV-002"]
        ir["progression"] = [p for p in ir["progression"]
                             if p["source_id"] != "CONV-002"]
    v2_ir(corpus, "mostly-excluded", mutate=_excl)

    # a basis is a claim about what the owner did; show the words
    v2_ir(corpus, "directive-unquoted", mutate=lambda ir: [_ledger3(ir)] + [
        it.__setitem__("owner_authority_basis", "owner-directive")
        or it.__setitem__("quote", "")
        for it in ir["items"] if it["kind"] == "OWNER_DECISION"])
    # a character floor alone let mid-sentence prose stand in for a decision
    def _twoword(ir):
        _ledger3(ir)
        # 26 characters, two words, lifted mid-sentence out of the long owner turn
        for it in ir["items"]:
            if it["id"] == "RND-001":
                it["provenance"] = [{"source_id": "CONV-002", "revision": 1,
                                     "messages": "3"}]
                it["quote"] = "formulering som"
                it["owner_authority_basis"] = "owner-authored"
    v2_ir(corpus, "two-word-quote", mutate=_twoword)
    # the range's own link pasted back as the reference name
    v2_ir(corpus, "url-as-name", mutate=lambda ir: [_ledger3(ir), ir["items"][0].__setitem__(
        "evidence_refs", [{"name": "https://example.com/x",
                           "source_id": "CONV-001", "messages": "1"}])])
    # a name with no token long enough to check was never checked at all
    v2_ir(corpus, "tokenless-ref", mutate=lambda ir: [_ledger3(ir), ir["items"][0].__setitem__(
        "evidence_refs", [{"name": "x y", "source_id": "CONV-001",
                           "messages": "1"}])])
    # everything declared invisible is not a report of blindness
    def _absorb(ir):
        _ledger3(ir)
        base = copy.deepcopy(ir["items"][1])
        for k in range(20, 26):                      # over the 10-item floor
            extra = copy.deepcopy(base)
            extra["id"] = "RND-%03d" % k
            extra["claim"] = "Filler distinction %d." % k
            extra.pop("standing", None)
            ir["items"].append(extra)
        for row in ir["coverage"]:
            row["basis"] = []
            row["state"] = "UNKNOWN"
            row["note"] = ""
        ir["unlensed"] = [{"distinction": "everything",
                           "items": [i["id"] for i in ir["items"]]}]
    v2_ir(corpus, "unlensed-absorbs", mutate=_absorb)
    # two items superseding each other say nothing is live
    v2_ir(corpus, "supersede-cycle", mutate=lambda ir: [
        _ledger3(ir),
        ir["items"][1].__setitem__("standing", "SUPERSEDED"),
        ir["items"][2].__setitem__("standing", "SUPERSEDED"),
        ir["items"][1].__setitem__("relations", [
            {"rel": "supersedes", "target": ir["items"][2]["id"]}]),
        ir["items"][2].__setitem__("relations", [
            {"rel": "supersedes", "target": ir["items"][1]["id"]}])])
    # two progression rows for one source: last-wins hid the honest number
    v2_ir(corpus, "dup-progression", mutate=lambda ir: [
        _ledger3(ir),
        ir["progression"].append({"source_id": "CONV-001",
                                  "examined_through": 5})])   # identical, not a clash
    # a turn with real prose is not "no-material-content"
    # the long owner turn, honestly labelled: 300+ characters carrying no material
    # distinction is exactly what `no-material-content` is for
    v2_ir(corpus, "honest-ledger", mutate=lambda ir: ir.__setitem__(
        "owner_turn_ledger", [{"source_id": "CONV-002", "messages": "1",
                               "reason": "duplicate-restatement"},
                              {"source_id": "CONV-002", "messages": "3",
                               "reason": "no-material-content"}]))
    # a real project name, verbatim in the cited range, too short to tokenise
    v2_ir(corpus, "short-ref-name", mutate=lambda ir: [
        _ledger3(ir),
        ir["items"][0].__setitem__(
            "evidence_refs", [{"name": "Ägarplanet",
                               "source_id": "CONV-001", "messages": "1"}])])
    # 16 characters, the most decision-like sentence in its turn
    v2_ir(corpus, "short-owner-quote", mutate=lambda ir: [
        _ledger3(ir), owner_quote(ir, "RND-001", "Det är beslutat.")])


    # ONLY the word floor: 40 characters, two words
    def _wordfloor(ir):
        _ledger3(ir)
        for it in ir["items"]:
            if it["id"] == "RND-001":
                it["provenance"] = [{"source_id": "CONV-002", "revision": 1,
                                     "messages": "3"}]
                it["quote"] = "ansvarsfördelningen kontraktsefterlevnaden"
                it["owner_authority_basis"] = "owner-authored"
    v2_ir(corpus, "word-floor-only", mutate=_wordfloor)

    # ONLY the character floor: three words, 14 characters
    def _charfloor(ir):
        _ledger3(ir)
        for it in ir["items"]:
            if it["id"] == "RND-001":
                it["provenance"] = [{"source_id": "CONV-002", "revision": 1,
                                     "messages": "3"}]
                it["quote"] = "det, och varje"
                it["owner_authority_basis"] = "owner-authored"
    v2_ir(corpus, "char-floor-only", mutate=_charfloor)

    # ONLY the bare-URL rule: the URL really is in the cited range, so the token
    # test would pass it
    v2_ir(corpus, "url-in-range", mutate=lambda ir: [
        _ledger3(ir),
        ir["items"][0].__setitem__(
            "evidence_refs", [{"name": "https://example.invalid/kontrakt-v2",
                               "source_id": "CONV-002", "messages": "3"}])])

    # ONLY the echo-scan scoping: the quote sits in a cited owner turn of CONV-002
    # AND in an assistant turn of CONV-001, and the item ALSO cites an unrelated
    # owner turn in CONV-001 — the move that used to silence the warning entirely
    def _echo_bypass(ir):
        _ledger3(ir)
        for it in ir["items"]:
            if it["id"] == "RND-001":
                it["provenance"] = [
                    {"source_id": "CONV-002", "revision": 1, "messages": "3"},
                    {"source_id": "CONV-001", "revision": 1, "messages": "1"}]
                it["quote"] = ("Johnny decided we will switch to framework X. "
                               "That is settled.")
                it["owner_authority_basis"] = "owner-authored"
    v2_ir(corpus, "echo-bypass", mutate=_echo_bypass)

    rc, out = run(corpus, "validate")
    check("M every owner basis must show the owner's words",
          expect_code(out, "RND_OWNER_BASIS_UNQUOTED", "directive-unquoted"), out)
    check("M a two-word owner-authored quote is refused",
          expect_code(out, "RND_OWNER_AUTHORED_UNQUOTED", "two-word-quote"), out)
    check("M an evidence_ref that is just a URL is refused",
          expect_code(out, "RND_EVIDENCE_REF_INVALID", "url-as-name"), out)
    # pinned to its own message: the weak-match rule also fires on this input, so
    # asserting the code alone cannot tell the two branches apart
    check("M declaring the whole compile unlensed is refused",
          expect_code(out, "RND_UNLENSED_INVALID", "unlensed-absorbs"), out)
    check("M a supersession CYCLE is as vacuous as superseding yourself",
          expect_code(out, "RND_STANDING_UNSUPPORTED", "supersede-cycle"), out)
    check("M a version-1 compile is told the semantic rules did not apply",
          bool(re.search(r"WARN\s+\[v1-here\]\s+RND_COMPILE_NOT_SEMANTIC",
                         out)), out)
    # --- false-positive regressions -------------------------------------------
    # Three rules were REMOVED in round three because an independent review showed
    # they fired on honest work: an evidence_ref token-match test that rejected
    # `Gauntlet` and `Ägarplanet`, ledger reason content checks that refused a
    # truthful `no-material-content`, and a 24-character owner-quote floor that
    # refused "Det är beslutat.". These assert they stay gone.
    check("M a short verbatim reference name is accepted",
          not expect_code(out, "RND_EVIDENCE_REF_INVALID", "short-ref-name"), out)
    check("M a truthful no-material-content ledger entry is accepted",
          not expect_code(out, "RND_OWNER_LEDGER_REASON_CONTRADICTED",
                          "honest-ledger")
          and not expect_code(out, "RND_OWNER_TURN_UNACCOUNTED", "honest-ledger"),
          out)
    check("M a short genuine owner sentence is accepted as owner-authored",
          not expect_code(out, "RND_OWNER_AUTHORED_UNQUOTED", "short-owner-quote"),
          out)
    check("M identical repeated progression rows are accepted",
          not expect_code(out, "RND_PROGRESSION_INVALID", "dup-progression"), out)
    check("M a two-source project with one uncaptured source still passes",
          not expect_code(out, "RND_SOURCE_SET_MOSTLY_EXCLUDED",
                          "mostly-excluded"), out)

    check("M the CHARACTER floor bites on its own",
          expect_code(out, "RND_OWNER_AUTHORED_UNQUOTED", "char-floor-only"), out)
    check("M the WORD floor bites on its own, not only the character floor",
          expect_code(out, "RND_OWNER_AUTHORED_UNQUOTED", "word-floor-only"), out)
    check("M a bare URL is refused even when it IS in the cited range",
          expect_code(out, "RND_EVIDENCE_REF_INVALID", "url-in-range"), out)
    check("M citing an unrelated turn in the echoing source does not buy silence",
          bool(re.search(r"WARN\s+\[echo-bypass\]\s+"
                         r"RND_OWNER_AUTHORED_ECHOED_ELSEWHERE", out)), out)
    check("M control still clean in the same run", control_clean(out), out)




def scenario_n_ledger_is_a_ratio_not_a_word(tmp):
    """N: explaining away almost every owner turn is not compiling.

    Content checks on ledger REASONS were tried and removed: they refused a truthful
    `no-material-content` on a 267-character turn while leaving `question-only` and
    `duplicate-restatement` unchecked, so relabelling one word took a semantically
    empty corpus from 257 findings to zero. What replaces them is a ratio, which no
    choice of word can move: a compile may explain why PARTICULAR owner turns are
    uncited; a compile that explains away essentially all of them has not read the
    corpus.

    Calibration on the real thing: the published r38 ledgers 19% of its 581 owner
    turns, the remediated candidate 18%; the empty compiles ledger 98%+.
    """
    corpus = mk_corpus(tmp)
    src = corpus / "_projects" / "demo" / "sources" / "CONV-002" / "conversation.md"
    body = src.read_text(encoding="utf-8").rstrip()
    for n in range(3, 25):                       # 22 more owner turns
        body += ("\n\n---\n\n## Meddelande %d — Johnny (användare)\n\n"
                 "Kort kommentar nummer %d.\n" % (n, n))
    src.write_text(body, encoding="utf-8")
    mpath = corpus / "_projects" / "demo" / "project-manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    for entry in manifest["sources"]:
        if entry["source_id"] == "CONV-002":
            rev = entry["revisions"][0]
            rev["sha256"] = _whole_file_sha(body)
            rev["message_count"] = body.count("## Meddelande ")
    write_json(mpath, manifest)

    def _base(ir):
        ir["progression"] = [{"source_id": "CONV-001", "examined_through": 5},
                             {"source_id": "CONV-002", "examined_through": 24}]

    # honest: the new turns are ledgered, but the corpus's owner turns are mostly
    # still CITED by items
    def _honest(ir):
        _base(ir)
        ir["owner_turn_ledger"] = [
            {"source_id": "CONV-002", "messages": "1",
             "reason": "duplicate-restatement"}] + [
            {"source_id": "CONV-002", "messages": str(n),
             "reason": "acknowledgement-only"} for n in range(3, 15)]
    v2_ir(corpus, "ledger-honest", mutate=_honest)

    # empty: every owner turn in the corpus explained away
    def _sweep(ir):
        _base(ir)
        ir["owner_turn_ledger"] = [
            {"source_id": "CONV-001", "messages": str(n),
             "reason": "question-only"} for n in (1, 3, 5)] + [
            {"source_id": "CONV-002", "messages": str(n),
             "reason": "question-only"} for n in [1] + list(range(3, 25))]
    v2_ir(corpus, "ledger-sweep", mutate=_sweep)

    rc, out = run(corpus, "validate")
    check("N ledgering essentially every owner turn is refused",
          expect_code(out, "RND_OWNER_TURNS_MOSTLY_LEDGERED", "ledger-sweep"), out)
    # the sweep uses `question-only` throughout — a reason with no content check —
    # so this verdict cannot be moved by choosing a different word
    check("N the verdict does not depend on which reason word was chosen",
          not expect_code(out, "RND_OWNER_LEDGER_REASON_INVALID", "ledger-sweep")
          and expect_code(out, "RND_OWNER_TURNS_MOSTLY_LEDGERED", "ledger-sweep"),
          out)
    check("N a compile that ledgers some turns and cites the rest is accepted",
          not expect_code(out, "RND_OWNER_TURNS_MOSTLY_LEDGERED", "ledger-honest"),
          out)


def main():
    scenarios = [
        scenario_version_seal,
        scenario_a_short_reversal_survives_volume,
        scenario_b_relayed_text_is_not_owner_authored,
        scenario_c_direction_does_not_own_mechanism,
        scenario_d_assistant_claim_is_not_owner,
        scenario_b2_relay_requires_order,
        scenario_d_progression,
        scenario_e_negative_knowledge,
        scenario_f_evidence_survives_the_conclusion,
        scenario_g_lens_blindness,
        scenario_h_cross_source_without_false_consensus,
        scenario_ij_volume_buys_nothing,
        scenario_k_cheap_compliance_is_refused,
        scenario_l_ordering_and_fail_closed,
        scenario_m_round_two,
        scenario_n_ledger_is_a_ratio_not_a_word,
    ]
    for scenario in scenarios:
        tmp = tempfile.mkdtemp(prefix="intake-rnd41-")
        try:
            print("\n=== %s ===" % scenario.__name__)
            scenario(tmp)
        except Exception as exc:
            check("%s (scenario raised)" % scenario.__name__, False,
                  "%s: %s" % (type(exc).__name__, exc))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [(n, d) for n, ok, d in RESULTS if not ok]
    print("\n%d/%d checks passed" % (len(RESULTS) - len(failed), len(RESULTS)))
    for n, d in failed:
        print("FAILED: %s\n        %s" % (n, str(d)[:400]))
    if len(RESULTS) < MIN_CHECKS:
        print("FAIL: only %d checks executed (floor %d) — a suite that runs "
              "nothing proves nothing" % (len(RESULTS), MIN_CHECKS))
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
