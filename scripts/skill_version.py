#!/usr/bin/env python3
"""Skill version and drift guard — the installed skill answers for itself.

    skill_version.py check [--require-frozen]
    skill_version.py stamp          # print the identities to paste into the freeze

The 2026-09-11 gap analysis measured the failure this guard closes: the installed
skill sat at v4.0 (`4f15826`) while origin/main had moved three versions (v4.1–v4.3)
and the corpus, the CI workflow and the mapping pilot were all built against the
newer contract. The installed validators refused the published corpus; SKILL.md
still read `v4.0 FROZEN`. Nothing said so until someone ran both by hand.

What is compared, all from the local repository (no network, no clock):

    REGISTERED   the version and identities SKILL.md's freeze block records
    INSTALLED    HEAD of the checkout this file lives in, and the tree of scripts/
    ORIGIN       refs/remotes/origin/main, when the checkout has fetched it

The runtime surface is `scripts/` — the validators and adapters a corpus, a CI
workflow or a pilot actually execute — so the identity that must not drift silently
is the TREE of scripts/ at the registered freeze commit, recorded in SKILL.md as
`SKILL_SCRIPTS_TREE`. `check` reports:

    SKILL_DRIFT=NONE               scripts/ is byte-identical to the registered tree
    SKILL_DRIFT=UNCOMMITTED        scripts/ has working-tree changes (a build in progress)
    SKILL_DRIFT=AHEAD              committed scripts/ differ from the registered tree
                                   (a release that was never frozen, or a freeze
                                   that was never registered)
    SKILL_DRIFT=BEHIND_ORIGIN      origin/main's scripts/ differ from the installed
                                   tree — the published contract moved on
    SKILL_DRIFT=UNKNOWN            no git, or no registration to compare against

Exit 0 on NONE; with --require-frozen exit 1 on anything else. Every other tool
stays silent about this on purpose — a validator that printed a drift warning on
every run would be ignored within a week. The chain (`project_contract.py chain`)
prints the line, and the full-sweep mission passes --require-frozen.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = ROOT / "SKILL.md"

_FIELDS = ("NORTROPIC_INTAKE_VERSION", "ARCHITECTURE_STATE", "FREEZE_DATE",
           "SKILL_MAIN", "SKILL_TREE", "SKILL_SCRIPTS_TREE")


def registered():
    """The freeze block's fields, first occurrence of each (the current freeze)."""
    out = {}
    if not SKILL_MD.exists():
        return out
    text = SKILL_MD.read_text(encoding="utf-8")
    for key in _FIELDS:
        m = re.search(r"^%s=(\S+)" % key, text, re.M)
        if m:
            out[key] = m.group(1).strip()
    return out


def git(*args):
    try:
        r = subprocess.run(["git", "-C", str(ROOT)] + list(args),
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def installed():
    out = {"head": git("rev-parse", "HEAD"),
           "scripts_tree": git("rev-parse", "HEAD:scripts"),
           "dirty_scripts": None, "origin_main": None, "origin_scripts_tree": None}
    if out["head"]:
        status = git("status", "--porcelain", "--", "scripts")
        out["dirty_scripts"] = bool(status)
        if git("rev-parse", "--verify", "-q", "refs/remotes/origin/main"):
            out["origin_main"] = git("rev-parse", "refs/remotes/origin/main")
            out["origin_scripts_tree"] = git("rev-parse", "refs/remotes/origin/main:scripts")
    return out


def contract_surface():
    """The versioned contract surfaces the runtime speaks — read from the code."""
    sys.path.insert(0, str(ROOT / "scripts"))
    surface = {}
    try:
        import rnd_contract
        surface["rnd-ir"] = max(rnd_contract.SUPPORTED_IR_VERSIONS)
    except Exception:                                            # noqa: BLE001
        surface["rnd-ir"] = "?"
    try:
        import project_contract
        surface["project-manifest"] = project_contract.PROJECT_MANIFEST_VERSION
    except Exception:                                            # noqa: BLE001
        surface["project-manifest"] = "?"
    try:
        import attachment_surface
        surface["attachment-manifest"] = attachment_surface.ATTACHMENT_MANIFEST_VERSION
    except Exception:                                            # noqa: BLE001
        surface["attachment-manifest"] = "?"
    try:
        import obsidian_projection
        surface["projection"] = obsidian_projection.PROJECTION_VERSION
    except Exception:                                            # noqa: BLE001
        surface["projection"] = "?"
    return surface


def drift(reg, inst):
    if not inst.get("head"):
        return "UNKNOWN"
    if inst.get("dirty_scripts"):
        return "UNCOMMITTED"
    want = reg.get("SKILL_SCRIPTS_TREE")
    if not want:
        return "UNKNOWN"
    if inst.get("scripts_tree") != want:
        return "AHEAD"
    if inst.get("origin_scripts_tree") and inst["origin_scripts_tree"] != inst["scripts_tree"]:
        return "BEHIND_ORIGIN"
    return "NONE"


def report(require_frozen=False):
    reg = registered()
    inst = installed()
    state = drift(reg, inst)
    surface = contract_surface()
    lines = [
        "INTAKE_SKILL_VERSION=%s" % reg.get("NORTROPIC_INTAKE_VERSION", "?"),
        "REGISTERED_SKILL_MAIN=%s" % reg.get("SKILL_MAIN", "?"),
        "REGISTERED_SCRIPTS_TREE=%s" % reg.get("SKILL_SCRIPTS_TREE", "?"),
        "INSTALLED_HEAD=%s" % (inst.get("head") or "?"),
        "INSTALLED_SCRIPTS_TREE=%s" % (inst.get("scripts_tree") or "?"),
        "ORIGIN_MAIN=%s" % (inst.get("origin_main") or "not fetched"),
        "CONTRACT_SURFACE=%s" % " ".join("%s:%s" % (k, surface[k])
                                          for k in ("rnd-ir", "project-manifest",
                                                    "attachment-manifest", "projection")),
        "SKILL_DRIFT=%s" % state,
    ]
    return lines, state, (state == "NONE" or not require_frozen)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("check")
    p.add_argument("--require-frozen", action="store_true")
    sub.add_parser("stamp")
    args = ap.parse_args(argv)
    if args.cmd == "stamp":
        inst = installed()
        print("SKILL_MAIN=%s" % (inst.get("head") or "?"))
        print("SKILL_TREE=%s" % (git("rev-parse", "HEAD^{tree}") or "?"))
        print("SKILL_SCRIPTS_TREE=%s" % (inst.get("scripts_tree") or "?"))
        return 0
    lines, state, ok = report(getattr(args, "require_frozen", False))
    for ln in lines:
        print(ln)
    if state != "NONE":
        print("The installed skill and the registered contract differ (%s). A corpus, "
              "a CI workflow or a pilot validated against one is not validated against "
              "the other — say which, or fetch/freeze until they agree." % state)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
