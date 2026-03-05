---
priority: high
effort: medium
depends: [t319_1]
issue_type: feature
status: Ready
labels: [opencode, codeagent]
created_at: 2026-03-06 01:18
updated_at: 2026-03-06 01:18
---

Update release workflow, install.sh, and ait setup to package, distribute, and install OpenCode skill wrappers.

## Context

The Codex CLI support (t130_2) added a full pipeline: release workflow packages skills, install.sh stages them, ait setup installs them. We need the same for OpenCode. The `setup_opencode()` function currently exists as a placeholder.

## Files to Modify

### 1. `.github/workflows/release.yml` (~line 38)
- Add OpenCode skills packaging block (mirror Codex `codex_skills/` → `opencode_skills/`)
- Copy `.opencode/skills/aitask-*/` to `opencode_skills/`
- Copy `opencode_tool_mapping.md` to `opencode_skills/`
- Include `opencode_skills/` in tarball

### 2. `install.sh` (~line 402)
- Add `install_opencode_staging()` — store wrappers from `opencode_skills/` to `aitasks/metadata/opencode_skills/`
- Add `install_seed_opencode_config()` — store `seed/opencode_config.seed.json` and `seed/opencode_instructions.seed.md` to `aitasks/metadata/`
- Call both from main install flow (~line 654)
- Update `commit_installed_files()` to check `.opencode/skills/`

### 3. `aiscripts/aitask_setup.sh` (~line 1470)
Implement `setup_opencode()` (currently placeholder), mirroring `setup_codex_cli()`:
- **Interactive Y/n confirmation prompt** (auto-accept in non-interactive mode) — same pattern as Codex
- Copy skill wrappers from staging `aitasks/metadata/opencode_skills/` to `.opencode/skills/`
- Copy shared tool mapping file
- Report installed skill count
- Assemble instructions: `assemble_aitasks_instructions "$project_dir" "opencode"` → `.opencode/instructions.md`
- **Merge permission config**: Merge `seed/opencode_config.seed.json` into project's `opencode.json` (deep merge, add missing keys, preserve existing). Create `merge_opencode_settings()` function using Python JSON merge (simpler than TOML merge used for Codex).
- **Note:** OpenCode binary may be at `~/.opencode/bin/opencode` or on PATH — use `command -v opencode` for detection, no hardcoded paths.

## Reference Patterns

- `setup_codex_cli()` at `aiscripts/aitask_setup.sh:1393-1467`
- `merge_codex_settings()` at `aiscripts/aitask_setup.sh:1303-1390`
- `install_codex_staging()` at `install.sh:402`
- `install_seed_codex_config()` at `install.sh:427`
- Release workflow Codex block at `.github/workflows/release.yml:38`

## Verification

- `./ait setup` installs OpenCode wrappers when `opencode` binary is detected
- Skill count matches (17 wrappers)
- `.opencode/instructions.md` created with `>>>aitasks`/`<<<aitasks` markers
- `opencode.json` permissions merged correctly (existing settings preserved)
