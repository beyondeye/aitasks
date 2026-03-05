#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="${ROOT_DIR}/aidocs/opencode_tools.md"

PROMPT=$(cat <<'PROMPT_EOF'
Write all the tools descriptions to aidocs/opencode_tools.md with the current date and time and OpenCode version.

Requirements:
- Use the current working project root.
- Include only built-in tools available to the LLM in OpenCode for this session.
- Do NOT include skills, custom commands, or user-defined extensions — only tools.
- For each tool, include functionality and arguments.
- The output must be in Markdown format.
- Save the final result only to aidocs/opencode_tools.md.
PROMPT_EOF
)

mkdir -p "${ROOT_DIR}/aidocs"

# OpenCode has no --dangerously-skip-permissions flag. Create a temporary
# project config with "permission": "allow" so the run doesn't block on
# permission prompts, then restore the original config (if any) on exit.
OC_CONFIG="${ROOT_DIR}/opencode.json"
OC_CONFIG_BAK="${OC_CONFIG}.extract-bak"
cleanup() {
  if [[ -f "${OC_CONFIG_BAK}" ]]; then
    mv "${OC_CONFIG_BAK}" "${OC_CONFIG}"
  elif [[ -f "${OC_CONFIG}" ]]; then
    rm -f "${OC_CONFIG}"
  fi
}
trap cleanup EXIT

if [[ -f "${OC_CONFIG}" ]]; then
  cp "${OC_CONFIG}" "${OC_CONFIG_BAK}"
fi
# $schema is literal JSON, not a variable
# shellcheck disable=SC2016
echo '{"$schema": "https://opencode.ai/config.json", "permission": "allow"}' > "${OC_CONFIG}"

cd "${ROOT_DIR}"
opencode run \
  --dir "${ROOT_DIR}" \
  "${PROMPT}"

if [[ -f "${OUTPUT_FILE}" ]]; then
  echo "Generated: ${OUTPUT_FILE}"
else
  echo "OpenCode run completed, but ${OUTPUT_FILE} was not created." >&2
  exit 1
fi
