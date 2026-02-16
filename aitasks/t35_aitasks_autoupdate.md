---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitasks, claudeskills]
created_at: 2026-02-04 08:20
updated_at: 2026-02-04 08:20
boardidx: 30
boardcol: next
---

I want to create a claude skill that will take care to update the project local definitions of aitasks related skills, like aitask-pick (and all the other skills with the same prefix) from two different possible sources 1) the aitasks repo on github (https://github.com/beyondeye/aitasks.git), aitasks as defined in another project, both local (directory search with fzf) or on github (need t[D[D[D[to prorvide url) the update process consists of: retrieving the aitasks shell scripts and copying them 2) retrieve the skills markdown definitions and MERGE them with existing skills: the usually actually should choose upfront if he wants to overrite or merge the skills. if he chooses merge, then the autoypdate skill should one by one for all the aitasks skill compare the definitions show to diff to the user and ask for each diff if to use the updated version or the current viersion. ask me questions if you need clarifications
