#!/usr/bin/env python3
"""Obsidian projection — a contract-governed DERIVATIVE of one RND compile.

    obsidian_projection.py render --corpus C --compile K --vault V [--write]
    obsidian_projection.py verify --corpus C --compile K --vault V

The vault is a separate directory (a separate repository, per owner decision D3).
It is never a source of truth: every card is regenerated from `rnd-ir.json`, every
provenance row points back into the corpus by corpus-relative path, and the vault's
manifest binds the exact `ir_sha256` (and, when the project has one, the
`cut_sha256`) the projection was rendered from. What the vault ADDS — the reader's
own notes under `## Anteckningar`, manual canvas nodes and edges, moved positions —
is annotation: preserved byte for byte across re-renders, never read back as
evidence, never allowed to carry authority vocabulary.

The pilot (kartlaggning-pilot, 2026-09-09) established the principles this script
lifts into a contract: a generated object is only ever updated where it is still
what the generator last wrote; a manually deleted node is not recreated; a card's
notes section survives; the canvas serialisation matches Obsidian's own so a save
without edits is byte-identical. What the pilot could not do — refuse a vault that
drifted from its compile, a card without an item, an item without a card, a
provenance row that resolves to nothing, a note that quietly says `priority: high`
— is what `verify` does, so the projection can be a link in the intake chain.

Codes:
    PROJECTION_MANIFEST_MISSING   no projection-manifest.json — nothing binds the vault
    PROJECTION_STALE              manifest ir_sha256 (or cut) != the compile's now, or
                                  a generated region differs from a fresh render
    PROJECTION_ITEM_MISSING       an IR record has no card
    PROJECTION_CARD_ORPHANED      a card names a record the IR does not hold and the
                                  card is not marked retired
    PROJECTION_PROVENANCE_UNRESOLVED  a card's provenance row does not resolve against
                                  the bound source bytes
    PROJECTION_AUTHORITY_VOCABULARY   a card (generated or annotation) carries a
                                  priority/status/disposition field — the vault
                                  would be turning into a backlog
    PROJECTION_ANNOTATION_LOST    a note or manual canvas object the manifest recorded
                                  is gone after render
    PROJECTION_IDENTITY_CONFLICT  old annotation identity cannot safely carry to new IR
    PROJECTION_NONDETERMINISTIC   two renders of the same IR differ
    PROJECTION_CANVAS_INVALID     a canvas is unparsable or an edge dangles
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from intake_common import (  # noqa: E402
    Finding, corpus_root, fails, read_json, report, sha256_file, sha256_text,
)
import rnd_contract as rc  # noqa: E402

PROJECTION_VERSION = 1
MANIFEST_NAME = "projection-manifest.json"
STATE_NAME = ".projection-state.json"
CARDS_DIR = "kort"
LENSES_DIR = "linser"
NODE_PREFIX = "pj:"
GEN_START = "<!-- projection:generated:start — regenerated on every render; write below "
GEN_START += "## Anteckningar -->"
GEN_END = "<!-- projection:generated:end -->"
NOTES_HEAD = "## Anteckningar"
_NOTES_HEAD_RE = re.compile(r"^## Anteckningar[ \t]*$", re.M)
NOTES_PLACEHOLDER = "_(manual; preserved verbatim across renders — annotation, never evidence)_"

NODE_KEY_ORDER = {
    "file": ["id", "type", "file", "subpath", "x", "y", "width", "height", "color"],
    "text": ["id", "type", "x", "y", "width", "height", "color", "text"],
    "group": ["id", "type", "x", "y", "width", "height", "color", "label",
              "background", "backgroundStyle"],
    "link": ["id", "type", "url", "x", "y", "width", "height", "color"],
}
EDGE_KEY_ORDER = ["id", "fromNode", "fromSide", "fromEnd", "toNode", "toSide",
                  "toEnd", "color", "label"]
CARD_W, CARD_H, GAP, COLS = 400, 200, 40, 6

# The vault must never become a backlog. Same lemma-based refusal the IR uses for
# its keys, applied to card frontmatter keys — plus a line-level pattern over the
# whole card, notes included, because a note that says `prioritet: hög` is an
# annotation turning into a ranking.
_AUTHORITY_LINE_RE = re.compile(
    r"^\s*(?:priority|prioritet|status|disposition|rank|ranking|weight|vikt|urgency|"
    r"importance|viktighet|score|poäng|deadline|assignee|owner_task|task|plan)\s*:",
    re.I | re.M)
_CANVAS_AUTHORITY_RE = re.compile(
    r"(?:^|\n)\s*(?:priority|prioritet|status|disposition|rank|urgency|importance)"
    r"\s*:", re.I)


# ----------------------------------------------------------------- helpers --

def _ordered(d, order):
    keys = [k for k in order if k in d] + [k for k in d if k not in order]
    return {k: d[k] for k in keys}


def dump_canvas(c):
    """Obsidian's own serialisation (1.13): tab indent, one node/edge per line,
    compact objects, file order preserved — so a save without edits is a no-op."""
    lines = ["{", "\t\"nodes\":["]
    lines.append(",\n".join(
        "\t\t" + json.dumps(_ordered(n, NODE_KEY_ORDER.get(n.get("type"), [])),
                            ensure_ascii=False, separators=(",", ":"))
        for n in c["nodes"]))
    lines.append("\t],")
    lines.append("\t\"edges\":[")
    lines.append(",\n".join(
        "\t\t" + json.dumps(_ordered(e, EDGE_KEY_ORDER), ensure_ascii=False,
                            separators=(",", ":")) for e in c["edges"]))
    lines.append("\t]")
    lines.append("}")
    return "\n".join(lines)


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-") or "x"


def _read(path):
    return io.open(path, encoding="utf-8").read()


def split_card(text):
    """(generated region, notes section) of an existing card, or ("", None)."""
    start = 0
    if GEN_START in text and GEN_END in text:
        gen = text[text.index(GEN_START):text.index(GEN_END) + len(GEN_END)]
        start = text.index(GEN_END) + len(GEN_END)
    else:
        gen = ""
    # the notes head is a LINE, searched after the generated region — the start
    # marker itself mentions the head in prose, and matching that would fold the
    # generated region into the "notes" and double it on every render. Everything
    # after the generated region is the READER'S region and is carried whole
    # (independent review F-14: text between the end marker and the head used to
    # be neither verified nor preserved); the head must still be present in it.
    m = _NOTES_HEAD_RE.search(text, start)
    if m:
        rest = text[start:]
        return gen, rest.lstrip("\n") if rest.strip() else rest
    return gen, None


def load_ir(corpus, compile_id):
    ir, findings = rc.load_ir(corpus, compile_id)
    return ir, findings


def ir_sha(corpus, compile_id):
    p = rc.compile_dir(corpus, compile_id) / rc.IR_NAME
    return sha256_file(p) if p.exists() else ""


# ------------------------------------------------------------------ cards --

def render_card(ir, item, lenses_of, sources):
    """The generated region of one record's card. Deterministic: no clocks."""
    iid = item.get("id", "?")
    kind = item.get("kind", "?")
    fm = [
        "---",
        "id: %s" % iid,
        "kind: %s" % kind,
        "atomicity: %s" % (item.get("atomicity") or "—"),
        "standing: %s" % (item.get("standing") or "—"),
        "authority_class: %s" % (item.get("authority_class") or "—"),
        "compile: %s" % ir.get("compile_id", "?"),
        "fingerprint: %s" % (item.get("fingerprint") or rc.record_fingerprint(item)),
        "lenses: [%s]" % ", ".join(lenses_of.get(iid, [])),
        "sources: [%s]" % ", ".join(sorted({str(p.get("source_id", p.get("rq", "")))
                                             for p in (item.get("provenance") or [])
                                             if isinstance(p, dict)})),
        "projection_card: rnd-record",
        "---",
    ]
    body = [GEN_START, "# %s · %s" % (iid, kind), ""]
    body.append("**Claim:** %s" % str(item.get("claim", "")).strip())
    body.append("")
    q = str(item.get("quote", "")).strip()
    if q:
        body.append("**Quote:** ”%s”" % q)
        body.append("")
    body.append("**Scope:** %s · **Uncertainty:** %s"
                % (item.get("scope", "—"), item.get("uncertainty", "—")))
    if item.get("owner_authority_basis"):
        body.append("**Owner authority basis:** %s" % item["owner_authority_basis"])
    if item.get("activation_condition"):
        body.append("**Activation condition (information only):** %s"
                    % item["activation_condition"])
    body.append("")
    body.append("## Provenance")
    body.append("")
    body.append("| source | rev | messages/lines | path (corpus-relative) |")
    body.append("|---|---|---|---|")
    for p in (item.get("provenance") or []):
        if not isinstance(p, dict):
            continue
        if p.get("rq"):
            body.append("| %s | — | owner answer | review-queue.md |" % p["rq"])
            continue
        sid = str(p.get("source_id", ""))
        b = sources.get(sid)
        body.append("| %s | %s | %s | `%s` |"
                    % (sid, p.get("revision", "—"),
                       p.get("messages", p.get("lines", "—")),
                       b.rel if b is not None else "UNBOUND"))
    body.append("")
    rels = [r for r in (item.get("relations") or []) if isinstance(r, dict)]
    if rels:
        body.append("## Relations")
        body.append("")
        for r in rels:
            body.append("- %s → [[%s]]%s" % (r.get("rel", "?"), r.get("target", "?"),
                                              (" (scope: %s)" % r["scope"])
                                              if r.get("scope") else ""))
        body.append("")
    lin = [e for e in (item.get("lineage") or []) if isinstance(e, dict)]
    if lin:
        body.append("## Lineage")
        body.append("")
        for e in lin:
            body.append("- %s %s" % (e.get("relation", "?"), e.get("id", "?")))
        body.append("")
    el = item.get("epistemic_limit")
    if el:
        body.append("## Epistemic limit")
        body.append("")
        body.append("```json")
        body.append(json.dumps(el, ensure_ascii=False, indent=1, sort_keys=True))
        body.append("```")
        body.append("")
    tags = item.get("tags") or []
    if tags:
        body.append("**Tags:** %s" % ", ".join(str(t) for t in tags))
        body.append("")
    body.append("_Derived from `_rnd/%s/rnd-ir.json`. No execution authority, no "
                "priority, no status — a card is a reading of a record._"
                % ir.get("compile_id", "?"))
    body.append(GEN_END)
    return "\n".join(fm) + "\n" + "\n".join(body) + "\n"


def render_source_card(ir, sid, b, items_by_source):
    fm = ["---", "id: SRC-%s" % sid, "kind: %s" % b.kind,
          "compile: %s" % ir.get("compile_id", "?"),
          "projection_card: source", "---"]
    body = [GEN_START, "# %s" % sid, "",
            "**Path (corpus-relative):** `%s`" % b.rel,
            "**Bound identity:** `%s`" % (b.recorded_sha or b.recorded_file_sha or "—"),
            "**Revision:** %s" % b.rec.get("revision", "—"), ""]
    if b.is_document():
        body.append("**Document** — evidence role: %s; line extent: %s"
                    % (b.rec.get("evidence_role", "?"), b.line_total()))
    else:
        body.append("**Conversation** — messages recorded: %s"
                    % (b.recorded_count if b.recorded_count is not None else "—"))
    body.append("")
    body.append("## Records citing this source")
    body.append("")
    for iid in items_by_source.get(sid, []):
        body.append("- [[%s]]" % iid)
    if not items_by_source.get(sid):
        body.append("- (none)")
    body.append("")
    body.append(GEN_END)
    return "\n".join(fm) + "\n" + "\n".join(body) + "\n"


def compose_card(generated, notes):
    notes = notes if notes is not None else "%s\n\n%s\n" % (NOTES_HEAD, NOTES_PLACEHOLDER)
    if not notes.endswith("\n"):
        notes += "\n"
    return generated + "\n" + notes


# ----------------------------------------------------------------- canvas --

def _layout(new_ids, existing_nodes):
    """Grid placement for NEW nodes only, below whatever already exists."""
    ymax = max([n.get("y", 0) + n.get("height", 0) for n in existing_nodes] or [-GAP])
    pos = {}
    for i, nid in enumerate(new_ids):
        r, c = divmod(i, COLS)
        pos[nid] = (c * (CARD_W + GAP), ymax + GAP + r * (CARD_H + GAP), CARD_W, CARD_H)
    return pos


def merge_canvas(existing, state_entry, want_nodes, want_edges, log):
    """Never delete, never move, refresh generated fields only where untouched."""
    nodes = {n["id"]: n for n in existing.get("nodes", []) if isinstance(n, dict)}
    edges = {e["id"]: e for e in existing.get("edges", []) if isinstance(e, dict)}
    suppressed_n = set(state_entry.setdefault("suppressed_nodes", []))
    suppressed_e = set(state_entry.setdefault("suppressed_edges", []))
    gen = state_entry.setdefault("gen", {})
    for nid in state_entry.get("nodes", []):
        if nid not in nodes and nid not in suppressed_n:
            suppressed_n.add(nid)
            log.append("node %s manually removed — not recreated" % nid)
    for eid in state_entry.get("edges", []):
        if eid not in edges and eid not in suppressed_e:
            suppressed_e.add(eid)
            log.append("edge %s manually removed — not recreated" % eid)

    def refresh(oid, obj, spec, fields):
        newv = {k: spec[k] for k in fields if spec.get(k) is not None}
        cur = {k: obj[k] for k in fields if obj.get(k) is not None}
        last = gen.get(oid)
        if last is None and cur != newv:
            gen[oid] = dict(cur, _origin="unknown-kept")
            log.append("%s untracked and differs from the generator — kept as "
                       "annotation" % oid)
            return
        if last is None or (last.get("_origin") is None and cur == last):
            if cur != newv:
                for k in fields:
                    obj.pop(k, None)
                obj.update(newv)
            gen[oid] = newv
        else:
            log.append("%s has manually edited fields — kept" % oid)

    new = []
    for nid, spec in want_nodes:
        if nid in nodes:
            refresh(nid, nodes[nid], spec, ("file", "text", "label", "color"))
        elif nid not in suppressed_n:
            new.append((nid, spec))
    pos = _layout([nid for nid, _ in new], list(nodes.values()))
    for nid, spec in new:
        x, y, w, h = pos[nid]
        n = {"id": nid, "type": spec["type"], "x": x, "y": y, "width": w, "height": h}
        for k in ("file", "text", "label", "color"):
            if spec.get(k):
                n[k] = spec[k]
        nodes[nid] = n
        gen[nid] = {k: spec[k] for k in ("file", "text", "label", "color")
                    if spec.get(k) is not None}
    for eid, spec in want_edges:
        if eid in edges:
            refresh(eid, edges[eid], spec, ("label", "color"))
        elif eid not in suppressed_e and spec["fromNode"] in nodes \
                and spec["toNode"] in nodes:
            e = {"id": eid, "fromNode": spec["fromNode"], "fromSide": "bottom",
                 "toNode": spec["toNode"], "toSide": "top"}
            if spec.get("label"):
                e["label"] = spec["label"]
            edges[eid] = e
            gen[eid] = {k: spec[k] for k in ("label", "color") if spec.get(k)}
    # file order: existing order first, new appended — Obsidian preserves order
    order_n = [n["id"] for n in existing.get("nodes", []) if isinstance(n, dict)
               and n["id"] in nodes] + [nid for nid, _ in new]
    order_e = [e["id"] for e in existing.get("edges", []) if isinstance(e, dict)
               and e["id"] in edges] + [eid for eid, _ in want_edges
                                       if eid in edges and eid not in
                                       {e["id"] for e in existing.get("edges", [])
                                        if isinstance(e, dict)}]
    state_entry["nodes"] = sorted(set(order_n) | {nid for nid in state_entry.get("nodes", [])
                                                  if nid.startswith(NODE_PREFIX)})
    state_entry["edges"] = sorted(set(order_e) | {eid for eid in state_entry.get("edges", [])
                                                  if eid.startswith(NODE_PREFIX)})
    state_entry["suppressed_nodes"] = sorted(suppressed_n)
    state_entry["suppressed_edges"] = sorted(suppressed_e)
    return {"nodes": [nodes[i] for i in order_n], "edges": [edges[i] for i in order_e]}


# ------------------------------------------------------------------ render --

def plan(corpus, compile_id):
    """Everything the render needs, derived from the IR — or findings."""
    ir, findings = load_ir(corpus, compile_id)
    if ir is None:
        return None, findings
    items = [i for i in (ir.get("items") or []) if isinstance(i, dict)
             and rc.ITEM_ID_RE.match(str(i.get("id", "")))]
    sources = rc.bind_sources(corpus, ir)
    lenses_of = {}
    lens_items = {}
    for row in (ir.get("coverage") or []):
        if not isinstance(row, dict):
            continue
        lens = str(row.get("lens", "")).strip()
        for b in (row.get("basis") or []):
            lenses_of.setdefault(str(b).strip(), []).append(lens)
            lens_items.setdefault(lens, []).append(str(b).strip())
    for u in (ir.get("unlensed") or []):
        if isinstance(u, dict):
            for b in (u.get("items") or []):
                lenses_of.setdefault(str(b).strip(), []).append("unlensed")
                lens_items.setdefault("unlensed", []).append(str(b).strip())
    by_id = {i["id"]: i for i in items}
    for iid in by_id:
        if iid not in lenses_of:
            lens_items.setdefault("oplacerat", []).append(iid)
            lenses_of[iid] = ["oplacerat"]
    items_by_source = {}
    for i in items:
        for p in (i.get("provenance") or []):
            if isinstance(p, dict) and p.get("source_id"):
                items_by_source.setdefault(str(p["source_id"]), []).append(i["id"])
    for k in items_by_source:
        items_by_source[k] = sorted(set(items_by_source[k]))
    return {"ir": ir, "items": items, "by_id": by_id, "sources": sources,
            "lenses_of": lenses_of, "lens_items": lens_items,
            "items_by_source": items_by_source}, findings


def identity_preflight(corpus, compile_id, vault, current):
    """Refuse ambiguous reuse before touching cards, canvas state or the manifest.

    Legacy v1 manifests already bind the old IR. Use that witness and each card's
    header; a bare filename is never an identity. A different compile can carry
    an unchanged local ID only through a validated SAME lineage to that exact IR.
    Renumbering, split/revised records and retired-ID reuse need an explicit
    migration; this renderer deliberately does not guess where annotations belong.
    """
    def refuse(detail):
        return [Finding(compile_id, "PROJECTION_IDENTITY_CONFLICT", detail)]

    path = vault / MANIFEST_NAME
    managed = ((vault / STATE_NAME).exists() or
               any((vault / CARDS_DIR).glob("*.md")) or
               any((vault / LENSES_DIR).glob("*.canvas")))
    if not path.exists():
        return refuse("existing projection has no identity manifest; preserve it and "
                      "restore its binding before rendering") if managed else []
    old, err = read_json(path)
    if err or not isinstance(old, dict):
        return refuse("previous projection manifest is unreadable")
    previous = old.get("compile")
    if not isinstance(previous, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", previous):
        return refuse("previous compile identity is missing or invalid")
    ir_path = rc.compile_dir(corpus, previous) / rc.IR_NAME
    if not ir_path.is_file() or sha256_file(ir_path) != old.get("ir_sha256"):
        return refuse("previous IR is missing or changed; cannot prove annotation identity")
    before, err = read_json(ir_path)
    if err or not isinstance(before, dict):
        return refuse("previous IR cannot be read")
    if (before.get("source_set") or {}).get("project") != \
            (current["ir"].get("source_set") or {}).get("project"):
        return refuse("projection belongs to a different source project")
    by_id = {i["id"]: i for i in before.get("items", [])}
    for iid in by_id:
        if not (vault / CARDS_DIR / (iid + ".md")).is_file():
            return refuse("%s: previous card missing; cannot prove preserved manual data" % iid)
    changing = previous != compile_id
    baseline = current["ir"].get("lineage_baseline") or {}
    for card in sorted((vault / CARDS_DIR).glob("RND-*.md")):
        text = _read(card)
        header = text.split(GEN_START, 1)[0]
        def field(name):
            match = re.search(r"^" + name + r": ([^\n]+)$", header, re.M)
            return match.group(1) if match else None
        item = by_id.get(card.stem)
        target = current["by_id"].get(card.stem)
        if item is None:
            if target is not None or field("retired") != "true":
                return refuse("%s: unbound or retired local ID cannot be reused" % card.name)
            continue
        fingerprint = rc.record_fingerprint(item)
        gen, _notes = split_card(text)
        if (field("id") != item["id"] or field("compile") != previous or
                field("fingerprint") != fingerprint or
                (item.get("fingerprint") and item["fingerprint"] != fingerprint)):
            return refuse("%s: old card does not match its bound record" % card.name)
        if sha256_text(gen) != (old.get("generated") or {}).get(
                "%s/%s" % (CARDS_DIR, card.name)):
            return [Finding(compile_id, "PROJECTION_STALE",
                            "%s: previous generated region changed" % card.name)]
        if target is not None:
            if (rc.record_fingerprint(target) != fingerprint or
                    (target.get("fingerprint") and target["fingerprint"] != fingerprint)):
                return refuse("%s: changed record behind a reused local ID; preserve "
                              "the old projection and resolve identity explicitly" % card.name)
            if changing and (baseline.get("compile") != previous or
                             baseline.get("ir_sha256") != old.get("ir_sha256") or
                             {"id": item["id"], "relation": "SAME"} not in
                             (target.get("lineage") or [])):
                return refuse("%s: compile change needs SAME lineage to the exact "
                              "previous IR" % card.name)
    return []


def render_files(corpus, compile_id, vault, write=False):
    """{relpath: bytes} of every generated file, merged with what the vault holds.
    Returns (files, manifest, log, findings)."""
    p, findings = plan(corpus, compile_id)
    if p is None:
        return {}, None, [], findings
    vault = Path(vault)
    identity_findings = identity_preflight(corpus, compile_id, vault, p)
    if identity_findings:
        return {}, None, [], findings + identity_findings
    state_path = vault / STATE_NAME
    state, _ = read_json(state_path) if state_path.exists() else ({}, None)
    state = state if isinstance(state, dict) else {}
    log = []
    files = {}
    ir = p["ir"]
    notes_seen = {}

    def existing(rel):
        f = vault / rel
        return _read(f) if f.is_file() else None

    # record cards
    for item in p["items"]:
        rel = "%s/%s.md" % (CARDS_DIR, item["id"])
        gen = render_card(ir, item, p["lenses_of"], p["sources"])
        old = existing(rel)
        _g, notes = split_card(old) if old is not None else ("", None)
        if notes is not None:
            notes_seen[rel] = sha256_text(notes)
        files[rel] = compose_card(gen, notes)
    # retired cards: a card whose record is gone keeps its notes and is marked
    if (vault / CARDS_DIR).is_dir():
        for f in sorted((vault / CARDS_DIR).glob("RND-*.md")):
            iid = f.stem
            if iid in p["by_id"]:
                continue
            old = _read(f)
            _g, notes = split_card(old)
            if notes is not None:
                notes_seen["%s/%s" % (CARDS_DIR, f.name)] = sha256_text(notes)
            gen = ("---\nid: %s\nretired: true\ncompile: %s\nprojection_card: "
                   "rnd-record\n---\n%s\n# %s · RETIRED\n\nThis record is not in "
                   "`%s`. The card stays so its notes survive; it is not evidence.\n%s\n"
                   % (iid, ir.get("compile_id", "?"), GEN_START, iid,
                      ir.get("compile_id", "?"), GEN_END))
            files["%s/%s" % (CARDS_DIR, f.name)] = compose_card(gen, notes)
            log.append("%s retired — record absent from the IR; notes kept" % iid)
    # source cards
    for sid, b in sorted(p["sources"].items()):
        if b.excluded:
            continue
        rel = "%s/SRC-%s.md" % (CARDS_DIR, sid)
        gen = render_source_card(ir, sid, b, p["items_by_source"])
        old = existing(rel)
        _g, notes = split_card(old) if old is not None else ("", None)
        if notes is not None:
            notes_seen[rel] = sha256_text(notes)
        files[rel] = compose_card(gen, notes)
    # lens canvases
    canvases = state.setdefault("canvases", {})
    for lens, iids in sorted(p["lens_items"].items()):
        rel = "%s/%s.canvas" % (LENSES_DIR, _slug(lens))
        old = existing(rel)
        try:
            cur = json.loads(old) if old else {"nodes": [], "edges": []}
        except ValueError:
            findings.append(Finding(compile_id, "PROJECTION_CANVAS_INVALID",
                                    "%s is not valid JSON" % rel))
            continue
        want_nodes = [("%scard:%s" % (NODE_PREFIX, iid),
                       {"type": "file", "file": "%s/%s.md" % (CARDS_DIR, iid)})
                      for iid in sorted(set(iids)) if iid in p["by_id"]]
        want_edges = []
        members = {iid for iid in iids}
        for iid in sorted(members):
            for r in (p["by_id"].get(iid, {}).get("relations") or []):
                if not isinstance(r, dict):
                    continue
                t = str(r.get("target", ""))
                rel_name = str(r.get("rel", ""))
                if t in members and rel_name in ("supports", "contradicts",
                                                 "supersedes", "composed_of"):
                    want_edges.append(("%sedge:%s>%s:%s" % (NODE_PREFIX, iid, t, rel_name),
                                       {"fromNode": "%scard:%s" % (NODE_PREFIX, iid),
                                        "toNode": "%scard:%s" % (NODE_PREFIX, t),
                                        "label": rel_name}))
        entry = canvases.setdefault(rel, {})
        merged = merge_canvas(cur, entry, want_nodes, want_edges, log)
        files[rel] = dump_canvas(merged) + "\n"
    # sources canvas
    rel = "%s/kallor.canvas" % LENSES_DIR
    old = existing(rel)
    try:
        cur = json.loads(old) if old else {"nodes": [], "edges": []}
    except ValueError:
        cur = {"nodes": [], "edges": []}
        findings.append(Finding(compile_id, "PROJECTION_CANVAS_INVALID",
                                "%s is not valid JSON" % rel))
    want_nodes = [("%ssrc:%s" % (NODE_PREFIX, sid),
                   {"type": "file", "file": "%s/SRC-%s.md" % (CARDS_DIR, sid)})
                  for sid, b in sorted(p["sources"].items()) if not b.excluded]
    entry = canvases.setdefault(rel, {})
    files[rel] = dump_canvas(merge_canvas(cur, entry, want_nodes, [], log)) + "\n"
    # index
    lines = ["# %s — projection index" % ir.get("compile_id", "?"), "",
             "Generated from `_rnd/%s/rnd-ir.json`. Cards under `%s/`, lens views "
             "under `%s/`. A card is a reading; the record is canonical; the "
             "corpus is evidence." % (ir.get("compile_id", "?"), CARDS_DIR, LENSES_DIR),
             ""]
    for kind in rc.KINDS:
        ids = sorted(i["id"] for i in p["items"] if i.get("kind") == kind)
        if ids:
            lines.append("## %s (%d)" % (kind, len(ids)))
            lines.append("")
            for iid in ids:
                lines.append("- [[%s]] — %s" % (iid, str(p["by_id"][iid].get("claim", ""))[:120]))
            lines.append("")
    files["INDEX.md"] = "\n".join(lines) + "\n"

    src = ir.get("source_set") if isinstance(ir.get("source_set"), dict) else {}
    manual_objects = {}
    for rel in files:
        if not rel.endswith(".canvas"):
            continue
        try:
            c = json.loads(files[rel])
        except ValueError:
            continue
        objs = {}
        for kind in ("nodes", "edges"):
            for o in c.get(kind, []):
                if isinstance(o, dict) and not str(o.get("id", "")).startswith(NODE_PREFIX):
                    objs[str(o.get("id"))] = sha256_text(
                        json.dumps(o, sort_keys=True, ensure_ascii=False))
        if objs:
            manual_objects[rel] = objs
    manifest = {
        "projection_version": PROJECTION_VERSION,
        "manual_objects": manual_objects,   # canvas -> {id: sha256 of the object}
        "compile": compile_id,
        "ir_sha256": ir_sha(corpus, compile_id),
        "cut_sha256": str(src.get("cut_sha256", "")).strip() or None,
        "project": src.get("project"),
        "corpus_commit": _corpus_commit(corpus),
        "records": len(p["items"]),
        "sources": len([b for b in p["sources"].values() if not b.excluded]),
        "generated": {},        # relpath -> sha256 of the GENERATED region
        "annotations": {},      # relpath -> sha256 of the notes section, if any
        "authority": "none — a projection carries no priority, status or disposition",
    }
    for rel, text in files.items():
        if rel.endswith(".md") and rel.startswith(CARDS_DIR + "/"):
            gen, notes = split_card(text)
            manifest["generated"][rel] = sha256_text(gen)
            if notes is not None and notes.strip() != \
                    "%s\n\n%s" % (NOTES_HEAD, NOTES_PLACEHOLDER):
                manifest["annotations"][rel] = sha256_text(notes)
        else:
            manifest["generated"][rel] = sha256_text(text)
    if write:
        for rel, text in files.items():
            f = vault / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            if not f.exists() or _read(f) != text:
                io.open(f, "w", encoding="utf-8").write(text)
        rc.write_json(vault / MANIFEST_NAME, manifest)
        rc.write_json(state_path, state)
        # annotation preservation, proven after the write
        for rel, digest in notes_seen.items():
            f = vault / rel
            _g, notes = split_card(_read(f)) if f.is_file() else ("", None)
            if notes is None or sha256_text(notes) != digest:
                findings.append(Finding(compile_id, "PROJECTION_ANNOTATION_LOST",
                                        "%s: the notes section changed across render"
                                        % rel))
    return files, manifest, log, findings


def _corpus_commit(corpus):
    try:
        head = Path(corpus) / ".git" / "HEAD"
        ref = head.read_text().strip()
        if ref.startswith("ref: "):
            rp = Path(corpus) / ".git" / ref[5:]
            return rp.read_text().strip() if rp.exists() else ""
        return ref
    except OSError:
        return ""


# ------------------------------------------------------------------ verify --

def verify_vault(corpus, compile_id, vault):
    vault = Path(vault)
    findings = []
    meta = {"cards": 0}
    try:
        vault.resolve().relative_to(Path(corpus).resolve())
        findings.append(Finding(compile_id, "PROJECTION_MANIFEST_MISSING",
                                "%s lives inside the corpus — a projection is a separate "
                                "derivative, never a corpus file; nothing inside the "
                                "corpus is accepted as a vault" % vault))
        return findings, meta
    except ValueError:
        pass
    mpath = vault / MANIFEST_NAME
    if not mpath.is_file():
        findings.append(Finding(compile_id, "PROJECTION_MANIFEST_MISSING",
                                "%s has no %s — nothing binds this vault to a compile"
                                % (vault, MANIFEST_NAME)))
        return findings, meta
    manifest, err = read_json(mpath)
    if err or not isinstance(manifest, dict):
        findings.append(Finding(compile_id, "PROJECTION_MANIFEST_MISSING",
                                "%s unreadable: %s" % (MANIFEST_NAME, err)))
        return findings, meta
    if str(manifest.get("compile", "")).strip() != compile_id:
        findings.append(Finding(compile_id, "PROJECTION_STALE",
                                "vault was rendered from compile %r, asked to verify "
                                "against %r" % (manifest.get("compile"), compile_id)))
        return findings, meta
    current = ir_sha(corpus, compile_id)
    if str(manifest.get("ir_sha256", "")).strip().lower() != current:
        findings.append(Finding(
            compile_id, "PROJECTION_STALE",
            "vault renders ir_sha256 %s… but the IR is %s… — re-render; the IR is "
            "canonical and the vault is a projection of it"
            % (str(manifest.get("ir_sha256", ""))[:12], current[:12])))
    p, pf = plan(corpus, compile_id)
    findings.extend(pf)
    if p is None:
        return findings, meta
    src = p["ir"].get("source_set") if isinstance(p["ir"].get("source_set"), dict) else {}
    bound_cut = str(src.get("cut_sha256", "")).strip() or None
    if (manifest.get("cut_sha256") or None) != bound_cut:
        findings.append(Finding(
            compile_id, "PROJECTION_STALE",
            "vault binds cut %s but the compile binds %s"
            % (manifest.get("cut_sha256"), bound_cut)))

    # determinism: two in-memory renders agree, and disk generated regions match
    files1, _m1, _l1, f1 = render_files(corpus, compile_id, vault, write=False)
    files2, _m2, _l2, _f2 = render_files(corpus, compile_id, vault, write=False)
    findings.extend(f1)
    if files1 != files2:
        findings.append(Finding(compile_id, "PROJECTION_NONDETERMINISTIC",
                                "two renders of the same IR differ"))
    cards_dir = vault / CARDS_DIR
    for item in p["items"]:
        f = cards_dir / ("%s.md" % item["id"])
        if not f.is_file():
            findings.append(Finding(compile_id, "PROJECTION_ITEM_MISSING",
                                    "%s has no card" % item["id"]))
    if cards_dir.is_dir():
        for f in sorted(cards_dir.glob("*.md")):
            text = _read(f)
            rel = "%s/%s" % (CARDS_DIR, f.name)
            meta["cards"] += 1
            if f.stem.startswith("RND-") and f.stem not in p["by_id"]:
                if not re.search(r"^retired:\s*true\s*$", text, re.M):
                    findings.append(Finding(
                        compile_id, "PROJECTION_CARD_ORPHANED",
                        "%s names a record the IR does not hold and is not marked "
                        "retired — a card without a record is a claim without "
                        "evidence" % f.name))
            elif f.stem.startswith("SRC-"):
                sid = f.stem[4:]
                if sid not in p["sources"] or p["sources"][sid].excluded:
                    findings.append(Finding(compile_id, "PROJECTION_CARD_ORPHANED",
                                            "%s names an unbound source" % f.name))
            # generated region must equal a fresh render
            gen_disk, notes = split_card(text)
            want = files1.get(rel)
            if want is not None:
                gen_want, _n = split_card(want)
                fm_disk = text[:text.index(GEN_START)] if GEN_START in text else ""
                fm_want = want[:want.index(GEN_START)] if GEN_START in want else ""
                if gen_disk != gen_want or fm_disk != fm_want:
                    findings.append(Finding(
                        compile_id, "PROJECTION_STALE",
                        "%s: the generated region differs from a fresh render of the "
                        "bound IR — re-render; generated text is never edited" % f.name))
            if notes is None:
                findings.append(Finding(compile_id, "PROJECTION_ANNOTATION_LOST",
                                        "%s has no `%s` section — the place a reader's "
                                        "notes survive is missing" % (f.name, NOTES_HEAD)))
            elif rel in (manifest.get("annotations") or {}) and \
                    NOTES_PLACEHOLDER in notes and notes.strip() == \
                    ("%s\n\n%s" % (NOTES_HEAD, NOTES_PLACEHOLDER)):
                findings.append(Finding(compile_id, "PROJECTION_ANNOTATION_LOST",
                                        "%s: the manifest recorded notes on this card "
                                        "and it now carries only the placeholder"
                                        % f.name))
            # authority vocabulary — generated AND annotation
            m = _AUTHORITY_LINE_RE.search(text)
            if m:
                findings.append(Finding(
                    compile_id, "PROJECTION_AUTHORITY_VOCABULARY",
                    "%s carries %r — a projection never ranks, schedules or "
                    "dispositions; that line would make the vault a backlog"
                    % (f.name, m.group(0).strip())))
            # provenance rows resolve
            if f.stem in p["by_id"]:
                item = p["by_id"][f.stem]
                for pr in (item.get("provenance") or []):
                    if not isinstance(pr, dict) or pr.get("rq"):
                        continue
                    sid = str(pr.get("source_id", ""))
                    b = p["sources"].get(sid)
                    if b is None or b.excluded or not b.verify(compile_id, []):
                        findings.append(Finding(
                            compile_id, "PROJECTION_PROVENANCE_UNRESOLVED",
                            "%s cites %s, which does not resolve to bound bytes"
                            % (f.stem, sid)))
                        continue
                    if b.is_document():
                        rng = rc.parse_msg_range(pr.get("lines")) if pr.get("lines") else None
                        if pr.get("lines") and (rng is None or rng[1] > b.line_total()):
                            findings.append(Finding(
                                compile_id, "PROJECTION_PROVENANCE_UNRESOLVED",
                                "%s cites %s lines %s beyond the document"
                                % (f.stem, sid, pr.get("lines"))))
                    else:
                        spec = pr.get("messages")
                        rng = rc.parse_msg_range(spec) if spec is not None else None
                        if spec is not None and (rng is None or rng[1] > b.message_count()):
                            findings.append(Finding(
                                compile_id, "PROJECTION_PROVENANCE_UNRESOLVED",
                                "%s cites %s msg %s of a %d-message capture"
                                % (f.stem, sid, spec, b.message_count())))
    # canvases: parse, dangling edges, manual objects intact, no authority text
    state, _ = read_json(vault / STATE_NAME) if (vault / STATE_NAME).exists() else ({}, None)
    state = state if isinstance(state, dict) else {}
    ldir = vault / LENSES_DIR
    if ldir.is_dir():
        for f in sorted(ldir.glob("*.canvas")):
            try:
                c = json.loads(_read(f))
            except ValueError:
                findings.append(Finding(compile_id, "PROJECTION_CANVAS_INVALID",
                                        "%s is not valid JSON" % f.name))
                continue
            ids = {n.get("id") for n in c.get("nodes", []) if isinstance(n, dict)}
            for e in c.get("edges", []):
                if not isinstance(e, dict):
                    continue
                if e.get("fromNode") not in ids or e.get("toNode") not in ids:
                    findings.append(Finding(compile_id, "PROJECTION_CANVAS_INVALID",
                                            "%s: edge %s dangles" % (f.name, e.get("id"))))
            for n in c.get("nodes", []):
                if isinstance(n, dict) and n.get("type") == "file":
                    if not (vault / str(n.get("file", ""))).is_file():
                        findings.append(Finding(compile_id, "PROJECTION_CANVAS_INVALID",
                                                "%s: node %s points at a missing file %s"
                                                % (f.name, n.get("id"), n.get("file"))))
                if isinstance(n, dict) and n.get("type") == "text" and \
                        _CANVAS_AUTHORITY_RE.search(str(n.get("text", ""))):
                    findings.append(Finding(compile_id, "PROJECTION_AUTHORITY_VOCABULARY",
                                            "%s: text node %s carries priority/status "
                                            "vocabulary" % (f.name, n.get("id"))))
            rel = "%s/%s" % (LENSES_DIR, f.name)
            entry = (state.get("canvases") or {}).get(rel) or {}
            for mid in entry.get("manual_nodes", []):
                if mid not in ids:
                    findings.append(Finding(compile_id, "PROJECTION_ANNOTATION_LOST",
                                            "%s: manual node %s recorded at last render "
                                            "is gone" % (f.name, mid)))
            # the manifest's record of manual objects (bound at render, not a
            # deletable side file): every id recorded must still be present
            present = {str(o.get("id")) for kind in ("nodes", "edges")
                       for o in c.get(kind, []) if isinstance(o, dict)}
            for mid in ((manifest.get("manual_objects") or {}).get(rel) or {}):
                if mid not in present:
                    findings.append(Finding(compile_id, "PROJECTION_ANNOTATION_LOST",
                                            "%s: manual object %s recorded in the "
                                            "projection manifest is gone" % (f.name, mid)))
    return findings, meta


# --------------------------------------------------------------------- CLI --

def cmd_render(args):
    corpus = corpus_root(args.corpus)
    vault = Path(args.vault)
    if args.write:
        # a vault is a SEPARATE directory: never inside the corpus, never the
        # corpus itself — the projection must not be able to become the truth it
        # projects
        try:
            vault.resolve().relative_to(Path(corpus).resolve())
            print("FAIL: the vault must not live inside the corpus (%s) — a "
                  "projection is a separate derivative, never a corpus file" % corpus)
            return 1
        except ValueError:
            pass
    files, manifest, log, findings = render_files(corpus, args.compile, vault,
                                                  write=args.write)
    # record manual canvas objects so a later verify can prove they survived
    if args.write and manifest is not None:
        sp = vault / STATE_NAME
        state, _ = read_json(sp) if sp.exists() else ({}, None)
        state = state if isinstance(state, dict) else {}
        for rel in list((state.get("canvases") or {})):
            f = vault / rel
            if f.is_file():
                try:
                    c = json.loads(_read(f))
                except ValueError:
                    continue
                state["canvases"][rel]["manual_nodes"] = sorted(
                    n.get("id") for n in c.get("nodes", []) if isinstance(n, dict)
                    and not str(n.get("id", "")).startswith(NODE_PREFIX))
        rc.write_json(sp, state)
    for f in findings:
        print(f)
    for ln in log:
        print("  note: %s" % ln)
    if manifest is None:
        return 1
    print("PROJECTION %s → %s%s" % (args.compile, vault,
                                    "" if args.write else " (dry run — nothing written)"))
    print("IR_SHA256=%s" % manifest["ir_sha256"])
    print("CUT_SHA256=%s" % (manifest["cut_sha256"] or "none"))
    print("FILES=%d  RECORDS=%d  SOURCES=%d  ANNOTATED_CARDS=%d"
          % (len(files), manifest["records"], manifest["sources"],
             len(manifest["annotations"])))
    print("AUTHORITY=none — cards carry no priority, status or disposition")
    return 1 if fails(findings) else 0


def cmd_verify(args):
    corpus = corpus_root(args.corpus)
    findings, meta = verify_vault(corpus, args.compile, Path(args.vault))
    print("PROJECTION_CARDS=%s" % meta.get("cards", 0))
    return report(findings, "projection verify",
                  quiet_pass="the vault is a faithful projection of the bound IR")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    for name in ("render", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--corpus")
        p.add_argument("--compile", required=True)
        p.add_argument("--vault", required=True)
        if name == "render":
            p.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "render":
        return cmd_render(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
