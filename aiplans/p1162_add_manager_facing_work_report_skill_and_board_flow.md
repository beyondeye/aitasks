---
Task: t1162_add_manager_facing_work_report_skill_and_board_flow.md
Base branch: main
plan_verified: []
---

# Plan: t1162 — Manager-facing work-report skill and board flow

## Context

`aitask-changelog` reports backward (what landed); there is no forward-looking
"what will be worked on today/this week" report for managers. Task membership
must come from selected `ait board` columns, with each column's ascending
`boardidx` order as the priority order. This task adds a `/aitask-work-report`
skill, a deterministic gatherer helper, a contextual `w` board action that
launches an agent with the exact board-reviewed selection, `work-report` as a
read-only code-agent operation, and docs. The report is drafted in-session
only — no report file is written. Per user request (explicit AC amendment),
the report also includes a **completion projection** derived from historical
average tasks-completed-per-day (reusing the stats collection seam), projected
over the report horizon — clearly labeled as a projection, never a commitment.

**Decomposition (user-approved): 5 child tasks** + an aggregate
manual-verification sibling offered at creation time. Children are created
post-approval (plan mode is read-only), each with a self-contained child plan
under `aiplans/p1162/`. Children auto-depend on prior siblings (sequential).

## Exploration findings (anchors for child plans)

- **Board TUI** (`.aitask-scripts/board/aitask_board.py`, ~7060 lines):
  - `w` key is currently unbound — free to claim.
  - Model binding: `Binding("p", "pick_task", "Pick")` at `aitask_board.py:4619`;
    handler `action_pick_task` at `:5640-5680`; footer gating in `check_action`
    at `:4655-4766` (return `False` hides; derived views gated via
    `self.base_filter in ("inflight", "bytopic")`).
  - Focused column: `_get_focused_col_id()` at `:5391-5399` (works for both a
    focused `TaskCard` and a focused `CollapsedColumnPlaceholder`, `:1074-1088`).
  - Column data: `TaskManager.columns` / `column_order` (`:502-503`); tasks map
    via frontmatter `boardcol` (default `"unordered"`, `:271-275`) and
    `boardidx` (default `0`, `:279-283`); `get_column_tasks(col_id)` at
    `:668-671` sorts by `board_idx` and ignores search/filters (full column
    contents — exactly what the task requires). Dynamic Unsorted column id is
    `"unordered"`, shown only when non-empty; pickers prepend it at index 0.
  - Multi-select modal model: `IssueTypeFilterScreen` (`:3090-3143`) —
    `SelectionList` + Space toggle (native), Enter confirms, Escape cancels.
  - Agent launch: `AgentCommandScreen` (`lib/agent_command_screen.py:363-399`),
    command via `resolve_dry_run_command(project_root, operation, *args)`
    (`lib/agent_launch_utils.py:199`) which shells
    `aitask_codeagent.sh --dry-run invoke <op> <args>`;
    `_FRESH_WINDOW_OPERATIONS` at `agent_command_screen.py:64-66`.
  - New `Binding` entries in `KanbanApp.BINDINGS` are auto-registered for user
    customization by `ShortcutsMixin` (`_shortcuts_scope = "board"`) — no extra
    wiring.
- **Dispatch** (`.aitask-scripts/aitask_codeagent.sh`):
  `SUPPORTED_OPERATIONS=(pick explain …)` at `:26`; per-agent command
  composition in `build_invoke_command` (`:405-548`). Codex skill launches
  already run in **default mode** (comment at `:505-509`) — the "read-only
  analysis → default mode not Plan Mode" requirement is the existing behavior;
  pin it with a test. There is **no separate "lightweight model class"** in the
  code: `explain` resolves via the standard chain (flag → user config
  `.defaults[op]` → project config → `DEFAULT_AGENT_STRING`). Interpretation
  (explicit, not silent): "same model class as explain" = `work-report` uses the
  identical resolution chain and default as `explain`, and gets `work-report`
  verified-score entries in `seed/models_*.json` mirroring `explain`'s scores.
- **Skill shape**: plain static skill (like `aitask-changelog` / `aitask-explain`)
  — single `SKILL.md`, no `.j2`, no goldens; 3 mirror wrappers
  (`.agents/skills/<name>/SKILL.md`, `.opencode/skills/<name>/SKILL.md`,
  `.opencode/commands/<name>.md`). Satisfaction feedback with
  `skill_name = "work-report"`.
- **Helper whitelisting**: new helper scripts must be whitelisted in 5
  touchpoints (`.claude/settings.local.json`, `.codex/rules/default.rules`,
  `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json`) — verified by `aitask_audit_wrappers.sh`.
- **Test conventions**: bash tests source `tests/lib/asserts.sh`, isolated tree
  via `mktemp -d` + `export TASK_DIR` (model: `tests/test_query_files_inflight.sh`);
  dispatch tests model `tests/test_codeagent.sh`; board Pilot tests model
  `tests/test_board_footer_visibility.py` (asserts `app.screen.active_bindings`).

## Child tasks

### t1162_1 — Work-report gatherer helper + unit tests

New `.aitask-scripts/aitask_work_report_gather.sh`: thin bash entry
(whitelistable, `set -euo pipefail`, sources `lib/python_resolve.sh`) that
delegates to a new `.aitask-scripts/lib/work_report_gather.py` (reuses
`lib/config_utils.load_layered_config` for `board_config.json` — canonical
layered-read seam — and parses parent task frontmatter from `aitasks/t*.md`).

**PINNED output contract** (pipe-delimited, exit 0 for all validation
outcomes; status via lines):

```
COLUMN:<col_id>|<title>
TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<task_file_path>
VELOCITY:<window_days>|<completed_count>|<avg_per_day>
ERROR:unknown_column:<id>
ERROR:unknown_task:<id>
ERROR:task_not_in_selected_columns:<id>
ERROR:task_order_changed:<canonical_csv>
NO_TASKS
```

- **Parsing rule (PINNED — no escaping needed):** each record has exactly ONE
  free-text field and it is always LAST (`<title>` in `COLUMN:`,
  `<task_file_path>` in `TASK:`); consumers split on `|` with
  `maxsplit = fixed_field_count`, so pipes in column titles or paths survive
  intact. Round-trip tests cover a pipe-bearing column title and task path.
  All other fields are pipe-free by construction (ids, enums, numbers).
- `pending_children` = length of the task's `children_to_implement` (0 for a
  leaf task) — the "N of M subtasks" input.
- `remaining_items` = **remaining-work semantics, defined independently of
  membership (PINNED):** a task with a `children_to_implement` key →
  `len(children_to_implement)` (a fully-finished parent family, `[]`, → 0);
  a leaf task → 0 if `status: Done` else 1. Inclusion in the report is
  unchanged (no status filter — Done-but-unarchived items still appear);
  only the projection's work-item count uses `remaining_items`.
- **`--tasks` order is significant (PINNED):** the csv carries the
  board-reviewed sequence. After validation, the gatherer compares the given
  sequence (post-dedup) against the current canonical order (board
  column/boardidx order restricted to those tasks); on mismatch it emits
  `ERROR:task_order_changed:<canonical_csv>` (fail-closed, like all errors) —
  a task reordered between board review and agent execution can never
  silently change report priority order. The board `w` flow composes
  `--tasks` in exactly the displayed grouped order; the skill's interactive
  path passes the gatherer's own emitted order (always consistent).
- `VELOCITY:` lines (emitted after `COLUMN:`/`TASK:` lines on every successful
  gather, windows 7 and 30 days): completion throughput computed from archived
  tasks' `completed_at` timestamps by **reusing the canonical stats collection
  seam** (`.aitask-scripts/stats/stats_data.py` — import from
  `work_report_gather.py`; do NOT parse `aitask_stats.sh` human-text output
  and do NOT reimplement the archive scan). Counts include archived children
  (same unit as `pending_children`-based work items). `avg_per_day` rounded to
  2 decimals; zero history ⇒ `VELOCITY:<w>|0|0`.

- CLI modes:
  - `--list-columns` — **enumeration mode**: emits only `COLUMN:` lines for
    every reportable column: `unordered` first **when it currently has tasks**,
    then `column_order` left-to-right. This is the single discovery source for
    the skill's no-args interactive path (and available to anything else), so
    the dynamic Unsorted column can never be silently omitted.
  - `--columns <csv>` (required outside `--list-columns`), `--tasks <csv>`
    (optional subset filter).
  - `t` prefixes normalized (`t42` == `42`). Duplicate ids in either csv are
    deduped (idempotent). Any `ERROR:` line ⇒ no `COLUMN:`/`TASK:` lines are
    emitted (fail-closed validation, all errors listed).
- Ordering: columns in board `column_order` left-to-right order restricted to
  the requested set; `unordered` (dynamic Unsorted) is a valid requestable id,
  prepended before ordered columns when it has tasks; within each column tasks
  sort by ascending `boardidx`.
- **PINNED membership contract (must match the board's
  `TaskManager.get_column_tasks` semantics — the round-trip equivalence test
  in t1162_4 is the oracle):** active parent tasks only = top-level
  `aitasks/t*.md` (archived dir and `t<N>/` children excluded); **phantom
  stubs excluded** (mirror `_is_phantom_stub`, `aitask_board.py:539-541`:
  metadata empty or keys ⊆ `BOARD_KEYS = ("boardcol", "boardidx")` from
  `board/task_yaml.py:44` — layout-only files the board never displays);
  **no status filtering** (the board shows all statuses); `boardcol` defaults
  to `"unordered"` when absent; `boardidx` defaults to `0`; tie-break on equal
  `boardidx` must reproduce the board's ordering (stable sort by `boardidx`
  over the board's load order — t1162_1 pins the exact rule after reading
  `TaskManager.load_tasks`, and the equivalence test enforces agreement).
- Internal helper only — no new `ait` subcommand.
- Tests: new `tests/test_work_report_gather.sh` covering ordering,
  multi-column grouping, subsets, `t` prefixes, invalid/moved/missing tasks,
  Unsorted dynamics, duplicates, empty selections (the task's Verification
  list), **plus stale-selection scenarios** (a board-reviewed task that was
  since archived/deleted → `ERROR:unknown_task`; moved out of the selected
  columns → `ERROR:task_not_in_selected_columns`; **reordered within its
  column → `ERROR:task_order_changed`**), **`--list-columns` enumeration with
  and without Unsorted tasks present**, **protocol round-trips**
  (pipe-bearing column title and task path parsed intact via the
  last-field/maxsplit rule), **remaining-work semantics** (Done leaf → 0,
  fully-finished parent family `[]` → 0, pending parent → child count,
  active leaf → 1), **phantom-stub exclusion**, and **velocity**: fixture
  archived tasks with `completed_at` inside/outside the 7/30-day windows
  (frozen "now" seam for determinism), `pending_children` counts, and the
  zero-history `VELOCITY:<w>|0|0` case.

### t1162_2 — `work-report` code-agent operation + dry-run tests + whitelisting

- Add `work-report` to `SUPPORTED_OPERATIONS` (`aitask_codeagent.sh:26`) and a
  case arm in `build_invoke_command` for claudecode / codex / opencode composing
  `/aitask-work-report <args>` (model: the `explain` arms at `:435-438`,
  `:500-521`, `:528-529`). Codex uses the standard default-mode skill launch
  (no plan-mode forcing) — pinned by test.
- Add `"work-report"` to `_FRESH_WINDOW_OPERATIONS`
  (`lib/agent_command_screen.py:64-66`).
- **Seed the per-operation default (this is the "lightweight model class"):**
  `seed/codeagent_config.json` and the live
  `aitasks/metadata/codeagent_config.json` carry
  `.defaults.explain = "claudecode/sonnet4_6"`; without a `work-report` entry
  the resolution chain falls through to `DEFAULT_AGENT_STRING`
  (`claudecode/opus4_8`) — a *different, heavier* default. Add
  `"work-report": "claudecode/sonnet4_6"` to **both** files (mirroring
  `explain`'s entry).
- Add `work-report` verified-score entries to `seed/models_*.json` (mirror
  `explain` values) and any live `aitasks/metadata/models_*.json` present.
- Whitelist `aitask_work_report_gather.sh` in all 5 touchpoints (run
  `aitask_audit_wrappers.sh` to verify).
- Tests: extend/model `tests/test_codeagent.sh` — dry-run invoke for each of
  the 3 agents with `--columns`/`--tasks` args passed through verbatim; assert
  codex command contains no plan-mode flag; **assert
  `aitask_codeagent.sh resolve work-report` returns the same agent string as
  `resolve explain` under the seeded config (both `claudecode/sonnet4_6`) and
  in a no-config environment (both fall to `DEFAULT_AGENT_STRING`)**.

### t1162_3 — `/aitask-work-report` skill + agent wrappers

- `.claude/skills/aitask-work-report/SKILL.md` (plain static skill):
  1. Parse args: `--columns <csv>`, `--tasks <csv>` optional.
  2. No args → interactive: **column discovery via
     `aitask_work_report_gather.sh --list-columns`** (the only discovery
     source — it emits `unordered` first when Unsorted currently has tasks, so
     the dynamic column is always offered), `AskUserQuestion` multiSelect for
     columns, then run the gatherer with the chosen columns and present the
     ordered task list for exclusions (multiSelect, paginate past 4-option
     limit). With explicit `--tasks` → validate via gatherer and **skip**
     membership prompts (board already reviewed the selection).
  3. **Fail-closed gatherer parsing (PINNED):** after ANY gatherer run, if the
     output contains one or more `ERROR:` lines or is `NO_TASKS`, the skill
     MUST stop before drafting — present every error verbatim (e.g. a
     board-reviewed task archived/moved between board launch and agent
     execution), and offer via `AskUserQuestion`: re-select interactively /
     abort. It never drafts from a partial or silently-corrected selection —
     the report must contain exactly the validated selected tasks.
  4. Horizon question on EVERY run: "Today" / "This week" / custom label (via
     Other free text). Labels the report only — never changes membership.
  5. For each selected task: read task file (description, metadata, depends),
     active plan (`aitask_query_files.sh plan-file <id>`), and — **PINNED
     child-context rules** for parents with children: the report line covers
     the parent as a single manager-level item; pending children
     (`children_to_implement`) inform the "outcome" phrasing and progress
     (e.g. "3 of 5 subtasks complete", derived from pending vs archived
     children via `aitask_query_files.sh archived-children <id>`); done/
     archived children are counted, never listed individually; folded tasks
     are merged content and never appear as separate items; child plans are
     NOT mined for implementation-level file/symbol detail.
  6. Draft first-person manager-friendly Markdown: short focus summary →
     column-grouped ordered priorities (outcome + current status + `t<id>`
     for traceability) → **throughput-based completion projection** → final
     blockers/manager-asks section. Exactly the selected tasks; no invented
     dates/estimates/progress/commitments; no implementation-level file/symbol
     detail.
  6b. **Completion projection (PINNED — explicit AC amendment, user-requested):**
     the original AC forbids *invented* estimates; **data-derived projections
     from the gatherer's `VELOCITY:` lines are in scope** and must be labeled
     as projections from historical throughput, never as commitments.
     Mechanics: work items = Σ over selected tasks of `remaining_items` (the
     gatherer's remaining-work field — Done leaves and fully-finished parent
     families contribute 0, so included-but-finished items never inflate the
     estimate; if the sum is 0, say the selection is effectively complete and
     omit the projection); throughput = `avg_per_day` (prefer
     the 30-day window; mention the 7-day figure when it diverges notably);
     projected days ≈ work items ÷ avg_per_day, compared against the chosen
     horizon (e.g. "≈ N days at the recent pace of X tasks/day — roughly
     fits / exceeds this week"). If velocity is 0 (no history), state
     "insufficient completion history for a projection" and omit the section
     — never fabricate a rate.
  7. Present in-session for review/editing (iterate on feedback). Do NOT write
     a report file.
  8. Satisfaction Feedback Procedure with `skill_name: work-report`.
- Wrappers: `.agents/skills/aitask-work-report/SKILL.md`,
  `.opencode/skills/aitask-work-report/SKILL.md`,
  `.opencode/commands/aitask-work-report.md` (copy the `aitask-changelog`
  wrapper shapes). Run `./.aitask-scripts/aitask_skill_verify.sh` (no-op for
  static skills but confirms nothing broke).
- **Skill contract guard test** (`tests/test_work_report_skill_contract.sh`):
  the fail-closed behavior lives in static SKILL.md prose, so pin it at the
  source (enforce-in-source over trusting agents): assert the canonical
  SKILL.md contains the load-bearing contract markers — the fail-closed
  `ERROR:`/`NO_TASKS` hard-stop section, the "never drafts from a partial or
  silently-corrected selection" sentence, the `--list-columns` discovery
  requirement, the no-report-file rule, and the projection's
  "insufficient completion history" fallback — and that all 3 wrapper files
  point at the canonical path. A contract edit that drops any marker fails
  the test.

### t1162_4 — Board `w` Work Report flow + Pilot tests

- `Binding("w", "work_report", "Work Report")` in `KanbanApp.BINDINGS`
  (auto-customizable via ShortcutsMixin).
- `check_action` gate: hide (`return False`) when
  `self.base_filter in ("inflight", "bytopic")` or `_get_focused_col_id()`
  yields no column (works for focused card AND collapsed placeholder).
- `action_work_report`:
  1. **Column multi-select** — new `ModalScreen` modeled on
     `IssueTypeFilterScreen` (`SelectionList`, Space/Enter/Escape): options =
     `column_order` columns with `unordered` prepended when non-empty; focused
     column initially checked.
  2. **Task multi-select** — second modal, grouped by chosen columns in board
     order, one `Selection` per underlying parent task, ALL initially checked;
     contents from `manager.get_column_tasks(col_id)` (full column, ignores
     search/board filters). Board ordering preserved after exclusions.
  3. Empty columns or empty tasks selection → `self.notify(...)`, no launch.
     Escape at either modal cancels cleanly.
  4. Launch: `resolve_dry_run_command(Path("."), "work-report", "--columns",
     csv, "--tasks", csv)` → `AgentCommandScreen(..., operation="work-report",
     operation_args=["--columns", csv, "--tasks", csv],
     skill_name="work-report")`, prompt `"/aitask-work-report --columns …
     --tasks …"`; result callback mirrors `action_pick_task` (`:5668-5678`).
- Pilot/unit tests (model `test_board_footer_visibility.py`,
  `test_board_view_filter.py`, agent-command dialog tests): footer visibility
  per view + focus state, collapsed-placeholder focus, defaults (focused column
  checked; all tasks checked), full-column behavior under active search/filter,
  cancellation, empty selection, stable ordering, exact launch args, shortcut
  registration (`test_shortcuts_registry_coverage.sh` picks up the new binding).
- **Round-trip equivalence test (membership-contract oracle):** on a shared
  fixture tree (including Unsorted tasks, `boardidx` ties, archived tasks, a
  parent with children, missing `boardcol`, **and a phantom layout stub —
  boardcol/boardidx-only frontmatter**), assert that the exact
  `--columns`/`--tasks` args the board `w` flow would launch, when fed through
  `aitask_work_report_gather.sh`, reproduce the same task membership AND order
  the board modal displayed (`TaskManager.get_column_tasks` per column). This
  pins the two independent implementations (board Python vs gatherer) against
  drift on archived exclusion, child exclusion, phantom-stub exclusion,
  default `boardcol`, status filtering, tie-break ordering, and Unsorted
  behavior. The launch site composes `--tasks` in exactly the displayed
  grouped order (the reviewed sequence the gatherer's order check defends).

### t1162_5 — Documentation

Per `aidocs/framework/documentation_conventions.md` (current-state-only,
genericize agent names):
- `website/content/docs/skills/aitask-work-report.md` + row in
  `skills/_index.md` table.
- `website/content/docs/workflows/work-report.md` + bullet in the
  hand-curated `workflows/_index.md`.
- Board shortcut: `tuis/board/reference.md` keyboard-shortcuts table +
  `tuis/board/how-to.md` narrative.
- `commands/codeagent.md` supported-operations list.
- Verify: `cd website && hugo build --gc --minify` + link check.

### Aggregate manual-verification sibling (offered at creation time)

Recommend creating it (TUI-heavy work). Checklist covers the happy path AND
the failure paths that live only in skill prose:
- Happy path: focus a board column, press `w`, change both selections, launch
  an agent, choose a period, confirm the report contains exactly the selected
  tasks in board order (with the projection section present and labeled).
- **Validation-error stop:** launch from the board, then archive/delete one
  selected task before the agent runs the gatherer → verify the skill stops
  with the error shown and offers re-select/abort (does NOT draft).
- **Stale reorder:** reorder a selected task within its column after board
  launch → verify `task_order_changed` stops the draft.
- **Zero-history projection:** run against a tree with no archived
  completions → verify "insufficient completion history" and no fabricated
  rate.
- **Custom horizon:** choose a custom label via free text → verify it labels
  the report without changing membership.

## Post-approval flow (this session)

Create the 5 children via the Batch Task Creation Procedure, write the 5 child
plans to `aiplans/p1162/`, revert parent to Ready + release parent lock, offer
the manual-verification sibling, then child checkpoint (start first child /
stop). Step 9 (Post-Implementation) archival/merge runs per child and for the
parent when all children complete.

## Verification (parent-level)

- `bash tests/test_work_report_gather.sh`, `bash tests/test_codeagent.sh` (+
  new work-report dispatch asserts), board Python tests
  (`tests/test_board_*`), `bash tests/test_shortcuts_registry_coverage.sh`.
- `./.aitask-scripts/aitask_skill_verify.sh`; `aitask_audit_wrappers.sh` for
  whitelist coverage.
- Hugo build for docs.
- Manual smoke test via the aggregate manual-verification sibling.

## Risk

### Code-health risk: low
- `check_action` additions could disturb existing footer gating for other keys · severity: low · → mitigation: covered by existing + new Pilot footer-visibility tests (no separate task)
- Wrapper/whitelist drift across 5 touchpoints · severity: low · → mitigation: `aitask_audit_wrappers.sh` verification in t1162_2 (no separate task)

### Goal-achievement risk: medium
- AC breadth across 5 surfaces (focused-column defaults, filter bypass, collapsed placeholders, exact launch args) risks a slipped requirement · severity: medium · → mitigation: aggregate manual-verification sibling (created at decomposition time)
- "Lightweight model class used by explain" = the seeded `.defaults.explain = claudecode/sonnet4_6` entry — omitting a `work-report` entry would silently fall through to the heavier `DEFAULT_AGENT_STRING` · severity: low · → mitigation: seeded `.defaults.work-report` in both configs + resolve-equivalence dry-run test (t1162_2)
- Board modal and gatherer are two independent membership implementations that could drift (archived/child exclusion, tie-breaks, Unsorted) · severity: medium · → mitigation: pinned membership contract (t1162_1) + round-trip equivalence test (t1162_4)
- Stale board selection between launch and agent execution could silently drop OR reorder tasks · severity: medium · → mitigation: fail-closed `ERROR:`/`NO_TASKS` skill contract (t1162_3) + order-significant `--tasks` with `task_order_changed` + stale-selection/reorder gatherer tests (t1162_1)
- Fail-closed behavior lives in static SKILL.md prose — an agent could draft past a validation error · severity: medium · → mitigation: skill contract guard test pinning the load-bearing markers (t1162_3) + explicit failure-path items in the MV sibling checklist
- Projection could overstate remaining work (Done leaves, finished parent families) or mismatch velocity units · severity: low · → mitigation: pinned `remaining_items` semantics decoupled from membership + remaining-work and velocity fixture tests (t1162_1)
