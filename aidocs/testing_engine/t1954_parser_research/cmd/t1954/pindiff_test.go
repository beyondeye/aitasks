package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const pindiffHead = "# Matrix: baseline\n\n%s\n\n## Per case\n\n| lang | case | status | FP-W | DS-W | SIL-U | REC-C | MISS-W | MISS-C | READ-M | OVER-R | PLACE | FID | BEH | range | ops a/r/u/nm |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"

func writeMatrix(t *testing.T, dir, subject, ident string, rows []string, notes string) {
	t.Helper()
	body := strings.Replace(pindiffHead, "%s", ident, 1) + strings.Join(rows, "\n") + "\n\n## Notes per case\n\n" + notes
	if err := os.WriteFile(filepath.Join(dir, "matrix_"+subject+".md"), []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

// A changed row, a changed note, a case only at one pin, and an unchanged
// case are each reported (or not) as such, and the safety sums follow the rows.
func TestPinDiff(t *testing.T) {
	oldD, newD := t.TempDir(), t.TempDir()
	same := "| bash | a.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a | 1/0/0/0 |"
	writeMatrix(t, oldD, "baseline", "baseline: commit=old", []string{
		same,
		"| python | bom_doc.py | ok | 0 | 0 | 0 | 3 | 0 | 0 | 1 | 0 | 1 | 1 | 2 | n/a | 2/0/0/0 |",
		"| go | gone.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a | 0/0/0/0 |",
	}, "- `python/bom_doc.py`\n  - read: missing line=3\n- `bash/a.sh`\n  - x\n")
	writeMatrix(t, newD, "baseline", "baseline: commit=new", []string{
		same,
		"| python | bom_doc.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a | 1/1/0/0 |",
		"| kotlin | multidollar.kt | ok | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | n/a | 0/0/0/0 |",
	}, "- `bash/a.sh`\n  - y\n")
	out := filepath.Join(t.TempDir(), "pc.md")
	if code := cmdPinDiff([]string{"--old", oldD, "--new", newD, "--out", out}); code != 0 {
		t.Fatalf("exit %d", code)
	}
	b, err := os.ReadFile(out)
	if err != nil {
		t.Fatal(err)
	}
	s := string(b)
	for _, want := range []string{
		"| baseline | 3 / 3 | 1 | 2 | 1 | 1 | [0 0 0 3] → [1 0 0 0] |",
		"- `python/bom_doc.py`\n  - old: `| python | bom_doc.py | ok | 0 | 0 | 0 | 3 |",
		"- `go/gone.go` — only at the old pin",
		"- `kotlin/multidollar.kt` — only at the new pin",
		"commit=old", "commit=new",
		"Differing cases in total: 4.",
	} {
		if !strings.Contains(s, want) {
			t.Errorf("missing %q in:\n%s", want, s)
		}
	}
	if strings.Contains(s, "`bash/a.sh`\n  - old:") == false {
		t.Errorf("a changed note on an unchanged row must be listed:\n%s", s)
	}
}
