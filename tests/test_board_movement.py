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
import hashlib
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
for _p in (str(_BOARD), str(_LIB)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from task_yaml import BOARD_KEYS, normalize_board_idx, parse_frontmatter, serialize_frontmatter  # noqa: E402

# --- Fixture vocabulary ------------------------------------------------------

COLUMNS = [
    {"id": "c0", "title": "Col 0", "color": "#FF5555"},
    {"id": "c1", "title": "Col 1", "color": "#50FA7B"},
    {"id": "c2", "title": "Col 2", "color": "#BD93F9"},
    {"id": "c3", "title": "Col 3", "color": "#8BE9FD"},
    {"id": "c4", "title": "Col 4", "color": "#FFB86C"},
]
COLUMN_ORDER = [c["id"] for c in COLUMNS]

# Non-board frontmatter keys. At least one is REQUIRED: TaskManager._is_phantom_stub
# drops any task whose keys are a subset of BOARD_KEYS, so a fixture carrying only
# boardcol/boardidx would load ZERO tasks and every scenario would pass vacuously.
_META_ORDER = ["priority", "effort", "issue_type", "status"]
_META_BASE = {
    "priority": "medium",
    "effort": "low",
    "issue_type": "chore",
    "status": "Ready",
}


def fixture_name(i: int) -> str:
    return f"t{9000 + i}_fixture.md"


def _fixture_body(i: int) -> str:
    return f"\n## Context\n\nSynthetic fixture task {i}.\n\n## Notes\n\nBody line {i}.\n"


def _fixture_text(i: int, col: str, idx: int) -> str:
    """Build a task file through the canonical serializer.

    Hand-written YAML would be re-normalized by `Task.save()` on the very first
    write, so the byte differ would report a change caused by formatting rather
    than by the move. Board keys are emitted last here, which is also where
    `serialize_frontmatter` puts them on re-save, making an unchanged-value write
    byte-identical.
    """
    meta = dict(_META_BASE)
    meta["boardcol"] = col
    meta["boardidx"] = idx
    return serialize_frontmatter(meta, _fixture_body(i), list(_META_ORDER))


def expected_nonboard(i: int) -> tuple[dict, str]:
    return dict(_META_BASE), _fixture_body(i)


# --- Temp tree ---------------------------------------------------------------

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "aitask test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "aitask test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def build_tree(root: Path, cards, *, branch_mode: bool = True, settings=None) -> Path:
    """Materialise a synthetic TASK_DIR and return the tree root (the child's cwd).

    `cards` is a list of (index, col_id, board_idx). `branch_mode=True` reproduces
    production: real files under `.aitask-data/aitasks`, a git repo there, and an
    `aitasks` symlink at the tree root, so `_task_git_cmd()` yields
    `git -C .aitask-data`. `branch_mode=False` is the legacy topology used only by
    the git-cost comparison.
    """
    tree = root / "tree"
    if branch_mode:
        data = tree / ".aitask-data"
        tasks = data / "aitasks"
        git_root = data
    else:
        data = None
        tasks = tree / "aitasks"
        git_root = tree
    (tasks / "metadata").mkdir(parents=True)

    for i, col, idx in cards:
        (tasks / fixture_name(i)).write_text(_fixture_text(i, col, idx), encoding="utf-8")

    (tasks / "metadata" / "board_config.json").write_text(
        json.dumps({"columns": COLUMNS, "column_order": COLUMN_ORDER}, indent=2) + "\n",
        encoding="utf-8",
    )
    local = {
        "settings": {
            # The auto-refresh timer must never fire mid-benchmark, and a collapsed
            # column would make lateral ping-pong skip past its neighbour.
            "auto_refresh_minutes": 0,
            "collapsed_columns": [],
            "sync_on_refresh": False,
            **(settings or {}),
        }
    }
    (tasks / "metadata" / "board_config.local.json").write_text(
        json.dumps(local, indent=2) + "\n", encoding="utf-8"
    )

    if branch_mode:
        (tree / "aitasks").symlink_to(Path(".aitask-data") / "aitasks")

    env = {**os.environ, **_GIT_ENV}
    subprocess.run(["git", "init", "-q", "-b", "main", "."], cwd=git_root, env=env, check=True)
    subprocess.run(["git", "add", "-A", "."], cwd=git_root, env=env, check=True)
    subprocess.run(
        ["git", "commit", "-q", "--no-verify", "-m", "fixture"],
        cwd=git_root, env=env, check=True,
    )
    return tree


# --- The differ: an explicit allowlist, never the whole tree -----------------
#
# Snapshotting the tree root would pick up `.git/index` (git status refreshes its
# stat cache) and any IPC file, making the exact changed-path set noisy and
# platform-dependent. IPC lives outside the tree by construction; this allowlist
# covers only the logical task and board-config files.

def snapshot(tree: Path) -> dict[str, str]:
    base = tree / "aitasks"  # traverses the symlink in branch mode
    out: dict[str, str] = {}
    paths = list(base.rglob("*.md")) + list((base / "metadata").glob("board_config*.json"))
    for p in sorted(paths):
        rel = p.relative_to(tree).as_posix()
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def diff_snapshots(before: dict, after: dict) -> dict[str, set]:
    return {
        "changed": {k for k in before.keys() & after.keys() if before[k] != after[k]},
        "added": set(after) - set(before),
        "removed": set(before) - set(after),
    }


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
    """Injected defect used to prove the flip table discriminates."""
    if not mutate:
        return
    if mutate == "skip_normalize":
        B.TaskManager.normalize_indices = lambda self_, col_id: None
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
            _focus(B, app, params["focus"])
            await _settle(pilot)
            probe.reset()
            probe.filter_event = asyncio.Event()
            probe.refocus_event = asyncio.Event()
            await pilot.press(params["key"])
            await _settle(pilot, 5)
            result["writes_by_file"] = dict(probe.writes)
            result["writes_total"] = sum(probe.writes.values())
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
            # Ping-pong must be stationary: `move_task_col` appends at
            # max_idx + 10, so right->left only restores the pre-state for a
            # card starting at the BOTTOM of its column. Assert it every pair
            # rather than letting the workload drift.
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
# Non-canonical source column, so normalize_indices has real work to do.
GAPPED = [(1, "c0", 5), (2, "c0", 17), (3, "c0", 42),
          (4, "c1", 10), (5, "c1", 20), (6, "c2", 10)]

SCENARIOS = {
    "lateral_canonical": {"cards": CANONICAL, "focus": 3, "key": "shift+right"},
    "lateral_gapped":    {"cards": GAPPED,    "focus": 3, "key": "shift+right"},
    "vertical_swap":     {"cards": CANONICAL, "focus": 2, "key": "shift+down"},
    "extreme_top":       {"cards": CANONICAL, "focus": 3, "key": "ctrl+up"},
    "extreme_bottom":    {"cards": CANONICAL, "focus": 1, "key": "ctrl+down"},
    "shift_column":      {"cards": CANONICAL, "focus": 1, "key": "ctrl+right"},
}

# --- THE FLIP TABLE ---------------------------------------------------------
#
# Today's behaviour, asserted EXACTLY (never assertGreater). t1243_3 rewrites the
# indexing scheme and t1243_11 adds block moves; both MUST consciously edit this
# table. **A silent pass after such a rewrite is a bug in the table, not a
# passing test.** `writes` counts reload_and_save_board_fields calls (a file can
# be written twice in one action); `changed` is the byte differ's exact set --
# the two disagree by design, because Task.save() does not bump updated_at and an
# unchanged-value write is byte-identical.
FLIP_TABLE = {
    "lateral_canonical": {
        "writes": 1,
        "changed": {"aitasks/t9003_fixture.md"},
        "state": {1: ("c0", 10), 2: ("c0", 20), 3: ("c1", 30),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "lateral_gapped": {
        "writes": 3,
        "changed": {"aitasks/t9001_fixture.md", "aitasks/t9002_fixture.md",
                    "aitasks/t9003_fixture.md"},
        "state": {1: ("c0", 10), 2: ("c0", 20), 3: ("c1", 30),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "vertical_swap": {
        "writes": 2,
        "changed": {"aitasks/t9002_fixture.md", "aitasks/t9003_fixture.md"},
        "state": {1: ("c0", 10), 2: ("c0", 30), 3: ("c0", 20),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "extreme_top": {
        "writes": 4,
        "changed": {"aitasks/t9001_fixture.md", "aitasks/t9002_fixture.md",
                    "aitasks/t9003_fixture.md"},
        "state": {1: ("c0", 20), 2: ("c0", 30), 3: ("c0", 10),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "extreme_bottom": {
        "writes": 4,
        "changed": {"aitasks/t9001_fixture.md", "aitasks/t9002_fixture.md",
                    "aitasks/t9003_fixture.md"},
        "state": {1: ("c0", 30), 2: ("c0", 10), 3: ("c0", 20),
                  4: ("c1", 10), 5: ("c1", 20), 6: ("c2", 10)},
    },
    "shift_column": {
        "writes": 0,
        "changed": {"aitasks/metadata/board_config.json"},
        "state": {1: ("c0", 10), 2: ("c0", 20), 3: ("c0", 30),
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
        result = run_child(tree, ipc, {
            "mode": "scenario",
            "focus": fixture_name(spec["focus"]),
            "key": spec["key"],
            "mutate": mutate,
            "size": [200, 60],
        }, tag=name)
        after = snapshot(tree)
        return tree, spec, result, diff_snapshots(before, after)

    def _assert_frozen(self, name, tree, spec, result, delta):
        expect = FLIP_TABLE[name]

        # The fixture actually loaded — a phantom-stub drop would otherwise make
        # every assertion below pass vacuously.
        self.assertEqual(result["loaded"], sorted(fixture_name(i) for i, _, _ in spec["cards"]))
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


class HarnessDiscriminationTests(_ScenarioBase):
    """Prove the oracle can fail — a passing test pins nothing until it does."""

    def test_flip_table_rejects_a_mutated_board(self):
        name = "lateral_gapped"
        tree, spec, result, delta = self._run_scenario(name, mutate="skip_normalize")
        expect = FLIP_TABLE[name]
        observed = (result["writes_total"], delta["changed"])
        self.assertNotEqual(
            observed, (expect["writes"], expect["changed"]),
            "no-op'ing normalize_indices must break the frozen record; if this "
            "passes, the flip table is not actually pinning behaviour",
        )
        with self.assertRaises(AssertionError):
            self._assert_frozen(name, tree, spec, result, delta)


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

    Lateral moves the BOTTOM card of c0: `move_task_col` appends at
    max_idx + 10, so only a bottom-of-column card returns to its exact slot
    after right-then-left. Vertical moves a mid-column card, where swap_tasks is
    symmetric.
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
