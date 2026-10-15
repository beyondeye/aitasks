#!/usr/bin/env bash
# test_attach_local_backend.sh - e2e for the local attachment backend, cache, and
# the single-transaction add/get/rm verbs (t1030_2), and L: add refuses an
# archived owner, loose or bundled, while ls/get keep accepting one and rm a
# loose one (t2011). Uses a legacy-mode git repo
# fixture (no .aitask-data worktree -> _ait_detect_data_worktree returns ".",
# task_git passes through to plain git in the fixture cwd).
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
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
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_backend.sh"
# task_utils.sh (via archive_utils.sh) REPLACES the EXIT trap set above with
# its own extraction cleanup, so re-arm ours. And route every bundle
# extraction into the fixture: resolve_task_file inside `$( )` -- in the CLIs
# and in section L's preconditions -- never cleans up its temp dir.
trap 'rm -rf "$TMP"' EXIT
export TMPDIR="$TMP/tmpdir"; mkdir -p "$TMPDIR"
# outside_repo <path> -- "outside" iff <path> is absolute and not under the
# fixture repo. A substring test for "aitasks/" would misfire whenever the
# host's TMPDIR itself contains that segment.
outside_repo() { [[ "$1" == /* && "$1" != "$REPO"/* ]] && echo outside || echo "inside: $1"; }

meta_refs() { "$PY" "$PROJECT_DIR/.aitask-scripts/lib/attachment_meta.py" --meta-dir attachments/meta refs "$1" | paste -sd, -; }

# ── A. Backend round-trip (put -> head -> get -> verify, list, delete) ────────
printf 'blob round trip bytes\n' > b1.bin
HB="$(artifact_sha256 b1.bin)"
artifact_backend_put "$HB" b1.bin
assert_exit_zero "backend head finds the stored blob" artifact_backend_head "$HB"
artifact_backend_get "$HB" b1.out
assert_eq "backend get returns identical bytes" "$(cat b1.bin)" "$(cat b1.out)"
assert_eq "round-tripped blob hashes back to the same hash" "$HB" "$(artifact_sha256 b1.out)"
assert_contains "backend list includes the blob" "$HB" "$(artifact_backend_list)"
artifact_backend_delete "$HB"
assert_exit_nonzero "backend head misses after delete" artifact_backend_head "$HB"

# ── B. add: one commit, get identical bytes, ls ──────────────────────────────
printf 'hello e2e attachment\n' > e1.png
HE1="$(artifact_sha256 e1.png)"; SHARD_E1="$(artifact_shard_path "$HE1")"
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
HRB="$(artifact_sha256 rb.png)"; SHARD_RB="$(artifact_shard_path "$HRB")"
printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit
"$ATT" add 5 rb.png --name rb.png >/dev/null 2>&1 || true
rm -f .git/hooks/pre-commit
assert_file_not_exists "rollback: no orphan meta after failed commit" "attachments/meta/$SHARD_RB.json"
assert_file_not_exists "rollback: no orphan blob after failed commit" "attachments/blobs/$SHARD_RB"
assert_not_contains "rollback: t5 frontmatter unchanged" "rb.png" "$(cat aitasks/t5_demo.md)"

# ── K. In-resolver content verification (t1076_1) ────────────────────────────
# artifact_resolve is shared substrate: it verifies resolved bytes itself, so
# consumers do not depend on caller-side re-hashing. Corrupted CACHE copies
# self-heal (single re-fetch); corrupted CANONICAL blobs die loudly.
export XDG_CACHE_HOME="$TMP/xdg"   # keep resolver cache inside the fixture
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_cache.sh"

printf 'verified resolve bytes\n' > v1.bin
HV="$(artifact_sha256 v1.bin)"
artifact_backend_put "$HV" v1.bin

# Clean resolve: verified, correct bytes (symlink for the local backend).
vp="$(artifact_resolve "$HV")"
assert_eq "resolve returns verified bytes" "$(cat v1.bin)" "$(cat "$vp")"

# Corrupted REGULAR-FILE cache entry (the remote-fill shape) self-heals.
rm -f "$vp"; mkdir -p "$(dirname "$vp")"
printf 'WRONG CACHED BYTES\n' > "$vp"
vp2="$(artifact_resolve "$HV" 2>/dev/null)"
assert_eq "corrupted cache copy self-heals to correct bytes" "$(cat v1.bin)" "$(cat "$vp2")"

# Corrupted CANONICAL blob, reached via the existing cache symlink: die, named.
printf 'CANON CORRUPT\n' > "$(artifact_local_blob_path "$HV")"
k_out="$( artifact_resolve "$HV" 2>&1 )"; k_rc=$?
assert_exit_nonzero_rc "corrupt canonical via cache symlink dies" "$k_rc"
assert_contains "symlink-path error names the canonical blob" "canonical blob" "$k_out"

# Same corruption with a cold cache (local-branch verify before linking): die.
rm -f "$vp2"
k_out="$( artifact_resolve "$HV" 2>&1 )"; k_rc=$?
assert_exit_nonzero_rc "corrupt canonical on cold cache dies (never silent wrong bytes)" "$k_rc"
assert_contains "cold-cache error names the canonical blob" "canonical blob" "$k_out"
artifact_local_delete "$HV"; artifact_backend_put "$HV" v1.bin   # restore canon

# Unknown backend name fails clearly via the dispatcher.
k_out="$( ARTIFACT_BACKEND=nosuch artifact_resolve "$HV" 2>&1 )"; k_rc=$?
assert_exit_nonzero_rc "unknown backend dies" "$k_rc"
assert_contains "unknown-backend error names the backend" "nosuch" "$k_out"

# Malformed hash: rejected at resolver entry, BEFORE any path derivation —
# no cache directory may be created from an unvalidated (traversal-capable)
# value, and the self-heal rm must never see a traversal path.
k_out="$( artifact_resolve "../bad/hash" 2>&1 )"; k_rc=$?
assert_exit_nonzero_rc "malformed hash dies at resolver entry" "$k_rc"
assert_contains "malformed-hash error is the validation error" "invalid hash" "$k_out"
assert_not_contains "no misleading blob-not-found for a malformed hash" "blob not found" "$k_out"
assert_dir_not_exists "no traversal dir created in the cache root" "$TMP/xdg/ait/bad"
( artifact_cache_path "../bad/hash" ) >/dev/null 2>&1; k_rc=$?
assert_exit_nonzero_rc "artifact_cache_path dies on a malformed hash" "$k_rc"

# ── L. add refuses an archived owner; ls/get/rm still accept one (t2011) ─────
# resolve_task_file also answers with loose archived files and with temp
# extractions from .tar.zst bundles. add must write into neither: each refusal
# leaves no commit, no blob, no ledger file and no task-data change.
mk_task_at() {  # <path> <status>
    printf -- '---\npriority: medium\nstatus: %s\nupdated_at: 2026-01-01 00:00\n---\n\nTask body.\n' "$2" > "$1"
}
mkdir -p aitasks/archived/t21 aitasks/archived/_b0 aitasks/t24 "$TMP/bundle_src"
mk_task_at aitasks/archived/t20_loose.md Done
mk_task_at aitasks/archived/t21/t21_1_child.md Done
mk_task_at "$TMP/bundle_src/t22_bundled.md" Done
mk_task_at aitasks/t23_live.md Implementing
mk_task_at aitasks/t24/t24_1_kid.md Implementing
mk_task_at aitasks/t25_par.md Implementing
mk_task_at aitasks/t26_packed.md Implementing
L_PATHS=(aitasks/archived/t20_loose.md aitasks/archived/t21 aitasks/t23_live.md
         aitasks/t24 aitasks/t25_par.md aitasks/t26_packed.md)
git add -- "${L_PATHS[@]}"
git commit -q -m "fixture: L owners" -- "${L_PATHS[@]}"
# t26 gets a REAL attachment while active, then is packed into the bundle with
# t22, so L6's rm finds an entry to remove and reaches the transaction.
printf 'L6 attach payload\n' > l6.bin; HL6="$(artifact_sha256 l6.bin)"
"$ATT" add 26 l6.bin >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "L6 fixture: add on t26 while it is ACTIVE succeeds" "$rc"
cp aitasks/t26_packed.md "$TMP/bundle_src/t26_packed.md"
tar -cf - -C "$TMP/bundle_src" . | zstd -q -o aitasks/archived/_b0/old0.tar.zst
git rm -q -- aitasks/t26_packed.md
git add -- aitasks/archived/_b0
git commit -q -m "fixture: bundle t22 and t26" -- aitasks/t26_packed.md aitasks/archived/_b0
# Fixture shape: t22 must really resolve through the bundle tier (a temp
# extraction outside aitasks/), or L3 would test the loose path twice.
l3_resolved="$(resolve_task_file 22 2>/dev/null)"
assert_eq "L3 precondition: t22 resolves to a bundle extraction" "t22_bundled.md" "$(basename "$l3_resolved")"
assert_eq "L3 precondition: the extraction is outside the repo" "outside" "$(outside_repo "$l3_resolved")"

LAST_OUT=""
check_archived_refusal() {  # <label> <id> [archived-file]
    local label="$1" id="$2" afile="${3:-}" out rc before st_before payload shard
    # Per-case payload: a blob one case stored cannot mask another case's.
    payload="l_${label}.bin"; printf '%s attach payload\n' "$label" > "$payload"
    shard="$(artifact_shard_path "$(artifact_sha256 "$payload")")"
    before="$(git rev-list --count HEAD)"
    st_before="$(git status --porcelain -- aitasks attachments)"
    out="$("$ATT" add "$id" "$payload" 2>&1)"; rc=$?
    assert_exit_nonzero_rc "$label: add on an archived owner dies" "$rc"
    assert_contains "$label: error names the owner as archived" "is archived" "$out"
    assert_eq "$label: no commit" "$before" "$(git rev-list --count HEAD)"
    assert_file_not_exists "$label: no blob stored" "attachments/blobs/$shard"
    assert_file_not_exists "$label: no ledger file written" "attachments/meta/$shard.json"
    assert_eq "$label: no task-data change" "$st_before" \
        "$(git status --porcelain -- aitasks attachments)"
    if [[ -n "$afile" ]]; then
        assert_eq "$label: archived file gained no attachments: key" "0" "$(grep -c '^attachments:' "$afile")"
    fi
    LAST_OUT="$out"
}
check_archived_refusal L1 20 aitasks/archived/t20_loose.md
assert_contains "L1: error names the loose archived file" "aitasks/archived/t20_loose.md" "$LAST_OUT"
check_archived_refusal L2 21_1 aitasks/archived/t21/t21_1_child.md
check_archived_refusal L3 22
assert_contains "L3: error says the owner is in an archive bundle" "archive bundle" "$LAST_OUT"

# L4. Same id, both directions: add is accepted while t23 is active, refused
# once it is archived, and ls/get/rm keep working on the (loose) archived owner.
printf 'L4 attach payload\n' > l4.bin
out="$("$ATT" add 23 l4.bin 2>&1)"; rc=$?
assert_exit_zero_rc "L4 control: add on the ACTIVE owner succeeds" "$rc"
git mv aitasks/t23_live.md aitasks/archived/t23_live.md
git commit -q -m "fixture: archive t23" -- aitasks/t23_live.md aitasks/archived/t23_live.md
assert_contains "L4: ls still lists an archived owner's attachment" "l4.bin" "$("$ATT" ls 23 2>&1)"
"$ATT" get 23 l4.bin --out l4.got >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "L4: get still works on an archived owner" "$rc"
assert_eq "L4: get returns the stored bytes" "$(cat l4.bin)" "$(cat l4.got 2>/dev/null)"
printf 'L4b attach payload\n' > l4b.bin; SHARD_L4B="$(artifact_shard_path "$(artifact_sha256 l4b.bin)")"
before="$(git rev-list --count HEAD)"
out="$("$ATT" add 23 l4b.bin 2>&1)"; rc=$?
assert_exit_nonzero_rc "L4: add on the now-archived owner dies" "$rc"
assert_contains "L4: refusal names the owner as archived" "is archived" "$out"
assert_eq "L4: refused add made no commit" "$before" "$(git rev-list --count HEAD)"
assert_file_not_exists "L4: refused add wrote no ledger file" "attachments/meta/$SHARD_L4B.json"
out="$("$ATT" rm 23 l4.bin 2>&1)"; rc=$?
assert_exit_zero_rc "L4: rm still works on a loose archived owner" "$rc"
assert_eq "L4: rm committed" "$((before + 1))" "$(git rev-list --count HEAD)"
assert_not_contains "L4: archived file lost the entry" "l4.bin" "$(cat aitasks/archived/t23_live.md)"

# L5. The active/archived decision must not depend on how TASK_DIR /
# ARCHIVED_DIR are SPELLED. resolve_task_file keeps them verbatim, so a
# trailing slash yields `aitasks//t24/t24_1_kid.md` for a child while dirname
# collapses a parent's `aitasks//t25_par.md` to `aitasks`. Both active owners
# must still be accepted, and the archived ones still refused.
printf 'L5 attach payload\n' > l5.bin
out="$(TASK_DIR=aitasks/ ARCHIVED_DIR=aitasks/archived/ "$ATT" add 24_1 l5.bin 2>&1)"; rc=$?
assert_exit_zero_rc "L5: trailing-slash TASK_DIR: ACTIVE child accepted" "$rc"
assert_contains "L5: trailing-slash TASK_DIR: child entry written" "l5.bin" "$(cat aitasks/t24/t24_1_kid.md)"
out="$(TASK_DIR=aitasks/ ARCHIVED_DIR=aitasks/archived/ "$ATT" add 25 l5.bin 2>&1)"; rc=$?
assert_exit_zero_rc "L5: trailing-slash TASK_DIR: ACTIVE parent accepted" "$rc"
assert_contains "L5: trailing-slash TASK_DIR: parent entry written" "l5.bin" "$(cat aitasks/t25_par.md)"
before="$(git rev-list --count HEAD)"
out="$(TASK_DIR=aitasks/ ARCHIVED_DIR=aitasks/archived/ "$ATT" add 21_1 l5.bin 2>&1)"; rc=$?
assert_exit_nonzero_rc "L5: trailing-slash dirs: loose archived child still refused" "$rc"
assert_contains "L5: trailing-slash dirs: refusal names the archived file" "aitasks/archived/" "$out"
out="$(TASK_DIR=aitasks/ ARCHIVED_DIR=aitasks/archived/ "$ATT" add 22 l5.bin 2>&1)"; rc=$?
assert_exit_nonzero_rc "L5: trailing-slash dirs: bundled owner still refused" "$rc"
assert_contains "L5: trailing-slash dirs: bundled refusal says archived" "is archived" "$out"
assert_eq "L5: the two refusals made no commit" "$before" "$(git rev-list --count HEAD)"

# L6. A BUNDLED owner with a real attachment pins the scope the help and the
# refusal message state: ls and get work on it, but rm cannot -- the entry it
# would remove lives in a temp extraction outside the repo, so the transaction
# refuses before any mutation. The lookup must SUCCEED first (an rm that died
# at "no attachment matching" would prove nothing about the transaction).
l6_resolved="$(resolve_task_file 26 2>/dev/null)"
assert_eq "L6 precondition: t26 resolves to a bundle extraction" "t26_packed.md" "$(basename "$l6_resolved")"
assert_eq "L6 precondition: the extraction is outside the repo" "outside" "$(outside_repo "$l6_resolved")"
assert_contains "L6 precondition: the extraction lists the attachment" "$HL6" "$(cat "$l6_resolved" 2>/dev/null)"
assert_contains "L6: ls lists a bundled owner's attachment" "l6.bin" "$("$ATT" ls 26 2>&1)"
"$ATT" get 26 l6.bin --out l6.got >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "L6: get works on a bundled owner" "$rc"
assert_eq "L6: get returns the stored bytes" "$(cat l6.bin)" "$(cat l6.got 2>/dev/null)"
before="$(git rev-list --count HEAD)"
st_before="$(git status --porcelain -- aitasks attachments)"
out="$("$ATT" rm 26 l6.bin 2>&1)"; rc=$?
assert_exit_nonzero_rc "L6: rm on a bundled owner is refused" "$rc"
assert_not_contains "L6: rm got past the attachment lookup" "no attachment matching" "$out"
assert_contains "L6: rm was refused at the transaction boundary" "could not read the git status" "$out"
assert_eq "L6: refused rm made no commit" "$before" "$(git rev-list --count HEAD)"
assert_eq "L6: the ledger still lists t26" "26" "$(meta_refs "$HL6")"
assert_eq "L6: refused rm changed no task data" "$st_before" \
    "$(git status --porcelain -- aitasks attachments)"

echo ""
echo "test_attach_local_backend.sh: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
