---
priority: medium
effort: high
depends: []
xdeps: [93]
xdeprepo: aitasks_go
issue_type: feature
status: Ready
labels: [go_engine, install, skills, task_relations]
gates: [risk_evaluated]
created_at: 2026-11-04 08:54
updated_at: 2026-11-04 08:54
---

## Goal

Make the task-query engine (aitasks_go#93) usable from the framework. Install
it, expose it through `ait`, keep a fallback for when it is absent, and wire it
into the skills that search tasks today.

## Context — read first

- `aidocs/framework/task_search_analysis.md` (committed in `aa67dd50e`): why
  grep-based task search costs what it does, the comparison with GitHub Issues
  and beads, the measurements, and the layered direction. This task is the
  framework-side half of layers L1 and L2.
- The engine itself is **aitasks_go#93**. The work is split along the
  repository line: engine in aitasks_go, shim, installer, skills and docs here.
  This task waits for it through `xdeps`. Read its landed interface (the
  `goengines/README.md` *Interfaces* mirror) before planning, because verb
  names and the output protocol are settled there.
- How candidates become recorded relations, and how the notify list at task
  completion is consumed, is **t1981**'s decision. Coordinate; do not
  duplicate.

## Scope

1. **Install.** `lib/engine_install.sh` stages, verifies and publishes only
   `ait-testmap` (plus its `.sha256` sidecar). Extend it to the new executable
   while keeping SHA256SUMS verification, the `.dev` marker, `ait engine prune`,
   the `ait engine build` dev slot, `--local-engine`, `--force-engine`,
   `--no-testmap` and `AIT_TESTMAP_FETCH=0`. Decide whether those opt-outs
   cover the new binary or it gets its own (the `TESTMAP` names are
   testmap-specific). Read `aidocs/framework/go_engine.md` and
   `aidocs/framework/aitasks_extension_points.md` (install flow, PATH and
   binary shimming) first.
2. **Shim and fallback.** Add an `ait` verb through a
   `.aitask-scripts/aitask_<name>.sh` shim that resolves the engine from the
   slot for `.aitask-scripts/VERSION`, as `aitask_testmap.sh` does. When the
   engine is absent, a fallback must answer. Either a Python path built on
   `lib/plan_paths.py` and `lib/task_yaml.py` covers the subset it can, or a
   distinct absent-engine line tells consumers to fall back to grep. Every
   answer states which path produced it.
3. **Helper whitelist.** The touchpoints for a helper invoked from skills
   (`aidocs/framework/aitasks_extension_points.md`).
4. **Skill integration** (Claude Code first; separate port tasks for the other
   agent trees):
   - `/aitask-note` Related Task Discovery: candidates from `mentioned-by`,
     `mentions` and `cited-by`, triaged with cards, instead of titles, labels
     and the first ~5 body lines.
   - `/aitask-trail`: cards for `new_related_task` neighbours, and member path
     surfaces for shared-file collisions. Today the gatherer extracts paths
     for in-flight tasks only. Extend the gatherer's pinned contract rather
     than forking it.
   - `/aitask-create`: an advisory "does this already exist?" check before
     creating. It never blocks.
   - The notify offer at task completion: candidates only, coordinated with
     t1981.
5. **Docs.** Website docs for the new `ait` verb, following
   `aidocs/framework/documentation_conventions.md`. Regenerate goldens for any
   `.md.j2` or procedure change in the same commit.

## Requirements

- Helpers report evidence; the agent judges. No relevance thresholds in skill
  prose.
- The fallback has its own tests, run with the engine absent. Exit statuses
  survive pipelines (check `PIPESTATUS`, never `| tail`).
- Tests never touch a real `~/.aitask` or `AITASKS_HOME`; use a scratch `HOME`.
- Where the Python fallback and the engine overlap they must agree. Decide at
  planning whether that is pinned here or by aitasks_go#93's differential test.

## Out of scope

- The relations store and its consumption policy (t1981).
- Semantic re-ranking.
