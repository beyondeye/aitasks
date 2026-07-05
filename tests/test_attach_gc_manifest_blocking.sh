#!/usr/bin/env bash
# test_attach_gc_manifest_blocking.sh - `ait attach gc` vs the artifact-manifest
# store (t1076_1). Asserts the design-§9 reconciliation: any hash referenced by
# ANY artifact-manifest version blocks reclamation (version-aware), an
# artifact-only blob (no meta file) is invisible to gc, and a malformed
# manifest aborts the sweep fail-closed with an error naming the file.
# Includes the negative control proving the guard is load-bearing: an
# identically-orphaned blob with NO manifest reference IS swept in the same run.
# Legacy-mode git fixture (no .aitask-data -> task_git is plain git in cwd).
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
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_backend.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_manifest.sh"

mk_task() {
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s body.\n' "$1" > "aitasks/$1.md"
}
mk_task t5_demo
git add -A; git commit -q -m init

meta_refs()  { "$PY" "$META" --meta-dir attachments/meta refs "$1" | paste -sd, -; }
set_grace()  { printf 'attachments_gc_grace: %s\n' "$1" > aitasks/metadata/project_config.yaml; }
blob_of()    { printf 'attachments/blobs/%s' "$(artifact_shard_path "$1")"; }
meta_of()    { printf 'attachments/meta/%s.json' "$(artifact_shard_path "$1")"; }

# Distinct content per case (content-addressed -> distinct hashes).
printf 'manifest-guarded bytes\n'      > a_guard.bin; HA="$(artifact_sha256 a_guard.bin)"
printf 'negative-control bytes\n'      > a_neg.bin;   HB="$(artifact_sha256 a_neg.bin)"
printf 'old-version bytes\n'           > a_oldv.bin;  HC="$(artifact_sha256 a_oldv.bin)"
printf 'current-version bytes\n'       > a_curv.bin;  HD="$(artifact_sha256 a_curv.bin)"
printf 'artifact-only bytes\n'         > a_art.bin;   HE="$(artifact_sha256 a_art.bin)"

set_grace 0   # every orphan is immediately past grace -> the guard is the only protection

# ── A. Guarded blob survives; negative control is swept in the SAME run ──────
# Both A and B: attached to t5, then rm'd -> zero refs + orphaned_at stamped.
# Only A gains a manifest reference. Without the t1076_1 guard, A would go the
# way of B — B proves the sweep really ran (the guard is load-bearing).
"$ATT" add 5 a_guard.bin --name guard.bin >/dev/null 2>&1
"$ATT" add 5 a_neg.bin   --name neg.bin   >/dev/null 2>&1
artifact_manifest create art:t5-demo "$HA" now=100
"$ATT" rm 5 guard.bin >/dev/null 2>&1
"$ATT" rm 5 neg.bin   >/dev/null 2>&1
assert_eq "guarded blob is fully orphaned in the ledger" "" "$(meta_refs "$HA")"
assert_eq "negative-control blob is fully orphaned too" "" "$(meta_refs "$HB")"
"$ATT" gc >/dev/null 2>&1
assert_file_exists "manifest-referenced orphan SURVIVES gc" "$(blob_of "$HA")"
assert_file_exists "its zero-ref meta file is retained (block lifts at pruning)" "$(meta_of "$HA")"
assert_file_not_exists "negative control: unguarded orphan IS swept" "$(blob_of "$HB")"
assert_file_not_exists "negative control: unguarded orphan's meta swept too" "$(meta_of "$HB")"

# ── B. Version-awareness: an OLD version's blob survives (not just current) ──
"$ATT" add 5 a_oldv.bin --name oldv.bin >/dev/null 2>&1
"$ATT" add 5 a_curv.bin --name curv.bin >/dev/null 2>&1
artifact_manifest create art:t5-versions "$HC" now=200
artifact_manifest set-current art:t5-versions "$HD" now=201   # HC is now an OLD version
assert_eq "manifest current moved to the new version" "$HD" "$(artifact_manifest current art:t5-versions)"
"$ATT" rm 5 oldv.bin >/dev/null 2>&1
"$ATT" rm 5 curv.bin >/dev/null 2>&1
"$ATT" gc >/dev/null 2>&1
assert_file_exists "OLD manifest version's blob survives gc (version-aware)" "$(blob_of "$HC")"
assert_file_exists "current manifest version's blob survives gc" "$(blob_of "$HD")"

# ── C. Artifact-only blob (backend put, no meta file) is invisible to gc ─────
artifact_backend_put "$HE" a_art.bin
assert_file_exists "artifact-only blob stored" "$(blob_of "$HE")"
assert_file_not_exists "artifact-only blob has no attachment meta file" "$(meta_of "$HE")"
"$ATT" gc >/dev/null 2>&1
assert_file_exists "gc leaves the artifact-only blob untouched" "$(blob_of "$HE")"

# ── D. Malformed manifest: gc aborts fail-closed, names the file, sweeps nothing ─
# Re-orphan a fresh sweepable blob so a (wrongly) proceeding sweep WOULD delete it.
printf 'sweepable-under-corruption bytes\n' > a_swp.bin; HS="$(artifact_sha256 a_swp.bin)"
"$ATT" add 5 a_swp.bin --name swp.bin >/dev/null 2>&1
"$ATT" rm 5 swp.bin >/dev/null 2>&1
printf 'not json at all\n' > artifacts/manifests/corrupt.json
gc_out="$("$ATT" gc 2>&1)"; gc_rc=$?
assert_exit_nonzero_rc "gc dies on a malformed manifest" "$gc_rc"
assert_contains "gc error names the offending manifest file" "corrupt.json" "$gc_out"
assert_contains "gc error says the sweep was aborted" "sweep aborted" "$gc_out"
assert_file_exists "fail-closed: sweepable orphan NOT deleted under corruption" "$(blob_of "$HS")"
assert_file_exists "fail-closed: guarded blob untouched under corruption" "$(blob_of "$HA")"
rm -f artifacts/manifests/corrupt.json
# After repair (removal), the same orphan is sweepable again -> sweep proceeds.
"$ATT" gc >/dev/null 2>&1
assert_file_not_exists "after repair, the orphan is swept normally" "$(blob_of "$HS")"

echo ""
echo "test_attach_gc_manifest_blocking.sh: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
