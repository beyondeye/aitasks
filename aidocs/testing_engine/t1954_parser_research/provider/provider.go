// Package provider is the t1954 experimental interface: a candidate lexical
// provider reports comment/literal byte ranges, diagnostics, placement
// anchors and (Python) docstring literals, and the shared adapter ToContext
// turns that into the landed annot.Context so the real M2.2 grammar and
// rewriter run on it unchanged (the evaluation seam).
//
// The interface is the one in the t1954 shared design
// (aiplans/p1954_research_multilanguage_annotation_parsers.md, "Experimental
// interface"), including the capability-availability amendment: an anchor a
// provider does not declare is unknown, never "none".
package provider

import (
	"errors"
	"fmt"
	"strings"
)

// SpanKind is what a reported byte range is.
type SpanKind uint8

const (
	LineComment SpanKind = iota
	BlockComment
	String
	Heredoc
	DocLiteralKind // the shared design's "DocLiteral" span kind (renamed: DocLiteral is also a type)
	Other
)

func (k SpanKind) String() string {
	switch k {
	case LineComment:
		return "line-comment"
	case BlockComment:
		return "block-comment"
	case String:
		return "string"
	case Heredoc:
		return "heredoc"
	case DocLiteralKind:
		return "doc-literal"
	}
	return "other"
}

// Span is a byte range [Start, End) as the provider reports it.
type Span struct {
	Start, End int
	Kind       SpanKind
}

// Diag is malformed or unsupported input: an ERROR/MISSING node, an error
// token, an unterminated construct, a form the provider does not model.
type Diag struct {
	Start, End int
	Reason     string
}

// Anchors are placement anchors as 1-based lines. A zero field means "none"
// ONLY when the matching bit is declared in Capabilities.Anchors.
type Anchors struct {
	Shebang, HeaderEnd, Package, ImportEnd, Prologue, InnerAttrEnd int
}

// AnchorSet has one bit per Anchors field.
type AnchorSet uint8

const (
	AShebang AnchorSet = 1 << iota
	AHeaderEnd
	APackage
	AImportEnd
	APrologue
	AInnerAttrEnd
)

var anchorNames = []struct {
	bit  AnchorSet
	name string
}{
	{AShebang, "Shebang"}, {AHeaderEnd, "HeaderEnd"}, {APackage, "Package"},
	{AImportEnd, "ImportEnd"}, {APrologue, "Prologue"}, {AInnerAttrEnd, "InnerAttrEnd"},
}

// Names lists the anchors in s, in declaration order.
func (s AnchorSet) Names() []string {
	var out []string
	for _, a := range anchorNames {
		if s&a.bit != 0 {
			out = append(out, a.name)
		}
	}
	return out
}

// DocLiteral is one literal of the Python module docstring's first
// statement: the byte offsets of its CONTENT (after prefix and opening
// quotes, before the closing quotes) and whether it is raw.
type DocLiteral struct {
	ContentStart, ContentEnd int
	Raw                      bool
}

// DocInfo is the Python module docstring, normalised by the provider.
type DocInfo struct {
	Literals []DocLiteral // every literal of the first statement, in order
	StmtEnd  int          // byte offset just past the complete statement (closing parens included)
}

// Capabilities is what a provider establishes for a language.
type Capabilities struct {
	TokenRanges bool      // exposes exact token/node byte ranges
	FullCover   bool      // Result.Leaves partition the whole input
	Errors      bool      // reports malformed input as Diags
	DocLiterals bool      // fills Result.Doc (Python)
	Anchors     AnchorSet // anchors the provider DETERMINES; undeclared = unknown
}

// Result is one analysis.
type Result struct {
	Spans   []Span
	Leaves  []Span // only with Capabilities.FullCover: every token/leaf, in order
	Diags   []Diag // non-empty => uncertain; never silently empty on failure
	Anchors Anchors
	Doc     *DocInfo // Python only; nil = no docstring (meaningful only with DocLiterals)
}

// Provider is a candidate lexical provider.
type Provider interface {
	Name() string
	Langs() []string
	Caps(lang string) Capabilities
	// Analyze fails only when the provider itself fails; that is reported
	// "unsupported", never "no comments".
	Analyze(lang string, src []byte) (Result, error)
}

// Need is what an operation requires of a provider (a bit set).
type Need uint8

const (
	// NeedLexical: line classes (and, for Python, docstring read records).
	NeedLexical Need = 1 << iota
	// NeedWrite: any edit — certainty must be established.
	NeedWrite
	// NeedFreshFileInsert: the file-level block has no annotation yet, the
	// one path that reaches fixedPosition / a proposed placement rule.
	NeedFreshFileInsert
)

// ErrUnsupportedCapability marks an operation the provider cannot support.
var ErrUnsupportedCapability = errors.New("unsupported capability")

// UnsupportedCapabilityError names what is missing.
type UnsupportedCapabilityError struct{ Missing []string }

func (e *UnsupportedCapabilityError) Error() string {
	return fmt.Sprintf("unsupported:%s", strings.Join(e.Missing, ","))
}

func (e *UnsupportedCapabilityError) Unwrap() error { return ErrUnsupportedCapability }
