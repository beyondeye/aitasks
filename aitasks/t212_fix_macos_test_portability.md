---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [macos, bash_scripts]
created_at: 2026-02-22 23:08
updated_at: 2026-02-22 23:08
---

Fix 4 failing test scripts caused by macOS portability issues: wc -l whitespace padding breaking string comparisons in assert_eq, hardcoded Linux path in test_t167, and unmocked network in test_global_shim. Document wc -l gotcha in macOS compat guide.
