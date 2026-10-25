//go:build linux

package procsup

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"
)

// Test-binary environment switches, read here only (test code):
//
//	AIT_TEST_OMIT_DISPATCH=1        skip MaybeSupervise — a binary that forgot it
//	AIT_TEST_LAUNCH_LOG=<file>      every launch appends a line to <file>
//	AIT_TEST_DIE_AFTER_CLEANUP=1    a supervisor dies after its cleanup, before its status
const (
	omitDispatchEnv = "AIT_TEST_OMIT_DISPATCH"
	launchLogEnv    = "AIT_TEST_LAUNCH_LOG"
	dieAfterEnv     = "AIT_TEST_DIE_AFTER_CLEANUP"
	parentArg       = "__procsup_parent" // <script>: Start it, print the pids, block
)

func TestMain(m *testing.M) {
	if os.Getenv(dieAfterEnv) == "1" {
		SetDieAfterCleanupForTesting()
	}
	if log := os.Getenv(launchLogEnv); log != "" {
		OnLaunchForTesting(func() { appendLine(log, fmt.Sprint(os.Getpid())) })
	}
	if os.Getenv(omitDispatchEnv) != "1" {
		MaybeSupervise()
	}
	if len(os.Args) == 3 && os.Args[1] == parentArg {
		os.Exit(parentMain(os.Args[2]))
	}
	os.Exit(m.Run())
}

// parentMain is a process acting as a supervisor's parent: it starts script,
// prints `<supervisor pid> <command pid>` and blocks until it is killed.
func parentMain(script string) int {
	var sup int
	OnStartForTesting(func(s, _ int) { sup = s })
	p, err := Start(context.Background(), Spec{Path: "/bin/sh", Args: []string{"-c", script}})
	if err != nil {
		fmt.Println("START_ERROR", err)
		return 3
	}
	fmt.Println(sup, p.Pid())
	time.Sleep(time.Hour)
	return 0
}

func appendLine(path, line string) {
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_APPEND|os.O_CREATE, 0o644)
	if err != nil {
		panic(err)
	}
	defer f.Close()
	if _, err := f.WriteString(line + "\n"); err != nil {
		panic(err)
	}
}
