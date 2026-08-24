---
Task: t1544_6_backlog_stats_documentation.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_7_manual_verification_stats_backlog.md, aitasks/t1544/t1544_8_backlog_stats_retrospective.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_1_session_discovery_dedupe.md, aiplans/archived/p1544/p1544_2_task_category_axis_module.md, aiplans/archived/p1544/p1544_3_backlog_flow_collection.md, aiplans/archived/p1544/p1544_4_cli_backlog_sections_and_csv.md, aiplans/archived/p1544/p1544_5_stats_tui_backlog_panes.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-24 22:40
---

# p1544_6 — Backlog stats documentation

## Context

t1544 added a **backlog** dimension to `ait stats` — a weekly open-task level by
category plus the net flow that explains its movement. t1544_4 shipped the CLI
sections, flags and CSV surfaces; t1544_5 shipped the two TUI panes and the
`backlog` preset. Nothing is documented yet.

This is a first-class docs child (per `aidocs/framework/planning_conventions.md`
§"User-facing features: docs are a plan deliverable"), and the same pages carry
pre-existing factual errors that predate the feature. Both are in scope.

**Everything below was verified against live output during planning, not read off
the plan.** The verification results are recorded inline so implementation writes
prose, not guesses.

## Verified ground truth (checked this session)

| Claim | Verified value |
|---|---|
| `DEFAULT_PRESETS` (`.aitask-scripts/stats/stats_config.py:17`) | **7** presets: `overview`(3) `labels`(3) `agents`(4) `velocity`(3) `pipeline`(2) `sessions`(3) `backlog`(2) — pane counts differ |
| Preset definition site | **code**, not `aitasks/metadata/stats_config.json`. The JSON is an optional project override layer merged by `load_layered_config` → `deep_merge` (`lib/config_utils.py:110`): **dicts merge per key, lists replace** |
| Precedence contract | pinned by `tests/test_stats_backlog_panes.py::TestPresetPrecedence` — a code-only preset survives a JSON `presets` block; a JSON-pinned preset *list* replaces the code list wholesale |
| Fact-table CSV header | 12 cols: `date, day_of_week, week_offset, task_id, labels, issue_type, task_type, implemented_with, codeagent, llm_model, created_at, category` |
| Backlog CSV header | `week_ending, category, open, arrived, departed, net` |
| New flags | `--backlog-weeks N` (default 8, max 99), `--csv-backlog [FILE]` (default `aitask_backlog.csv`) |
| Rendered `###` sections | **13** — the doc lists name 9 |
| Column order, **both** tables | chronological `W-7 … Now`, **`Now` last** (t1588 reordered the level table too; p1544_4's "Now first" text is stale) |
| Net-flow last column | headed `Now*`, a partial week, with a range footnote |
| Backlog clock | `parse_completed_date` — `completed_at`, else `updated_at` when status is `Done`/`Completed`; deliberately **not** `resolve_completion_date`'s `merge_approved`/`review_approved` stamps |
| Population | archived **and** active tasks (`iter_active_markdown_files` via `collect_inflight`'s `on_file` hook). Postponed → open; Folded → excluded; `Done`-but-unarchived → departed |
| TUI-only caps | **level pane**: a block of ≤6 categories shows in full; above that, 5 show plus an `Other` row summing the rest (`_LEVEL_ROW_CAP = 6`, `shown = block[:5]`). **Net-flow chart**: at most 4 real series plus `Other` (`_NETFLOW_SERIES = 5`, `chosen = ranked[:4]`), ranked by **horizon volume** (arrivals + departures, not net), and `Other` is emitted only when its sum is non-zero. `TOTAL OPEN` and the ARRIVALS/DEPARTURES/NET strip are computed over **all** members, so totals stay complete when either cap engages |
| TUI-only horizon | fixed at `BACKLOG_WEEKS_DEFAULT` (8) — no `--backlog-weeks` equivalent — and week start fixed to Monday (`stats_app.py` passes the literal `1`) |
| Data population is **not** archive-only | `collect_stats`'s backlog walk covers active tasks, and `collect_inflight` (which backs the existing `pipeline.inflight` pane) already did — so "archived task completion data" is imprecise *today*, and the backlog panes widen it |
| Build tooling | `hugo v0.164.0+extended` and `website/node_modules` both present — `hugo build --gc --minify` runs without `npm install` |

## Implementation steps

### 1. `website/content/docs/tuis/stats/_index.md` — two pre-existing errors

- **L57** "Four presets ship with the framework, each bundling three panes" —
  wrong on both counts. Replace with a lead-in that pins **no separate count**
  ("The framework ships these presets:"), so only the table can rot rather than a
  number contradicting the table beside it. Complete the table to all seven
  presets with their exact pane titles (`agents` gains *Usage rankings*; add
  `pipeline`, `sessions`, `backlog`).
- **L66** "Presets are defined in `aitasks/metadata/stats_config.json` and are
  read-only at runtime" — the second half is true, the first is not. Correct it
  outright (no contradicting sentence beside it): presets are defined in
  `.aitask-scripts/stats/stats_config.py`; the JSON is an **optional
  project-local override layer**, merged per preset key, and a preset *list*
  pinned there replaces the code list wholesale — so a project that pins a preset
  will not pick up panes later added to it. State the same contract the
  precedence test asserts.
- **L82** "ships the four default presets" — reconcile with the corrected passage
  above: the project layer is git-tracked, read-only at runtime, and *may* pin or
  override preset pane lists.

### 2. `website/content/docs/tuis/stats/_index.md` — the `backlog` preset

Add the `backlog` row (**Backlog level · Net flow**) and describe both panes,
including every TUI-only behaviour that has no CLI counterpart — a user with many
categories sees aggregation the CLI never applies, so all of it must be stated:

- **Level pane** — a block of six or fewer categories shows in full; above that,
  five show and the remainder is summed into an `Other` row.
- **Net-flow pane** — the chart plots at most four categories plus an `Other`
  series, ranked by **horizon volume** (arrivals + departures, *not* net, so a
  busy category that nets to ~zero is not buried in `Other`).
- **Totals are never capped** — `TOTAL OPEN` and the ARRIVALS / DEPARTURES / NET
  strip are computed over every category, so they stay correct when a cap engages
  and cannot be recovered by summing the visible rows.
- **Horizon** fixed at 8 weeks (no `--backlog-weeks` equivalent) and week start
  fixed to Monday.

### 2b. `website/content/docs/tuis/stats/_index.md` + `tuis/_index.md` — data scope

Four passages describe Stats as an archive-only view. That is already imprecise
(the `pipeline.inflight` pane reads active tasks via `collect_inflight`) and the
backlog panes make it plainly false, so correct all four to distinguish the
**completion metrics**, drawn from archived tasks, from the **backlog series**,
whose population is active *plus* archived:

| Site | Current text |
|---|---|
| `tuis/stats/_index.md:5` | frontmatter `description:` — "browsing archive completion statistics" |
| `tuis/stats/_index.md:30` | "the interactive, pane-based view of archived task completion data" — its enumeration of what `lib/stats_data.py` covers also needs the backlog series |
| `tuis/stats/_index.md:111` | `r` keybinding — "Refresh data from the archive" |
| `tuis/_index.md:22` | "Pane-based viewer for archived task completion statistics: …" — same enumeration, same fix (this is the mirrored per-TUI list step 5 covers) |

Current-state phrasing only — describe what the data scope *is*, with no "now
also scans" framing.

### 3. `website/content/docs/commands/board-stats.md`

- **Option table** gains `--backlog-weeks N` and `--csv-backlog [FILE]`, worded
  from `--help`.
- **"Statistics provided"** — rewrite the numbered list to the 13 sections
  actually rendered, in render order. That adds the two backlog sections *and*
  the two pre-existing omissions (Pipeline Timing, Verified Model Rankings);
  appending to a list that is already wrong would leave it wrong.
- **"CSV export format"** — 10 → 12 columns. State explicitly that open tasks are
  **not** rows in that table, so the backlog level is not reproducible from it;
  the series lives in `--csv-backlog`, whose columns are
  `week_ending, category, open, arrived, departed, net`.
- **"Data sources"** — extend: the backlog sections use `completed_at` (falling
  back to `updated_at` for `Done`/`Completed`), **not** the
  `merge_approved`/`review_approved` ledger stamps the other sections prefer.
  State the **behavioural guarantee**: the two clocks agree on *whether* a task
  completed and can disagree on *which week* it lands in, so a small number of
  tasks are bucketed one week apart between the backlog sections and the
  completion sections. Also: the backlog population scans **active** tasks as
  well as archived ones; a `Done`-but-unarchived task counts as departed;
  **Postponed** counts as open; **Folded** is excluded.

  **Deliberate deviation from the task text.** `aitasks/t1544/t1544_6…md:69` asks
  for "~0.3% of tasks". That figure is a frozen literal — hardcoded at
  `.aitask-scripts/aitask_stats.py:471` and taken from a single t1544_3
  measurement (6 of ~1828 archived tasks by week bucket) — with no maintained
  metric behind it. It drifts with every task added or metadata repair, which
  would make a current-state reference page false while the code stays correct.
  Document the invariant, omit the sample percentage.

### 4. `website/content/docs/skills/aitask-stats.md`

Bring the report-contents list to the 13 rendered sections (same completion rule
as step 3), and extend the supported-options line with `--backlog-weeks` and
`--csv-backlog`.

### 5. `website/content/docs/tuis/_index.md`

L22 mirrors a per-TUI content list — confirmed. Add the backlog level / net-flow
coverage to that sentence, and apply the data-scope correction from step 2b in
the same edit (it is one sentence, not two).

### 6. `aitask-stats` skill docs — all three agent trees

Handed over by t1544_4's Final Implementation Notes. **`.claude/` is the source of
truth; edit it first**, then the two wrappers.

- `.claude/skills/aitask-stats/SKILL.md` — Options list gains `-w, --week-start`,
  `--backlog-weeks`, `--csv-backlog`; "Statistics Provided" goes from 7 entries to
  the 13 rendered sections; "Export Format" goes from 7 CSV columns to 12, plus
  the `--csv-backlog` file and its columns.
- `.opencode/skills/aitask-stats/SKILL.md` — the `## Arguments` line lists only
  `--days N`, `--verbose`/`-v`, `--csv [FILE]`; add the three missing flags.
- `.agents/skills/aitask-stats/SKILL.md` — its `## Arguments` section is a
  truncated stub ("Run the statistics script:") with no flag list; give it the
  same flag list as the OpenCode wrapper.

## Files

- `website/content/docs/tuis/stats/_index.md`
- `website/content/docs/commands/board-stats.md`
- `website/content/docs/skills/aitask-stats.md`
- `website/content/docs/tuis/_index.md`
- `.claude/skills/aitask-stats/SKILL.md`
- `.opencode/skills/aitask-stats/SKILL.md`
- `.agents/skills/aitask-stats/SKILL.md`

## Plan artifact synchronization (before implementation)

`aiplans/p1544/p1544_6_backlog_stats_documentation.md` currently holds the
earlier, narrower plan: no third-tree skill scope, no completed 13-section lists,
no TUI cap detail, no data-scope sweep, and no record of the mitigation decision.
It must not be the artifact a later agent or audit reads.

The first action after approval — before any doc edit — is the externalization
that `planning.md` Step 6 prescribes:

```bash
./.aitask-scripts/aitask_plan_externalize.sh 1544_6 --force --no-worktree \
  --profile aitasks/metadata/profiles/fast.yaml
```

`--force` overwrites the existing file (`OVERWRITTEN:<path>:<source>`) with this
plan, `## Risk` and `### Planned mitigations` included; the `plan_verified` entry
is then appended and both land in the same commit. From that point `aiplans/` is
the authority and this internal file is a copy. Confirm the helper reported
`OVERWRITTEN:` — a `PLAN_EXISTS:` result means the stale plan survived and
implementation must not start.

## Conventions

`aidocs/framework/documentation_conventions.md`: **current-state only** — no
version history, no "newly added" framing; genericize any passage naming specific
coding agents; **correct** a wrong sentence outright rather than adding a
contradicting one beside it.

## Verification

```bash
cd website && hugo build --gc --minify          # node_modules already present
./.aitask-scripts/aitask_skill_verify.sh        # skill-surface check for step 6
```

- Hugo build succeeds with no broken `relref` links.
- Every number and column list is re-checked against live output at
  implementation time — not against this plan:
  ```bash
  ./ait stats --help
  ./ait stats --csv /tmp/t.csv --csv-backlog /tmp/b.csv && head -1 /tmp/t.csv && head -1 /tmp/b.csv
  ./ait stats | grep '^### '
  python3 -c "import sys; sys.path.insert(0,'.aitask-scripts'); from stats.stats_config import DEFAULT_PRESETS; print(len(DEFAULT_PRESETS), {k:len(v) for k,v in DEFAULT_PRESETS.items()})"
  ```
- The preset table's names and pane titles match `DEFAULT_PRESETS` and the
  `register(PaneDef(...))` titles.
- No user-facing passage still describes Stats' data as archive-only (`grep -ni
  archiv` over the four website files returns only the completion-metric
  passages, where it is correct).
- The documented TUI caps match `_LEVEL_ROW_CAP` and `_NETFLOW_SERIES`.
- The precedence prose matches `tests/test_stats_backlog_panes.py::TestPresetPrecedence`.
- The three `aitask-stats` SKILL.md trees agree on the flag list.
- No volatile sample statistic is pinned in the new prose — in particular
  `grep -n '0\.3%' website/content/docs/` returns nothing.

## Upstream observation (record at Step 8, do not fix here)

`.aitask-scripts/aitask_stats.py:471` prints `~0.3%` as a hardcoded literal in
the backlog footnote, and `stats/panes/backlog.py` mirrors that line verbatim
(pinned by t1544_5's CLI-parity test). The figure is a frozen t1544_3 sample with
no maintained metric, so the rendered CLI/TUI footnote carries exactly the
staleness this plan keeps out of the docs. Fixing it is a code change with a test
coupling — out of scope for a documentation task; note it in the Final
Implementation Notes as an upstream defect. t1544_8 (retrospective) already
carries the same figure.

## Risk

### Code-health risk: low
- Docs-and-skill-prose only; no executable code path changes. The one
  non-website surface (three `SKILL.md` files) is guarded by
  `aitask_skill_verify.sh`, and `relref` breakage is caught by the Hugo build.
  · severity: low · → mitigation: none needed
- **The corrected prose re-pins hand-written counts and column lists with no
  drift guard** — the same shape that let this page claim "Four presets" while
  seven shipped, and let the skill doc claim 7 CSV columns against 12. Step 1
  removes the standalone count, which narrows but does not close it: the preset
  table, the 13-section list and the 12-column list all still duplicate source
  values by hand. · severity: medium · → mitigation: stats_docs_source_drift_guard

### Goal-achievement risk: low
- The task's named failure mode is documenting the plan rather than the shipped
  behaviour. Closed during planning: every claim in the ground-truth table above
  was read from live output, source, or the pinning test — including the
  `Now`-last column order, which contradicts p1544_4's own plan text.
  · severity: low · → mitigation: none needed

### Planned mitigations
- timing: after | name: stats_docs_source_drift_guard | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: high | addresses: code-health — hand-pinned doc counts/column lists have no drift guard | desc: Assert the preset names and pane titles in website/content/docs/tuis/stats/_index.md match stats_config.DEFAULT_PRESETS and the register(PaneDef(...)) titles, and that the CSV column lists in board-stats.md and .claude/skills/aitask-stats/SKILL.md match the headers aitask_stats.py emits.
