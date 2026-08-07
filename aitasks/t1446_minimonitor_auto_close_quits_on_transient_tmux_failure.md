---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, tmux, tui]
gates: [risk_evaluated]
created_at: 2026-08-07 10:03
updated_at: 2026-08-07 10:03
---

## Symptom

Every `ait minimonitor` companion pane disappeared while the coding agent it
was sitting next to kept running. Observed across all three tmux sessions
(`aitasks`, `thinking_app`, `thinking_backend`) — no minimonitor pane remained
anywhere except one that predated the event.

## Evidence — the event is dated exactly

systemd emits one scope-teardown line per tmux pane. Eight
`tmux-spawn-*.scope` units closed together at **2026-08-06 21:46:15–16**, all
with an 83–104 MB memory peak (python/Textual sized), and their wall-clock ages
map 1:1 onto the companion spawn times:

| scope age at teardown | companion of |
|---|---|
| 1d 3h 22m | `aitasks:4` agent (started 08-05 18:23) |
| 21h 54m | `aitasks:5` agent (08-05 23:51) |
| 13h 5m | `aitasks:6` agent (08-06 08:40) |
| 9h 49m | `aitasks:7` agent (08-06 11:57) |
| 6h 16m | `aitasks:8` agent (08-06 15:29) |
| 6h 21m | `thinking_back:3` agent (08-06 15:24) |
| 4d 0h 18m | `thinkingapp:2` agent (08-02 21:28) |
| 22h 4m | `thinkingapp:4` lazygit companion (08-05 23:41) |

The machine was stalled at that instant: at-spi logged "Disabling unresponsive
app" at 21:45:21, `qemu-system-x86` SEGV'd at 21:46:17, and a global OOM kill
followed at 21:48:32. **No python process appears among the kernel's OOM
victims** (chromium, java, systemd-coredump only) — the minimonitors exited
*voluntarily*, they were not killed.

## Root cause — a fail-open on an unverifiable signal

1. `.aitask-scripts/lib/tmux_exec.py:172-179` — `TmuxExec.run` returns
   `(-1, "")` on `TimeoutExpired` / `OSError`. The default timeout is 5 s.
2. `.aitask-scripts/monitor/monitor_core.py:1763-1765` —
   `discover_window_panes` collapses **any** `rc != 0` into `[]`. A timed-out
   query and a genuinely empty window become the same value.
3. `.aitask-scripts/monitor/minimonitor_app.py:511-519` — `_check_auto_close`
   reads that `[]` as "no other panes remain in my window" and calls
   `self.exit()`. The only guard is a 5-second grace window after mount
   (`minimonitor_app.py:483`).

A machine-wide stall pushes the 5 s timeout over the edge in every minimonitor
process at once, so they all quit within the same second. The code is original
(t496_2, April) and has no test covering the failure branch.

**Built-in control:** `ait monitor` and `ait board` panes of the same age (and
older) survived the identical stall. `_check_auto_close` exists only in
minimonitor — it is the sole discriminator between the processes that died and
the ones that lived.

**Why one survived:** `aitasks:2`'s companion (`%187`) is a race artifact, not
immunity. When `capture_all_async` fails the tick returns early
(`minimonitor_app.py:456-458`) *before* reaching the auto-close check, so a
process whose capture timed out first skips the check that killed its siblings.

## Acceptance criteria

- [ ] The auto-close decision is made only on a **positively observed** empty
      window. An unverifiable observation (tmux error, timeout, transport
      failure) must never be treated as "empty" and must never exit the app.
      Prefer a signature that cannot conflate the two — e.g. returning
      `list | None`, or a `(ok, panes)` pair — rather than a sentinel the
      caller has to remember to check.
- [ ] Every other caller of `discover_window_panes` is audited for the same
      conflation and updated or explicitly documented as safe.
- [ ] Regression test drives the `rc = -1` path through the **real**
      `MiniMonitorApp._check_auto_close` and asserts the app does **not** exit;
      a companion test asserts it *does* exit on a genuine empty-window
      observation. A negative control (revert the fix → the first test fails)
      is named in the plan.
- [ ] Consider whether repeated consecutive failures should still auto-close
      (e.g. N consecutive verified-empty observations) — decide explicitly and
      record the reasoning; do not leave it implicit.

## Out of scope — secondary finding worth its own task

Companion-pane cleanup-hook arming is inconsistent across launch paths:

- `.aitask-scripts/lib/agent_launch_utils.py:1465-1603` —
  `maybe_spawn_minimonitor` spawns the companion but never arms the
  `pane-died` cleanup hook, so board- and codebrowser-launched windows carry a
  companion with no hook (verified live: `aitasks:8` `%384` had a companion,
  no hook).
- `.aitask-scripts/lib/tui_switcher.py:1387` arms it with a **bare**
  `set-hook -p … pane-died` (index 0) — exactly the overwrite hazard that
  `attach_shadow_cleanup_hook` (`agent_launch_utils.py:1390-1445`) was written
  to avoid. A later shadow spawn can claim the slot: `aitasks:7`'s `%375`
  now points at the shadow `%386` rather than at its companion.

Also noted, harmless but dead: the single-instance guards in
`.aitask-scripts/aitask_minimonitor.sh:37` and
`agent_launch_utils.py:1567` test `pane_current_command` for
`minimonitor` / `monitor_app`, but a live minimonitor pane reports `python`,
so neither guard can ever fire.
