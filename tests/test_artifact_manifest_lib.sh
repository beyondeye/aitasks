#!/usr/bin/env bash
# test_artifact_manifest_lib.sh - unit tests for the per-artifact manifest
# primitive (t1076_1): lib/artifact_manifest.py + lib/artifact_manifest.sh.
# CRUD, schema invariants, fail-closed malformed-manifest policy, atomicity,
# and the two t1076_1 ACs: manifest writes never touch a task file, and the
# committed manifest travels through the (data) branch — a second clone
# resolves the same handle. Uses a legacy-mode git repo fixture
# (no .aitask-data worktree -> _ait_detect_data_worktree returns ".").
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

PY="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; resolve_python)"
MANIFEST_PY="$PROJECT_DIR/.aitask-scripts/lib/artifact_manifest.py"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/repo"
mkdir -p "$REPO/aitasks/metadata"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester
printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask t5 body.\n' > aitasks/t5_demo.md
git add -A; git commit -q -m init

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_manifest.sh"

H1="sha256:1111111111111111111111111111111111111111111111111111111111111111"
H2="sha256:2222222222222222222222222222222222222222222222222222222222222222"
H3="sha256:3333333333333333333333333333333333333333333333333333333333333333"

# ── A. create -> get/current/versions/backend ─────────────────────────────────
artifact_manifest create art:t5-demo "$H1" now=100
assert_file_exists "manifest file at artifacts/manifests/<id>.json" "artifacts/manifests/t5-demo.json"
assert_eq "current after create" "$H1" "$(artifact_manifest current art:t5-demo)"
assert_eq "versions after create" "$H1" "$(artifact_manifest versions art:t5-demo)"
assert_contains "get prints the backend (default local)" '"backend": "local"' "$(artifact_manifest get art:t5-demo)"
assert_contains "get prints created_at epoch" '"created_at": 100' "$(artifact_manifest get art:t5-demo)"
assert_exit_nonzero "create on an existing handle dies" artifact_manifest create art:t5-demo "$H2"

# Reads on a missing handle: empty output, exit 0.
assert_eq "get on missing handle prints nothing" "" "$(artifact_manifest get art:nosuch)"
assert_exit_zero "get on missing handle exits 0" artifact_manifest get art:nosuch
assert_eq "current on missing handle prints nothing" "" "$(artifact_manifest current art:nosuch)"

# ── B. handle validation (validation-not-transformation) ─────────────────────
assert_exit_nonzero "handle without art: prefix dies" artifact_manifest create t5-x "$H1"
assert_exit_nonzero "uppercase handle dies (case-insensitive fs collision)" artifact_manifest create art:Foo "$H1"
assert_exit_nonzero "path-traversal handle dies" artifact_manifest create 'art:../x' "$H1"
assert_exit_nonzero "leading-dot handle dies" artifact_manifest create 'art:.hidden' "$H1"
assert_exit_nonzero "empty id dies" artifact_manifest create 'art:' "$H1"
long_id="$(printf 'a%.0s' $(seq 1 129))"
assert_exit_nonzero "handle id >128 chars dies" artifact_manifest create "art:$long_id" "$H1"
assert_exit_nonzero "invalid hash dies on create" artifact_manifest create art:t5-badhash "sha256:zzzz"
# (subshell: artifact_manifest_relpath is a bash function whose die would exit
#  this test shell — same pattern as the shard_path check in the scaffold test)
( artifact_manifest_relpath 'art:../x' ) >/dev/null 2>&1; relpath_rc=$?
assert_exit_nonzero_rc "relpath helper rejects invalid handle" "$relpath_rc"
assert_eq "relpath helper shape" "artifacts/manifests/t5-demo.json" "$(artifact_manifest_relpath art:t5-demo)"

# ── C. set-current: append+move; repoint-to-old moves without duplicate ──────
artifact_manifest set-current art:t5-demo "$H2" now=200
assert_eq "set-current moves current to the new hash" "$H2" "$(artifact_manifest current art:t5-demo)"
assert_eq "set-current appended the new version (oldest first)" "$H1
$H2" "$(artifact_manifest versions art:t5-demo)"
artifact_manifest set-current art:t5-demo "$H1" now=300
assert_eq "repoint to an old version moves current" "$H1" "$(artifact_manifest current art:t5-demo)"
assert_eq "repoint to an old version does NOT duplicate versions" "$H1
$H2" "$(artifact_manifest versions art:t5-demo)"
assert_exit_nonzero "set-current on a missing manifest dies" artifact_manifest set-current art:nosuch "$H1"

# ── D. set-backend + conservative name-shape validation ──────────────────────
artifact_manifest set-backend art:t5-demo s3-compat now=400
assert_contains "set-backend persists a valid name" '"backend": "s3-compat"' "$(artifact_manifest get art:t5-demo)"
artifact_manifest set-backend art:t5-demo gh_release now=401
assert_contains "underscore backend name accepted" '"backend": "gh_release"' "$(artifact_manifest get art:t5-demo)"
assert_exit_nonzero "backend name with space dies" artifact_manifest set-backend art:t5-demo "Bad Name"
assert_exit_nonzero "backend name with ! dies" artifact_manifest set-backend art:t5-demo "s3compat!"
assert_exit_nonzero "uppercase backend name dies" artifact_manifest set-backend art:t5-demo "Local"
assert_exit_nonzero "create with bad backend kv dies" artifact_manifest create art:t5-bad "$H1" "backend=No Good"
artifact_manifest set-backend art:t5-demo local now=402   # restore

# ── E. list + referenced-hashes (union across manifests, all versions) ───────
artifact_manifest create art:t6-report "$H2" now=500      # shares H2 with t5-demo
artifact_manifest set-current art:t6-report "$H3" now=501
assert_eq "list prints every handle sorted" "art:t5-demo
art:t6-report" "$(artifact_manifest list)"
assert_eq "referenced-hashes = union of ALL versions, deduped, sorted" "$H1
$H2
$H3" "$(artifact_manifest referenced-hashes)"

# ── F. atomicity / cleanliness ────────────────────────────────────────────────
leftover="$(find artifacts/manifests -name '.manifest.*' | wc -l | xargs)"
assert_eq "no temp files left behind in artifacts/manifests/" "0" "$leftover"

# ── G. AC: manifest writes never touch a task file ────────────────────────────
task_bytes_before="$(cat aitasks/t5_demo.md)"
git add -A; git commit -q -m "pre-mutation snapshot"
artifact_manifest create art:t5-ac "$H1" now=600
artifact_manifest set-current art:t5-ac "$H2" now=601
artifact_manifest set-backend art:t5-ac local now=602
assert_eq "task file byte-identical after create+set-current+set-backend" \
    "$task_bytes_before" "$(cat aitasks/t5_demo.md)"
assert_eq "git sees no change under aitasks/" "" "$(git status --porcelain -- aitasks/)"

# ── H. AC: committed manifest travels through the branch ─────────────────────
rel="$(artifact_manifest_relpath art:t5-ac)"
git add "$rel"
git commit -q -m "ait: add manifest for art:t5-ac"
assert_contains "committed manifest readable via git show" '"handle": "art:t5-ac"' \
    "$(git show "HEAD:$rel")"
git add -A; git commit -q -m "commit remaining fixture state" >/dev/null 2>&1 || true
CLONE="$TMP/clone"
git clone -q "$REPO" "$CLONE"
clone_rec="$("$PY" "$MANIFEST_PY" --manifest-dir "$CLONE/artifacts/manifests" get art:t5-ac)"
assert_contains "second clone resolves the handle (current)" "\"current\": \"$H2\"" "$clone_rec"
assert_eq "second clone record matches the origin record" \
    "$("$PY" "$MANIFEST_PY" --manifest-dir "$REPO/artifacts/manifests" get art:t5-ac)" "$clone_rec"

# ── I. malformed-manifest policy: fail-closed, names the offending file ──────
printf 'not json at all\n' > artifacts/manifests/broken.json
bad_out="$( artifact_manifest list 2>&1 )"; bad_rc=$?
assert_exit_nonzero_rc "list dies on a malformed manifest" "$bad_rc"
assert_contains "error names the offending file" "broken.json" "$bad_out"
bad_out="$( artifact_manifest referenced-hashes 2>&1 )"; bad_rc=$?
assert_exit_nonzero_rc "referenced-hashes dies on a malformed manifest" "$bad_rc"
assert_contains "referenced-hashes error names the file" "broken.json" "$bad_out"
rm -f artifacts/manifests/broken.json

# Invariant violation (current not in versions) is equally fatal and named.
cat > artifacts/manifests/drift.json <<EOF
{"handle": "art:drift", "current": "$H3",
 "versions": ["$H1"], "backend": "local",
 "created_at": 1, "updated_at": 2}
EOF
bad_out="$( artifact_manifest referenced-hashes 2>&1 )"; bad_rc=$?
assert_exit_nonzero_rc "invariant violation (current not in versions) dies" "$bad_rc"
assert_contains "invariant error names file + invariant" "current not in versions" "$bad_out"
assert_contains "invariant error names the offending file" "drift.json" "$bad_out"
rm -f artifacts/manifests/drift.json

# Handle/filename mismatch is caught (a renamed/copied manifest cannot lie).
cp artifacts/manifests/t5-demo.json artifacts/manifests/wrongname.json
bad_out="$( artifact_manifest list 2>&1 )"; bad_rc=$?
assert_exit_nonzero_rc "handle/filename mismatch dies" "$bad_rc"
assert_contains "mismatch error names the file" "wrongname.json" "$bad_out"
rm -f artifacts/manifests/wrongname.json

echo ""
echo "test_artifact_manifest_lib.sh: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
