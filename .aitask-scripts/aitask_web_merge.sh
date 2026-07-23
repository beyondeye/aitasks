#!/usr/bin/env bash
# aitask_web_merge.sh - Detect branches with completed Claude Web task executions
#
# Scans remote branches for .aitask-data-updated/completed_*.json markers.
# Outputs structured lines for the calling skill to parse and handle interactively.
#
# Usage:
#   ./.aitask-scripts/aitask_web_merge.sh              # Scan using cached remote data
#   ./.aitask-scripts/aitask_web_merge.sh --fetch      # Fetch first, then scan
#   ./.aitask-scripts/aitask_web_merge.sh materialize <task_id> <marker_json>
#                                                      # Validate marker provenance and
#                                                      # materialize the active-gates tuple
#
# Output format (one line per completed branch):
#   COMPLETED:<branch>:<completed_filename>
#
# If no completions found:
#   NONE
#
# materialize mode output (exactly one line):
#   WEBMAT_OK:<materialize-active status line>   Tuple materialized (or NOOP) under
#                                                the marker's profile; exit 0
#   WEBMAT_SKIP:no-profile                       Legacy marker without provenance
#                                                fields; nothing done; exit 0
#   WEBMAT_INVALID:<reason>                      Marker/provenance validation failed;
#                                                nothing done; exit 1
#   WEBMAT_FAIL:<rc>:<output>                    materialize-active itself failed;
#                                                exit 1 (a previously persisted tuple
#                                                may or may not have been cleared —
#                                                see the helper's stderr)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Configuration ---
DO_FETCH=false

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_web_merge.sh [options]

Scan remote branches for completed Claude Web task executions.

Options:
  --fetch       Run git fetch --all --prune before scanning
  --help, -h    Show this help

Subcommands:
  materialize <task_id> <marker_json>
                Validate the completion marker's profile provenance
                (profile + profile_filename fields) and materialize the
                task's active-gates tuple under exactly that profile file.
                Output (one line): WEBMAT_OK:<status> | WEBMAT_SKIP:no-profile
                | WEBMAT_INVALID:<reason> | WEBMAT_FAIL:<rc>:<output>

Output format (scan mode):
  COMPLETED:<branch>:<completed_filename>    For each detected branch
  NONE                                       If no completions found

Examples:
  ./.aitask-scripts/aitask_web_merge.sh --fetch    # Fetch and scan
  ./.aitask-scripts/aitask_web_merge.sh            # Scan cached data only
  ./.aitask-scripts/aitask_web_merge.sh materialize 42_2 .aitask-data-updated/completed_t42_2.json
EOF
}

# --- Argument Parsing ---
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --fetch)
                DO_FETCH=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            -*)
                die "Unknown option: $1. Use --help for usage."
                ;;
            *)
                die "Unexpected argument: $1. Use --help for usage."
                ;;
        esac
    done
}

# --- materialize mode (t635_35) ---
# Validates a completion marker's profile provenance and materializes the
# task's active-gates tuple under EXACTLY the recorded profile file. The
# marker fields are an authority input for gate selection, so validation is
# strict and fail-closed: a malformed marker never falls back to another
# profile and never silently skips.
cmd_materialize() {
    if [[ $# -ne 2 ]]; then
        echo "WEBMAT_INVALID:usage (expected: materialize <task_id> <marker_json>)"
        exit 1
    fi
    local task_id="$1" marker="$2"
    local task_dir="${TASK_DIR:-aitasks}"
    local profiles_dir="$task_dir/metadata/profiles"

    # shellcheck source=lib/python_resolve.sh disable=SC1091
    source "$SCRIPT_DIR/lib/python_resolve.sh"
    local python_bin
    python_bin="$(require_ait_python)"

    # Parse the two provenance fields with a real JSON parser. Output:
    #   OK<TAB><profile><TAB><profile_filename>   (missing fields emit empty)
    # or a bare error token on unreadable/invalid JSON.
    local parsed
    if ! parsed="$("$python_bin" - "$marker" <<'PYEOF'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
except (OSError, ValueError):
    print("BAD_MARKER")
    sys.exit(0)
if not isinstance(data, dict):
    print("BAD_MARKER")
    sys.exit(0)
def field(k):
    v = data.get(k, "")
    # Non-string → \x01 sentinel (NUL would be stripped by bash command
    # substitution and could not be detected by the caller).
    return v if isinstance(v, str) else "\x01"
print("OK\t%s\t%s" % (field("profile"), field("profile_filename")))
PYEOF
)"; then
        echo "WEBMAT_INVALID:parser-error"
        exit 1
    fi
    if [[ "$parsed" == "BAD_MARKER" ]]; then
        echo "WEBMAT_INVALID:bad-marker"
        exit 1
    fi
    local profile_name profile_filename
    profile_name="$(printf '%s' "$parsed" | cut -f2)"
    profile_filename="$(printf '%s' "$parsed" | cut -f3)"
    if [[ "$profile_name" == $'\x01' || "$profile_filename" == $'\x01' ]]; then
        echo "WEBMAT_INVALID:non-string-provenance"
        exit 1
    fi

    # Legacy marker: neither provenance field present → raw-`gates:` fallback
    # governs (never guess a profile). Skip is exit 0 — it is not a failure.
    if [[ -z "$profile_name" && -z "$profile_filename" ]]; then
        echo "WEBMAT_SKIP:no-profile"
        exit 0
    fi
    # A v1 marker always writes both fields; one without the other is corrupt.
    if [[ -z "$profile_name" || -z "$profile_filename" ]]; then
        echo "WEBMAT_INVALID:partial-provenance"
        exit 1
    fi

    # Filename must be a plain profiles-dir entry (optional local/ prefix).
    # No absolute paths, no `..`, no other slashes.
    if ! [[ "$profile_filename" =~ ^(local/)?[A-Za-z0-9._-]+\.yaml$ ]]; then
        echo "WEBMAT_INVALID:bad-profile-filename"
        exit 1
    fi
    local profile_file="$profiles_dir/$profile_filename"
    if [[ ! -f "$profile_file" ]]; then
        echo "WEBMAT_INVALID:profile-not-found"
        exit 1
    fi
    # Defense-in-depth: the resolved file must live inside the profiles dir
    # (realpath -m tolerates the aitasks/ data-branch symlink layout).
    local real_dir real_file
    real_dir="$(realpath -m "$profiles_dir")"
    real_file="$(realpath -m "$profile_file")"
    case "$real_file" in
        "$real_dir"/*) ;;
        *)
            echo "WEBMAT_INVALID:outside-profiles-dir"
            exit 1
            ;;
    esac

    # The loaded profile's declared name must equal the marker's profile name —
    # a renamed/repointed file must not silently govern under old provenance.
    local yaml_name
    yaml_name="$(sed -n 's/^name:[[:space:]]*//p' "$profile_file" | head -1 | tr -d '"'"'" )"
    if [[ "$yaml_name" != "$profile_name" ]]; then
        echo "WEBMAT_INVALID:name-mismatch"
        exit 1
    fi

    # Delegate to the canonical materializer; forward its single status line.
    # stderr is captured separately: on success it carries advisory WARNs
    # (passed through to our stderr), on failure it carries the actual
    # diagnostic (materialize-active reports errors on stderr, so a
    # stdout-only capture would leave WEBMAT_FAIL with an empty reason).
    local out err rc err_file
    err_file="$(mktemp "${TMPDIR:-/tmp}/webmat_err_XXXXXX")"
    set +e
    out="$("$SCRIPT_DIR/aitask_gate.sh" materialize-active "$task_id" --profile "$profile_file" 2>"$err_file")"
    rc=$?
    set -e
    err="$(cat "$err_file")"
    rm -f "$err_file"
    if [[ $rc -eq 0 ]]; then
        [[ -n "$err" ]] && printf '%s\n' "$err" >&2
        echo "WEBMAT_OK:${out}"
        exit 0
    fi
    echo "WEBMAT_FAIL:${rc}:$(printf '%s %s' "$out" "$err" | tr '\n' ' ')"
    exit 1
}

# --- Known branches to skip ---
is_skip_branch() {
    local branch="$1"
    case "$branch" in
        main|master|aitask-data|aitask-locks|aitask-ids)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# --- Main ---
main() {
    if [[ $# -gt 0 && "$1" == "materialize" ]]; then
        shift
        cmd_materialize "$@"   # always exits
    fi
    parse_args "$@"

    if [[ "$DO_FETCH" == true ]]; then
        git fetch --all --prune --quiet 2>/dev/null || warn "Fetch failed, using cached remote data"
    fi

    local found=0

    # Iterate over remote-tracking branches
    while IFS= read -r ref; do
        # Strip leading whitespace and "origin/" prefix
        ref="${ref#"${ref%%[![:space:]]*}"}"
        local branch="${ref#origin/}"

        # Skip known infrastructure branches
        if is_skip_branch "$branch"; then
            continue
        fi

        # Check for completion markers in .aitask-data-updated/
        local markers
        markers=$(git ls-tree --name-only "origin/${branch}:.aitask-data-updated/" 2>/dev/null | grep '^completed_' || true)

        if [[ -z "$markers" ]]; then
            continue
        fi

        # Output one line per marker found
        while IFS= read -r marker; do
            if [[ -n "$marker" ]]; then
                echo "COMPLETED:${branch}:${marker}"
                found=$((found + 1))
            fi
        done <<< "$markers"
    done < <(git branch -r --no-color 2>/dev/null | grep '^[[:space:]]*origin/' | grep -v 'HEAD')

    if [[ "$found" -eq 0 ]]; then
        echo "NONE"
    fi
}

main "$@"
