#!/usr/bin/env python3
"""v4.2 attachment EVIDENCE suite — proving ACT-05's vacuity is actually gone.

The attachment qualification recorded ACT-05, "every material attachment has an
evidence_ref", as VACUOUS BY CONSTRUCTION. The IR had no attachment field, so the
rule could not activate on any input whatsoever; its permanent green measured
nothing at all.

Adding an attachment field to the IR does not by itself fix that. A representation
nobody can trip is the same vacuity wearing a schema. So this suite exists to prove
the opposite of a green: that each new IR-side rule FIRES on a real compile, that a
control differing in exactly one respect does NOT fire, and that the activation is
counted rather than assumed.

The rules under test:

  RND_ATTACHMENT_REF_INVALID               attachment provenance that binds to nothing
  RND_ATTACHMENT_EVIDENCE_ABSENT_UNMARKED  an absent document reading like a read one
  RND_ATTACHMENT_UNCERTAINTY_INVERTED      AMR-001: missing bytes licensing confidence
  RND_ATTACHMENT_AUTHORITY_OVERSTATED      describing an unopenable document as evidence
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from test_rnd_v4 import (  # noqa: E402
        check, mk_corpus, run, RESULTS,
    )
    from test_rnd_v41 import v2_ir  # noqa: E402
except SystemExit:
    # See the note in test_attachment_v42.py: a stubbed module exits 0 during import.
    print("FAIL  a module under test exited during import — this suite ran nothing")
    raise SystemExit(1)

import tempfile  # noqa: E402

MIN_CHECKS = 11
ACTIVATION = {}


def add_ref(ir, iid, **ref):
    for it in ir["items"]:
        if it["id"] == iid:
            base = {"name": "the phase-0 owner-review archive the owner uploaded",
                    "source_id": "CONV-001", "messages": "1"}
            base.update(ref)
            it["evidence_refs"] = [base]


def expect(corpus, cid, code, name, present=True, mutate=None):
    """Assert a code fires ON THIS COMPILE, and count the activation.

    Scoped to the slug on purpose. `validate` walks every compile in the corpus, and
    the first draft matched the bare code anywhere in the output - so a finding
    legitimately raised by an EARLIER adversarial fixture satisfied a later control,
    and two controls "passed" for a reason that had nothing to do with them. Findings
    print as `FAIL  [slug]  CODE`, so the slug is what makes the assertion about the
    fixture actually under test.
    """
    v2_ir(corpus, cid, mutate=mutate)
    rc, out = run(corpus, "validate")
    attached = re.search(r"^\s*(?:FAIL|WARN)\s+\[%s\]\s+%s\b"
                         % (re.escape(cid), re.escape(code)), out, re.M)
    hit = bool(attached)
    ACTIVATION.setdefault(code, 0)
    if hit:
        ACTIVATION[code] += 1
    check(name, hit is present,
          "rc=%d %s %s for [%s]\n%s"
          % (rc, code, "missing" if present else "unexpectedly present", cid,
             "\n".join(l for l in out.splitlines() if "[%s]" % cid in l)[:900]))


def main():
    with tempfile.TemporaryDirectory() as td:
        corpus = mk_corpus(Path(td))

        # --- the representation exists and a correct ref is accepted ---------
        expect(corpus, "att-control",
               "RND_ATTACHMENT_REF_INVALID",
               "IR1 CONTROL: a captured attachment ref is accepted",
               present=False,
               mutate=lambda ir: add_ref(
                   ir, "RND-001", attachment_id="ATT-001-001",
                   attachment_capture="RECOVERED_EXACT",
                   attachment_sha256="2d8cbc39da762cc088ff170de24e9f3f2513de6c8ae5"
                                     "8ba6003f4e34abc6e20d"))

        # --- binding ---------------------------------------------------------
        expect(corpus, "att-nobind", "RND_ATTACHMENT_REF_INVALID",
               "IR2 attachment detail with no attachment_id is refused",
               mutate=lambda ir: add_ref(ir, "RND-001",
                                         attachment_capture="UNAVAILABLE"))

        expect(corpus, "att-badstate", "RND_ATTACHMENT_REF_INVALID",
               "IR3 an invented attachment_status is refused",
               mutate=lambda ir: add_ref(ir, "RND-001",
                                         attachment_id="ATT-001-001",
                                         attachment_capture="PROBABLY_READ"))

        expect(corpus, "att-hash-nobytes", "RND_ATTACHMENT_REF_INVALID",
               "IR4 a sha256 on an attachment nobody holds is refused",
               mutate=lambda ir: add_ref(ir, "RND-001",
                                         attachment_id="ATT-001-001",
                                         attachment_capture="UNAVAILABLE",
                                         source_evidence_absent=True,
                                         attachment_sha256="a" * 64))

        # --- absence must be visible ----------------------------------------
        expect(corpus, "att-unmarked", "RND_ATTACHMENT_EVIDENCE_ABSENT_UNMARKED",
               "IR5 an unavailable attachment not marked absent is refused",
               mutate=lambda ir: add_ref(ir, "RND-001",
                                         attachment_id="ATT-001-001",
                                         attachment_capture="UNAVAILABLE"))

        expect(corpus, "att-marked", "RND_ATTACHMENT_EVIDENCE_ABSENT_UNMARKED",
               "IR6 CONTROL: the same ref marked source_evidence_absent is accepted",
               present=False,
               mutate=lambda ir: add_ref(ir, "RND-001",
                                         attachment_id="ATT-001-001",
                                         attachment_capture="UNAVAILABLE",
                                         source_evidence_absent=True))

        # --- AMR-001: no semantic completion of an absent source -------------
        def _invert(ir):
            add_ref(ir, "RND-001", attachment_id="ATT-001-001",
                    attachment_capture="UNAVAILABLE", source_evidence_absent=True)
            for it in ir["items"]:
                if it["id"] == "RND-001":
                    it["uncertainty"] = "low — the review returned negative-rule " \
                                        "corrections"
                    it["authority_class"] = "derived"
        expect(corpus, "att-inverted", "RND_ATTACHMENT_UNCERTAINTY_INVERTED",
               "IR7 AMR-001: an absent attachment may not license low uncertainty",
               mutate=_invert)

        def _honest(ir):
            add_ref(ir, "RND-001", attachment_id="ATT-001-001",
                    attachment_capture="UNAVAILABLE", source_evidence_absent=True)
            for it in ir["items"]:
                if it["id"] == "RND-001":
                    it["uncertainty"] = "high — the document's bytes are unavailable; " \
                                        "only its existence and the reported outcome " \
                                        "are proven"
                    it["authority_class"] = "derived"
        expect(corpus, "att-honest", "RND_ATTACHMENT_UNCERTAINTY_INVERTED",
               "IR8 CONTROL: the same item with honest uncertainty is accepted",
               present=False, mutate=_honest)

        def _authority(ir):
            add_ref(ir, "RND-001", attachment_id="ATT-001-001",
                    attachment_capture="CAPTURED_REFERENCE_ONLY",
                    source_evidence_absent=True)
            for it in ir["items"]:
                if it["id"] == "RND-001":
                    it["uncertainty"] = "high — bytes absent"
                    it["authority_class"] = "evidence"
        expect(corpus, "att-authority", "RND_ATTACHMENT_AUTHORITY_OVERSTATED",
               "IR9 describing an unopenable document as evidence is refused",
               mutate=_authority)

        def _mixed(ir):
            for it in ir["items"]:
                if it["id"] == "RND-001":
                    it["evidence_refs"] = [
                        {"name": "the archive the owner uploaded, recovered exactly",
                         "source_id": "CONV-001", "messages": "1",
                         "attachment_id": "ATT-001-001",
                         "attachment_capture": "RECOVERED_EXACT",
                         "attachment_sha256": "b" * 64},
                        {"name": "the master plan document, bytes unavailable",
                         "source_id": "CONV-001", "messages": "1",
                         "attachment_id": "ATT-001-002",
                         "attachment_capture": "UNAVAILABLE",
                         "source_evidence_absent": True}]
                    it["uncertainty"] = "low — one attachment is in hand"
                    it["authority_class"] = "evidence"
        expect(corpus, "att-mixed", "RND_ATTACHMENT_UNCERTAINTY_INVERTED",
               "IR10 CONTROL: an item with at least one attachment IN HAND may be "
               "confident", present=False, mutate=_mixed)

    print("\n" + "=" * 72)
    print("ACTIVATION REPORT — ACT-05 was vacuous by construction; this is the proof")
    print("it is not vacuous any more")
    print("=" * 72)
    dead = [r for r, n in ACTIVATION.items() if n == 0]
    for rule in sorted(ACTIVATION):
        print("  %-46s activated %d time(s)%s"
              % (rule, ACTIVATION[rule],
                 "   <-- NEVER FIRED" if ACTIVATION[rule] == 0 else ""))
    check("ACTIVATION  every IR attachment rule actually fired", not dead,
          "never activated: %s" % dead)

    passed = [r for r in RESULTS if r[1]]
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d passed, %d failed, %d checks total"
          % (len(passed), len(failed), len(RESULTS)))
    if len(RESULTS) < MIN_CHECKS:
        print("SUITE UNDER-RAN: %d < floor %d" % (len(RESULTS), MIN_CHECKS))
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
