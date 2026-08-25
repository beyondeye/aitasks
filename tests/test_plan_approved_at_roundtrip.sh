#!/usr/bin/env bash
# test_plan_approved_at_roundtrip.sh - Tests for `plan_approved_at:` (t1595)
# frontmatter registration.
#
# The field marks a task whose plan was approved and whose implementation was
# deliberately deferred ("Approve and stop here"), so `ait ls` and the planning
# step's existing-plan prompt can tell it apart from a never-planned task.
#
# The hazard is the one aidocs/framework/aitasks_extension_points.md names:
# aitask_update.sh parses frontmatter with an allowlist `case` that has NO
# default arm and rebuilds the block from a fixed positional field list, so an
# unregistered -- or half-threaded -- field is silently dropped on any
# `ait update`. These tests prove:
#   - an unrelated `ait update` (e.g. --status) PRESERVES the marker,
#   - the parent child-completion write path preserves it too (the one call site
#     a batch-update test never exercises -- the post-phase mitigation of t1595),
#   - `now` resolves to a well-formed timestamp, an explicit one is kept,
#   - "" CLEARS by removing the line, and a task never given the flag does not
#     sprout an empty key,
#   - a malformed value is rejected non-zero with the file byte-unchanged,
#   - every write_task_file call site forwards the new positional.
#
# Run: bash tests/test_plan_approved_at_roundtrip.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]:-}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
}
trap cleanup EXIT

UPD="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_paa_roundtrip_XXXXXX")"
CLEANUP_DIRS+=("$TMP")
mkdir -p "$TMP/aitasks/metadata" "$TMP/aitasks/t60"
: > "$TMP/aitasks/metadata/labels.txt"
printf 'feature\nbug\nchore\ntest\nmanual_verification\n' \
    > "$TMP/aitasks/metadata/task_types.txt"

# Value of a frontmatter field, or "" when the key is absent.
field() { # field <file> <name>
    awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{sub("^"f":[[:space:]]*",""); print; exit}' "$1"
}

# PRESENT/ABSENT for the key itself. `field` alone cannot tell an absent key
# from one whose value is empty, and clearing this field means "the line is
# gone" -- so absence needs its own probe.
has_field() { # has_field <file> <name>
    if awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{found=1; exit} END{exit !found}' "$1"; then
        echo PRESENT
    else
        echo ABSENT
    fi
}

digest() { cksum < "$1"; }

upd() { ( cd "$TMP" && TASK_DIR=aitasks "$UPD" "$@" ); }

seed_task() { # seed_task <path> <extra frontmatter line(s)>
    local path="$1" extra="${2:-}"
    {
        echo "---"
        echo "priority: high"
        echo "effort: medium"
        echo "depends: []"
        echo "issue_type: feature"
        echo "status: Ready"
        echo "labels: []"
        [[ -n "$extra" ]] && printf '%s\n' "$extra"
        echo "created_at: 2026-08-10 09:00"
        echo "updated_at: 2026-08-10 09:00"
        echo "---"
        echo ""
        echo "## Context"
        echo "Body."
    } > "$path"
}

MARKER="2026-08-20 09:15"

# ============================================================
# Part A - durability (THE regression this field is exposed to)
# ============================================================
echo "--- Part A: update durability ---"

seed_task "$TMP/aitasks/t50_demo.md" "plan_approved_at: $MARKER"

upd --batch 50 --status Editing --silent >/dev/null 2>&1
assert_eq "unrelated --status update preserves plan_approved_at" "$MARKER" \
    "$(field "$TMP/aitasks/t50_demo.md" plan_approved_at)"

upd --batch 50 --priority low --silent >/dev/null 2>&1
assert_eq "unrelated --priority update preserves plan_approved_at" "$MARKER" \
    "$(field "$TMP/aitasks/t50_demo.md" plan_approved_at)"

# ============================================================
# Part B - set (now / explicit) and clear
# ============================================================
echo "--- Part B: set / clear ---"

upd --batch 50 --plan-approved-at now --silent >/dev/null 2>&1
stamped="$(field "$TMP/aitasks/t50_demo.md" plan_approved_at)"
TOTAL=$((TOTAL + 1))
if [[ "$stamped" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}$ ]]; then
    PASS=$((PASS + 1))
    echo "PASS: --plan-approved-at now stamps a well-formed timestamp ($stamped)"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: --plan-approved-at now stamps a well-formed timestamp (got '$stamped')"
fi
# ...and "now" is resolved, never written through verbatim.
assert_not_contains "the literal 'now' never reaches the file" "now" "$stamped"

upd --batch 50 --plan-approved-at "$MARKER" --silent >/dev/null 2>&1
assert_eq "--plan-approved-at <ts> replaces the value" "$MARKER" \
    "$(field "$TMP/aitasks/t50_demo.md" plan_approved_at)"

upd --batch 50 --plan-approved-at "" --silent >/dev/null 2>&1
assert_eq "--plan-approved-at '' removes the key entirely" "ABSENT" \
    "$(has_field "$TMP/aitasks/t50_demo.md" plan_approved_at)"

# Clearing an already-absent marker is a no-op, not an empty key: every clear
# site in the workflow fires unconditionally, so this is the common case.
upd --batch 50 --plan-approved-at "" --silent >/dev/null 2>&1
assert_eq "clearing an absent marker stays ABSENT (idempotent)" "ABSENT" \
    "$(has_field "$TMP/aitasks/t50_demo.md" plan_approved_at)"

seed_task "$TMP/aitasks/t51_nomarker.md"
upd --batch 51 --status Editing --silent >/dev/null 2>&1
assert_eq "task without the flag gains no plan_approved_at key" "ABSENT" \
    "$(has_field "$TMP/aitasks/t51_nomarker.md" plan_approved_at)"

# ============================================================
# Part C - malformed values are rejected, file byte-unchanged
# ============================================================
echo "--- Part C: rejection ---"

seed_task "$TMP/aitasks/t52_bad.md" "plan_approved_at: $MARKER"
for bad in "yesterday" "2026-08-20" "2026-08-20T09:15Z" "not a date"; do
    before="$(digest "$TMP/aitasks/t52_bad.md")"
    upd --batch 52 --plan-approved-at "$bad" --silent >/dev/null 2>&1
    rc=$?
    assert_exit_nonzero_rc "malformed --plan-approved-at '$bad' is rejected" "$rc"
    assert_eq "malformed '$bad' leaves the file byte-unchanged" \
        "$before" "$(digest "$TMP/aitasks/t52_bad.md")"
done

# ============================================================
# Part D - parent child-completion write path (t1595 post-phase mitigation)
# ============================================================
#
# `--status Done` on a CHILD drives handle_child_task_completion, which rewrites
# the PARENT through its own write_task_file call site. That site is invisible to
# every assertion above, and a positional missed there drops the parent's marker
# with no error -- the exact silent-drop failure mode this field is exposed to.
echo "--- Part D: parent child-completion write path ---"

seed_task "$TMP/aitasks/t60_parent.md" "children_to_implement: [t60_1, t60_2]
plan_approved_at: $MARKER"
seed_task "$TMP/aitasks/t60/t60_1_child.md"
seed_task "$TMP/aitasks/t60/t60_2_child.md"

upd --batch 60_1 --status Done --silent >/dev/null 2>&1

assert_eq "parent's plan_approved_at survives a child's --status Done" "$MARKER" \
    "$(field "$TMP/aitasks/t60_parent.md" plan_approved_at)"
# The guard is not vacuous: the parent really was rewritten by that path.
assert_eq "the child-completion path did rewrite the parent" "[t60_2]" \
    "$(field "$TMP/aitasks/t60_parent.md" children_to_implement)"

# ============================================================
# Part E - structural: every write_task_file call site forwards the positional
# ============================================================
echo "--- Part E: call-site forwarding ---"

UPD_SRC="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"
call_sites="$(grep -cE '^[[:space:]]*write_task_file "' "$UPD_SRC")"
forwarded="$(grep -cE '^[[:space:]]*"\$(CURRENT_PLAN_APPROVED_AT|new_plan_approved_at)"[[:space:]]*\\?$' "$UPD_SRC")"
assert_eq "every write_task_file call site forwards plan_approved_at" \
    "$call_sites" "$forwarded"
# ...and the guard itself is not vacuous: the call sites still exist.
assert_eq "write_task_file call-site count is unchanged" "3" "$call_sites"

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -ne 0 ]]; then
    echo "Failed: $FAIL"
    echo "===================="
    exit 1
fi
echo "===================="
