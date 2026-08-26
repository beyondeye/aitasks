---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [aitask_ls, aitask_board]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-26 17:57
updated_at: 2026-08-26 17:59
---

## Problem

There is no way to ask `ait ls` for the tasks in a board column. Answering
"what's in `now`?" today means hand-rolling a `sed`/`grep` sweep over every
task file's frontmatter — which is what a session had to do on 2026-08-26 to
answer exactly that question.

`aitask_ls.sh` does not read `boardcol` **at all** (grep count: 0), and the
field is missing from its `--help` METADATA FORMAT list even though every other
frontmatter key it parses is documented there.

## How the board resolves a column (reuse this, do not re-derive)

The board does not *filter* by column — it **groups** tasks into lanes. The
Textual-free canonical seam is `.aitask-scripts/lib/board_columns.py`:

- `_column_of(metadata)` (`board_columns.py:503`) — `metadata.get("boardcol",
  UNORDERED_ID)`, with a **non-string** `boardcol` mapped to `""` so it matches
  no column (a `boardcol: 42` parses typed and would otherwise match nothing
  silently — see the YAML-typing hazard).
- `UNORDERED_ID = "unordered"` (`:117`) — a **synthetic** lane, deliberately NOT
  in `columns` / `column_order`. The board hand-injects it, and it exists only
  while some task has no column of its own.
- Columns are **per-project configurable** (`aitasks/metadata/board_config.json`,
  via `load_columns_at` / `project_columns_at`). `DEFAULT_ORDER =
  ["now", "next", "backlog"]` (`:111`) is a fallback, **not** a fixed vocabulary
  — nothing may hardcode those three ids.
- `aitask_update.sh --boardcol` already validates a supplied id against the
  configured columns (t1377_1); `lib/task_utils.sh:989` records why.

## Existing drift to fix, not extend

`lib/work_report_gather.py:194-196` already selects tasks by board column for
`/aitask-work-report` — and **re-implements** `_column_of` inline instead of
importing it. Adding a third, bash-side copy in `aitask_ls.sh` would make three
implementations of one rule.

Prefer routing the bash side through the existing Python seam (the shape
`aitask_work_report_gather.sh` already uses: `require_ait_python` + `exec` into
`lib/`), and fold the `work_report_gather.py` copy back onto `_column_of` in the
same change. If a bash-local read is genuinely unavoidable for performance,
say so explicitly and add a drift guard that fails when the two disagree.

## Two decisions that are not plumbing

1. **The unordered lane must be reachable.** `--boardcol unordered` has to match
   tasks carrying **no** `boardcol` field, or a whole lane of the board is
   unfilterable from the CLI. Decide and document it; do not let it fall out of
   the implementation by accident.
2. **An unknown column id must be refused, not silently empty.** Without
   validation, `--boardcol now` against a project with renamed columns returns
   zero rows — indistinguishable from "that column is empty". Validate against
   the configured columns and fail with the valid set named, reusing
   `aitask_update.sh`'s existing validator rather than a second one.

## Suggested implementation

`aitask_ls.sh` — the change is mechanical and mirrors the existing `--type`
filter end to end:

1. `boardcol)` case in `parse_yaml_frontmatter` (`aitask_ls.sh:344`), setting
   `boardcol_text`.
2. Reset `boardcol_text` in `parse_task_metadata` (`:531`) alongside the other
   per-file globals.
3. `--boardcol COL` flag + a filter block in `process_task_file`, placed with
   the `--status` / `--labels` / `--type` blocks.
4. Document `boardcol` in the `--help` METADATA FORMAT list (currently absent)
   and add the flag to OPTIONS.
5. Consider surfacing the column in the `-v` line. **Decide deliberately**: the
   `-v` format is parsed by the pick skills (`aitask-pick`'s Step 2a documents
   its exact shape, including the optional `, Follow-up:` and `, Plan: approved`
   segments), so any addition must follow that established optional-segment
   convention and the skills' parsing text updated in the same change.

## Verification

- `ait ls --boardcol now` matches the board's `now` lane exactly — compare
  against `ait board` (or a `board_columns.py` query) for the same project,
  not against a hand-written expectation.
- `--boardcol unordered` returns tasks with no `boardcol` field, and only those.
- `--boardcol <unknown>` **fails** with the configured column ids named; it does
  not exit 0 with no rows.
- A project with **renamed** columns (not now/next/backlog) filters correctly —
  this is the case that catches a hardcoded default order.
- A task with a non-string `boardcol` (e.g. `boardcol: 42`) matches nothing,
  matching board behaviour.
- Composes with the existing filters: `--boardcol now --status all`,
  `--boardcol now -l <label>`, `--boardcol now --type bug`.
- `--all-levels` / `--children` still behave (children carry their own
  `boardcol`).
