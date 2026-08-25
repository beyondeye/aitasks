---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, task_metadata, robustness, crash_recovery]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1599_1, t1599_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-25 11:09
updated_at: 2026-08-25 12:48
---

## Origin

Surfaced during t1590. While that task's data-branch changes sat uncommitted, a
concurrent session claimed t1595; its `aitask_pick_own.sh` staged the whole
`aitasks/` tree and committed t1590's `stats_config.json` edit and task file
under the message `ait: Start work on t1595: set status to Implementing`
(`442c65179`). Content was intact, but provenance was lost.

That was not a one-off. It is the designed behaviour of three helpers.

## Defect

Three scripts stage a **whole directory** and then commit the **entire index**
with no path scoping, so any file another session is mid-edit on is swept into
a commit whose message names a different task:

- `.aitask-scripts/aitask_pick_own.sh:363` — `task_git add aitasks/`, then the
  unscoped `task_git commit -m "ait: Start work on t${task_id}…"` at `:369`.
  Runs on **every task claim**, so this is the highest-frequency site.
- `.aitask-scripts/aitask_sync.sh:176-177` — `task_git add aitasks/ aiplans/`
  then `ait: Auto-commit task changes before sync`. A deliberate catch-all, but
  it is invoked from `aitask_pick_own.sh --sync` at Step 0c of every pick.
- `.aitask-scripts/aitask_fold_mark.sh:591,616` — `task_git add aitasks/` then
  an unscoped commit (`:604`) and, worse, an unscoped `commit --amend` (`:620`)
  that can rewrite a commit which has since acquired foreign files.

## Measured blast radius (data branch, this repo)

Scanned the last 400 `ait: Start work on t…` commits, counting those carrying a
task/plan file belonging to a **different** task, or an `aitasks/metadata/*`
config (legitimate `emails.txt` / lock churn excluded):

| metric | value |
|---|---|
| claim commits examined | 400 |
| carrying a foreign task or metadata file | **107 (26%)** |

Sync path, last 300 scanned: 66 auto-commits, **17 carrying >2 task/plan files**.

Concrete cross-task examples:

- `e80ade758` — claimed t1275, committed `t1544_7` **and** `t1560_4`.
- `d3f43a206` — claimed t1587, committed `t1544_5`.
- `3ca4e043a` — claimed t1544_7, committed `t1586`.
- `da9dfeb89` — claimed t594_4, committed `stats_config.json` **and** `t597_4`.

`aitasks/metadata/stats_config.json` has four commits in its entire history;
**three are swallows** (`da9dfeb89`, `c4445b4eb`, `442c65179`). Only
`eb9560fc7` names the change it carries.

## Why it matters

1. **Provenance is wrong.** `git log -- <file>` attributes a change to a task
   that never touched it, and `aitask_issue_update.sh` — which finds commits by
   the `(tNN)` tag — cannot associate the change with its real task.
2. **Half-finished state is committed and pushed.** The swallowed file is
   whatever the other session had on disk at that instant, not a reviewed state.
   If that session later aborts or reverts, the pushed commit still carries the
   partial edit.
3. **It crosses machines.** `commit_and_push` pushes, so another PC's in-flight
   work is propagated without its author's involvement.

## Suggested fix

The remedy differs per site — do not apply one blanket patch:

- **`aitask_pick_own.sh`** — it knows exactly which paths it touched (the task
  file, plus `emails.txt` when an email was stored, plus lock artifacts). Stage
  and commit those paths explicitly: `task_git commit -o -- <paths>`. This is
  the framework's own convention (`feedback_commit_only_paths_not_index`).
- **`aitask_fold_mark.sh`** — the primary and folded task IDs are known at the
  call site; scope both the commit and the `--amend` to their files. The amend
  needs care: re-scoping an amend that already captured foreign files should
  fail loudly rather than silently rewrite them.
- **`aitask_sync.sh`** — this one is *intentionally* a sweep, so scoping alone
  is not the answer. Options to evaluate: skip files whose task is locked by a
  **different live** session (the lock records host + pid + starttime, so
  liveness is already decidable — see `aitask_lock.sh --check`), or refuse the
  auto-commit and report when foreign dirty files are present.

## Verification

- A regression test that seeds a dirty unrelated task file, runs a claim of a
  different task, and asserts the resulting commit's `--name-only` contains
  **only** the claimed task's paths. This must be a real negative control: the
  test has to fail against today's `add aitasks/`.
- Re-run the history scan above after the fix; new claim commits should show a
  0% foreign-file rate.

## Out of scope

Rewriting the existing mis-attributed history. The data branch is shared and
frequently has live sessions on it; the 107 historical commits stay as they are.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-25T09:47:21Z status=pass attempt=1 type=human
