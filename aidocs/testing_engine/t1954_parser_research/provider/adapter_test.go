package provider

import (
	"errors"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

func missing(err error) string {
	var u *UnsupportedCapabilityError
	if errors.As(err, &u) {
		return strings.Join(u.Missing, ",")
	}
	return ""
}

func TestCheckFollowsTheOperationPath(t *testing.T) {
	noAnchors := Capabilities{TokenRanges: true, Errors: true}
	cases := []struct {
		name string
		lang string
		caps Capabilities
		need Need
		want string // missing capabilities, "" = supported
	}{
		{"lexical needs spans only", "kotlin", Capabilities{}, NeedLexical, ""},
		{"a restamp/member insert needs no anchors", "kotlin", noAnchors, NeedWrite, ""},
		{"a fresh file insert needs the language's anchors", "kotlin", noAnchors, NeedWrite | NeedFreshFileInsert, "APackage,AImportEnd"},
		{"declared anchors suffice", "kotlin", Capabilities{Errors: true, Anchors: APackage | AImportEnd}, NeedWrite | NeedFreshFileInsert, ""},
		{"bash fresh insert needs no anchors", "bash", noAnchors, NeedWrite | NeedFreshFileInsert, ""},
		{"rust needs inner attributes and imports", "rust", Capabilities{Errors: true, Anchors: AImportEnd}, NeedWrite | NeedFreshFileInsert, "AInnerAttrEnd"},
		{"a write without error reporting is unsupported", "go", Capabilities{TokenRanges: true}, NeedWrite, "Errors"},
		{"lexical without error reporting still scores", "go", Capabilities{TokenRanges: true}, NeedLexical, ""},
		{"python records need DocLiterals", "python", Capabilities{Errors: true}, NeedRecords, "DocLiterals"},
		{"python writes need DocLiterals", "python", Capabilities{Errors: true}, NeedWrite, "DocLiterals"},
		{"python classes do not", "python", Capabilities{Errors: true}, NeedLexical, ""},
	}
	for _, tc := range cases {
		err := Check(tc.lang, tc.caps, tc.need)
		if got := missing(err); got != tc.want || (tc.want == "" && err != nil) {
			t.Errorf("%s: missing %q (err %v), want %q", tc.name, got, err, tc.want)
		}
		if tc.want != "" && !errors.Is(err, ErrUnsupportedCapability) {
			t.Errorf("%s: %v does not wrap ErrUnsupportedCapability", tc.name, err)
		}
	}
}

func TestToContextEnforcesCheck(t *testing.T) {
	src := []byte("class T\n")
	_, err := ToContext("kotlin", src, Capabilities{Errors: true}, Result{}, NeedWrite|NeedFreshFileInsert)
	if missing(err) != "APackage,AImportEnd" {
		t.Fatalf("ToContext let an anchor-less provider reach fresh insertion: %v", err)
	}
}

func TestUndeclaredAnchorsAreNeverCopied(t *testing.T) {
	src := []byte("package a\nimport b.C\nclass T\n")
	res := Result{Anchors: Anchors{Package: 1, ImportEnd: 2}}
	ctx, err := ToContext("kotlin", src, Capabilities{Errors: true}, res, NeedWrite)
	if err != nil {
		t.Fatal(err)
	}
	if ctx.Package != 0 || ctx.Import != 0 {
		t.Fatalf("undeclared anchors leaked into the context: package %d import %d", ctx.Package, ctx.Import)
	}
	ctx, err = ToContext("kotlin", src, Capabilities{Errors: true, Anchors: APackage | AImportEnd}, res, NeedWrite|NeedFreshFileInsert)
	if err != nil || ctx.Package != 1 || ctx.Import != 2 {
		t.Fatalf("declared anchors: package %d import %d err %v", ctx.Package, ctx.Import, err)
	}
	if got := Mask(Anchors{Package: 4, ImportEnd: 5, Prologue: 6}, AImportEnd); got != (Anchors{ImportEnd: 5}) {
		t.Fatalf("Mask: %+v", got)
	}
}

func TestToContextClasses(t *testing.T) {
	// line 1 code; 2 a real comment; 3 opens a string; 4 inside it; 5 closes it; 6 heredoc body.
	src := []byte("x = 1\n  // c\nval s = \"\"\"\n// fake\n\"\"\"\nbody\n")
	starts := LineStarts(src)
	res := Result{Spans: []Span{
		{starts[1] + 2, starts[2] - 1, LineComment},
		{starts[2] + 8, starts[4] + 3, String},
		{starts[5], len(src) - 1, Heredoc},
	}}
	ctx, err := ToContext("kotlin", src, Capabilities{TokenRanges: true}, res, NeedLexical)
	if err != nil {
		t.Fatal(err)
	}
	want := []annot.LineClass{annot.Code, annot.Comment, annot.Code, annot.Literal, annot.Literal, annot.Literal}
	for i := range want {
		if ctx.Class[i] != want[i] {
			t.Errorf("line %d: class %d, want %d", i+1, ctx.Class[i], want[i])
		}
	}
	res.Diags = []Diag{{Start: starts[3], Reason: "boom"}}
	ctx, _ = ToContext("kotlin", src, Capabilities{TokenRanges: true}, res, NeedLexical)
	if ctx.Uncertain == nil || ctx.Uncertain.Line != 4 {
		t.Fatalf("a Diag must make the context uncertain at its line: %+v", ctx.Uncertain)
	}
}

func TestDocLiteralsConvertToColumns(t *testing.T) {
	src := []byte("(\n    \"doc\\n\"\n    \"testmap:covers src/g.sh\"\n)\n")
	starts := LineStarts(src)
	res := Result{Doc: &DocInfo{
		Literals: []DocLiteral{{starts[1] + 5, starts[1] + 10, false}, {starts[2] + 5, starts[2] + 28, false}},
		StmtEnd:  starts[3] + 1,
	}}
	ctx, err := ToContext("python", src, Capabilities{Errors: true, DocLiterals: true}, res, NeedRecords)
	if err != nil {
		t.Fatal(err)
	}
	if len(ctx.Docs) != 2 || ctx.Docs[1].StartLine != 3 || ctx.Docs[1].StartCol != 5 || ctx.DocEnd != 4 {
		t.Fatalf("docs %+v docEnd %d", ctx.Docs, ctx.DocEnd)
	}
}
