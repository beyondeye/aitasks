package annot

import (
	"fmt"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// BenchmarkScan is `scan` with the real annotation source over an
// aitasks-shaped repository: ≈420 annotated test files (1–3 covers each, a
// few member files), ≈600 sources and ≈1,000 other files, all untracked in a
// fresh repository (git lists them). Budget: the proposal's 300 ms for scan.
func BenchmarkScan(b *testing.B) {
	r := fixture.New(b)
	r.Write(b, registry.ConfigPath, "contract: 1\n")
	for i := range 600 {
		r.Write(b, fmt.Sprintf("src/lib%d/s%d.sh", i%20, i), "echo source\n")
	}
	for i := range 420 {
		var body strings.Builder
		body.WriteString("#!/usr/bin/env bash\n# A test header.\n#\n")
		for k := range 1 + i%3 {
			fmt.Fprintf(&body, "# testmap:covers src/lib%d/s%d.sh @2026-01-01/0123456789\n", (i+k)%20, (i*7+k)%600)
		}
		body.WriteString("set -euo pipefail\nsource \"$(dirname \"$0\")/lib/asserts.sh\"\n")
		if i%20 == 0 {
			body.WriteString("# testmap:unit Alpha\n# testmap:covers src/lib0/s0.sh\nalpha() { :; }\n")
		}
		for range 40 {
			body.WriteString("assert_eq \"x\" \"$(echo x)\" \"$(cat <<EOF\nx\nEOF\n)\"\n")
		}
		ext := ".sh"
		if i%4 == 0 {
			ext = ".py"
			body.Reset()
			fmt.Fprintf(&body, "\"\"\"Test %d.\"\"\"\n# testmap:covers src/lib1/s%d.sh\nimport unittest\n", i, i%600)
			for range 40 {
				body.WriteString("x = f\"{1}\" + '#' + \"\"\"a\"\"\"\n")
			}
		}
		r.Write(b, fmt.Sprintf("tests/test_%d%s", i, ext), body.String())
	}
	for i := range 1000 {
		r.Write(b, fmt.Sprintf("docs/d%d/page%d.md", i%30, i), "# Title\n\nText.\n")
	}
	in := registry.Inputs{Annotations: Source{}, Lister: emptyLister{}}
	for b.Loop() {
		if _, err := registry.Scan(bg, r.Dir, in, false); err != nil {
			b.Fatal(err)
		}
	}
}
