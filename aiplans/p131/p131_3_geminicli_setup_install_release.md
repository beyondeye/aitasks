---
Task: t131_3_geminicli_setup_install_release.md
Parent Task: aitasks/t131_geminicli_support.md
Sibling Tasks: aitasks/t131/t131_1_*.md, aitasks/t131/t131_2_*.md, aitasks/t131/t131_4_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Gemini CLI Setup, Install, and Release Pipeline (t131_3)

## Overview

Update 3 existing scripts, create 1 seed file, and add automated tests to integrate Gemini CLI into the distribution pipeline.

**Verified against codebase (2026-03-08):** All assumptions confirmed. Line numbers accurate within ±1-2. Note: `assemble_aitasks_instructions` comment at line 823 says "gemini" but naming convention uses "geminicli" — will update.

## Step 1: Create `seed/geminicli_instructions.seed.md`

Follow `seed/opencode_instructions.seed.md` pattern:

```markdown
# aitasks Framework — Gemini CLI Instructions

For shared aitasks conventions (task file format, task hierarchy,
git operations, commit message format), see `seed/aitasks_agent_instructions.seed.md`.
During `ait setup`, those conventions are installed directly into this file.

The sections below are Gemini CLI-specific additions.

## Skills

aitasks skills are available in `.gemini/skills/`. Each skill is a wrapper
that references the authoritative Claude Code skill in `.claude/skills/`.
Read the wrapper for tool mapping guidance.

Custom commands are also available in `.gemini/commands/`.

## Agent Identification

When recording `implemented_with` in task metadata, identify as
`geminicli/<model_name>`. Read `aitasks/metadata/models_geminicli.json` to find the
matching `name` for your model ID. Construct as `geminicli/<name>`.
```

## Step 2: Implement `setup_gemini_cli()` in `aiscripts/aitask_setup.sh`

Replace the placeholder at line 1297-1300 with full implementation. Follow `setup_opencode()` (lines 1524-1612):

```bash
setup_gemini_cli() {
    local project_dir="$SCRIPT_DIR/.."
    local staging_skills="$project_dir/aitasks/metadata/geminicli_skills"
    local staging_commands="$project_dir/aitasks/metadata/geminicli_commands"
    local dest_skills="$project_dir/.gemini/skills"
    local dest_commands="$project_dir/.gemini/commands"

    # Check staging files exist
    if [[ ! -d "$staging_skills" && ! -d "$staging_commands" ]]; then
        info "No Gemini CLI staging files found — skipping"
        info "  Re-run 'ait install' to get Gemini CLI support files"
        return
    fi

    # Count and prompt
    local count
    count=$(find "$staging_skills" -name "SKILL.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo ""
    info "Found $count Gemini CLI skill wrappers ready for installation."
    echo ""
    # Y/n prompt (interactive / non-interactive)

    # 1. Copy skill wrappers + shared docs
    # 2. Copy command wrappers
    # 3. Assemble and insert instructions into GEMINI.md
    #    content="$(assemble_aitasks_instructions "$project_dir" "geminicli")" || true
    #    insert_aitasks_instructions "$project_dir/GEMINI.md" "$content"
    # No config merge needed (no permissions/settings config for Gemini CLI)
}
```

## Step 3: Add install staging functions to `install.sh`

### `install_gemini_staging()` (after `install_opencode_staging()` ~line 461)

Follow `install_opencode_staging()` pattern:
- Stage skills from `$INSTALL_DIR/gemini_skills/` to `$INSTALL_DIR/aitasks/metadata/geminicli_skills/`
- Stage commands from `$INSTALL_DIR/gemini_commands/` to `$INSTALL_DIR/aitasks/metadata/geminicli_commands/`

### `install_seed_gemini_config()` (after `install_seed_opencode_config()` ~line 506)

Follow `install_seed_opencode_config()` pattern:
- Stage `geminicli_instructions.seed.md` from `seed/` to `aitasks/metadata/`

### Add calls in main install flow (~line 718)

After the OpenCode staging calls:
```bash
info "Storing Gemini CLI staging files..."
install_gemini_staging

info "Storing Gemini CLI config seeds..."
install_seed_gemini_config
```

## Step 4: Update `.github/workflows/release.yml`

Add a new step after the OpenCode bundling step (~line 72):

```yaml
- name: Build gemini skills directory from .gemini/skills
  run: |
    mkdir -p gemini_commands
    if [ -d .gemini/commands ]; then
      cp -r .gemini/commands/. gemini_commands/
    fi
    if [ -d .gemini/skills ]; then
      mkdir -p gemini_skills
      for skill_dir in .gemini/skills/aitask-*/; do
        [ -d "$skill_dir" ] || continue
        skill_name="$(basename "$skill_dir")"
        cp -r "$skill_dir" "gemini_skills/$skill_name"
      done
      if [ -f .gemini/skills/geminicli_tool_mapping.md ]; then
        cp .gemini/skills/geminicli_tool_mapping.md gemini_skills/geminicli_tool_mapping.md
      fi
      if [ -f .gemini/skills/geminicli_planmode_prereqs.md ]; then
        cp .gemini/skills/geminicli_planmode_prereqs.md gemini_skills/geminicli_planmode_prereqs.md
      fi
    fi
```

Add `gemini_skills/` and `gemini_commands/` to the tarball command (~line 84).

## Step 5: Create `tests/test_gemini_setup.sh`

Mirror `tests/test_opencode_setup.sh` with Gemini CLI equivalents. 6 tests (no JSON merge — Gemini CLI has no config file):

1. **Packaging** — 17 skill wrappers + tool mapping + planmode prereqs + 17 commands
2. **Staging** — skills/commands to `aitasks/metadata/geminicli_*/`, source cleaned up
3. **Instruction assembly** — Layer 1 + Layer 2 with agent_type `"geminicli"`
4. **Marker insertion** — `>>>aitasks`/`<<<aitasks` markers in new file
5. **Idempotency** — re-insert same content, unchanged
6. **User content preservation** — existing content survives insert + update

## Verification

```bash
bash -n .aitask-scripts/aitask_setup.sh
bash -n install.sh
bash tests/test_gemini_setup.sh
```

## Final Implementation Notes

- **Actual work done:** Created `seed/geminicli_instructions.seed.md`, replaced `setup_gemini_cli()` placeholder with full implementation (~73 lines) mirroring `setup_opencode()`, added `install_gemini_staging()` and `install_seed_gemini_config()` to `install.sh` with main flow calls, added Gemini CLI bundling step and tarball entries to release workflow, created `tests/test_gemini_setup.sh` with 26 assertions (all passing).
- **Deviations from plan:** Added Step 5 (automated tests) during plan verification — not in original plan. Updated `assemble_aitasks_instructions` comment from "gemini" to "geminicli" at line 823.
- **Issues encountered:** None.
- **Key decisions:** Used agent_type `"geminicli"` (not `"gemini"`) for consistency with naming conventions (`models_geminicli.json`, `geminicli_skills/`, etc.). Instructions insert into `GEMINI.md` at project root (like Claude Code's `CLAUDE.md`) rather than `.gemini/instructions.md` (like OpenCode). No config merge step needed — Gemini CLI has no equivalent of `opencode.json` or `codex_config.toml`.
- **Notes for sibling tasks:** The distribution pipeline is now complete for Gemini CLI. t131_4 (website docs) can reference the full pipeline when documenting Gemini CLI support. The `seed/geminicli_instructions.seed.md` file follows the same Layer 2 pattern as codex/opencode. Test file `tests/test_gemini_setup.sh` follows `tests/test_opencode_setup.sh` pattern exactly (minus JSON merge test).

## Post-Implementation

- Refer to Step 9 (Post-Implementation) in `.claude/skills/task-workflow/SKILL.md`
