#!/usr/bin/env bash
# test_artifact_share_resolution.sh - e2e for share-handle resolution (t1076_3):
# the `artifacts:` backend registry in project_config.yaml, the `dir` backend
# through the full `ait artifact` CLI, the write-back cache warm, and the
# `move` verb (copy-then-repoint, rollback, resumability). Proves both task
# ACs: (1) a handle authored on one checkout resolves on a second checkout
# that has only the project config; (2) a backend swap in config re-resolves
# the same handle with zero task-file (and zero manifest) changes.
# Uses a legacy-mode git repo fixture with an OUT-OF-REPO store dir.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ART="$PROJECT_DIR/.aitask-scripts/aitask_artifact.sh"
PY="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; resolve_python)"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export XDG_CACHE_HOME="$TMP/xdg"   # keep resolver cache inside the fixture
REPO="$TMP/repo"
STORE="$TMP/store"
mkdir -p "$REPO/aitasks/metadata" "$STORE"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester
printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask t5 body.\n' > aitasks/t5_demo.md
printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask t6 body.\n' > aitasks/t6_other.md
write_config() {  # write_config <store-path>
    printf 'attachments_gc_grace: 0\nartifacts:\n  default_backend: dir\n  backends:\n    dir:\n      path: %s\n' "$1" \
        > aitasks/metadata/project_config.yaml
}
write_config "$STORE"
git add -A; git commit -q -m init

# Pure libs for in-test hashing / shard paths / manifest access.
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_utils.sh"

manifest_of() { cat "artifacts/manifests/${1#art:}.json" 2>/dev/null; }
mf() { "$PY" "$PROJECT_DIR/.aitask-scripts/lib/artifact_manifest.py" --manifest-dir artifacts/manifests "$@"; }

# ── A. create on dir: blob outside the repo, commit touches manifest+task ─────
printf '<html>plan v1</html>\n' > plan.html
H1="$(artifact_sha256 plan.html)"; SHARD1="$(artifact_shard_path "$H1")"
before="$(git rev-list --count HEAD)"
out="$("$ART" create 5 plan.html --kind html_plan --backend dir 2>&1)"
after="$(git rev-list --count HEAD)"
assert_eq "exactly one commit per create" "1" "$((after - before))"
assert_contains "create prints the HANDLE line" "HANDLE:art:t5-htmlplan" "$out"
assert_contains "manifest records backend dir" '"backend": "dir"' "$(manifest_of art:t5-htmlplan)"
assert_file_exists "blob lands in the external store" "$STORE/$SHARD1"
assert_file_not_exists "no blob under the data-branch store" "attachments/blobs/$SHARD1"
committed="$(git show --name-only --pretty=format: HEAD)"
assert_contains "commit contains the manifest" "artifacts/manifests/t5-htmlplan.json" "$committed"
assert_contains "commit contains the task file" "aitasks/t5_demo.md" "$committed"
assert_not_contains "commit contains no blob path" "attachments/blobs" "$committed"
cache_entry="$XDG_CACHE_HOME/ait/artifacts/$H1"
assert_file_exists "cache warmed at create (write-back)" "$cache_entry"
if [[ -f "$cache_entry" && ! -L "$cache_entry" ]]; then
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
else
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); echo "FAIL: dir cache entry is a regular file"
fi

# ── B. default_backend from config ────────────────────────────────────────────
printf 'report bytes\n' > rep.txt
"$ART" create 6 rep.txt --kind report >/dev/null 2>&1
assert_contains "create without --backend uses artifacts.default_backend" \
    '"backend": "dir"' "$(manifest_of art:t6-report)"

# ── C. get via dir after cache clear ──────────────────────────────────────────
rm -rf "$XDG_CACHE_HOME"
"$ART" get art:t5-htmlplan --out got.html >/dev/null 2>&1
assert_eq "get after cache clear returns the bytes" "$(cat plan.html)" "$(cat got.html)"
assert_file_exists "get repopulated the cache" "$XDG_CACHE_HOME/ait/artifacts/$H1"

# ── D. AC 1 — second checkout resolves with only the project config ──────────
git clone -q "$REPO" "$TMP/repo2"
rm -rf "$XDG_CACHE_HOME"
(
    cd "$TMP/repo2" || exit 1
    "$ART" get art:t5-htmlplan --out got2.html >/dev/null 2>&1
) || true
assert_eq "AC1: second checkout resolves the handle (fetch+verify)" \
    "$(cat plan.html)" "$(cat "$TMP/repo2/got2.html" 2>/dev/null)"
assert_file_exists "AC1: fetch populated the cache" "$XDG_CACHE_HOME/ait/artifacts/$H1"
# With the store unmounted, the verified cache still serves the handle.
mv "$STORE" "$TMP/store.away"
(
    cd "$TMP/repo2" || exit 1
    "$ART" get art:t5-htmlplan --out got3.html >/dev/null 2>&1
) || true
assert_eq "AC1: cache leg serves with the store unmounted" \
    "$(cat plan.html)" "$(cat "$TMP/repo2/got3.html" 2>/dev/null)"
mv "$TMP/store.away" "$STORE"

# ── E. AC 2 — backend swap in config, zero task-file / manifest diff ─────────
cp -r "$STORE" "$TMP/store2"
cp aitasks/t5_demo.md "$TMP/t5.before"
write_config "$TMP/store2"
rm -rf "$XDG_CACHE_HOME"
"$ART" get art:t5-htmlplan --out got4.html >/dev/null 2>&1
assert_eq "AC2: swapped store path re-resolves the same handle" \
    "$(cat plan.html)" "$(cat got4.html)"
assert_eq "AC2: zero task-file / manifest changes" "" \
    "$(git status --porcelain -- aitasks/t5_demo.md aitasks/t6_other.md artifacts/)"
assert_exit_zero "AC2: task file byte-identical after the swap" cmp -s aitasks/t5_demo.md "$TMP/t5.before"
write_config "$STORE"
git checkout -q -- aitasks/metadata/project_config.yaml 2>/dev/null || true
write_config "$STORE"

# ── F. update on dir backend: manifest-only commit, write-back warm ──────────
printf '<html>plan v2</html>\n' > plan2.html
H2="$(artifact_sha256 plan2.html)"; SHARD2="$(artifact_shard_path "$H2")"
before="$(git rev-list --count HEAD)"
"$ART" update art:t5-htmlplan plan2.html >/dev/null 2>&1
after="$(git rev-list --count HEAD)"
assert_eq "exactly one commit per update" "1" "$((after - before))"
committed="$(git show --name-only --pretty=format: HEAD)"
assert_contains "update commit contains the manifest" "artifacts/manifests/t5-htmlplan.json" "$committed"
assert_not_contains "update commit contains no task file" "aitasks/" "$committed"
# Write-back warmed the cache: the store copy is not needed to serve v2.
rm -f "$STORE/$SHARD2"
"$ART" get art:t5-htmlplan --out gotv2.html >/dev/null 2>&1
assert_eq "v2 served from the write-back-warmed cache" "$(cat plan2.html)" "$(cat gotv2.html)"
# Restore the store copy; an old version still fetches from the store.
( source "$PROJECT_DIR/.aitask-scripts/lib/artifact_backend.sh"; \
  source "$PROJECT_DIR/.aitask-scripts/lib/artifact_backends/dir.sh" 2>/dev/null; \
  ARTIFACT_BACKEND=dir ARTIFACT_DIR_ROOT="$STORE" artifact_backend_put "$H2" plan2.html )
rm -rf "$XDG_CACHE_HOME"
"$ART" get art:t5-htmlplan --version "$H1" --out gotv1.html >/dev/null 2>&1
assert_eq "get --version fetches an old version from the store" "$(cat plan.html)" "$(cat gotv1.html)"

# ── G. move suite ─────────────────────────────────────────────────────────────
# local→dir with 2 versions.
printf 'local artifact v1\n' > la1.txt
printf 'local artifact v2\n' > la2.txt
HL1="$(artifact_sha256 la1.txt)"; SHL1="$(artifact_shard_path "$HL1")"
HL2="$(artifact_sha256 la2.txt)"; SHL2="$(artifact_shard_path "$HL2")"
"$ART" create 6 la1.txt --kind mockup --handle art:t6-mock --backend local >/dev/null 2>&1
"$ART" update art:t6-mock la2.txt >/dev/null 2>&1
cp aitasks/t6_other.md "$TMP/t6.before"
before="$(git rev-list --count HEAD)"
"$ART" move art:t6-mock --to dir >/dev/null 2>&1
after="$(git rev-list --count HEAD)"
assert_eq "exactly one commit per move" "1" "$((after - before))"
assert_contains "move repointed the manifest to dir" '"backend": "dir"' "$(manifest_of art:t6-mock)"
assert_file_exists "move copied v1 to the store" "$STORE/$SHL1"
assert_file_exists "move copied v2 to the store" "$STORE/$SHL2"
assert_file_exists "source local blob v1 intact" "attachments/blobs/$SHL1"
assert_file_exists "source local blob v2 intact" "attachments/blobs/$SHL2"
committed="$(git show --name-only --pretty=format: HEAD)"
assert_contains "move commit contains the manifest" "artifacts/manifests/t6-mock.json" "$committed"
assert_not_contains "move commit contains no task file" "aitasks/" "$committed"
assert_exit_zero "task file byte-identical after move" cmp -s aitasks/t6_other.md "$TMP/t6.before"
rm -rf "$XDG_CACHE_HOME"
"$ART" get art:t6-mock --out mock.out >/dev/null 2>&1
assert_eq "cache-cleared get serves from dir after move" "$(cat la2.txt)" "$(cat mock.out)"

# Round-trip back to local: the source blobs never left the data branch
# (non-destructive move), so only the manifest changes.
"$ART" move art:t6-mock --to local >/dev/null 2>&1
assert_contains "move back repointed the manifest to local" '"backend": "local"' "$(manifest_of art:t6-mock)"
mv "$STORE" "$TMP/store.away"
rm -rf "$XDG_CACHE_HOME"
"$ART" get art:t6-mock --out mock2.out >/dev/null 2>&1
assert_eq "get works with the store away after move to local" "$(cat la2.txt)" "$(cat mock2.out)"
mv "$TMP/store.away" "$STORE"

# dir→local for a DIR-BORN artifact: the blobs are new to the data branch and
# must be staged + committed by the move.
printf 'dir-born artifact\n' > db.txt
HDB="$(artifact_sha256 db.txt)"; SHDB="$(artifact_shard_path "$HDB")"
"$ART" create 6 db.txt --kind report --handle art:t6-dirborn --backend dir >/dev/null 2>&1
"$ART" move art:t6-dirborn --to local >/dev/null 2>&1
assert_contains "dir-born move repointed the manifest to local" '"backend": "local"' "$(manifest_of art:t6-dirborn)"
committed="$(git show --name-only --pretty=format: HEAD)"
assert_contains "dir->local move commits the blobs" "attachments/blobs/$SHDB" "$committed"
mv "$STORE" "$TMP/store.away"
rm -rf "$XDG_CACHE_HOME"
"$ART" get art:t6-dirborn --out db.out >/dev/null 2>&1
assert_eq "dir-born artifact serves from local with the store away" "$(cat db.txt)" "$(cat db.out)"
mv "$TMP/store.away" "$STORE"

# move to an unregistered target dies pre-mutation.
cp "artifacts/manifests/t6-mock.json" "$TMP/mock.manifest.before"
assert_exit_nonzero "move to an unregistered target dies" "$ART" move art:t6-mock --to s3
assert_exit_zero "rejected move left the manifest untouched" \
    cmp -s "artifacts/manifests/t6-mock.json" "$TMP/mock.manifest.before"

# same-backend move: friendly no-op, zero new commits.
before="$(git rev-list --count HEAD)"
out="$("$ART" move art:t6-mock --to local 2>&1)"; rc=$?
after="$(git rev-list --count HEAD)"
assert_exit_zero_rc "same-backend move exits 0" "$rc"
assert_contains "same-backend move says nothing to do" "nothing to do" "$out"
assert_eq "same-backend move makes no commit" "0" "$((after - before))"

# move of a missing handle dies.
assert_exit_nonzero "move of a missing handle dies" "$ART" move art:nosuch --to dir

# Commit-failure rollback: a failing pre-commit hook lets `add` succeed and
# `commit` fail while reset/checkout still work (an .git/index.lock would
# block the restore itself and fail the test for the wrong reason).
# State: art:t6-mock is back on local; $STORE still holds HL1+HL2 from the
# earlier local->dir move. Remove HL2 from the store so the failed move
# CREATES it (and must delete it on rollback) while HL1 PRE-EXISTS (and must
# survive rollback) — pre-existence tracking is load-bearing.
rm -f "$STORE/$SHL2"
printf 'exit 1\n' > .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit
cp "artifacts/manifests/t6-mock.json" "$TMP/mock.manifest.before2"
out="$("$ART" move art:t6-mock --to dir 2>&1)"; rc=$?
rm -f .git/hooks/pre-commit
assert_exit_nonzero_rc "move with failing commit dies" "$rc"
assert_exit_zero "rollback restored the manifest byte-identical" \
    cmp -s "artifacts/manifests/t6-mock.json" "$TMP/mock.manifest.before2"
assert_eq "rollback left no dirty data paths" "" \
    "$(git status --porcelain -- aitasks/ artifacts/ attachments/)"
assert_file_not_exists "rollback deleted the newly copied target blob" "$STORE/$SHL2"
assert_file_exists "pre-existing target blob survived rollback" "$STORE/$SHL1"
# Resumability positive control: the same move now succeeds.
assert_exit_zero "re-run of the failed move succeeds" "$ART" move art:t6-mock --to dir
assert_contains "re-run repointed the manifest" '"backend": "dir"' "$(manifest_of art:t6-mock)"
"$ART" move art:t6-mock --to local >/dev/null 2>&1   # restore for later sections

# ── H. rm on dir backend: store blob survives ─────────────────────────────────
printf 'dir-owned artifact\n' > dirart.txt
HDA="$(artifact_sha256 dirart.txt)"; SHDA="$(artifact_shard_path "$HDA")"
"$ART" create 5 dirart.txt --kind report --handle art:t5-dirrep --backend dir >/dev/null 2>&1
out="$("$ART" rm 5 art:t5-dirrep 2>&1)"
assert_contains "rm on dir backend warns blobs not deleted" "not deleted" "$out"
assert_contains "rm warn points at the reaper task" "t1135" "$out"
assert_file_exists "store blob survives rm" "$STORE/$SHDA"
assert_eq "manifest deleted by rm" "" "$(manifest_of art:t5-dirrep)"
committed="$(git show --name-only --pretty=format: HEAD)"
assert_contains "rm commit contains the task file" "aitasks/t5_demo.md" "$committed"
assert_contains "rm commit contains the manifest" "artifacts/manifests/t5-dirrep.json" "$committed"
assert_not_contains "rm commit contains no blob path" "attachments/blobs" "$committed"

# ── I. unregistered-backend get fails closed ─────────────────────────────────
# Point the manifest at a backend name absent from config (via the lib —
# BACKEND_RE allows it; registry membership is enforced at activation).
mf set-backend art:t5-htmlplan ghost >/dev/null
out="$("$ART" get art:t5-htmlplan --out ghost.out 2>&1)"; rc=$?
assert_exit_nonzero_rc "get with an unregistered manifest backend dies" "$rc"
assert_contains "unregistered-get error is actionable" "not registered" "$out"
mf set-backend art:t5-htmlplan dir >/dev/null
git checkout -q -- artifacts/ 2>/dev/null || true

echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
