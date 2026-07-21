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
# The install side is also POSITION-SENSITIVE (t1197): because the cleanup in (1)
# runs mid-main(), an installer wired after it is dead code in a real install.
# The derivation counts only calls that precede the cleanup, so such an installer
# is reported rather than silently accepted.
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

# WIRING_SRC — shell source eval'd inside BOTH derivation subprocesses. They are
# separate processes, so a shared bash function is the only way to keep the two
# wiring checks from drifting apart, which is the very failure mode this guard
# exists to catch.
#
# Call POSITION is part of the wiring contract (t1197). main() runs
# `rm -rf "$INSTALL_DIR/seed"` once the seed installers are done, so an installer
# wired AFTER that line delivers nothing in a real tarball install — yet a
# position-blind name match accepts it anyway, because the test fixture still has
# a populated seed/ when the derivation calls the function directly. Everything
# below therefore keys on the cleanup line as an anchor and counts only the calls
# that precede it.
WIRING_SRC="$(cat <<'SRC'
# Rendered verbatim by `declare -f main` as `    rm -rf "$INSTALL_DIR/seed";`.
# (main()'s only other `rm -rf` is the tmpdir trap, which does not match.)
SEED_CLEANUP_ANCHOR='rm -rf "$INSTALL_DIR/seed"'

# require_anchor <who> <body> — fail loudly when the anchor is gone. Falling back
# to scanning the whole body would silently restore the position-blind match the
# moment install.sh reworded that line.
require_anchor() {
    [[ "$2" == *"$SEED_CLEANUP_ANCHOR"* ]] && return 0
    printf '%s: seed-cleanup anchor not found in main() body\n' "$1" >&2
    return 3
}

# Plain bash prefix/suffix removal, not sed: no escaping of the `$` and `/` in
# the anchor, and no BSD-vs-GNU divergence (aidocs/framework/sed_macos_issues.md).
main_body_before_cleanup() {
    require_anchor main_body_before_cleanup "$1" || return 3
    printf '%s' "${1%%"$SEED_CLEANUP_ANCHOR"*}"
}
main_body_after_cleanup() {
    require_anchor main_body_after_cleanup "$1" || return 3
    printf '%s' "${1#*"$SEED_CLEANUP_ANCHOR"}"
}

# splice_probe_wiring <body> <wiring> <pre|post> — insert a synthetic call site on
# the requested side of the cleanup anchor, modelling a newly wired installer.
splice_probe_wiring() {
    local head tail
    require_anchor splice_probe_wiring "$1" || return 3
    head="${1%%"$SEED_CLEANUP_ANCHOR"*}"
    tail="${1#*"$SEED_CLEANUP_ANCHOR"}"
    case "$3" in
        pre)  printf '%s' "$head$2$SEED_CLEANUP_ANCHOR$tail" ;;
        post) printf '%s' "$head$SEED_CLEANUP_ANCHOR$2$tail" ;;
        *)    printf 'splice_probe_wiring: bad position: %s\n' "$3" >&2; return 3 ;;
    esac
}

# calls_installer <body> <fn> — is <fn> invoked at COMMAND POSITION in <body>?
# `declare -f` pretty-prints one command per line, so command position is a line
# start or a spot right after `;` `&&` `||` `|` `{` `(`. A bare name match would
# also count a mention inside a string, e.g. info "about to run install_seed_x".
# Residual limitation, accepted: a mention inside a single-line string that
# itself follows one of those separators still matches. Errors here fail LOUD —
# a missed call is reported as unwired, never silently accepted.
calls_installer() {
    grep -qE "(^|[;&|{(])[[:space:]]*$2([^[:alnum:]_]|$)" <<< "$1"
}

all_installers() { declare -F | awk '{print $3}' | grep '^install_seed_'; }

# wired_installers <body> — installers called BEFORE the seed cleanup.
wired_installers() {
    local pre fn
    pre="$(main_body_before_cleanup "$1")" || return 3
    for fn in $(all_installers); do
        calls_installer "$pre" "$fn" && printf '%s\n' "$fn"
    done
    return 0
}

# postcleanup_installers <body> — installers called ONLY after the cleanup: the
# position defect itself. Powers the developer-facing failure diagnostics.
postcleanup_installers() {
    local pre post fn
    pre="$(main_body_before_cleanup "$1")" || return 3
    post="$(main_body_after_cleanup "$1")" || return 3
    for fn in $(all_installers); do
        calls_installer "$pre" "$fn" && continue
        calls_installer "$post" "$fn" && printf '%s\n' "$fn"
    done
    return 0
}
SRC
)"

# derive_install_manifest <fixture> [probe_fn_src] [probe_wiring] [probe_position]
#
# Runs the installers main() ACTUALLY CALLS BEFORE THE SEED CLEANUP: the
# install_seed_* functions whose call site appears, at command position, in the
# pre-cleanup portion of `declare -f main`. `declare -f` reproduces the parsed
# function without comments, so this is a true call-site check — an installer
# that exists but was never wired, or was wired too late, contributes nothing,
# which is right, because a real tarball install would not deliver its file
# either.
#
# probe_fn_src defines a synthetic installer and MUST NOT redefine main() —
# doing so would clobber the real one and collapse the wired set to the probe
# alone — EXCEPT in the Test 11 anchor controls, which redefine it deliberately
# to exercise the missing-anchor path. The synthetic CALL SITE is supplied
# separately via probe_wiring and spliced into the real main() body on the
# probe_position side (`pre`, the default, or `post`) of the cleanup anchor,
# modelling "real main() plus one newly wired installer".
#
# On failure the manifest is the poison line DERIVATION_FAILED — never an empty
# or partial snapshot, which would read as ordinary drift — and the subprocess
# stderr is surfaced rather than discarded.
derive_install_manifest() {
    local fixture="$1" probe_fn_src="${2:-}" probe_wiring="${3:-}" probe_position="${4:-pre}"
    local errf="$TESTROOT/derive_err.$$" rc
    bash -c '
        set -uo pipefail
        source "$1/install.sh" --source-only
        eval "$5"
        INSTALL_DIR="$2"
        [[ -n "$3" ]] && eval "$3"
        create_data_dirs
        main_body="$(declare -f main)"
        if [[ -n "$4" ]]; then
            main_body="$(splice_probe_wiring "$main_body" "$4" "$6")" || exit 3
        fi
        # Capture first, then check: `for fn in $(wired_installers ...)` would
        # swallow a nonzero status into a harmless empty loop.
        wired="$(wired_installers "$main_body")" || exit 3
        for fn in $wired; do "$fn"; done
        exit 0
    ' _ "$PROJECT_DIR" "$fixture" "$probe_fn_src" "$probe_wiring" "$WIRING_SRC" \
      "$probe_position" >/dev/null 2>"$errf"
    rc=$?
    if (( rc != 0 )); then
        echo "derive_install_manifest: derivation subprocess failed (rc=$rc)" >&2
        cat "$errf" >&2
        rm -f "$errf"
        echo "DERIVATION_FAILED"
        return "$rc"
    fi
    rm -f "$errf"
    snapshot "$fixture"
}

# list_unwired_installers [probe_fn_src] [probe_wiring] [probe_position] — every
# install_seed_* NOT called before the seed cleanup. Catches the two cases a
# wired-set-derived manifest cannot see on its own: an installer added and paired
# with a setup entry but never called, and one called too late to matter.
list_unwired_installers() { _installer_wiring_report unwired "$@"; }

# list_postcleanup_installers [...] — the subset of the above that IS called, but
# only after the cleanup. Names the position defect in failure diagnostics.
list_postcleanup_installers() { _installer_wiring_report postcleanup "$@"; }

_installer_wiring_report() {
    local mode="$1" probe_fn_src="${2:-}" probe_wiring="${3:-}" probe_position="${4:-pre}"
    local errf="$TESTROOT/wiring_err.$$" out rc
    out="$(bash -c '
        set -uo pipefail
        source "$2/install.sh" --source-only >/dev/null 2>&1
        eval "$5"
        [[ -n "$3" ]] && eval "$3"
        main_body="$(declare -f main)"
        if [[ -n "$4" ]]; then
            main_body="$(splice_probe_wiring "$main_body" "$4" "$6")" || exit 3
        fi
        if [[ "$1" == postcleanup ]]; then
            postcleanup_installers "$main_body" || exit 3
        else
            wired="$(wired_installers "$main_body")" || exit 3
            for fn in $(all_installers); do
                grep -qx "$fn" <<< "$wired" || echo "$fn"
            done
        fi
        exit 0
    ' _ "$mode" "$PROJECT_DIR" "$probe_fn_src" "$probe_wiring" "$WIRING_SRC" \
      "$probe_position" 2>"$errf")"
    rc=$?
    if (( rc != 0 )); then
        echo "_installer_wiring_report($mode): subprocess failed (rc=$rc)" >&2
        cat "$errf" >&2
        rm -f "$errf"
        echo "ANCHOR_MISSING"
        return 0
    fi
    rm -f "$errf"
    [[ -z "$out" ]] && return 0
    sort <<< "$out"
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
install_rc=$?
derive_setup_manifest   "$(make_fixture live_s)" > "$TESTROOT/m_setup"

TOTAL=$((TOTAL + 1))
if (( install_rc != 0 )); then
    # The install-side derivation itself failed, so there is no manifest to
    # compare. Report that, and do NOT run the comparison: a poisoned manifest
    # against the full setup manifest would dress one broken derivation up as
    # dozens of unrelated SETUP_ONLY findings and bury the real diagnostic.
    echo "  FAIL: T2: install-side derivation failed (rc=$install_rc) — see the"
    echo "    diagnostic above; drift comparison skipped (no manifest to compare)."
    echo "    Most likely the seed-cleanup anchor moved or was reworded: the guard"
    echo "    keys on the literal 'rm -rf \"\$INSTALL_DIR/seed\"' line in main()."
    FAIL=$((FAIL + 1))
elif drift="$(compare_manifests "$TESTROOT/m_install" "$TESTROOT/m_setup")"; then
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
    echo "      ...or it IS defined and called, but AFTER that cleanup, which"
    echo "      delivers nothing in a real install. Called post-cleanup:"
    # ANCHOR_MISSING means the wiring check itself could not run — its own
    # diagnostic was already printed to stderr; do not restate it as a finding.
    pc2="$(list_postcleanup_installers)"
    [[ "$pc2" == ANCHOR_MISSING ]] && pc2=""
    echo "        ${pc2:-(none)}"
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

# --- Test 6: every installer that exists is wired into main(), in time ---
echo "--- Test 6: every install_seed_* is called before the seed cleanup ---"
unwired="$(list_unwired_installers)"
TOTAL=$((TOTAL + 1))
if [[ -z "$unwired" ]]; then
    echo "  PASS: T6: all install_seed_* functions are wired into main()"
    PASS=$((PASS + 1))
else
    echo "  FAIL: T6: install_seed_* not called from main() before the cleanup:"
    while IFS= read -r line; do echo "    $line"; done <<< "$unwired"
    # ANCHOR_MISSING means the wiring check itself could not run — its own
    # diagnostic was already printed to stderr; do not restate it as a finding.
    pc6="$(list_postcleanup_installers)"
    if [[ -n "$pc6" && "$pc6" != ANCHOR_MISSING ]]; then
        echo "    Of these, called only AFTER 'rm -rf \$INSTALL_DIR/seed' — too"
        echo "    late to deliver anything in a real install:"
        while IFS= read -r line; do echo "      $line"; done <<< "$pc6"
    fi
    echo "    Define install_seed_<x>() AND call it from main(), BEFORE the"
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

# --- Test 9: call POSITION decides the manifest (t1197) ---
# One probe, two wiring positions, opposite verdicts. The setup side needs no
# synthetic code: the real *_instructions.seed.md glob in
# populate_data_branch_seed_metadata already delivers the probe seed, so
# $TESTROOT/m_setup_probe (built in Test 4) is the matching setup manifest.
echo "--- Test 9: negative control — post-cleanup wiring is caught (t1197) ---"
# shellcheck disable=SC2016  # deliberate: the probe body is eval'd in the
# derivation subprocess, where INSTALL_DIR is set — it must NOT expand here.
POS_PROBE_FN='install_seed_postcleanup_probe() { cp "$INSTALL_DIR/seed/probe_instructions.seed.md" "$INSTALL_DIR/aitasks/metadata/probe_instructions.seed.md"; }'
POS_PROBE_CALL=$'\n    install_seed_postcleanup_probe\n'

FX9A="$(make_fixture pos_pre)"
printf '# probe\n' > "$FX9A/seed/probe_instructions.seed.md"
derive_install_manifest "$FX9A" "$POS_PROBE_FN" "$POS_PROBE_CALL" pre > "$TESTROOT/m_install_pos_pre"

FX9B="$(make_fixture pos_post)"
printf '# probe\n' > "$FX9B/seed/probe_instructions.seed.md"
derive_install_manifest "$FX9B" "$POS_PROBE_FN" "$POS_PROBE_CALL" post > "$TESTROOT/m_install_pos_post"

drift9_pre="$(compare_manifests "$TESTROOT/m_install_pos_pre" "$TESTROOT/m_setup_probe")" || true
assert_eq "T9: pre-cleanup wiring still counts (truncation did not cut too early)" \
    "" "$drift9_pre"

drift9_post="$(compare_manifests "$TESTROOT/m_install_pos_post" "$TESTROOT/m_setup_probe")" || true
assert_eq "T9: post-cleanup wiring is reported as drift, and is the only drift" \
    "SETUP_ONLY:probe_instructions.seed.md" "$drift9_post"
assert_contains "T9: real installers still contributed (post leg)" \
    "codex_config.seed.toml" "$(cat "$TESTROOT/m_install_pos_post")"

echo ""

# --- Test 10: the wiring surface honours position too (t1197) ---
echo "--- Test 10: negative control — list_unwired_installers sees position ---"
assert_eq "T10: pre-cleanup wiring is not reported as unwired" \
    "" "$(list_unwired_installers "$POS_PROBE_FN" "$POS_PROBE_CALL" pre)"
assert_eq "T10: post-cleanup wiring is reported, and nothing else" \
    "install_seed_postcleanup_probe" \
    "$(list_unwired_installers "$POS_PROBE_FN" "$POS_PROBE_CALL" post)"
assert_eq "T10: ...and is named as a POSITION defect, not a missing call" \
    "install_seed_postcleanup_probe" \
    "$(list_postcleanup_installers "$POS_PROBE_FN" "$POS_PROBE_CALL" post)"

# A name mentioned only inside a pre-cleanup string is not a call site.
assert_eq "T10: a string mention is not a call site" \
    "install_seed_mention_probe" \
    "$(list_unwired_installers 'install_seed_mention_probe() { :; }' \
        $'\n    info "about to run install_seed_mention_probe";\n' pre)"

echo ""

# --- Test 11: a missing cleanup anchor fails loudly (t1197) ---
# The direct helper controls alone are not enough: a wrapper that ignores the
# subprocess status would still degrade into an empty or broad drift result
# instead of a diagnostic — which is exactly what a reworded cleanup line would
# cause. So both real guard paths are driven end to end as well.
echo "--- Test 11: missing seed-cleanup anchor fails loudly (t1197) ---"
ANCHORLESS_MAIN='main() { install_seed_task_types; }'

out11a="$(bash -c 'eval "$1"; main_body_before_cleanup "$2"' _ "$WIRING_SRC" "$ANCHORLESS_MAIN" 2>&1)"
rc11a=$?
assert_eq "T11a: main_body_before_cleanup exits 3 without the anchor" "3" "$rc11a"
assert_contains "T11a: ...and names the missing anchor" "anchor not found" "$out11a"

out11b="$(bash -c 'eval "$1"; splice_probe_wiring "$2" "x" pre' _ "$WIRING_SRC" "$ANCHORLESS_MAIN" 2>&1)"
rc11b=$?
assert_eq "T11b: splice_probe_wiring exits 3 without the anchor" "3" "$rc11b"
assert_contains "T11b: ...and names the missing anchor" "anchor not found" "$out11b"

out11c="$(derive_install_manifest "$(make_fixture anchorless)" "$ANCHORLESS_MAIN" 2>&1)"
rc11c=$?
assert_eq "T11c: derive_install_manifest propagates the failure" "3" "$rc11c"
assert_contains "T11c: ...poisons the manifest instead of snapshotting" \
    "DERIVATION_FAILED" "$out11c"
assert_contains "T11c: ...and surfaces the diagnostic" "anchor not found" "$out11c"

out11d="$(list_unwired_installers "$ANCHORLESS_MAIN" 2>&1)"
assert_contains "T11d: list_unwired_installers reports ANCHOR_MISSING" \
    "ANCHOR_MISSING" "$out11d"
assert_contains "T11d: ...and surfaces the diagnostic" "anchor not found" "$out11d"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
[[ $FAIL -eq 0 ]]
