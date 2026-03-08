---
priority: high
effort: medium
depends: []
issue_type: feature
status: Done
labels: [geminicli]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-08 14:52
updated_at: 2026-03-08 15:06
completed_at: 2026-03-08 15:06
---

## Summary

Migrate Gemini CLI custom commands from `.md` to `.toml` format, add permission whitelisting support (policies), and update the entire release/install/setup pipeline to handle these new files.

## Context

The `.gemini/commands/` directory previously contained 17 `.md` command wrapper files. These have been replaced with `.toml` format files, which is the correct format for Gemini CLI custom commands. Additionally, a new permission whitelisting system has been added via `.gemini/policies/aitasks-whitelist.toml` and `.gemini/settings.json`, analogous to Claude Code's `.claude/settings.local.json` and OpenCode's `opencode.json`.

## Changes Already Done (uncommitted)

1. **Deleted:** 17 old `.gemini/commands/*.md` files (wrong format)
2. **Added:** 17 new `.gemini/commands/*.toml` files (correct format)
3. **Added:** `.gemini/policies/aitasks-whitelist.toml` — permission whitelist with 50+ rules for aitask scripts, git, and utilities
4. **Added:** `.gemini/settings.json` — Gemini CLI settings pointing to `.gemini/policies/` directory
5. **Deleted:** `imgs/aitasks_logo_dark_theme_transbg.png` (unrelated cleanup)

## Remaining Work

### 1. Commit the uncommitted changes
Commit all the above changes with an appropriate commit message.

### 2. Update release workflow (`.github/workflows/release.yml`)
- Add `gemini_policies/` directory to the tarball (copy from `.gemini/policies/`)
- Add `gemini_settings.json` to the tarball (copy from `.gemini/settings.json`)
- The workflow already handles `gemini_commands/` — verify it correctly picks up `.toml` files instead of the old `.md` files

### 3. Update install script (`install.sh`)
- Stage `gemini_policies/` from tarball to `aitasks/metadata/geminicli_policies/`
- Stage `gemini_settings.json` from tarball to `aitasks/metadata/geminicli_settings.seed.json`

### 4. Update `ait setup` (`.aitask-scripts/aitask_setup.sh`)
In the `setup_gemini_cli()` function:
- Install `.gemini/policies/aitasks-whitelist.toml` from `aitasks/metadata/geminicli_policies/` to `.gemini/policies/`
- Install `.gemini/settings.json` from `aitasks/metadata/geminicli_settings.seed.json` to `.gemini/settings.json`
- Follow the same merge/union pattern used by Claude Code (`setup_claude_code()`) and OpenCode (`setup_opencode()`) for permission files:
  - If `.gemini/policies/` or `.gemini/settings.json` already exists, merge rather than overwrite
  - For policies: merge TOML rules (deduplicate by commandPrefix/commandRegex)
  - For settings.json: merge JSON with existing (preserve user's custom settings, add policyPaths if missing)
  - Prompt user for approval before installing permissions (consistent with Claude Code and OpenCode behavior)

### 5. Add seed files
- `seed/geminicli_policies/aitasks-whitelist.toml` — copy of `.gemini/policies/aitasks-whitelist.toml`
- `seed/geminicli_settings.seed.json` — copy of `.gemini/settings.json`

### 6. Verify command format migration
Ensure the release workflow, install script, and setup script all reference `.toml` files (not `.md`) for Gemini CLI commands. The old `.md` wrappers should not be referenced anywhere.

## Reference Files

- **Release workflow:** `.github/workflows/release.yml`
- **Install script:** `install.sh`
- **Setup script:** `.aitask-scripts/aitask_setup.sh` (function `setup_gemini_cli()`)
- **Claude Code permissions pattern:** `setup_claude_code()` in `aitask_setup.sh`
- **OpenCode permissions pattern:** `setup_opencode()` in `aitask_setup.sh`
- **Seed directory:** `seed/`
