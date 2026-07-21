#!/usr/bin/env bash
set -euo pipefail

# Delivery + content contract for aitasks/metadata/crew_runner_config.yaml (t1196).
#
# WHY THIS FILE EXISTS AS ITS OWN HARNESS
#
# 1. It runs the REAL install.sh, not a sourced installer function.
#    aidocs/framework/aitasks_extension_points.md ("Test the full install flow
#    for setup helpers") requires that a setup helper touching aitasks/metadata/
#    be exercised through the actual `install.sh -> ait setup` flow in a scratch
#    dir, because install.sh DELETES seed/ at the end of install: a helper
#    reading `$project_dir/seed/...` passes every hand-crafted-fixture test and
#    still silently no-ops on a fresh user install. tests/test_seed_manifest_drift.sh
#    (t1194) derives its manifests by SOURCING installer functions against a
#    fixture that still has seed/, so by construction it cannot cover the
#    post-cleanup state. Test 2/3 below install for real and then hand off to the
#    setup helper on that post-install repo.
#
# 2. It has a working exit path. These checks deliberately do NOT live in
#    tests/test_crew_runner.sh: that script's footer reads a file-backed
#    COUNTER_FILE that the shared asserts.sh helpers never write, so it prints
#    `FAIL:` lines and still exits 0 — a regression there would be invisible to
#    CI. (Pre-existing defect, logged separately.) Every assertion here is at top
#    level, mutating the PASS/FAIL counters that the `[[ $FAIL -eq 0 ]]` footer
#    actually reads.
#
# THE CONTRACT UNDER TEST
#
# The shipped template must declare NO active override, so DEFAULT_INTERVAL /
# DEFAULT_MAX_CONCURRENT in agentcrew_runner.py stay the single source of truth
# for those values. Manifest parity (t1194) only proves both delivery paths ship
# a file BY NAME — uncommenting a key would satisfy parity while silently
# promoting the seed to the effective default.
#
# ensure_crew_runner_config()'s early exits must also be explicit `return 0`: it
# runs at top level in aitask_setup.sh's main() under `set -euo pipefail`, and
# the seedless path is the COMMON case (every tarball install), so a bare
# `return` after a failed `[[ -f ]]` would abort the whole `ait setup` run. Same
# hazard class as t1193.

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

SEED_TEMPLATE="$PROJECT_DIR/seed/crew_runner_config.yaml"
METADATA_REL="aitasks/metadata/crew_runner_config.yaml"

TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

# Same resolution as tests/test_crew_runner.sh — the framework venv when present.
PYTHON="python3"
if [[ -x "$HOME/.aitask/venv/bin/python" ]]; then
    PYTHON="$HOME/.aitask/venv/bin/python"
fi

# assert_same_as_template — single-use here, stays inline (see asserts.sh header).
assert_same_as_template() {
    local desc="$1" file="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$file" ]] && diff -q "$SEED_TEMPLATE" "$file" > /dev/null 2>&1; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc"
        echo "    '$file' is missing or differs from $SEED_TEMPLATE"
        FAIL=$((FAIL + 1))
    fi
}

# resolve_cfg <repo_dir> — what the runner resolves with no CLI args, from that
# repo. agentcrew_runner.py reads CONFIG_FILE relative to cwd, hence the subshell
# cd. Output is captured, so the assertions stay at top level where the counters
# are visible.
resolve_cfg() {
    (
        cd "$1" || exit 1
        PYTHONPATH=".aitask-scripts" $PYTHON -c "
from agentcrew.agentcrew_runner import resolve_config
print(resolve_config(None, None))
" 2>/dev/null
    )
}

echo "=== crew_runner_config.yaml delivery + content contract (t1196) ==="
echo ""

# ---------------------------------------------------------------------------
# Test 1 — the template itself declares no active override
# ---------------------------------------------------------------------------
# Guarding the seed guards both delivered copies: install_seed_crew_runner_config()
# and populate_data_branch_seed_metadata() both `cp` it verbatim (asserted below).
#
# `yaml.safe_load` on a comment-only document returns None, NOT {}, so coalesce
# exactly as agentcrew_utils.read_yaml does before subscripting — a bare .get()
# would raise AttributeError and fail this test while the behavior it guards is
# perfectly correct.
echo "--- Test 1: shipped template declares no active override ---"
active_keys="$($PYTHON -c "
import yaml
cfg = yaml.safe_load(open('$SEED_TEMPLATE')) or {}
print(','.join(k for k in ('interval', 'max_concurrent') if k in cfg))
" 2>/dev/null)"
assert_eq "T1: no active interval/max_concurrent in the template" "" "$active_keys"

echo ""

# ---------------------------------------------------------------------------
# Test 2 — the REAL install.sh flow
# ---------------------------------------------------------------------------
echo "--- Test 2: real install.sh delivers the template (local tarball) ---"

TARBALL="$TESTROOT/aitasks_test.tar.gz"
(
    cd "$PROJECT_DIR"
    tar czf "$TARBALL" \
        .aitask-scripts/ \
        ait \
        packaging/ \
        seed/ \
        aitasks/metadata/labels.txt \
        aitasks/metadata/task_types.txt \
        aitasks/metadata/profiles/ \
        2>/dev/null
) || true

INSTALLED="$TESTROOT/installed"
mkdir -p "$INSTALLED"
(
    cd "$INSTALLED"
    git init --quiet -b main
    git config user.email "test@test.com"
    git config user.name "Test User"
    git config commit.gpgsign false
    echo "# test project" > README.md
    git add README.md
    git commit -q -m "Initial commit"
) > /dev/null 2>&1

bash "$PROJECT_DIR/install.sh" --dir "$INSTALLED" --local-tarball "$TARBALL" \
    < /dev/null > "$TESTROOT/install.log" 2>&1
install_rc=$?
assert_eq "T2: install.sh exits 0" "0" "$install_rc"
assert_same_as_template "T2: install delivers the template verbatim" \
    "$INSTALLED/$METADATA_REL"

# The precondition every later test depends on: install.sh really did delete
# seed/. If this ever stops holding, Test 3's seedless assertions become vacuous.
assert_file_not_exists "T2: install.sh deleted seed/ (seedless precondition)" \
    "$INSTALLED/seed"

# Behavioral ground truth, against the ACTUALLY INSTALLED file rather than a
# hand-copied fixture: it must resolve to exactly what the absent-file path
# resolves to.
assert_eq "T2: installed template -> built-in defaults" "(30, 3)" "$(resolve_cfg "$INSTALLED")"

rm -f "$INSTALLED/$METADATA_REL"
assert_eq "T2: no config at all -> the same built-in defaults" \
    "(30, 3)" "$(resolve_cfg "$INSTALLED")"

# Negative control. Without it, both assertions above would also pass if the
# runner never read the file (wrong path, wrong cwd) — they would return the
# defaults for the wrong reason. An uncommented key must actually win.
cp "$SEED_TEMPLATE" "$INSTALLED/$METADATA_REL"
printf 'interval: 45\n' >> "$INSTALLED/$METADATA_REL"
assert_eq "T2: an uncommented key overrides the built-in default" \
    "(45, 3)" "$(resolve_cfg "$INSTALLED")"
cp "$SEED_TEMPLATE" "$INSTALLED/$METADATA_REL"

echo ""

# ---------------------------------------------------------------------------
# Test 3 — the install.sh -> ait setup handoff, on the real post-install repo
# ---------------------------------------------------------------------------
# This is the flow aitasks_extension_points.md mandates: not a hand-crafted seed
# fed to the helper, but the helper running against a genuinely seedless repo
# produced by a real install.
echo "--- Test 3: setup helper on the real post-install (seedless) repo ---"

run_ensure() {   # run_ensure <project_dir> — under errexit, as main() runs it
    bash -c '
        set -euo pipefail
        source "$1/.aitask-scripts/aitask_setup.sh" --source-only
        SCRIPT_DIR="$2/.aitask-scripts"
        ensure_crew_runner_config
        echo REACHED_NEXT_STEP
    ' _ "$PROJECT_DIR" "$1" 2>/dev/null
}

# 3a: the ordinary post-install state — config present, seed/ gone. The helper
# must be a clean no-op here. (Note this leg does NOT catch a bare `return` on
# the first guard: when the target exists, `[[ -f x ]] && return` returns the
# successful test's status, i.e. 0. The `return 0` there is defensive; 3c below
# is the leg that actually catches the errexit hazard.)
assert_contains "T3a: setup continues past the helper on a seedless repo" \
    "REACHED_NEXT_STEP" "$(run_ensure "$INSTALLED")"

# 3b: the install-delivered file is never clobbered by the later setup pass.
assert_same_as_template "T3b: installed file left untouched by the setup pass" \
    "$INSTALLED/$METADATA_REL"

# 3c: TWO contracts in one leg.
#   (i) The errexit hazard this harness exists for: with both the target and
#       seed/ absent, `[[ -f "$seed_config" ]] || return` propagates status 1,
#       and at main()'s top level under `set -e` that takes the whole `ait setup`
#       run down — for every tarball-installed repo, the common case. Verified:
#       reintroducing the bare `return` fails exactly this assertion.
#  (ii) The DOCUMENTED RESIDUAL, pinned rather than left as prose. With seed/
#       gone the helper cannot restore a deleted config — `ait setup` alone is
#       not the repair path for tarball installs; `ait upgrade` (which re-runs
#       install.sh) is.
rm -f "$INSTALLED/$METADATA_REL"
assert_contains "T3c: seedless helper still exits cleanly with nothing to copy" \
    "REACHED_NEXT_STEP" "$(run_ensure "$INSTALLED")"
assert_file_not_exists "T3c: ...and cannot restore the file without seed/" \
    "$INSTALLED/$METADATA_REL"

echo ""

# ---------------------------------------------------------------------------
# Test 4 — the source-tree / clean-clone path (seed/ survives)
# ---------------------------------------------------------------------------
echo "--- Test 4: source-tree repo (seed/ present) ---"

SRCTREE="$TESTROOT/srctree"
mkdir -p "$SRCTREE/.aitask-scripts" "$SRCTREE/aitasks/metadata" "$SRCTREE/seed"
cp "$SEED_TEMPLATE" "$SRCTREE/seed/"

assert_contains "T4: helper runs cleanly under errexit" \
    "REACHED_NEXT_STEP" "$(run_ensure "$SRCTREE")"
assert_same_as_template "T4: template populated verbatim from seed/" \
    "$SRCTREE/$METADATA_REL"

# No-clobber: a user customization must survive a later `ait setup`.
printf 'interval: 99\n' > "$SRCTREE/$METADATA_REL"
assert_contains "T4: re-run is clean" "REACHED_NEXT_STEP" "$(run_ensure "$SRCTREE")"
assert_eq "T4: user customization preserved byte-for-byte" \
    "interval: 99" "$(cat "$SRCTREE/$METADATA_REL")"

# The data-branch initializer is the other setup-side delivery path (the one
# t1194's manifest parity derives). Assert it ships the template verbatim too.
DATABRANCH="$TESTROOT/databranch"
mkdir -p "$DATABRANCH/metadata"
bash -c '
    set -uo pipefail
    source "$1/.aitask-scripts/aitask_setup.sh" --source-only
    populate_data_branch_seed_metadata "$1/seed" "$2/metadata" "$1/.aitask-scripts/gates_reference.yaml"
' _ "$PROJECT_DIR" "$DATABRANCH" > /dev/null 2>&1
assert_same_as_template "T4: data-branch initializer ships it verbatim" \
    "$DATABRANCH/metadata/crew_runner_config.yaml"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
[[ $FAIL -eq 0 ]]
