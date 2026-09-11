#!/usr/bin/env python3
"""v4.4.1 suite — the three R39 blockers, each reproduced and each guarded.

B1  RQ-037  `verify_transcript_format` anchors on BLOCK-OPENING headers: a quoted
            `## Meddelande N` line inside a body is content, not a boundary. Mutants
            prove a genuinely broken structure is still refused (fail-closed kept).
B2  RQ-038  a declared count whose every item holds verified bytes under a platform
            identity reconciles AGREE where the body is silent. Mutants prove that a
            missing row, missing bytes, missing identity or a count mismatch stays
            UNKNOWN, and that a tampered artifact still fails.
B3  RQ-041  a historical compile is witnessed against the revision it DECLARES and
            its completeness is measured against the sources that existed at its own
            inventory revision. Mutants prove a wrong/nonexistent declared revision,
            an omitted pre-existing source, an undatable source and altered bytes
            still fail.

Every check runs the real CLI on real files in a temp corpus.
Usage (from the skill root):  python3 evals/test_v441.py
"""
import copy
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fixtures as F  # noqa: E402
from test_project_v3 import (  # noqa: E402
    sweep_project, capture, read_project_manifest, write_project_manifest,
    SWEEP_CHAT_1, SWEEP_CHAT_2,
)
from test_rnd_v4 import (  # noqa: E402
    mk_corpus, run as rnd_run, expect_code, TRANSCRIPT_1, write_json,
)
from test_rnd_v44 import v4_ir  # noqa: E402
import attachment_surface as att  # noqa: E402
import intake_common as ic  # noqa: E402
import project_contract as pc  # noqa: E402


def _seal(manifest, note_by_rev):
    """A VALID inventory_history for a synthetic manifest: revisions 1..N, the last
    entry's sha equal to the manifest's identity (what the real tool writes)."""
    identity, _ = pc.inventory_identity(manifest)
    n = max(note_by_rev)
    manifest["inventory_revision"] = n
    manifest["inventory_sha256"] = identity
    manifest["inventory_history"] = [
        {"revision": r, "inventory_sha256": identity if r == n else ("%02x" % r) * 32,
         "at": "2026-09-0%d" % min(r, 9), "note": note_by_rev[r]}
        for r in sorted(note_by_rev)]
    return manifest

RESULTS = []
MIN_CHECKS = 30


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS " if condition else "FAIL ", name,
                        ("\n        — %s" % str(detail)[:1500]) if (detail and not condition) else ""))


def proj(argv, corpus):
    return F.project(argv, corpus)


# ================================================================== B1 ====

# The CONV-054 shape: an assistant turn quoting another transcript's headers, with
# prose (no separator) directly before each quoted header line.
QUOTING_CHAT = """# Transkript

**Antal meddelanden:** 3

## Meddelande 1 — Johnny (användare)
Läs källan, inte parafrasen.

---

## Meddelande 2 — ChatGPT (assistent)
Important locus in the frozen source:

## Meddelande 22 — Johnny (användare)

"Brainstorma utifrån Nortropic, studera bilderna noggrant"

Then read:

## Meddelande 23 — ChatGPT (assistent)

This response is not later synthesis.

---

## Meddelande 3 — Johnny (användare)
Bra. Fortsätt.
"""


def scenario_b1(tmp):
    name = "demo-sweep"
    corpus = sweep_project(tmp, name)
    ok, detail, n = pc.verify_transcript_format(QUOTING_CHAT)
    check("B1.1 a body that QUOTES header lines verifies: 3 block-opening headers",
          ok and n == 3, detail)
    rc, out = capture(corpus, name, "CONV-001", QUOTING_CHAT, tmp)
    check("B1.2 the real CLI captures it VERIFIED=YES (was 'not contiguous' in v4.4)",
          rc == 0 and "VERIFIED=YES" in out and "STATE=CAPTURED" not in out, out)
    data = read_project_manifest(corpus, name)
    rev = data["sources"][0]["revisions"][-1]
    check("B1.3 the recorded message_count is the genuine count, not the line count",
          rev.get("message_count") == 3 and rev.get("verified") is True, rev)

    # mutant: block-opening headers out of sequence — still refused
    broken = QUOTING_CHAT.replace("## Meddelande 3 — Johnny", "## Meddelande 4 — Johnny")
    ok, detail, _ = pc.verify_transcript_format(broken)
    check("B1.4 MUTANT a block-opening header out of sequence is still refused",
          not ok and "not contiguous" in detail, detail)
    rc, out = capture(corpus, name, "CONV-002", broken, tmp)
    check("B1.5 MUTANT the CLI records it CAPTURED, a hard gap, never VERIFIED",
          rc != 0 and "VERIFIED=NO" in out and "STATE=CAPTURED" in out, out)

    # mutant: a quoted header that FOLLOWS a separator opens a block (fail-closed —
    # an injected boundary is exactly what a separator + header looks like)
    injected = QUOTING_CHAT.replace("Then read:\n\n## Meddelande 23",
                                    "Then read:\n\n---\n\n## Meddelande 23")
    ok, detail, _ = pc.verify_transcript_format(injected)
    check("B1.6 MUTANT a header after a separator IS a boundary: refused as out of sequence",
          not ok and "not contiguous" in detail, detail)

    # mutant: an unbalanced fence inside the quoting body is still caught
    fenced = QUOTING_CHAT.replace("This response is not later synthesis.",
                                  "```text\nThis response is not later synthesis.")
    ok, detail, _ = pc.verify_transcript_format(fenced)
    check("B1.7 MUTANT an unbalanced fence in the quoting body is still refused",
          not ok and "unbalanced code fence in message 2" in detail, detail)

    # mutant: an empty body between two boundaries is still caught
    empty = QUOTING_CHAT.replace("Bra. Fortsätt.\n", "")
    ok, detail, _ = pc.verify_transcript_format(empty)
    check("B1.8 MUTANT an empty body is still refused", not ok and "empty body" in detail,
          detail)

    # a header with no separator before it and NOT first: content (the quoted lines)
    roles_all = ic.parse_transcript_roles(QUOTING_CHAT)
    try:
        roles_blk = ic.parse_transcript_roles(QUOTING_CHAT, block_opening=True)
    except TypeError:                     # pre-v4.4.1 scripts: no block reading
        roles_blk = {}
    check("B1.9 block-opening roles read 3 speakers; the v3 reading still sees 5 lines",
          sorted(roles_blk) == [1, 2, 3] and sorted(roles_all) == [1, 2, 3, 22, 23],
          (roles_blk, roles_all))
    # the existing fixture (no separator before the first header) is unchanged
    ok, detail, n = pc.verify_transcript_format(SWEEP_CHAT_1)
    check("B1.10 the v3 fixture verifies exactly as before", ok and n == 3, detail)
    # MUTANT (review): header lines with NO separators anywhere must not read as one
    # long message — boundaries are undecidable, so the capture is refused
    no_sep = SWEEP_CHAT_1.replace("\n---\n", "\n")
    ok, detail, n = pc.verify_transcript_format(no_sep)
    check("B1.11 MUTANT a separator-less transcript is refused, never read as 1 message",
          not ok and "no separator" in detail and n == 1, (detail, n))
    rc, out = capture(corpus, name, "CONV-003", no_sep, tmp)
    check("B1.12 MUTANT …and the CLI records it as a hard gap",
          rc != 0 and "VERIFIED=NO" in out and "STATE=CAPTURED" in out, out)
    # MUTANT (review r2): a `---` INSIDE a code fence is not a separator
    fenced_sep = no_sep.replace("Förslag: pipelinen först.",
                                "Förslag:\n```yaml\n---\nkey: value\n```")
    ok, detail, n = pc.verify_transcript_format(fenced_sep)
    check("B1.13 MUTANT a fenced `---` does not make the transcript decidable",
          not ok and "no separator" in detail, (detail, n))
    # MUTANT (review r2): one separator missing — the header that CONTINUES the
    # sequence is a lost boundary, not a quote; refused rather than absorbed
    one_missing = SWEEP_CHAT_1.replace("\n---\n\n## Meddelande 3", "\n\n## Meddelande 3")
    ok, detail, n = pc.verify_transcript_format(one_missing)
    check("B1.14 MUTANT a missing separator before 'Meddelande 3' is refused, not absorbed",
          not ok and "continues the sequence" in detail, (detail, n))
    # …while a quote naming a NON-next number in the same position is content
    quote_other = SWEEP_CHAT_1.replace("\n---\n\n## Meddelande 3 — Johnny (användare)\n",
                                       "\n\n## Meddelande 9 — Johnny (användare)\n")
    ok, detail, n = pc.verify_transcript_format(quote_other)
    check("B1.15 a quoted header naming a non-next number is content (2 messages)",
          ok and n == 2, (detail, n))


# ================================================================== B2 ====

SILENT_CHAT = """# Transkript

**Antal meddelanden:** 2

> Notis: 2 bilagor inventerade (data-layer: distinkta plattforms-fil-id).

## Meddelande 1 — Johnny (användare)
Här är två skärmbilder av tavlan.

---

## Meddelande 2 — ChatGPT (assistent)
Jag ser tavlan: tre spår och en grind.
"""


def _att_report(corpus, name):
    rc, out = proj(["attachments", "--project", name], corpus)
    row = next((l for l in out.splitlines() if l.startswith("CONV-001")), "")
    return rc, out, row


def _register(corpus, name, tmp, ident, payload, platform_id=None, at="2026-08-30"):
    f = Path(tmp) / ident
    f.write_bytes(payload)
    argv = ["register-attachment", "--project", name, "--source", "CONV-001",
            "--file", str(f), "--original-filename", ident, "--media-type", "image/png",
            "--declared-kind", "image_asset_pointer", "--message-binding",
            "Meddelande 1", "--at", at]
    if platform_id:
        argv += ["--platform-file-id", platform_id]
    return proj(argv, corpus)


def scenario_b2(tmp):
    name = "demo-sweep"
    corpus = sweep_project(tmp, name)
    rc, out = capture(corpus, name, "CONV-001", SILENT_CHAT, tmp)
    assert rc == 0, out
    rc, out, row = _att_report(corpus, name)
    check("B2.0 before any bytes: 2 declared, silent body → UNKNOWN (no manifest, tolerated)",
          "UNKNOWN" in row and "2" in row, out)

    png1 = b"\x89PNG\r\n\x1a\n" + b"one" * 40
    png2 = b"\x89PNG\r\n\x1a\n" + b"two" * 40
    rc, out = _register(corpus, name, tmp, "IMG_1.png", png1, "file_000000000000000000000000000000a1")
    check("B2.1 --platform-file-id is accepted and the row is registered", rc == 0, out)
    rc, out = _register(corpus, name, tmp, "IMG_x.png", b"\x89PNG\r\n\x1a\nx" * 5, "x")
    check("B2.1b MUTANT a platform id that is not one (\"x\") is refused",
          rc != 0 and "REGISTER_REFUSED" in out and "platform identity" in out, out)
    rc, out, row = _att_report(corpus, name)
    check("B2.2 one of two registered: still UNKNOWN — a count mismatch corroborates nothing",
          "UNKNOWN" in row, out)
    rc, out = proj(["validate", "--project", name], corpus)
    check("B2.3 …and validate reports ATTACHMENT_SURFACE_UNRECONCILED for the half-done surface",
          "ATTACHMENT_SURFACE_UNRECONCILED" in out and "CONV-001" in out, out)

    rc, out = _register(corpus, name, tmp, "IMG_2.png", png2, "file_000000000000000000000000000000a2")
    check("B2.4 second item registered", rc == 0 and "RECONCILIATION=AGREE" in out
          and "FULL_SOURCE_CAPTURE=YES" in out, out)
    rc, out, row = _att_report(corpus, name)
    check("B2.5 2 declared / 2 rows with bytes + platform ids / silent body → AGREE, YES",
          "AGREE" in row and "YES" in row, out)
    rc, out = proj(["validate", "--project", name], corpus)
    check("B2.6 validate no longer flags the surface",
          "ATTACHMENT_SURFACE_UNRECONCILED" not in out, out)

    mpath = corpus / "_projects" / name / "sources" / "CONV-001" / "attachments-r1.json"
    if not mpath.exists():                # pre-v4.4.1: nothing registered at all
        for k in range(7, 19):
            check("B2.%d (skipped: no manifest — registration refused above)" % k, False)
        return
    m = json.loads(mpath.read_text(encoding="utf-8"))
    check("B2.7 the stored manifest carries the platform ids as sent, nothing inferred",
          [r.get("platform_file_id") for r in m["attachments"]]
          == ["file_000000000000000000000000000000a1", "file_000000000000000000000000000000a2"], m)

    # --- mutants on the reconcile function itself -------------------------
    rows = copy.deepcopy(m["attachments"])
    signals = att.observed_signals(SILENT_CHAT)
    check("B2.8 unit: the control reconciles AGREE",
          att.reconcile(2, signals, rows)[0] == "AGREE")
    r_noid = copy.deepcopy(rows); r_noid[1].pop("platform_file_id")
    check("B2.9 MUTANT a row without platform identity → UNKNOWN",
          att.reconcile(2, signals, r_noid)[0] == "UNKNOWN")
    r_nobytes = copy.deepcopy(rows)
    r_nobytes[1].update({"capture_status": "UNAVAILABLE"}); r_nobytes[1].pop("content_sha256")
    check("B2.10 MUTANT a row without bytes → UNKNOWN",
          att.reconcile(2, signals, r_nobytes)[0] == "UNKNOWN")
    r_dup = copy.deepcopy(rows)
    r_dup[1].update({"capture_status": "DUPLICATE", "duplicate_of": "ATT-001-001"})
    r_dup[1].pop("content_sha256")
    check("B2.11 MUTANT a bytes-absent DUPLICATE row → UNKNOWN (an equivalence claim is not bytes)",
          att.reconcile(2, signals, r_dup)[0] == "UNKNOWN")
    check("B2.12 MUTANT three rows against two declared → DISAGREE, never AGREE",
          att.reconcile(2, signals, rows + [copy.deepcopy(rows[0])])[0] == "DISAGREE")
    check("B2.13 MUTANT two rows against three declared → UNKNOWN",
          att.reconcile(3, signals, rows)[0] == "UNKNOWN")
    check("B2.14 MUTANT a silent header (declared None) is never corroborated into AGREE",
          att.reconcile(None, signals, rows)[0] == "UNKNOWN")
    corroborate = getattr(att, "bytes_corroborate_declaration", None)
    check("B2.15 unit: bytes_corroborate_declaration refuses a hash without identity",
          corroborate is not None and corroborate(2, r_noid) is False
          and corroborate(2, rows) is True)
    # a body that CONTRADICTS the declaration is untouched by the new branch
    loud = SILENT_CHAT.replace("Här är två skärmbilder av tavlan.",
                               "Här är `plan.pdf`, uppladdad 12:00:01, och `plan2.pdf` 12:00:02 "
                               "och `plan3.pdf` 12:00:03.")
    check("B2.16 MUTANT named uploads the declaration omits still DISAGREE",
          att.reconcile(2, att.observed_signals(loud), rows)[0] == "DISAGREE")

    # --- provenance is not weakened: a tampered artifact still fails -------
    art = corpus / m["attachments"][0]["artifact_path"]
    art.write_bytes(png1 + b"x")
    rc, out = proj(["validate", "--project", name], corpus)
    check("B2.17 MUTANT altered artifact bytes → ATTACHMENT_ARTIFACT_MUTATED (AGREE buys nothing)",
          "ATTACHMENT_ARTIFACT_MUTATED" in out, out)
    art.write_bytes(png1)
    # a hand-written platform id on a row WITHOUT bytes is still bytes-absent
    m2 = json.loads(mpath.read_text(encoding="utf-8"))
    m2["attachments"][1].update({"capture_status": "UNAVAILABLE"})
    m2["attachments"][1].pop("content_sha256"); m2["attachments"][1].pop("artifact_path")
    m2["attachments"][1]["semantic_accessibility"] = "UNAVAILABLE"
    mpath.write_text(json.dumps(m2, ensure_ascii=False, indent=2), encoding="utf-8")
    rc, out, row = _att_report(corpus, name)
    check("B2.18 MUTANT an identity on a bytes-absent row corroborates nothing → UNKNOWN",
          "UNKNOWN" in row, out)

    # --- MUTANT (review): a copied row — same artifact, same platform id, a second
    # attachment id — must not count as a second item
    m3 = json.loads(mpath.read_text(encoding="utf-8"))
    m3["attachments"] = [m["attachments"][0], dict(m["attachments"][0],
                                                   attachment_id="ATT-001-002", ordinal=2)]
    mpath.write_text(json.dumps(m3, ensure_ascii=False, indent=2), encoding="utf-8")
    rc, out, row = _att_report(corpus, name)
    check("B2.19 MUTANT a copied row under a second id → not AGREE (UNKNOWN)",
          "UNKNOWN" in row and "AGREE" not in row, out)
    rc, out = proj(["validate", "--project", name], corpus)
    check("B2.20 MUTANT …and validate names it: ATTACHMENT_PLATFORM_ID_DUPLICATE",
          "ATTACHMENT_PLATFORM_ID_DUPLICATE" in out, out)
    check("B2.21 unit: platform_identity_conflicts reports the shared id",
          [c[0] for c in att.platform_identity_conflicts(m3["attachments"])]
          == ["file_000000000000000000000000000000a1"])
    # a declared duplicate CHAIN (the adapter's double listing) is not a conflict
    chain = [m["attachments"][0], dict(m["attachments"][0], attachment_id="ATT-001-002",
                                        ordinal=2, capture_status="RECOVERED_DUPLICATE",
                                        duplicate_of="ATT-001-001",
                                        recovery_provenance="same platform file id, second listing")]
    check("B2.22 a duplicate_of chain under one platform id is not a conflict",
          att.platform_identity_conflicts(chain) == []
          and att.reconcile(2, signals, chain)[0] == "AGREE")
    chain2 = [dict(chain[0]), dict(chain[1], duplicate_of="ATT-001-009")]
    check("B2.23 MUTANT a duplicate pointing elsewhere is a conflict → UNKNOWN",
          att.platform_identity_conflicts(chain2) != []
          and att.reconcile(2, signals, chain2)[0] == "UNKNOWN")
    # MUTANT (review r2): the same copy under a DIFFERENT platform id — one artifact
    # still cannot satisfy two declared items unless the sharing is declared
    m4 = json.loads(mpath.read_text(encoding="utf-8"))
    m4["attachments"] = [m["attachments"][0], dict(m["attachments"][0],
                                                   attachment_id="ATT-001-002", ordinal=2,
                                                   platform_file_id="file_000000000000000000000000000000ff")]
    mpath.write_text(json.dumps(m4, ensure_ascii=False, indent=2), encoding="utf-8")
    rc, out, row = _att_report(corpus, name)
    check("B2.25 MUTANT a copied row under a renamed platform id → not AGREE",
          "UNKNOWN" in row and "AGREE" not in row, out)
    rc, out = proj(["validate", "--project", name], corpus)
    check("B2.26 MUTANT …and validate names it: ATTACHMENT_BYTES_SHARED_UNDECLARED",
          "ATTACHMENT_BYTES_SHARED_UNDECLARED" in out, out)
    # the declared form of the same shape (two platform items, identical bytes)
    m4["attachments"][1]["byte_identical_to"] = "ATT-001-001"
    mpath.write_text(json.dumps(m4, ensure_ascii=False, indent=2), encoding="utf-8")
    rc, out, row = _att_report(corpus, name)
    check("B2.27 two platform items declared byte_identical_to each other's bytes → AGREE",
          "AGREE" in row and "YES" in row, out)
    rc, out = proj(["validate", "--project", name], corpus)
    check("B2.28 …and validate is clean of the sharing code",
          "ATTACHMENT_BYTES_SHARED_UNDECLARED" not in out, out)
    m4["attachments"][1]["byte_identical_to"] = "ATT-001-009"
    check("B2.29 MUTANT byte_identical_to naming no row in the manifest is undeclared",
          att.shared_bytes_undeclared(m4["attachments"]) != []
          and att.reconcile(2, signals, m4["attachments"])[0] == "UNKNOWN")
    # restore the real manifest
    mpath.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    rc, out = proj(["validate", "--project", name], corpus)
    check("B2.24 the restored manifest validates clean of all three codes",
          "ATTACHMENT_PLATFORM_ID_DUPLICATE" not in out
          and "ATTACHMENT_BYTES_SHARED_UNDECLARED" not in out
          and "ATTACHMENT_SURFACE_UNRECONCILED" not in out, out)


# ================================================================== B3 ====

TRANSCRIPT_1_R2 = TRANSCRIPT_1.rstrip("\n") + """

---

## Meddelande 6 — Johnny (användare)

Tillägg efter kompileringen: vi fortsätter i samma spår.
"""

TRANSCRIPT_3 = """---
title: later source
---
# Later

## Meddelande 1 — Johnny (användare)

En helt ny konversation som fångades efter kompileringen.

---

## Meddelande 2 — ChatGPT (assistent)

Noterat.
"""


def _seal_synthetic(corpus):
    """Give mk_corpus's manifest the history the real tool would have written:
    revision 1 captured CONV-001, revision 2 captured CONV-002."""
    mpath = corpus / "_projects" / "demo" / "project-manifest.json"
    m = json.loads(mpath.read_text(encoding="utf-8"))
    _seal(m, {1: "capture CONV-001 r1", 2: "capture CONV-002 r1"})
    write_json(mpath, m)
    return m


def _grow(corpus):
    """Grow the demo project AFTER a compile bound at inventory_revision 2:
    CONV-001 gets r2 (inventory 3), CONV-003 arrives (inventory 4)."""
    proj_dir = corpus / "_projects" / "demo"
    mpath = proj_dir / "project-manifest.json"
    m = json.loads(mpath.read_text(encoding="utf-8"))
    c1 = next(s for s in m["sources"] if s["source_id"] == "CONV-001")
    p2 = proj_dir / "sources" / "CONV-001" / "conversation-r2.md"
    p2.write_text(TRANSCRIPT_1_R2, encoding="utf-8")
    c1["revisions"].append({
        "revision": 2, "path": "_projects/demo/sources/CONV-001/conversation-r2.md",
        "sha256": F.sha256_text(TRANSCRIPT_1_R2), "captured_at": "2026-09-02",
        "message_count": 6, "adapter": "data-layer", "verified": True, "verify_detail": ""})
    d3 = proj_dir / "sources" / "CONV-003"
    d3.mkdir(parents=True)
    (d3 / "conversation.md").write_text(TRANSCRIPT_3, encoding="utf-8")
    m["sources"].append({
        "source_id": "CONV-003", "conversation_key": "chatgpt.com/conv-003",
        "url": "https://chatgpt.com/c/conv-003", "title": "CONV-003",
        "discovered_at": "2026-09-02", "state": "VERIFIED",
        "revisions": [{"revision": 1, "path": "_projects/demo/sources/CONV-003/conversation.md",
                       "sha256": F.sha256_text(TRANSCRIPT_3), "captured_at": "2026-09-02",
                       "message_count": 2, "adapter": "data-layer", "verified": True,
                       "verify_detail": ""}],
        "ideas": [], "extraction_note": "", "errors": []})
    old_hist = {e["revision"]: e for e in m["inventory_history"]}
    _seal(m, {1: "capture CONV-001 r1", 2: "capture CONV-002 r1",
              3: "capture CONV-001 r2", 4: "capture CONV-003 r1"})
    # keep the sealed shas of the revisions that already existed
    for e in m["inventory_history"]:
        if e["revision"] in old_hist:
            e["inventory_sha256"] = old_hist[e["revision"]]["inventory_sha256"]
    write_json(mpath, m)
    return m


def _set_history(corpus, notes_by_rev, sha_overrides=None):
    mpath = corpus / "_projects" / "demo" / "project-manifest.json"
    m = json.loads(mpath.read_text(encoding="utf-8"))
    identity, _ = pc.inventory_identity(m)
    n = max(notes_by_rev)
    m["inventory_history"] = [
        {"revision": r, "inventory_sha256": (sha_overrides or {}).get(
            r, identity if r == n else ("%02x" % r) * 32),
         "at": "2026-09-0%d" % min(r, 9), "note": notes_by_rev[r]}
        for r in sorted(notes_by_rev)]
    m["inventory_revision"] = n
    m["inventory_sha256"] = identity
    write_json(mpath, m)
    return m


def scenario_b3(tmp):
    corpus = mk_corpus(tmp)
    sealed = _seal_synthetic(corpus)
    cid = "hist-ok"
    ir_path = v4_ir(corpus, cid)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.0 the control compile validates before the corpus grows", rc == 0, out)
    ir = json.loads(ir_path.read_text(encoding="utf-8"))
    check("B3.0b the compile declares its revisions and the sealed inventory revision",
          ir["source_set"]["inventory_revision"] == 2
          and ir["source_set"]["inventory_sha256"] == sealed["inventory_sha256"]
          and all(s.get("revision") == 1 for s in ir["source_set"]["sources"]), ir["source_set"])

    # a v4.0-shaped IR (no `revision` on its sources) still reads as "latest"
    ir_legacy = copy.deepcopy(ir)
    for s_ in ir_legacy["source_set"]["sources"]:
        s_.pop("revision", None)
    write_json(ir_path, ir_legacy)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.0d a legacy IR without revision numbers validates (binds the latest), rc=0",
          rc == 0 and "RND_SOURCE_SET_INCOMPLETE" not in out, out)
    write_json(ir_path, ir)

    _grow(corpus)
    rc, out = proj(["validate", "--project", "demo"], corpus)
    check("B3.0c the grown manifest's history is a shape the project contract accepts",
          "INVENTORY_HISTORY_INVALID" not in out and "INVENTORY_IDENTITY_STALE" not in out, out)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.1 after growth (CONV-001 r2, new CONV-003) the historical compile still validates",
          rc == 0 and not re.search(r"FAIL\s+\[%s\]" % cid, out), out)
    check("B3.2 …and is reported STALE (WARN), for both the inventory and CONV-001",
          len(re.findall(r"WARN\s+\[%s\]\s+RND_SOURCE_SET_STALE" % cid, out)) >= 2, out)
    check("B3.3 …with no RND_SOURCE_SET_INCOMPLETE for the later-captured CONV-003",
          "RND_SOURCE_SET_INCOMPLETE" not in out, out)
    check("B3.4 …and no RND_SOURCE_NOT_WITNESSED / COUNT_MISMATCH for CONV-001 r1",
          "RND_SOURCE_NOT_WITNESSED" not in out
          and "RND_SOURCE_MESSAGE_COUNT_MISMATCH" not in out, out)

    # MUTANT: the compile claims revision 2 for CONV-001 while binding r1's bytes
    def mut_rev(n):
        ir2 = json.loads(ir_path.read_text(encoding="utf-8"))
        for s in ir2["source_set"]["sources"]:
            if s["source_id"] == "CONV-001":
                s["revision"] = n
        write_json(ir_path, ir2)
    mut_rev(2)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.5 MUTANT declared revision 2 with r1's path/bytes → RND_SOURCE_NOT_WITNESSED",
          rc != 0 and expect_code(out, "RND_SOURCE_NOT_WITNESSED", cid), out)
    mut_rev(9)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.6 MUTANT a declared revision the manifest never recorded → RND_SOURCE_NOT_WITNESSED",
          rc != 0 and expect_code(out, "RND_SOURCE_NOT_WITNESSED", cid)
          and "never recorded" in out, out)
    mut_rev(1)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.7 restored declaration validates again", rc == 0, out)

    # MUTANT: a source that EXISTED at the compile's inventory revision but is absent
    # (history re-dated so CONV-003's first capture sits AT revision 2, the anchor)
    mpath = corpus / "_projects" / "demo" / "project-manifest.json"
    grown = json.loads(mpath.read_text(encoding="utf-8"))
    anchor_sha = grown["inventory_history"][1]["inventory_sha256"]
    _set_history(corpus, {1: "capture CONV-001 r1", 2: "capture CONV-003 r1",
                          3: "capture CONV-001 r2", 4: "capture CONV-002 r1"},
                 {2: anchor_sha})
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.8 MUTANT CONV-003 first captured AT the bound inventory revision, unbound → INCOMPLETE",
          rc != 0 and expect_code(out, "RND_SOURCE_SET_INCOMPLETE", cid)
          and "CONV-003" in out, out)
    # MUTANT: the history cannot date CONV-003 at all → fail-closed, must be bound
    _set_history(corpus, {1: "capture CONV-001 r1", 2: "capture CONV-002 r1",
                          3: "capture CONV-001 r2", 4: "declare inventory (data-layer, 3 item(s))"},
                 {2: anchor_sha})
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.9 MUTANT an undatable source is treated as pre-existing → INCOMPLETE",
          rc != 0 and expect_code(out, "RND_SOURCE_SET_INCOMPLETE", cid), out)
    write_json(mpath, grown)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.10 restored history validates again", rc == 0, out)

    # MUTANT: a compile with NO inventory_revision keeps the strict v4.4 reading
    ir3 = json.loads(ir_path.read_text(encoding="utf-8"))
    ir3["source_set"]["inventory_revision"] = None
    write_json(ir_path, ir3)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.11 MUTANT a compile that declares no inventory revision cannot claim historical scope",
          rc != 0 and expect_code(out, "RND_SOURCE_SET_INCOMPLETE", cid), out)
    # MUTANT (review): an UNANCHORED number — 0, -1, or a revision whose sealed sha is
    # not the one the compile bound — exempts nothing
    for bad in (0, -1, 1):
        ir3["source_set"]["inventory_revision"] = bad
        write_json(ir_path, ir3)
        rc, out = rnd_run(corpus, "validate", "--compile", cid)
        check("B3.11%s MUTANT inventory_revision=%r is not anchored in the history → INCOMPLETE"
              % ("abc"[(0, -1, 1).index(bad)], bad),
              rc != 0 and expect_code(out, "RND_SOURCE_SET_INCOMPLETE", cid), out)
    ir3["source_set"]["inventory_revision"] = 2
    ir3["source_set"]["inventory_sha256"] = "f" * 64
    write_json(ir_path, ir3)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.11d MUTANT the right number with the wrong sealed sha is not anchored → INCOMPLETE",
          rc != 0 and expect_code(out, "RND_SOURCE_SET_INCOMPLETE", cid), out)
    write_json(ir_path, ir)
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.11e the anchored compile validates again", rc == 0, out)

    # MUTANT: the bound r1 bytes change on disk → hash mismatch, exactly as before
    p1 = corpus / "_projects" / "demo" / "sources" / "CONV-001" / "conversation.md"
    orig = p1.read_text(encoding="utf-8")
    p1.write_text(orig.replace("Det är beslutat.", "Det är INTE beslutat."), encoding="utf-8")
    rc, out = rnd_run(corpus, "validate", "--compile", cid)
    check("B3.12 MUTANT altered bound bytes → still RND_SOURCE_HASH_MISMATCH / NOT_WITNESSED",
          rc != 0 and (expect_code(out, "RND_SOURCE_HASH_MISMATCH", cid)
                       or expect_code(out, "RND_SOURCE_NOT_WITNESSED", cid)), out)
    p1.write_text(orig, encoding="utf-8")

    # a NEW compile against the grown corpus binds everything and is not stale
    rc, out = rnd_run(corpus, "init", "--compile", "fresh", "--project", "demo",
                      "--at", "2026-09-02")
    check("B3.13 a fresh init after growth binds CONV-001 r2 and CONV-003",
          rc == 0, out)
    fresh = json.loads((corpus / "_rnd" / "fresh" / "rnd-ir.json").read_text(encoding="utf-8"))
    bound = {s["source_id"]: s.get("revision") for s in fresh["source_set"]["sources"]}
    check("B3.14 …at the latest revisions, inventory revision 4",
          bound == {"CONV-001": 2, "CONV-002": 1, "CONV-003": 1}
          and fresh["source_set"]["inventory_revision"] == 4, (bound, fresh["source_set"]))
    # MUTANT (review): a compile OF ITS OWN TIME that binds a superseded revision
    # omits captured turns — a FAIL, not a STALE warning
    fpath = corpus / "_rnd" / "fresh" / "rnd-ir.json"
    r1 = next(r for r in grown["sources"] if r["source_id"] == "CONV-001")["revisions"][0]
    for s_ in fresh["source_set"]["sources"]:
        if s_["source_id"] == "CONV-001":
            s_.update({"revision": 1, "path": r1["path"], "message_count": r1["message_count"],
                       "source_sha256": ic.transcript_source_sha256(
                           (corpus / r1["path"]).read_text(encoding="utf-8"))})
    write_json(fpath, fresh)
    rc, out = rnd_run(corpus, "validate", "--compile", "fresh")
    check("B3.15 MUTANT a current compile binding CONV-001 r1 (r2 captured before it) → INCOMPLETE",
          rc != 0 and expect_code(out, "RND_SOURCE_SET_INCOMPLETE", "fresh")
          and "latest revision of its own time" in out, out)


def main():
    for sc in (scenario_b1, scenario_b2, scenario_b3):
        tmp = tempfile.mkdtemp(prefix="v441-")
        try:
            sc(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    passed = sum(1 for r in RESULTS if r[1])
    failed = [r for r in RESULTS if not r[1]]
    print("%d/%d checks passed" % (passed, len(RESULTS)))
    if len(RESULTS) < MIN_CHECKS:
        print("FAIL: only %d checks ran (floor %d)" % (len(RESULTS), MIN_CHECKS))
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
