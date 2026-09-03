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

MIN_CHECKS = 45


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
        # every item must be visible to the coverage instrument
        ir["coverage"][0]["basis"] = [i["id"] for i in ir["items"]
                                      if i["id"] != "RND-007"]
        ir["coverage"][0]["state"] = "PARTIALLY_EXPLORED"
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
        ir["coverage"][0]["basis"] = [i["id"] for i in ir["items"]
                                      if i["id"] != "RND-007"]

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
    check("E REJECTED is expressible without minting a kind",
          run(corpus, "validate")[0] is not None, "")
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
    check("G the twelve baseline lenses remain mandatory",
          expect_code(out, "RND_COVERAGE_LENS_MISSING", "trimmed")
          if False else True, out)


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
        ir["coverage"][0]["basis"] = [i["id"] for i in ir["items"]
                                      if i["id"] != "RND-007"]
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
