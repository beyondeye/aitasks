---
Task: t1468_3_board_card_followup_kind_glyph.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_1_*.md, aitasks/t1468/t1468_2_*.md, aitasks/t1468/t1468_4_*.md, aitasks/t1468/t1468_5_*.md, aitasks/t1468/t1468_6_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
---

# p1468_3 — Board card `followup_kind` glyph (shape + colour)

Context and the per-surface decision table are in
`aitasks/t1468/t1468_3_board_card_followup_kind_glyph.md`.

**Precondition:** t1468_1 has landed — `.aitask-scripts/lib/followup_kinds.tsv`
and `lib/followup_kinds.py` exist.

**No dependency on t1468_5.** Every card that must show the glyph has access to
the real `Task` object, so all of them read frontmatter. The trail *snapshot*
field added in t1468_5 serves the trail document, not board rendering.

Read `aidocs/framework/tui_conventions.md` before editing.

## Implementation steps

### 1. Maps and the totality boundary

1.1 Module-level maps in `.aitask-scripts/board/aitask_board.py`, built from
`lib/followup_kinds.py`, placed beside `TRAIL_CLASSIFICATION_GLYPHS` (`:609-618`)
so the two marker vocabularies sit together.

1.2 `normalize_followup_kind(value) -> str | None` — the **totality boundary**.
`lib/task_yaml.py` deliberately leaves values type-honest, so a hand-edited or
foreign field can arrive as `None`, a list, a dict, an int or a bool. Copy
`normalize_group_slug` (`.aitask-scripts/lib/board_groups.py:63-99`), which
exists for exactly this reason. **Never read the raw value inside `compose`.**

An unknown-but-well-formed string returns `None` (no glyph), not a fallback
glyph — an unrecognised kind is not a follow-up we can classify, and inventing a
marker for it would be a lie. Mirror `_trail_badge_text`'s explicit-fallback
discipline (`:2912-2919`) in shape, not in outcome.

### 2. Colour authority — TSV, programmatically

Build the gutter label as:

```python
Label(Text(glyph, style=colour), classes="task-followup-glyph")
```

Textual CSS cannot read the TSV, so a `.fk-<kind>` colour class would be a
second, unsynchronisable source of truth that a key-only drift test cannot catch.
One authority makes drift **impossible** rather than merely detectable. A literal
Rich style also resolves in both `render().spans` and composited strips, whereas
an unresolved CSS colour name resolves in neither — which matters directly for
the verification below.

Add **one** CSS rule for layout only, beside `.task-mark` / `.task-number` at
`:6808-6810`:

```
.task-followup-glyph { width: auto; margin: 0 1 0 0; }
```

No `color:` in that rule. No per-kind classes.

### 3. The five surfaces

All three `TaskCard` subclasses **fully override** `compose` with no `super()`
call, so each needs the glyph added explicitly.

3.1 **`TaskCard.compose`** (`:2625`, title row `:2632-2641`) — yield the gutter
label **after** the ☑/☐ mark and **before** the task number. It must not hang off
the mark: `markable=True` is set only at `KanbanColumn.task_block:3534`, so
`TopicColumn` cards (`:2878-2887`) and child cards have no mark and the glyph
must still appear. Source: `self.task_data.metadata` (already unfiltered at
`:2626`).

3.2 **`InFlightTaskCard.compose`** (`:2786`) — source `self.item.task.metadata`.
`InFlightItem.task` (`:104`) is the real `Task`; no new plumbing.

3.3 **`TrailTaskCard.compose`** (`:2956`) — source `self.task_data.metadata`.
`__init__` passes `view.task` to `super()`, so this is the real `Task`. Read
frontmatter, **not** `self.trail_entry`.

3.4 **`TrailGhostCard`** (`:3006`) — **no glyph, by design.** `_GhostTaskStub`
(`:2894-2910`) has `metadata = {}`; a ghost is a referenced task with no local
file, so there is nothing to classify and nothing to pick. This is a tested
decision, not an omission — see verification.

3.5 **`GroupHeader._label()`** (`:2340-2342`) — a collapsed group mounts **no**
member cards (`KanbanColumn.compose:3500-3517` `continue`s past `task_block`,
dropping members and their `.child-wrapper` rows), so a member glyph is invisible
there. Add a roll-up using `self.members`, which the widget already carries as
data for exactly this purpose:

```
▾ perf work (3) · 1 follow-up
```

Keep the existing `▸`/`▾` collapse glyph and count intact; append the roll-up
only when the count is non-zero.

## Verification

Render-level, on **every** surface — a `TaskCard`-only test suite would pass
while follow-ups stay invisible in In-Flight and By-Trail.

1. `label.render().plain` for the glyph on `TaskCard`, `InFlightTaskCard`,
   `TrailTaskCard`. Harnesses already exist: `tests/test_board_marking.py`
   `MarkGlyphRenderTests:159` (booted board, plain card),
   `tests/test_board_bytrail_view.py:411-431` and
   `tests/test_board_inflight_view.py:225-249` (per-card `CardApp`).
2. **Composited strips** (`_screen_rows`, `tests/test_board_bytrail_view.py:101-112`)
   for **width and colour**. `render().spans` alone cannot see colour resolution,
   and width only shows up in the composited row. Use `_settle` before asserting.
3. `TrailGhostCard` renders cleanly with **no** glyph and does not raise on the
   empty-metadata path.
4. `GroupHeader._label()` roll-up appears when a collapsed group contains
   follow-ups and is absent when it does not (negative control) — assert via
   `.render().plain`, per `tests/test_board_group_focus.py:160,309`.
5. Glyph **uniqueness** across the map and **single-cell width** for every glyph.
6. Drift guard: map keys == `followup_kinds.tsv` (precedent
   `tests/test_board_bytrail_view.py:184`, which pins glyph-map keys against the
   schema enum and asserts value uniqueness).
7. `normalize_followup_kind` totality: `None`, `[]`, `{}`, `0`, `True`, and an
   unknown string all yield no glyph and no exception.
8. `bash tests/run_all_python_tests.sh` — read the **last** line.
9. **Live board** (`ait board`) in a real terminal: a follow-up is identifiable
   at a glance by colour and shape in a kanban column, in By-Topic, in In-Flight,
   in By-Trail, and as a collapsed-group roll-up — **and at a narrow terminal
   width**. Visible is not the same as readable; check the narrow case
   explicitly, and check it against a column of mixed follow-up and non-follow-up
   cards rather than a single card in isolation.

Note the `board_fixture.py` **TASK_DIR invariant** in its docstring: the relative
literal `"aitasks"` with cwd inside the fixture tree is required, or
`is_modified` silently returns `[]` and assertions pass vacuously.

## Notes for sibling tasks

- The glyph vocabulary is now width-verified. t1468_5's schema enum must match
  `followup_kinds.tsv` exactly — the drift guard here and the one there read the
  same file.
- `GroupHeader` roll-up wording is user-visible; t1468_4's `ait ls` display
  should use consistent terminology.
