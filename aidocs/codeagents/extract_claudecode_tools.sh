#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_FILE="${ROOT_DIR}/aidocs/codeagents/claudecode_tools.md"

PROMPT=$(cat <<'PROMPT_EOF'
Write all the tools descriptions to aidocs/codeagents/claudecode_tools.md with the current date and time and Claude Code version.

Requirements:
- Use the current working project root.
- Include only built-in tools available to the LLM in Claude Code for this session.
- Do NOT include skills, custom commands, or user-defined extensions — only tools.
- For each tool, include functionality and arguments.
- The output must be in Markdown format.
- Save the final result only to aidocs/codeagents/claudecode_tools.md.
PROMPT_EOF
)

mkdir -p "${ROOT_DIR}/aidocs/codeagents"

cd "${ROOT_DIR}"
# Interactive paste-and-go (NOT `claude -p`): headless print mode is billed at a
# higher per-token rate. The session runs the prompt, then exits when you quit.
claude \
  --dangerously-skip-permissions \
  "${PROMPT}"

if [[ -f "${OUTPUT_FILE}" ]]; then
  echo "Generated: ${OUTPUT_FILE}"
else
  echo "Claude Code run completed, but ${OUTPUT_FILE} was not created." >&2
  exit 1
fi
