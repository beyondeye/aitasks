package main

import (
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"

	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
	"github.com/beyondeye/aitasks/goengines/internal/testmap"
)

// versionInfo is the --json shape of `version`.
type versionInfo struct {
	Version  string `json:"version"`
	Commit   string `json:"commit"`
	Contract int    `json:"contract"`
	Engine   string `json:"engine"`
}

// enginePath is the resolved path of the running binary.
var enginePath = func() (string, error) {
	p, err := os.Executable()
	if err != nil {
		return "", err
	}
	return filepath.EvalSymlinks(p)
}

// runVersion prints the build identity:
//
//	VERSION:<version>
//	COMMIT:<commit>
//	CONTRACT:<contract>
//	ENGINE:<absolute path of this binary>
//
// or, with --json, {"version","commit","contract","engine"}.
func runVersion(e env, args []string) int {
	fs := flag.NewFlagSet("version", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	asJSON := fs.Bool("json", false, "print one JSON object")
	if err := fs.Parse(args); err != nil || fs.NArg() > 0 {
		return lineproto.Usage(e.stderr, "ait-testmap version [--json]")
	}
	path, err := enginePath()
	if err != nil {
		fmt.Fprintf(e.stderr, "ENGINE_PATH_UNKNOWN:%v\n", err)
		return lineproto.ExitFramework
	}
	info := versionInfo{Version: version, Commit: commit, Contract: testmap.Contract, Engine: path}
	w := lineproto.NewWriter(e.stdout, *asJSON)
	if w.JSON {
		err = w.Emit(info)
	} else {
		for _, l := range [][2]string{
			{"VERSION", info.Version}, {"COMMIT", info.Commit},
			{"CONTRACT", strconv.Itoa(info.Contract)}, {"ENGINE", info.Engine},
		} {
			if err = w.Line(l[0], l[1]); err != nil {
				break
			}
		}
	}
	if err != nil {
		fmt.Fprintf(e.stderr, "OUTPUT_ERROR:%v\n", err)
		return lineproto.ExitFramework
	}
	return lineproto.ExitOK
}
