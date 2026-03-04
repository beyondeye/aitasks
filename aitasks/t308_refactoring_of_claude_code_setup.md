---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [install_scripts]
created_at: 2026-03-04 06:50
updated_at: 2026-03-04 06:50
---

in ait setup create a separate method with all claude specific installation like the claude code permissions and move all claude-code specific config there. run this method only if claude is installed, careate also similar stub methods for geminicli codexcli and opencode and similarly run the method only if the associated codeagent is installed
