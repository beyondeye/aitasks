---
Task: t1544_5_stats_tui_backlog_panes.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_1_*.md, aitasks/t1544/t1544_2_*.md, aitasks/t1544/t1544_3_*.md, aitasks/t1544/t1544_4_*.md, aitasks/t1544/t1544_6_*.md, aitasks/t1544/t1544_7_*.md, aitasks/t1544/t1544_8_*.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_*_*.md
Base branch: main
Output branch: main
---

# p1544_5 — Stats TUI backlog panes

## Goal

Expose t1544_3's two series in the stats TUI as registered panes reachable from
a preset, with the same information and the same horizon as the CLI. Parallel
with t1544_4 — neither depends on the other.

Read `aidocs/framework/tui_conventions.md` before editing, and t1544_3's Final
Implementation Notes for the helper signature and field names.

## Implementation steps

1. **`.aitask-scripts/stats/panes/backlog.py`** — new module. Copy the shape of
   `stats/panes/sessions.py` (the simplest complete pane module).

2. **`backlog.level`** — a `DataTable(zebra_stripes=True)`, categories × weeks,
   mirroring `stats/panes/labels.py::_render_heatmap`.

   The corpus resolves to **17 distinct categories** (14 present live), so
   17 rows × 9 columns is the realistic worst case. Add a **row cap with an
   `Other` bucket**, in the style of `lib/stats_data.py::chart_totals`'s `limit`
   handling, rather than letting the table grow unbounded. Rank rows by current
   level descending, and include the follow-ups / genuine subtotals and
   `TOTAL OPEN` as the CLI does.

3. **`backlog.netflow`** — arrivals vs departures per week, **split by
   category**.

   A plain `multiple_bar(weeks, [arrivals, departures])` mirroring
   `velocity.py::_render_parent_child` is a *totals* chart and would **fail**
   the parent's acceptance criterion, which requires the net-flow surface to
   carry the category axis. Use top-N categories + `Other`. `render_chart`
   defaults to `width=100`, and 8 weeks × 2 series is already 16 bars, so
   per-category series must be **capped**, not stacked. If the chart cannot
   carry the split legibly, a second `DataTable` (categories × weeks, signed net)
   beside a totals chart is an acceptable shape — but the category dimension
   must be present somewhere in this pane.

4. **Register both** at the bottom of the module:
   `register(PaneDef("backlog.level", "<Title>", "Backlog", _render_level))` and
   the same for `backlog.netflow`.

5. **Add the module to the eager import list in `stats/panes/__init__.py`.**
   That list is what runs each module's `register()`; a module missing from it
   never registers, and a wrong entry is a `ModuleNotFoundError` that stops the
   **whole TUI from starting** (the subject of sibling risk task t1305). The
   list's order also determines `PANE_DEFS` iteration order, which the
   pane-selector modal relies on to group by category.

6. **Preset** — add `"backlog": ["backlog.level", "backlog.netflow"]` to
   `stats/stats_config.py::DEFAULT_PRESETS`.

   **Change no config file.** Do not edit or delete anything in
   `aitasks/metadata/stats_config.json`.

   The parent task's "add it to both sources" instruction rests on a false
   premise, verified during planning: `load_layered_config` uses `deep_merge`,
   which merges dicts **per key** and only replaces **lists**.
   `stats_config.load()["presets"]` already contains the `sessions` preset even
   though the JSON lacks it — so adding a new preset key to `DEFAULT_PRESETS`
   alone is sufficient **by mechanism**, not by luck. An earlier draft proposed
   deleting the JSON's redundant `presets` block; that was withdrawn because it
   holds no overrides *in this checkout*, which does not prove the data-branch
   JSON is never a real override surface elsewhere.

7. **Horizon** — read `stats_data.BACKLOG_WEEKS_DEFAULT`. Do **not** declare a
   pane-local `_BACKLOG_WEEKS`; the CLI flag's default reads the same constant,
   and a second literal is how the two surfaces drift apart.

8. **Week start** — stays Monday, like every other pane. Say so in a code
   comment pointing at the existing t597_4 TODO in `stats/panes/overview.py`,
   rather than inheriting it silently. Two reasons: `stats_app.py` hardcodes
   `week_start_dow=1` at both `collect_stats` call sites, and the string→dow
   resolver `resolve_week_start` lives in the CLI rather than `lib/`, so
   honouring `stats_config`'s persisted-but-unread `week_start` key would need
   that resolver moved first. Out of scope.

## Files

- `.aitask-scripts/stats/panes/backlog.py` (new)
- `.aitask-scripts/stats/panes/__init__.py`
- `.aitask-scripts/stats/stats_config.py`
- `tests/` — pane-registration, preset-precedence, horizon-constant

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests
ait stats-tui
```

Automated:

- **Pane registration** — import the package and assert `"backlog.level"` and
  `"backlog.netflow"` are in `PANE_DEFS`. This is the guard against the
  `ModuleNotFoundError` trap.
- **Horizon** — the pane resolves to `BACKLOG_WEEKS_DEFAULT`, asserted against
  the constant rather than the number 8.
- **Preset precedence** — assert the **effective** config via
  `stats_config.load()`, never an equality test between the two literals (which
  would lock the duplication in permanently):
  1. a preset key present only in `DEFAULT_PRESETS` (the new `backlog`) appears
     in the effective presets;
  2. a `presets.<name>` **list** in the JSON **replaces** the code list for that
     preset — the real, unnoticed drift, since a pane added to an existing code
     preset is silently masked for any project that pins it. The test **pins**
     this behaviour; changing it to merge-instead-of-replace is a behaviour
     change to every preset and is out of scope (surface it as a follow-up);
  3. `backlog` survives alongside an existing JSON `presets` block — adding the
     pane cannot discard a user's overrides.

Manual (also seeded on t1544_7's checklist):

- `ait stats-tui` starts at all.
- The `backlog` layout appears in the layout picker and both panes appear in the
  sidebar.
- Each pane renders real data rather than its empty state; the level table is
  readable at a normal terminal width and its row cap engages on the real
  corpus; the netflow pane visibly carries the category dimension.
- The other five presets still list their original panes and still render.
- The TUI's backlog numbers match `ait stats` for the same week and horizon.

Keep new test files to plain `unittest.TestCase` methods —
`tests/test_collection_parity.py` enforces unittest-count == pytest-count per
module.
