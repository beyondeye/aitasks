package deps

import (
	"errors"
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
