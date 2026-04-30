---
Task: t719_1_control_client_module.md
Parent Task: aitasks/t719_monitor_tmux_control_mode_refactor.md
Sibling Tasks: aitasks/t719/t719_2_hot_path_integration.md, aitasks/t719/t719_3_adaptive_polling.md, aitasks/t719/t719_4_pipe_pane_push.md
Archived Sibling Plans: aiplans/archived/p719/p719_*_*.md
Worktree: aiwork/t719_1_control_client_module
Branch: aitask/t719_1_control_client_module
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 10:48
---

# Plan — t719_1: TmuxControlClient module

## Goal

Ship `.aitask-scripts/monitor/tmux_control.py` as a standalone, well-tested
module providing `TmuxControlClient`. No changes to `tmux_monitor.py` or
the apps in this child — pure addition. Subsequent siblings (`t719_2`
integration onwards) build on it.

## Files to add

- `.aitask-scripts/monitor/tmux_control.py` (~250–320 LOC)
- `tests/test_tmux_control.sh` (~150 LOC)

## Step 1 — Skeleton + types

```python
# .aitask-scripts/monitor/tmux_control.py
from __future__ import annotations

import asyncio
import collections
import contextlib
import re
from typing import Optional

_HEAD_RE = re.compile(r"^%(begin|end|error)\s+\d+\s+(\d+)\s+\d+\s*$")
_EXIT_RE = re.compile(r"^%exit(?:\s+.*)?$")

class TmuxControlClient:
    def __init__(self, session: str, command_timeout: float = 5.0):
        self.session = session
        self.command_timeout = command_timeout
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._pending: collections.deque[asyncio.Future] = collections.deque()
        self._capturing: Optional[tuple[int, list[str]]] = None  # (cmd_id, buffer)
        self._write_lock = asyncio.Lock()
        self._alive = False

    @property
    def is_alive(self) -> bool:
        return self._alive
```

## Step 2 — start()

```python
async def start(self) -> bool:
    try:
        self._proc = await asyncio.create_subprocess_exec(
            "tmux", "-C", "attach", "-t", self.session,
            "-f", "no-output,ignore-size",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=4 * 1024 * 1024,
        )
    except (FileNotFoundError, OSError):
        return False
    # tmux -C emits a DCS prefix and possibly some startup async events
    # before the first command — the reader handles that.
    self._alive = True
    self._reader_task = asyncio.create_task(self._reader_loop())
    return True
```

## Step 3 — Reader loop / state machine

```python
async def _reader_loop(self) -> None:
    assert self._proc is not None and self._proc.stdout is not None
    try:
        while True:
            line_bytes = await self._proc.stdout.readline()
            if not line_bytes:
                break  # EOF
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")

            if self._capturing is not None:
                cmd_id, buf = self._capturing
                m = _HEAD_RE.match(line)
                if m and m.group(1) in ("end", "error") and int(m.group(2)) == cmd_id:
                    rc = 0 if m.group(1) == "end" else 1
                    self._capturing = None
                    self._resolve_next((rc, "\n".join(buf) + ("\n" if buf else "")))
                else:
                    buf.append(line)
                continue

            # Idle — look for %begin or async events
            m = _HEAD_RE.match(line)
            if m and m.group(1) == "begin":
                self._capturing = (int(m.group(2)), [])
            elif _EXIT_RE.match(line):
                break  # treat as EOF
            # else: any other %-line is async, discard
    except (asyncio.CancelledError, ConnectionResetError, OSError):
        pass
    finally:
        self._teardown_pending()
```

`_resolve_next` and `_teardown_pending` resolve the leftmost queued future
(and any in-flight capture buffer) with `(-1, "")` on failure paths.

```python
def _resolve_next(self, result: tuple[int, str]) -> None:
    if not self._pending:
        return  # spurious response, ignore
    fut = self._pending.popleft()
    if not fut.done():
        fut.set_result(result)

def _teardown_pending(self) -> None:
    self._alive = False
    self._capturing = None
    while self._pending:
        fut = self._pending.popleft()
        if not fut.done():
            fut.set_result((-1, ""))
```

## Step 4 — request()

```python
def _quote_arg(self, arg: str) -> str:
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'

async def request(self, args: list[str], timeout: float | None = None) -> tuple[int, str]:
    if not self._alive or self._proc is None or self._proc.stdin is None:
        return (-1, "")
    cmd_line = " ".join(self._quote_arg(a) for a in args) + "\n"
    fut: asyncio.Future = asyncio.get_running_loop().create_future()

    async with self._write_lock:
        if not self._alive:
            return (-1, "")
        self._pending.append(fut)
        try:
            self._proc.stdin.write(cmd_line.encode("utf-8"))
            await self._proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError, OSError):
            self._teardown_pending()
            return (-1, "")

    try:
        return await asyncio.wait_for(fut, timeout=timeout if timeout is not None else self.command_timeout)
    except asyncio.TimeoutError:
        # Mark dead — we can't reliably correlate future responses now.
        self._teardown_pending()
        return (-1, "")
```

## Step 5 — close()

```python
async def close(self) -> None:
    self._alive = False
    if self._proc is None:
        return
    if self._proc.stdin is not None and not self._proc.stdin.is_closing():
        with contextlib.suppress(Exception):
            self._proc.stdin.close()
    try:
        await asyncio.wait_for(self._proc.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            self._proc.kill()
        with contextlib.suppress(Exception):
            await self._proc.wait()
    if self._reader_task is not None and not self._reader_task.done():
        self._reader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self._reader_task
    self._teardown_pending()
```

## Step 6 — `tests/test_tmux_control.sh`

Skeleton (mirrors `tests/test_tmux_exact_session_targeting.sh:86-97`):

```bash
#!/usr/bin/env bash
set -euo pipefail

if ! command -v tmux >/dev/null; then
    echo "SKIP: tmux not available"
    exit 0
fi

TEST_TMUX_DIR=$(mktemp -d)
export TMUX_TMPDIR="$TEST_TMUX_DIR"
unset TMUX
SESSION="ait_test_$$"
trap 'tmux -L default kill-server 2>/dev/null || true; rm -rf "$TEST_TMUX_DIR"' EXIT

tmux new-session -d -s "$SESSION" "tail -f /dev/null"
for i in 1 2 3 4 5; do
    tmux new-window -t "${SESSION}:" -n "agent-${i}" "tail -f /dev/null"
done

PYTHONPATH=.aitask-scripts python3 - <<PYEOF
import asyncio
from monitor.tmux_control import TmuxControlClient

async def main():
    c = TmuxControlClient(session="$SESSION")
    assert await c.start(), "start failed"

    # Case 1: parity smoke
    rc, out = await c.request(["display-message", "-p", "#S"])
    assert rc == 0 and out.strip() == "$SESSION", (rc, out)

    # Case 2: concurrent gather
    results = await asyncio.gather(*[c.request(["display-message", "-p", "tick"]) for _ in range(5)])
    assert all(rc == 0 and out.strip() == "tick" for rc, out in results), results

    # Case 3: error response
    rc, out = await c.request(["list-panes", "-t", "no-such-session"])
    assert rc != 0, (rc, out)
    assert c.is_alive, "client died on bad command"

    await c.close()
    print("OK")

asyncio.run(main())
PYEOF

# Case 4: server-kill recovery
PYTHONPATH=.aitask-scripts python3 - <<PYEOF
import asyncio, subprocess
from monitor.tmux_control import TmuxControlClient

async def main():
    c = TmuxControlClient(session="$SESSION")
    assert await c.start()
    subprocess.run(["tmux", "kill-server"], check=False)
    rc, out = await c.request(["display-message", "-p", "#S"])
    assert rc == -1 and out == "", (rc, out)
    assert not c.is_alive
    await c.close()
    print("OK")

asyncio.run(main())
PYEOF

echo "PASS: test_tmux_control"
```

## Verification

- `bash tests/test_tmux_control.sh` exits 0 on Linux + macOS.
- `shellcheck tests/test_tmux_control.sh` clean.
- Module importable in isolation:
  `PYTHONPATH=.aitask-scripts python3 -c "from monitor.tmux_control import TmuxControlClient"`
- `git diff --stat` shows only the two new files (plus the plan file).
- No new shell helpers added → 5-touchpoint whitelisting checklist does
  not apply. Confirm: `grep -rn "tmux_control" seed/` returns nothing.

## Step 9 — Post-Implementation

Per `task-workflow/SKILL.md` Step 9: `bash tests/test_tmux_control.sh`
in Step 9's `verify_build` (if configured), then archival.

## Notes for sibling tasks

- `request(args, timeout)` returns `(rc, str)` with rc `-1` reserved for
  transport failure. `t719_2`'s `_tmux_async` helper relies on this rc
  contract for fallback.
- `is_alive` is the canonical liveness signal for `t719_2` and `t719_4`.
- The argument-quoting strategy in `_quote_arg` preserves byte-for-byte
  parity with the existing subprocess wire format, including literal tab
  bytes inside format strings — verified by Case 1 in tests.
