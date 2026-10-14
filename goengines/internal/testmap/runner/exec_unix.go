//go:build unix

package runner

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os/exec"
	"slices"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// Bounds of one runner process.
var (
	// ListTimeout bounds `describe` and `list` (a runner's list may exec the
	// build's own list task).
	ListTimeout = 300 * time.Second
	// outputMax bounds stdout; past it the runner is killed and refused.
	outputMax = 64 << 20
	// stderrMax bounds the stderr kept (only its first line is reported).
	stderrMax = 64 << 10
	// drainDelay bounds the wait for pipes a leaked process still holds once
	// the runner has exited or been killed.
	drainDelay = 500 * time.Millisecond
	// SweepTimeout bounds the session sweep; live processes left after it
	// are a mechanism failure (cleanup_incomplete).
	SweepTimeout = 5 * time.Second
)

// capWriter keeps at most max bytes. Past it, it records the overflow, calls
// onOver once and discards the rest, so the pipe keeps draining.
type capWriter struct {
	buf    bytes.Buffer
	max    int
	over   bool
	onOver func()
}

func (w *capWriter) Write(p []byte) (int, error) {
	if room := w.max - w.buf.Len(); len(p) > room {
		w.buf.Write(p[:max(room, 0)])
		if !w.over && w.onOver != nil {
			w.onOver()
		}
		w.over = true
		return len(p), nil
	}
	return w.buf.Write(p)
}

// command is one runner process to start.
type command struct {
	Path string
	Args []string
	Dir  string
	Env  []string
}

// execResult is how one runner process ended.
type execResult struct {
	Stdout      []byte
	StderrFirst string
	Exit        int   // the exit status; -1 when killed by a signal or never started
	Killed      bool  // the engine's deadline fired and the engine killed it
	Overflow    bool  // stdout exceeded outputMax (it was killed)
	StartErr    error // the process could not be started
	Sweep       error // *cleanupError: the session could not be proven empty
}

// cleanupError is a session the sweep could not prove empty.
type cleanupError struct {
	Detail string // cleanup_incomplete:<pids> | cleanup_unverified:<reason>
}

func (e *cleanupError) Error() string { return e.Detail }

// execRunner runs c under deadline. The runner leads a new session
// (Setsid): every process group it or its tests create with setpgid stays
// inside that session, so the engine owns all of them — process groups do
// not nest, and a SIGKILLed runner cannot clean up after itself. On every
// exit path (a normal exit, the engine's deadline, an output overflow, a
// cancelled context) the whole session is swept before execRunner returns.
//
// Residual: a process that calls setsid() itself leaves the session and
// escapes the sweep; the runner contract forbids it.
func execRunner(ctx context.Context, c command, deadline time.Duration) execResult {
	dctx, cancel := context.WithTimeout(ctx, deadline)
	defer cancel()
	cmd := exec.CommandContext(dctx, c.Path, c.Args...)
	cmd.Dir = c.Dir
	cmd.Env = c.Env
	stdout := &capWriter{max: outputMax, onOver: cancel}
	stderr := &capWriter{max: stderrMax}
	cmd.Stdout = stdout
	cmd.Stderr = stderr
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	cmd.Cancel = func() error { return syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL) }
	cmd.WaitDelay = drainDelay
	res := execResult{Exit: -1}
	err := cmd.Run()
	if cmd.Process == nil {
		res.StartErr = err
		return res
	}
	// The runner's pid is its session id (Setsid). Sweep whatever is left,
	// whatever happened.
	res.Sweep = sweepSession(cmd.Process.Pid)
	if cmd.ProcessState != nil {
		res.Exit = cmd.ProcessState.ExitCode()
	}
	res.Overflow = stdout.over
	res.Killed = err != nil && !stdout.over && ctx.Err() == nil && errors.Is(dctx.Err(), context.DeadlineExceeded)
	if errors.Is(err, exec.ErrWaitDelay) && cmd.ProcessState != nil && cmd.ProcessState.Exited() {
		err = nil // exited on its own; a leaked process held the pipes (swept above)
	}
	res.Stdout = stdout.buf.Bytes()
	first, _, _ := strings.Cut(strings.TrimSpace(stderr.buf.String()), "\n")
	if len(first) > 512 {
		first = first[:512] + "…"
	}
	res.StderrFirst = first
	return res
}

// proc is one process of a session.
type proc struct {
	Pid, Pgid int
	Zombie    bool
}

// sweepSession kills every process whose session id is sid and returns once
// none is alive (a zombie counts as gone: it runs nothing and its parent
// reaps it). Each round kills every process group found in the session, then
// every remaining pid, then re-enumerates — a process forked during a round
// is caught by the next. A session that cannot be enumerated, or that is
// still alive after SweepTimeout, is a *cleanupError: the engine never claims
// a cleanup it could not observe.
//
// While any member is alive the kernel keeps sid allocated, so it cannot be
// reused for an unrelated session during the sweep.
func sweepSession(sid int) error {
	end := time.Now().Add(SweepTimeout)
	for {
		procs, err := sessionProcs(sid)
		if err != nil {
			return &cleanupError{Detail: "cleanup_unverified:" + err.Error()}
		}
		var live []proc
		for _, p := range procs {
			if !p.Zombie {
				live = append(live, p)
			}
		}
		if len(live) == 0 {
			return nil
		}
		if time.Now().After(end) {
			pids := make([]string, len(live))
			for i, p := range live {
				pids[i] = strconv.Itoa(p.Pid)
			}
			return &cleanupError{Detail: "cleanup_incomplete:" + strings.Join(pids, ",")}
		}
		var groups []int
		for _, p := range live {
			if p.Pgid > 0 && !slices.Contains(groups, p.Pgid) {
				groups = append(groups, p.Pgid)
			}
		}
		for _, g := range groups {
			_ = syscall.Kill(-g, syscall.SIGKILL)
		}
		for _, p := range live {
			_ = syscall.Kill(p.Pid, syscall.SIGKILL)
		}
		time.Sleep(10 * time.Millisecond)
	}
}

// exitText describes how a runner process ended, for error details.
func (r execResult) exitText() string {
	switch {
	case r.StartErr != nil:
		return "could not start: " + r.StartErr.Error()
	case r.Overflow:
		return fmt.Sprintf("output exceeds %d bytes", outputMax)
	case r.Killed:
		return "timed out"
	}
	s := "exit " + strconv.Itoa(r.Exit)
	if r.StderrFirst != "" {
		s += ": " + r.StderrFirst
	}
	return s
}
