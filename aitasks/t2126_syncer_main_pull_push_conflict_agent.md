---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [syncer, git, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
folded_tasks: [1791]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-22 12:48
updated_at: 2026-10-22 12:49
---

## Problem

In `ait syncer`, the aitask-data sync (`s`) has a dedicated conflict flow. When `ait sync --batch` reports `CONFLICT`, the syncer keeps a `DataConflictContext` (which `a` re-opens) and shows `SyncConflictScreen` with **Launch agent to resolve** / **Resolve Interactively**. The agent gets a purpose-built prompt (`build_data_conflict_prompt` in `lib/sync_action_runner.py`) that states the context, the goal, the constraint and the known pitfalls.

The `main`-row actions have no counterpart. `u` (pull) and `p` (push) run git directly in `_main_pull_worker` / `_main_push_worker` (`.aitask-scripts/syncer/syncer_app.py` ~2475-2539 at base 6dc5b76a4; re-derive, the file moves). They send **every** non-zero exit through `_fail`, which opens the generic `SyncFailureScreen`. Its agent prompt (`_launch_resolution_agent`) is only the command, a status and a stderr tail. It gives no guidance for the one failure the user actually needs help with: local and remote `main` have diverged.

- Pull: `git pull --ff-only` refuses when the branch has diverged.
- Push: `git push origin main:main` is rejected (`non-fast-forward` / `fetch first`) when the remote is ahead.

## Goal

Give both main-branch actions a conflict path that matches the data-sync one, so that a diverged pull and a rejected push each offer a code agent set up to integrate local and remote `main`.

1. **Classify the failure** in both workers. A diverged `--ff-only` pull and a non-fast-forward / fetch-first push rejection are recognised from markers that only that operation prints (stop evidence must be operation-specific). Run the classified git commands with a pinned C locale, so that a localized git does not silently drop the classification. Any other failure (auth, network, timeout, a refusal to overwrite files) stays on the generic `SyncFailureScreen` path, unchanged.
2. **A dedicated main-conflict context and dialog.** It is a sibling of `DataConflictContext` that records the action (pull/push), branch, repo root, label and output tail. It is stored in `_last_failure` so that `a` re-opens it, and it is rooted in the repo the action targeted, as the multi-repo rows already are. The dialog names the repo and states what diverged. It dismisses with a closed value set, and callers dispatch by equality, as `SyncConflictScreen` does (t1911). Deciding whether to reuse/generalize `SyncConflictScreen` or add a new screen is part of planning. "Resolve Interactively" in its `ait sync` meaning does not apply to `main`. Offer an interactive alternative only if it has a real meaning here, for example a terminal in that repo.
3. **A purpose-built prompt builder** next to `build_data_conflict_prompt`. It follows the same shape: context, the outcome wanted, the constraints, and the pitfalls that are facts about this setup. It is not a recipe. The outcome: local and remote `main` integrated with both sides' commits kept, the result published for the push case, and the live checkout up to date. Constraints that apply because the main checkout is shared by several live agent sessions: never force-push; never stash, reset or check out other sessions' uncommitted edits; leave no merge or rebase in progress in the shared checkout; and ask the user when the choice between merge and rebase, or an ambiguous resolution, is theirs to make. Pitfall: a rebase drops merge commits. The tmux window name is distinct, e.g. `agent-syncfix-main-<action>`.
4. **Pull precondition (merged from t1791, below):** drop the blanket dirty-worktree refusal and let `git pull --ff-only` decide. Still refuse up front when the checkout is mid-rebase or mid-merge, and decide on `--no-autostash` / `--no-overwrite-ignore` (see t1792's probe note, merged below). A "would be overwritten" refusal is not divergence. It stays a plain failure that surfaces git's message.

## Acceptance criteria

- Diverged `main` + `u` → the main-conflict dialog. **Launch agent** opens `AgentCommandScreen` with the new prompt, rooted in that repo. `a` re-opens the same dialog from another row.
- Remote ahead + `p` → the main-conflict dialog for the push case, with a prompt that requires publishing and forbids force-push.
- Any other pull/push failure → the generic `SyncFailureScreen`, as today.
- Classification unit tests feed real git output captured in scratch repos (diverged pull, non-fast-forward and fetch-first rejections, and a non-conflict failure as the negative control). A mutant that drops the classifier must fail them.
- The t1791 acceptance criteria below hold.
- `website/content/docs/tuis/syncer/_index.md` (key table plus "Failure handling") documents the new dialog. Run `python3 check_links.py --build` from `website/`.

## Touchpoints

- `.aitask-scripts/syncer/syncer_app.py`: `_main_pull_worker`, `_main_push_worker`, `_fail`, `action_agent_resolve`, `_launch_*_agent`
- `.aitask-scripts/lib/sync_action_runner.py`: the new prompt builder, plus the shared dialog if one is reused/generalized (the board also imports `SyncConflictScreen`, so keep its contract)
- `.aitask-scripts/syncer/sync_failure_screen.py`: only if the context types are reorganised
- `tests/test_syncer_rows.py` (existing failure/conflict modal tests ~2900-3100, 3696), `tests/test_sync_action_runner.py` (prompt tests)
- `website/content/docs/tuis/syncer/_index.md`

## Merged from t1791: syncer main pull refuses any dirty worktree


## Problem

The syncer's code-branch pull refuses whenever the worktree is dirty at all, although the command it guards refuses only when it would actually overwrite something.

`_main_pull_worker` (`.aitask-scripts/syncer/syncer_app.py` ~2326-2334 at base e7bcb66c — re-derive, the file moves) checks `git status --porcelain`. Any output makes it refuse with "Working tree dirty — stash or commit before pulling", before it ever runs `git pull --ff-only`. A fast-forward-only pull refuses only when it would **overwrite** a dirty or untracked file, which is a strictly weaker precondition.

The user runs several code agents at once in the same checkout, so the working tree is dirty almost all the time. The syncer's main-branch pull therefore almost never runs.

## Origin

Raised as point 4 of an inbox note on t1731, sent from a t1725 explore session. The user had reported "syncer fails because of dirty worktree", and this refusal message matches that report. It is unconfirmed which message they actually saw. Filed as a follow-up of t1731, whose data-branch fix has the same shape: an over-strong precondition in front of a git command that already guards itself. This is a separate, code-branch surface.

## Goal

Let git decide. Drop the blanket dirty-worktree refusal and run `git pull --ff-only`. When it refuses, surface git's own message, which names the files that would be overwritten, not a generic line.

Keep refusing up front when the checkout is mid-rebase or mid-merge. Consider `--no-autostash`, and whether `--no-overwrite-ignore` is appropriate here: git's default silently overwrites ignored files.

## Acceptance criteria

- An unrelated dirty file, with the remote ahead on other files: the pull fast-forwards, and the dirty file is byte-identical afterwards.
- The remote changes the dirty file: the pull is refused, and the message names that file.
- A diverged branch, where no fast-forward is possible: refused, as today.
- The checkout is mid-rebase: refused before any pull runs.


## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1791** (`t1791_syncer_main_pull_refuses_any_dirty_worktree.md`)

## Folded History

Reference only: the notes and gate history these tasks carried before they were folded. Their markers are neutralized, so none of it is part of this task's inbox or gate ledger.

### t1791: syncer main pull refuses any dirty worktree

#### Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> | **✉ note:t1792** id=2026-10-14T15:34:56Z.51ee8eadce7fc3ad26c6b2b3 from=t1792 from_verified=yes at=2026-10-14T15:34:56Z base=7f1d0614a333c14f0130789c8a22e2233e6d9db0 base_branch=main dirty=no host=omg16
>
> | Advisory context from t1792. These are probe results on git 2.55.0 in scratch repos, valid as of commit 02e4a1bad. They bear on this task's "consider --no-autostash / --no-overwrite-ignore" question.
> | 
> | - **Autostash on a fast-forward.** `merge --ff-only` with `merge.autoStash=true` stashes and re-applies an unrelated dirty tracked file. The file's inode and ctime change even though its bytes come back. With `--no-autostash` the file is left untouched.
> | - **Ignored files on a fast-forward.** `merge --ff-only` (git's default `--overwrite-ignore`) and a behind-only `pull --rebase` both silently overwrite an ignored local file that an incoming commit writes. With `--no-overwrite-ignore`, git refuses at write time and leaves HEAD, the index and the worktree unchanged. That holds for the exact path, for an ignored file where an incoming directory goes, and for an ignored directory where an incoming file goes.
> | - **Git's refusal message** names the files raw, with control characters replaced by '?'. If you print it, avoid `echo -e` / `warn()`, which would decode any literal backslash sequence in a filename.
> | - **What `ait sync` now does** (aitask_sync.sh `do_pull_rebase`): it fast-forwards only to a pinned upstream SHA, using `--ff-only --no-autostash --no-overwrite-ignore`. A refusal is reported and never retried as a rebase.
> | 
> | Whether the same flags fit the syncer's `pull --ff-only` on main is this task's decision.
