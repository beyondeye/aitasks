---
priority: high
effort: medium
depends: [t227_4]
issue_type: feature
status: Implementing
labels: [core]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 16:52
updated_at: 2026-02-24 16:58
---

Introduce a per-user, gitignored config file `aitasks/metadata/userconfig.yaml` to replace the broken "first email from emails.txt" pattern in multi-user setups.

## Context

Currently, the `fast` profile and other automated workflows use `default_email: first` which reads the first email from `aitasks/metadata/emails.txt`. This is a shared, committed file -- in multi-user setups, the "first" email could be any team member's, not the current user's. Every place in the framework that auto-selects an email needs to be updated to use the new per-user config.

## File Format
```yaml
# Local user configuration (gitignored, not shared)
email: user@example.com
default_profile: fast
```

## Key Files to Create/Modify

### New files
- `aitasks/metadata/userconfig.yaml` -- gitignored template
- `.gitignore` and `seed/.gitignore` -- add the pattern

### Shell scripts
- `aiscripts/aitask_setup.sh` -- prompt for userconfig during setup if missing
- `aiscripts/lib/task_utils.sh` -- add `get_user_email()` helper function
- `aiscripts/aitask_own.sh` -- fallback email from userconfig when `--email` not provided

### Skill definitions
- `.claude/skills/task-workflow/SKILL.md` -- handle `default_email: userconfig` sentinel
- `.claude/skills/aitask-pickrem/SKILL.md` -- same change
- `.claude/skills/aitask-pickweb/SKILL.md` -- use userconfig from the start

### Execution profiles
- `aitasks/metadata/profiles/fast.yaml` -- change `default_email: first` to `default_email: userconfig`
- `aitasks/metadata/profiles/remote.yaml` -- same change

## Changes Required

1. **Gitignore the file** -- add `aitasks/metadata/userconfig.yaml` to `.gitignore`
2. **Update ait setup** -- prompt for email and profile, write userconfig.yaml
3. **Add get_user_email() helper** in task_utils.sh:
   ```bash
   get_user_email() {
     local config="aitasks/metadata/userconfig.yaml"
     if [[ -f "$config" ]]; then
       grep '^email:' "$config" | sed 's/^email: *//'
     fi
   }
   ```
4. **Update all "first email" patterns** -- when profile says `default_email: userconfig`, read from userconfig.yaml
5. **Update emails.txt workflow** -- `emails.txt` remains as shared registry; when user enters email interactively, also update userconfig.yaml
6. **Board TUI** -- pre-fill lock email prompt from userconfig.yaml

## Verification
- Verify `aitasks/metadata/userconfig.yaml` is in `.gitignore`
- Run `ait setup` and verify it creates/prompts for userconfig
- Verify `get_user_email()` helper works
- Verify profiles with `default_email: userconfig` read from userconfig.yaml
- Test: two different userconfig files should resolve to different emails
