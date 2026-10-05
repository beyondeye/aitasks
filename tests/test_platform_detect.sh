#!/usr/bin/env bash
# test_platform_detect.sh — `uname` → release-asset suffix (t1852_4, M1.4).
#
# Pins .aitask-scripts/lib/platform_detect.sh: the linux|darwin × amd64|arm64
# table, the PLATFORM_UNSUPPORTED refusal, the live default, and agreement with
# Go's own naming (goengines' platform.AssetSuffix() is runtime.GOOS_GOARCH,
# which is what the release assets are named after). The Go cross-check reads
# the HOST values (GOHOSTOS / GOHOSTARCH) with any GOOS / GOARCH target
# override unset, and a control re-runs it under such an override.
#
# Run: bash tests/test_platform_detect.sh
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

LIB="$PROJECT_DIR/.aitask-scripts/lib/platform_detect.sh"

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

# lib_run <snippet> — source the lib in a fresh bash and run <snippet>;
# stdout to stdout, stderr to $SCRATCH/err, exit status preserved.
lib_run() {
    bash -c '. "$1" && eval "$2"' _ "$LIB" "$1" 2>"$SCRATCH/err"
}

# --- P1: the supported table ------------------------------------------------
while read -r s m want; do
    out="$(lib_run "platform_asset_suffix $s $m")"
    assert_eq "P1 $s $m → $want" "$want" "$out"
done <<'EOF'
Linux x86_64 linux_amd64
Linux amd64 linux_amd64
Linux aarch64 linux_arm64
Linux arm64 linux_arm64
Darwin x86_64 darwin_amd64
Darwin arm64 darwin_arm64
Darwin aarch64 darwin_arm64
EOF

assert_eq "P1 platform_os Darwin" "darwin" "$(lib_run 'platform_os Darwin')"
assert_eq "P1 platform_arch aarch64" "arm64" "$(lib_run 'platform_arch aarch64')"

# --- P2: anything off the release matrix is refused -------------------------
for pair in "FreeBSD amd64" "Linux armv7l" "MINGW64_NT x86_64" "Linux i686"; do
    rc=0
    out="$(lib_run "platform_asset_suffix $pair")" || rc=$?
    assert_eq "P2 '$pair' exits 1" "1" "$rc"
    assert_eq "P2 '$pair' prints nothing on stdout" "" "$out"
    assert_eq "P2 '$pair' names the pair on stderr" \
        "PLATFORM_UNSUPPORTED:${pair% *}|${pair#* }" "$(cat "$SCRATCH/err")"
done
rc=0
out="$(lib_run 'platform_os SunOS')" || rc=$?
assert_eq "P2 platform_os SunOS exits 1" "1" "$rc"
assert_contains "P2 platform_os SunOS refuses on stderr" "PLATFORM_UNSUPPORTED:SunOS|" "$(cat "$SCRATCH/err")"

# --- P3: the no-argument default is the live uname --------------------------
live_rc=0
live="$(lib_run 'platform_asset_suffix')" || live_rc=$?
explicit_rc=0
explicit="$(lib_run "platform_asset_suffix $(uname -s) $(uname -m)")" || explicit_rc=$?
assert_eq "P3 default == explicit uname (output)" "$explicit" "$live"
assert_eq "P3 default == explicit uname (status)" "$explicit_rc" "$live_rc"

# --- P4: agreement with Go's host naming (the release asset names) ----------
# go_host_suffix — Go's view of THIS host, immune to a GOOS/GOARCH cross-build
# override in the environment.
go_host_suffix() {
    printf '%s_%s\n' "$(env -u GOOS -u GOARCH go env GOHOSTOS)" \
        "$(env -u GOOS -u GOARCH go env GOHOSTARCH)"
}
if command -v go >/dev/null 2>&1; then
    assert_eq "P4 matches go env GOHOSTOS_GOHOSTARCH" "$(go_host_suffix)" "$live"
    # Control: with a target override set (on a linux/amd64 host `go env GOOS`
    # would now say darwin), the comparison must still hold — proving it reads
    # the host, not the cross-compile target.
    assert_eq "P4 control precondition: the override does move go env GOOS" \
        "darwin_arm64" "$(GOOS=darwin GOARCH=arm64 go env GOOS)_$(GOOS=darwin GOARCH=arm64 go env GOARCH)"
    over="$(GOOS=darwin GOARCH=arm64 bash -c "$(declare -f go_host_suffix); go_host_suffix")"
    assert_eq "P4 control: host comparison survives GOOS/GOARCH override" "$live" "$over"
else
    echo "SKIP: P4 (go not installed)"
fi

# --- P5: idempotent double-source --------------------------------------------
out="$(lib_run '. "$1"; platform_asset_suffix Linux x86_64')"
assert_eq "P5 double source keeps working" "linux_amd64" "$out"

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
