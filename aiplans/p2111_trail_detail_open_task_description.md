---
Task: t2111_trail_detail_open_task_description.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2111 — Trail detail modal: task header + "open description" control

## Context

Opening a trail card's details (Enter / double-click), in `ait trails` and in
`ait board`'s By-Trail view, shows why the task holds its place in the wave but
nothing about the task itself: no title, no live status, no description. In
`ait trails` there is no other way to reach the task content. The user does
**not** want the full description appended to the modal body, which is already
long. They want a short "what is this task" header plus an explicit control
that opens the full description in its own screen.

## Files

- `.aitask-scripts/board/board_trail_view.py`: `TrailEntryView`,
  `build_trail_lanes`, `TrailDetailScreen`
- `.aitask-scripts/board/board_trail_screen.py`: `_open_trail_entry_detail`
- `.aitask-scripts/board/trails_app.py`: `check_action` nav guard for the
  pushed viewer
- `tests/test_board_bytrail_view.py`, `tests/test_trails_app.py`: new tests

Add no new top-level names to `board_trail_view.py`. `tests/test_board_trail_view.py`
pins that module's exact top-level name set (`MOVED_NAMES | VIEW_ONLY_NAMES`), so
every helper becomes a method on `TrailDetailScreen`.

## Steps

1. **Keep the archived task** (`board_trail_view.py`).
   - Add the field `archived_task: "Task | None" = None` at the end of
     `TrailEntryView`. Positional constructors keep working. `task` stays
     `None` for every ghost, because card and gating code reads
     `view.task`/`is_ghost` as "live".
   - In `build_trail_lanes`, the archived branch does
     `TrailEntryView(entry, None, "archived", landed, drift, archived_task=archived_task)`.
   - Live views do not need the field: they use `view.task`.
   - Check `tests/lib/trail_model_checks.py` for `==` comparisons of whole
     views, and update any that build an archived view without the new field.

2. **Pass the task through** (`board_trail_screen.py`,
   `_open_trail_entry_detail`). Read `view = getattr(card, "trail_view", None)`.
   Set `task = view.task if view.task is not None else view.archived_task` and
   `ghost_kind = view.ghost_kind`. Push
   `TrailDetailScreen(doc, reasons, entry=…, wave=…, task=task, ghost_kind=ghost_kind)`.
   Both hosts already route through this method: `aitask_board.py`
   `action_view_details` and `trails_app.py` `action_view_details`. This
   respects contracts C1 and C2: the view receives task objects and never
   looks up files.

3. **`TrailDetailScreen` constructor**: add the keyword arguments `task=None`
   and `ghost_kind=""`, stored as `self.task` and `self.ghost_kind`. Existing
   call sites (tests, the no-entry path) stay valid.

4. **Compact task header**, rendered by a new `_task_header(text, head, line)`
   step inside `_sections()`. It runs only when `self.entry is not None` and
   comes before the `Entry …` section, so with no entry the output is
   byte-identical to today.
   - With a task: `head(f"Task {task_num} · {task_name}" + (" (archived)" if ghost_kind == "archived" else ""))`.
     `task_num` and `task_name` come from `TaskCard._parse_filename(task.filename)`,
     the parser the cards use (`board_widgets` is already imported).
   - Then one metadata line from the **live task file's** frontmatter, not the
     trail snapshot: `status · priority · effort · type: <issue_type> · labels: a, b`.
     Empty fields are skipped.
   - Then one hint line: `Description: press o (or the Description button) to open it`.
     When `content.strip()` is empty, it reads `Description: the task file has no description`.
   - With no task: `head(f"Task {entry['task']}")` and one reason line:
     - `cross_repo`: "lives in another repository — no local task file, so its description is not available here."
     - `missing`: "no task file found (active or archived) — description not available."
   - Values are appended to the `Text` as plain strings, never as markup (as
     the existing `line()` helper does).

5. **Description control**
   - Add a `_description_available()` method: `self.task is not None and bool((self.task.content or "").strip())`.
   - Add the binding `Binding("o", "view_description", "Description", show=False)`.
     `o` does not collide with the modal's `a`/`escape`. It avoids the
     By-Trail host's `d` (Freshness), `v` (Summary) and `T`. The board's
     App-level `o` (sort order) is non-priority, so the screen binding shadows
     it, the same way `a` shadows `view_all`.
   - `check_action`: `if action == "view_description": return self._description_available()`.
   - `action_view_description` re-checks `_description_available()` first,
     because a binding gate is not an action guard. It then lazily imports
     `SectionViewerScreen` from `section_viewer` inside try/except, matching
     `board_detail_screen.action_fullscreen_plan`, and calls
     `self.app.push_screen(SectionViewerScreen(self.task.content, title=f"{task_num} {task_name} — description"))`.
     If the import fails, it shows a warning notification.
   - `compose`: wrap the buttons in `Horizontal(id="trail_detail_buttons")`.
     `Button("Description (o)", id="btn_trail_detail_desc")` is added only when
     `_description_available()`, followed by the existing Close button. Add the
     CSS rule `#trail_detail_buttons { height: auto; }` to `DEFAULT_CSS`. An
     `@on(Button.Pressed, "#btn_trail_detail_desc")` handler calls the action.

6. **Arrow keys in the pushed viewer under `ait trails`** (`trails_app.py`
   `check_action`). TrailsApp binds the arrow keys at App level with
   `priority=True`, and `_nav_vertical` just cycles focus while any modal is
   up. Under the stand-alone app, ↑/↓ would therefore never reach the
   `SectionViewerScreen` minimap or the Markdown scroll. Add the board's
   existing rule to the nav block: when `type(self.screen).__name__ == "SectionViewerScreen"`,
   return `False` for `nav_*`. The board already has this rule in
   `aitask_board.py` around line 2470.

7. **Cross-repo descriptions are deferred.** Fetching a foreign task's body via
   `aitask_query_files.sh --project` would need a subprocess and a worker from
   the modal, plus an availability story. The header states why no description
   is shown. This plan does not create a follow-up task; mention the option in
   the Final Implementation Notes.

## Tests

In `tests/test_board_bytrail_view.py`, a new `TrailDetailTaskHeaderTests(ByTrailTestBase)`:

- **Live task, unit test without an App.** Construct a `Task` with
  `Task.from_text` (title, status, priority, effort, issue_type, labels, body)
  and pass it to `TrailDetailScreen(..., task=t, ghost_kind="")`. Assert that:
  - the header shows the title and metadata;
  - `Task t…` comes before `Entry …`;
  - `check_action("view_description")` is True;
  - the body text is **not** in `_sections().plain`, per the user's constraint.
- **Live task, pilot test on the board.** Enter synthetic By-Trail with the
  fixture, focus the first card (`aitasks#1147`), press Enter, and assert
  `app.screen.task is focused.task_data`. Press `o`, assert the screen is
  `SectionViewerScreen` and its `_content` equals the task's content. Press
  Escape and assert the screen is back to `TrailDetailScreen`.
- **Archived.** Run `build_trail_lanes` with an `archived_lookup` that returns
  a `Task`. Assert `view.task is None`, `ghost_kind == "archived"` and
  `view.archived_task is` that task. A screen built with it shows "(archived)"
  and has the description available.
- **Missing and cross-repo.** The header shows the reason text, and
  `check_action("view_description")` is False. Calling `action_view_description()`
  directly on the unmounted screen returns without touching `self.app`, which
  would raise if it were reached. An entry and task with an empty body gives
  the "no description" line and the control is unavailable.
- **No entry.** `TrailDetailScreen(doc, [])._sections()` contains no `Task `
  header, and the existing no-entry assertions still hold.

In `tests/test_trails_app.py`, a new `TrailDetailTaskTests(TrailsAppTestBase)`:
- **Live card.** Using `_boot_and_select`, press Enter on the first live member
  and assert the modal's `task` is the focused card's `task_data`. Press `o`
  and assert `SectionViewerScreen`. While it is up,
  `app.check_action("nav_down", ())` is False, and ↓ does not dismiss it or
  change the focused card. Press Escape and the detail is back.
- **Archived ghost, opened through its real card.** This end-to-end check
  covers the opener's `view.archived_task` handoff, which a direct
  `TrailDetailScreen(...)` construction would bypass.
  - Patch the board `TaskManager._load_archived_task`, at class level so it is
    in place before the first render, to return
    `Task.from_text(<archived path>, raw, archived=True)` for `GHOST_REF`
    (`"99999"`) and `None` otherwise. `raw` carries a distinctive status, a
    title and a body marker.
  - Boot, navigate to the ghost card, and assert it is a `TrailGhostCard` whose
    `trail_view.ghost_kind == "archived"`.
  - Press Enter. The modal's `task` is the archived `Task`, its `ghost_kind` is
    `"archived"`, and the header shows "(archived)" plus the archived status.
    `#btn_trail_detail_desc` is mounted.
  - Press `o`. The screen is `SectionViewerScreen` and its `_content` contains
    the archived body marker. Escape returns to the detail.
  - **Negative control, run during implementation and not committed:**
    temporarily change `_open_trail_entry_detail` to pass `task=view.task`
    only, and confirm this test fails. Then restore the change.

Existing tests must keep passing: scoping, the `a` toggle and its gating, the
totals line, layout centring (`test_the_detail_modal_lays_out_without_the_board`)
and the single-home and re-export checks.

## Verification

```bash
python3 -m pytest tests/test_board_bytrail_view.py tests/test_trails_app.py tests/test_board_trail_view.py -q
bash tests/run_all_python_tests.sh   # read the final PYTHON SUITE line
```

Manual: run `ait trails` and open a trail. Enter on a live card shows the
header; `o` opens the description and arrows scroll it; Escape returns. Do the
same on a ghost card. The same flow works in `ait board`'s By-Trail view.

## Post-implementation

Step 9 of the task workflow: review, commit, archive.

## Risk

### Code-health risk: low
- `TrailEntryView` gains a field, and the modal's `compose` gains a button row.
  This could disturb existing view-equality checks or the modal layout test.
  severity: low · → mitigation: none (covered by step 1's check of
  `trail_model_checks.py` and by the existing layout test running unchanged)
- The stand-alone TrailsApp's priority arrow bindings would starve the pushed
  `SectionViewerScreen`. severity: low · → mitigation: none (addressed in plan
  step 6, with a test)

### Goal-achievement risk: low
- Archived ghosts could lose the header and description if the opener dropped
  `view.archived_task`, and unit-level tests would not catch it. severity: low
  · → mitigation: none (covered by the archived-ghost pilot test, which opens
  the modal through the real card, plus its negative control)

The header, the control, the ghost reasons, both hosts and the no-entry path are
each covered by a step and a test. Cross-repo description fetching is explicitly
deferred.
