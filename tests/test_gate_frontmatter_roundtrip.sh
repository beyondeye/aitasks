#!/usr/bin/env bash
# test_gate_frontmatter_roundtrip.sh - Tests for `gates:` (t635_1) and
# `also_blocks_dependents:` (t635_3) frontmatter registration.
#
# The hazard: aitask_update.sh reconstructs frontmatter from a fixed positional
# field list, so an UNregistered field is silently dropped on any `ait update`.
# These tests prove both fields are durable across update/create/fold:
#   - an unrelated `ait update` (e.g. --status) PRESERVES them,
#   - --gates / --also-blocks-dependents replace / clear,
#   - create --gates writes it (draft path that finalize copies forward),
#   - fold unions both lists across folded tasks into the primary.
#
# Run: bash tests/test_gate_frontmatter_roundtrip.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/terminal_compat.sh
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

UPD="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"
CREATE="$PROJECT_DIR/.aitask-scripts/aitask_create.sh"

# ============================================================
# Part A — update / create durability (lightweight, no git)
# ============================================================

A_TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_gate_fm_A_XXXXXX")"
CLEANUP_DIRS+=("$A_TMP")
mkdir -p "$A_TMP/aitasks/metadata"
: > "$A_TMP/aitasks/metadata/labels.txt"
printf 'feature\nbug\nchore\n' > "$A_TMP/aitasks/metadata/task_types.txt"

cat > "$A_TMP/aitasks/t50_demo.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ui, backend]
gates: [tests_pass, review]
created_at: 2026-06-14 09:00
updated_at: 2026-06-14 09:00
---

## Context
Body.
EOF

field() { # field <file> <name>
    awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{sub("^"f":[[:space:]]*",""); print; exit}' "$1"
}

# Run update from inside the temp dir with a relative TASK_DIR — the way `ait`
# invokes scripts (from the project root). An absolute TASK_DIR while cwd is a
# different git/data-worktree repo confuses data-worktree detection.
upd() { ( cd "$A_TMP" && TASK_DIR=aitasks "$UPD" "$@" ); }

echo "--- Part A: update durability ---"
# THE durability regression: an unrelated update must NOT drop gates.
upd --batch 50 --status Editing --silent >/dev/null
assert_eq "unrelated --status update preserves gates" "[tests_pass, review]" \
    "$(field "$A_TMP/aitasks/t50_demo.md" gates)"

# --gates replaces.
upd --batch 50 --gates "tests_pass,docs_updated" --silent >/dev/null
assert_eq "--gates replaces the set" "[tests_pass, docs_updated]" \
    "$(field "$A_TMP/aitasks/t50_demo.md" gates)"

# --gates "" clears (field omitted entirely).
upd --batch 50 --gates "" --silent >/dev/null
assert_eq "--gates '' clears the field" "" \
    "$(field "$A_TMP/aitasks/t50_demo.md" gates)"

# A task with NO gates stays without one after an unrelated update.
cat > "$A_TMP/aitasks/t51_nogate.md" <<'EOF'
---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: []
created_at: 2026-06-14 09:00
updated_at: 2026-06-14 09:00
---

body
EOF
upd --batch 51 --status Editing --silent >/dev/null
assert_eq "no-gates task gets no empty gates field" "" \
    "$(field "$A_TMP/aitasks/t51_nogate.md" gates)"

echo "--- Part A: also_blocks_dependents durability (t635_3) ---"
cat > "$A_TMP/aitasks/t52_abd.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
gates: [build_verified]
also_blocks_dependents: [docs_updated]
created_at: 2026-06-14 09:00
updated_at: 2026-06-14 09:00
---

body
EOF
# THE durability regression: an unrelated update must NOT drop the field.
upd --batch 52 --status Editing --silent >/dev/null
assert_eq "unrelated --status update preserves also_blocks_dependents" "[docs_updated]" \
    "$(field "$A_TMP/aitasks/t52_abd.md" also_blocks_dependents)"
assert_eq "...and preserves gates alongside it" "[build_verified]" \
    "$(field "$A_TMP/aitasks/t52_abd.md" gates)"
# --also-blocks-dependents replaces.
upd --batch 52 --also-blocks-dependents "docs_updated,manual_verified" --silent >/dev/null
assert_eq "--also-blocks-dependents replaces the set" "[docs_updated, manual_verified]" \
    "$(field "$A_TMP/aitasks/t52_abd.md" also_blocks_dependents)"
# --also-blocks-dependents "" clears (field omitted entirely).
upd --batch 52 --also-blocks-dependents "" --silent >/dev/null
assert_eq "--also-blocks-dependents '' clears the field" "" \
    "$(field "$A_TMP/aitasks/t52_abd.md" also_blocks_dependents)"

echo "--- Part A: create --gates ---"
# Batch create produces a draft; finalize sed-copies it, so gates must be on the draft.
( cd "$A_TMP" && TASK_DIR=aitasks "$CREATE" --batch --name "gate create demo" \
    --priority high --effort low --type feature --desc "body" \
    --gates "tests_pass,review" >/dev/null 2>&1 )
draft="$(find "$A_TMP/aitasks/new" -name 'draft_*gate_create_demo.md' 2>/dev/null | head -1)"
TOTAL=$((TOTAL + 1))
if [[ -n "$draft" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: create --gates produced no draft"
fi
[[ -n "$draft" ]] && assert_eq "create --gates writes gates to draft" "[tests_pass, review]" \
    "$(field "$draft" gates)"

# ============================================================
# Part B — fold unions gates into the primary (git scaffold)
# ============================================================

setup_fold_project() {
    local tmpdir; tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")
    local remote_dir="$tmpdir/remote.git"; git init --bare --quiet "$remote_dir"
    local local_dir="$tmpdir/local"; git clone --quiet "$remote_dir" "$local_dir" 2>/dev/null
    pushd "$local_dir" >/dev/null
    git config user.email "test@test.com"; git config user.name "Test"
    mkdir -p aitasks/metadata
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh
    printf 'bug\nchore\nfeature\n' > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt
    git add -A; git commit -m "setup" --quiet; git push --quiet 2>/dev/null || true
}

write_fold_task() { # write_fold_task PATH [extra_fm_line ...]
    local path="$1"; shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---" "priority: medium" "effort: low" "depends: []" \
            "issue_type: chore" "status: Ready" "labels: []"
        for extra in "$@"; do printf '%s\n' "$extra"; done
        printf '%s\n' "created_at: 2026-01-01 10:00" "updated_at: 2026-01-01 10:00" "---"
        printf '\nBody\n'
    } > "$path"
}

echo "--- Part B: fold gates union ---"
setup_fold_project

write_fold_task aitasks/t10_primary.md "gates: [tests_pass]" "also_blocks_dependents: [docs_updated]"
write_fold_task aitasks/t20_folded.md  "gates: [review, tests_pass]" "also_blocks_dependents: [manual_verified]"
git add -A; git commit -m "fold setup" --quiet

fold_out=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 10 20 2>&1)
assert_contains "fold reports primary updated" "PRIMARY_UPDATED:10" "$fold_out"

union=$(field aitasks/t10_primary.md gates)
stripped=$(echo "$union" | tr -d '[]" ')
assert_eq "fold unions gates (primary first, deduped)" "tests_pass,review" "$stripped"

abd_union=$(field aitasks/t10_primary.md also_blocks_dependents)
abd_stripped=$(echo "$abd_union" | tr -d '[]" ')
assert_eq "fold unions also_blocks_dependents (primary first, deduped)" \
    "docs_updated,manual_verified" "$abd_stripped"

popd >/dev/null 2>&1 || true

# ============================================================
echo "--- syntax checks ---"
TOTAL=$((TOTAL + 1))
if bash -n "$UPD" && bash -n "$CREATE" && bash -n "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: syntax check"
fi

trap 'for d in "${CLEANUP_DIRS[@]}"; do [[ -d "$d" ]] && rm -rf "$d"; done' EXIT

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
