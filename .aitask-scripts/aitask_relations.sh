#!/usr/bin/env bash
# aitask_relations.sh - `ait relations`: the task-relations store (t1981_1).
#
# Records live on the orphan branch `aitask-relations`, never in task files.
# Design: aidocs/framework/task_relations.md (D1 store, D2 schema, D3 lookup,
# D11 freshness, and the "Store API" section). Implementation:
# lib/relations_cli.py -> lib/relations_store.py -> lib/orphan_ref_store.py.
#
# Verbs (this child): show <id> [--json] [--no-fetch] | why <a> <b> [--no-fetch]
#                     | status | flush | gc [--dry-run]
# Every reader output starts with RELATIONS_STATE: / STORE: / ANALYSIS: lines.
# Exit: 0 ok, 1 usage/validation error, 2 unknown verb, 3 kept for retry
# (RETAINED:) or refused (GC_REFUSED:).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

PY="$(require_ait_python)"
exec "$PY" "$SCRIPT_DIR/lib/relations_cli.py" "$@"
