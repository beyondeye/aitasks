---
Task: t335_gemini_cli_command_toml_migration_and_permission_setup.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Implementation Plan: Gemini CLI Command TOML Migration & Permission Setup

## Context

Gemini CLI custom commands were defined as `.md` files, which was the wrong format. They've been
rewritten as `.toml` files (the correct Gemini CLI format). Additionally, a new permission
whitelisting system via `.gemini/policies/aitasks-whitelist.toml` and `.gemini/settings.json`
has been added locally but needs to be integrated into the release/install/setup pipeline.

Currently Claude Code and OpenCode have full permission whitelist support in `ait setup`, but
Gemini CLI does not. This task adds that support.

## Implementation Steps

### Step 1: Commit the uncommitted changes [DONE]

Committed as `6e706e1`:
- 17 deleted `.gemini/commands/*.md` files (old wrong format)
- 17 new `.gemini/commands/*.toml` files (correct format)
- New `.gemini/policies/aitasks-whitelist.toml`
- New `.gemini/settings.json`
- Deleted `imgs/aitasks_logo_dark_theme_transbg.png` (unrelated cleanup)

### Step 2: Add seed files [DONE]

Created:
- `seed/geminicli_policies/aitasks-whitelist.toml` — copy of `.gemini/policies/aitasks-whitelist.toml`
- `seed/geminicli_settings.seed.json` — copy of `.gemini/settings.json`

### Step 3: Update release workflow [DONE]

Updated `.github/workflows/release.yml`:
- Added gemini_policies/ directory and gemini_settings.json to the build step
- Added both to the tarball creation step

### Step 4: Update install script [DONE]

Updated `install.sh`:
- `install_gemini_staging()`: Added staging for `gemini_policies/` → `aitasks/metadata/geminicli_policies/` and `gemini_settings.json` → `aitasks/metadata/geminicli_settings.seed.json`
- `install_seed_gemini_config()`: Added fallback staging from `seed/geminicli_policies/` and `seed/geminicli_settings.seed.json`

### Step 5: Add merge functions [DONE]

Added to `.aitask-scripts/aitask_setup.sh`:
- `merge_gemini_policies()` — Python-based TOML rule deduplication by (toolName, commandPrefix/commandRegex/argsPattern)
- `merge_gemini_settings()` — JSON merge (jq or Python) ensuring policyPaths array union

### Step 6: Update setup_gemini_cli() [DONE]

Added section 3 to `setup_gemini_cli()`:
- Shows user the commandPrefix values from policy files
- Asks for approval ("Install these Gemini CLI permission policies? [Y/n]")
- Installs policy files with merge-if-exists pattern
- Installs settings.json with merge-if-exists pattern
- Follows the same UX pattern as `setup_claude_code()` and `setup_opencode()`

## Verification

- shellcheck passes with no new warnings on both `aitask_setup.sh` and `install.sh`
- Seed files verified as exact copies of source files
- Release workflow YAML includes new entries in both build and tarball steps

## Final Implementation Notes

- **Actual work done:** All 6 planned steps implemented as designed. Additionally updated `tests/test_gemini_setup.sh` to fix `.md` → `.toml` file extension in assertions and added 3 new test sections (policy merge, settings merge, seed file existence).
- **Deviations from plan:** Added test updates (not in original plan but requested during review). Added `info()`/`success()` stub functions to test file for compatibility with extracted merge functions.
- **Issues encountered:** Test 7 initially failed because `info()` and `success()` functions weren't defined in the test context (only `warn()` was). Fixed by adding stubs.
- **Key decisions:** Used Python-based TOML parsing (not a TOML library) for `merge_gemini_policies()` since the format is simple and predictable `[[rule]]` blocks. This avoids requiring `toml` pip package. The merge deduplicates by `(toolName, commandPrefix, commandRegex, argsPattern)` tuple.
