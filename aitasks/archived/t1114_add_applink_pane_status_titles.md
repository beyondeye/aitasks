---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [applink, tests]
implemented_with: codex/gpt5_5
created_at: 2026-07-02 16:22
updated_at: 2026-07-02 16:23
completed_at: 2026-07-02 16:23
---

Add best-effort task titles to applink `pane_status` pushes so clients can display task context alongside the derived task id. Preserve existing status payload behavior when no task resolver is available or when title lookup fails, and cover the new behavior in the pusher test suite.
