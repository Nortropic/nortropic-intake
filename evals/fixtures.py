#!/usr/bin/env python3
"""Fixture builders shared by the context/plan/acceptance suites.

Every fixture is written to disk as real files and run through the real validators —
no mocks anywhere in this test tree. Builders take overrides so a test can mutate one
field and assert that exactly that mutation is what fails.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PLAN_CONTRACT = SCRIPTS / "plan_contract.py"
CONTEXT_CONTRACT = SCRIPTS / "context_contract.py"

CONTROL_SLUG = "control-ok"


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body_of(text):
    """Everything after the frontmatter — the content identity."""
    if not text.startswith("---"):
        return text
    end = text.index("\n---", 3)
    rest = text[end + 4:]
    return rest[1:] if rest.startswith("\n") else rest


def frontmatter(fields):
    lines = ["---"]
    for k, v in fields.items():
        if v is None:
            continue
        lines.append("%s: %s" % (k, v))
    lines.append("---")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ brief --

BRIEF_BODY = """
# Idea brief: {title}

## 1. Summary
A durable context pipeline for the operator product, planned against current repo truth.

## 2. Context you need
The operator product renders fixture data today. Current canonical repository authority
beats all intake artifacts; within the intake package this brief wins over rationale and
transcript.

## 3. Destination (goal, not implementation plan)
An operator can see real backend state, or an explicit UNKNOWN.

## 4. Decisions already made (do not relitigate silently)
- D1. Read-first slice over the real backend — because synthesized completeness is a lie
  the operator cannot detect (← msg 12).
- D2. Snapshot wins over event streams — because a client-side fold is not authority
  (← msg 18–20).
- D3. Roles separate advisory repos from write targets — because authority differs per
  repository (← msg 31, SRC-002).

REJECTED (each explicit in the source):
- R1. A second task ledger inside the product — because two ledgers means two truths
  (← msg 22).
- R2. Polling the canonical system directly from product code — because it would make
  the product a writer to system state (← msg 27).

## 5. Acceptance criteria (v1)
- AC1. WHEN backend state is unavailable, THE UI SHALL render UNKNOWN rather than a
  synthesized value (← msg 12).
- AC2. WHEN a snapshot and an event stream disagree, THE system SHALL prefer the
  snapshot (← msg 18–20).
- AC3. WHEN an advisory-only repository is a plan target, THE plan SHALL NOT author
  changes there (← msg 31).

## 6. Constraints & implementation notes
Invariants this must not violate: Nortropic's trust layer — constitution & rulebook.

## 7. Out of scope (v1)
Anything in the canonical system repository beyond reading it.

## 8. Verification (how we know it works)
An operator screenshot plus the backend record it claims to show.

## 9. Open questions (interview the owner before planning)
- Q1. Which backend field is authoritative for the header state? (← msg 33)
- Q2. Should the advisory repo be readable at runtime at all? (← msg 37)
- Q3. Do we ship the read-first slice before the write path exists? (← msg 41)

## 10. Process for this brief
1. Clarify. 2. Plan. 3. Approve exact candidate. 4. Implement fresh. 5. Review.
"""


def brief(slug, title="Durable context pipeline", status="clarified", **extra):
    fields = {
        "title": '"%s"' % title,
        "type": "idea-brief",
        "status": status,
        "slug": slug,
        "owner": "Johnny (Nortropic)",
        "created": "2026-08-25",
        "source_conversation": "%s-full-chat.md" % slug,
        "design_rationale": "%s-design-rationale.md" % slug,
        "intended_repo_path": "%s/idea-%s.md" % (slug, slug),
        # Q1/Q2 are answered by CLAR-002/CLAR-001; Q3 is deliberately deferred, so
        # every open question has a disposition and none can silently vanish.
        "open_questions_deferred": "[Q3]",
    }
    fields.update(extra)
    return frontmatter(fields) + BRIEF_BODY.format(title=title)


# ------------------------------------------------------------ plan bodies --

PLAN_BODY = """
# {kind}: {title} (v{version})

## 1. Authority boundary
Preserves owner-approved execution intent and its provenance. Does not override the
constitution, the rulebook, frozen gates, current published production truth, or a later
owner-approved transition. Repository truth wins on conflict; the divergence is reported.
Not a runtime, not a second source of truth, not an execution-state ledger.

## 2. Scope boundaries
In scope: the three slices in §3, against the operator product only. Out of scope: any
write to the canonical system repository, which is advisory-only for this plan, and the
neighbouring workstreams.

## 3. Execution order

### S1 — Read-first backend adapter
Implements D1. Covers AC1. Render UNKNOWN when the backend is unreachable; never a
placeholder value. No writes anywhere.

### S2 — Snapshot precedence in the fold
Implements D2. Covers AC2. When snapshot and stream disagree the snapshot wins and the
disagreement is surfaced to the operator.

### S3 — Target-role enforcement in the plan runner
Implements D3 and CLAR-001. Covers AC3. Advisory-only targets are read, never written.
Owner-only transition: publishing the slice to production.

## 4. Decisions carried into execution
- D1 read-first — carried unchanged.
- D2 snapshot precedence — carried unchanged.
- D3 role separation — carried, refined by CLAR-001.
- Adapter retries are capped at three attempts with no backoff jitter.

## 5. Deferred work
The write path, until the read-first slice is observed in production.

## 6. Rejected paths (must not be re-adopted)
R1 stays rejected: a second task ledger would create two truths.
R2 stays rejected: product code must never poll canonical system state directly.

## 7. Owner-only transitions
Publishing to production; reopening this plan; changing the advisory-only role.

## 8. Stop conditions
PLAN_IDENTITY_UNAVAILABLE; any conflict between plan and current repository truth.

## 9. Acceptance criteria
AC1, AC2 and AC3 all demonstrated end to end against the real backend, with evidence an
independent reviewer can confirm from the record alone.

## 10. Current / next slice semantics
Computed by reconciling this plan against each target repository. Stored pointers are
hints; repository evidence overrides them.

## 11. Precedence & coherence patches
CLAR-001 refines D3: advisory-only means read-only, enforced by the runner.

## Provenance
Plan Mode output, reviewed against the coherence report before approval.
"""


def candidate(slug, version=1, title="Durable context pipeline", body=None, **overrides):
    fields = {
        "title": '"%s — plan candidate v%d"' % (title, version),
        "type": "plan-candidate",
        "status": "candidate",
        "slug": slug,
        "owner": "Johnny (Nortropic)",
        "created": "2026-08-25",
        "plan_version": str(version),
        "source_brief": "idea-%s.md" % slug,
        "source_brief_sha256": "0" * 64,
        "canonical_execution_repo": "unknown",
        "plan_source": "claude-code-plan-mode",
        "fidelity": "full",
    }
    for k, v in overrides.items():
        if v is None:
            fields.pop(k, None)
        else:
            fields[k] = v
    text = body if body is not None else PLAN_BODY.format(
        kind="Plan candidate", title=title, version=version)
    return frontmatter(fields) + text


def approved_plan(slug, version=1, title="Durable context pipeline", body=None,
                  candidate_name=None, candidate_sha=None, **overrides):
    text = body if body is not None else PLAN_BODY.format(
        kind="Approved plan", title=title, version=version)
    fields = {
        "title": '"%s — approved plan v%d"' % (title, version),
        "type": "approved-plan",
        "status": "approved",
        "approval_state": "approved",
        "slug": slug,
        "owner": "Johnny (Nortropic)",
        "approved_at": "2026-08-25",
        "approved_by": "Johnny (Nortropic)",
        "approval_evidence": '"owner approved candidate sha in session 2026-08-25"',
        "plan_version": str(version),
        "source_brief": "idea-%s.md" % slug,
        "source_brief_sha256": "0" * 64,
        "canonical_execution_repo": "unknown",
        "plan_source": "claude-code-plan-mode",
        "fidelity": "full",
        "authority": "owner-approved-execution-intent",
        "plan_content_sha256": sha256_text(text),
        "approved_candidate": candidate_name or ("%s-plan-candidate.md" % slug),
        "approved_candidate_sha256": candidate_sha or ("0" * 64),
    }
    for k, v in overrides.items():
        if v is None:
            fields.pop(k, None)
        else:
            fields[k] = v
    return frontmatter(fields) + text


# ---------------------------------------------------------- other artifacts --

def manifest(slug, folder, targets=None, extra_sources=None, **overrides):
    sources = []
    n = 0
    for name, kind in ((("%s-full-chat.md" % slug), "chat-transcript"),
                       (("%s-design-rationale.md" % slug), "design-rationale"),
                       (("%s-owner-clarifications.md" % slug), "owner-clarifications")):
        path = Path(folder) / name
        if not path.exists():
            continue
        n += 1
        entry = {"source_id": "SRC-%03d" % n, "kind": kind, "name": name, "path": name,
                 "sha256": sha256_file(path), "capture_status": "captured",
                 "load_bearing": True}
        if kind == "chat-transcript":
            entry["fidelity"] = "full"
        sources.append(entry)
    for extra in (extra_sources or []):
        n += 1
        entry = {"source_id": "SRC-%03d" % n}
        entry.update(extra)
        sources.append(entry)
    data = {
        "manifest_version": 1,
        "slug": slug,
        "execution_targets": targets if targets is not None else
            [{"repo": "operator-product", "role": "operator-product"}],
        "sources": sources,
    }
    data.update(overrides)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


CLARIFICATIONS_BODY = """
# Owner clarifications: {title}

## CLAR-001
- date: 2026-08-25
- resolves: Q2
- affects: D3, AC3
- question: Should the advisory repository be readable at runtime, or reference-only?
- owner_answer: Reference-only. The runner may read it while planning, but nothing in
  the product may depend on it at runtime, and nothing may ever write to it.

## CLAR-002
- date: 2026-08-25
- resolves: Q1
- affects: AC1
- question: Which backend field is authoritative for the header state?
- owner_answer: The snapshot's `state` field. If it is absent the header renders UNKNOWN.
"""


def clarifications(slug, title="Durable context pipeline", body=None, **overrides):
    fields = {
        "title": '"%s — owner clarifications"' % title,
        "type": "owner-clarifications",
        "slug": slug,
        "owner": "Johnny (Nortropic)",
        "authority": "owner-delta",
        "append_only": "true",
    }
    for k, v in overrides.items():
        if v is None:
            fields.pop(k, None)
        else:
            fields[k] = v
    return frontmatter(fields) + (body if body is not None
                                  else CLARIFICATIONS_BODY.format(title=title))


TRANSCRIPT = """# Transkript

**Antal meddelanden:** 3

## Meddelande 1 — Johnny (användare)
We should render real backend state, or UNKNOWN. Never a made-up value.

---

## Meddelande 2 — ChatGPT (assistent)
Snapshot should win over the event fold.

---

## Meddelande 3 — Johnny (användare)
And the canonical system repo is advisory only — we read it, never write it.
"""


# ------------------------------------------------------------- corpus build --

def add_control(corpus):
    """A package that must ALWAYS pass, in every fixture.

    Without it, a `must fail` assertion is satisfied by a validator that rejects
    everything — it only means something alongside "and a valid package still passes,
    in the same run".
    """
    folder = Path(corpus) / CONTROL_SLUG
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ("idea-%s.md" % CONTROL_SLUG)).write_text(
        brief(CONTROL_SLUG, status="clarified"), encoding="utf-8")
    (folder / ("%s-design-rationale.md" % CONTROL_SLUG)).write_text(
        "# rationale\n", encoding="utf-8")
    (folder / ("%s-full-chat.md" % CONTROL_SLUG)).write_text(TRANSCRIPT, encoding="utf-8")
    return corpus


def build_package(tmp, slug="demo-idea", status="clarified", with_clarifications=True,
                  with_manifest=True, with_candidate=False, with_plan=False,
                  brief_extra=None, manifest_kw=None, candidate_kw=None, plan_kw=None,
                  files=None, target_repos=None):
    """Write a complete package to disk and return (corpus, folder).

    `with_plan` promotes through the REAL `approve` command rather than hand-building
    approved bytes — so the happy-path fixture exercises the production promotion path
    and cannot accidentally diverge from it.

    `target_repos` is [(role, path)] of real git repositories; they become the
    manifest's and the plan's execution_targets.
    """
    corpus = Path(tmp) / "corpus"
    folder = corpus / slug
    folder.mkdir(parents=True, exist_ok=True)
    add_control(corpus)

    (folder / ("%s-full-chat.md" % slug)).write_text(TRANSCRIPT, encoding="utf-8")
    (folder / ("%s-design-rationale.md" % slug)).write_text(
        "# rationale\n\nWhy the design took its shape.\n", encoding="utf-8")
    if with_clarifications:
        (folder / ("%s-owner-clarifications.md" % slug)).write_text(
            clarifications(slug), encoding="utf-8")

    targets = list(target_repos or [])
    extra = dict(brief_extra or {})
    cand_kw = dict(candidate_kw or {})
    if targets:
        cand_kw.setdefault("execution_targets",
                           "[%s]" % ", ".join("%s=%s" % (p, role) for role, p in targets))
        cand_kw.setdefault("canonical_execution_repo", str(targets[0][1]))

    cand_name = "%s-plan-candidate.md" % slug
    cand_path = folder / cand_name
    if with_candidate or with_plan:
        cand_path.write_text(candidate(slug, **cand_kw), encoding="utf-8")

    # brief must exist before `approve` runs (it validates against it)
    (folder / ("idea-%s.md" % slug)).write_text(
        brief(slug, status="clarified", **{k: v for k, v in extra.items()
                                           if not k.startswith("approved_plan")}),
        encoding="utf-8")

    if with_plan:
        # The corpus is a real git repository and the candidate is committed before
        # approval — that is the contract's anchor, so the happy-path fixture must
        # exercise it rather than route around it.
        git_commit_corpus(corpus, "candidate for %s" % slug)
        kw = dict(plan_kw or {})
        if kw.pop("handbuilt", False):
            kw.setdefault("candidate_name", cand_name)
            kw.setdefault("candidate_sha", sha256_file(cand_path))
            plan_text = approved_plan(slug, **kw)
            plan_name = "%s-approved-plan.md" % slug
            (folder / plan_name).write_text(plan_text, encoding="utf-8")
        else:
            rc, out = plan(["approve", "--slug", slug,
                            "--candidate-sha", sha256_file(cand_path),
                            "--approved-by", "Johnny (Nortropic)",
                            "--approved-at", "2026-08-25",
                            "--evidence", "owner approved this candidate sha"], corpus)
            if rc != 0:
                raise AssertionError("fixture approve failed:\n%s" % out)
            plan_name = "%s-approved-plan.md" % slug
        extra.setdefault("approved_plan", plan_name)
        extra.setdefault("approved_plan_sha256", sha256_file(folder / plan_name))
        extra.setdefault("plan_version", "1")
        extra.setdefault("plan_approved_at", "2026-08-25")

    if with_manifest:
        mkw = dict(manifest_kw or {})
        if targets and "targets" not in mkw:
            mkw["targets"] = [{"repo": str(p), "role": role} for role, p in targets]
        (folder / ("%s-context-manifest.json" % slug)).write_text(
            manifest(slug, folder, **mkw), encoding="utf-8")

    for name, text in (files or {}).items():
        (folder / name).write_text(text, encoding="utf-8")

    (folder / ("idea-%s.md" % slug)).write_text(
        brief(slug, status=status, **extra), encoding="utf-8")
    return corpus, folder


def rebind(folder, slug, plan_name=None):
    """Bind (or re-bind) the brief to its approved plan — the Phase 4 step by hand."""
    import re
    brief_path = folder / ("idea-%s.md" % slug)
    text = brief_path.read_text(encoding="utf-8")
    if plan_name is None:
        m = re.search(r"^approved_plan: (\S+)$", text, re.M)
        plan_name = m.group(1) if m else ("%s-approved-plan.md" % slug)
    if not (folder / plan_name).exists():
        return
    sha = sha256_file(folder / plan_name)
    if re.search(r"^approved_plan: ", text, re.M):
        text = re.sub(r"^approved_plan: .*$", "approved_plan: %s" % plan_name,
                      text, flags=re.M)
        text = re.sub(r"^approved_plan_sha256: .*$", "approved_plan_sha256: %s" % sha,
                      text, flags=re.M)
    else:
        text = re.sub(
            r"^(intended_repo_path: .*)$",
            r"\1\napproved_plan: %s\napproved_plan_sha256: %s\nplan_version: 1\n"
            r"plan_approved_at: 2026-08-25" % (plan_name, sha),
            text, count=1, flags=re.M)
    brief_path.write_text(text, encoding="utf-8")


GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")


def git_commit_corpus(corpus, message="fixture"):
    """Make the corpus a real git repo and commit everything currently in it.

    The approval contract anchors candidate bytes against git history, so fixtures
    need real history — not a stand-in for it.
    """
    corpus = Path(corpus)
    if not (corpus / ".git").exists():
        subprocess.run(["git", "init", "-q", "-b", "main", str(corpus)],
                       check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(corpus), "add", "-A"], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(corpus), "commit", "-q", "--allow-empty",
                    "-m", message], check=True, env=GIT_ENV)


def git_repo(path, files=None, branch="main"):
    """A real git repository — target-repo evidence is never mocked."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")
    subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True, env=env)
    for name, text in (files or {"README.md": "# repo\n"}).items():
        (path / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "init"], check=True, env=env)
    head = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                          capture_output=True, text=True, env=env).stdout.strip()
    return path, head


def run(script, argv, corpus=None):
    cmd = [sys.executable, str(script)]
    if corpus:
        cmd += ["--corpus", str(corpus)]
    cmd += argv
    env = dict(os.environ)
    env.pop("NORTROPIC_INTAKE_CORPUS", None)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout + proc.stderr


def plan(argv, corpus=None):
    return run(PLAN_CONTRACT, argv, corpus)


def context(argv, corpus=None):
    return run(CONTEXT_CONTRACT, argv, corpus)
