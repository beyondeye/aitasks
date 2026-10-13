package provider

import (
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

// rec is a recorded tool token: [start, end) and the tool's type.
type rec struct {
	s, e int
	typ  string
}

// pygClass maps recorded Pygments types the way provider/pygments.go does.
func pygClass(typ string) TokClass {
	switch {
	case typ == "Token.Literal.String.Interpol":
		return TInterpOpen // only used where the recorded text is "${"; see interp() below
	case strings.HasPrefix(typ, "Token.Literal.String"):
		return TString
	case strings.HasPrefix(typ, "Token.Comment.Single"):
		return TLineComment
	case strings.HasPrefix(typ, "Token.Comment"):
		return TBlockComment
	}
	return TCode
}

func classify(src string, rs []rec, interp func(text string) TokClass) []CTok {
	var out []CTok
	for _, r := range rs {
		c := pygClass(r.typ)
		if r.typ == "Token.Literal.String.Interpol" {
			c = interp(src[r.s:r.e])
		}
		out = append(out, CTok{r.s, r.e, c})
	}
	return out
}

func classesOf(t *testing.T, lang, src string, spans []Span) []annot.LineClass {
	t.Helper()
	ctx, err := ToContext(lang, []byte(src), Capabilities{TokenRanges: true}, Result{Spans: spans}, NeedLexical)
	if err != nil {
		t.Fatal(err)
	}
	return ctx.Class
}

// The recorded Pygments 2.21.0 stream (stripnl/ensurenl off) for a Python
// triple-quoted string split at every newline: line 2 ("# no") begins at
// byte 9, exactly where a fragment begins.
const pyMulti = "x = \"\"\"a\n# no\nb\"\"\"\ny = 1  # c\n# d\n"

var pyMultiToks = []rec{
	{0, 1, "Token.Name"}, {1, 2, "Token.Text"}, {2, 3, "Token.Operator"}, {3, 4, "Token.Text"},
	{4, 7, "Token.Literal.String.Double"}, {7, 8, "Token.Literal.String.Double"},
	{8, 9, "Token.Literal.String.Double"}, {9, 13, "Token.Literal.String.Double"},
	{13, 14, "Token.Literal.String.Double"}, {14, 15, "Token.Literal.String.Double"},
	{15, 18, "Token.Literal.String.Double"}, {18, 19, "Token.Text.Whitespace"},
	{19, 20, "Token.Name"}, {20, 21, "Token.Text"}, {21, 22, "Token.Operator"}, {22, 23, "Token.Text"},
	{23, 24, "Token.Literal.Number.Integer"}, {24, 26, "Token.Text"},
	{26, 29, "Token.Comment.Single"}, {29, 30, "Token.Text.Whitespace"},
	{30, 33, "Token.Comment.Single"}, {33, 34, "Token.Text.Whitespace"},
}

func noInterp(string) TokClass { return TString }

func TestCoalesceFragmentBoundary(t *testing.T) {
	toks := classify(pyMulti, pyMultiToks, noInterp)
	spans := Coalesce([]byte(pyMulti), toks)
	got := classesOf(t, "python", pyMulti, spans)
	want := []annot.LineClass{annot.Code, annot.Literal, annot.Literal, annot.Code, annot.Comment}
	for i, w := range want {
		if got[i] != w {
			t.Fatalf("coalesced: line %d class %v, want %v (spans %v)", i+1, got[i], w, spans)
		}
	}
	// Negative control: the raw fragments as spans put line 2 on a fragment
	// boundary, which ToContext (strict start check) classes Code.
	var raw []Span
	for _, c := range toks {
		if c.Class == TString {
			raw = append(raw, Span{c.Start, c.End, String})
		}
	}
	if rawCls := classesOf(t, "python", pyMulti, raw); rawCls[1] != annot.Code {
		t.Fatalf("negative control: raw fragments gave line 2 %v; the boundary bug this test guards is not reproduced", rawCls[1])
	}
}

// A literal that genuinely opens at a line start keeps that line's class.
func TestCoalesceConstructStartUnaffected(t *testing.T) {
	src := "\"\"\"top\n# doc\n\"\"\"\n"
	spans := Coalesce([]byte(src), []CTok{{0, 16, TString}, {16, 17, TCode}})
	got := classesOf(t, "python", src, spans)
	if got[0] != annot.Code || got[1] != annot.Literal || got[2] != annot.Literal {
		t.Fatalf("classes %v", got)
	}
}

// Kotlin: an interpolation inside a raw string, as Pygments tokenises it
// (recorded), yields ONE string span; the comment after the literal stays a
// comment.
func TestCoalesceInterpolation(t *testing.T) {
	src := "val s = \"\"\"a\n${f(\"x\")}\n// no\n\"\"\"\n// c\n"
	rs := []rec{
		{0, 3, "Token.Keyword.Declaration"}, {3, 4, "Token.Text.Whitespace"}, {4, 5, "Token.Name.Variable"},
		{5, 6, "Token.Text.Whitespace"}, {6, 7, "Token.Operator"}, {7, 8, "Token.Text.Whitespace"},
		{8, 11, "Token.Literal.String"}, {11, 13, "Token.Literal.String"}, {13, 15, "Token.Literal.String.Interpol"},
		{15, 16, "Token.Name"}, {16, 17, "Token.Punctuation"}, {17, 18, "Token.Literal.String"},
		{18, 19, "Token.Name"}, {19, 20, "Token.Literal.String"}, {20, 21, "Token.Punctuation"},
		{21, 22, "Token.Literal.String.Interpol"}, {22, 29, "Token.Literal.String"}, {29, 32, "Token.Literal.String"},
		{32, 33, "Token.Text.Whitespace"}, {33, 37, "Token.Comment.Single"}, {37, 38, "Token.Text.Whitespace"},
	}
	interp := func(text string) TokClass {
		if strings.HasSuffix(text, "{") {
			return TInterpOpen
		}
		return TInterpClose
	}
	spans := Coalesce([]byte(src), classify(src, rs, interp))
	if len(spans) != 2 || spans[0] != (Span{8, 32, String}) || spans[1] != (Span{33, 37, LineComment}) {
		t.Fatalf("spans %v", spans)
	}
	got := classesOf(t, "kotlin", src, spans)
	want := []annot.LineClass{annot.Code, annot.Literal, annot.Literal, annot.Literal, annot.Comment}
	for i, w := range want {
		if got[i] != w {
			t.Fatalf("line %d class %v want %v", i+1, got[i], w)
		}
	}
}

// An interpolation the tool leaves without a close never swallows a token
// the tool called a comment.
func TestCoalesceNeverSwallowsComments(t *testing.T) {
	src := "\"${x\n// c\n"
	spans := Coalesce([]byte(src), []CTok{{0, 1, TString}, {1, 3, TInterpOpen}, {3, 4, TCode}, {4, 5, TCode}, {5, 9, TLineComment}, {9, 10, TCode}})
	if len(spans) != 2 || spans[0] != (Span{0, 5, String}) || spans[1] != (Span{5, 9, LineComment}) {
		t.Fatalf("spans %v", spans)
	}
}

func TestCoalesceLineCommentTrimAndBlockMerge(t *testing.T) {
	src := "// a\n/* b\n c */\n"
	spans := Coalesce([]byte(src), []CTok{{0, 5, TLineComment}, {5, 10, TBlockComment}, {10, 15, TBlockComment}, {15, 16, TCode}})
	if len(spans) != 2 || spans[0] != (Span{0, 4, LineComment}) || spans[1] != (Span{5, 15, BlockComment}) {
		t.Fatalf("spans %v", spans)
	}
}

func TestBracketed(t *testing.T) {
	// QUOTE_OPEN x ${ QUOTE_OPEN y QUOTE_CLOSE } QUOTE_CLOSE, then an unclosed one.
	type tk struct {
		s, e int
		k    string
	}
	ts := []tk{{0, 1, "open"}, {1, 2, ""}, {2, 4, ""}, {4, 5, "open"}, {5, 6, ""}, {6, 7, "close"}, {7, 8, ""}, {8, 9, "close"}, {10, 11, "code"}, {12, 13, "open"}, {13, 15, ""}}
	got := Bracketed(len(ts), func(i int) (int, int) { return ts[i].s, ts[i].e },
		func(i int) bool { return ts[i].k == "open" }, func(i int) bool { return ts[i].k == "close" })
	if len(got) != 2 || got[0] != (Span{0, 9, String}) || got[1] != (Span{12, 15, String}) {
		t.Fatalf("got %v", got)
	}
}
