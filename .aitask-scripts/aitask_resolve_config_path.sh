#!/usr/bin/env bash
# aitask_resolve_config_path.sh — Resolve a settings-defined file path with a
# seeded-default fallback.
#
# The canonical CLI seam for "a project_config.yaml value that names a file on
# disk, with a fallback to the guide/template ait setup installed". Skills shell
# out to it; Python callers should import config_utils.resolve_config_path
# directly. Reading via PyYAML (the same parser the settings TUI writes with)
# handles quoted values, inline # comments, whitespace, and dotted/nested keys
# uniformly — unlike a hand-rolled grep in a skill.
#
# Usage:
#   aitask_resolve_config_path.sh <dotted.key> [default_rel]
#
# Contract: ALWAYS exits 0 and prints exactly one line — the resolved
# repo-root-relative path, or an EMPTY line when nothing usable exists OR the
# resolver itself cannot run (missing python3, missing PyYAML, import/parse
# error). A caller may therefore treat "empty output" and "any failure"
# identically and fall back to its own behaviour; the helper never aborts it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
key="${1:?usage: aitask_resolve_config_path.sh <dotted.key> [default_rel]}"
default_rel="${2:-}"

# The heredoc lives inside a function with NO trailing operators on the <<'PY'
# line; error handling is applied to the function CALL, cleanly outside it.
_run_resolver() {
  PYTHONPATH="$REPO_ROOT/.aitask-scripts/lib" python3 - "$REPO_ROOT" "$key" "$default_rel" <<'PY'
import sys
try:
    from config_utils import resolve_config_path
    root, key, default_rel = sys.argv[1], sys.argv[2], (sys.argv[3] or None)
    print(resolve_config_path(key, default_rel, root=root) or "")
except Exception:
    print("")
PY
}

out=""
if command -v python3 >/dev/null 2>&1; then
  # 2>/dev/null and || apply to the function call, not the heredoc.
  out="$(_run_resolver 2>/dev/null)" || out=""
fi
printf '%s\n' "$out"
exit 0
