#!/usr/bin/env python3
"""v4.4 suite — PROJECT side: byte-verified source cut, attachment byte
registration, document sources with evidence roles, and the composed chain.

Every new FAIL code has a positive check and a mutant check. Built the way the v3
suite is built: real files, the real CLI, a real git repository where a witness is
needed. The chain scenario drives the WHOLE v4.4 chain end to end on a synthetic
project — enumeration proof (the shipped adapter's own record), capture, extract,
route, audit, cut, a version-4 compile with every turn accounted for, its audit,
an Obsidian vault — and proves CHAIN_COMPLETE flips to NO when any link is pulled.

Usage (from the skill root):  python3 evals/test_project_v44.py
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fixtures as F  # noqa: E402
from test_project_v3 import (  # noqa: E402
    sweep_project, capture, sweep_audit_doc, read_project_manifest,
    write_project_manifest, real_discovery_record, GID, URL_1, URL_2, URL_3,
    SWEEP_CHAT_1, SWEEP_CHAT_2,
)
import rnd_contract as rc  # noqa: E402

RESULTS = []
MIN_CHECKS = 50
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
PROJECTION = SCRIPTS / "obsidian_projection.py"

SWEEP_CHAT_3 = """# Transkript

**Antal meddelanden:** 2

> Notis: 1 bilaga inventerad (uppladdad fil); innehållet ej infångat.

## Meddelande 1 — Johnny (användare)
Här är masterplanen som uppladdad bilaga. Kapitel två gäller.

---

## Meddelande 2 — ChatGPT (assistent)
Läst. Kapitel två säger att ledgern är valfri.
"""


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS " if condition else "FAIL ", name,
                        ("\n        — %s" % str(detail)[:1200]) if (detail and not condition) else ""))


def proj(argv, corpus):
    return F.project(argv, corpus)


def projection(argv, corpus):
    r = subprocess.run([sys.executable, str(PROJECTION)] + argv
                       + ["--corpus", str(corpus)], capture_output=True, text=True,
                       timeout=120)
    return r.returncode, r.stdout + r.stderr


def swept_and_routed(tmp, name="demo-sweep", verified=False):
    """A project with three captured, extracted, routed and audited sources."""
    corpus = sweep_project(tmp, name)
    if verified:
        ev = Path(tmp) / "evidence.json"
        ev.write_text(json.dumps(real_discovery_record([URL_1, URL_2, URL_3])),
                      encoding="utf-8")
        rc_, out = proj(["declare", "--project", name, "--inventory", str(ev),
                         "--evidence", str(ev), "--method", "data-layer",
                         "--verified", "--at", "2026-08-30"], corpus)
        assert rc_ == 0, out
    for sid, text in (("CONV-001", SWEEP_CHAT_1), ("CONV-002", SWEEP_CHAT_2),
                      ("CONV-003", SWEEP_CHAT_3)):
        rc_, out = capture(corpus, name, sid, text, tmp)
        assert rc_ == 0, out
        rc_, out = proj(["mark-extracted", "--project", name, "--source", sid,
                         "--no-ideas", "--note", "proving fixture", "--at", "2026-08-30"],
                        corpus)
        assert rc_ == 0, out
        rc_, out = proj(["mark-routed", "--project", name, "--source", sid,
                         "--at", "2026-08-30"], corpus)
        assert rc_ == 0, out
    data = read_project_manifest(corpus, name)
    (corpus / "_projects" / name / "sweep-audit.md").write_text(
        sweep_audit_doc(name, [F.audit_round(data["inventory_revision"], verdict="PASS",
                                             scope="inventory + captures + routing",
                                             at="2026-08-30")]), encoding="utf-8")
    return corpus


# ================================================================ S1: cut ==

def scenario_cut(tmp):
    corpus = swept_and_routed(tmp)
    name = "demo-sweep"
    rc_, out = proj(["cut", "--project", name, "--at", "2026-09-01"], corpus)
    check("CUT1 a cut dated after the captures is refused: SOURCE_CUT_UNVERIFIED",
          rc_ == 1 and "SOURCE_CUT_UNVERIFIED" in out and "CONV-001" in out, out)
    # a byte-identical re-capture records the verification date without a revision
    rc_, out = capture(corpus, name, "CONV-001", SWEEP_CHAT_1, tmp, at="2026-09-01")
    check("CUT2 a no-op capture records VERIFIED_UNCHANGED_AT on the latest revision",
          rc_ == 0 and "CAPTURE_UNCHANGED" in out and "VERIFIED_UNCHANGED_AT=2026-09-01" in out,
          out)
    data = read_project_manifest(corpus, name)
    rev = [s for s in data["sources"] if s["source_id"] == "CONV-001"][0]["revisions"][-1]
    check("CUT2b the manifest carries verified_unchanged_at and the inventory did not move",
          rev.get("verified_unchanged_at") == "2026-09-01"
          and data["inventory_revision"] == 4, json.dumps(rev))
    rc_, out = proj(["cut", "--project", name, "--at", "2026-09-01"], corpus)
    check("CUT3 one verified source is not enough — the other two are named",
          rc_ == 1 and "CONV-002" in out and "CONV-003" in out and "CONV-001" not in
          out.split("SOURCE_CUT_UNVERIFIED")[1], out)
    for sid, text in (("CONV-002", SWEEP_CHAT_2), ("CONV-003", SWEEP_CHAT_3)):
        capture(corpus, name, sid, text, tmp, at="2026-09-01")
    rc_, out = proj(["cut", "--project", name, "--at", "2026-09-01"], corpus)
    m = re.search(r"SOURCE_CUT=([0-9a-f]{64})", out)
    check("CUT4 with every source byte-verified on/after the date the cut is made",
          rc_ == 0 and m is not None and "BRANCH_PROBE sources=3 shared_prefix_pairs=0" in out,
          out)
    digest = m.group(1) if m else ""
    rc_, out = proj(["validate", "--project", name], corpus)
    check("CUT5 a fresh cut validates CURRENT (no SOURCE_CUT_* finding)",
          rc_ == 0 and "SOURCE_CUT_BROKEN" not in out and "SOURCE_CUT_STALE" not in out, out)
    rc_, out = proj(["coverage", "--project", name], corpus)
    check("CUT6 coverage prints the cut and its state",
          "SOURCE_CUT=%s" % digest in out and "SOURCE_CUT_STATE=CURRENT" in out, out)
    rc_, out = proj(["cut", "--project", name, "--at", "2026-09-01"], corpus)
    check("CUT7 cutting the same bytes again is a no-op", rc_ == 0 and "CUT_UNCHANGED" in out,
          out)
    # MUTANT: a bound byte moves → BROKEN
    src = corpus / "_projects" / name / "sources" / "CONV-002" / "conversation.md"
    original = src.read_bytes()
    src.write_bytes(original + b"\n\nappended after the cut\n")
    rc_, out = proj(["validate", "--project", name], corpus)
    check("CUT8 a bound source that changed after the cut is SOURCE_CUT_BROKEN",
          rc_ != 0 and "SOURCE_CUT_BROKEN" in out, out)
    src.write_bytes(original)
    # MUTANT: the stored digest is edited → BROKEN (the record was tampered)
    data = read_project_manifest(corpus, name)
    data["source_cut"]["cut_sha256"] = "0" * 64
    write_project_manifest(corpus, name, data)
    rc_, out = proj(["validate", "--project", name], corpus)
    check("CUT9 a cut whose digest does not recompute from its lines is BROKEN",
          "SOURCE_CUT_BROKEN" in out and "does not recompute" in out, out)
    data["source_cut"]["cut_sha256"] = digest
    write_project_manifest(corpus, name, data)
    # a new revision after the cut → STALE (honest, a WARN)
    rc_, out = capture(corpus, name, "CONV-002", SWEEP_CHAT_2 + "\n---\n\n"
                       "## Meddelande 3 — Johnny (användare)\nNytt efter cutten.\n",
                       tmp, at="2026-09-02")
    rc_, out = proj(["validate", "--project", name], corpus)
    check("CUT10 a source revision arriving after the cut makes it STALE, not broken",
          re.search(r"WARN\s+\[demo-sweep\]\s+SOURCE_CUT_STALE", out) is not None
          and "SOURCE_CUT_BROKEN" not in out, out)
    rc_, out = proj(["coverage", "--project", name], corpus)
    check("CUT11 coverage reports SOURCE_CUT_STATE=STALE", "SOURCE_CUT_STATE=STALE" in out, out)
    # F-4: dates are dates, and a capture's input never comes from the corpus itself
    rc_, out = capture(corpus, name, "CONV-001", SWEEP_CHAT_1, tmp, at="later")
    check("CUT13 capture --at that is not a date is refused", rc_ == 2 and "not a YYYY-MM-DD" in out,
          out)
    rc_, out = proj(["cut", "--project", name, "--at", "2099-13-45"], corpus)
    check("CUT13b cut --at that is not a real date is refused", rc_ == 2, out)
    inside = corpus / "_projects" / name / "sources" / "CONV-001" / "conversation.md"
    rc_, out = proj(["capture", "--project", name, "--source", "CONV-001", "--file",
                     str(inside), "--at", "2026-09-05"], corpus)
    check("CUT14 re-feeding the corpus's own file is not a capture",
          rc_ == 2 and "inside the corpus" in out, out)
    data = read_project_manifest(corpus, name)
    for s_ in data["sources"]:
        if s_["source_id"] == "CONV-003":
            s_["revisions"][-1]["captured_at"] = "unknown"
    write_project_manifest(corpus, name, data)
    rc_, out = proj(["validate", "--project", name], corpus)
    check("CUT15 a captured_at that is not a date is SOURCE_DATE_INVALID",
          "SOURCE_DATE_INVALID" in out, out)
    for s_ in data["sources"]:
        if s_["source_id"] == "CONV-003":
            s_["revisions"][-1]["captured_at"] = "2026-09-01"
    write_project_manifest(corpus, name, data)
    # F-5: the review queue is bound by the cut
    corpus3 = swept_and_routed(Path(tmp) / "rq", "rq")
    for sid, text in (("CONV-001", SWEEP_CHAT_1), ("CONV-002", SWEEP_CHAT_2),
                      ("CONV-003", SWEEP_CHAT_3)):
        capture(corpus3, "rq", sid, text, tmp, at="2026-08-30")
    q = corpus3 / "_projects" / "rq" / "review-queue.md"
    q.write_text("---\ntitle: rq — review queue\ntype: review-queue\nproject: rq\n"
                 "owner: Johnny (Nortropic)\nappend_only: true\n---\n\n# Review queue: rq\n\n"
                 "## RQ-001\n- date: 2026-08-30\n- issue: is the gate deferred?\n"
                 "- affects: CONV-001\n- recommendation: ask\n- evidence: msg 1\n"
                 "- owner_judgment_required: yes\n\n## RQ-002\n- date: 2026-08-30\n"
                 "- resolves: RQ-001\n- question: deferred?\n- owner_answer: Yes, deferred.\n",
                 encoding="utf-8")
    rc_, out = proj(["cut", "--project", "rq", "--at", "2026-08-30"], corpus3)
    assert rc_ == 0, out
    q.write_text(q.read_text(encoding="utf-8").replace("Yes, deferred.", "Yes, deferred — "
                                                                       "for v1 only."),
                 encoding="utf-8")
    rc_, out = proj(["validate", "--project", "rq"], corpus3)
    check("CUT16 an owner answer rewritten after the cut breaks the cut",
          "SOURCE_CUT_BROKEN" in out and "review-queue.md" in out, out)
    # a hard gap refuses a cut
    corpus2 = sweep_project(Path(tmp) / "gap", "gap")
    capture(corpus2, "gap", "CONV-001", SWEEP_CHAT_1, tmp)
    rc_, out = proj(["cut", "--project", "gap", "--at", "2026-08-30"], corpus2)
    check("CUT12 a project with hard gaps cannot be cut",
          rc_ == 1 and "CUT_REFUSED" in out and "hard gap" in out, out)


# ==================================================== S2: attachments ======

def scenario_register_attachment(tmp):
    corpus = swept_and_routed(tmp)
    name = "demo-sweep"
    payload = Path(tmp) / "masterplan.md"
    payload.write_text("# Masterplan\n\n## Kapitel två\n\nLedgern är valfri.\n",
                       encoding="utf-8")
    rc_, out = proj(["register-attachment", "--project", name, "--source", "CONV-003",
                     "--file", str(payload), "--original-filename", "masterplan.md",
                     "--declared-kind", "uploaded_file", "--materiality", "MATERIAL",
                     "--message-binding", "owner msg 1", "--at", "2026-08-30"], corpus)
    check("ATT1 bytes of a declared attachment are registered with a hash",
          rc_ == 0 and "REGISTERED CONV-003 r1 ATT-003-001" in out
          and "STATUS=CAPTURED_CONTENT" in out, out)
    mpath = corpus / "_projects" / name / "sources" / "CONV-003" / "attachments-r1.json"
    man = json.loads(mpath.read_text(encoding="utf-8"))
    row = man["attachments"][0]
    art = corpus / row["artifact_path"]
    check("ATT1b the manifest row carries content_sha256 and an artifact under attachments/",
          row["content_sha256"] == hashlib.sha256(payload.read_bytes()).hexdigest()
          and art.is_file() and art.read_bytes() == payload.read_bytes(), json.dumps(row))
    check("ATT1c declared and observed are measured from the transcript, not asserted",
          man["declared_count"] == 1 and man["attachment_manifest_version"] == 2, json.dumps(man))
    rc_, out = proj(["validate", "--project", name], corpus)
    check("ATT2 the project validates with the registered attachment",
          rc_ == 0 and "ATTACHMENT_ARTIFACT_UNCLAIMED" not in out
          and "MANIFEST_TREE_MISMATCH" not in out, out)
    rc_, out = proj(["attachments", "--project", name], corpus)
    check("ATT3 the surface reports the bytes and derives FULL_SOURCE_CAPTURE for CONV-003",
          "ATTACHMENTS_WITH_BYTES=1" in out and re.search(r"CONV-003\s+r1\s+1\s+\d+\s+AGREE\s+YES", out),
          out)
    rc_, out = proj(["register-attachment", "--project", name, "--source", "CONV-003",
                     "--file", str(payload), "--at", "2026-08-30"], corpus)
    check("ATT4 registering the same bytes under a new id is refused (declare DUPLICATE)",
          rc_ == 2 and "already registered as ATT-003-001" in out, out)
    other = Path(tmp) / "other.md"
    other.write_text("different bytes\n", encoding="utf-8")
    rc_, out = proj(["register-attachment", "--project", name, "--source", "CONV-003",
                     "--file", str(other), "--attachment-id", "ATT-003-001"], corpus)
    check("ATT5 replacing registered bytes under an existing id is refused",
          rc_ == 2 and "never replaced" in out, out)
    rc_, out = proj(["register-attachment", "--project", name, "--source", "CONV-003",
                     "--file", str(other), "--recovered"], corpus)
    check("ATT6 --recovered without --recovery-provenance is refused",
          rc_ == 2 and "recovery-provenance" in out, out)
    rc_, out = proj(["register-attachment", "--project", name, "--source", "CONV-003",
                     "--file", str(other), "--revision", "7"], corpus)
    check("ATT7 a revision other than the bound one is refused",
          rc_ == 2 and "BOUND revision" in out, out)
    # F-3: a recorded bytes-absent row is a FACT; bytes for it are a RECOVERY.
    # Own fixture: a transcript that DECLARES two attachments, one registered.
    corpus_r = sweep_project(Path(tmp) / "rec", "rec")
    for sid, text in (("CONV-001", SWEEP_CHAT_1), ("CONV-002", SWEEP_CHAT_2),
                      ("CONV-003", SWEEP_CHAT_3.replace("1 bilaga inventerad", "2 bilagor inventerade"))):
        capture(corpus_r, "rec", sid, text, tmp)
    proj(["register-attachment", "--project", "rec", "--source", "CONV-003",
          "--file", str(payload), "--materiality", "MATERIAL"], corpus_r)
    mpath_r = corpus_r / "_projects" / "rec" / "sources" / "CONV-003" / "attachments-r1.json"
    man = json.loads(mpath_r.read_text(encoding="utf-8"))
    man["attachments"].append({"attachment_id": "ATT-003-002", "ordinal": 2,
                               "capture_status": "UNAVAILABLE", "materiality": "MATERIAL",
                               "semantic_accessibility": "UNAVAILABLE",
                               "declared_kind": "uploaded_file"})
    man["full_source_capture"] = "NO"     # what the rows now derive; a hand-written manifest says so
    mpath_r.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    rc_, out = proj(["validate", "--project", "rec"], corpus_r)
    check("ATT7a the fixture with one UNAVAILABLE row validates (WARN only)", rc_ == 0, out)
    later = Path(tmp) / "plausible.md"
    later.write_text("a plausible file that fits the name\n", encoding="utf-8")
    rc_, out = proj(["register-attachment", "--project", "rec", "--source", "CONV-003",
                     "--file", str(later), "--attachment-id", "ATT-003-002"], corpus_r)
    check("ATT7b bytes for a recorded UNAVAILABLE row are refused without recovery "
          "provenance — a recorded state is never reclassified by plain registration",
          rc_ == 2 and "RECOVERY" in out, out)
    man2 = json.loads(mpath_r.read_text(encoding="utf-8"))
    check("ATT7c the refused registration left the row UNAVAILABLE",
          [a for a in man2["attachments"] if a["attachment_id"] == "ATT-003-002"][0]
          ["capture_status"] == "UNAVAILABLE", json.dumps(man2)[:300])
    rc_, out = proj(["register-attachment", "--project", "rec", "--source", "CONV-003",
                     "--file", str(later), "--attachment-id", "ATT-003-002", "--recovered",
                     "--recovery-provenance", "owner's original from the tool that produced "
                     "it, matched on name+upload stamp"], corpus_r)
    man3 = json.loads(mpath_r.read_text(encoding="utf-8"))
    row2 = [a for a in man3["attachments"] if a["attachment_id"] == "ATT-003-002"][0]
    check("ATT7d with --recovered and provenance the row becomes RECOVERED_EXACT and drops "
          "the bytes-absent semantic state",
          rc_ == 0 and row2["capture_status"] == "RECOVERED_EXACT"
          and "semantic_accessibility" not in row2 and row2.get("recovery_provenance"), out)
    rc_, out = proj(["validate", "--project", "rec"], corpus_r)
    check("ATT7e the recovered row validates", rc_ == 0, out)
    # MUTANT: the artifact bytes change on disk → ATTACHMENT_ARTIFACT_MUTATED
    art.write_bytes(art.read_bytes() + b"\ntampered\n")
    rc_, out = proj(["validate", "--project", name], corpus)
    check("ATT8 a registered artifact whose bytes moved fails ATTACHMENT_ARTIFACT_MUTATED",
          rc_ != 0 and "ATTACHMENT_ARTIFACT_MUTATED" in out, out)
    art.write_bytes(payload.read_bytes())
    # the cut binds the manifest and the artifact
    for sid, text in (("CONV-001", SWEEP_CHAT_1), ("CONV-002", SWEEP_CHAT_2),
                      ("CONV-003", SWEEP_CHAT_3)):
        capture(corpus, name, sid, text, tmp, at="2026-08-30")
    rc_, out = proj(["cut", "--project", name, "--at", "2026-08-30"], corpus)
    data = read_project_manifest(corpus, name)
    lines = (data.get("source_cut") or {}).get("lines") or []
    if not lines:
        print("CUT OUTPUT:", out[:1500])
    check("ATT9 the cut binds the attachment manifest and the artifact bytes",
          rc_ == 0 and any(ln.startswith("ATT _projects") for ln in lines)
          and any(ln.startswith("ART _projects") for ln in lines), json.dumps(lines))
    art.write_bytes(art.read_bytes() + b"x")
    rc_, out = proj(["validate", "--project", name], corpus)
    check("ATT10 an artifact changed after the cut breaks the cut too",
          "SOURCE_CUT_BROKEN" in out, out)


# ====================================================== S6: documents ======

def scenario_register_document(tmp):
    corpus = swept_and_routed(tmp)
    name = "demo-sweep"
    doc = Path(tmp) / "spec.md"
    doc.write_text("# Spec\n\nRule one.\nRule two.\n", encoding="utf-8")
    rc_, out = proj(["register-document", "--project", name, "--file", str(doc),
                     "--role", "external_reference", "--title", "Spec"], corpus)
    check("DOC1 an external_reference without --used-in is refused",
          rc_ == 2 and "used" in out.lower(), out)
    rc_, out = proj(["register-document", "--project", name, "--file", str(doc),
                     "--role", "external_reference", "--title", "Spec",
                     "--used-in", "CONV-001:2-3", "--at", "2026-08-30"], corpus)
    check("DOC1b a use citation whose turns never name the document is refused "
          "(SOURCE_USE_UNANCHORED)", rc_ == 1 and "SOURCE_USE_UNANCHORED" in out, out)
    rc_, out = proj(["register-document", "--project", name, "--file", str(doc),
                     "--role", "external_reference", "--title", "Spec",
                     "--used-in", "CONV-001:2-3", "--use-anchor", "e",
                     "--at", "2026-08-30"], corpus)
    check("DOC1c (R2-3) a one-letter anchor is not an anchor", rc_ == 1 and "SOURCE_USE_UNANCHORED" in out,
          out)
    rc_, out = proj(["register-document", "--project", name, "--file", str(doc),
                     "--role", "external_reference", "--title", "Spec",
                     "--used-in", "CONV-001:2-3", "--use-anchor", "ipelin",
                     "--at", "2026-08-30"], corpus)
    check("DOC1d (R2-3) an anchor inside a word does not match (word boundaries)",
          rc_ == 1 and "SOURCE_USE_UNANCHORED" in out, out)
    rc_, out = proj(["register-document", "--project", name, "--file", str(doc),
                     "--role", "external_reference", "--title", "Spec",
                     "--used-in", "CONV-001:2-3", "--use-anchor", "pipelinen",
                     "--at", "2026-08-30"], corpus)
    check("DOC2 an external_reference with evidenced, anchored use is registered as DOC-001",
          rc_ == 0 and "REGISTERED DOC-001 (external_reference)" in out
          and "LINES=4" in out, out)
    data = read_project_manifest(corpus, name)
    d = [s for s in data["sources"] if s["source_id"] == "DOC-001"][0]
    check("DOC2b the document record is a document, CAPTURED, line-counted, and moved "
          "the inventory", d["kind"] == "document" and d["state"] == "CAPTURED"
          and d["revisions"][0]["line_count"] == 4 and data["inventory_revision"] == 5,
          json.dumps(d))
    rc_, out = proj(["validate", "--project", name], corpus)
    check("DOC3 the project validates with a document source", rc_ == 0, out)
    rc_, out = proj(["coverage", "--project", name], corpus)
    check("DOC4 coverage reports documents separately from conversations",
          "SOURCES=3" in out and "DOCUMENT_SOURCES=1  (external_reference:1)" in out
          and "DOCUMENT_COVERAGE_COMPLETE=YES" in out, out)
    rc_, out = proj(["register-document", "--project", name, "--file", str(doc),
                     "--role", "project_file", "--title", "Spec again"], corpus)
    check("DOC5 the same bytes are never registered twice", rc_ == 0 and "REGISTER_UNCHANGED" in out,
          out)
    # MUTANTS on the record
    def mutate(fn, code, label):
        data = read_project_manifest(corpus, name)
        d = [s for s in data["sources"] if s["source_id"] == "DOC-001"][0]
        keep = json.loads(json.dumps(d))
        fn(d)
        write_project_manifest(corpus, name, data)
        rc_, out = proj(["validate", "--project", name], corpus)
        check(label, code in out, out)
        d.clear()
        d.update(keep)
        write_project_manifest(corpus, name, data)
    mutate(lambda d: d.__setitem__("evidence_role", "nearby_file"), "DOCUMENT_ROLE_INVALID",
           "DOC6 an evidence role outside the closed set is refused")
    mutate(lambda d: d.__setitem__("used_in", []), "SOURCE_USE_UNEVIDENCED",
           "DOC7 an external_reference whose use evidence is removed is unevidenced")
    mutate(lambda d: d.__setitem__("used_in", [{"source_id": "CONV-001", "messages": "2-9"}]),
           "SOURCE_USE_UNRESOLVED",
           "DOC8 a use citation past the conversation does not resolve")
    mutate(lambda d: d.__setitem__("used_in", [{"source_id": "CONV-077", "messages": "1"}]),
           "SOURCE_USE_UNRESOLVED",
           "DOC9 a use citation into a conversation the project lacks does not resolve")
    mutate(lambda d: d["revisions"][0].__setitem__("line_count", 9),
           "DOCUMENT_LINE_COUNT_MISMATCH",
           "DOC10 a line_count the bytes do not hold is refused")
    mutate(lambda d: d.__setitem__("kind", "spreadsheet"), "SOURCE_KIND_INVALID",
           "DOC11 an unknown source kind falls closed")
    mutate(lambda d: d.__setitem__("state", "ROUTED"), "SOURCE_STATE_INVALID",
           "DOC12 a conversation lifecycle state on a document is refused")
    docfile = corpus / d["revisions"][0]["path"]
    docfile.write_text(docfile.read_text() + "\nedited\n", encoding="utf-8")
    rc_, out = proj(["validate", "--project", name], corpus)
    check("DOC13 a document whose bytes changed after registration is refused",
          "PROJECT_SOURCE_HASH_MISMATCH" in out, out)
    docfile.write_text(doc.read_text(), encoding="utf-8")
    # conversation_attachment must name a registered attachment
    rc_, out = proj(["register-document", "--project", name, "--file", str(Path(tmp) / "x.md"),
                     "--role", "conversation_attachment"], corpus)
    check("DOC14 a conversation_attachment without --attachment is refused",
          rc_ == 2, out)
    att = Path(tmp) / "att.md"
    att.write_text("attachment bytes\n", encoding="utf-8")
    proj(["register-attachment", "--project", name, "--source", "CONV-003",
          "--file", str(att), "--materiality", "MATERIAL"], corpus)
    doc2 = Path(tmp) / "att-as-doc.md"
    doc2.write_text("attachment bytes as a document\n", encoding="utf-8")
    rc_, out = proj(["register-document", "--project", name, "--file", str(doc2),
                     "--role", "conversation_attachment",
                     "--attachment", "CONV-003:r1:ATT-003-009"], corpus)
    check("DOC15 a conversation_attachment naming an unregistered attachment is refused",
          rc_ == 1 and "DOCUMENT_ATTACHMENT_UNBOUND" in out, out)
    rc_, out = proj(["register-document", "--project", name, "--file", str(doc2),
                     "--role", "conversation_attachment",
                     "--attachment", "CONV-003:r1:ATT-003-001"], corpus)
    check("DOC15b a conversation_attachment whose bytes differ from the registered "
          "attachment is refused", rc_ == 1 and "DOCUMENT_ATTACHMENT_UNBOUND" in out, out)
    same = Path(tmp) / "att-same.md"
    same.write_bytes(att.read_bytes())
    rc_, out = proj(["register-document", "--project", name, "--file", str(same),
                     "--role", "conversation_attachment",
                     "--attachment", "CONV-003:r1:ATT-003-001"], corpus)
    check("DOC16 a conversation_attachment that IS the registered attachment's bytes is "
          "accepted", rc_ == 0 and "REGISTERED DOC-002 (conversation_attachment)" in out, out)
    # a binary with a text derivative
    pdfish = Path(tmp) / "blob.pdf"
    pdfish.write_bytes(b"%PDF-1.4\x00\x01binary\x00")
    txt = Path(tmp) / "blob.txt"
    txt.write_text("page one\npage two\n", encoding="utf-8")
    rc_, out = proj(["register-document", "--project", name, "--file", str(pdfish),
                     "--role", "project_file", "--text-derivative", str(txt)], corpus)
    check("DOC17 a text derivative without its tool is refused", rc_ == 2 and "text-tool" in out,
          out)
    rc_, out = proj(["register-document", "--project", name, "--file", str(pdfish),
                     "--role", "project_file"], corpus)
    check("DOC17b a binary with no text derivative registers with DOCUMENT_UNADDRESSABLE "
          "(a WARN: nothing can cite it by line)",
          rc_ == 0 and "DOCUMENT_UNADDRESSABLE" in out, out)
    data = read_project_manifest(corpus, name)
    data["sources"] = [d for d in data["sources"] if d["source_id"] != "DOC-003"]
    write_project_manifest(corpus, name, data)
    shutil.rmtree(corpus / "_projects" / name / "sources" / "DOC-003")
    rc_, out = proj(["register-document", "--project", name, "--file", str(pdfish),
                     "--role", "project_file", "--text-derivative", str(txt),
                     "--text-tool", "pdftotext -layout (poppler 26.08)"], corpus)
    check("DOC18 a binary registers with a line-addressable text derivative",
          rc_ == 0 and "LINES=None" in out and "TEXT_DERIVATIVE=yes" in out, out)
    data = read_project_manifest(corpus, name)
    d3 = [s for s in data["sources"] if s["source_id"] == "DOC-003"][0]
    tpath = corpus / d3["revisions"][0]["text_derivative"]["path"]
    tpath.write_text("page one\n", encoding="utf-8")
    rc_, out = proj(["validate", "--project", name], corpus)
    check("DOC19 a text derivative whose bytes moved is refused",
          "DOCUMENT_TEXT_DERIVATIVE_MISMATCH" in out, out)


# ============================================================ S5: chain ====

def scenario_chain(tmp):
    corpus = swept_and_routed(tmp, verified=True)
    name = "demo-sweep"
    for sid, text in (("CONV-001", SWEEP_CHAT_1), ("CONV-002", SWEEP_CHAT_2),
                      ("CONV-003", SWEEP_CHAT_3)):
        capture(corpus, name, sid, text, tmp, at="2026-08-30")
    rc_, out = proj(["cut", "--project", name, "--at", "2026-08-30"], corpus)
    assert rc_ == 0, out
    cut = read_project_manifest(corpus, name)["source_cut"]["cut_sha256"]
    rc_, out = proj(["chain", "--project", name], corpus)
    check("CH1 with no compile the chain is incomplete and says so",
          rc_ == 1 and "RND_COMPILE=NONE" in out and "CHAIN_COMPLETE=NO" in out
          and "SOURCE_CUT=%s" % cut in out and "ENUMERATION_VERIFIED=YES" in out, out)
    # a version-4 compile bound to the cut, every turn accounted for
    rc_, out = F.run(SCRIPTS / "rnd_contract.py",
                     ["init", "--compile", "chain-v4", "--project", name, "--atomic",
                      "--at", "2026-08-30", "--corpus", str(corpus)])
    assert rc_ == 0, out
    ir_path = corpus / "_rnd" / "chain-v4" / "rnd-ir.json"
    ir = json.loads(ir_path.read_text(encoding="utf-8"))
    check("CH2 init binds the compile to the project's cut",
          ir["source_set"].get("cut_sha256") == cut, json.dumps(ir["source_set"])[:400])
    items = [
        {"id": "RND-001", "kind": "OWNER_DECISION", "atomicity": "ATOMIC",
         "claim": "The pipeline is built first.", "scope": "sequencing",
         "provenance": [{"source_id": "CONV-001", "revision": 1, "messages": "3"}],
         "authority_class": "owner", "owner_authority_basis": "owner-authored",
         "quote": "Ja, pipelinen först — beslutat.", "standing": "CURRENT_CANDIDATE",
         "uncertainty": "none — verbatim", "tags": [], "relations": []},
        {"id": "RND-002", "kind": "OPTION", "atomicity": "ATOMIC",
         "claim": "Build the pipeline before the quality gate.", "scope": "sequencing",
         "provenance": [{"source_id": "CONV-001", "revision": 1, "messages": "2"}],
         "authority_class": "derived", "standing": "PROPOSAL",
         "uncertainty": "assistant proposal", "tags": [],
         "relations": [{"rel": "supports", "target": "RND-001"}]},
        {"id": "RND-003", "kind": "OBSERVATION", "atomicity": "ATOMIC",
         "claim": "Two ideas were raised in the opening turn: an export pipeline and a "
                  "quality gate.", "scope": "intake",
         "provenance": [{"source_id": "CONV-001", "revision": 1, "messages": "1"}],
         "authority_class": "evidence", "uncertainty": "none", "tags": [], "relations": []},
        {"id": "RND-004", "kind": "OBSERVATION", "atomicity": "ATOMIC",
         "claim": "The attached masterplan's chapter two says the ledger is optional.",
         "scope": "intake",
         "provenance": [{"source_id": "CONV-003", "revision": 1, "messages": "1-2"}],
         "authority_class": "evidence", "uncertainty": "the attachment itself is "
                                                       "registered; content read by "
                                                       "the assistant",
         "tags": [], "relations": []},
    ]
    conv2 = corpus / "_projects" / name / "sources" / "CONV-002" / "conversation.md"
    n2 = conv2.read_text(encoding="utf-8").count("## Meddelande ")
    for it in items:
        it["fingerprint"] = rc.record_fingerprint(it)
    ir["items"] = items
    ir["turn_ledger"] = [{"source_id": "CONV-002", "messages": "1-%d" % n2,
                          "reason": "no-material-content"}]
    # CONV-002's turns: owner turns need owner reasons — split by role
    roles = rc.genuine_message_roles(rc.transcript_source_region(
        conv2.read_text(encoding="utf-8"))[0])[0]
    ir["turn_ledger"] = [
        {"source_id": "CONV-002", "messages": str(n),
         "reason": "no-material-content" if r == rc.ROLE_OWNER else "no-material-content"}
        for n, r in sorted(roles.items())]
    ir["progression"] = [{"source_id": "CONV-001", "examined_through": 3},
                         {"source_id": "CONV-002", "examined_through": n2},
                         {"source_id": "CONV-003", "examined_through": 2}]
    ir["coverage"][0].update({"state": "PARTIALLY_EXPLORED", "basis": ["RND-003", "RND-004"]})
    ir["coverage"][1].update({"state": "PARTIALLY_EXPLORED", "basis": ["RND-001"]})
    ir["coverage"][2].update({"state": "PARTIALLY_EXPLORED", "basis": ["RND-002"]})
    ir_path.write_text(json.dumps(ir, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rc_, out = F.run(SCRIPTS / "rnd_contract.py",
                     ["validate", "--compile", "chain-v4", "--corpus", str(corpus)])
    check("CH3 the version-4 compile validates with every turn accounted for",
          "RND_TURN_UNACCOUNTED" not in out and not re.search(r"^FAIL", out, re.M), out)
    rc_, out = F.run(SCRIPTS / "rnd_contract.py",
                     ["render", "--compile", "chain-v4", "--write", "--corpus", str(corpus)])
    ir_sha = hashlib.sha256(ir_path.read_bytes()).hexdigest()
    (corpus / "_rnd" / "chain-v4" / "compile-audit.md").write_text(
        "---\ntitle: audit\ntype: compile-audit\ncompile: chain-v4\nappend_only: true\n---\n\n"
        "## AUDIT-1\n- auditor: fresh reviewer\n- audited_at: 2026-08-30\n"
        "- scope: ir_sha256=%s\n- verdict: PASS\n- atomicity_reviewed: yes\n"
        "- compound_suspects_reviewed: none\n- owner_ledger_reviewed: %s\n"
        % (ir_sha, ", ".join("CONV-002:%d" % n for n, r in sorted(roles.items())
                             if r == rc.ROLE_OWNER)),
        encoding="utf-8")
    rc_, out = proj(["chain", "--project", name, "--compile", "chain-v4"], corpus)
    check("CH4 with the compile bound and audited, only the projection is missing",
          rc_ == 1 and "RND_COMPILE_VALID=YES" in out and "RND_COMPILE_AUDITED=YES" in out
          and "RND_BOUND_TO_CUT=YES" in out and "TURNS_ACCOUNTED=100%" in out
          and "PROJECTION_VAULT=NONE" in out and "CHAIN_COMPLETE=NO" in out, out)
    vault = Path(tmp) / "vault"
    rc_, out = projection(["render", "--compile", "chain-v4", "--vault", str(vault), "--write"],
                          corpus)
    assert rc_ == 0, out
    rc_, out = proj(["chain", "--project", name, "--compile", "chain-v4",
                     "--vault", str(vault)], corpus)
    check("CH5 the whole chain is complete: exit 0 and CHAIN_COMPLETE=YES",
          rc_ == 0 and "CHAIN_COMPLETE=YES" in out and "PROJECTION_VERIFIED=YES" in out
          and "CORPUS_INTEGRITY=PASS" in out, out)
    # pull each link, one at a time
    ir2 = json.loads(ir_path.read_text(encoding="utf-8"))
    ir2["turn_ledger"] = ir2["turn_ledger"][1:]
    ir_path.write_text(json.dumps(ir2, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rc_, out = proj(["chain", "--project", name, "--compile", "chain-v4",
                     "--vault", str(vault)], corpus)
    check("CH6 dropping one ledger entry breaks the chain (compile invalid, projection stale)",
          rc_ == 1 and "RND_COMPILE_VALID=NO" in out and "CHAIN_COMPLETE=NO" in out
          and "PROJECTION_VERIFIED=NO" in out, out)
    ir_path.write_text(json.dumps(ir, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rc_, out = proj(["chain", "--project", name, "--compile", "chain-v4",
                     "--vault", str(vault)], corpus)
    check("CH7 restoring the IR restores the chain", rc_ == 0 and "CHAIN_COMPLETE=YES" in out, out)
    (vault / "kort" / "RND-004.md").unlink()
    rc_, out = proj(["chain", "--project", name, "--compile", "chain-v4",
                     "--vault", str(vault)], corpus)
    check("CH8 a missing card breaks the chain through the projection link",
          rc_ == 1 and "PROJECTION_VERIFIED=NO" in out, out)
    projection(["render", "--compile", "chain-v4", "--vault", str(vault), "--write"], corpus)
    src = corpus / "_projects" / name / "sources" / "CONV-003" / "conversation.md"
    keep = src.read_bytes()
    src.write_bytes(keep + b"\nmoved\n")
    rc_, out = proj(["chain", "--project", name, "--compile", "chain-v4",
                     "--vault", str(vault)], corpus)
    check("CH9 a source byte moving after the cut breaks the chain at the cut",
          rc_ == 1 and "SOURCE_CUT_STATE=BROKEN" in out and "CHAIN_COMPLETE=NO" in out, out)
    src.write_bytes(keep)
    data = read_project_manifest(corpus, name)
    data["enumeration"]["verified"] = False
    write_project_manifest(corpus, name, data)
    rc_, out = proj(["chain", "--project", name, "--compile", "chain-v4",
                     "--vault", str(vault)], corpus)
    check("CH10 an unverified enumeration cannot be typed away — the chain says NO",
          rc_ == 1 and "ENUMERATION_VERIFIED=NO" in out, out)
    data["enumeration"]["verified"] = True
    write_project_manifest(corpus, name, data)
    # F-1: a compile that DROPS a captured source, or excludes it with a false reason
    def with_ir(mut, label, code):
        ir3 = json.loads(json.dumps(ir))
        mut(ir3)
        ir_path.write_text(json.dumps(ir3, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        rc_, out = F.run(SCRIPTS / "rnd_contract.py",
                         ["validate", "--compile", "chain-v4", "--corpus", str(corpus)])
        rc2, out2 = proj(["chain", "--project", name, "--compile", "chain-v4",
                          "--vault", str(vault)], corpus)
        check(label, code in out and rc2 == 1 and "CHAIN_COMPLETE=NO" in out2, out + out2)
        ir_path.write_text(json.dumps(ir, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    with_ir(lambda i: i["source_set"].__setitem__(
        "sources", [x for x in i["source_set"]["sources"] if x["source_id"] != "CONV-003"]),
        "CH11 dropping a captured source from the IR is RND_SOURCE_SET_INCOMPLETE and the "
        "chain says NO", "RND_SOURCE_SET_INCOMPLETE")
    with_ir(lambda i: i["source_set"].__setitem__(
        "sources", [x if x["source_id"] != "CONV-003" else
                    {"source_id": "CONV-003", "excluded": "no captured revision — a gap, "
                                                           "recorded rather than hidden"}
                    for x in i["source_set"]["sources"]]),
        "CH12 excluding a captured source with the tool's own gap text is "
        "RND_SOURCE_SET_INCOMPLETE", "RND_SOURCE_SET_INCOMPLETE")
    with_ir(lambda i: i["source_set"].__setitem__(
        "sources", [x if x["source_id"] != "CONV-003" else
                    {"source_id": "CONV-003", "excluded": "outside the compile's declared "
                                                           "scope (--only) — not compiled"}
                    for x in i["source_set"]["sources"]]),
        "CH13 the scope phrase without a declared scope list is RND_SOURCE_SET_INCOMPLETE",
        "RND_SOURCE_SET_INCOMPLETE")
    # F-16: a vault inside the corpus is never accepted
    inside_vault = corpus / "_projection-vault"
    shutil.copytree(vault, inside_vault)
    rc_, out = proj(["chain", "--project", name, "--compile", "chain-v4",
                     "--vault", str(inside_vault)], corpus)
    check("CH14 a vault inside the corpus fails the projection link",
          rc_ == 1 and "PROJECTION_VERIFIED=NO" in out, out)
    shutil.rmtree(inside_vault)


def main():
    for sc in (scenario_cut, scenario_register_attachment, scenario_register_document,
               scenario_chain):
        tmp = tempfile.mkdtemp(prefix="project-v44-")
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
