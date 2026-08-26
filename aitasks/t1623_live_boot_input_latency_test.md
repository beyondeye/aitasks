---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [aitask_monitormini, tui, tmux, performance]
gates: [risk_evaluated]
anchor: 1598
followup_kind: risk_mitigation
created_at: 2026-08-26 08:03
updated_at: 2026-08-26 08:03
boardcol: now
boardidx: 11334
---

## Origin

Risk-mitigation ("after") follow-up for t1598, created at Step 8d after implementation landed.

## Risk addressed

Goal-achievement risk from t1598's plan, verbatim:

> T2 proves the *pump* property with a synthetic stall; it does not prove a real
> boot is fast. · severity: low · → mitigation: live_boot_input_latency_test

t1598's regression test (`tests/test_minimonitor_startup_input_latency.py`)
stalls the first refresh on an `asyncio.Event`, which leaves the event loop
completely free. That is deliberate and it is what makes the test deterministic
and fast — it isolates exactly the structural property (does the first refresh
occupy the App message pump?) that a loop-lag probe provably cannot see. But it
boots no tmux server, spawns no subprocess, and therefore says nothing about
whether a real `ait minimonitor` boot is actually responsive.

## Goal

A live boot test: minimonitor booted in a real tmux pane against a deliberately
wedged, **isolated** marks lock, asserting a keypress takes visible effect under
a wall-clock budget.

Concrete requirements, carried over from t1598's plan so they are not
re-derived:

- **Isolate the lock, never the user's.** `AITASKS_AGENT_MARKS_FILE`
  (`aitask_agent_marks.sh:47`) redirects the store, and `MARKS_LOCK_DIR` at
  `:51` is derived from it, so the wedge lands in the fixture and not in
  `~/.config/aitasks/`.
- **`dead_pid_fixture` is the WRONG fixture for wedging.** A dead holder is now
  reclaimed on sight (t1598's Protocol G), so it would not stall at all. Use a
  live `sleep 120 &` holder — the shape `tests/lib/proc_fixtures.sh:23-26`
  explicitly sanctions. `dead_pid_fixture` is the right fixture for the
  *negative control* ("a stale lock must NOT stall the boot").
- **Isolate tmux** via `tests/lib/tmux_isolation.sh` `require_isolated_tmux`,
  which pins `AITASKS_TMUX_SOCKET=""` and redirects `TMUX_TMPDIR` so the test
  can reach neither the user's personal default server nor the dedicated `ait`
  server.
- **Synthetic project** = a copy of `ait` beside a `.aitask-scripts` **symlink**
  (a `cp -r` snapshot silently runs stale code after the next edit — see
  `tests/test_board_startup_focus_live.py:186`).
- **Pass `AITASKS_TMUX_SOCKET` as an `env` PREFIX** on the send-keys command,
  not via `tmux set-environment`: the session environment is applied to panes
  tmux spawns itself, and the pane's shell is already running
  (`tests/test_codebrowser_startup_focus_live.py:243-251`).
- **Serial carve-out is a coordinated TWO-FILE edit**, enforced by
  `tests/test_serial_carveout_doc_drift.sh`: add the module to
  `SERIAL_CARVE_OUT` in `tests/run_all_python_tests.sh` **and** to the
  `serial-carve-out:begin/:end` marker block in `CLAUDE.md`, in the same commit,
  or that guard fails. Budget must FAIL rather than skip, matching the three
  existing live tests.

## Why this was deferred rather than done in t1598

t1598's synthetic test fails deterministically on exactly the structural defect,
in under a second, with no tmux server — so it is the better *regression* guard.
The live variant costs a 45s serial budget and a permanent two-file coupling
forever after, and buys belt-and-braces evidence rather than a sharper signal.
That trade is worth making deliberately, in its own task, rather than bolted on.
