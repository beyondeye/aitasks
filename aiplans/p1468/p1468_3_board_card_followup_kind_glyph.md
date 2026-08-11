---
Task: t1468_3_board_card_followup_kind_glyph.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_1_*.md, aitasks/t1468/t1468_2_*.md, aitasks/t1468/t1468_4_*.md, aitasks/t1468/t1468_5_*.md, aitasks/t1468/t1468_6_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-11 15:00
---

# p1468_3 — Board card `followup_kind` glyph (shape + colour)

Context and the per-surface decision table are in
`aitasks/t1468/t1468_3_board_card_followup_kind_glyph.md`.

Read `aidocs/framework/tui_conventions.md` before editing.

## Re-verification corrections (2026-08-11)

This plan was re-verified against current source. Five things in the previous
draft were wrong; the steps below already incorporate the corrections.

1. **The vocabulary is not a `.tsv`.** t1468_1 rejected that design and shipped
   `.aitask-scripts/lib/followup_kinds.py` (source of truth) +
   `lib/followup_kinds_sh.sh` (shell bridge), modelled on the `launch_modes`
   seam. Every `followup_kinds.tsv` reference is dead.
2. **`normalize_followup_kind` already exists** in that module — do **not**
   re-implement it in the board. The totality boundary is imported, not copied.
3. **No new glyph/colour map belongs in the board.** `FOLLOWUP_KINDS` is the one
   authority; the board imports it. This removes the need for a two-map drift
   guard entirely (see Verification).
4. **`TrailTaskCard` / `TrailGhostCard` have no `task-title-row` `Horizontal`**
   (`:3277-3299`, `:3327-3343`) — they yield a bare `Label(Text(...),
   classes="task-title")`. The "gutter `Label` in the title row" placement does
   not apply there; the glyph is prepended into the existing Rich `Text`.
5. **Every line number in the previous draft was stale** (t1243_10 landed ~+300
   lines). All references below are re-verified against current `HEAD`.

Two behaviours were **decided by the user** during re-verification and are no
longer open:

- **Unknown kind ⇒ `·`, uncoloured.** Absent/empty still renders nothing.
- **Collapsed-group roll-up shows per-kind glyphs + counts**, coloured
  (`▸ perf work (3) · ▲2 ◈1`), not a plain `1 follow-up` count.

---

## Implementation steps

### 1. Import the vocabulary; add the one board-level boundary

`.aitask-scripts/board/aitask_board.py` already does a flat
`sys.path.insert(..., "lib")` at `:15` and imports lib modules by bare name
(`:19-61`). Add beside `from board_groups import (...)` (`:58-61`):

```python
from followup_kinds import FOLLOWUP_KINDS, UNKNOWN_GLYPH, normalize_followup_kind
```

**Do not** copy the map or the normaliser into the board.

**The one thing the module does not give us.** `followup_kinds.glyph_for()` /
`colour_for()` collapse *absent* and *unknown* into the same answer — both
return `("·", None)` — because they were written for validation, not rendering.
On the board those two cases must diverge: the overwhelming majority of tasks
have no `followup_kind` and must render **nothing at all**, while a hand-edited
typo must render `·`. So add one module-level helper beside
`_trail_badge_text` (`:3233`), where the file's other render-boundary helpers
live:

```python
def _followup_marker(metadata):
    """`(glyph, colour)` for a task's `followup_kind`, or `None` for not-a-follow-up.

    The board's totality boundary. `lib/task_yaml.py` leaves frontmatter values
    type-honest, so a hand-edited or foreign field arrives as `None`, a list, a
    dict, an int or a bool — `normalize_followup_kind` (imported, not copied)
    coerces all of those to `""`.

    Deliberately NOT `followup_kinds.glyph_for()`: that helper answers `·` for
    an ABSENT kind too, which would paint a marker on every ordinary task. Here
    absent -> `None` (no widget), unknown-but-present -> the `·` fallback with
    NO colour, because an unrecognised kind has no severity family to signal.
    """
    kind = normalize_followup_kind((metadata or {}).get("followup_kind"))
    if not kind:
        return None
    entry = FOLLOWUP_KINDS.get(kind)
    return (entry[0], entry[1]) if entry else (UNKNOWN_GLYPH, None)
```

Returning a tuple-or-`None` rather than a bare glyph string is what lets every
call site below be a single `if marker:` — and keeps "no marker" structurally
distinct from "a marker that happens to be `·`".

### 2. One CSS rule — layout only, no colour

Colour comes from `FOLLOWUP_KINDS` via a literal Rich style
(`Label(Text(glyph, style=colour))`). Textual CSS cannot read that dict, so a
`.fk-<kind>` colour class would be a second, unsynchronisable authority. One
authority makes drift **impossible** rather than merely detectable — and a
literal Rich style resolves in both `render().spans` and composited strips,
whereas an unresolved CSS colour name resolves in neither, which the colour
verification below depends on.

Add beside `.task-mark` / `.task-number` in `KanbanApp.CSS` (`:7134-7139`):

```
.task-followup-glyph { width: auto; margin: 0 1 0 0; }
```

No `color:`. No per-kind classes.

### 3. The five surfaces

All three `TaskCard` subclasses **fully override** `compose` with no `super()`
call, so each needs the glyph added explicitly; none inherits it.

**3.1 `TaskCard.compose`** (`:2946`, title row `:2955-2964`). Yield the gutter
label **after** the ☑/☐ mark and **before** the task number:

```python
with Horizontal(classes="task-title-row"):
    if self.markable:
        ...                                   # existing mark label
    marker = _followup_marker(meta)
    if marker:
        glyph, colour = marker
        yield Label(Text(glyph, style=colour) if colour else Text(glyph),
                    classes="task-followup-glyph")
    if task_num:
        ...                                   # existing number label
```

It must **not** hang off the mark: `markable=True` is set only at
`KanbanColumn.task_block:3861`, so `TopicColumn` cards (`:3205-3207`) and child
cards (`:3869`) have no mark and must still show the glyph. `meta` is already
bound at `:2947` and is unfiltered.

**3.2 `InFlightTaskCard.compose`** (`:3107`, title row `:3108-3110`). Same
insertion, before the `task-number` label. Source is **`self.task_data.metadata`**,
not `self.item.task.metadata`: `__init__` passes `item.task` to `super()`
(`:3104`), so `self.task_data` *is* the real `Task` and every surface reads the
same attribute.

**3.3 `TrailTaskCard.compose`** (`:3277`). There is **no** title-row
`Horizontal` here — `:3279-3285` builds a Rich `Text` and yields one
`Label(title, classes="task-title")`. Prepend into that `Text`, mirroring the
existing `✔ ` prepend at `:3281`:

```python
title = Text()
marker = _followup_marker(self.task_data.metadata)
if marker:
    glyph, colour = marker
    title.append(glyph, style=colour) if colour else title.append(glyph)
    title.append(" ")
if self.trail_view.landed:
    ...
```

Order matters: the follow-up glyph goes **before** the `✔ `, so the leading
column of a By-Trail card is the provenance marker on every card, landed or not.
Read **frontmatter, not `self.trail_entry`** — this is what removes any
dependency of this child on t1468_5, whose trail-snapshot field serves the trail
*document*, not board rendering.

**3.4 `TrailGhostCard`** (`:3327`) — **no glyph, by design.** `_GhostTaskStub`
(`:3216-3230`) has `metadata = {}`; a ghost is a referenced task with no local
file, so there is nothing to classify and nothing to pick. `_followup_marker({})`
returns `None`, so the correct behaviour falls out of the boundary rather than
needing a special case — but it is a **tested decision, not an omission**.

**3.5 `GroupHeader._label()`** (`:2641-2647`) — collapsed-group roll-up. A
collapsed group mounts **no** member cards (`KanbanColumn.compose:3839-3842`
`continue`s past `task_block`, dropping members *and* their `.child-wrapper`
rows), so a member glyph is invisible there. `self.members` is task **data**
carried for exactly this purpose (`:2618-2621`; t1243_10 reads the same list for
its `· N match` badge).

`_label()` currently returns a `str`. Change it to return a Rich `Text`:

```python
def _label(self) -> Text:
    glyph = "▸" if self.collapsed else "▾"
    label = Text(f"{glyph} {group_display_title(self.slug)} ({len(self.members)})")
    if self.match_count is not None:
        label.append(f" · {self.match_count} match")
    rollup = self._followup_rollup()
    if rollup:
        label.append(" · ")
        label.append_text(rollup)
    return label
```

with a sibling helper building the coloured roll-up in canonical
`FOLLOWUP_KINDS` declaration order (deterministic; unknown kinds tallied under
`·` and placed last), returning an empty `Text` when the group holds no
follow-ups. Members are `Task` objects, so read `m.metadata` directly.

Three properties this preserves, each already pinned by an existing test:

- the badge stays **inside** `_label()`, so `set_collapsed`'s in-place repaint
  (`:2649-2663`) cannot erase it — the trap `test_set_collapsed_repaint_preserves_the_badge`
  (`tests/test_board_group_filtering.py:779`) exists for;
- ordering is `glyph · title (count) · N match · <rollup>`, so the existing exact
  string assertions at `test_board_group_filtering.py:765-796` and
  `test_board_group_focus.py:317-319,610` keep passing unchanged;
- `Static.update()` accepts a `RenderableType` and `.render().plain` is what
  every existing assertion reads (precedent: `TrailTaskCard` already yields
  `Label(Text(...))` and `test_board_bytrail_view.py:449` reads `.plain` off it),
  so the return-type change is source-compatible with all of them.

Returning `Text` additionally **removes a latent markup-injection path**: `_label()`
currently interpolates the user-authored `group_display_title(self.slug)` into a
string that `Static` renders with markup enabled, so a hand-edited
`boardgroup: "a[/]b"` is parsed as Rich markup today. A `Text` is never
markup-parsed. Note this in the docstring — it is a deliberate side benefit, not
an accident.

**Required fixture update.** `GroupHeaderLabelTests._Member`
(`tests/test_board_group_filtering.py:753-754`) is a bare `class _Member: pass`
with no `metadata`. Once `_label()` reads `m.metadata` those five tests raise
`AttributeError`. Give the stub `metadata: dict = {}` — it stands in for a
`Task`, so this is retargeting a fixture, not weakening a guard. Do **not** add a
`getattr(m, "metadata", {})` fallback in production: that would mask a real
`Task` arriving without metadata.

---

## Post-phase (risk mitigations)

Runs after the implementation steps above, before the plan is consolidated.

**[colour_assertion_negative_control]** The colour assertions in Verification 2
are the only thing standing between "the glyph paints" and the acceptance
criterion "identifiable by colour **and** shape". There is **no board-suite
precedent** for reading colour off a composited strip, so a wrong extraction can
pass vacuously. Prove it can fail: change exactly one entry's colour in
`FOLLOWUP_KINDS` (e.g. `risk_mitigation` `yellow` → `green`), re-run the colour
test, and confirm it goes **RED**; record the failing test id and the exact
assertion message in Final Implementation Notes; restore the module
**byte-identical** and confirm GREEN. One mutation, one named failing test — a
control that stays green is itself the defect.

**[narrow_width_composited_probe]** The gutter adds 2 cells (glyph + margin) to
a title row whose `.task-title` is `width: 1fr` inside a column with
`min_width: 30` (`KanbanColumn.on_mount:3877`), and `TrailTaskCard` prepends
into the title `Text` rather than into a fixed-width gutter — so it clips on a
different rule from the other surfaces. Assert on **composited strips** at the
minimum width that the glyph is still painted on a kanban card and a By-Trail
card, with a mixed column of follow-up and non-follow-up cards. Precedent:
`MarkNarrowWidthTests` (`tests/test_board_marking.py:538-551`) exists because
`Label.render().plain` stays fully populated even when the parent clips it to
nothing — a label-level assertion cannot see this.

---

## Verification

Render-level, on **every** surface — a `TaskCard`-only suite would pass while
follow-ups stay invisible in In-Flight and By-Trail.

1. **Glyph text per surface.** `label.render().plain` for `TaskCard`,
   `InFlightTaskCard`, `TrailTaskCard`. Harnesses to lift verbatim:
   - `tests/test_board_marking.py:159` `MarkGlyphRenderTests` — booted board
     (`app.run_test(size=(160,48))`), `_mark_label`-style
     `card.query(".task-followup-glyph")`, re-query after any state change;
   - `tests/test_board_bytrail_view.py:411-429` `_render_card` — per-card
     `CardApp`, returns `label.render()` so `.spans` stays reachable;
   - `tests/test_board_inflight_view.py:220-249` — same shape; note an
     `InFlightItem` is never constructed directly, it comes from
     `mgr.get_inflight_items()[0]` over a `_task(...)` written with
     `_body(status, extra_fm=...)`, which is where `followup_kind:` is injected.
2. **Colour on the composited screen.** No board precedent exists; lift the
   segment walk from `tests/test_monitor_session_divider.py:475-486` — iterate
   `strip` for Rich `Segment`s, guard `seg.style is None or seg.style.color is
   None`. Assert on the colour **name** (`seg.style.color.name == "yellow"`),
   not a hex: Rich's standalone `cyan` is `#008080` while Textual's palette
   resolves it to `#00ffff`, and the name is what `FOLLOWUP_KINDS` actually
   pins. Use `_settle` (`tests/test_board_bytrail_view.py:134-144`) before
   asserting.
3. **Every kind renders.** Parametrise over `FOLLOWUP_KINDS` — one card per
   kind, each asserting its own glyph and colour. This is the drift guard that
   *matters* now that there is only one map: it fails the moment a kind is added
   to the module without the board painting it. (The previous draft's
   "map keys == tsv" guard is vacuous by construction — the board no longer owns
   a second map.)
4. **`GroupHeader` roll-up.** App-free via `GroupHeaderLabelTests`
   (`tests/test_board_group_filtering.py:748`), asserting `.render().plain`:
   present with mixed kinds, ordered canonically, **absent** when the group holds
   no follow-ups (negative control), and surviving a `set_collapsed` flip and a
   `set_match_count` set/clear. Plus one booted-board case via
   `test_board_group_focus.py:159-161`'s `_header()` on a genuinely collapsed
   group.
5. **`TrailGhostCard`** renders cleanly with **no** glyph and does not raise on
   the empty-metadata path.
6. **Boundary totality.** `_followup_marker` over `None`, `{}`, a missing key,
   `[]`, `{}`, `0`, `True`, `""`, `"   "` → all `None`; an unknown non-empty
   string → `("·", None)`; each of the 8 valid kinds → its own `(glyph, colour)`.
7. **Vocabulary properties**, asserted against `FOLLOWUP_KINDS` itself: all 8
   glyphs distinct, and `rich.cells.cell_len(glyph) == 1` for each (plus
   `UNKNOWN_GLYPH`). Verified empirically during re-planning — all 8 are width 1.
8. Both post-phase mitigations above.
9. `bash tests/run_all_python_tests.sh` — read the **LAST** line for the verdict
   (`set -o pipefail` if piping; an earlier `Results: N passed` line belongs to
   one module, not the suite).
10. **Live board** (`ait board`) in a real terminal: a follow-up is identifiable
    at a glance by colour and shape in a kanban column, in By-Topic, in
    In-Flight, in By-Trail, and as a collapsed-group roll-up — **and at a narrow
    terminal width**, against a column of mixed follow-up and non-follow-up
    cards rather than a single card in isolation.

**Fixture invariant.** `tests/lib/board_fixture.py` requires `TASK_DIR` to be the
relative literal `"aitasks"` with cwd inside the fixture tree, or `is_modified`
silently returns `[]` and assertions pass vacuously (`load_board_module` rejects
an absolute value). Seed `followup_kind` through `FixtureTask(..., extra={...})`
— `extra` is `dict.update`d over the base frontmatter, so arbitrary keys work
(only `boardcol` / `boardidx` are written after it and cannot be overridden).

---

## Risk

### Code-health risk: low

- `GroupHeader._label()` changes its return type from `str` to `Text`, which
  also silently stops Rich-markup interpretation of the group title; three
  `Static.update()` call sites (`__init__`, `set_collapsed`, `set_match_count`)
  and one app-free test class read it · severity: low · → mitigation: none
  (covered by Verification 4, which exercises all three repaint paths through
  `.render().plain`, and by the pre-existing exact-string assertions that must
  pass unchanged)
- Five render seams in one file must each be edited separately because the three
  `TaskCard` subclasses fully override `compose` with no `super()` call — a
  missed seam is invisible in the other four · severity: low · → mitigation:
  none (covered by Verification 1 and 3, which assert per surface and per kind)

### Goal-achievement risk: medium

- The acceptance criterion is at-a-glance identification by colour **and** shape,
  but no board test has ever read colour off a composited strip; a mis-written
  extraction passes vacuously while the glyph paints uncoloured · severity:
  medium (residual — addressed by inline post-phase
  `colour_assertion_negative_control`) · → mitigation: inline post-phase
  colour_assertion_negative_control
- The gutter adds 2 cells to a title row already at `width: 1fr` inside a
  30-cell minimum column, and `TrailTaskCard` prepends into the title `Text`
  rather than a fixed gutter, so it clips on a different rule — visible is not
  the same as readable · severity: medium (residual — addressed by inline
  post-phase `narrow_width_composited_probe`) · → mitigation: inline post-phase
  narrow_width_composited_probe

### Planned mitigations
- timing: post-phase | name: colour_assertion_negative_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: a vacuous colour assertion that cannot see an uncoloured glyph | desc: mutate one FOLLOWUP_KINDS colour, confirm the colour test goes RED with a named failing assertion, restore byte-identical and confirm GREEN
- timing: post-phase | name: narrow_width_composited_probe | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: the glyph being present in render().plain but clipped off the composited screen at minimum column width | desc: assert on composited strips at the board's minimum column width that the glyph still paints on a kanban card and a By-Trail card in a mixed column

---

## Notes for sibling tasks

- **The vocabulary is `lib/followup_kinds.py`, never a `.tsv`.** t1468_5's schema
  enum must match `FOLLOWUP_KINDS`'s keys; import them rather than restating them.
- **`glyph_for()` / `colour_for()` are validation helpers, not render helpers** —
  they answer `·` / `None` for an *absent* kind as well as an unknown one. Any
  surface that must distinguish "not a follow-up" from "unrecognised follow-up"
  (t1468_4's `ait ls` / pick output does) needs its own boundary, as
  `_followup_marker` is here. Consider promoting a shared
  `marker_for(kind) -> (glyph, colour) | None` into `lib/followup_kinds.py` if
  t1468_4 needs the same split.
- **`▲` is ambiguous on a By-Trail card.** It is `risk_mitigation` in
  `FOLLOWUP_KINDS` and `preferred_predecessor` in `TRAIL_CLASSIFICATION_GLYPHS`
  (`board/aitask_board.py:622-628`), and both render on the same card — the
  follow-up glyph in the title line, the classification in the `.trail-badges`
  line. Accepted here rather than renegotiating a vocabulary t1468_1 already
  landed and t1468_4/5/6 build on; the two never share a line.
- **Roll-up wording is user-visible.** t1468_4's `ait ls` display should use the
  same glyphs and the same `FOLLOWUP_KINDS` ordering.
- Clearing `followup_kind` is **key removal with no tombstone** — treat *absent*
  as "not a follow-up" and never assert `== None`.
