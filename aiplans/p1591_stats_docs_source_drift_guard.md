---
Task: t1591_stats_docs_source_drift_guard.md
Base branch: main
Output branch: main
---

# t1591 — Stats docs ↔ source drift guard

## Context

t1544_6 fixed stats docs that had drifted from the code ("Four presets" against
seven shipped; the skill doc listing 7 CSV columns against 12). It checked the
corrected prose by hand. The preset table, the 12- and 6-column CSV lists and the
13-entry "Statistics provided" list still copy source values by hand, and nothing
fails when they drift. This task turns that hand check into a committed test.

Pure test addition: **no source or doc file changes.**

## Verified facts (probed read-only during planning)

- `DEFAULT_PRESETS` (`.aitask-scripts/stats/stats_config.py:17`) mapped through
  `PANE_DEFS[i].title` (`stats.panes`) equals the table under
  `## Built-in layouts (presets)` in `website/content/docs/tuis/stats/_index.md`
  (rows `| **name** | A · B · C |`). Comparison → `True`.
- `write_csv(path, [])` emits header
  `date,…,created_at,category` (12). `write_backlog_csv` with an empty
  `StatsData` emits `week_ending,category,open,arrived,departed,net`. These match
  `board-stats.md:94,96` and `.claude/skills/aitask-stats/SKILL.md:69,72`.
- `main([])` on a **one-task synthetic repo** (temp `TASK_DIR` / `ARCHIVE_DIR` /
  `TASK_TYPES_FILE`, the same patch pattern as `tests/test_aitask_stats_py.py:787-793`)
  with `load_verified_rankings` stubbed to a one-operation synthetic
  `VerifiedRankingData` returns 0 and prints 13 `^### ` headings in the order of
  both numbered doc lists. `render_text_report` emits 12 of them unconditionally,
  and the rankings block adds the 13th. `#### <op>` sub-headings don't match `^### `.

## Implementation

### 1. New file `tests/test_stats_docs_drift.py` (unittest, no runner registration needed)

Module loading: same `importlib` pattern as `tests/test_aitask_stats_py.py:22-33`,
but with a **distinct module name** (`aitask_stats_docs_drift`) so it never
replaces that file's `sys.modules["aitask_stats_py"]` under a shared pytest worker.
`sys.path.insert(0, <repo>/.aitask-scripts)` so that `stats.stats_config` and
`stats.panes` import. `stats_data` comes from `sys.modules["stats_data"]`.

Doc paths are constants: `WEBSITE_TUI = website/content/docs/tuis/stats/_index.md`,
`WEBSITE_CMD = website/content/docs/commands/board-stats.md`,
`SKILL_DOC = .claude/skills/aitask-stats/SKILL.md`.

**Strict parsers.** Each takes the doc text and raises `DocParseError(AssertionError)`
when the anchor is missing or yields nothing, so a renamed heading or a restructured
table **fails, never skips**:

- `section(text, heading)`: the text after an exact heading line, up to the next
  heading of the same or a higher level. Raises if the heading is absent.
- `parse_preset_table(text)`: works on `section(text, "## Built-in layouts (presets)")`.
  Every line starting with `|`, apart from the header and separator rows, must
  match `^\| \*\*(\w+)\*\* \| (.+?) \|$`. A table line that doesn't match raises.
  Panes are split on `·` and stripped. It raises on zero rows or a duplicate
  preset name, and returns a dict.
- `parse_inline_columns(text, anchor_regex)`: website form. Captures the
  backticked list after the anchor. `--csv` uses
  ``r"`--csv` writes one row per \*completed\* task: `([^`]+)`"`` and
  `--csv-backlog` uses ``r"`--csv-backlog` writes `([^`]+)`"``. The capture is
  split on `,` and stripped. Raises on no match or an empty list.
- `parse_bullet_columns(text, label_regex)`: skill form. Captures the first `- `
  line after `**CSV Export (\`--csv\`):**…` or `**Backlog Export (\`--csv-backlog\`):**…`.
  Same split and the same raises.
- `parse_numbered_bold_list(region)`: **every** line in the bounded region that
  looks like an ordered-list item (`^\s*\d+[.)]\s`) must match the strict form
  `^(\d+)\. \*\*(.+?)\*\*`. One that doesn't, such as an unbolded
  `14. Extra report section`, raises `DocParseError` instead of being skipped.
  The numbers must run 1..N without gaps, and N = 0 raises. Returns the bold labels.
  (Review finding: a bold-only regex would silently ignore an unbolded extra
  entry, so the guard has to inspect every numbered line in the region.)
  - website region: the text after `**Statistics provided:**` in `board-stats.md`
    (raises if the anchor is absent), up to the next line starting with `**` or
    `#`. The next line starting with `**` is `**Data sources:**`. The paragraph
    between the list and that line contains no numbered lines, as probed.
  - skill region: `section(text, "## Statistics Provided")`.

**Source side (synthetic, no repo data):**

- `source_presets()` = `{k: [PANE_DEFS[i].title for i in v] for k, v in DEFAULT_PRESETS.items()}`.
- `source_csv_headers()`: in a `TemporaryDirectory`, `write_csv(p, [])` and
  `write_backlog_csv(p, data, build_backlog_axis(data, backlog_week_offsets(8)), today, 1)`,
  then read row 0 of each with `csv.reader`.
- `source_section_headings()`: drives the **real command assembly**: `main([])`
  with stdout captured (`contextlib.redirect_stdout`), asserting exit 0. It keeps
  the lines that start with `### `. Concatenating `render_text_report` with
  `render_verified_rankings` would copy `main()`'s print order into the test, and
  a later reorder or drop in `main()` would go unseen (second review finding,
  folded in because it costs little). Default args give `days=7` and
  `backlog_weeks=8`. No `--csv` flag is passed, so nothing is written. The
  rankings come from the synthetic `VerifiedRankingData(by_window={"pick":
  {"all_providers": {"all_time": [VerifiedModelEntry("m", "M", "all_providers",
  80, 3)]}}}, operations=["pick"])`. `load_verified_rankings` is stubbed on the
  loaded module (`main` resolves it as a module global) and restored in
  `tearDownClass`. Probed: rc 0 and the 13 headings, in order.
- A minimal synthetic-repo fixture (`setUpClass` / `tearDownClass`): a temp
  `aitasks/archived/` holding **one** `Done` task
  (`created_at: 2026-01-01 09:00`, `completed_at: 2026-01-02 09:00`,
  `issue_type: feature`), because `main()` early-exits on an empty repo, plus an
  empty `aitasks/metadata/`. It patches `TASK_DIR`, `ARCHIVE_DIR` and
  `TASK_TYPES_FILE` on the loaded module and on `stats_data`, restoring them in
  `try/finally` exactly as `test_aitask_stats_py.py` does. The CSV-header helper
  builds its data from the same fixture with `collect_stats(today=…, week_start_dow=1)`.
  The headings and the CSV headers don't depend on the fixture's contents or on
  `date.today()`.

**The section pin table (claim 3).** Doc labels are prose ("Daily breakdown") and
headings are code ("### Daily Completions (Last 7 Days)"), so pairing them needs an
explicit table. That table is the single place a new section has to be registered:

```python
SECTIONS = [  # (emitted heading, board-stats.md label, aitask-stats SKILL.md label)
    ("### Summary", "Summary", "Summary"),
    ("### Backlog Level (Open Tasks) - Weekly (Last 8 Weeks)", "Backlog level", "Backlog Level"),
    ("### Backlog Net Flow (Arrivals - Departures) - Weekly (Last 8 Weeks)", "Backlog net flow", "Backlog Net Flow"),
    ("### Daily Completions (Last 7 Days)", "Daily breakdown", "Daily Breakdown"),
    ("### Average Completions by Day of Week", "Day of week averages", "Day of Week Stats"),
    ("### Pipeline Timing (gated tasks)", "Pipeline timing", "Pipeline Timing"),
    ("### Completions by Label - Weekly Trend (Last 4 Weeks)", "Label weekly trends", "Label Weekly Trends"),
    ("### Label Avg by Day of Week (Last 30 Days)", "Label day-of-week", "Label Day-of-Week Breakdown"),
    ("### By Task Type - Weekly Trend (Last 4 Weeks)", "Task type trends", "Task Type Weekly Trends"),
    ("### By Issue Type per Label - Weekly Trend (Last 4 Weeks)", "Label + type trends", "Features/Bugs by Label Trends"),
    ("### By Code Agent - Weekly Trend (Last 4 Weeks)", "Code agent trends", "Code Agent Weekly Trends"),
    ("### By LLM Model - Weekly Trend (Last 4 Weeks)", "LLM model trends", "LLM Model Weekly Trends"),
    ("### Verified Model Rankings", "Verified model rankings", "Verified Model Rankings"),
]
```

Labels are copied verbatim from the two docs at implementation time.

**Tests** (each `assertEqual` carries a `msg` naming the doc file, the section and
the fix: "update the doc (and SECTIONS) to match the source"):

- `TestPresetTable.test_website_table_matches_shipped_presets`: parsed table == `source_presets()`.
- `TestCsvColumns`: four tests, {website, skill} × {`--csv`, `--csv-backlog`}. Each
  checks the parsed list == the emitted header, order included.
- `TestSectionList`:
  - `test_source_headings_match_pin_table`: the emitted headings == `[h for h, _, _ in SECTIONS]`.
    A new, removed, renamed or reordered section in code fails here, and the message
    says to add it to both doc lists and to SECTIONS.
  - `test_website_list_matches`: the website labels == column 2.
  - `test_skill_list_matches`: the skill labels == column 3.
- `TestGuardsFailClosed`: in-file negative controls on **mutated strings only**,
  never the real files (no probe edits in the shared worktree):
  - the doc text with its anchor heading removed → each parser raises `DocParseError`
    (preset section, both CSV anchors on both forms, both numbered lists);
  - a malformed preset table row (`| overview | Summary |` without bold) → raises;
  - a numbered list with a gap (1, 3) → raises;
  - an **unbolded numbered entry** inside the bounded list region raises, on both
    doc sites. One case appends `14. Extra report section` after item 13 and
    another inserts an unbolded line mid-list. The first case is the exact one
    the review probe showed a bold-only regex passes;
  - mutants that must compare **unequal**: one preset pane title renamed in a copy of
    the real doc, one CSV column dropped, one section entry removed. Each is parsed
    and checked with `assertNotEqual` against the source, which proves the
    comparisons can detect drift.

### 2. Nothing else

No change to `aitask_stats.py`, `stats_config.py` or any doc. `.agents/` and
`.opencode/` already carry only the flag list, which `aitask_skill_verify.sh`
covers. The python runner discovers `test_*.py` automatically.

## Verification

1. `~/.aitask/venv/bin/python -m pytest tests/test_stats_docs_drift.py -v` (or
   `python -m unittest tests.test_stats_docs_drift -v`) passes all tests.
2. `bash tests/run_all_python_tests.sh --test-dir <scratch dir with a copy/symlink of
   the new file>` is optional. The direct run plus
   `~/.aitask/venv/bin/python -m pytest tests/test_stats_docs_drift.py tests/test_aitask_stats_py.py`
   in **one process** proves the two files do not collide on module state.
3. The negative-control class itself is the red proof: it shows each parser fails
   closed and each comparison detects a mutation, without touching the real files.
4. Step 9 (Post-Implementation) covers commit, archival and merge
   (current-branch mode).

## Risk

### Code-health risk: low
None identified. (Considered: the SECTIONS pin table is a second hand copy of the
headings, but it sits inside the guard and a mismatch fails loudly, so it can't drift
silently. A cosmetic heading rename failing the test is the intended behaviour. The
change adds one test file and touches no source.)

### Goal-achievement risk: low
None identified. (Considered: a guard that passes vacuously is designed out by strict
parsers, which check every numbered line in the region and not only the bolded
ones, plus the in-file negative controls. The section order is read from the real
`main()` assembly, not from a copy of it. Both doc sites are covered for claims 2
and 3. The render is synthetic, so the test doesn't depend on repo data, as the task
requires.)

## Implementation progress

- [x] `tests/test_stats_docs_drift.py` written as planned (18 tests: 1 preset, 4 CSV,
  3 section-list, 10 fail-closed negative controls). No other file touched.
- Deviation (minor): CSV anchors use one `parse_columns(text, pattern)` for both
  the website (inline backticks) and skill (bullet) forms instead of two
  functions, and require **exactly one** match, so two disagreeing copies of a
  list in one doc also fail.
- `section()` ignores `#` lines inside ``` fences, so a shell comment in a code
  block can't end a section early.

## Verification results

- `~/.aitask/venv/bin/python -m pytest tests/test_stats_docs_drift.py -v` → 18 passed.
- One process, both orders, with `tests/test_aitask_stats_py.py` → 76 passed each
  time (no module-state collision).
- `python -m unittest tests.test_stats_docs_drift` (the runner's fallback backend) → OK.
- Ad-hoc mutant on the `main()` route: stubbing `render_verified_rankings` to `""`
  → 12 headings instead of 13, so the drift is detected. After the stub is
  restored, the next call returns the full pinned list.

## Final Implementation Notes
- **Actual work done:** Added `tests/test_stats_docs_drift.py` (18 unittest tests,
  pytest- and unittest-runnable). It guards the three hand-pinned doc claims t1544_6
  had checked by hand:
  1. the stats TUI preset table == `DEFAULT_PRESETS` × `PANE_DEFS[...].title`;
  2. the `--csv` and `--csv-backlog` column lists, on both the website and skill
     doc sites, == the headers `write_csv` / `write_backlog_csv` emit;
  3. the numbered "Statistics provided" lists, on both doc sites, == the `### `
     headings `main()` prints, paired through the in-test `SECTIONS` table.
  The source side is synthetic: a one-archived-task temp repo patched into
  `aitask_stats` + `stats_data`, with `load_verified_rankings` stubbed. No assertion
  depends on repository task data.
- **Deviations from plan:** One `parse_columns(text, pattern)` serves both CSV doc
  forms, requiring exactly one match (stricter than planned). `section()` skips
  `#` lines inside ``` fences. No other deviations.
- **Issues encountered:** None. Both review findings raised at plan approval were
  folded into the plan before implementation: every numbered line in the list
  region must be bolded, and the section order is read from the `main()` route.
- **Key decisions:** The `SECTIONS` pin table is the single registration point for
  a new report section. A cosmetic heading rename fails the test by design. Negative
  controls mutate in-memory copies of the real docs, never the files. A `_mutate()`
  helper asserts that the target text still exists, so a stale control fails
  instead of passing vacuously.
- **Upstream defects identified:** None
