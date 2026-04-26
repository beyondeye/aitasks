---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [installation, install_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-26 09:52
updated_at: 2026-04-26 11:29
completed_at: 2026-04-26 11:29
boardidx: 10
---

when running ait upgrade to update the installed version of the aitasks framework, the ait dispatcher is not updated. also I just run ait upgrade in ../aitasks_mobile and I see that the new framework files that were added on upgrade were not git-added to the repo, as it is done on normal installation with ait setup (framework files are considered part of the repo sources). can you check if ait upgrade actually worked (check copied files). has been all framework files be copied correctly?
