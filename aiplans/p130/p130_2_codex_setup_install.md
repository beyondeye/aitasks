---
Task: t130_2_codex_setup_install.md
Parent Task: aitasks/t130_codecli_support.md
Sibling Tasks: aitasks/t130/t130_1_codex_skill_wrappers.md, aitasks/t130/t130_3_codex_docs_update.md
Archived Sibling Plans: aiplans/archived/p130/p130_1_codex_skill_wrappers.md
Worktree: n/a (working on current branch)
Branch: main
Base branch: main
---

# Plan: Update Install Pipeline for Codex CLI (t130_2)

## Overview

Update the release workflow, install.sh, and ait setup to package, distribute, and conditionally install Codex CLI skill wrappers and config. This task depends on t130_1 (wrappers must exist first).

## Step 1: Update release workflow

**File:** `.github/workflows/release.yml`

Add a new step after "Build skills directory from .claude/skills" (line 36) and before "Create release tarball":

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

Update the tarball creation step to include `codex_skills/`:

```yaml
          tar -czf aitasks-${{ github.ref_name }}.tar.gz \
            ait \
            CHANGELOG.md \
            aiscripts/ \
            skills/ \
            seed/ \
            codex_skills/
```

Note: `seed/codex_config.seed.toml` and `seed/codex_instructions.seed.md` are already included via `seed/`.

## Step 2: Update install.sh — add staging functions

**File:** `install.sh`

Add after `install_seed_claude_settings()` function (line 399):

```bash
# --- Store Codex CLI staging files ---
install_codex_staging() {
    if [[ ! -d "$INSTALL_DIR/codex_skills" ]]; then
        return
    fi

    mkdir -p "$INSTALL_DIR/aitasks/metadata/codex_skills"

    for skill_dir in "$INSTALL_DIR/codex_skills"/aitask-*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name="$(basename "$skill_dir")"
        mkdir -p "$INSTALL_DIR/aitasks/metadata/codex_skills/$skill_name"
        cp "$skill_dir/SKILL.md" "$INSTALL_DIR/aitasks/metadata/codex_skills/$skill_name/SKILL.md"
    done

    rm -rf "$INSTALL_DIR/codex_skills"
    info "  Stored Codex CLI skills staging at aitasks/metadata/codex_skills/"
}

# --- Store Codex CLI config and instructions seeds ---
install_seed_codex_config() {
    local src="$INSTALL_DIR/seed/codex_config.seed.toml"
    local dest="$INSTALL_DIR/aitasks/metadata/codex_config.seed.toml"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored Codex CLI config seed"
    fi

    local src_inst="$INSTALL_DIR/seed/codex_instructions.seed.md"
    local dest_inst="$INSTALL_DIR/aitasks/metadata/codex_instructions.seed.md"
    if [[ -f "$src_inst" ]]; then
        cp "$src_inst" "$dest_inst"
        info "  Stored Codex CLI instructions seed"
    fi
}
```

Add calls in `main()` after line 598 (`install_seed_claude_settings`):

```bash
    info "Storing Codex CLI staging files..."
    install_codex_staging

    info "Storing Codex CLI config seed..."
    install_seed_codex_config
```

## Step 3: Update install.sh — commit_installed_files

**File:** `install.sh`, lines 498-504

Add `.agents/skills/` and `.codex/` to `check_paths`:

```bash
    local check_paths=(
        "aiscripts/"
        "aitasks/metadata/"
        "aireviewguides/"
        "ait"
        ".claude/skills/"
        ".agents/skills/"
        ".codex/"
    )
```

## Step 4: Add merge_codex_settings() to setup script

**File:** `aiscripts/aitask_setup.sh`

Add before the `setup_codex_cli()` function (around line 1248):

```bash
# --- Merge Codex CLI config.toml (add aitask-specific settings) ---
merge_codex_settings() {
    local seed_file="$1"
    local dest_file="$2"

    if ! command -v python3 &>/dev/null; then
        warn "python3 not found. Cannot merge Codex settings automatically."
        warn "Please manually merge $seed_file into $dest_file"
        return
    fi

    local merged=""
    merged="$(python3 -c "
import sys

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print('ERROR: No TOML parser available (need Python 3.11+ or tomli)', file=sys.stderr)
        sys.exit(1)

with open(sys.argv[1], 'rb') as f:
    existing = tomllib.load(f)
with open(sys.argv[2], 'rb') as f:
    seed = tomllib.load(f)

def deep_merge(base, overlay):
    result = dict(base)
    for key, value in overlay.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif isinstance(result[key], list) and isinstance(value, list):
            existing_strs = [str(item) for item in result[key]]
            for item in value:
                if str(item) not in existing_strs:
                    result[key].append(item)
    return result

merged = deep_merge(existing, seed)

try:
    import tomli_w
    sys.stdout.buffer.write(tomli_w.dumps(merged).encode())
except ImportError:
    def toml_serialize(d, prefix=''):
        lines = []
        tables = []
        array_tables = []
        for k, v in d.items():
            full_key = f'{prefix}.{k}' if prefix else k
            if isinstance(v, dict):
                tables.append((full_key, v))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                array_tables.append((full_key, v))
            elif isinstance(v, bool):
                lines.append(f'{k} = {str(v).lower()}')
            elif isinstance(v, str):
                lines.append(f'{k} = \"{v}\"')
            elif isinstance(v, (int, float)):
                lines.append(f'{k} = {v}')
            elif isinstance(v, list):
                items = ', '.join(f'\"{i}\"' if isinstance(i, str) else str(i) for i in v)
                lines.append(f'{k} = [{items}]')
        for line in lines:
            print(line)
        for full_key, table in tables:
            print(f'\\n[{full_key}]')
            toml_serialize(table, full_key)
        for full_key, entries in array_tables:
            for entry in entries:
                print(f'\\n[[{full_key}]]')
                toml_serialize(entry, full_key)
    toml_serialize(merged)
" "$dest_file" "$seed_file")"

    if [[ -n "$merged" ]]; then
        echo "$merged" > "$dest_file"
        info "  Merged aitask settings into .codex/config.toml"
    else
        warn "  Merge produced empty output — existing config unchanged"
    fi
}
```

## Step 5: Replace setup_codex_cli() placeholder

**File:** `aiscripts/aitask_setup.sh`, lines 1250-1253

Replace the placeholder with the full implementation:

```bash
# --- Codex CLI setup (skills + config + instructions) ---
setup_codex_cli() {
    local project_dir="$SCRIPT_DIR/.."
    local staging_skills="$project_dir/aitasks/metadata/codex_skills"
    local dest_skills="$project_dir/.agents/skills"
    local dest_codex="$project_dir/.codex"

    if [[ ! -d "$staging_skills" ]]; then
        info "No Codex CLI staging files found — skipping"
        info "  Re-run 'ait install' to get Codex CLI support files"
        return
    fi

    local count
    count=$(find "$staging_skills" -name "SKILL.md" -type f 2>/dev/null | wc -l | tr -d ' ')

    echo ""
    info "Found $count Codex CLI skill wrappers ready for installation."
    info "These wrap aitask Claude Code skills for use with Codex CLI (\$skill-name syntax)."
    echo ""

    if [[ -t 0 ]]; then
        printf "  Install Codex CLI skills and config? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"") ;;
        *)
            info "Skipped Codex CLI skill installation."
            return
            ;;
    esac

    # Copy skill wrappers
    mkdir -p "$dest_skills"
    local installed=0
    for skill_dir in "$staging_skills"/aitask-*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name="$(basename "$skill_dir")"
        mkdir -p "$dest_skills/$skill_name"
        cp "$skill_dir/SKILL.md" "$dest_skills/$skill_name/SKILL.md"
        installed=$((installed + 1))
    done
    success "  Installed $installed Codex CLI skill wrappers to .agents/skills/"

    # Merge config.toml seed
    local seed_config="$project_dir/aitasks/metadata/codex_config.seed.toml"
    local dest_config="$dest_codex/config.toml"
    if [[ -f "$seed_config" ]]; then
        mkdir -p "$dest_codex"
        if [[ ! -f "$dest_config" ]]; then
            cp "$seed_config" "$dest_config"
            info "  Created .codex/config.toml from seed"
        else
            info "  Existing .codex/config.toml found — merging aitask settings..."
            merge_codex_settings "$seed_config" "$dest_config"
        fi
    fi

    # Copy instructions.md (don't overwrite existing)
    local seed_instructions="$project_dir/aitasks/metadata/codex_instructions.seed.md"
    if [[ -f "$seed_instructions" ]]; then
        local dest_instructions="$dest_codex/instructions.md"
        mkdir -p "$dest_codex"
        if [[ ! -f "$dest_instructions" ]]; then
            cp "$seed_instructions" "$dest_instructions"
            info "  Created .codex/instructions.md"
        else
            info "  Existing .codex/instructions.md found — not overwriting"
        fi
    fi
}
```

## Verification

- [ ] `shellcheck aiscripts/aitask_setup.sh` passes
- [ ] `shellcheck install.sh` passes
- [ ] TOML merge works: create test config, run merge, verify output
- [ ] Release workflow YAML is valid
- [ ] Conditional install: user says "n" → no files copied
- [ ] Fresh install: no `.codex/config.toml` → copied from seed
- [ ] Existing install: `.codex/config.toml` exists → merged

## Step 9 Reference

After implementation, follow task-workflow Step 9 for archival and cleanup.
