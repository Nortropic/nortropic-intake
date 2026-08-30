# Project manifest — `_projects/<project>/project-manifest.json`

The coverage contract of one PROJECT_SWEEP: which conversations exist, in what
lifecycle state, with what identity and what enumeration honesty. Everything here is
recomputed and re-validated from plain files by `scripts/project_contract.py`;
"Claude thinks it read everything" is never the evidence.

## The shape

```json
{
  "project_manifest_version": 1,
  "project": "improvements",
  "title": "Improvements — R&D corpus sweep",
  "platform": "chatgpt",
  "origin": "https://chatgpt.com/g/g-p-…/project",
  "created": "2026-09-01",
  "enumeration": {
    "method": "declared",
    "verified": false,
    "declared_inventory_sha256": "<sha256 of the inventory file>",
    "note": "owner-exported URL list; data-layer listing not provable"
  },
  "project_status": "",
  "inventory_revision": 3,
  "inventory_sha256": "<deterministic identity of the source inventory>",
  "inventory_history": [
    {"revision": 1, "inventory_sha256": "…", "at": "2026-09-01",
     "note": "declare inventory (declared, 41 item(s))"}
  ],
  "sources": [
    {
      "source_id": "CONV-001",
      "conversation_key": "chatgpt.com/68a1b2c3-…",
      "url": "https://chatgpt.com/c/68a1b2c3-…",
      "title": "Gauntlet quality layer (title is informational, never identity)",
      "discovered_at": "2026-09-01",
      "state": "ROUTED",
      "revisions": [
        {"revision": 1, "path": "_projects/improvements/sources/CONV-001/conversation.md",
         "sha256": "…", "captured_at": "2026-09-01", "message_count": 75,
         "adapter": "data-layer", "verified": true, "verify_detail": ""}
      ],
      "extracted_revision": 1,
      "routed_revision": 1,
      "ideas": ["gauntlet-wayfinder"],
      "extraction_note": "",
      "errors": []
    }
  ]
}
```

## The rules the validator enforces

- **Identity before ideas.** `conversation_key` is `host/<platform-conversation-id>`
  — never a title. Two conversations with the same title are two sources; a rerun
  upserts by key and can never duplicate one (`DUPLICATE_SOURCE_IDENTITY`).
- **Raw survives.** Every revision's bytes stay on disk exactly as captured
  (`SOURCE_FILE_MISSING`, `PROJECT_SOURCE_HASH_MISMATCH`); once committed, git is the
  witness (`PROJECT_SOURCE_MUTATED`). An updated conversation is a NEW revision file
  (`conversation-r2.md`), never an overwrite.
- **The tree and the manifest tell one story**, in both directions
  (`MANIFEST_TREE_MISMATCH`): an unrecorded capture is a silent one.
- **States are derived, not asserted.** The lifecycle
  `DISCOVERED → CAPTURED → VERIFIED → EXTRACTED → ROUTED → COMPLETE` (plus explicit
  `FAILED`) is recomputed from the record; a label the files cannot back fails as
  `SOURCE_STATE_INCONSISTENT` or `FALSE_COMPLETENESS`. `COMPLETE` is written only by
  `finalize`, and only over a source that is ROUTED at its latest revision.
- **Idea provenance is a hash link.** A source's `ideas` list holds slugs whose
  packages carry this conversation as an episode transcript, byte-identical to a
  recorded revision (`IDEA_PROVENANCE_DANGLING`, `IDEA_EPISODE_HASH_UNLINKED`).
  One chat may produce many ideas; many chats may CONTINUE_EXISTING one idea.
- **Enumeration is honest.** `verified: true` requires a provable completion signal
  (see `scripts/project_discovery.js` — a CANDIDATE adapter until verified live);
  otherwise coverage answers for the DECLARED inventory only and prints
  `PROJECT_ENUMERATION_UNVERIFIED`. Claiming verified with `method: none` fails
  (`ENUMERATION_CLAIM_INVALID`). DO NOT FAKE IT.
- **Hard gaps beat everything.** A source at DISCOVERED/CAPTURED/FAILED is a hard
  gap: `SOURCE_COVERAGE_COMPLETE=NO`, and the project's end state is
  `INCOMPLETE_HARD_GAPS` — never "complete with review". A review-queue item can
  never absorb a capture gap, because completeness is computed from lifecycle states
  and never reads the queue.
- **The inventory identity is deterministic** (sorted key+revision-hash lines plus
  the enumeration line); its history is append-only against git
  (`INVENTORY_HISTORY_REWRITTEN`/`_TRUNCATED`), and the sweep audit binds to the
  current `inventory_revision`.

## What does NOT belong here

Idea content (that lives in the idea packages), owner decisions (review-queue
entries carry the owner's exact words), execution state of any kind, credentials,
or a second copy of anything the corpus already records. `PROJECT.md` is a stamped
RENDERING of this manifest — the manifest stays canonical.
