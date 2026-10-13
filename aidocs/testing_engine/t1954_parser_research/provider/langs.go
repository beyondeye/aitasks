package provider

import (
	"path"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

// The research languages: `//` leader, no docstring. annot knows them only
// through the seam's LangHook (ResearchLangOf), installed in the harness
// process alone. TSX is its own Lang because a provider sees only the Lang,
// never the path, and TypeScript and TSX are different grammars (`<T>x` is a
// type assertion in .ts and a JSX element in .tsx).
var (
	TypeScript = annot.Lang{Name: "typescript", Leader: "//"}
	TSX        = annot.Lang{Name: "tsx", Leader: "//"}
	JavaScript = annot.Lang{Name: "javascript", Leader: "//"}
	Java       = annot.Lang{Name: "java", Leader: "//"}
	Rust       = annot.Lang{Name: "rust", Leader: "//"}
	Swift      = annot.Lang{Name: "swift", Leader: "//"}
)

// M22Langs are the languages annot lexes itself; ResearchLangs reach annot
// only through the seam.
var (
	M22Langs      = []string{"bash", "python", "go", "kotlin"}
	ResearchLangs = []string{"typescript", "tsx", "javascript", "java", "rust", "swift"}
	AllLangs      = append(append([]string(nil), M22Langs...), ResearchLangs...)
)

var researchExt = map[string]annot.Lang{
	".ts": TypeScript, ".mts": TypeScript, ".tsx": TSX,
	".js": JavaScript, ".jsx": JavaScript, ".mjs": JavaScript,
	".java":  Java,
	".rs":    Rust,
	".swift": Swift,
}

var byName = map[string]annot.Lang{
	annot.Bash.Name: annot.Bash, annot.Python.Name: annot.Python,
	annot.Go.Name: annot.Go, annot.Kotlin.Name: annot.Kotlin,
	TypeScript.Name: TypeScript, TSX.Name: TSX, JavaScript.Name: JavaScript,
	Java.Name: Java, Rust.Name: Rust, Swift.Name: Swift,
}

// LangByName returns a language by its annot name.
func LangByName(name string) (annot.Lang, bool) {
	l, ok := byName[name]
	return l, ok
}

// IsResearch reports whether lang is one of the research languages.
func IsResearch(lang string) bool {
	_, ok := researchExt["."+map[string]string{
		"typescript": "ts", "tsx": "tsx", "javascript": "js", "java": "java", "rust": "rs", "swift": "swift",
	}[lang]]
	return ok
}

// ResearchLangOf is the LangHook: it maps only the research extensions and
// declines everything else, so the four M2.2 languages always take annot's
// landed LangOf path.
func ResearchLangOf(p string, _ []byte) (annot.Lang, bool) {
	l, ok := researchExt[path.Ext(p)]
	return l, ok
}

// LangOfPath is the language of a path for the harness: research extensions
// first, then annot's own LangOf.
func LangOfPath(p string, data []byte) (annot.Lang, bool) {
	if l, ok := ResearchLangOf(p, data); ok {
		return l, true
	}
	return annot.LangOf(p, data)
}
