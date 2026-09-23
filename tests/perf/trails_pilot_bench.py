"""trails_pilot_bench.py - steady-state Pilot benchmark of `ait trails` (t1794_11).

The t718_6 protocol (aidocs/framework/python_tui_performance.md) applied to
`board/trails_app.py`: one Textual `App.run_test` session per repetition,
driving a fixed keyboard workload against THIS repo's task tree, timed with
`perf_counter` around the whole `run_test` block. 5 warmup + 8 measured
repetitions in one process, so PyPy's JIT gets the same warmup it got there.

Usage (from the repo root, under the interpreter being measured):
    <python> tests/perf/trails_pilot_bench.py --list
    <python> tests/perf/trails_pilot_bench.py --trail <handle> [--warmup 5] [--reps 8]

Workload per repetition — every step settles and asserts the state it must
reach, and any failed assertion aborts the run, so a repetition is recorded
only if the whole flow happened:
    boot -> selector -> focus <handle> + enter -> TrailsScreen with cards
    -> enter (detail) -> escape -> v (summary) -> escape
    -> d (drift re-run; call count must grow) -> 10x down -> no live workers

Deterministic seams (patched on `board_trail_screen`, identical under both
interpreters, so subprocess latency stays out of the interpreter comparison):
`load_trail_blob` returns the doc discovered at boot and `run_trail_drift`
returns a fixed ("CURRENT", []) verdict. Boot-time `discover_trails` stays
real, as the t718_6 board workload kept its real refresh.

Manual and never collected (not `test_*`-named). Run nothing else heavy
alongside it. The settle discipline mirrors tests/test_trails_app.py.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_trail_screen  # noqa: E402
import board_trail_view  # noqa: E402
import board_widgets  # noqa: E402
import trails_app  # noqa: E402
from trail_discovery import discover_trails, trail_entry_refs  # noqa: E402

SIZE = (160, 48)
DOWN_PRESSES = 10


class BenchFailure(RuntimeError):
    """A workload state was not reached; the run is invalid and aborts."""


def check(condition: bool, what: str) -> None:
    if not condition:
        raise BenchFailure(what)


def make_app(tasks_dir: Path):
    return trails_app.TrailsApp(
        tasks_dir=tasks_dir,
        metadata_file=tasks_dir / "metadata" / "board_config.json",
        gates_registry_file=tasks_dir / "metadata" / "gates.yaml")


async def settle(app, pilot) -> None:
    """Workers finished, their callbacks landed, and the queued re-mount /
    refocus done: card set, focused widget and screen stable across two
    consecutive pauses (bounded). Same discipline as test_trails_app._settle."""
    for _ in range(3):
        await app.workers.wait_for_complete()
        await pilot.pause()
    previous = None
    for _ in range(40):
        app.screen.refresh(layout=True)
        await pilot.pause()
        state = (tuple(id(c) for c in app.query(board_widgets.TaskCard)),
                 id(app.screen.focused), type(app.screen).__name__)
        if state == previous:
            return
        previous = state
    raise BenchFailure("UI never settled")


async def wait_until(pilot, predicate, what: str, tries: int = 40) -> None:
    for _ in range(tries):
        if predicate():
            return
        await pilot.pause()
    raise BenchFailure(what)


async def one_rep(tasks_dir: Path, handle: str, drift_calls: list) -> float:
    app = make_app(tasks_dir)
    start = time.perf_counter()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        check(isinstance(app.screen, board_trail_view.TrailSelectScreen),
              "boot did not open the trail selector")
        items = [i for i in app.screen.query(board_trail_view.TrailSelectItem)
                 if i.info.handle == handle]
        check(len(items) == 1, f"trail {handle!r} not offered by the selector")
        items[0].focus()
        await pilot.pause()
        await pilot.press("enter")
        await settle(app, pilot)
        check(isinstance(app.screen, trails_app.TrailsScreen), "selection did not land")
        check(app.active_trail_handle == handle, "wrong trail selected")
        check(len(app.query(board_widgets.TaskCard)) > 0, "no cards rendered")
        check(app._focused_card() is not None, "no card focused after selection")

        await pilot.press("enter")
        await wait_until(pilot, lambda: isinstance(
            app.screen, board_trail_view.TrailDetailScreen), "detail modal never opened")
        await pilot.press("escape")
        await settle(app, pilot)
        check(app._focused_card() is not None, "no card focused after detail")

        await pilot.press("v")
        await wait_until(pilot, lambda: isinstance(
            app.screen, board_trail_view.TrailSummaryScreen), "summary modal never opened")
        await pilot.press("escape")
        await settle(app, pilot)
        check(app._focused_card() is not None, "no card focused after summary")

        before = len(drift_calls)
        await pilot.press("d")
        await settle(app, pilot)
        check(len(drift_calls) > before, "d did not re-run the drift check")
        check(app._trail_drift is not None and app._trail_drift[0] == "CURRENT",
              "drift verdict not applied")

        for _ in range(DOWN_PRESSES):
            await pilot.press("down")
            await settle(app, pilot)
            check(app._focused_card() is not None, "focus lost while walking")

        await settle(app, pilot)
        check(not [w for w in app.workers if not w.is_finished],
              "workers still live at teardown")
    return (time.perf_counter() - start) * 1000.0


async def run(tasks_dir: Path, handle: str, warmup: int, reps: int) -> None:
    infos, _errors = discover_trails()
    by_handle = {i.handle: i for i in infos}
    check(handle in by_handle, f"trail {handle!r} not discovered")
    doc = by_handle[handle].doc
    drift_calls: list = []

    def fake_drift(h):
        drift_calls.append(h)
        return ("CURRENT", [])

    impl = f"{sys.implementation.name}-{'.'.join(map(str, sys.version_info[:3]))}"
    measured = []
    with patch.object(board_trail_screen, "load_trail_blob", lambda h: (doc, "", [])), \
            patch.object(board_trail_screen, "run_trail_drift", fake_drift):
        for i in range(warmup + reps):
            ms = await one_rep(tasks_dir, handle, drift_calls)
            kind = "warmup" if i < warmup else "measured"
            if kind == "measured":
                measured.append(ms)
            print(f"{impl} trail={handle} {kind} rep={i + 1} ms={ms:.0f}", flush=True)
    print(f"summary {impl} trail={handle} n={len(measured)} "
          f"median_ms={statistics.median(measured):.0f} "
          f"[{min(measured):.0f}–{max(measured):.0f}]", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trail", help="trail handle (see --list)")
    parser.add_argument("--list", action="store_true", help="list discovered trails")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--reps", type=int, default=8)
    parser.add_argument("--tasks-dir", type=Path, default=Path("aitasks"))
    args = parser.parse_args()
    if args.list:
        infos, _ = discover_trails()
        for info in infos:
            members = len(trail_entry_refs(info.doc or {}))
            print(f"{info.handle}\towner=t{info.owner_id}\tmembers={members}")
        return 0
    if not args.trail:
        parser.error("--trail is required (or --list)")
    try:
        asyncio.run(run(args.tasks_dir, args.trail, args.warmup, args.reps))
    except BenchFailure as exc:
        print(f"ABORTED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
