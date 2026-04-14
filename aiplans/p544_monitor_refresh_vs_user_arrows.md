---
Task: aitasks/t544_monitor_refresh_vs_user_arrows.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan for t544 — monitor TUI: async tmux refresh

## Context

In `ait monitor` the user presses up/down in the left pane (agent list) to
switch the focused agent. An auto-refresh timer fires every
`tmux.monitor.refresh_seconds` (default 3 s). On every tick the agent list
becomes unresponsive to up/down for ~0.5–2 s and keypresses appear dropped.

## Root cause

Textual's event loop is single-threaded and cooperative.
`MonitorApp._refresh_data()` at `.aitask-scripts/monitor/monitor_app.py:469`
is declared `async` but never awaits anything. Line 477 calls
`self._monitor.capture_all()`, which in `.aitask-scripts/monitor/tmux_monitor.py:240`
runs `subprocess.run(["tmux", "list-panes", …])` (line 116) followed by one
`subprocess.run(["tmux", "capture-pane", …])` per pane (line 211). Each
`subprocess.run` blocks the single event loop synchronously. With ~10
agent panes at `capture_lines=200`, a tick blocks for ~0.5–2 s. Keypresses
queued during the block are not dispatched until the coroutine returns.

The same pattern exists in `_fast_preview_refresh()` at
`monitor_app.py:524` (via `capture_pane()` at `tmux_monitor.py:206`) and in
the minimonitor at `.aitask-scripts/monitor/minimonitor_app.py:201`.

## Approach — Option B: async subprocess refactor

Rewrite the tmux subprocess layer using `asyncio.create_subprocess_exec` so
the event loop can yield while tmux calls are in flight. This makes
`_refresh_data` a real coroutine that awaits, keeping the UI responsive at
all times. As a bonus, per-pane captures in `capture_all_async` can run
concurrently with `asyncio.gather`, reducing total tick latency.

Keep the existing sync methods (`discover_panes`, `capture_pane`,
`capture_all`) in place — `tmux_monitor.py:11` (the `__main__` test block)
uses them and they are easy to leave as thin shims around shared parsing
helpers. No sync call sites outside `monitor_app.py` / `minimonitor_app.py`
need to change.

## Files to modify

1. `.aitask-scripts/monitor/tmux_monitor.py` — add async variants and shared parsing helpers.
2. `.aitask-scripts/monitor/monitor_app.py` — await async variants in `_refresh_data` and `_fast_preview_refresh`.
3. `.aitask-scripts/monitor/minimonitor_app.py` — await `capture_all_async` in `_refresh_data`.

## Implementation steps

### Step 1 — `tmux_monitor.py`: add async subprocess runner and parsing helpers

At the top of the file, alongside existing `import subprocess`:

```python
import asyncio
import contextlib
```

Add a module-level async helper (near the other module helpers, before
`class TmuxMonitor`):

```python
async def _run_tmux_async(args: list[str], timeout: float = 5.0) -> tuple[int, str]:
    """Run `tmux <args>` asynchronously. Returns (returncode, stdout_text).

    Returns (-1, "") on FileNotFoundError / OSError / timeout, matching the
    error semantics of the synchronous helpers (they just return empty on
    failure).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "tmux", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError):
        return (-1, "")
    try:
        stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        return (-1, "")
    return (proc.returncode or 0, stdout_bytes.decode("utf-8", errors="replace"))
```

Refactor the existing sync methods to extract pure parsing helpers — this
lets the new async methods share all the post-subprocess logic (cache
updates, idle-time tracking, filter rules):

- Extract `_parse_list_panes(self, stdout: str) -> list[TmuxPaneInfo]`
  from the body of `discover_panes()` starting at current line 125 (the
  `for line in result.stdout.strip().splitlines()` loop through line 157).
  This helper applies the companion-pane filter and populates
  `self._pane_cache`.
- Extract `_finalize_capture(self, pane: TmuxPaneInfo, content: str) -> PaneSnapshot`
  from the body of `capture_pane()` starting at current line 220
  (`now = time.monotonic()` through the `return PaneSnapshot(...)` at line 238).
  This helper mutates `self._last_content` / `self._last_change_time` and
  builds the snapshot.

Rewrite `discover_panes()` and `capture_pane()` as thin wrappers that call
`_parse_list_panes` / `_finalize_capture` after running the subprocess via
the existing sync `subprocess.run` path. The observable behavior of both
functions must stay byte-for-byte identical — the only change is that the
bodies after the subprocess call now live in the shared helpers.

Add the async variants (placed immediately after their sync counterparts):

```python
async def discover_panes_async(self) -> list[TmuxPaneInfo]:
    fmt = "\t".join([
        "#{window_index}", "#{window_name}", "#{pane_index}",
        "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
        "#{pane_width}", "#{pane_height}",
    ])
    rc, stdout = await _run_tmux_async(
        ["list-panes", "-s", "-t", self.session, "-F", fmt],
    )
    if rc != 0:
        return []
    return self._parse_list_panes(stdout)

async def capture_pane_async(self, pane_id: str) -> PaneSnapshot | None:
    pane = self._pane_cache.get(pane_id)
    if pane is None:
        return None
    rc, content = await _run_tmux_async(
        ["capture-pane", "-p", "-e", "-t", pane_id,
         "-S", f"-{self.capture_lines}"],
    )
    if rc != 0:
        return None
    return self._finalize_capture(pane, content)

async def capture_all_async(self) -> dict[str, PaneSnapshot]:
    panes = await self.discover_panes_async()
    current_ids = {p.pane_id for p in panes}

    # Clean stale entries (same logic as sync capture_all)
    stale = [pid for pid in self._last_content if pid not in current_ids]
    for pid in stale:
        del self._last_content[pid]
        self._last_change_time.pop(pid, None)
        self._pane_cache.pop(pid, None)

    # Capture all panes concurrently; skip any that error out.
    results = await asyncio.gather(
        *(self.capture_pane_async(p.pane_id) for p in panes),
        return_exceptions=True,
    )
    snapshots: dict[str, PaneSnapshot] = {}
    for pane, snap in zip(panes, results):
        if isinstance(snap, PaneSnapshot):
            snapshots[pane.pane_id] = snap
    return snapshots
```

Notes:
- Concurrent `gather` is safe: each `capture_pane_async` call touches a
  different `pane_id` key in `_last_content` / `_last_change_time`, and
  the event loop serializes the dict mutations anyway (single thread).
- `return_exceptions=True` matches the current sync behavior of silently
  dropping panes that fail to capture (sync version returns `None` and
  skips the entry).

### Step 2 — `monitor_app.py`: await the async variants

Line 477, inside `async def _refresh_data`:

```python
# Before
self._snapshots = self._monitor.capture_all()
# After
self._snapshots = await self._monitor.capture_all_async()
```

Line 528, inside `async def _fast_preview_refresh`:

```python
# Before
snap = self._monitor.capture_pane(self._focused_pane_id)
# After
snap = await self._monitor.capture_pane_async(self._focused_pane_id)
```

No other changes in `monitor_app.py` — both functions are already `async`
and the surrounding logic (cache cleanup, focus restore, DOM rebuild) is
unchanged.

Leave `_consume_focus_request()` at line 549 untouched. It runs a single
fast `tmux show-environment` call, and now that the big captures yield,
its occasional ~5 ms block is not user-visible.

### Step 3 — `minimonitor_app.py`: await `capture_all_async`

Line 201, inside `async def _refresh_data`:

```python
# Before
self._snapshots = self._monitor.capture_all()
# After
self._snapshots = await self._monitor.capture_all_async()
```

No other changes — this method already awaits `_rebuild_pane_list()`.

## Verification

End-to-end manual test (golden path):

1. Ensure there is a tmux session `aitasks` with several agent windows. If
   none are running, start any ~3–5 dummy shells in windows named
   `agent-t1`, `agent-t2`, … to trigger the companion filter path.
2. Run `ait monitor` in another pane.
3. While the status bar updates, hold down `↓` (and `↑`) rapidly. The
   selection cursor must follow the keypresses with no perceptible lag,
   including across refresh tick boundaries.
4. Tab into the preview zone and type — the preview fast-refresh (0.3 s
   timer) must remain smooth.
5. Open/close windows in the tmux session and confirm the agent list and
   stale-entry cleanup still work (new panes appear, closed panes vanish).

Regression test for minimonitor:

1. Inside a tmux agent window, launch the minimonitor companion pane (the
   normal way it is spawned — via the aitask_monitor launcher).
2. Confirm the minimonitor still shows the agent list, auto-selects the
   right card, and auto-closes when its window has no other panes.

Non-regression for the `tmux_monitor.py` CLI test block (`python3
tmux_monitor.py`): it uses the sync `capture_all()` entry point, which
still exists and now routes through the shared helpers. Run it once to
confirm it prints snapshots as before.

If lint is configured for this repo (`.aitask-scripts/` is shell;
`monitor/*.py` has no dedicated linter in CLAUDE.md), just `python3 -m py_compile`
the three files to catch syntax issues:

```bash
python3 -m py_compile \
    .aitask-scripts/monitor/tmux_monitor.py \
    .aitask-scripts/monitor/monitor_app.py \
    .aitask-scripts/monitor/minimonitor_app.py
```

## Out of scope

- Not touching `send_keys`, `send_enter`, `display-message`, `show-environment`
  or any other small tmux calls. They are sub-10 ms and not the source of
  the freeze. If a future task wants full async coverage it can revisit.
- Not modifying the 3 s refresh interval or adding debounce on arrow
  keys — once the event loop stops blocking, the original responsiveness
  issue is gone and the extra complexity is not justified.

## Step 9 — post-implementation

Follow task-workflow Step 9: review → commit on main (no worktree) with
message `bug: Make monitor TUI tmux refresh async (t544)` → `aitask_archive.sh 544`
→ `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Implemented as planned in all three files.
  - `.aitask-scripts/monitor/tmux_monitor.py`: added `asyncio` + `contextlib` imports,
    module-level `_run_tmux_async()` helper (uses `create_subprocess_exec` +
    `wait_for`), extracted shared helpers `_parse_list_panes()`,
    `_finalize_capture()`, `_capture_args()`, `_clean_stale()`, and added the
    async method trio `discover_panes_async()` / `capture_pane_async()` /
    `capture_all_async()`. `capture_all_async()` dispatches all per-pane
    captures concurrently via `asyncio.gather(..., return_exceptions=True)`.
    Sync methods (`discover_panes`, `capture_pane`, `capture_all`) remain as
    thin wrappers around the shared helpers — byte-for-byte equivalent
    behavior.
  - `.aitask-scripts/monitor/monitor_app.py`: `_refresh_data` now awaits
    `capture_all_async()` (line 477); `_fast_preview_refresh` now awaits
    `capture_pane_async()` (line 528).
  - `.aitask-scripts/monitor/minimonitor_app.py`: `_refresh_data` now awaits
    `capture_all_async()` (line 201).
- **Deviations from plan:** None. Small bonus: added `_capture_args()` /
  `_clean_stale()` helpers so the sync and async capture paths share even
  more code than the plan specified. The planned extractions were
  `_parse_list_panes` and `_finalize_capture`; these two extras fell out
  naturally and keep the sync + async pairs symmetric.
- **Issues encountered:** None during implementation. `py_compile` passed
  first time. A live smoke test (`python3 -c "…asyncio.run(m.capture_all_async())"`)
  returned the same set of 8 pane IDs as the sync `capture_all()` on the
  running `aitasks` tmux session, confirming the async path is behaviorally
  equivalent.
- **Key decisions:** Kept the sync methods in place rather than deleting
  them (the module's public surface includes them; removing would be
  unnecessary churn for this task). Left `_consume_focus_request()`,
  `send_keys`, `send_enter`, `discover_window_panes`, and
  `_update_own_window_info` as sync — they are sub-10 ms tmux calls that
  don't contribute to the freeze and rewriting them is out of scope.
- **Verification performed:** `python3 -m py_compile` on all three files
  passed; `python3 tests/test_git_tui_config.py` (only test that imports
  `tmux_monitor`) still passes; manual smoke test against live tmux
  confirmed sync and async paths return identical pane sets; user
  confirmed responsiveness is good in real `ait monitor` use.
- **Known residual issue (follow-up):** User reported that if an arrow
  key is pressed at exactly the moment a refresh tick fires, the keystroke
  is lost and the selection does not advance. This is a separate
  DOM-rebuild race — `_rebuild_pane_list()` in `monitor_app.py` still
  tears down and remounts all `PaneCard` widgets synchronously on every
  tick, and `call_after_refresh(self._restore_focus, …)` can overwrite an
  in-flight user navigation. Filed as follow-up task
  **t545 — `t545_monitor_arrow_key_lost_on_refresh_race.md`** with
  hypothesis, investigation steps, and four candidate fixes.
