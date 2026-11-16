---
Task: t1912_4_stats_writer_cutover.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-16 08:47
---

# t1912_4 — Stats writer cutover (plan, verified 2026-11-15)

## Context

Child 4 of t1912. The two counter writers (`aitask_usage_update.sh`,
`aitask_verified_update.sh`) still rewrite `aitasks/metadata/models_<agent>.json`
on `aitask-data`. They pre-converge the shared `.aitask-data` worktree, clone
origin, commit, push and post-converge (`lib/verified_update_lib.sh`). That is
the 88% of rebase cycles the parent task is about. Earlier children built
everything this cutover needs:
- t1912_1: the store and its CLI `aitask_model_stats.py`;
- t1912_2: readers read file + branch through the loader;
- t1912_3: every step that relied on the converge's push side effect now runs
  `task-data-push.md`.

This child switches the writers to the store. It deletes the clone/push path
and both converges, and it stops writing `verified`.

Full spec: `aitasks/t1912/t1912_4_stats_writer_cutover.md`. The t1912_3 inbox
note (acknowledged) confirms that the converge can be removed.

## Verification findings (what the original plan did not know)

- **Sourcers of `verified_update_lib.sh`:** only the two writers, plus tests
  (`test_usage_update.sh`, `test_verified_update.sh`,
  `tests/lib/metadata_update_fixture.sh`). No other script uses
  `previous_calendar_month`, `has_remote_tracking`, `current_task_branch` or
  `model_registration_hint`.
- **`UPDATED_REMOTE_ONLY`** is produced only by these two writers. It is
  consumed only by `satisfaction-feedback.md` (L33, L104 of the source), the
  three procedure goldens, `test_metadata_partial_sync_recovery.sh` and the
  writer tests.
- **The CLI already prints** `UPDATED:<agent>/<model>:<skill>:<value>`, which is
  the same shape the writers print (`AGENT_STRING` is `<agent>/<model>`).
- **Value semantics (user decision, 2026-11-15): effective.** The CLI currently
  returns the value computed from the branch blob alone. Until t1912_5 migrates
  an agent, that blob holds only post-cutover writes, so a model with 100 legacy
  runs at 80 that is rated 5 would print 100. The writers must print what every
  reader now shows. That means a small change in the store and CLI (step 3).
- **`test_model_stats_parity.sh` runs the real jq writers.** It is the proof
  that the Python port matches jq. Deleting the renderers kills it unless its
  results are frozen first (inline pre-phase below).
- **Merge semantics reproduce the old writer semantics on the effective view.**
  Legacy month M + branch bump in M+1 ⇒ `merge_buckets` re-slots to month M+1
  and prev_month M. A gap ⇒ empty prev_month. Same month ⇒ sum. So the
  rollover tests that seed bucket state in the *file* keep their expected
  values; they only read the store's effective `export` instead of the file.
- **`tests/test_create_manual_verification.sh` ~L363** cites
  `test_verified_update.sh` Test 33B as the reachable coverage for the t1728
  staged-target hazard. Test 33 is retired here, so that comment must point
  only at `tests/test_verification_followup.sh` (verify that it covers the
  hazard before editing).
- **`tests/test_codeagent_trail.sh` L181 / `test_codeagent_work_report.sh` L189**
  cite "Test 19/20". Keep those two tests and their numbers in the rewrite.
- **Whitelist decision: no entries for `aitask_model_stats.py`.**
  `test_helper_whitelist_coverage.sh` covers helpers a *skill* invokes. Skills
  still invoke only the two writers, which are already whitelisted, and the
  writers call the CLI internally.
- **Docs** (`aidocs/framework/adding_a_new_codeagent.md` L315-316,
  `model_reference_locations.md`, website) belong to t1912_6. Here only the
  writers' `--help` text and code comments that this change makes false are
  updated. The `sed_macos_issues.md` L562 entry is a dated sweep record and is
  left as it is.
- **Working tree hazard:** other sessions have dirty files, including
  `task-workflow-remote-*` renders and `.aitask-data` task files for
  t2304/2306/2307. Every commit names its paths explicitly. The rerender's
  unrelated output is never staged.

### Pre-phase (risk mitigations)

1. [freeze_parity_golden] Before any writer edit, extend
   `tests/test_model_stats_parity.sh` with an opt-in capture:
   - When `PARITY_CAPTURE=<file>` is set, each `check` also appends one TSV row:
     `label, stats_key, skill, date, score_100, pre_stats_json (jq -S -c),
     writer_value, writer_bucket (jq -S -c)`.
   - Run it once against the live jq writers into
     `tests/golden/model_stats_parity/steps.tsv`.
   - The capture counts its own `check` calls at runtime (a counter in
     `check`, no hard-coded number) and fails if the row count differs.
     Today's file has **22**: usage 8 dates + 2 seeded; verified 8 dates +
     3 flat + 1 rounding.
   - Commit the capture hook, the golden and a header comment naming the
     capture commit, as `test: Freeze the jq writer parity golden (t1912_4)`.
     That commit is the reproducible source: `git show <sha>:tests/test_model_stats_parity.sh`.
   - Step 7 later rewrites the test to golden-only.

## Steps

1. **Acceptance test first (red against the current writers).** NEW
   `tests/test_stats_writers_leave_task_data.sh`, using `tests/lib/sync_fixture.sh`
   `setup_repo` (bare remote + real branch-mode clone with a full framework copy,
   so the CLI and libs are present).
   - **Setup:**
     - Seed `aitasks/metadata/models_claudecode.json` (model `opus4_6`) on the
       data branch, then commit and push.
     - Advance origin's `aitask-data` by one commit from a second clone.
     - Dirty `.aitask-data` with a modified tracked file and an untracked file.
     - Install a `bin/git` wrapper first on `PATH` that appends
       `PWD<TAB>argv` to a log, then execs the real git.
   - **Snapshot before and after:**
     - `git -C .aitask-data rev-parse HEAD`;
     - `git -C .aitask-data ls-files -s | sha256sum`;
     - `git -C .aitask-data status --porcelain --untracked-files=all`;
     - `refs/remotes/origin/aitask-data` in the local clone;
     - origin's `refs/heads/aitask-data`.
   - **Run:** `aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent`,
     then `aitask_verified_update.sh … --score 4 --silent`.
   - **Assert:**
     - All five snapshot values are byte-identical.
     - No logged argv contains `merge`, `rebase` or `pull`.
     - No logged `fetch` / `push` / `ls-remote` line mentions `aitask-data`.
     - No logged line has a PWD inside `.aitask-data`, and none has
       `-C …/.aitask-data`.
     - Both outputs are `UPDATED:` lines.
     - `aitask_model_stats.py show --root <clone>` reflects runs=1 for both
       stats keys.
     - Origin now has `refs/heads/aitask-stats`.
   - **Red run:** run it before step 2 and record the result in this plan's
     implementation notes. Expected red: the pre-converge fetches or rebases,
     and HEAD or the porcelain changes. Bash bodies in subshells use
     `assert_counters_init` / `assert_counters_load` (t1207).

2. **`lib/verified_update_lib.sh` — shrink to the shared CLI bridge.** Delete
   these and keep only `model_registration_hint`:
   - `MAX_REMOTE_RETRIES`, `REGISTRY_CAS_ATTEMPTS`;
   - the out-params;
   - `run_git_quiet`, `log_info`, `previous_calendar_month`;
   - `has_remote_tracking`, `current_task_branch`, `current_task_remote`;
   - `configure_clone_identity`, `run_before_push_hook`,
     `is_retryable_push_error`;
   - `converge_current_repo_with_remote`;
   - `commit_metadata_update_local`, `commit_and_push_from_remote_clone`,
     `commit_metadata_update`.

   Then add:
   ```bash
   # model_stats_write <verb> <cli args...> — run aitask_model_stats.py against the
   # repo root (cwd; the caller anchored it). Sets MODEL_STATS_LINE to the CLI's
   # last stdout line, or to a synthesized STATS_ERROR:<reason>; returns 0 only for
   # an UPDATED: line with exit 0. Never touches the task-data worktree.
   # STATS_DIVERGED:<l>|<r> is mapped to STATS_ERROR:diverged:<l>|<r>.
   # The CLI's stderr is forwarded even under --silent: it is quiet on success
   # and carries only real problems (an unavailable total, a local ref that could
   # not be advanced after a durable push), as the old writers' unconditional
   # `warn` on a stranded commit did.
   ```
   The missing CLI case gives `STATS_ERROR:cli_missing` and no Python gives
   `STATS_ERROR:no_python`, both via `resolve_python` from `python_resolve.sh`,
   which `task_utils.sh` sources. Rewrite the header comment: the old contract
   (traps, `_AIT_*` globals) is gone. The filename stays, so sourcers and docs
   keep working.

3. **Store + CLI — report the effective total from the write's own snapshot.**

   **Why not the loader.** `load_agent_stats` is a display reader and fails soft:
   - `_branch_content` catches `GitError` / `OSError`, and `ors.resolve` turns a
     failed rev-parse into `None`. Both silently read as "no branch", which
     gives legacy-only totals. A reproduction found runs=1/score_sum=20 where
     the true total was 2/120.
   - `update` also only *warns* when `advance_ref` cannot move the local ref
     after a successful push, so a re-read can miss our own write.

   A post-write total therefore never comes from the loader, and it never falls
   back to the branch-only value. Either would contradict the agreed effective
   semantics.

   - **`lib/model_stats_store.py` — the post-push boundary.**
     - After `cas_push` returns `OK`, the write is durable on origin.
       `ors.advance_ref` can still *raise*: `is_ancestor` and `cas_local`
       raise `GitError`, and `subprocess` raises `OSError`. Today that
       exception escapes `update`, and the CLI's top-level handler prints
       `STATS_ERROR` / exit 1 for a rating that is recorded.
     - Wrap everything after the `OK` in `try`, so that `advance_ref` and the
       `DIVERGED` warning can never turn the result into a failure. Record the
       outcome as `local_ref`: `ADVANCED` | `ALREADY_NEWER` | `DIVERGED` |
       `ERROR:<reason>`.
     - The no-remote path keeps raising on a failed `cas_local`. That is
       correct: the local ref *is* the store there, so the write did not land.
     - `update(..., *, return_commit=False)`: keyword-only and
       default-preserving. When it is true, return an `UpdateResult(value,
       commit, local_ref)` named tuple; `local_ref` is always `ADVANCED` on the
       no-remote path. The default return is still just `value`, so existing
       callers are unchanged.
     - New `class TotalUnavailable(StatsError)`.
     - New `effective_total(project_root, agent, model, key, skill, today,
       committed_models, commit)`, with every input strict. It computes:
       - `marked = ors.read_file(top, commit, marker_path(agent)) is not None`.
         This is the marker state *in the commit we wrote*. A `GitError`
         raises `TotalUnavailable("marker_unreadable")`.
       - `legacy = {} if marked else legacy_models(..., strict=True)`. Add a
         `strict` keyword to `legacy_models`: a missing file is still `{}`, but
         an unreadable file or invalid JSON raises
         `TotalUnavailable("legacy_unreadable")`. The non-strict default that
         readers use is unchanged.
       - `merged = merge_stats(legacy, committed_models)`. `committed_models`
         is exactly the blob of that commit, captured by the CLI's `fn`
         closure: the last `fn` call is the committed attempt, because
         `update` returns right after that attempt's push.
       - `entry = _normalize(merged[model][key][skill])`. A missing entry
         raises `TotalUnavailable("entry_missing")`.
       - `usagestats`: `runs` of the bucket among `month` / `prev_month` whose
         `period` equals `current_periods(today)`'s month. If no bucket
         matches, raise `TotalUnavailable("period_not_in_view")`. That can
         only happen with a `--date` older than the legacy prev month. It
         never answers 0.
       - `verifiedstats`: `_jq_round(score_sum / runs)` of `all_time`. A
         runs value of 0 raises `TotalUnavailable`.
   - **`aitask_model_stats.py` `cmd_bump_usage` / `cmd_record_verified`:**
     - `fn` records `holder["models"] = new_blob["models"]` (deep copy) on each
       call. Then `res = mss.update(..., return_commit=True)`.
     - When `res.local_ref` is `DIVERGED` or `ERROR:*`, report the local
       problem **separately**, on stderr: `model-stats: recorded on origin, but
       the local aitask-stats ref was not advanced (<local_ref>); run
       'aitask_model_stats.py refresh' or './ait sync'`. The result is still a
       recorded success. The total does not depend on the local ref (it reads
       `res.commit`, which exists locally because it was built here).
     - **After `update` returns, the write is durable.** From that point no
       failure may become a failure exit, and nothing may read as "not
       recorded".
     - `effective_total(...)` runs inside `try`:
       - success ⇒ `UPDATED:<a>/<m>:<s>:<total>`, exit 0;
       - `TotalUnavailable`, or *any* exception ⇒
         `UPDATED:<a>/<m>:<s>:unknown`, exit 0. stderr gets
         `model-stats: recorded, but the effective total is unavailable (<reason>)`.
     - The branch-only value is never printed.
     - Docstring: document `:unknown`. `UPDATED:` always means *recorded*,
       and the value field is an integer or the literal `unknown`.
   - **`tests/test_model_stats_store.py`:** new `TestEffectiveTotal`. The CLI
     runs in-process via `aitask_model_stats.main([...])` so seams can be
     monkeypatched.
     - Legacy `verifiedstats.pick` all_time 1/20 plus `record-verified
       --score 5` ⇒ `:60`. This is the reproduction's case: 2 runs / 120.
     - Legacy usage month (same period) runs 3 plus `bump-usage` ⇒ `:4`.
     - Marker present in the tree ⇒ the branch-only total, with legacy ignored.
     - **Suppressed-read independence:** patch `mss._branch_content` to
       return `_EMPTY_BRANCH` and `ors.resolve` (for `L_REF`, after the push)
       to return `None`, which is the fail-soft loader state. The printed
       total is still `:60`. This proves the loader is not consulted.
     - **Unavailable paths (each with exit 0 and `:unknown`):**
       - `ors.read_file` raises `GitError` for the marker path;
       - the legacy file holds invalid JSON;
       - `merge_stats` raises.

       In every case: the stderr line is present; the stats commit is on the
       local ref (or origin) with runs incremented, so the write was not
       lost; and the output is never the branch-only value (`:100`).
     - A `--date` older than the legacy prev month ⇒ `:unknown`, never `:0`.
     - **Post-push failure (deterministic, in-process):**
       - Set up a clone with a bare origin. Patch `ors.advance_ref` to raise
         `GitError` (then, in a second case, `OSError`), and run
         `record-verified --score 4`.
       - Expect exit 0, stdout `UPDATED:…:80`, and the stderr local-ref line.
       - Origin's `aitask-stats` holds **exactly one** increment
         (`git --git-dir origin cat-file` of the agent blob: runs = 1, one
         commit past the root). The local ref is unmoved.
       - Then an unpatched second run ⇒ origin runs = 2. There is no double
         count, because the base is re-read from origin.
       - Pre-fix control: the same injection against the unwrapped `update`
         gives `STATS_ERROR` / exit 1 (recorded in the implementation notes).
     - The existing `test_record_and_bump_lines` (no legacy file) still prints
       `:1` / `:80`.

4. **Rewrite both writers' bodies.** Each writer keeps:
   - `parse_args` / `parse_agent_string`, the `SUPPORTED_AGENTS` list and every
     `die` message;
   - the `--agent`/`--cli-id` resolution and the mutual-exclusion rules;
   - the `--score` reject in the usage writer and the `^[1-5]$` check in the
     verified writer;
   - `require_jq`, `ensure_model_exists` (read-only `jq -e` on the registry) and
     the registration hint;
   - `ait_cd_repo_root` (the registry path is still cwd-relative);
   - the `--date` format regex (the CLI rejects impossible calendar dates as
     `STATS_ERROR:usage:…`).

   Each writer removes:
   - the `registry_cas.sh` source;
   - `resolve_date_periods` and the `CURRENT_*` / `PREV_MONTH` globals;
   - `render_*`, `update_model_file`, `map_score`;
   - the EXIT trap / `ait_archive_rearm_exit_trap`;
   - the remote/local branching and both `UPDATED_REMOTE_ONLY` blocks.

   The new main tail:
   ```bash
   local args=(--agent "$PARSED_AGENT" --model "$PARSED_MODEL" --skill "$SKILL_NAME")
   [[ -n "$DATE_OVERRIDE" ]] && args+=(--date "$DATE_OVERRIDE")
   if ! model_stats_write bump-usage "${args[@]}"; then      # record-verified … --score "$SCORE"
       [[ "$SILENT" == "true" ]] || warn "Usage count for ${AGENT_STRING} ${SKILL_NAME} was not recorded (${MODEL_STATS_LINE#STATS_ERROR:})."
       echo "$MODEL_STATS_LINE"; return 1
   fi
   new_runs="${MODEL_STATS_LINE##*:}"   # an integer, or the literal `unknown`
   if [[ "$SILENT" != "true" ]]; then
       if [[ "$new_runs" == unknown ]]; then
           success "Recorded ${AGENT_STRING} ${SKILL_NAME} usage (current total unavailable)"
       else
           success "Updated ${AGENT_STRING} ${SKILL_NAME} usage count to ${new_runs}"
       fi
   fi
   echo "UPDATED:${AGENT_STRING}:${SKILL_NAME}:${new_runs}"
   ```
   `model_stats_write` treats only `UPDATED:` with exit 0 as success. It also
   checks that the CLI's `<agent>/<model>:<skill>` echo matches the arguments.
   A mismatch gives `STATS_ERROR:unexpected_output`. Writer `--help` documents
   that `UPDATED:` always means recorded, and that the value is an integer or
   `unknown`.
   Also update `--help`:
   - drop the "Concurrency note" and the `UPDATED_REMOTE_ONLY` rows;
   - document `STATS_ERROR:<reason>` with a non-zero exit;
   - say counters live on the `aitask-stats` branch, and that the verified
     writer records `verifiedstats` and never writes `verified`.

   Make the cwd-anchor comment (L14-19) name only the registry path. `verified`
   is no longer written: nothing touches the file.

5. **Comments made false by this change** (current-state wording):
   - `lib/registry_cas.sh` L7: drop the counter writers and keep
     `aitask_opencode_models.sh` and the t1912_5 strip.
   - `lib/model_stats_windows.py` L11.
   - `lib/model_stats_store.py` L34/L198/L240: "port of the former jq
     renderers".
   - `tests/lib/test_scaffold.sh` L36: drop the counter writers from the list
     of `registry_cas.sh` sourcers.
   - `tests/test_opencode_models_merge.sh` L7: legacy counters still present
     until t1912_5.
   - `tests/test_create_manual_verification.sh` L363.

6. **`satisfaction-feedback.md`** (source `.claude/skills/task-workflow/`):
   - Step 0: replace the `UPDATED_REMOTE_ONLY` bullet with "On
     `STATS_ERROR:<reason>` (non-zero exit): warn `usage not recorded:
     <reason>` and continue". Keep the generic failure bullet.
   - Step 1.4: replace the `UPDATED_REMOTE_ONLY` bullet with two bullets:
     - "`UPDATED:<agent>/<model>:<skill>:unknown` (exit 0): the rating **is**
       recorded, but its current average could not be read. Display
       `Recorded <skill> rating for <agent>/<model> (current average
       unavailable)`. Do not retry and do not call it unrecorded."
     - "`STATS_ERROR:<reason>` (non-zero exit) or any other failure: display
       `Verified score not recorded (<reason>)` and **continue** — a failed
       stats write never fails the workflow."
   - Step 0 also says: `UPDATED:…:unknown` is a success.
   - Then run `./.aitask-scripts/aitask_skill_rerender.sh` and regenerate
     `tests/golden/procs/task-workflow/satisfaction-feedback-{default,fast,remote}.md`
     with the render loop of `test_skill_render_task_workflow.sh`.
   - Review each diff (only these lines may change).
   - Run `./.aitask-scripts/aitask_skill_verify.sh`.
   - `.agents/` / `.opencode/` are renders or wrappers of the same source
     (t1912_3 finding), so **no port tasks** are needed.
   - `tests/test_skill_render_task_workflow.sh` Test 3b/3c: assert that
     `STATS_ERROR` is present and `UPDATED_REMOTE_ONLY` is absent in the
     default, `true` and fast/remote renders.

7. **Tests: fixture + rewrites** (disposition ledger below):
   - `tests/lib/metadata_update_fixture.sh`:
     - `_mdfix_populate` also copies `aitask_model_stats.py` plus
       `copy_lib_py_closure <repo> model_stats_store`, and drops the
       `verified_update_lib`-specific comment.
     - Keep `setup_local_metadata_repo`.
     - Add `setup_remote_stats_repo <script>` (bare origin plus a clone, so
       the store takes its leased-push path).
     - Add `mdfix_export <repo> [agent]` (the CLI `export`).
     - Delete the clone-path hooks and checks (`mdfix_write_refresh_hook`,
       `mdfix_write_rename_hook`, `mdfix_install_*_pre_receive`,
       `mdfix_write_attempt_counter_hook`, `mdfix_server_race_reason`,
       `_mdfix_attempts`, `mdfix_check_*`) and the old
       `setup_remote_metadata_repo` / `setup_branch_mode_metadata_repo`.
       Their only consumers are the retired tests (grep-verified).
     - Rewrite the header.
   - `tests/test_usage_update.sh` / `tests/test_verified_update.sh`: rewritten
     per the ledger. Every kept assertion reads `mdfix_export`. Every
     successful run also asserts that `models_claudecode.json` is byte-identical
     (sha256 before and after), which proves the writers no longer touch it.
   - `tests/test_verified_update_flags.sh`: fixture swap only; its assertions
     are output-only.
   - `tests/test_model_stats_parity.sh`: golden-only. For each `steps.tsv` row,
     feed `pre_stats_json` to the port and compare value and bucket.
     - Completeness comes from an **explicit case manifest** in the test: the
       22 labels, written out. The golden's label column must equal the
       manifest exactly (same set, no duplicates).
     - A truncated or padded golden therefore fails, and so does a dropped
       case, with no row dropped to fit a number.
     - Assert the manifest has 22 entries as a cross-check against the
       capture.
   - `tests/test_metadata_partial_sync_recovery.sh`: **delete**. Reason: it
     pins that the stats writers' `UPDATED_REMOTE_ONLY` "recover with
     `./ait sync`" hint works, and the hint and outcome no longer exist (no
     other writer produces them, grep-verified). The recovery mechanics remain
     covered by `test_sync_guarded_merge.sh` AC1/AC4 and
     `test_task_push.sh` 37/38, as its own header states.
   - `tests/test_metadata_writer_inventory.py` L144-145: remove both pins.
     Confirm the scan no longer flags either writer (the honest-discovery
     check).
   - `tests/test_task_data_writer_guard.sh` ~L270: the loop keeps asserting
     0 guard hits. The label for the two writers becomes "writes no task data
     (aitask-stats store, t1912_4)".

   **Disposition ledger** (retire = path deleted; concurrency of the new path
   is pinned by `test_model_stats_store.py` forced-conflict and two-clone
   tests):

   | file | tests | disposition |
   |---|---|---|
   | usage | 1-6 | keep; read the store (Test 6: file byte-identical) |
   | usage | 7-11, 16, t1884 | keep |
   | usage | 12 | retarget: a remote store write lands on origin `aitask-stats` and on local `refs/heads/aitask-stats` |
   | usage | 13 | moved to the acceptance test |
   | usage | 14, 15 | replaced: unreachable origin ⇒ `STATS_ERROR:unreachable:…`, exit 1, file untouched; positive control on a reachable origin ⇒ `UPDATED:` / 0 |
   | usage | 17 | keep (non-root cwd, branch-mode via `sync_fixture`) |
   | usage | t1928a-c, t2134 | retire: no registry rewrite, no push classifier |
   | verified | 1-8, 10-18 | keep; read the store's effective view (same expected values, by merge re-slotting) |
   | verified | 19, 20 | keep (t1232): store runs = 1, printed 80, file has no `work-report` / `trail` / `explain` key added |
   | verified | 9, 9t, t2134a-d | retire: no data-branch push or retry |
   | verified | 21 | retarget like usage 12 |
   | verified | 22 | moved to the acceptance test |
   | verified | 23 | retire: converge removed by design (t1912_3 re-homed publication) |
   | verified | 24, 25 | replaced like usage 14/15 |
   | verified | 26, 29, 30, 31, 33A-E | retire: out-params, commit seam and converge are deleted (the seam's own coverage stays in `test_verification_followup.sh`) |
   | verified | 27, 28, 32, t1884 | keep |
   | verified | t1928a-c | retire |
   | verified | new | effective value with legacy counters: file all_time 4/320 plus score 5 ⇒ `:84`; `verified` not written |
   | both | new (bridge) | the scaffold's `aitask_model_stats.py` is replaced by a stub. `UPDATED:…:unknown` / 0 ⇒ writer prints `UPDATED:…:unknown`, exit 0. `STATS_ERROR:x` / 1 ⇒ `STATS_ERROR:x`, exit 1. `STATS_DIVERGED:a\|b` / 1 ⇒ `STATS_ERROR:diverged:a\|b`, exit 1. A mismatched echo ⇒ `STATS_ERROR:unexpected_output`. The CLI missing ⇒ `STATS_ERROR:cli_missing`. A stub that writes a stderr warning and then `UPDATED:` / 0, run under `--silent` ⇒ the writer forwards the warning to stderr and exits 0. |

8. **Sanity sweep, then commit.**
   - `grep -rn "UPDATED_REMOTE_ONLY\|commit_metadata_update\|converge_current_repo_with_remote"`
     over `.aitask-scripts tests .claude/skills/task-workflow` ⇒ nothing. The
     archived plans and the `.pre-rewrite` fixture are excluded.
   - Commit the code, tests and goldens on `main`, naming every path
     explicitly: `refactor: Cut the stats writers over to the aitask-stats store (t1912_4)`.

9. **Notes to siblings** (`./ait note`, after the commit):
   - t1678: the stats writers no longer touch the shared index, so do not lock
     them.
   - t1725: the stats-driven rebase windows are gone.

   The parent plan asks for both. Check first that neither has been sent
   already.

## Verification

- `bash tests/test_stats_writers_leave_task_data.sh` is green, and it was red
  against the pre-cutover writers.
- Pass:
  - `test_usage_update.sh`, `test_verified_update.sh`,
    `test_verified_update_flags.sh`, `test_model_stats_parity.sh`;
  - `test_model_stats_refresh_routes.sh`;
  - `test_task_data_writer_guard.sh`, `test_skill_render_task_workflow.sh`,
    `test_helper_whitelist_coverage.sh`;
  - `test_codeagent_trail.sh`, `test_codeagent_work_report.sh`,
    `test_opencode_models_merge.sh`, `test_create_manual_verification.sh`;
  - `test_codeagent.sh`.
- `python3 -m pytest tests/test_model_stats_store.py tests/test_metadata_writer_inventory.py tests/test_stats_readers_golden.py`.
- `./.aitask-scripts/aitask_skill_verify.sh` is clean.
- `shellcheck .aitask-scripts/aitask_usage_update.sh .aitask-scripts/aitask_verified_update.sh .aitask-scripts/lib/verified_update_lib.sh`.
- `bash tests/run_all_python_tests.sh` with the last line `PYTHON SUITE: PASSED`.
  Check it with `${PIPESTATUS[0]}`. Use `TMPDIR` on `/home` if the `/tmp` quota
  bites (the known `shadow_q_harness` caveat).
- **Manual smoke (outward-facing; confirm first):** this session's real Step 0
  usage bump for `pick` *is* the smoke test. Run it once after the commit,
  then set `usage_collected = true` so Step 9b does not bump twice. Check that
  `git -C .aitask-data rev-parse HEAD` and `status --porcelain` are unchanged.
  Check that `aitask_model_stats.py show` lists the bump. The first such write
  creates `aitask-stats` on origin.

## Step 9

Post-Implementation per task-workflow (current branch, no worktree).

## Risk

### Code-health risk: medium
- Deleting the jq renderers removes the only live proof that the Python port matches them · severity: low (residual — addressed by inline pre-phase freeze_parity_golden) · → mitigation: inline pre-phase freeze_parity_golden
- Rewriting ~1700 lines of writer tests could silently drop coverage of a behaviour that is still valid (CLI validation, resolver fallbacks, non-root cwd, t1232 ownership) · severity: medium · → mitigation: none (the disposition ledger in step 7 names every test id with keep / retarget / retire and a reason)
- Shared, dirty working tree (other sessions' renders and task files) could ride along in the commit · severity: low · → mitigation: none (path-scoped commits; the rerender's unrelated output is never staged)
- The post-write total could silently misreport (fail-soft loader), or a recorded write could become a failure exit (the post-write total, or a raising `advance_ref` after a confirmed push) · severity: low (designed out in step 3) · → mitigation: none (total from the committed snapshot with strict reads; post-`OK` local-ref maintenance wrapped and reported separately; `:unknown` with exit 0; covered by the `TestEffectiveTotal` failure-path and post-push-injection tests)

### Goal-achievement risk: medium
- Removing the converge stops publishing task-data commits from any session-ending step that t1912_3's grep inventory missed · severity: medium · → mitigation: t2288 (existing pinned-inventory guard task)
- The acceptance test could pass vacuously (for example, a no-remote path that never meets origin) · severity: low · → mitigation: none (the fixture has a real origin with the data branch ahead, plus a recorded red run against the old writers)
- Writers now need a Python. Where none resolves, every stats write becomes `STATS_ERROR:no_python` · severity: low · → mitigation: none (Satisfaction Feedback warns and continues; the framework already requires Python for readers)

### Planned mitigations
- timing: pre-phase | name: freeze_parity_golden | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: deleting the jq renderers removes the port-parity proof | desc: capture the live jq writers' per-step value+bucket into tests/golden/model_stats_parity/steps.tsv before any writer edit; rewrite the parity test to golden-only after

## Implementation notes (progress, deviations, evidence)

- **Pre-phase freeze_parity_golden — done** (commit `5e33fad89`). The capture
  ran against the live jq writers at `25cc60714` and produced 22 rows; the
  runtime counter matched. `tests/test_model_stats_parity.sh` is now
  golden-only and compares against a 22-label manifest. Negative controls:
  corrupting one bucket in a copy of the golden fails exactly that assertion
  (1 failure), and dropping one row fails the manifest and row-count
  assertions. The golden-only rewrite also found a bash pitfall: `read` with
  `IFS=$'\t'` collapses the empty `score_100` column of usage rows (tab is IFS
  whitespace), so the fields are split in Python and joined with `\x1f`.
- **Step 1, red run** against the pre-cutover writers (8 of 21 failed):
  - HEAD, the index hash, the clone's `origin/aitask-data` tracking ref and
    origin's `aitask-data` tip all moved;
  - the git log showed `-C .aitask-data fetch`,
    `-C .aitask-data merge --ff-only … origin/aitask-data` (pre- and
    post-converge, for both writers) and
    `push origin HEAD:refs/heads/aitask-data` from the temp clone;
  - the registry gained `usagestats` and `verifiedstats`;
  - no `aitask-stats` push happened.

  `status --porcelain` stayed equal, because the ff-only merge carried the
  dirty files across. After the cutover: 22/22 green, including a third run
  launched from `aitasks/metadata` (a symlink into `.aitask-data`).
- **Step 3, pre-fix controls.** The new `TestEffectiveTotal` (12 tests) was
  run against HEAD `5e33fad89`'s store and CLI in a scratch worktree: 10
  failed. The post-push `GitError` injection gave exit 1 (`STATS_ERROR`), as
  the reviewer described. Two tests passed pre-fix, and are meant to: the
  marker case (branch-only, the same as before) and the no-remote CAS failure
  (it must remain an error).
- **Deviation:** the non-root cwd tests (usage 17, verified 32) use the new
  `setup_remote_stats_repo` (subdir and unrelated cwd) instead of
  `sync_fixture`. The branch-mode, inside-the-data-worktree case lives in the
  acceptance test, which already uses the real branch-mode layout.
- **Deviation:** the fixture tests pin cleanliness with
  `status --porcelain --untracked-files=no` plus an unchanged HEAD. The CLI's
  `lib/__pycache__` is untracked noise in fixtures that have no `.gitignore`.
- **Not covered:** `STATS_ERROR:no_python` (forcing `resolve_python` to fail
  would mean faking `$HOME`, `AIT_PYTHON` and `PATH` together). The branch is
  three lines next to `cli_missing`, which is tested.
- `test_metadata_writer_inventory.py` currently fails one tripwire on
  `.aitask-scripts/lib/sitrep_crash.py`. That file holds another session's
  uncommitted work and was dirty before this task started. Neither stats
  writer is flagged after their pins were removed.

## Post-Review Changes

### Change Request 1 (2026-11-16)
- **Requested by user (two blocking findings, both confirmed):**
  1. `effective_total` read the legacy registry under the caller's raw
     `project_root`, while `update` writes into the resolved toplevel. A CLI
     run from a nested cwd without `--root` therefore printed the branch-only
     value: `:100` instead of `:60`.
  2. The CLI's `SKILL_RE` (`[A-Za-z0-9][A-Za-z0-9_.-]*`) narrowed the writers'
     public interface. `--skill custom/skill` used to record and now returned
     `STATS_ERROR:usage:…` with exit 2.
- **Changes made:**
  1. `effective_total` reads the legacy registry under `top` (the resolved
     toplevel); an explicit `metadata_path` is still used verbatim.
  2. `SKILL_RE` is now `[^\x00-\x1f\x7f]+`. That accepts any non-empty skill,
     with one stated exception: control characters, which would split the
     single-line `UPDATED:` result every caller parses (the old writers
     emitted a broken line in that case). The t1912_1
     `TestCliValidation` case that pinned `a:b` as invalid now pins `a\nb`,
     `a\tb` and the empty skill.
- **Tests:**
  - `test_nested_cwd_without_root_reads_the_repository_registry` and
    `test_every_skill_the_writers_accepted_is_accepted` in
    `test_model_stats_store.py`;
  - writer-level compatibility loops: `test_usage_update.sh` 11c (6 skills)
    and `test_verified_update.sh` 8b (4 skills).

  Pre-fix control, in a scratch worktree with only the two fixes reverted:
  both new store tests fail, with exactly the reported symptoms (`:100` vs
  `:60`, and `STATS_ERROR:usage:invalid --skill: 'custom/skill'`).
- **Files affected:** `.aitask-scripts/lib/model_stats_store.py`,
  `.aitask-scripts/aitask_model_stats.py`, `tests/test_model_stats_store.py`,
  `tests/test_usage_update.sh`, `tests/test_verified_update.sh`.

### Change Request 2 (2026-11-16)
- **Requested by user (blocking, confirmed):** `model_stats_write` forwarded
  `--skill` and its value as separate argv entries, so argparse read a skill
  that starts with `-` as an option. With `--skill -custom` the old writer gave
  `UPDATED:…:-custom:1`; the new one gave `STATS_ERROR:usage:argument --skill:
  expected one argument`.
- **Changes made:** the bridge now forwards every `--opt value` pair as one
  `--opt=value` token, and `--root=$PWD` the same way. argparse always binds a
  `=`-attached value, even one like `-h` or `--skill=x`. The target echo check
  uses the values recorded while forwarding. A trailing option with no value
  returns `STATS_ERROR:usage:`.
- **Tests:**
  - `test_usage_update.sh` 11c adds `-custom`, `--looks-like-a-flag`, `-h`,
    `a=b` and `--skill=x`;
  - `test_verified_update.sh` 8b adds `-custom` and `--score`;
  - the verified bridge stub reads `--score=`.

  Pre-fix control, with the bridge reverted to separate-argument forwarding
  in a scratch worktree: all four option-looking skills fail with the
  reported `STATS_ERROR`.
- **Files affected:** `.aitask-scripts/lib/verified_update_lib.sh`,
  `tests/test_usage_update.sh`, `tests/test_verified_update.sh`.

## Final Implementation Notes
- **Actual work done:** the cutover landed as planned.
  - **Writers.** `aitask_usage_update.sh` and `aitask_verified_update.sh` keep
    their CLI, validation, read-only registry check and registration hint.
    They write through `aitask_model_stats.py bump-usage` / `record-verified`
    via `model_stats_write`, the shared bridge that is now the only content of
    `lib/verified_update_lib.sh` apart from `model_registration_hint`.
    - Deleted: the clone/push path, both converges, the `registry_cas.sh`
      counter rewrite, the jq renderers, the EXIT/unstage traps and
      `UPDATED_REMOTE_ONLY`.
    - `verified` is never written.
  - **Output contract.** `UPDATED:<agent>/<model>:<skill>:<value>` always means
    recorded. `<value>` is the **effective** total, the one readers show (user
    decision), or `unknown`. A failed write prints `STATS_ERROR:<reason>` with
    a non-zero exit.
  - **Store / CLI.**
    - `update(..., return_commit=True)` returns
      `UpdateResult(value, commit, local_ref)`. Nothing after a push `OK` can
      raise.
    - New `effective_total` is computed from the committed blob, the marker
      in that commit and a strict legacy read under the resolved toplevel.
    - `TotalUnavailable` is new, and `legacy_models(strict=True)`.
    - `SKILL_RE` was widened to any non-empty skill without control
      characters.
  - **satisfaction-feedback.md:** handles `STATS_ERROR` (warn and continue)
    and `:unknown` (recorded, no retry), and drops `UPDATED_REMOTE_ONLY`.
    Rerendered; 3 goldens and 3 tracked remote renders updated.
  - **Tests:**
    - new `test_stats_writers_leave_task_data.sh` (the acceptance test);
    - 14 new store tests (`TestEffectiveTotal`);
    - the frozen jq parity golden plus the golden-only parity test;
    - rewritten usage, verified and flags tests and the fixture;
    - `test_metadata_partial_sync_recovery.sh` retired;
    - pins and comments updated in five other files.
- **Deviations from plan:**
  - Both review rounds (Post-Review Changes 1 and 2).
  - Non-root cwd tests use `setup_remote_stats_repo`. The inside-the-data-
    worktree case is in the acceptance test.
  - The fixture cleanliness checks ignore untracked `__pycache__`.
  - `STATS_ERROR:no_python` is not tested.
  - The bridge forwards `--opt=value` tokens.
- **Issues encountered:**
  - The bash `IFS=$'\t'` collapse of empty TSV fields (fixed by splitting in
    Python).
  - A `git rm` staged a deletion into the shared index; it was unstaged at
    once, and the deletion is committed by path.
  - The full Python suite verdict is **FAILED** with 2 failures, neither from
    this change:
    - `test_metadata_writer_inventory::test_no_unclassified_file_writes_metadata`
      fails identically at HEAD `5e33fad89` without this change;
    - `test_minimonitor_concern_action::…test_enter_failure_names_the_leftover_text_and_disarms`
      sits under another session's uncommitted monitor edits; it passes in
      isolation, and its id no longer exists in the current file.
- **Key decisions:**
  - The effective total never comes from the fail-soft loader, and never
    falls back to the branch-only value.
  - Once a write is durable, any reporting problem is `:unknown` or a stderr
    note, never a failure exit.
  - The CLI's stderr is forwarded even under `--silent`.
  - No whitelist entries for `aitask_model_stats.py`: skills invoke only the
    two writers.
  - No port tasks: `.agents/` / `.opencode/` are renders of the same source.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/sitrep_crash.py:1 — t2307's commit 87ecc9799 left a metadata-targeting write unclassified in tests/test_metadata_writer_inventory.py (NewWriterTripwire fails at HEAD)`
  - `.aitask-scripts/aitask_model_stats.py:211 — export/show default --root to the raw cwd and read the legacy registry under it (load_agent_stats does not resolve the toplevel), so run from a nested directory they show branch-only counters; the writers and readers pass the repo root, so only direct CLI use is affected`
- **Notes for sibling tasks:**
  - **t1912_5 (migration):**
    - Writers now only ever add branch counters; the registry's stats keys
      are frozen legacy, waiting for the strip.
    - `effective_total` reads the marker from the commit just written, so
      once a marker lands the printed total becomes branch-only with no
      writer change.
    - `registry_cas.sh` stays for `aitask_opencode_models.sh` and the strip.
    - The parity golden (`tests/golden/model_stats_parity/steps.tsv`) pins
      the bucket ports that `merge_buckets` builds on.
  - **t1912_6 (docs):**
    - The writers' `--help` text now states the storage and result contract.
    - `aidocs/framework/adding_a_new_codeagent.md` L315-316 and
      `model_reference_locations.md` rows for the two writers, plus their
      retired tests, are for you to update.
  - **t1912_7 (retrospective):** after this commit no stats write touches the
    `.aitask-data` reflog.
  - **t2288:** the converge is gone; the re-homed `task-data-push.md` sites
    are now the only publication of those commits.
