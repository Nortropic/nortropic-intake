# Rationale rubric — score a `<slug>-design-rationale.md`

Score each criterion 0 (absent/wrong), 1 (present but weak), 2 (fully met).
**Pass: ≥ 16/20 AND no zero on a criterion marked (critical).**
Use a fresh reviewer (subagent) given only: the rationale, the brief, the transcript
path, and this rubric. Where a criterion's subject genuinely does not occur in the
source (noted per criterion), score it 2 — absence of the phenomenon is not a defect.

| # | Criterion | What "2" looks like |
|---|---|---|
| S1 | Distinct job (critical) | Materially different from the brief and the transcript: preserves design logic, not a copy of either, not an implementation plan/spec, not a generic summary; length 2–4 pages scaled to the source. |
| S2 | Core thesis + problem framing | §1–2 capture the central conceptual model (not a feature list) and why the brainstorm happened / the reinforced desired state. |
| S3 | Reasoning chain grounded | §3 preserves the major causal path ("A led to B because …") readable without the conversation; no invented hidden reasoning beyond the user-visible source. |
| S4 | Provenance (critical) | Every material claim ends with `(← msg N)` / `(← msg N–M)` that resolves to real messages in the linked transcript. |
| S5 | Rejections preserved (critical) | Each rejected path is unmistakably marked REJECTED with why, the failure it would create, and a source range — impossible to misread as a decision. |
| S6 | Unresolved stays unresolved | Explored-but-undecided ideas appear in §6 with competing hypotheses and what would resolve them; none silently promoted to decisions. |
| S7 | Trade-offs & pivots from source | §7/§10 list only tensions and pivots actually present in the conversation, each with source tags. (No tensions/pivots in source → 2 with sections truthfully brief.) |
| S8 | Metaphor safety | Where the source leans on metaphors/analogies, §8 translates each: metaphor → functional principle → what must NOT be copied literally. (No metaphors in source → 2 with §8 omitted.) |
| S9 | Evidence & claim labels | External references are marked MENTIONED IN SOURCE vs INDEPENDENTLY VERIFIED — never a silent upgrade; claim-kind labels (owner decision / assistant inference / open hypothesis) used where the distinction matters. |
| S10 | Retrieval map + frontmatter | §11 topic→message-range map resolves and covers the major topics; §12 states the load-when ladder incl. "do not preload the raw transcript"; frontmatter links brief + transcript, carries `authority: non-authoritative-rationale`, and `fidelity` mirrors the transcript. |

Report as: score table, total, pass/fail, and for every 0 or 1 a one-line fix.
