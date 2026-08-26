#!/usr/bin/env bash
# data_symlinks.sh - Canonical creation of the branch-mode data layout.
#
#   <root>/.aitask-data        the data-branch worktree (or a symlink to it)
#   <root>/aitasks  -> .aitask-data/aitasks
#   <root>/aiplans  -> .aitask-data/aiplans
#
# The RELATIVE link form above is load-bearing: install.sh's ensure_data_root()
# recognizes ONLY `.aitask-data/<name>` and die()s on anything else. Do not
# change the target spelling here without changing that check in the same
# commit. tests/test_init_data.sh pins the emitted target for that reason.
#
# Two functions, two different postures:
#
#   ait_ensure_data_symlinks   the PRIMARY checkout path (ait setup,
#                              aitask_init_data.sh). Creates what is absent and
#                              leaves an existing, resolving link alone —
#                              semantics unchanged from the two inline copies it
#                              replaced, so the install flow gains no new
#                              behaviour.
#   ait_link_worktree_data     the LINKED WORKTREE path. Validates existing
#                              entries and repairs mismatches, because inside a
#                              task worktree all three names are framework-owned
#                              and gitignored — a stale link to another
#                              checkout's data branch is drift to fix, not user
#                              state to preserve.
#
# Neither function ever replaces an entry that is not a symlink.

[[ -n "${_AIT_DATA_SYMLINKS_LOADED:-}" ]] && return 0
_AIT_DATA_SYMLINKS_LOADED=1

# warn() comes from terminal_compat.sh. Source it here rather than relying on
# the caller having done so — this lib is sourced by two scripts and must not
# depend on their ordering.
# shellcheck source=terminal_compat.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/terminal_compat.sh"

AIT_DATA_DIR_NAME=".aitask-data"
AIT_DATA_LINKS=(aitasks aiplans)

# ait_data_link_target <name> -> the required raw target for <root>/<name>.
# One definition so the writer and every validator agree by construction.
ait_data_link_target() {
    printf '%s/%s' "$AIT_DATA_DIR_NAME" "$1"
}

# ait_canon_path <path> -> the physical, symlink-resolved absolute path, or
# empty (status 1) when <path> is not an existing directory. Both sides of every
# identity comparison below go through this, so a symlinked checkout cannot make
# two spellings of the same directory compare unequal.
ait_canon_path() {
    [[ -d "$1" ]] || return 1
    ( cd "$1" 2>/dev/null && pwd -P ) || return 1
}

# ait_main_worktree_root <dir>
#   Sets AIT_WT_MAIN_ROOT to the canonical root of <dir>'s repository MAIN
#   worktree. Returns 0 on success, 1 when <dir> is not inside a git repository,
#   2 when it is but the root could not be resolved.
#
#   Resolution goes through the git-common-dir, and is deliberately
#   PARSE-FREE: every value flows through a variable, so a repository path
#   containing a newline (or any other separator) resolves like any other.
#   `git worktree list --porcelain` cannot be used for this -- it emits such a
#   path raw and unquoted, so splitting its first record truncates it, and its
#   `-z` form needs git 2.36 AND cannot survive `$(...)`, which strips NUL.
#
#   Two candidates, in order, because neither alone covers every layout:
#
#     1. `rev-parse --show-toplevel` run FROM the common dir. A submodule's
#        gitdir (<super>/.git/modules/<name>) carries core.worktree, so this
#        maps it onto the real checkout. It must be `-C <common>`, never
#        `--git-dir=<common>`: the latter makes git treat the CALLER's cwd as
#        the work tree and cheerfully returns the caller's own repository root.
#     2. Otherwise `dirname <common>` -- git's own definition of the main
#        worktree for an ordinary repository, where the gitdir has no
#        core.worktree and candidate 1 exits non-zero.
#
#   The winner is then VALIDATED: it must be a working tree that is its own
#   toplevel. Without that, a deinitialized submodule would fall through to
#   candidate 2 and yield <super>/.git/modules -- an existing directory, which
#   is exactly the silent-wrong-answer class this helper exists to remove. A
#   failed validation is state 2, never a guess.
#
#   KNOWN LAYOUT BOUNDARY -- `git init --separate-git-dir` answers state 2.
#   That linkage is one-way: the checkout's .git FILE points at the gitdir, but
#   the gitdir gets no core.worktree, so nothing in it names the checkout. Git
#   itself cannot resolve it either -- `git worktree list` reports that repo's
#   main worktree as the gitdir. Refusing is deliberate and is an improvement on
#   the dirname() form, which returned the gitdir's PARENT and let every probe
#   run against an unrelated directory.
#
#   Derives everything FROM <dir>, so no ambient cwd can select a different
#   repository and the same-repo property every caller relies on is free.
ait_main_worktree_root() {
    local dir="${1:-.}" common root verify canon
    common="$(cd "$dir" 2>/dev/null && git rev-parse --git-common-dir 2>/dev/null)" || return 1
    [[ -n "$common" ]] || return 1
    common="$(cd "$dir" 2>/dev/null && ait_canon_path "$common")" || return 2
    root="$(git -C "$common" rev-parse --show-toplevel 2>/dev/null)" || root=""
    [[ -n "$root" ]] || root="$(dirname "$common")"
    canon="$(ait_canon_path "$root")" || return 2
    verify="$(git -C "$canon" rev-parse --show-toplevel 2>/dev/null)" || return 2
    verify="$(ait_canon_path "$verify")" || return 2
    [[ "$verify" == "$canon" ]] || return 2
    AIT_WT_MAIN_ROOT="$canon"
    return 0
}

# ait_linked_worktree_roots <dir>
#   Classifies <dir> against its repository's worktree topology. On success sets
#   BOTH AIT_WT_TOPLEVEL (this checkout's root) and AIT_WT_MAIN_ROOT (the
#   primary's). Three states, because "cannot classify" is its own answer and
#   must never be read as a negative:
#
#     0  <dir> is inside a LINKED worktree            -> act on it
#     1  definitively NOT linked: the primary checkout (a submodule's included),
#        a plain subdirectory of one, or not a repository at all
#     2  indeterminate: inside a repository, but the topology did not resolve
#        -> callers must refuse conservatively, never fall through
#
#   The predicate is `--git-dir != --git-common-dir`. They are equal exactly
#   when the checkout owns its repository -- an ordinary primary, a submodule's
#   primary (whose pair is <super>/.git/modules/<name> on both sides), and a
#   `--separate-git-dir` checkout -- and differ only for a linked worktree,
#   whose git-dir is <common>/worktrees/<name>. Comparing roots instead (the
#   toplevel against dirname(git-common-dir)) misreads every submodule primary
#   as linked.
#
#   Deliberately NOT using `--path-format=absolute` (git 2.31+): it would make
#   every older git indeterminate, and callers refuse on indeterminate. Both
#   options used here predate that by years, and each side is canonicalized
#   against <dir> so a relative answer resolves correctly.
ait_linked_worktree_roots() {
    local dir="${1:-.}" gitdir common toplevel
    gitdir="$(cd "$dir" 2>/dev/null && git rev-parse --git-dir 2>/dev/null)" || return 1
    [[ -n "$gitdir" ]] || return 1
    common="$(cd "$dir" 2>/dev/null && git rev-parse --git-common-dir 2>/dev/null)" || return 2
    [[ -n "$common" ]] || return 2
    gitdir="$(cd "$dir" 2>/dev/null && ait_canon_path "$gitdir")" || return 2
    common="$(cd "$dir" 2>/dev/null && ait_canon_path "$common")" || return 2
    # Equal => this checkout owns its repository: not a linked worktree.
    [[ "$gitdir" != "$common" ]] || return 1
    toplevel="$(ait_canon_path \
        "$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null)" || return 2
    [[ -n "$toplevel" ]] || return 2
    ait_main_worktree_root "$dir" || return 2
    [[ "$toplevel" != "$AIT_WT_MAIN_ROOT" ]] || return 2
    # shellcheck disable=SC2034  # out-param: read by callers alongside AIT_WT_MAIN_ROOT
    AIT_WT_TOPLEVEL="$toplevel"
    return 0
}

# ait_ensure_data_symlinks <root>
#   Create the two data symlinks under <root> if absent; drop a dangling link
#   first. An existing, resolving link is left alone whatever its target — see
#   the posture note above. Idempotent.
#   Returns 1 if <root> is not a directory.
ait_ensure_data_symlinks() {
    local root="$1" name
    [[ -d "$root" ]] || return 1
    for name in "${AIT_DATA_LINKS[@]}"; do
        # Remove a broken symlink so the create below can repair it.
        if [[ -L "$root/$name" && ! -e "$root/$name" ]]; then
            rm -f "$root/$name"
        fi
        [[ -L "$root/$name" ]] || ln -sf "$(ait_data_link_target "$name")" "$root/$name"
    done
    return 0
}

# ait_link_worktree_data <worktree_root> <main_root>
#   Give a linked git worktree the primary's data layout. Runs in two phases so
#   the refusal contract is structural rather than remembered:
#
#     1. preflight (read-only) classifies ALL THREE entries and reports every
#        non-symlink conflict, having written nothing;
#     2. apply executes only the operations preflight collected.
#
#   A sequential per-entry loop could repair .aitask-data, then hit a real
#   `aitasks` directory and fail, leaving a partially rewritten worktree while
#   claiming it refused. There is deliberately no path from a conflict to a
#   write.
#
#   Sets AIT_LINK_WORKTREE_CHANGED=1 when anything was created or repaired, 0
#   when every entry was already exactly correct.
#   Returns 1 on an unusable argument, 2 when an entry blocks the link.
ait_link_worktree_data() {
    local wt="$1" main="$2"
    local wt_canon main_canon data_canon name target actual i
    # Parallel arrays rather than a delimited encoding: a readlink target may
    # legitimately contain any character except NUL, and a packed record would
    # truncate it.
    local -a op_name=() op_target=() op_old=() conflicts=()

    # shellcheck disable=SC2034  # read by callers to pick LINKED vs ALREADY_LINKED
    AIT_LINK_WORKTREE_CHANGED=0

    wt_canon="$(ait_canon_path "$wt")" || return 1
    main_canon="$(ait_canon_path "$main")" || return 1
    data_canon="$(ait_canon_path "$main_canon/$AIT_DATA_DIR_NAME")" || return 1

    # --- Phase 1: preflight (read-only) ---

    # The .aitask-data entry is validated by CANONICAL TARGET: a link into
    # another checkout's data branch resolves perfectly well and would silently
    # point ./ait and the whole suite at the wrong repo's task data.
    if [[ -L "$wt_canon/$AIT_DATA_DIR_NAME" ]]; then
        actual="$(ait_canon_path "$wt_canon/$AIT_DATA_DIR_NAME" || true)"
        if [[ "$actual" != "$data_canon" ]]; then
            op_name+=("$AIT_DATA_DIR_NAME")
            op_target+=("$data_canon")
            op_old+=("${actual:-$(readlink "$wt_canon/$AIT_DATA_DIR_NAME")}")
        fi
    elif [[ -e "$wt_canon/$AIT_DATA_DIR_NAME" ]]; then
        conflicts+=("$wt_canon/$AIT_DATA_DIR_NAME")
    else
        op_name+=("$AIT_DATA_DIR_NAME"); op_target+=("$data_canon"); op_old+=("")
    fi

    # The two data links are validated by RAW target against the one literal
    # install.sh also recognizes, so the two checks drift together or not at all.
    for name in "${AIT_DATA_LINKS[@]}"; do
        target="$(ait_data_link_target "$name")"
        if [[ -L "$wt_canon/$name" ]]; then
            actual="$(readlink "$wt_canon/$name")"
            if [[ "$actual" != "$target" ]]; then
                op_name+=("$name"); op_target+=("$target"); op_old+=("$actual")
            fi
        elif [[ -e "$wt_canon/$name" ]]; then
            conflicts+=("$wt_canon/$name")
        else
            op_name+=("$name"); op_target+=("$target"); op_old+=("")
        fi
    done

    # Report EVERY conflict, not just the first — the caller is about to be told
    # to resolve them by hand.
    if (( ${#conflicts[@]} > 0 )); then
        warn "refusing to link worktree data: these paths exist and are not symlinks:" >&2
        printf '  %s\n' "${conflicts[@]}" >&2
        warn "remove or move them yourself; this helper never replaces a real file or directory" >&2
        return 2
    fi

    # --- Phase 2: apply ---
    for (( i = 0; i < ${#op_name[@]}; i++ )); do
        [[ -z "${op_old[i]}" ]] \
            || warn "repointing $wt_canon/${op_name[i]} (was: ${op_old[i]})" >&2
        rm -f "$wt_canon/${op_name[i]}"
        ln -s "${op_target[i]}" "$wt_canon/${op_name[i]}"
        # shellcheck disable=SC2034  # read by callers to pick LINKED vs ALREADY_LINKED
        AIT_LINK_WORKTREE_CHANGED=1
    done
    return 0
}
