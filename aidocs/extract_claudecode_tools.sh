#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="${ROOT_DIR}/aidocs/claudecode_tools.md"

PROMPT=$(cat <<'PROMPT_EOF'
Write all the tools descriptions to aidocs/claudecode_tools.md with the current date and time and Claude Code version.

Requirements:
- Use the current working project root.
- Include only built-in tools available to the LLM in Claude Code for this session.
- Do NOT include skills, custom commands, or user-defined extensions — only tools.
- For each tool, include functionality and arguments.
- The output must be in Markdown format.
- Save the final result only to aidocs/claudecode_tools.md.
PROMPT_EOF
)

mkdir -p "${ROOT_DIR}/aidocs"

cd "${ROOT_DIR}"
claude -p \
  --dangerously-skip-permissions \
  "${PROMPT}"

if [[ -f "${OUTPUT_FILE}" ]]; then
  echo "Generated: ${OUTPUT_FILE}"
else
  echo "Claude Code run completed, but ${OUTPUT_FILE} was not created." >&2
  exit 1
fi
