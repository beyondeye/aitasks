---
Task: t1162_3_work_report_skill_and_wrappers.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_4_board_w_work_report_flow.md, aitasks/t1162/t1162_5_work_report_documentation.md, aitasks/t1162/t1162_6_manual_verification_add_manager_facing_work_report_skill_and.md
Archived Sibling Plans: aiplans/archived/p1162/p1162_1_work_report_gatherer_helper.md, aiplans/archived/p1162/p1162_2_work_report_codeagent_operation.md
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-23 15:52
---

# Plan: t1162_3 — `/aitask-work-report` skill + agent wrappers + contract guard

## Context

The canonical manager-facing skill. Plain static skill (NO `.j2`, NO goldens,
NO profile stub — same shape as `aitask-changelog` / `aitask-explain`).
Consumes the t1162_1 gatherer (`.aitask-scripts/aitask_work_report_gather.sh`)
and the t1162_2 `work-report` code-agent operation. Parent design:
`aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md`
(t1162_3 section).

**Plan verified against current `main` on 2026-07-23** (verify path; no prior
verifications). Everything re-checked live:

- Gatherer CLI flags confirmed in `lib/work_report_gather.py` argparse:
  `--list-columns`, `--columns`, `--tasks`, `--now`, `--velocity-window`,
  `--velocity-model`, `--project` (opt-in). Live runs confirmed:
  `--list-columns` emits `COLUMN:<id>|<title>` with `unordered` first;
  `--columns now` emits `TASK:` rows then `VELOCITY_MODEL:` + `VELOCITY:`
  rows (no `PROJECTION:` without `--project`); unknown task →
  `ERROR:unknown_task:<id>` with no non-ERROR lines.
- **Failure surface verified (review concern):** usage/config errors go
  through `_die()` — **stderr + non-zero exit, NO `ERROR:` sentinel on
  stdout** (e.g. non-positive `--velocity-window`, unknown
  `--velocity-model`, malformed `--now`, pipe-bearing config `col_id`). And
  an **empty board config emits zero `COLUMN:` rows with exit 0** (verified
  with a `columns: []` fixture). Both cases are handled explicitly in the
  workflow below.
- Wrapper shapes confirmed against the three `aitask-changelog` wrapper files
  (non-templated "Source of Truth" pointer form). The audit
  (`aitask_audit_wrappers.sh`) checks exactly these 3 trees: `agents`,
  `opencode-skill`, `opencode-command` — matching the task's 3 wrapper files.
  Skill discovery is by directory presence, so no registration list to edit.
- t1162_2 operation is live: `./.aitask-scripts/aitask_codeagent.sh --dry-run
  invoke work-report --columns now --tasks 1` →
  `DRY_RUN: claude --model claude-sonnet-4-6 /aitask-work-report\ --columns\ …`.
  Args arrive as flat whitespace-delimited text (dispatcher rejects
  whitespace-bearing args fail-closed, so token splitting is safe).
- `aitask_query_files.sh` verbs `plan-file <id>` and `archived-children <N>`
  exist. `tests/lib/asserts.sh` provides `assert_eq` / `assert_contains` /
  `assert_not_contains` mutating caller-local PASS/FAIL/TOTAL.
- `tests/test_opencode_skill_legacy_pointers.sh` only constrains *templated*
  skills — the legacy "Source of Truth" pointer shape is correct for this
  static skill (it has no `.j2`).
- `.claude/skills/task-workflow/satisfaction-feedback.md` exists;
  `skill_name` is a plain string input.

## Files (all new)

1. `.claude/skills/aitask-work-report/SKILL.md` — canonical skill.
2. `.agents/skills/aitask-work-report/SKILL.md` — Codex thin wrapper; copy
   `.agents/skills/aitask-changelog/SKILL.md` shape (Source-of-Truth pointer +
   `codex_tool_mapping.md` note), with an Arguments section naming the
   optional flags.
3. `.opencode/skills/aitask-work-report/SKILL.md` — copy
   `.opencode/skills/aitask-changelog/SKILL.md` shape.
4. `.opencode/commands/aitask-work-report.md` — copy
   `.opencode/commands/aitask-changelog.md` shape: description frontmatter,
   `@.opencode/skills/opencode_tool_mapping.md`, `Arguments: $ARGUMENTS`,
   `@.claude/skills/aitask-work-report/SKILL.md`.
5. `tests/test_work_report_skill_contract.sh` — contract guard test.

## AC amendment (explicit — no silent deviation)

The task's step 1 pins only `--columns <csv>` / `--tasks <csv>`. This plan
**adds two optional passthrough flags**: `--velocity-model <id>` and
`--velocity-window <days>`, forwarded **verbatim to every gatherer
invocation** (including the `--project` re-run); when absent, the gatherer's
defaults apply. Rationale: the task itself pins "the estimator is selectable
via `--velocity-model`" — without forwarding, a caller cannot actually select
it. The task file's workflow section is amended accordingly at implementation
time (committed via `./ait git`).

## SKILL.md workflow (write these steps; contract sentences marked ⚠ must
appear verbatim-recognizable — the guard test greps for them)

Frontmatter: `name: aitask-work-report`, description: "Draft a manager-facing
work report from selected board columns."

0. **Gatherer output contract (PINNED — write this schema block verbatim
   into the SKILL.md).** Every gatherer stdout line must match one of:
   ```
   COLUMN:<col_id>|<title>
   TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<task_file_path>
   VELOCITY_MODEL:<model_id>|<window_days>|<start_date>|<end_date>|<model_label>
   VELOCITY:<bucket_id>|<observed_units>|<completed_count>|<avg_per_unit>|<bucket_label>
   PROJECTION:<remaining_total>|<projected_date>|<days_ahead>|<basis_completions>|<caveat>
   ERROR:<reason>[:<detail>]
   NO_TASKS
   ```
   Split on `|` with **maxsplit = field-count − 1**: the free-text field is
   always LAST (`<title>`, `<task_file_path>`, `<model_label>`,
   `<bucket_label>`); `PROJECTION:` and `ERROR:` have no free-text field.
   Note the `VELOCITY:` field order: bucket id, **observed units, completed
   count, average**, then label — do not swap counts and averages. ⚠ Any
   line matching none of these prefixes, or a recognized prefix with the
   wrong field count, is a **malformed record**: treat it as an
   infrastructure failure (hard stop per step 3) — never guess, reorder, or
   skip fields.
1. **Parse arguments:** `--columns <csv>`, `--tasks <csv>` (both optional;
   `--tasks` requires `--columns`), plus optional `--velocity-model <id>`
   and `--velocity-window <days>` forwarded verbatim to every gatherer run
   (absent → gatherer defaults). Args arrive as flat whitespace-delimited
   text — parse tokens; values are guaranteed whitespace-free by the
   dispatcher.
2. **Selection:**
   - No `--columns` → interactive path. ⚠ Column discovery MUST use
     `./.aitask-scripts/aitask_work_report_gather.sh --list-columns` as the
     only discovery source (it emits `unordered` first when the Unsorted
     column currently has tasks — the dynamic column is always offered).
     ⚠ **Empty discovery:** if the run exits 0 but emits zero `COLUMN:`
     lines, there are no reportable columns — inform the user ("the board
     has no reportable columns — nothing to report") and END the skill;
     never present an empty selection prompt. Otherwise present columns via
     `AskUserQuestion` `multiSelect: true` (paginate: max 4 options per
     question — 3 + "Show more", as in aitask-pick Step 2c). Then run the
     gatherer with the chosen columns and present the ordered task list for
     inclusion/exclusion (multiSelect, paginated; all tasks pre-announced as
     included, user unchecks to exclude).
   - With `--columns` (+ optional `--tasks`) → run the gatherer once with the
     exact args and SKIP membership prompts (the board already reviewed the
     selection).
3. ⚠ **Fail-closed validation (NON-NEGOTIABLE) — after EVERY gatherer run.**
   Hard-stop conditions, checked in this order:
   1. **Non-zero exit status** (usage error, malformed board config,
      infrastructure/read failure — the gatherer prints diagnostics to
      stderr only, with no stdout sentinel);
   2. one or more `ERROR:` lines, or `NO_TASKS`;
   3. **missing expected output** (exit 0 but no `TASK:` line in report
      mode) or any **malformed record** per the step-0 schema.

   On ANY of these: STOP — do not draft. Present the diagnostics verbatim
   (stderr for condition 1; every `ERROR:` line for condition 2; the
   offending line for condition 3), then `AskUserQuestion`:
   "Re-select interactively" / "Abort". ⚠ Include the sentence: the skill
   "never drafts from a partial or silently-corrected selection" — the
   report must contain exactly the validated selected tasks, parsed from
   well-formed records only.
4. **Horizon (every run):** `AskUserQuestion` — "Today" / "This week" /
   custom label via Other free text. The period labels the report only; ⚠ it
   never changes task membership.
5. **Context gathering per selected task:** read the task file (description,
   frontmatter metadata, `depends`); active plan via
   `./.aitask-scripts/aitask_query_files.sh plan-file <id>`; for parents with
   children: pending list from `children_to_implement`, archived children via
   `./.aitask-scripts/aitask_query_files.sh archived-children <id>`.
   Child-context rules (PINNED): one manager-level line per parent; progress
   phrased as "N of M subtasks complete"; done/archived children counted,
   never listed individually; folded tasks are merged content — never
   separate items; do NOT mine child plans for file/symbol detail.
6. **Draft the report** (first-person, manager-friendly Markdown):
   - Short focus summary (2-3 sentences).
   - Column-grouped priorities in gatherer order: per task — outcome
     (what will be delivered, benefit-level), current status, `t<id>`.
   - **Observed throughput** (default): render the `VELOCITY:` rows
     **generically** (per bucket: `<bucket_label>`, `<avg_per_unit>`,
     `<observed_units>`) — the estimator is selectable, so do NOT hardcode
     weekday semantics; quote `<observed_units>` so the reader can judge
     confidence.
   - **Completion projection — opt-in (the user must ask for a forecast).**
     Only then re-invoke the gatherer with `--project` (same
     columns/tasks/velocity args) and read the `PROJECTION:` record.
     **The gatherer computes it** — report it as-is; do NOT recompute it and
     do NOT do date arithmetic in-prompt. `remaining_total` 0 → say the
     selection is effectively complete and omit the projection. Otherwise
     quote `<projected_date>`, `<days_ahead>` and `<basis_completions>`, and
     **always surface `<caveat>`**: the figure counts tasks, so it ignores
     task size, blockers and capacity — an extrapolation of past throughput,
     never a commitment or a delivery estimate.
     **Horizon comparison — a fits/exceeds judgement is made ONLY for the
     "Today" horizon**, read directly off the gatherer's `<days_ahead>`
     field: `0` → fits today, `> 0` → exceeds today. That is a field read,
     not arithmetic. ⚠ For "This week" AND custom free-text labels, show the
     horizon label plus the gatherer-provided `<projected_date>` /
     `<days_ahead>` **without any inferred fits/exceeds judgement** —
     deciding "fits this week" would require computing days remaining in
     the week (prompt-side date arithmetic, forbidden), and the skill
     cannot know what date a custom label like "Sprint 14" denotes.
     ⚠ `PROJECTION:<n>|none|insufficient_data|…` → state "insufficient
     completion history for a projection" and omit the section — never
     fabricate a rate.
   - Blockers / manager-asks section (only real blockers from `depends` /
     task content — nothing invented).
   - Include exactly the selected tasks; no invented dates, estimates,
     progress, commitments, dependencies, or blockers; no
     implementation-level file/symbol detail.
7. **Present in-session** for review/editing; iterate on feedback. ⚠ Do NOT
   write a report file (no dated file, no repository file) — the draft lives
   in the session only.
8. **Satisfaction feedback:** execute the Satisfaction Feedback Procedure
   (`.claude/skills/task-workflow/satisfaction-feedback.md`) with
   `skill_name` = `"work-report"`.

## Contract guard test (`tests/test_work_report_skill_contract.sh`)

Scaffold on `tests/test_opencode_skill_legacy_pointers.sh` shape: `set -e`,
resolve `PROJECT_DIR`, own `PASS/FAIL/TOTAL`, source `tests/lib/asserts.sh`,
`cd "$PROJECT_DIR"`, summary + exit 1 on failure. Assert (`assert_contains`
over the canonical SKILL.md content):
- the `--list-columns` discovery requirement
  (`aitask_work_report_gather.sh --list-columns`),
- the fail-closed `ERROR:`/`NO_TASKS` hard-stop wording,
- **the non-zero-exit hard-stop rule** ("Non-zero exit status"),
- **the malformed-record rule** ("malformed record"),
- **the pinned record schemas** — the exact `TASK:<col_id>|<task_id>|…` and
  `VELOCITY:<bucket_id>|<observed_units>|<completed_count>|<avg_per_unit>|<bucket_label>`
  schema lines (pins the field ORDER, not just prose),
- **the empty-discovery path** ("no reportable columns"),
- "never drafts from a partial or silently-corrected selection",
- the no-report-file rule ("Do NOT write a report file"),
- "insufficient completion history for a projection",
- the opt-in projection marker (`--project`),
- **the velocity passthrough declaration** (`--velocity-model`),
- **the horizon-judgement restriction** ("without any inferred fits/exceeds
  judgement" — applies to "This week" and custom labels; only "Today" gets a
  judgement, read off `<days_ahead>`),
- `skill_name` = `"work-report"`.
Plus: each of the 3 wrapper files exists and contains the canonical path
`.claude/skills/aitask-work-report/SKILL.md`.

Marker-string discipline (wrapped-prose caveat, per project feedback memory):
choose short distinctive phrases that cannot be line-wrapped apart, and run
each grep against the actual file before committing the test. Harness
self-check: temporarily corrupt one expectation, confirm the suite prints
FAIL and exits 1, then revert.

## Verification

- `bash tests/test_work_report_skill_contract.sh` — all PASS, exit 0.
- Harness-can-fail check (corrupt one marker → FAIL + exit 1 → revert).
- `./.aitask-scripts/aitask_skill_verify.sh` — passes (static skill; verifies
  no stub surface broke).
- `./.aitask-scripts/aitask_audit_wrappers.sh discover` — no
  `GAP:*:aitask-work-report` lines (wrapper coverage for the new skill).
- Full wrapper/helper audit — `aitask_work_report_gather.sh` now referenced
  by a skill; whitelist coverage confirmed end-to-end (t1162_2 note).
- Dry-run sanity: `./.aitask-scripts/aitask_codeagent.sh --dry-run invoke
  work-report --columns now --tasks 1` shows the slash command (already
  confirmed live during verification).
- Task-file AC amendment (velocity passthrough flags) applied and committed
  via `./ait git`.

## Risk

### Code-health risk: low
- Pure addition: 5 new files, no existing code or skill surface modified; the
  audit and verify tooling discover the skill by directory presence, so no
  registration lists are touched · severity: low · → mitigation: none needed
- The contract guard test pins prose markers and two schema lines, which
  future wording edits to the skill could trip; markers are short and
  distinctive and the failure message names the missing marker, so the fix is
  local and obvious · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The skill's pinned behaviors (fail-closed hard stop incl. non-zero
  exit/malformed records, opt-in projection, no report file, membership
  integrity) are prose contracts executed by an LLM; the guard test pins
  their presence and exact record schemas, and the gatherer enforces the data
  contract fail-closed on its side · severity: low · → mitigation: none needed
- Interactive pagination (8 live columns, potentially many tasks) is specified
  from the proven aitask-pick Step 2c pattern, with an explicit
  empty-discovery exit · severity: low · → mitigation: none needed

## Post-Review Changes

### Change Request 1 (2026-07-23 15:10) — three blocking review concerns

All three verified before changing anything (the Codex gap was confirmed by
diffing the two tool-mapping files: `.agents/skills/codex_tool_mapping.md`
has no multi-select adaptation for `request_user_input`, while
`.opencode/skills/opencode_tool_mapping.md` explicitly maps `multiple` ↔
`multiSelect`).

1. **Codex multi-select gap (high).** The canonical skill required
   `multiSelect: true` prompts, which Codex cannot render. *Fix:* an
   agent-neutral "Agents without native multi-select" fallback in the
   canonical SKILL.md — present the full candidate list as numbered text,
   collect ONE free-text comma-separated id list (columns: include; tasks:
   exclude, empty = none), normalize, and pass through the gatherer so any
   typo/unknown id fails closed. Explicitly forbids per-item yes/no
   emulation. The Codex wrapper now points at this fallback.
2. **Pagination protocol underspecified (medium).** *Fix:* a named
   "Paginated multi-select protocol" shared by both prompts: accumulator
   retained across pages; a response selecting items + "Show more" records
   the items AND advances; loop ends on a response without "Show more" or
   at the last page; unreached pages keep default state (columns: not
   included; tasks: not excluded); final result applied in canonical
   gatherer order. Task prompt re-phrased as select-to-EXCLUDE, matching
   the tool's options-start-unselected semantics.
3. **Discovery run had no defined hard stop (medium).** *Fix:* Step 1 now
   validates the `--list-columns` run first (Step 2 in list mode: non-zero
   exit, `ERROR:` line, or malformed record → hard stop; only `COLUMN:`
   records are well-formed in list mode); zero rows is the intentional
   empty-board case only after a clean run. Step 2 condition 3 documents
   the list-mode variant.

- **Files affected:** `.claude/skills/aitask-work-report/SKILL.md`,
  `.agents/skills/aitask-work-report/SKILL.md`,
  `tests/test_work_report_skill_contract.sh` (4 new markers: list-mode
  discovery validation, pagination accumulator, multi-select fallback
  presence + its comma-list contract). Suite grew 22 → 26 assertions.

### Change Request 2 (2026-07-23 15:20) — fallback id handling was branch-blind

- **Requested by user:** The no-multi-select fallback stripped optional `t`
  prefixes from a list that can contain *column* ids — the live board
  exposes `COLUMN:tests`, which would become `ests` — and routed both
  branches "as in point 5" (the `--tasks` re-run), which is wrong for the
  column-selection call. Verified: CONFIRMED (the `tests` column id exists
  in the current board config).
- **Changes made:** the fallback now has two explicit branches: column
  selection preserves ids exactly as typed (trim only, NO prefix stripping)
  and invokes `--columns <selected-columns>` (point 4); task exclusion
  strips the optional `t` on task ids ONLY, removes exclusions, and re-runs
  `--tasks <canonical-survivors>` (point 5). Both branches remain
  gatherer-validated. Two new guard-test markers pin the per-branch rules
  (suite 26 → 28 assertions).
- **Files affected:** `.claude/skills/aitask-work-report/SKILL.md`,
  `tests/test_work_report_skill_contract.sh`.

### Change Request 3 (2026-07-23 15:28) — exclusion typos silently vanished

- **Requested by user:** In the fallback task-exclusion branch, exclusions
  were subtracted from the validated selection before any check, so an
  unknown exclusion id (e.g. `9999`) was a no-op — the survivors still
  validated and the report drafted, contradicting the fail-closed claim.
  Verified: CONFIRMED (set subtraction cannot reject a non-member).
- **Changes made:** every normalized exclusion is now membership-validated
  against the displayed validated task-id set BEFORE subtraction; unknown
  ids or tokens that normalize to nothing hard-stop through the Step 2
  re-select/abort prompt. The closing fail-closed sentence now names which
  mechanism checks each id class (gatherer for columns and the final task
  list, pre-subtraction membership check for exclusions). New guard marker
  "Validate every exclusion BEFORE subtracting" (suite 28 → 29 assertions).
- **Files affected:** `.claude/skills/aitask-work-report/SKILL.md`,
  `tests/test_work_report_skill_contract.sh`.

## Final Implementation Notes

- **Actual work done:** Shipped the canonical
  `.claude/skills/aitask-work-report/SKILL.md` (pinned gatherer record
  schemas; 3-condition fail-closed validation incl. non-zero exit and
  malformed records, with a list-mode variant for `--list-columns`;
  empty-discovery exit; paginated multi-select protocol with a cross-page
  accumulator; a no-multi-select fallback with per-branch id handling and
  pre-subtraction exclusion validation; opt-in `--project` projection with
  Today-only fits/exceeds judgement; no report file; satisfaction feedback
  with `skill_name: work-report`), the three wrappers
  (`.agents/skills/aitask-work-report/SKILL.md`,
  `.opencode/skills/aitask-work-report/SKILL.md`,
  `.opencode/commands/aitask-work-report.md`, all pointing at the canonical
  path), and `tests/test_work_report_skill_contract.sh` (29 assertions).
  Applied the planned AC amendment (velocity flags forwarded) to the task
  file via `./ait git`.
- **Deviations from plan:** None structural. Three review rounds after the
  initial build hardened the interactive contracts beyond the approved
  plan's text — see Post-Review Changes 1–3 (Codex no-multi-select
  fallback with per-branch id rules, pagination accumulator protocol,
  list-mode discovery validation, pre-subtraction exclusion validation).
  One marker phrase had to be re-wrapped in the source so the guard grep
  could see it (the wrapped-prose caveat firing exactly as the plan warned).
- **Issues encountered:** First test run failed on two markers — one needle
  had a stray backtick, and "insufficient completion history for a
  projection" was line-wrapped in the SKILL.md prose; fixed the needle and
  unwrapped the source line. Harness self-check performed: corrupting one
  marker makes the suite print FAIL and exit 1; reverted and re-verified.
- **Key decisions:**
  - The gatherer record schemas are pinned verbatim inside the SKILL.md and
    the guard test greps the two order-sensitive schema lines (`TASK:`,
    `VELOCITY:`), so field order cannot silently drift while prose markers
    still pass.
  - Fail-closed is three-conditioned (exit status first, then
    `ERROR:`/`NO_TASKS`, then missing/malformed output) because the
    gatherer's `_die()` path emits stderr only — an `ERROR:`-only rule
    would draft from absent input.
  - The no-multi-select fallback collects ONE free-text comma list per
    prompt (never per-item yes/no), handles column ids verbatim (a `tests`
    column id must not lose its `t`), and validates exclusions against the
    displayed set BEFORE subtracting so typos hard-stop.
  - A fits/exceeds judgement exists only for the "Today" horizon (a direct
    `<days_ahead>` field read); "This week" would require prompt-side date
    arithmetic, which stays forbidden.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **t1162_4 (board `w`):** launch with explicit `--columns`/`--tasks` —
    the skill then skips all membership prompts and only gatherer-validates.
    The skill also accepts optional `--velocity-model`/`--velocity-window`
    passthrough (AC amendment); the board does not need to send them.
  - **t1162_5 (docs):** the user-facing contract to document: interactive
    column/task selection, horizon labels (Today / This week / custom),
    default throughput section, opt-in projection with caveat, no report
    file ever written. The canonical SKILL.md is the source; the guard
    test's marker list enumerates every load-bearing sentence.
  - Wrapper edits must keep the literal canonical path
    `.claude/skills/aitask-work-report/SKILL.md` — the guard test checks
    all three files for it.
  - When editing the canonical SKILL.md, run
    `bash tests/test_work_report_skill_contract.sh` before committing —
    marker phrases must not be line-wrapped apart.

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9.
