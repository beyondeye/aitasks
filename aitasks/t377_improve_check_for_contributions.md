---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_contribute]
created_at: 2026-03-12 11:46
updated_at: 2026-03-12 11:46
---

in aitask-contribute skill we check for local changes vs code into some source repo, this repo being the aitasks project repo, or another configured remote repo. my questions is: what kind of "changes" are checked and how? are changes checked by checking for local commits that are absent in remote repo? are we checking for uncomitted changes? or both? how exactly we compare the remote repo, with the current state of code locally? we need to be flexible and support all modes.
