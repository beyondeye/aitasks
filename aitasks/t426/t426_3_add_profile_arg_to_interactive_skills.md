---
priority: medium
effort: medium
depends: [t426_2, 2]
issue_type: feature
status: Implementing
labels: [execution_profiles]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-22 10:21
updated_at: 2026-03-22 11:18
---

Add --profile <name> argument parsing to 6 interactive skills (pick, fold, review, pr-import, revert, explore). Pass skill_name and profile_override to the profile selection procedure. Also update Codex wrappers (.agents/skills/) and OpenCode wrappers (.opencode/skills/) Arguments sections to document --profile pass-through. Gemini CLI has no wrappers.
