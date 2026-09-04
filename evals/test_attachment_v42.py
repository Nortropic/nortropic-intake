#!/usr/bin/env python3
"""v4.2 attachment source-surface suite — adversarial, with activation evidence.

The r38 remediation before this one learned the lesson this file is built around:

    `0 false positives` can be meaningless if the evaluated population never
    exercised the rule.

The attachment qualification then found the same shape one level worse. ACT-05,
"every material attachment has an evidence_ref", was VACUOUS BY CONSTRUCTION — the
IR carried no attachment field at all, so nothing could ever have activated it, and
its permanent green said nothing whatsoever.

So every check here does two jobs. It asserts the failing state FAILS, and it
asserts a control that differs in exactly one respect PASSES. At the end the suite
prints an ACTIVATION REPORT: for each rule, how many fixtures actually tripped it.
A rule with zero activations is reported as a suite FAILURE, not quietly skipped —
because a check that has never fired is a check nobody has tested.

What this suite cannot do, stated rather than implied: it cannot prove that any
attachment MEANS what an IR item says it means. A static validator proves structural
and provenance properties of a source surface. Semantic coverage still requires
independent source-first falsification against the real bytes.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

# A stubbed module is `import sys; sys.exit(0)`, which fires DURING import and takes
# this process down with status 0 — a suite that executed nothing, exiting green. The
# repo's mutation guard caught exactly that here, so the import is trapped: a module
# that exits while being imported is a lobotomised module, and that is a suite
# FAILURE, never a pass. The `hasattr` sweep catches the other shape the repo has
# already learned about — a stub that imports cleanly but answers nothing.
def _import_or_fail():
    try:
        import attachment_surface as _att
        import intake_common as _ic
    except SystemExit:
        print("FAIL  a module under test exited during import — it is stubbed or "
              "broken, so this suite ran nothing and must not exit 0")
        raise SystemExit(1)
    for mod, names in ((_att, ("declared_attachments", "observed_signals",
                               "reconcile", "validate_manifest",
                               "observed_lower_bound", "named_upload_identities")),
                       (_ic, ("attachment_bytes_available", "full_source_capture",
                              "source_surface_identity", "transcript_source_sha256",
                              "sha256_text"))):
        missing = [n for n in names if not hasattr(mod, n)]
        if missing:
            print("FAIL  %s is missing %s — an inert module cannot certify anything"
                  % (getattr(mod, "__name__", mod), missing))
            raise SystemExit(1)
    return _att, _ic


att, _ic = _import_or_fail()
attachment_bytes_available = _ic.attachment_bytes_available
full_source_capture = _ic.full_source_capture
sha256_text = _ic.sha256_text
source_surface_identity = _ic.source_surface_identity
transcript_source_sha256 = _ic.transcript_source_sha256

PASSED, FAILED = [], []
ACTIVATION = {}
MIN_CHECKS = 36


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print("%s %s%s" % ("PASS" if ok else "FAIL", name,
                       "" if ok else "\n      " + str(detail)[:900]))


def activates(rule, findings, name, expect=True):
    """Assert a named rule fires (or does not), and record the activation."""
    codes = [f.code for f in findings]
    hit = rule in codes
    ACTIVATION.setdefault(rule, 0)
    if hit:
        ACTIVATION[rule] += 1
    check(name, hit is expect,
          "codes=%s expected %s to be %s" % (codes, rule, "present" if expect else "absent"))
    return hit


# --------------------------------------------------------------- fixtures --

def transcript(messages, note=""):
    """A capture in the corpus's own shape: builder header, then the message region."""
    head = ["# Fixture — fullständigt transkript", "",
            "**Källprojekt:** Fixture", "**Exportdatum:** 2026-09-04",
            "**Antal meddelanden:** %d" % len(messages), ""]
    if note:
        head += ["> Notis: %s" % note, ""]
    head += ["---", ""]
    body = []
    for i, (role, text) in enumerate(messages, 1):
        body += ["## Meddelande %d — %s" % (i, role), "", text, "", "---", ""]
    return "\n".join(head + body)


CLEAN = transcript([("Johnny (användare)", "Vad tycker du om planen?"),
                    ("ChatGPT (assistent)", "Den håller.")])

WITH_CHIPS = transcript(
    [("Johnny (användare)", "Här är underlaget."),
     ("ChatGPT (assistent)", "Jag har läst dokumentet och sammanfattar det.")],
    note="2 bilagor inventerade (plan.md, bilaga.pdf); innehållet ej infångat i svepet.")

# The AMR-004 shape, generalised: the body announces uploads by (name, stamp) that
# the header's count does not contain. No filename in this fixture appears in any
# rule — the detector keys on the SHAPE, which is why it generalises.
UNDERCOUNT = transcript(
    [("Johnny (användare)", "Kolla de två filerna."),
     ("ChatGPT (assistent)",
      "De exakta två filerna är: - `Inklistrad text.txt`, uppladdad 24 aug "
      "19:38:58 — börjar med masterplanen. - `Inklistrad text.txt`, uppladdad "
      "24 aug 19:41:04 — fortsättningen.")],
    note="1 bilagor inventerade (annat.md); innehållet ej infångat i svepet.")


def att_row(aid, status, material="NON_MATERIAL", **kw):
    row = {"attachment_id": aid, "ordinal": int(aid.rsplit("-", 1)[1]),
           "capture_status": status, "materiality": material}
    row.update(kw)
    return row


def manifest(rows, recon="AGREE", declared=None, **kw):
    d = {"attachment_manifest_version": 1, "source_id": "CONV-001", "revision": 1,
         "reconciliation": recon, "attachments": rows}
    if declared is not None:
        d["declared_count"] = declared
    d.update(kw)
    return d


def vm(data, corpus=None):
    return att.validate_manifest(data, "CONV-001", 1, "fixture", corpus)


# ============================ A. source identity is blind ====================
print("\n--- A. the defect: body identity cannot see the attachment surface ---")

mutated = WITH_CHIPS.replace("2 bilagor inventerade", "0 bilagor inventerade")
check("A1  the mutation actually applied", mutated != WITH_CHIPS)
check("A2  body identity is IDENTICAL after the declared count is falsified",
      transcript_source_sha256(WITH_CHIPS) == transcript_source_sha256(mutated),
      "this is the r38 defect, asserted so it cannot silently return")

stripped = "\n".join(l for l in WITH_CHIPS.split("\n") if not l.startswith("> Notis:"))
check("A3  body identity is IDENTICAL after the whole chip note is deleted",
      transcript_source_sha256(WITH_CHIPS) == transcript_source_sha256(stripped))

rec_full = [{"source_id": "CONV-001", "revision": 1,
             "source_sha256": transcript_source_sha256(WITH_CHIPS),
             "declared_count": 2, "observed_count": 2, "reconciliation": "AGREE",
             "attachments": [att_row("ATT-001-001", "CAPTURED_CONTENT",
                                     content_sha256="a" * 64)]}]
rec_gone = [dict(rec_full[0], attachments=[att_row("ATT-001-001", "UNAVAILABLE")])]
check("A4  SOURCE-SURFACE identity DIFFERS when the same body loses its bytes",
      source_surface_identity(rec_full)[0] != source_surface_identity(rec_gone)[0],
      "the new identity must see exactly what the old one could not")
check("A5  and the body digest is unchanged across that same transition",
      rec_full[0]["source_sha256"] == rec_gone[0]["source_sha256"])

rec_swapped = [dict(rec_full[0], attachments=[
    att_row("ATT-001-001", "CAPTURED_CONTENT", content_sha256="b" * 64)])]
check("A6  attachment REPLACED while the body is untouched moves the surface identity",
      source_surface_identity(rec_full)[0] != source_surface_identity(rec_swapped)[0])
check("A7  surface identity is order-independent (sorted canonical lines)",
      source_surface_identity(rec_full + rec_gone)[0]
      == source_surface_identity(rec_gone + rec_full)[0])

# ============================ B. declared vs observed ========================
print("\n--- B. declared and observed evidence are reconciled, never assumed ---")

d0, _ = att.declared_attachments(CLEAN)
d2, _ = att.declared_attachments(WITH_CHIPS)
check("B1  a silent header reads as None, never as zero", d0 is None)
check("B2  a declared count is read from the header", d2 == 2, d2)

sig_u = att.observed_signals(UNDERCOUNT)
ids = sig_u["named_upload_identities"]
check("B3  two same-named uploads at different stamps are TWO identities",
      len(ids) == 2, ids)
recon, floor = att.reconcile(*(att.declared_attachments(UNDERCOUNT)[0], sig_u))
check("B4  declared count lower than the observed upload evidence → DISAGREE",
      recon == "DISAGREE", (recon, floor))

recon_ok, _ = att.reconcile(2, att.observed_signals(WITH_CHIPS),
                            [{"original_filename": "plan.md"},
                             {"original_filename": "bilaga.pdf"}])
check("B5  CONTROL: a declaration covering what the body evidences → not DISAGREE",
      recon_ok != "DISAGREE", recon_ok)

covered, _ = att.reconcile(
    2, sig_u, [{"original_filename": "Inklistrad text.txt", "uploaded_at": "19:38:58"},
               {"original_filename": "Inklistrad text.txt", "uploaded_at": "19:41:04"}])
check("B6  CONTROL: the same body reconciles once both identities are declared",
      covered != "DISAGREE", covered)

# Found by an adversarial pass over _covered, not by a fixture that expected it.
undated, _ = att.reconcile(1, sig_u, [{"original_filename": "Inklistrad text.txt"}])
check("B7  an UNDATED declaration cannot cover two DATED uploads of that name",
      undated == "DISAGREE",
      "`\"\" in stamp` is always true, so one undated entry silently covered both "
      "AMR-004 uploads and dissolved the contradiction")
check("B8  CONTROL: an undated declaration still covers an undated observation",
      att._covered(("plan.md", ""), [{"original_filename": "plan.md"}]) is True)

silent = att.reconcile(None, {"filecite_sites": 9, "named_upload_identities": []})[0]
check("B9  a SILENT header over a file-citing body is UNKNOWN, never DISAGREE",
      silent == "UNKNOWN",
      "silence is not a claim; accusing it would flood the real findings")

# The corpus's own negative control, in miniature: many discussed paths, no uploads.
paths = transcript([("Johnny (användare)",
                     "Se ~/nortropic/a.md och ~/nortropic/b.md och /Users/x/c.md")])
check("B10 paths merely DISCUSSED do not count as uploads",
      att.observed_lower_bound(att.observed_signals(paths)) == 0,
      "the first draft scored the real CONV-008 negative control at 7 phantom uploads")

# ============================ C. capture states ==============================
print("\n--- C. only bytes in hand count as bytes in hand ---")

for st, expect in (("CAPTURED_CONTENT", True), ("RECOVERED_EXACT", True),
                   ("RECOVERED_DUPLICATE", True), ("CAPTURED_REFERENCE_ONLY", False),
                   ("DUPLICATE", False), ("UNAVAILABLE", False), ("UNKNOWN", False)):
    check("C:%-24s bytes_available == %s" % (st, expect),
          attachment_bytes_available(st) is expect)

activates("ATTACHMENT_HASH_WITHOUT_BYTES",
          vm(manifest([att_row("ATT-001-001", "UNAVAILABLE", content_sha256="c" * 64)])),
          "C8  a content hash on an attachment with no bytes is refused")
activates("ATTACHMENT_BYTES_UNHASHED",
          vm(manifest([att_row("ATT-001-001", "CAPTURED_CONTENT")])),
          "C9  bytes claimed present with no hash are refused")
activates("ATTACHMENT_RECOVERY_UNPROVENANCED",
          vm(manifest([att_row("ATT-001-001", "RECOVERED_EXACT",
                               content_sha256="d" * 64)])),
          "C10 a recovered attachment with no provenance is refused")
activates("ATTACHMENT_RECOVERY_UNPROVENANCED",
          vm(manifest([att_row("ATT-001-001", "RECOVERED_EXACT", content_sha256="d" * 64,
                               recovery_provenance="owner msg 29 names the path; "
                                                   "msg 32 records ARCHIVE_SHA256")])),
          "C11 CONTROL: a recovered attachment WITH provenance is accepted", expect=False)
activates("ATTACHMENT_DUPLICATE_UNBOUND",
          vm(manifest([att_row("ATT-001-001", "DUPLICATE")])),
          "C12 a duplicate naming nothing it duplicates is refused")
activates("ATTACHMENT_DUPLICATE_UNBOUND",
          vm(manifest([att_row("ATT-001-001", "DUPLICATE", duplicate_of="ATT-001-002")])),
          "C13 CONTROL: a bound duplicate is accepted", expect=False)
activates("ATTACHMENT_CAPTURE_STATE_INVALID",
          vm(manifest([att_row("ATT-001-001", "PROBABLY_FINE")])),
          "C14 an invented capture state is refused")

# ============================ D. completeness ================================
print("\n--- D. FULL_SOURCE_CAPTURE is derived, and cannot be talked into YES ---")

check("D1  a MATERIAL attachment without bytes forces NO",
      full_source_capture([att_row("ATT-001-001", "UNAVAILABLE", "MATERIAL")],
                          "AGREE", 1) == "NO")
check("D2  a DISAGREE surface forces NO",
      full_source_capture([att_row("ATT-001-001", "CAPTURED_CONTENT", "MATERIAL",
                                   content_sha256="a" * 64)], "DISAGREE", 1) == "NO")
check("D3  a NON_MATERIAL attachment without bytes is UNKNOWN, not NO and not YES",
      full_source_capture([att_row("ATT-001-001", "UNAVAILABLE", "NON_MATERIAL")],
                          "AGREE", 1) == "UNKNOWN")
check("D4  every declared attachment captured and reconciled → YES",
      full_source_capture([att_row("ATT-001-001", "CAPTURED_CONTENT", "MATERIAL",
                                   content_sha256="a" * 64)], "AGREE", 1) == "YES")
# The vacuity that this suite's own subject nearly reproduced.
check("D5  55 declared and 0 described is UNKNOWN, never YES",
      full_source_capture([], "AGREE", 55) == "UNKNOWN",
      "an empty list has no member lacking bytes; the vacuous truth read as complete")
check("D6  nothing declared and nothing described is UNKNOWN, not YES",
      full_source_capture([], "AGREE", None) == "UNKNOWN")
activates("FULL_SOURCE_CAPTURE_OVERSTATED",
          vm(manifest([att_row("ATT-001-001", "UNAVAILABLE", "MATERIAL")],
                      declared=1, full_source_capture="YES")),
          "D7  a manifest asserting YES over unavailable material is refused")

# ============================ E. revision binding ============================
print("\n--- E. attachment surface is a property of a REVISION ---")

r1 = {"source_id": "CONV-001", "revision": 1, "source_sha256": "e" * 64,
      "declared_count": 54, "observed_count": 1, "reconciliation": "AGREE",
      "attachments": []}
r2 = dict(r1, revision=2, declared_count=55)
check("E1  a stale count carried across a revision moves the surface identity",
      source_surface_identity([r1])[0] != source_surface_identity([r2])[0],
      "CONV-001 really does declare 54 at r1 and 55 at r2 in the frozen corpus")
activates("ATTACHMENT_MANIFEST_REVISION_MISMATCH",
          att.validate_manifest(manifest([], declared=0), "CONV-001", 2, "fixture"),
          "E2  a manifest bound to the wrong revision is refused")
activates("ATTACHMENT_MANIFEST_SOURCE_MISMATCH",
          att.validate_manifest(manifest([], declared=0), "CONV-999", 1, "fixture"),
          "E3  a manifest bound to the wrong source is refused")

# ============================ F. artifacts on disk ===========================
print("\n--- F. bytes claimed present must BE present, and still hash true ---")

with tempfile.TemporaryDirectory() as td:
    corpus = Path(td)
    (corpus / "att").mkdir()
    p = corpus / "att" / "real.txt"
    p.write_text("historical bytes\n", encoding="utf-8")
    good = sha256_text("historical bytes\n")
    activates("ATTACHMENT_ARTIFACT_MISSING",
              vm(manifest([att_row("ATT-001-001", "CAPTURED_CONTENT",
                                   content_sha256=good, artifact_path="att/gone.txt")]),
                 corpus),
              "F1  an artifact_path that does not exist is refused")
    activates("ATTACHMENT_ARTIFACT_MUTATED",
              vm(manifest([att_row("ATT-001-001", "CAPTURED_CONTENT",
                                   content_sha256="f" * 64,
                                   artifact_path="att/real.txt")]), corpus),
              "F2  an artifact that no longer hashes to its record is refused")
    activates("ATTACHMENT_ARTIFACT_MUTATED",
              vm(manifest([att_row("ATT-001-001", "CAPTURED_CONTENT",
                                   content_sha256=good,
                                   artifact_path="att/real.txt")]), corpus),
              "F3  CONTROL: an intact artifact is accepted", expect=False)

# ============================ G. the clean control ===========================
print("\n--- G. the whole mechanism stays silent on a clean surface ---")

clean_findings = vm(manifest(
    [att_row("ATT-001-001", "CAPTURED_CONTENT", "MATERIAL", content_sha256="a" * 64)],
    recon="AGREE", declared=1, full_source_capture="YES"))
check("G1  a fully captured, reconciled, correctly-stated manifest produces NO findings",
      clean_findings == [], [f.code for f in clean_findings])

# ============================ activation report ==============================
print("\n" + "=" * 72)
print("ACTIVATION REPORT — a green check over zero eligible examples is NOT evidence")
print("=" * 72)
dead = []
for rule in sorted(ACTIVATION):
    n = ACTIVATION[rule]
    print("  %-46s activated %d time(s)%s"
          % (rule, n, "   <-- NEVER FIRED" if n == 0 else ""))
    if n == 0:
        dead.append(rule)
print()
print("rules exercised: %d/%d" % (len(ACTIVATION) - len(dead), len(ACTIVATION)))
if dead:
    check("ACTIVATION  every rule this suite claims to test actually fired", False,
          "never activated: %s" % dead)
else:
    check("ACTIVATION  every rule this suite claims to test actually fired", True)

print()
print("SCOPE: this suite proves STRUCTURAL and PROVENANCE properties of a source")
print("surface. It does not, and cannot, prove semantic understanding of any")
print("attachment. Final coverage requires independent source-first falsification.")
print()
print("%d passed, %d failed, %d checks total"
      % (len(PASSED), len(FAILED), len(PASSED) + len(FAILED)))
if len(PASSED) + len(FAILED) < MIN_CHECKS:
    print("SUITE UNDER-RAN: %d checks < floor %d — a suite that executes nothing "
          "must not exit 0" % (len(PASSED) + len(FAILED), MIN_CHECKS))
    sys.exit(1)
sys.exit(1 if FAILED else 0)
