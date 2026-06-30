#!/usr/bin/env bash
# test_attach_task_delete_decref.sh - `ait attach decref-deleted` (t1093): the
# hard-delete decref path the board shells out to. Legacy-mode git fixture (no
# .aitask-data -> task_git is plain git in cwd). Asserts that hard-deleting a
# task releases its attachment refs (so gc can finally reclaim a fully-orphaned
# blob), that shared blobs survive while another task still references them, that
# a parent delete cascades to children, that folded-origin blobs are GUARDED
# (skipped) via --protect-task so a revived task is never orphaned, and that a
# failed commit rolls back cleanly.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ATT="$PROJECT_DIR/.aitask-scripts/aitask_attach.sh"
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

mk_task() {  # mk_task <relpath-stem> e.g. t10_demo or t20/t20_1_child
    local f="aitasks/$1.md"; mkdir -p "$(dirname "$f")"
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s body.\n' "$1" > "$f"
}
meta_refs()  { "$PY" "$META" --meta-dir attachments/meta refs "$1" | paste -sd, -; }
orphaned()   { "$PY" "$META" --meta-dir attachments/meta orphaned-at "$1"; }
set_grace()  { printf 'attachments_gc_grace: %s\n' "$1" > aitasks/metadata/project_config.yaml; }
blob_of()    { printf 'attachments/blobs/%s' "$(attachment_shard_path "$1")"; }
meta_file()  { printf 'attachments/meta/%s.json' "$(attachment_shard_path "$1")"; }

mk_task t10_single
mk_task t11_sharedA
mk_task t12_sharedB
mk_task t20_parent
mk_task t20/t20_1_childA
mk_task t20/t20_2_childB
mk_task t20/t20_3_sibling      # NOT deleted — its blob must survive
mk_task t30_primary
mk_task t31_folded             # revived (unfolded) on delete — protected
mk_task t40_rollback
git add -A; git commit -q -m init

# Distinct content -> distinct content-addressed hashes.
printf 'single bytes\n'        > a_single.bin;  HSI="$(attachment_sha256 a_single.bin)"
printf 'shared 11/12 bytes\n'  > a_shared.bin;  HSH="$(attachment_sha256 a_shared.bin)"
printf 'parent own bytes\n'    > a_pown.bin;    HPO="$(attachment_sha256 a_pown.bin)"
printf 'child A bytes\n'       > a_ca.bin;      HCA="$(attachment_sha256 a_ca.bin)"
printf 'parent+childB bytes\n' > a_pc.bin;      HPC="$(attachment_sha256 a_pc.bin)"
printf 'sibling bytes\n'       > a_sib.bin;     HSB="$(attachment_sha256 a_sib.bin)"
printf 'primary own bytes\n'   > a_eown.bin;    HEO="$(attachment_sha256 a_eown.bin)"
printf 'folded origin bytes\n' > a_fold.bin;    HFO="$(attachment_sha256 a_fold.bin)"
printf 'rollback bytes\n'      > a_rb.bin;      HRB="$(attachment_sha256 a_rb.bin)"

"$ATT" add 10 a_single.bin --name single.bin >/dev/null 2>&1
"$ATT" add 11 a_shared.bin --name shared.bin >/dev/null 2>&1
"$ATT" add 12 a_shared.bin --name shared.bin >/dev/null 2>&1
"$ATT" add 20 a_pown.bin   --name pown.bin   >/dev/null 2>&1
"$ATT" add 20_1 a_ca.bin   --name ca.bin     >/dev/null 2>&1
"$ATT" add 20 a_pc.bin     --name pc.bin     >/dev/null 2>&1
"$ATT" add 20_2 a_pc.bin   --name pc.bin     >/dev/null 2>&1   # parent + childB share HPC
"$ATT" add 20_3 a_sib.bin  --name sib.bin    >/dev/null 2>&1
"$ATT" add 30 a_eown.bin   --name eown.bin   >/dev/null 2>&1
"$ATT" add 40 a_rb.bin     --name rb.bin     >/dev/null 2>&1

# ── A. Single attachment: delete decrefs -> orphaned -> gc reclaims ───────────
assert_eq "single blob ref present pre-delete" "10" "$(meta_refs "$HSI")"
"$ATT" decref-deleted 10 >/dev/null 2>&1
assert_eq "delete removes the sole ref" "" "$(meta_refs "$HSI")"
TOTAL=$((TOTAL+1))
if [[ -n "$(orphaned "$HSI")" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: delete stamps orphaned_at"; fi
# Simulate the board removing the task file after decref (so the gc cross-check
# no longer sees t10's frontmatter blocking the now-orphaned blob).
git rm -q aitasks/t10_single.md >/dev/null 2>&1; git commit -q -m "delete t10" >/dev/null 2>&1
set_grace 0
"$ATT" gc >/dev/null 2>&1
assert_file_not_exists "gc reclaims the orphaned blob past grace" "$(blob_of "$HSI")"
assert_file_not_exists "gc removes the meta file too" "$(meta_file "$HSI")"

# ── B. Shared blob: deleting ONE task retains the blob for the other ──────────
assert_eq "shared blob has both refs" "11,12" "$(meta_refs "$HSH")"
"$ATT" decref-deleted 11 >/dev/null 2>&1
assert_eq "deleting one sharer leaves the other ref" "12" "$(meta_refs "$HSH")"
set_grace 0
"$ATT" gc >/dev/null 2>&1
assert_file_exists "still-referenced shared blob survives gc" "$(blob_of "$HSH")"

# ── C. Cascade: parent + children in one call; non-doomed sibling untouched ───
assert_eq "parent+childB shared blob has both refs" "20,20_2" "$(meta_refs "$HPC")"
"$ATT" decref-deleted 20 20_1 20_2 >/dev/null 2>&1
assert_eq "parent own blob ref removed"  "" "$(meta_refs "$HPO")"
assert_eq "childA blob ref removed"      "" "$(meta_refs "$HCA")"
assert_eq "parent+childB shared blob fully released" "" "$(meta_refs "$HPC")"
assert_eq "non-doomed sibling blob untouched" "20_3" "$(meta_refs "$HSB")"
assert_contains "cascade made a single decref commit" "Decref attachments of deleted task(s)" "$(git log -1 --pretty=%s)"
# Idempotent re-run: nothing to change -> clean no-op (no empty-commit failure).
before="$(git rev-parse HEAD)"
"$ATT" decref-deleted 20 20_1 20_2 >/dev/null 2>&1; rerun_rc=$?
assert_eq "re-run exits 0 (idempotent no-op)" "0" "$rerun_rc"
assert_eq "re-run creates no empty commit" "$before" "$(git rev-parse HEAD)"

# ── D. Folded guard: --protect-task skips a revived task's shared blob ─────────
# Simulate post-fold state: HFO was rebound to the primary (30), but the folded
# task's (31) frontmatter still lists it (fold does not strip folded frontmatter).
"$ATT" add 31 a_fold.bin --name fold.bin >/dev/null 2>&1   # 31 frontmatter lists HFO
"$ATT" add 30 a_fold.bin --name fold.bin >/dev/null 2>&1   # HFO refs now 30,31
"$PY" "$META" --meta-dir attachments/meta decref "$HFO" 31 >/dev/null 2>&1  # rebind 31->30
git add -A; git commit -q -m "simulate fold rebind 31->30"
assert_eq "folded-origin blob ref is the primary only" "30" "$(meta_refs "$HFO")"
out="$("$ATT" decref-deleted --protect-task 31 30 2>&1)"
assert_contains "folded-origin hash is SKIPPED" "SKIPPED:30:${HFO}:folded" "$out"
assert_eq "folded-origin blob ref retained (NOT orphaned)" "30" "$(meta_refs "$HFO")"
assert_eq "primary's OWN blob still decref'd" "" "$(meta_refs "$HEO")"

# ── E. Commit-failure rollback: a failed commit restores the ledger cleanly ────
assert_eq "rollback blob ref present pre-delete" "40" "$(meta_refs "$HRB")"
printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit
"$ATT" decref-deleted 40 >/dev/null 2>&1; rb_rc=$?
rm -f .git/hooks/pre-commit
assert_exit_nonzero_rc "decref-deleted dies when its commit fails" "$rb_rc"
assert_eq "rollback restores the ref after a failed commit" "40" "$(meta_refs "$HRB")"
assert_eq "no staged ledger edits remain after rollback" "" "$(git diff --cached --name-only)"

echo ""
echo "test_attach_task_delete_decref.sh: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
