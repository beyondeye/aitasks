package deps

import (
	"errors"
	"fmt"
	"slices"
	"strings"
	"testing"
)

func lexText(t *testing.T, src string) string {
	t.Helper()
	toks, err := ktLex(src)
	if err != nil {
		t.Fatalf("lex %q: %v", src, err)
	}
	var b []string
	for _, k := range toks {
		b = append(b, string(k.kind)+":"+k.text)
	}
	return strings.Join(b, " ")
}

func TestKotlinLexer(t *testing.T) {
	for src, want := range map[string]string{
		// Comments, nested block comments and string contents are skipped.
		"a /* x /* y */ z */ b // c d\ne": "n:a n:b n:e",
		`f("com.x.Y", 'c', '\'')`:         `n:f o:( s:com.x.Y o:, S: o:, S: o:)`,
		// Template code is kept.
		`"$name and ${com.x.util.f()}"`: "n:name n:com o:. n:x o:. n:util o:. n:f o:( o:) S:",
		// Raw strings; a run of more than three quotes: the last three close.
		`"""a "b" """"`:          `s:a "b" "`,
		"`odd name`.call()":      "n:odd name o:. n:call o:( o:)",
		"x::class.java":          "n:x o::: n:class o:. n:java",
		"@field:Inject lateinit": "o:@ n:field o:: n:Inject n:lateinit",
		// Dollars inside strings, and a lone $ in code before no quote.
		`"a$" + "$$"`: `s:a$ o:+ s:$$`,
		"$ x":         "o:$ n:x",
		"$$$ x":       "o:$ o:$ o:$ n:x",
		// $`name` is a short template whose name may hold quotes; the run's
		// last $ starts it. An empty or unclosed name, or one spanning a
		// newline, is text.
		"\"$`a\"b`\"":            "n:a\"b S:",
		"\"\"\"$`q\"\"\"`\"\"\"": "n:q\"\"\" S:",
		"\"$$`x\"`\"":            "n:x\" S:",
		"\"$``\"":                "s:$``",
		"\"$`x\"":                "s:$`x",
		"\"\"\"$`a\nb`\"\"\"":    "s:$`a\nb`",
	} {
		if got := lexText(t, src); got != want {
			t.Errorf("%s\n got %s\nwant %s", src, got, want)
		}
	}
	for _, bad := range []string{`"open`, "/* never", "\"a\nb\"", "`x", `"${a`,
		// Multi-dollar strings: the interpolation threshold is not modelled.
		`$$"""${/*}"""`, `$$"a"`, `"${ $$"x" }"`} {
		if _, err := ktLex(bad); err == nil {
			t.Errorf("%q tokenized", bad)
		}
	}
}

// A Kotlin 2.2 multi-dollar string's single ${ is literal text. Read as a
// template, the /* inside it opened a comment running to a later string's */
// and silently swallowed fun f() — the file now fails closed instead.
func TestKotlinLexerMultiDollarFailsClosed(t *testing.T) {
	src := "package p\n\nval s = $$\"\"\"${/*}\"\"\"\nfun f() = Callee()\nval t = \"\"\"*/}\"\"\"\n"
	if _, err := ktLex(src); !errors.Is(err, errUntokenizable) {
		t.Fatalf("ktLex err = %v, want errUntokenizable", err)
	}
	if got := scanKotlin([]byte(src)).Opaque; !slices.Contains(got, "untokenizable") {
		t.Fatalf("opaque %v, want untokenizable", got)
	}
}

// A backticked name keeps its unquoted text and kind, and is marked so that
// `fun` the identifier is never read as `fun` the keyword.
func TestKotlinLexerMarksEscapedIdentifiers(t *testing.T) {
	toks, err := ktLex("`fun` fun `interface` interface \"$`fun`\"")
	if err != nil {
		t.Fatal(err)
	}
	var got []string
	for _, k := range toks {
		got = append(got, fmt.Sprintf("%c:%s:%t", k.kind, k.text, k.esc))
	}
	if want := []string{"n:fun:true", "n:fun:false", "n:interface:true", "n:interface:false", "n:fun:true", "S::false"}; !slices.Equal(got, want) {
		t.Errorf("tokens %v, want %v", got, want)
	}
}

// A backticked name in a short template ($`q"""`) may hold quotes. Read as
// text, its quotes closed the string early; the backtick after them opened a
// name in code, the /* after that a comment running to the */ two lines down,
// and fun f(), Callee and val t vanished with no error.
func TestKotlinLexerShortTemplateBacktickedName(t *testing.T) {
	probe := func(call string) string {
		return lines(
			"package p",
			"val `q\"\"\"` = 1",
			"val s = \"\"\"$`q\"\"\"`\"\"\" + \"\"\"`/*\"\"\"",
			"fun f() = "+call,
			"val t = 1 // */",
		)
	}
	src := probe("Callee()")
	toks, err := ktLex(src)
	if err != nil {
		t.Fatalf("ktLex: %v", err)
	}
	var names []string
	for _, k := range toks {
		if k.kind == 'n' {
			names = append(names, k.text)
		}
	}
	for _, want := range []string{"f", "Callee", "t"} {
		if !slices.Contains(names, want) {
			t.Errorf("names %q lack %q", names, want)
		}
	}
	var decls []string
	for _, d := range scanKotlin([]byte(src)).Kt.Decls {
		decls = append(decls, d.Name)
	}
	for _, want := range []string{"f", "t"} {
		if !slices.Contains(decls, want) {
			t.Errorf("decls %q lack %q", decls, want)
		}
	}
	// Refs keep only lowercase-led dotted chains, so the qualified call is
	// what reaches them.
	refs := scanKotlin([]byte(probe("p.Callee()"))).Kt.Refs
	if !slices.Contains(refs, ktRef{Chain: "p.Callee", Line: 4}) {
		t.Errorf("refs %+v lack p.Callee at line 4", refs)
	}
}
