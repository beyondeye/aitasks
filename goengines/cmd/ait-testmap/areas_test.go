package main

import (
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

func TestAreasVerb(t *testing.T) {
	root := repo(t)
	if code, out, errs := call("areas"); code != 0 || errs != "" || out != "AREAS:0\n" {
		t.Fatalf("empty: %d %q %q", code, out, errs)
	}
	if code, _, errs := call("areas", "--import-codemap"); code != 2 || errs != "CODEMAP_ABSENT:"+registry.CodemapPath+"\n" {
		t.Fatalf("no codemap: %d %q", code, errs)
	}
	write(t, root, map[string]string{registry.CodemapPath: "version: 1\nareas:\n  - {name: src, path: src/}\n  - {name: app, path: app/}\n"})
	want := "AREA_IMPORT:app|app/**|added\nAREA_IMPORT:src|src/**|added\n"
	if code, out, errs := call("areas", "--import-codemap"); code != 0 || errs != "" || out != want {
		t.Fatalf("dry run: %d %q %q", code, out, errs)
	}
	if code, out, _ := call("areas", "--import-codemap", "--apply"); code != 0 || out != want+"WROTE:"+registry.AreasPath+"\n" {
		t.Fatalf("apply: %d %q", code, out)
	}
	if code, out, _ := call("areas", "--list"); code != 0 || out != "AREA:app|1|1|0\nAREA:src|1|2|0\nAREAS:2\n" {
		t.Fatalf("list: %d %q", code, out)
	}
	if code, out, _ := call("areas", "--json"); code != 0 || !strings.HasPrefix(out, `{"areas":[{"name":"app","globs":["app/**"],"files":1,"rows":0}`) {
		t.Fatalf("json: %d %q", code, out)
	}
	write(t, root, map[string]string{registry.CodemapPath: "version: 1\nareas:\n  - {name: src, path: src/}\n  - {name: src, path: app/}\n"})
	if code, _, errs := call("areas", "--import-codemap"); code != 3 || errs != "INPUT_ERROR:code_areas|duplicate area src\n" {
		t.Fatalf("duplicate: %d %q", code, errs)
	}
	for _, args := range [][]string{{"areas", "--apply"}, {"areas", "--list", "--import-codemap"}, {"areas", "extra"}} {
		if code, _, _ := call(args...); code != 64 {
			t.Errorf("%v: %d, want usage", args, code)
		}
	}
	t.Chdir(t.TempDir())
	if code, _, errs := call("areas"); code != 2 || errs != "TESTMAP_ABSENT:aitestmap/\n" {
		t.Fatalf("no registry: %d %q", code, errs)
	}
}

func TestClassifyVerbUsage(t *testing.T) {
	repo(t)
	for _, args := range [][]string{{"classify"}, {"classify", "tests/test_a.sh"}, {"classify", "--bogus"}} {
		if code, out, _ := call(args...); code != 64 || out != "" {
			t.Errorf("%v: %d %q, want usage", args, code, out)
		}
	}
	t.Chdir(t.TempDir())
	if code, _, errs := call("classify", "--suggest"); code != 2 || errs != "TESTMAP_ABSENT:aitestmap/\n" {
		t.Fatalf("no registry: %d %q", code, errs)
	}
}
