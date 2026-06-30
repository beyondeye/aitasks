#!/usr/bin/env bash
# test_attach_fold_rebind.sh - fold re-bind + frontmatter merge (t1030_3).
# Legacy-mode git fixture (no .aitask-data -> task_git is plain git in cwd).
# Folding A into B must transfer A's attachments to B fully: rebind the refcount
# AND merge the frontmatter entry (so it stays accessible on B and survives A's
# deletion at archival), with deterministic collision handling.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ATT="$PROJECT_DIR/.aitask-scripts/aitask_attach.sh"
FOLD="$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh"
ARCHIVE="$PROJECT_DIR/.aitask-scripts/aitask_archive.sh"
META="$PROJECT_DIR/.aitask-scripts/lib/attachment_meta.py"
PY="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; resolve_python)"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/repo"; mkdir -p "$REPO/aitasks/metadata"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/attachment_utils.sh"

mk_task() {
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s body.\n' "$1" > "aitasks/$1.md"
}
mk_parent_with_child() {   # <parent_stem> <child_csv>
    printf -- '---\npriority: medium\nstatus: Ready\nchildren_to_implement: [%s]\nupdated_at: 2026-01-01 00:00\n---\n\nParent.\n' "$2" > "aitasks/$1.md"
}
mk_child() {               # <parent_num> <child_stem>
    mkdir -p "aitasks/t$1"
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nChild.\n' > "aitasks/t$1/$2.md"
}

meta_refs() { "$PY" "$META" --meta-dir attachments/meta refs "$1" | paste -sd, -; }
blob_of()   { printf 'attachments/blobs/%s' "$(attachment_shard_path "$1")"; }
status_of() { sed -n 's/^status: //p' "$1" | head -1; }

# Scenario tasks.
mk_task t20_primary;  mk_task t21_folded                 # A: basic transfer
mk_task t22_primary;  mk_task t23_folded                 # B: dup hash
mk_task t24_primary;  mk_task t25_folded                 # C: name collision + lengthen
mk_task t26_top; mk_task t27_mid; mk_task t28_deep       # D: transitive
mk_task t30_primary; mk_task t31_folded; mk_task t33_trans  # E: rollback
mk_parent_with_child t32_parent "t32_2"; mk_child 32 t32_2_child
git add -A; git commit -q -m init

# Distinct content -> distinct hashes.
printf 'basic transfer\n'  > c_basic.bin; HB="$(attachment_sha256 c_basic.bin)"
printf 'dup shared\n'      > c_dup.bin;   HD="$(attachment_sha256 c_dup.bin)"
printf 'collide Y\n'       > c_y.bin;     HY="$(attachment_sha256 c_y.bin)"
printf 'collide D1\n'      > c_d1.bin
printf 'collide D2\n'      > c_d2.bin
printf 'transitive\n'      > c_trans.bin; HT="$(attachment_sha256 c_trans.bin)"
printf 'rollback blob\n'   > c_rb.bin;    HR="$(attachment_sha256 c_rb.bin)"

# ── A. Basic: fold t21 -> t20 transfers the attachment + survives archival ───
"$ATT" add 21 c_basic.bin --name basic.bin >/dev/null 2>&1
"$FOLD" --commit-mode fresh 20 21 >/dev/null 2>&1
assert_eq "fold rebinds the ref to the primary" "20" "$(meta_refs "$HB")"
assert_contains "primary frontmatter gains the folded attachment" "basic.bin" "$("$ATT" ls 20 2>&1)"
"$ARCHIVE" 20 >/dev/null 2>&1                 # deletes folded t21, no decref (D4)
assert_file_not_exists "folded task file deleted at archival" "aitasks/t21_folded.md"
assert_eq "blob still referenced by the archived primary" "20" "$(meta_refs "$HB")"
assert_file_exists "blob survives the folded task's deletion + archival" "$(blob_of "$HB")"

# ── B. Duplicate hash already on the primary -> skipped, single ref ───────────
"$ATT" add 22 c_dup.bin --name dup.bin >/dev/null 2>&1
"$ATT" add 23 c_dup.bin --name dup.bin >/dev/null 2>&1
assert_eq "pre-fold the shared blob has both refs" "22,23" "$(meta_refs "$HD")"
"$FOLD" --commit-mode fresh 22 23 >/dev/null 2>&1
assert_eq "dup-hash fold leaves a single ref on the primary" "22" "$(meta_refs "$HD")"
assert_eq "dup-hash fold adds no second frontmatter entry" "1" \
    "$("$ATT" ls 22 2>&1 | grep -c 'dup.bin')"

# ── C. Same name / different hash -> renamed, suffix lengthens until unique ───
HY_HEX="${HY#sha256:}"
"$ATT" add 24 c_d1.bin --name doc.bin >/dev/null 2>&1
# Pre-occupy the 8-hex candidate name so the rename MUST lengthen to 16 hex.
"$ATT" add 24 c_d2.bin --name "doc~${HY_HEX:0:8}.bin" >/dev/null 2>&1
"$ATT" add 25 c_y.bin  --name doc.bin >/dev/null 2>&1   # collides with t24's doc.bin
"$FOLD" --commit-mode fresh 24 25 >/dev/null 2>&1
assert_eq "collision fold rebinds Y to the primary" "24" "$(meta_refs "$HY")"
ls24="$("$ATT" ls 24 2>&1)"
assert_contains "rename lengthens the hex suffix to 16 when 8 already taken" \
    "doc~${HY_HEX:0:16}.bin" "$ls24"
assert_contains "the original doc.bin is still present" "doc.bin" "$ls24"

# ── D. Transitive: t28 -> t27 -> t26 rebinds the deep blob to the top ─────────
"$ATT" add 28 c_trans.bin --name trans.bin >/dev/null 2>&1
"$FOLD" --commit-mode fresh 27 28 >/dev/null 2>&1     # t27.folded_tasks=[28]
assert_eq "first fold rebinds to the mid task" "27" "$(meta_refs "$HT")"
"$FOLD" --commit-mode fresh 26 27 >/dev/null 2>&1     # 28 is transitive of 27
assert_eq "transitive fold rebinds the deep blob to the top primary" "26" "$(meta_refs "$HT")"
assert_contains "top primary lists the transitive attachment" "trans.bin" "$("$ATT" ls 26 2>&1)"

# ── E. Fold-commit-failure rollback restores the WHOLE transaction ───────────
"$ATT" add 31 c_rb.bin --name rb.bin >/dev/null 2>&1
# Give t31 a transitive folded task so the rollback set must cover it too.
"$PROJECT_DIR/.aitask-scripts/aitask_update.sh" --batch 31 --folded-tasks "t33_trans" --silent >/dev/null 2>&1 || true
# Use the real id form for the transitive task: set t31.folded_tasks=[33].
"$PROJECT_DIR/.aitask-scripts/aitask_update.sh" --batch 31 --folded-tasks "33" --silent >/dev/null 2>&1 || true
git add -A; git commit -q -m "pre-rollback state"
printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit
"$FOLD" --commit-mode fresh 30 31 32_2 >/dev/null 2>&1; fold_rc=$?
rm -f .git/hooks/pre-commit
assert_exit_nonzero_rc "fold dies when its commit fails" "$fold_rc"
assert_eq "rollback: folded task status reverted (NOT Folded)" \
    "Implementing" "$(status_of aitasks/t31_folded.md)"
assert_eq "rollback: rebound ref reverted to the folded task" "31" "$(meta_refs "$HR")"
assert_not_contains "rollback: primary frontmatter has no merged entry" \
    "rb.bin" "$("$ATT" ls 30 2>&1)"
assert_contains "rollback: child's parent still lists the child" \
    "t32_2" "$(cat aitasks/t32_parent.md)"
assert_eq "rollback: transitive task folded_into NOT repointed to primary" \
    "" "$(sed -n 's/^folded_into: //p' aitasks/t33_trans.md | head -1)"

echo ""
echo "test_attach_fold_rebind.sh: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
