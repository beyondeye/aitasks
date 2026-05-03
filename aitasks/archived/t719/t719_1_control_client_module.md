---
priority: high
effort: medium
depends: []
issue_type: performance
status: Done
labels: [performance, monitor, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-30 10:25
updated_at: 2026-05-03 08:33
completed_at: 2026-05-03 08:33
---

## Context

First step of t719 (`tmux -C` control-mode refactor for monitor/minimonitor). Ship a working `tmux -C` client as a standalone, well-tested module. Subsequent siblings (`t719_2` integration, `t719_3` adaptive polling, `t719_4` pipe-pane) build on it. **No changes to `tmux_monitor.py` or the apps in this child** — pure addition.

The parent plan (`aiplans/p719_monitor_tmux_control_mode_refactor.md`) explains the architectural motivation; the design choices below come straight from a Plan-agent design review (logged in the parent plan's "Serialization design note").

## Key Files to Modify

- **NEW** `.aitask-scripts/monitor/tmux_control.py` (~250–320 LOC) — `class TmuxControlClient` with public API:
  - `__init__(session: str, command_timeout: float = 5.0)`
  - `async start() -> bool` (spawns the subprocess, returns False if tmux missing or attach fails)
  - `async request(args: list[str], timeout: float | None = None) -> tuple[int, str]` (mirrors the existing `_run_tmux_async` signature: `(rc, stdout_text)`; rc `-1` means transport failure)
  - `async close() -> None`
  - `is_alive` property
- **NEW** `tests/test_tmux_control.sh` (~150 LOC)

## Reference Files for Patterns

- `.aitask-scripts/monitor/tmux_monitor.py:94-119` — current `_run_tmux_async` signature/error semantics to mirror exactly.
- `tests/test_tmux_exact_session_targeting.sh:86-97` — tmux-fixture test pattern (`mktemp -d`, `TMUX_TMPDIR`, `unset TMUX`, `tmux new-session -d -s …`, trap-based cleanup, skip-if-no-tmux).
- `tests/test_multi_session_monitor.sh:702-705` — multi-session fixture variant.

## Implementation Plan

### 1. Subprocess spawn

```python
asyncio.create_subprocess_exec(
    "tmux", "-C", "attach", "-t", session,
    "-f", "no-output,ignore-size",
    stdin=PIPE, stdout=PIPE, stderr=DEVNULL,
    limit=4 * 1024 * 1024,
)
```

- `-f no-output` is **load-bearing**: without it the control client is flooded with `%output` async events for every byte the panes write. With it, only command-response blocks come back. (tmux man page, CONTROL MODE / CLIENT FLAGS.)
- `-f ignore-size` prevents tmux from resizing user-visible panes to match this control client's default 80×24.
- `limit=4*1024*1024` raises asyncio's StreamReader line buffer above its 64 KiB default — a dense `capture-pane -e` (200 lines × ANSI escapes) can otherwise raise `LimitOverrunError` only under load (classic production-only bug).

### 2. Reader task + state machine

Single long-running `asyncio.Task` reads `proc.stdout` line by line. State:

- **Idle** → on `%begin <epoch> <id> <flags>` → **Capturing(id)** with empty buffer.
- **Capturing** → buffer each line until `%end <epoch> <id> <flags>` → resolve the leftmost pending future with `(0, "".join(buffer))`. On `%error <epoch> <id> <flags>` → resolve with `(1, "".join(buffer))`.
- Any line starting with `%` while **Idle** is treated as an async event and discarded. (tmux man guarantees notifications never appear inside an output block, so we don't need to discriminate inside Capturing.)
- `%exit [reason]` is treated as EOF.

### 3. Request dispatch — FIFO, NOT id map

```python
_pending: collections.deque[asyncio.Future]
_write_lock: asyncio.Lock
```

The `cmd_id` in `%begin` is assigned by the **server**, not the client — we only learn it by reading the response. Per-id demultiplexing buys nothing over FIFO ordering, and a write-lock is required anyway to prevent interleaved bytes on stdin from concurrent `request()` calls. The reader pops from the left on each `%end`/`%error`. The cmd_id is used only as a sanity-check assertion.

### 4. Argument escaping

Each arg wrapped in `"..."` with `\` → `\\` and `"` → `\"`. Pass literal tab bytes (`0x09`) inside format strings — tmux's lexer accepts them inside double quotes, and parity with the existing subprocess wire format is preserved automatically. Do not escape `$`.

### 5. Output decoding

In plain `tmux -C` (NOT `-CC`), the body of a `%begin/%end` block is delivered raw — no octal escaping. (Octal escaping applies only to `%output` async notifications, which `no-output` suppresses.) Step 6's parity test asserts byte-for-byte equality with the subprocess path; if a future tmux release diverges, the decoder lands there, not speculatively here.

### 6. Failure handling

On EOF / `%exit` / broken pipe / `proc.returncode != None`: set `_alive = False`, resolve **both** the in-progress Capturing future *and* every queued future with `(-1, "")`, do not auto-restart. The next caller sees `is_alive == False` and falls back to subprocess (handled in `t719_2`).

### 7. close()

Close stdin (tmux drops the control client on EOF); await `proc.wait()` with a short timeout; cancel reader task. Avoid `kill-client` — it races with stdin close and offers nothing extra.

### 8. Test cases (`tests/test_tmux_control.sh`)

Bash test driver with isolated `TMUX_TMPDIR`, trap cleanup, skip if `tmux` missing. Runs a small Python helper (heredoc into `mktemp …/test.py`) that imports `monitor.tmux_control.TmuxControlClient` via `PYTHONPATH=.aitask-scripts`.

Cases:

1. **Smoke / parity** — `display-message -p "#S"`, `list-panes -F …`, `capture-pane -p`. Compare each result to `subprocess.run(["tmux", ...])` equivalent. Assert byte-for-byte equality.
2. **Concurrent** — Run 5 `capture-pane` requests via `asyncio.gather`; assert all succeed and outputs are correctly demultiplexed (each future receives its own response, no cross-talk). With FIFO dispatch this validates ordering correctness.
3. **Error response** — Issue `list-panes -t nonexistent`; assert `rc != 0`, no exception, `is_alive == True` after.
4. **Server-kill recovery** — `tmux kill-server` while client is alive; assert `is_alive` flips to `False`; assert all in-flight + queued futures resolve with `(-1, "")`; assert next `request()` returns `(-1, "")` without raising.

## Verification Steps

- `bash tests/test_tmux_control.sh` — passes locally on Linux.
- `shellcheck tests/test_tmux_control.sh` — clean.
- Module is importable: `PYTHONPATH=.aitask-scripts python3 -c "from monitor.tmux_control import TmuxControlClient; print(TmuxControlClient)"`.
- No new shell helpers under `.aitask-scripts/` were added (just a Python module + a bash test), so the 5-touchpoint whitelisting checklist does not apply. Confirm by `grep -rn "tmux_control" seed/`.
- This child does NOT modify `tmux_monitor.py`, `monitor_app.py`, or `minimonitor_app.py` — verify with `git diff --stat` showing only the two new files plus possibly the plan file.
