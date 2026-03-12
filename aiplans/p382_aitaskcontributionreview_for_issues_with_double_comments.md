---
Task: t382_aitaskcontributionreview_for_issues_with_double_comments.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Context

The `parse_overlap_from_comments()` function in `aitask_contribution_review.sh` uses `head -1` to select the first overlap-results comment found in an issue's comments. Due to a bug in the automated workflow, some issues have multiple duplicate overlap-results comments (e.g., issues 6 and 7). The first comment may be stale — the last (most recent) one should be used instead.

## Plan

### 1. Fix `parse_overlap_from_comments()` to use last overlap comment

**File:** `.aitask-scripts/aitask_contribution_review.sh` (line 289)

Replace the current grep-all-bodies-then-head-1 approach with a jq-first approach that selects the last comment containing the marker, then extracts from that single comment:

```bash
# Before (picks first match across all flattened bodies):
overlap_comment=$(echo "$comments_json" | jq -r '.[].body' | grep -o '<!-- overlap-results[^>]*-->' | head -1 || echo "")

# After (selects last comment containing the marker, then extracts):
overlap_comment=$(echo "$comments_json" | jq -r '[.[] | select(.body | contains("<!-- overlap-results"))] | last | .body // empty' | grep -o '<!-- overlap-results[^>]*-->' || echo "")
```

### 2. Add test for multiple overlap comments

**File:** `tests/test_contribution_review.sh`

New Test 7: two overlap-results comments with different data, manual comment interleaved. Verifies the last one's data is used and the first is ignored.

## Final Implementation Notes
- **Actual work done:** Changed `parse_overlap_from_comments()` to use jq filtering (`select` + `last`) instead of `head -1` on grep output. Added test case for duplicate overlap comments. Renumbered existing tests 7-13 → 8-14.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Used `jq` filtering with `contains()` and `last` rather than simple `tail -1` to be robust against interleaved manual comments. The jq approach selects the last *comment object* containing the marker, rather than the last grep match across all flattened bodies.
