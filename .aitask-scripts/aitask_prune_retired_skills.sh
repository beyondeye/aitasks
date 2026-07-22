#!/usr/bin/env bash
# aitask_prune_retired_skills.sh - Remove retired skill surfaces from a project.
#
# Usage:
#   aitask_prune_retired_skills.sh [--dir <project>] [--manifest <file>]
#                                  [--prune-rendered] [--quiet]
#
# WHY THIS EXISTS
#   install_skills() (install.sh), setup_codex() and setup_opencode()
#   (aitask_setup.sh) install agent wrappers with additive `mkdir -p` + `cp`
#   loops. None of them removes a wrapper that DISAPPEARED upstream, and
#   `ait upgrade` just re-runs install.sh. So when the framework retires a
#   skill, every already-installed project keeps a discoverable slash command
#   whose authoring template no longer exists. This helper is the migration
#   path: it is invoked by install.sh and `ait setup` and prunes the retired
#   surfaces listed in the manifest.
#
# OWNERSHIP IS DECIDED BY CONTENT, NOT BY PATH
#   An exact retired path is NOT proof the framework owns the file: a user may
#   have customized the skill, kept their own unrelated skill at that name, or
#   edited an untracked Codex/OpenCode staging wrapper. Deleting those on
#   upgrade would be unrecoverable for untracked files. A path is therefore
#   removed ONLY when `git hash-object` of every file under it appears in the
#   manifest's SHA set (every version the framework ever shipped there).
#   Anything else is preserved, reported as KEPT, and named in a closing
#   warning with a manual cleanup command.
#
#   Directories are ALL-OR-NOTHING: one modified or unrecognized file preserves
#   the whole directory. A partial delete would leave a broken half-skill.
#
#   Rendered closures (<root>/<stem>-<profile>[-<agent>]-/) are GENERATED from
#   the user's own profiles, so no shipped hash can identify them and the
#   authoring template needed to re-render for comparison is exactly what was
#   deleted. They are therefore never removed by an upgrade — only reported —
#   unless the user explicitly passes --prune-rendered.
#
# Output (stdout, line-oriented — install.sh / aitask_setup.sh parse it):
#   PRUNED:<path>          a retired path was removed
#   KEPT:<path>:<reason>   a retired path was preserved
#   The human-facing warning goes to STDERR so it survives `$(...)` capture.
#
# Idempotence means NO ADDITIONAL REMOVALS, not silence: PRUNED lines are
# one-shot events (the paths are gone), while KEPT lines are a standing report
# of current state and repeat on every run for as long as those paths exist.
# That repeat is required — otherwise a project would lose its cleanup
# instruction on the very next upgrade.
#
# Exit code: 0 in all normal cases (including "nothing to do" and "everything
# was kept"). A kept path is a reportable outcome, not an error — a nonzero
# exit would abort the installer over user data we deliberately did not touch.
# Internal helper: not exposed via the `ait` dispatcher.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=.aitask-scripts/lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$SCRIPT_DIR/lib/agent_skills_paths.sh"

PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$SCRIPT_DIR/retired_skills_manifest.txt"
PRUNE_RENDERED=false
QUIET=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)             PROJECT_DIR="$2"; shift 2 ;;
        --manifest)        MANIFEST="$2"; shift 2 ;;
        --prune-rendered)  PRUNE_RENDERED=true; shift ;;
        --quiet)           QUIET=true; shift ;;
        -h|--help)
            sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) die "aitask_prune_retired_skills.sh: unknown argument: $1" ;;
    esac
done

[[ -d "$PROJECT_DIR" ]] || die "aitask_prune_retired_skills.sh: no such directory: $PROJECT_DIR"

# A missing manifest means this framework build retires nothing — a no-op, not
# an error. Never fail an installer over it.
if [[ ! -f "$MANIFEST" ]]; then
    exit 0
fi

# --- Load the manifest -------------------------------------------------------

declare -A KNOWN_SHA=()
RETIRED_DIRS=()
RETIRED_FILES=()
RETIRED_STEMS=()

while IFS=$'\t' read -r kind value; do
    case "$kind" in
        DIR)  RETIRED_DIRS+=("$value") ;;
        FILE) RETIRED_FILES+=("$value") ;;
        STEM) RETIRED_STEMS+=("$value") ;;
        SHA)  KNOWN_SHA["$value"]=1 ;;
        *)    : ;;  # comments and blank lines
    esac
done < <(grep -E '^(DIR|FILE|STEM|SHA)'$'\t' "$MANIFEST" || true)

if [[ ${#KNOWN_SHA[@]} -eq 0 ]]; then
    # No ownership data — refuse to delete anything by path alone.
    warn "aitask_prune_retired_skills.sh: manifest has no SHA records; skipping prune." >&2
    exit 0
fi

KEPT_PATHS=()

# is_known_blob <file> — true when the file's git blob hash is one the
# framework shipped at a retired path. Uses `git hash-object`, which is a pure
# hash function and works outside a git repository.
is_known_blob() {
    local f="$1" sha
    sha="$(git hash-object -- "$f" 2>/dev/null)" || return 1
    [[ -n "${KNOWN_SHA[$sha]:-}" ]]
}

report_kept() {
    local rel="$1" reason="$2"
    printf 'KEPT:%s:%s\n' "$rel" "$reason"
    KEPT_PATHS+=("$rel  ($reason)")
}

report_pruned() {
    printf 'PRUNED:%s\n' "$1"
}

# --- Retired single files ----------------------------------------------------

for rel in "${RETIRED_FILES[@]:-}"; do
    [[ -n "$rel" ]] || continue
    abs="$PROJECT_DIR/$rel"
    [[ -e "$abs" ]] || continue
    if [[ ! -f "$abs" || -L "$abs" ]]; then
        report_kept "$rel" "not-a-regular-file"
        continue
    fi
    if is_known_blob "$abs"; then
        rm -f "$abs"
        report_pruned "$rel"
    else
        report_kept "$rel" "unrecognized-content"
    fi
done

# --- Retired directories (all-or-nothing) ------------------------------------

for rel in "${RETIRED_DIRS[@]:-}"; do
    [[ -n "$rel" ]] || continue
    abs="$PROJECT_DIR/$rel"
    [[ -e "$abs" ]] || continue
    if [[ ! -d "$abs" || -L "$abs" ]]; then
        report_kept "$rel" "not-a-directory"
        continue
    fi

    # Any non-regular entry (symlink, socket, fifo) is unrecognized content.
    if [[ -n "$(find "$abs" -mindepth 1 ! -type f ! -type d -print -quit 2>/dev/null)" ]]; then
        report_kept "$rel" "unrecognized-content"
        continue
    fi

    unknown=""
    while IFS= read -r -d '' f; do
        if ! is_known_blob "$f"; then
            unknown="${f#"$PROJECT_DIR"/}"
            break
        fi
    done < <(find "$abs" -type f -print0 2>/dev/null)

    if [[ -n "$unknown" ]]; then
        # ALL-OR-NOTHING: one unrecognized file preserves the whole directory,
        # including its unmodified siblings. A partial delete would leave a
        # broken half-skill.
        report_kept "$rel" "unrecognized-content"
    else
        rm -rf "$abs"
        report_pruned "$rel"
    fi
done

# --- Rendered closures -------------------------------------------------------
#
# Match <root>/<stem>-<profile>[-<agent>]- EXACTLY on the stem. The REQUIRED
# hyphen immediately after the stem is the guard: without it, a retired stem
# that is a PREFIX of a live skill would swallow the live skill's renders —
# retiring `aitask-pick` would delete `aitask-pickn-fast-`, retiring
# `task-workflow` would delete `task-workflown-fast-`. (Today's retired stems
# happen to be the longer names, so the hazard is latent rather than active —
# but the next retirement inherits this code, and tests/test_prune_retired_skills.sh
# pins the behaviour with an inverted-stem control.)

for agent in claude codex opencode; do
    root_rel="$(agent_skill_root "$agent")" || continue
    root_abs="$PROJECT_DIR/$root_rel"
    [[ -d "$root_abs" ]] || continue

    for stem in "${RETIRED_STEMS[@]:-}"; do
        [[ -n "$stem" ]] || continue
        while IFS= read -r -d '' dir; do
            base="$(basename "$dir")"
            # Require the separator right after the stem AND the trailing
            # hyphen that marks a generated dir.
            [[ "$base" == "${stem}-"*"-" ]] || continue
            rel="$root_rel/$base"
            if [[ "$PRUNE_RENDERED" == true ]]; then
                rm -rf "$dir"
                report_pruned "$rel"
            else
                report_kept "$rel" "rendered-closure-not-verifiable"
            fi
        done < <(find "$root_abs" -mindepth 1 -maxdepth 1 -type d -name "${stem}-*-" -print0 2>/dev/null)
    done
done

# --- Closing warning ---------------------------------------------------------

if [[ ${#KEPT_PATHS[@]} -gt 0 && "$QUIET" != true ]]; then
    {
        printf '\n'
        warn "${#KEPT_PATHS[@]} retired skill path(s) were KEPT, not deleted:"
        for entry in "${KEPT_PATHS[@]}"; do
            printf '    %s\n' "$entry"
        done
        printf '\n'
        printf '  "unrecognized-content" means the file differs from every version the\n'
        printf '  framework shipped there — a local modification, or your own skill at\n'
        printf '  that name. "rendered-closure-not-verifiable" means a generated\n'
        printf '  per-profile directory, which an upgrade never deletes.\n\n'
        printf '  These are safe to leave in place. If you do not need them:\n'
        for entry in "${KEPT_PATHS[@]}"; do
            printf '    rm -rf %s\n' "${entry%%  (*}"
        done
        printf '\n'
    } >&2
fi

exit 0
