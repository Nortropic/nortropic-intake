#!/usr/bin/env python3
"""Bounded regression against a preserved, capture-built historical Git fixture.

The fixture must already contain legitimate uncommitted source growth and an
active ordinary hook. This test copies it for every case; no commit, hook rewrite,
HOME override, installed-skill write, or network operation is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fixture', required=True, type=Path)
    ap.add_argument('--scratch', required=True, type=Path)
    ap.add_argument('--evidence', required=True, type=Path)
    args = ap.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=False)
    args.evidence.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    logs, results = [], []

    def run(label, argv, cwd):
        t = time.monotonic()
        p = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                           capture_output=True, text=True, timeout=30)
        logs.append(dict(label=label, argv=list(map(str, argv)), cwd=str(cwd),
                         exit=p.returncode, stdout=p.stdout, stderr=p.stderr,
                         seconds=round(time.monotonic()-t, 4)))
        (args.evidence/'commands.json').write_text(json.dumps(logs, indent=2)+'\n')
        return p.returncode, p.stdout+p.stderr

    def alter_json(path, mutate):
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

    def case(name, mutate=None, expected_code=None):
        corpus = args.scratch/name
        shutil.copytree(args.fixture, corpus, symlinks=True)
        m = corpus/'_projects/demo/project-manifest.json'
        ir = corpus/'_rnd/historical/rnd-ir.json'
        if mutate:
            mutate(corpus, m, ir)
        # Render mutants so RND_RENDER_STALE cannot be the reason for a red test.
        code, out = run(name+'-render', [sys.executable, '-B', ROOT/'scripts/rnd_contract.py',
                        'render', '--compile', 'historical', '--write', '--corpus', corpus], corpus)
        assert code == 0, out
        for phase in ['before-stage', 'staged']:
            if phase == 'staged':
                code, out = run(name+'-stage', ['git', 'add', '.'], corpus)
                assert code == 0, out
            code, out = run(name+'-'+phase, [sys.executable, '-B', ROOT/'scripts/rnd_contract.py',
                            'validate', '--compile', 'historical', '--corpus', corpus], corpus)
            okay = (code == 0 if expected_code is None else code != 0 and expected_code in out)
            okay = okay and 'RND_RENDER_STALE' not in out
            if expected_code is None:
                okay = okay and 'RND_SOURCE_SET_STALE' in out and 'RND_EVIDENCE_BASE_UNWITNESSED' in out
            results.append(dict(case=name, phase=phase, pass_=okay,
                                expected_code=expected_code, actual_exit=code))
            (args.evidence/'checks.json').write_text(json.dumps(results, indent=2)+'\n')
            assert okay, out
        return corpus

    good = case('valid-growth')
    for validator in ['project', 'plan', 'context']:
        code, out = run('valid-growth-'+validator, [sys.executable, '-B', ROOT/('scripts/'+validator+'_contract.py'),
                         '--corpus', good, 'validate'], good)
        assert code == 0, out
    case('false-revision', lambda c,m,i: alter_json(i, lambda x: x['source_set']['sources'][0].update(revision=9)),
         'RND_SOURCE_NOT_WITNESSED')
    case('false-history-anchor', lambda c,m,i: alter_json(i, lambda x: x['source_set'].update(inventory_sha256='0'*64)),
         'RND_EVIDENCE_MUTATED')
    case('rewritten-inventory-history', lambda c,m,i: alter_json(m, lambda x: x['inventory_history'][0].update(note='forged old note')),
         'RND_EVIDENCE_MUTATED')
    case('rewritten-old-revision', lambda c,m,i: alter_json(m, lambda x: x['sources'][0]['revisions'][0].update(message_count=99)),
         'RND_EVIDENCE_MUTATED')
    def raw_mutation(c,m,i):
        p=c/'_projects/demo/sources/CONV-001/conversation.md'
        p.write_text(p.read_text().replace('Vi bygger ingen egen kö.', 'Vi bygger en egen kö.'))
        # Even a coordinated current-manifest hash edit cannot erase the HEAD witness.
        alter_json(m, lambda x: x['sources'][0]['revisions'][0].update(sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    case('rewritten-old-raw-and-hash', raw_mutation, 'RND_EVIDENCE_MUTATED')
    case('rewritten-source-identity', lambda c,m,i: alter_json(m, lambda x: x['sources'][0].update(conversation_key='chatgpt.com/forged')),
         'RND_EVIDENCE_MUTATED')
    summary = dict(checks=len(results), passed=sum(x['pass_'] for x in results),
                   candidate_rnd_sha256=hashlib.sha256((ROOT/'scripts/rnd_contract.py').read_bytes()).hexdigest(),
                   scope='direct candidate validators only; no normal-hook candidate commit claimed')
    (args.evidence/'result.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
