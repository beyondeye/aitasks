#!/usr/bin/env bash
# test_goengines_build.sh - goengines/build.sh: asset names, build identity,
# the release matrix and its sums file, and usage refusals (t1852_3).
# Run: bash tests/test_goengines_build.sh
# Needs a Go toolchain; without one it prints SKIP and passes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0
. "$PROJECT_DIR/tests/lib/asserts.sh"

BUILD="$PROJECT_DIR/goengines/build.sh"

if ! command -v go >/dev/null 2>&1; then
    echo "SKIP: go not found on PATH"
    exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

GOOS_HOST="$(go env GOOS)"
GOARCH_HOST="$(go env GOARCH)"
VERSION_FILE="$(tr -d '[:space:]' < "$PROJECT_DIR/.aitask-scripts/VERSION")"

# --- 1. host build with an explicit identity ---------------------------------
out="$("$BUILD" --version 9.9.9-test --commit abc123 --out "$TMP/h" 2>/dev/null)"
bin="$TMP/h/ait-testmap_9.9.9-test_${GOOS_HOST}_${GOARCH_HOST}"
assert_eq "host build prints one BUILT line" "BUILT:$bin" "$out"
assert_file_exists "host binary named <name>_<V>_<os>_<arch>" "$bin"
json="$("$bin" version --json)"
assert_contains "version --json carries --version" '"version":"9.9.9-test"' "$json"
assert_contains "version --json carries --commit" '"commit":"abc123"' "$json"
assert_eq "host build writes no sums file" "" "$(find "$TMP/h" -name '*SHA256SUMS*')"

# --- 2. default version is .aitask-scripts/VERSION ----------------------------
out="$("$BUILD" --commit abc123 --out "$TMP/d" 2>/dev/null)"
assert_eq "default version comes from VERSION" \
    "BUILT:$TMP/d/ait-testmap_${VERSION_FILE}_${GOOS_HOST}_${GOARCH_HOST}" "$out"

# --- 3. the release matrix ----------------------------------------------------
out="$("$BUILD" --version 1.2.3 --commit abc123 --out "$TMP/all" all 2>/dev/null)"
assert_eq "all prints four BUILT lines" "4" "$(printf '%s\n' "$out" | grep -c '^BUILT:')"
assert_contains "all prints the SUMS line" "SUMS:$TMP/all/ait-testmap_1.2.3_SHA256SUMS.txt" "$out"
sums="$TMP/all/ait-testmap_1.2.3_SHA256SUMS.txt"
assert_eq "sums file lists the four matrix binaries, sorted" \
    "ait-testmap_1.2.3_darwin_amd64 ait-testmap_1.2.3_darwin_arm64 ait-testmap_1.2.3_linux_amd64 ait-testmap_1.2.3_linux_arm64" \
    "$(awk '{print $2}' "$sums" | tr '\n' ' ' | sed 's/ $//')"
if command -v sha256sum >/dev/null 2>&1; then
    check=(sha256sum -c)
else
    check=(shasum -a 256 -c)
fi
if (cd "$TMP/all" && "${check[@]}" "$(basename "$sums")" >/dev/null); then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: sha256 check of the sums file"
fi
for t in linux_amd64 linux_arm64 darwin_amd64 darwin_arm64; do
    info="$(go version -m "$TMP/all/ait-testmap_1.2.3_$t")"
    assert_contains "$t: GOOS" "GOOS=${t%%_*}" "$info"
    assert_contains "$t: GOARCH" "GOARCH=${t#*_}" "$info"
    assert_contains "$t: CGO disabled" "CGO_ENABLED=0" "$info"
    assert_contains "$t: trimpath" "-trimpath=true" "$info"
    assert_not_contains "$t: no VCS stamp" "vcs.revision" "$info"
done
assert_eq "the bench tool under internal/ is never built" "" \
    "$(find "$TMP/all" -name '*benchgate*')"

# --- 4. usage refusals: exit 2, nothing built ---------------------------------
refuse() {
    local desc="$1"; shift
    local rc=0
    "$BUILD" --out "$TMP/bad" "$@" >/dev/null 2>&1 || rc=$?
    assert_eq "$desc exits 2" "2" "$rc"
    assert_eq "$desc builds nothing" "" "$(find "$TMP/bad" -type f 2>/dev/null)"
}
refuse "a version with a space" --version "1 0"
refuse "an upper-case target" Linux-amd64
refuse "all combined with host" all host
refuse "an unknown option" --frobnicate
# An explicit empty value is a usage error, never the default in disguise.
refuse "an explicit empty --version" --version ""
refuse "an explicit empty --commit" --commit ""
refuse "an explicit empty --out" --out ""
refuse "--version with no value" --version

# --- 5. the VERSION file: only the line ending is stripped --------------------
# A copy of build.sh in a fake tree whose cmd/ is empty: the version is
# resolved before the executables are discovered, so the error names which of
# the two stopped the run.
fake_version() {
    local tree="$TMP/fake_$1"
    mkdir -p "$tree/goengines/cmd" "$tree/.aitask-scripts"
    cp "$BUILD" "$tree/goengines/build.sh"
    printf '%b' "$2" > "$tree/.aitask-scripts/VERSION"
    local rc=0 err
    err="$("$tree/goengines/build.sh" --commit abc123 2>&1 >/dev/null)" || rc=$?
    printf '%s|%s' "$rc" "$err"
}
res="$(fake_version space '1 2\n')"
assert_eq "a VERSION with inner whitespace exits 1" "1" "${res%%|*}"
assert_contains "a VERSION with inner whitespace is reported malformed, not joined" \
    "is malformed: '1 2'" "$res"
res="$(fake_version crlf '1.2.3\r\n')"
assert_contains "a CRLF VERSION is accepted (the run stops later, at cmd discovery)" \
    "no executables" "$res"
assert_not_contains "a CRLF VERSION is not reported malformed" "malformed" "$res"
res="$(fake_version empty '\n')"
assert_contains "an empty VERSION is refused" "is empty" "$res"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
