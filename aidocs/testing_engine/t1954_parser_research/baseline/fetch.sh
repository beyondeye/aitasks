#!/usr/bin/env bash
# fetch.sh — extract the pinned, immutable goengines baseline for the t1954
# parser research.
#
#   baseline/fetch.sh               -> .baseline/            (seam.patch applied)
#   baseline/fetch.sh --unpatched   -> .baseline-unpatched/  (no patch; guard input)
#
# The source is `git archive <commit> goengines` from the object store, never
# the working tree, so uncommitted edits by concurrent sessions cannot reach a
# measurement. Every identity check fails closed: a commit whose goengines tree
# differs from PIN, or a seam.patch whose sha256 differs from PIN, refuses to
# produce a snapshot. The result is renamed into place only when complete.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(dirname "$here")" # the research dir
die() { echo "fetch.sh: $*" >&2; exit 2; }

mode=patched
case "${1:-}" in
    "") ;;
    --unpatched) mode=unpatched ;;
    *) die "usage: fetch.sh [--unpatched]" ;;
esac

pin() { sed -n "s/^$1: *//p" "$here/PIN" | head -n1; }
commit="$(pin commit)"
tree="$(pin tree)"
seam_sha="$(pin seam_sha256)"
[[ -n "$commit" && -n "$tree" && -n "$seam_sha" ]] || die "PIN is missing commit/tree/seam_sha256"

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
    else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

top="$(git -C "$root" rev-parse --show-toplevel)"
git -C "$top" cat-file -e "$commit^{commit}" 2>/dev/null || die "pinned commit $commit is not in this repository"
actual_tree="$(git -C "$top" rev-parse "$commit:goengines")"
[[ "$actual_tree" == "$tree" ]] || die "IDENTITY mismatch: $commit:goengines is $actual_tree, PIN says $tree"

if [[ "$mode" == patched ]]; then
    dest="$root/.baseline"
    actual_sha="$(sha256 "$here/seam.patch")"
    [[ "$actual_sha" == "$seam_sha" ]] || die "IDENTITY mismatch: seam.patch sha256 is $actual_sha, PIN says $seam_sha"
    id_seam="$seam_sha"
else
    dest="$root/.baseline-unpatched"
    id_seam="none"
fi

tmp="$(mktemp -d "$root/.baseline.tmp.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
git -C "$top" archive "$commit" goengines | tar -x -C "$tmp"
if [[ "$mode" == patched ]]; then
    (cd "$tmp" && patch -p1 --forward --batch --quiet <"$here/seam.patch") || die "seam.patch does not apply to $commit"
fi
# content_sha256: every snapshot file's sha256, in byte order of path, as
# "<hex>  <path>" lines, hashed again — re-checked by the harness on every
# run, so an edit inside the extracted snapshot is refused too.
content="$(cd "$tmp" && find goengines -type f -print | LC_ALL=C sort | while IFS= read -r f; do
    printf '%s  %s\n' "$(sha256 "$f")" "$f"
done | { if command -v sha256sum >/dev/null 2>&1; then sha256sum; else shasum -a 256; fi; } | cut -d' ' -f1)"
printf 'commit: %s\ntree: %s\nseam_sha256: %s\ncontent_sha256: %s\n' "$commit" "$tree" "$id_seam" "$content" >"$tmp/IDENTITY"

old=""
if [[ -e "$dest" ]]; then
    old="$dest.old.$$"
    mv "$dest" "$old"
fi
mv "$tmp" "$dest"
trap - EXIT
[[ -z "$old" ]] || rm -rf "$old"
echo "BASELINE:$mode|$commit|$tree|$id_seam -> ${dest#"$root"/}"
