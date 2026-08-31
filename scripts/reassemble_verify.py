#!/usr/bin/env python3
"""Step 4 — Reassemble transported slices and run the fail-closed verification.

Usage:
  python3 reassemble_verify.py <slices_file> <expected_len> <out_messages.json>
                               [--transport file|tool-output]
                               (--sha256 <digest> | --digest-unavailable)

<slices_file>: a text file containing ALL slice outputs pasted in any order —
each slice must look like  S<i>|<payload>#END#  (junk between slices is fine).
<expected_len>: the `len` reported by extract.js.
--sha256:      the `sha256` reported by the capture script, of the same bytes. Length
               is a weak oracle; this is the strong one, and it is REQUIRED. BOTH
               capture scripts report it — data_capture.js (preferred) alongside
               `exportLen`, extract.js (DOM fallback) alongside `len` — so its absence
               means the payload did not come from either, and that has to be said
               deliberately with --digest-unavailable rather than by leaving the flag
               off.
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
   ARRIVED INTACT. A chunk that actually got cut loses its `#END#`, and the slice
   regex is non-greedy, so it swallows the FOLLOWING slice's marker and the two
   arrive merged — an index silently absent from the ledger while nothing looks
   missing. That shape is detected separately below, by counting `S<i>|` markers in
   the raw text against the slices actually parsed. The bound is what stops the
   playbook from prescribing a size that spills; the marker count is what notices
   when one did.

2. LENGTH DOES NOT IDENTIFY BYTES. The clipboard relay needs a trusted click to arm
   its copy handler. When that click does not land, `pbpaste` returns whatever the
   clipboard held before — the PREVIOUS conversation. A stale export of the same
   length passes every check this script used to run, and the wrong conversation is
   delivered as a verified capture. `--sha256` closes that; nothing else here can.

Order matters here. The DIGEST is the authority: if the reassembled bytes hash to what
the extractor reported, the transfer is correct and no framing heuristic gets a vote —
which is what keeps a conversation that happens to contain `#END#` or `S12|` in its own
text from being diagnosed as a broken transfer. Only when the length or the digest
fails, or the digest was explicitly waived, do the framing diagnostics run, and then
their whole job is to say WHAT to re-fetch: a gap in the middle, a slice truncated so
the next merged into it, or a transfer simply short at the tail — the shape a
missing-index scan cannot see, because there is no index above the highest that arrived.

Checks: chunk bound (per transport), slice framing (a literal `#END#` inside a message
is not a slice terminator), exact total length, exact digest unless waived,
duplicate indexes reported, framing diagnosis on failure, JSON parses and is a list of
{role,text}, U+2060 stripped (restores neutralized words), no empty messages, balanced
code fences per message. Exits non-zero on any failure — do NOT build the markdown from
unverified data.
"""
import argparse, hashlib, json, re, sys

# Measured, not guessed: the observed tool-output ceiling is ~32 KB, and the run that
# exceeded it spilled. Chunks are cut at 24 KB in the playbook to leave room for the
# S<i>| prefix, the #END# marker and the tool's own framing.
TOOL_OUTPUT_CHUNK_MAX = 32768


def fail(message):
    print("FAIL: %s" % message)
    raise SystemExit(1)


# `#END#` is a marker, not a reserved word: the extractors escape non-ASCII only, so a
# conversation that DISCUSSES this protocol carries the literal tokens in its text. With
# a plain non-greedy match the first such `#END#` ends the slice early and the transfer
# dies on a length mismatch — and on the preferred clipboard relay, which wraps the whole
# export as one slice, that makes such a conversation untransportable. This corpus's
# subject matter is this protocol, so that is not a hypothetical.
#
# The anchored pattern only accepts an `#END#` that is followed by the next marker or by
# the end of the file, which is what actually terminates a slice.
_SLICE_LOOSE = re.compile(r"S(\d+)\|(.*?)#END#", re.S)
_SLICE_ANCHORED = re.compile(r"S(\d+)\|(.*?)#END#(?=\s*(?:S\d+\||\Z))", re.S)


def _collect(matches):
    idx, dupes = {}, set()
    for i, payload in matches:
        if int(i) in idx:
            dupes.add(int(i))    # a re-fetch: the later copy wins, and it is reported
        idx[int(i)] = payload
    return idx, dupes


def parse_slices(raw, expected):
    """(matches, {index: payload}, duplicate-indexes) — prefer the parse that adds up.

    Both readings are tried and the one whose total length equals what the extractor
    declared wins; ties go to the anchored one. Nothing is trusted on that basis — the
    digest still decides — this only stops a legitimate `#END#` inside a message from
    being read as the end of a slice.
    """
    for pattern in (_SLICE_ANCHORED, _SLICE_LOOSE):
        matches = pattern.findall(raw)
        if not matches:
            continue
        idx, dupes = _collect(matches)
        if sum(len(v) for v in idx.values()) == expected:
            return matches, idx, dupes
    matches = _SLICE_LOOSE.findall(raw)
    idx, dupes = _collect(matches)
    return matches, idx, dupes


def diagnose(raw, idx, found, got_len, expected):
    """Say what to re-fetch. Only ever called once the transfer is already known bad.

    Three shapes, and the first two are the ones a length mismatch alone cannot tell
    apart. Nothing here decides correctness — the digest did that — so a conversation
    whose text legitimately contains `S12|` or `#END#` can at worst get an imperfect
    hint about a transfer that was broken anyway.
    """
    # Merge first: a payload that contains another slice's marker is positive evidence
    # that the slice before it was cut, and it means the ABSORBING slice is corrupt too
    # — so this must not be reported as a plain gap with "the arrived slices are still
    # valid", which would be false.
    markers = len(re.findall(r"S\d+\|", raw))
    swallowed = sorted(k for k, v in idx.items() if re.search(r"S\d+\|", v))
    if swallowed:
        print("TRANSPORT_SLICE_MERGED — %d marker(s) in the file but %d slice(s) "
              "parsed; slice(s) %s were cut mid-payload and absorbed the next one, so "
              "they are corrupt as well. Re-fetch from index %d onward; slices before "
              "that are still valid" % (markers, len(found), swallowed, min(swallowed)))
        return

    missing = [k for k in range(max(idx) + 1) if k not in idx]
    if missing:
        print("TRANSPORT_INCOMPLETE — %d slice(s) never arrived. Re-fetch exactly "
              "index(es) %s; the arrived slices are still valid"
              % (len(missing), missing))
        return

    if markers > len(found):
        print("TRANSPORT_SLICE_TRUNCATED — %d marker(s) in the file but %d slice(s) "
              "parsed, and none absorbed another: the LAST slice lost its #END#. "
              "Re-fetch from index %d onward" % (markers, len(found), max(idx) + 1))
        return

    # Short, with no gap and no merge. A missing-index scan is structurally blind here:
    # there is no index above the highest one received. Two different causes, and the
    # single-slice case is the preferred clipboard relay's own failure mode — it always
    # frames S0 itself (`printf 'S0|'; cat …; printf '#END#'`), so the frame is intact
    # even when the clipboard held a partial export. Telling that operator to re-fetch
    # slice 1 would name a slice that never existed.
    if got_len < expected:
        if len(idx) == 1:
            print("TRANSPORT_PAYLOAD_SHORT — the single slice S%d is framed correctly "
                  "but its payload is %d char(s) short. Nothing was lost in transit: "
                  "what was handed over was already partial. Re-run the capture and the "
                  "relay — on the clipboard path this is what a trusted click that "
                  "never landed, or a copy that raced the paste, looks like"
                  % (max(idx), expected - got_len))
            return
        print("TRANSPORT_TAIL_MISSING — short by %d char(s) with every index up to S%d "
              "present and framed. Either slices after S%d never arrived (re-fetch from "
              "index %d onward) or one that did was itself truncated without losing its "
              "#END#; re-fetching the tail settles which"
              % (expected - got_len, max(idx), max(idx), max(idx) + 1))
        return
    print("TRANSPORT_LENGTH_UNEXPLAINED — %d char(s) too long with no gap, no merge and "
          "no duplicate. The payload is not what the extractor reported; re-run the "
          "extraction rather than the transfer" % (got_len - expected))


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

    found, idx, dupes = parse_slices(raw, expected)

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

    if dupes:
        print("TRANSPORT_SLICE_REFETCHED — index(es) %s arrived more than once; the "
              "LAST copy of each was used" % sorted(dupes))

    s = "".join(idx[k] for k in sorted(idx))
    actual = hashlib.sha256(s.encode("utf-8")).hexdigest()

    if len(s) != expected:
        diagnose(raw, idx, found, len(s), expected)
        fail("reassembled length %d != expected %d" % (len(s), expected))

    if args.digest:
        if actual.lower() != args.digest.strip().lower():
            print("TRANSPORT_DIGEST_MISMATCH — these are not the bytes that were "
                  "extracted (same length, different content: a stale clipboard from "
                  "an undelivered click looks exactly like this)")
            diagnose(raw, idx, found, len(s), expected)
            fail("sha256 %s != expected %s" % (actual, args.digest.strip().lower()))
    else:
        print("TRANSPORT_DIGEST_UNVERIFIED — --digest-unavailable was passed, so only "
              "the LENGTH of this payload was checked. Two different conversations of "
              "equal length are indistinguishable here. Record this downgrade wherever "
              "the capture is reported; do not let it read as a verified transfer.")

    try:
        data = json.loads(s)
    except ValueError as exc:
        fail("reassembled payload is not JSON: %s" % exc)
    if not isinstance(data, list) or not all(
            isinstance(m, dict) and "text" in m and "role" in m for m in data):
        fail("reassembled payload is not a list of {role, text} messages — this is a "
             "fail-closed gate, so an unexpected shape stops here rather than being "
             "half-understood")
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
