package runner

import (
	"errors"
	"reflect"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// Member and variant ids and the artifact column parse; the kind is the
// granularity vocabulary.
func TestListParse(t *testing.T) {
	rows, err := ParseList([]byte("tests/test_a.sh\tfile\ttests/test_a.sh\n" +
		"app/F.kt#Welcome\tclass\tcom.x.Welcome\n" +
		"app/F.kt#Welcome@rtl\tvariant\tcom.x.Welcome --rtl\tapp/res/rtl.png\n"))
	if err != nil {
		t.Fatal(err)
	}
	want := []ListRow{
		{Unit: registry.ListedUnit{ID: registry.MustParseID("tests/test_a.sh"), Kind: "file", Lowering: "tests/test_a.sh"}, Line: 1},
		{Unit: registry.ListedUnit{ID: registry.MustParseID("app/F.kt#Welcome"), Kind: "class", Lowering: "com.x.Welcome"}, Line: 2},
		{Unit: registry.ListedUnit{ID: registry.MustParseID("app/F.kt#Welcome@rtl"), Kind: "variant", Lowering: "com.x.Welcome --rtl", Artifact: "app/res/rtl.png"}, Line: 3},
	}
	if !reflect.DeepEqual(rows, want) {
		t.Fatalf("got  %+v\nwant %+v", rows, want)
	}
	if rows, err := ParseList(nil); err != nil || rows != nil {
		t.Fatalf("empty list: %v %v", rows, err)
	}
}

// Every malformed row is refused with its line — never skipped. A
// SCAFFOLD_TODO line is malformed until M6.4 recognises it.
func TestListMalformed(t *testing.T) {
	for name, tc := range map[string]struct{ in, want string }{
		"two fields":    {"a.sh\tfile\n", "list line 1: 2 fields"},
		"five fields":   {"a.sh\tfile\tx\ty\tz\n", "list line 1: 5 fields"},
		"empty field":   {"a.sh\t\tx\n", "list line 1: field 2 is empty"},
		"blank line":    {"a.sh\tfile\tx\n\n", "list line 2: 1 fields"},
		"bad id":        {"../a.sh\tfile\tx\n", "list line 1: invalid unit id"},
		"bad kind":      {"a.sh\tunit\tx\n", `list line 1: kind "unit"`},
		"variant no @":  {"a.sh\tvariant\tx\n", "list line 1: variant row"},
		"bad artifact":  {"a.sh\tfile\tx\t/abs\n", "list line 1: artifact"},
		"duplicate id":  {"a.sh\tfile\tx\na.sh\tfile\ty\n", "list line 2: id a.sh already listed on line 1"},
		"no final eol":  {"a.sh\tfile\tx", "no trailing newline"},
		"control char":  {"a.sh\tfile\tx\r\n", "list line 1: field 3 contains a control character"},
		"scaffold todo": {"SCAFFOLD_TODO\n", "list line 1: 1 fields"},
	} {
		if _, err := ParseList([]byte(tc.in)); err == nil || !strings.Contains(err.Error(), tc.want) {
			t.Errorf("%s: %v (want %q)", name, err, tc.want)
		}
	}
}

// Through the real lister and M2.1's scan, a malformed row is
// INPUT_ERROR:lister|… (exit 3), and scan writes nothing.
func TestListMalformedThroughScan(t *testing.T) {
	if !isolated(t, hangLimit) {
		return
	}
	r := newRepo(t, map[string]string{"tests/test_a.sh": "#!/bin/sh\n"})
	put(t, r, "shell", spec{describe: "unit: file", list: "tests/test_a.sh|file\n"})
	runners(t, r, "runners:\n  - name: shell\n    bind: ['tests/*.sh']\n")
	commitAll(t, r)
	_, err := registry.Scan(bg, r.Dir, registry.Inputs{Annotations: noAnns{}, Lister: Lister{}}, true)
	var ie *registry.InputError
	if !errors.As(err, &ie) || ie.Input != registry.InputLister {
		t.Fatalf("scan: %v", err)
	}
	line, _ := ie.Line()
	if !strings.HasPrefix(line, "INPUT_ERROR:lister|RUNNER_PROTOCOL:shell/list/list line 1: 2 fields") {
		t.Fatalf("line %q", line)
	}
}
