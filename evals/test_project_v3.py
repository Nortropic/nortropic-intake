#!/usr/bin/env python3
"""v3 suite — role-aware provenance, durable approval strength, PROJECT_SWEEP.

The owner's v3 regression matrix, built as real files and real git repositories and
run through the real validators — no mocks:

  A1–A4   role-aware provenance: an assistant turn can never impersonate the owner;
          a real owner message can back a decision; mixed ranges resolve to the part
          that actually carries authority; external text still confers nothing.
  B5–B8   approval strength: WEAK is written durably, STRONG stays STRONG, a legacy
          plan is LEGACY_UNKNOWN (never promoted), a post-commit masquerade is caught.
  C8–C12  project source model: stable identities, title-collisions stay separate,
          idempotent reruns, traceable revisions, surviving raw history.
  D13–D16 project coverage: hard gaps beat completeness, manifest matches the tree,
          interrupted sweeps resume, a false COMPLETE fails validation.
  E17–E20 idea routing: one chat → many ideas, many chats → one idea, ambiguity is
          queued without blocking, duplicate INDEX state is detected.
  F21–F24 mode separation: a full synthetic sweep never interviews, never plans,
          and completes unattended; single mode is untouched.
  G25–G29 audit & trust: dangling provenance, self-closed findings, tampered hashes,
          mutated raw, and project normalization that cannot mint owner authority.
  H30–H31 side-effect contract: the tools never commit the corpus; fixtures never
          touch the real corpus (every command runs against a tmp --corpus).

All real Improvements sweeping is out of scope here BY CONSTRUCTION: every project
in this suite is synthetic, in a temp directory, and torn down after the run.

Usage (from the skill root):
  python3 evals/test_project_v3.py            # exit 1 on any failure
"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixtures as F  # noqa: E402

RESULTS = []

# A suite that exits 0 having run nothing reports success it did not earn.
MIN_CHECKS = 50


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS " if condition else "FAIL ", name,
                        ("\n        — %s" % detail) if (detail and not condition) else ""))


# ------------------------------------------------------------ mini fixtures --

ROLE_TRANSCRIPT = """# Transkript

**Antal meddelanden:** 4

## Meddelande 1 — Johnny (användare)
Vi behöver en cache för operatörsvyn.

---

## Meddelande 2 — ChatGPT (assistent)
Då är B beslutat: vi bygger cachen med en write-through-strategi.

---

## Meddelande 3 — Johnny (användare)
Ja — write-through, och den får aldrig serva äldre än 5 sekunder.

---

## Meddelande 4 — ChatGPT (assistent)
Noterat. Jag föreslår också att vi byter ramverk till Q.
"""

ROLELESS_TRANSCRIPT = """# Transkript (äldre exportformat)

## Meddelande 1
Vi behöver en cache för operatörsvyn.

---

## Meddelande 2
Då är B beslutat.
"""


def mini_pkg(corpus, slug, transcript, decision_lines, extra_sources=None):
    """A minimal package: brief + rationale + transcript (+ optional manifest).

    Small on purpose — these packages exist to exercise the provenance rules, so the
    brief carries exactly the decision lines under test plus one clean AC.
    """
    folder = Path(corpus) / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ("%s-full-chat.md" % slug)).write_text(transcript, encoding="utf-8")
    (folder / ("%s-design-rationale.md" % slug)).write_text(
        "# rationale\n\nWhy the design took its shape.\n", encoding="utf-8")
    body = ["# Idea brief: %s" % slug, "",
            "## 4. Decisions already made", ""]
    body += decision_lines
    body += ["", "## 5. Acceptance criteria (v1)",
             "- AC1. WHEN the cache is stale, THE UI SHALL refresh it (← msg 3).", ""]
    (folder / ("idea-%s.md" % slug)).write_text(
        F.frontmatter({"title": '"%s"' % slug, "type": "idea-brief", "status": "idea",
                       "slug": slug, "owner": "Johnny (Nortropic)",
                       "created": "2026-08-30"}) + "\n".join(body), encoding="utf-8")
    if extra_sources is not None:
        (folder / ("%s-context-manifest.json" % slug)).write_text(
            F.manifest(slug, folder, extra_sources=extra_sources), encoding="utf-8")
    return folder


SWEEP_CHAT_1 = """# Transkript

**Antal meddelanden:** 3

## Meddelande 1 — Johnny (användare)
Idé ett: en export-pipeline. Idé två: en kvalitetsgrind. Båda ska byggas.

---

## Meddelande 2 — ChatGPT (assistent)
Förslag: pipelinen först.

---

## Meddelande 3 — Johnny (användare)
Ja, pipelinen först — beslutat.
"""

SWEEP_CHAT_2 = """# Transkript

**Antal meddelanden:** 2

## Meddelande 1 — Johnny (användare)
Mer om kvalitetsgrinden: den ska vara fail-closed.

---

## Meddelande 2 — ChatGPT (assistent)
Då dokumenterar vi fail-closed som grundprincip.
"""

SWEEP_CHAT_2B = SWEEP_CHAT_2 + """
---

## Meddelande 3 — Johnny (användare)
Tillägg: grinden ska också logga varje beslut.
"""

URL_1 = "https://chatgpt.com/c/aaaaaaaa-1111-2222-3333-000000000001"
URL_2 = "https://chatgpt.com/c/bbbbbbbb-1111-2222-3333-000000000002"
URL_3 = "https://chatgpt.com/c/cccccccc-1111-2222-3333-000000000003"


def sweep_audit_doc(project, rounds):
    return F.frontmatter({"title": '"%s — sweep audit"' % project,
                          "type": "sweep-audit", "project": project,
                          "owner": "Johnny (Nortropic)", "append_only": "true"}) \
        + "\n# Sweep audit: %s\n\n" % project + "".join(rounds)


def review_queue_doc(project, blocks):
    return F.frontmatter({"title": '"%s — review queue"' % project,
                          "type": "review-queue", "project": project,
                          "owner": "Johnny (Nortropic)", "append_only": "true"}) \
        + "\n# Review queue: %s\n\n" % project + "".join(blocks)


def rq_block(rq_id, issue="CONTINUE_EXISTING vs RELATED is ambiguous",
             affects="CONV-001", recommendation="treat as RELATED until owner rules",
             owner_required="yes", resolves=None, owner_answer=None):
    lines = ["## %s" % rq_id, "- date: 2026-08-30"]
    if resolves:
        lines.append("- resolves: %s" % resolves)
    else:
        lines += ["- issue: %s" % issue,
                  "- affects: %s" % affects,
                  "- recommendation: %s" % recommendation,
                  "- evidence: msg 1–3 in %s" % affects,
                  "- owner_judgment_required: %s" % owner_required]
    if owner_answer:
        lines.append("- owner_answer: %s" % owner_answer)
    return "\n".join(lines) + "\n\n"


def read_project_manifest(corpus, name):
    return json.loads((Path(corpus) / "_projects" / name /
                       "project-manifest.json").read_text(encoding="utf-8"))


def write_project_manifest(corpus, name, data):
    (Path(corpus) / "_projects" / name / "project-manifest.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sweep_project(tmp, name="demo-sweep"):
    """init + declare(3 conversations) against a fresh tmp corpus. Returns corpus."""
    corpus = Path(tmp) / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    F.add_control(corpus)
    inv = Path(tmp) / "inventory.json"
    inv.write_text(json.dumps([
        {"url": URL_1, "title": "Pipeline & grind"},
        {"url": URL_2, "title": "Kvalitetsgrinden"},
        {"url": URL_3, "title": "Kvalitetsgrinden"},   # same TITLE, different id
    ]), encoding="utf-8")
    rc, out = F.project(["init", "--project", name, "--title", "Demo sweep",
                         "--platform", "chatgpt", "--at", "2026-08-30"], corpus)
    assert rc == 0, out
    rc, out = F.project(["declare", "--project", name, "--inventory", str(inv),
                         "--method", "declared", "--at", "2026-08-30"], corpus)
    assert rc == 0, out
    return corpus


def capture(corpus, name, source, text, tmp, at="2026-08-30"):
    f = Path(tmp) / ("cap-%s-%s.md" % (source, F.sha256_text(text)[:8]))
    f.write_text(text, encoding="utf-8")
    return F.project(["capture", "--project", name, "--source", source,
                      "--file", str(f), "--at", at], corpus)


def deliver_idea(corpus, slug, transcript_texts):
    """A swept idea package whose episode transcripts ARE the conversations."""
    folder = Path(corpus) / slug
    folder.mkdir(parents=True, exist_ok=True)
    for i, text in enumerate(transcript_texts):
        n = ("%s-full-chat.md" % slug) if i == 0 else \
            ("%s-full-chat-CHAT-%03d.md" % (slug, i + 1))
        (folder / n).write_text(text, encoding="utf-8")
    (folder / ("%s-design-rationale.md" % slug)).write_text(
        "# rationale\n", encoding="utf-8")
    (folder / ("idea-%s.md" % slug)).write_text(
        F.frontmatter({"title": '"%s"' % slug, "type": "idea-brief", "status": "idea",
                       "slug": slug, "owner": "Johnny (Nortropic)",
                       "created": "2026-08-30"})
        + "# Idea brief: %s\n\n## 4. Decisions already made\n"
          "- D1. Build it — because the owner said so (← msg 1).\n" % slug,
        encoding="utf-8")
    return folder


def upsert_index(corpus, slug):
    index = Path(corpus) / "INDEX.md"
    line = "| %s | %s | idea | 2026-08-30 | — |\n" % (slug, slug)
    text = index.read_text(encoding="utf-8") if index.exists() else \
        "# Idébanken\n\n| slug | title | STATUS | created | links |\n|---|---|---|---|---|\n"
    if not re.search(r"^\|\s*%s\s*\|" % re.escape(slug), text, re.M):
        text += line
    index.write_text(text, encoding="utf-8")


# ============================================================ A. roles ======

def a_role_aware(tmp):
    corpus = Path(tmp) / "corpus"
    corpus.mkdir(parents=True)
    F.add_control(corpus)

    # A1: the assistant "decides" something the owner never said.
    mini_pkg(corpus, "cache-idea", ROLE_TRANSCRIPT, [
        "- D1. Write-through cache — because staleness must be bounded (← msg 3).",
        "- D2. B är beslutat — because the assistant said so (← msg 2).",
    ])
    rc, out = F.context(["coverage", "--slug", "cache-idea"], corpus)
    check("A1 an assistant 'decision' is refused as owner backing",
          rc != 0 and re.search(
              r"OWNER_BACKING_ASSISTANT_ONLY — D2 .*msg 2", out),
          out.strip()[:1200])
    check("A2 a real owner message still backs a decision",
          "OWNER_BACKING_ASSISTANT_ONLY — D1" not in out
          and "PROVENANCE_ROLE_UNKNOWN — D1" not in out, out.strip()[:1200])

    # A3: a mixed interval — the validator must know which part carries authority.
    mini_pkg(corpus, "mixed-idea", ROLE_TRANSCRIPT, [
        "- D1. Bounded staleness — because the owner set the bound (← msg 2–3).",
        "- D2. Framework Q — because it came up late (← msg 4).",
    ])
    rc, out = F.context(["coverage", "--slug", "mixed-idea"], corpus)
    check("A3a a mixed user+assistant interval passes on the owner part",
          "OWNER_BACKING_ASSISTANT_ONLY — D1" not in out, out.strip()[:1200])
    check("A3b the assistant-only part is named, message numbers and all",
          re.search(r"OWNER_BACKING_ASSISTANT_ONLY — D2 .*msg 4", out) is not None,
          out.strip()[:1200])

    # A4: external source text can never carry instruction authority.
    # (SRC-003: the mini manifest holds transcript + rationale, then this source.)
    mini_pkg(corpus, "external-idea", ROLE_TRANSCRIPT, [
        "- D1. Switch to framework X — because a vendor page insists (← SRC-003).",
    ], extra_sources=[{"kind": "external-url", "name": "vendor page",
                       "origin": "https://vendor.example/docs", "title": "Docs",
                       "accessed_at": "2026-08-30", "source_class": "documentation",
                       "supports": "D1", "capture_status": "captured",
                       "load_bearing": True, "trust": "EXTERNAL_EVIDENCE",
                       "instruction_authority": "none"}])
    rc, out = F.context(["coverage", "--slug", "external-idea"], corpus)
    check("A4 external evidence still cannot BE a decision",
          rc != 0 and "DECISION_SOURCED_ONLY_FROM_EXTERNAL_EVIDENCE" in out
          and "D1" in out, out.strip()[:1200])

    # Legacy: role-less headers are reported honestly, never assumed owner-backed
    # and never accused of being assistant-only.
    mini_pkg(corpus, "legacy-idea", ROLELESS_TRANSCRIPT, [
        "- D1. Build the cache — because we said so back then (← msg 1).",
    ])
    rc, out = F.context(["coverage", "--slug", "legacy-idea"], corpus)
    check("A5 legacy role-less provenance reports WARN PROVENANCE_ROLE_UNKNOWN",
          re.search(r"^WARN\s+\[legacy-idea\]\s+PROVENANCE_ROLE_UNKNOWN — D1",
                    out, re.M) is not None
          and "OWNER_BACKING_ASSISTANT_ONLY" not in out, out.strip()[:1200])

    # And the control package (real owner-backed citations) stays clean.
    rc, out = F.context(["coverage", "--slug", F.CONTROL_SLUG], corpus)
    check("A6 the control package raises no role findings at all",
          "OWNER_BACKING_ASSISTANT_ONLY" not in out
          and "PROVENANCE_ROLE_UNKNOWN" not in out, out.strip()[:1200])


# ========================================================= B. approvals =====

def b_approval_strength(tmp):
    # B5: a weak approval is durably WEAK.
    corpus, folder = F.build_package(Path(tmp) / "b5", slug="weak-idea",
                                     with_candidate=True, status="clarified")
    cand = folder / "weak-idea-plan-candidate.md"
    rc, out = F.plan(["approve", "--slug", "weak-idea",
                      "--candidate-sha", F.sha256_file(cand),
                      "--approved-by", "Johnny (Nortropic)",
                      "--approved-at", "2026-08-30",
                      "--evidence", "owner approved this sha in session",
                      "--allow-uncommitted-candidate"], corpus)
    plan_path = folder / "weak-idea-approved-plan.md"
    fm, _, _ = F.read_frontmatter_text(plan_path.read_text(encoding="utf-8"))
    check("B5a weak approval promotes, and says WEAK at approval time",
          rc == 0 and "APPROVAL_ATTESTATION=WEAK" in out, out.strip()[:1200])
    check("B5b the WEAK attestation is persisted in the plan's own frontmatter",
          fm.get("approval_attestation") == "WEAK"
          and fm.get("approval_git_anchor") in ("UNTRACKED", "MUTATED"),
          str({k: fm.get(k) for k in ("approval_attestation", "approval_git_anchor")}))
    F.rebind(folder, "weak-idea")
    text = (folder / "idea-weak-idea.md").read_text(encoding="utf-8")
    (folder / "idea-weak-idea.md").write_text(
        text.replace("status: clarified", "status: planned"), encoding="utf-8")
    rc, out = F.plan(["validate", "--slug", "weak-idea"], corpus)
    check("B5c a later validator can still see the approval was weak",
          rc == 0 and "approval_attestation" not in out.lower().replace(
              "approval_attestation: weak", ""), out.strip()[:800])
    rc, out = F.plan(["resume", "--slug", "weak-idea", "--workstream", "W1"], corpus)
    check("B5d resume reports APPROVAL_ATTESTATION=WEAK",
          "APPROVAL_ATTESTATION=WEAK" in out, out.strip()[:1500])

    # B6: a strong approval stays strong.
    corpus6, folder6 = F.build_package(Path(tmp) / "b6", slug="strong-idea",
                                       with_plan=True, status="planned")
    fm6, _, _ = F.read_frontmatter_text(
        (folder6 / "strong-idea-approved-plan.md").read_text(encoding="utf-8"))
    check("B6a the committed-candidate path records STRONG + UNCHANGED anchor",
          fm6.get("approval_attestation") == "STRONG"
          and fm6.get("approval_git_anchor") == "UNCHANGED",
          str({k: fm6.get(k) for k in ("approval_attestation", "approval_git_anchor")}))
    rc, out = F.plan(["resume", "--slug", "strong-idea", "--workstream", "W1"], corpus6)
    check("B6b resume reports APPROVAL_ATTESTATION=STRONG",
          "APPROVAL_ATTESTATION=STRONG" in out, out.strip()[:1500])

    # B7: a legacy plan (no attestation) is LEGACY_UNKNOWN — reported, never promoted.
    # Simulated faithfully: a REAL v3 approval with the two attestation lines
    # stripped is byte-wise exactly what a v2.1 `approve` produced.
    corpus7, folder7 = F.build_package(Path(tmp) / "b7", slug="legacy-plan",
                                       with_plan=True, status="planned")
    plan7 = folder7 / "legacy-plan-approved-plan.md"
    plan7.write_text("\n".join(
        line for line in plan7.read_text(encoding="utf-8").splitlines()
        if not line.startswith(("approval_attestation:", "approval_git_anchor:")))
        + "\n", encoding="utf-8")
    F.rebind(folder7, "legacy-plan")
    rc, out = F.plan(["validate", "--slug", "legacy-plan"], corpus7)
    check("B7a a legacy plan without attestation is WARN LEGACY_UNKNOWN, not a FAIL",
          rc == 0 and re.search(
              r"^WARN\s+\[legacy-plan\]\s+PLAN_ATTESTATION_LEGACY_UNKNOWN",
              out, re.M) is not None and "never assumed STRONG" in out,
          out.strip()[:1200])
    rc, out = F.plan(["resume", "--slug", "legacy-plan", "--workstream", "W1"], corpus7)
    check("B7b resume reports APPROVAL_ATTESTATION=LEGACY_UNKNOWN",
          "APPROVAL_ATTESTATION=LEGACY_UNKNOWN" in out, out.strip()[:1500])

    # B7c: an out-of-vocabulary attestation is a FAIL, not a shrug.
    corpus7c, folder7c = F.build_package(Path(tmp) / "b7c", slug="forged-att",
                                         with_plan=True, status="planned")
    plan7c = folder7c / "forged-att-approved-plan.md"
    plan7c.write_text(plan7c.read_text(encoding="utf-8").replace(
        "approval_attestation: STRONG", "approval_attestation: TOTAL"),
        encoding="utf-8")
    F.rebind(folder7c, "forged-att")
    rc, out = F.plan(["validate", "--slug", "forged-att"], corpus7c)
    check("B7c an unreadable attestation value fails validation",
          rc != 0 and re.search(
              r"^FAIL\s+\[forged-att\]\s+PLAN_ATTESTATION_INVALID", out, re.M)
          is not None
          and "PLAN_CONTENT_SHA_MISMATCH" not in out, out.strip()[:1200])

    # B8: flipping WEAK→STRONG after the commit is caught by the git witness.
    F.git_commit_corpus(corpus, "weak plan committed")
    ptext = plan_path.read_text(encoding="utf-8")
    plan_path.write_text(ptext.replace("approval_attestation: WEAK",
                                       "approval_attestation: STRONG"),
                         encoding="utf-8")
    rc, out = F.plan(["validate", "--slug", "weak-idea"], corpus)
    check("B8 a post-commit WEAK→STRONG masquerade fails validation",
          rc != 0 and "PLAN_MUTATED_AFTER_COMMIT" in out, out.strip()[:1200])


# ==================================================== C. source model =======

def c_source_model(tmp):
    corpus = sweep_project(tmp)
    data = read_project_manifest(corpus, "demo-sweep")
    ids = [s["source_id"] for s in data["sources"]]
    keys = [s["conversation_key"] for s in data["sources"]]
    check("C8 a multi-conversation project gets stable CONV ids from platform ids",
          ids == ["CONV-001", "CONV-002", "CONV-003"]
          and len(set(keys)) == 3, str(list(zip(ids, keys))))
    titles = [s["title"] for s in data["sources"]]
    check("C9 two conversations with the same title stay separate sources",
          titles.count("Kvalitetsgrinden") == 2
          and keys[1] != keys[2], str(titles))

    inv2 = Path(tmp) / "inventory2.json"
    inv2.write_text(json.dumps([{"url": URL_1, "title": "Pipeline & grind (renamed)"},
                                {"url": URL_2}]), encoding="utf-8")
    rc, out = F.project(["declare", "--project", "demo-sweep", "--inventory",
                         str(inv2), "--method", "declared", "--at", "2026-08-30"],
                        corpus)
    data = read_project_manifest(corpus, "demo-sweep")
    check("C10a a re-declare upserts by identity — no duplicate sources",
          rc == 0 and "0 new, 2 already known" in out
          and len(data["sources"]) == 3, out.strip()[:600])
    check("C10b a renamed conversation keeps its id (title is not identity)",
          data["sources"][0]["source_id"] == "CONV-001"
          and "renamed" in data["sources"][0]["title"], str(data["sources"][0]))

    rc, out = capture(corpus, "demo-sweep", "CONV-001", SWEEP_CHAT_1, tmp)
    check("C10c first capture verifies and lands as revision 1",
          rc == 0 and "revision 1" in out and "VERIFIED=YES" in out,
          out.strip()[:600])
    rc, out = capture(corpus, "demo-sweep", "CONV-001", SWEEP_CHAT_1, tmp)
    check("C10d re-capturing identical bytes is a no-op, never a duplicate",
          rc == 0 and "CAPTURE_UNCHANGED" in out, out.strip()[:600])

    rc, out = capture(corpus, "demo-sweep", "CONV-002", SWEEP_CHAT_2, tmp)
    rc, out = capture(corpus, "demo-sweep", "CONV-002", SWEEP_CHAT_2B, tmp,
                      at="2026-08-31")
    data = read_project_manifest(corpus, "demo-sweep")
    conv2 = data["sources"][1]
    check("C11 an updated conversation becomes a traceable second revision",
          rc == 0 and [r["revision"] for r in conv2["revisions"]] == [1, 2]
          and conv2["revisions"][0]["sha256"] != conv2["revisions"][1]["sha256"],
          str(conv2["revisions"]))
    r1 = Path(corpus) / conv2["revisions"][0]["path"]
    check("C12 the old revision's raw bytes survive, byte-identical",
          r1.exists() and F.sha256_file(r1) == conv2["revisions"][0]["sha256"],
          str(r1))
    return corpus


# ======================================================= D. coverage ========

def d_coverage(tmp):
    corpus = sweep_project(tmp)
    capture(corpus, "demo-sweep", "CONV-001", SWEEP_CHAT_1, tmp)
    # CONV-002: a capture that fails format verification — a hard gap.
    rc, out = capture(corpus, "demo-sweep", "CONV-002",
                      "just some text, no message headers", tmp)
    check("D13a a bad capture fails closed to CAPTURED with the reason recorded",
          rc != 0 and "VERIFIED=NO" in out and "hard gap" in out, out.strip()[:800])
    rc, out = F.project(["coverage", "--project", "demo-sweep"], corpus)
    check("D13b a capture failure makes hard completeness FALSE",
          rc != 0 and "SOURCE_COVERAGE_COMPLETE=NO" in out
          and re.search(r"HARD_GAP CONV-002", out), out.strip()[:1500])
    check("D13c the never-captured source is a hard gap too",
          re.search(r"HARD_GAP CONV-003 .*never captured", out) is not None,
          out.strip()[:1500])

    # D14: manifest ↔ tree, both directions.
    stray = Path(corpus) / "_projects" / "demo-sweep" / "sources" / "CONV-001" / "notes.md"
    stray.write_text("unrecorded\n", encoding="utf-8")
    rc, out = F.project(["validate", "--project", "demo-sweep"], corpus)
    check("D14a an unrecorded file under sources/ fails the tree match",
          rc != 0 and "MANIFEST_TREE_MISMATCH" in out and "notes.md" in out,
          out.strip()[:1200])
    stray.unlink()
    recorded = Path(corpus) / "_projects" / "demo-sweep" / "sources" / "CONV-001" / "conversation.md"
    moved = recorded.read_bytes()
    recorded.unlink()
    rc, out = F.project(["validate", "--project", "demo-sweep"], corpus)
    check("D14b a missing recorded revision file fails validation",
          rc != 0 and "SOURCE_FILE_MISSING" in out, out.strip()[:1200])
    recorded.write_bytes(moved)

    # D15: an interrupted sweep resumes from the manifest alone.
    rc, out = F.project(["status", "--project", "demo-sweep"], corpus)
    check("D15 status names exactly what remains after an interruption",
          "re-capture CONV-002" in out and "capture CONV-003" in out
          and "extract CONV-001" in out, out.strip()[:1500])

    # D16: a hand-asserted COMPLETE fails validation.
    data = read_project_manifest(corpus, "demo-sweep")
    data["project_status"] = "COMPLETE"
    data["sources"][2]["state"] = "COMPLETE"
    write_project_manifest(corpus, "demo-sweep", data)
    rc, out = F.project(["validate", "--project", "demo-sweep"], corpus)
    check("D16 a false COMPLETE (project and source) fails for its own reason",
          rc != 0 and out.count("FALSE_COMPLETENESS") >= 2, out.strip()[:1500])


# ==================================================== E. idea routing =======

def e_idea_routing(tmp):
    corpus = sweep_project(tmp)
    capture(corpus, "demo-sweep", "CONV-001", SWEEP_CHAT_1, tmp)
    capture(corpus, "demo-sweep", "CONV-002", SWEEP_CHAT_2, tmp)
    capture(corpus, "demo-sweep", "CONV-003", SWEEP_CHAT_2B, tmp)

    # E17: one chat → two ideas (both packages carry the conversation as an episode).
    deliver_idea(corpus, "export-pipeline", [SWEEP_CHAT_1])
    deliver_idea(corpus, "quality-gate", [SWEEP_CHAT_1, SWEEP_CHAT_2])
    upsert_index(corpus, "export-pipeline")
    upsert_index(corpus, "quality-gate")
    rc, out = F.project(["mark-extracted", "--project", "demo-sweep",
                         "--source", "CONV-001",
                         "--ideas", "export-pipeline,quality-gate",
                         "--at", "2026-08-30"], corpus)
    check("E17 one conversation can produce two ideas, both hash-linked",
          rc == 0 and "export-pipeline, quality-gate" in out, out.strip()[:600])

    # E18: a second chat CONTINUE_EXISTING into the same idea.
    rc, out = F.project(["mark-extracted", "--project", "demo-sweep",
                         "--source", "CONV-002", "--ideas", "quality-gate",
                         "--at", "2026-08-30"], corpus)
    check("E18 a second conversation continues the same idea — no new slug",
          rc == 0 and not (Path(corpus) / "quality-gate-2").exists(),
          out.strip()[:600])

    # a conversation that produced nothing durable must say so.
    rc, out = F.project(["mark-extracted", "--project", "demo-sweep",
                         "--source", "CONV-003", "--no-ideas"], corpus)
    check("E18b no-ideas without a note is refused",
          rc != 0 and "must say so explicitly" in out, out.strip()[:400])
    rc, out = F.project(["mark-extracted", "--project", "demo-sweep",
                         "--source", "CONV-003", "--no-ideas",
                         "--note", "duplicate brainstorm of CONV-002; queued"], corpus)
    check("E18c no-ideas with an explicit note is recorded",
          rc == 0, out.strip()[:400])

    # E19: ambiguity is queued — and the rest of the sweep continues.
    queue = Path(corpus) / "_projects" / "demo-sweep" / "review-queue.md"
    queue.write_text(review_queue_doc("demo-sweep", [
        rq_block("RQ-001",
                 issue="CONV-003 may be a CONTINUE_EXISTING of quality-gate, or "
                       "merely RELATED",
                 affects="CONV-003, quality-gate",
                 recommendation="hold as no-ideas; owner decides the relation")]),
        encoding="utf-8")
    for source in ("CONV-001", "CONV-002", "CONV-003"):
        F.project(["mark-routed", "--project", "demo-sweep", "--source", source,
                   "--at", "2026-08-30"], corpus)
    rc, out = F.project(["coverage", "--project", "demo-sweep"], corpus)
    check("E19a the queued ambiguity blocks nothing — every source still routed",
          "PROCESSING_COMPLETE=YES" in out and "OPEN_REVIEW_ITEMS=1" in out
          and "RQ-001" in out, out.strip()[:1500])

    # audit at the current inventory revision, then finalize.
    data = read_project_manifest(corpus, "demo-sweep")
    audit = Path(corpus) / "_projects" / "demo-sweep" / "sweep-audit.md"
    audit.write_text(sweep_audit_doc("demo-sweep", [
        F.audit_round(data["inventory_revision"], verdict="PASS",
                      scope="inventory + captures + routing of demo-sweep",
                      at="2026-08-30")]), encoding="utf-8")
    rc, out = F.project(["finalize", "--project", "demo-sweep",
                         "--at", "2026-08-30"], corpus)
    check("E19b open review items end the sweep as COMPLETE_WITH_OPEN_REVIEW",
          rc != 0 and "PROJECT_STATUS=COMPLETE_WITH_OPEN_REVIEW" in out
          and "OPEN_REVIEW_ITEMS=RQ-001" in out, out.strip()[:1500])
    check("E19c the kernel handoff carries the enumeration status, unhidden",
          "ENUMERATION=declared/UNVERIFIED" in out, out.strip()[:1500])

    # E20: duplicate INDEX rows are detected.
    index = Path(corpus) / "INDEX.md"
    index.write_text(index.read_text(encoding="utf-8")
                     + "| quality-gate | dubblett | idea | 2026-08-30 | — |\n",
                     encoding="utf-8")
    rc, out = F.project(["validate", "--project", "demo-sweep"], corpus)
    check("E20 a duplicate INDEX row fails validation",
          rc != 0 and "INDEX_DUPLICATE_ROW" in out and "quality-gate" in out,
          out.strip()[:1200])
    return corpus


# ================================================== F. mode separation ======

def f_mode_separation(tmp):
    corpus = sweep_project(tmp, name="mode-sweep")
    capture(corpus, "mode-sweep", "CONV-001", SWEEP_CHAT_1, tmp)
    capture(corpus, "mode-sweep", "CONV-002", SWEEP_CHAT_2, tmp)
    capture(corpus, "mode-sweep", "CONV-003", SWEEP_CHAT_2B, tmp)
    deliver_idea(corpus, "swept-idea", [SWEEP_CHAT_1])
    upsert_index(corpus, "swept-idea")
    F.project(["mark-extracted", "--project", "mode-sweep", "--source", "CONV-001",
               "--ideas", "swept-idea", "--at", "2026-08-30"], corpus)
    for source, note in (("CONV-002", "background only"),
                         ("CONV-003", "background only")):
        F.project(["mark-extracted", "--project", "mode-sweep", "--source", source,
                   "--no-ideas", "--note", note], corpus)
    for source in ("CONV-001", "CONV-002", "CONV-003"):
        F.project(["mark-routed", "--project", "mode-sweep", "--source", source],
                  corpus)
    data = read_project_manifest(corpus, "mode-sweep")
    audit = Path(corpus) / "_projects" / "mode-sweep" / "sweep-audit.md"
    audit.write_text(sweep_audit_doc("mode-sweep", [
        F.audit_round(data["inventory_revision"], verdict="PASS",
                      scope="full synthetic sweep", at="2026-08-30")]),
        encoding="utf-8")
    rc, out = F.project(["finalize", "--project", "mode-sweep",
                         "--at", "2026-08-30"], corpus)
    check("F24 a full synthetic sweep completes unattended, via CLI alone",
          rc == 0 and "PROJECT_STATUS=COMPLETE" in out, out.strip()[:1200])

    plans = list(Path(corpus).rglob("*-plan-candidate*.md")) \
        + list(Path(corpus).rglob("*-approved-plan*.md"))
    check("F21/F22 the sweep produced no plan candidates and no approved plans",
          plans == [], str(plans))
    fm, _, _ = F.read_frontmatter_text(
        (Path(corpus) / "swept-idea" / "idea-swept-idea.md").read_text(
            encoding="utf-8"))
    check("F21b swept ideas land at status: idea — never clarified, never planned",
          fm.get("status") == "idea", str(fm.get("status")))
    check("F23 single mode still interviews and plans (proven by suites 6–8 and "
          "B6 above)", True)


# ===================================================== G. audit & trust =====

def g_audit_trust(tmp):
    corpus = sweep_project(tmp, name="audit-sweep")
    capture(corpus, "audit-sweep", "CONV-001", SWEEP_CHAT_1, tmp)

    # G25: dangling and hash-unlinked idea provenance.
    data = read_project_manifest(corpus, "audit-sweep")
    data["sources"][0]["ideas"] = ["ghost-idea"]
    write_project_manifest(corpus, "audit-sweep", data)
    rc, out = F.project(["validate", "--project", "audit-sweep"], corpus)
    check("G25a a claimed idea that does not exist fails as dangling provenance",
          rc != 0 and "IDEA_PROVENANCE_DANGLING" in out and "ghost-idea" in out,
          out.strip()[:1200])
    deliver_idea(corpus, "ghost-idea", [SWEEP_CHAT_2])   # wrong bytes on purpose
    rc, out = F.project(["validate", "--project", "audit-sweep"], corpus)
    check("G25b an idea whose episode matches no recorded revision fails the hash link",
          rc != 0 and "IDEA_EPISODE_HASH_UNLINKED" in out, out.strip()[:1200])
    data["sources"][0]["ideas"] = []
    write_project_manifest(corpus, "audit-sweep", data)

    # G26: an audit round may not close its own finding.
    audit = Path(corpus) / "_projects" / "audit-sweep" / "sweep-audit.md"
    audit.write_text(sweep_audit_doc("audit-sweep", [
        F.audit_round(1, verdict="FINDINGS", at="2026-08-30",
                      scope="inventory completeness",
                      findings=[{"id": "FIND-001",
                                 "finding": "SILENT_CAPTURE_FAILURE",
                                 "severity": "material",
                                 "evidence": "CONV-002 was declared and never "
                                             "captured, and no error records it"}],
                      remediated="FIND-001")]), encoding="utf-8")
    rc, out = F.project(["audit", "--project", "audit-sweep"], corpus)
    check("G26 a sweep-audit round cannot close the finding it raised",
          rc != 0 and "SWEEP_AUDIT_FINDING_SELF_CLOSED" in out, out.strip()[:1200])

    # dismissal needs the owner's own words in the review queue.
    audit.write_text(sweep_audit_doc("audit-sweep", [
        F.audit_round(1, verdict="FINDINGS", at="2026-08-30",
                      scope="inventory completeness",
                      findings=[{"id": "FIND-001",
                                 "finding": "SILENT_CAPTURE_FAILURE",
                                 "severity": "material",
                                 "evidence": "CONV-002 declared, never captured"}]),
        F.audit_round(2, verdict="PASS", at="2026-08-31",
                      scope="re-audit after owner ruling",
                      dismissed="FIND-001 (RQ-001)")]), encoding="utf-8")
    rc, out = F.project(["audit", "--project", "audit-sweep"], corpus)
    check("G26b a dismissal citing no owner-answered RQ is refused",
          rc != 0 and "SWEEP_AUDIT_DISMISSED_WITHOUT_OWNER" in out,
          out.strip()[:1200])
    queue = Path(corpus) / "_projects" / "audit-sweep" / "review-queue.md"
    queue.write_text(review_queue_doc("audit-sweep", [
        rq_block("RQ-001", issue="CONV-002 uncapturable?", affects="CONV-002",
                 recommendation="owner decides whether to drop it",
                 owner_answer="Drop it — that chat was a duplicate test thread.")]),
        encoding="utf-8")
    rc, out = F.project(["audit", "--project", "audit-sweep"], corpus)
    check("G26c the same dismissal passes once the RQ carries the owner's answer",
          rc == 0, out.strip()[:1200])

    # G27: a tampered hash in the manifest is caught.
    data = read_project_manifest(corpus, "audit-sweep")
    data["sources"][0]["revisions"][0]["sha256"] = "0" * 64
    write_project_manifest(corpus, "audit-sweep", data)
    rc, out = F.project(["validate", "--project", "audit-sweep"], corpus)
    check("G27 a tampered source hash fails validation",
          rc != 0 and "PROJECT_SOURCE_HASH_MISMATCH" in out, out.strip()[:1200])
    data["sources"][0]["revisions"][0]["sha256"] = F.sha256_file(
        Path(corpus) / data["sources"][0]["revisions"][0]["path"])
    write_project_manifest(corpus, "audit-sweep", data)

    # G28: raw mutation after commit is caught by the git witness.
    F.git_commit_corpus(corpus, "sweep state committed")
    conv = Path(corpus) / "_projects" / "audit-sweep" / "sources" / "CONV-001" / "conversation.md"
    conv.write_text(conv.read_text(encoding="utf-8")
                    .replace("beslutat", "aldrig beslutat"), encoding="utf-8")
    rc, out = F.project(["validate", "--project", "audit-sweep"], corpus)
    check("G28 mutated raw conversation bytes fail against the committed witness",
          rc != 0 and "PROJECT_SOURCE_MUTATED" in out, out.strip()[:1200])
    # (hash mismatch also fires — the mutation changed the bytes; both name CONV-001)

    # queue append-only under the same witness.
    queue.write_text(review_queue_doc("audit-sweep", []), encoding="utf-8")
    rc, out = F.project(["validate", "--project", "audit-sweep"], corpus)
    check("G28b a review-queue item cannot be edited away after commit",
          rc != 0 and "REVIEW_QUEUE_NOT_APPEND_ONLY" in out, out.strip()[:1200])

    # G29: project normalization cannot mint owner authority — the swept idea's own
    # coverage gate still refuses an assistant-only decision.
    corpus29 = Path(tmp) / "g29-corpus"
    corpus29.mkdir(parents=True)
    F.add_control(corpus29)
    mini_pkg(corpus29, "swept-assist", SWEEP_CHAT_1, [
        "- D1. Pipeline first — because the ASSISTANT proposed it (← msg 2).",
    ])
    rc, out = F.context(["coverage", "--slug", "swept-assist"], corpus29)
    check("G29 a swept idea citing only an assistant turn is refused downstream",
          rc != 0 and re.search(
              r"OWNER_BACKING_ASSISTANT_ONLY — D1 .*msg 2", out) is not None,
          out.strip()[:1200])


# ================================================== H. side effects =========

def h_side_effects(tmp):
    corpus = sweep_project(tmp, name="fx-sweep")
    F.git_commit_corpus(corpus, "baseline")
    import subprocess
    head_before = subprocess.run(["git", "-C", str(corpus), "rev-parse", "HEAD"],
                                 capture_output=True, text=True).stdout.strip()
    capture(corpus, "fx-sweep", "CONV-001", SWEEP_CHAT_1, tmp)
    F.project(["status", "--project", "fx-sweep"], corpus)
    F.project(["coverage", "--project", "fx-sweep"], corpus)
    F.project(["validate", "--project", "fx-sweep"], corpus)
    head_after = subprocess.run(["git", "-C", str(corpus), "rev-parse", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
    check("H30 the project tooling writes files but never commits the corpus",
          head_before == head_after, "%s → %s" % (head_before, head_after))
    check("H31 every command in this suite ran against a tmp --corpus "
          "(fixtures.run always passes --corpus and strips the env override)",
          "--corpus" in open(F.__file__, encoding="utf-8").read()
          and "NORTROPIC_INTAKE_CORPUS" in open(F.__file__, encoding="utf-8").read())


# ------------------------------------------------------------------ runner --

def main():
    scenarios = [a_role_aware, b_approval_strength, c_source_model, d_coverage,
                 e_idea_routing, f_mode_separation, g_audit_trust, h_side_effects]
    for scenario in scenarios:
        tmp = tempfile.mkdtemp(prefix="intake-v3-")
        try:
            print("\n=== %s ===" % scenario.__name__)
            scenario(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [(n, d) for n, ok, d in RESULTS if not ok]
    print("\n%d/%d checks passed" % (len(RESULTS) - len(failed), len(RESULTS)))
    if len(RESULTS) < MIN_CHECKS:
        print("FAIL: only %d checks executed (floor %d) — a suite that runs nothing "
              "proves nothing" % (len(RESULTS), MIN_CHECKS))
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
