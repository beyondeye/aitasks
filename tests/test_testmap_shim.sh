#!/usr/bin/env bash
# test_testmap_shim.sh — the `ait testmap` shim and its strict handshake
# (t1852_4, test map M1.4).
#
# Most cases run a STAGED framework tree ($S/fw/.aitask-scripts/ with the shim,
# lib/aitasks_home.sh and a VERSION of 1.2.3) against an $AITASKS_HOME host
# directory and fake engines; the W cases drive the real `./ait` dispatcher,
# and E1 builds the real engine when Go is present. Case IDs are the ones the
# shim's header "Interfaces" table cites.
#
# Run: bash tests/test_testmap_shim.sh
#
# shellcheck disable=SC2016  # single-quoted `bash -c` snippets expand in the child.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

S="$(mktemp -d)"
trap 'rm -rf "$S"' EXIT

# --- staged framework tree ----------------------------------------------------
FW="$S/fw/.aitask-scripts"
mkdir -p "$FW/lib" "$S/home"
cp "$PROJECT_DIR/.aitask-scripts/aitask_testmap.sh" "$FW/"
cp "$PROJECT_DIR/.aitask-scripts/lib/aitasks_home.sh" "$FW/lib/"
printf '1.2.3\n' > "$FW/VERSION"
SHIM="$FW/aitask_testmap.sh"
H="$S/h"
REL="$H/engine/v1.2.3/ait-testmap"
DEV="$H/engine/dev/ait-testmap"
MISSING_HINT="run 'ait setup' or set AIT_TESTMAP_BIN"
DEV_HINT="run 'ait engine build' or unset AIT_ENGINE"
OVR_HINT="fix or unset AIT_TESTMAP_BIN"

# Fake engines record into these (exported so the fakes see them).
export FAKE_RAN="$S/ran" FAKE_ATE="$S/ate"

# mkfake <path> <version> [version-rc] — a fake engine.
#   `version`: prints the four-line text form for <version>; <version> "-"
#   prints no VERSION: line, "DOUBLE:<v>" prints two. If it can read a line of
#   stdin it records it in $FAKE_ATE (the handshake must close stdin).
#   any other verb: touches $FAKE_RAN, prints ARG:<a> per argument, with
#   `--stdin` also STDIN:<stdin, newlines as spaces>; exits $FAKE_EXIT.
mkfake() {
    local path="$1" ver="$2" vrc="${3:-0}" vlines
    case "$ver" in
        -)        vlines='COMMIT:abc' ;;
        DOUBLE:*) vlines="VERSION:${ver#DOUBLE:}"$'\n'"VERSION:${ver#DOUBLE:}" ;;
        *)        vlines="VERSION:$ver"$'\n'"COMMIT:abc"$'\n'"CONTRACT:1"$'\n'"ENGINE:$path" ;;
    esac
    mkdir -p "$(dirname "$path")"
    cat > "$path" <<EOF
#!/usr/bin/env bash
if [[ "\${1:-}" == version ]]; then
    if IFS= read -r -t 1 line; then printf '%s\n' "\$line" >> "\$FAKE_ATE"; fi
    cat <<'VEOF'
$vlines
VEOF
    exit $vrc
fi
: > "\$FAKE_RAN"
for a in "\$@"; do printf 'ARG:%s\n' "\$a"; done
case " \$* " in *" --stdin "*) printf 'STDIN:%s\n' "\$(tr '\n' ' ')" ;; esac
exit "\${FAKE_EXIT:-0}"
EOF
    chmod +x "$path"
}

reset_host() { rm -rf "$H" "$FAKE_RAN" "$FAKE_ATE"; }

# shim [VAR=value ...] -- [args ...] — run the staged shim with a clean
# engine environment plus the given assignments; sets OUT / ERR / RC.
shim() {
    local -a assigns=()
    while [[ $# -gt 0 && "$1" != "--" ]]; do assigns+=("$1"); shift; done
    shift
    RC=0
    OUT="$(env -u AIT_TESTMAP_BIN -u AIT_ENGINE HOME="$S/home" AITASKS_HOME="$H" \
        "${assigns[@]}" bash "$SHIM" "$@" 2>"$S/stderr")" || RC=$?
    ERR="$(cat "$S/stderr")"
}

ran() { [[ -e "$FAKE_RAN" ]] && echo yes || echo no; }

# --- R: the release slot ------------------------------------------------------
reset_host; mkfake "$REL" 1.2.3
shim FAKE_EXIT=5 -- run "a b" "" z
assert_eq "R1 engine exit status is returned" "5" "$RC"
assert_eq "R1 args reach the engine verbatim" $'ARG:run\nARG:a b\nARG:\nARG:z' "$OUT"
assert_eq "R1 no stderr on the release tier" "" "$ERR"

RC=0
OUT="$(printf 'l1\nl2\n' | env -u AIT_TESTMAP_BIN -u AIT_ENGINE HOME="$S/home" \
    AITASKS_HOME="$H" bash "$SHIM" x --stdin 2>/dev/null)" || RC=$?
assert_eq "R2 stdin reaches the verb intact" $'ARG:x\nARG:--stdin\nSTDIN:l1 l2 ' "$OUT"
assert_eq "R2 the handshake did not consume stdin" "no" "$([[ -e "$FAKE_ATE" ]] && echo yes || echo no)"

reset_host
shim -- version
assert_eq "R3 absent slot exits 3" "3" "$RC"
assert_eq "R3 ENGINE_MISSING names the exact slot and the repair" "ENGINE_MISSING:$REL|$MISSING_HINT" "$ERR"
assert_eq "R3 stdout stays empty" "" "$OUT"

reset_host; mkfake "$REL" 1.2.2
shim -- run
assert_eq "R4 version mismatch exits 3" "3" "$RC"
assert_eq "R4 mismatch is reported, then ENGINE_MISSING" \
    "ENGINE_REJECTED:$REL|version-mismatch|1.2.2|1.2.3"$'\n'"ENGINE_MISSING:$REL|$MISSING_HINT" "$ERR"
assert_eq "R4 the mismatched engine never ran a verb" "no" "$(ran)"

reset_host
mkfake "$H/engine/v1.2.2/ait-testmap" 1.2.2
mkfake "$H/engine/v9.9.9/ait-testmap" 9.9.9
shim -- run
assert_eq "R5 never newest-wins: exits 3" "3" "$RC"
assert_eq "R5 never newest-wins: names only v1.2.3" "ENGINE_MISSING:$REL|$MISSING_HINT" "$ERR"
assert_eq "R5 no other slot ran" "no" "$(ran)"

for v in devel 1.2.3-dev+abc1234; do
    reset_host; mkfake "$REL" "$v"
    shim -- run
    assert_eq "R6 release slot refuses '$v' (exit)" "3" "$RC"
    assert_contains "R6 release slot refuses '$v'" "ENGINE_REJECTED:$REL|version-mismatch|$v|1.2.3" "$ERR"
done

reset_host; mkfake "$REL" 1.2.3 1
shim -- run
assert_contains "R7 version exiting 1 is unreadable" "ENGINE_REJECTED:$REL|version-unreadable" "$ERR"
reset_host; mkfake "$REL" -
shim -- run
assert_contains "R7 no VERSION: line is unreadable" "ENGINE_REJECTED:$REL|version-unreadable" "$ERR"
reset_host; mkfake "$REL" DOUBLE:1.2.3
shim -- run
assert_contains "R7 two VERSION: lines are unreadable" "ENGINE_REJECTED:$REL|version-unreadable" "$ERR"
reset_host; mkfake "$REL" 1.2.3; chmod -x "$REL"
shim -- run
assert_eq "R7 non-executable slot exits 3" "3" "$RC"
assert_contains "R7 non-executable slot is reported" "ENGINE_REJECTED:$REL|not-executable" "$ERR"
assert_eq "R7 nothing ran" "no" "$(ran)"

# --- D: the developer slot ----------------------------------------------------
for v in 1.2.3-dev+abc1234 "1.2.3-dev+$(printf '%040d' 0 | tr 0 a)"; do
    reset_host; mkfake "$DEV" "$v"
    shim AIT_ENGINE=dev -- run
    assert_eq "D1 dev slot '$v' runs" "0|yes" "$RC|$(ran)"
done

for v in 1.2.3 1.2.2-dev+abc1234 1.2.3-dev+XYZ1234 1.2.3-dev+abc; do
    reset_host; mkfake "$DEV" "$v"; mkfake "$REL" 1.2.3
    shim AIT_ENGINE=dev -- run
    assert_eq "D2 dev slot refuses '$v' (exit 3, no fall-through)" "3|no" "$RC|$(ran)"
    assert_eq "D2 dev slot refuses '$v'" \
        "ENGINE_REJECTED:$DEV|version-mismatch|$v|1.2.3-dev+<sha>"$'\n'"ENGINE_MISSING:$DEV|$DEV_HINT" "$ERR"
done

reset_host; mkfake "$REL" 1.2.3
shim AIT_ENGINE=dev -- run
assert_eq "D3 absent dev slot exits 3 despite a valid release slot" "3|no" "$RC|$(ran)"
assert_eq "D3 names the dev slot and its repair" "ENGINE_MISSING:$DEV|$DEV_HINT" "$ERR"

shim AIT_ENGINE=release -- run
assert_eq "D4 unknown AIT_ENGINE exits 64" "64" "$RC"
assert_eq "D4 unknown AIT_ENGINE is a usage error" "USAGE:AIT_ENGINE must be 'dev' or unset" "$ERR"

# --- O: the override ----------------------------------------------------------
reset_host; mkfake "$REL" 1.2.3; mkfake "$DEV" 1.2.3-dev+abc1234
O="$S/o/fake-engine"; mkfake "$O" -
shim AIT_TESTMAP_BIN="$O" AIT_ENGINE=dev -- x
assert_eq "O1 the override wins over dev and release, no version check" "0|yes" "$RC|$(ran)"
assert_eq "O1 the override is announced on stderr" "ENGINE_OVERRIDE:$O" "$ERR"
assert_eq "O1 stdout is the engine's alone" "ARG:x" "$OUT"

reset_host; mkfake "$REL" 1.2.3
NX="$S/o/not-executable"; printf 'x\n' > "$NX"
for bad in "$S/o/nope" "$NX"; do
    shim AIT_TESTMAP_BIN="$bad" -- run
    assert_eq "O2 broken override '$bad' exits 3 without fall-through" "3|no" "$RC|$(ran)"
    assert_eq "O2 broken override '$bad' is reported" \
        "ENGINE_OVERRIDE:$bad"$'\n'"ENGINE_REJECTED:$bad|not-executable"$'\n'"ENGINE_MISSING:$bad|$OVR_HINT" "$ERR"
done
shim AIT_TESTMAP_BIN="o/fake-engine" -- run
assert_eq "O2 relative override exits 3" "3|no" "$RC|$(ran)"
assert_contains "O2 relative override is not-absolute" "ENGINE_REJECTED:o/fake-engine|not-absolute" "$ERR"
assert_contains "O2 relative override names its repair" "ENGINE_MISSING:o/fake-engine|$OVR_HINT" "$ERR"

# --- V / U: unusable inputs ----------------------------------------------------
reset_host; mkfake "$REL" 1.2.3
for content in "" "1 2"; do
    printf '%s\n' "$content" > "$FW/VERSION"
    shim -- run
    assert_eq "V1 VERSION '$content' exits 3" "3|no" "$RC|$(ran)"
    assert_eq "V1 VERSION '$content' is invalid" "VERSION_INVALID:$FW/VERSION" "$ERR"
done
# V2 — missing and unreadable VERSION: one structured line, nothing raw.
# shim_cli <shim> — CLI run: sets RC and ERR (stderr verbatim).
shim_cli() {
    RC=0
    env -u AIT_TESTMAP_BIN -u AIT_ENGINE HOME="$S/home" AITASKS_HOME="$H" \
        bash "$1" run >/dev/null 2>"$S/stderr" || RC=$?
    ERR="$(cat "$S/stderr")"
}
# shim_resolve <shim> — source-only resolver: "rc|error" on stdout, and its
# stderr verbatim in RERR.
shim_resolve() {
    env -u AIT_TESTMAP_BIN -u AIT_ENGINE HOME="$S/home" AITASKS_HOME="$H" bash -c '
        source "$1" --source-only
        rc=0; testmap_resolve_engine || rc=$?
        printf "%s|%s\n" "$rc" "$TESTMAP_ENGINE_ERROR"' _ "$1" 2>"$S/rstderr"
    RERR="$(cat "$S/rstderr")"
}
# unreadable <file> — chmod 000; false (case skipped) when the mode is not
# enforced for this user (root).
unreadable() { chmod 000 "$1"; [[ ! -r "$1" ]]; }

mv "$FW/VERSION" "$FW/VERSION.bak"
shim_cli "$SHIM"
assert_eq "V2 missing VERSION is one structured line" "3|VERSION_INVALID:$FW/VERSION" "$RC|$ERR"
mv "$FW/VERSION.bak" "$FW/VERSION"
if unreadable "$FW/VERSION"; then
    shim_cli "$SHIM"
    assert_eq "V2 unreadable VERSION (CLI) is one structured line" "3|VERSION_INVALID:$FW/VERSION" "$RC|$ERR"
    shim_resolve "$SHIM" >"$S/rout"
    assert_eq "V2 unreadable VERSION (resolver) error" "3|VERSION_INVALID:$FW/VERSION" "$(cat "$S/rout")"
    assert_eq "V2 unreadable VERSION (resolver) leaks no raw stderr" "" "$RERR"
else
    echo "SKIP: V2 unreadable (file mode not enforced for this user)"
fi
chmod 644 "$FW/VERSION"

printf '1.2.3\r\n' > "$FW/VERSION"
shim -- run
assert_eq "V1 a CRLF VERSION still matches" "0|yes" "$RC|$(ran)"
printf '1.2.3\n' > "$FW/VERSION"

reset_host
shim AITASKS_HOME="$S/a|b" -- run
assert_eq "U1 unsafe AITASKS_HOME exits 3" "3" "$RC"
assert_eq "U1 names the variable, not the value" "ENGINE_PATH_UNSAFE:AITASKS_HOME" "$ERR"
shim AIT_TESTMAP_BIN="$S/o/a|b" -- run
assert_eq "U1 unsafe AIT_TESTMAP_BIN exits 3" "3" "$RC"
assert_eq "U1 unsafe override is named, not echoed" "ENGINE_PATH_UNSAFE:AIT_TESTMAP_BIN" "$ERR"

# U2 — a framework dir that cannot travel as a field (LF, pipe): an invalid
# VERSION must still yield exactly ONE diagnostic line; a valid VERSION there
# must still work (the dir is only ever printed by VERSION_INVALID).
for odd in $'nl\ndir' 'pipe|dir'; do
    oddfw="$S/$odd/.aitask-scripts"
    mkdir -p "$oddfw/lib"
    cp "$SHIM" "$oddfw/"; cp "$FW/lib/aitasks_home.sh" "$oddfw/lib/"
    label="${odd//$'\n'/\\n}"
    printf '1 2\n' > "$oddfw/VERSION"
    RC=0
    env -u AIT_TESTMAP_BIN -u AIT_ENGINE HOME="$S/home" AITASKS_HOME="$H" \
        bash "$oddfw/aitask_testmap.sh" run >/dev/null 2>"$S/stderr" || RC=$?
    assert_eq "U2 '$label' framework dir + bad VERSION exits 3" "3" "$RC"
    assert_eq "U2 '$label' yields one line naming the variable" "ENGINE_PATH_UNSAFE:SCRIPT_DIR" "$(cat "$S/stderr")"
    out="$(env -u AIT_TESTMAP_BIN -u AIT_ENGINE HOME="$S/home" AITASKS_HOME="$H" bash -c '
        source "$1" --source-only
        rc=0; testmap_resolve_engine || rc=$?
        printf "%s|%s\n" "$rc" "$TESTMAP_ENGINE_ERROR"' _ "$oddfw/aitask_testmap.sh" 2>/dev/null)"
    assert_eq "U2 '$label' resolver error is one line" "3|ENGINE_PATH_UNSAFE:SCRIPT_DIR" "$out"
    printf '1.2.3\n' > "$oddfw/VERSION"
    if unreadable "$oddfw/VERSION"; then
        shim_cli "$oddfw/aitask_testmap.sh"
        assert_eq "U2 '$label' unreadable VERSION (CLI) is one line" "3|ENGINE_PATH_UNSAFE:SCRIPT_DIR" "$RC|$ERR"
        shim_resolve "$oddfw/aitask_testmap.sh" >"$S/rout"
        assert_eq "U2 '$label' unreadable VERSION (resolver) error" "3|ENGINE_PATH_UNSAFE:SCRIPT_DIR" "$(cat "$S/rout")"
        assert_eq "U2 '$label' unreadable VERSION (resolver) leaks no raw stderr" "" "$RERR"
    else
        echo "SKIP: U2 '$label' unreadable (file mode not enforced for this user)"
    fi
    chmod 644 "$oddfw/VERSION"
    reset_host; mkfake "$REL" 1.2.3
    printf '1.2.3\n' > "$oddfw/VERSION"
    RC=0
    env -u AIT_TESTMAP_BIN -u AIT_ENGINE HOME="$S/home" AITASKS_HOME="$H" \
        bash "$oddfw/aitask_testmap.sh" run >/dev/null 2>&1 || RC=$?
    assert_eq "U2 '$label' framework dir + valid VERSION still runs" "0|yes" "$RC|$(ran)"
done

# --- A1: the resolver API (no exec) ---------------------------------------------
resolve() {
    env -u AIT_TESTMAP_BIN -u AIT_ENGINE HOME="$S/home" AITASKS_HOME="$H" bash -c '
        source "$1" --source-only
        rc=0; testmap_resolve_engine || rc=$?
        printf "%s|%s|%s\n" "$rc" "$TESTMAP_ENGINE_BIN" "$TESTMAP_ENGINE_ERROR"' _ "$SHIM" 2>/dev/null
}
reset_host; mkfake "$REL" 1.2.3
assert_eq "A1 resolver: match sets TESTMAP_ENGINE_BIN" "0|$REL|" "$(resolve)"
rm -f "$REL"
assert_eq "A1 resolver: absent sets TESTMAP_ENGINE_ERROR" "3||ENGINE_MISSING:$REL|$MISSING_HINT" "$(resolve)"
assert_eq "A1 resolver never execs the engine" "no" "$(ran)"

# --- W: the real dispatcher ----------------------------------------------------
AIT="$PROJECT_DIR/ait"
mkfake "$S/o/ver-engine" 7.7.7
mkdir -p "$S/home2/.aitask"
printf '%s 99.0.0\n' "$(date +%s)" > "$S/home2/.aitask/update_check"

RC=0
OUT="$(env -u AIT_ENGINE HOME="$S/home2" AIT_TESTMAP_BIN="$S/o/ver-engine" "$AIT" testmap version 2>/dev/null)" || RC=$?
assert_eq "W1 ait testmap reaches the shim" "0" "$RC"
assert_eq "W1 stdout is exactly the engine's (no update notice)" \
    "VERSION:7.7.7"$'\n'"COMMIT:abc"$'\n'"CONTRACT:1"$'\n'"ENGINE:$S/o/ver-engine" "$OUT"

OUT="$(env HOME="$S/home2" "$AIT" no-such-cmd 2>/dev/null)"
assert_contains "W2 control: the seeded cache does print a notice elsewhere" "Update available" "$OUT"

assert_contains "W3 ait help lists testmap" "testmap        Run the test map engine" "$("$AIT" help)"

# W4 — no network with a MISSING cache. Each run is captured with $( ): the
# update check's background subshell inherits that pipe, so the substitution
# returns only once every writer — including a spawned fetch — has finished.
mkdir -p "$S/fakebin"
cat > "$S/fakebin/curl" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >> "$CURL_REC"
exit 0
EOF
chmod +x "$S/fakebin/curl"
out="$(env HOME="$S/home4" CURL_REC="$S/curl_ctl" PATH="$S/fakebin:$PATH" "$AIT" no-such-cmd 2>&1)"
assert_file_exists "W4 control: the fake curl intercepts the dispatcher's fetch" "$S/curl_ctl"
out="$(env -u AIT_ENGINE HOME="$S/home3" CURL_REC="$S/curl_tm" PATH="$S/fakebin:$PATH" \
    AIT_TESTMAP_BIN="$S/o/ver-engine" "$AIT" testmap version 2>&1)"
assert_contains "W4 ait testmap ran" "VERSION:7.7.7" "$out"
assert_file_not_exists "W4 ait testmap invoked no curl" "$S/curl_tm"
assert_file_not_exists "W4 ait testmap wrote no update cache" "$S/home3/.aitask/update_check"

# --- E1: the real engine --------------------------------------------------------
if command -v go >/dev/null 2>&1; then
    V="$(cat "$PROJECT_DIR/.aitask-scripts/VERSION")"
    target="$(env -u GOOS -u GOARCH go env GOHOSTOS)_$(env -u GOOS -u GOARCH go env GOHOSTARCH)"
    built="$(env -u GOOS -u GOARCH "$PROJECT_DIR/goengines/build.sh" "$target" \
        --version "$V" --out "$S/b" 2>/dev/null | sed -n 's/^BUILT://p')"
    H2="$S/h2"; SLOT="$H2/engine/v$V/ait-testmap"
    mkdir -p "$(dirname "$SLOT")"
    if [[ -n "$built" ]] && cp "$built" "$SLOT"; then
        e1() {
            RC=0
            OUT="$(env -u AIT_TESTMAP_BIN -u AIT_ENGINE HOME="$S/home5" AITASKS_HOME="$H2" \
                "$AIT" testmap "$@" 2>"$S/stderr")" || RC=$?
            ERR="$(cat "$S/stderr")"
        }
        e1 version
        assert_eq "E1 real engine: version exits 0" "0" "$RC"
        assert_eq "E1 real engine: VERSION line is the framework's" "VERSION:$V" "$(printf '%s\n' "$OUT" | head -n1)"
        e1 select
        assert_eq "E1 real engine: a stub verb's exit 64 passes through" "64" "$RC"
        assert_contains "E1 real engine: stub stderr passes through" "NOT_IMPLEMENTED:select" "$ERR"
        rm -f "$SLOT"
        e1 version
        assert_eq "E1 real engine removed: exit 3" "3" "$RC"
        assert_eq "E1 real engine removed: ENGINE_MISSING" "ENGINE_MISSING:$SLOT|$MISSING_HINT" "$ERR"
    else
        assert_eq "E1 goengines/build.sh produced a host binary" "built" "missing"
    fi
else
    echo "SKIP: E1 (go not installed)"
fi

# --- Summary -----------------------------------------------------------------
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
