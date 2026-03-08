---
priority: high
effort: medium
depends: [t131_2]
issue_type: feature
status: Implementing
labels: [geminicli]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-07 23:21
updated_at: 2026-03-08 08:50
---

Update setup script, install script, and release workflow to support Gemini CLI distribution.

## Context

The aitasks framework has a multi-stage installation pipeline:
1. **Release** (`.github/workflows/release.yml`) — Bundles agent skills into tarball
2. **Install** (`install.sh`) — Stages files from tarball to `aitasks/metadata/` staging dirs
3. **Setup** (`aiscripts/aitask_setup.sh`) — Copies from staging to final `.gemini/` location when agent is detected

This task implements all three stages for Gemini CLI. The setup function (`setup_gemini_cli()`) is currently a placeholder at `aitask_setup.sh:1297`.

Depends on t131_1 and t131_2 (the skill and command files must exist first).

## Key Files to Modify

- `aiscripts/aitask_setup.sh` — Replace placeholder `setup_gemini_cli()` with full implementation (~80 lines)
- `install.sh` — Add `install_gemini_staging()` and `install_seed_gemini_config()` functions (~40 lines each)
- `.github/workflows/release.yml` — Add Gemini CLI bundling step (~15 lines)

## Key Files to Create

- `seed/geminicli_instructions.seed.md` — Gemini-specific instructions layer

## Reference Files for Patterns

- `aiscripts/aitask_setup.sh:1524-1612` — `setup_opencode()` function (follow this pattern)
- `install.sh:427-461` — `install_opencode_staging()` function (follow this pattern)
- `install.sh:489-506` — `install_seed_opencode_config()` function (follow this pattern)
- `.github/workflows/release.yml:53-72` — OpenCode release bundling (follow this pattern)
- `seed/opencode_instructions.seed.md` — Pattern for instructions seed

## Implementation Plan

### Step 1: Create seed file

Create `seed/geminicli_instructions.seed.md` following `seed/opencode_instructions.seed.md`:
- Skills location: `.gemini/skills/`
- Commands location: `.gemini/commands/`
- Invoke syntax: `/skill-name` or custom command
- Agent identification: `geminicli/<model_name>` from `models_geminicli.json`

### Step 2: Implement `setup_gemini_cli()` in aitask_setup.sh

Replace the placeholder at line 1297 with a full implementation mirroring `setup_opencode()`:
1. Check for staging files in `aitasks/metadata/geminicli_skills/` and `aitasks/metadata/geminicli_commands/`
2. Ask user for confirmation (Y/n prompt)
3. Copy skill wrappers (aitask-*/SKILL.md + geminicli_tool_mapping.md + geminicli_planmode_prereqs.md)
4. Copy command wrappers
5. Assemble instructions: `assemble_aitasks_instructions "$project_dir" "geminicli"`
6. Insert into `GEMINI.md`: `insert_aitasks_instructions`
7. No config merge needed (unlike Codex/OpenCode)

### Step 3: Add install staging functions to install.sh

Add `install_gemini_staging()` after `install_opencode_staging()`:
- Stage skill dirs from `$INSTALL_DIR/gemini_skills/` to `$INSTALL_DIR/aitasks/metadata/geminicli_skills/`
- Copy shared docs (tool mapping, planmode prereqs)
- Stage command files from `$INSTALL_DIR/gemini_commands/` to `$INSTALL_DIR/aitasks/metadata/geminicli_commands/`

Add `install_seed_gemini_config()` after `install_seed_opencode_config()`:
- Stage `geminicli_instructions.seed.md` from `seed/` to `aitasks/metadata/`

Add calls to both functions in the main install flow (around line 718).

### Step 4: Update release workflow

Add a new step in `.github/workflows/release.yml` to bundle Gemini CLI files:
- Build `gemini_skills/` from `.gemini/skills/`
- Build `gemini_commands/` from `.gemini/commands/`
- Add both to the tarball

## Verification Steps

```bash
# Syntax check
bash -n aiscripts/aitask_setup.sh
bash -n install.sh

# Shellcheck
shellcheck aiscripts/aitask_setup.sh

# Verify setup function is no longer a placeholder
grep -A5 "setup_gemini_cli" aiscripts/aitask_setup.sh | head -10
```
