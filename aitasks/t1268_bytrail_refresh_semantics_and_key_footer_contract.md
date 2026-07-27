---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
created_at: 2026-07-27 18:07
updated_at: 2026-07-27 18:17
---

## Problem

The By-Trail view (`.aitask-scripts/board/aitask_board.py`) shows stale task
statuses that cannot be refreshed from within the view, and its footer
advertises actions that do something else — or nothing at all.

Observed: with trail `art:trail-gates-framework-landing` open, t1264 rendered
as `Ready` while its file on disk had said `status: Implementing` for hours.
No key in the view could fix that.

## Findings (verified against the source, 2026-07-27)

### 1. Card status is live-sourced but never re-read

`TrailTaskCard.compose` (aitask_board.py:1869) renders
`self.task_data.metadata.get("status")`, and `build_trail_lanes` (:533)
documents that it deliberately never trusts `snapshot.status` from the
artifact. So the display contract is correct — the data feeding it is not.

Nothing in the By-Trail path re-reads task files:

- `refresh_board()` (:5790) never calls `manager.load_tasks()`.
- `_set_base_filter` calls `load_tasks()` only for `inflight` (:6214-6217).
- `_activate_trail` (:7076) and `s`-rescan re-fetch the **artifact blob**
  only, via `ait artifact get`.

So a card shows whatever `load_tasks()` last cached.

### 2. The one local path is unreachable in practice

`_refresh_board_data()` (:5765) does exactly the cheap recompute we want:
`load_tasks()` + re-project the cached `_trail_doc`, which recomputes both
`landed` (:547/:552) and the `📋 <status>` label (:1869-1871) with zero
subprocesses. But:

- `r` is intercepted before it (:5781) whenever a trail is active, so the
  key never reaches it in By-Trail.
- Its only other caller is `_auto_refresh_tick` (:5706), gated on
  `manager.auto_refresh_minutes > 0`. That property defaults to `0`
  (:790/:795/:811) and this repo's `aitasks/metadata/board_config.json` has
  no `settings` block at all — so the timer never starts.

Net effect: on a default install there is **no** way to refresh a By-Trail
card status without leaving to In-Flight and back, or restarting the board.

### 3. `r` launches a heavyweight agent instead

`action_refresh_board` (:5777-5788) diverts to
`_launch_trail(["--refresh", handle], ...)` (:7145), which resolves
`aitask_codeagent.sh invoke trail` and opens an `AgentCommandScreen`. The
model class for `trail` is `claudecode/opus5`
(`aitasks/metadata/codeagent_config.json:19`).

The `/aitask-trail --refresh` flow itself (`SKILL.md.j2:242-327`) is cheap on
the deterministic side (~6 sub-second helper calls) but expensive on the model
side: it re-reads every drifted member's task and plan file, re-reasons the
ordering, and **re-authors the entire trail JSON with Write** — 132 KB on this
trail — behind at least two mandatory `AskUserQuestion` confirmations. That is
minutes of wall-clock for what is often a one-field status change.

### 4. The instant deterministic path already exists and is already wired

`./.aitask-scripts/aitask_trail_gather.sh drift --trail art:<handle>` is
read-only, LLM-free and runs in ~0.3s. Run live during exploration it already
produced exactly the missing signal:

```
STALE
DRIFT:plan_changed|aitasks#1264|plan appeared: aitasks:aiplans/p1264_...md
DRIFT:status_changed|aitasks#1264|status 'Ready' -> 'Implementing'
DIGEST:b780d65988f4bf72
```

The board already calls it (`_start_trail_drift` :7094, `run_trail_drift`
:727). The gaps are in how the result is used:

- Drift reasons are **per-task** (`code|task_ref|detail`) yet are projected
  nowhere near the owning card — only into the window subtitle
  (`_refresh_subtitle` :5725, `(⚠ stale: N)`) and the `TrailDetailScreen`
  "Drift reasons" list (:2276-2280).
- It fires only on view entry / trail activation. There is no on-demand
  re-run key.
- After the `r` agent writes a new artifact version, `on_trail_result`
  (:7180) calls only `refresh_board()` — it neither reloads `_trail_doc` nor
  re-runs the drift check, so both the cached document and the stale verdict
  survive until the trail is re-picked through the `s` selector.

### 5. Footer labels lie, and Commit All is unscoped

Footer text comes from static `KanbanApp.BINDINGS` description strings
(:5410-5468); Textual's `Footer` renders them verbatim and the board has no
dynamic relabeling mechanism. In By-Trail the footer therefore reads
`r Refresh` and `s Sync` for actions that launch an agent and open a trail
picker respectively. Meanwhile every card prints the literal hint
`[enter details] [r refresh] [s select]` (:1873) — so `s` carries two
contradictory labels on screen simultaneously, and neither `r` nor `s` is
actually card-scoped despite the hint appearing per card.

`check_action` (:5495-5637) is otherwise thorough about hiding inapplicable
actions in `bytrail` (`toggle_children` :5578, `work_report` :5597,
`move_task_*` :5615, `move_col_*`/`toggle_column_collapsed` :5621,
`trail_task` :5628, `sort_topic` :5635). It has **no** `bytrail` case for
`commit_all`, `sync_remote` or `refresh_board`.

Consequence for `C` Commit All: it is gated only on
`get_modified_tasks()` being non-empty (:5571-5573), and that scans every
entry in `task_datas` + `child_task_datas` repo-wide (:1236-1245). Pressing
`C` in By-Trail commits modified task files that are not trail members.

### 6. `ait sync` is unreachable from By-Trail

`action_sync_remote` (:7251-7264) returns at the `bytrail` branch (:7258-7262)
**before** `_run_sync` is ever called. This is a functional hole, not only a
labelling one: task data lives on the `aitask-data` branch, so a status changed
by a remote agent or another machine only reaches this checkout through a sync.
And even if sync did run, gap 1 means the cards would still not move.

## Acceptance criteria

1. From within By-Trail with an active trail, a single keypress performs the
   fast local recompute — `load_tasks()` + re-project the cached trail
   document — with no subprocess and no agent launch, and the card for a task
   whose frontmatter status changed on disk updates immediately.
2. The same fast path (or a companion key) re-runs
   `aitask_trail_gather.sh drift` on demand and updates the freshness banner,
   without touching the artifact.
3. Per-task drift reasons are visible on the owning card (the gatherer already
   emits `code|task_ref|detail`), not only in the subtitle and detail modal.
   Ghost cards must be handled — a drift reason can name an archived or
   cross-repo member.
4. Launching the agent refresh remains available on its own clearly-labelled
   key, distinct from the local refresh.
5. After the agent refresh completes and the artifact version moves, the view
   picks up the new document and re-runs drift without requiring the user to
   re-pick the trail through the `s` selector.
6. Footer labels shown in By-Trail describe what the keys actually do there,
   and the per-card hint line agrees with the footer for every key it names.
   Decide and implement one mechanism (per-view binding descriptions, a
   By-Trail-specific footer, or removing the misleading per-card hint).
7. `C` Commit All is either hidden in By-Trail via `check_action` or scoped to
   the trail's member tasks. Document which, and why, in the code.
8. `ait sync` is reachable from By-Trail on some key, and a successful sync is
   followed by the local recompute so the cards reflect what was pulled.
9. Tests extend `tests/test_board_bytrail_view.py`, which already pins the
   split (`test_auto_refresh_tick_never_launches_in_bytrail` :471-495,
   `test_refresh_launch_args` :585-607) and carries a read-only negative
   control asserting only `drift`/`get`/`versions` verbs are ever spawned.
   New tests must include a negative control proving the local refresh key
   spawns no agent, and render-level assertions (`widget.render().plain`) for
   the per-card drift marker and the footer labels.

## Key files

- `.aitask-scripts/board/aitask_board.py` — `TrailTaskCard.compose` (:1845),
  `TrailGhostCard` (:1885), `build_trail_lanes` (:527), `KanbanApp.BINDINGS`
  (:5410), `check_action` (:5495), `_refresh_board_data` (:5765),
  `action_refresh_board` (:5777), `refresh_board` (:5790),
  `_refresh_subtitle` (:5725), `_set_base_filter` (:6205),
  `_activate_trail` (:7076), `_start_trail_drift` (:7094),
  `_launch_trail` (:7145), `action_sync_remote` (:7251),
  `action_commit_all` (:7956), `TaskManager.get_modified_tasks` (:1236),
  `TrailDetailScreen` (:2203), `_trail_stored_freshness` (:2115)
- `.aitask-scripts/lib/trail_gather.py` — drift codes and the
  `code|task_ref|detail` protocol
- `tests/test_board_bytrail_view.py`

## Secondary finding (decide in planning: fix here or split out)

`_trail_stored_freshness` (:2115) renders the trail-selection modal's badge
from the **persisted** `doc["freshness"]["state"]`. On the live artifact that
field says `"current"` with an empty `drift_reasons` list while a live drift
run reports `STALE` — because `freshness` records what was true at write time.
The selection modal therefore shows a green badge for a demonstrably stale
trail. Fixing it means either running drift per discovered trail (N subprocess
calls at ~0.3s each on the discovery path) or relabelling the badge as
"as recorded". Cheap to relabel, so it may belong here; a per-trail live check
may not.

## Coordination

`t1210_5` (trail move-to-column commands) adds `m`/`M` bindings plus new
`bytrail` cases in the same `check_action` function and the same BINDINGS
list. Whichever lands second must rebase onto the other's footer/gating
changes. Neither blocks the other, but do not develop them in parallel on the
same region without checking.
