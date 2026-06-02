---
Task: t904_task_detail_dialog_enhancements.md
Worktree: (current branch — fast profile, no worktree)
Branch: main
Base branch: main
---

# Plan: Task Detail Dialog Enhancements (t904)

## Goal

In `ait board`, the `TaskDetailScreen` modal has accumulated many metadata
fields (risk×2, cross-repo/verifies, folded, contributor, implemented_with,
file references, lock status, …). The metadata block (`height: auto`) grows
with content and squeezes the `#md_view` markdown viewer (`1fr`), which fills
only the leftover space. Two confirmed improvements:

1. **Bigger dialog** — grow `#detail_dialog` from `height: 80%` to `96%`
   (near full vertical, small margin). Textual `%` is relative to the screen,
   so it auto-adapts to terminal size; no manual screen-size query needed.
2. **Collapsible metadata groups** — wrap the secondary metadata fields in
   Textual `Collapsible` sections, **collapsed by default**, so the user can
   reclaim vertical space for the markdown viewer. The editable **core**
   (priority / risk×2 / effort / status / type) stays always-visible (open).

Confirmed design decisions (via AskUserQuestion):
- Implement **both** improvements.
- Dialog height **~96%** (width stays 80%).
- **Core open, secondary sections collapsed** on open.

## Background / current structure

- `TaskDetailScreen` lives in `.aitask-scripts/board/aitask_board.py`
  (class at line ~2349; `compose()` at ~2416).
- The editable core is the `#meta_editable` Container (lines ~2427-2462):
  `CycleField`s (or `ReadOnlyField`s when Done/Folded/read-only). Its
  `Changed` events drive the Save button (`on_cycle_changed` /
  `_update_save_button` / `save_changes`). **This block is left untouched.**
- After `#meta_editable`, a flat run of conditional `yield`s emits the
  remaining fields (lines ~2464-2564): labels, depends, verifies, assigned_to,
  issue, pull_request, contributor, implemented_with, dates, parent, children,
  folded_tasks, folded_into, file_references, and lock status.
- `#md_view` is a `VerticalScroll` → inherits `height: 1fr` from
  `ScrollableContainer`, so it fills the space remaining after the docked title
  (`#detail_title`, dock top), docked buttons (`#detail_buttons_area`, dock
  bottom), the auto-height metadata, and `#view_indicator`. **Collapsing
  metadata frees space `#md_view` reclaims automatically** — no extra height
  rule needed on `#md_view`.
- Textual **8.2.7** is installed; `textual.widgets.Collapsible` is available
  (context-manager compose, `collapsed=` arg, Enter-to-toggle on focused
  `CollapsibleTitle`, hidden content is non-focusable when collapsed).

### Why this is safe re: keyboard nav (verified)

- `KanbanApp` binds `enter` → `view_details` **without** `priority=True`
  (line ~3612), so a focused `CollapsibleTitle`'s own `enter` binding wins —
  no conflict; Enter toggles the section.
- In a pushed modal, `check_action` keeps `nav_up`/`nav_down` active and
  `action_nav_up/down` move focus via `focus_previous()`/`focus_next()`.
  `CollapsibleTitle` is `can_focus=True`, so it joins the existing
  up/down/Tab focus chain; collapsed content (`display: none`) is skipped.
- No new screen-level `Binding` is added, so the `board.detail` shortcut
  manifest and skill goldens are unaffected (this is a pure Python TUI change;
  no `.md.j2`/closure edits).

## Field grouping

Three collapsed sections (each emitted **only if non-empty**):

1. **`#sec_relations` — "Dependencies & hierarchy (N)"**: depends, verifies,
   parent (child tasks), children, folded_tasks, folded_into.
2. **`#sec_tracking` — "Tracking & provenance (N)"**: labels, assigned_to,
   issue, pull_request, contributor, implemented_with, created/updated dates.
3. **`#sec_lockfiles` — "Lock & files"**: file_references (always shown when a
   manager exists) + lock status (always shown) → this group is always present.

The `(N)` count in titles 1-2 tells the user how many fields are hidden without
expanding.

## Implementation

### File: `.aitask-scripts/board/aitask_board.py`

#### Step 1 — Import `Collapsible`

Edit the widgets import (line 39) to add `Collapsible`:

```python
from textual.widgets import Header, Footer, Static, Label, Markdown, Input, Button, LoadingIndicator, SelectionList, DataTable, Collapsible
```

#### Step 2 — Extract field-building helpers on `TaskDetailScreen`

Add three helper methods that return **lists of widgets** (so the empty-check is
a trivial `if widgets:`). They reuse the *exact* existing conditionals — only
moved, never altered. Insert them right before `compose()` (after
`_resolve_plan_path`, ~line 2415).

```python
    def _build_relations_fields(self, meta):
        """Dependencies & hierarchy metadata widgets (in display order)."""
        out = []
        if meta.get("depends"):
            deps = meta["depends"]
            if deps and self.manager:
                out.append(DependsField(deps, self.manager, self.task_data, classes="meta-ro"))
            elif deps:
                dep_str = ", ".join(str(d) for d in deps)
                out.append(ReadOnlyField(f"[b]Depends:[/b] {dep_str}", classes="meta-ro"))
        if meta.get("verifies"):
            verifies = meta["verifies"]
            if verifies and self.manager:
                out.append(VerifiesField(verifies, self.manager, self.task_data, classes="meta-ro"))
            elif verifies:
                v_str = ", ".join(str(v) for v in verifies)
                out.append(ReadOnlyField(f"[b]Verifies:[/b] {v_str}", classes="meta-ro"))
        # Parent field for child tasks
        if self.task_data.filepath.parent != TASKS_DIR and self.manager:
            parent_num = self.manager.get_parent_num_for_child(self.task_data)
            if parent_num:
                out.append(ParentField(parent_num, self.manager, classes="meta-ro"))
        # Children field for parent tasks
        if meta.get("children_to_implement"):
            children_ids = meta["children_to_implement"]
            if children_ids and self.manager:
                out.append(ChildrenField(children_ids, self.manager, self.task_data, classes="meta-ro"))
            elif children_ids:
                children = ", ".join(str(c) for c in children_ids)
                out.append(ReadOnlyField(f"[b]Children:[/b] {children}", classes="meta-ro"))
        # Folded tasks field
        if meta.get("folded_tasks"):
            folded_ids = meta["folded_tasks"]
            if folded_ids and self.manager:
                out.append(FoldedTasksField(folded_ids, self.manager, self.task_data, classes="meta-ro"))
            elif folded_ids:
                folded_str = ", ".join(str(f) for f in folded_ids)
                out.append(ReadOnlyField(f"[b]Folded Tasks:[/b] {folded_str}", classes="meta-ro"))
        # Folded into field
        if meta.get("folded_into"):
            folded_into_num = str(meta["folded_into"])
            if self.manager:
                out.append(FoldedIntoField(folded_into_num, self.manager, classes="meta-ro"))
            else:
                out.append(ReadOnlyField(f"[b]Folded Into:[/b] t{folded_into_num}", classes="meta-ro"))
        return out

    def _build_tracking_fields(self, meta):
        """Tracking & provenance metadata widgets (in display order)."""
        out = []
        if meta.get("labels"):
            out.append(ReadOnlyField(f"[b]Labels:[/b] {', '.join(meta['labels'])}", classes="meta-ro"))
        if meta.get("assigned_to"):
            out.append(ReadOnlyField(f"[b]Assigned to:[/b] {meta['assigned_to']}", classes="meta-ro"))
        if meta.get("issue"):
            out.append(IssueField(meta["issue"], classes="meta-ro"))
        if meta.get("pull_request"):
            out.append(PullRequestField(meta["pull_request"], classes="meta-ro"))
        if meta.get("contributor"):
            contributor_text = meta["contributor"]
            if meta.get("contributor_email"):
                contributor_text += f" ({meta['contributor_email']})"
            out.append(ReadOnlyField(f"  [b]Contributor:[/b] @{contributor_text}", classes="meta-ro"))
        if meta.get("implemented_with"):
            out.append(ReadOnlyField(f"[b]Implemented with:[/b] {meta['implemented_with']}", classes="meta-ro"))
        dates = []
        if meta.get("created_at"):
            dates.append(f"[b]Created:[/b] {meta['created_at']}")
        if meta.get("updated_at"):
            dates.append(f"[b]Updated:[/b] {meta['updated_at']}")
        if dates:
            out.append(ReadOnlyField("  |  ".join(dates), classes="meta-ro"))
        return out

    def _build_lockfiles_fields(self, meta):
        """File references + lock status widgets. Also sets self._lock_info."""
        out = []
        # File references field (read-only, navigate via enter)
        if self.manager:
            file_refs = meta.get("file_references") or []
            out.append(FileReferencesField(file_refs, self.manager, self.task_data, classes="meta-ro"))
        # Lock status (side effect: compute self._lock_info, consumed by compose for buttons)
        if self.manager:
            task_num, _ = TaskCard._parse_filename(self.task_data.filename)
            lock_id = task_num.lstrip("t")
            self._lock_info = self.manager.lock_map.get(lock_id)
        if self._lock_info:
            locked_by = self._lock_info["locked_by"]
            locked_at = self._lock_info["locked_at"]
            hostname = self._lock_info.get("hostname", "")
            stale_marker = ""
            try:
                lock_time = datetime.strptime(locked_at, "%Y-%m-%d %H:%M")
                hours_ago = (datetime.now() - lock_time).total_seconds() / 3600
                if hours_ago > 24:
                    stale_marker = " [yellow](may be stale)[/yellow]"
            except (ValueError, TypeError):
                pass
            host_str = f" on {hostname}" if hostname else ""
            out.append(ReadOnlyField(
                f"[b]\U0001f512 Locked:[/b] {locked_by}{host_str} since {locked_at}{stale_marker}",
                classes="meta-ro"))
        else:
            out.append(ReadOnlyField("[b]\U0001f513 Lock:[/b] [dim]Unlocked[/dim]", classes="meta-ro"))
        return out
```

**Note on `self._lock_info`:** it is initialized to `None` in `__init__`
(line ~2386) and consumed later in `compose()` for the button-disabled logic
(`is_locked = self._lock_info is not None`, line ~2573). `_build_lockfiles_fields`
preserves that side effect, and it is called *before* the button area is
composed (see Step 3), so behavior is unchanged.

#### Step 3 — Rewrite the metadata region of `compose()`

Replace the flat conditional run (current lines ~2464-2564, i.e. everything
between the close of the `#meta_editable` `with` block and the
`has_plan = ...` / `yield Label("[b]Viewing:[/b] Task", ...)` lines) with:

```python
            # --- Grouped, collapsible secondary metadata ---
            relations = self._build_relations_fields(meta)
            if relations:
                with Collapsible(title=f"Dependencies & hierarchy ({len(relations)})",
                                 collapsed=True, id="sec_relations", classes="meta-section"):
                    yield from relations

            tracking = self._build_tracking_fields(meta)
            if tracking:
                with Collapsible(title=f"Tracking & provenance ({len(tracking)})",
                                 collapsed=True, id="sec_tracking", classes="meta-section"):
                    yield from tracking

            lockfiles = self._build_lockfiles_fields(meta)
            if lockfiles:
                with Collapsible(title="Lock & files",
                                 collapsed=True, id="sec_lockfiles", classes="meta-section"):
                    yield from lockfiles
```

The `#meta_editable` block above and the `#view_indicator` / `#md_view` /
`#detail_buttons_area` blocks below remain exactly as-is.

#### Step 4 — CSS changes (`KanbanApp.CSS`, ~line 3408)

a) Bigger dialog — change `#detail_dialog` height:

```css
    #detail_dialog {
        width: 80%;
        height: 96%;            /* was 80% — near full vertical */
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
```

b) Tighten the collapsible sections so collapsed rows stay compact and blend
into the dialog (add after the `#meta_editable` rule, ~line 3442):

```css
    #detail_dialog .meta-section { padding-bottom: 0; border-top: hkey $secondary-background; }
    #detail_dialog .meta-section Contents { padding: 0 0 0 3; }
```

(Default `Collapsible` CSS adds `padding-bottom: 1` and `Contents { padding: 1 0 0 3 }`;
these overrides remove the extra vertical padding while keeping a left indent
and the separator line.)

## Verification

### Automated — new Pilot test `tests/test_board_detail_collapsible.py`

Follow the structure of `tests/test_board_detail_arrow_nav.py` (chdir to repo
root, import `KanbanApp`/`TaskDetailScreen`, drive via `app.run_test`). Add a
synthetic task with rich metadata if the live board lacks one (or `skipTest`
when no parent task is loaded, mirroring the existing test). Assert:

1. **Sections present & collapsed:** after pushing `TaskDetailScreen`, query
   `Collapsible` widgets; every `.meta-section` present has `.collapsed is True`.
2. **Core stays visible:** `#meta_editable` exists and its `CycleField`s
   (or `ReadOnlyField`s) are present and not inside any collapsed `Collapsible`
   (i.e. the editable core is a direct child of `#detail_dialog`, region-visible).
3. **Dialog height bumped:** `app.screen.query_one("#detail_dialog").styles.height`
   renders to 96% (assert the `Scalar`'s value/unit, or compare computed region
   height against an 80%-of-screen baseline at a fixed `size=`).
4. **Toggle works:** focus a section's `CollapsibleTitle`, `pilot.press("enter")`,
   assert that section's `.collapsed` flips to `False` and a previously-hidden
   field becomes focusable.
5. **No regression to nav:** down/up still move focus among visible fields and
   the section titles without dismissing the dialog.

### Regression

- `python3 -m pytest tests/test_board_detail_arrow_nav.py -v` — up/down field
  nav must still pass (CollapsibleTitle joins the focus chain).
- `python3 -m pytest tests/test_shortcut_scopes.py -v` — `board.detail` scope
  unchanged (no new bindings).
- Lint: `python3 -m pyflakes .aitask-scripts/board/aitask_board.py` (or repo's
  Python check) to confirm the `Collapsible` import is used and no name errors.

### Manual (recommended — TUI visual)

- `ait board` → open a task with many metadata fields (e.g. one with depends,
  risk, contributor, lock). Confirm: dialog is near full height; the three
  secondary sections appear collapsed; the markdown viewer is visibly larger;
  expanding a section pushes content and the viewer shrinks accordingly;
  Tab/↑/↓ navigation and Enter-toggle work; Save/Pick/Lock buttons still
  function. This is a candidate for a Step 8c manual-verification follow-up.

## Risk

### Code-health risk: low
- The `compose()` field-emission is refactored into three helper methods; a
  copy error could drop or alter a field's conditional, and the `self._lock_info`
  side effect must be preserved · severity: low · → mitigation: TBD (covered by
  the new Pilot test + existing arrow-nav test; helpers copy conditionals
  verbatim).

### Goal-achievement risk: low
- Requirements were confirmed via AskUserQuestion and map directly to the two
  changes; `Collapsible` availability verified on Textual 8.2.7 · severity: low
  · → mitigation: TBD.

## Step 9 — Post-Implementation

Standard cleanup/archival per `task-workflow` Step 9: commit code (regular git)
and plan (`./ait git`) separately, run archival via
`./.aitask-scripts/aitask_archive.sh 904`, push. Working on the current branch
(fast profile) — no worktree/branch teardown. `verify_build` per
`project_config.yaml` (if configured) runs at archival.
