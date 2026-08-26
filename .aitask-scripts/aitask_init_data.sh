#!/usr/bin/env bash
# aitask_init_data.sh - Lightweight data branch initialization
#
# Ensures the aitask-data worktree and symlinks are set up when the
# repository uses data-branch mode. Safe to call repeatedly (idempotent).
# Does NOT create branches, migrate data, update .gitignore, or modify CLAUDE.md.
# For full setup, use: ait setup
#
# Usage:
#   ./.aitask-scripts/aitask_init_data.sh
#   ./.aitask-scripts/aitask_init_data.sh --link-worktree <dir>
#
# Output (stdout, structured for LLM parsing):
#   INITIALIZED       Worktree and symlinks created successfully
#   ALREADY_INIT      Already initialized (.aitask-data worktree exists)
#   LEGACY_MODE       Not a data-branch repo (aitasks/ is a real directory)
#   NO_DATA_BRANCH    No aitask-data branch found locally or remotely
#
# Output for --link-worktree:
#   LINKED            Data layout created or repaired in the worktree
#   ALREADY_LINKED    All three entries were already exactly correct
#   LEGACY_MODE       Primary keeps task data on the code branch — nothing to do
#   NOT_INITIALIZED   Primary has no .aitask-data worktree — run: ait setup
#
# Called by:
#   .claude/skills/aitask-pickrem/SKILL.md (Step 0)
#   .claude/skills/task-workflow/SKILL.md (Step 7, --link-worktree)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/data_symlinks.sh
source "$SCRIPT_DIR/lib/data_symlinks.sh"

# --- Help ---
case "${1:-}" in
    --help|-h)
        cat <<'EOF'
Usage: aitask_init_data.sh
       aitask_init_data.sh --link-worktree <dir>

Initialize the aitask-data worktree and symlinks for repos that use
data-branch mode. Safe to call multiple times (idempotent).

Does NOT create branches, migrate data, or modify .gitignore/CLAUDE.md.
For full setup, use: ait setup

Output (stdout):
  INITIALIZED       Worktree and symlinks created
  ALREADY_INIT      Already initialized
  LEGACY_MODE       Not a data-branch repo
  NO_DATA_BRANCH    No aitask-data branch found

--link-worktree <dir>
  Give a linked git worktree (e.g. a task worktree at aiwork/<task_name>)
  the same task-data layout as the primary checkout: a .aitask-data symlink
  to the primary's data worktree, plus the aitasks/ and aiplans/ symlinks on
  top of it. Without them, ./ait run from inside the worktree resolves
  aitasks/ locally and finds nothing, and suite modules that read
  aitasks/metadata/*.json fail with FileNotFoundError.

  <dir> must be a linked worktree ROOT — not an ordinary subdirectory, not
  the main checkout, and not the .aitask-data worktree. Anything else is
  refused without writing.

Output (stdout):
  LINKED            Data layout created or repaired
  ALREADY_LINKED    All three entries were already exactly correct
  LEGACY_MODE       Primary keeps task data on the code branch — nothing to do
  NOT_INITIALIZED   Primary has no .aitask-data worktree — run: ait setup
EOF
        exit 0
        ;;
    --link-worktree)
        target_dir="${2:-}"
        [[ -n "$target_dir" ]] || die "--link-worktree requires a directory argument"
        [[ -d "$target_dir" ]] || die "--link-worktree: '$target_dir' is not a directory"

        # Derive the main root FROM the supplied dir, so the same-repo check is
        # free and no ambient cwd can pick a different repository.
        git_common="$(git -C "$target_dir" rev-parse --path-format=absolute \
            --git-common-dir 2>/dev/null)" \
            || die "--link-worktree: '$target_dir' is not inside a git repository"
        main_root="$(ait_canon_path "$(dirname "$git_common")")" \
            || die "--link-worktree: could not resolve the main worktree root"

        target_canon="$(ait_canon_path "$target_dir")" \
            || die "--link-worktree: could not resolve '$target_dir'"

        # <dir> must be a worktree ROOT. This is load-bearing and the two checks
        # below do NOT imply it: an ordinary subdirectory of the primary shares
        # its git-common-dir, so it resolves the same main_root and is trivially
        # unequal to it. Without this check a mistyped path would plant symlinks
        # into an arbitrary source directory.
        toplevel_canon="$(ait_canon_path \
            "$(git -C "$target_dir" rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || true)"
        [[ -n "$toplevel_canon" && "$toplevel_canon" == "$target_canon" ]] \
            || die "--link-worktree: '$target_dir' is not a worktree root (its worktree root is '${toplevel_canon:-<unresolved>}')"

        [[ "$target_canon" != "$main_root" ]] \
            || die "--link-worktree: '$target_dir' is the main checkout — use the plain invocation there"

        # The data worktree is ALSO a registered worktree root, so it passes both
        # checks above; linking it would nest .aitask-data inside the data branch.
        data_root_canon="$(ait_canon_path "$main_root/$AIT_DATA_DIR_NAME" 2>/dev/null || true)"
        [[ -z "$data_root_canon" || "$target_canon" != "$data_root_canon" ]] \
            || die "--link-worktree: '$target_dir' is the .aitask-data worktree — refusing to nest the data layout inside itself"

        # Legacy mode: task data is tracked on the code branch, so the worktree
        # checkout already has it. Nothing to link.
        if [[ -d "$main_root/aitasks" && ! -L "$main_root/aitasks" ]]; then
            echo "LEGACY_MODE"
            exit 0
        fi

        if [[ ! -d "$main_root/$AIT_DATA_DIR_NAME/.git" \
              && ! -f "$main_root/$AIT_DATA_DIR_NAME/.git" ]]; then
            echo "NOT_INITIALIZED"
            exit 0
        fi

        link_rc=0
        ait_link_worktree_data "$target_canon" "$main_root" || link_rc=$?
        if [[ "$link_rc" -eq 2 ]]; then
            die "--link-worktree: refused (see the conflicting paths above); nothing was written"
        elif [[ "$link_rc" -ne 0 ]]; then
            die "--link-worktree: could not resolve the data layout for '$target_dir'"
        fi

        if [[ "$AIT_LINK_WORKTREE_CHANGED" -eq 1 ]]; then
            echo "LINKED"
        else
            echo "ALREADY_LINKED"
        fi
        exit 0
        ;;
esac

# --- Check 1: Already initialized ---
if [[ -d ".aitask-data/.git" || -f ".aitask-data/.git" ]]; then
    ait_ensure_data_symlinks "$PWD"
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
ait_ensure_data_symlinks "$PWD"

success "Data branch initialized: .aitask-data/ worktree + symlinks" >&2
echo "INITIALIZED"
