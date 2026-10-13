#!/usr/bin/env bash
# gen.sh - regenerate the committed ANTLR4 Go lexers of the t1954_3 `antlr`
# provider from the pins in antlr/LOCK.
#
#   antlr/gen.sh <scratch-dir>           download + verify + generate into provider/antlrgen/
#   antlr/gen.sh --check <scratch-dir>   regenerate into a temp dir and require byte-identity
#
# Needs network (the tool jar and grammars-v4 files, sha256-verified), java
# (JDK 11+) and python3. Nothing is installed system-wide. Per-language
# target work (the maintenance cost the findings record):
#   - Kotlin (Apache-2.0, kotlin/kotlin/LICENSE), Java (BSD, grammar header):
#     target-neutral lexer grammars, generated as-is;
#   - Rust (MIT, grammar header): grammars-v4 ships a Go base class (rust/Go/rust_lexer_base.go) and
#     a transform (rust/Go/transformGrammar.py) that rewrites `this.` to `p.`
#     in predicates and `l.` in actions; both are applied here, and the base
#     file's `package parser` is renamed to the generated package;
#   - TypeScript: grammars-v4 has NO Go target base class, so it is not
#     generated (it would need a hand-written Go base).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
die() { echo "gen.sh: $*" >&2; exit 1; }
check=0
if [[ "${1:-}" == "--check" ]]; then check=1; shift; fi
scratch="${1:?usage: gen.sh [--check] <scratch-dir>}"
mkdir -p "$scratch"
lock="$here/LOCK"
jar_url=$(sed -n 's/^tool: \([^ ]*\) .*/\1/p' "$lock")
jar_sha=$(sed -n 's/^tool: .* sha256=\(.*\)/\1/p' "$lock")
commit=$(sed -n 's/^grammars_v4: //p' "$lock")
jar="$scratch/$(basename "$jar_url")"
[[ -f "$jar" ]] || curl -sSfL -o "$jar" "$jar_url"
[[ "$(sha256sum "$jar" | cut -d' ' -f1)" == "$jar_sha" ]] || die "tool jar sha256 mismatch: $jar"
g="$scratch/grammars-v4-$commit"
while read -r _ f sha; do
  sha="${sha#sha256=}"
  mkdir -p "$g/$(dirname "$f")"
  [[ -f "$g/$f" ]] || curl -sSfL -o "$g/$f" "https://raw.githubusercontent.com/antlr/grammars-v4/$commit/$f"
  [[ "$(sha256sum "$g/$f" | cut -d' ' -f1)" == "$sha" ]] || die "sha256 mismatch: $f"
done < <(grep '^file: ' "$lock")

out="$root/provider/antlrgen"
if (( check )); then out="$(mktemp -d)"; fi
work="$(mktemp -d)"
trap 'rm -rf "$work"; if (( check )); then rm -rf "$out"; fi' EXIT
gen() { # <lang> <package> <grammar dir> <grammar file>
  local lang=$1 pkg=$2 dir=$3 file=$4
  rm -rf "${out:?}/${lang:?}"; mkdir -p "$out/$lang" "$work/$lang"
  cp "$g/$dir"/*.g4 "$work/$lang/"
  (cd "$work/$lang" && java -jar "$jar" -Dlanguage=Go -package "$pkg" -o gen "$file") || die "generation failed: $file"
  cp "$work/$lang/gen/"*.go "$out/$lang/"
}
gen kotlin antlrkotlin kotlin/kotlin KotlinLexer.g4
gen java antlrjava java/java JavaLexer.g4
# Rust: the grammars-v4 Go transform (transformGrammar.py, reproduced as sed):
# `this.` -> `p.` on predicate lines ("}?"), `l.` elsewhere.
mkdir -p "$work/rust"
sed -e '/}?/s/this\./p./g' -e '/}?/!s/this\./l./g' "$g/rust/RustLexer.g4" > "$work/RustLexer.g4"
rm -rf "${out:?}/rust"; mkdir -p "$out/rust"
(cd "$work" && java -jar "$jar" -Dlanguage=Go -package antlrrust -o rustgen RustLexer.g4) || die "generation failed: RustLexer.g4"
cp "$work/rustgen/"*.go "$out/rust/"
# Copy the base: rename the package; drop the trailing `return false` after
# FloatLiteralPossible's exhaustive switch (unreachable: `go vet` refuses it);
# gofmt (upstream indents with spaces).
{ echo "// Copied from antlr/grammars-v4@$commit rust/Go/rust_lexer_base.go; the rust grammar"
  echo "// directory is MIT (rust/RustLexer.g4 header; no separate LICENSE file). Changed: the package"
  echo "// clause, one unreachable \`return false\` removed (go vet), gofmt."
  sed 's/^package parser$/package antlrrust/' "$g/rust/Go/rust_lexer_base.go" |
    python3 -c 'import sys,re; s=sys.stdin.read(); t=re.sub(r"(\n    default:\n        return true\n    \}\n)\n    return false\n\}", r"\1}", s, count=1); sys.exit("gen.sh: the unreachable return was not found") if t == s else sys.stdout.write(t)'
} > "$out/rust/rust_lexer_base.go"
gofmt -w "$out/rust/rust_lexer_base.go"
if (( check )); then
  if diff -r "$out" "$root/provider/antlrgen"; then echo "ANTLRGEN:identical"; else die "regenerated Go differs from provider/antlrgen"; fi
else
  echo "ANTLRGEN:$out|tool=$(basename "$jar")|grammars-v4=$commit"
fi
