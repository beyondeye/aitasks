package registry

import (
	"errors"
	"reflect"
	"strings"
	"testing"
)

const codemapFixture = `version: 1
areas:
  - name: board
    path: .aitask-scripts/board/
    description: the board TUI
    children:
      - name: board_tests
        path: tests/board/
  - name: scripts
    path: .aitask-scripts/
`

func importRepo(t *testing.T, files map[string]string) string {
	t.Helper()
	root := t.TempDir()
	all := map[string]string{ConfigPath: "contract: 1\n", CodemapPath: codemapFixture}
	for k, v := range files {
		all[k] = v
	}
	writeTree(t, root, all)
	return root
}

func TestImportCodemapFresh(t *testing.T) {
	root := importRepo(t, nil)
	res, err := ImportCodemap(root, false)
	if err != nil {
		t.Fatal(err)
	}
	want := []ImportRow{
		{"board", ".aitask-scripts/board/**", ImportAdded},
		{"board_tests", "tests/board/**", ImportAdded},
		{"scripts", ".aitask-scripts/**", ImportAdded},
	}
	if !reflect.DeepEqual(res.Rows, want) || len(res.Wrote) != 0 {
		t.Fatalf("dry run: %+v", res)
	}
	if res, err = ImportCodemap(root, true); err != nil || !reflect.DeepEqual(res.Wrote, []string{AreasPath}) {
		t.Fatalf("apply: %+v %v", res, err)
	}
	golden(t, "scoped/areas_fresh.yaml", []byte(readFile(t, root, AreasPath)))
	// The written file loads, and a re-import keeps everything.
	if res, err = ImportCodemap(root, true); err != nil || len(res.Wrote) != 0 {
		t.Fatalf("re-import: %+v %v", res, err)
	}
	for _, r := range res.Rows {
		if r.State != ImportKept {
			t.Fatalf("re-import: %+v", res.Rows)
		}
	}
}

// An existing areas.yaml keeps its comments and hand edits: an area of the
// same name with other globs is reported `differs` and never rewritten; a
// hand file's area counts as existing too.
func TestImportCodemapAppendKeepsHandEdits(t *testing.T) {
	root := importRepo(t, map[string]string{
		AreasPath:               "# hand-curated areas\ncontract: 1\nareas:\n  # the board, narrowed by hand\n  board: {paths: [\".aitask-scripts/board/app/**\"]}\n",
		RegistryDir + "/h.yaml": "contract: 1\nareas:\n  scripts: {paths: [\".aitask-scripts/**\"]}\n",
	})
	res, err := ImportCodemap(root, true)
	if err != nil {
		t.Fatal(err)
	}
	want := []ImportRow{
		{"board", ".aitask-scripts/board/**", ImportDiffers},
		{"board_tests", "tests/board/**", ImportAdded},
		{"scripts", ".aitask-scripts/**", ImportKept},
	}
	if !reflect.DeepEqual(res.Rows, want) || !reflect.DeepEqual(res.Wrote, []string{AreasPath}) {
		t.Fatalf("%+v", res)
	}
	golden(t, "scoped/areas_appended.yaml", []byte(readFile(t, root, AreasPath)))
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	if a := ScopedOf(reg).Areas["board"]; !reflect.DeepEqual(a.Globs, []string{".aitask-scripts/board/app/**"}) {
		t.Fatalf("hand edit rewritten: %+v", a)
	}
}

func TestImportCodemapRefusals(t *testing.T) {
	root := importRepo(t, nil)
	writeTree(t, root, map[string]string{})
	for _, tc := range []struct{ body, want string }{
		{"version: 2\nareas: []\n", "version 2 is not 1"},
		{"version: 1\nareas: [{name: a, path: x/}, {name: a, path: y/}]\n", "duplicate area a"},
		{"version: 1\nareas: [{name: a, path: x/, children: [{name: a, path: x/y/}]}]\n", "duplicate area a"},
		{"version: 1\nareas: [{name: \"a b\", path: x/}]\n", "whitespace"},
		{"version: 1\nareas: [{name: a, path: ../x/}]\n", "path"},
		{"version: 1\nareas: [{name: a, path: \"\"}]\n", "empty path"},
		{"version: [\n", "code_areas"},
	} {
		writeTree(t, root, map[string]string{CodemapPath: tc.body})
		_, err := ImportCodemap(root, true)
		var ie *InputError
		if !errors.As(err, &ie) || ie.Input != InputCodemap || !strings.Contains(ie.Error(), tc.want) {
			t.Errorf("%q: err %v, want INPUT_ERROR:code_areas containing %q", tc.body, err, tc.want)
		}
	}
	empty := t.TempDir()
	writeTree(t, empty, map[string]string{ConfigPath: "contract: 1\n"})
	if _, err := ImportCodemap(empty, false); !errors.Is(err, ErrCodemapAbsent) {
		t.Fatalf("absent: %v", err)
	}
	if _, err := ImportCodemap(t.TempDir(), false); !errors.Is(err, ErrAbsent) {
		t.Fatalf("no aitestmap/: %v", err)
	}
}

func TestListAreas(t *testing.T) {
	root := importRepo(t, map[string]string{
		AreasPath:               "contract: 1\nareas:\n  board: {paths: [\"src/board/**\", \"src/x.py\"]}\n  empty: {paths: [\"none/**\"]}\n",
		RegistryDir + "/h.yaml": "contract: 1\nscopes: [{test: tests/t.py, kind: e2e, areas: [board]}, {test: tests/u.py, kind: e2e, areas: [board, empty]}]\n",
		"src/board/a.py":        "", "src/board/b/c.py": "", "src/x.py": "",
	})
	got, err := ListAreas(root)
	if err != nil {
		t.Fatal(err)
	}
	want := []AreaSummary{{"board", []string{"src/board/**", "src/x.py"}, 3, 2}, {"empty", []string{"none/**"}, 0, 1}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v", got)
	}
}
