---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_changelog]
created_at: 2026-07-31 11:12
updated_at: 2026-07-31 11:12
---

## Origin

Spawned from t1355 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_changelog.sh:184-192 — show_help's --gather format block lists COMMITS before NOTES, but gather() emits NOTES before COMMITS (stale help text)`

## Diagnostic context

While building the `aitask-docs-gap` skill (t1355), which parses the
`--gather` output, the actual emission order in `gather()` (lines 136-157)
was confirmed to be `ISSUE_TYPE`, `TITLE`, `PLAN_FILE`, `NOTES` (+body),
`COMMITS` (+body) — but the format block in `show_help` (lines 184-192)
documents `COMMITS` before `NOTES`. Any consumer written against the help
text and parsing by position would misread the sections. Both existing
consumers (`aitask-changelog`, `aitask-docs-gap`) parse by `KEY:` prefix and
are unaffected.

## Suggested fix

Reorder the format block in `show_help` to match the real emission order
(NOTES before COMMITS).
