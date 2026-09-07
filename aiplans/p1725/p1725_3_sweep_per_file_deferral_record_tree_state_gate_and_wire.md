---
Task: t1725_3_sweep_per_file_deferral_record_tree_state_gate_and_wire.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_1_*.md, aitasks/t1725/t1725_2_*.md, aitasks/t1725/t1725_4_*.md, aitasks/t1725/t1725_5_*.md, aitasks/t1725/t1725_6_*.md
Archived Sibling Plans: aiplans/archived/p1725/p1725_*_*.md
Base branch: main
Output branch: main
---

# t1725_3 — per-file deferral record, tree-state rebase gate, wire + parser, `--commit-for-task`

Parent plan: `aiplans/p1725_sync_deferrals_actionable_and_safe_to_continue.md`,
section "Child 3" (authoritative for every contract below). Findings 1 (shell), 2,
3, 4 / AC1 (wire), AC2. No sibling dependency; t1725_4 and t1725_5 build on it.
Related: t1696 (hint wording) — this task implements the sync-side fast-forward it
suggested; a note was sent to t1696.

## Files

`.aitask-scripts/aitask_sync.sh` (`batch_out` ~166, `_protect` ~279, `_pct_encode`
~307, `_lock_snapshot` ~394, `_holder_verdict` ~424, `_sweep_dirty` ~599,
`_commit_group` ~753, `report_skipped` ~856, `do_push` ~1152, `main` ~1221, seams
~246-277, `show_help` ~66); `.aitask-scripts/lib/sync_action_runner.py`;
`tests/test_sync_deferral_and_quarantine.sh`; `tests/lib/sync_fixture.sh`;
`tests/test_sync_action_runner.py`; `task_utils.sh:get_user_email` (~1533),
`task_data_converge` (~943, the ff-only rule mirrored here).

### Pre-phase (risk mitigations)

1. [characterize_sync_paths_never_empty_stdout] Before any restructure: a forced-path
   harness (`tests/test_sync_protect_paths.sh`) drives every `_protect "<reason>"`
   literal — scanned from the source — through `aitask_sync.sh --batch` under `set -u`
   (planted live lock / unreachable origin for the lock branch / staged path /
   ownerless file / `pre_group_commit` seam content change / `pre_commit_phase` seam
   lock acquisition) and asserts stdout is non-empty and starts with a recognised
   token every time. Commit green against the current script, then restructure.

## Steps

2. **Record (3a).** Parallel arrays `PROT_REASON PROT_TASK PROT_PATH PROT_STATE
   PROT_HOLDER PROT_EMAIL PROT_HOST PROT_PID PROT_PANE PROT_PANE_STATE PROT_ACTION`
   replace `PROTECTED_DIRTY`. `_protect <reason> <task> <path> <tree_state> <line>`;
   per-task protections call it once per path of the task; path-less ones
   (`scan_failed`, `lock_contended`) record `path=""`, `tree_state=unknown`.
   `tree_state`: porcelain `??` → `untracked`, else `tracked`. `_lock_snapshot` keeps
   `LOCK_EMAIL`. `PROT_PANE` / `PROT_PANE_STATE` stay empty (t1725_4).
3. **Holder class (3b).** `_holder_class <tid>` → `self|other|remote|unverified|none`;
   `self` only with every identity present and verified (lock email non-empty ==
   `get_user_email` non-empty; lock host non-empty, not `unknown`, == `hostname`);
   anything missing → `unverified`. Per-class human line / action text as in the
   task body; "held by other sessions" removed everywhere.
4. **Gate (3c).** `_rebase_blocked` (inputs `local_ahead`, `remote_ahead`,
   `incoming=$(task_git diff --name-only HEAD..@{u})` after `do_fetch`): blocked when
   any record is `unknown`; or `tracked` and `local_ahead > 0`; or its path ∈
   `incoming`. `main`: not blocked & `local_ahead == 0` → `task_git merge --ff-only
   --quiet @{u}` (`did_pull=true`); not blocked & `local_ahead > 0` → `do_pull_rebase`.
   Rewrite the ~1269 comment. Replace the `do_push` ~1186 site with the same
   predicate.
5. **Push retry re-gate.** In `do_push`'s rejection branch: after the retry fetch
   recompute the three inputs, re-run `_rebase_blocked` → blocked: emit the deferral,
   return 2; else `do_pull_rebase` (remove the bare `pull --rebase` at ~1198). Add
   the marker-gated `pre_push` seam before the first push.
6. **Wire (3d).** Status line `DEFERRED:protected_dirty:<N> file(s) block the rebase:
   live_lock=<k> …` (reason set unchanged). Then `batch_detail` lines (new helper,
   not `batch_out`):
   `DEFERRED_FILE:<sub_reason>|<task>|<path>|<tree_state>|<holder>|<email>|<host>|<pid>|<pane>|<pane_state>|<action>`
   — path/action/email/host/pane `_pct_encode`d; closed/numeric fields bare. One
   `_emit_protected_deferral` used by `main` and `do_push`. `report_skipped` stays.
7. **Parser (3e).** `DeferredFile` (one field per column), `SyncResult.deferred_files`,
   `DEFERRED_FILE_REASONS` (closed; scan test over `_protect\s+"([a-z_]+)"`),
   continuation lines collected only after a `DEFERRED` first line; unknown
   sub-reason / bad closed-field value / malformed line → `STATUS_ERROR`; first-line
   `DEFERRED_FILE:` → unknown status; decode every encoded field, `%25` last.
8. **Flags (3f).** `--commit-for-task <id>[,…]` evaluated inside `_holder_verdict` at
   both snapshots (`self` → `free`; else refused on stderr); bypasses neither 5a.3 nor
   5a.4; prints the live-session warning when it commits. `--expect-path <enc>`
   (repeatable, never CSV): group ≠ set → `_protect "commit_scope_changed"`.
   `--require-waiting`: in `_commit_group` after 5a.3, re-probe via t1725_4's
   helpers; not `waiting_*` (or no probe available) → `_protect "holder_not_waiting"`
   — fail closed. `show_help` documents all three and the `DEFERRED_FILE:` lines.
9. `shellcheck .aitask-scripts/aitask_sync.sh`.

## Verification

As enumerated in the task body: AC2 (i)–(iv); wire rows for `self` / `other` /
`remote` / `unverified`; `--commit-for-task` self / other / unverified / seam;
`--expect-path` identical / grown / comma path; `--require-waiting` fail-closed;
`pre_push` race blocked vs unrelated advance; parser round trips (`|` in path,
email, `a|b` session, literal `%7C` host), fail-closed cases, first-line
`DEFERRED_FILE:`, closed-set scan; existing Tests 1–17 and `_emitted_tokens` still
green. Run `bash tests/test_sync_deferral_and_quarantine.sh`, `bash tests/test_sync.sh`,
`bash tests/test_sync_auto_commit_scoping.sh`, `bash tests/test_sync_protect_paths.sh`,
`bash tests/run_all_python_tests.sh --test-dir tests`.

## Step 9

Standard post-implementation; parent t1725 archives after the last child.
