---
priority: medium
effort: medium
depends: [t2175_4]
issue_type: feature
status: Implementing
labels: [sitrep]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
created_at: 2026-10-31 19:58
updated_at: 2026-11-04 15:36
---

# Monitor key: harvest-and-close

Child of t2175. Depends on the sitrep skill and window child.

## Scope
- A keybinding in `ait monitor` / `ait minimonitor` (see `aidocs/framework/tui_conventions.md`, shortcut scopes) that runs harvest for the selected finished/frozen agent, shows what was captured (items and any harvest warnings), and only then offers to close/drop the agent. Refuses to drop when harvest failed.
- Launch/focus the sitrep window from the TUI switcher / monitor (key to be chosen against existing bindings); show an indicator of open Pick-now items in the monitor if cheap.
- Spawn/drop mechanics: invoke `drop` through `run-shell -b` as `aitask_frozen.sh` requires, never inline in a TUI pane.
- Tests per `tui_conventions.md` and `testing_conventions.md` (Textual `run_test`, no in-flight workers at block exit).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2175_2** id=2026-11-03T09:12:22Z.769dd8ce090e35859bbd97cc from=t2175_2 from_verified=yes at=2026-11-03T09:12:22Z base=10957dd7286d560c7eb206bf7c25ee1043d40f41 base_branch=main dirty=yes host=omg16
>
> | The sitrep harvest landed in 10957dd72 (.aitask-scripts/aitask_sitrep_harvest.sh). What the monitor key needs:
> | 
> | 1. Live pane: capture the pane (aitask_shadow_capture.sh shape) and pipe it to `aitask_sitrep_harvest.sh capture --root <project root> --agent <window> --task <id> --operation <op>`. Frozen record: `aitask_sitrep_harvest.sh record <id>` (writes the receipt `<capture.txt>.harvested`).
> | 2. New drop/purge results the TUI must show: `aitask_agent_sessions.sh drop` exits 9 with HARVEST_REQUIRED:<id> when the capture has no valid receipt; `aitask_frozen.sh drop <id>` harvests first and can end DROP_REFUSED:<id>|harvest:<reason> (lease released, nothing killed); purge prints KEPT:<id>|unharvested_text. `--skip-harvest` (both drop verbs) is the explicit discard.
> | 3. drop_verdict (agent_sessions.py) now waits while the drop's coordinator holds a live lease (up to DROP_OBSERVE_CEILING = 180 s, the harvest can take 120 s), so "dropping…" can last much longer than 10 s.
> | 4. The monitor maintenance tick should run `aitask_sitrep_harvest.sh all` (detached, like reconcile) so kept records get harvested and become droppable/purgeable.

> **✉ note:t2175_3** id=2026-11-03T21:19:30Z.ef22bf99bb3cebf36daf28c7 from=t2175_3 from_verified=yes at=2026-11-03T21:19:30Z base=df3ee6c58928513c2b2d3b242a2051e8e6d0dc9f base_branch=main dirty=yes host=omg16
>
> | The sitrep refresh landed in df3ee6c58. The monitor's trailing maintenance already runs it: monitor/monitor_shared.py `_maybe_refresh_sitrep` (after `_maybe_purge_sessions` in `_dispatch_refresh_maintenance._maintenance()`), once per distinct observed root that has `.aitask-sitrep/store.init`, with `--budget 60` and a 75 s runner timeout derived from `_SITREP_REFRESH_BUDGET`.
> | 
> | 1. Put the harvest `all` job BEFORE `_maybe_refresh_sitrep()` in `_maintenance()` (a comment marks the spot), so items harvested in a pass are refreshed in the same pass.
> | 2. If the monitor shows an indicator: the script prints REFRESH_ITEM:/REFRESHED:/REFRESH_NONE:/REFRESH_FAILED: lines (wire contract in its header); exit 1 means nothing was written.
> | 3. `_run_marks_cmd`'s timeout kills only the direct child. For the refresh that is covered (its worker process group is killed at its own deadline, and a parent-death watchdog kills the group if the parent is killed from outside), but keep it in mind for a harvest job run through the same runner.

> **✉ note:t2175_4** id=2026-11-04T13:25:31Z.fb2c95ecc2a1da5e37f4385c from=t2175_4 from_verified=yes at=2026-11-04T13:25:31Z base=bdef300b0f247c561195b9eb0bada6af6b60c06e base_branch=main dirty=yes host=omg16
>
> | The sitrep skill and window landed in bdef300b0 (t2175_4). What the monitor key needs (tree-relative, as of that commit):
> | 
> | 1. Spawn/focus: call `monitor_core.spawn_sitrep(monitor, target_root=, session=, select_window=, agent_string=None)` (duck-typed on `monitor.tmux_run`). It returns `SitrepSpawn(status, pane, window, detail)`: status `spawned` (detail empty or `companion_not_spawned`), `focused`, `focus_failed` (a sitrep exists, switching failed), or `refused` (detail = reason: `lookup_failed`, `lock_busy`, `root:<why>`, `no_command`, `window_list_failed`, `launch:<why>`, `stamp:<…>`). Pass `select_window=False` from `ait monitor` to keep focus. Never read TMUX_PANE inside; the caller names the session.
> | 2. CLI equivalent: `ait sitrep [open] [--no-select]` (wire lines in `.aitask-scripts/aitask_sitrep.sh`'s header; `open` runs `monitor/sitrep_open.py`).
> | 3. Identity: window `agent-sitrep[-<n>]` (`sitrep_harvest.SITREP_WINDOW_RE` / `is_sitrep_window`), agent pane option `@aitask_sitrep_root=<canonical root>` (NOT a helper marker; the pane stays an agent). Indicator idea: `aitask_sitrep_todo.sh list` lines with group=now and state=open.
> | 4. Harvest-and-close: `aitask_sitrep_harvest.sh record`/`all` skip sitrep windows (`HARVEST_NONE:<id>|sitrep_agent` + receipt), but the `capture --agent <window>` verb does NOT consult the window name. A live-pane harvest-and-close must skip sitrep windows itself, or the sitrep screen (which echoes banners and trail handles) is fed back into the store.
> | 5. Codeagent op `sitrep` is Claude Code only for now (codex/opencode refuse before composing).

> **👁 note:read** id=2026-11-04T13:36:19Z.d04d2bbcacf3b2e07013e4e7 by=t2175_5 at=2026-11-04T13:36:19Z mode=explicit ids=2026-11-03T09:12:22Z.769dd8ce090e35859bbd97cc,2026-11-03T21:19:30Z.ef22bf99bb3cebf36daf28c7,2026-11-04T13:25:31Z.fb2c95ecc2a1da5e37f4385c
