---
priority: high
effort: high
depends: [t1468_2]
issue_type: feature
status: Implementing
labels: [aitask_board, ui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1468
created_at: 2026-08-10 16:29
updated_at: 2026-08-11 14:45
---

## Context

Parent: t1468 — mark auto-spawned follow-up tasks with a machine-readable kind.
Depends on **t1468_1** (the `followup_kind:` field and
`.aitask-scripts/lib/followup_kinds.tsv`).

This child makes a follow-up **recognisable at first sight on the board**. The
user's explicit acceptance criterion: identifiable through **both colour and
shape**, at a glance. A leading gutter glyph in the title row (not the badge
line) keeps cards scannable down a column.

Read the parent plan
`aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md`.

**This child does NOT depend on t1468_5** — see the per-surface table below.

## Key file

`.aitask-scripts/board/aitask_board.py` (one file, several seams).

### Glyph + colour source — one authority

Derive the maps from `.aitask-scripts/lib/followup_kinds.tsv` (created in
t1468_1). Mirror the house precedent: `TRAIL_CLASSIFICATION_GLYPHS` (`:609-618`)
and `_trail_badge_text` (`:2912-2919`), which uses a `·` fallback for an unknown
classification.

**Colour comes from the TSV, not from CSS.** Build the gutter label as
`Label(Text(glyph, style=<tsv colour>))`. Textual CSS cannot read the TSV, so a
`.fk-<kind>` colour class would be a second, unsynchronisable source that a
key-only drift test cannot catch — one authority makes drift *impossible* rather
than merely detectable. A literal Rich style also resolves in **both**
`render().spans` and composited strips, whereas an unresolved CSS colour name
resolves in neither.

Add **one** shared CSS class for layout only (`width: auto; margin: 0 1 0 0;`),
beside `.task-mark` / `.task-number` at `:6808-6810`. Do **not** introduce
per-kind colour classes.

### Totality boundary

`lib/task_yaml.py` deliberately leaves values type-honest, so a hand-edited or
foreign `followup_kind` can arrive as `None`, list, dict, int or bool. Write a
`normalize_followup_kind` boundary function — copy `normalize_group_slug`
(`.aitask-scripts/lib/board_groups.py:63-99`) — and **never read the raw value
inside `compose`**.

### Per-surface behaviour — DECIDED, not an implementation-time choice

All three `TaskCard` subclasses **fully override** `compose` (no `super()` call),
so each needs the glyph added explicitly; none inherits it.

| card | line | decision | data source |
|---|---|---|---|
| `TaskCard` (kanban, topic, child) | `:2625` | **must show** | `self.task_data.metadata` (`:2626`, unfiltered) |
| `InFlightTaskCard` | `:2786` | **must show** | `InFlightItem.task` (`:104`) is the **real `Task`** — read `item.task.metadata`; no new plumbing |
| `TrailTaskCard` | `:2956` | **must show** | `__init__` passes `view.task` to `super()`, so `self.task_data` is the real `Task` — read **frontmatter, not the trail snapshot** |
| `TrailGhostCard` | `:3006` | **shows no glyph, by design** | `_GhostTaskStub.metadata` is `{}` (`:2905`). A ghost is a referenced task with no local file — nothing to classify, nothing to pick. |
| `GroupHeader` | `:2314` | **must show a roll-up** | `self.members` (task data) |

Reading frontmatter rather than the trail snapshot on `TrailTaskCard` is what
**removes any dependency of this child on t1468_5** — the snapshot field added
there serves the trail *document*, not board rendering.

### Placement in the title row

`TaskCard.compose` `:2632-2641`: the gutter `Label` goes **after** the ☑/☐ mark
and **before** the task number. It must **not** hang off the mark —
`markable=True` is set only in `KanbanColumn.task_block:3534`, so `TopicColumn`
cards (`:2878-2887`) and child cards have no mark.

### Collapsed groups

`KanbanColumn.compose:3500-3517` mounts **no member cards** when a group is
collapsed (`continue` skips `task_block`, dropping members and their
`.child-wrapper` rows), so a glyph on a member is invisible there. Add a roll-up
to `GroupHeader._label()` (`:2340-2342`) — it already carries `self.members` as
*data* for exactly this purpose (t1243_10 reads the same list for a `· 2 match`
badge). Something like `▾ perf work (3) · 1 follow-up`.

## Reference files for patterns

- `tests/test_board_marking.py` `MarkGlyphRenderTests:159` — glyph on a plain
  `TaskCard` in a booted board; `label.render().plain` assertions; boots via
  `tests/lib/board_fixture.py` (`bf.enter_fixture_tree`, `:46`).
- `tests/test_board_bytrail_view.py:411-431` — per-card `CardApp` harness for
  `TrailTaskCard`; `:101-112` `_screen_rows` composited strips; `:184`
  glyph-map-keys drift guard to copy.
- `tests/test_board_inflight_view.py:225-249` — the same harness for
  `InFlightTaskCard`.
- `tests/test_board_group_focus.py:160,309` — `GroupHeader` `.render().plain`
  assertions.
- `tests/lib/board_fixture.py` — note the **TASK_DIR invariant** in its
  docstring: the relative literal `"aitasks"` with cwd inside the tree is
  required, or `is_modified` silently returns `[]`.

## Verification steps

**Render-level verification on every surface in the table above** — one test per
card class, not just `TaskCard`:

1. `label.render().plain` for the glyph on `TaskCard`, `InFlightTaskCard`,
   `TrailTaskCard`; **plus composited strips** (`_screen_rows`) for **width AND
   colour** — a `render().spans` check alone cannot see an unresolved colour, and
   width only shows up in the composited row.
2. `TrailGhostCard` renders cleanly with **no** glyph and does not crash on the
   empty-metadata fallback (this is a tested decision, not an omission).
3. Collapsed-group roll-up appears in `GroupHeader._label()`.
4. Glyph **uniqueness** and **single-cell width** pinned; drift guard asserting
   map keys == `followup_kinds.tsv` (precedent
   `tests/test_board_bytrail_view.py:184`).
5. Unknown / malformed value falls back safely (the `normalize_followup_kind`
   boundary) — cover `None`, a list, an int, and an unknown string.
6. `bash tests/run_all_python_tests.sh` (read the LAST line for the verdict).
7. **Live board in a real terminal** (`ait board`): a follow-up is identifiable
   at a glance by colour and shape — in a kanban column, in By-Topic, in
   In-Flight, in By-Trail, as a collapsed-group roll-up, and **at a narrow
   terminal width**. Visible is not the same as readable; check the narrow case
   explicitly.
