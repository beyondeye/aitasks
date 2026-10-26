#!/usr/bin/env bash
# dashcheck.sh — run the hang-guard preflight and the Go suite with dash as
# /bin/sh, locally, before a push. Never shipped: build.sh builds only cmd/*.
#
# GitHub-hosted ubuntu runners use dash as /bin/sh; a dev box often uses bash.
# The two differ in ways tests can trip over: `dash -c "sleep 300"` forks
# sleep instead of exec'ing it, so a pid-only kill of the shell leaves sleep
# behind. That passed every local run and leaked on every hosted run (t2148).
#
#   dashcheck.sh [--stress N] [--] [go test args...]     (default: ./...)
#
# It runs ./ci/preflight.sh and then `go test -count=1 <args>` in an
# ubuntu:24.04 container shaped like the hosted runner: dash /bin/sh, git from
# ppa:git-core/ppa (as the runner images install it), python3 with the pinned
# pytest of the CI check job, AIT_TESTMAP_REQUIRE_REAL_TOOLS=1, a non-root uid
# and --init. The host's Go toolchain, module cache (both read-only) and build
# cache are mounted at their own paths, with the module read-only, and the
# container runs offline (--network none, GOPROXY=off). The preparation on the
# host is what may download: `go mod download` fetches modules missing from the
# cache, and the image is built once per Dockerfile content.
#
# -count=1 always comes first: the build cache is the host's, and the test
# cache does not key on which /bin/sh a test exec'd, so without it a result
# cached by a bash run would replay here as "ok (cached)". An explicit
# -count=N among the arguments still wins (the last flag does).
#
# --stress N (1-99): --cpus 1 plus N busy loops in the container, which
# amplifies races that only lose on a loaded runner.
#
# Container output goes to stderr. The only stdout line is the verdict:
#   DASHCHECK:PASS                                     exit 0
#   DASHCHECK:FAIL:<probe|preflight|suite>:<rc>        exit 1
#   DASHCHECK:FAIL:internal:<rc>                       exit 1 (this script
#       stopped on an error no other verdict covers)
#   DASHCHECK:NOT_RUN:<reason>                         exit 3, never a pass:
#       no-docker | docker-unreachable | no-go | not-linux |
#       unmountable-path | cache-unusable | modules-unavailable |
#       image-build-failed
#   usage error                                        exit 2
# The probe fails when the container's /bin/sh is not dash (the parity this
# check claims is not there) or the host Go cannot run in it.
#
# AIT_DASHCHECK_DOCKER names the docker command (default: docker).
set -euo pipefail

decided=""

# Every exit prints a verdict: one that no other path decided is an internal
# failure, never silence (which a caller could not tell from a pass).
# shellcheck disable=SC2329  # invoked by the EXIT trap
on_exit() {
    local rc=$?
    if [[ -z "$decided" ]]; then
        echo "DASHCHECK:FAIL:internal:$rc"
        exit 1
    fi
}
trap on_exit EXIT

usage() {
    decided=usage
    echo "usage: dashcheck.sh [--stress N] [--] [go test args...]" >&2
    exit 2
}

verdict() {
    decided="$1"
    echo "DASHCHECK:$1"
    exit "$2"
}

not_run() {
    echo "dashcheck: not run: $2" >&2
    verdict "NOT_RUN:$1" 3
}

stress=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stress)
            # Bounded before any arithmetic: a long digit string wraps.
            [[ $# -ge 2 && "$2" =~ ^[1-9][0-9]?$ ]] || usage
            stress="$2"
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            break
            ;;
    esac
done
args=("$@")
[[ ${#args[@]} -gt 0 ]] || args=(./...)

DOCKER="${AIT_DASHCHECK_DOCKER:-docker}"
command -v "$DOCKER" >/dev/null 2>&1 || not_run no-docker "'$DOCKER' is not on PATH"
"$DOCKER" info >/dev/null 2>&1 || not_run docker-unreachable "'$DOCKER info' failed (is the daemon running?)"

cd "$(dirname "${BASH_SOURCE[0]}")/.."
module="$(pwd -P)"

command -v go >/dev/null 2>&1 || not_run no-go "go is not on PATH"
goenv="$(go env GOHOSTOS GOROOT GOCACHE GOMODCACHE)" || not_run no-go "'go env' failed"
{ read -r hostos && read -r goroot && read -r gocache && read -r gomodcache; } <<<"$goenv" \
    || not_run no-go "'go env' printed fewer than 4 lines"
# The host toolchain runs inside a Linux container.
[[ "$hostos" == linux ]] || not_run not-linux "the host Go is $hostos/; the container needs a linux toolchain"
for p in "$module" "$goroot" "$gocache" "$gomodcache"; do
    [[ "$p" == /* && "$p" != *:* ]] || not_run unmountable-path "'$p' is not an absolute path without ':'"
done

mkdir -p "$gocache" 2>/dev/null && [[ -w "$gocache" ]] \
    || not_run cache-unusable "GOCACHE '$gocache' is not a writable directory"
go mod download >&2 || not_run modules-unavailable "'go mod download' failed; the container has no network"

dockerfile='FROM ubuntu:24.04
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends software-properties-common gpg-agent ca-certificates \
 && add-apt-repository -y ppa:git-core/ppa \
 && apt-get install -y --no-install-recommends git python3 python3-pip \
 && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --break-system-packages --no-cache-dir pytest==8.4.2 pytest-xdist==3.8.0
'
image="aitasks-dashcheck:$(printf '%s' "$dockerfile" | sha256sum | cut -c1-12)"
if ! "$DOCKER" image inspect "$image" >/dev/null 2>&1; then
    echo "dashcheck: building $image (once per Dockerfile content)" >&2
    printf '%s' "$dockerfile" | "$DOCKER" build -t "$image" - >&2 \
        || not_run image-build-failed "'$DOCKER build' failed"
fi

run=(run --rm --init --network none --user "$(id -u):$(id -g)"
    -v "$goroot:$goroot:ro" -v "$gomodcache:$gomodcache:ro" -v "$gocache:$gocache"
    -v "$module:$module:ro" -w "$module"
    -e HOME=/tmp -e "PATH=$goroot/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    -e "GOROOT=$goroot" -e "GOCACHE=$gocache" -e "GOMODCACHE=$gomodcache"
    -e GOTOOLCHAIN=local -e GOPROXY=off -e GOFLAGS=-mod=readonly -e CGO_ENABLED=0
    -e AIT_TESTMAP_REQUIRE_REAL_TOOLS=1)
[[ "$stress" -eq 0 ]] || run+=(--cpus 1)

rc=0
probe="$("$DOCKER" "${run[@]}" "$image" sh -c 'readlink -f /bin/sh && go version')" || rc=$?
printf '%s\n' "$probe" >&2
if [[ "$rc" -ne 0 ]]; then
    echo "dashcheck: the probe failed: the host Go may not run in the container (a dynamically linked distro build?)" >&2
    verdict "FAIL:probe:$rc" 1
fi
sh_path="${probe%%$'\n'*}"
if [[ "${sh_path##*/}" != dash ]]; then
    echo "dashcheck: /bin/sh in the container is '$sh_path', not dash: no parity to check" >&2
    verdict "FAIL:probe:$rc" 1
fi

"$DOCKER" "${run[@]}" "$image" ./ci/preflight.sh >&2 || verdict "FAIL:preflight:$?" 1

suite=(go test -count=1 "${args[@]}")
if [[ "$stress" -gt 0 ]]; then
    # dash runs this; the loops die with the container (--init).
    # shellcheck disable=SC2016  # expanded by the container's sh, not here
    suite=(sh -c 'n=$1; shift; i=0
while [ "$i" -lt "$n" ]; do (while :; do :; done) & i=$((i + 1)); done
exec "$@"' dashcheck-stress "$stress" "${suite[@]}")
fi
"$DOCKER" "${run[@]}" "$image" "${suite[@]}" >&2 || verdict "FAIL:suite:$?" 1

verdict PASS 0
