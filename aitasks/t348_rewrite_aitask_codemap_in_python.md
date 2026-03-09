---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [bash_scripts, aitask_codemap]
created_at: 2026-03-09 16:20
updated_at: 2026-03-09 16:20
boardcol: now
boardidx: 10
---

current the aitask_codemap has hard coded exclude_dirs that exclude current framework directory. add an option to NOT EXCLUDE aitasks framework directories, and option to pass an external list of directory to exclude in .gitignore format, and use the same mechanism as in reviewguides (.reviewguideignore) and by default read the project .gitignore file to ignore directory taht should not probably be scanned. substitute this mechanism to the hard coded directories like node_modules, __pychache__ (although node_modules, is a particularly dangerous directory, with a lot of files that can take ages to scan). also consider if rewriting the script in python could improve performance/ features/ reliability
