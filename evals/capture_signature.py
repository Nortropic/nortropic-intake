#!/usr/bin/env python3
"""Capture signature of a <slug>-full-chat.md — the regression fingerprint.

Computes the capture-invariant shape of a delivered transcript: message count,
role sequence, per-message char lengths, first/last previews, fence balance and
a sha256 over the message body (metadata header excluded, so a re-capture of the
same chat on a different day reproduces the signature even though export-date
lines differ).

Usage:
  python3 capture_signature.py <full-chat.md>                  # print signature JSON
  python3 capture_signature.py <full-chat.md> --check <golden> # diff against golden, exit 1 on drift

Golden files live in evals/golden/<slug>.signature.json and are generated from a
REAL delivered transcript (measured shape — never hand-written fixtures).
Cross-check: if the transcript header declares a message count
("antal_meddelanden: 75 (29 användare, 46 assistent)" or
"**Antal meddelanden:** 20 (10 …)"), it must match what the body contains.
"""
import hashlib, json, re, sys

HEADER_RE = re.compile(r"^## Meddelande (\d+) — (.+?)\s*$", re.M)
DECLARED_RE = re.compile(
    r"(?:antal_meddelanden:|\*\*Antal meddelanden:\*\*)\s*(\d+)\s*\((\d+)\s*användare,\s*(\d+)\s*assistent",
    re.I,
)


def signature(path):
    text = open(path, encoding="utf-8").read()
    headers = list(HEADER_RE.finditer(text))
    if not headers:
        sys.exit("FAIL: no '## Meddelande N — <roll>' headers found")

    body = text[headers[0].start():]
    msgs = []
    for i, h in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        content = text[h.end():end].strip()
        content = re.sub(r"\n---\s*$", "", content).strip()  # trailing separator
        roleline = h.group(2)
        role = "user" if "användare" in roleline else (
            "assistant" if "assistent" in roleline else roleline)
        msgs.append((int(h.group(1)), role, content))

    nums = [n for n, _, _ in msgs]
    if nums != list(range(1, len(nums) + 1)):
        sys.exit(f"FAIL: message numbering not contiguous 1..{len(nums)}: {nums[:10]}…")
    if any(not c for _, _, c in msgs):
        sys.exit("FAIL: empty message body")

    unbalanced = [n for n, _, c in msgs
                  if sum(1 for l in c.split("\n") if l.startswith("```")) % 2]

    decl = DECLARED_RE.search(text[:headers[0].start()])
    if decl:
        d_total, d_user, d_asst = (int(decl.group(k)) for k in (1, 2, 3))
        got_user = sum(1 for _, r, _ in msgs if r == "user")
        got_asst = sum(1 for _, r, _ in msgs if r == "assistant")
        if (d_total, d_user, d_asst) != (len(msgs), got_user, got_asst):
            sys.exit(f"FAIL: header declares {d_total} ({d_user}u/{d_asst}a) "
                     f"but body has {len(msgs)} ({got_user}u/{got_asst}a)")

    def preview(s):
        return re.sub(r"\s+", " ", s)[:80]

    return {
        "message_count": len(msgs),
        "role_counts": {
            "user": sum(1 for _, r, _ in msgs if r == "user"),
            "assistant": sum(1 for _, r, _ in msgs if r == "assistant"),
        },
        "role_sequence": "".join("u" if r == "user" else "a" for _, r, _ in msgs),
        "per_message_chars": [len(c) for _, _, c in msgs],
        "total_chars": sum(len(c) for _, _, c in msgs),
        "first_message_preview": preview(msgs[0][2]),
        "last_message_preview": preview(msgs[-1][2]),
        "unbalanced_fence_messages": unbalanced,
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
    }


def main():
    if len(sys.argv) not in (2, 4) or (len(sys.argv) == 4 and sys.argv[2] != "--check"):
        sys.exit(__doc__)
    sig = signature(sys.argv[1])
    if sig["unbalanced_fence_messages"]:
        sys.exit(f"FAIL: unbalanced code fences in messages {sig['unbalanced_fence_messages']}")
    if len(sys.argv) == 2:
        print(json.dumps(sig, ensure_ascii=False, indent=1))
        return
    golden = json.load(open(sys.argv[3], encoding="utf-8"))
    drift = [k for k in golden if sig.get(k) != golden[k]]
    if drift:
        for k in drift:
            print(f"DRIFT {k}: golden={golden[k]!r} now={sig.get(k)!r}", file=sys.stderr)
        sys.exit(f"FAIL: signature drift in {drift}")
    print(f"OK: {sig['message_count']} messages "
          f"({sig['role_counts']['user']}u/{sig['role_counts']['assistant']}a), "
          f"{sig['total_chars']} chars — matches golden")


if __name__ == "__main__":
    main()
