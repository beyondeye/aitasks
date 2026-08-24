---
Task: t1586_extract_backlog_view_helper.md
Base branch: main
Output branch: main
---

# t1586 — Extract the shared backlog view logic into `lib/backlog_view.py`

## Context

t1544_4 landed ~150 lines of backlog axis/ordering/subtotal logic inside
`.aitask-scripts/aitask_stats.py` and deliberately kept it private, refusing to
extract a helper shaped for a *guessed* consumer. t1544_5 has now landed
(`7eb74d761`) and is that real second consumer: `.aitask-scripts/stats/panes/backlog.py`
re-implements the same logic verbatim because the CLI's versions are
underscore-private and live above `lib/` in the layering. Its module docstring
names this task by number and says so outright.

Measured duplication today — byte-for-byte equivalent in both files:

| logic | CLI (`aitask_stats.py`) | TUI (`stats/panes/backlog.py`) |
|---|---|---|
| all-tasks re-key | `_aggregate_all` (L326) | `_aggregate_all` (L89) |
| 7 task-exclusion reasons | `BACKLOG_TASK_EXCLUSION_REASONS` (L290) | `_TASK_EXCLUSION_REASONS` (L60) |
| column order (`W-n…`, `Now` last) | `_backlog_columns` (L373) | `_columns` (L71) |
| 3× `backlog_levels` + scratch clamp sink | `_build_backlog_axis` (L341) | `_derive_levels` (L104) |
| level ordering key | L358 | L191 |
| net-flow ordering key | L504 | L258 |

The outcome: one pure base-layer module both surfaces import, so the
load-bearing `_aggregate_all` accumulation contract and the deterministic
ordering tie-break exist exactly once.

**Seam extent (confirmed with the user).** The task's Goal names three items but
also says "the two different row-membership predicates are CLI concerns" while
listing "the ordering rule" as shared. Settled reading: lift the three named
items **plus** the column-order helper (t1588's pane docstring explicitly
forward-points to t1586 for it) **plus** a shared ordering function. The two
net-flow row-**membership** predicates stay per-surface, as the task says.

**On the task's `depends: [1544_5]` instruction.** That line was written while
t1544_5 was still pending. It has since landed and been archived, so the
blocking condition it was meant to express is already satisfied; wiring a
`depends:` onto an archived task now would only add a dangling edge for
`ait ls` to resolve. No frontmatter dependency is added — the gate the
instruction existed to enforce is met.

## Approach

### Pre-phase (risk mitigations)

1. `[characterize_backlog_sections]` **Before editing any source**, add a
   characterization test to `TestBacklogSections` in
   `tests/test_aitask_stats_py.py`: render the report on that class's existing
   synthetic fixture, slice out the `### Backlog Level (Open Tasks)` and
   `### Backlog Net Flow` sections **whole** with the module's existing
   `_section` helper, and compare each byte-for-byte against a literal expected
   string in the test. Scoped to those two sections only (never the
   wall-clock `Generated:` line, never the unrelated ~450 lines of label
   tables), so it cannot go brittle on changes this task does not make. Unlike
   today's per-row spot assertions it also pins column widths, footnote lines
   and blank-line placement — which is what makes it discriminate on a lost
   tie-break or a mis-lifted width. **Run it against the UNMODIFIED sources and
   confirm it passes before proceeding**: a golden minted after the change pins
   nothing.

### 1. New file `.aitask-scripts/lib/backlog_view.py`

Pure base-layer module. Imports only lib siblings (`stats_data`,
`task_category`), using the established `_LIB_DIR`-on-`sys.path` preamble from
`lib/stats_data.py:28-33`. No TUI import, so `tests/test_no_lib_to_tui_import.sh`
stays green by construction.

Public surface (no leading underscores — it is consumed by two packages):

```python
BACKLOG_TASK_EXCLUSION_REASONS = (...)   # the 7 TASK reasons; negative_level
                                         # deliberately absent (it counts CELLS)

@dataclass
class BacklogAxis:
    offsets: List[int]
    levels: Counter
    scope_levels: Counter
    total_levels: Counter
    followup_rows: List[str]
    genuine_rows: List[str]
    clamped_cells: int = 0

    @property
    def has_rows(self) -> bool: ...

def aggregate_all(flow: Counter) -> Counter: ...
def build_backlog_axis(data: StatsData, offsets: Sequence[int]) -> BacklogAxis: ...
def backlog_columns(offsets: Sequence[int], now_label: str) -> Tuple[List[int], List[str]]: ...
def order_categories(categories, levels, *, followups_first=False) -> List[str]: ...
```

Straight lifts of the CLI bodies, unchanged. Two deliberate adjustments:

- **`BacklogAxis.cell_w` is dropped.** It is CLI pipe-table width state that
  `render_backlog_level` writes at L457 and reads at L458-461 and nowhere else
  (no test reads it; `render_backlog_netflow` and `write_backlog_csv` already use
  a plain local). Pushing a "width-adaptive numeric cell" field into `lib/` is
  exactly what the task says to leave behind. It becomes a local in
  `render_backlog_level`.
- **`order_categories`** absorbs the sort key that both surfaces spell out twice.
  `followups_first=False` (level rule) →
  `(-levels[(c, 0)], category_display_name(c))`; `followups_first=True`
  (net-flow rule) → `(not is_followup_category(c), -levels[(c, 0)], category_display_name(c))`.
  `build_backlog_axis` calls it with `False`, then partitions into
  `followup_rows` / `genuine_rows`.

Docstrings carry over the two strongest recorded contracts — the "MUST
accumulate, a dict comprehension keeps only the LAST value" note on
`aggregate_all`, and the per-call scratch-Counter rationale, merging the pane's
sharper version (`stats_app._show_pane` re-renders against the same cached
`StatsData`, so a shared sink would grow unbounded for the session's life).

### 2. `.aitask-scripts/aitask_stats.py`

- Import the six names from `backlog_view` (lib is already on `sys.path` at
  L21) and delete `_aggregate_all`, `_build_backlog_axis`, `BacklogAxis`,
  `BACKLOG_TASK_EXCLUSION_REASONS`, `_backlog_columns`.
- Re-export `BacklogAxis`, `BACKLOG_TASK_EXCLUSION_REASONS`,
  `build_backlog_axis`, `backlog_columns` at module scope and add them to
  `__all__` — the same idiom the file already uses for the t1235 data-layer
  split ("kept at module scope so existing tests and call sites that reference
  `aitask_stats.X` continue to work"). No private `_`-prefixed aliases: an alias
  that exists only for tests is dead weight.
- `render_backlog_level`: `cell_w` becomes a local; call sites at L457-461 read
  the local.
- `render_backlog_netflow`: replace the inline sort lambda at L504 with
  `order_categories(rows_src, axis.levels, followups_first=True)`. Its
  membership predicate above it is untouched.
- `_backlog_table_row` / `_backlog_table_sep` / `BACKLOG_LABEL_W` /
  `BACKLOG_MIN_CELL_W` / `_render_backlog_exclusions` all stay — CLI formatting.

### 3. `.aitask-scripts/stats/panes/backlog.py`

- Delete `_aggregate_all`, `_TASK_EXCLUSION_REASONS`, `_columns`,
  `_derive_levels`; import from `backlog_view` (bare import, exactly like the
  existing `from stats_data import …` — `lib/` reaches `sys.path` through
  `stats_app.py`'s `lib.tui_switcher` import / `stats/__init__.py`).
- `_level_rows`: `axis = build_backlog_axis(stats, offsets)`, then read
  `axis.followup_rows` / `axis.genuine_rows` instead of recomputing `visible`,
  and `axis.levels` / `axis.scope_levels` / `axis.total_levels` /
  `axis.clamped_cells` for the cells. `_cap_block`, the `Other` bucket, the
  `if rows:` guard and the subtotal labels are unchanged.
- `_netflow_rows`: build the axis for `levels`, keep its own `members`
  membership predicate, and sort via
  `order_categories(members, axis.levels, followups_first=True)`. The
  volume-ranked chart series (`_NETFLOW_SERIES`, `Other`) is untouched.
- `_diagnostic_lines` and `_render_level` reference the imported
  `BACKLOG_TASK_EXCLUSION_REASONS`.
- Update the module docstring: the "duplicates `aitask_stats.py`'s … t1586 lifts
  the shared parts" paragraph becomes a statement of what now lives in
  `lib/backlog_view.py` and what stays local (cap, `Other`, chart series). Same
  for `_columns`' "Mirrors `aitask_stats._backlog_columns`" note, which is being
  deleted with the function.

### 4. Tests

- `tests/test_aitask_stats_py.py` (3 sites: L591, L763, L822) and
  `tests/test_stats_backlog_panes.py` (L419, L425): `stats._build_backlog_axis`
  / `CLI._build_backlog_axis` → `build_backlog_axis` via the re-export. Call-site
  rename only — no assertion is touched, so every existing negative control keeps
  its discriminating power.
- Add a small module of direct unit tests for the new seam in
  `tests/test_aitask_stats_py.py` (it already owns the backlog fixtures):
  - **negative control, carried over from t1544_4:** `aggregate_all` on a flow
    with two categories in the same offset sums them — the assertion that fails
    under a dict comprehension. Currently pinned only indirectly through the
    rendered report (`test_all_tasks_axis_sums_categories_sharing_a_week`); that
    test stays, and this adds the direct probe at the new public boundary.
  - `order_categories` tie-break: two categories at equal level order by display
    name, and `followups_first=True` puts a follow-up category ahead of a
    higher-level genuine one.
  - `backlog_columns` puts offset 0 last and labels it with the caller's
    `now_label`.

### Post-phase (risk mitigations)

1. `[pin_no_residual_duplication]` Add `tests/test_backlog_view_is_single_sourced.py`.
   Assert that neither `.aitask-scripts/aitask_stats.py` nor
   `.aitask-scripts/stats/panes/backlog.py` re-declares an extracted name —
   no `def _aggregate_all`, `def _backlog_columns`, `def _columns`,
   `def _derive_levels`, and no local 7-reason exclusion tuple
   (`_TASK_EXCLUSION_REASONS = (` / `BACKLOG_TASK_EXCLUSION_REASONS = (`) — and
   that both files import those names from `backlog_view`. Include a **negative
   control**: run the same scan over a temp-dir copy that re-adds
   `def _aggregate_all(` to one file and assert that file IS flagged, and that
   exactly one file is flagged. Without it, a scan whose pattern never matches
   would pass forever and pin nothing. Document the detection boundary in the
   file header (textual scan; a re-fork through an aliased or dynamically built
   name is not detected), the way `tests/test_no_lib_to_tui_import.sh` does.

## Verification

0. The two inline risk-mitigation phases are part of the deliverable, not
   optional extras: `characterize_backlog_sections` must be **green on the
   unmodified sources first**, and `pin_no_residual_duplication` must be green
   — including its own negative control — at the end (it is a Python module, so
   step 2's suite run covers it).
1. `bash tests/test_no_lib_to_tui_import.sh` — the layering guard for the new
   `lib/` module.
2. `bash tests/run_all_python_tests.sh --test-dir tests` — **read the LAST line
   only** (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); do not pipe to
   `tail` without `pipefail`.
3. **Byte-identical `ait stats`, with the same-clock control t1544_4 used.** A
   plain before/after diff is invalid here: other agents create and complete
   tasks concurrently, which moves the real backlog series. Capture
   new → old → new and require the two *new* captures to be identical; only then
   is the old-vs-new diff attributable to the change:
   ```bash
   S=/tmp/claude-1000/.../scratchpad          # scratchpad dir
   # taken BEFORE any edit:
   #   cp .aitask-scripts/aitask_stats.py .aitask-scripts/stats/panes/backlog.py $S/old/
   cap() { find .aitask-scripts -name __pycache__ -prune -exec rm -rf {} + ;
           ./ait stats > "$1" 2>&1 ; ./ait stats --csv-backlog "$1.csv" >/dev/null 2>&1 ; }
   # stash the NEW sources first, so the restore below never depends on git
   cp .aitask-scripts/aitask_stats.py .aitask-scripts/stats/panes/backlog.py $S/new/
   cap $S/new1
   cp $S/old/aitask_stats.py .aitask-scripts/ ; cp $S/old/backlog.py .aitask-scripts/stats/panes/
   cap $S/old_out
   cp $S/new/aitask_stats.py .aitask-scripts/ ; cp $S/new/backlog.py .aitask-scripts/stats/panes/
   cap $S/new2
   diff <(grep -v '^Generated:' $S/new1) <(grep -v '^Generated:' $S/new2)   # must be empty -> clock/state stable
   diff <(grep -v '^Generated:' $S/old_out) <(grep -v '^Generated:' $S/new1) # must be empty -> no behavior change
   diff $S/old_out.csv $S/new1.csv                                          # backlog CSV identical
   ```
   The new sources are restored from a scratchpad copy, never from git — they
   are uncommitted at that point, so `git checkout --` would destroy them.
4. **Stats TUI panes unchanged:** `tests/test_stats_backlog_panes.py` (includes
   `TestCliParity`, which renders one `StatsData` through both surfaces and
   compares row for row — the cross-surface parity guard this refactor most
   needs) and `tests/test_stats_backlog_panes_live.py`.
5. `ait stats-tui` opened by hand on the two Backlog panes, confirming the level
   table and net-flow chart render as before.
6. Baseline for comparison, captured before any edit: `tests/test_aitask_stats_py.py`
   + `tests/test_stats_backlog_panes.py` = **69 passed**.

## Step 9 (Post-Implementation)

Standard closure: commit on `main` (current-branch mode, no worktree, no merge),
then archive `t1586` and this plan per the task-workflow Step 9 procedure.

## Risk

Levels below are the **reassessment** against the augmented plan (both inline
mitigations included), per `risk-evaluation.md`'s reassessment note. Both
dimensions were already `low` pre-insertion and remain `low`; the two
`medium`-severity bullets are now pinned rather than merely argued.

### Code-health risk: low

- The lift must be verbatim: re-typing `aggregate_all` as a dict comprehension,
  or letting the ordering key lose its `category_display_name` tie-break, changes
  numbers silently rather than failing loudly. · severity: medium · → mitigation: inline pre-phase characterize_backlog_sections
- Nothing stops a later edit from re-declaring a local `_aggregate_all` or
  `_columns` in either surface and silently re-forking the seam this task
  exists to create. · severity: low · → mitigation: inline post-phase pin_no_residual_duplication
- Dropping `BacklogAxis.cell_w` touches CLI render code the extraction otherwise
  leaves alone. Blast radius is 5 lines inside one function, no test or call site
  reads the field, and the pre-phase golden pins the resulting column widths
  directly. · severity: low · → mitigation: inline pre-phase characterize_backlog_sections
- `order_categories(..., followups_first=...)` is a boolean-parameterised sort —
  a small policy-in-a-primitive wobble in an otherwise pure module. Bounded: two
  call shapes, both exercised by existing tests. · severity: low · → mitigation: none (accepted)

### Goal-achievement risk: low

- `ait stats` byte-identity is asserted against a *live* repo whose backlog moves
  under concurrent agent activity; a naive diff would produce false failures and
  could mask a real one. The new→old→new control in Verification step 3 makes the
  comparison mean something, and the pre-phase golden gives the same claim a
  deterministic, re-runnable form that does not depend on the live repo at
  all. · severity: medium · → mitigation: inline pre-phase characterize_backlog_sections
- The task's "leave the row-membership predicates behind" line sits in tension
  with its "the ordering rule moves" line. Resolved by explicit user decision
  before planning finished, and recorded in Context above. · severity: low · → mitigation: none (resolved)

### Planned mitigations
- timing: pre-phase | name: characterize_backlog_sections | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "the lift must be verbatim" + goal-achievement "live byte-identity is noisy" | desc: Whole-section golden of the two rendered backlog sections on the existing synthetic fixture, minted and confirmed green against the UNMODIFIED sources before any edit.
- timing: post-phase | name: pin_no_residual_duplication | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "a later edit can silently re-fork the seam" | desc: Guard test (with a negative control) that neither surface re-declares an extracted name and both import them from backlog_view.

## Implementation Notes

Landed as planned; no deviations from the approved approach. Both inline
mitigation phases were executed in their planned positions.

**Pre-phase — `characterize_backlog_sections`.** Added
`_LEVEL_SECTION_GOLDEN` / `_FLOW_SECTION_GOLDEN` and
`TestBacklogSections::test_backlog_sections_render_byte_for_byte` to
`tests/test_aitask_stats_py.py`, minted and confirmed green against the
unmodified sources. Its discriminating power was then proven rather than
assumed: mutating `_aggregate_all` to the dict comprehension made `TOTAL OPEN`
read 2 instead of 4 and the golden failed; the source was restored byte-identical
before proceeding.

**Post-phase — `pin_no_residual_duplication`.** Added
`tests/test_backlog_view_is_single_sourced.py` (7 tests). It scans via `ast` at
module level rather than textually, so a lifted name inside a docstring, comment
or `import` line cannot trip it. Four negative controls: a re-forked `def` is
flagged (and exactly one file is), a restated constant is flagged, a nested copy
is *not* (pinning the documented boundary so the header's claim cannot rot), and
an `import` of the constant is not mistaken for a re-declaration.

**Two small in-scope adjustments beyond the named lift**, both of which the
Approach called for:
- `is_followup_category`, `backlog_levels` and `dataclass` became unused in
  `aitask_stats.py` once the axis moved, and were dropped from its imports.
- All six lifted names are re-exported and listed in `__all__` (not just the
  four originally named), so `aggregate_all` and `order_categories` are reachable
  as `aitask_stats.X` like every other re-export and no import is left unused.

### Verification results

| check | result |
|---|---|
| `tests/test_no_lib_to_tui_import.sh` | 13 passed, 0 failed |
| `tests/run_all_python_tests.sh --test-dir tests` | `PYTHON SUITE: PASSED (runner=pytest, exit=0)` |
| `ait stats` old vs new, live repo | identical (control: two `new` captures identical, so the window was stable) |
| `ait stats --csv-backlog` old vs new | identical |
| `tests/test_aitask_stats_py.py` | 53 passed (was 69 across both stats modules; now 79 with the 10 added) |
| `tests/test_stats_backlog_panes.py` + `_live.py` + `test_stats_multistage.py` | 35 passed |
| TUI pane row output old vs new, live repo | `_level_rows` + `_netflow_rows` byte-identical |

The pane check was run as a direct old-vs-new comparison of the pure row
derivations against live data, not inferred transitively from `TestCliParity`.

**Not done by the agent:** the by-hand `ait stats-tui` pass over the two Backlog
panes (Verification step 5). The automated live-render module
(`tests/test_stats_backlog_panes_live.py`) boots the real TUI and passes, and the
pure row output is proven identical, but a human eyeball on the rendered chart
was not performed.

## Final Implementation Notes

- **Actual work done:** Exactly the approved approach. `lib/backlog_view.py`
  created with the six shared names; `aitask_stats.py` and
  `stats/panes/backlog.py` both reduced to importing them (−151 / −143 lines
  respectively) with only per-surface presentation left behind. Both inline
  risk-mitigation phases executed in their planned positions.
- **Deviations from plan:** None in approach. Two mechanical consequences the
  Approach anticipated: three imports (`is_followup_category`, `backlog_levels`,
  `dataclass`) became unused in the CLI and were dropped, and all six lifted
  names — not only the four originally named — are re-exported and listed in
  `__all__`, so no imported name is left unused and every one is reachable as
  `aitask_stats.X`.
- **Issues encountered:** None substantive. One scripted edit asserted a
  substring count of 2 for `_TASK_EXCLUSION_REASONS` and saw 3, because
  `BACKLOG_TASK_EXCLUSION_REASONS` contains it; the assertion aborted the write
  before any change, and the edit was redone against the unambiguous
  `in _TASK_EXCLUSION_REASONS` fragment. No file was left half-edited.
- **Key decisions:**
  - **Seam extent** was settled with the user before planning finished: the
    three names t1586 lists, plus `backlog_columns` (t1588's pane docstring
    forward-pointed to this task for it) and `order_categories`. The two
    net-flow row-MEMBERSHIP predicates stay per-surface, as the task directs —
    membership is a per-table decision, only the ordering is shared.
  - **`BacklogAxis.cell_w` was dropped, not moved.** It was CLI pipe-table width
    state written and read inside one function; carrying a "width-adaptive
    numeric cell" field into `lib/` is precisely what the task says to leave
    behind. It is now a local, matching what the flow table already did.
  - **`build_backlog_axis` keeps its `StatsData` parameter** rather than taking
    four bare Counters. A narrower signature would be more purist, but both
    consumers hold a `StatsData` and the wider one makes this a straight lift
    with no behavioural surface at all.
  - **The pane's sharper scratch-Counter rationale won** over the CLI's when the
    two docstrings were merged: it names the concrete failure
    (`stats_app._show_pane` re-rendering against one cached `StatsData`, so a
    shared clamp sink grows unbounded for the session).
  - **The drift guard scans with `ast`, not text**, so a lifted name in a
    docstring, comment or import cannot trip it — and its documented blind spot
    (a copy nested inside a function) is pinned by its own test rather than only
    claimed in prose.
- **Upstream defects identified:** None.

### `depends: [1544_5]`

The task file asked for this to be wired at pick time. It was **not** added, on
purpose: t1544_5 landed and was archived before this task was picked
(commit `7eb74d761`), so the blocking condition the instruction expressed is
already satisfied and a `depends:` edge onto an archived task would only leave
`ait ls` a dangling reference to resolve.
