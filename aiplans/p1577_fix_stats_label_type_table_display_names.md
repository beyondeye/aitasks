---
Task: t1577_fix_stats_label_type_table_display_names.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1577 — Fix stats label×type table display names

## Context

`ait stats` renders the same issue-type vocabulary with **two different display
conventions in one report**. The `### By Task Type` table goes through the
canonical display map (`bug` → `Bug Fixes`), while the adjacent
`### By Issue Type per Label` table bypasses it with a bare
`issue_type.capitalize()` (`bug` → `Bug`). Live output today:

```
### By Task Type - Weekly Trend (Last 4 Weeks)
| Bug Fixes      | 70    | ...
| Refactors      | 8     | ...

### By Issue Type per Label - Weekly Trend (Last 4 Weeks)
| tui          | Bug     | 27    | ...
| tui          | Refactor | 3     | ...
```

This was found while implementing t1544_2, which moved the display map into
`.aitask-scripts/lib/task_category.py::TYPE_DISPLAY_NAMES` and reduced
`aitask_stats.py::get_type_display_name` to a delegator. t1544_2 had to prove
`ait stats` output byte-identical, so it deliberately left the defect alone.

**Intended outcome:** one display convention everywhere — every surface that
renders an issue type reads the canonical map.

### Scope decisions (confirmed with the user during planning)

1. **One convention everywhere**, not a short-form helper. The "the label table
   is deliberately abbreviated to keep the row narrow" hypothesis is falsified
   by the live output: the `:<7` column already prints `Documentation` (13) and
   `Manual_verification` (19) unpadded. It is not a short form — it is a second,
   inconsistent convention.
2. **Include the stats-TUI pane.** Planning turned up a **third** site the task
   did not name: `.aitask-scripts/stats/panes/labels.py:41` labels its "Issue
   types" bar chart with `t.capitalize()`. `task_category.py:145-147` already
   documents "the stats TUI panes need only `type_display_name`" — that consumer
   was anticipated by t1544_2 and never wired up.
3. **Widen the `Type` column to 19** (`Manual_verification`, the longest display
   name over `aitasks/metadata/task_types.txt`). Note Python's `:<N` pads but
   never truncates, so today's output is *ragged*, not cut off.

### Surface inventory (complete)

| Site | State |
|---|---|
| `aitask_stats.py:363` — `### By Task Type` | already correct (`get_type_display_name`) |
| `aitask_stats.py:382` — `### By Issue Type per Label` | **defect** — `.capitalize()` |
| `stats/panes/labels.py:41` — TUI "Issue types" chart | **defect** — `.capitalize()` |
| `aitask_stats_legacy.sh:688` | same defect, but **dead code** — `ait stats` execs `aitask_stats.sh` → `aitask_stats.py`; nothing dispatches the legacy script. Out of scope; recorded at Step 8b. |

No consumer parses the text report: `render_text_report` has exactly two callers
(`aitask_stats.py:511` `main`, and one test). The change is display-only.

## Implementation

### 1. `.aitask-scripts/aitask_stats.py` — label×type table

Reuse the existing delegator `get_type_display_name` (`:213`) rather than
importing `task_category` a second time; the adjacent table at `:363` already
calls it, so both tables end up on one call.

At `:382`, replace the type cell and widen it to 19:

```python
f"| {label:<12} | {get_type_display_name(issue_type):<19} | {total:<5} | "
```

Widen the header and separator rows at `:371-372` to match (the `Type` cell goes
from 9 to 21 chars including its padding spaces; row length 64 → 76, still under
80 columns):

```python
print("| Label        | Type                | Total | W-3 | W-2 | W-1 | This Week |", file=out)
print("|--------------|---------------------|-------|-----|-----|-----|-----------|", file=out)
```

### 2. `.aitask-scripts/stats/panes/labels.py` — TUI "Issue types" chart

Add `from task_category import type_display_name` alongside the existing flat
`from stats_data import ...` import. This resolves because `stats/__init__.py:16-17`
inserts `lib/` into `sys.path` — the same mechanism `stats_data` uses. Then at
`:41`:

```python
plt.bar([type_display_name(t) for t in types], values)
```

This module is imported at TUI startup, so a bad import path would break the
whole stats TUI — verification below drives the real entry point, not a replica.

### 3. `tests/test_aitask_stats_py.py` — discriminating test

Add one test to `TestCollection` (its fixture already has the right shape: no
`task_types.txt`, so `get_valid_task_types()` falls back to
`["bug", "feature", "refactor"]`, and the fixture tasks carry `alpha`/`bug`,
`beta`/`feature`, `gamma`/`refactor`, `epsilon`/`feature`).

```python
def test_label_type_table_uses_canonical_display_names(self):
    data = stats.collect_stats(today=date(2026, 3, 5), week_start_dow=1)
    report = stats.render_text_report(
        data, days=7, verbose=False, week_start_dow=1, today=date(2026, 3, 5),
    )
    section = report.split("### By Issue Type per Label")[1].split("###")[0]
    # Canonical map, not raw.capitalize()
    self.assertIn("| alpha        | Bug Fixes ", section)
    self.assertIn("| gamma        | Refactors ", section)
    self.assertIn("| beta         | Features ", section)
    self.assertNotIn("| Bug ", section)
    self.assertNotIn("| Refactor ", section)
```

Discriminating: `bug`/`refactor`/`feature` are exactly the types whose display
name differs from `.capitalize()`, and the assertions fail against today's code.

### 4. `tests/test_aitask_stats_py.py` — TUI pane test

Add a test that drives the real `_render_issue_types`, patching the module-bound
`render_chart` to capture the `setup_fn` and calling it with a stub `plt` that
records `bar()` labels. The pane module imports cleanly under the ait venv
(verified during planning).

```python
def test_stats_tui_issue_type_chart_uses_canonical_display_names(self):
    import stats.panes.labels as pane_mod
    captured = {}
    class _Plt:
        def bar(self, labels, values): captured["labels"] = list(labels)
        def title(self, *a): pass
    orig = pane_mod.render_chart
    pane_mod.render_chart = lambda setup_fn, container: setup_fn(_Plt())
    try:
        data = stats.collect_stats(today=date(2026, 3, 5), week_start_dow=1)
        pane_mod._render_issue_types(data, object())
    finally:
        pane_mod.render_chart = orig
    self.assertIn("Bug Fixes", captured["labels"])
    self.assertIn("Refactors", captured["labels"])
    self.assertNotIn("Bug", captured["labels"])
```

Import-path detail: the test module must have `.aitask-scripts` and
`.aitask-scripts/lib` on `sys.path` for `import stats.panes.labels`. The existing
`_load_stats_module()` already loads `aitask_stats.py`, which puts `lib` on the
path; add the `.aitask-scripts` root if the import fails.

## Verification

1. **Before/after capture** (the task calls for this explicitly — this change
   alters existing output by design, so an unchanged-output assertion is wrong):
   ```bash
   ./ait stats > /tmp/claude-1000/.../stats_before.txt   # scratchpad
   # ...after the change...
   ./ait stats > .../stats_after.txt
   diff -u .../stats_before.txt .../stats_after.txt
   ```
   Expect: changes confined to the `### By Issue Type per Label` block —
   `Bug`→`Bug Fixes`, `Refactor`→`Refactors`, `Feature`→`Features`,
   `Test`→`Tests`, `Chore`→`Chores`, `Style`→`Style Changes`, plus the widened
   column. `Documentation` / `Enhancement` / `Manual_verification` shift position
   but keep their text (no map entry — `raw.capitalize()` fallback). **No other
   section may change** — in particular `### By Task Type` must be untouched.
2. **Cross-surface parity**, asserted directly rather than against a probe: for
   every type present in both tables, the rendered name must be identical.
   Confirm by eye on the diff, backed by the tests above.
3. `bash tests/run_all_python_tests.sh --test-dir tests` (or narrow with
   `--test-dir` to the stats modules). Read only the last line for the verdict;
   use `set -o pipefail` if piping.
4. **Real entry point for the TUI** — the pane module is imported at startup, so
   an import error would break the whole TUI, not just the chart:
   ```bash
   ./ait stats-tui       # navigate to Labels → "Issue types"
   ```
   Expect bars labeled `Bug Fixes` / `Refactors` / `Features`, and the TUI to
   boot at all.
5. **Negative control:** revert just the `:382` edit and re-run test 3 — the new
   label×type assertion must fail with the `Bug Fixes` mismatch (not an earlier
   error), proving the mutation reaches the probed assertion.

## Step 9 (Post-Implementation)

Standard flow: merge/cleanup and archival per the task-workflow Step 9. Task is
gated on `risk_evaluated` (active set materialized at claim time).

## Risk

### Code-health risk: low
- Changes existing `ait stats` output by design; nothing in-repo parses the text
  report (verified: `render_text_report` has only `main` + one test as callers),
  but an external script scraping the table would see churn. · severity: low ·
  → mitigation: covered by Verification steps 1–2 (explicit before/after capture
  with a bounded expected diff) — no additional mitigation wanted.
- New cross-module import inside a Textual pane module that is loaded at TUI
  startup; a wrong import path would break the whole stats TUI rather than just
  the chart. · severity: low · → mitigation: covered by Verification step 4
  (drives the real `ait stats-tui` entry point) — the path was already confirmed
  during planning (`stats/__init__.py:16-17` puts `lib/` on `sys.path`).

### Goal-achievement risk: low
- t1544_4 renders the new unified category axis over the same vocabulary and
  could re-introduce a second convention if it inherits from the wrong side.
  · severity: low · → mitigation: out of scope for this task; recorded in Final
  Implementation Notes as a forward pointer, not an edit to t1544_4's file.

Both dimensions are `low` and every listed concern is already discharged by a
step in this plan's Verification section, so **no additional spawned or inline
mitigation is proposed** (`risk_mitigations_planned = false`). Listing them
here rather than writing "None identified." keeps the reasoning visible.

## Final Implementation Notes

- **Actual work done:** Exactly the three planned edits, no deviations in shape.
  `aitask_stats.py:382` now calls `get_type_display_name(issue_type)` instead of
  `issue_type.capitalize()`, with the `Type` column widened `:<7` → `:<19` and
  the header/separator rows widened to match. `stats/panes/labels.py:42` now
  labels its bar chart with `type_display_name(t)` (new
  `from task_category import type_display_name`). Two tests added to
  `tests/test_aitask_stats_py.py::TestCollection`, one per surface.
- **Deviations from plan:** One test-authoring correction. The plan's negative
  assertions were `assertNotIn("| Bug ", section)` — substring-unsafe, since
  `"| Bug "` is a substring of `"| Bug Fixes"`, so it failed against the *fixed*
  code. Replaced with a per-row parse of the Type cell plus `assertEqual`, which
  is both strictly discriminating and independent of the column width (a future
  width change will not break it). A separate `assertIn` on the header row pins
  the width instead. The pane test's `assertNotIn("Bug", captured["labels"])` was
  already safe — `captured["labels"]` is a list, so `in` is element membership.
- **Issues encountered:** Driving the live `ait stats-tui` to the "Issue types"
  pane by keystroke proved unreliable (`]` cycles *projects*, not panes; Tab
  focus did not reach the `#sidebar` ListView). Verified instead by (a) booting
  the real TUI in a tmux pane to prove the import chain, and (b) rendering
  `PANE_DEFS["labels.issue_types"]` inside a real Textual app under `run_test`
  and reading `widget.render().plain` — which printed the axis labels
  `Bug Fixes / Chores / Enhancement / Manual_verification / Tests`. Note
  `Static.renderable` was `None` there; `render()` is the working probe.
- **Key decisions:**
  - *One display convention everywhere*, confirmed with the user. The competing
    "the label table is deliberately abbreviated" reading is falsified by the
    live output: the `:<7` column already printed `Documentation` (13) and
    `Manual_verification` (19) unpadded, so it was never a short form.
  - *Width 19*, sized to the longest display name (`Manual_verification`). Note
    Python's `:<N` pads but never truncates, so the pre-fix output was ragged,
    not cut off — the task's "truncates" wording was imprecise.
  - *Scope widened to the stats-TUI pane* (a third site the task did not name),
    because `task_category.py:145-147` already documents "the stats TUI panes
    need only `type_display_name`" — that consumer was anticipated by t1544_2
    and simply never wired up. Leaving it would have made "one convention
    everywhere" false on a live surface.
  - `### By Task Type`'s own `:<14` overflow on `Manual_verification` was left
    alone: pre-existing, unaffected by this change, and outside the task.
- **Verification evidence:** before/after `ait stats` diff confined to the target
  section (only other delta: the `Generated:` timestamp); cross-surface parity
  went from 5 label-table names with no counterpart in the type table to 0; full
  Python suite `PASSED (runner=pytest, exit=0)`; two isolated negative controls
  each failed their own named test at the probed assertion while the other test
  stayed green.
- **Concurrency note:** a second session was active in this repo during
  implementation — it landed `t1560_1` mid-task and held uncommitted work in
  `lib/stats_data.py`, `lib/task_category.py`, `lib/work_report_gather.py`,
  `tests/test_stats_multistage.py`, `tests/test_task_category.py` (t1544_3
  shaped). It touches neither `TYPE_DISPLAY_NAMES` nor `type_display_name`, so
  there was no conflict; the code commit was path-scoped (`git commit -o --`) to
  the three files above so none of that work was swept in. The full-suite run
  did include those in-flight edits.
- **Forward pointer:** t1544_4 renders the new unified category axis over this
  same vocabulary and should take the `type:` half from
  `task_category.type_display_name` / `category_display_name` explicitly rather
  than inheriting a second convention. Recorded here rather than by editing
  t1544_4's task file.
- **Upstream defects identified:** `.aitask-scripts/aitask_stats_legacy.sh:688 — the label x type table renders types with a bare ${issue_type^} while the same script's own get_type_display_name is used at :651, the identical two-convention defect fixed here; the script is unreachable from the CLI (ait stats execs aitask_stats.sh -> aitask_stats.py) but still receives maintenance touches`
