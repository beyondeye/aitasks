#!/usr/bin/env bash
# fetch.sh — fetch the pinned C grammar sources for the tree-sitter reference
# providers (tscgo, tswasm) into .tsref/ (git-ignored).
#
#   tsref/fetch.sh                -> .tsref/<repo>/ at each LOCK commit, verified
#   tsref/fetch.sh --print-sums   -> fetch, then print srcsum lines for LOCK
#
# Every check fails closed (exit 2): a fetched HEAD that is not the pinned
# commit, a generator CLI whose version differs from LOCK, or a source tree
# whose srcsum differs from LOCK. The result is renamed into place only when
# complete. Network access is needed for `git fetch`.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(dirname "$here")"
die() { echo "tsref/fetch.sh: $*" >&2; exit 2; }

print=0
case "${1:-}" in
    "") ;;
    --print-sums) print=1 ;;
    *) die "usage: fetch.sh [--print-sums]" ;;
esac

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum | cut -d' ' -f1
    else shasum -a 256 | cut -d' ' -f1; fi
}

# srcsum <dir>: sha256 over "<sha256>  <relpath>" of every file under dir.
srcsum() {
    (cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | while IFS= read -r -d '' f; do
        printf '%s  %s\n' "$(sha256 <"$f")" "$f"
    done) | sha256
}

lock="$here/LOCK"
tmp="$(mktemp -d "$root/.tsref.tmp.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

while read -r kind name url commit; do
    [[ "$kind" == repo ]] || continue
    d="$tmp/$name"
    mkdir -p "$d"
    git -C "$d" init -q
    git -C "$d" fetch -q --depth 1 "$url" "$commit" || die "cannot fetch $url $commit"
    git -C "$d" -c advice.detachedHead=false checkout -q FETCH_HEAD
    got="$(git -C "$d" rev-parse HEAD)"
    [[ "$got" == "$commit" ]] || die "$name: fetched $got, LOCK says $commit"
    rm -rf "$d/.git"
done <"$lock"

want_gen="$(sed -n 's/^generator tree-sitter //p' "$lock")"
while read -r kind name _; do
    [[ "$kind" == generate ]] || continue
    have="$(tree-sitter --version 2>/dev/null | awk '{print $2}')" || true
    [[ "$have" == "$want_gen" ]] || die "$name needs tree-sitter $want_gen to generate its parser (have '${have:-none}')"
    (cd "$tmp/$name" && tree-sitter generate src/grammar.json >/dev/null 2>&1) || die "$name: tree-sitter generate failed"
done <"$lock"

status=0
while read -r kind repo dir; do
    [[ "$kind" == grammar ]] || continue
    key="$repo/$dir"
    [[ -f "$tmp/$key/parser.c" ]] || die "$key: no parser.c"
    sum="$(srcsum "$tmp/$key")"
    if [[ $print == 1 ]]; then
        echo "srcsum $key $sum"
        continue
    fi
    want="$(awk -v k="$key" '$1 == "srcsum" && $2 == k {print $3}' "$lock")"
    [[ -n "$want" ]] || die "$key: no srcsum in LOCK"
    [[ "$sum" == "$want" ]] || { echo "tsref/fetch.sh: $key: srcsum $sum, LOCK says $want" >&2; status=2; }
done < <(awk '$1 == "grammar" {print "grammar", $3, $4}' "$lock")
# typescript/tsx scanners include ../../common/scanner.h: pin that dir too.
common="tree-sitter-typescript/common"
csum="$(srcsum "$tmp/$common")"
if [[ $print == 1 ]]; then
    echo "srcsum $common $csum"
    exit 0
fi
want="$(awk -v k="$common" '$1 == "srcsum" && $2 == k {print $3}' "$lock")"
[[ "$csum" == "$want" ]] || { echo "tsref/fetch.sh: $common: srcsum $csum, LOCK says ${want:-none}" >&2; status=2; }
[[ $status == 0 ]] || exit 2

rm -rf "$root/.tsref"
mv "$tmp" "$root/.tsref"
trap - EXIT
echo "TSREF:ok -> .tsref"
