#!/usr/bin/env bash
set -euo pipefail

# Seed manifest drift guard (t1194).
#
# aitasks/metadata/ has two MUTUALLY EXCLUSIVE delivery paths:
#
#   1. install.sh's install_seed_*() family. It runs `rm -rf "$INSTALL_DIR/seed"`
#      once they are done, so in a tarball-installed project seed/ is gone and
#      every setup-side seed path below is dead — install.sh is the only source.
#   2. The framework source tree / clean clone, where install.sh never runs.
#      Delivery is the union of populate_data_branch_seed_metadata() (the
#      data-branch initializer) and ensure_agent_config_seeds() (t1185).
#
# A seed added to one side only drifts silently: install-flow users get the file
# and source-tree users do not, or vice versa. That is exactly the t1185 failure
# mode reproduced for a new file, so this guard asserts the two manifests agree.
#
# Both manifests are DERIVED FROM LIVE SOURCE — each script is sourced with its
# --source-only guard and its populate functions run against a throwaway
# fixture. Nothing here hardcodes an expected file list: a hardcoded list would
# just become a third manifest to drift.

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

# compare_manifests returns non-zero BY DESIGN (it is the guard's verdict), and
# the negative controls invoke it expecting failure — errexit would abort the
# run on the first intentional drift. Same relaxation as
# tests/test_setup_agent_config_seeds.sh.
set +eu

# ---------------------------------------------------------------------------
# Fixture + derivation helpers
# ---------------------------------------------------------------------------

# make_fixture <name> — a project dir carrying the real seed/ and the canonical
# gate reference, with an empty metadata dir for the populate pass to fill.
make_fixture() {
    local dir="$TESTROOT/$1"
    mkdir -p "$dir/.aitask-scripts" "$dir/aitasks/metadata"
    cp -r "$PROJECT_DIR/seed" "$dir/seed"
    cp "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml" "$dir/.aitask-scripts/"
    echo "$dir"
}

# snapshot <fixture> — the delivered metadata set, one metadata-relative path
# per line. `find -printf` is GNU-only (BSD/macOS find has no such primary), so
# the prefix is stripped with sed instead — see
# aidocs/framework/sed_macos_issues.md.
snapshot() {
    ( cd "$1" && find aitasks/metadata -type f 2>/dev/null \
        | sed 's#^aitasks/metadata/##' | sort )
}

# install.sh and aitask_setup.sh both define info/warn/die/success, so each
# derivation runs in its OWN process — they are never sourced into one shell.

# derive_install_manifest <fixture> [probe_fn_src] [probe_wiring]
#
# Runs the installers main() ACTUALLY CALLS: the install_seed_* functions
# intersected with the names appearing in `declare -f main`. `declare -f`
# reproduces the parsed function without comments, so this is a true call-site
# check — an installer that exists but was never wired contributes nothing,
# which is right, because a real tarball install would not deliver its file
# either.
#
# probe_fn_src defines a synthetic installer and MUST NOT redefine main() —
# doing so would clobber the real one and collapse the wired set to the probe
# alone. The synthetic CALL SITE is supplied separately via probe_wiring, a
# string appended to the real main() body, which models "real main() plus one
# newly wired installer".
derive_install_manifest() {
    local fixture="$1" probe_fn_src="${2:-}" probe_wiring="${3:-}"
    bash -c '
        set -uo pipefail
        source "$1/install.sh" --source-only
        INSTALL_DIR="$2"
        [[ -n "$3" ]] && eval "$3"
        create_data_dirs
        main_body="$(declare -f main)$4"
        for fn in $(declare -F | awk "{print \$3}" | grep "^install_seed_"); do
            grep -qE "(^|[^[:alnum:]_])${fn}([^[:alnum:]_]|$)" <<< "$main_body" || continue
            "$fn"
        done
    ' _ "$PROJECT_DIR" "$fixture" "$probe_fn_src" "$probe_wiring" >/dev/null 2>&1
    snapshot "$fixture"
}

# list_unwired_installers [probe_fn_src] — every install_seed_* NOT referenced
# in main(). Catches the case a wired-set-derived manifest cannot see on its
# own: an installer added and paired with a setup entry but never called.
list_unwired_installers() {
    local probe_fn_src="${1:-}"
    bash -c '
        set -uo pipefail
        source "$1/install.sh" --source-only >/dev/null 2>&1
        [[ -n "$2" ]] && eval "$2"
        main_body="$(declare -f main)"
        for fn in $(declare -F | awk "{print \$3}" | grep "^install_seed_"); do
            grep -qE "(^|[^[:alnum:]_])${fn}([^[:alnum:]_]|$)" <<< "$main_body" || echo "$fn"
        done
    ' _ "$PROJECT_DIR" "$probe_fn_src" 2>/dev/null | sort
}

# derive_setup_manifest <fixture> — the source-tree side: the data-branch
# initializer plus the t1185 populate-missing pass.
derive_setup_manifest() {
    local fixture="$1"
    bash -c '
        set -uo pipefail
        source "$1/.aitask-scripts/aitask_setup.sh" --source-only
        populate_data_branch_seed_metadata \
            "$2/seed" "$2/aitasks/metadata" "$2/.aitask-scripts/gates_reference.yaml"
        SCRIPT_DIR="$2/.aitask-scripts"
        ensure_agent_config_seeds
    ' _ "$PROJECT_DIR" "$fixture" >/dev/null 2>&1
    snapshot "$fixture"
}

# compare_manifests <install_list_file> <setup_list_file> — the oracle.
# Emits INSTALL_ONLY:<path> / SETUP_ONLY:<path>; returns 1 if either is present.
compare_manifests() {
    local only
    only="$(comm -23 "$1" "$2" | sed 's/^/INSTALL_ONLY:/')"
    only+=$'\n'"$(comm -13 "$1" "$2" | sed 's/^/SETUP_ONLY:/')"
    only="$(grep -E '^(INSTALL|SETUP)_ONLY:' <<< "$only" || true)"
    [[ -z "$only" ]] && return 0
    echo "$only"
    return 1
}

echo "=== Seed Manifest Drift Guard (t1194) ==="
echo ""

# --- Test 1: the oracle itself ---
echo "--- Test 1: compare_manifests detects drift in both directions ---"
printf 'a\nb\n' > "$TESTROOT/l_same_a"
printf 'a\nb\n' > "$TESTROOT/l_same_b"
printf 'a\nb\nextra_i\n' > "$TESTROOT/l_extra_i"
printf 'a\nb\nextra_s\n' > "$TESTROOT/l_extra_s"

out1="$(compare_manifests "$TESTROOT/l_same_a" "$TESTROOT/l_same_b")"; rc1=$?
assert_eq "T1: identical manifests report no drift" "0" "$rc1"
assert_eq "T1: identical manifests print nothing" "" "$out1"

out2="$(compare_manifests "$TESTROOT/l_extra_i" "$TESTROOT/l_same_b")"; rc2=$?
assert_eq "T1: install-side extra returns nonzero" "1" "$rc2"
assert_contains "T1: install-side extra is named" "INSTALL_ONLY:extra_i" "$out2"

out3="$(compare_manifests "$TESTROOT/l_same_a" "$TESTROOT/l_extra_s")"; rc3=$?
assert_eq "T1: setup-side extra returns nonzero" "1" "$rc3"
assert_contains "T1: setup-side extra is named" "SETUP_ONLY:extra_s" "$out3"

echo ""

# --- Test 2: live parity (the guard) ---
echo "--- Test 2: install.sh and the setup path deliver the same metadata set ---"
derive_install_manifest "$(make_fixture live_i)" > "$TESTROOT/m_install"
derive_setup_manifest   "$(make_fixture live_s)" > "$TESTROOT/m_setup"

drift="$(compare_manifests "$TESTROOT/m_install" "$TESTROOT/m_setup")" || true
TOTAL=$((TOTAL + 1))
if [[ -z "$drift" ]]; then
    echo "  PASS: T2: no drift between the two delivery paths"
    PASS=$((PASS + 1))
else
    echo "  FAIL: T2: seed manifest drift detected"
    while IFS= read -r line; do echo "    $line"; done <<< "$drift"
    echo "    INSTALL_ONLY => add it to the setup path:"
    echo "      .aitask-scripts/aitask_setup.sh populate_data_branch_seed_metadata()"
    echo "      or ensure_agent_config_seeds()"
    echo "    SETUP_ONLY   => add an install_seed_*() to install.sh AND call it"
    echo "      from main() before the 'rm -rf \$INSTALL_DIR/seed'"
    FAIL=$((FAIL + 1))
fi

# Sanity: the derivations produced something, so an empty-vs-empty comparison
# can never be mistaken for parity.
assert_contains "T2: install manifest is non-trivial" "task_types.txt" "$(cat "$TESTROOT/m_install")"
assert_contains "T2: setup manifest is non-trivial" "task_types.txt" "$(cat "$TESTROOT/m_setup")"

echo ""

# --- Test 3: negative control — a newly wired installer with no setup entry ---
# Simulates the exact future change the guard exists to catch. The real main()
# is left intact; only a synthetic call site is appended to it.
echo "--- Test 3: negative control — install-only drift is caught ---"
FX3="$(make_fixture probe_i)"
printf 'probe: 1\n' > "$FX3/seed/drift_probe.yaml"
# shellcheck disable=SC2016  # deliberate: the probe body is eval'd in the
# derivation subprocess, where INSTALL_DIR is set — it must NOT expand here.
derive_install_manifest "$FX3" \
    'install_seed_drift_probe() { cp "$INSTALL_DIR/seed/drift_probe.yaml" "$INSTALL_DIR/aitasks/metadata/drift_probe.yaml"; }' \
    $'\n    install_seed_drift_probe\n' > "$TESTROOT/m_install_probe"

drift3="$(compare_manifests "$TESTROOT/m_install_probe" "$TESTROOT/m_setup")" || true
assert_contains "T3: the unmatched seed is reported" "INSTALL_ONLY:drift_probe.yaml" "$drift3"
# Attribution: the real sequence must still have run. If a future change let the
# probe clobber main(), the drift would balloon into many unrelated lines.
assert_eq "T3: the probe is the ONLY drift (real main() still ran)" \
    "INSTALL_ONLY:drift_probe.yaml" "$drift3"
assert_contains "T3: real installers still contributed" \
    "codex_config.seed.toml" "$(cat "$TESTROOT/m_install_probe")"

echo ""

# --- Test 4: negative control — setup-only drift, no synthetic code ---
# The real *_instructions.seed.md glob in populate_data_branch_seed_metadata
# picks this up; install.sh has no matching installer.
echo "--- Test 4: negative control — setup-only drift is caught ---"
FX4="$(make_fixture probe_s)"
printf '# probe\n' > "$FX4/seed/probe_instructions.seed.md"
derive_setup_manifest "$FX4" > "$TESTROOT/m_setup_probe"

drift4="$(compare_manifests "$TESTROOT/m_install" "$TESTROOT/m_setup_probe")" || true
assert_eq "T4: the unmatched seed is reported (and is the only drift)" \
    "SETUP_ONLY:probe_instructions.seed.md" "$drift4"

echo ""

# --- Test 5: the non-identity rename t1185 introduced ---
echo "--- Test 5: claude_settings rename holds on both sides ---"
for side in install setup; do
    m="$(cat "$TESTROOT/m_$side")"
    assert_contains "T5: $side delivers the renamed metadata name" \
        "claude_settings.seed.json" "$m"
    assert_not_contains "T5: $side does not deliver the raw seed/ name" \
        "claude_settings.local.json" "$m"
done

echo ""

# --- Test 6: every installer that exists is wired into main() ---
echo "--- Test 6: no install_seed_* is defined but never called ---"
unwired="$(list_unwired_installers)"
TOTAL=$((TOTAL + 1))
if [[ -z "$unwired" ]]; then
    echo "  PASS: T6: all install_seed_* functions are wired into main()"
    PASS=$((PASS + 1))
else
    echo "  FAIL: T6: install_seed_* defined but never called from main():"
    while IFS= read -r line; do echo "    $line"; done <<< "$unwired"
    echo "    Define install_seed_<x>() AND call it from main(), before the"
    echo "    'rm -rf \$INSTALL_DIR/seed' cleanup."
    FAIL=$((FAIL + 1))
fi

echo ""

# --- Test 7: the wiring assertion actually fires ---
echo "--- Test 7: negative control — an unwired installer is reported ---"
unwired_probe="$(list_unwired_installers 'install_seed_unwired_probe() { :; }')"
assert_eq "T7: the unwired probe is reported, and nothing else" \
    "install_seed_unwired_probe" "$unwired_probe"

echo ""

# --- Test 8: the extracted helper's seed/gates independence (t1147) ---
echo "--- Test 8: populate_data_branch_seed_metadata seed/gates independence ---"

run_populate() {   # run_populate <dest> <seed_dir> <gates_ref>
    bash -c '
        set -uo pipefail
        source "$1/.aitask-scripts/aitask_setup.sh" --source-only
        populate_data_branch_seed_metadata "$3" "$2" "$4"
    ' _ "$PROJECT_DIR" "$@" >/dev/null 2>&1
}

# 8a: both present.
D8A="$TESTROOT/t8a"; mkdir -p "$D8A/metadata"
run_populate "$D8A/metadata" "$PROJECT_DIR/seed" "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml"
assert_eq "T8a: exits 0 with seed and gate reference present" "0" "$?"
assert_file_exists "T8a: seed metadata populated" "$D8A/metadata/task_types.txt"
assert_file_exists "T8a: gate registry populated" "$D8A/metadata/gates.yaml"

# 8b: seed absent, gate reference present — gates.yaml must STILL land (t1147).
D8B="$TESTROOT/t8b"; mkdir -p "$D8B/metadata"
run_populate "$D8B/metadata" "$TESTROOT/definitely-absent-seed" \
    "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml"
assert_eq "T8b: exits 0 with seed/ absent" "0" "$?"
assert_file_exists "T8b: gate registry copied despite absent seed/ (t1147)" \
    "$D8B/metadata/gates.yaml"
assert_file_not_exists "T8b: no seed metadata fabricated" "$D8B/metadata/task_types.txt"

# 8c: both absent — clean no-op.
D8C="$TESTROOT/t8c"; mkdir -p "$D8C/metadata"
run_populate "$D8C/metadata" "$TESTROOT/definitely-absent-seed" \
    "$TESTROOT/definitely-absent-gates.yaml"
assert_eq "T8c: exits 0 with both absent" "0" "$?"
assert_file_not_exists "T8c: no gate registry fabricated" "$D8C/metadata/gates.yaml"
assert_file_not_exists "T8c: no seed metadata fabricated" "$D8C/metadata/task_types.txt"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
[[ $FAIL -eq 0 ]]
