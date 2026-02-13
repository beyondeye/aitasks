---
priority: low
effort: low
depends: []
issue_type: documentation
status: Done
labels: [aitasks, docs]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-13 11:47
updated_at: 2026-02-13 12:00
completed_at: 2026-02-13 12:00
---

Add documentation for the new atomic task locking mechanism (aitask_lock.sh) to the Development section at the end of README.md. Cover: purpose (preventing race conditions when two PCs pick the same task), the aitask-locks branch, lock/unlock lifecycle during aitask-pick workflow, available commands (--init, --lock, --unlock, --check, --list, --cleanup), and how it integrates with ait setup.
