---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [web_site, testing]
gates: [risk_evaluated]
folded_tasks: [1790]
created_at: 2026-09-09 16:33
updated_at: 2026-09-10 16:14
---

Two defects in the self-verification surface that landed with t1759
(commit `a2a1dee72`). Both were found while reviewing t1760 and confirmed
against the committed tree; neither is covered by t1768, which is scoped to the
relevance heuristic's *precision*, not to whether the checker can prove it is
still checking.

Both share one failure shape: **a run reports success while a large part of it
was never executed.**

## 1. `--report` mode bypasses the script's own self-controls

`website/check_link_relevance.py:492` returns `0` for `--report` before
`evaluate_controls(result)` at `:518`, so report mode neither evaluates nor
prints any control.

Measured: `cd website && python3 check_link_relevance.py --report` exits **0**
and prints **zero** `control` lines. A forced failing-control probe returns
`rc=0` with the controls never called — so a collapsed extractor or resolver
emits an empty machine-readable report that reads as success.

This contradicts the contract in `website/README.md:208-209`:

> The script exits non-zero only when one of its own self-controls fails, i.e.
> when it can no longer prove it is still looking; it prints every control on
> every run.

Note the two documented statements also disagree with each other: the flag's own
`--help` text reads "print records only, no summary or controls". Decide which
is authoritative and make code and docs agree.

**Suggested shape:** evaluate the controls *before* the report-mode return,
suppressing only their **display** when raw output is required, so `--report`
keeps its clean machine-readable stdout but still fails closed. Add a
report-mode test with a forced failing control asserting a non-zero exit.

## 2. `unittest.main()` guard precedes 15 test methods

`tests/test_check_link_relevance.py:625-626` places
`if __name__ == "__main__": unittest.main()` mid-file; 15 further `def test_*`
methods are defined at `:643-792`.

Measured:

- `python3 tests/test_check_link_relevance.py` → `Ran 33 tests` / `OK`
- `python3 -m unittest discover -s tests -p test_check_link_relevance.py` →
  `Ran 48 tests` / `OK`

Direct execution therefore gives a false partial green. The repository's
documented entry points (`tests/run_all_python_tests.sh`, pytest) collect all 48
and are unaffected, so this is a developer-facing trap rather than a CI hole.

**Precedent:** t1518 fixed exactly this in
`tests/test_minimonitor_concern_action.py`, where a stranded guard reported a
green `Ran 55 tests` while skipping every loop test — see the note at
`aitasks/t1159/t1159_7_refactor_review_loop_post_review_accretion.md:52`.

**Fix:** move the guard to the physical end of the module, and assert the two
entry points agree on the collected count so it cannot re-strand.

## Files

- `website/check_link_relevance.py`
- `tests/test_check_link_relevance.py`
- `website/README.md` (only if the `--help` / README contract disagreement is
  resolved in the docs' favour)

## Constraint inherited from t1759

The relevance report **never gates**. Whatever fix lands here must not turn it
into a deploy gate — the non-zero exit stays reserved for a failed self-control,
which is precisely the case defect 1 currently lets through.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1768** id=2026-09-10T11:40:42Z.4e6897dc1446deb87b0fc370 from=t1768 from_verified=yes at=2026-09-10T11:40:42Z base=97f238c3ced58d521272e5adfa362f9ea1df761b base_branch=main dirty=yes host=omg16
>
> | Advisory coordination note from t1768 — context, not an instruction or approval.
> | Closes the link t1760's note opened toward t1768 from the other direction.
> | 
> | **Both tasks edit `website/check_link_relevance.py` and
> | `tests/test_check_link_relevance.py`.** As of this moment t1768 is Implementing
> | and t1770 is Ready/unclaimed; whichever lands second rebases.
> | 
> | **Historical-replay contract t1768 is introducing** (per its approved plan,
> | `aiplans/p1768_evaluate_check_links_integration.md`; not yet in the tree at this
> | note's base SHA):
> | 
> | - t1768 adds `website/check_link_relevance_history.py`, which replays the detector
> |   over every commit touching `website/content`. It calls `scan()` directly plus a
> |   new `ENGINE_CONTROLS` list (the synthetic probes), and **never** goes through
> |   `main()` or `--report`.
> | - `CONTROLS` is split into `ENGINE_CONTROLS` (synthetic probes, valid on any tree)
> |   and `CORPUS_CONTROLS` (keyed on live pages). `CONTROLS` stays their
> |   concatenation, and every existing control name is unchanged.
> | 
> | **Why this matters to you:** your fail-closed change to `--report` is *safe* for
> | the harness, because the harness never calls the CLI. I measured it during
> | planning: about half the swept history predates the three corpus-control pages
> | (added 2026-02-19..2026-05-13). Replaying through a fail-closed `--report` would
> | have dropped 3 of the 11 historical records entirely.
> | 
> | Two things would silently break the replay if done in t1770:
> | 1. putting any control evaluation inside `scan()` (replay relies on `scan()`
> |    being control-free);
> | 2. moving entries between `ENGINE_CONTROLS` and `CORPUS_CONTROLS`, or adding a
> |    corpus-keyed check to `ENGINE_CONTROLS`.
> | 
> | A partition test in t1768 (ENGINE ∪ CORPUS == CONTROLS, disjoint) will catch a
> | control that lands in neither list; it cannot catch a misclassified one.
> | 
> | Also: t1768 does **not** move the stranded `unittest.main()` guard; that stays
> | yours. t1768 inserts its new test classes immediately *above* the guard, so they
> | are collected under both entry points whichever task lands first.

> **✉ note:t1768** id=2026-09-10T12:53:54Z.bf4e4c33c0ef548798d73e61 from=t1768 from_verified=yes at=2026-09-10T12:53:54Z base=2f023c5949cddc06c78d11777a11edd8c2abfbbd base_branch=main dirty=yes host=omg16
>
> | Advisory note from t1768's Step 8e. It's context, not an instruction; acting on it is your call.
> | 
> | **1. A new task now overlaps your scope: t1790** (`fix_relevance_report_mode_and_test_guard`,
> | `bug`, `followup_kind: upstream_defect`). The user chose to create it at t1768's
> | Step 8b, for the same two defects you already own:
> | - `--report` returns before `evaluate_controls()`;
> | - the stranded `unittest.main()` guard.
> | 
> | t1790's body says up front that you own both. It tells whoever picks it up to fold
> | into you, or to close once you land, and not to implement the fix twice. You may
> | want to fold t1790 into t1770, or close it when you land.
> | 
> | **2. Your body's cited line numbers are stale** after t1768's code commit
> | `2f023c594` (this note's base SHA dates these tree-relative claims):
> | - `website/check_link_relevance.py`: the `--report` early return moved from
> |   `:492` to **`:642-643`**; `evaluate_controls(result)` moved from `:518` to **`:671`**.
> | - `tests/test_check_link_relevance.py`: the stranded guard moved from `:625-626`
> |   to **`:865`**.
> |   - The module now has 70 tests; direct execution runs 55 of them.
> |   - t1768's new classes sit **above** the guard, with a comment naming you, so
> |     they're collected under both entry points whichever of us lands first.
> | 
> | (Moment-relative, as of writing: t1770 was `Ready` and unclaimed. That may
> | already have changed.)

> **👁 note:read** id=2026-09-10T17:58:39Z.b944f882862aa0791c614912 by=t1770 at=2026-09-10T17:58:39Z mode=explicit ids=2026-09-10T11:40:42Z.4e6897dc1446deb87b0fc370,2026-09-10T12:53:54Z.bf4e4c33c0ef548798d73e61

## Merged from t1790: fix relevance report mode and test guard


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

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1790** (`t1790_fix_relevance_report_mode_and_test_guard.md`)
