---
priority: medium
effort: medium
depends: [t130_1]
issue_type: feature
status: Done
labels: [aitasks, codexcli]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-04 10:46
updated_at: 2026-03-05 09:12
completed_at: 2026-03-05 09:12
---

## Context

This is child task 2 of t130 (Codex CLI support). It updates the installation pipeline (release workflow, install.sh, ait setup) to package, distribute, and conditionally install Codex CLI skill wrappers and config.

Depends on t130_1 (skill wrappers must exist before they can be packaged).

## Architecture

The installation flow has 3 stages:
1. **Release** — `.agents/skills/` staged to `codex_skills/` in tarball; seed files in `seed/`
2. **install.sh** — stores staging files to `aitasks/metadata/` (permanent, for setup)
3. **ait setup** — conditionally copies from `aitasks/metadata/` to `.agents/skills/` and `.codex/`

Config uses a **merge** pattern (like Claude Code's `settings.local.json`): `seed/codex_config.seed.toml` gets merged into existing `.codex/config.toml` rather than overwriting.

## Key Files to Modify

### 1. `.github/workflows/release.yml`

Add a step between "Build skills directory" and "Create release tarball":

```yaml
- name: Build codex skills directory from .agents/skills
  run: |
    if [ -d .agents/skills ]; then
      mkdir -p codex_skills
      for skill_dir in .agents/skills/aitask-*/; do
        [ -d "$skill_dir" ] || continue
        skill_name="$(basename "$skill_dir")"
        cp -r "$skill_dir" "codex_skills/$skill_name"
      done
    fi
```

Update the tarball creation to include `codex_skills/`:
```yaml
tar -czf aitasks-${{ github.ref_name }}.tar.gz \
  ait CHANGELOG.md aiscripts/ skills/ seed/ codex_skills/
```

### 2. `install.sh`

Add two new functions after `install_seed_claude_settings()`:

**`install_codex_staging()`** — stores codex skill wrappers from `codex_skills/` staging dir to `aitasks/metadata/codex_skills/`:
- Loop over `codex_skills/aitask-*/` directories
- Copy each `SKILL.md` to `aitasks/metadata/codex_skills/<name>/SKILL.md`
- Clean up the `codex_skills/` staging dir

**`install_seed_codex_config()`** — stores seed files:
- Copy `seed/codex_config.seed.toml` to `aitasks/metadata/codex_config.seed.toml`
- Copy `seed/codex_instructions.seed.md` to `aitasks/metadata/codex_instructions.seed.md`

Call both in `main()` after `install_seed_claude_settings`.

Update `commit_installed_files()` to include `.agents/skills/` and `.codex/` in `check_paths`.

### 3. `aiscripts/aitask_setup.sh`

**Replace `setup_codex_cli()` placeholder** (lines 1250-1253) with:
- Check for staging files at `aitasks/metadata/codex_skills/`
- Count available skill wrappers
- Ask user for confirmation (Y/n prompt, auto-accept in non-interactive mode)
- Copy skill wrappers to `.agents/skills/`
- Merge config seed into `.codex/config.toml` (or create fresh)
- Copy instructions seed to `.codex/instructions.md` (don't overwrite existing)

**Add `merge_codex_settings()` function** (parallel to existing `merge_claude_settings()`):
- Uses Python with `tomllib` (3.11+) for reading TOML
- For writing: try `tomli_w` first, fallback to manual TOML serializer
- Deep merge logic: add seed key/values only where missing in existing config; extend `prefix_rules` arrays with new entries
- Pattern: identical to `merge_claude_settings()` but adapted for TOML

## Reference Files for Patterns

- `aiscripts/aitask_setup.sh:1149-1197` — `merge_claude_settings()` function (pattern to follow)
- `aiscripts/aitask_setup.sh:1200-1241` — `setup_claude_code()` function (pattern to follow)
- `install.sh:184-204` — `install_skills()` function (staging pattern)
- `install.sh:387-399` — `install_seed_claude_settings()` (seed storage pattern)
- `.github/workflows/release.yml:30-45` — existing skill staging and tarball creation

## Implementation Steps

1. Update `.github/workflows/release.yml` — add Codex staging step and update tarball
2. Add `install_codex_staging()` to `install.sh`
3. Add `install_seed_codex_config()` to `install.sh`
4. Update `commit_installed_files()` in `install.sh`
5. Add `merge_codex_settings()` to `aiscripts/aitask_setup.sh`
6. Replace `setup_codex_cli()` in `aiscripts/aitask_setup.sh`

## Verification

1. `shellcheck aiscripts/aitask_setup.sh` passes
2. `shellcheck install.sh` passes (if applicable)
3. Dry-run test: create a temp dir, run `setup_codex_cli` with staging files
4. Verify merge works: create test `.codex/config.toml`, run merge, check output
5. Verify release.yml includes `codex_skills/` in tarball
6. Verify conditional installation: user says "n" → no files copied
