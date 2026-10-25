package registry

import (
	"context"
	"errors"
	"slices"
	"testing"
)

// withInference installs a fake live module inference returning doc over
// files, counting its calls.
func withInference(t *testing.T, doc ModulesDoc, files []string) *int {
	t.Helper()
	n := new(int)
	prev := RegisterModuleInference(func(context.Context, string, *Registry) (*LiveModules, error) {
		*n++
		return &LiveModules{Doc: doc, Files: files}, nil
	})
	t.Cleanup(func() { RegisterModuleInference(prev) })
	return n
}

func modulesCheckRoot(t *testing.T, files map[string]string) string {
	t.Helper()
	root := t.TempDir()
	files[ConfigPath] = "contract: 1\nbootstrap_until: 2099-01-01\n"
	writeTree(t, root, files)
	return root
}

var noInputs = Inputs{Annotations: fakeAnns{}, Lister: fakeLister{}}

func liveDoc(rows ...ModuleRow) ModulesDoc { return ModulesDoc{Contract: 1, Modules: rows} }

var lib = ModuleRow{Name: "codemap:lib", Provider: ProviderCodemap, Root: "lib", Evidence: []string{"entry:lib"}}

func TestModuleRulesNeedADeclaredTable(t *testing.T) {
	calls := withInference(t, liveDoc(lib), []string{"lib/a.sh"})
	root := modulesCheckRoot(t, map[string]string{})
	res := runCheck(t, root, noInputs, true)
	if *calls != 0 || len(only(t, res, RuleModulesDrift))+len(only(t, res, RuleModuleConflict)) != 0 {
		t.Fatalf("undeclared table judged: %d calls, %+v", *calls, res.Findings)
	}
}

// [modules_drift_negative_control] A committed table equal to the live
// inference is no drift; one changed row is; the finding fails only under
// --strict past bootstrap, like SCAN_DRIFT. The inference runs once per check.
func TestModulesDriftNegativeControl(t *testing.T) {
	committed, err := RenderModules(liveDoc(lib))
	if err != nil {
		t.Fatal(err)
	}
	root := modulesCheckRoot(t, map[string]string{ModulesPath: string(committed)})
	calls := withInference(t, liveDoc(lib), []string{"lib/a.sh"})
	if res := runCheck(t, root, noInputs, true); len(only(t, res, RuleModulesDrift)) != 0 || *calls != 1 {
		t.Fatalf("fresh table: %v, %d calls", res.Findings, *calls)
	}
	changed := lib
	changed.Evidence = []string{"entry:library"}
	withInference(t, liveDoc(changed), []string{"lib/a.sh"})
	res := runCheck(t, root, noInputs, false)
	if got := only(t, res, RuleModulesDrift); !slices.Equal(got, []string{"MODULES_DRIFT:" + ModulesPath}) || res.Failing != 0 {
		t.Fatalf("drifted table: %v failing %d", got, res.Failing)
	}
	writeTree(t, root, map[string]string{ConfigPath: "contract: 1\nbootstrap_until: 2020-01-01\n"})
	if res := runCheck(t, root, noInputs, true); res.Failing != 1 {
		t.Fatalf("strict past bootstrap: failing %d", res.Failing)
	}
	// A hand-only table with nothing generated and no file is not drifted.
	root = modulesCheckRoot(t, map[string]string{RegistryDir + "/hand.yaml": "contract: 1\nmodules:\n  lib: {paths: [\"lib/**\"]}\n"})
	withInference(t, liveDoc(), []string{"lib/a.sh"})
	if res := runCheck(t, root, noInputs, true); len(only(t, res, RuleModulesDrift)) != 0 {
		t.Fatalf("hand-only: %v", res.Findings)
	}
}

func TestModuleConflictIsInfo(t *testing.T) {
	root := modulesCheckRoot(t, map[string]string{RegistryDir + "/hand.yaml": "contract: 1\nmodules:\n  public: {paths: [\"lib/public/**\"]}\n"})
	withInference(t, liveDoc(lib), []string{"lib/a.sh", "lib/public/p.sh"})
	// --strict before bootstrap_until: the absent committed file's
	// MODULES_DRIFT is reported but nothing fails; the conflict never does.
	res := runCheck(t, root, noInputs, true)
	if got := only(t, res, RuleModuleConflict); !slices.Equal(got, []string{"MODULE_CONFLICT:public@hand|codemap:lib@codemap|1|lib/public/p.sh"}) || res.Failing != 0 {
		t.Fatalf("conflict: %v failing %d", got, res.Failing)
	}
}

func TestModuleRulesFailClosed(t *testing.T) {
	root := modulesCheckRoot(t, map[string]string{ModulesPath: "contract: 1\n"})
	prev := RegisterModuleInference(nil)
	t.Cleanup(func() { RegisterModuleInference(prev) })
	_, err := Check(context.Background(), root, noInputs, CheckOptions{})
	var ce *CheckError
	if !errors.As(err, &ce) || ce.Rule != RuleModulesDrift {
		t.Fatalf("no inference: %v", err)
	}
	root = modulesCheckRoot(t, map[string]string{RegistryDir + "/hand.yaml": "contract: 1\nmodules:\n  a: {paths: [\"x/*.json\"]}\n  b: {paths: [\"x/app.json\"]}\n"})
	withInference(t, liveDoc(), []string{"x/app.json"})
	_, err = Check(context.Background(), root, noInputs, CheckOptions{})
	var inv *InvalidError
	if !errors.As(err, &inv) {
		t.Fatalf("hand overlap: %v, want REGISTRY_INVALID", err)
	}
}
