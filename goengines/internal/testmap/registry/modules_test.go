package registry

import (
	"errors"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"
)

// modulesRegistry loads a registry with the given files.
func modulesRegistry(t *testing.T, files map[string]string) (*Registry, error) {
	t.Helper()
	root := t.TempDir()
	files[ConfigPath] = "contract: 1\n"
	writeTree(t, root, files)
	return Load(root)
}

// The generated table round-trips: load → render is byte-identical, for a
// golden carrying every provider, an agent row and module deps.
func TestModulesLoadRenderGolden(t *testing.T) {
	want, err := os.ReadFile(filepath.Join("testdata", "modules", "_modules.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	reg, err := modulesRegistry(t, map[string]string{ModulesPath: string(want)})
	if err != nil {
		t.Fatal(err)
	}
	m := ModulesOf(reg)
	if !m.Committed() || !m.Declared() || len(m.Doc().Modules) != 5 {
		t.Fatalf("loaded %+v", m.Doc())
	}
	got, err := RenderModules(m.Doc())
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(want) {
		t.Fatalf("round trip\n got:\n%s\nwant:\n%s", got, want)
	}
}

func TestModulesLoadRefusals(t *testing.T) {
	const head = "contract: 1\nmodules:\n"
	gen := map[string]string{
		"unknown field":         head + "  - {name: codemap:a, provider: codemap, root: a, colour: red}\n",
		"bad provider":          head + "  - {name: codemap:a, provider: maven, root: a}\n",
		"hand provider in file": head + "  - {name: x, provider: hand, paths: [\"x/**\"]}\n",
		"name not generated":    head + "  - {name: codemap:b, provider: codemap, root: a}\n",
		"subtree at root":       head + "  - {name: codemap:., provider: codemap, root: .}\n",
		"unnameable root":       head + "  - {name: gradle:api, provider: gradle, root: \"odd:dir\", gradle: \":api\"}\n",
		"glob root":             head + "  - {name: codemap:a, provider: codemap, root: \"a*\"}\n",
		"gradle without path":   head + "  - {name: gradle:api, provider: gradle, root: api}\n",
		"gradle root project":   head + "  - {name: \"gradle:\", provider: gradle, root: api, gradle: \":\"}\n",
		"agent without by":      head + "  - {name: billing, provider: agent, paths: [\"b/**\"]}\n",
		"agent by human":        head + "  - {name: billing, provider: agent, by: \"human:x@y\", paths: [\"b/**\"]}\n",
		"agent without paths":   head + "  - {name: billing, provider: agent, by: \"agent:x\"}\n",
		"agent with root":       head + "  - {name: billing, provider: agent, by: \"agent:x\", paths: [\"b/**\"], root: b}\n",
		"agent reserved prefix": head + "  - {name: \"codemap:billing\", provider: agent, by: \"agent:x\", paths: [\"b/**\"]}\n",
		"duplicate":             head + "  - {name: codemap:a, provider: codemap, root: a}\n  - {name: codemap:a, provider: codemap, root: a}\n",
		"dep unknown module":    head + "  - {name: codemap:a, provider: codemap, root: a, deps: [{module: codemap:b, evidence: {from: a/x, to: b/y}}]}\n",
		"nested row":            head + "  - {name: codemap:a, provider: codemap, root: a, submodules: [{name: x}]}\n",
	}
	for name, body := range gen {
		t.Run("generated/"+name, func(t *testing.T) {
			_, err := modulesRegistry(t, map[string]string{ModulesPath: body})
			var inv *InvalidError
			if !errors.As(err, &inv) || inv.Path != ModulesPath {
				t.Fatalf("err %v, want REGISTRY_INVALID on %s", err, ModulesPath)
			}
		})
	}
	hand := map[string]string{
		"reserved prefix": "modules:\n  \"gradle:api\": {paths: [\"api/**\"]}\n",
		"submodules key":  "modules:\n  api: {paths: [\"api/**\"], submodules: {public: {paths: [\"api/public/**\"]}}}\n",
		"children key":    "modules:\n  api: {paths: [\"api/**\"], children: [public]}\n",
		"other key":       "modules:\n  api: {paths: [\"api/**\"], owner: team-a}\n",
		"glob in name":    "modules:\n  \"api*\": {paths: [\"api/**\"]}\n",
		"slash in name":   "modules:\n  \"a/b\": {paths: [\"api/**\"]}\n",
		"no paths":        "modules:\n  api: {}\n",
		"not a mapping":   "modules: [api]\n",
		"bad glob":        "modules:\n  api: {paths: [\"api/[\"]}\n",
	}
	for name, body := range hand {
		t.Run("hand/"+name, func(t *testing.T) {
			_, err := modulesRegistry(t, map[string]string{RegistryDir + "/hand.yaml": "contract: 1\n" + body})
			var inv *InvalidError
			if !errors.As(err, &inv) || inv.Path != RegistryDir+"/hand.yaml" {
				t.Fatalf("err %v, want REGISTRY_INVALID on the hand file", err)
			}
		})
	}
}

func TestNamesAndRoots(t *testing.T) {
	for dir, want := range map[string]string{"": ".", ".": ".", "a/b": "a:b", "a.b": "a.b", "a-b_c": "a-b_c"} {
		if got, ok := NativeID(dir); !ok || got != want {
			t.Errorf("NativeID(%q) = %q %v, want %q", dir, got, ok, want)
		}
	}
	for _, dir := range []string{"a:b", "x/a:b", "a b", "a*", "a#b", "a/../b", "a//b"} {
		if _, ok := NativeID(dir); ok {
			t.Errorf("NativeID(%q) accepted", dir)
		}
	}
	if err := ValidRoot(ProviderGradle, "odd:dir"); err == nil {
		t.Error("ValidRoot accepted a ':' directory for a valid Gradle path's projectDir")
	}
	if ValidRoot(ProviderCodemap, ".") == nil || ValidRoot(ProviderGo, ".") != nil {
		t.Error("only a package provider may sit at the repository root")
	}
	if n, err := GeneratedName(ProviderGradle, "services/payments/api", ":services:payments:api"); err != nil || n != "gradle:services:payments:api" {
		t.Errorf("gradle name %q %v", n, err)
	}
	if n, err := GeneratedName(ProviderPython, "tools/lib", ""); err != nil || n != "py:tools:lib" {
		t.Errorf("python name %q %v", n, err)
	}
}

// ownership fixture: every provider over one tree.
func ownershipModules(t *testing.T, hand string) *Modules {
	t.Helper()
	files := map[string]string{ModulesPath: `contract: 1
modules:
  - {name: billing, provider: agent, by: "agent:x", paths: ["billing/**"]}
  - {name: codemap:services, provider: codemap, root: services}
  - {name: codemap:services:api, provider: codemap, root: services/api}
  - {name: gradle:api, provider: gradle, root: services/api, gradle: ":api"}
  - {name: gradle:apx, provider: gradle, root: services/api, gradle: ":apx"}
  - {name: gradle:app, provider: gradle, root: app, gradle: ":app"}
  - {name: go:., provider: go, root: .}
  - {name: go:tool, provider: go, root: tool}
  - {name: py:tool, provider: python, root: tool}
`}
	if hand != "" {
		files[RegistryDir+"/hand.yaml"] = "contract: 1\n" + hand
	}
	reg, err := modulesRegistry(t, files)
	if err != nil {
		t.Fatal(err)
	}
	return ModulesOf(reg)
}

func TestModuleOwnerOf(t *testing.T) {
	m := ownershipModules(t, "modules:\n  api: {paths: [\"services/api/public/**\"]}\n")
	for p, want := range map[string]string{
		"services/api/public/A.kt":   "api",                  // hand wins
		"services/api/internal/B.kt": "codemap:services:api", // codemap over Gradle; deepest root
		"services/x.md":              "codemap:services",
		"app/src/A.kt":               "gradle:app",
		"billing/x.sh":               "billing", // agent
		"main.go":                    "go:.",    // root package, own files only
		"README.md":                  "",        // never claimed by go:.
		"tool/parse.go":              "go:tool",
		"tool/parse.py":              "py:tool",
		"tool/data/x.go":             "", // a subpackage directory is not tool's
		"elsewhere/x":                "",
	} {
		if got, err := m.OwnerOf(p); err != nil || got != want {
			t.Errorf("OwnerOf(%s) = %q %v, want %q", p, got, err, want)
		}
	}
}

func TestModulesResolve(t *testing.T) {
	files := []string{"services/api/public/A.kt", "services/api/internal/B.kt", "services/x.md", "app/A.kt", "billing/x.sh", "main.go", "README.md", "tool/parse.go"}
	m := ownershipModules(t, "modules:\n  api: {paths: [\"services/api/public/**\"]}\n  billing: {paths: [\"billing/**\", \"main.go\"]}\n")
	res, err := m.Resolve(files)
	if err != nil {
		t.Fatal(err)
	}
	var got []string
	for _, c := range res.Conflicts {
		got = append(got, strings.Join(c.Fields(), "|"))
	}
	want := []string{
		"api@hand|codemap:services:api@codemap|1|services/api/public/A.kt",
		"api@hand|gradle:api@gradle|1|services/api/public/A.kt",
		"billing@hand|billing@agent|1|billing/x.sh", // the hand module takes the agent row's name
		"billing@hand|go:.@go|1|main.go",
		// codemap:services:api and gradle:api share a root: identical claims.
	}
	if !slices.Equal(got, want) {
		t.Fatalf("conflicts\n got %v\nwant %v", got, want)
	}
	var effective []string
	for _, e := range res.Modules {
		effective = append(effective, e.Name+"="+strings.Join(e.Members, ","))
	}
	wantEff := []string{
		"api=services/api/public/A.kt",
		"billing=billing/x.sh,main.go",
		"codemap:services=services/x.md",
		"codemap:services:api=services/api/internal/B.kt",
		"go:tool=tool/parse.go",
		"gradle:app=app/A.kt",
	}
	if !slices.Equal(effective, wantEff) {
		t.Fatalf("effective\n got %v\nwant %v", effective, wantEff)
	}
	if !slices.Equal(res.Unmapped, []string{"README.md"}) {
		t.Fatalf("unmapped %v", res.Unmapped)
	}
	for _, e := range res.Modules {
		if e.Name == "billing" && (e.Provider != ProviderHand || !slices.Equal(e.Evidence, []string{"file:" + RegistryDir + "/hand.yaml"})) {
			t.Fatalf("hand module %+v", e)
		}
	}
}

// Identical claims refine nothing: a hand module equal to a codemap module's
// whole set is no conflict.
func TestResolveIdenticalSetsNotReported(t *testing.T) {
	reg, err := modulesRegistry(t, map[string]string{
		ModulesPath:                "contract: 1\nmodules:\n  - {name: codemap:lib, provider: codemap, root: lib}\n",
		RegistryDir + "/hand.yaml": "contract: 1\nmodules:\n  lib: {paths: [\"lib/**\"]}\n",
	})
	if err != nil {
		t.Fatal(err)
	}
	res, err := ModulesOf(reg).Resolve([]string{"lib/a.sh", "lib/b.sh"})
	if err != nil || len(res.Conflicts) != 0 || len(res.Modules) != 1 || res.Modules[0].Name != "lib" {
		t.Fatalf("%+v %v", res, err)
	}
}

// Two hand modules on one path is an authoring error, whatever kind of file
// the path is; across hand files the same name is one module (globs unioned).
func TestHandOverlapIsInvalid(t *testing.T) {
	reg, err := modulesRegistry(t, map[string]string{
		RegistryDir + "/a.yaml": "contract: 1\nmodules:\n  conf: {paths: [\"conf/**\"]}\n  web: {paths: [\"web/**\"]}\n",
		RegistryDir + "/b.yaml": "contract: 1\nmodules:\n  app: {paths: [\"conf/app.json\"]}\n  web: {paths: [\"site/**\"]}\n",
	})
	if err != nil {
		t.Fatal(err)
	}
	m := ModulesOf(reg)
	_, err = m.Resolve([]string{"conf/app.json", "web/x.html"})
	var inv *InvalidError
	if !errors.As(err, &inv) || !strings.Contains(inv.Reason, "app and conf both claim conf/app.json") {
		t.Fatalf("resolve: %v", err)
	}
	if _, err := m.OwnerOf("conf/app.json"); !errors.As(err, &inv) {
		t.Fatalf("OwnerOf: %v", err)
	}
	if got, err := m.OwnerOf("site/i.html"); err != nil || got != "web" {
		t.Fatalf("unioned globs: %q %v", got, err)
	}
	for _, h := range m.Hand() {
		if h.Name == "web" && !slices.Equal(h.Files, []string{RegistryDir + "/a.yaml", RegistryDir + "/b.yaml"}) {
			t.Fatalf("web files %v", h.Files)
		}
	}
}

// Doc is a snapshot: editing it never reaches the loaded table or its cached
// ownership; nor does editing a document after WithGenerated took it.
func TestModulesDocIsADeepCopy(t *testing.T) {
	m := ownershipModules(t, "")
	if o, _ := m.OwnerOf("billing/a.sh"); o != "billing" {
		t.Fatalf("owner %q", o)
	}
	doc := m.Doc()
	for i := range doc.Modules {
		if doc.Modules[i].Name == "billing" {
			doc.Modules[i].Paths[0] = "elsewhere/**"
		}
	}
	if o, _ := m.OwnerOf("billing/a.sh"); o != "billing" {
		t.Fatalf("editing Doc() changed the table: owner %q", o)
	}
	live := m.WithGenerated(doc)
	doc.Modules[0].Paths[0] = "billing/**"
	if o, _ := live.OwnerOf("elsewhere/x"); o != "billing" {
		t.Fatalf("editing a doc after WithGenerated changed the view: owner %q", o)
	}
}
