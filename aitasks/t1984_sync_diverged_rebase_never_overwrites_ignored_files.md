---
priority: medium
effort: high
depends: [1678]
issue_type: bug
status: Ready
labels: [git, syncer, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-10-14 16:45
updated_at: 2026-10-14 16:45
---

## Origin

Spawned from t1792. Four plan-review rounds on t1792 showed that the guarantee
below cannot be made race-free without writer exclusion. By the user's scope
decision, t1792 shipped only the behind-only half: a pinned fast-forward with
`--no-autostash --no-overwrite-ignore` and no rebase fallback. This task takes
the diverged half.

## Problem

When `ait sync` must replay local commits (a diverged branch), `do_pull_rebase`
in `.aitask-scripts/aitask_sync.sh` runs
`pull --rebase --no-autostash`. `git rebase` has no `--no-overwrite-ignore`.
Its checkout and every replayed pick overwrite an **ignored** local file
(`aitasks/metadata/userconfig.yaml`, `*.local.json`) that an incoming or
replayed commit writes.

This was verified on git 2.55 during t1792. The exposure is documented in
`website/content/docs/commands/sync.md` ("Stashing and ignored files") and in
`do_pull_rebase`'s header comment.

An incoming commit can track a path that this checkout ignores in three ways:

- the path was tracked before its ignore rule was added;
- another checkout has different ignore rules;
- someone ran `git add -f`.

## Depends on t1678

The protection must hold while other framework writers run. Today they are not
excluded:

- **Branch mode.** `task_git` checks for an in-progress rebase or merge only
  **before** it runs git (`assert_data_worktree_clean`). That is a TOCTOU. A
  commit admitted before git creates its rebase state can run after any guard
  has passed, and between the rebase's own steps.
- **Legacy mode.** `ait_data_inprogress_state` deliberately returns nothing, so
  there is no check at all.

Writer exclusion has to hold across the **whole** guarded operation, from pin to
rebase finish, in **both** modes. That is t1678's data_index lock adoption.

## Accepted strategy (user decision on t1792): "refuse unless provably safe"

Refuse the diverged rebase unless all three hold:

- no path it writes holds an ignored file now;
- no path it writes is covered by an ignore rule;
- no path it writes is a `.gitignore`.

Under those conditions, any file that appears later at a written path is
untracked but not ignored, and git's own checkout refuses to overwrite it.

## Findings the design must satisfy (each confirmed in review, with repro shape)

1. **Pin the replay input, not only the base.** `--fork-point` and `@{u}` are
   mutable refs.
   - Repro: local commit L and remote commit U diverge. After the pin, another
     session publishes a merge M containing both U and L, and a fetch moves
     `@{u}` to M.
   - A `rebase --fork-point --onto <U> <upstream ref>` then exits 0 with HEAD at
     U, and L's file is gone.
2. **The written set must include every replayed commit's own writes**, not
   only the difference between the endpoints.
   - Repro: the base ignores userconfig.yaml. Local commit A force-adds it;
     local commit B untracks it; a private copy is then restored. Remote U
     touches another file.
   - The endpoint difference shows only U's file, but replaying A, then B,
     deletes the private copy.
   - Compute the set with
     `diff --name-only -z --no-renames --diff-filter=d HEAD U` plus
     `log --format= --name-only -z --no-renames --diff-filter=d U..HEAD`.
3. **Scan-to-write race.** A rebase writes with no ignored-file protection, so
   re-scanning just before it does not help. Check the ignore *rules* instead,
   which makes git's untracked-file protection the backstop.
4. **Late local commits must never enter the replay.** A commit made after the
   pin was replayed unchecked when the rebase read the current HEAD.
   - Repro: after the preflight, a holder commits an add of ignored
     userconfig.yaml and then an untrack, leaving private bytes on disk. The
     rebase deletes them.
5. **Ignore exceptions.** `git check-ignore --no-index -v -z --stdin` exits 0
   and prints the record when the matching rule is a `!negation`.
   - Classify with the non-verbose form, which prints only paths that really
     are ignored.
   - For the diagnostic, feed the path on stdin: `-z` without `--stdin` is
     fatal.
   - If the diagnostic fails, still refuse.
6. **Never re-attach HEAD outside git's rebase state.**
   - An explicit-commit rebase followed by `update-ref branch` and then
     `symbolic-ref HEAD` lets a writer commit onto the detached HEAD in between.
     That commit is orphaned and its content is left staged.
   - Either keep git's own finish (it updates the branch with a compare-and-swap
     against `orig-head`, then re-attaches HEAD, while its state still exists),
     or make the re-attach atomic.
   - `update-ref --stdin symref-update` needs git 2.46. That excludes Ubuntu
     24.04 (2.43) and Apple git (2.39).
7. **Rebase-state markers are a preflight, not an exclusion.** This is the
   dependency on t1678 above.

## Candidate design (from t1792's review)

- **Pin** `PULL_H` and `PULL_U`, and compute the written set from finding 2.
- **Preflight**, refusing on any of:
  - an ignored file present at, over or under a written path (reuse
    `_gm_ignored_hit`): `ERROR:pull_overwrites_ignored`;
  - a written `.gitignore`: `ERROR:pull_ignored_path`;
  - a written path covered by an ignore rule (finding 5): `ERROR:pull_ignored_path`,
    naming `<source>:<line>:<pattern>`;
  - any listing failure: `ERROR:pull_preflight_unverified`.
- **Apply with a guarded `rebase -i`** on the branch:
  `rebase -i --no-autostash --no-autosquash --empty=drop --no-fork-point
  -c rebase.updateRefs=false "$PULL_U"`.
  - Its pass-through `GIT_SEQUENCE_EDITOR` checks that both
    `rebase-merge/orig-head` and the branch named in `rebase-merge/head-name`
    equal `PULL_H`.
  - The editor runs after git has created its state and before anything is
    written. A non-zero exit removes the state and leaves everything unchanged.
- **Hold t1678's lock** from the pin to the rebase finish, in both modes.
- **Classify** a guard refusal as `ERROR:pull_head_moved`.
- **Verify first:** that the `-i` flags keep parity with today's non-interactive
  rebase, and how hooks time relative to the state's creation.

## Required test cells

Use `tests/lib/sync_fixture.sh`, whose `run_sync` isolates global git config.
Each cell needs a red-proof mutant run in an isolated scratch copy.

| cell | case | expected |
|---|---|---|
| C8 | **finding 1.** Local L (t20); remote U (t30). A `pre_pull_apply` racer merges U+L into M, pushes it, and fetches it locally. | the final HEAD has both edits; `SYNCED`. |
| C9 | **finding 2.** The add-then-remove local pair, with a private copy restored; remote touches t30. | `ERROR:pull_overwrites_ignored`; the private copy is unchanged; HEAD unchanged. |
| C4b | Diverged; local userconfig; remote force-adds it. | `ERROR:pull_overwrites_ignored`. |
| C6 | **Push-retry route.** A dirty unlocked t20 (the sweep commits it); local userconfig; a racing pre-push force-adds userconfig. | first output line `ERROR:pull_overwrites_ignored`. |
| C11 | Diverged; remote adds a new non-ignored path; a hook creates an untracked copy there after the checks. | git refuses; the copy is unchanged. |
| C11b | Diverged; remote force-adds userconfig; no local copy. | `ERROR:pull_ignored_path` naming the `.gitignore` rule; the seam that would create the file never fires. |
| C12 | Diverged; remote edits `.gitignore`. | `ERROR:pull_ignored_path`. |
| C13b | Diverged; a racer commit is fetched after the checks. | it is not applied; the push retry then refuses. |
| C15 | **finding 4.** A late add plus untrack after the pin, with the private copy restored. | `ERROR:pull_head_moved`; the private copy is unchanged; nothing written. |
| C16a | `info/exclude` has `aitasks/metadata/*.local` and `!aitasks/metadata/allowed.local`; remote adds `allowed.local`. | `SYNCED`. |
| C16b | As C16a, but the remote also force-adds `secret.local`. | `ERROR:pull_ignored_path` naming `secret.local` and its rule. |
| C18 | A writer commits inside git's own read-to-state window (a `pre-rebase` hook). | refused; the late commit stays on the branch. |
| C19 | A writer runs during git's finish (a `post-rewrite` hook). | refused, or its commit is an ancestor of the final HEAD; never orphaned. |
| C20 | Local commits `x` and `fixup! x`, with `rebase.autoSquash=true`. | both survive as separate commits. |
| C21 | A local commit becomes empty after rebasing. | it is dropped, and no rebase state is left. |
| — | **Concurrency**, in legacy mode **and** in branch mode. One writer starts while the state exists; another is admitted before the state exists and completes after validation. | no private bytes are lost; no commit is orphaned. |

## Also

- When this lands, update the "Stashing and ignored files" section of
  `website/content/docs/commands/sync.md`. It currently documents the diverged
  route as unprotected.
- Update the comment in `do_pull_rebase` that points here.
