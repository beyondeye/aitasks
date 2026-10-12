package main

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

type fakeAnns []registry.FileAnnotations

func (f fakeAnns) Annotations(context.Context, string) ([]registry.FileAnnotations, error) {
	return f, nil
}

type fakeLister []registry.Listing

func (f fakeLister) List(context.Context, string) ([]registry.Listing, error) { return f, nil }

type failingLister struct{}

func (failingLister) List(context.Context, string) ([]registry.Listing, error) {
	return nil, errors.New("runner list exploded")
}

// withInputs swaps the production wiring point, exactly as M2.2 / M3.1 fill it.
func withInputs(t *testing.T, in registry.Inputs) {
	t.Helper()
	old := testmapInputs
	testmapInputs = func() registry.Inputs { return in }
	t.Cleanup(func() { testmapInputs = old })
}

func write(t *testing.T, root string, files map[string]string) {
	t.Helper()
	for p, c := range files {
		full := filepath.Join(root, filepath.FromSlash(p))
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(full, []byte(c), 0o644); err != nil {
			t.Fatal(err)
		}
	}
}

// repo is a working directory with a registry and real files on disk.
func repo(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	write(t, root, map[string]string{
		registry.ConfigPath: "contract: 1\nbootstrap_until: 2099-01-01\n",
		"tests/test_a.sh":   "#!/usr/bin/env bash\n",
		"app/F.kt":          "class F\n",
		"src/a.sh":          "",
		"src/b.kt":          "",
	})
	t.Chdir(root)
	return root
}

func fakes() registry.Inputs {
	return registry.Inputs{
		Annotations: fakeAnns{
			{Path: "tests/test_a.sh", Units: []registry.UnitAnnotation{{Covers: []registry.Cover{{Source: "src/a.sh", Line: 2, StampedAt: "2026-10-01", StampedBlob: "0123456789"}}}}},
			{Path: "app/F.kt", Units: []registry.UnitAnnotation{{Member: "Welcome", Line: 4, Covers: []registry.Cover{{Source: "src/b.kt", Line: 5}}}}},
		},
		Lister: fakeLister{{Runner: "r", Units: []registry.ListedUnit{
			{ID: registry.MustParseID("tests/test_a.sh")},
			{ID: registry.MustParseID("app/F.kt#Welcome@ltr")},
			{ID: registry.MustParseID("app/F.kt#Welcome@rtl")},
		}}},
	}
}

func TestScanCheckAbsentRegistry(t *testing.T) {
	t.Chdir(t.TempDir())
	withInputs(t, fakes())
	for _, verb := range []string{"scan", "check"} {
		code, out, errs := call(verb)
		if code != 2 || out != "" || errs != "TESTMAP_ABSENT:aitestmap/\n" {
			t.Errorf("%s: %d %q %q", verb, code, out, errs)
		}
	}
}

// Production wiring before M2.2 / M3.1 land: both verbs refuse, exit 3.
func TestScanCheckInputUnavailable(t *testing.T) {
	repo(t)
	for _, verb := range []string{"scan", "check"} {
		code, out, errs := call(verb)
		if code != 3 || out != "" || errs != "INPUT_UNAVAILABLE:annotations\n" {
			t.Errorf("%s: %d %q %q", verb, code, out, errs)
		}
	}
}

// [command_level_injection_proof] The plug point works at command level: a
// fake annotation source's covers and a fake lister's variants reach
// _scanned.yaml through the real entry point, a re-run is byte-identical,
// and removing either provider flips the verbs to INPUT_UNAVAILABLE exit 3.
func TestInjectionProofThroughRun(t *testing.T) {
	root := repo(t)
	withInputs(t, fakes())
	code, out, errs := call("scan", "--apply")
	if code != 0 || errs != "" || out != "SCAN:2|2|2\nWROTE:"+registry.ScannedPath+"\n" {
		t.Fatalf("scan --apply: %d %q %q", code, out, errs)
	}
	data, err := os.ReadFile(filepath.Join(root, registry.ScannedPath))
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"test: app/F.kt#Welcome", "variants: [ltr, rtl]", "source: src/b.kt", "source: src/a.sh", "stamped_blob: \"0123456789\""} {
		if !strings.Contains(string(data), want) {
			t.Errorf("_scanned.yaml lacks %q:\n%s", want, data)
		}
	}
	code, out, _ = call("scan", "--apply")
	if code != 0 || out != "SCAN:2|2|2\n" {
		t.Fatalf("re-apply: %d %q (must not print WROTE:)", code, out)
	}
	again, _ := os.ReadFile(filepath.Join(root, registry.ScannedPath))
	if string(again) != string(data) {
		t.Fatal("re-apply is not byte-identical")
	}
	code, out, errs = call("check")
	if code != 0 || out != "CHECK:pass|0|0\n" || errs != "" {
		t.Fatalf("check: %d %q %q", code, out, errs)
	}
	for _, in := range []registry.Inputs{{Lister: fakes().Lister}, {Annotations: fakes().Annotations}} {
		withInputs(t, in)
		want := "INPUT_UNAVAILABLE:annotations\n"
		if in.Annotations != nil {
			want = "INPUT_UNAVAILABLE:lister\n"
		}
		for _, verb := range []string{"scan", "check"} {
			if code, out, errs := call(verb); code != 3 || out != "" || errs != want {
				t.Errorf("%s without a provider: %d %q %q", verb, code, out, errs)
			}
		}
	}
}

func TestCheckFailAndStrict(t *testing.T) {
	root := repo(t)
	withInputs(t, fakes())
	call("scan", "--apply")
	write(t, root, map[string]string{
		registry.ConfigPath:              "bootstrap_until: 2020-01-01\n",
		registry.RegistryDir + "/x.yaml": "owns: [\"src/**\"]\nedges: [{test: tests/test_unlisted.sh, covers: src/a.sh}]\n",
	})
	code, out, _ := call("check")
	if code != 0 || out != "UNREGISTERED:tests/test_unlisted.sh\nCHECK:pass|1|0\n" {
		t.Fatalf("non-strict: %d %q", code, out)
	}
	code, out, _ = call("check", "--strict")
	if code != 1 || out != "UNREGISTERED:tests/test_unlisted.sh\nCHECK:fail|1|1\n" {
		t.Fatalf("strict: %d %q", code, out)
	}
	if err := os.Remove(filepath.Join(root, "src/a.sh")); err != nil {
		t.Fatal(err)
	}
	code, out, _ = call("check")
	if code != 1 || !strings.Contains(out, "STALE_PATH:tests/test_a.sh|src/a.sh\n") || !strings.HasSuffix(out, "CHECK:fail|3|2\n") {
		t.Fatalf("stale: %d %q", code, out)
	}
	code, out, _ = call("check", "--json")
	var res struct {
		Status   string `json:"status"`
		Failing  int    `json:"failing"`
		Findings []struct {
			Rule   string   `json:"rule"`
			Fields []string `json:"fields"`
			Fail   bool     `json:"fail"`
		} `json:"findings"`
	}
	if code != 1 || json.Unmarshal([]byte(out), &res) != nil || res.Status != "fail" || res.Failing != 2 || len(res.Findings) != 3 || res.Findings[0].Rule != "STALE_PATH" || !res.Findings[0].Fail {
		t.Fatalf("--json: %d %q", code, out)
	}
}

func TestScanMemberDriftRefuses(t *testing.T) {
	root := repo(t)
	in := fakes()
	in.Lister = fakeLister{{Runner: "r", Units: []registry.ListedUnit{{ID: registry.MustParseID("tests/test_a.sh")}, {ID: registry.MustParseID("app/F.kt#Renamed")}}}}
	withInputs(t, in)
	code, out, _ := call("scan", "--apply")
	want := "DEAD_MEMBER:app/F.kt#Welcome\nUNANNOTATED_MEMBER:app/F.kt#Renamed\nSCAN:2|2|0\nSCAN_DRIFT:" + registry.ScannedPath + "\n"
	if code != 1 || out != want {
		t.Fatalf("%d %q\nwant %q", code, out, want)
	}
	if _, err := os.Stat(filepath.Join(root, registry.ScannedPath)); !os.IsNotExist(err) {
		t.Fatal("refused scan wrote _scanned.yaml")
	}
	code, out, _ = call("scan", "--json")
	var res registry.ScanResult
	if code != 1 || json.Unmarshal([]byte(out), &res) != nil || !res.Changed || len(res.Findings) != 2 || !res.Findings[0].Fail {
		t.Fatalf("--json: %d %q", code, out)
	}
}

func TestScanCheckFrameworkErrors(t *testing.T) {
	for _, tc := range []struct {
		file, body, want string
	}{
		{registry.ScannedPath, "contract: 2\n", "CONTRACT_MISMATCH:" + registry.ScannedPath + "|2|1\n"},
		{registry.RegistryDir + "/hand.yaml", "contract: 3\n", "CONTRACT_MISMATCH:" + registry.RegistryDir + "/hand.yaml|3|1\n"},
		{registry.ConfigPath, "contract: 2\n", "CONTRACT_MISMATCH:" + registry.ConfigPath + "|2|1\n"},
		{registry.RegistryDir + "/hand.yaml", "bogus: 1\n", "REGISTRY_INVALID:" + registry.RegistryDir + "/hand.yaml|unknown key bogus\n"},
	} {
		root := repo(t)
		withInputs(t, fakes())
		write(t, root, map[string]string{tc.file: tc.body})
		for _, verb := range []string{"scan", "check"} {
			code, out, errs := call(verb)
			if code != 3 || out != "" || errs != tc.want {
				t.Errorf("%s %s: %d %q %q, want %q", verb, tc.file, code, out, errs, tc.want)
			}
		}
	}
	repo(t)
	withInputs(t, registry.Inputs{Annotations: fakes().Annotations, Lister: failingLister{}})
	for _, verb := range []string{"scan", "check"} {
		if code, out, errs := call(verb); code != 3 || out != "" || errs != "INPUT_ERROR:lister|runner list exploded\n" {
			t.Errorf("%s: %d %q %q", verb, code, out, errs)
		}
	}
}

// A real unreadable directory under a declared pattern: exit 3 with
// CHECK_ERROR and no CHECK: line, plain and strict.
func TestCheckUnreadableDirectoryNeverPasses(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("permissions are not enforced for root")
	}
	root := repo(t)
	in := fakes()
	in.Lister = fakeLister{{Runner: "r", ArtifactGlobs: []string{"shots/**/*.png"}, Units: []registry.ListedUnit{
		{ID: registry.MustParseID("tests/test_a.sh")}, {ID: registry.MustParseID("app/F.kt#Welcome@ltr")}, {ID: registry.MustParseID("app/F.kt#Welcome@rtl")},
	}}}
	withInputs(t, in)
	call("scan", "--apply")
	write(t, root, map[string]string{"shots/deep/x.png": ""})
	dir := filepath.Join(root, "shots", "deep")
	if err := os.Chmod(dir, 0o000); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.Chmod(dir, 0o755) })
	for _, args := range [][]string{{"check"}, {"check", "--strict"}, {"check", "--json"}} {
		code, out, errs := call(args...)
		if code != 3 || out != "" || !strings.HasPrefix(errs, "CHECK_ERROR:enumerate|") || strings.Contains(errs, "CHECK:") {
			t.Errorf("%v: %d %q %q", args, code, out, errs)
		}
	}
}

func TestScanCheckUsage(t *testing.T) {
	for _, tc := range []struct {
		args []string
		want string
	}{
		{[]string{"scan", "--bogus"}, "USAGE:ait-testmap scan [--apply] [--json]\n"},
		{[]string{"scan", "extra"}, "USAGE:ait-testmap scan [--apply] [--json]\n"},
		{[]string{"check", "--apply"}, "USAGE:ait-testmap check [--strict] [--json]\n"},
	} {
		if code, out, errs := call(tc.args...); code != 64 || out != "" || errs != tc.want {
			t.Errorf("%v: %d %q %q", tc.args, code, out, errs)
		}
	}
}
