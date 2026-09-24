// Command benchgate runs the engine's benchmarks and applies the 2× rule
// against the committed baselines. It lives under internal/ so the release
// build, which ships every cmd/*, never ships it.
//
//	go run ./internal/tools/benchgate -baseline bench/baseline.txt [-partial] [-update] [-- <producer argv>]
//
// It runs the producer itself (default: go test -p 1 -cpu 1 -run ^$ -bench .
// -count 3 ./...) rather than reading a pipe, so a failing producer can never
// be masked by a passing checker. The flags keep recording and checking
// comparable across hosts: -p 1 runs one package's benchmarks at a time (the
// calibrations and the benchmarks they scale must not overlap), -cpu 1 fixes
// GOMAXPROCS whatever the host's core count, and -count 3 lets ParseBench
// keep each benchmark's fastest of three runs — a single sample on a loaded
// host skews a baseline or a scale enough to hide a 2× regression. A custom
// producer for the gate or -update must keep all three. Exit 0 pass; 1
// regression, over budget, missing baseline benchmark or calibration (full
// mode), implausible host scale, empty measurement set or producer failure;
// 64 usage.
package main

import (
	"bytes"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"

	"github.com/beyondeye/aitasks/goengines/internal/benchgate"
)

// modulePrefix is trimmed from package paths to form benchmark names.
const modulePrefix = "github.com/beyondeye/aitasks/goengines/"

var defaultProducer = []string{"go", "test", "-p", "1", "-cpu", "1", "-run", "^$", "-bench", ".", "-count", "3", "./..."}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("benchgate", flag.ContinueOnError)
	fs.SetOutput(stderr)
	baselinePath := fs.String("baseline", "", "committed baseline file (required)")
	partial := fs.Bool("partial", false, "developer subset run: unmeasured baselines do not fail (never the gate)")
	update := fs.Bool("update", false, "re-record the baseline from this run instead of judging it")
	if err := fs.Parse(args); err != nil {
		return 64
	}
	if *baselinePath == "" {
		fmt.Fprintln(stderr, "USAGE:benchgate -baseline <file> [-partial] [-update] [-- <producer argv>]")
		return 64
	}
	if *update && *partial {
		fmt.Fprintln(stderr, "USAGE:-update needs a full run: a partial run would drop the unmeasured baselines")
		return 64
	}
	producer := fs.Args()
	if len(producer) == 0 {
		producer = defaultProducer
	}
	mode := benchgate.Full
	if *partial {
		mode = benchgate.Partial
	}

	baseline := &benchgate.Baseline{Entries: map[string]benchgate.Entry{}}
	raw, err := os.ReadFile(*baselinePath)
	switch {
	case err == nil:
		if baseline, err = benchgate.ParseBaseline(bytes.NewReader(raw)); err != nil {
			fmt.Fprintln(stderr, err)
			return 64
		}
	case errors.Is(err, os.ErrNotExist) && *update:
		// First recording.
	default:
		fmt.Fprintln(stderr, err)
		return 64
	}

	fmt.Fprintf(stdout, "BENCH_MODE:%s\n", mode)

	var out bytes.Buffer
	cmd := exec.Command(producer[0], producer[1:]...)
	cmd.Stdout = &out
	cmd.Stderr = stderr
	perr := cmd.Run()
	cur, parseErr := benchgate.ParseBench(bytes.NewReader(out.Bytes()), modulePrefix)
	if perr != nil || parseErr != nil {
		code := -1
		var ee *exec.ExitError
		if errors.As(perr, &ee) {
			code = ee.ExitCode()
		}
		fmt.Fprintf(stdout, "BENCH_PRODUCER_FAILED:%d\n", code)
		if perr != nil && code == -1 {
			fmt.Fprintln(stderr, perr)
		}
		if parseErr != nil {
			fmt.Fprintln(stderr, parseErr)
		}
		stderr.Write(out.Bytes())
		return 1
	}

	if *update {
		// Rewrite drops every unmeasured baseline, so a run that could not
		// be judged later must not be written: one missing a calibration its
		// lines need fails every full gate, one with only calibrations has no
		// benchmarks left.
		for _, class := range baseline.RequiredClasses(cur) {
			if _, ok := cur[benchgate.Calibrations[class]]; !ok {
				fmt.Fprintf(stdout, "BENCH_CALIBRATION_MISSING:%s|current\n", class)
				return 1
			}
		}
		if benchgate.Measured(cur) == 0 {
			fmt.Fprintln(stdout, "BENCH_EMPTY:")
			return 1
		}
		if err := os.WriteFile(*baselinePath, []byte(baseline.Rewrite(cur)), 0o644); err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		fmt.Fprintf(stdout, "BENCH_UPDATED:%s|%d\n", *baselinePath, len(cur))
		return 0
	}

	res := benchgate.Compare(cur, baseline, mode)
	for _, l := range res.Lines {
		fmt.Fprintln(stdout, l)
	}
	if res.Fail {
		return 1
	}
	return 0
}
