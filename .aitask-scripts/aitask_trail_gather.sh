#!/usr/bin/env bash

# aitask_trail_gather.sh - Deterministic gatherer + drift checker for
# implementation trails (t1210_2; RFC aidocs/implementation_trail_design.md).
#
# Verbs (line protocol documented in lib/trail_gather.py):
#   snapshot --scope task|topic|multi_topic [--owner <id>] <ids...>
#   drift --trail <path-or-art:handle>
#
# Must be invoked with cwd at the project root (the `ait` dispatcher / skill
# convention — the artifact CLI and the Python lib resolve config paths
# relative to cwd). Internal skill helper — deliberately NOT wired into the
# `ait` dispatcher.
#
# Handle resolution boundary: a `drift --trail art:<handle>` argument is
# resolved here via aitask_artifact.sh into a temp file; the Python lib only
# ever sees a path. The artifact CLI's success output ("Wrote <path>") goes
# to stderr so stdout stays protocol-clean; a failed resolution emits
# ERROR:artifact_unresolved:<handle> on stdout and exits 0 (a validation
# outcome consumers can distinguish from CURRENT/STALE/invalid_trail).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh disable=SC1091
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh disable=SC1091
source "$SCRIPT_DIR/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

# Rewrite `drift --trail art:<handle>` into a temp-file path; everything else
# passes through untouched.
args=("$@")
tmp_trail=""
cleanup() { if [[ -n "$tmp_trail" ]]; then rm -f "$tmp_trail"; fi; }
trap cleanup EXIT

if [[ "${1:-}" == "drift" ]]; then
    for i in "${!args[@]}"; do
        if [[ "${args[$i]}" == "--trail" ]]; then
            next=$((i + 1))
            handle="${args[$next]:-}"
            if [[ "$handle" == art:* ]]; then
                tmp_trail="$(mktemp "${TMPDIR:-/tmp}/trail_gather.XXXXXX")"
                # Success output ("Wrote <path>") must not pollute the
                # protocol stream -- redirect stdout to stderr.
                if ! "$SCRIPT_DIR/aitask_artifact.sh" get "$handle" \
                        --out "$tmp_trail" 1>&2; then
                    echo "ERROR:artifact_unresolved:$handle"
                    exit 0
                fi
                args[next]="$tmp_trail"
            fi
            break
        fi
    done
fi

"$PYTHON" "$SCRIPT_DIR/lib/trail_gather.py" "${args[@]}"
