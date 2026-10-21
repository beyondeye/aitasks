package runner

import (
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"slices"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// The static runners.yaml rules, including every subsumption shape that
// would otherwise let `run --all` drop tests behind a suite that never runs.
func TestConfigRefusals(t *testing.T) {
	for name, tc := range map[string]struct{ in, want string }{
		"unknown top key":   {"runnerz: []\n", `unknown key "runnerz"`},
		"unknown entry key": {"runners:\n  - name: a\n    binds: [x]\n", `unknown key "binds"`},
		"bad name":          {"runners:\n  - name: 'a b'\n", "invalid name"},
		"duplicate name":    {"runners:\n  - name: a\n  - name: a\n", "declared twice"},
		"builtin+script":    {"runners:\n  - name: a\n    builtin: x\n    script: s.sh\n", "exclusive"},
		"command alone":     {"runners:\n  - name: a\n    command: pytest\n", "needs builtin:"},
		"bad bind":          {"runners:\n  - name: a\n    bind: ['a/[']\n", "invalid bind glob"},
		"bad cwd":           {"runners:\n  - name: a\n    cwd: ../up\n", "cwd"},
		"self subsumed":     {"runners:\n  - name: a\n    subsumed_by: a\n", "names itself"},
		"mutual cycle":      {"runners:\n  - name: a\n    subsumed_by: b\n  - name: b\n    subsumed_by: a\n", "subsumption cycle a→b→a"},
		"three cycle":       {"runners:\n  - name: a\n    subsumed_by: b\n  - name: b\n    subsumed_by: c\n  - name: c\n    subsumed_by: a\n", "subsumption cycle a→b→c→a"},
		"undeclared target": {"runners:\n  - name: a\n    subsumed_by: z\n", "undeclared runner z"},
		"timeout over max":  {"max_invocation_s: 10\nrunners:\n  - name: a\n    timeout_s: 11\n", "timeout_s 11 exceeds max_invocation_s 10"},
		"batch over max":    {"runners:\n  - name: a\n    max_invocation_s: 5\n    timeout_s: 1\n    batch_timeout_s: 6\n", "batch_timeout_s 6 exceeds"},
		"default over max":  {"max_invocation_s: 60\nrunners:\n  - name: a\n", "the default timeout_s 600 exceeds"},
		"zero seconds":      {"runners:\n  - name: a\n    timeout_s: 0\n", "number of seconds in [0.001, 2592000]"},
		"infinite seconds":  {"runners:\n  - name: a\n    timeout_s: Inf\n", "number of seconds in"},
		"NaN seconds":       {"runners:\n  - name: a\n    timeout_s: NaN\n", "number of seconds in"},
		"sub-ms seconds":    {"runners:\n  - name: a\n    timeout_s: 1e-12\n", "number of seconds in"},
		"huge seconds":      {"max_invocation_s: 1e300\nrunners: []\n", "number of seconds in"},
		"yaml .inf":         {"max_invocation_s: .inf\nrunners: []\n", "number of seconds in"},
		"bad describe key":  {"runners:\n  - name: a\n    timeouts: never\n", ""},
	} {
		_, err := ParseConfig([]byte(tc.in))
		if name == "bad describe key" {
			continue // a describe value is checked once merged (TestDescribeOverrideValidated)
		}
		if err == nil || !strings.Contains(err.Error(), tc.want) {
			t.Errorf("%s: %v (want %q)", name, err, tc.want)
		}
	}
}

func TestLoadConfigAbsentAndContract(t *testing.T) {
	root := t.TempDir()
	if _, err := LoadConfig(root); !errors.Is(err, ErrNoRunners) {
		t.Fatalf("absent: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(root, registry.Dir), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, RunnersPath), []byte("contract: 2\nrunners: []\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	var cm *testmap.ContractMismatchError
	if _, err := LoadConfig(root); !errors.As(err, &cm) {
		t.Fatalf("contract 2: %v", err)
	}
}

// Ownership: a testmap:runner override beats bindings (file level and per
// member), the first matching binding beats later ones, an unbound unit
// belongs to the runner that listed it, and a lister that does not own a
// unit drops it.
func TestOwnership(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{
		"tests/test_a.sh":         "#!/bin/sh\n",
		"tests/special/test_s.sh": "#!/bin/sh\n",
		"tests/special/test_o.sh": "#!/bin/sh\n# testmap:runner special\n",
		"tests/m.sh":              "#!/bin/sh\n# testmap:unit A\n# testmap:unit B\n# testmap:runner special\n",
		"suite/whole.cfg":         "",
	})
	both := "tests/test_a.sh|file|a\ntests/special/test_s.sh|file|s\ntests/special/test_o.sh|file|o\ntests/m.sh#A|method|A\ntests/m.sh#B|method|B\n"
	put(t, r, "shell", spec{describe: "unit: file", list: both})
	put(t, r, "special", spec{describe: "unit: file", list: both})
	put(t, r, "whole", spec{describe: "unit: suite", list: "suite/whole.cfg|suite|all\n"})
	runners(t, r, `runners:
  - name: shell
    bind: ['tests/**/*.sh']
  - name: special
    bind: ['tests/special/**']
  - name: whole
`)
	commitAll(t, r)
	repo, err := Load(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	owner := map[string]string{}
	for _, u := range repo.Units {
		owner[u.ID.String()] = u.Runner
	}
	want := map[string]string{
		"tests/test_a.sh":         "shell",   // binding
		"tests/special/test_s.sh": "shell",   // first match wins over the later special binding
		"tests/special/test_o.sh": "special", // file-level override
		"tests/m.sh#A":            "shell",   // binding (the file-level block names no runner)
		"tests/m.sh#B":            "special", // member override
		"suite/whole.cfg":         "whole",   // unbound: its only lister
	}
	if !reflect.DeepEqual(owner, want) {
		t.Fatalf("owners %v\nwant   %v", owner, want)
	}
	if got := repo.Bound["special"]; !slices.Equal(got, []string{"tests/special/test_o.sh"}) {
		t.Errorf("special bound %v", got)
	}
	if got := repo.Bound["shell"]; !slices.Contains(got, "tests/special/test_s.sh") || slices.Contains(got, "tests/special/test_o.sh") {
		t.Errorf("shell bound %v", got)
	}
	// The lister input: each unit appears under its owner only.
	for _, l := range repo.Listings() {
		for _, u := range l.Units {
			if owner[u.ID.String()] != l.Runner {
				t.Errorf("%s listed under %s", u.ID, l.Runner)
			}
		}
	}
}

func TestOwnershipRefusals(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{"tests/x.sh": "#!/bin/sh\n# testmap:runner nobody\n"})
	put(t, r, "a", spec{describe: "unit: file", list: "tests/x.sh|file|x\n"})
	runners(t, r, "runners:\n  - name: a\n    bind: ['tests/*']\n")
	commitAll(t, r)
	if _, err := Load(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "RUNNER_UNKNOWN:tests/x.sh|nobody") {
		t.Fatalf("unknown override: %v", err)
	}
	r = newRepo(t, map[string]string{"tests/x.sh": "#!/bin/sh\n"})
	put(t, r, "a", spec{describe: "unit: file", list: "tests/x.sh|file|x\n"})
	put(t, r, "b", spec{describe: "unit: file", list: "tests/x.sh|file|x\n"})
	runners(t, r, "runners:\n  - name: a\n  - name: b\n")
	commitAll(t, r)
	if _, err := Load(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "listed by a, b") {
		t.Fatalf("two unbound listers: %v", err)
	}
}

// Shadow-by-name: an executable aitestmap/runners/<name>.sh shadows the
// builtin and the resolution record says so; without it the builtin runs as
// `<self> runner <builtin> <verb>` with the command override in its env; an
// unregistered builtin and a non-executable shadow are refused.
func TestShadowByNameAndBuiltins(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	withBuiltin(t, "pytest")
	r := newRepo(t, map[string]string{"tests/test_a.py": ""})
	put(t, r, "pytest", spec{describe: "unit: file", list: "tests/test_a.py|file|a\n"})
	runners(t, r, "runners:\n  - name: pytest\n    builtin: pytest\n    command: python3 -m pytest\n")
	commitAll(t, r)
	repo, err := Load(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	want := Resolution{Runner: "pytest", Source: SourceShadow, Path: "aitestmap/runners/pytest.sh", Reason: "aitestmap/runners/pytest.sh shadows builtin:pytest"}
	if got := repo.Runner("pytest").Resolution; got != want {
		t.Fatalf("resolution %+v", got)
	}

	// Without the shadow: the builtin, through SelfExe.
	r.Remove(t, "aitestmap/runners/pytest.sh")
	self := filepath.Join(stateOf(t, r), "self.sh")
	body := "#!/usr/bin/env bash\n[ \"$1 $2\" = 'runner pytest' ] || exit 9\n[ \"$AIT_TESTMAP_COMMAND\" = 'python3 -m pytest' ] || exit 8\n" +
		"case \"$3\" in describe) echo 'unit: file';; list) printf 'tests/test_a.py\\tfile\\ta\\n';; esac\n"
	if err := os.WriteFile(self, []byte(body), 0o755); err != nil {
		t.Fatal(err)
	}
	old := SelfExe
	SelfExe = func() (string, error) { return self, nil }
	t.Cleanup(func() { SelfExe = old })
	repo, err = Load(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	if got := repo.Runner("pytest").Resolution; got.Source != SourceBuiltin || got.Reason != "builtin:pytest" || len(repo.Units) != 1 {
		t.Fatalf("builtin: %+v %v", got, repo.Units)
	}

	runners(t, r, "runners:\n  - name: pytest\n    builtin: nosuch\n")
	if _, err := Load(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "RUNNER_UNRESOLVED:pytest|builtin nosuch is not registered") {
		t.Fatalf("unregistered builtin: %v", err)
	}
	runners(t, r, "runners:\n  - name: pytest\n    builtin: pytest\n")
	r.Write(t, "aitestmap/runners/pytest.sh", "#!/bin/sh\n") // not executable
	if _, err := Load(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "is not an executable file") {
		t.Fatalf("non-executable shadow: %v", err)
	}
	runners(t, r, "runners:\n  - name: lonely\n")
	if _, err := Load(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "RUNNER_UNRESOLVED:lonely|no script:, builtin: or aitestmap/runners/lonely.sh") {
		t.Fatalf("nothing to run: %v", err)
	}
}

// runners.yaml describe keys override the runner's own describe (a generic
// suite builtin cannot know full / children), and the merged result is
// validated.
func TestDescribeOverrideValidated(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{"suite.cfg": ""})
	put(t, r, "full", spec{describe: "unit: file", list: "suite.cfg|suite|all\n"})
	runners(t, r, "runners:\n  - name: full\n    unit: suite\n    full: true\n    children: pytest-junitxml\n    fallback_command: make test\n")
	commitAll(t, r)
	repo, err := Load(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	if d := repo.Runner("full").Describe; d.Unit != "suite" || !d.Full || d.Children != "pytest-junitxml" {
		t.Fatalf("merged %+v", d)
	}
	for yaml, want := range map[string]string{
		"runners:\n  - name: full\n    timeouts: never\n":                                   "RUNNER_INVALID:full|describe: timeouts",
		"runners:\n  - name: full\n    axis: a.b\n":                                         "RUNNER_INVALID:full|describe: axis: invalid axis name",
		"runners:\n  - name: full\n    token_format: '{nope}'\n":                            "unknown placeholder {nope}",
		"runners:\n  - name: full\n    fallback_command: make test\n":                       "fallback_command is only valid on a unit: suite runner",
		"runners:\n  - name: full\n    timeouts: batch\n":                                   "timeouts: batch needs batch_timeout_s",
		"runners:\n  - name: full\n    batch_timeout_s: 5\n    timeout_s: 1\n":              "batch_timeout_s is only valid with timeouts: batch",
		"runners:\n  - name: full\n    unit: suite\n  - name: sub\n    subsumed_by: full\n": "",
	} {
		runners(t, r, yaml)
		if want == "" {
			continue
		}
		if _, err := Load(bg, r.Dir); err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("%q: %v (want %q)", yaml, err, want)
		}
	}
	// subsumed_by a runner that is not full: true.
	put(t, r, "sub", spec{describe: "unit: file", list: ""})
	runners(t, r, "runners:\n  - name: full\n    unit: suite\n  - name: sub\n    subsumed_by: full\n")
	if _, err := Load(bg, r.Dir); err == nil || !strings.Contains(err.Error(), "RUNNER_INVALID:sub|subsumed_by full is not a full: true runner") {
		t.Fatalf("non-full target: %v", err)
	}
}

// batch / needs reach the units: runner needs ∪ file needs ∪ member needs,
// sorted; testmap:batch no (member over file) and timeouts: none make a unit
// a singleton.
func TestUnitAttributes(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{
		"tests/m.sh": "#!/bin/sh\n# testmap:needs b\n# testmap:batch no\n# testmap:unit A\n# testmap:needs c a\n# testmap:batch yes\n# testmap:unit B\n",
		"tests/n.sh": "#!/bin/sh\n",
	})
	put(t, r, "shell", spec{describe: "unit: method\nneeds: [z]\ntimeouts: batch",
		list: "tests/m.sh#A|method|A\ntests/m.sh#B|method|B\ntests/m.sh#B@v|variant|Bv\ntests/n.sh|file|n\n"})
	put(t, r, "single", spec{describe: "unit: file", list: "tests/o.sh|file|o\n"})
	r.Write(t, "tests/o.sh", "#!/bin/sh\n")
	runners(t, r, "runners:\n  - name: shell\n    timeout_s: 7\n    batch_timeout_s: 70\n  - name: single\n")
	commitAll(t, r)
	repo, err := Load(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	got := map[string]Unit{}
	for _, u := range repo.Units {
		got[u.ID.String()] = u
	}
	check := func(id string, res []string, batchNo bool) {
		t.Helper()
		u := got[id]
		if !slices.Equal(u.Resources, res) || u.BatchNo != batchNo {
			t.Errorf("%s: resources %v batchNo %v; want %v %v", id, u.Resources, u.BatchNo, res, batchNo)
		}
	}
	check("tests/m.sh#A", []string{"a", "b", "c", "z"}, false) // member batch yes overrides the file's no
	check("tests/m.sh#B", []string{"b", "z"}, true)            // inherits the file's batch no
	check("tests/m.sh#B@v", []string{"b", "z"}, true)          // a variant inherits its base unit's
	check("tests/n.sh", []string{"z"}, false)
	check("tests/o.sh", nil, true) // timeouts: none → engine-bounded singleton
	if got["tests/m.sh#A"].TimeoutS != 7 || got["tests/o.sh"].TimeoutS != DefaultTimeoutS {
		t.Errorf("timeouts %v %v", got["tests/m.sh#A"].TimeoutS, got["tests/o.sh"].TimeoutS)
	}
}
