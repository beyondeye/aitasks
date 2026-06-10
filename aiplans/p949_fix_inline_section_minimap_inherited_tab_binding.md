---
Task: t949_fix_inline_section_minimap_inherited_tab_binding.md
Worktree: (current branch — profile 'fast')
Branch: (current branch — profile 'fast')
Base branch: main
---

# Plan: Fix `_InlineSectionMinimap` inherited Tab-binding (t949)

## Context

`_InlineSectionMinimap` (`.aitask-scripts/brainstorm/brainstorm_app.py:887`)
documents itself as "no Tab binding" and sets `BINDINGS = []` on its lazily-built
`_NoTabMinimap(SectionMinimap)` subclass. But Textual **merges** `BINDINGS` across
the MRO, so the empty list adds nothing and removes nothing — the subclass still
inherits `SectionMinimap`'s `tab → toggle_focus` *priority* binding
(`.aitask-scripts/lib/section_viewer.py:276`). The docstring claim is therefore
false.

The defect is **latent, not active**: the class's only consumer,
`NodeDetailModal`, declares its own screen-level priority binding
`Binding("tab", "focus_minimap", ..., priority=True)`
(`brainstorm_app.py:1149`), which owns Tab inside that modal. Priority bindings
resolve screen-before-widget, and `action_focus_minimap` is a no-op when focus is
already on the minimap — so the inherited `toggle_focus` never visibly fires.

**Conclusion (verified by MRO inspection):** `_NoTabMinimap` is bind-for-bind
identical to stock `SectionMinimap` (the merge makes the two binding sets equal),
and even if `BINDINGS=[]` worked, the screen-level binding already masks Tab. The
class is pure dead complexity wrapping a false docstring. The cleanest fix is to
**drop it** and have `NodeDetailModal` use stock `SectionMinimap` directly —
provably behavior-neutral.

This was spawned from t945_3, which fixed the analogous live bug on the
proposal-preview pane by adding `_PreviewMinimap` (which *overrides* the Tab keys
rather than clearing the list). `_PreviewMinimap` is correct and stays as-is.

## Approach (recommended: drop the dead class)

### 1. `.aitask-scripts/brainstorm/brainstorm_app.py` — delete `_InlineSectionMinimap`

Remove the entire class (lines 887–910), i.e. from `class _InlineSectionMinimap:`
through its `return cls._cache`, leaving `_PreviewMinimap` (the next class)
intact.

### 2. `brainstorm_app.py` — point `NodeDetailModal.compose` at stock `SectionMinimap`

`compose()` already lazily imports from `section_viewer` at line 1164:

```python
from section_viewer import SectionAwareMarkdown
```

Change it to also import `SectionMinimap` (keeps the import lazy, matching the
existing pattern — no new module-level import):

```python
from section_viewer import SectionAwareMarkdown, SectionMinimap
```

Then replace the two call sites (lines 1177 and 1183):

```python
yield _InlineSectionMinimap.cls()(
    id="proposal_minimap", classes="node_detail_minimap"
)
# ...
yield _InlineSectionMinimap.cls()(
    id="plan_minimap", classes="node_detail_minimap"
)
```

with:

```python
yield SectionMinimap(
    id="proposal_minimap", classes="node_detail_minimap"
)
# ...
yield SectionMinimap(
    id="plan_minimap", classes="node_detail_minimap"
)
```

`SectionMinimap.__init__` accepts `compact=True` by default and `**kwargs`
(`id`, `classes`), so the call signature is satisfied. All behavior used by
`NodeDetailModal` (`focus_first_row`, `populate`, `display`, `SectionRow`
children, `SectionSelected`/`ToggleFocus` messages) lives on the base class.

### 3. `tests/test_brainstorm_node_detail_minimap.py` — refresh stale docstring

The module docstring (line 5) names `_InlineSectionMinimap` in prose. Update that
reference to `SectionMinimap` so it doesn't dangle after the class is removed.
The test bodies query `#proposal_minimap`/`#plan_minimap` by id and assert on
`SectionRow` children + `.display` — all base-class behavior — so no test logic
changes are needed.

## Why not the "fix the docstring / override the key" alternative

Keeping `_InlineSectionMinimap` and genuinely neutralizing Tab (e.g. overriding
the key to a no-op) would retain a class whose entire job is to suppress a binding
that is *already* masked by the screen — complexity for zero functional gain.
Dropping the class removes the misleading code outright and is the smaller diff.

## Risk

### Code-health risk: low
- Change is behavior-neutral by construction (`_NoTabMinimap` ≡ `SectionMinimap`
  after MRO merge) and confined to one TUI modal's compose + one stale test
  docstring · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- Goal is precisely "remove the false-docstring / latent inherited binding"; the
  plan deletes the offending class entirely, which fully satisfies it. The only
  open verification is confirming NodeDetailModal's Tab/minimap behavior is
  unchanged, covered below · severity: low · → mitigation: none needed

## Verification

1. **Existing pilot tests pass** (cover minimap rows, hide-when-no-sections,
   section-select delegation):
   ```bash
   python3 tests/test_brainstorm_node_detail_minimap.py
   ```
2. **No dangling references:**
   ```bash
   grep -rn "_InlineSectionMinimap\|_NoTabMinimap" .aitask-scripts/ tests/
   ```
   (expected: no matches)
3. **Manual (optional):** Launch `ait brainstorm`, open a node detail modal
   (Enter on a node), switch to the Proposal/Plan tab, press Tab → focus moves
   into the minimap; arrow through rows, Enter scrolls content; Tab again stays
   on the minimap (no jump) — identical to current behavior.

## Step 9 (Post-Implementation)

Per the shared task-workflow: review/commit (Step 8), then archive via
`./.aitask-scripts/aitask_archive.sh 949` and `./ait git push` (Step 9). Working
on the current branch (profile 'fast'), so no worktree/branch cleanup.

## Final Implementation Notes

- **Actual work done:** Exactly as planned. Deleted the `_InlineSectionMinimap`
  class from `.aitask-scripts/brainstorm/brainstorm_app.py`; switched
  `NodeDetailModal.compose` to import `SectionMinimap` alongside the existing lazy
  `SectionAwareMarkdown` import and yield stock `SectionMinimap(...)` at the two
  call sites (`#proposal_minimap`, `#plan_minimap`); refreshed the stale
  `_InlineSectionMinimap` prose reference in
  `tests/test_brainstorm_node_detail_minimap.py`'s module docstring. Net diff:
  −28 lines.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Chose the "drop the dead class" option over "fix the
  docstring / override the key". The change is behavior-neutral by construction:
  Textual merges `BINDINGS` across the MRO, so `_NoTabMinimap(SectionMinimap)`
  with `BINDINGS = []` was already bind-for-bind identical to stock
  `SectionMinimap` — and `NodeDetailModal`'s screen-level priority
  `tab → focus_minimap` binding owns Tab regardless. The class was pure dead
  complexity wrapping a false "no Tab binding" docstring; removing it is the
  smaller, honest diff.
- **Upstream defects identified:** None.
- **Verification performed:** All 3 pilot tests in
  `tests/test_brainstorm_node_detail_minimap.py` pass; `py_compile` of
  `brainstorm_app.py` succeeds; `grep` for `_InlineSectionMinimap`/`_NoTabMinimap`
  across `.aitask-scripts/` and `tests/` returns no matches.
