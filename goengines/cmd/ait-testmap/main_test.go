package main

import (
	"bytes"
	"encoding/json"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"testing"
)

func call(args ...string) (code int, stdout, stderr string) {
	var o, e bytes.Buffer
	code = run(args, &o, &e)
	return code, o.String(), e.String()
}

// The verb table the proposal fixes (Engine binary identity and budget).
// Adding or dropping a verb is a proposal change, not a table edit.
var proposalVerbs = []string{
	"test", "select", "schedule", "run", "scan", "check", "stale", "annotate",
	"verify", "explain", "axes", "areas", "classify", "costs", "score",
	"attribute", "readiness", "brief", "onboard", "runner", "version",
}

var proposalOnboard = []string{
	"detect", "inventory", "seed", "review", "classify", "adopt", "reject",
	"scaffold", "status", "finish",
}

func names(table []verb) []string {
	var n []string
	for _, v := range table {
		n = append(n, leaf(v.Name))
	}
	return n
}

func TestVerbTableMatchesProposal(t *testing.T) {
	if got := names(verbs); !slices.Equal(got, proposalVerbs) {
		t.Fatalf("verbs %v\nwant  %v", got, proposalVerbs)
	}
	for _, v := range verbs {
		if v.Name == "onboard" && !slices.Equal(names(v.Sub), proposalOnboard) {
			t.Fatalf("onboard %v\nwant    %v", names(v.Sub), proposalOnboard)
		}
		if (v.Run == nil) == (v.Sub == nil) {
			t.Fatalf("%s: exactly one of Run and Sub", v.Name)
		}
	}
}

func TestStubsExit64(t *testing.T) {
	var calls [][]string
	for _, v := range proposalVerbs {
		switch v {
		case "version":
		case "onboard":
			for _, s := range proposalOnboard {
				calls = append(calls, []string{"onboard", s, "--flag"})
			}
		case "runner":
			calls = append(calls, []string{"runner", "pytest"})
		default:
			calls = append(calls, []string{v, "--anything"})
		}
	}
	for _, args := range calls {
		code, out, errs := call(args...)
		want := "NOT_IMPLEMENTED:" + strings.Join(args[:len(args)-1], " ") + "\n"
		if args[0] == "runner" {
			want = "NOT_IMPLEMENTED:runner\n"
		}
		if code != 64 || out != "" || errs != want {
			t.Errorf("%v: code %d stdout %q stderr %q, want 64 / %q", args, code, out, errs, want)
		}
	}
}

func TestUnknownAndUsage(t *testing.T) {
	for _, tc := range []struct {
		args []string
		want string
	}{
		{nil, "USAGE:ait-testmap <verb> [args]\n"},
		{[]string{"bogus"}, "UNKNOWN_VERB:bogus\nUSAGE:ait-testmap <verb> [args]\n"},
		{[]string{"onboard"}, "USAGE:ait-testmap onboard <verb> [args]\n"},
		{[]string{"onboard", "bogus"}, "UNKNOWN_VERB:onboard bogus\nUSAGE:ait-testmap onboard <verb> [args]\n"},
		{[]string{"version", "--bogus"}, "USAGE:ait-testmap version [--json]\n"},
		{[]string{"version", "extra"}, "USAGE:ait-testmap version [--json]\n"},
	} {
		code, out, errs := call(tc.args...)
		if code != 64 || out != "" || errs != tc.want {
			t.Errorf("%v: code %d stdout %q stderr %q", tc.args, code, out, errs)
		}
	}
}

func TestExitContractEnforced(t *testing.T) {
	var e bytes.Buffer
	table := []verb{{Name: "x", Run: func(env, []string) int { return 1 }, Exits: notImplemented}}
	if code := dispatch(table, "", []string{"x"}, env{stdout: &e, stderr: &e}); code != 3 {
		t.Fatalf("code %d", code)
	}
	if e.String() != "EXIT_CONTRACT_VIOLATION:x|1\n" {
		t.Fatalf("stderr %q", e.String())
	}
}

func fakeEngine(t *testing.T, path string) {
	old := enginePath
	enginePath = func() (string, error) { return path, nil }
	t.Cleanup(func() { enginePath = old })
}

func TestVersionText(t *testing.T) {
	fakeEngine(t, "/opt/engine/ait-testmap")
	code, out, errs := call("version")
	want := "VERSION:devel\nCOMMIT:unknown\nCONTRACT:1\nENGINE:/opt/engine/ait-testmap\n"
	if code != 0 || out != want || errs != "" {
		t.Fatalf("code %d out %q err %q", code, out, errs)
	}
}

func TestVersionJSON(t *testing.T) {
	fakeEngine(t, "/opt/engine/ait-testmap")
	code, out, _ := call("version", "--json")
	want := `{"version":"devel","commit":"unknown","contract":1,"engine":"/opt/engine/ait-testmap"}` + "\n"
	if code != 0 || out != want {
		t.Fatalf("code %d out %q", code, out)
	}
}

func TestVersionUnsafeEnginePath(t *testing.T) {
	fakeEngine(t, "/weird|path")
	if code, out, errs := call("version"); code != 3 || !strings.HasPrefix(errs, "OUTPUT_ERROR:") || strings.Contains(out, "ENGINE:") {
		t.Fatalf("code %d out %q err %q", code, out, errs)
	}
}

// Pins the -X variable names the release build (M1.3) and `ait engine build`
// (M1.5) set, and ENGINE: resolving to the real binary.
func TestLdflagsWiring(t *testing.T) {
	if testing.Short() {
		t.Skip("builds a binary")
	}
	bin := filepath.Join(t.TempDir(), "ait-testmap")
	build := exec.Command("go", "build", "-trimpath", "-buildvcs=false",
		"-ldflags", "-s -w -X main.version=9.9.9-dev+abc123 -X main.commit=abc123", "-o", bin, ".")
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build: %v\n%s", err, out)
	}
	out, err := exec.Command(bin, "version", "--json").Output()
	if err != nil {
		t.Fatal(err)
	}
	var got versionInfo
	if err := json.Unmarshal(out, &got); err != nil {
		t.Fatal(err)
	}
	real, _ := filepath.EvalSymlinks(bin)
	if got != (versionInfo{Version: "9.9.9-dev+abc123", Commit: "abc123", Contract: 1, Engine: real}) {
		t.Fatalf("got %+v", got)
	}
	err = exec.Command(bin, "select").Run()
	if ee, ok := err.(*exec.ExitError); !ok || ee.ExitCode() != 64 {
		t.Fatalf("stub via binary: %v", err)
	}
}

func BenchmarkDispatchVersion(b *testing.B) {
	var o, e bytes.Buffer
	for b.Loop() {
		o.Reset()
		if run([]string{"version", "--json"}, &o, &e) != 0 {
			b.Fatal(e.String())
		}
	}
}
