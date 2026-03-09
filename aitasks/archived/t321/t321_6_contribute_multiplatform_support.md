---
priority: medium
effort: medium
depends: [t321_5]
issue_type: feature
status: Done
labels: [auto-update]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-08 22:32
updated_at: 2026-03-09 12:02
completed_at: 2026-03-09 12:02
---

## Context

This is a follow-up task from t321_3 (documentation). The aitask-contribute skill and aitask_contribute.sh script were developed with the aitasks GitHub repo in mind, using the gh CLI for issue creation. However, aitasks supports GitHub, GitLab, and Bitbucket as git remotes.

This task should verify and extend the contribute functionality to work across all supported platforms, or at minimum clearly document platform limitations.

## Key Files to Analyze

- .aitask-scripts/aitask_contribute.sh — the core script, currently uses gh CLI (GitHub-specific)
- .claude/skills/aitask-contribute/SKILL.md — skill definition, prerequisites check requires gh CLI
- .aitask-scripts/lib/task_utils.sh — detect_platform() function for platform detection

## Areas to Investigate

1. Can aitask_contribute.sh work with GitLab (glab CLI) and Bitbucket (bkt CLI) for issue creation?
2. What changes are needed in the script to support multi-platform issue creation?
3. Should the skill's prerequisites check detect the platform and require the appropriate CLI tool?
4. Update documentation (skill doc and workflow page) to reflect actual platform support

## Reference Files for Patterns

- .aitask-scripts/aitask_issue_update.sh — example of multi-platform support pattern
- .aitask-scripts/aitask_pr_import.sh — another multi-platform example
- website/content/docs/skills/aitask-contribute.md — documentation to update
- website/content/docs/workflows/contribute-and-manage.md — workflow page to update

## Verification Steps

- Test or verify issue creation flow for GitHub (existing)
- Design/implement issue creation for GitLab using glab CLI
- Design/implement issue creation for Bitbucket using bkt CLI
- Update documentation to reflect supported platforms
