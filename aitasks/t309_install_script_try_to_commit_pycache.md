---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [install_scripts]
created_at: 2026-03-05 09:28
updated_at: 2026-03-05 09:28
---

I have run ait setup in this repo (the aitasks repo) and at the end it suggest that the following framework file should be added to git:   aiscripts/__pycache__/aitask_explain_process_raw_data.cpython-314.pyc

this is wrong: first __pycache__ should be gitignores 2) even if found and not gitignored this files are not framework files, need to review how not committed framework files are scanned, now that we also have added wrappers for skills to support codex cli (see task 130)
