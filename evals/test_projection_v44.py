#!/usr/bin/env python3
"""v4.4 suite — OBSIDIAN PROJECTION as a contract-governed derivative.

The vault is regenerated from the IR, deterministically; it binds the IR identity;
it preserves annotations; it can never become a source of truth. Every
PROJECTION_* code has a positive check (the control vault verifies clean) and a
mutant check (planting the defect produces the code).

Usage (from the skill root):  python3 evals/test_projection_v44.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_rnd_v4 import mk_corpus, write_json  # noqa: E402
from test_rnd_v44 import v4_ir  # noqa: E402
import obsidian_projection as op  # noqa: E402
import rnd_contract as rc  # noqa: E402

RESULTS = []
MIN_CHECKS = 24
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "obsidian_projection.py"


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS " if condition else "FAIL ", name,
                        ("\n        — %s" % str(detail)[:1200]) if (detail and not condition) else ""))


def run(corpus, *args):
    r = subprocess.run([sys.executable, str(SCRIPT)] + list(args) + ["--corpus", str(corpus)],
                       capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def code(out, c):
    return bool(re.search(r"FAIL\s+\[[^\]]+\]\s+%s\b" % re.escape(c), out))


def tree_hashes(vault):
    import hashlib
    out = {}
    for f in sorted(Path(vault).rglob("*")):
        if f.is_file() and f.name != op.STATE_NAME:
            out[str(f.relative_to(vault))] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def scenario_render_and_verify(tmp):
    corpus = mk_corpus(tmp)
    v4_ir(corpus, "control-ok")
    vault = Path(tmp) / "vault"
    rc_, out = run(corpus, "render", "--compile", "control-ok", "--vault", str(vault), "--write")
    check("P1 render writes a vault with a card per record and a manifest",
          rc_ == 0 and (vault / "kort" / "RND-001.md").is_file()
          and (vault / op.MANIFEST_NAME).is_file() and "RECORDS=7" in out, out)
    first = tree_hashes(vault)
    rc_, out = run(corpus, "render", "--compile", "control-ok", "--vault", str(vault), "--write")
    check("P2 a second render is byte-identical", tree_hashes(vault) == first, out)
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(vault))
    check("P3 the control vault verifies clean", rc_ == 0 and "0 FAIL" in out, out)
    man = json.loads((vault / op.MANIFEST_NAME).read_text())
    check("P4 the manifest binds the IR identity and declares no authority",
          man["ir_sha256"] == rc.sha256_file(corpus / "_rnd/control-ok/rnd-ir.json")
          and man["authority"].startswith("none"), json.dumps(man)[:300])
    # rendering INTO the corpus is refused
    rc_, out = run(corpus, "render", "--compile", "control-ok",
                   "--vault", str(corpus / "_obsidian"), "--write")
    check("P5 a vault inside the corpus is refused — the projection may not become a "
          "corpus file", rc_ == 1 and "must not live inside the corpus" in out, out)
    # canvases parse and serialise like Obsidian
    canvas = vault / "linser" / "truth-trust.canvas"
    text = canvas.read_text(encoding="utf-8")
    c = json.loads(text)
    check("P6 a lens canvas is Obsidian-shaped: tab indent, one node per line, pj: ids",
          text.startswith("{\n\t\"nodes\":[\n\t\t{") and all(
              n["id"].startswith("pj:") for n in c["nodes"]), text[:200])
    # annotations survive: a note on a card, a manual node and a moved node on a canvas
    card = vault / "kort" / "RND-001.md"
    card.write_text(card.read_text(encoding="utf-8") + "Min anteckning om beslutet.\n",
                    encoding="utf-8")
    c["nodes"].append({"id": "manual-note-1", "type": "text", "x": 5000, "y": 0,
                       "width": 300, "height": 100, "text": "läsarens egen kommentar"})
    c["nodes"][0]["x"] = 9999
    canvas.write_text(op.dump_canvas(c) + "\n", encoding="utf-8")
    rc_, out = run(corpus, "render", "--compile", "control-ok", "--vault", str(vault), "--write")
    after = json.loads(canvas.read_text(encoding="utf-8"))
    check("P7 the card note survives a re-render",
          "Min anteckning om beslutet." in card.read_text(encoding="utf-8")
          and "PROJECTION_ANNOTATION_LOST" not in out, out)
    check("P8 the manual canvas node and the moved position survive a re-render",
          any(n["id"] == "manual-note-1" for n in after["nodes"])
          and after["nodes"][0]["x"] == 9999, json.dumps(after)[:400])
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(vault))
    check("P9 an annotated vault still verifies clean", rc_ == 0, out)
    man = json.loads((vault / op.MANIFEST_NAME).read_text())
    check("P10 the manifest records which cards carry notes",
          "kort/RND-001.md" in man["annotations"], json.dumps(man["annotations"]))
    # a manually deleted node is not recreated
    c2 = json.loads(canvas.read_text(encoding="utf-8"))
    c2["nodes"] = [n for n in c2["nodes"] if n["id"] != "pj:card:RND-001"]
    c2["edges"] = [e for e in c2["edges"] if "RND-001" not in e["id"]]
    canvas.write_text(op.dump_canvas(c2) + "\n", encoding="utf-8")
    run(corpus, "render", "--compile", "control-ok", "--vault", str(vault), "--write")
    c3 = json.loads(canvas.read_text(encoding="utf-8"))
    check("P11 a manually deleted generated node is not recreated",
          not any(n["id"] == "pj:card:RND-001" for n in c3["nodes"]), json.dumps(c3)[:300])

    # ---- mutants -------------------------------------------------------------
    def fresh():
        v = Path(tmp) / ("v-%d" % len(RESULTS))
        run(corpus, "render", "--compile", "control-ok", "--vault", str(v), "--write")
        return v

    v = fresh()
    (v / "kort" / "RND-003.md").unlink()
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M1 a record without a card: PROJECTION_ITEM_MISSING",
          rc_ == 1 and code(out, "PROJECTION_ITEM_MISSING"), out)

    v = fresh()
    (v / "kort" / "RND-099.md").write_text(
        "---\nid: RND-099\nkind: OPTION\n---\n%s\n# RND-099\n%s\n\n## Anteckningar\n"
        % (op.GEN_START, op.GEN_END), encoding="utf-8")
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M2 a card without a record: PROJECTION_CARD_ORPHANED",
          code(out, "PROJECTION_CARD_ORPHANED"), out)

    v = fresh()
    card = v / "kort" / "RND-002.md"
    card.write_text(card.read_text(encoding="utf-8") + "priority: high\n", encoding="utf-8")
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M3 'priority: high' in a note: PROJECTION_AUTHORITY_VOCABULARY",
          code(out, "PROJECTION_AUTHORITY_VOCABULARY"), out)
    card.write_text(card.read_text(encoding="utf-8").replace("priority: high\n", "status: klar\n"),
                    encoding="utf-8")
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M3b 'status:' is refused too — a vault is not a backlog",
          code(out, "PROJECTION_AUTHORITY_VOCABULARY"), out)

    v = fresh()
    card = v / "kort" / "RND-002.md"
    text = card.read_text(encoding="utf-8")
    card.write_text(text.replace("**Claim:**", "**Claim (edited by hand):**"), encoding="utf-8")
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M4 an edited generated region: PROJECTION_STALE (generated text is never edited)",
          code(out, "PROJECTION_STALE"), out)

    v = fresh()
    ir_path = corpus / "_rnd/control-ok/rnd-ir.json"
    ir = json.loads(ir_path.read_text())
    ir["items"][0]["claim"] += " (IR changed after render)"
    ir["items"][0]["fingerprint"] = rc.record_fingerprint(ir["items"][0])
    write_json(ir_path, ir)
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M5 an IR that moved after render: PROJECTION_STALE on the manifest binding",
          code(out, "PROJECTION_STALE") and "re-render" in out, out)
    ir["items"][0]["claim"] = ir["items"][0]["claim"].replace(" (IR changed after render)", "")
    ir["items"][0]["fingerprint"] = rc.record_fingerprint(ir["items"][0])
    write_json(ir_path, ir)

    v = fresh()
    (v / op.MANIFEST_NAME).unlink()
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M6 no manifest: PROJECTION_MANIFEST_MISSING", code(out, "PROJECTION_MANIFEST_MISSING"),
          out)

    v = fresh()
    canvas = v / "linser" / "truth-trust.canvas"
    c = json.loads(canvas.read_text(encoding="utf-8"))
    c["edges"].append({"id": "dangling", "fromNode": "pj:card:RND-001", "toNode": "nowhere"})
    canvas.write_text(op.dump_canvas(c) + "\n", encoding="utf-8")
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M7 a dangling canvas edge: PROJECTION_CANVAS_INVALID",
          code(out, "PROJECTION_CANVAS_INVALID"), out)
    canvas.write_text("{not json", encoding="utf-8")
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M7b an unparsable canvas: PROJECTION_CANVAS_INVALID",
          code(out, "PROJECTION_CANVAS_INVALID"), out)

    v = fresh()
    card = v / "kort" / "RND-004.md"
    text = card.read_text(encoding="utf-8")
    card.write_text(text[:text.index("## Anteckningar")], encoding="utf-8")
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M8 a card whose notes section is gone: PROJECTION_ANNOTATION_LOST",
          code(out, "PROJECTION_ANNOTATION_LOST"), out)

    v = fresh()
    canvas = v / "linser" / "truth-trust.canvas"
    c = json.loads(canvas.read_text(encoding="utf-8"))
    c["nodes"].append({"id": "manual-2", "type": "text", "x": 1, "y": 1, "width": 10,
                       "height": 10, "text": "kept?"})
    canvas.write_text(op.dump_canvas(c) + "\n", encoding="utf-8")
    run(corpus, "render", "--compile", "control-ok", "--vault", str(v), "--write")
    c = json.loads(canvas.read_text(encoding="utf-8"))
    c["nodes"] = [n for n in c["nodes"] if n["id"] != "manual-2"]
    canvas.write_text(op.dump_canvas(c) + "\n", encoding="utf-8")
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M9 a manual canvas node recorded at last render that vanished: "
          "PROJECTION_ANNOTATION_LOST", code(out, "PROJECTION_ANNOTATION_LOST"), out)

    v = fresh()
    src = corpus / "_projects/demo/sources/CONV-002/conversation.md"
    keep = src.read_bytes()
    src.write_bytes(keep + b"\nmoved\n")
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("M10 a source whose bytes moved: PROJECTION_PROVENANCE_UNRESOLVED",
          code(out, "PROJECTION_PROVENANCE_UNRESOLVED"), out)
    src.write_bytes(keep)

    # F-14: text between the end marker and the notes head is the reader's — preserved
    v = fresh()
    card = v / "kort" / "RND-002.md"
    text = card.read_text(encoding="utf-8")
    text = text.replace(op.GEN_END + "\n", op.GEN_END + "\nEn rad i mellanrummet.\n", 1)
    card.write_text(text, encoding="utf-8")
    run(corpus, "render", "--compile", "control-ok", "--vault", str(v), "--write")
    check("F-14 prose between the generated region and the notes head survives a re-render",
          "En rad i mellanrummet." in card.read_text(encoding="utf-8"), card.read_text())
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("F-14 and the vault still verifies (it is annotation)", rc_ == 0, out)
    # F-15: manual objects are recorded in the bound manifest, not only the state file
    v = fresh()
    canvas = v / "linser" / "truth-trust.canvas"
    c = json.loads(canvas.read_text(encoding="utf-8"))
    c["nodes"].append({"id": "manual-3", "type": "text", "x": 1, "y": 1, "width": 10,
                       "height": 10, "text": "kept?"})
    canvas.write_text(op.dump_canvas(c) + "\n", encoding="utf-8")
    run(corpus, "render", "--compile", "control-ok", "--vault", str(v), "--write")
    man = json.loads((v / op.MANIFEST_NAME).read_text())
    check("F-15 the manifest records the manual object",
          "manual-3" in (man.get("manual_objects") or {}).get("linser/truth-trust.canvas", {}),
          json.dumps(man.get("manual_objects")))
    c = json.loads(canvas.read_text(encoding="utf-8"))
    c["nodes"] = [n for n in c["nodes"] if n["id"] != "manual-3"]
    canvas.write_text(op.dump_canvas(c) + "\n", encoding="utf-8")
    (v / op.STATE_NAME).unlink()
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(v))
    check("F-15 deleting the manual node AND the state file is still PROJECTION_ANNOTATION_LOST",
          code(out, "PROJECTION_ANNOTATION_LOST"), out)
    # F-16: verify refuses a vault inside the corpus
    inside = corpus / "_vault"
    shutil.copytree(fresh(), inside)
    rc_, out = run(corpus, "verify", "--compile", "control-ok", "--vault", str(inside))
    check("F-16 verify refuses a vault inside the corpus", rc_ == 1 and "inside the corpus" in out,
          out)
    shutil.rmtree(inside)

    # nondeterminism is only reachable by a broken renderer — prove the detector
    # fires by making the renderer nondeterministic in-process
    v = fresh()
    original = op.render_card

    def noisy(ir, item, lenses_of, sources, _n=[0]):
        _n[0] += 1
        return original(ir, item, lenses_of, sources).replace(
            "**Claim:**", "**Claim %d:**" % _n[0])
    op.render_card = noisy
    try:
        findings, _meta = op.verify_vault(corpus, "control-ok", v)
    finally:
        op.render_card = original
    check("M11 a renderer whose two passes differ: PROJECTION_NONDETERMINISTIC",
          any(f.code == "PROJECTION_NONDETERMINISTIC" for f in findings),
          "; ".join(f.code for f in findings))


def main():
    tmp = tempfile.mkdtemp(prefix="projection-v44-")
    try:
        scenario_render_and_verify(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    passed = sum(1 for r in RESULTS if r[1])
    failed = [r for r in RESULTS if not r[1]]
    print("%d/%d checks passed" % (passed, len(RESULTS)))
    if len(RESULTS) < MIN_CHECKS:
        print("FAIL: only %d checks ran (floor %d)" % (len(RESULTS), MIN_CHECKS))
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
