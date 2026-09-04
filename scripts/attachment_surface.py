#!/usr/bin/env python3
"""Attachment source surface — declared vs observed, reconciled or refused.

The fourth mechanism in the intake contract, and the one the r38 attachment
falsification proved was missing. `project_contract.py` records WHICH conversations
were captured and hashes their message bodies; this module records what those bodies
were NOT: the documents, pastes, images and archives the conversation rested on.

The distinction it exists to keep:

    CONVERSATION BODY  !=  COMPLETE CONVERSATION SOURCE SURFACE

when attachments exist. A body digest answers "are these the same messages?". It has
never answered "is this the whole source?", and r38 showed what happens when the two
are read as one: 98 declared attachments, 88 with no bytes at all, every body green.

Two independent readings of the same source, never one:

  DECLARED  what the capture's own header note claims - a count, sometimes names.
            It is prose written ABOUT the conversation, so it is exactly as
            trustworthy as any other assertion: not very.

  OBSERVED  what the message bodies independently evidence - platform citation
            markers, upload announcements, the owner naming a path. Structural
            signals emitted by the platform, not by the builder.

When they agree the surface reconciles. When they disagree the source is NOT
silently repaired and NOT silently trusted: it carries DISAGREE, and every
downstream completeness question answers NO or UNKNOWN until a human resolves it.

Why it is not a filename rule
-----------------------------
The two `Inklistrad text.txt` uploads AMR-004 found are a symptom. A rule keyed to
that name would have caught exactly those two and nothing else, and would have read
as coverage. The generalisation is the CONTRADICTION: a body that evidences uploads
its own header does not declare. Detection is by platform-native marker, upload
verbs and owner-supplied paths - none of which mention a filename.
"""
import io
import json
import re

from intake_common import (
    ATTACHMENT_CAPTURE_STATES, ATTACHMENT_MATERIALITY, RECONCILIATION_STATES,
    Finding, attachment_bytes_available, full_source_capture, sha256_file,
    transcript_source_region,
)

ATTACHMENT_MANIFEST_VERSION = 1
ATT_ID_RE = re.compile(r"^ATT-[A-Za-z0-9]+-\d{3,}$")

# ---------------------------------------------------------------- declared --

# The builder writes the chip note in Swedish; `N bilagor inventerade` is the shape
# every capture in the corpus uses. English is accepted so the mechanism is not
# language-locked. The number is what matters - the prose around it is decoration.
_DECLARED_RE = re.compile(
    r"(\d+)\s*(?:bilag(?:a|or)|attachments?)\b", re.I)


def declared_attachments(text):
    """(count, raw_phrase) read from the builder header, or (None, "") if silent.

    None and 0 are different answers. None means the header never spoke about
    attachments, which is not the same as claiming there are none - and a source that
    never spoke cannot be said to agree with anything.
    """
    region, found = transcript_source_region(text)
    header = text[:len(text) - len(region)] if found else text
    m = _DECLARED_RE.search(header)
    if not m:
        return None, ""
    start = max(0, m.start() - 40)
    return int(m.group(1)), re.sub(r"\s+", " ", header[start:m.end() + 160]).strip()


# ---------------------------------------------------------------- observed --

# ChatGPT emits its file citations as `filecite<U+E202>turnNfileM<U+E202>...<U+E201>`.
# The private-use delimiters are the platform's own, so this is a STRUCTURAL signal:
# the builder cannot forge it and cannot accidentally omit it while copying the body
# verbatim. `(turn, file)` pairs are citation SITES, not distinct files - the same
# document cited in three turns yields three pairs - so the count is reported as an
# upper bound on distinct attachments and a lower bound on "file-backed evidence
# exists here". It is used to detect CONTRADICTION, never to mint a count.
_FILECITE_RE = re.compile(u"fileciteturn(\\d+)file(\\d+)")
_ANYCITE_RE = re.compile(u"(\\w*?)citeturn(\\d+)([a-z]+)(\\d+)")

# An upload the body announces in words. Kept deliberately small and verb-shaped:
# these are things a conversation SAYS happened, in either language.
_UPLOAD_RE = re.compile(
    r"(?:ladda(?:t|de)?\s+upp|uppladdad|uppladdning(?:en|ar)?|bifogad|bifogat"
    r"|upload(?:ed|s)?|attached\s+file|the\s+uploaded\s+(?:file|archive|document))",
    re.I)

_EXT = (r"pdf|txt|md|png|jpe?g|gif|webp|heic|tgz|tar|gz|zip|csv|json|docx?|xlsx?")

# A NAMED UPLOAD IDENTITY: a document name carrying an upload stamp.
#
# This is the signal that generalises AMR-004 without naming it. `Inklistrad text.txt`
# appears TWICE in CONV-013's body with two different upload times, and the header
# declares five chips dated 20260825-20260826 - neither of which is the 24 Aug pair.
# A filename rule would have caught exactly those two files and nothing else, and
# would have read as coverage. Keying on (name, upload-stamp) instead catches the
# general shape: a document the body says was uploaded, whose identity the declared
# surface does not contain. The filename is data here, never logic.
_NAMED_UPLOAD_RE = re.compile(
    r"`([^`\n]{1,80}\.(?:%s))`[^\n]{0,120}?(\d{1,2}[:.]\d{2}[:.]\d{2})" % _EXT, re.I)

# Paths the body merely MENTIONS are deliberately NOT an upload signal. Tried and
# rejected: it read every repo path a conversation discusses as an attachment, which
# scored CONV-008 - the corpus's own negative control, 47 inline pastes and zero
# chips - at seven phantom uploads. A detector that accuses the clean case is worse
# than none, because the noise is what teaches people to ignore the real findings.
_MENTIONED_PATH_RE = re.compile(
    r"(?:^|\s)(?:/Users/[^\s\"\'<>]+|~/[^\s\"\'<>]+)\.(?:%s)" % _EXT, re.I)


def named_upload_identities(text):
    """Distinct (document-name, upload-stamp) pairs the message bodies announce.

    An identity, not a count. Two uploads of the same filename at different times are
    two attachments, and that is precisely the case the declared surface lost.
    """
    region, _ = transcript_source_region(text)
    return sorted(set((n.strip(), s.strip()) for n, s in _NAMED_UPLOAD_RE.findall(region)))


def observed_signals(text):
    """Structural evidence, in the message bodies, that files were part of the source.

    Everything here is measured from the SOURCE REGION only: the builder's header is a
    declaration, and letting it corroborate itself would make reconciliation circular.
    """
    region, _ = transcript_source_region(text)
    sites = set(_FILECITE_RE.findall(region))
    kinds = {}
    for _pre, turn, kind, idx in _ANYCITE_RE.findall(region):
        kinds.setdefault(kind, set()).add((turn, idx))
    return {
        "filecite_sites": len(sites),
        "filecite_turns": len(set(t for t, _ in sites)),
        "upload_phrases": len(_UPLOAD_RE.findall(region)),
        "named_upload_identities": named_upload_identities(text),
        "mentioned_paths": len(set(_MENTIONED_PATH_RE.findall(region))),
        "cite_kinds": dict((k, len(v)) for k, v in sorted(kinds.items())),
    }


def observed_lower_bound(signals):
    """The smallest number of attachments the body's own evidence forces.

    Deliberately conservative. Citation SITES are not distinct files - the same
    document cited in three turns yields three sites - so they establish a floor of
    one file-backed source, never a count. Overstating here would manufacture
    contradictions, which is the mirror image of the defect being fixed and just as
    dishonest. `mentioned_paths` is reported but contributes nothing, for the reason
    recorded at its definition.
    """
    if not signals:
        return 0
    floor = 0
    if signals.get("filecite_sites") or signals.get("upload_phrases"):
        floor = 1
    named = len(signals.get("named_upload_identities") or ())
    return max(floor, named)


def _covered(identity, declared_identities):
    """Is an observed (name, stamp) upload present in the declared surface?

    Matched on the stamp as well as the name, because the same filename uploaded
    twice is two attachments. A declared entry that names the file but not the
    occasion does not cover a second occasion of it.
    """
    name, stamp = identity
    for d in declared_identities or ():
        dn = str((d or {}).get("original_filename") or "").strip().lower()
        ds = str((d or {}).get("uploaded_at") or "").strip()
        if dn == name.strip().lower() and (not stamp or stamp in ds or ds in stamp):
            return True
    return False


def reconcile(declared, signals, declared_identities=()):
    """AGREE / DISAGREE / UNKNOWN over one source revision.

    Three genuinely different answers, and the third is never rounded toward the
    first. The order matters: an IDENTITY the body evidences and the declaration does
    not contain outranks any arithmetic, because that is the shape AMR-004 took and
    counting alone could not see it.
    """
    floor = observed_lower_bound(signals)
    observed_ids = list((signals or {}).get("named_upload_identities") or ())
    uncovered = [i for i in observed_ids if not _covered(i, declared_identities)]

    if declared is None:
        # The header never spoke about attachments. Silence is not a claim, so it
        # cannot be CONTRADICTED - but it also cannot be trusted as "none" when the
        # body evidences files. That is exactly the undecidable case UNKNOWN is for.
        return ("UNKNOWN", floor) if (floor > 0 or uncovered) else ("UNKNOWN", floor)
    if uncovered:
        # A positive declaration contradicted by an upload identity it omits.
        return "DISAGREE", max(floor, declared + len(uncovered))
    if declared < floor:
        return "DISAGREE", floor
    if declared == 0 and floor == 0:
        return "AGREE", floor
    if declared > 0 and floor == 0:
        # Declared attachments leaving no trace in the body at all. Not provably
        # wrong - a silent image needs no citation - but not corroborated either.
        return "UNKNOWN", floor
    return "AGREE", floor
    if declared > 0 and floor == 0:
        # Declared attachments that leave no trace in the body at all. Not provably
        # wrong - a silent image needs no citation - but not corroborated either.
        return "UNKNOWN", floor
    return "AGREE", floor


# ---------------------------------------------------------------- manifest --

def manifest_path(source_dir, revision):
    return source_dir / ("attachments-r%d.json" % int(revision))


def load_manifest(path):
    try:
        return json.loads(io.open(path, encoding="utf-8").read()), None
    except Exception as exc:                                   # noqa: BLE001
        return None, str(exc)


def validate_manifest(data, source_id, revision, slug, corpus=None):
    """Structural findings over one attachment manifest. Never semantic.

    A static validator cannot prove that an attachment MEANS what an item claims. It
    can prove the surface is internally consistent, that bytes claimed present are
    present and hash correctly, and that nothing asserts completeness it has not
    earned. That is the whole remit, and the report says so rather than implying more.
    """
    findings = []

    def fail(code, detail):
        findings.append(Finding(slug, code, detail))

    if not isinstance(data, dict):
        fail("ATTACHMENT_MANIFEST_UNREADABLE", "manifest is not an object")
        return findings
    if data.get("attachment_manifest_version") != ATTACHMENT_MANIFEST_VERSION:
        fail("ATTACHMENT_MANIFEST_VERSION_INVALID",
             "attachment_manifest_version=%r, expected %d"
             % (data.get("attachment_manifest_version"),
                ATTACHMENT_MANIFEST_VERSION))
    if str(data.get("source_id", "")).strip() != source_id:
        fail("ATTACHMENT_MANIFEST_SOURCE_MISMATCH",
             "manifest source_id=%r, expected %s"
             % (data.get("source_id"), source_id))
    if int(data.get("revision", -1) or -1) != int(revision):
        fail("ATTACHMENT_MANIFEST_REVISION_MISMATCH",
             "manifest revision=%r, expected %s" % (data.get("revision"), revision))

    recon = str(data.get("reconciliation", "")).strip().upper()
    if recon not in RECONCILIATION_STATES:
        fail("ATTACHMENT_RECONCILIATION_INVALID",
             "reconciliation=%r, expected one of %s"
             % (data.get("reconciliation"), ", ".join(RECONCILIATION_STATES)))

    rows = data.get("attachments")
    if not isinstance(rows, list):
        fail("ATTACHMENT_MANIFEST_UNREADABLE", "attachments is not a list")
        return findings

    seen = set()
    for a in rows:
        if not isinstance(a, dict):
            fail("ATTACHMENT_ENTRY_INVALID", "an attachment entry is not an object")
            continue
        aid = str(a.get("attachment_id", "")).strip()
        if not ATT_ID_RE.match(aid):
            fail("ATTACHMENT_ID_INVALID",
                 "attachment_id=%r does not match ATT-<source>-NNN" % aid)
        if aid in seen:
            fail("ATTACHMENT_ID_DUPLICATE", "%s appears twice" % aid)
        seen.add(aid)

        status = str(a.get("capture_status", "")).strip().upper()
        if status not in ATTACHMENT_CAPTURE_STATES:
            fail("ATTACHMENT_CAPTURE_STATE_INVALID",
                 "%s: capture_status=%r, expected one of %s"
                 % (aid, a.get("capture_status"),
                    ", ".join(ATTACHMENT_CAPTURE_STATES)))
        material = str(a.get("materiality", "")).strip().upper()
        if material not in ATTACHMENT_MATERIALITY:
            fail("ATTACHMENT_MATERIALITY_INVALID",
                 "%s: materiality=%r, expected one of %s"
                 % (aid, a.get("materiality"), ", ".join(ATTACHMENT_MATERIALITY)))

        # Bytes claimed present must BE present. This is the check that stops a
        # capture status from being an aspiration.
        if attachment_bytes_available(status):
            digest = str(a.get("content_sha256", "")).strip().lower()
            rel = str(a.get("artifact_path", "")).strip()
            if not digest:
                fail("ATTACHMENT_BYTES_UNHASHED",
                     "%s claims %s but carries no content_sha256 — bytes in hand are "
                     "bytes that can be re-verified" % (aid, status))
            if status in ("RECOVERED_EXACT", "RECOVERED_DUPLICATE"):
                if not str(a.get("recovery_provenance", "")).strip():
                    fail("ATTACHMENT_RECOVERY_UNPROVENANCED",
                         "%s is %s with no recovery_provenance — a recovered "
                         "attachment must prove it is THE attachment bound to this "
                         "frozen revision, not merely a plausible file" % (aid, status))
            if rel and corpus is not None:
                p = corpus / rel
                if not p.is_file():
                    fail("ATTACHMENT_ARTIFACT_MISSING",
                         "%s names artifact_path %s, which does not exist" % (aid, rel))
                elif digest and sha256_file(p) != digest:
                    fail("ATTACHMENT_ARTIFACT_MUTATED",
                         "%s: %s no longer hashes to its recorded content_sha256"
                         % (aid, rel))
        else:
            # The mirror check. An attachment WITHOUT bytes may not carry a content
            # hash, because a hash reads as evidence and there is nothing to hash.
            if str(a.get("content_sha256", "")).strip():
                fail("ATTACHMENT_HASH_WITHOUT_BYTES",
                     "%s is %s yet carries a content_sha256 — a hash of nothing is a "
                     "claim of possession" % (aid, status))
        if status == "DUPLICATE" and not str(a.get("duplicate_of", "")).strip():
            fail("ATTACHMENT_DUPLICATE_UNBOUND",
                 "%s is DUPLICATE but names no duplicate_of — an unbound equivalence "
                 "claim cannot be checked" % aid)

    # Completeness is DERIVED here and compared against whatever the manifest stored,
    # so a manifest can never talk its way to YES.
    derived = full_source_capture(rows, recon, data.get("declared_count"))
    stored = str(data.get("full_source_capture", "")).strip().upper()
    if stored and stored != derived:
        fail("FULL_SOURCE_CAPTURE_OVERSTATED",
             "manifest records full_source_capture=%s, but the attachments and the "
             "%s reconciliation derive %s" % (stored, recon or "missing", derived))
    return findings


def summarise(data):
    rows = [a for a in (data.get("attachments") or []) if isinstance(a, dict)]
    by = {}
    for a in rows:
        k = str(a.get("capture_status", "")).strip().upper() or "?"
        by[k] = by.get(k, 0) + 1
    recon = str(data.get("reconciliation", "UNKNOWN")).strip().upper()
    return {
        "count": len(rows),
        "by_capture_status": by,
        "with_bytes": sum(1 for a in rows
                          if attachment_bytes_available(a.get("capture_status"))),
        "material_without_bytes": sum(
            1 for a in rows
            if str(a.get("materiality", "")).strip().upper() == "MATERIAL"
            and not attachment_bytes_available(a.get("capture_status"))),
        "reconciliation": recon,
        "full_source_capture": full_source_capture(
            rows, recon, data.get("declared_count")),
    }
