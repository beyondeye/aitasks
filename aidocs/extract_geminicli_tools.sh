#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="${ROOT_DIR}/aidocs/geminicli_tools.md"

PROMPT=$(cat <<'PROMPT_EOF'
Write all the tools descriptions to aidocs/geminicli_tools.md with the current date and time and gemini CLI version.

Requirements:
- Use the current working project root.
- Include all available tools to the LLM in Gemini CLI for this session.
- For each tool, include functionality and arguments.
- The output must be in Markdown format.
- Save the final result only to aidocs/geminicli_tools.md.
PROMPT_EOF
)

mkdir -p "${ROOT_DIR}/aidocs"

cd "${ROOT_DIR}"
gemini 
  --yolo 
  --prompt "${PROMPT}"

if [[ -f "${OUTPUT_FILE}" ]]; then
  echo "Generated: ${OUTPUT_FILE}"
else
  echo "Gemini run completed, but ${OUTPUT_FILE} was not created." >&2
  exit 1
fi
