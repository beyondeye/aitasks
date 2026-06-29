#!/usr/bin/env python3
"""Tests for multi-stage completion stats (t635_20).

Covers the ledger-aware completion-date resolver (pass-only, resolver-only),
the in-flight 'completed, awaiting gates' classifier, and the time-in-phase
spans (ledger timestamps only, per-span N). Uses the `project_root` parameter
so no module-level globals are patched.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
STATS_DATA_PATH = PROJECT_DIR / ".aitask-scripts" / "stats" / "stats_data.py"

spec = importlib.util.spec_from_file_location("stats_data", STATS_DATA_PATH)
assert spec is not None and spec.loader is not None
sd = importlib.util.module_from_spec(spec)
sys.modules["stats_data"] = sd
spec.loader.exec_module(sd)


PASS = 0
FAIL = 0
TOTAL = 0


def assert_eq(desc: str, expected, actual) -> None:
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if expected == actual:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {desc} (expected {expected!r}, got {actual!r})")


def assert_true(desc: str, actual) -> None:
    assert_eq(desc, True, bool(actual))


# --- fixture builders -----------------------------------------------------

def _ledger(*lines: str) -> str:
    body = "\n\n".join(lines)
    return f"\n## Gate Runs\n\n{body}\n"


def _marker(gate: str, status: str, ts: str, icon: str = "✅") -> str:
    return f"> **{icon} gate:{gate}** run={ts} status={status} attempt=1 type=human"


def _task(frontmatter: str, *ledger_markers: str) -> str:
    fm = f"---\n{frontmatter}\n---\n\nBody.\n"
    return fm + _ledger(*ledger_markers) if ledger_markers else fm


# --- D-1 resolver ---------------------------------------------------------

def test_resolve_completion_date() -> None:
    R = sd.resolve_completion_date

    # merge_approved present & pass -> dates by merge.
    both = _task(
        "status: Done\ncompleted_at: 2026-06-28 09:00",
        _marker("review_approved", "pass", "2026-06-20T10:00:00Z"),
        _marker("merge_approved", "pass", "2026-06-25T10:00:00Z"),
    )
    assert_eq("merge wins over review", date(2026, 6, 25),
              R(both, sd.parse_frontmatter(both)))

    # review-only (no merge) -> dates by review (current-branch / fast profile).
    review_only = _task(
        "status: Done\ncompleted_at: 2026-06-28 09:00",
        _marker("review_approved", "pass", "2026-06-20T10:00:00Z"),
    )
    assert_eq("review-only dates by review", date(2026, 6, 20),
              R(review_only, sd.parse_frontmatter(review_only)))

    # merge marker present but FAIL -> skip it, fall to review pass.
    merge_failed = _task(
        "status: Done\ncompleted_at: 2026-06-28 09:00",
        _marker("review_approved", "pass", "2026-06-20T10:00:00Z"),
        _marker("merge_approved", "fail", "2026-06-25T10:00:00Z", icon="❌"),
    )
    assert_eq("failed merge skipped, dates by review", date(2026, 6, 20),
              R(merge_failed, sd.parse_frontmatter(merge_failed)))

    # merge fail -> pass retry (last-wins pass) -> dates by merge.
    merge_retry = _task(
        "status: Done\ncompleted_at: 2026-06-28 09:00",
        _marker("review_approved", "pass", "2026-06-20T10:00:00Z"),
        _marker("merge_approved", "fail", "2026-06-24T10:00:00Z", icon="❌"),
        _marker("merge_approved", "pass", "2026-06-26T10:00:00Z"),
    )
    assert_eq("merge retry pass dates by final pass", date(2026, 6, 26),
              R(merge_retry, sd.parse_frontmatter(merge_retry)))

    # no markers -> completed_at fallback (back-compat).
    legacy = _task("status: Done\ncompleted_at: 2026-03-01 10:00")
    assert_eq("no ledger -> completed_at", date(2026, 3, 1),
              R(legacy, sd.parse_frontmatter(legacy)))

    # Done + no completed_at -> updated_at fallback (parity with parse_completed_date).
    done_updated = _task("status: Done\nupdated_at: 2026-02-15 08:00")
    assert_eq("no completed_at -> updated_at", date(2026, 2, 15),
              R(done_updated, sd.parse_frontmatter(done_updated)))

    # lingering unrelated fail (build_verified) but review pass -> still dated by review.
    lingering = _task(
        "status: Done\ncompleted_at: 2026-06-28 09:00",
        _marker("review_approved", "pass", "2026-06-20T10:00:00Z"),
        _marker("build_verified", "fail", "2026-06-20T09:00:00Z", icon="❌"),
    )
    assert_eq("lingering unrelated fail still ledger-dated", date(2026, 6, 20),
              R(lingering, sd.parse_frontmatter(lingering)))


# --- D-2 in-flight classifier ---------------------------------------------

def _write(base: Path, relpath: str, content: str) -> None:
    p = base / "aitasks" / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_collect_inflight(tmp: Path) -> None:
    # In-flight: review_approved pass + declared gate not yet pass -> BLOCKED.
    _write(tmp, "t100_inflight.md", _task(
        "status: Implementing\ngates: [docs_updated]",
        _marker("review_approved", "pass", "2026-06-22T10:00:00Z"),
    ))
    # Mid-implementation: only plan_approved -> excluded (not completed).
    _write(tmp, "t101_midimpl.md", _task(
        "status: Implementing\ngates: [docs_updated]",
        _marker("plan_approved", "pass", "2026-06-22T10:00:00Z"),
    ))
    # Reviewed but all declared gates pass -> would just archive -> excluded.
    _write(tmp, "t102_ready.md", _task(
        "status: Implementing\ngates: [docs_updated]",
        _marker("review_approved", "pass", "2026-06-22T10:00:00Z"),
        _marker("docs_updated", "pass", "2026-06-22T11:00:00Z"),
    ))
    # Archived deferred task -> must NOT count (archived/ is pruned).
    _write(tmp, "archived/t99_archived.md", _task(
        "status: Done\ngates: [docs_updated]\ncompleted_at: 2026-06-22 12:00",
        _marker("review_approved", "pass", "2026-06-22T10:00:00Z"),
    ))

    data = sd.collect_inflight(date(2026, 6, 29), 1, project_root=tmp)
    assert_eq("only the genuinely in-flight task counts", 1, data.count)
    assert_eq("in-flight task id captured", ["t100_inflight"], data.task_ids)
    assert_eq("in-flight dated by review_approved", 1,
              data.daily_counts.get(date(2026, 6, 22), 0))


# --- D-3 phase timings (via collect_stats over archived) -------------------

def test_phase_timings(tmp: Path) -> None:
    arch = "archived"
    # Full pipeline: implement 2h, review->merge 24h.
    _write(tmp, f"{arch}/t1_full.md", _task(
        "status: Done\ncompleted_at: 2026-06-26 10:00",
        _marker("plan_approved", "pass", "2026-06-25T10:00:00Z"),
        _marker("review_approved", "pass", "2026-06-25T12:00:00Z"),
        _marker("merge_approved", "pass", "2026-06-26T12:00:00Z"),
    ))
    # Review-only (current-branch): implement 1h, NO review->merge sample.
    _write(tmp, f"{arch}/t2_reviewonly.md", _task(
        "status: Done\ncompleted_at: 2026-06-25 11:00",
        _marker("plan_approved", "pass", "2026-06-25T10:00:00Z"),
        _marker("review_approved", "pass", "2026-06-25T11:00:00Z"),
    ))
    # No ledger -> contributes no span sample, dated by completed_at (back-compat).
    _write(tmp, f"{arch}/t3_nogate.md", _task(
        "status: Done\ncompleted_at: 2026-06-24 09:00"))

    data = sd.collect_stats(today=date(2026, 6, 29), week_start_dow=1, project_root=tmp)
    pt = data.phase_timings
    assert_eq("implement span sample count", 2, len(pt.implement_hours))
    assert_eq("review->merge span sample count (review-only excluded)", 1,
              len(pt.review_merge_hours))
    assert_true("implement spans are 1h and 2h",
                sorted(round(h, 3) for h in pt.implement_hours) == [1.0, 2.0])
    assert_eq("review->merge span is 24h", 24.0, round(pt.review_merge_hours[0], 3))
    assert_eq("no archival date leaks into a span (only 1 r->m sample)", 1,
              len(pt.review_merge_hours))

    # Back-compat: all three archived tasks counted; no-ledger dated by completed_at.
    assert_eq("all archived tasks counted", 3, data.total_tasks)
    assert_eq("no-ledger task buckets on completed_at", 1,
              data.daily_counts.get(date(2026, 6, 24), 0))
    # Ledger task dated by merge (2026-06-26), not archival completed_at (also 26).
    assert_eq("full-pipeline task dated by merge", 1,
              data.daily_counts.get(date(2026, 6, 26), 0))
    assert_eq("inflight empty for archived-only fixture", 0, data.inflight.count)


def test_format_duration() -> None:
    assert_eq("minutes under 1h", "30m", sd.format_duration(0.5))
    assert_eq("hours under a day", "2.0h", sd.format_duration(2.0))
    assert_eq("days for >=24h", "1.5d", sd.format_duration(36.0))


def main() -> int:
    import tempfile
    test_resolve_completion_date()
    test_format_duration()
    with tempfile.TemporaryDirectory(prefix="stats_inflight_") as t:
        test_collect_inflight(Path(t))
    with tempfile.TemporaryDirectory(prefix="stats_timing_") as t:
        test_phase_timings(Path(t))

    print("")
    print("==========================")
    print(f"Results: {PASS}/{TOTAL} passed, {FAIL} failed")
    print("==========================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
