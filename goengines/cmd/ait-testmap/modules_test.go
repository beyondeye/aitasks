package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// modulesRepo is a git repository (the module inference scans it) with a
// registry, as the process cwd; scans use a private cache.
func modulesRepo(t *testing.T, files map[string]string) *fixture.Repo {
	t.Helper()
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	r := fixture.New(t)
	r.Write(t, registry.ConfigPath, "contract: 1\nbootstrap_until: 2099-01-01\n")
	for p, c := range files {
		r.Write(t, p, c)
	}
	t.Chdir(r.Dir)
	withInputs(t, registry.Inputs{Annotations: fakeAnns{}, Lister: fakeLister{}})
	return r
}

// A codemap with a child entry and an unnameable entry, a Gradle build with
// one included project, a hand module refining a codemap module, and files no
// scanner reads (JSON, Markdown, text).
var modulesFixture = map[string]string{
	registry.CodemapPath: "version: 1\nareas:\n" +
		"  - name: src\n    path: src/\n    children:\n      - {name: deep, path: src/deep/}\n" +
		"  - {name: odd, path: a:b/}\n",
	"settings.gradle.kts":               "include(\":app\")\n",
	"app/build.gradle.kts":              "",
	"app/A.kt":                          "class A\n",
	"src/a.sh":                          "#!/bin/sh\n. ./src/deep/d.sh\n",
	"src/deep/d.sh":                     "#!/bin/sh\n",
	"src/conf.json":                     "{}\n",
	"README.md":                         "# r\n",
	"a:b/x.txt":                         "x\n",
	registry.RegistryDir + "/hand.yaml": "contract: 1\nmodules:\n  cfg: {paths: [\"src/conf.json\"]}\n",
}

const modulesTable = "MODULE:cfg|hand|src/conf.json|1|file:aitestmap/registry/hand.yaml\n" +
	"MODULE:codemap:src|codemap|src|1|entry:src\n" +
	"MODULE:codemap:src:deep|codemap|src/deep|1|entry:deep\n" +
	"MODULE:gradle:app|gradle|app|2|settings:settings.gradle.kts,build:app/build.gradle.kts\n"

func TestModulesVerb(t *testing.T) {
	root := modulesRepo(t, modulesFixture).Dir
	inferred := "MODULE_REFUSED:codemap|a:b|unnameable\n" +
		"MODULE_REFUSED:gradle|.|repository_root\n" +
		"MODULE_CONFLICT:cfg@hand|codemap:src@codemap|1|src/conf.json\n" +
		modulesTable
	// Unmapped: config.yaml, hand.yaml, code_areas.yaml, settings.gradle.kts,
	// README.md and a:b/x.txt (the refused codemap entry's file).
	want := inferred + "MODULES:4|6|hand=1,codemap=2,gradle=1\nMODULES_DRIFT:" + registry.ModulesPath + "\n"
	if code, out, errs := call("modules", "--scan"); code != 0 || errs != "" || out != want {
		t.Fatalf("scan dry run: %d %q\n got %q\nwant %q", code, errs, out, want)
	}
	if _, err := os.Stat(filepath.Join(root, registry.ModulesPath)); !os.IsNotExist(err) {
		t.Fatal("a dry run wrote the table")
	}
	// Before the table is written, --list knows only the hand module.
	if code, out, _ := call("modules", "--list"); code != 0 || out != "MODULE:cfg|hand|src/conf.json|1|file:aitestmap/registry/hand.yaml\nMODULES:1|10|hand=1\n" {
		t.Fatalf("list before apply: %d %q", code, out)
	}
	want = inferred + "MODULES:4|6|hand=1,codemap=2,gradle=1\nWROTE:" + registry.ModulesPath + "\n"
	if code, out, errs := call("modules", "--scan", "--apply"); code != 0 || errs != "" || out != want {
		t.Fatalf("apply: %d %q\n got %q\nwant %q", code, errs, out, want)
	}
	written, err := os.ReadFile(filepath.Join(root, registry.ModulesPath))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(string(written), registry.ModulesHeader) || !strings.Contains(string(written), "evidence: {from: src/a.sh, to: src/deep/d.sh}") {
		t.Fatalf("written table:\n%s", written)
	}
	// Re-applying writes nothing and reports no drift (the table itself is
	// now one more unmapped file).
	want = inferred + "MODULES:4|7|hand=1,codemap=2,gradle=1\n"
	if code, out, _ := call("modules", "--scan", "--apply"); code != 0 || out != want {
		t.Fatalf("re-apply: %d %q", code, out)
	}
	again, _ := os.ReadFile(filepath.Join(root, registry.ModulesPath))
	if string(again) != string(written) {
		t.Fatal("re-apply is not byte-identical")
	}
	if code, out, _ := call("modules"); code != 0 || out != modulesTable+"MODULES:4|7|hand=1,codemap=2,gradle=1\n" {
		t.Fatalf("list: %d %q", code, out)
	}
	for p, line := range map[string]string{
		"src/conf.json":        "MODULE_OF:src/conf.json|cfg|path\n",
		"src/deep/d.sh":        "MODULE_OF:src/deep/d.sh|codemap:src:deep|path\n",
		"app/build.gradle.kts": "MODULE_OF:app/build.gradle.kts|gradle:app|path\n",
		"README.md":            "MODULE_OF:README.md||unmapped\n",
		"src/gone.sh":          "MODULE_OF:src/gone.sh|codemap:src|path\n", // a path that does not exist is still owned
	} {
		if code, out, errs := call("modules", "--explain", p); code != 0 || errs != "" || out != line {
			t.Errorf("explain %s: %d %q %q", p, code, out, errs)
		}
	}
	var j struct {
		Modules []struct {
			Name    string   `json:"name"`
			Members []string `json:"members"`
			Deps    []struct {
				Module string `json:"module"`
			} `json:"deps"`
		} `json:"modules"`
		Unmapped int `json:"unmapped"`
	}
	code, out, _ := call("modules", "--list", "--json")
	if code != 0 || json.Unmarshal([]byte(out), &j) != nil || len(j.Modules) != 4 || j.Unmapped != 7 || j.Modules[1].Name != "codemap:src" || len(j.Modules[1].Deps) != 1 || j.Modules[1].Deps[0].Module != "codemap:src:deep" {
		t.Fatalf("list --json: %d %q", code, out)
	}
	// list / explain consistency: every member's --explain names its module.
	for _, m := range j.Modules {
		for _, p := range m.Members {
			if _, out, _ := call("modules", "--explain", p); out != "MODULE_OF:"+p+"|"+m.Name+"|path\n" {
				t.Errorf("%s listed under %s, explained as %q", p, m.Name, out)
			}
		}
	}
	// check: the committed table is fresh, the conflict is reported (Info).
	if code, out, _ := call("check"); code != 0 || out != "MODULE_CONFLICT:cfg@hand|codemap:src@codemap|1|src/conf.json\n"+emptyAdoption+"CHECK:pass|1|0\n" {
		t.Fatalf("check fresh: %d %q", code, out)
	}
	write(t, root, map[string]string{registry.CodemapPath: strings.Replace(modulesFixture[registry.CodemapPath], "name: deep", "name: deeper", 1)})
	if code, out, _ := call("check"); code != 0 || out != "MODULES_DRIFT:"+registry.ModulesPath+"\nMODULE_CONFLICT:cfg@hand|codemap:src@codemap|1|src/conf.json\n"+emptyAdoption+"CHECK:pass|2|0\n" {
		t.Fatalf("check drifted: %d %q", code, out)
	}
	if code, out, _ := call("modules", "--scan"); code != 0 || !strings.HasSuffix(out, "MODULES_DRIFT:"+registry.ModulesPath+"\n") {
		t.Fatalf("scan drifted: %d %q", code, out)
	}
}

// Two hand modules meeting only on a file no scanner reads: every surface
// refuses with the same REGISTRY_INVALID line, and nothing is written.
func TestModulesHandOverlapOnUnscannedFile(t *testing.T) {
	root := modulesRepo(t, map[string]string{
		"conf/app.json":                     "{}\n",
		"conf/x.sh":                         "#!/bin/sh\n",
		registry.RegistryDir + "/hand.yaml": "contract: 1\nmodules:\n  conf: {paths: [\"conf/**\"]}\n  app: {paths: [\"conf/app.json\"]}\n",
	}).Dir
	const want = "REGISTRY_INVALID:aitestmap/registry/hand.yaml|modules: app and conf both claim conf/app.json\n"
	for _, args := range [][]string{
		{"modules", "--explain", "conf/app.json"}, {"modules", "--list"}, {"modules", "--scan", "--apply"}, {"check"},
	} {
		if code, out, errs := call(args...); code != 3 || out != "" || errs != want {
			t.Errorf("%v: %d %q %q", args, code, out, errs)
		}
	}
	if _, err := os.Stat(filepath.Join(root, registry.ModulesPath)); !os.IsNotExist(err) {
		t.Fatal("an invalid table was written")
	}
	if code, out, _ := call("modules", "--explain", "conf/x.sh"); code != 0 || out != "MODULE_OF:conf/x.sh|conf|path\n" {
		t.Fatalf("an unambiguous path still explains: %d %q", code, out)
	}
}

func TestModulesVerbUsageAndErrors(t *testing.T) {
	modulesRepo(t, map[string]string{})
	for _, args := range [][]string{
		{"modules", "--apply"}, {"modules", "--list", "--scan"}, {"modules", "--explain", "a", "--scan"},
		{"modules", "--explain", "/abs"}, {"modules", "--explain", ""}, {"modules", "extra"},
	} {
		if code, out, errs := call(args...); code != 64 || out != "" || !strings.HasPrefix(errs, "USAGE:") {
			t.Errorf("%v: %d %q %q, want usage", args, code, out, errs)
		}
	}
	if code, out, _ := call("modules"); code != 0 || out != "MODULES:0|1|\n" {
		t.Fatalf("empty: %d %q", code, out)
	}
	write(t, ".", map[string]string{registry.CodemapPath: "version: 3\nareas: []\n"})
	if code, _, errs := call("modules", "--scan"); code != 3 || errs != "INPUT_ERROR:code_areas|version 3 is not 1\n" {
		t.Fatalf("bad codemap: %d %q", code, errs)
	}
	t.Chdir(t.TempDir())
	if code, _, errs := call("modules"); code != 2 || errs != "TESTMAP_ABSENT:aitestmap/\n" {
		t.Fatalf("no registry: %d %q", code, errs)
	}
}

// An output record that cannot be rendered refuses the run before anything is
// written: a refused codemap entry whose path holds '|' cannot travel in a
// MODULE_REFUSED line, so `--scan --apply` exits 3 and the table is untouched.
func TestModulesScanApplyWritesNothingOnUnrenderableOutput(t *testing.T) {
	root := modulesRepo(t, map[string]string{
		registry.CodemapPath: "version: 1\nareas:\n  - {name: src, path: src/}\n  - {name: odd, path: \"a|b/\"}\n",
		"src/x.sh":           "#!/bin/sh\n",
	}).Dir
	code, out, errs := call("modules", "--scan", "--apply")
	if code != 3 || out != "" || !strings.HasPrefix(errs, "CHECK_ERROR:output|") {
		t.Fatalf("%d %q %q", code, out, errs)
	}
	if _, err := os.Stat(filepath.Join(root, registry.ModulesPath)); !os.IsNotExist(err) {
		t.Fatal("the table was written although the run was refused")
	}
}

// --list and --explain read the committed table: a codemap broken since the
// last --scan --apply does not hide it (only --scan, which re-infers, refuses).
func TestModulesListSurvivesABrokenCodemap(t *testing.T) {
	root := modulesRepo(t, map[string]string{
		registry.CodemapPath: "version: 1\nareas:\n  - {name: src, path: src/}\n",
		"src/x.sh":           "#!/bin/sh\n",
	}).Dir
	if code, _, errs := call("modules", "--scan", "--apply"); code != 0 {
		t.Fatalf("apply: %d %q", code, errs)
	}
	write(t, root, map[string]string{registry.CodemapPath: "version: 2\nareas: []\n"})
	if code, out, errs := call("modules", "--list"); code != 0 || errs != "" || !strings.HasPrefix(out, "MODULE:codemap:src|codemap|src|1|entry:src\nMODULES:1|") {
		t.Fatalf("list: %d %q %q", code, out, errs)
	}
	if code, out, _ := call("modules", "--explain", "src/x.sh"); code != 0 || out != "MODULE_OF:src/x.sh|codemap:src|path\n" {
		t.Fatalf("explain: %d %q", code, out)
	}
	if code, _, errs := call("modules", "--scan"); code != 3 || errs != "INPUT_ERROR:code_areas|version 2 is not 1\n" {
		t.Fatalf("scan: %d %q", code, errs)
	}
}
