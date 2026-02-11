---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 09:22
updated_at: 2026-02-11 10:38
completed_at: 2026-02-11 10:38
boardcol: now
boardidx: 10
---

in the aitasks frontmatter metadata with the fields depends (that contains al list of tasks like [t85_2, t85_3] aand the children_to_implement field with similar list of tasks: claude code when writing task "manually" without using the aitask_create.sh bash script or atask_update script, many times write the dependencies without the "t" prefix that is [85_2, 85_3] it would be possible, in the aitask_update script and int he python aitask_board script, where we READ this dependencies from metadata to support both format (but always outputing t<number> format
