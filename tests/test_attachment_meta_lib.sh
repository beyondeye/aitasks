#!/usr/bin/env bash
# test_attachment_meta_lib.sh - the shared bash front lib/attachment_meta.sh
# (t1030_3): the duration parser (gc grace knob), the task-hash reader (gc
# blocking scan), and the meta relpath shape. Pure helpers — no git required.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/yaml_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/attachment_meta.sh"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# The lib helpers `die` (exit 1) on bad input. assert_exit_nonzero runs its
# command in the current shell, so a sourced function's `exit` would kill the
# test — wrap the failure-path calls in a subshell so the exit is contained.
pdts() { ( parse_duration_to_seconds "$@" ); }

# ── parse_duration_to_seconds ────────────────────────────────────────────────
assert_eq "30d -> seconds"  "2592000" "$(parse_duration_to_seconds 30d)"
assert_eq "24h -> seconds"  "86400"   "$(parse_duration_to_seconds 24h)"
assert_eq "90m -> seconds"  "5400"    "$(parse_duration_to_seconds 90m)"
assert_eq "120s -> seconds" "120"     "$(parse_duration_to_seconds 120s)"
assert_eq "bare integer is seconds" "45" "$(parse_duration_to_seconds 45)"
assert_exit_nonzero "garbage duration dies"  pdts "lots"
assert_exit_nonzero "empty duration dies"    pdts ""
assert_exit_nonzero "unknown unit dies"      pdts "5y"

# ── attach_meta_relpath ──────────────────────────────────────────────────────
H="sha256:abcdef0000000000000000000000000000000000000000000000000000000000"
assert_eq "meta relpath shards <2>/<62>.json" \
    "attachments/meta/ab/cdef0000000000000000000000000000000000000000000000000000000000.json" \
    "$(attach_meta_relpath "$H")"

# ── attach_task_hashes ───────────────────────────────────────────────────────
HA="sha256:1111111111111111111111111111111111111111111111111111111111111111"
HB="sha256:2222222222222222222222222222222222222222222222222222222222222222"
task="$TMP/t9_demo.md"
cat > "$task" <<EOF
---
priority: medium
status: Implementing
attachments:
  - hash: $HA
    name: a.png
    backend: local
  - hash: $HB
    name: b.png
    backend: local
updated_at: 2026-01-01 00:00
---

Body.
EOF
got="$(attach_task_hashes "$task" | paste -sd, -)"
assert_eq "attach_task_hashes lists every attachment hash" "$HA,$HB" "$got"

noatt="$TMP/t10_none.md"
printf -- '---\nstatus: Ready\nupdated_at: 2026-01-01 00:00\n---\nNo attachments.\n' > "$noatt"
assert_eq "attach_task_hashes is empty for a task with no attachments" "" "$(attach_task_hashes "$noatt")"

echo ""
echo "test_attachment_meta_lib.sh: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
