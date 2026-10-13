package provider

import (
	"errors"
	"path/filepath"
	"strings"
)

func init() { register("pygments", func() (Provider, error) { return NewPygments() }) }

// Pygments is the Pygments highlighter (Python) as a provider, run as one
// long-lived subprocess (oracle/pygments_oracle.py). The helper decodes the
// bytes the way the language does and returns original-source byte offsets
// plus each token's original-codec text (the t1954_3 position contract).
type Pygments struct {
	p       *jsonProc
	Version string
}

// NewPygments starts the helper with T1954_PYGMENTS_PYTHON (a venv holding
// the pinned Pygments), else T1954_PYTHON, else python3.
func NewPygments() (*Pygments, error) {
	py := envOr("T1954_PYGMENTS_PYTHON", "T1954_PYTHON", "python3")
	p, err := startJSONProc("pygments", nil, py, filepath.Join("oracle", "pygments_oracle.py"))
	if err != nil {
		return nil, err
	}
	g := &Pygments{p: p}
	var v struct {
		Version string
		Error   string
	}
	if err := p.call(map[string]any{"version": true}, &v); err != nil {
		p.Close()
		return nil, err
	}
	if v.Version == "" {
		p.Close()
		return nil, errors.New("pygments: helper did not report a version (is Pygments importable?) " + v.Error)
	}
	g.Version = v.Version
	return g, nil
}

// Close stops the helper.
func (g *Pygments) Close() error { return g.p.Close() }

func (*Pygments) Name() string { return "pygments" }
func (*Pygments) Langs() []string {
	return []string{"bash", "python", "go", "kotlin", "typescript", "tsx", "javascript", "java", "rust", "swift"}
}

// Caps: Token.Error for unmatched input (Errors); a total tokeniser
// (FullCover, enforced per input by Layer 1). String.Doc has no statement
// model, so DocLiterals is not declared (findings: --doccheck).
func (*Pygments) Caps(string) Capabilities {
	return Capabilities{TokenRanges: true, FullCover: true, Errors: true}
}

// Analyze lexes src through the helper.
func (g *Pygments) Analyze(lang string, src []byte) (Result, error) {
	var r struct {
		Tokens      []wireToken
		Unsupported string
		Error       string
	}
	if err := g.p.call(map[string]string{"src": b64(src), "lang": lang}, &r); err != nil {
		return Result{}, err
	}
	if r.Unsupported != "" {
		return Result{}, &UnsupportedCapabilityError{Missing: []string{r.Unsupported}}
	}
	if r.Error != "" {
		return Result{}, errors.New("pygments: " + r.Error)
	}
	toks := make([]hlTok, 0, len(r.Tokens))
	for _, w := range r.Tokens {
		t, err := w.raw()
		if err != nil {
			return Result{}, err
		}
		toks = append(toks, hlTok{RawToken: t, Class: pygClassOf(t), Err: t.Type == "Token.Error"})
	}
	return hlResult("pygments", src, toks)
}

func pygClassOf(t RawToken) TokClass {
	switch typ := t.Type; {
	case typ == "Token.Literal.String.Interpol":
		return interpClass(string(t.Text))
	case typ == "Token.Literal.String.Heredoc":
		return THeredoc
	case strings.HasPrefix(typ, "Token.Literal.String"):
		return TString
	case typ == "Token.Comment.Single" || typ == "Token.Comment.Hashbang":
		return TLineComment
	case typ == "Token.Comment.Multiline":
		return TBlockComment // a fragment (" outer ", "\n") is block by its type, never by its text
	case strings.HasPrefix(typ, "Token.Comment"):
		return commentClass(string(t.Text))
	}
	return TCode
}
