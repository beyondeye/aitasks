//go:build unix

package runner

// The hang guard for this package's process-starting tests lives in
// internal/testsupport/hangguard (the watchdog, its controls and the source
// tripwire); this package is one of the tripwire's tripwirePackages entries,
// so a test that reaches a process start without the guard as its first
// statement fails ci/preflight.sh.

import (
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
)

// hangLimit bounds one isolated test. The slowest runs in about 3 s; the
// limit stays under the fixtures' `sleep 30` so that a lost deadline reads as
// a hang rather than a slow pass.
const hangLimit = 20 * time.Second

// isolated is hangguard.Isolated. A guarded test starts with
//
//	if !isolated(t, hangLimit) {
//		return
//	}
func isolated(t *testing.T, limit time.Duration) bool {
	t.Helper()
	return hangguard.Isolated(t, limit)
}
