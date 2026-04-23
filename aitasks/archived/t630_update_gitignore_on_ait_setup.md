---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [installation, install_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-23 14:17
updated_at: 2026-04-23 14:28
completed_at: 2026-04-23 14:28
---

I have just noticed that on a fresh install of the ait framework while running ait setup in a new project directory, __pycache__ aitasks framework directory are not added to .gitignore. they should, what would be best is a general __pycache__ .gitignore rule appended to existing .gitignore, or in a new .gitignore file if not existing that is also commited together with other framework files

I mena committed during ait setup (after user approval, like general approval of committing framewrok files)
