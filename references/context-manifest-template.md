# Context-manifest template (`<slug>-context-manifest.json`)

The WHERE layer of an intake package: a machine-readable map of every piece of source
material the thinking rests on, with integrity hashes and a capture status per source.

It does **not** duplicate content. Its whole job is to make the complete intellectual
source set *discoverable, addressable and integrity-checkable* — so that "full context"
means full information preservation, not full preload.

    FULL INFORMATION PRESERVATION  +  PROGRESSIVE DISCLOSURE  +  JUST-IN-TIME RETRIEVAL

Scaffold it from what is verifiably on disk, then complete it by hand from evidence:

    python3 ~/.claude/skills/nortropic-intake/scripts/context_contract.py \
        manifest init --slug <slug>
    python3 ~/.claude/skills/nortropic-intake/scripts/context_contract.py \
        manifest --slug <slug>          # validate

`manifest init` only records files it can see and hash. It never invents an attachment,
a URL or a repository — those you add from the brainstorm's own evidence.

## Rules that matter more than the field list

- **Never guess a source.** A manifest entry asserts that something existed and what its
  identity was. Fabricating one is worse than omitting it, because it looks like proof.
- **Load-bearing is explicit.** `load_bearing: true` means planning depends on it. A
  load-bearing source that is still `pending` blocks Plan Mode — a perfect brief must
  never hide missing source evidence.
- **Unavailable needs an owner, not a shrug.** `unavailable_owner_acknowledged` requires
  `owner_ack: {date, note}`. The acknowledgement itself is durable evidence.
- **Hashes are checked.** Any `captured` source with a `path` must exist in the idea
  folder and hash to its recorded `sha256`. Edit the source, re-hash the manifest.
- **No credentials, ever.** The validator refuses a manifest containing tokens, keys,
  presigned-URL signatures or credential query parameters. Sanitize the URL, or record
  the source as redacted. A manifest must never turn a secret into durable metadata.
- **Paths stay inside the package.** Relative to the idea folder; no `..`, no absolute
  paths, no private session/transcript paths.
- **Execution targets carry roles.** Nortropic repos do not share authority, so a plan
  spanning several of them must say which is which.

## Shape

```json
{
  "manifest_version": 1,
  "slug": "<slug>",
  "execution_targets": [
    { "repo": "~/nortropic/verkstadsgolvet",  "role": "operator-product" },
    { "repo": "~/nortropic/nortropic-system", "role": "advisory-only" }
  ],
  "sources": [
    {
      "source_id": "SRC-001",
      "kind": "chat-transcript",
      "name": "<slug>-full-chat.md",
      "path": "<slug>-full-chat.md",
      "sha256": "…",
      "capture_status": "captured",
      "fidelity": "full",
      "load_bearing": true,
      "origin": "https://chatgpt.com/c/…"
    },
    {
      "source_id": "SRC-004",
      "kind": "attachment",
      "name": "architecture-plan.pdf",
      "path": "sources/architecture-plan.pdf",
      "sha256": "…",
      "capture_status": "captured",
      "load_bearing": true
    },
    {
      "source_id": "SRC-005",
      "kind": "repository",
      "name": "nortropic-system @ docs/07-konstitution.md",
      "origin": "https://github.com/Nortropic/nortropic-system",
      "capture_status": "captured",
      "load_bearing": true,
      "note": "Read while planning; not copied into the package."
    },
    {
      "source_id": "SRC-006",
      "kind": "attachment",
      "name": "old-spec.pdf",
      "capture_status": "unavailable_owner_acknowledged",
      "load_bearing": true,
      "owner_ack": {
        "date": "2026-08-25",
        "note": "Original upload lost. Owner accepts planning without it; the decisions
                 it informed are already captured as D4 and D5."
      }
    }
  ]
}
```

## Fields

| Field | Meaning |
|---|---|
| `source_id` | `SRC-001`, unique and stable. Briefs, rationales and plans cite it. |
| `kind` | `chat-transcript`, `attachment`, `pasted-text`, `image`, `external-url`, `repository`, `commit`, `owner-clarifications`, `related-package`, `superseded-package`, `research`, `design-rationale`, `brief` |
| `name` | Human-facing name, as the owner would recognise it. |
| `path` | Relative to the idea folder, when the content lives in the package. |
| `sha256` | Required for `captured` sources with a `path`. |
| `capture_status` | `captured` · `not_load_bearing` · `unavailable_owner_acknowledged` · `pending` |
| `load_bearing` | `true`/`false`, never omitted. |
| `fidelity` | `full` / `partial`, mirroring the transcript's own metadata. |
| `origin` | URL or repository the source came from — sanitized of credentials. |
| `owner_ack` | `{date, note}` — required when the status is owner-acknowledged. |

## Execution-target roles

| Role | Authority |
|---|---|
| `canonical-system` | Owner-gated system authority; Intake may never author its truth |
| `operator-product` | Implementation target for product work |
| `advisory-only` | **READ ONLY** — reference material, never a write target |
| `intake-corpus` | The intake corpus itself |

`resume` prints these back with the repository evidence, and marks advisory targets
`TARGET_REPO_WRITABLE=NO`, so a multi-repo plan cannot quietly flatten the difference.

## Legacy packages

Ideas captured before this contract have no manifest. That is reported as
`LEGACY_CONTEXT_MANIFEST_MISSING` at **WARN** level — they stay valid in the corpus. Build
the manifest deliberately when the idea is next activated for planning, from the sources
you can actually find. Never mass-generate manifests across the corpus, and never
reconstruct an attachment list from a model's reading of the transcript.
