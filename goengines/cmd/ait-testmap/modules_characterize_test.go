package main

import (
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// [characterize_check_without_table] `check` on a registry that declares no
// modules table — no `_modules.yaml`, no hand `modules:` block — is exactly
// what it was before M2.7, also when the repository carries a codemap and a
// Gradle build the providers would read: same lines, same exit, and the module
// inference never runs (it needs git, and these registries never opted in).
// The expected strings were recorded from the engine before M2.7 landed.

func characterizeCheck(t *testing.T, label string) {
	t.Helper()
	cases := []struct {
		args      []string
		code      int
		out, errs string
	}{
		{[]string{"check"}, 0, emptyAdoption + "CHECK:pass|0|0\n", ""},
		{[]string{"check", "--json"}, 0, `{"status":"pass","findings":[],"failing":0,"summary":` + emptyAdoptionJSON + "}\n", ""},
	}
	for _, c := range cases {
		code, out, errs := call(c.args...)
		if code != c.code || out != c.out || errs != c.errs {
			t.Errorf("%s %v: %d %q %q\nwant %d %q %q", label, c.args, code, out, errs, c.code, c.out, c.errs)
		}
	}
}

func TestCharacterizeCheckWithoutModulesTable(t *testing.T) {
	calls := countModuleInference(t)

	repo(t) // a plain directory: no git, no codemap, no Gradle
	withInputs(t, fakes())
	call("scan", "--apply")
	characterizeCheck(t, "non-git")

	r := fixture.New(t)
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	files := map[string]string{
		registry.ConfigPath:    "contract: 1\nbootstrap_until: 2099-01-01\n",
		"tests/test_a.sh":      "#!/usr/bin/env bash\n",
		"app/F.kt":             "class F\n",
		"src/a.sh":             "",
		"src/b.kt":             "",
		registry.CodemapPath:   "version: 1\nareas:\n  - name: src\n    path: src/\n    children:\n      - {name: deep, path: src/deep/}\n  - {name: app, path: app/}\n",
		"settings.gradle.kts":  "include(\":app\", \":lib\")\n",
		"app/build.gradle.kts": "dependencies { implementation(project(\":lib\")) }\n",
		"lib/build.gradle.kts": "",
	}
	for p, c := range files {
		r.Write(t, p, c)
	}
	r.Commit(t, "1", "test", "fixture")
	t.Chdir(r.Dir)
	call("scan", "--apply")
	characterizeCheck(t, "git+codemap+gradle")

	if *calls != 0 {
		t.Errorf("module inference ran %d time(s) for registries without a modules table", *calls)
	}
}
