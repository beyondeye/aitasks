#!/usr/bin/env bash
# test_artifact_fold_transfer.sh - fold transfer of `artifacts:` frontmatter
# entries (t1076_2). Folding A into B must merge A's handle-only artifact
# entries into B (dedupe by handle — handles are the identity; no ledger
# rebind, manifests are handle-keyed). Also regression-checks that the mixed
# attachments+artifacts fold still rebinds attachment refs, and that the
# Step 5b detection extension is load-bearing (artifacts-only folds trigger
# the transfer; bare folds still skip it).
# Legacy-mode git fixture (no .aitask-data -> task_git is plain git in cwd).
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ART="$PROJECT_DIR/.aitask-scripts/aitask_artifact.sh"
ATT="$PROJECT_DIR/.aitask-scripts/aitask_attach.sh"
FOLD="$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh"
META="$PROJECT_DIR/.aitask-scripts/lib/attachment_meta.py"
PY="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; resolve_python)"
FMP="$PROJECT_DIR/.aitask-scripts/lib/frontmatter_patch.py"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export XDG_CACHE_HOME="$TMP/xdg"
REPO="$TMP/repo"; mkdir -p "$REPO/aitasks/metadata"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/yaml_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_utils.sh"

mk_task() {
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s body.\n' "$1" > "aitasks/$1.md"
}

meta_refs() { "$PY" "$META" --meta-dir attachments/meta refs "$1" | paste -sd, -; }
handles_of() { read_yaml_mappings "aitasks/$1.md" artifacts | grep '^handle=' | sed 's/^handle=//' | paste -sd, -; }

mk_task t20_primary; mk_task t21_folded      # A: basic artifact transfer
mk_task t22_primary; mk_task t23_folded      # B: dedupe by handle
mk_task t24_primary; mk_task t25_folded      # C: mixed attachments + artifacts
mk_task t26_primary; mk_task t27_folded      # D: bare fold (negative control)
git add -A; git commit -q -m init

printf 'artifact one\n'   > a1.bin
printf 'artifact two\n'   > a2.bin
printf 'attachment one\n' > att1.bin; HATT="$(artifact_sha256 att1.bin)"

# ── A. Artifacts-only fold: entry transferred (detection is load-bearing) ────
"$ART" create 21 a1.bin --kind report --handle art:t21-rep --name "folded rep" >/dev/null 2>&1
"$FOLD" --commit-mode fresh 20 21 >/dev/null 2>&1
assert_eq "primary gains the folded artifact entry" "art:t21-rep" "$(handles_of t20_primary)"
recs="$(read_yaml_mappings aitasks/t20_primary.md artifacts)"
assert_contains "kind transferred" "kind=report" "$recs"
assert_contains "name transferred" "name=folded rep" "$recs"
assert_file_exists "manifest untouched by fold (handle-keyed)" "artifacts/manifests/t21-rep.json"

# ── B. Dedupe: primary already lists the handle -> no duplicate entry ────────
"$ART" create 23 a2.bin --kind report --handle art:t23-rep >/dev/null 2>&1
"$PY" "$FMP" append aitasks/t22_primary.md artifacts "handle=art:t23-rep" "kind=report"
git add aitasks/t22_primary.md; git commit -q -m "primary already lists the handle"
"$FOLD" --commit-mode fresh 22 23 >/dev/null 2>&1
n_entries="$(read_yaml_mappings aitasks/t22_primary.md artifacts | grep -c '^handle=' || true)"
assert_eq "no duplicate entry when primary already lists the handle" "1" "$n_entries"

# ── C. Mixed fold: artifacts transfer AND attachment rebind (regression) ─────
"$ATT" add 25 att1.bin --name att1.bin >/dev/null 2>&1
"$ART" create 25 a1.bin --kind mockup --handle art:t25-mock >/dev/null 2>&1
"$FOLD" --commit-mode fresh 24 25 >/dev/null 2>&1
assert_eq "mixed fold transfers the artifact entry" "art:t25-mock" "$(handles_of t24_primary)"
assert_eq "mixed fold still rebinds the attachment ref" "24" "$(meta_refs "$HATT")"
assert_contains "mixed fold merges the attachment frontmatter" "att1.bin" "$("$ATT" ls 24 2>&1)"

# ── D. Bare fold (negative control): Step 5b body skipped, fold still works ──
"$FOLD" --commit-mode fresh 26 27 >/dev/null 2>&1
assert_eq "bare fold: primary has no artifacts" "" "$(handles_of t26_primary)"
assert_eq "bare fold marks folded_into" "folded_into: 26" "$(grep '^folded_into:' aitasks/t27_folded.md)"

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
