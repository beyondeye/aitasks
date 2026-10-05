#!/usr/bin/env bash
# platform_detect.sh — map `uname` to the release-asset platform suffix.
#
# Sourced (not executed) by the engine installer (install_engine_binary(),
# `ait engine`), which composes the release asset name
# `ait-testmap_<V>_<os>_<arch>`. The suffix mirrors the Go side's
# goengines/internal/platform.AssetSuffix() (`runtime.GOOS_GOARCH`), and the
# supported set is the release matrix: linux|darwin × amd64|arm64.
#
#   platform_os   [<uname -s>]              → linux | darwin
#   platform_arch [<uname -m>]              → amd64 | arm64
#   platform_asset_suffix [<uname -s> <uname -m>] → <os>_<arch>
#
# Arguments default to the live `uname -s` / `uname -m`, so callers pass
# nothing and tests drive the table without faking `uname`. Anything outside
# the matrix prints `PLATFORM_UNSUPPORTED:<uname -s>|<uname -m>` on stderr and
# returns 1 (the cue to build from source); nothing is printed on stdout.
#
# Idempotent: sourcing this multiple times is a no-op after the first.

if [[ -n "${_PLATFORM_DETECT_LOADED:-}" ]]; then
    return 0
fi
_PLATFORM_DETECT_LOADED=1

platform_os() {
    local s="${1:-$(uname -s)}"
    case "$s" in
        Linux)  printf '%s\n' linux ;;
        Darwin) printf '%s\n' darwin ;;
        *)
            printf 'PLATFORM_UNSUPPORTED:%s|%s\n' "$s" "$(uname -m)" >&2
            return 1
            ;;
    esac
}

platform_arch() {
    local m="${1:-$(uname -m)}"
    case "$m" in
        x86_64|amd64)  printf '%s\n' amd64 ;;
        aarch64|arm64) printf '%s\n' arm64 ;;
        *)
            printf 'PLATFORM_UNSUPPORTED:%s|%s\n' "$(uname -s)" "$m" >&2
            return 1
            ;;
    esac
}

platform_asset_suffix() {
    local s="${1:-$(uname -s)}" m="${2:-$(uname -m)}" os arch
    # Report the pair actually examined (not the live uname the single-field
    # helpers would name), exactly once.
    if ! os="$(platform_os "$s" 2>/dev/null)" ||
       ! arch="$(platform_arch "$m" 2>/dev/null)"; then
        printf 'PLATFORM_UNSUPPORTED:%s|%s\n' "$s" "$m" >&2
        return 1
    fi
    printf '%s_%s\n' "$os" "$arch"
}
