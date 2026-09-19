#!/usr/bin/env python3
"""Synthetic regressions for the measured compile-switch annotation defect."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "evals")]
from test_rnd_v4 import mk_corpus, write_json
from test_rnd_v44 import v4_ir
import obsidian_projection as op
import rnd_contract as rc

SCRIPT = Path(os.environ.get("INTAKE_PROJECTION_SCRIPT", ROOT / "scripts/obsidian_projection.py"))


def hashes(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}


class IdentityTransition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="projection-identity-")
        self.addCleanup(self.tmp.cleanup)
        self.corpus = mk_corpus(self.tmp.name)
        self.a = v4_ir(self.corpus, "compile-a")
        self.ir = json.loads(self.a.read_text())
        self.vault = Path(self.tmp.name) / "vault"
        self.assertEqual(self.run_projection("render", "compile-a").returncode, 0)
        self.card = self.vault / "kort/RND-001.md"
        self.card.write_text(self.card.read_text() + "NOTE BELONGS TO ORIGINAL DECISION\n")
        self.canvas = self.vault / "linser/truth-trust.canvas"
        canvas = json.loads(self.canvas.read_text())
        canvas["nodes"][0]["x"] = 9876
        canvas["nodes"].append({"id": "manual", "type": "text", "text": "reader note",
                                "x": 0, "y": 0, "width": 200, "height": 100})
        canvas["nodes"] = [n for n in canvas["nodes"] if n["id"] != "pj:card:RND-004"]
        canvas["edges"] = [e for e in canvas["edges"]
                            if e["fromNode"] != "pj:card:RND-004" and e["toNode"] != "pj:card:RND-004"]
        self.canvas.write_text(op.dump_canvas(canvas) + "\n")
        self.assertEqual(self.run_projection("render", "compile-a").returncode, 0)

    def run_projection(self, command, cid):
        args = [sys.executable, "-B", str(SCRIPT), command, "--corpus", str(self.corpus),
                "--compile", cid, "--vault", str(self.vault)]
        if command == "render":
            args.append("--write")
        return subprocess.run(args, capture_output=True, text=True, timeout=30)

    def install(self, ir):
        path = self.corpus / "_rnd/compile-b/rnd-ir.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, ir)
        for command in ("render", "validate"):
            args = [sys.executable, "-B", str(ROOT / "scripts/rnd_contract.py"), command,
                    "--corpus", str(self.corpus), "--compile", "compile-b"]
            if command == "render":
                args.append("--write")
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def same(self):
        ir = copy.deepcopy(self.ir)
        ir["compile_id"] = "compile-b"
        ir["lineage_baseline"] = {"compile": "compile-a", "ir_sha256": rc.sha256_file(self.a)}
        for item in ir["items"]:
            item["lineage"] = [{"id": item["id"], "relation": "SAME"}]
        return ir

    def refused_unchanged(self, cid="compile-b"):
        before = hashes(self.vault)
        result = self.run_projection("render", cid)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("PROJECTION_IDENTITY_CONFLICT", result.stdout)
        self.assertEqual(hashes(self.vault), before, "refusal must precede every write")

    def test_reused_id_different_valid_record(self):
        ir = copy.deepcopy(self.ir)
        ir["compile_id"] = "compile-b"
        remap = {"RND-001": "RND-002", "RND-002": "RND-001"}
        def swap(value):
            if isinstance(value, str):
                return remap.get(value, value)
            if isinstance(value, list):
                return [swap(v) for v in value]
            if isinstance(value, dict):
                return {k: swap(v) for k, v in value.items()}
            return value
        ir = swap(ir)
        for item in ir["items"]:
            item["fingerprint"] = rc.record_fingerprint(item)
        self.install(ir)
        self.refused_unchanged()
        self.assertEqual(self.run_projection("verify", "compile-a").returncode, 0)

    def test_explicit_same_lineage_preserves_manual_surfaces(self):
        self.install(self.same())
        notes = op.split_card(self.card.read_text())[1]
        canvas = self.canvas.read_bytes()
        result = self.run_projection("render", "compile-b")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(op.split_card(self.card.read_text())[1], notes)
        self.assertEqual(self.canvas.read_bytes(), canvas)
        self.assertEqual(self.run_projection("verify", "compile-b").returncode, 0)
        snapshot = hashes(self.vault)
        self.assertEqual(self.run_projection("render", "compile-b").returncode, 0)
        self.assertEqual(hashes(self.vault), snapshot)

    def test_missing_lineage_is_not_permission(self):
        ir = copy.deepcopy(self.ir)
        ir["compile_id"] = "compile-b"
        self.install(ir)
        self.refused_unchanged()

    def test_missing_manifest_refused_before_writing(self):
        (self.vault / op.MANIFEST_NAME).unlink()
        self.refused_unchanged("compile-a")

    def test_forged_old_fingerprint_refused(self):
        self.card.write_text(self.card.read_text().replace(self.ir["items"][0]["fingerprint"], "0" * 64))
        self.refused_unchanged("compile-a")

    def test_changed_previous_ir_refused(self):
        self.a.write_text(self.a.read_text() + "\n")
        self.refused_unchanged("compile-a")

    def test_missing_old_card_cannot_transfer_canvas_state(self):
        self.install(self.same())
        self.card.unlink()
        self.refused_unchanged()

    def test_false_lineage_binding_refused(self):
        self.install(self.same())
        path = self.corpus / "_rnd/compile-b/rnd-ir.json"
        ir = json.loads(path.read_text())
        ir["lineage_baseline"]["ir_sha256"] = "0" * 64
        write_json(path, ir)
        self.refused_unchanged()

    def test_false_new_fingerprint_refused(self):
        self.install(self.same())
        path = self.corpus / "_rnd/compile-b/rnd-ir.json"
        ir = json.loads(path.read_text())
        ir["items"][0]["fingerprint"] = "0" * 64
        write_json(path, ir)
        self.refused_unchanged()


if __name__ == "__main__":
    unittest.main()
