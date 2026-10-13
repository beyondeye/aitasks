package provider

import (
	"strings"
	"testing"
)

// Every node kind the mapping reads must exist in the grammar: a grammar
// bump that renames one must fail here instead of silently unmapping it.
func TestTSKindsExistInGrammars(t *testing.T) {
	for _, lang := range TSLangs {
		l := GoTreeSitterLanguages[lang]()
		have := map[string]bool{}
		for _, n := range l.SymbolNames {
			have[n] = true
		}
		for _, k := range TSKinds(lang) {
			if !have[k] {
				t.Errorf("%s: kind %q not in the grammar's symbol table", lang, k)
			}
		}
	}
}

func analyze(t *testing.T, lang, src string) (Result, []string) {
	t.Helper()
	res, err := NewGoTreeSitter().Analyze(lang, []byte(src))
	if err != nil {
		t.Fatalf("%s: %v", lang, err)
	}
	ctx, err := ToContext(lang, []byte(src), TSCaps(lang), res, NeedLexical)
	if err != nil {
		t.Fatalf("%s: ToContext: %v", lang, err)
	}
	var cls []string
	for _, c := range ctx.Class {
		cls = append(cls, [...]string{"code", "comment", "literal"}[c])
	}
	return res, cls
}

// The fake `testmap:` line inside each language's hardest string form is
// never a comment; the real comment after it is.
func TestTSFakeCommentInStrings(t *testing.T) {
	cases := map[string]string{
		"bash":       "x=$(cat <<EOF\n# testmap:covers fake\nEOF\n)\n# testmap:covers real\n",
		"python":     "s = \"\"\"\n# testmap:covers fake\n\"\"\"\n# testmap:covers real\n",
		"go":         "package p\nvar s = `\n// testmap:covers fake\n`\n// testmap:covers real\n",
		"kotlin":     "val s = \"\"\"\n// testmap:covers fake ${1}\n\"\"\"\n// testmap:covers real\n",
		"typescript": "const s = `${1}\n// testmap:covers fake\n`;\n// testmap:covers real\n",
		"javascript": "const s = `${1}\n// testmap:covers fake\n`;\n// testmap:covers real\n",
		"tsx":        "const e = <p>\n// testmap:covers fake\n</p>;\n// testmap:covers real\n",
		"java":       "class C { String s = \"\"\"\n// testmap:covers fake\n\"\"\"; }\n// testmap:covers real\n",
		"rust":       "const S: &str = r#\"\n// testmap:covers fake\n\"#;\n// testmap:covers real\n",
		"swift":      "let s = #\"\"\"\n// testmap:covers fake\n\"\"\"#\n// testmap:covers real\n",
	}
	for lang, src := range cases {
		res, cls := analyze(t, lang, src)
		if len(res.Diags) > 0 {
			t.Errorf("%s: unexpected diags %v", lang, res.Diags)
		}
		for i, line := range strings.Split(strings.TrimSuffix(src, "\n"), "\n") {
			if strings.Contains(line, "fake") && cls[i] == "comment" || strings.Contains(line, "real") && cls[i] != "comment" {
				t.Errorf("%s: line %d %q classed %s", lang, i+1, line, cls[i])
			}
		}
	}
}

// A comment inside a multi-line interpolation field is inside a string: by
// the M2.2 policy it is data, never an annotation line.
func TestTSInterpolationIsData(t *testing.T) {
	_, cls := analyze(t, "python", "t = f\"\"\"{\n# testmap:covers fake\nx}\"\"\"\n")
	if cls[1] != "literal" {
		t.Errorf("python f-string field: %v", cls)
	}
	// ...but bash `$( … )` inside double quotes is code (M2.2 / shfmt).
	_, cls = analyze(t, "bash", "x=\"$(\n# testmap:covers real\necho)\"\n")
	if cls[1] != "comment" {
		t.Errorf("bash quoted $( ): %v", cls)
	}
}

func TestTSMalformedHasDiags(t *testing.T) {
	for lang, src := range map[string]string{
		"python": "s = \"\"\"never closed\n",
		"go":     "package p\nfunc f( {\n",
		"rust":   "fn main() { let s = \"x;\n",
	} {
		res, _ := analyze(t, lang, src)
		if len(res.Diags) == 0 {
			t.Errorf("%s: malformed input produced no Diags", lang)
		}
	}
}

func TestTSPythonDocInfo(t *testing.T) {
	for _, c := range []struct {
		src     string
		lits    int
		raw     bool
		stmtEnd string // the source prefix the statement ends at
	}{
		{`"""Doc."""` + "\n", 1, false, `"""Doc."""`},
		{`r'''raw'''` + "\n", 1, true, `r'''raw'''`},
		{"(\"a\"\n \"b\")\nx = 1\n", 2, false, "(\"a\"\n \"b\")"},
		{`u"x"; y = 2` + "\n", 1, false, `u"x"`},
	} {
		res, _ := analyze(t, "python", c.src)
		if res.Doc == nil || len(res.Doc.Literals) != c.lits || res.Doc.Literals[0].Raw != c.raw || res.Doc.StmtEnd != len(c.stmtEnd) {
			t.Errorf("%q: doc %+v", c.src, res.Doc)
		}
	}
	for _, src := range []string{`f"""x"""` + "\n", `b"""x"""` + "\n", `("a")("b")` + "\n", "# c\nx = 1\n"} {
		if res, _ := analyze(t, "python", src); res.Doc != nil {
			t.Errorf("%q: not a docstring, got %+v", src, res.Doc)
		}
	}
}

func TestTSAnchors(t *testing.T) {
	for _, c := range []struct {
		lang, src string
		want      Anchors
	}{
		{"go", "package p\n\nimport (\n\t\"a\"\n)\n", Anchors{Package: 1, ImportEnd: 5}},
		{"kotlin", "package a\n\nimport b.C\nimport d.E\n\nclass X\n", Anchors{Package: 1, ImportEnd: 4}},
		{"java", "package a;\nimport b.C;\nclass X {}\n", Anchors{Package: 1, ImportEnd: 2}},
		{"javascript", "#!/usr/bin/env node\n\"use strict\";\nimport x from \"y\";\nf();\n", Anchors{Prologue: 2, ImportEnd: 3}},
		{"rust", "//! Doc.\n#![allow(x)]\n\nuse a::b;\nuse c::{\n  d,\n};\nfn f() {}\n", Anchors{InnerAttrEnd: 2, ImportEnd: 7}},
		{"swift", "@testable import A\nimport B\nclass C {}\n", Anchors{ImportEnd: 2}},
		{"bash", "#!/bin/sh\necho\n", Anchors{Shebang: 1}},
	} {
		res, _ := analyze(t, c.lang, c.src)
		if res.Anchors != c.want {
			t.Errorf("%s: anchors %+v, want %+v", c.lang, res.Anchors, c.want)
		}
	}
}

func TestTSLineCommentSpanEndsAtEOL(t *testing.T) {
	src := "//! inner\r\nfn f() {}\r\n"
	res, _ := analyze(t, "rust", src)
	for _, s := range res.Spans {
		if s.Kind == LineComment && strings.ContainsAny(src[s.Start:s.End], "\r\n") {
			t.Errorf("line comment %q includes its line ending", src[s.Start:s.End])
		}
	}
}

// A comment opening a bash continuation line trails the previous command:
// never an annotation line (M2.2 policy); a comment ending in a backslash
// does not continue, so the next comment line stays a comment.
func TestTSBashContinuationComment(t *testing.T) {
	_, cls := analyze(t, "bash", "echo a \\\n# testmap:covers x\n# real\n")
	if cls[1] == "comment" || cls[2] != "comment" {
		t.Errorf("continuation: %v", cls)
	}
	_, cls = analyze(t, "bash", "# a comment ending in \\\n# testmap:covers real\n")
	if cls[1] != "comment" {
		t.Errorf("comment ending in a backslash: %v", cls)
	}
	_, cls = analyze(t, "bash", "echo a \\\\\n# testmap:covers real\n")
	if cls[1] != "comment" {
		t.Errorf("escaped backslash: %v", cls)
	}
}
