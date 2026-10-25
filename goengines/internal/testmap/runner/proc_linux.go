//go:build linux

package runner

import (
	"errors"
	"os"
	"strconv"
	"syscall"
)

// readStat reads /proc/<pid>/stat for the recursion guard's process view
// (recursion_linux.go), injectable so tests can fault-inject what a
// restricted process (another uid under a hidepid /proc) would answer. The
// session enumeration and sweep live in procsup.
var readStat = func(pid int) ([]byte, error) { return os.ReadFile("/proc/" + strconv.Itoa(pid) + "/stat") }

// gone reports an error that means the process no longer exists.
func gone(err error) bool { return errors.Is(err, os.ErrNotExist) || errors.Is(err, syscall.ESRCH) }
