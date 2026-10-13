package provider

import (
	"errors"
	"os"
	"path/filepath"
)

func init() { register("tsnative", func() (Provider, error) { return NewTSNative() }) }

// TSNative is the TypeScript compiler's own parser (typescript 5.9.3 via
// oracle/ts_oracle.js in "provider" mode) as a provider for TypeScript, TSX
// and JavaScript — the "established parser for an additional target
// language" on the same footing as pytokenize. It SHARES its extraction with
// the ts-parser oracle (SharesOracle), so its range column is
// self-consistency; its independent evidence is the hand oracles.
type TSNative struct{ p *jsonProc }

// NewTSNative starts node with NODE_PATH=$T1954_TS_NODE_MODULES.
func NewTSNative() (*TSNative, error) {
	nm := os.Getenv("T1954_TS_NODE_MODULES")
	if nm == "" {
		return nil, errors.New("tsnative: T1954_TS_NODE_MODULES not set (no typescript installed)")
	}
	if _, err := os.Stat(filepath.Join(nm, "typescript", "package.json")); err != nil {
		return nil, errors.New("tsnative: typescript not installed in " + nm)
	}
	p, err := startJSONProc("tsnative", []string{"NODE_PATH=" + nm}, "node", filepath.Join("oracle", "ts_oracle.js"), "--serve")
	if err != nil {
		return nil, err
	}
	return &TSNative{p: p}, nil
}

// Close stops node.
func (t *TSNative) Close() error { return t.p.Close() }

func (*TSNative) Name() string         { return "tsnative" }
func (*TSNative) Langs() []string      { return []string{"typescript", "tsx", "javascript"} }
func (*TSNative) SharesOracle() string { return "ts-parser" }

// Caps: exact ranges, syntactic diagnostics (Errors), and the two anchors
// the proposed TS/JS placement rule reads, determined from the AST.
func (*TSNative) Caps(string) Capabilities {
	return Capabilities{TokenRanges: true, Errors: true, Anchors: AImportEnd | APrologue}
}

var tsScriptName = map[string]string{"typescript": "input.ts", "tsx": "input.tsx", "javascript": "input.js"}

// Analyze parses src. The script kind comes from the Lang (a provider never
// sees the path): .jsx files are the javascript Lang, which TypeScript also
// parses with JSX enabled.
func (t *TSNative) Analyze(lang string, src []byte) (Result, error) {
	if _, _, err := StrictUTF8(src); err != nil {
		return Result{}, err // node would decode invalid bytes to U+FFFD and move every offset
	}
	var r struct {
		Comments []wireToken
		Literals []wireToken
		Diags    [][2]any
		Anchors  struct{ ImportEnd, Prologue int }
		Error    string
	}
	if err := t.p.call(map[string]string{"name": tsScriptName[lang], "mode": "provider", "src": b64(src)}, &r); err != nil {
		return Result{}, err
	}
	if r.Error != "" {
		return Result{}, errors.New("tsnative: " + r.Error)
	}
	var res Result
	var all []RawToken
	for _, group := range [][]wireToken{r.Comments, r.Literals} {
		for _, w := range group {
			tk, err := w.raw()
			if err != nil {
				return Result{}, err
			}
			all = append(all, tk)
			kind := String
			switch tk.Type {
			case "line":
				kind = LineComment
			case "block":
				kind = BlockComment
			}
			res.Spans = append(res.Spans, Span{tk.Start, tk.End, kind})
		}
	}
	if err := ValidateSpanTexts(src, all); err != nil {
		return Result{}, err
	}
	SortSpans(res.Spans)
	for _, d := range r.Diags {
		at := num(d[0])
		msg, _ := d[1].(string)
		res.Diags = append(res.Diags, Diag{at, at, msg})
	}
	res.Anchors = Anchors{ImportEnd: r.Anchors.ImportEnd, Prologue: r.Anchors.Prologue}
	return res, nil
}
