package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// The unrelated provenance row of the re-stamp fixtures: noncanonical on
// purpose (a head comment, quoted values, fields out of schema order, an
// unknown field), so "byte-identical" means the splicer never touched it.
const unrelatedRow = "  # hand-kept row\n" +
	"  - source: \"src/keep.sh\"\n" +
	"    test: 'tests/keep.sh'\n" +
	"    by: \"agent:keeper\"\n" +
	"    origin: [\"coverage\"]\n" +
	"    future_field: kept\n" +
	"    adopted_at: \"2026-09-01\"\n"

func adoptedFile(rows ...string) string {
	return "contract: 1\nadopted:\n" + strings.Join(rows, "")
}

func targetRowYAML(by, extra string) string {
	return "  - {test: tests/t.sh, source: src/a.sh, origin: [coverage], adopted_at: 2026-10-01, by: '" + by + "'" + extra + "}\n"
}

var stampLineRe = regexp.MustCompile(`STAMP:[^|]*\|[^|]*\|(\d{4}-\d{2}-\d{2}/[0-9a-f]{10})\|`)

func stampIn(t *testing.T, out string) string {
	t.Helper()
	m := stampLineRe.FindStringSubmatch(out)
	if m == nil {
		t.Fatalf("no STAMP line in %q", out)
	}
	return m[1]
}

func adoptedRows(t *testing.T, r *fixture.Repo) []registry.AdoptedRow {
	t.Helper()
	reg, err := registry.Load(r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	return registry.AdoptionOf(reg).RawAdopted
}

func fileText(t *testing.T, r *fixture.Repo, p string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(r.Dir, p))
	if err != nil {
		return "<absent>"
	}
	return string(b)
}

// stampedRepo has tests/t.sh covering src/a.sh with a stamp naming its
// current blob (written by a person, so no provenance row came with it), and
// adoptedYAML as aitestmap/registry/adopted.yaml.
func stampedRepo(t *testing.T, adoptedYAML string) *fixture.Repo {
	t.Helper()
	r := stampRepo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": "#!/bin/sh\n# testmap:covers src/a.sh\necho\n"})
	if code, out, errs := call("annotate", "--by", "human:p@example.invalid", "tests/t.sh", "src/a.sh"); code != 0 {
		t.Fatalf("setup: %d %q %q", code, out, errs)
	}
	if adoptedYAML != "" {
		r.Write(t, registry.AdoptedPath, adoptedYAML)
	}
	hookCalls = nil
	return r
}

// The provenance rule through the real verbs: an automated re-stamp
// refreshes the matching row and keeps its by:, an explicit human deletes
// it, and the unrelated row stays byte-identical in every case.
func TestRestampProvenanceThroughVerbs(t *testing.T) {
	cases := []struct {
		name    string
		agent   string // AIT_AGENT_STRING
		args    []string
		stale   bool // change src/a.sh first
		deleted bool
	}{
		{"agent-verify-refreshes", "claudecode/opus5_5", []string{"verify", "tests/t.sh"}, true, false},
		{"auto-annotate-refreshes", "", []string{"annotate", "--by", "auto", "tests/t.sh", "src/a.sh"}, true, false},
		{"human-verify-deletes", "", []string{"verify", "--by", "human:p@example.invalid", "tests/t.sh"}, true, true},
		{"human-annotate-deletes", "", []string{"annotate", "--by", "human:p@example.invalid", "tests/t.sh", "src/a.sh"}, true, true},
		{"human-verify-current-deletes", "", []string{"verify", "--by", "human:p@example.invalid", "tests/t.sh"}, false, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := stampedRepo(t, adoptedFile(targetRowYAML("agent:old", ", stamp: 2026-10-01/0123456789"), unrelatedRow))
			if c.stale {
				r.Write(t, "src/a.sh", "a changed\n")
			}
			t.Setenv("AIT_AGENT_STRING", c.agent)
			code, out, errs := call(c.args...)
			if code != 0 || errs != "" {
				t.Fatalf("%d %q %q", code, out, errs)
			}
			if !strings.Contains(out, "WROTE:"+registry.AdoptedPath+"\n") {
				t.Errorf("no WROTE for adopted.yaml: %q", out)
			}
			text := fileText(t, r, registry.AdoptedPath)
			if !strings.Contains(text, unrelatedRow) {
				t.Errorf("the unrelated row changed:\n%s", text)
			}
			rows := adoptedRows(t, r)
			if c.deleted {
				if len(rows) != 1 || rows[0].Test != "tests/keep.sh" {
					t.Fatalf("rows %+v", rows)
				}
				return
			}
			if len(rows) != 2 || rows[0].Test != "tests/t.sh" || rows[0].By != "agent:old" || rows[0].Stamp != stampIn(t, out) {
				t.Fatalf("refreshed row: %+v (stamp %s)", rows, stampIn(t, out))
			}
		})
	}
}

// Re-stamping an edge with no provenance row leaves adopted.yaml
// byte-identical whatever the actor — an already-stamped edge is never
// relabelled as a machine claim.
func TestRestampWithoutRowLeavesAdoptedUntouched(t *testing.T) {
	for _, args := range [][]string{
		{"annotate", "--by", "agent:x", "tests/t.sh", "src/a.sh"},
		{"verify", "--by", "auto", "tests/t.sh"},
		{"verify", "--by", "human:p@example.invalid", "tests/t.sh"},
	} {
		r := stampedRepo(t, adoptedFile(unrelatedRow))
		before := fileText(t, r, registry.AdoptedPath)
		r.Write(t, "src/a.sh", "a changed\n")
		code, out, errs := call(args...)
		if code != 0 || errs != "" || strings.Contains(out, "adopted.yaml") {
			t.Fatalf("%v: %d %q %q", args, code, out, errs)
		}
		if fileText(t, r, registry.AdoptedPath) != before {
			t.Errorf("%v: adopted.yaml changed", args)
		}
	}
}

// A machine actor's first stamp gets its provenance row before the test file
// is written — an inserted line and an existing unstamped line alike; an
// unspecified actor's gets none.
func TestFirstStampProvenance(t *testing.T) {
	cases := []struct {
		name  string
		body  string
		args  []string
		agent string
		row   string // expected by:, "" = no row
	}{
		{"agent-insert", "#!/bin/sh\necho\n", []string{"annotate", "tests/t.sh", "src/a.sh"}, "claudecode/opus5_5", "agent:claudecode/opus5_5"},
		{"agent-unstamped-line", "#!/bin/sh\n# testmap:covers src/a.sh\necho\n", []string{"annotate", "tests/t.sh", "src/a.sh"}, "claudecode/opus5_5", "agent:claudecode/opus5_5"},
		{"auto-verify-unstamped-line", "#!/bin/sh\n# testmap:covers src/a.sh\necho\n", []string{"verify", "--by", "auto", "tests/t.sh"}, "", "auto"},
		{"unspecified-insert", "#!/bin/sh\necho\n", []string{"annotate", "tests/t.sh", "src/a.sh"}, "", ""},
		{"unspecified-unstamped-line", "#!/bin/sh\n# testmap:covers src/a.sh\necho\n", []string{"verify", "tests/t.sh"}, "", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := stampRepo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": c.body})
			t.Setenv("AIT_AGENT_STRING", c.agent)
			code, out, errs := call(c.args...)
			if code != 0 || errs != "" {
				t.Fatalf("%d %q %q", code, out, errs)
			}
			if c.row == "" {
				if fileText(t, r, registry.AdoptedPath) != "<absent>" || strings.Contains(out, "adopted.yaml") {
					t.Fatalf("an unspecified actor created provenance: %q", out)
				}
				return
			}
			if !strings.Contains(out, "WROTE:"+registry.AdoptedPath+"\nWROTE:tests/t.sh\n") {
				t.Errorf("provenance must be written before the test file: %q", out)
			}
			rows := adoptedRows(t, r)
			if len(rows) != 1 || rows[0].By != c.row || rows[0].Stamp != stampIn(t, out) || rows[0].Origin[0] != "annotate" {
				t.Fatalf("rows %+v", rows)
			}
		})
	}
}

// (a) The intent phase fails: no test file is touched; after the fix the
// retry writes both.
func TestIntentFailureWritesNothingAndRetryConverges(t *testing.T) {
	r := stampRepo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": "#!/bin/sh\necho\n"})
	r.Write(t, registry.AdoptedPath, "contract: 2\n")
	t.Setenv("AIT_AGENT_STRING", "claudecode/opus5_5")
	code, out, errs := call("annotate", "tests/t.sh", "src/a.sh")
	if code != 3 || out != "" || !strings.HasPrefix(errs, "RESTAMP_HOOK_ERROR:") {
		t.Fatalf("%d %q %q", code, out, errs)
	}
	if fileText(t, r, "tests/t.sh") != "#!/bin/sh\necho\n" || fileText(t, r, registry.AdoptedPath) != "contract: 2\n" {
		t.Fatal("a file was written")
	}
	r.Write(t, registry.AdoptedPath, "contract: 1\nadopted: []\n")
	code, out, _ = call("annotate", "tests/t.sh", "src/a.sh")
	if rows := adoptedRows(t, r); code != 0 || len(rows) != 1 || rows[0].Stamp != stampIn(t, out) {
		t.Fatalf("retry: %d %q %+v", code, out, rows)
	}
}

// (c) The post phase fails after the test file was written: the written
// file is still reported, and re-running the verb converges.
func TestPostFailureReportsWritesAndRetryConverges(t *testing.T) {
	for _, by := range []string{"human:p@example.invalid", "auto"} {
		r := stampedRepo(t, adoptedFile(targetRowYAML("agent:old", ", stamp: 2026-10-01/0123456789")))
		good := fileText(t, r, registry.AdoptedPath)
		r.Write(t, "src/a.sh", "a changed\n")
		r.Write(t, registry.AdoptedPath, "contract: 2\n")
		code, out, errs := call("verify", "--by", by, "tests/t.sh")
		if code != 3 || out != "WROTE:tests/t.sh\n" || !strings.HasPrefix(errs, "RESTAMP_HOOK_ERROR:") {
			t.Fatalf("%s: %d %q %q", by, code, out, errs)
		}
		r.Write(t, registry.AdoptedPath, good)
		code, out, errs = call("verify", "--by", by, "tests/t.sh")
		if code != 0 || errs != "" {
			t.Fatalf("%s retry: %d %q %q", by, code, out, errs)
		}
		rows := adoptedRows(t, r)
		if by == "auto" {
			if len(rows) != 1 || rows[0].Stamp == "2026-10-01/0123456789" || rows[0].Stamp != stampIn(t, out) {
				t.Fatalf("auto retry: %+v", rows)
			}
		} else if len(rows) != 0 {
			t.Fatalf("human retry: %+v", rows)
		}
	}
}

// The intent phase wrote provenance and then the test-file write failed: the
// verb exits non-zero and still reports the file it wrote (line and JSON),
// with no stamp claimed; restoring the directory and retrying converges.
func TestApplyFailureAfterIntentReportsCompletedWrites(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignores directory permissions")
	}
	for _, asJSON := range []bool{false, true} {
		r := stampRepo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": "#!/bin/sh\necho\n"})
		t.Setenv("AIT_AGENT_STRING", "claudecode/opus5_5")
		dir := filepath.Join(r.Dir, "tests")
		if err := os.Chmod(dir, 0o555); err != nil {
			t.Fatal(err)
		}
		args := []string{"annotate", "tests/t.sh", "src/a.sh"}
		if asJSON {
			args = []string{"annotate", "--json", "tests/t.sh", "src/a.sh"}
		}
		code, out, errs := call(args...)
		os.Chmod(dir, 0o755)
		if code == 0 || errs == "" {
			t.Fatalf("json=%v: %d %q %q", asJSON, code, out, errs)
		}
		if asJSON {
			var res struct {
				Stamps     []any    `json:"stamps"`
				Wrote      []string `json:"wrote"`
				Incomplete bool     `json:"incomplete"`
			}
			if err := json.Unmarshal([]byte(out), &res); err != nil || len(res.Stamps) != 0 || !res.Incomplete ||
				len(res.Wrote) != 1 || res.Wrote[0] != registry.AdoptedPath {
				t.Fatalf("json: %q %v", out, err)
			}
		} else if out != "WROTE:"+registry.AdoptedPath+"\n" {
			t.Fatalf("stdout %q", out)
		}
		if rows := adoptedRows(t, r); len(rows) != 1 || fileText(t, r, "tests/t.sh") != "#!/bin/sh\necho\n" {
			t.Fatalf("state: %+v", rows)
		}
		code, out, errs = call("annotate", "tests/t.sh", "src/a.sh")
		if rows := adoptedRows(t, r); code != 0 || len(rows) != 1 || rows[0].Stamp != stampIn(t, out) {
			t.Fatalf("retry: %d %q %q %+v", code, out, errs, rows)
		}
	}
}

// A review record outlives its carrier: a human verify deleting a verifies
// adoption whose memo write had failed first writes the record to
// onboard.yaml; when that write fails, the deletion is refused.
func TestHumanVerifyPreservesUnrecordedReview(t *testing.T) {
	carrier := targetRowYAML("agent:x", ", run: review-1, packet_sha: pk, test_blob: tb1")
	t.Run("preserved", func(t *testing.T) {
		r := stampedRepo(t, adoptedFile(carrier))
		code, out, errs := call("verify", "--by", "human:p@example.invalid", "tests/t.sh")
		if code != 0 || errs != "" || out != "STAMP:tests/t.sh|src/a.sh|"+stampIn(t, out)+"|current\n"+
			"WROTE:"+registry.OnboardPath+"\nWROTE:"+registry.AdoptedPath+"\nSTAMPS:0|0|1|0\n" {
			t.Fatalf("%d %q %q", code, out, errs)
		}
		reg, err := registry.Load(r.Dir)
		if err != nil {
			t.Fatal(err)
		}
		a := registry.AdoptionOf(reg)
		if len(a.RawAdopted) != 0 || len(a.Onboard.Reviews) != 1 || len(a.Unrecorded()) != 0 ||
			!a.Reviewed("tests/t.sh", "src/a.sh", "tb1", "agent:x") {
			t.Fatalf("%+v", a)
		}
	})
	t.Run("preservation-fails", func(t *testing.T) {
		if os.Geteuid() == 0 {
			t.Skip("root ignores directory permissions")
		}
		r := stampedRepo(t, adoptedFile(carrier))
		dir := filepath.Join(r.Dir, registry.Dir)
		if err := os.Chmod(dir, 0o555); err != nil {
			t.Fatal(err)
		}
		code, out, errs := call("verify", "--by", "human:p@example.invalid", "tests/t.sh")
		os.Chmod(dir, 0o755)
		if code != 3 || out != "" || !strings.HasPrefix(errs, "RESTAMP_HOOK_ERROR:") {
			t.Fatalf("%d %q %q", code, out, errs)
		}
		if rows := adoptedRows(t, r); len(rows) != 1 {
			t.Fatal("the carrier was deleted although its record was not preserved")
		}
		if code, _, _ := call("verify", "--by", "human:p@example.invalid", "tests/t.sh"); code != 0 || len(adoptedRows(t, r)) != 0 {
			t.Fatalf("retry: %d", code)
		}
	})
}
