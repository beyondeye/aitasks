---
Task: t1933_fix_multi_session_primitives_field_list.md
Base branch: main
Output branch: main
---

# Plan: t1933 — update the pinned `AitasksSession` field list

## Context

`tests/test_multi_session_primitives.sh` pins the sorted field names of the
`AitasksSession` dataclass (`.aitask-scripts/lib/agent_launch_utils.py`). t1811
(commit bc97800ee) added `default_session_problem: str | None = None` to that
dataclass but never updated this pin, so the test reports 19/20 with:

```
FAIL: AitasksSession fields (expected 'FIELDS:is_live,is_stale,project_group,project_name,project_root,session',
got 'FIELDS:default_session_problem,is_live,is_stale,project_group,project_name,project_root,session')
```

The production field is intentional (documented in the dataclass comment), so
the test expectation is what is stale.

## Change

`tests/test_multi_session_primitives.sh:55` — change the expected string to the
sorted list including the new field:

```
FIELDS:default_session_problem,is_live,is_stale,project_group,project_name,project_root,session
```

No production code changes.

## Other pinned field lists (task asks to check) — none stale

- `grep -rln AitasksSession tests/` → 17 files; the only one that pins the full
  field set is this one (`fields(u.AitasksSession)` at line 46). The others
  construct sessions by keyword, which the defaulted new field does not affect.
- `tests/test_multi_session_monitor.sh` pins `TmuxPaneInfo` (only checks
  `session_name` presence/default) — currently 47/47 passing.
- No Python test asserts an exact `AitasksSession` field set.

## Verification

- `bash tests/test_multi_session_primitives.sh` → `Results: 20/20 passed`.
- `shellcheck tests/test_multi_session_primitives.sh` produces no new warnings.

## Risk

### Code-health risk: low
None identified. (One-line test-expectation change; no production code touched.)

### Goal-achievement risk: low
None identified. (Failure reproduced; the fix matches the dataclass exactly, and
the "other pinned lists" audit found no further stale pins.)

## Implementation status

- [x] `tests/test_multi_session_primitives.sh:55` expectation updated — done as planned, no deviations.
- [x] Verified: `bash tests/test_multi_session_primitives.sh` → `Results: 20/20 passed, 0 failed` (exit 0).
- [x] `shellcheck` reports only pre-existing SC1091 (info) on the untouched `source` lines.

## Final Implementation Notes
- **Actual work done:** Updated the pinned sorted `AitasksSession` field list in `tests/test_multi_session_primitives.sh:55` to include `default_session_problem` (added by t1811, commit bc97800ee). One-line test-expectation change; no production code touched.
- **Deviations from plan:** None.
- **Issues encountered:** None. Audit of the other 16 test files referencing `AitasksSession` found no other exact field-set pin; `tests/test_multi_session_monitor.sh` (pins `TmuxPaneInfo.session_name` only) passes 47/47.
- **Key decisions:** Kept the exact-set pin (rather than loosening it to a subset check) so a future field addition is still surfaced deliberately.
- **Upstream defects identified:** None
