---
name: aitask-work-report
description: Draft a manager-facing work report from selected board columns.
---

## Overview

Drafts a first-person, manager-friendly Markdown report of upcoming work,
built from selected `ait board` columns. Task membership and ordering come
from the deterministic gatherer helper
(`./.aitask-scripts/aitask_work_report_gather.sh`) — the report contains
exactly the validated selected tasks, in board order, or it is not drafted
at all.

## Gatherer output contract (PINNED)

Every gatherer stdout line must match one of these record schemas:

```
COLUMN:<col_id>|<title>
TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<task_file_path>
VELOCITY_MODEL:<model_id>|<window_days>|<start_date>|<end_date>|<model_label>
VELOCITY:<bucket_id>|<observed_units>|<completed_count>|<avg_per_unit>|<bucket_label>
PROJECTION:<remaining_total>|<projected_date>|<days_ahead>|<basis_completions>|<caveat>
ERROR:<reason>[:<detail>]
NO_TASKS
```

Split each record on `|` with **maxsplit = field-count − 1**: the free-text
field is always LAST (`<title>`, `<task_file_path>`, `<model_label>`,
`<bucket_label>`); `PROJECTION:` and `ERROR:` have no free-text field. Note
the `VELOCITY:` field order: bucket id, **observed units, completed count,
average**, then label — do not swap counts and averages.

Any line matching none of these prefixes, or a recognized prefix with the
wrong field count, is a **malformed record**: treat it as an infrastructure
failure (hard stop per Step 2) — never guess, reorder, or skip fields.

## Workflow

### Step 0: Parse Arguments

Arguments arrive as flat whitespace-delimited text (the code-agent dispatcher
rejects whitespace-bearing values, so token splitting is safe). Recognize:

- `--columns <csv>` — column ids to report on (optional).
- `--tasks <csv>` — task ids, order significant (optional; requires
  `--columns`).
- `--velocity-model <id>` and `--velocity-window <days>` — optional; forward
  them **verbatim to every gatherer invocation** (including the `--project`
  re-run). When absent, the gatherer's defaults apply.

### Step 1: Select Columns and Tasks

**With `--columns` (+ optional `--tasks`):** run the gatherer once with the
exact args and SKIP all membership prompts — the board already reviewed the
selection:

```bash
./.aitask-scripts/aitask_work_report_gather.sh --columns <csv> [--tasks <csv>] [velocity args]
```

Then apply Step 2 to the output and, if it passes, proceed to Step 3.

**Without `--columns` (interactive path):**

1. Column discovery MUST use
   `./.aitask-scripts/aitask_work_report_gather.sh --list-columns` as the
   only discovery source (it emits `unordered` first when the Unsorted
   column currently has tasks — the dynamic column is always offered).
   **Validate the discovery run first** — apply Step 2 in list mode: a
   non-zero exit, any `ERROR:` line, or any malformed record (the only
   well-formed records in list mode are `COLUMN:` lines) is a hard stop
   per Step 2. Zero `COLUMN:` lines is NOT a hard stop in list mode — it is
   handled next.
2. **Empty discovery:** if the validated run exited 0 with zero `COLUMN:`
   lines, there are no reportable columns — inform the user ("the board has
   no reportable columns — nothing to report") and END the skill. Never
   present an empty selection prompt.
3. Otherwise present the columns via `AskUserQuestion` with
   `multiSelect: true`, using the **Paginated multi-select protocol** below
   (selection semantics: selected = included column).
4. Run the gatherer with the chosen columns (plus any velocity args), apply
   Step 2, then present the ordered task list for exclusions:
   `AskUserQuestion` with `multiSelect: true` via the same protocol, one
   option per `TASK:` row (label = `t<task_id>`, description = column +
   status + a short name derived from the task filename). Phrase each page
   as "Select any tasks to EXCLUDE from the report" — **every listed task
   is included unless explicitly selected for exclusion** (this matches the
   tool's semantics: options start unselected, so include-by-default means
   select-to-exclude).
5. If the user excluded tasks, re-run the gatherer with the surviving ids as
   an explicit ordered `--tasks` list (canonical board order) and apply
   Step 2 again — the final selection is always gatherer-validated.

**Paginated multi-select protocol** (used by both selection prompts):

- `AskUserQuestion` supports a maximum of 4 options: show 3 candidate items
  per page, plus a "Show more" option while more items remain (the last page
  shows up to 4 items and no "Show more").
- Keep an **accumulator across pages**: every candidate item selected on any
  page is added to it and is never dropped by later pages.
- A response that selects both candidate items and "Show more" records those
  items in the accumulator AND advances to the next page.
- The loop ends when a response does not include "Show more", or the last
  page is answered. Pages never reached keep their items in the default
  state (columns: not included; tasks: not excluded — i.e. still in the
  report).
- The final result is the accumulator applied in canonical gatherer order
  (the pages' presentation order never reorders anything).

**Agents without native multi-select** (e.g. Codex CLI, whose
`request_user_input` mapping has no multi-select adaptation): do NOT emulate
with one yes/no question per item. Instead present the full candidate list
as numbered text and ask ONE free-text question for a
comma-separated list of ids, handled per branch:

- **Column selection:** the answer lists column ids to include. Preserve
  each id exactly as typed — column ids are opaque strings and may
  legitimately start with `t` (e.g. a `tests` column), so NO prefix
  stripping. Trim whitespace only, then run the gatherer with
  `--columns <selected-columns>` (point 4).
- **Task exclusion:** the answer lists task ids to exclude (empty answer =
  exclude none). Task ids are numeric with an optional `t` prefix —
  normalize by trimming and stripping the optional `t` on task ids ONLY.
  **Validate every exclusion BEFORE subtracting:** each normalized
  exclusion id must be a member of the displayed validated task-id set —
  an unknown id, or input that normalizes to nothing (e.g. a bare `t` or
  empty token), is a hard stop through the Step 2 re-select/abort prompt,
  never a silent no-op (subtract-first would make a typo like `9999`
  vanish without rejection, and the survivors would still validate).
  Only after all exclusions validate, remove them from the selection and
  re-run the gatherer with the survivors as an ordered `--tasks` list in
  canonical board order (point 5).

In both branches every id the user typed is checked — column ids and the
final task list by the gatherer, exclusion ids by the pre-subtraction
membership check — so any typo or unknown id fails closed rather than
silently dropping.

### Step 2: Fail-Closed Validation (NON-NEGOTIABLE — after EVERY gatherer run)

Hard-stop conditions, checked in this order:

1. **Non-zero exit status** — usage error, malformed board config, or
   infrastructure/read failure. The gatherer prints diagnostics to stderr
   only, with no stdout sentinel.
2. One or more `ERROR:` lines, or `NO_TASKS`.
3. **Missing expected output** (exit 0 but no `TASK:` line in report mode)
   or any **malformed record** per the pinned schema block above. In
   **list mode** (`--list-columns`) the only well-formed records are
   `COLUMN:` lines; a malformed record still hard-stops, but a zero-row
   result is the intentional empty-board case handled by Step 1's
   empty-discovery path, not a hard stop.

On ANY of these: STOP — do not draft. Present the diagnostics verbatim
(stderr for condition 1; every `ERROR:` line for condition 2; the offending
line for condition 3), then `AskUserQuestion`:

- Question: "The gatherer rejected the selection (details above). How would
  you like to proceed?"
- Header: "Selection"
- Options:
  - "Re-select interactively" (description: "Restart Step 1 on the
    interactive path")
  - "Abort" (description: "End the skill without drafting a report")

This skill never drafts from a partial or silently-corrected selection — the
report must contain exactly the validated selected tasks, parsed from
well-formed records only.

### Step 3: Report Horizon (every run)

Use `AskUserQuestion`:

- Question: "What period should this report cover?"
- Header: "Horizon"
- Options:
  - "Today" (description: "Label the report as today's plan")
  - "This week" (description: "Label the report as this week's plan")
  - A custom label can be typed via the built-in "Other" free-text option
    (e.g. a sprint or milestone name)

The period labels the report only — it never changes task membership.

### Step 4: Gather Per-Task Context

For each selected task (each `TASK:` row):

- Read the task file (`<task_file_path>`): description, frontmatter metadata,
  `depends`.
- Read the active plan when present:
  `./.aitask-scripts/aitask_query_files.sh plan-file <task_id>`
  (`PLAN_FILE:<path>` → read it; `NOT_FOUND` → skip).
- For parents with children: pending list from `children_to_implement` in the
  task frontmatter; archived (completed) children via
  `./.aitask-scripts/aitask_query_files.sh archived-children <task_id>`.

Child-context rules (PINNED):

- One manager-level line per parent task.
- Progress phrased as "N of M subtasks complete" (archived = complete,
  `children_to_implement` = pending).
- Done/archived children are counted, never listed individually.
- Folded tasks are merged content — never separate report items.
- Do NOT mine child plans for implementation-level file/symbol detail.

### Step 5: Draft the Report

First-person, manager-friendly Markdown, in-session only:

- **Focus summary** — 2-3 sentences on the overall thrust of the selected
  work under the chosen horizon label.
- **Column-grouped priorities** in gatherer order: per task — the outcome
  (what will be delivered, at benefit level), current status, and `t<id>`
  for traceability.
- **Observed throughput** (default section): render the `VELOCITY:` rows
  **generically** — per bucket: `<bucket_label>`, `<avg_per_unit>`, and
  `<observed_units>` (quote the observed units so the reader can judge
  confidence). The estimator is selectable (`--velocity-model`), so do NOT
  hardcode weekday semantics or bucket meanings.
- **Completion projection — opt-in.** Include it ONLY when the user
  explicitly asks for a forecast. Then re-invoke the gatherer with
  `--project` (same columns/tasks/velocity args) and read the `PROJECTION:`
  record. The gatherer computes it — report it as-is; do NOT recompute it
  and do NOT do date arithmetic in-prompt.
  - `remaining_total` is `0` → say the selection is effectively complete and
    omit the projection.
  - `PROJECTION:<n>|none|insufficient_data|…` → state
    "insufficient completion history for a projection" and omit the
    section — never fabricate a rate.
  - Otherwise quote `<projected_date>`, `<days_ahead>` and
    `<basis_completions>`, and **always surface `<caveat>`**: the figure
    counts tasks, so it ignores task size, blockers and capacity — an
    extrapolation of past throughput, never a commitment or a delivery
    estimate.
  - **Horizon comparison:** a fits/exceeds judgement is made ONLY for the
    "Today" horizon, read directly off `<days_ahead>`: `0` → fits today,
    `> 0` → exceeds today (a field read, not arithmetic). For "This week"
    and custom labels, show the horizon label plus the gatherer-provided
    `<projected_date>` / `<days_ahead>` without any inferred fits/exceeds
    judgement — deciding "fits this week" would require computing days
    remaining in the week, and the skill cannot know what date a custom
    label denotes.
- **Blockers / manager-asks** — only real blockers from `depends` and task
  content. Nothing invented.

Constraints: include exactly the selected tasks; no invented dates,
estimates, progress, commitments, dependencies, or blockers; no
implementation-level file/symbol detail.

### Step 6: Present and Iterate

Present the draft in-session for review and editing; iterate on feedback
until the user is satisfied. Do NOT write a report file (no dated file, no
repository file) — the draft lives in the session only.

**Finalization (before Step 7):** when the user signals they are satisfied
("finalize", "good", "ship it", etc.), **re-render the COMPLETE report as a
single consolidated block** — every iterated edit and any opt-in projection
integrated inline — and present that as the final version *before* moving to
Step 7. Never advance to the satisfaction prompt while the latest full report
exists only as separate deltas across earlier turns (e.g. a projection or a
correction shown on its own): the reader must see one whole, current report,
not a stitch of fragments.

### Step 7: Satisfaction Feedback

Execute the Satisfaction Feedback Procedure
(`.claude/skills/task-workflow/satisfaction-feedback.md`) with
`skill_name` = `"work-report"`.

## Notes

- The gatherer is the single source of membership/order truth; it is
  board-equivalent by construction (see
  `aiplans/archived/p1162/p1162_1_work_report_gatherer_helper.md`).
- The board `w` flow launches this skill with explicit `--columns`/`--tasks`
  so the agent receives the exact board-reviewed selection.
