# Evals — run these after ANY change to this skill

Three checks, all repeatable. Zero regression = all three pass. None of them touches
the capture/distill/verify pipeline itself — they measure its outputs.

## 1. Trigger eval (`trigger.json`)

Does the SKILL.md description still activate on the right requests and stay quiet on the
wrong ones?

1. Read `trigger.json`.
2. Spawn a FRESH judge (subagent, no other context). Give it ONLY: the current SKILL.md
   frontmatter `description` and the bare `query` strings — **never** the `expect` labels.
3. Ask for a trigger / no-trigger verdict per query (one line of reasoning each).
4. Diff verdicts against `expect`. Pass = 16/16. On mismatch: fix the description (or,
   if the world changed, the query set) — never coach the judge.

## 2. Capture-diff (`capture_signature.py` + `golden/`)

Does a known chat still produce the same capture signature? Guards the transcript body
format (`## Meddelande N — <roll>`, separators, junk-line rules) and the fail-closed
invariants (contiguous numbering, balanced fences, header count = body count).

```bash
# verify against the goldens (the regression test) — run BOTH:
python3 evals/capture_signature.py \
  ~/nortropic/innovation-intake/gauntlet-wayfinder/gauntlet-wayfinder-full-chat.md \
  --check evals/golden/gauntlet-wayfinder.signature.json
python3 evals/capture_signature.py \
  evals/golden/agent-workflow-claudeai-full-chat.md \
  --check evals/golden/agent-workflow-claudeai.signature.json

# (re)generate a golden — ONLY from a real, verified delivery, never hand-written:
python3 evals/capture_signature.py <path>/<slug>-full-chat.md > evals/golden/<slug>.signature.json
```

Golden fixtures must have measured shape: generate them from an actual delivered
transcript that passed the skill's own verification, then commit the JSON here. If the
transcript format legitimately changes, re-run the capture on the same source chat and
regenerate — a golden is only updated with a new measurement, never edited by hand.

Current goldens — BOTH data-layer adapters (ChatGPT and claude.ai) now have signature
coverage:
- `golden/gauntlet-wayfinder.signature.json` — ChatGPT data-layer capture, 75 messages
  (29 user / 46 assistant), source: `~/nortropic/innovation-intake/gauntlet-wayfinder/`.
- `golden/agent-workflow-claudeai.signature.json` — claude.ai data-layer capture,
  18 messages (10 user / 8 assistent), source chat: claude.ai/chat/
  e8403718-9c9f-453c-8ae5-1d5d53f198fc ("Automatisera agent-workflow med Claude").
  Its transcript (`golden/agent-workflow-claudeai-full-chat.md`) is a LOCAL, gitignored
  fixture — a private chat stays out of git; only the signature JSON is committed. If
  the transcript is missing on this machine, regenerate it by re-running the data-layer
  capture on that chat (adapter in `scripts/data_capture.js`, transcript format per
  SKILL.md Phase 1) — the signature must still match, that is the regression test.

## 3. Brief rubric (`brief-rubric.md`)

Scores a delivered `idea-<slug>.md` 0–20. Use on every new brief before delivery, and on
a known-good brief after template changes (it should still pass). Fresh reviewer
(subagent) gets only: the brief, the transcript path, the rubric. Pass = ≥16/20 and no
zero on criteria marked (critical). Note: pre-existing briefs written before the
provenance/invariants additions score 0–1 on R4/R10 by design — that flags backfill work,
not a regression.
