---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Done
labels: [opencode, ci]
assigned_to: dario-e@beyond-eye.com
implemented_with: opencode/openai_gpt_5_3_codex
created_at: 2026-03-06 12:57
updated_at: 2026-03-06 13:10
completed_at: 2026-03-06 13:10
---

The release packaging pipeline needs updates to also package .opencode/commands/ and opencode_planmode_prereqs.md. Currently only aitask-*/ subdirs and opencode_tool_mapping.md are packaged. Files to update: .github/workflows/release.yml (tarball creation step), install.sh (install_opencode_staging function), aiscripts/aitask_setup.sh (setup_opencode function to also install commands).
