#!/usr/bin/env bash
# aitask_relations.sh - `ait relations`: the task-relations store and analysis.
#
# Records live on the orphan branch `aitask-relations`, never in task files.
# Design: aidocs/framework/task_relations.md (D1 store, D2 schema, D3 lookup,
# D5 worker, D8 completeness, D11 freshness, and the "Store API" and "Worker
# API" sections). Implementation: lib/relations_cli.py -> lib/relations_store.py
# -> lib/orphan_ref_store.py; analysis: lib/relations_worker.py,
# lib/relations_spool.py, lib/relations_config.py.
#
# Store verbs (t1981_1): show <id> [--json] [--no-fetch] | why <a> <b>
#   [--no-fetch] | status | flush | gc [--dry-run]
# Analysis verbs (t1981_3): analyze <id> [--dry-run] [--now [--wait <s>]]
#   [--over-cap] | stamp <id> | plan-digest <id> | analysis-state <id>
#   [--expect-plan <sha>] | usage [--days N] | ledgers --export
#   | unblock <id> [--kill] [--force] | enable | disable
# Every reader output starts with RELATIONS_STATE: / STORE: / ANALYSIS: lines.
# Exit: 0 ok, 1 usage/validation error, 2 unknown verb, 3 kept for retry
# (RETAINED:), refused (GC_REFUSED:, CAP_REACHED:, BLOCKED_UNRESOLVED,
# STILL_UNRESOLVED:) or a bounded wait that ran out (WAIT_TIMEOUT:).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

PY="$(require_ait_python)"
exec "$PY" "$SCRIPT_DIR/lib/relations_cli.py" "$@"
