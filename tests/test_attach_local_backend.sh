#!/usr/bin/env bash
# test_attach_local_backend.sh - e2e for the local attachment backend, cache, and
# the single-transaction add/get/rm verbs (t1030_2). Uses a legacy-mode git repo
# fixture (no .aitask-data worktree -> _ait_detect_data_worktree returns ".",
# task_git passes through to plain git in the fixture cwd).
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ATT="$PROJECT_DIR/.aitask-scripts/aitask_attach.sh"
PY="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; resolve_python)"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/repo"
mkdir -p "$REPO/aitasks/metadata"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester
mk_task() {
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s body.\n' "$1" > "aitasks/$1.md"
}
mk_task t5_demo; mk_task t6_other
git add -A; git commit -q -m init

# Source the pure libs for in-test hashing / shard / backend round-trip.
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/attachment_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/attachment_backend.sh"

meta_refs() { "$PY" "$PROJECT_DIR/.aitask-scripts/lib/attachment_meta.py" --meta-dir attachments/meta refs "$1" | paste -sd, -; }

# ── A. Backend round-trip (put -> head -> get -> verify, list, delete) ────────
printf 'blob round trip bytes\n' > b1.bin
HB="$(attachment_sha256 b1.bin)"
attachment_backend_put "$HB" b1.bin
assert_exit_zero "backend head finds the stored blob" attachment_backend_head "$HB"
attachment_backend_get "$HB" b1.out
assert_eq "backend get returns identical bytes" "$(cat b1.bin)" "$(cat b1.out)"
assert_eq "round-tripped blob hashes back to the same hash" "$HB" "$(attachment_sha256 b1.out)"
assert_contains "backend list includes the blob" "$HB" "$(attachment_backend_list)"
attachment_backend_delete "$HB"
assert_exit_nonzero "backend head misses after delete" attachment_backend_head "$HB"

# ── B. add: one commit, get identical bytes, ls ──────────────────────────────
printf 'hello e2e attachment\n' > e1.png
HE1="$(attachment_sha256 e1.png)"; SHARD_E1="$(attachment_shard_path "$HE1")"
before="$(git rev-list --count HEAD)"
"$ATT" add 5 e1.png --name e1.png >/dev/null 2>&1
after="$(git rev-list --count HEAD)"
assert_eq "exactly one commit per add" "1" "$((after - before))"
assert_file_exists "blob stored under blobs/<2>/<62>" "attachments/blobs/$SHARD_E1"
assert_file_exists "per-blob meta written (no global index)" "attachments/meta/$SHARD_E1.json"
assert_file_not_exists "no global index.json exists" "attachments/index.json"
"$ATT" get 5 e1.png --out e1.out >/dev/null 2>&1
assert_eq "get returns identical bytes" "$(cat e1.png)" "$(cat e1.out)"
assert_contains "ls shows the attachment" "e1.png" "$("$ATT" ls 5 2>&1)"

# ── C. Duplicate rejection (hash AND name, per task) ─────────────────────────
assert_exit_nonzero "duplicate-hash add rejected" "$ATT" add 5 e1.png --name e1_again.png
printf 'totally different bytes\n' > e2.png
assert_exit_nonzero "duplicate-name add rejected" "$ATT" add 5 e2.png --name e1.png

# ── D. Same blob on a SECOND task -> 2 refs (refcount case) ───────────────────
"$ATT" add 6 e1.png --name e1.png >/dev/null 2>&1
assert_eq "same blob on two tasks -> refs [5,6]" "5,6" "$(meta_refs "$HE1")"

# ── E. rm: decref, blob kept (gc is t1030_3), frontmatter entry gone ─────────
"$ATT" rm 5 e1.png >/dev/null 2>&1
assert_file_exists "blob NOT deleted on rm (gc deferred to t1030_3)" "attachments/blobs/$SHARD_E1"
assert_eq "rm decrefs the task -> refs [6]" "6" "$(meta_refs "$HE1")"
assert_not_contains "rm removed the frontmatter entry from t5" "e1.png" "$("$ATT" ls 5 2>&1)"
assert_contains "t6 still references the blob" "e1.png" "$("$ATT" ls 6 2>&1)"

# ── F. rm rollback must NOT drop another task's valid ref ─────────────────────
# (the exact property the single-transaction lock guarantees)
"$ATT" add 5 e1.png --name e1.png >/dev/null 2>&1     # refs back to [5,6]
printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit
"$ATT" rm 5 e1.png >/dev/null 2>&1 || true            # commit fails -> rollback
rm -f .git/hooks/pre-commit
assert_eq "rm-rollback preserves BOTH refs (no clobber)" "5,6" "$(meta_refs "$HE1")"
assert_contains "rm-rollback restores t5 frontmatter entry" "e1.png" "$("$ATT" ls 5 2>&1)"

# ── G. Staged-path scoping: unrelated staged file not swept into attach ──────
echo unrelated > unrelated.txt; git add unrelated.txt
printf 'scope bytes\n' > e3.png
"$ATT" add 5 e3.png --name e3.png >/dev/null 2>&1
assert_not_contains "unrelated staged file NOT in the attach commit" \
    "unrelated.txt" "$(git show --name-only --format= HEAD)"
git reset -q HEAD unrelated.txt; rm -f unrelated.txt

# ── H. Size cap: project_config override rejects; default lets a small file ──
printf 'attachment_max_size_mb: 1\n' > aitasks/metadata/project_config.yaml
head -c 2097152 /dev/zero > big.bin
assert_exit_nonzero "oversize add rejected per project_config cap" "$ATT" add 5 big.bin --name big.bin
rm -f aitasks/metadata/project_config.yaml
printf 'tiny ok\n' > tiny.bin
assert_exit_zero "small add passes under the default 25 MB cap" "$ATT" add 5 tiny.bin --name tiny.bin

# ── I. Locking: no leak after success; a held lock makes a second op die busy ─
assert_dir_not_exists "no attach lock dir lingers after a successful op" "attachments/.attach.lock"
sleep 30 & LIVE=$!
mkdir -p attachments/.attach.lock; echo "$LIVE" > attachments/.attach.lock/pid; echo tok > attachments/.attach.lock/owner
printf 'busy\n' > busy.png
ATTACH_LOCK_TIMEOUT=1 "$ATT" add 5 busy.png --name busy.png >/dev/null 2>&1; rc=$?
assert_exit_nonzero_rc "second op dies busy while the global lock is held" "$rc"
kill "$LIVE" 2>/dev/null || true; rm -rf attachments/.attach.lock
# (Standalone metadata mutation under the same global lock is a t1030_3 surface
#  — no standalone mutating `ait attach` verb exists yet, so it is covered there.)

# ── J. add rollback: a forced commit failure leaves no orphan meta/blob ──────
printf 'rollback unique bytes 7788\n' > rb.png
HRB="$(attachment_sha256 rb.png)"; SHARD_RB="$(attachment_shard_path "$HRB")"
printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit
"$ATT" add 5 rb.png --name rb.png >/dev/null 2>&1 || true
rm -f .git/hooks/pre-commit
assert_file_not_exists "rollback: no orphan meta after failed commit" "attachments/meta/$SHARD_RB.json"
assert_file_not_exists "rollback: no orphan blob after failed commit" "attachments/blobs/$SHARD_RB"
assert_not_contains "rollback: t5 frontmatter unchanged" "rb.png" "$(cat aitasks/t5_demo.md)"

echo ""
echo "test_attach_local_backend.sh: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
