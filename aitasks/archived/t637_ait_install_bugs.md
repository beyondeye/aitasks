---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [installation, install_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-23 22:34
updated_at: 2026-04-24 07:39
completed_at: 2026-04-24 07:39
---

the ait install scripts can be used to update the aitasks framework installed in a project repo. there are several bugs that need to be fixed. 1) the project settings (edited with ait settings) are ovverridden with the default: this is very problematic: the existing project settings should be kept: only when new project settings key exists in the new default config pulled with ait install, those keys should be merged in the existing configuration 2) the update aitasks framework files, should be committed to the proect git repo, if the framework files for previous version are committed: we can check the VERSION framework file if it is committed or not, in order to decide 3) the .gitignore for __pycache__ directories in the aitasks framework dir (in ,aitasks-scripts) or is absent or it is not working (look at ../aitasks-mobile where we have updated the framework with ait install. ask me questions if you need clarifications
