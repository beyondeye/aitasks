#!/usr/bin/env bash
# test_aitasks_home_unset_home.sh - the per-user framework root
# ($AITASKS_HOME, lib/aitasks_home.sh) with an unset or empty HOME (t2348).
#
# cron, systemd and `env -i` run with no HOME. Before t2347 the bash startup
# code survived that; lib/aitasks_home.sh still expanded $HOME at source time,
# so with neither AITASKS_HOME nor HOME:
#   HOME unset  -> "HOME: unbound variable" aborts aitask_testmap.sh,
#                  aitask_engine.sh, and install.sh's engine installer
#   HOME=""     -> a root-level default: /.aitasks/engine/... for the shim and
#                  the engine, and `ait engine home` reads /.aitask as the
#                  legacy root it would migrate
# It now refuses with one clear line. The paths that need no default root keep
# working with a blank HOME: the shim's AIT_TESTMAP_BIN override, an invalid
# AIT_ENGINE's USAGE answer, `ait engine --help`, and every engine verb given an
# explicit AITASKS_HOME (the engine's own HOME-derived paths, the registry and
# the legacy root, refuse only in the verbs that read them).
#
# Cases: N1 lib, N2 lib with an unassignable root (readonly), N3 engine
# installer (errexit off), S1-S7 shim, E1-E4 engine, plus a HOME-set control.
#
# --- SAFETY RULES (they also make the pre-fix control safe to run) ----------
# The pre-fix tree derives ABSOLUTE root-level paths from HOME="", and no
# scratch cwd contains those:
#   * Shim probe-safety. The old shim resolves /.aitasks/engine/{dev,v<V>}/
#     ait-testmap, and _tm_check_slot EXECUTES any executable found there
#     (`"$bin" version`). A shim run that could reach Tier 2/3 without an
#     explicit scratch AITASKS_HOME is therefore EITHER (a) an in-process
#     resolver call with _tm_check_slot redefined as a recorder that executes
#     nothing, OR (b) a CLI run with HOME ABSENT (the old shim aborts while
#     sourcing, before any probe). Unrestricted: the override (Tier 1), an
#     invalid AIT_ENGINE (answered before any slot), and an explicit scratch
#     AITASKS_HOME.
#   * Engine. With a blank HOME every engine call is one of --help, -h, `home`
#     with NO argument (report: lock-free, read-only), `home --bogus` (both the
#     old and the new code reject it during argument parsing, before any path
#     is read), `prune --dry-run`, or an unknown verb. `home --migrate` is NEVER
#     run here: on the old tree it would operate on /.aitask and could move
#     host files. File-move coverage lives in the scratch-HOME migration suite
#     (tests/test_aitasks_home.sh H*).
#   * Cases with a VALID scratch HOME (N2, S5-S7) derive only scratch paths. S5
#     still stubs the probe: a readonly empty AITASKS_HOME made an earlier draft
#     probe /engine/v<V>/ait-testmap.
#
# AITASKS_HOME_TEST_ROOT=<tree> points the cases at another checkout holding
# `.aitask-scripts` (default: this repository) - used for the pre-fix control.
#
# Run: bash tests/test_aitasks_home_unset_home.sh
#
# shellcheck disable=SC2016  # the single-quoted `bash -c` snippets must NOT
#                            # expand in this shell.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/run_tmpdir.sh"
run_tmpdir_init test_aitasks_home_unset_home
trap run_tmpdir_cleanup EXIT

TREE="${AITASKS_HOME_TEST_ROOT:-$PROJECT_DIR}"
S="$TREE/.aitask-scripts"
TEST_BASH="$(command -v bash)"
V="$(tr -d '\r\n' <"$S/VERSION")"

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ah_unset_home_XXXXXX")"
AH="$ROOT/ah"                 # an explicit AITASKS_HOME that is never created
STUB="$ROOT/stub_engine"      # the AIT_TESTMAP_BIN override target
PROBES="$ROOT/probes"         # the in-process slot-probe recorder's log
ENVSTUB="$ROOT/env_engine"    # an override that reports the root it inherited
SHOME="$ROOT/shome"           # a valid scratch HOME (S5-S7, N2)
mkdir -p "$SHOME"
printf '#!/bin/sh\necho "STUB:$*"\n' >"$STUB"
printf '#!/bin/sh\necho "AH=${AITASKS_HOME-unset} LOCK=${AITASKS_HOME_LOCK-unset}"\n' >"$ENVSTUB"
chmod +x "$STUB" "$ENVSTUB"

# run <home> [VAR=value ...] -- <argv...> — run argv in a clean env (env -i).
# <home>: absent | empty | <path>. Sets OUT, ERR and RC in THIS shell.
run() {
    local mode="$1"; shift
    local -a envs=("TMPDIR=${TMPDIR:-/tmp}")
    while [[ $# -gt 0 && "$1" != "--" ]]; do envs+=("$1"); shift; done
    shift
    case "$mode" in
        absent) ;;
        empty)  envs+=("HOME=") ;;
        *)      envs+=("HOME=$mode") ;;
    esac
    RC=0
    env -i PATH=/usr/bin:/bin "${envs[@]}" "$TEST_BASH" "$@" \
        >"$ROOT/out" 2>"$ROOT/err" </dev/null || RC=$?
    OUT="$(cat "$ROOT/out")"
    ERR="$(cat "$ROOT/err")"
}

# The in-process resolver (probe-safety form (a)): source the shim, replace the
# slot probe with a recorder that executes nothing, then resolve.
RESOLVE_SNIPPET='source "$1" --source-only
_tm_check_slot() { printf "PROBE:%s\n" "$1" >>"$PROBES"; return 1; }
rc=0; testmap_resolve_engine 2>/dev/null || rc=$?
echo "RC=$rc"; echo "ERR=$TESTMAP_ENGINE_ERROR"; echo "SURVIVED"'

HOME_UNSET_TOKEN="ENGINE_HOME_UNSET:AITASKS_HOME|set AITASKS_HOME, or a non-empty HOME"
USAGE_TOKEN="USAGE:AIT_ENGINE must be 'dev' or unset"

for mode in absent empty; do
    # --- N1: the lib, neither AITASKS_HOME nor HOME -------------------------
    # set -u as every real sourcer has it; -e off so the status is printable.
    run "$mode" -- -c 'set -u; source "$1/lib/aitasks_home.sh"; echo "RC=$?"
        echo "REASON=${AITASKS_HOME_REFUSAL-unset}"
        echo "AH=${AITASKS_HOME-unset}"; echo "LOADED=${_AITASKS_HOME_LOADED-unset}"
        declare -F aitasks_engine_dir >/dev/null && echo HAS_FN; echo END' _ "$S"
    assert_contains "N1[$mode] source returns 1" "RC=1" "$OUT"
    assert_contains "N1[$mode] refusal reason home-unset" "REASON=home-unset" "$OUT"
    assert_contains "N1[$mode] AITASKS_HOME stays unset" "AH=unset" "$OUT"
    assert_contains "N1[$mode] loaded flag stays unset (re-source re-checks)" "LOADED=unset" "$OUT"
    assert_not_contains "N1[$mode] aitasks_engine_dir not defined" "HAS_FN" "$OUT"
    assert_contains "N1[$mode] message names AITASKS_HOME" "AITASKS_HOME is unset" "$ERR"
    assert_contains "N1[$mode] message names HOME" "HOME is unset or empty" "$ERR"
    assert_not_contains "N1[$mode] no unbound-variable abort" "unbound variable" "$ERR"

    run "$mode" "AITASKS_HOME=$AH" -- -c 'set -u; source "$1/lib/aitasks_home.sh"; echo "RC=$?"
        echo "AH=$AITASKS_HOME"; aitasks_engine_dir dev' _ "$S"
    assert_eq "N1[$mode] explicit AITASKS_HOME needs no HOME" \
        "RC=0|AH=$AH|$AH/engine/dev" "$(tr '\n' '|' <<<"$OUT" | sed 's/|$//')"

    # --- N3: engine installer, errexit OFF (install.sh's `… || true`) -------
    run "$mode" -- -c 'set -u; warn(){ :; }
        source "$1/lib/engine_install.sh" || echo "REFUSED:$?"
        echo SURVIVED; declare -F engine_publish_locked >/dev/null && echo HAS_FN
        echo "LOADED=${_ENGINE_INSTALL_LOADED-unset} AH=${AITASKS_HOME-unset}"' _ "$S"
    assert_contains "N3[$mode] refused source reported" "REFUSED:1" "$OUT"
    assert_contains "N3[$mode] caller survives" "SURVIVED" "$OUT"
    assert_not_contains "N3[$mode] installer functions stay undefined" "HAS_FN" "$OUT"
    assert_contains "N3[$mode] installer + root stay unloaded" "LOADED=unset AH=unset" "$OUT"

    # --- S1: shim, neither variable, in-process resolver (probe stubbed) ----
    : >"$PROBES"
    run "$mode" "PROBES=$PROBES" -- -c "$RESOLVE_SNIPPET" _ "$S/aitask_testmap.sh"
    assert_contains "S1[$mode] resolver rc 3" "RC=3" "$OUT"
    assert_contains "S1[$mode] resolver error token" "ERR=$HOME_UNSET_TOKEN" "$OUT"
    assert_contains "S1[$mode] sourcing shell survives" "SURVIVED" "$OUT"
    assert_eq "S1[$mode] no slot probed" "" "$(cat "$PROBES")"

    # --- S4 (dev): same, AIT_ENGINE=dev -------------------------------------
    : >"$PROBES"
    run "$mode" "PROBES=$PROBES" AIT_ENGINE=dev -- -c "$RESOLVE_SNIPPET" _ "$S/aitask_testmap.sh"
    assert_contains "S4[$mode] dev: resolver rc 3" "RC=3" "$OUT"
    assert_contains "S4[$mode] dev: resolver error token" "ERR=$HOME_UNSET_TOKEN" "$OUT"
    assert_eq "S4[$mode] dev: no slot probed" "" "$(cat "$PROBES")"

    # --- S2: the override needs no root --------------------------------------
    run "$mode" "AIT_TESTMAP_BIN=$STUB" -- "$S/aitask_testmap.sh" version
    assert_eq "S2[$mode] override runs without a root" "STUB:version|rc=0" "$OUT|rc=$RC"
    assert_eq "S2[$mode] override announced, nothing else" "ENGINE_OVERRIDE:$STUB" "$ERR"
    run "$mode" "AIT_TESTMAP_BIN=$STUB" "AITASKS_HOME=$AH" -- "$S/aitask_testmap.sh" version
    assert_eq "S2[$mode] override with explicit root" "STUB:version|rc=0" "$OUT|rc=$RC"

    # --- S3: explicit root, no HOME -> its own slot, never /.aitasks --------
    run "$mode" "AITASKS_HOME=$AH" -- "$S/aitask_testmap.sh" version
    assert_eq "S3[$mode] explicit root: ENGINE_MISSING in that root, rc 3" \
        "ENGINE_MISSING:$AH/engine/v$V/ait-testmap|run 'ait setup' or set AIT_TESTMAP_BIN|rc=3" "$ERR|rc=$RC"

    # --- S4 (bogus mode): USAGE/64 is kept, override still first -------------
    run "$mode" AIT_ENGINE=bogus -- "$S/aitask_testmap.sh" version
    assert_eq "S4[$mode] invalid mode still USAGE, rc 64" "$USAGE_TOKEN|rc=64" "$ERR|rc=$RC"
    run "$mode" AIT_ENGINE=bogus "AIT_TESTMAP_BIN=$STUB" -- "$S/aitask_testmap.sh" version
    assert_eq "S4[$mode] override still precedes the mode check" "STUB:version|rc=0" "$OUT|rc=$RC"

    # --- E1: engine help needs no root ---------------------------------------
    for flag in --help -h; do
        run "$mode" -- "$S/aitask_engine.sh" "$flag"
        assert_eq "E1[$mode] $flag rc 0, no root" "0" "$RC"
        assert_contains "E1[$mode] $flag prints the help header" 'aitask_engine.sh — `ait engine <verb>`' "$OUT"
        run "$mode" "AITASKS_HOME=$AH" -- "$S/aitask_engine.sh" "$flag"
        assert_eq "E1[$mode] $flag rc 0, explicit root" "0" "$RC"
        assert_contains "E1[$mode] $flag help header, explicit root" 'aitask_engine.sh — `ait engine <verb>`' "$OUT"
    done

    # --- E2: `home` (read-only report ONLY — see SAFETY RULES) --------------
    run "$mode" "AITASKS_HOME=$AH" -- "$S/aitask_engine.sh" home
    assert_eq "E2[$mode] home refuses: HOME_SKIPPED:home-unset, rc 1" "HOME_SKIPPED:home-unset|rc=1" "$OUT|rc=$RC"
    assert_dir_not_exists "E2[$mode] explicit root left untouched" "$AH"
    # An invalid argument is a usage error first (argument parsing only).
    run "$mode" "AITASKS_HOME=$AH" -- "$S/aitask_engine.sh" home --bogus
    assert_eq "E2[$mode] home --bogus: usage error, nothing on stdout, rc 64" "|rc=64" "$OUT|rc=$RC"
    assert_contains "E2[$mode] home --bogus: USAGE on stderr" "USAGE:ait engine" "$ERR"

    # --- E3: prune --dry-run -------------------------------------------------
    run "$mode" "AITASKS_HOME=$AH" -- "$S/aitask_engine.sh" prune --dry-run
    assert_eq "E3[$mode] no registry path: PRUNE_REFUSED:no-home, rc 1" \
        "PRUNE_REFUSED:no-home|set AITASKS_PROJECTS_INDEX or HOME|rc=1" "$OUT|rc=$RC"
    run "$mode" "AITASKS_HOME=$AH" "AITASKS_PROJECTS_INDEX=$ROOT/missing.yaml" -- \
        "$S/aitask_engine.sh" prune --dry-run
    assert_eq "E3[$mode] registry override still bypasses HOME" \
        "PRUNE_REFUSED:no-registry|$ROOT/missing.yaml|rc=1" "$OUT|rc=$RC"

    # --- E4: startup ---------------------------------------------------------
    run "$mode" -- "$S/aitask_engine.sh" home
    assert_eq "E4[$mode] neither variable: rc 1, nothing on stdout" "|rc=1" "$OUT|rc=$RC"
    assert_contains "E4[$mode] neither variable: the lib's Error line" "Error: AITASKS_HOME is unset" "$ERR"
    assert_not_contains "E4[$mode] neither variable: no unbound-variable abort" "unbound variable" "$ERR"
    run "$mode" "AITASKS_HOME=$AH" -- "$S/aitask_engine.sh" bogus
    assert_eq "E4[$mode] explicit root: startup survives (UNKNOWN_VERB, rc 64)" "64" "$RC"
    assert_contains "E4[$mode] explicit root: UNKNOWN_VERB" "UNKNOWN_VERB:bogus" "$ERR"
    assert_not_contains "E4[$mode] explicit root: no unbound-variable abort" "unbound variable" "$ERR"
done

# --- N2: lib, valid HOME, root cannot be assigned (readonly) ----------------
# The lazy, conditional source the shim uses: under errexit, `if ! source`
# would run on past a failed assignment, so the lib must refuse up front.
N2_SNIPPET='set -euo pipefail; f() { if source "$1/lib/aitasks_home.sh"; then echo RC=0; else echo RC=1; fi; }
f "$1"; echo "REASON=${AITASKS_HOME_REFUSAL-unset} LOADED=${_AITASKS_HOME_LOADED-unset}"
declare -F aitasks_engine_dir >/dev/null && echo HAS_FN; echo END'
run "$SHOME" -- -c 'readonly AITASKS_HOME=""; '"$N2_SNIPPET" _ "$S"
assert_contains "N2 readonly empty AITASKS_HOME: source fails" "RC=1" "$OUT"
assert_contains "N2 readonly empty AITASKS_HOME: reason, not loaded" "REASON=root-unsettable LOADED=unset" "$OUT"
assert_not_contains "N2 readonly empty AITASKS_HOME: no aitasks_engine_dir" "HAS_FN" "$OUT"
assert_contains "N2 readonly empty AITASKS_HOME: names the variable" "AITASKS_HOME is readonly and empty" "$ERR"
run "$SHOME" "AITASKS_HOME=$AH" -- -c 'readonly AITASKS_HOME_LOCK=/elsewhere; '"$N2_SNIPPET" _ "$S"
assert_contains "N2 readonly foreign AITASKS_HOME_LOCK: source fails" "RC=1" "$OUT"
assert_contains "N2 readonly foreign AITASKS_HOME_LOCK: reason, not loaded" "REASON=root-unsettable LOADED=unset" "$OUT"
assert_not_contains "N2 readonly foreign AITASKS_HOME_LOCK: no aitasks_engine_dir" "HAS_FN" "$OUT"
# A refused source publishes nothing. With a DERIVED root and a conflicting
# function-local readonly lock, no root may survive the refusal: once the
# function returns and HOME changes, the retry must derive the NEW root.
mkdir -p "$ROOT/home2"
run "$SHOME" -- -c 'set -u
    f() { local -r AITASKS_HOME_LOCK=/elsewhere; if source "$1/lib/aitasks_home.sh" 2>/dev/null; then echo RC=0; else echo RC=1; fi; }
    f "$1"; echo "AH_AFTER=${AITASKS_HOME-unset} LOCK_AFTER=${AITASKS_HOME_LOCK-unset}"
    HOME="$2"; source "$1/lib/aitasks_home.sh"; echo "RETRY_AH=$AITASKS_HOME RETRY_LOCK=$AITASKS_HOME_LOCK"' _ "$S" "$ROOT/home2"
assert_contains "N2 derived root + foreign local lock: source fails" "RC=1" "$OUT"
assert_contains "N2 derived root + foreign local lock: nothing published" "AH_AFTER=unset LOCK_AFTER=unset" "$OUT"
assert_contains "N2 retry after the refusal derives the NEW root" \
    "RETRY_AH=$ROOT/home2/.aitasks RETRY_LOCK=$ROOT/home2/.aitasks/.home.lock" "$OUT"
# A readonly lock that already holds the right value is accepted without
# reassignment, even by an UNGUARDED source under errexit.
MATCH_SNIPPET='set -euo pipefail; readonly AITASKS_HOME_LOCK="$2"; source "$1/lib/aitasks_home.sh"
echo "RC=0 AH=$AITASKS_HOME LOCK=$AITASKS_HOME_LOCK LOADED=${_AITASKS_HOME_LOADED-unset}"'
run "$SHOME" "AITASKS_HOME=$AH" -- -c "$MATCH_SNIPPET" _ "$S" "$AH/.home.lock"
assert_eq "N2 matching readonly lock, explicit root: loads" \
    "RC=0 AH=$AH LOCK=$AH/.home.lock LOADED=1|rc=0" "$OUT|rc=$RC"
assert_not_contains "N2 matching readonly lock, explicit root: no readonly error" "readonly" "$ERR"
run "$SHOME" -- -c "$MATCH_SNIPPET" _ "$S" "$SHOME/.aitasks/.home.lock"
assert_eq "N2 matching readonly lock, derived root: loads" \
    "RC=0 AH=$SHOME/.aitasks LOCK=$SHOME/.aitasks/.home.lock LOADED=1|rc=0" "$OUT|rc=$RC"
assert_not_contains "N2 matching readonly lock, derived root: no readonly error" "readonly" "$ERR"
run "$SHOME" "AITASKS_HOME=$AH" -- -c 'readonly AITASKS_HOME; '"$N2_SNIPPET" _ "$S"
assert_contains "N2 readonly NON-empty AITASKS_HOME still loads" "RC=0" "$OUT"
assert_contains "N2 readonly NON-empty AITASKS_HOME: loaded" "LOADED=1" "$OUT"

# --- S5: shim, valid HOME, unassignable root (probe stubbed) -----------------
: >"$PROBES"
run "$SHOME" "PROBES=$PROBES" -- -c 'readonly AITASKS_HOME=""; '"$RESOLVE_SNIPPET" _ "$S/aitask_testmap.sh"
assert_contains "S5 readonly empty root: resolver rc 3" "RC=3" "$OUT"
assert_contains "S5 readonly empty root: ENGINE_ROOT_INVALID" "ERR=ENGINE_ROOT_INVALID:AITASKS_HOME|root-unsettable" "$OUT"
assert_eq "S5 readonly empty root: no slot probed (never /engine/...)" "" "$(cat "$PROBES")"

# --- S6: an override engine still inherits a derivable root ------------------
run "$SHOME" "AIT_TESTMAP_BIN=$ENVSTUB" -- "$S/aitask_testmap.sh"
assert_eq "S6 override inherits the derived root and lock" \
    "AH=$SHOME/.aitasks LOCK=$SHOME/.aitasks/.home.lock|rc=0" "$OUT|rc=$RC"
run "$SHOME" "AIT_TESTMAP_BIN=$ENVSTUB" "AITASKS_HOME=$AH" -- "$S/aitask_testmap.sh"
assert_eq "S6 override inherits an explicit root and its lock" \
    "AH=$AH LOCK=$AH/.home.lock|rc=0" "$OUT|rc=$RC"

# --- S7: missing lib = incomplete install, not a HOME problem ----------------
mkdir -p "$ROOT/nolib/.aitask-scripts"
cp "$S/aitask_testmap.sh" "$S/VERSION" "$ROOT/nolib/.aitask-scripts/"
NOLIB_DIR="$(cd "$ROOT/nolib/.aitask-scripts" && pwd)"
run "$SHOME" -- "$NOLIB_DIR/aitask_testmap.sh" version
assert_eq "S7 missing lib: ENGINE_LIB_FAILED with the repair, rc 3" \
    "ENGINE_LIB_FAILED:$NOLIB_DIR/lib/aitasks_home.sh|run 'ait setup' to repair the install|rc=3" "$ERR|rc=$RC"
run "$SHOME" "AIT_TESTMAP_BIN=$STUB" -- "$NOLIB_DIR/aitask_testmap.sh" version
assert_eq "S7 missing lib: the override still runs" "STUB:version|rc=0" "$OUT|rc=$RC"

# --- S1 / S4 (dev) CLI: probe-safety form (b) — HOME ABSENT only ------------
run absent -- "$S/aitask_testmap.sh" version
assert_eq "S1[cli] ENGINE_HOME_UNSET is the one stderr line, rc 3" "$HOME_UNSET_TOKEN|rc=3" "$ERR|rc=$RC"
run absent AIT_ENGINE=dev -- "$S/aitask_testmap.sh" version
assert_eq "S4[cli] dev: ENGINE_HOME_UNSET, rc 3" "$HOME_UNSET_TOKEN|rc=3" "$ERR|rc=$RC"

# --- HOME-set control: the default root is unchanged -------------------------
mkdir -p "$ROOT/home"
run "$ROOT/home" -- -c 'set -u; source "$1/lib/aitasks_home.sh"; echo "AH=$AITASKS_HOME"' _ "$S"
assert_eq "C1 HOME set: default root is \$HOME/.aitasks" "AH=$ROOT/home/.aitasks" "$OUT"

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed (of $TOTAL total)"
echo "================================"

if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
