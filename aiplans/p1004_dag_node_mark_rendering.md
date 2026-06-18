---
Task: t1004_dag_node_mark_rendering.md
Worktree: (current branch — profile 'fast')
Branch: (current branch — profile 'fast')
Base branch: main
---

# Plan: Render space-marked state on Browse graph-view DAG nodes (t1004)

## Context

t983_3 introduced `space`-marking of Browse nodes. The marked set lives in
`NodeSelection.marked` (`brainstorm_app.py:2231`). That task wired marking into
the model and reflected it on the **list view** only — the `NodeRow` glyph
(`NodeRow.render`, `brainstorm_app.py:2544` → `"● "` when `marked`). The
**graph view** (`DAGDisplay`, `brainstorm_dag_display.py`) was left without a
per-node mark glyph; t983_3 deferred it as a best-effort follow-up and recorded
the risk (`dag_node_mark_rendering`, code-health low). A textual
`#browse_marked_info` summary (t983_4) shows the marked *names* in both views,
but the graph's node boxes themselves don't show which are marked, so the two
views are visually inconsistent on a marked node's box.

Goal: render the marked glyph on `DAGDisplay` node boxes so the graph and list
views agree, driven by the same `NodeSelection.marked`, kept in sync through the
existing `_refresh_node_marks` sync point.

**Glyph decision (user):** use a **checkbox** — `☑` (U+2611, bold yellow) when
marked, `☐` (U+2610, dim) when not — shown **always** (every node renders a box,
checked or empty). Applied to **both** views so they stay consistent: this
replaces the list view's current `●`/blank treatment with the same checkbox, and
adds the checkbox to the graph boxes.

## Design

The DAG already threads orthogonal per-node state (`is_head`, `is_focused`,
`is_anchor`) from `_render_dag` → `_render_layer` → `_render_node_box`. Marked
state is another orthogonal per-node flag, so it follows the same path. The
marked set is owned by the app's `NodeSelection`; the `DAGDisplay` widget caches
a copy pushed in via a `set_marked()` method (mirrors how `compare_anchor_id`
is held as widget instance state and re-rendered).

### 1. `brainstorm_dag_display.py` — rendering

- **Add a module-level glyph + style constants** near the other styles (after
  `EDGE_STYLE`, ~line 56):
  ```python
  MARK_CHECKED = "☑"    # ☑ — marked
  MARK_UNCHECKED = "☐"  # ☐ — unmarked
  MARK_CHECKED_STYLE = Style(color="yellow", bold=True)  # matches list-view ☑ (t1004)
  MARK_UNCHECKED_STYLE = Style(color="#6272A4")          # dim Dracula (empty box)
  ```
  These are imported by the new test for the cross-view glyph assertions.

- **`_render_node_box(...)`** (line 215): add a keyword param
  `is_marked: bool = False`. In the title row (Row 1, ~lines 256–267), prepend a
  2-char checkbox indicator to the `inner` Text **before** the node_id — always
  present (checked or empty) — so the box width is preserved by the existing
  `pad = inner_w - len(inner.plain)` logic:
  ```python
  inner = Text()
  glyph = MARK_CHECKED if is_marked else MARK_UNCHECKED
  gstyle = MARK_CHECKED_STYLE if is_marked else MARK_UNCHECKED_STYLE
  inner.append(glyph + " ", style=gstyle + bg)
  inner.append(node_id, style=NODE_ID_STYLE + bg)
  if is_head:
      inner.append(" HEAD", style=HEAD_TAG_STYLE + bg)
  ```
  (The default `is_marked=False` renders `☐`. The glyph always consumes 2 chars
  of `inner_w`; the trailing pad shrinks accordingly, so each row stays
  `BOX_WIDTH` wide — the invariant asserted by `test_each_row_is_box_width`.
  `☑`/`☐` are BMP text-width-1 glyphs like the existing `●`.)

- **`_render_layer(...)`** (line 299): add param `marked_ids: set[str] | None = None`,
  normalize `marks = marked_ids or set()`, and pass
  `is_marked=(nid in marks)` into the `_render_node_box` call.

- **`_render_dag()`** (line 572): pass `marked_ids=self._marked` to `_render_layer`.

- **`DAGDisplay.__init__`** (line 514): add `self._marked: set[str] = set()`.

- **Add `set_marked(self, marked) -> None`** on `DAGDisplay`:
  ```python
  def set_marked(self, marked) -> None:
      """Cache the Browse marked set and repaint node glyphs (t1004).

      The app's NodeSelection.marked is the source of truth; this widget holds
      a copy pushed via _refresh_node_marks so the graph view mirrors the
      list-view ● glyph."""
      self._marked = set(marked)
      if self._layers:
          self._render_dag()
  ```
  Storing a copy (`set(marked)`) avoids aliasing the live selection set. The
  `self._layers` guard skips the repaint when no DAG is loaded yet. Because
  `_marked` is instance state untouched by `load_dag`, marks survive a DAG
  rebuild (e.g. the HEAD-change reload at `brainstorm_app.py:7992`)
  automatically — `_render_dag` reads the cached set.

### 2. `brainstorm_app.py` — list-view glyph (both-views consistency)

- **`NodeRow.render()`** (line 2544): replace the `●`/blank mark with the same
  checkbox so the list matches the graph:
  ```python
  mark = "[bold yellow]☑[/] " if self.marked else "[#6272A4]☐[/] "
  ```
  (Was `"[bold yellow]●[/] " if self.marked else "  "`.) Unmarked rows now show a
  dim empty `☐` instead of blank — matching the graph's always-on checkbox.
  Update the adjacent t983_3 comment (lines 2526–2528) to say "checkbox glyph".

### 3. `brainstorm_app.py` — sync point

- **`_refresh_node_marks()`** (line 6078): after the NodeRow loop and the
  `_refresh_marked_summary()` call, push the set to the DAG:
  ```python
  try:
      self.query_one(DAGDisplay).set_marked(self._selection.marked)
  except Exception:
      pass
  ```
  This is the documented single sync point — `action_browse_mark` already calls
  it after every `toggle` (line 6150). The `try/except` mirrors the defensive
  guard already used by `_refresh_marked_summary` (the DAG is always composed in
  the Browse tab, but the guard keeps the method safe in any future caller).
  Update the method docstring (lines 6079–6084), which currently says the DAG
  glyph is a deferred follow-up, to note the DAG is now repainted here.

- **`_load_existing_session()`** (line 6630): after
  `self.query_one(DAGDisplay).load_dag(self.session_path)` (line 6640), add
  `self.query_one(DAGDisplay).set_marked(self._selection.marked)` so a reload
  triggered by node deletion (`action_delete_node` → `_selection.remove(...)`
  → `_load_existing_session`, lines 6446–6463) re-syncs the cached set and drops
  ids for nodes that no longer exist. (Harmless even without it — a stale id
  matches no rendered node — but this keeps the cache honest.)

## Why this shape (rejected alternatives)

- **Border-color marking** (like HEAD/anchor): rejected — marked is orthogonal
  to head/focus/anchor (a node can be all at once), and a 4th border color
  doesn't compose. A glyph inside the box composes cleanly and matches the list.
- **Passing marks through `load_dag`'s signature**: rejected — `load_dag` is
  about session data, not transient selection; threading selection through it
  couples two concerns. A dedicated `set_marked()` push mirrors the existing
  `_compare_anchor_id` widget-state pattern and keeps the source of truth in the
  app's `NodeSelection`.

## Tests

New file `tests/test_brainstorm_dag_node_mark.py` (pure-function unit tests,
mirroring the style of `tests/test_brainstorm_dag_op_badge.py`; imports
`MARK_CHECKED`/`MARK_UNCHECKED`/`MARK_CHECKED_STYLE` from the module):

- `is_marked=True` → title row (`rows[1].plain`) contains `☑` and not `☐`.
- `is_marked=False` (default) → title row contains `☐` and not `☑`.
- Width invariant: every row stays `BOX_WIDTH` for both `is_marked=True` and
  `is_marked=False`, for both a head and non-head node (guards alignment).
- The `☑` span carries a bold-yellow style (assert a span with `bold` and a
  yellow color exists in `rows[1]`, mirroring `dag_op_badge`'s style-span
  assertions).
- `_render_layer(..., marked_ids={nid})` checks only the listed node (`☑`),
  others `☐`.

The existing `test_brainstorm_browse_view.py` covers the list-view marked state
behaviorally (`rows[0].marked` toggling); the `●`→`☑` swap is a render-string
change those tests don't assert on, so they stay green. The existing brainstorm
suite must stay green. Run the impacted tests:
```bash
bash tests/test_brainstorm_dag_node_mark.py   # new
bash tests/test_brainstorm_dag_op_badge.py    # _render_node_box callers
bash tests/test_brainstorm_dag.py
bash tests/test_brainstorm_browse_view.py      # _refresh_node_marks / marks
bash tests/test_brainstorm_node_delete.py      # reload path
```

## Verification

- Run the unit tests above (all PASS).
- Manual (graph view): launch `ait brainstorm <task>` with a multi-node session,
  press `g` for graph view — every node box shows a dim `☐`. Navigate with
  arrows, press `space` on a node — its box title flips to a yellow `☑`; press
  `space` again — back to `☐`. Toggle to list view (`v`/`d`) and confirm the
  same nodes show `☑`/`☐` consistently (no alignment drift). Change HEAD (`h`)
  to force a DAG reload and confirm marks persist.

## Risk

### Code-health risk: low
- Additive change following the established `is_head`/`is_focused`/`is_anchor`
  threading pattern; new param defaults to `False` so no existing caller breaks.
  The only width-sensitive edit preserves `BOX_WIDTH` via existing padding and is
  pinned by a new width test. · severity: low · → mitigation: None (covered by tests)

### Goal-achievement risk: low
- Goal is a single, well-understood glyph parity between two views; the sync
  point (`_refresh_node_marks`) and source of truth (`NodeSelection.marked`)
  already exist and are exercised by the list view. · severity: low · →
  mitigation: None identified.

## Post-Implementation

Steps 8–9 of task-workflow: user review of the diff, commit
(`enhancement: ... (t1004)`), then archival on the current branch (no worktree
under profile 'fast').
