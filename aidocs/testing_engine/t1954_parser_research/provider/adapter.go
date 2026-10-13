package provider

import (
	"fmt"
	"sort"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

// NeedRecords: annotation records read through ParseFile — line classes and,
// for Python, the module docstring (whose read records need DocLiterals).
// It refines the shared design's NeedLexical, which covers classes only.
const NeedRecords Need = 1 << 7

// requiredAnchors are the anchors a fresh file-level insertion consults: the
// landed fixedPosition for the M2.2 languages (Go: the package clause;
// Kotlin: imports, then the package; bash and Python read only line classes
// and the docstring) and the proposed rules for the research languages.
var requiredAnchors = map[string]AnchorSet{
	"bash":       0,
	"python":     0,
	"go":         APackage,
	"kotlin":     APackage | AImportEnd,
	"typescript": AImportEnd | APrologue,
	"tsx":        AImportEnd | APrologue,
	"javascript": AImportEnd | APrologue,
	"java":       APackage | AImportEnd,
	"rust":       AInnerAttrEnd | AImportEnd,
	"swift":      AImportEnd,
}

// RequiredAnchors is the anchor set a fresh file-level insertion needs.
func RequiredAnchors(lang string) AnchorSet { return requiredAnchors[lang] }

// Check reports what caps lacks for need in lang (nil: supported).
func Check(lang string, caps Capabilities, need Need) error {
	var missing []string
	if need&(NeedRecords|NeedWrite) != 0 && lang == "python" && !caps.DocLiterals {
		missing = append(missing, "DocLiterals")
	}
	if need&NeedWrite != 0 && !caps.Errors {
		missing = append(missing, "Errors")
	}
	if need&NeedFreshFileInsert != 0 {
		req, ok := requiredAnchors[lang]
		if !ok {
			missing = append(missing, "placement-rule("+lang+")")
		}
		for _, n := range (req &^ caps.Anchors).Names() {
			missing = append(missing, "A"+n)
		}
	}
	if len(missing) > 0 {
		return &UnsupportedCapabilityError{Missing: missing}
	}
	return nil
}

// ToContext builds the annot.Context the landed grammar and rewriter read
// from a provider Result. It enforces Check itself, so no caller can hand
// annot a context the provider cannot justify, and it never reconstructs
// what the provider did not report: an undeclared anchor stays 0 and only a
// NeedFreshFileInsert request — which requires the anchor — could reach the
// code that reads it.
//
// Line classes follow annot's definition, from the line's first byte:
//   - Literal: the line starts strictly inside a String, BlockComment,
//     DocLiteral or Other span, or anywhere inside a Heredoc span (a heredoc
//     body always begins at a line start);
//   - Comment: otherwise, a LineComment span starts at the line's first
//     non-blank byte and the bytes there begin with the language's leader;
//   - Code: everything else.
//
// Any Diag makes the context Uncertain (fail closed even when the provider
// does not declare Errors).
func ToContext(lang string, src []byte, caps Capabilities, res Result, need Need) (annot.Context, error) {
	if err := Check(lang, caps, need); err != nil {
		return annot.Context{}, err
	}
	l, ok := LangByName(lang)
	if !ok {
		return annot.Context{}, fmt.Errorf("ToContext: unknown language %q", lang)
	}
	for _, s := range res.Spans {
		if s.Start < 0 || s.End > len(src) || s.Start > s.End {
			return annot.Context{}, fmt.Errorf("ToContext: span [%d,%d) out of bounds (len %d)", s.Start, s.End, len(src))
		}
	}
	starts := LineStarts(src)
	ctx := annot.Context{Class: make([]annot.LineClass, len(starts))}

	spans := append([]Span(nil), res.Spans...)
	sort.Slice(spans, func(i, j int) bool { return spans[i].Start < spans[j].Start })
	commentAt := map[int]bool{}
	for _, s := range spans {
		if s.Kind == LineComment {
			commentAt[s.Start] = true
		}
	}
	for i, s := range starts {
		if insideData(spans, s) {
			ctx.Class[i] = annot.Literal
			continue
		}
		f := s
		for f < len(src) && (src[f] == ' ' || src[f] == '\t') {
			f++
		}
		if commentAt[f] && hasPrefixAt(src, f, l.Leader) {
			ctx.Class[i] = annot.Comment
		}
	}
	if len(res.Diags) > 0 {
		d := res.Diags[0]
		ctx.Uncertain = &annot.Unclosed{Line: LineOf(starts, d.Start), Construct: d.Reason}
	}
	if res.Doc != nil && caps.DocLiterals {
		for _, lit := range res.Doc.Literals {
			if lit.ContentStart < 0 || lit.ContentEnd > len(src) || lit.ContentStart > lit.ContentEnd {
				return annot.Context{}, fmt.Errorf("ToContext: doc literal [%d,%d) out of bounds", lit.ContentStart, lit.ContentEnd)
			}
			sl, sc := LineCol(starts, lit.ContentStart)
			el, ec := LineCol(starts, lit.ContentEnd)
			ctx.Docs = append(ctx.Docs, annot.DocSpan{StartLine: sl, StartCol: sc, EndLine: el, EndCol: ec, Raw: lit.Raw})
		}
		if len(ctx.Docs) > 0 {
			end := res.Doc.StmtEnd
			if end > 0 {
				end--
			}
			ctx.DocEnd = LineOf(starts, end)
		}
	}
	if caps.Anchors&APackage != 0 {
		ctx.Package = res.Anchors.Package
	}
	if caps.Anchors&AImportEnd != 0 {
		ctx.Import = res.Anchors.ImportEnd
	}
	return ctx, nil
}

func insideData(spans []Span, off int) bool {
	for _, s := range spans {
		if s.Start > off {
			break
		}
		switch s.Kind {
		case Heredoc:
			if s.Start <= off && off < s.End {
				return true
			}
		case String, BlockComment, DocLiteralKind, Other:
			if s.Start < off && off < s.End {
				return true
			}
		}
	}
	return false
}

func hasPrefixAt(src []byte, at int, p string) bool {
	return at+len(p) <= len(src) && string(src[at:at+len(p)]) == p
}

// LineStarts returns the byte offset of every line, split as annot splits:
// on "\n", with a final "\n" not starting another line.
func LineStarts(src []byte) []int {
	starts := []int{0}
	for i, b := range src {
		if b == '\n' && i+1 < len(src) {
			starts = append(starts, i+1)
		}
	}
	if len(src) == 0 {
		return nil
	}
	return starts
}

// LineOf is the 1-based line holding byte off.
func LineOf(starts []int, off int) int {
	i := sort.Search(len(starts), func(i int) bool { return starts[i] > off })
	if i == 0 {
		return 1
	}
	return i
}

// LineCol is the 1-based line and 0-based byte column of off.
func LineCol(starts []int, off int) (int, int) {
	l := LineOf(starts, off)
	return l, off - starts[l-1]
}
