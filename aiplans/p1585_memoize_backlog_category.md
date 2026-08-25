---
Task: t1585_memoize_backlog_category.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1585 — Memoize the backlog category so the archived tree is classified once

## Context

`ait stats` classifies the archived task tree **twice** when `with_backlog=True`.
`stats_data._accumulate_backlog` resolves each task's category at the end of its
guard chain (`.aitask-scripts/lib/stats_data.py:1206`), and t1544_4's `csv_rows`
producer calls `resolve_category` again for the same file
(`.aitask-scripts/lib/stats_data.py:1401`) to fill the `category` column that
only materializes with `--csv`.

Measured on this box against the real corpus (median of 5, warm):

| | |
|---|---|
| `collect_stats(with_backlog=True)` | **328.5 ms** |
| `collect_stats(with_backlog=False)` | 169.3 ms |
| `resolve_category` calls | **4178** over **2313** distinct files |
| files classified **twice** | **1865** (== exactly the 1865 csv rows) |
| csv rows with an empty `category` cell | 0 |

So the duplicate pass is ~45% of all classification calls and is paid on every
`ait stats` and every stats-TUI load. This task is the risk-mitigation follow-up
t1544_4 spawned for exactly that (`anchor: 1544`, `followup_kind: risk_mitigation`).

**Goal:** classify each file once — have the collection path expose the category
it already resolves, and have the row producer consume it.

## Two constraints that shape the design

1. **`_accumulate_backlog` returns early on all seven guards** and resolves the
   category only after them. A task can be *excluded from the backlog series*
   yet still *produce a csv row*, so a naive memo would ship an empty cell. The
   case is production-reachable and verified live: a `folded` task carrying a
   `merge_approved` ledger stamp — `resolve_completion_date` dates it
   (→ csv row) while the `folded` guard excludes it (→ no memo entry):

   ```
   status: Folded, folded_into: 200, no completed_at, merge_approved pass 2026-06-22
   resolve_completion_date -> 2026-06-22    parse_completed_date -> None
   ```

   0 such tasks exist in the corpus today (hence "empty category cells: 0"), so
   **the real corpus cannot exercise the fallback** — a fixture must.

   → Design choice: **fall back to a direct call on a memo miss** rather than
   hoisting the resolution above the guards. Hoisting would classify
   `no_frontmatter` / `no_created_at` files that are never classified today,
   adding work in the name of removing it.

2. **The `with_backlog=False` contract must survive unedited.**
   `tests/test_stats_multistage.py::_check_with_backlog_off` asserts
   `resolve_category` is called **exactly zero** times under
   `collect_stats(with_backlog=False)`, and that the `category` cell is empty
   in that mode and populated when on. Both must keep passing **without editing
   the check**. The fallback therefore lives strictly inside the `with_backlog`
   branch.

## Implementation

All production changes are in `.aitask-scripts/lib/stats_data.py`. Both touched
functions are module-private with exactly one call site each — no external
signature changes.

### 1. `_accumulate_backlog` returns the category it resolved

Change the signature to `-> Optional[str]` and:

- return `None` from **each** of the seven exclusion guards (they already
  `return`; make it `return None` explicitly for readability), and
- `return category` after the flows are booked:

```python
    category = resolve_category(frontmatter, body, filename, tally=None)
    scope = "child" if is_child_task(filename) else "parent"
    ...
    if departed is not None:
        ...
    return category
```

Extend the docstring with a short paragraph: the return value is the category
this call resolved, `None` on every exclusion, and a `None` **means "not
classified here", not "no category"** — the caller must fall back rather than
emit an empty cell.

### 2. `_book_backlog` forwards it

`.aitask-scripts/lib/stats_data.py:1309` — annotate `-> Optional[str]` and
`return _accumulate_backlog(...)`. `_observe_live` (live tree, no csv rows)
keeps ignoring the value; no change there.

### 3. The archive loop binds it per iteration

Replace, at `.aitask-scripts/lib/stats_data.py:1327`:

```python
        if with_backlog:
            _book_backlog(filename, frontmatter, body, archived=True)
```

with:

```python
        # The category this file's booking resolved, carried down to the csv
        # row below so the archived tree is classified ONCE (t1585). None means
        # "the booking excluded this file before classifying it" — the row
        # producer must fall back, not emit an empty cell.
        booked_category: Optional[str] = None
        if with_backlog:
            booked_category = _book_backlog(filename, frontmatter, body, archived=True)
```

A per-iteration local, not a dict keyed by filename: the value is produced and
consumed inside one iteration of the same loop, so a dict would only add
unbounded growth and a key-identity question for no benefit.

### 4. The csv row consumes it, with a fallback

Replace the inline conditional at `.aitask-scripts/lib/stats_data.py:1401`
(`resolve_category(frontmatter, body, filename) if with_backlog else ""`) with a
value computed just above the `csv_rows.append(...)`, next to the existing
`created = _parse_frontmatter_date(...)`:

```python
        if not with_backlog:
            category = ""
        elif booked_category is not None:
            category = booked_category
        else:
            # Reachable: this file was EXCLUDED from the backlog flows (e.g. a
            # `folded` task whose merge_approved stamp still dates it) so the
            # booking returned before classifying. It still gets a row, so
            # classify it directly rather than ship an empty cell (t1585).
            category = resolve_category(frontmatter, body, filename)
```

and pass `category` as the 12th element. Keep t1544_4's existing lockstep
comment about `aitask_stats.write_csv`'s header, updating the `category`
sentence to describe the memo + fallback instead of the second pass.

`resolve_category` never returns `""` (worst case `type:unknown`), so
`booked_category is not None` is a sound hit test — but the explicit `is not
None` is used rather than truthiness so that stays true by construction.

## Tests

`tests/test_stats_multistage.py` — add **one new check**, leaving
`_check_backlog` and `_check_with_backlog_off` **untouched**. (Seeding the
discriminating fixture into the shared `_seed_backlog_tree` would shift
`_check_backlog`'s `folded` tally and break its `identity 2: departures ==
total_tasks + live departed` assertion, whose third term is 0 only because no
such task exists in that fixture. A dedicated tree keeps both existing guards
at full strength.)

### `_check_category_single_pass(tmp)`

Fixture tree (own tempdir, registered in `main()` next to the other backlog
checks). **Each file's category is distinct**, so a value that reaches the wrong
row is caught by identity rather than by non-emptiness — all three verified
against the real resolver before planning:

| file | frontmatter | category | role |
|---|---|---|---|
| `archived/t500_normal.md` | Done, `issue_type: refactor`, **`created_at: 2026-06-08 09:00`**, `completed_at: 2026-06-22 09:00` | `type:refactor` | booked **and** csv row → the **memo-hit** case |
| `archived/t501_folded_stamped.md` | `status: Folded`, `folded_into: 200`, `issue_type: bug`, `created_at: 2026-06-08 09:00`, **no** `completed_at`, `merge_approved pass` marker | `type:bug` | excluded from the flows, still a csv row → the **memo-miss / fallback** case |
| `t502_live.md` | live Ready, `issue_type: chore`, **`created_at: 2026-06-22 09:00`** | `type:chore` | booked only, no csv row → the **live-tree** path |

Dates are chosen against `_TODAY = 2026-06-29` / `_DOW = 1`: `created_at`
2026-06-08 → arrival offset 3, 2026-06-22 → offset 1, `completed_at` 2026-06-22
→ departure offset 1.

Bodies stay the default `"Body."` so the retro-classifier does not fire and the
category really is the `type:` fallback shown above.

**Every frontmatter field above is load-bearing — the table is the exact fixture,
not an abbreviation.** `created_at` in particular is what routes a file *through*
the memo rather than around it, because `_accumulate_backlog`'s `no_created_at`
guard returns **before** classifying:

| t500 has `created_at`? | classified on **today's unfixed** code | what the check would prove |
|---|---|---|
| yes | **twice** | assertion 1 fails now, passes after the fix — a real guard |
| no | once (booking skipped → csv fallback) | **nothing**: the check passes against the unfixed code, and the memo-hit path it exists to cover is never taken |

Both rows measured, not reasoned. `t502_live.md` has the same dependency — drop
its `created_at` and it is excluded at the same guard, never appears in `seen`,
and never produces `type:chore`, so assertion 7 would cover nothing.

`iter_all_archived_markdown` yields loose parent files **`sorted()`**, so
`t500_normal.md` is processed before `t501_folded_stamped.md`. That order is
what makes the exact assertions catch a *stale-local* variant of the memo
(`if (c := _book_backlog(...)) is not None: booked_category = c`, i.e. the
variable declared outside the loop and only overwritten on a hit): under it
t501's row would inherit t500's `type:refactor`. Name that dependency in a test
comment so a later fixture rename does not silently retire the catch.

**Instrumentation ordering (load-bearing).** The check must not classify through
its own recorder — a single expected-value call made while the monkeypatch is
installed lands in the recorded list and fails assertions 2/3 despite correct
production behaviour. So:

```python
    real = sd.resolve_category            # saved BEFORE instrumenting
    seen: list[str] = []

    def recording(metadata, body, filename, tally=None):
        seen.append(filename)
        return real(metadata, body, filename, tally)

    sd.resolve_category = recording
    try:
        data = sd.collect_stats(_TODAY, _DOW, project_root=tmp, with_backlog=True)
    finally:
        sd.resolve_category = real        # restored before ANY assertion runs
```

Every expected value is then computed **after** restoration (or via the saved
`real`), never through `sd.resolve_category` while patched. The `try/finally`
also guarantees restoration if `collect_stats` raises, so a failure here cannot
poison the checks that run after it in `main()`.

Assertions, all evaluated after restoration:

1. **The single-pass invariant** — no filename appears more than once in `seen`
   (`[f for f, n in Counter(seen).items() if n > 1] == []`). This is the whole
   point of the task, stated as a property rather than a count.
2. **The memo hit really was a hit, and carried the *correct* value** — three
   assertions that are only jointly conclusive:
   - `data.backlog_arrivals[("type:refactor", 3)] == 1` and
     `data.backlog_departures[("type:refactor", 1)] == 1` — t500 was **booked**,
     i.e. it reached the classification at the end of `_accumulate_backlog`
     rather than returning at a guard;
   - t500's csv row exists and has `r[11] == "type:refactor"` — the row
     **consumed** a correct category;
   - `seen.count("t500_normal.md") == 1` — and it was classified **once**.

   Booked + rowed + one call ⇒ the row was served by `booked_category`; there is
   no other way to get all three. Any one of them alone is satisfiable by the
   fallback path. The exact-value half additionally proves the booking returned
   the *right* category rather than merely *a* category — a booking that
   returned, say, the `scope` string or a neighbouring iteration's value would
   still be non-empty.
3. **The fallback fires exactly once** — `seen.count("t501_folded_stamped.md") == 1`.
   Zero would mean an empty cell; two would mean the memo miss also
   double-classified.
4. **No silently-empty cell, with the right value** — t501's csv row has
   `r[11] == "type:bug"` (pinned as a literal *and* cross-checked against
   `real(fm, body, "t501_folded_stamped.md")` computed post-restoration), and
   every row's cell is non-empty.
5. **It really was a memo miss** — t501 contributed nothing to
   `backlog_arrivals` / `backlog_departures` and is tallied under
   `backlog_excluded["folded"]`. This is what makes assertions 3–4 a fallback
   test rather than an incidental pass.
6. **Row identity** — rows are located by their `task_id` column (`r[3]`), not
   by index, so the assertions survive a fixture addition.
7. **The live-tree path still books, and still classifies exactly once** —
   `seen.count("t502_live.md") == 1` and
   `data.backlog_arrivals[("type:chore", 1)] == 1`. t500/t501 are both
   *archived*, so without this assertion nothing in the check exercises
   `_observe_live` — the one caller that keeps **ignoring** `_book_backlog`'s
   new return value. It also pins that the live file produces no csv row
   (no row has `task_id == "t502_live"`).

### Post-phase (risk mitigations)

**`single_pass_invariant_guard`** — assertion 1 above is deliberately written as
a *property over the recorded call list* (no filename twice) rather than an
exact call count, so it keeps catching the regression when the fixture grows.
Pair it with the two-ended comment in production (§3 and §4) naming the
producer/consumer coupling, so a future edit that inserts a `continue` between
the booking and the row — or moves the booking below the `completed is None`
short-circuit — fails this check instead of silently restoring the second pass.

The distinct-category fixtures and the exact-value assertions (2 and 4) are the
second half of this guard: the invariant alone proves each file is classified
*once*, not that the one value lands on the *right* row. Together they cover
both failure modes of the coupling.

## Verification

- **Negative control, run FIRST.** Add `_check_category_single_pass` and run it
  against the **unmodified** `stats_data.py`. It must **FAIL** on assertion 1
  with `t500_normal.md` classified **twice** (measured: `{'t500_normal.md': 2,
  't501_folded_stamped.md': 1, 't502_live.md': 1}`). A new check that passes
  before the fix is guarding nothing — if it passes here, the fixture is wrong,
  not the production code. Only then apply the `stats_data.py` change and
  confirm it flips to green with `{'t500_normal.md': 1, …}`.
- Expected post-fix state of the fixture tree, for pinning the assertions
  (measured against current code, and unchanged by this task except for the
  call counts): arrivals `{('type:refactor', 3): 1, ('type:chore', 1): 1}`,
  departures `{('type:refactor', 1): 1}`, excluded `{'folded': 1}`, csv rows
  `[('t500_normal', 'type:refactor'), ('t501_folded_stamped', 'type:bug')]`.
- `bash tests/run_all_python_tests.sh --test-dir tests` — **read the LAST line
  only** (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); do not pipe without
  `pipefail`.
- `tests/test_stats_multistage.py::_check_with_backlog_off` passes **unedited**
  (both its `0`-calls-when-off and `category populated when on` assertions).
- Re-run the baseline measurement script (median of 5
  `collect_stats(with_backlog=True)` over the real corpus, plus the call-count
  instrumentation) and report the actual before/after. Expected shape:
  4178 → **2313** calls (the 1865 duplicates removed), ~60–70 ms off the 328.5 ms
  baseline on this box. The task text's "~62 ms" figure was measured on a
  248 ms baseline elsewhere — report the **measured** delta here rather than
  restating that number, and note that a box running concurrent agents will
  read noisier.
- `ait stats --csv <f>` still emits 12 columns with a non-empty `category` on
  every row (`awk -F, 'NF!=12' <f>` empty; no row with a trailing empty field).

## Risk

### Code-health risk: low
- The producer (`_book_backlog` call) and the consumer (the csv cell) are ~75
  lines apart in one loop body, so the coupling is implicit: a future edit that
  inserts a `continue`, reorders the booking, or reuses `booked_category`
  outside the iteration would silently reintroduce the second pass or, worse,
  attribute one file's category to another row. · severity: low · → mitigation:
  inline post-phase single_pass_invariant_guard
- Blast radius is one file and two module-private functions with one call site
  each; no public signature, no caller outside `stats_data.py`, and
  `work_report_gather.py` (the live `with_backlog=False` caller) is untouched.
  · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The target is measured, not estimated: the exact duplicate count (1865) and
  the baseline (328.5 ms) were captured before planning, and both named
  constraints have a dedicated executable guard. The one residual is that the
  absolute ms saving will not match t1544_4's "~62 ms" figure because this box
  measures a different baseline — that is a reporting hazard, not a design one.
  · severity: low · → mitigation: verification step reports the measured delta
  rather than restating the inherited number

### Planned mitigations
- timing: post-phase | name: single_pass_invariant_guard | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health bullet 1 (producer/consumer coupling across the archive loop body) | desc: assert the single-pass contract as a property over the recorded resolve_category call list (no filename twice) rather than an exact count, plus two-ended coupling comments at the producer and consumer sites

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`, `create_worktree: false`) — no task branch,
so Step 9 skips the merge and goes straight to gate verification, archival via
`./.aitask-scripts/aitask_archive.sh 1585`, and push.

## Post-Review Changes

### Change Request 1 (2026-08-25 18:20)
- **Requested by user:** The new `collect_stats` docstring sentence "Each file is
  classified **exactly once** per collection" is false. `with_backlog=False`
  performs zero classifications, and an archived file that is excluded from the
  flows *and* has no csv row performs zero as well. Reword to: under
  `with_backlog=True`, each file requiring a category is classified **at most
  once**.
- **Verified:** confirmed on both counts — the off path is pinned at 0 calls by
  `_check_with_backlog_off`, and the legacy `no_frontmatter` archived files
  return at the first guard and are dropped by the `completed is None`
  short-circuit before any row is built, so they are never classified.
- **Changes made:** reworded the `collect_stats` docstring to claim "at most
  once" under `with_backlog=True`, naming both zero-classification cases
  explicitly and stating that what the change rules out is classifying the same
  file *twice*. Swept the same loose "classified once" phrasing at the two other
  sites introduced by this task — the `_accumulate_backlog` return-value
  paragraph and the PRODUCER comment in the archive loop — plus the new test's
  docstring, which now reads "No file is classified TWICE under
  `with_backlog=True`" to match the property its central assertion actually
  checks. No behavioural change; assertions untouched.
- **Files affected:** `.aitask-scripts/lib/stats_data.py`,
  `tests/test_stats_multistage.py`
- **Re-verified:** `python3 tests/test_stats_multistage.py` → 98/98 passed.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, in two files.
  `_accumulate_backlog` now returns `Optional[str]` — `None` from each of its
  seven exclusion guards (made explicit), the resolved `category` after the
  flows are booked. `_book_backlog` forwards it. The archive loop binds it to a
  per-iteration local `booked_category`, and the csv-row producer consumes that
  value, falling back to a direct `resolve_category` call only on a memo miss,
  with the whole branch gated inside `with_backlog` so the off path's
  zero-classification contract is untouched. Producer and consumer each carry a
  comment naming the other end of the coupling. Added
  `_check_category_single_pass` to `tests/test_stats_multistage.py` (+107 lines,
  pure insertions) and registered it in `main()`.

- **Measured result (real corpus, median of 5, warm, load ~1.6):**

  | | before | after |
  |---|---|---|
  | `resolve_category` calls | 4178 | **2316** |
  | files classified twice | 1865 | **0** (max 1/file) |
  | `collect_stats(with_backlog=True)` | 328.5 ms | **267.5 ms** (−61.0 ms, −18.6%) |
  | `collect_stats(with_backlog=False)` | 169.3 ms | 176.0 ms (unchanged; no code change on that path, difference is noise) |
  | `with_backlog=False` classification calls | 0 | **0** |

  The −61 ms lands on the ~62 ms second pass the task targeted. Absolute numbers
  are box- and corpus-specific: this box measured a 328.5 ms baseline where
  t1544_4 measured 248 ms, so the *delta* is the comparable figure, not the
  totals. The distinct-file count rose 2313 → 2316 during the session because
  the corpus grew (this task's own commits).

- **Deviations from plan:** None in approach. One addition: the `collect_stats`
  docstring's `~77 ms / 171→248 ms` figure described a quantity this change
  alters, so it was updated rather than left stale.

- **Issues encountered:**
  - The negative control behaved exactly as predicted and was worth the step —
    it failed on unmodified source with `t500_normal.md` classified twice, and
    *only* the two pin assertions failed. Everything else stayed green in both
    states, confirming those are guards rather than accidental pins.
  - Three rounds of plan review caught fixture defects of one kind: a fixture
    table that omitted `created_at`. Because `_accumulate_backlog` returns at
    its `no_created_at` guard *before* classifying, the omission would have
    routed the fixture past the memo entirely — and for `t500_normal.md` it
    would have made the whole new check pass against the *unfixed* code. Measured
    both ways before fixing.
  - A fourth review round caught an over-broad docstring claim ("classified
    exactly once per collection"); corrected to "at most once, under
    `with_backlog=True`", with both zero-classification cases named. See
    Post-Review Changes.

- **Key decisions:**
  - **Fallback on a memo miss, not hoisting the resolution above the guards.**
    Hoisting would classify `no_frontmatter` / `no_created_at` files that are
    never classified today — adding work in the name of removing it.
  - **A per-iteration local, not a dict memo.** Producer and consumer are in one
    iteration of one loop; a dict would add unbounded growth and a key-identity
    question for nothing.
  - **A dedicated fixture tree, not an addition to `_seed_backlog_tree`.**
    Adding the folded-with-stamp task there would have shifted `_check_backlog`'s
    `folded` tally *and* broken its `identity 2: departures == total_tasks + live
    departed` assertion, whose third term is 0 only because no such task exists
    in that fixture. Both pre-existing checks are therefore untouched — the test
    diff is 107 insertions and 0 deletions, which is also the proof that
    `_check_with_backlog_off` passes unedited.
  - **`booked_category is not None` rather than truthiness.** `resolve_category`
    never returns `""`, and testing identity keeps that true by construction.
  - **Distinct category per fixture file** (`type:refactor` / `type:bug` /
    `type:chore`) so a value landing on the wrong row is caught by identity, not
    by non-emptiness.

- **Upstream defects identified:** None.

  (Two suite failures were observed but are **not** defects found by this task:
  `test_shadow_phase_restamp.py::BothAppsWireItTest::test_each_app_calls_the_helper`
  and
  `test_collection_structure.py::NoInheritedTestDuplicationTests::test_no_class_inherits_tests_from_a_same_module_base`
  both fail on *uncommitted working-tree changes* belonging to another in-flight
  task in this shared checkout — `.aitask-scripts/monitor/minimonitor_app.py`
  and `tests/test_minimonitor_auto_close_guard.py`, which at HEAD has a single
  plain `DiscoverWindowPanesContractTests(unittest.TestCase)` rather than the
  base-plus-two-subclasses that trips the duplication scan. They are that task's
  to resolve, not a pre-existing defect this task uncovered. Full suite
  otherwise: 5257 passed, 2 skipped.)

- **Build verification:** `bash tests/run_all_python_tests.sh --test-dir tests`
  → `PYTHON SUITE: FAILED (runner=pytest, exit=1)` with the two unrelated
  failures described above; `python3 tests/test_stats_multistage.py` → 98/98.
  `ait stats --csv` → 12 columns, 1867 rows, 0 malformed rows, 0 empty
  `category` cells (parsed with `csv.reader`).
