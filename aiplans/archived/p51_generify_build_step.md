---
Task: t51_generify_build_step.md
Branch: (current branch)
Base branch: main
---

# Plan: Generify Build Verification Step (t51)

## Context

The task-workflow SKILL.md (Step 9: Post-Implementation) has a hardcoded Android build command:
```bash
JAVA_HOME=/opt/android-studio/jbr ./gradlew assembleDebug
```
This makes the workflow Android-specific. The goal is to make it configurable per project type via a new `aitasks/metadata/project_config.yaml` file, and to add build verification to all three workflow skills (task-workflow, pickrem, pickweb).

## Approach

Introduce a project-level config file (`project_config.yaml`) with a `verify_build` field. All three workflow SKILLs read this config instead of hardcoding a command. If not configured, the step is skipped. On build failure, the agent automatically goes back to fix errors (no interactive prompts).

**Why `project_config.yaml` and not execution profiles?**
- Build commands are a **project characteristic** (same across all profiles), not a workflow behavior
- `project_config.yaml` can grow to hold future project-level settings (test commands, lint commands, etc.)
- Follows the existing pattern: `userconfig.yaml` = per-user, `project_config.yaml` = per-project

## Changes Made

### New Files
1. `seed/project_config.yaml` — Seed template with full documentation and examples
2. `aitasks/metadata/project_config.yaml` — Project config for aitasks itself (empty verify_build)
3. `website/content/docs/skills/aitask-pick/build-verification.md` — Full documentation subpage

### Modified Files
4. `.claude/skills/task-workflow/SKILL.md` — Replaced hardcoded Android build with generic verify_build logic; added Project Configuration section
5. `.claude/skills/aitask-pickrem/SKILL.md` — Added build verification between Step 8 and Step 9
6. `.claude/skills/aitask-pickweb/SKILL.md` — Added build verification between Step 6 and Step 7
7. `aiscripts/aitask_setup.sh` — Added seed copy for project_config.yaml
8. `CLAUDE.md` — Added project_config.yaml to metadata directory listing
9. `website/content/docs/skills/aitask-pick/_index.md` — Converted from .md to directory; added Build Verification link

### Follow-up Tasks Created
- t235: Create aitask-pickrem website documentation page
- t236: Create aitask-pickweb website documentation page

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned — introduced `project_config.yaml` with `verify_build` field, updated all three workflow SKILL.md files, added seed template, setup script copy, CLAUDE.md update, and website documentation with subpage.
- **Deviations from plan:** None. All 10 planned steps were implemented as specified.
- **Issues encountered:** None. All YAML files validated, shellcheck passed (only pre-existing warnings), all three skills have consistent build verification text.
- **Key decisions:** Build verification is project-level (not profile-level). On failure, the agent auto-fixes task-related errors and logs pre-existing failures without attempting to fix them. Website docs structured as a subpage of aitask-pick for reusability across pickrem/pickweb references.
