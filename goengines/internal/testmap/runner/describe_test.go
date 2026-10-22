package runner

import (
	"reflect"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// Every M3.1 describe key decodes to its field, both list forms included.
func TestDescribeGoldens(t *testing.T) {
	withReportingContract(t, "pytest-junitxml")
	d, err := ParseDescribe([]byte(`unit: class
batch: no
needs: [heavy-run, emulator]
group_by: regex:^(.*?)/src/
filter_scope: whole_run
full: yes
children: pytest-junitxml
artifact_glob: app/src/**/screens/*.kt
timeouts: batch
`))
	if err != nil {
		t.Fatal(err)
	}
	want := Describe{Unit: "class", Batch: false, Needs: []string{"heavy-run", "emulator"}, GroupBy: "regex:^(.*?)/src/",
		FilterScope: FilterWholeRun, Full: true, Children: "pytest-junitxml", ArtifactGlob: []string{"app/src/**/screens/*.kt"}, Timeouts: TimeoutsBatch,
		Accounting: AccountingUnit, Discovery: DiscoveryCandidates}
	if !reflect.DeepEqual(d, want) {
		t.Fatalf("got  %+v\nwant %+v", d, want)
	}
	if err := d.Validate(); err != nil {
		t.Fatal(err)
	}
	min, err := ParseDescribe([]byte("unit: file\n"))
	if err != nil {
		t.Fatal(err)
	}
	if want := (Describe{Unit: "file", Batch: true, GroupBy: "none", FilterScope: FilterPerUnit, Timeouts: TimeoutsNone,
		Accounting: AccountingUnit, Discovery: DiscoveryCandidates}); !reflect.DeepEqual(min, want) {
		t.Fatalf("defaults: %+v", min)
	}
}

// Unknown keys and malformed values are refused, never ignored.
func TestDescribeRefusesUnknown(t *testing.T) {
	for _, in := range []string{
		"unit: file\nbogus: 1\n",
		"unit: file\nunit: class\n",
		"unit: file\nbatch: maybe\n",
		"unit: file\nneeds: {a: b}\n",
		"- unit\n",
		"",
	} {
		if _, err := ParseDescribe([]byte(in)); err == nil {
			t.Errorf("%q accepted", in)
		}
	}
	_, err := ParseDescribe([]byte("unit: file\nbogus: 1\n"))
	if err == nil || !strings.Contains(err.Error(), `unknown key "bogus"`) {
		t.Errorf("bogus: %v", err)
	}
}

// A registered key (a later submodule's named extension) lands raw in Ext
// and survives a merge; registering one of M3.1's own keys, or a key
// already registered (M2.4's axis), panics.
func TestDescribeExtensionKey(t *testing.T) {
	const key = "x_test_key"
	RegisterDescribeKey(key)
	t.Cleanup(func() { extMu.Lock(); delete(extKeys, key); extMu.Unlock() })
	d, err := ParseDescribe([]byte("unit: variant\n" + key + ": locale\n"))
	if err != nil {
		t.Fatal(err)
	}
	if n, ok := d.Ext[key]; !ok || n.Value != "locale" {
		t.Fatalf("Ext = %v", d.Ext)
	}
	if m := (Describe{}).Merge(d, map[string]bool{}); m.Ext[key].Value != "locale" {
		t.Fatal("merge dropped an extension key")
	}
	for _, k := range []string{"unit", "axis"} {
		func() {
			defer func() {
				if recover() == nil {
					t.Errorf("registering %s did not panic", k)
				}
			}()
			RegisterDescribeKey(k)
		}()
	}
}

// M2.4's describe keys: `axis:` names an axis and `token_format:` is a token
// template; both are validated (shape only — whether the axis is declared is
// check's UNKNOWN_VARIANT) and read back through the accessors.
func TestDescribeAxisKeys(t *testing.T) {
	d, err := ParseDescribe([]byte("unit: variant\naxis: matrix\ntoken_format: '{base}@{variant}'\n"))
	if err != nil {
		t.Fatal(err)
	}
	if err := d.Validate(); err != nil {
		t.Fatal(err)
	}
	id := registry.MustParseID("app/F.kt#Welcome@ru")
	if d.Axis() != "matrix" || d.TokenFormat().Render(id) != "app/F.kt#Welcome@ru" {
		t.Fatalf("axis %q token %q", d.Axis(), d.TokenFormat().Render(id))
	}
	if plain, _ := ParseDescribe([]byte("unit: file\n")); plain.Axis() != "" || plain.TokenFormat().Render(id) != id.String() {
		t.Fatal("absent keys must default to no axis and {id}")
	}
	for in, want := range map[string]string{
		"unit: variant\naxis: [a]\n":               "axis must be a string",
		"unit: variant\naxis: ~\n":                 "axis must be a string",
		"unit: variant\naxis: a.b\n":               "invalid axis name",
		"unit: variant\naxis: 'a b'\n":             "invalid axis name",
		"unit: variant\ntoken_format: '{bogus}'\n": "unknown placeholder",
		"unit: variant\ntoken_format: '{id'\n":     "unbalanced '{'",
		"unit: variant\ntoken_format: 'id}'\n":     "unbalanced '}'",
		"unit: variant\ntoken_format: ''\n":        "token_format is empty",
	} {
		d, err := ParseDescribe([]byte(in))
		if err == nil {
			err = d.Validate()
		}
		if err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("%q: %v (want %q)", in, err, want)
		}
	}
}

func TestDescribeValidate(t *testing.T) {
	for _, in := range []string{
		"batch: true\n", // unit required
		"unit: module\n",
		"unit: file\nneeds: ['a b']\n",
		"unit: file\ngroup_by: module\n",
		"unit: file\ngroup_by: 'regex:('\n",
		"unit: file\ngroup_by: 'regex:^src/'\n", // no capture group
		"unit: file\nfilter_scope: some\n",
		"unit: file\nchildren: x\n", // needs full
		"unit: suite\nfull: true\nchildren: 'a b'\n",
		"unit: file\nartifact_glob: ['a/[']\n",
		"unit: file\ntimeouts: sometimes\n",
	} {
		d, err := ParseDescribe([]byte(in))
		if err != nil {
			t.Errorf("%q: parse: %v", in, err)
			continue
		}
		if err := d.Validate(); err == nil {
			t.Errorf("%q validated", in)
		}
	}
}

func TestGroupOf(t *testing.T) {
	id := registry.MustParseID("core/src/test/FooTest.kt#Foo@ltr")
	for g, want := range map[string]string{"none": "", "file": "core/src/test/FooTest.kt", "dir": "core/src/test", "regex:^(.*?)/src/": "core"} {
		got, err := Describe{GroupBy: g}.GroupOf(id)
		if err != nil || got != want {
			t.Errorf("%s: %q %v", g, got, err)
		}
	}
	if _, err := (Describe{GroupBy: "regex:^(app)/"}).GroupOf(id); err == nil {
		t.Error("a non-matching group_by regex grouped")
	}
}

// Exactly one YAML document: a key in a second document would otherwise
// vanish unvalidated, in describe output and in runners.yaml alike.
func TestOneDocumentOnly(t *testing.T) {
	if _, err := ParseDescribe([]byte("unit: file\n---\ntimeouts: per_unit\nbogus: x\n")); err == nil || !strings.Contains(err.Error(), "more than one YAML document") {
		t.Errorf("describe: %v", err)
	}
	if _, err := ParseConfig([]byte("runners: []\n---\nrunnerz: 1\n")); err == nil || !strings.Contains(err.Error(), "more than one YAML document") {
		t.Errorf("runners.yaml: %v", err)
	}
	if _, err := ParseDescribe([]byte("unit: file\n---\n")); err == nil {
		t.Error("an empty second document accepted")
	}
}

// The describe `axis:` reaches M2.1's lister input (M2.4), so `scan` can
// persist which axis a unit's variants live on; a runner naming none leaves
// it empty.
func TestListingsCarryAxis(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{"app/F.kt": "class F\n", "tests/test_a.sh": "#!/bin/sh\n"})
	put(t, r, "screens", spec{describe: "unit: variant\naxis: matrix", list: "app/F.kt@ru|variant|F-ru\napp/F.kt@en|variant|F-en\n"})
	put(t, r, "shell", spec{describe: "unit: file", list: "tests/test_a.sh|file|a\n"})
	runners(t, r, "runners:\n  - name: screens\n    bind: ['app/**']\n  - name: shell\n    bind: ['tests/*.sh']\n")
	commitAll(t, r)
	repo, err := Load(bg, r.Dir)
	if err != nil {
		t.Fatal(err)
	}
	got := map[string]string{}
	for _, l := range repo.Listings() {
		got[l.Runner] = l.Axis
	}
	if got["screens"] != "matrix" || got["shell"] != "" {
		t.Fatalf("%v", got)
	}
}
