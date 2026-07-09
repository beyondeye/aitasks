---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [tui, git-integration, project_groups]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/fable5
created_at: 2026-07-08 08:42
updated_at: 2026-07-09 09:34
---

## Goal

Add cross-repo support to the `ait syncer` TUI (`.aitask-scripts/syncer/`), modeled on the multi-project pattern already implemented in the `ait stats` TUI. The user wants to see changes / desync status of **all registered repos in one TUI** and issue push / pull / sync commands from that single place.

**Decision (scoped in exploration):** per-repo actions only. The selector switches which repo you view, and `sync` / `pull` / `push` act on the **selected** repo. The aggregate "All projects" row is a **read-only status overview** — no batch fan-out of actions across repos (that can be a follow-up if wanted).

## Current state (single-repo)

- `syncer/syncer_app.py` (`SyncerApp`, ~545 lines) — fixed 2-row `DataTable` (`main`, `aitask-data`) with Status / Ahead / Behind / Last-refresh, plus a detail pane. Bindings: `r` refresh, `s` sync (data branch), `u` pull (main), `p` push (main), `f` fetch-toggle, `a` resolve-with-agent, `q` quit. Row-gating via `check_action`.
- `lib/desync_state.py` — computes state. `repo_root()` is hardcoded `Path.cwd()` (line ~45). Crucially, `snapshot_ref(name, fetch, root)` **already accepts a `root` param**; only `snapshot()` (which hardcodes the 2 refs and does not thread `root`) needs generalizing. `detect_primary_branch()` / `physical_main_branch()` are already per-worktree and generalize cleanly.
- Actions are **CWD-bound** — the main cross-repo work:
  - `lib/sync_action_runner.py` shells out to relative `./.aitask-scripts/aitask_sync.sh --batch` (CWD-dependent).
  - `syncer_app.py` `_main_pull_worker` / `_main_push_worker` run raw `git` in the CWD `main` worktree (`_main_worktree` = `Path(".")`).
  - `aitask_sync.sh` locates its data worktree via `_AIT_DATA_WORKTREE` from `lib/aitask_path.sh`, relative to CWD.

## Reference model — `ait stats` TUI cross-repo (replicate this)

- Discovery: call `discover_aitasks_sessions(include_registered=True)` from `.aitask-scripts/lib/agent_launch_utils.py` → yields live tmux + registry (`~/.config/aitasks/projects.yaml`) repos as `AitasksSession` objects, keyed on `realpath(project_root)` via `AitasksSession.key`. This is the single reusable seam — do NOT reinvent registry parsing or shell out to `aitask_project_resolve.sh`.
- UI: left-sidebar `ListView` project selector (`#session_panel`) + aggregate sentinel `ALL_SESSIONS_KEY = "__all__"` ("All projects"); ←/→ cycle repos, `[` / `]` cycle project groups. Gated on `len(sessions) >= 2` (`multi_session`).
- Data layer parameterized on `project_root`, read **in-process** per repo, memoized per key. Aggregate = merge of per-repo results.
- Reusable pure helpers (all in `agent_launch_utils.py`, shared with stats + TUI switcher): `cross_group_ring` / `cross_group_step`, `default_selected_group`, `advance_group_selection`, `resolve_selected_key`, `disambiguate_labels`.
- See `stats/stats_app.py` for the concrete selector + `_cycle_session` / `_cycle_group` / `_apply_session_selection` flow, and `aidocs/framework/cross_repo_references.md` for registry schema + resolver protocol.

## Work breakdown (indicative — refine in planning)

1. **Read layer (easy):** Generalize `desync_state.snapshot()` to accept a repo `root` and thread it through to `snapshot_ref` (already root-aware). Confirm ahead/behind/paths git calls run against the given worktree, not CWD.
2. **Discovery + selector UI:** Call `discover_aitasks_sessions(include_registered=True)`; add the stats-style `ListView` selector + `ALL_SESSIONS_KEY` aggregate; reuse `disambiguate_labels`, `default_selected_group`, `cross_group_*` for labels/navigation. Gate on `>= 2` repos so single-repo UX is unchanged.
3. **Aggregate view:** Read-only overview across all discovered repos (status/ahead/behind per repo × per ref). No actions from the aggregate row.
4. **Action layer (the hard part):** Retarget the CWD-bound action backend at the **selected** repo root:
   - `sync_action_runner.run_sync_batch()` must run `aitask_sync.sh` inside the selected repo (e.g. via `cd` into the root, an absolute script path + `--repo`/cwd, or `ait projects exec <name> -- ...`). Pick the cleanest seam and note the trade-off.
   - `_main_pull_worker` / `_main_push_worker` and `_main_worktree` must target the selected repo's worktree rather than `Path(".")`.
   - Verify `physical_main_branch` / `detect_primary_branch` resolve against the selected repo.
5. **Selection-scoped action gating:** `check_action` must gate `s`/`u`/`p` on the currently-selected repo+ref, and disable actions entirely when the aggregate ("All projects") row is selected.

## Considerations / open questions for planning

- **Action-targeting mechanism** for `aitask_sync.sh`: subprocess `cwd=<root>` with an absolute script path is likely simplest and keeps parsing intact; evaluate vs `ait projects exec`. Whichever is chosen, keep a dry-run/test seam that doesn't need live git state (see the resolve/target split pattern used elsewhere in the framework).
- **Refresh cost:** fetching desync state for N repos every `--interval` seconds could be heavy — consider staggering, on-demand refresh for non-selected repos, or reusing the threaded worker per repo.
- **Blast radius / safety:** actions now mutate *other people's* repos from one TUI — ensure the selected-repo target is unambiguous and confirm gating so a mis-highlighted row can't push/pull the wrong repo.
- **Failure/agent-resolution path** (`_launch_resolution_agent`) builds prompts + launches tmux for the CWD repo; decide whether/how it retargets per selected repo.
- Keep `desync_state.py`'s Python `detect_primary_branch` in sync with `lib/git_utils.sh` (documented twin).

## Tests

- Unit-test the per-repo `snapshot(root=...)` read path against a fixture repo (not CWD).
- Unit-test the action-target resolution seam (command construction with a repo root) without live git — assert the right cwd/path/args, mirroring the existing dry-run split.
- Test `check_action` gating: actions disabled on aggregate row; enabled per selected repo+ref.
- Single-repo regression: with `< 2` repos, the selector is absent and behavior is unchanged.
- Reference the syncer/stats TUI test conventions (Textual render-level + pure-helper unit tests).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-09T06:34:13Z status=pass attempt=1 type=human
