---
Task: t1035_board_bytopic_sort_modes.md
Base branch: main
plan_verified: []
---

# Plan: Board By-Topic selectable sort modes + topic-build caching (t1035)

## Context

The board's By-Topic view (`y`) groups tasks into per-anchor swimlanes. v1
(t1016_4) shipped a single hardcoded ordering: topic lanes sorted
most-recently-touched first, with the "Ungrouped" lane always last. The user
asked for richer, selectable lane ordering. This task threads a `sort_mode`
through the grouping core, adds a context-scoped modal picker to switch modes
(persisted to board settings), and documents the modes. "Ungrouped" stays
pinned last in every mode.

Because reordering (and, later, filtering) will re-run the By-Topic build
repeatedly on a structurally-stable task set, this is also the right moment to
**cache the expensive bucket-building step** and separate it from the cheap
re-sort — so a mode change (or refocus refresh) re-sorts cached lanes instead
of re-bucketing every task.

All logic lives in `.aitask-scripts/board/aitask_board.py`; the ordering
decision is already isolated in the pure, import-tested
`group_tasks_by_topic(tasks)` (line 359) — the natural seam.

## Sort modes

| mode | ordering | notes |
|------|----------|-------|
| `recency` (default) | newest member's `updated_at`/`created_at` first | current behavior, unchanged |
| `topic_id` | root id descending (newest topic ids first) | numeric-segment aware (`t9` before `t10`) |
| `size` | most members first | stable ties keep first-seen order |
| `alphabetical` | lane label, case-insensitive ascending | |

"Ungrouped" is appended by the caller *after* lane sorting, so it stays last
in every mode for free (no per-mode special-casing).

## Files to modify

1. `.aitask-scripts/board/aitask_board.py` — core split + cache + app wiring + modal
2. `tests/test_board_topic_group.py` — sort-mode cases + cache behavior
3. `website/content/docs/tuis/board/reference.md` — sort-modes note + `o` key

---

## 1. Pure core — split build (cacheable) from sort, thread `sort_mode`

Near the topic-grouping block (~line 286) add module constants (imported by
tests, app, and modal):

```python
TOPIC_SORT_MODES = ("recency", "topic_id", "size", "alphabetical")
# (mode, human label) — drives the picker rows and the placeholder hint.
TOPIC_SORT_MODE_LABELS = [
    ("recency", "Recency (newest first)"),
    ("topic_id", "Topic id (newest first)"),
    ("size", "Size (largest first)"),
    ("alphabetical", "Alphabetical"),
]
```

Add the sort helpers alongside `_lane_recency` (~line 356):

```python
def _topic_id_sortkey(key):
    """Sortable key for a topic id ('1016', '130_2'): numeric segments compared
    as ints (so 't9' sorts before 't10') and negated for descending order.
    Non-numeric keys sort last, stringwise. Used by the 'topic_id' sort mode."""
    parts = str(key).split("_")
    try:
        return (0, tuple(-int(p) for p in parts))
    except ValueError:
        return (1, str(key))


def _sort_topic_lanes(lanes, sort_mode):
    """Sort (key, label, members) lane triples in place per mode. 'Ungrouped' is
    appended by the caller and is never in `lanes`, so it stays pinned last in
    every mode. Python's sort is stable → ties keep first-seen order."""
    if sort_mode == "topic_id":
        lanes.sort(key=lambda lane: _topic_id_sortkey(lane[0]))
    elif sort_mode == "size":
        lanes.sort(key=lambda lane: len(lane[2]), reverse=True)
    elif sort_mode == "alphabetical":
        lanes.sort(key=lambda lane: lane[1].casefold())
    else:  # "recency" (default)
        lanes.sort(key=lambda lane: _lane_recency(lane[2]), reverse=True)
```

Split the current `group_tasks_by_topic` body into a **build** step (the
expensive bucketing + label computation — the cacheable part) and an
**assemble** step (validate mode, sort, append Ungrouped — the cheap part).
Keep `group_tasks_by_topic` as the pure public entry (tests use it):

```python
def _build_topic_lanes(tasks):
    """Bucket tasks into topic lanes. Returns (topic_lanes, ungrouped) where
    topic_lanes is an unsorted list of (key, label, members) triples in
    first-seen order and ungrouped is the collapsed singleton members. This is
    the sort-independent, cacheable heart of the By-Topic view."""
    tasks_by_id = {}
    for task in tasks:
        own = task_own_id(task)
        if own:
            tasks_by_id.setdefault(own, task)

    buckets = {}
    order = []
    for task in tasks:
        key = topic_key(task, tasks_by_id)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(task)

    topic_lanes = []   # (key, label, members)
    ungrouped = []
    for key in order:
        members = buckets[key]
        if len(members) >= 2:
            topic_lanes.append(
                (key, _topic_lane_label(key, members, tasks_by_id), members))
        else:
            ungrouped.extend(members)
    return topic_lanes, ungrouped


def _assemble_topic_lanes(topic_lanes, ungrouped, sort_mode):
    """Order the cached lane triples per sort_mode and flatten to (label,
    members) pairs, pinning 'Ungrouped' last. Copies the triple list so a cached
    build is never reordered in place."""
    if sort_mode not in TOPIC_SORT_MODES:
        sort_mode = "recency"
    ordered = list(topic_lanes)
    _sort_topic_lanes(ordered, sort_mode)
    lanes = [(label, members) for _key, label, members in ordered]
    if ungrouped:
        lanes.append(("Ungrouped", ungrouped))
    return lanes


def group_tasks_by_topic(tasks, sort_mode="recency"):
    """Bucket tasks into per-anchor topic lanes, ordered by sort_mode (one of
    TOPIC_SORT_MODES; unknown → 'recency'). 'Ungrouped' is always last.
    Uncached pure entry point — the board renders via
    TaskManager.grouped_topic_lanes(), which caches the build."""
    topic_lanes, ungrouped = _build_topic_lanes(tasks)
    return _assemble_topic_lanes(topic_lanes, ungrouped, sort_mode)
```

Behavior is identical to today when called `group_tasks_by_topic(tasks)`
(default recency) — existing tests keep passing.

## 2. Caching layer — `TaskManager`

The build depends only on each task's **filename** (own id / label) and
**anchor** (its own topic key, and — for children — its parent's key), consumed
**in input order** (buckets, lane tie order, and Ungrouped member order all
follow first-seen order). The sort depends on live
`updated_at`/`created_at`/member-count/label, read from the same Task objects.
So:

- An **ordered content signature** = the sequence of `(filename, anchor)` pairs
  in input order detects every change that alters bucket membership, labels, or
  first-seen ordering (add/remove/anchor edit — including a parent anchor change
  that re-keys its children — *and* any reordering of the input list). It is
  deliberately **not** sorted: `_build_topic_lanes` preserves first-seen order,
  so an order-independent signature would let a reordered-but-same-membership
  input return a cached build with stale tie/Ungrouped order. Matching the
  signature to the exact ordered input the build consumes closes that hidden
  contract. In-place edits to non-structural fields (status, `updated_at`,
  boardidx) mutate the *same* Task objects, so a re-sort/re-render reads fresh
  values with no staleness → they need not invalidate the build.
- The one case a signature can miss is **object replacement** with an identical
  signature (e.g. `r`/auto-refresh calls `load_tasks()`, rebuilding all Task
  objects with unchanged filenames+anchors+order but possibly changed status).
  Those go through exactly three seams — `load_tasks`, `load_child_tasks`,
  `reload_task` — so clear the cache explicitly there.

Add to `TaskManager.__init__` (near the other caches, ~line 414):
```python
# (signature, topic_lanes, ungrouped) for the By-Topic build; None = cold.
self.topic_lane_cache = None
```

Signature helper (module-level, pure):
```python
def _topic_membership_signature(tasks):
    """Ordered signature of the inputs that affect topic *bucketing* (not sort
    ordering): each task's filename + anchor, in input order. NOT sorted —
    _build_topic_lanes preserves first-seen order for lane ties and Ungrouped
    members, so the signature must change when the input order changes.
    Sort-mode inputs (updated_at, size, label) are re-read live at sort time and
    are intentionally absent here."""
    return tuple(
        (t.filename, str(t.metadata.get("anchor") or "")) for t in tasks)
```

Cached accessor on `TaskManager`:
```python
def grouped_topic_lanes(self, tasks, sort_mode):
    """Cached By-Topic lanes: rebuild buckets only when the membership/anchor
    signature changes; otherwise re-sort the cached build (cheap). This makes
    sort-mode switches and refocus refreshes O(lanes·log) instead of
    re-bucketing every task."""
    sig = _topic_membership_signature(tasks)
    if self.topic_lane_cache is None or self.topic_lane_cache[0] != sig:
        topic_lanes, ungrouped = _build_topic_lanes(tasks)
        self.topic_lane_cache = (sig, topic_lanes, ungrouped)
    _sig, topic_lanes, ungrouped = self.topic_lane_cache
    return _assemble_topic_lanes(topic_lanes, ungrouped, sort_mode)
```

Clear at the three reload seams — add `self.topic_lane_cache = None` at the top
of `load_tasks` (~463), `load_child_tasks` (~473), and `reload_task` (~484).
(`load_tasks` already calls `load_child_tasks`; the redundant clear is
harmless.) This mirrors how `clear_gate_cache()` is invoked from `load_tasks`.

## 3. App wiring

**Reader** on `BoardApp` (validated):
```python
def _topic_sort_mode(self):
    mode = self.manager.settings.get("topic_sort_mode", "recency")
    return mode if mode in TOPIC_SORT_MODES else "recency"
```

**refresh_board** bytopic branch (line 4652): render via the cached accessor —
`for label, members in self.manager.grouped_topic_lanes(all_tasks, self._topic_sort_mode()):`.

**Binding** (after the `y`/`view_bytopic` line, ~4450):
`Binding("o", "sort_topic", "Sort Order")` — `o` is free (`O`=Options,
`s`=Sync). Shown in the footer but gated to the By-Topic view via
`check_action`.

**check_action** gate (with the other conditional actions, ~4547):
```python
elif action == "sort_topic":
    if self.base_filter != "bytopic":
        return None
```

**Action** — open the picker, persist + re-render on change (re-render hits the
cache → no rebuild, just re-sort):
```python
def action_sort_topic(self):
    if self.base_filter != "bytopic":
        return
    def on_dismiss(mode):
        if mode is None or mode == self._topic_sort_mode():
            return
        self.manager.settings["topic_sort_mode"] = mode
        self.manager.save_metadata()
        focused = self._focused_card()
        refocus = focused.task_data.filename if focused else ""
        self.refresh_board(refocus_filename=refocus)
    self.push_screen(TopicSortModeScreen(self._topic_sort_mode()), on_dismiss)
```

`topic_sort_mode` lands under `settings` → a **user key** (`_USER_KEYS =
{"settings"}`, line 64), so it persists locally/gitignored exactly like
`filter_issue_types` — no project-config churn.

**Modal** — mirror the single-select `GateChoiceScreen` / `GateChoiceItem`
pattern (line 1394), reusing the `#dep_picker_dialog` / `#dep_picker_title`
styles. Focusable `Static` rows already get up/down focus cycling via the
app's `action_nav_up/down` (no `check_action` nav change needed — see comment
at line 4479). Add near `GateChoiceScreen`:
```python
class TopicSortModeItem(Static):
    """Focusable row for selecting a By-Topic sort mode."""
    can_focus = True
    def __init__(self, mode: str, label: str, selected: bool):
        glyph = "◉" if selected else "○"  # ◉ current, ○ others
        super().__init__(f"{glyph} {label}")
        self.mode = mode
    def on_focus(self):
        self.add_class("dep-item-focused")
    def on_blur(self):
        self.remove_class("dep-item-focused")
    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.mode)
    def on_click(self, event):
        self.screen.dismiss(self.mode)


class TopicSortModeScreen(ModalScreen):
    """Single-select picker for the By-Topic lane sort order."""
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]
    def __init__(self, current: str):
        super().__init__()
        self.current = current
    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                "Topic sort order — [dim]Enter to select, Esc to cancel[/]",
                id="dep_picker_title",
            )
            for mode, label in TOPIC_SORT_MODE_LABELS:
                yield TopicSortModeItem(mode, label, selected=(mode == self.current))
    def on_mount(self):
        for item in self.query(TopicSortModeItem):
            if item.mode == self.current:
                item.focus()
                break
    def action_cancel(self):
        self.dismiss(None)
```

**Discoverability** — surface the current mode in the By-Topic search
placeholder (`_compute_search_placeholder`, line 5023):
```python
elif self.base_filter == "bytopic":
    base = f"Search topics · sort: {self._topic_sort_mode()}"
```

## 4. Tests — `tests/test_board_topic_group.py`

**Sort modes** — add a `TopicSortModeTests` class (reuse the `_mk` helper).
Build ≥2 lanes differing in recency, size, id, and label, plus loners, then
assert per mode:
- **recency** — explicit `sort_mode="recency"` matches the existing default
  ordering (newest-member lane leads).
- **topic_id** — highest root id leads; `t9` before `t10` (numeric, not
  lexical).
- **size** — most-member lane leads; equal-size ties keep first-seen order.
- **alphabetical** — lanes ordered by label case-insensitively.
- **Ungrouped-last invariant** — loop over `TOPIC_SORT_MODES`, assert
  `lanes[-1][0] == "Ungrouped"` for every mode.
- **unknown mode → recency fallback** — `sort_mode="bogus"` equals recency.

**Caching** — add a `TopicBuildCacheTests` class. `TaskManager.__init__` does
real disk I/O (`_ensure_paths()` mkdir, `load_metadata()` which may write
`board_config.json`, `load_tasks()` globs the repo), so **construct via
`TaskManager.__new__(TaskManager)`** — the repo's established test pattern
(`tests/test_board_inflight_view.py:21`) — and set only the fields the tested
methods touch (`topic_lane_cache = None`, and `task_datas = {}` /
`child_task_datas = {}` for the reload-seam tests). Use a call-counting spy that
monkeypatches the module's `_build_topic_lanes` (restore in `tearDown`):
- **cache hit on same signature** — two `grouped_topic_lanes(tasks, m)` calls
  with different modes rebuild **once** yet return correctly-different orders
  (proves re-sort off cache, and that the cached triples aren't mutated).
- **rebuild on anchor change** — mutate a task's `anchor` → signature differs →
  second call rebuilds.
- **rebuild on membership change** — add/remove a task → rebuild.
- **rebuild on input reorder** (concern-driven) — pass the *same* task set in a
  different order → signature differs → rebuild (guards the first-seen order
  contract; a sorted signature would wrongly cache-hit here).
- **reload seams clear the cache** (negative control) — preset
  `mgr.topic_lane_cache = ("stale",)`; `reload_task("nope.md")` (fast
  false-return path, no disk writes) must leave it `None`; and, with
  `glob.glob` monkeypatched to `[]`, `load_child_tasks()` must leave it `None`.
  This proves the object-replacement seam can't serve stale Task objects.

## Risk

Assessed separately on the two required dimensions.

### Code-health risk: medium
- Caching layer is the only stateful/invalidation-bearing part; a wrong
  invalidation could render stale lanes · severity: medium · → mitigation:
  contained in-task (ordered filename+anchor signature + clears at the three
  object-replacement seams + negative-control tests that reproduce staleness if
  a seam-clear is removed or the signature is order-independent)
- Sort split + modal are additive, copy established in-file patterns, and keep
  `group_tasks_by_topic`'s recency-default behavior; cache is board-local (one
  `TaskManager` field), touches no shared surface, and degrades safely (a
  cold/None cache just rebuilds) · severity: low · → mitigation: TBD (none
  needed)

### Goal-achievement risk: low
- Subtle correctness points — numeric `topic_id` ordering, Ungrouped-last
  invariant, cache hit/invalidate/clear — could regress · severity: low · →
  mitigation: each pinned by unit tests, including negative controls
- Requirements are concrete and fully covered (4 modes, Ungrouped pinned last,
  switch affordance, persistence, build caching, tests, docs); affordance
  confirmed with the user (modal picker on `o`) · severity: low · → mitigation:
  TBD (none needed)

No before/after mitigation tasks required: goal-achievement risk is low and the
medium code-health risk is fully contained by the in-task test guards above.

## Verification

```bash
# Pure-core + cache unit tests (primary):
python3 -m pytest tests/test_board_topic_group.py -v
# Full python suite (board import smoke + regressions):
bash tests/run_all_python_tests.sh
```

Manual smoke (optional): `ait board` → `y` (By-Topic) → `o` opens the picker →
select each mode and confirm lane order changes while "Ungrouped" stays last;
reorder several times and confirm no visible rebuild lag; press `r` after an
external edit and confirm the view reflects it (cache invalidated); re-open
`ait board` and confirm the chosen mode persisted.

## Post-Implementation

Follows the shared task-workflow Step 8 (review) → Step 9 (merge + archive).
This task is risk-gated (`risk_evaluated`), so the `## Risk` section above is
required; the workflow writes the two risk levels to the task frontmatter
post-approval and records the `risk_evaluated` gate at Step 9.

## Post-Review Changes

### Change Request 1 (2026-07-02)
- **Requested by user:** `o` shortcut sat at the end of the footer; task/column
  movement actions and the `x` toggle-children action stayed *visible but
  greyed* in the By-Topic (and In-Flight) views instead of being hidden; the
  sort picker did not respond to ↑/↓ and applied immediately on click with no
  confirmation.
- **Changes made:**
  - Moved the `o` (Sort Order) binding to just after `View/Edit` so it reads
    near the front of the footer.
  - Rebuilt the picker (`TopicSortModeScreen`) as a custom row-based modal: the
    screen owns ↑/↓ (`cursor_up`/`cursor_down`) with a `check_action`
    fall-through (mirroring `SectionViewerScreen`); a click only *selects* a
    row; Enter / Confirm applies; Esc / Cancel dismisses with no change. (A
    `RadioSet` was rejected — its cursor-vs-pressed split and toggle-on-Enter
    would need fragile private-attr overrides.)
  - **Root cause of the "greyed not hidden" issue:** in Textual 8.2.7
    `Screen.active_bindings`, `check_action` returning `False` *excludes* a
    binding (hidden) while `None` yields `enabled=False` (shown, greyed). The
    board's `check_action` used `return None` with `# Hide from footer`
    comments, so those actions were only greyed. Changed the movement actions
    (`move_task_*`, `move_col_*`, `toggle_column_collapsed`) and
    `toggle_children` to `return False` in the derived In-Flight / By-Topic
    views, and made the `sort_topic` gate return `False` outside By-Topic.
- **Files affected:** `.aitask-scripts/board/aitask_board.py`,
  `tests/test_board_topic_group.py`.

## Final Implementation Notes
- **Actual work done:** Added 4 selectable By-Topic lane sort modes
  (`recency` default, `topic_id`, `size`, `alphabetical`) by splitting the pure
  build (`_build_topic_lanes`) from the sort/assemble (`_assemble_topic_lanes`)
  and threading `sort_mode` through `group_tasks_by_topic`. Added a cached
  accessor `TaskManager.grouped_topic_lanes` (ordered `(filename, anchor)`
  signature; cleared at the `load_tasks`/`load_child_tasks`/`reload_task`
  seams). Added a context-scoped `o` key + `TopicSortModeScreen` picker
  (persisted to board settings). "Ungrouped" stays pinned last in every mode.
  Documented in the board reference. 34 unit tests (sort modes, cache
  behaviour incl. negative controls, picker logic) all pass.
- **Deviations from plan:** The picker was implemented as a custom row modal
  rather than the originally-sketched focusable-Static list, after review
  feedback surfaced that arrow-nav and confirm-before-apply were required.
- **Issues encountered:** Textual 8.2.7's `check_action` footer semantics are
  the inverse of the board's long-standing assumption (`None` greys, `False`
  hides) — see Post-Review Changes.
- **Upstream defects identified:** `.aitask-scripts/board/aitask_board.py` —
  multiple `check_action` branches (`commit_selected`, `commit_all`,
  `pick_task`, `brainstorm_task`, `open_cross_repo`) `return None` with a
  `# Hide from footer` intent, but under Textual 8.2.7 `None` only greys the
  key rather than hiding it (only `False` hides). These footer actions are
  therefore shown greyed instead of hidden when inapplicable. Out of scope for
  t1035 (user chose to scope this task to the movement/sort/toggle-children
  actions); worth a separate bug task to normalize the remaining sites to
  `return False`.
