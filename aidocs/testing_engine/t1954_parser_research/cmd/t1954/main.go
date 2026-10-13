// Command t1954 is the t1954 parser-research harness. Every verb first
// proves the compiled-in goengines snapshot is the one baseline/PIN names
// (exit 2 otherwise) and prints that identity at the top of its output.
//
//	t1954 matrix   [--provider p,…] [--lang l,…] [--out dir] [--behaviour] [--oracle]
//	t1954 edit     [--provider p] [--lang l]        the edit suite alone, to stdout
//	t1954 guard                                      unpatched vs patched-unhooked baseline matrices
//	t1954 classes  --provider p <file>…              line classes, for debugging
//	t1954 realrepo --repo <path> [--name n] [--provider p,…]
//	t1954 bench    [--provider p,…] [--quick]
//	t1954 footprint
//	t1954 oraclecheck                                native cross-checks of the hand oracles
//	t1954 env      [--t3]                            results/environment.md (--t3: only the t1954_3 tools section)
//	t1954 localpolicy [--provider p,…]              the local-error refusal alternative
//	t1954 tsdiff   [--repos a,b] [--out f]           tree-sitter runtime differential (-tags t1954cgo)
//	t1954 lsp      [--servers a,b] [--workdir d]     do language servers expose comments? (t1954_3)
//	t1954 sidecar                                    the registry fed from YAML sidecars (t1954_3)
//	t1954 footprint-t3                               the t1954_3 candidates' footprint
package main

import (
	"fmt"
	"os"

	"github.com/beyondeye/aitasks/goengines/t1954research/internal/identity"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/seam"
)

var id identity.ID

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	root, err := identity.FindRoot()
	if err != nil {
		fail(2, err)
	}
	id, err = identity.Verify(root, seam.Available)
	if err != nil {
		fail(2, err)
	}
	if err := os.Chdir(root); err != nil {
		fail(2, err)
	}
	verb, args := os.Args[1], os.Args[2:]
	var code int
	switch verb {
	case "matrix":
		code = cmdMatrix(args)
	case "edit":
		code = cmdEdit(args)
	case "guard":
		code = cmdGuard(args)
	case "classes":
		code = cmdClasses(args)
	case "realrepo":
		code = cmdRealrepo(args)
	case "bench":
		code = cmdBench(args)
	case "bench-child":
		code = cmdBenchChild(args)
	case "footprint":
		code = cmdFootprint(args)
	case "oraclecheck":
		code = cmdOracleCheck(args)
	case "env":
		code = cmdEnv(args)
	case "localpolicy":
		code = cmdLocalPolicy(args)
	default:
		f, ok := extraVerbs[verb]
		if !ok {
			usage()
		}
		code = f(args)
	}
	os.Exit(code)
}

// extraVerbs are verbs registered from their own files: tsdiff compiled in
// only under a build tag (it needs the cgo reference provider), and the
// t1954_3 experiments (lsp, sidecar, footprint-t3).
var extraVerbs = map[string]func([]string) int{}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: t1954 matrix|edit|guard|classes|oraclecheck|realrepo|bench|footprint|env|localpolicy|lsp|sidecar|footprint-t3 [flags]")
	os.Exit(64)
}

func fail(code int, err error) {
	fmt.Fprintf(os.Stderr, "t1954: %v\n", err)
	os.Exit(code)
}
