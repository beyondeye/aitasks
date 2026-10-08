---
Task: t1911_syncer_agent_resolve_data_sync_conflict.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1911 — Launch a code agent to resolve an aitask-data sync CONFLICT

## Context

`ait syncer` can hand a failed `main` pull/push to a code agent
(`SyncFailureScreen` → `_launch_resolution_agent`). The **aitask-data** branch
has no equivalent. When `ait sync --batch` ends in `CONFLICT:<files>`, the
shared `SyncConflictScreen` offers only "Resolve Interactively" (an `$EDITOR`
walk) or "Dismiss", and `a` afterwards says "No recent failure to resolve".
That modal is used by the syncer's `s`, the board's manual sync and its
`sync_on_refresh` auto-sync. People keep spawning an agent by hand.

This task does three things:
- adds an agent option to the shared modal;
- wires it into both TUIs;
- gives the agent a prompt that states the situation, the outcome wanted, one
  hard constraint and the known pitfalls. The agent chooses its own approach.

## Design decisions

### D1 — Agent autonomy: context + outcome + one constraint (user direction, 2026-10-07)

The prompt is **not** a recipe. It carries:

- **Context:**
  - the repo root and the conflicted files;
  - the state `ait sync` left behind: in batch mode it aborts its rebase
    before printing `CONFLICT:`, so `.aitask-data` was clean on the local
    branch with the remote commits unapplied, and the state may have moved
    since;
  - that `ait sync` without `--batch` opens `$EDITOR`.
- **Desired outcome:**
  - the conflicts resolved as semantic merges: task and plan files are
    *merged, not superseded*, keeping both sides' intent in frontmatter and
    body;
  - the aitask-data branch integrated with the remote and published;
  - the live `.aitask-data` checkout up to date, with any worktree the agent
    created removed;
  - **at the end** (user direction, 2026-10-07): other sessions' ongoing work
    is preserved. That means their uncommitted edits in `.aitask-data` and
    any commits they made there while the agent worked. The shared checkout
    is left usable, with no unresolved merge or rebase in progress.
- **The one central constraint:** resolve in a separate worktree, never in
  `.aitask-data`. That checkout is shared by every session on the machine, and
  while it is mid-rebase or mid-merge their task writes fail
  (`assert_data_worktree_clean`).
- **Brief factual pitfalls** (the shadow review's findings, verified against
  the code):
  - an ordinary rebase drops merge commits, so resolution edits that exist
    only in a merge commit can disappear without a conflict — and both
    `ait sync` and the framework's push retry (`_task_pull_rebase`) rebase
    when they pull;
  - the auto-merge driver (`.aitask-scripts/board/aitask_merge.py`, which
    `ait sync` runs) can undo deliberate changes. It unions `labels`/`depends`
    without the merge base (`aitask_merge.py:415-418`), re-adding an entry one
    side removed, and lets `Implementing` beat `Done` for `status` (`:426-428`).
- **A verification requirement:** before finishing, verify that the final
  integrated result preserves the intended resolution — both as published on
  the remote and in the live `.aitask-data`. The method is the agent's choice.
- **Autonomy and asking:**
  - it follows the repository's own instructions;
  - it chooses its tools, merge or rebase strategy, commands and recovery;
  - it asks the user when intent is ambiguous or a decision needs them;
  - there is no fixed retry count and no "stop and ask on every failure".

**What this supersedes.** The task file's constraints 2–4 and 6 and acceptance
criterion 4 asked for a prescribed procedure: no `./ait git add` mid-rebase,
rerere pinned off, publishing via `ait sync`/`ait git`. They are replaced by
this direction. The isolation constraint makes the `./ait git add`-mid-rebase
guard moot for `.aitask-data`, and the publication path is the agent's choice,
judged by the verified outcome. Recorded in the Final Implementation Notes.

### D2 — Unchanged scope

- The conflict dialog gets three buttons and a closed dismiss set.
- The syncer wiring re-offers the conflict on `a`.
- The board wiring launches only on an explicit button press.
- `DEFERRED:*` stays un-armed.
- `DEFERRED:worktree_wedged` gets no agent offer: a wedged worktree may be a
  live session's in-progress resolution. At most a diagnose-first follow-up;
  noted, not created.

## Implementation steps

### 1. Shared modal + prompt builder — `.aitask-scripts/lib/sync_action_runner.py`

- New constants:
  ```python
  #: SyncConflictScreen dismiss values — a CLOSED set (t1911); None = Dismiss/escape.
  CONFLICT_CHOICE_AGENT = "agent"
  CONFLICT_CHOICE_INTERACTIVE = "interactive"
  #: tmux window for the data-conflict resolution agent (syncer and board).
  DATA_CONFLICT_WINDOW_NAME = "agent-syncfix-data-conflict"
  ```
- `SyncConflictScreen.__init__(self, conflicted_files, repo_label: str = "")`.
  - Title: `"Sync Conflict Detected"`, plus `f" — {repo_label}"` when set
    (multi-repo syncer).
  - Body ends: "Launch a code agent to resolve them, or resolve them yourself
    in an interactive terminal?"
  - Buttons, in order:
    - `Button("Launch agent to resolve", variant="warning", id="btn_sync_agent")`;
    - `Button("Resolve Interactively", variant="primary", id="btn_sync_resolve")`
      (id kept);
    - `Button("Dismiss", id="btn_sync_dismiss")`.
  - Handlers dismiss with `CONFLICT_CHOICE_AGENT` /
    `CONFLICT_CHOICE_INTERACTIVE` / `None`; `action_cancel` → `None`.
  - Dialog widened (60% → ~72%, checked by the render test) so three buttons
    fit at 120 columns.
- New pure `build_data_conflict_prompt(conflicted_files, repo_root) -> str`.
  It filters empty names (a bare `CONFLICT:` parses to `[""]`); with none left
  it says the sync did not name the files and the agent should inspect the
  state. Draft text (wording may tighten):

  ```
  An `ait sync` of the aitask-data branch in <root> stopped on merge conflicts
  its auto-merge engine could not resolve:
    - <f1>
    - <f2>

  Context: in batch mode `ait sync` aborts its rebase before reporting a
  conflict, so at that moment the shared `.aitask-data` checkout was clean on
  the local aitask-data branch — local commits intact, remote commits not
  applied. The state may have moved since; check it yourself. (`ait sync`
  without `--batch` opens $EDITOR on conflicts.)

  Goal: resolve the conflicts and leave the aitask-data branch integrated with
  the remote and published, with the live `.aitask-data` checkout up to date.
  Task and plan files are merged, not superseded: keep both sides' intent, in
  frontmatter and body. Choose your own approach, tools and recovery,
  following this repository's instructions. Ask the user when the intended
  merge is ambiguous or a decision needs their input.

  When you are done, other sessions' ongoing work must be preserved — their
  uncommitted edits in `.aitask-data` and any commits they made there while
  you worked — and the shared checkout must be usable, with no unresolved
  merge or rebase in progress.

  Constraint: do the resolution in a separate git worktree, never in
  `.aitask-data`. That checkout is shared by every session on this machine,
  and while it is mid-rebase or mid-merge their task writes fail. Keep it
  available to them throughout.

  Pitfalls:
  - An ordinary rebase drops merge commits, so edits that exist only in a
    merge commit's conflict resolution can disappear without any conflict —
    and `ait sync` and the framework's push retry both rebase when they pull.
  - The auto-merge driver (`.aitask-scripts/board/aitask_merge.py`, which
    `ait sync` runs) can undo deliberate changes: it unions list fields such as
    `labels` and `depends` without consulting the merge base (re-adding an
    entry one side removed), and it lets `Implementing` win over `Done` for
    `status`.

  Before you finish, verify — by whatever method you choose — that the final
  integrated result preserves the intended resolution, both as published on
  the remote and in the live `.aitask-data` checkout, and that the end state
  above holds. Remove any worktree you created.
  ```
- Update the module docstring's layer list (the modal now has three buttons;
  the module also owns the conflict agent prompt).

### 2. Syncer — `.aitask-scripts/syncer/syncer_app.py`

- Import the three constants and `build_data_conflict_prompt`.
- New frozen dataclass next to the failure escape hatch:
  ```python
  @dataclass(frozen=True)
  class DataConflictContext:
      """The last aitask-data CONFLICT, kept so `a` re-offers ITS resolution
      (t1911) — a sibling of SyncFailureContext, not an instance: a conflict has
      no failed command, and the generic modal would render one anyway."""
      target: ActionTarget
      conflicted_files: tuple[str, ...]

      @property
      def repo_root(self) -> Path:   # None root = legacy CWD (the launch repo)
          return (self.target.root or Path(".")).resolve()
  ```
- `self._last_failure: SyncFailureContext | DataConflictContext | None`.
- `_on_data_sync_done`, CONFLICT branch: build the context, store it in
  `_last_failure`, call `_open_conflict_screen(ctx)`, return. The DEFERRED
  branch is untouched (still not captured).
- `_open_conflict_screen(ctx)`: pushes
  `SyncConflictScreen(list(ctx.conflicted_files), repo_label=ctx.target.label)`
  with `lambda choice: self._on_conflict_resolved(choice, ctx)`.
- `_on_conflict_resolved(choice, ctx)`:
  - `== CONFLICT_CHOICE_AGENT` → `_launch_data_conflict_agent(ctx)`;
  - `== CONFLICT_CHOICE_INTERACTIVE` → `_run_interactive_sync_shared(ctx.target)`;
  - then `_tick_refresh()` as today.
  - Equality only: a stray truthy value launches nothing.
- `action_agent_resolve`:
  - `None` → notify "No recent failure or conflict to resolve.";
  - `DataConflictContext` → `_open_conflict_screen`;
  - else → `_open_failure_screen`.
- Generalise `_launch_resolution_agent`:
  - Extract its tail into `_launch_agent(*, title, window_name, prompt,
    project_root)`: resolve the command and agent string,
    `AgentCommandScreen(operation="raw", operation_args=[prompt])`, then
    `launch_in_tmux` + `maybe_spawn_minimonitor`, then `_tick_refresh`.
  - The failure path keeps its exact prompt, title and window.
  - New `_launch_data_conflict_agent(ctx)` calls it with:
    - title `"Resolve aitask-data sync conflict"` (+ `f" on {label}"` in
      multi-repo);
    - `DATA_CONFLICT_WINDOW_NAME`;
    - `build_data_conflict_prompt(ctx.conflicted_files, ctx.repo_root)`;
    - `project_root=ctx.repo_root`, so multi-repo rows target their own repo.

### 3. Board — `.aitask-scripts/board/aitask_board.py`

- Import the constants and the builder from `sync_action_runner`.
- `_show_conflict_dialog.on_result(choice)`:
  - `CONFLICT_CHOICE_INTERACTIVE` → `_run_interactive_sync_shared()`
    (unchanged);
  - `CONFLICT_CHOICE_AGENT` → `_launch_data_conflict_agent(files)`;
  - anything else → `load_tasks()` + `refresh_board()` (unchanged dismiss).
- New `_launch_data_conflict_agent(files)`, shaped like `_launch_work_report`:
  - prompt from `build_data_conflict_prompt(files, Path(".").resolve())`;
  - command from `resolve_dry_run_command(Path("."), "raw", prompt)`; None →
    error notify, no dialog;
  - `AgentCommandScreen(..., default_window_name=DATA_CONFLICT_WINDOW_NAME,
    project_root=Path("."), operation="raw", operation_args=[prompt],
    default_agent_string=resolve_agent_string(Path("."), "raw"))`;
  - result `"run"` → `self.run_dialog_command(screen.full_command)`;
    `TmuxLaunchConfig` → `launch_in_tmux` + `maybe_spawn_minimonitor` on a new
    window; then reload and refresh.
  - Docstring: reachable only from the explicit button. With `sync_on_refresh`
    the dialog can pop up unattended, and nothing spawns without the press.

### 4. Tests — launch context, isolation requirement, intended outcomes (no Git recipe)

- `tests/test_sync_action_runner.py`:
  - `SyncConflictScreenTests` (a tiny host `App`, `run_test`):
    - the three buttons and escape dismiss with `"agent"` / `"interactive"` /
      `None` / `None`;
    - `repo_label` reaches the title;
    - at (120, 30) the three buttons lie inside the dialog and do not overlap.
  - `BuildDataConflictPromptTests`, checking content by intent, not by exact
    commands:
    - **launch context:** every conflicted file and the absolute repo root
      appear; a bare `[""]` is filtered and replaced by the "did not name the
      files" wording; the prompt says the sync aborted its rebase and that the
      state may have moved since;
    - **isolation requirement:** it requires a separate worktree, forbids
      resolving in `.aitask-data`, and gives the reason (shared by other
      sessions whose writes fail mid-rebase);
    - **intended outcomes:** resolved, integrated with the remote, published,
      live checkout up to date, created worktrees removed, "merged, not
      superseded";
    - **end state:** other sessions' ongoing work is preserved (uncommitted
      edits and commits made meanwhile in `.aitask-data`), and the shared
      checkout is left usable with no unresolved merge or rebase in progress;
    - **verification:** the final published and live result must be verified
      to preserve the resolution and that end state, method left open;
    - **pitfalls:** the rebase/merge-commit loss and the auto-merge driver
      undoing deliberate changes;
    - **ask the user** when intent is ambiguous.
- `tests/test_syncer_rows.py`, new `DataConflictAgentTests(_TabbedShellBase)`:
  - Patches on `syncer_app`: `resolve_dry_run_command`,
    `resolve_agent_string`, `AgentCommandScreen` (a spy ModalScreen — avoids
    real tmux probes), `run_interactive_sync`, `maybe_spawn_minimonitor`.
  - CONFLICT shows the three-button modal.
  - Escape, then `a`, re-opens the **conflict** modal (not
    `SyncFailureScreen`), with the same files.
  - Agent button: the spy gets `DATA_CONFLICT_WINDOW_NAME`,
    `operation="raw"`, `operation_args=[prompt]`, and a prompt carrying the
    files. In a two-repo boot, the selected repo's root is `project_root`,
    `resolve_dry_run_command`'s root and the root named in the prompt.
  - Dismissing the spy with a new-window `TmuxLaunchConfig` →
    `launch_in_tmux` + minimonitor.
  - Interactive button → `run_interactive_sync(repo_root=target.root)`.
  - Dismiss launches nothing.
  - `DEFERRED` leaves `_last_failure` None.
  - A captured `SyncFailureContext` still opens `SyncFailureScreen` via `a`.
- New `tests/test_board_sync_conflict_agent.py` (the construction-spy pattern
  of `tests/test_board_dialog_run_dispatch.py`, `bf.FixtureBoardTestBase`):
  - `_show_conflict_dialog` pushes `SyncConflictScreen(files)`.
  - Callback routing: `"interactive"` → `_run_interactive_sync_shared`;
    `"agent"` → `_launch_data_conflict_agent(files)`; `None` and a stray
    `True` → reload only.
  - `_launch_data_conflict_agent` builds the screen with the window name, the
    raw op and a file-bearing prompt rooted at the board's repo.
  - `"run"` → `run_dialog_command(full_command)`; tmux config →
    `launch_in_tmux` + minimonitor; unresolvable command → error notify, no
    screen.

### 5. Docs (current-state only)

- `website/content/docs/tuis/syncer/_index.md`:
  - the `a` rows (L125, L312) → "Re-open the most recent failure or data-sync
    conflict";
  - the L129 paragraph names the three-option conflict dialog;
  - "Failure handling" gains a data-conflict paragraph:
    - the three buttons and the window `agent-syncfix-data-conflict`;
    - the agent gets the conflicted files and the goal, and resolves in its
      own worktree so `.aitask-data` stays usable by other sessions;
    - it finishes with other sessions' work preserved and no merge or rebase
      left in progress;
    - it verifies the published result;
    - `a` re-offers the dialog, and deferrals do not arm it;
  - L349 → "the agent escape hatch on failure or conflict".
- `website/content/docs/tuis/board/how-to.md` "Handling conflicts": three
  options; the agent launches only on the button press (also with sync on
  refresh).
- `website/content/docs/tuis/board/reference.md` Sync Conflict row: three
  options.
- Check `website/content/docs/commands/sync.md` for dialog wording.
- `cd website && python3 check_links.py --build`.

## Verification

- `python3 -m pytest tests/test_sync_action_runner.py tests/test_syncer_rows.py tests/test_board_sync_conflict_agent.py tests/test_board_dialog_run_dispatch.py -q`
- The full Python suite once at the end (read the last-line verdict only).
- `cd website && python3 check_links.py --build`
- Manual (Step 8c candidate):
  - boot `ait syncer` against a fixture in a CONFLICT; check the three-button
    modal render and that `a` re-opens it;
  - launch the agent once on a real conflict and confirm it resolves in a
    separate worktree and verifies the published result.

## Notes

- Upstream defect (pre-existing, out of scope — for Step 8b): the syncer's
  agent launch callback ignores `AgentCommandScreen`'s `"run"` result, so
  "Run in terminal" silently does nothing (`syncer_app.py:2454-2461`, carried
  into `_launch_agent`). The fix needs a cwd-aware terminal spawn for
  multi-repo rows.
- The engine behaviours named in the pitfalls also affect ordinary `ait sync`
  auto-merges. That is merge-causality work owned by t1459; offer an
  `/aitask-note` there at Step 8e.
- Step 9 (Post-Implementation): current-branch profile, so no merge; archive
  with `aitask_archive.sh 1911` after the `risk_evaluated` gate.

## Risk

### Code-health risk: low
- The shared modal's dismiss contract changes from `bool` to a closed string set; a missed caller doing `if resolve:` would read `"agent"` as truthy and open the interactive sync. Only two callers exist (syncer, board — grepped), both change in the same commit, dispatch is by equality, and a stray-`True` test pins it · severity: low · → mitigation: none
- The syncer's `_last_failure` now holds two context types, dispatched by `isinstance` in `action_agent_resolve`; covered by tests for both branches · severity: low · → mitigation: none
- One more `AgentCommandScreen` launch site on the board (the idiom already repeats ~6× there); it follows `_launch_work_report` exactly · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The quality of the resolution rests on the agent's judgement. The prompt states the outcome, the isolation constraint, the two verified pitfalls, and a mandatory verification of the published and live result, but no step is enforced. The earlier procedure-helper follow-up (`helperize_data_conflict_procedure`) was dropped on the user's direction: enforcing a fixed workflow is no longer the intended design · severity: medium · → mitigation: none
- The agent could still choose a strategy that loses a merge-only resolution, or accept a driver result that undoes a deliberate change. Both are named as pitfalls, and the outcome-verification requirement is the backstop; a live manual check is offered at Step 8c · severity: low · → mitigation: none
- With `sync_on_refresh`, the board re-pops the conflict dialog every interval while an agent is already resolving (pre-existing re-pop behaviour); noisy, not harmful — the agent works in its own worktree · severity: low · → mitigation: none

## Post-Review Changes

### Change Request 1 (2026-10-08 12:40)
- **Requested by user:** (1) at 80 columns the three-button row needs 64 content columns but the dialog gives 51, clipping "Dismiss" — keep all three visible and add an 80-column regression case; (2) the syncer doc said the agent targets the highlighted row's repo, but `a` re-targets the repo whose sync conflicted; (3) the conflict modal still derives from bare `ModalScreen` (follow-up, not this task).
- **Changes made:** (1) `#sync_conflict_dialog` gets `min-width: 72` (64 content + 6 border/padding, plus slack); the render test now checks 80/100/120 columns against the dialog's CONTENT region. A valid negative control (`min-width: 0` override) measured 57 wide and clipped at 80. (2) Doc now says "rooted in the repository whose sync conflicted (also when you re-open the dialog with `a` from another row)". (3) Recorded under Upstream defects for a Step 8b follow-up.
- **Files affected:** `.aitask-scripts/lib/sync_action_runner.py`, `tests/test_sync_action_runner.py`, `website/content/docs/tuis/syncer/_index.md`

## Final Implementation Notes
- **Actual work done:**
  - `lib/sync_action_runner.py`: `SyncConflictScreen` has three buttons and dismisses with the closed set `CONFLICT_CHOICE_AGENT` / `CONFLICT_CHOICE_INTERACTIVE` / `None`. It takes an optional `repo_label` and is `72%` wide with a `min-width: 72`. New pure `build_data_conflict_prompt()` and `DATA_CONFLICT_WINDOW_NAME`.
  - `syncer/syncer_app.py`: new `DataConflictContext`. CONFLICT is stored in `_last_failure` so `a` re-opens the conflict modal. `_launch_resolution_agent` is split into a shared `_launch_agent(...)` plus `_launch_data_conflict_agent(ctx)`, rooted in the conflicting repo.
  - `board/aitask_board.py`: equality routing in `_show_conflict_dialog`, plus a new `_launch_data_conflict_agent(files)`.
  - Tests: the modal (dismiss values, title, button fit at 80/100/120 columns), the prompt (context, isolation, outcome, end state, verification, pitfalls — no Git recipe), syncer `DataConflictAgentTests` (6), and new `tests/test_board_sync_conflict_agent.py` (8).
  - Docs: syncer, board how-to and reference, and `commands/sync.md`.
- **Deviations from plan:**
  - The plan went through three rounds before approval:
    1. The 10-step recipe.
    2. A publish-from-scratch design plus a `merge_audit.py` tool, after the shadow review.
    3. By user direction, an autonomy-oriented prompt: context + outcome + one constraint (a separate worktree) + two factual pitfalls + outcome verification + the end state (other sessions' work preserved, no merge or rebase left in progress).
  - Dropped: the recipe, the audit tool, the Git fixture test and the `helperize_data_conflict_procedure` mitigation.
  - This supersedes the task file's constraints 2–4 and 6 and acceptance criterion 4 (a prescribed procedure that pinned rerere and published via `ait sync`/`ait git`).
  - The modal floor `min-width: 72` was added in review.
- **Issues encountered:**
  - An 80-column clip was found in review. At 80 columns `72%` alone leaves 51 content columns against the 64 the buttons need.
  - A first negative control was invalid because Textual merges a base class's `DEFAULT_CSS` into a subclass. An explicit `min-width: 0` override was used instead.
- **Key decisions:**
  - Dispatch is by equality on the closed dismiss set, so a stray truthy value launches nothing (a stray `True` is pinned by a test).
  - The conflict context targets the repo whose sync conflicted, also when `a` re-opens it from another row.
  - `DEFERRED:*` is still never captured. `DEFERRED:worktree_wedged` gets no agent offer: it may be a live session's resolution.
- **Upstream defects identified:**
  - `.aitask-scripts/syncer/syncer_app.py:2518-2525` — the syncer agent-launch callback (`_launch_agent.on_launch`, inherited from the old `_launch_resolution_agent`) ignores `AgentCommandScreen`'s `"run"` result, so "Run in terminal" silently does nothing for both the failure and the data-conflict agent. The fix needs a cwd-aware terminal spawn for multi-repo rows.
  - `.aitask-scripts/lib/sync_action_runner.py:496` and `.aitask-scripts/syncer/sync_failure_screen.py:26` — `SyncConflictScreen` and `SyncFailureScreen` derive from bare `ModalScreen` against the `GuardedModalScreen` dismissal rule in `aidocs/framework/tui_conventions.md`. A stale `action_cancel` after the next modal opened popped that next modal (review: PLAUSIBLE; natural key timing unverified).
