package main

import (
	"os"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/procsup"
)

// TestMain makes this test binary the supervisor of the runners its
// in-process verbs start (procsup.SupervisorExe is the test binary here).
func TestMain(m *testing.M) {
	procsup.MaybeSupervise()
	os.Exit(m.Run())
}
