---
Task: t1082_fix_failed_verification_t717_5_item12.md
Worktree: (current branch - fast profile)
Branch: main
Base branch: main
---

# t1082 - Fix failed verification t717_5 item 12

## Summary

Fix the "Top verified models (recent)" picker ranking so models with recent
verified activity rank ahead of legacy fallback scores from models with no
recent runs.

## Implementation Plan

- Update `.aitask-scripts/lib/agent_model_picker.py` so top-verified candidates
  record whether their score came from recent `month + prev_month` buckets or
  from the no-recent legacy fallback.
- Sort top-verified candidates by recent-presence first, then score, provider,
  and model name.
- Add a focused regression test that mirrors the failed manual-verification
  fixture: a high no-recent fallback score must not outrank a lower recent
  score.

## Verification

- `python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py`
- `python3 tests/test_agent_model_picker.py`
- `./ait gates run 1082`

## Final Implementation Notes

- **Actual work done:** Added recent-vs-fallback ranking metadata in
  `_build_top_verified()` and sorted recent candidates ahead of no-recent
  fallback rows. Added `tests/test_agent_model_picker.py` to lock the failed
  fixture.
- **Deviations from plan:** Used `unittest` execution for the focused test
  because `pytest` is not installed in the active project interpreter.
- **Issues encountered:** `pytest` was unavailable; direct `unittest` execution
  passed. Git staging required escalation because `.git/index.lock` is outside
  the writable sandbox.
- **Key decisions:** Kept no-recent fallback rows visible after recent rows so
  the picker can still show up to five options without letting legacy scores
  dominate the recent ranking.
- **Upstream defects identified:** None
