package runner

import (
	"reflect"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// Every M3.1 describe key decodes to its field, both list forms included.
func TestDescribeGoldens(t *testing.T) {
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
		FilterScope: FilterWholeRun, Full: true, Children: "pytest-junitxml", ArtifactGlob: []string{"app/src/**/screens/*.kt"}, Timeouts: TimeoutsBatch}
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
	if want := (Describe{Unit: "file", Batch: true, GroupBy: "none", FilterScope: FilterPerUnit, Timeouts: TimeoutsNone}); !reflect.DeepEqual(min, want) {
		t.Fatalf("defaults: %+v", min)
	}
}

// Unknown keys — M2.4's axis / token_format until it registers them — and
// malformed values are refused, never ignored.
func TestDescribeRefusesUnknown(t *testing.T) {
	for _, in := range []string{
		"unit: file\naxis: locale\n",
		"unit: file\ntoken_format: x\n",
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
	_, err := ParseDescribe([]byte("unit: file\naxis: locale\n"))
	if err == nil || !strings.Contains(err.Error(), `unknown key "axis"`) {
		t.Errorf("axis: %v", err)
	}
}

// A registered key (M2.4's named extension) lands raw in Ext and survives a
// merge; registering one of M3.1's own keys panics.
func TestDescribeExtensionKey(t *testing.T) {
	RegisterDescribeKey("axis")
	t.Cleanup(func() { extMu.Lock(); delete(extKeys, "axis"); extMu.Unlock() })
	d, err := ParseDescribe([]byte("unit: variant\naxis: locale\n"))
	if err != nil {
		t.Fatal(err)
	}
	if n, ok := d.Ext["axis"]; !ok || n.Value != "locale" {
		t.Fatalf("Ext = %v", d.Ext)
	}
	if m := (Describe{}).Merge(d, map[string]bool{}); m.Ext["axis"].Value != "locale" {
		t.Fatal("merge dropped an extension key")
	}
	defer func() {
		if recover() == nil {
			t.Error("registering an M3.1 key did not panic")
		}
	}()
	RegisterDescribeKey("unit")
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
