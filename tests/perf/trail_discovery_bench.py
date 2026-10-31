"""trail_discovery_bench.py - cold/warm timing of `discover_trails` (t2173_1).

Times `trail_discovery.discover_trails()` against THIS repo's task tree in three
phases, each with a count of the `artifact get` subprocesses it spawned:

    no-cache  AIT_TRAIL_CACHE=0 — the uncached baseline
    cold      a fresh, empty AIT_TRAIL_CACHE_DIR (populates it)
    warm      the same dir again, median of --reps runs

and then checks that all three phases discovered the same thing per handle
(owner id, archived, folded, name, load error, document) — the post-phase
"cached == uncached on the real repo" differential. Exits 1 if they differ.

The cache dir is a temp dir, so the checkout's own `.aitask-cache/` is never
touched. Real `artifact get` subprocesses run in the no-cache and cold phases.

Usage (from the repo root):
    python3 tests/perf/trail_discovery_bench.py [--reps 7]

Manual and never collected (not `test_*`-named).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import trail_discovery as td  # noqa: E402

_REAL_RUN = subprocess.run
_SPAWNS = {"get": 0}


def _counting_run(cmd, *args, **kwargs):
    if len(cmd) > 1 and cmd[1] == "get":
        _SPAWNS["get"] += 1
    return _REAL_RUN(cmd, *args, **kwargs)


def _summary(infos):
    return {i.handle: (i.owner_id, i.owner_archived, i.owner_folded, i.name,
                       i.load_error, json.dumps(i.doc, sort_keys=True))
            for i in infos}


def _timed_scan():
    _SPAWNS["get"] = 0
    start = time.perf_counter()
    infos, unreadable = td.discover_trails()
    elapsed = time.perf_counter() - start
    return elapsed, _SPAWNS["get"], _summary(infos), unreadable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reps", type=int, default=7,
                        help="warm repetitions (median reported)")
    args = parser.parse_args(argv)
    os.chdir(REPO_ROOT)
    subprocess.run = _counting_run

    with tempfile.TemporaryDirectory(prefix="trail_bench_") as cache:
        os.environ["AIT_TRAIL_CACHE"] = "0"
        base_t, base_gets, base, base_unreadable = _timed_scan()
        os.environ.pop("AIT_TRAIL_CACHE")
        os.environ["AIT_TRAIL_CACHE_DIR"] = cache
        cold_t, cold_gets, cold, _ = _timed_scan()
        warm = [_timed_scan() for _ in range(max(1, args.reps))]

    warm_t = statistics.median(w[0] for w in warm)
    warm_gets = max(w[1] for w in warm)
    print(f"trails discovered: {len(base)}   unreadable: {len(base_unreadable)}")
    print(f"{'phase':<10} {'seconds':>9} {'get spawns':>11}")
    print(f"{'no-cache':<10} {base_t:>9.3f} {base_gets:>11}")
    print(f"{'cold':<10} {cold_t:>9.3f} {cold_gets:>11}")
    print(f"{'warm':<10} {warm_t:>9.3f} {warm_gets:>11}   "
          f"(median of {len(warm)}; min {min(w[0] for w in warm):.3f}, "
          f"max {max(w[0] for w in warm):.3f})")

    mismatched = sorted(
        h for h in set(base) | set(cold)
        | {h for w in warm for h in w[2]}
        if not (base.get(h) == cold.get(h)
                and all(w[2].get(h) == base.get(h) for w in warm)))
    if mismatched:
        print(f"DIFFERENTIAL: FAIL — {len(mismatched)} handle(s) differ: "
              + ", ".join(mismatched))
        return 1
    print(f"DIFFERENTIAL: PASS — uncached == cold == warm for all "
          f"{len(base)} handle(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
