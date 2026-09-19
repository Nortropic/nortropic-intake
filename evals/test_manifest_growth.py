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
    ap.add_argument('--queue-only', action='store_true',
                    help='Only qualify preserved/changed/deleted HEAD review queue during growth')
    ap.add_argument('--recapture-only', action='store_true')
    ap.add_argument('--committed-fixture', type=Path)
    ap.add_argument('--external-capture', type=Path)
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

    def case(name, mutate=None, expected_code=None, fixture=None):
        corpus = args.scratch/name
        shutil.copytree(fixture or args.fixture, corpus, symlinks=True)
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

    if args.recapture_only:
        assert not args.queue_only
        assert args.committed_fixture and args.external_capture
        sys.path.insert(0, str(ROOT/'scripts'))
        from intake_common import transcript_source_sha256
        seeds = {}
        for label, base in [('no-growth', args.committed_fixture), ('mixed-growth', args.fixture)]:
            seed = args.scratch/(label+'-seed')
            shutil.copytree(base, seed, symlinks=True)
            manifest = seed/'_projects/demo/project-manifest.json'
            before = json.loads(manifest.read_text())
            code, out = run(label+'-capture', [sys.executable, '-B', ROOT/'scripts/project_contract.py',
                            '--corpus', seed, 'capture', '--project', 'demo', '--source', 'CONV-002',
                            '--file', args.external_capture, '--adapter', 'data-layer', '--at', '2026-09-19'], seed)
            assert code == 0 and 'VERIFIED_UNCHANGED_AT=2026-09-19' in out, out
            after = json.loads(manifest.read_text())
            assert after['inventory_history'] == before['inventory_history']
            assert after['inventory_revision'] == before['inventory_revision']
            assert after['inventory_sha256'] == before['inventory_sha256']
            for validator in ['project', 'plan', 'context']:
                code, out = run(label+'-'+validator, [sys.executable, '-B',
                                ROOT/('scripts/'+validator+'_contract.py'), '--corpus', seed, 'validate'], seed)
                assert code == 0, out
            seeds[label] = seed
        case('recapture-no-growth', fixture=seeds['no-growth'])
        case('recapture-mixed-growth', fixture=seeds['mixed-growth'])
        def false_measurement(c,m,i):
            alter_json(m, lambda x: x['sources'][1]['revisions'][-1].update(verified_unchanged_source_sha256='0'*64))
        case('recapture-false-hash', false_measurement, 'RND_EVIDENCE_MUTATED', fixture=seeds['no-growth'])
        def raw_and_hash(c,m,i):
            path=c/'_projects/demo/sources/CONV-002/conversation.md'
            path.write_text(path.read_text().replace('Vi bygger ingen egen kö.', 'Vi bygger en egen kö.'))
            whole=hashlib.sha256(path.read_bytes()).hexdigest()
            source=transcript_source_sha256(path.read_text())
            alter_json(m, lambda x: x['sources'][1]['revisions'][-1].update(
                sha256=whole, source_sha256=source, verified_unchanged_source_sha256=source))
        case('recapture-raw-plus-coordinated-hashes', raw_and_hash, 'RND_EVIDENCE_MUTATED', fixture=seeds['no-growth'])
        def old_revision_measurement(c,m,i):
            data=json.loads(m.read_text())
            assert len(data['sources'][0]['revisions'])==2
            measurement={k:v for k,v in data['sources'][1]['revisions'][-1].items() if k.startswith('verified_unchanged_')}
            measurement['verified_unchanged_source_sha256']=transcript_source_sha256(
                (c/'_projects/demo/sources/CONV-001/conversation.md').read_text())
            data['sources'][0]['revisions'][0].update(measurement)
            m.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
        case('recapture-nonlatest-revision', old_revision_measurement, 'RND_EVIDENCE_MUTATED', fixture=seeds['no-growth'])
        case('recapture-extra-manifest-change',
             lambda c,m,i: alter_json(m, lambda x: x.update(title='Unauthorized no-growth title change')),
             'RND_EVIDENCE_MUTATED', fixture=seeds['no-growth'])
        summary=dict(checks=len(results), passed=sum(x['pass_'] for x in results),
                     candidate_rnd_sha256=hashlib.sha256((ROOT/'scripts/rnd_contract.py').read_bytes()).hexdigest(),
                     scope='recapture-only direct candidate validators; external synthetic input; no new normal-hook candidate commit claimed')
        (args.evidence/'result.json').write_text(json.dumps(summary, indent=2)+'\n')
        print(json.dumps(summary, indent=2))
        return

    if args.queue_only:
        seed = args.scratch/'queue-seed'
        shutil.copytree(args.fixture, seed, symlinks=True)
        manifest = seed/'_projects/demo/project-manifest.json'
        growth_manifest = manifest.read_bytes()
        r2 = seed/'_projects/demo/sources/CONV-001/conversation-r2.md'
        growth_raw = r2.read_bytes()
        code, old_manifest = run('queue-baseline-manifest',
                                 ['git', 'show', 'HEAD:_projects/demo/project-manifest.json'], seed)
        assert code == 0
        manifest.write_text(old_manifest)
        r2.unlink()  # only this new isolated copy, returning it to genuine baseline
        queue = seed/'_projects/demo/review-queue.md'
        assert not queue.exists(), 'expected original qualified fixture without queue'
        queue.write_text("---\ntitle: Synthetic queue\ntype: review-queue\nproject: demo\n"
                         "append_only: true\n---\n\n## RQ-001\n\n"
                         "- date: 2026-09-19\n- issue: Synthetic original issue\n"
                         "- affects: CONV-001\n- recommendation: Preserve for later consideration\n"
                         "- owner_judgment_required: no\n")
        code, out = run('queue-baseline-stage', ['git', 'add', '.'], seed)
        assert code == 0, out
        code, out = run('queue-baseline-normal-commit',
                         ['git', 'commit', '-m', 'Synthetic review queue baseline through active ordinary hook'], seed)
        assert code == 0, out
        code, original = run('queue-committed-blob',
                              ['git', 'show', 'HEAD:_projects/demo/review-queue.md'], seed)
        assert code == 0 and original == queue.read_text(), original
        manifest.write_bytes(growth_manifest)
        r2.write_bytes(growth_raw)
        case('queue-preserved-growth', fixture=seed)
        def change_queue(c,m,i):
            path=c/'_projects/demo/review-queue.md'
            path.write_text(path.read_text().replace('Synthetic original issue', 'Rewritten old issue'))
        def delete_queue(c,m,i):
            (c/'_projects/demo/review-queue.md').unlink()
        case('queue-rewritten-growth', change_queue, 'RND_EVIDENCE_MUTATED', fixture=seed)
        case('queue-deleted-growth', delete_queue, 'RND_EVIDENCE_MUTATED', fixture=seed)
        summary = dict(checks=len(results), passed=sum(x['pass_'] for x in results),
                       candidate_rnd_sha256=hashlib.sha256((ROOT/'scripts/rnd_contract.py').read_bytes()).hexdigest(),
                       scope='queue-only direct candidate validators; genuine baseline commit via installed ordinary hook; no candidate normal-hook growth commit claimed')
        (args.evidence/'result.json').write_text(json.dumps(summary, indent=2)+'\n')
        print(json.dumps(summary, indent=2))
        return

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
