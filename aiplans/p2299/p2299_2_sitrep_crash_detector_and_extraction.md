---
Task: t2299_2_sitrep_crash_detector_and_extraction.md
Parent Task: aitasks/t2299_sitrep_track_crashed_agents_for_resume.md
Sibling Tasks: aitasks/t2299/t2299_1_*.md, aitasks/t2299/t2299_3_*.md, aitasks/t2299/t2299_4_*.md
Archived Sibling Plans: aiplans/archived/p2299/p2299_*_*.md
Base branch: main
Output branch: main
---

# Plan: crash detector and extraction (t2299_2)

## Context

This child adds the deterministic pass that classifies every locked or
Implementing task through ONE ordered decision table. For each stored category
it extracts source-tagged evidence and maintains one `recover:t<N>` item, using
t2299_1's atomic `recovery-apply`.

The task file carries the decision table, the episode-key rules, the strict
input rules, the evidence list, the output grammar and the full test list; that
spec is authoritative. This plan orders the work. Read t2299_1's archived plan
first (verb results, ref helpers).

## Steps

1. **`lib/sitrep_crash.py` skeleton.** Stdlib only, plus lib imports
   (`sitrep_todo`, `gate_ledger`, `archive_iter`, `task_yaml`,
   `agent_sessions`, `parallel_admission_collect`). Define dataclasses
   `LockRec(id, fields, state: ok|error, why)`, `TaskRec(id, path, status,
   archived, folded, meta, text, state, why)`, and `Facts`, and the constants
   `CATEGORIES` and `ROW_*`.
2. **Strict readers.**
   - `read_locks(root)`:
     - resolve the ref (origin, then local);
     - `ls-tree -z` → `(oid, name)`;
     - one `cat-file --batch` subprocess fed all oids → parse each blob with a strict `key: value` reader;
     - each failure becomes `LockRec(state=error)`;
     - a missing ref or an unreadable tree raises `SourceError`.
   - `read_tasks(root, ids)`:
     - walk the active tree;
     - fall back to `archive_iter.find_archived_markdown_by_id` for locked ids with no active file;
     - parse with `task_yaml.parse_frontmatter`;
     - a missing or invalid `status`, or any `OSError`, becomes `TaskRec(state=error)`.
3. **Classification.**
   - `episode_key(lock, recorded)` follows the three rules in the task file.
   - `recovery_verdict(facts) -> Verdict(row, category, state, outcome)` implements the 9 rows in order.
   - Liveness goes through `parallel_admission_collect.classify_liveness`, which applies the host guard first, then `lock_holder_liveness`.
   - Make the liveness function injectable (a module-level hook) so the unit tests can be table-driven. The end-to-end tests still use real PIDs.
   - `format_outcome` / `parse_outcome`.
4. **Evidence extractors**, each returning `(value, source_tags)`:
   - `phase_of`, from the ledger text: `has_gate_markers`, then `resume_point_from_text`. For POSTIMPL, `read_task_gate_state(task_file, registry_file, current_digest=memo)` gives `archive_pending`.
   - `plan_of`: `plan`, `plan_signature` (`plan_approved` in `stale_signed`) and `plan_fresh`, as follows:
     - file list = `file_references:` plus the backticked or bare tokens in the plan or task that are in the `git ls-files` set;
     - baseline = `premise_baseline`, else `rev-list -1 --before=<approval ts>`;
     - commit count from `git log <base>..HEAD -- files`;
     - dirty referenced files: for the shared tree only, intersect the referenced files with `git status`.
   - `work_of`:
     - `aitask_task_worktree.sh resolve`;
     - the shared-tree `git status` (computed once per pass);
     - attribution by naming;
     - the unattributed bucket;
     - overlaps across all Implementing tasks;
     - the `(t<N>)` commit count;
     - the `aitask/<task_name>` head.
   - `pane_of`: an `agent_sessions.load_safe()` match → the tail of the capture.
5. **Rendering.** Write `survey_passage(...)`, a deterministic text block,
   together with `title_of`, `group_of` / `rank_of` and `context_of`. Check
   that the context fits within the writer's limits (background ≤ 400 bytes,
   entry ≤ 2000).
6. **Apply loop.**
   1. Take one lock-free `list` read: the current items by ref, plus each item's rev and recorded incarnation (from `context c<N>`, or by parsing `todo.md` with `sitrep_todo.load_todo_for_read`).
   2. Classify every task.
   3. For each task:
      - a stored category: `retain` its passages, then make ONE `recovery-apply`;
      - a done or unknown row with an existing open item: the same verb with the state and outcome only, no context;
      - dismissed items: never written except through a reopening apply.
   4. Map the writer's replies to `CRASH_ITEM` result words; `STALE` becomes `CRASH_WARN:…|stale`.
   5. Fault seam: `AITASK_SITREP_CRASH_FAULT=before_apply|after_retain` exits 1 at that point.
7. **CLI.**
   - Add `cmd_crashed` to `aitask_sitrep_harvest.sh`, following the `cmd_capture` / `run_source` pattern: plan → `WORK:` → `with_harvest_lock`.
   - `--dry-run` skips the lock.
   - Add the `main()` case.
   - Add the header contract.
   - Python entry: `sitrep_crash.py plan|apply|dry-run`.
8. **Tests.**
   - `tests/test_sitrep_crash.py`, unit tests:
     - the decision rows, driven by the injectable liveness hook;
     - episode keys;
     - the outcome round trip;
     - plan freshness with scratch git;
     - the attribution, overlap and unattributed control;
     - the strict readers given corrupt blobs and unreadable files (chmod 000, skipped when root).
   - `tests/test_sitrep_crash.sh`, end to end:
     - a scratch repo with lock blobs committed to a branch, plus `update-ref refs/remotes/origin/aitask-locks`;
     - a dead PID from `sleep & kill; wait`;
     - a live PID from `sleep 300 &`, with the starttime captured through `pid_anchor.sh`;
     - the real writer;
     - every scenario from the task's Verification list, including 3-pass stability, dismissal races (dismiss through the writer between a `--dry-run` read and the real run, then force a `STALE` via the fault seam) and `--dry-run` writing nothing.
9. **Live dry run** in this repo (read-only). Re-survey first and record the result in Final Implementation Notes.

## Verification

- `python3 -m pytest tests/test_sitrep_crash.py -q`
- `bash tests/test_sitrep_crash.sh`
- `bash tests/test_sitrep_harvest.sh` (verb dispatch unchanged)
- `bash tests/test_sitrep_todo.sh`
- `shellcheck .aitask-scripts/aitask_sitrep_harvest.sh`
- `bash tests/test_no_lib_to_tui_import.sh`
- `tests/test_gate_ledger_only_surfaces.py`, if `read_task_gate_state` call sites are registered there (add this one if the guard requires it)
- `./.aitask-scripts/aitask_sitrep_harvest.sh crashed --root "$PWD" --dry-run`

## Risk

### Code-health risk: medium
- The extraction shells out per task: `resolve`, `git log` and `cat-file`. A repo with many in-flight tasks could make the monitor tick slow. · severity: medium · → mitigation: one shared `git status`, one `cat-file --batch`, memoized digests, and a per-pass budget/timeout honoured by t2299_3's caller
- The path-naming attribution heuristic can mis-attribute files. · severity: medium · → mitigation: by design the evidence is source-tagged and advisory, unattributed files are kept separate, and a control test covers it
- Plan-path token extraction could match prose. · severity: low · → mitigation: intersect with `git ls-files`

### Goal-achievement risk: medium
- The live survey is moment-relative. Acceptance numbers may differ by implementation time. · severity: low · → mitigation: re-survey before checking
- `plan_signature` depends on witness digests that may be absent for workflow-recorded `plan_approved`; it would then read `none`, not `valid`. · severity: medium · → mitigation: report `none` honestly and keep it out of the "fresh" criterion unless it is `stale`

## Step 9

Post-implementation: commit this task's paths only (`feature: … (t2299_2)`); archive via Step 9.
