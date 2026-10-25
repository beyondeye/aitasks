package runner

import (
	"context"
	"errors"
	"fmt"
	"os"
	"slices"
	"strconv"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/procsup"
)

// nestedEngineArg makes the test binary a minimal engine: `<test binary>
// __nested_engine check|run` loads (check) or runs every unit (run) in its
// working directory, like `ait-testmap check` / `run --all`. The dispatch is
// by argv, not by environment, so it also works under `env -i`.
const nestedEngineArg = "__nested_engine"

// TestMain dispatches the nested engine; otherwise it runs the package's
// tests under an active marker for the enclosing repository (G9: the
// engine's own suite stays green under one, because every test entry uses a
// fixture repository).
// dieAfterCleanupEnv=run makes this binary, supervising a runner's `run`,
// die once its cleanup reached ECHILD and before its status (test code
// only: TestNoSessionSignallingWhenSupervised).
const dieAfterCleanupEnv = "AIT_TEST_DIE_AFTER_CLEANUP"

func TestMain(m *testing.M) {
	if os.Getenv(dieAfterCleanupEnv) == "run" && slices.Contains(os.Args, "run") {
		procsup.SetDieAfterCleanupForTesting()
	}
	procsup.MaybeSupervise() // this binary is the supervisor of every runner it starts
	if len(os.Args) == 3 && os.Args[1] == nestedEngineArg {
		os.Exit(nestedEngine(os.Args[2]))
	}
	if id, err := Identity(context.Background(), "."); err == nil {
		if inherited, perr := ParseActive(os.Getenv(ActiveEnv)); perr == nil {
			os.Setenv(ActiveEnv, FormatActive(unionIDs(inherited, []string{id})))
		}
	}
	os.Exit(m.Run())
}

// nestedEngine prints the refusal line and VIA:<detector> on stderr, or
// NESTED_OK:<exit>, and exits as the engine would.
//
// It keeps an inherited AIT_HANGGUARD_ISOLATE: TestMain dispatches here before
// m.Run, so the variable cannot trigger an isolation of its own, and it is
// what lets the watchdog find this engine's runner processes if one hangs
// (a cleared-environment case loses it, by construction).
func nestedEngine(verb string) int {
	root, err := os.Getwd()
	if err != nil {
		fmt.Fprintln(os.Stderr, "NESTED_ERROR:"+err.Error())
		return 3
	}
	code := 0
	switch verb {
	case "check":
		_, err = Load(context.Background(), root)
	case "run":
		var rep *RunReport
		rep, err = Run(context.Background(), root, Options{All: true, RunID: "nested-" + strconv.Itoa(os.Getpid())})
		if err == nil {
			code = rep.Exit()
		}
	default:
		return 64
	}
	var re *RecursionError
	switch {
	case errors.As(err, &re):
		line, _ := re.Line()
		fmt.Fprintln(os.Stderr, line)
		fmt.Fprintln(os.Stderr, "VIA:"+re.Via)
		return re.ExitCode()
	case err != nil:
		fmt.Fprintln(os.Stderr, "NESTED_ERROR:"+oneLine(err.Error()))
		return 3
	}
	fmt.Fprintf(os.Stderr, "NESTED_OK:%d\n", code)
	return code
}
