# Brief rubric — score an `idea-<slug>.md`

Score each criterion 0 (absent/wrong), 1 (present but weak), 2 (fully met).
**Pass: ≥ 16/20 AND no zero on a criterion marked (critical).**
Use a fresh reviewer (subagent) given only the brief, the transcript path, and this rubric.

| # | Criterion | What "2" looks like |
|---|---|---|
| R1 | Self-contained (critical) | Actable without opening the transcript; systems, files, interfaces named. |
| R2 | Right altitude | Destination + quality bar; no implementation plan or pseudo-code; constraints marked "suggestions, not orders". |
| R3 | Decision log complete (critical) | Decisions AND explicitly rejected paths, each with a one-line "— because …". |
| R4 | Provenance tags | Every §4 entry ends with `(← msg N)` / `(← msg N–M)` that resolves to real transcript messages. |
| R5 | Side-tracks sorted (critical) | Every tangent in exactly one bucket: decided / rejected / open question; none silently dropped. |
| R6 | EARS criteria testable | "WHEN … THE <system> SHALL …" form; each maps to a check the agent can actually run. |
| R7 | Out of scope explicit | Neighboring ideas from the same chat and all rejected paths listed. |
| R8 | Open questions real | Genuine owner decisions, not filler; none already answered elsewhere in the brief. |
| R9 | Frontmatter valid | `status` is a lifecycle value (idea/clarified/planned/building/verified/superseded); `intended_repo_path` is `<slug>/idea-<slug>.md`; corpus links (supersedes/superseded_by/related) present where the corpus check set them. |
| R10 | Invariants pointer + length | One-line constitution/rulebook pointer at §2 and §6 (pointer, never copied content); brief ≤ ~1000 words. |

Report as: score table, total, pass/fail, and for every 0 or 1 a one-line fix.
