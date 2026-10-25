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

# The executables build.sh ships: every cmd/*/ holding a .go file (its own
# discovery rule). An export may add programs beside ait-testmap, so every
# count below is per executable.
CMDS=()
for d in "$PROJECT_DIR"/goengines/cmd/*/; do
    compgen -G "$d*.go" >/dev/null || continue
    CMDS+=("$(basename "$d")")
done
N=${#CMDS[@]}
assert_contains "ait-testmap is among the executables" " ait-testmap " " ${CMDS[*]} "

# built_lines <dir> <version> <target>: the BUILT lines one target prints.
built_lines() {
    local c lines=""
    for c in "${CMDS[@]}"; do
        lines+="BUILT:$1/${c}_$2_$3"$'\n'
    done
    printf '%s' "${lines%$'\n'}"
}

# --- 1. host build with an explicit identity ---------------------------------
out="$("$BUILD" --version 9.9.9-test --commit abc123 --out "$TMP/h" 2>/dev/null)"
assert_eq "host build prints one BUILT line per executable" \
    "$(built_lines "$TMP/h" 9.9.9-test "${GOOS_HOST}_${GOARCH_HOST}")" "$out"
for c in "${CMDS[@]}"; do
    assert_file_exists "$c: host binary named <name>_<V>_<os>_<arch>" "$TMP/h/${c}_9.9.9-test_${GOOS_HOST}_${GOARCH_HOST}"
done
json="$("$TMP/h/ait-testmap_9.9.9-test_${GOOS_HOST}_${GOARCH_HOST}" version --json)"
assert_contains "version --json carries --version" '"version":"9.9.9-test"' "$json"
assert_contains "version --json carries --commit" '"commit":"abc123"' "$json"
assert_eq "host build writes no sums file" "" "$(find "$TMP/h" -name '*SHA256SUMS*')"

# --- 2. default version is .aitask-scripts/VERSION ----------------------------
out="$("$BUILD" --commit abc123 --out "$TMP/d" 2>/dev/null)"
assert_eq "default version comes from VERSION" \
    "$(built_lines "$TMP/d" "$VERSION_FILE" "${GOOS_HOST}_${GOARCH_HOST}")" "$out"

if command -v sha256sum >/dev/null 2>&1; then
    check=(sha256sum -c)
else
    check=(shasum -a 256 -c)
fi

# assert_matrix <dir> <version> <build.sh stdout> <name>...: the release
# matrix of every named executable, one sorted sums file each.
assert_matrix() {
    local dir="$1" v="$2" out="$3" c t sums
    shift 3
    assert_eq "all prints four BUILT lines per executable" "$((4 * $#))" "$(printf '%s\n' "$out" | grep -c '^BUILT:')"
    assert_eq "all prints one SUMS line per executable" "$#" "$(printf '%s\n' "$out" | grep -c '^SUMS:')"
    for c in "$@"; do
        sums="$dir/${c}_${v}_SHA256SUMS.txt"
        assert_contains "$c: the SUMS line" "SUMS:$sums" "$out"
        assert_eq "$c: its sums file lists exactly its four matrix binaries, sorted" \
            "${c}_${v}_darwin_amd64 ${c}_${v}_darwin_arm64 ${c}_${v}_linux_amd64 ${c}_${v}_linux_arm64" \
            "$(awk '{print $2}' "$sums" | tr '\n' ' ' | sed 's/ $//')"
        if (cd "$dir" && "${check[@]}" "$(basename "$sums")" >/dev/null); then
            assert_record_pass
        else
            assert_record_fail
            echo "FAIL: $c: sha256 check of the sums file"
        fi
        for t in linux_amd64 linux_arm64 darwin_amd64 darwin_arm64; do
            info="$(go version -m "$dir/${c}_${v}_$t")"
            assert_contains "$c $t: GOOS" "GOOS=${t%%_*}" "$info"
            assert_contains "$c $t: GOARCH" "GOARCH=${t#*_}" "$info"
            assert_contains "$c $t: CGO disabled" "CGO_ENABLED=0" "$info"
            assert_contains "$c $t: trimpath" "-trimpath=true" "$info"
            assert_not_contains "$c $t: no VCS stamp" "vcs.revision" "$info"
        done
    done
}

# --- 3. the release matrix ----------------------------------------------------
out="$("$BUILD" --version 1.2.3 --commit abc123 --out "$TMP/all" all 2>/dev/null)"
assert_matrix "$TMP/all" 1.2.3 "$out" "${CMDS[@]}"
assert_eq "the matrix holds the binaries and sums files only" "$((5 * N))" \
    "$(find "$TMP/all" -type f | wc -l | tr -d ' ')"
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

# --- 6. several executables ---------------------------------------------------
# A fake tree with two programs and a cmd/ directory that holds no Go source:
# each program gets its own binaries, identity and sums file, and nothing is
# built for the directory without Go source.
fake="$TMP/multi"
mkdir -p "$fake/goengines/cmd/alpha" "$fake/goengines/cmd/beta" "$fake/goengines/cmd/notes" "$fake/.aitask-scripts"
cp "$BUILD" "$fake/goengines/build.sh"
printf '1.0.0\n' > "$fake/.aitask-scripts/VERSION"
printf 'module example.com/multi\n\ngo %s\n' "$(go env GOVERSION | sed -E 's/^go([0-9]+\.[0-9]+).*/\1/')" > "$fake/goengines/go.mod"
for c in alpha beta; do
    cat > "$fake/goengines/cmd/$c/main.go" <<EOF
package main

import "fmt"

var version, commit = "unset", "unset"

func main() { fmt.Println("$c", version, commit) }
EOF
done
printf 'notes, no Go source\n' > "$fake/goengines/cmd/notes/README"
CMDS=(alpha beta)
out="$("$fake/goengines/build.sh" --version 7.7.7 --commit def456 --out "$TMP/mh" 2>/dev/null)"
assert_eq "two executables: one host BUILT line each" \
    "$(built_lines "$TMP/mh" 7.7.7 "${GOOS_HOST}_${GOARCH_HOST}")" "$out"
for c in alpha beta; do
    assert_eq "$c carries its own --version / --commit" "$c 7.7.7 def456" \
        "$("$TMP/mh/${c}_7.7.7_${GOOS_HOST}_${GOARCH_HOST}")"
done
out="$("$fake/goengines/build.sh" --version 7.7.7 --commit def456 --out "$TMP/ma" all 2>/dev/null)"
assert_matrix "$TMP/ma" 7.7.7 "$out" alpha beta
assert_eq "nothing is built for a cmd/ directory without Go source" "" "$(find "$TMP/ma" -name 'notes*')"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
