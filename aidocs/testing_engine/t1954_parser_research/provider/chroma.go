package provider

import (
	"fmt"
	"strings"

	"github.com/alecthomas/chroma/v2"
	"github.com/alecthomas/chroma/v2/lexers"
)

func init() { register("chroma", func() (Provider, error) { return Chroma{}, nil }) }

// Chroma is github.com/alecthomas/chroma/v2 (pure-Go regex-state-machine
// highlighter, a Pygments port) as a provider for every research language.
// TSX has no lexer of its own: Chroma's TypeScript lexer claims *.tsx.
type Chroma struct{}

var chromaLexer = map[string]string{
	"bash": "bash", "python": "python", "go": "go", "kotlin": "kotlin",
	"typescript": "typescript", "tsx": "tsx", "javascript": "javascript",
	"java": "java", "rust": "rust", "swift": "swift",
}

func (Chroma) Name() string { return "chroma" }
func (Chroma) Langs() []string {
	return []string{"bash", "python", "go", "kotlin", "typescript", "tsx", "javascript", "java", "rust", "swift"}
}

// Caps: Chroma emits an Error token for input no rule matches (Errors), and
// is a total tokeniser (FullCover — Layer 1 enforces the partition on every
// input). It determines no placement anchor and no Python docstring.
func (Chroma) Caps(string) Capabilities {
	return Capabilities{TokenRanges: true, FullCover: true, Errors: true}
}

// Analyze tokenises src with the language's lexer. EnsureLF is off (its
// default rewrites CRLF to LF, which would move every later offset).
// Chroma lexes runes, so the input must be strict UTF-8 (BOM stripped and
// re-added as an offset base); anything else is refused, never guessed.
func (Chroma) Analyze(lang string, src []byte) (Result, error) {
	l := lexers.Get(chromaLexer[lang])
	if l == nil {
		return Result{}, fmt.Errorf("chroma: no lexer for %s", lang)
	}
	body, base, err := StrictUTF8(src)
	if err != nil {
		return Result{}, err
	}
	it, err := l.Tokenise(&chroma.TokeniseOptions{State: "root"}, string(body))
	if err != nil {
		return Result{}, fmt.Errorf("chroma: %w", err)
	}
	var toks []hlTok
	pos := base
	for t := it(); t != chroma.EOF; t = it() {
		if t.Value == "" {
			continue
		}
		toks = append(toks, hlTok{RawToken: RawToken{Start: pos, End: pos + len(t.Value), Text: []byte(t.Value), Type: t.Type.String()},
			Class: chromaClass(t), Err: t.Type == chroma.Error})
		pos += len(t.Value)
	}
	// EnsureNL (the TypeScript, JavaScript and Rust lexers' config) appends
	// "\n" to an input without one: a documented library normalisation, not
	// an adapter offset error, so that one byte is trimmed back off.
	if n := len(toks); n > 0 && pos == len(src)+1 && !strings.HasSuffix(string(src), "\n") && strings.HasSuffix(string(toks[n-1].Text), "\n") {
		last := &toks[n-1]
		last.End--
		last.Text = last.Text[:len(last.Text)-1]
		if last.Start == last.End {
			toks = toks[:n-1]
		}
	}
	return hlResult("chroma", src, toks)
}

func chromaClass(t chroma.Token) TokClass {
	switch {
	case t.Type == chroma.LiteralStringInterpol:
		return interpClass(t.Value)
	case t.Type == chroma.LiteralStringHeredoc:
		return THeredoc
	case t.Type.InSubCategory(chroma.LiteralString):
		return TString
	case t.Type == chroma.CommentSingle || t.Type == chroma.CommentHashbang:
		return TLineComment
	case t.Type == chroma.CommentMultiline:
		return TBlockComment // a fragment (" outer ", "\n") is block by its type, never by its text
	case t.Type.InCategory(chroma.Comment):
		return commentClass(t.Value)
	}
	return TCode
}
