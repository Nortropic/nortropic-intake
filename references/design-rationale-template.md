# Design-rationale template (`<slug>-design-rationale.md`)

The middle layer of the intake package: preserves WHY the brief ended up as it did,
without forcing the implementing agent to reread the raw brainstorm. Derived
independently from the transcript — never by copying the brief and adding prose.

**Default use: NOT preloaded into the main implementation context.** Read it when
architecture choices are ambiguous, two implementations both satisfy the brief, a
reviewer needs design intent, a later agent questions a rejection, a premise may have
changed, or planning needs deeper reasoning context.

## Rules that matter more than the section list

- **Non-authoritative.** Current canonical repository authority beats every intake
  artifact; within the intake package the brief beats this file, and this file beats the
  transcript, on intentional interpretation. A detailed rationale never becomes execution
  authority. Say so via `authority: non-authoritative-rationale` in the frontmatter.
- **It is NOT**: an implementation plan, a generic summary, a giant essay, a copy of the
  transcript, a copy of the brief, or ungrounded chain-of-thought reconstruction. Target
  2–4 pages; scale with the source, never past what the conversation supports.
- **Provenance on every material claim.** Each claim derived from the conversation ends
  with a message-range tag `(← msg N)` / `(← msg N–M)` into the linked full-chat.
- **Only explicit reasoning and defensible synthesis.** Never claim hidden/private
  reasoning that is not present in the user-visible source. Where useful, label a claim's
  kind: SOURCE-DERIVED FACT, OWNER DECISION, ASSISTANT INFERENCE, EXTERNAL CLAIM
  MENTIONED IN SOURCE, or OPEN HYPOTHESIS.
- **Rejections and unresolved explorations keep their status.** A rejected path stays
  visibly rejected (with the failure it would create); an explored-but-unresolved idea is
  never silently promoted to a decision.
- **Section examples are illustrative.** Any example shapes below appear in a real
  rationale only when that source conversation supports them.

## Structure (use exactly these sections; §8 is optional)

```markdown
---
title: "<Idea title> — design rationale"
type: design-rationale
status: source-derived
slug: <slug>
owner: Johnny (Nortropic)
created: <YYYY-MM-DD>
source_conversation: <slug>-full-chat.md
execution_brief: idea-<slug>.md
authority: non-authoritative-rationale
fidelity: full   # or partial — mirror the transcript's fidelity metadata
---

# Design rationale: <title>

## 1. Core thesis
The fundamental idea that emerged — the central conceptual model, not a feature list.
2–5 sentences, with source tags.

## 2. Problem / current state / intended outcome
Why this brainstorm happened: the problem being solved, and the desired state that was
repeatedly reinforced. (← msg tags)

## 3. Reasoning chain
The major causal logic, so a future architect understands the intellectual path without
reading the conversation: "A led to B because …; B made C necessary because …; C
rejected D because …". Every material step cites its message range. Do not invent
hidden reasoning.

## 4. Design decisions and why
The major decisions with fuller rationale than the brief's one-liners. For each:
D1. <decision>
    Why: <reasoning>
    Evidence: <what in the conversation supports it>
    Source: (← msg N–M)

## 5. Explicit rejections / anti-requirements
Critical section — for each rejected path:
REJECTED: <path>
WHY: <reasoning from the source>
FAILURE IT WOULD CREATE: <what goes wrong if built anyway>
SOURCE: (← msg N–M)

## 6. Explored but unresolved
Ideas seriously explored but NOT decided — never silently promoted. For each: the
question, the competing hypotheses, what evidence/decision would resolve it, source range.

## 7. Important trade-offs / tensions
Only tensions actually present in the source (e.g. autonomy vs control, context richness
vs context pollution), each with source tags.

## 8. Metaphor / concept → technical principle   (OPTIONAL)
Only when the brainstorm leans on metaphors or adjacent domains. Translate each:
METAPHOR → FUNCTIONAL PRINCIPLE → WHAT MUST NOT BE COPIED LITERALLY.
This protects implementing agents from treating a metaphor as a requirement.

## 9. External evidence mentioned in the conversation
Papers, companies, repos, books, frameworks, URLs, research findings that materially
influenced the reasoning. This is conversation-derived provenance: mark each item
MENTIONED IN SOURCE unless it was INDEPENDENTLY VERIFIED during this run — never
silently upgrade a transcript mention into a verified fact. Intake is
extraction/distillation, not a research agent.

## 10. Evolution / pivots
The few moments where the design materially changed:
initial hypothesis → challenge/finding → revised model. (← msg tags)
Keeps later agents from reviving superseded early framing.

## 11. Retrieval map
Compact table so a subagent can fetch targeted raw evidence instead of reading the
whole full-chat:

| topic | message range |
|---|---|
| <topic> | N–M |

## 12. What to load when
DEFAULT IMPLEMENTATION: read `idea-<slug>.md`.
IF DESIGN RATIONALE IS NEEDED: read this file.
IF EXACT SOURCE EVIDENCE IS NEEDED: read only the relevant message ranges in
`<slug>-full-chat.md` (use §11).
Do not preload the raw transcript into the main implementing context.
```
