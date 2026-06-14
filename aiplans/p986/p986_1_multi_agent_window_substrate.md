---
Task: t986_1_multi_agent_window_substrate.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_2_*.md, aitasks/t986/t986_3_*.md, aitasks/t986/t986_4_*.md, aitasks/t986/t986_5_*.md, aitasks/t986/t986_6_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: aiwork/t986_1_multi_agent_window_substrate
Branch: aitask/t986_1_multi_agent_window_substrate
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-14 16:37
---

# Plan: t986_1 — Multi-agent-per-window substrate + shadow helper-pane exclusion

## Context

Foundation for the shadow agent (t986). The shadow is a *second* coding agent in
the shadowed agent's tmux window. The tmux gateway + capture are pane-keyed
(safe); six monitor app-layer sites assume one agent per window. Re-key monitor
state on `pane_id` and classify the `shadow` pane as a helper so it is excluded
from agent lists.

**Shadow lifecycle coupling (user requirement).** A shadow is bound to one
specific shadowed agent. When that agent's pane ends, its bound shadow pane must
be killed automatically — even if other agents remain in the same window. This
task implements the cleanup-side consumption and defines the binding contract;
t986_5 (spawn glue) sets the binding and wires the hook (see Cross-task contract).

**t719 coordination — resolved.** t719's impactful children (t719_1 control-client,
t719_2 hot-path integration) are Done + archived, and t822_6 (2026-06-14) already
extracted the control-client code into `monitor_core.py`. This plan rebases against
that already-stable, refactored layout — no active conflict.

## Plan verification (2026-06-14, verify path)

Re-checked every cited site against the current tree (post-t822_6). All file
paths and line numbers below are accurate as written. One nuance recorded in
step 2: `TaskInfoCache` keeps a primary cache keyed by `(session_name, task_id)`
**and** a secondary `_window_to_task_id` dict (keyed by `window_name`) consumed by
`get_task_id(window_name)` — the latter is the window→task assumption to re-key.

## Binding contract (shadow ↔ shadowed agent)

The shadow pane carries a tmux **user option** `@aitask_shadow_target` set to the
shadowed agent's `pane_id` (e.g. `%7`). tmux user options are pane-scoped, survive
for the pane's lifetime, and are enumerable via `list-panes -F '#{@aitask_shadow_target}'`
— no parallel state file. t986_5 sets it at spawn (`set-option -p ... @aitask_shadow_target`);
this task reads it in classification + cleanup. A pane with this option set is, by
definition, a shadow helper pane (it complements the `agent-shadow-*` window-name /
shadow-op-in-cmdline detection in step 4).

## Implementation steps

1. **Extract pure units** (no Textual import): pane→task-id mapping and
   per-window agent-pane counting, so they can be unit-tested in isolation.
2. **Re-key task→pane resolution** (`monitor/monitor_core.py`): `_TASK_ID_RE`
   (~1381) + `TaskInfoCache` (~1398-1450). Replace the window-keyed
   `_window_to_task_id` lookup behind `get_task_id()` with a `pane_id`-keyed
   resolution (or `(window_index, pane_index)`); thread the pane id through the
   monitor/minimonitor display, sibling, and kill paths. (The `(session_name,
   task_id)` primary cache is unaffected — the window name is the input that must
   become pane-derived.)
3. **`kill_agent_pane_smart()`** (1278-1318): keep `kill_window()` only when ALL
   agent panes in the window are gone; otherwise `kill_pane()`. Today it already
   filters companions via `_is_companion_process()` when counting `others` —
   ensure shadow panes are filtered the same way (step 4) so the count is correct.
4. **Companion classification** (`_is_companion_process()` 152-170 — keyword set
   `_COMPANION_KEYWORDS` ~149; `classify_pane()` ~877-885 + companion filter in
   `_parse_list_panes()` ~910-912): recognize the `shadow` pane (window name
   `agent-shadow-*`, shadow op in cmdline, and/or the `@aitask_shadow_target`
   user option) and exclude it from agent snapshots — exactly as
   minimonitor/monitor panes are excluded today.
5. **`minimonitor_app.py:_find_sibling_pane_id()`** (674-697): resolve the
   intended agent pane by id (reuse `own_snap.pane.pane_id` from
   `_find_own_agent_snapshot()` ~403-422, already surfaced as `own_pane_id` at
   ~599), not `other_panes[0]`.
6. **monitor_app.py display sites** (982, 1120, 1509-1513): derive task-id per
   pane (via the step-2 pane-keyed resolver) instead of from
   `snap.pane.window_name`.
7. **Launch path** (`lib/agent_launch_utils.py`): refocus the just-launched pane
   captured from `split-window -P` / `new-window`, not the hardcoded `.0`
   (753-758); account for a shadow pane in `maybe_spawn_minimonitor()`'s
   `len(pane_lines) >= 3` skip (728-740) so the companion still spawns with a
   shadow present.
8. **Cleanup — shadow auto-kill + per-pane companion accounting**
   (`aitask_companion_cleanup.sh`, currently `<primary> <companion>` →
   counts window siblings, kills companion only if none remain). Raw tmux stays
   (allowlisted Layer-A hook). On an agent pane's `pane-died`:
   - **Kill bound shadows:** enumerate panes (session-scoped, to also cover the
     configurable separate-window placement) via
     `list-panes -s -F '#{pane_id}\t#{@aitask_shadow_target}'`; `kill-pane` every
     pane whose `@aitask_shadow_target` equals the dying `primary` — independent of
     whether other agents remain.
   - **Exclude shadows from the sibling count:** a pane with `@aitask_shadow_target`
     set is a helper, not a real agent, so it must NOT count toward `others`
     (otherwise a leftover shadow would wrongly keep the minimonitor alive / block
     window collapse). The minimonitor companion survives only while a *real*
     agent sibling remains.
   - Killing a *different* agent in the window must leave an unrelated shadow alive
     (its `@aitask_shadow_target` differs).
9. Keep all raw tmux behind the gateway in the Python layer —
   `tests/test_no_raw_tmux.sh` allowlist unchanged (monitor_core.py /
   aitask_companion_cleanup.sh / the monitor apps are already listed).

## Cross-task contract (t986_5)

t986_5's spawn glue must, when launching a shadow: (a) set
`@aitask_shadow_target=<shadowed_agent_pane_id>` on the shadow pane, and (b)
ensure the shadowed agent's pane has a `pane-died` hook invoking
`aitask_companion_cleanup.sh` (agents launched with a minimonitor already have
this hook; an agent that gets only a shadow needs t986_5 to attach it). This task
makes the cleanup script shadow-aware; t986_5 establishes the binding + hook. Add
a reverse coordination note to t986_5 at implementation time.

## Verification

New tests follow the existing monitor-headless precedents
(`tests/test_kill_agent_pane_smart.sh`, `tests/test_multi_session_monitor.sh`,
`tests/test_launch_in_tmux_pane_pid.py`): bash harness + embedded Python, mock
`_is_companion_process()`, real-tmux fixtures (isolated `TMUX_TMPDIR` / private
socket) for integration tiers.

- pane_id-keyed task map resolves the correct task per pane (not per window).
- Two agents in one tmux window: killing one leaves the other alive with correct
  task-ids; killing the last collapses the window.
- `_find_sibling_pane_id()` returns the intended agent pane (by id), not the
  first non-companion pane.
- A `shadow`-classified pane (window `agent-shadow-*` / shadow op / `@aitask_shadow_target`
  set) is absent from monitor and minimonitor agent lists and from
  `kill_agent_pane_smart` peer counts.
- **Shadow lifecycle:** with a shadow bound to agent A (`@aitask_shadow_target=A`)
  in a window also holding agent B — killing A auto-kills its shadow; killing B
  leaves A's shadow alive; a shadow never keeps the minimonitor alive once the
  last real agent is gone.
- `bash tests/test_no_raw_tmux.sh` stays green; `shellcheck
  .aitask-scripts/aitask_companion_cleanup.sh` clean.

## Risk

### Code-health risk: medium
- Re-keys operationally-destructive central paths (`kill_agent_pane_smart` window-vs-pane decision, the shadow-aware `pane-died` cleanup hook, `TaskInfoCache` task-id resolution); a keying/binding bug could kill the wrong agent's pane/window or orphan/over-kill a shadow · severity: medium · → mitigation: in-scope (step-1 pure-unit tests + the multi-pane & shadow-lifecycle real-tmux integration tests in `## Verification`; live behavior covered by the t986_7 aggregate manual-verification sibling)
- Wide blast radius across 5 files and several central functions, but every site was verified against the current tree, the approach mirrors the already-correct pane-keyed `capture_pane()`/`capture_all_async()` reference, the binding uses a single pane-scoped tmux user option (no parallel state), and the gateway invariant is guarded by `test_no_raw_tmux.sh` · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- None identified. Approach verified-sound against current code; all 6 sites + shadow exclusion confirmed to exist as described; `_find_own_agent_snapshot()` already exposes the pane_id the sibling-finder needs. The shadow lifecycle coupling is delivered here cleanly via the `@aitask_shadow_target` contract; its spawn-side counterpart is explicitly assigned to t986_5.

_No `### Planned mitigations` subsection: the code-health risk is mitigated in-scope (this task owns its tests; t986_7 covers live verification). No separate before/after follow-up task would add value._

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
