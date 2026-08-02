"""Characterization + performance baseline for `ait board` task movement (t1243_1).

There were **zero** board-movement tests before this file. Children t1243_3/4/5/11
all change how the board writes `boardidx` / `boardcol` or how it re-renders after
a move, so this harness and the pre-registered baseline must exist first.

Why the scenarios run in a **child interpreter**
------------------------------------------------
`aitask_board.TASKS_DIR = task_dir()` is a *module-load* constant, and
`bash tests/run_all_python_tests.sh` runs every `test_*.py` in ONE interpreter
(pytest when importable, otherwise `unittest discover` — the fallback in use on
this machine), where 16 other `test_board_*.py` files already imported
`aitask_board`. Setting `TASK_DIR` in-process is therefore a silent no-op against
a cached module and this file would exercise the **real** `aitasks/` tree.
`IsolationNegativeControlTests` proves exactly that failure mode, read-only.

`TASK_DIR` alone is not enough either: `_task_git_cmd()` resolves
`DATA_WORKTREE = Path(".aitask-data")` **relative to cwd** and `refresh_lock_map()`
shells `./.aitask-scripts/aitask_lock.sh` relative to cwd, so the child's cwd is
the temp tree root — never REPO_ROOT.

The fixture reproduces production's **branch-mode** topology (`aitasks` symlinked
to `.aitask-data/aitasks`, git repo in `.aitask-data`) and keeps `TASK_DIR`
*relative*, because `TaskManager.is_modified` compares `str(task.filepath)` against
`git status --porcelain` paths like `aitasks/tN.md`; an absolute `TASK_DIR` would
never match and no card would render its modified marker.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_board_movement -v   (pytest also works)
  baseline: AITASK_BOARD_BENCH=1 python3 -m unittest \
              tests.test_board_movement.BoardMovementBenchmarkTests.test_bench_baseline -v
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
_BOARD = REPO_ROOT / ".aitask-scripts" / "board"
_LIB = REPO_ROOT / ".aitask-scripts" / "lib"
_TESTS_LIB = REPO_ROOT / "tests" / "lib"
# _TESTS_LIB must be inserted at module level, not inside a test: this file
# re-execs itself as the child interpreter (`--child`, see __main__ below), and
# the child needs the same import path.
for _p in (str(_BOARD), str(_LIB), str(_TESTS_LIB)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from task_yaml import BOARD_KEYS, normalize_board_idx, parse_frontmatter  # noqa: E402

# The fixture vocabulary, the temp-tree builder and the byte differ live in the
# shared harness (t1354_1) so the migrated board modules and this
# characterization harness build identical trees. `build_tree` keeps its exact
# pre-t1354_1 behaviour here — in particular `project_name=None`, so no
# `project_config.yaml` is written and the snapshot allowlist below sees the
# same file set it always saw.
from board_fixture import (  # noqa: E402,F401
    COLUMNS,
    COLUMN_ORDER,
    _GIT_ENV,
    _META_BASE,
    _META_ORDER,
    _fixture_body,
    _fixture_text,
    build_tree,
    diff_snapshots,
    expected_nonboard,
    fixture_name,
    snapshot,
)


def read_board_fields(tree: Path) -> dict[str, dict]:
    """Read boardcol/boardidx straight off disk — independent of the board."""
    out = {}
    for p in sorted((tree / "aitasks").glob("*.md")):
        meta, _body, _order = parse_frontmatter(p.read_text(encoding="utf-8"))
        out[p.name] = {"boardcol": meta.get("boardcol"), "boardidx": meta.get("boardidx")}
    return out


def nonboard_diff(tree: Path, cards) -> list[str]:
    """Files whose non-board frontmatter or body did not survive the scenario."""
    bad = []
    for i, _col, _idx in cards:
        name = fixture_name(i)
        meta, body, _order = parse_frontmatter((tree / "aitasks" / name).read_text(encoding="utf-8"))
        exp_meta, exp_body = expected_nonboard(i)
        got_meta = {k: v for k, v in meta.items() if k not in BOARD_KEYS}
        if got_meta != exp_meta or body != exp_body:
            bad.append(name)
    return bad


def expected_order(state: dict[str, dict]) -> dict[str, list[str]]:
    """Recompute column order from on-disk state using the documented sort key.

    Deliberately re-implemented here rather than calling `get_column_tasks`: the
    child reports the board's own ordering and the two are compared, so the board
    is not grading itself.
    """
    cols: dict[str, list[str]] = {}
    for name, fields in state.items():
        cols.setdefault(fields["boardcol"], []).append(name)
    return {
        col: sorted(names, key=lambda n: (normalize_board_idx(state[n]["boardidx"]), n))
        for col, names in cols.items()
    }


# --- Child-process runner ----------------------------------------------------

def run_child(tree: Path, ipc: Path, params: dict, *, tag: str = "run") -> dict:
    """Run one scenario in a fresh interpreter rooted at the temp tree."""
    pin = ipc / f"{tag}_params.json"
    pout = ipc / f"{tag}_result.json"
    pin.write_text(json.dumps(params), encoding="utf-8")

    env = {k: v for k, v in os.environ.items()}
    env["TASK_DIR"] = "aitasks"  # relative: see module docstring
    # Deliberately NOT seeding PYTHONPATH (t1236): this module bootstraps its own
    # sys.path from __file__, and the child re-executes this same file, so it
    # bootstraps itself too. Handing it a path would let a broken bootstrap pass
    # here and fail only at runtime. Any inherited value is scrubbed for the same
    # reason -- the child must behave identically whatever the caller exported.
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("AITASK_BOARD_BENCH", None)
    env.update(_GIT_ENV)

    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", str(pin), str(pout)],
        cwd=str(tree), env=env, capture_output=True, text=True, timeout=900,
    )
    if not pout.exists():
        raise AssertionError(
            f"child produced no result file (rc={proc.returncode})\n"
            f"--- stderr ---\n{proc.stderr[-4000:]}"
        )
    result = json.loads(pout.read_text(encoding="utf-8"))
    if result.get("error"):
        raise AssertionError(
            f"child failed: {result['error']}\n{result.get('traceback', '')}\n"
            f"--- stderr ---\n{proc.stderr[-4000:]}"
        )
    return result


# =============================================================================
# CHILD SIDE — everything below runs only in the spawned interpreter
# =============================================================================

class Probe:
    """Write spy + exclusive span timers + nesting proof + deferral interval."""

    LEAVES = ("apply_filter", "recompose", "git_status", "save_fields")

    def __init__(self):
        self.nesting: list[list[str]] = []
        self._stack: dict[int, list[str]] = {}
        self.reset()

    def reset(self):
        self.spans = {k: 0.0 for k in self.LEAVES}
        self.counts = {k: 0 for k in self.LEAVES}
        self.inclusive_refresh = 0.0
        self.writes: dict[str, int] = {}
        # Compaction spy (t1243_3). "Exactly one respace" must be asserted
        # directly, not inferred from a write total that also counts the
        # placement write.
        self.respaces: list[str] = []
        self.sync_end: float | None = None
        self.first_deferred_start: float | None = None
        self.filter_event: asyncio.Event | None = None
        self.refocus_event: asyncio.Event | None = None

    # -- span bookkeeping ----------------------------------------------------

    def _enter(self, name: str) -> float:
        tid = threading.get_ident()
        stack = self._stack.setdefault(tid, [])
        if stack:
            # Non-overlap is PROVEN here, not inferred from a non-negative
            # residual: uninstrumented time can absorb a double count and still
            # leave the residual positive.
            self.nesting.append([stack[-1], name])
        stack.append(name)
        t0 = time.perf_counter()
        if self.sync_end is not None and self.first_deferred_start is None and t0 >= self.sync_end:
            self.first_deferred_start = t0
        return t0

    def _exit(self, name: str, t0: float):
        dt = time.perf_counter() - t0
        self._stack[threading.get_ident()].pop()
        self.spans[name] += dt
        self.counts[name] += 1

    def mark_deferred(self):
        t = time.perf_counter()
        if self.sync_end is not None and self.first_deferred_start is None and t >= self.sync_end:
            self.first_deferred_start = t

    @property
    def defer(self) -> float:
        if self.sync_end is None or self.first_deferred_start is None:
            return 0.0
        return max(0.0, self.first_deferred_start - self.sync_end)


def _install_probe(B, probe: Probe, ablate=()):
    """Wrap the four leaves, the two inclusive reporters, the action bodies and
    the refocus callbacks. Patched on the CLASS so every instance is covered.

    `ablate` names leaves whose body is skipped (the wrapper still runs, so the
    call still counts). See `BoardMovementBenchmarkTests` for why removable cost
    is measured by ablation rather than by span share.
    """
    ablate = set(ablate)

    def leaf(owner, attr, name, on_call=None):
        orig = getattr(owner, attr)
        skip = name in ablate

        def wrapper(self_, *a, **kw):
            t0 = probe._enter(name)
            try:
                return None if skip else orig(self_, *a, **kw)
            finally:
                probe._exit(name, t0)
                if on_call is not None:
                    on_call(self_)
        setattr(owner, attr, wrapper)

    def _after_filter(_app):
        if probe.filter_event is not None:
            probe.filter_event.set()

    leaf(B.KanbanApp, "apply_filter", "apply_filter", on_call=_after_filter)
    leaf(B.KanbanApp, "_recompose_column", "recompose")
    leaf(B.TaskManager, "refresh_git_status", "git_status")

    def _save_wrapper(orig):
        def wrapper(self_, *a, **kw):
            t0 = probe._enter("save_fields")
            try:
                return orig(self_, *a, **kw)
            finally:
                probe._exit("save_fields", t0)
                probe.writes[self_.filename] = probe.writes.get(self_.filename, 0) + 1
        return wrapper
    B.Task.reload_and_save_board_fields = _save_wrapper(B.Task.reload_and_save_board_fields)

    # Compaction spy (t1243_3). Not a timed leaf: it runs INSIDE
    # `reposition_task`, whose writes are already counted by `save_fields`, so
    # entering a span here would register a nesting violation.
    def _respace_wrapper(orig):
        def wrapper(self_, col_id, *a, **kw):
            probe.respaces.append(col_id)
            return orig(self_, col_id, *a, **kw)
        return wrapper
    B.TaskManager.respace_column = _respace_wrapper(B.TaskManager.respace_column)

    # Report-only: these CONTAIN _recompose_column, so they are excluded from
    # every formula and are never added to the leaf sum.
    for attr in ("refresh_column", "refresh_columns"):
        orig = getattr(B.KanbanApp, attr)

        def make(orig):
            def wrapper(self_, *a, **kw):
                t0 = time.perf_counter()
                try:
                    return orig(self_, *a, **kw)
                finally:
                    probe.inclusive_refresh += time.perf_counter() - t0
            return wrapper
        setattr(B.KanbanApp, attr, make(orig))

    # End of synchronous key handling — the left edge of the deferral interval.
    for attr in ("_move_task_lateral", "_move_task_vertical", "_move_task_to_extreme"):
        orig = getattr(B.KanbanApp, attr)

        def make(orig):
            def wrapper(self_, *a, **kw):
                try:
                    return orig(self_, *a, **kw)
                finally:
                    probe.sync_end = time.perf_counter()
            return wrapper
        setattr(B.KanbanApp, attr, make(orig))

    # The LAST deferred callback every move path queues — the true
    # "keypress fully applied" signal, and the timed region's close condition.
    for attr in ("_refocus_card", "_refocus_column"):
        orig = getattr(B.KanbanApp, attr)

        def make(orig):
            def wrapper(self_, *a, **kw):
                probe.mark_deferred()
                try:
                    return orig(self_, *a, **kw)
                finally:
                    if probe.refocus_event is not None:
                        probe.refocus_event.set()
            return wrapper
        setattr(B.KanbanApp, attr, make(orig))


def _apply_mutation(B, mutate: str | None):
    """Injected defect used to prove the flip table discriminates.

    t1243_3 re-pointed these. The pre-gap-indexing mutation no-op'd
    `TaskManager.normalize_indices`, a method that no longer exists — the
    assignment would merely CREATE an unused attribute, leaving the mutation
    inert and making `HarnessDiscriminationTests` fail for the wrong reason (the
    control must fail because behaviour is pinned, not because the defect
    missed). Both mutations below target live code.
    """
    if not mutate:
        return
    if mutate == "respace_after_move":
        # Reinstates exactly the write amplification gap indexing removed: a
        # column move that also renumbers both columns to 10/20/30. Must break
        # the frozen record for `lateral_gapped`.
        orig = B.TaskManager.move_tasks_to_column

        def wrapper(self_, task_names, new_col):
            names = list(task_names)
            sources = {self_.task_datas[n].board_col
                       for n in names if n in self_.task_datas}
            result = orig(self_, names, new_col)
            for col in sources | {new_col}:
                self_.respace_column(col, stride=10)
            return result
        B.TaskManager.move_tasks_to_column = wrapper
    elif mutate == "skip_respace":
        # Removes the compaction remedy. `reposition_task`'s retry then has no
        # room and its in-code assertion must fire — proving the remedy is
        # load-bearing on the real action path rather than merely present.
        B.TaskManager.respace_column = lambda self_, col_id, stride=None: None
    else:  # pragma: no cover - guarded by the caller
        raise ValueError(f"unknown mutation: {mutate}")


async def _settle(pilot, times=3):
    for _ in range(times):
        await pilot.pause()


def _focus(B, app, filename):
    for card in app.query(B.TaskCard):
        if not card.is_child and card.task_data.filename == filename:
            card.focus()
            return card
    raise AssertionError(f"no card for {filename}")


def _board_order(app) -> dict[str, list[str]]:
    return {
        col: [t.filename for t in app.manager.get_column_tasks(col)]
        for col in app.manager.column_order
    }


def _child_main(params_path: str, result_path: str) -> int:
    params = json.loads(Path(params_path).read_text(encoding="utf-8"))
    out: dict = {}
    try:
        import aitask_board as B

        probe = Probe()
        _install_probe(B, probe, ablate=params.get("ablate", ()))
        _apply_mutation(B, params.get("mutate"))

        out = asyncio.run(_run_in_app(B, probe, params))
        out["tasks_dir"] = str(B.TASKS_DIR)
        out["tasks_dir_resolved"] = str(Path(B.TASKS_DIR).resolve())
        out["nesting_violations"] = probe.nesting
    except BaseException as exc:  # noqa: BLE001 - reported to the parent
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["traceback"] = traceback.format_exc()
    Path(result_path).write_text(json.dumps(out), encoding="utf-8")
    return 1 if out.get("error") else 0


async def _run_in_app(B, probe: Probe, params: dict) -> dict:
    app = B.KanbanApp()
    size = tuple(params.get("size", [200, 60]))
    async with app.run_test(size=size) as pilot:
        await _settle(pilot)
        result = {
            "loaded": sorted(app.manager.task_datas),
            "unordered_empty": not app.manager.get_column_tasks("unordered"),
        }
        probe.filter_event = asyncio.Event()
        probe.refocus_event = asyncio.Event()

        if params["mode"] == "scenario":
            # `steps` is a list of {focus, key}; the single-key form is one step.
            # Multi-step exists because transit and gap exhaustion are
            # *sequences* — a single keypress cannot drive an interval down to
            # its bound, let alone past it (t1243_3). The probe is reset once,
            # before the first step, so counts accumulate across the whole
            # sequence.
            steps = params.get("steps") or [
                {"focus": params["focus"], "key": params["key"]}]
            _focus(B, app, steps[0]["focus"])
            await _settle(pilot)
            probe.reset()
            probe.filter_event = asyncio.Event()
            probe.refocus_event = asyncio.Event()
            for i, step in enumerate(steps):
                if i:
                    # Re-focus explicitly rather than relying on where the
                    # previous move left focus: a step that moves a *different*
                    # card must not silently act on the one still focused.
                    _focus(B, app, step["focus"])
                    await _settle(pilot)
                await pilot.press(step["key"])
                await _settle(pilot, 5)
            result["writes_by_file"] = dict(probe.writes)
            result["writes_total"] = sum(probe.writes.values())
            result["respaces"] = list(probe.respaces)
            result["board_order"] = _board_order(app)
        else:
            result.update(await _bench(B, app, pilot, probe, params))
        return result


async def _sample(pilot, probe: Probe, key: str) -> dict:
    """One timed keypress.

    NEVER uses `pilot.pause()` here: in Textual 8.2.7 `pause()` calls
    `wait_for_idle(0)`, whose loop always sleeps at least one
    `SLEEP_GRANULARITY` (1/50 s) BEFORE any idle test — a ≥20 ms synthetic floor
    that would dominate a single-digit-ms keypress and dilute every ratio.
    `pilot.press` awaits `_wait_for_screen()`, which is event-driven with no
    sleep, and the region closes on an `asyncio.Event`.
    """
    probe.reset()
    probe.filter_event = asyncio.Event()
    probe.refocus_event = asyncio.Event()

    t0 = time.perf_counter()
    await pilot.press(key)
    press_covered = probe.refocus_event.is_set()
    await asyncio.wait_for(probe.refocus_event.wait(), timeout=5)
    t1 = time.perf_counter()

    return {
        "e2e": t1 - t0,
        "af": probe.spans["apply_filter"],
        "rc": probe.spans["recompose"],
        "git": probe.spans["git_status"],
        "save": probe.spans["save_fields"],
        "defer": probe.defer,
        "inclusive_refresh": probe.inclusive_refresh,
        "writes": sum(probe.writes.values()),
        "filter_calls": probe.counts["apply_filter"],
        "press_covered": press_covered,
    }


def _validate(sample: dict, nesting: list) -> list[str]:
    """The four per-sample validity invariants. Any failure fails the RUN."""
    bad = []
    if sample["writes"] <= 0:
        bad.append("zero-write sample (action was rejected, not performed)")
    if sample["filter_calls"] <= 0:
        bad.append("apply_filter did not run inside the timed region")
    if nesting:
        bad.append(f"instrumented spans nested: {nesting}")
    leaves = sample["af"] + sample["rc"] + sample["git"] + sample["save"]
    other = sample["e2e"] - leaves
    if other < 0:
        bad.append(f"negative residual {other:.6f} (leaf sum exceeds e2e)")
    if sample["defer"] > other + 1e-9:
        bad.append("defer exceeds the unattributed residual")
    if sample["rc"] > sample["inclusive_refresh"] + 1e-9:
        bad.append("recompose exceeds its inclusive refresh wrapper")
    return bad


async def _floor(pilot, probe: Probe, key: str, n: int) -> list[float]:
    """Harness floor: the same timed press with a key that has no binding.

    `Pilot.press` awaits `_wait_for_screen()`, which posts a `call_later` to the
    app *and every widget* and waits for all of them. That cost is proportional
    to the widget count and is pure test-harness bookkeeping, not board latency.
    Without this control an O(cards) harness cost is indistinguishable from
    O(cards) board work and would be attributed to `other`.
    """
    out = []
    for _ in range(n):
        probe.reset()
        t0 = time.perf_counter()
        await pilot.press(key)
        out.append(time.perf_counter() - t0)
        if sum(probe.writes.values()):
            raise RuntimeError(f"floor key {key!r} is bound to a writing action")
    return out


async def _bench(B, app, pilot, probe: Probe, params: dict) -> dict:
    warmup_pairs = params["warmup_pairs"]
    pairs = params["pairs"]
    axes = {}
    floor_key = params.get("floor_key", "f9")
    floor = await _floor(pilot, probe, floor_key, warmup_pairs + pairs)
    floor = floor[warmup_pairs:]
    for axis, spec in params["axes"].items():
        _focus(B, app, spec["focus"])
        await _settle(pilot, 5)
        start_state = _board_order(app)
        samples = []
        for n in range(warmup_pairs + pairs):
            record = []
            for key in (spec["forward"], spec["back"]):
                s = await _sample(pilot, probe, key)
                problems = _validate(s, probe.nesting)
                if problems:
                    raise RuntimeError(f"{axis} pair {n} key {key}: " + "; ".join(problems))
                record.append(s)
            # Ping-pong must be stationary: `move_task_to_column` appends past
            # the destination maximum, so right->left only restores the
            # pre-state for a card starting at the BOTTOM of its column. The
            # comparison is on ORDER, not on indices — under gap indexing each
            # round trip lands the card on a fresh (larger) index while its
            # slot is unchanged, which is exactly the invariant the workload
            # needs. Assert it every pair rather than letting the workload drift.
            if _board_order(app) != start_state:
                raise RuntimeError(f"{axis} pair {n}: pre-state not restored")
            if n >= warmup_pairs:
                samples.extend(record)
        axes[axis] = samples
    return {"axes": axes, "floor": floor}


# --- Reporting helpers (parent side) ----------------------------------------

def _median(xs):
    return statistics.median(xs) if xs else 0.0


def _p90(xs):
    if not xs:
        return 0.0
    ordered = sorted(xs)
    return ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]


def summarise(samples: list[dict]) -> dict:
    """Per-sample ratios, THEN medianed — never a ratio of aggregates.

    Denominator is wall-clock e2e for every quantity. Subtracting deferral would
    make the 40% gate and the 30% target incoherent (e2e=20ms, defer=10ms,
    render=5ms reads as a 50% share but yields only a 25% wall-clock win).
    """
    e2e = [s["e2e"] for s in samples]
    ratio = lambda f: _median([f(s) / s["e2e"] for s in samples])  # noqa: E731
    return {
        "n": len(samples),
        "e2e_median": _median(e2e),
        "e2e_p90": _p90(e2e),
        "defer_median": _median([s["defer"] for s in samples]),
        "defer_share": ratio(lambda s: s["defer"]),
        "R_pair": ratio(lambda s: s["af"] + s["rc"]),
        "R_af": ratio(lambda s: s["af"]),
        "R_rc": ratio(lambda s: s["rc"]),
        "R_git": ratio(lambda s: s["git"]),
        "R_rm4": ratio(lambda s: s["af"] + s["git"]),
        "R_rm5": ratio(lambda s: s["rc"]),
        "other_share": ratio(lambda s: s["e2e"] - (s["af"] + s["rc"] + s["git"] + s["save"])),
        "press_covered_all": all(s["press_covered"] for s in samples),
    }


# =============================================================================
# PARENT SIDE — scenarios, flip table, controls
# =============================================================================

# Canonical: c0 = 10/20/30, c1 = 10/20, c2 = 10.
CANONICAL = [(1, "c0", 10), (2, "c0", 20), (3, "c0", 30),
             (4, "c1", 10), (5, "c1", 20), (6, "c2", 10)]
# Non-canonical source column. Before t1243_3 this was where normalize_indices
# had real work to do; now it is the fixture that proves the source column is
# NOT rewritten — it must still read 5/17/42 after the move.
GAPPED = [(1, "c0", 5), (2, "c0", 17), (3, "c0", 42),
          (4, "c1", 10), (5, "c1", 20), (6, "c2", 10)]
# t9004 carries the STRING "20": `build_tree` passes the value straight into
# serialize_frontmatter, so the file reads `boardidx: '20'`. Before t1243_3 the
# raw `max()` in move_task_col raised TypeError comparing str with int.
QUOTED = [(1, "c0", 10), (2, "c0", 20), (3, "c0", 30),
          (4, "c1", "20"), (5, "c1", 30), (6, "c2", 10)]
# Tied indices are reachable in production: delete_column assigns board_idx = 0
# to every evicted task. Rendered order falls back to the filename tie-break.
TIED2 = [(1, "c0", 10), (2, "c0", 10), (3, "c0", 30),
         (4, "c1", 10), (5, "c1", 20), (6, "c2", 10)]
TIED3 = [(1, "c0", 10), (2, "c0", 10), (3, "c0", 10),
         (4, "c1", 10), (5, "c1", 20), (6, "c2", 10)]

# Drives c0's top gap down to width 1: 10/20/30 -> 10,15,20 -> 10,12,15 ->
# 10,11,12. Each step moves whichever card currently sits LAST, so every insert
# targets the same shrinking interval; a single card pressed repeatedly would
# reach the top and prepend instead.
_HALVING_STEPS = [
    {"focus": fixture_name(3), "key": "shift+up"},
    {"focus": fixture_name(2), "key": "shift+up"},
    {"focus": fixture_name(3), "key": "shift+up"},
]

SCENARIOS = {
    "lateral_canonical": {"cards": CANONICAL, "focus": 3, "key": "shift+right"},
    "lateral_gapped":    {"cards": GAPPED,    "focus": 3, "key": "shift+right"},
    "vertical_swap":     {"cards": CANONICAL, "focus": 2, "key": "shift+down"},
    "extreme_top":       {"cards": CANONICAL, "focus": 3, "key": "ctrl+up"},
    "extreme_bottom":    {"cards": CANONICAL, "focus": 1, "key": "ctrl+down"},
    "shift_column":      {"cards": CANONICAL, "focus": 1, "key": "ctrl+right"},
    # --- gap indexing (t1243_3) ---
    "transit_multi_hop": {"cards": CANONICAL, "steps": [
        {"focus": fixture_name(3), "key": "shift+right"},
        {"focus": fixture_name(3), "key": "shift+right"},
    ]},
    "vertical_at_bound":  {"cards": CANONICAL, "steps": list(_HALVING_STEPS)},
    "vertical_exhaustion": {"cards": CANONICAL, "steps": _HALVING_STEPS + [
        {"focus": fixture_name(2), "key": "shift+up"},
    ]},
    "quoted_boardidx":    {"cards": QUOTED, "focus": 3, "key": "shift+right"},
    "tie_two_way_up":     {"cards": TIED2,  "focus": 2, "key": "shift+up"},
    "tie_two_way_down":   {"cards": TIED2,  "focus": 1, "key": "shift+down"},
    "tie_three_way_up_compacts": {"cards": TIED3, "focus": 3, "key": "shift+up"},
}

# --- THE FLIP TABLE ---------------------------------------------------------
#
# Behaviour asserted EXACTLY (never assertGreater). **A silent pass after a
# movement rewrite is a bug in the table, not a passing test** — t1243_11 adds
# block moves and MUST consciously edit it, as t1243_3 did here.
#
# `writes` counts reload_and_save_board_fields calls (a file can be written
# twice in one action -- see `vertical_exhaustion`, where a respace and then the
# placement both touch the moved card); `changed` is the byte differ's exact
# set. The two disagree by design, because Task.save() does not bump updated_at
# and an unchanged-value write is byte-identical. `respaces` lists the columns
# compacted, so "exactly one compaction" is asserted directly.
#
# FLIPPED BY t1243_3 (gap indexing). The old values are quoted per row: canonical
# renumbering rewrote every task in up to two columns on every move, so a
# one-card move dirtied up to three files. Now each single move writes exactly
# one file, and no file outside the move is ever touched -- which is what the
# unchanged `(col, idx)` of every other card in each row asserts.
FLIP_TABLE = {
    "lateral_canonical": {
        # was: writes 1, same changed set. Index 30 (max+10) -> 1044 (max+STEP).
        "writes": 1,
        "changed": {"aitasks/t9003_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 10), 2: ("c0", 20), 3: ("c1", 1044),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "lateral_gapped": {
        # THE HEADLINE FLIP. was: writes 3, changed all three c0 files, and c0
        # renumbered 5/17/42 -> 10/20/30. The source column is now untouched.
        "writes": 1,
        "changed": {"aitasks/t9003_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 5), 2: ("c0", 17), 3: ("c1", 1044),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "vertical_swap": {
        # was: writes 2, changed 2 files (a swap wrote both cards). One insert
        # past the column maximum replaces the swap.
        "writes": 1,
        "changed": {"aitasks/t9002_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 10), 2: ("c0", 1054), 3: ("c0", 30),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "extreme_top": {
        # was: writes 4, changed 3 files (write at min-10, then renumber).
        # A NEGATIVE index is the point: it makes "move to top" a single write.
        "writes": 1,
        "changed": {"aitasks/t9003_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 10), 2: ("c0", 20), 3: ("c0", -1014),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "extreme_bottom": {
        # was: writes 4, changed 3 files.
        "writes": 1,
        "changed": {"aitasks/t9001_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 1054), 2: ("c0", 20), 3: ("c0", 30),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "shift_column": {
        # Unflipped: column reordering never touched task files and still doesn't.
        "writes": 0,
        "changed": {"aitasks/metadata/board_config.json"},
        "respaces": [],
        "state": {1: ("c0", 10), 2: ("c0", 20), 3: ("c0", 30),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },

    # --- new in t1243_3 ---------------------------------------------------
    "transit_multi_hop": {
        # THE TRANSIT GUARANTEE. c0 -> c1 -> c2 writes the moved card once per
        # hop and NOTHING in c0 or c1. Before gap indexing this dirtied both
        # transit columns. 20+STEP=1044, then 10+STEP=1034.
        "writes": 2,
        "changed": {"aitasks/t9003_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 10), 2: ("c0", 20), 3: ("c2", 1034),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "vertical_at_bound": {
        # Three inserts into the same shrinking interval: (10,20)->15,
        # (10,15)->12, (10,12)->11. The last gap is exactly 2 -- the tightest
        # interval that still has an interior value -- so it must NOT compact.
        # t9001 is never written.
        "writes": 3,
        "changed": {"aitasks/t9002_fixture.md", "aitasks/t9003_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 10), 2: ("c0", 12), 3: ("c0", 11),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "vertical_exhaustion": {
        # The same three steps, then a fourth into the now-1-wide gap (10,11):
        # index_between returns None -> ONE respace at stride_for(1)=1024
        # (10,11,12 -> 1024,2048,3072, three writes) -> retry (1024,2048)->1536,
        # one more write on the same card. A legacy 10-spaced column self-heals
        # once and is STEP-spaced thereafter; there is never a second compaction.
        "writes": 7,
        "changed": {"aitasks/t9001_fixture.md", "aitasks/t9002_fixture.md",
                    "aitasks/t9003_fixture.md"},
        "respaces": ["c0"],
        "state": {1: ("c0", 1024), 2: ("c0", 1536), 3: ("c0", 2048),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "quoted_boardidx": {
        # c1 holds the string '20' next to the int 30. The old raw max() raised
        # TypeError comparing str with int; every read now goes through
        # normalize_board_idx, so this appends past max(20,30). t9004 keeps its
        # STRING value -- the quoted file is neither rewritten nor coerced.
        "writes": 1,
        "changed": {"aitasks/t9003_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 10), 2: ("c0", 20), 3: ("c1", 1054),
                  4: ("c1", "20"), 5: ("c1", 30), 6: ("c2", 10)},
    },
    "tie_two_way_up": {
        # t9001 and t9002 both at 10, ordered by the filename tie-break. Moving
        # t9002 up leaves no neighbour above the destination slot, so it
        # prepends to min-STEP. THE EQUAL-INDEX NO-OP, FIXED: the old swap
        # exchanged 10 for 10, both writes were byte-identical, and the card did
        # not move at all.
        "writes": 1,
        "changed": {"aitasks/t9002_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 10), 2: ("c0", -1014), 3: ("c0", 30),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "tie_two_way_down": {
        # The mirror: t9001 moves down past its tied neighbour into (10,30)->20.
        # Also formerly a no-op.
        "writes": 1,
        "changed": {"aitasks/t9001_fixture.md"},
        "respaces": [],
        "state": {1: ("c0", 20), 2: ("c0", 10), 3: ("c0", 30),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "tie_three_way_up_compacts": {
        # A tie is the densest possible interval, so it reaches the compaction
        # branch in ONE keypress where vertical_exhaustion needs four -- the two
        # therefore fail independently. (10,10) -> None -> respace to
        # 1024/2048/3072 -> retry (1024,2048) -> 1536.
        "writes": 4,
        "changed": {"aitasks/t9001_fixture.md", "aitasks/t9002_fixture.md",
                    "aitasks/t9003_fixture.md"},
        "respaces": ["c0"],
        "state": {1: ("c0", 1024), 2: ("c0", 2048), 3: ("c0", 1536),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
}


class _TreeMixin(unittest.TestCase):
    def make_tree(self, cards, **kw):
        tmp = Path(tempfile.mkdtemp(prefix="aitask_board_move_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        ipc = tmp / "ipc"          # deliberately OUTSIDE the snapshot allowlist
        ipc.mkdir()
        return build_tree(tmp, cards, **kw), ipc


class _ScenarioBase(_TreeMixin):
    """Scenario runner + flip-table assertions, shared by the two test classes."""

    def _run_scenario(self, name, mutate=None):
        spec = SCENARIOS[name]
        tree, ipc = self.make_tree(spec["cards"])
        before = snapshot(tree)
        params = {
            "mode": "scenario",
            "mutate": mutate,
            "size": [200, 60],
        }
        if "steps" in spec:
            params["steps"] = spec["steps"]
        else:
            params["focus"] = fixture_name(spec["focus"])
            params["key"] = spec["key"]
        result = run_child(tree, ipc, params, tag=name)
        after = snapshot(tree)
        return tree, spec, result, diff_snapshots(before, after)

    def _assert_frozen(self, name, tree, spec, result, delta):
        expect = FLIP_TABLE[name]

        # The fixture actually loaded — a phantom-stub drop would otherwise make
        # every assertion below pass vacuously.
        self.assertEqual(result["loaded"], sorted(fixture_name(i) for i, _, _ in spec["cards"]))
        self.assertEqual(result["respaces"], expect["respaces"],
                         "compaction must happen exactly where the table says")
        self.assertTrue(result["unordered_empty"], "no fixture card may land in 'unordered'")
        self.assertEqual(result["nesting_violations"], [], "instrumented spans must not nest")
        self.assertEqual(Path(result["tasks_dir_resolved"]),
                         (tree / "aitasks").resolve(),
                         "child must resolve TASKS_DIR inside the temp tree")

        self.assertEqual(result["writes_total"], expect["writes"], "write-spy count")
        self.assertEqual(delta["changed"], expect["changed"], "exact changed-path set")
        self.assertEqual(delta["added"], set())
        self.assertEqual(delta["removed"], set())

        state = read_board_fields(tree)
        want = {fixture_name(i): {"boardcol": c, "boardidx": x}
                for i, (c, x) in expect["state"].items()}
        self.assertEqual(state, want, "final boardcol/boardidx read from disk")

        self.assertEqual(nonboard_diff(tree, spec["cards"]), [],
                         "status/priority/issue_type/body must survive every write")

        # Independent ground truth: the expected order is recomputed here from
        # on-disk state, then compared with the board's own get_column_tasks.
        board_order = {k: v for k, v in result["board_order"].items() if v}
        self.assertEqual(board_order, expected_order(state), "column ordering")


class BoardMovementCharacterizationTests(_ScenarioBase):
    """Freeze today's write amplification, final state and ordering."""

    def test_lateral_canonical(self):
        self._assert_frozen("lateral_canonical", *self._run_scenario("lateral_canonical"))

    def test_lateral_gapped_writes_untouched_neighbours(self):
        """The transit-write problem t1243_3 exists to fix, pinned as behaviour."""
        self._assert_frozen("lateral_gapped", *self._run_scenario("lateral_gapped"))

    def test_vertical_swap(self):
        self._assert_frozen("vertical_swap", *self._run_scenario("vertical_swap"))

    def test_extreme_top(self):
        self._assert_frozen("extreme_top", *self._run_scenario("extreme_top"))

    def test_extreme_bottom(self):
        self._assert_frozen("extreme_bottom", *self._run_scenario("extreme_bottom"))

    def test_shift_column_writes_no_task_files(self):
        self._assert_frozen("shift_column", *self._run_scenario("shift_column"))


class GapIndexingTests(_ScenarioBase):
    """The single-write and single-respace guarantees, driven through real keys."""

    def test_transit_dirties_nothing_outside_the_moved_task(self):
        """A->B->C writes the moved card once per hop and nothing in A or B."""
        self._assert_frozen("transit_multi_hop", *self._run_scenario("transit_multi_hop"))

    def test_at_bound_interval_does_not_compact(self):
        """Three inserts drive the gap to exactly 2 — still no respace."""
        self._assert_frozen("vertical_at_bound", *self._run_scenario("vertical_at_bound"))

    def test_exhausted_interval_compacts_exactly_once(self):
        """A fourth insert exhausts the gap: one respace, then the retry
        succeeds. A legacy 10-spaced column self-heals and stays STEP-spaced."""
        self._assert_frozen("vertical_exhaustion", *self._run_scenario("vertical_exhaustion"))

    def test_quoted_boardidx_no_longer_raises(self):
        """The raw max() TypeError, and the quoted file is left untouched."""
        self._assert_frozen("quoted_boardidx", *self._run_scenario("quoted_boardidx"))

    def test_tied_indices_move_up(self):
        """The equal-index no-op: the old swap exchanged 10 for 10 and the card
        never moved."""
        self._assert_frozen("tie_two_way_up", *self._run_scenario("tie_two_way_up"))

    def test_tied_indices_move_down(self):
        self._assert_frozen("tie_two_way_down", *self._run_scenario("tie_two_way_down"))

    def test_three_way_tie_compacts_once(self):
        self._assert_frozen("tie_three_way_up_compacts",
                            *self._run_scenario("tie_three_way_up_compacts"))


class HarnessDiscriminationTests(_ScenarioBase):
    """Prove the oracle can fail — a passing test pins nothing until it does."""

    def test_flip_table_rejects_a_mutated_board(self):
        """Reinstating the old renumber-after-move must break the frozen record.

        The pre-t1243_3 mutation no-op'd `normalize_indices`; after the rewrite
        that method does not exist, so the assignment would create an unused
        attribute and this control would fail because the DEFECT missed rather
        than because behaviour is pinned.
        """
        name = "lateral_gapped"
        tree, spec, result, delta = self._run_scenario(name, mutate="respace_after_move")
        expect = FLIP_TABLE[name]
        observed = (result["writes_total"], delta["changed"])
        self.assertNotEqual(
            observed, (expect["writes"], expect["changed"]),
            "respacing both columns after a move must break the frozen record; "
            "if this passes, the flip table is not actually pinning behaviour",
        )
        with self.assertRaises(AssertionError):
            self._assert_frozen(name, tree, spec, result, delta)

    def test_compaction_is_load_bearing_on_the_real_action_path(self):
        """Removing the respace remedy must make the exhausted move FAIL.

        `reposition_task`'s post-respace retry cannot fail while `stride_for`
        holds, so the in-code assertion guarding it is unreachable in normal
        operation. Breaking the remedy is the only way to show it is not
        vacuous — and it proves the compaction is reached through the real
        keypress path, not merely present in the manager.
        """
        with self.assertRaises(AssertionError) as ctx:
            self._run_scenario("vertical_exhaustion", mutate="skip_respace")
        self.assertIn("retry after respace", str(ctx.exception))

    def test_the_same_scenario_passes_unmutated(self):
        """Negative control for the control above: the AssertionError came from
        the removed remedy, not from the scenario being broken."""
        self._assert_frozen("vertical_exhaustion", *self._run_scenario("vertical_exhaustion"))


class IsolationNegativeControlTests(unittest.TestCase):
    """Read-only proof that the in-process variant would read the REAL tree."""

    def test_in_process_task_dir_override_reads_the_real_repo(self):
        import aitask_board  # already cached here, as in a full-suite run

        tmp = Path(tempfile.mkdtemp(prefix="aitask_board_negctrl_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "aitasks").mkdir()
        prev = os.environ.get("TASK_DIR")

        # patch.dict restores the prior value (or its absence) even on failure.
        # The full suite runs in ONE interpreter, so a leaked TASK_DIR would
        # point later tests and their subprocesses at a deleted temp tree.
        with mock.patch.dict(os.environ, {"TASK_DIR": str(tmp / "aitasks")}):
            # 1. the override is a no-op against the cached module constant
            self.assertEqual(aitask_board.TASKS_DIR, Path("aitasks"))
            # 2. ... and it is genuinely a different root
            self.assertNotEqual(
                Path(os.environ["TASK_DIR"]).resolve(),
                (REPO_ROOT / aitask_board.TASKS_DIR).resolve(),
            )
            # 3. ... which would have enumerated the real repo's tasks.
            #    Read-only: no TaskManager is constructed and nothing is written.
            real = sorted(p.name for p in (REPO_ROOT / aitask_board.TASKS_DIR).glob("*.md"))
            self.assertTrue(real, "the real aitasks/ tree must be non-empty for this control")
            self.assertEqual([n for n in real if n.endswith("_fixture.md")], [],
                             "the real tree must contain none of the fixture files")

        self.assertEqual(os.environ.get("TASK_DIR"), prev, "TASK_DIR must be restored")


class HarnessInvariantTests(unittest.TestCase):
    """Guards on the harness itself, not on the board."""

    def test_timed_region_never_calls_pilot_pause(self):
        """`pause()` is a ≥20 ms synthetic sleep — it must not be inside a sample.

        Textual 8.2.7's `Pilot.pause()` calls `wait_for_idle(0)`, whose loop
        always sleeps one `SLEEP_GRANULARITY` (1/50 s) before testing for idle.
        Two such calls would add ~40 ms to a keypress plausibly costing
        single-digit ms and dilute every attribution ratio, so the timed region
        is confined to `_sample` and closes on an `asyncio.Event` instead.
        """
        import ast
        import inspect
        import textwrap

        fn = ast.parse(textwrap.dedent(inspect.getsource(_sample))).body[0]
        # AST, not substring: a docstring or comment mentioning pause() must not
        # trip the guard, and a real call must not hide behind one.
        calls = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
        self.assertNotIn("pilot.pause", calls,
                         "the timed region must not contain a Pilot idle wait")
        self.assertIn("pilot.press", calls)
        self.assertIn("asyncio.wait_for", calls)
        self.assertIn("probe.refocus_event.wait", calls)

    def test_pause_floor_assumption_still_holds(self):
        """Pin the Textual internals the timing design depends on."""
        from textual._wait import SLEEP_GRANULARITY
        self.assertGreaterEqual(
            SLEEP_GRANULARITY, 1 / 100,
            "if Textual's idle granularity changed, re-check the timing design")


BENCH_ENV = "AITASK_BOARD_BENCH"

# Pre-registered, recorded in aiplans/p1243_board_task_groups_and_fast_reordering.md
# BEFORE any measurement. Thresholds are the parent plan's, unchanged.
PREMISE_THRESHOLD = 0.40   # combined workstream only: R_pair on the lateral axis
TARGET_THRESHOLD = 0.30    # each child's own target == its opportunity gate
BENCH_CARDS = 200
BENCH_WARMUP_PAIRS = 3
BENCH_PAIRS = 20
SMOKE_CARDS = 20
SMOKE_PAIRS = 2


def _bench_cards(n: int):
    """n cards spread over the 5 columns, canonical 10/20/30... per column."""
    per = {c: 0 for c in COLUMN_ORDER}
    cards = []
    for i in range(1, n + 1):
        col = COLUMN_ORDER[(i - 1) % len(COLUMN_ORDER)]
        per[col] += 10
        cards.append((i, col, per[col]))
    return cards


def _bench_axes(cards):
    """Ping-pong anchors.

    Lateral moves the BOTTOM card of c0: `move_task_to_column` appends past the
    destination maximum, so only a bottom-of-column card returns to its exact
    slot after right-then-left. Vertical moves a mid-column card, where the
    down/up pair is symmetric under gap indexing: down appends past the column
    maximum, up then lands back on the midpoint of the same interval, so the
    index is periodic and no gap ever narrows (t1243_3 — a shrinking gap would
    eventually trigger a compaction mid-benchmark and pollute the samples).
    """
    c0 = [i for i, col, _ in cards if col == "c0"]
    return {
        "lateral": {"focus": fixture_name(c0[-1]), "forward": "shift+right", "back": "shift+left"},
        "vertical": {"focus": fixture_name(c0[len(c0) // 2]), "forward": "shift+down", "back": "shift+up"},
    }


class BoardMovementBenchmarkTests(_TreeMixin):
    """Pre-registered baseline. Full run is env-gated; the smoke always runs.

    **Removable cost is measured by ABLATION, not by span share.** The first
    baseline run attributed only 1.6 % of a lateral keypress to
    `apply_filter + _recompose_column` while leaving 98 % unattributed, which
    would have refuted the premise. That reading was an instrumentation
    artifact: `_recompose_column` calls `remove_children()` / `mount_all()`,
    which return awaitables the board never awaits, so the mount + CSS + layout
    work they cause happens in the message pump *after* the wrapped call
    returns. A wall-clock span around `_recompose_column` therefore measures its
    bookkeeping, not its cost.

    Two controls establish that the missing time is real board work:
    a no-op-keypress **floor** (46-86 ms, i.e. `Pilot._wait_for_screen`'s
    per-widget bookkeeping is not the wall), and **scaling** with card count
    (460 ms at 25 cards -> 2222 ms at 200) while every span share stays pinned
    near 1 %.

    Ablation asks the question the gates actually ask -- "how much can this
    child remove?" -- and is immune to where in the pump the cost lands. Each
    ablated configuration no-ops one or more leaves and re-measures; the delta
    against the full run is that lever's removable cost. It is an **ideal
    removal upper bound**: a real implementation must still do the work
    correctly, so clearing a gate remains necessary-not-sufficient, exactly as
    pre-registered.
    """

    def _bench(self, n_cards, pairs, warmup, *, branch_mode=True, tag="bench",
               ablate=(), axes=None):
        cards = _bench_cards(n_cards)
        tree, ipc = self.make_tree(cards, branch_mode=branch_mode)
        all_axes = _bench_axes(cards)
        chosen = {k: v for k, v in all_axes.items() if axes is None or k in axes}
        result = run_child(tree, ipc, {
            "mode": "bench",
            "size": [200, 60],
            "warmup_pairs": warmup,
            "pairs": pairs,
            "axes": chosen,
            "ablate": list(ablate),
        }, tag=tag)
        self.assertEqual(result["nesting_violations"], [])
        self.assertEqual(len(result["loaded"]), n_cards)
        out = {axis: summarise(s) for axis, s in result["axes"].items()}
        out["_floor"] = _median(result["floor"])
        return out

    def test_bench_smoke_keeps_the_measurement_path_alive(self):
        """Ungated: small, no thresholds, but every validity invariant active."""
        report = self._bench(SMOKE_CARDS, SMOKE_PAIRS, 1, tag="smoke")
        for axis in ("lateral", "vertical"):
            self.assertEqual(report[axis]["n"], SMOKE_PAIRS * 2)
            self.assertGreater(report[axis]["e2e_median"], 0.0)
            self.assertGreaterEqual(report[axis]["other_share"], 0.0)

    @unittest.skipUnless(os.environ.get(BENCH_ENV) == "1",
                         f"set {BENCH_ENV}=1 to run the full pre-registered baseline")
    def test_bench_baseline(self):
        P, W = BENCH_PAIRS, BENCH_WARMUP_PAIRS
        full = self._bench(BENCH_CARDS, P, W, tag="full")
        legacy = self._bench(BENCH_CARDS, P, W, branch_mode=False, tag="legacy",
                             axes=["lateral"])
        # Ablations: each no-ops one lever and re-measures. delta == removable cost.
        abl = {
            "no_rc": self._bench(BENCH_CARDS, P, W, tag="no_rc",
                                 ablate=["recompose"], axes=["lateral"]),
            "no_af_git": self._bench(BENCH_CARDS, P, W, tag="no_af_git",
                                     ablate=["apply_filter", "git_status"]),
            "no_af_rc": self._bench(BENCH_CARDS, P, W, tag="no_af_rc",
                                    ablate=["apply_filter", "recompose"],
                                    axes=["lateral"]),
        }

        def removed(axis, cfg):
            base = full[axis]["e2e_median"]
            return max(0.0, base - abl[cfg][axis]["e2e_median"]) / base

        lat_e2e = full["lateral"]["e2e_median"]
        vert_e2e = full["vertical"]["e2e_median"]
        R_pair_lat = removed("lateral", "no_af_rc")
        R_rm4 = max(removed("lateral", "no_af_git"), removed("vertical", "no_af_git"))
        R_rm5_lat = removed("lateral", "no_rc")

        # t1243_4's levers are measured while recompose still dominates, which
        # masks them. This CONDITIONAL share asks what apply_filter is worth on
        # the board t1243_5 would leave behind (recompose already gone) -- the
        # world t1243_4 would actually ship into. Reported, not gated: the
        # pre-registered gate is the unconditional one above.
        post = abl["no_rc"]["lateral"]["e2e_median"]
        R_rm4_after_rm5 = max(0.0, post - abl["no_af_rc"]["lateral"]["e2e_median"]) / post

        verdicts = {
            "workstream_B_premise (R_pair_lateral >= 0.40)":
                (R_pair_lat, PREMISE_THRESHOLD, R_pair_lat >= PREMISE_THRESHOLD),
            "t1243_4 opportunity (max R_rm4 >= 0.30)":
                (R_rm4, TARGET_THRESHOLD, R_rm4 >= TARGET_THRESHOLD),
            "t1243_5 opportunity (R_rm5_lateral >= 0.30)":
                (R_rm5_lat, TARGET_THRESHOLD, R_rm5_lat >= TARGET_THRESHOLD),
        }

        print("\n=== t1243_1 pre-registered baseline (ablation attribution) ===")
        print(f"method: {BENCH_CARDS} cards / {len(COLUMN_ORDER)} columns, "
              f"{W} warm-up pairs discarded, {P} recorded pairs/axis/config")
        print(f"harness floor (no-op keypress): {full['_floor']*1000:.1f} ms "
              f"-- {full['_floor']/lat_e2e*100:.1f}% of lateral e2e")
        for axis in ("lateral", "vertical"):
            s = full[axis]
            print(f"\n[{axis}] n={s['n']}  e2e median={s['e2e_median']*1000:.1f} ms  "
                  f"p90={s['e2e_p90']*1000:.1f} ms")
            print(f"  deferral (diagnostic): {s['defer_median']*1000:.1f} ms "
                  f"({s['defer_share']*100:.1f}%)   press_covered_all={s['press_covered_all']}")
            print(f"  span shares (UNDER-attribute; see class docstring): "
                  f"af={s['R_af']*100:.1f}% rc={s['R_rc']*100:.1f}% "
                  f"git={s['R_git']*100:.1f}% other={s['other_share']*100:.1f}%")
        print("\n[ablation] median e2e with a lever removed:")
        print(f"  lateral  full={lat_e2e*1000:8.1f} ms   "
              f"-recompose={abl['no_rc']['lateral']['e2e_median']*1000:8.1f} ms   "
              f"-filter-git={abl['no_af_git']['lateral']['e2e_median']*1000:8.1f} ms   "
              f"-filter-recompose={abl['no_af_rc']['lateral']['e2e_median']*1000:8.1f} ms")
        print(f"  vertical full={vert_e2e*1000:8.1f} ms   "
              f"-filter-git={abl['no_af_git']['vertical']['e2e_median']*1000:8.1f} ms")
        print(f"\n[topology] lateral e2e branch-mode={lat_e2e*1000:.1f} ms (production, "
              f"used by the checkpoint)  legacy={legacy['lateral']['e2e_median']*1000:.1f} ms; "
              f"git span share {full['lateral']['R_git']*100:.2f}% vs "
              f"{legacy['lateral']['R_git']*100:.2f}%")
        print("\n--- verdicts ---")
        for label, (value, threshold, ok) in verdicts.items():
            print(f"  {'PASS' if ok else 'MISS'}  {label}: {value*100:.1f}% vs {threshold*100:.0f}%")
        print(f"  INFO  t1243_4 share AFTER t1243_5 removes recompose "
              f"(conditional, not gated): {R_rm4_after_rm5*100:.1f}% of "
              f"{post*1000:.1f} ms")

        missed = [f"{k}: {v[0]*100:.1f}% vs {v[1]*100:.0f}%"
                  for k, v in verdicts.items() if not v[2]]
        if missed:
            # A missed gate is EVIDENCE, not an instruction. Nothing here revises,
            # replaces or postpones a task, and no code is reverted -- the
            # Performance-Gate Confirmation Checkpoint (parent plan, "Decision
            # checkpoint") requires the user to choose. This test therefore
            # reports and does not fail the suite.
            print("\n*** performance gate(s) MISSED: " + "; ".join(missed))
            print("*** Take NO corrective action. Present these measurements to the")
            print("*** user and ask: continue / revise scope / postpone / keep as-is.")

        # The run itself must be sound even though a missed gate is not a failure:
        # every sample survived the four validity invariants (enforced in the
        # child) and the expected number of samples was recorded per axis.
        for axis in ("lateral", "vertical"):
            self.assertEqual(full[axis]["n"], P * 2, f"{axis}: sample count")
            self.assertGreater(full[axis]["e2e_median"], 0.0, f"{axis}: median latency")
        self.assertLess(full["_floor"], 0.5 * lat_e2e,
                        "harness floor must not dominate the measurement")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--child":
        sys.exit(_child_main(sys.argv[2], sys.argv[3]))
    unittest.main()
