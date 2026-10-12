// Package annot is the `testmap:` annotation grammar (v3) and its line-targeted
// rewriter: the parser `scan` reads test files with, the stamp format
// `@<date>/<blob10>`, and the only writer of `testmap:` lines — `annotate`,
// `verify` and every later adopter (`stale --confirm*`, `onboard adopt`,
// `--agent-verdicts`, `--author`) write through Apply.
//
// Annotations live on comment lines only (Invariant 6). A line is a comment
// line when the language's lexer (lexctx.go) proves it starts in code context
// with the comment leader — never by its text alone, so an annotation-shaped
// line inside a heredoc, a string or a raw string is data, never read and
// never written. A Python module docstring is read, never written.
//
// Later submodules land here as named extensions: M2.3 the `annotate
// --suggest` / `--from-body` arms, M7.4 `annotate --author`, M2.6 the
// post-re-stamp hook (hook.go).
package annot

import (
	"bytes"
	"path"
	"strings"
)

// Lang is a language the grammar knows: its comment leader, and whether its
// module docstring is read.
type Lang struct {
	Name      string
	Leader    string
	Docstring bool
}

var (
	Bash   = Lang{Name: "bash", Leader: "#"}
	Python = Lang{Name: "python", Leader: "#", Docstring: true}
	Go     = Lang{Name: "go", Leader: "//"}
	Kotlin = Lang{Name: "kotlin", Leader: "//"}
)

var byExt = map[string]Lang{
	".sh": Bash, ".bash": Bash,
	".py": Python,
	".go": Go,
	".kt": Kotlin, ".kts": Kotlin,
}

// LangOf returns the language of a file: by extension, or — for a file with
// no extension — by its shebang (`sh` / `bash` / `python`). A file of any
// other kind has no comment leader the grammar knows.
func LangOf(p string, data []byte) (Lang, bool) {
	ext := path.Ext(p)
	if l, ok := byExt[ext]; ok {
		return l, true
	}
	if ext != "" || !bytes.HasPrefix(data, []byte("#!")) {
		return Lang{}, false
	}
	first, _, _ := bytes.Cut(data, []byte("\n"))
	fields := strings.Fields(strings.TrimPrefix(string(first), "#!"))
	if len(fields) == 0 {
		return Lang{}, false
	}
	interp := path.Base(fields[0])
	if interp == "env" {
		for _, f := range fields[1:] {
			if !strings.HasPrefix(f, "-") {
				interp = f
				break
			}
		}
	}
	switch {
	case interp == "sh" || interp == "bash":
		return Bash, true
	case strings.HasPrefix(interp, "python"):
		return Python, true
	}
	return Lang{}, false
}
