#!/usr/bin/env bash
# test_artifact_dir_backend.sh - lib-level tests for the `dir` artifact backend,
# the backend registry (t1076_3), and the artifact_store write-back helper.
# Covers: dir adapter round-trip (incl. corrupt-pre-existing-dest self-heal),
# registry activation (param export, cross-activation leakage guard, fail-closed
# validation incl. top-level non-mapping config), the resolver through dir
# (regular-file cache entry, self-heal, unmounted-root die), and artifact_store
# (cache warmed without a backend get round-trip; store repair). Uses a
# legacy-mode git repo fixture (no .aitask-data worktree).
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/repo"
STORE="$TMP/store"
mkdir -p "$REPO/aitasks/metadata" "$STORE"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester
printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask body.\n' > aitasks/t5_demo.md
git add -A; git commit -q -m init

# Keep the resolver cache inside the fixture.
export XDG_CACHE_HOME="$TMP/xdg"

write_config() {  # write_config <store-path>
    printf 'artifacts:\n  default_backend: dir\n  backends:\n    dir:\n      path: %s\n' "$1" \
        > aitasks/metadata/project_config.yaml
}
write_config "$STORE"

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_backend.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_cache.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_registry.sh"

# ── A. dir adapter round-trip ─────────────────────────────────────────────────
artifact_registry_activate dir
printf 'dir backend blob bytes\n' > a1.bin
HA="$(artifact_sha256 a1.bin)"; SHARD_A="$(artifact_shard_path "$HA")"
artifact_backend_put "$HA" a1.bin
assert_file_exists "blob lands at <store>/<2>/<62>" "$STORE/$SHARD_A"
assert_exit_zero "dir head finds the stored blob" artifact_backend_head "$HA"
artifact_backend_get "$HA" a1.out
assert_eq "dir get returns identical bytes" "$(cat a1.bin)" "$(cat a1.out)"
assert_eq "dir get - streams to stdout" "$(cat a1.bin)" "$(artifact_backend_get "$HA" -)"
assert_contains "dir list includes the blob" "$HA" "$(artifact_backend_list)"
assert_exit_zero "double-put is idempotent" artifact_backend_put "$HA" a1.bin
assert_eq "no .put.* temp residue after put" "" "$(find "$STORE" -name '.put.*' -print)"

# Corrupt pre-existing dest self-heal: wrong bytes at the content address are
# repaired from the (provably correct) source bytes.
printf 'WRONG BYTES\n' > "$STORE/$SHARD_A"
assert_exit_zero "put over a corrupt dest succeeds" artifact_backend_put "$HA" a1.bin 2>/dev/null
assert_eq "corrupt dest was repaired to correct bytes" "$HA" "$(artifact_sha256 "$STORE/$SHARD_A")"
# A pre-seeded CORRECT dest is left untouched (no gratuitous rewrite).
touch -d '2000-01-01 00:00:00' "$STORE/$SHARD_A"
mtime_before="$(stat -c %Y "$STORE/$SHARD_A" 2>/dev/null || stat -f %m "$STORE/$SHARD_A")"
artifact_backend_put "$HA" a1.bin
mtime_after="$(stat -c %Y "$STORE/$SHARD_A" 2>/dev/null || stat -f %m "$STORE/$SHARD_A")"
assert_eq "correct pre-existing dest is not rewritten" "$mtime_before" "$mtime_after"
# Staged-bytes verification: put runs in errexit-suppressed transaction
# trees, so a partial copy must never be installed. Simulate bytes that do
# not hash to the address by putting a mismatched file: die, no store entry,
# no temp residue.
printf 'bytes that do not match HA\n' > mismatch.bin
artifact_backend_delete "$HA"
out="$( (artifact_backend_put "$HA" mismatch.bin) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "put of bytes that fail staged verification dies" "$rc"
assert_contains "staged-verification error says nothing installed" "nothing installed" "$out"
assert_file_not_exists "no store entry installed on staged-verification failure" "$STORE/$SHARD_A"
assert_eq "no temp residue after staged-verification failure" "" "$(find "$STORE" -name '.put.*' -print)"
artifact_backend_put "$HA" a1.bin   # restore for the delete assertions below

artifact_backend_delete "$HA"
assert_exit_nonzero "dir head misses after delete" artifact_backend_head "$HA"

# ── B. registry activation ────────────────────────────────────────────────────
artifact_registry_activate dir
assert_eq "activate dir exports ARTIFACT_BACKEND" "dir" "$ARTIFACT_BACKEND"
assert_eq "activate dir exports ARTIFACT_DIR_ROOT" "$STORE" "$ARTIFACT_DIR_ROOT"
artifact_registry_activate local
assert_eq "activate local exports ARTIFACT_BACKEND" "local" "$ARTIFACT_BACKEND"
assert_eq "activate local clears the previous backend's params (leakage guard)" \
    "" "${ARTIFACT_DIR_ROOT:-}"

out="$( (artifact_registry_activate nosuch) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "activate of an unregistered backend dies" "$rc"
assert_contains "unregistered-backend error is actionable" "not registered" "$out"

# Registered but adapterless: `s3` in config has no shipped adapter yet.
printf 'artifacts:\n  backends:\n    s3:\n      bucket: b\n' > aitasks/metadata/project_config.yaml
out="$( (artifact_registry_activate s3) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "registered-but-adapterless backend dies" "$rc"
assert_contains "adapterless error names the arriving tasks" "t1089" "$out"

# dir with missing required key.
printf 'artifacts:\n  backends:\n    dir: {}\n' > aitasks/metadata/project_config.yaml
out="$( (artifact_registry_activate dir) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "dir without path dies" "$rc"
assert_contains "missing-key error names the key" "path" "$out"

# dir with a relative path.
printf 'artifacts:\n  backends:\n    dir:\n      path: relative/store\n' > aitasks/metadata/project_config.yaml
out="$( (artifact_registry_activate dir) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "dir with a relative path dies" "$rc"
assert_contains "relative-path error says absolute" "absolute" "$out"

# artifacts: block malformed (a list, not a mapping).
printf 'artifacts:\n  - not\n  - a-mapping\n' > aitasks/metadata/project_config.yaml
out="$( (artifact_registry_activate dir) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "list-shaped artifacts: block dies" "$rc"

# Top-level non-mapping config: must die, NOT silently fail open to local.
printf -- '- the\n- whole\n- file\n- is\n- a\n- list\n' > aitasks/metadata/project_config.yaml
out="$( (artifact_registry_activate dir) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "top-level non-mapping config dies on activate" "$rc"
assert_contains "non-mapping error names the file" "project_config.yaml" "$out"
out="$( (artifact_registry_default_backend) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "top-level non-mapping config dies on default-backend" "$rc"

# Positive controls beside the fail-closed cases.
rm -f aitasks/metadata/project_config.yaml
assert_eq "missing config file -> default backend local" "local" "$(artifact_registry_default_backend)"
assert_exit_zero "activate local works with no config file" artifact_registry_activate local
write_config "$STORE"
assert_eq "default-backend reads artifacts.default_backend" "dir" "$(artifact_registry_default_backend)"
printf 'artifacts:\n  default_backend: nosuch\n  backends:\n    dir:\n      path: %s\n' "$STORE" \
    > aitasks/metadata/project_config.yaml
out="$( (artifact_registry_default_backend) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "unregistered default_backend dies" "$rc"
write_config "$STORE"

# ── C. resolver through dir ───────────────────────────────────────────────────
artifact_registry_activate dir
printf 'resolver through dir\n' > c1.bin
HC="$(artifact_sha256 c1.bin)"
artifact_backend_put "$HC" c1.bin
rm -rf "$XDG_CACHE_HOME"
cpath="$(artifact_resolve "$HC")"
assert_exit_zero "resolve through dir succeeds" test -n "$cpath"
if [[ -f "$cpath" && ! -L "$cpath" ]]; then
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
else
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); echo "FAIL: dir cache entry is a regular file (not a symlink)"
fi
assert_eq "resolved bytes verify" "$HC" "$(artifact_sha256 "$cpath")"

# Corrupted cache copy self-heals from the dir store.
printf 'corrupted cache copy\n' > "$cpath"
cpath2="$(artifact_resolve "$HC" 2>/dev/null)"
assert_eq "corrupted cache copy self-heals from the store" "$HC" "$(artifact_sha256 "$cpath2")"

# Missing root (unmounted share) dies actionably. Clear the cache first —
# with a warm cache the resolver correctly serves offline (asserted in §D).
rm -rf "$XDG_CACHE_HOME"
mv "$STORE" "$TMP/store.away"
out="$( (artifact_resolve "$HC") 2>&1 )"; rc=$?
assert_exit_nonzero_rc "resolve with the store root missing dies" "$rc"
assert_contains "unmounted-root error asks about the mount" "is the share mounted" "$out"
mv "$TMP/store.away" "$STORE"

# ── D. artifact_store write-back ──────────────────────────────────────────────
artifact_registry_activate dir
printf 'write-back store bytes\n' > d1.bin
HD="$(artifact_sha256 d1.bin)"; SHARD_D="$(artifact_shard_path "$HD")"
rm -rf "$XDG_CACHE_HOME"
artifact_store "$HD" d1.bin
assert_file_exists "store put the blob in the dir store" "$STORE/$SHARD_D"
assert_file_exists "store warmed the cache" "$XDG_CACHE_HOME/ait/artifacts/$HD"
# Cache was warmed at write time: the store copy is not needed for a resolve.
rm -f "$STORE/$SHARD_D"
cpath="$(artifact_resolve "$HD")"
assert_eq "resolve served from the write-back-warmed cache" "$HD" "$(artifact_sha256 "$cpath")"
artifact_backend_put "$HD" d1.bin   # restore the store copy

# Tampered source dies before any put.
printf 'not the d1 bytes\n' > tampered.bin
out="$( (artifact_store "$HD" tampered.bin) 2>&1 )"; rc=$?
assert_exit_nonzero_rc "store of a file that does not hash to <hash> dies" "$rc"

# Store-repair regression: wrong bytes pre-seeded at the shard path get
# repaired, and a cache-cleared re-resolve returns correct bytes (the
# second-checkout corruption scenario).
printf 'WRONG STORE BYTES\n' > "$STORE/$SHARD_D"
artifact_store "$HD" d1.bin 2>/dev/null
assert_eq "artifact_store repaired the corrupt store entry" "$HD" "$(artifact_sha256 "$STORE/$SHARD_D")"
rm -rf "$XDG_CACHE_HOME"
cpath="$(artifact_resolve "$HD")"
assert_eq "cache-cleared re-resolve returns correct bytes" "$HD" "$(artifact_sha256 "$cpath")"

echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
