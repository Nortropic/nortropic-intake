#!/usr/bin/env python3
"""Shared primitives for the Nortropic Intake contracts.

`plan_contract.py` (HOW: candidate → approval → plan → resume) and
`context_contract.py` (WHERE/DELTAS: manifest → clarifications → coverage → trace)
both build on this module. It holds exactly what both need and nothing else: a
flat-frontmatter reader that refuses ambiguity, content hashing, the stable-ID
parser, fenced-code awareness, git evidence helpers and the Finding type.

Design rules this module exists to enforce:
  * Plain files, stable IDs, hashes. No database, no index, no daemon.
  * Fail closed on anything undecidable — never guess between two readings.
  * Nothing here reads a private conversation/session path, ever.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_CORPUS = Path.home() / "nortropic" / "innovation-intake"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def corpus_root(explicit=None):
    if explicit:
        return Path(explicit)
    return Path(os.environ.get("NORTROPIC_INTAKE_CORPUS", str(DEFAULT_CORPUS)))


# ---------------------------------------------------------------- findings --

class Finding(object):
    """One contract violation. `level` is FAIL (blocks) or WARN (legacy/deferred)."""

    def __init__(self, slug, code, detail, level="FAIL"):
        self.slug = slug
        self.code = code
        self.detail = detail
        self.level = level

    def __str__(self):
        return "%-4s  [%s]  %s — %s" % (self.level, self.slug, self.code, self.detail)


def fails(findings):
    return [f for f in findings if f.level == "FAIL"]


def warns(findings):
    return [f for f in findings if f.level == "WARN"]


# ---------------------------------------------------------------- parsing --

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)
# YAML starts a comment at ` #` — one space is enough. Matching that exactly is what
# keeps this reader from disagreeing with a YAML-aware one. A value that must contain
# a `#` goes in quotes, where nothing is stripped.
_TRAILING_COMMENT_RE = re.compile(r"\s+#.*$")


def read_frontmatter(path):
    """Flat `key: value` frontmatter reader. Returns (fields, body, errors).

    Deliberately not a YAML parser — intake frontmatter is flat by contract. Anything
    a YAML reader would interpret differently (nested keys, duplicate keys, a value
    that runs onto the next line) is reported as an error rather than guessed at, so
    the gate can never disagree with what a human reading the file sees.
    """
    raw = Path(path).read_text(encoding="utf-8")
    raw = raw.lstrip("﻿")  # a BOM would otherwise defeat the leading `---` match
    m = _FM_RE.match(raw)
    if not m:
        return {}, raw, []
    fm, errors = {}, []
    for offset, line in enumerate(m.group(1).splitlines()):
        lineno = offset + 2
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace():
            errors.append("line %d: indented/nested frontmatter is not allowed — "
                          "intake frontmatter is flat `key: value`: %r"
                          % (lineno, line.strip()))
            continue
        if ":" not in line:
            errors.append("line %d: value ran onto its own line, or not a `key: value` "
                          "line — keep every value on one line: %r"
                          % (lineno, line.strip()))
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        quote = value[0] if value and value[0] in "\"'" else None
        if quote is None:
            value = _TRAILING_COMMENT_RE.sub("", value).strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                value = [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]
        else:
            if len(value) < 2 or value[-1] != quote:
                errors.append("line %d: unterminated quoted value for %r — keep every "
                              "frontmatter value on one line" % (lineno, key))
                continue
            value = value[1:-1]
        if key in fm:
            errors.append("line %d: duplicate key %r — which one is authoritative is "
                          "not decidable" % (lineno, key))
        fm[key] = value
    return fm, raw[m.end():], errors


def fm_str(fm, key):
    value = fm.get(key)
    return value.strip() if isinstance(value, str) else ("" if value is None else value)


def fm_list(fm, key):
    value = fm.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    value = str(value).strip()
    return [value] if value else []


# ---------------------------------------------------------------- hashing --

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def body_sha256(path):
    """Content identity: the hash of everything AFTER the frontmatter block.

    This is what makes exact owner approval possible. A plan candidate and the
    approved plan promoted from it carry different frontmatter by design (approval
    date, approver, status) but must carry byte-identical bodies. Hashing the body
    alone lets the promotion be proved rather than trusted.
    """
    _, body, _ = read_frontmatter(path)
    return sha256_text(body)


# ------------------------------------------------------- markdown structure --

def fence_spans(text):
    """(start, end) spans of fenced code blocks — ``` and ~~~, any info string."""
    spans = []
    open_at, marker = None, None
    for m in re.finditer(r"^[ \t]*(`{3,}|~{3,})[^\n]*$", text, re.M):
        token = m.group(1)[0] * 3
        if open_at is None:
            open_at, marker = m.start(), token
        elif token == marker:
            spans.append((open_at, m.end()))
            open_at, marker = None, None
    if open_at is not None:            # unclosed fence swallows the rest
        spans.append((open_at, len(text)))
    return spans


def outside_fences(text, matches):
    spans = fence_spans(text)
    return [m for m in matches if not any(a <= m.start() < b for a, b in spans)]


def section_bodies(body):
    """number -> (heading text, section content) for every `## N. …` heading.

    Headings inside a fenced code block do not count: a document that quotes a
    template in a ```markdown block has not written those sections, it has pasted
    them. Fenced content INSIDE a real section still counts as that section's
    content — commands and snippets are legitimate material.
    """
    out = {}
    heads = outside_fences(body, list(re.finditer(r"^##\s*(\d+)\.\s*([^\n]*)$", body, re.M)))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        out[int(h.group(1))] = (h.group(2).strip(), body[h.end():end])
    return out


# -------------------------------------------------------------- stable IDs --

# `- D4. text — because … (← msg 44–47)` / `AC3. WHEN … SHALL …` / `R2. …` / `Q1. …`
ID_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?P<id>(?:D|R|Q|AC)\d+)\.\s+(?P<text>.+?)\s*$", re.M)
# `### S4 — Persist the manifest` in an approved plan's execution order
SLICE_RE = re.compile(r"^\s*#{2,4}\s*(?P<id>S\d+)\s*[—:.-]\s*(?P<text>.+?)\s*$", re.M)
PROVENANCE_RE = re.compile(r"\(←\s*([^)]+)\)")
CLAR_RE = re.compile(r"^##\s*(CLAR-\d+)\s*$", re.M)
REF_RE = re.compile(r"\b(D\d+|R\d+|Q\d+|AC\d+|S\d+|SRC-\d+|CLAR-\d+)\b")

ID_KINDS = {"D": "decision", "R": "rejection", "Q": "open-question",
            "AC": "acceptance-criterion", "S": "plan-slice",
            "SRC": "source", "CLAR": "owner-clarification"}


def id_kind(identifier):
    m = re.match(r"^(SRC|CLAR|AC|D|R|Q|S)", identifier)
    return ID_KINDS.get(m.group(1)) if m else None


def parse_ids(text):
    """Every D/R/Q/AC entry in a document body -> {id: {text, provenance, line}}.

    Multi-line entries are joined: an entry runs until the next ID line or a blank
    line followed by a non-indented line, which is how the brief template already
    wraps them.
    """
    out = {}
    matches = outside_fences(text, list(ID_LINE_RE.finditer(text)))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[m.start():end]
        # stop at the next heading so a trailing section is not absorbed
        heading = re.search(r"^#{1,6}\s", chunk[1:], re.M)
        if heading:
            chunk = chunk[:heading.start() + 1]
        body = re.sub(r"\s+", " ", chunk).strip()
        out[m.group("id")] = {
            "id": m.group("id"),
            "text": body,
            "provenance": PROVENANCE_RE.findall(chunk),
            "line": text[:m.start()].count("\n") + 1,
        }
    return out


def parse_slices(text):
    """`### S<n> — heading` entries in an approved plan / candidate body.

    A slice ends at the next slice OR the next `## ` section, whichever comes first —
    otherwise the last slice in §3 would swallow §4–§11 and appear to cover every
    decision and rejection in the document.
    """
    out = {}
    matches = outside_fences(text, list(SLICE_RE.finditer(text)))
    section_starts = [m.start() for m in
                      outside_fences(text, list(re.finditer(r"^##\s[^\n]*$", text, re.M)))]
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        following = [s for s in section_starts if s > m.start()]
        if following:
            end = min(end, following[0])
        chunk = text[m.start():end]
        out[m.group("id")] = {
            "id": m.group("id"),
            "heading": m.group("text").strip(),
            "line": text[:m.start()].count("\n") + 1,
            "end_line": text[:end].count("\n") + 1,
            "refs": sorted(set(REF_RE.findall(chunk)) - {m.group("id")}),
            "owner_only": bool(re.search(r"owner-only|owner only|ägaren", chunk, re.I)),
            "text": chunk,
        }
    return out


# ------------------------------------------------------------ git evidence --

def git(repo, *args, **kw):
    try:
        out = subprocess.run(["git", "-C", str(repo)] + list(args),
                             capture_output=True, text=True, timeout=kw.get("timeout", 20))
    except Exception:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_evidence(repo):
    head = git(repo, "rev-parse", "HEAD")
    if head is None:
        return None
    return {
        "repo": str(Path(repo).resolve()),
        "head": head,
        "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "?",
        "dirty": "YES" if git(repo, "status", "--porcelain") else "NO",
        "remote": git(repo, "remote", "get-url", "origin") or "none",
    }


def git_commit_exists(repo, commit):
    return git(repo, "cat-file", "-e", "%s^{commit}" % commit) is not None


def git_head_blob(repo, relpath):
    """The committed version of a file, or None if untracked/absent."""
    return git(repo, "show", "HEAD:%s" % relpath)


def git_immutability(repo, relpath, path):
    """Anchor a file's bytes against git history — the only witness an agent cannot edit.

    Returns one of:
      ("UNTRACKED", None)  no committed version exists yet (nothing to violate)
      ("UNCHANGED", None)  the file is byte-identical to its committed version
      ("MUTATED", detail)  it differs from what was committed

    Every hash the intake contract records lives in a file the writing agent controls,
    so hashes alone prove only internal consistency. Git history is outside that
    control: once an approval is committed, changing it is detectable.
    """
    committed = git_head_blob(repo, relpath)
    if committed is None:
        return "UNTRACKED", None
    try:
        current = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return "MUTATED", "cannot read %s: %s" % (relpath, exc)
    if current.rstrip("\n") == committed.rstrip("\n"):
        return "UNCHANGED", None
    return "MUTATED", ("%s differs from its committed version" % relpath)


def expand(path):
    return Path(os.path.expanduser(str(path)))


# --------------------------------------------------------- secret hygiene --

# Manifests record WHERE a source lives. They must never turn a credential into
# durable metadata, so anything that looks like one is refused rather than stored.
CREDENTIAL_PATTERNS = [
    (r"(?i)\b(access_token|api[_-]?key|auth[_-]?token|session[_-]?token|"
     r"client[_-]?secret|password|passwd|private[_-]?key)\b\s*[=:]", "credential parameter"),
    (r"(?i)[?&](token|key|sig|signature|password|auth)=", "credential in URL query"),
    (r"(?i)X-Amz-(Signature|Credential|Security-Token)", "presigned-URL credential"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key material"),
    (r"\bgh[pousr]_[A-Za-z0-9]{16,}", "GitHub token"),
    (r"\bsk-[A-Za-z0-9]{20,}", "API secret key"),
    (r"\bxox[abposr]-[A-Za-z0-9-]{10,}", "Slack token"),
]


def scan_credentials(text):
    """Return [(pattern description, matched excerpt)] — excerpt is truncated."""
    hits = []
    for pattern, label in CREDENTIAL_PATTERNS:
        for m in re.finditer(pattern, text):
            excerpt = text[max(0, m.start() - 12):m.start() + 24].replace("\n", " ")
            hits.append((label, excerpt.strip()))
    return hits


# ------------------------------------------------------------------- json --

def read_json(path):
    """Returns (data, error). Never raises on malformed input."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "file does not exist"
    except ValueError as exc:
        return None, "is not valid JSON: %s" % exc
    except OSError as exc:
        return None, "cannot be read: %s" % exc


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")


# ------------------------------------------------------------- reporting ---

def report(findings, label, quiet_pass=None):
    """Print findings; return the exit code (1 if any FAIL)."""
    for f in findings:
        print(f)
    hard = fails(findings)
    soft = warns(findings)
    if not findings and quiet_pass:
        print(quiet_pass)
    print("\n%s: %d FAIL, %d WARN" % (label, len(hard), len(soft)))
    return 1 if hard else 0


def die(message):
    sys.exit("FAIL: %s" % message)
