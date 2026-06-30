#!/usr/bin/env bash
# test_attach_archive_gc.sh - attachment lifecycle on archive + `ait attach gc`
# (t1030_3). Legacy-mode git fixture (no .aitask-data -> task_git is plain git in
# cwd). Asserts the D4 model: archiving NEVER decrefs (an archived task is still a
# real referrer -> browsable history; its blobs are never GC'd), and gc reclaims
# only FULLY-orphaned blobs past the grace window.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ATT="$PROJECT_DIR/.aitask-scripts/aitask_attach.sh"
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
mk_task t5_demo; mk_task t6_other; mk_task t7_fold; mk_task t8_orphan; mk_task t9_rb
git add -A; git commit -q -m init

meta_refs()  { "$PY" "$META" --meta-dir attachments/meta refs "$1" | paste -sd, -; }
set_grace()  { printf 'attachments_gc_grace: %s\n' "$1" > aitasks/metadata/project_config.yaml; }
blob_of()    { printf 'attachments/blobs/%s' "$(attachment_shard_path "$1")"; }

# Distinct content per case (content-addressed -> distinct hashes).
printf 'archived-retention bytes\n'  > a_keep.bin; HK="$(attachment_sha256 a_keep.bin)"
printf 'shared blob bytes\n'         > a_shared.bin; HS="$(attachment_sha256 a_shared.bin)"
printf 'folded exclusion bytes\n'    > a_fold.bin; HF="$(attachment_sha256 a_fold.bin)"
printf 'orphan reclaim bytes\n'      > a_orph.bin; HR="$(attachment_sha256 a_orph.bin)"
printf 'gc rollback bytes\n'         > a_rb.bin;   HX="$(attachment_sha256 a_rb.bin)"

"$ATT" add 5 a_keep.bin   --name keep.bin   >/dev/null 2>&1
"$ATT" add 5 a_shared.bin --name shared.bin >/dev/null 2>&1
"$ATT" add 6 a_shared.bin --name shared.bin >/dev/null 2>&1
"$ATT" add 7 a_fold.bin   --name fold.bin   >/dev/null 2>&1
"$ATT" add 8 a_orph.bin   --name orph.bin   >/dev/null 2>&1
"$ATT" add 9 a_rb.bin     --name rb.bin     >/dev/null 2>&1

# ── A. Archiving NEVER decrefs (D4): refs + blob survive archival ─────────────
"$ARCHIVE" 5 >/dev/null 2>&1
assert_file_exists "archived task file moved" "aitasks/archived/t5_demo.md"
assert_eq "archive keeps the sole ref (no decref)" "5" "$(meta_refs "$HK")"
assert_file_exists "archived task's blob retained" "$(blob_of "$HK")"
assert_eq "shared blob keeps BOTH refs after one task archived" "5,6" "$(meta_refs "$HS")"

# ── B. gc never sweeps a blob an archived task still references ───────────────
set_grace 0   # even with zero grace, archived references must block GC
"$ATT" gc >/dev/null 2>&1
assert_file_exists "gc retains archived-referenced blob (HK) even past grace" "$(blob_of "$HK")"
assert_file_exists "gc retains shared blob (HS)" "$(blob_of "$HS")"

# ── C. Folded exclusion: a Folded task's frontmatter must NOT pin an orphan ───
# Drop HF's ref directly (frontmatter still lists it on t7) to simulate an
# orphan whose only listing is a pending-deletion Folded task.
"$PY" "$META" --meta-dir attachments/meta decref "$HF" 7 now=1 >/dev/null 2>&1
git add -A; git commit -q -m "decref HF for fold-exclusion case"
# While t7 is still live (Implementing) its frontmatter blocks GC:
"$ATT" gc >/dev/null 2>&1
assert_file_exists "live task's frontmatter blocks GC of HF" "$(blob_of "$HF")"
# Mark t7 Folded -> it is pending-deletion and must be excluded from the scan:
"$PROJECT_DIR/.aitask-scripts/aitask_update.sh" --batch 7 --status Folded --silent >/dev/null 2>&1
"$ATT" gc >/dev/null 2>&1
assert_file_not_exists "Folded task does NOT block GC -> HF swept" "$(blob_of "$HF")"

# ── D. Orphan reclaim honors the grace window ────────────────────────────────
"$ATT" rm 8 orph.bin >/dev/null 2>&1            # decref -> orphaned_at stamped now
assert_eq "rm empties refs" "" "$(meta_refs "$HR")"
set_grace 30d
"$ATT" gc >/dev/null 2>&1
assert_file_exists "fresh orphan within grace is retained" "$(blob_of "$HR")"
set_grace 0
"$ATT" gc >/dev/null 2>&1
assert_file_not_exists "orphan past grace is swept" "$(blob_of "$HR")"
assert_file_not_exists "swept blob's meta file removed too" "attachments/meta/$(attachment_shard_path "$HR").json"

# ── E. gc commit-failure rollback: no deleted-but-uncommitted split-brain ─────
"$ATT" rm 9 rb.bin >/dev/null 2>&1
set_grace 0
printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit
"$ATT" gc >/dev/null 2>&1; gc_rc=$?
rm -f .git/hooks/pre-commit
assert_exit_nonzero_rc "gc dies when its commit fails" "$gc_rc"
assert_file_exists "rollback restores the blob after a failed gc commit" "$(blob_of "$HX")"
assert_file_exists "rollback restores the meta file after a failed gc commit" \
    "attachments/meta/$(attachment_shard_path "$HX").json"

echo ""
echo "test_attach_archive_gc.sh: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
