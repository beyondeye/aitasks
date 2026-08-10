#!/usr/bin/env bash
# test_followup_kind_roundtrip.sh - Tests for `followup_kind:` (t1468_1)
# frontmatter registration.
#
# The hazard: aitask_update.sh parses frontmatter with an allowlist `case`
# that has NO default arm, and rebuilds the block from a fixed positional
# field list, so an UNregistered field is silently dropped on any `ait update`.
# These tests prove the field is durable and correctly gated:
#   - an unrelated `ait update` (e.g. --status) PRESERVES it,
#   - --followup-kind sets / replaces, and "" CLEARS by removing the line,
#   - an invalid kind is rejected non-zero with the file byte-unchanged,
#   - create writes it (incl. the draft path that finalize copies forward),
#   - the manual_verification cross-field invariant holds in BOTH violation
#     directions (kind-only and type-only) and permits the paired transition,
#   - every write_task_file call site forwards the new positional.
#
# Run: bash tests/test_followup_kind_roundtrip.sh

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
CREATE="$PROJECT_DIR/.aitask-scripts/aitask_create.sh"

A_TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_fk_roundtrip_XXXXXX")"
CLEANUP_DIRS+=("$A_TMP")
mkdir -p "$A_TMP/aitasks/metadata" "$A_TMP/aitasks/t60"
: > "$A_TMP/aitasks/metadata/labels.txt"
printf 'feature\nbug\nchore\ntest\nmanual_verification\n' \
    > "$A_TMP/aitasks/metadata/task_types.txt"

# Value of a frontmatter field, or "" when the key is absent.
field() { # field <file> <name>
    awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{sub("^"f":[[:space:]]*",""); print; exit}' "$1"
}

# PRESENT/ABSENT for the key itself. `field` alone cannot tell an absent key
# from one whose value is empty, and the clear-semantics of this field are
# exactly "the line is gone" -- so absence needs its own probe.
has_field() { # has_field <file> <name>
    if awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{found=1; exit} END{exit !found}' "$1"; then
        echo PRESENT
    else
        echo ABSENT
    fi
}

digest() { cksum < "$1"; }

# Run update the way `ait` does: from the project root with a relative TASK_DIR.
upd() { ( cd "$A_TMP" && TASK_DIR=aitasks "$UPD" "$@" ); }
crt() { ( cd "$A_TMP" && TASK_DIR=aitasks "$CREATE" "$@" ); }

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

# ============================================================
# Part A - durability (THE negative control)
# ============================================================
echo "--- Part A: update durability ---"

seed_task "$A_TMP/aitasks/t50_demo.md" "followup_kind: risk_mitigation"

# THE durability regression: an unrelated update must NOT drop followup_kind.
upd --batch 50 --status Editing --silent >/dev/null 2>&1
assert_eq "unrelated --status update preserves followup_kind" "risk_mitigation" \
    "$(field "$A_TMP/aitasks/t50_demo.md" followup_kind)"

# A second, different unrelated update (read-modify-write) also preserves it.
upd --batch 50 --priority low --silent >/dev/null 2>&1
assert_eq "unrelated --priority update preserves followup_kind" "risk_mitigation" \
    "$(field "$A_TMP/aitasks/t50_demo.md" followup_kind)"

echo "--- Part A: set / replace / clear ---"

upd --batch 50 --followup-kind upstream_defect --silent >/dev/null 2>&1
assert_eq "--followup-kind replaces the value" "upstream_defect" \
    "$(field "$A_TMP/aitasks/t50_demo.md" followup_kind)"

upd --batch 50 --followup-kind "" --silent >/dev/null 2>&1
assert_eq "--followup-kind '' removes the key entirely" "ABSENT" \
    "$(has_field "$A_TMP/aitasks/t50_demo.md" followup_kind)"

# A task never given the flag must not sprout an empty field.
seed_task "$A_TMP/aitasks/t51_nokind.md"
upd --batch 51 --status Editing --silent >/dev/null 2>&1
assert_eq "task without the flag gains no followup_kind key" "ABSENT" \
    "$(has_field "$A_TMP/aitasks/t51_nokind.md" followup_kind)"

echo "--- Part A: invalid value rejected, file byte-unchanged ---"

seed_task "$A_TMP/aitasks/t52_bad.md" "followup_kind: carry_over"
before="$(digest "$A_TMP/aitasks/t52_bad.md")"
upd --batch 52 --followup-kind not_a_real_kind --silent >/dev/null 2>&1
rc=$?
assert_exit_nonzero_rc "invalid followup_kind is rejected" "$rc"
assert_eq "invalid followup_kind leaves the file byte-unchanged" \
    "$before" "$(digest "$A_TMP/aitasks/t52_bad.md")"

# ============================================================
# Part B - create: draft, draft->finalize, and child serializers
# ============================================================
echo "--- Part B: create ---"

# `--batch` alone writes a DRAFT (create_draft_file); `--batch --finalize`
# claims a real id and moves it into aitasks/ via the strip-sed. Both
# serializers must emit, and the sed must carry the field through. Finalize
# claims an id, so this part needs a real git repo.
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
B_TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_fk_create_XXXXXX")"
CLEANUP_DIRS+=("$B_TMP")
git init --bare --quiet "$B_TMP/remote.git"
git clone --quiet "$B_TMP/remote.git" "$B_TMP/local" 2>/dev/null
(
    cd "$B_TMP/local" || exit 1
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/metadata aitasks/new aitasks/archived
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    chmod +x .aitask-scripts/*.sh
    printf 'feature\nbug\nchore\ntest\nmanual_verification\n' > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt
    echo "aitasks/new/" > .gitignore
    git add -A && git commit -m "seed" --quiet
    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1 || true
) || true

bcrt() { ( cd "$B_TMP/local" && bash .aitask-scripts/aitask_create.sh "$@" 2>/dev/null ); }

draft="$(bcrt --batch --silent --name fk_draft --desc body --followup-kind qa_test_gap)"
if [[ -n "$draft" && -f "$B_TMP/local/$draft" ]]; then
    assert_eq "create_draft_file emits followup_kind" "qa_test_gap" \
        "$(field "$B_TMP/local/$draft" followup_kind)"
    ( cd "$B_TMP/local" && bash .aitask-scripts/aitask_create.sh --batch \
        --finalize "$(basename "$draft")" >/dev/null 2>&1 ) || true
    finalized="$(ls "$B_TMP"/local/aitasks/t*_fk_draft.md 2>/dev/null | head -n1)"
    if [[ -n "$finalized" ]]; then
        assert_eq "draft --finalize carries followup_kind through" "qa_test_gap" \
            "$(field "$finalized" followup_kind)"
    else
        TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
        echo "FAIL: draft --finalize carries followup_kind through (not finalized)"
    fi
else
    TOTAL=$((TOTAL + 2)); FAIL=$((FAIL + 2))
    echo "FAIL: create_draft_file emits followup_kind (draft not created)"
    echo "FAIL: draft --finalize carries followup_kind through (draft not created)"
fi

# A draft created without the flag must not sprout an empty key.
draft_nk="$(bcrt --batch --silent --name fk_nokind --desc body)"
if [[ -n "$draft_nk" && -f "$B_TMP/local/$draft_nk" ]]; then
    assert_eq "draft without the flag has no followup_kind key" "ABSENT" \
        "$(has_field "$B_TMP/local/$draft_nk" followup_kind)"
else
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: draft without the flag has no followup_kind key (draft not created)"
fi

# create_child_task_file is a third, separate serializer.
( cd "$B_TMP/local" && bash .aitask-scripts/aitask_create.sh --batch --silent \
    --name fk_parent --desc body >/dev/null 2>&1 ) || true
parent_draft="$(ls "$B_TMP"/local/aitasks/new/*fk_parent.md 2>/dev/null | head -n1)"
[[ -n "$parent_draft" ]] && ( cd "$B_TMP/local" && bash .aitask-scripts/aitask_create.sh \
    --batch --finalize "$(basename "$parent_draft")" >/dev/null 2>&1 ) || true
parent_file="$(ls "$B_TMP"/local/aitasks/t*_fk_parent.md 2>/dev/null | head -n1)"
if [[ -n "$parent_file" ]]; then
    pnum="$(basename "$parent_file" | sed 's/^t\([0-9]*\)_.*/\1/')"
    # --parent also drafts first; create_child_task_file runs at finalize time.
    child_draft="$(bcrt --batch --silent --parent "$pnum" --name fk_child \
        --desc body --followup-kind review_finding)"
    [[ -n "$child_draft" ]] && ( cd "$B_TMP/local" && bash .aitask-scripts/aitask_create.sh \
        --batch --finalize "$(basename "$child_draft")" >/dev/null 2>&1 ) || true
    child_file="$(ls "$B_TMP"/local/aitasks/t"$pnum"/t"$pnum"_*_fk_child.md 2>/dev/null | head -n1)"
    if [[ -n "$child_file" ]]; then
        assert_eq "create_child_task_file emits followup_kind" "review_finding" \
            "$(field "$child_file" followup_kind)"
    else
        TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
        echo "FAIL: create_child_task_file emits followup_kind (child not created)"
    fi
else
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: create_child_task_file emits followup_kind (parent not created)"
fi

# create rejects an invalid kind before writing anything.
( cd "$B_TMP/local" && bash .aitask-scripts/aitask_create.sh --batch --silent \
    --name fk_bad --desc body --followup-kind not_a_real_kind >/dev/null 2>&1 )
rc=$?
assert_exit_nonzero_rc "create rejects an invalid followup_kind" "$rc"
assert_eq "create writes no draft for an invalid kind" "" \
    "$(ls "$B_TMP"/local/aitasks/new/*fk_bad.md 2>/dev/null | head -n1)"

# create enforces the cross-field invariant too.
( cd "$B_TMP/local" && bash .aitask-scripts/aitask_create.sh --batch --silent \
    --name fk_mv --desc body --type feature \
    --followup-kind manual_verification >/dev/null 2>&1 )
rc=$?
assert_exit_nonzero_rc "create rejects MV kind on a non-MV type" "$rc"

# ============================================================
# Part C - manual_verification cross-field invariant
# ============================================================
echo "--- Part C: cross-field invariant ---"

# (1) kind-only violation: setting the kind on a non-MV task.
seed_task "$A_TMP/aitasks/t53_mv.md"
before="$(digest "$A_TMP/aitasks/t53_mv.md")"
upd --batch 53 --followup-kind manual_verification --silent >/dev/null 2>&1
rc=$?
assert_exit_nonzero_rc "kind-only violation rejected (feature task)" "$rc"
assert_eq "kind-only violation leaves the file byte-unchanged" \
    "$before" "$(digest "$A_TMP/aitasks/t53_mv.md")"

# (2) type-only violation: a consistent MV pair broken by changing ONLY the
#     type. A flag-level check cannot see this -- the invariant must be
#     evaluated on the RESULTING issue_type.
seed_task "$A_TMP/aitasks/t54_pair.md" "followup_kind: manual_verification"
( cd "$A_TMP" && TASK_DIR=aitasks "$UPD" --batch 54 --type manual_verification --silent ) >/dev/null 2>&1
before="$(digest "$A_TMP/aitasks/t54_pair.md")"
upd --batch 54 --type feature --silent >/dev/null 2>&1
rc=$?
assert_exit_nonzero_rc "type-only violation rejected (orphans the kind)" "$rc"
assert_eq "type-only violation leaves the file byte-unchanged" \
    "$before" "$(digest "$A_TMP/aitasks/t54_pair.md")"

# (3) the paired transition IS legal in one call.
upd --batch 54 --type feature --followup-kind carry_over --silent >/dev/null 2>&1
rc=$?
assert_exit_zero_rc "paired type+kind transition accepted" "$rc"
assert_eq "paired transition writes the new kind" "carry_over" \
    "$(field "$A_TMP/aitasks/t54_pair.md" followup_kind)"
assert_eq "paired transition writes the new type" "feature" \
    "$(field "$A_TMP/aitasks/t54_pair.md" issue_type)"

# (4) the converse pairing stays legal: an MV task may carry another kind.
seed_task "$A_TMP/aitasks/t55_conv.md"
upd --batch 55 --type manual_verification --followup-kind carry_over --silent >/dev/null 2>&1
rc=$?
assert_exit_zero_rc "MV task may carry a non-MV kind (converse allowed)" "$rc"

# ============================================================
# Part D - the parent children-cleanup write path (call site :1161)
# ============================================================
echo "--- Part D: parent children-cleanup write path ---"

# This route rewrites the PARENT file through its own write_task_file call with
# an independent argument list. A batch-only durability test never touches it.
cat > "$A_TMP/aitasks/t60_parent.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
followup_kind: review_finding
children_to_implement: [t60_1]
created_at: 2026-08-10 09:00
updated_at: 2026-08-10 09:00
---

## Context
Parent body.
EOF
seed_task "$A_TMP/aitasks/t60/t60_1_child.md"

upd --batch 60_1 --status Done --silent >/dev/null 2>&1
assert_eq "parent children-cleanup write preserves parent followup_kind" \
    "review_finding" "$(field "$A_TMP/aitasks/t60_parent.md" followup_kind)"
# Positive control that the cleanup route actually ran: the parent went in with
# children_to_implement: [t60_1], and the key is dropped entirely once it empties.
assert_eq "parent children-cleanup actually ran (child removed)" "ABSENT" \
    "$(has_field "$A_TMP/aitasks/t60_parent.md" children_to_implement)"

# ============================================================
# Part E - every write_task_file call site forwards the positional
# ============================================================
echo "--- Part E: call-site coverage (structural) ---"

# The call sites pass independent argument lists; none delegates to another.
# Parts A/D drive the batch and parent-cleanup routes for real, but the
# interactive site needs a TTY -- so guard ALL of them structurally: every
# write_task_file invocation must end by forwarding the new positional.
#
# Both patterns are anchored to a whole line so the `local
# new_followup_kind="$CURRENT_FOLLOWUP_KIND"` assignment and the invariant call
# are not miscounted as forwards.
UPD_SRC="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"
call_sites="$(grep -cE '^[[:space:]]*write_task_file "' "$UPD_SRC")"
forwarded="$(grep -cE '^[[:space:]]*"\$(CURRENT_FOLLOWUP_KIND|new_followup_kind)"$' "$UPD_SRC")"
assert_eq "every write_task_file call site forwards followup_kind" \
    "$call_sites" "$forwarded"
# ...and the guard itself is not vacuous: the call sites still exist.
assert_eq "write_task_file call-site count is unchanged" "3" "$call_sites"

# Every write path that can CHANGE issue_type must enforce the cross-field
# invariant. Part C drives the batch path for real; the interactive path needs a
# TTY, so it is guarded structurally here -- the two counts must move together.
#
# The parent children-cleanup path is deliberately EXCLUDED: it re-writes
# `$CURRENT_TYPE` unchanged, so it cannot introduce a violation, and dying there
# would block an unrelated parent update on a task whose pair was already
# inconsistent from a hand edit ("enforce at the write seams, tolerate at read").
type_changing="$(grep -cE '^[[:space:]]+"\$new_type" ' "$UPD_SRC")"
enforced="$(grep -cE '^[[:space:]]*enforce_manual_verification_kind_invariant ' "$UPD_SRC")"
assert_eq "every type-changing write path enforces the MV invariant" \
    "$type_changing" "$enforced"
assert_eq "there are still two type-changing write paths (batch + interactive)" \
    "2" "$type_changing"

# The interactive enforcement must sit BEFORE its write, not after it -- a check
# that runs post-write would let the forbidden pair reach disk.
interactive_check="$(grep -nE '^[[:space:]]*enforce_manual_verification_kind_invariant "\$new_type" "\$CURRENT_FOLLOWUP_KIND"' "$UPD_SRC" | cut -d: -f1)"
interactive_write="$(grep -nE '^[[:space:]]+"\$new_type" ' "$UPD_SRC" | head -n1 | cut -d: -f1)"
TOTAL=$((TOTAL + 1))
if [[ -n "$interactive_check" && -n "$interactive_write" \
   && "$interactive_check" -lt "$interactive_write" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: interactive MV check must precede its write (check=$interactive_check write=$interactive_write)"
fi

# ============================================================
# Part F - the vocabulary bridge fails closed
# ============================================================
echo "--- Part F: bridge fails closed ---"

EMPTY_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_fk_empty_XXXXXX")"
CLEANUP_DIRS+=("$EMPTY_DIR")
seed_task "$A_TMP/aitasks/t56_bridge.md"
before="$(digest "$A_TMP/aitasks/t56_bridge.md")"
( cd "$A_TMP" && TASK_DIR=aitasks AIT_FOLLOWUP_KINDS_DIR="$EMPTY_DIR" \
    "$UPD" --batch 56 --followup-kind carry_over --silent ) >/dev/null 2>&1
rc=$?
assert_exit_nonzero_rc "unreachable vocabulary module fails closed" "$rc"
assert_eq "failed-closed validation leaves the file byte-unchanged" \
    "$before" "$(digest "$A_TMP/aitasks/t56_bridge.md")"

# ============================================================
echo ""
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ $FAIL -eq 0 ]] || exit 1
exit 0
