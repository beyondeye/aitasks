package deps

import (
	"fmt"
	"os"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// benchRepo is a fresh repository holding fixture.AitasksShape.
func benchRepo(b *testing.B) *fixture.Repo {
	b.Helper()
	r := fixture.New(b)
	fixture.AitasksShape(b, r)
	return r
}

func benchEnv(b *testing.B) {
	b.Setenv("GOTOOLCHAIN", "local")
	b.Setenv("GOFLAGS", "")
	b.Setenv("GOWORK", "off")
}

// BenchmarkScanWarm is a scan whose blob cache and go-list result are
// primed: the selector's per-call cost. Budget 150 ms, inside the proposal's
// 200 ms warm `select`.
func BenchmarkScanWarm(b *testing.B) {
	benchEnv(b)
	r := benchRepo(b)
	o := Options{Config: registry.Defaults(), CacheDir: b.TempDir()}
	if _, err := Scan(bg, r.Dir, o); err != nil {
		b.Fatal(err)
	}
	for b.Loop() {
		if _, err := Scan(bg, r.Dir, o); err != nil {
			b.Fatal(err)
		}
	}
}

// BenchmarkScanCold is a scan with an empty cache, `go list` included.
// Budget 1.5 s, the proposal's cold `select`.
func BenchmarkScanCold(b *testing.B) {
	benchEnv(b)
	r := benchRepo(b)
	base := b.TempDir()
	n := 0
	for b.Loop() {
		n++
		dir := fmt.Sprintf("%s/c%d", base, n)
		if _, err := Scan(bg, r.Dir, Options{Config: registry.Defaults(), CacheDir: dir}); err != nil {
			b.Fatal(err)
		}
		b.StopTimer()
		os.RemoveAll(dir)
		b.StartTimer()
	}
}
