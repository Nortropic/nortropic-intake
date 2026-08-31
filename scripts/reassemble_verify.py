#!/usr/bin/env python3
"""Step 4 — Reassemble transported slices and run the fail-closed verification.

Usage:
  python3 reassemble_verify.py <slices_file> <expected_len> <out_messages.json>
                               [--transport file|tool-output] [--sha256 <digest>]

<slices_file>: a text file containing ALL slice outputs pasted in any order —
each slice must look like  S<i>|<payload>#END#  (junk between slices is fine).
<expected_len>: the `len` reported by extract.js.
--sha256:      the `sha256` reported by extract.js, of the same bytes. Length is a
               weak oracle; this is the strong one, and it is REQUIRED. extract.js
               always reports it, so its absence means the payload did not come from
               there — say that deliberately with --digest-unavailable rather than by
               leaving the flag off.
--transport:   how the bytes reached this file. Defaults to the conservative answer.

Two things the Improvements proving run taught this script:

1. TOOL-OUTPUT TRANSPORT IS BOUNDED. A capture agent logged ~40 KB chunks, the tool
   output limit is around 32 KB, and the overflow spilled to a file the agent then
   went looking for outside its sandbox. The bound is now checked here rather than
   left to a number in a playbook: under `--transport tool-output` a FRAMED chunk
   (`S<i>|` + payload + `#END#`, which is what the tool actually carries) above
   TOOL_OUTPUT_CHUNK_MAX is a hard failure. The clipboard/file relay does not pass
   through tool output at all and declares `--transport file`, which is unbounded.
   The default is `tool-output` on purpose — the risky path must be the one you get
   without thinking about it.

   Be exact about the limit of that check: it fires on an oversized chunk that
   ARRIVED INTACT. A chunk that genuinely spilled never reaches this script as a
   chunk at all — it shows up as a missing slice index, which is the other failure
   below. The bound is what stops the playbook from prescribing a size that spills;
   it is not a detector for a spill that already happened.

2. LENGTH DOES NOT IDENTIFY BYTES. The clipboard relay needs a trusted click to arm
   its copy handler. When that click does not land, `pbpaste` returns whatever the
   clipboard held before — the PREVIOUS conversation. A stale export of the same
   length passes every check this script used to run, and the wrong conversation is
   delivered as a verified capture. `--sha256` closes that; nothing else here can.

Checks: chunk bound (per transport), every index present exactly once, exact total
length, exact digest when given, JSON parses, U+2060 stripped (restores neutralized
words), no empty messages, balanced code fences per message. Exits non-zero on any
failure — do NOT build the markdown from unverified data.
"""
import argparse, hashlib, json, re, sys

# Measured, not guessed: the observed tool-output ceiling is ~32 KB, and the run that
# exceeded it spilled. Chunks are cut at 24 KB in the playbook to leave room for the
# S<i>| prefix, the #END# marker and the tool's own framing.
TOOL_OUTPUT_CHUNK_MAX = 32768


def fail(message):
    print("FAIL: %s" % message)
    raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(add_help=True,
                                 description=__doc__.splitlines()[0])
    ap.add_argument("slices")
    ap.add_argument("expected_len", type=int)
    ap.add_argument("out")
    ap.add_argument("--transport", choices=["file", "tool-output"],
                    default="tool-output",
                    help="file = clipboard/artifact relay, never through tool output "
                         "(unbounded); tool-output = console/javascript_tool payloads "
                         "(bounded at %d chars per chunk). Default: tool-output."
                         % TOOL_OUTPUT_CHUNK_MAX)
    ap.add_argument("--sha256", dest="digest",
                    help="expected sha256 of the reassembled payload, from extract.js")
    ap.add_argument("--digest-unavailable", action="store_true",
                    help="proceed with LENGTH ONLY — a deliberate, recorded downgrade "
                         "for a payload that did not come from extract.js")
    args = ap.parse_args()
    if not args.digest and not args.digest_unavailable:
        # The stale-clipboard defect is only closed if the strong oracle is actually
        # used. Leaving the flag off used to be an omission nobody noticed; now it is
        # a choice that has to be made out loud.
        fail("no --sha256 given. Length alone cannot tell two conversations apart, "
             "and a trusted click that never landed leaves the PREVIOUS export on the "
             "clipboard at whatever length it happens to be. Pass the digest "
             "extract.js reported, or say --digest-unavailable on purpose.")

    raw = open(args.slices, encoding="utf-8").read()
    expected = args.expected_len

    found = re.findall(r"S(\d+)\|(.*?)#END#", raw, re.S)
    idx = {}
    for i, p in found:
        idx[int(i)] = p  # later re-fetches of a slice override earlier ones

    if not idx:
        fail("no S<i>|...#END# slices found")

    if args.transport == "tool-output":
        # Measure what the tool actually carried: the framed chunk, not the payload
        # inside it. A payload exactly at the bound still spills once framed.
        framed = lambda k, v: len("S%d|" % k) + len(v) + len("#END#")
        oversize = sorted((k, framed(k, v)) for k, v in idx.items()
                          if framed(k, v) > TOOL_OUTPUT_CHUNK_MAX)
        if oversize:
            print("TRANSPORT_CHUNK_OVERSIZE — %d framed chunk(s) exceed the %d-char "
                  "tool-output bound: %s"
                  % (len(oversize), TOOL_OUTPUT_CHUNK_MAX,
                     ", ".join("S%d=%d" % kv for kv in oversize[:5])))
            fail("a chunk this size does not survive tool output intact; it spills. "
                 "Re-cut the transfer smaller, or move the bytes by file/clipboard "
                 "relay and declare --transport file. Never read a spill back out of "
                 "the runtime's own storage.")

    missing = [k for k in range(max(idx) + 1) if k not in idx]
    if missing:
        # An honest incomplete state, and a resumable one: it names exactly what to
        # re-fetch rather than delivering a short archive that parses.
        print("TRANSPORT_INCOMPLETE — %d slice(s) never arrived" % len(missing))
        fail("missing slice indexes: %s — re-fetch exactly these and re-run; the "
             "arrived slices are still valid" % missing)

    s = "".join(idx[k] for k in sorted(idx))
    if len(s) != expected:
        fail("reassembled length %d != expected %d" % (len(s), expected))

    actual = hashlib.sha256(s.encode("utf-8")).hexdigest()
    if args.digest:
        if actual.lower() != args.digest.strip().lower():
            print("TRANSPORT_DIGEST_MISMATCH — these are not the bytes that were "
                  "extracted (same length, different content: a stale clipboard from "
                  "an undelivered click looks exactly like this)")
            fail("sha256 %s != expected %s" % (actual, args.digest.strip().lower()))
    else:
        print("TRANSPORT_DIGEST_UNVERIFIED — --digest-unavailable was passed, so only "
              "the LENGTH of this payload was checked. Two different conversations of "
              "equal length are indistinguishable here. Record this downgrade wherever "
              "the capture is reported; do not let it read as a verified transfer.")

    data = json.loads(s)
    for m in data:
        m["text"] = m["text"].replace("⁠", "").strip()
    if any(not m["text"] for m in data):
        fail("empty message text after reassembly")
    for i, m in enumerate(data):
        fences = sum(1 for l in m["text"].split("\n") if l.startswith("```"))
        if fences % 2:
            fail("message %d: unbalanced code fences (%d)" % (i, fences))

    json.dump(data, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    total = sum(len(m["text"]) for m in data)
    roles = ",".join(m["role"] for m in data)
    print("OK: %d messages (%s), %d chars -> %s" % (len(data), roles, total, args.out))
    print("TRANSPORT=%s  SLICES=%d  BYTES=%d  SHA256=%s"
          % (args.transport, len(idx), len(s), actual))


if __name__ == "__main__":
    main()
