#!/usr/bin/env bash
# functional_probes.sh — t1954_1 pre-phase feasibility_smoke (functional half).
#
#   feasibility/functional_probes.sh <work-dir>
#
# Each probe module PARSES real input with one candidate (not a blank import:
# dead-code elimination would let a cgo-only package "build" under
# CGO_ENABLED=0). Every probe is built CGO_ENABLED=0 -trimpath for the four
# release targets; the official cgo binding is also built with cgo. Results go
# to <work-dir>/fn_results.tsv and module versions to <work-dir>/versions.txt.
# Network access (go get) is required; nothing is installed outside <work-dir>
# and the Go module cache.
# Row: name  cgo  target  build  size  host-run-output  build-error
set -uo pipefail
work=${1:?usage: functional_probes.sh <work-dir>}
mkdir -p "$work" && cd "$work" || exit 2
out=$PWD/fn_results.tsv; : > "$out"
row() { printf '%s\n' "$(IFS=$'\t'; echo "$*")" >> "$out"; }
mk() { # name deps... ; main.go from stdin
  local name=$1; shift
  rm -rf "$name"; mkdir "$name"; cat > "$name/main.go"
  (cd "$name" && go mod init "fn/$name" >/dev/null 2>&1 && for d in "$@"; do go get "$d" >/dev/null 2>&1 || echo "GETFAIL $d" >&2; done && go mod tidy >/dev/null 2>&1)
}
build() { # name tags cgo label
  local name=$1 tags=$2 cgo=$3 lbl=$4
  for t in linux/amd64 linux/arm64 darwin/amd64 darwin/arm64; do
    local os=${t%/*} arch=${t#*/} log rc=0
    log=$(cd "$name" && CGO_ENABLED=$cgo GOOS=$os GOARCH=$arch go build -buildvcs=false -trimpath -tags "$tags" -o "bin_${os}_${arch}" . 2>&1) || rc=$?
    local size=- run=-
    if [ $rc -eq 0 ]; then
      size=$(stat -c %s "$name/bin_${os}_${arch}")
      if [ "$t" = "$(go env GOOS)/$(go env GOARCH)" ]; then run=$("$name/bin_${os}_${arch}" 2>&1 | tr '\t\n' '  ' | cut -c1-400); fi
    fi
    row "$lbl" "cgo=$cgo" "$t" "$([ $rc -eq 0 ] && echo pass || echo fail)" "$size" "${run:--}" "$(echo "$log" | grep -v '^#' | head -2 | tr '\t\n' '  ' | cut -c1-200)"
  done
}
# shellcheck disable=SC2016  # Go source text: $ must not expand
SNIP='var snip = map[string]string{
	"bash":       "x=$(cat <<EOF\n# testmap:covers fake\nEOF\n)\n# testmap:covers real\n",
	"python":     "s = \"\"\"\n# testmap:covers fake\n\"\"\"\n# testmap:covers real\n",
	"go":         "package p\nvar s = `\n// testmap:covers fake\n`\n// testmap:covers real\n",
	"kotlin":     "val s = \"\"\"\n// testmap:covers fake ${1}\n\"\"\"\n// testmap:covers real\n",
	"typescript": "const s = `${1}\n// testmap:covers fake\n`;\n// testmap:covers real\n",
	"javascript": "const s = `${1}\n// testmap:covers fake\n`;\n// testmap:covers real\n",
	"java":       "class C { String s = \"\"\"\n// testmap:covers fake\n\"\"\"; }\n// testmap:covers real\n",
	"rust":       "const S: &str = r#\"\n// testmap:covers fake\n\"#;\n// testmap:covers real\n",
	"swift":      "let s = #\"\"\"\n// testmap:covers fake\n\"\"\"#\n// testmap:covers real\n",
}'

mk gotreesitter github.com/odvcencio/gotreesitter@v0.55.1 <<GOSRC
package main

import (
	"fmt"
	"sort"
	"strings"

	gts "github.com/odvcencio/gotreesitter"
	"github.com/odvcencio/gotreesitter/grammars"
)

$SNIP

func count(n *gts.Node, lang *gts.Language, typ string) int {
	c := 0
	if strings.Contains(n.Type(lang), typ) {
		c++
	}
	for i := 0; i < n.ChildCount(); i++ {
		c += count(n.Child(i), lang, typ)
	}
	return c
}

func main() {
	langs := map[string]func() *gts.Language{
		"bash": grammars.BashLanguage, "python": grammars.PythonLanguage, "go": grammars.GoLanguage,
		"kotlin": grammars.KotlinLanguage, "typescript": grammars.TypescriptLanguage, "javascript": grammars.JavascriptLanguage,
		"java": grammars.JavaLanguage, "rust": grammars.RustLanguage, "swift": grammars.SwiftLanguage,
	}
	var names []string
	for k := range langs {
		names = append(names, k)
	}
	sort.Strings(names)
	for _, k := range names {
		l := langs[k]()
		tree, err := gts.NewParser(l).Parse([]byte(snip[k]))
		if err != nil {
			fmt.Printf("%s:ERR(%v) ", k, err)
			continue
		}
		r := tree.RootNode()
		fmt.Printf("%s:err=%v,comments=%d ", k, r.HasErrorOrMissing(), count(r, l, "comment"))
	}
}
GOSRC
build gotreesitter "" 0 gotreesitter_all
build gotreesitter "grammar_subset grammar_subset_bash grammar_subset_python grammar_subset_go grammar_subset_kotlin grammar_subset_typescript grammar_subset_javascript grammar_subset_java grammar_subset_rust grammar_subset_swift" 0 gotreesitter_subset8

mk chroma github.com/alecthomas/chroma/v2@latest <<GOSRC
package main

import (
	"fmt"
	"sort"

	"github.com/alecthomas/chroma/v2"
	"github.com/alecthomas/chroma/v2/lexers"
)

$SNIP

func main() {
	var names []string
	for k := range snip {
		names = append(names, k)
	}
	sort.Strings(names)
	for _, k := range names {
		lx := lexers.Get(k)
		if lx == nil {
			fmt.Printf("%s:NOLEXER ", k)
			continue
		}
		it, err := lx.Tokenise(nil, snip[k])
		if err != nil {
			fmt.Printf("%s:ERR ", k)
			continue
		}
		c, e := 0, 0
		for t := it(); t != chroma.EOF; t = it() {
			if t.Type.InCategory(chroma.Comment) {
				c++
			}
			if t.Type == chroma.Error {
				e++
			}
		}
		fmt.Printf("%s:comments=%d,errtok=%d ", k, c, e)
	}
}
GOSRC
build chroma "" 0 chroma

mk mvdansh mvdan.cc/sh/v3@latest <<'GOSRC'
package main

import (
	"fmt"
	"strings"

	"mvdan.cc/sh/v3/syntax"
)

func main() {
	src := "x=$(cat <<EOF\n# testmap:covers fake\nEOF\n)\n# testmap:covers real\n"
	f, err := syntax.NewParser(syntax.KeepComments(true)).Parse(strings.NewReader(src), "")
	if err != nil {
		fmt.Println("ERR", err)
		return
	}
	n := 0
	syntax.Walk(f, func(node syntax.Node) bool {
		if c, ok := node.(*syntax.Comment); ok {
			n++
			fmt.Printf("comment@%d:%q ", c.Pos().Offset(), c.Text)
		}
		return true
	})
	fmt.Printf("comments=%d ", n)
	_, err = syntax.NewParser().Parse(strings.NewReader("cat <<EOF\nunterminated\n"), "")
	fmt.Printf("malformed_err=%v", err != nil)
}
GOSRC
build mvdansh "" 0 mvdansh

mk antlr4 github.com/antlr4-go/antlr/v4@latest <<'GOSRC'
package main

import (
	"fmt"

	"github.com/antlr4-go/antlr/v4"
)

// Runtime only: a lexer for a target language must be GENERATED from a
// grammars-v4 .g4 with the ANTLR tool (Java) — t1954_3's prototype.
func main() {
	in := antlr.NewInputStream("val x = 1 // c\n")
	fmt.Printf("runtime-ok size=%d (no generated lexer)", in.Size())
}
GOSRC
build antlr4 "" 0 antlr4

mk wazero github.com/tetratelabs/wazero@latest <<'GOSRC'
package main

import (
	"context"
	"fmt"

	"github.com/tetratelabs/wazero"
)

func main() {
	ctx := context.Background()
	r := wazero.NewRuntime(ctx)
	defer r.Close(ctx)
	_, err := r.Instantiate(ctx, []byte("\x00asm\x01\x00\x00\x00"))
	fmt.Printf("instantiate-empty-module err=%v", err)
}
GOSRC
build wazero "" 0 wazero

mk malivvan github.com/malivvan/tree-sitter@v0.0.1 <<'GOSRC'
package main

import (
	"context"
	"fmt"

	ts "github.com/malivvan/tree-sitter"
)

func main() {
	ctx := context.Background()
	t, err := ts.New(ctx)
	if err != nil {
		fmt.Println("ERR new", err)
		return
	}
	p, err := t.NewParser(ctx)
	if err != nil {
		fmt.Println("ERR parser", err)
		return
	}
	l, err := t.LanguageC(ctx)
	if err != nil {
		fmt.Println("ERR lang", err)
		return
	}
	if err := p.SetLanguage(ctx, l); err != nil {
		fmt.Println("ERR set", err)
		return
	}
	_, err = p.ParseString(ctx, "int x; // c\n")
	fmt.Printf("parsed-C err=%v (bundled grammars: C, C++ only)", err)
}
GOSRC
build malivvan "" 0 malivvan

mk official github.com/tree-sitter/go-tree-sitter@latest github.com/tree-sitter/tree-sitter-go@latest <<'GOSRC'
package main

import (
	"fmt"

	sitter "github.com/tree-sitter/go-tree-sitter"
	tsgo "github.com/tree-sitter/tree-sitter-go/bindings/go"
)

func main() {
	p := sitter.NewParser()
	defer p.Close()
	if err := p.SetLanguage(sitter.NewLanguage(tsgo.Language())); err != nil {
		fmt.Println("ERR", err)
		return
	}
	tree := p.Parse([]byte("package p\nvar s = `\n// testmap:covers fake\n`\n// testmap:covers real\n"), nil)
	defer tree.Close()
	fmt.Printf("root=%s err=%v", tree.RootNode().Kind(), tree.RootNode().HasError())
}
GOSRC
build official "" 0 official_cgo0
build official "" 1 official_cgo1

for d in gotreesitter chroma mvdansh antlr4 wazero malivvan official; do
  (cd "$d" && go list -m all 2>/dev/null | grep -E 'gotreesitter|chroma|mvdan|antlr|wazero|malivvan|tree-sitter' | sed "s|^|$d: |")
done > versions.txt
