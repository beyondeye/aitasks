---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-23 18:38
updated_at: 2026-03-23 18:55
---

## Problem

`aitask_query_files.sh recent-archived <limit>` crashes with exit code 141 (SIGPIPE) when the number of archived tasks exceeds the `limit` parameter.

### Root Cause

In `cmd_recent_archived()` (line 408), the pipeline:
```bash
sorted=$(printf '%s\n' "${entries[@]}" | sort -t'|' -k1 -r | head -n "$limit")
```

When there are more entries than `$limit` (currently 186 archived tasks vs limit=15), `sort` outputs all entries. After `head -n 15` reads 15 lines and closes, `sort` gets SIGPIPE (signal 13 → exit code 141). With `set -eo pipefail`, this propagates as a fatal error.

### Impact

Blocks `/aitask-qa` interactive task selection — the `recent-archived` query is called to find recently completed tasks for QA analysis. When it fails, parallel tool calls in the QA skill are cancelled.

### Bug introduced

In commit 8ce7b026 (t428_1 — aitask-qa skill), when `cmd_recent_archived` was added.

## Fix

Replace the `sort | head` pipeline with a SIGPIPE-safe approach. Options:

1. **Remove `head` from pipeline, limit in loop:** Sort all entries, then limit output in the `while read` loop using a counter variable. This avoids `head` closing the pipe early entirely.

2. **Suppress SIGPIPE:** Add `|| true` after the pipeline assignment: `sorted=$(...) || true`. Simple but less targeted.

Option 1 is preferred — it's the same pattern used in similar fixes (see t389).

Also audit the per-file `grep | sed | head -n 1` pipelines (lines 382, 384, 394, 396) for the same class of bug — they could SIGPIPE if any archived task file has multiple `completed_at:` or `issue_type:` lines matching the grep pattern.
