#!/usr/bin/env bash
set -euo pipefail

# install.sh - Curl-friendly bootstrap installer for the aitask framework
# Usage: curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
#   or:  bash install.sh [--force] [--dir PATH] [--local-tarball PATH]

REPO="beyondeye/aitasks"
INSTALL_DIR="."
FORCE=false
LOCAL_TARBALL=""

# --- Color helpers ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[ait]${NC} $1"; }
success() { echo -e "${GREEN}[ait]${NC} $1"; }
warn()    { echo -e "${YELLOW}[ait]${NC} $1"; }
die()     { echo -e "${RED}[ait] Error:${NC} $1" >&2; exit 1; }

# --- Usage ---
usage() {
    cat <<EOF
Usage: install.sh [OPTIONS]

Install the aitask framework into a project directory.

Options:
  --force             Overwrite existing framework files (preserves data dirs)
  --dir PATH          Install to PATH instead of current directory
  --local-tarball PATH  Use a local tarball instead of downloading from GitHub
  --help              Show this help message

Examples:
  curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | bash
  bash install.sh --dir ~/my-project
  bash install.sh --force
  bash install.sh --local-tarball ./aitasks-0.1.0.tar.gz
EOF
    exit 0
}

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        --dir)
            [[ $# -ge 2 ]] || die "--dir requires a path argument"
            INSTALL_DIR="$2"
            shift 2
            ;;
        --local-tarball)
            [[ $# -ge 2 ]] || die "--local-tarball requires a path argument"
            LOCAL_TARBALL="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            die "Unknown option: $1. Use --help for usage."
            ;;
    esac
done

# Resolve INSTALL_DIR to absolute path
INSTALL_DIR="$(cd "$INSTALL_DIR" 2>/dev/null && pwd)" || die "Directory does not exist: $INSTALL_DIR"

# --- Prerequisites check ---
check_prerequisites() {
    if ! command -v tar &>/dev/null; then
        die "tar is required but not found. Install it and try again."
    fi

    DOWNLOAD_CMD=""
    if command -v curl &>/dev/null; then
        DOWNLOAD_CMD="curl"
    elif command -v wget &>/dev/null; then
        DOWNLOAD_CMD="wget"
    fi

    if [[ -z "$LOCAL_TARBALL" && -z "$DOWNLOAD_CMD" ]]; then
        die "curl or wget is required for downloading. Install one and try again."
    fi
}

# --- Safety check ---
check_existing_install() {
    if [[ -f "$INSTALL_DIR/ait" || -d "$INSTALL_DIR/.aitask-scripts" ]]; then
        if $FORCE; then
            warn "Existing installation found. --force specified, overwriting framework files..."
        else
            die "aitasks already installed in $INSTALL_DIR (found ait or .aitask-scripts/). Use --force to overwrite."
        fi
    fi
}

# --- Interactive confirmation ---
confirm_install() {
    # When piped (curl | bash), stdin is not a terminal — skip prompt
    if [[ -t 0 ]]; then
        echo ""
        info "Will install aitasks framework to: $INSTALL_DIR"

        # Check if this looks like a git repo root
        if git -C "$INSTALL_DIR" rev-parse --is-inside-work-tree &>/dev/null; then
            local git_root
            git_root="$(git -C "$INSTALL_DIR" rev-parse --show-toplevel 2>/dev/null)" || true
            if [[ -n "$git_root" && "$git_root" != "$INSTALL_DIR" ]]; then
                warn "You are inside a git repository, but not at its root."
                info "  Git root: $git_root"
                info "  Current:  $INSTALL_DIR"
                info "aitasks should be installed at the git repository root."
                printf "  Continue installing here anyway? [y/N] "
                read -r answer
                case "${answer:-N}" in
                    [Yy]*) ;;
                    *) info "Aborted. Re-run from: $git_root"; exit 0 ;;
                esac
                return
            fi
        else
            warn "No git repository found in $INSTALL_DIR"
            info "aitasks is tightly integrated with git — task IDs, locking, and"
            info "sync all require a git repository. You should install aitasks at"
            info "the root of the project where you want to manage tasks."
            info ""
            info "If this is a new project, 'ait setup' will offer to run 'git init'."
        fi

        printf "  Install here? [Y/n] "
        read -r answer
        case "${answer:-Y}" in
            [Yy]*|"") ;;
            *) info "Aborted."; exit 0 ;;
        esac
    fi
}

# --- Download tarball ---
download_tarball() {
    local dest="$1"

    if [[ -n "$LOCAL_TARBALL" ]]; then
        [[ -f "$LOCAL_TARBALL" ]] || die "Local tarball not found: $LOCAL_TARBALL"
        cp "$LOCAL_TARBALL" "$dest"
        return
    fi

    info "Fetching latest release from GitHub..."

    local api_response=""
    if [[ "$DOWNLOAD_CMD" == "curl" ]]; then
        api_response="$(curl -sS --max-time 15 "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null)" || true
    else
        api_response="$(wget -qO- --timeout=15 "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null)" || true
    fi

    if [[ -z "$api_response" ]]; then
        die "Could not reach GitHub API. Download manually from: https://github.com/$REPO/releases"
    fi

    local tarball_url=""
    tarball_url="$(echo "$api_response" \
        | grep '"browser_download_url".*\.tar\.gz"' \
        | head -1 \
        | sed 's/.*"\(http[^"]*\)".*/\1/')" || true

    if [[ -z "$tarball_url" ]]; then
        die "Could not find release tarball. Download manually from: https://github.com/$REPO/releases"
    fi

    info "Downloading: $tarball_url"

    if [[ "$DOWNLOAD_CMD" == "curl" ]]; then
        curl -sSL --max-time 120 "$tarball_url" -o "$dest" || die "Download failed."
    else
        wget -q --timeout=120 "$tarball_url" -O "$dest" || die "Download failed."
    fi
}

# --- Install skills ---
install_skills() {
    if [[ ! -d "$INSTALL_DIR/skills" ]]; then
        warn "No skills/ directory in tarball — skipping skill installation"
        return
    fi

    mkdir -p "$INSTALL_DIR/.claude/skills"

    for skill_dir in "$INSTALL_DIR/skills"/*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name="$(basename "$skill_dir")"
        mkdir -p "$INSTALL_DIR/.claude/skills/$skill_name"
        cp -r "$skill_dir". "$INSTALL_DIR/.claude/skills/$skill_name/"
        info "  Installed skill: $skill_name"
    done

    # Clean up staging directory
    rm -rf "$INSTALL_DIR/skills"
}

# --- Create data directories ---
create_data_dirs() {
    mkdir -p "$INSTALL_DIR/aitasks/metadata"
    mkdir -p "$INSTALL_DIR/aitasks/metadata/profiles"
    mkdir -p "$INSTALL_DIR/aitasks/archived"
    mkdir -p "$INSTALL_DIR/aiplans/archived"
    mkdir -p "$INSTALL_DIR/aireviewguides"
}

# --- Merge seed file into destination (preserve existing user values) ---
# Usage: merge_seed <mode> <src> <dest> <label>
# Modes: yaml | json | text-union
# - If dest is missing: straight copy.
# - If dest exists and FORCE=true: merge via aitask_install_merge.py (existing
#   dest values win, new seed keys are added).
# - If dest exists and FORCE!=true: keep existing dest untouched.
merge_seed() {
    local mode="$1" src="$2" dest="$3" label="$4"
    if [[ ! -f "$dest" ]]; then
        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
        info "  Installed $label"
        return
    fi
    if [[ "$FORCE" != true ]]; then
        info "  $label exists (kept)"
        return
    fi
    if python3 "$INSTALL_DIR/.aitask-scripts/aitask_install_merge.py" "$mode" "$src" "$dest" 2>/dev/null; then
        info "  Merged $label (kept existing values, added new seed keys)"
    else
        warn "  Merge failed for $label — leaving existing file untouched"
    fi
}

# --- Install scoped .aitask-scripts/.gitignore ---
# Framework-owned gitignore that prevents Python cache artifacts from leaking
# into downstream project repos. Unconditionally overwritten each install.
install_seed_aitask_scripts_gitignore() {
    local src="$INSTALL_DIR/seed/aitask_scripts_gitignore.seed"
    local dest="$INSTALL_DIR/.aitask-scripts/.gitignore"
    if [[ ! -f "$src" ]]; then
        warn "No seed/aitask_scripts_gitignore.seed in tarball — skipping"
        return
    fi
    cp "$src" "$dest"
    info "  Installed .aitask-scripts/.gitignore"
}

# --- Install seed profiles ---
install_seed_profiles() {
    if [[ ! -d "$INSTALL_DIR/seed/profiles" ]]; then
        warn "No seed/profiles/ directory in tarball — skipping profile installation"
        return
    fi

    mkdir -p "$INSTALL_DIR/aitasks/metadata/profiles"

    for profile in "$INSTALL_DIR/seed/profiles"/*.yaml; do
        [[ -f "$profile" ]] || continue
        local bname
        bname="$(basename "$profile")"
        local dest="$INSTALL_DIR/aitasks/metadata/profiles/$bname"
        merge_seed yaml "$profile" "$dest" "profile: $bname"
    done

}

# --- Install seed task types ---
install_seed_task_types() {
    local src="$INSTALL_DIR/seed/task_types.txt"
    local dest="$INSTALL_DIR/aitasks/metadata/task_types.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/task_types.txt in tarball — skipping task types installation"
        return
    fi

    merge_seed text-union "$src" "$dest" "task types: task_types.txt"
}

# --- Install seed project config ---
install_seed_project_config() {
    local src="$INSTALL_DIR/seed/project_config.yaml"
    local dest="$INSTALL_DIR/aitasks/metadata/project_config.yaml"

    if [[ ! -f "$src" ]]; then
        warn "No seed/project_config.yaml in tarball — skipping project config installation"
        return
    fi

    merge_seed yaml "$src" "$dest" "project config: project_config.yaml"
}

# --- Install seed review types ---
install_seed_reviewtypes() {
    local src="$INSTALL_DIR/seed/reviewguides/reviewtypes.txt"
    local dest="$INSTALL_DIR/aireviewguides/reviewtypes.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/reviewguides/reviewtypes.txt in tarball — skipping review types installation"
        return
    fi

    merge_seed text-union "$src" "$dest" "review types: reviewtypes.txt"
}

# --- Install seed review labels ---
install_seed_reviewlabels() {
    local src="$INSTALL_DIR/seed/reviewguides/reviewlabels.txt"
    local dest="$INSTALL_DIR/aireviewguides/reviewlabels.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/reviewguides/reviewlabels.txt in tarball — skipping review labels installation"
        return
    fi

    merge_seed text-union "$src" "$dest" "review labels: reviewlabels.txt"
}

# --- Install seed review environments ---
install_seed_reviewenvironments() {
    local src="$INSTALL_DIR/seed/reviewguides/reviewenvironments.txt"
    local dest="$INSTALL_DIR/aireviewguides/reviewenvironments.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/reviewguides/reviewenvironments.txt in tarball — skipping review environments installation"
        return
    fi

    merge_seed text-union "$src" "$dest" "review environments: reviewenvironments.txt"
}

# --- Install seed review guides ---
# Review guides are user-editable prose. Never overwrite an existing guide, even
# on --force: only install guides whose destination does not yet exist.
install_seed_reviewguides() {
    if [[ ! -d "$INSTALL_DIR/seed/reviewguides" ]]; then
        warn "No seed/reviewguides/ directory in tarball — skipping review guide installation"
        return
    fi

    mkdir -p "$INSTALL_DIR/aireviewguides"

    while IFS= read -r -d '' mode_file; do
        local rel_path="${mode_file#$INSTALL_DIR/seed/reviewguides/}"
        local dest="$INSTALL_DIR/aireviewguides/$rel_path"
        mkdir -p "$(dirname "$dest")"
        if [[ -f "$dest" ]]; then
            info "  Review guide exists (kept): $rel_path"
        else
            cp "$mode_file" "$dest"
            info "  Installed review guide: $rel_path"
        fi
    done < <(find "$INSTALL_DIR/seed/reviewguides" -name "*.md" -type f -print0 2>/dev/null)

    local src_ignore="$INSTALL_DIR/seed/reviewguides/.reviewguidesignore"
    local dest_ignore="$INSTALL_DIR/aireviewguides/.reviewguidesignore"
    if [[ -f "$src_ignore" ]]; then
        if [[ -f "$dest_ignore" ]]; then
            info "  Filter file exists (kept): .reviewguidesignore"
        else
            cp "$src_ignore" "$dest_ignore"
            info "  Installed filter file: .reviewguidesignore"
        fi
    fi
}

# --- Install seed code agent configuration ---
install_seed_codeagent_config() {
    local src="$INSTALL_DIR/seed/codeagent_config.json"
    local dest="$INSTALL_DIR/aitasks/metadata/codeagent_config.json"

    if [[ ! -f "$src" ]]; then
        warn "No seed/codeagent_config.json in tarball — skipping"
        return
    fi

    merge_seed json "$src" "$dest" "code agent config: codeagent_config.json"
}

# --- Install seed model configuration files ---
install_seed_models() {
    local found=false

    for src in "$INSTALL_DIR/seed"/models_*.json; do
        [[ -f "$src" ]] || continue
        found=true
        local bname
        bname="$(basename "$src")"
        local dest="$INSTALL_DIR/aitasks/metadata/$bname"
        merge_seed json "$src" "$dest" "model config: $bname"
    done

    if [[ "$found" == false ]]; then
        warn "No seed/models_*.json files in tarball — skipping model installation"
    fi
}

# --- Install seed Claude Code permissions ---
install_seed_claude_settings() {
    local src="$INSTALL_DIR/seed/claude_settings.local.json"
    local dest="$INSTALL_DIR/aitasks/metadata/claude_settings.seed.json"

    if [[ ! -f "$src" ]]; then
        warn "No seed/claude_settings.local.json in tarball — skipping"
        return
    fi

    cp "$src" "$dest"
    info "  Stored Claude Code permissions seed at aitasks/metadata/claude_settings.seed.json"
}

# --- Store Codex CLI staging files ---
install_codex_staging() {
    if [[ ! -d "$INSTALL_DIR/codex_skills" ]]; then
        return
    fi

    mkdir -p "$INSTALL_DIR/aitasks/metadata/codex_skills"

    for skill_dir in "$INSTALL_DIR/codex_skills"/*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name="$(basename "$skill_dir")"
        mkdir -p "$INSTALL_DIR/aitasks/metadata/codex_skills/$skill_name"
        cp -r "$skill_dir". "$INSTALL_DIR/aitasks/metadata/codex_skills/$skill_name/"
    done

    # Copy shared helper docs (codex + gemini)
    for doc in codex_tool_mapping.md codex_interactive_prereqs.md geminicli_tool_mapping.md geminicli_planmode_prereqs.md; do
        if [[ -f "$INSTALL_DIR/codex_skills/$doc" ]]; then
            cp "$INSTALL_DIR/codex_skills/$doc" "$INSTALL_DIR/aitasks/metadata/codex_skills/$doc"
        fi
    done

    rm -rf "$INSTALL_DIR/codex_skills"
    info "  Stored Codex CLI skills staging at aitasks/metadata/codex_skills/"
}

# --- Store OpenCode staging files ---
install_opencode_staging() {
    if [[ ! -d "$INSTALL_DIR/opencode_skills" && ! -d "$INSTALL_DIR/opencode_commands" ]]; then
        return
    fi

    if [[ -d "$INSTALL_DIR/opencode_skills" ]]; then
        mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_skills"

        for skill_dir in "$INSTALL_DIR/opencode_skills"/*/; do
            [[ -d "$skill_dir" ]] || continue
            local skill_name
            skill_name="$(basename "$skill_dir")"
            mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_skills/$skill_name"
            cp -r "$skill_dir". "$INSTALL_DIR/aitasks/metadata/opencode_skills/$skill_name/"
        done

        # Copy shared OpenCode helper docs
        if [[ -f "$INSTALL_DIR/opencode_skills/opencode_tool_mapping.md" ]]; then
            cp "$INSTALL_DIR/opencode_skills/opencode_tool_mapping.md" "$INSTALL_DIR/aitasks/metadata/opencode_skills/opencode_tool_mapping.md"
        fi
        if [[ -f "$INSTALL_DIR/opencode_skills/opencode_planmode_prereqs.md" ]]; then
            cp "$INSTALL_DIR/opencode_skills/opencode_planmode_prereqs.md" "$INSTALL_DIR/aitasks/metadata/opencode_skills/opencode_planmode_prereqs.md"
        fi

        rm -rf "$INSTALL_DIR/opencode_skills"
        info "  Stored OpenCode skills staging at aitasks/metadata/opencode_skills/"
    fi

    if [[ -d "$INSTALL_DIR/opencode_commands" ]]; then
        mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_commands"
        cp -r "$INSTALL_DIR/opencode_commands/." "$INSTALL_DIR/aitasks/metadata/opencode_commands/"
        rm -rf "$INSTALL_DIR/opencode_commands"
        info "  Stored OpenCode commands staging at aitasks/metadata/opencode_commands/"
    fi
}

# --- Store Codex CLI config and instructions seeds ---
install_seed_codex_config() {
    local src dest

    src="$INSTALL_DIR/seed/codex_config.seed.toml"
    dest="$INSTALL_DIR/aitasks/metadata/codex_config.seed.toml"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored Codex CLI config seed"
    fi

    src="$INSTALL_DIR/seed/codex_instructions.seed.md"
    dest="$INSTALL_DIR/aitasks/metadata/codex_instructions.seed.md"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored Codex CLI instructions seed"
    fi

    src="$INSTALL_DIR/seed/aitasks_agent_instructions.seed.md"
    dest="$INSTALL_DIR/aitasks/metadata/aitasks_agent_instructions.seed.md"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored shared agent instructions seed"
    fi
}

# --- Store Gemini CLI staging files ---
install_gemini_staging() {
    if [[ ! -d "$INSTALL_DIR/gemini_skills" && ! -d "$INSTALL_DIR/gemini_commands" \
          && ! -d "$INSTALL_DIR/gemini_policies" && ! -f "$INSTALL_DIR/gemini_settings.json" ]]; then
        return
    fi

    if [[ -d "$INSTALL_DIR/gemini_skills" ]]; then
        # Only stage helper docs (skill wrappers are now unified in codex_skills)
        mkdir -p "$INSTALL_DIR/aitasks/metadata/geminicli_skills"
        for doc in geminicli_tool_mapping.md geminicli_planmode_prereqs.md; do
            if [[ -f "$INSTALL_DIR/gemini_skills/$doc" ]]; then
                cp "$INSTALL_DIR/gemini_skills/$doc" "$INSTALL_DIR/aitasks/metadata/geminicli_skills/$doc"
            fi
        done

        rm -rf "$INSTALL_DIR/gemini_skills"
        info "  Stored Gemini CLI helper docs staging at aitasks/metadata/geminicli_skills/"
    fi

    if [[ -d "$INSTALL_DIR/gemini_commands" ]]; then
        mkdir -p "$INSTALL_DIR/aitasks/metadata/geminicli_commands"
        cp -r "$INSTALL_DIR/gemini_commands/." "$INSTALL_DIR/aitasks/metadata/geminicli_commands/"
        rm -rf "$INSTALL_DIR/gemini_commands"
        info "  Stored Gemini CLI commands staging at aitasks/metadata/geminicli_commands/"
    fi

    if [[ -d "$INSTALL_DIR/gemini_policies" ]]; then
        mkdir -p "$INSTALL_DIR/aitasks/metadata/geminicli_policies"
        cp -r "$INSTALL_DIR/gemini_policies/." "$INSTALL_DIR/aitasks/metadata/geminicli_policies/"
        rm -rf "$INSTALL_DIR/gemini_policies"
        info "  Stored Gemini CLI policies staging at aitasks/metadata/geminicli_policies/"
    fi

    if [[ -f "$INSTALL_DIR/gemini_settings.json" ]]; then
        cp "$INSTALL_DIR/gemini_settings.json" "$INSTALL_DIR/aitasks/metadata/geminicli_settings.seed.json"
        rm -f "$INSTALL_DIR/gemini_settings.json"
        info "  Stored Gemini CLI settings seed at aitasks/metadata/geminicli_settings.seed.json"
    fi
}

# --- Store OpenCode config and instructions seeds ---
install_seed_opencode_config() {
    local src dest

    src="$INSTALL_DIR/seed/opencode_config.seed.json"
    dest="$INSTALL_DIR/aitasks/metadata/opencode_config.seed.json"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored OpenCode config seed"
    fi

    src="$INSTALL_DIR/seed/opencode_instructions.seed.md"
    dest="$INSTALL_DIR/aitasks/metadata/opencode_instructions.seed.md"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored OpenCode instructions seed"
    fi
}

# --- Store Gemini CLI config and instructions seeds ---
install_seed_gemini_config() {
    local src dest

    src="$INSTALL_DIR/seed/geminicli_instructions.seed.md"
    dest="$INSTALL_DIR/aitasks/metadata/geminicli_instructions.seed.md"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored Gemini CLI instructions seed"
    fi

    src="$INSTALL_DIR/seed/geminicli_policies"
    dest="$INSTALL_DIR/aitasks/metadata/geminicli_policies"
    if [[ -d "$src" && ! -d "$dest" ]]; then
        mkdir -p "$dest"
        cp -r "$src/." "$dest/"
        info "  Stored Gemini CLI policies seed"
    fi

    src="$INSTALL_DIR/seed/geminicli_settings.seed.json"
    dest="$INSTALL_DIR/aitasks/metadata/geminicli_settings.seed.json"
    if [[ -f "$src" && ! -f "$dest" ]]; then
        cp "$src" "$dest"
        info "  Stored Gemini CLI settings seed"
    fi
}

# --- Show changelog between versions (upgrade only) ---
show_upgrade_changelog() {
    local tarball_path="$1"
    local install_dir="$2"

    # Only relevant during upgrade (existing install + --force)
    if [[ "$FORCE" != true ]]; then
        return
    fi

    local current_version=""
    if [[ -f "$install_dir/VERSION" ]]; then
        current_version="$(cat "$install_dir/VERSION")"
    elif [[ -f "$install_dir/.aitask-scripts/VERSION" ]]; then
        current_version="$(cat "$install_dir/.aitask-scripts/VERSION")"
    else
        return  # Can't determine current version, skip
    fi

    # Extract VERSION and CHANGELOG.md from tarball into temp dir
    local tmpextract
    tmpextract="$(mktemp -d)"

    tar -xzf "$tarball_path" -C "$tmpextract" .aitask-scripts/VERSION 2>/dev/null || true
    tar -xzf "$tarball_path" -C "$tmpextract" CHANGELOG.md 2>/dev/null || true

    local new_version=""
    if [[ -f "$tmpextract/.aitask-scripts/VERSION" ]]; then
        new_version="$(cat "$tmpextract/.aitask-scripts/VERSION")"
    fi

    if [[ -z "$new_version" || "$current_version" == "$new_version" ]]; then
        rm -rf "$tmpextract"
        return
    fi

    info "Upgrading: v${current_version} → v${new_version}"

    if [[ -f "$tmpextract/CHANGELOG.md" ]]; then
        echo ""
        info "Changelog:"
        echo ""

        # Print all version sections newer than current_version
        local in_range=false
        while IFS= read -r line; do
            if [[ "$line" =~ ^##\ v ]]; then
                local heading_version
                heading_version="${line#\#\# v}"
                if [[ "$heading_version" == "$current_version" ]]; then
                    break  # Stop before current version's section
                fi
                in_range=true
            fi
            if $in_range; then
                echo "  $line"
            fi
        done < "$tmpextract/CHANGELOG.md"

        echo ""
    else
        warn "No CHANGELOG.md in release (changelog display requires aitasks >= next release)"
    fi

    rm -rf "$tmpextract"

    # Ask for confirmation (only when stdin is a terminal)
    if [[ -t 0 ]]; then
        printf "  Proceed with upgrade? [Y/n] "
        read -r answer
        case "${answer:-Y}" in
            [Yy]*|"") ;;
            *) info "Aborted."; exit 0 ;;
        esac
    fi
}

# --- Set permissions ---
set_permissions() {
    chmod +x "$INSTALL_DIR/ait"
    chmod +x "$INSTALL_DIR"/.aitask-scripts/*.sh
    # Shared libraries in lib/ (sourced, not executed, but keep +x for consistency)
    find "$INSTALL_DIR/.aitask-scripts/lib" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
}

# --- Commit installed files to git (safety net) ---
# Runs after extraction — commits framework files if this project has opted
# into tracking them (heuristic: .aitask-scripts/VERSION is git-tracked).
# No interactive prompt (stdin may not be a terminal when piped).
# Non-fatal: warns on failure instead of aborting. Never pushes.
commit_installed_files() {
    if ! git -C "$INSTALL_DIR" rev-parse --is-inside-work-tree &>/dev/null; then
        return
    fi

    # Only auto-commit if the previous framework version was committed. We use
    # .aitask-scripts/VERSION as the sentinel: projects that want framework
    # files tracked commit it, projects that don't leave it untracked.
    if ! git -C "$INSTALL_DIR" ls-files --error-unmatch .aitask-scripts/VERSION &>/dev/null; then
        info "  .aitask-scripts/VERSION is not git-tracked — skipping auto-commit of framework update."
        return
    fi

    local version="unknown"
    if [[ -f "$INSTALL_DIR/.aitask-scripts/VERSION" ]]; then
        version="$(cat "$INSTALL_DIR/.aitask-scripts/VERSION")"
    fi

    # Build list of framework paths to stage. NOTE: this list is duplicated in
    # .aitask-scripts/aitask_setup.sh commit_framework_files(); keep them in sync.
    # install.sh runs stand-alone via curl|bash so it cannot source a shared helper.
    local paths_to_add=()
    local check_paths=(
        ".aitask-scripts/"
        "aitasks/metadata/"
        "aireviewguides/"
        "ait"
        ".claude/skills/"
        ".agents/"
        ".codex/"
        ".gemini/"
        ".opencode/"
        ".gitignore"
        ".github/workflows/"
        "CLAUDE.md"
        "GEMINI.md"
        "AGENTS.md"
        "opencode.json"
    )

    for p in "${check_paths[@]}"; do
        if [[ -e "$INSTALL_DIR/$p" ]]; then
            paths_to_add+=("$p")
        fi
    done

    if [[ ${#paths_to_add[@]} -eq 0 ]]; then
        return
    fi

    info "Committing framework update (v${version}) to git..."
    (
        cd "$INSTALL_DIR"
        git add "${paths_to_add[@]}" 2>/dev/null || true
        # One-time cleanup: drop any __pycache__ paths that were tracked before
        # the scoped .aitask-scripts/.gitignore landed.
        local cached_pycache
        cached_pycache="$(git ls-files '.aitask-scripts/*/__pycache__/*' 2>/dev/null || true)"
        if [[ -n "$cached_pycache" ]]; then
            echo "$cached_pycache" | xargs git rm --cached --quiet 2>/dev/null || true
        fi
        if ! git diff --cached --quiet 2>/dev/null; then
            git commit -m "ait: Update aitasks framework to v${version}"
        fi
    ) && success "Framework update committed to git" \
      || warn "Could not commit framework update (non-fatal)."
}

# --- Main ---
main() {
    echo ""
    info "aitask framework installer"
    echo ""

    check_prerequisites
    check_existing_install
    confirm_install

    # Temp directory with cleanup
    local tmpdir
    tmpdir="$(mktemp -d)"
    # shellcheck disable=SC2064  # Intentional: expand $tmpdir now, not at signal time
    trap "rm -rf '$tmpdir'" EXIT

    local tarball_path="$tmpdir/aitasks.tar.gz"

    download_tarball "$tarball_path"

    # Show changelog and confirm (upgrade path only)
    show_upgrade_changelog "$tarball_path" "$INSTALL_DIR"

    info "Extracting to $INSTALL_DIR..."
    tar -xzf "$tarball_path" -C "$INSTALL_DIR"

    # Remove CHANGELOG.md from project (only in tarball for upgrade changelog display)
    rm -f "$INSTALL_DIR/CHANGELOG.md"
    # Clean up legacy VERSION at root (moved to .aitask-scripts/VERSION in v0.3.0+)
    rm -f "$INSTALL_DIR/VERSION"

    info "Installing Claude Code skills..."
    install_skills

    info "Installing .aitask-scripts/.gitignore..."
    install_seed_aitask_scripts_gitignore

    info "Creating data directories..."
    create_data_dirs

    info "Installing execution profiles..."
    install_seed_profiles

    info "Installing seed task types..."
    install_seed_task_types

    info "Installing project config..."
    install_seed_project_config

    info "Installing review types..."
    install_seed_reviewtypes

    info "Installing review labels..."
    install_seed_reviewlabels

    info "Installing review environments..."
    install_seed_reviewenvironments

    info "Installing review guides..."
    install_seed_reviewguides

    info "Installing code agent configuration..."
    install_seed_codeagent_config

    info "Installing model configuration files..."
    install_seed_models

    info "Storing Claude Code permissions seed..."
    install_seed_claude_settings

    info "Storing Codex CLI staging files..."
    install_codex_staging

    info "Storing Codex CLI config seeds..."
    install_seed_codex_config

    info "Storing OpenCode staging files..."
    install_opencode_staging

    info "Storing OpenCode config seeds..."
    install_seed_opencode_config

    info "Storing Gemini CLI staging files..."
    install_gemini_staging

    info "Storing Gemini CLI config seeds..."
    install_seed_gemini_config

    # Clean up seed directory after all seed installers have run
    rm -rf "$INSTALL_DIR/seed"

    info "Setting permissions..."
    set_permissions

    info "Installing global shim..."
    # Source the setup script (without running main) to reuse install_global_shim()
    # shellcheck source=.aitask-scripts/aitask_setup.sh
    source "$INSTALL_DIR/.aitask-scripts/aitask_setup.sh" --source-only
    install_global_shim

    commit_installed_files

    echo ""
    echo "=== aitasks installed successfully ==="
    echo ""
    if [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
        info "Next step: run 'ait setup' to install dependencies and configure Claude Code permissions."
    else
        info "Next step: restart your shell (or run 'source ~/.zshrc'), then run 'ait setup'."
        info "Or run immediately with: ./ait setup"
    fi
    echo ""
    echo "Quick start:"
    echo "  ait setup      # Install dependencies and configure permissions"
    echo "  ait create     # Create a new task"
    echo "  ait ls -v 15   # List top 15 tasks"
    echo "  ait board      # Open task board"
    echo ""
    echo "Claude Code skills installed to .claude/skills/"
    echo ""
}

main "$@"
