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
  - claudecode/opus4_7_1m @ 2026-05-03 08:28
---

# Plan — t719_1: TmuxControlClient module

## Goal

Ship `.aitask-scripts/monitor/tmux_control.py` as a standalone, well-tested
module providing `TmuxControlClient`. No changes to `tmux_monitor.py` or
the apps in this child — pure addition. Subsequent siblings (`t719_2`
integration onwards) build on it.

## Status (verify pass, 2026-05-03)

The module and test were drafted on 2026-04-30 and committed on disk as
untracked files (no progress markers in the plan, so this is the first
verify pass against working code). On verification:

- `PYTHONPATH=.aitask-scripts python3 -c "from monitor.tmux_control import TmuxControlClient"` succeeds.
- `bash tests/test_tmux_control.sh` **fails** at Case 1a:
  `display-message -p "#S"` returns `(0, "")` instead of `(0, "<session>\n")`.
- `shellcheck tests/test_tmux_control.sh` reports SC2030/SC2031 (info)
  on `export TMUX_TMPDIR` inside `(...)` subshells.

Root cause (confirmed by piping the same command sequence into
`tmux -C attach` and reading raw output):

```
%begin <epoch> <id_A> 0   ← implicit attach acknowledgment, flags=0
%end   <epoch> <id_A> 0
%session-changed $0 ait_dbg_22004
%begin <epoch> <id_B> 1   ← actual response to display-message, flags=1
ait_dbg_22004
%end   <epoch> <id_B> 1
```

The current reader treats every `%begin` block as a user response. Race:
the user calls `request()` immediately after `start()`, the reader runs,
sees the implicit attach `%begin/%end` first, pops the user's pending
future and resolves it with the empty attach body. The real
`%begin/%end <id_B> 1` then arrives with `_pending` empty and is
silently dropped.

The original plan's "Reader task + state machine" did not anticipate the
attach-ack block. Verify-mode update: filter blocks by the `flags`
bitmask. tmux's man page (CONTROL MODE, NOTIFICATIONS) documents that
the third field after `%begin`/`%end`/`%error` is a flags mask whose
bit `1` means "command was issued via the control client". Server-emitted
blocks (attach ack, `%session-changed`-driven introspection, etc.) have
flags=0. Only flags-bit-1 blocks should be delivered to pending futures.

## Files to add

- `.aitask-scripts/monitor/tmux_control.py` (~250–320 LOC) — present, needs
  reader fix described in Step 3 below.
- `tests/test_tmux_control.sh` (~150 LOC) — present, no logic changes
  needed; add a `# shellcheck disable=SC2030,SC2031` directive next to
  each subshell-scoped `export TMUX_TMPDIR` so the lint is clean.

## Step 1 — Skeleton + types

**Implemented as planned.** No verify-mode changes.

```python
# .aitask-scripts/monitor/tmux_control.py
from __future__ import annotations

import asyncio
import collections
import contextlib
import re
from typing import Optional

# Updated regex (verify pass): capture flags as group 3 so we can filter
# server-emitted blocks (flags bit 1 = "command from control client").
_HEAD_RE = re.compile(r"^%(begin|end|error)\s+\d+\s+(\d+)\s+(\d+)\s*$")
_EXIT_RE = re.compile(r"^%exit(?:\s+.*)?$")

class TmuxControlClient:
    def __init__(self, session: str, command_timeout: float = 5.0):
        self.session = session
        self.command_timeout = command_timeout
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._pending: "collections.deque[asyncio.Future]" = collections.deque()
        # Capturing buffer carries (cmd_id, buf, deliver). deliver=False
        # for server-emitted blocks (flags bit 1 unset) — buf is dropped
        # at %end/%error without resolving any pending future.
        self._capturing: Optional[tuple[int, list[str], bool]] = None
        self._write_lock = asyncio.Lock()
        self._alive = False
```

## Step 2 — start()

**Implemented as planned.** No verify-mode changes.

The 50 ms `await asyncio.sleep(0.05)` before checking `returncode` stays
— it gives `tmux -C attach` a beat to fail synchronously when the
target session does not exist (the process exits with non-zero rc in
that case).

## Step 3 — Reader loop / state machine **(FIX)**

Verify-mode replacement. The two changes:

1. Capture flags in `_HEAD_RE` (already shown in Step 1).
2. On `%begin`, compute `deliver = (flags & 1) != 0` and store it in
   the `_capturing` tuple. On `%end`/`%error`, resolve the pending
   future only when `deliver` is True; otherwise drop the buffer.

```python
async def _reader_loop(self) -> None:
    assert self._proc is not None and self._proc.stdout is not None
    try:
        while True:
            line_bytes = await self._proc.stdout.readline()
            if not line_bytes:
                break  # EOF
            line = line_bytes.decode("utf-8", errors="replace")
            if line.endswith("\n"):
                line = line[:-1]

            if self._capturing is not None:
                cmd_id, buf, deliver = self._capturing
                m = _HEAD_RE.match(line)
                if m and m.group(1) in ("end", "error") and int(m.group(2)) == cmd_id:
                    rc = 0 if m.group(1) == "end" else 1
                    body = "\n".join(buf) + ("\n" if buf else "")
                    self._capturing = None
                    if deliver:
                        self._resolve_next((rc, body))
                    # else: server-emitted block (e.g. attach ack) — drop.
                else:
                    buf.append(line)
                continue

            m = _HEAD_RE.match(line)
            if m and m.group(1) == "begin":
                cmd_id = int(m.group(2))
                flags = int(m.group(3))
                deliver = (flags & 1) != 0
                self._capturing = (cmd_id, [], deliver)
            elif _EXIT_RE.match(line):
                break  # tmux server is going away
            # Any other %-line outside a Capturing block is an async
            # event (e.g., %session-changed, %sessions-changed). Discard.
    except (asyncio.CancelledError, ConnectionResetError, OSError):
        pass
    finally:
        self._teardown_pending()
```

`_resolve_next` and `_teardown_pending` are unchanged from the existing
implementation. The leftmost-pending-future contract is preserved
because we only call `_resolve_next` for client-issued blocks.

## Step 4 — request()

**Implemented as planned.** No verify-mode changes.

Note: with the Step 3 fix, the user's first `request()` after `start()`
is no longer at risk of receiving the empty attach-ack body, regardless
of reader-task scheduling order.

## Step 5 — close()

**Implemented as planned.** No verify-mode changes.

## Step 6 — `tests/test_tmux_control.sh`

**Implemented as planned, with one cosmetic addition to satisfy
`shellcheck`.**

The script intentionally uses `(...)` subshells for case isolation, so
each case can `export TMUX_TMPDIR=...` and `unset TMUX` without leaking
into siblings. Shellcheck flags this with SC2030/SC2031 (info) — both
are false positives for this pattern. Suppress per-line:

```bash
(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030  # subshell-scoped export is intentional
    export TMUX_TMPDIR="$F1"
    unset TMUX
    ...
)
```

And similarly for the `F2` block. No other test changes needed.

Cases (unchanged from original plan, all already in the file):

1. **Smoke / parity** — `display-message -p "#S"`, `list-panes -F …`
   (with a tab-bearing format), `capture-pane -p`. Each result compared
   byte-for-byte to the equivalent `subprocess.run(["tmux", ...])`.
2. **Concurrent** — `asyncio.gather` of 5 `display-message` calls;
   assert FIFO demultiplexing returns each its own response, no
   cross-talk.
3. **Error response** — `list-panes -t no_such_session_xyz`; assert
   `rc != 0`, no exception, `is_alive` still True.
4. **Server-kill recovery** — `tmux kill-server`; assert `is_alive`
   flips False and subsequent `request()` returns `(-1, "")` cleanly.

## Verification

- `bash tests/test_tmux_control.sh` exits 0 on Linux (re-run after the
  Step 3 fix lands; Case 1a is the canary).
- `shellcheck tests/test_tmux_control.sh` clean (SC2030/SC2031
  suppressed).
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
- **Server vs client block flag** (verify pass): The reader filters
  blocks where the `%begin <epoch> <id> <flags>` flags bitmask has bit
  `1` cleared. Sibling tasks adding new commands need not worry about
  this — server-emitted notifications outside `%begin/%end` blocks
  (e.g., `%session-changed`) are still handled by the
  `_capturing is None` branch's "discard async events" comment.
