---
Task: t96_install_defaults_for_claude_settings_for_aitasks.md
Worktree: (none - working on main)
Branch: main
Base branch: main
---

## Context

The aitask-pick skill (and other aitask skills) invoke many Bash commands during their workflow. Each time a user runs the workflow for the first time, Claude Code prompts for approval on every single command — `sed`, `mv`, `mkdir`, `git checkout`, etc. This is tedious and discouraging for new users. The fix: ship a default `settings.local.json` with pre-approved permissions for all aitask operations, and merge it during `ait setup`.

## Files Modified

| File | Action |
|------|--------|
| `seed/claude_settings.local.json` | **CREATE** — seed file with 29 default permissions |
| `aitasks/metadata/claude_settings.seed.json` | **CREATE** — copy of seed for `ait setup` to read |
| `install.sh` | **MODIFY** — add `install_seed_claude_settings()` to copy seed to metadata |
| `aiscripts/aitask_setup.sh` | **MODIFY** — add `install_claude_settings()` + `merge_claude_settings()` with interactive prompt |
| `.claude/settings.local.json` | **MODIFY** — updated project's own file (gitignored) |
| `README.md` | **MODIFY** — document Claude Code permissions |

**No changes to `release.yml`** — `seed/` is already in the tarball.

## Implementation

### Seed permissions (29 entries)

Excluded from defaults (require manual approval): `rm`, `mv`, `rmdir`, `tar`, `bash` — potentially destructive. Kept `sed` since Claude already has the Edit tool.

### install.sh changes

Simple `install_seed_claude_settings()` function that copies `seed/claude_settings.local.json` to `aitasks/metadata/claude_settings.seed.json` (no user interaction — that happens in `ait setup`).

### aitask_setup.sh changes

Two functions added:
- `merge_claude_settings()` — merges `permissions.allow` arrays (union, no duplicates). Two-tier fallback: jq → python3 → manual warning. Preserves all existing keys.
- `install_claude_settings()` — shows permissions list, asks Y/n interactively, copies or merges into `.claude/settings.local.json`.

Called in `main()` after `install_global_shim` and before `check_latest_version`.

## Verification

1. `bash -n install.sh` — syntax OK
2. `bash -n aiscripts/aitask_setup.sh` — syntax OK
3. `seed/claude_settings.local.json` — valid JSON
4. Tested jq merge with overlapping + custom entries — union correct, no duplicates, preserves deny/other keys
5. Tested python3 merge fallback — identical results

## Final Implementation Notes

- **Actual work done:** Created seed permissions file, added simple copy in install.sh, added interactive merge in ait setup, documented in README
- **Deviations from plan:** User requested moving the interactive prompt from install.sh to ait setup so it's always interactive (never silent in piped curl|bash mode). Also removed rm, mv, rmdir, tar, bash from default permissions per user request.
- **Issues encountered:** None
- **Key decisions:** Store seed at `aitasks/metadata/claude_settings.seed.json` so `ait setup` can access it after the seed/ directory is cleaned up. Two-tier jq/python3 fallback for JSON merging.
