---
Task: t1957_3_cross_repo_linked_trail_discovery.md
Parent Task: aitasks/t1957_trail_cross_repo_blockers_and_linked_trails.md
Sibling Tasks: aitasks/t1957/t1957_1_*.md, aitasks/t1957/t1957_2_*.md, aitasks/t1957/t1957_4_*.md, aitasks/t1957/t1957_5_*.md
Archived Sibling Plans: aiplans/archived/p1957/p1957_*_*.md
Base branch: main
Output branch: main
---

Parent plan (decisions, linked-trail definition, risk record):
`aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`.
The task file `aitasks/t1957/t1957_3_cross_repo_linked_trail_discovery.md` carries the full context,
reference files and line anchors.


## t1957_3 — Cross-repo linked-trail discovery helper

Files: new `.aitask-scripts/lib/trail_links.py`, `tests/test_trail_links.py`
(+ whitelist/extension-point entries per
`aidocs/framework/aitasks_extension_points.md` if a new helper script needs
registering — it is a Python lib with a `__main__`, check the doc).

**Linked-trail relation** (both directions, `proj#id` members count):
trail B (repo Y) is linked to trail A (repo X) when any of
- (fwd-xdeps) a member of A has `xdeprepo: Y` and an `xdeps` id that is a member of B;
- (fwd-member) A has a cross-repo member `Y#id` that is a member of B;
- (rev-xdeps) a member of B has `xdeprepo: X` and an `xdeps` id that is a member of A;
- (rev-member) B has a cross-repo member `X#id` that is a member of A.
Identity is compared as `(realpath(project root), task_id)` — project names
are resolved through `trail_gather.ProjectRoots` (registry resolver), never by
string equality of names (registry name may differ from `project.name`).

1. `python3 trail_links.py export` — run with `cwd=<repo root>`,
   `TASK_DIR=aitasks`: `discover_trails()` there and print one JSON object
   `{local_project, trails:[{handle, name, owner_id, load_error,
   members:[ref...], member_xdeps:{ref:{xdeprepo, xdeps:[...]}}}]}`
   (member xdeps read from that repo's task files, active + archived).
   Uses **this checkout's** Python with the other repo's artifact CLI
   (cwd-relative), so the export works against a repo on an older framework.
2. `find_linked_trails(local_doc, local_member_meta, local_root, exports) ->
   list[LinkedTrail(project, root, handle, name, reasons[str])]` — pure, takes
   exported data, unit-testable.
   `scan_linked_trails(local_doc, ...) -> LinkScan(links, errors, complete)`
   (thread use only). **Candidate projects** = registry entries
   (`aitask_project_resolve.sh list`, self excluded by realpath) ∪ every
   `xdeprepo` named by a local member ∪ the project of every cross-repo member
   ref — so a project the trail directly points at is searched (or reported)
   even when it is missing from the registry. **Nothing is skipped silently:**
   each candidate that cannot be searched becomes a
   `ProjectScanError(project, kind, detail)` with `kind` ∈ `stale` (registered
   path moved/missing), `not_found` (name does not resolve), `export_failed`,
   `timeout`. `complete = not errors`. Export per project via
   `subprocess.run([sys.executable, __file__, "export"], cwd=root, timeout=30)`.
3. Tests: pure relation over synthetic exports for all four directions;
   name≠project.name resolution; unparseable refs ignored; self excluded;
   **a local member with `xdeprepo` naming a STALE registered project →
   `complete=False`, one `stale` error, no links** (and the same for a
   `not_found` xdeprepo); successful empty scan → `complete=True`, no errors;
   export against a fixture repo (tmp git repo with a stored trail) — reuse the
   trail fixtures from `tests/test_trail_discovery.py`.

### Post-phase (risk mitigations)
1. [measure_linked_scan_latency] Time `scan_linked_trails` against the real registry on this host (`aitasks_mobile` is registered) and record per-project export timings in t1957_3's Final Implementation Notes. If a single scan exceeds ~2s, add a per-project progress callback and a session-lifetime cache of exports (invalidated by an explicit rescan) before closing the child.

## Step 9 reference

After implementation and review, follow task-workflow Step 9 (merge if
applicable, archive this child; the parent t1957 archives automatically when its
last child is archived).
