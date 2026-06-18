#!/usr/bin/env bash
# aitask_projects.sh - User-facing dispatcher for the cross-repo project
# registry. Routed by `ait projects <verb>`.
#
# The registry lives at `~/.config/aitasks/projects.yaml` (override with
# `AITASKS_PROJECTS_INDEX`). It is a flat list of `{name, path,
# git_remote, last_opened, project_group}` entries, populated automatically by
# `ait ide` and by direct `ait projects add` invocations.
#
# Verbs:
#   list                   - List every registered project with status.
#   add [<path>]           - Register the project at <path> (default: $(pwd)).
#                            Idempotent — replaces an existing entry of
#                            the same name. Refreshes `last_opened`.
#   remove <name> [--force]
#                          - Drop a single entry from the registry.
#                            Prompts for confirmation unless --force.
#   update <name> <new_path>
#                          - Repoint an existing entry to a new on-disk
#                            root; refreshes last_opened, keeps git_remote.
#   prune [--dry-run] [--yes]
#                          - Drop every STALE registry entry (path no
#                            longer holds the aitasks marker). Prompts
#                            per entry unless --yes.
#   doctor [--clone]       - Interactive scan: per-entry prune /
#                            update / clone / keep / skip-all over
#                            STALE rows. Clone branch is opt-in via
#                            --clone.
#   group <subcommand>     - Manage project-group membership
#                            (list / set / unset / sync). t1025_1.
#   resolve <name>         - Re-emit the resolver's structured output for
#                            <name> (RESOLVED:/NOT_FOUND:/STALE:).
#   exec <name> -- <cmd>   - Resolve <name>, cd into the root, exec <cmd>.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

REGISTRY_FILE="${AITASKS_PROJECTS_INDEX:-$HOME/.config/aitasks/projects.yaml}"
RESOLVER="$SCRIPT_DIR/aitask_project_resolve.sh"

# Project-group constants (t1025_1) — must match agent_launch_utils.py
# (PROJECT_GROUP_UNSET_SENTINEL / PROJECT_GROUP_UNGROUPED_LABEL).
GROUP_UNSET_SENTINEL="-"
GROUP_UNGROUPED_LABEL="(ungrouped)"

show_help() {
    cat <<'EOF'
Usage: ait projects <verb> [arguments]

User-facing dispatcher for the cross-repo project registry. Lets
sibling aitasks projects refer to one another by logical name instead
of by disk path.

Verbs:
  list                       List every registered project with status
                             (LIVE / OK / STALE).
  add [<path>]               Register the project at <path> (default:
                             current directory). Idempotent.
  remove <name> [--force]    Drop the named entry from the registry.
                             Prompts for confirmation unless --force.
  update <name> <new_path>   Repoint <name> to a new on-disk root
                             (refreshes last_opened, keeps git_remote).
  prune [--dry-run] [--yes]  Drop every STALE registry entry (path no
                             longer holds the aitasks marker). Prompts
                             per entry unless --yes; --dry-run lists
                             matches without modifying the registry.
  doctor [--clone]           Interactive scan: walk every STALE entry
                             and offer prune / update / clone / keep /
                             skip-all per entry. Clone is opt-in via
                             --clone and only offered for entries that
                             have a git_remote.
  group <list|set|unset|sync>
                             Manage project-group membership:
                               list                 groups -> members
                               set <name> <group>   assign a group slug
                               unset <name>         clear (explicitly ungrouped)
                               sync                 backfill from repo configs
  resolve <name>             Print the resolver output for <name>:
                               RESOLVED:<path>
                               NOT_FOUND:<name>
                               STALE:<name>:<path>
  exec <name> -- <command>   Resolve <name>, cd into its root, then
                             exec <command>. Errors out on NOT_FOUND
                             or STALE.

Registry file: $HOME/.config/aitasks/projects.yaml
              (override with AITASKS_PROJECTS_INDEX)

See aidocs/framework/cross_repo_references.md for the registry schema and the
resolver order.

Examples:
  cd /path/to/aitasks_mobile && ait projects add
  ait projects list
  ait projects remove old_project --force
  ait projects update aitasks_mobile /new/path/to/aitasks_mobile
  ait projects prune --dry-run
  ait projects prune --yes
  ait projects doctor
  ait projects doctor --clone
  ait projects resolve aitasks
  ait projects exec aitasks -- pwd
  ait projects exec aitasks -- ./.aitask-scripts/aitask_ls.sh -v 5
EOF
}

# --- Helpers ------------------------------------------------------------

# Read the `project.<key>` field from a project_config.yaml at <root>.
# Echoes the value on stdout (empty if absent / file missing).
read_project_field() {
    local root="$1"
    local key="$2"
    local cfg="$root/aitasks/metadata/project_config.yaml"
    [[ -f "$cfg" ]] || return 0

    awk -v want_key="$key" '
        # Track when we are inside the top-level project: block.
        /^project:[[:space:]]*$/ { in_project=1; next }
        # Any top-level non-comment, non-blank line exits the block.
        /^[^ #]/ && !/^project:/ { in_project=0 }
        in_project && /^[[:space:]]+[a-z_]+:/ {
            line=$0
            sub(/^[[:space:]]+/, "", line)
            split(line, kv, ":")
            k=kv[1]
            v=substr(line, length(k) + 2)
            sub(/^[[:space:]]+/, "", v)
            sub(/[[:space:]]+$/, "", v)
            gsub(/^"/, "", v); gsub(/"$/, "", v)
            gsub(/^'\''/, "", v); gsub(/'\''$/, "", v)
            if (k == want_key) { print v; exit }
        }
    ' "$cfg"
}

# Validate a project-group slug via the single Python authority (t1025_1).
# Returns 0 if valid, 1 otherwise (reason printed to stderr by the shim). Write
# paths (group set / add+sync bootstrap) reject invalid slugs; they all
# `require_python` first, so a resolvable interpreter is guaranteed here.
validate_group_slug() {
    local slug="$1"
    local python_bin
    python_bin=$(resolve_python)
    [[ -n "$python_bin" ]] || { warn "No Python interpreter — cannot validate group slug"; return 1; }
    "$python_bin" "$SCRIPT_DIR/lib/agent_launch_utils.py" --validate-slug "$slug"
}

# Read a registered entry's current project_group (5th pipe field) by name from
# pre-fetched `list_registry_entries` output. Echoes the raw value (slug, the
# unset sentinel `-`, or empty). Used by cmd_add to let a user-set registry
# group survive a re-add (registry wins over config bootstrap).
registry_group_for_name() {
    local want="$1"
    local tsv="$2"
    awk -F'|' -v n="$want" '$1 == n { print $5; exit }' <<< "$tsv"
}

# Determine the logical name for a project at <root>:
#   1. project.name in project_config.yaml
#   2. directory basename
project_name_for_root() {
    local root="$1"
    local name
    name=$(read_project_field "$root" "name")
    [[ -n "$name" ]] && { printf '%s\n' "$name"; return 0; }
    basename "$root"
}

# Atomic write — writes <content> to <target> via mktemp+mv.
atomic_write() {
    local target="$1"
    local content="$2"
    mkdir -p "$(dirname "$target")"
    local tmp
    tmp=$(mktemp "${target}.XXXXXX")
    # Force exactly one trailing newline (command substitution stripped any).
    printf '%s\n' "$content" > "$tmp"
    mv -f "$tmp" "$target"
}

# Iterate the registry and emit one pipe-separated line per entry:
#   <name>|<path>|<git_remote>|<last_opened>
# Pipe is used (not tab) so empty middle fields survive `read -r` (tab is
# whitespace IFS — consecutive tabs collapse).
# Empty / missing registry → no output.
#
# Single registry-file reader authority (t970): shells out to the Python
# parser in agent_launch_utils.py instead of re-implementing the YAML grammar
# in awk. The output is byte-identical to the former awk reader (golden-corpus
# tested in tests/test_registry_reader_parity.sh). Because this feeds the
# read-modify-write round-trip (cmd_add / cmd_remove / cmd_update re-serialize
# the whole file via build_registry_yaml), every mutating verb guards Python
# availability up front with `require_python` — a missing interpreter aborts
# loudly rather than returning empty and wiping git_remote/last_opened.
list_registry_entries() {
    [[ -f "$REGISTRY_FILE" ]] || return 0
    local python_bin
    python_bin=$(resolve_python)
    [[ -n "$python_bin" ]] || return 0
    AITASKS_PROJECTS_INDEX="$REGISTRY_FILE" "$python_bin" \
        "$SCRIPT_DIR/lib/agent_launch_utils.py" --list-registry
}

# Build a registry YAML body from entries on stdin (pipe-separated:
# name|path|git_remote|last_opened|project_group). Pipe (not tab) is used so
# empty middle fields don't get collapsed by `read -r` under whitespace IFS.
# The 5th project_group field (t1025_1) is a slug, the unset sentinel `-`, or
# empty; emitted only when non-empty (so the sentinel persists). Emits the full
# file contents on stdout.
build_registry_yaml() {
    {
        # shellcheck disable=SC2016
        printf '# aitasks per-user project registry — managed by `ait projects`.\n'
        # shellcheck disable=SC2016
        printf '# Edit by hand at your own risk; use `ait projects add` instead.\n'
        printf 'projects:\n'
        while IFS='|' read -r name path remote last group; do
            [[ -z "$name" ]] && continue
            printf '  - name: %s\n' "$name"
            printf '    path: %s\n' "$path"
            # Use explicit `if` (not `[[ ]] && printf`) so an empty trailing
            # field does not leave the loop body — and thus the whole loop — with
            # a non-zero exit, which `set -euo pipefail` would turn into a failed
            # `body=$(... | build_registry_yaml)` assignment (t1025_1).
            if [[ -n "$remote" ]]; then printf '    git_remote: %s\n' "$remote"; fi
            if [[ -n "$last" ]];   then printf '    last_opened: %s\n' "$last"; fi
            if [[ -n "$group" ]];  then printf '    project_group: %s\n' "$group"; fi
        done
    }
}

# Classify a registry entry by (name, path).
# Optional 3rd arg: newline-separated list of currently-live project_names
# (from live_tmux_project_names). When provided and the name matches, the
# entry is classified LIVE; otherwise OK / STALE based on the marker file.
# Echoes exactly one of: LIVE / OK / STALE.
classify_registry_entry() {
    local name="$1"
    local path="$2"
    local live="${3:-}"

    if [[ -n "$live" ]] && grep -Fxq "$name" <<< "$live" 2>/dev/null; then
        printf 'LIVE\n'
        return 0
    fi
    if [[ -d "$path" && -f "$path/aitasks/metadata/project_config.yaml" ]]; then
        printf 'OK\n'
    else
        printf 'STALE\n'
    fi
}

# --- Verb: list ---------------------------------------------------------

# Returns a sorted, newline-separated list of project_name values for
# every currently-live tmux session that resolves to an aitasks project.
live_tmux_project_names() {
    local python_bin
    python_bin=$(resolve_python) || return 0
    [[ -n "$python_bin" ]] || return 0

    "$python_bin" - "$SCRIPT_DIR/lib" <<'PYEOF' 2>/dev/null || true
import sys
sys.path.insert(0, sys.argv[1])
try:
    from agent_launch_utils import discover_aitasks_sessions
    for s in discover_aitasks_sessions():
        print(s.project_name)
except Exception:
    pass
PYEOF
}

cmd_list() {
    if [[ ! -f "$REGISTRY_FILE" ]]; then
        info "No registered projects. Run \`ait projects add\` from any aitasks project root."
        return 0
    fi

    local live
    live=$(live_tmux_project_names)

    local has_any=0
    while IFS='|' read -r name path remote _last _group; do
        [[ -z "$name" ]] && continue
        has_any=1
        local status
        status=$(classify_registry_entry "$name" "$path" "$live")
        if [[ -n "$remote" ]]; then
            printf '%-20s  %-7s  %s  (%s)\n' "$name" "$status" "$path" "$remote"
        else
            printf '%-20s  %-7s  %s\n' "$name" "$status" "$path"
        fi
    done < <(list_registry_entries)

    if [[ "$has_any" == "0" ]]; then
        info "Registry file exists but contains no entries."
    fi
}

# --- Verb: add ----------------------------------------------------------

cmd_add() {
    require_python >/dev/null  # registry mutation routes reads through Python (t970)
    # Prefer the caller's pwd (captured by the ait wrapper before its own cd)
    # over $(pwd), which after `ait` has already cd'd would always be the
    # ait-script directory.
    local target_path="${1:-${AIT_INVOCATION_PWD:-$(pwd)}}"
    if [[ ! -d "$target_path" ]]; then
        die "Path does not exist: $target_path"
    fi
    target_path=$(cd "$target_path" && pwd)

    if [[ ! -f "$target_path/aitasks/metadata/project_config.yaml" ]]; then
        die "Not an aitasks project (no aitasks/metadata/project_config.yaml under $target_path)"
    fi

    local new_name new_remote new_last
    new_name=$(project_name_for_root "$target_path")
    new_remote=$(read_project_field "$target_path" "git_remote")
    new_last=$(date -u +"%Y-%m-%d")

    local tsv_in tsv_out
    tsv_in=$(list_registry_entries || true)

    # Resolve the project_group for the fresh entry (t1025_1):
    #   - On re-add, an existing registry group (incl. the `-` unset sentinel)
    #     WINS — never clobbered by config bootstrap.
    #   - Otherwise bootstrap from the repo config's project.project_group,
    #     rejecting an invalid slug with a clear, sourced message (D4).
    local new_group=""
    if [[ -n "$tsv_in" ]]; then
        new_group=$(registry_group_for_name "$new_name" "$tsv_in")
    fi
    if [[ -z "$new_group" ]]; then
        local cfg_group
        cfg_group=$(read_project_field "$target_path" "project_group")
        if [[ -n "$cfg_group" ]]; then
            if ! validate_group_slug "$cfg_group" 2>/dev/null; then
                die "Repo '$new_name' project_config.yaml has an invalid project.project_group '$cfg_group' (must match ^[a-z0-9][a-z0-9_-]*\$). Fix the config or set the group later with 'ait projects group set'."
            fi
            new_group="$cfg_group"
        fi
    fi

    # Rebuild the registry: keep every entry whose name differs from
    # new_name, then append the fresh entry.
    tsv_out=""
    if [[ -n "$tsv_in" ]]; then
        tsv_out=$(awk -F'|' -v skip="$new_name" '$1 != skip { print }' <<< "$tsv_in")
    fi
    # Re-append the fresh entry (5 fields — preserves project_group).
    if [[ -n "$tsv_out" ]]; then
        tsv_out+=$'\n'
    fi
    tsv_out+="${new_name}|${target_path}|${new_remote}|${new_last}|${new_group}"

    local body
    body=$(printf '%s\n' "$tsv_out" | build_registry_yaml)
    atomic_write "$REGISTRY_FILE" "$body"

    info "Registered $new_name → $target_path"
}

# --- Verb: remove -------------------------------------------------------

cmd_remove() {
    require_python >/dev/null  # registry mutation routes reads through Python (t970)
    local name=""
    local force=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force) force=1; shift ;;
            -h|--help)
                echo "Usage: ait projects remove <name> [--force]"
                return 0
                ;;
            -*) die "Unknown flag: $1" ;;
            *)
                [[ -z "$name" ]] || die "Usage: ait projects remove <name> [--force]"
                name="$1"
                shift
                ;;
        esac
    done
    [[ -n "$name" ]] || die "Usage: ait projects remove <name> [--force]"

    local tsv
    tsv=$(list_registry_entries || true)
    if [[ -z "$tsv" ]]; then
        die "No registered projects."
    fi
    # Confirm the entry exists before prompting / mutating.
    if ! awk -F'|' -v want="$name" '$1 == want { found=1 } END { exit !found }' <<< "$tsv"; then
        die "Project '$name' is not registered."
    fi

    if [[ "$force" -ne 1 ]]; then
        printf "Remove '%s' from registry? [y/N]: " "$name" >&2
        local ans=""
        read -r ans || true
        case "$ans" in
            y|Y) ;;
            *)
                info "Aborted."
                return 0
                ;;
        esac
    fi

    local tsv_out
    tsv_out=$(awk -F'|' -v skip="$name" '$1 != skip { print }' <<< "$tsv")

    local body
    body=$(printf '%s\n' "$tsv_out" | build_registry_yaml)
    atomic_write "$REGISTRY_FILE" "$body"

    info "Removed $name"
}

# --- Verb: update -------------------------------------------------------

cmd_update() {
    require_python >/dev/null  # registry mutation routes reads through Python (t970)
    local name="${1:-}"
    local new_path="${2:-}"
    [[ -n "$name" && -n "$new_path" ]] \
        || die "Usage: ait projects update <name> <new_path>"

    if [[ ! -d "$new_path" ]]; then
        die "Path does not exist: $new_path"
    fi
    if [[ ! -f "$new_path/aitasks/metadata/project_config.yaml" ]]; then
        die "Not an aitasks project (no aitasks/metadata/project_config.yaml under $new_path)"
    fi
    new_path=$(cd "$new_path" && pwd)

    local tsv
    tsv=$(list_registry_entries || true)
    if [[ -z "$tsv" ]]; then
        die "No registered projects."
    fi
    if ! awk -F'|' -v want="$name" '$1 == want { found=1 } END { exit !found }' <<< "$tsv"; then
        die "Project '$name' is not registered."
    fi

    local today
    today=$(date -u +"%Y-%m-%d")

    # Carry $5 (project_group) through the rewrite (t1025_1) — repointing the
    # path/last_opened must never drop a registered group.
    local tsv_out
    tsv_out=$(awk -F'|' \
        -v name="$name" \
        -v new_path="$new_path" \
        -v today="$today" \
        '$1 == name { print $1 "|" new_path "|" $3 "|" today "|" $5; next } { print }' \
        <<< "$tsv")

    local body
    body=$(printf '%s\n' "$tsv_out" | build_registry_yaml)
    atomic_write "$REGISTRY_FILE" "$body"

    info "Updated $name → $new_path"
}

# --- Verb: prune --------------------------------------------------------

cmd_prune() {
    require_python >/dev/null  # registry mutation routes reads through Python (t970)
    local dry_run=0
    local assume_yes=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) dry_run=1; shift ;;
            --yes|-y)  assume_yes=1; shift ;;
            -h|--help)
                echo "Usage: ait projects prune [--dry-run] [--yes]"
                return 0
                ;;
            *) die "Unknown argument: $1" ;;
        esac
    done

    local tsv
    tsv=$(list_registry_entries || true)

    local stale_names=()
    local stale_paths=()
    if [[ -n "$tsv" ]]; then
        while IFS='|' read -r name path _remote _last _group; do
            [[ -z "$name" ]] && continue
            local status
            status=$(classify_registry_entry "$name" "$path")
            if [[ "$status" == "STALE" ]]; then
                stale_names+=("$name")
                stale_paths+=("$path")
            fi
        done <<< "$tsv"
    fi

    local total=${#stale_names[@]}
    echo "Found $total stale entries."
    if [[ "$total" -eq 0 ]]; then
        return 0
    fi

    if [[ "$dry_run" -eq 1 ]]; then
        local i
        for ((i = 0; i < total; i++)); do
            printf '  %s → %s\n' "${stale_names[i]}" "${stale_paths[i]}"
        done
        return 0
    fi

    local pruned=0
    local i
    for ((i = 0; i < total; i++)); do
        local name="${stale_names[i]}"
        local path="${stale_paths[i]}"
        if [[ "$assume_yes" -ne 1 ]]; then
            printf "Prune '%s' (path: %s)? [y/N]: " "$name" "$path" >&2
            local ans=""
            read -r ans || true
            case "$ans" in
                y|Y) ;;
                *) continue ;;
            esac
        fi
        cmd_remove "$name" --force
        pruned=$((pruned + 1))
    done

    echo "Pruned $pruned of $total stale entries."
}

# --- Verb: doctor -------------------------------------------------------

cmd_doctor() {
    require_python >/dev/null  # registry mutation routes reads through Python (t970)
    local enable_clone=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --clone) enable_clone=1; shift ;;
            -h|--help)
                echo "Usage: ait projects doctor [--clone]"
                return 0
                ;;
            *) die "Unknown argument: $1" ;;
        esac
    done

    local tsv
    tsv=$(list_registry_entries || true)

    local stale_names=() stale_paths=() stale_remotes=() stale_lasts=()
    if [[ -n "$tsv" ]]; then
        while IFS='|' read -r name path remote last _group; do
            [[ -z "$name" ]] && continue
            local status
            status=$(classify_registry_entry "$name" "$path")
            if [[ "$status" == "STALE" ]]; then
                stale_names+=("$name")
                stale_paths+=("$path")
                stale_remotes+=("$remote")
                stale_lasts+=("$last")
            fi
        done <<< "$tsv"
    fi

    local total=${#stale_names[@]}
    echo "Found $total stale entries."
    [[ "$total" -eq 0 ]] && return 0

    local i
    for ((i = 0; i < total; i++)); do
        local idx=$((i + 1))
        local name="${stale_names[i]}"
        local path="${stale_paths[i]}"
        local remote="${stale_remotes[i]}"
        local last="${stale_lasts[i]}"

        printf '\n[%d/%d] STALE: %s -> %s\n' "$idx" "$total" "$name" "$path"
        [[ -n "$last"   ]] && printf '         last opened: %s\n' "$last"
        [[ -n "$remote" ]] && printf '         git_remote:  %s\n' "$remote"

        # Only offer `c`lone when --clone is set AND the entry has a remote.
        local can_clone=0 actions
        if [[ "$enable_clone" -eq 1 && -n "$remote" ]]; then
            can_clone=1
            actions="[p]rune / [u]pdate / [c]lone / [k]eep / [s]kip-all"
        else
            actions="[p]rune / [u]pdate / [k]eep / [s]kip-all"
        fi
        printf '         Action? %s : ' "$actions" >&2

        local ans=""
        read -r ans || true

        case "$ans" in
            p|P)
                cmd_remove "$name" --force
                ;;
            u|U)
                printf '         New path: ' >&2
                local new_path=""
                read -r new_path || true
                if [[ -z "$new_path" ]]; then
                    warn "No path given - skipping."
                    continue
                fi
                # cmd_update die()s on a missing-marker error; running it in
                # a subshell isolates set -e so the doctor loop continues.
                if ( cmd_update "$name" "$new_path" ); then
                    :
                else
                    warn "Update failed - entry left as-is."
                fi
                ;;
            c|C)
                if [[ "$can_clone" -ne 1 ]]; then
                    warn "Clone not available (requires --clone and a git_remote)."
                    continue
                fi
                printf '         Clone %s into %s? [y/N]: ' "$remote" "$path" >&2
                local confirm=""
                read -r confirm || true
                case "$confirm" in
                    y|Y) ;;
                    *) info "Clone declined."; continue ;;
                esac
                if git clone "$remote" "$path"; then
                    if [[ -f "$path/aitasks/metadata/project_config.yaml" ]]; then
                        info "Cloned and now OK."
                    else
                        warn "Cloned but no aitasks/metadata/project_config.yaml - entry remains STALE."
                    fi
                else
                    warn "git clone failed - entry remains STALE."
                fi
                ;;
            k|K)
                info "Keeping $name."
                ;;
            s|S)
                info "Skipping remaining entries."
                break
                ;;
            *)
                warn "Unrecognized action '$ans' - keeping entry."
                ;;
        esac
    done
}

# --- Verb: resolve ------------------------------------------------------

cmd_resolve() {
    local name="${1:-}"
    [[ -n "$name" ]] || die "Usage: ait projects resolve <name>"
    "$RESOLVER" "$name"
}

# --- Verb: exec ---------------------------------------------------------

cmd_exec() {
    local name="${1:-}"
    [[ -n "$name" ]] || die "Usage: ait projects exec <name> -- <cmd> [args...]"
    shift

    # Strip optional `--` separator.
    if [[ "${1:-}" == "--" ]]; then
        shift
    fi
    [[ $# -gt 0 ]] || die "ait projects exec: no command provided after '<name> --'"

    local out
    out=$("$RESOLVER" "$name")
    case "$out" in
        RESOLVED:*)
            local root="${out#RESOLVED:}"
            cd "$root"
            exec "$@"
            ;;
        STALE:*)
            local rest="${out#STALE:}"
            die "Project '$name' is registered but its path is stale: $rest"
            ;;
        NOT_FOUND:*)
            die "Project '$name' is not registered. Run \`cd /path/to/$name && ait projects add\`."
            ;;
        *)
            die "Resolver returned unexpected output: $out"
            ;;
    esac
}

# --- Verb: group --------------------------------------------------------

# Resolve an entry's EFFECTIVE project-group (t1025_1), mirroring discovery:
#   registry slug wins; sentinel `-` -> ungrouped (no fallback); empty ->
#   validated repo config; invalid/absent -> ungrouped. Echoes the group slug,
#   or empty for ungrouped.
group_effective() {
    local path="$1"
    local reg_group="$2"
    if [[ "$reg_group" == "$GROUP_UNSET_SENTINEL" ]]; then
        return 0
    fi
    if [[ -n "$reg_group" ]]; then
        printf '%s\n' "$reg_group"
        return 0
    fi
    local cfg
    cfg=$(read_project_field "$path" "project_group")
    [[ -n "$cfg" ]] || return 0
    if validate_group_slug "$cfg" >/dev/null 2>&1; then
        printf '%s\n' "$cfg"
    fi
}

# Rewrite the registry, setting entry <name>'s project_group field to <value>
# (may be empty). Dies if <name> is not registered.
set_registry_group() {
    local name="$1"
    local value="$2"
    local tsv
    tsv=$(list_registry_entries || true)
    if [[ -z "$tsv" ]] || ! awk -F'|' -v want="$name" '$1 == want { f=1 } END { exit !f }' <<< "$tsv"; then
        die "Project '$name' is not registered."
    fi
    local tsv_out
    tsv_out=$(awk -F'|' -v name="$name" -v value="$value" \
        '$1 == name { print $1 "|" $2 "|" $3 "|" $4 "|" value; next } { print }' \
        <<< "$tsv")
    local body
    body=$(printf '%s\n' "$tsv_out" | build_registry_yaml)
    atomic_write "$REGISTRY_FILE" "$body"
}

cmd_group() {
    require_python >/dev/null  # registry mutation routes reads through Python (t970)
    local sub="${1:-}"
    case "$sub" in
        list)
            local live
            live=$(live_tmux_project_names)
            local tsv
            tsv=$(list_registry_entries || true)
            if [[ -z "$tsv" ]]; then
                info "No registered projects."
                return 0
            fi
            # Buffer "group<TAB>member-line" rows, then print grouped + sorted.
            local rows=""
            local name path _remote _last group eff status label
            while IFS='|' read -r name path _remote _last group; do
                [[ -z "$name" ]] && continue
                eff=$(group_effective "$path" "$group")
                status=$(classify_registry_entry "$name" "$path" "$live")
                label="$name"
                [[ "$status" != "OK" && "$status" != "LIVE" ]] && label="$name [$status]"
                if [[ -z "$eff" ]]; then
                    rows+=$(printf '%s\t  %s\n' "$GROUP_UNGROUPED_LABEL" "$label")$'\n'
                else
                    rows+=$(printf '%s\t  %s\n' "$eff" "$label")$'\n'
                fi
            done <<< "$tsv"
            # Real groups sorted; the synthetic (ungrouped) bucket prints last.
            local g
            while IFS= read -r g; do
                [[ -z "$g" ]] && continue
                printf '%s:\n' "$g"
                awk -F'\t' -v want="$g" '$1 == want { print $2 }' <<< "$rows"
            done < <(awk -F'\t' -v ung="$GROUP_UNGROUPED_LABEL" '$1 != ung { print $1 }' <<< "$rows" | sort -u)
            if awk -F'\t' -v ung="$GROUP_UNGROUPED_LABEL" '$1 == ung { f=1 } END { exit !f }' <<< "$rows"; then
                printf '%s:\n' "$GROUP_UNGROUPED_LABEL"
                awk -F'\t' -v ung="$GROUP_UNGROUPED_LABEL" '$1 == ung { print $2 }' <<< "$rows"
            fi
            ;;
        set)
            local name="${2:-}"
            local group="${3:-}"
            [[ -n "$name" && -n "$group" ]] || die "Usage: ait projects group set <name> <group>"
            local reason
            if ! reason=$(validate_group_slug "$group" 2>&1); then
                die "Invalid project-group '$group': $reason"
            fi
            set_registry_group "$name" "$group"
            info "Set group of $name → $group"
            ;;
        unset)
            local name="${2:-}"
            [[ -n "$name" ]] || die "Usage: ait projects group unset <name>"
            # Write the explicit sentinel so discovery does NOT fall back to the
            # repo config (lets a config-grouped repo be truly cleared).
            set_registry_group "$name" "$GROUP_UNSET_SENTINEL"
            info "Cleared group of $name (explicitly ungrouped)"
            ;;
        sync)
            # Backfill absent/empty registry groups from each repo's config.
            # Never overwrites a real value or the `-` sentinel. Rejects invalid
            # config slugs with a sourced message.
            local tsv
            tsv=$(list_registry_entries || true)
            if [[ -z "$tsv" ]]; then
                info "No registered projects."
                return 0
            fi
            local tsv_out="" changed=0
            local name path remote last group cfg
            while IFS='|' read -r name path remote last group; do
                [[ -z "$name" ]] && continue
                if [[ -z "$group" ]]; then
                    cfg=$(read_project_field "$path" "project_group")
                    if [[ -n "$cfg" ]]; then
                        if ! validate_group_slug "$cfg" >/dev/null 2>&1; then
                            die "Repo '$name' project_config.yaml has an invalid project.project_group '$cfg'. Fix the config or use 'ait projects group set'."
                        fi
                        group="$cfg"
                        changed=$((changed + 1))
                    fi
                fi
                tsv_out+="${name}|${path}|${remote}|${last}|${group}"$'\n'
            done <<< "$tsv"
            local body
            body=$(printf '%s' "$tsv_out" | build_registry_yaml)
            atomic_write "$REGISTRY_FILE" "$body"
            info "Synced project groups from repo configs ($changed updated)."
            ;;
        ""|--help|-h)
            cat <<'EOF'
Usage: ait projects group <list|set|unset|sync>
  list                 Show groups and their member projects.
  set <name> <group>   Assign <name> to <group> (slug: ^[a-z0-9][a-z0-9_-]*$).
  unset <name>         Clear <name>'s group (explicitly ungrouped).
  sync                 Backfill absent registry groups from repo configs.
EOF
            ;;
        *)
            die "Unknown group subcommand: $sub (try 'ait projects group --help')"
            ;;
    esac
}

# --- Dispatch -----------------------------------------------------------

main() {
    local verb="${1:-}"
    case "$verb" in
        ""|--help|-h|help)
            show_help
            ;;
        list)
            shift
            cmd_list "$@"
            ;;
        add)
            shift
            cmd_add "$@"
            ;;
        remove|rm)
            shift
            cmd_remove "$@"
            ;;
        update)
            shift
            cmd_update "$@"
            ;;
        prune)
            shift
            cmd_prune "$@"
            ;;
        doctor)
            shift
            cmd_doctor "$@"
            ;;
        group)
            shift
            cmd_group "$@"
            ;;
        resolve)
            shift
            cmd_resolve "$@"
            ;;
        exec)
            shift
            cmd_exec "$@"
            ;;
        *)
            die "Unknown verb: $verb (try 'ait projects --help')"
            ;;
    esac
}

main "$@"
