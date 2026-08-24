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
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
STATS_DATA_PATH = PROJECT_DIR / ".aitask-scripts" / "lib" / "stats_data.py"

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


def _task(frontmatter: str, *ledger_markers: str, body: str = "Body.") -> str:
    # `body` is a keyword so every existing call keeps the default; the backlog
    # checks need real prose because the retro-classifier fires on body headings.
    fm = f"---\n{frontmatter}\n---\n\n{body}\n"
    return fm + _ledger(*ledger_markers) if ledger_markers else fm


# --- D-1 resolver ---------------------------------------------------------

def _check_resolve_completion_date() -> None:
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


def _check_collect_inflight(tmp: Path) -> None:
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

def _check_phase_timings(tmp: Path) -> None:
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


# --- backlog level / net flow (t1544_3) -----------------------------------

# Fixture clock: 2026-06-29 is a MONDAY, so with week_start_dow=1 it is also the
# start of the current week. Week ends: off0 = 07-05, off1 = 06-28, off2 = 06-21,
# off3 = 06-14. 2026-07-01 is therefore a SAME-WEEK future date (offset 0, but
# later than today) — the only shape that discriminates the date guard from a
# `week_offset_for(...) < 0` guard.
_TODAY = date(2026, 6, 29)
_DOW = 1


def _check_backlog_levels() -> None:
    L = sd.backlog_levels

    # The pre-horizon contract: out_offsets selects OUTPUT COLUMNS ONLY. An
    # arrival far outside the window must still be counted as open inside it.
    lv = L(Counter({("type:bug", 40): 1}), Counter(), [3, 2, 1, 0])
    assert_eq("pre-horizon arrival is open at the oldest rendered week", 1,
              lv[("type:bug", 3)])
    assert_eq("pre-horizon arrival is still open now", 1, lv[("type:bug", 0)])

    # A departure clears the level from its own week onward, not before it.
    lv = L(Counter({("type:bug", 3): 1}), Counter({("type:bug", 1): 1}), [3, 2, 1, 0])
    assert_eq("open before the departure week (3)", 1, lv[("type:bug", 3)])
    assert_eq("open before the departure week (2)", 1, lv[("type:bug", 2)])
    assert_eq("closed in the departure week", 0, lv[("type:bug", 1)])
    assert_eq("still closed after", 0, lv[("type:bug", 0)])

    # The clamp is not silent: one tally per clamped OUTPUT CELL.
    ex: Counter = Counter()
    lv = L(Counter(), Counter({("type:bug", 2): 1}), [3, 2, 1, 0], excluded=ex)
    assert_eq("negative level clamps to 0", 0, lv[("type:bug", 2)])
    assert_eq("negative level is counted, not absorbed", 3, ex["negative_level"])

    # Generic over the first key element — the scope split reuses it verbatim.
    lv = L(Counter({("child", 1): 2}), Counter(), [1, 0])
    assert_eq("works on the scope axis too", 2, lv[("child", 0)])

    assert_eq("horizon offsets are oldest-first", [7, 6, 5, 4, 3, 2, 1, 0],
              sd.backlog_week_offsets(8))
    assert_eq("week end at offset 0", date(2026, 7, 5),
              sd.week_end_for_offset(_TODAY, _DOW, 0))
    assert_eq("week end at offset 3", date(2026, 6, 14),
              sd.week_end_for_offset(_TODAY, _DOW, 3))


def _seed_backlog_tree(tmp: Path) -> None:
    """Fixture corpus for _check_backlog. Each task's issue_type is unique where
    it has to act as a discriminator, so an exclusion that silently failed shows
    up as a non-zero count under its own category key."""
    # --- live, included
    _write(tmp, "t200_open.md", _task(
        "status: Ready\nissue_type: feature\ncreated_at: 2026-06-22 09:00"))
    _write(tmp, "t200/t200_1_child.md", _task(
        "status: Ready\nissue_type: feature\ncreated_at: 2026-06-22 09:00"))
    # Kind derivable ONLY from the body — proves the prose reaches the classifier.
    _write(tmp, "t202_prose.md", _task(
        "status: Ready\nissue_type: feature\ncreated_at: 2026-06-22 09:00",
        body="## Upstream defect\n\nA pre-existing bug elsewhere."))
    # review_approved pass + no completed_at: resolve_completion_date would date
    # this weeks ago; the one clock (parse_completed_date) must leave it OPEN.
    _write(tmp, "t204_review_marker.md", _task(
        "status: Ready\nissue_type: refactor\ncreated_at: 2026-06-22 09:00",
        _marker("review_approved", "pass", "2026-06-15T10:00:00Z")))
    # Live Done, no completed_at -> departs via the updated_at fallback.
    _write(tmp, "t206_live_done.md", _task(
        "status: Done\nissue_type: test\ncreated_at: 2026-06-15 09:00"
        "\nupdated_at: 2026-06-22 09:00"))
    # Pre-horizon arrival, still open.
    _write(tmp, "t214_ancient.md", _task(
        "status: Ready\nissue_type: documentation\ncreated_at: 2025-09-15 09:00"))

    # --- live, excluded (each with a discriminating issue_type)
    _write(tmp, "t203_no_created.md", _task(
        "status: Ready\nissue_type: feature"))
    _write(tmp, "t208_folded.md", _task(
        "status: Folded\nissue_type: feature\ncreated_at: 2026-06-22 09:00"))
    _write(tmp, "t209_folded_into.md", _task(
        "status: Ready\nissue_type: feature\ncreated_at: 2026-06-22 09:00"
        "\nfolded_into: 200"))
    # Bogus followup_kind: must be EXCLUDED, not merely tallied. It is given a
    # departure too, so a tally-without-exclusion shows up on BOTH flows.
    _write(tmp, "t210_bogus_kind.md", _task(
        "status: Done\nissue_type: bug\ncreated_at: 2026-06-22 09:00"
        "\ncompleted_at: 2026-06-22 09:00\nfollowup_kind: not_a_real_kind"))
    # Same-week future created_at -> phantom arrival if guarded by offset.
    _write(tmp, "t211_future_created.md", _task(
        "status: Ready\nissue_type: chore\ncreated_at: 2026-07-01 09:00"))
    # Same-week future completed_at -> premature departure if guarded by offset.
    _write(tmp, "t212_future_completed.md", _task(
        "status: Ready\nissue_type: style\ncreated_at: 2026-06-22 09:00"
        "\ncompleted_at: 2026-07-01 09:00"))
    # Draft under new/ -> pruned by the iterator, never seen at all.
    _write(tmp, "new/t213_draft.md", _task(
        "status: Ready\nissue_type: performance\ncreated_at: 2026-06-22 09:00"))

    # --- archived
    _write(tmp, "archived/t201_completed.md", _task(
        "status: Done\nissue_type: feature\ncreated_at: 2026-06-08 09:00"
        "\ncompleted_at: 2026-06-22 09:00"))
    # completed_at (06-22, offset 1) and the ledger stamp (06-15, offset 2)
    # disagree: the backlog clock must follow completed_at.
    _write(tmp, "archived/t205_ledger.md", _task(
        "status: Done\nissue_type: enhancement\ncreated_at: 2026-06-08 09:00"
        "\ncompleted_at: 2026-06-22 09:00",
        _marker("merge_approved", "pass", "2026-06-15T10:00:00Z")))
    _write(tmp, "archived/t207_no_completed.md", _task(
        "status: Ready\nissue_type: feature\ncreated_at: 2026-06-08 09:00"))
    # Legacy archived files with NO parseable frontmatter — both real shapes
    # from the corpus (t20 has none at all; t21/t22 open with a pseudo-delimiter
    # that is not an exact `---`). These die at the archive loop's
    # `completed is None` short-circuit, so they are only ever reported if the
    # backlog booking happens BEFORE it — which is what makes them the fixture
    # that catches a later reordering.
    _write(tmp, "archived/t20_legacy_none.md",
           "there is already a skill for creating aitasks\n\nmore prose\n")
    _write(tmp, "archived/t21_legacy_pseudo.md",
           "--- effort:med pri:med\n\nsome prose\n\n---\n\ntrailing\n")


def _check_backlog(tmp: Path) -> None:
    _seed_backlog_tree(tmp)
    data = sd.collect_stats(_TODAY, _DOW, project_root=tmp)
    arr, dep = data.backlog_arrivals, data.backlog_departures

    # --- exclusions: every reason, exactly once
    assert_eq("every exclusion reason fires, with its expected count", {
        "no_frontmatter": 2,
        "no_created_at": 1,
        "folded": 2,
        "invalid_followup_kind": 1,
        "future_created_at": 1,
        "future_completed_at": 1,
        "archived_no_completed_at": 1,
    }, dict(data.backlog_excluded))
    # Both frontmatter-less shapes are reported, and neither reaches a flow —
    # pinned by the unchanged arrival/departure totals asserted below. This is
    # the assertion that fails if backlog booking is ever moved below the
    # archive loop's `completed is None` short-circuit.
    assert_eq("legacy frontmatter-less archived files are reported", 2,
              data.backlog_excluded["no_frontmatter"])

    # --- an excluded task contributes to NEITHER flow. The tally alone passes
    # under the defect this guards (resolve_category counts, then falls through
    # to a real category), so both halves are asserted.
    assert_eq("bogus followup_kind: no arrival", 0, arr[("type:bug", 1)])
    assert_eq("bogus followup_kind: no departure", 0, dep[("type:bug", 1)])
    assert_eq("same-week future created_at: no phantom arrival", 0,
              sum(v for (c, _o), v in arr.items() if c == "type:chore"))
    assert_eq("same-week future completed_at: no arrival", 0,
              sum(v for (c, _o), v in arr.items() if c == "type:style"))
    assert_eq("same-week future completed_at: no premature departure", 0,
              sum(v for (c, _o), v in dep.items() if c == "type:style"))
    assert_eq("draft under new/ is never seen", 0,
              sum(v for (c, _o), v in arr.items() if c == "type:performance"))

    # --- arrivals
    assert_eq("parent + child arrive in their created week", 2,
              arr[("type:feature", 1)])
    assert_eq("archived task arrives in its own created week", 1,
              arr[("type:feature", 3)])
    assert_eq("kind derived from body prose alone", 1,
              arr[("kind:upstream_defect", 1)])
    assert_eq("pre-horizon arrival is recorded unclamped", 1,
              arr[("type:documentation", 41)])
    assert_eq("total arrivals", 8, sum(arr.values()))

    # --- departures: one clock, one rule
    assert_eq("review_approved marker does not depart a live task", 0,
              sum(v for (c, _o), v in dep.items() if c == "type:refactor"))
    assert_eq("live Done departs via the updated_at fallback", 1,
              dep[("type:test", 1)])
    assert_eq("ledger-vs-completed_at: departs in the completed_at week", 1,
              dep[("type:enhancement", 1)])
    assert_eq("ledger-vs-completed_at: NOT the ledger week", 0,
              dep[("type:enhancement", 2)])
    assert_eq("total departures", 3, sum(dep.values()))

    # --- derived level and the scope split
    offsets = sd.backlog_week_offsets(4)
    levels = sd.backlog_levels(arr, dep, offsets)
    total_open = sum(v for (_c, o), v in levels.items() if o == 0)
    assert_eq("TOTAL OPEN now", 5, total_open)

    scope = sd.backlog_levels(data.backlog_scope_arrivals,
                              data.backlog_scope_departures, offsets)
    assert_eq("open parents now", 4, scope[("parent", 0)])
    assert_eq("open children now", 1, scope[("child", 0)])
    assert_eq("scope split sums to TOTAL OPEN", total_open,
              scope[("parent", 0)] + scope[("child", 0)])

    # --- reconciliation identity 1. `folded` is itself an exclusion reason, so
    # it is NOT subtracted again; `negative_level` counts cells, not tasks, and
    # is excluded from the sum.
    live_files = sum(1 for _ in sd.iter_active_markdown_files(project_root=tmp))
    assert_eq("live files seen (new/ pruned)", 12, live_files)
    # backlog_excluded is a corpus-wide tally: it is aggregated over BOTH trees
    # and carries no per-tree split, so the live share has to be named for this
    # fixture. Here the archived tree contributes exactly `no_frontmatter` (the
    # two legacy files) and `archived_no_completed_at`; `negative_level` counts
    # output cells rather than tasks and is never a task exclusion at all.
    not_live_excluded = ("no_frontmatter", "archived_no_completed_at", "negative_level")
    live_excluded = sum(n for r, n in data.backlog_excluded.items()
                        if r not in not_live_excluded)
    live_departed = 1
    assert_eq("identity 1: open == live - excluded - departed",
              total_open, live_files - live_excluded - live_departed)

    # --- reconciliation identity 2. The third term (archived tasks excluded
    # before their departure was recorded) is 0 here: the only archived
    # exclusion, t207, has no resolvable completion date either, so it is
    # absent from total_tasks as well.
    assert_eq("identity 2: departures == total_tasks + live departed",
              sum(dep.values()), data.total_tasks + live_departed)


def _check_backlog_merge(tmp: Path) -> None:
    """Multi-project aggregation is plain additive Counter.update — the third
    lockstep site. Missing it is invisible in single-project use."""
    a, b = tmp / "a", tmp / "b"
    _write(a, "t300_one.md", _task(
        "status: Ready\nissue_type: feature\ncreated_at: 2026-06-22 09:00"))
    _write(b, "t400_two.md", _task(
        "status: Ready\nissue_type: feature\ncreated_at: 2026-06-22 09:00"))
    _write(b, "t401_other.md", _task(
        "status: Ready\nissue_type: bug\ncreated_at: 2026-06-15 09:00"))
    _write(b, "t402_folded.md", _task(
        "status: Folded\nissue_type: bug\ncreated_at: 2026-06-15 09:00"))

    da = sd.collect_stats(_TODAY, _DOW, project_root=a)
    db = sd.collect_stats(_TODAY, _DOW, project_root=b)
    merged = sd.merge_stats_data([da, db])

    assert_eq("merged arrivals add on a shared key", 2,
              merged.backlog_arrivals[("type:feature", 1)])
    assert_eq("merged arrivals keep a project-unique key", 1,
              merged.backlog_arrivals[("type:bug", 2)])
    assert_eq("merged scope arrivals add", 3,
              sum(merged.backlog_scope_arrivals.values()))
    assert_eq("merged exclusions add", 1, merged.backlog_excluded["folded"])
    assert_eq("merge is additive, not a replacement", 3,
              sum(merged.backlog_arrivals.values()))
    # A stock derived from summed flows equals the sum of the stocks — the
    # property that lets the merge stay a plain Counter.update.
    offs = sd.backlog_week_offsets(4)
    lv_m = sd.backlog_levels(merged.backlog_arrivals, merged.backlog_departures, offs)
    lv_a = sd.backlog_levels(da.backlog_arrivals, da.backlog_departures, offs)
    lv_b = sd.backlog_levels(db.backlog_arrivals, db.backlog_departures, offs)
    assert_eq("merged level == sum of per-project levels",
              sum(v for (_c, o), v in lv_a.items() if o == 0)
              + sum(v for (_c, o), v in lv_b.items() if o == 0),
              sum(v for (_c, o), v in lv_m.items() if o == 0))


def _check_with_backlog_off(tmp: Path) -> None:
    """The flag is purely SUBTRACTIVE: it removes the classification work and
    nothing else. It cannot remove a live-tree walk — collect_inflight runs
    regardless — so the measurable contract is the resolve_category call count."""
    _seed_backlog_tree(tmp)

    real = sd.resolve_category
    calls = {"n": 0}

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    sd.resolve_category = counting
    try:
        calls["n"] = 0
        off = sd.collect_stats(_TODAY, _DOW, project_root=tmp, with_backlog=False)
        off_calls = calls["n"]
        calls["n"] = 0
        on = sd.collect_stats(_TODAY, _DOW, project_root=tmp, with_backlog=True)
        on_calls = calls["n"]
    finally:
        sd.resolve_category = real

    assert_eq("with_backlog=False classifies nothing", 0, off_calls)
    assert_true("with_backlog=True does classify", on_calls > 0)
    assert_eq("arrivals empty when off", 0, len(off.backlog_arrivals))
    assert_eq("departures empty when off", 0, len(off.backlog_departures))
    assert_eq("scope arrivals empty when off", 0, len(off.backlog_scope_arrivals))
    assert_eq("scope departures empty when off", 0, len(off.backlog_scope_departures))
    assert_eq("exclusions empty when off", 0, len(off.backlog_excluded))

    # Purely subtractive: every pre-existing field is identical either way.
    assert_eq("total_tasks unaffected", on.total_tasks, off.total_tasks)
    assert_eq("daily_counts unaffected", on.daily_counts, off.daily_counts)
    assert_eq("inflight unaffected", on.inflight.task_ids, off.inflight.task_ids)
    # csv_rows gained two columns in t1544_4. The PRE-EXISTING ten are still
    # identical either way -- that is what "purely subtractive" claims -- and so
    # is created_at, which needs no classification. Only `category` is
    # conditional, because populating it would mean calling resolve_category,
    # which is exactly the work this flag exists to skip. Both directions are
    # pinned below so the semantic is a contract, not an accident.
    assert_eq("csv_rows unaffected (pre-existing columns)",
              [r[:11] for r in on.csv_rows], [r[:11] for r in off.csv_rows])
    assert_true("csv_rows category empty when off", all(r[11] == "" for r in off.csv_rows))
    assert_true("csv_rows category populated when on", all(r[11] for r in on.csv_rows))
    assert_true("csv_rows non-empty (the assertions above are not vacuous)", len(on.csv_rows) > 0)
    assert_eq("phase_timings unaffected", on.phase_timings.implement_hours,
              off.phase_timings.implement_hours)


def _check_format_duration() -> None:
    assert_eq("minutes under 1h", "30m", sd.format_duration(0.5))
    assert_eq("hours under a day", "2.0h", sd.format_duration(2.0))
    assert_eq("days for >=24h", "1.5d", sd.format_duration(36.0))


def main() -> int:
    import tempfile
    _check_resolve_completion_date()
    _check_format_duration()
    with tempfile.TemporaryDirectory(prefix="stats_inflight_") as t:
        _check_collect_inflight(Path(t))
    with tempfile.TemporaryDirectory(prefix="stats_timing_") as t:
        _check_phase_timings(Path(t))
    _check_backlog_levels()
    with tempfile.TemporaryDirectory(prefix="stats_backlog_") as t:
        _check_backlog(Path(t))
    with tempfile.TemporaryDirectory(prefix="stats_backlog_merge_") as t:
        _check_backlog_merge(Path(t))
    with tempfile.TemporaryDirectory(prefix="stats_backlog_off_") as t:
        _check_with_backlog_off(Path(t))

    print("")
    print("==========================")
    print(f"Results: {PASS}/{TOTAL} passed, {FAIL} failed")
    print("==========================")
    return 1 if FAIL else 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211).

    ``assert_eq`` tallies into ``FAIL`` instead of raising, so the assertion is
    on ``main()``'s return code; the per-check detail is printed to stdout.
    ``main()`` owns its own tempdir setup, so the wrapper delegates rather than
    duplicating the driver.
    """

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    raise SystemExit(main())
