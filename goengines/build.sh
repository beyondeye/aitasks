#!/usr/bin/env bash
# build.sh — the single build and release-matrix command for every Go
# executable under goengines/cmd/.
#
#   goengines/build.sh [--version V] [--commit SHA] [--out DIR] [TARGET...]
#
# TARGET (default: host)
#   all          the release matrix linux_amd64 linux_arm64 darwin_amd64
#                darwin_arm64, plus <name>_<V>_SHA256SUMS.txt per executable
#   host         this machine's $(go env GOOS)_$(go env GOARCH)
#   <os>_<arch>  any pair Go supports (off-matrix hosts build from source)
#
# --version  build identity (default: the contents of .aitask-scripts/VERSION)
# --commit   build commit (default: git rev-parse HEAD, else "unknown")
# --out      output directory (default: goengines/dist; a relative path
#            resolves from the caller's working directory)
#
# Every binary is <name>_<V>_<os>_<arch>, built with CGO_ENABLED=0 -trimpath
# -buildvcs=false -ldflags "-s -w -X main.version=<V> -X main.commit=<sha>".
# The engine contract is a source constant, never an ldflag.
#
# stdout: BUILT:<abs path> per binary, SUMS:<abs path> per sums file.
# Progress goes to stderr. Exit 0 ok, 1 build failure or an unusable VERSION
# file, 2 usage (including an explicitly empty option value).
set -euo pipefail

readonly MATRIX=(linux_amd64 linux_arm64 darwin_amd64 darwin_arm64)

usage() {
    echo "USAGE:$1" >&2
    echo "usage: goengines/build.sh [--version V] [--commit SHA] [--out DIR] [all | host | <os>_<arch> ...]" >&2
    exit 2
}

die() {
    echo "ERROR:$1" >&2
    exit 1
}

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# An option given explicitly must carry a non-empty value: an empty one is a
# usage error, never a silent fall-back to the default.
version="" commit="" out=""
version_set=0 commit_set=0 out_set=0
targets=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version|--commit|--out)
            [[ $# -ge 2 && -n "$2" ]] || usage "$1 needs a non-empty value"
            case "$1" in
                --version) version="$2" version_set=1 ;;
                --commit)  commit="$2"  commit_set=1 ;;
                --out)     out="$2"     out_set=1 ;;
            esac
            shift 2 ;;
        -h|--help) sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*)        usage "unknown option: $1" ;;
        *)         targets+=("$1"); shift ;;
    esac
done

[[ ${#targets[@]} -gt 0 ]] || targets=(host)
for t in "${targets[@]}"; do
    [[ "$t" =~ ^(all|host|[a-z0-9]+_[a-z0-9]+)$ ]] || usage "bad target: $t"
    [[ "$t" != all || ${#targets[@]} -eq 1 ]] || usage "all cannot be combined with other targets"
done

# The version lands in a filename and inside -ldflags, where a space would
# split the flag list.
readonly VERSION_RE='^[A-Za-z0-9._+-]+$'
if [[ "$version_set" -eq 1 ]]; then
    [[ "$version" =~ $VERSION_RE ]] || usage "bad version: $version"
else
    vfile="$here/../.aitask-scripts/VERSION"
    [[ -r "$vfile" ]] || die "no --version and $vfile is unreadable"
    # Strip only the line ending ($(...) drops trailing newlines, then one CR);
    # any other whitespace is malformed content, never silently removed.
    version="$(<"$vfile")"
    version="${version%$'\r'}"
    [[ -n "$version" ]] || die "$vfile is empty"
    [[ "$version" =~ $VERSION_RE ]] || die "$vfile is malformed: '$version'"
fi

if [[ "$commit_set" -eq 0 ]]; then
    commit="$(git -C "$here" rev-parse HEAD 2>/dev/null)" || commit=unknown
fi
[[ "$commit" =~ ^[A-Za-z0-9]+$ ]] || usage "bad commit: $commit"

# Resolve --out against the caller's directory before moving to the module.
[[ "$out_set" -eq 1 ]] || out="$here/dist"
mkdir -p "$out"
out="$(cd "$out" && pwd)"

cd "$here"
command -v go >/dev/null 2>&1 || die "go not found on PATH"
go version >&2

cmds=()
for d in cmd/*/; do
    compgen -G "$d*.go" >/dev/null || continue
    cmds+=("$(basename "$d")")
done
[[ ${#cmds[@]} -gt 0 ]] || die "no executables under goengines/cmd/"

if [[ "${targets[0]}" == all ]]; then
    targets=("${MATRIX[@]}")
    want_sums=1
else
    want_sums=0
    for i in "${!targets[@]}"; do
        [[ "${targets[$i]}" == host ]] && targets[i]="$(go env GOOS)_$(go env GOARCH)"
    done
fi

sha256_line() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1"
    else
        die "neither sha256sum nor shasum is available"
    fi
}

ldflags="-s -w -X main.version=$version -X main.commit=$commit"
for name in "${cmds[@]}"; do
    built=()
    for t in "${targets[@]}"; do
        os="${t%%_*}" arch="${t#*_}"
        bin="${name}_${version}_${os}_${arch}"
        echo "building $bin" >&2
        CGO_ENABLED=0 GOOS="$os" GOARCH="$arch" go build -trimpath -buildvcs=false \
            -ldflags "$ldflags" -o "$out/$bin" "./cmd/$name" || die "build failed: $bin"
        echo "BUILT:$out/$bin"
        built+=("$bin")
    done
    if [[ "$want_sums" -eq 1 ]]; then
        sums="${name}_${version}_SHA256SUMS.txt"
        tmp="$out/.$sums.tmp"
        (
            cd "$out"
            for b in $(printf '%s\n' "${built[@]}" | LC_ALL=C sort); do
                sha256_line "$b"
            done
        ) > "$tmp" || { rm -f "$tmp"; die "checksum failed: $sums"; }
        mv -f "$tmp" "$out/$sums"
        echo "SUMS:$out/$sums"
    fi
done
