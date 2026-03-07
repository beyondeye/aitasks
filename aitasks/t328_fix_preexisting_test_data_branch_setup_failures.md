---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [install_scripts]
created_at: 2026-03-07 23:52
updated_at: 2026-03-07 23:52
---

test_data_branch_setup.sh has 7 failing tests related to CLAUDE.md content generation (update_claudemd_git_section). The function now uses assemble_aitasks_instructions() which reads from aitasks/metadata/aitasks_agent_instructions.seed.md, but the test fixtures don't create this seed file. Tests 1, 6, 7, 8 fail because the seed file is missing in the temp test directories, so update_claudemd_git_section silently returns without creating/updating CLAUDE.md. Fix: update test fixtures to include the seed file, or adjust the tests to match the new seed-based architecture.
