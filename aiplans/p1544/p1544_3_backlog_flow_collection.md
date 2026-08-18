---
Task: t1544_3_backlog_flow_collection.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_4_*.md, aitasks/t1544/t1544_5_*.md, aitasks/t1544/t1544_6_*.md, aitasks/t1544/t1544_7_*.md, aitasks/t1544/t1544_8_*.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_1_session_discovery_dedupe.md, aiplans/archived/p1544/p1544_2_task_category_axis_module.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-18 23:46
---

# p1544_3 — Backlog flow collection

## Context

`ait stats` answers "how much did we complete?" but not "how much is
outstanding, of what kind, and is it growing faster than we burn it down?".
Parent t1544 adds that. This child is the **data layer**: two weekly series
(arrivals and departures per category, over full history) stored on
`StatsData`, plus the pure helper that derives the open-task *level* from them,
so the CLI (t1544_4) and the TUI (t1544_5) are pure renderings.

t1544_1 (session dedupe) and t1544_2 (`task_category` + `split_frontmatter`)
are archived; both are consumed here.

## Verification pass (2026-08-18)

Re-verified against live source. The plan's design is sound and every measured
claim still holds; six findings refine it, each evidence-backed.

### Confirmed against the live corpus

| claim | plan said | measured now |
|---|---|---|
| archived with `completed_at` | 1818 | **1833** |
| archived on the `Done`+`updated_at` fallback | 9 | **9** |
| archived with **neither** | 0 | **0** |
| archived with no frontmatter | 3 (`t20`/`t21`/`t22`) | **3, same files** |
| live folded / archived folded | 5 / 0 | **5 / 0** |
| live departing (`Done`, unarchived) | 1 | **1** (`t1392`) |
| live `Postponed` | 9 | **9** |
| arrivals at offset ≥ 12 | 1318 | **1316** (of 2279; ≥ 8: **1628**) |
| two clocks differ by day / week bucket | 26 / 6 | **26 / 6** |

The pre-horizon number is the load-bearing one: at the default 8-week horizon
**1628 of 2279 arrivals sit outside the window**, so cumulating over
`out_offsets` instead of the full keyspace is catastrophically wrong, exactly as
the plan says. Max offset is 29 (~30 weeks of history), and **no** arrival has a
negative offset today.

### Finding 1 — the live walk is shared via a callback, not an extraction

`collect_inflight` (`stats_data.py:1004`) owns the live walk and is invoked
inline inside `collect_stats`'s return constructor (`:1156`) — i.e. today it is
a *second, independent* walk performed after the archive loop.

Sharing it by **extracting** the walk into a new function is blocked by a frozen
guard: `tests/test_gate_ledger_only_surfaces.py:89` registers
`("lib/stats_data.py", "collect_inflight")` as a ratified ledger-only surface,
and the guard asserts **exact set equality** — so moving the
`archive_status_from_text` call into a differently-named function requires
renaming the frozen key (and leaving the old entry also fails).

Measured cost of *not* sharing: a second live walk+read of all 442 files is
**4.0 ms** against `collect_stats`'s **161 ms** (2.5%).

**Decision (user-confirmed):** share the walk via an optional per-file callback
on `collect_inflight`, keeping the guard registry untouched and the public API
backward-compatible. See step 8.

### Finding 2 — `aitasks/new/` can only be pruned inside the iterator

`iter_active_markdown_files` (`:877`) yields `(basename, content)` — the bare
`os.walk` filename, **not** a path. Directory context is therefore already lost
by the time any caller sees a file, so the backlog collector *cannot* skip
`aitasks/new/` itself. The prune must go in the iterator's `dirs[:]` filter
(`:892`, currently `("archived", "metadata")`).

`aitasks/new/` exists and is completely empty (0 entries, no `.gitkeep`), so
this is a zero-behaviour-change edit today — and it correctly excludes drafts
from `collect_inflight` too.

### Finding 3 — backlog accumulation must precede the archive loop's `continue`

`collect_stats`'s archive loop does `completed = resolve_completion_date(...)`
then `if completed is None: continue` (`:1069-1071`). All three
no-frontmatter tasks die there. Backlog accumulation must be inserted **between
the frontmatter parse and that `continue`**, or `no_frontmatter` /
`archived_no_completed_at` can never be tallied.

The loop also currently calls `parse_frontmatter(content)` (`:1068`), which
discards the body the retro-classifier needs. Switch that one line to
`split_frontmatter(content)` — behaviour-identical by construction
(`parse_frontmatter` *is* `split_frontmatter(content)[0]`, `:298`).

### Finding 4 — the parents/children split needs two more counters, not three fields

Deliverable 3 requires a `(parents / children)` split on the `TOTAL OPEN` row.
A task is simultaneously (say) `kind:risk_mitigation` *and* a child, so the
split cannot live in the category key, and it must be per-week — which means
its own flow pair. Two options were rejected:

- **3-tuple keys** `(category, scope, offset)` — reshapes the `backlog_levels`
  contract the task explicitly pins.
- **Reserved `scope:` keys inside `backlog_arrivals`** — pollutes the category
  keyspace; any consumer enumerating categories would have to filter, and
  t1544_4/_5 enumerate.

So: **five** new `StatsData` fields, not three. The two extra reuse
`backlog_levels` verbatim (it is generic over the first key element).

### Finding 5 — `resolve_category`'s `tally` writes exactly one key

Live source (`task_category.py:158`) increments **only**
`tally["invalid_followup_kind"]`, and only when a `followup_kind` is present but
unrecognised. Every other `backlog_excluded` reason string is defined here.
Signature confirmed:
`resolve_category(metadata, body: str, filename: str, tally: Optional[dict] = None) -> str`.

### Finding 6 — a future `completed_at` needs its own reason

The task lists `future_created_at` because a negative offset would poison the
cumulation. The same argument applies to a **departure**, which the task does
not list. To hold the invariant t1544_4/_5 will rely on — *every offset key is
≥ 0* — a future `completed_at` excludes the task from **both** axes and tallies
`future_completed_at`.

0 such tasks exist today. Reconciliation identity 2 (below) assumes none; if the
counter ever fires, that is the signal saying so.

### Finding 7 — `invalid_followup_kind` is a *tally*, not an exclusion

Measured directly:

```python
resolve_category({"followup_kind": "not_a_real_kind", "issue_type": "bug"},
                 "Body.", "t999_x.md", tally=tally)
# -> 'type:bug'   tally == {'invalid_followup_kind': 1}
```

`resolve_category` (`task_category.py:154-158`) tallies the invalid kind and
then **falls through** to a derived or `type:` category. So passing
`tally=backlog_excluded` and then recording the flows would count the task in
both arrivals and departures **while reporting it as excluded** — a half-count
that directly violates the task's "skip entirely on both axes" contract, and one
that puts reconciliation identity 1 (`TOTAL OPEN == live − folded − departed −
excluded`) permanently off by the number of such tasks.

**Fix:** detect the invalid declared kind *before* category resolution and
return before either flow is incremented. Rather than re-deriving the clamp in
`stats_data` (which would need `task_category._unquote`, deliberately private),
expose the state from the resolver's own module — see step 1a and step 6.

### Finding 8 — the future-date guard must compare dates, not week offsets

`week_offset_for` compares **week starts**, so a date later than today *within
the current week* returns `0`, not `-1`. Measured, for `today = 2026-08-18`
(Tue) and a future date of `2026-08-21` (Fri, same week):

| `week_start_dow` | same-week future | later-week future |
|---|---|---|
| 0 | **0** | -1 |
| 1 | **0** | -1 |

So an `offset < 0` guard misses every future date up to six days out. The
consequences are both real: a future `created_at` becomes a **phantom arrival**
counted as open now, and a future `completed_at` **prematurely subtracts** a
task that is still open today.

**Fix:** compare the raw event date against `today` before bucketing. This is
strictly stronger *and* simpler — if `d <= today` then
`week_start(d) <= week_start(today)`, so a non-negative offset is guaranteed —
so it **replaces** the offset check rather than supplementing it.

The fixtures for this must be **same-week** future dates. A later-week fixture
is caught by the old buggy guard too and would therefore discriminate nothing.

## Implementation steps

### Pre-phase (risk mitigations)

1. `[capture_stats_baseline]` **Run before touching any file** — this must be
   the first action of implementation:

   ```bash
   ./ait stats > /tmp/t1544_3_stats_before.txt
   ```

   Once the archive loop is edited the baseline can no longer be re-derived from
   the working tree, and a "diff against a pre-change capture" step that captures
   *after* the change proves nothing.

### Main phase

1. **Imports and constants** — `.aitask-scripts/lib/stats_data.py`:
   - `from dataclasses import dataclass, field` — **`field` is not imported
     today** (`:20`); a bare `= Counter()` default is a mutable-default
     `ValueError` at class-definition time and the module would not import.
   - `from task_category import has_invalid_followup_kind, resolve_category  # noqa: E402`, beside the
     existing `archive_iter` / `config_utils` / `gate_ledger` sibling imports
     (`:29-41`) — the same house pattern, after the `_LIB_DIR` `sys.path`
     insert. Module scope is safe: `task_category`'s display half is
     dependency-free and `classify` is imported lazily inside `resolve_category`
     (t1544_2's design), so this adds no eager dependency.
   - `BACKLOG_WEEKS_DEFAULT = 8` — the single horizon default, read by both
     t1544_4's `--backlog-weeks` argparse default and t1544_5's pane, so the two
     surfaces cannot show different windows.

1a. **Expose the declared-kind state** — `.aitask-scripts/lib/task_category.py`
    (Finding 7). Factor the clamp out of `resolve_category` into a private
    helper and add one public predicate beside it:

    ```python
    def _declared_kind(metadata) -> str:
        # _unquote BEFORE the clamp, so '"carry_over"' resolves rather than
        # counting as invalid. Unchanged semantics — this is the same
        # expression resolve_category used inline.
        return followup_kind_field(_unquote(metadata.get("followup_kind")))


    def has_invalid_followup_kind(metadata) -> bool:
        """True when `followup_kind` is PRESENT but not a recognised kind.

        Exposed so a caller that must exclude such a task can decide *before*
        calling resolve_category, which tallies the invalid value and then
        falls through to a real category. Keeps `_unquote` private and the
        clamp expressed exactly once.
        """
        return _declared_kind(metadata) == INVALID_ENUM
    ```

    `resolve_category` calls `_declared_kind(metadata)` in place of its inline
    expression — a pure refactor, no behaviour change, and its existing `tally`
    contract is untouched for other callers. `tests/test_task_category.py`'s 20
    checks must stay green unedited.

2. **Five new `StatsData` fields**, each `field(default_factory=Counter)`,
   appended after `phase_timings` (`:164`) in the defaulted tail:

   ```python
   backlog_arrivals: Counter = field(default_factory=Counter)        # (category, week_offset)
   backlog_departures: Counter = field(default_factory=Counter)      # (category, week_offset)
   backlog_scope_arrivals: Counter = field(default_factory=Counter)  # ("parent"|"child", week_offset)
   backlog_scope_departures: Counter = field(default_factory=Counter)
   backlog_excluded: Counter = field(default_factory=Counter)        # reason -> count
   ```

3. **Three lockstep sites.** The dataclass (2), `_empty_stats_data()`
   (`:1164`, explicit all-keyword construction — add all five for style
   consistency even though the defaults would cover it), and
   `merge_stats_data()` (`:1192`) — plain additive `Counter.update`, exactly
   like every other counter there. Missing the third silently drops the series
   from multi-project aggregation.

4. **Bucketing helpers**, both derived from the existing `week_start_for` so
   there is exactly one week-boundary definition:

   ```python
   def backlog_week_offsets(weeks: int) -> List[int]:
       """[weeks-1 … 1, 0] — newest-last, matching panes/labels.py:55's idiom."""
       return list(range(weeks - 1, -1, -1))

   def week_end_for_offset(today: date, week_start_dow: int, offset: int) -> date:
       return week_start_for(today, week_start_dow) - timedelta(days=7 * offset) + timedelta(days=6)
   ```

   Reuse `week_offset_for` unchanged, simply **without** the `0 <= off <= 3`
   clamp — confirmed the clamp lives at two call sites (`:1102`, `:1109`), not
   inside the helper, so full history needs no change to it.

   **Do not touch** any existing 4-week site: `sorted_weekly_keys`'s `range(4)`
   (`:926`), the two `<= 3` guards, the four `range(4)` in `aitask_stats.py`
   (`:361,378,396,414`), `panes/labels.py:13` `_HEATMAP_WEEKS`,
   `panes/velocity.py:65`.

5. **`backlog_levels(arrivals, departures, out_offsets, excluded=None)`** — the
   contract that must not be got wrong. `out_offsets` selects **output columns
   only**; the cumulation always runs over every key present, however old.

   ```python
   per_cat: Dict[str, Counter] = defaultdict(Counter)
   for (cat, off), n in arrivals.items():
       per_cat[cat][off] += n
   for (cat, off), n in departures.items():
       per_cat[cat][off] -= n

   out = set(out_offsets)
   levels: Counter = Counter()
   for cat, deltas in per_cat.items():
       running = 0
       for off in sorted(set(deltas) | out, reverse=True):   # oldest first
           running += deltas.get(off, 0)
           if off in out:
               if running < 0 and excluded is not None:
                   excluded["negative_level"] += 1
               levels[(cat, off)] = max(0, running)
   return levels
   ```

   A single suffix-scan per category — O(k log k), not O(k × weeks). The delta
   at `off` is added *before* the membership test, so week `w`'s own arrivals
   count toward level `w`.

   The clamp is **not** silent, and `excluded` is an optional sink mirroring
   `resolve_category`'s `tally` (t1544_2's house pattern) — t1544_4/_5 pass
   `data.backlog_excluded`. It never fires on today's data, which is exactly why
   a silent clamp would mask a future regression.

6. **Collection — one clock, one rule.** A task has departed iff
   `parse_completed_date(frontmatter)` returns a date (`completed_at`, else
   `updated_at` when `status` is `Done`/`Completed`). The identical rule applies
   to archived and live files; **no** archived-vs-live special case.

   **Do not use `resolve_completion_date()`** — it prefers the
   `merge_approved`/`review_approved` ledger stamps, which on a *live* file mean
   "in flight", not "gone".

   New private helper, called from both trees:

   ```python
   def _accumulate_backlog(filename, frontmatter, body, today, week_start_dow, *,
                           archived, arrivals, departures,
                           scope_arrivals, scope_departures, excluded) -> None:
   ```

   Order of decisions — **skip entirely on both axes, never half-count, always
   tally** (an arrival kept with its departure dropped stays open forever).
   Every row below `return`s before *either* flow is touched:

   | # | condition | reason string |
   |---|---|---|
   | 1 | `not frontmatter` | `no_frontmatter` |
   | 2 | `status == "Folded"` or `"folded_into" in frontmatter` | `folded` |
   | 3 | `has_invalid_followup_kind(frontmatter)` | `invalid_followup_kind` (Finding 7) |
   | 4 | `created_at` missing/unparseable | `no_created_at` |
   | 5 | `created > today` | `future_created_at` (Finding 8) |
   | 6 | `archived and departed is None` | `archived_no_completed_at` |
   | 7 | `departed is not None and departed > today` | `future_completed_at` (Findings 6, 8) |

   Rows 5 and 7 compare **raw dates against `today`**, never
   `week_offset_for(...) < 0` — the offset form returns `0` for a same-week
   future date and would let a phantom arrival or a premature departure
   through. The date form also guarantees every bucketed offset is ≥ 0, which
   is the invariant t1544_4/_5 rely on, so no separate offset guard is needed.

   Then `cat = resolve_category(frontmatter, body, filename, tally=None)`,
   `scope = "child" if is_child_task(filename) else "parent"`, and increment the
   arrival pair plus, when departed, the departure pair.

   **`tally=None` is deliberate.** Row 3 has already excluded and counted every
   task the resolver's tally would have flagged, so passing `excluded` here
   would double-count. The tally is owned at the exclusion site, where the
   `return` that makes it truthful also lives.

   **Postponed counts as open** (outstanding work by the stated definition; 9
   live). **Parents and children both count**, with the scope split making that
   visible.

7. **Archive-side wiring** (`collect_stats`, `:1067-1071`) — per Finding 3:

   ```python
   for filename, content in iter_archived_markdown_files(project_root=project_root):
       frontmatter, body = split_frontmatter(content)          # was parse_frontmatter
       if with_backlog:
           _accumulate_backlog(filename, frontmatter, body, today, week_start_dow,
                               archived=True, ...)
       completed = resolve_completion_date(content, frontmatter)
       if completed is None:
           continue
       ...unchanged...
   ```

8. **Live-side wiring — one walk via a callback** (Finding 1):

   - `iter_active_markdown_files` (`:892`): prune `new` alongside `archived` /
     `metadata`, and say why in the docstring (Finding 2).
   - `collect_inflight` gains `on_file: Optional[Callable[[str, str], None]] = None`,
     invoked as the **first statement of the loop body** — before
     `if not has_gate_markers(content): continue` — so every live file is seen.
     Document it as "an optional per-file observer so a caller can share this
     walk instead of adding a second one (t1544_3)". The
     `archive_status_from_text` call stays in this function, so
     `tests/test_gate_ledger_only_surfaces.py` is untouched.
   - `collect_stats` **hoists** the `collect_inflight` call out of the return
     constructor into a local before `return StatsData(...)`, passing the
     observer only when `with_backlog`. Hoisting makes the ordering explicit
     rather than relying on argument-evaluation order to populate counters that
     appear earlier in the same constructor call.

9. **`with_backlog` and its one opt-out caller.**
   `collect_stats(today, week_start_dow, project_root=None, with_backlog: bool = True)`.
   `lib/work_report_gather.py:394` calls `collect_stats(now, 1, project_root=None)`
   purely to read `.daily_counts` — change it to pass `with_backlog=False`.

   **Assert the real cost contract, not a stronger one.** The flag **cannot**
   eliminate a live-tree walk (`collect_inflight` runs regardless). What it
   eliminates is the per-file classification and bookkeeping — measured
   **120 ms archived + 16 ms live = ~136 ms**, roughly doubling `collect_stats`'s
   161 ms. Gating `collect_inflight` itself is **out of scope**: pre-existing
   cost this task does not introduce, and it would change the meaning of a field
   other callers read.

10. **Module docstring** — add `task_category` to the base-layer sibling
    enumeration (`:1-11`). t1544_2 deliberately left it alone because that
    import edge did not exist yet; this child creates it and owns the update.

### Post-phase (risk mitigations)

1. `[crosscheck_level_against_direct_stock]` After implementation, compute the
   open-task level over the **real** corpus a second, independent way and
   compare it week by week against `backlog_levels`.

   The check must be **independent ground truth, not a second artifact of the
   same code**: write the direct stock straight from the definition — for each
   week end `E` from `week_end_for_offset`, count tasks with
   `created_at <= E` and (`parse_completed_date` is `None` or `> E`), applying
   the same exclusions — rather than reusing any helper this task added beyond
   the date/bucketing primitives.

   Run it over both trees at the default 8-week horizon and record the two
   series plus their per-week delta in the Final Implementation Notes. Any
   non-zero delta is a defect in the derivation, not in the check.

   This is a **one-off implementation-time check, not a test**: a live-corpus
   assertion flakes when a concurrent session archives a task mid-run, which is
   why the committed identities stay on synthetic fixtures.

## Files

- `.aitask-scripts/lib/task_category.py` — `_declared_kind` + `has_invalid_followup_kind` (step 1a)
- `.aitask-scripts/lib/stats_data.py`
- `.aitask-scripts/lib/work_report_gather.py`
- `tests/test_stats_multistage.py`
- `tests/test_task_category.py` — cases for the new predicate

## Verification

Follow `tests/test_stats_multistage.py`'s style exactly: script-style
`_check_*(tmp)` functions with `assert_eq` counters, the `_task()` / `_marker()`
/ `_ledger()` / `_write()` fixture builders, `main()` returning 1 on failure,
wrapped by `ScriptChecksTest`. It passes `project_root=tmp` and patches **no**
globals — which is what this child needs, since the new code walks **both**
trees. Do not mix in `tests/test_aitask_stats_py.py`'s global-patching style.

`_task(frontmatter, *ledger_markers)` hardcodes the body `"Body.\n"`; add an
optional `body="Body."` keyword (backward-compatible) so the classifier-derived
case can supply a real prose rule. Note `_write()` prepends `aitasks/`, so
archived fixtures go to `archived/…`.

**`_check_backlog_levels()`** (no tmp — pure helper):
- an arrival at offset 40 with `out_offsets=[3,2,1,0]` gives level **1** at
  offset 3, not 0 — the pre-horizon contract;
- a departure clears the level from its own week onward;
- a forced negative raw level clamps to 0 **and** tallies `negative_level`;
- `backlog_week_offsets(8) == [7,6,5,4,3,2,1,0]`;
- `week_end_for_offset` agrees with `week_start_for` at offset 0 and 3.

**`_check_backlog(tmp)`** must cover:
- a task open across a week boundary;
- a task completed mid-series;
- a follow-up whose kind is only derivable by `classify()` (prose rule, no
  `followup_kind:` field) — proves the body reaches the classifier;
- missing `created_at` → excluded from both flows, tallied;
- a live task with a passing `review_approved` marker and no `completed_at`
  → stays **open** (the `resolve_completion_date` trap);
- a task whose ledger week differs from its `completed_at` week → departs in the
  **`completed_at`** week;
- a live `Done` task → departs;
- an archived task with no `completed_at` → excluded from both flows;
- a **Folded** task (both detections: `status: Folded`, and `folded_into:`
  alone) → excluded from both flows;
- a task with a bogus `followup_kind` → `invalid_followup_kind` tallied **and
  zero contribution to either flow** (Finding 7). Assert both halves: the tally
  alone passes under the defect, since the defect *is* a tally without an
  exclusion. Include a departed one, so a missing exclusion would show up in
  `backlog_departures` as well as `backlog_arrivals`;
- a **same-week future `created_at`** → `future_created_at`, no phantom
  arrival; and a **same-week future `completed_at`** → `future_completed_at`,
  the task not prematurely subtracted (Finding 8). Both fixtures must sit in the
  *current* week relative to the fixture's `today`: a later-week date is caught
  by the offset form too and would discriminate nothing;
- a file under `aitasks/new/` → **not** counted (Finding 2);
- the parent/child scope split;
- merge additivity across two `project_root`s (`merge_stats_data`). Per
  t1544_1's notes, session uniqueness is guaranteed upstream in
  `_assemble_aitasks_sessions` and only for `include_registered=True`, and is
  already pinned by t1544_1's tests — do **not** re-test discovery here;
- both reconciliation identities, on **synthetic fixtures only** (during parent
  planning both briefly read off-by-one purely because a concurrent session
  archived a task mid-measurement):
  - `TOTAL OPEN` at offset 0 == (live files yielded by `iter_active_markdown_files`)
    − (live tasks excluded for **any** reason) − (live tasks that departed).
    Note `folded` *is* one of the exclusion reasons, so do not subtract it a
    second time; and the excluded count is a sum over the **task-exclusion**
    reasons only — `negative_level` counts clamped output cells, not tasks, and
    must be left out of this sum.
  - `Σ departures over all history` == `data.total_tasks` + live-departed −
    (archived tasks excluded before their departure was recorded). The third
    term is 0 today and each of its reasons has its own counter; assert it as 0
    on the fixtures and state the dependency rather than hiding it.

**`_check_with_backlog_off(tmp)`**:
- all five backlog counters empty;
- `resolve_category` invoked **zero** times — monkeypatch `sd.resolve_category`
  with a counting wrapper (module-scope import makes this the clean seam);
- every pre-existing field (`daily_counts`, `total_tasks`, `inflight`,
  `phase_timings`) identical to a `with_backlog=True` run — the flag is purely
  subtractive.

**`tests/test_task_category.py`** — add cases for the new predicate (step 1a):
`has_invalid_followup_kind` is `True` for a present-but-bogus value, `False`
when the field is absent, `False` for a real kind, and `False` for a quoted real
kind (`'"carry_over"'` — pinning that `_unquote` still runs before the clamp).
The existing 20 checks must pass **unedited**; if one needs editing, the
refactor changed behaviour and is wrong.

### Suite and live checks

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
bash tests/test_stats_data.sh
bash tests/test_no_lib_to_tui_import.sh
python3 -m unittest tests.test_gate_ledger_only_surfaces -v   # guard must stay green
./ait stats > /tmp/t1544_3_stats_after.txt            # byte-identical vs baseline,
                                                      # ignoring the `Generated:` line
```

Counting live files with `find -L aitasks -name 't*.md' -not -path '*metadata*'`
is **wrong** — it also excludes real task files whose filenames contain
"metadata". Use `iter_active_markdown_files`.

**Path resolution:** the stats data layer resolves paths from the process cwd; a
probe run from the wrong directory silently scans nothing and reports all-zero.
Pass `project_root=` in tests.

Step 9 (Post-Implementation) handles cleanup, archival and merge.

## Notes for sibling tasks

Record in the Final Implementation Notes: the final `backlog_levels` signature
(including the `excluded` sink), the exact `backlog_excluded` reason strings,
all **five** `StatsData` field names, the shape of the scope split, the
`on_file` callback contract on `collect_inflight`, and the measured
`collect_stats` cost delta. t1544_4 and t1544_5 render directly from all of it.

Two contract points t1544_4 must not get wrong when rendering `backlog_excluded`:

- **Every** reason string in it means "this task contributed to neither flow" —
  including `invalid_followup_kind`, which this child converted from a
  fall-through tally into a real exclusion (Finding 7). The one exception is
  `negative_level`, which counts *clamped output cells*, not tasks, and must not
  be summed into a task-count column.
- `task_category.has_invalid_followup_kind(metadata)` is the supported way to
  ask that question; do not re-derive the clamp, and do not call
  `resolve_category(..., tally=…)` expecting the tally alone to exclude
  anything.

t1544_4 additionally inherits t1544_2's recorded upstream defect
(`aitask_stats.py:384` renders types with a bare `.capitalize()`, bypassing the
display map) as a decision it must make explicitly rather than copy.

## Risk

### Code-health risk: medium

- `collect_stats` feeds three surfaces (CLI report, stats TUI, `work_report_gather`) and its archive loop is edited in place — the `parse_frontmatter` → `split_frontmatter` swap and an accumulation call inserted before the `completed is None` short-circuit. A subtle slip changes existing report output. · severity: medium · → mitigation: inline pre-phase capture_stats_baseline
- Five new fields grow the dataclass / `_empty_stats_data` / `merge_stats_data` lockstep from three sites to five. A missed `merge_stats_data` entry silently drops a whole series from multi-project aggregation and is invisible in single-project use. · severity: medium · → mitigation: covered by the merge-additivity check in `_check_backlog`
- Step 1a edits `task_category.py`, which t1544_4 and t1544_5 also depend on, to factor the clamp into `_declared_kind`. It is a pure refactor, but a slip changes the category axis itself rather than just the backlog series. · severity: low · → mitigation: covered — `tests/test_task_category.py`'s existing 20 checks must pass unedited
- The `on_file` observer gives `collect_inflight` a responsibility its name does not advertise, and it must fire *before* the gate-marker filter — a future reader tidying the loop could move it below the `continue` and silently drop most live arrivals. · severity: low · → mitigation: covered — most `_check_backlog` fixtures carry no gate markers, so an observer placed below the filter fails them

### Goal-achievement risk: low

- The flows→stock derivation is asserted only against synthetic fixtures (deliberately — a live-corpus assertion flakes when a concurrent session archives mid-run). A systematic error in `backlog_levels` would satisfy every fixture that was built from the same mental model and still be wrong on the real corpus. · severity: medium · → mitigation: inline post-phase crosscheck_level_against_direct_stock
- t1544_4 and t1544_5 render directly from these field names, reason strings and key shapes; a wrong shape means rework in two downstream siblings. · severity: low · → mitigation: recorded in `## Notes for sibling tasks`

### Planned mitigations
- timing: pre-phase | name: capture_stats_baseline | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (in-place edits to collect_stats could change existing report output) | desc: capture ./ait stats to a file as the very first action, before any edit, so the byte-identity check compares against genuinely pre-change output
- timing: post-phase | name: crosscheck_level_against_direct_stock | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk 1 (flows to stock derivation otherwise asserted only against fixtures built from the same mental model) | desc: after implementation, derive the open-task level over the real corpus from an independently written direct-stock expression and compare week by week against backlog_levels

**Reassessment after inlining:** both phases are bounded verification steps that
add no production code; the levels above already describe the plan as augmented
(code-health **medium**, goal-achievement **low**).
