---
Task: t1162_5_work_report_documentation.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_6_manual_verification_add_manager_facing_work_report_skill_and.md
Archived Sibling Plans: aiplans/archived/p1162/p1162_1_work_report_gatherer_helper.md, aiplans/archived/p1162/p1162_2_work_report_codeagent_operation.md, aiplans/archived/p1162/p1162_3_work_report_skill_and_wrappers.md, aiplans/archived/p1162/p1162_4_board_w_work_report_flow.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-07-24 11:14
---

# Plan: t1162_5 — Work-report documentation (verified)

## Context

t1162 shipped a manager-facing work-report feature across four children — the
gatherer helper (t1162_1), the `work-report` code-agent operation (t1162_2),
the canonical skill + wrappers (t1162_3), and the board `w` flow (t1162_4).
All four are archived and landed. **Nothing about the feature appears on the
website** (`grep -r "work.report" website/content/` → zero hits), so users have
no discoverable entry point.

This is the documentation child, deliberately sequenced last so it documents
**landed source**, not plan expectations.

## Verification findings (why this plan differs from the original)

Re-verified against live source. The original t1162_5 task/plan text carries
claims that **drifted during implementation** and must NOT be copied into docs:

1. **No "7/30-day windows".** That blended-rate design was replaced mid-task.
   The gatherer's default lookback is **90 days**
   (`DEFAULT_VELOCITY_WINDOW`, `lib/work_report_gather.py:68`), and the
   estimator is selectable: `dow` (per-weekday averages, default) or `flat`.
2. **The projection is opt-in, not a default section.** "Observed throughput"
   (`VELOCITY:` rows) is the default; the projection appears only when the user
   asks for a forecast, whereupon the skill re-runs the gatherer with
   `--project` (`SKILL.md:222-224`). Floor: **10 completions** in the window.
3. **Fits/exceeds judgement exists only for the "Today" horizon** — a direct
   `days_ahead` field read. "This week" and custom labels deliberately get none.
4. **More flags than documented**: `--velocity-model` / `--velocity-window`
   passthrough. (`--project` is a *gatherer* flag, never a skill argument.)
5. **Extra scope the user asked for during t1162_4 review**, recorded in that
   plan's sibling notes but absent from the t1162_5 text: document how to
   customize the work-report agent default.

## Scope decisions (AC amendments — confirmed this session)

- **Backfill the whole Operations table**, not just `work-report`. It is
  missing `explore-relay`, `shadow`, and `learn` too (ground truth:
  `SUPPORTED_OPERATIONS`, `.aitask-scripts/aitask_codeagent.sh:26`).
- **New `## Reporting` group** in `workflows/_index.md` (a sixth group).
- **Ship a doc-list drift guard in this task** rather than deferring it.

## Files

**New pages**

1. `website/content/docs/skills/aitask-work-report.md` — `weight: 62`,
   `maturity: [stable]`, `depth: [intermediate]`; modeled on
   `skills/aitask-changelog.md` (intro → `**Usage:**` → the standard
   run-from-project-root Note → `## Step-by-Step` → `## Key Features` →
   `## Workflows`). Document: `--columns <csv>`, `--tasks <csv>` (requires
   `--columns`), `--velocity-model <id>`, `--velocity-window <days>`;
   interactive vs board-launched paths; the horizon prompt (Today / This week /
   custom via "Other") and that it **labels only, never changes membership**;
   report structure (focus summary → column-grouped priorities with `t<id>` →
   Observed throughput → opt-in projection → blockers/manager-asks); the
   projection's caveat, 10-completion floor, "insufficient completion history
   for a projection" fallback, and Today-only fits/exceeds; the fail-closed
   stale-selection stop (diagnostics verbatim → Re-select interactively /
   Abort); and that **no report file is ever written**.
2. `website/content/docs/workflows/work-report.md` — `weight: 86`,
   `depth: [intermediate]` (workflow pages carry no `maturity`); modeled on
   `workflows/explain.md`. End-to-end: board `w` flow, direct invocation, the
   review/edit loop, and how a manager should read the projection.

**Index / cross-reference edits** (hand-curated — both must be updated or the
pages are undiscoverable)

3. `website/content/docs/skills/_index.md` — row under
   `### Configuration & Reporting`, after `/aitask-changelog`. Also add the
   **missing `/aitask-add-model` row** (pre-existing gap; required for the new
   guard to pass).
4. `website/content/docs/workflows/_index.md` — new `## Reporting` group
   between `## Git` and `## Maintenance`, and **update the t594_7 comment**
   that enumerates "these five groupings" → six.

**Existing-page edits**

5. `website/content/docs/tuis/board/reference.md` — `w` row in
   `#### Task Operations`, between the `p` and `b` rows (matching binding order
   at `board/aitask_board.py:4725-4729`). Context cell in house style:
   column-scoped, hidden in In-Flight / By-Topic.
6. `website/content/docs/tuis/board/how-to.md` — new
   `### How to Generate a Work Report` after
   `### How to Pick a Task for Implementation`. Covers: focus a column, press
   **W**, the column multi-select (focused column pre-checked), the task
   multi-select (**all pre-checked — deselect to exclude**, always full column
   contents regardless of search/filters), Space/Enter/Esc, the empty-selection
   notifications, and the launch dialog showing the exact command. Plus the two
   customization surfaces the user asked for: the agent default
   (`aitasks/metadata/codeagent_config.json` → `defaults."work-report"`, or
   `codeagent_config.local.json` which wins, editable via `ait settings` →
   Agent Defaults, plus the per-launch picker in the dialog) and rebinding `w`
   itself (board `?` editor / Settings → Shortcuts, persisted in
   `userconfig.yaml` under `shortcuts.board.work_report` — *not*
   `board_config.json`).
7. `website/content/docs/commands/codeagent.md` — backfill `work-report`,
   `explore-relay`, `shadow`, `learn` into the `### Operations` table; add a
   Board work-report bullet under `### TUI Integration`.

**Guard + task file**

8. `tests/test_website_doc_lists.sh` (new) — repo test convention: self-contained
   bash, `assert_*` helpers, PASS/FAIL summary, exit 1 on failure. Asserts
   (a) every id in `SUPPORTED_OPERATIONS` has a row in `codeagent.md`'s
   Operations table, and (b) every `website/content/docs/skills/aitask-*.md`
   page has a row in `skills/_index.md`.
9. `aitasks/t1162/t1162_5_work_report_documentation.md` — record the three AC
   amendments above, committed with `./ait git`.

## Conventions to honor

- **Current-state-only** prose; no version history
  (`aidocs/framework/documentation_conventions.md`).
- **Genericize** supported-agent references in blurb prose; keep literal
  enumerations only in the per-agent tables.
- Links: plain relative `page/` inside `skills/` and `workflows/`;
  `{{< relref "/docs/..." >}}` when linking from `tuis/board/*` or `commands/*`.
- Generic invented example project/task names in samples.
- **Do not** mention `diffviewer`; leave the documented-TUIs list unchanged.

## Risk

### Code-health risk: low
- Adding a sixth workflows group leaves the t594_7 maintenance comment ("these
  five groupings") factually wrong unless updated in the same edit · severity:
  low · → mitigation: corrected inline in the same change
- The new guard greps hand-maintained markdown tables; an over-strict matcher
  could fail on legitimate formatting variation · severity: low · → mitigation:
  match on the backticked id in the first table cell, and prove the harness
  fails on a real regression before trusting it

### Goal-achievement risk: medium
- The task text and original plan carry drifted claims ("7/30-day windows",
  projection as a default section); copying them verbatim would ship
  confidently-wrong user-facing docs · severity: medium · → mitigation: every
  documented claim cross-checked against live source during this verification
  pass; corrections enumerated above
- Hand-maintained doc lists drift silently — 4 of 10 operations and one skill
  page were already missing · severity: medium · → mitigation: drift-guard test
  shipped in this task (scope decision confirmed)

No separate before/after mitigation tasks are needed — both mitigations are
in-scope work in this change.

## Verification

- `cd website && hugo build --gc --minify` succeeds. Toolchain confirmed
  present: Hugo v0.164.0+extended, Go, Sass, `node_modules` installed.
- New pages render and every internal link/relref resolves during the build.
- `bash tests/test_website_doc_lists.sh` passes — **and is proven able to fail**:
  temporarily remove one operation row and one skill row, confirm the suite
  prints FAIL and exits 1, then restore.
- Spot-check each documented flag/behavior against
  `.claude/skills/aitask-work-report/SKILL.md`, `lib/work_report_gather.py`,
  and `board/aitask_board.py` — no drifted claims.

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9. This is
the last implementation child; t1162_6 (aggregate manual verification) is the
actual final child, so archiving this one will not yet archive the parent.
