---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness, crash_recovery]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
implemented_with: claudecode/opus5
created_at: 2026-08-25 12:48
updated_at: 2026-08-25 17:05
---

## Context

Parent: t1599 — three framework helpers stage a whole directory and commit the
entire git index, sweeping another live session's in-flight files into a commit
whose message names a different task.

This child owns the **highest-frequency** site. `aitask_pick_own.sh` runs on
**every task claim**. Measured on the live `aitask-data` branch (Jul 1 – Aug 25
2026): **83 of the last 300 `ait: Start work on t…` commits (28%)** carry a
foreign task file. Worst cases are `ait board` boardidx reshuffles landing under
an unrelated claim — `c1427200b` (claiming t1405) carried **178** foreign task
files.

## Exclusive script ownership

This child owns **`.aitask-scripts/aitask_pick_own.sh`** and nothing else.
Do NOT edit `aitask_sync.sh` (t1599_3), `aitask_fold_mark.sh` (t1599_2), or the
sweep targets owned by t1599_4.

## Key files to modify

- `.aitask-scripts/aitask_pick_own.sh` — `commit_and_push()` at `:360-373`, and
  its call site at `:475`.
- `tests/test_pick_own_scoped_commit.sh` — new.

## Step 1 (pre-phase risk mitigation): `partial_commit_worktree_semantics`

Do this FIRST, before any scoping edit.

`git commit -m <msg> -- <paths>` performs a **partial** commit: it takes those
paths' **worktree** content and ignores the index entry for them. That is a real
behaviour change from today's index-wide commit, and the other three children
inherit the pattern — so pin it before propagating it.

Add a characterization test that stages a task file, modifies it again on disk,
then claims, and asserts **which** version landed in the commit. Write down the
answer explicitly in the test's comment header.

## Step 2: Scope the commit

Current code (`:359-374`), verbatim:

```bash
commit_and_push() {
    local task_id="$1"

    task_git add aitasks/

    # Only commit if there are staged changes (idempotent re-run safety)
    if task_git diff --cached --quiet; then
        info "No changes to commit (task may already be in Implementing status)"
    else
        task_git commit -m "ait: Start work on t${task_id}: set status to Implementing" --quiet
    fi

    # Push is best-effort — network failure should not block the workflow
    task_push
}
```

Replace with:

```bash
commit_and_push() {
    local task_id="$1"; shift
    local paths=( "$@" )
    (( ${#paths[@]} )) || { info "No paths to commit"; task_push; return 0; }

    # `add` is needed ONLY so an untracked path can be named by the pathspec;
    # a pathspec cannot match a file git does not know about.
    task_git add -- "${paths[@]}" >/dev/null 2>&1 || true

    if [[ -z "$(task_git status --porcelain -- "${paths[@]}" 2>/dev/null)" ]]; then
        info "No changes to commit (task may already be in Implementing status)"
    else
        task_git commit -m "ait: Start work on t${task_id}: set status to Implementing" \
            --quiet -- "${paths[@]}"
    fi

    task_push
}
```

**The empty-`paths` guard is load-bearing.** `git commit --` with no pathspec
commits the whole index, silently re-creating the exact bug being fixed.

**The no-op guard must be scoped too.** Today's `task_git diff --cached --quiet`
has no pathspec, so unrelated staged content from another session currently
decides whether the claim commits at all. Use the scoped
`status --porcelain -- "${paths[@]}"` form (the same shape as
`aitask_gate.sh:1025-1032`).

## Step 3: The call site

Only two data-branch paths are written by a claim:

- the **task file** — `resolve_task_file "$TASK_ID"`, already resolved in
  `main()` at `:396` (returns a repo-relative `aitasks/...` path);
- **`aitasks/metadata/emails.txt`** — `EMAILS_FILE` at `:68`, written by
  `store_email()` at `:232-237`.

Nothing else. Lock artifacts are blobs on the orphan `aitask-locks` branch and
are never in the data index (`aitask_lock.sh` uses `hash-object`/`mktree`/
`commit-tree`/`push` plumbing). `.aitask-gates/<id>/change_baseline` is
gitignored and written *after* the commit. `active_gates` is committed
separately by `aitask_gate.sh materialize-active`, which is already path-scoped.

`task_file` is a `local` in `main()`, so thread it in. Build the array
conditionally — `:396` ends with `|| true` so `task_file` can be empty, and
`emails.txt` exists only when an email resolved:

```bash
commit_paths=( )
[[ -n "$task_file" ]] && commit_paths+=( "$task_file" )
[[ -f "$EMAILS_FILE" ]] && commit_paths+=( "$EMAILS_FILE" )
commit_and_push "$TASK_ID" ${commit_paths[@]+"${commit_paths[@]}"}
```

## Reference patterns to copy (do not reinvent)

Three sites already do this correctly:

- `.aitask-scripts/aitask_attach.sh:196-205` — `_attach_commit()`, with a
  load-bearing comment explaining exactly this bug.
- `.aitask-scripts/aitask_gate_record.sh:81-82`
- `.aitask-scripts/aitask_gate.sh:1025-1032` — the cleanest scoped no-op guard.

`task_git` (`lib/task_utils.sh:181-189`) is a transparent pass-through that
accepts `--` and pathspecs unchanged. `task_push` needs no change.

Note the argument order: `-m` must come **before** the `--` pathspec, or git
reads the message as a path.

## Verification

New test `tests/test_pick_own_scoped_commit.sh`. **No test anywhere asserts this
commit today** — `grep -rn 'Start work on t' tests/` returns zero hits.

- Fixture: copy `setup_paired_repos` from `tests/test_lock_force.sh:37-91`
  (bare remote + clone, `setup_fake_aitask_repo`, copies `aitask_pick_own.sh`,
  `aitask_lock.sh`, `aitask_update.sh`, `lib/task_utils.sh`, `lib/pid_anchor.sh`,
  and `ait`).
- Seed a bystander `aitasks/t2_bystander.md`, commit it, then leave an
  uncommitted edit on it.
- Claim t1: `./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com"`.
- Assert with the `tests/test_gate_record.sh:83-96` idioms:
  - `git log -1 --pretty=%s` == `ait: Start work on t1: set status to Implementing`
  - `git show --name-status --pretty=format: -M0 HEAD` contains **only** t1's
    paths and **not** `t2_bystander`
  - the bystander is still ` M` unstaged (the
    `tests/test_archive_no_overbroad_add.sh:154-167` assertion shape)
- Add the Step-1 characterization assertions.
- Also cover: claim with no email (no `emails.txt` in the commit), and an
  idempotent re-claim (no new commit — the
  `tests/test_gate_record.sh:100-107` `rev-list --count` idiom).

**Negative control (required).** Run the same fixture against the PRE-fix
`commit_and_push` and confirm it FAILS on the bystander assertion. A test that
passes against today's `add aitasks/` proves nothing.

Test conventions: header/footer per `tests/test_lock_force.sh`; source
`tests/lib/test_scaffold.sh` then `tests/lib/asserts.sh`. Assertion argument
order is `assert_contains <desc> <needle> <haystack>`. The
`(cd "$TMPDIR/local" && …)` command-substitution form keeps asserts at top
level, so the `assert_counters_init` subshell opt-in is NOT needed.

Also run `shellcheck .aitask-scripts/aitask_pick_own.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-25T13:57:28Z status=pass attempt=1 type=human
