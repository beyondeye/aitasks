---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [yaml, board, archive]
created_at: 2026-03-17 15:16
updated_at: 2026-03-17 15:16
---

Fix: Folded task t38 was not deleted when primary task t398 was archived.

Root cause: TUI board's _normalize_task_ids() in task_yaml.py converted int IDs to strings, causing PyYAML to quote them ([38] -> ['38']). Bash YAML parsers didn't strip quotes, so glob t'38'_*.md failed to match.

Changes: Fix Python root cause, consolidate parse_yaml_list()/normalize_task_ids() into task_utils.sh, add defensive quote-stripping, fix 6 corrupted files, delete orphaned t38.
