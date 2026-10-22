//go:build linux

package hangguard

import (
	"bytes"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"slices"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// The watchdog's own /proc readers and kill — not readStat/getsid, which are
// the code under test — injectable so a control can fault-inject them.
var (
	wdReadEnviron = func(pid int) ([]byte, error) { return os.ReadFile("/proc/" + strconv.Itoa(pid) + "/environ") }
	wdReadStat    = func(pid int) ([]byte, error) { return os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat") }
	wdKill        = syscall.Kill
)

// wdGone reports an error meaning the process no longer exists.
func wdGone(err error) bool { return errors.Is(err, fs.ErrNotExist) || errors.Is(err, syscall.ESRCH) }

// confirmDelay separates an empty scan from the scan that confirms it.
const confirmDelay = 2 * time.Millisecond

// wdProcExists reports whether /proc still lists pid. Only absence answers
// no: any other failure to look counts as present.
func wdProcExists(pid int) bool {
	_, err := os.Lstat("/proc/" + strconv.Itoa(pid))
	return !wdGone(err)
}

// markedProc is a live process the reap owns.
type markedProc struct {
	pid, pgid, sid int
	start          uint64 // stat starttime: with the pid, the process's identity
	comm           string
}

// uncertainProc is owned but could not be shown live or gone.
type uncertainProc struct {
	pid    int
	reason string
	marked bool // its environment carries the marker in this very scan
}

// scanMarked reads every process's environment once and returns the pids
// whose environment holds entry exactly. An environment it may not read
// (another uid; a setuid descendant is the residual) cannot establish
// ownership: skipped, never killed. Any other failure to read one — or to
// list /proc at all — is returned in unreadable: the scan cannot rule out a
// marked process there, so no cleanup is verified while one remains, yet the
// processes it did identify are still reaped.
func scanMarked(entry string) (matched map[int]bool, unreadable []string) {
	matched = map[int]bool{}
	ents, err := os.ReadDir("/proc")
	if err != nil {
		return matched, []string{"/proc: " + err.Error()}
	}
	needle := []byte(entry)
	for _, e := range ents {
		pid, perr := strconv.Atoi(e.Name())
		if perr != nil {
			continue
		}
		env, rerr := wdReadEnviron(pid)
		switch {
		case rerr == nil:
			if hasEntry(env, needle) {
				matched[pid] = true
			}
		case wdGone(rerr):
		case errors.Is(rerr, syscall.EACCES) || errors.Is(rerr, syscall.EPERM):
			// unrelated: ownership cannot be established
		default:
			unreadable = append(unreadable, fmt.Sprintf("pid %d: environ: %v", pid, rerr))
		}
	}
	return matched, unreadable
}

// hasEntry reports whether the NUL-separated environment env holds entry.
func hasEntry(env, entry []byte) bool {
	for len(env) > 0 {
		item := env
		if i := bytes.IndexByte(env, 0); i >= 0 {
			item, env = env[:i], env[i+1:]
		} else {
			env = nil
		}
		if bytes.Equal(item, entry) {
			return true
		}
	}
	return false
}

// parseWdStat reads command name, state, process group, session and start
// time from a stat line; the name is in parentheses and may itself hold
// spaces or ')'.
func parseWdStat(pid int, b []byte) (markedProc, string, bool) {
	line := string(b)
	open, end := strings.IndexByte(line, '('), strings.LastIndexByte(line, ')')
	if open < 0 || end < open {
		return markedProc{}, "", false
	}
	f := strings.Fields(line[end+1:]) // state ppid pgrp session … starttime (field 22)
	if len(f) < 20 {
		return markedProc{}, "", false
	}
	pgid, err1 := strconv.Atoi(f[2])
	sid, err2 := strconv.Atoi(f[3])
	start, err3 := strconv.ParseUint(f[19], 10, 64)
	if err1 != nil || err2 != nil || err3 != nil {
		return markedProc{}, "", false
	}
	return markedProc{pid: pid, pgid: pgid, sid: sid, start: start, comm: line[open+1 : end]}, f[0], true
}

// reapMarked kills every process carrying entry and returns once none is
// left, with every one it owned ("<pid>:<comm>", or "<pid>:?" when it could
// not be inspected).
//
// A process is owned from the scan in which its marker first matches, and is
// tracked by identity — pid plus start time — rather than by what later
// inspections can read: losing access to its environment, or the marker
// vanishing from it, never releases it. Only an observed exit does: /proc no
// longer listing the pid, a zombie, or another start time under the same pid
// (ours exited and the pid was reused, so it is never signalled). Each round
// kills the live owned processes' groups and pids, and an owned process it
// cannot inspect by pid only — and only when its marker matched in that same
// scan, since its identity cannot otherwise be checked — then scans again,
// so a process forked meanwhile is caught by the next round. It never
// signals its own pid or group.
//
// A process caught inside execve — past the switch to its new image, before
// the kernel has set up the image's environment — reads an empty
// environment, and does so right after it starts (tens of microseconds;
// measured in t1985). So one empty scan is not proof: it returns clean only
// when a confirming scan, confirmDelay later, is empty too.
//
// An owned process still present after bound, or a scan that could not read
// every environment, is an error: it never reports a cleanup it could not
// observe.
func reapMarked(entry string, bound time.Duration) ([]string, error) {
	end := time.Now().Add(bound)
	self, own := os.Getpid(), syscall.Getpgrp()
	type identity struct {
		start uint64
		known bool
	}
	owned := map[int]*identity{}
	quiet := false // the previous scan was empty
	var order []int
	labels := map[int]string{}
	note := func(pid int, label string) {
		if _, ok := labels[pid]; !ok {
			order = append(order, pid)
		}
		if label != strconv.Itoa(pid)+":?" || labels[pid] == "" {
			labels[pid] = label
		}
	}
	seen := func() []string {
		out := make([]string, len(order))
		for i, pid := range order {
			out[i] = labels[pid]
		}
		return out
	}
	for {
		matched, unreadable := scanMarked(entry)
		for pid := range matched {
			if owned[pid] == nil {
				owned[pid] = &identity{}
			}
		}
		var live []markedProc
		var uncertain []uncertainProc
		for pid, id := range owned {
			st, err := wdReadStat(pid)
			if err != nil {
				if wdGone(err) || !wdProcExists(pid) {
					delete(owned, pid)
					continue
				}
				uncertain = append(uncertain, uncertainProc{pid, "stat: " + err.Error(), matched[pid]})
				continue
			}
			p, state, ok := parseWdStat(pid, st)
			switch {
			case !ok:
				uncertain = append(uncertain, uncertainProc{pid, fmt.Sprintf("unparsable stat %.64q", st), matched[pid]})
			case id.known && p.start != id.start, state == "Z", state == "X":
				delete(owned, pid) // exited (its pid may since have been reused)
			case !id.known && !matched[pid]:
				uncertain = append(uncertain, uncertainProc{pid, "identity unverifiable", false})
			default:
				id.start, id.known = p.start, true
				live = append(live, p)
			}
		}
		slices.SortFunc(live, func(a, b markedProc) int { return a.pid - b.pid })
		slices.SortFunc(uncertain, func(a, b uncertainProc) int { return a.pid - b.pid })
		for _, p := range live {
			note(p.pid, strconv.Itoa(p.pid)+":"+p.comm)
		}
		for _, u := range uncertain {
			note(u.pid, strconv.Itoa(u.pid)+":?")
		}
		if len(live) == 0 && len(uncertain) == 0 && len(unreadable) == 0 {
			if quiet {
				return seen(), nil
			}
			quiet = true
			time.Sleep(confirmDelay)
			continue
		}
		quiet = false
		if time.Now().After(end) {
			var still []string
			for _, p := range live {
				still = append(still, strconv.Itoa(p.pid))
			}
			for _, u := range uncertain {
				still = append(still, fmt.Sprintf("%d (uninspectable: %s)", u.pid, u.reason))
			}
			var parts []string
			if len(still) > 0 {
				parts = append(parts, "still present after "+bound.String()+": "+strings.Join(still, ", "))
			}
			if len(unreadable) > 0 {
				parts = append(parts, "scan incomplete: "+strings.Join(unreadable, "; "))
			}
			return seen(), errors.New("cleanup_unverified: " + strings.Join(parts, "; "))
		}
		for _, p := range live {
			if p.pgid > 1 && p.pgid != own {
				_ = wdKill(-p.pgid, syscall.SIGKILL)
			}
			if p.pid > 1 && p.pid != self {
				_ = wdKill(p.pid, syscall.SIGKILL)
			}
		}
		for _, u := range uncertain {
			if u.marked && u.pid > 1 && u.pid != self {
				_ = wdKill(u.pid, syscall.SIGKILL) // its group is unknown
			}
		}
		time.Sleep(10 * time.Millisecond)
	}
}
