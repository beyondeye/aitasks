---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [tui, monitor]
gates: [risk_evaluated]
created_at: 2026-07-29 11:05
updated_at: 2026-07-29 11:05
---

## Problem

`ait monitor` and `ait minimonitor` classify every AGENT pane into one of three
states — `PROMPT` (awaiting user input), `IDLE` (content unchanged past the
threshold), `Active` — rendered as a colored `●` plus a text badge
(`monitor_shared.py:69` `_state_color`, `:116` `format_pane_status`; bold
magenta / yellow / green).

That vocabulary cannot express the most common end-state of a task-bound agent:
**the agent is idle because its task is finished and archived, not because it
stalled.** A completed `agent-pick-<id>` pane sits at `IDLE 412s` in yellow,
visually identical to an agent that hung. The user must open the task-info
dialog to tell the two apart.

Add a fourth status — **COMPLETED** — with its own color, shown when the pane's
task resolves to `Done` / archived.

## Current state (verified)

**Status is derived, never stored.** `PaneSnapshot`
(`.aitask-scripts/monitor/monitor_core.py:548-556`) carries only
`idle_seconds`, `is_idle`, `awaiting_input`, `awaiting_input_kind`. There is no
status enum; the `awaiting_input > is_idle > active` ladder is re-derived at
each consumer.

**One shared mapping, three inline duplicates.** Canonical:

- `monitor_shared.py:69` `_state_color(snap)` → `"bold magenta" | "yellow" | "green"`
- `monitor_shared.py:80` `format_state_dot(snap)` → colored `●`
- `monitor_shared.py:91` `format_shadow_glyph(shadow_snap)` → colored `◆`
- `monitor_shared.py:116` `format_pane_status(snap)` → `PROMPT Ns` / `IDLE Ns` / `Active`

Sites that hand-roll the same ladder instead of calling the above:

- `monitor_app.py:1195-1199` — SessionBar `N awaiting` / `N idle` counters (hardcoded magenta/yellow)
- `minimonitor_app.py:564-569` — second copy of the same counter markup
- `applink/pusher.py:390-415` — `pane_status` push to the mobile companion, its own wire schema over the four fields
- `monitor_app.py:1056-1093` `_maybe_auto_switch` — focus-jump preference (awaiting first, then most-idle)

**Pane → task binding is a single window-name regex.** `monitor_core.py:2387`:

```python
_TASK_ID_RE = re.compile(r'^agent-(?:pick|qa)-(\d+(?:_\d+)?)$')
```

Consumed pane-keyed via `TaskInfoCache.get_task_id_for_pane`
(`monitor_core.py:2530`), whose docstring documents `_pane_to_task_id` as a
forward-looking seam — there is no `@aitask_task_id` pane option, no claim
file, no registry. Known misses: `agent-resume-<num>` windows
(`board/aitask_board.py:7918`) and `unique_window_name()`'s `-2` collision
suffix (`lib/agent_launch_utils.py:1330`) do not match the anchored regex.

**The completion signal is already reachable — nothing new to parse.**
`aitask_archive.sh:143` rewrites `status: Done` and adds `completed_at:`, then
`:170` moves the file into `aitasks/archived/`. `TaskInfoCache._resolve`
(`monitor_core.py:2703`) already globs **both** `aitasks/` and
`aitasks/archived/` (its docstring says so explicitly) and returns
`TaskInfo.status` from frontmatter plus `task_file` / `task_file_abs`. Both
TUIs already call `get_task_info` for every agent pane on every refresh tick
(default 3 s — `monitor_app.py:1276-1287`, `minimonitor_app.py:632-646`), so
detecting COMPLETED needs **no new I/O layer**.

**The real blocker is cache staleness.** `TaskInfoCache._cache`
(`monitor_core.py:2492`) is keyed by `(session_name, task_id)` with **no TTL and
no file-identity key**. After the first resolution the file is never re-read,
so a task archived mid-session keeps rendering its pre-archival status
indefinitely. The only refresh paths are explicit `invalidate()` calls from
dialog actions (`monitor_app.py:2321, 2423, 2555`; `minimonitor_app.py:942,
1520`). `GateSummaryCache` (`monitor_core.py:2421`) already solves exactly this
with an `(st_mtime_ns, st_size)` identity key and is the pattern to copy — but
note archival **moves** the file, so a stat on the old path fails; the
freshness key must handle "resolved path no longer exists" by re-resolving,
not by failing closed to a stale entry.

**Prior Done-awareness exists only as a fallback heuristic**, and is partly
wrong: `monitor_app.py:2425-2427` treats a *missing* task file as `Done`
(`f"(archived t{task_id})"` / `"Done"`), and the kill-on-Done conditions at
`monitor_app.py:2500` / `minimonitor_app.py:1046` accept `not current_info or
current_info.status == "Done"`. Because `_resolve` already searches archived,
`current_info` is usually **not** `None` after archival — the file-missing
branch only fires for tar-bundled (`aitasks/archived/_b0/old*.tar.zst`) or
cross-project misses. The reliable post-archival signal is
`info.status == "Done"` after a fresh read.

**No legend, no tests.** Neither TUI documents the dot colors anywhere
(minimonitor's key-hints footer `minimonitor_app.py:270-279` covers only the
compare-mode glyphs `≈`/`=`; the full monitor uses a stock Textual `Footer()`).
No test in `tests/` asserts the rendered badge or dot text.

## Goal

A task-bound agent pane whose task has been completed and archived is visually
distinct at a glance in both TUIs, and stays correct as the task transitions
mid-session.

## Acceptance criteria

1. **New COMPLETED state.** A fourth state exists in the status ladder,
   returned for an AGENT pane whose resolved `TaskInfo.status == "Done"` (or
   whose task file resolves under `aitasks/archived/`). Its precedence relative
   to `PROMPT` / `IDLE` / `Active` is decided and documented in the plan —
   consider that a completed agent may still be sitting on a final prompt.
2. **Own color, same glyph.** COMPLETED gets a distinct color (not magenta /
   yellow / green) applied to the existing `●` dot, and a distinct badge text
   in `format_pane_status`. Colour choice must remain legible on both dark and
   light terminal themes.
3. **One ladder, no new duplicates.** The state is added in
   `monitor_shared._state_color` / `format_pane_status`, and the three
   hand-rolled sites (`monitor_app.py:1195`, `minimonitor_app.py:564`,
   `applink/pusher.py:403`) are either migrated to the shared helper or
   explicitly and test-guarded kept in sync. The applink wire schema change is
   coordinated with the mobile companion (see `aidocs/applink/protocol.md`) —
   if a schema bump is not in scope, say so explicitly and keep the push
   backward-compatible.
4. **Freshness.** `TaskInfoCache` re-reads a task whose file changed or moved,
   using the `GateSummaryCache` file-identity pattern, without adding a
   per-tick disk read for unchanged tasks. Archival (file move) must invalidate
   the entry, not silently keep serving the pre-archival `TaskInfo`.
5. **Non-task panes unaffected.** Panes with no resolvable task id
   (`agent-explore-*`, `agent-raw-*`, TUI / OTHER panes) never render
   COMPLETED.
6. **`agent-resume-<id>` gap.** Either extend `_TASK_ID_RE` to cover
   `agent-resume-` (and any other launcher-emitted prefix carrying a task id),
   or document why it is out of scope. Whatever is chosen, unit-test the regex
   against every window name the framework's launch sites actually emit
   (`monitor_app.py:2507,2587`; `minimonitor_app.py:1016`;
   `board/aitask_board.py:6989,7161,7918`; `codebrowser/history_screen.py:430`).
7. **Legend.** The status vocabulary (including COMPLETED) is discoverable from
   inside at least one TUI surface, and documented in
   `aidocs/framework/monitor_idle_and_prompt_detection.md`.
8. **Tests.** Render-level tests assert the produced text/markup for all four
   states from both card builders (`monitor_app._format_agent_card_text`,
   `minimonitor_app._agent_card_text`) — there is zero coverage today. Include
   a freshness test that flips a task to `Done` + moves it to `archived/`
   mid-run and asserts the card updates.

## Notes

- `aidocs/framework/monitor_idle_and_prompt_detection.md` is stale on two
  points and should be corrected as part of this work: it names
  `tmux_monitor.py` as the home of `_finalize_capture` (it moved to
  `monitor_core.py`; `tmux_monitor.py` is a pure re-export shim), and its
  "three sites consume `awaiting_input`/`is_idle`" list predates the applink
  pusher/router consumers and the `_state_color` / `format_state_dot` /
  `format_shadow_glyph` split.
- `aitasks/` is a symlink to `.aitask-data/aitasks` (separate git repo) — path
  resolution and mtime checks must not assume a plain directory.
- Do **not** try to detect completion from `aitask_archive.sh`'s structured
  stdout (`ARCHIVED_TASK:` / `COMMITTED:` etc., documented at `:60-79`) — those
  lines go to the invoking skill only and are not persisted.
- Follow-up: per-gate emoji on the agent card (created alongside this task;
  depends on the freshness and card-rendering work here).

Read `aidocs/framework/tui_conventions.md` and
`aidocs/framework/monitor_idle_and_prompt_detection.md` before implementing.
