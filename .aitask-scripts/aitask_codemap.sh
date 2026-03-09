#!/usr/bin/env bash

# aitask_codemap.sh - Structural scanning for project code areas
# Internal-only script (NOT an ait subcommand).
# Scans the repo structure and generates code_areas.yaml skeleton.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

VENV_PYTHON="$HOME/.aitask/venv/bin/python"

if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
    if ! command -v "$PYTHON" &>/dev/null; then
        echo "Error: Python not found. Run 'ait setup' to install dependencies." >&2
        exit 1
    fi
fi

ARG_SCAN=false
ARG_EXISTING=""
ARG_WRITE=false
ARG_HELP=false
ARG_INCLUDE_FRAMEWORK_DIRS=false
ARG_IGNORE_FILE=""

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --scan) ARG_SCAN=true; shift ;;
            --existing) ARG_EXISTING="${2:?--existing requires a path}"; shift 2 ;;
            --write) ARG_WRITE=true; shift ;;
            --include-framework-dirs) ARG_INCLUDE_FRAMEWORK_DIRS=true; shift ;;
            --ignore-file) ARG_IGNORE_FILE="${2:?--ignore-file requires a path}"; shift 2 ;;
            --help|-h) ARG_HELP=true; shift ;;
            *) die "Unknown argument: $1" ;;
        esac
    done
}

show_help() {
    cat <<'HELP'
Usage: aitask_codemap.sh [OPTIONS]

Scan repository structure and generate a code_areas.yaml skeleton.

Discovery behavior:
  - Runs with the shared aitasks Python at `~/.aitask/venv/bin/python` when available,
    otherwise falls back to `$PYTHON` or `python3`
  - Only scans directories that contain git-tracked files (`git ls-files`)
  - Does NOT read the project `.gitignore` by default
  - Always skips `.git`, `node_modules`, and `__pycache__`
  - Skips framework-owned top-level directories by default:
    `.aitask-scripts`, `aitasks`, `aiplans`, `aireviewguides`, `.claude`,
    `.gemini`, `.agents`, `.opencode`, `seed`
  - `aidocs/` and `aiwork/` are treated as normal project directories
  - `--ignore-file` applies extra gitignore-style filtering to tracked paths

Options:
  --scan                            Scan repo and output YAML to stdout
  --scan --existing <path>          Scan and output only areas not in existing file
  --write                           Write skeleton to aitasks/metadata/code_areas.yaml
  --include-framework-dirs          Include framework-owned top-level directories
  --ignore-file <path>              Apply extra gitignore-style excludes from file
  --help                            Show this help

Examples:
  ./.aitask-scripts/aitask_codemap.sh --scan
  ./.aitask-scripts/aitask_codemap.sh --scan --existing aitasks/metadata/code_areas.yaml
  ./.aitask-scripts/aitask_codemap.sh --scan --include-framework-dirs
  ./.aitask-scripts/aitask_codemap.sh --scan --ignore-file codemap.ignore
  ./.aitask-scripts/aitask_codemap.sh --write
HELP
}

run_codemap() {
    local -a cmd=("$PYTHON" "$SCRIPT_DIR/aitask_codemap.py")

    if [[ -n "$ARG_EXISTING" ]]; then
        cmd+=(--existing "$ARG_EXISTING")
    fi
    if [[ "$ARG_INCLUDE_FRAMEWORK_DIRS" == true ]]; then
        cmd+=(--include-framework-dirs)
    fi
    if [[ -n "$ARG_IGNORE_FILE" ]]; then
        cmd+=(--ignore-file "$ARG_IGNORE_FILE")
    fi

    "${cmd[@]}"
}

main() {
    parse_args "$@"

    if [[ "$ARG_HELP" == true ]]; then
        show_help
        exit 0
    fi

    if [[ "$ARG_WRITE" == true ]]; then
        local target="$TASK_DIR/metadata/code_areas.yaml"
        if [[ -f "$target" ]]; then
            die "code_areas.yaml already exists at $target. Use --scan --existing to find unmapped areas."
        fi
        mkdir -p "$TASK_DIR/metadata"
        run_codemap > "$target"
        info "Written to $target"
        exit 0
    fi

    if [[ "$ARG_SCAN" == true ]]; then
        run_codemap
        exit 0
    fi

    die "No action specified. Use --scan, --write, or --help."
}

main "$@"
