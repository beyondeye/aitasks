---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [syncer, aitask_board, gitremote, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-07 15:55
updated_at: 2026-10-07 16:09
---

## Problem

`ait syncer` already lets the user hand a failed **code-branch** (`main`)
action to a code agent, but has no equivalent for the **aitask-data**
branch. When `ait sync` cannot auto-merge a data-branch conflict, the only
offer is an interactive `$EDITOR` walk. In practice we keep spawning an agent
by hand to resolve these conflicts. The syncer should offer it directly, the
same way it does for `main`.

## Current behaviour (as explored)

**Code branch — agent escape hatch exists.**
- `u` (`git pull --ff-only`) and `p` (`git push origin main:main`) failures go
  through `_fail` → `_capture_failure` → `SyncFailureScreen`
  (`.aitask-scripts/syncer/sync_failure_screen.py`), which offers
  **"Launch agent to resolve"** / **"Dismiss"**.
- "Launch" → `_launch_resolution_agent`
  (`.aitask-scripts/syncer/syncer_app.py`, ~L2424) builds a prompt (branch,
  action, command, status, output tail), resolves the `raw` operation via
  `resolve_dry_run_command` / `resolve_agent_string`, and opens an
  `AgentCommandScreen` (window `agent-syncfix-<action>`, rooted in
  `ctx.repo_root`). `launch_in_tmux`, plus `maybe_spawn_minimonitor` for a
  new window.
- `a` (`action_agent_resolve`) re-opens the last captured failure.

**aitask-data — no agent option.**
- `s` → `_sync_data_worker` → `run_sync_batch` (`aitask_sync.sh --batch`).
  `lib/task_automerge.sh` (`ait_automerge_rebase_loop`) auto-resolves
  task/plan conflicts first. Whatever it cannot resolve comes back as
  `CONFLICT:<f1>,<f2>`.
- `_on_data_sync_done` on `STATUS_CONFLICT` pushes the **shared**
  `SyncConflictScreen` (`.aitask-scripts/lib/sync_action_runner.py`, ~L409),
  which offers only **"Resolve Interactively"** (`run_interactive_sync` →
  spawn a terminal running `./ait sync`, which opens each conflicted file in
  `$EDITOR`) or **"Dismiss"**.
- `CONFLICT` does **not** call `_capture_failure`, so `a` afterwards says
  "No recent failure to resolve."
- (`STATUS_ERROR` / `STATUS_TIMEOUT` for `s` already capture a failure, so `a`
  works for those. `STATUS_DEFERRED` is deliberately NOT captured, because a
  deferral is sync correctly declining to touch another session's in-flight
  work. Keep it that way.)

**Board shares the modal.** `.aitask-scripts/board/aitask_board.py`
`_run_sync` / `_show_conflict_dialog` push the same `SyncConflictScreen` for
both manual sync and `sync_on_refresh` auto-sync. The board already imports
`AgentCommandScreen`, `resolve_dry_run_command`, `launch_in_tmux` and
`maybe_spawn_minimonitor`.

## Goal

When an aitask-data sync ends in `CONFLICT`, the user can launch a code agent
to resolve the remaining conflicts from the conflict modal, with the same UX
as the `main` escape hatch: `AgentCommandScreen`, configured default agent,
tmux window, and minimonitor. `a` can re-open it later.

## Design constraints / gotchas the implementation must handle

1. **The rebase is already aborted when the TUI sees `CONFLICT`.** In batch
   mode `do_pull_rebase` runs `rebase --abort` before printing
   `CONFLICT:...` (`aitask_sync.sh`, `do_pull_rebase`). The data worktree is
   clean, local commits are intact, and the remote commits are unapplied. The
   agent must **redo** the pull/rebase itself. The prompt therefore has to be
   a concrete procedure, not just "investigate this failure".
2. **`./ait git add` is refused mid-rebase.** `task_git` →
   `assert_data_worktree_clean` (`lib/task_utils.sh`) dies on any mutating
   subcommand while `.aitask-data` is mid-rebase unless
   `AIT_GIT_SKIP_STATE_CHECK=1` is set. Recovery verbs
   (`rebase --continue/--abort`) pass. The interactive path in
   `aitask_sync.sh` sets that bypass scoped to its own `task_git add`. The
   agent's procedure must say exactly how to stage a resolved file.
3. **Pin the same git options sync uses.** `AIT_RECONCILE_GIT_OPTS`
   (`-c rerere.enabled=false -c maintenance.auto=false`) is applied to every
   pull/rebase/abort in sync (t1789). An agent-driven rebase must not silently
   re-enable rerere.
4. **Try the automerge engine first.** The agent should resolve only what
   `task_automerge.sh` leaves, ideally by re-running the engine (or
   `./ait sync`) and hand-merging only the remainder, rather than
   re-resolving frontmatter conflicts by hand.
5. **Concurrency: a held rebase blocks every other session.** While
   `.aitask-data` is mid-rebase, every concurrent session's task writes
   (claim, status update, commit) die in `assert_data_worktree_clean`. An
   agent that thinks for minutes inside a live rebase is a real hazard on a
   machine running many agents. **Planning must decide** between (a)
   resolving in the shared worktree with an explicit "keep the rebase window
   short / abort on any doubt" rule, or (b) resolving in a scratch worktree
   or detached checkout of the data branch, then landing the result on the
   real `.aitask-data` with a fast-forward or short rebase. Prefer (b) if it
   can be done without reimplementing sync's guards.
6. **Finish through `ait sync`, never a raw push.** After resolving, the
   agent should publish via `./ait sync` (or `./ait git push`). Sync's
   publication quarantine, protected-dirty deferral and auto-commit scoping
   must stay in charge (memory: push = `ait git` only).
7. **Merged, not superseded.** The prompt must tell the agent that conflicts
   in task/plan markdown are semantic merges (frontmatter fields + body), so
   it keeps both sides' intent rather than choosing a side. Status
   vocabulary and `folded_*` / `children_to_implement` fields need care.

## Scope

- **Shared modal:** `SyncConflictScreen` gains a third button,
  **"Launch agent to resolve"**. Its dismiss value changes from `bool` to a
  small closed set (e.g. `"interactive" | "agent" | None`). Update every
  caller (syncer `_on_conflict_resolved`, board `_show_conflict_dialog`) in
  the same change. Do not leave a `bool` caller misreading a string.
- **Syncer:** build a data-conflict prompt (conflicted file list, repo root,
  the procedure from the constraints above) and launch it through the
  existing `_launch_resolution_agent` path, generalised or with a sibling
  builder, window e.g. `agent-syncfix-data-conflict`. Arm `a` for
  `CONFLICT` too, with a context that re-opens the **conflict** modal or the
  agent offer, not the generic failure modal with a misleading "Command"
  line.
- **Board:** wire the same agent option into `_show_conflict_dialog`. With
  `sync_on_refresh`, the modal can pop up unattended. Launching still
  requires the explicit button press. No unprompted spawn.
- **Out of scope:** automatically spawning an agent with no user action;
  agent handling for `DEFERRED:*` statuses; changing what
  `task_automerge.sh` can resolve (see t1459 for merge-causality work).
  Planning may note whether `DEFERRED:worktree_wedged` warrants a follow-up
  offer.

## Acceptance criteria

- A data-branch `CONFLICT` in the syncer shows a modal with "Launch agent to
  resolve", "Resolve Interactively" and "Dismiss". "Launch" opens
  `AgentCommandScreen` rooted in the conflicting repo (multi-repo rows target
  the right repo) with a prompt that carries the conflicted files and the
  resolution procedure.
- After dismissing a `CONFLICT` modal, `a` re-offers the resolution, so it no
  longer says "No recent failure".
- The board's conflict dialog offers the same agent option, and its existing
  interactive and dismiss behaviour is unchanged.
- The agent prompt's procedure is correct against the live guards: it does
  not tell the agent to run a `./ait git add` that `assert_data_worktree_clean`
  would refuse, it pins rerere off, and it publishes via `ait sync` /
  `ait git`.
- `DEFERRED` still does not arm the agent offer.

## Tests / docs touchpoints

- `tests/test_sync_action_runner.py` — modal dismiss values (all three
  buttons + escape).
- `tests/test_syncer_rows.py` (or a new syncer test) — `CONFLICT` arms `a`,
  the prompt builder includes the files and the procedure, and the
  multi-repo target is honoured. Patch the impure seams on `syncer_app` as
  the existing tests do.
- Board conflict-dialog callback test for the new dismiss value.
- Docs: `website/content/docs/tuis/syncer/_index.md` (Actions paragraph
  ~L129 and the failure-escape-hatch section ~L326),
  `website/content/docs/tuis/board/how-to.md` (~L480 "Handling conflicts"),
  `website/content/docs/tuis/board/reference.md` (~L688 Sync Conflict row).
  Run `python3 check_links.py --build` after editing.
