package main

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// hookCalls records every post-re-stamp hook call the verbs make; hookFail
// makes the hook fail. The hook is registered once for the test binary,
// exactly as M2.6 registers its own from an init.
var (
	hookCalls []hookCall
	hookFail  error
)

type hookCall struct {
	actor string
	edges []annot.Restamp
}

func init() {
	annot.RegisterRestampHook(func(_ context.Context, _ string, a annot.Actor, e []annot.Restamp) ([]string, error) {
		hookCalls = append(hookCalls, hookCall{a.String(), e})
		return nil, hookFail
	})
}

// stampRepo is a git repository with a registry, as the process cwd.
func stampRepo(t *testing.T, files map[string]string) *fixture.Repo {
	t.Helper()
	r := fixture.New(t)
	r.Write(t, registry.ConfigPath, "contract: 1\n")
	for p, c := range files {
		r.Write(t, p, c)
	}
	t.Chdir(r.Dir)
	hookCalls, hookFail = nil, nil
	t.Setenv("AIT_AGENT_STRING", "")
	return r
}

var stampRe = `\d{4}-\d{2}-\d{2}/[0-9a-f]{10}`

func matchOut(t *testing.T, what, got, pattern string) {
	t.Helper()
	if !regexp.MustCompile(`^` + pattern + `$`).MatchString(got) {
		t.Errorf("%s: got %q, want /%s/", what, got, pattern)
	}
}

// The hook fires through the real verbs with the re-stamped edges and the
// actor: added by annotate, then restamped / current by verify, with an
// explicit human, a default agent and an unspecified actor.
func TestAnnotateVerifyThroughRun(t *testing.T) {
	r := stampRepo(t, map[string]string{
		"src/a.sh":   "a\n",
		"tests/t.sh": "#!/bin/sh\n# header\n# Covers: prose, never rewritten\necho\n",
	})
	code, out, errs := call("annotate", "--by", "human:x@example.invalid", "tests/t.sh", "src/a.sh")
	if code != 0 || errs != "" {
		t.Fatalf("annotate: %d %q %q", code, out, errs)
	}
	matchOut(t, "annotate", out, `STAMP:tests/t.sh\|src/a.sh\|`+stampRe+`\|added\nWROTE:tests/t.sh\nSTAMPS:1\|0\|0\|0\n`)
	data, _ := os.ReadFile(filepath.Join(r.Dir, "tests/t.sh"))
	if !strings.Contains(string(data), "# Covers: prose, never rewritten\n# testmap:covers src/a.sh @") {
		t.Errorf("file: %q", data)
	}
	r.Write(t, "src/a.sh", "a changed\n")
	t.Setenv("AIT_AGENT_STRING", "claudecode/opus5_5")
	code, out, _ = call("verify", "tests/t.sh")
	matchOut(t, "verify", out, `STAMP:tests/t.sh\|src/a.sh\|`+stampRe+`\|restamped\nWROTE:tests/t.sh\nSTAMPS:0\|1\|0\|0\n`)
	t.Setenv("AIT_AGENT_STRING", "")
	code2, out2, _ := call("verify", "tests/t.sh")
	matchOut(t, "verify again", out2, `STAMP:tests/t.sh\|src/a.sh\|`+stampRe+`\|current\nSTAMPS:0\|0\|1\|0\n`)
	if code != 0 || code2 != 0 {
		t.Errorf("codes %d %d", code, code2)
	}
	want := []struct{ actor, state string }{{"human:x@example.invalid", "added"}, {"agent:claudecode/opus5_5", "restamped"}, {"", "current"}}
	if len(hookCalls) != len(want) {
		t.Fatalf("hook calls %+v", hookCalls)
	}
	for i, w := range want {
		c := hookCalls[i]
		if c.actor != w.actor || len(c.edges) != 1 || string(c.edges[0].State) != w.state ||
			c.edges[0].Test.String() != "tests/t.sh" || c.edges[0].Source != "src/a.sh" || c.edges[0].Line != 4 {
			t.Errorf("call %d: %+v, want %+v", i, c, w)
		}
	}
}

func TestAnnotateJSONAndSkips(t *testing.T) {
	stampRepo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": "#!/bin/sh\n"})
	code, out, _ := call("annotate", "--json", "tests/t.sh", "src/a.sh", "src/gone.sh")
	var res struct {
		Stamps  []any `json:"stamps"`
		Skipped []struct {
			Test, Source, Reason string
		} `json:"skipped"`
		Refused []any    `json:"refused"`
		Wrote   []string `json:"wrote"`
	}
	if err := json.Unmarshal([]byte(out), &res); err != nil || code != 1 {
		t.Fatalf("%d %q %v", code, out, err)
	}
	if len(res.Stamps) != 0 || len(res.Wrote) != 0 || len(res.Skipped) != 1 || res.Skipped[0].Reason != "missing" {
		t.Errorf("all or nothing: %+v", res)
	}
	code, out, _ = call("verify", "tests/none.sh", "tests/t.sh#M")
	if code != 1 || out != "STAMP_REFUSED:tests/none.sh|missing\nSTAMP_REFUSED:tests/t.sh#M|no-member-block\nSTAMPS:0|0|0|2\n" {
		t.Errorf("refusals: %d %q", code, out)
	}
}

func TestStampVerbErrors(t *testing.T) {
	t.Chdir(t.TempDir())
	if code, out, errs := call("verify", "tests/t.sh"); code != 2 || out != "" || errs != "TESTMAP_ABSENT:aitestmap/\n" {
		t.Errorf("absent: %d %q %q", code, out, errs)
	}
	stampRepo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": "#!/bin/sh\n\n# testmap:covres src/a.sh\n"})
	if code, out, errs := call("verify", "tests/t.sh"); code != 3 || out != "" || errs != "ANNOT_INVALID:tests/t.sh|3|unknown key \"covres\"\n" {
		t.Errorf("invalid: %d %q %q", code, out, errs)
	}
	stampRepo(t, map[string]string{"src/a.sh": "a\n", "tests/t.sh": "#!/bin/sh\n"})
	hookFail = errors.New("adopted.yaml unwritable")
	if code, _, errs := call("annotate", "tests/t.sh", "src/a.sh"); code != 3 || errs != "RESTAMP_HOOK_ERROR:adopted.yaml unwritable\n" {
		t.Errorf("hook: %d %q", code, errs)
	}
	// REWRITE_CONFLICT is exit 75, inside the verbs' contract.
	var buf strings.Builder
	e := env{stdout: &strings.Builder{}, stderr: &buf}
	code := reportStampError(e, &annot.ConflictError{Path: "tests/t.sh", At: 4, Reason: "ownership"})
	if code != 75 || buf.String() != "REWRITE_CONFLICT:tests/t.sh|4\n" || !stampExits.Allows(code) {
		t.Errorf("conflict: %d %q", code, buf.String())
	}
	if lineproto.Enforce("annotate", stampExits, 75, &strings.Builder{}) != 75 {
		t.Error("75 outside the contract")
	}
}

func TestStampVerbUsage(t *testing.T) {
	stampRepo(t, map[string]string{"tests/t.sh": "#!/bin/sh\n"})
	for _, args := range [][]string{
		{"annotate"}, {"annotate", "tests/t.sh"}, {"annotate", "tests/t.sh@v1", "src/a.sh"},
		{"annotate", "--by", "robot:x", "tests/t.sh", "src/a.sh"}, {"annotate", "tests/t.sh", "./src/a.sh"},
		{"verify"}, {"verify", "--by", "human:", "tests/t.sh"}, {"verify", "tests/t.sh@v"},
	} {
		if code, out, errs := call(args...); code != 64 || out != "" || !strings.HasPrefix(errs, "USAGE:") {
			t.Errorf("%v: %d %q %q", args, code, out, errs)
		}
	}
	// --suggest and --from-body landed with M2.3 (annotate_deps.go); --author
	// (M7.4) is still a stub.
	for _, arm := range []string{"--author"} {
		if code, _, errs := call("annotate", arm, "tests/t.sh"); code != 64 || errs != "NOT_IMPLEMENTED:annotate "+arm+"\n" {
			t.Errorf("%s: %d %q", arm, code, errs)
		}
	}
}

// scan reads annotations through the production wiring: only the lister
// (M3.1, not landed) is swapped for a fake.
func TestScanThroughTheRealSource(t *testing.T) {
	r := stampRepo(t, map[string]string{
		"tests/t.sh": "#!/bin/sh\n# testmap:covers src/a.sh @2026-01-01/0123456789\n# testmap:unit M\n# testmap:covers src/m.sh\n",
		"tests/x.sh": "cat <<EOF\n# testmap:covers src/heredoc.sh\nEOF\n",
	})
	in := testmapInputs()
	in.Lister = fakeLister{}
	withInputs(t, in)
	code, out, errs := call("scan", "--apply")
	if code != 0 || errs != "" || out != "SCAN:2|2|0\nWROTE:"+registry.ScannedPath+"\n" {
		t.Fatalf("scan: %d %q %q", code, out, errs)
	}
	data, _ := os.ReadFile(filepath.Join(r.Dir, registry.ScannedPath))
	for _, want := range []string{"test: tests/t.sh\n", "source: src/a.sh", "stamped_at: \"2026-01-01\"", "stamped_blob: \"0123456789\"", "test: tests/t.sh#M", "source: src/m.sh"} {
		if !strings.Contains(string(data), want) {
			t.Errorf("_scanned.yaml lacks %q:\n%s", want, data)
		}
	}
	if strings.Contains(string(data), "heredoc") {
		t.Errorf("a heredoc look-alike reached the map:\n%s", data)
	}
	r.Write(t, "tests/bad.sh", "# testmap:covres src/a.sh\n")
	if code, out, errs := call("scan"); code != 3 || out != "" || !strings.HasPrefix(errs, "INPUT_ERROR:annotations|tests/bad.sh:1: unknown key") {
		t.Errorf("malformed: %d %q %q", code, out, errs)
	}
}
