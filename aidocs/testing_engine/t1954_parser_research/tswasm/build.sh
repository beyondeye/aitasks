#!/usr/bin/env bash
# build.sh — build .tswasm/ts.wasm: one WASI reactor module holding the
# tree-sitter C runtime (go-tree-sitter v0.25.0's vendored src/lib.c — the
# runtime tscgo uses), the pinned grammars from .tsref/ (tsref/fetch.sh) and
# tswasm/shim.c, with go-tree-sitter's own CFLAGS. The tswasm provider loads it
# with wazero.
#
#   tswasm/build.sh <zig>     e.g. a zig 0.17.0 release unpacked in a scratch dir
#
# Prints the module's size and sha256. Fails (exit 2) on a missing input.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(dirname "$here")"
die() { echo "tswasm/build.sh: $*" >&2; exit 2; }
zig="${1:?usage: build.sh <path-to-zig>}"
[[ -x "$zig" ]] || die "not executable: $zig"
[[ -d "$root/.tsref" ]] || die "run tsref/fetch.sh first"
gts="$(cd "$root" && go list -m -f '{{.Dir}}' github.com/tree-sitter/go-tree-sitter)" || die "go-tree-sitter not in the module graph"
ref="$root/.tsref"
mkdir -p "$root/.tswasm"
obj="$(mktemp -d "$root/.tswasm/obj.XXXXXX")"
trap 'rm -rf "$obj"' EXIT
flags=(--target=wasm32-wasi-musl -O2 -w -std=c11 -D_POSIX_C_SOURCE=200112L -D_DEFAULT_SOURCE -DHAVE_ENDIAN_H)
# Each translation unit gets its own include path (a grammar's
# tree_sitter/parser.h, the runtime's include/), as the cgo build does.
cc() { "$zig" cc "${flags[@]}" -I"$2" -c "$1" -o "$obj/$3.o" || die "compile failed: $1"; }
"$zig" cc "${flags[@]}" -I"$gts/include" -I"$gts/src" -c "$gts/src/lib.c" -o "$obj/runtime.o" || die "compile failed: lib.c"
"$zig" cc "${flags[@]}" -I"$gts/include" -c "$here/shim.c" -o "$obj/shim.o" || die "compile failed: shim.c"
n=0
for d in tree-sitter-bash/src tree-sitter-python/src tree-sitter-go/src tree-sitter-kotlin/src \
    tree-sitter-typescript/typescript/src tree-sitter-typescript/tsx/src tree-sitter-javascript/src \
    tree-sitter-java/src tree-sitter-rust/src tree-sitter-swift/src; do
    n=$((n + 1))
    cc "$ref/$d/parser.c" "$ref/$d" "g${n}_parser"
    [[ -f "$ref/$d/scanner.c" ]] && cc "$ref/$d/scanner.c" "$ref/$d" "g${n}_scanner"
done
out="$root/.tswasm/ts.wasm"
"$zig" cc --target=wasm32-wasi-musl -mexec-model=reactor -O2 "$obj"/*.o -o "$out" \
    -Wl,--export=malloc -Wl,--export=free -Wl,--strip-debug -Wl,-z,stack-size=1048576 || die "link failed"
size=$(stat -c %s "$out" 2>/dev/null || stat -f %z "$out")
sum=$(sha256sum "$out" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "$out" | cut -d' ' -f1)
echo "TSWASM:$out|size=$size|sha256=$sum|zig=$("$zig" version)"
