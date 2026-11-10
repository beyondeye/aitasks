---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Done
labels: [release_scripts, bash_scripts, issue_integration]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2261
implemented_with: claudecode/opus5_5
created_at: 2026-11-09 23:12
updated_at: 2026-11-10 12:37
completed_at: 2026-11-10 12:37
---

## Context

Child 1 of t2261 (release-time issue notifications). The parent's goal: when a
release tag ships, every issue resolved since the previous release gets a
"Released in vX.Y.Z" comment. This child builds the **writer** half. Every
successful issue update records one entry in a rolling ledger, "issues fixed
since the last release". The writer is `aitask_issue_update.sh`. Its callers are
task-workflow Step 9 (`issue-update.md` + the inline FOLDED_* handling),
`aitask-pickrem` and `aitask-web-merge`, so hooking the script covers primary,
parent, related and folded issues alike. The consumer half, which posts the
release comments, is t2261_2.

**The authoritative design is `aiplans/p2261_release_issue_notifications.md`**
(sections "Ledger contract" and "Child t2261_1"). The child plan
`aiplans/p2261/p2261_1_*.md` carries the step-by-step detail.

## Ledger contract (summary — the parent plan is authoritative)

- One file per record. A single shared file conflicts in `ait sync` when two
  machines append. The layout is
  `aitasks/metadata/release_issues/pending/<task_id>--<key>.rec` (later moved
  by t2261_2 to `released/<tag>/`).
- `<key>` = the first 16 hex characters of `printf '%s' "$url" | git
  hash-object --stdin`. Identity is the exact `task_id` + `issue_url` bytes
  inside the file. A key hit with a different URL fails closed
  (`hash_collision`).
- Format: `key=value` lines: `schema=1`, `task_id`, `issue_url`, `platform`
  (github|gitlab), `action` (closed|commented|closed_silent),
  `recorded_at` (ISO UTC). Every value is validated on write and on read. The
  URL charset is `^https?://[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]+$`.
- Dedupe: a pending or released record with the same pair → no new record.
- Lock: `ait_ledger_lock_acquire release_issues ledger` (`lib/ledger_block.sh`)
  around find + write + commit. Commit through
  `ait_commit_paths_staging_untracked` with explicit paths. A commit failure
  rolls the file back.

## Key files

- New `.aitask-scripts/lib/issue_backends.sh`: the github/gitlab/bitbucket
  backends and the `source_*` dispatchers, moved verbatim from
  `aitask_issue_update.sh`. Dispatchers take an *issue ref*: the URL for
  GitHub (`gh issue comment|close|view` accept a URL, which fixes cross-repo
  and GHE issues being commented on the current repo); the number plus
  `-R slug` for GitLab, unchanged.
- New `.aitask-scripts/lib/release_issue_ledger.sh`: `ril_root`, `ril_key`,
  `ril_validate_*`, `ril_find`, `ril_record`, `ril_read`.
- `.aitask-scripts/aitask_issue_update.sh`: source the libs. After the
  platform call succeeds, record in a **subshell**, so a `die` in a shared
  helper cannot hide the successful update. Outputs:
  `RELEASE_LEDGER:recorded|duplicate:<path>` (exit 0), or
  `RELEASE_LEDGER_FAILED:<reason>` plus a stderr hint with the exact
  `--record-only` command (exit 3). A new `--record-only` mode records with no
  platform or CLI call. `--dry-run` never records.
- `.claude/skills/task-workflow/issue-update.md`: one paragraph. On
  `RELEASE_LEDGER_FAILED:`, the issue was updated: run the printed
  `--record-only` command, never the original. Then run
  `aitask_skill_verify.sh` and regenerate the goldens; suggest Codex and
  OpenCode port tasks.
- New tests: `tests/test_issue_update_argv.sh` (pre-phase characterization)
  and `tests/test_issue_update_ledger.sh`.

## Reference files

- `.aitask-scripts/aitask_note.sh`: lock + path-scoped commit + rollback on
  a commit failure (the read-receipt path).
- `.aitask-scripts/lib/ledger_block.sh` (`ait_ledger_lock_acquire` /
  `_release`) and `lib/stale_lock.sh`. Never acquire the lock inside `$( )`.
- `lib/task_utils.sh`: `ait_commit_paths_staging_untracked`,
  `task_git_commit_scoped`, `ait_data_mode`, `extract_issue_url`,
  `detect_platform_from_url`.
- `tests/lib/asserts.sh`; file-backed counters for subshell test bodies
  (CLAUDE.md, t1207).

## Implementation plan

0. **Pre-phase [characterize_issue_update_argv]:** before touching the
   script, add `tests/test_issue_update_argv.sh`, which pins the exact
   gh/glab argv per action (close-with-notes, comment-only, close-silently,
   `--issue-url … --close <primary>`) on the **unmodified** script, with PATH
   stubs. After the extraction the GitLab expectations are unchanged. The
   GitHub expectations change only from `<number>` to the issue URL; keep the
   pre-change value as a commented control naming its commit.
1. Extract the backends into `lib/issue_backends.sh` and add the issue-ref
   dispatch.
2. Add `lib/release_issue_ledger.sh`.
3. Writer hook: map the flags to an action, record in a subshell, outputs
   and exit 3 as above.
4. Add `--record-only` and update `--help`.
5. `issue-update.md` note, skill verify, goldens.
6. `tests/test_issue_update_ledger.sh`:
   - one record per action;
   - nothing on `--dry-run` or a failed stub;
   - dedupe;
   - parallel distinct writers → N records; parallel identical → 1;
   - `--issue-url` records the primary id;
   - an injected commit failure → `RELEASE_LEDGER_FAILED`, exit 3, rolled
     back, issue updated, and `--record-only` then records with zero stub
     calls;
   - the GitHub URL target;
   - an invalid URL is refused.
7. After the commit: `./ait note 2251 --from 2261_1`. t2251 retires the
   Bitbucket backend, which now lives in `lib/issue_backends.sh`; its
   inventory line for `aitask_issue_update.sh` is stale. Check t2251's state
   before editing the shared file, per the shared-file rule.

## Verification

- `bash tests/test_issue_update_argv.sh` passes before and after the
  extraction.
- `bash tests/test_issue_update_ledger.sh` passes.
- `shellcheck .aitask-scripts/aitask_issue_update.sh .aitask-scripts/lib/issue_backends.sh .aitask-scripts/lib/release_issue_ledger.sh`.
- `./.aitask-scripts/aitask_skill_verify.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-10T08:42:03Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-10T09:44:55Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-10T10:36:59Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:11ddd4402a858086

> **✅ gate:risk_evaluated** run=2026-11-10T10:36:59Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2261_1/risk_evaluated_2026-11-10T10:36:59Z-risk_evaluated-a1.log`
