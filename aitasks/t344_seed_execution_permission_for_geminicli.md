---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [geminicli]
created_at: 2026-03-09 13:31
updated_at: 2026-03-09 13:31
boardidx: 110
boardcol: next
---

geminicli is currently almost unusable because of the missing execution permissions for the aiscripts tools: project level permission are currently ignored, and global user level permission when added during skill execution are narrowed to specific commands. this issue must be solved if we want to make geminicli usable: a possibility is copy the proper execution perimission at USER level in ait setup (adding a caveat that project level permission does not work) need to try at least if this works, and if yes then add the option in ait setup for geminiclil (install permission at user level instead of project level)
