#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="${ROOT_DIR}/aidocs/codexcli_tools.md"

PROMPT=$(cat <<'PROMPT_EOF'
Write all the tools descriptions to aidocs/codexcli_tools.md with the current date and time and codecli version.

Requirements:
- Use the current working project root.
- Include all available tools to the LLM in Codex CLI for this session.
- For each tool, include functionality and arguments.
- The output must be in Markdown format.
- Save the final result only to aidocs/codexcli_tools.md.
PROMPT_EOF
)

mkdir -p "${ROOT_DIR}/aidocs"

codex exec \
  --cd "${ROOT_DIR}" \
  --skip-git-repo-check \
  --full-auto \
  "${PROMPT}"

if [[ -f "${OUTPUT_FILE}" ]]; then
  echo "Generated: ${OUTPUT_FILE}"
else
  echo "Codex run completed, but ${OUTPUT_FILE} was not created." >&2
  exit 1
fi
