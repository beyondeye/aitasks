---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-19 09:32
updated_at: 2026-03-19 12:04
---

in ait board there are several operations that run asynchronously and there is not indication that they are running and only a notification is shown when the operation completed: some notable: sync, commit, commit all (in main screen), lock/unlock (in task detail screen), this tasks consists of auditing ait board code for such operation and making a plan to add a LoadingIndicator widget that while the such async operations are running

LoadingIndicator is built-in wdidget in textual 8.1.x
