---
priority: medium
effort: low
depends: []
issue_type: bug
status: Folded
labels: [documentation, website]
gates: [risk_evaluated]
folded_into: 1770
anchor: 1661
followup_kind: upstream_defect
created_at: 2026-09-10 15:52
updated_at: 2026-09-10 16:14
---

## Origin

Spawned from t1768 during Step 8b review (the user chose to create it).

**Overlap, stated up front:** the two open defects below are **already owned by
t1770** (`harden_check_link_relevance_self_verification`, `Ready` when this was
written), whose body describes both with suggested fixes. The third was fixed in
t1768. Before doing any work here, check t1770's state:

- if t1770 has landed, verify both defects are gone at the lines named below
  (they move with edits) and close this task;
- if t1770 is still open, fold this task into it, or coordinate so the fix lands
  once — do not implement it twice.

## Upstream defect

- `website/check_link_relevance.py:642-643` — `--report` returns before
  `evaluate_controls()` (`:671`), so report mode never evaluates or prints a
  self-control and exits 0 even when one would fail. **Already owned by t1770**
  (verified against the tree; t1768 sent it a coordination note).
- `tests/test_check_link_relevance.py:865` — `if __name__ == "__main__":
  unittest.main()` sits above later test classes, so direct execution silently
  runs a subset (55 of the module's 70 tests). **Already owned by t1770.**
- `website/README.md` / `website/check_link_relevance.py` docstring — both
  claimed "roughly seven internal links in ten" carry a backticked token;
  measured 388 of 1034 (37%). **Fixed in t1768** (both now point at the run's
  `links checked` line).

Line numbers are as of t1768's code commit `2f023c594`.

## Diagnostic context

t1768 evaluated whether the relevance heuristic could fold into `check_links.py`
(no) and whether coverage should widen past backtick-quoted link text (no), and
added a `subject-of-page` label plus `website/check_link_relevance_history.py`.
The `--report` defect matters to that harness only indirectly: the harness
replays through `scan()` plus `ENGINE_CONTROLS` and never calls `main()` or
`--report`, precisely so that making `--report` fail closed cannot drop the
history records that exist only in trees older than the corpus-control pages.
Keep `scan()` free of control evaluation when fixing it.

t1768 placed its new test classes **above** the stranded guard, with a comment
naming t1770, so they are collected under both entry points whichever task lands
first. Moving the guard to the physical end of the module keeps them collected.

## Suggested fix

As in t1770: evaluate controls before the `--report` return and suppress only
their display; move the `unittest.main()` guard to the end of the module and
assert the direct-run and discovery counts agree.
