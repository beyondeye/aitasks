---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [install_scripts]
children_to_implement: [t326_2, t326_3]
created_at: 2026-03-07 20:01
updated_at: 2026-03-07 23:09
---

this is a big refactoring of the directory structure for the aitasks framework. I want to remove the symlink that is installed at install time that link aitasks directory to .aitask-data, and change all direct references in all the code(scripts/skills)  and all documentation do the aitasksdirectory to use instead directly .aitask-data. also I want to rename the aiscripts directory to the new name .aitask-scripts and change ALL references in all doucmentation and in all skills, scripts, to reference the new directory. this is a very complex task that require full research of existing code and docs, and also for implementation require several phase. for avoding breaking things before all is ready, leave the existing directory aiscripts and the aitasks symlink and only when everyting is verified to have moved correclty remove the aitasks symlink and the old aiscripts directory and verify again. ultrathink
this is a complex task that need to be split in child tasks
