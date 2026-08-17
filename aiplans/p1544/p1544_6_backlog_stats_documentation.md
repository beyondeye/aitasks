---
Task: t1544_6_backlog_stats_documentation.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_1_*.md, aitasks/t1544/t1544_2_*.md, aitasks/t1544/t1544_3_*.md, aitasks/t1544/t1544_4_*.md, aitasks/t1544/t1544_5_*.md, aitasks/t1544/t1544_7_*.md, aitasks/t1544/t1544_8_*.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_*_*.md
Base branch: main
Output branch: main
---

# p1544_6 — Backlog stats documentation

## Goal

Document the backlog and net-flow surfaces, and fix the pre-existing errors on
the same pages. A first-class docs deliverable per
`aidocs/framework/planning_conventions.md`, not a verification afterthought.

**Write from the shipped behaviour, not from the plan.** Read t1544_4's and
t1544_5's Final Implementation Notes, then check every number and column list
against live output.

Read `aidocs/framework/documentation_conventions.md` first: current-state only
(no version history, no "newly added" framing), genericize any passage naming
specific coding agents, and *correct* wrong sentences outright rather than
adding a contradicting one beside them.

## Implementation steps

### 1. `website/content/docs/tuis/stats/_index.md` — two pre-existing errors

- **"Four presets ship with the framework, each bundling three panes"** with a
  four-row table. There are already **six** (`overview`, `labels`, `agents`,
  `velocity`, `pipeline`, `sessions`), and they do not all bundle three
  (`agents` has four, `pipeline` two). With `backlog` it becomes seven. Rewrite
  the sentence and complete the table.
- **"Presets are defined in `aitasks/metadata/stats_config.json` and are
  read-only at runtime"** is **factually wrong**. They are defined in
  `.aitask-scripts/stats/stats_config.py::DEFAULT_PRESETS`. The JSON is an
  *optional project-local override layer*: `load_layered_config` merges it with
  `deep_merge`, which merges **dicts per key** and **replaces lists** — so a
  preset present only in code still appears, while a preset *list* pinned in the
  JSON replaces the code list for that preset. Document that precedence; it is
  exactly what t1544_5's precedence test pins, so the doc and the test must say
  the same thing.

  The "Config persistence" section further down describes the project/user layer
  split correctly — reconcile the two passages instead of leaving them in
  conflict.

### 2. `website/content/docs/tuis/stats/_index.md` — the new preset

Add the `backlog` row and describe the two panes.

### 3. `website/content/docs/commands/board-stats.md`

- Option table: add `--backlog-weeks N` and `--csv-backlog [FILE]`.
- "Statistics provided" numbered list: add the two new sections.
- **"CSV export format"** pins the exact 10-column list; it becomes 12
  (`created_at`, `category` appended). State that open tasks are **not** rows in
  that table, so the backlog level is not reproducible from it — the series
  lives in `--csv-backlog`. Document the new file's columns:
  `week_ending, category, open, arrived, departed, net`.
- **"Data sources"** already documents the completion fallback chain for the
  existing counters. Extend it: the backlog sections use `completed_at`
  (falling back to `updated_at` for `Done`/`Completed`), **not** the
  `merge_approved`/`review_approved` ledger stamps the other sections prefer, so
  the two can name a different week for ~0.3% of tasks. Also state that the
  backlog population scans **active** tasks as well as archived ones, that a
  `Done`-but-unarchived task counts as departed, that **Postponed** tasks count
  as open, and that **Folded** tasks are excluded.

### 4. `website/content/docs/skills/aitask-stats.md`

Update the description of what the report contains.

### 5. `website/content/docs/tuis/_index.md`

Only if it mirrors a per-TUI pane or preset list — check, then update if so.

## Files

- `website/content/docs/commands/board-stats.md`
- `website/content/docs/tuis/stats/_index.md`
- `website/content/docs/skills/aitask-stats.md`
- `website/content/docs/tuis/_index.md` (conditional)

## Verification

```bash
cd website && npm install && hugo build --gc --minify
```

- The build succeeds with no broken `relref` links.
- Every number and column list matches live output, checked directly:
  ```bash
  ./ait stats --help
  ./ait stats --csv /tmp/t.csv --csv-backlog /tmp/b.csv
  head -1 /tmp/t.csv && head -1 /tmp/b.csv
  ```
- The preset count in the prose matches
  `.aitask-scripts/stats/stats_config.py::DEFAULT_PRESETS`.
- The precedence description matches what t1544_5's test asserts.
