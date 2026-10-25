//go:build linux

package builtin

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/procsup"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

// This test binary is the engine, every supervisor and every builtin
// process: runner.SelfExe and procsup.SupervisorExe are both os.Executable,
// and TestMain dispatches `__supervise …` and `runner <name> …` before the
// tests.
//
// Test-only environment (read here only):
//
//	AIT_TEST_PROCSUP_UNAVAILABLE=1  the process has no containment (as on darwin)
//	AIT_TEST_STATE=<dir>            the echo adapter writes <dir>/<runner>.builtin.pid
const (
	unavailableEnv = "AIT_TEST_PROCSUP_UNAVAILABLE"
	stateEnv       = "AIT_TEST_STATE"
)

// executor runs the plan serially, or all at once when parallel is set.
type executor struct{ parallel atomic.Bool }

var plan = &executor{}

func (x *executor) Execute(ctx context.Context, invs []*runner.Invocation, invoke runner.InvokeFunc) ([]runner.Outcome, error) {
	out := make([]runner.Outcome, len(invs))
	if !x.parallel.Load() {
		for i, inv := range invs {
			out[i] = invoke(ctx, inv)
		}
		return out, nil
	}
	var wg sync.WaitGroup
	for i, inv := range invs {
		wg.Add(1)
		go func() { defer wg.Done(); out[i] = invoke(ctx, inv) }()
	}
	wg.Wait()
	return out, nil
}

func TestMain(m *testing.M) {
	if os.Getenv(unavailableEnv) == "1" {
		procsup.SetUnavailableForTesting()
	}
	procsup.MaybeSupervise()
	if len(os.Args) == 3 && os.Args[1] == nestedEngineArg {
		os.Exit(nestedEngine(os.Args[2]))
	}
	Register(echoAdapter("echo", true))
	Register(echoAdapter("prodecho", false))
	if len(os.Args) > 2 && os.Args[1] == "runner" {
		os.Exit(Main(os.Args[2:], os.Stdout, os.Stderr))
	}
	runner.RegisterExecutor(plan)
	os.Exit(m.Run())
}

// echoAdapter is a test-only cases adapter around a tool named by the
// runner's command: (`<tool> list <file>` prints the file's case names,
// `<tool> run <file>` prints `<case> <status>` lines). Units are the
// repository's tests/*.echo files.
func echoAdapter(name string, testOnly bool) Adapter {
	return Adapter{
		Name:     name,
		TestOnly: testOnly,
		Describe: func(*Env) ([]byte, error) {
			return []byte("unit: file\naccounting: cases\ndiscovery: native\ntimeouts: batch\n"), nil
		},
		List: func(ctx context.Context, e *Env, w io.Writer) error {
			argv, err := SplitCommand(e.Command)
			if err != nil {
				return err
			}
			files, _ := filepath.Glob(filepath.Join(e.Root, "tests", "*.echo"))
			for _, f := range files {
				id, _ := filepath.Rel(e.Root, f)
				out := filepath.Join(os.TempDir(), "echo-list-"+strconv.Itoa(os.Getpid()))
				rr := e.Supervise(ctx, procsup.RunSpec{Path: argv[0], Args: append(argv[1:], "list", id), Dir: e.Root,
					Stdout: out, Timeout: DiscoveryBound()})
				if rr.StartErr != nil || rr.Exit != 0 || rr.Cleanup != nil || rr.SupervisorDied {
					return fmt.Errorf("list %s: %+v", id, rr)
				}
				b, err := os.ReadFile(out)
				os.Remove(out)
				if err != nil {
					return err
				}
				fmt.Fprintf(w, "%s\tfile\t%s\n", id, strings.TrimSuffix(filepath.Base(id), ".echo"))
				for _, c := range strings.Fields(string(b)) {
					if !strings.HasPrefix(c, "@") {
						fmt.Fprintf(w, "%s\tcase\t%s\n", id, c)
					}
				}
			}
			return nil
		},
		Run: func(ctx context.Context, e *Env, m *runner.Manifest, res *Results) int {
			if st := os.Getenv(stateEnv); st != "" {
				_ = os.WriteFile(filepath.Join(st, e.Runner+".builtin.pid"), []byte(strconv.Itoa(os.Getpid())+"\n"), 0o644)
			}
			argv, err := SplitCommand(e.Command)
			if err != nil {
				return 64
			}
			code := 0
			for i, u := range m.Units {
				if err := res.Start(u.ID); err != nil {
					return 3
				}
				out := filepath.Join(m.ReportDir, fmt.Sprintf("unit-%d.out", i))
				rr := e.Supervise(ctx, procsup.RunSpec{Path: argv[0], Args: append(argv[1:], "run", u.ID), Dir: e.Root,
					Stdout: out, Timeout: time.Duration(u.TimeoutS * float64(time.Second)), Grace: time.Second})
				if rr.StartErr != nil || rr.Cleanup != nil || rr.SupervisorDied {
					return 3
				}
				b, _, err := e.Fresh(out)
				if err != nil {
					return 3
				}
				sc := bufio.NewScanner(strings.NewReader(string(b)))
				for sc.Scan() {
					f := strings.Fields(sc.Text())
					if len(f) != 2 {
						continue
					}
					if err := res.Case(u.ID, f[0], f[1], 1, ""); err != nil {
						return 3
					}
					if f[1] == "fail" {
						code = 1
					}
				}
			}
			return code
		},
	}
}

// errorsAs is errors.As for a target type.
func errorsAs[T error](err error) bool {
	var t T
	return errors.As(err, &t)
}
