package provider

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
)

func init() { register("textmate", func() (Provider, error) { return NewTextMate() }) }

// TextMate is the regex-state TextMate grammar engine (vscode-textmate +
// vscode-oniguruma, the grammars of shiki's tm-grammars package) as a
// provider, via oracle/textmate_oracle.js — the engine behind VS Code and
// shiki highlighting, and the stand-in for the regex-highlighter class
// (highlight.js, Prism). It has no error model, so Errors is not declared
// and every write scores unsupported:Errors; the lexical and record levels
// are measured.
type TextMate struct {
	p       *jsonProc
	Version string
}

// NewTextMate starts node with NODE_PATH=$T1954_TM_NODE_MODULES.
func NewTextMate() (*TextMate, error) {
	nm := os.Getenv("T1954_TM_NODE_MODULES")
	if nm == "" {
		return nil, errors.New("textmate: T1954_TM_NODE_MODULES not set (vscode-textmate, vscode-oniguruma, tm-grammars)")
	}
	p, err := startJSONProc("textmate", []string{"NODE_PATH=" + nm}, "node", filepath.Join("oracle", "textmate_oracle.js"))
	if err != nil {
		return nil, err
	}
	var v struct{ Version, Error string }
	if err := p.call(map[string]any{"version": true}, &v); err != nil || v.Version == "" {
		p.Close()
		return nil, errors.New("textmate: helper did not start: " + v.Error)
	}
	return &TextMate{p: p, Version: v.Version}, nil
}

// Close stops node.
func (t *TextMate) Close() error { return t.p.Close() }

func (*TextMate) Name() string { return "textmate" }
func (*TextMate) Langs() []string {
	return []string{"bash", "python", "go", "kotlin", "typescript", "tsx", "javascript", "java", "rust", "swift"}
}

// Caps: exact ranges and a total tokenisation (with explicit line-break
// tokens); no Errors, no anchors, no docstrings.
func (*TextMate) Caps(string) Capabilities { return Capabilities{TokenRanges: true, FullCover: true} }

// Analyze tokenises the BOM-stripped UTF-8 body.
func (t *TextMate) Analyze(lang string, src []byte) (Result, error) {
	body, base, err := StrictUTF8(src)
	if err != nil {
		return Result{}, err
	}
	var r struct {
		Tokens []wireToken
		Error  string
	}
	if err := t.p.call(map[string]string{"lang": lang, "src": b64(body)}, &r); err != nil {
		return Result{}, err
	}
	if r.Error != "" {
		return Result{}, errors.New("textmate: " + r.Error)
	}
	toks := make([]hlTok, 0, len(r.Tokens))
	for _, w := range r.Tokens {
		tk, err := w.raw()
		if err != nil {
			return Result{}, err
		}
		tk.Start += base
		tk.End += base
		toks = append(toks, hlTok{RawToken: tk, Class: tmClass(tk.Type)})
	}
	return hlResult("textmate", src, toks)
}

func tmClass(c string) TokClass {
	switch strings.TrimPrefix(c, "eol:") {
	case "string":
		return TString
	case "comment.line":
		return TLineComment
	case "comment.block":
		return TBlockComment
	}
	return TCode
}
