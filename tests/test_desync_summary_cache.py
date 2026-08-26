"""The three readers of `monitor/desync_summary.py` and their blocking contracts (t1622).

The desync probe spawns a fresh Python interpreter. Which reader a call site
picks is therefore a correctness question, and this suite pins the three
contracts with no TUI in the way:

* `get_desync_summary_async` — fetches, off the event loop, sharing the TTL cache;
* `get_desync_summary_cached` — NEVER spawns, ignores the TTL by design;
* `_fetch_async` — reaps its child on BOTH exits: the timeout and a cancellation.

**Why cancellation gets its own test.** `asyncio.wait_for` cancels the inner
`communicate()` and re-raises `CancelledError` *without touching the child*, and
Textual cancels the refresh worker when the app exits. A `_fetch_async` that
catches only `TimeoutError` therefore leaks a live Python interpreter past the
TUI it belonged to — and every state assertion still passes, because the return
path was never reached. Only the child's pid can tell you.

**Child hygiene.** Every subprocess here is a stub script this suite spawned
itself, and the only pid ever signalled is one read back from that stub's own
pid file. Nothing in this file touches tmux.

Positive controls (run by hand; each must FAIL this suite):

| mutation | must fail |
|---|---|
| drop `except asyncio.CancelledError` from `_fetch_async` | `test_a_cancelled_fetch_kills_its_child_and_reraises` |
| swallow the `CancelledError` (`return ""` instead of `raise`) | the same test, on the missing exception |
| drop the `_terminate` call from the timeout branch | `test_a_timed_out_fetch_kills_its_child` |
| make `get_desync_summary_cached` fetch on a miss | `test_the_cached_reader_never_spawns` |
| make `get_desync_summary_cached` honour the TTL | `test_the_cached_reader_ignores_the_ttl` |

Run: python3 tests/test_desync_summary_cache.py
or:  bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from monitor import desync_summary as ds  # noqa: E402

#: A `--format lines` payload with one ref behind, so `_format` produces a
#: non-empty string and "the reader returned something" is distinguishable from
#: "the reader returned the clean-tree empty string".
BEHIND_PAYLOAD = "REF: aitask-data\nSTATUS: ok\nAHEAD: 0\nBEHIND: 3\n"

#: How long a bounded liveness poll waits for a killed child to disappear.
#: SIGKILL + reap is immediate; this is slack for a loaded box, not a race.
REAP_BUDGET_S = 5.0


def _wait_gone(pid: int, budget: float = REAP_BUDGET_S) -> bool:
    """True once `pid` no longer exists. Bounded poll, never a bare sleep."""
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:          # exists, owned by someone else
            pass
        time.sleep(0.02)
    return False


class _CacheIsolated(unittest.TestCase):
    """`_cache` is module state shared with every other suite in the process."""

    def setUp(self) -> None:
        self._saved = dict(ds._cache)
        ds._cache.clear()
        self.addCleanup(self._restore)
        self.root = self._tmpdir()

    def _tmpdir(self) -> Path:
        """A scratch directory that goes away with the test.

        `mkdtemp` would strand one per call — and this suite takes three per
        lifecycle test (root, stub helper, pid file), so a full run left 15
        directories behind in /tmp.
        """
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        return Path(td.name)

    def _restore(self) -> None:
        ds._cache.clear()
        ds._cache.update(self._saved)


class CachedReaderTests(_CacheIsolated):
    """`get_desync_summary_cached` reads; it never computes."""

    def test_an_empty_cache_reads_as_empty_not_as_a_fetch(self):
        def boom(*a, **k):
            raise AssertionError("the cached reader spawned a subprocess")

        self.assertEqual(ds.get_desync_summary_cached(self.root), "")

        ds._fetch, real = boom, ds._fetch
        self.addCleanup(lambda: setattr(ds, "_fetch", real))
        self.assertEqual(ds.get_desync_summary_cached(self.root), "")

    def test_the_cached_reader_never_spawns(self):
        """The load-bearing property: no fetch on a hit, no fetch on a miss."""
        def boom(*a, **k):
            raise AssertionError("the cached reader spawned a subprocess")

        real_sync, real_async = ds._fetch, ds._fetch_async
        ds._fetch, ds._fetch_async = boom, boom
        self.addCleanup(lambda: (setattr(ds, "_fetch", real_sync),
                                 setattr(ds, "_fetch_async", real_async)))

        ds._cache[str(self.root)] = (time.monotonic(), " · sentinel", "full")
        self.assertEqual(ds.get_desync_summary_cached(self.root), " · sentinel")

    def test_the_cached_reader_ignores_the_ttl(self):
        """Deliberate: expiring here would blank a still-true warning on keypress.

        The TTL decides when to RE-FETCH, which only the fetching readers do.
        """
        stale = time.monotonic() - (ds._TTL_SECONDS * 10)
        ds._cache[str(self.root)] = (stale, " · sentinel", "full")
        self.assertEqual(
            ds.get_desync_summary_cached(self.root), " · sentinel",
            "a long-expired entry was dropped — the keypress path would blank "
            "the bar until the next tick repainted it",
        )

    def test_an_entry_recorded_under_the_other_variant_is_not_reused(self):
        """Both directions — the compact and full strings are not interchangeable."""
        ds._cache[str(self.root)] = (time.monotonic(), " · ↓3", "compact")
        self.assertEqual(ds.get_desync_summary_cached(self.root, compact=True), " · ↓3")
        self.assertEqual(
            ds.get_desync_summary_cached(self.root, compact=False), "",
            "the compact suffix was served to a caller asking for the full form",
        )


class AsyncReaderTests(_CacheIsolated):
    """`get_desync_summary_async` shares the cache and the TTL with the sync one."""

    def test_the_async_reader_populates_the_cache_and_then_reuses_it(self):
        calls = {"n": 0}

        async def counted(project_root, *, compact):
            calls["n"] += 1
            return " · [yellow]desync: aitask-data 3↓[/]"

        real, ds._fetch_async = ds._fetch_async, counted
        self.addCleanup(lambda: setattr(ds, "_fetch_async", real))

        async def scenario():
            first = await ds.get_desync_summary_async(self.root)
            second = await ds.get_desync_summary_async(self.root)
            return first, second

        first, second = asyncio.run(scenario())
        self.assertIn("aitask-data 3↓", first)
        self.assertEqual(first, second)
        self.assertEqual(calls["n"], 1, "the second call inside the TTL re-spawned")
        # The entry the cached reader will later serve.
        self.assertEqual(ds.get_desync_summary_cached(self.root), first)

    def test_an_expired_entry_is_refetched(self):
        """The other direction of the TTL — the fetching reader DOES expire."""
        calls = {"n": 0}

        async def counted(project_root, *, compact):
            calls["n"] += 1
            return f" · fetch{calls['n']}"

        real, ds._fetch_async = ds._fetch_async, counted
        self.addCleanup(lambda: setattr(ds, "_fetch_async", real))

        async def scenario():
            first = await ds.get_desync_summary_async(self.root)
            ts, val, variant = ds._cache[str(self.root)]
            ds._cache[str(self.root)] = (ts - ds._TTL_SECONDS - 1, val, variant)
            return first, await ds.get_desync_summary_async(self.root)

        first, second = asyncio.run(scenario())
        self.assertNotEqual(first, second)
        self.assertEqual(calls["n"], 2)


class FetchAsyncChildLifecycleTests(_CacheIsolated):
    """`_fetch_async` must not outlive its caller — on EITHER exit."""

    def _stub_helper(self, body: str) -> Path:
        """Write a stub `desync_state.py` and point `_HELPER` at it."""
        helper = self._tmpdir() / "desync_state_stub.py"
        helper.write_text(body)
        real = ds._HELPER
        ds._HELPER = helper
        self.addCleanup(lambda: setattr(ds, "_HELPER", real))
        return helper

    def _sleeper(self, pid_file: Path) -> None:
        """A helper that announces its pid, then blocks well past any budget."""
        self._stub_helper(
            "import os, sys, time\n"
            f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
            "sys.stdout.flush()\n"
            "time.sleep(120)\n"
        )

    def _read_pid(self, pid_file: Path, budget: float = REAP_BUDGET_S) -> int:
        deadline = time.monotonic() + budget
        while time.monotonic() < deadline:
            if pid_file.exists():
                raw = pid_file.read_text().strip()
                if raw:
                    return int(raw)
            time.sleep(0.02)
        self.fail("the stub helper never reported a pid — it may not have spawned")

    def test_a_timed_out_fetch_kills_its_child(self):
        """"Returned empty" does not prove the child died — check the pid."""
        pid_file = self._tmpdir() / "pid"
        self._sleeper(pid_file)
        real_timeout, ds._TIMEOUT_SECONDS = ds._TIMEOUT_SECONDS, 0.3
        self.addCleanup(lambda: setattr(ds, "_TIMEOUT_SECONDS", real_timeout))

        async def scenario():
            return await ds._fetch_async(self.root, compact=False)

        self.assertEqual(asyncio.run(scenario()), "")
        pid = int(pid_file.read_text().strip())
        self.assertTrue(
            _wait_gone(pid),
            f"the timed-out helper (pid {pid}) is still running — `_terminate` "
            f"did not reach it",
        )

    def test_a_cancelled_fetch_kills_its_child_and_reraises(self):
        """The second exit: shutdown cancels the refresh worker mid-flight."""
        pid_file = self._tmpdir() / "pid"
        self._sleeper(pid_file)
        # Long enough that the timeout branch cannot be what cleans up — this
        # test must exercise the cancel path or nothing.
        real_timeout, ds._TIMEOUT_SECONDS = ds._TIMEOUT_SECONDS, 120
        self.addCleanup(lambda: setattr(ds, "_TIMEOUT_SECONDS", real_timeout))

        holder: dict[str, int] = {}

        async def scenario():
            task = asyncio.ensure_future(ds._fetch_async(self.root, compact=False))
            # Cancel only once a real child is in flight — cancelling before the
            # spawn would prove nothing about reaping.
            holder["pid"] = await asyncio.get_event_loop().run_in_executor(
                None, self._read_pid, pid_file
            )
            task.cancel()
            with self.assertRaises(
                asyncio.CancelledError,
                msg="the cancellation was swallowed — the caller cannot tell "
                    "a shutdown from a clean empty result",
            ):
                await task

        asyncio.run(scenario())
        pid = holder["pid"]
        self.assertTrue(
            _wait_gone(pid),
            f"the cancelled helper (pid {pid}) outlived its caller — a "
            f"`except asyncio.TimeoutError` alone does not reap it",
        )

    def test_a_clean_fetch_returns_the_formatted_summary(self):
        """Positive control: the lifecycle tests above are not passing vacuously."""
        self._stub_helper(f"print({BEHIND_PAYLOAD!r}, end='')\n")

        async def scenario():
            return await ds._fetch_async(self.root, compact=False)

        self.assertIn("aitask-data 3↓", asyncio.run(scenario()))

    def test_a_missing_helper_is_not_an_error(self):
        ds._HELPER, real = Path("/nonexistent/desync_state.py"), ds._HELPER
        self.addCleanup(lambda: setattr(ds, "_HELPER", real))

        async def scenario():
            return await ds._fetch_async(self.root, compact=False)

        self.assertEqual(asyncio.run(scenario()), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
