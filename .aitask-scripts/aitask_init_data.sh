#!/usr/bin/env bash
# aitask_init_data.sh - Lightweight data branch initialization
#
# Ensures the aitask-data worktree and symlinks are set up when the
# repository uses data-branch mode. Safe to call repeatedly (idempotent).
# Does NOT create branches, migrate data, update .gitignore, or modify CLAUDE.md.
# For full setup, use: ait setup
#
# Usage:
#   ./aiscripts/aitask_init_data.sh
#
# Output (stdout, structured for LLM parsing):
#   INITIALIZED       Worktree and symlinks created successfully
#   ALREADY_INIT      Already initialized (.aitask-data worktree exists)
#   LEGACY_MODE       Not a data-branch repo (aitasks/ is a real directory)
#   NO_DATA_BRANCH    No aitask-data branch found locally or remotely
#
# Called by:
#   .claude/skills/aitask-pickrem/SKILL.md (Step 0)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Help ---
case "${1:-}" in
    --help|-h)
        cat <<'EOF'
Usage: aitask_init_data.sh

Initialize the aitask-data worktree and symlinks for repos that use
data-branch mode. Safe to call multiple times (idempotent).

Does NOT create branches, migrate data, or modify .gitignore/CLAUDE.md.
For full setup, use: ait setup

Output (stdout):
  INITIALIZED       Worktree and symlinks created
  ALREADY_INIT      Already initialized
  LEGACY_MODE       Not a data-branch repo
  NO_DATA_BRANCH    No aitask-data branch found
EOF
        exit 0
        ;;
esac

# --- Ensure symlinks exist (helper) ---
ensure_symlinks() {
    # Remove broken symlinks if present
    [[ -L "aitasks" && ! -e "aitasks" ]] && rm -f "aitasks"
    [[ -L "aiplans" && ! -e "aiplans" ]] && rm -f "aiplans"

    [[ -L "aitasks" ]] || ln -sf .aitask-data/aitasks aitasks
    [[ -L "aiplans" ]] || ln -sf .aitask-data/aiplans aiplans
}

# --- Check 1: Already initialized ---
if [[ -d ".aitask-data/.git" || -f ".aitask-data/.git" ]]; then
    ensure_symlinks
    echo "ALREADY_INIT"
    exit 0
fi

# --- Check 2: Legacy mode (real directory, not symlink) ---
if [[ -d "aitasks" && ! -L "aitasks" ]]; then
    echo "LEGACY_MODE"
    exit 0
fi

# --- Check 3: Does aitask-data branch exist? ---
branch_found=false

# Check local branches
if git show-ref --verify refs/heads/aitask-data &>/dev/null; then
    branch_found=true
fi

# Check remote (if local not found and remote exists)
if [[ "$branch_found" == false ]] && git remote get-url origin &>/dev/null; then
    if git ls-remote --heads origin aitask-data 2>/dev/null | grep -q aitask-data; then
        info "Found aitask-data branch on remote, fetching..." >&2
        git fetch origin aitask-data 2>/dev/null || {
            warn "Failed to fetch aitask-data branch from remote" >&2
            echo "NO_DATA_BRANCH"
            exit 0
        }
        branch_found=true
    fi
fi

if [[ "$branch_found" == false ]]; then
    echo "NO_DATA_BRANCH"
    exit 0
fi

# --- Step 4: Create worktree ---
info "Creating .aitask-data/ worktree..." >&2
git worktree prune 2>/dev/null || true
git worktree add .aitask-data aitask-data >/dev/null 2>&1 || {
    die "Failed to create worktree. Run: git worktree add .aitask-data aitask-data"
}

# --- Step 5: Create symlinks ---
ensure_symlinks

success "Data branch initialized: .aitask-data/ worktree + symlinks" >&2
echo "INITIALIZED"
