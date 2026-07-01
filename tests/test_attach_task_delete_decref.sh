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
mk_task t31_folded             # revived (unfolded) on delete — rebind target (D/I/J)
mk_task t50_gprimary           # multi-folded case (G): primary
mk_task t51_gfolded1           # multi-folded case (G): revived folded #1
mk_task t52_gfolded2           # multi-folded case (G): revived folded #2
mk_task t60_hprimary           # defensive no-op case (H): primary
mk_task t61_hfolded            # defensive no-op case (H): revived folded
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
printf 'multi folded bytes\n'  > a_multi.bin;   HMU="$(attachment_sha256 a_multi.bin)"
printf 'not-in-primary bytes\n'> a_nd.bin;      HND="$(attachment_sha256 a_nd.bin)"
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
assert_contains "cascade made a single decref commit" "Release/rebind attachments of deleted task(s)" "$(git log -1 --pretty=%s)"
# Idempotent re-run: nothing to change -> clean no-op (no empty-commit failure).
before="$(git rev-parse HEAD)"
"$ATT" decref-deleted 20 20_1 20_2 >/dev/null 2>&1; rerun_rc=$?
assert_eq "re-run exits 0 (idempotent no-op)" "0" "$rerun_rc"
assert_eq "re-run creates no empty commit" "$before" "$(git rev-parse HEAD)"

# ── D. Rebind: --protect-task MOVES a revived task's shared blob to it (t1096) ─
# Simulate post-fold state: HFO was rebound to the primary (30) at fold time, but
# the folded task's (31) frontmatter still lists it (fold does not strip folded
# frontmatter). This is the "primary-owned duplicate hash" case: the primary
# lists HFO (merged) AND the revived folded task lists it too.
"$ATT" add 31 a_fold.bin --name fold.bin >/dev/null 2>&1   # 31 frontmatter lists HFO
"$ATT" add 30 a_fold.bin --name fold.bin >/dev/null 2>&1   # HFO refs now 30,31
"$PY" "$META" --meta-dir attachments/meta decref "$HFO" 31 >/dev/null 2>&1  # rebind 31->30
git add -A; git commit -q -m "simulate fold rebind 31->30"
assert_eq "folded-origin blob ref is the primary only" "30" "$(meta_refs "$HFO")"
out="$("$ATT" decref-deleted --protect-task 31 30 2>&1)"
assert_contains "folded-origin hash is REBOUND to the revived task" "REBOUND:30:${HFO}:31" "$out"
assert_eq "folded-origin ref MOVED to the revived task (not the deleted primary)" "31" "$(meta_refs "$HFO")"
assert_eq "rebound blob NOT orphaned (incref-before-decref)" "" "$(orphaned "$HFO")"
assert_eq "primary's OWN (non-folded) blob still decref'd" "" "$(meta_refs "$HEO")"

# ── I. Retry idempotency: a re-run does NOT re-incref / resurrect (Rule A) ─────
# Immediately after D, HFO refs={31}; re-running the same delete must find 30 is
# no longer a referent -> REBIND_NOOP, no ledger change, no empty commit.
before_i="$(git rev-parse HEAD)"
out_i="$("$ATT" decref-deleted --protect-task 31 30 2>&1)"; i_rc=$?
assert_eq "re-run exits 0" "0" "$i_rc"
assert_contains "already-rebound hash is a REBIND_NOOP on retry" "REBIND_NOOP:30:${HFO}" "$out_i"
assert_eq "retry leaves the rebound ref untouched (no duplicate/resurrected owner)" "31" "$(meta_refs "$HFO")"
assert_eq "retry creates no empty commit" "$before_i" "$(git rev-parse HEAD)"

# ── G. Multiple folded tasks sharing one hash -> ALL survivors become referrers ─
"$ATT" add 51 a_multi.bin --name m.bin >/dev/null 2>&1   # gfolded1 lists HMU
"$ATT" add 52 a_multi.bin --name m.bin >/dev/null 2>&1   # gfolded2 lists HMU
"$ATT" add 50 a_multi.bin --name m.bin >/dev/null 2>&1   # primary lists HMU (refs 50,51,52)
"$PY" "$META" --meta-dir attachments/meta decref "$HMU" 51 >/dev/null 2>&1  # fold rebind 51->50
"$PY" "$META" --meta-dir attachments/meta decref "$HMU" 52 >/dev/null 2>&1  # fold rebind 52->50
git add -A; git commit -q -m "simulate multi-fold rebind 51,52->50"
assert_eq "multi-folded blob ref is the primary only pre-delete" "50" "$(meta_refs "$HMU")"
out_g="$("$ATT" decref-deleted --protect-task 51 --protect-task 52 50 2>&1)"
# Output CSV follows --protect-task arg order (not part of the contract) -> assert
# by MEMBERSHIP, not exact order.
gline="$(printf '%s\n' "$out_g" | grep "^REBOUND:50:${HMU}:")"
assert_contains "multi-folded REBOUND names survivor 51" "51" "$gline"
assert_contains "multi-folded REBOUND names survivor 52" "52" "$gline"
# meta_refs is sorted (cmd_refs sorts) -> exact "51,52" is stable.
assert_eq "ref restored to BOTH surviving referrers" "51,52" "$(meta_refs "$HMU")"
set_grace 0
"$ATT" gc >/dev/null 2>&1
assert_file_exists "multi-referenced blob survives gc" "$(blob_of "$HMU")"

# ── H. Revived hash NOT referenced by the primary -> defensive no-op ───────────
# The revived folded task lists HND, but the doomed primary never did. HND must be
# left entirely untouched (no REBOUND, no DECREFED, no error).
"$ATT" add 61 a_nd.bin --name nd.bin >/dev/null 2>&1   # only the folded task lists HND
git add -A; git commit -q -m "hfolded lists HND (primary does not)"
assert_eq "defensive-case blob ref is the folded task pre-delete" "61" "$(meta_refs "$HND")"
out_h="$("$ATT" decref-deleted --protect-task 61 60 2>&1)"; h_rc=$?
assert_eq "defensive no-op exits 0" "0" "$h_rc"
TOTAL=$((TOTAL+1))
if printf '%s\n' "$out_h" | grep -q ":${HND}"; then FAIL=$((FAIL+1)); echo "FAIL: HND should not appear in decref-deleted output"; else PASS=$((PASS+1)); fi
assert_eq "unrelated revived-task blob ref untouched" "61" "$(meta_refs "$HND")"

# ── B'. Unresolved --protect-task id is FATAL (fail-closed, Rule B) ────────────
out_p="$("$ATT" decref-deleted --protect-task 99999 40 2>&1)"; p_rc=$?
assert_exit_nonzero_rc "unresolved protected (revived) id aborts the delete" "$p_rc"
assert_contains "fatal message names the unresolved protected task" "protected (revived) task t99999" "$out_p"

# ── J. End-to-end board unfold sequence: revived task owns the ref; later ──────
#       deletion of that task lets gc finally reclaim the blob (the deferred leak).
# Replays _do_delete's real subprocess sequence for t30/t31 (D already ran the
# decref-deleted step first, while both files existed -> HFO refs={31}).
# The board runs the unfold as an uncommitted subprocess, so t31 is left modified;
# match the board's `git rm -f` (line: [*_task_git_cmd(), "rm", "-f", path]).
"$PROJECT_DIR/.aitask-scripts/aitask_update.sh" --batch 31 --status Ready --folded-into "" >/dev/null 2>&1
assert_eq "board unfold revives the folded task to Ready" "Ready" "$(grep '^status:' aitasks/t31_folded.md | awk '{print $2}')"
git rm -qf aitasks/t30_primary.md >/dev/null 2>&1; git commit -q -m "board: delete primary t30" >/dev/null 2>&1
assert_eq "revived task OWNS the rebound blob after the primary is gone" "31" "$(meta_refs "$HFO")"
# Now the revived task is itself hard-deleted later: its ref is finally released.
"$ATT" decref-deleted 31 >/dev/null 2>&1
assert_eq "deleting the revived task releases the last ref" "" "$(meta_refs "$HFO")"
TOTAL=$((TOTAL+1))
if [[ -n "$(orphaned "$HFO")" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: revived-task delete stamps orphaned_at"; fi
git rm -qf aitasks/t31_folded.md >/dev/null 2>&1; git commit -q -m "board: delete revived t31" >/dev/null 2>&1
set_grace 0
"$ATT" gc >/dev/null 2>&1
assert_file_not_exists "gc finally reclaims the once-folded blob (deferred leak closed)" "$(blob_of "$HFO")"

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
