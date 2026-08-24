---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t1544_3]
issue_type: feature
status: Done
labels: [reporting, tui, backlog]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1544
implemented_with: claudecode/opus5
created_at: 2026-08-17 22:07
updated_at: 2026-08-24 18:32
completed_at: 2026-08-24 18:32
---

## Context

Fifth child of t1544 (backlog level + net flow by category in `ait stats`).
Parent plan: `aiplans/p1544_stats_backlog_and_net_flow_by_category.md`.
Depends on **t1544_3** (the data layer). Parallel with t1544_4 (the CLI) — both
are pure renderings of the same `StatsData` fields, neither depends on the other.

Read t1544_3's Final Implementation Notes first for the final `backlog_levels()`
signature and field names.

## Deliverable 1 — `stats/panes/backlog.py` (new), two panes

**`backlog.level`** — a `DataTable`, categories x weeks, mirroring
`stats/panes/labels.py::_render_heatmap`.

The corpus resolves to **17 distinct categories** (14 present live), so a
17-row x 9-column table is the realistic worst case. Add a **row cap with an
`Other` bucket**, in the style of `lib/stats_data.py::chart_totals`'s `limit`
handling, rather than letting the table grow unbounded. Rank rows by current
level descending. Include the follow-ups / genuine subtotal rows and
`TOTAL OPEN`, as the CLI does.

**`backlog.netflow`** — arrivals vs departures per week, **split by category**.

A plain `multiple_bar(weeks, [arrivals, departures])` mirroring
`velocity.py::_render_parent_child` would be a *totals* chart and would **fail**
t1544's acceptance criterion, which requires the net-flow surface to be split by
the unified category axis. Use top-N categories + `Other`. Note
`render_chart` defaults to `width=100`, so per-category series must be **capped**,
not stacked — 8 weeks x 2 series is already 16 bars. If the chart cannot carry
the category split legibly, a second `DataTable` (categories x weeks, signed
net) alongside a totals chart is an acceptable shape — but the category
dimension must be present somewhere in this pane.

Register both with `register(PaneDef("backlog.<name>", "<Title>", "Backlog", _render))`
at the bottom of the module.

## Deliverable 2 — the import trap

**Add the new module to the eager import list in `stats/panes/__init__.py`.**

```python
from . import overview, labels, agents, velocity, sessions, pipeline  # noqa: F401
```

That list is what runs each module's `register()`. A pane module missing from it
never registers — and a *wrong* entry is a `ModuleNotFoundError` that stops the
**whole TUI from starting**. This exact trap is the subject of the sibling risk
task t1305.

Guard it with a test that imports the package and asserts `"backlog.level"` and
`"backlog.netflow"` are in `PANE_DEFS`.

Note the list's order also determines `PANE_DEFS` iteration order, which the
pane-selector modal relies on to group by category.

## Deliverable 3 — the preset, and what NOT to do

Add `"backlog": ["backlog.level", "backlog.netflow"]` to
`stats/stats_config.py::DEFAULT_PRESETS`.

**Change no config file.** Do **not** edit
`aitasks/metadata/stats_config.json`, and do **not** delete anything from it.

The parent task's instruction to "add the preset to both sources or you add a
third divergence" **rests on a false premise**, verified during planning:
`load_layered_config` uses `deep_merge`, which merges dicts **per key** and only
replaces **lists**. `stats_config.load()["presets"]` already contains the
`sessions` preset even though the JSON lacks it — so the JSON's missing key masks
nothing, and adding a new preset key to `DEFAULT_PRESETS` alone is sufficient
**by mechanism**, not by luck.

An earlier draft of the parent plan proposed deleting the JSON's redundant
`presets` block. That was **withdrawn**: it holds no genuine overrides *in this
checkout*, which proves the committed file is redundant **here** — not that the
data-branch JSON is never a real override surface in another project. Deleting it
would remove a supported project-local layout override to fix a cosmetic
duplication, and could silently discard a user's layout.

## Deliverable 4 — the precedence test (this is the real deliverable)

The override contract is currently neither documented nor covered. Add a test
asserting the **effective** config via `stats_config.load()` — never an equality
test between the two literals, which would lock the duplication in permanently:

1. a preset key present only in `DEFAULT_PRESETS` (the new `backlog`) appears in
   the effective presets;
2. a `presets.<name>` **list** present in the JSON **replaces** the code list for
   that preset. This is the real, unnoticed drift — a pane added to an existing
   code preset **is** masked by a project JSON that pins that preset. The test
   **pins** the behaviour; it does not change it;
3. `backlog` survives alongside an existing JSON `presets` block — i.e. adding
   the pane cannot discard a user's overrides.

Changing the list semantics to merge-instead-of-replace is a behaviour change to
every preset and is **out of scope**. The test documents the current contract so
a future task can change it deliberately. Consider surfacing that as a follow-up.

## Deliverable 5 — horizon and week start

- **Horizon:** read `stats_data.BACKLOG_WEEKS_DEFAULT` — do **not** declare a
  pane-local `_BACKLOG_WEEKS`. The CLI flag's default reads the same constant;
  a second literal here is exactly how the two surfaces drift into showing
  different windows for the same metric. Add a test asserting the pane resolves
  to the constant.
- **Week start:** stays Monday, like every other pane. Say so in a code comment
  rather than inheriting it silently, and point at the existing t597_4 TODO in
  `stats/panes/overview.py`. Two reasons: `stats_app.py` hardcodes
  `week_start_dow=1` at both `collect_stats` call sites, **and** the string->dow
  resolver `resolve_week_start` lives in the CLI, not in `lib/`, so honouring
  `stats_config`'s persisted-but-unread `week_start` key would require moving
  that resolver first. Out of scope here.

## Key files to modify

- `.aitask-scripts/stats/panes/backlog.py` — **new**
- `.aitask-scripts/stats/panes/__init__.py` — the eager import list
- `.aitask-scripts/stats/stats_config.py` — `DEFAULT_PRESETS`
- `tests/` — pane-registration test, preset-precedence test, horizon-constant test

## Reference files for patterns

- `.aitask-scripts/stats/panes/base.py` — `PaneDef`, `register`, `render_chart`
  (plotext -> ANSI -> `Static`, `width=100`, `height=22`), `empty_state`
- `.aitask-scripts/stats/panes/labels.py` — `_render_heatmap`: the
  `DataTable(zebra_stripes=True)` category x week template
- `.aitask-scripts/stats/panes/velocity.py` — `_render_parent_child`: the
  two-series `multiple_bar` template with its no-`multiple_bar` fallback
- `.aitask-scripts/stats/panes/sessions.py` — the simplest complete pane module
  (38 lines), the shape to copy
- `.aitask-scripts/lib/stats_data.py` — `chart_totals` (the top-N + `Other`
  idiom), `build_chart_title`, `backlog_levels`
- `.aitask-scripts/lib/config_utils.py` — `load_layered_config`, `deep_merge`
- `aidocs/framework/tui_conventions.md` — read before editing any Textual TUI

## Verification steps

```bash
bash tests/run_all_python_tests.sh --test-dir tests
ait stats-tui        # app starts at all (the import trap)
# select the `backlog` layout in the layout picker; view both panes;
# confirm each renders real data rather than its empty state
```

- Confirm the other five presets still list their original panes.
- Confirm the `DataTable` is readable at a normal terminal width and that the
  row cap engages on the real corpus.
- Confirm the netflow pane visibly carries the **category** dimension.

Note `tests/test_collection_parity.py` enforces unittest-count == pytest-count
per module; keep new test files to plain `unittest.TestCase` methods.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-24T14:18:34Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-24T15:32:06Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-24T15:32:43Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:e4da8669c0e072df

> **✅ gate:risk_evaluated** run=2026-08-24T15:32:43Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1544_5/risk_evaluated_2026-08-24T15:32:43Z-risk_evaluated-a1.log`
