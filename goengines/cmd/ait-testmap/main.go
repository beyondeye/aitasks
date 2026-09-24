// Command ait-testmap is the test map engine. It is reached through the
// `ait testmap` shim, which resolves the binary for the framework version;
// its verbs speak the line protocol on stdout (or JSON with --json) and a
// per-verb exit contract.
//
// Build identity is set at link time:
//
//	go build -ldflags "-X main.version=<V> -X main.commit=<sha>" ./cmd/ait-testmap
//
// An unset build reports version "devel", which matches neither the release
// handshake (== VERSION) nor the dev one (<V>-dev+<sha>), so the shim refuses
// it rather than running an unidentified engine.
package main

import (
	"io"
	"os"
)

var (
	version = "devel"
	commit  = "unknown"
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

// env is what a verb runs with.
type env struct {
	stdout, stderr io.Writer
}

// run dispatches args to the verb table and returns the process exit code.
func run(args []string, stdout, stderr io.Writer) int {
	return dispatch(verbs, "", args, env{stdout: stdout, stderr: stderr})
}
