---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [monitor, minimonitor, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1934, 1935]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-08 17:14
updated_at: 2026-10-09 15:34
---

## Problem

A single pane whose working directory wanders into another aitasks repo
remaps the **whole tmux session** to that repo. Every monitor/minimonitor row
for the session then resolves its task against the wrong project: no task
title on `agent-pick-<id>` rows, and no COMPLETED/DONE glyph for archived
tasks.

Observed 2026-10-08 in session `aitasks`:
- The tmux global env holds `AITASKS_PROJECT_aitasks=/home/ddt/Work/aitasks`,
  set by `ait ide`.
- Pane `1:1` (window `aitasks`, a `claude` process) had
  `pane_current_path=/home/ddt/Work/thinking_app`. Every other pane in the
  session was in `/home/ddt/Work/aitasks`.
- `discover_aitasks_sessions_checked()` returned
  `AitasksSession(session='aitasks', project_root=/home/ddt/Work/thinking_app, ...)`.
- As a result, minimonitor rows for t1888 (archived), t1914 and the others
  showed no title and no DONE glyph.
- Sessions `thinking_back` and `thinkingapp` were unaffected because none of
  their panes moved.
- Resolving the same tasks directly with
  `TaskInfoCache(Path('/home/ddt/Work/aitasks'))` works:
  t1888 → Done/archived, t1914 → Implementing. The task data is fine; only
  the session→root mapping is wrong.

## Cause

`.aitask-scripts/lib/agent_launch_utils.py`:
- `_collect_live_roots` (~L1289) tries `_project_root_from_pane_paths` first.
  It returns the **first** pane cwd that walks up to an aitasks project
  (~L1112).
- The explicit `AITASKS_PROJECT_<session>` registry value is consulted only
  when **no** pane resolves.

So one pane listed first, for example a Claude Code session whose process cwd
followed a cross-repo `cd`, overrides both the explicit registration and the
majority of panes.

## Goal

Make the session→project-root mapping robust to one wandering pane:
- **Prefer an explicit `AITASKS_PROJECT_<session>` value** over the pane-cwd
  guess when it names a valid project root (marker file present).
- Fall back to pane cwds only when the variable is absent or invalid.
- When pane cwds disagree and no explicit value exists, do not let pane order
  decide. Use a deterministic rule such as a majority vote, the agent panes'
  roots, or the session's first window. Planning chooses the rule and records
  why.

**Blast radius.** `_collect_live_roots` feeds every consumer:
- `discover_aitasks_sessions`, `_checked` (used by
  `aitask_project_resolve.sh candidates`, t1869) and `_async`;
- monitor/minimonitor `get_session_to_project_mapping_async`;
- the TUI switcher, applink and stats.

Check each consumer's expectation and keep the `_checked` completeness
contract.

## Tests

Add a regression test over the pluggable `run` / `read_registry` seam of
`_collect_live_roots`. A session has one pane in repo B and the rest in repo
A, and the registry names repo A: the result must be A. Also cover:
- no registry value with mixed panes;
- a registry value pointing at a path with no marker file;
- all panes agreeing.

## Trigger and blast radius (user report, 2026-10-08)

**Trigger.** The mis-mapping began when the user **closed the first two windows**
of the `aitasks` session: the `ait monitor` and `ait brainstorm` TUIs. This fits
the cause above. `list-panes -s` lists panes in window-index order, and
`_project_root_from_pane_paths` returns the first pane cwd that walks up to a
project. While the TUI windows existed, their panes, whose cwd was
`/home/ddt/Work/aitasks`, came first and masked the wandering `claude` pane.
Closing them made that pane (window 1, cwd `/home/ddt/Work/thinking_app`) the
first one listed, which flipped the whole session's root on the next tick.

This is order-dependent: the same set of panes resolves differently depending
on which windows happen to sort first. That ordering itself should not decide
the root.

**Not a pane↔task pairing cache.** `TaskInfoCache._pane_to_task_id` is keyed by
`pane_id` and derived from the window name. Closing other windows changes
neither, and the rows still show their `agent-pick-<id>` window names. The
failure is downstream, at the root: `get_task_info(task_id, session)` resolves
against `_root_for_session(session)`, which is now the wrong repo.

**Also lost while mis-mapped: priority/parked marks.** Marks are keyed by
`(canonical project root, window name)` (`agent_marks.mark_key`), looked up via
`AgentMarksMixin._root_for_session` → `_session_root_map`
(`monitor_shared.py:1325`), which is fed the same discovery mapping every tick
(`minimonitor_app.py:1602`, `monitor_app.py:1045`). So the starred and parked
states of the session's agents disappear along with the titles and DONE glyphs.

**Mark data is hidden, not deleted (verified by reading the purge).** The
liveness purge (`AgentMarksMixin._observed_agent_windows`, ~`monitor_shared.py:1290`,
then `agent_marks` purge ~L468) only sweeps roots that some enumerated session
maps to. While mis-mapped, no session maps to `/home/ddt/Work/aitasks`, so its
marks are not sweepable and survive; they reappear once the mapping is
corrected.

**Hazard:** a mark set or cycled *while* the session is mis-mapped is written
under the wrong root (e.g. `agent-pick-1914` under `thinking_app`). Planning
should check whether such a stray mark can later be purged or misapplied when
the thinking_app session is swept, and add a regression test.

**Also broken: minimonitor pick-by-number (`p`), and it can launch the WRONG
task (user report, 2026-10-08).** Picking t1922 from the minimonitor reported
"Task t1922 not found". The cause:
- `action_pick_by_number` binds `target_root = self._root_for_snap(snap)`
  (`minimonitor_app.py:3249`);
- `_on_pick_number_entered` resolves `get_task_info(target_id, sess)`
  (`:3274`).

Both go through the same session → root map, which points at thinking_app.
t1922 exists only in aitasks, so the lookup fails. **When the id also exists in
the mis-mapped repo** (thinking_app has ids up to t493, so any colliding number),
the dialog shows the *other repo's* task and `_launch_pick` starts
`/aitask-pick <id>` in that repo. That is a silent wrong-task launch, not just a
display gap. The task info dialog (`i` / `I`, `_show_task_info_for`, `:5167`)
fails the same way.

This raises the severity. Planning should list every consumer of
`_session_root_map` / `TaskInfoCache` session roots that **acts**: pick
launches, next-sibling `n`, re-pick of a frozen agent, restore, kill dialogs.
Each must refuse rather than act when the session's root is ambiguous (panes
disagree with each other, or with `AITASKS_PROJECT_<session>`). Display-only
consumers may degrade.

**Test:** a pick-by-number regression where the followed pane's session is
registered to repo A, one pane sits in repo B, and the typed id exists in both
repos. It must resolve and launch in A, or refuse; never B.

**Also affected: the TUI switcher (`j`).** `tui_switcher.py` builds its list
from `discover_aitasks_sessions(include_registered=True)`. While mis-mapped,
that list (observed 2026-10-08) holds **two `aitasks` entries**: a live one
rooted at `thinking_app` and a registered one rooted at `aitasks`. The live
`thinkingapp` session is **missing**, collapsed into the first entry by the
key-dedupe on project root.

`j` → board from the minimonitor therefore ran
`new-window -t aitasks: -c /home/ddt/Work/thinking_app -n board …`, opening
thinking_app's board inside the `aitasks` session. That board then crashed on
an unrelated stale-module bug, filed as t1926. Add the switcher to the
consumer audit: its selected entry, the dedupe, and the window spawn cwd.

**Tests to add (in addition to the ones above):**
- order dependence: the same pane set, with the wandering pane listed first and
  then last, must resolve to the same root;
- marks: with the session mapping corrected, marks keyed under the right root
  are found again; while mis-mapped, they are not purged.

## Workaround

`cd` the wandering pane back into its own repo, or close it. The monitor picks
up the fix on its next refresh.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-09T08:13:31Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-09T12:28:44Z status=pass attempt=1 type=human
