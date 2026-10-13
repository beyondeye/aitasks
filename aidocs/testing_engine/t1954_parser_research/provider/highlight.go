package provider

import (
	"fmt"
	"strings"
)

// Shared mapping for the TOTAL tokenisers (Chroma, Pygments, TextMate):
// every input byte is some token, so Layer 1 requires an exact partition,
// and Layer 2 coalesces their fragments into construct-level spans.

// hlTok is a validated raw token with the role its tool type maps to.
type hlTok struct {
	RawToken
	Class TokClass
	Err   bool // the tool's error token
}

// interpClass classifies a string-interpolation delimiter token by its text:
// `${`, `#{`, `{`, `\(` open; `}` and `)` close; anything else is string data.
func interpClass(text string) TokClass {
	switch {
	case strings.HasSuffix(text, "{") || strings.HasSuffix(text, "("):
		return TInterpOpen
	case text == "}" || text == ")":
		return TInterpClose
	}
	return TString
}

// commentClass maps a comment token whose TYPE does not say line or block
// (Comment, Comment.Special, Comment.Preproc) by its text: one that opens
// with `/*` is a block comment, anything else (`//`, `#`, `///`, `//!`, a
// shebang) a line comment. Multiline fragments never come here — a fragment
// such as " outer " inside /* … */ is block by its type (an early adapter
// version classified it by text: the range metric caught it, t1954_3).
func commentClass(text string) TokClass {
	if strings.HasPrefix(text, "/*") {
		return TBlockComment
	}
	return TLineComment
}

// hlResult validates a total tokeniser's tokens and builds the Result:
// error tokens become Diags, Spans are the coalesced constructs, Leaves the
// raw tokens.
func hlResult(tool string, src []byte, toks []hlTok) (Result, error) {
	var res Result
	raws := make([]RawToken, len(toks))
	ctoks := make([]CTok, len(toks))
	for i, t := range toks {
		raws[i] = t.RawToken
		ctoks[i] = CTok{t.Start, t.End, t.Class}
		if t.Err {
			res.Diags = append(res.Diags, Diag{t.Start, t.End, fmt.Sprintf("%s error token %q", tool, clip(t.Text))})
		}
	}
	if _, err := ValidateTokens(src, raws, res.Diags, GapPolicy{Total: true}); err != nil {
		return Result{}, err
	}
	res.Spans = Coalesce(src, ctoks)
	res.Leaves = LeavesOf(raws)
	if res.Leaves != nil && len(src) >= len(BOM) && string(src[:len(BOM)]) == string(BOM) && (len(raws) == 0 || raws[0].Start > 0) {
		// A BOM the tool never saw is a leaf of its own, so the leaves still
		// partition the original bytes.
		res.Leaves = append([]Span{{0, len(BOM), Other}}, res.Leaves...)
	}
	return res, nil
}
