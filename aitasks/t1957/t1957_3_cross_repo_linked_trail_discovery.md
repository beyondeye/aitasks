---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [trails, cross_repo]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1957
implemented_with: claudecode/opus5_5
created_at: 2026-10-12 21:32
updated_at: 2026-10-13 15:28
---

## Context

Part of t1957 (parent plan:
`aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`). The jump
action (t1957_4) needs to find, for the active trail in this repo, the
**linked** trails in other registered repos.

`lib/trail_discovery.discover_trails()` is bound to cwd and `TASK_DIR`
(`ARTIFACT_SCRIPT` is cwd-relative, `_tasks_dir()` reads `TASK_DIR`), returns
`(infos, unreadable)`; `TrailInfo` has `handle, owner_id, name, doc, load_error,
…` and no member list (members = `trail_entry_refs(doc)`, canonical
`<project>#<id>`). There is no CLI entry point. Project roots resolve through
`trail_gather.ProjectRoots` (wraps `aitask_project_resolve.sh`, maps the local
project to `Path(".")`); `aitask_project_resolve.sh list` prints
`PROJECT:<name>:<path>:<status>`. `xdeprepo` is a single project name per task,
`xdeps` a list of ids in that repo (normalize a leading `t`). The local project
name is `project.name` in `aitasks/metadata/project_config.yaml`, which may
differ from the registry name.

## Linked-trail relation

Trail B (repo Y) is linked to trail A (repo X) when any of:
- (fwd-xdeps) a member of A has `xdeprepo: Y` and an `xdeps` id that is a member of B;
- (fwd-member) A has a cross-repo member `Y#id` that is a member of B;
- (rev-xdeps) a member of B has `xdeprepo: X` and an `xdeps` id that is a member of A;
- (rev-member) B has a cross-repo member `X#id` that is a member of A.
Identity compares `(realpath(project root), task_id)`; names are always resolved
to roots, never compared as strings.

## Key Files to Modify

- New `.aitask-scripts/lib/trail_links.py` (+ `__main__` with `export`).
- New `tests/test_trail_links.py`.
- Check `aidocs/framework/aitasks_extension_points.md` for any registration a
  new lib module with a CLI mode needs (whitelists, etc.).

## Reference Files for Patterns

- `lib/trail_discovery.py` (`discover_trails` ~326, `trail_entry_refs` ~77,
  `_iter_trail_frontmatter_records` ~195).
- `lib/trail_gather.py` (`ProjectRoots` ~289-312, `canonical_id` ~276,
  `local_project_name` ~260).
- `lib/cross_repo_notation.py` (`parse_ref`).
- Trail fixtures in `tests/test_trail_discovery.py`.

## Implementation Plan

1. `python3 trail_links.py export` (run with `cwd=<repo root>`,
   `TASK_DIR=aitasks`): `discover_trails()` there; print JSON
   `{local_project, trails:[{handle, name, owner_id, load_error, members:[ref…],
   member_xdeps:{ref:{xdeprepo, xdeps:[…]}}}]}` (member xdeps from that repo's
   task files, active + archived). Uses this checkout's Python with the other
   repo's artifact CLI.
2. Pure `find_linked_trails(local_doc, local_member_meta, local_root, exports)
   -> list[LinkedTrail(project, root, handle, name, reasons)]`.
3. `scan_linked_trails(...) -> LinkScan(links, errors, complete)` (worker-thread
   use only). Candidates = registry entries (self excluded by realpath) ∪ every
   `xdeprepo` named by a local member ∪ the project of every cross-repo member
   ref. **Nothing is skipped silently**: an unsearchable candidate becomes
   `ProjectScanError(project, kind, detail)`, `kind` ∈ `stale`, `not_found`,
   `export_failed`, `timeout`; `complete = not errors`. Export per project via
   `subprocess.run([sys.executable, __file__, "export"], cwd=root, timeout=30)`.
4. Tests: all four directions over synthetic exports; name ≠ project.name
   resolution; unparseable refs ignored; self excluded; local member with
   `xdeprepo` naming a STALE registered project → `complete=False`, one `stale`
   error, no links (same for `not_found`); successful empty scan →
   `complete=True`; export against a fixture repo with a stored trail.
5. **Post-phase [measure_linked_scan_latency]** (risk mitigation, do LAST): time
   `scan_linked_trails` against the real registry on this host
   (`aitasks_mobile` is registered) and record per-project export timings in
   the plan's Final Implementation Notes. If a single scan exceeds ~2s, add a
   per-project progress callback and a session-lifetime export cache
   (invalidated by an explicit rescan) before closing this child.

## Verification

- `python3 -m pytest tests/test_trail_links.py tests/test_trail_discovery.py -q`.
- Manual: `cd <aitasks_mobile root> && TASK_DIR=aitasks python3 <this repo>/.aitask-scripts/lib/trail_links.py export` prints valid JSON.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-13T12:28:07Z status=pass attempt=1 type=human
