---
priority: medium
effort: medium
depends: [t369_4]
issue_type: test
status: Ready
labels: [aitask_explain, aitask_pick]
created_at: 2026-03-11 18:34
updated_at: 2026-03-11 18:34
---

Write tests for aitask_explain_format_context.py and aitask_explain_context.sh. Test synthetic reference.yaml processing, greedy selection algorithm, cache reuse, --max-plans limiting, and graceful no-op. Follow existing test patterns (assert_eq/assert_contains, PASS/FAIL).
