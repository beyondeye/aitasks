package registry

import (
	"errors"
	"testing"
)

// The id grammar golden table: <path>[#<member>][@<variant>].
func TestParseIDGolden(t *testing.T) {
	valid := []struct {
		in   string
		want ID
	}{
		{"tests/test_a.sh", ID{Path: "tests/test_a.sh"}},
		{"a", ID{Path: "a"}},
		{"app/ScreenFixtures.kt#Welcome", ID{Path: "app/ScreenFixtures.kt", Member: "Welcome"}},
		{"app/ScreenFixtures.kt#Welcome@pixel5Ru_ltr", ID{Path: "app/ScreenFixtures.kt", Member: "Welcome", Variant: "pixel5Ru_ltr"}},
		{"tests/golden/x.md@ru-rtl", ID{Path: "tests/golden/x.md", Variant: "ru-rtl"}},
		{".github/x.yml#job.step", ID{Path: ".github/x.yml", Member: "job.step"}},
		{"a/b.c/d-e_f.py#Test::method", ID{Path: "a/b.c/d-e_f.py", Member: "Test::method"}},
	}
	for _, tc := range valid {
		got, err := ParseID(tc.in)
		if err != nil || got != tc.want {
			t.Errorf("ParseID(%q) = %+v, %v; want %+v", tc.in, got, err, tc.want)
			continue
		}
		if got.String() != tc.in {
			t.Errorf("String() = %q, want round trip %q", got.String(), tc.in)
		}
		if !got.Valid() {
			t.Errorf("%q: Valid() false", tc.in)
		}
	}
	invalid := []string{
		"", "#m", "@v", "/abs/x", "a//b", "a/", "./a", "a/./b", "a/../b", "..", `a\b`,
		"a#", "a@", "a#m@", "a#@v", "a#m#n", "a@v@w", "a@v#m", "a#m/n", "a@v/w",
		"a b", "a#m n", "a@v\tw", "a|b", "a#m|n", "a\nb", "a#\x01",
	}
	for _, in := range invalid {
		if id, err := ParseID(in); err == nil || !errors.Is(err, ErrBadID) {
			t.Errorf("ParseID(%q) = %+v, %v; want ErrBadID", in, id, err)
		}
	}
}

func TestIDBase(t *testing.T) {
	id := MustParseID("f.kt#M@v")
	if got := id.Base().String(); got != "f.kt#M" {
		t.Fatalf("Base = %q", got)
	}
	if got := MustParseID("f.md@v").Base().String(); got != "f.md" {
		t.Fatalf("Base = %q", got)
	}
}

func TestCheckPath(t *testing.T) {
	for _, p := range []string{"a", "a/b.go", ".aitask-scripts/aitask_x.sh"} {
		if err := CheckPath(p); err != nil {
			t.Errorf("%q: %v", p, err)
		}
	}
	for _, p := range []string{"", "/a", "a/../b", "a#b", "a@b", "a|b", "a b"} {
		if CheckPath(p) == nil {
			t.Errorf("%q: accepted", p)
		}
	}
}
