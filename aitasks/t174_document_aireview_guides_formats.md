---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [aitask_review]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-19 08:07
updated_at: 2026-02-19 22:45
---

aireviewguides shipped with the aitask framework and that can be interacted with from claude skills: aitask_review, aitask-reviewguild-classify and aitask-reviewguide-merge use specific metadata format and additional metadata stored in aireviewguides/*.txt files. I want to document this in the docs/development.md includeing the "algorithms" used to match guides to files and matching files to environments, see also the scripts aitask_review_detect_env, aitask_reviewguide_scan
