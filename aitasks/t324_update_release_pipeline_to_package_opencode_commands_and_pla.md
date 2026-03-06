---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [opencode, ci]
created_at: 2026-03-06 12:57
updated_at: 2026-03-06 12:57
---

The release packaging pipeline needs updates to also package .opencode/commands/ and opencode_planmode_prereqs.md. Currently only aitask-*/ subdirs and opencode_tool_mapping.md are packaged. Files to update: .github/workflows/release.yml (tarball creation step), install.sh (install_opencode_staging function), aiscripts/aitask_setup.sh (setup_opencode function to also install commands).
