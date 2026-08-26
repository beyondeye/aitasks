---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tmux, aitask_monitormini, aitask_monitor, tui]
gates: [risk_evaluated]
anchor: 1598
followup_kind: upstream_defect
created_at: 2026-08-26 17:35
updated_at: 2026-08-26 17:35
---

## Origin

Spawned from t1622 during Step 8 review. t1622 fixed the same defect class in
`monitor/desync_summary.py:_fetch_async`; this is the shared-gateway instance it
deliberately left alone, and which t1622 then made more reachable.

## Upstream defect

`.aitask-scripts/lib/tmux_exec.py:218` — `TmuxClient.run_async` wraps
`proc.communicate()` in `asyncio.wait_for` and catches **only**
`asyncio.TimeoutError`. `wait_for` cancels the inner `communicate()` and
re-raises `CancelledError` **without touching the child**, so a cancelled
gateway call leaves its `tmux` process running until it exits on its own.

Every async gateway caller is exposed. The concrete path t1622 widened:
`minimonitor_app.py:1405` (`_seed_own_window_info`) dispatches an ambient
`tmux display-message` as a `run_worker` task at mount, and Textual cancels
workers on app exit — so closing minimonitor while that probe is in flight
strands the child. The child is short-lived and self-terminating, which is why
t1622 scoped it out rather than special-casing one call site; the fix belongs in
the gateway, once, for every caller.

Its docstring also claims only "on timeout the child is killed and reaped
before returning" — accurate today, and part of what needs updating.

## Suggested fix

Mirror what t1622 landed in `monitor/desync_summary.py`: extract the kill+reap
into one helper and call it from **both** exits.

```python
    except asyncio.TimeoutError:
        await self._terminate(proc)
        return (-1, "")
    except asyncio.CancelledError:
        # Kill BEFORE the re-raise and never swallow the CancelledError:
        # `kill()` is synchronous, so the signal lands even if the reaping
        # `await` is cancelled in turn.
        await self._terminate(proc)
        raise
```

Check `run_async_via_control` and any other `await`-on-a-child site in the
gateway for the same shape while you are there.

## Verification

The pattern is proven — reuse `tests/test_desync_summary_cache.py`'s
`FetchAsyncChildLifecycleTests`: spawn a stub that writes its pid and blocks,
cancel the task once the pid file appears, then assert `CancelledError`
propagates **and** the pid is gone within a bounded poll. Asserting only on the
return value cannot see this bug — the return path is never reached.

Positive control: drop the new `except` clause; the test must fail on the
surviving child, not on a missing exception.

**Do not signal any pid the test did not create**, and do not spawn a real tmux
server: the gateway's argv can be exercised against a stub binary.
