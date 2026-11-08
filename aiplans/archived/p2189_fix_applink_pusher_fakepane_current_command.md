---
Task: t2189_fix_applink_pusher_fakepane_current_command.md
Base branch: main
Output branch: main
---

# t2189 — Give the applink pusher test's `FakePane` the fields `capture_pane_async` reads

## Context

`tests/test_applink_pusher.sh` dies at its embedded-Python line 812 with
`AttributeError: 'FakePane' object has no attribute 'current_command'`. The case
that hits it is the concern-1 guard, which seeds a real `TmuxMonitor`'s
`_pane_cache` with a hand-built `FakePane` and calls `capture_pane_async`. Since
t1467, `TmuxMonitor.capture_pane_async`
(`.aitask-scripts/monitor/monitor_core.py:3500`) calls
`agent_key_from_pane(pane.current_command, pane.pane_pid, pane.pane_id)`, and the
fixture never gained those two fields. The script exits 1 after 98 `ok` checks,
so every later check silently never runs.

Reproduced at the start of this session: the script exits 1 with the same
traceback.

## Change

One file: `tests/test_applink_pusher.sh`, class `FakePane` (around line 53).
After `self.category = FakeCategory()`, add:

```python
        # Fields the real TmuxPaneInfo carries and capture_pane_async reads
        # (agent_key_from_pane, t1467). "claude" resolves on rung 1, and the
        # falsy pid keeps the pid rungs (pgrep/ps) from ever running in a test.
        self.current_command = "claude"
        self.pane_pid = 0
```

Why these values:
- `agent_key_from_pane` (`.aitask-scripts/lib/agent_keys.py:173`) returns from
  rung 1 (`agent_key_from_command`) when the command names an agent. It returns
  `""` before any subprocess call when `pane_pid` is falsy. Either way the test
  never starts a real `pgrep`/`ps`, so it stays deterministic.
- `classify_content` only applies prompt patterns when
  `category == PaneCategory.AGENT`. The fixture's `FakeCategory` isn't a
  `PaneCategory`, so the agent key does not change any classification. The fix
  only stops the crash; it does not change what the checks measure.

Rejected alternative: building the fixture from a real `TmuxPaneInfo`. That
would change `category` semantics for the roughly 40 other `FakePane` uses
(the pusher reads `category.value`), which widens the scope beyond the defect.

Probe already run (scratch mirror copy with this exact edit): exit 0,
`ALL PASSED (137 checks)`, against 98 before the crash. So the 39
previously-skipped checks pass and need no further fixes.

## Verification

1. `bash tests/test_applink_pusher.sh; echo "EXIT=$?"` → last line
   `ALL PASSED (137 checks)`, `EXIT=0`.
2. Confirm the previously-crashing pair now runs:
   `bash tests/test_applink_pusher.sh 2>&1 | grep 'capture_pane_async (finalizing)'`
   prints one `ok -` line.
3. Run the sibling applink shell tests as a regression sweep (`tests/test_applink_*.sh`)
   and compare against their current status.

## Step 9 (Post-Implementation)

Commit `tests/test_applink_pusher.sh` alone (path-scoped) as
`bug: Give the applink pusher test's FakePane current_command/pane_pid (t2189)`,
then archive per Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Added `current_command = "claude"` and `pane_pid = 0` (with a
  comment naming the reader and why the values are safe) to `FakePane.__init__` in
  `tests/test_applink_pusher.sh`, exactly as planned. The script now runs to
  `ALL PASSED (137 checks)`, exit 0 (98 checks before the crash). The 39 checks that
  never ran before all passed and needed no further fixes; the
  `capture_pane_async (finalizing) DOES record _last_content (control)` check runs and
  passes.
- **Deviations from plan:** None.
- **Issues encountered:** None in the target file. The sibling sweep
  (`tests/test_applink_*.sh`, 14 other scripts): 13 exit 0 and
  `test_applink_devices.sh` exits 1 on a separate, pre-existing fixture drift (see the
  next bullet). That test file and `applink_app.py` are both unmodified against HEAD,
  and this change cannot reach it.
- **Key decisions:** Kept the hand-written fake instead of building it from a real
  `TmuxPaneInfo`. A real `category` would change what the ~40 other `FakePane` uses
  measure (the pusher reads `category.value`). The falsy `pane_pid` means
  `agent_key_from_pane` never starts `pgrep`/`ps`, so the test stays deterministic.
- **Upstream defects identified:**
  - `tests/test_applink_devices.sh:41 — FakeServer (embedded-script traceback line 63) lacks a tunnel attribute, so the devices-screen mount crashes in applink_app.py:491 (_refresh reads server.tunnel.status_line(), added by t1061_3 0c0111627) and the script exits 1`
