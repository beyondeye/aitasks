---
Task: t319_2_opencode_setup_install.md
Parent Task: aitasks/t319_opencode_support.md
Sibling Tasks: aitasks/t319/t319_1_opencode_skill_wrappers.md, aitasks/t319/t319_3_opencode_docs_update.md, aitasks/t319/t319_4_opencode_model_discovery.md
Archived Sibling Plans: (none yet)
Worktree: (none - working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Update Release/Install/Setup Pipeline for OpenCode

## Overview

Extend the release workflow, install.sh, and ait setup to package, distribute, and install OpenCode skill wrappers — mirroring the Codex CLI pipeline.

## Step 1: Update release workflow

**File:** `.github/workflows/release.yml`

Add an OpenCode skills packaging block after the Codex block (~line 38):

```yaml
- name: Build opencode skills directory from .opencode/skills
  run: |
    if [ -d .opencode/skills ]; then
      mkdir -p opencode_skills
      for skill_dir in .opencode/skills/aitask-*/; do
        skill_name=$(basename "$skill_dir")
        cp -r "$skill_dir" "opencode_skills/$skill_name"
      done
      if [ -f .opencode/skills/opencode_tool_mapping.md ]; then
        cp .opencode/skills/opencode_tool_mapping.md opencode_skills/opencode_tool_mapping.md
      fi
    fi
```

Add `opencode_skills/` to the tarball file list (same section as `codex_skills/`).

## Step 2: Update install.sh

**File:** `install.sh`

### 2a: Add `install_opencode_staging()` (~after `install_codex_staging()` at line 423)

```bash
install_opencode_staging() {
    if [[ ! -d "$INSTALL_DIR/opencode_skills" ]]; then
        return
    fi
    mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_skills"
    for skill_dir in "$INSTALL_DIR/opencode_skills"/aitask-*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name="$(basename "$skill_dir")"
        mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_skills/$skill_name"
        cp "$skill_dir/SKILL.md" "$INSTALL_DIR/aitasks/metadata/opencode_skills/$skill_name/SKILL.md"
    done
    if [[ -f "$INSTALL_DIR/opencode_skills/opencode_tool_mapping.md" ]]; then
        cp "$INSTALL_DIR/opencode_skills/opencode_tool_mapping.md" "$INSTALL_DIR/aitasks/metadata/opencode_skills/opencode_tool_mapping.md"
    fi
    rm -rf "$INSTALL_DIR/opencode_skills"
    info "  Stored OpenCode skills staging at aitasks/metadata/opencode_skills/"
}
```

### 2b: Add `install_seed_opencode_config()` (~after `install_seed_codex_config()`)

```bash
install_seed_opencode_config() {
    local src dest
    # OpenCode config seed
    src="$INSTALL_DIR/seed/opencode_config.seed.json"
    dest="$INSTALL_DIR/aitasks/metadata/opencode_config.seed.json"
    [[ -f "$src" ]] && cp "$src" "$dest" && info "  Stored opencode_config.seed.json"

    # OpenCode instructions seed
    src="$INSTALL_DIR/seed/opencode_instructions.seed.md"
    dest="$INSTALL_DIR/aitasks/metadata/opencode_instructions.seed.md"
    [[ -f "$src" ]] && cp "$src" "$dest" && info "  Stored opencode_instructions.seed.md"
}
```

### 2c: Call both from main install flow (~line 654)

Add after `install_seed_codex_config`:
```bash
install_opencode_staging
install_seed_opencode_config
```

### 2d: Update `commit_installed_files()` to check `.opencode/skills/`

Add `.opencode/skills/` and `.opencode/` to the list of directories checked.

## Step 3: Implement `setup_opencode()` in ait setup

**File:** `aiscripts/aitask_setup.sh` (~line 1470, replacing placeholder)

Mirror `setup_codex_cli()` (lines 1393-1467):

```bash
setup_opencode() {
    local project_dir="$SCRIPT_DIR/.."
    local staging_skills="$project_dir/aitasks/metadata/opencode_skills"
    local dest_skills="$project_dir/.opencode/skills"
    local dest_opencode="$project_dir/.opencode"

    if [[ ! -d "$staging_skills" ]]; then
        info "No OpenCode staging files found — skipping"
        info "  Re-run 'ait install' to get OpenCode support files"
        return
    fi

    local count
    count=$(find "$staging_skills" -name "SKILL.md" -type f 2>/dev/null | wc -l | tr -d ' ')

    echo ""
    info "Found $count OpenCode skill wrappers ready for installation."
    echo ""

    if [[ -t 0 ]]; then
        printf "  Install OpenCode skills and config? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"") ;;
        *)
            info "Skipped OpenCode skill installation."
            return
            ;;
    esac

    # 1. Copy skill wrappers
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
    # Copy shared tool mapping file
    if [[ -f "$staging_skills/opencode_tool_mapping.md" ]]; then
        cp "$staging_skills/opencode_tool_mapping.md" "$dest_skills/opencode_tool_mapping.md"
    fi
    success "  Installed $installed OpenCode skill wrappers to .opencode/skills/"

    # 2. Assemble and insert instructions (Layer 1 + Layer 2, with markers)
    local content
    content="$(assemble_aitasks_instructions "$project_dir" "opencode")" || true
    if [[ -n "$content" ]]; then
        mkdir -p "$dest_opencode"
        local dest_instructions="$dest_opencode/instructions.md"
        insert_aitasks_instructions "$dest_instructions" "$content"
        info "  Installed .opencode/instructions.md (with aitasks markers)"
    fi

    # 3. Merge opencode.json permission seed
    local seed_config="$project_dir/aitasks/metadata/opencode_config.seed.json"
    if [[ -f "$seed_config" ]]; then
        local dest_config="$project_dir/opencode.json"
        if [[ ! -f "$dest_config" ]]; then
            cp "$seed_config" "$dest_config"
            info "  Created opencode.json from seed"
        else
            info "  Existing opencode.json found — merging aitask settings..."
            merge_opencode_settings "$seed_config" "$dest_config"
        fi
    fi
}
```

### 3b: Create `merge_opencode_settings()` function

Add before `setup_opencode()`. Uses Python JSON merge (simpler than TOML merge for Codex):

```bash
merge_opencode_settings() {
    local seed_file="$1"
    local dest_file="$2"

    local python_cmd=""
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        python_cmd="$VENV_DIR/bin/python"
    elif command -v python3 &>/dev/null; then
        python_cmd="python3"
    else
        warn "python3 not found. Cannot merge OpenCode settings automatically."
        warn "Please manually merge $seed_file into $dest_file"
        return
    fi

    local merged=""
    merged="$("$python_cmd" -c "
import json, sys

with open(sys.argv[1]) as f:
    existing = json.load(f)
with open(sys.argv[2]) as f:
    seed = json.load(f)

def deep_merge(base, overlay):
    result = dict(base)
    for key, value in overlay.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif isinstance(result[key], list) and isinstance(value, list):
            existing_items = [str(item) for item in result[key]]
            for item in value:
                if str(item) not in existing_items:
                    result[key].append(item)
    return result

merged = deep_merge(existing, seed)
print(json.dumps(merged, indent=2))
" "$dest_file" "$seed_file")"

    if [[ -n "$merged" ]]; then
        echo "$merged" > "$dest_file"
        info "  Merged aitask settings into opencode.json"
    else
        warn "  Merge produced empty output — existing config unchanged"
    fi
}
```

## Step 4: Verify `assemble_aitasks_instructions()` handles "opencode"

Check that `assemble_aitasks_instructions()` at line 822 looks for `seed/opencode_instructions.seed.md` when agent_type is "opencode". The function already uses the pattern `seed/${agent_type}_instructions.seed.md`, so it should work if the seed file exists. Verify this.

## Step 5: Commit

```bash
git add .github/workflows/release.yml install.sh aiscripts/aitask_setup.sh
git commit -m "feature: Add OpenCode setup/install pipeline (t319_2)"
```

## Verification

- [ ] `.github/workflows/release.yml` packages `opencode_skills/` in tarball
- [ ] `install.sh` stages OpenCode wrappers and seed files
- [ ] `./ait setup` prompts "Install OpenCode skills and config? [Y/n]" when opencode is detected
- [ ] After setup: `.opencode/skills/` has 17 wrappers + tool mapping
- [ ] After setup: `.opencode/instructions.md` has aitasks markers
- [ ] After setup: `opencode.json` has merged permissions (existing settings preserved)
- [ ] `wc -l` usage stripped with `| tr -d ' '` (macOS portability)

## Post-Implementation: Step 9

Follow task-workflow Step 9 for archival.
