---
Task: t1243_10_group_collapse_and_filtering.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_11_group_formation_and_block_moves.md, aitasks/t1243/t1243_12_group_membership_commands.md, aitasks/t1243/t1243_13_documentation.md, aitasks/t1243/t1243_14_retrospective_benchmark.md, aitasks/t1243/t1243_15_manual_verification_board_groups_and_reordering.md
Archived Sibling Plans: aiplans/archived/p1243/p1243_1_movement_baseline_and_harness.md, aiplans/archived/p1243/p1243_2_board_field_persistence_seam.md, aiplans/archived/p1243/p1243_3_gap_indexing.md, aiplans/archived/p1243/p1243_4_render_filter_scoping.md, aiplans/archived/p1243/p1243_5_lateral_dom_transplant.md, aiplans/archived/p1243/p1243_6_multiselect_marking.md, aiplans/archived/p1243/p1243_7_move_to_column_command.md, aiplans/archived/p1243/p1243_8_boardgroup_field_and_model.md, aiplans/archived/p1243/p1243_9_group_focus_and_rendering.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-10 18:37
---

# t1243_10 — Group collapse persistence and filtering

## Context

Child 10 of 14 in the t1243 board-groups decomposition. In-column task groups
already render (`GroupHeader`, t1243_9) and can be collapsed with `x`, but the
collapse state is **session-only** — it dies with the process. This task makes it
durable, gives every operation that can invalidate a collapse key an owner, and
finishes the one remaining gap in group-aware filtering.

**This plan was re-verified against the live tree and is materially narrower than
the version on disk.** `aitask_board.py` has grown 9,043 → 11,901 lines since
t1243_10 was written, and t1243_9 landed most of what the old plan's "Step 1 —
unit-level filtering" describes. Verified present today:

| Old plan Step 1 item | Status |
|---|---|
| Collapsed group evaluated from member `Task` **data** | ✅ `_group_header_matches` (`:8097`) |
| Header visible iff ≥1 member **or member's child** matches | ✅ child-aware via `_any_child_matches` (`:8069`), hardened by t1469 |
| Visible header counts toward `cols_with_visible` | ✅ header loop `:8202-8208`, ordered before the placeholder loop |
| `GroupHeader` in the focus-rescue isinstance tuple | ✅ `:8221` |
| Scoped `apply_filter(cols=…)` reaches headers | ✅ `_filter_group_headers(cols)` (`:8036`) |
| `· N match` badge | ❌ **remains** — `GroupHeader._label()` (`:2405`) carries a forward pointer to it |

So the real remaining scope is: **persistence, the lifecycle owners, the
prune-on-load sweep, the badge, and the test matrix.** Two further premise shifts:
`merge_columns` (t1377_4) landed *before* t1243_9, so per the task's own "Notes for
sibling tasks" **this task owns the sixth lifecycle owner**; and the group-move /
group-rename / group-dissolve owners belong to t1243_11 / t1243_12, which have not
landed — this task ships the seam they will call, not their wiring.

## Design decisions

**D1 — The manager owns the live set; the app aliases it.** `TaskManager` gains
`collapsed_groups: set` and `KanbanApp.__init__` assigns
`self.collapsed_groups = self.manager.collapsed_groups`. Every `KanbanColumn`
keeps holding that same object by reference (`:3534`), so t1243_9's data flow is
untouched — only its two ends move.

This removes the sync problem rather than managing it: a `TaskManager` lifecycle
method that re-points keys has *already* updated the board's rendering source when
it returns, so there is no post-call step anyone can forget, and the headless
`merge_columns` seam works with no app present. Rejected: re-seeding the app's set
inside `refresh_board` — two of the four owners run inside `ColumnManageScreen`,
which refreshes only in `on_closed` (`:11124`), so the sync would lag a whole modal
session.

The hazard this creates is **rebinding**: `self.collapsed_groups = {...}` anywhere
would orphan every column's reference. Closed by making
`_reset_collapsed_groups(keys)` (`clear()` + `update()`) the only site that replaces
contents.

**D2 — Runtime saves write only the user layer.** `aidocs/framework/tui_conventions.md:198-207`
is explicit: *"Runtime `save()` paths in config modules must write only the
user-level (`*.local.json`, gitignored) layer. Project-level (`*.json`, tracked)
files are read-only at runtime."* Today `save_metadata()` **always** rewrites the
tracked `board_config.json` (the `if user_data:` guard at `:1321` is vacuous —
`data` always carries the `"settings"` key), and it runs `_reconcile_external_columns()`,
which can mutate `self.columns` and raise a user-visible toast. Under the old
approach, pressing `x` on a group header could pull in another checkout's column
and pop a reconciliation notice.

New `TaskManager.save_settings()` writes only the local layer.

**The policy is the whole surface, not the two sites this task happened to touch.**
Audited every `settings` write and every `save_metadata()` caller in
`aitask_board.py` (7 writes, 12 call sites). Five *existing* paths mutate `settings`
and nothing else, and all five must be routed through `save_settings()`:

| Site | Mutates | Verdict |
|---|---|---|
| `toggle_column_collapsed` `:2064` | `settings` only | **→ `save_settings()`** |
| `action_sort_topic` `:8381-8382` (`topic_sort_mode`) | `settings` only | **→ `save_settings()`** |
| type-filter dismiss, empty confirm `:8410-8411` | `settings` only | **→ `save_settings()`** |
| type-filter dismiss, non-empty `:8418-8419` | `settings` only | **→ `save_settings()`** |
| `_handle_settings_result` `:11233-11234` | `settings` only — `SettingsScreen.dismiss` (`:6344`) returns exactly `{auto_refresh_minutes, sync_on_refresh}` | **→ `save_settings()`** |
| `load_metadata` bootstrap `:1190` | creates both files when absent | keep — first-time ship of a project file is the exception the convention names |
| `add_column` `:2010`, `update_column` `:2046`, `delete_column` `:2084`, `merge_columns` `:2186` | `columns` / `column_order` | keep (project) |
| `ColumnManageScreen._shift` `:6598`, `_shift_column` `:10973` | `column_order` | keep (project) |

Also audited and **correctly excluded**: `settings/settings_app.py::save_board`
(`:502`) writes both layers, but that is the `ait settings` editor — the "explicit
user-initiated" exception the convention carves out — and it legitimately edits
`columns` too. `_prune_orphan_collapsed_columns` `:1223` writes `settings` but
issues no save at all, by design.

**A one-time audit is not a policy.** The split is invisible at the call site — both
methods are one line and either "works" — so the sixth author to add a settings key
will reach for `save_metadata()` exactly as the previous five did. Structural fix:
extend the **existing** AST guard in `tests/test_board_columns_reconcile.py`, which
already scans `aitask_board.py` for callers of a watched symbol against an
`ALLOWED_CALLERS` allowlist and carries a negative control that injects a fake call
site (`:294-406`). Add `save_metadata` as a watched callee whose allowlist is the
**seven** project-mutating functions above (`load_metadata`, `add_column`,
`update_column`, `delete_column`, `merge_columns`, `ColumnManageScreen._shift`,
`_shift_column`); a new settings-only caller then fails the suite with a message
naming `save_settings()`.

**Guard caveat to handle, not discover later:** three of the five settings-only sites
live in nested `on_dismiss` closures, and `_callers_of` attributes a call to its
*immediately* enclosing `FunctionDef` — so they currently attribute to `on_dismiss`,
a name shared by several unrelated modals. Attribute to the **outermost enclosing
method** instead (walk the `FunctionDef` stack), or the allowlist becomes ambiguous
and a future `on_dismiss` inherits an exemption it was never granted. The negative
control must inject its synthetic caller **inside a closure** so it proves this
specific behaviour rather than the easy top-level case.

*Cost of the retrofit, verified:* two tests in `tests/test_board_column_manage.py`
(`:384-387`, `:740-748`) use `toggle_column_collapsed("c3")` purely as a gesture
meaning *"now issue a later project-layer save"*, then assert on `project_cols()`.
The invariant they guard (a merged source must not be resurrected) is untouched;
only the gesture stops writing the project file, which would make them vacuous.
Retarget both to `self.manager.save_metadata()` — which is what the neighbouring
test at `:737` already does. No test asserts on the project layer for the
type-filter or settings-dialog paths (checked), so those three carry no test cost.

**D3 — Coalescing is a set union, and that is provable.** Collapse state is a
*presence* set, not a value map. "Destination wins if it already exists" and
"otherwise the arriving key's state is adopted" agree in all four cells:

| arriving | destination | union of re-pointed keys |
|---|---|---|
| collapsed | collapsed | present (deduped) |
| expanded | collapsed | present — arriving contributed nothing |
| collapsed | expanded | present — adopted |
| expanded | expanded | absent |

The vacated key is dropped for free, because a re-point *rewrites* rather than
adds beside. This equivalence holds **only** because the key carries no value; the
docstring must say so, so a future value-carrying view key is forced to revisit it
rather than inherit a coincidence.

**D4 — Badge semantics.** The count is *"how many member cards the expanded group
would show"* — per member, "matches itself **or** a child matches", i.e. exactly
`apply_filter`'s unit-loop rule for a mounted parent. Shown **only** when the group
is collapsed, the header is visible, a filter is actually narrowing, and the count
is **less than the member total** (`· 3 match` on `▸ perf work (3)` is noise).

Counting is a **separate function from `_group_header_matches`, not a second
predicate**: it composes the same two primitives (`task_matches_filter`,
`_any_child_matches`) member by member. They must stay separate because
`_group_header_matches` short-circuits on the first matching member and never
reaches the child index for a group that matched cheaply — making visibility
`count > 0` would force a full member walk and a `_children_by_parent()` build on
every keystroke, flipping the existing `idle == 0` control in
`test_child_index_is_built_at_most_once_per_pass`.

**D5 — The prune sweep runs after `load_tasks()`, not in `load_metadata()`.**
`TaskManager.__init__` runs `load_metadata()` *then* `load_tasks()`. Membership is
a fact about tasks; the column sweep's fact (the id list) is a fact about config.
Copying `_prune_orphan_collapsed_columns`' placement would see zero members for
every key and **wipe the whole list on every boot**.

## Implementation

### Pre-phase (risk mitigations)

**`anchor-reverify`** — before any edit, re-locate every symbol this plan names by
**name** (never line number) and confirm the behaviour still matches: `apply_filter`
and its three `_filter_*` generators, `_group_header_matches`, `_any_child_matches`,
`_children_by_parent`, `GroupHeader._label`/`set_collapsed`, `KanbanColumn.compose`/
`is_group_collapsed`, `TaskManager.load_metadata`/`save_metadata`/`load_tasks`/
`update_column`/`delete_column`/`merge_columns`/`_prune_orphan_collapsed_columns`,
and `board_groups.build_column_units`/`group_members`/`normalize_group_slug`. Re-run
the D2 audit (`grep -n "settings\[[^]]*\] *=\|settings\.update(" ` and
`grep -n "save_metadata()"` over `aitask_board.py`) and confirm the counts still read
7 writes / 12 call sites. If a premise has changed, **stop and record it** rather
than working around it.

### 1. `.aitask-scripts/lib/board_groups.py` — pure key algebra

Append `GROUP_KEY_SEP = "/"`, plus:

- `group_key(col_id, slug)` → `"<col>/<slug>"`. The **single** construction site;
  `KanbanColumn.is_group_collapsed` (`:3538`) switches to it so the runtime set and
  the persisted list cannot drift apart via a second f-string.
- `parse_group_key(key)` → `(col, slug) | None`. Total over junk, for the same
  reason `normalize_group_slug` is: this is persisted JSON in a hand-editable
  per-user file. Split **once, from the left** (`str.partition`) — column ids are
  `^[a-z0-9_]+$` but a hand-edited `boardgroup` may contain `/`. Slug half goes
  through `normalize_group_slug`, so a parsed key can only name an identity
  `build_column_units` can produce.
- `remap_group_keys(keys, remap=None)` → **sorted list**. `remap` is
  `(col, slug) -> (col, slug) | None`; `None` drops. `remap=None` is the identity
  rule, i.e. pure normalization — which the load path uses, so key hygiene has one
  implementation shared with every lifecycle remap. Sorted because it is the
  persisted form and sorting makes `board_config.local.json` byte-stable.
- `column_remap(mapping)` — the one rule shape with three callers (column rename /
  delete / merge). Slug-half and single-identity rules stay inline at their single
  call sites; a helper per shape with one caller would be speculative.

### 2. `TaskManager` — persistence

- `self.collapsed_groups: set = set()` in `__init__`, beside `self.settings` (`:1168`).
- `_reset_collapsed_groups(keys)` — the only contents-replacement site (see D1); its
  docstring states the rebinding hazard.
- **Load end**, in `load_metadata` after `_prune_orphan_collapsed_columns()`:
  read `settings["collapsed_groups"]`, `isinstance(raw, list)` guard mirroring the
  column sweep, feed through `remap_group_keys(raw)`.
- **Save end**, three extracted helpers so the two save paths cannot drift:
  - `_settings_for_save()` — projects the set to `sorted(...)`, and **`pop`s the key
    when the set is empty** so a collapse→expand round-trip returns the file to its
    original bytes. The only projection site, so no save path can persist a stale list.
  - `_config_layers()` — one `split_config` site, deriving the user layer from
    `_USER_KEYS` rather than hardcoding "settings goes local" a second time.
  - `_write_user_layer(user_data)` — tags failures `MetadataWriteError("local", …)`.
  - `save_settings()` = `_config_layers()` → `_write_user_layer(...)`. No
    `_reconcile_external_columns`, no project write, no `_refresh_known_col_ids`.
  - `save_metadata()` refactored onto the same three helpers; its two-phase contract,
    phase tags and project-first ordering are **unchanged**.
- `is_group_collapsed(col_id, slug)` and `toggle_group_collapsed(col_id, slug) -> bool`
  (returns the new state), the latter saving through `save_settings()`.

### 3. `KanbanApp`

- `__init__` (`:7209-7214`): replace the session-only set with the alias; keep the
  comment block, rewritten to state the aliasing contract.
- `action_toggle_group` (`:10499-10503`): route through `manager.toggle_group_collapsed`,
  wrapped in a **narrow** `except MetadataWriteError` → `notify(..., severity="warning")`.
  The in-memory toggle stands; refusing a view keystroke because a gitignored file is
  unwritable would be worse — but it must not be silent. The recompose and
  `_refocus_group_header` lines are untouched.
- Retrofit all five existing settings-only save sites per the D2 table:
  `toggle_column_collapsed` `:2065`, `action_sort_topic` `:8382`, both type-filter
  dismiss branches `:8411`/`:8419`, and `_handle_settings_result` `:11234`.
- Extend the AST guard in `tests/test_board_columns_reconcile.py`: add `save_metadata`
  to `WATCHED_CALLEES` with `ALLOWED_CALLERS["save_metadata"]` = the **seven**
  project-mutating functions, so a future settings-only caller fails closed. See the
  post-phase block for the closure-attribution caveat and the negative control.

### 4. The lifecycle seam and its six owners

`TaskManager.remap_collapsed_groups(remap)` — in-memory only (every owner already
ends in a save), guarded by `if not self.collapsed_groups: return`.

| Owner | Edit |
|---|---|
| `update_column` `:2038` | after the `collapsed_columns` migration, inside the dormant-but-correct rename branch: `column_remap({col_id: new_id})` |
| `delete_column` `:2080` | after the `collapsed_columns` cleanup, before `save_metadata()`: `column_remap({col_id: UNORDERED_ID})` — the group *survives* the delete, following its members |
| `merge_columns` `:2178` | with the other config removals, keyed on **`drained`**, not `merged` — a partially-merged source still exists and still holds members, so its key is still true; the convergent retry re-points when it finally drains |
| group move (t1243_11) | seam only — `_apply_group_move` calls it *after* the member writes |
| group rename (t1243_12) | seam only |
| group dissolve (t1243_12) | seam only — the rule returns `None` |

`merge_columns` needs a **fourth element in its rollback snapshot**, restored
**in place**: `self.collapsed_groups = before[3]` would orphan every column's
reference, so it must be `self._reset_collapsed_groups(before[3])`. The
`phase == "local"` branch stays unchanged — the merge is durable and
`collapsed_groups` lives in the pending local half, identical treatment to
`collapsed_columns`.

Forward pointers for t1243_11/_12 live in the docstrings of `remap_group_keys` (rule
shapes) and `remap_collapsed_groups` (owner list), plus one line in
`_apply_group_move`'s existing seam docstring. **Nothing is written into their task files.**

### 5. `_prune_orphan_collapsed_groups`, called at the end of `load_tasks()`

Guard `if not self.collapsed_groups or self.unreadable_files: return` — zero cost on
an ungrouped board, and skipped while any task file is unreadable (a failed
`Task.load()` wipes metadata, so membership is invisible; that is the same "cannot
prove it is empty" state `merge_columns` already refuses to act on). Live keys from
**one linear pass** over `task_datas` (parents only) using `task_group_slug` +
`board_col` — the same coercions the renderer uses, so the sweep cannot disagree
with the screen. In-memory only, exactly like the column sweep.

Two boundaries the docstring must state:
- **"No members" is literal.** A group down to exactly **one** member keeps its key —
  `build_column_units` deliberately keeps a single member's slug, so the renderer
  merely stops drawing a header while the key goes inert, not stale. Pruning at one
  would silently discard the user's collapse the first time a sync moved a member out.
- **Column liveness is not a second criterion.** A key naming a vanished column is
  kept while its members still claim it; deriving liveness from one source
  (membership) is what stops two criteria from disagreeing.

### 6. The badge

- `GroupHeader.match_count: int | None = None`; `_label()` appends `f" · {n} match"`;
  `set_match_count(n)` with a no-op guard, mirroring `set_collapsed`'s in-place
  repaint idiom. No pluralisation branch — "2 match" and "1 match" both read.
- `_group_match_count(header, visible, search, child_index)` — per member,
  `task_matches_filter(...)` else `_any_child_matches(...)`, sharing the pass's
  memoized index builder so a pass still builds it at most once.
- `apply_filter` header loop: compute `narrowing = visible is not None or bool(self.search_filter)`
  **once per pass**, then `header.set_match_count(count)` where `count` is set only
  when `narrowing and v and header.collapsed and n < len(header.members)`.
- **Recompose ordering is already guaranteed** — `refresh_column:7975`,
  `refresh_columns:8001` and `refresh_board` all end in
  `call_after_refresh(self.apply_filter[, scope])`, so a fresh badge-less header is
  always re-decided. Not a gap: `_move_needs_recompose` forces a recompose whenever a
  column is grouped, so the DOM-transplant fast path never runs in a column with a header.

### 7. Test-harness prerequisite (blocking — do this first)

`tests/lib/board_fixture.py::PristineTreeMixin` restores `**/*.md` **only**. The
moment `x` persists, `test_board_group_focus.py::GroupCollapseTests::test_collapse_refocuses_the_header_even_when_it_is_not_first`
(`:615`) leaves `c4/beta_grp` in the fixture's `board_config.local.json`, and
`test_toggle_group_invoked_directly_with_a_card_focused_is_inert` (`:650`) then
asserts `set(app.collapsed_groups) == set()` and **fails**. Class order also leaks
collapse state into `GroupFilteringTests`.

The fix already exists unshared: `_PristineConfigMixin` in
`tests/test_board_column_dialog.py:565-589`, whose own docstring calls this a
"harness gap". Promote it to `board_fixture.PristineConfigMixin`, point the dialog
module at the shared copy, and mix it into `_GroupFocusBase`.

### Post-phase (risk mitigations)

**`save-path-drift-guard`** — after the five retrofits land, extend
`tests/test_board_columns_reconcile.py`'s AST scanner so the D2 classification is
enforced rather than merely documented: `save_metadata` joins `WATCHED_CALLEES`,
`ALLOWED_CALLERS["save_metadata"]` lists the seven project-mutating functions, and
the failure message names `save_settings()` as the fix. Attribute each call to its
**outermost** enclosing method (see the D2 closure caveat). Retarget the module's
existing injected-call-site negative control (`:398-406`) to inject a synthetic
settings-only caller **inside a nested closure** — an allowlist that silently matched
everything, or one defeated by closure attribution, would otherwise pass forever.

## Verification

New module `tests/test_board_group_filtering.py`. House style throughout: every
class opens with `test_fixture_facts`, and every positive assertion is paired with a
**discriminating** negative control in the same method.

**Two topologies, both new.** `GROUP_TOPOLOGY` is reused for nothing — it is pinned
by exact-count assertions (`"▾ perf work (2)"`, DOM-unit lists, a positional index)
and carries no metadata that makes `locked`/`free`/`git`/`type` discriminate.
`FILTER_TOPOLOGY` (pilot) is built so `c0/perf_work` has **3 members of which
exactly 2 match** `"zeta"` — one directly, one only through a child — so the count
differs from the member total, from 1, and from 0, killing `len(members)`, a
hardcoded 1, member-only counting and an off-by-one at once. `LIFECYCLE_TOPOLOGY`
(manager) puts the same slug in four columns so a re-point keyed on the slug instead
of the column half fails, and pre-seeds a `perf_work` group in `unordered` so
`delete_column`'s re-point lands on an **existing** identity (a real collision, not a
rename).

| Area | Cases | The control that makes it discriminate |
|---|---|---|
| Collapsed + search | member match; **child-only match with no child card mounted anywhere**; no match hides header *and* reveals the placeholder | the existing child-only test (`:788`) uses an **expanded** group where a mounted `↳` row could carry the decision; the collapsed variant proves the *data* path |
| Base filter / add-ons | `free` hides an all-busy collapsed group while its neighbour stays and the placeholder stays hidden; `locked` inverts both exactly; a busy group rescued by a **free child**; `git`/`type` partial match; **add-on ∩ search** | nothing in the existing suite touches `base_filter` or the add-ons at all; the intersection case fails if `visible` is recomputed per unit instead of composed once |
| Scoped `cols` | scoped pass flips only the named column's header; collapsing under a live filter goes through the real `refresh_column` → `call_after_refresh(apply_filter, {col})` path | scoped × base-filter / × add-on / × child-only are **orthogonal products with no interaction term** — `cols` enters only via the three generators, downstream of both the `visible` composition and the shared index. Not written; said so in the module docstring rather than padded |
| Badge | `render().plain` only, never `match_count`: three distinct counts off one group (`2` / no badge / `1`); child-awareness pinned; `set_collapsed` repaint **preserves** the badge (the trap — it repaints via `_label()`) | a badge held outside `_label()` is silently erased by an unrelated glyph flip |
| Persistence | key lands in the user layer; `"collapsed_groups"` **absent from the whole project file text** (catches nesting under a project key); restart reproduces the collapse while a never-collapsed group comes back **expanded**; hydration before the first compose; junk keys don't crash the board | the expanded control separates "hydration worked" from "everything renders collapsed" |
| No project write | **byte-identity is vacuous** — atomic replace with identical bytes passes it. Three oracles: a call-through spy on `save_project_config`, an unlisted canary key in the project file that any `save_metadata()` destroys, and inode/mtime identity — plus a **positive control** issuing a real project write so a dead oracle cannot pass green forever | the positive control must now be `add_column` / a direct `save_metadata()`, **not** `toggle_column_collapsed` — it no longer writes the project layer (D2) |
| Save-path drift guard | in `tests/test_board_columns_reconcile.py`: every `save_metadata()` caller in `aitask_board.py` is in the project-mutating allowlist | the module's existing injected-call-site control, retargeted — add a synthetic settings-only caller to the parsed AST and assert the guard rejects it. Without that, an allowlist that silently matched everything would pass forever |
| Lifecycle | restart-and-assert for delete / rename / merge; a **refused** merge leaves keys byte-identical; a source that did **not** drain keeps its keys; a failed local write is healed by the next load | the non-drained case separates "iterate `source_ids`" from "iterate `drained`" |
| Coalesce | the asymmetric pair — destination collapsed + arriving **expanded** (an unconditional-adopt impl deletes the key), and arriving collapsed + destination **expanded** (a destination-always-wins impl loses it); vacated key asserted on the **list**, so a duplicate append is visible; the 4-cell table direct | both-collapsed is **not** discriminating — the two readings are indistinguishable when the states are equal |
| Prune | valid key **survives** a fresh manager (the load-order guard for D5 — the one case that catches the whole-list wipe); one member kept vs zero members dropped, differing by exactly one member; `unordered` survives; malformed/non-list tolerated; in-memory until the next save | the one-vs-zero pair is the boundary; any `<2` or off-by-one fails one of them |

**Deliberately not tested, with reasons stated in the module docstring:** the
scoped variants of the base-filter/add-on rows (no interaction term); `inflight` /
`bytopic` / `bytrail` (they mount no `KanbanColumn`, so no `GroupHeader` exists —
such a case would assert on an empty query and pass forever); and a "the seam
exists" test for the t1243_11/_12 owners (asserting a helper this task just wrote is
importable is a tautology — the 4-cell coalesce table states the specification
instead). For the two not-yet-landed owners, two **characterization** cases pin what
the board does today on an *external* rename/move (the stale key is pruned, not
re-pointed onto a wrong identity), with a docstring saying the command path's
expectation becomes "followed" when t1243_11/_12 land.

Run: `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
line for the verdict, and use `set -o pipefail` if piping.

## Risk

### Code-health risk: medium

- The change edits `aitask_board.py`'s save path, load path, three column
  operations and the per-keystroke filter pass — a wide blast radius in an
  11,901-line load-bearing file that grew ~2,900 lines since this plan was written ·
  severity: medium · → mitigation: inline pre-phase `anchor-reverify` (Implementation §0)
- Making `KanbanApp.collapsed_groups` an alias of the manager's set introduces a
  silent-failure mode: any future `self.collapsed_groups = {...}` orphans every
  mounted `KanbanColumn`'s reference and the board renders stale collapse state with
  no error · severity: medium · → mitigation: `_reset_collapsed_groups` is the sole
  contents-replacement site and its docstring states the hazard; the
  `merge_columns` rollback is the one existing site that would have rebound
- Retrofitting **five** existing settings-only save sites reaches beyond this task's
  own feature into settled code — two t1377-era column paths, the type-filter dialog
  and the settings dialog — and three of those five have no test asserting their
  save behaviour today · severity: medium · → mitigation: each is a one-line method
  swap whose correctness is decided by the D2 audit table (does the site mutate a
  project key?), the two affected convergence tests keep their invariant and only
  retarget their gesture, and the new AST guard pins the classification so the audit
  cannot silently rot
- The user-layer-only save skips `_reconcile_external_columns`, so a settings-only
  save no longer merges in columns another process added · severity: low ·
  → mitigation: strictly safer, not riskier — reconciliation exists to stop the
  wholesale project rewrite clobbering those columns, and this path performs no such
  rewrite; the next real `save_metadata()` still reconciles
- `apply_filter` runs on every search keystroke; a counting rule that could not
  short-circuit would put a `_children_by_parent()` walk on that path · severity:
  medium · → mitigation: counting is confined behind `narrowing and v and
  header.collapsed`, and the existing `idle == 0` control in
  `test_child_index_is_built_at_most_once_per_pass` fails if that regresses

### Goal-achievement risk: low

- The task file and its stored plan describe a "Step 1 — unit-level filtering" that
  t1243_9 has already delivered, so implementing them literally would rewrite
  working code · severity: medium · → mitigation: re-verified against source and
  against the parent plan's "LANDED in t1243_9" section; the delta is recorded in
  this plan's Context table
- The task file names **five** lifecycle owners; `merge_columns` is a sixth and two
  of the five are owned by unlanded siblings, so "wire the five transitions" is not
  executable as written · severity: medium · → mitigation: the owner table above
  distinguishes wired-now from seam-only, and the coalesce specification is tested
  directly so t1243_11/_12 inherit a contract rather than a promise
- The stated acceptance check "no project-layer write is ever issued (assert
  `board_config.json` is byte-identical)" cannot fail as written — an atomic replace
  with identical bytes passes it · severity: medium · → mitigation: replaced with a
  spy + canary + inode/mtime triple carrying a live positive control; byte-identity
  is kept only as the weakest third leg
- A "runtime writes only the user layer" rule stated in prose is invisible at the
  call site — both save methods are one line and either appears to work, which is
  precisely how five existing sites drifted onto the wrong one · severity: medium ·
  → mitigation: inline post-phase `save-path-drift-guard` — the rule is enforced by
  an AST allowlist extending the existing `test_board_columns_reconcile.py` scanner,
  so the audit becomes a fail-closed test rather than a fact that was once true

Both confirmed mitigations are **inline** phases of this plan, not spawned tasks:
`anchor-reverify` (Implementation §0, pre-phase) and `save-path-drift-guard`
(Implementation post-phase). No blocking "before" task is needed, so nothing gates
the start of implementation.

## Step 9 (Post-Implementation)

Standard: merge to `main` (current-branch profile — no worktree), run the gate
orchestrator, archive. Upstream observations for the Final Implementation Notes:
the vacuous `if user_data:` guard at `aitask_board.py:1321`;
`tests/lib/board_fixture.py::PristineTreeMixin` restoring only `*.md` (fixed here as
a prerequisite, but a latent harness gap that would have bitten any
config-persisting board test); and the five pre-existing settings-only saves that
had drifted onto `save_metadata()` in violation of `tui_conventions.md:198` — fixed
here, and the reason the drift guard exists.

---

## Final Implementation Notes

- **Actual work done:** All five plan deliverables landed as designed.
  `lib/board_groups.py` gained the pure key algebra (`GROUP_KEY_SEP`,
  `group_key`, `parse_group_key`, `remap_group_keys`, `column_remap`).
  `TaskManager` gained `collapsed_groups` as the single in-memory truth,
  `_reset_collapsed_groups` (the never-rebind guard), the `load_metadata` load
  end, `_settings_for_save` / `_config_layers` / `_write_user_layer` /
  `save_settings`, `is_group_collapsed` / `toggle_group_collapsed`, the
  `remap_collapsed_groups` seam wired into `update_column` / `delete_column` /
  `merge_columns` (incl. the four-element rollback snapshot restored **in
  place**), and `_prune_orphan_collapsed_groups` at the end of `load_tasks()`.
  `KanbanApp.collapsed_groups` became an alias; `action_toggle_group` routes
  through the model behind a narrow `except MetadataWriteError`. `GroupHeader`
  gained `match_count` / `set_match_count`, and `apply_filter` gained
  `_group_match_count` behind a once-per-pass `narrowing` guard. All five
  pre-existing settings-only save sites were retrofitted to `save_settings()`.
  Verification: `tests/test_board_group_filtering.py` (new, 57 tests) plus the
  drift guard in `tests/test_board_columns_reconcile.py`.

- **Deviations from plan:**
  1. **`PristineConfigMixin` was folded into `PristineTreeMixin` rather than
     promoted as a second mixin.** Board config is part of the fixture tree —
     `bf.snapshot()` always treated it that way — and one mixin removes the
     "which do I pick?" decision that produced the duplicate in the first place.
     Restoring is a no-op when nothing changed, and no consumer depended on the
     leak. `test_board_column_dialog.py` keeps `_PristineConfigMixin` as an alias
     so its class still reads as "this one needs config restored".
  2. **The AST guard uses IMMEDIATE-enclosing attribution, not outermost.** The
     plan's caveat was inverted: immediate is the *stricter* rule, because a
     nested `on_dismiss` is flagged under its own (never allow-listed) name,
     whereas outermost attribution would let a nested call inherit its parent
     method's exemption. Recorded in `_callers_of_name`'s docstring.
  3. **`test_destination_key_wins_when_it_already_exists` is labelled a
     specification pin, not a guard.** Under a presence-set representation an
     expanded arriving group has no key at all, so no key-remapping
     implementation can violate that direction; two negative controls leave it
     green. Kept (the design states the rule in two directions) but explicitly
     marked, per the plan's own anti-padding rule.

- **Issues encountered:**
  1. **Two of the first five negative controls PASSED under mutation.** The
     merge control was unreachable: with nothing draining, `merge_columns`
     returns at `if not drained:` *before* the remap, so `drained` vs
     `source_ids` cannot differ. Rewritten as a **partial** merge (c0 drains, c2
     is blocked by a selective write fault), which now fails correctly under the
     mutation. The second was the presence-set case above.
  2. **The retrofit exposed six pre-existing vacuous or gesture-coupled tests.**
     Seven call sites across `test_board_column_manage.py` (2) and
     `test_board_columns_reconcile.py` (5) used `toggle_column_collapsed` purely
     as "now issue a project-layer save". Four failed loudly once it stopped
     writing that layer; **two had been passing either way** — `written()` reads
     the project file from disk, where `bc.create_column` has already written the
     external column, so "the external column survived an ordinary board save"
     passed whether or not the board saved at all. Only its negative control
     carried weight. Retargeted to one canonical `_ReconcileCase.project_save_gesture()`
     (an Edit Column commit — `update_column` with the id unchanged), which
     preserves the original intent that a direct `save_metadata()` call would not
     prove a user-reachable path.
  3. `Task.load_ok` is False only on a genuine read/decode failure; malformed
     YAML still parses to `metadata == {}`. The unreadable-file test needed an
     invalid-UTF-8 payload (`b"\xff\xfe …"`), matching `test_board_column_manage.py`.

- **Key decisions:**
  - **The manager owns the set; the app aliases it.** This removes the sync
    problem rather than managing it — a lifecycle remap has already updated the
    board's rendering source when it returns. The rejected alternative
    (re-seeding inside `refresh_board`) would have lagged a whole modal session,
    because `ColumnManageScreen` refreshes only in `on_closed`.
  - **Counting is a separate function from `_group_header_matches`, sharing the
    same two per-member primitives.** Making visibility `count > 0` would kill
    the short-circuit and put a `_children_by_parent()` walk on the
    per-keystroke path.
  - **The prune is member-based only**, and "no members" is literal: a group at
    exactly one member keeps its key (the renderer stops drawing a header, which
    makes the key inert, not stale). Column liveness is deliberately not a second
    criterion, so two criteria can never disagree.

- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:1321 — the `if user_data:` guard in
    `save_metadata` is vacuous; `data` always carries the `"settings"` key, so
    `split_config` always returns a truthy `user_data` and the local file is
    always written. Harmless today, but it reads as a conditional that can skip
    the local write, which it cannot.
  - `.aitask-scripts/board/aitask_board.py:1329-1334 — the
    `auto_refresh_minutes` property setter has **zero callers**;
    `_handle_settings_result` writes the key through `settings.update()` instead.
    Dead code of the same class as the `Task._BOARD_KEYS` assignment t1243_2
    retired.

- **Notes for sibling tasks:**
  - **`TaskManager.remap_collapsed_groups(remap)` is the ONE seam** for t1243_11
    (group move) and t1243_12 (group rename / dissolve). Ready-made rule shapes
    are in `board_groups.remap_group_keys`'s docstring, and
    `_apply_group_move`'s docstring carries the exact lateral-move call.
  - **Call it AFTER the member writes, in the same synchronous block.** A reload
    between the two would observe the new key with no members and prune it.
  - **Coalescing needs no code.** The remap is a set union, so a move or a
    confirmed rename onto an existing same-slug group combines automatically;
    the vacated key is dropped by the rewrite. This holds *only* because the key
    carries no value — a future value-carrying view key must revisit it.
  - **Never rebind `collapsed_groups`.** `KanbanApp` and every mounted
    `KanbanColumn` alias the manager's set; replace contents via
    `_reset_collapsed_groups`, never `self.collapsed_groups = {...}`.
  - **Use `save_settings()` for anything confined to `self.settings`.** The AST
    guard in `tests/test_board_columns_reconcile.py::SavePathContainmentTests`
    fails the build otherwise, and names the remedy in its message.
  - **`GroupHeader.members` staleness is still untested** (t1243_9's note stands):
    the board has no `boardgroup` write path until t1243_11/_12, so a header can
    only go stale once one of them lands. **Whichever lands first owes that test.**
  - **`t1377_4`'s `merge_columns` is wired**; the collapse-key lifecycle table in
    the parent plan now has six owners, three live and three seams.
