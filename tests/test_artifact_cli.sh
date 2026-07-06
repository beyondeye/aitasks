#!/usr/bin/env bash
# test_artifact_cli.sh - e2e for the `ait artifact` CLI (t1076_2): the artifact
# pointer/version model on the t1076_1 substrate. Covers create (derived +
# explicit handles, validation), update-in-place (the core AC: task file stays
# byte-identical), the move stub, rm (manifest/blob guards with negative
# controls, ambiguity, stale-reference cleanup, Folded revive-safety), ls/get/
# versions, the decref-deleted artifact guard, aitask_update.sh preservation of
# the artifacts: block, and the gc interplay (manifest block lifts after rm).
# Uses a legacy-mode git repo fixture (no .aitask-data worktree ->
# _ait_detect_data_worktree returns ".", task_git passes through to plain git).
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ART="$PROJECT_DIR/.aitask-scripts/aitask_artifact.sh"
ATT="$PROJECT_DIR/.aitask-scripts/aitask_attach.sh"
UPD="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"
PY="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; resolve_python)"
FMP="$PROJECT_DIR/.aitask-scripts/lib/frontmatter_patch.py"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export XDG_CACHE_HOME="$TMP/xdg"   # keep resolver cache inside the fixture
REPO="$TMP/repo"
mkdir -p "$REPO/aitasks/metadata" "$REPO/aitasks/archived" "$REPO/aitasks/t16"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester
mk_task() {
    printf -- '---\npriority: medium\nstatus: %s\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s body.\n' "${2:-Implementing}" "$1"
}
mk_task t5_demo   > aitasks/t5_demo.md
mk_task t6_other  > aitasks/t6_other.md
mk_task t7_doomed > aitasks/t7_doomed.md
mk_task t8_prot   > aitasks/t8_prot.md
mk_task t9_folded Folded > aitasks/t9_folded.md
mk_task t10_attonly > aitasks/t10_attonly.md
mk_task t16_2_child > aitasks/t16/t16_2_child.md
printf 'attachments_gc_grace: 0\n' > aitasks/metadata/project_config.yaml
git add -A; git commit -q -m init

# Pure libs for in-test hashing / shard paths.
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/yaml_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_utils.sh"

manifest_of() { cat "artifacts/manifests/${1#art:}.json" 2>/dev/null; }

# ── A. create: derived handle, manifest, frontmatter, blob, commit ────────────
printf '<html>plan v1</html>\n' > plan.html
H1="$(artifact_sha256 plan.html)"; SHARD1="$(artifact_shard_path "$H1")"
before="$(git rev-list --count HEAD)"
out="$("$ART" create 5 plan.html --kind html_plan --name "Demo plan" 2>&1)"
after="$(git rev-list --count HEAD)"
assert_eq "exactly one commit per create" "1" "$((after - before))"
assert_contains "create prints the machine-parseable HANDLE line" "HANDLE:art:t5-htmlplan" "$out"
assert_file_exists "manifest created" "artifacts/manifests/t5-htmlplan.json"
assert_contains "manifest current is v1 hash" "\"current\": \"$H1\"" "$(manifest_of art:t5-htmlplan)"
assert_contains "manifest backend is local" '"backend": "local"' "$(manifest_of art:t5-htmlplan)"
assert_file_exists "blob stored under blobs/<2>/<62>" "attachments/blobs/$SHARD1"
assert_file_not_exists "no per-blob meta for an artifact-only blob" "attachments/meta/$SHARD1.json"

recs="$(read_yaml_mappings aitasks/t5_demo.md artifacts)"
expected_rec="$(printf 'handle=art:t5-htmlplan\nkind=html_plan\nname=Demo plan')"
assert_eq "frontmatter entry round-trips (handle/kind/name, schema order)" "$expected_rec" "$recs"
fm_order="$(grep -A2 '^artifacts:' aitasks/t5_demo.md | tail -n +2 | sed 's/^[- ]*//;s/:.*//' | paste -sd, -)"
assert_eq "frontmatter key order is handle,kind,..." "handle,kind" "$fm_order"

# Child-id handle derivation: 16_2 -> art:t16.2-<kindslug>
out="$("$ART" create 16_2 plan.html --kind mockup 2>&1)"
assert_contains "child derived handle uses . for _" "HANDLE:art:t16.2-mockup" "$out"

# ── B. create validation (each dies) ──────────────────────────────────────────
printf 'x\n' > tiny.txt
assert_exit_nonzero "missing --kind dies" "$ART" create 6 tiny.txt
assert_exit_nonzero "uppercase kind dies" "$ART" create 6 tiny.txt --kind Upper
assert_exit_nonzero "digit-leading kind dies" "$ART" create 6 tiny.txt --kind 1x
assert_exit_nonzero "kind with space dies" "$ART" create 6 tiny.txt --kind "a b"
assert_exit_nonzero "non-local backend dies" "$ART" create 6 tiny.txt --kind report --backend s3
assert_exit_nonzero "invalid explicit handle (traversal) dies" "$ART" create 6 tiny.txt --kind report --handle "art:../x"
assert_exit_nonzero "invalid explicit handle (uppercase) dies" "$ART" create 6 tiny.txt --kind report --handle "art:Foo"
dup_err="$( "$ART" create 6 tiny.txt --kind html_plan --handle art:t5-htmlplan 2>&1 )"; rc=$?
assert_exit_nonzero_rc "duplicate handle (existing manifest) dies" "$rc"
assert_contains "duplicate-handle error suggests --handle" -- "--handle" "$dup_err" 2>/dev/null \
    || assert_contains "duplicate-handle error suggests --handle" "handle" "$dup_err"
assert_exit_nonzero "second create with same derived handle on same task dies" \
    "$ART" create 5 tiny.txt --kind html_plan

printf 'artifact_max_size_mb: 1\nattachments_gc_grace: 0\n' > aitasks/metadata/project_config.yaml
dd if=/dev/zero of=big.bin bs=1024 count=2048 2>/dev/null
assert_exit_nonzero "over-cap file dies (artifact_max_size_mb: 1)" "$ART" create 6 big.bin --kind report
printf 'attachments_gc_grace: 0\n' > aitasks/metadata/project_config.yaml

# ── C. update: manifest repoints, task file BYTE-IDENTICAL (core AC) ──────────
cp aitasks/t5_demo.md "$TMP/t5.before"
printf '<html>plan v2</html>\n' > plan2.html
H2="$(artifact_sha256 plan2.html)"
before="$(git rev-list --count HEAD)"
"$ART" update art:t5-htmlplan plan2.html >/dev/null 2>&1
after="$(git rev-list --count HEAD)"
assert_eq "exactly one commit per update" "1" "$((after - before))"
assert_contains "manifest current moved to v2" "\"current\": \"$H2\"" "$(manifest_of art:t5-htmlplan)"
assert_contains "versions kept v1" "$H1" "$(manifest_of art:t5-htmlplan)"
if cmp -s aitasks/t5_demo.md "$TMP/t5.before"; then
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
else
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); echo "FAIL: update left task file byte-identical"
fi
assert_eq "no task-file changes pending after update" "" "$(git status --porcelain -- aitasks/)"

before="$(git rev-list --count HEAD)"
"$ART" update art:t5-htmlplan plan2.html >/dev/null 2>&1
after="$(git rev-list --count HEAD)"
assert_eq "idempotent same-bytes update makes no commit" "0" "$((after - before))"
assert_exit_nonzero "update on missing handle dies" "$ART" update art:nosuch plan2.html

# ── D. move: stub dies, manifest untouched ────────────────────────────────────
cp "artifacts/manifests/t5-htmlplan.json" "$TMP/manifest.before"
assert_exit_nonzero "move is a stub and dies" "$ART" move art:t5-htmlplan --to s3
if cmp -s "artifacts/manifests/t5-htmlplan.json" "$TMP/manifest.before"; then
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
else
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); echo "FAIL: move stub left the manifest untouched"
fi

# ── E. get / versions / ls ────────────────────────────────────────────────────
"$ART" get art:t5-htmlplan --out got.html >/dev/null 2>&1
assert_eq "get returns current (v2) bytes" "$(cat plan2.html)" "$(cat got.html)"
"$ART" get art:t5-htmlplan --version "$H1" --out got1.html >/dev/null 2>&1
assert_eq "get --version returns the old (v1) bytes" "$(cat plan.html)" "$(cat got1.html)"
assert_exit_nonzero "get --version with a non-version hash dies" \
    "$ART" get art:t5-htmlplan --version "sha256:9999999999999999999999999999999999999999999999999999999999999999"
assert_exit_nonzero "get on missing handle dies" "$ART" get art:nosuch
vers="$("$ART" versions art:t5-htmlplan 2>&1)"
assert_contains "versions marks current with *" "* $H2" "$vers"
assert_contains "versions lists the old hash unmarked" "  $H1" "$vers"
ls5="$("$ART" ls 5 2>&1)"
assert_contains "ls <task> joins manifest fields (kind)" "html_plan" "$ls5"
assert_contains "ls <task> shows the backend" "local" "$ls5"
assert_contains "ls <task> shows the name" "Demo plan" "$ls5"
lsg="$("$ART" ls 2>&1)"
assert_contains "global ls lists the handle" "art:t5-htmlplan" "$lsg"

# ── F. rm suite ───────────────────────────────────────────────────────────────
# F1. ambiguous name dies, nothing removed.
printf 'amb one\n' > amb1.txt; printf 'amb two\n' > amb2.txt
"$ART" create 6 amb1.txt --kind report --handle art:t6-amb1 --name "same name" >/dev/null 2>&1
"$ART" create 6 amb2.txt --kind report --handle art:t6-amb2 --name "same name" >/dev/null 2>&1
amb_err="$("$ART" rm 6 "same name" 2>&1)"; rc=$?
assert_exit_nonzero_rc "ambiguous-name rm dies" "$rc"
assert_contains "ambiguity error says to use the handle" "use the handle" "$amb_err"
assert_contains "nothing was removed (entry 1 still listed)" "art:t6-amb1" "$("$ART" ls 6 2>&1)"
assert_contains "nothing was removed (entry 2 still listed)" "art:t6-amb2" "$("$ART" ls 6 2>&1)"
assert_file_exists "no manifest was deleted on ambiguity" "artifacts/manifests/t6-amb1.json"

# F2. rm by handle: last reference -> manifest deleted, artifact-only blob swept.
HA1="$(artifact_sha256 amb1.txt)"; SHARDA1="$(artifact_shard_path "$HA1")"
"$ART" rm 6 art:t6-amb1 >/dev/null 2>&1
assert_file_not_exists "manifest deleted on last-reference rm" "artifacts/manifests/t6-amb1.json"
assert_file_not_exists "artifact-only blob swept" "attachments/blobs/$SHARDA1"
assert_not_contains "frontmatter entry removed" "art:t6-amb1" "$("$ART" ls 6 2>&1)"

# F3. rm by unambiguous name works.
"$ART" rm 6 "same name" >/dev/null 2>&1
assert_file_not_exists "rm by now-unambiguous name deleted its manifest" "artifacts/manifests/t6-amb2.json"

# F4. negative control — blob shared with an ATTACHMENT survives rm.
printf 'shared with attachment\n' > shared_att.bin
HS="$(artifact_sha256 shared_att.bin)"; SHARDS="$(artifact_shard_path "$HS")"
"$ATT" add 6 shared_att.bin --name shared_att.bin >/dev/null 2>&1
"$ART" create 5 shared_att.bin --kind report --handle art:t5-sharedatt >/dev/null 2>&1
"$ART" rm 5 art:t5-sharedatt >/dev/null 2>&1
assert_file_not_exists "manifest deleted" "artifacts/manifests/t5-sharedatt.json"
assert_file_exists "blob shared with an attachment KEPT (meta-file guard)" "attachments/blobs/$SHARDS"

# F5. negative control — hash shared by ANOTHER manifest survives rm.
printf 'shared by two manifests\n' > shared_man.bin
HM="$(artifact_sha256 shared_man.bin)"; SHARDM="$(artifact_shard_path "$HM")"
"$ART" create 5 shared_man.bin --kind report --handle art:t5-sharedman >/dev/null 2>&1
"$ART" create 6 shared_man.bin --kind report --handle art:t6-sharedman >/dev/null 2>&1
"$ART" rm 5 art:t5-sharedman >/dev/null 2>&1
assert_file_not_exists "t5 manifest deleted" "artifacts/manifests/t5-sharedman.json"
assert_file_exists "t6 manifest survives" "artifacts/manifests/t6-sharedman.json"
assert_file_exists "blob referenced by remaining manifest KEPT" "attachments/blobs/$SHARDM"

# F6. manifest KEPT when a second task's artifacts: lists the handle.
printf 'multi ref\n' > multi.txt
"$ART" create 5 multi.txt --kind report --handle art:t5-multi >/dev/null 2>&1
"$PY" "$FMP" append aitasks/t6_other.md artifacts "handle=art:t5-multi" "kind=report"
git add aitasks/t6_other.md; git commit -q -m "seed second reference"
rm_out="$("$ART" rm 5 art:t5-multi 2>&1)"
assert_file_exists "manifest KEPT while another task lists the handle" "artifacts/manifests/t5-multi.json"
assert_contains "rm says who still references it" "t6_other" "$rm_out"
assert_not_contains "t5 entry removed" "art:t5-multi" "$("$ART" ls 5 2>&1)"

# F7. manifest KEPT when a FOLDED task lists the handle (revive-safety).
printf 'folded ref\n' > folded.txt
"$ART" create 5 folded.txt --kind report --handle art:t5-folded >/dev/null 2>&1
"$PY" "$FMP" append aitasks/t9_folded.md artifacts "handle=art:t5-folded" "kind=report"
git add aitasks/t9_folded.md; git commit -q -m "seed folded reference"
"$ART" rm 5 art:t5-folded >/dev/null 2>&1
assert_file_exists "manifest KEPT while a Folded (revivable) task lists the handle" "artifacts/manifests/t5-folded.json"

# F8. stale-entry cleanup: manifest deleted out-of-band -> rm repairs the task.
printf 'stale ref\n' > stale.txt
HS2="$(artifact_sha256 stale.txt)"; SHARDS2="$(artifact_shard_path "$HS2")"
"$ART" create 5 stale.txt --kind report --handle art:t5-stale >/dev/null 2>&1
git rm -q artifacts/manifests/t5-stale.json; git commit -q -m "out-of-band manifest loss"
ls_warn="$("$ART" ls 5 2>&1)"
assert_contains "ls surfaces the stale reference" "stale" "$ls_warn"
stale_out="$("$ART" rm 5 art:t5-stale 2>&1)"; rc=$?
assert_exit_zero_rc "stale-entry rm exits 0" "$rc"
assert_contains "stale-entry rm warns about the missing manifest" "missing" "$stale_out"
assert_not_contains "stale frontmatter entry removed" "art:t5-stale" "$("$ART" ls 5 2>&1)"
assert_file_exists "stale-entry rm touches no blob" "attachments/blobs/$SHARDS2"
assert_eq "stale-entry rm committed the task-file cleanup" "" "$(git status --porcelain -- aitasks/)"

# F9. rm of unknown ref dies.
assert_exit_nonzero "rm of unknown ref dies" "$ART" rm 5 art:nosuch

# F10. fail-closed scan failure mid-rm ROLLS BACK (malformed sibling manifest).
# referenced-hashes dies on any malformed manifest in the tree (t1076_1 policy);
# the rm txn must restore the already-patched task file and already-deleted
# manifest so the same rm works once the named manifest is repaired.
printf 'rollback probe\n' > rbp.txt
"$ART" create 5 rbp.txt --kind report --handle art:t5-rbp >/dev/null 2>&1
printf 'not json' > artifacts/manifests/zz-malformed.json
rb_err="$("$ART" rm 5 art:t5-rbp 2>&1)"; rc=$?
assert_exit_nonzero_rc "rm dies when the reference scan hits a malformed manifest" "$rc"
assert_contains "scan-failure rm says it rolled back" "rolled back" "$rb_err"
assert_contains "frontmatter entry restored by rollback" "art:t5-rbp" "$("$ART" ls 5 2>&1)"
assert_file_exists "manifest restored by rollback" "artifacts/manifests/t5-rbp.json"
assert_eq "no uncommitted task changes after rollback" "" "$(git status --porcelain -- aitasks/)"
rm -f artifacts/manifests/zz-malformed.json
"$ART" rm 5 art:t5-rbp >/dev/null 2>&1
assert_file_not_exists "same rm succeeds after repairing the malformed manifest" "artifacts/manifests/t5-rbp.json"
assert_not_contains "entry removed on the successful re-run" "art:t5-rbp" "$("$ART" ls 5 2>&1)"

# ── G. decref-deleted artifact guard (board hard-delete choke point) ──────────
printf 'doomed artifact\n' > doomed.txt
"$ART" create 7 doomed.txt --kind report --handle art:t7-doomed >/dev/null 2>&1
g_err="$("$ATT" decref-deleted 7 2>&1)"; rc=$?
assert_exit_nonzero_rc "doomed task with an artifact makes decref-deleted die" "$rc"
assert_contains "guard error names the task and handle" "t7 still has artifact art:t7-doomed" "$g_err"
assert_file_exists "guard aborted before any mutation (manifest intact)" "artifacts/manifests/t7-doomed.json"

# Protected survivor listing the handle -> allowed through.
"$PY" "$FMP" append aitasks/t8_prot.md artifacts "handle=art:t7-doomed" "kind=report"
git add aitasks/t8_prot.md; git commit -q -m "seed protected reference"
assert_exit_zero "guard allows delete when a protected survivor lists the handle" \
    "$ATT" decref-deleted --protect-task 8 7

# Attachment-only doomed task -> unchanged behavior (regression).
printf 'doomed attachment\n' > datt.bin
"$ATT" add 10 datt.bin --name datt.bin >/dev/null 2>&1
assert_exit_zero "attachment-only doomed task still decrefs fine" "$ATT" decref-deleted 10

# ── H. aitask_update.sh preserves the artifacts: block ────────────────────────
# Extract the artifacts: block exactly as aitask_update.sh's
# extract_frontmatter_block does (header + indented body, frontmatter only).
artifacts_block() {
    awk 'NR==1 && $0=="---" { infm=1; next }
         infm==1 && $0=="---" { exit }
         infm==1 {
             if ($0 ~ /^[^[:space:]]/) { capturing = ($0 ~ /^artifacts:/) ? 1 : 0 }
             if (capturing) print
         }' "$1"
}
art_block_before="$(artifacts_block aitasks/t5_demo.md)"
"$UPD" --batch 5 --priority high --silent >/dev/null 2>&1
art_block_after="$(artifacts_block aitasks/t5_demo.md)"
assert_eq "artifacts: block byte-identical across aitask_update.sh rewrite" \
    "$art_block_before" "$art_block_after"
assert_eq "priority actually updated" "priority: high" "$(grep '^priority:' aitasks/t5_demo.md)"
git add -A; git commit -q -m "post-update snapshot"

# ── I. gc interplay: manifest blocks gc; rm lifts the block ───────────────────
printf 'gc interplay bytes\n' > gcx.bin
HG="$(artifact_sha256 gcx.bin)"; SHARDG="$(artifact_shard_path "$HG")"
"$ATT" add 6 gcx.bin --name gcx.bin >/dev/null 2>&1
"$ART" create 5 gcx.bin --kind report --handle art:t5-gcx >/dev/null 2>&1
"$ATT" rm 6 gcx.bin >/dev/null 2>&1        # orphan the attachment ref (grace 0)
"$ATT" gc >/dev/null 2>&1
assert_file_exists "manifest-referenced orphan blob survives gc" "attachments/blobs/$SHARDG"
"$ART" rm 5 art:t5-gcx >/dev/null 2>&1
# rm keeps the blob itself (attachment meta file exists) — gc now reclaims it.
assert_file_exists "rm kept the attachment-ledger blob (meta-file guard)" "attachments/blobs/$SHARDG"
"$ATT" gc >/dev/null 2>&1
assert_file_not_exists "gc sweeps once the manifest block is lifted" "attachments/blobs/$SHARDG"

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
