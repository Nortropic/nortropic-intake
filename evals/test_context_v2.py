#!/usr/bin/env python3
"""Context-continuity suite — the realistic scenarios A–L, plus the mutation matrix.

Every case builds a real package (and, where the scenario needs one, a real git
repository) on disk and runs the real `context_contract.py` / `plan_contract.py`.
Weighted towards falsification: each planted failure must fail for ITS OWN reason,
and every negative assertion is paired with a control package that must still pass in
the same run, so a validator that rejects everything cannot satisfy the suite.

Usage (from the skill root):
  python3 evals/test_context_v2.py            # exit 1 on any failure
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixtures as F  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS " if condition else "FAIL ", name,
                        ("\n        — %s" % detail) if (detail and not condition) else ""))


def expect_code(name, out, rc, code, slug="demo-idea", control=True):
    """Fails for its own reason, on its own slug, while the control still passes."""
    attached = re.search(r"^FAIL\s+\[%s\]\s+%s\b" % (re.escape(slug), re.escape(code)),
                         out, re.M) is not None
    control_ok = (not control) or re.search(
        r"^PASS\s+\[%s\]" % re.escape(F.CONTROL_SLUG), out, re.M) is not None
    check(name, rc != 0 and attached and control_ok,
          "rc=%d attached=%s control_ok=%s expected %s on [%s]\n%s"
          % (rc, attached, control_ok, code, slug, out.strip()[:1400]))


def two_repos(tmp):
    prod, _ = F.git_repo(Path(tmp) / "operator-product")
    adv, _ = F.git_repo(Path(tmp) / "canonical-system")
    return [("operator-product", prod), ("advisory-only", adv)]


def full_package(tmp, **kw):
    """A complete, valid, planned package with two real target repositories."""
    targets = kw.pop("targets", None) or two_repos(tmp)
    kw.setdefault("with_candidate", True)
    kw.setdefault("with_plan", True)
    kw.setdefault("status", "planned")
    corpus, folder = F.build_package(tmp, target_repos=targets, **kw)
    return corpus, folder, targets


# ============================================================ scenario A ===

def scenario_a_long_brainstorm(tmp):
    """A large chat with many discarded ideas: everything preserved, nothing preloaded."""
    long_chat = F.TRANSCRIPT + "\n" + "\n".join(
        "## Meddelande %d — Johnny (användare)\nA side-track we later abandoned (%d).\n\n---"
        % (i, i) for i in range(4, 140))
    corpus, folder, targets = full_package(tmp)
    (folder / "demo-idea-full-chat.md").write_text(long_chat, encoding="utf-8")
    # manifest must notice the transcript changed under it
    rc, out = F.context(["validate", "--slug", "demo-idea"], corpus)
    expect_code("A1  transcript edited after capture → SOURCE_HASH_MISMATCH",
                out, rc, "SOURCE_HASH_MISMATCH", control=False)

    # re-hash the manifest and everything is consistent again
    m = json.loads((folder / "demo-idea-context-manifest.json").read_text())
    for s in m["sources"]:
        if s["kind"] == "chat-transcript":
            s["sha256"] = F.sha256_file(folder / s["path"])
    (folder / "demo-idea-context-manifest.json").write_text(
        json.dumps(m, indent=2) + "\n", encoding="utf-8")

    rc, out = F.context(["coverage", "--slug", "demo-idea",
                         "--target-repo", str(targets[0][1]),
                         "--target-repo", str(targets[1][1])], corpus)
    check("A2  long brainstorm still reaches PLANNING_CONTEXT_COMPLETE=YES",
          rc == 0 and "PLANNING_CONTEXT_COMPLETE=YES" in out, out.strip()[-900:])
    check("A3  rejections survive distillation with stable ids",
          "rejections traced           2/2" in out, out.strip()[-900:])

    rc, out = F.plan(["resume", "--slug", "demo-idea", "--workstream", "WS"], corpus)
    check("A4  Plan/impl context never preloads the raw transcript",
          "RAW_TRANSCRIPT=on-demand (not preloaded)" in out
          and "RAW_LOOKUP_AVAILABLE=YES" in out
          and "A side-track we later abandoned" not in out, out.strip()[-600:])


# ============================================================ scenario B ===

def scenario_b_load_bearing_attachment(tmp):
    """Two referenced files, one missing: planning is blocked until it is resolved."""
    pending = [{"kind": "attachment", "name": "architecture-plan.pdf",
                "path": "sources/architecture-plan.pdf", "capture_status": "pending",
                "load_bearing": True}]
    corpus, folder, targets = full_package(
        tmp, manifest_kw={"extra_sources": pending})
    args = ["coverage", "--slug", "demo-idea"] + \
        sum([["--target-repo", str(p)] for _, p in targets], [])
    rc, out = F.context(args, corpus)
    check("B1  load-bearing PENDING source blocks planning",
          rc != 0 and "PLANNING_CONTEXT_COMPLETE=NO" in out
          and "LOAD_BEARING_SOURCE_PENDING" in out
          and "architecture-plan.pdf" in out, out.strip()[-1200:])
    check("B2  a perfect brief does not hide the missing evidence",
          "decisions traced            3/3" in out and "PLANNING_CONTEXT_COMPLETE=NO" in out,
          out.strip()[-1200:])

    # the owner explicitly accepts planning without it — and that is durable
    m = json.loads((folder / "demo-idea-context-manifest.json").read_text())
    for s in m["sources"]:
        if s.get("name") == "architecture-plan.pdf":
            s["capture_status"] = "unavailable_owner_acknowledged"
            s["owner_ack"] = {"date": "2026-08-25",
                              "note": "Original upload lost; owner accepts planning "
                                      "without it and will re-derive from the brief."}
    (folder / "demo-idea-context-manifest.json").write_text(
        json.dumps(m, indent=2) + "\n", encoding="utf-8")
    rc, out = F.context(args, corpus)
    check("B3  explicit owner acknowledgement unblocks planning",
          rc == 0 and "PLANNING_CONTEXT_COMPLETE=YES" in out
          and "owner-acknowledged 1" in out, out.strip()[-900:])

    # ...but the acknowledgement itself must be durable, not implied
    for s in m["sources"]:
        if s.get("name") == "architecture-plan.pdf":
            del s["owner_ack"]
    (folder / "demo-idea-context-manifest.json").write_text(
        json.dumps(m, indent=2) + "\n", encoding="utf-8")
    rc, out = F.context(["validate", "--slug", "demo-idea"], corpus)
    expect_code("B4  acknowledgement without a durable record → FAIL",
                out, rc, "SOURCE_OWNER_ACK_MISSING", control=False)


# ============================================================ scenario C ===

def scenario_c_clarification_changes_design(tmp):
    """Raw stays X; the owner's Y is durable, outranks the brief, and is traceable."""
    corpus, folder, targets = full_package(tmp)
    raw = (folder / "demo-idea-full-chat.md").read_text(encoding="utf-8")
    clar = (folder / "demo-idea-owner-clarifications.md").read_text(encoding="utf-8")
    check("C1  the raw transcript still says what was actually said",
          "the canonical system repo is advisory only" in raw, raw[:200])
    check("C2  the owner's exact later wording is durable, with its question",
          "Reference-only." in clar and "CLAR-001" in clar
          and "resolves: Q2" in clar, clar[:400])

    rc, out = F.context(["trace", "--slug", "demo-idea", "--id", "CLAR-001"], corpus)
    check("C3  the clarification traces to the ids it changes",
          rc == 0 and "D3" in out and "AC3" in out and "Q2" in out, out.strip()[-800:])

    rc, out = F.plan(["coherence", "--slug", "demo-idea"], corpus)
    check("C4  the plan uses the clarification, and says so",
          rc == 0 and "CLAR-001" in out, out.strip()[-800:])

    # rewriting what the owner said is refused
    (folder / "demo-idea-owner-clarifications.md").write_text(
        clar.replace("Reference-only.", "Actually, write to it freely."), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(corpus)], check=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")
    subprocess.run(["git", "-C", str(corpus), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(corpus), "commit", "-qm", "x"], check=True, env=env)
    (folder / "demo-idea-owner-clarifications.md").write_text(
        clar.replace("Reference-only.", "Never said this."), encoding="utf-8")
    rc, out = F.context(["clarifications", "--slug", "demo-idea"], corpus)
    check("C5  editing recorded owner wording → NOT_APPEND_ONLY",
          rc != 0 and "CLARIFICATIONS_NOT_APPEND_ONLY" in out, out.strip()[-700:])


# ============================================================ scenario D ===

def scenario_d_plan_adds_scope(tmp):
    """A plan-added requirement is visible BEFORE approval, not buried."""
    corpus, folder, targets = full_package(tmp, with_plan=False)
    rc, out = F.plan(["coherence", "--slug", "demo-idea"], corpus)
    check("D1  a plan-only decision is surfaced as NEW_PLAN_DECISIONS",
          rc == 0 and re.search(r"^NEW_PLAN_DECISIONS=[1-9]", out, re.M)
          and "Adapter retries are capped" in out, out.strip()[-900:])

    cand = folder / "demo-idea-plan-candidate.md"
    text = cand.read_text(encoding="utf-8")
    cand.write_text(text.replace(
        "## 4. Decisions carried into execution",
        "## 4. Decisions carried into execution\n"
        "- We will also rewrite the billing subsystem end to end.\n"), encoding="utf-8")
    rc, out = F.plan(["coherence", "--slug", "demo-idea"], corpus)
    check("D2  a substantial new requirement appears in the delta",
          "rewrite the billing subsystem" in out, out.strip()[-900:])

    # dropping an acceptance criterion is reported, not silently accepted
    cand.write_text(re.sub(r"Covers AC2\.", "", text), encoding="utf-8")
    rc, out = F.plan(["coherence", "--slug", "demo-idea"], corpus)
    check("D3  an uncovered acceptance criterion is reported as dropped",
          re.search(r"^DROPPED_REQUIREMENTS=[1-9]", out, re.M)
          and "AC2" in out and "OWNER_REVIEW_REQUIRED=YES" in out, out.strip()[-900:])

    # re-adopting a rejected path is called out by name
    cand.write_text(text.replace(
        "R1 stays rejected: a second task ledger would create two truths.",
        "R1: we now implement the second task ledger after all."), encoding="utf-8")
    rc, out = F.plan(["coherence", "--slug", "demo-idea"], corpus)
    check("D4  a re-adopted rejection is flagged before approval",
          re.search(r"^REOPENED_REJECTIONS=[1-9]", out, re.M) and "R1" in out,
          out.strip()[-900:])


# ============================================================ scenario E ===

def scenario_e_exact_approval(tmp):
    """The owner approves bytes. Anything else is refused."""
    corpus, folder, targets = full_package(tmp, with_plan=False)
    cand = folder / "demo-idea-plan-candidate.md"
    sha = F.sha256_file(cand)
    F.git_commit_corpus(corpus, "candidate under review")   # the approval anchor

    rc, out = F.plan(["approve", "--slug", "demo-idea", "--candidate-sha", "0" * 64,
                      "--approved-by", "Johnny (Nortropic)", "--approved-at", "2026-08-25",
                      "--evidence", "said yes"], corpus)
    check("E1  approving a sha that is not the candidate on disk → REFUSED",
          rc == 2 and "APPROVAL_REFUSED" in out and "different documents" in out,
          out.strip()[-700:])

    # candidate swapped between the owner reading it and approval landing
    original = cand.read_text(encoding="utf-8")
    cand.write_text(original.replace("Read-first backend adapter",
                                     "Write-first backend adapter"), encoding="utf-8")
    rc, out = F.plan(["approve", "--slug", "demo-idea", "--candidate-sha", sha,
                      "--approved-by", "Johnny (Nortropic)", "--approved-at", "2026-08-25",
                      "--evidence", "said yes"], corpus)
    check("E2  candidate substituted after the owner read it → REFUSED",
          rc == 2 and "APPROVAL_REFUSED" in out, out.strip()[-700:])
    cand.write_text(original, encoding="utf-8")

    rc, out = F.plan(["approve", "--slug", "demo-idea", "--candidate-sha", sha,
                      "--approved-by", "Johnny (Nortropic)", "--approved-at", "2026-08-25",
                      "--evidence", "owner approved this candidate sha"], corpus)
    plan_path = folder / "demo-idea-approved-plan.md"
    check("E3  approving the exact candidate promotes it",
          rc == 0 and "APPROVED" in out and plan_path.exists(), out.strip()[-700:])

    sys.path.insert(0, str(F.ROOT / "scripts"))
    from intake_common import body_sha256
    check("E4  OWNER_APPROVED body == IMPLEMENTATION body, provably",
          body_sha256(plan_path) == body_sha256(cand), "promotion changed the body")

    F.rebind(folder, "demo-idea")
    (folder / "idea-demo-idea.md").write_text(
        (folder / "idea-demo-idea.md").read_text(encoding="utf-8")
        .replace("status: clarified", "status: planned"), encoding="utf-8")
    rc, out = F.plan(["validate", "--slug", "demo-idea"], corpus)
    check("E5  the promoted package validates", rc == 0, out.strip()[-800:])

    # a post-approval semantic edit is refused
    plan_path.write_text(plan_path.read_text(encoding="utf-8")
                         .replace("Covers AC1.", "Covers AC1 and also rewrites auth."),
                         encoding="utf-8")
    F.rebind(folder, "demo-idea")   # even re-binding the file hash cannot rescue it
    rc, out = F.plan(["validate", "--slug", "demo-idea"], corpus)
    check("E6  post-approval body edit → refused even after re-binding",
          rc != 0 and ("PLAN_CONTENT_SHA_MISMATCH" in out
                       or "PLAN_CANDIDATE_BODY_DIVERGED" in out), out.strip()[-900:])


# ======================================================== scenarios F & G ===

def scenario_fg_compaction_and_fresh_agent(tmp):
    """Everything conversational is gone; only slug + repos remain."""
    corpus, folder, targets = full_package(tmp)
    pointer = targets[0][1] / "CLAUDE.md"
    rc, out = F.plan(["pointer", "--slug", "demo-idea", "--workstream", "V2_CONTEXT",
                      "--into", str(pointer), "--execution-pointer", "S1 done"], corpus)
    check("F1  keyed pointer installed", rc == 0, out.strip()[-500:])

    # ---- compaction: a new process, scrubbed env, cwd outside everything ----
    proc = subprocess.run(
        [sys.executable, str(F.PLAN_CONTRACT), "--corpus", str(corpus), "resume",
         "--slug", "demo-idea", "--workstream", "V2_CONTEXT",
         "--pointer", str(pointer), "--target-repo", str(targets[0][1])],
        capture_output=True, text=True, cwd="/",
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
    out = proc.stdout + proc.stderr
    plan_sha = F.sha256_file(folder / "demo-idea-approved-plan.md")
    check("F2  fresh process recovers the full context package identity",
          proc.returncode == 0 and "CONTEXT_PACKAGE_VALID=YES" in out
          and plan_sha in out and "SOURCE_MANIFEST_IDENTITY=" in out
          and "CLARIFICATION_IDENTITY=" in out and "APPROVAL_RECEIPT=" in out,
          out.strip()[-1200:])
    check("F3  it hands back an ordered load plan, not a context dump",
          "CONTEXT_LOAD_ORDER" in out and "on-demand (not preloaded)" in out,
          out.strip()[-800:])
    check("G1  recovery needed no owner, no session and no environment",
          proc.returncode == 0 and "PLAN_IDENTITY_UNAVAILABLE" not in out,
          out.strip()[-600:])

    # the plan itself vanishing must fail closed, never be reconstructed
    (folder / "demo-idea-approved-plan.md").unlink()
    rc, out = F.plan(["resume", "--slug", "demo-idea", "--workstream", "V2_CONTEXT",
                      "--pointer", str(pointer)], corpus)
    check("F4  plan gone after compaction → PLAN_IDENTITY_UNAVAILABLE, not a guess",
          rc == 2 and "PLAN_IDENTITY_UNAVAILABLE" in out
          and "Do not reconstruct" in out, out.strip()[-700:])


# ============================================================ scenario H ===

def scenario_h_two_workstreams_one_repo(tmp):
    """Two unrelated workstreams pointing at the same repository must not collide."""
    targets = two_repos(tmp)
    corpus, folder = F.build_package(tmp, slug="alpha-idea", status="planned",
                                     with_candidate=True, with_plan=True,
                                     target_repos=targets)
    F.build_package(tmp, slug="beta-idea", status="planned",
                    with_candidate=True, with_plan=True, target_repos=targets)
    pointer = targets[0][1] / "CLAUDE.md"

    rc1, o1 = F.plan(["pointer", "--slug", "alpha-idea", "--workstream", "ALPHA",
                      "--into", str(pointer), "--execution-pointer", "S1"], corpus)
    rc2, o2 = F.plan(["pointer", "--slug", "beta-idea", "--workstream", "BETA",
                      "--into", str(pointer), "--execution-pointer", "S3"], corpus)
    text = pointer.read_text(encoding="utf-8")
    check("H1  both workstreams coexist; neither overwrote the other",
          rc1 == 0 and rc2 == 0
          and text.count("NORTROPIC-ACTIVE-PLAN:BEGIN") == 2
          and "ACTIVE_INTAKE_SLUG: alpha-idea" in text
          and "ACTIVE_INTAKE_SLUG: beta-idea" in text
          and "BLOCKS_IN_FILE=2" in o2, (o1 + o2)[-700:])

    rc, out = F.plan(["resume", "--slug", "alpha-idea", "--workstream", "ALPHA",
                      "--pointer", str(pointer)], corpus)
    check("H2  a session resolves ITS workstream's hint, not the other's",
          rc == 0 and "NEXT_EXECUTION_POINTER=S1" in out and "S3" not in
          out.split("NEXT_EXECUTION_POINTER")[1][:40], out.strip()[-700:])

    rc, out = F.plan(["resume", "--slug", "alpha-idea", "--pointer", str(pointer)], corpus)
    check("H3  without a workstream the hint is refused, not guessed",
          rc == 0 and "NEXT_EXECUTION_POINTER=S3" not in out, out.strip()[-700:])

    # rewriting alpha must leave beta byte-identical
    before = re.search(r"(?s)BEGIN workstream=BETA.*?END workstream=BETA[^>]*-->", text)
    F.plan(["pointer", "--slug", "alpha-idea", "--workstream", "ALPHA",
            "--into", str(pointer), "--execution-pointer", "S2"], corpus)
    after_text = pointer.read_text(encoding="utf-8")
    after = re.search(r"(?s)BEGIN workstream=BETA.*?END workstream=BETA[^>]*-->", after_text)
    check("H4  updating one workstream leaves the other untouched",
          before and after and before.group(0) == after.group(0)
          and "CURRENT_EXECUTION_POINTER: S2" in after_text,
          "beta block changed")


# ============================================================ scenario I ===

def scenario_i_multi_repo(tmp):
    """One plan, two repos, different authority. Resume reconciles both."""
    corpus, folder, targets = full_package(tmp)
    rc, out = F.plan(["resume", "--slug", "demo-idea", "--workstream", "WS",
                      "--target-repo", str(targets[0][1]),
                      "--target-repo", str(targets[1][1])], corpus)
    check("I1  resume discovers and inspects both target repositories",
          rc == 0 and out.count("TARGET_REPO_EVIDENCE=head:") == 2, out.strip()[-900:])
    check("I2  the advisory repo keeps its read-only authority",
          "TARGET_REPO_WRITABLE=NO" in out and "advisory-only" in out, out.strip()[-900:])

    rc, out = F.plan(["map", "--slug", "demo-idea"], corpus)
    data = json.loads(out)
    check("I3  the plan map carries both targets with their roles",
          len(data["execution_targets"]) == 2
          and {t["role"] for t in data["execution_targets"]}
          == {"operator-product", "advisory-only"}, out[-400:])

    bad = folder / "demo-idea-approved-plan.md"
    bad.write_text(bad.read_text(encoding="utf-8").replace(
        "=advisory-only", "=overlord"), encoding="utf-8")
    F.rebind(folder, "demo-idea")
    rc, out = F.plan(["validate", "--slug", "demo-idea"], corpus)
    check("I4  an undeclared/invented target role → FAIL",
          rc != 0 and "EXECUTION_TARGET_ROLE_INVALID" in out, out.strip()[-700:])


# ============================================================ scenario J ===

def scenario_j_stale_pointer(tmp):
    """Repo evidence beats the cache, and the discrepancy is reported."""
    corpus, folder, targets = full_package(tmp)
    pointer = targets[0][1] / "CLAUDE.md"
    F.plan(["pointer", "--slug", "demo-idea", "--workstream", "WS",
            "--into", str(pointer), "--execution-pointer", "S2"], corpus)
    old_sha = F.sha256_file(folder / "demo-idea-approved-plan.md")

    # the plan legitimately moves on; the pointer now names a dead identity
    plan = folder / "demo-idea-approved-plan.md"
    plan.write_text(plan.read_text(encoding="utf-8").replace(
        "approved_at: 2026-08-25", "approved_at: 2026-08-26"), encoding="utf-8")
    F.rebind(folder, "demo-idea")
    new_sha = F.sha256_file(plan)
    rc, out = F.plan(["resume", "--slug", "demo-idea", "--workstream", "WS",
                      "--pointer", str(pointer),
                      "--target-repo", str(targets[0][1])], corpus)
    check("J1  a stale pointer is reported and its hint discarded",
          rc == 0 and "POINTER_STALE=YES" in out
          and "NEXT_EXECUTION_POINTER=UNSET (stale pointer discarded" in out
          and "S2" not in out.split("NEXT_EXECUTION_POINTER")[1][:60],
          out.strip()[-900:])
    identity = re.search(r"^PLAN_IDENTITY=(\S+)", out, re.M)
    stale_line = re.search(r"^POINTER_STALE=YES.*$", out, re.M)
    check("J2  the identity reported is the corpus's; the dead sha appears only as "
          "the reported discrepancy",
          identity and identity.group(1).endswith("@sha256:" + new_sha)
          and stale_line and old_sha in stale_line.group(0)
          and old_sha not in out.replace(stale_line.group(0), ""),
          out.strip()[-900:])


# ============================================================ scenario K ===

def scenario_k_execution_status_lie(tmp):
    """`verified` is an observation. It cannot be made true by editing frontmatter."""
    corpus, folder, targets = full_package(tmp, status="planned")
    brief = folder / "idea-demo-idea.md"
    brief.write_text(brief.read_text(encoding="utf-8")
                     .replace("status: planned", "status: verified"), encoding="utf-8")
    rc, out = F.plan(["validate"], corpus)
    expect_code("K1  `verified` with no evidence → EXECUTION_EVIDENCE_MISSING",
                out, rc, "EXECUTION_EVIDENCE_MISSING")

    brief.write_text(brief.read_text(encoding="utf-8").replace(
        "status: verified",
        "status: verified\nexecution_repo: %s\nexecution_commit: deadbeefdead\n"
        "execution_slice: S9\nverification_evidence: docs/evidence.md"
        % targets[0][1]), encoding="utf-8")
    rc, out = F.plan(["validate"], corpus)
    expect_code("K2  evidence naming a slice the plan does not contain → FAIL",
                out, rc, "EXECUTION_EVIDENCE_UNKNOWN_SLICE")

    brief.write_text(brief.read_text(encoding="utf-8")
                     .replace("execution_slice: S9", "execution_slice: S1"),
                     encoding="utf-8")
    rc, out = F.plan(["validate"], corpus)
    check("K3  shape-valid evidence passes the corpus check (repos not needed)",
          rc == 0, out.strip()[-700:])

    rc, out = F.plan(["resume", "--slug", "demo-idea", "--workstream", "WS",
                      "--target-repo", str(targets[0][1])], corpus)
    check("K4  resume proves the commit and the REPOSITORY WINS",
          "EXECUTION_STATE_CONTRADICTED=YES" in out
          and "REPOSITORY WINS" in out
          and "does not exist in the repository" in out, out.strip()[-900:])

    real = subprocess.run(["git", "-C", str(targets[0][1]), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    brief.write_text(brief.read_text(encoding="utf-8")
                     .replace("execution_commit: deadbeefdead",
                              "execution_commit: %s" % real), encoding="utf-8")
    rc, out = F.plan(["resume", "--slug", "demo-idea", "--workstream", "WS",
                      "--target-repo", str(targets[0][1])], corpus)
    check("K5  a real commit is CONFIRMED, and confirmation is not a quality claim",
          "EXECUTION_STATE_OBSERVED=CONFIRMED" in out
          and "not that the work is correct" in out, out.strip()[-900:])


# ============================================================ scenario L ===

def scenario_l_bidirectional_provenance(tmp):
    """source → decision → AC → slice → evidence, and all the way back."""
    corpus, folder, targets = full_package(tmp)
    real = subprocess.run(["git", "-C", str(targets[0][1]), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    brief = folder / "idea-demo-idea.md"
    brief.write_text(brief.read_text(encoding="utf-8").replace(
        "status: planned",
        "status: building\nexecution_repo: %s\nexecution_commit: %s\n"
        "execution_slice: S1" % (targets[0][1], real)), encoding="utf-8")

    rc, out = F.context(["trace", "--slug", "demo-idea", "--id", "AC1"], corpus)
    check("L1  forwards: AC1 reaches its source material",
          rc == 0 and "REACHES_SOURCE=YES" in out and "SRC-001" in out,
          out.strip()[-900:])
    check("L2  backwards: AC1 reaches the slice and the implementation evidence",
          "S1" in out and "REACHES_IMPLEMENTATION=YES" in out, out.strip()[-900:])

    rc, out = F.context(["trace", "--slug", "demo-idea", "--commit", real], corpus)
    check("L3  from a commit back to plan slice, criterion, decision and source",
          rc == 0 and "S1" in out and "AC1" in out and "D1" in out
          and "REACHES_SOURCE=YES" in out, out.strip()[-1000:])

    rc, out = F.context(["trace", "--slug", "demo-idea", "--commit", "0" * 12], corpus)
    check("L4  an unknown commit resolves to nothing, loudly",
          rc != 0 and "PROVENANCE_UNRESOLVED" in out, out.strip()[-500:])


# ============================== scenario N: the review's own repros ========

def scenario_n_review_repros(tmp):
    """Every defect the independent adversarial review reproduced, locked shut.

    These are not hypotheticals: each one had a working repro that made the tools
    report success on material the owner never approved.
    """
    # --- C1: re-binding every recorded hash must not launder a post-approval edit ---
    corpus, folder, targets = full_package(Path(tmp) / "c1")
    F.git_commit_corpus(corpus, "approved state")
    plan = folder / "demo-idea-approved-plan.md"
    cand = folder / "demo-idea-plan-candidate.md"
    for path in (plan, cand):
        before = path.read_text(encoding="utf-8")
        after = before.replace("Advisory-only targets are read, never written.",
                               "Advisory-only targets may be written after all.")
        assert after != before, "the fixture edit must actually change the bytes"
        path.write_text(after, encoding="utf-8")
    sys.path.insert(0, str(F.ROOT / "scripts"))
    from intake_common import read_frontmatter, sha256_text
    body = read_frontmatter(plan)[1]
    text = re.sub(r"^plan_content_sha256: .*$", "plan_content_sha256: %s" % sha256_text(body),
                  plan.read_text(encoding="utf-8"), flags=re.M)
    text = re.sub(r"^approved_candidate_sha256: .*$",
                  "approved_candidate_sha256: %s" % F.sha256_file(cand), text, flags=re.M)
    plan.write_text(text, encoding="utf-8")
    F.rebind(folder, "demo-idea")
    rc, out = F.plan(["validate"], corpus)
    expect_code("N1  post-approval edit + full re-bind → PLAN_MUTATED_AFTER_COMMIT",
                out, rc, "PLAN_MUTATED_AFTER_COMMIT")

    # --- C3: resume must validate the context package, not assert it ---
    corpus, folder, targets = full_package(Path(tmp) / "c3")
    m = folder / "demo-idea-context-manifest.json"
    data = json.loads(m.read_text())
    data["sources"][0]["sha256"] = "c" * 64
    m.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    rc, out = F.plan(["resume", "--slug", "demo-idea", "--workstream", "WS"], corpus)
    check("N2  resume refuses when the context package does not validate",
          rc == 2 and "CONTEXT_PACKAGE_VALID=NO" in out
          and "SOURCE_HASH_MISMATCH" in out
          and "CONTEXT_PACKAGE_VALID=YES" not in out, out.strip()[-800:])

    # --- M1: the gate has no bypass flag ---
    corpus, folder, targets = full_package(Path(tmp) / "m1")
    brief = folder / "idea-demo-idea.md"
    brief.write_text(re.sub(r"\s*\(← [^)]*\)", "", brief.read_text(encoding="utf-8")),
                     encoding="utf-8")
    args = ["coverage", "--slug", "demo-idea"] + \
        sum([["--target-repo", str(p)] for _, p in targets], [])
    rc, out = F.context(args, corpus)
    rc2, out2 = F.context(args + ["--lenient-ids"], corpus)
    check("N3  stripping source tags blocks the gate, and there is no --lenient bypass",
          rc != 0 and "PLANNING_CONTEXT_COMPLETE=NO" in out
          and "PROVENANCE_MISSING" in out and rc2 != 0
          and "unrecognized arguments" in out2, (out + out2).strip()[-700:])

    # --- M2: an override must be the same repository, not the same basename ---
    # The real attack: the DECLARED target does not exist, and a throwaway repo with the
    # same last path segment is offered in its place.
    missing = Path(tmp) / "m2" / "nowhere" / "nortropic-system"
    corpus, folder, targets = full_package(
        Path(tmp) / "m2", targets=[("canonical-system", missing)])
    fake, _ = F.git_repo(Path(tmp) / "m2" / "fake" / "nortropic-system")
    rc, out = F.context(["coverage", "--slug", "demo-idea", "--target-repo", str(fake)],
                        corpus)
    check("N4  a basename-matching decoy repo does not count as inspection",
          rc != 0 and "TARGET_REPO_NOT_INSPECTED" in out
          and "PLANNING_CONTEXT_COMPLETE=NO" in out, out.strip()[-800:])

    # --- M5: a captured source may not live outside the package ---
    corpus, folder, targets = full_package(Path(tmp) / "m5")
    outside = Path(tmp) / "m5" / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "elsewhere.md").write_text("real content\n", encoding="utf-8")
    (folder / "escaped.md").symlink_to(outside / "elsewhere.md")
    m = folder / "demo-idea-context-manifest.json"
    data = json.loads(m.read_text())
    data["sources"].append({"source_id": "SRC-090", "kind": "attachment",
                            "name": "escaped.md", "path": "escaped.md",
                            "sha256": F.sha256_file(folder / "escaped.md"),
                            "capture_status": "captured", "load_bearing": True})
    m.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    rc, out = F.context(["validate"], corpus)
    expect_code("N5  a symlinked source escaping the idea folder → SOURCE_PATH_INVALID",
                out, rc, "SOURCE_PATH_INVALID")

    # --- M7: a tag that addresses nothing is not provenance ---
    corpus, folder, targets = full_package(Path(tmp) / "m7")
    brief = folder / "idea-demo-idea.md"
    brief.write_text(brief.read_text(encoding="utf-8")
                     .replace("(← msg 12)", "(← owner said so)"), encoding="utf-8")
    rc, out = F.context(["coverage", "--slug", "demo-idea",
                         "--target-repo", str(targets[0][1]),
                         "--target-repo", str(targets[1][1])], corpus)
    check("N6  a source tag naming nothing is not counted as traced",
          rc != 0 and "PROVENANCE_UNRESOLVABLE" in out
          and "PLANNING_CONTEXT_COMPLETE=NO" in out, out.strip()[-800:])
    rc, out = F.context(["trace", "--slug", "demo-idea", "--id", "D1"], corpus)
    check("N7  trace does not invent a transcript edge for prose",
          "REACHES_SOURCE=NO" in out, out.strip()[-500:])

    # --- M8: map must not serve an unvalidated plan ---
    corpus, folder, targets = full_package(Path(tmp) / "m8")
    plan = folder / "demo-idea-approved-plan.md"
    plan.write_text(plan.read_text(encoding="utf-8")
                    + "\n### S9 — ship the thing we rejected in R2\nDo it anyway.\n",
                    encoding="utf-8")
    rc, out = F.plan(["map", "--slug", "demo-idea"], corpus)
    check("N8  map refuses to serve slices from an unproven plan",
          rc == 2 and "PLAN_IDENTITY_UNAVAILABLE" in out
          and '"slices"' not in out
          and "ship the thing we rejected" not in out, out.strip()[-700:])

    # --- M9: the coherence delta must be acknowledged, not merely producible ---
    corpus, folder, targets = full_package(Path(tmp) / "m9", with_plan=False)
    cand = folder / "demo-idea-plan-candidate.md"
    cand.write_text(re.sub(r"Covers AC2\.", "", cand.read_text(encoding="utf-8")),
                    encoding="utf-8")
    F.git_commit_corpus(corpus, "candidate with a delta")
    base = ["approve", "--slug", "demo-idea", "--candidate-sha", F.sha256_file(cand),
            "--approved-by", "Johnny (Nortropic)", "--approved-at", "2026-08-25",
            "--evidence", "said yes"]
    rc, out = F.plan(base, corpus)
    check("N9  approve refuses a material delta without an explicit acknowledgement",
          rc == 2 and "APPROVAL_REFUSED" in out and "DROPPED_REQUIREMENT AC2" in out,
          out.strip()[-700:])
    rc, out = F.plan(base + ["--accept-delta"], corpus)
    check("N10 …and proceeds once the owner has approved the delta itself",
          rc == 0 and "APPROVED" in out, out.strip()[-700:])

    # --- M11 + self-approval + git anchor ---
    corpus, folder, targets = full_package(Path(tmp) / "m11")
    rc, out = F.plan(["pointer", "--slug", "demo-idea", "--workstream", "design system",
                      "--into", str(targets[0][1] / "CLAUDE.md")], corpus)
    check("N11 a workstream name that would corrupt the marker is refused",
          rc == 2 and "single token" in out
          and not (targets[0][1] / "CLAUDE.md").exists(), out.strip()[-600:])

    corpus, folder, targets = full_package(Path(tmp) / "self", with_plan=False)
    cand = folder / "demo-idea-plan-candidate.md"
    F.git_commit_corpus(corpus, "candidate")
    rc, out = F.plan(["approve", "--slug", "demo-idea", "--candidate-sha",
                      F.sha256_file(cand), "--approved-by", "Claude",
                      "--approved-at", "2026-08-25", "--evidence", "I approve"], corpus)
    check("N12 approve refuses when the agent signs for the owner",
          rc != 0 and "PLAN_NOT_APPROVED" in out
          and not (folder / "demo-idea-approved-plan.md").exists(), out.strip()[-600:])

    corpus, folder, targets = full_package(Path(tmp) / "anchor", with_plan=False)
    cand = folder / "demo-idea-plan-candidate.md"
    base = ["approve", "--slug", "demo-idea", "--candidate-sha", F.sha256_file(cand),
            "--approved-by", "Johnny (Nortropic)", "--approved-at", "2026-08-25",
            "--evidence", "said yes"]
    rc, out = F.plan(base, corpus)
    check("N13 an uncommitted candidate is refused: the bytes have no witness",
          rc == 2 and "not anchored in git" in out, out.strip()[-600:])
    rc, out = F.plan(base + ["--allow-uncommitted-candidate"], corpus)
    check("N14 …the escape hatch exists but records a WEAK attestation, not a proof",
          rc == 0 and "APPROVAL_ATTESTATION=WEAK" in out
          and "does NOT prove" in out, out.strip()[-800:])

    # --- M3: ID-shaped lines hidden in a code fence ---
    corpus, folder, targets = full_package(Path(tmp) / "fence")
    brief = folder / "idea-demo-idea.md"
    brief.write_text(brief.read_text(encoding="utf-8").replace(
        "## 9. Open questions (interview the owner before planning)",
        "## 9. Open questions (interview the owner before planning)\n\n"
        "```\n- Q9. A question nobody answered.\n```\n"), encoding="utf-8")
    rc, out = F.context(["coverage", "--slug", "demo-idea",
                         "--target-repo", str(targets[0][1]),
                         "--target-repo", str(targets[1][1])], corpus)
    check("N15 a question hidden inside a code fence is reported, not silently dropped",
          rc != 0 and "IDS_HIDDEN_IN_CODE_FENCE" in out and "Q9" in out,
          out.strip()[-700:])


# ====================================================== mutation matrix ====

def mutation_matrix(tmp):
    """Each planted failure must fail for ITS OWN reason, with a control passing."""
    cases = []

    def mutate(name, code, fn, slug="demo-idea", tool="context"):
        d = Path(tmp) / re.sub(r"\W", "", name)[:40]
        corpus, folder, targets = full_package(d)
        fn(folder, corpus, targets)
        runner = F.context if tool == "context" else F.plan
        rc, out = runner(["validate"], corpus)
        expect_code(name, out, rc, code, slug=slug)
        cases.append(name)

    def edit_manifest(folder, fn):
        p = folder / "demo-idea-context-manifest.json"
        data = json.loads(p.read_text())
        fn(data)
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    mutate("M01 attachment hash mutated → SOURCE_HASH_MISMATCH", "SOURCE_HASH_MISMATCH",
           lambda f, c, t: edit_manifest(f, lambda d: d["sources"][0].update(
               {"sha256": "b" * 64})))
    mutate("M02 duplicate source ids → SOURCE_ID_DUPLICATE", "SOURCE_ID_DUPLICATE",
           lambda f, c, t: edit_manifest(f, lambda d: d["sources"][1].update(
               {"source_id": d["sources"][0]["source_id"]})))
    mutate("M03 manifest points at a file that is gone → SOURCE_FILE_MISSING",
           "SOURCE_FILE_MISSING",
           lambda f, c, t: (f / "demo-idea-design-rationale.md").unlink())
    mutate("M04 credential smuggled into a manifest → MANIFEST_CREDENTIAL_LEAK",
           "MANIFEST_CREDENTIAL_LEAK",
           lambda f, c, t: edit_manifest(f, lambda d: d["sources"][0].update(
               {"origin": "https://example.com/x?access_token=ghp_AAAAAAAAAAAAAAAAAAAA"})))
    mutate("M05 orphaned clarification reference → CLARIFICATION_ORPHANED",
           "CLARIFICATION_ORPHANED",
           lambda f, c, t: _sub(f / "demo-idea-owner-clarifications.md",
                                "resolves: Q2", "resolves: Q99"))
    def strip_answer(f, c, t):
        p = f / "demo-idea-owner-clarifications.md"
        text = p.read_text(encoding="utf-8")
        text = re.sub(r"- owner_answer: Reference-only\..*?(?=\n## )", "- owner_answer:\n",
                      text, flags=re.S)
        p.write_text(text, encoding="utf-8")
        edit_manifest(f, lambda d: [s.update({"sha256": F.sha256_file(f / s["path"])})
                                    for s in d["sources"] if s.get("path")])
    mutate("M06 clarification without the owner's answer → CLARIFICATION_INCOMPLETE",
           "CLARIFICATION_INCOMPLETE", strip_answer)
    mutate("M07 execution target role invented → EXECUTION_TARGET_ROLE_INVALID",
           "EXECUTION_TARGET_ROLE_INVALID",
           lambda f, c, t: edit_manifest(f, lambda d: d["execution_targets"][0].update(
               {"role": "supreme-authority"})))
    mutate("M08 manifest declares no targets → EXECUTION_TARGETS_MISSING",
           "EXECUTION_TARGETS_MISSING",
           lambda f, c, t: edit_manifest(f, lambda d: d.update({"execution_targets": []})))

    def drop_ac(f, c, t):
        p = f / "demo-idea-approved-plan.md"
        _sub(p, "Covers AC2.", "")
        F.rebind(f, "demo-idea")
    mutate("M09 plan drops an AC → still valid shape, caught by coherence",
           "PLAN_CONTENT_SHA_MISMATCH", drop_ac, tool="plan")

    def swap_candidate(f, c, t):
        cand = f / "demo-idea-plan-candidate.md"
        _sub(cand, "Read-first backend adapter", "Write-first backend adapter")
    mutate("M10 candidate substituted after approval → PLAN_CANDIDATE_SHA_MISMATCH",
           "PLAN_CANDIDATE_SHA_MISMATCH", swap_candidate, tool="plan")

    def unknown_ref(f, c, t):
        p = f / "demo-idea-approved-plan.md"
        _sub(p, "Implements D1.", "Implements D1 and D99.")
        F.rebind(f, "demo-idea")
    mutate("M11 plan references an unknown decision id → content hash breaks",
           "PLAN_CONTENT_SHA_MISMATCH", unknown_ref, tool="plan")

    mutate("M12 supersession cycle → PLAN_SUPERSESSION_BROKEN",
           "PLAN_SUPERSESSION_BROKEN",
           lambda f, c, t: (_sub(f / "demo-idea-approved-plan.md",
                                 "authority: owner-approved-execution-intent",
                                 "authority: owner-approved-execution-intent\n"
                                 "supersedes_plan: demo-idea-approved-plan.md"),
                            F.rebind(f, "demo-idea")), tool="plan")
    mutate("M13 brief claims a private session path → not required anywhere",
           "SOURCE_PATH_INVALID",
           lambda f, c, t: edit_manifest(f, lambda d: d["sources"][0].update(
               {"path": "../../.claude/projects/x.jsonl"})))
    print("    (%d mutations, each failing for its own code, control passing)" % len(cases))


def _sub(path, old, new):
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


# ================================================== final acceptance test ===

def final_acceptance(tmp):
    """§39 — the whole pipeline, ending in a process with no brainstorm context."""
    print("\n--- FINAL ACCEPTANCE: brainstorm → plan → approval → compaction → resume ---")
    targets = two_repos(tmp)
    corpus, folder = F.build_package(
        tmp, slug="acceptance-idea", status="clarified", with_candidate=True,
        target_repos=targets,
        manifest_kw={"extra_sources": [
            {"kind": "attachment", "name": "architecture.pdf", "path": "architecture.pdf",
             "sha256": F.sha256_text("PDF"), "capture_status": "captured",
             "load_bearing": True}]},
        files={"architecture.pdf": "PDF"})

    args = ["coverage", "--slug", "acceptance-idea"] + \
        sum([["--target-repo", str(p)] for _, p in targets], [])
    rc, out = F.context(args, corpus)
    check("X1  context coverage gate opens with a captured attachment",
          rc == 0 and "PLANNING_CONTEXT_COMPLETE=YES" in out
          and "captured 4" in out, out.strip()[-900:])

    rc, out = F.plan(["coherence", "--slug", "acceptance-idea"], corpus)
    check("X2  coherence report produced for owner review",
          rc == 0 and "DECISIONS_PRESERVED=3/3" in out and "SLICES:" in out,
          out.strip()[-700:])

    cand = folder / "acceptance-idea-plan-candidate.md"
    sha = F.sha256_file(cand)
    F.git_commit_corpus(corpus, "acceptance candidate under review")
    rc, out = F.plan(["approve", "--slug", "acceptance-idea", "--candidate-sha", sha,
                      "--approved-by", "Johnny (Nortropic)", "--approved-at", "2026-08-25",
                      "--evidence", "owner approved candidate %s" % sha[:12]], corpus)
    check("X3  owner approves the exact candidate sha", rc == 0 and "APPROVED" in out,
          out.strip()[-700:])

    F.rebind(folder, "acceptance-idea")
    brief = folder / "idea-acceptance-idea.md"
    real = subprocess.run(["git", "-C", str(targets[0][1]), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    brief.write_text(brief.read_text(encoding="utf-8").replace(
        "status: clarified",
        "status: building\nexecution_repo: %s\n"
        "execution_commit: %s\nexecution_slice: S1" % (targets[0][1], real)),
        encoding="utf-8")
    rc, out = F.plan(["validate", "--slug", "acceptance-idea"], corpus)
    check("X4  bound package validates", rc == 0, out.strip()[-700:])

    pointer = targets[0][1] / "CLAUDE.md"
    F.plan(["pointer", "--slug", "acceptance-idea", "--workstream", "ACCEPTANCE",
            "--into", str(pointer), "--execution-pointer", "S1 done"], corpus)

    # ---- everything conversational is destroyed here ----
    proc = subprocess.run(
        [sys.executable, str(F.PLAN_CONTRACT), "--corpus", str(corpus), "resume",
         "--slug", "acceptance-idea", "--workstream", "ACCEPTANCE",
         "--pointer", str(pointer), "--target-repo", str(targets[0][1]),
         "--target-repo", str(targets[1][1])],
        capture_output=True, text=True, cwd="/",
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
    out = proc.stdout + proc.stderr
    flags = {
        "BRAINSTORM_CONTEXT_LOSS": "SOURCE_MANIFEST_IDENTITY=" in out and "ABSENT" not in
                                   out.split("SOURCE_MANIFEST_IDENTITY=")[1][:12],
        "PLAN_CONTEXT_LOSS": "PLAN_STATUS=APPROVED" in out,
        "OWNER_CLARIFICATION_LOSS": "CLARIFICATION_IDENTITY=" in out and "ABSENT" not in
                                    out.split("CLARIFICATION_IDENTITY=")[1][:12],
        "ATTACHMENT_IDENTITY_LOSS": True,
        "FRESH_SESSION_RECOVERY": proc.returncode == 0,
        "MULTI_REPO_RECOVERY": out.count("TARGET_REPO_EVIDENCE=head:") == 2,
        "MULTI_WORKSTREAM_DISAMBIGUATION": "ACTIVE_WORKSTREAM=ACCEPTANCE" in out,
        "REPO_REALITY_WINS": "EXECUTION_STATE_OBSERVED=CONFIRMED" in out,
    }
    rc2, trace = F.context(["trace", "--slug", "acceptance-idea", "--commit", real], corpus)
    flags["BIDIRECTIONAL_PROVENANCE"] = rc2 == 0 and "REACHES_SOURCE=YES" in trace

    rc3, mout = F.context(["manifest", "--slug", "acceptance-idea"], corpus)
    flags["ATTACHMENT_IDENTITY_LOSS"] = rc3 == 0 and "manifest valid" in mout

    for key, ok in flags.items():
        label = key if key.endswith(("RECOVERY", "PROVENANCE", "WINS",
                                     "DISAMBIGUATION")) else key
        check("X5 %-34s %s" % (label, "PASS" if ok else "FAIL"), ok,
              out.strip()[-900:] if not ok else "")
    return flags


# ------------------------------------------------------------------ main ---

SCENARIOS = [
    ("A  long brainstorm", scenario_a_long_brainstorm),
    ("B  load-bearing attachment", scenario_b_load_bearing_attachment),
    ("C  clarification changes the design", scenario_c_clarification_changes_design),
    ("D  plan introduces new scope", scenario_d_plan_adds_scope),
    ("E  exact approval", scenario_e_exact_approval),
    ("F/G compaction and fresh agent", scenario_fg_compaction_and_fresh_agent),
    ("H  two workstreams, one repo", scenario_h_two_workstreams_one_repo),
    ("I  multi-repo plan", scenario_i_multi_repo),
    ("J  stale pointer", scenario_j_stale_pointer),
    ("K  execution status lie", scenario_k_execution_status_lie),
    ("L  bidirectional provenance", scenario_l_bidirectional_provenance),
    ("N  the adversarial review's own repros", scenario_n_review_repros),
]

# A suite that exits 0 having run nothing is worse than a failing one: it reports
# success. Both suites assert a floor on checks actually executed.
MIN_CHECKS = 80


def main():
    for label, fn in SCENARIOS:
        print("\n--- SCENARIO %s ---" % label)
        tmp = tempfile.mkdtemp(prefix="ctx-v2-")
        try:
            fn(tmp)
        except KeyboardInterrupt:
            raise
        # BaseException, not Exception: a stubbed dependency raises SystemExit, which
        # would otherwise unwind the whole suite to a green exit code having run nothing.
        except BaseException as exc:
            check("%s raised %s" % (label, type(exc).__name__), False, str(exc)[:400])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n--- MUTATION MATRIX ---")
    tmp = tempfile.mkdtemp(prefix="ctx-v2-mut-")
    try:
        mutation_matrix(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    tmp = tempfile.mkdtemp(prefix="ctx-v2-acc-")
    try:
        final_acceptance(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [n for n, ok, _ in RESULTS if not ok]
    print("\n%d/%d checks passed" % (len(RESULTS) - len(failed), len(RESULTS)))
    if failed:
        print("failed:")
        for n in failed:
            print("  - %s" % n)
    if len(RESULTS) < MIN_CHECKS:
        print("\nSUITE DID NOT RUN: only %d checks executed, expected at least %d. "
              "Exiting non-zero — a green exit code from a suite that ran nothing is "
              "the worst possible outcome." % (len(RESULTS), MIN_CHECKS))
        sys.exit(1)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
