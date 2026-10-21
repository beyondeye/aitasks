package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/axes"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

const axesDecl = `contract: 1
axes:
  - name: matrix
    facets: [locale, direction]
    values:
      en-ltr: {locale: en, direction: ltr}
      ru-ltr: {locale: ru, direction: ltr}
      ar-rtl: {locale: ar, direction: rtl}
    sources:
      locale:
        ru: ["res/values-ru/**"]
        ar: ["res/values-ar/**"]
`

// axisInputs: a matrix runner listing two declared values and one
// undeclared, a runner on an undeclared axis, and annotation claims.
func axisInputs() registry.Inputs {
	return registry.Inputs{
		Annotations: fakeAnns{
			{Path: "app/F.kt", Units: []registry.UnitAnnotation{{}, {Member: "Welcome", Line: 4}}},
			{Path: "tests/test_a.sh", Units: []registry.UnitAnnotation{{Axes: []string{"matrix.locale=ru", "matrix.size=xl", "nope.locale=ru", "matrix.locale=fr"}}}},
		},
		Lister: fakeLister{
			{Runner: "screens", Axis: "matrix", Units: []registry.ListedUnit{
				{ID: registry.MustParseID("app/F.kt#Welcome@en-ltr")},
				{ID: registry.MustParseID("app/F.kt#Welcome@ru-ltr")},
				{ID: registry.MustParseID("app/F.kt#Welcome@zz-new")},
			}},
			{Runner: "other", Axis: "ghost", Units: []registry.ListedUnit{{ID: registry.MustParseID("app/G.kt@v")}}},
			{Runner: "shell", Units: []registry.ListedUnit{{ID: registry.MustParseID("tests/test_a.sh")}}},
		},
	}
}

func axesRepo(t *testing.T, config string) string {
	t.Helper()
	root := repo(t)
	write(t, root, map[string]string{
		axes.Path:                   axesDecl,
		"res/values-ru/strings.xml": "<r/>",
		"app/G.kt":                  "class G\n",
	})
	if config != "" {
		write(t, root, map[string]string{registry.ConfigPath: config})
	}
	withInputs(t, axisInputs())
	return root
}

func TestAxesList(t *testing.T) {
	axesRepo(t, "")
	code, out, errs := call("axes")
	want := "AXIS_DECL:matrix|locale,direction|3|2\n" +
		"AXIS_VALUE:matrix|ar-rtl|locale=ar,direction=rtl|0\n" +
		"AXIS_VALUE:matrix|en-ltr|locale=en,direction=ltr|1\n" +
		"AXIS_VALUE:matrix|ru-ltr|locale=ru,direction=ltr|1\n" +
		"AXIS_DECLS:1\n"
	if code != 0 || errs != "" || out != want {
		t.Fatalf("%d %q %q\nwant %q", code, out, errs, want)
	}
	if c2, out2, _ := call("axes", "--list"); c2 != 0 || out2 != want {
		t.Fatalf("--list: %d %q", c2, out2)
	}
	code, out, _ = call("axes", "--json")
	var got struct {
		Axes []struct {
			Name     string   `json:"name"`
			Facets   []string `json:"facets"`
			Variants int      `json:"variants"`
			Values   []struct {
				Value    string            `json:"value"`
				Facets   map[string]string `json:"facets"`
				Variants int               `json:"variants"`
			} `json:"values"`
		} `json:"axes"`
	}
	if err := json.Unmarshal([]byte(out), &got); code != 0 || err != nil || len(got.Axes) != 1 || got.Axes[0].Variants != 2 || got.Axes[0].Values[2].Facets["locale"] != "ru" {
		t.Fatalf("--json: %d %v %s", code, err, out)
	}
}

func TestAxesCheck(t *testing.T) {
	axesRepo(t, "")
	findings := "DEAD_AXIS_SOURCE:matrix|locale|ar|res/values-ar/**\n" +
		"UNKNOWN_VARIANT:app/F.kt#Welcome@zz-new|matrix|undeclared-value\n" +
		"UNKNOWN_VARIANT:app/G.kt@v|ghost|undeclared-axis\n" +
		"UNKNOWN_VARIANT:tests/test_a.sh|matrix.locale=fr|claim-undeclared-value\n" +
		"UNKNOWN_VARIANT:tests/test_a.sh|matrix.size=xl|claim-undeclared-facet\n" +
		"UNKNOWN_VARIANT:tests/test_a.sh|nope.locale=ru|claim-undeclared-axis\n" +
		"UNCOVERED_VALUE:matrix|ar-rtl\n"
	// Inside the bootstrap window only DEAD_AXIS_SOURCE fails.
	code, out, errs := call("axes", "--check")
	if code != 1 || errs != "" || out != findings+"CHECK:fail|7|1\n" {
		t.Fatalf("%d %q %q", code, out, errs)
	}
	if code, out, _ := call("axes", "--check", "--strict"); code != 1 || !strings.HasSuffix(out, "CHECK:fail|7|1\n") {
		t.Fatalf("--strict in the window: %d %q", code, out)
	}
	// The full check carries the same axis findings, after M2.1's and M2.6's.
	if _, out, _ := call("check"); !strings.Contains(out, findings) || !strings.HasSuffix(out, emptyAdoption+"CHECK:fail|8|1\n") {
		t.Fatalf("check: %q", out)
	}
	code, out, _ = call("axes", "--check", "--json")
	var res registry.CheckResult
	if err := json.Unmarshal([]byte(out), &res); code != 1 || err != nil || res.Failing != 1 || len(res.Findings) != 7 || len(res.Summary) != 0 {
		t.Fatalf("--json: %d %v %s", code, err, out)
	}
}

// Past the bootstrap window --strict fails UNKNOWN_VARIANT and
// UNCOVERED_VALUE too; without --strict they still only report.
func TestAxesCheckStrictPastBootstrap(t *testing.T) {
	axesRepo(t, "contract: 1\n")
	if code, out, _ := call("axes", "--check"); code != 1 || !strings.HasSuffix(out, "CHECK:fail|7|1\n") {
		t.Fatalf("%d %q", code, out)
	}
	if code, out, _ := call("axes", "--check", "--strict"); code != 1 || !strings.HasSuffix(out, "CHECK:fail|7|7\n") {
		t.Fatalf("--strict: %d %q", code, out)
	}
}

func TestAxesCheckPasses(t *testing.T) {
	root := axesRepo(t, "")
	write(t, root, map[string]string{"res/values-ar/strings.xml": "<r/>"})
	withInputs(t, registry.Inputs{
		Annotations: fakeAnns{{Path: "tests/test_a.sh", Units: []registry.UnitAnnotation{{Axes: []string{"matrix.locale=ru"}}}}},
		Lister: fakeLister{{Runner: "screens", Axis: "matrix", Units: []registry.ListedUnit{
			{ID: registry.MustParseID("app/F.kt@en-ltr")}, {ID: registry.MustParseID("app/F.kt@ru-ltr")}, {ID: registry.MustParseID("app/F.kt@ar-rtl")},
		}}, {Runner: "plain", Units: []registry.ListedUnit{{ID: registry.MustParseID("tests/test_a.sh")}, {ID: registry.MustParseID("docs/x.md@v")}}}},
	})
	// docs/x.md@v comes from a runner naming no axis: never judged.
	if code, out, errs := call("axes", "--check", "--strict"); code != 0 || errs != "" || out != "CHECK:pass|0|0\n" {
		t.Fatalf("%d %q %q", code, out, errs)
	}
}

func TestAxesExplain(t *testing.T) {
	axesRepo(t, "")
	for path, want := range map[string]string{
		"res/values-ru/strings.xml": "AXIS:matrix.locale|ru|res/values-ru/**\nAXIS:matrix.direction|-|no-source\n",
		"res/values-ar/gone.xml":    "AXIS:matrix.locale|ar|res/values-ar/**\nAXIS:matrix.direction|-|no-source\n",
		"src/Main.kt":               "AXIS:matrix.locale|-|no-match\nAXIS:matrix.direction|-|no-source\n",
	} {
		if code, out, errs := call("axes", "--explain", path); code != 0 || errs != "" || out != want {
			t.Errorf("%s: %d %q %q", path, code, out, errs)
		}
	}
	code, out, _ := call("axes", "--explain", "src/Main.kt", "--json")
	want := `{"path":"src/Main.kt","hits":[{"axis":"matrix","facet":"locale","value":"-","why":"no-match"},{"axis":"matrix","facet":"direction","value":"-","why":"no-source"}]}` + "\n"
	if code != 0 || out != want {
		t.Fatalf("--json: %d %q", code, out)
	}
}

func TestAxesAbsentAndErrors(t *testing.T) {
	root := repo(t)
	withInputs(t, fakes())
	for _, args := range [][]string{{"axes"}, {"axes", "--explain", "a.kt"}} {
		if code, out, errs := call(args...); code != 2 || out != "" || errs != "AXES_ABSENT:"+axes.Path+"\n" {
			t.Errorf("%v: %d %q %q", args, code, out, errs)
		}
	}
	// --check still runs without axes.yaml (a runner may name an undeclared axis).
	if code, out, _ := call("axes", "--check"); code != 0 || out != "CHECK:pass|0|0\n" {
		t.Fatalf("--check without axes.yaml: %d %q", code, out)
	}
	write(t, root, map[string]string{axes.Path: "contract: 1\naxes: [{name: m}]\n"})
	for _, args := range [][]string{{"axes"}, {"axes", "--check"}, {"axes", "--explain", "a.kt"}, {"check"}} {
		if code, out, errs := call(args...); code != 3 || out != "" || !strings.HasPrefix(errs, "REGISTRY_INVALID:"+axes.Path+"|") {
			t.Errorf("%v: %d %q %q", args, code, out, errs)
		}
	}
	for _, args := range [][]string{
		{"axes", "--list", "--check"}, {"axes", "--check", "--explain", "a"}, {"axes", "--strict"},
		{"axes", "--explain", "/abs"}, {"axes", "--explain", ""}, {"axes", "extra"}, {"axes", "--bogus"},
	} {
		if code, out, errs := call(args...); code != 64 || out != "" || !strings.Contains(errs, "USAGE:") {
			t.Errorf("%v: %d %q %q", args, code, out, errs)
		}
	}
	t.Chdir(t.TempDir())
	if code, _, errs := call("axes"); code != 2 || errs != "TESTMAP_ABSENT:aitestmap/\n" {
		t.Fatalf("no aitestmap/: %d %q", code, errs)
	}
}

// End to end through the real runner repository: a runner script whose
// describe declares `axis:` makes `scan --apply` persist it on the row.
func TestAxesRealRunnerPersistsAxis(t *testing.T) {
	r := runnerRepo(t, twoRows)
	r.Write(t, "app/F.kt", "class F\n")
	r.Write(t, axes.Path, axesDecl)
	r.Write(t, runner.RunnersPath, "contract: 1\nrunners:\n  - name: shell\n    bind: ['tests/*.sh']\n    timeout_s: 5\n    batch_timeout_s: 10\n  - name: screens\n    bind: ['app/**']\n")
	script := "#!/usr/bin/env bash\ncase \"$1\" in\n" +
		"describe) printf 'unit: variant\\naxis: matrix\\ntoken_format: \"{base}@{variant}\"\\n';;\n" +
		"list) printf 'app/F.kt@en-ltr\\tvariant\\ten\\napp/F.kt@ru-ltr\\tvariant\\tru\\n';;\n" +
		"esac\n"
	r.Write(t, runner.RunnersDir+"/screens.sh", script)
	if err := os.Chmod(filepath.Join(r.Dir, runner.RunnersDir, "screens.sh"), 0o755); err != nil {
		t.Fatal(err)
	}
	r.Commit(t, "2", "test", "axis runner")
	if code, out, errs := call("scan", "--apply"); code != 0 || errs != "" || !strings.HasPrefix(out, "SCAN:2|1|2\n") {
		t.Fatalf("scan: %d %q %q", code, out, errs)
	}
	data, _ := os.ReadFile(filepath.Join(r.Dir, registry.ScannedPath))
	if !strings.Contains(string(data), "  - test: app/F.kt\n    axis: matrix\n    variants: [en-ltr, ru-ltr]\n") {
		t.Fatalf("_scanned.yaml:\n%s", data)
	}
	if code, out, _ := call("axes"); code != 0 || !strings.HasPrefix(out, "AXIS_DECL:matrix|locale,direction|3|2\n") {
		t.Fatalf("axes: %d %q", code, out)
	}
	// res/values-ru/** and res/values-ar/** match nothing in this tree.
	if code, out, _ := call("axes", "--check"); code != 1 || !strings.Contains(out, "DEAD_AXIS_SOURCE:matrix|locale|ru|res/values-ru/**\n") || !strings.Contains(out, "UNCOVERED_VALUE:matrix|ar-rtl\n") {
		t.Fatalf("axes --check: %d %q", code, out)
	}
}
