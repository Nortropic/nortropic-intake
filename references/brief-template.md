# Idea brief template (`idea-<slug>.md`)

Grounded in Anthropic's Claude Code best practices (self-contained specs, verification-first,
fresh-session execution), their context-engineering guidance (right altitude, minimal
high-signal context), and spec-driven development practice (EARS criteria, explicit
out-of-scope, 1–3 pages). Reference example: `idea-gauntlet-quality-layer.md` in the Drive
folder "Nortropic innovation-intake".

## Rules that matter more than the section list

- **Self-contained.** Claude Code must be able to act on the brief alone. This brief is
  the primary intake artifact for execution; the rationale holds deeper design logic and
  the full chat is raw evidence, both linked as reference. Authority: current canonical
  repository authority beats all intake artifacts; within the intake package this brief
  wins over rationale and transcript — say so explicitly in the brief (§2).
- **Right altitude.** Describe the destination and the quality bar. Do not write the
  implementation plan or pseudo-code; the agent chooses architecture. Constraints go in a
  clearly marked "suggestions, not orders" section.
- **Sort the side-tracks.** A brainstorm is full of tangents; put each in exactly one
  bucket so none is silently dropped: **decided** (decision log), **rejected** (logged with
  its "because" — scan for reversals like "vi bygger ingen", "skippa X", "nej, gör
  istället…"), or **explored-but-unresolved** (→ becomes an open question). The classic
  failures are mirror images: an agent implementing an idea the human discarded two messages
  later, or a real decision getting buried as a tangent. When the owner is present, Phase
  2.5 confirms this sort before building.
- **Reasoning in three layers.** Every decision carries a one-line rationale ("— because …")
  so the most important *why* lives in the brief at near-zero token cost. The fuller design
  logic lives in `<slug>-design-rationale.md`; the full nuance stays in the transcript.
  Retrieval ladder (Process step 1): brief → rationale → targeted transcript message
  ranges only if still needed — never preload rationale or transcript into the
  implementing agent's main context.
- **Provenance on every decision.** Each §4 entry ends with a source tag `(← msg N)` or
  `(← msg N–M)` citing the message(s) in the linked transcript where it was made. A fresh
  session — possibly months later, for an idea-bank brief — jumps straight to the exact
  rationale instead of rereading the whole chat.
- **Invariants are pointed to, never copied.** One line at §2 and §6 points to Nortropic's
  trust layer (constitution, rulebook: trust contracts, frozen gates, §-rules). A pointer
  stays true when the trust docs evolve; a copy silently rots — extra important for
  idea-bank briefs built long after capture by a session with no other Nortropic context.
- **Verifiable bar.** Acceptance criteria in EARS form so each maps to a check the agent
  can run. End with an end-to-end verification step that proves the whole thing works —
  evidence, not claims.
- **Interview before planning.** Open questions are for Claude Code to ask Johnny
  (AskUserQuestion) in the Clarify step — not rhetorical filler.
- **Length:** target 2–3 pages (~1000 words). Controlled complexity exception: up to a
  hard maximum of 1600 words for genuinely high-complexity/long-source brainstorms where
  further compression would materially lose owner decisions, explicit rejected paths,
  genuine unresolved questions, or required provenance. Verbosity, duplicated rationale,
  implementation detail or transcript-like retelling never justify the exception.
  Past 1600 words the brief is defective: decompose the idea or compress further.

## Structure (use exactly these sections)

```markdown
---
title: "<Idea title>"
type: idea-brief
status: idea   # lifecycle: idea → clarified → planned → building → verified; terminal: superseded
               # routing sets it: idébank stores as `idea`; the Phase 2.5 interview sets `clarified`
               # (`ready-for-clarification` in older briefs is the legacy name for `idea`)
slug: <slug>
owner: Johnny (Nortropic)
created: <YYYY-MM-DD>
source_conversation: <slug>-full-chat.md   # raw evidence — this brief takes precedence
design_rationale: <slug>-design-rationale.md   # deeper design logic — read on demand, never preloaded
intended_repo_path: <slug>/idea-<slug>.md   # idea folder sits directly in the corpus-repo root
# Corpus links (set by the Phase 2.8 corpus check — include only the ones that apply):
# supersedes: [<old-slug>]
# superseded_by: <new-slug>   # set on the OLD brief when superseded, together with status: superseded
# related: [<slug>, ...]
---

# Idea brief: <title>

## 1. Summary
2–4 sentences: what is being added/changed, and the single most important framing decision.

## 2. Context you need
The minimum system context an agent needs (current architecture, what is missing, why now).
End with: "This brief is the primary intake artifact for execution. Deeper design logic
lives in the linked design rationale; the full chat is raw evidence — read targeted
message ranges only if the rationale is insufficient. Current canonical repository
authority beats all intake artifacts; within the intake package this brief wins over
rationale and transcript." followed by the one-line invariants pointer:
"Invariants this must not violate: Nortropic's trust layer — constitution & rulebook
(`nortropic-system/docs/07-konstitution.md`, `03-regelverk.md`): trust contracts, frozen
gates, §-rules. Pointer only — read them there; never copied here."

## 3. Destination (goal, not implementation plan)
Bulleted end-state. Close with: choose architecture/decomposition/tooling yourself,
pointing to the constraints section.

## 4. Decisions already made (do not relitigate silently)
D1, D2, … — including explicitly REJECTED paths, each marked as rejected.
Format: "D1. <decision> — because <one-line rationale from the chat> (← msg 18–20)."
The why lets the agent ask sharper interview questions and notice when a premise has
changed; the `(← msg N–M)` tag cites the source message(s) in the linked transcript so
the rationale can be pulled precisely, even long after capture.

## 5. Acceptance criteria (v1)
AC1, AC2, … in EARS form: "WHEN <trigger>, THE <system> SHALL <behavior>."
Each criterion must be checkable by the agent (test, render comparison, record inspection).

## 6. Constraints & implementation notes (right altitude — suggestions, not orders)
Open with the same one-line invariants pointer as §2 (constitution & rulebook — pointer,
never a copy). Then: native mechanisms to prefer, security defaults, fail-closed conditions.

## 7. Out of scope (v1)
Explicit list. Include neighboring ideas from the same chat and anything rejected.

## 8. Verification (how we know it works)
One end-to-end check producing evidence an independent reviewer can confirm
"from the record alone".

## 9. Open questions (interview the owner before planning)
Q1, Q2, … — real decisions Johnny must make, not filler.

## 10. Process for this brief
1. Clarify: first send a subagent to read `<slug>-design-rationale.md` (its rejection
   and unresolved sections cover most §9 rationale) and report back what bears on §9;
   only if the rationale lacks the needed evidence, exact source wording matters, or a
   conflict/ambiguity remains, have it read the targeted message ranges in the source
   conversation via the rationale's retrieval map — never the whole transcript, and keep
   both out of main context; then interview the owner on §9 (AskUserQuestion); append
   answers here.
2. Plan in plan mode; owner reviews before any code ("address all notes, don't implement yet").
3. Implement in a fresh session from the approved plan.
4. Adversarial review: fresh subagent checks the diff against this brief; report only
   gaps affecting correctness or stated requirements.
5. Traceability: commit messages cite this brief's slug.

## References
- Source conversation (same folder + intended repo path)
- https://code.claude.com/docs/en/best-practices
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
```
