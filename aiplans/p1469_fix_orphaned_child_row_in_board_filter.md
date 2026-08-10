---
Task: t1469_fix_orphaned_child_row_in_board_filter.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1469 — Fix the orphaned child row in the board filter

## Context

`KanbanApp.apply_filter` (`.aitask-scripts/board/aitask_board.py:8032`) decides
each mounted card's visibility from that card's **own** data.
`Task.search_haystack` (`:238`) is `"<filename> <metadata>".lower()`, and a
parent's metadata never contains its children's text — so a filter that matches
only a child hides the parent card while leaving the child card visible. An
expanded child lives inside a `Horizontal(classes="child-wrapper")` next to a
`"↳"` connector Static, so the result renders as a bare `↳ t<parent>_<n> …`
row under nothing.

The same shape occurs for every filter dimension, not only search: the base sets
(`_free_visible_set`, `_git_visible_set`, `_type_visible_set`) are computed
per task, so a parent excluded from the set while a child stays in it produces
the identical orphan row.

t1243_9 fixed only the *group* consequence — `_group_header_matches` (`:8004`)
already makes a `GroupHeader` visible when a member **or a member's child**
matches, so a header is never hidden above a visible child row. The ungrouped
parent-card case was deliberately left alone; this task closes it, and unifies
the two rules onto one primitive so they can no longer diverge.

**Decided direction (confirmed with the user):** Option 2 — *show the parent* —
applied with the **full predicate**. A parent card is visible when it matches
itself **or** when any of its children passes the whole active filter (base set
∩ add-ons ∩ search). A matching child therefore re-admits its parent whatever
hid the parent. This is deliberately wider than the search-only variant: it
makes "a visible `↳` row always has a visible parent above it" a theorem of the
standard column view rather than a search-specific patch, at the cost of a
base-filter behaviour change recorded under Risk below.

## Implementation

### Pre-phase (risk mitigations)

1. `[guard_child_index_key_agreement]` In
   `tests/test_board_render_scoping.py`'s new class, add
   `test_parent_key_derivations_agree`: for every child in
   `app.manager.child_task_datas`, assert
   `app.manager.get_parent_num_for_child(child)` equals
   `TaskCard._parse_filename(<that child's parent filename>)[0]`, and assert the
   set of keys `_children_by_parent()` produces is a subset of the parent-num
   set derived from `app.manager.task_datas` filenames. Rationale: the index is
   keyed by the child filepath's **directory name** and looked up by a
   **filename regex** on the parent — two independent derivations. If they
   diverge, `_any_child_matches` returns `False` for every parent, the orphan
   bug returns, and nothing fails. Control: assert the fixture yields ≥1 key, so
   a vacuous empty-index pass cannot satisfy the test.

### 1. `.aitask-scripts/board/aitask_board.py` — new shared primitive

Add `_any_child_matches` next to `_children_by_parent` (`:7983`):

```python
    def _any_child_matches(self, task, visible, search: str,
                           child_index) -> bool:
        """Whether ANY child of `task` passes the filter (t1469).

        THE single child-aware primitive: the group-header rule
        (`_group_header_matches`) and the parent-card rule (`apply_filter`'s
        unit loop) are both "matches itself OR this returns True", so a change
        here moves them together instead of letting them diverge — which is
        exactly how the ungrouped case was left broken when t1243_9 fixed the
        header.

        The FULL `task_matches_filter` predicate is applied to the child — base
        set AND search, not search alone. A parent is therefore re-admitted only
        by a child the current view would actually show, which is what makes
        "a visible `↳` row always has a visible parent above it" hold for every
        filter dimension rather than for search alone.

        `child_index` is the per-pass `_children_by_parent()` map. The empty-map
        fast path is what keeps a childless board from paying a filename parse
        per card on the per-keystroke path.
        """
        if not child_index:
            return False
        num, _ = TaskCard._parse_filename(task.filename)
        if not num:
            return False
        return any(task_matches_filter(c, visible, search)
                   for c in child_index.get(num, ()))
```

`_children_by_parent` keys by `get_parent_num_for_child` (`:1462`, the child
filepath's parent directory name, e.g. `"t9000"`) and
`TaskCard._parse_filename` (`lib/topic_semantics.py:18`) yields the same form
for a parent filename — the pairing `_group_header_matches` already relies on.
A file whose name does not parse (`t_unparseable.md`) yields `""` and is
short-circuited.

### 2. `_group_header_matches` — delegate its child phase

Replace the inline child loop (`:8025-8029`) with a call to
`_any_child_matches`, keeping the existing two-phase order (all members' own
match first, then the child lookups) so the docstring's short-circuit claim
stays true. Update the docstring to name `_any_child_matches` as the shared
rule and to state that the parent-card rule now uses the same primitive.

### 3. `apply_filter` — rescue the parent card, build the index lazily

In the unit loop (`:8062`):

```python
        # `_children_by_parent()` is built AT MOST ONCE per pass and only when a
        # decision needs it: a unit that matched its own corpus never reaches a
        # child lookup, so a board with no filter active still pays nothing.
        index_cache = []

        def child_index():
            if not index_cache:
                index_cache.append(self._children_by_parent())
            return index_cache[0]

        cols_with_visible = set()
        for unit in self._filter_units(cols):
            v = task_matches_filter(unit.task_data, visible, self.search_filter)
            if not v and not getattr(unit, "is_child", False):
                v = self._any_child_matches(unit.task_data, visible,
                                            self.search_filter, child_index())
            set_unit_display(unit, v)
            if v:
                cols_with_visible.add(unit.column_id)
```

`getattr(unit, "is_child", False)` matches `set_unit_display`'s idiom, so a
future non-`TaskCard` unit needs no branch added here. A child unit is never
rescued: children have no children, and in By-Topic / By-Trail child tasks
mount as ordinary top-level cards.

State the invariant's **scope** in the `apply_filter` docstring, because the
rule is board-wide but the guarantee it buys is not: what becomes derivable is
*a visible `.child-wrapper` row always has a visible parent card above it*, and
that row shape exists only in `KanbanColumn.task_block` (`:3519`). By-Topic and
By-Trail render a child as a top-level card whose parent may not be in the lane
or wave at all — the rescue still shows a parent that IS mounted there, but no
parent-visibility invariant is claimed for those views.

The header loop then calls `child_index()` instead of the current
`self._children_by_parent() if headers else {}` line (`:8078`) — the same map,
already built by the unit loop in the common case. Update the comment above it,
which currently claims the block "is free until then" for ungrouped boards.

Extend `apply_filter`'s docstring with the parent-card rule and the fact that a
matching child overrides **every** dimension, base filters included.

### 4. Docstring cross-references for the widened rule

`_free_visible_set` (`:8137`) documents "Parents: shown only when the parent
itself is not busy AND no child is busy" — still true of the *set*, no longer
true of what renders. Add one line to each of `_locked_visible_set`,
`_free_visible_set`, `_git_visible_set` and `_type_visible_set` noting that
`apply_filter`'s child-aware rule can re-admit a parent this set excludes when
one of its children is in the set, with a pointer to `_any_child_matches`.

### 5. `tests/test_board_render_scoping.py` — new coverage

New class `ChildAwareParentFilterTests(bf.FixtureBoardTestBase, _PristineTreeMixin,
unittest.TestCase)` on `bf.DEFAULT_TOPOLOGY` (parent `t9000_parent.md` with
children `t9000_1_childone.md` / `t9000_2_childtwo.md`, and **no** group
headers — the point is that the fix is independent of groups):

1. `test_fixture_facts` — `"childone"` is absent from the parent's
   `search_haystack` and present in the child's; with
   `app.expanded_tasks.add("t9000_parent.md")` before `run_test`, the child card
   and its `.child-wrapper` are mounted. Without this the cases below stop
   discriminating.
2. `test_child_only_search_shows_the_parent` — search `"childone"`: the child
   card, its wrapper and the **parent card** are all `display != "none"`.
   Negative control in the same case: `"zzz_no_such_task_zzz"` hides all three
   (so the positive assertions are not vacuous).
3. `test_child_match_rescues_a_parent_across_every_filter_dimension` — pins the
   full-predicate half over **all four** dimensions, not just Free, since the
   rescue's whole claim is that it reads the composed `visible` set rather than
   any one filter. One compact `subTest`-parameterized case; every setup makes
   the **child** qualify and the **parent** not, each paired with a control
   that revokes the child's qualification and re-asserts the parent is hidden.
   All fixture tasks default to `issue_type: chore` and carry no `issue:`
   (`tests/lib/board_fixture.py:162`), so the parent side needs no setup —
   mutate the child's in-memory metadata only, and call
   `_invalidate_search_haystack()` after each mutation so no stale memo can be
   read if a case later adds a search term.

   | case | setup (child `t9000_1_childone.md`) | why the parent is excluded |
   |---|---|---|
   | `free` | parent `status = "Implementing"` | `_free_visible_set` skips a busy parent; the free child is in the set |
   | `git` | `metadata["issue"] = "https://example.invalid/issues/9"`, `app.git_filter_active = True` | `_git_visible_set` selects on `issue:`/`pull_request:`; the parent carries neither |
   | `type` | `metadata["issue_type"] = "bug"`, `settings["filter_issue_types"] = ["bug"]`, `app.type_filter_active = True` | `_type_visible_set` selects `bug`; the parent is `chore` |
   | `git ∩ type` | both of the above, both add-ons active | the parent fails both; the child passes the intersection |

   Assertion per case: the parent card is `display != "none"`. Control per case:
   revoke the child's qualification (clear `issue`, reset `issue_type`, or mark
   the child `Implementing` for the free case) → parent hidden.

   Plus the **sharp intersection control**, which is what proves the rescue
   consults the composed set and not merely one dimension: give the child the
   `issue:` but leave its `issue_type` as `chore` with both add-ons active and
   `filter_issue_types = ["bug"]`. The child now passes Git and fails Type, so
   `visible` excludes it — the child card AND the parent card must both be
   hidden. A rescue that tested any single dimension would show the parent here.
4. `test_no_visible_child_wrapper_without_a_visible_parent` — the invariant,
   swept rather than point-asserted: over a matrix of filter states
   (`""`, `"childone"`, `"childtwo"`, `"zzz…"`, and `base_filter` in
   `all`/`free`), assert for every visible `.child-wrapper` in the DOM that the
   parent `TaskCard` of that column above it is visible. Control: temporarily
   monkeypatch `KanbanApp._any_child_matches` to `lambda *a, **k: False` and
   assert the sweep now finds an orphan — a sweep that passes against the
   pre-fix behaviour proves nothing.
0. `test_parent_key_derivations_agree` — the pre-phase mitigation step above;
   written first, since it guards the primitive the rest of the class exercises.
5. `test_child_index_is_built_at_most_once_per_pass` — spy on
   `_children_by_parent` (same `mock.patch.object` shape as
   `test_board_group_focus.py:204`): one build for a `"zzz…"` whole-board pass,
   two after a second pass (control against a dead spy), and **zero** for a pass
   with no filter active, where every card matches its own corpus.

### 6. `tests/test_board_group_focus.py` — retarget two controls

Both are behaviour changes this task intends, not regressions.

- `test_child_only_match_keeps_the_header_visible` (`:782`): the control
  `assertEqual(seen["parent"], "none")` (`:804-806`) inverts to
  `assertNotEqual(..., "none")`. Rewrite the docstring: the header's
  child-awareness is now the *same* rule as the card's, and the precondition
  that keeps the case discriminating is `test_fixture_facts`' corpus assertion
  (`:747`), not the hidden parent. The header assertion (`:807`) and the child
  assertion (`:803`) are unchanged.
- `test_child_index_is_built_once_per_pass_and_not_at_all_without_headers`
  (`:849`): rename to `test_child_index_is_built_at_most_once_per_pass`. Its
  `seen["no_headers"] == 0` control (`:880`) no longer holds — the still-active
  `"zzz…"` search makes c3's three parent cards reach a child lookup. Retarget
  the control to a pass with the search **cleared**, where nothing needs the
  index, so "not always built" is still pinned. `one_pass == 1` /
  `two_passes == 2` (`:875`, `:877`) are unchanged and now also pin that the
  unit loop and the header loop share one build.

Also update `test_fixture_facts`' docstring (`:730`) — the corpus fact is now
the precondition for both rules.

### 7. `website/content/docs/tuis/board/how-to.md`

Line 138 ("matches against both the task filename and the entire metadata
dictionary") and the view-mode note at line 140/193 gain one sentence: a parent
card also stays visible when one of its child tasks matches the active filter,
so an expanded child row is never left dangling under a hidden parent.

**Scope the wording deliberately.** Do *not* write "a matching child is never
shown without its parent" — that is broader than the implementation
guarantees. The invariant holds for the standard column view, where a child row
is mounted inside a `.child-wrapper` directly under its parent card
(`KanbanColumn.task_block`, `:3519`). By-Topic and By-Trail mount child tasks as
ordinary top-level cards with no parent nesting, and a child can be in a lane or
wave whose parent card is not rendered at all — there is no orphan row to fix
there and no parent-visibility invariant to claim.

### Post-phase (risk mitigations)

1. `[manual_verify_free_view_widening]` Run **two** distinct Free-view states on
   the live board and record both outcomes in the Final Implementation Notes.
   They are different shapes — a busy *child* never makes its parent busy, it
   only removes an otherwise-free parent through the `_free_visible_set`
   cascade — and only the first is the questionable one.

   - **State A (the one the risk is about): parent `Implementing`, both children
     `Ready`.** Expand the parent, press `f`. `_free_visible_set` excludes the
     parent because *the parent itself is busy*, and includes both children;
     the new rule re-admits it via a matching child. Expected: a genuinely busy
     parent card renders in a view whose stated purpose is "what is free to
     pick". Judge whether that reads as useful context or as a filter leak.
   - **State B: parent `Ready`, one child `Implementing`, one child `Ready`.**
     Expand the parent, press `f`. Here the parent is excluded only by the
     cascade ("no child is busy"), and the free child re-admits it. Expected:
     the free parent renders above its free child, with the busy child hidden —
     and no bare `↳` row, which is the defect this task exists to remove.

   If State A reads as a leak, say so in the notes — that is the signal to
   reconsider the full-predicate choice in favour of the search-only variant.
   The decision belongs to the user, not to a silent narrowing during
   implementation.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` for the board modules —
  in practice run at minimum `test_board_render_scoping.py`,
  `test_board_group_focus.py`, `test_board_view_filter.py`,
  `test_board_topic_view.py`, `test_board_empty_column_focus.py`,
  `test_board_work_report.py`, `test_board_dom_transplant.py`,
  `test_board_marking.py`, then the whole Python suite. Read only the last
  line for the verdict.
- Expected-green-unchanged (surveyed, do not "fix" them if they fail — a
  failure there means the rule is wider than designed):
  `test_board_render_scoping.py::test_search_still_hides_non_matching_cards`
  (search `"t9003"`; neither child of `t9000` contains that token),
  `test_board_view_filter.py`'s `visible_live.issubset(expected)` (`:126` — the
  only busy fixture task, `t9001_alpha`, has no children, so no rescue fires),
  `test_board_empty_column_focus.py::test_hidden_child_cards_hide_their_connector_wrapper`,
  `test_board_work_report.py::test_hidden_cards_still_listed` (`:479`).
- Negative control for the fix itself: item 5.4 above — with
  `_any_child_matches` stubbed to `False` the swept invariant must FAIL.
- `python3 -m pytest tests/test_board_render_scoping.py -v` for the new class in
  isolation while iterating.
- Live check on the real board (`ait board`): expand a parent with children,
  type a token that only a child carries — the parent card stays, no bare `↳`
  row appears. Then run both states of the `manual_verify_free_view_widening`
  post-phase step and record their outcomes in the Final Implementation Notes.

## Post-implementation

Step 9 (Post-Implementation) handles the merge to `main`, the `risk_evaluated`
gate, and archival of the task and this plan.

## Risk

### Code-health risk: medium
- `apply_filter` is the per-keystroke hot path; the change adds a lazily-built
  `O(children)` index plus, per parent card that fails its own match, one
  filename parse and a bounded child scan. Each child is scanned at most once
  per pass, so the pass stays `O(cards + children)` — but the "ungrouped boards
  pay nothing" property pinned by `test_board_group_focus.py:880` is
  deliberately given up. · severity: medium · → mitigation: none confirmed
  (the `bench_filter_keystroke_cost` candidate was declined)
- The child lookup is keyed by two independent derivations of a parent number —
  `get_parent_num_for_child` (the child's directory name) on the index side,
  `TaskCard._parse_filename` (a filename regex) on the lookup side. A
  divergence fails **open**: `_any_child_matches` returns `False` for every
  parent, the orphan row comes back, and no test notices. · severity: medium ·
  → mitigation: inline pre-phase guard_child_index_key_agreement
- The full-predicate rule makes four documented helpers
  (`_locked_visible_set` / `_free_visible_set` / `_git_visible_set` /
  `_type_visible_set`) no longer the sole authority on what renders: a parent
  they exclude can be re-admitted by a matching child. Free view will start
  showing a busy parent whenever any of its children is free — including
  collapsed parents, where no orphan row existed to justify it. Implementation
  step 4 documents this at each site, but it is a real behaviour change with no
  test outside this task pinning the old reading. · severity: medium ·
  → mitigation: inline post-phase manual_verify_free_view_widening

### Goal-achievement risk: low
- The rule makes "a visible `.child-wrapper` row ⇒ a visible parent card above
  it" derivable **for the standard column view** (a visible child satisfies
  `task_matches_filter`, which is exactly what `_any_child_matches` tests), and
  the scoped-pass case is safe because a parent and its children always share a
  column. By-Topic / By-Trail are out of scope by construction — they mount no
  child rows. The remaining exposure is that
  the widened base-filter behaviour is later judged a regression and reverted
  toward the search-only variant. · severity: low · → mitigation: none confirmed

### Planned mitigations
- timing: pre-phase | name: guard_child_index_key_agreement | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — silent fail-open if the two parent-key derivations diverge | desc: unit-test that `_children_by_parent`'s keys and `TaskCard._parse_filename`'s parent-num agree, with a non-vacuous key-count control
- timing: post-phase | name: manual_verify_free_view_widening | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — Free view now shows a busy parent above its free children | desc: run the Free-view case explicitly on the live board and record in the Final Implementation Notes whether the widened view reads as context or as a filter leak

**Post-inline reassessment.** Re-run against the augmented plan: the pre-phase
guard closes the fail-open bullet and the post-phase check puts a human eye on
the widened Free view, but the hot-path-cost bullet is unmitigated and the four
helpers' widened contract still lands. Levels are unchanged — code-health
**medium**, goal-achievement **low**.

**Declined:** `bench_filter_keystroke_cost` (spawn 'before'; a within-run
ablation of the added `apply_filter` cost) — dropped by the user, leaving the
hot-path bullet carried rather than measured.
