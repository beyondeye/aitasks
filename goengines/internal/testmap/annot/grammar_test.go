package annot

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

var update = flag.Bool("update", false, "rewrite the golden files")

// golden compares got with testdata/<name>, or rewrites it under -update.
func golden(t *testing.T, name string, got []byte) {
	t.Helper()
	p := filepath.Join("testdata", name)
	if *update {
		if err := os.WriteFile(p, got, 0o644); err != nil {
			t.Fatal(err)
		}
		return
	}
	want, err := os.ReadFile(p)
	if err != nil {
		t.Fatalf("%s: %v (run with -update)", p, err)
	}
	if string(got) != string(want) {
		t.Errorf("%s differs:\n--- got\n%s\n--- want\n%s", p, got, want)
	}
}

// Every testdata/parse/<name>.<ext>.in parses, as <name>.<ext>, to the units
// pinned in <name>.<ext>.golden. The .in suffix keeps the fixtures out of
// every language table, so no scan ever reads them as test files.
func TestParseGoldens(t *testing.T) {
	ins, _ := filepath.Glob("testdata/parse/*.in")
	if len(ins) == 0 {
		t.Fatal("no fixtures")
	}
	for _, in := range ins {
		data, err := os.ReadFile(in)
		if err != nil {
			t.Fatal(err)
		}
		name := strings.TrimSuffix(filepath.Base(in), ".in")
		f, err := ParseFile("tests/"+name, data)
		if err != nil {
			t.Errorf("%s: %v", name, err)
			continue
		}
		out, _ := json.MarshalIndent(f.Units, "", "  ")
		golden(t, "parse/"+name+".golden", append(out, '\n'))
	}
}

func coverSources(f *File) []string {
	var out []string
	for _, u := range f.Units {
		for _, c := range u.Covers {
			out = append(out, u.Member+":"+c.Source)
		}
	}
	return out
}

// Only real comment lines are read: annotation-shaped lines in heredoc
// bodies (including one delayed past a continuation), strings, raw strings
// and block comments are data — even a malformed key there is not an error.
func TestLookalikesAreNeverRead(t *testing.T) {
	want := map[string]string{
		"lookalikes.sh": ":src/real.sh,:src/real2.sh",
		"lookalikes.py": ":src/real.py,:src/real2.py",
		"lookalikes.kt": ":src/Real.kt,:src/Real2.kt",
		"lookalikes.go": ":src/real.go,:src/real2.go",
	}
	for name, w := range want {
		data, err := os.ReadFile("testdata/parse/" + name + ".in")
		if err != nil {
			t.Fatal(err)
		}
		f, err := ParseFile("tests/"+name, data)
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		if got := strings.Join(coverSources(f), ","); got != w {
			t.Errorf("%s: read %s, want %s", name, got, w)
		}
	}
}

// A Kotlin script header is a comment: a /* in it no longer makes the file
// uncertain, so its annotations are read, under CRLF too. A lone CR is a
// line break to kotlinc but not here: the file is refused, never misread.
func TestKotlinShebangAnnotations(t *testing.T) {
	const lf = "#!/usr/bin/env -S kotlin -cp lib/*\npackage p\nimport q.R\n// testmap:covers src/a.kt\nclass T\n"
	for name, src := range map[string]string{"lf": lf, "crlf": strings.ReplaceAll(lf, "\n", "\r\n")} {
		f, err := ParseFile("tests/S.kts", []byte(src))
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		if got := strings.Join(coverSources(f), ","); got != ":src/a.kt" {
			t.Errorf("%s: read %s", name, got)
		}
	}
	f, err := ParseFile("tests/S.kts", []byte(strings.ReplaceAll(lf, "\n", "\r")))
	var se *SyntaxError
	if !errors.As(err, &se) || !strings.Contains(se.Reason, "lone carriage return") {
		t.Errorf("lone CR: file %v error %v, want a lone carriage return SyntaxError", f, err)
	}
}

func TestParseDocstringAndBlocks(t *testing.T) {
	data, _ := os.ReadFile("testdata/parse/python_docstring.py.in")
	f, err := ParseFile("tests/test_x.py", data)
	if err != nil {
		t.Fatal(err)
	}
	if len(f.Units) != 2 || f.Units[1].Member != "TestA" {
		t.Fatalf("units %+v", f.Units)
	}
	c := f.Units[0].Covers
	if len(c) != 2 || !c[0].Line.Docstring || c[0].Stamp.Blob != "0123456789" || c[1].Line.Docstring {
		t.Fatalf("file-level covers %+v", c)
	}
	if f.Units[0].Last != 8 { // the last *comment* annotation; the docstring is never an anchor
		t.Errorf("last %d", f.Units[0].Last)
	}
	// Python decides what a docstring is (review finding): a parenthesized
	// literal and one followed by `; x = 1` are both read.
	for _, src := range []string{"(\"\"\"testmap:covers src/a.sh\"\"\")\n", "\"\"\"testmap:covers src/a.sh\"\"\"; x = 1\n",
		"(\n    \"\"\"Doc.\n    testmap:covers src/a.sh\n    \"\"\"\n)\n"} {
		f, err := ParseFile("tests/t.py", []byte(src))
		if err != nil || len(f.Units[0].Covers) != 1 || f.Units[0].Covers[0].Source != "src/a.sh" || !f.Units[0].Covers[0].Line.Docstring {
			t.Errorf("%q: %+v %v", src, f, err)
		}
	}
}

// The module docstring is read as its value: literals decoded and
// concatenated, then split into lines (review round 2). Expectations are
// CPython's ast.get_docstring for each source.
func TestDocstringValue(t *testing.T) {
	cases := []struct {
		src, covers string // covers: "<line>:<source>,…", "" for none, "!" for a refusal
	}{
		{"\"testmap:covers \" \"src/a.sh\"\n", "1:src/a.sh"},
		{"\"ordinary prose \" \"testmap:covers src/a.sh\"\n", ""},
		{"\"a\\ntestmap:covers src/b.sh\"\n", "1:src/b.sh"},
		{"r\"a\\ntestmap:covers src/b.sh\"\n", ""},
		{"\"\"\"x\n\"\"\" \"\"\"testmap:covers src/c.sh\"\"\"\n", "2:src/c.sh"},
		{"\"\\x74estmap:covers src/d.sh\"\n", "1:src/d.sh"},
		{"\"\"\"Doc.\ntestmap:covers src/a.sh\\\n more\"\"\"\n", "!"}, // one line: "testmap:covers src/a.sh more"
		{"\"\\N{LATIN SMALL LETTER T}estmap:covers x\"\n", "!"},
		{"\"testmap:covers src/\\N{BULLET}.sh\"\n", "!"},
		{"\"Prints \\N{BULLET} items.\"\n# testmap:covers src/e.sh\n", "2:src/e.sh"},
		// Review round 3: a token split across literals; calls are not
		// grouping; a literal U+FFFD is ordinary text.
		{"\"test\" \"map:covers src/a.sh\"\n", "1:src/a.sh"},
		{"\"testmap:covers src/a.sh\"(\"arg\")\n", ""},
		{"\"testmap:covers src/a.sh\" (\"b\")\n", ""},
		{"((\"testmap:covers src/a.sh\") )\n", "1:src/a.sh"},
		{"\"testmap:covers src/\uFFFD.sh\"\n", "1:src/\uFFFD.sh"},
		// Review round 4: an undecodable escape may be a line break, and the
		// refusal and the parse trim the same (Unicode) whitespace.
		{"\"prose \\N{LINE FEED} testmap:covers src/a.sh\"\n", "!"},
		{"\"\u00a0testmap:covers src/\\N{BULLET}.sh\"\n", "!"},
		{"\"\u00a0testmap:covers src/a.sh\"\n", "1:src/a.sh"},
		{"\"Prints \\N{BULLET} items, \\N{EM DASH} nothing else.\"\n", ""},
		// Multi-byte runes before the annotation (found by the repository probe).
		{"\"\"\"Café — résumé.\ntestmap:covers src/f.sh\n\"\"\"\n", "2:src/f.sh"},
	}
	for _, tc := range cases {
		f, err := ParseFile("tests/t.py", []byte(tc.src))
		if tc.covers == "!" {
			var se *SyntaxError
			if !errors.As(err, &se) {
				t.Errorf("%q: got %v, want a refusal", tc.src, err)
			}
			continue
		}
		if err != nil {
			t.Errorf("%q: %v", tc.src, err)
			continue
		}
		var got []string
		for _, c := range f.Units[0].Covers {
			got = append(got, fmt.Sprintf("%d:%s", c.Line.No, c.Source))
		}
		if strings.Join(got, ",") != tc.covers {
			t.Errorf("%q: covers %v, want %q", tc.src, got, tc.covers)
		}
	}
}

func TestParseErrors(t *testing.T) {
	cases := []struct {
		name, src string
		line      int
		reason    string
	}{
		{"unknown key", "#!/bin/sh\n\n# testmap:frobnicate x\n", 3, "unknown key"},
		{"empty key", "# testmap:\n", 1, "empty key"},
		{"malformed key", "# testmap:Covers x\n", 1, "malformed key"},
		{"key glued", "# testmap:covers:x\n", 1, "malformed key"},
		{"duplicate member", "# testmap:unit A\n# testmap:unit A\n", 2, "duplicate member"},
		{"member with slash", "# testmap:unit a/b\n", 1, "invalid member"},
		{"member with variant", "#!/bin/sh\n# testmap:unit M@v\n", 2, "invalid member"},
		{"member with hash", "# testmap:unit M#x\n", 1, "invalid member"},
		{"duplicate kind", "# testmap:kind unit\n# testmap:kind e2e\n", 2, "duplicate testmap:kind"},
		{"duplicate covers", "# testmap:covers a.sh\n# testmap:covers a.sh @2026-01-01/0123456789\n", 2, "duplicate covers"},
		{"extra token", "# testmap:covers a.sh @2026-01-01/0123456789 extra\n", 1, "path and an optional stamp"},
		{"bad stamp", "# testmap:covers a.sh @2026-01-01/0123456\n", 1, "10 lowercase hex"},
		{"bad stamp date", "# testmap:covers a.sh @2026-13-01/0123456789\n", 1, "bad date"},
		{"bad path", "# testmap:covers ../a.sh\n", 1, "covers"},
		{"bad glob", "# testmap:scope src/[a.sh\n", 1, "invalid glob"},
		{"bad axis", "# testmap:axis locale=ar\n", 1, "axis"},
		{"bad date", "# testmap:reviewed 2026-02-30\n", 1, "bad date"},
		{"bad batch", "# testmap:batch maybe\n", 1, "yes or no"},
		{"uncertain", "cat <<EOF\n# testmap:covers a.sh\n", 1, "cannot determine comment context"},
	}
	for _, tc := range cases {
		_, err := ParseFile("tests/t.sh", []byte(tc.src))
		var se *SyntaxError
		if !errors.As(err, &se) || se.Line != tc.line || !strings.Contains(se.Reason, tc.reason) {
			t.Errorf("%s: got %v, want line %d %q", tc.name, err, tc.line, tc.reason)
		}
	}
	py := "\"\"\"Doc\ntestmap:unit A\n\"\"\"\n"
	if _, err := ParseFile("tests/t.py", []byte(py)); err == nil || !strings.Contains(err.Error(), "docstring") {
		t.Errorf("testmap:unit in a docstring: %v", err)
	}
	if _, err := ParseFile("tests/t.txt", []byte("# testmap:covers a\n")); !errors.Is(err, ErrNoLeader) {
		t.Errorf("unknown language: %v", err)
	}
}

func TestLangOf(t *testing.T) {
	cases := map[string]string{
		"a.sh": "bash", "a.bash": "bash", "a.py": "python", "a.go": "go", "a.kt": "kotlin", "a.kts": "kotlin",
	}
	for p, w := range cases {
		if l, ok := LangOf(p, nil); !ok || l.Name != w {
			t.Errorf("%s: %v %v", p, l, ok)
		}
	}
	for src, w := range map[string]string{
		"#!/usr/bin/env bash\n": "bash", "#!/bin/sh\n": "bash", "#!/usr/bin/env -S python3 -u\n": "python",
	} {
		if l, ok := LangOf("bin/tool", []byte(src)); !ok || l.Name != w {
			t.Errorf("%q: %v %v", src, l, ok)
		}
	}
	for _, p := range []string{"a.txt", "a.md", "Makefile"} {
		if _, ok := LangOf(p, []byte("x\n")); ok {
			t.Errorf("%s has a language", p)
		}
	}
}

func TestStamp(t *testing.T) {
	s, err := ParseStamp("@2026-10-12/0123456789")
	if err != nil || s.String() != "@2026-10-12/0123456789" {
		t.Fatalf("%v %v", s, err)
	}
	for _, bad := range []string{"2026-10-12/0123456789", "@2026-10-12/012345678", "@2026-10-12/01234567890",
		"@2026-10-12/ABCDEF0123", "@2026-10-32/0123456789", "@2026-10-12"} {
		if _, err := ParseStamp(bad); err == nil {
			t.Errorf("%s accepted", bad)
		}
	}
}
