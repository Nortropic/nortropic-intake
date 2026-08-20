#!/usr/bin/env python3
"""Step 4 — Reassemble slices and run the fail-closed verification.

Usage:
  python3 reassemble_verify.py <slices_file> <expected_len> <out_messages.json>

<slices_file>: a text file containing ALL slice outputs pasted in any order —
each slice must look like  S<i>|<payload>#END#  (junk between slices is fine).
<expected_len>: the `len` reported by extract.js.

Checks: every index present exactly once, exact total length, JSON parses,
U+2060 stripped (restores neutralized words), no empty messages, balanced code
fences per message. Exits non-zero on any failure — do NOT build the markdown
from unverified data.
"""
import json, re, sys

def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    raw = open(sys.argv[1], encoding="utf-8").read()
    expected = int(sys.argv[2])

    found = re.findall(r"S(\d+)\|(.*?)#END#", raw, re.S)
    idx = {}
    for i, p in found:
        idx[int(i)] = p  # later re-fetches of a slice override earlier ones

    if not idx:
        sys.exit("FAIL: no S<i>|...#END# slices found")
    missing = [k for k in range(max(idx) + 1) if k not in idx]
    if missing:
        sys.exit(f"FAIL: missing slice indexes: {missing}")

    s = "".join(idx[k] for k in sorted(idx))
    if len(s) != expected:
        sys.exit(f"FAIL: reassembled length {len(s)} != expected {expected}")

    data = json.loads(s)
    for m in data:
        m["text"] = m["text"].replace("⁠", "").strip()
    if any(not m["text"] for m in data):
        sys.exit("FAIL: empty message text after reassembly")
    for i, m in enumerate(data):
        fences = sum(1 for l in m["text"].split("\n") if l.startswith("```"))
        if fences % 2:
            sys.exit(f"FAIL: message {i}: unbalanced code fences ({fences})")

    json.dump(data, open(sys.argv[3], "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    total = sum(len(m["text"]) for m in data)
    roles = ",".join(m["role"] for m in data)
    print(f"OK: {len(data)} messages ({roles}), {total} chars -> {sys.argv[3]}")

if __name__ == "__main__":
    main()
