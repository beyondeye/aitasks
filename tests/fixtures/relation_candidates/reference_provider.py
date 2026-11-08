#!/usr/bin/env python3
"""reference_provider.py - a minimal candidate provider that follows the contract.

The behavioural reference for t1981_2's ``aitask_relation_candidates.sh`` and
the default provider of the worker tests. It implements the SCREENING SNAPSHOT
rule (lib/relation_candidates_contract.py; aidocs/framework/task_relations.md
"Worker API"):

* every body is the current working-tree file;
* a task listed in the manifest's ``stamps`` contributes its plan as of the
  stamp's ``data_commit``; any other task its working-tree plan;
* cards and plan-derived evidence come only from that content;
* the result echoes the digests of what it screened.

Which tasks are candidates is fixed by a spec file (``REF_PROVIDER_SPEC``), not
discovered: candidate DISCOVERY is t1981_2's job; this file pins the contract.

Usage: reference_provider.py <id> --json|--text --cap <n> --snapshot <manifest>

Spec (JSON): {"candidates": [{"id": "11", "sources": ["mention_in"]}],
              "truncated": {"label": ["13"]}, "provider": "fallback",
              "coverage": {"answered": [...], "missing_sources": [...]}}
Modes (REF_PROVIDER_MODE, for tests): ``working`` reads working-tree plans even
for stamped tasks (NON-conforming); ``fail`` exits 3; ``garbage`` prints
non-JSON; ``salt`` adds REF_PROVIDER_SALT to every candidate's evidence.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, ".aitask-scripts", "lib"))

import relation_candidates_contract as cc  # noqa: E402
import relations_schema as rs  # noqa: E402

DEFAULT_COVERAGE = {"answered": ["mention_in", "mention_out", "cites", "token"], "missing_sources": []}


def _task_glob(root, tid, kind):
    base = os.environ.get("TASK_DIR", "aitasks") if kind == "task" else os.environ.get("PLAN_DIR", "aiplans")
    letter = "t" if kind == "task" else "p"
    if "_" in tid:
        parent = tid.split("_")[0]
        pats = [os.path.join(root, base, f"{letter}{parent}", f"{letter}{tid}_*.md")]
    else:
        pats = [os.path.join(root, base, f"{letter}{tid}_*.md")]
    for pat in pats:
        for path in sorted(glob.glob(pat)):
            name = os.path.basename(path)
            if "_" not in tid and re.match(rf"^{letter}{tid}_\d+_", name):
                continue
            return path
    return None


def _read(path):
    if path is None:
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _plan_at(data_repo, commit, root, tid):
    plan_rel = os.path.relpath(os.path.realpath(os.path.join(root, os.environ.get("PLAN_DIR", "aiplans"))),
                               data_repo)
    if "_" in tid:
        parent = tid.split("_")[0]
        where, pat = f"{plan_rel}/p{parent}", re.compile(rf"^p{tid}_.*\.md$")
    else:
        where, pat = plan_rel, re.compile(rf"^p{tid}_(?!\d+_).*\.md$")
    ls = subprocess.run(["git", "-C", data_repo, "ls-tree", "--name-only", f"{commit}:{where}"],
                        capture_output=True, text=True)
    for name in ls.stdout.splitlines():
        if pat.match(name):
            return subprocess.run(["git", "-C", data_repo, "show", f"{commit}:{where}/{name}"],
                                  capture_output=True, text=True, check=True).stdout
    return None


def screened(root, manifest, tid, mode):
    ref = f"aitasks#{tid}"
    body = _read(_task_glob(root, tid, "task"))
    stamp = manifest["stamps"].get(ref)
    if stamp and mode != "working":
        plan = _plan_at(manifest["data_repo"], stamp, root, tid)
    else:
        plan = _read(_task_glob(root, tid, "plan"))
    return body, plan


def card_and_evidence(ref, body, plan, sources, salt):
    nbody = rs.normalize_body(body)
    first = next((ln for ln in nbody.splitlines() if ln.strip()), "")
    card = f"{ref}: {first.strip()}"
    evidence = [{"source": s, "detail": f"{s} evidence for {ref}"} for s in sources]
    if plan is not None:
        nplan = rs.normalize_plan(plan)
        card += " || plan: " + " ".join(ln.strip() for ln in nplan.splitlines() if ln.strip())[:300]
        for ln in nplan.splitlines():
            if "`" in ln:  # plan-derived evidence: backticked tokens
                evidence.append({"source": "token", "detail": ln.strip()[:160], "section": "plan"})
    if salt:
        evidence.append({"source": sources[0], "detail": salt})
    return card, evidence


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--text", action="store_true")
    ap.add_argument("--cap", type=int, default=25)
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args(argv)
    mode = os.environ.get("REF_PROVIDER_MODE", "")
    if mode == "fail":
        sys.stderr.write("reference_provider: forced failure\n")
        return 3
    if mode == "garbage":
        print("this is not json")
        return 0
    root = os.getcwd()
    with open(args.snapshot, encoding="utf-8") as fh:
        manifest = cc.validate_snapshot(json.load(fh))
    with open(os.environ["REF_PROVIDER_SPEC"], encoding="utf-8") as fh:
        spec = json.load(fh)
    salt = os.environ.get("REF_PROVIDER_SALT", "") if mode == "salt" else ""
    tid = rs.norm_id(args.id)
    sbody, splan = screened(root, manifest, tid, mode)
    result = {
        "schema": cc.SCHEMA, "source": f"aitasks#{tid}",
        "provider": {"path": spec.get("provider", "fallback"), "detail": "reference provider"},
        "coverage": spec.get("coverage", DEFAULT_COVERAGE),
        "cap": args.cap,
        "source_inputs": rs.digests(sbody, splan),
        "candidates": [], "truncated": {"count": 0, "by_class": {}, "inputs": {}},
    }
    for cand in spec.get("candidates", []):
        ctid = rs.norm_id(cand["id"])
        ref = f"aitasks#{ctid}"
        body, plan = screened(root, manifest, ctid, mode)
        card, evidence = card_and_evidence(ref, body, plan, cand["sources"], salt)
        result["candidates"].append({"ref": ref, "sources": cand["sources"], "card": card,
                                     "evidence": evidence, "inputs": rs.digests(body, plan)})
    for cls, ids in spec.get("truncated", {}).items():
        refs = [f"aitasks#{rs.norm_id(i)}" for i in ids]
        result["truncated"]["by_class"][cls] = refs
        for i, ref in zip(ids, refs):
            body, plan = screened(root, manifest, rs.norm_id(i), mode)
            result["truncated"]["inputs"][ref] = rs.digests(body, plan)
        result["truncated"]["count"] += len(refs)
    try:
        cc.validate(result)
    except cc.ContractError as exc:
        # A spec that declares a core source missing is how tests exercise the
        # worker's refusal: emit it anyway; the CONSUMER must reject it.
        if not str(exc).startswith("core_missing:"):
            raise
    sys.stdout.write(cc.to_text(result) if args.text else cc.to_json(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
