#!/usr/bin/env python3
"""Freeze the shadow ``>q`` baseline for the t2179 experiments.

What it pins, all under ``frozen/`` next to this file:

* both agents' **fast render trees**, copied (the renders are gitignored, so a
  hash alone could not rebuild a sandbox later) — ``frozen/claude/render/`` from
  ``.claude/skills/aitask-shadow-fast-/`` and ``frozen/codex/render/`` from
  ``.agents/skills/aitask-shadow-fast-codex-/``;
* each agent's **production stub**, verbatim — ``frozen/<agent>/stub/SKILL.md``;
* ``frozen/FREEZE.json`` — repo SHA, sha256 of the ``.j2`` source and of every
  frozen file, and the ``>q`` span per agent;
* ``variants/v1_baseline.md`` — the ``>q`` bullet's exact bytes.

It refuses when the ``.j2`` or either stub is dirty in git: the frozen copy must
be reproducible from the recorded SHA. Run from anywhere:

    python3 aidocs/benchmarks/shadow_q/freeze.py [--no-render]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from qspan import extract_q_bullet, find_q_span  # noqa: E402

REPO = HERE.parents[2]

SOURCE_J2 = ".claude/skills/aitask-shadow/SKILL.md.j2"
AGENTS = {
    "claude": {
        "render_src": ".claude/skills/aitask-shadow-fast-",
        "stub_src": ".claude/skills/aitask-shadow/SKILL.md",
        "render_flag": "claude",
        # Paths inside a sandbox, i.e. where each production stub dispatches.
        "stub_dst": ".claude/skills/aitask-shadow/SKILL.md",
        "render_dst": ".claude/skills/aitask-shadow-fast-",
    },
    "codex": {
        "render_src": ".agents/skills/aitask-shadow-fast-codex-",
        "stub_src": ".agents/skills/aitask-shadow/SKILL.md",
        "render_flag": "codex",
        "stub_dst": ".agents/skills/aitask-shadow/SKILL.md",
        "render_dst": ".agents/skills/aitask-shadow-fast-codex-",
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def assert_sources_clean(repo: Path) -> None:
    paths = [SOURCE_J2] + [a["stub_src"] for a in AGENTS.values()]
    dirty = _git(repo, "status", "--porcelain", "--", *paths).strip()
    if dirty:
        raise SystemExit(f"freeze: refusing, source files are dirty:\n{dirty}")


def render(repo: Path) -> None:
    for agent in AGENTS.values():
        subprocess.run(
            [
                "./.aitask-scripts/aitask_skill_render.sh",
                "aitask-shadow",
                "--profile",
                "fast",
                "--agent",
                agent["render_flag"],
            ],
            cwd=repo,
            check=True,
        )


def freeze(repo: Path = REPO, out: Path = HERE, run_render: bool = True) -> dict:
    assert_sources_clean(repo)
    if run_render:
        render(repo)
    frozen = out / "frozen"
    record: dict = {
        "repo_sha": _git(repo, "rev-parse", "HEAD").strip(),
        "source_j2": SOURCE_J2,
        "source_j2_sha256": sha256_file(repo / SOURCE_J2),
        "profile": "fast",
        "agents": {},
    }
    baseline = None
    for name, spec in AGENTS.items():
        dst = frozen / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(repo / spec["render_src"], dst / "render")
        (dst / "stub").mkdir(parents=True)
        shutil.copy2(repo / spec["stub_src"], dst / "stub" / "SKILL.md")
        skill_text = (dst / "render" / "SKILL.md").read_text(encoding="utf-8")
        start, end = find_q_span(skill_text)
        bullet = extract_q_bullet(skill_text)
        if baseline is None:
            baseline = bullet
        elif bullet != baseline:
            raise SystemExit(f"freeze: the {name} >q bullet differs from claude's")
        files = {
            str(p.relative_to(dst)): sha256_file(p)
            for p in sorted(dst.rglob("*"))
            if p.is_file()
        }
        record["agents"][name] = {
            "render_src": spec["render_src"],
            "stub_src": spec["stub_src"],
            "stub_dst": spec["stub_dst"],
            "render_dst": spec["render_dst"],
            "q_span_lines": [start + 1, end],  # 1-based, inclusive
            "files": files,
        }
    variants = out / "variants"
    variants.mkdir(exist_ok=True)
    (variants / "v1_baseline.md").write_text(baseline + "\n", encoding="utf-8")
    record["v1_baseline_sha256"] = sha256_file(variants / "v1_baseline.md")
    (frozen / "FREEZE.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-render", action="store_true", help="skip re-rendering")
    args = ap.parse_args(argv)
    rec = freeze(run_render=not args.no_render)
    print(f"FROZEN:{rec['repo_sha']}")
    for name, a in rec["agents"].items():
        print(f"AGENT:{name}|q_span={a['q_span_lines'][0]}-{a['q_span_lines'][1]}|files={len(a['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
