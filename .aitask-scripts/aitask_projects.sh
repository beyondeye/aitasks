#!/usr/bin/env bash
# aitask_projects.sh - User-facing dispatcher for the cross-repo project
# registry. Routed by `ait projects <verb>`.
#
# The registry lives at `~/.config/aitasks/projects.yaml` (override with
# `AITASKS_PROJECTS_INDEX`). It is a flat list of `{name, path,
# git_remote, last_opened}` entries, populated automatically by
# `ait ide` and by direct `ait projects add` invocations.
#
# Verbs:
#   list                   - List every registered project with status.
#   add [<path>]           - Register the project at <path> (default: $(pwd)).
#                            Idempotent — replaces an existing entry of
#                            the same name. Refreshes `last_opened`.
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
  resolve <name>             Print the resolver output for <name>:
                               RESOLVED:<path>
                               NOT_FOUND:<name>
                               STALE:<name>:<path>
  exec <name> -- <command>   Resolve <name>, cd into its root, then
                             exec <command>. Errors out on NOT_FOUND
                             or STALE.

Registry file: $HOME/.config/aitasks/projects.yaml
              (override with AITASKS_PROJECTS_INDEX)

See aidocs/cross_repo_references.md for the registry schema and the
resolver order.

Examples:
  cd /path/to/aitasks_mobile && ait projects add
  ait projects list
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
list_registry_entries() {
    [[ -f "$REGISTRY_FILE" ]] || return 0
    awk '
        function emit() {
            if (cur_name != "") {
                printf "%s|%s|%s|%s\n", cur_name, cur_path, cur_remote, cur_last
            }
            cur_name=""; cur_path=""; cur_remote=""; cur_last=""
        }
        function unquote(s) {
            gsub(/^[[:space:]]+/, "", s)
            gsub(/[[:space:]]+$/, "", s)
            gsub(/^"/, "", s); gsub(/"$/, "", s)
            gsub(/^'\''/, "", s); gsub(/'\''$/, "", s)
            return s
        }
        /^[[:space:]]*-[[:space:]]*name:[[:space:]]*/ {
            emit()
            v=$0
            sub(/^[[:space:]]*-[[:space:]]*name:[[:space:]]*/, "", v)
            cur_name=unquote(v)
            next
        }
        /^[[:space:]]+name:[[:space:]]*/ {
            emit()
            v=$0
            sub(/^[[:space:]]+name:[[:space:]]*/, "", v)
            cur_name=unquote(v)
            next
        }
        /^[[:space:]]+path:[[:space:]]*/ {
            v=$0
            sub(/^[[:space:]]+path:[[:space:]]*/, "", v)
            cur_path=unquote(v)
            next
        }
        /^[[:space:]]+git_remote:[[:space:]]*/ {
            v=$0
            sub(/^[[:space:]]+git_remote:[[:space:]]*/, "", v)
            cur_remote=unquote(v)
            next
        }
        /^[[:space:]]+last_opened:[[:space:]]*/ {
            v=$0
            sub(/^[[:space:]]+last_opened:[[:space:]]*/, "", v)
            cur_last=unquote(v)
            next
        }
        END { emit() }
    ' "$REGISTRY_FILE"
}

# Build a registry YAML body from entries on stdin (pipe-separated:
# name|path|git_remote|last_opened). Pipe (not tab) is used so empty
# middle fields don't get collapsed by `read -r` under whitespace IFS.
# Emits the full file contents on stdout.
build_registry_yaml() {
    {
        # shellcheck disable=SC2016
        printf '# aitasks per-user project registry — managed by `ait projects`.\n'
        # shellcheck disable=SC2016
        printf '# Edit by hand at your own risk; use `ait projects add` instead.\n'
        printf 'projects:\n'
        while IFS='|' read -r name path remote last; do
            [[ -z "$name" ]] && continue
            printf '  - name: %s\n' "$name"
            printf '    path: %s\n' "$path"
            [[ -n "$remote" ]] && printf '    git_remote: %s\n' "$remote"
            [[ -n "$last" ]]   && printf '    last_opened: %s\n' "$last"
        done
    }
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
    while IFS='|' read -r name path remote _last; do
        [[ -z "$name" ]] && continue
        has_any=1
        local status
        if grep -Fxq "$name" <<< "$live" 2>/dev/null; then
            status="LIVE"
        elif [[ -d "$path" && -f "$path/aitasks/metadata/project_config.yaml" ]]; then
            status="OK"
        else
            status="STALE"
        fi
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

    # Rebuild the registry: keep every entry whose name differs from
    # new_name, then append the fresh entry.
    local tsv_in tsv_out
    tsv_in=$(list_registry_entries || true)
    tsv_out=""
    if [[ -n "$tsv_in" ]]; then
        tsv_out=$(awk -F'|' -v skip="$new_name" '$1 != skip { print }' <<< "$tsv_in")
    fi
    # Re-append the fresh entry.
    if [[ -n "$tsv_out" ]]; then
        tsv_out+=$'\n'
    fi
    tsv_out+="${new_name}|${target_path}|${new_remote}|${new_last}"

    local body
    body=$(printf '%s\n' "$tsv_out" | build_registry_yaml)
    atomic_write "$REGISTRY_FILE" "$body"

    info "Registered $new_name → $target_path"
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
