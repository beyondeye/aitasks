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
#   WORKTREE_UNLINKED Linked worktree, primary already holds the data branch
#                     (exit 3) — give this worktree the layout with
#                     --link-worktree <dir>
#   NOT_INITIALIZED   Linked worktree, primary has no .aitask-data worktree
#                     (exit 3) — run 'ait setup' at the primary first. Same
#                     state as the --link-worktree token of that name, which
#                     exits 0 because its no-op is harmless.
#   WORKTREE_INDETERMINATE
#                     Inside a repository whose worktree topology could not be
#                     resolved, so a linked worktree cannot be ruled out
#                     (exit 3) — refused rather than guessed, because
#                     initializing from a linked worktree can put the repo's
#                     only task data inside it.
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
  WORKTREE_UNLINKED Linked worktree, primary already holds the data branch
                    (exit 3) — give this worktree the layout with
                    --link-worktree <dir>
  NOT_INITIALIZED   Linked worktree, primary has no .aitask-data worktree
                    (exit 3) — run 'ait setup' at the primary first. Same
                    state as the --link-worktree token of that name, which
                    exits 0 because its no-op is harmless.
  WORKTREE_INDETERMINATE
                    Worktree topology unresolvable, so a linked worktree
                    cannot be ruled out (exit 3) — refused, not guessed.

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
        # free and no ambient cwd can pick a different repository. The
        # resolution lives in ait_main_worktree_root() (lib/data_symlinks.sh):
        # the dirname(git-common-dir) form this used to inline resolves to
        # <super>/.git/modules for a worktree of a git SUBMODULE -- an existing
        # directory, so every probe below silently ran against the wrong root
        # and this command answered NOT_INITIALIZED for a submodule that was in
        # fact initialized (t1627).
        main_root_rc=0
        ait_main_worktree_root "$target_dir" || main_root_rc=$?
        case "$main_root_rc" in
            0) main_root="$AIT_WT_MAIN_ROOT" ;;
            1) die "--link-worktree: '$target_dir' is not inside a git repository" ;;
            *) die "--link-worktree: could not resolve the main worktree root" ;;
        esac

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

# --- Check 3b: bare invocation inside a linked worktree ---
# Checks 1 and 2 probe RELATIVE paths, so they only ever see this checkout. In a
# linked worktree with no data layout neither fires, and control reaches Step 4 —
# where `git worktree add` does one of two wrong things depending on the
# primary's state. Classify instead of guessing.
#
# Ordering is load-bearing. This runs AFTER Check 3, so a repo with no
# aitask-data branch still answers NO_DATA_BRANCH from inside a worktree exactly
# as it did before; that answer is already correct and must not be swallowed.
#
# Keyed on the worktree ROOT, not on $PWD: an ordinary subdirectory of the
# primary shares the primary's toplevel and must NOT be called a worktree, and a
# nested subdirectory of a task worktree must still resolve to that worktree.
# The classification itself lives in ait_linked_worktree_roots()
# (lib/data_symlinks.sh) so setup_data_branch can ask the same question and the
# two halves cannot drift (t1627).
#
# Its state 2 — inside a repository, but the topology did not resolve — is
# refused rather than fallen through. The fall-through this replaces reached
# Step 4, which is precisely the route that SUCCEEDS wrongly against an
# uninitialized primary; "cannot classify" must not be read as "not a worktree".
wt_class_rc=0
ait_linked_worktree_roots "$PWD" || wt_class_rc=$?
# SCRIPT_DIR is absolute, so a printed command is copy-safe from ANY cwd —
# including a nested subdirectory of the worktree, where a ./.aitask-scripts/...
# spelling does not resolve.
self="$SCRIPT_DIR/${BASH_SOURCE[0]##*/}"
if [[ "$wt_class_rc" -eq 2 ]]; then
    echo "WORKTREE_INDETERMINATE"
    die_code 3 "'$PWD' is inside a git repository whose worktree topology could not be resolved, so it cannot be told apart from a linked task worktree. Refusing to create a data worktree here rather than guessing: initializing from a linked worktree can put the repo's only task data inside it. Run this from the primary checkout, or give an existing worktree the layout with: \"$self\" --link-worktree <dir>"
fi
if [[ "$wt_class_rc" -eq 0 ]]; then
    wt_toplevel="$AIT_WT_TOPLEVEL"
    wt_main_root="$AIT_WT_MAIN_ROOT"
    if [[ -d "$wt_main_root/$AIT_DATA_DIR_NAME/.git" \
          || -f "$wt_main_root/$AIT_DATA_DIR_NAME/.git" ]]; then
        # The primary holds the aitask-data branch, so a second worktree of
        # it cannot be created here. --link-worktree is the operation that
        # applies, and it accepts this worktree from any cwd.
        echo "WORKTREE_UNLINKED"
        die_code 3 "'$wt_toplevel' is a linked git worktree with no task-data layout, and the primary checkout at '$wt_main_root' already has the aitask-data branch checked out — a second worktree of it cannot be created here. Run: \"$self\" --link-worktree \"$wt_toplevel\""
    fi
    # The branch exists (Check 3 passed) but the primary has no data
    # worktree. Step 4 would SUCCEED here and put the repo's only task-data
    # checkout inside a throwaway task worktree, which is removed when the
    # task lands. Same state --link-worktree already calls NOT_INITIALIZED.
    echo "NOT_INITIALIZED"
    die_code 3 "'$wt_toplevel' is a linked git worktree, and the primary checkout at '$wt_main_root' has no $AIT_DATA_DIR_NAME worktree. Initializing from here would put the repo's only task data inside this worktree. Run 'ait setup' in '$wt_main_root' first, then: \"$self\" --link-worktree \"$wt_toplevel\""
fi

# --- Step 4: Create worktree ---
info "Creating .aitask-data/ worktree..." >&2
git worktree prune 2>/dev/null || true
# Surface git's own error: the old text named `git worktree add .aitask-data
# aitask-data` as the remedy, which is the command that just failed.
wt_add_err="$(git worktree add .aitask-data aitask-data 2>&1 >/dev/null)" || {
    die "Failed to create the .aitask-data worktree in '$PWD'. git said: ${wt_add_err:-<no output>}"
}

# --- Step 5: Create symlinks ---
ait_ensure_data_symlinks "$PWD"

success "Data branch initialized: .aitask-data/ worktree + symlinks" >&2
echo "INITIALIZED"
