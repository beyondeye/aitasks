package classify

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

type fakeAnns []registry.FileAnnotations

func (f fakeAnns) Annotations(context.Context, string) ([]registry.FileAnnotations, error) {
	return f, nil
}

type fakeLister []registry.Listing

func (f fakeLister) List(context.Context, string) ([]registry.Listing, error) { return f, nil }

func listing(ids ...string) fakeLister {
	l := registry.Listing{Runner: "r"}
	for _, s := range ids {
		l.Units = append(l.Units, registry.ListedUnit{ID: registry.MustParseID(s), Kind: "file", Lowering: s})
	}
	return fakeLister{l}
}

func classifyRepo(t *testing.T) *fixture.Repo {
	t.Helper()
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	r := fixture.New(t)
	files := map[string]string{
		registry.ConfigPath:                     "contract: 1\nunit_covers_max: 2\n",
		registry.AreasPath:                      "contract: 1\nareas:\n  src: {paths: [\"src/**\"]}\n",
		"tests/test_board_live.py":              "import subprocess\nsubprocess.run(['tmux', 'new-session'])\n",
		"tests/test_net.sh":                     "#!/usr/bin/env bash\ncurl -s https://example.invalid\n",
		"app/src/androidTest/kotlin/FooTest.kt": "class FooTest\n",
		"tests/test_emu.sh":                     "#!/usr/bin/env bash\nadb shell true\n",
		"tests/test_needs.sh":                   "#!/usr/bin/env bash\n# testmap:needs repo-git-index\n",
		"tests/test_fan.sh": "#!/usr/bin/env bash\n. \"$PROJECT_DIR/src/a.sh\"\n. \"$PROJECT_DIR/src/b.sh\"\n" +
			". \"$PROJECT_DIR/tests/lib/h.sh\"\n",
		"tests/lib/h.sh": "#!/usr/bin/env bash\n. \"$PROJECT_DIR/src/c.sh\"\n",
		"src/a.sh":       "", "src/b.sh": "", "src/c.sh": "",
		"tests/test_plain.sh": "#!/usr/bin/env bash\n. \"$PROJECT_DIR/src/a.sh\"\n",
		"tests/test_live2.py": "print('already integration')\n",
	}
	for p, c := range files {
		r.Write(t, p, c)
	}
	r.Commit(t, "1", "test", "fixtures")
	t.Chdir(r.Dir)
	return r
}

func classifyInputs() registry.Inputs {
	return registry.Inputs{
		Annotations: fakeAnns{
			{Path: "tests/test_needs.sh", Units: []registry.UnitAnnotation{{Needs: []string{"repo-git-index"}}}},
			{Path: "tests/test_live2.py", Units: []registry.UnitAnnotation{{Kind: "integration", Areas: []string{"src"}, ScopedLine: 1}}},
		},
		Lister: listing("tests/test_board_live.py", "tests/test_net.sh", "app/src/androidTest/kotlin/FooTest.kt",
			"tests/test_emu.sh", "tests/test_needs.sh", "tests/test_fan.sh", "tests/test_plain.sh", "tests/test_live2.py"),
	}
}

func TestSuggestShippedSignals(t *testing.T) {
	r := classifyRepo(t)
	got, err := Suggest(context.Background(), r.Dir, classifyInputs(), nil)
	if err != nil {
		t.Fatal(err)
	}
	want := []Suggestion{
		{Test: "app/src/androidTest/kotlin/FooTest.kt", Kind: "device", Reason: "convention:**/androidTest/**", Current: "unit"},
		{Test: "tests/test_board_live.py", Kind: "integration", Reason: "convention:**/*_live.py;resource:tmux", Current: "unit"},
		{Test: "tests/test_emu.sh", Kind: "device", Reason: "resource:emulator", Current: "unit"},
		{Test: "tests/test_fan.sh", Kind: "integration", Reason: "fanout:3;areas:src", Current: "unit"},
		{Test: "tests/test_needs.sh", Kind: "integration", Reason: "resource:needs:repo-git-index", Current: "unit"},
		{Test: "tests/test_net.sh", Kind: "integration", Reason: "resource:network", Current: "unit"},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got\n%+v\nwant\n%+v", got, want)
	}
	// test_plain.sh (no signal; 1 subject <= unit_covers_max) and
	// test_live2.py (already integration: the convention signal does not
	// outrank it) are absent.
}

// fanout counts subjects strictly above unit_covers_max, through helpers.
func TestSubjectsAndFanoutBoundary(t *testing.T) {
	r := classifyRepo(t)
	r.Write(t, registry.ConfigPath, "contract: 1\nunit_covers_max: 3\n")
	got, err := Suggest(context.Background(), r.Dir, classifyInputs(), []string{"tests/test_fan.sh"})
	if err != nil || len(got) != 0 {
		t.Fatalf("3 subjects at unit_covers_max 3: %+v %v", got, err)
	}
}

func TestRegisteredSignalIsConsulted(t *testing.T) {
	r := classifyRepo(t)
	RegisterSignal("test-p95", func(in Input) ([]Signal, error) {
		if in.Test == "tests/test_plain.sh" {
			return []Signal{{Kind: registry.KindE2E, Token: "p95:120s"}}, nil
		}
		return nil, nil
	})
	t.Cleanup(func() {
		signalsMu.Lock()
		signals = signals[:len(signals)-1]
		signalsMu.Unlock()
	})
	got, err := Suggest(context.Background(), r.Dir, classifyInputs(), []string{"tests/test_plain.sh", "tests/test_live2.py"})
	if err != nil {
		t.Fatal(err)
	}
	want := []Suggestion{{Test: "tests/test_plain.sh", Kind: "e2e", Reason: "p95:120s;areas:src", Current: "unit"}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v", got)
	}
}

func TestSuggestRefusals(t *testing.T) {
	r := classifyRepo(t)
	for _, tc := range []struct{ arg, want string }{
		{"tests/missing.sh", "INPUT_ERROR:tests|tests/missing.sh: missing"},
		{"../x.sh", "INPUT_ERROR:tests|../x.sh"},
	} {
		_, err := Suggest(context.Background(), r.Dir, classifyInputs(), []string{tc.arg})
		var ie *registry.InputError
		if !errors.As(err, &ie) {
			t.Fatalf("%s: %v", tc.arg, err)
		}
		if l, _ := ie.Line(); !strings.HasPrefix(l, tc.want) {
			t.Fatalf("%s: %q", tc.arg, l)
		}
	}
	bad := classifyInputs()
	bad.Annotations = fakeAnns{{Path: "tests/test_net.sh", Units: []registry.UnitAnnotation{{Kind: "nope", ScopedLine: 1}}}}
	if _, err := Suggest(context.Background(), r.Dir, bad, nil); err == nil || !strings.Contains(err.Error(), `unknown kind "nope"`) {
		t.Fatalf("a refused annotation refuses classify: %v", err)
	}
	if _, err := Suggest(context.Background(), r.Dir, registry.Inputs{}, nil); err == nil {
		t.Fatal("no inputs: classify must refuse")
	}
}

// Eligibility is one rule for default and named targets.
func TestSuggestEligibility(t *testing.T) {
	r := classifyRepo(t)
	r.Write(t, registry.ConfigPath, "contract: 1\nunit_covers_max: 2\nexclude: [\"tests/excluded/**\"]\n")
	r.Write(t, "tests/excluded/test_emu.sh", "#!/usr/bin/env bash\nadb shell true\n")
	r.Write(t, "tests/lib/tmux_helper.sh", "#!/usr/bin/env bash\n# testmap:reads tests/*.sh\ntmux ls\n")
	r.Write(t, "tests/test_var.kt", "class V { fun t() { emulator() } }\n")
	in := classifyInputs()
	in.Annotations = append(in.Annotations.(fakeAnns), registry.FileAnnotations{Path: "tests/lib/tmux_helper.sh",
		Units: []registry.UnitAnnotation{{Reads: []string{"tests/*.sh"}, ReadsLine: 2}}})
	l := in.Lister.(fakeLister)
	l[0].Units = append(l[0].Units,
		registry.ListedUnit{ID: registry.MustParseID("tests/test_emu.sh@ltr"), Kind: "variant", Lowering: "e"},
		registry.ListedUnit{ID: registry.MustParseID("tests/test_var.kt#T@rtl"), Kind: "variant", Lowering: "v"})
	// Default universe: the excluded file and the helper are never targets,
	// and the two variant-bearing files (own variant; member variant) are
	// never suggested a broad kind, whatever their signals say.
	got, err := Suggest(context.Background(), r.Dir, in, nil)
	if err != nil {
		t.Fatal(err)
	}
	for _, s := range got {
		switch s.Test {
		case "tests/test_emu.sh", "tests/test_var.kt", "tests/excluded/test_emu.sh", "tests/lib/tmux_helper.sh":
			t.Fatalf("ineligible target suggested: %+v", s)
		}
	}
	// Named: variant-bearing files are skipped the same way ...
	if got, err := Suggest(context.Background(), r.Dir, in, []string{"tests/test_emu.sh", "tests/test_var.kt"}); err != nil || len(got) != 0 {
		t.Fatalf("named variant-bearing: %+v %v", got, err)
	}
	// ... and a named path that is not a test is refused.
	for arg, want := range map[string]string{
		"tests/excluded/test_emu.sh": "INPUT_ERROR:tests|tests/excluded/test_emu.sh: excluded",
		"tests/lib/tmux_helper.sh":   "INPUT_ERROR:tests|tests/lib/tmux_helper.sh: a testmap:reads helper, not a test",
	} {
		_, err := Suggest(context.Background(), r.Dir, in, []string{arg})
		var ie *registry.InputError
		if !errors.As(err, &ie) {
			t.Fatalf("%s: %v", arg, err)
		}
		if l, _ := ie.Line(); l != want {
			t.Fatalf("%s: %q", arg, l)
		}
	}
}

// A target reached through a symbolic link on any component is never read:
// a named one is refused, a listed one skipped (the annotation source's
// universe), and the file outside the repository is never classified.
func TestSuggestNeverFollowsLinks(t *testing.T) {
	r := classifyRepo(t)
	outside := t.TempDir()
	if err := os.WriteFile(filepath.Join(outside, "test_escape.sh"), []byte("#!/usr/bin/env bash\nadb shell true\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, filepath.Join(r.Dir, "linked")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("test_emu.sh", filepath.Join(r.Dir, "tests", "test_leaf_link.sh")); err != nil {
		t.Fatal(err)
	}
	for _, arg := range []string{"linked/test_escape.sh", "tests/test_leaf_link.sh"} {
		_, err := Suggest(context.Background(), r.Dir, classifyInputs(), []string{arg})
		var ie *registry.InputError
		if !errors.As(err, &ie) {
			t.Fatalf("%s: %v", arg, err)
		}
		if l, _ := ie.Line(); l != "INPUT_ERROR:tests|"+arg+": not a regular file reached without a symbolic link" {
			t.Fatalf("%s: %q", arg, l)
		}
	}
	in := classifyInputs()
	l := in.Lister.(fakeLister)
	l[0].Units = append(l[0].Units, registry.ListedUnit{ID: registry.MustParseID("linked/test_escape.sh"), Kind: "file", Lowering: "x"})
	got, err := Suggest(context.Background(), r.Dir, in, nil)
	if err != nil {
		t.Fatal(err)
	}
	for _, s := range got {
		if s.Test == "linked/test_escape.sh" {
			t.Fatalf("read through a link: %+v", s)
		}
	}
}

// A file-kind proposal that would contradict a member's own kind is never
// made: a file has one broad kind, and BuildScoped refuses a member kind
// that differs from it.
func TestSuggestRespectsMemberKinds(t *testing.T) {
	r := classifyRepo(t)
	for p, c := range map[string]string{
		"tests/test_restate.sh": "#!/usr/bin/env bash\nadb shell true\n",
		"tests/test_unitm.sh":   "#!/usr/bin/env bash\nadb shell true\n",
		"tests/test_devm.sh":    "#!/usr/bin/env bash\nadb shell true\n",
	} {
		r.Write(t, p, c)
	}
	in := classifyInputs()
	in.Annotations = append(in.Annotations.(fakeAnns),
		// integration file whose member restates integration: device would orphan it
		registry.FileAnnotations{Path: "tests/test_restate.sh", Units: []registry.UnitAnnotation{
			{Kind: "integration", Areas: []string{"src"}, ScopedLine: 2},
			{Member: "M", Line: 4, Kind: "integration", ScopedLine: 5}}},
		// unit file with an explicitly unit member: any broad file kind refuses it
		registry.FileAnnotations{Path: "tests/test_unitm.sh", Units: []registry.UnitAnnotation{
			{}, {Member: "U", Line: 3, Kind: "unit", ScopedLine: 4}}},
		// unit file whose only member is already device: device is compatible
		registry.FileAnnotations{Path: "tests/test_devm.sh", Units: []registry.UnitAnnotation{
			{}, {Member: "D", Line: 3, Kind: "device", Areas: []string{"src"}, ScopedLine: 4}}},
	)
	got, err := Suggest(context.Background(), r.Dir, in, []string{"tests/test_restate.sh", "tests/test_unitm.sh", "tests/test_devm.sh"})
	if err != nil {
		t.Fatal(err)
	}
	want := []Suggestion{{Test: "tests/test_devm.sh", Kind: "device", Reason: "resource:emulator", Current: "unit"}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v", got)
	}
}
