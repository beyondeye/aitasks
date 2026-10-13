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
//	t1954 env                                        results/environment.md
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
	default:
		usage()
	}
	os.Exit(code)
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: t1954 matrix|edit|guard|classes|oraclecheck|realrepo|bench|footprint|env [flags]")
	os.Exit(64)
}

func fail(code int, err error) {
	fmt.Fprintf(os.Stderr, "t1954: %v\n", err)
	os.Exit(code)
}
