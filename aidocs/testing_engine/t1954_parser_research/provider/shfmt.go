package provider

import (
	"bytes"
	"errors"

	"mvdan.cc/sh/v3/syntax"
)

func init() { register("shfmt", func() (Provider, error) { return Shfmt{}, nil }) }

// Shfmt is mvdan.cc/sh/v3/syntax (the parser behind shfmt) as a bash
// provider: comments, quoted-string literal parts and heredoc bodies with
// byte positions, and the parse error as a Diag.
type Shfmt struct{}

func (Shfmt) Name() string    { return "shfmt" }
func (Shfmt) Langs() []string { return []string{"bash"} }
func (Shfmt) Caps(string) Capabilities {
	return Capabilities{TokenRanges: true, Errors: true}
}

// Analyze parses src as bash. String spans are emitted for single-quoted
// strings and for the literal parts of double-quoted strings (so a line that
// starts inside a "$( … )" in a string is not mistaken for string data); a
// heredoc span covers the body and the terminator line.
func (Shfmt) Analyze(_ string, src []byte) (Result, error) {
	var res Result
	f, err := syntax.NewParser(syntax.KeepComments(true), syntax.Variant(syntax.LangBash)).Parse(bytes.NewReader(src), "")
	if err != nil {
		var pe syntax.ParseError
		at := 0
		if errors.As(err, &pe) {
			at = int(pe.Pos.Offset())
		}
		res.Diags = append(res.Diags, Diag{Start: at, End: at, Reason: err.Error()})
		return res, nil
	}
	off := func(p syntax.Pos) int { return int(p.Offset()) }
	syntax.Walk(f, func(n syntax.Node) bool {
		switch x := n.(type) {
		case *syntax.Comment:
			s := off(x.Hash)
			res.Spans = append(res.Spans, Span{s, s + 1 + len(x.Text), LineComment})
		case *syntax.SglQuoted:
			res.Spans = append(res.Spans, Span{off(x.Pos()), off(x.End()), String})
		case *syntax.DblQuoted:
			for _, part := range x.Parts {
				if lit, ok := part.(*syntax.Lit); ok {
					res.Spans = append(res.Spans, Span{off(lit.Pos()), off(lit.End()), String})
				}
			}
		case *syntax.Redirect:
			if x.Hdoc != nil && x.Hdoc.Pos().IsValid() && len(x.Hdoc.Parts) > 0 {
				s, e := off(x.Hdoc.Pos()), off(x.Hdoc.End())
				// The terminator line follows the body.
				for e < len(src) && src[e] != '\n' {
					e++
				}
				res.Spans = append(res.Spans, Span{s, e, Heredoc})
			}
		}
		return true
	})
	if bytes.HasPrefix(src, []byte("#!")) {
		res.Anchors.Shebang = 1
	}
	return res, nil
}
