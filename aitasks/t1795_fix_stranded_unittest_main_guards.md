---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing]
gates: [risk_evaluated]
anchor: 1770
followup_kind: upstream_defect
created_at: 2026-09-11 11:27
updated_at: 2026-09-11 11:27
---

## Origin

Spawned from t1770 during Step 8b review.

## Upstream defect

- `tests/test_minimonitor_own_mark.py:786` — `unittest.main()` guard mid-file; `OwnAgentStaysCapturedTests` and `OwnWindowInfoConfirmationTests` never run under direct execution
- `tests/test_monitor_finalize_offload.py:418` — `unittest.main()` guard mid-file; `AgentScopingCallSiteTests` never runs under direct execution
- `tests/test_shadow_seam.py:1263` — `unittest.main()` guard mid-file; `FormatShadowStaleBannerTests`, `NarrowShadowStaleBannerTests`, `FormatStalenessDetailTests` and `_Meta` never run under direct execution

Line numbers as of t1770's code commit `c78deab36`; they move with edits.

## Diagnostic context

`unittest.main()` calls `sys.exit()`, so a guard placed mid-file stops the
interpreter there: every class defined below it is never defined, and
`python3 tests/<module>.py` reports a green partial count. Discovery-based entry
points (`tests/run_all_python_tests.sh`, pytest, `python3 -m unittest`) import the
module instead and collect everything, so this is a developer-facing trap rather
than a CI hole — which is why it goes unnoticed.

Same defect fixed before in `tests/test_minimonitor_concern_action.py` (t1518) and
`tests/test_check_link_relevance.py` (t1770). t1770's planning ran an AST scan over
`tests/**/*.py` (top-level `ClassDef`/`FunctionDef` after the top-level
`if __name__ == "__main__":`) and found exactly these three remaining modules.

## Suggested fix

Move each guard to the physical end of its module. Then add a repo-wide guard
test that fails on any module with a top-level definition after its `__main__`
guard — `_defs_after_main_guard()` in `tests/test_check_link_relevance.py` (t1770)
generalizes directly — so no module can re-strand. It can only land once all
three are clean, since it would fail immediately today.
