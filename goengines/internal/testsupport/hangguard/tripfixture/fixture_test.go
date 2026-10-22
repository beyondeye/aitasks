//go:build unix

// Package tripfixture is the hang-guard tripwire's second real package: a
// consumer of hangguard.Isolated outside the runner package, whose guarded
// tests the tripwire's red proofs strip (an unguarded process start must be
// flagged) and empty (a guarded test that starts nothing must be unseen).
package tripfixture

import (
	"os/exec"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard"
)

const limit = 10 * time.Second

// startAll starts and waits for each command through *exec.Cmd methods, which
// the tripwire's name resolution does not follow: it is this package's local
// starter (its tripwirePackages entry names it).
func startAll(cs []*exec.Cmd) error {
	for _, c := range cs {
		if err := c.Start(); err != nil {
			return err
		}
		if err := c.Wait(); err != nil {
			return err
		}
	}
	return nil
}

func TestGuardedCommand(t *testing.T) {
	if !hangguard.Isolated(t, limit) {
		return
	}
	if err := exec.Command("/bin/sh", "-c", "exit 0").Run(); err != nil {
		t.Fatal(err)
	}
}

func TestGuardedLocalStarter(t *testing.T) {
	if !hangguard.Isolated(t, limit) {
		return
	}
	if err := startAll([]*exec.Cmd{{Path: "/bin/sh", Args: []string{"sh", "-c", "exit 0"}}}); err != nil {
		t.Fatal(err)
	}
}
