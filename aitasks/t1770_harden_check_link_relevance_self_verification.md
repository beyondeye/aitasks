---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [web_site, testing]
created_at: 2026-09-09 16:33
updated_at: 2026-09-09 16:33
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
