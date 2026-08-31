#!/usr/bin/env python3
"""v3.1 transport suite — bounded, digest-verified capture transport.

Every scenario here answers to something the Improvements proving run actually did:

  T1–T3   a conversation far larger than the tool-output ceiling survives transport
          in bounded chunks, byte-exact, with its hash intact.
  T4–T5   an unbounded tool-output chunk — the shape that spilled — is refused, and
          the file/clipboard relay that never touches tool output is not.
  T6–T7   a transfer that dies midway reports an honest incomplete state that names
          exactly what to re-fetch, and resumes to a correct result.
  T8–T9   equal length is not identity: the stale-clipboard payload a missed click
          leaves behind is caught by the digest and stated plainly when absent.
  T10–T13 the trust boundary, written the honest way round: the invariants Intake
          can actually enforce over its OWN instructions and fixtures, and no claim
          about the sandbox, which belongs to the runtime.

Nothing here reads or writes any real user file. Every path is a temp directory.

Usage (from the skill root):
  python3 evals/test_transport_v31.py
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RV = ROOT / "scripts" / "reassemble_verify.py"
CHUNK_MAX = 32768

RESULTS = []

# A suite that exits 0 having run nothing reports success it did not earn.
MIN_CHECKS = 18


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS " if condition else "FAIL ", name,
                        ("\n        — %s" % detail) if (detail and not condition) else ""))


def esc(s):
    """extract.js escapes to ASCII so a slice can never split a character."""
    return "".join(c if 0x20 <= ord(c) <= 0x7e else "\\u%04x" % ord(c) for c in s)


def export_payload(messages):
    return esc(json.dumps(messages))


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slices(payload, chunk):
    return ["S%d|%s#END#" % (i, payload[o:o + chunk])
            for i, o in enumerate(range(0, len(payload), chunk))]


def verify(tmp, parts, expected_len, transport=None, digest=None, name="slices.txt"):
    f = Path(tmp) / name
    f.write_text("".join(parts), encoding="utf-8")
    out = Path(tmp) / (name + ".json")
    cmd = [sys.executable, str(RV), str(f), str(expected_len), str(out)]
    if transport:
        cmd += ["--transport", transport]
    if digest:
        cmd += ["--sha256", digest]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr), out


# A conversation comfortably past the ~32 KB tool-output ceiling: 3 messages, ~120 KB.
BIG = [
    {"role": "user", "text": "Vi behöver Evolution Radar.\n" + ("detalj rad\n" * 3000)},
    {"role": "assistant", "text": "```python\n" + ("x = 1\n" * 3000) + "```"},
    {"role": "user", "text": "Bra — kör på det. " + ("ännu mer text " * 2000)},
]


# ============================================ T1–T3 large source, bounded ===

def t_large_bounded(tmp):
    payload = export_payload(BIG)
    digest = sha(payload)
    check("T1a the synthetic conversation really is past the tool-output ceiling",
          len(payload) > CHUNK_MAX * 2, "%d chars" % len(payload))

    parts = slices(payload, 24000)
    rc, out, dest = verify(tmp, parts, len(payload), "tool-output", digest)
    check("T2a a >32 KB conversation transports in bounded 24k chunks and verifies",
          rc == 0 and "OK: 3 messages" in out, out.strip()[:600])
    check("T2b it took several chunks — this is the bounded path, not one big one",
          len(parts) >= 4, "%d chunks" % len(parts))

    got = json.loads(dest.read_text(encoding="utf-8"))
    check("T3a every message survives, none truncated",
          len(got) == 3 and all(m["text"] for m in got),
          str([len(m["text"]) for m in got]))
    check("T3b the code fence is still balanced after chunked transport",
          got[1]["text"].count("```") == 2)
    check("T3c byte length is exact after bounded transport",
          re.search(r"BYTES=%d\b" % len(payload), out) is not None, out.strip()[-300:])
    check("T3d and the hash is exact — the bytes are the extracted bytes",
          re.search(r"SHA256=%s\b" % digest, out) is not None, out.strip()[-300:])
    # The reassembled JSON must round-trip to the same messages that went in.
    # The verifier strips U+2060 and trims each message by contract, so compare
    # against that same normalization — anything else would be testing the fixture.
    want = [m["text"].replace("\u2060", "").strip() for m in BIG]
    check("T3e no source bytes were lost or rewritten in transit",
          [m["text"] for m in got] == want,
          str([(len(a), len(b)) for a, b in zip([m["text"] for m in got], want)]))


# ============================================== T4–T5 the bound is real ====

def t_bound(tmp):
    payload = export_payload(BIG)
    digest = sha(payload)

    rc, out, _ = verify(tmp, ["S0|" + payload + "#END#"], len(payload),
                        "tool-output", digest, name="one-big.txt")
    check("T4a one unbounded chunk through tool output is REFUSED, not truncated",
          rc != 0 and "TRANSPORT_CHUNK_OVERSIZE" in out, out.strip()[:600])
    check("T4b the refusal names the bound and the honest remedy",
          str(CHUNK_MAX) in out and "--transport file" in out
          and "spill" in out.lower(), out.strip()[:600])
    check("T4c and it explicitly refuses the thing the proving run did next",
          "Never read a spill back out of the runtime" in out, out.strip()[:600])

    # The clipboard/artifact relay never passes through tool output, so it is not
    # bounded by it — and says which path it took.
    rc, out, _ = verify(tmp, ["S0|" + payload + "#END#"], len(payload),
                        "file", digest, name="relay.txt")
    check("T5a the file/clipboard relay carries the same payload in one hop",
          rc == 0 and "TRANSPORT=file" in out, out.strip()[:600])

    # Default = the conservative answer: an undeclared transport is treated as the
    # risky one, so forgetting the flag cannot silently unbound the transfer.
    rc, out, _ = verify(tmp, ["S0|" + payload + "#END#"], len(payload),
                        None, digest, name="undeclared.txt")
    check("T5b an UNDECLARED transport defaults to bounded, never to unbounded",
          rc != 0 and "TRANSPORT_CHUNK_OVERSIZE" in out, out.strip()[:400])


# ======================================= T6–T7 honest failure, resumable ===

def t_resumable(tmp):
    payload = export_payload(BIG)
    digest = sha(payload)
    parts = slices(payload, 24000)
    lost = 2
    partial = [s for i, s in enumerate(parts) if i != lost]

    rc, out, dest = verify(tmp, partial, len(payload), "tool-output", digest,
                           name="partial.txt")
    check("T6a a transfer that dies midway fails closed — no short archive is built",
          rc != 0 and not dest.exists(), out.strip()[:600])
    check("T6b the incomplete state is stated, not inferred",
          "TRANSPORT_INCOMPLETE" in out, out.strip()[:600])
    check("T6c and it is RESUMABLE: it names exactly which slice to re-fetch",
          re.search(r"missing slice indexes: \[%d\]" % lost, out) is not None,
          out.strip()[:600])

    rc, out, dest = verify(tmp, partial + [parts[lost]], len(payload),
                           "tool-output", digest, name="resumed.txt")
    check("T7 re-fetching only the named slice completes the capture, byte-exact",
          rc == 0 and re.search(r"SHA256=%s\b" % digest, out) is not None,
          out.strip()[:600])


# ================================= T8–T9 length is not identity (FINDING D) ==

def t_digest(tmp):
    real = export_payload([{"role": "user", "text": "Bygg Evolution Radar nu."},
                           {"role": "assistant", "text": "Beslutat: radarn laser."}])
    # The conversation the clipboard still held when the trusted click did not land,
    # padded to exactly the same length as the one that should have arrived.
    other = [{"role": "user", "text": "Bygg K."},
             {"role": "assistant", "text": "Beslutat: grinden staller krav."}]
    stale = export_payload(other)
    assert len(stale) <= len(real), "pad the shorter payload, never the longer"
    other[1]["text"] += "!" * (len(real) - len(stale))
    stale = export_payload(other)
    check("T8a the reproducer is honest: same length, different conversation",
          len(stale) == len(real) and stale != real,
          "%d vs %d" % (len(stale), len(real)))

    rc, out, _ = verify(tmp, ["S0|" + stale + "#END#"], len(real), "file",
                        sha(real), name="stale.txt")
    check("T8b a stale clipboard from an undelivered click is caught by the digest",
          rc != 0 and "TRANSPORT_DIGEST_MISMATCH" in out, out.strip()[:600])

    rc, out, _ = verify(tmp, ["S0|" + stale + "#END#"], len(real), "file",
                        None, name="stale-nodigest.txt")
    check("T9 without a digest the run says so out loud instead of passing quietly",
          rc == 0 and "TRANSPORT_DIGEST_UNVERIFIED" in out, out.strip()[:600])


# =========================== T10–T13 the trust boundary, stated honestly ====

def t_boundary(tmp):
    """Intake does not own the sandbox. It owns its own instructions and fixtures,
    and those are what these checks hold — no security claim it cannot cash."""
    # T10: Intake's own instructions must not send anyone into the runtime's storage.
    offenders = []
    for path in sorted(list((ROOT / "scripts").glob("*.py"))
                       + list((ROOT / "scripts").glob("*.js"))
                       + list((ROOT / "references").glob("*.md"))
                       + [ROOT / "SKILL.md", ROOT / "README.md"]):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"\.claude/(?:projects|sessions|history)", text):
            # A sentence that FORBIDS the path is the opposite of an offender, and
            # that sentence routinely wraps — so judge the surrounding window, not
            # the one line the match happened to land on.
            window = text[max(0, m.start() - 400):m.end() + 200]
            if re.search(r"[Nn]ever|not require|no private|must not|forbid", window):
                continue
            offenders.append("%s: %s"
                             % (path.name, text[max(0, m.start() - 40):m.end() + 40].strip()[:90]))
    check("T10 no Intake script or instruction sends anyone into the runtime's own "
          "session storage", not offenders, "; ".join(offenders))

    # T11: the one sandbox exception Intake authors must carry a negative scope.
    playbook = (ROOT / "references" / "extraction.md").read_text(encoding="utf-8")
    bypass = [ln for ln in playbook.splitlines()
              if re.search(r"sandbox-disabled|dangerouslyDisableSandbox", ln)]
    check("T11a Intake authors exactly one sandbox exception, no more",
          len(bypass) == 1, "%d: %s" % (len(bypass), bypass))
    check("T11b and it is scoped — it says what must NEVER be done sandbox-disabled",
          "SCOPE OF THAT EXCEPTION" in playbook
          and re.search(r"Never\s+disable the sandbox to read", playbook) is not None)
    check("T11c the boundary is described honestly: Intake states it, the runtime "
          "owns it — no enforcement is claimed that Intake cannot deliver",
          "Intake cannot enforce this" in playbook)

    # T12: this suite's own hygiene — everything it touched is under a temp dir.
    check("T12 every path this suite wrote is inside its temp directory",
          str(tmp).startswith(tempfile.gettempdir()), str(tmp))

    # T13: and no eval in the repo reads or writes the runtime's real storage.
    real_hits = []
    for path in sorted((ROOT / "evals").glob("*.py")):
        if path.name == Path(__file__).name:
            continue                      # this file is the auditor, not a subject
        for m in re.finditer(r"[^\n]*(?:Path\.home\(\)|~|\$HOME)[^\n]*\.claude/"
                             r"(?:projects|sessions|history)[^\n]*",
                             path.read_text(encoding="utf-8")):
            real_hits.append("%s: %s" % (path.name, m.group(0).strip()[:80]))
    check("T13 no eval opens the real ~/.claude/projects — fixtures use temp dirs",
          not real_hits, "; ".join(real_hits))


# ------------------------------------------------------------------ runner --

def main():
    for scenario in (t_large_bounded, t_bound, t_resumable, t_digest, t_boundary):
        tmp = tempfile.mkdtemp(prefix="intake-transport-")
        try:
            print("\n=== %s ===" % scenario.__name__)
            scenario(tmp)
        except Exception as exc:
            # A scenario that raises has proved nothing, so it records a failure
            # instead of killing the run — otherwise the mutation guard's signal is
            # a stack trace and every later check silently never happens.
            check("%s (scenario raised)" % scenario.__name__, False,
                  "%s: %s" % (type(exc).__name__, exc))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [(n, d) for n, ok, d in RESULTS if not ok]
    print("\n%d/%d checks passed" % (len(RESULTS) - len(failed), len(RESULTS)))
    for n, d in failed:
        print("FAILED: %s\n        %s" % (n, d))
    if len(RESULTS) < MIN_CHECKS:
        print("FAIL: only %d checks executed (floor %d) — a suite that runs nothing "
              "proves nothing" % (len(RESULTS), MIN_CHECKS))
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
