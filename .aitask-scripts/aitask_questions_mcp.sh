#!/usr/bin/env bash
# aitask_questions_mcp.sh - STDIO launcher for the aitask_questions MCP server.
#
# Registered by `ait setup` in a project's .codex/config.toml as
#   [mcp_servers.aitask_questions] command = ".aitask-scripts/aitask_questions_mcp.sh"
# and started by the Codex client, never by a person or a skill. It serves
# attended workflow questions as MCP forms and keeps every question durable, so
# a form that times out can be answered at the ordinary prompt and resumed.
#
# CONTRACTS
#   1. stdout belongs to the MCP protocol. Every diagnostic goes to stderr.
#   2. No answer is ever produced here: a missing dependency or unusable state
#      directory exits non-zero and the client reports the server unavailable,
#      which leaves the workflow question pending (never defaulted).
#   3. Question state lives OUTSIDE the project (per-user state directory), so
#      it can never be committed and needs no .gitignore rule. Occurrences are
#      scoped by this checkout's real path; a worktree is a separate scope.
#
# Environment:
#   AIT_QUESTIONS_STATE_DIR    state directory
#                              (default: ${XDG_STATE_HOME:-~/.local/state}/aitasks/questions)
#   AIT_QUESTIONS_TIMEOUT      seconds one form stays open before the question
#                              falls back to the prompt (default 300, max 900).
#                              Must stay below the client's tool_timeout_sec.
#   AIT_QUESTIONS_MULTISELECT  text (default) | native
#   AIT_PYTHON                 interpreter to try first
#
# Spec: aidocs/codeagents/codex_questions.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"

state_dir="${AIT_QUESTIONS_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/aitasks/questions}"
timeout="${AIT_QUESTIONS_TIMEOUT:-300}"
multiselect="${AIT_QUESTIONS_MULTISELECT:-text}"

python_cmd=""
for cand in "${AIT_PYTHON:-}" "$HOME/.aitask/venv/bin/python" python3; do
    [[ -n "$cand" ]] || continue
    command -v "$cand" >/dev/null 2>&1 || continue
    if "$cand" -c 'import mcp.server, anyio' >/dev/null 2>&1; then
        python_cmd="$cand"
        break
    fi
done
if [[ -z "$python_cmd" ]]; then
    echo "aitask_questions: the 'mcp' Python package is not installed. Run 'ait setup' to install it." >&2
    exit 3
fi

exec "$python_cmd" "$SCRIPT_DIR/aitask_questions_server.py" \
    --project "$PROJECT_DIR" --state-dir "$state_dir" \
    --timeout "$timeout" --multiselect-mode "$multiselect"
