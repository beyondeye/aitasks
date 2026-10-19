package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

// [e2e_real_inputs_fixture] M2.5 end to end through the real verb table, the
// real annotation source (annot.Source) and the real runner repository: no
// fake input anywhere, so the toRegistry and testmapInputs wiring is what
// runs.
func TestScopedEndToEndRealInputs(t *testing.T) {
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	r := fixture.New(t)
	wide := "#!/usr/bin/env bash\n"
	for i := 1; i <= 9; i++ {
		wide += fmt.Sprintf("# testmap:covers src/s%d.sh\n", i)
	}
	for i := 1; i <= 9; i++ {
		wide += fmt.Sprintf(". \"$PROJECT_DIR/src/s%d.sh\"\n", i)
	}
	files := map[string]string{
		registry.ConfigPath:  "contract: 1\nbootstrap_until: 2099-01-01\n",
		registry.CodemapPath: "version: 1\nareas:\n  - name: board\n    path: src/board/\n    children:\n      - {name: board_ui, path: src/board/ui/}\n",
		runner.RunnersPath:   "contract: 1\nrunners:\n  - name: shell\n    bind: ['tests/*.sh']\n    timeout_s: 5\n    batch_timeout_s: 10\n",
		runner.RunnersDir + "/shell.sh": "#!/usr/bin/env bash\ncase \"$1\" in\n" +
			"describe) printf 'unit: file\\ntimeouts: batch\\n';;\n" +
			"list) printf 'tests/test_board_live.sh\\tfile\\tb\\ntests/test_flow.sh#flow_a\\tmethod\\tf\\ntests/test_wide.sh\\tfile\\tw\\n';;\n" +
			"esac\n",
		"tests/test_board_live.sh": "#!/usr/bin/env bash\n# testmap:kind integration\n# testmap:area board\ntmux new-session -d\n",
		"tests/test_flow.sh": "#!/usr/bin/env bash\n# testmap:unit flow_a\n# testmap:kind e2e\n# testmap:scope src/board/**\n" +
			"# testmap:trigger src/lib/x.sh\nflow_a() { :; }\n",
		"tests/lib/fixture.sh": "#!/usr/bin/env bash\n# testmap:reads tests/*.sh\n",
		"tests/test_wide.sh":   wide,
		"src/board/app.sh":     "", "src/board/ui/view.sh": "", "src/lib/x.sh": "",
	}
	for i := 1; i <= 9; i++ {
		files[fmt.Sprintf("src/s%d.sh", i)] = ""
	}
	for p, c := range files {
		r.Write(t, p, c)
	}
	if err := os.Chmod(filepath.Join(r.Dir, runner.RunnersDir, "shell.sh"), 0o755); err != nil {
		t.Fatal(err)
	}
	r.Commit(t, "1", "test", "fixture")
	t.Chdir(r.Dir)

	expect := func(step string, code int, out, errs string, args ...string) {
		t.Helper()
		c, o, e := call(args...)
		if c != code || o != out || e != errs {
			t.Fatalf("%s: %v\nexit %d (want %d)\nstdout %q\nwant   %q\nstderr %q\nwant   %q", step, args, c, code, o, out, e, errs)
		}
	}
	expect("import", 0, "AREA_IMPORT:board|src/board/**|added\nAREA_IMPORT:board_ui|src/board/ui/**|added\nWROTE:"+registry.AreasPath+"\n", "",
		"areas", "--import-codemap", "--apply")
	expect("scan", 0, "SCAN:2|9|0\nWROTE:"+registry.ScannedPath+"\nWROTE:"+registry.ScopedPath+"\n", "", "scan", "--apply")
	data, err := os.ReadFile(filepath.Join(r.Dir, registry.ScopedPath))
	if err != nil {
		t.Fatal(err)
	}
	wantScoped := registry.GeneratedHeader + "contract: 1\nscopes:\n" +
		"  - test: tests/test_board_live.sh\n    kind: integration\n    areas: [board]\n    line: 2\n" +
		"  - test: tests/test_flow.sh#flow_a\n    kind: e2e\n    globs: [src/board/**]\n    triggers: [src/lib/x.sh]\n    line: 3\n" +
		"reads:\n  - helper: tests/lib/fixture.sh\n    globs: [tests/*.sh]\n    line: 2\n"
	if string(data) != wantScoped {
		t.Fatalf("_scoped.yaml:\n%s\nwant\n%s", data, wantScoped)
	}
	expect("check", 0, "KIND_MISMATCH:tests/test_wide.sh|9|CONVERT_TO_SUITE\n"+emptyAdoption+"CHECK:pass|1|0\n", "", "check")
	expect("classify", 0, "CLASSIFY:tests/test_wide.sh|integration|fanout:9\n", "", "classify", "--suggest")

	// The child area's directory goes away: its glob is dead.
	if err := os.RemoveAll(filepath.Join(r.Dir, "src/board/ui")); err != nil {
		t.Fatal(err)
	}
	expect("dead area", 1, "DEAD_SCOPE:"+registry.AreasPath+"|areas|board_ui|src/board/ui/**\n"+
		"KIND_MISMATCH:tests/test_wide.sh|9|CONVERT_TO_SUITE\n"+emptyAdoption+"CHECK:fail|2|1\n", "", "check")

	// A reads line moved into a listed test is refused by both verbs.
	r.Write(t, "tests/test_flow.sh", "#!/usr/bin/env bash\n# testmap:reads x/*\n# testmap:unit flow_a\n# testmap:kind e2e\n# testmap:scope src/board/**\nflow_a() { :; }\n")
	refused := "INPUT_ERROR:annotations|tests/test_flow.sh:2: testmap:reads is legal only in a helper (a file no runner lists)\n"
	for _, verb := range []string{"scan", "check"} {
		expect(verb+" refused", 3, "", refused, verb)
	}
	if got, _ := os.ReadFile(filepath.Join(r.Dir, registry.ScopedPath)); !strings.Contains(string(got), "test_flow.sh#flow_a") {
		t.Fatal("a refused scan must not rewrite _scoped.yaml")
	}
}

// A scoped annotation the generated file could not hold (an area name with
// '/') is refused before anything is written, so the registry stays
// loadable and fixing the annotation recovers.
func TestScopedInvalidAreaRecovers(t *testing.T) {
	r := fixture.New(t)
	r.Write(t, registry.ConfigPath, "contract: 1\nbootstrap_until: 2099-01-01\n")
	r.Write(t, runner.RunnersPath, "contract: 1\nrunners:\n  - name: shell\n    bind: ['tests/*.sh']\n    timeout_s: 5\n    batch_timeout_s: 10\n")
	r.Write(t, runner.RunnersDir+"/shell.sh", "#!/usr/bin/env bash\ncase \"$1\" in\ndescribe) printf 'unit: file\\ntimeouts: batch\\n';;\n"+
		"list) printf 'tests/test_live.sh\\tfile\\tl\\n';;\nesac\n")
	if err := os.Chmod(filepath.Join(r.Dir, runner.RunnersDir, "shell.sh"), 0o755); err != nil {
		t.Fatal(err)
	}
	r.Write(t, "tests/test_live.sh", "#!/usr/bin/env bash\n# testmap:kind integration\n# testmap:area invalid/name\n")
	r.Commit(t, "1", "test", "fixture")
	t.Chdir(r.Dir)
	code, out, errs := call("scan", "--apply")
	if code != 3 || out != "" || errs != "INPUT_ERROR:annotations|tests/test_live.sh:2: area contains '/'\n" {
		t.Fatalf("scan: %d %q %q", code, out, errs)
	}
	for _, p := range []string{registry.ScannedPath, registry.ScopedPath} {
		if _, err := os.Stat(filepath.Join(r.Dir, p)); !os.IsNotExist(err) {
			t.Fatalf("%s written by a refused scan: %v", p, err)
		}
	}
	r.Write(t, "tests/test_live.sh", "#!/usr/bin/env bash\n# testmap:kind integration\n# testmap:area board\n")
	if code, out, errs := call("scan", "--apply"); code != 0 || errs != "" || out != "SCAN:0|0|0\nWROTE:"+registry.ScopedPath+"\n" {
		t.Fatalf("recovered scan: %d %q %q", code, out, errs)
	}
	if code, _, errs := call("check"); code != 1 || errs != "" {
		t.Fatalf("check after recovery loads (board is undeclared → DEAD_SCOPE): %d %q", code, errs)
	}
}
