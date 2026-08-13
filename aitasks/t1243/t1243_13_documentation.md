---
priority: medium
effort: medium
depends: [t1243_12]
issue_type: documentation
status: Ready
labels: [aitask_board, web_site, development]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-07-28 01:18
updated_at: 2026-07-28 01:18
---

## Context

**Child 13 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md`).

Documentation is a **first-class deliverable** for a user-visible TUI feature,
not a verification afterthought (`aidocs/framework/planning_conventions.md`,
"User-facing features: docs are a plan deliverable"). This child covers both the
board feature docs and the `boardgroup` frontmatter-field surfaces, which drift
independently.

**Read `aidocs/framework/documentation_conventions.md` first** — current-state-only
prose (no version history in doc bodies), and genericize any passage that names
specific coding agents.

## Key files to modify

### A. Board feature docs (`website/content/docs/tuis/`)

The board page(s) — groups and the new keys. Cover:

- **Task groups**: what a group is (a named, ordered collection inside one
  column), that membership lives in the task file as `boardgroup`, that a group
  expands/collapses and moves as a block, and that collapse state is per-user.
- **Group commands**: `G`, and the command-palette entries.
- **`x`** now expands/collapses "the thing under focus" — children on a card,
  the group on a header.

> **Scope narrowed — twice.** Marking (`space`, `☑`/`☐`) and bulk
> move-to-column (`m`) were documented by **t1432**; the **shipped half of task
> groups** was then documented by **t1504** (the v0.31.0 docs-gap sweep), which
> again covered the landed board surfaces while this child stayed blocked behind
> `t1243_12`. Already written by t1504, on the live pages — do **not**
> re-introduce it:
>
> - `board/how-to.md` — "How to Group Tasks in a Column": what a group is,
>   field-based membership via `ait update --boardgroup` (including the
>   reject-don't-coerce rule and the `""` tombstone), the 2+-member header vs the
>   single-member plain card, `x`-on-header collapse, focus units, the `· N
>   match` filter badge, and per-user collapse persistence in
>   `board_config.local.json`.
> - `board/reference.md` — the second `x` row (group header context), a "Group
>   Header Anatomy" block, the `boardgroup` metadata / board-data-field entries,
>   and the `board_config.local.json` row.
> - `development/task-format.md` — the `boardgroup` frontmatter row.
>
> **This child now owns:** `G`, group *formation* and block moves, the group
> command-palette entries, in-board membership commands (t1243_11 / t1243_12),
> and **all of section B's non-website `boardgroup` surfaces** — the seed block,
> the `AGENTS.md` regeneration, `CLAUDE.md`, and the `.codex` / `.opencode`
> instruction mirrors, none of which t1504 touched. When t1243_12 lands, the
> how-to's "Assigning membership" subsection will need the in-board command
> added beside the CLI form; build on that prose rather than replacing it.

Do **not** document `diffviewer` or add it to any list of TUIs (project note in
`CLAUDE.md`).

### B. `boardgroup` frontmatter-field surfaces

Per `aidocs/framework/aitasks_extension_points.md` "Adding a new frontmatter
field", layer 5 enumerates surfaces that drift independently — update **all** of
them:

- `seed/aitasks_agent_instructions.seed.md` "## Task File Format" YAML block,
  then regenerate the **AGENTS.md** mirror via the `ait setup` path
  (`update_agentsmd`, `>>>aitasks` markers). Update the
  `.codex/instructions.md` / `.opencode/instructions.md` mirrors **by hand** to
  match the seed — they are markerless full-file format, and running
  `insert_aitasks_instructions` on them appends a duplicate block.
- `CLAUDE.md` "### Task File Format" YAML block (hand-maintained, no markers).
- `website/content/docs/development/task-format.md` "### Frontmatter Fields"
  table.
- `.claude/skills/task-workflow/task-creation-batch.md` — only if a creation flag
  was added. **It was not**: `--boardgroup` is update-only, mirroring
  `--boardidx`, which is absent from `aitask_create.sh`. Confirm and note this
  rather than inventing a flag.
- The board `tuis/board/reference.md` row (the board renders the field via
  `BoardGroupField`).

Also pick up any layer t1243_8 flagged as uncovered in its Final Implementation
Notes.

## Reference files for patterns

- `aidocs/framework/aitasks_extension_points.md` — the worked `anchor` example
  (t1016) is the closest precedent for a scalar board-adjacent field.
- The existing `anchor` rows in `task-format.md` and the seed YAML block.

## Implementation plan

1. Read the **live** source of truth for each surface before editing — archived
   plans drift; do not copy from this task description where the code disagrees.
2. Write the board feature docs from the landed behaviour, not from the design
   plan (children 9–12 may have adjusted details).
3. Sweep the frontmatter surfaces in the order listed, regenerating AGENTS.md via
   the `ait setup` path rather than editing it directly.
4. Add a bullet to the workflows/TUI index page if one is required — those index
   pages are **hand-curated lists**, not generated.

## Verification

- **Drift grep:** every key documented as a board shortcut actually exists in
  `KanbanApp.BINDINGS` (and vice versa for the keys this feature added).
- `boardgroup` appears in **all** enumerated frontmatter surfaces; grep each path
  explicitly and report the hit count rather than assuming.
- `AGENTS.md` matches the seed block after regeneration (no duplicated block).
- `hugo build --gc --minify` succeeds in `website/`.
- No passage names a specific coding agent where a generic phrasing would do.
