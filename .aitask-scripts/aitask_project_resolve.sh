#!/usr/bin/env bash
# aitask_project_resolve.sh - Resolve a logical aitasks project name to a path.
#
# Internal helper for the cross-repo project registry (t826_1). Invoked by
# `aitask_projects.sh` (the user-facing `ait projects` dispatcher) and by
# `aitask_create.sh --project`. Not whitelisted for direct skill use —
# skills always go through `ait projects resolve <name>` or
# `aitask_projects.sh resolve <name>`.
#
# Resolution order:
#   1. Live tmux scan — calls
#      `agent_launch_utils.discover_aitasks_sessions()` and matches
#      `project_name` (basename of the project root) then `session`
#      against <name>. This path also covers the tmux global env var
#      `AITASKS_PROJECT_<sess>` since `discover_aitasks_sessions()`
#      already falls back to it.
#   2. Per-user index `~/.config/aitasks/projects.yaml` — flat YAML
#      list, parsed with awk.
#   3. Process env var `AITASKS_PROJECT_<name>` — manual override
#      useful in non-tmux contexts (CI, remote agents). Note: this is
#      the *process* env var, not the tmux global of the same shape.
#
# A registry entry is treated as STALE when it points at a path that
# no longer contains `aitasks/metadata/project_config.yaml`.
#
# Usage:
#   ./.aitask-scripts/aitask_project_resolve.sh <name>
#   ./.aitask-scripts/aitask_project_resolve.sh list
#
# Output for <name> (exactly one line, exit 0):
#   RESOLVED:<absolute-path>
#   NOT_FOUND:<name>
#   STALE:<name>:<path>
#
# Output for `list` (one line per registered entry, exit 0):
#   PROJECT:<name>:<path>:<status>
# where <status> is RESOLVED or STALE. Entries from the tmux scan and
# process env-var are NOT included — `list` enumerates the persistent
# per-user registry only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

REGISTRY_FILE="${AITASKS_PROJECTS_INDEX:-$HOME/.config/aitasks/projects.yaml}"

show_help() {
    cat <<'EOF'
Usage: aitask_project_resolve.sh <name>
       aitask_project_resolve.sh list

Resolve a logical aitasks project name to its filesystem root, or list
every entry from the per-user registry.

Resolve output (single line, exit 0):
  RESOLVED:<absolute-path>   Project found and path is a valid aitasks root.
  NOT_FOUND:<name>           No registered project matched.
  STALE:<name>:<path>        Registered, but the path is no longer a valid root.

List output (one line per registered entry, exit 0):
  PROJECT:<name>:<path>:<status>   Where <status> is RESOLVED or STALE.

Internal helper. Prefer `ait projects resolve <name>` / `ait projects list`
for user-facing use.
EOF
}

# Iterate every (name, path) pair from the per-user registry and emit one
# `PROJECT:<name>:<path>:<status>` line per entry. STALE when the path no
# longer holds an aitasks project root. Only the persistent registry is
# enumerated — the tmux scan and process env-var lookups are intentionally
# excluded so the output is reproducible across shells.
#
# Reads through the single Python registry-file authority (t970,
# agent_launch_utils.py --list-registry); status is still computed here in bash
# via path_is_aitasks_project. The `list` verb is not on the resolve hot path
# (it backs the one-shot project picker in aitask_create.sh), so the Python
# startup cost is acceptable here. Degrades to empty output if no interpreter
# is available — `list` is read-only, so there is no data-loss risk.
cmd_list() {
    [[ -f "$REGISTRY_FILE" ]] || return 0
    local python_bin
    python_bin=$(resolve_python)
    [[ -n "$python_bin" ]] || return 0
    local name path status
    while IFS='|' read -r name path _remote _last; do
        [[ -z "$name" ]] && continue
        if path_is_aitasks_project "$path"; then
            status="RESOLVED"
        else
            status="STALE"
        fi
        printf 'PROJECT:%s:%s:%s\n' "$name" "$path" "$status"
    done < <(AITASKS_PROJECTS_INDEX="$REGISTRY_FILE" "$python_bin" \
        "$SCRIPT_DIR/lib/agent_launch_utils.py" --list-registry)
}

# Print RESOLVED:<path> if a tmux scan finds a session whose project_name or
# session name matches NAME. Prints nothing on miss / failure.
tmux_scan_lookup() {
    local name="$1"
    local python_bin
    python_bin=$(resolve_python) || return 0
    [[ -n "$python_bin" ]] || return 0

    "$python_bin" - "$name" "$SCRIPT_DIR/lib" <<'PYEOF' 2>/dev/null || true
import sys
from pathlib import Path

name = sys.argv[1]
lib_dir = sys.argv[2]
sys.path.insert(0, lib_dir)

try:
    from agent_launch_utils import discover_aitasks_sessions
except Exception:
    sys.exit(0)

try:
    sessions = discover_aitasks_sessions()
except Exception:
    sys.exit(0)

# Match priority: project_name (= basename(project_root)) first, then session.
for s in sessions:
    if s.project_name == name:
        print(f"RESOLVED:{s.project_root}")
        sys.exit(0)
for s in sessions:
    if s.session == name:
        print(f"RESOLVED:{s.project_root}")
        sys.exit(0)
PYEOF
}

# Print "<path>" for the registry entry matching NAME, or nothing.
#
# Deliberately kept as a lean bash awk reader rather than shelling out to the
# Python registry authority (t970): this runs on the resolve hot path (every
# `ait projects resolve` / cross-repo lookup), and resolve already pays one
# Python startup for the live-tmux scan above. Measurement showed a Python
# `--resolve-index` shell-out adds ~50ms/call here — a second interpreter
# startup that would roughly double resolve latency — so the single-name lookup
# stays in bash. It is pinned byte-identical to `agent_launch_utils.py
# --resolve-index` by tests/test_registry_reader_parity.sh; keep the two in sync.
index_lookup_path() {
    local name="$1"
    [[ -f "$REGISTRY_FILE" ]] || return 0

    # The registry is a flat list of mappings:
    #
    #   projects:
    #     - name: aitasks
    #       path: /home/ddt/Work/aitasks
    #       git_remote: ...
    #     - name: aitasks_mobile
    #       ...
    #
    # awk over the file, tracking the current entry's name and path.
    awk -v want="$name" '
        /^[[:space:]]*-[[:space:]]*name:[[:space:]]*/ {
            sub(/^[[:space:]]*-[[:space:]]*name:[[:space:]]*/, "")
            gsub(/[[:space:]]+$/, "")
            gsub(/^"/, ""); gsub(/"$/, "")
            gsub(/^'\''/, ""); gsub(/'\''$/, "")
            cur_name=$0
            cur_path=""
            next
        }
        /^[[:space:]]+name:[[:space:]]*/ {
            sub(/^[[:space:]]+name:[[:space:]]*/, "")
            gsub(/[[:space:]]+$/, "")
            gsub(/^"/, ""); gsub(/"$/, "")
            gsub(/^'\''/, ""); gsub(/'\''$/, "")
            cur_name=$0
            cur_path=""
            next
        }
        /^[[:space:]]+path:[[:space:]]*/ {
            sub(/^[[:space:]]+path:[[:space:]]*/, "")
            gsub(/[[:space:]]+$/, "")
            gsub(/^"/, ""); gsub(/"$/, "")
            gsub(/^'\''/, ""); gsub(/'\''$/, "")
            cur_path=$0
            if (cur_name == want && cur_path != "") {
                print cur_path
                exit
            }
        }
    ' "$REGISTRY_FILE"
}

# Print "<path>" if the env var AITASKS_PROJECT_<NAME> is set, else nothing.
# The env var value is the project root (absolute path).
env_lookup_path() {
    local name="$1"
    local var="AITASKS_PROJECT_${name}"
    local value="${!var:-}"
    [[ -n "$value" ]] || return 0
    printf '%s\n' "$value"
}

# Validate that PATH is a real aitasks project root. Returns 0 if valid.
path_is_aitasks_project() {
    local path="$1"
    [[ -d "$path" && -f "$path/aitasks/metadata/project_config.yaml" ]]
}

main() {
    case "${1:-}" in
        ""|--help|-h)
            show_help
            return 0
            ;;
        list)
            cmd_list
            return 0
            ;;
    esac

    local name="$1"

    # 1. Live tmux scan (already covers the AITASKS_PROJECT_<sess> tmux global).
    local tmux_out
    tmux_out=$(tmux_scan_lookup "$name")
    if [[ -n "$tmux_out" ]]; then
        # tmux_scan_lookup only prints RESOLVED:<path> for valid roots
        # (the discover function itself filters on project_config.yaml).
        printf '%s\n' "$tmux_out"
        return 0
    fi

    # 2. Per-user index.
    local index_path
    index_path=$(index_lookup_path "$name")
    if [[ -n "$index_path" ]]; then
        if path_is_aitasks_project "$index_path"; then
            printf 'RESOLVED:%s\n' "$index_path"
            return 0
        fi
        printf 'STALE:%s:%s\n' "$name" "$index_path"
        return 0
    fi

    # 3. Process env var (manual override).
    local env_path
    env_path=$(env_lookup_path "$name")
    if [[ -n "$env_path" ]]; then
        if path_is_aitasks_project "$env_path"; then
            printf 'RESOLVED:%s\n' "$env_path"
            return 0
        fi
        printf 'STALE:%s:%s\n' "$name" "$env_path"
        return 0
    fi

    printf 'NOT_FOUND:%s\n' "$name"
}

main "$@"
