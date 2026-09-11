# Obsidian projection — vault layout and the contract it answers to (v4.4)

A vault is a SEPARATE repository (owner decision D3, 2026-09-11). It is regenerated
from one RND compile by `scripts/obsidian_projection.py render`, verified by
`verify`, and bound to the compile by `projection-manifest.json`. It is a derivative:
the record is canonical, the corpus is evidence, the vault is a reading.

    <vault>/
      projection-manifest.json     compile, ir_sha256, cut_sha256, corpus_commit,
                                   sha256 of every generated region, which cards
                                   carry notes, "authority": "none — …"
      .projection-state.json       generated-field memory and tombstones for the
                                   canvases (which pj: objects exist, which were
                                   manually removed, which manual objects were seen)
      INDEX.md                     records by kind, generated
      kort/RND-NNN.md              one card per record
      kort/SRC-<source>.md         one card per bound source
      linser/<lens>.canvas         one canvas per coverage lens (+ unlensed, oplacerat)
      linser/kallor.canvas         the bound sources

## A card

```
---
id: RND-088
kind: OWNER_DECISION
atomicity: ATOMIC
standing: CURRENT_CANDIDATE
authority_class: owner
compile: improvements-r38-c4-epistemic
fingerprint: 5a4400fa…
lenses: [rnd-intake]
sources: [CONV-001]
projection_card: rnd-record
---
<!-- projection:generated:start — regenerated on every render; write below ## Anteckningar -->
# RND-088 · OWNER_DECISION

**Claim:** …
**Quote:** ”…”
**Scope:** … · **Uncertainty:** …
**Owner authority basis:** owner-authored

## Provenance
| source | rev | messages/lines | path (corpus-relative) |
|---|---|---|---|
| CONV-001 | 2 | 62-71 | `_projects/improvements/sources/CONV-001/conversation-r2.md` |

## Relations
- supersedes → [[RND-087]]

## Lineage
- SAME RND-088

_Derived from `_rnd/<compile>/rnd-ir.json`. No execution authority, no priority, no status — a card is a reading of a record._
<!-- projection:generated:end -->

## Anteckningar

_(manual; preserved verbatim across renders — annotation, never evidence)_
```

Everything between the markers is regenerated on every render and must never be
edited (an edit is `PROJECTION_STALE`). Everything under `## Anteckningar` is the
reader's and survives byte for byte. A card whose record disappears from the IR is
kept with `retired: true` so its notes survive — it is not evidence.

## A canvas

Obsidian's own serialisation (1.13): tab indent, one object per line, compact JSON,
file order preserved. Generated objects carry `pj:` ids (`pj:card:RND-088`,
`pj:src:CONV-001`, `pj:edge:RND-088>RND-087:supersedes`); anything else is manual and
is never touched. A generated node is refreshed only in its generated fields and only
if they are still what the generator last wrote; position is never refreshed; a
generated object the reader deleted is tombstoned and not recreated.

## What verify refuses

`PROJECTION_STALE`, `PROJECTION_ITEM_MISSING`, `PROJECTION_CARD_ORPHANED`,
`PROJECTION_PROVENANCE_UNRESOLVED`, `PROJECTION_AUTHORITY_VOCABULARY`,
`PROJECTION_ANNOTATION_LOST`, `PROJECTION_NONDETERMINISTIC`,
`PROJECTION_CANVAS_INVALID`, `PROJECTION_MANIFEST_MISSING` — see SKILL.md. The one
that guards the vault's nature is `PROJECTION_AUTHORITY_VOCABULARY`: `priority:`,
`status:`, `disposition:`, `rank:`, `urgency:`, `deadline:` … anywhere in a card,
notes included, is refused. A note may say anything about a record except what the
organisation should do with it.
