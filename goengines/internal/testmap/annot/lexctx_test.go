package annot

import (
	"strings"
	"testing"
)

// classes renders a Context as one rune per line: c Code, # Comment,
// L Literal.
func classes(c Context) string {
	var b strings.Builder
	for _, k := range c.Class {
		b.WriteByte("c#L"[k])
	}
	return b.String()
}

const look = "# testmap:covers x @2026-01-01/0123456789"

type lexCase struct {
	name, src, want string
	uncertain       int // expected Uncertain line, 0 = certain
}

func runLex(t *testing.T, l Lang, cases []lexCase) {
	t.Helper()
	for _, tc := range cases {
		c := Classify(l, []byte(tc.src))
		got := classes(c)
		u := 0
		if c.Uncertain != nil {
			u = c.Uncertain.Line
		}
		if u != tc.uncertain || (tc.uncertain == 0 && got != tc.want) {
			t.Errorf("%s/%s: classes %q uncertain %+v, want %q uncertain line %d",
				l.Name, tc.name, got, c.Uncertain, tc.want, tc.uncertain)
		}
	}
}

func TestClassifyBash(t *testing.T) {
	runLex(t, Bash, []lexCase{
		{"plain", "#!/bin/bash\n# testmap:covers a\necho hi\n", "##c", 0},
		{"heredoc", "cat <<EOF\n" + look + "\nEOF\n# real\n", "cLL#", 0},
		{"heredoc-strip-quoted", "cat <<-'EOF'\n\t" + look + "\n\tEOF\n# real\n", "cLL#", 0},
		{"heredoc-partly-quoted", "cat <<\"E\"OF\n" + look + "\nEOF\n# real\n", "cLL#", 0},
		{"heredoc-in-cmdsubst", "x=$(cat <<EOF\n" + look + "\nEOF\n)\n# real\n", "cLLc#", 0},
		// The body starts after the next newline token, not the next line.
		{"delayed-by-continuation", "consume <<EOF \\\nEOF arg\n" + look + "\nEOF\n# real\n", "ccLL#", 0},
		{"delayed-by-spanning-quote", "consume <<EOF \"a\nEOF\nb\"\n" + look + "\nEOF\n# real\n", "cLLLL#", 0},
		{"two-heredocs", "cat <<A <<B\n" + look + "\nA\n" + look + "\nB\n# real\n", "cLLLL#", 0},
		{"double-quote-spanning", "x=\"a\n" + look + "\nb\"\n# real\n", "cLL#", 0},
		{"single-quote-spanning", "x='a\n" + look + "\n'\n# real\n", "cLL#", 0},
		{"dollar-quote-spanning", "x=$'a\\'\n" + look + "\n'\n# real\n", "cLL#", 0},
		{"backtick-spanning", "x=`echo\n" + look + "\n`\n# real\n", "cLL#", 0},
		{"continuation-line-is-code", "echo a \\\n" + look + "\n# real\n", "cc#", 0},
		// No false negatives: these never open anything.
		{"here-string", "cat <<< \"$x\"\n# real\n", "c#", 0},
		{"arith-shift", "echo $(( 1 << 2 ))\n# real\n", "c#", 0},
		{"arith-command", "(( x = 1 << 3 ))\n# real\n", "c#", 0},
		{"param-hash", "echo ${x#y} ${#a[@]} $# a#b\n# real\n", "c#", 0},
		{"case-in-cmdsubst", "x=$(case $y in a) echo 1;; esac)\n# real\n", "c#", 0},
		{"comment-quote", "echo hi # it's\n# real\n", "c#", 0},
		// `$((` closed by a lone ')' was a subshell inside $( … ) (found in
		// tests/test_xdeps_blocking.sh by the repository probe).
		{"cmdsubst-of-subshell", "line=$(( cd \"$D\" && ls 2>&1 ) | grep '^t)' || true)\n# real\n", "c#", 0},
		{"cmdsubst-of-subshell-quoted", "x=\"$(( cd a ) | wc -l)\"\n# real\n", "c#", 0},
		{"double-subshell", "(( cd x ) ; ls )\n# real\n", "c#", 0},
		{"arith-or-subshell-across-lines", "x=$(( cd a\n) )\n", "", 1},
		// An unquoted heredoc body joins backslash-newlines before the
		// delimiter is compared; a quoted one does not (review finding).
		{"heredoc-body-continuation", "cat <<EOF\nprefix\\\nEOF\n" + look + "\nEOF\n# real\n", "cLLLL#", 0},
		{"heredoc-body-escaped-backslash", "cat <<EOF\nprefix\\\\\nEOF\n# real\n", "cLL#", 0},
		{"heredoc-quoted-no-joining", "cat <<'EOF'\nprefix\\\nEOF\n# real\n", "cLL#", 0},
		{"heredoc-strip-continuation", "cat <<-EOF\n\tprefix\\\n\tEOF\n\t" + look + "\n\tEOF\n# real\n", "cLLLL#", 0},
		// ${ … } spans lines as one word (review finding).
		{"param-expansion-spanning", "printf '%s\\n' ${x:-\n" + look + "\n}\n# real\n", "cLL#", 0},
		{"param-expansion-in-quotes", "echo \"${x:-a\n" + look + "\n}\"\n# real\n", "cLL#", 0},
		{"param-expansion-nested", "echo ${x:-${y:-'}'\n" + look + "\n}}\n# real\n", "cLL#", 0},
		{"param-expansion-unterminated", "echo ${x:-\n" + look + "\n", "", 1},
		// Review round 2: literal braces in ${…}, and $'…' / $"…" delimiters.
		{"param-expansion-literal-brace", "printf '%s\\n' ${x:-{}\n# real\n", "c#", 0},
		{"param-expansion-literal-braces", "printf '%s\\n' ${x:-{a}b}\n# real\n", "c#", 0},
		{"heredoc-ansi-c-delimiter", "cat <<$'EOF'\n$EOF\n" + look + "\nEOF\n# real\n", "cLLL#", 0},
		{"heredoc-locale-delimiter", "cat <<$\"EOF\"\n$EOF\n" + look + "\nEOF\n# real\n", "cLLL#", 0},
		{"heredoc-escape-in-quoted-delimiter", "cat <<$'E\\x4fF'\nEOF\n" + look + "\n", "", 1},
		{"heredoc-escape-in-double-quoted", "cat <<\"E\\\"F\"\nx\n", "", 1},
		{"escaped-quote", "echo \\' \\\"\n# real\n", "c#", 0},
		// bash gives a byte-order mark no meaning: U+FEFF'#' is a word.
		{"bom-is-a-word", "\ufeff# header\n# real\n", "c#", 0},
		// Refused, never guessed.
		{"heredoc-in-backticks", "x=`cat <<EOF`\nEOF\n", "", 1},
		{"unterminated-heredoc", "cat <<EOF\n" + look + "\n", "", 1},
		{"unterminated-quote", "x=\"a\n" + look + "\n", "", 1},
	})
}

func TestClassifyPython(t *testing.T) {
	runLex(t, Python, []lexCase{
		{"docstring", "\"\"\"Doc.\n\ntestmap:covers a.py\n\"\"\"\n# testmap:covers b.py\nimport os\n", "cLLL#c", 0},
		{"string-not-docstring", "import os\nX = \"\"\"\n" + look + "\n\"\"\"\n# real\n", "ccLL#", 0},
		{"raw-triple", "X = r'''\\\n" + look + "\n'''\n# real\n", "cLL#", 0},
		{"fstring-nested", "X = f\"\"\"{d[\"k\"]}\n" + look + "\n{y:>{w}}\"\"\"\n# real\n", "cLL#", 0},
		{"brackets", "x = [\n    1,  # inside\n    # real\n]\n", "cc#c", 0},
		{"hash-in-string", "x = '#'\ny = \"\"\"a\"\"\"\n# real\n", "cc#", 0},
		{"continuation", "x = 1 + \\\n" + look + "\n", "cc", 0},
		{"unterminated", "X = \"\"\"\n" + look + "\n", "", 1},
		// CPython skips a byte-order mark at the start of the file.
		{"bom-comment", "\ufeff# c\nimport os\n", "#c", 0},
	})
	// The module docstring is the first statement when it is made of string
	// literals only — as ast.get_docstring decides (verified with CPython).
	docs := []struct {
		src        string
		first, end int    // literal line extent, 0 = no docstring
		content    string // the text of the first literal on its first line
	}{
		{"#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n'''Doc'''\nimport x\n", 3, 3, "Doc"},
		{"(\"\"\"testmap:covers src/a.sh\"\"\")\n", 1, 1, "testmap:covers src/a.sh"},
		{"\"\"\"testmap:covers src/a.sh\"\"\"; x = 1\n", 1, 1, "testmap:covers src/a.sh"},
		{"\"a\" \"b\"\nimport x\n", 1, 1, "a"},
		{"(\n  \"\"\"multi\ntestmap:covers a\"\"\"\n)\n", 2, 3, "multi"},
		{"import x\n\"\"\"not a docstring\"\"\"\n", 0, 0, ""},
		{"b\"\"\"bytes\"\"\"\n", 0, 0, ""},
		{"f\"\"\"f-string\"\"\"\n", 0, 0, ""},
		{"\"a\" + x\n", 0, 0, ""},
		{"[\"a\"]\n", 0, 0, ""},
		// The t1954 corpus case python/bom_doc.py.
		{"\ufeff\"\"\"Doc after a BOM.\n\ntestmap:covers src/bom_doc.py\n\"\"\"\nprint(\"bom\")\n", 1, 4, "Doc after a BOM."},
	}
	for _, d := range docs {
		c := Classify(Python, []byte(d.src))
		first, end, content := 0, 0, ""
		if len(c.Docs) > 0 {
			first, end = c.Docs[0].StartLine, c.Docs[len(c.Docs)-1].EndLine
			content = docSegments(strings.Split(d.src, "\n")[first-1], first, c)[0]
		}
		if first != d.first || end != d.end || content != d.content {
			t.Errorf("%q: docstring %d-%d %q, want %d-%d %q", d.src, first, end, content, d.first, d.end, d.content)
		}
	}
}

// The t1954 corpus cases kotlin/multidollar_*.kt
// (aidocs/testing_engine/t1954_parser_research/corpus/kotlin/): Kotlin 2.2
// multi-dollar strings, where only a $-run as long as the prefix starts a
// template. kotlinc compiles all four; each reads one record, the comment
// outside every string.
const (
	ktDollarDesync = `package app

// testmap:covers app/real.kt
fun f() {
    val s = $$"""${/*"""
    // */
}
val t = """
// testmap:covers app/fake.kt
"""
val u = """x"""
// """
`
	ktDollarInterpolation = `package app

val x = 1
val s = $$"""$${x} ${not a template} // testmap:covers app/fake.kt"""
val r = $$"${"
// testmap:covers app/real.kt
fun h() = "}"
`
	ktDollarLiteralBrace = `package app

val s = $$"""${
// testmap:covers app/fake.kt
}"""

// testmap:covers app/real.kt
fun f() = 1
`
	ktDollarQuoteBoundary = `package app

val a = $$"""${"""
val b = """
// testmap:covers app/fake.kt
"""
val c = """
}"""
// testmap:covers app/real.kt
fun k() = 3
`
)

func TestClassifyKotlin(t *testing.T) {
	kl := strings.Replace(look, "#", "//", 1)
	runLex(t, Kotlin, []lexCase{
		{"plain", "package a\nimport b.C\n// testmap:covers x\nclass T\n", "cc#c", 0},
		{"raw", "val s = \"\"\"\n" + kl + "\n${\"\\\"\\\"\\\"\"}\n\"\"\"\"\"\n// real\n", "cLLL#", 0},
		{"block-nested", "/* a /* b */\n" + kl + "\n*/\n// real\n", "cLL#", 0},
		{"slashes-in-string", "val s = \"//\" + '\"'\n// real\n", "c#", 0},
		{"template-string", "val s = \"${f(\"}\")}\"\n// real\n", "c#", 0},
		{"unterminated-raw", "val s = \"\"\"\n" + kl + "\n", "", 1},
		// kotlinc skips a byte-order mark at the start of the file.
		{"bom-comment", "\ufeff" + kl + "\nclass T\n", "#c", 0},
		// Multi-dollar strings: a template needs a $-run at least as long as
		// the prefix; a shorter one is text.
		{"multidollar-comment-desync", ktDollarDesync, "cc#cc#ccLLc#", 0},
		{"multidollar-interpolation", ktDollarInterpolation, "ccccc#c", 0},
		{"multidollar-literal-brace", ktDollarLiteralBrace, "cccLLc#c", 0},
		{"multidollar-quote-boundary", ktDollarQuoteBoundary, "ccccLLcL#c", 0},
		{"dollar-prefix-3", "val s = $$$\"\"\"$${/*\"\"\"\n// real\n", "c#", 0},
		// A longer run opens one: its last two dollars start the template.
		{"dollar-run-longer", "val s = $$\"\"\"$$${\"\"\"\n" + kl + "\n\"\"\"}\"\"\"\n// real\n", "cLL#", 0},
		{"dollar-run-before-close", "val s = $$\"\"\"a$$\"\"\"\n// real\n", "c#", 0},
		// Each string keeps its own prefix across nested templates.
		{"dollar-inside-template", "val s = \"${ $$\"${\" }\"\n// real\n", "c#", 0},
		{"dollar-prefix-restored", "val s = $$\"\"\"$${ \"${x}\" }${/*\"\"\"\n// real\n", "c#", 0},
		// $`name` is a short template: the backticked name may hold quotes.
		{"short-template-backticks", "val s = \"$`x\"/*`\"\n// real\n", "c#", 0},
		{"short-template-backticks-dollar", "val s = $$\"$$`x\"/*`\"\n// real\n", "c#", 0},
		{"short-template-below-prefix", "val s = $$\"$`x\" + 1 + '`'\n// real\n", "c#", 0},
		{"short-template-unclosed-backtick", "val s = \"$`x\"\n// real\n", "c#", 0},
	})
	c := Classify(Kotlin, []byte("package a\n\nimport b.C\nimport d.E\n\nclass T {\n  import x\n}\n"))
	if c.Package != 1 || c.Import != 4 {
		t.Errorf("package %d import %d", c.Package, c.Import)
	}
	if c := Classify(Kotlin, []byte("\ufeffpackage a\n\nclass T\n")); c.Package != 1 {
		t.Errorf("package after a byte-order mark: line %d", c.Package)
	}
}

func TestClassifyGo(t *testing.T) {
	gl := strings.Replace(look, "#", "//", 1)
	runLex(t, Go, []lexCase{
		{"plain", "package a\n\n// testmap:covers x\nfunc f() {} // trailing\n", "cc#c", 0},
		{"raw-string", "package a\n\nvar s = `\n" + gl + "\n`\n// real\n", "cccLL#", 0},
		{"block", "package a\n/*\n" + gl + "\n*/\n// real\n", "ccLL#", 0},
		{"unterminated-raw", "package a\nvar s = `\n" + gl + "\n", "", 2},
		// gc skips a byte-order mark at the start of the file.
		{"bom-comment", "\ufeff" + gl + "\npackage a\n", "#c", 0},
	})
	if c := Classify(Go, []byte("//go:build x\n\n// Package a.\npackage a\n")); c.Package != 4 {
		t.Errorf("package line %d", c.Package)
	}
	if c := Classify(Go, []byte("\ufeffpackage a\n")); c.Package != 1 {
		t.Errorf("package after a byte-order mark: line %d", c.Package)
	}
}
