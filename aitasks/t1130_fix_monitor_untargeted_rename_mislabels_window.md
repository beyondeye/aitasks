---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tmux, monitor, tui, codeagent]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 941
created_at: 2026-07-05 16:03
updated_at: 2026-07-05 16:26
---

Fix the monitor's `on_mount` window-rename so it can never mislabel an unrelated window as `monitor`. This is a **t941 follow-up**.

## Root cause — untargeted `rename-window` fallback in the monitor

**Observed:** In a live `aitasks` session, an explore agent (`claude … /aitask-explore`) with its companion minimonitor pane occupied a window named `monitor` (with `automatic-rename off`), alongside the legitimate `monitor` window. The explore window is spawned via `tui_switcher._spawn_in_session` as `new-window -n agent-explore-N`, so it is born correctly named — it was renamed afterward. Since `rename-window` is what turns `automatic-rename off`, a full-monitor `on_mount` ran `rename-window monitor` against this window.

**Cause:** `.aitask-scripts/monitor/monitor_app.py`
- `on_mount` (lines 487-490) calls `subprocess.run(_rename_window_argv(os.environ.get("TMUX_PANE")), …)`.
- `_rename_window_argv(pane)` (lines 62-74) appends `-t <pane>` **only when `pane` is truthy**; when `TMUX_PANE` is unset/empty it emits the **untargeted** `tmux rename-window monitor`.
- tmux resolves an untargeted `rename-window` to the **attached client's active window**. With `automatic-rename off`, that permanently mislabels whatever window is focused. If a `monitor_app` process starts without `TMUX_PANE` while a freshly-spawned `agent-explore-N` (or any agent) window is active, that window becomes `monitor` — the exact t941 symptom, still reachable through the fallback branch.
- t941 (commit `bc50549d3`) pinned the rename to `$TMUX_PANE` but deliberately **retained** the untargeted fallback, and `tests/test_monitor_rename_window_target.sh:51-54` currently **asserts** that `None`/`''` produce the untargeted form — i.e. the regression test enshrines the failure mode.

## Fix (fail-safe)
- In `monitor_app.py` `on_mount`, **skip the rename entirely** when `TMUX_PANE` is falsy — never emit the untargeted form. There is no reliable way to identify the monitor's own window without `TMUX_PANE`, so renaming an arbitrary active window is always wrong. The rename exists so the TUI switcher can find the monitor; that only matters on the normal path where `TMUX_PANE` is set.
- Update `tests/test_monitor_rename_window_target.sh` so the `None`/`''` cases assert **no rename is issued**, converting the regression guard from blessing the bug to guarding the fix. Keep the truthy-pane assertion (`-t %7`).
- Consider adding a single-instance guard to `.aitask-scripts/aitask_monitor.sh` mirroring `.aitask-scripts/aitask_minimonitor.sh:33-42`, so a second `monitor_app` cannot start (and re-run the rename) inside a window that already hosts a monitor/minimonitor. (Secondary hardening; scope per the risk gate.)

## Acceptance criteria
- A `monitor_app` started without `TMUX_PANE` in its environment issues **no** `rename-window`, leaving the active window's name untouched.
- Normal launch (with `TMUX_PANE` set) still renames the monitor's own window to `monitor`.
- `tests/test_monitor_rename_window_target.sh` asserts the no-rename behavior for falsy pane and passes.

## Scope note — folded root cause B already resolved (t1115)
This task originally folded in `t_fix_agent_launch_tui_window_reuse`, which described a *second* root cause for the same symptom: the shared `AgentCommandScreen` reusing a remembered `monitor` window for `pick`/`raw`/etc. launches. On investigation that fix **already landed in t1115** (`should_default_to_new_window` in `.aitask-scripts/lib/agent_command_screen.py:136-152`, with `tests/test_agent_command_dialog_default_session.py`). Root cause B is therefore **out of scope** here (already fixed); this task is narrowed to root cause A. The folded task's original content is preserved below as historical context.

## Merged from t_fix_agent_launch_tui_window_reuse (RESOLVED by t1115 — historical)

> The following was the folded task's content. Its fix already landed in t1115; retained for provenance only.

Fix code-agent launches from the shared `AgentCommandScreen` so pick/raw/explain/etc. launches do not accidentally reuse an existing TUI window such as `monitor` when the caller passed a new `agent-*` default window name.

- **Observed symptom:** launching `/aitask-pick 1111_2` with Codex produced a Codex `node` pane in a tmux window named `monitor` instead of `agent-pick-1111_2`.
- **Fix that landed (t1115):** `_compute_window_options()` now calls `should_default_to_new_window(default_window_name, operation, explicit_tmux_window)` — explicit caller window wins; otherwise an `agent-`/`create-` prefixed `default_window_name` or a fresh-window operation forces `+ New window`, so a remembered `monitor` window no longer poisons agent launches. Covered by `tests/test_agent_command_dialog_default_session.py`.
